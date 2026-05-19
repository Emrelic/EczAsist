"""
Nöbet Takvimi Modülü (Faz 2)

Eczane nöbet günlerini tespit eden ve takvim yöneten sistem.

Kapsam:
- Resmi (milli) tatil tarihleri — sabit liste, 2017-2030 otomatik populate
- Dini bayram tarihleri (Ramazan + Kurban) — WebFetch ile çekilip onaylanır
- Nöbet shift algoritması (mesai vs. gece nöbeti vs. pazar nöbeti vs. tatil nöbeti)
- Nöbet günü tespiti: bir tarih aralığında satış zamanı dağılımına bakarak

Eczane açılışı: 2017-05-23 (öncesi filtrelenir).

Mesai segmenti:
  Pzt-Cts 09:00-19:00 = mesai
  Pzt-Cmt 19:00 → ertesi gün 09:00 = gece nöbeti
  Paz 09:00 → Pzt 09:00 = pazar nöbeti (24 saat)
  Resmi/dini tatil 09:00 → ertesi gün 09:00 = tatil nöbeti (24 saat)

Nöbet onay eşiği (kullanıcı belirlemesi, 2026-05-18):
  Mesai dışı satış sayısı ≥ 10 VE ≥ 4 farklı saate yayılmış → o shift NÖBET olarak işaretlenir.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sabit milli tatil tarihleri (ay, gün) — her yıl aynı tarihte
# ---------------------------------------------------------------------------
MILLI_TATILLER_SABIT = [
    (1, 1,   "Yılbaşı"),
    (4, 23,  "Ulusal Egemenlik ve Çocuk Bayramı"),
    (5, 1,   "Emek ve Dayanışma Günü"),
    (5, 19,  "Atatürk'ü Anma Gençlik ve Spor Bayramı"),
    (7, 15,  "Demokrasi ve Millî Birlik Günü"),
    (8, 30,  "Zafer Bayramı"),
    (10, 29, "Cumhuriyet Bayramı"),
]

# Eczane açılış tarihi
ECZANE_ACILIS = date(2017, 5, 23)


# ---------------------------------------------------------------------------
# Dini bayram tarihleri (Türkiye / Diyanet İşleri Başkanlığı resmi takvimi)
# 2026 ve öncesi: Diyanet ilanı (kesin)
# 2027 ve sonrası: astronomik tahmin (Diyanet'in son ilanına bağlı, ±1 gün
# kayma olabilir). Kullanıcı manuel düzeltebilir (nobet_takvimi.db üzerinden).
#
# Format: (yil, "ramazan"|"kurban", baslangic_date)
# Ramazan 1. gün → 3 gün, Kurban 1. gün → 4 gün otomatik üretilir.
# ---------------------------------------------------------------------------
DINI_BAYRAM_BASLANGIC = [
    # Yıl, tür, Bayram 1. gün
    (2017, "ramazan", date(2017, 6, 25)),
    (2017, "kurban",  date(2017, 9, 1)),
    (2018, "ramazan", date(2018, 6, 15)),
    (2018, "kurban",  date(2018, 8, 21)),
    (2019, "ramazan", date(2019, 6, 4)),
    (2019, "kurban",  date(2019, 8, 11)),
    (2020, "ramazan", date(2020, 5, 24)),
    (2020, "kurban",  date(2020, 7, 31)),
    (2021, "ramazan", date(2021, 5, 13)),
    (2021, "kurban",  date(2021, 7, 20)),
    (2022, "ramazan", date(2022, 5, 2)),
    (2022, "kurban",  date(2022, 7, 9)),
    (2023, "ramazan", date(2023, 4, 21)),
    (2023, "kurban",  date(2023, 6, 28)),
    (2024, "ramazan", date(2024, 4, 10)),
    (2024, "kurban",  date(2024, 6, 16)),
    (2025, "ramazan", date(2025, 3, 30)),
    (2025, "kurban",  date(2025, 6, 6)),
    (2026, "ramazan", date(2026, 3, 20)),
    (2026, "kurban",  date(2026, 5, 26)),
    # Aşağıdakiler astronomik tahmin — Diyanet ilanı geldikçe düzeltilebilir
    (2027, "ramazan", date(2027, 3, 10)),
    (2027, "kurban",  date(2027, 5, 16)),
    (2028, "ramazan", date(2028, 2, 26)),
    (2028, "kurban",  date(2028, 5, 4)),
    (2029, "ramazan", date(2029, 2, 14)),
    (2029, "kurban",  date(2029, 4, 24)),
    (2030, "ramazan", date(2030, 2, 4)),
    (2030, "kurban",  date(2030, 4, 13)),
]

# Bayram süresi: Ramazan 3 gün, Kurban 4 gün
DINI_BAYRAM_GUN_SAYISI = {"ramazan": 3, "kurban": 4}

# Nöbet onay eşikleri
NOBET_MIN_SATIS = 10
NOBET_MIN_DAGILIM_SAAT = 4

# Mesai saatleri
MESAI_BAS_SAAT = 9
MESAI_BIT_SAAT = 19

# Shoulder (sarkma) penceresi tanımları (kullanıcı kuralı, 2026-05-18):
# 08:00-08:59 satışları için: o gün [SABAH_DERIN_BAS, SABAH_DERIN_BIT) sessizse mesai sayılır
# 19:00-19:59 satışları için: o gün AKSAM_DERIN_BAS+ ya da ertesi gün [00:00, AKSAM_DERIN_BIT)
#                              arası sessizse mesai sayılır
SABAH_SHOULDER_SAAT = 8     # 08:00-08:59 shoulder
AKSAM_SHOULDER_SAAT = 19    # 19:00-19:59 shoulder
SABAH_DERIN_BAS = 3         # 03:00 dahil
SABAH_DERIN_BIT = 8         # 08:00 hariç (sabah shoulder'dan önceki dilim)
AKSAM_DERIN_BAS = 23        # 23:00 dahil (o gün)
AKSAM_DERIN_BIT = 3         # 03:00 hariç (ertesi gün)


class NobetTakvimi:
    """Eczane nöbet takvim/tespit motoru."""

    def __init__(self, db_dosya: str = "nobet_takvimi.db"):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = Path(script_dir) / db_dosya
        self.conn: Optional[sqlite3.Connection] = None
        self._baglan()
        self._tablolari_olustur()
        self._milli_tatilleri_populate()
        self._dini_bayramlari_populate()

        # Cache: her çağrıda DB'ye gitme
        self._tatil_cache: Optional[Set[date]] = None

    # ------------------------------------------------------------------
    # DB kurulum
    # ------------------------------------------------------------------
    def _baglan(self):
        self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _tablolari_olustur(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS resmi_tatiller (
                tarih TEXT PRIMARY KEY,
                ad TEXT NOT NULL,
                tip TEXT NOT NULL CHECK(tip IN ('milli', 'dini')),
                kaynak TEXT,
                eklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_tatil_tip
            ON resmi_tatiller(tip)
        """)
        self.conn.commit()

    def _milli_tatilleri_populate(self, baslangic_yil: int = 2017, bitis_yil: int = 2030):
        """Sabit milli tatilleri DB'ye ekler (varsa atlar)."""
        c = self.conn.cursor()
        kayit_eklendi = 0
        for yil in range(baslangic_yil, bitis_yil + 1):
            for ay, gun, ad in MILLI_TATILLER_SABIT:
                tarih = date(yil, ay, gun)
                if tarih < ECZANE_ACILIS:
                    continue
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO resmi_tatiller (tarih, ad, tip, kaynak) VALUES (?, ?, 'milli', 'sabit')",
                        (tarih.isoformat(), ad)
                    )
                    if c.rowcount > 0:
                        kayit_eklendi += 1
                except Exception as e:
                    logger.warning(f"Milli tatil eklenirken hata ({tarih}): {e}")
        self.conn.commit()
        if kayit_eklendi:
            logger.info(f"NobetTakvimi: {kayit_eklendi} milli tatil eklendi")
        self._tatil_cache = None  # cache invalidate

    def _dini_bayramlari_populate(self):
        """Diyanet kaynaklı dini bayramları (2017-2030) DB'ye ekler — varsa atlar.

        Ramazan: 3 gün, Kurban: 4 gün — Bayram 1. günden başlayarak ardışık.
        2026 ve öncesi Diyanet ilanı; 2027+ astronomik tahmin (kullanıcı düzeltebilir).
        """
        c = self.conn.cursor()
        eklenen = 0
        for yil, tur, baslangic in DINI_BAYRAM_BASLANGIC:
            if baslangic < ECZANE_ACILIS:
                continue
            gun_sayisi = DINI_BAYRAM_GUN_SAYISI.get(tur, 3)
            for offset in range(gun_sayisi):
                tarih = baslangic + timedelta(days=offset)
                tur_etiket = "Ramazan Bayramı" if tur == "ramazan" else "Kurban Bayramı"
                ad = f"{tur_etiket} {offset + 1}. gün"
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO resmi_tatiller (tarih, ad, tip, kaynak) VALUES (?, ?, 'dini', 'diyanet')",
                        (tarih.isoformat(), ad)
                    )
                    if c.rowcount > 0:
                        eklenen += 1
                except Exception as e:
                    logger.warning(f"Dini bayram eklenirken hata ({tarih}): {e}")
        self.conn.commit()
        if eklenen:
            logger.info(f"NobetTakvimi: {eklenen} dini bayram günü eklendi (Diyanet kaynak)")
        self._tatil_cache = None

    # ------------------------------------------------------------------
    # Dini bayram (manuel/WebFetch ile populate edilir)
    # ------------------------------------------------------------------
    def dini_bayram_ekle(
        self,
        tarihler: List[Tuple[date, str]],
        kaynak: str = "manuel",
    ) -> int:
        """Çoklu dini bayram tarihini ekle. Mevcutsa atla.

        Args:
            tarihler: [(date, ad), ...] — ad örn. "Ramazan Bayramı 1. gün"
            kaynak: 'webfetch' veya 'manuel'

        Returns:
            int: eklenen kayıt sayısı
        """
        c = self.conn.cursor()
        eklenen = 0
        for tarih, ad in tarihler:
            if tarih < ECZANE_ACILIS:
                continue
            try:
                c.execute(
                    "INSERT OR IGNORE INTO resmi_tatiller (tarih, ad, tip, kaynak) VALUES (?, ?, 'dini', ?)",
                    (tarih.isoformat(), ad, kaynak)
                )
                if c.rowcount > 0:
                    eklenen += 1
            except Exception as e:
                logger.warning(f"Dini bayram eklenirken hata ({tarih}): {e}")
        self.conn.commit()
        self._tatil_cache = None
        return eklenen

    def dini_bayram_sil(self, tarih: date) -> bool:
        c = self.conn.cursor()
        c.execute(
            "DELETE FROM resmi_tatiller WHERE tarih = ? AND tip = 'dini'",
            (tarih.isoformat(),)
        )
        silindi = c.rowcount > 0
        self.conn.commit()
        if silindi:
            self._tatil_cache = None
        return silindi

    def tum_tatiller_getir(self) -> List[Dict]:
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT tarih, ad, tip, kaynak FROM resmi_tatiller ORDER BY tarih"
        ).fetchall()
        return [dict(r) for r in rows]

    def dini_bayramlar_getir(self) -> List[Dict]:
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT tarih, ad, kaynak FROM resmi_tatiller WHERE tip='dini' ORDER BY tarih"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Tatil seti cache
    # ------------------------------------------------------------------
    def _tatil_seti(self) -> Set[date]:
        if self._tatil_cache is None:
            c = self.conn.cursor()
            rows = c.execute("SELECT tarih FROM resmi_tatiller").fetchall()
            self._tatil_cache = {
                date.fromisoformat(r['tarih']) for r in rows
            }
        return self._tatil_cache

    # ------------------------------------------------------------------
    # Nöbet shift algoritması
    # ------------------------------------------------------------------
    def nobet_shift(self, dt: datetime) -> Optional[Dict]:
        """Bir datetime'ın hangi nöbet shift'ine ait olduğunu döndürür.

        Returns:
            None: mesai zamanı (Pzt-Cts 09:00-19:00, ve o gün tatil değil)
            dict: {
                'shift_tarihi': date — nöbetin başladığı gün
                'tip': 'gece' | 'pazar' | 'tatil'
            }

        Algoritma:
          - Bugün tatilse VE saat >= 9: tatil nöbeti başlıyor (shift_tarihi=bugün)
          - Bugün Pazar VE saat >= 9: pazar nöbeti başlıyor
          - Bugün Pzt-Cmt VE 19:00 <= saat: gece nöbeti başlıyor (shift_tarihi=bugün)
          - Saat < 9: önceki günün shift'inin uzantısı
              - dün tatil: tatil nöbeti devamı
              - dün Pazar: pazar nöbeti devamı
              - dün Pzt-Cmt: dünün gece nöbeti devamı
          - Pzt-Cmt 09:00-19:00 (ve tatil değil) = MESAİ → None
        """
        tarih = dt.date()
        saat = dt.hour
        weekday = dt.weekday()  # 0=Mon, 6=Sun
        tatiller = self._tatil_seti()

        onceki_gun = tarih - timedelta(days=1)
        onceki_weekday = (weekday - 1) % 7  # 0=Mon
        bugun_tatil = tarih in tatiller
        onceki_tatil = onceki_gun in tatiller

        # Saat < 9: önceki shift'in devamı (gece bitiş zamanı)
        if saat < MESAI_BAS_SAAT:
            if onceki_tatil:
                return {'shift_tarihi': onceki_gun, 'tip': 'tatil'}
            if onceki_weekday == 6:  # dün Pazar
                return {'shift_tarihi': onceki_gun, 'tip': 'pazar'}
            # dün Pzt-Cmt → o günün gece nöbeti
            if onceki_weekday in (0, 1, 2, 3, 4, 5):
                return {'shift_tarihi': onceki_gun, 'tip': 'gece'}
            # Theoretically unreachable
            return {'shift_tarihi': onceki_gun, 'tip': 'gece'}

        # Saat >= 9
        if bugun_tatil:
            return {'shift_tarihi': tarih, 'tip': 'tatil'}
        if weekday == 6:  # Pazar
            return {'shift_tarihi': tarih, 'tip': 'pazar'}
        # Pzt-Cmt
        if weekday in (0, 1, 2, 3, 4, 5):
            if MESAI_BAS_SAAT <= saat < MESAI_BIT_SAAT:
                return None  # MESAİ
            elif saat >= MESAI_BIT_SAAT:
                return {'shift_tarihi': tarih, 'tip': 'gece'}

        return None  # safety

    # ------------------------------------------------------------------
    # Nöbet günü tespiti (toplu satış listesi üzerinden)
    # ------------------------------------------------------------------
    def _shoulder_aktivite_haritalari(
        self, satislar: List[Dict]
    ) -> Tuple[Dict[date, int], Dict[date, int]]:
        """Her takvim günü D için derin gece satış sayılarını hesapla.

        sabah_derin[D] = D 03:00–08:00 arası satış sayısı (önceki nöbetin son saatleri)
        aksam_derin[D] = D 23:00+ + D+1 00:00–03:00 arası satış sayısı (sonraki nöbetin ilk saatleri)
        """
        from collections import defaultdict
        sabah: Dict[date, int] = defaultdict(int)
        aksam: Dict[date, int] = defaultdict(int)
        for s in satislar:
            dt = s.get('tarih')
            if not hasattr(dt, 'hour'):
                continue
            d = dt.date()
            h = dt.hour
            if SABAH_DERIN_BAS <= h < SABAH_DERIN_BIT:
                sabah[d] += 1
            if h >= AKSAM_DERIN_BAS:
                aksam[d] += 1
            elif h < AKSAM_DERIN_BIT:
                # Ertesi günün 00:00-03:00 satışı → önceki günün akşam derin'ine yazılır
                aksam[d - timedelta(days=1)] += 1
        return dict(sabah), dict(aksam)

    def _shoulder_mesai_mi(
        self,
        dt: datetime,
        sabah_derin: Dict[date, int],
        aksam_derin: Dict[date, int],
    ) -> bool:
        """Shoulder kuralı: 08:00-08:59 veya 19:00-19:59 satışı, o gün için
        derin gece sessiz ise mesai sayılır (nöbet sayılmaz).

        Sadece Pzt-Cmt mesai günlerinde uygulanır. Pazar ve resmi/dini tatil
        günlerinde tüm gün nöbet olduğu için shoulder kuralı uygulanmaz.
        """
        d = dt.date()
        wd = dt.weekday()  # 0=Pzt, 6=Paz
        if wd == 6:  # Pazar
            return False
        if d in self._tatil_seti():
            return False

        h = dt.hour
        if h == SABAH_SHOULDER_SAAT:
            # 08:00-08:59: o gün 03:00-08:00 sessizse mesai
            return sabah_derin.get(d, 0) == 0
        if h == AKSAM_SHOULDER_SAAT:
            # 19:00-19:59: o gün 23:00+ ve ertesi 00:00-03:00 sessizse mesai
            return aksam_derin.get(d, 0) == 0
        return False

    def nobet_shiftlerini_tespit_et(
        self,
        satislar: List[Dict],
        min_satis: int = NOBET_MIN_SATIS,
        min_saat_dagilimi: int = NOBET_MIN_DAGILIM_SAAT,
    ) -> Dict[date, Dict]:
        """Verilen satış listesini nöbet shift'lerine göre grupla ve
        eşiği aşan shift'leri ONAYLI nöbet olarak işaretle.

        Shoulder kuralı: 08:00-09:00 ve 19:00-20:00 sarkma satışları, derin
        gece (03:00-08:00 sabah, 23:00→03:00 akşam) sessiz ise mesai sayılır
        (sadece Pzt-Cmt mesai günlerinde). Bkz. _shoulder_mesai_mi.

        Args:
            satislar: [{'tarih': datetime, ...}, ...] her satışın datetime'ı
            min_satis: bir shift'in nöbet sayılması için min satış sayısı
            min_saat_dagilimi: shift'teki satışların min farklı saat sayısı

        Returns:
            {shift_tarihi(date): {
                'tip': 'gece'|'pazar'|'tatil',
                'satis_sayisi': int,
                'distinct_saat': int,
                'onayli_nobet': bool,
                'satislar': list,  # bu shift'e ait satışlar
                'shoulder_elenen': int,  # mesai sayılarak elenen shoulder satış sayısı
            }, ...}
        """
        sabah_derin, aksam_derin = self._shoulder_aktivite_haritalari(satislar)
        shiftler: Dict[date, Dict] = {}
        shoulder_elenen_global = 0

        for s in satislar:
            dt = s.get('tarih')
            if dt is None:
                continue
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except ValueError:
                    continue

            # Shoulder kontrolü: derin gece sessiz mi?
            if self._shoulder_mesai_mi(dt, sabah_derin, aksam_derin):
                shoulder_elenen_global += 1
                continue  # mesai sayılır, shift'e dahil edilmez

            shift_bilgi = self.nobet_shift(dt)
            if shift_bilgi is None:
                continue  # MESAİ — atlanır

            shift_tarihi = shift_bilgi['shift_tarihi']
            tip = shift_bilgi['tip']

            if shift_tarihi not in shiftler:
                shiftler[shift_tarihi] = {
                    'tip': tip,
                    'satis_sayisi': 0,
                    'saatler': set(),
                    'satislar': [],
                }
            shiftler[shift_tarihi]['satis_sayisi'] += 1
            shiftler[shift_tarihi]['saatler'].add(dt.hour)
            shiftler[shift_tarihi]['satislar'].append(s)

        # Onay etiketleme
        for tarih, info in shiftler.items():
            info['distinct_saat'] = len(info['saatler'])
            info['onayli_nobet'] = (
                info['satis_sayisi'] >= min_satis
                and info['distinct_saat'] >= min_saat_dagilimi
            )
            # saatler set'ini JSON-friendly liste olarak bırakmamak için sil
            info['saatler'] = sorted(info['saatler'])

        return shiftler

    def onayli_nobet_satislari(
        self,
        satislar: List[Dict],
        min_satis: int = NOBET_MIN_SATIS,
        min_saat_dagilimi: int = NOBET_MIN_DAGILIM_SAAT,
    ) -> List[Dict]:
        """Sadece onaylı nöbet shift'lerine ait satışları döndürür.

        Her satışın 'shift_tarihi' ve 'shift_tipi' alanları enjekte edilir.
        """
        shiftler = self.nobet_shiftlerini_tespit_et(
            satislar, min_satis=min_satis, min_saat_dagilimi=min_saat_dagilimi
        )
        sonuc = []
        for shift_tarihi, info in shiftler.items():
            if not info['onayli_nobet']:
                continue
            for s in info['satislar']:
                yeni = dict(s)
                yeni['shift_tarihi'] = shift_tarihi
                yeni['shift_tipi'] = info['tip']
                sonuc.append(yeni)
        return sonuc

    def kapat(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_takvim_instance: Optional[NobetTakvimi] = None


def get_nobet_takvimi() -> NobetTakvimi:
    global _takvim_instance
    if _takvim_instance is None:
        _takvim_instance = NobetTakvimi()
    return _takvim_instance


# ---------------------------------------------------------------------------
# Komut satırı test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    nt = NobetTakvimi()

    print("=" * 60)
    print(f"DB: {nt.db_yolu}")
    print(f"Toplam tatil: {len(nt._tatil_seti())}")
    print(f"  Milli: {sum(1 for t in nt.tum_tatiller_getir() if t['tip']=='milli')}")
    print(f"  Dini:  {sum(1 for t in nt.tum_tatiller_getir() if t['tip']=='dini')}")

    print("\n--- nobet_shift algoritma testleri ---")
    testler = [
        # (datetime, beklenen tip ya da None)
        (datetime(2026, 5, 18, 14, 0),  None,    "Pzt 14:00 - mesai"),
        (datetime(2026, 5, 18, 19, 30), "gece",  "Pzt 19:30 - gece nöbeti başlıyor"),
        (datetime(2026, 5, 19, 6, 0),   "gece",  "Sal 06:00 - Pzt gece nöbeti devamı"),
        (datetime(2026, 5, 17, 12, 0),  "pazar", "Pazar 12:00 - pazar nöbeti"),
        (datetime(2026, 5, 18, 5, 0),   "pazar", "Pzt 05:00 - Pazar nöbeti devamı"),
        (datetime(2026, 5, 23, 14, 0),  None,    "Cmt 14:00 - mesai"),
        (datetime(2026, 5, 23, 21, 0),  "gece",  "Cmt 21:00 - Cmt gece nöbeti"),
        (datetime(2026, 1, 1, 12, 0),   "tatil", "1 Ocak öğle - tatil nöbeti"),
        (datetime(2026, 10, 29, 14, 0), "tatil", "29 Ekim - tatil nöbeti"),
    ]
    for dt, beklenen, aciklama in testler:
        sonuc = nt.nobet_shift(dt)
        gercek_tip = sonuc['tip'] if sonuc else None
        gercek_shift = sonuc['shift_tarihi'] if sonuc else '-'
        ok = "OK " if gercek_tip == beklenen else "FAIL"
        print(f"  [{ok}] {dt.strftime('%a %d.%m.%Y %H:%M')} -> tip={gercek_tip} shift={gercek_shift}  ({aciklama})")
