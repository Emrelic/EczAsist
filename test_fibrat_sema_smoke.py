# -*- coding: utf-8 -*-
"""Fibrat atomik şema headless render smoke testi.

Aktif sekmeler (snapshot 3cd6b33):
- Tab D — DMN Karar Modeli (_dmn_ciz_canvas)
- Tab G — Klasik Akım Şeması (_klasik_ciz_canvas)

Her senaryo için fibrat SartSonuc listesi üretilir, ardından her iki
canvas renderer'ı çağrılıp item sayısı / bbox kontrol edilir.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

import json
import types
import tkinter as tk
from recete_kontrol import sut_kontrolleri as sk
from aylik_recete_sorgu_gui import AylikReceteSorguGUI


def _olustur_satir(ad, ilac_sonuc):
    rapor = sk.kontrol_fibrat(ilac_sonuc)
    s = {
        'ri_id': ad,
        'verdict': {
            'uygun': 'UYGUN', 'uygun_degil': 'UYGUN DEĞİL',
            'kontrol_edilemedi': 'ŞÜPHELİ',
        }.get(rapor.sonuc.value, 'ŞÜPHELİ'),
        'verdict_sartlar': json.dumps([
            {'ad': p.ad,
             'durum': p.durum.value,
             'neden': p.neden,
             'kaynak': getattr(p, 'kaynak', ''),
             'grup': getattr(p, 'grup', ''),
             'veya_grubu': bool(getattr(p, 'veya_grubu', False))}
            for p in rapor.sartlar
        ], ensure_ascii=False),
        'verdict_sut': rapor.sut_kurali or '',
        'verdict_detaylar': json.dumps(rapor.detaylar or {},
                                        ensure_ascii=False),
        'ilac': ilac_sonuc.get('ilac_adi', ''),
    }
    return s, rapor


def _make_mock_with_methods(root, prefix_keys):
    class _Mock:
        pass
    mock = _Mock()
    mock.root = root
    mock._klasik_canvas = tk.Canvas(root, width=2000, height=600)
    mock._klasik_neden_map = {}
    mock._dmn_canvas = tk.Canvas(root, width=2000, height=600)
    mock._dmn_neden_map = {}
    mock._sema_tip_item = None
    for attr in dir(AylikReceteSorguGUI):
        if (any(attr.startswith(p) for p in prefix_keys)
                and not attr.startswith('__')):
            v = AylikReceteSorguGUI.__dict__.get(attr)
            if v is not None:
                if callable(v) and not isinstance(v, (staticmethod, type)):
                    setattr(mock, attr, types.MethodType(v, mock))
                else:
                    setattr(_Mock, attr, v)
    return mock


def _render_klasik(satir):
    sartlar = json.loads(satir['verdict_sartlar']) if satir['verdict_sartlar'] else []
    detaylar = json.loads(satir['verdict_detaylar']) if satir['verdict_detaylar'] else {}
    root = tk.Tk()
    root.withdraw()
    mock = _make_mock_with_methods(root, (
        '_klasik_', '_rbd_atom_negatif', '_rbd_grup_durumu',
        '_rbd_atom_kis', '_KLASIK_'))
    mock._klasik_ciz_canvas(sartlar, detaylar=detaylar,
                              verdict=satir['verdict'], satir=satir)
    n = len(mock._klasik_canvas.find_all())
    root.destroy()
    return n


def _render_dmn(satir):
    sartlar = json.loads(satir['verdict_sartlar']) if satir['verdict_sartlar'] else []
    detaylar = json.loads(satir['verdict_detaylar']) if satir['verdict_detaylar'] else {}
    root = tk.Tk()
    root.withdraw()
    mock = _make_mock_with_methods(root, ('_dmn_', '_DMN_'))
    mock._dmn_ciz_canvas(sartlar, detaylar=detaylar,
                          verdict=satir['verdict'], satir=satir)
    n = len(mock._dmn_canvas.find_all())
    root.destroy()
    return n


SENARYOLAR = [
    ('Yol-a UYGUN — TG=620 Kardiyo', {
        'ilac_adi': 'LIPANTHYL 200 MG',
        'rapor_kodu': '04.08',
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': ['TG: 620 mg/dL'],
    }),
    ('Yol-b UYGUN — TG=250 + DM + KVC', {
        'ilac_adi': 'LIPANTHYL 200 MG',
        'rapor_kodu': '04.08',
        'doktor_uzmanligi': 'KALP VE DAMAR CERRAHISI',
        'rapor_aciklamalari': ['TG: 250 mg/dL, DM mevcut'],
        'recete_teshisleri': ['E11'],
    }),
    ('UYGUN_DEGIL — TG=250 risk yok', {
        'ilac_adi': 'LIPANTHYL 200 MG',
        'rapor_kodu': '04.08',
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': ['TG: 250 mg/dL'],
    }),
    ('UYGUN_DEGIL — Aile hekimi', {
        'ilac_adi': 'LIPANTHYL 200 MG',
        'rapor_kodu': '04.08',
        'doktor_uzmanligi': 'AILE HEKIMI',
        'rapor_aciklamalari': ['TG: 620 mg/dL'],
    }),
    ('Raporsuz', {
        'ilac_adi': 'LIPANTHYL 200 MG',
        'rapor_kodu': '',
        'doktor_uzmanligi': '',
        'rapor_aciklamalari': [],
    }),
]

ok_klasik = 0
ok_dmn = 0
for ad, ilac_sonuc in SENARYOLAR:
    satir, rapor = _olustur_satir(ad, ilac_sonuc)
    sartlar_count = len(json.loads(satir['verdict_sartlar']))
    if sartlar_count == 0:
        print(f'⚠ [{ad}] verdict_sartlar BOŞ (raporsuz — beklenen)')
        ok_klasik += 1
        ok_dmn += 1
        continue
    try:
        n = _render_klasik(satir)
        if n > 0:
            print(f'✓ [Klasik|{ad}] verdict={rapor.sonuc.value} | '
                  f'{sartlar_count} atom | items={n}')
            ok_klasik += 1
        else:
            print(f'✗ [Klasik|{ad}] canvas boş')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'✗ [Klasik|{ad}] Hata: {e}')
    try:
        n = _render_dmn(satir)
        if n > 0:
            print(f'✓ [DMN   |{ad}] items={n}')
            ok_dmn += 1
        else:
            print(f'✗ [DMN   |{ad}] canvas boş')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'✗ [DMN   |{ad}] Hata: {e}')

print(f'\nSONUÇ: Klasik {ok_klasik}/{len(SENARYOLAR)}, '
      f'DMN {ok_dmn}/{len(SENARYOLAR)}')
sys.exit(0 if (ok_klasik == len(SENARYOLAR)
               and ok_dmn == len(SENARYOLAR)) else 1)
