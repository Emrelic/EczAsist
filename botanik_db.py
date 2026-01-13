"""
Botanik EOS Veritabanı Bağlantı Modülü
SQL Server üzerinden Botanik veritabanına erişim sağlar
"""

import pyodbc
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


class BotanikDB:
    """Botanik EOS SQL Server veritabanı bağlantı sınıfı"""

    # Test ortamı bağlantı ayarları (localhost)
    TEST_CONFIG = {
        'server': 'localhost',
        'database': 'eczane_test',
        'trusted_connection': True,
        'trust_server_certificate': True
    }

    # PRODUCTION ortamı bağlantı ayarları (gerçek sunucu)
    PRODUCTION_CONFIG = {
        'server': '192.168.1.120\\BOTANIKSQL',  # IP\Instance formatı
        'database': 'eczane',
        'trusted_connection': False,  # SQL Server Authentication kullanılacak
        'user': 'sa',
        'password': '123',
        'trust_server_certificate': True
    }

    # Varsayılan olarak PRODUCTION kullan
    DEFAULT_CONFIG = PRODUCTION_CONFIG

    # YASAKLI SQL KOMUTLARI - GÜVENLİK
    YASAKLI_KOMUTLAR = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE', 'DENY',
        'BACKUP', 'RESTORE', 'SHUTDOWN', 'KILL'
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

    def baglan(self) -> bool:
        """Veritabanına bağlan"""
        try:
            conn_str = self._connection_string_olustur()
            self.conn = pyodbc.connect(conn_str, timeout=30)
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
        SQL sorgusunun güvenli olup olmadığını kontrol et.
        Sadece SELECT sorgularına izin verilir.

        Returns:
            True: Sorgu güvenli
            False: Sorgu tehlikeli komut içeriyor
        """
        sql_upper = sql.upper().strip()

        # Yasaklı komutları kontrol et
        for komut in self.YASAKLI_KOMUTLAR:
            # Kelimenin başında veya boşluktan sonra gelen komutları kontrol et
            if sql_upper.startswith(komut + ' ') or sql_upper.startswith(komut + '('):
                logger.error(f"GÜVENLİK UYARISI: Yasaklı komut tespit edildi: {komut}")
                return False
            # Sorgu içinde de kontrol et (alt sorgular hariç SELECT)
            if f' {komut} ' in f' {sql_upper} ' or f';{komut} ' in sql_upper:
                # WITH ... AS yapısında INSERT vb. olmamalı
                if komut != 'AS':  # AS keyword'ü WITH için gerekli
                    logger.error(f"GÜVENLİK UYARISI: Yasaklı komut tespit edildi: {komut}")
                    return False

        return True

    def sorgu_calistir(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        SQL sorgusu çalıştır ve sonuçları döndür.
        GÜVENLİK: Sadece SELECT sorguları çalıştırılabilir!
        """
        try:
            # GÜVENLİK KONTROLÜ
            if not self._guvenlik_kontrolu(sql):
                logger.error("SORGU REDDEDİLDİ: Güvenlik kontrolünden geçemedi!")
                return []

            if not self.conn:
                if not self.baglan():
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
        """Ürün adına göre ara"""
        sql = f"""
        SELECT TOP {limit}
            UrunId,
            UrunAdi,
            UrunFiyatEtiket,
            UrunStokDepo + UrunStokRaf + UrunStokAcik as ToplamStok
        FROM Urun
        WHERE UrunAdi LIKE '%{arama}%' AND UrunSilme = 0
        ORDER BY UrunAdi
        """
        return self.sorgu_calistir(sql)

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
            WHERE u.UrunUrunTipId <> 1  -- İlaç olmayanlar
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
        WHERE u.UrunSilme = 0 AND u.UrunUrunTipId != 1
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

        sql = f"""
        ;WITH AlimlarCumulative AS (
            -- Tüm alımlar, tarih ve ürün bazında kümülatif
            SELECT
                fs.FSUrunId as UrunId,
                fg.FGFaturaTarihi as Tarih,
                SUM(fs.FSUrunAdet) as GunlukAlim,
                SUM(SUM(fs.FSUrunAdet)) OVER (
                    PARTITION BY fs.FSUrunId
                    ORDER BY fg.FGFaturaTarihi
                    ROWS UNBOUNDED PRECEDING
                ) as KumulatifAlim
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0 AND fs.FSUrunAdet > 0
            GROUP BY fs.FSUrunId, fg.FGFaturaTarihi
        ),
        TakasGirisler AS (
            -- Takas girişleri
            SELECT
                ts.TSUrunId as UrunId,
                CAST(t.TakasTarihi as date) as Tarih,
                SUM(ts.TSUrunAdedi) as GunlukAlim
            FROM TakasSatir ts
            JOIN Takas t ON ts.TSTakasId = t.TakasId
            WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
            GROUP BY ts.TSUrunId, CAST(t.TakasTarihi as date)
        ),
        TumSatislar AS (
            -- Reçeteli satışlar
            SELECT
                ri.RIUrunId as UrunId,
                CAST(ra.RxReceteTarihi as date) as Tarih,
                SUM(ri.RIAdet) as GunlukSatis
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND ri.RIIade = 0
            GROUP BY ri.RIUrunId, CAST(ra.RxReceteTarihi as date)

            UNION ALL

            -- Elden satışlar
            SELECT
                ei.RIUrunId as UrunId,
                CAST(ea.RxReceteTarihi as date) as Tarih,
                SUM(ei.RIAdet) as GunlukSatis
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND ei.RIIade = 0
            GROUP BY ei.RIUrunId, CAST(ea.RxReceteTarihi as date)

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
        SatisOzet AS (
            SELECT
                UrunId,
                Tarih,
                SUM(GunlukSatis) as GunlukSatis
            FROM TumSatislar
            GROUP BY UrunId, Tarih
        )

        SELECT TOP {limit}
            fg.FGFaturaNo as FaturaNo,
            fg.FGFaturaTarihi as Tarih,
            d.DepoAdi as Depo,
            u.UrunId,
            u.UrunAdi,
            fs.FSUrunAdet as Adet,
            fs.FSIskontoKamu as MF,
            fs.FSBirimFiyat as BirimFiyat,
            fs.FSMaliyet as Maliyet,
            fs.FSUrunAdet * COALESCE(fs.FSMaliyet, fs.FSBirimFiyat) as ToplamTutar,
            fg.FGVadeTarihi as FaturaVade,

            -- Fatura öncesi toplam alım
            COALESCE((
                SELECT SUM(fs2.FSUrunAdet)
                FROM FaturaSatir fs2
                JOIN FaturaGiris fg2 ON fs2.FSFGId = fg2.FGId
                WHERE fg2.FGSilme = 0 AND fs2.FSUrunId = fs.FSUrunId
                AND fg2.FGFaturaTarihi < fg.FGFaturaTarihi
            ), 0) +
            COALESCE((
                SELECT SUM(ts.TSUrunAdedi)
                FROM TakasSatir ts
                JOIN Takas t ON ts.TSTakasId = t.TakasId
                WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
                AND ts.TSUrunId = fs.FSUrunId
                AND CAST(t.TakasTarihi as date) < fg.FGFaturaTarihi
            ), 0) as OncekiAlimlar,

            -- Fatura öncesi toplam satış
            COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM SatisOzet s
                WHERE s.UrunId = fs.FSUrunId AND s.Tarih < fg.FGFaturaTarihi
            ), 0) as OncekiSatislar,

            -- Fatura öncesi stok (alımlar - satışlar)
            COALESCE((
                SELECT SUM(fs2.FSUrunAdet)
                FROM FaturaSatir fs2
                JOIN FaturaGiris fg2 ON fs2.FSFGId = fg2.FGId
                WHERE fg2.FGSilme = 0 AND fs2.FSUrunId = fs.FSUrunId
                AND fg2.FGFaturaTarihi < fg.FGFaturaTarihi
            ), 0) +
            COALESCE((
                SELECT SUM(ts.TSUrunAdedi)
                FROM TakasSatir ts
                JOIN Takas t ON ts.TSTakasId = t.TakasId
                WHERE t.TakasSilme = 0 AND ts.TSSilme = 0 AND t.TakasYonu = 1
                AND ts.TSUrunId = fs.FSUrunId
                AND CAST(t.TakasTarihi as date) < fg.FGFaturaTarihi
            ), 0) -
            COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM SatisOzet s
                WHERE s.UrunId = fs.FSUrunId AND s.Tarih < fg.FGFaturaTarihi
            ), 0) as FaturaOncesiStok,

            -- Fatura öncesi X ay içindeki satışlar (aylık ortalama için)
            COALESCE((
                SELECT SUM(s.GunlukSatis)
                FROM SatisOzet s
                WHERE s.UrunId = fs.FSUrunId
                AND s.Tarih >= DATEADD(MONTH, -{ortalama_ay}, fg.FGFaturaTarihi)
                AND s.Tarih < fg.FGFaturaTarihi
            ), 0) as OncekiDonemSatis,

            -- Aylık ortalama satış (fatura öncesi X ay)
            ROUND(
                COALESCE((
                    SELECT SUM(s.GunlukSatis)
                    FROM SatisOzet s
                    WHERE s.UrunId = fs.FSUrunId
                    AND s.Tarih >= DATEADD(MONTH, -{ortalama_ay}, fg.FGFaturaTarihi)
                    AND s.Tarih < fg.FGFaturaTarihi
                ), 0) / {ortalama_ay}.0
            , 2) as AylikOrtalama,

            -- Parametre olarak kullanılan ay sayısı
            {ortalama_ay} as OrtalamaAy

        FROM FaturaGiris fg
        JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
        JOIN Urun u ON fs.FSUrunId = u.UrunId
        LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId AND fg.FGIlgiliTipi = 1
        WHERE fg.FGSilme = 0 AND fs.FSUrunAdet > 0
        {tarih_filtre}
        {depo_filtre}
        {urun_filtre}

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
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND ri.RIIade = 0
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
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND ei.RIIade = 0
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
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0 AND ri.RIIade = 0
            AND ra.RxReceteTarihi >= '{baslangic_tarih}'
            """)

        if 'ELDEN_SATIS' in hareket_tipleri:
            hareket_bloklari.append(f"""
            SELECT DISTINCT ei.RIUrunId as UrunId
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0 AND ei.RIIade = 0
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
