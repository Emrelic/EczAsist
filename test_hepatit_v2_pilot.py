# -*- coding: utf-8 -*-
"""SUT 4.2.13(3) Akut Hepatit B — v2 motor pilot test.

JSON v2 dosyasındaki yerleşik senaryolar üzerinden uçtan uca doğrulama.
Bu test pilot başarısının kanıtıdır: AI'nın ürettiği JSON v2 dosyası,
kod dokunmadan motor + verdict üretimi yapıyor.

Kullanım:
    python test_hepatit_v2_pilot.py

Pilot: docs/SUT_AI_PROTOKOL_v1.md (2026-05-23)
"""
import os
import sys

# Stdout UTF-8 (Windows için)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from recete_kontrol.sut_motor.motor_v2 import (
    kural_yukle_v2, degerlendir_v2, senaryo_calistir,
)
from recete_kontrol.sut_motor.formul_parser import (
    parse_formul, kullanilan_atomlar,
)

_PROJE_KOK = os.path.dirname(os.path.abspath(__file__))
_PILOT_DOSYA = os.path.join(
    _PROJE_KOK, 'sut_kurallari', 'v2', 'akut_hepatit_b_4_2_13_3.json')


def test_jsonu_yukleme(k):
    """Şema doğrulama yükleme sırasında otomatik geçmeli."""
    assert k['schema_version'] == 'v2'
    assert k['sut_kodu'] == '4.2.13(3)'
    assert 'atomlar' in k
    assert 'formul' in k
    assert len(k['atomlar']) >= 6
    assert len(k['senaryolar']) >= 5


def test_formul_atomlari(k):
    """Formülde geçen tüm atom referansları atomlar bölümünde tanımlı."""
    agac = parse_formul(k['formul'])
    kullanilan = kullanilan_atomlar(agac)
    tanimsiz = kullanilan - set(k['atomlar'])
    assert not tanimsiz, f'Formülde tanımsız atomlar: {tanimsiz}'


def test_atomlar_kaynak_metadata(k):
    """Her atom kaynak alanına sahip (görsel/dokümanter)."""
    for ad, tanim in k['atomlar'].items():
        assert 'kaynak' in tanim, f"Atom {ad}: kaynak alanı eksik"
        assert 'tip' in tanim, f"Atom {ad}: tip alanı eksik"
        assert 'ad' in tanim, f"Atom {ad}: insan-okur 'ad' alanı eksik"


def test_negatif_atomlarda_sessizlik_default_ke(k):
    """regex_negatif tipli atomlarda sessizlik default mutlaka KE olmalı
    (CLAUDE.md §2.5 örtük kabul yasağı)."""
    for ad, tanim in k['atomlar'].items():
        if tanim['tip'] == 'regex_negatif':
            sd = tanim.get('sessizlik_default', '').upper()
            assert sd == 'KE', (
                f"Atom {ad}: regex_negatif sessizlik_default 'KE' olmalı, "
                f"bulundu: {sd!r}")


def test_bilgi_atomlari_matematik_etkisi(k):
    """Bilgi atomları (bilgi=true) formüle dahil değil — matematiği bozmaz."""
    agac = parse_formul(k['formul'])
    formuldeki = kullanilan_atomlar(agac)
    for ad, tanim in k['atomlar'].items():
        if tanim.get('bilgi'):
            assert ad not in formuldeki, (
                f"Bilgi atomu {ad} formülde geçmemeli (matematiği bozar). "
                f"Formül: {k['formul']}")


def test_demo_sart_listesi_uretiyor(k):
    """Demo: bir senaryo için SartSonuc listesi tüm atomları içermeli."""
    sen = k['senaryolar'][0]
    rapor = degerlendir_v2(k, sen['ilac_sonuc'])
    assert len(rapor.sartlar) == len(k['atomlar']), (
        f"{len(k['atomlar'])} atom bekleniyordu, "
        f"{len(rapor.sartlar)} bulundu")
    gruplar = {s.grup for s in rapor.sartlar if s.grup}
    assert len(gruplar) >= 3, (
        f"En az 3 farklı grup beklenir, bulundu: {gruplar}")


def test_yerlesik_senaryo(k, i):
    """JSON içindeki yerleşik senaryoları sırayla koş."""
    basarili, rapor, mesaj = senaryo_calistir(k, i)
    if not basarili:
        detay = '\n'.join(
            f'    - [{s.durum.value}] {s.ad}: {s.neden[:120]}'
            for s in (rapor.sartlar if rapor else []))
        raise AssertionError(
            f"Senaryo {i} ({k['senaryolar'][i]['ad']}) başarısız:\n"
            f"  {mesaj}\n{detay}")


def main():
    k = kural_yukle_v2(_PILOT_DOSYA)

    tests = [
        ('Yükleme + şema doğrulama', lambda: test_jsonu_yukleme(k)),
        ('Formül atomları tanımlı', lambda: test_formul_atomlari(k)),
        ('Atom kaynak metadata', lambda: test_atomlar_kaynak_metadata(k)),
        ('Negatif atomlarda sessizlik=KE',
         lambda: test_negatif_atomlarda_sessizlik_default_ke(k)),
        ('Bilgi atomları formül dışı',
         lambda: test_bilgi_atomlari_matematik_etkisi(k)),
        ('SartSonuc listesi üretimi',
         lambda: test_demo_sart_listesi_uretiyor(k)),
    ]
    for i in range(len(k['senaryolar'])):
        tests.append(
            (f'Senaryo S{i+1}: {k["senaryolar"][i]["ad"][:40]}',
             lambda i=i: test_yerlesik_senaryo(k, i)))

    print(f'\n{"="*70}')
    print(f'SUT 4.2.13(3) Akut Hepatit B — v2 motor pilot test')
    print(f'{"="*70}\n')

    ok = fail = 0
    for ad, fn in tests:
        try:
            fn()
            print(f'  ✓ {ad}')
            ok += 1
        except AssertionError as e:
            print(f'  ✗ {ad}')
            for satir in str(e).split('\n')[:6]:
                print(f'      {satir}')
            fail += 1
        except Exception as e:
            print(f'  ✗ ERROR: {ad} → {e}')
            fail += 1

    print(f'\n{"="*70}')
    print(f'SONUÇ: {ok}/{ok+fail} TEST GEÇTİ')
    if fail == 0:
        print(f'✓ Pilot uçtan uca çalışıyor — JSON v2 → motor → SartSonuc → '
              f'verdict pipeline tamam')
    print(f'{"="*70}\n')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
