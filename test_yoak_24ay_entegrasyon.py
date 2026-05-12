"""SUT 4.2.15.D-1 entegrasyon testi — 24 ay sonrasi aile hekimi reçetesi.

Pilot: SAYIME HERGUL benzeri senaryo:
- D-1 AF tum sartlari TAMAM (risk fakt., non-valvuler, mitral/mekanik yok,
  varfarin 2 ay, INR 5/3 tutulamadi, varfarin kesildi)
- Doktor: AILE HEKIMI
- Hasta YOAK gecmisi: 24 ay+ once -> F yolundan UYGUN beklenir
- Hasta YOAK gecmisi: <24 ay -> SK raporu yok ise UYGUN_DEGIL beklenir
"""
import sys
import os
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol import sut_kontrolleri as sk

RAPOR_TAM = (
    "PROSPEKTUSUNDE HIPERTANSIYONA SAHIP BELIRTILEN RISK FAKTORLERINDEN "
    "BIR YA DA DAHA FAZLASINA SAHIP NON-VALVULER ATRIYAL FIBRILASYONLU "
    "HASTADIR. HASTANIN EKOKARDIYOGRAFI ILE ROMATIZMAL KAPAK VE ORTA "
    "CIDDI MITRAL DARLIK KAPAK OLMADIGI VE MEKANIK PROTEZ KAPAK OLMAYAN "
    "NONVALVULER ATRIYAL FIBRILASYON HASTALIGI GOZLENMISTIR. KARDIYOLOJI "
    "UZMANI DEGERLENDIRMESI ILE EN AZ 2 AY SUREYLE VARFARIN "
    "KULLANMASINDAN SONRA EN AZ BIRER HAFTA ARA ILE YAPILAN SON 5 "
    "OLCUMUN EN AZ UCUNDE VARFARIN ILE HEDEFLENEN INR DEGERLERI 2-3 "
    "ARASINDA TUTULAMAMISTIR VE VARFARIN KESILEREK XARELTO "
    "(RIVAROKSABAN) 15-20 MG 1X1 KULLANILMASI UYGUNDUR."
)


def yap(**ek):
    base = {
        "ilac_adi": "XARELTO 20 MG",
        "etkin_madde": "RIVAROKSABAN",
        "atc_kodu": "B01AF01",
        "rapor_kodu": "",  # SK YOK (aile hekimi senaryosu)
        "recete_teshisleri": ["I48 ATRIYAL FIBRILASYON"],
        "rapor_aciklamalari": [RAPOR_TAM],
        "recete_aciklamalari": [],
        "mesaj_metni": "",
        "doktor_uzmanligi": "AILE HEKIMI",
        "hasta_yasi": "78",
        "recete_dozu": "20 MG 1X1",
        "recete_ilaclari": [],
        "kurum_adi": "AILE SAGLIGI MERKEZI",
        "tesis_kodu": "",
        "recete_tarihi": "05.05.2026",
        "hasta_yoak_ilk_recete_tarihi": None,
        "diger_raporlar_icd": [],
    }
    base.update(ek)
    return base


basari = 0
toplam = 0


def kontrol(ad, beklenen_sonuc, ilac_sonuc):
    global basari, toplam
    toplam += 1
    try:
        rapor = sk.kontrol_yoak(ilac_sonuc)
        sonuc = rapor.sonuc.name.lower()
        if sonuc == beklenen_sonuc.lower():
            basari += 1
            print(f"[OK] {ad}: sonuc={sonuc}")
        else:
            print(f"[FAIL] {ad}: beklenen={beklenen_sonuc}, gercek={sonuc}")
            print(f"       mesaj: {rapor.mesaj[:200]}")
    except Exception as e:
        print(f"[ERROR] {ad}: {e}")


print("=" * 70)
print("SUT 4.2.15.D-1 entegrasyon — 24 ay sonrasi aile hekimi senaryosu")
print("=" * 70)

# Senaryo A: Hasta YOAK gecmisi 24 ay+ once, aile hekimi reçetesi
# Beklenen: UYGUN (F yolu acik: 24 ay TAMAM + uzman ibare + aile hekimi)
kontrol(
    "A1 ilk=2023-06-15 (34 ay), aile hekimi, SK yok",
    "uygun",
    yap(hasta_yoak_ilk_recete_tarihi="2023-06-15"))

# Senaryo B: Hasta yeni baslama (3 ay), aile hekimi reçetesi, SK yok
# Beklenen: UYGUN_DEGIL (F1 YOK + SK yok -> her iki yol da kapali)
kontrol(
    "B1 ilk=2026-02-01 (3 ay), aile hekimi, SK yok",
    "uygun_degil",
    yap(hasta_yoak_ilk_recete_tarihi="2026-02-01"))

# Senaryo C: Hasta YOAK gecmisi yok (DB'de kayit yok)
# Beklenen: SUPHELI (F1 KE -> 24 ay durumu belirsiz, manuel dogrulama)
kontrol(
    "C1 hasta_yoak_ilk=None, aile hekimi, SK yok",
    "kontrol_edilemedi",
    yap(hasta_yoak_ilk_recete_tarihi=None))

# Senaryo D: 24 ay TAMAM ama doktor branşı yetkisiz (ne aile ne uzman)
kontrol(
    "D1 ilk=2023-06-15 (34 ay), DERMATOLOJI doktor, SK yok",
    "uygun_degil",
    yap(hasta_yoak_ilk_recete_tarihi="2023-06-15",
        doktor_uzmanligi="DERMATOLOJI",
        kurum_adi="", tesis_kodu=""))

# Senaryo E: Hasta yeni (3 ay) ama SK raporu var, uzman branş
# Beklenen: UYGUN (E yolu acik: SK + uzman branş + tum tıbbı sartlar)
kontrol(
    "E1 ilk=2026-02-01, KARDIYOLOJI doktor, SK rapor_kodu=04.03",
    "uygun",
    yap(hasta_yoak_ilk_recete_tarihi="2026-02-01",
        rapor_kodu="04.03",
        doktor_uzmanligi="KARDIYOLOJI",
        kurum_adi="", tesis_kodu=""))

print()
print("=" * 70)
print(f"Sonuc: {basari}/{toplam} entegrasyon testi gecti")
print("=" * 70)
sys.exit(0 if basari == toplam else 1)
