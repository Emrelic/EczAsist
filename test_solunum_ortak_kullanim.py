# -*- coding: utf-8 -*-
"""SUT 4.2.24.B — LABA/LAMA/ICS reçeteler-arası (son 3 ay) ortak kullanım
tespiti akıl testleri.

Geçmiş, `hasta_ilac_gecmisi` pipeline alanıyla enjekte edilir (EOS'a
gidilmez; TC verilmez → EOS yolu kapalı). Senaryolar:
  1. Aynı reçetede SYMBICORT + SPIRIVA → üçlü (mevcut davranış korunur)
  2. SPIRIVA tek + geçmişte SYMBICORT + raporda 4.2.24.B şartları → UYGUN
  3. SPIRIVA tek + geçmişte SYMBICORT + şartlar/rapor kodu yok → KE (ŞÜPHELİ)
  4. SPIRIVA tek + geçmiş boş → LAMA tek yolu (üçlü tetiklenmez)
  5. SYMBICORT (LABA+ICS) + geçmişte SPIRIVA → üçlü
  6. VENTOLIN (SABA) + geçmişte üçlü → SABA yolu (bileşen yok, yükseltme yok)
  7. Geçmişteki satış 3 aydan eski → üçlü tetiklenmez
  8. TRELEGY tek başına → üçlü (mevcut davranış korunur)

Çalıştırma: python test_solunum_ortak_kullanim.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from recete_kontrol.sut_kontrolleri import kontrol_solunum
from recete_kontrol.base_kontrol import KontrolSonucu

BASARILI = 0
BASARISIZ = 0


def kontrol_et(ad, ilac_sonuc, beklenen_sonuc, beklenen_alt_grup=None):
    global BASARILI, BASARISIZ
    rapor = kontrol_solunum(ilac_sonuc)
    hatalar = []
    if rapor.sonuc != beklenen_sonuc:
        hatalar.append(f'sonuç {rapor.sonuc} != beklenen {beklenen_sonuc}')
    if beklenen_alt_grup is not None:
        alt = (rapor.detaylar or {}).get('alt_grup', '')
        if alt != beklenen_alt_grup:
            hatalar.append(f'alt_grup {alt!r} != beklenen {beklenen_alt_grup!r}')
    if hatalar:
        BASARISIZ += 1
        print(f'✗ {ad}: {"; ".join(hatalar)}')
        print(f'    mesaj: {rapor.mesaj}')
    else:
        BASARILI += 1
        print(f'✓ {ad}')
    return rapor


RAPOR_424B_TAM = (
    'KOAH tanısı ile takipli. En az 3 ay ICS+LABA tedavisine rağmen '
    'yetersiz yanıt. Yılda 2 orta/ağır alevlenme (atak). mMRC: 3, CAT skor: 18. '
    'Göğüs hastalıkları uzmanı raporu.')


# ── 1. Aynı reçetede SYMBICORT + SPIRIVA → üçlü + şartlar VAR → UYGUN ──
kontrol_et(
    '1. Aynı reçete SYMBICORT+SPIRIVA, 4.2.24.B şartları raporda → UYGUN',
    {
        'ilac_adi': 'SPIRIVA 18 MCG KAPSUL',
        'etkin_madde': 'TIOTROPIUM BROMUR',
        'rapor_kodu': '',
        'rapor_aciklamalari': [RAPOR_424B_TAM],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [{'ad': 'SYMBICORT TURBUHALER 160/4.5'}],
    },
    KontrolSonucu.UYGUN, 'LABA+ICS+LAMA (üçlü)')

# ── 2. SPIRIVA tek + geçmişte SYMBICORT + şartlar raporda → UYGUN ──
r2 = kontrol_et(
    '2. SPIRIVA + geçmiş(3 ay) SYMBICORT, şartlar raporda → UYGUN üçlü',
    {
        'ilac_adi': 'SPIRIVA 18 MCG KAPSUL',
        'etkin_madde': 'TIOTROPIUM BROMUR',
        'rapor_kodu': '',
        'rapor_aciklamalari': [RAPOR_424B_TAM],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        'hasta_ilac_gecmisi': [
            {'ad': 'SYMBICORT TURBUHALER 160/4.5', 'tarih': '2026-05-10'},
        ],
    },
    KontrolSonucu.UYGUN, 'LABA+ICS+LAMA (üçlü)')
assert (r2.detaylar or {}).get('gecmis_uclu_kullanim') is True, \
    'senaryo 2: gecmis_uclu_kullanim True olmalı'
assert 'son 3 ay satışıyla tamamlandı' in (r2.mesaj or ''), \
    'senaryo 2: mesajda geçmiş kaynak notu olmalı'

# ── 3. SPIRIVA tek + geçmişte SYMBICORT + şart/rapor kodu yok → KE ──
kontrol_et(
    '3. SPIRIVA + geçmiş SYMBICORT, şartlar yok → KONTROL_EDILEMEDI',
    {
        'ilac_adi': 'SPIRIVA 18 MCG KAPSUL',
        'etkin_madde': 'TIOTROPIUM BROMUR',
        'rapor_kodu': '',
        'rapor_aciklamalari': ['KOAH tanısı ile takipli hasta.'],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        'hasta_ilac_gecmisi': [
            {'ad': 'SYMBICORT TURBUHALER 160/4.5', 'tarih': '2026-05-10'},
        ],
    },
    KontrolSonucu.KONTROL_EDILEMEDI, 'LABA+ICS+LAMA (üçlü)')

# ── 4. SPIRIVA tek + geçmiş boş → LAMA tek yolu (KOAH var → UYGUN) ──
r4 = kontrol_et(
    '4. SPIRIVA + geçmiş boş → LAMA tek yolu (üçlü değil)',
    {
        'ilac_adi': 'SPIRIVA 18 MCG KAPSUL',
        'etkin_madde': 'TIOTROPIUM BROMUR',
        'rapor_kodu': '',
        'rapor_aciklamalari': ['KOAH tanısı. Göğüs hastalıkları uzmanı.'],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        # hasta_ilac_gecmisi yok + TC yok → geçmiş taranamaz → yükseltme yok
    },
    KontrolSonucu.UYGUN, 'LAMA')
assert (r4.detaylar or {}).get('gecmis_uclu_kullanim') is False, \
    'senaryo 4: gecmis_uclu_kullanim False olmalı'

# ── 5. SYMBICORT (LABA+ICS) + geçmişte SPIRIVA → üçlü ──
kontrol_et(
    '5. SYMBICORT + geçmiş SPIRIVA, şartlar raporda → UYGUN üçlü',
    {
        'ilac_adi': 'SYMBICORT TURBUHALER 160/4.5',
        'etkin_madde': 'FORMOTEROL FUMARAT+BUDEZONID',
        'rapor_kodu': '',
        'rapor_aciklamalari': [RAPOR_424B_TAM],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        'hasta_ilac_gecmisi': [
            {'ad': 'SPIRIVA 18 MCG KAPSUL', 'tarih': '2026-04-20'},
        ],
    },
    KontrolSonucu.UYGUN, 'LABA+ICS+LAMA (üçlü)')

# ── 6. VENTOLIN (SABA) + geçmişte üçlü satış → SABA yolu değişmez ──
r6 = kontrol_et(
    '6. VENTOLIN + geçmişte üçlü satış → SABA yolu (yükseltme yok)',
    {
        'ilac_adi': 'VENTOLIN INHALER',
        'etkin_madde': 'SALBUTAMOL SULFAT',
        'rapor_kodu': '',
        'rapor_aciklamalari': [],
        'recete_teshisleri': ['J45 ASTIM'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        'hasta_ilac_gecmisi': [
            {'ad': 'TRELEGY ELLIPTA', 'tarih': '2026-05-10'},
        ],
    },
    KontrolSonucu.UYGUN, 'SABA')
assert (r6.detaylar or {}).get('gecmis_uclu_kullanim') is False, \
    'senaryo 6: SABA bileşen katmaz → yükseltme olmamalı'

# ── 7. Geçmiş satış 3 aydan eski → üçlü tetiklenmez ──
r7 = kontrol_et(
    '7. SPIRIVA + SYMBICORT satışı 5 ay önce → LAMA tek yolu',
    {
        'ilac_adi': 'SPIRIVA 18 MCG KAPSUL',
        'etkin_madde': 'TIOTROPIUM BROMUR',
        'rapor_kodu': '',
        'rapor_aciklamalari': ['KOAH tanısı. Göğüs hastalıkları uzmanı.'],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
        'recete_tarihi': '15.06.2026',
        'hasta_ilac_gecmisi': [
            {'ad': 'SYMBICORT TURBUHALER 160/4.5', 'tarih': '2026-01-10'},
        ],
    },
    KontrolSonucu.UYGUN, 'LAMA')
assert (r7.detaylar or {}).get('gecmis_uclu_kullanim') is False, \
    'senaryo 7: pencere dışı satış üçlü tetiklememeli'

# ── 8. TRELEGY tek başına → üçlü (mevcut davranış) ──
kontrol_et(
    '8. TRELEGY + şartlar raporda → UYGUN üçlü',
    {
        'ilac_adi': 'TRELEGY ELLIPTA 92/55/22',
        'etkin_madde': '',
        'rapor_kodu': '',
        'rapor_aciklamalari': [RAPOR_424B_TAM],
        'recete_teshisleri': ['J44 KOAH'],
        'recete_ilaclari': [],
    },
    KontrolSonucu.UYGUN, 'LABA+ICS+LAMA (üçlü)')

print()
print(f'SONUÇ: {BASARILI} başarılı / {BASARISIZ} başarısız '
      f'(toplam {BASARILI + BASARISIZ})')
sys.exit(1 if BASARISIZ else 0)
