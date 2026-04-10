# -*- coding: utf-8 -*-
"""
SUT Kontrolleri

6 SUT kuralı için algoritmik ilaç kontrolleri:
1. Kombine Antihipertansifler (4.2.12.B) - Monoterapi ibaresi
2. DPP-4 / SGLT-2 / GLP-1 İnhibitörleri (4.2.38) - Glisemik kontrol
3. Klopidogrel / Prasugrel / Tikagrelor (4.2.15) - Anjiografi tarihi
4. Statinler (4.2.28.A) - LDL düzeyi
5. Fibratlar (4.2.28.B) - Trigliserid düzeyi
6. Ranolazin (4.2.15.F) - Kronik stabil angina, BB/KKB intoleransı
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from .base_kontrol import BaseKontrol, KontrolSonucu, KontrolRaporu

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# SUT Kategori Tespiti
# ═══════════════════════════════════════════════════════════════════════

# SUT maddesi -> kategori eşleştirme
SUT_MADDESI_KATEGORI = {
    '4.2.12': 'KOMBINE_ANTIHIPERTANSIF',
    '4.2.12.B': 'KOMBINE_ANTIHIPERTANSIF',
    '4.2.38': 'DIYABET_DPP4_SGLT2',
    '4.2.38.A': 'DIYABET_DPP4_SGLT2',
    '4.2.38.B': 'DIYABET_DPP4_SGLT2',
    '4.2.15': 'KLOPIDOGREL',
    '4.2.15.A': 'KLOPIDOGREL',
    '4.2.15.B': 'KLOPIDOGREL',
    '4.2.15.C': 'IVABRADIN',
    '4.2.15.D': 'YOAK',
    '4.2.15.F': 'RANOLAZIN',
    '4.2.28': 'STATIN',
    '4.2.28.A': 'STATIN',
    '4.2.28.B': 'FIBRAT',
    '4.2.2': 'PSIKIYATRI',
    '4.2.9': 'SOLUNUM',
    '4.2.24': 'SOLUNUM',
    '4.2.24.B': 'SOLUNUM',
}

# Rapor kodu -> kategori eşleştirme (Medula rapor kodları)
RAPOR_KODU_KATEGORI = {
    '07.02': 'DIYABET_DPP4_SGLT2',   # Diyabet ilaçları
    '07.02.1': 'DIYABET_DPP4_SGLT2',
    # NOT: 07.01 genel endokrin kodu - 07.01.5 Puberte Prekoks, 07.01.1 BH Eksikliği
    # Sadece 07.02.x diyabet. 07.01 diyabet DEĞİL!
    '04.02': 'STATIN',                 # Kardiyovasküler (statin/klopidogrel/beta bloker)
    '04.02.1': 'KLOPIDOGREL',          # Antiplatelet
    '04.05': 'KOMBINE_ANTIHIPERTANSIF', # Antihipertansif
    # 04.08: Lipid düşürücü — statin veya fibrat olabilir
    # Kategori ilaç adı/etkin maddeden belirlenir, rapor kodu son çare
    '04.08': 'STATIN',
    '04.01': 'IVABRADIN',              # İvabradin/Eplerenon
    '04.03': 'YOAK',                   # Antikoagülan (YOAK)
    '04.04': 'KLOPIDOGREL',            # Antitrombotik
    '11.04': 'PSIKIYATRI',             # Psikiyatri
    '11.04.5': 'PSIKIYATRI',
    '11.04.8': 'PSIKIYATRI',
    '11.03': 'PSIKIYATRI',
    '05.01': 'SOLUNUM',               # Solunum LABA+ICS
    '05.02': 'SOLUNUM',               # Solunum LABA+LAMA+ICS
    '12.01': 'GOZ',                    # Göz ilaçları
    '12.04': 'GOZ',
    '02.00': 'ONKOLOJI',              # Onkoloji
    '02.01': 'ONKOLOJI',
    '10.04': 'NOROLOJI',              # Nöroloji
    '10.05': 'NOROLOJI',
    '10.12': 'NOROLOJI',
    '06.01': 'BIFOSFONAT',            # Osteoporoz
    '06.02': 'BIFOSFONAT',
    '14.01': 'ANTIVIRAL',             # Antiviral
    '20.00': 'GENEL_RAPORLU',         # Genel raporlu
    '20.02': 'GENEL_RAPORLU',
    '06.06': 'GIS',                    # GİS
    '03.00': 'POTASYUM_SITRAT',        # Üroloji/Nefroloji raporlu
    '15.08': 'GENEL_RAPORLU',          # Nörojenik Mesane (Üroloji)
    '15.01': 'GIS',                     # Gastroenteroloji
    '15.02': 'GIS',                     # GIS raporlu
    '08.01': 'GENEL_RAPORLU',          # Hematoloji
    '08.02': 'GENEL_RAPORLU',          # Hematoloji
    '09.01': 'GENEL_RAPORLU',          # Kadın Hastalıkları
    '16.01': 'GENEL_RAPORLU',          # Organ Nakli
    '01.01': 'GENEL_RAPORLU',          # Romatoloji
    '13.01': 'GENEL_RAPORLU',          # Dermatoloji
}

# Etkin madde -> kategori eşleştirme (büyük harf, boşluklar düzeltilmiş)
ETKIN_MADDE_KATEGORI = {
    # KOMBINE_ANTIHIPERTANSIF
    'VALSARTAN/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'AMLODIPIN/VALSARTAN': 'KOMBINE_ANTIHIPERTANSIF',
    'OLMESARTAN MEDOKSOMIL/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'AMLODIPIN/OLMESARTAN': 'KOMBINE_ANTIHIPERTANSIF',
    'TELMISARTAN/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'AMLODIPIN/TELMISARTAN': 'KOMBINE_ANTIHIPERTANSIF',
    'IRBESARTAN/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'PERINDOPRIL/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'AMLODIPIN/PERINDOPRIL': 'KOMBINE_ANTIHIPERTANSIF',
    'RAMIPRIL/AMLODIPIN': 'KOMBINE_ANTIHIPERTANSIF',
    'AMLODIPIN/ATORVASTATIN': 'KOMBINE_ANTIHIPERTANSIF',
    'SAKUBITRIL/VALSARTAN': 'KOMBINE_ANTIHIPERTANSIF',
    # ARB+Diüretik kombinasyonları
    'VALSARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'OLMESARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'TELMISARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'IRBESARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'KANDESARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'LOSARTAN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    # ACE+Diüretik
    'PERINDOPRIL/INDAPAMID': 'KOMBINE_ANTIHIPERTANSIF',
    'ENALAPRIL/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'RAMIPRIL/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'LISINOPRIL/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    # Üçlü kombinasyonlar
    'VALSARTAN/AMLODIPIN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'OLMESARTAN/AMLODIPIN/HIDROKLOROTIYAZID': 'KOMBINE_ANTIHIPERTANSIF',
    'PERINDOPRIL/AMLODIPIN/INDAPAMID': 'KOMBINE_ANTIHIPERTANSIF',

    # DIYABET_DPP4_SGLT2
    'SITAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'SITAGLIPTIN FOSFAT': 'DIYABET_DPP4_SGLT2',
    'VILDAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'SAKSAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'LINAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'ALOGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'DAPAGLIFLOZIN': 'DIYABET_DPP4_SGLT2',
    'DAPAGLIFLOZIN PROPANDIOL': 'DIYABET_DPP4_SGLT2',
    'EMPAGLIFLOZIN': 'DIYABET_DPP4_SGLT2',
    'KANAGLIFLOZIN': 'DIYABET_DPP4_SGLT2',
    'ERTUGLIFLOZIN': 'DIYABET_DPP4_SGLT2',
    'LIRAGLUTID': 'DIYABET_DPP4_SGLT2',
    'SEMAGLUTID': 'DIYABET_DPP4_SGLT2',
    'DULAGLUTID': 'DIYABET_DPP4_SGLT2',
    'EKSENATID': 'DIYABET_DPP4_SGLT2',
    # Kombine
    'SITAGLIPTIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'VILDAGLIPTIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'SAKSAGLIPTIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'LINAGLIPTIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'ALOGLIPTIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'DAPAGLIFLOZIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'EMPAGLIFLOZIN/METFORMIN': 'DIYABET_DPP4_SGLT2',
    'EMPAGLIFLOZIN/LINAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'DAPAGLIFLOZIN/SAKSAGLIPTIN': 'DIYABET_DPP4_SGLT2',
    'INSÜLIN GLARJIN/LIKSISENATID': 'DIYABET_DPP4_SGLT2',
    'INSÜLIN DEGLUDEK/LIRAGLUTID': 'DIYABET_DPP4_SGLT2',

    # KLOPIDOGREL
    'KLOPIDOGREL': 'KLOPIDOGREL',
    'KLOPIDOGREL BISULFAT': 'KLOPIDOGREL',
    'KLOPIDOGREL HIDROJEN SULFAT': 'KLOPIDOGREL',
    'PRASUGREL': 'KLOPIDOGREL',
    'PRASUGREL HIDROKLORÜR': 'KLOPIDOGREL',
    'TIKAGRELOR': 'KLOPIDOGREL',

    # STATIN
    'ATORVASTATIN': 'STATIN',
    'ATORVASTATIN KALSIYUM': 'STATIN',
    'ROSUVASTATIN': 'STATIN',
    'ROSUVASTATIN KALSIYUM': 'STATIN',
    'SIMVASTATIN': 'STATIN',
    'PRAVASTATIN': 'STATIN',
    'PRAVASTATIN SODYUM': 'STATIN',
    'FLUVASTATIN': 'STATIN',
    'FLUVASTATIN SODYUM': 'STATIN',
    'PITAVASTATIN': 'STATIN',
    'PITAVASTATIN KALSIYUM': 'STATIN',
    'EZETIMIB': 'STATIN',
    'EZETIMIB/SIMVASTATIN': 'STATIN',
    'EZETIMIB/ATORVASTATIN': 'STATIN',
    'EZETIMIB/ROSUVASTATIN': 'STATIN',

    # FIBRAT
    'FENOFIBRAT': 'FIBRAT',
    'GEMFIBROZIL': 'FIBRAT',
    'BEZAFIBRAT': 'FIBRAT',
    'SIPROFIBRAT': 'FIBRAT',

    # BIFOSFONAT (Osteoporoz)
    'ALENDRONAT': 'BIFOSFONAT',
    'ALENDRONAT SODYUM': 'BIFOSFONAT',
    'ALENDRONIK ASIT': 'BIFOSFONAT',
    'RISEDRONAT': 'BIFOSFONAT',
    'RISEDRONAT SODYUM': 'BIFOSFONAT',
    'IBANDRONAT': 'BIFOSFONAT',
    'IBANDRONIK ASIT': 'BIFOSFONAT',
    'ZOLEDRONAT': 'BIFOSFONAT',
    'ZOLEDRONIK ASIT': 'BIFOSFONAT',
    'KOLEKALSITEROL': 'BIFOSFONAT',  # Fosavance = alendronat+kolekalsiferol

    # YOAK (Yeni Oral Antikoagülanlar)
    'RIVAROKSABAN': 'YOAK',
    'APIKSABAN': 'YOAK',
    'EDOKSABAN': 'YOAK',
    'DABIGATRAN': 'YOAK',
    'DABIGATRAN ETEKSILAT': 'YOAK',

    # YOAK (Yeni Oral Antikoagülanlar)
    'APIKSABAN': 'YOAK',
    'EDOKSABAN': 'YOAK',
    'EDOKSABAN TOSILAT': 'YOAK',
    'RIVAROKSABAN': 'YOAK',
    'DABIGATRAN': 'YOAK',
    'DABIGATRAN ETEKSILAT': 'YOAK',

    # IVABRADIN
    'IVABRADIN': 'IVABRADIN',
    'IVABRADIN HIDROKLORÜR': 'IVABRADIN',

    # EPLERENON
    'EPLERENON': 'EPLERENON',

    # RANOLAZIN
    'RANOLAZIN': 'RANOLAZIN',

    # PSIKIYATRI
    'ESSITALOPRAM': 'PSIKIYATRI',
    'ESSITALOPRAM OKZALAT': 'PSIKIYATRI',
    'FLUOKSETIN': 'PSIKIYATRI',
    'FLUOKSETIN HCL': 'PSIKIYATRI',
    'SERTRALIN': 'PSIKIYATRI',
    'SERTRALIN HCL': 'PSIKIYATRI',
    'PAROKSETIN': 'PSIKIYATRI',
    'DULOKSETIN': 'PSIKIYATRI',
    'DULOKSETIN HCL': 'PSIKIYATRI',
    'VENLAFAKSIN': 'PSIKIYATRI',
    'ARIPIPRAZOL': 'PSIKIYATRI',
    'KETIAPIN': 'PSIKIYATRI',
    'OLANZAPIN': 'PSIKIYATRI',
    'RISPERIDON': 'PSIKIYATRI',
    'PALIPERIDON': 'PSIKIYATRI',

    # SOLUNUM
    'FORMOTEROL FUMARAT': 'SOLUNUM',
    'SALMETEROL': 'SOLUNUM',
    'FORMOTEROL FUMARAT+BUDEZONID': 'SOLUNUM',
    'FORMOTEROL FUMARAT+FLUTIKAZON PROPIYONAT': 'SOLUNUM',
    'SALMETEROL+FLUTIKAZON PROPIYONAT': 'SOLUNUM',
    'TIOTROPIUM BROMUR': 'SOLUNUM',
    'UMEKLIDINYUM': 'SOLUNUM',
    'INDAKATEROL': 'SOLUNUM',
    'GLICOPIRONYUM': 'SOLUNUM',

    # DIYABET EK (taramada görülenler)
    'PIOGLITAZON': 'DIYABET_DPP4_SGLT2',
    'PIOGLITAZON HCL': 'DIYABET_DPP4_SGLT2',
    'AKARBOZ': 'DIYABET_DPP4_SGLT2',
    'GLIKLAZID': 'DIYABET_DPP4_SGLT2',
    'GLIMEPIRID': 'DIYABET_DPP4_SGLT2',
    'METFORMIN': 'DIYABET_DPP4_SGLT2',
    'METFORMIN HCL': 'DIYABET_DPP4_SGLT2',
    'INSULIN ASPART': 'DIYABET_DPP4_SGLT2',
    'INSULIN GLARJIN': 'DIYABET_DPP4_SGLT2',
    'INSULIN NPH': 'DIYABET_DPP4_SGLT2',

    # BB ilaçlar - raporsuz ama mesajlı (2026-04-06 eklendi)
    # Reçete türü kontrolü gereken
    'TRAMADOL': 'RECETE_TURU_KIRMIZI',
    'TRAMADOL HCL': 'RECETE_TURU_KIRMIZI',
    'BIPERIDEN': 'RECETE_TURU_YESIL',
    'BIPERIDEN HCL': 'RECETE_TURU_YESIL',

    # Rapor zorunlu ama raporsuz yazılabilen (SUT uyarısı)
    'TRIMETAZIDIN': 'TRIMETAZIDIN',
    'TRIMETAZIDIN DIHIDROKLORUR': 'TRIMETAZIDIN',
    'ENOKSAPARIN': 'DMAH',
    'ENOKSAPARIN SODYUM': 'DMAH',

    # Kadın hormonları
    'NORETISTERON': 'KADIN_HORMON',
    'NORETISTERON ASETAT': 'KADIN_HORMON',

    # Antibiyotik (EK-4/E)
    'SIPROFLOKSASIN': 'ANTIBIYOTIK_FLOROKINOLON',
    'SIPROFLOKSASIN HCL': 'ANTIBIYOTIK_FLOROKINOLON',

    # Makrolid antibiyotik (EK-4/E - oral form KY, kısıtlama yok)
    'KLARITROMISIN': 'RAPORSUZ_BILGILENDIRME',

    # Potasyum Sitrat (EK-4/F - Üroloji/Nefroloji raporlu)
    'POTASYUM SITRAT': 'POTASYUM_SITRAT',

    # MAO-B İnhibitörleri (Parkinson)
    'SELEGILIN': 'RAPORSUZ_BILGILENDIRME',
    'SELEGILIN HCL': 'RAPORSUZ_BILGILENDIRME',
    'RASAGILIN': 'RAPORSUZ_BILGILENDIRME',
    'RASAGILIN MEZILAT': 'RAPORSUZ_BILGILENDIRME',
    'SAFINAMID': 'RAPORSUZ_BILGILENDIRME',

    # Raporsuz verilebilen - mesaj bilgilendirme
    'IBUPROFEN': 'RAPORSUZ_BILGILENDIRME',
    'PARASETAMOL': 'RAPORSUZ_BILGILENDIRME',
    'OKSIKONAZOL': 'RAPORSUZ_BILGILENDIRME',
    'BENZIDAMIN': 'RAPORSUZ_BILGILENDIRME',
    'KLORFENIRAMIN': 'RAPORSUZ_BILGILENDIRME',
    'FENILEFRIN': 'RAPORSUZ_BILGILENDIRME',
    'PSEUDOEFEDRIN': 'RAPORSUZ_BILGILENDIRME',

    # Mono antihipertansif (raporsuz verilebilir)
    'VALSARTAN': 'MONO_ANTIHIPERTANSIF',
    'DOKSAZOSIN': 'MONO_ANTIHIPERTANSIF',
    'DOKSAZOSIN MEZILAT': 'MONO_ANTIHIPERTANSIF',

    # Montelukast
    'MONTELUKAST': 'SOLUNUM',
    'MONTELUKAST SODYUM': 'SOLUNUM',
    'DESLORATADIN': 'RAPORSUZ_BILGILENDIRME',
}


# İlaç ticari adı → kategori (etkin madde boş geldiğinde kullanılır)
ILAC_ADI_KATEGORI = {
    'PRIMOLUT': 'KADIN_HORMON',
    'IBURAMIN': 'RAPORSUZ_BILGILENDIRME',
    # CEDRINA = Ketiapin (antipsikotik) - Psikiyatri uzman raporu gerekir
    'CEDRINA': 'PSIKIYATRI',
    'OLAXINN': 'PSIKIYATRI',
    'JARDIANCE': 'DIYABET_DPP4_SGLT2',
    'FORZIGA': 'DIYABET_DPP4_SGLT2',
    'DIAFORMIN': 'DIYABET_DPP4_SGLT2',
    'GLUKOFEN': 'DIYABET_DPP4_SGLT2',
    'GLIFOR': 'DIYABET_DPP4_SGLT2',
    'CIPRO': 'ANTIBIYOTIK_FLOROKINOLON',
    'TRAVAZOL': 'RAPORSUZ_BILGILENDIRME',
    'CONTRAMAL': 'RECETE_TURU_KIRMIZI',
    'OKSAPAR': 'DMAH',
    'LUSTRAL': 'PSIKIYATRI',
    'IBUCOLD': 'RAPORSUZ_BILGILENDIRME',
    'A-FERIN': 'RAPORSUZ_BILGILENDIRME',
    'THERAFLU': 'RAPORSUZ_BILGILENDIRME',
    'DIOVAN': 'MONO_ANTIHIPERTANSIF',
    'CARDURA': 'MONO_ANTIHIPERTANSIF',
    'DESMONT': 'SOLUNUM',
    'OCERAL': 'RAPORSUZ_BILGILENDIRME',
    'ANDOREX': 'RAPORSUZ_BILGILENDIRME',
    'MACROL': 'RAPORSUZ_BILGILENDIRME',
    'AKINETON': 'RECETE_TURU_YESIL',
    'ENOX': 'DMAH',
    'ANTI-ASIDOZ': 'POTASYUM_SITRAT',
    'ANTIASIDOZ': 'POTASYUM_SITRAT',
    'NORM-ASIDOZ': 'POTASYUM_SITRAT',
    'FULSAC': 'PSIKIYATRI',
    'CITOLES': 'PSIKIYATRI',
    'ABIZOL': 'PSIKIYATRI',
    'DUXET': 'PSIKIYATRI',
    'EFEXOR': 'PSIKIYATRI',
    'EFFEXOR': 'PSIKIYATRI',
    'CYMBALTA': 'PSIKIYATRI',
    # Klopidogrel / Antiplatelet
    'PLAVIX': 'KLOPIDOGREL',
    'KARUM': 'KLOPIDOGREL',
    'KLOPIDOGREL': 'KLOPIDOGREL',
    'BRILINTA': 'KLOPIDOGREL',
    'EFFIENT': 'KLOPIDOGREL',
    'PLAGREL': 'KLOPIDOGREL',
    'PINGEL': 'KLOPIDOGREL',
    # YOAK
    'XARELTO': 'YOAK',
    'RAZINA': 'YOAK',
    'ELIQUIS': 'YOAK',
    'LIXIANA': 'YOAK',
    'PRADAXA': 'YOAK',
    'DABIGATRAN': 'YOAK',
    # LATIXA = Ranolazin (antianginal) → SUT 4.2.15.F
    'LATIXA': 'RANOLAZIN',
    'RANEXA': 'RANOLAZIN',
    # Fibratlar
    'LIPANTHYL': 'FIBRAT',
    'LIPANTIL': 'FIBRAT',
    'TRALIP': 'FIBRAT',
    'LIPOFEN': 'FIBRAT',
    # Bifosfonatlar (Osteoporoz)
    'FOSAMAX': 'BIFOSFONAT',
    'FOSAVANCE': 'BIFOSFONAT',
    'FOSACAN': 'BIFOSFONAT',
    'ACTONEL': 'BIFOSFONAT',
    'BONVIVA': 'BIFOSFONAT',
    'ACLASTA': 'BIFOSFONAT',
    'ZOMETA': 'BIFOSFONAT',
    'OSTEOFOS': 'BIFOSFONAT',
    'OSTEOMAX': 'BIFOSFONAT',
    'ALENDRO': 'BIFOSFONAT',
    # Statinler
    'ATOR': 'STATIN',
    'LIPITOR': 'STATIN',
    'CRESTOR': 'STATIN',
    'ROZACT': 'STATIN',
    'ROSUVA': 'STATIN',
    'KOLESTER': 'STATIN',
    'PRAVATOR': 'STATIN',
    # ARB / Antihipertansifler (mono)
    'HIPERSAR': 'MONO_ANTIHIPERTANSIF',
    'MICARDIS': 'MONO_ANTIHIPERTANSIF',
    'ATACAND': 'MONO_ANTIHIPERTANSIF',
    'KARVEA': 'MONO_ANTIHIPERTANSIF',
    'LOSARTAN': 'MONO_ANTIHIPERTANSIF',
    'COZAAR': 'MONO_ANTIHIPERTANSIF',
    # Psikiyatri ek
    'DESYREL': 'PSIKIYATRI',
    'SECITA': 'PSIKIYATRI',
    'DEPAKIN': 'PSIKIYATRI',
    'RISPERDAL': 'PSIKIYATRI',
    'KETILEPT': 'PSIKIYATRI',
    'ZYPREXA': 'PSIKIYATRI',
}


def sut_kategorisi_tespit_et(ilac_sonuc: Dict) -> Optional[str]:
    """
    İlaç kontrol sonucundan SUT kategorisini tespit et.

    Args:
        ilac_sonuc: ilac_kontrolu_yap() dönüş değeri

    Returns:
        str: Kategori kodu veya None
    """
    # 1. SUT maddesi ile eşleştir (en güvenilir)
    sut_maddesi = ilac_sonuc.get('sut_maddesi')
    if sut_maddesi:
        for madde, kategori in SUT_MADDESI_KATEGORI.items():
            if sut_maddesi.startswith(madde):
                return kategori

    # 2. Etkin madde ile eşleştir
    etkin_madde = ilac_sonuc.get('etkin_madde')
    if etkin_madde:
        etkin_madde_upper = etkin_madde.strip().upper()
        if etkin_madde_upper in ETKIN_MADDE_KATEGORI:
            return ETKIN_MADDE_KATEGORI[etkin_madde_upper]

        # Kısmi eşleştirme
        for em, kategori in ETKIN_MADDE_KATEGORI.items():
            if em in etkin_madde_upper or etkin_madde_upper in em:
                return kategori

    # 2b. İlaç adından kategori tahmin et (etkin madde eşleşmediyse veya boşsa)
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    if ilac_adi:
        ilac_kisa = ilac_adi.split()[0] if ilac_adi else ""
        for em, kategori in ILAC_ADI_KATEGORI.items():
            if em in ilac_adi or em == ilac_kisa:
                return kategori

    # 3. Rapor kodu ile eşleştir
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        # Tam eşleşme
        if rapor_kodu in RAPOR_KODU_KATEGORI:
            return RAPOR_KODU_KATEGORI[rapor_kodu]
        # Ana kod eşleşmesi (ör: 07.02.1 → 07.02)
        ana_kod = '.'.join(rapor_kodu.split('.')[:2])
        if ana_kod in RAPOR_KODU_KATEGORI:
            return RAPOR_KODU_KATEGORI[ana_kod]

    # 4. SUT veritabanlarından ara (ilaç adı ile)
    ilac_adi = ilac_sonuc.get('ilac_adi')

    # 3a. SQLite veritabanı (sut_ilac_db)
    try:
        from sut_ilac_db import sut_kategori_bul
        sonuclar = sut_kategori_bul(etkin_madde=etkin_madde, ilac_adi=ilac_adi)
        if sonuclar:
            return sonuclar[0].get('sut_kategorisi') or sonuclar[0].get(2)
    except (ImportError, Exception):
        pass

    # 3b. Python dict veritabanı (sut_ilac_veritabani)
    try:
        from sut_ilac_veritabani import ticari_isimde_ara, etkin_maddeye_gore_getir
        if etkin_madde:
            sonuclar = etkin_maddeye_gore_getir(etkin_madde)
            if sonuclar:
                return sonuclar[0][2]

        if ilac_adi:
            marka = ilac_adi.split()[0] if ilac_adi else ""
            if marka and len(marka) >= 3:
                sonuclar = ticari_isimde_ara(marka)
                if sonuclar:
                    return sonuclar[0][2]
    except (ImportError, Exception):
        pass

    # 5. Öğrenilen ilaçlar DB (AI tarafından belirlenen kategori)
    try:
        from kontrol_kurallari import get_ogrenilen_ilaclar
        ogrenilen = get_ogrenilen_ilaclar()
        if ilac_adi:
            kayit = ogrenilen.ilac_bul(ilac_adi)
            if kayit and kayit.get("farmakolojik_grup"):
                logger.info(f"AI öğrenilen kategori: {ilac_adi} → {kayit['farmakolojik_grup']}")
                return kayit["farmakolojik_grup"]
        if etkin_madde:
            kayitlar = ogrenilen.etkin_madde_ile_bul(etkin_madde)
            for k in kayitlar:
                if k.get("farmakolojik_grup"):
                    logger.info(f"AI öğrenilen kategori (etkin madde): {etkin_madde} → {k['farmakolojik_grup']}")
                    return k["farmakolojik_grup"]
    except (ImportError, Exception):
        pass

    return None


# ═══════════════════════════════════════════════════════════════════════
# SUT Kontrol Fonksiyonları (Mesaj metninden algoritmik kontrol)
# ═══════════════════════════════════════════════════════════════════════

def _turkce_normalize(metin: str) -> str:
    """Kapsamlı Türkçe/Latince metin normalizasyonu — büyük/küçük harf ve
    fonetik farklılıkları ortadan kaldırarak eşleştirme doğruluğunu artırır.

    Dönüşümler:
      1. Lowercase
      2. Türkçe özel karakterler → ASCII (İ/ı→i, Ö/ö→o, Ü/ü→u, Ş/ş→s, Ç/ç→c, Ğ/ğ→g)
      3. Avrupa aksanlı karakterler → ASCII (â→a, é→e, ñ→n, vb.)
      4. Digraph / fonetik dönüşümler (ph→f, th→t, sh→s, ch→c, ck→k, qu→k, wh→v)
      5. Harf denkliği (x→ks, w→v, q→k, y→i geçişleri)
    """
    # 1. Türkçe büyük harfleri ÖNCE dönüştür (İ.lower() = i+combining dot sorunu)
    _TR_BUYUK = str.maketrans({
        'İ': 'i', 'I': 'i',
        'Ö': 'o', 'Ü': 'u', 'Ş': 's', 'Ç': 'c', 'Ğ': 'g',
    })
    t = metin.translate(_TR_BUYUK)

    # 2. Lowercase (artık İ sorunu yok)
    t = t.lower()

    # 3. Kalan Türkçe + Avrupa aksanlı karakterler + harf denkliği
    _NORM_MAP = str.maketrans({
        'ı': 'i', 'ö': 'o', 'ü': 'u', 'ş': 's', 'ç': 'c', 'ğ': 'g',
        # Avrupa aksanlı
        'â': 'a', 'à': 'a', 'á': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
        'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ù': 'u', 'ú': 'u', 'û': 'u',
        'ñ': 'n', 'ý': 'y', 'ÿ': 'y',
        # Harf denkliği
        'w': 'v', 'q': 'k',
    })
    t = t.translate(_NORM_MAP)
    # ß → ss (translate tek char → tek char, bu özel)
    t = t.replace('ß', 'ss')

    # 4. Digraph / fonetik dönüşümler (sıra önemli — uzun olanlar önce)
    _DIGRAPHS = [
        ('ph', 'f'),
        ('th', 't'),
        ('sh', 's'),
        ('ch', 'c'),
        ('ck', 'k'),
        ('qu', 'k'),
        ('wh', 'v'),
        ('gh', 'g'),
        ('ae', 'e'),
        ('oe', 'o'),
    ]
    for digraph, replacement in _DIGRAPHS:
        t = t.replace(digraph, replacement)

    # x → ks
    t = t.replace('x', 'ks')

    return t


def _turkce_ara(metin: str, aranan: str) -> bool:
    """Türkçe karakter farkı gözetmeden metin içinde arama.
    İ/i/I/ı, Ü/ü/U/u, Ö/ö/O/o, Ş/ş/S/s, Ç/ç/C/c, Ğ/ğ/G/g fark etmez.
    Örnek: _turkce_ara("SÜLFONİLÜRELER", "sülfonilüre") → True
    """
    return _turkce_normalize(aranan) in _turkce_normalize(metin)


def _tum_metinleri_birlesir(ilac_sonuc: Dict) -> str:
    """
    SUT kontrolü için tüm metin kaynaklarını birleştir.
    Mesaj metni + rapor açıklamaları + tanı bilgileri.
    """
    parcalar = []

    # Mesaj metni (İlaç Bilgi penceresinden)
    mesaj = ilac_sonuc.get('mesaj_metni')
    if mesaj:
        parcalar.append(mesaj)

    # Rapor açıklamaları
    aciklamalar = ilac_sonuc.get('rapor_aciklamalari', [])
    if aciklamalar:
        parcalar.extend(aciklamalar)

    # Tanı bilgileri
    tani_bilgileri = ilac_sonuc.get('rapor_tani_bilgileri', [])
    for tani in tani_bilgileri:
        sut_kodu = tani.get('sut_kodu', '')
        if sut_kodu:
            parcalar.append(sut_kodu)
        for icd in tani.get('icd_kodlari', []):
            adi = icd.get('adi', '')
            if adi:
                parcalar.append(adi)

    return " ".join(parcalar)


def _mesaj_icinde_ara(mesaj_metni: str, aranacak_kelimeler: List[str]) -> bool:
    """Mesaj metni içinde anahtar kelimeleri ara."""
    if not mesaj_metni:
        return False
    mesaj_lower = mesaj_metni.lower()
    return all(kelime.lower() in mesaj_lower for kelime in aranacak_kelimeler)


def _eslesen_parcayi_bul(metin: str, anahtar_kelime: str, cerceve=40) -> str:
    """Metinde anahtar kelimenin geçtiği bölümü ±cerceve karakter ile döndür."""
    if not metin or not anahtar_kelime:
        return ""
    metin_lower = _turkce_normalize(metin)
    aranan_lower = _turkce_normalize(anahtar_kelime)
    pos = metin_lower.find(aranan_lower)
    if pos < 0:
        return ""
    baslangic = max(0, pos - cerceve)
    bitis = min(len(metin), pos + len(anahtar_kelime) + cerceve)
    parca = metin[baslangic:bitis].strip()
    if baslangic > 0:
        parca = "..." + parca
    if bitis < len(metin):
        parca = parca + "..."
    return parca


def kontrol_kombine_antihipertansif(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.12.B - Kombine Antihipertansif Kontrol

    Raporda "monoterapi ile hasta kan basıncının yeteri kadar
    kontrol altına alınamadığı" ibaresi olmalı.
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    eslesen_kelime = ""
    if tum_metin:
        metin_lower = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        if 'monoterapi' in metin_lower:
            bulundu = True
            eslesen_kelime = "monoterapi"
        elif 'tek ilaç' in metin_lower and 'yeter' in metin_lower:
            bulundu = True
            eslesen_kelime = "tek ilaç"
        elif 'kan basıncı' in metin_lower and 'kontrol' in metin_lower:
            bulundu = True
            eslesen_kelime = "kan basıncı"

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Monoterapi ibaresi bulundu',
            detaylar={'aranan': 'monoterapi', 'bulundu': True},
            uyari='Raporda "monoterapi ile yeterli kontrol sağlanamadığı" ibaresi kontrol edilmeli',
            sut_kurali='SUT 4.2.12.B — Monoterapi ile kan basıncı kontrol altına alınamamış olmalı',
            aranan_ibare='monoterapi / tek ilaç tedavisi / kan basıncı kontrol',
            bulunan_metin=_eslesen_parcayi_bul(tum_metin, eslesen_kelime)
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Monoterapi ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'monoterapi', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: Monoterapi ibaresi raporda olmalı',
            sut_kurali='SUT 4.2.12.B — Monoterapi ile kan basıncı kontrol altına alınamamış olmalı',
            aranan_ibare='monoterapi / tek ilaç tedavisi / kan basıncı kontrol'
        )


def kontrol_diyabet_dpp4_sglt2(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.38 - DPP-4 / SGLT-2 / GLP-1 Kontrol

    Fıkra 6: SGLT2 inhibitörleri (dapagliflozin, empagliflozin) ve kombinasyonları:
    - Metformin ve/veya sülfonilürelerin maksimum tolere edilebilir dozlarında
      yeterli glisemik kontrol sağlanamamış hastalarda
    - Endokrinoloji veya iç hastalıkları uzmanınca veya raporu ile
    - Kalp yetmezliği/KBH endikasyonunda raporsuz yazılabilir (diyabet dışı)
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    doktor = (ilac_sonuc.get('doktor_uzmanligi') or '').lower()

    # Doktor branş kontrolü
    doktor_endokrin = any(k in doktor for k in ['endokrin', 'endokrinoloji'])
    doktor_dahiliye = any(k in doktor for k in ['iç hastalık', 'ic hastalik', 'dahiliye', 'internal'])
    doktor_uygun_sglt2 = doktor_endokrin or doktor_dahiliye

    # SGLT2 mi?
    sglt2_ilaclar = ['JARDIANCE', 'FORZIGA', 'INVOKANA', 'STEGLATRO',
        'EMPAGLIFLOZIN', 'DAPAGLIFLOZIN', 'KANAGLIFLOZIN', 'ERTUGLIFLOZIN']
    sglt2_kombi = ['GLYXAMBI', 'SYNJARDY', 'QTERN']  # SGLT2+DPP4/metformin kombi
    sglt2_mi = any(k in ilac_adi for k in sglt2_ilaclar + sglt2_kombi)

    sut_kurali = 'SUT 4.2.38(6) — SGLT2: endokrinoloji/iç hastalıkları + metformin/sülfonilüre maks dozda glisemik kontrol sağlanamamış'

    bulundu = False
    if tum_metin:
        metformin_var = _turkce_ara(tum_metin, 'metformin')
        sulfonilure_var = _turkce_ara(tum_metin, 'sülfonilüre')
        glisemik_var = _turkce_ara(tum_metin, 'glisemik') or _turkce_ara(tum_metin, 'kan şekeri') or 'hba1c' in tum_metin.lower()
        kontrol_var = _turkce_ara(tum_metin, 'kontrol') or _turkce_ara(tum_metin, 'yeterli') or _turkce_ara(tum_metin, 'sağlana')
        maksimum_var = _turkce_ara(tum_metin, 'maksimum') or _turkce_ara(tum_metin, 'maks') or _turkce_ara(tum_metin, 'tolere')

        if metformin_var and (sulfonilure_var or glisemik_var):
            bulundu = True
        elif glisemik_var and kontrol_var:
            bulundu = True
        elif metformin_var and kontrol_var:
            bulundu = True

    if bulundu:
        eslesen = ""
        for kelime in ['metformin', 'sülfonilüre', 'glisemik', 'hba1c', 'kan şekeri', 'maksimum']:
            p = _eslesen_parcayi_bul(tum_metin, kelime)
            if p:
                eslesen = p
                break

        # SGLT2 için doktor branşı kontrolü
        uyari_brans = ""
        if sglt2_mi and not doktor_uygun_sglt2 and not rapor_kodu:
            uyari_brans = f"SGLT2 — doktor ({doktor or 'bilinmiyor'}) endokrinoloji/iç hastalıkları değil, rapor gerekli"

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Metformin/sülfonilüre glisemik kontrol ibaresi bulundu',
            detaylar={'aranan': 'metformin + sülfonilüre + glisemik', 'bulundu': True,
                      'doktor_uygun': doktor_uygun_sglt2 if sglt2_mi else None},
            uyari=uyari_brans if uyari_brans else None,
            sut_kurali=sut_kurali if sglt2_mi else 'SUT 4.2.38 — Metformin/sülfonilüre maks dozda glisemik kontrol sağlanamamış olmalı',
            aranan_ibare='metformin + sülfonilüre + glisemik kontrol / HbA1c',
            bulunan_metin=eslesen
        )
    else:
        # Raporsuz SGLT2/DPP4/GLP1 ilaçları → teşhise bağlı kontrol
        ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
        rapor_kodu = ilac_sonuc.get('rapor_kodu', '')

        # SGLT2 ilaçları (empagliflozin, dapagliflozin) — kalp yetmezliği veya KBH
        # endikasyonunda raporsuz yazılabilir
        sglt2_ilaclar = ['JARDIANCE', 'FORZIGA', 'INVOKANA', 'STEGLATRO',
            'EMPAGLIFLOZIN', 'DAPAGLIFLOZIN', 'KANAGLIFLOZIN', 'ERTUGLIFLOZIN']
        sglt2_mi = any(k in ilac_adi for k in sglt2_ilaclar)

        # DPP-4 ve GLP-1 ilaçları (bunlar her durumda rapor gerektirir)
        dpp4_glp1 = any(k in ilac_adi for k in ['DPP4', 'DPP-4', 'GLP-1', 'GLP1',
            'JANUVIA', 'GALVUS', 'ONGLYZA', 'TRAJENTA', 'NESINA',
            'OZEMPIC', 'TRULICITY', 'VICTOZA', 'BYETTA',
            'SITAGLIPTIN', 'VILDAGLIPTIN', 'SAKSAGLIPTIN', 'LINAGLIPTIN', 'ALOGLIPTIN',
            'LIRAGLUTID', 'SEMAGLUTID', 'DULAGLUTID', 'EKSENATID'])
        metformin = 'METFORMIN' in ilac_adi or 'GLUKOFEN' in ilac_adi or 'DIAFORMIN' in ilac_adi or 'GLIFOR' in ilac_adi

        if sglt2_mi and not rapor_kodu:
            # SGLT2 raporsuz — 2 durum:
            # A) Diyabet endikasyonunda: endokrinoloji/iç hastalıkları uzmanı raporsuz yazabilir
            # B) Kalp yetmezliği/KBH endikasyonunda: raporsuz yazılabilir (farklı endikasyon)
            teshisler = (ilac_sonuc.get('recete_teshisleri') or [])
            teshis_metin_sglt2 = ' '.join(teshisler).upper()
            tum = tum_metin.upper() if tum_metin else ''

            kalp_yetmezligi = any(k in teshis_metin_sglt2 or k in tum for k in [
                'I50', 'KALP YETMEZLİĞİ', 'KALP YETMEZLIGI', 'HEART FAILURE',
                'KARDİYOMİYOPATİ', 'KARDIYOMIYOPATI', 'HFrEF', 'HFpEF',
                'KALP YETERSİZLİĞİ', 'KALP YETERSIZLIGI',
            ])
            kbh = any(k in teshis_metin_sglt2 or k in tum for k in [
                'N18', 'KRONİK BÖBREK', 'KRONIK BOBREK', 'CKD',
                'BÖBREK YETMEZLİĞİ', 'BOBREK YETMEZLIGI', 'BÖBREK YETERSİZLİĞİ',
                'RENAL YETMEZLİK', 'RENAL YETMEZLIK',
            ])

            if kalp_yetmezligi:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj='SGLT2 — kalp yetmezliği endikasyonu (raporsuz yazılabilir)',
                    detaylar={'endikasyon': 'kalp_yetmezligi', 'teshisler': teshisler},
                    sut_kurali='SGLT2 kalp yetmezliği endikasyonunda rapor gerekmez',
                    aranan_ibare='I50 / kalp yetmezliği teşhisi')
            elif kbh:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj='SGLT2 — kronik böbrek hastalığı endikasyonu (raporsuz yazılabilir)',
                    detaylar={'endikasyon': 'kbh', 'teshisler': teshisler},
                    sut_kurali='SGLT2 KBH endikasyonunda rapor gerekmez',
                    aranan_ibare='N18 / kronik böbrek hastalığı teşhisi')
            elif doktor_uygun_sglt2:
                # Diyabet endikasyonu — endokrinoloji/iç hastalıkları uzmanı raporsuz yazabilir
                brans = 'endokrinoloji' if doktor_endokrin else 'iç hastalıkları'
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'SGLT2 — {brans} uzmanı tarafından yazılmış (raporsuz yazılabilir)',
                    detaylar={'endikasyon': 'diyabet', 'doktor': doktor, 'teshisler': teshisler},
                    sut_kurali=sut_kurali,
                    aranan_ibare=f'Doktor: endokrinoloji/iç hastalıkları uzmanı',
                    bulunan_metin=f'Doktor: {doktor}')
            else:
                # Diyabet endikasyonu + doktor uygun değil → rapor gerekli
                return KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj=f'SGLT2 raporsuz — doktor ({doktor or "bilinmiyor"}) endokrinoloji/iç hastalıkları değil',
                    uyari='SUT 4.2.38(6): SGLT2 diyabet endikasyonunda endokrinoloji veya iç hastalıkları uzmanı yazabilir veya raporu gerekli',
                    detaylar={'teshisler': teshisler, 'doktor': doktor},
                    sut_kurali=sut_kurali,
                    aranan_ibare='Endokrinoloji/iç hastalıkları uzmanı veya raporu')

        if dpp4_glp1 and not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='DPP-4/GLP-1 ilacı RAPORSUZ yazılmış! Rapor ZORUNLU',
                uyari='SUT 4.2.38 - Bu ilaç raporsuz verilemez'
            )
        if metformin and not rapor_kodu:
            # Metformin raporsuz verilebilir
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='Metformin raporsuz verilebilir',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Glisemik kontrol ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'metformin + sülfonilüre', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: Metformin ve sülfonilüre yetersiz glisemik yanıt ibaresi raporda olmalı'
        )


def kontrol_klopidogrel(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.15 - Klopidogrel / Prasugrel / Tikagrelor Kontrol

    Endikasyonlar:
    A) Koroner stent (max 12 ay)
    B) AKS (STEMI/NSTEMI/unstabil angina)
    C) Anjiografik koroner arter hastalığı (ASA intoleransı şartıyla)
    D) Tıkayıcı periferik arter hastalığı (ASA intoleransı şartıyla)
    E) İskemik inme (ASA intoleransı şartıyla)
    F) Kalp kapak biyoprotezi (ASA intoleransı şartıyla)

    Kombine kullanım yasağı: klopidogrel+prasugrel+tikagrelor+YOAK birlikte KARŞILANMAZ
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''

    birlesik = (tum_metin or '') + ' ' + teshis_metin
    metin_lower = _turkce_normalize(birlesik) if birlesik else ''

    sut_kurali = 'SUT 4.2.15 — Klopidogrel/Prasugrel/Tikagrelor kullanım kuralları'
    detaylar = {'ilac_adi': ilac_adi, 'rapor_kodu': rapor_kodu}

    # ── 1. Endikasyon tespiti ──
    endikasyonlar = []
    eslesen_metinler = []

    # Stent
    stent_var = 'stent' in metin_lower
    if stent_var:
        endikasyonlar.append('Koroner stent')
        eslesen_metinler.append(_eslesen_parcayi_bul(birlesik, 'stent'))

    # AKS / MI
    aks_var = any(k in metin_lower for k in ['akut koroner', 'aks', 'stemi', 'nstemi',
                                              'unstabil angina', 'unstable angina'])
    mi_var = any(k in metin_lower for k in ['miyokard', 'infarktusu', 'infarktus'])
    if aks_var or mi_var:
        endikasyonlar.append('AKS/MI')
        for k in ['akut koroner', 'stemi', 'nstemi', 'miyokard']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen_metinler.append(p)
                break

    # Raporda "12 ay klopidogrel kullanımı uygundur" → stent/AKS sonrası onay
    klopidogrel_onay = any(k in metin_lower for k in [
        'klopidogrel kullanimi uygundur', 'clopidogrel kullanimi uygundur',
        '12 ay klopidogrel', '12 ay clopidogrel',
    ])
    if klopidogrel_onay and not stent_var and not aks_var and not mi_var:
        endikasyonlar.append('Doktor onayı (12 ay)')
        eslesen_metinler.append(_eslesen_parcayi_bul(birlesik, 'klopidogrel') or
                                _eslesen_parcayi_bul(birlesik, 'clopidogrel') or '')

    # Anjiografi / KAH (çeşitli yazımlar: anjio/angio/anjiyo/angyo)
    anjio_var = any(k in metin_lower for k in ['anjio', 'angio', 'anjiyo', 'angyo', 'angiyo'])
    kah_var = any(k in metin_lower for k in ['koroner arter', 'iskemik kalp'])
    bypass_var = any(k in metin_lower for k in ['bypass', 'kabg'])
    perkutan_var = any(k in metin_lower for k in ['perkutan', 'pkag', 'ptca'])
    if anjio_var or kah_var or bypass_var or perkutan_var:
        endikasyonlar.append('KAH/Anjiografi')
        for k in ['anjio', 'koroner arter', 'bypass', 'kabg', 'perkütan']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen_metinler.append(p)
                break

    # İskemik inme
    inme_var = any(k in metin_lower for k in ['iskemik inme', 'serebral iskemi',
                                               'serebrovasküler', 'serebrovaskuler', 'tia'])
    icd_inme = any(k in teshis_metin for k in ['I63', 'I64', 'I65', 'I66', 'G45', 'G46'])
    if inme_var or icd_inme:
        endikasyonlar.append('İskemik inme')
        for k in ['inme', 'serebral', 'serebrovas']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen_metinler.append(p)
                break

    # Periferik arter
    pah_var = any(k in metin_lower for k in ['periferik arter', 'tıkayıcı', 'tikayici',
                                              'kladikasyo', 'intermittan'])
    icd_pah = any(k in teshis_metin for k in ['I70', 'I73', 'I74'])
    if pah_var or icd_pah:
        endikasyonlar.append('Periferik arter')
        for k in ['periferik arter', 'tıkayıcı', 'tikayici']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen_metinler.append(p)
                break

    # ICD kodları ile ek kontrol
    icd_kah = any(k in teshis_metin for k in ['I20', 'I21', 'I22', 'I23', 'I24', 'I25'])
    if icd_kah and 'KAH/Anjiografi' not in endikasyonlar:
        endikasyonlar.append('KAH (ICD)')

    # ── 2. ASA intoleransı kontrolü ──
    asa_intolerans = any(k in metin_lower for k in ['asa intolerans', 'aspirin intolerans',
                                                     'aspirin kontrendik', 'asetilsalisilik intolerans',
                                                     'gastrointestinal intolerans',
                                                     'aspirin allerjisi', 'asa allerjisi'])
    # ASA gerektiren endikasyonlar (stent, AKS ve doktor onayı hariç)
    asa_gereken = any(e in endikasyonlar for e in ['İskemik inme', 'Periferik arter', 'KAH/Anjiografi', 'KAH (ICD)'])
    asa_gereksiz = any(e in endikasyonlar for e in ['Koroner stent', 'AKS/MI', 'Doktor onayı (12 ay)'])

    # ── 3. Tarih bilgisi ──
    tarih_match = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', birlesik)
    tarih_str = f" | Tarih: {', '.join(tarih_match[:2])}" if tarih_match else ""

    detaylar['endikasyonlar'] = endikasyonlar
    detaylar['asa_intolerans'] = asa_intolerans
    detaylar['tarihler'] = tarih_match[:3] if tarih_match else []

    eslesen_birlesik = eslesen_metinler[0] if eslesen_metinler else ""

    # ── 4. Sonuç ──
    if not endikasyonlar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Stent/AKS/anjiografi/inme/periferik arter ibaresi bulunamadı',
            detaylar=detaylar,
            uyari='RAPOR KONTROLÜ GEREKLİ: Endikasyon raporda belirtilmeli',
            sut_kurali=sut_kurali,
            aranan_ibare='stent / AKS / anjiografi / koroner arter / iskemik inme / periferik arter'
        )

    # Stent veya AKS → ASA intoleransı gerekmez
    if asa_gereksiz:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f"Endikasyon: {', '.join(endikasyonlar)}{tarih_str}",
            detaylar=detaylar,
            uyari='Stent sonrası max 12 ay kullanım' if stent_var else None,
            sut_kurali=sut_kurali,
            aranan_ibare='stent / AKS / MI',
            bulunan_metin=eslesen_birlesik
        )

    # KAH/inme/PAH → ASA intoleransı gerekli
    if asa_gereken:
        if asa_intolerans:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f"Endikasyon: {', '.join(endikasyonlar)} + ASA intoleransı mevcut{tarih_str}",
                detaylar=detaylar,
                sut_kurali=sut_kurali,
                aranan_ibare='endikasyon + ASA intoleransı',
                bulunan_metin=eslesen_birlesik
            )
        else:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f"Endikasyon: {', '.join(endikasyonlar)} ama ASA intoleransı ibaresi bulunamadı",
                detaylar=detaylar,
                uyari='SUT 4.2.15: KAH/inme/PAH endikasyonunda raporda ASA intoleransı belirtilmeli',
                sut_kurali=sut_kurali,
                aranan_ibare='ASA/aspirin intoleransı / gastrointestinal intolerans',
                bulunan_metin=eslesen_birlesik
            )

    # Genel endikasyon bulundu
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=f"Endikasyon: {', '.join(endikasyonlar)}{tarih_str}",
        detaylar=detaylar,
        sut_kurali=sut_kurali,
        aranan_ibare='stent / AKS / anjiografi / koroner arter',
        bulunan_metin=eslesen_birlesik
    )


def kontrol_statin(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.28.A - Statin Kontrol

    SUT kuralları:
    1. LDL eşik değerleri (risk kategorisine göre):
       - LDL > 190: Ek risk faktörü gerekmez
       - LDL > 160: 2 ek risk faktörü gerekli
       - LDL > 130: 3 ek risk faktörü gerekli
       - LDL > 70 : DM, AKS, MI, inme, KAH, PAH, AAA, karotid arter hastalığı
    2. İlk başlangıçta 6 ay içinde en az 1 hafta arayla 2 lipid ölçümü
    3. Yüksek doz statin: Kardiyoloji/KDC/Endokrinoloji/Geriatri raporu gerekli
    4. Rapor süresi: max 2 yıl
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''

    # Tüm metinleri birleştir (rapor + reçete teşhis)
    birlesik_metin = (tum_metin or '') + ' ' + teshis_metin

    detaylar = {
        'ilac_adi': ilac_adi,
        'rapor_kodu': rapor_kodu,
        'ldl_degeri': None,
        'risk_kategorisi': None,
        'yuksek_doz': False,
    }

    metin_lower = birlesik_metin.replace('İ', 'i').replace('I', 'ı').lower() if birlesik_metin else ''

    # ── 1. LDL değeri ara ──
    ldl_degeri = None
    ldl_eslesen = ""

    # Çeşitli LDL formatları: "LDL: 142", "LDL=142", "LDL 142", "LDL-C: 142",
    # "LDL kolesterol: 142", "LDL Kolesterol (İndirekt, hesaplamalı) 112.8"
    ldl_patterns = [
        r'ldl[- ]*c?\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        r'ldl[^0-9]{0,50}(\d{2,3}(?:[.,]\d+)?)',
    ]
    for pattern in ldl_patterns:
        ldl_match = re.findall(pattern, metin_lower)
        if ldl_match:
            try:
                ldl_degeri = int(float(ldl_match[0].replace(',', '.')))
                ldl_eslesen = _eslesen_parcayi_bul(birlesik_metin, 'ldl')
                break
            except ValueError:
                pass

    # Kolesterol genel ibare (LDL bulunamazsa)
    ldl_var = ldl_degeri is not None
    kolesterol_var = 'kolesterol' in metin_lower or 'kolestrol' in metin_lower
    lipid_var = 'lipid' in metin_lower or 'hiperlipidemi' in metin_lower
    dislipidemi_var = 'dislipidemi' in metin_lower or 'hiperlipidemi' in metin_lower

    detaylar['ldl_degeri'] = ldl_degeri

    # ── 2. Risk faktörleri ara ──
    risk_faktorleri = []

    # Yüksek risk grubu (LDL > 70 yeterli)
    dm_var = any(k in metin_lower for k in ['diyabet', 'diabetes', 'dm ', 'tip 2', 'tip2'])
    aks_var = any(k in metin_lower for k in ['akut koroner', 'aks ', 'aks,'])
    mi_var = any(k in metin_lower for k in ['miyokard', 'infarktüs', 'infarktusu', 'mi ', 'stemi', 'nstemi'])
    inme_var = any(k in metin_lower for k in ['inme', 'stroke', 'serebrovasküler', 'sva '])
    kah_var = any(k in metin_lower for k in ['koroner arter', 'kah ', 'kah,', 'iskemik kalp'])
    pah_var = any(k in metin_lower for k in ['periferik arter', 'pah ', 'pah,'])
    aaa_var = any(k in metin_lower for k in ['aort anevrizma', 'aaa '])
    karotid_var = any(k in metin_lower for k in ['karotid', 'karotis'])
    stent_var = 'stent' in metin_lower
    bypass_var = any(k in metin_lower for k in ['bypass', 'kabg'])

    # ICD kodları ile de kontrol et
    icd_dm = any(k in teshis_metin for k in ['E10', 'E11', 'E12', 'E13', 'E14'])
    icd_kah = any(k in teshis_metin for k in ['I20', 'I21', 'I22', 'I23', 'I24', 'I25'])
    icd_inme = any(k in teshis_metin for k in ['I60', 'I61', 'I62', 'I63', 'I64', 'I65', 'I66'])
    icd_pah = any(k in teshis_metin for k in ['I70', 'I73', 'I74'])
    icd_lipid = any(k in teshis_metin for k in ['E78', 'E78.0', 'E78.1', 'E78.2', 'E78.5'])

    if dm_var or icd_dm:
        risk_faktorleri.append('DM')
    if aks_var or mi_var or stent_var or bypass_var:
        risk_faktorleri.append('AKS/MI')
    if kah_var or icd_kah:
        risk_faktorleri.append('KAH')
    if inme_var or icd_inme:
        risk_faktorleri.append('İnme')
    if pah_var or icd_pah:
        risk_faktorleri.append('PAH')
    if aaa_var:
        risk_faktorleri.append('AAA')
    if karotid_var:
        risk_faktorleri.append('Karotid')

    cok_yuksek_risk = len(risk_faktorleri) > 0  # DM/AKS/MI/inme/KAH/PAH/AAA/karotid
    detaylar['risk_kategorisi'] = ', '.join(risk_faktorleri) if risk_faktorleri else 'Genel'
    detaylar['risk_faktorleri'] = risk_faktorleri

    # ── 3. Yüksek doz statin kontrolü ──
    yuksek_doz_ilaclar = {
        'ROSUVASTATIN': 20, 'CRESTOR': 20, 'ROZACT': 20, 'ROSUVA': 20,
        'ATORVASTATIN': 40, 'LIPITOR': 40, 'ATOR': 40,
        'SIMVASTATIN': 40, 'PRAVASTATIN': 40, 'FLUVASTATIN': 80,
    }
    ilac_dozaj = _ilac_adından_dozaj_cikar(ilac_adi) if '_ilac_adından_dozaj_cikar' in dir() else None
    # Basit dozaj çıkarma
    doz_match = re.search(r'(\d+)\s*MG', ilac_adi)
    ilac_mg = int(doz_match.group(1)) if doz_match else None

    for ilac_kisa, esik_doz in yuksek_doz_ilaclar.items():
        if ilac_kisa in ilac_adi and ilac_mg and ilac_mg >= esik_doz:
            detaylar['yuksek_doz'] = True
            break

    # ── 4. Sonuç değerlendirme ──
    sut_kurali = 'SUT 4.2.28.A — Statin kullanım kuralları'

    # LDL değeri bulundu
    if ldl_var and ldl_degeri:
        # Risk bazlı eşik kontrolü
        if cok_yuksek_risk and ldl_degeri > 70:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 70 mg/dL (risk: {', '.join(risk_faktorleri)})"
        elif ldl_degeri > 190:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 190 mg/dL (ek risk faktörü gerekmez)"
        elif ldl_degeri > 160:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 160 mg/dL (2 risk faktörü gerekli)"
        elif ldl_degeri > 130:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 130 mg/dL (3 risk faktörü gerekli)"
        elif ldl_degeri > 70 and cok_yuksek_risk:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 70 mg/dL (yüksek risk: {', '.join(risk_faktorleri)})"
        elif ldl_degeri <= 70:
            uygunluk = "ŞÜPHELI"
            aciklama = f"LDL {ldl_degeri} ≤ 70 mg/dL — statin endikasyonu sorgulanmalı"
        else:
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} mg/dL raporda mevcut"

        # Yüksek doz uyarısı
        uyari_mesaj = ""
        if detaylar['yuksek_doz']:
            uyari_mesaj = "YÜKSEK DOZ — Kardiyoloji/KDC/Endokrinoloji/Geriatri raporu gerekli"

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN if uygunluk == "UYGUN" else KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=aciklama,
            detaylar=detaylar,
            uyari=uyari_mesaj if uyari_mesaj else None,
            sut_kurali=sut_kurali,
            aranan_ibare=f"LDL değeri + risk faktörleri ({', '.join(risk_faktorleri) if risk_faktorleri else 'yok'})",
            bulunan_metin=ldl_eslesen
        )

    # LDL değeri yok ama kolesterol/lipid/dislipidemi ibaresi var
    if kolesterol_var or lipid_var or dislipidemi_var or icd_lipid:
        eslesen_k = 'kolesterol' if kolesterol_var else ('lipid' if lipid_var else 'dislipidemi')
        eslesen = _eslesen_parcayi_bul(birlesik_metin, eslesen_k)
        risk_bilgi = f" | Risk: {', '.join(risk_faktorleri)}" if risk_faktorleri else ""
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Kolesterol/lipid ibaresi var ama LDL sayısal değeri bulunamadı{risk_bilgi}',
            detaylar=detaylar,
            uyari='LDL sayısal değeri raporda belirtilmeli (ör: LDL: 142 mg/dL)',
            sut_kurali=sut_kurali,
            aranan_ibare='LDL sayısal değeri (mg/dL)',
            bulunan_metin=eslesen
        )

    # Hiçbir lipid ibaresi yok — rapor kodundan kontrol
    if rapor_kodu and rapor_kodu.startswith('04.08'):
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Rapor kodu {rapor_kodu} (lipid düşürücü) ama LDL/kolesterol ibaresi bulunamadı',
            detaylar=detaylar,
            uyari='Raporda LDL değeri olmalı — manuel kontrol gerekli',
            sut_kurali=sut_kurali,
            aranan_ibare='LDL değeri / kolesterol / lipid / dislipidemi'
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='LDL/kolesterol ibaresi mesaj metninde bulunamadı',
        detaylar=detaylar,
        uyari='RAPOR KONTROLÜ GEREKLİ: LDL düzeyi raporda olmalı',
        sut_kurali=sut_kurali,
        aranan_ibare='LDL değeri / kolesterol / hiperlipidemi / dislipidemi'
    )


def kontrol_fibrat(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.28.B - Fibrat Kontrol (Fenofibrat/Gemfibrozil)

    SUT kuralları:
    - Trigliserid ≥ 500 mg/dL → ek risk faktörü gerekmez
    - Trigliserid ≥ 200 mg/dL + DM/KAH/PAH/MI/İnme → yeterli
    - Raporda en az 1 hafta arayla 2 trigliserid ölçümü (6 ay içinde)
    - Diyet sonrası değer belirtilmeli
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (tum_metin or '') + ' ' + teshis_metin
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower() if birlesik else ''

    sut_kurali = 'SUT 4.2.28.B — Fibrat: Trigliserid düzeyi raporda belirtilmiş olmalı'
    detaylar = {'tg_degeri': None, 'risk_faktorleri': []}

    # ── 1. Trigliserid değeri ara ──
    tg_degeri = None
    tg_eslesen = ""
    tg_patterns = [
        r'(?:trigliserid|trigliserit|triglyceri)[^0-9]{0,20}(\d{2,4})',
        r'tg\s*[:=]?\s*(\d{2,4})',
    ]
    for pattern in tg_patterns:
        tg_match = re.findall(pattern, metin_lower)
        if tg_match:
            try:
                tg_degeri = int(tg_match[0])
                for k in ['trigliserid', 'trigliserit', 'tg']:
                    p = _eslesen_parcayi_bul(birlesik, k)
                    if p:
                        tg_eslesen = p
                        break
                break
            except ValueError:
                pass

    tg_var = tg_degeri is not None
    tg_ibare = any(k in metin_lower for k in ['trigliserid', 'trigliserit', 'triglyceri', 'tg ', 'tg:', 'tg='])
    detaylar['tg_degeri'] = tg_degeri

    # ── 2. Risk faktörleri ──
    risk = []
    if any(k in metin_lower for k in ['diyabet', 'diabetes', 'dm ']) or any(k in teshis_metin for k in ['E10', 'E11', 'E14']):
        risk.append('DM')
    if any(k in metin_lower for k in ['koroner', 'kah ', 'iskemik kalp']) or any(k in teshis_metin for k in ['I20', 'I25']):
        risk.append('KAH')
    if any(k in metin_lower for k in ['periferik arter', 'pah ']) or any(k in teshis_metin for k in ['I70', 'I73']):
        risk.append('PAH')
    if any(k in metin_lower for k in ['miyokard', 'infarktüs', 'mi ']):
        risk.append('MI')
    if any(k in metin_lower for k in ['inme', 'stroke', 'serebrovas']) or any(k in teshis_metin for k in ['I63', 'I64']):
        risk.append('İnme')
    if any(k in metin_lower for k in ['pankreatit', 'pankreas']):
        risk.append('Pankreatit riski')
    detaylar['risk_faktorleri'] = risk

    # ── 3. Sonuç ──
    if tg_var and tg_degeri:
        if tg_degeri >= 500:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'TG {tg_degeri} ≥ 500 mg/dL (ek risk gerekmez)',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='Trigliserid ≥ 500 mg/dL',
                bulunan_metin=tg_eslesen
            )
        elif tg_degeri >= 200 and risk:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'TG {tg_degeri} ≥ 200 mg/dL + risk: {", ".join(risk)}',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare=f'Trigliserid ≥ 200 + risk ({", ".join(risk)})',
                bulunan_metin=tg_eslesen
            )
        elif tg_degeri >= 200:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'TG {tg_degeri} ≥ 200 mg/dL ama risk faktörü tespit edilemedi',
                detaylar=detaylar, sut_kurali=sut_kurali,
                uyari='TG 200-499 arasında DM/KAH/PAH/MI/İnme risk faktörü gerekli',
                aranan_ibare='Trigliserid ≥ 200 + risk faktörü',
                bulunan_metin=tg_eslesen
            )
        else:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=f'TG {tg_degeri} < 200 mg/dL — fibrat endikasyonu yok',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='Trigliserid ≥ 200 veya ≥ 500 mg/dL',
                bulunan_metin=tg_eslesen
            )

    if tg_ibare:
        eslesen = _eslesen_parcayi_bul(birlesik, 'trigliserid') or _eslesen_parcayi_bul(birlesik, 'tg')
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Trigliserid ibaresi var ama sayısal değer bulunamadı',
            detaylar=detaylar, sut_kurali=sut_kurali,
            uyari='Raporda TG sayısal değeri olmalı (ör: TG: 520 mg/dL)',
            aranan_ibare='Trigliserid sayısal değeri',
            bulunan_metin=eslesen
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='Trigliserid ibaresi mesaj metninde bulunamadı',
        detaylar=detaylar, sut_kurali=sut_kurali,
        uyari='RAPOR KONTROLÜ GEREKLİ: Trigliserid düzeyi raporda olmalı',
        aranan_ibare='trigliserid / TG'
    )


# ═══════════════════════════════════════════════════════════════════════
# Ana Kontrol Fonksiyonu
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# YENİ KONTROL FONKSİYONLARI (2026-04-05 eklendi)
# ═══════════════════════════════════════════════════════════════════════

def kontrol_yoak(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.15.D - YOAK (Rivaroksaban/Apiksaban/Edoksaban/Dabigatran) Kontrol

    Kurallar:
    1. Non-valvüler AF'de: Varfarin denenmiş + INR takibi yapılamıyor/kontrendike
       VEYA INR hedef aralıkta tutulamıyor
    2. DVT/PE tedavisi: Doğrudan başlanabilir (varfarin şartı yok)
    3. Ortopedik cerrahi profilaksisi: Doğrudan (kısa süreli)
    4. Kanser ilişkili tromboz: Doğrudan
    5. Kombine kullanım yasak: YOAK + klopidogrel/prasugrel/tikagrelor KARŞILANMAZ
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower() if birlesik else ''

    sut_kurali = 'SUT 4.2.15.D — YOAK kullanım kuralları'
    detaylar = {'endikasyon': None, 'varfarin_bilgi': False}

    if not metin_lower:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok", sut_kurali=sut_kurali,
                             aranan_ibare='AF / DVT / PE / varfarin / INR')

    # Endikasyonlar
    varfarin = bool(re.search(r'varfarin|kumadin|coumadin|warfarin', metin_lower))
    inr = bool(re.search(r'[iı]nr', metin_lower))
    af = any(k in metin_lower for k in ['atriyal fibrilasyon', 'atrial fibrilasyon', 'atriyal fib',
                                         'a.fibrilasyon', 'a.fib']) or 'I48' in teshis_metin
    dvt = any(k in metin_lower for k in ['derin ven', 'dvt', 'derin venöz'])
    pe = any(k in metin_lower for k in ['pulmoner emboli', 'pulmoner tromboz', 'pe ']) or 'I26' in teshis_metin
    kanser = any(k in metin_lower for k in ['kanser', 'malign', 'tümör', 'onkoloji', 'metastaz'])
    ortopedik = any(k in metin_lower for k in ['protez', 'artroplasti', 'ortopedik'])
    icd_af = 'I48' in teshis_metin
    icd_dvt = any(k in teshis_metin for k in ['I80', 'I82'])
    icd_pe = 'I26' in teshis_metin

    # INR kontrolü
    inr_degeri = None
    inr_match = re.findall(r'[iı]nr\s*[:=]?\s*([\d,.]+)', metin_lower)
    if inr_match:
        try:
            inr_degeri = float(inr_match[0].replace(',', '.'))
        except:
            pass
    # INR aralık ifadesi: "INR değerinin 2-3 arasında tutulamadığından" vb.
    if not inr_match:
        inr_aralik = re.findall(r'[iı]nr[^0-9]{0,30}(\d)[- ]+(\d)', metin_lower)
        if inr_aralik:
            inr_match = inr_aralik  # inr boolean zaten True, sayısal değer aralık olarak mevcut

    # INR "tutulamadı/tutulamıyor" ifadesi — SUT şartı karşılanmış demek
    inr_tutulamadi = bool(re.search(r'[iı]nr[^.]{0,60}(tutulam|saglanam|sa[gğ]lanam)', metin_lower))

    # Sonuç
    eslesen = ""

    # DVT/PE → varfarin şartı yok
    if dvt or pe or icd_dvt or icd_pe:
        for k in ['derin ven', 'dvt', 'pulmoner emboli', 'pe']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen = p
                break
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'DVT/PE endikasyonu — varfarin şartı aranmaz',
            detaylar={**detaylar, 'endikasyon': 'DVT/PE'},
            sut_kurali=sut_kurali,
            aranan_ibare='DVT / pulmoner emboli',
            bulunan_metin=eslesen
        )

    # Kanser ilişkili tromboz
    if kanser:
        eslesen = _eslesen_parcayi_bul(birlesik, 'kanser') or _eslesen_parcayi_bul(birlesik, 'malign')
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Kanser ilişkili tromboz — doğrudan YOAK',
            detaylar={**detaylar, 'endikasyon': 'Kanser'},
            sut_kurali=sut_kurali,
            aranan_ibare='kanser / malignite + tromboz',
            bulunan_metin=eslesen
        )

    # AF + varfarin/INR
    if af or icd_af:
        eslesen = _eslesen_parcayi_bul(birlesik, 'fibrilasyon') or _eslesen_parcayi_bul(birlesik, 'I48')
        if varfarin and (inr or inr_tutulamadi):
            inr_bilgi = f" (INR: {inr_degeri})" if inr_degeri else ""
            tutulamadi_bilgi = " — INR hedef aralıkta tutulamadığı belirtilmiş" if inr_tutulamadi else ""
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'AF + varfarin denenmiş + INR bilgisi mevcut{inr_bilgi}{tutulamadi_bilgi}',
                detaylar={**detaylar, 'endikasyon': 'AF', 'varfarin_bilgi': True, 'inr': inr_degeri,
                          'inr_tutulamadi': inr_tutulamadi},
                sut_kurali=sut_kurali,
                aranan_ibare='AF + varfarin + INR',
                bulunan_metin=eslesen
            )
        elif varfarin:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='AF + varfarin var ama INR bilgisi bulunamadı',
                detaylar={**detaylar, 'endikasyon': 'AF'},
                uyari='INR hedef aralıkta tutulamadığı raporda belirtilmeli',
                sut_kurali=sut_kurali,
                aranan_ibare='INR değeri / INR kontrolü yapılamıyor ibaresi',
                bulunan_metin=eslesen
            )
        else:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='AF tanısı var ama varfarin bilgisi raporda bulunamadı',
                detaylar={**detaylar, 'endikasyon': 'AF'},
                uyari='SUT: AF\'de YOAK için önce varfarin denenmiş olmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='varfarin + INR',
                bulunan_metin=eslesen
            )

    # Ortopedik profilaksi
    if ortopedik:
        eslesen = _eslesen_parcayi_bul(birlesik, 'protez') or _eslesen_parcayi_bul(birlesik, 'artroplasti')
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Ortopedik cerrahi profilaksisi',
            detaylar={**detaylar, 'endikasyon': 'Ortopedik'},
            sut_kurali=sut_kurali,
            aranan_ibare='ortopedik cerrahi / protez / artroplasti',
            bulunan_metin=eslesen
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='YOAK endikasyonu tespit edilemedi (AF/DVT/PE/kanser)',
        sut_kurali=sut_kurali,
        aranan_ibare='AF / DVT / PE / kanser / ortopedik cerrahi / varfarin + INR'
    )


def kontrol_bifosfonat(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.17 - Bifosfonat (Alendronat/Fosavance/Fosamax/Risedronat/İbandronat/Zoledronat)

    T-skoru eşikleri:
    - Patolojik kırığı OLAN: T ≤ -1
    - 65 yaş üstü kırıksız: T ≤ -2.5
    - 65 yaş altı kırıksız: T ≤ -3
    - Sekonder osteoporoz (kortikosteroid): T ≤ -1
    - 75 yaş üstü VEYA kalça kırığı: KMY gerekmez
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower() if birlesik else ''

    sut_kurali = 'SUT 4.2.17 — Bifosfonat: DEXA T-skoru raporda belirtilmiş olmalı'
    detaylar = {'t_skoru': None, 'kirik': False, 'kortikosteroid': False}

    if not metin_lower:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok", sut_kurali=sut_kurali,
                             aranan_ibare='T-skoru / osteoporoz / DEXA / kırık')

    # ── 1. T-skoru ara ──
    t_skoru = None
    t_eslesen = ""
    # Formatlar: "T: -2.8", "T=-2,8", "T skoru: -3.1", "T-score: -2.5"
    t_patterns = [
        r't[- ]*(?:skor|score|değer)[^0-9\-]*(-?\d+[.,]\d+)',
        r't\s*[:=]\s*(-?\d+[.,]\d+)',
        r'(-\d+[.,]\d+)\s*(?:sd|standart)',
    ]
    for pattern in t_patterns:
        t_match = re.findall(pattern, metin_lower)
        if t_match:
            try:
                t_skoru = float(t_match[0].replace(',', '.'))
                t_eslesen = _eslesen_parcayi_bul(birlesik, str(t_match[0]))
                break
            except:
                pass

    detaylar['t_skoru'] = t_skoru

    # ── 2. Kırık bilgisi ──
    kirik = any(k in metin_lower for k in ['kırık', 'kirik', 'fraktür', 'fraktur', 'fracture',
                                            'vertebra komp', 'kompresyon'])
    kalca_kirigi = any(k in metin_lower for k in ['kalça kırığı', 'kalca kirigi', 'femur kırığı',
                                                   'femur boyun kırığı', 'hip fracture'])
    icd_kirik = any(k in teshis_metin for k in ['M80', 'M81', 'M82', 'S72', 'S32', 'S22'])
    kirik = kirik or kalca_kirigi or icd_kirik
    detaylar['kirik'] = kirik

    # ── 3. Kortikosteroid (sekonder osteoporoz) ──
    kortiko = any(k in metin_lower for k in ['kortikosteroid', 'kortizon', 'prednizolon',
                                              'metilprednizolon', 'deksametazon', 'steroid'])
    detaylar['kortikosteroid'] = kortiko

    # ── 4. Osteoporoz teşhisi ──
    osteoporoz = any(k in metin_lower for k in ['osteoporoz', 'osteopeni', 'kemik erimesi',
                                                 'kemik yoğunluğu', 'kmy', 'dexa', 'dxa'])
    icd_osteo = any(k in teshis_metin for k in ['M80', 'M81', 'M82', 'M85'])

    # ── 5. Sonuç değerlendirme ──

    # Kalça kırığı → KMY gerekmez
    if kalca_kirigi:
        eslesen = _eslesen_parcayi_bul(birlesik, 'kalça kırığı') or _eslesen_parcayi_bul(birlesik, 'femur')
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Osteoporotik kalça kırığı — KMY ölçümü gerekmez',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='kalça kırığı / femur kırığı',
            bulunan_metin=eslesen
        )

    # T-skoru bulundu → eşik kontrolü
    if t_skoru is not None:
        if kirik and t_skoru <= -1:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'T-skoru {t_skoru} ≤ -1 + kırık mevcut',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='T ≤ -1 + patolojik kırık',
                bulunan_metin=t_eslesen
            )
        if kortiko and t_skoru <= -1:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'T-skoru {t_skoru} ≤ -1 + kortikosteroid (sekonder osteoporoz)',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='T ≤ -1 + kortikosteroid kullanımı',
                bulunan_metin=t_eslesen
            )
        if t_skoru <= -3:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'T-skoru {t_skoru} ≤ -3 (65 yaş altı kırıksız eşik)',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='T ≤ -3',
                bulunan_metin=t_eslesen
            )
        if t_skoru <= -2.5:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'T-skoru {t_skoru} ≤ -2.5 (65 yaş üstü eşik)',
                detaylar=detaylar, sut_kurali=sut_kurali,
                aranan_ibare='T ≤ -2.5 (65 yaş üstü)',
                bulunan_metin=t_eslesen,
                uyari='65 yaş altı ise T ≤ -3 gerekli'
            )
        if t_skoru <= -1:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'T-skoru {t_skoru} — kırık veya kortikosteroid bilgisi gerekli',
                detaylar=detaylar, sut_kurali=sut_kurali,
                uyari='T -1 ile -2.5 arası: patolojik kırık veya sekonder osteoporoz şartı aranır',
                aranan_ibare='kırık / kortikosteroid kullanımı',
                bulunan_metin=t_eslesen
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'T-skoru {t_skoru} > -1 — bifosfonat endikasyonu yok',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='T ≤ -1 (en düşük eşik)',
            bulunan_metin=t_eslesen
        )

    # T-skoru yok ama osteoporoz/kırık ibaresi var
    if osteoporoz or icd_osteo or kirik:
        eslesen = ""
        for k in ['osteoporoz', 'kmy', 'dexa', 'kırık', 'kemik']:
            p = _eslesen_parcayi_bul(birlesik, k)
            if p:
                eslesen = p
                break
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Osteoporoz/kırık ibaresi var ama T-skoru sayısal değeri bulunamadı',
            detaylar=detaylar, sut_kurali=sut_kurali,
            uyari='Raporda DEXA T-skoru sayısal değeri olmalı (ör: T: -2.8)',
            aranan_ibare='T-skoru sayısal değeri',
            bulunan_metin=eslesen
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='Osteoporoz/T-skoru/kırık ibaresi bulunamadı',
        detaylar=detaylar, sut_kurali=sut_kurali,
        uyari='RAPOR KONTROLÜ GEREKLİ: DEXA T-skoru raporda olmalı',
        aranan_ibare='osteoporoz / T-skoru / DEXA / kırık'
    )


def kontrol_ivabradin(ilac_sonuc: Dict) -> KontrolRaporu:
    """İvabradin (4.2.15.C) / Eplerenon
    İvabradin: NYHA II-IV + sinüs ritmi VEYA beta blokör intoleransı VEYA EF≤%45
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)

    if not metin:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok")

    bb_intolerans = _turkce_ara(metin, 'beta blok') and (_turkce_ara(metin, 'intolerans') or _turkce_ara(metin, 'kontrendik'))
    kalp_yetmezligi = _turkce_ara(metin, 'kalp yetmezli') or _turkce_ara(metin, 'heart failure')
    angina = _turkce_ara(metin, 'angina') or _turkce_ara(metin, 'anjina')
    nyha = _turkce_ara(metin, 'NYHA')
    sinus = _turkce_ara(metin, 'sinüs ritm') or _turkce_ara(metin, 'sinus ritm')
    semptomatik = _turkce_ara(metin, 'semptomatik')
    stabil = _turkce_ara(metin, 'stabil')
    sistolik = _turkce_ara(metin, 'sistolik disfonksiyon')
    ef = re.search(r'EF\s*[≤<]?\s*%?\s*(\d+)', metin, re.IGNORECASE)

    if bb_intolerans:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Beta blokör intoleransı/kontrendikasyonu raporda mevcut")
    if ef:
        ef_deger = int(ef.group(1))
        if ef_deger <= 45:
            return KontrolRaporu(KontrolSonucu.UYGUN,
                                 f"EF={ef_deger}% (≤45%) - kalp yetmezliği endikasyonu")
    if nyha and sinus:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "NYHA sınıfı + sinüs ritmi raporda mevcut")
    if sistolik and nyha:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Sistolik disfonksiyon + NYHA raporda mevcut")
    if angina and semptomatik:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Angina pektoris + semptomatik tedavi raporda mevcut")
    if angina and stabil:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Kronik stabil angina raporda mevcut")
    if kalp_yetmezligi:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Kalp yetmezliği tanısı raporda mevcut",
                             uyari="EF değeri kontrol edilmeli")
    if angina:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Angina tanısı raporda mevcut",
                             uyari="Semptom durumu kontrol edilmeli")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "İvabradin/Ranolazin endikasyon koşulları tespit edilemedi")


def kontrol_ranolazin(ilac_sonuc: Dict) -> KontrolRaporu:
    """Ranolazin (SUT 4.2.15.F)

    Kronik stabil angina pektorisli hastaların semptomatik tedavisinde:
    - Beta blokör ve/veya verapamil-diltiazem tedavisine rağmen anjinası
      devam eden hastalarda, VEYA
    - Bu ilaçlara intoleransı ve/veya kontrendikasyonu olan hastalarda
    - Kardiyoloji uzmanı tarafından düzenlenen 1 yıl süreli uzman hekim raporu
    - Kardiyoloji veya iç hastalıkları uzmanı reçete edebilir
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')

    if not metin and not rapor_kodu:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok")

    detaylar = {}

    # ── Angina tanısı ──
    angina = _turkce_ara(metin, 'angina') or _turkce_ara(metin, 'anjina')
    stabil = _turkce_ara(metin, 'stabil') or _turkce_ara(metin, 'kronik')
    semptomatik = _turkce_ara(metin, 'semptomatik')

    # ── Beta blokör / Kalsiyum kanal blokörü durumu ──
    bb_kullanim = _turkce_ara(metin, 'beta blok')
    kkb_kullanim = _turkce_ara(metin, 'verapamil') or _turkce_ara(metin, 'diltiazem')
    onceki_tedavi = bb_kullanim or kkb_kullanim

    # İntolerans / kontrendikasyon
    intolerans = _turkce_ara(metin, 'intolerans') or _turkce_ara(metin, 'tolerans')
    kontrendikasyon = _turkce_ara(metin, 'kontrendik') or _turkce_ara(metin, 'kontraendik')
    yetersiz = (_turkce_ara(metin, 'yetersiz') or _turkce_ara(metin, 'cevaps')
                or _turkce_ara(metin, 'devam eden') or _turkce_ara(metin, 'ragmen'))

    detaylar['angina'] = angina
    detaylar['onceki_tedavi'] = onceki_tedavi
    detaylar['intolerans'] = intolerans or kontrendikasyon
    detaylar['yetersiz_yanit'] = yetersiz

    # ── Karar mantığı ──

    # Durum 1: BB/KKB intoleransı veya kontrendikasyonu
    if onceki_tedavi and (intolerans or kontrendikasyon):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Beta blokör/KKB intoleransı veya kontrendikasyonu raporda mevcut",
            detaylar=detaylar)

    # Durum 2: BB/KKB altında anjina devam ediyor
    if onceki_tedavi and yetersiz:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Önceki tedaviye rağmen anjina devam ettiği raporda belirtilmiş",
            detaylar=detaylar)

    # Durum 3: İntolerans/kontrendikasyon tek başına
    if intolerans or kontrendikasyon:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "İntolerans/kontrendikasyon raporda mevcut",
            detaylar=detaylar,
            uyari="Beta blokör veya verapamil/diltiazem belirtilmemiş, doğrulanmalı")

    # Durum 4: Kronik stabil angina + semptomatik
    if angina and (stabil or semptomatik):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Kronik stabil angina pektoris tanısı raporda mevcut",
            detaylar=detaylar,
            uyari="BB/KKB intoleransı veya yetersizliği ayrıca doğrulanmalı")

    # Durum 5: Sadece angina tanısı var
    if angina:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Angina tanısı raporda mevcut",
            detaylar=detaylar,
            uyari="Stabil angina ve BB/KKB durumu kontrol edilmeli")

    # Durum 6: Rapor kodu 04.02 var ama metin yetersiz
    if rapor_kodu and rapor_kodu.startswith('04.02'):
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            "Kardiyoloji raporu mevcut ancak angina/intolerans ibaresi bulunamadı",
            detaylar=detaylar,
            uyari="Rapor içeriği manuel kontrol edilmeli")

    return KontrolRaporu(
        KontrolSonucu.KONTROL_EDILEMEDI,
        "Ranolazin endikasyon koşulları tespit edilemedi (angina, BB/KKB intoleransı)",
        detaylar=detaylar)


def kontrol_psikiyatri(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Psikiyatri ilaçları (SUT 4.2.2) - Detaylı SUT kontrolleri.

    SUT Kuralları:
    1. RAPOR: Psikiyatri, nöroloji veya geriatri uzman raporu zorunlu
       - Rapor süresi: 1 yıl (yılda bir yenilenir)
       - İlk reçete: Uzman hekim yazmalı
       - Devam reçete: Rapor varsa tüm hekimler yazabilir
    2. ALT GRUPLAR:
       a) SSRI/SNRI (Essitalopram, Sertralin, Duloksetin vb.)
          - Psikiyatri/Nöroloji/Geriatri uzman raporu ile
          - Doz: Etkin maddeye göre maks doz kısıtlaması
       b) Antipsikotikler (Ketiapin, Olanzapin, Risperidon, Aripiprazol, Paliperidon)
          - Psikiyatri uzman raporu ZORUNLU
          - Nöroloji/geriatri de yazabilir ama psikiyatri tercih edilir
          - Depot formlar: Sadece psikiyatri
       c) Mood stabilizatörleri (Valproat, Lityum, Lamotrijin)
          - Psikiyatri/Nöroloji uzman raporu
       d) Benzodiazepin türevleri (Diazepam, Alprazolam, Lorazepam)
          - Yeşil reçete zorunlu
          - Rapor gerekmez ama uzun süreli kullanımda rapor istenir
    3. KOMBİNASYON KISITLAMALARI:
       - 2'den fazla antidepresan kombinasyonu dikkat gerektirir
       - Antipsikotik + antidepresan: uygun (augmentasyon)
       - MAO-İ + SSRI: kontrendike (serotonin sendromu)
    4. DOZ KISITLAMALARI (maks günlük dozlar):
       - Essitalopram: 20 mg (yaşlılarda 10 mg)
       - Sertralin: 200 mg
       - Fluoksetin: 80 mg
       - Paroksetin: 60 mg
       - Duloksetin: 120 mg
       - Venlafaksin: 375 mg
       - Ketiapin: 800 mg
       - Olanzapin: 20 mg
       - Risperidon: 16 mg
       - Aripiprazol: 30 mg
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper().strip()
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper().strip()
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''

    detaylar = {
        'etkin_madde': etkin_madde,
        'ilac_adi': ilac_adi,
        'rapor_kodu': rapor_kodu,
        'alt_grup': 'bilinmiyor',
    }

    # ── Alt grup tespiti ──
    ssri_maddeler = ['ESSITALOPRAM', 'SERTRALIN', 'FLUOKSETIN', 'PAROKSETIN',
                     'FLUVOKSAMIN', 'SITALOPRAM']
    snri_maddeler = ['DULOKSETIN', 'VENLAFAKSIN', 'MILNASIPRAN', 'DESVENLAFAKSIN']
    trisiklik_maddeler = ['AMITRIPTILIN', 'IMIPRAMIN', 'KLOMIPRAMIN', 'NORTRIPTILIN',
                          'DOKSEPIN', 'MAPROTILIN', 'OPIPRAMOL']
    atipik_ad_maddeler = ['TRAZODON', 'MIRTAZAPIN', 'BUPROPION', 'VORTIOKSETIN',
                          'AGOMELATINE', 'AGOMELATAIN', 'TIANEPTIN', 'MOKLOBEMID']
    antipsikotik_maddeler = ['KETIAPIN', 'OLANZAPIN', 'RISPERIDON', 'ARIPIPRAZOL',
                             'PALIPERIDON', 'KLOZAPIN', 'ZIPRASIDON', 'AMISÜLPRID',
                             'KARIPRAZIN', 'LURASIDON', 'HALOPERIDOL', 'KLORPROMAZIN',
                             'SÜLPIRID', 'ZUKLOPENTIKSOL', 'FLUFENAZIN', 'LEVOMEPROMAZIN']
    mood_stab_maddeler = ['VALPROIK', 'VALPROAT', 'LITYUM', 'LAMOTRIJIN',
                          'KARBAMAZEPIN', 'OKSKARBAZEPIN']
    benzo_maddeler = ['DIAZEPAM', 'ALPRAZOLAM', 'LORAZEPAM', 'BROMAZEPAM',
                      'KLORDIAZEPOKSIT', 'KLORAZEPAT', 'MIDAZOLAM', 'KLONAZEPAM']

    # Alt grup belirle
    is_ssri = any(m in etkin_madde for m in ssri_maddeler)
    is_snri = any(m in etkin_madde for m in snri_maddeler)
    is_trisiklik = any(m in etkin_madde for m in trisiklik_maddeler)
    is_atipik_ad = any(m in etkin_madde for m in atipik_ad_maddeler)
    is_antipsikotik = any(m in etkin_madde for m in antipsikotik_maddeler)
    is_mood_stab = any(m in etkin_madde for m in mood_stab_maddeler)
    is_benzo = any(m in etkin_madde for m in benzo_maddeler)

    # İlaç adından da kontrol (etkin madde boş gelirse)
    if not any([is_ssri, is_snri, is_trisiklik, is_atipik_ad,
                is_antipsikotik, is_mood_stab, is_benzo]):
        ssri_ticari = ['SECITA', 'CITOLES', 'LUSTRAL', 'FULSAC', 'PROZAC',
                       'SEROXAT', 'PAXIL', 'SELECTRA', 'CIPRALEX']
        snri_ticari = ['DUXET', 'CYMBALTA', 'EFEXOR', 'EFFEXOR']
        atipik_ticari = ['DESYREL', 'REMERON']
        antipsik_ticari = ['CEDRINA', 'KETILEPT', 'SEROQUEL', 'OLAXINN',
                           'ZYPREXA', 'RISPERDAL', 'ABIZOL', 'ABILIFY',
                           'LEPONEX', 'INVEGA']
        mood_ticari = ['DEPAKIN', 'DEPAKINE', 'CONVULEX', 'LAMICTAL']

        if any(t in ilac_adi for t in ssri_ticari):
            is_ssri = True
        elif any(t in ilac_adi for t in snri_ticari):
            is_snri = True
        elif any(t in ilac_adi for t in atipik_ticari):
            is_atipik_ad = True
        elif any(t in ilac_adi for t in antipsik_ticari):
            is_antipsikotik = True
        elif any(t in ilac_adi for t in mood_ticari):
            is_mood_stab = True

    # Alt grup adı belirle
    if is_ssri:
        detaylar['alt_grup'] = 'SSRI'
    elif is_snri:
        detaylar['alt_grup'] = 'SNRI'
    elif is_trisiklik:
        detaylar['alt_grup'] = 'Trisiklik_Antidepresan'
    elif is_atipik_ad:
        detaylar['alt_grup'] = 'Atipik_Antidepresan'
    elif is_antipsikotik:
        detaylar['alt_grup'] = 'Antipsikotik'
    elif is_mood_stab:
        detaylar['alt_grup'] = 'Mood_Stabilizator'
    elif is_benzo:
        detaylar['alt_grup'] = 'Benzodiazepin'

    # Bupropion / Vortioksetin / Agomelatin özel grubu
    bva_maddeler = ['BUPROPION', 'VORTIOKSETIN', 'AGOMELATINE', 'AGOMELATAIN', 'AGOMELATIN']
    bva_ticari = ['WELLBUTRIN', 'BRINTELLIX', 'VALDOXAN', 'THYMANAX']
    is_bva = any(m in etkin_madde for m in bva_maddeler) or any(t in ilac_adi for t in bva_ticari)
    if is_bva:
        detaylar['alt_grup'] = 'Bupropion/Vortioksetin/Agomelatin'

    # ── Benzodiazepin: Yeşil reçete kontrolü (rapor gerekmez) ──
    if is_benzo:
        recete_turu = ilac_sonuc.get('recete_turu', 'Normal')
        if recete_turu == 'Yeşil':
            return KontrolRaporu(KontrolSonucu.UYGUN,
                                 "Benzodiazepin - yeşil reçete ile uygun",
                                 detaylar=detaylar,
                                 sut_kurali='SUT — Benzodiazepinler yeşil reçete ile yazılır')
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Benzodiazepin - reçete türü: {recete_turu}",
                             detaylar=detaylar,
                             uyari="Yeşil reçete zorunluluğu kontrol edilmeli",
                             sut_kurali='SUT — Benzodiazepinler yeşil reçete ile yazılır')

    # ── SUT Fıkra (1): Trisiklik/Tetrasiklik/SSRI → tüm hekimler raporsuz yazabilir ──
    if is_trisiklik or is_ssri:
        # Tüm hekimler raporsuz yazabilir (ilk 6 ay)
        # 6 aydan uzun kullanımda psikiyatri uzmanı gerekir
        return KontrolRaporu(KontrolSonucu.UYGUN,
            f"{detaylar['alt_grup']} — tüm hekimler raporsuz yazabilir",
            detaylar=detaylar,
            uyari='6 aydan uzun kullanım veya grup değişikliğinde psikiyatri uzman raporu gerekli',
            sut_kurali='SUT 4.2.2(1) — Trisiklik/SSRI tüm hekimlerce yazılabilir, 6 ay+ psikiyatri raporu',
            aranan_ibare='Trisiklik/SSRI → rapor gerekmez (ilk 6 ay)')

    # ── SUT Fıkra (1): SNRI/NASSA → psikiyatri/nöroloji/geriatri ──
    # (SNRI zaten rapor kontrolüne düşecek, burada sadece raporsuz durumu kontrol et)

    # ── SUT Fıkra (1): Bupropion/Vortioksetin/Agomelatin → sadece major depresif bozukluk ──
    if is_bva:
        doktor_bva = (ilac_sonuc.get('doktor_uzmanligi') or '').lower()
        doktor_psik = any(k in doktor_bva for k in ['psikiyatri', 'ruh sağ', 'ruh ve sinir'])
        doktor_noro = any(k in doktor_bva for k in ['nöroloji', 'noroloji'])
        recete_teshisleri_bva = ilac_sonuc.get('recete_teshisleri', [])
        teshis_bva = ' '.join(recete_teshisleri_bva).upper() if recete_teshisleri_bva else ''
        major_depresif = any(k in teshis_bva for k in ['F32', 'F33']) or \
                         _turkce_ara(metin or '', 'major depresif') or \
                         _turkce_ara(metin or '', 'depresif bozukluk')

        if rapor_kodu:
            uyari_bva = 'SADECE major depresif bozukluk endikasyonunda' if not major_depresif else None
            return KontrolRaporu(KontrolSonucu.UYGUN,
                f"{detaylar['alt_grup']} — rapor mevcut ({rapor_kodu})",
                detaylar=detaylar, uyari=uyari_bva,
                sut_kurali='SUT 4.2.2(1) — Bupropion/vortioksetin/agomelatin: sadece major depresif, psikiyatri/nöroloji raporu',
                aranan_ibare='Major depresif bozukluk (F32/F33) + psikiyatri/nöroloji')
        if doktor_psik or doktor_noro:
            return KontrolRaporu(KontrolSonucu.UYGUN,
                f"{detaylar['alt_grup']} — {'psikiyatri' if doktor_psik else 'nöroloji'} uzmanı tarafından yazılmış",
                detaylar=detaylar,
                uyari='SADECE major depresif bozukluk endikasyonunda yazılabilir' if not major_depresif else None,
                sut_kurali='SUT 4.2.2(1) — Bupropion/vortioksetin/agomelatin: psikiyatri/nöroloji uzmanı yazabilir')
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
            f"{detaylar['alt_grup']} — psikiyatri/nöroloji uzmanı veya raporu gerekli",
            detaylar=detaylar,
            uyari='SUT 4.2.2: Bupropion/vortioksetin/agomelatin sadece major depresif bozuklukta, psikiyatri/nöroloji',
            sut_kurali='SUT 4.2.2(1)')

    # ── SUT Fıkra (7): Valproat — bipolar bozukluk endikasyonunda psikiyatri/nöroloji ──
    if is_mood_stab and ('VALPROAT' in etkin_madde or 'VALPROIK' in etkin_madde or
                          'DEPAKIN' in ilac_adi or 'DEPAKINE' in ilac_adi or 'CONVULEX' in ilac_adi):
        bipolar = any(k in teshis_metin for k in ['F31']) if recete_teshisleri else False
        if not bipolar:
            bipolar = _turkce_ara(metin or '', 'bipolar')
        detaylar['alt_grup'] = 'Valproat (Bipolar)'
        if rapor_kodu:
            return KontrolRaporu(KontrolSonucu.UYGUN,
                f"Valproat — bipolar bozukluk raporu mevcut ({rapor_kodu})",
                detaylar=detaylar,
                sut_kurali='SUT 4.2.2(7) — Valproat: bipolar bozuklukta psikiyatri/nöroloji raporu',
                aranan_ibare='Bipolar bozukluk (F31) + psikiyatri/nöroloji raporu')
        doktor_val = (ilac_sonuc.get('doktor_uzmanligi') or '').lower()
        if any(k in doktor_val for k in ['psikiyatri', 'nöroloji', 'noroloji']):
            return KontrolRaporu(KontrolSonucu.UYGUN,
                "Valproat — psikiyatri/nöroloji uzmanı tarafından yazılmış",
                detaylar=detaylar,
                sut_kurali='SUT 4.2.2(7) — Valproat: bipolar bozuklukta psikiyatri/nöroloji uzmanı yazabilir')
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
            "Valproat (bipolar) — psikiyatri/nöroloji uzmanı veya raporu gerekli",
            detaylar=detaylar,
            sut_kurali='SUT 4.2.2(7) — Valproat bipolar bozuklukta psikiyatri/nöroloji gerekli')

    # ── Antipsikotik alt tip ayrımı ──
    # Tipik (klasik) antipsikotikler: rapor gerekmez, tüm hekimler yazabilir
    tipik_maddeler = ['HALOPERIDOL', 'KLORPROMAZIN', 'LEVOMEPROMAZIN', 'SÜLPIRID',
                      'ZUKLOPENTIKSOL', 'FLUFENAZIN', 'TRIFLUOPERAZIN', 'PIMOZID']
    atipik_maddeler = ['KETIAPIN', 'OLANZAPIN', 'RISPERIDON', 'ARIPIPRAZOL',
                       'PALIPERIDON', 'KLOZAPIN', 'ZIPRASIDON', 'AMISÜLPRID',
                       'KARIPRAZIN', 'LURASIDON', 'SERTINDOL', 'ZOTEPIN']

    is_tipik = any(m in etkin_madde for m in tipik_maddeler)
    is_atipik = any(m in etkin_madde for m in atipik_maddeler)
    # İlaç adından tipik/atipik kontrolü
    if not is_tipik and not is_atipik and is_antipsikotik:
        tipik_ticari = ['NORODOL', 'LARGACTIL', 'CLOPIXOL']
        if any(t in ilac_adi for t in tipik_ticari):
            is_tipik = True
        else:
            is_atipik = True  # Bilinmeyen antipsikotik → atipik varsay

    # Parenteral/depot form kontrolü
    is_parenteral = any(k in ilac_adi for k in ['AMPUL', 'ENJEKS', 'IM ', 'I.M.', 'FLAKON'])
    is_depot = any(k in ilac_adi for k in ['DEPOT', 'CONSTA', 'SUSTENNA', 'MAINTENA',
                                            'UZUN ETK', 'AYLIK', '1 AYLIK', '3 AYLIK'])

    # Klozapin özel kontrol
    is_klozapin = 'KLOZAPIN' in etkin_madde or 'LEPONEX' in ilac_adi or 'CLOZARIL' in ilac_adi

    # Demans tanısı kontrolü (recete_teshisleri ve teshis_metin fonksiyon başında tanımlı)
    is_demans = any(k in teshis_metin for k in ['F01', 'F03', 'G30', 'F00']) or \
                _turkce_ara(metin or '', 'demans') or _turkce_ara(metin or '', 'alzheimer')

    detaylar['antipsikotik_tip'] = 'tipik' if is_tipik else ('atipik' if is_atipik else 'bilinmiyor')
    detaylar['parenteral'] = is_parenteral
    detaylar['depot'] = is_depot
    detaylar['klozapin'] = is_klozapin
    detaylar['demans'] = is_demans

    sut_kurali_ap = 'SUT 4.2.2 — Antipsikotik kullanım kuralları'

    # ── SUT Fıkra (4): TİPİK ANTİPSİKOTİK — rapor gerekmez, tüm hekimler yazabilir ──
    if is_tipik and not is_depot:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Tipik antipsikotik ({etkin_madde or ilac_adi[:20]}) — rapor gerekmez",
                             detaylar=detaylar,
                             sut_kurali='SUT 4.2.2(4) — Tipik antipsikotikler rapor kısıtlamasına tabi değil',
                             aranan_ibare='Tipik antipsikotik → rapor gerekmez')

    # ── SUT Fıkra (5): ACİL SERVIS İSTİSNASI ──
    # Acil serviste atipik antipsikotik parenteral (depot hariç) tek doz, tüm hekimler yazabilir
    recete_alt_turu = (ilac_sonuc.get('recete_alt_turu') or '').lower()
    is_acil = 'acil' in recete_alt_turu
    if is_acil and is_parenteral and not is_depot and (is_atipik or is_antipsikotik):
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Acil servis — atipik antipsikotik parenteral tek doz (depot hariç)",
                             detaylar=detaylar,
                             sut_kurali='SUT 4.2.2(5) — Acil serviste parenteral atipik antipsikotik (depot hariç) tek doz tüm hekimlerce yazılabilir',
                             aranan_ibare='Reçete alt türü: Acil + parenteral form (depot hariç)',
                             bulunan_metin=f'Reçete alt türü: {recete_alt_turu}')

    # ── Rapor kodu kontrolü ──
    psikiyatri_rapor_kodlari = ['11.04', '11.03']
    noroloji_rapor_kodlari = ['10.']
    rapor_psikiyatri = False
    rapor_noroloji = False
    rapor_diger = False
    if rapor_kodu:
        rapor_psikiyatri = any(rapor_kodu.startswith(k) for k in psikiyatri_rapor_kodlari)
        rapor_noroloji = any(rapor_kodu.startswith(k) for k in noroloji_rapor_kodlari)
        if not rapor_psikiyatri and not rapor_noroloji:
            rapor_diger = True
            detaylar['rapor_tipi'] = 'diger_brans'

    rapor_var = rapor_psikiyatri or rapor_noroloji or rapor_diger

    if rapor_var and rapor_kodu:
        if rapor_psikiyatri:
            detaylar['rapor_tipi'] = 'psikiyatri'
        elif rapor_noroloji:
            detaylar['rapor_tipi'] = 'noroloji'

        uyarilar = []

        # Klozapin özel kurallar
        if is_klozapin:
            uyarilar.append("KLOZAPİN: Maks 1 aylık doz, klozapin granülosit izlem formu zorunlu")
            uyarilar.append("Hemogram takibi: ilk 18 hafta haftalık, sonra aylık")

        # Depot/parenteral: SADECE psikiyatri raporu geçerli
        if is_depot:
            if not rapor_psikiyatri:
                return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                    f"Depot antipsikotik — SADECE psikiyatri raporu geçerli (mevcut: {detaylar.get('rapor_tipi','?')})",
                    detaylar=detaylar, sut_kurali=sut_kurali_ap,
                    uyari='SUT: Depot formlar (EK-4/F) psikiyatri uzmanı sağlık kurulu raporu gerektirir',
                    aranan_ibare='Psikiyatri uzman raporu (11.04.x)')
            uyarilar.append("Depot form (EK-4/F) — psikiyatri sağlık kurulu raporu")

        if is_parenteral and not is_depot:
            if not rapor_psikiyatri:
                uyarilar.append("Parenteral atipik antipsikotik — psikiyatri raporu tercih edilir")

        # Atipik antipsikotik + psikiyatri dışı rapor
        if is_atipik and not rapor_psikiyatri and not rapor_noroloji:
            uyarilar.append(f"Atipik antipsikotik — rapor branşı ({detaylar.get('rapor_tipi','?')}) uygun olmayabilir")

        # Demans tanısında geriatri de yeterli
        if is_demans and rapor_noroloji:
            uyarilar.append("Demans tanısında nöroloji raporu yeterli")

        eslesen = f"Rapor kodu {rapor_kodu} → {detaylar.get('rapor_tipi','?')} branşı"

        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Uzman raporu mevcut ({detaylar.get('rapor_tipi','?')}) - {detaylar['alt_grup']}",
                             detaylar=detaylar,
                             uyari=" | ".join(uyarilar) if uyarilar else None,
                             sut_kurali=sut_kurali_ap,
                             aranan_ibare=f"Rapor kodu: {rapor_kodu} (psikiyatri: 11.04.x, nöroloji: 10.x)",
                             bulunan_metin=eslesen)

    # ── Rapor kodu yok → doktor branşı + mesaj/metin analizi ──
    # SUT 4.2.2: Atipik antipsikotik oral formları psikiyatri veya nöroloji
    # uzman hekimleri tarafından RAPORSUZ da yazılabilir.
    doktor = (ilac_sonuc.get('doktor_uzmanligi') or '').lower()
    doktor_psikiyatri = any(k in doktor for k in ['psikiyatri', 'ruh sağ', 'ruh ve sinir'])
    doktor_noroloji = any(k in doktor for k in ['nöroloji', 'noroloji'])
    doktor_geriatri = 'geriatri' in doktor
    doktor_uygun = doktor_psikiyatri or doktor_noroloji

    if not rapor_kodu and is_atipik and not is_depot:
        # Oral atipik: psikiyatri/nöroloji uzmanı raporsuz yazabilir
        if doktor_uygun:
            brans = 'psikiyatri' if doktor_psikiyatri else 'nöroloji'
            uyarilar = []
            if is_klozapin:
                uyarilar.append("KLOZAPİN: Maks 1 aylık doz, granülosit izlem formu zorunlu")
            return KontrolRaporu(KontrolSonucu.UYGUN,
                f"Atipik antipsikotik — {brans} uzmanı tarafından yazılmış (raporsuz yazılabilir)",
                detaylar=detaylar, sut_kurali=sut_kurali_ap,
                uyari=" | ".join(uyarilar) if uyarilar else None,
                aranan_ibare=f'Doktor branşı: {brans} (psikiyatri/nöroloji raporsuz yazabilir)',
                bulunan_metin=f'Doktor: {doktor}')
        # Demans tanısında geriatri de yeterli
        if is_demans and doktor_geriatri:
            return KontrolRaporu(KontrolSonucu.UYGUN,
                "Atipik antipsikotik (demans) — geriatri uzmanı tarafından yazılmış",
                detaylar=detaylar, sut_kurali=sut_kurali_ap,
                aranan_ibare='Demans + geriatri uzmanı',
                bulunan_metin=f'Doktor: {doktor}')

    if not metin and not rapor_kodu:
        if is_depot:
            return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                "DEPOT antipsikotik RAPORSUZ! Psikiyatri sağlık kurulu raporu ZORUNLU (EK-4/F)",
                detaylar=detaylar, sut_kurali=sut_kurali_ap,
                uyari="SUT 4.2.2 - Depot formlar EK-4/F sağlık kurulu raporu gerektirir",
                aranan_ibare='Psikiyatri sağlık kurulu raporu')
        if is_parenteral and not doktor_psikiyatri:
            return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                "Parenteral atipik antipsikotik — SADECE psikiyatri uzmanı yazabilir",
                detaylar=detaylar, sut_kurali=sut_kurali_ap,
                uyari="SUT 4.2.2 - Parenteral formlar sadece psikiyatri uzmanı",
                aranan_ibare='Psikiyatri uzman raporu')
        if (is_atipik or is_antipsikotik) and not doktor_uygun:
            return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                f"Atipik antipsikotik — doktor branşı ({doktor or 'bilinmiyor'}) psikiyatri/nöroloji değil, rapor gerekli",
                detaylar=detaylar, sut_kurali=sut_kurali_ap,
                uyari="SUT 4.2.2 - Psikiyatri/nöroloji dışı hekim raporsuz yazamaz",
                aranan_ibare='Psikiyatri/nöroloji uzmanı veya raporu')
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok - kontrol edilemedi",
                             detaylar=detaylar, sut_kurali=sut_kurali_ap)

    # ── Metin analizi: Uzman branş tespiti ──
    psikiyatri_uzman = (_turkce_ara(metin, 'psikiyatri') or
                        _turkce_ara(metin, 'ruh sag') or
                        _turkce_ara(metin, 'ruh ve sinir'))
    noroloji_uzman = (_turkce_ara(metin, 'noroloji') or
                      _turkce_ara(metin, 'nöroloji'))
    geriatri_uzman = _turkce_ara(metin, 'geriatri')
    dahiliye_uzman = (_turkce_ara(metin, 'dahiliye') or
                      _turkce_ara(metin, 'ic hastaliklari') or
                      _turkce_ara(metin, 'iç hastalıkları'))
    aile_hekimi = (_turkce_ara(metin, 'aile hekimi') or
                   _turkce_ara(metin, 'pratisyen'))

    uzman_var = psikiyatri_uzman or noroloji_uzman or geriatri_uzman
    uzman_adi = []
    if psikiyatri_uzman:
        uzman_adi.append('psikiyatri')
    if noroloji_uzman:
        uzman_adi.append('nöroloji')
    if geriatri_uzman:
        uzman_adi.append('geriatri')

    # ── Metin analizi: Tanı tespiti ──
    # Depresif bozukluklar
    depresyon = (_turkce_ara(metin, 'depres') or
                 _turkce_ara(metin, 'major depresif') or
                 _turkce_ara(metin, 'distimi'))
    # Anksiyete bozuklukları
    anksiyete = (_turkce_ara(metin, 'anksiyete') or
                 _turkce_ara(metin, 'kaygi bozuklugu') or
                 _turkce_ara(metin, 'kaygı bozukluğu'))
    # Panik bozukluk
    panik = _turkce_ara(metin, 'panik')
    # OKB
    okb = (_turkce_ara(metin, 'obsesif') or
           _turkce_ara(metin, 'kompulsif') or
           _turkce_ara(metin, 'OKB'))
    # Fobiler
    fobi = (_turkce_ara(metin, 'fobi') or
            _turkce_ara(metin, 'sosyal kaygi'))
    # Bipolar
    bipolar = (_turkce_ara(metin, 'bipolar') or
               _turkce_ara(metin, 'manik') or
               _turkce_ara(metin, 'mani'))
    # Şizofreni ve psikotik bozukluklar
    sizofreni = (_turkce_ara(metin, 'sizofreni') or
                 _turkce_ara(metin, 'şizofreni') or
                 _turkce_ara(metin, 'psikotik') or
                 _turkce_ara(metin, 'psikoz'))
    # TSSB
    tssb = (_turkce_ara(metin, 'travma sonrasi stres') or
            _turkce_ara(metin, 'TSSB') or
            _turkce_ara(metin, 'PTSD'))
    # DEHB
    dehb = (_turkce_ara(metin, 'dikkat eksikligi') or
            _turkce_ara(metin, 'DEHB') or
            _turkce_ara(metin, 'ADHD'))
    # Uyku bozukluğu
    uyku = (_turkce_ara(metin, 'uykusuzluk') or
            _turkce_ara(metin, 'insomni'))
    # Genel psikiyatrik tanı (ICD kodları)
    icd_psik = bool(re.search(r'F\d{2}', metin))

    tani_var = any([depresyon, anksiyete, panik, okb, fobi, bipolar,
                    sizofreni, tssb, dehb, uyku, icd_psik])

    tani_listesi = []
    if depresyon: tani_listesi.append('depresyon')
    if anksiyete: tani_listesi.append('anksiyete')
    if panik: tani_listesi.append('panik bozukluk')
    if okb: tani_listesi.append('OKB')
    if fobi: tani_listesi.append('fobi')
    if bipolar: tani_listesi.append('bipolar')
    if sizofreni: tani_listesi.append('şizofreni/psikoz')
    if tssb: tani_listesi.append('TSSB')
    if dehb: tani_listesi.append('DEHB')
    if uyku: tani_listesi.append('uyku bozukluğu')
    if icd_psik: tani_listesi.append('ICD-F kodu')

    detaylar['tanilar'] = tani_listesi
    detaylar['uzman_branslari'] = uzman_adi

    # ── Doz kontrolü (metin içinden) ──
    maks_dozlar = {
        'ESSITALOPRAM': 20, 'SERTRALIN': 200, 'FLUOKSETIN': 80,
        'PAROKSETIN': 60, 'DULOKSETIN': 120, 'VENLAFAKSIN': 375,
        'KETIAPIN': 800, 'OLANZAPIN': 20, 'RISPERIDON': 16,
        'ARIPIPRAZOL': 30, 'PALIPERIDON': 12, 'TRAZODON': 600,
        'MIRTAZAPIN': 45, 'BUPROPION': 450, 'KLOZAPIN': 900,
        'HALOPERIDOL': 20, 'AMISÜLPRID': 1200,
    }
    doz_uyarisi = None
    for madde, maks in maks_dozlar.items():
        if madde in etkin_madde:
            doz_match = re.search(r'(\d+)\s*mg', metin, re.IGNORECASE) if metin else None
            if doz_match:
                doz = int(doz_match.group(1))
                if doz > maks:
                    doz_uyarisi = f"{madde} dozu ({doz} mg) maksimum dozu ({maks} mg/gün) aşıyor"
                    detaylar['doz_asimi'] = True
                    detaylar['doz_bilgi'] = f"{doz} mg > maks {maks} mg"
            break

    # ── Klozapin özel kontrol ──
    if 'KLOZAPIN' in etkin_madde or 'LEPONEX' in ilac_adi:
        if not uzman_var and not rapor_kodu:
            return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                                 "KLOZAPİN RAPORSUZ! Psikiyatri uzman raporu + hemogram takibi ZORUNLU",
                                 detaylar=detaylar,
                                 uyari="SUT 4.2.2 - Klozapin: psikiyatri raporu + haftalık hemogram (ilk 18 hafta)")

    # ── Sonuç değerlendirme ──
    # 1. Uzman + tanı = en iyi durum
    if uzman_var and tani_var:
        uyari_parts = [f"Uzman: {'/'.join(uzman_adi)}", "Rapor süresi: 1 yıl"]
        if doz_uyarisi:
            uyari_parts.append(f"DOZ UYARISI: {doz_uyarisi}")
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Uzman raporu ({'/'.join(uzman_adi)}) + tanı ({', '.join(tani_listesi)}) mevcut - {detaylar['alt_grup']}",
                             detaylar=detaylar,
                             uyari=" | ".join(uyari_parts))

    # 2. Sadece uzman var
    if uzman_var:
        uyari_parts = [f"Uzman: {'/'.join(uzman_adi)}", "Rapor süresi: 1 yıl"]
        if doz_uyarisi:
            uyari_parts.append(f"DOZ UYARISI: {doz_uyarisi}")
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Uzman raporu mevcut ({'/'.join(uzman_adi)}) - {detaylar['alt_grup']}",
                             detaylar=detaylar,
                             uyari=" | ".join(uyari_parts))

    # 3. Sadece tanı var (uzman adı yok)
    if tani_var:
        uyari_parts = ["Uzman adı kontrol edilmeli (psikiyatri/nöroloji/geriatri)"]
        if is_antipsikotik:
            uyari_parts.append("Antipsikotik ilaç - psikiyatri uzman raporu tercih edilir")
        if doz_uyarisi:
            uyari_parts.append(f"DOZ UYARISI: {doz_uyarisi}")
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Psikiyatrik tanı raporda mevcut ({', '.join(tani_listesi)}) - {detaylar['alt_grup']}",
                             detaylar=detaylar,
                             uyari=" | ".join(uyari_parts))

    # 4. Dahiliye/aile hekimi yazmış (uzman değil)
    if dahiliye_uzman or aile_hekimi:
        brans = 'dahiliye' if dahiliye_uzman else 'aile hekimi'
        if is_antipsikotik:
            return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                                 f"Antipsikotik ilaç {brans} tarafından yazılmış - psikiyatri uzman raporu ZORUNLU",
                                 detaylar=detaylar,
                                 uyari="SUT 4.2.2 - Antipsikotik ilaçlar psikiyatri/nöroloji uzman raporu gerektirir")
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             f"Raporda {brans} ibaresi var ama psikiyatri/nöroloji/geriatri uzmanı gerekli",
                             detaylar=detaylar,
                             uyari="SUT 4.2.2 - Antidepresan: psikiyatri/nöroloji/geriatri uzman raporu gerekli")

    # 5. Rapor kodu var, diğer branş (psikiyatri/nöroloji değil)
    if rapor_kodu and rapor_diger and not tani_var and not uzman_var:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             f"Rapor kodu ({rapor_kodu}) mevcut ama psikiyatri/nöroloji branşı değil",
                             detaylar=detaylar,
                             uyari="Rapor branşı ve tanı manuel kontrol edilmeli")

    # 6. Hiçbir bilgi bulunamadı
    if is_antipsikotik:
        return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                             "Antipsikotik ilaç - psikiyatri uzman raporu/tanısı tespit edilemedi, rapor ZORUNLU",
                             detaylar=detaylar,
                             uyari="SUT 4.2.2 - Antipsikotik ilaçlar kesinlikle raporsuz verilemez")

    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         f"Psikiyatri uzman raporu/tanısı tespit edilemedi - {detaylar['alt_grup']}",
                         detaylar=detaylar,
                         uyari="SUT 4.2.2 - Psikiyatri/nöroloji/geriatri uzman raporu gerekli, rapor süresi 1 yıl")


def kontrol_solunum(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.24 - Solunum Sistemi İlaçları (Astım/KOAH)

    İlaç alt grupları ve kuralları:
    1. SABA/SAMA: Raporsuz yazılabilir
    2. ICS tek: Uzman hekim yazarsa raporsuz
    3. LABA+ICS: Rapor gerekli (göğüs hast./alerji/iç hast./çocuk)
    4. LAMA: Rapor gerekli
    5. LABA+LAMA+ICS (üçlü): Rapor + 3 ay ICS+LABA başarısızlığı + atak + dispne
    6. Montelukast: İç hast./çocuk/göğüs hast. raporu
    7. Omalizumab: Sağlık kurulu raporu (16 hafta ilk, yıllık devam)
    8. Roflumilast: FEV1≤%50 + yılda ≥2 atak, 6 aylık rapor
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', [])
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''

    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower() if birlesik else ''

    sut_kurali = 'SUT 4.2.24 — Solunum sistemi ilaçları kullanım kuralları'
    detaylar = {'ilac_adi': ilac_adi, 'alt_grup': 'bilinmiyor'}

    # ── 1. İlaç alt grubu tespiti ──
    # SABA (kısa etkili beta agonist) — raporsuz
    saba_maddeler = ['SALBUTAMOL', 'TERBUTALIN']
    saba_ticari = ['VENTOLIN', 'BUVENTOL']
    is_saba = any(m in etkin_madde for m in saba_maddeler) or any(t in ilac_adi for t in saba_ticari)

    # SAMA — raporsuz
    is_sama = 'IPRATROPIUM' in etkin_madde or 'IPRATROPY' in etkin_madde or 'ATROVENT' in ilac_adi

    # ICS tek başına
    ics_maddeler = ['BUDESONID', 'FLUTIKAZON', 'BEKLOMETAZON', 'SIKLESONID', 'MOMETAZON']
    ics_ticari = ['PULMICORT', 'FLIXOTIDE', 'BECLOFORTE', 'ALVESCO', 'MIFLONIDE']
    is_ics_tek = (any(m in etkin_madde for m in ics_maddeler) or any(t in ilac_adi for t in ics_ticari)) \
                  and not any(k in etkin_madde for k in ['FORMOTEROL', 'SALMETEROL', 'VILANTEROL'])

    # LABA+ICS kombinasyon
    laba_ics_ticari = ['SERETIDE', 'SYMBICORT', 'FOSTER', 'RELVAR', 'DUORESP',
                       'MIFLONIDE COMBI', 'AIRFLUSAL', 'BUFOMIX', 'FOKUSAL']
    laba_ics_madde = ('FORMOTEROL' in etkin_madde or 'SALMETEROL' in etkin_madde or 'VILANTEROL' in etkin_madde) \
                     and any(m in etkin_madde for m in ics_maddeler)
    is_laba_ics = any(t in ilac_adi for t in laba_ics_ticari) or laba_ics_madde

    # LAMA
    lama_maddeler = ['TIOTROPIUM', 'GLIKOPIRONYUM', 'UMEKLIDINYUM', 'AKLIDINYUM']
    lama_ticari = ['SPIRIVA', 'INCRUSE', 'SEEBRI', 'BRETARIS', 'EKLIRA']
    is_lama = any(m in etkin_madde for m in lama_maddeler) or any(t in ilac_adi for t in lama_ticari)

    # LABA+LAMA
    laba_lama_ticari = ['ANORO', 'ULTIBRO', 'SPIOLTO', 'DUAKLIR', 'BEVESPI']
    is_laba_lama = any(t in ilac_adi for t in laba_lama_ticari)

    # Üçlü kombinasyon (LABA+ICS+LAMA)
    uclu_ticari = ['TRELEGY', 'TRIMBOW', 'ENERZAIR', 'BREQUAL', 'BREQAL']
    is_uclu = any(t in ilac_adi for t in uclu_ticari)

    # Montelukast
    is_montelukast = 'MONTELUKAST' in etkin_madde or 'SINGULAIR' in ilac_adi or 'ONCEAIR' in ilac_adi

    # Omalizumab (biyolojik)
    is_omalizumab = 'OMALIZUMAB' in etkin_madde or 'XOLAIR' in ilac_adi

    # Roflumilast
    is_roflumilast = 'ROFLUMILAST' in etkin_madde or 'DAXAS' in ilac_adi or 'DALIRESP' in ilac_adi

    # Alt grup adı
    if is_saba: detaylar['alt_grup'] = 'SABA'
    elif is_sama: detaylar['alt_grup'] = 'SAMA'
    elif is_ics_tek: detaylar['alt_grup'] = 'ICS'
    elif is_uclu: detaylar['alt_grup'] = 'LABA+ICS+LAMA (üçlü)'
    elif is_laba_ics: detaylar['alt_grup'] = 'LABA+ICS'
    elif is_laba_lama: detaylar['alt_grup'] = 'LABA+LAMA'
    elif is_lama: detaylar['alt_grup'] = 'LAMA'
    elif is_montelukast: detaylar['alt_grup'] = 'Montelukast'
    elif is_omalizumab: detaylar['alt_grup'] = 'Omalizumab (biyolojik)'
    elif is_roflumilast: detaylar['alt_grup'] = 'Roflumilast'

    # ── 2. Tanı tespiti ──
    astim = bool(re.search(r'ast[ıi]m|asthma', metin_lower))
    koah = bool(re.search(r'koah|copd|kronik\s*obstr', metin_lower))
    icd_astim = any(k in teshis_metin for k in ['J45', 'J46'])
    icd_koah = any(k in teshis_metin for k in ['J43', 'J44'])
    astim = astim or icd_astim
    koah = koah or icd_koah
    detaylar['astim'] = astim
    detaylar['koah'] = koah

    # Uzman branş
    gogus = bool(re.search(r'g[oö][gğ][uü]s\s*hastal|pulmonoloji|pneumoloji', metin_lower))
    alerji = _turkce_ara(metin_lower, 'alerji') or _turkce_ara(metin_lower, 'immunoloji')

    eslesen = ""
    for k in ['astım', 'astim', 'koah', 'copd', 'kronik obstr', 'göğüs hastal']:
        p = _eslesen_parcayi_bul(birlesik, k)
        if p:
            eslesen = p
            break

    # ── 3. Alt gruba göre kontrol ──

    # SABA/SAMA → raporsuz yazılabilir
    if is_saba or is_sama:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{detaylar["alt_grup"]} — raporsuz yazılabilir',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='SABA/SAMA → rapor gerekmez',
            bulunan_metin=eslesen if eslesen else None
        )

    # Omalizumab → sağlık kurulu raporu gerekli
    if is_omalizumab:
        yuksek_doz_ics = _turkce_ara(metin_lower, 'yüksek doz') or _turkce_ara(metin_lower, 'yuksek doz')
        ige = bool(re.search(r'ig\s*e|ige', metin_lower))
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN if (astim and (yuksek_doz_ics or ige)) else KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Omalizumab — {"astım + IgE/yüksek doz ICS mevcut" if astim else "astım tanısı kontrol edilmeli"}',
            detaylar=detaylar, sut_kurali='SUT 4.2.24 — Omalizumab: sağlık kurulu raporu, ilk 16 hafta değerlendirme',
            uyari='Sağlık kurulu raporu zorunlu (alerji + göğüs hastalıkları)' if not astim else None,
            aranan_ibare='astım + yüksek doz ICS başarısızlığı + IgE düzeyi',
            bulunan_metin=eslesen
        )

    # Roflumilast → FEV1≤%50 + yılda ≥2 atak
    if is_roflumilast:
        fev1_match = re.findall(r'fev1?\s*[:=<]?\s*(%?\d+)', metin_lower)
        fev1 = None
        if fev1_match:
            try:
                fev1 = int(fev1_match[0].replace('%', ''))
            except:
                pass
        atak = bool(re.search(r'atak|alevlenme|eksaserbasyon', metin_lower))
        if fev1 and fev1 <= 50 and atak:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Roflumilast — FEV1 {fev1}% ≤ 50 + atak öyküsü',
                detaylar={**detaylar, 'fev1': fev1}, sut_kurali=sut_kurali,
                aranan_ibare='FEV1 ≤ %50 + yılda ≥2 atak',
                bulunan_metin=eslesen
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Roflumilast — {"FEV1 " + str(fev1) + "%" if fev1 else "FEV1 bulunamadı"}, {"atak var" if atak else "atak bilgisi yok"}',
            detaylar={**detaylar, 'fev1': fev1}, sut_kurali=sut_kurali,
            uyari='Roflumilast: FEV1≤%50 + yılda ≥2 atak + göğüs hastalıkları 6 aylık rapor',
            aranan_ibare='FEV1 ≤ %50 + atak sayısı'
        )

    # Üçlü kombinasyon → 3 ay ICS+LABA başarısızlığı + atak + dispne
    if is_uclu:
        onceki_tedavi = bool(re.search(r'ics.*laba|iks.*laba|inhaler.*kortikosteroid|laba.*ics', metin_lower))
        yetersiz = _turkce_ara(metin_lower, 'yetersiz') or _turkce_ara(metin_lower, 'yeterli yan') or \
                   _turkce_ara(metin_lower, 'başarısız') or _turkce_ara(metin_lower, 'cevapsız')
        atak = bool(re.search(r'atak|alevlenme|eksaserbasyon', metin_lower))
        dispne = bool(re.search(r'dispne|mmrc|cat\s*skor|nefes\s*darl', metin_lower))
        detaylar['onceki_tedavi'] = onceki_tedavi
        detaylar['atak'] = atak
        detaylar['dispne'] = dispne

        if koah and (onceki_tedavi or yetersiz) and atak:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Üçlü kombinasyon — KOAH + önceki ICS+LABA + atak',
                detaylar=detaylar, sut_kurali='SUT 4.2.24.B — Üçlü: 3 ay ICS+LABA başarısızlığı + ≥2 atak/yıl + mMRC≥2',
                aranan_ibare='KOAH + ICS+LABA öncesi tedavi + atak + dispne',
                bulunan_metin=eslesen
            )
        if koah or astim:
            eksik = []
            if not onceki_tedavi and not yetersiz:
                eksik.append('ICS+LABA öncesi tedavi')
            if not atak:
                eksik.append('atak bilgisi')
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'Üçlü kombinasyon — eksik: {", ".join(eksik)}',
                detaylar=detaylar, sut_kurali='SUT 4.2.24.B — Üçlü: 3 ay ICS+LABA başarısızlığı gerekli',
                uyari='Raporda "en az 3 ay ICS+LABA kullanılıp yetersiz yanıt" ve "yılda ≥2 atak" belirtilmeli',
                aranan_ibare='ICS+LABA öncesi + atak + dispne',
                bulunan_metin=eslesen
            )

    # Genel solunum ilaçları (LABA+ICS, LAMA, LABA+LAMA, ICS, Montelukast)
    if not metin_lower:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Rapor/mesaj metni yok', sut_kurali=sut_kurali,
            aranan_ibare='astım / KOAH / göğüs hastalıkları raporu')

    # Tanı var mı?
    if astim or koah:
        tani_adi = 'Astım' if astim else 'KOAH'
        uzman_bilgi = ""
        if gogus:
            uzman_bilgi = " + göğüs hastalıkları uzmanı"
        elif alerji:
            uzman_bilgi = " + alerji uzmanı"
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{tani_adi} tanısı mevcut{uzman_bilgi} — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare=f'{tani_adi} tanısı (J45/J46 veya J43/J44)',
            bulunan_metin=eslesen
        )

    if gogus or alerji:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Uzman raporu mevcut ({"göğüs hastalıkları" if gogus else "alerji"}) — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='göğüs hastalıkları / alerji uzman raporu',
            bulunan_metin=_eslesen_parcayi_bul(birlesik, 'göğüs' if gogus else 'alerji')
        )

    # Rapor kodu var ama tanı bulunamadı
    if rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Rapor kodu {rapor_kodu} var ama astım/KOAH tanısı bulunamadı',
            detaylar=detaylar, sut_kurali=sut_kurali,
            uyari='Raporda astım veya KOAH tanısı olmalı',
            aranan_ibare='astım (J45/J46) / KOAH (J43/J44)'
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=f'Astım/KOAH tanısı veya göğüs hastalıkları raporu tespit edilemedi — {detaylar["alt_grup"]}',
        detaylar=detaylar, sut_kurali=sut_kurali,
        aranan_ibare='astım / KOAH / göğüs hastalıkları / alerji / pulmonoloji'
    )


def kontrol_genel_raporlu(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Genel raporlu ilaçlar - Detaylı SUT kontrolleri.

    GENEL_RAPORLU kategorisi, özel bir kategori fonksiyonu olmayan raporlu ilaçları kapsar.
    Bu fonksiyon rapor kodu, etkin madde ve ilaç adına göre alt-kural kontrolleri yapar:

    1. GnRH (LHRH) Analogları (SUT 4.2.14.C) - Löprolid, Gosrelin, Triptorelin, Büserelin
       - Endokrinoloji / Üroloji / Kadın Hastalıkları / Onkoloji uzman raporu
       - Endikasyonlar: prostat ca, meme ca, endometriozis, puberte prekoks, myoma uteri
       - Rapor kodu: 07.01.5 (puberte prekoks), 02.xx (onkoloji), 09.xx (kadın hast.)
    2. Büyüme Hormonu (SUT 4.2.14.A) - Somatropin
       - Çocuk endokrinoloji uzman raporu, 6 aylık
       - Rapor kodu: 07.01.1
    3. Eritropoietin / ESA (SUT 4.2.30) - Eritropoietin, Darbepoetin
       - Nefroloji / Hematoloji / Onkoloji uzman raporu
       - Rapor kodu: 08.xx, 13.xx
    4. İmmünosüpresifler (SUT 4.2.32) - Mikofenolat, Takrolimus, Siklosporin
       - Transplantasyon / otoimmün endikasyon
       - Rapor kodu: 15.xx, 16.xx
    5. TNF İnhibitörleri / Biyolojikler (SUT 4.2.33) - Adalimumab, Etanersept, İnfliksimab vb.
       - İlgili branş uzman raporu, basamak tedavi şartı
       - Rapor kodu: 01.xx (romatoloji), 06.xx (dermatoloji), 09.xx
    6. İmmünglobulinler (SUT 4.2.6) - IVIG
       - Hematoloji / Nöroloji / İmmünoloji uzman raporu
    7. Koagülasyon Faktörleri (SUT 4.2.5) - Faktör VIII, IX vb.
       - Hematoloji uzman raporu
    8. Antifungal (SUT EK-4/E) - Vorikonazol, Kaspofungin, Amfoterisin B
       - Enfeksiyon hastalıkları / Hematoloji uzman raporu
    9. Diğer raporlu ilaçlar → rapor kodu kontrolü + genel uyarı
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()

    if not metin and not rapor_kodu and not ilac_adi and not etkin_madde:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             'Rapor/mesaj metni yok — kontrol yapılamadı')

    # ── 1. GnRH (LHRH) Analogları (SUT 4.2.14.C) ──
    gnrh_etkin = ['LOPROLID', 'LÖPROLID', 'LEUPROLID', 'LEUPRORELIN',
                  'GOSERELIN', 'GOSRELIN', 'TRIPTORELIN', 'BUSERELIN', 'BÜSERELIN',
                  'DEGARELIX', 'NAFARELIN']
    gnrh_ilac = ['LUCRIN', 'ELIGARD', 'ZOLADEX', 'GONAPEPTYL', 'DECAPEPTYL',
                 'DIPHERELINE', 'SUPREFACT', 'FIRMAGON', 'ENANTONE', 'PROSTAP']
    gnrh_mi = any(_turkce_ara(etkin_madde, e) for e in gnrh_etkin) or \
              any(i in ilac_adi for i in gnrh_ilac)

    if gnrh_mi:
        uyarilar = []
        detaylar = {'alt_kategori': 'GNRH_ANALOG', 'sut_maddesi': '4.2.14.C'}

        # Rapor kodu kontrolü
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'GnRH analoğu RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.14.C - Endokrinoloji/Üroloji/Kadın Hast./Onkoloji uzman raporu gerekli',
                sut_kurali='SUT 4.2.14.C — GnRH analogları uzman sağlık kurulu raporu ile reçete edilir'
            )

        # Rapor kodu bazlı endikasyon tespiti
        endikasyon = None
        if rapor_kodu.startswith('07.01.5'):
            endikasyon = 'Puberte Prekoks'
            uyarilar.append('Çocuk endokrinoloji uzman raporu olmalı')
            uyarilar.append('Kemik yaşı / Tanner evresi raporda belirtilmeli')
        elif rapor_kodu.startswith('07.01'):
            endikasyon = 'Endokrinoloji'
            uyarilar.append('Endokrinoloji uzman raporu kontrol edilmeli')
        elif rapor_kodu.startswith('02.'):
            endikasyon = 'Onkoloji'
            uyarilar.append('Onkoloji uzman raporu / protokol kontrol edilmeli')
        elif rapor_kodu.startswith('09.'):
            endikasyon = 'Kadın Hastalıkları (Endometriozis/Myoma)'
            uyarilar.append('Kadın hastalıkları uzman raporu kontrol edilmeli')
        elif rapor_kodu.startswith('03.') or rapor_kodu.startswith('04.'):
            endikasyon = 'Üroloji (Prostat)'
            uyarilar.append('Üroloji uzman raporu kontrol edilmeli')

        # Metin içinde endikasyon ipuçları
        if metin:
            endikasyon_ipucu = []
            if _turkce_ara(metin, 'prostat'):
                endikasyon_ipucu.append('prostat kanseri')
            if _turkce_ara(metin, 'meme'):
                endikasyon_ipucu.append('meme kanseri')
            if _turkce_ara(metin, 'endometriozis') or _turkce_ara(metin, 'endometrioz'):
                endikasyon_ipucu.append('endometriozis')
            if _turkce_ara(metin, 'puberte') or _turkce_ara(metin, 'prekoks'):
                endikasyon_ipucu.append('puberte prekoks')
            if _turkce_ara(metin, 'myoma') or _turkce_ara(metin, 'miyom'):
                endikasyon_ipucu.append('myoma uteri')
            if endikasyon_ipucu:
                detaylar['endikasyon_ipucu'] = endikasyon_ipucu

        detaylar['endikasyon'] = endikasyon or 'Belirlenemedi'
        detaylar['rapor_kodu'] = rapor_kodu

        mesaj = f"GnRH analoğu — rapor kodu {rapor_kodu}"
        if endikasyon:
            mesaj += f" ({endikasyon})"

        return KontrolRaporu(
            KontrolSonucu.UYGUN, mesaj,
            detaylar=detaylar,
            uyari=' | '.join(uyarilar) if uyarilar else 'Rapor içeriği ve süresi manuel kontrol edilmeli',
            sut_kurali='SUT 4.2.14.C — GnRH analogları ilgili branş uzman raporu ile reçete edilir',
            aranan_ibare='GnRH analog + uzman raporu',
            bulunan_metin=_eslesen_parcayi_bul(metin, 'rapor') if metin else ''
        )

    # ── 2. Büyüme Hormonu (SUT 4.2.14.A) ──
    bh_etkin = ['SOMATROPIN', 'SOMATOTROPIN']
    bh_ilac = ['GENOTROPIN', 'NORDITROPIN', 'HUMATROPE', 'SAIZEN', 'OMNITROPE',
               'NUTROPIN', 'ZOMACTON']
    bh_mi = any(_turkce_ara(etkin_madde, e) for e in bh_etkin) or \
            any(i in ilac_adi for i in bh_ilac)

    if bh_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Büyüme hormonu RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'BUYUME_HORMONU'},
                uyari='SUT 4.2.14.A - Çocuk endokrinoloji uzman raporu gerekli (6 aylık)',
                sut_kurali='SUT 4.2.14.A — Büyüme hormonu çocuk endokrinoloji uzman raporu ile verilir'
            )
        uyarilar = ['Çocuk endokrinoloji veya endokrinoloji uzman raporu olmalı',
                    'Rapor süresi: 6 ay', 'Boy SDS / büyüme hızı raporda belirtilmeli']
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Büyüme hormonu — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'BUYUME_HORMONU', 'rapor_kodu': rapor_kodu},
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.14.A — Büyüme hormonu 6 aylık uzman raporu ile verilir'
        )

    # ── 3. Eritropoietin / ESA (SUT 4.2.30) ──
    esa_etkin = ['ERITROPOIETIN', 'ERITROPOETIN', 'EPOETIN', 'DARBEPOETIN',
                 'DARBEPOETIN ALFA', 'METOKSIPOLIETILENGLIKOL']
    esa_ilac = ['EPREX', 'NEORECORMON', 'ARANESP', 'MIRCERA', 'BINOCRIT',
                'RETACRIT', 'ERYPRO']
    esa_mi = any(_turkce_ara(etkin_madde, e) for e in esa_etkin) or \
             any(i in ilac_adi for i in esa_ilac)

    if esa_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'ESA ilacı RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'ESA_ERITROPOIETIN'},
                uyari='SUT 4.2.30 - Nefroloji/Hematoloji/Onkoloji uzman raporu gerekli',
                sut_kurali='SUT 4.2.30 — ESA ilaçları uzman raporu ile verilir'
            )
        uyarilar = ['Hemoglobin düzeyi raporda belirtilmeli (Hb < 10 g/dL başlama kriteri)',
                    'Hedef Hb: 10-12 g/dL aralığı']
        if metin:
            hb_var = _turkce_ara(metin, 'hemoglobin') or _turkce_ara(metin, 'hb') or \
                     _turkce_ara(metin, 'hgb')
            if hb_var:
                uyarilar.insert(0, 'Hemoglobin değeri raporda tespit edildi')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"ESA ilacı — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'ESA_ERITROPOIETIN', 'rapor_kodu': rapor_kodu},
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.30 — ESA ilaçları Hb düzeyi takibi ile uzman raporu gerektirir'
        )

    # ── 4. İmmünosüpresifler (SUT 4.2.32) ──
    immunsup_etkin = ['MIKOFENOLAT', 'MIKOFENOLAT MOFETIL', 'MIKOFENOLIK ASIT',
                      'TAKROLIMUS', 'SIKLOSPORIN', 'EVEROLIMUS', 'SIROLIMUS',
                      'AZATIOPRIN', 'BASILIKSIMAB']
    immunsup_ilac = ['CELLCEPT', 'MYFORTIC', 'PROGRAF', 'ADVAGRAF', 'ENVARSUS',
                     'SANDIMMUN', 'NEORAL', 'CERTICAN', 'RAPAMUNE',
                     'IMURAN', 'SIMULECT']
    immunsup_mi = any(_turkce_ara(etkin_madde, e) for e in immunsup_etkin) or \
                  any(i in ilac_adi for i in immunsup_ilac)

    if immunsup_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'İmmünosüpresif ilaç RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'IMMUNSUPRESIF'},
                uyari='SUT 4.2.32 - Transplantasyon/Otoimmün endikasyonda uzman raporu gerekli',
                sut_kurali='SUT 4.2.32 — İmmünosüpresif ilaçlar uzman raporu ile verilir'
            )
        # Transplantasyon vs otoimmün kontrol
        transplant = False
        if metin:
            transplant = _turkce_ara(metin, 'transplant') or _turkce_ara(metin, 'nakil') or \
                         _turkce_ara(metin, 'greft')
        endikasyon = 'Transplantasyon' if transplant else 'Belirlenemedi (transplant/otoimmün)'
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İmmünosüpresif — rapor kodu {rapor_kodu} ({endikasyon})",
            detaylar={'alt_kategori': 'IMMUNSUPRESIF', 'rapor_kodu': rapor_kodu, 'endikasyon': endikasyon},
            uyari='İlaç kan düzeyi takibi ve rapor süresi manuel kontrol edilmeli',
            sut_kurali='SUT 4.2.32 — İmmünosüpresif ilaçlar uzman raporu ile verilir'
        )

    # ── 5. Biyolojik İlaçlar / TNF İnhibitörleri (SUT 4.2.33) ──
    biyolojik_etkin = ['ADALIMUMAB', 'ETANERSEPT', 'INFLIKSIMAB', 'GOLIMUMAB',
                       'SERTOLIZUMAB', 'SEKUKINUMAB', 'IKSEKIZUMAB', 'USTEKINUMAB',
                       'VEDOLIZUMAB', 'TOFASITINIB', 'BARICITINIB', 'UPADACITINIB',
                       'GUSELKUMAB', 'RISANKIZUMAB', 'TOCILIZUMAB', 'SARILUMAB',
                       'ABATASEPT', 'RITUKSIMAB', 'BELIMUMAB', 'DUPILUMAB',
                       'OMALIZUMAB', 'BENRALIZUMAB', 'MEPOLIZUMAB']
    biyolojik_ilac = ['HUMIRA', 'ENBREL', 'REMICADE', 'SIMPONI', 'CIMZIA',
                      'COSENTYX', 'TALTZ', 'STELARA', 'ENTYVIO', 'XELJANZ',
                      'OLUMIANT', 'RINVOQ', 'TREMFYA', 'SKYRIZI', 'ACTEMRA',
                      'KEVZARA', 'ORENCIA', 'MABTHERA', 'BENLYSTA', 'DUPIXENT',
                      'XOLAIR', 'FASENRA', 'NUCALA', 'IMRALDI', 'HYRIMOZ',
                      'HADLIMA', 'HULIO', 'ERELZI', 'BENEPALI', 'INFLECTRA',
                      'REMSIMA', 'FLIXABI']
    biyolojik_mi = any(_turkce_ara(etkin_madde, e) for e in biyolojik_etkin) or \
                   any(i in ilac_adi for i in biyolojik_ilac)

    if biyolojik_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Biyolojik ilaç RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'BIYOLOJIK_TNF'},
                uyari='SUT 4.2.33 - İlgili branş uzman raporu gerekli, basamak tedavi şartı var',
                sut_kurali='SUT 4.2.33 — Biyolojik ilaçlar basamak tedavi sonrası uzman raporu ile verilir'
            )
        uyarilar = ['Basamak tedavi şartı: Konvansiyonel tedavilere yanıtsızlık raporda belirtilmeli',
                    'Rapor süresi ve tedavi yanıtı manuel kontrol edilmeli']
        # Endikasyon ipuçları
        if metin:
            if _turkce_ara(metin, 'romatoid') or _turkce_ara(metin, 'artrit'):
                uyarilar.append('Endikasyon ipucu: Romatoid Artrit')
            elif _turkce_ara(metin, 'psoriaz') or _turkce_ara(metin, 'sedef'):
                uyarilar.append('Endikasyon ipucu: Psoriazis')
            elif _turkce_ara(metin, 'crohn') or _turkce_ara(metin, 'kolitis') or _turkce_ara(metin, 'kolit'):
                uyarilar.append('Endikasyon ipucu: İnflamatuar Bağırsak Hastalığı')
            elif _turkce_ara(metin, 'ankilozan') or _turkce_ara(metin, 'spondilit'):
                uyarilar.append('Endikasyon ipucu: Ankilozan Spondilit')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Biyolojik ilaç — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'BIYOLOJIK_TNF', 'rapor_kodu': rapor_kodu},
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.33 — Biyolojik ilaçlar basamak tedavi sonrası uzman raporu ile verilir'
        )

    # ── 6. İmmünglobulinler (SUT 4.2.6) ──
    ivig_etkin = ['IMMUNOGLOBULIN', 'IMMÜNGLOBULIN', 'IMMUNGLOBULIN']
    ivig_ilac = ['OCTAGAM', 'PRIVIGEN', 'KIOVIG', 'FLEBOGAMMA', 'HIZENTRA',
                 'CUTAQUIG', 'INTRATECT', 'IVIG', 'SUBCUVIA']
    ivig_mi = any(_turkce_ara(etkin_madde, e) for e in ivig_etkin) or \
              any(i in ilac_adi for i in ivig_ilac)

    if ivig_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'İmmünglobulin RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'IMMUNOGLOBULIN'},
                uyari='SUT 4.2.6 - Hematoloji/Nöroloji/İmmünoloji uzman raporu gerekli',
                sut_kurali='SUT 4.2.6 — İmmünglobulinler uzman raporu ile verilir'
            )
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İmmünglobulin — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'IMMUNOGLOBULIN', 'rapor_kodu': rapor_kodu},
            uyari='Doz (g/kg) ve endikasyon raporda belirtilmeli | Rapor süresi manuel kontrol edilmeli',
            sut_kurali='SUT 4.2.6 — İmmünglobulinler uzman raporu ile verilir'
        )

    # ── 7. Koagülasyon Faktörleri (SUT 4.2.5) ──
    faktor_etkin = ['FAKTOR VIII', 'FAKTÖR VIII', 'FAKTOR IX', 'FAKTÖR IX',
                    'FAKTOR VII', 'FAKTÖR VII', 'VON WILLEBRAND',
                    'EMICIZUMAB', 'FITUSIRAN']
    faktor_ilac = ['ADVATE', 'KOGENATE', 'REFACTO', 'BENEFIX', 'NOVOSEVEN',
                   'HEMLIBRA', 'RIXUBIS', 'NUWIQ', 'ELOCTA', 'ALPROLIX',
                   'FEIBA', 'WILATE', 'HAEMATE', 'AFSTYLA']
    faktor_mi = any(_turkce_ara(etkin_madde, e) for e in faktor_etkin) or \
                any(i in ilac_adi for i in faktor_ilac)

    if faktor_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Koagülasyon faktörü RAPORSUZ yazılmış! Hematoloji raporu ZORUNLU',
                detaylar={'alt_kategori': 'KOAGULASYON_FAKTORU'},
                uyari='SUT 4.2.5 - Hematoloji uzman raporu gerekli',
                sut_kurali='SUT 4.2.5 — Koagülasyon faktörleri hematoloji uzman raporu ile verilir'
            )
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Koagülasyon faktörü — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'KOAGULASYON_FAKTORU', 'rapor_kodu': rapor_kodu},
            uyari='Faktör düzeyi ve profilaksi/tedavi dozu raporda belirtilmeli',
            sut_kurali='SUT 4.2.5 — Koagülasyon faktörleri hematoloji uzman raporu ile verilir'
        )

    # ── 8. Sistemik Antifungaller (SUT EK-4/E) ──
    antifungal_etkin = ['VORIKONAZOL', 'KASPOFUNGIN', 'ANIDULAFUNGIN', 'MIKAFUNGIN',
                        'AMFOTERISIN', 'POSAKONAZOL', 'ISAVUKONAZOL', 'FLUKONAZOL']
    antifungal_ilac = ['VFEND', 'CANCIDAS', 'ECALTA', 'MYCAMINE', 'AMBISOME',
                       'ABELCET', 'NOXAFIL', 'CRESEMBA', 'DIFLUCAN', 'TRIFLUCAN']
    antifungal_mi = any(_turkce_ara(etkin_madde, e) for e in antifungal_etkin) or \
                    any(i in ilac_adi for i in antifungal_ilac)

    if antifungal_mi:
        if not rapor_kodu:
            # Bazı antifungaller (flukonazol oral) raporsuz yazılabilir
            flukonazol_mi = _turkce_ara(etkin_madde, 'flukonazol') or \
                            any(i in ilac_adi for i in ['DIFLUCAN', 'TRIFLUCAN'])
            if flukonazol_mi:
                return KontrolRaporu(
                    KontrolSonucu.UYGUN,
                    'Flukonazol oral form raporsuz yazılabilir',
                    detaylar={'alt_kategori': 'ANTIFUNGAL_SISTEMIK'},
                    uyari='EK-4/E listesinde kısıtlama yok (oral form)'
                )
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Sistemik antifungal RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'ANTIFUNGAL_SISTEMIK'},
                uyari='SUT EK-4/E - Enfeksiyon hastalıkları uzman raporu gerekli',
                sut_kurali='SUT EK-4/E — Sistemik antifungaller uzman raporu ile verilir'
            )
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Sistemik antifungal — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'ANTIFUNGAL_SISTEMIK', 'rapor_kodu': rapor_kodu},
            uyari='Kültür/antifungal duyarlılık sonucu ve tedavi süresi raporda belirtilmeli',
            sut_kurali='SUT EK-4/E — Sistemik antifungaller uzman raporu ile verilir'
        )

    # ── 9. Pulmoner Hipertansiyon İlaçları (SUT 4.2.26) ──
    ph_etkin = ['BOSENTAN', 'AMBRISENTAN', 'MACITENTAN', 'SILDENAFIL', 'TADALAFIL',
                'RIOCIGUAT', 'SELEKSIPAG', 'ILOPROST', 'TREPROSTINIL', 'EPOPROSTENOL']
    ph_ilac = ['TRACLEER', 'VOLIBRIS', 'OPSUMIT', 'REVATIO', 'ADCIRCA',
               'ADEMPAS', 'UPTRAVI', 'VENTAVIS', 'REMODULIN', 'FLOLAN']
    # Sildenafil/Tadalafil PH dışında da kullanılır — rapor kodu ile ayır
    ph_rapor = rapor_kodu.startswith('04.') or rapor_kodu.startswith('05.') if rapor_kodu else False
    ph_mi = (any(_turkce_ara(etkin_madde, e) for e in ph_etkin) or
             any(i in ilac_adi for i in ph_ilac))
    # Sildenafil/Tadalafil sadece PH rapor kodu varsa bu kategoriye girer
    sild_tad = _turkce_ara(etkin_madde, 'sildenafil') or _turkce_ara(etkin_madde, 'tadalafil')
    if sild_tad and not ph_rapor:
        ph_mi = False  # PH rapor kodu yoksa genel raporlu olarak devam et

    if ph_mi and not sild_tad:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Pulmoner HT ilacı RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'PULMONER_HIPERTANSIYON'},
                uyari='SUT 4.2.26 - Kardiyoloji/Göğüs hastalıkları uzman raporu gerekli',
                sut_kurali='SUT 4.2.26 — Pulmoner HT ilaçları uzman raporu ile verilir'
            )
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Pulmoner HT ilacı — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'PULMONER_HIPERTANSIYON', 'rapor_kodu': rapor_kodu},
            uyari='PAB değeri ve fonksiyonel sınıf raporda belirtilmeli | Rapor süresi: 6 ay',
            sut_kurali='SUT 4.2.26 — Pulmoner HT ilaçları uzman raporu ile verilir'
        )

    # ── 10. Multipl Skleroz İlaçları (SUT 4.2.25) ──
    ms_etkin = ['INTERFERON BETA', 'GLATIRAMER', 'FINGOLIMOD', 'DIMETIL FUMARAT',
                'TERIFLUNOMID', 'NATALIZUMAB', 'ALEMTUZUMAB', 'OKRELIZUMAB',
                'SIPONIMOD', 'OZANIMOD', 'KLADRIBIN', 'OFATUMUMAB']
    ms_ilac = ['AVONEX', 'REBIF', 'BETAFERON', 'EXTAVIA', 'COPAXONE',
               'GILENYA', 'TECFIDERA', 'AUBAGIO', 'TYSABRI', 'LEMTRADA',
               'OCREVUS', 'MAYZENT', 'ZEPOSIA', 'MAVENCLAD', 'KESIMPTA']
    ms_mi = any(_turkce_ara(etkin_madde, e) for e in ms_etkin) or \
            any(i in ilac_adi for i in ms_ilac)

    if ms_mi:
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'MS ilacı RAPORSUZ yazılmış! Nöroloji uzman raporu ZORUNLU',
                detaylar={'alt_kategori': 'MULTIPL_SKLEROZ'},
                uyari='SUT 4.2.25 - Nöroloji uzman raporu gerekli',
                sut_kurali='SUT 4.2.25 — MS ilaçları nöroloji uzman raporu ile verilir'
            )
        uyarilar = ['EDSS skoru raporda belirtilmeli',
                    'Atak sıklığı ve MR bulguları kontrol edilmeli']
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"MS ilacı — rapor kodu {rapor_kodu}",
            detaylar={'alt_kategori': 'MULTIPL_SKLEROZ', 'rapor_kodu': rapor_kodu},
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.25 — MS ilaçları nöroloji uzman raporu ile verilir'
        )

    # ── 11. Genel Rapor Kodu Kontrolleri (alt-kategoriye uymayan) ──
    if rapor_kodu:
        # Rapor kodu var — temel kontroller
        detaylar = {'rapor_kodu': rapor_kodu, 'alt_kategori': 'GENEL'}

        # Rapor kodundan branş tahmini
        brans = None
        if rapor_kodu.startswith('01.'): brans = 'Romatoloji'
        elif rapor_kodu.startswith('02.'): brans = 'Onkoloji'
        elif rapor_kodu.startswith('03.'): brans = 'Üroloji/Nefroloji'
        elif rapor_kodu.startswith('04.'): brans = 'Kardiyoloji'
        elif rapor_kodu.startswith('05.'): brans = 'Göğüs Hastalıkları'
        elif rapor_kodu.startswith('06.'): brans = 'Ortopedi/Endokrin'
        elif rapor_kodu.startswith('07.'): brans = 'Endokrinoloji'
        elif rapor_kodu.startswith('08.'): brans = 'Hematoloji'
        elif rapor_kodu.startswith('09.'): brans = 'Kadın Hastalıkları'
        elif rapor_kodu.startswith('10.'): brans = 'Nöroloji'
        elif rapor_kodu.startswith('11.'): brans = 'Psikiyatri'
        elif rapor_kodu.startswith('12.'): brans = 'Göz Hastalıkları'
        elif rapor_kodu.startswith('13.'): brans = 'Dermatoloji'
        elif rapor_kodu.startswith('14.'): brans = 'Enfeksiyon Hastalıkları'
        elif rapor_kodu.startswith('15.'): brans = 'Gastroenteroloji'
        elif rapor_kodu.startswith('16.'): brans = 'Organ Nakli'
        elif rapor_kodu.startswith('20.'): brans = 'Genel'

        if brans:
            detaylar['brans_tahmini'] = brans

        uyari_parts = []
        uyari_parts.append(f'Rapor branşı: {brans}' if brans else 'Rapor branşı belirlenemedi')
        uyari_parts.append('Rapor içeriği ve süresi manuel kontrol edilmeli')

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Raporlu ilaç — rapor kodu {rapor_kodu}" + (f" ({brans})" if brans else ""),
            detaylar=detaylar,
            uyari=' | '.join(uyari_parts),
            sut_kurali='Rapor kodu mevcut — detaylı SUT kuralı alt-kategorilerde eşleşmedi'
        )

    # ── Rapor kodu yok ──
    return KontrolRaporu(
        KontrolSonucu.KONTROL_EDILEMEDI,
        'Rapor kodu bulunamadı — raporlu ilaç ise UYGUN DEĞİL olabilir',
        uyari='İlacın rapor zorunluluğu olup olmadığı kontrol edilmeli'
    )


def kontrol_onkoloji(ilac_sonuc: Dict) -> KontrolRaporu:
    """Onkoloji ilaçları (02.00) - Rapor var mı kontrolü"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Onkoloji rapor kodu mevcut ({rapor_kodu})",
                             uyari="Onkoloji protokolü manuel kontrol edilmeli")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Onkoloji rapor kodu bulunamadı")


def kontrol_noroloji(ilac_sonuc: Dict) -> KontrolRaporu:
    """Nöroloji ilaçları - Uzman raporu kontrolü"""
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Nöroloji rapor kodu mevcut ({rapor_kodu})")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Nöroloji rapor bilgisi eksik")


def kontrol_goz(ilac_sonuc: Dict) -> KontrolRaporu:
    """Göz ilaçları - Rapor kontrolü"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Göz rapor kodu mevcut ({rapor_kodu})")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Göz rapor bilgisi eksik")


def kontrol_antiviral(ilac_sonuc: Dict) -> KontrolRaporu:
    """Antiviral ilaçlar - Rapor kontrolü"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Antiviral rapor kodu mevcut ({rapor_kodu})")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Antiviral rapor bilgisi eksik")


def kontrol_gis(ilac_sonuc: Dict) -> KontrolRaporu:
    """GİS ilaçları - Rapor kontrolü"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"GİS rapor kodu mevcut ({rapor_kodu})")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "GİS rapor bilgisi eksik")


def kontrol_recete_turu_kirmizi(ilac_sonuc: Dict) -> KontrolRaporu:
    """Kırmızı reçete gerektiren ilaçlar (Tramadol vb.) - SUT 4.2.4"""
    recete_turu = ilac_sonuc.get('recete_turu', 'Normal')
    if recete_turu == 'Kırmızı':
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Kırmızı reçete - uygun")
    return KontrolRaporu(KontrolSonucu.UYGUN,
                         f"Reçete türü: {recete_turu} (kırmızı reçete kontrolü yapılmalı)",
                         uyari="Tramadol/opioid - kırmızı reçete zorunlu")


def kontrol_recete_turu_yesil(ilac_sonuc: Dict) -> KontrolRaporu:
    """Yeşil reçete gerektiren ilaçlar (Biperiden vb.)"""
    recete_turu = ilac_sonuc.get('recete_turu', 'Normal')
    if recete_turu == 'Yeşil':
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Yeşil reçete - uygun")
    return KontrolRaporu(KontrolSonucu.UYGUN,
                         f"Reçete türü: {recete_turu} (yeşil reçete kontrolü yapılmalı)",
                         uyari="Biperiden - yeşil reçete zorunlu")


def kontrol_trimetazidin(ilac_sonuc: Dict) -> KontrolRaporu:
    """Trimetazidin (SUT 4.2.14.C) - Kardiyoloji uzman raporu zorunlu"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    metin = _tum_metinleri_birlesir(ilac_sonuc)

    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Trimetazidin - rapor mevcut ({rapor_kodu})")
    if not rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                             "Trimetazidin RAPORSUZ yazılmış! Kardiyoloji uzman raporu ZORUNLU",
                             uyari="SUT 4.2.14.C - raporsuz verilemez")


def kontrol_dmah(ilac_sonuc: Dict) -> KontrolRaporu:
    """DMAH/Enoksaparin (SUT 4.2.7) - Rapor + uyarı kodu zorunlu"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')

    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"DMAH - rapor mevcut ({rapor_kodu})",
                             uyari="Uyarı kodu 280(başlangıç)/281(idame) kontrol edilmeli")
    return KontrolRaporu(KontrolSonucu.UYGUN_DEGIL,
                         "DMAH/Enoksaparin RAPORSUZ yazılmış! Rapor ZORUNLU",
                         uyari="SUT 4.2.7 - raporsuz verilemez")


def kontrol_kadin_hormon(ilac_sonuc: Dict) -> KontrolRaporu:
    """Kadın cinsiyet hormonları (SUT 4.2.29)"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Kadın hormonu - rapor mevcut ({rapor_kodu})")
    return KontrolRaporu(KontrolSonucu.UYGUN,
                         "Kadın hormonu raporsuz - kısa süreli kullanım olabilir",
                         uyari="SUT 4.2.29 - uzun süreli kullanımda rapor gerekli")


def kontrol_antibiyotik_florokinolon(ilac_sonuc: Dict) -> KontrolRaporu:
    """Florokinolon antibiyotikler (EK-4/E) - Kültür antibiyogram"""
    return KontrolRaporu(KontrolSonucu.UYGUN,
                         "Florokinolon antibiyotik - ayaktan tedavide raporsuz verilebilir",
                         uyari="EK-4/E: Pnömoni dışı endikasyonlarda kültür antibiyogram önerilir")


def kontrol_raporsuz_bilgilendirme(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Raporsuz verilebilen ilaçlar - detaylı SUT kontrolleri.

    Bu kategori: NSAİD'ler, antihistaminikler, dekonjestanlar, antifungaller,
    makrolid antibiyotikler, MAO-B inhibitörleri (Parkinson) vb.

    Her alt grup için SUT mevzuatına göre:
    - Rapor gereksinimi
    - Uzman/branş kısıtlaması
    - Doz/süre kısıtlamaları
    - Kombinasyon kontrolleri
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper().strip()
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper().strip()
    recete_turu = ilac_sonuc.get('recete_turu', 'Normal')

    detaylar = {
        'etkin_madde': etkin_madde,
        'ilac_adi': ilac_adi,
        'rapor_kodu': rapor_kodu,
        'alt_kategori': 'bilinmiyor',
    }

    # ── Alt kategori tespiti ──
    # MAO-B İnhibitörleri (Selegilin, Rasagilin, Safinamid) - Parkinson
    maob_maddeler = ['SELEGILIN', 'RASAGILIN', 'SAFINAMID']
    maob_ticari = ['AZILECT', 'XADAGO']
    is_maob = any(m in etkin_madde for m in maob_maddeler) or any(t in ilac_adi for t in maob_ticari)

    # NSAİD'ler (İbuprofen, Parasetamol vb.)
    nsaid_maddeler = ['IBUPROFEN', 'PARASETAMOL', 'NAPROKSEN', 'DIKLOFENAK',
                      'MELOKSIKAM', 'PIROKSIKAM', 'INDOMETAZIN', 'KETOPROFEN',
                      'FLURBIPROFEN', 'DEKSKETOPROFEN', 'ETODOLAK', 'LORNOKSIKAM',
                      'TENOKSIKAM', 'ASETILSALISILIK']
    is_nsaid = any(m in etkin_madde for m in nsaid_maddeler)

    # Makrolid antibiyotikler (Klaritromisin, Azitromisin)
    makrolid_maddeler = ['KLARITROMISIN', 'AZITROMISIN', 'ERITROMISIN', 'ROKSITROMISIN']
    makrolid_ticari = ['MACROL', 'KLACID', 'DEZEST', 'AZITRO']
    is_makrolid = (any(m in etkin_madde for m in makrolid_maddeler) or
                   any(t in ilac_adi for t in makrolid_ticari))

    # Antihistaminikler (Desloratadin, Klorfeniramin, Setirizin)
    antihist_maddeler = ['DESLORATADIN', 'KLORFENIRAMIN', 'SETIRIZIN', 'LORATADIN',
                         'FEKSOFENADRIN', 'LEVOSETRIZIN', 'EBASTIN', 'RUPATADIN']
    is_antihistaminik = any(m in etkin_madde for m in antihist_maddeler)

    # Dekonjestanlar / Soğuk algınlığı kombinasyonları
    dekonjestan_maddeler = ['FENILEFRIN', 'PSEUDOEFEDRIN', 'OKSIMETAZOLIN']
    dekonjestan_ticari = ['IBUCOLD', 'A-FERIN', 'THERAFLU', 'TYLOLHOT', 'NUROFEN']
    is_dekonjestan = (any(m in etkin_madde for m in dekonjestan_maddeler) or
                      any(t in ilac_adi for t in dekonjestan_ticari))

    # Topikal antifungal/antiseptik (Oksikonazol, Benzidamin)
    topikal_maddeler = ['OKSIKONAZOL', 'BENZIDAMIN', 'MIKONAZOL', 'KLOTRIMAZOL',
                        'TERBINAFIN', 'KETOKONAZOL', 'NISTATIN']
    topikal_ticari = ['TRAVAZOL', 'OCERAL', 'ANDOREX', 'TANTUM']
    is_topikal = (any(m in etkin_madde for m in topikal_maddeler) or
                  any(t in ilac_adi for t in topikal_ticari))

    # ══════════════════════════════════════════════════════════════
    # 1. MAO-B İnhibitörleri (Selegilin, Rasagilin, Safinamid)
    # SUT: Nöroloji uzmanı raporsuz yazabilir, diğer hekimler rapor ile
    # Parkinson tanısı (G20) gerekli
    # Doz: Selegilin maks 10 mg/gün, Rasagilin maks 1 mg/gün
    # Kombinasyon: SSRI/SNRI ile birlikte kullanım kontrendike (serotonin sendromu)
    # ══════════════════════════════════════════════════════════════
    if is_maob:
        detaylar['alt_kategori'] = 'MAO-B_INHIBITORU'

        uyarilar = []
        uyarilar.append("Nöroloji uzmanı raporsuz yazabilir, diğer hekimler rapor ile yazabilir")

        # Selegilin spesifik kontroller
        if 'SELEGILIN' in etkin_madde:
            uyarilar.append("Selegilin maks doz: 10 mg/gün (genellikle 5 mg 2x1)")
            uyarilar.append("Tiraminden zengin gıdalarla etkileşim riski (peynir efekti)")

            # Doz bilgisi metin veya raporda varsa kontrol et
            if metin:
                doz_match = re.search(r'(\d+)\s*mg', metin, re.IGNORECASE)
                if doz_match:
                    doz = int(doz_match.group(1))
                    if doz > 10:
                        return KontrolRaporu(
                            KontrolSonucu.UYGUN_DEGIL,
                            f"Selegilin dozu ({doz} mg) maksimum dozu (10 mg/gün) aşıyor",
                            detaylar=detaylar,
                            uyari="SUT: Selegilin günlük maks doz 10 mg"
                        )

        elif 'RASAGILIN' in etkin_madde:
            uyarilar.append("Rasagilin maks doz: 1 mg/gün")
        elif 'SAFINAMID' in etkin_madde:
            uyarilar.append("Safinamid maks doz: 100 mg/gün, L-DOPA ile birlikte kullanılmalı")

        # Kombinasyon uyarısı (tüm MAO-B inhibitörleri için)
        uyarilar.append("KOMBİNASYON UYARISI: SSRI/SNRI ile birlikte serotonin sendromu riski")
        uyarilar.append("Aynı reçetede etkin madde tekrarı kontrol edilmeli")

        # Rapor varsa
        if rapor_kodu:
            # Parkinson tanısı kontrolü
            parkinson_bulundu = False
            if metin:
                parkinson_bulundu = (_turkce_ara(metin, 'parkinson') or
                                     bool(re.search(r'G20|G21|G22', metin, re.IGNORECASE)))
            if parkinson_bulundu:
                detaylar['tani'] = 'Parkinson (G20)'
                return KontrolRaporu(
                    KontrolSonucu.UYGUN,
                    f"MAO-B inhibitörü - Parkinson tanısı raporda mevcut ({rapor_kodu})",
                    detaylar=detaylar,
                    uyari=" | ".join(uyarilar)
                )
            else:
                return KontrolRaporu(
                    KontrolSonucu.KONTROL_EDILEMEDI,
                    f"MAO-B inhibitörü - rapor mevcut ({rapor_kodu}) ama Parkinson tanısı (G20) doğrulanamadı",
                    detaylar=detaylar,
                    uyari=" | ".join(uyarilar)
                )

        # Rapor yok - nöroloji uzmanı raporsuz yazabilir
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "MAO-B inhibitörü (Parkinson) - raporsuz verilebilir (nöroloji uzmanı)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 2. Makrolid Antibiyotikler (EK-4/E)
    # SUT: Ayaktan tedavide raporsuz, kısıtlama yok
    # Süre: Klaritromisin genellikle 7-14 gün, Azitromisin 3-5 gün
    # Uyarı: Uzun QT sendromu riski, ilaç etkileşimleri
    # ══════════════════════════════════════════════════════════════
    if is_makrolid:
        detaylar['alt_kategori'] = 'MAKROLID_ANTIBIYOTIK'

        uyarilar = ["EK-4/E: Ayaktan tedavide tüm hekimler raporsuz yazabilir"]

        if 'KLARITROMISIN' in etkin_madde or 'MACROL' in ilac_adi or 'KLACID' in ilac_adi:
            uyarilar.append("Klaritromisin: Genellikle 7-14 gün, maks 14 gün")
            uyarilar.append("Statin ile etkileşim: Rabdomiyoliz riski (özellikle simvastatin)")
        elif 'AZITROMISIN' in etkin_madde:
            uyarilar.append("Azitromisin: Genellikle 3-5 gün tedavi")

        uyarilar.append("Aynı reçetede etkin madde tekrarı kontrol edilmeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Makrolid antibiyotik - ayaktan tedavide raporsuz verilebilir (EK-4/E)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 3. NSAİD'ler (İbuprofen, Parasetamol vb.)
    # SUT: Raporsuz, tüm hekimler yazabilir
    # Doz: İbuprofen maks 2400 mg/gün, Parasetamol maks 4000 mg/gün
    # Süre: Uzun süreli kullanımda GİS koruma gerekli
    # Kombinasyon: İki NSAİD aynı reçetede UYGUN DEĞİL
    # ══════════════════════════════════════════════════════════════
    if is_nsaid:
        detaylar['alt_kategori'] = 'NSAID'

        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'IBUPROFEN' in etkin_madde:
            uyarilar.append("İbuprofen maks doz: 2400 mg/gün (genellikle 400-600 mg 3x1)")
        elif 'PARASETAMOL' in etkin_madde:
            uyarilar.append("Parasetamol maks doz: 4000 mg/gün (genellikle 500 mg 3-4x1)")
        elif 'DIKLOFENAK' in etkin_madde:
            uyarilar.append("Diklofenak maks doz: 150 mg/gün")
        elif 'NAPROKSEN' in etkin_madde:
            uyarilar.append("Naproksen maks doz: 1100 mg/gün")

        uyarilar.append("KOMBİNASYON: Aynı reçetede birden fazla NSAİD kontrol edilmeli")
        uyarilar.append("Uzun süreli kullanımda GİS koruyucu (PPI) gerekebilir")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "NSAİD - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 4. Antihistaminikler (Desloratadin, Setirizin vb.)
    # SUT: Raporsuz, tüm hekimler yazabilir
    # 1. jenerasyon (Klorfeniramin): Sedasyon uyarısı
    # 2. jenerasyon (Desloratadin, Setirizin): Daha güvenli profil
    # ══════════════════════════════════════════════════════════════
    if is_antihistaminik:
        detaylar['alt_kategori'] = 'ANTIHISTAMINIK'

        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        jenerasyon1 = ['KLORFENIRAMIN', 'DIFENHIDRAMIN', 'PROMETAZIN', 'HIDROKSIZIN']
        if any(m in etkin_madde for m in jenerasyon1):
            uyarilar.append("1. jenerasyon antihistaminik: Sedasyon uyarısı, araç kullanımı")
        else:
            uyarilar.append("2. jenerasyon antihistaminik: Sedasyon riski düşük")

        uyarilar.append("Aynı reçetede etkin madde tekrarı kontrol edilmeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antihistaminik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 5. Dekonjestanlar / Soğuk algınlığı kombinasyonları
    # SUT: Raporsuz, tüm hekimler
    # Süre: Nazal dekonjestanlar maks 5-7 gün
    # Uyarı: Pseudoefedrin - hipertansiyon, kardiyak risk
    # ══════════════════════════════════════════════════════════════
    if is_dekonjestan:
        detaylar['alt_kategori'] = 'DEKONJESTAN'

        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'PSEUDOEFEDRIN' in etkin_madde:
            uyarilar.append("Pseudoefedrin: Hipertansiyon/kardiyak hastada dikkat")
        if 'FENILEFRIN' in etkin_madde:
            uyarilar.append("Fenilefrin: Nazal form maks 5-7 gün")

        uyarilar.append("Soğuk algınlığı kombinasyonlarında etkin madde çakışması kontrol edilmeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Dekonjestan/soğuk algınlığı ilacı - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 6. Topikal antifungal/antiseptik
    # SUT: Raporsuz, tüm hekimler
    # Süre: Topikal antifungal genellikle 2-4 hafta
    # ══════════════════════════════════════════════════════════════
    if is_topikal:
        detaylar['alt_kategori'] = 'TOPIKAL_ANTIFUNGAL'

        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'BENZIDAMIN' in etkin_madde or 'ANDOREX' in ilac_adi or 'TANTUM' in ilac_adi:
            uyarilar.append("Benzidamin: Antiinflamatuar gargara/sprey, kısa süreli kullanım")
        else:
            uyarilar.append("Topikal antifungal: Genellikle 2-4 hafta tedavi süresi")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Topikal antifungal/antiseptik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 7. Genel raporsuz bilgilendirme (alt kategori tespit edilemedi)
    # ══════════════════════════════════════════════════════════════
    detaylar['alt_kategori'] = 'GENEL_RAPORSUZ'
    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        "Raporsuz verilebilir - mesaj bilgilendirme amaçlı",
        detaylar=detaylar,
        uyari="Aynı reçetede etkin madde tekrarı kontrol edilmeli"
    )


def kontrol_mono_antihipertansif(ilac_sonuc: Dict) -> KontrolRaporu:
    """Mono antihipertansifler - raporsuz verilebilir"""
    return KontrolRaporu(KontrolSonucu.UYGUN,
                         "Mono antihipertansif - raporsuz verilebilir")


def kontrol_potasyum_sitrat(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Potasyum Sitrat (EK-4/F) - Üroloji/Nefroloji uzman raporu kontrolü

    SUT kuralı:
    - Nefroloji veya üroloji uzman hekimlerince raporsuz reçetelenir
    - Bu hekimlerce düzenlenen 6 ay süreli uzman hekim raporuyla tüm hekimler reçeteleyebilir
    - ICD: N25.8, N25.9 (renal tübüler asidoz), N20.0, N20.1 (böbrek taşı)
    - N20.0/N20.1 için: en az 1 kez girişimsel tedavi (ESWL/cerrahi) + idrar pH < 6.5
    """
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    metin = _tum_metinleri_birlesir(ilac_sonuc)

    # Rapor kodu yoksa - raporsuz yazılmış
    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            "Potasyum sitrat raporsuz yazılmış",
            uyari="EK-4/F: Üroloji/Nefroloji uzmanı raporsuz yazabilir, diğer hekimler 6 ay süreli uzman raporu ile yazabilir"
        )

    # Rapor kodu var - metin kontrolü
    if not metin:
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f"Rapor kodu mevcut ({rapor_kodu}) ama rapor metni okunamadı",
            uyari="Üroloji/Nefroloji uzman raporu kontrol edilmeli"
        )

    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()

    # Uzman branş kontrolü
    uroloji = bool(re.search(r'üroloji|uroloji', metin_lower))
    nefroloji = bool(re.search(r'nefroloji', metin_lower))

    # Tanı/endikasyon kontrolü
    rta = bool(re.search(r'renal\s*tübüler\s*asidoz|RTA', metin, re.IGNORECASE))
    bobrek_tasi = bool(re.search(r'böbrek\s*taşı|bobrek\s*tasi|renal\s*kalkül|nefrolitiazis|ürolitiazis|urolitiazis', metin_lower))
    asidoz = _turkce_ara(metin, 'asidoz') or _turkce_ara(metin, 'acidoz')

    # ICD kodu kontrolü
    icd_n25 = bool(re.search(r'N25[.\s]*[89]', metin, re.IGNORECASE))
    icd_n20 = bool(re.search(r'N20[.\s]*[01]', metin, re.IGNORECASE))

    # Girişimsel tedavi kontrolü (N20 için gerekli)
    girisimsel = bool(re.search(r'ESWL|cerrahi|girişimsel|girisimsel|litotripsi|nefrolitotomi|üreteroskopi|ureteroskopi', metin, re.IGNORECASE))
    ph_kontrol = bool(re.search(r'pH\s*[<≤]?\s*6[.,]5|idrar\s*pH', metin, re.IGNORECASE))

    # Değerlendirme
    if icd_n25 or rta:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Renal tübüler asidoz tanısı raporda mevcut (N25.8/N25.9)",
            detaylar={'icd': 'N25', 'rta': rta, 'uzman': 'üroloji' if uroloji else ('nefroloji' if nefroloji else 'bilinmiyor')}
        )

    if icd_n20 or bobrek_tasi:
        if girisimsel and ph_kontrol:
            return KontrolRaporu(
                KontrolSonucu.UYGUN,
                "Böbrek taşı + girişimsel tedavi + pH < 6.5 koşulları raporda mevcut",
                detaylar={'icd': 'N20', 'girisimsel': True, 'ph': True}
            )
        elif girisimsel:
            return KontrolRaporu(
                KontrolSonucu.UYGUN,
                "Böbrek taşı + girişimsel tedavi raporda mevcut",
                uyari="İdrar pH < 6.5 bilgisi kontrol edilmeli",
                detaylar={'icd': 'N20', 'girisimsel': True, 'ph': False}
            )
        else:
            return KontrolRaporu(
                KontrolSonucu.KONTROL_EDILEMEDI,
                "Böbrek taşı tanısı var ama girişimsel tedavi bilgisi bulunamadı",
                uyari="ESWL/cerrahi öyküsü ve idrar pH < 6.5 kontrol edilmeli"
            )

    if uroloji or nefroloji:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"{'Üroloji' if uroloji else 'Nefroloji'} uzman raporu mevcut",
            uyari="Tanı detayları (RTA/böbrek taşı) manuel kontrol edilmeli"
        )

    if asidoz:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Asidoz tanısı raporda mevcut",
            uyari="Üroloji/Nefroloji uzman raporu olduğu kontrol edilmeli"
        )

    return KontrolRaporu(
        KontrolSonucu.KONTROL_EDILEMEDI,
        "Potasyum sitrat endikasyonu (RTA/böbrek taşı/üroloji-nefroloji uzmanı) tespit edilemedi",
        uyari="EK-4/F: Üroloji veya Nefroloji uzman raporu gerekli"
    )


# Kategori -> kontrol fonksiyonu eşleştirme
KATEGORI_KONTROL_FONKSIYONU = {
    'KOMBINE_ANTIHIPERTANSIF': kontrol_kombine_antihipertansif,
    'DIYABET_DPP4_SGLT2': kontrol_diyabet_dpp4_sglt2,
    'KLOPIDOGREL': kontrol_klopidogrel,
    'STATIN': kontrol_statin,
    'FIBRAT': kontrol_fibrat,
    'YOAK': kontrol_yoak,
    'IVABRADIN': kontrol_ivabradin,
    'PSIKIYATRI': kontrol_psikiyatri,
    'SOLUNUM': kontrol_solunum,
    'GENEL_RAPORLU': kontrol_genel_raporlu,
    'ONKOLOJI': kontrol_onkoloji,
    'NOROLOJI': kontrol_noroloji,
    'GOZ': kontrol_goz,
    'ANTIVIRAL': kontrol_antiviral,
    'GIS': kontrol_gis,
    'EPLERENON': kontrol_ivabradin,  # Benzer koşullar (KY+EF)
    'RANOLAZIN': kontrol_ranolazin,
    'RECETE_TURU_KIRMIZI': kontrol_recete_turu_kirmizi,
    'RECETE_TURU_YESIL': kontrol_recete_turu_yesil,
    'TRIMETAZIDIN': kontrol_trimetazidin,
    'DMAH': kontrol_dmah,
    'KADIN_HORMON': kontrol_kadin_hormon,
    'ANTIBIYOTIK_FLOROKINOLON': kontrol_antibiyotik_florokinolon,
    'RAPORSUZ_BILGILENDIRME': kontrol_raporsuz_bilgilendirme,
    'MONO_ANTIHIPERTANSIF': kontrol_mono_antihipertansif,
    'POTASYUM_SITRAT': kontrol_potasyum_sitrat,
    'BIFOSFONAT': kontrol_bifosfonat,
}

KATEGORI_ISIMLERI = {
    'KOMBINE_ANTIHIPERTANSIF': 'Kombine Antihipertansif (4.2.12.B)',
    'DIYABET_DPP4_SGLT2': 'DPP-4/SGLT-2/GLP-1 (4.2.38)',
    'KLOPIDOGREL': 'Klopidogrel/Prasugrel/Tikagrelor (4.2.15)',
    'STATIN': 'Statin (4.2.28.A)',
    'FIBRAT': 'Fibrat (4.2.28.B)',
    'YOAK': 'YOAK - Yeni Oral Antikoagülan (4.2.15.D)',
    'IVABRADIN': 'İvabradin (4.2.15.C)',
    'EPLERENON': 'Eplerenon (EK-4/F)',
    'RANOLAZIN': 'Ranolazin (4.2.15.F)',
    'PSIKIYATRI': 'Psikiyatri İlaçları (4.2.2)',
    'SOLUNUM': 'Solunum İlaçları (4.2.9/4.2.24.B)',
    'GENEL_RAPORLU': 'Genel Raporlu İlaç',
    'ONKOLOJI': 'Onkoloji İlaçları',
    'NOROLOJI': 'Nöroloji İlaçları',
    'GOZ': 'Göz İlaçları',
    'ANTIVIRAL': 'Antiviral İlaçlar',
    'GIS': 'GİS İlaçları',
    'BIFOSFONAT': 'Bifosfonat/Osteoporoz (4.2.17)',
    'RECETE_TURU_KIRMIZI': 'Kırmızı Reçete Zorunlu (4.2.4)',
    'RECETE_TURU_YESIL': 'Yeşil Reçete Zorunlu',
    'TRIMETAZIDIN': 'Trimetazidin (4.2.14.C)',
    'DMAH': 'DMAH/Enoksaparin (4.2.7)',
    'KADIN_HORMON': 'Kadın Cinsiyet Hormonları (4.2.29)',
    'ANTIBIYOTIK_FLOROKINOLON': 'Florokinolon Antibiyotik (EK-4/E)',
    'RAPORSUZ_BILGILENDIRME': 'Raporsuz Verilebilir',
    'MONO_ANTIHIPERTANSIF': 'Mono Antihipertansif',
    'POTASYUM_SITRAT': 'Potasyum Sitrat (EK-4/F)',
}


def sut_kontrol_yap(ilac_sonuc: Dict) -> Optional[Dict]:
    """
    İlaç kontrol sonucu üzerinden SUT kontrolü yap.

    Args:
        ilac_sonuc: ilac_kontrolu_yap() dönüş değeri

    Returns:
        dict: {
            'kategori': str,
            'kategori_adi': str,
            'kontrol_raporu': KontrolRaporu,
        } veya None (SUT kategorisi bulunamadıysa)
    """
    # Kategori tespit et
    kategori = sut_kategorisi_tespit_et(ilac_sonuc)
    if not kategori:
        return None

    kategori_adi = KATEGORI_ISIMLERI.get(kategori, kategori)
    ilac_adi = ilac_sonuc.get('ilac_adi', '?')

    logger.info(f"🏷 SUT Kategori: {kategori_adi} | İlaç: {ilac_adi}")

    # Uygun kontrol fonksiyonunu çalıştır
    kontrol_fonk = KATEGORI_KONTROL_FONKSIYONU.get(kategori)
    if not kontrol_fonk:
        logger.warning(f"Kategori {kategori} için kontrol fonksiyonu yok")
        return None

    rapor = kontrol_fonk(ilac_sonuc)

    # Sonucu logla
    if rapor.sonuc == KontrolSonucu.UYGUN:
        logger.info(f"  ✓ {rapor.mesaj}")
    elif rapor.sonuc == KontrolSonucu.UYGUN_DEGIL:
        logger.warning(f"  ✗ {rapor.mesaj}")
    else:
        logger.info(f"  ? {rapor.mesaj}")

    if rapor.uyari:
        logger.info(f"  📌 {rapor.uyari}")

    return {
        'kategori': kategori,
        'kategori_adi': kategori_adi,
        'kontrol_raporu': rapor,
    }
