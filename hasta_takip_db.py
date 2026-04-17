"""
Hasta Takip & WhatsApp Mesaj Modülü - Veritabanı Sorguları

GÜVENLİK: Tüm sorgular SELECT-only. Botanik EOS veritabanına YAZMA YAPILMAZ.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)


class HastaTakipDB:
    """Takip edilen hastaların yazdırma günü gelen ilaçlarını bulur."""

    def __init__(self, db: Optional[BotanikDB] = None):
        self.db = db or BotanikDB()
        if not self.db.conn:
            self.db.baglan()

    def yazdirma_gunu_gelen_ilaclar(
        self,
        tolerans_gun: int = 0,
        rapor_tolerans_gun: int = 15,
        sadece_takipli: bool = True,
        eski_kayit_gun: int = 30,
        kaynak: str = "BIRLESIK",
        sadece_raporlu: bool = False,
        raporsuz_istisna_urunler: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        Bugün + tolerans_gun içinde yazdırma günü gelen hastaları/ilaçları döndür.

        Args:
            tolerans_gun: Hafta sonu toleransı (bu kadar gün sonrasına kadar da listele)
            rapor_tolerans_gun: Raporlu ilaçlarda bitiş tarihinden bu kadar gün önce yazdırılabilir
            sadece_takipli: True ise Musteri.MusteriTakipli=1 filtresi uygulanır
            eski_kayit_gun: Bitiş tarihi bu günden daha eski olanlar gösterilmez (gürültü temizliği)
            kaynak: 'RECETE' | 'MEDULA' | 'BIRLESIK'

        Returns:
            [{musteri_id, hasta_adi, cep_tel, takipli, urun_adi, doz,
              adet_kutu, rapor_kodu, bitis_tarihi, yazdirma_tarihi,
              kaynak, kac_gun_kaldi}, ...]
        """
        bugun = date.today().isoformat()
        sonuclar: List[Dict] = []
        istisnalar = set(raporsuz_istisna_urunler or [])

        if kaynak in ("RECETE", "BIRLESIK"):
            sonuclar.extend(
                self._recete_ilaclari_sorgula(
                    bugun, tolerans_gun, rapor_tolerans_gun,
                    sadece_takipli, eski_kayit_gun,
                )
            )

        if kaynak in ("MEDULA", "BIRLESIK"):
            sonuclar.extend(
                self._medula_hasta_ilaclari_sorgula(
                    bugun, tolerans_gun, rapor_tolerans_gun,
                    sadece_takipli, eski_kayit_gun,
                )
            )

        if sadece_raporlu:
            sonuclar = [
                s for s in sonuclar
                if self._raporlu_mu(s) or s.get("urun_id") in istisnalar
            ]

        return self._birlesik_ve_tekilsizlestir(sonuclar)

    @staticmethod
    def _raporlu_mu(satir: Dict) -> bool:
        """Satırın raporlu olup olmadığını güvenli şekilde değerlendir.

        RECETE kaynağı için rapor_kod_id int (0 veya null = raporsuz).
        MEDULA kaynağı için rapor_kod_id string (boş/null/whitespace = raporsuz).
        """
        rk = satir.get("rapor_kod_id")
        if rk is None:
            return False
        if isinstance(rk, str):
            return bool(rk.strip())
        try:
            return int(rk) > 0
        except (TypeError, ValueError):
            return False

    def _recete_ilaclari_sorgula(
        self, bugun: str, tolerans_gun: int, rapor_tolerans_gun: int,
        sadece_takipli: bool, eski_kayit_gun: int,
    ) -> List[Dict]:
        takipli_filtre = "AND m.MusteriTakipli = 1" if sadece_takipli else ""

        # RIBitisTarihi = ilacın hastada biteceği tarih (Botanik hesaplıyor).
        # Raporlu ise bitiş tarihinden rapor_tolerans_gun önce yazdırma açılır.
        sql = f"""
        SELECT
            m.MusteriId                                    AS musteri_id,
            LTRIM(RTRIM(ISNULL(m.MusteriTCKN, '')))        AS tckn,
            LTRIM(RTRIM(m.MusteriAdiSoyadi))               AS hasta_adi,
            LTRIM(RTRIM(ISNULL(m.MusteriTelCep, '')))      AS cep_tel,
            CAST(m.MusteriTakipli AS INT)                  AS takipli,
            LTRIM(RTRIM(u.UrunAdi))                        AS urun_adi,
            ri.RIUrunId                                    AS urun_id,
            ri.RIDoz                                       AS doz,
            ri.RIAdet                                      AS adet_kutu,
            ri.RIRaporNo                                   AS rapor_no,
            ri.RIRaporKodId                                AS rapor_kod_id,
            ri.RIBitisTarihi                               AS bitis_tarihi,
            CASE WHEN ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0
                 THEN DATEADD(DAY, -?, ri.RIBitisTarihi)
                 ELSE ri.RIBitisTarihi END                 AS yazdirma_tarihi,
            ra.RxReceteTarihi                              AS recete_tarihi,
            (SELECT COUNT(DISTINCT r2.RxId) FROM ReceteAna r2
              WHERE r2.RxMusteriId = m.MusteriId AND r2.RxSilme = 0) AS toplam_ziyaret,
            (SELECT MAX(r2.RxReceteTarihi) FROM ReceteAna r2
              WHERE r2.RxMusteriId = m.MusteriId AND r2.RxSilme = 0) AS son_ziyaret,
            'RECETE'                                       AS kaynak
        FROM ReceteIlaclari ri
        INNER JOIN ReceteAna ra  ON ra.RxId      = ri.RIRxId
        INNER JOIN Musteri   m   ON m.MusteriId  = ra.RxMusteriId
        LEFT  JOIN Urun      u   ON u.UrunId     = ri.RIUrunId
        WHERE ri.RISilme = 0
          AND ra.RxSilme = 0
          AND (ri.RIIade IS NULL OR ri.RIIade = 0)
          AND ri.RIBitisTarihi IS NOT NULL
          AND (
                CASE WHEN ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0
                     THEN DATEADD(DAY, -?, ri.RIBitisTarihi)
                     ELSE ri.RIBitisTarihi END
              ) <= DATEADD(DAY,  ?, ?)
          AND ri.RIBitisTarihi >= DATEADD(DAY, -?, ?)
          {takipli_filtre}
        ORDER BY bitis_tarihi ASC
        """
        params = (
            rapor_tolerans_gun,     # SELECT CASE
            rapor_tolerans_gun,     # WHERE CASE
            tolerans_gun, bugun,    # <= bugun + tolerans
            eski_kayit_gun, bugun,  # >= bugun - eski_kayit_gun
        )
        return self.db.sorgu_calistir(sql, params)

    def _medula_hasta_ilaclari_sorgula(
        self, bugun: str, tolerans_gun: int, rapor_tolerans_gun: int,
        sadece_takipli: bool, eski_kayit_gun: int,
    ) -> List[Dict]:
        takipli_filtre = "AND m.MusteriTakipli = 1" if sadece_takipli else ""

        # MedulaHastaIlaclari.VerilecekTarih Medula'dan sync'lenmiş tarihtir.
        # Doz string formatta ("Günde 1 x 1.0"), rapor kodu da string.
        sql = f"""
        SELECT
            m.MusteriId                                  AS musteri_id,
            LTRIM(RTRIM(ISNULL(m.MusteriTCKN, '')))      AS tckn,
            LTRIM(RTRIM(m.MusteriAdiSoyadi))             AS hasta_adi,
            LTRIM(RTRIM(ISNULL(m.MusteriTelCep, '')))    AS cep_tel,
            CAST(m.MusteriTakipli AS INT)                AS takipli,
            LTRIM(RTRIM(mhi.UrunAdi))                    AS urun_adi,
            mhi.UrunId                                   AS urun_id,
            NULL                                         AS doz,
            mhi.verilenkutu                              AS adet_kutu,
            NULL                                         AS rapor_no,
            mhi.RaporKodu                                AS rapor_kod_id,
            mhi.VerilecekTarih                           AS bitis_tarihi,
            CASE WHEN mhi.RaporKodu IS NOT NULL AND LTRIM(RTRIM(mhi.RaporKodu)) <> ''
                 THEN DATEADD(DAY, -?, mhi.VerilecekTarih)
                 ELSE mhi.VerilecekTarih END             AS yazdirma_tarihi,
            mhi.RxTarihi                                 AS recete_tarihi,
            (SELECT COUNT(DISTINCT r2.RxId) FROM ReceteAna r2
              WHERE r2.RxMusteriId = m.MusteriId AND r2.RxSilme = 0) AS toplam_ziyaret,
            (SELECT MAX(r2.RxReceteTarihi) FROM ReceteAna r2
              WHERE r2.RxMusteriId = m.MusteriId AND r2.RxSilme = 0) AS son_ziyaret,
            'MEDULA'                                     AS kaynak
        FROM MedulaHastaIlaclari mhi
        INNER JOIN Musteri m ON m.MusteriId = mhi.MusteriId
        WHERE mhi.VerilecekTarih IS NOT NULL
          AND (
                CASE WHEN mhi.RaporKodu IS NOT NULL AND LTRIM(RTRIM(mhi.RaporKodu)) <> ''
                     THEN DATEADD(DAY, -?, mhi.VerilecekTarih)
                     ELSE mhi.VerilecekTarih END
              ) <= DATEADD(DAY, ?, ?)
          AND mhi.VerilecekTarih >= DATEADD(DAY, -?, ?)
          {takipli_filtre}
        ORDER BY mhi.VerilecekTarih ASC
        """
        params = (
            rapor_tolerans_gun,
            rapor_tolerans_gun,
            tolerans_gun, bugun,
            eski_kayit_gun, bugun,
        )
        return self.db.sorgu_calistir(sql, params)

    @staticmethod
    def _birlesik_ve_tekilsizlestir(satirlar: List[Dict]) -> List[Dict]:
        """(musteri_id, urun_id) tekil — RECETE kaynağı MEDULA'ya göre önceliklidir."""
        kayit: Dict[tuple, Dict] = {}
        oncelik = {"RECETE": 2, "MEDULA": 1}

        for s in satirlar:
            mid = s.get("musteri_id")
            uid = s.get("urun_id")
            anahtar = (mid, uid)
            mevcut = kayit.get(anahtar)
            if mevcut is None:
                kayit[anahtar] = s
                continue
            # Aynı hasta+ilaç: en yüksek öncelikli kaynağı ve en güncel bitiş tarihini al
            if oncelik.get(s.get("kaynak"), 0) > oncelik.get(mevcut.get("kaynak"), 0):
                kayit[anahtar] = s
            else:
                s_bt = s.get("bitis_tarihi")
                m_bt = mevcut.get("bitis_tarihi")
                if s_bt and m_bt and s_bt > m_bt:
                    kayit[anahtar] = s

        def _gun(x):
            if x is None:
                return None
            if isinstance(x, datetime):
                return x.date()
            if isinstance(x, date):
                return x
            try:
                return datetime.strptime(str(x)[:10], "%Y-%m-%d").date()
            except ValueError:
                return None

        bugun = date.today()
        sonuc = []
        for s in kayit.values():
            s["bitis_tarihi"] = _gun(s.get("bitis_tarihi"))
            yt = _gun(s.get("yazdirma_tarihi"))
            s["yazdirma_tarihi"] = yt
            s["kac_gun_kaldi"] = (yt - bugun).days if yt else None
            sonuc.append(s)

        sonuc.sort(key=lambda r: (r.get("yazdirma_tarihi") or date.max, r.get("hasta_adi") or ""))
        return sonuc

    def hasta_portfoyu_getir(
        self,
        baslangic: Optional[date] = None,
        bitis: Optional[date] = None,
        sadece_telefonlu: bool = False,
        son_gelis_sonra: Optional[date] = None,
        sadece_takipli: bool = False,
        min_ziyaret: Optional[int] = None,
        max_ziyaret: Optional[int] = None,
    ) -> List[Dict]:
        """Hasta bazlı geliş sıklığı / son geliş / toplam ziyaret raporu.

        Filtreler:
          - baslangic, bitis: ReceteTarihi aralığı (varsayılan son 1 yıl)
          - sadece_telefonlu: MusteriTelCep dolu hastalar
          - son_gelis_sonra: MAX(ReceteTarihi) bu tarihten sonra
          - sadece_takipli: MusteriTakipli=1
          - min_ziyaret / max_ziyaret: ziyaret sayısı aralığı
        """
        bitis = bitis or date.today()
        baslangic = baslangic or (bitis - timedelta(days=365))

        having_parcalari = []
        params: list = [date.today().isoformat(),
                        baslangic.isoformat(), bitis.isoformat()]

        where_ekler = ["ra.RxSilme = 0", "ra.RxReceteTarihi BETWEEN ? AND ?"]
        if sadece_telefonlu:
            where_ekler.append(
                "m.MusteriTelCep IS NOT NULL AND LTRIM(RTRIM(m.MusteriTelCep)) <> ''"
            )
        if sadece_takipli:
            where_ekler.append("m.MusteriTakipli = 1")

        if son_gelis_sonra:
            having_parcalari.append("MAX(ra.RxReceteTarihi) >= ?")
            params.append(son_gelis_sonra.isoformat())
        if min_ziyaret is not None:
            having_parcalari.append("COUNT(DISTINCT CAST(ra.RxReceteTarihi AS DATE)) >= ?")
            params.append(int(min_ziyaret))
        if max_ziyaret is not None:
            having_parcalari.append("COUNT(DISTINCT CAST(ra.RxReceteTarihi AS DATE)) <= ?")
            params.append(int(max_ziyaret))

        having = ("HAVING " + " AND ".join(having_parcalari)) if having_parcalari else ""

        sql = f"""
        SELECT
            m.MusteriId                              AS musteri_id,
            LTRIM(RTRIM(m.MusteriAdiSoyadi))         AS hasta_adi,
            LTRIM(RTRIM(ISNULL(m.MusteriTelCep,''))) AS cep_tel,
            COUNT(DISTINCT CAST(ra.RxReceteTarihi AS DATE)) AS ziyaret_sayisi,
            COUNT(DISTINCT ra.RxId)                  AS recete_sayisi,
            MIN(ra.RxReceteTarihi)                   AS ilk_ziyaret,
            MAX(ra.RxReceteTarihi)                   AS son_ziyaret,
            DATEDIFF(DAY, MAX(ra.RxReceteTarihi), ?) AS son_ziyaretten_gun,
            CAST(m.MusteriTakipli AS INT)            AS takipli
        FROM Musteri m
        INNER JOIN ReceteAna ra ON ra.RxMusteriId = m.MusteriId
        WHERE {" AND ".join(where_ekler)}
        GROUP BY m.MusteriId, m.MusteriAdiSoyadi, m.MusteriTelCep, m.MusteriTakipli
        {having}
        ORDER BY ziyaret_sayisi DESC
        """
        return self.db.sorgu_calistir(sql, tuple(params))

    def hastanin_ilac_gecmisi(self, musteri_id: int, limit: int = 500) -> List[Dict]:
        """Bir hastanın reçete bazında tüm ilaç geçmişi (tarihe göre azalan)."""
        sql = f"""
        SELECT TOP {int(limit)}
            ra.RxId                                AS rx_id,
            ra.RxReceteTarihi                      AS recete_tarihi,
            ra.RxEReceteNo                         AS e_recete_no,
            LTRIM(RTRIM(u.UrunAdi))                AS urun_adi,
            ri.RIAdet                              AS adet,
            ri.RIDoz                               AS doz,
            ri.RIBitisTarihi                       AS bitis_tarihi,
            ri.RIRaporNo                           AS rapor_no,
            ri.RIRaporKodId                        AS rapor_kod_id
        FROM ReceteAna ra
        INNER JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
        LEFT  JOIN Urun u ON u.UrunId = ri.RIUrunId
        WHERE ra.RxMusteriId = ?
          AND ra.RxSilme = 0
          AND ri.RISilme = 0
          AND (ri.RIIade IS NULL OR ri.RIIade = 0)
        ORDER BY ra.RxReceteTarihi DESC, ra.RxId DESC
        """
        return self.db.sorgu_calistir(sql, (int(musteri_id),))

    def hastanin_yaklasan_yazdirmalari(
        self, musteri_id: int, geri_gun: int = 60, ileri_gun: int = 30,
        rapor_tolerans_gun: int = 15,
    ) -> List[Dict]:
        """Bir hastanın yaklaşan/geçmiş yazdırma günlerini getir."""
        bugun = date.today().isoformat()
        sql = """
        SELECT
            LTRIM(RTRIM(u.UrunAdi))                  AS urun_adi,
            ri.RIAdet                                AS adet,
            ri.RIDoz                                 AS doz,
            ri.RIRaporNo                             AS rapor_no,
            ri.RIRaporKodId                          AS rapor_kod_id,
            ra.RxReceteTarihi                        AS recete_tarihi,
            ri.RIBitisTarihi                         AS bitis_tarihi,
            CASE WHEN ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0
                 THEN DATEADD(DAY, -?, ri.RIBitisTarihi)
                 ELSE ri.RIBitisTarihi END           AS yazdirma_tarihi,
            DATEDIFF(DAY, ?,
                CASE WHEN ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0
                     THEN DATEADD(DAY, -?, ri.RIBitisTarihi)
                     ELSE ri.RIBitisTarihi END
            )                                        AS kac_gun_kaldi
        FROM ReceteIlaclari ri
        INNER JOIN ReceteAna ra ON ra.RxId = ri.RIRxId
        LEFT  JOIN Urun u ON u.UrunId = ri.RIUrunId
        WHERE ra.RxMusteriId = ?
          AND ra.RxSilme = 0
          AND ri.RISilme = 0
          AND (ri.RIIade IS NULL OR ri.RIIade = 0)
          AND ri.RIBitisTarihi IS NOT NULL
          AND ri.RIBitisTarihi BETWEEN DATEADD(DAY, -?, ?) AND DATEADD(DAY, ?, ?)
        ORDER BY yazdirma_tarihi ASC
        """
        return self.db.sorgu_calistir(sql, (
            int(rapor_tolerans_gun), bugun, int(rapor_tolerans_gun),
            int(musteri_id),
            int(geri_gun), bugun, int(ileri_gun), bugun,
        ))

    def hastanin_aktif_raporlari(self, musteri_id: int) -> List[Dict]:
        """Bir hastanın raporları + bitiş tarihi (RaporRaporKodlariICD MAX)."""
        sql = """
        SELECT
            ra.RaporAnaId                           AS rapor_id,
            ra.RaporAnaRaporNo                      AS rapor_no,
            ra.RaporAnaRaporTakipNo                 AS takip_no,
            ra.RaporAnaRaporTarihi                  AS rapor_tarihi,
            rt.RaporTuruAdi                         AS rapor_turu,
            h.HastaneAdi                            AS hastane,
            ra.RaporAnaAciklamalar                  AS aciklamalar,
            (SELECT MAX(RRKIBitisTarihi) FROM RaporRaporKodlariICD
              WHERE RRKIRaporAnaId = ra.RaporAnaId
                AND (RRKISilme IS NULL OR RRKISilme = 0)) AS bitis_tarihi,
            DATEDIFF(DAY, ?,
              (SELECT MAX(RRKIBitisTarihi) FROM RaporRaporKodlariICD
                WHERE RRKIRaporAnaId = ra.RaporAnaId
                  AND (RRKISilme IS NULL OR RRKISilme = 0))
            )                                       AS bitise_kac_gun
        FROM RaporAna ra
        LEFT JOIN RaporTuru rt ON rt.RaporTuruId = ra.RaporAnaRaporTuruId
        LEFT JOIN Hastane   h  ON h.HastaneId    = ra.RaporAnaHastaneId
        WHERE ra.RaporAnaMusteriId = ?
          AND (ra.RaporAnaSilme IS NULL OR ra.RaporAnaSilme = 0)
        ORDER BY ra.RaporAnaRaporTarihi DESC
        """
        return self.db.sorgu_calistir(sql, (date.today().isoformat(), int(musteri_id)))

    def devamlilik_raporu(self, bitis: Optional[date] = None) -> List[Dict]:
        """Hasta devamlılık: reçete adedi, son reçete tarihi, kaç gün oldu."""
        bitis = bitis or date.today()
        sql = """
        SELECT
            m.MusteriId                             AS musteri_id,
            LTRIM(RTRIM(m.MusteriAdiSoyadi))        AS hasta_adi,
            LTRIM(RTRIM(ISNULL(m.MusteriTelCep,''))) AS cep_tel,
            m.MusteriDogumTarihi                    AS dogum_tarihi,
            COUNT(DISTINCT ra.RxId)                 AS recete_adedi,
            MAX(ra.RxReceteTarihi)                  AS son_recete_tarihi,
            DATEDIFF(DAY, MAX(ra.RxReceteTarihi), ?) AS kac_gun_oldu,
            CAST(m.MusteriTakipli AS INT)           AS takipli
        FROM Musteri m
        INNER JOIN ReceteAna ra ON ra.RxMusteriId = m.MusteriId
        WHERE ra.RxSilme = 0
        GROUP BY m.MusteriId, m.MusteriAdiSoyadi, m.MusteriTelCep,
                 m.MusteriDogumTarihi, m.MusteriTakipli
        ORDER BY recete_adedi DESC
        """
        return self.db.sorgu_calistir(sql, (bitis.isoformat(),))

    def yaklasan_rapor_bitisleri(
        self,
        uyari_gun: int = 30,
        sadece_takipli: bool = False,
        sadece_telefonlu: bool = False,
        eski_gun: int = 0,
    ) -> List[Dict]:
        """Önümüzdeki uyari_gun içinde bitecek (veya bitmiş, eski_gun içinde) rapor
        teşhis satırlarını hasta bazlı gruplanmış olarak döndür.

        Her satır bir (rapor_ana, tanı_kodu, ICD) üçlüsüdür. UI tarafında
        hasta bazında gruplanabilir.
        """
        where_ekler = [
            "(rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)",
            "(ra.RaporAnaSilme IS NULL OR ra.RaporAnaSilme = 0)",
            "rrki.RRKIBitisTarihi IS NOT NULL",
            "rrki.RRKIBitisTarihi BETWEEN DATEADD(DAY, -?, ?) AND DATEADD(DAY, ?, ?)",
        ]
        params: list = [int(eski_gun), date.today().isoformat(),
                        int(uyari_gun), date.today().isoformat()]
        if sadece_takipli:
            where_ekler.append("m.MusteriTakipli = 1")
        if sadece_telefonlu:
            where_ekler.append(
                "m.MusteriTelCep IS NOT NULL AND LTRIM(RTRIM(m.MusteriTelCep)) <> ''"
            )

        sql = f"""
        SELECT
            m.MusteriId                              AS musteri_id,
            LTRIM(RTRIM(ISNULL(m.MusteriTCKN, ''))) AS tckn,
            LTRIM(RTRIM(m.MusteriAdiSoyadi))         AS hasta_adi,
            LTRIM(RTRIM(ISNULL(m.MusteriTelCep,''))) AS cep_tel,
            CAST(m.MusteriTakipli AS INT)            AS takipli,
            ra.RaporAnaId                            AS rapor_id,
            ra.RaporAnaRaporNo                       AS rapor_no,
            ra.RaporAnaRaporTarihi                   AS rapor_tarihi,
            rt.RaporTuruAdi                          AS rapor_turu,
            h.HastaneAdi                             AS hastane,
            rk.RaporKodu                             AS rapor_kodu,
            rk.RaporKodAciklama                      AS rapor_kod_aciklama,
            i.ICDKodu                                AS icd_kodu,
            i.ICDAciklamasi                          AS icd_aciklamasi,
            rrki.RRKIBaslamaTarihi                   AS baslama,
            rrki.RRKIBitisTarihi                     AS bitis,
            DATEDIFF(DAY, ?, rrki.RRKIBitisTarihi)   AS kalan_gun
        FROM RaporRaporKodlariICD rrki
        INNER JOIN RaporAna   ra  ON ra.RaporAnaId = rrki.RRKIRaporAnaId
        INNER JOIN Musteri    m   ON m.MusteriId   = ra.RaporAnaMusteriId
        LEFT  JOIN RaporKodlari rk ON rk.RaporKodId = rrki.RRKIRaporKodId
        LEFT  JOIN ICD        i   ON i.ICDId       = rrki.RRKIICDId
        LEFT  JOIN RaporTuru  rt  ON rt.RaporTuruId = ra.RaporAnaRaporTuruId
        LEFT  JOIN Hastane    h   ON h.HastaneId   = ra.RaporAnaHastaneId
        WHERE {" AND ".join(where_ekler)}
        ORDER BY m.MusteriAdiSoyadi ASC, rrki.RRKIBitisTarihi ASC
        """
        params.insert(0, date.today().isoformat())  # DATEDIFF için
        return self.db.sorgu_calistir(sql, tuple(params))

    def raporun_etkin_maddeleri(self, rapor_id: int) -> List[Dict]:
        """Bir raporun etken madde listesi."""
        sql = """
        SELECT
            em.EtkinMaddeAdi       AS etkin_madde,
            em.EtkinMaddeSGKKodu   AS sgk_kodu,
            rem.EtkinMaddeDoz      AS doz,
            rem.EtkinMaddeAdetMiktar   AS adet_miktar,
            rem.EtkinMaddeIcerikMiktar AS icerik_miktar
        FROM RaporEtkinMadde rem
        LEFT JOIN EtkinMadde em ON em.EtkinMaddeId = rem.EtkinMaddeId
        WHERE rem.EtkinMaddeRaporAnaId = ?
          AND (rem.EtkinMaddeSilme IS NULL OR rem.EtkinMaddeSilme = 0)
        ORDER BY em.EtkinMaddeAdi
        """
        return self.db.sorgu_calistir(sql, (int(rapor_id),))

    def hastanin_etkin_madde_ilaclari(
        self, musteri_id: int, sgk_kodu: str, lookback_gun: int = 365
    ) -> List[Dict]:
        """Hastanın verilen etken madde (SGK kodu) ile kullandığı ilaçlar.

        Bağlantı: Urun.UrunSGKKodId -> Etkin.EtkinId -> Etkin.EtkinKodu ==
        EtkinMadde.EtkinMaddeSGKKodu. Son 'lookback_gun' içinde yazdırılmış
        ReceteIlaclari ve EldenIlaclari kayıtlarından tekilleştirilmiş ilaç
        listesi döner (en son tarih öne gelir).
        """
        if not musteri_id or not sgk_kodu:
            return []
        sql = """
        SELECT urun_adi, MAX(son_tarih) AS son_tarih, SUM(adet) AS toplam_adet
        FROM (
            SELECT
                LTRIM(RTRIM(u.UrunAdi)) AS urun_adi,
                ra.RxReceteTarihi       AS son_tarih,
                ri.RIAdet               AS adet
            FROM ReceteIlaclari ri
            INNER JOIN ReceteAna ra ON ra.RxId = ri.RIRxId
            INNER JOIN Urun u       ON u.UrunId = ri.RIUrunId
            INNER JOIN Etkin e      ON e.EtkinId = u.UrunSGKKodId
            WHERE ra.RxMusteriId = ?
              AND e.EtkinKodu = ?
              AND (ri.RISilme IS NULL OR ri.RISilme = 0)
              AND (ra.RxSilme IS NULL OR ra.RxSilme = 0)
              AND ra.RxReceteTarihi >= DATEADD(day, -?, CAST(GETDATE() AS date))

            UNION ALL

            SELECT
                LTRIM(RTRIM(u.UrunAdi)) AS urun_adi,
                ea.RxReceteTarihi       AS son_tarih,
                ei.RIAdet               AS adet
            FROM EldenIlaclari ei
            INNER JOIN EldenAna ea  ON ea.RxId = ei.RIRxId
            INNER JOIN Urun u       ON u.UrunId = ei.RIUrunId
            INNER JOIN Etkin e      ON e.EtkinId = u.UrunSGKKodId
            WHERE ea.RxMusteriId = ?
              AND e.EtkinKodu = ?
              AND (ei.RISilme IS NULL OR ei.RISilme = 0)
              AND (ea.RxSilme IS NULL OR ea.RxSilme = 0)
              AND ea.RxReceteTarihi >= DATEADD(day, -?, CAST(GETDATE() AS date))
        ) t
        GROUP BY urun_adi
        ORDER BY son_tarih DESC
        """
        try:
            return self.db.sorgu_calistir(
                sql,
                (int(musteri_id), sgk_kodu, int(lookback_gun),
                 int(musteri_id), sgk_kodu, int(lookback_gun)),
            )
        except Exception as e:
            logger.warning("hastanin_etkin_madde_ilaclari hata: %s", e)
            return []

    def raporun_iliskili_ilaclari(self, rapor_id: int, musteri_id: int) -> List[Dict]:
        """Hastanın bu rapor numarasıyla yazdırılmış ilaçları (son 500 satır)."""
        sql = """
        SELECT TOP 200
            LTRIM(RTRIM(u.UrunAdi))  AS urun_adi,
            ri.RIAdet                AS adet,
            ri.RIBitisTarihi         AS bitis_tarihi,
            ra.RxReceteTarihi        AS recete_tarihi,
            ri.RIRaporNo             AS rapor_no
        FROM ReceteIlaclari ri
        INNER JOIN ReceteAna ra ON ra.RxId = ri.RIRxId
        LEFT  JOIN Urun u ON u.UrunId = ri.RIUrunId
        WHERE ra.RxMusteriId = ?
          AND ri.RIRaporNo = (SELECT RaporAnaRaporNo FROM RaporAna WHERE RaporAnaId = ?)
          AND ra.RxSilme = 0
          AND ri.RISilme = 0
        ORDER BY ra.RxReceteTarihi DESC
        """
        return self.db.sorgu_calistir(sql, (int(musteri_id), int(rapor_id)))

    def raporun_detayi(self, rapor_id: int, musteri_id: int) -> Dict:
        """Bir rapor için: tanı+ICD satırları, etken maddeler, ilişkili ilaçlar."""
        tanilar_sql = """
        SELECT
            rk.RaporKodu            AS rapor_kodu,
            rk.RaporKodAciklama     AS rapor_kod_aciklama,
            i.ICDKodu               AS icd_kodu,
            i.ICDAciklamasi         AS icd_aciklamasi,
            rrki.RRKIBaslamaTarihi  AS baslama,
            rrki.RRKIBitisTarihi    AS bitis
        FROM RaporRaporKodlariICD rrki
        LEFT JOIN RaporKodlari rk ON rk.RaporKodId = rrki.RRKIRaporKodId
        LEFT JOIN ICD i ON i.ICDId = rrki.RRKIICDId
        WHERE rrki.RRKIRaporAnaId = ?
          AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)
        ORDER BY rrki.RRKIBitisTarihi ASC
        """
        return {
            "tanilar": self.db.sorgu_calistir(tanilar_sql, (int(rapor_id),)),
            "etkin_maddeler": self.raporun_etkin_maddeleri(rapor_id),
            "ilaclar": self.raporun_iliskili_ilaclari(rapor_id, musteri_id),
        }

    def kapat(self):
        if self.db:
            self.db.kapat()
