# -*- coding: utf-8 -*-
"""SUT 4.2.28.B Fibrat — atomik kontrol akıl testi.

Senaryolar mevzuat lafzından türetildi (docs/sut/SUT_tam_metin.txt:7793-7800):
- Yol-a: TG>500 tek başına
- Yol-b: TG>200 + (DM ∨ AKS ∨ Mİ ∨ inme ∨ KAH ∨ PAH ∨ AAA ∨ karotid)
- D1: 5 uzman branş (Kardiyo/KVC/Endokrin/İç/Nöro) — Geriatri YOK
- Kati sınırlar: > 500 ve > 200 (= değil)

Beklenen sonuç tipleri:
  sartli_uygun  → tüm hesaplanabilir şartlar VAR, sadece T1 (6 ay ara) KE
                  — eczacı manuel doğrulayınca kesin UYGUN olur
                  (2026-05-16: T1 atomu eklendi, SARTLI_UYGUN dönüş yolu)
  uygun_degil   → ≥1 zorunlu grup YOK
  kontrol_edilemedi → ≥1 hesaplanabilir grup KE (manuel doğrulama)
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from recete_kontrol import sut_kontrolleri as sk


SENARYOLAR = [
    # ── Yol-a (TG > 500) ─────────────────────────────────────────
    {
        'ad': 'Yol-a UYGUN — TG=620 + Kardiyo',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },
    {
        'ad': 'Yol-a UYGUN — Trigliserit 510 + Nöroloji',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LOPID 600 MG',
            'rapor_kodu': '',
            'doktor_uzmanligi': 'NOROLOJI',
            'rapor_aciklamalari': ['Trigliserit: 510 mg/dL'],
        },
    },
    {
        'ad': 'Yol-a SINIR — TG=500 tam (kati > 500) → UYGUN_DEGIL',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 500 mg/dL'],
        },
    },

    # ── Yol-b (TG > 200 + KV hastalık ≥1) ────────────────────────
    {
        'ad': 'Yol-b UYGUN — TG=350 + DM + İç hast.',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'IC HASTALIKLARI',
            'rapor_aciklamalari': ['TG: 350 mg/dL, DM mevcut'],
            'recete_teshisleri': ['E11'],
        },
    },
    {
        'ad': 'Yol-b UYGUN — TG=260 + AKS (yeni atom) + KVC',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LOPID 600 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KVC',
            'rapor_aciklamalari': ['TG: 260 mg/dL, akut koroner sendrom'],
        },
    },
    {
        'ad': 'Yol-b UYGUN — TG=380 + AAA (yeni atom) + Endokrin',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'ENDOKRINOLOJI',
            'rapor_aciklamalari': ['TG: 380 mg/dL, abdominal aort anevrizması'],
        },
    },
    {
        'ad': 'Yol-b UYGUN — TG=240 + Karotid (yeni atom) + Nöro',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'NOROLOJI',
            'rapor_aciklamalari': ['TG: 240 mg/dL, karotid arter hastalığı'],
        },
    },
    {
        'ad': 'Yol-b SINIR — TG=200 tam (kati > 200) → UYGUN_DEGIL',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 200 mg/dL, DM'],
            'recete_teshisleri': ['E11'],
        },
    },
    {
        'ad': 'Yol-b YETERSİZ — TG=250 + risk YOK → UYGUN_DEGIL',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 250 mg/dL'],
        },
    },

    # ── D1 Uzman branş kontrolleri ──────────────────────────────
    {
        'ad': 'Branş AİLE HEK → UYGUN_DEGIL (Geriatri/AH yetkisiz)',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'AILE HEKIMI',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },
    {
        'ad': 'Branş GERIATRI → UYGUN_DEGIL (statinden farklı, GERIATRI YOK)',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'GERIATRI',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },
    {
        'ad': 'Branş bilinmiyor + rapor_kodu 04.02 → UYGUN (medula otoritesi)',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.02',
            'doktor_uzmanligi': '',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },

    # ── Endikasyon önkoşul + parse edge ──────────────────────────
    {
        'ad': 'TG ibare var ama sayı yok → ŞÜPHELİ (KE)',
        'beklenen': 'uygun_degil',  # B1=YOK → endikasyon önkoşul YOK
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['Trigliserid yüksek, tedavi gerekli'],
        },
    },
    {
        'ad': 'Raporsuz → UYGUN_DEGIL (rapor zorunlu)',
        'beklenen': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '',
            'doktor_uzmanligi': '',
            'rapor_aciklamalari': [],
        },
    },
    {
        'ad': 'Rapor kodu var ama metin boş → KE',
        'beklenen': 'kontrol_edilemedi',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': [],
        },
    },

    # ── 5 uzman branş ayrı ayrı doğrula ──────────────────────────
    {
        'ad': 'Branş 1/5 KARDIYO',
        'beklenen': 'sartli_uygun',
        'ilac': {'ilac_adi': 'LIPANTHYL 200 MG', 'rapor_kodu': '04.08',
                 'doktor_uzmanligi': 'KARDIYOLOJI',
                 'rapor_aciklamalari': ['TG: 620']},
    },
    {
        'ad': 'Branş 2/5 KVC',
        'beklenen': 'sartli_uygun',
        'ilac': {'ilac_adi': 'LIPANTHYL 200 MG', 'rapor_kodu': '04.08',
                 'doktor_uzmanligi': 'KALP VE DAMAR CERRAHISI',
                 'rapor_aciklamalari': ['TG: 620']},
    },
    {
        'ad': 'Branş 3/5 ENDOKRIN',
        'beklenen': 'sartli_uygun',
        'ilac': {'ilac_adi': 'LIPANTHYL 200 MG', 'rapor_kodu': '04.08',
                 'doktor_uzmanligi': 'ENDOKRINOLOJI',
                 'rapor_aciklamalari': ['TG: 620']},
    },
    {
        'ad': 'Branş 4/5 İÇ HAST.',
        'beklenen': 'sartli_uygun',
        'ilac': {'ilac_adi': 'LIPANTHYL 200 MG', 'rapor_kodu': '04.08',
                 'doktor_uzmanligi': 'IC HASTALIKLARI',
                 'rapor_aciklamalari': ['TG: 620']},
    },
    {
        'ad': 'Branş 5/5 NÖROLOJİ',
        'beklenen': 'sartli_uygun',
        'ilac': {'ilac_adi': 'LIPANTHYL 200 MG', 'rapor_kodu': '04.08',
                 'doktor_uzmanligi': 'NOROLOJI',
                 'rapor_aciklamalari': ['TG: 620']},
    },

    # ── ICD tabanlı KV hastalık ──────────────────────────────────
    {
        'ad': 'ICD I21 (Mİ) + TG=300 → Yol-b UYGUN',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 300 mg/dL'],
            'recete_teshisleri': ['I21'],
        },
    },
    {
        'ad': 'ICD I63 (inme) + TG=210 → Yol-b UYGUN',
        'beklenen': 'sartli_uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'NOROLOJI',
            'rapor_aciklamalari': ['TG: 210 mg/dL'],
            'recete_teshisleri': ['I63'],
        },
    },
]


def _calistir():
    ok = 0
    fail = 0
    for s in SENARYOLAR:
        try:
            r = sk.kontrol_fibrat(s['ilac'])
            actual = r.sonuc.value
            if actual == s['beklenen']:
                print(f"✓ [{s['ad']}] = {actual}")
                ok += 1
            else:
                print(f"✗ [{s['ad']}] beklenen={s['beklenen']} "
                      f"actual={actual}")
                print(f"   mesaj: {r.mesaj[:120]}")
                fail += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"✗ [{s['ad']}] HATA: {e}")
            fail += 1
    print(f"\nSONUÇ: {ok}/{len(SENARYOLAR)} OK, {fail} FAIL")
    return fail == 0


if __name__ == '__main__':
    sys.exit(0 if _calistir() else 1)
