"""
SUT (Saglik Uygulama Tebligi) Ilac Veritabani - SQLite Surumu

Turkiye'de satilan ilaclar icin 4 SUT kategorisi:
  1. KOMBINE_ANTIHIPERTANSIF (SUT 4.2.12) - Kombine antihipertansif ilaclar
  2. DIYABET_DPP4_SGLT2 (SUT 4.2.38) - DPP-4, SGLT-2, GLP-1 diyabet ilaclari
  3. KLOPIDOGREL (SUT 4.2.15) - Antiplatelet ilaclar
  4. STATIN (SUT 4.2.28) - Lipid dusurucu ilaclar

Kaynaklar:
- ilacabak.com (etkin madde bazli ilac listeleri)
- ilacrehberi.com
- ilacdata.com
- ilactr.com
- SGK Saglik Uygulama Tebligi (SUT) resmi metni

Son guncelleme: 2026-03-06

Kullanim:
    import sut_ilac_db
    # Veritabani otomatik olusturulur

    # Kategori bul
    sonuc = sut_ilac_db.sut_kategori_bul(ilac_adi="EXFORGE")
    sonuc = sut_ilac_db.sut_kategori_bul(etkin_madde="ATORVASTATIN")

    # Kategorideki ilaclari listele
    ilaclar = sut_ilac_db.sut_ilaclari_listele("KOMBINE_ANTIHIPERTANSIF")

    # Kontrol ibaresi al
    ibare = sut_ilac_db.sut_kontrol_ibaresi_al("STATIN")
"""

import sqlite3
import os

# Veritabani dosya yolu
_DB_DIZIN = os.path.dirname(os.path.abspath(__file__))
_DB_DOSYA = os.path.join(_DB_DIZIN, "sut_ilaclar.db")


# =============================================================================
# KATEGORI TANIMLARI
# =============================================================================

_KATEGORILER = [
    {
        "kategori_kodu": "KOMBINE_ANTIHIPERTANSIF",
        "kategori_adi": "Kombine Antihipertansif Ilaclar",
        "sut_maddesi": "4.2.12",
        "aranan_ibare": "monoterapi ile hasta kan basincinin yeteri kadar kontrol altina alinamadigi",
        "kontrol_metni": (
            "Anjiyotensin reseptor blokerlerinin diger antihipertansifler ile "
            "kombinasyonlarinin kullaniminda; hastanin monoterapi ile kan basincinin "
            "yeterli oranda kontrol altina alinamadiginin raporda belirtilmesi gerekmektedir."
        ),
        "aciklama": (
            "ARB + Kalsiyum Kanal Blokoru, ARB + Diuretik, ACE Inhibitoru + Diuretik, "
            "ACE Inhibitoru + KKB ve Uclu (ARB+KKB+HCT) kombinasyonlari. "
            "15.10.2016 tarihinden itibaren tum ARB kombine ilac raporlarinda "
            "'monoterapi ile kan basincinin yeterli oranda kontrol altina alinamadigi' "
            "ifadesinin yer almasi zorunludur."
        ),
    },
    {
        "kategori_kodu": "DIYABET_DPP4_SGLT2",
        "kategori_adi": "DPP-4 Inhibitorleri, SGLT-2 Inhibitorleri ve GLP-1 Agonistleri",
        "sut_maddesi": "4.2.38",
        "aranan_ibare": "metformin ve sulfonilure yeterli doz glisemik kontrol saglanamadi",
        "kontrol_metni": (
            "DPP-4 inhibitoru, SGLT-2 inhibitoru ve GLP-1 agonisti ilaclar; "
            "metformin ve/veya sulfonilürelerin maksimum tolere edilebilen dozlarinda "
            "yeterli glisemik kontrol saglanamayan hastalarda, endokrinoloji uzman "
            "hekimlerince duzenlenen uzman hekim raporuna dayanilarak tum hekimlerce "
            "recete edilebilir."
        ),
        "aciklama": (
            "DPP-4 Inhibitorleri (Sitagliptin, Vildagliptin, Linagliptin, Saksagliptin, Alogliptin), "
            "SGLT-2 Inhibitorleri (Dapagliflozin, Empagliflozin), "
            "GLP-1 Agonistleri (Liraglutid, Semaglutid, Dulaglutid, Eksenatid) "
            "ve bunlarin Metformin ile kombinasyonlari."
        ),
    },
    {
        "kategori_kodu": "KLOPIDOGREL",
        "kategori_adi": "Antiplatelet (Antiagregan) Ilaclar",
        "sut_maddesi": "4.2.15",
        "aranan_ibare": "koroner stent anjiografi akut koroner sendrom",
        "kontrol_metni": (
            "Klopidogrel: Koroner arter stenti uygulanan hastalarda rapor aranmaksizin, "
            "AKS'de kardiyoloji/kalp damar cerrahisi/ic hastaliklari/acil tip uzmani "
            "tarafindan rapor aranmaksizin baslanabilir. Taburcu sonrasi 12 ay sureli "
            "uzman hekim raporu gereklidir. "
            "Prasugrel: AKS hastalarinda 1 yil sureli saglik kurulu raporu. "
            "Tikagrelor: NSTEMI/STEMI hastalarinda 1 yil sureli saglik kurulu raporu."
        ),
        "aciklama": (
            "Klopidogrel (4.2.15.A), Prasugrel (4.2.15.C), Tikagrelor (4.2.15.E). "
            "Koroner stent, AKS (akut koroner sendrom), belgelenmis koroner hastalik, "
            "inme gibi endikasyonlarda kullanilir. Anjiografi tarihi/raporu gerekli olabilir."
        ),
    },
    {
        "kategori_kodu": "STATIN",
        "kategori_adi": "Lipid Dusurucu Ilaclar (Statinler ve Kombinasyonlari)",
        "sut_maddesi": "4.2.28",
        "aranan_ibare": "LDL kolesterol lipid statin",
        "kontrol_metni": (
            "Statinler uzman hekim raporuna dayanilarak; "
            "LDL>190 (ek risk faktoru gerekmez), LDL>160 (2 ek risk faktoru), "
            "LDL>130 (3 ek risk faktoru), LDL>70 (DM, AKS, MI, inme, KAH, PAH, AAA, "
            "karotid arter hastaligi) durumlarinda baslanabilir. "
            "Rosuvastatin 20mg+, Atorvastatin/Simvastatin 40mg+, Fluvastatin 80mg+ "
            "icin kardiyoloji/KDC/endokrinoloji/geriatri uzman raporu gerekir. "
            "Ezetimib: En az 6 ay statin tedavisine ragmen LDL>100 kalanlarda eklenir."
        ),
        "aciklama": (
            "Statinler (4.2.28.A): Atorvastatin, Rosuvastatin, Simvastatin, Pravastatin, "
            "Fluvastatin, Pitavastatin. "
            "Ezetimib (4.2.28.C): Tek basina veya statin kombinasyonlari. "
            "Yeni baslama icin 6 ay icerisinde en az 1 hafta arayla 2 lipid olcumu gerekli."
        ),
    },
]


# =============================================================================
# ILAC VERILERI
# =============================================================================

# Format: (etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi, aranan_ibare, rapor_kontrol_metni, notlar)

_KOMBINE_ANTIHIPERTANSIF = [
    # =========================================================================
    # ARB + KKB: VALSARTAN + AMLODIPIN
    # =========================================================================
    ("VALSARTAN + AMLODIPIN", "EXFORGE", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", "Monoterapi ile kan basinci yeterli kontrol altina alinamadigi raporda belirtilmeli", "ARB + KKB, Novartis"),
    ("VALSARTAN + AMLODIPIN", "CARDOFIX", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Sanovel"),
    ("VALSARTAN + AMLODIPIN", "COMBISAR", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),
    ("VALSARTAN + AMLODIPIN", "VALCODIN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),
    ("VALSARTAN + AMLODIPIN", "VALDIPIN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),

    # ARB + KKB + HCT: VALSARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik, Novartis"),
    ("VALSARTAN + AMLODIPIN + HCT", "CARDOFIX PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik, Sanovel"),

    # =========================================================================
    # ARB + KKB: OLMESARTAN + AMLODIPIN
    # =========================================================================
    ("OLMESARTAN + AMLODIPIN", "SEVIKAR", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Daiichi Sankyo"),
    ("OLMESARTAN + AMLODIPIN", "EXCALIBA", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Menarini"),
    ("OLMESARTAN + AMLODIPIN", "OLMECOMB", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Menarini"),

    # ARB + KKB + HCT: OLMESARTAN + AMLODIPIN + HCT (Uclu)
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),
    ("OLMESARTAN + AMLODIPIN + HCT", "OLMECOMB PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),

    # =========================================================================
    # ARB + KKB: TELMISARTAN + AMLODIPIN
    # =========================================================================
    ("TELMISARTAN + AMLODIPIN", "TELMODIP", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Neutec"),
    ("TELMISARTAN + AMLODIPIN", "TWYNSTA", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Boehringer Ingelheim"),

    # ARB + KKB + HCT: TELMISARTAN + AMLODIPIN + HCT (Uclu)
    ("TELMISARTAN + AMLODIPIN + HCT", "TELMODIP PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik, Celtis"),

    # =========================================================================
    # ARB + KKB: IRBESARTAN + AMLODIPIN
    # =========================================================================
    ("IRBESARTAN + AMLODIPIN", "KARVEA DUO", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB, Sanofi"),
    ("IRBESARTAN + AMLODIPIN", "IRDAPIN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),

    # ARB + KKB + HCT: IRBESARTAN + AMLODIPIN + HCT (Uclu)
    ("IRBESARTAN + AMLODIPIN + HCT", "IRDAPIN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),

    # =========================================================================
    # ARB + KKB: KANDESARTAN + AMLODIPIN
    # =========================================================================
    ("KANDESARTAN + AMLODIPIN", "CANLOX", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),
    ("KANDESARTAN + AMLODIPIN", "RANTAZIN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),
    ("KANDESARTAN + AMLODIPIN", "TANSIFA", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + KKB"),

    # ARB + KKB + HCT: KANDESARTAN + AMLODIPIN + HCT (Uclu)
    ("KANDESARTAN + AMLODIPIN + HCT", "CANLOX PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),
    ("KANDESARTAN + AMLODIPIN + HCT", "RANTAZIN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),
    ("KANDESARTAN + AMLODIPIN + HCT", "TANSIFA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ARB + KKB + Diuretik"),

    # =========================================================================
    # ARB + DIURETIK: VALSARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("VALSARTAN + HCT", "CO-DIOVAN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Novartis"),
    ("VALSARTAN + HCT", "CARDOPAN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Sanovel"),
    ("VALSARTAN + HCT", "VALCOR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Ilko"),

    # =========================================================================
    # ARB + DIURETIK: IRBESARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("IRBESARTAN + HCT", "KARVEZIDE", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Sanofi"),
    ("IRBESARTAN + HCT", "ARBESTA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("IRBESARTAN + HCT", "CO-IRDA", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("IRBESARTAN + HCT", "IRBECOR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("IRBESARTAN + HCT", "REBEVEA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("IRBESARTAN + HCT", "ROTAZAR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),

    # =========================================================================
    # ARB + DIURETIK: LOSARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("LOSARTAN + HCT", "HYZAAR", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Organon"),
    ("LOSARTAN + HCT", "EKLIPS PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "EKLIPS FORT", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "HYSARTAR", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "LOSAPRES PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "LOTANS PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Berko"),
    ("LOSARTAN + HCT", "LOXIBIN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "SARILEN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("LOSARTAN + HCT", "SARVASTAN", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),

    # =========================================================================
    # ARB + DIURETIK: KANDESARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("KANDESARTAN + HCT", "ATACAND PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, AstraZeneca"),
    ("KANDESARTAN + HCT", "AYRA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("KANDESARTAN + HCT", "CANDECARD PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Sandoz"),
    ("KANDESARTAN + HCT", "CANDEXIL PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Deva"),
    ("KANDESARTAN + HCT", "CANSAR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Sensys"),
    ("KANDESARTAN + HCT", "CANTAB PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Nobel"),
    ("KANDESARTAN + HCT", "CO-UCAND", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("KANDESARTAN + HCT", "LARMONI PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),
    ("KANDESARTAN + HCT", "TENSART PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik"),

    # =========================================================================
    # ARB + DIURETIK: TELMISARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("TELMISARTAN + HCT", "MICARDIS PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Boehringer Ingelheim"),
    ("TELMISARTAN + HCT", "MICATOR PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Humanis"),
    ("TELMISARTAN + HCT", "PRESCAN PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Ilko"),
    ("TELMISARTAN + HCT", "TELVIS PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Neutec"),
    ("TELMISARTAN + HCT", "TENVIA PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Celtis"),

    # =========================================================================
    # ARB + DIURETIK: OLMESARTAN + HIDROKLOROTIYAZID
    # =========================================================================
    ("OLMESARTAN + HCT", "OLMETEC PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ARB + Diuretik, Daiichi Sankyo"),

    # =========================================================================
    # ACE INHIBITORU + DIURETIK: ENALAPRIL + HIDROKLOROTIYAZID
    # =========================================================================
    ("ENALAPRIL + HCT", "ENAPRIL PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, Sandoz"),
    ("ENALAPRIL + HCT", "KONVERIL PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, Nobel"),
    ("ENALAPRIL + HCT", "RENITEC PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, MSD"),

    # =========================================================================
    # ACE INHIBITORU + DIURETIK: LISINOPRIL + HIDROKLOROTIYAZID
    # =========================================================================
    ("LISINOPRIL + HCT", "ZESTORETIC", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, AstraZeneca"),
    ("LISINOPRIL + HCT", "SINORETIK", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik"),

    # =========================================================================
    # ACE INHIBITORU + DIURETIK: RAMIPRIL + HIDROKLOROTIYAZID
    # =========================================================================
    ("RAMIPRIL + HCT", "TRITACE PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, Sanofi"),
    ("RAMIPRIL + HCT", "RAMICARD PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik"),

    # =========================================================================
    # ACE INHIBITORU + DIURETIK: PERINDOPRIL + INDAPAMID
    # =========================================================================
    ("PERINDOPRIL + INDAPAMID", "COVERSYL PLUS", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + Diuretik, Servier"),

    # =========================================================================
    # ACE INHIBITORU + KKB: PERINDOPRIL + AMLODIPIN
    # =========================================================================
    ("PERINDOPRIL + AMLODIPIN", "COVERAM", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + KKB, Servier"),

    # ACE + KKB + DIURETIK: PERINDOPRIL + AMLODIPIN + INDAPAMID (Uclu)
    ("PERINDOPRIL + AMLODIPIN + INDAPAMID", "TRIPLIXAM", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "Uclu: ACE Inh + KKB + Diuretik, Servier"),

    # =========================================================================
    # ACE INHIBITORU + KKB: RAMIPRIL + AMLODIPIN
    # =========================================================================
    ("RAMIPRIL + AMLODIPIN", "EGIRAMLON", "KOMBINE_ANTIHIPERTANSIF", "4.2.12",
     "monoterapi kan basinci kontrol", None, "ACE Inh + KKB, Egis"),
]


_DIYABET_DPP4_SGLT2 = [
    # =========================================================================
    # DPP-4: SITAGLIPTIN (tek basina)
    # =========================================================================
    ("SITAGLIPTIN", "JANUVIA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, MSD"),
    ("SITAGLIPTIN", "ARLIPTIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Ali Raif"),
    ("SITAGLIPTIN", "GLIPDIA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("SITAGLIPTIN", "JASITA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, 25/50/100 mg"),
    ("SITAGLIPTIN", "SANOSITA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Sanovel"),
    ("SITAGLIPTIN", "SIABET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),

    # DPP-4: SITAGLIPTIN + METFORMIN
    ("SITAGLIPTIN + METFORMIN", "JANUMET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, MSD"),
    ("SITAGLIPTIN + METFORMIN", "ARLIPTIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Ali Raif"),
    ("SITAGLIPTIN + METFORMIN", "SANOSITA PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Sanovel"),

    # =========================================================================
    # DPP-4: VILDAGLIPTIN (tek basina)
    # =========================================================================
    ("VILDAGLIPTIN", "GALVUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Novartis"),
    ("VILDAGLIPTIN", "DIYATIX", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Sanovel"),
    ("VILDAGLIPTIN", "GLIVIDIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Recordati"),
    ("VILDAGLIPTIN", "TAGLIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Nobel"),
    ("VILDAGLIPTIN", "VEFILDA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Vefa"),
    ("VILDAGLIPTIN", "VIDAPTIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Ali Raif"),
    ("VILDAGLIPTIN", "VILATIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Genveon"),
    ("VILDAGLIPTIN", "VILBIODA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Biofarma"),
    ("VILDAGLIPTIN", "VILCOZA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Helba"),
    ("VILDAGLIPTIN", "VILDABET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Ilko"),
    ("VILDAGLIPTIN", "VILDALIP", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Neutec"),
    ("VILDAGLIPTIN", "VILDEGA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Bilim"),
    ("VILDAGLIPTIN", "VILNORM", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, World Medicine"),

    # DPP-4: VILDAGLIPTIN + METFORMIN
    ("VILDAGLIPTIN + METFORMIN", "GALVUS MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Novartis"),
    ("VILDAGLIPTIN + METFORMIN", "DIYATIX PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Sanovel"),
    ("VILDAGLIPTIN + METFORMIN", "GLIVIDIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("VILDAGLIPTIN + METFORMIN", "TAGLIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Nobel"),
    ("VILDAGLIPTIN + METFORMIN", "VIDAPTIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("VILDAGLIPTIN + METFORMIN", "VIGLIDA PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("VILDAGLIPTIN + METFORMIN", "VILDABET MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Ilko"),
    ("VILDAGLIPTIN + METFORMIN", "VILDEGA PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Bilim"),
    ("VILDAGLIPTIN + METFORMIN", "VILMET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("VILDAGLIPTIN + METFORMIN", "VIPTIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),

    # =========================================================================
    # DPP-4: LINAGLIPTIN (tek basina)
    # =========================================================================
    ("LINAGLIPTIN", "TRAJENTA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Boehringer Ingelheim"),
    ("LINAGLIPTIN", "DIANOVIA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "ELNAGLIP", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINADIYA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINATIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINAZEP", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINCRETIN", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINIGA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LINTREJA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "LIZERA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),
    ("LINAGLIPTIN", "SNOXX", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru"),

    # DPP-4: LINAGLIPTIN + METFORMIN
    ("LINAGLIPTIN + METFORMIN", "TRAJENTAMET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin, Boehringer Ingelheim"),
    ("LINAGLIPTIN + METFORMIN", "DIANOVIA MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("LINAGLIPTIN + METFORMIN", "LINATIN MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("LINAGLIPTIN + METFORMIN", "LINAZEP PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("LINAGLIPTIN + METFORMIN", "LINIGA PLUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("LINAGLIPTIN + METFORMIN", "LINTREJAMET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),
    ("LINAGLIPTIN + METFORMIN", "SNOXX-MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + Metformin"),

    # =========================================================================
    # DPP-4: SAKSAGLIPTIN (tek basina)
    # =========================================================================
    ("SAKSAGLIPTIN", "ONGLYZA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, AstraZeneca/BMS"),

    # =========================================================================
    # DPP-4: ALOGLIPTIN (tek basina)
    # =========================================================================
    ("ALOGLIPTIN", "VIPIDIA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 inhibitoru, Takeda"),

    # =========================================================================
    # SGLT-2: DAPAGLIFLOZIN (tek basina)
    # =========================================================================
    ("DAPAGLIFLOZIN", "FORZIGA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru, AstraZeneca"),
    ("DAPAGLIFLOZIN", "CALIRA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DAPADAP", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DAPGEON", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DAPITUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DAPLIG", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DAPRENZA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "GLAZONE", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "GLYXAR", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "JAGLIF", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("DAPAGLIFLOZIN", "DANIPTA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),

    # SGLT-2: DAPAGLIFLOZIN + METFORMIN
    ("DAPAGLIFLOZIN + METFORMIN", "XIGDUO", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin, AstraZeneca"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET XR", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin, uzatilmis salim"),
    ("DAPAGLIFLOZIN + METFORMIN", "GLAZONEMET XR", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin, uzatilmis salim"),

    # =========================================================================
    # SGLT-2: EMPAGLIFLOZIN (tek basina)
    # =========================================================================
    ("EMPAGLIFLOZIN", "JARDIANCE", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru, Boehringer Ingelheim"),
    ("EMPAGLIFLOZIN", "EMLADIP", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "EMPACROS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "EMPAFEL", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru, Nobel"),
    ("EMPAGLIFLOZIN", "EMPALFO", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "EMPATOR", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "GLIFLOMED", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "GLYZARDA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "JARDIFLOZ", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),
    ("EMPAGLIFLOZIN", "JARDOLIX", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 inhibitoru"),

    # SGLT-2: EMPAGLIFLOZIN + METFORMIN
    ("EMPAGLIFLOZIN + METFORMIN", "SYNJARDY", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin, Boehringer Ingelheim"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "SGLT-2 + Metformin, Nobel"),

    # =========================================================================
    # DPP-4 + SGLT-2: LINAGLIPTIN + EMPAGLIFLOZIN
    # =========================================================================
    ("LINAGLIPTIN + EMPAGLIFLOZIN", "GLYXAMBI", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "DPP-4 + SGLT-2 kombinasyonu, Boehringer Ingelheim"),

    # =========================================================================
    # GLP-1 AGONISTLERI
    # =========================================================================
    ("LIRAGLUTID", "VICTOZA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, Novo Nordisk, SC enjeksiyon"),
    ("LIRAGLUTID", "SAXENDA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, Novo Nordisk, obezite endikasyonu"),
    ("SEMAGLUTID", "OZEMPIC", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, Novo Nordisk, haftalik SC enjeksiyon"),
    ("SEMAGLUTID", "RYBELSUS", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, Novo Nordisk, oral tablet"),
    ("DULAGLUTID", "TRULICITY", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, Eli Lilly, haftalik SC enjeksiyon"),
    ("EKSENATID", "BYETTA", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, AstraZeneca, SC enjeksiyon"),
    ("EKSENATID", "BYDUREON", "DIYABET_DPP4_SGLT2", "4.2.38",
     "metformin sulfonilure glisemik kontrol", None, "GLP-1 agonisti, AstraZeneca, haftalik SC enjeksiyon"),
]


_KLOPIDOGREL = [
    # =========================================================================
    # KLOPIDOGREL (SUT 4.2.15.A)
    # =========================================================================
    ("KLOPIDOGREL", "PLAVIX", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", "12 ay sureli uzman hekim raporu", "Orijinal, Sanofi"),
    ("KLOPIDOGREL", "PINGEL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "KARUM", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "ATERVIX", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "BACLAN", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "CLOGAN", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "CLOPRA", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "DILOXOL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "DIPOREL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "KLOGEL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "LOPIGROL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "OPIREL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "PLANOR", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),
    ("KLOPIDOGREL", "PLAVIDOL", "KLOPIDOGREL", "4.2.15.A",
     "koroner stent anjiografi akut koroner sendrom", None, "Jenerik"),

    # =========================================================================
    # PRASUGREL (SUT 4.2.15.C)
    # =========================================================================
    ("PRASUGREL", "EFFIENT", "KLOPIDOGREL", "4.2.15.C",
     "akut koroner sendrom PKG perkütan koroner girisim",
     "1 yil sureli saglik kurulu raporu, <75 yas, >60 kg, SVO oykusu olmayan",
     "Orijinal, Daiichi Sankyo/Er-Kim"),
    ("PRASUGREL", "SUGVIDA", "KLOPIDOGREL", "4.2.15.C",
     "akut koroner sendrom PKG perkütan koroner girisim",
     None, "Jenerik, Celtis"),

    # =========================================================================
    # TIKAGRELOR (SUT 4.2.15.E)
    # =========================================================================
    ("TIKAGRELOR", "BRILINTA", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom",
     "1 yil sureli saglik kurulu raporu, ICD-10: I21.0-I21.9",
     "Orijinal, AstraZeneca, 60/90 mg"),
    ("TIKAGRELOR", "AGRILOR", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 90 mg"),
    ("TIKAGRELOR", "CAMILLA", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 90 mg"),
    ("TIKAGRELOR", "TALDEROL", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 90 mg"),
    ("TIKAGRELOR", "TICASA", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 60/90 mg"),
    ("TIKAGRELOR", "TIGRELO", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 90 mg"),
    ("TIKAGRELOR", "TILANTA", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 60/90 mg"),
    ("TIKAGRELOR", "TIXALOR", "KLOPIDOGREL", "4.2.15.E",
     "NSTEMI STEMI akut koroner sendrom", None, "Jenerik, 90 mg"),
]


_STATIN = [
    # =========================================================================
    # ATORVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("ATORVASTATIN", "LIPITOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", "40mg+ icin uzman raporu gerekli", "Orijinal, Viatris"),
    ("ATORVASTATIN", "ATOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik, Sanovel"),
    ("ATORVASTATIN", "ATEROZ", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "ALVASTIN", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "AMVASTAN", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "AVITOREL", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "CHOLVAST", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "COLASTIN-L", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "DIVATOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "KOLESTOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "LIPIDRA", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ATORVASTATIN", "TARDEN", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),

    # =========================================================================
    # ROSUVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("ROSUVASTATIN", "CRESTOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", "20mg+ icin uzman raporu gerekli", "Orijinal, AstraZeneca"),
    ("ROSUVASTATIN", "COLNAR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "LIVERCOL", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "RONAP", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ROSACT", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ROSUCOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ROSUFIX", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ROSUSTAR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ROSUVAS", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "STAGE", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "STATA", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),
    ("ROSUVASTATIN", "ULTROX", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),

    # =========================================================================
    # SIMVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("SIMVASTATIN", "ZOCOR", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", "40mg+ icin uzman raporu gerekli", "Orijinal, MSD"),
    ("SIMVASTATIN", "LIPVAKOL", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),

    # =========================================================================
    # PRAVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("PRAVASTATIN", "PRAVACHOL", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Orijinal, BMS"),

    # =========================================================================
    # FLUVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("FLUVASTATIN", "LESCOL", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", "80mg+ icin uzman raporu gerekli", "Orijinal, Novartis"),

    # =========================================================================
    # PITAVASTATIN (SUT 4.2.28.A)
    # =========================================================================
    ("PITAVASTATIN", "ALIPZA", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Orijinal, Recordati"),
    ("PITAVASTATIN", "PRATIN", "STATIN", "4.2.28.A",
     "LDL kolesterol statin lipid", None, "Jenerik"),

    # =========================================================================
    # EZETIMIB (tek basina) (SUT 4.2.28.C)
    # =========================================================================
    ("EZETIMIB", "EZETROL", "STATIN", "4.2.28.C",
     "LDL kolesterol ezetimib statin yetersiz", "En az 6 ay statin tedavisine ragmen LDL>100", "Orijinal, Organon/MSD"),
    ("EZETIMIB", "EZETEC", "STATIN", "4.2.28.C",
     "LDL kolesterol ezetimib statin yetersiz", None, "Jenerik, Neutec"),
    ("EZETIMIB", "EZELIPIN", "STATIN", "4.2.28.C",
     "LDL kolesterol ezetimib statin yetersiz", None, "Jenerik, Celtis"),

    # =========================================================================
    # ATORVASTATIN + EZETIMIB KOMBINASYONU (SUT 4.2.28.A + 4.2.28.C)
    # =========================================================================
    ("ATORVASTATIN + EZETIMIB", "EZETEC PLUS", "STATIN", "4.2.28.C",
     "LDL kolesterol statin ezetimib kombine", None, "Statin + Ezetimib kombinasyonu, Neutec"),
    ("ATORVASTATIN + EZETIMIB", "FIXLIP", "STATIN", "4.2.28.C",
     "LDL kolesterol statin ezetimib kombine", None, "Statin + Ezetimib kombinasyonu, Celtis"),

    # =========================================================================
    # ROSUVASTATIN + EZETIMIB KOMBINASYONU (SUT 4.2.28.A + 4.2.28.C)
    # =========================================================================
    ("ROSUVASTATIN + EZETIMIB", "EZEROS", "STATIN", "4.2.28.C",
     "LDL kolesterol statin ezetimib kombine", None, "Statin + Ezetimib kombinasyonu, Nuvomed"),
    ("ROSUVASTATIN + EZETIMIB", "ROSALIN", "STATIN", "4.2.28.C",
     "LDL kolesterol statin ezetimib kombine", None, "Statin + Ezetimib kombinasyonu, Celtis"),

    # =========================================================================
    # SIMVASTATIN + EZETIMIB KOMBINASYONU (SUT 4.2.28.A + 4.2.28.C)
    # =========================================================================
    ("SIMVASTATIN + EZETIMIB", "EZESIM", "STATIN", "4.2.28.C",
     "LDL kolesterol statin ezetimib kombine", None, "Statin + Ezetimib kombinasyonu, Neutec"),
]


# =============================================================================
# VERITABANI ISLEMLERI
# =============================================================================

def _baglanti_al():
    """SQLite baglantisi olusturur."""
    conn = sqlite3.connect(_DB_DOSYA)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def sut_db_olustur():
    """SUT ilac veritabanini olusturur ve tum verileri yukler.

    Tablolari olusturur, mevcut verileri siler ve guncel verileri ekler.
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    # Tablolari olustur
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sut_kategoriler (
            id INTEGER PRIMARY KEY,
            kategori_kodu TEXT UNIQUE NOT NULL,
            kategori_adi TEXT,
            sut_maddesi TEXT,
            aranan_ibare TEXT,
            kontrol_metni TEXT,
            aciklama TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sut_ilaclar (
            id INTEGER PRIMARY KEY,
            etkin_madde TEXT NOT NULL,
            ticari_isim TEXT,
            sut_kategorisi TEXT NOT NULL,
            sut_maddesi TEXT,
            aranan_ibare TEXT,
            rapor_kontrol_metni TEXT,
            notlar TEXT,
            FOREIGN KEY (sut_kategorisi) REFERENCES sut_kategoriler(kategori_kodu)
        )
    """)

    # Indeksler
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ilaclar_kategori ON sut_ilaclar(sut_kategorisi)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ilaclar_etkin_madde ON sut_ilaclar(etkin_madde)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ilaclar_ticari_isim ON sut_ilaclar(ticari_isim)")

    # Mevcut verileri temizle
    cur.execute("DELETE FROM sut_ilaclar")
    cur.execute("DELETE FROM sut_kategoriler")

    # Kategorileri ekle
    for kat in _KATEGORILER:
        cur.execute("""
            INSERT INTO sut_kategoriler (kategori_kodu, kategori_adi, sut_maddesi,
                                         aranan_ibare, kontrol_metni, aciklama)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            kat["kategori_kodu"],
            kat["kategori_adi"],
            kat["sut_maddesi"],
            kat["aranan_ibare"],
            kat["kontrol_metni"],
            kat["aciklama"],
        ))

    # Tum ilac verilerini birlestir
    tum_ilaclar = _KOMBINE_ANTIHIPERTANSIF + _DIYABET_DPP4_SGLT2 + _KLOPIDOGREL + _STATIN

    # Ilaclari ekle
    for ilac in tum_ilaclar:
        etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi, aranan_ibare, rapor_kontrol_metni, notlar = ilac
        cur.execute("""
            INSERT INTO sut_ilaclar (etkin_madde, ticari_isim, sut_kategorisi,
                                     sut_maddesi, aranan_ibare, rapor_kontrol_metni, notlar)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi,
              aranan_ibare, rapor_kontrol_metni, notlar))

    conn.commit()
    conn.close()

    toplam = len(tum_ilaclar)
    return toplam


def sut_kategori_bul(etkin_madde=None, ilac_adi=None):
    """Etkin madde veya ilac adina gore SUT kategorisini bulur.

    Args:
        etkin_madde: Etkin madde adi (ornegin "ATORVASTATIN", "VALSARTAN + AMLODIPIN")
        ilac_adi: Ticari isim (ornegin "EXFORGE", "LIPITOR", "JANUVIA")

    Returns:
        list of dict: Eslesen ilac kayitlari.
            Her dict: {id, etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi,
                       aranan_ibare, rapor_kontrol_metni, notlar,
                       kategori_adi, kategori_aranan_ibare, kategori_kontrol_metni}
        Eslesme yoksa bos liste doner.
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    sonuclar = []

    if etkin_madde:
        etkin_upper = etkin_madde.upper().strip()
        cur.execute("""
            SELECT i.*, k.kategori_adi, k.aranan_ibare as kategori_aranan_ibare,
                   k.kontrol_metni as kategori_kontrol_metni
            FROM sut_ilaclar i
            LEFT JOIN sut_kategoriler k ON i.sut_kategorisi = k.kategori_kodu
            WHERE UPPER(i.etkin_madde) = ? OR UPPER(i.etkin_madde) LIKE ?
        """, (etkin_upper, f"%{etkin_upper}%"))
        sonuclar = [dict(row) for row in cur.fetchall()]

    if ilac_adi:
        ilac_upper = ilac_adi.upper().strip()
        # Dozaj bilgisini cikar - sadece ismi ara
        # "EXFORGE 5/160 MG" -> "EXFORGE" ile eslesebilsin
        cur.execute("""
            SELECT i.*, k.kategori_adi, k.aranan_ibare as kategori_aranan_ibare,
                   k.kontrol_metni as kategori_kontrol_metni
            FROM sut_ilaclar i
            LEFT JOIN sut_kategoriler k ON i.sut_kategorisi = k.kategori_kodu
            WHERE UPPER(i.ticari_isim) = ?
               OR UPPER(i.ticari_isim) LIKE ?
               OR ? LIKE UPPER(i.ticari_isim) || '%'
        """, (ilac_upper, f"%{ilac_upper}%", ilac_upper))
        ek_sonuclar = [dict(row) for row in cur.fetchall()]

        # Cift kayitlari onle
        mevcut_idler = {s["id"] for s in sonuclar}
        for s in ek_sonuclar:
            if s["id"] not in mevcut_idler:
                sonuclar.append(s)

    conn.close()
    return sonuclar


def sut_ilaclari_listele(kategori):
    """Belirli bir SUT kategorisindeki tum ilaclari listeler.

    Args:
        kategori: "KOMBINE_ANTIHIPERTANSIF", "DIYABET_DPP4_SGLT2",
                  "KLOPIDOGREL", "STATIN"

    Returns:
        list of dict: {id, etkin_madde, ticari_isim, sut_kategorisi,
                       sut_maddesi, aranan_ibare, rapor_kontrol_metni, notlar}
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM sut_ilaclar
        WHERE sut_kategorisi = ?
        ORDER BY etkin_madde, ticari_isim
    """, (kategori,))

    sonuclar = [dict(row) for row in cur.fetchall()]
    conn.close()
    return sonuclar


def sut_kontrol_ibaresi_al(kategori):
    """Belirli bir SUT kategorisi icin raporda aranan ibareyi dondurur.

    Args:
        kategori: "KOMBINE_ANTIHIPERTANSIF", "DIYABET_DPP4_SGLT2",
                  "KLOPIDOGREL", "STATIN"

    Returns:
        dict: {kategori_kodu, kategori_adi, sut_maddesi, aranan_ibare,
               kontrol_metni, aciklama}
        veya None
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM sut_kategoriler
        WHERE kategori_kodu = ?
    """, (kategori,))

    row = cur.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def sut_etkin_maddeler(kategori=None):
    """Benzersiz etkin madde listesi dondurur.

    Args:
        kategori: Opsiyonel - belirli kategorideki etkin maddeler

    Returns:
        list of str: Sirali benzersiz etkin maddeler
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    if kategori:
        cur.execute("""
            SELECT DISTINCT etkin_madde FROM sut_ilaclar
            WHERE sut_kategorisi = ?
            ORDER BY etkin_madde
        """, (kategori,))
    else:
        cur.execute("SELECT DISTINCT etkin_madde FROM sut_ilaclar ORDER BY etkin_madde")

    sonuclar = [row[0] for row in cur.fetchall()]
    conn.close()
    return sonuclar


def sut_marka_ara(arama_metni):
    """Ticari isimde arama yapar (buyuk/kucuk harf duyarsiz).

    Args:
        arama_metni: Ornegin "EXFORGE", "LIPITOR", "JANV"

    Returns:
        list of dict: Eslesen ilac kayitlari
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    arama_upper = arama_metni.upper().strip()
    cur.execute("""
        SELECT i.*, k.kategori_adi
        FROM sut_ilaclar i
        LEFT JOIN sut_kategoriler k ON i.sut_kategorisi = k.kategori_kodu
        WHERE UPPER(i.ticari_isim) LIKE ?
        ORDER BY i.ticari_isim
    """, (f"%{arama_upper}%",))

    sonuclar = [dict(row) for row in cur.fetchall()]
    conn.close()
    return sonuclar


def sut_istatistikler():
    """Veritabani istatistiklerini dondurur.

    Returns:
        dict: {toplam_ilac, toplam_etkin_madde, toplam_marka, kategoriler: {...}}
    """
    conn = _baglanti_al()
    cur = conn.cursor()

    # Toplam ilac sayisi
    cur.execute("SELECT COUNT(*) FROM sut_ilaclar")
    toplam_ilac = cur.fetchone()[0]

    # Toplam etkin madde
    cur.execute("SELECT COUNT(DISTINCT etkin_madde) FROM sut_ilaclar")
    toplam_etkin = cur.fetchone()[0]

    # Toplam marka
    cur.execute("SELECT COUNT(DISTINCT ticari_isim) FROM sut_ilaclar")
    toplam_marka = cur.fetchone()[0]

    # Kategori bazli istatistikler
    kategoriler = {}
    cur.execute("SELECT * FROM sut_kategoriler")
    for kat in cur.fetchall():
        kodu = kat["kategori_kodu"]
        cur.execute("SELECT COUNT(*) FROM sut_ilaclar WHERE sut_kategorisi=?", (kodu,))
        ilac_sayisi = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT etkin_madde) FROM sut_ilaclar WHERE sut_kategorisi=?", (kodu,))
        etkin_sayisi = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT ticari_isim) FROM sut_ilaclar WHERE sut_kategorisi=?", (kodu,))
        marka_sayisi = cur.fetchone()[0]

        kategoriler[kodu] = {
            "kategori_adi": kat["kategori_adi"],
            "sut_maddesi": kat["sut_maddesi"],
            "ilac_sayisi": ilac_sayisi,
            "etkin_madde_sayisi": etkin_sayisi,
            "marka_sayisi": marka_sayisi,
        }

    conn.close()

    return {
        "toplam_ilac": toplam_ilac,
        "toplam_etkin_madde": toplam_etkin,
        "toplam_marka": toplam_marka,
        "kategoriler": kategoriler,
    }


# =============================================================================
# VERITABANINI OTOMATIK OLUSTUR (import aninda)
# =============================================================================

def _db_kontrol_ve_olustur():
    """Veritabaninin var olup olmadigini kontrol eder, yoksa olusturur."""
    yeniden_olustur = False

    if not os.path.exists(_DB_DOSYA):
        yeniden_olustur = True
    else:
        # Tablo varligini kontrol et
        try:
            conn = _baglanti_al()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sut_ilaclar")
            sayi = cur.fetchone()[0]
            conn.close()
            if sayi == 0:
                yeniden_olustur = True
        except Exception:
            yeniden_olustur = True

    if yeniden_olustur:
        toplam = sut_db_olustur()
        print(f"[SUT DB] Veritabani olusturuldu: {_DB_DOSYA} ({toplam} ilac kaydi)")


# Modul import edildiginde otomatik calistir
_db_kontrol_ve_olustur()


# =============================================================================
# TEST / CALISTIRMA
# =============================================================================

if __name__ == "__main__":
    # Veritabanini yeniden olustur (guncel veri ile)
    print("Veritabani yeniden olusturuluyor...")
    toplam = sut_db_olustur()
    print(f"Toplam {toplam} ilac kaydi eklendi.\n")

    # Istatistikler
    stats = sut_istatistikler()
    print("=" * 70)
    print("SUT ILAC VERITABANI ISTATISTIKLERI")
    print("=" * 70)
    print(f"  Toplam ilac kaydi  : {stats['toplam_ilac']}")
    print(f"  Toplam etkin madde : {stats['toplam_etkin_madde']}")
    print(f"  Toplam marka       : {stats['toplam_marka']}")
    print()

    for kodu, bilgi in stats["kategoriler"].items():
        print(f"  {kodu} (SUT {bilgi['sut_maddesi']}):")
        print(f"    {bilgi['kategori_adi']}")
        print(f"    Ilac kaydi   : {bilgi['ilac_sayisi']}")
        print(f"    Etkin madde  : {bilgi['etkin_madde_sayisi']}")
        print(f"    Marka        : {bilgi['marka_sayisi']}")
        print()

    # Ornek aramalar
    print("=" * 70)
    print("ORNEK ARAMALAR")
    print("=" * 70)

    print("\n--- sut_kategori_bul(ilac_adi='EXFORGE') ---")
    sonuclar = sut_kategori_bul(ilac_adi="EXFORGE")
    for s in sonuclar:
        print(f"  {s['etkin_madde']:35s} | {s['ticari_isim']:20s} | {s['sut_kategorisi']:30s} | {s['sut_maddesi']}")

    print("\n--- sut_kategori_bul(etkin_madde='ATORVASTATIN') ---")
    sonuclar = sut_kategori_bul(etkin_madde="ATORVASTATIN")
    for s in sonuclar[:5]:
        print(f"  {s['etkin_madde']:35s} | {s['ticari_isim']:20s} | {s['sut_kategorisi']:30s} | {s['sut_maddesi']}")
    if len(sonuclar) > 5:
        print(f"  ... ve {len(sonuclar) - 5} kayit daha")

    print("\n--- sut_ilaclari_listele('KLOPIDOGREL') ---")
    sonuclar = sut_ilaclari_listele("KLOPIDOGREL")
    for s in sonuclar:
        print(f"  {s['etkin_madde']:20s} | {s['ticari_isim']:15s} | {s['sut_maddesi']}")

    print("\n--- sut_kontrol_ibaresi_al('STATIN') ---")
    ibare = sut_kontrol_ibaresi_al("STATIN")
    if ibare:
        print(f"  Kategori    : {ibare['kategori_adi']}")
        print(f"  SUT Maddesi : {ibare['sut_maddesi']}")
        print(f"  Aranan Ibare: {ibare['aranan_ibare']}")
        print(f"  Kontrol     : {ibare['kontrol_metni'][:100]}...")

    print("\n--- sut_marka_ara('JARDIANCE') ---")
    sonuclar = sut_marka_ara("JARDIANCE")
    for s in sonuclar:
        print(f"  {s['etkin_madde']:25s} | {s['ticari_isim']:15s} | {s['kategori_adi']}")

    print("\n--- sut_etkin_maddeler('DIYABET_DPP4_SGLT2') ---")
    maddeler = sut_etkin_maddeler("DIYABET_DPP4_SGLT2")
    for m in maddeler:
        print(f"  {m}")

    print("\n--- sut_etkin_maddeler() (tum kategoriler) ---")
    maddeler = sut_etkin_maddeler()
    print(f"  Toplam {len(maddeler)} benzersiz etkin madde")
    for m in maddeler[:10]:
        print(f"  {m}")
    print("  ...")
