# -*- coding: utf-8 -*-
"""Tab G Klasik Akım Şeması headless render testi."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

import json
import tkinter as tk
from recete_kontrol import sut_kontrolleri as sk
from aylik_recete_sorgu_gui import AylikReceteSorguGUI

# Mock D-1 reçete
ilac_sonuc = {
    'ilac_adi': 'XARELTO 20 MG',
    'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': [
        'Atriyal fibrilasyon tanısı, 78 yaşındadır, sağlık kurulu raporu — '
        'kardiyoloji + iç hastalıkları + nöroloji uzmanları onaylamıştır. '
        'Varfarin tedavisi altında iken serebrovasküler olay geçirmiştir.'
    ],
    'recete_teshisleri': ['I48 ATRIYAL FIBRILASYON'],
    'hasta_yasi': 78,
    'recete_ilaclari': [],
    'doktor_uzmanligi': 'KARDİYOLOJİ',
}
rapor = sk.kontrol_yoak(ilac_sonuc)
print(f'YOAK D-1 verdict: {rapor.sonuc.value}')

# Mock satır
satir = {
    'ri_id': 'TEST_KLASIK',
    'verdict': 'UYGUN' if rapor.sonuc.value == 'uygun' else 'UYGUN DEĞİL',
    'verdict_sartlar': json.dumps([
        {'ad': p.ad, 'durum': p.durum.value, 'neden': p.neden,
         'kaynak': p.kaynak, 'grup': p.grup,
         'veya_grubu': p.veya_grubu}
        for p in rapor.sartlar
    ], ensure_ascii=False),
    'verdict_sut': rapor.sut_kurali or '',
    'verdict_detaylar': json.dumps(rapor.detaylar or {}, ensure_ascii=False),
}

# Headless render — Tk root + canvas
root = tk.Tk()
root.withdraw()

# Mock'tan sadece klasik methodları kopyala
class _Mock:
    pass

mock = _Mock()
mock.root = root
mock._klasik_canvas = tk.Canvas(root, width=2000, height=600)
mock._klasik_neden_map = {}
mock._sema_tip_item = None

for attr in dir(AylikReceteSorguGUI):
    if (attr.startswith(('_klasik_', '_rbd_atom_negatif', '_rbd_grup_durumu',
                          '_rbd_atom_kis', '_KLASIK_'))
            and not attr.startswith('__')):
        v = AylikReceteSorguGUI.__dict__.get(attr)
        if v is not None:
            # method'ları mock'a bağla
            if callable(v) and not isinstance(v, (staticmethod, type)):
                # bound method bind
                import types
                setattr(mock, attr, types.MethodType(v, mock))
            else:
                setattr(_Mock, attr, v)

# sartlar listesi reconstruct
sartlar = json.loads(satir['verdict_sartlar'])
detaylar = json.loads(satir['verdict_detaylar'])
verdict = satir['verdict']

# Render!
try:
    mock._klasik_ciz_canvas(sartlar, detaylar=detaylar,
                              verdict=verdict, satir=satir)
    items = mock._klasik_canvas.find_all()
    print(f'✓ Klasik canvas render OK — {len(items)} item çizildi')
    # bbox
    bbox = mock._klasik_canvas.bbox('all')
    print(f'  canvas bbox: {bbox}')
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'✗ Render hatası: {e}')
    sys.exit(1)

root.destroy()
print('\nSonuç: Tab G headless render başarılı.')
