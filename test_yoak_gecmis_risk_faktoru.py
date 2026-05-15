"""SUT 4.2.15.D-1 — Risk faktörlerinin geçmiş raporlardan taranması.

Kullanıcı isteği (2026-05-13): inme/TIA/DM/HT şartları aktif raporda yoksa
hastanın geçmiş raporlarındaki ICD'lere de bakılsın. NYHA için aktif rapora
ek olarak geçmiş I50 (kalp yetmezliği) ICD'si varsa KONTROL_EDILEMEDI
(NYHA sınıfı manuel doğrulanmalı).

Kapsanan atomlar:
  - _yoak_atom_inme  (I63-66)
  - _yoak_atom_tia   (G45-46)
  - _yoak_atom_dm    (E10-14)
  - _yoak_atom_ht    (I10-15)
  - _yoak_atom_gecmis_ky_var (I50) — NYHA fallback
"""
import sys
import os
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol import sut_kontrolleri as sk


basari = 0
toplam = 0


def kontrol(ad, fn_result, beklenen_var, beklenen_kaynak_baslangic=None):
    """fn_result: (var, kaynak) tuple. beklenen_kaynak_baslangic: kaynak'ın
    başlaması gereken prefix ('aktif_metin', 'aktif_teshis', 'gecmis_icd:')
    veya None (kaynak kontrol etme)."""
    global basari, toplam
    toplam += 1
    var, kaynak = fn_result
    sebep = ''
    ok = (var == beklenen_var)
    if ok and beklenen_kaynak_baslangic is not None:
        ok = kaynak.startswith(beklenen_kaynak_baslangic)
        if not ok:
            sebep = f' (kaynak beklenen={beklenen_kaynak_baslangic!r} '\
                    f'gercek={kaynak!r})'
    if ok:
        basari += 1
        print(f"[OK] {ad}: var={var}, kaynak={kaynak}")
    else:
        print(f"[FAIL] {ad}: beklenen_var={beklenen_var}, "
              f"gercek_var={var}, kaynak={kaynak}{sebep}")


print("=" * 70)
print("SUT 4.2.15.D-1 — Geçmiş raporlardan risk faktörü taraması")
print("=" * 70)

# ─── HT (hipertansiyon) ─────────────────────────────────────────────────
print("\n--- HT testleri ---")
kontrol("HT yok-yok",
        sk._yoak_atom_ht("", "", []),
        beklenen_var=False)

kontrol("HT aktif metinde",
        sk._yoak_atom_ht("hipertansiyon mevcuttur", "", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_metin")

kontrol("HT aktif teşhiste",
        sk._yoak_atom_ht("", "I10 ESANSIYEL HIPERTANSIYON", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_teshis")

kontrol("HT geçmiş raporda",
        sk._yoak_atom_ht("", "", ["I10 ESANSIYEL HIPERTANSIYON"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

kontrol("HT her ikisinde (öncelik aktif)",
        sk._yoak_atom_ht("hipertansiyon var",
                          "I10 ESANSIYEL HIPERTANSIYON",
                          ["I10 ESANSIYEL HIPERTANSIYON"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_metin")

kontrol("HT geçmiş listede I11 (kalp HT)",
        sk._yoak_atom_ht("", "", ["I11.9 HIPERTANSIF KALP HASTALIGI"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

kontrol("HT geçmişte alakasız ICD",
        sk._yoak_atom_ht("", "", ["E11 TIP 2 DM", "I25 KORONER"]),
        beklenen_var=False)

# ─── DM (diabetes mellitus) ──────────────────────────────────────────────
print("\n--- DM testleri ---")
kontrol("DM yok-yok",
        sk._yoak_atom_dm("", "", []),
        beklenen_var=False)

kontrol("DM aktif metinde",
        sk._yoak_atom_dm("diyabet hastasi", "", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_metin")

kontrol("DM aktif teşhiste",
        sk._yoak_atom_dm("", "E11 TIP 2 DM", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_teshis")

kontrol("DM geçmiş raporda E11",
        sk._yoak_atom_dm("", "", ["E11.9 TIP 2 DM"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

kontrol("DM geçmiş raporda E14",
        sk._yoak_atom_dm("", "", ["E14 DIABETES"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

# ─── İnme ────────────────────────────────────────────────────────────────
print("\n--- İnme testleri ---")
kontrol("inme yok-yok",
        sk._yoak_atom_inme("", "", []),
        beklenen_var=False)

kontrol("inme aktif metinde",
        sk._yoak_atom_inme("hasta serebrovaskuler olay gecirmis", "", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_metin")

kontrol("inme geçmiş raporda I63",
        sk._yoak_atom_inme("", "", ["I63.0 ISKEMIK INME"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

kontrol("inme geçmiş raporda I65",
        sk._yoak_atom_inme("", "", ["I65 KAROTID ARTER OKLUZYONU"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

# ─── TIA ─────────────────────────────────────────────────────────────────
print("\n--- TIA testleri ---")
kontrol("TIA yok-yok",
        sk._yoak_atom_tia("", "", []),
        beklenen_var=False)

kontrol("TIA aktif metinde",
        sk._yoak_atom_tia("gecici iskemik atak oykusu", "", []),
        beklenen_var=True,
        beklenen_kaynak_baslangic="aktif_metin")

kontrol("TIA geçmiş raporda G45",
        sk._yoak_atom_tia("", "", ["G45.9 GECICI ISKEMIK ATAK"]),
        beklenen_var=True,
        beklenen_kaynak_baslangic="gecmis_icd:")

# ─── NYHA / Geçmiş KY (I50) ─────────────────────────────────────────────
print("\n--- Geçmiş KY (I50) testleri ---")
ky_var, ky_satir = sk._yoak_atom_gecmis_ky_var([])
toplam += 1
if not ky_var:
    basari += 1
    print(f"[OK] KY yok liste: var={ky_var}")
else:
    print(f"[FAIL] KY yok liste: var={ky_var}")

ky_var, ky_satir = sk._yoak_atom_gecmis_ky_var(
    ["I50.9 KALP YETMEZLIGI"])
toplam += 1
if ky_var and 'I50' in ky_satir:
    basari += 1
    print(f"[OK] KY I50 var: satir={ky_satir}")
else:
    print(f"[FAIL] KY I50 var: var={ky_var}, satir={ky_satir}")

ky_var, ky_satir = sk._yoak_atom_gecmis_ky_var(
    ["E11 TIP 2 DM", "I25 KORONER"])
toplam += 1
if not ky_var:
    basari += 1
    print(f"[OK] KY listede alakasız ICD: var={ky_var}")
else:
    print(f"[FAIL] KY listede alakasız ICD: var={ky_var}")

# ─── Entegrasyon: kontrol_yoak çağrısı + NYHA fallback ──────────────────
print("\n--- Entegrasyon: NYHA fallback senaryosu ---")
RAPOR_AF = (
    "PROSPEKTUSUNDE BELIRTILEN RISK FAKTORLERINDEN BIR YA DA DAHA FAZLASINA "
    "SAHIP NON-VALVULER ATRIYAL FIBRILASYONLU HASTADIR. ROMATIZMAL MITRAL "
    "KAPAK CIDDI MITRAL DARLIK MEKANIK PROTEZ KAPAK OLMAYAN. EN AZ 2 AY "
    "SUREYLE VARFARIN KULLANMASINDAN SONRA EN AZ BIRER HAFTA ARA ILE "
    "YAPILAN SON 5 OLCUMUN EN AZ UCUNDE INR 2-3 ARASINDA TUTULAMAMISTIR "
    "VARFARIN KESILEREK XARELTO 20 MG 1X1 UYGUNDUR."
)

ilac_sonuc_ky = {
    "ilac_adi": "XARELTO 20 MG",
    "etkin_madde": "RIVAROKSABAN",
    "atc_kodu": "B01AF01",
    "rapor_kodu": "04.03",
    "recete_teshisleri": ["I48 ATRIYAL FIBRILASYON"],
    "rapor_aciklamalari": [RAPOR_AF],
    "recete_aciklamalari": [],
    "mesaj_metni": "",
    "doktor_uzmanligi": "KARDIYOLOJI",
    "hasta_yasi": "60",
    "recete_dozu": "20 MG 1X1",
    "recete_ilaclari": [],
    "kurum_adi": "DEVLET HASTANESI",
    "tesis_kodu": "",
    "recete_tarihi": "05.05.2026",
    "hasta_yoak_ilk_recete_tarihi": None,
    "diger_raporlar_icd": [],
    "diger_raporlar_icd_tum_zamanlar": [
        "I50.9 KALP YETMEZLIGI",  # → NYHA için KE fallback tetiklemeli
    ],
}
rapor = sk.kontrol_yoak(ilac_sonuc_ky)
nyha_sart = next((p for p in (rapor.sartlar or [])
                   if 'NYHA' in p.ad), None)
toplam += 1
if (nyha_sart and
        nyha_sart.durum == sk.SartDurumu.KONTROL_EDILEMEDI and
        'manuel' in (nyha_sart.neden or '').lower()):
    basari += 1
    print(f"[OK] NYHA KE fallback tetikledi: {nyha_sart.neden[:80]}")
else:
    n = nyha_sart.ad if nyha_sart else '<yok>'
    d = nyha_sart.durum.name if nyha_sart else '<yok>'
    nd = (nyha_sart.neden if nyha_sart else '<yok>')[:100]
    print(f"[FAIL] NYHA KE fallback: ad={n}, durum={d}, neden={nd}")

# HT geçmiş raporda → risk faktörü sağlanır mı?
print("\n--- Entegrasyon: HT geçmiş raporda → risk fakt. VAR ---")
ilac_sonuc_ht = dict(ilac_sonuc_ky)
ilac_sonuc_ht["diger_raporlar_icd_tum_zamanlar"] = [
    "I10 ESANSIYEL HIPERTANSIYON"]
ilac_sonuc_ht["hasta_yasi"] = "55"  # ≥75 değil
rapor2 = sk.kontrol_yoak(ilac_sonuc_ht)
ht_sart = next((p for p in (rapor2.sartlar or [])
                 if p.ad == 'Hipertansiyon'), None)
toplam += 1
if (ht_sart and ht_sart.durum == sk.SartDurumu.VAR and
        'Geçmiş' in (ht_sart.neden or '')):
    basari += 1
    print(f"[OK] HT geçmişten tespit: {ht_sart.neden[:100]}")
else:
    d = ht_sart.durum.name if ht_sart else '<yok>'
    nd = (ht_sart.neden if ht_sart else '<yok>')[:100]
    print(f"[FAIL] HT geçmişten: durum={d}, neden={nd}")

# Geriye uyumluluk: diger_raporlar_icd_tum_zamanlar yoksa
# diger_raporlar_icd fallback çalışmalı
print("\n--- Geriye uyumluluk: sadece diger_raporlar_icd ile ---")
ilac_sonuc_eski = dict(ilac_sonuc_ht)
ilac_sonuc_eski.pop("diger_raporlar_icd_tum_zamanlar", None)
ilac_sonuc_eski["diger_raporlar_icd"] = ["I10 ESANSIYEL HIPERTANSIYON"]
rapor3 = sk.kontrol_yoak(ilac_sonuc_eski)
ht_sart3 = next((p for p in (rapor3.sartlar or [])
                  if p.ad == 'Hipertansiyon'), None)
toplam += 1
if (ht_sart3 and ht_sart3.durum == sk.SartDurumu.VAR):
    basari += 1
    print(f"[OK] Fallback diger_raporlar_icd çalıştı: "
          f"{ht_sart3.neden[:80]}")
else:
    d = ht_sart3.durum.name if ht_sart3 else '<yok>'
    print(f"[FAIL] Fallback: durum={d}")

# Hiçbir kaynakta yok → YOK
print("\n--- Tüm kaynaklarda yok ---")
ilac_sonuc_yok = dict(ilac_sonuc_ky)
ilac_sonuc_yok["diger_raporlar_icd_tum_zamanlar"] = []
ilac_sonuc_yok["diger_raporlar_icd"] = []
ilac_sonuc_yok["hasta_yasi"] = "55"
rapor4 = sk.kontrol_yoak(ilac_sonuc_yok)
nyha_sart4 = next((p for p in (rapor4.sartlar or [])
                    if 'NYHA' in p.ad), None)
toplam += 1
if nyha_sart4 and nyha_sart4.durum == sk.SartDurumu.YOK:
    basari += 1
    print(f"[OK] NYHA tümünde yok → YOK: {nyha_sart4.neden[:80]}")
else:
    d = nyha_sart4.durum.name if nyha_sart4 else '<yok>'
    print(f"[FAIL] NYHA tümünde yok: durum={d}")

print("\n" + "=" * 70)
print(f"SONUC: {basari}/{toplam} basarili")
print("=" * 70)
sys.exit(0 if basari == toplam else 1)
