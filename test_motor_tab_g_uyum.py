# -*- coding: utf-8 -*-
"""SUT Motor — Tab G şema renderı ile JSON şekil uyumluluk testi.

Tab G `_sema_render_devre` `satir["verdict_sartlar"]` JSON'unu okuyor
(aylik_recete_sorgu_gui.py:2904, 14624). Beklenen şema:
  [{ad, durum, neden, kaynak, grup, veya_grubu, alt_liste, sartli_atom}, ...]

Bu test:
  1. Motor üzerinden bir Fibrat senaryosu değerlendir
  2. Çıkan KontrolRaporu'nu mevcut GUI serileştirme kodu ile JSON'a dök
  3. JSON'u Tab G renderının okuduğu şemayla doğrula:
     - parse edilebilir
     - her şart dict ve gerekli alanları içeriyor
     - durum değeri SartDurumu enum value'larından biri (var/yok/kontrol_edilemedi/na)
  4. Verdict'in PILOT testindekiyle uyumlu olduğunu da kontrol et

Çalıştırma: python test_motor_tab_g_uyum.py
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol.sut_motor.uyumluluk import kontrol_fibrat_motor


# Tab G/_sema_render_devre'nin beklediği alanlar
_TAB_G_GEREKLI_ALANLAR = ('ad', 'durum', 'neden', 'grup')
_TAB_G_OPSIYONEL_ALANLAR = ('kaynak', 'veya_grubu', 'alt_liste', 'sartli_atom')
_GECERLI_DURUMLAR = ('var', 'yok', 'kontrol_edilemedi', 'na')


# Mevcut GUI serileştirme kodu (aylik_recete_sorgu_gui.py:14624-14637 birebir)
def _gui_serilestir(rapor) -> str:
    sartlar_obj = getattr(rapor, "sartlar", None) or []
    return json.dumps([
        {"ad": p.ad,
         "durum": (p.durum.value if hasattr(p.durum, "value")
                    else str(p.durum)),
         "neden": p.neden,
         "kaynak": getattr(p, "kaynak", ""),
         "grup": getattr(p, "grup", ""),
         "veya_grubu": bool(getattr(p, "veya_grubu", False)),
         "alt_liste": getattr(p, "alt_liste", None),
         "sartli_atom": bool(getattr(p, "sartli_atom", False))}
        for p in sartlar_obj
    ], ensure_ascii=False)


SENARYOLAR = [
    {
        'ad': 'Yol-a UYGUN — TG=620 + Kardiyo',
        'beklenen_verdict': 'uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'KARDIYOLOJI',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },
    {
        'ad': 'Yol-b UYGUN — TG=350 + DM + İç hast.',
        'beklenen_verdict': 'uygun',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'IC HASTALIKLARI',
            'rapor_aciklamalari': ['TG: 350 mg/dL, DM mevcut'],
            'recete_teshisleri': ['E11'],
        },
    },
    {
        'ad': 'Branş AİLE HEK → UYGUN_DEGIL',
        'beklenen_verdict': 'uygun_degil',
        'ilac': {
            'ilac_adi': 'LIPANTHYL 200 MG',
            'rapor_kodu': '04.08',
            'doktor_uzmanligi': 'AILE HEKIMI',
            'rapor_aciklamalari': ['TG: 620 mg/dL'],
        },
    },
]


def _dogrula_tab_g_jsonu(jsons: str, senaryo_ad: str) -> int:
    """JSON'u Tab G beklentilerine göre doğrula. Hata sayısı dön."""
    hatalar = 0
    try:
        sartlar = json.loads(jsons)
    except json.JSONDecodeError as e:
        print(f"   ✗ JSON parse hatası: {e}")
        return 1
    if not isinstance(sartlar, list):
        print(f"   ✗ Üst seviye liste değil: {type(sartlar)}")
        return 1
    if not sartlar:
        print(f"   ⚠ Şart listesi boş (Tab G 'şart yok' gösterir)")
        return 0  # boş liste hata değil, ama bilgi
    for i, s in enumerate(sartlar):
        if not isinstance(s, dict):
            print(f"   ✗ Şart[{i}] dict değil: {type(s)}")
            hatalar += 1
            continue
        for alan in _TAB_G_GEREKLI_ALANLAR:
            if alan not in s:
                print(f"   ✗ Şart[{i}] '{alan}' alanı yok")
                hatalar += 1
        if 'durum' in s and s['durum'] not in _GECERLI_DURUMLAR:
            print(f"   ✗ Şart[{i}] geçersiz durum: {s['durum']!r}")
            hatalar += 1
    return hatalar


def _calistir():
    print("=== SUT Motor → Tab G JSON Şekil Uyumluluk Testi ===\n")
    toplam_hata = 0
    grup_isimleri = set()
    for sen in SENARYOLAR:
        print(f"▶ {sen['ad']}")
        rapor = kontrol_fibrat_motor(sen['ilac'])
        verdict = rapor.sonuc.value
        beklenen = sen['beklenen_verdict']
        verdict_ok = (verdict == beklenen)
        print(f"   verdict:  {verdict}  (beklenen={beklenen}) "
              f"{'✓' if verdict_ok else '✗'}")
        if not verdict_ok:
            toplam_hata += 1

        jsons = _gui_serilestir(rapor)
        h = _dogrula_tab_g_jsonu(jsons, sen['ad'])
        toplam_hata += h
        if h == 0:
            sartlar = json.loads(jsons)
            print(f"   şart sayısı: {len(sartlar)}")
            for s in sartlar:
                grup_isimleri.add(s.get('grup', ''))
            # Örnek bir şart
            ilk = sartlar[0] if sartlar else {}
            print(f"   örnek şart: ad={ilk.get('ad')!r:60s} "
                  f"durum={ilk.get('durum')!r}")
        print()

    print("=" * 60)
    print(f"GRUP İSİMLERİ (Tab G şemada başlık olarak görünür):")
    for g in sorted(grup_isimleri):
        if g:
            print(f"  · {g}")
    print()
    print(f"Toplam hata: {toplam_hata}")
    print("=" * 60)
    if toplam_hata == 0:
        print("✓ Tab G entegrasyonu hazır — env var ile aktive edilebilir:")
        print("    set ECZASIST_SUT_MOTOR=FIBRAT  (Windows cmd)")
        print("    $env:ECZASIST_SUT_MOTOR='FIBRAT'  (PowerShell)")
        print("  Sonra GUI'yi çalıştır → Fibrat reçeteleri motor üzerinden")
        print("  değerlendirilir, Tab G şeması motor çıktısıyla çizilir.")
    return toplam_hata == 0


if __name__ == '__main__':
    sys.exit(0 if _calistir() else 1)
