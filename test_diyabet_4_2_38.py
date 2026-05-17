# -*- coding: utf-8 -*-
"""Akıl testi — SUT 4.2.38 9 yolaklı kontrol motoru.

Şu an Y1, Y2, Y3, Y6, Y9_KAPSAM_DISI, Y4 (kısmî) implemente edildi.
Y3b, Y5, Y7, Y8 için TODO döner — bu testte de KONTROL_EDILEMEDI beklenir.

Çalıştırma: python test_diyabet_4_2_38.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol.diyabet_4_2_38 import (
    diyabet_kontrol_4_2_38, yolak_belirle,
)
from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu


def t(ad: str, ilac_sonuc: dict, beklenen_yolak: str,
       beklenen_sonuc: KontrolSonucu) -> bool:
    """Tek senaryoyu çalıştırıp doğrula."""
    yolak = yolak_belirle(ilac_sonuc)
    rapor = diyabet_kontrol_4_2_38(ilac_sonuc)
    yolak_ok = (yolak == beklenen_yolak)
    sonuc_ok = (rapor.sonuc == beklenen_sonuc)
    durum = "OK" if (yolak_ok and sonuc_ok) else "FAIL"
    print(f"[{durum}] {ad}")
    print(f"     yolak: {yolak} (beklenen: {beklenen_yolak})")
    print(f"     sonuc: {rapor.sonuc.value} (beklenen: {beklenen_sonuc.value})")
    print(f"     mesaj: {rapor.mesaj}")
    if not (yolak_ok and sonuc_ok):
        print(f"     sartlar:")
        for s in rapor.sartlar:
            print(f"       - [{s.durum.value}] {s.ad}: {s.neden}")
    print()
    return yolak_ok and sonuc_ok


def main() -> None:
    sonuclar = []

    # T1: Y1 — Metformin tek başına, herhangi bir hekim
    sonuclar.append(t(
        "T1 Metformin (Y1) — herhangi hekim → UYGUN",
        {
            'ilac_adi': 'GLUKOFEN 850MG',
            'etkin_madde': 'METFORMIN',
            'doktor_uzmanligi': 'Pratisyen',
        },
        beklenen_yolak='Y1',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    # T2: Y1 — İnsan insülin (Humulin), aile hekimi
    sonuclar.append(t(
        "T2 Humulin (Y1) — aile hekimi → UYGUN",
        {
            'ilac_adi': 'HUMULIN M',
            'etkin_madde': 'INSULIN HUMAN',
            'doktor_uzmanligi': 'Aile Hekimliği',
        },
        beklenen_yolak='Y1',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    # T3: Y6 — Dapagliflozin, endokrinoloji uzmanı, rapor "max doz yetersiz"
    sonuclar.append(t(
        "T3 Dapagliflozin (Y6) — endo + rapor lafzı tam → UYGUN",
        {
            'ilac_adi': 'FORZIGA 10MG',
            'etkin_madde': 'DAPAGLIFLOZIN PROPANDIOL',
            'doktor_uzmanligi': 'Endokrinoloji ve Metabolizma Hastalıkları',
            'rapor_metni': ('Tip 2 diyabet. Metformin maksimum tolere edilebilir '
                            'dozda kullanılmasına rağmen yeterli glisemik kontrol '
                            'sağlanamamıştır.'),
        },
        beklenen_yolak='Y6',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    # T4: Y6 — Empagliflozin, pratisyen hekim, rapor lafzı yok → ŞÜPHELİ/UYGUN_DEGIL
    sonuclar.append(t(
        "T4 Empagliflozin (Y6) — pratisyen, raporsuz → UYGUN_DEĞİL",
        {
            'ilac_adi': 'JARDIANCE 25MG',
            'etkin_madde': 'EMPAGLIFLOZIN',
            'doktor_uzmanligi': 'Pratisyen Hekim',
            'rapor_metni': '',
        },
        beklenen_yolak='Y6',
        beklenen_sonuc=KontrolSonucu.UYGUN_DEGIL,
    ))

    # T5: Y4 — Sitagliptin, iç hastalıkları uzmanı + rapor lafzı
    sonuclar.append(t(
        "T5 Sitagliptin (Y4) — IH uzmanı + rapor tam → UYGUN",
        {
            'ilac_adi': 'JANUVIA 100MG',
            'etkin_madde': 'SITAGLIPTIN FOSFAT',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_metni': ('Tip 2 DM. Metformin ve sülfonilürelerin maksimum tolere '
                            'doz kullanılmasına rağmen yeterli glisemik kontrol '
                            'sağlanamadı.'),
        },
        beklenen_yolak='Y4',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    # T6: Y4 + DPP-4 + GLP-1 kombi yasağı — DPP-4 reçetede + diğer kalemde liraglutid
    sonuclar.append(t(
        "T6 Sitagliptin + Liraglutid (Y4 + KY4.1) → UYGUN_DEĞİL (kombi yasağı)",
        {
            'ilac_adi': 'JANUVIA 100MG',
            'etkin_madde': 'SITAGLIPTIN FOSFAT',
            'doktor_uzmanligi': 'Endokrinoloji',
            'rapor_metni': ('Tip 2 DM. Metformin maksimum tolere doz, yetersiz '
                            'glisemik kontrol.'),
            'recete_ilaclari': [
                {'ad': 'VICTOZA', 'etkin_madde': 'LIRAGLUTID'},
            ],
        },
        beklenen_yolak='Y4',
        beklenen_sonuc=KontrolSonucu.UYGUN_DEGIL,
    ))

    # T7: Y9 — Liraglutid (kapsam dışı) → UYGUN_DEĞİL
    sonuclar.append(t(
        "T7 Liraglutid (Y9_KAPSAM_DISI) → UYGUN_DEĞİL",
        {
            'ilac_adi': 'VICTOZA',
            'etkin_madde': 'LIRAGLUTID',
            'doktor_uzmanligi': 'Endokrinoloji',
        },
        beklenen_yolak='Y9_KAPSAM_DISI',
        beklenen_sonuc=KontrolSonucu.UYGUN_DEGIL,
    ))

    # T8: Y2 — Repaglinid, aile hekimi (Y2'de aile hekimi izinli)
    sonuclar.append(t(
        "T8 Repaglinid (Y2) — aile hekimi → UYGUN",
        {
            'ilac_adi': 'NOVONORM 1MG',
            'etkin_madde': 'REPAGLINID',
            'doktor_uzmanligi': 'Aile Hekimliği',
        },
        beklenen_yolak='Y2',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    # T9: Y3 — Pioglitazon, aile hekimi (Y3'te aile hekimi YOK)
    sonuclar.append(t(
        "T9 Pioglitazon (Y3) — aile hekimi → UYGUN_DEĞİL (Y3'te aile hek yok)",
        {
            'ilac_adi': 'ACTOS 30MG',
            'etkin_madde': 'PIOGLITAZON HCL',
            'doktor_uzmanligi': 'Aile Hekimliği',
        },
        beklenen_yolak='Y3',
        beklenen_sonuc=KontrolSonucu.UYGUN_DEGIL,
    ))

    # T10: Y3 — Analog insülin, endokrinoloji
    sonuclar.append(t(
        "T10 Lantus (Y3) — endokrinoloji → UYGUN",
        {
            'ilac_adi': 'LANTUS SOLOSTAR',
            'etkin_madde': 'INSULIN GLARJIN',
            'doktor_uzmanligi': 'Endokrinoloji',
        },
        beklenen_yolak='Y3',
        beklenen_sonuc=KontrolSonucu.UYGUN,
    ))

    print("=" * 70)
    basari = sum(1 for ok in sonuclar if ok)
    toplam = len(sonuclar)
    print(f"SONUÇ: {basari}/{toplam} test geçti.")
    if basari < toplam:
        sys.exit(1)


if __name__ == '__main__':
    main()
