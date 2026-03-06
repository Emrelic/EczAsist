"""
SUT (Saglik Uygulama Tebligi) Ilac Veritabani
Turkiye'de satilan ilaclar icin 4 SUT kategorisi

Kaynaklar:
- ilacabak.com (etkin madde bazli ilac listeleri)
- ilacrehberi.com
- ilactr.com
- ilacdata.com

Son guncelleme: 2026-03-06

Format: (etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi)
"""

# =============================================================================
# SUT KATEGORI TANIMLARI
# =============================================================================

SUT_KATEGORILERI = {
    "KOMBINE_ANTIHIPERTANSIF": {
        "sut_maddesi": "4.2.12",
        "aciklama": "ARB + Kalsiyum Kanal Blokoru Kombinasyonlari (ve uclu ARB+KKB+HCT)",
        "kosul": "Monoterapi ile kan basinci kontrol altina alinamadiginin raporda belirtilmesi gerekir"
    },
    "DIYABET_DPP4_SGLT2": {
        "sut_maddesi": "4.2.38",
        "aciklama": "DPP-4 Inhibitorleri, SGLT2 Inhibitorleri ve Metformin Kombinasyonlari",
        "kosul": "Metformin ve/veya sulfonilure ile yeterli glisemik kontrol saglanamayan hastalarda"
    },
    "KLOPIDOGREL": {
        "sut_maddesi": "4.2.15",
        "aciklama": "Klopidogrel iceren antiagregan ilaclar",
        "kosul": "Kardiyoloji/noroloji/kalp damar cerrahisi uzman hekim raporu"
    },
    "STATIN": {
        "sut_maddesi": "4.2.28",
        "aciklama": "Lipid dusurucu ilaclar (statinler ve kombinasyonlari)",
        "kosul": "20mg ustu rosuvastatin ve 40mg ustu atorvastatin/simvastatin uzman raporu gerektirir"
    }
}

# =============================================================================
# KATEGORI 1: KOMBINE ANTIHIPERTANSIF (SUT 4.2.12)
# ARB + Kalsiyum Kanal Blokoru Kombinasyonlari
# =============================================================================

KOMBINE_ANTIHIPERTANSIF = [
    # =========================================================================
    # VALSARTAN + AMLODIPIN
    # =========================================================================
    ("VALSARTAN + AMLODIPIN", "EXFORGE 5/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "EXFORGE 10/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "CARDOFIX 5/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "CARDOFIX 10/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "COMBISAR 5/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "COMBISAR 10/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "VALCODIN 5/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "VALCODIN 10/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "VALDIPIN 5/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN", "VALDIPIN 10/160 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # VALSARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    # =========================================================================
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT 5/160/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT 5/160/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT 10/160/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT 10/160/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "EXFORGE HCT 10/320/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "CARDOFIX PLUS 5/160/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "CARDOFIX PLUS 5/160/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "CARDOFIX PLUS 10/160/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("VALSARTAN + AMLODIPIN + HCT", "CARDOFIX PLUS 10/160/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # OLMESARTAN + AMLODIPIN
    # =========================================================================
    ("OLMESARTAN + AMLODIPIN", "SEVIKAR 20/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "SEVIKAR 40/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "SEVIKAR 40/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "EXCALIBA 20/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "EXCALIBA 40/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "EXCALIBA 40/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "OLMECOMB 40/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN", "OLMECOMB 40/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # OLMESARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    # =========================================================================
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS 20/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS 40/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS 40/5/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS 40/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "SEVIKAR PLUS 40/10/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS 20/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS 40/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS 40/5/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS 40/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "EXCALIBA PLUS 40/10/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "OLMECOMB PLUS 40/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "OLMECOMB PLUS 40/5/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "OLMECOMB PLUS 40/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("OLMESARTAN + AMLODIPIN + HCT", "OLMECOMB PLUS 40/10/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # TELMISARTAN + AMLODIPIN
    # =========================================================================
    ("TELMISARTAN + AMLODIPIN", "TELMODIP 80/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("TELMISARTAN + AMLODIPIN", "TELMODIP 80/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # TELMISARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    # =========================================================================
    ("TELMISARTAN + AMLODIPIN + HCT", "TELMODIP PLUS 80/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("TELMISARTAN + AMLODIPIN + HCT", "TELMODIP PLUS 80/10/25 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # IRBESARTAN + AMLODIPIN
    # =========================================================================
    ("IRBESARTAN + AMLODIPIN", "KARVEA DUO 150/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "KARVEA DUO 150/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "KARVEA DUO 300/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "IRDAPIN 150/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "IRDAPIN 150/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "IRDAPIN 300/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN", "IRDAPIN 300/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # IRBESARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    # =========================================================================
    ("IRBESARTAN + AMLODIPIN + HCT", "IRDAPIN PLUS 150/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN + HCT", "IRDAPIN PLUS 150/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN + HCT", "IRDAPIN PLUS 300/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("IRBESARTAN + AMLODIPIN + HCT", "IRDAPIN PLUS 300/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # KANDESARTAN + AMLODIPIN
    # =========================================================================
    ("KANDESARTAN + AMLODIPIN", "CANLOX 16/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "CANLOX 16/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "CANLOX 32/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "CANLOX 32/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "RANTAZIN 8/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "RANTAZIN 16/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "RANTAZIN 16/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "TANSIFA 16/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "TANSIFA 16/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "TANSIFA 32/5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN", "TANSIFA 32/10 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),

    # =========================================================================
    # KANDESARTAN + AMLODIPIN + HIDROKLOROTIYAZID (Uclu)
    # =========================================================================
    ("KANDESARTAN + AMLODIPIN + HCT", "CANLOX PLUS 16/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "CANLOX PLUS 16/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "RANTAZIN PLUS 16/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "RANTAZIN PLUS 16/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "TANSIFA PLUS 16/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "TANSIFA PLUS 16/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "TANSIFA PLUS 32/5/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
    ("KANDESARTAN + AMLODIPIN + HCT", "TANSIFA PLUS 32/10/12.5 MG", "KOMBINE_ANTIHIPERTANSIF", "4.2.12"),
]

# =============================================================================
# KATEGORI 2: DIYABET DPP-4 ve SGLT2 INHIBITORLERI (SUT 4.2.38)
# =============================================================================

DIYABET_DPP4_SGLT2 = [
    # =========================================================================
    # DPP-4: SITAGLIPTIN (tek basina)
    # =========================================================================
    ("SITAGLIPTIN", "JANUVIA 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "ARLIPTIN 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "GLIPDIA 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "JASITA 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "JASITA 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "JASITA 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "SANOSITA 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN", "SIABET 100 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: SITAGLIPTIN + METFORMIN
    # =========================================================================
    ("SITAGLIPTIN + METFORMIN", "JANUMET 50/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "JANUMET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "JANUMET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "ARLIPTIN MET 50/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "ARLIPTIN MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "ARLIPTIN MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "SANOSITA PLUS 50/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "SANOSITA PLUS 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SITAGLIPTIN + METFORMIN", "SANOSITA PLUS 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: VILDAGLIPTIN (tek basina)
    # =========================================================================
    ("VILDAGLIPTIN", "GALVUS 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "DIYATIX 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "GLIVIDIN 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "TAGLIN 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VEFILDA 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VIDAPTIN 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILATIN 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILBIODA 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILCOZA 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILDABET 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILDALIP 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILDEGA 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN", "VILNORM 50 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: VILDAGLIPTIN + METFORMIN
    # =========================================================================
    ("VILDAGLIPTIN + METFORMIN", "GALVUS MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "GALVUS MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "DIYATIX PLUS 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "DIYATIX PLUS 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "GLIVIDIN MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "GLIVIDIN MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "TAGLIN MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "TAGLIN MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIDAPTIN MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIDAPTIN MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIGLIDA PLUS 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIGLIDA PLUS 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILDABET MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILDABET MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILDEGA PLUS 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILDEGA PLUS 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILMET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VILMET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIPTIN MET 50/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("VILDAGLIPTIN + METFORMIN", "VIPTIN MET 50/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: LINAGLIPTIN (tek basina)
    # =========================================================================
    ("LINAGLIPTIN", "TRAJENTA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "DIANOVIA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "ELNAGLIP 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINADIYA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINATIN 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINAZEP 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINCRETIN 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINIGA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LINTREJA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "LIZERA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN", "SNOXX 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: LINAGLIPTIN + METFORMIN
    # =========================================================================
    ("LINAGLIPTIN + METFORMIN", "TRAJENTAMET 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "TRAJENTAMET 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "DIANOVIA MET 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "DIANOVIA MET 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINATIN MET 2.5/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINATIN MET 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINATIN MET 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINAZEP PLUS 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINIGA PLUS 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINIGA PLUS 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINTREJAMET 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "LINTREJAMET 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "SNOXX-MET 2.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + METFORMIN", "SNOXX-MET 2.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: SAKSAGLIPTIN (tek basina)
    # =========================================================================
    ("SAKSAGLIPTIN", "ONGLYZA 2.5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("SAKSAGLIPTIN", "ONGLYZA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP-4: ALOGLIPTIN (tek basina)
    # =========================================================================
    ("ALOGLIPTIN", "VIPIDIA 12.5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("ALOGLIPTIN", "VIPIDIA 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # SGLT2: DAPAGLIFLOZIN (tek basina)
    # =========================================================================
    ("DAPAGLIFLOZIN", "FORZIGA 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "CALIRA 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "CALIRA 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DANIPTA 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DAPADAP 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DAPGEON 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DAPITUS 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DAPLIG 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "DAPRENZA 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "GLAZONE 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "GLYXAR 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "JAGLIF 5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN", "JAGLIF 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # SGLT2: DAPAGLIFLOZIN + METFORMIN
    # =========================================================================
    ("DAPAGLIFLOZIN + METFORMIN", "XIGDUO 5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "XIGDUO 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET 5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET XR 5/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET XR 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET XR 10/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "CALIRA-MET XR 10/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "GLAZONEMET XR 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("DAPAGLIFLOZIN + METFORMIN", "GLAZONEMET XR 10/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # SGLT2: EMPAGLIFLOZIN (tek basina)
    # =========================================================================
    ("EMPAGLIFLOZIN", "JARDIANCE 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "JARDIANCE 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMLADIP 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMLADIP 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPACROS 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPACROS 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPAFEL 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPAFEL 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPALFO 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPALFO 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPATOR 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "EMPATOR 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "GLIFLOMED 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "GLIFLOMED 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "GLYZARDA 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "GLYZARDA 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "JARDIFLOZ 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "JARDIFLOZ 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "JARDOLIX 10 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN", "JARDOLIX 25 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # SGLT2: EMPAGLIFLOZIN + METFORMIN
    # =========================================================================
    ("EMPAGLIFLOZIN + METFORMIN", "SYNJARDY 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "SYNJARDY 12.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 5/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 12.5/500 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 12.5/850 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("EMPAGLIFLOZIN + METFORMIN", "EMPAFEL MET 12.5/1000 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),

    # =========================================================================
    # DPP4 + SGLT2: LINAGLIPTIN + EMPAGLIFLOZIN
    # =========================================================================
    ("LINAGLIPTIN + EMPAGLIFLOZIN", "GLYXAMBI 10/5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
    ("LINAGLIPTIN + EMPAGLIFLOZIN", "GLYXAMBI 25/5 MG", "DIYABET_DPP4_SGLT2", "4.2.38"),
]

# =============================================================================
# KATEGORI 3: KLOPIDOGREL (SUT 4.2.15)
# =============================================================================

KLOPIDOGREL = [
    ("KLOPIDOGREL", "PLAVIX 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "PINGEL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "KARUM 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "ATERVIX 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "BACLAN 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "CLOGAN 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "CLOPRA 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "DILOXOL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "DIPOREL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "KLOGEL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "LOPIGROL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "OPIREL 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "PLANOR 75 MG", "KLOPIDOGREL", "4.2.15"),
    ("KLOPIDOGREL", "PLAVIDOL 75 MG", "KLOPIDOGREL", "4.2.15"),
]

# =============================================================================
# KATEGORI 4: STATIN (SUT 4.2.28)
# =============================================================================

STATIN = [
    # =========================================================================
    # ATORVASTATIN
    # =========================================================================
    ("ATORVASTATIN", "LIPITOR 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "LIPITOR 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "LIPITOR 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "LIPITOR 80 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATOR 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATOR 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATOR 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATOR 80 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATEROZ 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATEROZ 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ATEROZ 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ALVASTIN 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ALVASTIN 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ALVASTIN 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "ALVASTIN 80 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "AVITOREL 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "AVITOREL 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "CHOLVAST 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "CHOLVAST 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "CHOLVAST 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "COLASTIN-L 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "COLASTIN-L 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "COLASTIN-L 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "COLASTIN-L 80 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "DIVATOR 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "DIVATOR 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "DIVATOR 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "KOLESTOR 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "KOLESTOR 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "KOLESTOR 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "LIPIDRA 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "LIPIDRA 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "TARDEN 10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "TARDEN 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "TARDEN 40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "TARDEN 80 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "AMVASTAN 20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN", "AMVASTAN 40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # ROSUVASTATIN
    # =========================================================================
    ("ROSUVASTATIN", "CRESTOR 5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "CRESTOR 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "CRESTOR 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "CRESTOR 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "COLNAR 5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "COLNAR 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "COLNAR 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "COLNAR 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "LIVERCOL 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "LIVERCOL 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "LIVERCOL 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "RONAP 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "RONAP 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "RONAP 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSACT 5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSACT 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSACT 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSACT 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUCOR 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUCOR 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUCOR 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUFIX 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUFIX 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUSTAR 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUSTAR 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUSTAR 40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUVAS 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ROSUVAS 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "STAGE 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "STAGE 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "STATA 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "STATA 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ULTROX 5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ULTROX 10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ULTROX 20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN", "ULTROX 40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # SIMVASTATIN
    # =========================================================================
    ("SIMVASTATIN", "ZOCOR 20 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN", "ZOCOR 40 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN", "LIPVAKOL 10 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN", "LIPVAKOL 20 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN", "LIPVAKOL 40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # FLUVASTATIN
    # =========================================================================
    ("FLUVASTATIN", "LESCOL 40 MG", "STATIN", "4.2.28"),
    ("FLUVASTATIN", "LESCOL XL 80 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # PRAVASTATIN
    # =========================================================================
    ("PRAVASTATIN", "PRAVACHOL 10 MG", "STATIN", "4.2.28"),
    ("PRAVASTATIN", "PRAVACHOL 20 MG", "STATIN", "4.2.28"),
    ("PRAVASTATIN", "PRAVACHOL 40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # PITAVASTATIN
    # =========================================================================
    ("PITAVASTATIN", "ALIPZA 1 MG", "STATIN", "4.2.28"),
    ("PITAVASTATIN", "ALIPZA 2 MG", "STATIN", "4.2.28"),
    ("PITAVASTATIN", "ALIPZA 4 MG", "STATIN", "4.2.28"),
    ("PITAVASTATIN", "PRATIN 2 MG", "STATIN", "4.2.28"),
    ("PITAVASTATIN", "PRATIN 4 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # ATORVASTATIN + EZETIMIB KOMBINASYONU
    # =========================================================================
    ("ATORVASTATIN + EZETIMIB", "EZETEC PLUS 10/10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN + EZETIMIB", "EZETEC PLUS 10/20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN + EZETIMIB", "EZETEC PLUS 10/40 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN + EZETIMIB", "FIXLIP 10/10 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN + EZETIMIB", "FIXLIP 10/20 MG", "STATIN", "4.2.28"),
    ("ATORVASTATIN + EZETIMIB", "FIXLIP 10/40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # ROSUVASTATIN + EZETIMIB KOMBINASYONU
    # =========================================================================
    ("ROSUVASTATIN + EZETIMIB", "EZEROS 10/5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "EZEROS 10/10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "EZEROS 10/20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "EZEROS 10/40 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "ROSALIN 10/5 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "ROSALIN 10/10 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "ROSALIN 10/20 MG", "STATIN", "4.2.28"),
    ("ROSUVASTATIN + EZETIMIB", "ROSALIN 10/40 MG", "STATIN", "4.2.28"),

    # =========================================================================
    # SIMVASTATIN + EZETIMIB KOMBINASYONU
    # =========================================================================
    ("SIMVASTATIN + EZETIMIB", "EZESIM 10/10 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN + EZETIMIB", "EZESIM 10/20 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN + EZETIMIB", "EZESIM 10/40 MG", "STATIN", "4.2.28"),
    ("SIMVASTATIN + EZETIMIB", "EZESIM 10/80 MG", "STATIN", "4.2.28"),
]

# =============================================================================
# TUM ILACLAR - BIRLESIK LISTE
# =============================================================================

TUM_SUT_ILACLARI = (
    KOMBINE_ANTIHIPERTANSIF +
    DIYABET_DPP4_SGLT2 +
    KLOPIDOGREL +
    STATIN
)

# =============================================================================
# YARDIMCI FONKSIYONLAR
# =============================================================================


def kategoriye_gore_getir(kategori):
    """Belirli bir SUT kategorisindeki tum ilaclari dondurur.

    Args:
        kategori: "KOMBINE_ANTIHIPERTANSIF", "DIYABET_DPP4_SGLT2",
                  "KLOPIDOGREL", "STATIN"

    Returns:
        list of tuples: (etkin_madde, ticari_isim, sut_kategorisi, sut_maddesi)
    """
    return [ilac for ilac in TUM_SUT_ILACLARI if ilac[2] == kategori]


def etkin_maddeye_gore_getir(etkin_madde):
    """Belirli bir etkin maddeyi iceren tum ilaclari dondurur.

    Args:
        etkin_madde: Ornegin "ATORVASTATIN", "VALSARTAN + AMLODIPIN"

    Returns:
        list of tuples
    """
    etkin_madde_upper = etkin_madde.upper()
    return [ilac for ilac in TUM_SUT_ILACLARI if ilac[0] == etkin_madde_upper]


def ticari_isimde_ara(arama_metni):
    """Ticari isim icinde arama yapar (buyuk/kucuk harf duyarsiz).

    Args:
        arama_metni: Ornegin "EXFORGE", "LIPITOR", "JANUVIA"

    Returns:
        list of tuples
    """
    arama_upper = arama_metni.upper()
    return [ilac for ilac in TUM_SUT_ILACLARI if arama_upper in ilac[1].upper()]


def benzersiz_etkin_maddeler(kategori=None):
    """Benzersiz etkin madde listesi dondurur.

    Args:
        kategori: Opsiyonel - belirli kategorideki etkin maddeler

    Returns:
        sorted list of strings
    """
    if kategori:
        ilaclari = kategoriye_gore_getir(kategori)
    else:
        ilaclari = TUM_SUT_ILACLARI
    return sorted(set(ilac[0] for ilac in ilaclari))


def benzersiz_ticari_isimler(kategori=None):
    """Benzersiz ticari isim listesi dondurur (doz bilgisi haric).

    Args:
        kategori: Opsiyonel - belirli kategorideki ticari isimler

    Returns:
        sorted list of strings (sadece marka ismi, doz haric)
    """
    if kategori:
        ilaclari = kategoriye_gore_getir(kategori)
    else:
        ilaclari = TUM_SUT_ILACLARI

    marka_isimleri = set()
    for ilac in ilaclari:
        # Ticari isimden doz bilgisini cikart (ilk sayi gecene kadar)
        isim = ilac[1]
        # Sayisal karakterden onceki kismi al
        marka = ""
        for char in isim:
            if char.isdigit():
                break
            marka += char
        marka = marka.strip()
        if marka:
            marka_isimleri.add(marka)

    return sorted(marka_isimleri)


def istatistikler():
    """Veritabani istatistiklerini dondurur."""
    stats = {
        "toplam_ilac": len(TUM_SUT_ILACLARI),
        "toplam_etkin_madde": len(benzersiz_etkin_maddeler()),
        "toplam_marka": len(benzersiz_ticari_isimler()),
        "kategoriler": {}
    }
    for kategori in SUT_KATEGORILERI:
        kategori_ilaclari = kategoriye_gore_getir(kategori)
        stats["kategoriler"][kategori] = {
            "ilac_sayisi": len(kategori_ilaclari),
            "etkin_madde_sayisi": len(benzersiz_etkin_maddeler(kategori)),
            "marka_sayisi": len(benzersiz_ticari_isimler(kategori)),
            "sut_maddesi": SUT_KATEGORILERI[kategori]["sut_maddesi"]
        }
    return stats


# =============================================================================
# TEST / CALISTIRMA
# =============================================================================

if __name__ == "__main__":
    stats = istatistikler()
    print("=" * 60)
    print("SUT ILAC VERITABANI ISTATISTIKLERI")
    print("=" * 60)
    print(f"Toplam ilac kaydi: {stats['toplam_ilac']}")
    print(f"Toplam etkin madde: {stats['toplam_etkin_madde']}")
    print(f"Toplam marka: {stats['toplam_marka']}")
    print()

    for kategori, bilgi in stats["kategoriler"].items():
        print(f"  {kategori} (SUT {bilgi['sut_maddesi']}):")
        print(f"    Ilac kaydi: {bilgi['ilac_sayisi']}")
        print(f"    Etkin madde: {bilgi['etkin_madde_sayisi']}")
        print(f"    Marka: {bilgi['marka_sayisi']}")
        print()

    print("=" * 60)
    print("ORNEK ARAMALAR:")
    print("=" * 60)

    print("\n--- Ticari isimde 'EXFORGE' arama ---")
    for ilac in ticari_isimde_ara("EXFORGE"):
        print(f"  {ilac[0]:40s} | {ilac[1]:30s} | {ilac[3]}")

    print("\n--- Etkin madde: ATORVASTATIN ---")
    for ilac in etkin_maddeye_gore_getir("ATORVASTATIN")[:5]:
        print(f"  {ilac[0]:40s} | {ilac[1]:30s} | {ilac[3]}")
    print("  ...")

    print("\n--- Kategori: KLOPIDOGREL ---")
    for ilac in kategoriye_gore_getir("KLOPIDOGREL"):
        print(f"  {ilac[0]:40s} | {ilac[1]:30s} | {ilac[3]}")
