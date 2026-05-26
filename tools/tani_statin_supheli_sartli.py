# -*- coding: utf-8 -*-
"""
Tanı scripti: statin reçeteleri için ŞÜPHELİ vs ŞARTLI_UYGUN sınıflandırma.

Kullanıcı kuralı:
  - Sadece "6 ay ara" atomu KE → ŞARTLI_UYGUN olmalı (eczacımızdan alımlı olmayan
    ilaçlar için Medula manuel kontrolü gerek; başka eksik yok).
  - 6 ay ara DIŞINDA da KE atom(lar)  → ŞÜPHELİ doğru sonuç.

Bu script, listede verilen reçeteleri Botanik EOS'tan SELECT ile okuyup statin
kontrol pipeline'ından geçirir, her reçetenin atom-bazlı sonucunu rapor eder
ve kategoriye atar.

Çıktı:
  - stdout: özet istatistik
  - tools/tani_statin_sonuc.txt: reçete-bazlı detaylı rapor

KIRMIZI ÇİZGİ: Sadece SELECT. BotanikDB guard üzerinden çalışır.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

# Windows console UTF-8 fix
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Proje köküne yol
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from botanik_db import BotanikDB  # noqa: E402
from recete_kontrol.sut_kontrolleri import kontrol_statin  # noqa: E402
from recete_kontrol.base_kontrol import (  # noqa: E402
    KontrolSonucu, SartDurumu, SartSonuc, KontrolRaporu)


# ───────────────────────────────────────────────────────────────────────
# REÇETE LİSTESİ — (TC, sistem_recete_no)
# ───────────────────────────────────────────────────────────────────────
RECETELER: List[Tuple[str, str]] = [
    ("13856626232", "3MG5YOR"),  # YASEMİN KARTAL
    ("49321848762", "3MCGBZL"),  # SERDAR YAVUZ
    ("40246498018", "3M9WTTU"),  # CENGİZ PEHLİVAN
    ("10289473082", "3M99S4D"),  # DÜRİYE KİBAR
    ("40777802162", "3M5HM7G"),  # YAĞMUR DOĞAN
    ("24685400740", "3LXJRA0"),  # HÜSEYİN HERGÜL
    ("29558199592", "3LRNTUL"),  # MEHMET ÇITAK
    ("24088991876", "3LQ879Z"),  # HASAN KINCIR
    ("22517614198", "3LDD88W"),  # FATMA BEHREM
    ("35974793894", "3KN8GA6"),  # FADİM YÜKSEL
    ("17939225794", "3KE8YAB"),  # VAHDETTİN TEMUR
    ("10289473082", "3KAYIH5"),  # DÜRİYE KİBAR
    ("40777802162", "3K6QROK"),  # YAĞMUR DOĞAN
    ("51487562468", "3K2L6GN"),  # SİNAN DEMİRHAN
    ("17378785422", "3JZP2AY"),  # AYŞE BUDAK
    ("18436737728", "3JAHW0G"),  # HALİME ERKANAT
    ("22517614198", "3J3CP44"),  # FATMA BEHREM
    ("43534008210", "3J3O69S"),  # RUKEN AVCI
    ("13203069026", "3IEY1T9"),  # LATİF KARTAL
    ("22517614198", "3IDVCRE"),  # FATMA BEHREM
    ("31558181798", "3I8HS3H"),  # EDİBE KILIÇLI
    ("17378785422", "3HV3I3T"),  # AYŞE BUDAK
    ("44173703436", "3HPNSHH"),  # HAMZA ŞİRİN
    ("40777802162", "3HLD63A"),  # YAĞMUR DOĞAN
    ("38323610286", "3HKE8ER"),  # GÜLDANE AKÇADAĞ
    ("51487562468", "3HKETUW"),  # SİNAN DEMİRHAN
    ("35974793894", "3HHDQC7"),  # FADİM YÜKSEL
    ("31705518460", "3GGGZ8Z"),  # HÜSEYİN ZİREK
    ("22456642900", "3GGL550"),  # AFİFE ODABAŞIOĞLU
    ("69844191350", "3FUD0CI"),  # SABİRE YILDIZ
    ("40777802162", "3FNDAXV"),  # YAĞMUR DOĞAN
    ("29195149752", "3FIHC6Y"),  # GÜRKAN KARAKURT
    ("13203069026", "3F395KX"),  # LATİF KARTAL
    ("35974793894", "3EWJHJV"),  # FADİM YÜKSEL
    ("30656316842", "3ETC553"),  # AHMET KILIÇALP
    ("60049442728", "3EQW5WE"),  # MUZAFFER ŞAHİN
    ("22517614198", "3E53FNC"),  # FATMA BEHREM
    ("19157464894", "3D918EA"),  # MÜRVET ÖZDURAN
    ("69844191350", "3CZHVST"),  # SABİRE YILDIZ
    ("13203069026", "3CNV0FH"),  # LATİF KARTAL
    ("19157464894", "3CE71TF"),  # MÜRVET ÖZDURAN
    ("13203069026", "3BUSBWY"),  # LATİF KARTAL
    ("44173703436", "3BCL756"),  # HAMZA ŞİRİN
    ("19403025138", "39OJ381"),  # ERDAL KAHRAMAN
    ("35974793894", "39A2KSH"),  # FADİM YÜKSEL
    ("19570738886", "3824NW2"),  # BAYRAM KARABAYIR
    ("17369785578", "35R8YS9"),  # HAVVA OYAN
    ("11509840738", "35P04HH"),  # YAŞAR YILMAZ
    ("22517614198", "358Q3SN"),  # FATMA BEHREM
    ("10556897146", "34OY9UF"),  # ÜMMÜGÜLSÜM AKBAL
    ("22517614198", "34IJVDW"),  # FATMA BEHREM
    ("45481579980", "336NPF7"),  # OSMAN NURİ ODABAŞI
    ("34084524886", "3349C2X"),  # DURSUN ESA
    ("26267459450", "32NNT1P"),  # BASRİ ASLAN
    ("34084524886", "30PAD23"),  # DURSUN ESA
    ("44674534232", "2Z0W7FW"),  # HATİCE KÖSE
    ("18919593780", "2YG6NNT"),  # HURŞİT KARABAŞ
    ("44674534232", "2VR4ZYO"),  # HATİCE KÖSE
    ("18919593780", "2UWWXRP"),  # HURŞİT KARABAŞ
    ("17165081188", "2TLLPDC"),  # KAMİL KAPIYOLDAŞ
    ("44674534232", "2SFVBQ0"),  # HATİCE KÖSE
    ("18919593780", "2RY3MNA"),  # HURŞİT KARABAŞ
    ("12373979258", "2RQ85MG"),  # RECEP ERTEN
    ("53245806722", "2RB94JW"),  # EMEL CENGİZ
    ("61900066480", "2R8W2UK"),  # REFİKA SARIGÜL
    ("12373979258", "2PPCPUZ"),  # RECEP ERTEN
]


STATIN_ATC_PREFIX = ("C10AA", "C10BA", "C10BX")
STATIN_AD_IPUC = ("STATIN", "ATORVAS", "ROSUVAS", "SIMVAS", "PRAVAS",
                  "FLUVAS", "PITAVAS", "LIPITOR", "CRESTOR", "ROZACT",
                  "EZETIMIB", "EZETROL", "INEGY")


def _yas_hesapla(dogum_tarihi, ref_tarih=None) -> Optional[int]:
    if dogum_tarihi is None:
        return None
    ref = ref_tarih or date.today()
    if hasattr(dogum_tarihi, 'date'):
        dt = dogum_tarihi.date()
    elif hasattr(dogum_tarihi, 'year'):
        dt = dogum_tarihi
    else:
        try:
            dt = datetime.strptime(str(dogum_tarihi)[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    yas = ref.year - dt.year - ((ref.month, ref.day) < (dt.month, dt.day))
    return yas if 0 <= yas <= 130 else None


def _is_statin(ilac_adi: str, atc_kodu: str) -> bool:
    a = (atc_kodu or "").upper().strip()
    if any(a.startswith(p) for p in STATIN_ATC_PREFIX):
        return True
    ad = (ilac_adi or "").upper()
    return any(s in ad for s in STATIN_AD_IPUC)


SQL_RECETE = """
SELECT TOP 1
    ra.RxId, ra.RxEReceteNo, ra.RxSgkIslemNo,
    ra.RxIslemTarihi, ra.RxKayitTarihi,
    ra.RxMusteriId,
    m.MusteriAdiSoyadi, m.MusteriTCKN, m.MusteriDogumTarihi
FROM ReceteAna ra
INNER JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
WHERE ra.RxSgkIslemNo = ?
  AND m.MusteriTCKN = ?
  AND (ra.RxSilme IS NULL OR ra.RxSilme = 0)
ORDER BY ra.RxId DESC
"""

SQL_ILACLAR = """
SELECT
    ri.RIId, ri.RIUrunId, ri.RIRaporKodId, ri.RIRaporNo,
    u.UrunAdi, atc.ATCKodu, atc.ATCTurkce,
    rk.RaporKodu, rk.RaporKodAciklama
FROM ReceteIlaclari ri
LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId
LEFT JOIN RaporKodlari rk ON rk.RaporKodId = ri.RIRaporKodId
WHERE ri.RIRxId = ?
  AND (ri.RISilme IS NULL OR ri.RISilme = 0)
"""

SQL_RAPOR_EŞLE = """
SELECT TOP 1
    COALESCE(direkt.RaporAnaId, fallback.RaporAnaId) AS RaporAnaId,
    COALESCE(direkt.RaporAnaAciklamalar, fallback.RaporAnaAciklamalar)
        AS RaporAnaAciklamalar,
    COALESCE(direkt.RaporAnaRaporTarihi, fallback.RaporAnaRaporTarihi)
        AS RaporAnaRaporTarihi,
    sr.SRRaporKodu
FROM SecilenRapor sr
OUTER APPLY (
    SELECT TOP 1
        rap.RaporAnaId, rap.RaporAnaAciklamalar, rap.RaporAnaRaporTarihi
    FROM RaporAna rap
    WHERE rap.RaporAnaMusteriId = ?
      AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
      AND (CAST(rap.RaporAnaRaporNo    AS NVARCHAR(50)) = sr.SRRaporNo
        OR CAST(rap.RaporAnaRaporTakipNo AS NVARCHAR(50)) = sr.SRRaporNo
        OR CAST(rap.RaporAnaProtokolNo   AS NVARCHAR(50)) = sr.SRRaporNo)
) direkt
OUTER APPLY (
    SELECT TOP 1
        rap.RaporAnaId, rap.RaporAnaAciklamalar, rap.RaporAnaRaporTarihi
    FROM RaporAna rap
    INNER JOIN RaporRaporKodlariICD rrk ON rrk.RRKIRaporAnaId = rap.RaporAnaId
    INNER JOIN RaporKodlari rk ON rk.RaporKodId = rrk.RRKIRaporKodId
    WHERE direkt.RaporAnaId IS NULL
      AND rap.RaporAnaMusteriId = ?
      AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
      AND (rrk.RRKISilme IS NULL OR rrk.RRKISilme = 0)
      AND rk.RaporKodu = sr.SRRaporKodu
      AND sr.SRRaporKodu IS NOT NULL AND sr.SRRaporKodu <> ''
    ORDER BY rap.RaporAnaRaporTarihi DESC
) fallback
WHERE sr.SRRxId = ? AND sr.SRUrunId = ?
  AND sr.SRRaporNo IS NOT NULL AND sr.SRRaporNo <> ''
ORDER BY sr.SRId DESC
"""

SQL_RAPOR_EKBILGI = """
SELECT REBTuru, REBDeger, REBAciklama
FROM RaporEkBilgi
WHERE REBRaporAnaId = ?
"""

SQL_RAPOR_DOKTOR_BRANS = """
SELECT TOP 1 b.BransAdi
FROM RaporDoktor rd
LEFT JOIN Brans b ON b.BransId = rd.RaporDoktorBransId
WHERE rd.RaporDoktorRaporAnaId = ?
  AND (rd.RaporDoktorSilme IS NULL OR rd.RaporDoktorSilme = 0)
"""

SQL_RECETE_TESHISLERI = """
SELECT i.ICDKodu
FROM ReceteIlaclari ri
INNER JOIN ReceteIlacTeshis rt ON rt.RITeshisRIId = ri.RIId
INNER JOIN ICD i ON i.ICDId = rt.RITeshisICDId
WHERE ri.RIRxId = ?
  AND (ri.RISilme IS NULL OR ri.RISilme = 0)
  AND (rt.RITeshisSilme IS NULL OR rt.RITeshisSilme = 0)
"""


def _ilac_sonuc_olustur(db: BotanikDB, rx_row: Dict,
                        ilac_row: Dict) -> Dict:
    """Bir ilaç satırı için kontrol_statin'in beklediği ilac_sonuc dict'ini üret."""
    musteri_id = rx_row["RxMusteriId"]
    rx_id = rx_row["RxId"]
    urun_id = ilac_row["RIUrunId"]
    ilac_adi = (ilac_row.get("UrunAdi") or "").strip()

    rap_rows = db.sorgu_calistir(
        SQL_RAPOR_EŞLE,
        (musteri_id, musteri_id, rx_id, urun_id))
    rap_row = rap_rows[0] if rap_rows else {}

    rapor_ana_id = rap_row.get("RaporAnaId")
    rapor_aciklamalari: List[str] = []
    if rap_row.get("RaporAnaAciklamalar"):
        for parca in str(rap_row["RaporAnaAciklamalar"]).replace(
                "\r\n", "\n").split("\n"):
            parca = parca.strip()
            if parca:
                rapor_aciklamalari.append(parca)

    # Rapor Ek Bilgi
    if rapor_ana_id:
        eb_rows = db.sorgu_calistir(SQL_RAPOR_EKBILGI, (rapor_ana_id,))
        for r in eb_rows:
            parts = []
            if r.get("REBTuru"):
                parts.append(str(r["REBTuru"]))
            if r.get("REBDeger"):
                parts.append(str(r["REBDeger"]))
            if r.get("REBAciklama"):
                parts.append(str(r["REBAciklama"]))
            if parts:
                rapor_aciklamalari.append(": ".join(parts))

    # Rapor doktoru branşı
    brans = ""
    if rapor_ana_id:
        b_rows = db.sorgu_calistir(SQL_RAPOR_DOKTOR_BRANS, (rapor_ana_id,))
        if b_rows:
            brans = (b_rows[0].get("BransAdi") or "").strip()

    rapor_kodu = ((ilac_row.get("RaporKodu") or "").strip()
                  or (rap_row.get("SRRaporKodu") or "").strip())

    # Reçete teşhisleri (ICD)
    teshis_rows = db.sorgu_calistir(SQL_RECETE_TESHISLERI, (rx_id,))
    recete_teshisleri = [r["ICDKodu"] for r in teshis_rows
                          if r.get("ICDKodu")]

    yas = _yas_hesapla(rx_row.get("MusteriDogumTarihi"),
                        rx_row.get("RxIslemTarihi")
                        or rx_row.get("RxKayitTarihi"))

    return {
        "ilac_adi": ilac_adi,
        "rapor_kodu": rapor_kodu,
        "rapor_kodu_aciklama": (ilac_row.get("RaporKodAciklama") or "").strip(),
        "recete_teshisleri": recete_teshisleri,
        "rapor_aciklamalari": rapor_aciklamalari,
        "recete_aciklamalari": [],
        "mesaj_metni": "",
        "doktor_uzmanligi": brans,
        "hasta_yasi": yas,
        "rapor_ana_id": rapor_ana_id,
    }


def _atom_kategori(rapor: KontrolRaporu) -> Tuple[str, List[str], List[str]]:
    """Atom listesini incele, kategori + KE atom adları + YOK atom adları döndür.

    Kategoriler:
      A — Sadece "6 ay ara" atomu KE (sartli_atom). Diğer hesaplanabilir
          atomlar VAR. Mantıkça SARTLI_UYGUN olmalı.
      B — 6 ay ara KE + başka KE atom(lar) (sartli_atom DEĞİL). Karışık KE.
      C — 6 ay ara VAR ama başka atom(lar) KE. Bu reçete 6 ay ile ilgisiz
          ŞÜPHELİ.
      D — Tüm atomlar VAR. Mantıkça UYGUN (bu listede olmamalı).
      E — En az bir atom YOK. Mantıkça UYGUN_DEGIL.
      X — Diğer (boş atom listesi vs.)
    """
    ke_atomlar = []
    yok_atomlar = []
    sartli_ke = []
    non_sartli_ke = []
    alti_ay_var = False
    alti_ay_ke = False

    for s in rapor.sartlar:
        durum = s.durum if isinstance(s.durum, SartDurumu) else \
            SartDurumu(s.durum)
        if durum == SartDurumu.YOK:
            yok_atomlar.append(s.ad)
        elif durum == SartDurumu.KONTROL_EDILEMEDI:
            ke_atomlar.append(s.ad)
            if getattr(s, "sartli_atom", False):
                sartli_ke.append(s.ad)
            else:
                non_sartli_ke.append(s.ad)
        elif durum == SartDurumu.VAR:
            if "6+ ay ara" in s.ad or "6 ay" in s.ad.lower():
                alti_ay_var = True

        if "6+ ay ara" in s.ad or "6 ay" in s.ad.lower():
            if durum == SartDurumu.KONTROL_EDILEMEDI:
                alti_ay_ke = True

    # E: en az bir YOK var → UYGUN_DEGIL kategorisi (ŞÜPHELİ'den farklı)
    if yok_atomlar and rapor.sonuc == KontrolSonucu.UYGUN_DEGIL:
        return ("E_UYGUN_DEGIL", ke_atomlar, yok_atomlar)
    if not ke_atomlar:
        if yok_atomlar:
            return ("E_UYGUN_DEGIL", ke_atomlar, yok_atomlar)
        return ("D_UYGUN", ke_atomlar, yok_atomlar)

    # KE var
    if alti_ay_ke and len(non_sartli_ke) == 0:
        # Sadece şartlı atom(lar) KE → mantıken SARTLI_UYGUN olmalı
        return ("A_SADECE_6AY_KE", ke_atomlar, yok_atomlar)
    if alti_ay_ke and len(non_sartli_ke) > 0:
        return ("B_6AY_VE_BASKA_KE", ke_atomlar, yok_atomlar)
    if not alti_ay_ke and len(non_sartli_ke) > 0:
        return ("C_BASKA_KE_6AY_VAR", ke_atomlar, yok_atomlar)
    return ("X_DIGER", ke_atomlar, yok_atomlar)


def _calistir():
    db = BotanikDB()
    if not db.baglan():
        print("HATA: Botanik EOS bağlantısı kurulamadı.")
        return

    out_path = os.path.join(_THIS_DIR, "tani_statin_sonuc.txt")
    sayac = {
        "A_SADECE_6AY_KE": 0,
        "B_6AY_VE_BASKA_KE": 0,
        "C_BASKA_KE_6AY_VAR": 0,
        "D_UYGUN": 0,
        "E_UYGUN_DEGIL": 0,
        "X_DIGER": 0,
        "RECETE_YOK": 0,
        "STATIN_YOK": 0,
    }
    sonuc_satirlari: List[str] = []

    for i, (tc, recete_no) in enumerate(RECETELER, 1):
        rx_rows = db.sorgu_calistir(SQL_RECETE, (recete_no, tc))
        if not rx_rows:
            sayac["RECETE_YOK"] += 1
            sonuc_satirlari.append(
                f"[{i:>3}] TC={tc} Rx={recete_no} → REÇETE_YOK (DB'de bulunamadı)")
            continue
        rx = rx_rows[0]
        ilac_rows = db.sorgu_calistir(SQL_ILACLAR, (rx["RxId"],))

        statin_ilaclar = [r for r in ilac_rows
                            if _is_statin(r.get("UrunAdi", ""),
                                          r.get("ATCKodu", ""))]
        if not statin_ilaclar:
            sayac["STATIN_YOK"] += 1
            ad_list = ", ".join((r.get("UrunAdi") or "?")[:20]
                                for r in ilac_rows)
            sonuc_satirlari.append(
                f"[{i:>3}] TC={tc} Rx={recete_no} {rx['MusteriAdiSoyadi']:20}"
                f" → STATIN_YOK (ilaçlar: {ad_list})")
            continue

        # İlk statin satırı üzerinden kontrol yap
        for il in statin_ilaclar:
            ilac_sonuc = _ilac_sonuc_olustur(db, rx, il)
            try:
                rapor = kontrol_statin(ilac_sonuc)
            except Exception as e:
                sonuc_satirlari.append(
                    f"[{i:>3}] TC={tc} Rx={recete_no} {rx['MusteriAdiSoyadi']:20}"
                    f" → HATA: {e}")
                sayac["X_DIGER"] += 1
                break

            kategori, ke_atomlar, yok_atomlar = _atom_kategori(rapor)
            sayac[kategori] = sayac.get(kategori, 0) + 1

            ke_str = "; ".join(ke_atomlar) if ke_atomlar else "-"
            yok_str = "; ".join(yok_atomlar) if yok_atomlar else "-"

            sonuc_satirlari.append(
                f"[{i:>3}] TC={tc} Rx={recete_no} "
                f"{(rx['MusteriAdiSoyadi'] or '')[:22]:22} "
                f"İlaç={ilac_sonuc['ilac_adi'][:20]:20} "
                f"Yaş={ilac_sonuc['hasta_yasi']} "
                f"Verdict={rapor.sonuc.value.upper()} "
                f"KATEGORİ={kategori}\n"
                f"        Branş={ilac_sonuc['doktor_uzmanligi'][:30]} "
                f"RaporKod={ilac_sonuc['rapor_kodu']}\n"
                f"        KE: {ke_str[:200]}\n"
                f"        YOK: {yok_str[:200]}")
            break  # sadece ilk statin için kontrol

    # Çıktı
    print("\n" + "=" * 70)
    print("STATIN ŞÜPHELİ vs ŞARTLI_UYGUN ANALİZİ")
    print("=" * 70)
    toplam = len(RECETELER)
    for k, v in sayac.items():
        pct = (100.0 * v / toplam) if toplam else 0
        print(f"  {k:25s} : {v:3d} (%{pct:.1f})")
    print(f"  {'TOPLAM':25s} : {toplam:3d}")
    print()
    print("Kategoriler:")
    print("  A_SADECE_6AY_KE     → mantıkça SARTLI_UYGUN olmalı "
          "(sadece 6 ay atomu KE)")
    print("  B_6AY_VE_BASKA_KE   → 6 ay + başka KE → ŞÜPHELİ doğru")
    print("  C_BASKA_KE_6AY_VAR  → 6 ay VAR ama başka KE → ŞÜPHELİ doğru")
    print("  D_UYGUN             → tüm atomlar VAR (listede olmamalı)")
    print("  E_UYGUN_DEGIL       → YOK var → UYGUN_DEGIL")
    print("  X_DIGER             → boş/hata")
    print()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("STATIN ŞÜPHELİ vs ŞARTLI_UYGUN — ATOM-BAZLI DETAY\n")
        f.write("=" * 70 + "\n\n")
        for satir in sonuc_satirlari:
            f.write(satir + "\n\n")
        f.write("\n" + "=" * 70 + "\n")
        f.write("ÖZET\n")
        f.write("=" * 70 + "\n")
        for k, v in sayac.items():
            pct = (100.0 * v / toplam) if toplam else 0
            f.write(f"  {k:25s} : {v:3d} (%{pct:.1f})\n")
        f.write(f"  {'TOPLAM':25s} : {toplam:3d}\n")

    print(f"Detay dosyası: {out_path}")
    if hasattr(db, 'kapat'):
        db.kapat()


if __name__ == "__main__":
    _calistir()
