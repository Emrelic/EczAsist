# -*- coding: utf-8 -*-
"""Uçtan uca demo — AI'nın ürettiği JSON v2 dosyası → motor → şema.

Bu demo göstermek için: AI bir JSON v2 dosyası ürettiğinde
(SUT_AI_PROTOKOL_v1.md adımlarıyla), bu dosya doğrudan
motor + GUI'ye verilince hiçbir kod değişikliği gerektirmeden
şart listesi + verdict + şema otomatik üretilir.

Kullanım:
    python demo_v2_pipeline.py
"""
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from recete_kontrol.sut_motor.motor_v2 import (
    kural_yukle_v2, degerlendir_v2,
)

_PILOT_DOSYA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'sut_kurallari', 'v2', 'akut_hepatit_b_4_2_13_3.json',
)


def _ascii_ampul(durum):
    """SartDurumu → ASCII ampul karakteri + renk açıklaması."""
    return {
        'var': '(●)',   # yeşil dolu — sağlandı
        'yok': '(✗)',   # kırmızı çarpı — sağlanmadı
        'kontrol_edilemedi': '(?)',  # sarı soru — manuel
        'na': '(-)',
    }.get(durum, '(?)')


def _grup_durumu(atoms, veya):
    """Atom listesi + grup tipi → grup durumu (var/yok/ke)."""
    var = sum(1 for s in atoms if s.durum.value == 'var')
    yok = sum(1 for s in atoms if s.durum.value == 'yok')
    ke = sum(1 for s in atoms if s.durum.value == 'kontrol_edilemedi')
    if veya:
        if var > 0: return 'var'
        if ke > 0: return 'kontrol_edilemedi'
        return 'yok'
    if yok > 0: return 'yok'
    if ke > 0: return 'kontrol_edilemedi'
    return 'var'


def _sema_ascii_ciz(rapor):
    """SartSonuc listesini ASCII devre şeması olarak çiz.

    AND grubu → seri (yatay)
    VEYA grubu → paralel (dikey blok)
    """
    sartlar = rapor.sartlar
    if not sartlar:
        return "(şart yok)"

    # Grup bazında topla (sıra korunur)
    gruplar = {}
    sira = []
    for s in sartlar:
        g = s.grup or '(grupsuz)'
        if g not in gruplar:
            gruplar[g] = []
            sira.append(g)
        gruplar[g].append(s)

    cizgiler = []
    cizgiler.append("┌─ ⊕ ─ devre başı ─")
    for i, g in enumerate(sira):
        atoms = gruplar[g]
        veya = any(s.veya_grubu for s in atoms)
        g_durum = _grup_durumu(atoms, veya)
        g_isaret = _ascii_ampul(g_durum)
        is_bilgi = '(bilgi)' in g

        bilgi_suffix = ' [BİLGİ — matematiği bozmaz]' if is_bilgi else ''
        cizgiler.append(f"│")
        cizgiler.append(
            f"│  ┌────────────────────────────────────────────────────────")
        cizgiler.append(
            f"│  │ {'[VEYA]' if veya else '[VE]'} {g}{bilgi_suffix}")
        cizgiler.append(
            f"│  │   Grup durumu: {g_isaret} {g_durum.upper()}")

        if veya:
            for j, s in enumerate(atoms):
                konektor = '  ╱─' if j == 0 else '  ║ ' if j < len(atoms) - 1 else '  ╲─'
                cizgiler.append(
                    f"│  │ {konektor} {_ascii_ampul(s.durum.value)} "
                    f"{s.ad[:50]}")
                cizgiler.append(f"│  │      {s.neden[:60]}")
        else:
            for j, s in enumerate(atoms):
                cizgiler.append(
                    f"│  │   ── {_ascii_ampul(s.durum.value)} {s.ad[:50]}")
                cizgiler.append(f"│  │      {s.neden[:60]}")
        cizgiler.append(
            f"│  └────────────────────────────────────────────────────────")
    cizgiler.append("│")
    cizgiler.append("└─ ⊖ ─ devre sonu ─")
    return '\n'.join(cizgiler)


def _verdict_sartlar_json(rapor):
    """GUI'nin beklediği verdict_sartlar JSON formatına çevir."""
    return [
        {
            "ad": s.ad,
            "durum": s.durum.value,
            "neden": s.neden,
            "kaynak": s.kaynak,
            "grup": s.grup,
            "veya_grubu": s.veya_grubu,
            "sartli_atom": s.sartli_atom,
        }
        for s in rapor.sartlar
    ]


def demo_senaryo(kural, sen_idx):
    sen = kural['senaryolar'][sen_idx]
    print(f"\n{'═'*72}")
    print(f"  📋 SENARYO {sen_idx + 1}: {sen['ad']}")
    print(f"{'═'*72}")
    print(f"\n  Girdi reçete:")
    for anahtar, deger in sen['ilac_sonuc'].items():
        d = str(deger)
        if len(d) > 80:
            d = d[:77] + '...'
        print(f"    {anahtar:25} : {d}")

    rapor = degerlendir_v2(kural, sen['ilac_sonuc'])

    print(f"\n  Verdict: {rapor.sonuc.value.upper()}")
    print(f"  Mesaj: {rapor.mesaj}")

    print(f"\n  ── Otomatik şema (ASCII devre) ──")
    print(_sema_ascii_ciz(rapor))

    print(f"\n  ── verdict_sartlar JSON (GUI Canvas için) ──")
    js = _verdict_sartlar_json(rapor)
    print('  ' + json.dumps(js, ensure_ascii=False, indent=2).replace('\n', '\n  ')[:600])
    if len(json.dumps(js, ensure_ascii=False)) > 600:
        print('  ...')


def main():
    print("╔" + "═"*70 + "╗")
    print("║" + " "*15 + "v2 PIPELINE UÇTAN UCA DEMO" + " "*29 + "║")
    print("║" + " "*5 + "JSON yapıştır → motor çalışır → şema otomatik çıkar" + " "*14 + "║")
    print("╚" + "═"*70 + "╝")

    kural = kural_yukle_v2(_PILOT_DOSYA)
    print(f"\n📂 Yüklendi: {os.path.basename(_PILOT_DOSYA)}")
    print(f"   • {kural['sut_kodu']} — {kural['adi']}")
    print(f"   • Atom sayısı: {len(kural['atomlar'])}")
    print(f"   • Boolean formül: {kural['formul']}")
    print(f"   • Senaryo sayısı: {len(kural['senaryolar'])}")
    print(f"\n💡 Bu JSON'u AI üretti. Aşağıda 3 farklı reçete senaryosu için "
          f"\n   motor çalıştırılıp şema otomatik çiziliyor — kod hiç dokunulmadı.")

    # 3 ilginç senaryo: UYGUN, UYGUN_DEGIL, ŞÜPHELİ
    for idx in [0, 4, 2]:  # S1 (uygun), S5 (uygun_degil), S3 (şüpheli)
        demo_senaryo(kural, idx)

    print(f"\n{'═'*72}")
    print(f"  ✓ DEMO TAMAMLANDI")
    print(f"{'═'*72}")
    print(f"\n  Akış özeti:")
    print(f"    1. AI protokol uyguladı → JSON v2 üretti (sut_kurallari/v2/)")
    print(f"    2. motor_v2 dosyayı yükledi + doğruladı")
    print(f"    3. Her senaryo için atomları çalıştırdı + formülü hesapladı")
    print(f"    4. SartSonuc listesi üretti (grup + veya_grubu metadata ile)")
    print(f"    5. GUI bu listeyi okuyup Canvas'a otomatik şema çiziyor")
    print(f"       (AND→seri, VEYA→paralel, ⊕'dan ⊖'ya devre)")
    print(f"\n  Sıradaki SUT için: aynı protokolü uygula, yeni JSON üret,")
    print(f"  sut_kurallari/v2/ dizinine koy. Kod dokunmaya gerek yok.")
    print()


if __name__ == '__main__':
    main()
