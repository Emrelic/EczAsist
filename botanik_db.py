"""
Botanik EOS Veritabanı Bağlantı Modülü
SQL Server üzerinden Botanik veritabanına erişim sağlar.

============================================================================
  KIRMIZI ÇİZGİ — BU MODÜL SADECE OKUMAYA İZİN VERİR
============================================================================
  Botanik EOS (SQL Server) veritabanına ASLA yazma yapılmaz.
  Sadece SELECT sorguları çalıştırılabilir.

  YASAKLI: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE,
           EXEC, EXECUTE, GRANT, REVOKE, DENY, BACKUP, RESTORE,
           SHUTDOWN, KILL ve benzeri kayıt değiştiren her komut.

  Guard: BotanikDB.sorgu_calistir() -> _guvenlik_kontrolu()
         Yasaklı komut tespit edilirse sorgu çalıştırılmadan reddedilir.

  Bu kuralı geçici olarak bile esnetme. Hiçbir istisnası yoktur.
  Ayrıntı: CLAUDE.md §2 (KIRMIZI ÇİZGİLER bölümü).
============================================================================
"""

import pyodbc
import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)

# db_config.json yolu
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_CONFIG_PATH = os.path.join(_SCRIPT_DIR, "db_config.json")


def _db_config_yukle():
    """db_config.json dosyasından bağlantı ayarlarını yükle"""
    if os.path.exists(_DB_CONFIG_PATH):
        try:
            with open(_DB_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if config.get('kurulum_tamamlandi'):
                return config
        except Exception as e:
            logger.warning("db_config.json okunamadi: %s", e)
    return None


class BotanikDB:
    """Botanik EOS SQL Server veritabanı bağlantı sınıfı"""

    # Test ortamı bağlantı ayarları (localhost)
    TEST_CONFIG = {
        'server': 'localhost',
        'database': 'eczane_test',
        'trusted_connection': True,
        'trust_server_certificate': True
    }

    # PRODUCTION ortamı - db_config.json varsa oradan okunur, yoksa fallback
    # 2026-05-14: sa/123 -> calede (db_datareader + DENY'li salt-okuma).
    # SQL Server motoru calede icin INSERT/UPDATE/DELETE/DDL/EXEC DENY etti;
    # bu sayede config silinse bile EczAsist asla yazma yapamaz.
    _FALLBACK_CONFIG = {
        'server': r'192.168.1.120\BOTANIKSQL',
        'database': 'eczane',
        'trusted_connection': False,
        'user': 'calede',
        'password': '152634485967',
        'trust_server_certificate': True
    }

    # db_config.json varsa onu kullan
    _harici_config = _db_config_yukle()
    PRODUCTION_CONFIG = _harici_config if _harici_config else _FALLBACK_CONFIG

    # Varsayılan olarak PRODUCTION kullan
    DEFAULT_CONFIG = PRODUCTION_CONFIG

    # Referans: kirmizi cizgi listesi (CLAUDE.md §2).
    # 2026-05-14'ten beri guard allow-list mantigi kullaniyor (sadece SELECT/WITH);
    # bu liste artik aktif kontrolde kullanilmiyor, sadece dokuman amacli kaldi.
    YASAKLI_KOMUTLAR_REFERANS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE', 'DENY',
        'BACKUP', 'RESTORE', 'SHUTDOWN', 'KILL', 'MERGE',
    ]

    def __init__(self, config: Optional[Dict] = None, production: bool = True):
        """
        Args:
            config: Özel bağlantı ayarları (opsiyonel)
            production: True=gerçek sunucu, False=test sunucusu
        """
        if config:
            self.config = config
        else:
            self.config = self.PRODUCTION_CONFIG if production else self.TEST_CONFIG
        self.conn = None
        self.cursor = None
        self.son_sorgu_hatasi = None  # son SQL hata metni (tanilama icin)

    def baglan(self) -> bool:
        """Veritabanına bağlan"""
        try:
            conn_str = self._connection_string_olustur()
            self.conn = pyodbc.connect(conn_str, timeout=30)
            self.conn.timeout = 300  # Query timeout: 5 dakika
            self.cursor = self.conn.cursor()
            logger.info(f"Veritabanına bağlandı: {self.config['database']}")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {e}")
            return False

    def _connection_string_olustur(self) -> str:
        """Bağlantı string'i oluştur"""
        parts = [
            f"DRIVER={{SQL Server}}",
            f"SERVER={self.config['server']}",
            f"DATABASE={self.config['database']}"
        ]

        if self.config.get('trusted_connection'):
            parts.append("Trusted_Connection=yes")
        else:
            parts.append(f"UID={self.config.get('user', 'sa')}")
            parts.append(f"PWD={self.config.get('password', '')}")

        if self.config.get('trust_server_certificate'):
            parts.append("TrustServerCertificate=yes")

        return ";".join(parts)

    def kapat(self):
        """Bağlantıyı kapat"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            logger.info("Veritabanı bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Bağlantı kapatma hatası: {e}")

    def _guvenlik_kontrolu(self, sql: str) -> bool:
        """
        ALLOW-LIST guard: sorgu mutlaka SELECT veya WITH (CTE) ile baslamali.

        - Lider yorumlar (-- ve /* */) atlanir
        - Lider noktali virgul tolere edilir (;WITH kalibi icin)
        - Bos / sadece-yorum / SELECT|WITH disi tum sorgular reddedilir

        Defense-in-depth: SQL Server motoru calede icin INSERT/UPDATE/DELETE/
        ALTER/CREATE/EXECUTE vb.'yi DENY etti — bu guard ek bir kullanici-hatasi
        ve yanlislikla yazma denemesi yakalayicisi.

        Returns:
            True: SELECT/WITH ile basliyor, calistirilabilir
            False: Reddedildi (yazma niyeti veya bozuk sorgu)
        """
        if not sql or not sql.strip():
            logger.error("GUVENLIK: Bos sorgu reddedildi")
            return False

        kalan = sql.strip()
        guvenlik_sayaci = 0  # Sonsuz dongu koruma
        while kalan and guvenlik_sayaci < 100:
            guvenlik_sayaci += 1
            # Lider noktali virgul (;WITH kalibi icin)
            if kalan.startswith(';'):
                kalan = kalan[1:].lstrip()
                continue
            # Tek satir yorum
            if kalan.startswith('--'):
                nl = kalan.find('\n')
                if nl < 0:
                    logger.error("GUVENLIK: Sorgu tamamen yorumdan ibaret")
                    return False
                kalan = kalan[nl + 1:].lstrip()
                continue
            # Blok yorum
            if kalan.startswith('/*'):
                kapanis = kalan.find('*/')
                if kapanis < 0:
                    logger.error("GUVENLIK: Kapanmamis blok yorum")
                    return False
                kalan = kalan[kapanis + 2:].lstrip()
                continue
            break

        if not kalan:
            logger.error("GUVENLIK: Yorumlar sonrasi bos sorgu")
            return False

        # Ilk kelimeyi izole et
        kalan_uc = kalan.upper()
        for izinli in ('SELECT', 'WITH'):
            if kalan_uc.startswith(izinli):
                sonraki_idx = len(izinli)
                if len(kalan_uc) == sonraki_idx:
                    return True  # cikis token: sadece SELECT/WITH
                sonraki_kar = kalan_uc[sonraki_idx]
                # Whitespace veya parantez OK; harf/rakam ise SELECTOR/WITHIN gibi yanlis match
                if sonraki_kar in ' \t\n\r\f\v(':
                    return True
                # Devam: yanlis match, izinli liste icinde olmayan token'a dustuk
                break

        # Reddedildi — ilk token'i logla
        try:
            ilk_token = kalan_uc.split(None, 1)[0][:20]
        except Exception:
            ilk_token = '???'
        logger.error(
            "GUVENLIK: Sadece SELECT/WITH izinli; reddedilen ilk token: %s",
            ilk_token,
        )
        return False

    def sorgu_calistir(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        SQL sorgusu çalıştır ve sonuçları döndür.
        GÜVENLİK: Sadece SELECT sorguları çalıştırılabilir!
        Son hata mesajı self.son_sorgu_hatasi'na kaydedilir (boş sonuç tanılaması için).
        """
        self.son_sorgu_hatasi = None
        try:
            # GÜVENLİK KONTROLÜ
            if not self._guvenlik_kontrolu(sql):
                self.son_sorgu_hatasi = "Guvenlik kontrolu reddetti"
                logger.error("SORGU REDDEDİLDİ: Güvenlik kontrolünden geçemedi!")
                return []

            if not self.conn:
                if not self.baglan():
                    self.son_sorgu_hatasi = "DB baglantisi kurulamadi"
                    return []

            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)

            columns = [column[0] for column in self.cursor.description]
            results = []
            for row in self.cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results

        except Exception as e:
            self.son_sorgu_hatasi = str(e)
            logger.error(f"Sorgu hatası: {e}")
            return []

    def tum_hareketler_getir(
        self,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        hareket_tipi: Optional[str] = None,
        urun_adi: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Tüm stok hareketlerini getir - KAPSAMLI TÜM ALANLAR
        """
        sql = f"""
        SELECT TOP {limit} * FROM (

            -- =====================================================
            -- 1. FATURA GİRİŞİ (Depodan Alım)
            -- =====================================================
            SELECT
                'FATURA_GIRIS' as HareketTipi,
                'GIRIS' as Yon,
                fg.FGFaturaTarihi as Tarih,
                fg.FGFaturaNo as BelgeNo,
                d.DepoAdi as Ilgili,
                u.UrunAdi,
                u.UrunId,
                fs.FSUrunAdet as Adet,
                fs.FSEtiketFiyat as EtiketFiyat,
                fs.FSBirimFiyat as BirimFiyat,
                fs.FSUrunAdet * COALESCE(fs.FSBirimFiyat, fs.FSMaliyet) as Tutar,
                fg.FGVadeTarihi as VadeTarihi,
                NULL as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                d.DepoAdi as DepoAdi,
                NULL as EczaneAdi,
                fs.FSMaliyet as Maliyet,
                fs.FSIskontoKamu as IskontoKamu,
                fs.FSIskontoEczane as IskontoEczane,
                fs.FSIskontoTicari as IskontoTicari,
                NULL as FiyatFarki,
                NULL as Iskonto,
                fg.FGId as BelgeId
            FROM FaturaGiris fg
            JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
            JOIN Urun u ON fs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId AND fg.FGIlgiliTipi = 1
            WHERE fg.FGSilme = 0

            UNION ALL

            -- =====================================================
            -- 2. FATURA ÇIKIŞI
            -- =====================================================
            SELECT
                'FATURA_CIKIS' as HareketTipi,
                'CIKIS' as Yon,
                CAST(fc.FGFaturaTarihi as date) as Tarih,
                fc.FGFaturaNo as BelgeNo,
                COALESCE(d.DepoAdi, c.MusteriAdiSoyadi, 'Bilinmiyor') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                fcs.FSUrunAdet as Adet,
                fcs.FSEtiketFiyat as EtiketFiyat,
                fcs.FSBirimFiyat as BirimFiyat,
                fcs.FSUrunAdet * fcs.FSBirimFiyat as Tutar,
                CAST(fc.FGVadeTarihi as date) as VadeTarihi,
                c.MusteriAdiSoyadi as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                d.DepoAdi as DepoAdi,
                NULL as EczaneAdi,
                fcs.FSMaliyet as Maliyet,
                fcs.FSIskontoKamu as IskontoKamu,
                fcs.FSIskontoEczane as IskontoEczane,
                fcs.FSIskontoTicari as IskontoTicari,
                NULL as FiyatFarki,
                NULL as Iskonto,
                fc.FGId as BelgeId
            FROM FaturaCikis fc
            JOIN FaturaCikisSatir fcs ON fc.FGId = fcs.FSFGId
            JOIN Urun u ON fcs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fc.FGIlgiliId = d.DepoId AND fc.FGIlgiliTipi = 1
            LEFT JOIN Musteri c ON fc.FGIlgiliId = c.MusteriId AND fc.FGIlgiliTipi = 2
            WHERE fc.FGSilme = 0

            UNION ALL

            -- =====================================================
            -- 3. REÇETELİ SATIŞ
            -- =====================================================
            SELECT
                'RECETE_SATIS' as HareketTipi,
                'CIKIS' as Yon,
                CAST(ra.RxIslemTarihi as date) as Tarih,
                ra.RxEReceteNo as BelgeNo,
                COALESCE(k.KurumAdi, 'Kurum') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                ri.RIAdet as Adet,
                ri.RIEtiketFiyati as EtiketFiyat,
                ri.RIKurumFiyati as BirimFiyat,
                ri.RIToplam as Tutar,
                NULL as VadeTarihi,
                m.MusteriAdiSoyadi as HastaAdi,
                COALESCE(dok.DoktorAdiSoyadi, dok.DoktorAdi + ' ' + ISNULL(dok.DoktorSoyadi, '')) as DoktorAdi,
                h.HastaneAdi as TesisAdi,
                ra.RxEReceteNo as ReceteNo,
                k.KurumAdi as KurumAdi,
                NULL as DepoAdi,
                NULL as EczaneAdi,
                NULL as Maliyet,
                ri.RIKurumIsk as IskontoKamu,
                NULL as IskontoEczane,
                NULL as IskontoTicari,
                ri.RIFiyatFarki as FiyatFarki,
                ri.RIIskonto as Iskonto,
                ra.RxId as BelgeId
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
            JOIN Urun u ON ri.RIUrunId = u.UrunId
            LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
            LEFT JOIN Doktor dok ON ra.RxDoktorId = dok.DoktorId
            LEFT JOIN Hastane h ON ra.RxHastaneId = h.HastaneId
            LEFT JOIN Kurum k ON ra.RxKurumId = k.KurumId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0

            UNION ALL

            -- =====================================================
            -- 4. TAKAS GİRİŞ (Eczaneden Gelen)
            -- =====================================================
            SELECT
                'TAKAS_GIRIS' as HareketTipi,
                'GIRIS' as Yon,
                CAST(t.TakasTarihi as date) as Tarih,
                CAST(t.TakasId as nvarchar(50)) as BelgeNo,
                COALESCE(e.EczaneAdi, 'Eczane') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                ts.TSUrunAdedi as Adet,
                ts.TSUrunFiyatEtiket as EtiketFiyat,
                ts.TSUrunFiyat as BirimFiyat,
                ts.TSUrunAdedi * ts.TSUrunFiyat as Tutar,
                NULL as VadeTarihi,
                NULL as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                NULL as DepoAdi,
                e.EczaneAdi as EczaneAdi,
                NULL as Maliyet,
                ts.TSUrunIskontoKamu as IskontoKamu,
                NULL as IskontoEczane,
                NULL as IskontoTicari,
                NULL as FiyatFarki,
                NULL as Iskonto,
                t.TakasId as BelgeId
            FROM Takas t
            JOIN TakasSatir ts ON t.TakasId = ts.TSTakasId
            JOIN Urun u ON ts.TSUrunId = u.UrunId
            LEFT JOIN Eczaneler e ON t.TakasEczaneId = e.EczaneId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1

            UNION ALL

            -- =====================================================
            -- 5. TAKAS ÇIKIŞ (Eczaneye Giden)
            -- =====================================================
            SELECT
                'TAKAS_CIKIS' as HareketTipi,
                'CIKIS' as Yon,
                CAST(t.TakasTarihi as date) as Tarih,
                CAST(t.TakasId as nvarchar(50)) as BelgeNo,
                COALESCE(e.EczaneAdi, 'Eczane') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                ts.TSUrunAdedi as Adet,
                ts.TSUrunFiyatEtiket as EtiketFiyat,
                ts.TSUrunFiyat as BirimFiyat,
                ts.TSUrunAdedi * ts.TSUrunFiyat as Tutar,
                NULL as VadeTarihi,
                NULL as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                NULL as DepoAdi,
                e.EczaneAdi as EczaneAdi,
                NULL as Maliyet,
                ts.TSUrunIskontoKamu as IskontoKamu,
                NULL as IskontoEczane,
                NULL as IskontoTicari,
                NULL as FiyatFarki,
                NULL as Iskonto,
                t.TakasId as BelgeId
            FROM Takas t
            JOIN TakasSatir ts ON t.TakasId = ts.TSTakasId
            JOIN Urun u ON ts.TSUrunId = u.UrunId
            LEFT JOIN Eczaneler e ON t.TakasEczaneId = e.EczaneId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 0

            UNION ALL

            -- =====================================================
            -- 6. İADE (Depoya İade)
            -- =====================================================
            SELECT
                'IADE' as HareketTipi,
                'CIKIS' as Yon,
                CAST(it.ITKayitTarihi as date) as Tarih,
                CAST(it.ITId as nvarchar(50)) as BelgeNo,
                COALESCE(d.DepoAdi, 'Depo') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                it.ITUrunAdet as Adet,
                u.UrunFiyatEtiket as EtiketFiyat,
                it.ITBirimMaliyet as BirimFiyat,
                it.ITUrunAdet * it.ITBirimMaliyet as Tutar,
                NULL as VadeTarihi,
                NULL as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                d.DepoAdi as DepoAdi,
                NULL as EczaneAdi,
                it.ITBirimMaliyet as Maliyet,
                NULL as IskontoKamu,
                NULL as IskontoEczane,
                NULL as IskontoTicari,
                NULL as FiyatFarki,
                NULL as Iskonto,
                it.ITId as BelgeId
            FROM IadeTakip it
            JOIN Urun u ON it.ITUrunId = u.UrunId
            LEFT JOIN Depo d ON it.ITDepoId = d.DepoId

            UNION ALL

            -- =====================================================
            -- 7. ELDEN SATIŞ (Parakende/Perakende Satış)
            -- =====================================================
            SELECT
                'ELDEN_SATIS' as HareketTipi,
                'CIKIS' as Yon,
                CAST(ea.RxIslemTarihi as date) as Tarih,
                COALESCE(ea.RxBelgeNo, CAST(ea.RxId as nvarchar(50))) as BelgeNo,
                COALESCE(m.MusteriAdiSoyadi, 'Parakende') as Ilgili,
                u.UrunAdi,
                u.UrunId,
                ei.RIAdet as Adet,
                ei.RIEtiketFiyati as EtiketFiyat,
                ei.RIToplam / NULLIF(ei.RIAdet, 0) as BirimFiyat,
                ei.RIToplam as Tutar,
                NULL as VadeTarihi,
                m.MusteriAdiSoyadi as HastaAdi,
                NULL as DoktorAdi,
                NULL as TesisAdi,
                NULL as ReceteNo,
                NULL as KurumAdi,
                NULL as DepoAdi,
                NULL as EczaneAdi,
                NULL as Maliyet,
                NULL as IskontoKamu,
                NULL as IskontoEczane,
                NULL as IskontoTicari,
                NULL as FiyatFarki,
                ei.RIIskonto as Iskonto,
                ea.RxId as BelgeId
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
            JOIN Urun u ON ei.RIUrunId = u.UrunId
            LEFT JOIN Musteri m ON ea.RxMusteriId = m.MusteriId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0

        ) AS TumHareketler
        WHERE 1=1
        """

        # Tarih filtreleri
        if baslangic_tarih:
            tarih_str = baslangic_tarih.strftime("%Y-%m-%d")
            sql += f" AND Tarih >= '{tarih_str}'"

        if bitis_tarih:
            tarih_str = bitis_tarih.strftime("%Y-%m-%d")
            sql += f" AND Tarih <= '{tarih_str}'"

        # Hareket tipi filtresi
        if hareket_tipi:
            sql += f" AND HareketTipi = '{hareket_tipi}'"

        # Ürün adı filtresi
        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            sql += f" AND UrunAdi LIKE '%{urun_adi_temiz}%'"

        sql += " ORDER BY Tarih DESC, BelgeId DESC"

        return self.sorgu_calistir(sql)

    def fatura_giris_detay(self, baslangic_tarih=None, bitis_tarih=None, depo_id=None, limit=1000):
        """Fatura girişleri detaylı"""
        sql = f"""
        SELECT TOP {limit}
            fg.FGFaturaTarihi as Tarih,
            fg.FGFaturaNo as FaturaNo,
            d.DepoAdi,
            u.UrunAdi,
            fs.FSUrunAdet as Miktar,
            fs.FSEtiketFiyat as EtiketFiyat,
            fs.FSBirimFiyat as AlisFiyati,
            fs.FSUrunAdet * fs.FSBirimFiyat as ToplamTutar,
            fg.FGVadeTarihi as VadeTarihi,
            fg.FGToplamTutar as FaturaToplamı
        FROM FaturaGiris fg
        JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
        JOIN Urun u ON fs.FSUrunId = u.UrunId
        LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId
        WHERE fg.FGSilme = 0
        """

        if baslangic_tarih:
            sql += f" AND fg.FGFaturaTarihi >= '{baslangic_tarih.strftime('%Y-%m-%d')}'"
        if bitis_tarih:
            sql += f" AND fg.FGFaturaTarihi <= '{bitis_tarih.strftime('%Y-%m-%d')}'"
        if depo_id:
            sql += f" AND fg.FGIlgiliId = {depo_id}"

        sql += " ORDER BY fg.FGFaturaTarihi DESC"
        return self.sorgu_calistir(sql)

    def recete_satis_detay(self, baslangic_tarih=None, bitis_tarih=None, limit=1000):
        """Reçeteli satışlar detaylı"""
        sql = f"""
        SELECT TOP {limit}
            CAST(ra.RxIslemTarihi as date) as Tarih,
            ra.RxEReceteNo as ReceteNo,
            m.MusteriAdiSoyadi as HastaAdi,
            m.MusteriTCKN as HastaTCKN,
            COALESCE(dok.DoktorAdiSoyadi, dok.DoktorAdi + ' ' + ISNULL(dok.DoktorSoyadi, '')) as DoktorAdi,
            h.HastaneAdi as TesisAdi,
            u.UrunAdi,
            ri.RIAdet as Miktar,
            ri.RIEtiketFiyati as EtiketFiyat,
            ri.RIKurumFiyati as KurumFiyati,
            ri.RIFiyatFarki as FiyatFarki,
            ri.RIToplam as Tutar,
            k.KurumAdi as KurumAdi
        FROM ReceteAna ra
        JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
        JOIN Urun u ON ri.RIUrunId = u.UrunId
        LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
        LEFT JOIN Doktor dok ON ra.RxDoktorId = dok.DoktorId
        LEFT JOIN Hastane h ON ra.RxHastaneId = h.HastaneId
        LEFT JOIN Kurum k ON ra.RxKurumId = k.KurumId
        WHERE ra.RxSilme = 0 AND ri.RISilme = 0
        """

        if baslangic_tarih:
            sql += f" AND CAST(ra.RxIslemTarihi as date) >= '{baslangic_tarih.strftime('%Y-%m-%d')}'"
        if bitis_tarih:
            sql += f" AND CAST(ra.RxIslemTarihi as date) <= '{bitis_tarih.strftime('%Y-%m-%d')}'"

        sql += " ORDER BY ra.RxIslemTarihi DESC"
        return self.sorgu_calistir(sql)

    def urun_ara(self, arama: str, limit: int = 50) -> List[Dict]:
        """Ürün adına göre ara — parametreli (SQL injection-safe)."""
        sql = f"""
        SELECT TOP {int(limit)}
            UrunId,
            UrunAdi,
            UrunFiyatEtiket,
            UrunStokDepo + UrunStokRaf + UrunStokAcik as ToplamStok
        FROM Urun
        WHERE UrunAdi LIKE ? AND UrunSilme = 0
        ORDER BY UrunAdi
        """
        return self.sorgu_calistir(sql, (f"%{arama}%",))

    def iade_fatura_detay_getir(self, fatura_no: str = None, fatura_tarihi: str = None, depo_adi: str = None) -> List[Dict]:
        """
        İade faturası detaylarını getir.
        FaturaCikis tablosundan fatura no veya tarihe göre sorgular.
        IadeTakip tablosundan da tarihe göre sorgular.
        İkisini birleştirip döndürür.
        """
        results = []

        # 1. FaturaCikis'ten iade faturası satırları
        if fatura_no:
            safe_fatura_no = str(fatura_no).replace("'", "''")
            sql = f"""
            SELECT
                fc.FGFaturaNo as FaturaNo,
                CAST(fc.FGFaturaTarihi as date) as FaturaTarihi,
                COALESCE(d.DepoAdi, 'Bilinmiyor') as DepoAdi,
                u.UrunAdi,
                u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                fcs.FSUrunAdet as Miktar,
                fcs.FSEtiketFiyat as EtiketFiyat,
                fcs.FSBirimFiyat as BirimFiyat,
                fcs.FSUrunAdet * fcs.FSBirimFiyat as ToplamTutar,
                fcs.FSMaliyet as Maliyet,
                u.UrunFiyatEtiket as GuncelEtiketFiyat,
                fc.FGToplamTutar as FaturaToplamTutar,
                'FATURA_CIKIS' as Kaynak
            FROM FaturaCikis fc
            JOIN FaturaCikisSatir fcs ON fc.FGId = fcs.FSFGId
            JOIN Urun u ON fcs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fc.FGIlgiliId = d.DepoId AND fc.FGIlgiliTipi = 1
            WHERE fc.FGSilme = 0
            AND fc.FGFaturaNo = '{safe_fatura_no}'
            ORDER BY u.UrunAdi
            """
            fc_results = self.sorgu_calistir(sql)
            if fc_results:
                results.extend(fc_results)

        # 2. FaturaCikis'ten tarihe göre (fatura no yoksa veya sonuç boşsa)
        if not results and fatura_tarihi:
            safe_tarih = str(fatura_tarihi).replace("'", "''")
            depo_filtre = ""
            if depo_adi:
                safe_depo = str(depo_adi).replace("'", "''")
                depo_filtre = f"AND d.DepoAdi LIKE '%{safe_depo}%'"

            sql = f"""
            SELECT
                fc.FGFaturaNo as FaturaNo,
                CAST(fc.FGFaturaTarihi as date) as FaturaTarihi,
                COALESCE(d.DepoAdi, 'Bilinmiyor') as DepoAdi,
                u.UrunAdi,
                u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                fcs.FSUrunAdet as Miktar,
                fcs.FSEtiketFiyat as EtiketFiyat,
                fcs.FSBirimFiyat as BirimFiyat,
                fcs.FSUrunAdet * fcs.FSBirimFiyat as ToplamTutar,
                fcs.FSMaliyet as Maliyet,
                u.UrunFiyatEtiket as GuncelEtiketFiyat,
                fc.FGToplamTutar as FaturaToplamTutar,
                'FATURA_CIKIS' as Kaynak
            FROM FaturaCikis fc
            JOIN FaturaCikisSatir fcs ON fc.FGId = fcs.FSFGId
            JOIN Urun u ON fcs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fc.FGIlgiliId = d.DepoId AND fc.FGIlgiliTipi = 1
            WHERE fc.FGSilme = 0
            AND CAST(fc.FGFaturaTarihi as date) = '{safe_tarih}'
            {depo_filtre}
            ORDER BY fc.FGFaturaNo, u.UrunAdi
            """
            fc_results = self.sorgu_calistir(sql)
            if fc_results:
                results.extend(fc_results)

        # 3. IadeTakip'ten tarihe göre (FaturaCikis'te bulunamazsa)
        if not results and fatura_tarihi:
            safe_tarih = str(fatura_tarihi).replace("'", "''")
            depo_filtre = ""
            if depo_adi:
                safe_depo = str(depo_adi).replace("'", "''")
                depo_filtre = f"AND d.DepoAdi LIKE '%{safe_depo}%'"

            sql = f"""
            SELECT
                CAST(it.ITId as nvarchar(50)) as FaturaNo,
                CAST(it.ITKayitTarihi as date) as FaturaTarihi,
                COALESCE(d.DepoAdi, 'Depo') as DepoAdi,
                u.UrunAdi,
                u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                it.ITUrunAdet as Miktar,
                u.UrunFiyatEtiket as EtiketFiyat,
                it.ITBirimMaliyet as BirimFiyat,
                it.ITUrunAdet * it.ITBirimMaliyet as ToplamTutar,
                it.ITBirimMaliyet as Maliyet,
                u.UrunFiyatEtiket as GuncelEtiketFiyat,
                NULL as FaturaToplamTutar,
                'IADE_TAKIP' as Kaynak
            FROM IadeTakip it
            JOIN Urun u ON it.ITUrunId = u.UrunId
            LEFT JOIN Depo d ON it.ITDepoId = d.DepoId
            WHERE CAST(it.ITKayitTarihi as date) = '{safe_tarih}'
            {depo_filtre}
            ORDER BY u.UrunAdi
            """
            it_results = self.sorgu_calistir(sql)
            if it_results:
                results.extend(it_results)

        return results

    def depo_listesi_getir(self) -> List[Dict]:
        """Tüm depoları getir"""
        sql = """
        SELECT DepoId, DepoAdi
        FROM Depo
        WHERE DepoSilme = 0
        ORDER BY DepoAdi
        """
        return self.sorgu_calistir(sql)

    def hareket_ozeti_getir(self) -> Dict:
        """Hareket özetini getir"""
        sql = """
        SELECT
            (SELECT COUNT(*) FROM FaturaGiris WHERE FGSilme = 0) as FaturaGirisSayisi,
            (SELECT COUNT(*) FROM FaturaCikis WHERE FGSilme = 0) as FaturaCikisSayisi,
            (SELECT COUNT(*) FROM ReceteAna WHERE RxSilme = 0) as ReceteSayisi,
            (SELECT COUNT(*) FROM Takas WHERE TakasSilme = 0) as TakasSayisi,
            (SELECT COUNT(*) FROM IadeTakip) as IadeSayisi
        """
        results = self.sorgu_calistir(sql)
        return results[0] if results else {}

    def stok_analiz_getir(
        self,
        urun_tipi: Optional[str] = None,
        urun_adi: Optional[str] = None,
        sadece_stoklu: bool = True,
        limit: int = 5000
    ) -> List[Dict]:
        """
        Stok analiz raporu - Tüm ilaçların stok, sarf, miad analizi

        Döndürülen alanlar:
        - UrunId, UrunAdi, UrunTipi, Stok
        - Sarf3, Sarf6, Sarf12, Sarf24 (son X aydaki toplam satış)
        - OrtAy3, OrtAy6, OrtAy12, OrtAy24 (aylık ortalama satış)
        - EtiketFiyat, KamuFiyat, Maliyet
        - EnYakinMiad, MiadaKacGun
        - StokBitisGunu (6 aylık ortalamaya göre)
        - MiadaKacKezBiter (miad tarihine kadar kaç kez stok biter)
        """

        # Bugünün tarihi
        bugun = datetime.now().strftime('%Y-%m-%d')

        sql = f"""
        WITH SatisVerileri AS (
            -- Reçeteli satışlar (iade olmayanlar)
            SELECT
                ri.RIUrunId as UrunId,
                ri.RIAdet as Adet,
                CAST(ra.RxReceteTarihi as date) as Tarih
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND (ri.RIIade = 0 OR ri.RIIade IS NULL)

            UNION ALL

            -- Elden satışlar (iade olmayanlar)
            SELECT
                ei.RIUrunId as UrunId,
                ei.RIAdet as Adet,
                CAST(ea.RxReceteTarihi as date) as Tarih
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
        ),
        SarfOzet AS (
            SELECT
                UrunId,
                -- Son 3 ay
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -3, '{bugun}') THEN Adet ELSE 0 END) as Sarf3,
                -- Son 6 ay
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -6, '{bugun}') THEN Adet ELSE 0 END) as Sarf6,
                -- Son 12 ay
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -12, '{bugun}') THEN Adet ELSE 0 END) as Sarf12,
                -- Son 24 ay
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -24, '{bugun}') THEN Adet ELSE 0 END) as Sarf24
            FROM SatisVerileri
            WHERE Tarih >= DATEADD(MONTH, -24, '{bugun}')
            GROUP BY UrunId
        ),
        -- İlaçlar için Karekod tablosundan en yakın miad (XD alanından parse)
        IlacMiadlar AS (
            SELECT
                k.KKUrunId as UrunId,
                MIN(
                    CASE
                        WHEN LEN(k.XD) = 6 AND ISNUMERIC(k.XD) = 1
                        THEN DATEFROMPARTS(
                            2000 + CAST(LEFT(k.XD, 2) as int),
                            CAST(SUBSTRING(k.XD, 3, 2) as int),
                            CAST(RIGHT(k.XD, 2) as int)
                        )
                        ELSE NULL
                    END
                ) as Miad
            FROM Karekod k
            JOIN Urun u ON k.KKUrunId = u.UrunId
            WHERE k.KKDurum = 1
                AND k.XD IS NOT NULL
                AND LEN(k.XD) = 6
                AND u.UrunUrunTipId = 1  -- Sadece ilaçlar
            GROUP BY k.KKUrunId
            HAVING MIN(
                CASE
                    WHEN LEN(k.XD) = 6 AND ISNUMERIC(k.XD) = 1
                    THEN DATEFROMPARTS(
                        2000 + CAST(LEFT(k.XD, 2) as int),
                        CAST(SUBSTRING(k.XD, 3, 2) as int),
                        CAST(RIGHT(k.XD, 2) as int)
                    )
                    ELSE NULL
                END
            ) > '{bugun}'
        ),
        -- Diğer ürünler için MiadTakip tablosundan en yakın miad
        DigerMiadlar AS (
            SELECT
                MiadTakipUrunId as UrunId,
                MIN(MiadTakipMiad) as Miad
            FROM MiadTakip
            WHERE MiadTakipMiad > '{bugun}'
            GROUP BY MiadTakipUrunId
        ),
        -- Birleşik en yakın miad (ilaçlar + diğer ürünler)
        EnYakinMiad AS (
            SELECT UrunId, Miad FROM IlacMiadlar
            UNION ALL
            SELECT dm.UrunId, dm.Miad
            FROM DigerMiadlar dm
            JOIN Urun u ON dm.UrunId = u.UrunId
            WHERE ISNULL(u.UrunUrunTipId, 0) <> 1  -- İlaç olmayanlar (NULL dahil)
        ),
        -- FIFO Ağırlıklı Ortalama Maliyet Hesabı
        FaturaAlislar AS (
            -- Tüm alışlar, en yeniden eskiye, kümülatif toplam ile
            SELECT
                fs.FSUrunId as UrunId,
                fs.FSUrunAdet as Adet,
                fs.FSMaliyet as Maliyet,
                fg.FGFaturaTarihi as Tarih,
                SUM(fs.FSUrunAdet) OVER (
                    PARTITION BY fs.FSUrunId
                    ORDER BY fg.FGFaturaTarihi DESC, fg.FGId DESC
                    ROWS UNBOUNDED PRECEDING
                ) as KumulatifAdet
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0 AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
        ),
        UrunStoklar AS (
            SELECT UrunId, (UrunStokDepo + UrunStokRaf + UrunStokAcik) as Stok
            FROM Urun WHERE UrunSilme = 0
        ),
        FIFOMaliyet AS (
            -- Her ürün için stok miktarına kadar olan faturalardan ağırlıklı ortalama
            SELECT
                fa.UrunId,
                SUM(
                    CASE
                        -- Bu parti tamamen stoğun içinde
                        WHEN fa.KumulatifAdet <= us.Stok THEN fa.Adet * fa.Maliyet
                        -- Bu parti kısmen stoğun içinde (sınır parti)
                        WHEN fa.KumulatifAdet - fa.Adet < us.Stok
                            THEN (us.Stok - (fa.KumulatifAdet - fa.Adet)) * fa.Maliyet
                        -- Bu parti stoğun dışında
                        ELSE 0
                    END
                ) / NULLIF(us.Stok, 0) as Maliyet
            FROM FaturaAlislar fa
            JOIN UrunStoklar us ON fa.UrunId = us.UrunId
            WHERE us.Stok > 0 AND (fa.KumulatifAdet - fa.Adet) < us.Stok
            GROUP BY fa.UrunId, us.Stok
        )

        SELECT TOP {limit}
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,

            -- Sarflar
            COALESCE(s.Sarf3, 0) as Sarf3,
            COALESCE(s.Sarf6, 0) as Sarf6,
            COALESCE(s.Sarf12, 0) as Sarf12,
            COALESCE(s.Sarf24, 0) as Sarf24,

            -- Aylık ortalamalar
            ROUND(COALESCE(s.Sarf3, 0) / 3.0, 2) as OrtAy3,
            ROUND(COALESCE(s.Sarf6, 0) / 6.0, 2) as OrtAy6,
            ROUND(COALESCE(s.Sarf12, 0) / 12.0, 2) as OrtAy12,
            ROUND(COALESCE(s.Sarf24, 0) / 24.0, 2) as OrtAy24,

            -- Fiyatlar
            u.UrunFiyatEtiket as EtiketFiyat,
            u.UrunFiyatKamu as KamuFiyat,
            COALESCE(m.Maliyet, 0) as Maliyet,

            -- Miad bilgileri
            eym.Miad as EnYakinMiad,
            DATEDIFF(DAY, '{bugun}', eym.Miad) as MiadaKacGun,

            -- Stok bitiş hesaplamaları (6 aylık ortalamaya göre)
            CASE
                WHEN COALESCE(s.Sarf6, 0) > 0
                THEN ROUND((u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) / (s.Sarf6 / 6.0) * 30, 0)
                ELSE NULL
            END as StokBitisGunu,

            -- Miada kadar kaç kez biter
            CASE
                WHEN COALESCE(s.Sarf6, 0) > 0 AND eym.Miad IS NOT NULL
                THEN ROUND(
                    DATEDIFF(DAY, '{bugun}', eym.Miad) /
                    NULLIF((u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) / (s.Sarf6 / 6.0) * 30, 0)
                , 2)
                ELSE NULL
            END as MiadaKacKezBiter,

            -- Toplam maliyet (stok * maliyet)
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) * COALESCE(m.Maliyet, 0) as ToplamMaliyet

        FROM Urun u
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN SarfOzet s ON u.UrunId = s.UrunId
        LEFT JOIN EnYakinMiad eym ON u.UrunId = eym.UrunId
        LEFT JOIN FIFOMaliyet m ON u.UrunId = m.UrunId
        WHERE u.UrunSilme = 0
        """

        # Sadece stoklu ürünler
        if sadece_stoklu:
            sql += " AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0"

        # Ürün tipi filtresi
        if urun_tipi and urun_tipi != "TUMU":
            urun_tipi_temiz = urun_tipi.replace("'", "''")
            sql += f" AND ut.UrunTipAdi = '{urun_tipi_temiz}'"

        # Ürün adı filtresi
        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            sql += f" AND u.UrunAdi LIKE '%{urun_adi_temiz}%'"

        sql += " ORDER BY (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) DESC, u.UrunAdi"

        return self.sorgu_calistir(sql)

    def urun_tipleri_getir(self) -> List[Dict]:
        """Ürün tiplerini getir"""
        sql = """
        SELECT DISTINCT ut.UrunTipId, ut.UrunTipAdi
        FROM UrunTip ut
        JOIN Urun u ON u.UrunUrunTipId = ut.UrunTipId
        WHERE ut.UrunTipSilme = 0 AND u.UrunSilme = 0
        AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0
        ORDER BY ut.UrunTipAdi
        """
        return self.sorgu_calistir(sql)

    def ilac_parti_detay_getir(self, urun_id: int) -> List[Dict]:
        """
        Bir ilaç ürünü için karekod bazlı parti detaylarını getir.
        Her parti için miad ve adet bilgisi döner.
        XD formatı: YYMMDD (örn: 251210 = 10.12.2025)
        """
        sql = f"""
        SELECT
            XD as MiadKod,
            -- XD'yi tarihe çevir (YYMMDD -> date)
            CASE
                WHEN LEN(XD) = 6 AND ISNUMERIC(XD) = 1
                THEN DATEFROMPARTS(
                    2000 + CAST(LEFT(XD, 2) as int),
                    CAST(SUBSTRING(XD, 3, 2) as int),
                    CAST(RIGHT(XD, 2) as int)
                )
                ELSE NULL
            END as Miad,
            COUNT(*) as Adet
        FROM Karekod
        WHERE KKUrunId = {urun_id}
        AND KKDurum = 1
        AND XD IS NOT NULL
        AND LEN(XD) = 6
        GROUP BY XD
        ORDER BY XD
        """
        return self.sorgu_calistir(sql)

    def stok_analiz_parti_getir(
        self,
        urun_tipi: Optional[str] = None,
        urun_adi: Optional[str] = None,
        sadece_stoklu: bool = True,
        limit: int = 5000
    ) -> List[Dict]:
        """
        Stok analiz raporu - İlaç ürünleri parti bazlı (karekod miadlarına göre)
        İlaç tipindeki ürünler karekod bazlı partilere ayrılır.
        Diğer ürün tipleri normal şekilde döner.
        """
        bugun = datetime.now().strftime('%Y-%m-%d')

        # Ürün adı filtresi
        urun_adi_filtre = ""
        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            urun_adi_filtre = f"AND u.UrunAdi LIKE '%{urun_adi_temiz}%'"

        # Ürün tipi filtresi
        urun_tipi_filtre = ""
        if urun_tipi and urun_tipi != "TUMU":
            urun_tipi_temiz = urun_tipi.replace("'", "''")
            urun_tipi_filtre = f"AND ut.UrunTipAdi = '{urun_tipi_temiz}'"

        sql = f"""
        ;WITH SatisVerileri AS (
            -- Reçeteli satışlar (iade olmayanlar)
            SELECT
                ri.RIUrunId as UrunId,
                ri.RIAdet as Adet,
                CAST(ra.RxReceteTarihi as date) as Tarih
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND (ri.RIIade = 0 OR ri.RIIade IS NULL)

            UNION ALL

            -- Elden satışlar (iade olmayanlar)
            SELECT
                ei.RIUrunId as UrunId,
                ei.RIAdet as Adet,
                CAST(ea.RxReceteTarihi as date) as Tarih
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
        ),
        SarfOzet AS (
            SELECT
                UrunId,
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -3, '{bugun}') THEN Adet ELSE 0 END) as Sarf3,
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -6, '{bugun}') THEN Adet ELSE 0 END) as Sarf6,
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -12, '{bugun}') THEN Adet ELSE 0 END) as Sarf12,
                SUM(CASE WHEN Tarih >= DATEADD(MONTH, -24, '{bugun}') THEN Adet ELSE 0 END) as Sarf24
            FROM SatisVerileri
            WHERE Tarih >= DATEADD(MONTH, -24, '{bugun}')
            GROUP BY UrunId
        ),
        FaturaAlislar AS (
            SELECT
                fs.FSUrunId as UrunId,
                fs.FSUrunAdet as Adet,
                fs.FSMaliyet as Maliyet,
                fg.FGFaturaTarihi as Tarih,
                SUM(fs.FSUrunAdet) OVER (
                    PARTITION BY fs.FSUrunId
                    ORDER BY fg.FGFaturaTarihi DESC, fg.FGId DESC
                    ROWS UNBOUNDED PRECEDING
                ) as KumulatifAdet
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0 AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
        ),
        UrunStoklar AS (
            SELECT UrunId, (UrunStokDepo + UrunStokRaf + UrunStokAcik) as Stok
            FROM Urun WHERE UrunSilme = 0
        ),
        FIFOMaliyet AS (
            SELECT
                fa.UrunId,
                SUM(
                    CASE
                        WHEN fa.KumulatifAdet <= us.Stok THEN fa.Adet * fa.Maliyet
                        WHEN fa.KumulatifAdet - fa.Adet < us.Stok
                            THEN (us.Stok - (fa.KumulatifAdet - fa.Adet)) * fa.Maliyet
                        ELSE 0
                    END
                ) / NULLIF(us.Stok, 0) as Maliyet
            FROM FaturaAlislar fa
            JOIN UrunStoklar us ON fa.UrunId = us.UrunId
            WHERE us.Stok > 0 AND (fa.KumulatifAdet - fa.Adet) < us.Stok
            GROUP BY fa.UrunId, us.Stok
        ),
        IlacPartiler AS (
            SELECT
                k.KKUrunId as UrunId,
                k.XD as MiadKod,
                CASE
                    WHEN LEN(k.XD) = 6 AND ISNUMERIC(k.XD) = 1
                    THEN DATEFROMPARTS(
                        2000 + CAST(LEFT(k.XD, 2) as int),
                        CAST(SUBSTRING(k.XD, 3, 2) as int),
                        CAST(RIGHT(k.XD, 2) as int)
                    )
                    ELSE NULL
                END as PartiMiad,
                COUNT(*) as PartiAdet,
                ROW_NUMBER() OVER (PARTITION BY k.KKUrunId ORDER BY k.XD) as PartiSira,
                SUM(COUNT(*)) OVER (PARTITION BY k.KKUrunId ORDER BY k.XD ROWS UNBOUNDED PRECEDING) as KumulatifAdet
            FROM Karekod k
            JOIN Urun u ON k.KKUrunId = u.UrunId
            WHERE k.KKDurum = 1
            AND k.XD IS NOT NULL
            AND LEN(k.XD) = 6
            AND u.UrunUrunTipId = 1
            GROUP BY k.KKUrunId, k.XD
        )

        SELECT TOP {limit}
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            ip.PartiAdet as Stok,
            ip.PartiSira as PartiNo,
            ip.PartiMiad as EnYakinMiad,
            DATEDIFF(DAY, '{bugun}', ip.PartiMiad) as MiadaKacGun,
            ip.KumulatifAdet - ip.PartiAdet as OncekiPartilerToplam,
            COALESCE(s.Sarf3, 0) as Sarf3,
            COALESCE(s.Sarf6, 0) as Sarf6,
            COALESCE(s.Sarf12, 0) as Sarf12,
            COALESCE(s.Sarf24, 0) as Sarf24,
            ROUND(COALESCE(s.Sarf3, 0) / 3.0, 2) as OrtAy3,
            ROUND(COALESCE(s.Sarf6, 0) / 6.0, 2) as OrtAy6,
            ROUND(COALESCE(s.Sarf12, 0) / 12.0, 2) as OrtAy12,
            ROUND(COALESCE(s.Sarf24, 0) / 24.0, 2) as OrtAy24,
            u.UrunFiyatEtiket as EtiketFiyat,
            u.UrunFiyatKamu as KamuFiyat,
            COALESCE(m.Maliyet, 0) as Maliyet,
            ip.PartiAdet * COALESCE(m.Maliyet, 0) as ToplamMaliyet,
            1 as IsParti
        FROM IlacPartiler ip
        JOIN Urun u ON ip.UrunId = u.UrunId
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN SarfOzet s ON u.UrunId = s.UrunId
        LEFT JOIN FIFOMaliyet m ON u.UrunId = m.UrunId
        WHERE u.UrunSilme = 0 AND ip.PartiMiad IS NOT NULL AND ip.PartiAdet > 0
        {urun_adi_filtre} {urun_tipi_filtre}

        UNION ALL

        SELECT TOP {limit}
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            NULL as PartiNo,
            (SELECT MIN(MiadTakipMiad) FROM MiadTakip WHERE MiadTakipUrunId = u.UrunId AND MiadTakipMiad > '{bugun}') as EnYakinMiad,
            DATEDIFF(DAY, '{bugun}', (SELECT MIN(MiadTakipMiad) FROM MiadTakip WHERE MiadTakipUrunId = u.UrunId AND MiadTakipMiad > '{bugun}')) as MiadaKacGun,
            0 as OncekiPartilerToplam,
            COALESCE(s.Sarf3, 0) as Sarf3,
            COALESCE(s.Sarf6, 0) as Sarf6,
            COALESCE(s.Sarf12, 0) as Sarf12,
            COALESCE(s.Sarf24, 0) as Sarf24,
            ROUND(COALESCE(s.Sarf3, 0) / 3.0, 2) as OrtAy3,
            ROUND(COALESCE(s.Sarf6, 0) / 6.0, 2) as OrtAy6,
            ROUND(COALESCE(s.Sarf12, 0) / 12.0, 2) as OrtAy12,
            ROUND(COALESCE(s.Sarf24, 0) / 24.0, 2) as OrtAy24,
            u.UrunFiyatEtiket as EtiketFiyat,
            u.UrunFiyatKamu as KamuFiyat,
            COALESCE(m.Maliyet, 0) as Maliyet,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) * COALESCE(m.Maliyet, 0) as ToplamMaliyet,
            0 as IsParti
        FROM Urun u
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN SarfOzet s ON u.UrunId = s.UrunId
        LEFT JOIN FIFOMaliyet m ON u.UrunId = m.UrunId
        WHERE u.UrunSilme = 0 AND ISNULL(u.UrunUrunTipId, 0) != 1
        AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0
        {urun_adi_filtre} {urun_tipi_filtre}

        ORDER BY UrunAdi, PartiNo
        """

        return self.sorgu_calistir(sql)


    def alis_analiz_getir(
        self,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        ortalama_ay: int = 6,
        depo_id: Optional[int] = None,
        urun_adi: Optional[str] = None,
        urun_tipleri: Optional[List[str]] = None,
        limit: int = 5000
    ) -> List[Dict]:
        """
        Alış Analiz Raporu - Fatura bazlı alış analizi

        Her alış faturası satırı için:
        - Fatura bilgileri (tarih, no, depo, ürün, adet, mf, birim fiyat, miad)
        - Fatura öncesi stok (o tarihe kadar alışlar - satışlar)
        - Fatura öncesi dönemden aylık ortalama satış
        - Fatura öncesi stok kaç aylık
        - Alınan miktar kaç aylık

        Args:
            baslangic_tarih: Fatura tarih filtresi başlangıç
            bitis_tarih: Fatura tarih filtresi bitiş
            ortalama_ay: Ortalama hesabı için fatura öncesi kaç ay
            depo_id: Depo filtresi (opsiyonel)
            urun_adi: Ürün adı filtresi (opsiyonel)
            limit: Maksimum kayıt sayısı
        """

        # Tarih filtreleri
        tarih_filtre = ""
        if baslangic_tarih:
            tarih_filtre += f" AND fg.FGFaturaTarihi >= '{baslangic_tarih.strftime('%Y-%m-%d')}'"
        if bitis_tarih:
            tarih_filtre += f" AND fg.FGFaturaTarihi <= '{bitis_tarih.strftime('%Y-%m-%d')}'"

        # Depo filtresi
        depo_filtre = ""
        if depo_id:
            depo_filtre = f" AND fg.FGIlgiliId = {depo_id}"

        # Ürün adı filtresi
        urun_filtre = ""
        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            urun_filtre = f" AND u.UrunAdi LIKE '%{urun_adi_temiz}%'"

        # Ürün tipi filtresi (çoklu seçim — IN listesi)
        urun_tipi_filtre = ""
        if urun_tipleri:
            tip_temiz = [t.replace("'", "''") for t in urun_tipleri if t]
            if tip_temiz:
                tip_listesi = ",".join([f"'{t}'" for t in tip_temiz])
                urun_tipi_filtre = f" AND ut.UrunTipAdi IN ({tip_listesi})"

        sql = f"""
        ;WITH
        -- Fatura sonrası girişler (MF DAHİL) - geriye doğru hesaplama için
        FaturaSonrasiGirisler AS (
            SELECT
                fsi.FSUrunId as UrunId,
                fgi.FGFaturaTarihi as FaturaTarihi,
                SUM(fsi.FSUrunAdet + COALESCE(fsi.FSUrunMf, 0)) as ToplamGiris
            FROM FaturaSatir fsi
            JOIN FaturaGiris fgi ON fsi.FSFGId = fgi.FGId
            WHERE fgi.FGSilme = 0
            GROUP BY fsi.FSUrunId, fgi.FGFaturaTarihi
        ),
        -- Fatura sonrası takas girişleri
        TakasSonrasiGirisler AS (
            SELECT
                ts.TSUrunId as UrunId,
                CAST(t.TakasTarihi as date) as TakasTarihi,
                SUM(ts.TSUrunAdedi) as ToplamGiris
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
            GROUP BY ts.TSUrunId, CAST(t.TakasTarihi as date)
        ),
        -- Perakende satışlar (Reçeteli + Elden) - AYLIK ORTALAMA İÇİN
        PerakendeSatislar AS (
            -- Reçeteli satışlar
            SELECT
                ri.RIUrunId as UrunId,
                CAST(ra.RxReceteTarihi as date) as Tarih,
                SUM(ri.RIAdet) as GunlukSatis
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            GROUP BY ri.RIUrunId, CAST(ra.RxReceteTarihi as date)

            UNION ALL

            -- Elden satışlar
            SELECT
                ei.RIUrunId as UrunId,
                CAST(ea.RxReceteTarihi as date) as Tarih,
                SUM(ei.RIAdet) as GunlukSatis
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            GROUP BY ei.RIUrunId, CAST(ea.RxReceteTarihi as date)
        ),
        PerakendeSatisOzet AS (
            SELECT
                UrunId,
                Tarih,
                SUM(GunlukSatis) as GunlukSatis
            FROM PerakendeSatislar
            GROUP BY UrunId, Tarih
        ),
        -- GÜNCEL aylık ortalama: bugünden geriye X ay, UrunId başına TEK SEFER (per-row scan yerine CTE)
        GuncelAylikOrt AS (
            SELECT
                UrunId,
                ROUND(SUM(GunlukSatis) / {ortalama_ay}.0, 2) as Ort
            FROM PerakendeSatisOzet
            WHERE Tarih >= DATEADD(MONTH, -{ortalama_ay}, CAST(GETDATE() as date))
              AND Tarih <  CAST(GETDATE() as date)
            GROUP BY UrunId
        ),
        -- Tüm çıkışlar (Reçeteli + Elden + Takas) - STOK HESABI İÇİN
        TumCikislar AS (
            -- Perakende satışlar
            SELECT UrunId, Tarih, GunlukSatis
            FROM PerakendeSatislar

            UNION ALL

            -- Takas çıkışlar
            SELECT
                ts.TSUrunId as UrunId,
                CAST(t.TakasTarihi as date) as Tarih,
                SUM(ts.TSUrunAdedi) as GunlukSatis
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 0
            GROUP BY ts.TSUrunId, CAST(t.TakasTarihi as date)
        ),
        TumCikisOzet AS (
            SELECT
                UrunId,
                Tarih,
                SUM(GunlukSatis) as GunlukSatis
            FROM TumCikislar
            GROUP BY UrunId, Tarih
        )

        SELECT TOP {limit}
            fg.FGFaturaNo as FaturaNo,
            fg.FGFaturaTarihi as Tarih,
            d.DepoAdi as Depo,
            u.UrunId,
            u.UrunAdi,
            fs.FSUrunAdet as Adet,
            fs.FSUrunMf as MF,
            fs.FSBirimFiyat as BirimFiyat,
            fs.FSMaliyet as Maliyet,
            fs.FSUrunAdet * COALESCE(fs.FSMaliyet, fs.FSBirimFiyat) as ToplamTutar,
            fg.FGVadeTarihi as FaturaVade,
            DAY(fg.FGFaturaTarihi) as AyGunu,
            DATEDIFF(DAY, fg.FGFaturaTarihi, EOMONTH(fg.FGFaturaTarihi)) + 1 as KalanGun,

            -- Güncel stok (Urun tablosundan - sadece StokRaf)
            u.UrunStokRaf as GuncelStok,

            -- Fatura günü ve sonrası girişler (MF dahil) - aynı gün DAHİL
            COALESCE((
                SELECT SUM(fsg.ToplamGiris)
                FROM FaturaSonrasiGirisler fsg
                WHERE fsg.UrunId = fs.FSUrunId
                AND CAST(fsg.FaturaTarihi as DATE) >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0) as FaturaGunuVeSonrasiGiris,

            -- Fatura günü ve sonrası takas girişleri
            COALESCE((
                SELECT SUM(tsg.ToplamGiris)
                FROM TakasSonrasiGirisler tsg
                WHERE tsg.UrunId = fs.FSUrunId
                AND tsg.TakasTarihi >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0) as FaturaGunuVeSonrasiTakasGiris,

            -- Fatura günü ve sonrası çıkışlar - aynı gün DAHİL (takas dahil)
            COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM TumCikisOzet s
                WHERE s.UrunId = fs.FSUrunId
                AND s.Tarih >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0) as FaturaGunuVeSonrasiCikis,

            -- FATURA ÖNCESİ STOK = GüncelStok - (Gün+SonrasıGirişler) + (Gün+SonrasıÇıkışlar)
            -- (Geriye doğru hesaplama - fatura günü başındaki stok, sadece StokRaf)
            u.UrunStokRaf
            - COALESCE((
                SELECT SUM(fsg.ToplamGiris)
                FROM FaturaSonrasiGirisler fsg
                WHERE fsg.UrunId = fs.FSUrunId
                AND CAST(fsg.FaturaTarihi as DATE) >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0)
            - COALESCE((
                SELECT SUM(tsg.ToplamGiris)
                FROM TakasSonrasiGirisler tsg
                WHERE tsg.UrunId = fs.FSUrunId
                AND tsg.TakasTarihi >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0)
            + COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM TumCikisOzet s
                WHERE s.UrunId = fs.FSUrunId
                AND s.Tarih >= CAST(fg.FGFaturaTarihi as DATE)
            ), 0) as FaturaOncesiStok,

            -- Fatura öncesi X ay içindeki PERAKENDE satışlar (aylık ortalama için - takas HARİÇ)
            COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM PerakendeSatisOzet s
                WHERE s.UrunId = fs.FSUrunId
                AND s.Tarih >= DATEADD(MONTH, -{ortalama_ay}, fg.FGFaturaTarihi)
                AND s.Tarih < fg.FGFaturaTarihi
            ), 0) as OncekiDonemSatis,

            -- Aylık ortalama PERAKENDE satış (fatura öncesi X ay - takas HARİÇ)
            ROUND(
                COALESCE((
                    SELECT SUM(s.GunlukSatis)
                    FROM PerakendeSatisOzet s
                    WHERE s.UrunId = fs.FSUrunId
                    AND s.Tarih >= DATEADD(MONTH, -{ortalama_ay}, fg.FGFaturaTarihi)
                    AND s.Tarih < fg.FGFaturaTarihi
                ), 0) / {ortalama_ay}.0
            , 2) as AylikOrtalama,

            -- GÜNCEL aylık ortalama (CTE'den JOIN — UrunId başına tek hesap)
            COALESCE(gao.Ort, 0) as GuncelAylikOrtalama,

            -- Ürün tipi (İlaç / Medikal / İtriyat ...)
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,

            -- Parametre olarak kullanılan ay sayısı
            {ortalama_ay} as OrtalamaAy

        FROM FaturaGiris fg
        JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
        JOIN Urun u ON fs.FSUrunId = u.UrunId
        LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId AND fg.FGIlgiliTipi = 1
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN GuncelAylikOrt gao ON gao.UrunId = fs.FSUrunId
        WHERE fg.FGSilme = 0 AND fs.FSUrunAdet > 0
        {tarih_filtre}
        {depo_filtre}
        {urun_filtre}
        {urun_tipi_filtre}

        ORDER BY fg.FGFaturaTarihi DESC, fg.FGId DESC, u.UrunAdi
        """

        return self.sorgu_calistir(sql)

    def stok_hareket_analiz_getir(
        self,
        yil_sayisi: int = 2,
        ay_sayisi: int = 6,
        hareket_tipleri: List[str] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """
        Stok Hareket Analiz Raporu - Son X yılda hareketi olan ürünler

        Args:
            yil_sayisi: Son kaç yıldaki hareketler (varsayılan 2)
            ay_sayisi: Aylık detay için kaç ay gösterilecek (varsayılan 6)
            hareket_tipleri: Seçili hareket tipleri listesi
            limit: Maksimum kayıt sayısı

        Returns:
            Her ürün için: UrunId, UrunAdi, UrunTipi, EsdegerId, Stok,
            ve seçili hareket tiplerine göre aylık toplamlar
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        bugun = datetime.now()
        baslangic_tarih = (bugun - relativedelta(years=yil_sayisi)).strftime('%Y-%m-%d')
        bugun_str = bugun.strftime('%Y-%m-%d')

        # Varsayılan hareket tipleri
        if hareket_tipleri is None:
            hareket_tipleri = ['RECETE_SATIS', 'ELDEN_SATIS']

        # Hareket tiplerini kategorize et
        giris_tipleri = []
        cikis_tipleri = []

        hareket_yon_map = {
            'FATURA_GIRIS': 'GIRIS',
            'TAKAS_GIRIS': 'GIRIS',
            'FATURA_CIKIS': 'CIKIS',
            'TAKAS_CIKIS': 'CIKIS',
            'IADE': 'CIKIS',
            'RECETE_SATIS': 'CIKIS',
            'ELDEN_SATIS': 'CIKIS'
        }

        for ht in hareket_tipleri:
            if hareket_yon_map.get(ht) == 'GIRIS':
                giris_tipleri.append(ht)
            else:
                cikis_tipleri.append(ht)

        # Aylık kolonlar için tarih aralıkları oluştur
        ay_kolonlari = []
        for i in range(ay_sayisi):
            ay_basi = (bugun - relativedelta(months=i)).replace(day=1)
            if i == 0:
                ay_sonu = bugun
            else:
                ay_sonu = (ay_basi + relativedelta(months=1)) - relativedelta(days=1)
            ay_kolonlari.append({
                'ay_no': i + 1,
                'ay_adi': ay_basi.strftime('%Y-%m'),
                'baslangic': ay_basi.strftime('%Y-%m-%d'),
                'bitis': ay_sonu.strftime('%Y-%m-%d')
            })

        # SQL sorgusu oluştur
        # Her hareket tipi için ayrı UNION bloğu
        hareket_bloklari = []

        if 'FATURA_GIRIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                fs.FSUrunId as UrunId,
                fs.FSUrunAdet as Adet,
                CAST(fg.FGFaturaTarihi as date) as Tarih,
                'FATURA_GIRIS' as HareketTipi,
                'GIRIS' as Yon
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0 AND fg.FGFaturaTarihi >= '{baslangic_tarih}'
            """)

        if 'FATURA_CIKIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                fcs.FSUrunId as UrunId,
                fcs.FSUrunAdet as Adet,
                CAST(fc.FGFaturaTarihi as date) as Tarih,
                'FATURA_CIKIS' as HareketTipi,
                'CIKIS' as Yon
            FROM FaturaCikisSatir fcs
            JOIN FaturaCikis fc ON fcs.FSFGId = fc.FGId
            WHERE fc.FGSilme = 0 AND fc.FGFaturaTarihi >= '{baslangic_tarih}'
            """)

        if 'TAKAS_GIRIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                ts.TSUrunId as UrunId,
                ts.TSUrunAdedi as Adet,
                CAST(t.TakasTarihi as date) as Tarih,
                'TAKAS_GIRIS' as HareketTipi,
                'GIRIS' as Yon
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
            AND t.TakasTarihi >= '{baslangic_tarih}'
            """)

        if 'TAKAS_CIKIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                ts.TSUrunId as UrunId,
                ts.TSUrunAdedi as Adet,
                CAST(t.TakasTarihi as date) as Tarih,
                'TAKAS_CIKIS' as HareketTipi,
                'CIKIS' as Yon
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 0
            AND t.TakasTarihi >= '{baslangic_tarih}'
            """)

        if 'IADE' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                it.ITUrunId as UrunId,
                it.ITUrunAdet as Adet,
                CAST(it.ITKayitTarihi as date) as Tarih,
                'IADE' as HareketTipi,
                'CIKIS' as Yon
            FROM IadeTakip it
            WHERE it.ITKayitTarihi >= '{baslangic_tarih}'
            """)

        if 'RECETE_SATIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                ri.RIUrunId as UrunId,
                ri.RIAdet as Adet,
                CAST(ra.RxReceteTarihi as date) as Tarih,
                'RECETE_SATIS' as HareketTipi,
                'CIKIS' as Yon
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
              AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
              AND ra.RxReceteTarihi >= '{baslangic_tarih}'
            """)

        if 'ELDEN_SATIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT
                ei.RIUrunId as UrunId,
                ei.RIAdet as Adet,
                CAST(ea.RxReceteTarihi as date) as Tarih,
                'ELDEN_SATIS' as HareketTipi,
                'CIKIS' as Yon
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
              AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
              AND ea.RxReceteTarihi >= '{baslangic_tarih}'
            """)

        if not hareket_bloklari:
            return []

        hareket_union = " UNION ALL ".join(hareket_bloklari)

        # Aylık toplamlar için CASE ifadeleri
        aylik_giris_cases = []
        aylik_cikis_cases = []

        for ay in ay_kolonlari:
            aylik_giris_cases.append(f"""
                SUM(CASE WHEN Yon = 'GIRIS' AND Tarih >= '{ay['baslangic']}' AND Tarih <= '{ay['bitis']}' THEN Adet ELSE 0 END) as Giris_Ay{ay['ay_no']}
            """)
            aylik_cikis_cases.append(f"""
                SUM(CASE WHEN Yon = 'CIKIS' AND Tarih >= '{ay['baslangic']}' AND Tarih <= '{ay['bitis']}' THEN Adet ELSE 0 END) as Cikis_Ay{ay['ay_no']}
            """)

        aylik_kolonlar = ",\n".join(aylik_giris_cases + aylik_cikis_cases)

        sql = f"""
        ;WITH TumHareketler AS (
            {hareket_union}
        ),
        UrunHareketOzet AS (
            SELECT
                UrunId,
                Yon,
                SUM(Adet) as ToplamAdet,
                COUNT(*) as ToplamIslem,
                {aylik_kolonlar}
            FROM TumHareketler
            GROUP BY UrunId, Yon
        )

        SELECT TOP {limit}
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            u.UrunEsdegerId as EsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            ho.Yon,
            ho.ToplamAdet,
            ho.ToplamIslem,
            {', '.join([f'COALESCE(ho.Giris_Ay{i+1}, 0) as Giris_Ay{i+1}' for i in range(ay_sayisi)])},
            {', '.join([f'COALESCE(ho.Cikis_Ay{i+1}, 0) as Cikis_Ay{i+1}' for i in range(ay_sayisi)])}
        FROM Urun u
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        JOIN UrunHareketOzet ho ON u.UrunId = ho.UrunId
        WHERE u.UrunSilme = 0
        ORDER BY u.UrunEsdegerId, u.UrunAdi, ho.Yon DESC
        """

        return self.sorgu_calistir(sql)

    def stok_hareket_urunler_getir(
        self,
        yil_sayisi: int = 2,
        hareket_tipleri: List[str] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """
        Son X yılda hareketi olan ürünlerin listesini getir
        Basit özet: UrunId, UrunAdi, UrunTipi, EsdegerId, Stok
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        bugun = datetime.now()
        baslangic_tarih = (bugun - relativedelta(years=yil_sayisi)).strftime('%Y-%m-%d')

        if hareket_tipleri is None:
            hareket_tipleri = ['RECETE_SATIS', 'ELDEN_SATIS']

        # Hareket sorguları
        hareket_bloklari = []

        if 'FATURA_GIRIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT fs.FSUrunId as UrunId
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0 AND fg.FGFaturaTarihi >= '{baslangic_tarih}'
            """)

        if 'FATURA_CIKIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT fcs.FSUrunId as UrunId
            FROM FaturaCikisSatir fcs
            JOIN FaturaCikis fc ON fcs.FSFGId = fc.FGId
            WHERE fc.FGSilme = 0 AND fc.FGFaturaTarihi >= '{baslangic_tarih}'
            """)

        if 'TAKAS_GIRIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT ts.TSUrunId as UrunId
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
            AND t.TakasTarihi >= '{baslangic_tarih}'
            """)

        if 'TAKAS_CIKIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT ts.TSUrunId as UrunId
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 0
            AND t.TakasTarihi >= '{baslangic_tarih}'
            """)

        if 'IADE' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT it.ITUrunId as UrunId
            FROM IadeTakip it
            WHERE it.ITKayitTarihi >= '{baslangic_tarih}'
            """)

        if 'RECETE_SATIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT ri.RIUrunId as UrunId
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
              AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
              AND ra.RxReceteTarihi >= '{baslangic_tarih}'
            """)

        if 'ELDEN_SATIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT ei.RIUrunId as UrunId
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
              AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
              AND ea.RxReceteTarihi >= '{baslangic_tarih}'
            """)

        if not hareket_bloklari:
            return []

        hareket_union = " UNION ".join(hareket_bloklari)

        sql = f"""
        ;WITH HareketliUrunler AS (
            {hareket_union}
        )
        SELECT TOP {limit}
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            u.UrunEsdegerId as EsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok
        FROM Urun u
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        WHERE u.UrunId IN (SELECT UrunId FROM HareketliUrunler)
        AND u.UrunSilme = 0
        ORDER BY u.UrunEsdegerId, u.UrunAdi
        """

        return self.sorgu_calistir(sql)

    # =====================================================
    # MF ANALİZ MODÜLÜ İÇİN SORGULAR
    # =====================================================

    def mf_ilac_listesi_getir(self, yil_sayisi: int = 5, sadece_stoklu: bool = False) -> List[Dict]:
        """
        MF Analiz için ilaç listesi getir
        Son X yılda hareketi olan ilaçlar

        Args:
            yil_sayisi: Son kaç yılda hareketi olan ilaçlar
            sadece_stoklu: Sadece stokta olanlar

        Returns:
            List[Dict]: UrunId, UrunAdi, UrunEsdegerId, Stok, PSF, KamuFiyat
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        baslangic = (datetime.now() - relativedelta(years=yil_sayisi)).strftime('%Y-%m-%d')

        stok_filtre = ""
        if sadece_stoklu:
            stok_filtre = "AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0"

        sql = f"""
        ;WITH HareketliUrunler AS (
            -- Reçeteli satış
            SELECT DISTINCT ri.RIUrunId as UrunId
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND ra.RxReceteTarihi >= '{baslangic}'

            UNION

            -- Elden satış
            SELECT DISTINCT ei.RIUrunId as UrunId
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND ea.RxReceteTarihi >= '{baslangic}'

            UNION

            -- Fatura girişi
            SELECT DISTINCT fs.FSUrunId as UrunId
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0
            AND fg.FGFaturaTarihi >= '{baslangic}'
        )
        SELECT
            u.UrunId,
            u.UrunAdi,
            u.UrunEsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            u.UrunFiyatEtiket as PSF,
            u.UrunFiyatKamu as KamuFiyat
        FROM Urun u
        WHERE u.UrunId IN (SELECT UrunId FROM HareketliUrunler)
        AND u.UrunSilme = 0
        AND u.UrunUrunTipId = 1  -- Sadece ilaçlar
        {stok_filtre}
        ORDER BY u.UrunAdi
        """
        return self.sorgu_calistir(sql)

    def mf_etken_madde_listesi_getir(self) -> List[Dict]:
        """
        MF Analiz için etken madde listesi getir
        Sadece stokta ilaç olan etken maddeler

        Returns:
            List[Dict]: EMLId, EMLAdi, IlacSayisi
        """
        sql = """
        SELECT
            em.EMLId,
            em.EMLAdi,
            COUNT(DISTINCT uem.UEMUrunId) as IlacSayisi
        FROM EtkenMaddeListesi em
        JOIN UrunEtkMad uem ON em.EMLId = uem.UEMEMLId
        JOIN Urun u ON uem.UEMUrunId = u.UrunId
        WHERE u.UrunSilme = 0
        AND u.UrunUrunTipId = 1
        AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0
        GROUP BY em.EMLId, em.EMLAdi
        HAVING COUNT(DISTINCT uem.UEMUrunId) > 0
        ORDER BY em.EMLAdi
        """
        return self.sorgu_calistir(sql)

    def mf_esdeger_kod_listesi_getir(self) -> List[Dict]:
        """
        MF Analiz için eşdeğer kod listesi getir
        Sadece stokta birden fazla ilaç olan gruplar

        Returns:
            List[Dict]: EsdegerId, IlacSayisi, OrnekIlac
        """
        sql = """
        SELECT
            u.UrunEsdegerId as EsdegerId,
            COUNT(*) as IlacSayisi,
            MIN(u.UrunAdi) as OrnekIlac
        FROM Urun u
        WHERE u.UrunSilme = 0
        AND u.UrunUrunTipId = 1
        AND u.UrunEsdegerId > 0
        AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0
        GROUP BY u.UrunEsdegerId
        ORDER BY MIN(u.UrunAdi)
        """
        return self.sorgu_calistir(sql)

    def mf_etken_maddeli_ilaclar_getir(self, etken_madde_id: int) -> List[Dict]:
        """
        Belirli etken maddeyi içeren ilaçları getir

        Args:
            etken_madde_id: EtkenMaddeListesi.EMLId

        Returns:
            List[Dict]: UrunId, UrunAdi, UrunEsdegerId, Stok, PSF, KamuFiyat
        """
        sql = f"""
        SELECT DISTINCT
            u.UrunId,
            u.UrunAdi,
            u.UrunEsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            u.UrunFiyatEtiket as PSF,
            u.UrunFiyatKamu as KamuFiyat
        FROM Urun u
        JOIN UrunEtkMad uem ON u.UrunId = uem.UEMUrunId
        WHERE uem.UEMEMLId = {etken_madde_id}
        AND u.UrunSilme = 0
        AND u.UrunUrunTipId = 1
        ORDER BY u.UrunAdi
        """
        return self.sorgu_calistir(sql)

    def etkin_madde_getir_ilac_adiyla(self, urun_adi: str) -> List[str]:
        """
        İlaç adına göre etkin madde(ler)ini getirir.
        Örnek: "VENTOLIN INHALER" → ["SALBUTAMOL"]

        Args:
            urun_adi: İlaç adı (kısmi eşleşme yapılır)

        Returns:
            List[str]: Etkin madde adları listesi
        """
        # SQL injection koruması - tek tırnak escape
        safe_adi = urun_adi.replace("'", "''")
        sql = f"""
        SELECT DISTINCT em.EMLAdi
        FROM EtkenMaddeListesi em
        JOIN UrunEtkMad uem ON em.EMLId = uem.UEMEMLId
        JOIN Urun u ON uem.UEMUrunId = u.UrunId
        WHERE u.UrunAdi LIKE '%{safe_adi}%'
        AND u.UrunSilme = 0
        ORDER BY em.EMLAdi
        """
        sonuclar = self.sorgu_calistir(sql)
        if sonuclar:
            return [s['EMLAdi'] for s in sonuclar]
        return []

    def etkin_madde_getir_barkod_ile(self, barkod: str) -> List[str]:
        """
        Barkod numarasına göre etkin madde(ler)ini getirir.

        Args:
            barkod: İlaç barkodu

        Returns:
            List[str]: Etkin madde adları listesi
        """
        safe_barkod = barkod.replace("'", "''")
        sql = f"""
        SELECT DISTINCT em.EMLAdi
        FROM EtkenMaddeListesi em
        JOIN UrunEtkMad uem ON em.EMLId = uem.UEMEMLId
        JOIN Urun u ON uem.UEMUrunId = u.UrunId
        LEFT JOIN UrunBarkod ub ON u.UrunId = ub.UBUrunId
        WHERE (ub.UBBarkod = '{safe_barkod}' OR u.UrunBarkod = '{safe_barkod}')
        AND u.UrunSilme = 0
        ORDER BY em.EMLAdi
        """
        sonuclar = self.sorgu_calistir(sql)
        if sonuclar:
            return [s['EMLAdi'] for s in sonuclar]
        return []

    def mf_esdeger_kodlu_ilaclar_getir(self, esdeger_id: int) -> List[Dict]:
        """
        Belirli eşdeğer koda sahip ilaçları getir

        Args:
            esdeger_id: Urun.UrunEsdegerId

        Returns:
            List[Dict]: UrunId, UrunAdi, UrunEsdegerId, Stok, PSF, KamuFiyat
        """
        sql = f"""
        SELECT
            u.UrunId,
            u.UrunAdi,
            u.UrunEsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            u.UrunFiyatEtiket as PSF,
            u.UrunFiyatKamu as KamuFiyat
        FROM Urun u
        WHERE u.UrunEsdegerId = {esdeger_id}
        AND u.UrunSilme = 0
        AND u.UrunUrunTipId = 1
        ORDER BY u.UrunAdi
        """
        return self.sorgu_calistir(sql)

    def mf_ilac_fiyat_detay_getir(self, urun_id: int) -> Optional[Dict]:
        """
        İlaç fiyat detaylarını getir (depocu fiyat hesaplaması dahil)

        Args:
            urun_id: Urun.UrunId

        Returns:
            Dict: UrunId, UrunAdi, EsdegerId, Stok, PSF, KamuFiyat, DepocuFiyat, Fark, IskontoKamu

        Depocu Fiyat Formülü (Türk İlaç Fiyatlandırması):
            Depocu (KDV Hariç) = PSF × 0.71
            Depocu (KDV Dahil) = Depocu (KDV Hariç) × 1.10
            Depocu (İskontolu) = Depocu (KDV Dahil) × (1 - IskontoKamu/100)

        Fiyat Farkı:
            ReceteIlaclari.RIFiyatFarki kolonundan son reçete kaydındaki değer alınır.
            Bu değer, ilacın SGK referans fiyatı ile satış fiyatı arasındaki farkı gösterir.
        """
        sql = f"""
        SELECT
            u.UrunId,
            u.UrunAdi,
            u.UrunEsdegerId as EsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            u.UrunFiyatEtiket as PSF,
            u.UrunFiyatKamu as KamuFiyat,
            ISNULL(u.UrunIskontoKamu, 0) as IskontoKamu,
            -- Depocu fiyat: PSF × 0.71 × 1.10 × (1 - IskontoKamu/100)
            -- KDV dahil ve kamu iskontosu uygulanmış
            u.UrunFiyatEtiket * 0.71 * 1.10 * (1 - ISNULL(u.UrunIskontoKamu, 0) / 100.0) as DepocuFiyat,
            -- Fiyat farkı: ReceteIlaclari tablosundan son kayıt (KUTU BAŞINA)
            -- RIFiyatFarki toplam fark, RIAdet'e bölerek birim fark elde ediyoruz
            ISNULL((
                SELECT TOP 1 ri.RIFiyatFarki / NULLIF(ri.RIAdet, 0)
                FROM ReceteIlaclari ri
                JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                WHERE ri.RIUrunId = u.UrunId
                AND ri.RIFiyatFarki > 0
                AND ri.RIAdet > 0
                AND ra.RxSilme = 0
                ORDER BY ra.RxKayitTarihi DESC
            ), 0) as Fark
        FROM Urun u
        WHERE u.UrunId = {urun_id}
        AND u.UrunSilme = 0
        """
        sonuc = self.sorgu_calistir(sql)
        return sonuc[0] if sonuc else None

    def mf_aylik_satis_getir(
        self,
        urun_idler: List[int],
        ay_sayisi: int = 6
    ) -> List[Dict]:
        """
        Belirtilen ilaçların aylık satış verilerini getir

        Args:
            urun_idler: İlaç ID listesi
            ay_sayisi: Kaç aylık veri (max 24)

        Returns:
            List[Dict]: Her ay için: AyKod (2024-01), SGKSatis, EldenSatis, ToplamSatis
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        if not urun_idler:
            return []

        ay_sayisi = min(ay_sayisi, 24)
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=ay_sayisi)).replace(day=1)

        urun_id_str = ','.join(map(str, urun_idler))

        # NOT: Kayıt tarihi (RxKayitTarihi) kullanılıyor, reçete tarihi değil!
        # Botanik Guide da kayıt tarihini esas alır.
        sql = f"""
        ;WITH Aylar AS (
            -- Son N ay için tarih aralıkları
            SELECT
                FORMAT(DATEADD(MONTH, -n, GETDATE()), 'yyyy-MM') as AyKod,
                DATEFROMPARTS(YEAR(DATEADD(MONTH, -n, GETDATE())), MONTH(DATEADD(MONTH, -n, GETDATE())), 1) as AyBasi,
                EOMONTH(DATEADD(MONTH, -n, GETDATE())) as AySonu
            FROM (SELECT TOP {ay_sayisi} ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 as n
                  FROM sys.objects) nums
        ),
        SGKSatislar AS (
            SELECT
                FORMAT(ra.RxKayitTarihi, 'yyyy-MM') as AyKod,
                SUM(ri.RIAdet) as Adet
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ri.RIUrunId IN ({urun_id_str})
            AND ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{baslangic.strftime('%Y-%m-%d')}'
            GROUP BY FORMAT(ra.RxKayitTarihi, 'yyyy-MM')
        ),
        EldenSatislar AS (
            SELECT
                FORMAT(ea.RxKayitTarihi, 'yyyy-MM') as AyKod,
                SUM(ei.RIAdet) as Adet
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ei.RIUrunId IN ({urun_id_str})
            AND ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{baslangic.strftime('%Y-%m-%d')}'
            GROUP BY FORMAT(ea.RxKayitTarihi, 'yyyy-MM')
        )
        SELECT
            a.AyKod,
            COALESCE(s.Adet, 0) as SGKSatis,
            COALESCE(e.Adet, 0) as EldenSatis,
            COALESCE(s.Adet, 0) + COALESCE(e.Adet, 0) as ToplamSatis
        FROM Aylar a
        LEFT JOIN SGKSatislar s ON a.AyKod = s.AyKod
        LEFT JOIN EldenSatislar e ON a.AyKod = e.AyKod
        ORDER BY a.AyKod DESC
        """
        return self.sorgu_calistir(sql)

    def mf_konsolide_veri_getir(
        self,
        urun_idler: List[int],
        ay_sayisi: int = 6
    ) -> Dict:
        """
        Birden fazla ilacın konsolide verilerini getir

        Args:
            urun_idler: İlaç ID listesi
            ay_sayisi: Kaç aylık veri

        Returns:
            Dict: {
                'toplam_stok': int,
                'aylik_ortalama': float,
                'aylik_veriler': List[Dict],  # Ay bazında SGK+Elden
                'ilac_detaylari': List[Dict]  # Her ilacın detayı
            }
        """
        if not urun_idler:
            return {'toplam_stok': 0, 'aylik_ortalama': 0, 'aylik_veriler': [], 'ilac_detaylari': []}

        urun_id_str = ','.join(map(str, urun_idler))

        # Stok ve ilaç detayları
        stok_sql = f"""
        SELECT
            u.UrunId,
            u.UrunAdi,
            u.UrunEsdegerId,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            u.UrunFiyatEtiket as PSF,
            u.UrunFiyatKamu as KamuFiyat,
            COALESCE(
                (SELECT TOP 1 fs.FSMaliyet
                 FROM FaturaSatir fs
                 JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                 WHERE fs.FSUrunId = u.UrunId AND fg.FGSilme = 0 AND fs.FSMaliyet > 0
                 ORDER BY fg.FGFaturaTarihi DESC),
                u.UrunFiyatEtiket * 0.80
            ) as DepocuFiyat
        FROM Urun u
        WHERE u.UrunId IN ({urun_id_str})
        AND u.UrunSilme = 0
        ORDER BY u.UrunAdi
        """
        ilac_detaylari = self.sorgu_calistir(stok_sql)

        # Toplam stok
        toplam_stok = sum(i.get('Stok', 0) or 0 for i in ilac_detaylari)

        # Aylık satışlar
        aylik_veriler = self.mf_aylik_satis_getir(urun_idler, ay_sayisi)

        # Aylık ortalama
        toplam_satis = sum(a.get('ToplamSatis', 0) or 0 for a in aylik_veriler)
        aylik_ortalama = toplam_satis / ay_sayisi if ay_sayisi > 0 else 0

        return {
            'toplam_stok': toplam_stok,
            'aylik_ortalama': round(aylik_ortalama, 2),
            'aylik_veriler': aylik_veriler,
            'ilac_detaylari': ilac_detaylari
        }

    def mf_satis_analizi_getir(
        self,
        urun_idler: List[int],
        ay_sayisi: int = 6
    ) -> Dict:
        """
        Seçilen ilaçlar için detaylı satış analizi getir.
        SGK/Elden, Raporlu/Raporsuz, Emekli/Çalışan dağılımı.
        Tüm değerler KUTU ADEDİ üzerinden hesaplanır.

        Args:
            urun_idler: İlaç ID listesi
            ay_sayisi: Kaç aylık veri

        Returns:
            Dict: {
                'sgk_toplam': int,          # SGK toplam kutu
                'elden_toplam': int,        # Elden toplam kutu
                'sgk_raporlu': int,         # SGK raporlu kutu
                'sgk_raporsuz': int,        # SGK raporsuz kutu
                'sgk_emekli': int,          # SGK emekli kutu
                'sgk_calisan': int,         # SGK çalışan kutu
                'sgk_oran': float,          # SGK yüzdesi
                'elden_oran': float,        # Elden yüzdesi
                'raporlu_oran': float,      # Raporlu yüzdesi (SGK içinde)
                'raporsuz_oran': float,     # Raporsuz yüzdesi (SGK içinde)
                'emekli_oran': float,       # Emekli yüzdesi (SGK içinde)
                'calisan_oran': float       # Çalışan yüzdesi (SGK içinde)
            }
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        if not urun_idler:
            return {
                'sgk_toplam': 0, 'elden_toplam': 0,
                'sgk_raporlu': 0, 'sgk_raporsuz': 0,
                'sgk_emekli': 0, 'sgk_calisan': 0,
                'sgk_oran': 0, 'elden_oran': 0,
                'raporlu_oran': 0, 'raporsuz_oran': 0,
                'emekli_oran': 0, 'calisan_oran': 0
            }

        ay_sayisi = min(ay_sayisi, 24)
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=ay_sayisi)).replace(day=1)
        baslangic_str = baslangic.strftime('%Y-%m-%d')

        urun_id_str = ','.join(map(str, urun_idler))

        # SGK Satışları - SGK işlem numarası OLAN reçeteler
        # Raporlu/Raporsuz ve Emekli/Çalışan ayrımı
        sql_sgk = f"""
        SELECT
            SUM(ri.RIAdet) as ToplamAdet,
            SUM(CASE WHEN ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0
                THEN ri.RIAdet ELSE 0 END) as RaporluAdet,
            SUM(CASE WHEN ri.RIRaporKodId IS NULL OR ri.RIRaporKodId = 0
                THEN ri.RIAdet ELSE 0 END) as RaporsuzAdet,
            SUM(CASE WHEN m.MusteriEmeklilik = 1
                THEN ri.RIAdet ELSE 0 END) as EmekliAdet,
            SUM(CASE WHEN m.MusteriEmeklilik = 0 OR m.MusteriEmeklilik IS NULL
                THEN ri.RIAdet ELSE 0 END) as CalisanAdet
        FROM ReceteIlaclari ri
        JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
        LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
        WHERE ri.RIUrunId IN ({urun_id_str})
        AND ra.RxSilme = 0 AND ri.RISilme = 0
        AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
        AND ra.RxKayitTarihi >= '{baslangic_str}'
        AND ra.RxSgkIslemNo IS NOT NULL AND ra.RxSgkIslemNo != ''
        """
        sgk_sonuc = self.sorgu_calistir(sql_sgk)

        # Elden Satışları: EldenAna + SGK işlem numarası OLMAYAN reçeteler
        sql_elden = f"""
        SELECT SUM(Adet) as ToplamAdet FROM (
            -- EldenAna tablosundan
            SELECT ei.RIAdet as Adet
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ei.RIUrunId IN ({urun_id_str})
            AND ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{baslangic_str}'

            UNION ALL

            -- ReceteAna'dan SGK işlem numarası OLMAYAN reçeteler
            SELECT ri.RIAdet as Adet
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ri.RIUrunId IN ({urun_id_str})
            AND ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{baslangic_str}'
            AND (ra.RxSgkIslemNo IS NULL OR ra.RxSgkIslemNo = '')
        ) as EldenSatislar
        """
        elden_sonuc = self.sorgu_calistir(sql_elden)

        # Sonuçları parse et
        sgk_toplam = int(sgk_sonuc[0].get('ToplamAdet') or 0) if sgk_sonuc else 0
        sgk_raporlu = int(sgk_sonuc[0].get('RaporluAdet') or 0) if sgk_sonuc else 0
        sgk_raporsuz = int(sgk_sonuc[0].get('RaporsuzAdet') or 0) if sgk_sonuc else 0
        sgk_emekli = int(sgk_sonuc[0].get('EmekliAdet') or 0) if sgk_sonuc else 0
        sgk_calisan = int(sgk_sonuc[0].get('CalisanAdet') or 0) if sgk_sonuc else 0
        elden_toplam = int(elden_sonuc[0].get('ToplamAdet') or 0) if elden_sonuc else 0

        # Oranları hesapla
        genel_toplam = sgk_toplam + elden_toplam
        sgk_oran = round((sgk_toplam / genel_toplam * 100), 1) if genel_toplam > 0 else 0
        elden_oran = round((elden_toplam / genel_toplam * 100), 1) if genel_toplam > 0 else 0

        # SGK içindeki oranlar
        raporlu_oran = round((sgk_raporlu / sgk_toplam * 100), 1) if sgk_toplam > 0 else 0
        raporsuz_oran = round((sgk_raporsuz / sgk_toplam * 100), 1) if sgk_toplam > 0 else 0
        emekli_oran = round((sgk_emekli / sgk_toplam * 100), 1) if sgk_toplam > 0 else 0
        calisan_oran = round((sgk_calisan / sgk_toplam * 100), 1) if sgk_toplam > 0 else 0

        return {
            'sgk_toplam': sgk_toplam,
            'elden_toplam': elden_toplam,
            'sgk_raporlu': sgk_raporlu,
            'sgk_raporsuz': sgk_raporsuz,
            'sgk_emekli': sgk_emekli,
            'sgk_calisan': sgk_calisan,
            'sgk_oran': sgk_oran,
            'elden_oran': elden_oran,
            'raporlu_oran': raporlu_oran,
            'raporsuz_oran': raporsuz_oran,
            'emekli_oran': emekli_oran,
            'calisan_oran': calisan_oran
        }

    def personel_listesi_getir(self) -> List[Dict]:
        """
        Aktif personel listesini döndür.

        Returns:
            List[Dict]: PersonelId, PersonelAdiSoyadi
        """
        sql = """
        SELECT PersonelId, PersonelAdiSoyadi
        FROM Personel
        WHERE PersonelSilme = 0
        ORDER BY PersonelAdiSoyadi
        """
        return self.sorgu_calistir(sql)

    def prim_raporu_getir(self, baslangic: str, bitis: str, personel_id: int = None) -> List[Dict]:
        """
        Prim raporlama verileri.
        Tarih aralığında prim verilen ürünlerin elden + reçeteli satışlarını getirir.

        Args:
            baslangic: Başlangıç tarihi (YYYY-MM-DD)
            bitis: Bitiş tarihi (YYYY-MM-DD)
            personel_id: Personel filtresi (None=tümü)

        Returns:
            List[Dict]: UrunAdi, UrunId, Etiket, Adet, Indirimler, Tutar,
                        PrimYuzde, PrimTutar, Personel, PersonelId, Tarih, AlisFiyati, AlisTahmini
        """
        personel_filtre_elden = ""
        personel_filtre_recete = ""
        if personel_id is not None:
            personel_filtre_elden = f"AND COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ea.RxPersonelId, 0)) = {int(personel_id)}"
            personel_filtre_recete = f"AND COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ra.RxPersonelId, 0)) = {int(personel_id)}"

        sql = f"""
        SELECT * FROM (
            -- Elden satislar
            SELECT
                u.UrunAdi, u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                ei.RIEtiketFiyati as Etiket,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1 THEN -ei.RIAdet ELSE ei.RIAdet END as Adet,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1
                    THEN -COALESCE(eh.RHIskontoToplam * ei.RIToplam / NULLIF(eh.RHEtiketToplam, 0), 0)
                    ELSE COALESCE(eh.RHIskontoToplam * ei.RIToplam / NULLIF(eh.RHEtiketToplam, 0), 0)
                END as Indirimler,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1 THEN -ei.RIToplam ELSE ei.RIToplam END as Tutar,
                COALESCE(pt.PrimTipTutar3, 0) as PrimYuzde,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1 THEN -(ei.RIToplam * COALESCE(pt.PrimTipTutar3, 0) / 100.0) ELSE ei.RIToplam * COALESCE(pt.PrimTipTutar3, 0) / 100.0 END as PrimTutar,
                COALESCE(pl.PersonelAdiSoyadi, p.PersonelAdiSoyadi, 'ATANMAMIŞ') as Personel,
                COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ea.RxPersonelId, 0), 0) as PersonelId,
                ea.RxReceteTarihi as Tarih,
                ISNULL(ei.RIIade, 0) as Iade,
                COALESCE(
                    (SELECT TOP 1 Fiyat FROM (
                        SELECT fs.FSMaliyet as Fiyat, fg.FGFaturaTarihi as Tarih, fg.FGId as Id
                        FROM FaturaSatir fs
                        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                        LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                        WHERE fs.FSUrunId = u.UrunId
                        AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                        AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                        UNION ALL
                        SELECT ts.TSUrunFiyat as Fiyat, t.TakasTarihi as Tarih, t.TakasId as Id
                        FROM TakasSatir ts
                        JOIN Takas t ON ts.TSTakasId = t.TakasId
                        WHERE ts.TSUrunId = u.UrunId
                        AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                        AND t.TakasSilme = 0 AND ts.TSSilme = 0
                        AND t.TakasYonu = 1
                     ) alis_kaynak ORDER BY Tarih DESC, Id DESC),
                    ei.RIEtiketFiyati * 0.80
                ) as AlisFiyati,
                CASE WHEN (SELECT TOP 1 1 FROM (
                    SELECT fg.FGFaturaTarihi as Tarih
                    FROM FaturaSatir fs
                    JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                    LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                    WHERE fs.FSUrunId = u.UrunId
                    AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                    AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                    UNION ALL
                    SELECT t.TakasTarihi as Tarih
                    FROM TakasSatir ts
                    JOIN Takas t ON ts.TSTakasId = t.TakasId
                    WHERE ts.TSUrunId = u.UrunId
                    AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                    AND t.TakasSilme = 0 AND ts.TSSilme = 0
                    AND t.TakasYonu = 1
                ) alis_kontrol) IS NULL THEN 1 ELSE 0 END as AlisTahmini
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            JOIN Urun u ON ei.RIUrunId = u.UrunId
            JOIN PrimUrunleri pu ON ei.RIUrunId = pu.PUUrunId AND pu.PUPasif = 0
            LEFT JOIN PrimTip pt ON pu.PUPrimTipId = pt.PrimTipId
            LEFT JOIN EldenHesap eh ON eh.RHRxId = ea.RxId AND eh.RHSilme = 0
            LEFT JOIN Personel p ON ea.RxPersonelId = p.PersonelId
            LEFT JOIN Logger lg ON lg.LoggerIslemId = ea.RxId AND lg.LoggerIslemTuru = 2 AND lg.LoggerIslemAltTuru = 1
            LEFT JOIN Personel pl ON lg.LoggerPersonelId = pl.PersonelId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND ea.RxReceteTarihi BETWEEN '{baslangic}' AND '{bitis}'
            {personel_filtre_elden}

            UNION ALL

            -- Receteli satislar
            SELECT
                u.UrunAdi, u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                ri.RIEtiketFiyati as Etiket,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1 THEN -ri.RIAdet ELSE ri.RIAdet END as Adet,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1
                    THEN -COALESCE(rh.RHIskontoToplam * ri.RIToplam / NULLIF(rh.RHEtiketToplam, 0), 0)
                    ELSE COALESCE(rh.RHIskontoToplam * ri.RIToplam / NULLIF(rh.RHEtiketToplam, 0), 0)
                END as Indirimler,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1 THEN -ri.RIToplam ELSE ri.RIToplam END as Tutar,
                COALESCE(pt.PrimTipTutar3, 0) as PrimYuzde,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1 THEN -(ri.RIToplam * COALESCE(pt.PrimTipTutar3, 0) / 100.0) ELSE ri.RIToplam * COALESCE(pt.PrimTipTutar3, 0) / 100.0 END as PrimTutar,
                COALESCE(pl.PersonelAdiSoyadi, p.PersonelAdiSoyadi, 'ATANMAMIŞ') as Personel,
                COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ra.RxPersonelId, 0), 0) as PersonelId,
                ra.RxReceteTarihi as Tarih,
                ISNULL(ri.RIIade, 0) as Iade,
                COALESCE(
                    (SELECT TOP 1 Fiyat FROM (
                        SELECT fs.FSMaliyet as Fiyat, fg.FGFaturaTarihi as Tarih, fg.FGId as Id
                        FROM FaturaSatir fs
                        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                        LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                        WHERE fs.FSUrunId = u.UrunId
                        AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                        AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                        UNION ALL
                        SELECT ts.TSUrunFiyat as Fiyat, t.TakasTarihi as Tarih, t.TakasId as Id
                        FROM TakasSatir ts
                        JOIN Takas t ON ts.TSTakasId = t.TakasId
                        WHERE ts.TSUrunId = u.UrunId
                        AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                        AND t.TakasSilme = 0 AND ts.TSSilme = 0
                        AND t.TakasYonu = 1
                     ) alis_kaynak ORDER BY Tarih DESC, Id DESC),
                    ri.RIEtiketFiyati * 0.80
                ) as AlisFiyati,
                CASE WHEN (SELECT TOP 1 1 FROM (
                    SELECT fg.FGFaturaTarihi as Tarih
                    FROM FaturaSatir fs
                    JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                    LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                    WHERE fs.FSUrunId = u.UrunId
                    AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                    AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                    UNION ALL
                    SELECT t.TakasTarihi as Tarih
                    FROM TakasSatir ts
                    JOIN Takas t ON ts.TSTakasId = t.TakasId
                    WHERE ts.TSUrunId = u.UrunId
                    AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                    AND t.TakasSilme = 0 AND ts.TSSilme = 0
                    AND t.TakasYonu = 1
                ) alis_kontrol) IS NULL THEN 1 ELSE 0 END as AlisTahmini
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            JOIN Urun u ON ri.RIUrunId = u.UrunId
            JOIN PrimUrunleri pu ON ri.RIUrunId = pu.PUUrunId AND pu.PUPasif = 0
            LEFT JOIN PrimTip pt ON pu.PUPrimTipId = pt.PrimTipId
            LEFT JOIN ReceteHesap rh ON rh.RHRxId = ra.RxId AND rh.RHSilme = 0
            LEFT JOIN Personel p ON ra.RxPersonelId = p.PersonelId
            LEFT JOIN Logger lg ON lg.LoggerIslemId = ra.RxId AND lg.LoggerIslemTuru = 1 AND lg.LoggerIslemAltTuru = 1
            LEFT JOIN Personel pl ON lg.LoggerPersonelId = pl.PersonelId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND ra.RxReceteTarihi BETWEEN '{baslangic}' AND '{bitis}'
            {personel_filtre_recete}
        ) TumSatislar
        ORDER BY UrunAdi, Tarih
        """
        return self.sorgu_calistir(sql)

    def ilac_disi_raporu_getir(self, baslangic: str, bitis: str, personel_id: int = None) -> List[Dict]:
        """
        İlaç dışı tüm ürünlerin satış raporu.
        İlaç, Pasif İlaç, Serumlar, Tıbbi Mamalar, İlaç Beraberi hariç tüm ürün tiplerini getirir.
        """
        personel_filtre_elden = ""
        personel_filtre_recete = ""
        if personel_id is not None:
            personel_filtre_elden = f"AND COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ea.RxPersonelId, 0)) = {int(personel_id)}"
            personel_filtre_recete = f"AND COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ra.RxPersonelId, 0)) = {int(personel_id)}"

        haric_tipler = "'İlaç', 'Pasif İlaç', 'Serumlar', 'Tıbbi Mamalar', 'İlaç Beraberi'"

        sql = f"""
        SELECT * FROM (
            -- Elden satislar
            SELECT
                u.UrunAdi, u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                ei.RIEtiketFiyati as Etiket,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1 THEN -ei.RIAdet ELSE ei.RIAdet END as Adet,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1
                    THEN -COALESCE(eh.RHIskontoToplam * ei.RIToplam / NULLIF(eh.RHEtiketToplam, 0), 0)
                    ELSE COALESCE(eh.RHIskontoToplam * ei.RIToplam / NULLIF(eh.RHEtiketToplam, 0), 0)
                END as Indirimler,
                CASE WHEN ISNULL(ei.RIIade, 0) = 1 THEN -ei.RIToplam ELSE ei.RIToplam END as Tutar,
                0 as PrimYuzde,
                0 as PrimTutar,
                COALESCE(pl.PersonelAdiSoyadi, p.PersonelAdiSoyadi, 'ATANMAMIŞ') as Personel,
                COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ea.RxPersonelId, 0), 0) as PersonelId,
                ea.RxReceteTarihi as Tarih,
                ISNULL(ei.RIIade, 0) as Iade,
                COALESCE(
                    (SELECT TOP 1 Fiyat FROM (
                        SELECT fs.FSMaliyet as Fiyat, fg.FGFaturaTarihi as Tarih, fg.FGId as Id
                        FROM FaturaSatir fs
                        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                        LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                        WHERE fs.FSUrunId = u.UrunId
                        AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                        AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                        UNION ALL
                        SELECT ts.TSUrunFiyat as Fiyat, t.TakasTarihi as Tarih, t.TakasId as Id
                        FROM TakasSatir ts
                        JOIN Takas t ON ts.TSTakasId = t.TakasId
                        WHERE ts.TSUrunId = u.UrunId
                        AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                        AND t.TakasSilme = 0 AND ts.TSSilme = 0
                        AND t.TakasYonu = 1
                     ) alis_kaynak ORDER BY Tarih DESC, Id DESC),
                    ei.RIEtiketFiyati * 0.80
                ) as AlisFiyati,
                CASE WHEN (SELECT TOP 1 1 FROM (
                    SELECT fg.FGFaturaTarihi as Tarih
                    FROM FaturaSatir fs
                    JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                    LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                    WHERE fs.FSUrunId = u.UrunId
                    AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                    AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                    UNION ALL
                    SELECT t.TakasTarihi as Tarih
                    FROM TakasSatir ts
                    JOIN Takas t ON ts.TSTakasId = t.TakasId
                    WHERE ts.TSUrunId = u.UrunId
                    AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                    AND t.TakasSilme = 0 AND ts.TSSilme = 0
                    AND t.TakasYonu = 1
                ) alis_kontrol) IS NULL THEN 1 ELSE 0 END as AlisTahmini
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            JOIN Urun u ON ei.RIUrunId = u.UrunId
            LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
            LEFT JOIN EldenHesap eh ON eh.RHRxId = ea.RxId AND eh.RHSilme = 0
            LEFT JOIN Personel p ON ea.RxPersonelId = p.PersonelId
            LEFT JOIN Logger lg ON lg.LoggerIslemId = ea.RxId AND lg.LoggerIslemTuru = 2 AND lg.LoggerIslemAltTuru = 1
            LEFT JOIN Personel pl ON lg.LoggerPersonelId = pl.PersonelId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND ea.RxReceteTarihi BETWEEN '{baslangic}' AND '{bitis}'
            AND COALESCE(ut.UrunTipAdi, '') NOT IN ({haric_tipler})
            {personel_filtre_elden}

            UNION ALL

            -- Receteli satislar
            SELECT
                u.UrunAdi, u.UrunId,
                (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId ORDER BY b.BarkodSilme ASC) as Barkod,
                ri.RIEtiketFiyati as Etiket,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1 THEN -ri.RIAdet ELSE ri.RIAdet END as Adet,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1
                    THEN -COALESCE(rh.RHIskontoToplam * ri.RIToplam / NULLIF(rh.RHEtiketToplam, 0), 0)
                    ELSE COALESCE(rh.RHIskontoToplam * ri.RIToplam / NULLIF(rh.RHEtiketToplam, 0), 0)
                END as Indirimler,
                CASE WHEN ISNULL(ri.RIIade, 0) = 1 THEN -ri.RIToplam ELSE ri.RIToplam END as Tutar,
                0 as PrimYuzde,
                0 as PrimTutar,
                COALESCE(pl.PersonelAdiSoyadi, p.PersonelAdiSoyadi, 'ATANMAMIŞ') as Personel,
                COALESCE(NULLIF(lg.LoggerPersonelId, -1), NULLIF(ra.RxPersonelId, 0), 0) as PersonelId,
                ra.RxReceteTarihi as Tarih,
                ISNULL(ri.RIIade, 0) as Iade,
                COALESCE(
                    (SELECT TOP 1 Fiyat FROM (
                        SELECT fs.FSMaliyet as Fiyat, fg.FGFaturaTarihi as Tarih, fg.FGId as Id
                        FROM FaturaSatir fs
                        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                        LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                        WHERE fs.FSUrunId = u.UrunId
                        AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                        AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                        UNION ALL
                        SELECT ts.TSUrunFiyat as Fiyat, t.TakasTarihi as Tarih, t.TakasId as Id
                        FROM TakasSatir ts
                        JOIN Takas t ON ts.TSTakasId = t.TakasId
                        WHERE ts.TSUrunId = u.UrunId
                        AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                        AND t.TakasSilme = 0 AND ts.TSSilme = 0
                        AND t.TakasYonu = 1
                     ) alis_kaynak ORDER BY Tarih DESC, Id DESC),
                    ri.RIEtiketFiyati * 0.80
                ) as AlisFiyati,
                CASE WHEN (SELECT TOP 1 1 FROM (
                    SELECT fg.FGFaturaTarihi as Tarih
                    FROM FaturaSatir fs
                    JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                    LEFT JOIN Depo dfl ON fg.FGIlgiliId = dfl.DepoId
                    WHERE fs.FSUrunId = u.UrunId
                    AND fs.FSMaliyet > 0 AND fs.FSUrunAdet > 0
                    AND ISNULL(dfl.DepoAdi, '') NOT LIKE '%düzeltme%'
                    UNION ALL
                    SELECT t.TakasTarihi as Tarih
                    FROM TakasSatir ts
                    JOIN Takas t ON ts.TSTakasId = t.TakasId
                    WHERE ts.TSUrunId = u.UrunId
                    AND ts.TSUrunFiyat > 0 AND ts.TSUrunAdedi > 0
                    AND t.TakasSilme = 0 AND ts.TSSilme = 0
                    AND t.TakasYonu = 1
                ) alis_kontrol) IS NULL THEN 1 ELSE 0 END as AlisTahmini
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            JOIN Urun u ON ri.RIUrunId = u.UrunId
            LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
            LEFT JOIN ReceteHesap rh ON rh.RHRxId = ra.RxId AND rh.RHSilme = 0
            LEFT JOIN Personel p ON ra.RxPersonelId = p.PersonelId
            LEFT JOIN Logger lg ON lg.LoggerIslemId = ra.RxId AND lg.LoggerIslemTuru = 1 AND lg.LoggerIslemAltTuru = 1
            LEFT JOIN Personel pl ON lg.LoggerPersonelId = pl.PersonelId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND ra.RxReceteTarihi BETWEEN '{baslangic}' AND '{bitis}'
            AND COALESCE(ut.UrunTipAdi, '') NOT IN ({haric_tipler})
            {personel_filtre_recete}
        ) TumSatislar
        ORDER BY UrunAdi, Tarih
        """
        return self.sorgu_calistir(sql)

    def prim_urunleri_listesi_getir(self) -> List[Dict]:
        """
        Prim verilen ürünlerin listesini döndür.

        Returns:
            List[Dict]: UrunAdi, UrunId, PrimYuzde, PrimTipAdi, EklemeTarihi, EtiketFiyat, Stok
        """
        sql = """
        SELECT
            u.UrunAdi,
            u.UrunId,
            COALESCE(pt.PrimTipTutar3, 0) as PrimYuzde,
            COALESCE(pt.PrimTipAdi, 'Tanımsız') as PrimTipAdi,
            pu.PUEklemeTarihi as EklemeTarihi,
            u.UrunFiyatEtiket as EtiketFiyat,
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok
        FROM PrimUrunleri pu
        JOIN Urun u ON pu.PUUrunId = u.UrunId
        LEFT JOIN PrimTip pt ON pu.PUPrimTipId = pt.PrimTipId
        WHERE pu.PUPasif = 0
        ORDER BY u.UrunAdi
        """
        return self.sorgu_calistir(sql)

    def mf_tahsilat_analizi_getir(self, ay_sayisi: int = 6) -> Dict:
        """
        TÜM reçeteler için tahsilat analizi.
        Hastadan alınan 4 kalem: Muayene, Reçete Katılım, İlaç Katılım, Fark

        YazarKasaKuyUrunler.YKKUrunSatisTipi:
        - 0: Muayene Katkı Payı
        - 1: Reçete Katkı Payı
        - 2: Hasta/İlaç Katılım Payı
        - 3: Fiyat Farkı

        Args:
            ay_sayisi: Kaç aylık veri (varsayılan 6)

        Returns:
            Dict: {
                'recete_sayisi': int,
                'muayene_toplam': float,
                'recete_katilim_toplam': float,
                'ilac_katilim_toplam': float,
                'fark_toplam': float,
                'genel_toplam': float,
                'muayene_oran': float,
                'recete_katilim_oran': float,
                'ilac_katilim_oran': float,
                'fark_oran': float
            }
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        ay_sayisi = min(ay_sayisi, 24)
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=ay_sayisi)).replace(day=1)
        baslangic_str = baslangic.strftime('%Y-%m-%d')

        sql = f"""
        SELECT
            SUM(CASE WHEN u.YKKUrunSatisTipi = 0 THEN u.YKKUrunFiyat * u.YKKUrunAdet ELSE 0 END) as MuayeneToplam,
            SUM(CASE WHEN u.YKKUrunSatisTipi = 1 THEN u.YKKUrunFiyat * u.YKKUrunAdet ELSE 0 END) as ReceteKatilimToplam,
            SUM(CASE WHEN u.YKKUrunSatisTipi = 2 THEN u.YKKUrunFiyat * u.YKKUrunAdet ELSE 0 END) as IlacKatilimToplam,
            SUM(CASE WHEN u.YKKUrunSatisTipi = 3 THEN u.YKKUrunFiyat * u.YKKUrunAdet ELSE 0 END) as FarkToplam,
            SUM(CASE WHEN u.YKKUrunSatisTipi IN (0,1,2,3) THEN u.YKKUrunFiyat * u.YKKUrunAdet ELSE 0 END) as GenelToplam,
            COUNT(DISTINCT yks.YKKSatId) as ReceteSayisi
        FROM YazarKasaKuySatis yks
        JOIN YazarKasaKuyUrunler u ON u.YKKUrunSatId = yks.YKKSatId
        JOIN ReceteAna ra ON yks.YKKSatRXId = ra.RxId
        WHERE ra.RxSilme = 0
        AND u.YKKUrunSatisTipi IN (0,1,2,3)
        AND ra.RxKayitTarihi >= '{baslangic_str}'
        """
        sonuc = self.sorgu_calistir(sql)

        if not sonuc or not sonuc[0]:
            return {
                'recete_sayisi': 0,
                'muayene_toplam': 0, 'recete_katilim_toplam': 0,
                'ilac_katilim_toplam': 0, 'fark_toplam': 0, 'genel_toplam': 0,
                'muayene_oran': 0, 'recete_katilim_oran': 0,
                'ilac_katilim_oran': 0, 'fark_oran': 0
            }

        s = sonuc[0]
        recete_sayisi = int(s.get('ReceteSayisi') or 0)
        muayene = float(s.get('MuayeneToplam') or 0)
        recete_kat = float(s.get('ReceteKatilimToplam') or 0)
        ilac_kat = float(s.get('IlacKatilimToplam') or 0)
        fark = float(s.get('FarkToplam') or 0)
        toplam = float(s.get('GenelToplam') or 0)

        # Oranları hesapla
        muayene_oran = round((muayene / toplam * 100), 1) if toplam > 0 else 0
        recete_kat_oran = round((recete_kat / toplam * 100), 1) if toplam > 0 else 0
        ilac_kat_oran = round((ilac_kat / toplam * 100), 1) if toplam > 0 else 0
        fark_oran = round((fark / toplam * 100), 1) if toplam > 0 else 0

        return {
            'recete_sayisi': recete_sayisi,
            'muayene_toplam': round(muayene, 2),
            'recete_katilim_toplam': round(recete_kat, 2),
            'ilac_katilim_toplam': round(ilac_kat, 2),
            'fark_toplam': round(fark, 2),
            'genel_toplam': round(toplam, 2),
            'muayene_oran': muayene_oran,
            'recete_katilim_oran': recete_kat_oran,
            'ilac_katilim_oran': ilac_kat_oran,
            'fark_oran': fark_oran
        }


    # ============================================================
    # SATIS RAPORLARI (yeni modul - 2026-05-18)
    # ReceteAna + EldenAna birlesik, tarih aralikli ve periyot bazli
    # toplam metrikler (recete/satis/kutu/TL).
    # ============================================================

    PERIYOT_IFADELERI = {
        'gunluk':   "CAST(Tarih as date)",
        'haftalik': "DATEADD(DAY, 2 - ((DATEPART(WEEKDAY, Tarih) + @@DATEFIRST - 1) % 7 + 1), CAST(Tarih as date))",
        'aylik':    "DATEFROMPARTS(YEAR(Tarih), MONTH(Tarih), 1)",
        '3aylik':   "DATEFROMPARTS(YEAR(Tarih), ((MONTH(Tarih) - 1) / 3) * 3 + 1, 1)",
        'yillik':   "DATEFROMPARTS(YEAR(Tarih), 1, 1)",
    }

    def kurum_listesi_getir(self) -> List[Dict]:
        """Reçete kırılımında dropdown için kurum listesi (SGK + diğer).

        Returns: [{KurumId, KurumAdi}, ...] alfabetik sıralı.
        """
        sql = """
        SELECT DISTINCT
            k.KurumId,
            k.KurumAdi
        FROM Kurum k
        WHERE k.KurumAdi IS NOT NULL
            AND LTRIM(RTRIM(k.KurumAdi)) <> ''
            AND EXISTS (
                SELECT 1 FROM ReceteAna ra
                WHERE ra.RxKurumId = k.KurumId AND ra.RxSilme = 0
            )
        ORDER BY k.KurumAdi
        """
        return self.sorgu_calistir(sql)

    def urun_fiyat_gecmisi_getir(
        self,
        urun_id: int,
        baslangic_tarih,
        bitis_tarih,
        periyot: str = 'aylik',
    ) -> List[Dict]:
        """Belirli bir ürünün tarihsel etiket fiyatı (PSF) ortalamasını periyot bazlı döndür.

        ReceteIlaclari.RIEtiketFiyati + EldenIlaclari.RIEtiketFiyati üzerinden
        her satış anındaki PSF — endeks olarak kullanılır. (TİTCK fiyat tablosu
        gerekli değil — satış kalemlerinde zaten var.)

        Args:
            urun_id: Botanik UrunId
            baslangic_tarih, bitis_tarih: date veya 'YYYY-MM-DD'
            periyot: 'gunluk'|'haftalik'|'aylik'|'3aylik'|'yillik'

        Returns:
            [{Donem(date), OrtalamaPSF(float), SatisSayisi(int)}, ...]
        """
        if periyot not in self.PERIYOT_IFADELERI:
            raise ValueError(f"Geçersiz periyot: {periyot}")

        if hasattr(baslangic_tarih, 'strftime'):
            bas_str = baslangic_tarih.strftime('%Y-%m-%d')
        else:
            bas_str = str(baslangic_tarih)
        if hasattr(bitis_tarih, 'strftime'):
            bit_str = bitis_tarih.strftime('%Y-%m-%d')
        else:
            bit_str = str(bitis_tarih)

        period_expr = self.PERIYOT_IFADELERI[periyot]
        urun_id_int = int(urun_id)

        sql = f"""
        WITH FiyatKalem AS (
            SELECT
                ra.RxIslemTarihi as Tarih,
                ri.RIEtiketFiyati as Fiyat
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
                AND ri.RIUrunId = {urun_id_int}
                AND ri.RIEtiketFiyati IS NOT NULL
                AND ri.RIEtiketFiyati > 0
                AND ra.RxIslemTarihi >= ?
                AND ra.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))

            UNION ALL

            SELECT
                ea.RxIslemTarihi as Tarih,
                ei.RIEtiketFiyati as Fiyat
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
                AND ei.RIUrunId = {urun_id_int}
                AND ei.RIEtiketFiyati IS NOT NULL
                AND ei.RIEtiketFiyati > 0
                AND ea.RxIslemTarihi >= ?
                AND ea.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))
        )
        SELECT
            {period_expr} as Donem,
            AVG(CAST(Fiyat as decimal(18,4))) as OrtalamaPSF,
            COUNT(*) as SatisSayisi
        FROM FiyatKalem
        GROUP BY {period_expr}
        ORDER BY {period_expr}
        """
        params = (bas_str, bit_str, bas_str, bit_str)
        sonuclar = self.sorgu_calistir(sql, params)
        return [{
            'Donem': r.get('Donem'),
            'OrtalamaPSF': float(r.get('OrtalamaPSF') or 0),
            'SatisSayisi': int(r.get('SatisSayisi') or 0),
        } for r in sonuclar]

    def urun_ara(self, arama: str, limit: int = 50) -> List[Dict]:
        """Ürün arama (endeks tanımına Botanik UrunId eşleme için).

        Returns: [{'UrunId', 'UrunAdi', 'UrunFiyatEtiket'}, ...]
        """
        sql = """
        SELECT TOP (?) UrunId, UrunAdi, UrunFiyatEtiket
        FROM Urun
        WHERE UrunSilme = 0 AND UrunAdi LIKE ?
        ORDER BY UrunAdi
        """
        return self.sorgu_calistir(sql, (int(limit), f"%{arama}%"))

    def satis_zaman_tutarlilik_getir(
        self,
        baslangic_dt,
        bitis_dt,
    ) -> List[Dict]:
        """Bir datetime aralığında satışların RxIslemTarihi vs RxKayitTarihi
        karşılaştırması. Zaman kayması/anomali tespitinde kullanılır.

        - RxIslemTarihi: satış üzerindeki zaman (reçete kaydında kullanıcının
          girdiği veya o anki sistem saati)
        - RxKayitTarihi: DB'ye INSERT edildiği fiziksel an

        Args:
            baslangic_dt, bitis_dt: RxIslemTarihi'ne göre filtre

        Returns:
            [{'Kaynak', 'RxId', 'IslemTarihi', 'KayitTarihi', 'FarkSn'(int)}, ...]
            FarkSn pozitif → kayıt işlemden sonra (normal)
            FarkSn büyük → toplu/geç kayıt
            FarkSn negatif → kayıt işlemden önce (mantıksız, hata)
        """
        def _fmt(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d %H:%M:%S')
            return str(d)
        bas_str = _fmt(baslangic_dt)
        bit_str = _fmt(bitis_dt)

        # Kayıt saatsiz (00:00:00) ise: gün bazlı fark hesapla (saatleri yok say)
        # Kayıt saatli ise: saniye bazlı fark (klasik)
        # FarkTipi='sn' veya 'gun' ile hangi hassasiyetin kullanıldığı bildirilir.
        sql = """
        SELECT
            'RECETE' as Kaynak,
            ra.RxId as RxId,
            ra.RxIslemTarihi as IslemTarihi,
            ra.RxKayitTarihi as KayitTarihi,
            CASE
                WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                THEN CAST(DATEDIFF(DAY,
                        CAST(ra.RxIslemTarihi as DATE),
                        CAST(ra.RxKayitTarihi as DATE)) as BIGINT) * 86400
                ELSE DATEDIFF(SECOND, ra.RxIslemTarihi, ra.RxKayitTarihi)
            END as FarkSn,
            CASE
                WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                THEN 'gun'
                ELSE 'sn'
            END as FarkTipi
        FROM ReceteAna ra
        WHERE ra.RxSilme = 0
            AND ra.RxIslemTarihi >= ?
            AND ra.RxIslemTarihi <= ?

        UNION ALL

        SELECT
            'ELDEN' as Kaynak,
            ea.RxId as RxId,
            ea.RxIslemTarihi as IslemTarihi,
            ea.RxKayitTarihi as KayitTarihi,
            CASE
                WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                THEN CAST(DATEDIFF(DAY,
                        CAST(ea.RxIslemTarihi as DATE),
                        CAST(ea.RxKayitTarihi as DATE)) as BIGINT) * 86400
                ELSE DATEDIFF(SECOND, ea.RxIslemTarihi, ea.RxKayitTarihi)
            END as FarkSn,
            CASE
                WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                     AND DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                THEN 'gun'
                ELSE 'sn'
            END as FarkTipi
        FROM EldenAna ea
        WHERE ea.RxSilme = 0
            AND ea.RxIslemTarihi >= ?
            AND ea.RxIslemTarihi <= ?

        ORDER BY IslemTarihi, RxId
        """
        sonuclar = self.sorgu_calistir(sql, (bas_str, bit_str, bas_str, bit_str))
        return [{
            'Kaynak': r.get('Kaynak'),
            'RxId': r.get('RxId'),
            'IslemTarihi': r.get('IslemTarihi'),
            'KayitTarihi': r.get('KayitTarihi'),
            'FarkSn': int(r.get('FarkSn') or 0) if r.get('FarkSn') is not None else None,
            'FarkTipi': r.get('FarkTipi') or 'sn',
        } for r in sonuclar]

    def kayit_tarihi_diagnostik(self) -> Dict:
        """ReceteAna ve EldenAna tablolarındaki `RxKayitTarihi` kolonunu
        analiz eder + DB genelinde bağımsız zaman kaynağı arar.

        Amaç:
        1. RxKayitTarihi'nin gerçek tipi (DATE/DATETIME) ve saat bileşeni
        2. BotanikEOS UI'da görünen saatin hangi kolondan geldiğini bulmak
        3. **Bağımsız zaman kaynağı arama**: DEFAULT GETDATE() vs sunucu-tarafı
           timestamp atayan kolonlar (PC saat sapması tespiti için kritik)
        4. Audit/log tablo adayları

        Returns:
            {
                'recete_kolonlar': [...],   # kolon adı + tipi (zaman içerenler)
                'elden_kolonlar': [...],
                'recete_kayit_saatli': int, # saat > 0 olan reçete sayısı
                'recete_kayit_saatsiz': int,
                'elden_kayit_saatli': int,
                'elden_kayit_saatsiz': int,
                'recete_ornek_saatli': [...],  # 5 saatli örnek (RxId + tam tarihler)
                'recete_ornek_saatsiz': [...], # 5 saatsiz örnek
                'elden_ornek_saatli': [...],
                'elden_ornek_saatsiz': [...],
            }
        """
        sonuc = {}

        # 1. ReceteAna ve EldenAna kolon listesi (sadece zaman içerenler)
        for tablo, anahtar in [('ReceteAna', 'recete_kolonlar'),
                                ('EldenAna', 'elden_kolonlar')]:
            sql = """
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                  AND (
                    DATA_TYPE IN ('date', 'datetime', 'datetime2',
                                  'datetimeoffset', 'smalldatetime', 'time')
                    OR COLUMN_NAME LIKE '%Tarih%'
                    OR COLUMN_NAME LIKE '%Saat%'
                    OR COLUMN_NAME LIKE '%Zaman%'
                    OR COLUMN_NAME LIKE '%Date%'
                    OR COLUMN_NAME LIKE '%Time%'
                  )
                ORDER BY ORDINAL_POSITION
            """
            sonuc[anahtar] = self.sorgu_calistir(sql, (tablo,))

        # 2. Recete kayıt saatli / saatsiz sayım (TOP 1M ile sınırla,
        #    geniş tablo için)
        recete_sayim_sql = """
            SELECT
                SUM(CASE
                    WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) > 0
                      OR DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) > 0
                      OR DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) > 0
                    THEN 1 ELSE 0 END) as Saatli,
                SUM(CASE
                    WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                      AND DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                      AND DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                    THEN 1 ELSE 0 END) as Saatsiz,
                COUNT(*) as Toplam
            FROM ReceteAna ra
            WHERE ra.RxSilme = 0 AND ra.RxKayitTarihi IS NOT NULL
        """
        r_rows = self.sorgu_calistir(recete_sayim_sql)
        if r_rows:
            sonuc['recete_kayit_saatli'] = int(r_rows[0].get('Saatli') or 0)
            sonuc['recete_kayit_saatsiz'] = int(r_rows[0].get('Saatsiz') or 0)
            sonuc['recete_toplam'] = int(r_rows[0].get('Toplam') or 0)

        elden_sayim_sql = """
            SELECT
                SUM(CASE
                    WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) > 0
                      OR DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) > 0
                      OR DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) > 0
                    THEN 1 ELSE 0 END) as Saatli,
                SUM(CASE
                    WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                      AND DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                      AND DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                    THEN 1 ELSE 0 END) as Saatsiz,
                COUNT(*) as Toplam
            FROM EldenAna ea
            WHERE ea.RxSilme = 0 AND ea.RxKayitTarihi IS NOT NULL
        """
        e_rows = self.sorgu_calistir(elden_sayim_sql)
        if e_rows:
            sonuc['elden_kayit_saatli'] = int(e_rows[0].get('Saatli') or 0)
            sonuc['elden_kayit_saatsiz'] = int(e_rows[0].get('Saatsiz') or 0)
            sonuc['elden_toplam'] = int(e_rows[0].get('Toplam') or 0)

        # 3. Saatli ve saatsiz örnekler (BotanikEOS UI ile karşılaştırma için)
        for tablo_kisa, tablo_full in [('recete', 'ReceteAna ra'),
                                         ('elden', 'EldenAna ea')]:
            pref = 'ra' if tablo_kisa == 'recete' else 'ea'
            for tip_kisa, kosul in [
                ('saatli',
                 f"DATEPART(HOUR, CAST({pref}.RxKayitTarihi as DATETIME)) > 0 "
                 f"OR DATEPART(MINUTE, CAST({pref}.RxKayitTarihi as DATETIME)) > 0 "
                 f"OR DATEPART(SECOND, CAST({pref}.RxKayitTarihi as DATETIME)) > 0"),
                ('saatsiz',
                 f"DATEPART(HOUR, CAST({pref}.RxKayitTarihi as DATETIME)) = 0 "
                 f"AND DATEPART(MINUTE, CAST({pref}.RxKayitTarihi as DATETIME)) = 0 "
                 f"AND DATEPART(SECOND, CAST({pref}.RxKayitTarihi as DATETIME)) = 0"),
            ]:
                # Convert RxKayitTarihi to string in SQL to bypass pyodbc truncation
                sql = f"""
                    SELECT TOP 5
                        {pref}.RxId,
                        CONVERT(varchar(30), {pref}.RxIslemTarihi, 121) as IslemStr,
                        CONVERT(varchar(30), {pref}.RxKayitTarihi, 121) as KayitStr,
                        DATEPART(HOUR, CAST({pref}.RxKayitTarihi as DATETIME)) as KayitSaat,
                        DATEPART(MINUTE, CAST({pref}.RxKayitTarihi as DATETIME)) as KayitDk,
                        DATEPART(SECOND, CAST({pref}.RxKayitTarihi as DATETIME)) as KayitSn
                    FROM {tablo_full}
                    WHERE {pref}.RxSilme = 0
                      AND {pref}.RxKayitTarihi IS NOT NULL
                      AND ({kosul})
                    ORDER BY {pref}.RxId DESC
                """
                sonuc[f'{tablo_kisa}_ornek_{tip_kisa}'] = self.sorgu_calistir(sql)

        # 4. Bağımsız zaman kaynağı: DEFAULT GETDATE() yazan kolonlar (TÜM DB)
        bagimsiz_sql = """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE DATA_TYPE IN ('datetime', 'datetime2', 'datetimeoffset',
                                'smalldatetime', 'date')
              AND COLUMN_DEFAULT IS NOT NULL
              AND (COLUMN_DEFAULT LIKE '%GETDATE%'
                   OR COLUMN_DEFAULT LIKE '%SYSDATETIME%'
                   OR COLUMN_DEFAULT LIKE '%CURRENT_TIMESTAMP%'
                   OR COLUMN_DEFAULT LIKE '%GETUTCDATE%')
            ORDER BY TABLE_NAME, COLUMN_NAME
        """
        sonuc['bagimsiz_timestamp_kolonlari'] = self.sorgu_calistir(bagimsiz_sql)

        # 5. Audit / log tablosu adayları
        audit_sql = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
              AND (
                TABLE_NAME LIKE '%Log%' OR
                TABLE_NAME LIKE '%Audit%' OR
                TABLE_NAME LIKE '%History%' OR
                TABLE_NAME LIKE '%Hareket%' OR
                TABLE_NAME LIKE '%Track%' OR
                TABLE_NAME LIKE '%Trail%'
              )
            ORDER BY TABLE_NAME
        """
        sonuc['audit_tablo_adaylari'] = self.sorgu_calistir(audit_sql)

        # 6. SQL Server şu anki saati + Python (PC) şu anki saati
        sunucu_sql = """
            SELECT
                SYSDATETIME() as SunucuSysdatetime,
                GETDATE() as SunucuGetdate,
                GETUTCDATE() as SunucuUtc,
                @@VERSION as SqlVersion
        """
        rows = self.sorgu_calistir(sunucu_sql)
        if rows:
            sonuc['sunucu_zaman'] = dict(rows[0])
        sonuc['pc_zaman'] = datetime.now()
        sonuc['pc_zaman_utc'] = datetime.utcnow()

        return sonuc

    def logger_manuel_degisiklik_tarama(
        self,
        baslangic_dt,
        bitis_dt,
        esik_sn: int = 5,
        max_kayit: int = 50000,
    ) -> Dict:
        """RxIslemTarihi vs Logger orijinal kayıt (Turu=1/1 reçete, 2/1 elden)
        karşılaştırması. |fark| > esik_sn ise muhtemel manuel tarih değişikliği.

        Logger orijinal kayıt PC saatinden olsa da değiştirilemeyen insert-only
        log. RxIslemTarihi sonradan elle değiştirilirse Logger sabit kalır →
        fark olur → manuel müdahale kanıtı.

        Her kayıt için beş ek bayrak hesaplanır:
        - DonusumMu: Reçete için, Logger Turu=1/AltTuru=1 anının ±3sn'sinde
          aynı LoggerMakina'da bir Turu=2/AltTuru=3 logu varsa 1.
        - AntibiyotikMu: Reçete/elden kalemlerinden en az biri ATC
          J01/J02/J04/J05 ise 1.
        - IsBankasiMu: Reçetenin RxKurumId'si Kurum.KurumAdi LIKE '%İş Bank%'
          eşleşiyorsa 1. Elden için 0.
        - BezMidir: Reçete/elden kalemlerinden en az birinin UrunAdi'nde
          'BEZ' geçiyorsa 1.
        - CezaeviMidir: Reçetenin RxKurumId'si bir cezaeviyse 1 (Kurum.
          KurumCezaeviId IS NOT NULL veya KurumAdi'nde 'CEZA'/'İNFAZ').
          Elden için 0.

        Returns:
            {
                'manuel_kayitlar': [
                    {'Kaynak','RxId','RxIslemTarihi','LoggerTarihi','FarkSn',
                     'LoggerMakina','LoggerPersonelId',
                     'DonusumMu','AntibiyotikMu','IsBankasiMu',
                     'BezMidir','CezaeviMidir'},
                    ...
                ],
                'makina_ozeti': [...],
            }
        """
        def _fmt(d):
            if hasattr(d, 'strftime'):
                if hasattr(d, 'hour'):
                    return d.strftime('%Y-%m-%d %H:%M:%S')
                return d.strftime('%Y-%m-%d') + ' 00:00:00'
            return str(d)
        bas_str = _fmt(baslangic_dt)
        bit_str = _fmt(bitis_dt)
        esik_sn_int = int(esik_sn)
        max_kayit_int = int(max_kayit)

        # 1. Manuel değişiklik kayıtları (|fark| > esik) + DonusumMu + AntibiyotikMu
        # Antibiyotik ATC prefixleri: J01* sistemik antibakteriyel,
        # J02* antifungal, J04* tüberküloz, J05* antiviral
        anti_filter = (
            "(atc.ATCKodu LIKE 'J01%' OR atc.ATCKodu LIKE 'J02%' "
            "OR atc.ATCKodu LIKE 'J04%' OR atc.ATCKodu LIKE 'J05%')"
        )
        manuel_sql = f"""
        SELECT TOP {max_kayit_int} * FROM (
            SELECT
                'RECETE' as Kaynak,
                ra.RxId,
                ra.RxIslemTarihi,
                L.LoggerTarihi,
                DATEDIFF(SECOND, L.LoggerTarihi, ra.RxIslemTarihi) as FarkSn,
                L.LoggerMakina,
                L.LoggerPersonelId,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Logger L2
                    WHERE L2.LoggerIslemTuru = 2
                      AND L2.LoggerIslemAltTuru = 3
                      AND L2.LoggerMakina = L.LoggerMakina
                      AND L2.LoggerTarihi >= DATEADD(SECOND, -3, L.LoggerTarihi)
                      AND L2.LoggerTarihi <= DATEADD(SECOND, 3, L.LoggerTarihi)
                ) THEN 1 ELSE 0 END as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ri.RIRxId = ra.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumAdi LIKE N'%İş Bank%'
                        OR k.KurumAdi LIKE N'%İŞ BANK%')
                ) THEN 1 ELSE 0 END as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    WHERE ri.RIRxId = ra.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumCezaeviId IS NOT NULL
                        OR k.KurumAdi LIKE N'%CEZA%'
                        OR k.KurumAdi LIKE N'%İNFAZ%')
                ) THEN 1 ELSE 0 END as CezaeviMidir
            FROM ReceteAna ra
            INNER JOIN Logger L
                ON L.LoggerIslemId = ra.RxId
               AND L.LoggerIslemTuru = 1
               AND L.LoggerIslemAltTuru = 1
            WHERE ra.RxSilme = 0
              AND ra.RxIslemTarihi >= ?
              AND ra.RxIslemTarihi <= ?

            UNION ALL

            SELECT
                'ELDEN' as Kaynak,
                ea.RxId,
                ea.RxIslemTarihi,
                L.LoggerTarihi,
                DATEDIFF(SECOND, L.LoggerTarihi, ea.RxIslemTarihi) as FarkSn,
                L.LoggerMakina,
                L.LoggerPersonelId,
                0 as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ei.RIRxId = ea.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                0 as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    WHERE ei.RIRxId = ea.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                0 as CezaeviMidir
            FROM EldenAna ea
            INNER JOIN Logger L
                ON L.LoggerIslemId = ea.RxId
               AND L.LoggerIslemTuru = 2
               AND L.LoggerIslemAltTuru = 1
            WHERE ea.RxSilme = 0
              AND ea.RxIslemTarihi >= ?
              AND ea.RxIslemTarihi <= ?
        ) AS T
        WHERE ABS(FarkSn) > ?
        ORDER BY ABS(FarkSn) DESC, RxIslemTarihi DESC
        """
        params = (bas_str, bit_str, bas_str, bit_str, esik_sn_int)
        manuel = self.sorgu_calistir(manuel_sql, params)

        # 2. Makina başına istatistik — Logger.LoggerMakina dağılımı + ort fark
        makina_sql = """
        SELECT
            ISNULL(L.LoggerMakina, '(BİLİNMİYOR)') as LoggerMakina,
            COUNT(*) as IslemSayisi,
            AVG(CAST(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi)) as float)) as FarkOrtalama,
            MIN(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as FarkMin,
            MAX(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as FarkMax,
            AVG(CAST(ABS(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as float)) as MutlakOrt,
            SUM(CASE WHEN ABS(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) > 5
                THEN 1 ELSE 0 END) as SuphliSayi
        FROM Logger L
        LEFT JOIN ReceteAna ra
            ON ra.RxId = L.LoggerIslemId AND L.LoggerIslemTuru = 1
        LEFT JOIN EldenAna ea
            ON ea.RxId = L.LoggerIslemId AND L.LoggerIslemTuru = 2
        WHERE L.LoggerIslemTuru IN (1, 2)
          AND L.LoggerIslemAltTuru = 1
          AND L.LoggerTarihi >= ?
          AND L.LoggerTarihi <= ?
          AND COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi) IS NOT NULL
        GROUP BY ISNULL(L.LoggerMakina, '(BİLİNMİYOR)')
        ORDER BY COUNT(*) DESC
        """
        makina = self.sorgu_calistir(makina_sql, (bas_str, bit_str))

        return {
            'manuel_kayitlar': [{
                'Kaynak': r.get('Kaynak'),
                'RxId': r.get('RxId'),
                'RxIslemTarihi': r.get('RxIslemTarihi'),
                'LoggerTarihi': r.get('LoggerTarihi'),
                'FarkSn': int(r.get('FarkSn') or 0) if r.get('FarkSn') is not None else None,
                'LoggerMakina': r.get('LoggerMakina'),
                'LoggerPersonelId': r.get('LoggerPersonelId'),
                'DonusumMu': bool(r.get('DonusumMu') or 0),
                'AntibiyotikMu': bool(r.get('AntibiyotikMu') or 0),
                'IsBankasiMu': bool(r.get('IsBankasiMu') or 0),
                'BezMidir': bool(r.get('BezMidir') or 0),
                'CezaeviMidir': bool(r.get('CezaeviMidir') or 0),
            } for r in (manuel or [])],
            'makina_ozeti': [{
                'LoggerMakina': r.get('LoggerMakina'),
                'IslemSayisi': int(r.get('IslemSayisi') or 0),
                'FarkOrtalama': float(r.get('FarkOrtalama') or 0),
                'FarkMin': int(r.get('FarkMin') or 0),
                'FarkMax': int(r.get('FarkMax') or 0),
                'MutlakOrt': float(r.get('MutlakOrt') or 0),
                'SuphliSayi': int(r.get('SuphliSayi') or 0),
            } for r in (makina or [])],
        }

    def birlesik_zaman_analizi(
        self,
        baslangic_dt,
        bitis_dt,
        kayit_esik_sn: int = 60,
        logger_esik_sn: int = 60,
        kontrol_esik_sn: int = 60,
        en_az_birinde: bool = True,
        max_kayit: int = 50000,
    ) -> Dict:
        """Üç zaman analizini tek sorguda birleştirir.

        Her reçete/elden kaydı için 3 fark hesaplanır:
        - KayitFark: RxIslemTarihi − RxKayitTarihi (saniye)
          (RxKayitTarihi DATE, saatsiz; fark gün × 86400 ölçeklenir)
        - LoggerFark: RxIslemTarihi − Logger.LoggerTarihi (saniye)
          (Logger insert-only; manuel müdahale kanıtı)
        - KontrolFark: RxKontrolTarihi − RxIslemTarihi (saniye, sadece reçete)
          (Kontrol/onay işlemden ne kadar sonra; NULL ise None döner)

        Filtreleme:
        - en_az_birinde=True (OR): herhangi bir |fark| > kendi eşiği ise dahil
        - en_az_birinde=False (AND): hepsinin |fark| > kendi eşiği ise dahil

        Her kayıt için Logger Forensik bayrakları da hesaplanır:
        DonusumMu / AntibiyotikMu / IsBankasiMu.

        Returns:
            {
                'kayitlar': [{...}, ...],
                'makina_ozeti': [...]   # Logger'a göre, manuel tarama ile aynı
            }
        """
        def _fmt(d):
            if hasattr(d, 'strftime'):
                if hasattr(d, 'hour'):
                    return d.strftime('%Y-%m-%d %H:%M:%S')
                return d.strftime('%Y-%m-%d') + ' 00:00:00'
            return str(d)
        bas_str = _fmt(baslangic_dt)
        bit_str = _fmt(bitis_dt)
        max_kayit_int = int(max_kayit)
        k_esik = int(kayit_esik_sn)
        l_esik = int(logger_esik_sn)
        c_esik = int(kontrol_esik_sn)

        anti_filter = (
            "(atc.ATCKodu LIKE 'J01%' OR atc.ATCKodu LIKE 'J02%' "
            "OR atc.ATCKodu LIKE 'J04%' OR atc.ATCKodu LIKE 'J05%')"
        )

        # KayitFark için RxKayitTarihi DATE — CAST(... AS datetime) ile saatsiz
        # toplam saniye = gün × 86400. RxIslemTarihi - RxKayitTarihi sonucu.
        # ABS değerleri WHERE'da kullanılır.
        if en_az_birinde:
            mantik_op = "OR"
        else:
            mantik_op = "AND"

        # Reçete bloğu — Kontrol da gösterilir
        # Elden bloğu — KontrolFark her zaman NULL (RxKontrolTarihi yok)
        birlesik_sql = f"""
        SELECT TOP {max_kayit_int} * FROM (
            SELECT
                'RECETE' as Kaynak,
                ra.RxId,
                ra.RxIslemTarihi,
                CAST(ra.RxKayitTarihi AS datetime) as RxKayitTarihi,
                L.LoggerTarihi,
                ra.RxKontrolTarihi,
                DATEDIFF(SECOND,
                    CAST(ra.RxKayitTarihi AS datetime), ra.RxIslemTarihi)
                    as KayitFark,
                DATEDIFF(SECOND, L.LoggerTarihi, ra.RxIslemTarihi)
                    as LoggerFark,
                CASE WHEN ra.RxKontrolTarihi IS NULL THEN NULL
                     ELSE DATEDIFF(SECOND, ra.RxIslemTarihi, ra.RxKontrolTarihi)
                END as KontrolFark,
                L.LoggerMakina,
                L.LoggerPersonelId,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Logger L2
                    WHERE L2.LoggerIslemTuru = 2
                      AND L2.LoggerIslemAltTuru = 3
                      AND L2.LoggerMakina = L.LoggerMakina
                      AND L2.LoggerTarihi >= DATEADD(SECOND, -3, L.LoggerTarihi)
                      AND L2.LoggerTarihi <= DATEADD(SECOND, 3, L.LoggerTarihi)
                ) THEN 1 ELSE 0 END as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ri.RIRxId = ra.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumAdi LIKE N'%İş Bank%'
                        OR k.KurumAdi LIKE N'%İŞ BANK%')
                ) THEN 1 ELSE 0 END as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    WHERE ri.RIRxId = ra.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumCezaeviId IS NOT NULL
                        OR k.KurumAdi LIKE N'%CEZA%'
                        OR k.KurumAdi LIKE N'%İNFAZ%')
                ) THEN 1 ELSE 0 END as CezaeviMidir
            FROM ReceteAna ra
            INNER JOIN Logger L
                ON L.LoggerIslemId = ra.RxId
               AND L.LoggerIslemTuru = 1
               AND L.LoggerIslemAltTuru = 1
            WHERE ra.RxSilme = 0
              AND ra.RxIslemTarihi >= ?
              AND ra.RxIslemTarihi <= ?

            UNION ALL

            SELECT
                'ELDEN' as Kaynak,
                ea.RxId,
                ea.RxIslemTarihi,
                CAST(ea.RxKayitTarihi AS datetime) as RxKayitTarihi,
                L.LoggerTarihi,
                CAST(NULL AS datetime) as RxKontrolTarihi,
                DATEDIFF(SECOND,
                    CAST(ea.RxKayitTarihi AS datetime), ea.RxIslemTarihi)
                    as KayitFark,
                DATEDIFF(SECOND, L.LoggerTarihi, ea.RxIslemTarihi)
                    as LoggerFark,
                CAST(NULL AS int) as KontrolFark,
                L.LoggerMakina,
                L.LoggerPersonelId,
                0 as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ei.RIRxId = ea.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                0 as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    WHERE ei.RIRxId = ea.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                0 as CezaeviMidir
            FROM EldenAna ea
            INNER JOIN Logger L
                ON L.LoggerIslemId = ea.RxId
               AND L.LoggerIslemTuru = 2
               AND L.LoggerIslemAltTuru = 1
            WHERE ea.RxSilme = 0
              AND ea.RxIslemTarihi >= ?
              AND ea.RxIslemTarihi <= ?
        ) AS T
        WHERE
            ABS(ISNULL(KayitFark, 0)) > {k_esik} {mantik_op}
            ABS(ISNULL(LoggerFark, 0)) > {l_esik} {mantik_op}
            (KontrolFark IS NOT NULL
              AND ABS(KontrolFark) > {c_esik})
        ORDER BY
            ABS(ISNULL(LoggerFark, 0)) DESC,
            ABS(ISNULL(KayitFark, 0)) DESC,
            RxIslemTarihi DESC
        """
        params = (bas_str, bit_str, bas_str, bit_str)
        kayitlar = self.sorgu_calistir(birlesik_sql, params)

        # Makina özeti — Logger Forensik ile aynı
        makina_sql = """
        SELECT
            ISNULL(L.LoggerMakina, '(BİLİNMİYOR)') as LoggerMakina,
            COUNT(*) as IslemSayisi,
            AVG(CAST(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi)) as float)) as FarkOrtalama,
            MIN(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as FarkMin,
            MAX(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as FarkMax,
            AVG(CAST(ABS(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) as float)) as MutlakOrt,
            SUM(CASE WHEN ABS(DATEDIFF(SECOND, L.LoggerTarihi,
                COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi))) > 5
                THEN 1 ELSE 0 END) as SuphliSayi
        FROM Logger L
        LEFT JOIN ReceteAna ra
            ON ra.RxId = L.LoggerIslemId AND L.LoggerIslemTuru = 1
        LEFT JOIN EldenAna ea
            ON ea.RxId = L.LoggerIslemId AND L.LoggerIslemTuru = 2
        WHERE L.LoggerIslemTuru IN (1, 2)
          AND L.LoggerIslemAltTuru = 1
          AND L.LoggerTarihi >= ?
          AND L.LoggerTarihi <= ?
          AND COALESCE(ra.RxIslemTarihi, ea.RxIslemTarihi) IS NOT NULL
        GROUP BY ISNULL(L.LoggerMakina, '(BİLİNMİYOR)')
        ORDER BY COUNT(*) DESC
        """
        makina = self.sorgu_calistir(makina_sql, (bas_str, bit_str))

        def _i(v):
            return int(v) if v is not None else None

        return {
            'kayitlar': [{
                'Kaynak': r.get('Kaynak'),
                'RxId': r.get('RxId'),
                'RxIslemTarihi': r.get('RxIslemTarihi'),
                'RxKayitTarihi': r.get('RxKayitTarihi'),
                'LoggerTarihi': r.get('LoggerTarihi'),
                'RxKontrolTarihi': r.get('RxKontrolTarihi'),
                'KayitFark': _i(r.get('KayitFark')),
                'LoggerFark': _i(r.get('LoggerFark')),
                'KontrolFark': _i(r.get('KontrolFark')),
                'LoggerMakina': r.get('LoggerMakina'),
                'LoggerPersonelId': r.get('LoggerPersonelId'),
                'DonusumMu': bool(r.get('DonusumMu') or 0),
                'AntibiyotikMu': bool(r.get('AntibiyotikMu') or 0),
                'IsBankasiMu': bool(r.get('IsBankasiMu') or 0),
                'BezMidir': bool(r.get('BezMidir') or 0),
                'CezaeviMidir': bool(r.get('CezaeviMidir') or 0),
            } for r in (kayitlar or [])],
            'makina_ozeti': [{
                'LoggerMakina': r.get('LoggerMakina'),
                'IslemSayisi': int(r.get('IslemSayisi') or 0),
                'FarkOrtalama': float(r.get('FarkOrtalama') or 0),
                'FarkMin': int(r.get('FarkMin') or 0),
                'FarkMax': int(r.get('FarkMax') or 0),
                'MutlakOrt': float(r.get('MutlakOrt') or 0),
                'SuphliSayi': int(r.get('SuphliSayi') or 0),
            } for r in (makina or [])],
        }

    def logger_yapisini_incele(self) -> Dict:
        """Logger tablosunun detaylı incelemesi — cross-check yazımı için.

        Returns:
            {
                'kolonlar': [...],
                'islem_turu_dagilimi': [(IslemTuru, AltTuru, sayı), ...],
                'ornek_recete_eslesme': [...],  # bir RxId'nin Logger'da
                                                  # bulunan kayıtları
                'ornek_elden_eslesme': [...],
            }
        """
        sonuc = {}

        # 1. Logger kolonları
        kol_sql = """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'Logger'
            ORDER BY ORDINAL_POSITION
        """
        sonuc['kolonlar'] = self.sorgu_calistir(kol_sql)

        # 2. LoggerIslemTuru + LoggerIslemAltTuru dağılımı (TOP 20)
        try:
            dag_sql = """
                SELECT TOP 20
                    LoggerIslemTuru,
                    LoggerIslemAltTuru,
                    COUNT(*) as Sayi
                FROM Logger
                GROUP BY LoggerIslemTuru, LoggerIslemAltTuru
                ORDER BY Sayi DESC
            """
            sonuc['islem_turu_dagilimi'] = self.sorgu_calistir(dag_sql)
        except Exception as e:
            sonuc['islem_turu_dagilimi'] = []
            sonuc['dagilim_hata'] = str(e)

        # 3. Son bir reçetenin (RxId) Logger'da eşleşmesi
        try:
            son_recete_sql = """
                SELECT TOP 1 RxId, RxIslemTarihi
                FROM ReceteAna
                WHERE RxSilme = 0
                ORDER BY RxId DESC
            """
            sr = self.sorgu_calistir(son_recete_sql)
            if sr:
                rx_id = sr[0].get('RxId')
                sonuc['ornek_recete_rxid'] = rx_id
                sonuc['ornek_recete_islem'] = sr[0].get('RxIslemTarihi')
                # Logger'da bu RxId ile eşleşen satırlar (LoggerId veya başka)
                eslesme_sql = f"""
                    SELECT TOP 10 *
                    FROM Logger
                    WHERE LoggerId = {int(rx_id)}
                       OR LoggerIslemId = {int(rx_id)}
                    ORDER BY LoggerTarihi DESC
                """
                sonuc['ornek_recete_eslesme'] = self.sorgu_calistir(eslesme_sql)
        except Exception as e:
            sonuc['ornek_recete_eslesme'] = []
            sonuc['recete_hata'] = str(e)

        # 4. Son bir elden satışın Logger'da eşleşmesi
        try:
            son_elden_sql = """
                SELECT TOP 1 RxId, RxIslemTarihi
                FROM EldenAna
                WHERE RxSilme = 0
                ORDER BY RxId DESC
            """
            se = self.sorgu_calistir(son_elden_sql)
            if se:
                rx_id_e = se[0].get('RxId')
                sonuc['ornek_elden_rxid'] = rx_id_e
                sonuc['ornek_elden_islem'] = se[0].get('RxIslemTarihi')
                eslesme_sql = f"""
                    SELECT TOP 10 *
                    FROM Logger
                    WHERE LoggerId = {int(rx_id_e)}
                       OR LoggerIslemId = {int(rx_id_e)}
                    ORDER BY LoggerTarihi DESC
                """
                sonuc['ornek_elden_eslesme'] = self.sorgu_calistir(eslesme_sql)
        except Exception as e:
            sonuc['ornek_elden_eslesme'] = []
            sonuc['elden_hata'] = str(e)

        return sonuc

    def log_tablo_analizi(self, tablo_isimleri: Optional[List[str]] = None) -> Dict:
        """Verilen log tablolarının yapısını + örnek satırlarını döker.
        Amaç: log tablolarında SUNUCU-tarafı insert zamanı (trigger yazımı vb)
        var mı yoksa uygulama tarafından mı yazılıyor netleştirmek.

        Args:
            tablo_isimleri: incelenecek tablolar. None ise default 4 tablo:
                ['BotanikLog', 'Logger', 'ReceteHesapLog', 'MedulaDokumLog']

        Returns:
            {tablo_adi: {
                'kolonlar': [{'COLUMN_NAME','DATA_TYPE','COLUMN_DEFAULT'}],
                'satir_sayisi': int,
                'ornekler': [{kolon: değer}, ...],  # TOP 5 son satır
                'trigger_var_mi': bool,
                'triggerlar': [trigger adı listesi],
                'hata': str | None,
            }, ...}
        """
        if not tablo_isimleri:
            tablo_isimleri = ['BotanikLog', 'Logger', 'ReceteHesapLog',
                              'MedulaDokumLog']

        sonuc = {}
        for tablo in tablo_isimleri:
            tablo_sonuc = {
                'kolonlar': [], 'satir_sayisi': None,
                'ornekler': [], 'trigger_var_mi': False,
                'triggerlar': [], 'hata': None,
            }
            # 1. Kolon yapısı + default değerler
            kol_sql = """
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_DEFAULT, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            kolonlar = self.sorgu_calistir(kol_sql, (tablo,))
            if not kolonlar:
                tablo_sonuc['hata'] = f"Tablo bulunamadı: {tablo}"
                sonuc[tablo] = tablo_sonuc
                continue
            tablo_sonuc['kolonlar'] = kolonlar

            # 2. Satır sayısı (hızlı yaklaşık — sys.partitions)
            try:
                say_sql = """
                    SELECT SUM(p.row_count) as Sayi
                    FROM sys.dm_db_partition_stats p
                    WHERE p.object_id = OBJECT_ID(?)
                      AND p.index_id < 2
                """
                say = self.sorgu_calistir(say_sql, (tablo,))
                if say and say[0].get('Sayi') is not None:
                    tablo_sonuc['satir_sayisi'] = int(say[0].get('Sayi'))
            except Exception:
                pass

            # 3. Triggerlar (INSERT trigger varsa sunucu tarafı insert zaman
            #    yazımı yapıyor olabilir)
            trig_sql = """
                SELECT t.name as TriggerAdi, t.is_disabled,
                       OBJECT_DEFINITION(t.object_id) as Tanim
                FROM sys.triggers t
                JOIN sys.objects o ON t.parent_id = o.object_id
                WHERE o.name = ?
            """
            try:
                triglar = self.sorgu_calistir(trig_sql, (tablo,))
                if triglar:
                    tablo_sonuc['trigger_var_mi'] = True
                    tablo_sonuc['triggerlar'] = triglar
            except Exception:
                pass

            # 4. TOP 5 örnek satır — varsa identity kolona göre azalan
            ident_kol = None
            for k in kolonlar:
                if str(k.get('DATA_TYPE') or '').lower() in ('int', 'bigint'):
                    n = (k.get('COLUMN_NAME') or '').lower()
                    if n.endswith('id') or n == 'id':
                        ident_kol = k.get('COLUMN_NAME')
                        break
            try:
                if ident_kol:
                    ornek_sql = (f"SELECT TOP 5 * FROM [{tablo}] "
                                  f"ORDER BY [{ident_kol}] DESC")
                else:
                    ornek_sql = f"SELECT TOP 5 * FROM [{tablo}]"
                tablo_sonuc['ornekler'] = self.sorgu_calistir(ornek_sql)
            except Exception as e:
                tablo_sonuc['hata'] = (tablo_sonuc['hata'] or '') + f" örnek hata: {e}"

            sonuc[tablo] = tablo_sonuc

        return sonuc

    def tek_kayit_zaman_dokumu(self, kaynak: str, rx_id) -> Dict:
        """Tek bir satışın TÜM zaman/tarih alanlarını + sunucu saati + PC saati
        döker. Bir kayıtla ilgili çakışan tarihlerin (kayıt/işlem/kontrol/...)
        karşılaştırılması için kullanılır.

        Returns:
            {
                'kaynak': 'RECETE' | 'ELDEN',
                'rx_id': int,
                'tablo_adi': str,
                'kolonlar': [{'COLUMN_NAME', 'DATA_TYPE'}, ...],  # zaman içeren kolonlar
                'degerler': {kolon_adi: değer, ...},  # her kolonun bu kayıttaki değeri
                'sunucu_now': datetime,  # SQL Server şu anki saat
                'sunucu_now_utc': datetime,
                'pc_now': datetime,  # Python (PC) şu anki saat
                'pc_now_utc': datetime,
                'hata': str | None,
            }
        """
        kaynak = (kaynak or '').upper().strip()
        if kaynak not in ('RECETE', 'ELDEN'):
            return {'hata': f"Geçersiz kaynak: {kaynak}"}
        try:
            rx_id_int = int(rx_id)
        except (TypeError, ValueError):
            return {'hata': f"Geçersiz rx_id: {rx_id!r}"}

        tablo = 'ReceteAna' if kaynak == 'RECETE' else 'EldenAna'

        # 1. Zaman kolonlarını bul
        kol_sql = """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
              AND (
                DATA_TYPE IN ('date', 'datetime', 'datetime2',
                              'datetimeoffset', 'smalldatetime', 'time')
                OR COLUMN_NAME LIKE '%Tarih%'
                OR COLUMN_NAME LIKE '%Saat%'
                OR COLUMN_NAME LIKE '%Zaman%'
              )
            ORDER BY ORDINAL_POSITION
        """
        kolonlar = self.sorgu_calistir(kol_sql, (tablo,))
        if not kolonlar:
            return {
                'kaynak': kaynak, 'rx_id': rx_id_int, 'tablo_adi': tablo,
                'kolonlar': [], 'degerler': None,
                'hata': f"{tablo} tablosunda zaman kolonu bulunamadı",
            }

        # 2. Bu kolonları + sunucu zamanını tek sorguyla çek
        kol_listesi = ", ".join(f"[{k['COLUMN_NAME']}]" for k in kolonlar)
        veri_sql = f"""
            SELECT
                {kol_listesi},
                SYSDATETIME() as _SunucuSysdatetime,
                GETDATE() as _SunucuGetdate,
                GETUTCDATE() as _SunucuUtc
            FROM {tablo}
            WHERE RxId = ?
        """
        rows = self.sorgu_calistir(veri_sql, (rx_id_int,))
        pc_now = datetime.now()
        pc_now_utc = datetime.utcnow()

        if not rows:
            return {
                'kaynak': kaynak, 'rx_id': rx_id_int, 'tablo_adi': tablo,
                'kolonlar': kolonlar, 'degerler': None,
                'sunucu_now': None, 'sunucu_now_utc': None,
                'pc_now': pc_now, 'pc_now_utc': pc_now_utc,
                'hata': f"{tablo}.RxId={rx_id_int} bulunamadı",
            }

        row = dict(rows[0])
        sunucu_now = row.pop('_SunucuSysdatetime', None)
        sunucu_get = row.pop('_SunucuGetdate', None)
        sunucu_utc = row.pop('_SunucuUtc', None)

        return {
            'kaynak': kaynak, 'rx_id': rx_id_int, 'tablo_adi': tablo,
            'kolonlar': kolonlar,
            'degerler': row,  # sadece kayıttaki zaman alanları
            'sunucu_now': sunucu_now,
            'sunucu_now_getdate': sunucu_get,
            'sunucu_now_utc': sunucu_utc,
            'pc_now': pc_now,
            'pc_now_utc': pc_now_utc,
            'hata': None,
        }

    def zaman_anomali_tarama(
        self,
        baslangic_dt,
        bitis_dt,
        esik_sn: int = 600,
        max_kayit: int = 200000,
    ) -> List[Dict]:
        """Geniş zaman aralığında RxIslemTarihi vs RxKayitTarihi farkı eşik
        üstündeki TÜM satışları DB seviyesinde filtreler.

        Hassasiyet:
        - Kayıt saatli ise → fark = saniye bazlı (DATEDIFF(SECOND, ...))
        - Kayıt saatsiz ise (saat=00:00:00) → işlem saatini de yok say,
          fark = gün bazlı × 86400 (eşik ile karşılaştırma için saniyeye çevrildi)
          Aynı gün ise FarkSn=0 → eşik altında → anomali değil
          1 gün sonra ise FarkSn=86400 → eşik üstü → anomali

        Args:
            baslangic_dt, bitis_dt: RxIslemTarihi filtresi (date veya datetime)
            esik_sn: pozitif fark için eşik (sn). |fark| > esik_sn VEYA fark < 0
                    olan kayıtlar dönecek. Varsayılan 600 (10 dk).
            max_kayit: güvenlik üst sınırı (DB ezilmesin)

        Returns:
            [{'Kaynak','RxId','IslemTarihi','KayitTarihi','FarkSn','FarkTipi'},
              ...]. FarkTipi='sn' veya 'gun'. FarkSn'e göre azalan (|fark|)
            sıralı.
        """
        def _fmt(d):
            if hasattr(d, 'strftime'):
                if hasattr(d, 'hour'):
                    return d.strftime('%Y-%m-%d %H:%M:%S')
                return d.strftime('%Y-%m-%d') + ' 00:00:00'
            return str(d)
        bas_str = _fmt(baslangic_dt)
        bit_str = _fmt(bitis_dt)
        esik_sn_int = int(esik_sn)
        max_kayit_int = int(max_kayit)

        # ÇİFT KARŞILAŞTIRMA + 4 BAYRAK (Logger Forensik ile aynı semantik):
        # - FarkSn = RxIslemTarihi vs RxKayitTarihi (kayıt DATE olduğu için
        #   gün-bazlı * 86400 olarak normalize)
        # - KontrolFarkSn = RxIslemTarihi vs RxKontrolTarihi (saniye, reçete)
        # - DonusumMu: Logger Turu=1/AltTuru=1 ±3sn + aynı PC'de Turu=2/AltTuru=3
        # - AntibiyotikMu: ReceteIlaclari/EldenIlaclari'nda ATC J01/J02/J04/J05
        # - IsBankasiMu: RxKurumId → Kurum.KurumAdi LIKE '%İş Bank%' (reçete)
        # - BezMidir: ReceteIlaclari/EldenIlaclari'nda UrunAdi LIKE '%BEZ%'
        anti_filter = (
            "(atc.ATCKodu LIKE 'J01%' OR atc.ATCKodu LIKE 'J02%' "
            "OR atc.ATCKodu LIKE 'J04%' OR atc.ATCKodu LIKE 'J05%')"
        )
        sql = f"""
        SELECT TOP {max_kayit_int} * FROM (
            SELECT
                'RECETE' as Kaynak,
                ra.RxId as RxId,
                ra.RxIslemTarihi as IslemTarihi,
                ra.RxKayitTarihi as KayitTarihi,
                ra.RxKontrolTarihi as KontrolTarihi,
                CASE
                    WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                    THEN CAST(DATEDIFF(DAY,
                            CAST(ra.RxIslemTarihi as DATE),
                            CAST(ra.RxKayitTarihi as DATE)) as BIGINT) * 86400
                    ELSE DATEDIFF(SECOND, ra.RxIslemTarihi, ra.RxKayitTarihi)
                END as FarkSn,
                CASE
                    WHEN DATEPART(HOUR, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(MINUTE, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(SECOND, CAST(ra.RxKayitTarihi as DATETIME)) = 0
                    THEN 'gun'
                    ELSE 'sn'
                END as FarkTipi,
                CASE WHEN ra.RxKontrolTarihi IS NULL THEN NULL
                     ELSE DATEDIFF(SECOND, ra.RxIslemTarihi, ra.RxKontrolTarihi)
                END as KontrolFarkSn,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Logger L1
                    INNER JOIN Logger L2
                        ON L2.LoggerIslemTuru = 2 AND L2.LoggerIslemAltTuru = 3
                       AND L2.LoggerMakina = L1.LoggerMakina
                       AND L2.LoggerTarihi >= DATEADD(SECOND, -3, L1.LoggerTarihi)
                       AND L2.LoggerTarihi <= DATEADD(SECOND, 3, L1.LoggerTarihi)
                    WHERE L1.LoggerIslemId = ra.RxId
                      AND L1.LoggerIslemTuru = 1
                      AND L1.LoggerIslemAltTuru = 1
                ) THEN 1 ELSE 0 END as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ri.RIRxId = ra.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumAdi LIKE N'%İş Bank%'
                        OR k.KurumAdi LIKE N'%İŞ BANK%')
                ) THEN 1 ELSE 0 END as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM ReceteIlaclari ri
                    INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
                    WHERE ri.RIRxId = ra.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                CASE WHEN EXISTS (
                    SELECT 1 FROM Kurum k
                    WHERE k.KurumId = ra.RxKurumId
                      AND (k.KurumCezaeviId IS NOT NULL
                        OR k.KurumAdi LIKE N'%CEZA%'
                        OR k.KurumAdi LIKE N'%İNFAZ%')
                ) THEN 1 ELSE 0 END as CezaeviMidir
            FROM ReceteAna ra
            WHERE ra.RxSilme = 0
                AND ra.RxIslemTarihi >= ?
                AND ra.RxIslemTarihi <= ?
                AND ra.RxKayitTarihi IS NOT NULL

            UNION ALL

            SELECT
                'ELDEN' as Kaynak,
                ea.RxId as RxId,
                ea.RxIslemTarihi as IslemTarihi,
                ea.RxKayitTarihi as KayitTarihi,
                NULL as KontrolTarihi,
                CASE
                    WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                    THEN CAST(DATEDIFF(DAY,
                            CAST(ea.RxIslemTarihi as DATE),
                            CAST(ea.RxKayitTarihi as DATE)) as BIGINT) * 86400
                    ELSE DATEDIFF(SECOND, ea.RxIslemTarihi, ea.RxKayitTarihi)
                END as FarkSn,
                CASE
                    WHEN DATEPART(HOUR, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(MINUTE, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                         AND DATEPART(SECOND, CAST(ea.RxKayitTarihi as DATETIME)) = 0
                    THEN 'gun'
                    ELSE 'sn'
                END as FarkTipi,
                CAST(NULL as BIGINT) as KontrolFarkSn,
                0 as DonusumMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    INNER JOIN ATC atc ON atc.ATCId = u.UrunATCId
                    WHERE ei.RIRxId = ea.RxId AND {anti_filter}
                ) THEN 1 ELSE 0 END as AntibiyotikMu,
                0 as IsBankasiMu,
                CASE WHEN EXISTS (
                    SELECT 1 FROM EldenIlaclari ei
                    INNER JOIN Urun u ON u.UrunId = ei.RIUrunId
                    WHERE ei.RIRxId = ea.RxId AND u.UrunAdi LIKE N'%BEZ%'
                ) THEN 1 ELSE 0 END as BezMidir,
                0 as CezaeviMidir
            FROM EldenAna ea
            WHERE ea.RxSilme = 0
                AND ea.RxIslemTarihi >= ?
                AND ea.RxIslemTarihi <= ?
                AND ea.RxKayitTarihi IS NOT NULL
        ) AS T
        WHERE FarkSn < 0 OR FarkSn > ?
           OR (KontrolFarkSn IS NOT NULL
               AND (KontrolFarkSn < 0 OR KontrolFarkSn > ?))
        ORDER BY ABS(FarkSn) DESC,
                 ABS(ISNULL(KontrolFarkSn, 0)) DESC,
                 IslemTarihi DESC
        """
        params = (bas_str, bit_str, bas_str, bit_str, esik_sn_int, esik_sn_int)
        sonuclar = self.sorgu_calistir(sql, params)
        return [{
            'Kaynak': r.get('Kaynak'),
            'RxId': r.get('RxId'),
            'IslemTarihi': r.get('IslemTarihi'),
            'KayitTarihi': r.get('KayitTarihi'),
            'KontrolTarihi': r.get('KontrolTarihi'),
            'FarkSn': int(r.get('FarkSn') or 0) if r.get('FarkSn') is not None else None,
            'FarkTipi': r.get('FarkTipi') or 'sn',
            'KontrolFarkSn': int(r.get('KontrolFarkSn')) if r.get('KontrolFarkSn') is not None else None,
            'DonusumMu': bool(r.get('DonusumMu') or 0),
            'AntibiyotikMu': bool(r.get('AntibiyotikMu') or 0),
            'IsBankasiMu': bool(r.get('IsBankasiMu') or 0),
            'BezMidir': bool(r.get('BezMidir') or 0),
            'CezaeviMidir': bool(r.get('CezaeviMidir') or 0),
        } for r in sonuclar]

    def gun_saat_yogunlugu_getir(
        self,
        baslangic_tarih,
        bitis_tarih,
    ) -> List[Dict]:
        """Bir tarih aralığında günlük saat dağılımı (anomali kıyas için).

        Returns:
            [{'Tarih'(date), 'Saat'(int), 'SatisSayisi'(int)}, ...]
        """
        def _fmt(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)
        bas_str = _fmt(baslangic_tarih)
        bit_str = _fmt(bitis_tarih)

        sql = """
        SELECT
            CAST(IslemTarihi as date) as Tarih,
            DATEPART(hour, IslemTarihi) as Saat,
            COUNT(*) as SatisSayisi
        FROM (
            SELECT ra.RxIslemTarihi as IslemTarihi
            FROM ReceteAna ra
            WHERE ra.RxSilme = 0
                AND ra.RxIslemTarihi >= ?
                AND ra.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))
            UNION ALL
            SELECT ea.RxIslemTarihi
            FROM EldenAna ea
            WHERE ea.RxSilme = 0
                AND ea.RxIslemTarihi >= ?
                AND ea.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))
        ) T
        GROUP BY CAST(IslemTarihi as date), DATEPART(hour, IslemTarihi)
        ORDER BY Tarih, Saat
        """
        sonuclar = self.sorgu_calistir(sql, (bas_str, bit_str, bas_str, bit_str))
        return [{
            'Tarih': r.get('Tarih'),
            'Saat': int(r.get('Saat') or 0),
            'SatisSayisi': int(r.get('SatisSayisi') or 0),
        } for r in sonuclar]

    def satis_kalem_detayi_getir(
        self,
        baslangic_dt,
        bitis_dt,
        kirilim: str = 'tumu',
        kurum_id: Optional[int] = None,
    ) -> List[Dict]:
        """Datetime aralığında her satış KALEMİ için tam detay döner.

        Her ilaç kalemi ayrı satır — hasta + doktor + kurum + ürün + adet + fiyat.
        satis_zaman_detay_getir'den farkı: bu kalem bazlı (RxIlaci satırı),
        diğeri satış (RxId) bazlı.

        Args:
            baslangic_dt, bitis_dt: datetime (saat+dakika+saniye dahil) veya 'YYYY-MM-DD HH:MM:SS'
            kirilim: 'tumu'|'recete'|'elden'|'kurum'

        Returns:
            [{'Kaynak', 'RxId', 'IslemTarihi', 'HastaAdi', 'DoktorAdi',
              'KurumAdi', 'TesisAdi', 'UrunAdi', 'Adet', 'BirimFiyat', 'Tutar'}, ...]
        """
        if kirilim not in ('tumu', 'recete', 'elden', 'kurum'):
            raise ValueError(f"Geçersiz kırılım: {kirilim}")

        # datetime → string
        def _fmt(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d %H:%M:%S')
            return str(d)
        bas_str = _fmt(baslangic_dt)
        bit_str = _fmt(bitis_dt)

        recete_aktif = kirilim in ('tumu', 'recete', 'kurum')
        elden_aktif = kirilim in ('tumu', 'elden')

        kurum_filtre = ""
        if kirilim in ('kurum', 'recete') and kurum_id is not None:
            kurum_filtre = f" AND ra.RxKurumId = {int(kurum_id)} "

        # Reçeteli: her kalem için doktor + hasta + kurum + ürün
        recete_blok = """
            SELECT
                'RECETE' as Kaynak,
                ra.RxId as RxId,
                ra.RxIslemTarihi as IslemTarihi,
                m.MusteriAdiSoyadi as HastaAdi,
                COALESCE(dok.DoktorAdiSoyadi,
                         ISNULL(dok.DoktorAdi, '') + ' ' + ISNULL(dok.DoktorSoyadi, '')) as DoktorAdi,
                k.KurumAdi as KurumAdi,
                h.HastaneAdi as TesisAdi,
                u.UrunAdi as UrunAdi,
                ri.RIAdet as Adet,
                ri.RIEtiketFiyati as BirimFiyat,
                ri.RIToplam as Tutar
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
            JOIN Urun u ON ri.RIUrunId = u.UrunId
            LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
            LEFT JOIN Doktor dok ON ra.RxDoktorId = dok.DoktorId
            LEFT JOIN Hastane h ON ra.RxHastaneId = h.HastaneId
            LEFT JOIN Kurum k ON ra.RxKurumId = k.KurumId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
                AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                AND ra.RxIslemTarihi >= ?
                AND ra.RxIslemTarihi <= ?
        """ + kurum_filtre

        # Elden: doktor/kurum yok
        elden_blok = """
            SELECT
                'ELDEN' as Kaynak,
                ea.RxId as RxId,
                ea.RxIslemTarihi as IslemTarihi,
                m.MusteriAdiSoyadi as HastaAdi,
                NULL as DoktorAdi,
                NULL as KurumAdi,
                NULL as TesisAdi,
                u.UrunAdi as UrunAdi,
                ei.RIAdet as Adet,
                ei.RIEtiketFiyati as BirimFiyat,
                ei.RIToplam as Tutar
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
            JOIN Urun u ON ei.RIUrunId = u.UrunId
            LEFT JOIN Musteri m ON ea.RxMusteriId = m.MusteriId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
                AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                AND ea.RxIslemTarihi >= ?
                AND ea.RxIslemTarihi <= ?
        """

        bloklar = []
        params = []
        if recete_aktif:
            bloklar.append(recete_blok)
            params.extend([bas_str, bit_str])
        if elden_aktif:
            bloklar.append(elden_blok)
            params.extend([bas_str, bit_str])

        if not bloklar:
            return []

        sql = "\nUNION ALL\n".join(bloklar) + "\nORDER BY IslemTarihi, RxId"
        sonuclar = self.sorgu_calistir(sql, tuple(params))

        temiz = []
        for r in sonuclar:
            temiz.append({
                'Kaynak': r.get('Kaynak'),
                'RxId': r.get('RxId'),
                'IslemTarihi': r.get('IslemTarihi'),
                'HastaAdi': r.get('HastaAdi') or '',
                'DoktorAdi': (r.get('DoktorAdi') or '').strip(),
                'KurumAdi': r.get('KurumAdi') or '',
                'TesisAdi': r.get('TesisAdi') or '',
                'UrunAdi': r.get('UrunAdi') or '',
                'Adet': float(r.get('Adet') or 0),
                'BirimFiyat': float(r.get('BirimFiyat') or 0),
                'Tutar': float(r.get('Tutar') or 0),
            })
        return temiz

    def satis_zaman_detay_getir(
        self,
        baslangic_tarih,
        bitis_tarih,
        kirilim: str = 'tumu',
        kurum_id: Optional[int] = None,
    ) -> List[Dict]:
        """Her satışın zaman detayını (RxIslemTarihi datetime) döndürür.

        Args:
            baslangic_tarih, bitis_tarih: date veya datetime (saat dahil).
              datetime ise SQL'de SAAT BAZINDA filtre (çok daha dar pencere).
              date ise: bas 00:00:00 → bit ertesi gun 00:00:00 (eski davranış).

        Returns:
            [{'kaynak', 'rx_id', 'tarih', 'kalem_sayisi', 'adet', 'tutar'}, ...]
        """
        if kirilim not in ('tumu', 'recete', 'elden', 'kurum'):
            raise ValueError(f"Geçersiz kırılım: {kirilim}")
        if kirilim == 'kurum' and kurum_id is None:
            raise ValueError("kırılım='kurum' için kurum_id zorunlu")

        # datetime ise saat-bazlı filtre (dar pencere, hızlı sorgu)
        # date ise gun bazlı (eski davranış, geniş pencere)
        from datetime import datetime as _dt
        is_datetime_bas = isinstance(baslangic_tarih, _dt)
        is_datetime_bit = isinstance(bitis_tarih, _dt)

        if is_datetime_bas:
            bas_str = baslangic_tarih.strftime('%Y-%m-%d %H:%M:%S')
        elif hasattr(baslangic_tarih, 'strftime'):
            bas_str = baslangic_tarih.strftime('%Y-%m-%d') + ' 00:00:00'
        else:
            bas_str = str(baslangic_tarih)

        if is_datetime_bit:
            bit_str = bitis_tarih.strftime('%Y-%m-%d %H:%M:%S')
            bit_filtre = "AND ra.RxIslemTarihi <= ?"
            bit_filtre_elden = "AND ea.RxIslemTarihi <= ?"
        elif hasattr(bitis_tarih, 'strftime'):
            # Tarih ise: ertesi günün 00:00'ı (eski davranış)
            bit_str = bitis_tarih.strftime('%Y-%m-%d')
            bit_filtre = "AND ra.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))"
            bit_filtre_elden = "AND ea.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))"
        else:
            bit_str = str(bitis_tarih)
            bit_filtre = "AND ra.RxIslemTarihi <= ?"
            bit_filtre_elden = "AND ea.RxIslemTarihi <= ?"

        recete_aktif = kirilim in ('tumu', 'recete', 'kurum')
        elden_aktif = kirilim in ('tumu', 'elden')

        kurum_filtre = ""
        if kirilim == 'kurum' and kurum_id is not None:
            kurum_filtre = f" AND ra.RxKurumId = {int(kurum_id)} "
        elif kirilim == 'recete' and kurum_id is not None:
            kurum_filtre = f" AND ra.RxKurumId = {int(kurum_id)} "

        # Reçete: kalemleri reçete bazında topla (kalem sayısı + kutu + tutar)
        recete_blok = f"""
            SELECT
                'RECETE' as Kaynak,
                ra.RxId as RxId,
                ra.RxIslemTarihi as Tarih,
                COUNT(*) as KalemSayisi,
                SUM(ri.RIAdet) as Adet,
                SUM(ri.RIToplam) as Tutar
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
                AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                AND ra.RxIslemTarihi >= ?
                {bit_filtre}
        """ + kurum_filtre + """
            GROUP BY ra.RxId, ra.RxIslemTarihi
        """

        elden_blok = f"""
            SELECT
                'ELDEN' as Kaynak,
                ea.RxId as RxId,
                ea.RxIslemTarihi as Tarih,
                COUNT(*) as KalemSayisi,
                SUM(ei.RIAdet) as Adet,
                SUM(ei.RIToplam) as Tutar
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
                AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                AND ea.RxIslemTarihi >= ?
                {bit_filtre_elden}
            GROUP BY ea.RxId, ea.RxIslemTarihi
        """

        kaynak_bloklari = []
        params = []
        if recete_aktif:
            kaynak_bloklari.append(recete_blok)
            params.extend([bas_str, bit_str])
        if elden_aktif:
            kaynak_bloklari.append(elden_blok)
            params.extend([bas_str, bit_str])

        if not kaynak_bloklari:
            return []

        sql = "\nUNION ALL\n".join(kaynak_bloklari) + "\nORDER BY Tarih"

        sonuclar = self.sorgu_calistir(sql, tuple(params))

        temiz = []
        for r in sonuclar:
            dt = r.get('Tarih')
            if hasattr(dt, 'date') and not hasattr(dt, 'hour'):
                continue
            temiz.append({
                'kaynak': r.get('Kaynak'),
                'rx_id': r.get('RxId'),
                'tarih': dt,
                'kalem_sayisi': int(r.get('KalemSayisi') or 0),
                'adet': float(r.get('Adet') or 0),
                'tutar': float(r.get('Tutar') or 0),
            })
        return temiz

    def satis_kalem_detay_getir(self, kaynak: str, rx_id) -> Dict:
        """Tek bir satışın (RECETE veya ELDEN) tam detayını döndür.

        Args:
            kaynak: 'RECETE' veya 'ELDEN'
            rx_id: RxId değeri (int)

        Returns:
            {
                'baslik': {...},   # üst bilgiler (hasta, doktor, hastane, kurum, ...)
                'kalemler': [...], # ilaç satırları (barkod, ad, adet, fiyatlar, ...)
            }
            Bulunamazsa baslik=None, kalemler=[].
        """
        try:
            rx_id_int = int(rx_id)
        except (TypeError, ValueError):
            return {'baslik': None, 'kalemler': []}

        kaynak = (kaynak or '').upper().strip()
        if kaynak not in ('RECETE', 'ELDEN'):
            return {'baslik': None, 'kalemler': []}

        if kaynak == 'RECETE':
            # Sadece bu repo'da kullanıldığı doğrulanmış kolonlar.
            # (RxBelgeNo/RxToplam/RxKatilimPayi/RxTeshis/RxAciklama/DoktorBranj
            #  ReceteAna/Doktor tablosunda olmayabilir → sorgu sessizce 0 satır
            #  döndürüyordu.) Toplam, kalemlerden hesaplanacak.
            baslik_sql = """
                SELECT
                    ra.RxId,
                    ra.RxIslemTarihi,
                    ra.RxKayitTarihi,
                    ra.RxReceteTarihi,
                    ra.RxEReceteNo,
                    m.MusteriAdiSoyadi as HastaAdi,
                    m.MusteriTCKN as HastaTCKN,
                    COALESCE(
                        dok.DoktorAdiSoyadi,
                        dok.DoktorAdi + ' ' + ISNULL(dok.DoktorSoyadi, '')
                    ) as DoktorAdi,
                    h.HastaneAdi as TesisAdi,
                    k.KurumAdi as KurumAdi
                FROM ReceteAna ra
                LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
                LEFT JOIN Doktor dok ON ra.RxDoktorId = dok.DoktorId
                LEFT JOIN Hastane h ON ra.RxHastaneId = h.HastaneId
                LEFT JOIN Kurum k ON ra.RxKurumId = k.KurumId
                WHERE ra.RxId = ? AND ra.RxSilme = 0
            """
            kalem_sql = """
                SELECT
                    ri.RIId,
                    ri.RIUrunId as UrunId,
                    u.UrunAdi,
                    (SELECT TOP 1 b.BarkodAdi FROM Barkod b
                        WHERE b.BarkodUrunId = u.UrunId
                        ORDER BY b.BarkodSilme ASC) as Barkod,
                    ri.RIAdet as Adet,
                    ri.RIEtiketFiyati as EtiketFiyat,
                    ri.RIKurumFiyati as KurumFiyat,
                    ri.RIFiyatFarki as FiyatFarki,
                    ri.RIIskonto as Iskonto,
                    ri.RIToplam as Toplam,
                    ri.RIIade as Iade
                FROM ReceteIlaclari ri
                LEFT JOIN Urun u ON ri.RIUrunId = u.UrunId
                WHERE ri.RIRxId = ? AND ri.RISilme = 0
                ORDER BY ri.RIId
            """
        else:  # ELDEN
            # Sadece doğrulanmış kolonlar; toplam kalemlerden hesaplanacak.
            baslik_sql = """
                SELECT
                    ea.RxId,
                    ea.RxIslemTarihi,
                    ea.RxKayitTarihi,
                    ea.RxBelgeNo,
                    m.MusteriAdiSoyadi as HastaAdi,
                    m.MusteriTCKN as HastaTCKN
                FROM EldenAna ea
                LEFT JOIN Musteri m ON ea.RxMusteriId = m.MusteriId
                WHERE ea.RxId = ? AND ea.RxSilme = 0
            """
            kalem_sql = """
                SELECT
                    ei.RIId,
                    ei.RIUrunId as UrunId,
                    u.UrunAdi,
                    (SELECT TOP 1 b.BarkodAdi FROM Barkod b
                        WHERE b.BarkodUrunId = u.UrunId
                        ORDER BY b.BarkodSilme ASC) as Barkod,
                    ei.RIAdet as Adet,
                    ei.RIEtiketFiyati as EtiketFiyat,
                    NULL as KurumFiyat,
                    NULL as FiyatFarki,
                    ei.RIIskonto as Iskonto,
                    ei.RIToplam as Toplam,
                    ei.RIIade as Iade
                FROM EldenIlaclari ei
                LEFT JOIN Urun u ON ei.RIUrunId = u.UrunId
                WHERE ei.RIRxId = ? AND ei.RISilme = 0
                ORDER BY ei.RIId
            """

        baslik_rows = self.sorgu_calistir(baslik_sql, (rx_id_int,))
        baslik_hata = self.son_sorgu_hatasi
        kalem_rows = self.sorgu_calistir(kalem_sql, (rx_id_int,))
        kalem_hata = self.son_sorgu_hatasi

        baslik = baslik_rows[0] if baslik_rows else None
        if baslik:
            baslik = dict(baslik)
            baslik['Kaynak'] = kaynak

        kalemler = []
        for r in kalem_rows or []:
            kalemler.append({
                'urun_id': r.get('UrunId'),
                'urun_adi': r.get('UrunAdi') or '',
                'barkod': r.get('Barkod') or '',
                'adet': float(r.get('Adet') or 0),
                'etiket_fiyat': float(r.get('EtiketFiyat') or 0),
                'kurum_fiyat': float(r.get('KurumFiyat') or 0)
                                if r.get('KurumFiyat') is not None else None,
                'fiyat_farki': float(r.get('FiyatFarki') or 0)
                                if r.get('FiyatFarki') is not None else None,
                'iskonto': float(r.get('Iskonto') or 0),
                'toplam': float(r.get('Toplam') or 0),
                'iade': bool(r.get('Iade')),
            })

        return {
            'baslik': baslik,
            'kalemler': kalemler,
            'baslik_hata': baslik_hata,
            'kalem_hata': kalem_hata,
        }

    def satis_raporu_getir(
        self,
        baslangic_tarih,
        bitis_tarih,
        kirilim: str = 'tumu',
        kurum_id: Optional[int] = None,
        periyot: str = 'aylik',
    ) -> List[Dict]:
        """İki tarih arası satışları periyot bazlı grupla.

        Args:
            baslangic_tarih: date veya 'YYYY-MM-DD'
            bitis_tarih: date veya 'YYYY-MM-DD' (dahil)
            kirilim: 'tumu' | 'recete' | 'elden' | 'kurum'
                'kurum' seçilirse kurum_id zorunlu
            kurum_id: kırılım='kurum' veya 'recete' iken belirli kurum filtresi
            periyot: 'gunluk' | 'haftalik' | 'aylik' | '3aylik' | 'yillik'

        Returns:
            [{Donem(date), ReceteSayisi, SatisSayisi, KutuSayisi, TLTutar}, ...]
            Donem periyodun başlangıç tarihi.
        """
        if periyot not in self.PERIYOT_IFADELERI:
            raise ValueError(f"Geçersiz periyot: {periyot}. Beklenen: {list(self.PERIYOT_IFADELERI.keys())}")
        if kirilim not in ('tumu', 'recete', 'elden', 'kurum'):
            raise ValueError(f"Geçersiz kırılım: {kirilim}")
        if kirilim == 'kurum' and kurum_id is None:
            raise ValueError("kırılım='kurum' için kurum_id zorunlu")

        # Tarihleri normalize et
        if hasattr(baslangic_tarih, 'strftime'):
            bas_str = baslangic_tarih.strftime('%Y-%m-%d')
        else:
            bas_str = str(baslangic_tarih)
        if hasattr(bitis_tarih, 'strftime'):
            bit_str = bitis_tarih.strftime('%Y-%m-%d')
        else:
            bit_str = str(bitis_tarih)

        period_expr = self.PERIYOT_IFADELERI[periyot]

        # Kaynak filtreleri (reçete / elden / her ikisi)
        recete_aktif = kirilim in ('tumu', 'recete', 'kurum')
        elden_aktif = kirilim in ('tumu', 'elden')

        # Kurum filtre cümlesi (parametre ile değil, int olduğu için string interpolation
        # — kurum_id sadece dropdown'dan int olarak gelir, SQL injection riski yok)
        kurum_filtre = ""
        if kirilim == 'kurum' and kurum_id is not None:
            kurum_filtre = f" AND ra.RxKurumId = {int(kurum_id)} "
        elif kirilim == 'recete' and kurum_id is not None:
            kurum_filtre = f" AND ra.RxKurumId = {int(kurum_id)} "

        # Kaynak UNION
        recete_blok = """
            SELECT
                'RECETE' as Kaynak,
                ra.RxId as RxId,
                ra.RxIslemTarihi as Tarih,
                ri.RIAdet as Adet,
                ri.RIToplam as Tutar
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
                AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                AND ra.RxIslemTarihi >= ?
                AND ra.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))
        """ + kurum_filtre

        elden_blok = """
            SELECT
                'ELDEN' as Kaynak,
                ea.RxId as RxId,
                ea.RxIslemTarihi as Tarih,
                ei.RIAdet as Adet,
                ei.RIToplam as Tutar
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
                AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                AND ea.RxIslemTarihi >= ?
                AND ea.RxIslemTarihi < DATEADD(DAY, 1, CAST(? as date))
        """

        kaynak_bloklari = []
        params = []
        if recete_aktif:
            kaynak_bloklari.append(recete_blok)
            params.extend([bas_str, bit_str])
        if elden_aktif:
            kaynak_bloklari.append(elden_blok)
            params.extend([bas_str, bit_str])

        if not kaynak_bloklari:
            return []

        kaynak_sql = "\n            UNION ALL\n".join(kaynak_bloklari)

        sql = f"""
        WITH SatisKaynak AS (
        {kaynak_sql}
        )
        SELECT
            {period_expr} as Donem,
            -- Reçeteli kırılım
            COUNT(DISTINCT CASE WHEN Kaynak = 'RECETE' THEN CAST(RxId as nvarchar(50)) END) as ReceteliSayisi,
            SUM(CASE WHEN Kaynak = 'RECETE' THEN 1 ELSE 0 END) as ReceteliKalem,
            SUM(CASE WHEN Kaynak = 'RECETE' THEN CAST(Adet as decimal(18,4)) ELSE 0 END) as ReceteliKutu,
            SUM(CASE WHEN Kaynak = 'RECETE' THEN CAST(Tutar as decimal(18,4)) ELSE 0 END) as ReceteliTL,
            -- Elden kırılım
            COUNT(DISTINCT CASE WHEN Kaynak = 'ELDEN' THEN CAST(RxId as nvarchar(50)) END) as EldenSayisi,
            SUM(CASE WHEN Kaynak = 'ELDEN' THEN 1 ELSE 0 END) as EldenKalem,
            SUM(CASE WHEN Kaynak = 'ELDEN' THEN CAST(Adet as decimal(18,4)) ELSE 0 END) as EldenKutu,
            SUM(CASE WHEN Kaynak = 'ELDEN' THEN CAST(Tutar as decimal(18,4)) ELSE 0 END) as EldenTL,
            -- Genel toplam
            COUNT(DISTINCT CAST(Kaynak as nvarchar(10)) + '-' + CAST(RxId as nvarchar(50))) as SatisSayisi,
            COUNT(*) as KalemSayisi,
            SUM(CAST(Adet as decimal(18,4))) as KutuSayisi,
            SUM(CAST(Tutar as decimal(18,4))) as TLTutar
        FROM SatisKaynak
        GROUP BY {period_expr}
        ORDER BY {period_expr}
        """

        sonuclar = self.sorgu_calistir(sql, tuple(params))

        # Decimal -> float dönüşümü ve None temizliği
        temiz = []
        for r in sonuclar:
            temiz.append({
                'Donem': r.get('Donem'),
                # Reçeteli kırılım
                'ReceteliSayisi': int(r.get('ReceteliSayisi') or 0),
                'ReceteliKalem': int(r.get('ReceteliKalem') or 0),
                'ReceteliKutu': float(r.get('ReceteliKutu') or 0),
                'ReceteliTL': float(r.get('ReceteliTL') or 0),
                # Elden kırılım
                'EldenSayisi': int(r.get('EldenSayisi') or 0),
                'EldenKalem': int(r.get('EldenKalem') or 0),
                'EldenKutu': float(r.get('EldenKutu') or 0),
                'EldenTL': float(r.get('EldenTL') or 0),
                # Genel toplam
                'SatisSayisi': int(r.get('SatisSayisi') or 0),
                'KalemSayisi': int(r.get('KalemSayisi') or 0),
                'KutuSayisi': float(r.get('KutuSayisi') or 0),
                'TLTutar': float(r.get('TLTutar') or 0),
                # Legacy alias (= ReceteliSayisi)
                'ReceteSayisi': int(r.get('ReceteliSayisi') or 0),
            })
        return temiz

    def hasta_ilk_recete_etken_bazli(
        self,
        hasta_tc: str,
        urun_keywords: tuple,
        limit: int = 5,
    ) -> List[Dict]:
        """Hastanın belirli etken/marka keyword listesiyle eşleşen
        İLK reçetelerini (en eskiden) döndür — başlangıç rapor tespiti için.

        Aktif reçetenin etken maddesini içeren UrunAdi'lı ilk reçete
        bulunur (örn. VEMLIDY/VIREAD/TENOFOVIR keyword'leriyle). Rapor
        bilgileri (RaporAna + RaporAnaAciklamalar) JOIN'le getirilir;
        eski reçetede SecilenRapor cache'i varsa o rapora bağlanır.

        Args:
            hasta_tc: MusteriTCKN (string, 11 haneli)
            urun_keywords: keyword tuple — UPPER(UrunAdi) LIKE '%kw%' OR ...
                örn: ('VEMLIDY', 'VIREAD', 'TENOFOVIR', ...)
            limit: dönecek satır sayısı (default 5 — en eski 5 reçete)

        Returns:
            List[Dict] — boş liste = hiç eşleşme yok (hasta_tc/keyword/EOS
            sorununda); her satır:
                RxId, RxIslemTarihi, RxReceteTarihi, RxEReceteNo,
                UrunId, UrunAdi, ATCKodu, RIRaporNo,
                RaporAnaId, RaporAnaRaporNo, RaporAnaRaporTakipNo,
                RaporAnaRaporTarihi, RaporAnaAciklamalar,
                MusteriTCKN, MusteriAdiSoyadi
            En eski tarih en başta.
        """
        if not hasta_tc or not urun_keywords:
            return []
        # Keyword sayısı kadar `?` placeholder — SQL injection-safe
        like_clauses = ' OR '.join(
            ['UPPER(u.UrunAdi) LIKE UPPER(?)' for _ in urun_keywords])
        like_params = [f'%{kw}%' for kw in urun_keywords]
        sql = f"""
        SELECT TOP {int(limit)}
            ra.RxId, ra.RxIslemTarihi, ra.RxReceteTarihi, ra.RxEReceteNo,
            u.UrunId, u.UrunAdi,
            atc.ATCKodu,
            ri.RIRaporNo, ri.RIRaporKodId,
            rap.RaporAnaId, rap.RaporAnaRaporNo,
            rap.RaporAnaRaporTakipNo, rap.RaporAnaRaporTarihi,
            rap.RaporAnaAciklamalar,
            m.MusteriTCKN, m.MusteriAdiSoyadi
        FROM ReceteAna ra
        INNER JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
                                      AND ri.RISilme = 0
        INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
        INNER JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
        LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId
        OUTER APPLY (
            SELECT TOP 1
                rap2.RaporAnaId, rap2.RaporAnaRaporNo,
                rap2.RaporAnaRaporTakipNo, rap2.RaporAnaRaporTarihi,
                rap2.RaporAnaAciklamalar
            FROM SecilenRapor sr
            INNER JOIN RaporAna rap2
                    ON rap2.RaporAnaMusteriId = ra.RxMusteriId
                   AND (rap2.RaporAnaSilme IS NULL OR rap2.RaporAnaSilme = 0)
                   AND (CAST(rap2.RaporAnaRaporNo AS NVARCHAR(50))
                        = sr.SRRaporNo
                     OR CAST(rap2.RaporAnaRaporTakipNo AS NVARCHAR(50))
                        = sr.SRRaporNo
                     OR CAST(rap2.RaporAnaProtokolNo AS NVARCHAR(50))
                        = sr.SRRaporNo)
            WHERE sr.SRRxId = ra.RxId
              AND sr.SRUrunId = ri.RIUrunId
        ) rap
        WHERE ra.RxSilme = 0
          AND m.MusteriTCKN = ?
          AND ({like_clauses})
        ORDER BY ra.RxIslemTarihi ASC, ra.RxId ASC
        """
        params = tuple([hasta_tc] + like_params)
        try:
            return self.sorgu_calistir(sql, params)
        except Exception as e:
            logger.error('hasta_ilk_recete_etken_bazli sorgu hatasi: %s', e)
            return []

    def hasta_etken_rapor_listesi(
        self,
        hasta_tc: str,
        urun_keywords: tuple,
        limit: int = 50,
    ) -> List[Dict]:
        """Hastanın belirli etken/marka keyword listesiyle eşleşen
        TÜM DISTINCT raporları (tarih sıralı, eskiden yeniye) döndür.

        Devam/başlangıç tespiti için: 'Bu hastanın bu etken için kaç
        rapor RaporAna'da var? Aktif rapor en eskisi mi?'

        Args:
            hasta_tc: 11 haneli TC
            urun_keywords: ('LAMIVUDIN','TENOFOVIR','VEMLIDY','VIREAD',...)
            limit: max distinct rapor sayısı (default 50)

        Returns:
            List[Dict] (en eski en başta):
                RaporAnaId, RaporAnaRaporNo, RaporAnaRaporTakipNo,
                RaporAnaRaporTarihi, ilk_recete_tarihi,
                bu_rapora_bagli_recete_sayisi
            Boş liste = eşleşme yok / EOS bağlantı hatası.
        """
        if not hasta_tc or not urun_keywords:
            return []
        like_clauses = ' OR '.join(
            ['UPPER(u.UrunAdi) LIKE UPPER(?)' for _ in urun_keywords])
        like_params = [f'%{kw}%' for kw in urun_keywords]
        # DISTINCT RaporAna — SecilenRapor üzerinden bağ + RaporAna metadata
        sql = f"""
        SELECT TOP {int(limit)}
            rap.RaporAnaId,
            rap.RaporAnaRaporNo,
            rap.RaporAnaRaporTakipNo,
            rap.RaporAnaRaporTarihi,
            MIN(ra.RxIslemTarihi) AS ilk_recete_tarihi,
            COUNT(DISTINCT ra.RxId) AS bu_rapora_bagli_recete_sayisi
        FROM ReceteAna ra
        INNER JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
                                      AND ri.RISilme = 0
        INNER JOIN Urun u ON u.UrunId = ri.RIUrunId
        INNER JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
        INNER JOIN SecilenRapor sr ON sr.SRRxId = ra.RxId
                                    AND sr.SRUrunId = ri.RIUrunId
        INNER JOIN RaporAna rap
                ON rap.RaporAnaMusteriId = ra.RxMusteriId
               AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
               AND (CAST(rap.RaporAnaRaporNo AS NVARCHAR(50))
                    = sr.SRRaporNo
                 OR CAST(rap.RaporAnaRaporTakipNo AS NVARCHAR(50))
                    = sr.SRRaporNo
                 OR CAST(rap.RaporAnaProtokolNo AS NVARCHAR(50))
                    = sr.SRRaporNo)
        WHERE ra.RxSilme = 0
          AND m.MusteriTCKN = ?
          AND ({like_clauses})
        GROUP BY rap.RaporAnaId, rap.RaporAnaRaporNo,
                 rap.RaporAnaRaporTakipNo, rap.RaporAnaRaporTarihi
        ORDER BY MIN(ra.RxIslemTarihi) ASC, rap.RaporAnaId ASC
        """
        params = tuple([hasta_tc] + like_params)
        try:
            return self.sorgu_calistir(sql, params)
        except Exception as e:
            logger.error('hasta_etken_rapor_listesi sorgu hatasi: %s', e)
            return []

    def hasta_tum_rapor_takip_nolari(self, hasta_tc: str) -> set:
        """Hastanın EOS'taki TÜM aktif raporlarının RaporTakipNo set'ini
        döndür — MEDULA tarama sırasında 'bu rapor zaten EOS'ta var,
        atlayalım' kontrolü için.

        Args:
            hasta_tc: MusteriTCKN (11 haneli string)

        Returns:
            set[str] — boş set = EOS'ta hiç rapor yok ya da sorgu hatası
        """
        if not hasta_tc or len(hasta_tc) != 11:
            return set()
        sql = """
        SELECT DISTINCT CAST(rap.RaporAnaRaporTakipNo AS NVARCHAR(50)) AS tn
        FROM RaporAna rap
        INNER JOIN Musteri m ON m.MusteriId = rap.RaporAnaMusteriId
        WHERE (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
          AND m.MusteriTCKN = ?
          AND rap.RaporAnaRaporTakipNo IS NOT NULL
        """
        try:
            rows = self.sorgu_calistir(sql, (hasta_tc,))
            return {(r.get('tn') or '').strip() for r in rows
                    if (r.get('tn') or '').strip()}
        except Exception as e:
            logger.error('hasta_tum_rapor_takip_nolari sorgu hatasi: %s', e)
            return set()


# Singleton instance
_db_instance = None

def get_botanik_db() -> BotanikDB:
    """Singleton BotanikDB instance döndür"""
    global _db_instance
    if _db_instance is None:
        _db_instance = BotanikDB()
    return _db_instance


# Test
if __name__ == "__main__":
    db = BotanikDB()
    if db.baglan():
        print("Bağlantı başarılı!")
        hareketler = db.tum_hareketler_getir(limit=10)
        print(f"Toplam: {len(hareketler)} kayıt")
        for h in hareketler:
            print(f"  {h['Tarih']} - {h['HareketTipi']} - {h['UrunAdi'][:30]}")
        db.kapat()
