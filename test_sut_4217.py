# -*- coding: utf-8 -*-
"""SUT 4.2.17 (Osteoporoz) — akıl testi senaryoları."""
import sys
sys.path.insert(0, '.')
from recete_kontrol import sut_kontrolleri as sk
from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu


def yazdir(baslik, rapor):
    sonuc = rapor.sonuc.value if hasattr(rapor.sonuc, 'value') else rapor.sonuc
    print(f"\n=== {baslik} ===")
    print(f"  Sonuç: {sonuc}")
    print(f"  Mesaj: {rapor.mesaj}")
    if rapor.uyari:
        print(f"  Uyarı: {rapor.uyari[:200]}")
    if rapor.sartlar:
        print(f"  Şartlar ({len(rapor.sartlar)}):")
        for s in rapor.sartlar[:20]:
            ikon = {'var': '✓', 'yok': '✗', 'kontrol_edilemedi': '?'}.get(s.durum.value, '·')
            print(f"    {ikon} {s.ad}: {s.neden[:80]}")


def test(baslik, beklenen, rapor):
    sonuc = rapor.sonuc.value if hasattr(rapor.sonuc, 'value') else rapor.sonuc
    ok = sonuc == beklenen
    iz = "✓ PASS" if ok else "✗ FAIL"
    print(f"{iz} | beklenen={beklenen}, gerçek={sonuc} | {baslik}")
    return ok


print("\n" + "="*70)
print("SUT 4.2.17 AKIL TESTİ")
print("="*70)

basarisiz = []

# ── Senaryo 1: Bifosfonat raporsuz → UYGUN_DEGIL ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '',
})
if not test("S1: Bifosfonat raporsuz", "uygun_degil", r): basarisiz.append("S1")

# ── Senaryo 2: 75 yaş üstü + rapor → UYGUN (KMY gerekmez) ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 78,
    'doktor_uzmanligi': 'iç hastalıkları',
    'rapor_aciklamalari': ['osteoporoz tedavisi'],
})
if not test("S2: 75+ yaş + rapor", "uygun", r): basarisiz.append("S2")

# ── Senaryo 3: 65+ yaş + T=-2.6 → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 68,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['DEXA KMY tarihi: 15.04.2025 lomber T: -2.7 femur boynu T: -2.4'],
})
if not test("S3: 65+ + T=-2.7 lomber", "uygun", r): basarisiz.append("S3")

# ── Senaryo 4: 60 yaş + T=-2.6 (65 altı, eşik -3) → UYGUN_DEGIL ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 60,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['lomber T-skoru: -2.6'],
})
if not test("S4: 60 yaş + T=-2.6 (eşik -3)", "uygun_degil", r): basarisiz.append("S4")

# ── Senaryo 5: 60 yaş + T=-3.2 → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 60,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['femur boynu T-skoru: -3.2'],
})
if not test("S5: 60 yaş + T=-3.2", "uygun", r): basarisiz.append("S5")

# ── Senaryo 6: Sekonder osteo (RA) + T=-1.5 → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 55,
    'doktor_uzmanligi': 'romatoloji',
    'rapor_aciklamalari': ['Romatoid artrit + osteoporoz, lomber T-skoru: -1.5'],
    'recete_teshisleri': ['M06.9 Romatoid artrit'],
})
if not test("S6: RA + T=-1.5", "uygun", r): basarisiz.append("S6")

# ── Senaryo 7: Kortikosteroid kelimesi var ama doz/süre yok → KONTROL_EDILEMEDI dalı ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 55,
    'doktor_uzmanligi': 'romatoloji',
    'rapor_aciklamalari': ['Hasta kortikosteroid kullanıyor, T-skoru: -1.8'],
})
# Steroid kelime VAR ama doz/süre YOK + kırık YOK → karar matrisinde sekonder=False
# T=-1.8 + 55 yaş + kırık yok + sekonder yok → UYGUN_DEGIL (T > -3 ve şart yok)
if not test("S7: Kortikosteroid kelime ama doz/süre yok", "uygun_degil", r): basarisiz.append("S7")

# ── Senaryo 8: Kortikosteroid 10 mg/gün 6 ay + T=-1.5 → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 55,
    'doktor_uzmanligi': 'romatoloji',
    'rapor_aciklamalari': ['Prednizolon 10 mg/gün 6 ay kullanıyor, T-skoru: -1.5'],
})
if not test("S8: Steroid 10mg 6ay + T=-1.5", "uygun", r): basarisiz.append("S8")

# ── Senaryo 9: Juvenil osteoporoz (yaş 14) + rapor → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 14,
    'doktor_uzmanligi': 'çocuk endokrinoloji',
})
if not test("S9: Juvenil osteoporoz raporlu", "uygun", r): basarisiz.append("S9")

# ── Senaryo 10: Paget hastalığı (M88) + endokrin → UYGUN ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'ACTONEL',
    'etkin_madde': 'RISEDRONAT SODYUM',
    'rapor_kodu': '06.02',
    'hasta_yasi': 65,
    'doktor_uzmanligi': 'endokrinoloji ve metabolizma hastalıkları',
    'recete_teshisleri': ['M88.9 Paget hastalığı'],
})
if not test("S10: Paget + endokrin", "uygun", r): basarisiz.append("S10")

# ── Senaryo 11: HO endikasyonu (M61) → UYGUN (KMY gerekmez) ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 45,
    'doktor_uzmanligi': 'ortopedi',
    'rapor_aciklamalari': ['Heterotopik ossifikasyon, kalça çıkığı sonrası'],
    'recete_teshisleri': ['M61.0 Travmatik miyozitis ossifikan'],
})
if not test("S11: HO endikasyonu", "uygun", r): basarisiz.append("S11")

# ── Senaryo 12: Aktif D vitamini osteoporozda → UYGUN_DEGIL ──
r = sk.kontrol_aktif_d_vitamini({
    'ilac_adi': 'ROCALTROL 0.25 MCG',
    'etkin_madde': 'KALSITRIOL',
    'rapor_kodu': '06.01',
    'rapor_aciklamalari': ['Postmenopozal osteoporoz tanısı'],
})
if not test("S12: Kalsitriol osteoporozda", "uygun_degil", r): basarisiz.append("S12")

# ── Senaryo 13: Aktif D vitamini renal osteodistrofi → UYGUN ──
r = sk.kontrol_aktif_d_vitamini({
    'ilac_adi': 'ROCALTROL 0.25 MCG',
    'etkin_madde': 'KALSITRIOL',
    'rapor_kodu': '03.01',
    'rapor_aciklamalari': ['Kronik böbrek yetmezliği, renal osteodistrofi'],
    'recete_teshisleri': ['N18.5'],
})
if not test("S13: Kalsitriol renal osteodistrofi", "uygun", r): basarisiz.append("S13")

# ── Senaryo 14: Raloksifen sağlık kurulu raporu yok → KONTROL_EDILEMEDI ──
r = sk.kontrol_raloksifen({
    'ilac_adi': 'EVISTA 60 MG',
    'etkin_madde': 'RALOKSIFEN HCL',
    'rapor_kodu': '06.01',
    'hasta_yasi': 65,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['Postmenopozal osteoporoz, T-skoru: -2.7'],
})
# SK ibaresi yok → KONTROL_EDILEMEDI
if not test("S14: Raloksifen SK yok", "kontrol_edilemedi", r): basarisiz.append("S14")

# ── Senaryo 15: Raloksifen + SK + intolerans + T uygun → UYGUN ──
r = sk.kontrol_raloksifen({
    'ilac_adi': 'EVISTA 60 MG',
    'etkin_madde': 'RALOKSIFEN HCL',
    'rapor_kodu': '06.01',
    'hasta_yasi': 65,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'Postmenopozal osteoporoz, lomber T-skoru: -2.7',
        'Bifosfonat intoleransı (gis intolerans), endokrinoloji uzmanı tarafından düzenlenen sağlık kurulu raporu',
    ],
})
if not test("S15: Raloksifen tam şartlı", "uygun", r): basarisiz.append("S15")

# ── Senaryo 16: Kalsitonin ağrılı vertebral kırık + SK → UYGUN ──
r = sk.kontrol_kalsitonin({
    'ilac_adi': 'MIACALCIC NASAL SPRAY',
    'etkin_madde': 'KALSITONIN SOMON',
    'rapor_kodu': '06.01',
    'hasta_yasi': 72,
    'doktor_uzmanligi': 'fiziksel tıp ve rehabilitasyon',
    'rapor_aciklamalari': [
        'Ağrılı vertebra kompresyon kırığı, sağlık kurulu raporu',
    ],
    'recete_teshisleri': ['M80.08 Postmenopozal osteoporoz vertebra kırığı ile'],
})
if not test("S16: Kalsitonin ağrılı vert kırık", "uygun", r): basarisiz.append("S16")

# ── Senaryo 17: Kalsitonin Sudek atrofisi → UYGUN ──
r = sk.kontrol_kalsitonin({
    'ilac_adi': 'MIACALCIC',
    'etkin_madde': 'KALSITONIN SOMON',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'fiziksel tıp ve rehabilitasyon',
    'rapor_aciklamalari': ['Sudek atrofisi tanısı, son 3 ay içinde'],
    'recete_teshisleri': ['M89.0'],
})
if not test("S17: Kalsitonin Sudek", "uygun", r): basarisiz.append("S17")

# ── Senaryo 18: Kombinasyon yasağı — bifosfonat + raloksifen ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 70,
    'rapor_aciklamalari': ['lomber T: -2.8'],
    'recete_ilaclari': [{'ad': 'EVISTA 60 MG'}],
})
if not test("S18: Bifosfonat + Raloksifen kombi", "uygun_degil", r): basarisiz.append("S18")

# ── Senaryo 19: Denosumab/Prolia raporsuz → UYGUN_DEGIL ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'PROLIA 60 MG',
    'etkin_madde': 'DENOSUMAB',
    'rapor_kodu': '',
})
if not test("S19: Prolia raporsuz", "uygun_degil", r): basarisiz.append("S19")

# ── Senaryo 20: Denosumab prostat Ca + onkoloji + SK ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'PROLIA 60 MG',
    'etkin_madde': 'DENOSUMAB',
    'rapor_kodu': '06.01',
    'hasta_yasi': 72,
    'rapor_aciklamalari': [
        'Prostat kanseri, hormon ablasyon tedavisi (LHRH agonist).',
        'Tıbbi onkoloji uzmanı tarafından düzenlenen sağlık kurulu raporu.',
    ],
    'recete_teshisleri': ['C61 Prostat Ca'],
})
if not test("S20: Prolia prostat Ca + onkoloji SK", "uygun", r): basarisiz.append("S20")

# ── Senaryo 21: XGEVA raporlu → UYGUN ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'XGEVA 120 MG',
    'etkin_madde': 'DENOSUMAB',
    'rapor_kodu': '02.01',
    'recete_teshisleri': ['C79.5 Kemik metastazı'],
})
if not test("S21: XGEVA raporlu", "uygun", r): basarisiz.append("S21")

# ── Senaryo 22: Romosozumab + MI öyküsü → UYGUN_DEGIL (kontrendike) ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'EVENITY 105 MG',
    'etkin_madde': 'ROMOSOZUMAB',
    'rapor_kodu': '06.01',
    'hasta_yasi': 70,
    'rapor_aciklamalari': ['Postmenopozal osteoporoz, miyokard infarktüs öyküsü 2024'],
    'recete_teshisleri': ['I21.4 MI'],
})
if not test("S22: Romosozumab MI öyküsü kontrendike", "uygun_degil", r): basarisiz.append("S22")

# ── Senaryo 23: KMY tarihi 3 yıl önce → KMY 2 yıl şartı YOK olarak işaretlenmeli ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 68,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['DEXA KMY tarihi: 10.05.2022 lomber T-skoru: -2.7'],
})
# Sonuç UYGUN olabilir (T-skoru eşiği sağlandı) ama KMY tarih şartı YOK olmalı
kmy_yok = any(s.ad.startswith('KMY tarihi') and s.durum == SartDurumu.YOK
              for s in r.sartlar)
ok = kmy_yok
iz = "✓ PASS" if ok else "✗ FAIL"
print(f"{iz} | KMY > 2 yıl YOK olarak işaretlenmeli | KMY YOK var mı: {kmy_yok}")
if not ok: basarisiz.append("S23")

# ── Senaryo 24: Kategori tespiti — DENOSUMAB → OSTEOPOROZ_BIYOLOJIK ──
kat = sk.sut_kategorisi_tespit_et({
    'ilac_adi': 'PROLIA 60 MG',
    'etkin_madde': 'DENOSUMAB',
})
ok = kat == 'OSTEOPOROZ_BIYOLOJIK'
iz = "✓ PASS" if ok else "✗ FAIL"
print(f"{iz} | Kategori PROLIA→OSTEOPOROZ_BIYOLOJIK | gerçek={kat}")
if not ok: basarisiz.append("S24")

# ── Senaryo 25: Kategori tespiti — RALOKSIFEN ──
kat = sk.sut_kategorisi_tespit_et({
    'ilac_adi': 'EVISTA 60 MG',
    'etkin_madde': 'RALOKSIFEN HCL',
})
ok = kat == 'RALOKSIFEN'
iz = "✓ PASS" if ok else "✗ FAIL"
print(f"{iz} | Kategori EVISTA→RALOKSIFEN | gerçek={kat}")
if not ok: basarisiz.append("S25")

# ── Senaryo 26: Kategori tespiti — KALSITONIN ──
kat = sk.sut_kategorisi_tespit_et({
    'ilac_adi': 'MIACALCIC NASAL SPRAY',
    'etkin_madde': 'KALSITONIN SOMON',
})
ok = kat == 'KALSITONIN'
iz = "✓ PASS" if ok else "✗ FAIL"
print(f"{iz} | Kategori MIACALCIC→KALSITONIN | gerçek={kat}")
if not ok: basarisiz.append("S26")

# ── Senaryo 27: Kategori tespiti — KALSITRIOL → AKTIF_D_VITAMINI ──
kat = sk.sut_kategorisi_tespit_et({
    'ilac_adi': 'ROCALTROL 0.25 MCG',
    'etkin_madde': 'KALSITRIOL',
})
ok = kat == 'AKTIF_D_VITAMINI'
iz = "✓ PASS" if ok else "✗ FAIL"
print(f"{iz} | Kategori ROCALTROL→AKTIF_D_VITAMINI | gerçek={kat}")
if not ok: basarisiz.append("S27")



# ── Senaryo 28: HİKMET — 56 yaş erkek + boşluklu eksi T-SKOR ──
# "BULGULAR:56 YAŞ ERKEK HASTA L1-L4 TOTAL T-SKOR : - 2.6"
# 65 altı + T=-2.6 + kırıksız + sekonder yok → UYGUN_DEGIL (eşik T ≤ -3)
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'fizik tedavi',
    'rapor_aciklamalari': [
        'BULGULAR:56 YAŞ ERKEK HASTA L1-L4 TOTAL T-SKOR : - 2.6 '
        'ÖLÇÜM TARIHI:12.03.2025'
    ],
})
if not test("S28: HİKMET 56 yaş 'TOTAL T-SKOR : - 2.6'", "uygun_degil", r):
    basarisiz.append("S28")

# ── Senaryo 29: FATMA — 69 yaş + tam sayı T SKOR:-3 + ters yaş ──
# 65+ + T=-3 + 2'den fazla kırık → UYGUN
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'ZOMETA 5 MG',
    'etkin_madde': 'ZOLEDRONIK ASIT',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'ortopedi',
    'rapor_aciklamalari': [
        'BULGULAR:M80.0 2 DEN FAZLA KIRIK ILE SOL ÖN KOL T SKOR:-3 '
        'HASTA 69 YAŞINDADIR.KEMIK ÖLÇÜM TARIHI:11.03.2026 RÖNTGENLE '
        'KESIN TANI KONULMUŞTUR.KIRIK ÖYKÜSÜ (+)'
    ],
    'recete_teshisleri': ['M80.0'],
})
if not test("S29: FATMA 69 yaş 'T SKOR:-3' tam sayı", "uygun", r):
    basarisiz.append("S29")

# ── Senaryo 30: SENİHA — anchor=TOTAL SKOR (T yok) ──
# yaş bilinmiyor + T=-3,2 → "YAS_BILINMIYOR_T_-3" UYGUN
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['*13.02.2026 L1-L4 TOTAL SKOR -3,2'],
})
if not test("S30: SENİHA 'TOTAL SKOR -3,2' (T anchor yok)", "uygun", r):
    basarisiz.append("S30")

# ── Senaryo 31: KADRİYE — anchor↔sayı arası 'l1-l4' token ──
# yaş bilinmiyor + T=-3.6 → UYGUN
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['t-skor l1-l4 -3.6 16.06.2025'],
})
if not test("S31: KADRİYE 't-skor l1-l4 -3.6' (token arada)",
            "uygun", r):
    basarisiz.append("S31")

# ── Senaryo 32: NERMİN — typo 'T-SCOR' (R sonu yok) ──
# yaş bilinmiyor + T=-3,6 → UYGUN
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        '17/02/2026 TARİHLİ DEXA : L1- L4 T-SCOR : -3,6'
    ],
})
if not test("S32: NERMİN 'T-SCOR : -3,6' (typo)", "uygun", r):
    basarisiz.append("S32")

# ── Senaryo 33: Eksi unutulmuş — pozitif değer negatif kabul edilir ──
# 'T-skoru: 2.6' → -2.6 olarak yorumlanır (T-skoru pratikte hep negatif)
# 65+ + T=-2.6 → UYGUN
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01',
    'hasta_yasi': 70,
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'lomber T-skoru: 2.6 ölçüm tarihi 15.04.2025'
    ],
})
if not test("S33: Eksi unutulmuş 'T-skoru: 2.6' → -2.6 kabul",
            "uygun", r):
    basarisiz.append("S33")

# ════════════════════════════════════════════════════════════════════════
# TERİPARATİD ÖN-KOŞUL ŞARTLARI (SUT 4.2.17.A(6)(b) + 4.1.4)
# ════════════════════════════════════════════════════════════════════════

# ── S34: FATMA BEHREM senaryosu — teriparatid + endikasyon dışı +
#        bifosfonat ön-koşul lafzı yok → KONTROL_EDILEMEDI (şüpheli) ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORSTEO 20 MCG/80 MIKROL ENJ COZ',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': '25194SW8',
    'hasta_yasi': 77,
    'cinsiyet': 'K',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        '77 YAŞINDA KADIN HASTA 07.11.2025 BAŞVURU TARİHLİ '
        '07.11.2025 KARAR TARİHLİ 25194SW8 BAŞVURU NUMARALI '
        'TERİPARATİD 6 AYLIK ENDIKASYON DIŞI İLAÇ KULLANIMI '
        'MEVCUTTUR 05.11.2025 TARİHLİ DXA DA LOMBER L1/L4 '
        'TOTAL T SKOR:-0.6 FEMUR BOYNU T SKOR:-2.2 FEMUR '
        'TOTAL T SKOR:-2.7 TERİPARATİD BAŞLANGIÇ RAPORUDUR'
    ],
})
if not test("S34: Teriparatid + endikasyon dışı + ön-koşul ibaresi yok → "
            "KONTROL_EDILEMEDI",
            "kontrol_edilemedi", r):
    basarisiz.append("S34")

# ── S35: Teriparatid + bifosfonat intolerans ibaresi + 75+ yaş → UYGUN ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORSTEO',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': 'X1',
    'hasta_yasi': 78,
    'cinsiyet': 'K',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'Sağlık kurulu raporu. Hasta bifosfonat intolerans nedeniyle '
        'teriparatid başlanmıştır. DXA 01.04.2025 lomber T-skor -3.1.'
    ],
})
if not test("S35: Teriparatid + bifosfonat intolerans ibaresi + 75+ → UYGUN",
            "uygun", r):
    basarisiz.append("S35")

# ── S36: Teriparatid + 'ciddi osteoporoz' lafzı (alternatif) + 75+ → UYGUN ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORTEO',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': 'X2',
    'hasta_yasi': 80,
    'cinsiyet': 'K',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'Sağlık kurulu raporu. Ciddi osteoporoz tanısı. DXA 02.05.2025 '
        'lomber T-skor -4.0 femur total T-skor -3.5.'
    ],
})
if not test("S36: Teriparatid + ciddi osteoporoz lafzı → UYGUN",
            "uygun", r):
    basarisiz.append("S36")

# ── S37: Teriparatid raporsuz → UYGUN_DEGIL (mevcut davranış korundu) ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORSTEO',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': '',
    'hasta_yasi': 70,
    'cinsiyet': 'K',
})
if not test("S37: Teriparatid raporsuz → UYGUN_DEGIL",
            "uygun_degil", r):
    basarisiz.append("S37")

# ── S38: Teriparatid + endikasyon dışı + Bakanlık onayı +
#         bifosfonat intolerans + 75+ yaş → UYGUN ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORSTEO',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': 'X3',
    'hasta_yasi': 76,
    'cinsiyet': 'K',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'Sağlık kurulu raporu. Bifosfonat yetersiz yanıt mevcut. '
        'Endikasyon dışı kullanım için Sağlık Bakanlığı onayı alınmıştır. '
        'DXA 03.04.2025 lomber T-skor -3.0.'
    ],
})
if not test("S38: Teriparatid + ED + Bakanlık onayı + bifosfonat yetersiz → "
            "UYGUN",
            "uygun", r):
    basarisiz.append("S38")

# ── S39: Teriparatid + endikasyon dışı (onay ibaresi yok) +
#         bifosfonat intolerans var → KONTROL_EDILEMEDI (ED onay belirsiz) ──
r = sk.kontrol_osteoporoz_biyolojik({
    'ilac_adi': 'FORSTEO',
    'etkin_madde': 'TERIPARATID',
    'rapor_kodu': 'X4',
    'hasta_yasi': 76,
    'cinsiyet': 'K',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': [
        'Sağlık kurulu raporu. Bifosfonat intolerans mevcut. Endikasyon '
        'dışı kullanım. DXA 03.04.2025 lomber T-skor -3.0.'
    ],
})
if not test("S39: Teriparatid + ED (onay ibaresi yok) + bifosfonat intolerans"
            " → KONTROL_EDILEMEDI",
            "kontrol_edilemedi", r):
    basarisiz.append("S39")

# ════════════════════════════════════════════════════════════════════════
# BOŞ METİN + RAPOR KODU AYRIMI (3 kontrol için)
# ════════════════════════════════════════════════════════════════════════

# ── S40: EMİNE ŞAN klonu — Bifosfonat boş metin + rapor kodu YOK
#         → UYGUN_DEGIL (raporsuz) ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '',
    'rapor_aciklamalari': [],
})
if not test("S40: Bifosfonat boş metin + raporsuz → UYGUN_DEGIL",
            "uygun_degil", r):
    basarisiz.append("S40")

# ── S41: Bifosfonat boş metin + rapor kodu VAR → KONTROL_EDILEMEDI
#         (rapor düzenlenmiş ama metni çekilememiş) ──
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX 70 MG',
    'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '12345',
    'rapor_aciklamalari': [],
})
if not test("S41: Bifosfonat boş metin + rapor kodu var → KONTROL_EDILEMEDI",
            "kontrol_edilemedi", r):
    basarisiz.append("S41")

# ── S42: YOAK boş metin + raporsuz → UYGUN_DEGIL ──
r = sk.kontrol_yoak({
    'ilac_adi': 'XARELTO 20 MG',
    'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '',
    'rapor_aciklamalari': [],
})
if not test("S42: YOAK boş metin + raporsuz → UYGUN_DEGIL",
            "uygun_degil", r):
    basarisiz.append("S42")

# ── S43: YOAK boş metin + rapor kodu var → KONTROL_EDILEMEDI ──
r = sk.kontrol_yoak({
    'ilac_adi': 'XARELTO 20 MG',
    'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '67890',
    'rapor_aciklamalari': [],
})
if not test("S43: YOAK boş metin + rapor kodu var → KONTROL_EDILEMEDI",
            "kontrol_edilemedi", r):
    basarisiz.append("S43")

# ── S44: İvabradin boş metin + raporsuz → UYGUN_DEGIL ──
r = sk.kontrol_ivabradin({
    'ilac_adi': 'PROCORALAN 7.5 MG',
    'etkin_madde': 'IVABRADIN',
    'rapor_kodu': '',
    'rapor_aciklamalari': [],
})
if not test("S44: İvabradin boş metin + raporsuz → UYGUN_DEGIL",
            "uygun_degil", r):
    basarisiz.append("S44")

# ── S45: İvabradin boş metin + rapor kodu var → KONTROL_EDILEMEDI ──
r = sk.kontrol_ivabradin({
    'ilac_adi': 'PROCORALAN 7.5 MG',
    'etkin_madde': 'IVABRADIN',
    'rapor_kodu': '11223',
    'rapor_aciklamalari': [],
})
if not test("S45: İvabradin boş metin + rapor kodu var → KONTROL_EDILEMEDI",
            "kontrol_edilemedi", r):
    basarisiz.append("S45")

# ════════════════════════════════════════════════════════════════════════
# Bug A+B+C — KMY referans tarihi / 75+ NA / Medula SK
# ════════════════════════════════════════════════════════════════════════

# ── S46: KAMİLE KAPLAN (3D0RLOO) — 81 yaş + raloksifen + rapor 06.01
#         + KMY 13.03.2024 + reçete 26.03.2025 + bifosfonat intolerans
#         → UYGUN (75+ KMY istisna + Medula SK kabul) ──
r = sk.kontrol_raloksifen({
    'ilac_adi': 'EVISTA 60 MG',
    'etkin_madde': 'RALOKSIFEN HCL',
    'rapor_kodu': '06.01',
    'hasta_yasi': 81,
    'recete_tarihi': '26/03/2025',
    'rapor_aciklamalari': [
        'HASTA BİFOSFONATLARI TOLERE EDEMİYOR.',
        'M81.09 - Postmenapozal osteoporoz, tanısı olan hasta',
        'HASTA YAŞI 81', 'LOMBER:L1-L4:-4.0',
        '13.03.2024 kemik ölçüm tarihi',
    ],
    'recete_teshisleri': ['M81.09'],
})
if not test("S46: KAMİLE KAPLAN 81 yaş + Medula 06.01 SK", "uygun", r):
    basarisiz.append("S46")

# Bug A izole: KMY reçete tarihine göre kıyaslanmalı (12 ay önce → VAR)
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX', 'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01', 'hasta_yasi': 70,
    'recete_tarihi': '26/03/2025',
    'doktor_uzmanligi': 'endokrinoloji',
    'rapor_aciklamalari': ['DEXA KMY tarihi: 13.03.2024 lomber T-skoru: -2.7'],
})
kmy_var = any(s.ad == 'KMY tarihi (son 2 yıl)' and s.durum == SartDurumu.VAR
              for s in r.sartlar)
ok = kmy_var and r.sonuc.value == 'uygun'
print(f"{'✓ PASS' if ok else '✗ FAIL'} | S47: Bug A — KMY reçete tarihine göre 12 ay önce → VAR")
if not ok: basarisiz.append("S47")

# Bug B izole: 75+ → KMY şartları NA
r = sk.kontrol_bifosfonat({
    'ilac_adi': 'FOSAMAX', 'etkin_madde': 'ALENDRONAT SODYUM',
    'rapor_kodu': '06.01', 'hasta_yasi': 78,
    'doktor_uzmanligi': 'iç hastalıkları',
    'rapor_aciklamalari': ['osteoporoz tedavisi'],
})
kmy_na = sum(1 for s in r.sartlar
             if s.ad.startswith('KMY') and s.durum == SartDurumu.NA)
ok = kmy_na >= 2
print(f"{'✓ PASS' if ok else '✗ FAIL'} | S48: Bug B — 75+ KMY şartları NA (sayı: {kmy_na})")
if not ok: basarisiz.append("S48")

# Bug C izole: rapor kodu 06.02 → SK lafzı olmasa bile VAR
r = sk.kontrol_kalsitonin({
    'ilac_adi': 'MIACALCIC NASAL', 'etkin_madde': 'KALSITONIN SOMON',
    'rapor_kodu': '06.02',
    'doktor_uzmanligi': 'fiziksel tıp ve rehabilitasyon',
    'rapor_aciklamalari': ['Ağrılı vertebra kompresyon kırığı'],
    'recete_teshisleri': ['M80.08'],
})
sk_var = any(s.ad == 'Sağlık kurulu raporu' and s.durum == SartDurumu.VAR
             and 'Medula' in s.neden for s in r.sartlar)
ok = sk_var and r.sonuc.value == 'uygun'
print(f"{'✓ PASS' if ok else '✗ FAIL'} | S49: Bug C — rapor 06.02 → SK Medula kabul")
if not ok: basarisiz.append("S49")


print("\n" + "="*70)
if basarisiz:
    print(f"❌ {len(basarisiz)} senaryo başarısız: {', '.join(basarisiz)}")
    sys.exit(1)
else:
    print("✅ Tüm senaryolar PASS")
