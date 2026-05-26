# -*- coding: utf-8 -*-
"""SUT 4.2.38 (kontrol_diyabet_dpp4_sglt2) — pankreatit/BMI/DPP-4 paralel-VEYA
fix doğrulama testleri (2026-05-17).

Kapsam:
  • Pankreatit 3-yönlü parser (NEG/POS/KE)
  • BMI lafız parser (sayı + operatör >, ≥, üstü)
  • DPP-4 (Y4) paralel-VEYA atomları (yetki: Endo/IH uzmanı VEYA raporu)
  • Glisemik şart ibaresi varyasyonları

Çalıştırma: python test_diyabet_sut_kontrolleri_fix.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol.sut_kontrolleri import (
    kontrol_diyabet_dpp4_sglt2,
    _diy_pankreatit_durumu, _diy_bmi_parse, _diy_bmi_esik_buyuk,
    _diy_glisemik_sart_var,
)
from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu


_BASARI = 0
_TOPLAM = 0


def _ok(ad: str, kosul: bool, detay: str = '') -> None:
    global _BASARI, _TOPLAM
    _TOPLAM += 1
    if kosul:
        _BASARI += 1
        print(f'  [OK] {ad}')
    else:
        print(f'  [FAIL] {ad}  {detay}')


def _sart_bul(rapor, ad_parca: str):
    """Sartlar listesinde adı parçayı içeren ilk sartı dön."""
    for s in (rapor.sartlar or []):
        if ad_parca.lower() in s.ad.lower():
            return s
    return None


# ═══════════════════════════════════════════════════════════════════════
# 1. Helper testleri
# ═══════════════════════════════════════════════════════════════════════

def test_pankreatit_parser() -> None:
    print('\n── Pankreatit 3-yönlü parser ──')
    cases = [
        ('NEG: AKUT PANKREATIT ÖYKÜSÜ YOKTUR', '',
         'AKUT PANKREATİT ÖYKÜSÜ YOKTUR', 'neg'),
        ('NEG: pankreatit geçirmemiş', '',
         'Hasta akut pankreatit geçirmemiş', 'neg'),
        ('NEG: pankreatit geçirilme öyküsü bulunmayan (AYNUR YILMAZ vakası)', '',
         'TEDAVİ ÖNCESİ ANEMNEZDE AKUT PANKREATİT GEÇİRİLME ÖYKÜSÜ BULUNMAYAN', 'neg'),
        ('NEG: pankreatit tespit edilmemiş', '',
         'Pankreatit tespit edilmemiştir', 'neg'),
        ('NEG: pankreatit saptanmadı', '',
         'Pankreatit saptanmamıştır', 'neg'),
        ('NEG: pankreatit mevcut değil', '',
         'Pankreatit mevcut değil', 'neg'),
        ('NEG: pankreatit görülmemiş', '',
         'Hastada pankreatit görülmemiştir', 'neg'),
        ('POS: pankreatit vardır', '',
         'Hastanın akut pankreatit öyküsü vardır', 'pos'),
        ('POS: pankreatit geçirilmiş', '',
         'Hasta geçmişte akut pankreatit geçirmiştir', 'pos'),
        ('POS: ICD K85', 'K85.9 - Akut pankreatit', '', 'pos'),
        ('POS: ICD K86.1', 'K86.1 - Kronik pankreatit', '', 'pos'),
        ('KE: pankreatit lafzı yok', '',
         'Hasta diyabet hastası BMI 35', 'unknown'),
        ('KE: pankreatit sessiz (risk faktörü)', '',
         'Pankreatit risk faktörleri değerlendirilmiştir', 'unknown'),
    ]
    for ad, t, m, beklenen in cases:
        got, _ = _diy_pankreatit_durumu(t, m)
        _ok(f'{ad} → {got}', got == beklenen,
            f'(beklenen: {beklenen})')


def test_bmi_parser() -> None:
    print('\n── BMI lafız parser (sayı + operatör) ──')
    cases = [
        ('BMI: 42', 'BMI: 42', (42.0, None)),
        ('BMI>35', 'BMI>35 Metformin', (35.0, '>')),
        ('BMI ≥ 35', 'BMI ≥ 35', (35.0, '>=')),
        ('BMI 35 üstü', 'BMI 35 üstü', (35.0, '>')),
        ('BMI: 30', 'BMI: 30', (30.0, None)),
        ('VKİ 41', 'VKİ 41', (41.0, None)),
        ('SUT lafzı: vücut kitle indeksi ... 35 kg/m üzerinde olan',
         "VÜCUT KİTLE İNDEKSİ TEDAVİ BAŞLANGICINDA 35 KG/M'NİN ÜZERİNDE OLAN", (35.0, '>')),
        ('SUT lafzı + sonra reçete BMI:29 — SUT lafzı tercih',
         "VÜCUT KİTLE İNDEKSİ TEDAVİ BAŞLANGICINDA 35 KG/M'NİN ÜZERİNDE OLAN. BYETTA İDAME BMI:29",
         (35.0, '>')),
        ('Geçersiz', 'Hasta diyabet hastası', (None, None)),
    ]
    for ad, m, beklenen in cases:
        got = _diy_bmi_parse(m)
        _ok(f'{ad} → {got}', got == beklenen,
            f'(beklenen: {beklenen})')


def test_bmi_esik() -> None:
    print('\n── BMI eşik > 35 değerlendirme ──')
    cases = [
        ('BMI>35 op>', (35.0, '>'), 'var'),
        ('BMI=42', (42.0, None), 'var'),
        ('BMI=35', (35.0, None), 'yok'),
        ('BMI=30', (30.0, None), 'yok'),
        ('BMI>30 op>', (30.0, '>'), 'ke'),
        ('BMI=None', (None, None), 'ke'),
        ('BMI>=35 op>=', (35.0, '>='), 'ke'),
        ('BMI>=40 op>=', (40.0, '>='), 'var'),
    ]
    for ad, (val, op), beklenen in cases:
        got, _ = _diy_bmi_esik_buyuk(val, op, 35.0)
        _ok(f'{ad} → {got}', got == beklenen,
            f'(beklenen: {beklenen})')


def test_glisemik_varyasyon() -> None:
    print('\n── Glisemik şart ibaresi varyasyonları ──')
    cases = [
        ('Klasik lafız',
         'Metformin veya sülfonilürelerin maksimum tolere edilebilir '
         'dozlarında yeterli glisemik kontrol sağlanamamıştır', True),
        ('AMARYL maks doz yetersiz',
         'AMARYL maksimum tolere dozda glisemik kontrol sağlanamamıştır', True),
        ('Glikoz yüksek + HbA1c',
         'Açlık kan şekeri 250, HbA1c 9.5, glisemik kontrol yetersiz', True),
        ('DIAMICRON yanıt vermedi',
         'DIAMICRON tedavisine yanıt vermedi', True),
        ('Hedef değere ulaşılamadı',
         'Metformin tedavisi ile hedef değer ulaşılamadı', True),
        ('Glisemik indeks yüksek',
         'Glisemik indeks yüksek seyretti', True),
        ('GLUKOFEN kullanmasına rağmen',
         'GLUKOFEN kullanmasına rağmen yeterli kontrol yok', True),
        ('Boş rapor', '', False),
        ('Konu dışı', 'Hastanın HT teşhisi vardır', False),
    ]
    for ad, metin, beklenen in cases:
        got, _ = _diy_glisemik_sart_var(metin)
        _ok(f'{ad} → {got}', got == beklenen,
            f'(beklenen: {beklenen})')


# ═══════════════════════════════════════════════════════════════════════
# 2. Eksenatid (Y5) — pankreatit + BMI senaryoları
# ═══════════════════════════════════════════════════════════════════════

_RAPOR_TEMPLATE = (
    'Metformin veya sülfonilürelerin maksimum tolere edilebilir dozlarında '
    'yeterli glisemik kontrol sağlanamamıştır .{pank} . {bmi}'
)


def _eksenatid_ilac(rapor_metni: str, rapor_kodu: str = '1234',
                    teshisler=None) -> dict:
    return {
        'ilac_adi': 'BYETTA 10 MCG',
        'etkin_madde': 'EKSENATID',
        'atc_kodu': 'A10BJ01',
        'doktor_uzmanligi': 'Endokrinoloji ve Metabolizma Hastalıkları',
        'rapor_doktor_uzmanligi': 'Endokrinoloji ve Metabolizma Hastalıkları',
        'recete_teshisleri': teshisler or ['E11 - Tip 2 Diabetes Mellitus'],
        'rapor_aciklamalari': [rapor_metni],
        'rapor_metni': rapor_metni,  # Yeni motor bu alanı okuyor
        'rapor_kodu': rapor_kodu,
        'hasta_yasi': 55,
        'hasta_kilo': 110,
        'hasta_boy': 170,
    }


def test_eksenatid_kullanici_vakasi() -> None:
    """FAZİLE KULAN vakası (kullanıcı raporu, 2026-05-17).

    Rapor: "Metformin veya sülfonilürelerin maks tolere doz yetersiz glisemik
    kontrol .AKUT PANKREATİT ÖYKÜSÜ YOKTUR . BMI>35"
    """
    print('\n── Eksenatid kullanıcı vakası (FAZİLE KULAN) ──')
    metin = _RAPOR_TEMPLATE.format(
        pank='AKUT PANKREATİT ÖYKÜSÜ YOKTUR', bmi='BMI>35')
    rapor = kontrol_diyabet_dpp4_sglt2(_eksenatid_ilac(metin))
    _ok('Sonuç UYGUN',
        rapor.sonuc == KontrolSonucu.UYGUN,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')
    pank_atom = _sart_bul(rapor, 'pankreatit')
    _ok('Pankreatit atomu VAR (lafzen YOK kabul)',
        pank_atom is not None and pank_atom.durum == SartDurumu.VAR)
    bmi_atom = _sart_bul(rapor, 'BMI')
    _ok('BMI atomu VAR (lafzen > 35)',
        bmi_atom is not None and bmi_atom.durum == SartDurumu.VAR)


def test_eksenatid_pankreatit_pos_lafiz() -> None:
    print('\n── Eksenatid + pankreatit POS lafız → UYGUN_DEGIL ──')
    metin = _RAPOR_TEMPLATE.format(
        pank='Hastada akut pankreatit öyküsü vardır', bmi='BMI: 42')
    rapor = kontrol_diyabet_dpp4_sglt2(_eksenatid_ilac(metin))
    _ok('Sonuç UYGUN_DEĞİL (pankreatit kontrendike)',
        rapor.sonuc == KontrolSonucu.UYGUN_DEGIL,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')


def test_eksenatid_pankreatit_icd_k85() -> None:
    print('\n── Eksenatid + ICD K85 → UYGUN_DEGIL ──')
    metin = _RAPOR_TEMPLATE.format(pank='', bmi='BMI: 42')
    teshisler = ['E11 - Tip 2 DM', 'K85.9 - Akut pankreatit']
    rapor = kontrol_diyabet_dpp4_sglt2(_eksenatid_ilac(metin, teshisler=teshisler))
    _ok('Sonuç UYGUN_DEĞİL (ICD K85.x kontrendike)',
        rapor.sonuc == KontrolSonucu.UYGUN_DEGIL,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')


def test_eksenatid_bmi_dusuk() -> None:
    print('\n── Eksenatid + BMI: 30 → UYGUN_DEGIL ──')
    metin = _RAPOR_TEMPLATE.format(
        pank='AKUT PANKREATİT ÖYKÜSÜ YOKTUR', bmi='BMI: 30')
    rapor = kontrol_diyabet_dpp4_sglt2(_eksenatid_ilac(metin))
    _ok('Sonuç UYGUN_DEĞİL (BMI 30 < 35)',
        rapor.sonuc == KontrolSonucu.UYGUN_DEGIL,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')


def test_eksenatid_aynur_yilmaz() -> None:
    """AYNUR YILMAZ vakası (kullanıcı raporu, 2026-05-17).

    Rapor SUT verbatim lafzı + reçete açıklamasında çelişen 'BMI:29'.
    Parser SUT lafzını ('VÜCUT KİTLE İNDEKSİ ... 35 KG/M'NİN ÜZERİNDE OLAN')
    önce yakalamalı; ayrıca 'AKUT PANKREATİT GEÇİRİLME ÖYKÜSÜ BULUNMAYAN'
    NEG olarak tanınmalı.
    """
    print('\n── Eksenatid AYNUR YILMAZ vakası (SUT lafzı + bulunmayan) ──')
    rapor_metni = (
        'METFORMİN VE SÜLFONİLÜRELERİ TOLERE EDİLEBİLECEK MAKSİMUM DOZLARDA '
        'KULLANIP YETERLİ GLİSEMİK KONTROL SAĞLANAMAMIŞTIR VE VÜCUT KİTLE İNDEKSİ '
        "TEDAVİ BAŞLANGICINDA 35 KG/M'NİN ÜZERİNDE OLAN VE TEDAVİ ÖNCESİ "
        'ANEMNEZDE AKUT PANKREATİT GEÇİRİLME ÖYKÜSÜ BULUNMAYAN TİP 2 DİYABET HASTASI.'
    )
    ilac_sonuc = {
        'ilac_adi': 'BYETTA 10 MCG',
        'etkin_madde': 'EKSENATID',
        'atc_kodu': 'A10BJ01',
        'doktor_uzmanligi': 'Endokrinoloji',
        'recete_teshisleri': ['E11 - Tip 2 DM'],
        'rapor_aciklamalari': [rapor_metni, 'Tip 2 DM'],
        'recete_aciklamalari': ['BYETTA İDAME BMI:29 TİP 2 DM'],
        'rapor_kodu': '5555',
        'hasta_yasi': 60,
    }
    rapor = kontrol_diyabet_dpp4_sglt2(ilac_sonuc)
    _ok('Sonuç UYGUN',
        rapor.sonuc == KontrolSonucu.UYGUN,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')
    pank_atom = _sart_bul(rapor, 'pankreatit')
    _ok('Pankreatit atomu VAR (BULUNMAYAN tanındı)',
        pank_atom is not None and pank_atom.durum == SartDurumu.VAR)
    bmi_atom = _sart_bul(rapor, 'BMI')
    _ok('BMI atomu VAR (SUT lafzı önceliği, BMI:29 dikkate alınmadı)',
        bmi_atom is not None and bmi_atom.durum == SartDurumu.VAR)


def test_eksenatid_bmi_sayisal_42() -> None:
    print('\n── Eksenatid + BMI: 42 sayısal → UYGUN ──')
    metin = _RAPOR_TEMPLATE.format(
        pank='AKUT PANKREATİT ÖYKÜSÜ YOKTUR', bmi='BMI: 42')
    rapor = kontrol_diyabet_dpp4_sglt2(_eksenatid_ilac(metin))
    _ok('Sonuç UYGUN (BMI 42 > 35)',
        rapor.sonuc == KontrolSonucu.UYGUN,
        f'(gerçek: {rapor.sonuc.value} | mesaj: {rapor.mesaj})')


# ═══════════════════════════════════════════════════════════════════════
# 3. DPP-4 (Y4) paralel-VEYA atomları
# ═══════════════════════════════════════════════════════════════════════

def _dpp4_ilac(doktor: str, rapor_kodu: str, glisemik_var: bool = True) -> dict:
    rapor_metni = ('Metformin maksimum tolere dozda yeterli glisemik kontrol '
                    'sağlanamamıştır') if glisemik_var else 'Diyabet teşhisi mevcut'
    # Raporlu yol testlerinde rapor_kodu varsa branşı da Endo olarak set et,
    # aksi halde atom KE+sartli döner ve test SARTLI_UYGUN beklemesi gerekir.
    rapor_brans = 'Endokrinoloji ve Metabolizma Hastalıkları' if rapor_kodu else ''
    return {
        'ilac_adi': 'JANUVIA 100MG',
        'etkin_madde': 'SITAGLIPTIN FOSFAT',
        'atc_kodu': 'A10BH01',
        'doktor_uzmanligi': doktor,
        'rapor_doktor_uzmanligi': rapor_brans,
        'recete_teshisleri': ['E11.9 - Tip 2 DM'],
        'rapor_aciklamalari': [rapor_metni],
        'rapor_metni': rapor_metni,
        'rapor_kodu': rapor_kodu,
    }


def _dpp4_paralel_atomlari(rapor) -> tuple:
    """Y4 paralel-yol gruplarındaki hekim ve rapor atomlarını çek.

    2026-05-25 paralel-yol kalıbı: hekim ‖Y4‖ Raporsuz Yol grubunda,
    rapor branşı ‖Y4‖ Raporlu Yol grubunda. Her grup AND (tek-atom + klinik).
    """
    hekim_atomu = next((s for s in (rapor.sartlar or [])
                        if '‖Y4‖ Raporsuz Yol' in s.grup
                        and 'rapor' not in s.ad.lower()), None)
    rapor_atomu = next((s for s in (rapor.sartlar or [])
                        if '‖Y4‖ Raporlu Yol' in s.grup
                        and ('rapor' in s.ad.lower()
                             or 'uzman' in s.ad.lower())), None)
    return (hekim_atomu, rapor_atomu)


def test_dpp4_endo_raporsuz() -> None:
    print('\n── DPP-4 + Endo + raporsuz + glisemik OK → UYGUN, yol-a VAR ──')
    rapor = kontrol_diyabet_dpp4_sglt2(
        _dpp4_ilac('Endokrinoloji ve Metabolizma Hastalıkları', ''))
    _ok('Sonuç UYGUN', rapor.sonuc == KontrolSonucu.UYGUN,
        f'({rapor.sonuc.value})')
    yol_a, yol_b = _dpp4_paralel_atomlari(rapor)
    _ok('Raporsuz yol atomu (hekim) bulundu', yol_a is not None)
    _ok('Raporlu yol atomu (rapor) bulundu', yol_b is not None)
    _ok('Yol-a (hekim): VAR',
        yol_a is not None and yol_a.durum == SartDurumu.VAR)
    _ok('Yol-b (rapor): YOK',
        yol_b is not None and yol_b.durum == SartDurumu.YOK)


def test_dpp4_pratisyen_raporlu() -> None:
    print('\n── DPP-4 + pratisyen + RAPORLU + glisemik OK → UYGUN, yol-b VAR ──')
    rapor = kontrol_diyabet_dpp4_sglt2(_dpp4_ilac('Pratisyen Hekim', '5678'))
    _ok('Sonuç UYGUN', rapor.sonuc == KontrolSonucu.UYGUN,
        f'({rapor.sonuc.value})')
    yol_a, yol_b = _dpp4_paralel_atomlari(rapor)
    _ok('Raporsuz yol atomu (hekim) bulundu', yol_a is not None)
    _ok('Raporlu yol atomu (rapor) bulundu', yol_b is not None)
    _ok('Yol-a (hekim): YOK',
        yol_a is not None and yol_a.durum == SartDurumu.YOK)
    _ok('Yol-b (rapor): VAR',
        yol_b is not None and yol_b.durum == SartDurumu.VAR)


def test_dpp4_pratisyen_raporsuz() -> None:
    print('\n── DPP-4 + pratisyen + RAPORSUZ → UYGUN_DEGIL ──')
    rapor = kontrol_diyabet_dpp4_sglt2(_dpp4_ilac('Pratisyen Hekim', '', False))
    _ok('Sonuç UYGUN_DEĞİL',
        rapor.sonuc == KontrolSonucu.UYGUN_DEGIL,
        f'({rapor.sonuc.value})')
    yol_a, yol_b = _dpp4_paralel_atomlari(rapor)
    _ok('İki paralel yol atomu bulundu',
        yol_a is not None and yol_b is not None)
    _ok('Her iki yol da YOK',
        yol_a is not None and yol_b is not None
        and yol_a.durum == SartDurumu.YOK
        and yol_b.durum == SartDurumu.YOK)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main() -> int:
    test_pankreatit_parser()
    test_bmi_parser()
    test_bmi_esik()
    test_glisemik_varyasyon()
    test_eksenatid_kullanici_vakasi()
    test_eksenatid_pankreatit_pos_lafiz()
    test_eksenatid_pankreatit_icd_k85()
    test_eksenatid_bmi_dusuk()
    test_eksenatid_bmi_sayisal_42()
    test_eksenatid_aynur_yilmaz()
    test_dpp4_endo_raporsuz()
    test_dpp4_pratisyen_raporlu()
    test_dpp4_pratisyen_raporsuz()

    print(f'\n{"="*60}\nSONUÇ: {_BASARI}/{_TOPLAM} test geçti.')
    return 0 if _BASARI == _TOPLAM else 1


if __name__ == '__main__':
    sys.exit(main())
