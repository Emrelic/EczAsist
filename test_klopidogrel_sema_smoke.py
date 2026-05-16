# -*- coding: utf-8 -*-
"""Klopidogrel atomik şema headless render smoke testi.

Klopidogrel 4-yolaklı atomik şema (SUT 4.2.15.A):
  Y-1 stent / Y-2 AKS / Y-3 kronik / Y-4 girişimsel intravasküler.
Yolak içi AND, yolaklar arası OR.

Her senaryo için Klopidogrel SartSonuc listesi üretilir, sema_grup_matematigi
ile yolak gruplaması doğrulanır, sonra Klasik ve DMN canvas renderer'ı
çağrılıp item sayısı kontrol edilir.
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
    rapor = sk.kontrol_klopidogrel(ilac_sonuc)
    s = {
        'ri_id': ad,
        'verdict': {
            'uygun': 'UYGUN', 'uygun_degil': 'UYGUN DEGIL',
            'kontrol_edilemedi': 'SUPHELI',
        }.get(rapor.sonuc.value, 'SUPHELI'),
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
        '_rbd_atom_kis', '_KLASIK_', '_sema_grup_matematigi'))
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
    mock = _make_mock_with_methods(root, ('_dmn_', '_DMN_', '_sema_grup_matematigi'))
    mock._dmn_ciz_canvas(sartlar, detaylar=detaylar,
                          verdict=satir['verdict'], satir=satir)
    n = len(mock._dmn_canvas.find_all())
    root.destroy()
    return n


def _grup_mat_kontrol(satir, beklenen_yolak_var_keys=None):
    """sema_grup_matematigi'nin yolak sanal gruplarini ve klop birlesigini
    uretip uretmedigini kontrol et."""
    sartlar = json.loads(satir['verdict_sartlar']) if satir['verdict_sartlar'] else []
    if not sartlar:
        return None
    gmat = AylikReceteSorguGUI._sema_grup_matematigi(sartlar)
    gruplar = gmat['gruplar']
    klop_birlesik = [g for g in gruplar
                     if g.get('yolak_birlesik')]
    sanal_yolaklar = [g for g in gruplar if g.get('sanal_yolak')]
    return {
        'klop_birlesik': klop_birlesik[0] if klop_birlesik else None,
        'sanal_yolaklar': sanal_yolaklar,
        'gerekli_toplam': gmat['gerekli_toplam'],
        'saglanan_toplam': gmat['saglanan_toplam'],
    }


SENARYOLAR = [
    ('Y-1 UYGUN stent + Kardiyolog', {
        'ilac_adi': 'PLAVIX',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '',
        'recete_teshisleri': ['I25.1'],
        'mesaj_metni': 'Koroner artere stent uygulanan hasta. PKG yapildi.',
        'doktor_uzmanligi': 'Kardiyoloji',
    }),
    ('Y-2 UYGUN STEMI + Acil', {
        'ilac_adi': 'PLAVIX',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '',
        'recete_teshisleri': ['I21.0'],
        'mesaj_metni': 'STEMI tanisi, hastaneye yatis. EKG ST yukselmesi, troponin pozitif.',
        'doktor_uzmanligi': 'Acil Tip',
    }),
    ('Y-3 UYGUN anjio+KAH + Kardiyolog rapor', {
        'ilac_adi': 'PLAVIX',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '04.02.1',
        'recete_teshisleri': ['I25.1'],
        'mesaj_metni': 'Koroner anjiografi yapildi. Koroner arter hastaligi tespit.',
        'rapor_dr_brans': 'Kardiyoloji',
        'doktor_uzmanligi': 'Aile Hekimligi',
    }),
    ('Y-4 UYGUN serebral koil + Beyin Cerrahisi', {
        'ilac_adi': 'KARUM',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '',
        'recete_teshisleri': [],
        'mesaj_metni': 'Serebral girisim sonrasi koil yerlestirildi.',
        'doktor_uzmanligi': 'Beyin Cerrahisi',
    }),
    ('UYGUN_DEGIL - hicbir endikasyon', {
        'ilac_adi': 'PLAVIX',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '',
        'recete_teshisleri': ['E11.9'],
        'mesaj_metni': 'Diyabet kontrolu icin',
        'doktor_uzmanligi': 'Aile Hekimligi',
    }),
    ('Prasugrel UYGUN', {
        'ilac_adi': 'EFFIENT',
        'etkin_madde': 'PRASUGREL',
        'rapor_kodu': '',
        'recete_teshisleri': ['I21.0'],
        'mesaj_metni': 'STEMI tanisi, PKG karari alindi. EKG ST yukselmesi, '
                       'troponin pozitif. SVO oykusu yok.',
        'doktor_uzmanligi': 'Kardiyoloji',
        'hasta_yasi': 60,
        'hasta_kilosu': 80,
    }),
]


ok_klasik = 0
ok_dmn = 0
ok_gmat = 0
for ad, ilac_sonuc in SENARYOLAR:
    satir, rapor = _olustur_satir(ad, ilac_sonuc)
    sartlar_count = len(json.loads(satir['verdict_sartlar']))
    if sartlar_count == 0:
        print(f'? [{ad}] verdict_sartlar BOS (raporsuz)')
        continue

    # 1) sema_grup_matematigi yolak sanal gruplarini uretti mi?
    gm = _grup_mat_kontrol(satir)
    if gm and gm['klop_birlesik'] and len(gm['sanal_yolaklar']) >= 2:
        print(f'[OK gmat | {ad}] verdict={rapor.sonuc.value} | '
              f'sanal yolak={len(gm["sanal_yolaklar"])} | '
              f'klop birlesik saglanan={gm["klop_birlesik"]["saglanan"]}/'
              f'{gm["klop_birlesik"]["gerekli"]}')
        ok_gmat += 1
    else:
        print(f'[FAIL gmat | {ad}] yolak sanal gruplari URETILMEDI')
        if gm:
            print(f'    klop_birlesik={gm["klop_birlesik"]}, '
                  f'sanal_yolak_sayi={len(gm["sanal_yolaklar"])}')

    # 2) Klasik canvas render
    try:
        n = _render_klasik(satir)
        if n > 0:
            print(f'[OK Klasik | {ad}] items={n}')
            ok_klasik += 1
        else:
            print(f'[FAIL Klasik | {ad}] canvas bos')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'[ERR Klasik | {ad}] {e}')

    # 3) DMN canvas render
    try:
        n = _render_dmn(satir)
        if n > 0:
            print(f'[OK DMN    | {ad}] items={n}')
            ok_dmn += 1
        else:
            print(f'[FAIL DMN  | {ad}] canvas bos')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'[ERR DMN | {ad}] {e}')

print()
print(f'=== gmat: {ok_gmat}/{len(SENARYOLAR)} | '
      f'Klasik: {ok_klasik}/{len(SENARYOLAR)} | '
      f'DMN: {ok_dmn}/{len(SENARYOLAR)} ===')
sys.exit(0 if (ok_gmat + ok_klasik + ok_dmn) == 3 * len(SENARYOLAR) else 1)
