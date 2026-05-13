# -*- coding: utf-8 -*-
"""SUT 4.2.28.A — Statin atomik şema akıl testi suite.

YOAK kalıbında atomik refactor sonrası (2026-05-13). Kullanıcı verdiği
SUT lafzına göre 4 üst-VEYA dalı (a/b/c/ç) + Madde 4 (yüksek doz) + Çocuk
(4.2.28.A-2) yolaklarını sınar.
"""
from recete_kontrol.sut_kontrolleri import kontrol_statin


def _yap(ilac_sonuc):
    return kontrol_statin(ilac_sonuc)


def test_case(ad, beklenen, ilac_sonuc):
    r = _yap(ilac_sonuc)
    gercek = r.sonuc.value
    durum = "OK " if gercek == beklenen else "FAIL"
    print(f"[{durum}] {ad}: beklenen={beklenen} | gercek={gercek}")
    if gercek != beklenen:
        print(f"       Mesaj: {r.mesaj[:200]}")
        for s in r.sartlar:
            if s.durum.value != 'na':
                print(f"         - [{s.durum.value}] {s.ad}: {s.neden[:90]}")
    return gercek == beklenen


# ── YETİŞKİN YOLAKLARI ─────────────────────────────────────────────────

S01_yol_a_uygun = {
    'ad': 'S01 — Yol-a: LDL>190 + 2 ölçüm uygun',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
    }}

S02_yol_a_tek_olcum = {
    'ad': 'S02 — Yol-a: LDL>190 + TEK ÖLÇÜM',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026'],
    }}

S03_yol_b_uygun = {
    'ad': 'S03 — Yol-b: LDL>160 + HT+aile + 2 ölçüm',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': [
            'LDL: 175 mg/dL 05.01.2026, LDL: 170 mg/dL 20.01.2026, '
            'Hipertansiyon mevcut, aile öyküsünde erken kardiyovasküler hastalık var',
        ],
        'recete_teshisleri': ['I10'],
    }}

S04_yol_b_yeterli_risk_yok = {
    'ad': 'S04 — Yol-b: LDL>160 + tek ek risk (yeterli değil)',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 175 mg/dL 05.01.2026, LDL: 170 mg/dL 20.01.2026, '
            'Hipertansiyon mevcut',
        ],
        'recete_teshisleri': ['I10'],
    }}

S05_yol_c_uygun = {
    'ad': 'S05 — Yol-c: LDL>130 + HT+aile+65yaş + 2 ölçüm',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 70,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': [
            'LDL: 145 mg/dL 03.01.2026, LDL: 140 mg/dL 18.01.2026, '
            'Hipertansiyon ve ailede erken koroner arter hastalığı öyküsü',
        ],
        'recete_teshisleri': ['I10'],
    }}

S06_yol_c_eksik_risk = {
    'ad': 'S06 — Yol-c: LDL>130 + sadece 2 ek risk',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [
            'LDL: 145 mg/dL 03.01.2026, LDL: 140 mg/dL 18.01.2026, '
            'Hipertansiyon ve ailede erken koroner arter hastalığı',
        ],
        'recete_teshisleri': ['I10'],
    }}

S07_yol_c2_dm = {
    'ad': 'S07 — Yol-ç: LDL>70 + DM (2 ölçüm gerekmez)',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '06.01',
        'hasta_yasi': 60,
        'doktor_uzmanligi': 'ENDOKRINOLOJI',
        'rapor_aciklamalari': ['Diyabetes mellitus tip 2, LDL: 95 mg/dL'],
        'recete_teshisleri': ['E11'],
    }}

S08_yol_c2_kah_raporkodu = {
    'ad': 'S08 — Yol-ç: LDL>70 + rapor_kodu 04.02 (KAH örtük)',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.02.1',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': ['LDL: 85 mg/dL, stent öyküsü'],
    }}

S09_ldl_dusuk_risk_yok = {
    'ad': 'S09 — LDL ≤ 70 + risk yok (statin endikasyonu yok)',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': ['LDL: 65 mg/dL'],
    }}

# ── YÜKSEK DOZ (Madde 4) ───────────────────────────────────────────────

S10_yuksek_doz_uzman_yok = {
    'ad': 'S10 — Yüksek doz (rosuv 20mg) + AİLE HEKİMİ + 24ay geçmiş bilinmiyor',
    'beklenen': 'kontrol_edilemedi',  # 24 ay belirsiz → manuel doğrulama (KE)
    'data': {
        'ilac_adi': 'CRESTOR 20 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'AILE HEKIMLIGI',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
    }}

S10b_yuksek_doz_aile_hek_pratisyen = {
    'ad': 'S10b — Yüksek doz + PRATİSYEN HEKİM (uzman değil, 24ay yok)',
    'beklenen': 'uygun_degil',  # Aile hekimi DE değil → 24ay path kapalı → YOK
    'data': {
        'ilac_adi': 'CRESTOR 20 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'PRATISYEN HEKIM',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
    }}

S11_yuksek_doz_uzman_var = {
    'ad': 'S11 — Yüksek doz (atorva 40mg) + KARDİYOLOJİ',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 40 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 60,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': [
            'LDL: 195 mg/dL 10.01.2026, LDL: 200 mg/dL 25.01.2026',
        ],
    }}

# ── ÇOCUK YOLAĞI (4.2.28.A-2) ──────────────────────────────────────────

S12_cocuk_kucuk_homoz = {
    'ad': 'S12 — Çocuk yaş<10: homozigot ailesel + LDL≥400',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'CRESTOR 5 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 8,
        'doktor_uzmanligi': 'COCUK ENDOKRINOLOJI',
        'rapor_aciklamalari': [
            'Homozigot ailesel hiperkolesterolemi, LDL: 420 mg/dL',
        ],
    }}

S13_cocuk_buyuk_ldl190 = {
    'ad': 'S13 — Çocuk yaş≥10: LDL>190',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'LIPITOR 10 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK KARDIYOLOJI',
        'rapor_aciklamalari': ['LDL: 200 mg/dL'],
    }}

# ── EDGE CASES ─────────────────────────────────────────────────────────

S14_bos_metin_raporsuz = {
    'ad': 'S14 — Boş metin + rapor kodu yok',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': [],
    }}

S15_ldl_yok_ama_rapor_kv = {
    'ad': 'S15 — LDL yok ama rapor_kodu 04.02 (KAH örtük)',
    'beklenen': 'uygun_degil',  # LDL değeri yoksa A1 endikasyon önkoşul YOK
    'data': {
        'ilac_adi': 'LIPITOR 20 MG',
        'etkin_madde': 'ATORVASTATIN',
        'rapor_kodu': '04.02',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'KARDIYOLOJI',
        'rapor_aciklamalari': ['Stent operasyonu sonrası kontrol'],
    }}

S16_iki_olcum_kisa_aralik = {
    'ad': 'S16 — Yol-a + ölçümler 5 gün arayla (kısa)',
    'beklenen': 'uygun_degil',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 15.01.2026'],
    }}

S17_yas_yok_yuksek_ldl = {
    'ad': 'S17 — Yaş yok + LDL>190 + 2 ölçüm (yetişkin varsayılır)',
    'beklenen': 'uygun',
    'data': {
        'ilac_adi': 'CRESTOR 10 MG',
        'etkin_madde': 'ROSUVASTATIN',
        'rapor_kodu': '04.08',
        'hasta_yasi': None,
        'doktor_uzmanligi': 'IC HASTALIKLARI',
        'rapor_aciklamalari': ['LDL: 210 mg/dL 10.01.2026, LDL: 215 mg/dL 25.01.2026'],
    }}


def main():
    cases = [
        S01_yol_a_uygun, S02_yol_a_tek_olcum,
        S03_yol_b_uygun, S04_yol_b_yeterli_risk_yok,
        S05_yol_c_uygun, S06_yol_c_eksik_risk,
        S07_yol_c2_dm, S08_yol_c2_kah_raporkodu,
        S09_ldl_dusuk_risk_yok,
        S10_yuksek_doz_uzman_yok, S10b_yuksek_doz_aile_hek_pratisyen,
        S11_yuksek_doz_uzman_var,
        S12_cocuk_kucuk_homoz, S13_cocuk_buyuk_ldl190,
        S14_bos_metin_raporsuz, S15_ldl_yok_ama_rapor_kv,
        S16_iki_olcum_kisa_aralik, S17_yas_yok_yuksek_ldl,
    ]
    ok = 0
    for c in cases:
        if test_case(c['ad'], c['beklenen'], c['data']):
            ok += 1
    print(f"\n{'=' * 60}")
    print(f"SONUC: {ok}/{len(cases)} senaryo basarili")
    if ok < len(cases):
        print(f"BASARISIZ: {len(cases) - ok} senaryo")


if __name__ == '__main__':
    main()
