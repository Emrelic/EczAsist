# -*- coding: utf-8 -*-
"""Tab C üst-OR fix + Tab B NOT-gate fix akıl testi.

Tab C (SUT Madde Akışı) fix:
  - D-1 madde (2): E_YOL ∨ F_YOL üst-OR (önceden AND idi → BUG)
  - D-2 madde (3): E2_YOL ∨ F2_YOL üst-OR
  - Madde-arası ok: D-1(1)(a)↔(1)(b) OR; D-2(1)(b)↔(2) OR; diğerleri AND

Tab B (FTA Ağacı) fix:
  - _fta_atom_negatif_mi: kontrendikasyon/kombi yasağı atomları NOT işaretli
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

# Tkinter import GUI sınıfı için gerekir; ama Canvas çizmiyoruz, sadece
# static/regular method'ları çağırıyoruz — testler headless.
from aylik_recete_sorgu_gui import AylikReceteSorguGUI as G

basarisiz = []


def assert_eq(ad, beklenen, gercek):
    durum = '✓' if beklenen == gercek else '✗'
    print(f'{durum} {ad}: beklenen={beklenen!r}, gerçek={gercek!r}')
    if beklenen != gercek:
        basarisiz.append(ad)


# ══════════════════════════════════════════════════════════════
# Test 1: _madde_ici_ustor — D-1(2), D-2(3) üst-OR
# ══════════════════════════════════════════════════════════════
print('\n── _madde_ici_ustor (madde-içi E∨F) ──')
assert_eq('T01 D-1(2) → True', True, G._madde_ici_ustor('4.2.15.D-1', '(2)'))
assert_eq('T02 D-2(3) → True', True, G._madde_ici_ustor('4.2.15.D-2', '(3)'))
assert_eq('T03 D-1(1) → False', False, G._madde_ici_ustor('4.2.15.D-1', '(1)'))
assert_eq('T04 D-1(4) → False', False, G._madde_ici_ustor('4.2.15.D-1', '(4)'))
assert_eq('T05 D-2(2) → False', False, G._madde_ici_ustor('4.2.15.D-2', '(2)'))
assert_eq('T06 D-2(1)(b) → False', False, G._madde_ici_ustor('4.2.15.D-2', '(1)(b)'))
assert_eq('T07 EK-4/F → False', False, G._madde_ici_ustor('EK-4/F (M.53–54)', 'EK-4/F'))

# ══════════════════════════════════════════════════════════════
# Test 2: _madde_arasi_baglac — varfarin (a)∨(b), varfarin∨istisna
# ══════════════════════════════════════════════════════════════
print('\n── _madde_arasi_baglac (madde-arası AND/OR) ──')
assert_eq('T10 D-1 (1)→(1)(a)', 'AND',
          G._madde_arasi_baglac('4.2.15.D-1', '(1)', '(1)(a)'))
assert_eq('T11 D-1 (1)(a)→(1)(b) [OR]', 'OR',
          G._madde_arasi_baglac('4.2.15.D-1', '(1)(a)', '(1)(b)'))
assert_eq('T12 D-1 (1)(b)→(2)', 'AND',
          G._madde_arasi_baglac('4.2.15.D-1', '(1)(b)', '(2)'))
assert_eq('T13 D-1 (2)→(4)', 'AND',
          G._madde_arasi_baglac('4.2.15.D-1', '(2)', '(4)'))
assert_eq('T14 D-2 (1)(a)→(1)(b)', 'AND',
          G._madde_arasi_baglac('4.2.15.D-2', '(1)(a)', '(1)(b)'))
assert_eq('T15 D-2 (1)(b)→(2) [OR]', 'OR',
          G._madde_arasi_baglac('4.2.15.D-2', '(1)(b)', '(2)'))
assert_eq('T16 D-2 (2)→(3)', 'AND',
          G._madde_arasi_baglac('4.2.15.D-2', '(2)', '(3)'))
assert_eq('T17 EK-4/F → AND',  'AND',
          G._madde_arasi_baglac('EK-4/F', 'EK-4/F', 'EK-4/F'))

# ══════════════════════════════════════════════════════════════
# Test 3: _fta_atom_negatif_mi — NOT atomları
# ══════════════════════════════════════════════════════════════
print('\n── _fta_atom_negatif_mi (NOT atom tespit) ──')
assert_eq('T20 "Orta-ciddi mitral darlık YOK"', True,
          G._fta_atom_negatif_mi('Orta-ciddi mitral darlık YOK'))
assert_eq('T21 "Mekanik protez kapak YOK"', True,
          G._fta_atom_negatif_mi('Mekanik protez kapak YOK'))
assert_eq('T22 "Aynı reçetede 2. YOAK YOK"', True,
          G._fta_atom_negatif_mi('Aynı reçetede 2. YOAK YOK'))
assert_eq('T23 "Apiksaban/Edoksaban kapsam dışı (NOT)"', True,
          G._fta_atom_negatif_mi('Apiksaban/Edoksaban kapsam dışı (NOT)'))
assert_eq('T24 "İnme öyküsü"', False,
          G._fta_atom_negatif_mi('İnme öyküsü'))
assert_eq('T25 "≥75 yaş"', False,
          G._fta_atom_negatif_mi('≥75 yaş'))
assert_eq('T26 "Non-valvüler atriyal fibrilasyon"', False,
          G._fta_atom_negatif_mi('Non-valvüler atriyal fibrilasyon'))
assert_eq('T27 "" (boş)', False, G._fta_atom_negatif_mi(''))

# ══════════════════════════════════════════════════════════════
# Test 4: _sut_madde_grupla — D-1(2) E∨F üst-OR davranışı
# Senaryo: E_YOL grup → YOK, F_YOL grup → VAR → madde (2) VAR olmalı
# (Önceden AND olduğu için YOK çıkıyordu — BUG)
# ══════════════════════════════════════════════════════════════
print('\n── _sut_madde_grupla D-1(2) E∨F senaryosu ──')


class _DummyGUI:
    """Mock — sadece grupla için gerekli helpers.

    Not: G.__dict__ üzerinden alarak staticmethod descriptor korunur
    (G._madde_ici_ustor sınıf erişimi descriptor'ı unwrap eder).
    """
    _SUT_MADDE_BASLIK = G._SUT_MADDE_BASLIK
    _sut_madde_extract = G.__dict__['_sut_madde_extract']
    _sut_madde_sort_key = G.__dict__['_sut_madde_sort_key']
    _sut_madde_grupla = G.__dict__['_sut_madde_grupla']
    _madde_ici_ustor = G.__dict__['_madde_ici_ustor']
    _fta_durum_normalize = G.__dict__['_fta_durum_normalize']
    _fta_grup_durum_hesapla = G.__dict__['_fta_grup_durum_hesapla']


dgui = _DummyGUI()

# D-1(2) E_YOL = 3 atom hep YOK (eski yıl 24 ay tamamlanmamış sayım)
# D-1(2) F_YOL = 3 atom hep VAR (24 ay sonrası geçerli)
sartlar = [
    # E_YOL — YOK (atomlar)
    {'ad': 'SK ibaresi', 'durum': 'yok', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(2)]', 'veya_grubu': False},
    {'ad': 'Kard/nöro zorunlu', 'durum': 'yok', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(2)]', 'veya_grubu': False},
    {'ad': '5 daldan ≥3', 'durum': 'yok', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(2)]', 'veya_grubu': False},
    # F_YOL — VAR (atomlar)
    {'ad': 'Uzman raporu', 'durum': 'var', 'neden': '',
     'grup': '24 ay sonrası alt yol [(2)]', 'veya_grubu': False},
    {'ad': 'Aile hekimi/uzman reçete', 'durum': 'var', 'neden': '',
     'grup': '24 ay sonrası alt yol [(2)]', 'veya_grubu': False},
]
sonuc = dgui._sut_madde_grupla(sartlar, alt_dal='4.2.15.D-1')
m2 = sonuc.get('(2)')
assert m2 is not None, 'D-1(2) madde bulunamadı'
assert_eq('T30 D-1(2) status (E=YOK, F=VAR, üst-OR)', 'var', m2['status'])
assert_eq('T31 D-1(2) grup sayısı', 2, len(m2['gruplar']))

# Tersi: E_YOL = VAR, F_YOL = YOK → madde (2) hala VAR (üst-OR)
sartlar2 = [
    {'ad': 'SK ibaresi', 'durum': 'var', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(2)]', 'veya_grubu': False},
    {'ad': 'Uzman raporu', 'durum': 'yok', 'neden': '',
     'grup': '24 ay sonrası alt yol [(2)]', 'veya_grubu': False},
]
sonuc2 = dgui._sut_madde_grupla(sartlar2, alt_dal='4.2.15.D-1')
m2b = sonuc2.get('(2)')
assert_eq('T32 D-1(2) (E=VAR, F=YOK) üst-OR', 'var', m2b['status'])

# Her ikisi YOK → madde YOK
sartlar3 = [
    {'ad': 'SK ibaresi', 'durum': 'yok', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(2)]', 'veya_grubu': False},
    {'ad': 'Uzman raporu', 'durum': 'yok', 'neden': '',
     'grup': '24 ay sonrası alt yol [(2)]', 'veya_grubu': False},
]
sonuc3 = dgui._sut_madde_grupla(sartlar3, alt_dal='4.2.15.D-1')
m2c = sonuc3.get('(2)')
assert_eq('T33 D-1(2) (E=YOK, F=YOK) üst-OR → YOK', 'yok', m2c['status'])

# D-2(3) için aynı üst-OR
sartlar4 = [
    {'ad': 'E2 SK ibaresi', 'durum': 'yok', 'neden': '',
     'grup': 'SK raporu — ilk 24 ay [(3)]', 'veya_grubu': False},
    {'ad': 'F2 Uzman raporu', 'durum': 'var', 'neden': '',
     'grup': '24 ay sonrası alt yol [(3)]', 'veya_grubu': False},
]
sonuc4 = dgui._sut_madde_grupla(sartlar4, alt_dal='4.2.15.D-2')
m3 = sonuc4.get('(3)')
assert_eq('T34 D-2(3) (E2=YOK, F2=VAR) üst-OR', 'var', m3['status'])

# alt_dal boşsa eski davranış: AND (regresyon olmasın)
sonuc5 = dgui._sut_madde_grupla(sartlar, alt_dal='')
m2_no_dal = sonuc5.get('(2)')
assert_eq('T35 alt_dal boş → AND (regresyon)', 'yok', m2_no_dal['status'])


# ══════════════════════════════════════════════════════════════
# Özet
# ══════════════════════════════════════════════════════════════
print('\n' + '═' * 60)
if not basarisiz:
    print(f'✓ TÜM TESTLER GEÇTİ (17/17)')
else:
    print(f'✗ {len(basarisiz)} test başarısız: {basarisiz}')
    sys.exit(1)
