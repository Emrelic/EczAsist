"""
Hastasi Olan Ilac Analiz Modulu - Veritabani Sorgulari

Sipariş modulunden cagrilarak son 12 ay icinde duzenli (≥2 alim) ve dusuk
hacimli (≤12 toplam recete) ilaclari tespit eder. Her hasta-ilac cifti icin
son alimdaki RIBitisTarihi'ni kullanir; UI tarafi cari ay / gelecek ay /
gecikmis filtresini kendi uygular.

GUVENLIK: Tum sorgular SELECT-only. Botanik EOS veritabanina YAZMA YAPILMAZ.
"""

import logging
from typing import List, Dict, Optional

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)


class HastasiOlanIlacDB:
    """Hastasi olan ilac analizi - son 12 ay recete gecmisi uzerinden."""

    GERIYE_AY = 12
    MIN_ALIM_SAYISI = 2
    MAX_TOPLAM_RECETE = 12

    # Antibiyotik / antifungal kelimeleri - urun adinda gecenler atlanir.
    # Bu modul kronik hastalik ilaclarina odaklanir; akut tedavide kullanilan
    # antibiyotik/antifungaller duzenli alim oruntusu uretmez. Listeye yeni
    # kelime eklemek istersen tekil olarak buradan ekleyebilirsin.
    EXCLUDE_KEYWORDS = (
        # Penisilinler / beta-laktam
        "AMOKSILIN", "AMOKSİSİLİN", "AMOKSISILIN", "AMOXIL", "AUGMENTIN",
        "AMOKLAVIN", "ALFOXIL", "LARGOPEN", "DEVA-MOX", "PENISILIN",
        "PENİSİLİN", "AMPISILIN", "AMPISILLIN", "OKSASILIN", "KLOKSASILIN",
        # Sefalosporinler
        "SEFAKLOR", "SEFUROKSIM", "SEFTRIAKSON", "SEFIKSIM", "SEFAZOLIN",
        "CEFAKS", "CEFAZOL", "DURATEC", "MAXIPIME", "ROCEPHIN", "AKSEF",
        "ZINNAT", "SUPRAX",
        # Makrolidler
        "AZITROMISIN", "AZİTROMİSİN", "KLARITROMISIN", "ERITROMISIN",
        "AZRO", "AZAX", "ZITROMAX", "ZITHROMAX", "KLACID", "RULID", "ROXID",
        "MAKROL",
        # Kinolonlar
        "SIPROFLOKSASIN", "SİPROFLOKSASIN", "LEVOFLOKSASIN", "MOKSIFLOKSASIN",
        "OFLOKSASIN", "CIPRO", "AVELOX", "TAVANIC", "CIPROXIN", "CIFLOX",
        "FLOKSAS",
        # Tetrasiklinler
        "DOKSISIKLIN", "DOKSİSİKLİN", "TETRASIKLIN", "MONODOX", "DOXIDAR",
        "TETRADOX",
        # Sulfonamidler
        "TRIMETOPRIM", "SULFAMETOKSAZOL", "BACTRIM", "SEPTRIN",
        # Diger antibiyotikler
        "METRONIDAZOL", "FLAGYL", "NIDAZOL",
        "NITROFURANTOIN", "FURADANTIN", "FURIDIN",
        "FOSFOMISIN", "MONUROL",
        "VANKOMISIN", "RIFAMPISIN", "RIFADIN",
        "LINEZOLID", "ZYVOX", "TIGESIKLIN", "TIGACYL",
        "GENTAMISIN", "TOBRAMISIN", "AMIKASIN", "NETILMISIN",
        "TEIKOPLANIN", "TARGOCID",
        "KLINDAMISIN", "DALACIN", "CLEOCIN",
        # Antifungaller
        "FLUKONAZOL", "FLUCONAZOLE", "DIFLUCAN", "FLUCAN", "ZOLAX",
        "ITRAKONAZOL", "ITRACONAZOLE", "SPORANOX",
        "KETOKONAZOL", "NIZORAL",
        "TERBINAFIN", "TERBİNAFİN", "LAMISIL", "TERBISIL", "FUNGOSAN",
        "MIKOFIN", "GRISEOFULVIN", "NISTATIN", "MIKOSTATIN", "AMPHOTERICIN",
        "EXODERIL", "MIKOZAL", "MIKAFUN", "VORICONAZOL",
    )

    def __init__(self, db: Optional[BotanikDB] = None):
        self.db = db or BotanikDB()
        if not self.db.conn:
            self.db.baglan()

    def _is_atlanan_kategori(self, urun_adi: str) -> bool:
        """Urun adi antibiyotik/antifungal kategorisinde mi? (substring match)"""
        if not urun_adi:
            return False
        ad_upper = urun_adi.upper()
        return any(kw in ad_upper for kw in self.EXCLUDE_KEYWORDS)

    def hastasi_olan_ilaclari_getir(self) -> List[Dict]:
        """Son 12 ayda hastasi olan ve tahmini bitisi yaklasan ilaclari dondur.

        Filtre uygulamaz; sonuclar tum tahmini bitis tarihleriyle gelir
        (gecikmis dahil). UI tarafi kendi cari ay / gelecek ay filtresini uygular.

        Her satir: {
            'UrunId', 'UrunAdi', 'Stok', 'UrunFiyatEtiket',
            'MusteriId', 'MusteriTCKN', 'MusteriAdiSoyadi',
            'AlimSayisi', 'SonAlimTarihi', 'SonKutu', 'OrtalamaKutu',
            'TahminiBitis', 'Olasilik', 'OnerilenMiktar'
        }
        """
        sql = """
        WITH son_donem AS (
            SELECT
                ra.RxMusteriId, ri.RIUrunId, ri.RIAdet, ri.RIBitisTarihi,
                ra.RxIslemTarihi, ri.RIId
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
              AND ra.RxIslemTarihi >= DATEADD(MONTH, -?, CAST(GETDATE() AS date))
              AND ra.RxMusteriId IS NOT NULL AND ra.RxMusteriId > 0
              AND ri.RIBitisTarihi IS NOT NULL
        ),
        ilac_toplami AS (
            SELECT RIUrunId, COUNT(*) AS toplam_recete
            FROM son_donem
            GROUP BY RIUrunId
            HAVING COUNT(*) <= ?
        ),
        hasta_ilac AS (
            SELECT
                s.RxMusteriId,
                s.RIUrunId,
                COUNT(*) AS alim_sayisi,
                MAX(s.RxIslemTarihi) AS son_islem,
                AVG(CAST(s.RIAdet AS FLOAT)) AS ort_kutu
            FROM son_donem s
            JOIN ilac_toplami it ON it.RIUrunId = s.RIUrunId
            GROUP BY s.RxMusteriId, s.RIUrunId
            HAVING COUNT(*) >= ?
        ),
        son_alim AS (
            SELECT
                hi.RxMusteriId,
                hi.RIUrunId,
                hi.alim_sayisi,
                hi.son_islem,
                hi.ort_kutu,
                (SELECT TOP 1 sd.RIBitisTarihi FROM son_donem sd
                 WHERE sd.RxMusteriId = hi.RxMusteriId
                   AND sd.RIUrunId = hi.RIUrunId
                   AND sd.RxIslemTarihi = hi.son_islem
                 ORDER BY sd.RIId DESC) AS tahmini_bitis,
                (SELECT TOP 1 sd.RIAdet FROM son_donem sd
                 WHERE sd.RxMusteriId = hi.RxMusteriId
                   AND sd.RIUrunId = hi.RIUrunId
                   AND sd.RxIslemTarihi = hi.son_islem
                 ORDER BY sd.RIId DESC) AS son_kutu
            FROM hasta_ilac hi
        )
        SELECT
            sa.RIUrunId AS UrunId,
            u.UrunAdi,
            (COALESCE(u.UrunStokDepo, 0) + COALESCE(u.UrunStokRaf, 0) + COALESCE(u.UrunStokAcik, 0)) AS Stok,
            u.UrunFiyatEtiket,
            sa.RxMusteriId AS MusteriId,
            m.MusteriTCKN,
            m.MusteriAdiSoyadi,
            sa.alim_sayisi AS AlimSayisi,
            sa.son_islem AS SonAlimTarihi,
            sa.son_kutu AS SonKutu,
            sa.ort_kutu AS OrtalamaKutu,
            sa.tahmini_bitis AS TahminiBitis
        FROM son_alim sa
        JOIN Urun u ON u.UrunId = sa.RIUrunId
        JOIN Musteri m ON m.MusteriId = sa.RxMusteriId
        WHERE u.UrunSilme = 0
          AND u.UrunUrunTipId = 1
          AND m.MusteriSilme = 0
          AND sa.tahmini_bitis IS NOT NULL
        ORDER BY sa.tahmini_bitis ASC, u.UrunAdi
        """

        params = (self.GERIYE_AY, self.MAX_TOPLAM_RECETE, self.MIN_ALIM_SAYISI)
        try:
            rows = self.db.sorgu_calistir(sql, params)
        except Exception as e:
            logger.error("Hastasi olan ilac sorgusu hatasi: %s", e)
            return []

        filtrelenmis: List[Dict] = []
        for r in rows:
            # 1) Antibiyotik / antifungal ilaclari ele
            if self._is_atlanan_kategori(r.get('UrunAdi', '')):
                continue

            # 2) Olasilik (alim sayisina gore)
            n = r.get('AlimSayisi') or 0
            if n >= 4:
                r['Olasilik'] = 100
            elif n == 3:
                r['Olasilik'] = 75
            elif n == 2:
                r['Olasilik'] = 50
            else:
                r['Olasilik'] = 0

            # 3) Onerilen miktar = ortalama kutunun yuvarlanmisi
            ort = r.get('OrtalamaKutu') or r.get('SonKutu') or 1
            try:
                r['OnerilenMiktar'] = max(1, int(round(float(ort))))
            except (TypeError, ValueError):
                r['OnerilenMiktar'] = 1

            # 4) Stok yeterli ise oneri olarak getirme
            #    (hasta gelse bile elimizdekinden karsilanabiliyor)
            try:
                stok = int(r.get('Stok') or 0)
            except (TypeError, ValueError):
                stok = 0
            if stok >= r['OnerilenMiktar']:
                continue

            filtrelenmis.append(r)

        return filtrelenmis

    def ilac_cikis_gecmisi_getir(self, urun_id: int) -> List[Dict]:
        """Bir ilacin son 12 aydaki tum cikislarini dondurur.

        Receteli satis (ReceteAna+ReceteIlaclari) ve elden satis (EldenAna+
        EldenIlaclari) birlikte, tarih DESC siralanmis halde.

        Her satir: {
            'Tarih', 'Saat', 'HastaAdi', 'TCKN', 'MusteriId',
            'Adet', 'Tur' ('Receteli' | 'Elden'), 'ReceteNo'
        }
        """
        if not urun_id:
            return []

        sql = """
        SELECT * FROM (
            SELECT
                CAST(ra.RxIslemTarihi AS date) AS Tarih,
                CONVERT(varchar(8), ra.RxIslemTarihi, 108) AS Saat,
                m.MusteriAdiSoyadi AS HastaAdi,
                m.MusteriTCKN AS TCKN,
                m.MusteriId AS MusteriId,
                ri.RIAdet AS Adet,
                N'Receteli' AS Tur,
                ra.RxEReceteNo AS ReceteNo
            FROM ReceteAna ra
            JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
            LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId AND m.MusteriSilme = 0
            WHERE ri.RIUrunId = ?
              AND ra.RxSilme = 0 AND ri.RISilme = 0
              AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
              AND ra.RxIslemTarihi >= DATEADD(MONTH, -?, CAST(GETDATE() AS date))

            UNION ALL

            SELECT
                CAST(ea.RxIslemTarihi AS date) AS Tarih,
                CONVERT(varchar(8), ea.RxIslemTarihi, 108) AS Saat,
                m.MusteriAdiSoyadi AS HastaAdi,
                m.MusteriTCKN AS TCKN,
                m.MusteriId AS MusteriId,
                ei.RIAdet AS Adet,
                N'Elden' AS Tur,
                CAST(ea.RxBelgeNo AS nvarchar(50)) AS ReceteNo
            FROM EldenAna ea
            JOIN EldenIlaclari ei ON ei.RIRxId = ea.RxId
            LEFT JOIN Musteri m ON m.MusteriId = ea.RxMusteriId AND m.MusteriSilme = 0
            WHERE ei.RIUrunId = ?
              AND ea.RxSilme = 0 AND ei.RISilme = 0
              AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
              AND ea.RxIslemTarihi >= DATEADD(MONTH, -?, CAST(GETDATE() AS date))
        ) AS Birlesik
        ORDER BY Tarih DESC, Saat DESC
        """
        params = (urun_id, self.GERIYE_AY, urun_id, self.GERIYE_AY)
        try:
            return self.db.sorgu_calistir(sql, params)
        except Exception as e:
            logger.error("Ilac cikis gecmisi sorgu hatasi: %s", e)
            return []

    def aylik_cikis_topla(self, urun_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """Bir grup ilac icin son 12 aydaki toplam cikisi UrunId basina aylik
        ('YYYY-MM') dagilim olarak dondurur. Receteli + Elden satislar birlikte.

        Returns:
            {UrunId: {'2025-06': 12, '2025-07': 9, ...}, ...}
        """
        if not urun_ids:
            return {}

        benzersiz = list({int(uid) for uid in urun_ids if uid})
        sonuc: Dict[int, Dict[str, int]] = {}

        BATCH = 500
        for i in range(0, len(benzersiz), BATCH):
            chunk = benzersiz[i:i + BATCH]
            placeholders = ','.join('?' * len(chunk))
            sql = f"""
            SELECT UrunId, YIL_AY, SUM(Adet) AS Toplam
            FROM (
                SELECT ri.RIUrunId AS UrunId,
                       FORMAT(ra.RxIslemTarihi, 'yyyy-MM') AS YIL_AY,
                       ri.RIAdet AS Adet
                FROM ReceteAna ra
                JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
                WHERE ra.RxSilme = 0 AND ri.RISilme = 0
                  AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                  AND ra.RxIslemTarihi >= DATEADD(MONTH, -?, CAST(GETDATE() AS date))
                  AND ri.RIUrunId IN ({placeholders})

                UNION ALL

                SELECT ei.RIUrunId AS UrunId,
                       FORMAT(ea.RxIslemTarihi, 'yyyy-MM') AS YIL_AY,
                       ei.RIAdet AS Adet
                FROM EldenAna ea
                JOIN EldenIlaclari ei ON ei.RIRxId = ea.RxId
                WHERE ea.RxSilme = 0 AND ei.RISilme = 0
                  AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                  AND ea.RxIslemTarihi >= DATEADD(MONTH, -?, CAST(GETDATE() AS date))
                  AND ei.RIUrunId IN ({placeholders})
            ) X
            GROUP BY UrunId, YIL_AY
            """
            params = (self.GERIYE_AY, *chunk, self.GERIYE_AY, *chunk)
            try:
                rows = self.db.sorgu_calistir(sql, params)
            except Exception as e:
                logger.error("Aylik cikis sorgusu hatasi: %s", e)
                continue

            for r in rows:
                uid = r.get('UrunId')
                yil_ay = r.get('YIL_AY')
                toplam = r.get('Toplam') or 0
                if uid is None or not yil_ay:
                    continue
                sonuc.setdefault(int(uid), {})[str(yil_ay)] = int(toplam)

        return sonuc
