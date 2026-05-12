"""SUT 4.2.15.D E grubu PARAMETRİK kontrol testi (RaporDoktor heyetinden).

heyet_doktorlari ilac_sonuc'a yüklü iken atomların VAR/YOK/KE çıkışı.
D-1 5 dal (kard/iç/göğüs/KVC/nöro), D-2 ilk 24 ay 4 dal (NÖRO yok).
"""
import sys
import os
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol import sut_kontrolleri as sk

RAPOR_D1 = (
    # SAYIME HERGUL gerçek raporu (test_yoak_24ay_entegrasyon.py ile uyumlu)
    "PROSPEKTUSUNDE HIPERTANSIYONA SAHIP BELIRTILEN RISK FAKTORLERINDEN "
    "BIR YA DA DAHA FAZLASINA SAHIP NON-VALVULER ATRIYAL FIBRILASYONLU "
    "HASTADIR. HASTANIN EKOKARDIYOGRAFI ILE ROMATIZMAL KAPAK VE ORTA "
    "CIDDI MITRAL DARLIK KAPAK OLMADIGI VE MEKANIK PROTEZ KAPAK OLMAYAN "
    "NONVALVULER ATRIYAL FIBRILASYON HASTALIGI GOZLENMISTIR. EN AZ 2 AY "
    "SUREYLE VARFARIN KULLANMASINDAN SONRA EN AZ BIRER HAFTA ARA ILE "
    "YAPILAN SON 5 OLCUMUN EN AZ UCUNDE VARFARIN ILE HEDEFLENEN INR "
    "DEGERLERI 2-3 ARASINDA TUTULAMAMISTIR VE VARFARIN KESILEREK "
    "XARELTO 20 MG 1X1 KULLANILMASI UYGUNDUR."
)


def yap_d1(heyet, **ek):
    """D-1 AF senaryo: tıbbi şartlar TAMAM, heyet parametrik."""
    base = {
        "ilac_adi": "XARELTO 20 MG",
        "etkin_madde": "RIVAROKSABAN",
        "atc_kodu": "B01AF01",
        "rapor_kodu": "",
        "recete_teshisleri": ["I48 ATRIYAL FIBRILASYON"],
        "rapor_aciklamalari": [RAPOR_D1],
        "recete_aciklamalari": [],
        "mesaj_metni": "",
        "doktor_uzmanligi": "KARDIYOLOJI",
        "hasta_yasi": "78",
        "recete_dozu": "20MG 1x1",
        "recete_ilaclari": [],
        "kurum_adi": "",
        "tesis_kodu": "",
        "recete_tarihi": "05.05.2026",
        "hasta_yoak_ilk_recete_tarihi": None,
        "diger_raporlar_icd": [],
        "heyet_doktorlari": heyet,
    }
    base.update(ek)
    return base


def heyet(*tuples):
    """('Dr. Ahmet', 'Kardiyoloji') şeklinde tuple list → heyet doktor list."""
    return [{"ad": ad, "brans": br, "tckn": ""} for ad, br in tuples]


basari = 0
toplam = 0


def kontrol_atom(ad, beklenen_durum, atom_fn, *args):
    global basari, toplam
    toplam += 1
    durum, neden = atom_fn(*args)
    name = durum.name if hasattr(durum, 'name') else str(durum)
    bekn = (beklenen_durum.name if hasattr(beklenen_durum, 'name')
            else str(beklenen_durum))
    if durum == beklenen_durum:
        basari += 1
        print(f"[OK] {ad}: durum={name}")
    else:
        print(f"[FAIL] {ad}: beklenen={bekn}, gercek={name}")
        print(f"       neden: {neden}")


SD = sk.SartDurumu

print("=" * 70)
print("PARAMETRİK heyet testleri (D-1 5 dal listesi)")
print("=" * 70)

# T1 — D-1 toplam 3 uzman (3 farklı dal): VAR
kontrol_atom(
    "T1 D-1 toplam: kard+iç+göğüs (3 farklı) -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Göğüs Hastalıkları"))),
    sk._YOAK_HEYET_KEYS_D1)

# T2 — D-1 toplam 3 uzman (2 kard + 1 iç): VAR (SUT D-1'de farklı dal zorunlu DEĞİL!)
kontrol_atom(
    "T2 D-1 toplam: kard*2+iç (3 toplam, 2 farklı dal) -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "Kardiyoloji"),
                  ("Dr C", "İç Hastalıkları"))),
    sk._YOAK_HEYET_KEYS_D1)

# T2b — D-1 toplam 3 uzman (aynı dalda 3 kard): VAR
kontrol_atom(
    "T2b D-1 toplam: 3 kardiyolog (aynı dal) -> VAR (SUT D-1'de geçer)",
    SD.VAR,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "Kardiyoloji"),
                  ("Dr C", "Kardiyoloji"))),
    sk._YOAK_HEYET_KEYS_D1)

# T2c — D-1 toplam: sadece 2 uzman (kard+iç): YOK
kontrol_atom(
    "T2c D-1 toplam: 2 uzman (kard+iç) -> YOK",
    SD.YOK,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"))),
    sk._YOAK_HEYET_KEYS_D1)

# T3 — Heyet boş, RaporDoktor DB'de yok → KE
kontrol_atom(
    "T3 D-1 toplam: heyet boş -> KE",
    SD.KONTROL_EDILEMEDI,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1([]),
    sk._YOAK_HEYET_KEYS_D1)

# T4 — Aynı dalda 3: kard kard kard → VAR (D-2 alt-OR a)
kontrol_atom(
    "T4 D-2 ayni dal: kard*3 -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_ayni_dalda_3,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "Kardiyoloji"),
                  ("Dr C", "Kardiyoloji"))),
    sk._YOAK_HEYET_KEYS_D2_ILK24)

# T5 — Aynı dalda max 2 (kard*2 + iç) → YOK
kontrol_atom(
    "T5 D-2 ayni dal max 2: kard*2+iç -> YOK",
    SD.YOK,
    sk._yoak_atom_heyet_ayni_dalda_3,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "Kardiyoloji"),
                  ("Dr C", "İç Hastalıkları"))),
    sk._YOAK_HEYET_KEYS_D2_ILK24)

# T6 — D-2 farklı 3 dal: kard+iç+göğüs (nöro D-2'de YOK)
kontrol_atom(
    "T6 D-2 farklı 3 dal: kard+iç+göğüs -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_farkli_3_dal,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Göğüs Hastalıkları"))),
    sk._YOAK_HEYET_KEYS_D2_ILK24)

# T6b — D-2 heyette nöro var ama D-2 listesinde nöro yok → sayılmaz
kontrol_atom(
    "T6b D-2 farklı: kard+iç+nöro (nöro sayılmaz D-2'de) -> YOK (2 farklı)",
    SD.YOK,
    sk._yoak_atom_heyet_farkli_3_dal,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Nöroloji"))),
    sk._YOAK_HEYET_KEYS_D2_ILK24)

# T7 — D-1 toplam 3 (nöro sayılır D-1'de): VAR
kontrol_atom(
    "T7 D-1 toplam: kard+iç+nöro (D-1'de 3 yetkili uzman) -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_3_uzman_toplam,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Nöroloji"))),
    sk._YOAK_HEYET_KEYS_D1)

# T8 — SK var (heyet ≥3)
kontrol_atom(
    "T8 SK var: heyet 3 doktor -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_sk_var,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Göğüs Hastalıkları"))),
    "")

# T9 — SK yok: heyet 2 doktor + rapor_kodu boş
kontrol_atom(
    "T9 SK yok: heyet 2 doktor + rapor_kodu boş -> YOK",
    SD.YOK,
    sk._yoak_atom_heyet_sk_var,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"))),
    "")

# T10 — Heyet 2 ama rapor_kodu=04.03 (Medula otorite) → VAR
kontrol_atom(
    "T10 SK fallback: heyet 2 + rapor_kodu=04.03 -> VAR",
    SD.VAR,
    sk._yoak_atom_heyet_sk_var,
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"))),
    "04.03")

# T11 — D-1 entegrasyon: heyet 3 farklı, doktor uzman, 24 ay tamam → UYGUN
print()
print("=" * 70)
print("D-1 entegrasyon (parametrik heyet ile)")
print("=" * 70)


def kontrol_full(ad, beklenen, ilac):
    global basari, toplam
    toplam += 1
    rapor = sk.kontrol_yoak(ilac)
    sonuc = rapor.sonuc.name.lower()
    if sonuc == beklenen.lower():
        basari += 1
        print(f"[OK] {ad}: {sonuc}")
    else:
        print(f"[FAIL] {ad}: beklenen={beklenen}, gercek={sonuc}")
        print(f"       mesaj: {rapor.mesaj[:200]}")


# T11: tıbbi şartlar TAMAM + heyet 3 farklı + uzman doktor → UYGUN
kontrol_full(
    "T11 D-1 entegrasyon UYGUN",
    "uygun",
    yap_d1(heyet(("Dr A", "Kardiyoloji"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "Göğüs Hastalıkları")),
            hasta_yoak_ilk_recete_tarihi="2023-06-15"))

# T12: heyet 3 uzman ama HEPSI iç hast (kard/nöro YOK) + 24 ay YOK
# → E2 (kard veya nöro zorunlu) YOK → E YOK → F YOK → UYGUN_DEGIL
kontrol_full(
    "T12 D-1 heyet 3 iç hast (kard/nöro YOK) + 24ay YOK -> UYGUN_DEGIL",
    "uygun_degil",
    yap_d1(heyet(("Dr A", "İç Hastalıkları"),
                  ("Dr B", "İç Hastalıkları"),
                  ("Dr C", "İç Hastalıkları")),
            hasta_yoak_ilk_recete_tarihi="2026-02-01"))  # 3 ay → YOK

# T13: heyet boş + rapor_kodu boş + 24 ay YOK + uzman → KE
# (E KE çünkü heyet DB'de yok, F YOK çünkü 24 ay tamam değil →
#  üst-OR (E ∨ F) = KE ∨ YOK = KE → genel KONTROL_EDILEMEDI/ŞÜPHELİ)
kontrol_full(
    "T13 D-1 heyet boş + 24ay YOK + uzman -> ŞÜPHELİ (E KE)",
    "kontrol_edilemedi",
    yap_d1([], hasta_yoak_ilk_recete_tarihi="2026-02-01"))

# T14: heyet boş + rapor_kodu=04.03 (Medula otorite) → UYGUN
kontrol_full(
    "T14 D-1 heyet boş + rapor_kodu=04.03 -> UYGUN (Medula otorite)",
    "uygun",
    yap_d1([], rapor_kodu="04.03",
            hasta_yoak_ilk_recete_tarihi="2023-06-15"))

print()
print("=" * 70)
print(f"Sonuc: {basari}/{toplam} test gecti")
print("=" * 70)
sys.exit(0 if basari == toplam else 1)
