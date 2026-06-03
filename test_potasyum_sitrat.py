# -*- coding: utf-8 -*-
"""SUT EK-4/F — Potasyum Sitrat (UROCIT-K, ATC A12BA02) kontrol testleri.

Kural (kontrol_potasyum_sitrat docstring):
  - Üroloji/Nefroloji UZMANI raporsuz reçeteleyebilir → UYGUN
  - Diğer hekimler için 6 ay süreli uzman raporu gerekir → raporsuzsa ŞÜPHELİ
  - Raporlu: N25.8/9 (RTA) VEYA N20.0/1 (böbrek taşı + girişimsel + pH<6.5)

Pilot: UROCIT-K, 27y N20.0 üroloji uzmanı raporsuz — eskiden yanlış ŞÜPHELİ,
artık UYGUN (2026-06-03).
"""
import importlib

sk = importlib.import_module("recete_kontrol.sut_kontrolleri")
KS = sk.KontrolSonucu


def _calistir(brans, rapor_kodu="", tesh="N20.0 BOBREK TASI", rap_ack=""):
    return sk.kontrol_potasyum_sitrat({
        "ilac_adi": "UROCIT-K 10 MEQ 100 KONTROLLU SALIM TABLET",
        "etkin_madde": "POTASYUM SITRAT",
        "atc_kodu": "A12BA02",
        "rapor_kodu": rapor_kodu,
        "recete_teshisleri": [tesh],
        "rapor_aciklamalari": [rap_ack] if rap_ack else [],
        "doktor_uzmanligi": brans,
    })


SENARYOLAR = [
    # (ad, brans, rapor_kodu, tesh, rap_ack, beklenen)
    ("Üroloji uzmanı + raporsuz → UYGUN",
     "Üroloji (Ana Branş)", "", "N20.0 BOBREK TASI", "", KS.UYGUN),
    ("Nefroloji + raporsuz → UYGUN",
     "Nefroloji", "", "N20.0", "", KS.UYGUN),
    ("Aile Hekimliği + raporsuz → ŞÜPHELİ (6 ay rapor gerekli)",
     "Aile Hekimliği", "", "N20.0", "", KS.KONTROL_EDILEMEDI),
    ("Branş boş + raporsuz → ŞÜPHELİ",
     "", "", "N20.0", "", KS.KONTROL_EDILEMEDI),
    ("Pratisyen + raporsuz → ŞÜPHELİ",
     "Pratisyen Hekim", "", "N20.0", "", KS.KONTROL_EDILEMEDI),
    ("Raporlu + RTA (N25.8) → UYGUN",
     "Üroloji", "03.00", "N25.8", "renal tübüler asidoz", KS.UYGUN),
    ("Raporlu + N20 + girişim + pH<6.5 → UYGUN",
     "Aile Hek", "03.00", "N20.0",
     "böbrek taşı ESWL yapıldı idrar pH 6.0", KS.UYGUN),
    ("Raporlu + N20 ama girişim yok → ŞÜPHELİ",
     "Aile Hek", "03.00", "N20.0", "böbrek taşı mevcut", KS.KONTROL_EDILEMEDI),
]


def main():
    gecti = 0
    for ad, brans, rk, tesh, ack, beklenen in SENARYOLAR:
        r = _calistir(brans, rk, tesh, ack)
        ok = r.sonuc == beklenen
        gecti += ok
        isaret = "[OK ]" if ok else "[FAIL]"
        print(f"{isaret} {ad}: beklenen={beklenen.name} gercek={r.sonuc.name}")
        if not ok:
            print(f"       mesaj: {r.mesaj}")
    print(f"\nSONUC: {gecti}/{len(SENARYOLAR)} senaryo basarili")
    return gecti == len(SENARYOLAR)


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
