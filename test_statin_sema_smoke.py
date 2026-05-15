# -*- coding: utf-8 -*-
"""Statin atomik şema headless render smoke testi.

Şema panelinin verdict_sartlar JSON ile statin için de render edebildiğini
doğrular (YOAK paritesi).
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

import json
import tkinter as tk
from recete_kontrol import sut_kontrolleri as sk
from aylik_recete_sorgu_gui import AylikReceteSorguGUI


def _olustur_satir(ad, ilac_sonuc):
    rapor = sk.kontrol_statin(ilac_sonuc)
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


def _render_klasik(satir):
    sartlar = json.loads(satir['verdict_sartlar']) if satir['verdict_sartlar'] else []
    detaylar = json.loads(satir['verdict_detaylar']) if satir['verdict_detaylar'] else {}

    root = tk.Tk()
    root.withdraw()

    class _Mock:
        pass
    mock = _Mock()
    mock.root = root
    mock._klasik_canvas = tk.Canvas(root, width=2000, height=600)
    mock._klasik_neden_map = {}
    mock._sema_tip_item = None

    import types
    for attr in dir(AylikReceteSorguGUI):
        if (attr.startswith(('_klasik_', '_rbd_atom_negatif',
                              '_rbd_grup_durumu', '_rbd_atom_kis',
                              '_KLASIK_'))
                and not attr.startswith('__')):
            v = AylikReceteSorguGUI.__dict__.get(attr)
            if v is not None:
                if callable(v) and not isinstance(v, (staticmethod, type)):
                    setattr(mock, attr, types.MethodType(v, mock))
                else:
                    setattr(_Mock, attr, v)

    mock._klasik_ciz_canvas(sartlar, detaylar=detaylar,
                              verdict=satir['verdict'], satir=satir)
    n = len(mock._klasik_canvas.find_all())
    bbox = mock._klasik_canvas.bbox('all')
    root.destroy()
    return n, bbox


# ── 14 senaryo: SUT 4.2.28.A tüm yolaklar + yeni atomlar (CU2/C2OL/X1)
SENARYOLAR = [
    # ── YETİŞKİN — Tüm üst-VEYA dalları ──
    ('YET Yol-a UYGUN — LDL>190 + 2 ölçüm', {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
    }),
    ('YET Yol-b UYGUN DEĞİL — tek risk (HT)', {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 175 mg/dL 05.01.2026, LDL: 170 mg/dL 20.01.2026, '
            'Hipertansiyon mevcut'],
        'recete_teshisleri': ['I10'],
    }),
    ('YET Yol-ç(2) UYGUN — LDL=80 + DM (ölçüm aranmaz)', {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 60,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': ['LDL: 80 mg/dL, DM mevcut'],
        'recete_teshisleri': ['E11'],
    }),
    ('YET İdame UYGUN — tarihli rapora istinaden', {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 65,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [
            '15.01.2024 tarihli rapora istinaden, idame tedavisi'],
    }),
    ('YET Yüksek doz — Rosu 20 mg + kardiyo', {
        'ilac_adi': 'CRESTOR 20 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 60,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': [
            'LDL: 195 mg/dL 10.01.2026, LDL: 200 mg/dL 25.01.2026'],
    }),
    # ── ÇOCUK — Yeni atomlar (CU2, C2OL, CL2, CO2) ──
    ('ÇOC yaş<10 (a)(1) UYGUN — kalp-tx + LDL=420 + 6ay', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 8,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            'Kalp nakli geçirmiş, LDL: 420 mg/dL 01.02.2026',
            'LDL: 425 mg/dL 10.02.2026, 6 ay süreli rapor'],
    }),
    ('ÇOC yaş<10 (a)(2) UYGUN — LDL=200 + ≥2 aile + 6ay', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 9,
        'doktor_uzmanligi': 'COCUK ENDOKRINOLOJISI VE METABOLIZMA HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 200 mg/dL 01.03.2026, LDL: 205 mg/dL 10.03.2026',
            'Birden fazla yakın aile bireyinde erken KV',
            '6 ay süreli rapor'],
    }),
    ('ÇOC yaş<10 (a)(2) ŞÜPHELİ — aile sayım belirsiz (KE)', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 9,
        'doktor_uzmanligi': 'COCUK ENDOKRINOLOJISI',
        'rapor_aciklamalari': [
            'LDL: 195 mg/dL 01.03.2026, LDL: 200 mg/dL 10.03.2026',
            'Aile öyküsü var, 6 ay süreli rapor'],
    }),
    ('ÇOC yaş≥10 (b)(1) UYGUN — LDL=200 + 6ay', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            'LDL: 200 mg/dL 01.02.2026, LDL: 210 mg/dL 10.02.2026',
            '6 ay süreli rapor'],
    }),
    ('ÇOC yaş≥10 (b)(3) UYGUN — LDL=140 + DM (klinik KVS genişletme)', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 15,
        'doktor_uzmanligi': 'COCUK METABOLIZMA HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 140 mg/dL 01.02.2026, LDL: 145 mg/dL 10.02.2026',
            'DM tip 1 mevcut, 6 ay süreli rapor'],
        'recete_teshisleri': ['E10'],
    }),
    ('ÇOC UYGUN_DEGIL — yaş 12, LDL=150, ek koşul yok', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 12,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            'LDL: 150 mg/dL 01.02.2026, LDL: 155 mg/dL 10.02.2026',
            '6 ay süreli rapor'],
    }),
    ('ÇOC ŞÜPHELİ — 6 ay süre ibaresi yok', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            'LDL: 200 mg/dL 01.02.2026, LDL: 210 mg/dL 10.02.2026'],
    }),
    ('ÇOC İdame UYGUN — devam raporu (ölçüm aranmaz)', {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            '20.06.2025 tarihli rapora istinaden, idame tedavisi',
            '6 ay süreli rapor'],
    }),
    # ── ŞARTLI UYGUN senaryoları (sadece sartli_atom KE) ──
    ('YET ŞARTLI UYGUN — 6 ay ara verisi yok, diğerleri tamam', {
        # Yol-a şartları tam (LDL=210 + 2 ölçüm), uzman kardiyo,
        # ama son_statin_alim_tarihi pipeline'a girmediği için X1 → KE.
        # Beklenen: ŞARTLI UYGUN (6 ay ara verilmediği varsayımıyla)
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': [
            'LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
        # son_statin_alim_tarihi YOK → X1 = KE → ŞARTLI UYGUN
    }),
    ('ÇOC ŞARTLI UYGUN — 6 ay rapor süresi metinde yok', {
        # Çocuk yaş≥10 b(1): LDL>190 ✓, 2 ölçüm ✓, çocuk kardiyoloji ✓
        # Sadece "6 ay" ibaresi raporda yok → CU2 = KE → ŞARTLI UYGUN
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJISI',
        'rapor_aciklamalari': [
            'LDL: 200 mg/dL 01.02.2026, LDL: 210 mg/dL 10.02.2026'],
        # "6 ay süreli" ibaresi YOK → CU2 = KE → ŞARTLI UYGUN
    }),
]

ok = 0
for ad, ilac_sonuc in SENARYOLAR:
    try:
        satir, rapor = _olustur_satir(ad, ilac_sonuc)
        sartlar_count = len(json.loads(satir['verdict_sartlar']))
        if sartlar_count == 0:
            print(f'✗ [{ad}] verdict_sartlar BOŞ — sema panel render edemez')
            continue
        n, bbox = _render_klasik(satir)
        if n > 0:
            print(f'✓ [{ad}] verdict={rapor.sonuc.value} | '
                  f'{sartlar_count} atom | canvas items={n}')
            ok += 1
        else:
            print(f'✗ [{ad}] canvas boş — render başarısız')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'✗ [{ad}] Hata: {e}')

print(f'\nSONUÇ: {ok}/{len(SENARYOLAR)} senaryo şema render başarılı.')
