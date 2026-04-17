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
    '15.04': 'SOLUNUM',               # Solunum raporlu (nebülizasyon vb.)
    '15.05': 'SOLUNUM',               # Solunum raporlu
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

    # İnkontinans antimuskarinikler (SUT 4.2.16.B)
    'SOLIFENASIN': 'INKONTINANS', 'SOLIFENASIN SUKSINAT': 'INKONTINANS',
    'TOLTERODIN': 'INKONTINANS', 'TOLTERODIN L-TARTRAT': 'INKONTINANS',
    'OKSIBUTININ': 'INKONTINANS', 'PROPIVERIN': 'INKONTINANS',
    'FESOTERODIN': 'INKONTINANS', 'FESOTERODIN FUMARAT': 'INKONTINANS',
    'TROSPIUM': 'INKONTINANS', 'DARIFENASIN': 'INKONTINANS',
    'MIRABEGRON': 'INKONTINANS',

    # BPH - 5α redüktaz (rapor) / Alfa bloker (raporsuz)
    'DUTASTERID': 'BPH_PROSTAT', 'FINASTERID': 'BPH_PROSTAT',
    'TAMSULOSIN': 'BPH_PROSTAT', 'ALFUZOSIN': 'BPH_PROSTAT',
    'SILODOSIN': 'BPH_PROSTAT', 'DOKSAZOSIN': 'BPH_PROSTAT',
    'TERAZOSIN': 'BPH_PROSTAT',
    'DUTASTERID+TAMSULOSIN': 'BPH_PROSTAT',

    # IV Demir
    'DEMIR KARBOKSIMALTOZ': 'DEMIR_IV',
    'DEMIR SUKROZ': 'DEMIR_IV',
    'DEMIR IZOMALTOSIT': 'DEMIR_IV',
    'FERRIK KARBOKSIMALTOZ': 'DEMIR_IV',

    # Desmopresin
    'DESMOPRESIN': 'DESMOPRESIN',
    'DESMOPRESIN ASETAT': 'DESMOPRESIN',

    # Nöropatik ağrı (SUT)
    'GABAPENTIN': 'NOROPATIK_AGRI',
    'PREGABALIN': 'NOROPATIK_AGRI',
    # DULOKSETIN aynı zamanda PSIKIYATRI — rapor kodu 20.x/nöropati ise nöropatik,
    # 11.04 ise psikiyatri. Kategori: PSIKIYATRI (zaten var), nöropatik koşullarda
    # ayrı subroutine'e yönlendirmek için kontrol_psikiyatri içinde değerlendirilmeli.

    # Antiviral detaylı (Hepatit B/C, HIV) — zaten ANTIVIRAL var, detaylı subroutine
    # kontrol_antiviral içinde çağrılacak.

    # Enteral beslenme
    'KAZEIN': 'ENTERAL_BESLENME',
    'MALTODEKSTRIN': 'ENTERAL_BESLENME',
    'SOYA PROTEIN IZOLATI': 'ENTERAL_BESLENME',
    'PEPTON': 'ENTERAL_BESLENME',
    'AMINO ASIT KARISIMI': 'ENTERAL_BESLENME',

    # ESA / Eritropoietin (SUT 4.2.30 - Nefroloji/Hematoloji/Onkoloji uzman raporu)
    # Kontrol fonksiyonu: kontrol_genel_raporlu içinde (ESA subroutine)
    'ERITROPOIETIN': 'GENEL_RAPORLU',
    'ERITROPOETIN': 'GENEL_RAPORLU',
    'EPOETIN': 'GENEL_RAPORLU',
    'EPOETIN ALFA': 'GENEL_RAPORLU',
    'EPOETIN BETA': 'GENEL_RAPORLU',
    'EPOETIN ZETA': 'GENEL_RAPORLU',
    'DARBEPOETIN': 'GENEL_RAPORLU',
    'DARBEPOETIN ALFA': 'GENEL_RAPORLU',
    'METOKSIPOLIETILENGLIKOL': 'GENEL_RAPORLU',
    'METOKSIPOLIETILENGLIKOL EPOETIN BETA': 'GENEL_RAPORLU',

    # ANTIVIRAL - HIV/Hepatit B/C (SUT 4.2.13 - özel kontrol fonksiyonu yok, rapor bazlı)
    # Bu ilaçlar listelendiğinde rapor kodu 06.01 bifosfonatla karışmasın diye ANTIVIRAL döner
    'TENOFOVIR': 'ANTIVIRAL',
    'TENOFOVIR DISOPROKSIL': 'ANTIVIRAL',
    'TENOFOVIR DISOPROKSIL FUMARAT': 'ANTIVIRAL',
    'TENOFOVIR ALAFENAMID': 'ANTIVIRAL',
    'ENTEKAVIR': 'ANTIVIRAL',
    'ADEFOVIR': 'ANTIVIRAL',
    'LAMIVUDIN': 'ANTIVIRAL',
    'EMTRISITABIN': 'ANTIVIRAL',
    'SOFOSBUVIR': 'ANTIVIRAL',
    'LEDIPASVIR': 'ANTIVIRAL',
    'VELPATASVIR': 'ANTIVIRAL',
    'GLEKAPREVIR': 'ANTIVIRAL',
    'PIBRENTASVIR': 'ANTIVIRAL',
    'DOLUTEGRAVIR': 'ANTIVIRAL',
    'ABACAVIR': 'ANTIVIRAL',
    'EFAVIRENZ': 'ANTIVIRAL',

    # BENZODIAZEPIN / Anksiyolitik (SUT raporsuz, sadece uzman hekim)
    'ALPRAZOLAM': 'BENZODIAZEPIN',
    'DIAZEPAM': 'BENZODIAZEPIN',
    'LORAZEPAM': 'BENZODIAZEPIN',
    'KLONAZEPAM': 'BENZODIAZEPIN',
    'BROMAZEPAM': 'BENZODIAZEPIN',
    'KLORDIAZEPOKSID': 'BENZODIAZEPIN',

    # ADHD (SUT 4.2.34.B — çocuk psikiyatrisi raporu)
    'ATOMOKSETIN': 'ADHD',
    'ATOMOKSETIN HCL': 'ADHD',
    'METILFENIDAT': 'ADHD',
    'METILFENIDAT HCL': 'ADHD',

    # Suni gözyaşı / göz lubrikan (raporsuz)
    'POLIVINIL ALKOL': 'GOZ_LUBRIKAN',
    'KARBOMER': 'GOZ_LUBRIKAN',
    'HIPROMELLOZ': 'GOZ_LUBRIKAN',
    'SODYUM HYALURONAT': 'GOZ_LUBRIKAN',

    # Mono antihipertansif (ACE inhibitörleri, ARB, kalsiyum kanal blokerleri vb.)
    'RAMIPRIL': 'MONO_ANTIHIPERTANSIF',
    'ENALAPRIL': 'MONO_ANTIHIPERTANSIF',
    'LISINOPRIL': 'MONO_ANTIHIPERTANSIF',
    'PERINDOPRIL': 'MONO_ANTIHIPERTANSIF',
    'KAPTOPRIL': 'MONO_ANTIHIPERTANSIF',
    'AMLODIPIN': 'MONO_ANTIHIPERTANSIF',
    'NEBIVOLOL': 'MONO_ANTIHIPERTANSIF',
    'METOPROLOL': 'MONO_ANTIHIPERTANSIF',
    'BISOPROLOL': 'MONO_ANTIHIPERTANSIF',
    'KARVEDILOL': 'MONO_ANTIHIPERTANSIF',
    'LOSARTAN': 'MONO_ANTIHIPERTANSIF',
    'VALSARTAN': 'MONO_ANTIHIPERTANSIF',
    'IRBESARTAN': 'MONO_ANTIHIPERTANSIF',
    'OLMESARTAN': 'MONO_ANTIHIPERTANSIF',
    'TELMISARTAN': 'MONO_ANTIHIPERTANSIF',
    'FUROSEMID': 'MONO_ANTIHIPERTANSIF',
    'SPIRONOLAKTON': 'MONO_ANTIHIPERTANSIF',

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
    'BUDESONID': 'SOLUNUM',
    'BUDEZONID': 'SOLUNUM',
    'FLUTIKAZON': 'SOLUNUM',
    'FLUTIKAZON PROPIYONAT': 'SOLUNUM',
    'FLUTIKAZON FUROAT': 'SOLUNUM',
    'BEKLOMETAZON': 'SOLUNUM',
    'BEKLOMETAZON DIPROPIYONAT': 'SOLUNUM',
    'SIKLESONID': 'SOLUNUM',
    'MOMETAZON': 'SOLUNUM',
    'MOMETAZON FUROAT': 'SOLUNUM',
    'SALBUTAMOL': 'SOLUNUM',
    'SALBUTAMOL SULFAT': 'SOLUNUM',
    'TERBUTALIN': 'SOLUNUM',
    'TERBUTALIN SULFAT': 'SOLUNUM',
    'IPRATROPIUM': 'SOLUNUM',
    'IPRATROPIUM BROMUR': 'SOLUNUM',
    'TIOTROPIUM': 'SOLUNUM',
    'MONTELUKAST SODYUM': 'SOLUNUM',
    'OMALIZUMAB': 'SOLUNUM',
    'MEPOLIZUMAB': 'SOLUNUM',
    'BENRALIZUMAB': 'SOLUNUM',
    'DUPILUMAB': 'SOLUNUM',
    'ROFLUMILAST': 'SOLUNUM',
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
    'CORTAIR': 'SOLUNUM',
    'PULMICORT': 'SOLUNUM',
    'FLIXOTIDE': 'SOLUNUM',
    'ALVESCO': 'SOLUNUM',
    'VENTOLIN': 'SOLUNUM',
    'BUVENTOL': 'SOLUNUM',
    'ATROVENT': 'SOLUNUM',
    'SPIRIVA': 'SOLUNUM',
    'SERETIDE': 'SOLUNUM',
    'SYMBICORT': 'SOLUNUM',
    'FOSTER': 'SOLUNUM',
    'RELVAR': 'SOLUNUM',
    'TRELEGY': 'SOLUNUM',
    'TRIMBOW': 'SOLUNUM',
    'ANORO': 'SOLUNUM',
    'ULTIBRO': 'SOLUNUM',
    'XOLAIR': 'SOLUNUM',
    'NUCALA': 'SOLUNUM',
    'FASENRA': 'SOLUNUM',
    'DUPIXENT': 'SOLUNUM',
    'DAXAS': 'SOLUNUM',
    'SINGULAIR': 'SOLUNUM',
    'ONCEAIR': 'SOLUNUM',
    'OCERAL': 'RAPORSUZ_BILGILENDIRME',
    'ANDOREX': 'RAPORSUZ_BILGILENDIRME',
    'MACROL': 'RAPORSUZ_BILGILENDIRME',
    'AKINETON': 'RECETE_TURU_YESIL',
    'ENOX': 'DMAH',

    # BPH / Prostat
    'XATRAL': 'BPH_PROSTAT',         # Alfuzosin
    'UROREC': 'BPH_PROSTAT',         # Silodosin
    'AVODART': 'BPH_PROSTAT',        # Dutasterid
    'COMBODART': 'BPH_PROSTAT',      # Dutasterid+Tamsulosin
    'DUODART': 'BPH_PROSTAT',
    'PROSCAR': 'BPH_PROSTAT',        # Finasterid
    'PROPECIA': 'BPH_PROSTAT',
    'FLOMAX': 'BPH_PROSTAT',         # Tamsulosin
    'TAMPROST': 'BPH_PROSTAT',
    'HYTRIN': 'BPH_PROSTAT',         # Terazosin

    # İnkontinans
    'KINZY': 'INKONTINANS',          # Solifenasin
    'VESICARE': 'INKONTINANS',
    'DETRUSITOL': 'INKONTINANS',     # Tolterodin
    'URICANDIN': 'INKONTINANS',
    'DITROPAN': 'INKONTINANS',       # Oksibutinin
    'MICTONORM': 'INKONTINANS',      # Propiverin
    'SPASMEKS': 'INKONTINANS',
    'TOVIAZ': 'INKONTINANS',         # Fesoterodin
    'BETMIGA': 'INKONTINANS',        # Mirabegron
    'EMSELEX': 'INKONTINANS',        # Darifenasin

    # IV Demir
    'INFERJECT': 'DEMIR_IV',
    'FERINJECT': 'DEMIR_IV',
    'MONOFER': 'DEMIR_IV',
    'VENOFER': 'DEMIR_IV',
    'COSMOFER': 'DEMIR_IV',
    'FERMED': 'DEMIR_IV',

    # Desmopresin
    'MINIRIN': 'DESMOPRESIN',
    'DESMOPAN': 'DESMOPRESIN',
    'NOCDURNA': 'DESMOPRESIN',

    # Nöropatik ağrı
    'NEURONTIN': 'NOROPATIK_AGRI',   # Gabapentin
    'NERUDA': 'NOROPATIK_AGRI',
    'GABATEVA': 'NOROPATIK_AGRI',
    'GABALEPT': 'NOROPATIK_AGRI',
    'LYRICA': 'NOROPATIK_AGRI',      # Pregabalin
    'GABRICA': 'NOROPATIK_AGRI',
    'PREGALIN': 'NOROPATIK_AGRI',
    'PREGABEX': 'NOROPATIK_AGRI',
    # CYMBALTA ve DUXET → PSIKIYATRI (nöropatik endikasyon kontrol_psikiyatri içinde)

    # Antiviral Hepatit/HIV ticari adlar
    'BARACLUDE': 'ANTIVIRAL',        # Entekavir
    'VIREAD': 'ANTIVIRAL',           # Tenofovir
    'HEPATERA': 'ANTIVIRAL',
    'LAMIVUDIN': 'ANTIVIRAL',
    'EPIVIR': 'ANTIVIRAL',
    'HEPSERA': 'ANTIVIRAL',          # Adefovir
    'BEMFOLA': 'ANTIVIRAL',
    'EPCLUSA': 'ANTIVIRAL',          # Sofosbuvir+Velpatasvir
    'HARVONI': 'ANTIVIRAL',          # Sofosbuvir+Ledipasvir
    'MAVIRET': 'ANTIVIRAL',          # Glekaprevir+Pibrentasvir
    'TIVICAY': 'ANTIVIRAL',          # Dolutegravir
    'TRIUMEQ': 'ANTIVIRAL',

    # Enteral beslenme
    'EVOLVIA': 'ENTERAL_BESLENME',
    'NUTRIDRINK': 'ENTERAL_BESLENME',
    'NUTREN': 'ENTERAL_BESLENME',
    'FRESUBIN': 'ENTERAL_BESLENME',
    'RESOURCE': 'ENTERAL_BESLENME',
    'ENSURE': 'ENTERAL_BESLENME',
    'PEPTAMEN': 'ENTERAL_BESLENME',
    'PROSURE': 'ENTERAL_BESLENME',
    'MODULEN': 'ENTERAL_BESLENME',
    'NEPRO': 'ENTERAL_BESLENME',
    'GLUCERNA': 'ENTERAL_BESLENME',
    'DIASIP': 'ENTERAL_BESLENME',
    'CUBITAN': 'ENTERAL_BESLENME',
    'IMPACT': 'ENTERAL_BESLENME',

    # ESA / Eritropoietin (ticari adlar → GENEL_RAPORLU → ESA subroutine)
    'EPOBEL': 'GENEL_RAPORLU',
    'EPREX': 'GENEL_RAPORLU',
    'NEORECORMON': 'GENEL_RAPORLU',
    'ARANESP': 'GENEL_RAPORLU',
    'MIRCERA': 'GENEL_RAPORLU',
    'BINOCRIT': 'GENEL_RAPORLU',
    'RETACRIT': 'GENEL_RAPORLU',
    'ERYPRO': 'GENEL_RAPORLU',
    'EPOKINE': 'GENEL_RAPORLU',
    'EPORON': 'GENEL_RAPORLU',
    'ABSEAMED': 'GENEL_RAPORLU',
    'BIOPOIN': 'GENEL_RAPORLU',
    'SILAPO': 'GENEL_RAPORLU',

    # Benzodiazepin / Anksiyolitik (raporsuz)
    'XANAX': 'BENZODIAZEPIN',
    'DIAPAM': 'BENZODIAZEPIN',
    'NERVIUM': 'BENZODIAZEPIN',
    'ATIVAN': 'BENZODIAZEPIN',
    'RIVOTRIL': 'BENZODIAZEPIN',
    'APRAZO': 'BENZODIAZEPIN',

    # ADHD (atomoksetin/metilfenidat)
    'ATTEX': 'ADHD',
    'STRATTERA': 'ADHD',
    'CONCERTA': 'ADHD',
    'RITALIN': 'ADHD',
    'MEDIKINET': 'ADHD',

    # Göz lubrikan / Suni gözyaşı
    'VISCOTEARS': 'GOZ_LUBRIKAN',
    'TEARS': 'GOZ_LUBRIKAN',
    'ARTELAC': 'GOZ_LUBRIKAN',
    'REFRESH': 'GOZ_LUBRIKAN',
    'SYSTANE': 'GOZ_LUBRIKAN',
    'HYLO': 'GOZ_LUBRIKAN',
    'THEALOZ': 'GOZ_LUBRIKAN',

    # Mono antihipertansif (ACE-i / ARB / KKB ticari adları)
    'DELIX': 'MONO_ANTIHIPERTANSIF',         # Ramipril
    'DELIX PROTECT': 'MONO_ANTIHIPERTANSIF',
    'TRITACE': 'MONO_ANTIHIPERTANSIF',
    'COVERSYL': 'MONO_ANTIHIPERTANSIF',
    'RENITEC': 'MONO_ANTIHIPERTANSIF',
    'NORVASC': 'MONO_ANTIHIPERTANSIF',
    'TENSAR': 'MONO_ANTIHIPERTANSIF',
    'KARVEZIDE': 'KOMBINE_ANTIHIPERTANSIF',
    'CO-IRDA': 'KOMBINE_ANTIHIPERTANSIF',   # İrbesartan+HCT
    'COAPROVEL': 'KOMBINE_ANTIHIPERTANSIF',
    'EXFORGE': 'KOMBINE_ANTIHIPERTANSIF',
    'CO-DIOVAN': 'KOMBINE_ANTIHIPERTANSIF',

    # NSAI / Raporsuz analjezikler
    'ETOL': 'RAPORSUZ_BILGILENDIRME',        # Etodolak
    'GERALGINE': 'RAPORSUZ_BILGILENDIRME',   # Parasetamol+kafein
    'VERMIDON': 'RAPORSUZ_BILGILENDIRME',
    'PAROL': 'RAPORSUZ_BILGILENDIRME',
    'MAJEZIK': 'RAPORSUZ_BILGILENDIRME',

    # Dermatolojik krem / topik (raporsuz)
    'DERMOTROSYD': 'RAPORSUZ_BILGILENDIRME',
    'DERMOVATE': 'RAPORSUZ_BILGILENDIRME',
    'FUCIDIN': 'RAPORSUZ_BILGILENDIRME',
    'BACTROBAN': 'RAPORSUZ_BILGILENDIRME',
    'TERRACORTRIL': 'RAPORSUZ_BILGILENDIRME',
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

    # 5. Çift ünsüz → tek (alerjik/allerjik, akut/acut, mg tıbbi yazım varyasyonları)
    # Bu Türkçede anlam değiştirmez, "hall" → "hal" gibi bazı kelimeleri etkileyebilir
    # ama tıbbi terim eşleşmelerinde kritik.
    import re as _re
    t = _re.sub(r'([bcçdfgğhjklmnprsştvyz])\1+', r'\1', t)

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


def _lab_degeri_cek(metin, anahtarlar, birim_patterns=None):
    """Metinden laboratuvar değerini çek.
    anahtarlar: aranan anahtar kelimeler listesi (Hb, Hemoglobin vb.)
    birim_patterns: sonrasında beklenen birim (opsiyonel, ör: 'g/dl', 'ng/ml', '%')
    Returns: (float_deger, eslesen_ibaresi) veya (None, "")
    """
    if not metin:
        return None, ""
    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()
    for anahtar in anahtarlar:
        ak = anahtar.lower()
        # "anahtar: 11.5", "anahtar = 11,5", "anahtar 11.5", "anahtar: %23"
        patterns = [
            rf'{re.escape(ak)}\s*[:=]?\s*%?\s*(\d+(?:[.,]\d+)?)',
            rf'{re.escape(ak)}[^0-9]{{0,40}}(\d+(?:[.,]\d+)?)',
        ]
        for pattern in patterns:
            m = re.search(pattern, metin_lower)
            if m:
                try:
                    deger = float(m.group(1).replace(",", "."))
                    # Eşlemenin etrafından ibare
                    pos = m.start()
                    bas = max(0, pos - 5)
                    son = min(len(metin), m.end() + 10)
                    return deger, metin[bas:son].strip()
                except (ValueError, IndexError):
                    pass
    return None, ""


def _buyume_hormonu_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.14.A - Büyüme hormonu (Somatropin) detaylı kontrol.
    Kriterler:
    - Çocuk endokrinoloji / endokrinoloji uzman raporu (6 aylık max)
    - Boy SDS < -2 (kısa boy kriteri)
    - Büyüme hızı yetersizliği
    - IGF-1 / GH uyarı testi değerleri
    - Kemik yaşı belirtilmeli
    """
    sut_kurali = 'SUT 4.2.14.A — Büyüme hormonu 6 aylık çocuk endokrinoloji raporu'
    detaylar = {'alt_kategori': 'BUYUME_HORMONU', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Büyüme hormonu RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.14.A - Çocuk endokrinoloji uzman raporu gerekli (6 aylık)',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # SDS değeri ara (−2'nin altı kriter): "SDS: -2.3", "SDS -2.5"
    sds_match = re.search(r'sds\s*[:=]?\s*(-?\d+[.,]?\d*)', metin_lower)
    sds = None
    if sds_match:
        try:
            sds = float(sds_match.group(1).replace(",", "."))
        except Exception:
            pass

    igf1, igf1_ibare = _lab_degeri_cek(birlesik, ['igf-1', 'igf1'])
    gh, gh_ibare = _lab_degeri_cek(birlesik, ['gh peak', 'büyüme hormonu peak', 'growth hormone'])
    cocuk_endokr = any(k in metin_lower for k in ['çocuk endokrinoloji', 'cocuk endokrinoloji',
                                                    'pediatrik endokrin'])

    detaylar.update({'sds': sds, 'igf1': igf1, 'cocuk_endokr': cocuk_endokr})

    sorunlar = []
    bilgiler = []
    if sds is not None:
        bilgiler.append(f"SDS: {sds}")
        if sds > -2:
            sorunlar.append(f"SDS {sds} > -2 — kısa boy kriteri karşılanmıyor")
    else:
        bilgiler.append("SDS (boy skor) raporda bulunamadı")
    if igf1 is not None:
        bilgiler.append(f"IGF-1: {igf1}")
    if not cocuk_endokr:
        bilgiler.append("Çocuk endokrinoloji ibaresi bulunamadı (kural için gerekli)")

    if sorunlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"Büyüme hormonu uygunsuz: {'; '.join(sorunlar)}",
            detaylar=detaylar, uyari=" | ".join(bilgiler),
            sut_kurali=sut_kurali, aranan_ibare='SDS<-2'
        )

    if sds is not None or igf1 is not None or cocuk_endokr:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Büyüme hormonu uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Rapor süresi max 6 ay. SDS, IGF-1, büyüme hızı takibi yapılmalı.',
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Büyüme hormonu UYGUN DEĞİL: SDS/IGF-1/uzman branş raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.14.A: SDS, IGF-1, GH uyarı testi, çocuk endokrinoloji raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='SDS + IGF-1 + çocuk endokrinoloji (hepsi zorunlu)'
    )


def _immunsupresif_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.32 - İmmünosüpresif ilaçlar detaylı kontrol.
    Kriterler:
    - Transplantasyon endikasyonu (böbrek/karaciğer/kalp/kemik iliği)
    - Otoimmün endikasyon (SLE, romatolojik, nefrotik sendrom vb.)
    - Transplant merkezi / nefroloji / romatoloji / hematoloji uzman raporu
    - Rapor süresi kontrolü (genelde 1 yıl)
    """
    sut_kurali = 'SUT 4.2.32 — İmmünosüpresif uzman raporu'
    detaylar = {'alt_kategori': 'IMMUNSUPRESIF', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'İmmünosüpresif ilaç RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.32 - Transplantasyon/Otoimmün uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    transplant = any(k in metin_lower for k in ['transplant', 'nakil', 'organ nakli',
                                                  'böbrek nakli', 'karaciğer nakli',
                                                  'kalp nakli', 'kemik iliği'])
    otoimmun = any(k in metin_lower for k in ['sle', 'lupus', 'romatoid', 'nefrotik',
                                                'otoimmün', 'otoimmun', 'vaskülit',
                                                'myastenia', 'crohn', 'kolit'])
    uzman = any(k in metin_lower for k in ['nefroloji', 'romatoloji', 'hematoloji',
                                             'gastroenteroloji', 'transplant merkezi',
                                             'organ nakli'])

    detaylar.update({'transplant': transplant, 'otoimmun': otoimmun, 'uzman': uzman})

    bilgiler = []
    if transplant: bilgiler.append("Transplantasyon endikasyonu")
    if otoimmun: bilgiler.append("Otoimmün hastalık")
    if uzman: bilgiler.append("Uzman branş tespit edildi")

    if transplant or otoimmun:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İmmünosüpresif uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Rapor 1 yıllık. Transplant/otoimmün endikasyon + uzman branş takibi yapılmalı.',
            sut_kurali=sut_kurali
        )

    if uzman:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İmmünosüpresif uygun (uzman raporu var) — rapor {rapor_kodu}",
            detaylar=detaylar,
            uyari='Endikasyon açık belirtilmedi ama uzman raporu mevcut.',
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'İmmünosüpresif UYGUN DEĞİL: Endikasyon (transplant/otoimmün) raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.32: Raporda transplant veya otoimmün hastalık ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='transplant / otoimmün / uzman (zorunlu)'
    )


def _biyolojik_tnf_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.33 - Biyolojik/TNF inhibitörü detaylı kontrol.
    Kriterler:
    - Basamak tedavi şartı: geleneksel DMARD / metotreksat / sulfasalazin denenmiş
    - Yetersiz yanıt / yan etki ibaresi
    - Endikasyon (RA, psoriazis, AS, Crohn, üveit vb.)
    - Uzman branş (Romatoloji/Dermatoloji/Gastroenteroloji vb.)
    - Hastalık aktivitesi (DAS28, PASI, BASDAI vb. skorlar)
    """
    sut_kurali = 'SUT 4.2.33 — Biyolojik/TNF ilaçları basamak tedavi + uzman raporu'
    detaylar = {'alt_kategori': 'BIYOLOJIK_TNF', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Biyolojik ilaç RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.33 - İlgili branş uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # Basamak tedavi: DMARD / metotreksat / sulfasalazin
    basamak_tedavi = any(k in metin_lower for k in [
        'metotreksat', 'methotrexate', 'mtx', 'sulfasalazin', 'leflunomid',
        'hidroksiklorokin', 'dmard', 'geleneksel tedavi', 'konvansiyonel',
        'topikal tedavi', 'uvb', 'fotokemoterapi', 'puva'
    ])
    yetersiz_yanit = any(k in metin_lower for k in [
        'yetersiz', 'yanıtsız', 'yanitsiz', 'yan etki', 'intolerans',
        'başarısız', 'basarisiz', 'refrakter'
    ])

    # Endikasyonlar
    endikasyonlar = []
    endikasyon_map = [
        (['romatoid', 'ra ', 'ra,'], 'Romatoid Artrit'),
        (['psoriazis', 'psoriasis', 'sedef'], 'Psoriazis'),
        (['ankilozan', 'spondilit', 'spondiloartrit'], 'Ankilozan Spondilit'),
        (['crohn', 'ülseratif kolit', 'ulseratif kolit', 'kolit'], 'İnflamatuar Bağırsak'),
        (['jüvenil', 'juvenil'], 'Jüvenil İdiyopatik Artrit'),
        (['psoriatik'], 'Psoriatik Artrit'),
        (['hidradenit'], 'Hidradenitis Supurativa'),
        (['astım', 'astim', 'koah'], 'Ağır Astım / KOAH'),
        (['üveit', 'uveit'], 'Üveit'),
    ]
    for kwlist, ad in endikasyon_map:
        if any(k in metin_lower for k in kwlist):
            endikasyonlar.append(ad)

    # Uzman branş
    uzman = any(k in metin_lower for k in [
        'romatoloji', 'dermatoloji', 'gastroenteroloji',
        'çocuk romatoloji', 'göğüs hastalıkları', 'göz', 'oftalmoloji'
    ])

    # Hastalık aktivite skoru
    aktivite_skor = any(k in metin_lower for k in [
        'das28', 'pasi', 'basdai', 'cdai', 'sdai', 'dlqi',
        'hastalık aktivite', 'hastalik aktivite'
    ])

    detaylar.update({
        'basamak_tedavi': basamak_tedavi, 'yetersiz_yanit': yetersiz_yanit,
        'endikasyonlar': endikasyonlar, 'uzman': uzman, 'aktivite_skor': aktivite_skor
    })

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if basamak_tedavi: bilgiler.append("Basamak tedavi belgesi var")
    if yetersiz_yanit: bilgiler.append("Yetersiz yanıt belirtilmiş")
    if uzman: bilgiler.append("Uzman branş tespit edildi")
    if aktivite_skor: bilgiler.append("Hastalık aktivite skoru mevcut")

    eksikler = []
    if not basamak_tedavi: eksikler.append("basamak tedavi (DMARD/metotreksat) yok")
    if not yetersiz_yanit: eksikler.append("yetersiz yanıt ibaresi yok")
    if not endikasyonlar: eksikler.append("endikasyon belirtilmemiş")

    # Basamak + yetersiz yanıt + endikasyon hepsi var → UYGUN
    if basamak_tedavi and yetersiz_yanit and endikasyonlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Biyolojik uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Rapor süresi ve tedavi yanıtı düzenli takip edilmeli.',
            sut_kurali=sut_kurali
        )

    # Kısmi bilgi — SUT tamamı gerektiriyor → UYGUN DEĞİL
    if endikasyonlar or basamak_tedavi or uzman:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"Biyolojik UYGUN DEĞİL: Eksik zorunlu bilgi ({', '.join(eksikler)})",
            detaylar=detaylar,
            uyari=f"Mevcut: {' | '.join(bilgiler) if bilgiler else 'az'}. SUT 4.2.33: basamak tedavi + yetersiz yanıt + endikasyon ZORUNLU.",
            sut_kurali=sut_kurali,
            aranan_ibare='basamak tedavi + yetersiz yanıt + endikasyon (hepsi zorunlu)'
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Biyolojik UYGUN DEĞİL: basamak tedavi/endikasyon/uzman bilgileri raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.33: DMARD/metotreksat denenmiş + yetersiz yanıt + endikasyon + uzman ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='basamak tedavi + endikasyon + uzman (hepsi zorunlu)'
    )


def _ivig_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.6 - İmmünglobulin (IVIG/SCIG) detaylı kontrol.
    Kriterler:
    - Endikasyon (primer immün yetmezlik, ITP, GBS, CIDP, myasteni vb.)
    - Uzman branş (Hematoloji/Nöroloji/İmmünoloji/Pediatri)
    - IgG düzeyi (primer immün yetmezlikte)
    - Doz g/kg takibi
    """
    sut_kurali = 'SUT 4.2.6 — İmmünglobulin uzman raporu'
    detaylar = {'alt_kategori': 'IMMUNOGLOBULIN', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'İmmünglobulin RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.6 - Hematoloji/Nöroloji/İmmünoloji uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # Endikasyonlar
    endikasyon_map = [
        (['primer immün', 'primer immun', 'agammaglobulinemi', 'cvid',
          'x-linked agama', 'kombine immün yetmezlik'], 'Primer İmmün Yetmezlik'),
        (['itp', 'idiyopatik trombositopeni', 'immun trombositopeni'], 'ITP'),
        (['gbs', 'guillain-barre', 'guillain barre'], 'Guillain-Barré'),
        (['cidp', 'kronik inflamatuar poliradikül'], 'CIDP'),
        (['myasteni', 'miyasteni'], 'Myasthenia Gravis'),
        (['kawasaki'], 'Kawasaki Hastalığı'),
        (['multifokal motor', 'mmn'], 'Multifokal Motor Nöropati'),
    ]
    endikasyonlar = []
    for kwlist, ad in endikasyon_map:
        if any(k in metin_lower for k in kwlist):
            endikasyonlar.append(ad)

    # IgG düzeyi (primer immün yetmezlikte)
    igg, igg_ibare = _lab_degeri_cek(birlesik, ['igg', 'ıgg'])

    uzman = any(k in metin_lower for k in ['hematoloji', 'nöroloji', 'noroloji',
                                             'immünoloji', 'immunoloji', 'pediatri',
                                             'çocuk', 'cocuk', 'allergy', 'alerji'])

    detaylar.update({'endikasyonlar': endikasyonlar, 'igg': igg, 'uzman': uzman})

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if igg is not None: bilgiler.append(f"IgG: {igg}")
    if uzman: bilgiler.append("Uzman branş tespit edildi")

    if endikasyonlar and uzman:
        uyarilar = ['Doz (g/kg) ve tedavi aralığı raporda belirtilmeli']
        if 'Primer' in ' '.join(endikasyonlar) and igg is None:
            uyarilar.append('Primer immün yetmezlik endikasyonunda IgG düzeyi raporlanmalı')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İmmünglobulin uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar, uyari=' | '.join(uyarilar),
            sut_kurali=sut_kurali
        )

    if endikasyonlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"İmmünglobulin UYGUN DEĞİL: Uzman branş raporda tespit edilemedi (rapor {rapor_kodu})",
            detaylar=detaylar,
            uyari=f"Endikasyon var: {', '.join(endikasyonlar)}. Ancak SUT 4.2.6 uzman branş ZORUNLU.",
            sut_kurali=sut_kurali,
            aranan_ibare='Hematoloji/Nöroloji/İmmünoloji (zorunlu)'
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'İmmünglobulin UYGUN DEĞİL: Endikasyon raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.6: Endikasyon (PID/ITP/GBS/CIDP vb.) + uzman branş ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='endikasyon + uzman (zorunlu)'
    )


def _inkontinans_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.16.B - Antimuskarinik inkontinans ilaçları detaylı kontrol.
    Etkin maddeler: Solifenasin, Tolterodin, Oksibutinin, Propiverin, Trospium,
                     Fesoterodin, Mirabegron, Darifenasin
    Ticari: KINZY, VESICARE, DETRUSITOL, DITROPAN, MICTONORM, SPASMEKS, TOVIAZ,
             BETMIGA, EMSELEX
    Kriterler:
    - Rapor kodu (15.08 Nörojenik mesane, R32/R33/N31/N32/N39 ICD)
    - Üroloji / Nöroloji / Kadın Hast. / Geriatri uzman raporu (1 yıl)
    - Endikasyon: urge inkontinans / overaktif mesane / nörojenik mesane / SİK
    - Oral oksibutinine yanıtsızlık bilgisi (solifenasin/tolterodin için)
    """
    sut_kurali = 'SUT 4.2.16.B — Antimuskarinik inkontinans ilaçları'
    detaylar = {'alt_kategori': 'INKONTINANS', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'İnkontinans ilacı RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.16.B — Üroloji/Nöroloji/Kadın Hast./Geriatri uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # Endikasyonlar
    endikasyonlar = []
    if any(k in metin_lower for k in ['nörojenik mesane', 'norojenik mesane', 'nörojenik',
                                        'norojenik']) or 'N31' in teshis_metin:
        endikasyonlar.append('Nörojenik mesane')
    if any(k in metin_lower for k in ['overaktif mesane', 'aşırı aktif mesane',
                                        'oab', 'asiri aktif']):
        endikasyonlar.append('Overaktif mesane')
    if any(k in metin_lower for k in ['urge inkontinans', 'urge', 'urgency',
                                        'sıkışma inkontinans']):
        endikasyonlar.append('Urge inkontinans')
    if any(k in metin_lower for k in ['stres inkontinans', 'stress inkontinans']):
        endikasyonlar.append('Stres inkontinans')

    # Uzman branş
    uzman = any(k in metin_lower for k in ['üroloji', 'uroloji', 'nöroloji', 'noroloji',
                                             'kadın doğum', 'kadin dogum',
                                             'kadın hastalıkları', 'kadin hastaliklari',
                                             'geriatri', 'jinekoloji'])

    # Oksibutinine yanıtsızlık (solifenasin/tolterodin gibi yeni ajanlar için kritik)
    oksibutinin_denendi = any(k in metin_lower for k in [
        'oksibutinin', 'oxybutynin', 'ditropan', 'oksi̇buti̇ni̇n',
        'yanıt alınamayan', 'yanit alinamayan', 'tolere edemeyen'
    ])

    detaylar.update({'endikasyonlar': endikasyonlar, 'uzman': uzman,
                      'oksibutinin_denendi': oksibutinin_denendi})

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if uzman: bilgiler.append("Uzman branş tespit edildi")
    if oksibutinin_denendi: bilgiler.append("Oksibutinin denenmiş / yanıtsız")

    if endikasyonlar and (uzman or rapor_kodu.startswith('15.')):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İnkontinans uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Rapor süresi 1 yıl. Üroloji uzmanı takibi gerekli.',
            sut_kurali=sut_kurali
        )

    if rapor_kodu.startswith('15.') or rapor_kodu.startswith('N31'):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İnkontinans — rapor kodu {rapor_kodu} (Ürolojik)",
            detaylar=detaylar,
            uyari='Rapor 1 yıl. Endikasyon açık belirtilmeli.',
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'İnkontinans UYGUN DEĞİL: Endikasyon/uzman bilgisi raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.16.B: Overaktif mesane/urge/nörojenik mesane + uzman raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='endikasyon + uzman (zorunlu)'
    )


def _bph_prostat_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """BPH tedavisi: Alfa blokerler (raporsuz) + 5-alfa redüktaz (Dutasterid/Finasterid, rapor)
    Etkin madde:
      - Alfa bloker: Tamsulosin, Alfuzosin, Silodosin, Doksazosin, Terazosin
      - 5-α redüktaz: Finasterid, Dutasterid
    Ticari:
      - Alfa: XATRAL, UROREC, FLOMAX, CARDURA, TAMPROST, HYTRIN
      - 5-α: AVODART, COMBODART, PROSCAR, PROPECIA
    SUT Kuralı:
      - Alfa blokerler BPH için RAPORSUZ (her hekim yazabilir)
      - 5-α redüktaz BPH için rapor gerekli (genelde 04.xx / N40)
      - Kombinasyon (Dutasterid+Tamsulosin, COMBODART): rapor
    """
    sut_kurali = 'SUT — BPH tedavisi: Alfa blokerler raporsuz, 5-α redüktaz rapor'
    detaylar = {'alt_kategori': 'BPH_PROSTAT', 'rapor_kodu': rapor_kodu}

    etkin_upper = (etkin_madde or '').upper()
    ilac_upper = (ilac_adi or '').upper()

    # 5-alfa redüktaz (rapor gerekli)
    five_alfa = any(k in etkin_upper for k in ['FINASTERID', 'DUTASTERID']) or \
                any(k in ilac_upper for k in ['AVODART', 'COMBODART', 'PROSCAR', 'PROPECIA'])

    # Alfa bloker (raporsuz)
    alfa_bloker = any(k in etkin_upper for k in ['TAMSULOSIN', 'ALFUZOSIN', 'SILODOSIN',
                                                    'DOKSAZOSIN', 'TERAZOSIN']) or \
                  any(k in ilac_upper for k in ['XATRAL', 'UROREC', 'FLOMAX', 'TAMPROST',
                                                   'HYTRIN', 'CARDURA'])

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    bph_var = any(k in metin_lower for k in ['bph', 'benign prostat hiperplazi',
                                                'prostat hiperplazi', 'prostat büyümesi',
                                                'prostat buyumesi']) or 'N40' in teshis_metin

    if alfa_bloker and not five_alfa:
        # Raporsuz alfa bloker — BPH için her durumda uygun
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Alfa bloker — BPH için raporsuz yazılabilir",
            detaylar={**detaylar, 'tip': 'alfa_bloker'},
            uyari='SUT: Alfa blokerler BPH endikasyonunda raporsuz reçete edilir',
            sut_kurali=sut_kurali
        )

    if five_alfa:
        if not rapor_kodu and not bph_var:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                '5-α redüktaz (Finasterid/Dutasterid) RAPORSUZ yazılmış! Rapor gerekli',
                detaylar={**detaylar, 'tip': '5_alfa_reduktaz'},
                uyari='SUT: 5-α redüktaz inhibitörleri BPH için üroloji raporu ile verilir',
                sut_kurali=sut_kurali, aranan_ibare='rapor'
            )
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"5-α redüktaz — rapor {rapor_kodu} (BPH)",
            detaylar={**detaylar, 'tip': '5_alfa_reduktaz'},
            uyari='Üroloji uzman raporu. PSA takibi önerilir.',
            sut_kurali=sut_kurali
        )

    # Bilinmeyen durum — etkin madde tespit edilemediyse güvenli taraf: UYGUN DEĞİL
    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'BPH ilacı UYGUN DEĞİL: Etkin madde tanılanamadı',
        detaylar=detaylar,
        uyari='Etkin madde bilinmeden SUT kuralı uygulanamaz',
        sut_kurali=sut_kurali
    )


def _demir_iv_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT - IV Demir tedavisi (Demir karboksimaltoz/sükroz/izomaltosit).
    Ticari: INFERJECT (Ferinject), MONOFER, FERMED, VENOFER, COSMOFER
    Kriterler:
      - Oral demir yanıtsızlığı / intolerans
      - Ferritin < 30 ng/mL (mutlak demir eksikliği) veya TSAT < %20
      - Hb düşüklüğü (anemi)
      - Nefroloji/Hematoloji/Gastroenteroloji/Kadın Hast. uzman raporu
    """
    sut_kurali = 'SUT — IV Demir: oral yanıtsız + ferritin/TSAT + uzman raporu'
    detaylar = {'alt_kategori': 'DEMIR_IV', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'IV Demir RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='Nefroloji/Hematoloji/GE/Kadın Hast. uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    hb, _ = _lab_degeri_cek(birlesik, ['hemoglobin', 'hgb', 'hb'])
    ferritin, _ = _lab_degeri_cek(birlesik, ['ferritin'])
    tsat, _ = _lab_degeri_cek(birlesik, ['tsat', 'transferrin satürasyonu',
                                           'transferrin saturasyonu'])

    oral_basarisiz = any(k in metin_lower for k in [
        'oral demir', 'oral tedavi', 'yanıtsız', 'yanitsiz', 'intolerans',
        'gastrointestinal yan etki', 'emilim bozuk'
    ])
    uzman = any(k in metin_lower for k in ['nefroloji', 'hematoloji', 'gastroenteroloji',
                                             'kadın hast', 'kadin hast', 'kadın doğum'])

    detaylar.update({'hb': hb, 'ferritin': ferritin, 'tsat': tsat,
                      'oral_basarisiz': oral_basarisiz, 'uzman': uzman})

    bilgiler = []
    if hb is not None: bilgiler.append(f"Hb: {hb}")
    if ferritin is not None: bilgiler.append(f"Ferritin: {ferritin}")
    if tsat is not None: bilgiler.append(f"TSAT: %{tsat}")
    if oral_basarisiz: bilgiler.append("Oral demir yanıtsız/intolerans")
    if uzman: bilgiler.append("Uzman branş var")

    sorunlar = []
    if ferritin is not None and ferritin >= 100 and (tsat is None or tsat >= 20):
        sorunlar.append(f"Ferritin {ferritin} ≥ 100 — mutlak demir eksikliği yok")

    if sorunlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"IV Demir uygunsuz: {'; '.join(sorunlar)}",
            detaylar=detaylar, uyari=' | '.join(bilgiler),
            sut_kurali=sut_kurali
        )

    kriter_sayisi = sum([oral_basarisiz, uzman,
                          ferritin is not None and ferritin < 100,
                          hb is not None and hb < 12])
    if kriter_sayisi >= 2:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"IV Demir uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Toplam doz uzman tarafından hesaplanmalı (Ganzoni formülü)',
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'IV Demir UYGUN DEĞİL: Lab değerleri/oral yanıtsızlık ibaresi raporda yetersiz',
        detaylar=detaylar,
        uyari='SUT: Oral demir başarısız + Ferritin<100 + uzman raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='oral demir yanıtsız + ferritin + uzman (zorunlu)'
    )


def _desmopresin_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """Desmopresin (MINIRIN) - Nokturnal enürezis / Diabetes insipidus / Hemofili tip A.
    Kriterler:
      - Nokturnal enürezis (çocuk): Pediatri/Çocuk nefroloji raporu
      - Diabetes insipidus: Endokrinoloji raporu
      - Hemofili A hafif form: Hematoloji raporu
    """
    sut_kurali = 'SUT — Desmopresin: endikasyon + ilgili uzman raporu'
    detaylar = {'alt_kategori': 'DESMOPRESIN', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Desmopresin RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='Pediatri/Endokrin/Hematoloji uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    endikasyonlar = []
    if any(k in metin_lower for k in ['enürezis', 'enurezis', 'nokturnal',
                                        'gece işemesi', 'gece isemesi']):
        endikasyonlar.append('Nokturnal enürezis')
    if any(k in metin_lower for k in ['diabetes insipidus', 'santral diabetes']):
        endikasyonlar.append('Diabetes insipidus')
    if any(k in metin_lower for k in ['hemofili a', 'von willebrand', 'vwd']):
        endikasyonlar.append('Hemofili A / vWD')

    uzman = any(k in metin_lower for k in ['pediatri', 'çocuk', 'cocuk', 'endokrinoloji',
                                             'hematoloji', 'nefroloji'])

    detaylar.update({'endikasyonlar': endikasyonlar, 'uzman': uzman})

    if endikasyonlar and uzman:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Desmopresin uygun — {', '.join(endikasyonlar)}",
            detaylar=detaylar,
            sut_kurali=sut_kurali
        )
    if endikasyonlar or uzman:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Desmopresin — rapor {rapor_kodu} (manuel kontrol önerilir)",
            detaylar=detaylar,
            uyari='Endikasyon (enürezis/DI/Hemofili) ve uzman branş kontrol edilmeli',
            sut_kurali=sut_kurali
        )
    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Desmopresin UYGUN DEĞİL: Endikasyon raporda bulunamadı',
        detaylar=detaylar,
        sut_kurali=sut_kurali,
        uyari='SUT: Enürezis / Diabetes insipidus / Hemofili A endikasyonu ZORUNLU',
        aranan_ibare='enürezis / DI / Hemofili A (zorunlu)'
    )


def _antiviral_hepatit_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.13 - Antiviral (Hepatit B/C, HIV) detaylı kontrol.
    Kriterler:
    - Hepatit B: HBV DNA, HBsAg pozitif, transaminaz (ALT/AST)
    - Hepatit C: Anti-HCV pozitif, HCV RNA, ALT
    - HIV: CD4 sayısı, viral yük
    - Gastroenteroloji / Enfeksiyon hastalıkları uzman raporu
    """
    sut_kurali = 'SUT 4.2.13 — Antiviral (Hepatit B/C, HIV) uzman raporu + lab değerleri'
    detaylar = {'alt_kategori': 'ANTIVIRAL_DETAYLI', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Antiviral RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='Gastroenteroloji/Enfeksiyon uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # Endikasyon
    hbv = any(k in metin_lower for k in ['hepatit b', 'hbv', 'hbsag', 'hepatitis b']) \
          or 'B18' in teshis_metin or 'B16' in teshis_metin
    hcv = any(k in metin_lower for k in ['hepatit c', 'hcv', 'hepatitis c']) \
          or 'B18.2' in teshis_metin or 'B17' in teshis_metin
    hiv = any(k in metin_lower for k in ['hiv', 'aids']) or 'B20' in teshis_metin

    # Lab değerleri
    hbv_dna, _ = _lab_degeri_cek(birlesik, ['hbv dna', 'hbv-dna'])
    hcv_rna, _ = _lab_degeri_cek(birlesik, ['hcv rna', 'hcv-rna'])
    cd4, _ = _lab_degeri_cek(birlesik, ['cd4', 'cd 4'])
    alt, _ = _lab_degeri_cek(birlesik, ['alt', 'sgpt'])
    ast, _ = _lab_degeri_cek(birlesik, ['ast', 'sgot'])

    uzman = any(k in metin_lower for k in ['gastroenteroloji', 'enfeksiyon', 'enfeksi̇yon',
                                             'hepatoloji'])

    detaylar.update({
        'hbv': hbv, 'hcv': hcv, 'hiv': hiv,
        'hbv_dna': hbv_dna, 'hcv_rna': hcv_rna, 'cd4': cd4,
        'alt': alt, 'ast': ast, 'uzman': uzman,
    })

    bilgiler = []
    if hbv: bilgiler.append("Hepatit B")
    if hcv: bilgiler.append("Hepatit C")
    if hiv: bilgiler.append("HIV")
    if hbv_dna is not None: bilgiler.append(f"HBV DNA: {hbv_dna}")
    if hcv_rna is not None: bilgiler.append(f"HCV RNA: {hcv_rna}")
    if cd4 is not None: bilgiler.append(f"CD4: {cd4}")
    if alt is not None: bilgiler.append(f"ALT: {alt}")
    if uzman: bilgiler.append("Uzman branş var")

    endikasyon_var = hbv or hcv or hiv

    if endikasyon_var and uzman and (hbv_dna is not None or hcv_rna is not None or cd4 is not None):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Antiviral uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Viral yük ve transaminaz takibi düzenli yapılmalı',
            sut_kurali=sut_kurali
        )

    eksikler = []
    if not endikasyon_var: eksikler.append("endikasyon (HBV/HCV/HIV) belirsiz")
    if not uzman: eksikler.append("uzman branş belirsiz")
    if hbv and hbv_dna is None: eksikler.append("HBV DNA yok")
    if hcv and hcv_rna is None: eksikler.append("HCV RNA yok")
    if hiv and cd4 is None: eksikler.append("CD4 yok")

    if endikasyon_var:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"Antiviral UYGUN DEĞİL: Eksik zorunlu bilgi ({', '.join(eksikler)})",
            detaylar=detaylar,
            uyari=f"Mevcut: {' | '.join(bilgiler) if bilgiler else 'az'}. SUT: viral yük + uzman raporu ZORUNLU.",
            sut_kurali=sut_kurali,
            aranan_ibare='viral yük + uzman raporu (zorunlu)'
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Antiviral UYGUN DEĞİL: Endikasyon (Hepatit B/C/HIV) raporda bulunamadı',
        detaylar=detaylar,
        sut_kurali=sut_kurali,
        uyari='SUT: HBV/HCV/HIV tanısı + lab değerleri ZORUNLU',
        aranan_ibare='HBV / HCV / HIV + lab değerleri (zorunlu)'
    )


def _noropatik_agri_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """Nöropatik ağrı ilaçları: Gabapentin, Pregabalin, Duloksetin (nöropatik endikasyon).
    SUT:
    - Gabapentin: Nöroloji raporu, DM nöropatisi / PHN / spinal kord / kanser ağrısı
    - Pregabalin: aynı + fibromiyalji + yaygın anksiyete
    - Duloksetin: DM nöropatisi / fibromiyalji
    Dozlar:
    - Gabapentin max 3600 mg/gün
    - Pregabalin max 600 mg/gün
    - Duloksetin max 120 mg/gün (nöropatik için 60 mg yeterli)
    """
    sut_kurali = 'SUT — Nöropatik ağrı: nöroloji raporu + endikasyon + doz sınırı'
    detaylar = {'alt_kategori': 'NOROPATIK_AGRI', 'rapor_kodu': rapor_kodu}

    etkin_upper = (etkin_madde or '').upper()
    ilac_upper = (ilac_adi or '').upper()

    gabapentin = 'GABAPENTIN' in etkin_upper or any(k in ilac_upper for k in
        ['NERUDA', 'NEURONTIN', 'GABATEVA', 'GABALEPT'])
    pregabalin = 'PREGABALIN' in etkin_upper or any(k in ilac_upper for k in
        ['LYRICA', 'GABRICA', 'PREGALIN', 'PREGABEX'])
    duloksetin = 'DULOKSETIN' in etkin_upper or any(k in ilac_upper for k in
        ['CYMBALTA', 'DUXET', 'DULOXIN', 'DULOX'])

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Nöropatik ağrı ilacı RAPORSUZ yazılmış! Nöroloji raporu gerekli',
            detaylar=detaylar,
            uyari='Gabapentin/Pregabalin/Duloksetin nöropatik ağrı için raporlu',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # Endikasyonlar
    endikasyonlar = []
    if any(k in metin_lower for k in ['nöropatik ağrı', 'noropatik agri',
                                        'nöropati', 'noropati', 'diyabetik nöropati',
                                        'diyabetik noropati']):
        endikasyonlar.append('Nöropatik ağrı / Nöropati')
    if any(k in metin_lower for k in ['postherpetik', 'phn', 'zona sonrası']):
        endikasyonlar.append('Post-herpetik nevralji')
    if any(k in metin_lower for k in ['fibromiyalji', 'fibromyalji']):
        endikasyonlar.append('Fibromiyalji')
    if any(k in metin_lower for k in ['spinal kord', 'medulla spinalis']):
        endikasyonlar.append('Spinal kord yaralanması')
    if any(k in metin_lower for k in ['kanser', 'malign', 'malignite']):
        endikasyonlar.append('Kanser ağrısı')
    if any(k in metin_lower for k in ['yaygın anksiyete', 'yaygin anksiyete', 'gad']):
        endikasyonlar.append('Yaygın anksiyete (pregabalin)')

    # Uzman
    uzman = any(k in metin_lower for k in ['nöroloji', 'noroloji', 'algoloji',
                                             'psikiyatri', 'fizik tedavi', 'romatoloji'])

    # Doz sınırı kontrolü (ilaç adından)
    doz_sinir_asildi = False
    doz_mesaj = ""
    dozaj_match = re.search(r'(\d+)\s*mg', ilac_upper)
    if dozaj_match:
        try:
            tablet_mg = int(dozaj_match.group(1))
            # Günlük doz için adet çarpanı bilinmiyor — sadece tablet dozu not
            if gabapentin and tablet_mg > 800:
                doz_mesaj = "Gabapentin tablet doz > 800 mg — günlük max 3600 mg kontrol edilmeli"
            elif pregabalin and tablet_mg > 300:
                doz_mesaj = "Pregabalin tablet doz > 300 mg — günlük max 600 mg kontrol edilmeli"
        except Exception:
            pass

    detaylar.update({'endikasyonlar': endikasyonlar, 'uzman': uzman,
                      'ilac_grubu': 'gabapentin' if gabapentin else
                                     ('pregabalin' if pregabalin else
                                      ('duloksetin' if duloksetin else 'bilinmiyor'))})

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if uzman: bilgiler.append("Uzman branş var")
    if doz_mesaj: bilgiler.append(doz_mesaj)

    if endikasyonlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Nöropatik ağrı uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Doz sınırı kontrol edilmeli. Rapor süresi max 1 yıl.',
            sut_kurali=sut_kurali
        )

    # Rapor kodu 20.00 (EK-4/D dışı) ise — ağrı tedavisi için genel
    if rapor_kodu.startswith('20.'):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Nöropatik ağrı — rapor {rapor_kodu} (genel)",
            detaylar=detaylar,
            uyari='Endikasyon (nöropati/PHN/fibromiyalji/kanser ağrısı) raporda belirtilmeli',
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Nöropatik ağrı UYGUN DEĞİL: Endikasyon raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT: Nöropati / PHN / fibromiyalji / kanser ağrısı + uzman raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='nöropatik ağrı / fibromiyalji / PHN (zorunlu)'
    )


def _enteral_beslenme_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.8 (benzeri) - Enteral beslenme solüsyonları.
    Ticari: EVOLVIA, NUTRIDRINK, NUTREN, FRESUBIN, RESOURCE, ENSURE, BEBELAC,
             PEPTAMEN, PROSURE, NUTREN JUNIOR, MODULEN
    Kriterler:
    - Endikasyon: Malnütrisyon / kronik hastalık / yutma bozukluğu / kanser /
      GİS hastalığı / kistik fibroz / inek sütü alerjisi (çocuk)
    - Uzman: İç Hast. / Gastroenteroloji / Onkoloji / Geriatri / Pediatri
    - Kalori hesabı (günlük ihtiyaç)
    - Oral / enteral tüp yolu
    """
    sut_kurali = 'SUT — Enteral beslenme: endikasyon + uzman raporu + kalori planı'
    detaylar = {'alt_kategori': 'ENTERAL_BESLENME', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Enteral beslenme solüsyonu RAPORSUZ yazılmış! Uzman raporu gerekli',
            detaylar=detaylar,
            uyari='İç Hast./GE/Onkoloji/Geriatri/Pediatri uzman raporu',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    endikasyonlar = []
    if any(k in metin_lower for k in ['malnütris', 'malnutrisyon', 'yetersiz beslenme',
                                        'kilo kaybı', 'kilo kaybi']):
        endikasyonlar.append('Malnütrisyon')
    if any(k in metin_lower for k in ['yutma bozukluğu', 'yutma guc', 'disfaji',
                                        'yutma gücluğu']):
        endikasyonlar.append('Disfaji / Yutma bozukluğu')
    if any(k in metin_lower for k in ['kanser', 'malignite', 'onkoloji']):
        endikasyonlar.append('Kanser / Onkoloji')
    if any(k in metin_lower for k in ['kistik fibroz', 'kistik fibrosis']):
        endikasyonlar.append('Kistik fibroz')
    if any(k in metin_lower for k in ['crohn', 'kolit', 'kısa bağırsak',
                                        'kisa bagirsak']):
        endikasyonlar.append('İnflamatuar/kısa bağırsak')
    if any(k in metin_lower for k in ['inek sütü aler', 'inek sutu aler',
                                        'süt alerji', 'sut alerji']):
        endikasyonlar.append('İnek sütü alerjisi')
    if any(k in metin_lower for k in ['serebral palsi', 'serebral felç',
                                        'nörolojik hastalık']):
        endikasyonlar.append('Nörolojik hastalık')
    if any(k in metin_lower for k in ['demans', 'alzheimer']):
        endikasyonlar.append('Demans / Alzheimer')

    uzman = any(k in metin_lower for k in ['iç hastalıkları', 'ic hastaliklari',
                                             'dahiliye', 'gastroenteroloji',
                                             'onkoloji', 'geriatri', 'pediatri',
                                             'çocuk', 'cocuk', 'nöroloji'])

    # PEG/enteral tüp ibaresi
    enteral_yol = any(k in metin_lower for k in ['peg', 'enteral tüp', 'enteral tup',
                                                    'gastrostomi', 'nazogastrik',
                                                    'sondayla', 'tüple', 'tuple'])

    detaylar.update({'endikasyonlar': endikasyonlar, 'uzman': uzman,
                      'enteral_yol': enteral_yol})

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if uzman: bilgiler.append("Uzman branş var")
    if enteral_yol: bilgiler.append("Enteral yol (PEG/sonda) belirtilmiş")

    if endikasyonlar and uzman:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Enteral beslenme uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar,
            uyari='Kalori hesabı ve rapor süresi (genelde 1 yıl) kontrol edilmeli',
            sut_kurali=sut_kurali
        )

    if endikasyonlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Enteral beslenme — rapor {rapor_kodu}, uzman belirsiz",
            detaylar=detaylar,
            uyari=f"Endikasyon mevcut: {', '.join(endikasyonlar)}. Uzman açık belirtilmeli.",
            sut_kurali=sut_kurali
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Enteral beslenme UYGUN DEĞİL: Endikasyon raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT: Malnütrisyon/disfaji/kanser/kistik fibroz + uzman raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='endikasyon + uzman (zorunlu)'
    )


def _koagulasyon_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.5 - Koagülasyon faktörleri detaylı kontrol.
    Kriterler:
    - Hemofili A/B tanısı
    - Faktör düzeyi (< %1 ağır, 1-5 orta, 5-40 hafif)
    - Hematoloji uzman raporu
    - İnhibitör varlığı (FEIBA/NovoSeven için)
    """
    sut_kurali = 'SUT 4.2.5 — Koagülasyon faktörleri hematoloji uzman raporu'
    detaylar = {'alt_kategori': 'KOAGULASYON_FAKTORU', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'Koagülasyon faktörü RAPORSUZ yazılmış! Hematoloji raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.5 - Hematoloji uzman raporu gerekli',
            sut_kurali=sut_kurali, aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    hemofili_a = any(k in metin_lower for k in ['hemofili a', 'faktör viii eksikliği',
                                                  'faktor viii eksik'])
    hemofili_b = any(k in metin_lower for k in ['hemofili b', 'faktör ix eksikliği',
                                                  'faktor ix eksik', 'christmas'])
    von_willebrand = any(k in metin_lower for k in ['von willebrand', 'vwd', 'vwf'])

    # Faktör düzeyi (% olarak)
    faktor, faktor_ibare = _lab_degeri_cek(birlesik, ['faktör viii', 'faktor viii',
                                                        'faktör ix', 'faktor ix',
                                                        'fviii', 'fix'])
    inhibitor_var = any(k in metin_lower for k in ['inhibitör', 'inhibitor',
                                                      'bethesda', 'bethesda ünitesi'])
    hematoloji = 'hematoloji' in metin_lower

    detaylar.update({
        'hemofili_a': hemofili_a, 'hemofili_b': hemofili_b,
        'von_willebrand': von_willebrand, 'faktor_duzey': faktor,
        'inhibitor': inhibitor_var, 'hematoloji': hematoloji
    })

    bilgiler = []
    if hemofili_a: bilgiler.append("Hemofili A")
    if hemofili_b: bilgiler.append("Hemofili B")
    if von_willebrand: bilgiler.append("von Willebrand")
    if faktor is not None: bilgiler.append(f"Faktör düzeyi: %{faktor}")
    if inhibitor_var: bilgiler.append("İnhibitör belirtilmiş")
    if hematoloji: bilgiler.append("Hematoloji uzman")

    if (hemofili_a or hemofili_b or von_willebrand) and hematoloji:
        uyarilar = ['Profilaksi veya tedavi dozu raporda olmalı']
        if faktor is None:
            uyarilar.append('Faktör düzeyi raporda belirtilmeli (< %1 ağır)')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Koagülasyon faktörü uygun (rapor {rapor_kodu}) — {' | '.join(bilgiler)}",
            detaylar=detaylar, uyari=' | '.join(uyarilar),
            sut_kurali=sut_kurali
        )

    if hemofili_a or hemofili_b or von_willebrand:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"Koagülasyon faktörü UYGUN DEĞİL: Hematoloji uzman raporu bulunamadı (rapor {rapor_kodu})",
            detaylar=detaylar,
            uyari=f"Endikasyon var: {', '.join(bilgiler)}. SUT 4.2.5 hematoloji ZORUNLU.",
            sut_kurali=sut_kurali,
            aranan_ibare='hematoloji uzman (zorunlu)'
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Koagülasyon faktörü UYGUN DEĞİL: Hemofili tanısı raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.5: Hemofili A/B/vWD tanısı + faktör düzeyi + hematoloji uzmanı ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='hemofili + faktör düzeyi + hematoloji (hepsi zorunlu)'
    )


def _esa_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin=""):
    """SUT 4.2.30 - ESA (Eritropoietin/Darbepoetin) detaylı kontrol.

    Kontrol edilen kriterler:
    - Ferritin > 100 ng/mL (demir deposu)
    - TSAT > %20 (transferrin satürasyonu)
    - Hb < 10 g/dL → başlama; 10-12 idame; > 12 kesilmeli
    - Uzman branş: Nefroloji / Hematoloji / Onkoloji
    - Endikasyon: KBY / hemodiyaliz / kronik böbrek / kemoterapi anemi

    Returns: KontrolRaporu
    """
    sut_kurali = 'SUT 4.2.30 — ESA (Eritropoietin) kullanım kuralları'
    detaylar = {'alt_kategori': 'ESA_ERITROPOIETIN', 'rapor_kodu': rapor_kodu}

    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'ESA ilacı RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='SUT 4.2.30 - Nefroloji/Hematoloji/Onkoloji uzman raporu gerekli',
            sut_kurali=sut_kurali,
            aranan_ibare='rapor'
        )

    birlesik = (metin or '') + ' ' + (teshis_metin or '')
    metin_lower = birlesik.replace('İ', 'i').replace('I', 'ı').lower()

    # ── Sayısal değerler ──
    hb, hb_ibare = _lab_degeri_cek(birlesik, ['hemoglobin', 'hgb', 'hb'])
    ferritin, ferritin_ibare = _lab_degeri_cek(birlesik, ['ferritin'])
    tsat, tsat_ibare = _lab_degeri_cek(birlesik, ['tsat', 'transferrin satürasyonu',
                                                    'transferrin saturasyonu',
                                                    'transferrin sat'])
    detaylar.update({'hb': hb, 'ferritin': ferritin, 'tsat': tsat})

    # ── Uzman branş ──
    uzman_var = any(k in metin_lower for k in ['nefroloji', 'hematoloji', 'onkoloji',
                                                 'iç hastalıkları', 'ic hastaliklari'])
    detaylar['uzman_var'] = uzman_var

    # ── Endikasyon ──
    kby = any(k in metin_lower for k in ['kronik böbrek', 'kronik bobrek', 'kby',
                                           'hemodiyaliz', 'periton diyaliz', 'diyaliz'])
    onkoloji = any(k in metin_lower for k in ['kemoterapi', 'onkoloji hastası',
                                                'malign', 'kemoterapiye bağlı anemi'])
    detaylar['endikasyon'] = 'KBY' if kby else ('Onkoloji' if onkoloji else 'Belirsiz')

    # ── Karar ağacı ──
    sorunlar = []
    bilgiler = []

    # Hb kontrolü
    if hb is not None:
        bilgiler.append(f"Hb: {hb} g/dL")
        if hb >= 13:
            sorunlar.append(f"Hb {hb} ≥ 13 — ESA kesilmeli (SUT: max 12)")
        elif hb > 12:
            sorunlar.append(f"Hb {hb} > 12 — doz azaltılmalı/kesilmeli")
    else:
        bilgiler.append("Hb değeri raporda bulunamadı")

    # Ferritin kontrolü
    if ferritin is not None:
        bilgiler.append(f"Ferritin: {ferritin} ng/mL")
        if ferritin <= 100:
            sorunlar.append(f"Ferritin {ferritin} ≤ 100 ng/mL — demir deposu yetersiz (SUT: >100)")
    else:
        bilgiler.append("Ferritin değeri raporda bulunamadı")

    # TSAT kontrolü
    if tsat is not None:
        bilgiler.append(f"TSAT: %{tsat}")
        if tsat <= 20:
            sorunlar.append(f"TSAT %{tsat} ≤ %20 — transferrin satürasyonu yetersiz (SUT: >%20)")
    else:
        bilgiler.append("TSAT değeri raporda bulunamadı")

    # Uzman branş kontrolü
    if not uzman_var:
        bilgiler.append("Uzman branş (Nefroloji/Hematoloji/Onkoloji) raporda açıkça belirtilmemiş")

    # ── Sonuç ──
    ozet = " | ".join(bilgiler)
    if sorunlar:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"ESA uygunsuz: {'; '.join(sorunlar)}",
            detaylar=detaylar,
            uyari=f"Lab bilgileri: {ozet}",
            sut_kurali=sut_kurali,
            aranan_ibare='Ferritin>100, TSAT>%20, Hb<12',
            bulunan_metin=hb_ibare or ferritin_ibare or tsat_ibare
        )

    # SUT 4.2.30 → 3 değer de ZORUNLU. En az biri eksikse UYGUN DEĞİL.
    eksikler = []
    if hb is None: eksikler.append("Hb")
    if ferritin is None: eksikler.append("Ferritin")
    if tsat is None: eksikler.append("TSAT")
    if eksikler:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"ESA UYGUN DEĞİL: ZORUNLU değerler eksik ({', '.join(eksikler)} bulunamadı)",
            detaylar=detaylar,
            uyari=f"Mevcut: {ozet}. Eksik: {', '.join(eksikler)} — SUT 4.2.30 raporda bulunmalı.",
            sut_kurali=sut_kurali,
            aranan_ibare='Hb + Ferritin + TSAT (hepsi zorunlu)'
        )

    # Tüm 3 değer var ve kriterlere uygun → UYGUN
    uyarilar = []
    if hb < 10:
        uyarilar.append("Hb < 10 → ESA başlama uygun")
    elif 10 <= hb <= 12:
        uyarilar.append("Hb 10-12 → idame dozu")
    if not uzman_var:
        uyarilar.append("Uzman branş ibaresi raporda açık değil (SUT: Nefro/Hema/Onko)")
    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        f"ESA uygun (rapor {rapor_kodu}) — {ozet}",
        detaylar=detaylar,
        uyari=' | '.join(uyarilar) if uyarilar else None,
        sut_kurali=sut_kurali,
        aranan_ibare='Ferritin>100 + TSAT>%20 + Hb<12',
        bulunan_metin=hb_ibare or ferritin_ibare or tsat_ibare
    )

    # Hiçbir sayısal değer bulunmadı — UYGUN DEĞİL
    # SUT 4.2.30 zorunlu kılıyor: Hb/Ferritin/TSAT raporda olmak ZORUNDA
    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'ESA UYGUN DEĞİL: Hb/Ferritin/TSAT değerleri raporda/reçetede bulunamadı',
        detaylar=detaylar,
        uyari='SUT 4.2.30: Raporda Hemoglobin, Ferritin ve TSAT değerleri ZORUNLU. Bulunamadı.',
        sut_kurali=sut_kurali,
        aranan_ibare='Hb + Ferritin + TSAT (hepsi ZORUNLU)'
    )


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
    Pratikte raporda kelime yazmaz — rapor kodu 04.05 + kombine etken madde yeterli sayılır.
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')

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
        elif 'hipertansiyon' in metin_lower or 'antihipertansif' in metin_lower:
            bulundu = True
            eslesen_kelime = "hipertansiyon"

    # Pragmatik: rapor kodu 04.05 (Arteriyel Hipertansiyon) varsa raporlu kombine ilaç
    # SUT gereği monoterapi yazılı kanıt aranır, ama Medula raporunda bu ibare bulunmaz.
    if not bulundu and rapor_kodu.startswith('04.05'):
        bulundu = True
        eslesen_kelime = f"rapor kodu {rapor_kodu}"

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
    # ASA gerektiren endikasyonlar: sadece "KAH" — iskemik inme ve PAH için SUT 4.2.15'te
    # ASA intoleransı ŞARTI yok (raporda Inme/PAH endikasyonu yeterli).
    asa_gereken = any(e in endikasyonlar for e in ['KAH/Anjiografi', 'KAH (ICD)'])
    asa_gereksiz = any(e in endikasyonlar for e in ['Koroner stent', 'AKS/MI', 'Doktor onayı (12 ay)',
                                                      'İskemik inme', 'Periferik arter'])

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
    # Varfarin varyasyonları: varfarin, warfarin, coumadin (ticari ad), kumadin, comadin (yanlış yazım)
    varfarin = bool(re.search(r'varfarin|warfarin|co?umadin|comadin|kumadin', metin_lower))
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
    SUT 4.2.24 - Solunum Sistemi İlaçları (Astım/KOAH) — Detaylı Kontrol

    Alt gruplar ve SUT kuralları:
    1.  SABA (Salbutamol, Terbutalin): Raporsuz, tüm hekimler
    2.  SAMA (İpratropium): Raporsuz, tüm hekimler
    3.  SABA+SAMA komb. (Combivent, İpramol): Raporsuz
    4.  ICS tek inhaler (Budesonid, Flutikazon vb.): Uzman raporu, 1 yıl
    5.  ICS nebülizasyon (Cortair, Pulmicort neb.): Rapor gerekli, 1 yıl
    6.  LABA tek (Formoterol, Salmeterol): Rapor gerekli, 1 yıl
    7.  LABA+ICS (Seretide, Symbicort vb.): Rapor, göğüs/alerji/iç hast./çocuk, 1 yıl
    8.  LAMA (Tiotropium, Glikopironyum vb.): KOAH raporu, göğüs hast., 1 yıl
    9.  LABA+LAMA (Anoro, Ultibro vb.): KOAH raporu, 1 yıl
    10. LABA+ICS+LAMA üçlü (Trelegy, Trimbow): 3 ay ICS+LABA başarısızlığı + ≥2 atak + mMRC≥2, 1 yıl
    11. LTRA (Montelukast, Zafirlukast): Rapor, iç hast./çocuk/göğüs/alerji, 1 yıl
    12. Omalizumab (Xolair): Sağlık kurulu, göğüs+alerji, ilk 16 hf + yıllık
    13. Anti-IL5/IL4 (Mepolizumab, Benralizumab, Dupilumab): Sağlık kurulu, eozinofil
    14. Roflumilast (Daxas): FEV1≤%50 + ≥2 atak/yıl, göğüs hast. 6 aylık rapor
    15. Teofilin: Raporsuz yazılabilir
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

    # ════════════════════════════════════════════════════════════════
    # 1. İLAÇ ALT GRUBU TESPİTİ
    # ════════════════════════════════════════════════════════════════

    # ICS etkin maddeleri (tek başına ve kombinasyonlarda kullanılır)
    ics_maddeler = ['BUDESONID', 'BUDEZONID', 'FLUTIKAZON', 'BEKLOMETAZON',
                    'SIKLESONID', 'MOMETAZON']
    # LABA etkin maddeleri
    laba_maddeler = ['FORMOTEROL', 'SALMETEROL', 'VILANTEROL', 'INDAKATEROL', 'OLODATEROL']
    # LAMA etkin maddeleri
    lama_maddeler = ['TIOTROPIUM', 'GLIKOPIRONYUM', 'UMEKLIDINYUM', 'AKLIDINYUM',
                     'GLICOPIRONYUM', 'REVEFENACIN']

    has_ics = any(m in etkin_madde for m in ics_maddeler)
    has_laba = any(m in etkin_madde for m in laba_maddeler)
    has_lama = any(m in etkin_madde for m in lama_maddeler)

    # ── Farmasötik form tespiti (nebülizasyon / inhaler / oral / enjeksiyon) ──
    ilac_adi_lower = ilac_adi.lower().replace('İ', 'i').replace('I', 'ı')
    is_nebulizasyon = any(k in ilac_adi_lower for k in [
        'neb', 'nebul', 'inhala', 'inh su', 'tek dozluk', 'ampul inh',
        'respiratör', 'nebülizasyon'])
    is_oral = any(k in ilac_adi_lower for k in ['tablet', 'film tablet', 'çiğneme', 'granül', 'şurup'])

    # ── SABA (kısa etkili beta-2 agonist) ──
    saba_maddeler_list = ['SALBUTAMOL', 'TERBUTALIN', 'FENOTEROL']
    saba_ticari = ['VENTOLIN', 'BUVENTOL', 'BRICANYL']
    is_saba = (any(m in etkin_madde for m in saba_maddeler_list) or
               any(t in ilac_adi for t in saba_ticari)) \
              and not has_ics and not has_lama

    # ── SAMA (kısa etkili antikolinerjik) ──
    is_sama = ('IPRATROPIUM' in etkin_madde or 'IPRATROPY' in etkin_madde or
               'ATROVENT' in ilac_adi) and not has_laba

    # ── SABA + SAMA kombinasyon ──
    saba_sama_ticari = ['COMBIVENT', 'IPRAMOL', 'DUOVENT', 'BERODUAL']
    is_saba_sama = any(t in ilac_adi for t in saba_sama_ticari) or \
                   (('SALBUTAMOL' in etkin_madde or 'FENOTEROL' in etkin_madde) and 'IPRATROPIUM' in etkin_madde)

    # ── ICS tek başına ──
    ics_ticari = ['PULMICORT', 'FLIXOTIDE', 'BECLOFORTE', 'ALVESCO', 'MIFLONIDE',
                  'CORTAIR', 'BUDICORT', 'NEUMOCORT', 'BUDECORT', 'BECLATE',
                  'CLENIL', 'ASMANEX', 'BECLOJET']
    is_ics_tek = (has_ics or any(t in ilac_adi for t in ics_ticari)) \
                 and not has_laba and not has_lama

    # ── LABA tek başına ──
    laba_ticari = ['FORADIL', 'OXIS', 'SEREVENT', 'ONBREZ', 'STRIVERDI']
    is_laba_tek = (has_laba or any(t in ilac_adi for t in laba_ticari)) \
                  and not has_ics and not has_lama

    # ── LABA+ICS kombinasyon ──
    laba_ics_ticari = ['SERETIDE', 'SYMBICORT', 'FOSTER', 'RELVAR', 'DUORESP',
                       'MIFLONIDE COMBI', 'AIRFLUSAL', 'BUFOMIX', 'FOKUSAL',
                       'VANNAIR', 'WIXELA', 'AIRDUO', 'BREO', 'FLUTIFORM']
    is_laba_ics = any(t in ilac_adi for t in laba_ics_ticari) or (has_laba and has_ics and not has_lama)

    # ── LAMA tek başına ──
    lama_ticari = ['SPIRIVA', 'INCRUSE', 'SEEBRI', 'BRETARIS', 'EKLIRA', 'TUDORZA']
    is_lama = (has_lama or any(t in ilac_adi for t in lama_ticari)) and not has_laba and not has_ics

    # ── LABA+LAMA ikili ──
    laba_lama_ticari = ['ANORO', 'ULTIBRO', 'SPIOLTO', 'DUAKLIR', 'BEVESPI', 'STIOLTO']
    is_laba_lama = any(t in ilac_adi for t in laba_lama_ticari) or (has_laba and has_lama and not has_ics)

    # ── Üçlü kombinasyon (LABA+ICS+LAMA) ──
    uclu_ticari = ['TRELEGY', 'TRIMBOW', 'ENERZAIR', 'BREQUAL', 'BREQAL', 'BREZTRI']
    is_uclu = any(t in ilac_adi for t in uclu_ticari) or (has_laba and has_ics and has_lama)

    # ── LTRA (Lökotrien reseptör antagonisti) ──
    is_ltra = 'MONTELUKAST' in etkin_madde or 'ZAFIRLUKAST' in etkin_madde or \
              any(t in ilac_adi for t in ['SINGULAIR', 'ONCEAIR', 'LUKASM', 'NOTTA',
                                           'DESMONT', 'AIRLUKAST', 'ACCOLATE'])

    # ── Omalizumab (Anti-IgE) ──
    is_omalizumab = 'OMALIZUMAB' in etkin_madde or 'XOLAIR' in ilac_adi

    # ── Anti-IL5 / Anti-IL4 biyolojikler ──
    is_mepolizumab = 'MEPOLIZUMAB' in etkin_madde or 'NUCALA' in ilac_adi
    is_benralizumab = 'BENRALIZUMAB' in etkin_madde or 'FASENRA' in ilac_adi
    is_dupilumab = 'DUPILUMAB' in etkin_madde or 'DUPIXENT' in ilac_adi
    is_anti_il = is_mepolizumab or is_benralizumab or is_dupilumab

    # ── Roflumilast (PDE4 inhibitörü) ──
    is_roflumilast = 'ROFLUMILAST' in etkin_madde or 'DAXAS' in ilac_adi or 'DALIRESP' in ilac_adi

    # ── Teofilin / Aminofilin ──
    is_teofilin = 'TEOFILIN' in etkin_madde or 'AMINOFILIN' in etkin_madde or \
                  any(t in ilac_adi for t in ['TEOBID', 'TALOTREN', 'AMINOCARDOL'])

    # ── Kromolin / Nedokromil ──
    is_kromolin = 'KROMOGLISIK' in etkin_madde or 'NEDOKROMIL' in etkin_madde or \
                  any(t in ilac_adi for t in ['INTAL', 'TILADE'])

    # ── Alt grup adı belirleme (öncelik sırası: spesifikten genele) ──
    if is_saba_sama:
        detaylar['alt_grup'] = 'SABA+SAMA kombinasyon'
    elif is_saba:
        detaylar['alt_grup'] = 'SABA'
    elif is_sama:
        detaylar['alt_grup'] = 'SAMA'
    elif is_teofilin:
        detaylar['alt_grup'] = 'Teofilin/Aminofilin'
    elif is_kromolin:
        detaylar['alt_grup'] = 'Kromolin/Nedokromil'
    elif is_omalizumab:
        detaylar['alt_grup'] = 'Omalizumab (Anti-IgE)'
    elif is_mepolizumab:
        detaylar['alt_grup'] = 'Mepolizumab (Anti-IL5)'
    elif is_benralizumab:
        detaylar['alt_grup'] = 'Benralizumab (Anti-IL5Rα)'
    elif is_dupilumab:
        detaylar['alt_grup'] = 'Dupilumab (Anti-IL4/IL13)'
    elif is_roflumilast:
        detaylar['alt_grup'] = 'Roflumilast (PDE4 inh.)'
    elif is_uclu:
        detaylar['alt_grup'] = 'LABA+ICS+LAMA (üçlü)'
    elif is_laba_ics:
        detaylar['alt_grup'] = 'LABA+ICS'
    elif is_laba_lama:
        detaylar['alt_grup'] = 'LABA+LAMA'
    elif is_lama:
        detaylar['alt_grup'] = 'LAMA'
    elif is_laba_tek:
        detaylar['alt_grup'] = 'LABA (tek)'
    elif is_ics_tek:
        if is_nebulizasyon:
            detaylar['alt_grup'] = 'ICS nebülizasyon'
        else:
            detaylar['alt_grup'] = 'ICS (inhaler)'
    elif is_ltra:
        detaylar['alt_grup'] = 'LTRA (Montelukast/Zafirlukast)'

    detaylar['form'] = 'nebülizasyon' if is_nebulizasyon else ('oral' if is_oral else 'inhaler')

    # ════════════════════════════════════════════════════════════════
    # 2. TANI TESPİTİ (ICD + metin tarama)
    # ════════════════════════════════════════════════════════════════

    astim = bool(re.search(r'ast[ıi]m|asthma', metin_lower))
    koah = bool(re.search(r'koah|copd|kronik\s*obstr[uü]ktif', metin_lower))
    alerjik_rinit = bool(re.search(r'alerjik\s*rinit|allergic\s*rhinitis', metin_lower))
    bronsiektazi = bool(re.search(r'bron[sş]iektazi|bronchiectasis', metin_lower))
    kistik_fibroz = bool(re.search(r'kistik\s*fibr[oö]z|cystic\s*fibrosis', metin_lower))

    icd_astim = any(k in teshis_metin for k in ['J45', 'J46'])
    icd_koah = any(k in teshis_metin for k in ['J43', 'J44'])
    icd_rinit = 'J30' in teshis_metin
    icd_bronsiektazi = 'J47' in teshis_metin

    astim = astim or icd_astim
    koah = koah or icd_koah
    alerjik_rinit = alerjik_rinit or icd_rinit
    bronsiektazi = bronsiektazi or icd_bronsiektazi

    detaylar['astim'] = astim
    detaylar['koah'] = koah
    detaylar['alerjik_rinit'] = alerjik_rinit
    detaylar['bronsiektazi'] = bronsiektazi

    # ════════════════════════════════════════════════════════════════
    # 3. UZMAN BRANŞ TESPİTİ
    # ════════════════════════════════════════════════════════════════

    gogus = bool(re.search(r'g[oö][gğ][uü]s\s*hastal|pulmonoloji|pneumoloji', metin_lower))
    alerji = _turkce_ara(metin_lower, 'alerji') or _turkce_ara(metin_lower, 'immunoloji') or \
             _turkce_ara(metin_lower, 'immünoloji')
    ic_hast = bool(re.search(r'i[cç]\s*hastal|dahiliye|internal\s*med', metin_lower))
    cocuk = bool(re.search(r'[cç]ocuk\s*sa[gğ]l|pediatri|[cç]ocuk\s*hastal', metin_lower))
    uzman_var = gogus or alerji or ic_hast or cocuk

    detaylar['uzman'] = {
        'gogus': gogus, 'alerji': alerji,
        'ic_hast': ic_hast, 'cocuk': cocuk
    }

    def _uzman_listesi() -> str:
        uzmanlar = []
        if gogus: uzmanlar.append('göğüs hastalıkları')
        if alerji: uzmanlar.append('alerji/immünoloji')
        if ic_hast: uzmanlar.append('iç hastalıkları')
        if cocuk: uzmanlar.append('çocuk sağlığı')
        return ', '.join(uzmanlar) if uzmanlar else ''

    # Eşleşen metin parçasını bul
    eslesen = ""
    for k in ['astım', 'astim', 'koah', 'copd', 'kronik obstr', 'göğüs hastal',
              'alerji', 'bronşiektazi', 'kistik fibroz', 'alerjik rinit']:
        p = _eslesen_parcayi_bul(birlesik, k)
        if p:
            eslesen = p
            break

    # ════════════════════════════════════════════════════════════════
    # 4. ALT GRUBA GÖRE DETAYLI SUT KONTROLÜ
    # ════════════════════════════════════════════════════════════════

    # ── SABA / SAMA / SABA+SAMA → Raporsuz, tüm hekimler yazabilir ──
    if is_saba or is_sama or is_saba_sama:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{detaylar["alt_grup"]} — raporsuz yazılabilir (tüm hekimler)',
            detaylar=detaylar, sut_kurali='SUT 4.2.24 — SABA/SAMA raporsuz kullanım',
            aranan_ibare='SABA/SAMA → rapor gerekmez',
            bulunan_metin=eslesen if eslesen else None
        )

    # ── Teofilin / Aminofilin → Raporsuz yazılabilir ──
    if is_teofilin:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{detaylar["alt_grup"]} — raporsuz yazılabilir (tüm hekimler)',
            detaylar=detaylar, sut_kurali='SUT 4.2.24 — Teofilin preparatları raporsuz',
            aranan_ibare='Teofilin/Aminofilin → rapor gerekmez',
            bulunan_metin=eslesen if eslesen else None
        )

    # ── Kromolin / Nedokromil → Raporsuz ──
    if is_kromolin:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{detaylar["alt_grup"]} — raporsuz yazılabilir',
            detaylar=detaylar, sut_kurali='SUT 4.2.24 — Kromoglisik asit/Nedokromil raporsuz',
            aranan_ibare='Kromolin → rapor gerekmez',
            bulunan_metin=eslesen if eslesen else None
        )

    # ── Omalizumab (Anti-IgE) → Sağlık kurulu raporu ──
    if is_omalizumab:
        yuksek_doz_ics = _turkce_ara(metin_lower, 'yüksek doz') or _turkce_ara(metin_lower, 'yuksek doz')
        ige = bool(re.search(r'ig\s*e|ige', metin_lower))
        ige_duzey = re.search(r'ig\s*e\s*[:=]?\s*(\d+)', metin_lower)
        ige_val = int(ige_duzey.group(1)) if ige_duzey else None
        ige_range_ok = (30 <= ige_val <= 1500) if ige_val else None
        kontrol_altinda_degil = _turkce_ara(metin_lower, 'kontrol altına alınamayan') or \
                                _turkce_ara(metin_lower, 'kontrol edilemeyen') or \
                                _turkce_ara(metin_lower, 'kontrol altında değil') or \
                                _turkce_ara(metin_lower, 'uncontrolled')
        saglik_kurulu = _turkce_ara(metin_lower, 'sağlık kurulu') or \
                        _turkce_ara(metin_lower, 'saglik kurulu')

        detaylar['ige'] = ige
        detaylar['ige_deger'] = ige_val
        detaylar['ige_30_1500'] = ige_range_ok
        detaylar['yuksek_doz_ics'] = yuksek_doz_ics
        detaylar['kontrol_altinda_degil'] = kontrol_altinda_degil

        if astim and (yuksek_doz_ics or kontrol_altinda_degil) and (ige or ige_val):
            mesaj_parts = ['Omalizumab — astım']
            if ige_val:
                mesaj_parts.append(f'IgE={ige_val} IU/mL')
                if not ige_range_ok:
                    mesaj_parts.append('(DİKKAT: 30-1500 aralığı dışı)')
            if yuksek_doz_ics:
                mesaj_parts.append('yüksek doz ICS')
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=' + '.join(mesaj_parts),
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — Omalizumab: göğüs+alerji sağlık kurulu raporu, '
                           'IgE 30-1500 IU/mL, ≥6 yaş, yüksek doz ICS+LABA yetersiz, '
                           'ilk 16 hafta değerlendirme, yıllık yenileme',
                uyari='Rapor süresi: ilk 16 hafta (değerlendirme) → yıllık yenileme. '
                      'Sağlık kurulu: göğüs hastalıkları + alerji/immünoloji' if not saglik_kurulu else None,
                aranan_ibare='astım + yüksek doz ICS başarısızlığı + IgE 30-1500',
                bulunan_metin=eslesen
            )
        eksik = []
        if not astim:
            eksik.append('astım tanısı')
        if not yuksek_doz_ics and not kontrol_altinda_degil:
            eksik.append('kontrol altına alınamama / yüksek doz ICS')
        if not ige and not ige_val:
            eksik.append('IgE düzeyi')
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Omalizumab — eksik: {", ".join(eksik)}',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — Omalizumab: göğüs+alerji sağlık kurulu raporu, '
                       'IgE 30-1500 IU/mL, ≥6 yaş, yüksek doz ICS+LABA yetersiz',
            uyari=f'Gerekli: (1) Alerjik astım tanısı, (2) Yüksek doz ICS+LABA\'ya rağmen kontrol edilememe, '
                  f'(3) IgE 30-1500 IU/mL, (4) ≥6 yaş, (5) Sağlık kurulu raporu (göğüs + alerji)',
            aranan_ibare='astım + IgE düzeyi + yüksek doz ICS başarısızlığı',
            bulunan_metin=eslesen
        )

    # ── Anti-IL5 / Anti-IL4 biyolojikler (Mepolizumab, Benralizumab, Dupilumab) ──
    if is_anti_il:
        biyolojik_adi = detaylar['alt_grup']
        eozinofil = re.search(r'eozinofil\s*[:=]?\s*(\d+)', metin_lower) or \
                    re.search(r'eo\s*[:=]?\s*(\d+)', metin_lower)
        eo_val = int(eozinofil.group(1)) if eozinofil else None
        agir_astim = _turkce_ara(metin_lower, 'ağır astım') or _turkce_ara(metin_lower, 'ciddi astım') or \
                     _turkce_ara(metin_lower, 'severe asthma')
        saglik_kurulu = _turkce_ara(metin_lower, 'sağlık kurulu') or \
                        _turkce_ara(metin_lower, 'saglik kurulu')
        kontrol_altinda_degil = _turkce_ara(metin_lower, 'kontrol altına alınamayan') or \
                                _turkce_ara(metin_lower, 'kontrol edilemeyen')

        if is_mepolizumab:
            eo_esik = 150
            ek_kural = 'eozinofil ≥150/µL (son 12 ay), ≥12 yaş'
        elif is_benralizumab:
            eo_esik = 300
            ek_kural = 'eozinofil ≥300/µL, ≥12 yaş'
        else:
            eo_esik = 150
            ek_kural = 'eozinofil ≥150/µL veya FeNO ≥25 ppb, ≥12 yaş'

        detaylar['eozinofil'] = eo_val
        detaylar['agir_astim'] = agir_astim

        if astim and (agir_astim or kontrol_altinda_degil) and eo_val and eo_val >= eo_esik:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'{biyolojik_adi} — ağır astım + eozinofil {eo_val}/µL ≥{eo_esik}',
                detaylar=detaylar,
                sut_kurali=f'SUT 4.2.24 — {biyolojik_adi}: sağlık kurulu raporu, '
                           f'{ek_kural}, yüksek doz ICS+LABA yetersiz, yıllık yenileme',
                uyari='Sağlık kurulu raporu zorunlu (göğüs hastalıkları + alerji/immünoloji). '
                      'İlk 4-6 ay değerlendirme, ardından yıllık yenileme.' if not saglik_kurulu else None,
                aranan_ibare=f'ağır eozinofilik astım + eozinofil ≥{eo_esik} + ICS+LABA başarısızlığı',
                bulunan_metin=eslesen
            )
        eksik = []
        if not astim:
            eksik.append('astım tanısı')
        if not agir_astim and not kontrol_altinda_degil:
            eksik.append('ağır/kontrol edilemeyen astım')
        if not eo_val:
            eksik.append(f'eozinofil sayısı (≥{eo_esik} gerekli)')
        elif eo_val < eo_esik:
            eksik.append(f'eozinofil {eo_val} < {eo_esik} eşik')
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'{biyolojik_adi} — eksik: {", ".join(eksik)}',
            detaylar=detaylar,
            sut_kurali=f'SUT 4.2.24 — {biyolojik_adi}: sağlık kurulu raporu, {ek_kural}',
            uyari=f'Gerekli: (1) Ağır eozinofilik astım, (2) Eozinofil ≥{eo_esik}/µL, '
                  f'(3) Yüksek doz ICS+LABA yetersiz, (4) Sağlık kurulu (göğüs + alerji)',
            aranan_ibare=f'ağır astım + eozinofil ≥{eo_esik}',
            bulunan_metin=eslesen
        )

    # ── Roflumilast → KOAH FEV1≤%50 + yılda ≥2 atak, göğüs hast. 6 aylık rapor ──
    if is_roflumilast:
        fev1_match = re.findall(r'fev1?\s*[:=<]?\s*(%?\d+)', metin_lower)
        fev1 = None
        if fev1_match:
            try:
                fev1 = int(fev1_match[0].replace('%', ''))
            except Exception:
                pass
        atak = bool(re.search(r'atak|alevlenme|eksaserbasyon|exacerbation', metin_lower))
        kronik_brons = bool(re.search(r'kronik\s*bron[sş]it|chronic\s*bronchitis', metin_lower))
        detaylar['fev1'] = fev1
        detaylar['atak'] = atak
        detaylar['kronik_brons'] = kronik_brons

        if koah and fev1 and fev1 <= 50 and atak:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Roflumilast — KOAH + FEV1 {fev1}% ≤50 + atak'
                      f'{" + kronik bronşit" if kronik_brons else ""}',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — Roflumilast: KOAH (FEV1≤%50) + kronik bronşit fenotipi + '
                           '≥2 atak/yıl, göğüs hastalıkları uzmanı, 6 aylık rapor',
                uyari='Rapor süresi: 6 AY (diğer solunum ilaçlarından farklı). '
                      'Yazabilecek uzman: SADECE göğüs hastalıkları.',
                aranan_ibare='KOAH + FEV1 ≤ %50 + yılda ≥2 atak + kronik bronşit',
                bulunan_metin=eslesen
            )
        eksik = []
        if not koah:
            eksik.append('KOAH tanısı')
        if not fev1:
            eksik.append('FEV1 değeri')
        elif fev1 > 50:
            eksik.append(f'FEV1 {fev1}% > 50 (≤50 gerekli)')
        if not atak:
            eksik.append('atak/alevlenme bilgisi')
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Roflumilast — eksik: {", ".join(eksik)}',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — Roflumilast: KOAH (FEV1≤%50) + kronik bronşit + ≥2 atak/yıl, '
                       'göğüs hast. 6 aylık rapor',
            uyari='Gerekli: (1) KOAH tanısı (J44), (2) FEV1≤%50, (3) Yılda ≥2 orta/ağır atak, '
                  '(4) Kronik bronşit fenotipi, (5) Göğüs hast. uzmanı 6 aylık rapor',
            aranan_ibare='KOAH + FEV1 ≤ %50 + atak sayısı',
            bulunan_metin=eslesen
        )

    # ── Üçlü kombinasyon (LABA+ICS+LAMA) → 3 ay ICS+LABA başarısızlığı ──
    if is_uclu:
        onceki_tedavi = bool(re.search(r'ics.*laba|iks.*laba|inhaler.*kortikosteroid|laba.*ics', metin_lower))
        yetersiz = _turkce_ara(metin_lower, 'yetersiz') or _turkce_ara(metin_lower, 'yeterli yanıt') or \
                   _turkce_ara(metin_lower, 'başarısız') or _turkce_ara(metin_lower, 'cevapsız') or \
                   _turkce_ara(metin_lower, 'inadequate') or _turkce_ara(metin_lower, 'kontrol altına alınamayan')
        atak = bool(re.search(r'atak|alevlenme|eksaserbasyon|exacerbation', metin_lower))
        dispne = bool(re.search(r'dispne|mmrc|cat\s*skor|nefes\s*darl|dyspnea', metin_lower))
        mmrc_match = re.search(r'mmrc\s*[:=]?\s*(\d)', metin_lower)
        cat_match = re.search(r'cat\s*(?:skor)?\s*[:=]?\s*(\d+)', metin_lower)
        mmrc_val = int(mmrc_match.group(1)) if mmrc_match else None
        cat_val = int(cat_match.group(1)) if cat_match else None

        detaylar['onceki_tedavi'] = onceki_tedavi or yetersiz
        detaylar['atak'] = atak
        detaylar['dispne'] = dispne
        detaylar['mmrc'] = mmrc_val
        detaylar['cat'] = cat_val

        if koah and (onceki_tedavi or yetersiz) and atak:
            semptom_bilgi = ""
            if mmrc_val is not None:
                semptom_bilgi += f', mMRC={mmrc_val}'
                if mmrc_val < 2:
                    semptom_bilgi += ' (DİKKAT: <2)'
            if cat_val is not None:
                semptom_bilgi += f', CAT={cat_val}'
                if cat_val < 10:
                    semptom_bilgi += ' (DİKKAT: <10)'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Üçlü kombinasyon — KOAH + ICS+LABA başarısızlığı + atak{semptom_bilgi}',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24.B — Üçlü: KOAH + en az 3 ay ICS+LABA yetersiz + '
                           '≥2 orta/ağır atak/yıl + mMRC≥2 veya CAT≥10, '
                           'göğüs hast. uzmanı, 1 yıllık rapor',
                uyari='Rapor süresi: 1 yıl. Yazabilecek uzman: göğüs hastalıkları.' if not gogus else None,
                aranan_ibare='KOAH + ICS+LABA öncesi tedavi + atak + dispne/mMRC/CAT',
                bulunan_metin=eslesen
            )
        if astim and (onceki_tedavi or yetersiz):
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='Üçlü kombinasyon — astım + ICS+LABA başarısızlığı (basamak tedavisi)',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — Üçlü (astım): ICS+LABA yetersiz yanıt → LAMA eklenmesi, '
                           'göğüs hast./alerji uzmanı, 1 yıllık rapor',
                aranan_ibare='astım + ICS+LABA yetersiz + basamak tedavisi',
                bulunan_metin=eslesen
            )
        eksik = []
        if not koah and not astim:
            eksik.append('KOAH/astım tanısı')
        if not onceki_tedavi and not yetersiz:
            eksik.append('ICS+LABA öncesi tedavi / yetersiz yanıt')
        if not atak and koah:
            eksik.append('atak bilgisi (≥2/yıl gerekli)')
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Üçlü kombinasyon — eksik: {", ".join(eksik)}',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24.B — Üçlü: en az 3 ay ICS+LABA başarısızlığı + ≥2 atak/yıl + mMRC≥2 gerekli',
            uyari='Gerekli: (1) KOAH veya ağır astım, (2) En az 3 ay ICS+LABA kullanılıp yetersiz yanıt, '
                  '(3) Yılda ≥2 orta/ağır atak (KOAH), (4) mMRC≥2 veya CAT≥10 (KOAH), '
                  '(5) Göğüs hast. uzmanı 1 yıllık rapor',
            aranan_ibare='ICS+LABA öncesi + atak + dispne/mMRC/CAT',
            bulunan_metin=eslesen
        )

    # ── LAMA tek → KOAH raporu gerekli ──
    if is_lama:
        detaylar['gerekli_tani'] = 'KOAH'
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları'

        if koah:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LAMA — KOAH tanısı mevcut{" + göğüs hast." if gogus else ""}',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LAMA: KOAH tanısı + göğüs hast. uzmanı raporu, 1 yıl',
                uyari='LAMA ilaçları SADECE KOAH endikasyonunda SGK kapsamındadır. '
                      'Astım için LAMA: ancak üçlü kombinasyon kapsamında.' if not gogus else None,
                aranan_ibare='KOAH tanısı (J43/J44) + göğüs hastalıkları raporu',
                bulunan_metin=eslesen
            )
        if astim:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='LAMA — astım tanısı var ancak LAMA için KOAH tanısı gerekli',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LAMA: KOAH endikasyonu gerekli',
                uyari='LAMA ilaçları SUT kapsamında sadece KOAH için ödenir. '
                      'Astımda LAMA kullanımı ancak üçlü kombinasyon (LABA+ICS+LAMA) kapsamında mümkündür.',
                aranan_ibare='KOAH tanısı (J43/J44)'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LAMA — KOAH tanısı tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — LAMA: KOAH + göğüs hast. uzmanı 1 yıllık rapor',
            uyari='Gerekli: (1) KOAH tanısı (J43/J44), (2) Göğüs hast. uzmanı raporu, (3) 1 yıl süreli',
            aranan_ibare='KOAH tanısı (J43/J44) + göğüs hastalıkları',
            bulunan_metin=eslesen
        )

    # ── LABA+LAMA ikili → KOAH raporu gerekli ──
    if is_laba_lama:
        detaylar['gerekli_tani'] = 'KOAH'
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları'

        if koah:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LABA+LAMA — KOAH tanısı mevcut{" + göğüs hast." if gogus else ""}',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+LAMA: KOAH tanısı + göğüs hast. uzmanı raporu, 1 yıl',
                uyari='Rapor süresi: 1 yıl. Yazabilecek uzman: göğüs hastalıkları.' if not gogus else None,
                aranan_ibare='KOAH tanısı (J43/J44)',
                bulunan_metin=eslesen
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LABA+LAMA — KOAH tanısı tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — LABA+LAMA: KOAH + göğüs hast. uzmanı 1 yıllık rapor',
            uyari='Gerekli: (1) KOAH tanısı (J43/J44), (2) Göğüs hast. uzmanı raporu, (3) 1 yıl süreli',
            aranan_ibare='KOAH tanısı (J43/J44)',
            bulunan_metin=eslesen
        )

    # ── ICS tek (inhaler veya nebülizasyon) ──
    if is_ics_tek:
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları / alerji / iç hastalıkları / çocuk sağlığı'

        if not metin_lower and not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'ICS {"nebülizasyon" if is_nebulizasyon else "inhaler"} — rapor/mesaj metni yok',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — ICS: astım/KOAH raporu gerekli, '
                           'göğüs/alerji/iç hast./çocuk uzmanı, 1 yıl',
                aranan_ibare='astım / KOAH raporu + uzman hekim'
            )

        if astim or koah:
            tani_adi = 'Astım' if astim else 'KOAH'
            uzman_str = f' + {_uzman_listesi()}' if uzman_var else ''
            form_str = 'nebülizasyon' if is_nebulizasyon else 'inhaler'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'ICS {form_str} — {tani_adi} tanısı{uzman_str}',
                detaylar=detaylar,
                sut_kurali=f'SUT 4.2.24 — ICS {"nebülizasyon" if is_nebulizasyon else ""}: '
                           f'{tani_adi} raporu, göğüs/alerji/iç hast./çocuk uzmanı, 1 yıl',
                uyari=f'Rapor süresi: 1 yıl. '
                      f'Yazabilecek uzmanlar: göğüs hast., alerji, iç hast., çocuk sağlığı.'
                      if not uzman_var else None,
                aranan_ibare=f'{tani_adi} tanısı + uzman raporu',
                bulunan_metin=eslesen
            )

        if bronsiektazi or kistik_fibroz:
            tani = 'Bronşiektazi' if bronsiektazi else 'Kistik fibrozis'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'ICS — {tani} tanısı mevcut',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — ICS: solunum hastalığı raporu',
                aranan_ibare=f'{tani} tanısı',
                bulunan_metin=eslesen
            )

        if uzman_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'ICS — uzman raporu mevcut ({_uzman_listesi()})',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — ICS: uzman hekim raporu, 1 yıl',
                aranan_ibare='göğüs / alerji / iç hast. / çocuk uzman raporu',
                bulunan_metin=eslesen
            )

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'ICS — rapor kodu {rapor_kodu} var ama astım/KOAH tanısı bulunamadı',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — ICS: astım (J45/J46) veya KOAH (J43/J44) tanısı gerekli',
                uyari='Raporda astım veya KOAH tanısı olmalı. '
                      'Rapor süresi: 1 yıl. Uzman: göğüs/alerji/iç hast./çocuk.',
                aranan_ibare='astım (J45/J46) / KOAH (J43/J44)'
            )

        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'ICS {"nebülizasyon" if is_nebulizasyon else "inhaler"} — '
                  f'astım/KOAH tanısı veya uzman raporu tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — ICS: astım/KOAH + uzman raporu + 1 yıl gerekli',
            uyari='Gerekli: (1) Astım veya KOAH tanısı, '
                  '(2) Göğüs hast./alerji/iç hast./çocuk sağlığı uzman raporu, (3) 1 yıl süreli',
            aranan_ibare='astım / KOAH / göğüs / alerji / iç hast. / çocuk'
        )

    # ── LABA tek başına → Rapor gerekli ──
    if is_laba_tek:
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları / alerji / iç hastalıkları / çocuk sağlığı'

        if astim or koah:
            tani_adi = 'Astım' if astim else 'KOAH'
            uzman_str = f' + {_uzman_listesi()}' if uzman_var else ''
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LABA tek — {tani_adi} tanısı{uzman_str}',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA: astım/KOAH raporu, göğüs/alerji/iç hast./çocuk, 1 yıl',
                uyari='DİKKAT: LABA tek başına astımda önerilmez (ICS ile birlikte kullanılmalı).'
                      if astim else None,
                aranan_ibare=f'{tani_adi} tanısı',
                bulunan_metin=eslesen
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LABA tek — astım/KOAH tanısı tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — LABA: astım/KOAH raporu gerekli, 1 yıl',
            uyari='Gerekli: (1) Astım veya KOAH tanısı, (2) Uzman raporu, (3) 1 yıl süreli',
            aranan_ibare='astım / KOAH tanısı',
            bulunan_metin=eslesen
        )

    # ── LABA+ICS kombinasyon → Rapor gerekli ──
    if is_laba_ics:
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları / alerji / iç hastalıkları / çocuk sağlığı'

        if not metin_lower and not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='LABA+ICS — rapor/mesaj metni yok',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+ICS: astım/KOAH raporu gerekli, '
                           'göğüs/alerji/iç hast./çocuk, 1 yıl',
                aranan_ibare='astım / KOAH raporu + uzman hekim'
            )

        if astim or koah:
            tani_adi = 'Astım' if astim else 'KOAH'
            uzman_str = f' + {_uzman_listesi()}' if uzman_var else ''
            basamak_bilgi = ''
            if astim:
                basamak_bilgi = ' (basamak 3-4 tedavi)'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LABA+ICS — {tani_adi} tanısı{uzman_str}{basamak_bilgi}',
                detaylar=detaylar,
                sut_kurali=f'SUT 4.2.24 — LABA+ICS: {tani_adi} raporu, '
                           f'göğüs/alerji/iç hast./çocuk uzmanı, 1 yıl',
                uyari=f'Rapor süresi: 1 yıl. '
                      f'Yazabilecek uzmanlar: göğüs hast., alerji, iç hast., çocuk sağlığı.'
                      if not uzman_var else None,
                aranan_ibare=f'{tani_adi} tanısı + uzman raporu',
                bulunan_metin=eslesen
            )

        if bronsiektazi or kistik_fibroz:
            tani = 'Bronşiektazi' if bronsiektazi else 'Kistik fibrozis'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LABA+ICS — {tani} tanısı mevcut',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+ICS: solunum hastalığı raporu',
                aranan_ibare=f'{tani} tanısı',
                bulunan_metin=eslesen
            )

        if uzman_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LABA+ICS — uzman raporu mevcut ({_uzman_listesi()})',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+ICS: uzman hekim raporu, 1 yıl',
                aranan_ibare='göğüs / alerji / iç hast. / çocuk uzman raporu',
                bulunan_metin=eslesen
            )

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'LABA+ICS — rapor kodu {rapor_kodu} var ama astım/KOAH tanısı bulunamadı',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+ICS: astım/KOAH tanısı gerekli',
                uyari='Raporda astım (J45/J46) veya KOAH (J43/J44) tanısı olmalı. '
                      'Rapor süresi: 1 yıl. Uzman: göğüs/alerji/iç hast./çocuk.',
                aranan_ibare='astım (J45/J46) / KOAH (J43/J44)'
            )

        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LABA+ICS — astım/KOAH tanısı veya uzman raporu tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — LABA+ICS: astım/KOAH + uzman raporu + 1 yıl',
            uyari='Gerekli: (1) Astım veya KOAH tanısı, '
                  '(2) Göğüs hast./alerji/iç hast./çocuk sağlığı uzman raporu, (3) 1 yıl süreli',
            aranan_ibare='astım / KOAH / göğüs / alerji / iç hast. / çocuk'
        )

    # ── LTRA (Montelukast / Zafirlukast) → Rapor gerekli ──
    if is_ltra:
        detaylar['rapor_suresi'] = '1 yıl'
        detaylar['yazabilecek_uzman'] = 'göğüs hastalıkları / alerji / iç hastalıkları / çocuk sağlığı'

        if astim or alerjik_rinit:
            tani_adi = 'Astım' if astim else 'Alerjik rinit'
            uzman_str = f' + {_uzman_listesi()}' if uzman_var else ''
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LTRA — {tani_adi} tanısı{uzman_str}',
                detaylar=detaylar,
                sut_kurali=f'SUT 4.2.24 — LTRA (Montelukast/Zafirlukast): '
                           f'{tani_adi} raporu, iç hast./çocuk/göğüs/alerji uzmanı, 1 yıl. '
                           f'Egzersiz astımı ve aspirin duyarlı astımda da kullanılabilir.',
                uyari=f'Rapor süresi: 1 yıl. '
                      f'Uzmanlar: iç hast., çocuk sağlığı, göğüs hast., alerji.'
                      if not uzman_var else None,
                aranan_ibare=f'{tani_adi} tanısı',
                bulunan_metin=eslesen
            )

        if koah:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='LTRA — KOAH tanısı var ancak LTRA endikasyonu astım/alerjik rinit',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LTRA: astım veya alerjik rinit endikasyonu',
                uyari='Montelukast/Zafirlukast SUT kapsamında astım ve alerjik rinit endikasyonlarında ödenir. '
                      'KOAH endikasyonu SUT\'ta tanımlı değildir.',
                aranan_ibare='astım (J45/J46) / alerjik rinit (J30)'
            )

        if uzman_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'LTRA — uzman raporu mevcut ({_uzman_listesi()})',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LTRA: uzman hekim raporu, 1 yıl',
                aranan_ibare='iç hast. / çocuk / göğüs / alerji uzman raporu',
                bulunan_metin=eslesen
            )

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'LTRA — rapor kodu {rapor_kodu} var ama astım/alerjik rinit tanısı bulunamadı',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LTRA: astım veya alerjik rinit tanısı gerekli',
                uyari='Raporda astım (J45/J46) veya alerjik rinit (J30) tanısı olmalı.',
                aranan_ibare='astım (J45/J46) / alerjik rinit (J30)'
            )

        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LTRA — astım/alerjik rinit tanısı tespit edilemedi',
            detaylar=detaylar,
            sut_kurali='SUT 4.2.24 — LTRA: astım/alerjik rinit + uzman raporu + 1 yıl',
            uyari='Gerekli: (1) Astım veya alerjik rinit tanısı, '
                  '(2) İç hast./çocuk/göğüs/alerji uzman raporu, (3) 1 yıl süreli',
            aranan_ibare='astım / alerjik rinit / göğüs / alerji / iç hast. / çocuk'
        )

    # ════════════════════════════════════════════════════════════════
    # 5. GENEL SOLUNUM İLACI (alt grup tespit edilemedi)
    # ════════════════════════════════════════════════════════════════

    if not metin_lower and not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Solunum ilacı ({detaylar["alt_grup"]}) — rapor/mesaj metni yok',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='astım / KOAH / göğüs hastalıkları raporu'
        )

    if astim or koah:
        tani_adi = 'Astım' if astim else 'KOAH'
        uzman_str = f' + {_uzman_listesi()}' if uzman_var else ''
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{tani_adi} tanısı mevcut{uzman_str} — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare=f'{tani_adi} tanısı (J45/J46 veya J43/J44)',
            bulunan_metin=eslesen
        )

    if bronsiektazi or kistik_fibroz:
        tani = 'Bronşiektazi' if bronsiektazi else 'Kistik fibrozis'
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{tani} tanısı mevcut — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare=f'{tani} tanısı',
            bulunan_metin=eslesen
        )

    if uzman_var:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Uzman raporu mevcut ({_uzman_listesi()}) — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            aranan_ibare='göğüs / alerji / iç hast. / çocuk uzman raporu',
            bulunan_metin=_eslesen_parcayi_bul(birlesik, 'göğüs' if gogus else ('alerji' if alerji else 'hastal'))
        )

    if rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Rapor kodu {rapor_kodu} var ama astım/KOAH tanısı bulunamadı — {detaylar["alt_grup"]}',
            detaylar=detaylar, sut_kurali=sut_kurali,
            uyari='Raporda astım (J45/J46) veya KOAH (J43/J44) tanısı olmalı',
            aranan_ibare='astım (J45/J46) / KOAH (J43/J44)'
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=f'Astım/KOAH tanısı veya uzman raporu tespit edilemedi — {detaylar["alt_grup"]}',
        detaylar=detaylar, sut_kurali=sut_kurali,
        uyari='Solunum ilacı için gerekli: astım/KOAH tanısı + uzman raporu',
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
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _buyume_hormonu_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

    # ── 3. Eritropoietin / ESA (SUT 4.2.30) ──
    esa_etkin = ['ERITROPOIETIN', 'ERITROPOETIN', 'EPOETIN', 'DARBEPOETIN',
                 'DARBEPOETIN ALFA', 'METOKSIPOLIETILENGLIKOL']
    esa_ilac = ['EPREX', 'NEORECORMON', 'ARANESP', 'MIRCERA', 'BINOCRIT',
                'RETACRIT', 'ERYPRO', 'EPOBEL', 'EPOKINE', 'EPORON',
                'DYNEPO', 'ABSEAMED', 'BIOPOIN', 'SILAPO']
    esa_mi = any(_turkce_ara(etkin_madde, e) for e in esa_etkin) or \
             any(i in ilac_adi for i in esa_ilac)

    if esa_mi:
        # Detaylı ESA kontrolü — Hb/Ferritin/TSAT sayısal kontrol + uzman branş + endikasyon
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _esa_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

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
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _immunsupresif_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

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
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _biyolojik_tnf_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

    # ── 6. İmmünglobulinler (SUT 4.2.6) ──
    ivig_etkin = ['IMMUNOGLOBULIN', 'IMMÜNGLOBULIN', 'IMMUNGLOBULIN']
    ivig_ilac = ['OCTAGAM', 'PRIVIGEN', 'KIOVIG', 'FLEBOGAMMA', 'HIZENTRA',
                 'CUTAQUIG', 'INTRATECT', 'IVIG', 'SUBCUVIA']
    ivig_mi = any(_turkce_ara(etkin_madde, e) for e in ivig_etkin) or \
              any(i in ilac_adi for i in ivig_ilac)

    if ivig_mi:
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _ivig_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

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
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _koagulasyon_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin_local)

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

    # ── 11. NSAİD / Antiinflamatuarlar (SUT EK-4/A — Raporsuz yazılabilir) ──
    nsaid_etkin = ['ETODOLAK', 'ETODOLAC', 'DIKLOFENAK', 'NAPROKSEN', 'IBUPROFEN',
                   'MELOKSIKAM', 'PIROKSIKAM', 'TENOKSIKAM', 'LORNOKSIKAM',
                   'INDOMETASIN', 'INDOMETAZIN', 'KETOPROFEN', 'FLURBIPROFEN',
                   'DEKKETOPROFEN', 'DEKSKETOPROFEN', 'ASETILSALISILIK',
                   'NIMESULID', 'SELEKOKSIB', 'ETORIKOKSIB', 'ASEKLOFENAC',
                   'NABUMETON', 'TOLMETIN', 'FENOPROFEN', 'OKSAPROZIN',
                   'DIFLUNISAL', 'SULINDAK']
    nsaid_ilac = ['ETOL', 'ETODOL', 'ETOPAN', 'LODINE',
                  'VOLTAREN', 'DIKLORON', 'DICLOMEC', 'ARTROTEC',
                  'NAPROSYN', 'APRANAX', 'PROXEN', 'NAPREN',
                  'BRUFEN', 'ADVIL', 'NUROFEN',
                  'MELOX', 'MOBIC', 'ZELOXIM',
                  'PIROXICAM', 'FELDENE', 'BREXIN',
                  'XEFO', 'LOXIDOL',
                  'PROFENID', 'KETOPROF',
                  'ARVELES', 'DEXOFEN', 'DEKSALGIN',
                  'CELEBREX', 'CELECOX',
                  'ARCOXIA', 'ETORIX',
                  'AIRTAL', 'PRESERVEX']
    nsaid_mi = any(_turkce_ara(etkin_madde, e) for e in nsaid_etkin) or \
               any(i in ilac_adi for i in nsaid_ilac)

    if nsaid_mi:
        detaylar = {'alt_kategori': 'NSAID_ANTIINFLAMATUAR'}
        uyarilar = []
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu} (NSAİD için genelde rapor zorunlu değil)')
        uyarilar.append('NSAİD kullanım süresi ve GİS koruma (PPI) kontrolü önerilir')
        uyarilar.append('Renal fonksiyon ve kardiyovasküler risk dikkat edilmeli')
        if _turkce_ara(ilac_adi, 'SR') or _turkce_ara(ilac_adi, 'RETARD') or \
           _turkce_ara(ilac_adi, 'UZATILMIS'):
            uyarilar.append('Uzatılmış salım formu — günde 1 doz yeterli olabilir')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"NSAİD (antiinflamatuar) — raporsuz yazılabilir",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT EK-4/A — NSAİD ilaçlar raporsuz reçete edilebilir'
        )

    # ── 12. Antiepileptikler (SUT 4.2.1) ──
    antiepil_etkin = ['PREGABALIN', 'GABAPENTIN', 'LEVETIRASETAM', 'LAMOTRIJIN',
                      'KARBAMAZEPIN', 'OKSKARBAZAPIN', 'VALPROIK', 'VALPROAT',
                      'TOPIRAMAT', 'ZONISAMID', 'LAKOSAMID', 'PERAMPANEL',
                      'BRIVARASETAM', 'ESLIKARBAZAPIN', 'FENITOIN', 'FENOBARBITAL',
                      'ETOSUKSIMID', 'KLOBAZAM', 'KLONAZEPAM', 'VIGABATRIN',
                      'STIRIPENTOL', 'RUFINAMID']
    antiepil_ilac = ['LYRICA', 'PREGABALIN', 'NEURONTIN', 'GABAPENTIN', 'GABANTIN',
                     'KEPPRA', 'LEVEBON', 'EPITERRA',
                     'LAMICTAL', 'LAMOTRIX',
                     'TEGRETOL', 'KARBALEX',
                     'TRILEPTAL', 'OXCARON',
                     'DEPAKIN', 'CONVULEX',
                     'TOPAMAX', 'TOPAMAC',
                     'ZONEGRAN', 'VIMPAT', 'FYCOMPA',
                     'EPANUTIN', 'LUMINAL', 'RIVOTRIL', 'FRISIUM']
    antiepil_mi = any(_turkce_ara(etkin_madde, e) for e in antiepil_etkin) or \
                  any(i in ilac_adi for i in antiepil_ilac)

    if antiepil_mi:
        detaylar = {'alt_kategori': 'ANTIEPILEPTIK', 'sut_maddesi': '4.2.1'}
        uyarilar = []
        pregabalin_mi = _turkce_ara(etkin_madde, 'pregabalin') or \
                        any(i in ilac_adi for i in ['LYRICA', 'PREGABALIN'])
        gabapentin_mi = _turkce_ara(etkin_madde, 'gabapentin') or \
                        any(i in ilac_adi for i in ['NEURONTIN', 'GABAPENTIN', 'GABANTIN'])

        if pregabalin_mi:
            detaylar['alt_grup'] = 'PREGABALIN'
            if not rapor_kodu:
                uyarilar.append('Pregabalin: Nöroloji/Algoloji/FTR uzman raporu gerekli')
                uyarilar.append('Epilepsi dışı endikasyon (nöropatik ağrı): maks 600 mg/gün')
                uyarilar.append('Rapor süresi: 1 yıl')
                return KontrolRaporu(
                    KontrolSonucu.UYGUN_DEGIL,
                    'Pregabalin RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                    detaylar=detaylar,
                    uyari=' | '.join(uyarilar),
                    sut_kurali='SUT 4.2.1 — Pregabalin uzman raporu ile reçete edilir (maks 600 mg/gün)'
                )
            uyarilar.append('Pregabalin maks doz: 600 mg/gün (nöropatik ağrı)')
            uyarilar.append('Rapor süresi: 1 yıl | İlk reçete: Nöroloji/Algoloji/FTR uzmanı')
        elif gabapentin_mi:
            detaylar['alt_grup'] = 'GABAPENTIN'
            if not rapor_kodu:
                uyarilar.append('Gabapentin: Nöroloji uzman raporu gerekli (epilepsi dışı endikasyon)')
                return KontrolRaporu(
                    KontrolSonucu.UYGUN_DEGIL,
                    'Gabapentin RAPORSUZ yazılmış! Nöroloji uzman raporu ZORUNLU',
                    detaylar=detaylar,
                    uyari=' | '.join(uyarilar),
                    sut_kurali='SUT 4.2.1 — Gabapentin nöroloji uzman raporu ile reçete edilir'
                )
            uyarilar.append('Gabapentin maks doz: 3600 mg/gün')
            uyarilar.append('Rapor süresi ve endikasyon kontrol edilmeli')
        else:
            if not rapor_kodu:
                return KontrolRaporu(
                    KontrolSonucu.KONTROL_EDILEMEDI,
                    'Antiepileptik ilaç — rapor kodu bulunamadı',
                    detaylar=detaylar,
                    uyari='Epilepsi tanısı ile raporsuz yazılabilir, nöropatik ağrı için rapor gerekli',
                    sut_kurali='SUT 4.2.1 — Antiepileptik ilaçlar endikasyona göre rapor gerektirebilir'
                )
            uyarilar.append('Antiepileptik ilaç — rapor içeriği ve endikasyon kontrol edilmeli')

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Antiepileptik — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar) if uyarilar else 'Rapor süresi ve endikasyon kontrol edilmeli',
            sut_kurali='SUT 4.2.1 — Antiepileptik ilaçlar endikasyona göre uzman raporu gerektirir'
        )

    # ── 13. Alzheimer İlaçları (SUT 4.2.27) ──
    alzheimer_etkin = ['DONEPEZIL', 'RIVASTIGMIN', 'RIVASTIGMINE', 'GALANTAMIN',
                       'MEMANTIN', 'MEMANTINE']
    alzheimer_ilac = ['ARICEPT', 'DONECEPT', 'REMINYL', 'EXELON',
                      'EBIXA', 'MEMANTINE', 'MEMANTIN']
    alzheimer_mi = any(_turkce_ara(etkin_madde, e) for e in alzheimer_etkin) or \
                   any(i in ilac_adi for i in alzheimer_ilac)

    if alzheimer_mi:
        detaylar = {'alt_kategori': 'ALZHEIMER', 'sut_maddesi': '4.2.27'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Alzheimer ilacı RAPORSUZ yazılmış! Nöroloji/Psikiyatri uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.27 - Nöroloji veya Psikiyatri uzman raporu gerekli (6 aylık)',
                sut_kurali='SUT 4.2.27 — Alzheimer ilaçları nöroloji/psikiyatri uzman raporu ile verilir'
            )
        uyarilar = ['Nöroloji veya Psikiyatri uzman raporu olmalı',
                    'Rapor süresi: 6 ay',
                    'MMSE/MoCA skoru raporda belirtilmeli',
                    'Devam reçetesinde tedavi yanıtı değerlendirilmeli']
        if metin:
            if _turkce_ara(metin, 'mmse') or _turkce_ara(metin, 'moca'):
                uyarilar.insert(0, 'Kognitif test skoru raporda tespit edildi')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Alzheimer ilacı — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.27 — Alzheimer ilaçları 6 aylık uzman raporu ile verilir'
        )

    # ── 14. Parkinson İlaçları (SUT 4.2.3) ──
    parkinson_etkin = ['LEVODOPA', 'KARBIDOPA', 'BENSERAZID', 'PRAMIPEKSOL',
                       'ROPINIROL', 'ROTIGOTIN', 'ENTAKAPON', 'OPICAPON',
                       'TOLKAPON', 'AMANTADIN', 'APOMORFIN']
    parkinson_ilac = ['MADOPAR', 'SINEMET', 'STALEVO', 'MIRAPEX', 'PEXOLA',
                      'REQUIP', 'NEUPRO', 'COMTAN', 'ONGENTYS', 'TASMAR',
                      'SYMMETREL', 'PK-MERZ']
    parkinson_mi = any(_turkce_ara(etkin_madde, e) for e in parkinson_etkin) or \
                   any(i in ilac_adi for i in parkinson_ilac)

    if parkinson_mi:
        detaylar = {'alt_kategori': 'PARKINSON', 'sut_maddesi': '4.2.3'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.KONTROL_EDILEMEDI,
                'Parkinson ilacı — rapor kodu bulunamadı',
                detaylar=detaylar,
                uyari='Levodopa/Karbidopa raporsuz yazılabilir, dopamin agonistleri rapor gerektirebilir',
                sut_kurali='SUT 4.2.3 — Parkinson ilaçları endikasyona göre uzman raporu gerektirebilir'
            )
        uyarilar = ['Nöroloji uzman raporu kontrol edilmeli',
                    'Parkinson tanısı ve evre raporda belirtilmeli']
        if _turkce_ara(etkin_madde, 'pramipeksol') or _turkce_ara(etkin_madde, 'ropinirol') or \
           _turkce_ara(etkin_madde, 'rotigotin'):
            uyarilar.append('Dopamin agonisti — uzman raporu zorunlu')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Parkinson ilacı — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.3 — Parkinson ilaçları nöroloji uzman raporu ile verilir'
        )

    # ── 15. Hepatit B/C İlaçları (SUT 4.2.19) ──
    hepatit_etkin = ['ENTEKAVIR', 'TENOFOVIR', 'TENOFOVIR DISOPROKSIL',
                     'TENOFOVIR ALAFENAMID', 'LAMIVUDIN',
                     'SOFOSBUVIR', 'LEDIPASVIR', 'VELPATASVIR', 'GLECAPREVIR',
                     'PIBRENTASVIR', 'DAKLATASVIR', 'OMBITASVIR', 'PARITAPREVIR',
                     'DASABUVIR', 'RIBAVIRIN', 'PEGINTERFERON']
    hepatit_ilac = ['BARACLUDE', 'VIREAD', 'VEMLIDY', 'ZEFFIX', 'HEPSERA',
                    'SOVALDI', 'HARVONI', 'EPCLUSA', 'MAVYRET', 'MAVIRET',
                    'DAKLINZA', 'VIEKIRAX', 'EXVIERA', 'COPEGUS', 'PEGASYS',
                    'PEGINTRON']
    hepatit_mi = any(_turkce_ara(etkin_madde, e) for e in hepatit_etkin) or \
                 any(i in ilac_adi for i in hepatit_ilac)

    if hepatit_mi:
        detaylar = {'alt_kategori': 'HEPATIT', 'sut_maddesi': '4.2.19'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Hepatit ilacı RAPORSUZ yazılmış! Gastroenteroloji/Enfeksiyon uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.19 - Gastroenteroloji veya Enfeksiyon hastalıkları uzman raporu gerekli',
                sut_kurali='SUT 4.2.19 — Hepatit ilaçları uzman raporu ile verilir'
            )
        uyarilar = ['Gastroenteroloji / Enfeksiyon hastalıkları uzman raporu olmalı',
                    'HBV DNA / HCV RNA düzeyi raporda belirtilmeli',
                    'Tedavi süresi ve protokol kontrol edilmeli']
        if metin:
            if _turkce_ara(metin, 'hepatit b') or _turkce_ara(metin, 'hbv'):
                uyarilar.insert(0, 'Hepatit B tanısı tespit edildi')
            elif _turkce_ara(metin, 'hepatit c') or _turkce_ara(metin, 'hcv'):
                uyarilar.insert(0, 'Hepatit C tanısı tespit edildi')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Hepatit ilacı — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.19 — Hepatit ilaçları uzman raporu ile verilir'
        )

    # ── 16. Anti-VEGF Göz İlaçları (SUT 4.2.12.C) ──
    antivegf_etkin = ['RANIBIZUMAB', 'AFLIBERSEPT', 'BROLUCIZUMAB', 'FARICIMAB',
                      'BEVACIZUMAB']
    antivegf_ilac = ['LUCENTIS', 'EYLEA', 'BEOVU', 'VABYSMO', 'AVASTIN']
    antivegf_mi = any(_turkce_ara(etkin_madde, e) for e in antivegf_etkin) or \
                  any(i in ilac_adi for i in antivegf_ilac)

    if antivegf_mi:
        detaylar = {'alt_kategori': 'ANTI_VEGF_GOZ', 'sut_maddesi': '4.2.12.C'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Anti-VEGF göz ilacı RAPORSUZ yazılmış! Göz hastalıkları uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.12.C - Göz hastalıkları uzman raporu gerekli',
                sut_kurali='SUT 4.2.12.C — Anti-VEGF göz ilaçları uzman raporu ile verilir'
            )
        uyarilar = ['Göz hastalıkları uzman raporu olmalı',
                    'OCT bulgusu ve görme keskinliği raporda belirtilmeli',
                    'Enjeksiyon sayısı ve aralığı kontrol edilmeli',
                    'Rapor süresi: 6 ay']
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Anti-VEGF göz ilacı — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.12.C — Anti-VEGF göz ilaçları 6 aylık uzman raporu ile verilir'
        )

    # ── 17. Osteoporoz Biyolojik İlaçları (SUT 4.2.28.C) ──
    osteo_biyo_etkin = ['DENOSUMAB', 'TERIPARATID', 'TERIPARATIDE',
                        'ROMOSOZUMAB', 'STRONSIYUM RANELAT']
    osteo_biyo_ilac = ['PROLIA', 'XGEVA', 'FORTEO', 'FORSTEO', 'MOVYMIA',
                       'EVENITY', 'PROTELOS']
    osteo_biyo_mi = any(_turkce_ara(etkin_madde, e) for e in osteo_biyo_etkin) or \
                    any(i in ilac_adi for i in osteo_biyo_ilac)

    if osteo_biyo_mi:
        detaylar = {'alt_kategori': 'OSTEOPOROZ_BIYOLOJIK', 'sut_maddesi': '4.2.28.C'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Osteoporoz biyolojik ilacı RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.28.C - Endokrinoloji/Romatoloji/FTR uzman raporu gerekli',
                sut_kurali='SUT 4.2.28.C — Osteoporoz biyolojik ilaçları uzman raporu ile verilir'
            )
        uyarilar = ['Endokrinoloji/Romatoloji/FTR uzman raporu olmalı',
                    'T-skoru raporda belirtilmeli (T ≤ -2.5 veya kırık öyküsü)',
                    'Bifosfonat intoleransı/kontrendikasyonu belirtilmeli (basamak tedavi)']
        xgeva_mi = 'XGEVA' in ilac_adi or _turkce_ara(etkin_madde, 'denosumab')
        if xgeva_mi and rapor_kodu and rapor_kodu.startswith('02.'):
            uyarilar.append('Onkoloji endikasyonu (kemik metastazı) olabilir — onkoloji raporu kontrol edilmeli')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Osteoporoz biyolojik — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.28.C — Osteoporoz biyolojik ilaçları uzman raporu ile verilir'
        )

    # ── 18. PPI - Proton Pompa İnhibitörleri (Raporsuz yazılabilir) ──
    ppi_etkin = ['OMEPRAZOL', 'LANSOPRAZOL', 'PANTOPRAZOL', 'RABEPRAZOL',
                 'ESOMEPRAZOL', 'DEKSLANSOPRAZOL']
    ppi_ilac = ['LOSEC', 'NEXIUM', 'LANSOR', 'OGASTRO', 'PANTPAS', 'CONTROLOC',
                'PARIET', 'DEXILANT', 'EMANERA', 'ESOPRAL',
                'PANTOPRAZOL', 'LANSOR']
    ppi_mi = any(_turkce_ara(etkin_madde, e) for e in ppi_etkin) or \
             any(i in ilac_adi for i in ppi_ilac)

    if ppi_mi:
        uyarilar = ['PPI raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        uyarilar.append('Uzun süreli PPI kullanımında (>8 hafta) endikasyon sorgulanmalı')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'PPI (proton pompa inhibitörü) — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'PPI_PROTON_POMPA'},
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT — PPI ilaçlar raporsuz reçete edilebilir'
        )

    # ── 19. BPH / Alfa Bloker / İnkontinans İlaçları (SUT 4.2.16) ──
    bph_etkin = ['TAMSULOSIN', 'ALFUZOSIN', 'SILODOSIN', 'TERAZOSIN',
                 'SOLIFENASIN', 'DARIFENASIN', 'FESOTERODIN', 'TOLTERODINE',
                 'OKSIBUTININ', 'MIRABEGRON', 'DUTASTERID', 'FINASTERID',
                 'DUTASTERID/TAMSULOSIN']
    bph_ilac = ['FLOMAX', 'TAMSOL', 'TAMEK', 'XATRAL', 'UROREC', 'RAPAFLO',
                'VESICARE', 'ENABLEX', 'TOVIAZ', 'DETRUSITOL', 'DITROPAN',
                'BETMIGA', 'AVODART', 'PROSCAR', 'COMBODART', 'DUODART']
    bph_mi = any(_turkce_ara(etkin_madde, e) for e in bph_etkin) or \
             any(i in ilac_adi for i in bph_ilac)

    if bph_mi:
        detaylar = {'alt_kategori': 'BPH_INKONTINANS'}
        solifenasin_mi = _turkce_ara(etkin_madde, 'solifenasin') or 'VESICARE' in ilac_adi
        mirabegron_mi = _turkce_ara(etkin_madde, 'mirabegron') or 'BETMIGA' in ilac_adi
        dutasterid_mi = _turkce_ara(etkin_madde, 'dutasterid') or _turkce_ara(etkin_madde, 'finasterid') or \
                        any(i in ilac_adi for i in ['AVODART', 'PROSCAR', 'COMBODART', 'DUODART'])

        if solifenasin_mi or mirabegron_mi:
            detaylar['sut_maddesi'] = '4.2.16.B'
            if not rapor_kodu:
                return KontrolRaporu(
                    KontrolSonucu.UYGUN_DEGIL,
                    'İnkontinans ilacı RAPORSUZ yazılmış! Üroloji uzman raporu ZORUNLU',
                    detaylar=detaylar,
                    uyari='SUT 4.2.16.B - Üroloji uzman raporu gerekli (aşırı aktif mesane)',
                    sut_kurali='SUT 4.2.16.B — İnkontinans ilaçları üroloji uzman raporu ile verilir'
                )
            uyarilar = ['Üroloji uzman raporu olmalı',
                        'Aşırı aktif mesane tanısı raporda belirtilmeli',
                        'Ürodinami sonucu kontrol edilmeli']
            return KontrolRaporu(
                KontrolSonucu.UYGUN,
                f"İnkontinans ilacı — rapor kodu {rapor_kodu}",
                detaylar=detaylar,
                uyari=' | '.join(uyarilar),
                sut_kurali='SUT 4.2.16.B — İnkontinans ilaçları üroloji uzman raporu ile verilir'
            )

        if dutasterid_mi:
            detaylar['sut_maddesi'] = '4.2.16'
            if not rapor_kodu:
                return KontrolRaporu(
                    KontrolSonucu.UYGUN_DEGIL,
                    '5-alfa redüktaz inhibitörü RAPORSUZ yazılmış! Üroloji uzman raporu ZORUNLU',
                    detaylar=detaylar,
                    uyari='SUT 4.2.16 - Üroloji uzman raporu gerekli',
                    sut_kurali='SUT 4.2.16 — BPH ilaçları üroloji uzman raporu ile verilir'
                )
            return KontrolRaporu(
                KontrolSonucu.UYGUN,
                f"5-alfa redüktaz inhibitörü — rapor kodu {rapor_kodu}",
                detaylar=detaylar,
                uyari='Üroloji uzman raporu ve prostat boyutu kontrol edilmeli',
                sut_kurali='SUT 4.2.16 — BPH ilaçları üroloji uzman raporu ile verilir'
            )

        # Alfa blokerler (tamsulosin vb.) — genelde raporsuz yazılabilir
        uyarilar = ['Alfa bloker — BPH endikasyonu ile raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'Alfa bloker (BPH) — raporsuz yazılabilir',
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT — Alfa blokerler raporsuz reçete edilebilir'
        )

    # ── 20. Opioid Analjezikler (Kırmızı/Yeşil Reçete) ──
    opioid_etkin = ['MORFIN', 'FENTANIL', 'OKSIKODON', 'HIDROKODON',
                    'BUPRENORFIN', 'TAPENTADOL', 'KODEIN', 'PETIDIN',
                    'METADON']
    opioid_ilac = ['MSCONTIN', 'DUROGESIC', 'OXYCONTIN', 'MATRIFEN',
                   'FENTANYL', 'SUBOXONE', 'PALEXIA', 'TRAMAL',
                   'CODEINE', 'DOLCONTRAL']
    opioid_mi = any(_turkce_ara(etkin_madde, e) for e in opioid_etkin) or \
                any(i in ilac_adi for i in opioid_ilac)

    if opioid_mi:
        detaylar = {'alt_kategori': 'OPIOID_ANALJEZIK'}
        uyarilar = ['Kırmızı/Yeşil reçete türü kontrolü gerekli',
                    'Opioid reçete süresi ve doz aşımı kontrol edilmeli']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
            if rapor_kodu.startswith('02.'):
                uyarilar.append('Onkoloji endikasyonu — kronik ağrı protokolü uygun')
        else:
            uyarilar.append('Onkolojik ağrı dışı kullanımda rapor gerekebilir')
        return KontrolRaporu(
            KontrolSonucu.UYGUN if rapor_kodu else KontrolSonucu.KONTROL_EDILEMEDI,
            f"Opioid analjezik — {'rapor kodu ' + rapor_kodu if rapor_kodu else 'rapor kodu yok'}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='Opioid analjezikler kırmızı/yeşil reçete ile yazılır, onkoloji dışı uzun süreli kullanımda rapor gerekebilir'
        )

    # ── 21. Tıbbi Beslenme Ürünleri (SUT 4.2.4) ──
    tbu_etkin = ['ENTERAL BESLENME', 'PARENTERAL BESLENME']
    tbu_ilac = ['ENSURE', 'FRESUBIN', 'NUTRISON', 'RESOURCE', 'FORTIMEL',
                'ISOSOURCE', 'MODULEN', 'PEPTAMEN', 'NUTREN', 'IMPACT',
                'NEOCATE', 'INFATRINI', 'NUTRAMIGEN']
    tbu_mi = any(_turkce_ara(etkin_madde, e) for e in tbu_etkin) or \
             any(i in ilac_adi for i in tbu_ilac)

    if tbu_mi:
        detaylar = {'alt_kategori': 'TIBBI_BESLENME', 'sut_maddesi': '4.2.4'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Tıbbi beslenme ürünü RAPORSUZ yazılmış! Uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='SUT 4.2.4 - İlgili branş uzman raporu gerekli',
                sut_kurali='SUT 4.2.4 — Tıbbi beslenme ürünleri uzman raporu ile verilir'
            )
        uyarilar = ['Endikasyon ve kalori ihtiyacı raporda belirtilmeli',
                    'Rapor süresi: 3-6 ay (endikasyona göre)']
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Tıbbi beslenme ürünü — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.4 — Tıbbi beslenme ürünleri uzman raporu ile verilir'
        )

    # ── 22. İnsülin Analogları (SUT 4.2.38.C) ──
    insulin_etkin = ['INSULIN GLARJIN', 'INSULIN DETEMIR', 'INSULIN DEGLUDEK',
                     'INSULIN ASPART', 'INSULIN LISPRO', 'INSULIN GLULISIN',
                     'INSULIN NPH', 'INSULIN REGULAR']
    insulin_ilac = ['LANTUS', 'TOUJEO', 'LEVEMIR', 'TRESIBA', 'NOVORAPID',
                    'HUMALOG', 'APIDRA', 'NOVOMIX', 'HUMULIN', 'FIASP',
                    'INSULATARD']
    insulin_mi = any(_turkce_ara(etkin_madde, e) for e in insulin_etkin) or \
                 any(i in ilac_adi for i in insulin_ilac)

    if insulin_mi:
        detaylar = {'alt_kategori': 'INSULIN', 'sut_maddesi': '4.2.38'}
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.KONTROL_EDILEMEDI,
                'İnsülin — rapor kodu bulunamadı',
                detaylar=detaylar,
                uyari='İnsülin endokrinoloji/dahiliye uzman raporu ile yazılır | HbA1c kontrol edilmeli',
                sut_kurali='SUT 4.2.38 — İnsülin tedavisi uzman raporu ile başlatılır'
            )
        uyarilar = ['Endokrinoloji/Dahiliye uzman raporu olmalı',
                    'HbA1c düzeyi raporda belirtilmeli',
                    'İnsülin türü ve doz şeması kontrol edilmeli']
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"İnsülin — rapor kodu {rapor_kodu}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT 4.2.38 — İnsülin tedavisi uzman raporu ile yürütülür'
        )

    # ── 23. Kas Gevşeticiler (Raporsuz yazılabilir) ──
    kas_etkin = ['TIZANIDIN', 'BAKLOFEN', 'SIKLOBENZAPRIN', 'DANTROLEN',
                 'METAMIZOL', 'KLORZOKSAZON', 'METOKARBAMOL', 'PRIDINOL',
                 'TIYOKOLSIKOZID', 'TIYOKOLSIKOSID', 'THIOCOLCHICOSIDE']
    kas_ilac = ['SIRDALUD', 'LIORESAL', 'MUSCORIL', 'DANTRIUM',
                'NOVALGIN', 'DEVALJIN', 'MYOGESIC', 'THIOCOLCHICOSIDE']
    kas_mi = any(_turkce_ara(etkin_madde, e) for e in kas_etkin) or \
             any(i in ilac_adi for i in kas_ilac)

    if kas_mi:
        uyarilar = ['Kas gevşetici — raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        baklofen_mi = _turkce_ara(etkin_madde, 'baklofen') or 'LIORESAL' in ilac_adi
        if baklofen_mi:
            uyarilar.append('Baklofen: Spastisite tedavisinde nöroloji raporu gerekebilir (yüksek doz)')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'Kas gevşetici — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'KAS_GEVSETIC'},
            uyari=' | '.join(uyarilar),
            sut_kurali='Kas gevşeticiler raporsuz reçete edilebilir (baklofen yüksek dozda rapor gerekebilir)'
        )

    # ── 24. Antidiyareik / GİS İlaçları (Raporsuz yazılabilir) ──
    gis_otc_etkin = ['LOPERAMID', 'DIOSMEKTIT', 'BIZMUT', 'SUKRALFAT',
                     'SIMETIDIN', 'FAMOTIDIN', 'RANITIDIN', 'MEBEVERIN',
                     'TRIMEBUTIN', 'ALVERIN', 'DOMPERIDON', 'METOKLOPRAMID',
                     'ONDANSETRON']
    gis_otc_ilac = ['IMODIUM', 'SMECTA', 'PEPTO', 'ULCURAN', 'FAMODIN',
                    'DUSPATALIN', 'DEBRIDAT', 'MOTILIUM', 'METPAMID',
                    'ZOFRAN', 'ONDAREN']
    gis_otc_mi = any(_turkce_ara(etkin_madde, e) for e in gis_otc_etkin) or \
                 any(i in ilac_adi for i in gis_otc_ilac)

    if gis_otc_mi:
        uyarilar = ['GİS ilacı — raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'GİS ilacı — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'GIS_GENEL'},
            uyari=' | '.join(uyarilar),
            sut_kurali='GİS ilaçları raporsuz reçete edilebilir'
        )

    # ── 25. Antihipertansifler - Kalsiyum Kanal Blokerleri / BB (Raporsuz) ──
    antihipertansif_etkin = ['AMLODIPIN', 'NIFEDIPIN', 'LERKANIDIPIN', 'DILTIAZEM',
                             'VERAPAMIL', 'METOPROLOL', 'BISOPROLOL', 'NEBIVOLOL',
                             'KARVEDILOL', 'ATENOLOL', 'PROPRANOLOL', 'ENALAPRIL',
                             'RAMIPRIL', 'PERINDOPRIL', 'LISINOPRIL', 'KAPTOPRIL',
                             'BENAZEPRIL', 'FOSINOPRIL', 'KINAPRIL',
                             'SPIRONOLAKTON', 'FUROSEMID', 'HIDROKLOROTIYAZID',
                             'INDAPAMID', 'TORASEMID', 'AMILORID']
    antihipertansif_ilac = ['NORVASC', 'ADALAT', 'LERCANIL', 'DILTIAZEM', 'ISOPTIN',
                            'BELOC', 'CONCOR', 'NEBILET', 'DILATREND', 'TENORMIN',
                            'DIDERAL', 'RENITEC', 'DELIX', 'COVERSYL', 'ZESTRIL',
                            'KAPTORIL', 'ALDACTONE', 'LASIX', 'FURORESE']
    antihipertansif_mi = any(_turkce_ara(etkin_madde, e) for e in antihipertansif_etkin) or \
                         any(i in ilac_adi for i in antihipertansif_ilac)

    if antihipertansif_mi:
        uyarilar = ['Antihipertansif (mono) — raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'Antihipertansif (mono) — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'ANTIHIPERTANSIF_MONO'},
            uyari=' | '.join(uyarilar),
            sut_kurali='Mono antihipertansif ilaçlar raporsuz reçete edilebilir'
        )

    # ── 26. Antibiyotikler (EK-4/E — Genel) ──
    antibiyotik_etkin = ['AMOKSISILIN', 'AMOKSISILIN/KLAVULANAT', 'AMPISILIN',
                         'SEFALEKSIN', 'SEFUROKSIM', 'SEFTRIAKSON', 'SEFDINIR',
                         'SEFPODOKSIM', 'SEFIKSIM', 'AZITROMISIN', 'KLARITROMISIN',
                         'ERITROMISIN', 'DOKSISIKLIN', 'TETRASIKLIN',
                         'TRIMETOPRIM', 'SULFAMETOKSAZOL', 'NITROFURANTOIN',
                         'FOSFOMISIN', 'METRONIDAZOL', 'ORNIDAZOL', 'SEKNIDAZOL',
                         'GENTAMISIN', 'AMIKASIN', 'TOBRAMISIN',
                         'LINEZOLID', 'DAPTOMISIN', 'TEIKOPLANIN', 'VANKOMISIN',
                         'MEROPENEM', 'IMIPENEM', 'ERTAPENEM', 'DORIPENEM',
                         'PIPERASILIN', 'KOLISTIN', 'TIGESIKLIN']
    antibiyotik_ilac = ['AUGMENTIN', 'AMOKLAVIN', 'KLAMOKS', 'CROXILEX',
                        'DUOCID', 'CEFZIL', 'ZINNAT', 'CEFAKS',
                        'CEFTRIAXONE', 'CEDAX', 'SUPRAX',
                        'AZITRO', 'ZITROMAX', 'AZOMAX',
                        'MACROL', 'KLACID', 'KLARITROMISIN',
                        'DOKSICILIN', 'TETRADOX',
                        'BACTRIM', 'FURADANTIN',
                        'MONUROL', 'FLAGYL', 'ORNIDAZOL',
                        'LINEZOLID', 'CUBICIN', 'TARGOCID', 'VANKOMISIN',
                        'MERONEM', 'TIENAM', 'INVANZ',
                        'TAZOCIN', 'KOLISTIN']
    antibiyotik_mi = any(_turkce_ara(etkin_madde, e) for e in antibiyotik_etkin) or \
                     any(i in ilac_adi for i in antibiyotik_ilac)

    if antibiyotik_mi:
        detaylar = {'alt_kategori': 'ANTIBIYOTIK_GENEL'}
        uyarilar = []
        # Parenteral/yatan hasta antibiyotikleri — rapor gerektirebilir
        kst_etkin = ['LINEZOLID', 'DAPTOMISIN', 'TEIKOPLANIN', 'VANKOMISIN',
                     'MEROPENEM', 'IMIPENEM', 'ERTAPENEM', 'DORIPENEM',
                     'PIPERASILIN', 'KOLISTIN', 'TIGESIKLIN']
        kst_ilac = ['LINEZOLID', 'CUBICIN', 'TARGOCID', 'VANKOMISIN',
                    'MERONEM', 'TIENAM', 'INVANZ', 'TAZOCIN', 'KOLISTIN']
        kisitli_mi = any(_turkce_ara(etkin_madde, e) for e in kst_etkin) or \
                     any(i in ilac_adi for i in kst_ilac)

        if kisitli_mi:
            detaylar['alt_grup'] = 'KISITLI_ANTIBIYOTIK'
            if not rapor_kodu:
                uyarilar.append('Kısıtlı antibiyotik — Enfeksiyon hastalıkları uzman raporu gerekebilir')
                return KontrolRaporu(
                    KontrolSonucu.KONTROL_EDILEMEDI,
                    'Kısıtlı antibiyotik — rapor kodu bulunamadı',
                    detaylar=detaylar,
                    uyari=' | '.join(uyarilar) if uyarilar else 'Enfeksiyon hastalıkları konsültasyonu gerekli',
                    sut_kurali='SUT EK-4/E — Kısıtlı antibiyotikler uzman raporu/konsültasyonu ile verilir'
                )
            uyarilar.append('Kısıtlı antibiyotik — kültür sonucu ve endikasyon kontrol edilmeli')
        else:
            uyarilar.append('Antibiyotik — raporsuz yazılabilir (EK-4/E listesi)')

        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"Antibiyotik — {'rapor kodu ' + rapor_kodu if rapor_kodu else 'raporsuz yazılabilir'}",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali='SUT EK-4/E — Antibiyotikler endikasyona göre raporsuz veya raporlu yazılır'
        )

    # ── 27. Tiroid İlaçları (Raporsuz yazılabilir) ──
    tiroid_etkin = ['LEVOTIROKSIN', 'LIYOTIRONIN', 'PROPILTIYOURASIL',
                    'METIMAZOL', 'TIAMAZOL', 'KARBIMAZOL']
    tiroid_ilac = ['EUTHYROX', 'LEVOTIRON', 'TIROMEL', 'PROPYCIL', 'THYROZOL',
                   'UNIMAZOL']
    tiroid_mi = any(_turkce_ara(etkin_madde, e) for e in tiroid_etkin) or \
                any(i in ilac_adi for i in tiroid_ilac)

    if tiroid_mi:
        uyarilar = ['Tiroid ilacı — raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        uyarilar.append('TSH düzeyi takibi önerilir')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'Tiroid ilacı — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'TIROID'},
            uyari=' | '.join(uyarilar),
            sut_kurali='Tiroid ilaçları raporsuz reçete edilebilir'
        )

    # ── 28. Demir / Vitamin / Mineral Preparatları (Raporsuz) ──
    vitamin_etkin = ['DEMIR', 'FERRÖZ', 'DEMIR SÜLFAT', 'DEMIR FUMARAT',
                     'KALSIYUM', 'KOLEKALSITEROL', 'ERGOKALSIFEROL',
                     'FOLIK ASIT', 'SIYANOKOBALAMIN', 'B12',
                     'ASKORBIK ASIT', 'TOKOFEROL', 'PIRIDOKSIN']
    vitamin_ilac = ['FERROSANOL', 'MALTOFER', 'FERRO', 'VENOFER',
                    'CALCIMAGON', 'CALTRATE', 'DEVIT',
                    'FOLBIOL', 'DODEX', 'BEMIKS',
                    'CEVIKAP', 'EVICAP']
    vitamin_mi = any(_turkce_ara(etkin_madde, e) for e in vitamin_etkin) or \
                 any(i in ilac_adi for i in vitamin_ilac)

    if vitamin_mi:
        uyarilar = ['Vitamin/mineral — raporsuz yazılabilir']
        if rapor_kodu:
            uyarilar.append(f'Rapor kodu mevcut: {rapor_kodu}')
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            'Vitamin/mineral preparatı — raporsuz yazılabilir',
            detaylar={'alt_kategori': 'VITAMIN_MINERAL'},
            uyari=' | '.join(uyarilar),
            sut_kurali='Vitamin ve mineral preparatları raporsuz reçete edilebilir'
        )

    # ── 29. Genel Rapor Kodu Kontrolleri (alt-kategoriye uymayan) ──
    if rapor_kodu:
        detaylar = {'rapor_kodu': rapor_kodu, 'alt_kategori': 'GENEL'}

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

    # ── 30. İlaç adından tanıma (etkin madde güvenilmez olduğunda) ──
    if ilac_adi:
        ilac_adi_bilinen = {
            'ETOL': ('Etodolak (NSAİD)', 'NSAID_ANTIINFLAMATUAR', True),
            'MAJEZIK': ('Flurbiprofen (NSAİD)', 'NSAID_ANTIINFLAMATUAR', True),
            'CATAFLAM': ('Diklofenak (NSAİD)', 'NSAID_ANTIINFLAMATUAR', True),
            'MINOSET': ('Parasetamol', 'ANALJEZIK', True),
            'PAROL': ('Parasetamol', 'ANALJEZIK', True),
            'VERMIDON': ('Parasetamol', 'ANALJEZIK', True),
            'TYLOL': ('Parasetamol', 'ANALJEZIK', True),
            'NOVALGIN': ('Metamizol', 'ANALJEZIK', True),
            'GRIPIN': ('Parasetamol kombine', 'ANALJEZIK', True),
        }
        for anahtar, (aciklama, kategori, raporsuz) in ilac_adi_bilinen.items():
            if anahtar in ilac_adi:
                sonuc = KontrolSonucu.UYGUN if raporsuz else KontrolSonucu.KONTROL_EDILEMEDI
                mesaj = f"{aciklama} — {'raporsuz yazılabilir' if raporsuz else 'rapor durumu kontrol edilmeli'}"
                return KontrolRaporu(
                    sonuc, mesaj,
                    detaylar={'alt_kategori': kategori, 'ilac_adi_eslesmesi': anahtar},
                    uyari='İlaç adından tanındı (etkin madde bilgisi güvenilmez)'
                )

    # ── Rapor kodu yok — bilinmeyen ilaç ──
    return KontrolRaporu(
        KontrolSonucu.KONTROL_EDILEMEDI,
        'Rapor kodu bulunamadı ve ilaç alt-kategorilerde eşleşmedi — manuel kontrol gerekli',
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
    """Antiviral ilaçlar (Hepatit B/C, HIV) - detaylı kontrol."""
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    return _antiviral_hepatit_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin)


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

    Alt gruplar:
    1.  NSAİD'ler (Etodolak, İbuprofen, Diklofenak, Naproksen vb.)
    2.  Parasetamol / Analjezikler
    3.  Makrolid Antibiyotikler (Klaritromisin, Azitromisin)
    4.  Penisilin grubu Antibiyotikler (Amoksisilin, Ampisilin)
    5.  Sefalosporin Antibiyotikler (Sefuroksim, Sefaleksin)
    6.  Antihistaminikler (Desloratadin, Setirizin, Loratadin)
    7.  Dekonjestanlar / Soğuk algınlığı kombinasyonları
    8.  Topikal antifungal/antiseptik
    9.  MAO-B İnhibitörleri (Parkinson)
    10. PPI - Proton Pompa İnhibitörleri (Omeprazol, Lansoprazol)
    11. H2 Reseptör Antagonistleri (Ranitidin, Famotidin)
    12. Antidiyareikler (Loperamid)
    13. Laksatifler (Laktuloz, Bisakodil)
    14. Antispazmodikler (Hyosin, Trimebutin)
    15. Kas gevşeticiler (Tizanidin, Miyorelaksanlar)
    16. Topikal NSAİD / Analjezik (jel/krem formları)
    17. Topikal kortikosteroidler (Düşük/orta potens)
    18. Oftalmik preparatlar (Suni gözyaşı, antiinflamatuar damlalar)
    19. Otik preparatlar (Kulak damlaları)
    20. Nazal kortikosteroidler (Mometazon, Flutikazon nazal)
    21. Mukolitikler / Ekspektoranlar (Asetilsistein, Bromheksin)
    22. Antitüsifler (Dekstrometorfan)
    23. Vitamin / Mineral preparatları (Demir, B12, D vit, Folik asit)
    24. Oral antifungaller (Flukonazol tek doz)
    25. Topikal antibiyotikler (Mupirosin, Fusidik asit)
    26. Üriner antiseptikler (Fosfomisin, Nitrofurantoin)
    27. Antiemetikler (Metoklopramid, Ondansetron)
    28. Beta-laktamaz inhibitörlü penisilinler (Amoksisilin-Klavulanat)
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

    # ── Alt kategori tespit listeleri ──

    # NSAİD'ler
    nsaid_maddeler = [
        'IBUPROFEN', 'NAPROKSEN', 'DIKLOFENAK', 'MELOKSIKAM', 'PIROKSIKAM',
        'INDOMETAZIN', 'KETOPROFEN', 'FLURBIPROFEN', 'DEKSKETOPROFEN',
        'ETODOLAK', 'LORNOKSIKAM', 'TENOKSIKAM', 'ASETILSALISILIK',
        'NIMESULID', 'SELEKOKSIB', 'ETORIKOKSIB', 'ASEKLOFENAK',
        'FENOPROFEN', 'TOLMETIN', 'SULINDAK', 'OKSAPROZIN',
    ]
    nsaid_maks_doz = {
        'IBUPROFEN': (2400, '400-600 mg 3x1'),
        'DIKLOFENAK': (150, '50 mg 3x1 veya 75 mg 2x1'),
        'NAPROKSEN': (1100, '550 mg 2x1'),
        'MELOKSIKAM': (15, '7.5-15 mg 1x1'),
        'PIROKSIKAM': (20, '20 mg 1x1'),
        'KETOPROFEN': (300, '100 mg 3x1'),
        'FLURBIPROFEN': (300, '100 mg 3x1'),
        'DEKSKETOPROFEN': (75, '25 mg 3x1'),
        'ETODOLAK': (1200, '300-600 mg 2x1'),
        'LORNOKSIKAM': (16, '8 mg 2x1'),
        'TENOKSIKAM': (20, '20 mg 1x1'),
        'INDOMETAZIN': (200, '25-50 mg 3x1'),
        'NIMESULID': (200, '100 mg 2x1'),
        'SELEKOKSIB': (400, '200 mg 2x1'),
        'ETORIKOKSIB': (120, '60-120 mg 1x1'),
        'ASEKLOFENAK': (200, '100 mg 2x1'),
    }
    is_nsaid = any(m in etkin_madde for m in nsaid_maddeler)

    # Parasetamol / Basit analjezikler
    parasetamol_maddeler = ['PARASETAMOL', 'ASETAMINOFEN']
    parasetamol_ticari = ['PAROL', 'TYLOL', 'MINOSET', 'VERMIDON', 'CALPOL',
                          'TAMOL', 'NUROFEN COLD']
    is_parasetamol = (any(m in etkin_madde for m in parasetamol_maddeler) or
                      any(t in ilac_adi for t in parasetamol_ticari))

    # Makrolid antibiyotikler
    makrolid_maddeler = ['KLARITROMISIN', 'AZITROMISIN', 'ERITROMISIN', 'ROKSITROMISIN']
    makrolid_ticari = ['MACROL', 'KLACID', 'DEZEST', 'AZITRO', 'KLAMOKS',
                       'KLAROMIN', 'AZRO', 'ZITROMAX']
    is_makrolid = (any(m in etkin_madde for m in makrolid_maddeler) or
                   any(t in ilac_adi for t in makrolid_ticari))

    # Penisilin grubu
    penisilin_maddeler = ['AMOKSISILIN', 'AMPISILIN', 'FENOKSIMETILPENISILIN',
                          'AMOKSISILIN KLAVULANAT', 'SULTAMISILIN',
                          'AMOKSISILIN/KLAVULANIK']
    penisilin_ticari = ['AUGMENTIN', 'KLAMOKS', 'AMOKLAVIN', 'LARGOPEN',
                        'DUOCID', 'ALFOXIL', 'OSPAMOX', 'BIOMENT',
                        'CROXILEX', 'KLAVUNAT']
    is_penisilin = (any(m in etkin_madde for m in penisilin_maddeler) or
                    any(t in ilac_adi for t in penisilin_ticari))

    # Sefalosporin antibiyotikler
    sefalo_maddeler = ['SEFUROKSIM', 'SEFALEKSIN', 'SEFAKLOR', 'SEFADROKSIL',
                       'SEFIKSIM', 'SEFPROZIL', 'SEFDINIR', 'SEFPODOKSIM',
                       'SEFDITORENPIVOKSIL', 'LORAKARBEF']
    sefalo_ticari = ['CEFAKS', 'SEFAKTIL', 'ORACEFTIN', 'ZINNAT', 'CEFIXIME',
                     'SUPRAX', 'SEFDIN', 'SPECTRACEF']
    is_sefalo = (any(m in etkin_madde for m in sefalo_maddeler) or
                 any(t in ilac_adi for t in sefalo_ticari))

    # Antihistaminikler
    antihist_maddeler = ['DESLORATADIN', 'KLORFENIRAMIN', 'SETIRIZIN', 'LORATADIN',
                         'FEKSOFENADRIN', 'LEVOSETRIZIN', 'EBASTIN', 'RUPATADIN',
                         'BILASTIN', 'DIFENHIDRAMIN', 'HIDROKSIZIN', 'PROMETAZIN',
                         'MEKLIZIN', 'KETOTIFEN']
    antihist_ticari = ['AERIUS', 'CLARITINE', 'ZYRTEC', 'XYZAL', 'TELFAST',
                       'ATARAX', 'FENISTIL', 'ZADITEN']
    is_antihistaminik = (any(m in etkin_madde for m in antihist_maddeler) or
                         any(t in ilac_adi for t in antihist_ticari))

    # Dekonjestanlar / Soğuk algınlığı
    dekonjestan_maddeler = ['FENILEFRIN', 'PSEUDOEFEDRIN', 'OKSIMETAZOLIN',
                            'KSILOMETAZOLIN']
    dekonjestan_ticari = ['IBUCOLD', 'A-FERIN', 'THERAFLU', 'TYLOLHOT', 'NUROFEN COLD',
                          'OTRIVIN', 'ILIADIN', 'SUDAFED', 'ACTIFED']
    is_dekonjestan = (any(m in etkin_madde for m in dekonjestan_maddeler) or
                      any(t in ilac_adi for t in dekonjestan_ticari))

    # Topikal antifungal/antiseptik
    topikal_maddeler = ['OKSIKONAZOL', 'BENZIDAMIN', 'MIKONAZOL', 'KLOTRIMAZOL',
                        'TERBINAFIN', 'KETOKONAZOL', 'NISTATIN', 'EKONAZOL',
                        'SERTAKONAZOL', 'SIKLOPIROKS']
    topikal_ticari = ['TRAVAZOL', 'OCERAL', 'ANDOREX', 'TANTUM', 'LAMISIL',
                      'FUNGICIDE', 'CANESTEN', 'CANDIO', 'MYCOSTATIN']
    is_topikal = (any(m in etkin_madde for m in topikal_maddeler) or
                  any(t in ilac_adi for t in topikal_ticari))

    # MAO-B İnhibitörleri (Parkinson)
    maob_maddeler = ['SELEGILIN', 'RASAGILIN', 'SAFINAMID']
    maob_ticari = ['AZILECT', 'XADAGO']
    is_maob = (any(m in etkin_madde for m in maob_maddeler) or
               any(t in ilac_adi for t in maob_ticari))

    # PPI - Proton Pompa İnhibitörleri
    ppi_maddeler = ['OMEPRAZOL', 'LANSOPRAZOL', 'PANTOPRAZOL', 'RABEPRAZOL',
                    'ESOMEPRAZOL', 'DEKSLANSOPRAZOL']
    ppi_ticari = ['NEXIUM', 'LOSEC', 'LANSOR', 'PANTPAS', 'CONTROLOC',
                  'PARIET', 'ZURCAL', 'OGASTRO']
    is_ppi = (any(m in etkin_madde for m in ppi_maddeler) or
              any(t in ilac_adi for t in ppi_ticari))

    # H2 Reseptör Antagonistleri
    h2ra_maddeler = ['RANITIDIN', 'FAMOTIDIN', 'NIZATIDIN']
    h2ra_ticari = ['ULCURAN', 'FAMODIN', 'PEPCID', 'RANITAB']
    is_h2ra = (any(m in etkin_madde for m in h2ra_maddeler) or
               any(t in ilac_adi for t in h2ra_ticari))

    # Antidiyareikler
    antidiyareik_maddeler = ['LOPERAMID', 'DIOSMEKTIT', 'SACCHAROMYCES']
    antidiyareik_ticari = ['IMODIUM', 'LOMOTIL', 'SMECTA', 'REFLOR']
    is_antidiyareik = (any(m in etkin_madde for m in antidiyareik_maddeler) or
                       any(t in ilac_adi for t in antidiyareik_ticari))

    # Laksatifler
    laksatif_maddeler = ['LAKTULOZ', 'BISAKODIL', 'SENNA', 'MAKROGOL',
                         'GLISERIN', 'PSYLLIUM', 'DOKUZAT']
    laksatif_ticari = ['DUPHALAC', 'BEKUNIS', 'LAXOBERAL', 'MOVICOL']
    is_laksatif = (any(m in etkin_madde for m in laksatif_maddeler) or
                   any(t in ilac_adi for t in laksatif_ticari))

    # Antispazmodikler
    antispazm_maddeler = ['HYOSIN', 'TRIMEBUTIN', 'MEBEVERIN', 'ALVERIN',
                          'OTILONYUM', 'PINAVERIUM', 'DROTAVERIN']
    antispazm_ticari = ['BUSCOPAN', 'DEBRIDAT', 'DUSPATALIN', 'SPASMOMEN',
                        'NOSPA', 'SPASFON']
    is_antispazm = (any(m in etkin_madde for m in antispazm_maddeler) or
                    any(t in ilac_adi for t in antispazm_ticari))

    # Kas gevşeticiler
    kas_gevsetici_maddeler = ['TIZANIDIN', 'BAKLOFEN', 'DANTROLEN',
                              'SIKLOBENZAPRIN', 'TOLPERISON', 'PRIDINOL',
                              'METOKARBAMOL', 'KLORZOKSAZON', 'EPERISON']
    kas_gevsetici_ticari = ['SIRDALUD', 'LIORESAL', 'MUSCORIL', 'MYOGESIC',
                            'MYDOCALM']
    is_kas_gevsetici = (any(m in etkin_madde for m in kas_gevsetici_maddeler) or
                        any(t in ilac_adi for t in kas_gevsetici_ticari))

    # Topikal NSAİD / Analjezik (jel/krem)
    topikal_nsaid_maddeler = ['DIKLOFENAK', 'PIROKSIKAM', 'KETOPROFEN',
                              'IBUPROFEN', 'NIMESULID', 'INDOMETAZIN']
    topikal_nsaid_formlar = ['JEL', 'KREM', 'POMAD', 'MERHEM']
    is_topikal_nsaid = (any(m in etkin_madde for m in topikal_nsaid_maddeler) and
                        any(f in ilac_adi for f in topikal_nsaid_formlar))

    # Topikal kortikosteroidler (düşük/orta potens)
    topikal_kortiko_maddeler = ['HIDROKORTIZON', 'BETAMETAZON', 'MOMETAZON',
                                'TRIAMSINOLON', 'PREDNIZOLON', 'FLUOSINOLON',
                                'DESONID', 'KLOBETAZOL', 'FLUTIKAZON',
                                'METILPREDNIZOLON ASEPONAT']
    topikal_kortiko_ticari = ['ADVANTAN', 'DERMOVATE', 'ELOCON', 'FUCICORT',
                              'HIPOKORT', 'BETNOVATE', 'LOCOID']
    topikal_kortiko_formlar = ['KREM', 'POMAD', 'MERHEM', 'LOSYON']
    is_topikal_kortiko = ((any(m in etkin_madde for m in topikal_kortiko_maddeler) and
                           any(f in ilac_adi for f in topikal_kortiko_formlar)) or
                          any(t in ilac_adi for t in topikal_kortiko_ticari))

    # Oftalmik preparatlar (göz damlaları)
    oftalmik_maddeler = ['KARBOKSIMETILSELULOZ', 'HIYALURONAT', 'SODYUM HIYALURONAT',
                         'POLIVINIL ALKOL', 'KARBOMER', 'HIPROMELLOZ']
    oftalmik_ticari = ['REFRESH', 'SYSTANE', 'TEARS NATURALE', 'VISMED',
                       'ARTELAC', 'OPTIVE', 'THEALOZ']
    is_oftalmik = (any(m in etkin_madde for m in oftalmik_maddeler) or
                   any(t in ilac_adi for t in oftalmik_ticari))

    # Otik preparatlar (kulak damlaları)
    otik_maddeler = ['SIPROFLOKSASIN DEKSAMETAZON', 'NEOMISIN',
                     'POLIMIKSIN', 'KLORAMFENIKOL']
    otik_ticari = ['CIPRODEX', 'OTORIN', 'OTOMISIN', 'OTOCOMB']
    otik_formlar = ['KULAK', 'OTIK']
    is_otik = (any(m in etkin_madde for m in otik_maddeler) or
               any(t in ilac_adi for t in otik_ticari) or
               any(f in ilac_adi for f in otik_formlar))

    # Nazal kortikosteroidler
    nazal_kortiko_maddeler = ['MOMETAZON', 'FLUTIKAZON', 'BUDESONID',
                              'BEKLOMETAZON', 'TRIAMSINOLON']
    nazal_formlar = ['NAZAL', 'BURUN']
    is_nazal_kortiko = (any(m in etkin_madde for m in nazal_kortiko_maddeler) and
                        any(f in ilac_adi for f in nazal_formlar))

    # Mukolitikler / Ekspektoranlar
    mukolitik_maddeler = ['ASETILSISTEIN', 'BROMHEKSIN', 'AMBROKSOL',
                          'KARBOSISTEIN', 'ERDOSTEIN', 'GUAIFENESIN']
    mukolitik_ticari = ['ASIST', 'MUCOSOLVAN', 'TUSSIVIN', 'ERDOSTIN',
                        'FLUIMUCIL', 'SOLMUX']
    is_mukolitik = (any(m in etkin_madde for m in mukolitik_maddeler) or
                    any(t in ilac_adi for t in mukolitik_ticari))

    # Antitüsifler
    antitusif_maddeler = ['DEKSTROMETORFAN', 'BUTAMIRAT', 'KODEIN',
                          'LEVODROPROPIZIN', 'BENZONATAT']
    antitusif_ticari = ['TUSSEYL', 'SINECOD', 'LEVOPRONT', 'TUSUBEN']
    is_antitusif = (any(m in etkin_madde for m in antitusif_maddeler) or
                    any(t in ilac_adi for t in antitusif_ticari))

    # Vitamin / Mineral preparatları
    vitamin_maddeler = ['DEMIR', 'FEROZ', 'DEMIR SULFAT', 'DEMIR FUMARAT',
                        'SIYANOKOBALAMIN', 'B12', 'KOLEKALSIFEROL',
                        'ERGOKALSIFEROL', 'FOLIK ASIT', 'FOLAT',
                        'ASKORBIK ASIT', 'C VITAMINI', 'TIAMIN',
                        'PIRIDOKSIN', 'KALSIYUM', 'MAGNEZYUM', 'CINKO']
    vitamin_ticari = ['FERRO SANOL', 'FERROSANOL', 'MALTOFER', 'DEVIT',
                      'FOLIXA', 'CEVIT', 'BEMIKS', 'BEPANTHOL',
                      'CALCIMAGON', 'CALTRATE', 'MAGNORM', 'ZINCOMAX']
    is_vitamin = (any(m in etkin_madde for m in vitamin_maddeler) or
                  any(t in ilac_adi for t in vitamin_ticari))

    # Oral antifungaller (kısa süreli)
    oral_antifungal_maddeler = ['FLUKONAZOL', 'ITRAKONAZOL']
    oral_antifungal_ticari = ['TRIFLUCAN', 'FLUZOL', 'FUNIT', 'SPORAX']
    is_oral_antifungal = (any(m in etkin_madde for m in oral_antifungal_maddeler) or
                          any(t in ilac_adi for t in oral_antifungal_ticari))

    # Topikal antibiyotikler
    topikal_ab_maddeler = ['MUPIROSIN', 'FUSIDIK ASIT', 'RETAPAMULIN',
                           'BASITRASIN', 'GENTAMISIN']
    topikal_ab_ticari = ['BACTROBAN', 'FUCIDIN', 'FUCICORT', 'GENTAMICIN']
    topikal_ab_formlar = ['KREM', 'POMAD', 'MERHEM']
    is_topikal_ab = ((any(m in etkin_madde for m in topikal_ab_maddeler) or
                      any(t in ilac_adi for t in topikal_ab_ticari)) and
                     any(f in ilac_adi for f in topikal_ab_formlar))

    # Üriner antiseptikler
    uriner_maddeler = ['FOSFOMISIN', 'NITROFURANTOIN', 'TRIMETOPRIM',
                       'TRIMETOPRIM SULFAMETOKSAZOL']
    uriner_ticari = ['MONUROL', 'FURADANTIN', 'BACTRIM', 'TRIMOKS']
    is_uriner = (any(m in etkin_madde for m in uriner_maddeler) or
                 any(t in ilac_adi for t in uriner_ticari))

    # Antiemetikler
    antiemetik_maddeler = ['METOKLOPRAMID', 'DOMPERIDON', 'ONDANSETRON',
                           'GRANISETRON', 'DIMENHIDRINAT', 'TROPISETRON']
    antiemetik_ticari = ['METPAMID', 'MOTILIUM', 'ZOFRAN', 'DRAMAMINE',
                         'EMEND', 'VOMETA']
    is_antiemetik = (any(m in etkin_madde for m in antiemetik_maddeler) or
                     any(t in ilac_adi for t in antiemetik_ticari))

    # ══════════════════════════════════════════════════════════════
    # 1. NSAİD'ler (İbuprofen, Etodolak, Diklofenak, Naproksen vb.)
    # SUT: Raporsuz, tüm hekimler yazabilir (EK-4/E)
    # Doz: Etkin maddeye göre maks günlük doz kontrolü
    # Süre: Akut kullanım 7-14 gün, kronik için GİS koruma gerekli
    # Kombinasyon: İki NSAİD aynı reçetede UYGUN DEĞİL
    # COX-2 selektif (Selekoksib, Etorikoksib): KV risk uyarısı
    # ══════════════════════════════════════════════════════════════
    if is_nsaid and not is_topikal_nsaid:
        detaylar['alt_kategori'] = 'NSAID'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir (EK-4/E)"]

        for madde, (maks, dozaj) in nsaid_maks_doz.items():
            if madde in etkin_madde:
                uyarilar.append(f"{madde} maks doz: {maks} mg/gün ({dozaj})")
                break

        cox2_selektif = ['SELEKOKSIB', 'ETORIKOKSIB']
        if any(m in etkin_madde for m in cox2_selektif):
            uyarilar.append("COX-2 selektif: Kardiyovasküler risk artışı, en düşük dozda en kısa süre")

        uzatilmis_salim = ['SR', 'RETARD', 'XR', 'UZATILMIS']
        if any(u in ilac_adi for u in uzatilmis_salim):
            uyarilar.append("Uzatılmış salımlı form: Günde 1-2 kez, bölünmemeli/çiğnenmemeli")

        uyarilar.append("KOMBİNASYON: Aynı reçetede birden fazla NSAİD UYGUN DEĞİL")
        uyarilar.append("Uzun süreli kullanımda GİS koruyucu (PPI) gerekebilir")
        uyarilar.append("Antikoagülan (Varfarin/YOAK) ile birlikte kanama riski artar")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "NSAİD - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 2. Parasetamol / Basit Analjezikler
    # SUT: Raporsuz, tüm hekimler yazabilir
    # Doz: Maks 4000 mg/gün (hepatotoksisite riski)
    # Kombinasyon: Birden fazla parasetamol içeren ilaç kontrolü
    # ══════════════════════════════════════════════════════════════
    if is_parasetamol:
        detaylar['alt_kategori'] = 'PARASETAMOL'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Parasetamol maks doz: 4000 mg/gün (genellikle 500 mg 3-4x1)",
            "KOMBİNASYON: Soğuk algınlığı ilaçlarında gizli parasetamol olabilir, toplam doz kontrol edilmeli",
            "Hepatotoksisite: KC hastalarında doz azaltılmalı (maks 2000 mg/gün)",
        ]
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Parasetamol - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 3. Makrolid Antibiyotikler (EK-4/E)
    # SUT: Ayaktan tedavide raporsuz, kısıtlama yok
    # Süre: Klaritromisin 7-14 gün, Azitromisin 3-5 gün
    # Kombinasyon: Statin etkileşimi, QT uzaması
    # ══════════════════════════════════════════════════════════════
    if is_makrolid:
        detaylar['alt_kategori'] = 'MAKROLID_ANTIBIYOTIK'
        uyarilar = ["EK-4/E: Ayaktan tedavide tüm hekimler raporsuz yazabilir"]

        if 'KLARITROMISIN' in etkin_madde:
            uyarilar.append("Klaritromisin: 7-14 gün, maks 14 gün")
            uyarilar.append("Statin etkileşimi: Rabdomiyoliz riski (özellikle simvastatin ile birlikte YASAK)")
            uyarilar.append("Kolşisin ile birlikte KESİNLİKLE VERİLMEMELİ")
        elif 'AZITROMISIN' in etkin_madde:
            uyarilar.append("Azitromisin: 3-5 gün tedavi (500 mg 1x1 veya 500+250+250)")
            uyarilar.append("QT uzaması riski: Kardiyak hastada dikkat")
        elif 'ERITROMISIN' in etkin_madde:
            uyarilar.append("Eritromisin: 7-14 gün, GİS yan etkisi sık")
        elif 'ROKSITROMISIN' in etkin_madde:
            uyarilar.append("Roksitromisin: 5-10 gün, 150 mg 2x1")

        uyarilar.append("Aynı reçetede başka antibiyotik kontrolü yapılmalı")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Makrolid antibiyotik - ayaktan tedavide raporsuz verilebilir (EK-4/E)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 4. Penisilin Grubu Antibiyotikler (EK-4/E)
    # SUT: Ayaktan tedavide raporsuz, tüm hekimler yazabilir
    # Amoksisilin-Klavulanat: En sık reçetelenen antibiyotik
    # Süre: Genellikle 7-14 gün
    # ══════════════════════════════════════════════════════════════
    if is_penisilin:
        detaylar['alt_kategori'] = 'PENISILIN_ANTIBIYOTIK'
        uyarilar = ["EK-4/E: Ayaktan tedavide tüm hekimler raporsuz yazabilir"]

        if 'KLAVULANAT' in etkin_madde or 'KLAVULANIK' in etkin_madde:
            uyarilar.append("Amoksisilin-Klavulanat: 625 mg 3x1 veya 1000 mg 2x1, 7-14 gün")
            uyarilar.append("KC fonksiyon bozukluğu uyarısı (nadiren kolestatik hepatit)")
        elif 'AMOKSISILIN' in etkin_madde:
            uyarilar.append("Amoksisilin: 500 mg 3x1 veya 1000 mg 2x1, 7-14 gün")
        elif 'AMPISILIN' in etkin_madde:
            uyarilar.append("Ampisilin: 500 mg 4x1, 7-14 gün")
        elif 'SULTAMISILIN' in etkin_madde:
            uyarilar.append("Sultamisilin: 375-750 mg 2x1, 7-14 gün")

        uyarilar.append("Penisilin alerjisi sorgulanmalı")
        uyarilar.append("Aynı reçetede başka antibiyotik kontrolü yapılmalı")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Penisilin grubu antibiyotik - ayaktan tedavide raporsuz verilebilir (EK-4/E)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 5. Sefalosporin Antibiyotikler (EK-4/E)
    # SUT: Oral formlar ayaktan tedavide raporsuz
    # Süre: 7-14 gün
    # Uyarı: Penisilin çapraz alerjisi %1-10
    # ══════════════════════════════════════════════════════════════
    if is_sefalo:
        detaylar['alt_kategori'] = 'SEFALOSPORIN_ANTIBIYOTIK'
        uyarilar = [
            "EK-4/E: Oral sefalosporinler ayaktan tedavide raporsuz yazılabilir",
            "Genellikle 7-14 gün tedavi süresi",
            "Penisilin alerjisi olanlarda çapraz alerji riski (%1-10)",
            "Aynı reçetede başka antibiyotik kontrolü yapılmalı",
        ]

        if 'SEFUROKSIM' in etkin_madde:
            uyarilar.append("Sefuroksim aksetil: 250-500 mg 2x1")
        elif 'SEFIKSIM' in etkin_madde:
            uyarilar.append("Sefiksim: 400 mg 1x1 (3. kuşak)")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Sefalosporin antibiyotik - ayaktan tedavide raporsuz verilebilir (EK-4/E)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 6. Antihistaminikler (Desloratadin, Setirizin vb.)
    # SUT: Raporsuz, tüm hekimler yazabilir
    # 1. jenerasyon: Sedasyon, antikolinerjik yan etki
    # 2. jenerasyon: Güvenli profil, tercih edilmeli
    # ══════════════════════════════════════════════════════════════
    if is_antihistaminik:
        detaylar['alt_kategori'] = 'ANTIHISTAMINIK'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        jenerasyon1 = ['KLORFENIRAMIN', 'DIFENHIDRAMIN', 'PROMETAZIN',
                       'HIDROKSIZIN', 'MEKLIZIN']
        if any(m in etkin_madde for m in jenerasyon1):
            uyarilar.append("1. jenerasyon antihistaminik: Sedasyon, antikolinerjik etki, araç kullanımı UYGUN DEĞİL")
            uyarilar.append("Yaşlılarda düşme riski, prostat hastalarında idrar retansiyonu")
            if 'HIDROKSIZIN' in etkin_madde:
                uyarilar.append("Hidroksizin: QT uzaması riski, yaşlılarda maks 50 mg/gün")
        else:
            uyarilar.append("2. jenerasyon antihistaminik: Sedasyon riski düşük, tercih edilir")

        uyarilar.append("Aynı reçetede birden fazla antihistaminik kontrolü yapılmalı")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antihistaminik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 7. Dekonjestanlar / Soğuk algınlığı kombinasyonları
    # SUT: Raporsuz, tüm hekimler
    # Süre: Nazal dekonjestanlar maks 5-7 gün (rinitis medikamentoza)
    # Uyarı: Pseudoefedrin - HT, kardiyak risk
    # ══════════════════════════════════════════════════════════════
    if is_dekonjestan:
        detaylar['alt_kategori'] = 'DEKONJESTAN'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'PSEUDOEFEDRIN' in etkin_madde:
            uyarilar.append("Pseudoefedrin: HT/kardiyak/hipertiroidi hastada KONTRENDİKE")
            uyarilar.append("MAO inhibitörleri ile birlikte VERİLMEMELİ")
        if 'FENILEFRIN' in etkin_madde:
            uyarilar.append("Fenilefrin: Nazal form maks 5-7 gün")
        if 'OKSIMETAZOLIN' in etkin_madde or 'KSILOMETAZOLIN' in etkin_madde:
            uyarilar.append("Topikal nazal dekonjestan: Maks 5-7 gün (rinitis medikamentoza riski)")

        uyarilar.append("KOMBİNASYON: Soğuk algınlığı ilaçlarında gizli parasetamol/NSAİD kontrolü")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Dekonjestan/soğuk algınlığı ilacı - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 8. Topikal antifungal/antiseptik
    # SUT: Raporsuz, tüm hekimler
    # Süre: Topikal antifungal 2-4 hafta, tırnakta 6-12 ay
    # ══════════════════════════════════════════════════════════════
    if is_topikal:
        detaylar['alt_kategori'] = 'TOPIKAL_ANTIFUNGAL'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'BENZIDAMIN' in etkin_madde:
            uyarilar.append("Benzidamin: Antiinflamatuar gargara/sprey, kısa süreli (7-10 gün)")
        elif 'TERBINAFIN' in etkin_madde:
            uyarilar.append("Topikal terbinafin: Dermatofitlerde 1-2 hafta, tinea pediste 4 hafta")
        else:
            uyarilar.append("Topikal antifungal: Genellikle 2-4 hafta tedavi süresi")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Topikal antifungal/antiseptik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 9. MAO-B İnhibitörleri (Parkinson)
    # SUT 4.2.20: Nöroloji uzmanı raporsuz yazabilir
    # Doz: Selegilin maks 10 mg/gün, Rasagilin maks 1 mg/gün
    # Kombinasyon: SSRI/SNRI ile serotonin sendromu riski
    # ══════════════════════════════════════════════════════════════
    if is_maob:
        detaylar['alt_kategori'] = 'MAO-B_INHIBITORU'
        uyarilar = ["Nöroloji uzmanı raporsuz yazabilir, diğer hekimler rapor ile yazabilir"]

        if 'SELEGILIN' in etkin_madde:
            uyarilar.append("Selegilin maks doz: 10 mg/gün (genellikle 5 mg 2x1)")
            uyarilar.append("Tiraminden zengin gıdalarla etkileşim riski (peynir efekti)")
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

        uyarilar.append("KOMBİNASYON: SSRI/SNRI ile serotonin sendromu riski")
        uyarilar.append("Meperidin/tramadol ile birlikte KONTRENDİKE")

        if rapor_kodu:
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

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "MAO-B inhibitörü (Parkinson) - raporsuz verilebilir (nöroloji uzmanı)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 10. PPI - Proton Pompa İnhibitörleri
    # SUT 4.2.17.A: Raporsuz reçete edilebilir
    # Süre: Akut 4-8 hafta, idame için rapor gerekebilir
    # Doz: Standart/çift doz uyarısı
    # ══════════════════════════════════════════════════════════════
    if is_ppi:
        detaylar['alt_kategori'] = 'PPI'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Akut tedavi: 4-8 hafta, sonrasında endikasyon değerlendirmeli",
        ]

        ppi_maks_doz = {
            'OMEPRAZOL': (40, '20 mg 1-2x1'),
            'LANSOPRAZOL': (60, '30 mg 1-2x1'),
            'PANTOPRAZOL': (80, '40 mg 1-2x1'),
            'RABEPRAZOL': (40, '20 mg 1-2x1'),
            'ESOMEPRAZOL': (80, '40 mg 1-2x1'),
        }
        for madde, (maks, dozaj) in ppi_maks_doz.items():
            if madde in etkin_madde:
                uyarilar.append(f"{madde} maks doz: {maks} mg/gün ({dozaj})")
                break

        uyarilar.append("Uzun süreli kullanımda: Mg eksikliği, B12 eksikliği, kemik kırığı riski")
        uyarilar.append("Klopidogrel ile etkileşim: Omeprazol/esomeprazol tercih edilmemeli (CYP2C19)")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "PPI - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 11. H2 Reseptör Antagonistleri
    # SUT: Raporsuz verilebilir
    # ══════════════════════════════════════════════════════════════
    if is_h2ra:
        detaylar['alt_kategori'] = 'H2RA'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Famotidin maks doz: 80 mg/gün (40 mg 2x1)",
        ]
        if 'RANITIDIN' in etkin_madde:
            uyarilar.append("UYARI: Ranitidin NDMA kontaminasyonu nedeniyle birçok ülkede geri çekildi")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "H2 reseptör antagonisti - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 12. Antidiyareikler
    # SUT: Raporsuz verilebilir
    # Doz: Loperamid maks 16 mg/gün
    # ══════════════════════════════════════════════════════════════
    if is_antidiyareik:
        detaylar['alt_kategori'] = 'ANTIDIYAREIK'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'LOPERAMID' in etkin_madde:
            uyarilar.append("Loperamid: Maks 16 mg/gün, başlangıç 4 mg sonra 2 mg/dışkılama")
            uyarilar.append("2 yaş altında KONTRENDİKE, kanlı/ateşli ishalde verilmemeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antidiyareik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 13. Laksatifler
    # SUT: Raporsuz verilebilir
    # Uyarı: Stimülan laksatifler uzun süreli kullanımda bağımlılık
    # ══════════════════════════════════════════════════════════════
    if is_laksatif:
        detaylar['alt_kategori'] = 'LAKSATIF'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
        ]

        stimulan = ['BISAKODIL', 'SENNA']
        if any(m in etkin_madde for m in stimulan):
            uyarilar.append("Stimülan laksatif: Kısa süreli kullanım, uzun süreli kullanımda barsak atonisi")
        elif 'LAKTULOZ' in etkin_madde:
            uyarilar.append("Laktuloz: Osmotik laksatif, hepatik ensefalopatide de kullanılır")
        elif 'MAKROGOL' in etkin_madde:
            uyarilar.append("Makrogol: Osmotik laksatif, kronik kullanıma uygun")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Laksatif - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 14. Antispazmodikler
    # SUT: Raporsuz verilebilir
    # Uyarı: Antikolinerjik yan etkiler (Hyosin)
    # ══════════════════════════════════════════════════════════════
    if is_antispazm:
        detaylar['alt_kategori'] = 'ANTISPAZMODIK'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'HYOSIN' in etkin_madde:
            uyarilar.append("Hyosin: Antikolinerjik, glokom/prostat hastasında dikkat")
        elif 'TRIMEBUTIN' in etkin_madde:
            uyarilar.append("Trimebutin: GİS motilite düzenleyici, 200 mg 3x1")
        elif 'MEBEVERIN' in etkin_madde:
            uyarilar.append("Mebeverin: 200 mg 2x1 (retard form)")
        elif 'DROTAVERIN' in etkin_madde:
            uyarilar.append("Drotaverin: Düz kas gevşetici, 40-80 mg 3x1")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antispazmodik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 15. Kas Gevşeticiler
    # SUT: Raporsuz verilebilir (oral formlar)
    # Süre: Akut kas spazmında 2-3 hafta
    # Uyarı: Sedasyon, hepatotoksisite (tizanidin)
    # ══════════════════════════════════════════════════════════════
    if is_kas_gevsetici:
        detaylar['alt_kategori'] = 'KAS_GEVSETICI'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Sedasyon uyarısı: Araç/makine kullanımı dikkat",
        ]

        if 'TIZANIDIN' in etkin_madde:
            uyarilar.append("Tizanidin: Maks 36 mg/gün, KC fonksiyon izlemi gerekli")
            uyarilar.append("Fluvoksamin/siprofloksasin ile birlikte KONTRENDİKE (CYP1A2)")
        elif 'BAKLOFEN' in etkin_madde:
            uyarilar.append("Baklofen: Ani kesilmemeli (nöbet/halüsinasyon riski), doz azaltarak bırakılmalı")
        elif 'TOLPERISON' in etkin_madde:
            uyarilar.append("Tolperison: 150 mg 3x1, sedasyonu düşük merkezi kas gevşetici")
        elif 'EPERISON' in etkin_madde:
            uyarilar.append("Eperison: 50 mg 3x1, sedasyonu düşük")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Kas gevşetici - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 16. Topikal NSAİD / Analjezik (Jel/Krem)
    # SUT: Raporsuz verilebilir
    # Uyarı: Sistemik emilim düşük, lokal uygulama
    # ══════════════════════════════════════════════════════════════
    if is_topikal_nsaid:
        detaylar['alt_kategori'] = 'TOPIKAL_NSAID'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Topikal form: Sistemik yan etki riski düşük",
            "Açık yara / ekzematöz cilde uygulanmamalı",
            "Oklüzif bandaj ile emilim artar",
        ]
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Topikal NSAİD (jel/krem) - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 17. Topikal Kortikosteroidler (Düşük/Orta Potens)
    # SUT: Raporsuz verilebilir
    # Süre: Genellikle 1-2 hafta, yüzde maks 5 gün
    # Uyarı: Cilt atrofisi, stria, telenjiektazi
    # ══════════════════════════════════════════════════════════════
    if is_topikal_kortiko:
        detaylar['alt_kategori'] = 'TOPIKAL_KORTIKOSTEROID'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Kısa süreli kullanım (1-2 hafta), yüzde maks 5 gün",
        ]

        yuksek_potens = ['KLOBETAZOL', 'BETAMETAZON']
        if any(m in etkin_madde for m in yuksek_potens):
            uyarilar.append("Yüksek potens: Yüz/intertriginöz bölgelerde kullanılmamalı, cilt atrofisi riski")
            uyarilar.append("Çocuklarda sınırlı alan ve sürede kullanılmalı")
        else:
            uyarilar.append("Düşük/orta potens: Yüzde kısa süreli uygun, vücutta 2-4 hafta")

        uyarilar.append("İnfekte lezyona tek başına uygulanmamalı")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Topikal kortikosteroid - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 18. Oftalmik Preparatlar (Suni gözyaşı vb.)
    # SUT: Raporsuz verilebilir
    # ══════════════════════════════════════════════════════════════
    if is_oftalmik:
        detaylar['alt_kategori'] = 'OFTALMIK'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Suni gözyaşı: Koruyucusuz tek doz formlar kontakt lens üzeri uygulanabilir",
            "Koruyuculu formlar: Lens çıkarılarak damlatılmalı, 15 dk beklenip lens takılmalı",
        ]
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Oftalmik preparat - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 19. Otik Preparatlar (Kulak damlaları)
    # SUT: Raporsuz verilebilir
    # Uyarı: Perforasyon varsa aminoglikozid damla KONTRENDİKE
    # ══════════════════════════════════════════════════════════════
    if is_otik:
        detaylar['alt_kategori'] = 'OTIK'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Timpan membran perforasyonunda aminoglikozidli damlalar KONTRENDİKE",
            "Genellikle 7-10 gün tedavi",
        ]
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Otik preparat - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 20. Nazal Kortikosteroidler
    # SUT: Raporsuz verilebilir
    # Süre: Mevsimsel alerjide 2-4 hafta, pereniyal rinitte uzun süreli
    # ══════════════════════════════════════════════════════════════
    if is_nazal_kortiko:
        detaylar['alt_kategori'] = 'NAZAL_KORTIKOSTEROID'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Her burun deliğine 1-2 puf, günde 1-2 kez",
            "Etki başlangıcı 12-24 saat, tam etki 1-2 hafta",
            "Burun kanaması, nazal septum kontrolü (uzun süreli kullanımda)",
        ]
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Nazal kortikosteroid - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 21. Mukolitikler / Ekspektoranlar
    # SUT: Raporsuz verilebilir
    # Uyarı: Asetilsistein astımda bronkospazm yapabilir
    # ══════════════════════════════════════════════════════════════
    if is_mukolitik:
        detaylar['alt_kategori'] = 'MUKOLITIK'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'ASETILSISTEIN' in etkin_madde:
            uyarilar.append("Asetilsistein: 600 mg/gün (200 mg 3x1 veya 600 mg 1x1 efervesan)")
            uyarilar.append("Astımlı hastalarda bronkospazm riski, dikkatle kullanılmalı")
        elif 'AMBROKSOL' in etkin_madde:
            uyarilar.append("Ambroksol: 30 mg 3x1, ekspektoran")
        elif 'ERDOSTEIN' in etkin_madde:
            uyarilar.append("Erdostein: 300 mg 2-3x1, antioksidan etkili mukolitik")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Mukolitik/ekspektoran - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 22. Antitüsifler
    # SUT: Raporsuz verilebilir
    # Uyarı: Kodein 12 yaş altında KONTRENDİKE (FDA/EMA)
    # ══════════════════════════════════════════════════════════════
    if is_antitusif:
        detaylar['alt_kategori'] = 'ANTITUSIF'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'KODEIN' in etkin_madde:
            uyarilar.append("Kodein: 12 yaş altında KONTRENDİKE (solunum depresyonu riski)")
            uyarilar.append("Emziren annelerde KONTRENDİKE")
            uyarilar.append("Bağımlılık potansiyeli: Kısa süreli kullanım")
        elif 'DEKSTROMETORFAN' in etkin_madde:
            uyarilar.append("Dekstrometorfan: MAO inhibitörleri ile birlikte VERİLMEMELİ")
            uyarilar.append("Yüksek dozda sedasyon ve serotonerjik etki")

        uyarilar.append("Prodüktif öksürükte antitüsif verilmemeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antitüsif - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 23. Vitamin / Mineral Preparatları
    # SUT: Raporsuz verilebilir
    # Uyarı: Demir - GİS yan etki, D vitamini - hiperkalsemi riski
    # ══════════════════════════════════════════════════════════════
    if is_vitamin:
        detaylar['alt_kategori'] = 'VITAMIN_MINERAL'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if any(m in etkin_madde for m in ['DEMIR', 'FEROZ', 'DEMIR SULFAT', 'DEMIR FUMARAT']):
            uyarilar.append("Demir: Aç karnına alınmalı, GİS yan etki sık (bulantı, kabızlık)")
            uyarilar.append("Çay/süt ile birlikte alınmamalı (emilim azalır)")
            uyarilar.append("Tetrasiklin/kinolon ile 2 saat ara bırakılmalı")
        elif any(m in etkin_madde for m in ['KOLEKALSIFEROL', 'ERGOKALSIFEROL']):
            uyarilar.append("D Vitamini: Uzun süreli yüksek doz hiperkalsemi riski")
            uyarilar.append("50.000 IU/hafta dozda Ca izlemi önerilir")
        elif any(m in etkin_madde for m in ['SIYANOKOBALAMIN', 'B12']):
            uyarilar.append("B12: IM enjeksiyon daha etkili, oral formda emilim düşük olabilir")
        elif 'FOLIK ASIT' in etkin_madde or 'FOLAT' in etkin_madde:
            uyarilar.append("Folik asit: Gebelikte nöral tüp defekti profilaksisi")
            uyarilar.append("B12 eksikliğini maskeleyebilir, önce B12 değerlendirilmeli")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Vitamin/mineral preparatı - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 24. Oral Antifungaller (Kısa süreli)
    # SUT: Flukonazol tek doz vajinal kandidiyazda raporsuz
    # İtrakonazol: Uzun süreli kullanımda rapor gerekebilir
    # ══════════════════════════════════════════════════════════════
    if is_oral_antifungal:
        detaylar['alt_kategori'] = 'ORAL_ANTIFUNGAL'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir (kısa süreli)"]

        if 'FLUKONAZOL' in etkin_madde:
            uyarilar.append("Flukonazol: Vajinal kandidiyaz tek doz 150 mg")
            uyarilar.append("Orofaringeal kandidiyaz: 100-200 mg/gün 7-14 gün")
            uyarilar.append("CYP2C9/3A4 inhibitörü: Varfarin, statin, fenitoin etkileşimi")
        elif 'ITRAKONAZOL' in etkin_madde:
            uyarilar.append("İtrakonazol: Tırnak mantarında 3 ay pulse tedavi")
            uyarilar.append("KC fonksiyon izlemi gerekli (uzun tedavide)")
            uyarilar.append("Asidik ortamda emilir: Aç karnına veya asidik içecekle")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Oral antifungal - raporsuz verilebilir (kısa süreli tedavi)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 25. Topikal Antibiyotikler
    # SUT: Raporsuz verilebilir
    # Süre: Genellikle 5-10 gün
    # ══════════════════════════════════════════════════════════════
    if is_topikal_ab:
        detaylar['alt_kategori'] = 'TOPIKAL_ANTIBIYOTIK'
        uyarilar = [
            "Raporsuz verilebilir - tüm hekimler yazabilir",
            "Topikal antibiyotik: Genellikle 5-10 gün, geniş alana uzun süreli uygulamada direnç riski",
        ]

        if 'MUPIROSIN' in etkin_madde:
            uyarilar.append("Mupirosin: İmpetigo, MRSA dekolonizasyonu, maks 10 gün")
        elif 'FUSIDIK' in etkin_madde:
            uyarilar.append("Fusidik asit: Stafilokok enfeksiyonları, 7-10 gün")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Topikal antibiyotik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 26. Üriner Antiseptikler
    # SUT: Raporsuz verilebilir (EK-4/E)
    # Fosfomisin: Tek doz komplike olmayan İYE
    # ══════════════════════════════════════════════════════════════
    if is_uriner:
        detaylar['alt_kategori'] = 'URINER_ANTISEPTIK'
        uyarilar = ["EK-4/E: Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'FOSFOMISIN' in etkin_madde:
            uyarilar.append("Fosfomisin: Tek doz 3 g (komplike olmayan alt İYE)")
            uyarilar.append("Aç karnına, yatmadan önce alınmalı")
        elif 'NITROFURANTOIN' in etkin_madde:
            uyarilar.append("Nitrofurantoin: 100 mg 2x1, 5-7 gün (alt İYE)")
            uyarilar.append("GFR <30 ml/dk'da KONTRENDİKE")
            uyarilar.append("Uzun süreli: Pulmoner fibrozis riski")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Üriner antiseptik - raporsuz verilebilir (EK-4/E)",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 27. Antiemetikler
    # SUT: Raporsuz verilebilir
    # Metoklopramid: EPS riski, maks 5 gün
    # Ondansetron: QT uzaması
    # ══════════════════════════════════════════════════════════════
    if is_antiemetik:
        detaylar['alt_kategori'] = 'ANTIEMETIK'
        uyarilar = ["Raporsuz verilebilir - tüm hekimler yazabilir"]

        if 'METOKLOPRAMID' in etkin_madde:
            uyarilar.append("Metoklopramid: Maks 30 mg/gün, maks 5 gün")
            uyarilar.append("EPS riski (özellikle genç kadınlarda), tardif diskinezi (uzun süreli)")
        elif 'DOMPERIDON' in etkin_madde:
            uyarilar.append("Domperidon: Maks 30 mg/gün (10 mg 3x1), maks 7 gün")
            uyarilar.append("QT uzaması riski: Kardiyak hastada dikkat")
        elif 'ONDANSETRON' in etkin_madde:
            uyarilar.append("Ondansetron: 8-16 mg/gün, QT uzaması riski")
            uyarilar.append("Kabızlık ve baş ağrısı sık yan etki")
        elif 'DIMENHIDRINAT' in etkin_madde:
            uyarilar.append("Dimenhidrinat: Hareket hastalığı, 50 mg 3-4x1, sedasyon yapar")

        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            "Antiemetik - raporsuz verilebilir",
            detaylar=detaylar,
            uyari=" | ".join(uyarilar)
        )

    # ══════════════════════════════════════════════════════════════
    # 28. Genel raporsuz bilgilendirme (alt kategori tespit edilemedi)
    # ══════════════════════════════════════════════════════════════
    detaylar['alt_kategori'] = 'GENEL_RAPORSUZ'
    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        "Raporsuz verilebilir - mesaj bilgilendirme amaçlı",
        detaylar=detaylar,
        uyari="Aynı reçetede etkin madde tekrarı kontrol edilmeli"
    )


def kontrol_mono_antihipertansif(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Mono Antihipertansifler — SUT Kuralı Kontrolü

    SUT kuralları:
    1. Mono antihipertansif ilaçlar raporsuz reçete edilebilir
    2. ACE inhibitörleri (ramipril, enalapril, lisinopril vb.)
       ARB'ler (valsartan, losartan, irbesartan, telmisartan, kandesartan vb.)
       KKB'ler (amlodipin, nifedipin, diltiazem, verapamil vb.)
       Beta blokerler (metoprolol, bisoprolol, nebivolol, atenolol vb.)
       Diüretikler (hidroklorotiazid, indapamid, furosemid vb.)
       Alfa blokerler (doksazosin vb.)
    3. Kombine antihipertansif DEĞİLDİR — aynı reçetede 2+ mono antihipertansif
       varsa ve rapor kodu 04.05 ise kombine antihipertansif kuralı (4.2.12.B) uygulanır
    4. ACE+ARB kombinasyonu kontrendike — aynı reçetede birlikte yazılmamalı
    5. Doz aşımı kontrolü: Ramipril maks 10mg/gün, Enalapril maks 40mg/gün vb.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    mesaj_metni = ilac_sonuc.get('mesaj_metni', '')

    sut_kurali = 'Mono antihipertansifler raporsuz reçete edilebilir (SUT genel hüküm)'

    # --- Alt grup tespiti ---
    ace_inhibitorleri = ['RAMIPRIL', 'ENALAPRIL', 'LISINOPRIL', 'PERINDOPRIL',
                         'KAPTOPRIL', 'CAPTOPRIL', 'FOSINOPRIL', 'TRANDOLAPRIL',
                         'BENAZEPRIL', 'KINAPRIL', 'QUINAPRIL', 'SILAZAPRIL',
                         'DELIX', 'TRITACE', 'ENAPRIL', 'KONVERIL', 'ZOFENIL',
                         'COVERSYL', 'ACERYL', 'GOPTEN']
    arb_ler = ['VALSARTAN', 'LOSARTAN', 'IRBESARTAN', 'TELMISARTAN',
               'KANDESARTAN', 'CANDESARTAN', 'OLMESARTAN', 'EPROSARTAN',
               'DIOVAN', 'COZAAR', 'KARVEA', 'MICARDIS', 'ATACAND',
               'HIPERSAR', 'BENICAR', 'TEVETEN']
    kkb_ler = ['AMLODIPIN', 'NIFEDIPIN', 'DILTIAZEM', 'VERAPAMIL',
               'FELODIPIN', 'LERKANIDIPIN', 'LACIDIPIN', 'NORVASC',
               'ADALAT', 'ISOPTIN', 'ZANIDIP']
    beta_blokerler = ['METOPROLOL', 'BISOPROLOL', 'NEBIVOLOL', 'ATENOLOL',
                      'PROPRANOLOL', 'KARVEDILOL', 'CARVEDILOL', 'BELOC',
                      'CONCOR', 'VASOXEN', 'DILATREND', 'TENSINOR']
    diuretikler = ['HIDROKLOROTIAZID', 'HYDROCHLOROTHIAZIDE', 'INDAPAMID',
                   'FUROSEMID', 'SPIRONOLAKTON', 'AMILORID',
                   'LASIX', 'FLUDEX', 'ALDACTONE']
    alfa_blokerler = ['DOKSAZOSIN', 'DOXAZOSIN', 'CARDURA']

    ilac_ref = f"{etkin_madde} {ilac_adi}"
    ace_mi = any(k in ilac_ref for k in ace_inhibitorleri)
    arb_mi = any(k in ilac_ref for k in arb_ler)
    kkb_mi = any(k in ilac_ref for k in kkb_ler)
    bb_mi = any(k in ilac_ref for k in beta_blokerler)
    diuretik_mi = any(k in ilac_ref for k in diuretikler)
    alfa_mi = any(k in ilac_ref for k in alfa_blokerler)

    alt_grup = ('ACE inhibitörü' if ace_mi else
                'ARB' if arb_mi else
                'KKB' if kkb_mi else
                'Beta bloker' if bb_mi else
                'Diüretik' if diuretik_mi else
                'Alfa bloker' if alfa_mi else
                'Mono antihipertansif')

    detaylar = {
        'alt_grup': alt_grup,
        'rapor_gerekli': False,
        'raporsuz_verilebilir': True,
    }

    uyarilar = []

    # --- 1) Rapor kodu kontrolü ---
    if rapor_kodu:
        if rapor_kodu.startswith('04.05'):
            detaylar['rapor_kodu_notu'] = 'Antihipertansif raporu mevcut'
            uyarilar.append(
                f"Rapor kodu {rapor_kodu} (antihipertansif) — mono ilaç için rapor zorunlu değil, "
                "ancak kombine antihipertansif kontrolü (4.2.12.B) kapsamında olabilir"
            )
        else:
            detaylar['rapor_kodu_notu'] = f'Rapor kodu {rapor_kodu} mevcut (antihipertansif dışı olabilir)'

    # --- 2) Mesaj kontrolü (Medula uyarı mesajları) ---
    if mesaj_metni:
        mesaj_lower = mesaj_metni.replace('İ', 'i').replace('I', 'ı').lower()
        if 'rapor' in mesaj_lower and ('gerekli' in mesaj_lower or 'zorunlu' in mesaj_lower):
            uyarilar.append(
                f"Medula mesajında rapor uyarısı var — kontrol edilmeli"
            )
        if 'kombine' in mesaj_lower or 'kombinasyon' in mesaj_lower:
            uyarilar.append(
                "Medula mesajında kombinasyon uyarısı — kombine antihipertansif kuralı (4.2.12.B) kontrol edilmeli"
            )
        if _turkce_ara(mesaj_metni, 'doz') and _turkce_ara(mesaj_metni, 'aşım'):
            uyarilar.append("Medula mesajında doz aşımı uyarısı var")

    # --- 3) ACE + ARB birlikte kullanım uyarısı ---
    if ace_mi or arb_mi:
        uyarilar.append(
            f"{alt_grup} — aynı reçetede ACE inhibitörü + ARB birlikte kullanımı kontrendikedir"
        )

    # --- 4) Doz kontrolü (ilac_adi'ndan mg bilgisi çıkarılabiliyorsa) ---
    mg_match = re.search(r'(\d+(?:[.,]\d+)?)\s*MG', ilac_adi)
    if mg_match:
        doz_mg = float(mg_match.group(1).replace(',', '.'))
        detaylar['tespit_edilen_doz_mg'] = doz_mg

        maks_dozlar = {
            'RAMIPRIL': (10, 'Ramipril maks 10 mg/gün'),
            'ENALAPRIL': (40, 'Enalapril maks 40 mg/gün'),
            'LISINOPRIL': (40, 'Lisinopril maks 40 mg/gün'),
            'PERINDOPRIL': (10, 'Perindopril maks 10 mg/gün'),
            'VALSARTAN': (320, 'Valsartan maks 320 mg/gün'),
            'LOSARTAN': (100, 'Losartan maks 100 mg/gün'),
            'IRBESARTAN': (300, 'İrbesartan maks 300 mg/gün'),
            'TELMISARTAN': (80, 'Telmisartan maks 80 mg/gün'),
            'KANDESARTAN': (32, 'Kandesartan maks 32 mg/gün'),
            'CANDESARTAN': (32, 'Kandesartan maks 32 mg/gün'),
            'AMLODIPIN': (10, 'Amlodipin maks 10 mg/gün'),
            'METOPROLOL': (200, 'Metoprolol maks 200 mg/gün'),
            'BISOPROLOL': (10, 'Bisoprolol maks 10 mg/gün'),
            'NEBIVOLOL': (5, 'Nebivolol maks 5 mg/gün'),
        }

        for madde, (maks, aciklama) in maks_dozlar.items():
            if madde in etkin_madde:
                detaylar['maks_doz_bilgi'] = aciklama
                if doz_mg > maks:
                    uyarilar.append(
                        f"DOZ AŞIMI: {etkin_madde} {doz_mg} mg > maks {maks} mg/gün"
                    )
                    detaylar['doz_asimi'] = True
                break

    # --- 5) Sonuç oluştur ---
    birlesik_uyari = ' | '.join(uyarilar) if uyarilar else None

    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=f"{alt_grup} — raporsuz verilebilir",
        detaylar=detaylar,
        uyari=birlesik_uyari,
        sut_kurali=sut_kurali,
        aranan_ibare='mono antihipertansif / raporsuz reçete',
        bulunan_metin=_eslesen_parcayi_bul(metin, etkin_madde.lower()) if metin and etkin_madde else None
    )


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
    # Minimal handlers — rapor varsa uygun, yoksa kontroledilemedi
    'BENZODIAZEPIN': kontrol_raporsuz_bilgilendirme,  # Raporsuz, uzman değerlendirmesi
    'GOZ_LUBRIKAN': kontrol_raporsuz_bilgilendirme,   # Raporsuz, suni gözyaşı
    'ADHD': kontrol_genel_raporlu,                     # Rapor + çocuk psikiyatrisi
    # Detaylı alt grup kontrolleri (wrapper — ilac_sonuc'dan parametreleri çıkarır)
    'INKONTINANS': lambda s: _inkontinans_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'BPH_PROSTAT': lambda s: _bph_prostat_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'DEMIR_IV': lambda s: _demir_iv_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'DESMOPRESIN': lambda s: _desmopresin_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'NOROPATIK_AGRI': lambda s: _noropatik_agri_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'ENTERAL_BESLENME': lambda s: _enteral_beslenme_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
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
    'BENZODIAZEPIN': 'Benzodiazepin/Anksiyolitik',
    'GOZ_LUBRIKAN': 'Göz Lubrikan / Suni Gözyaşı',
    'ADHD': 'ADHD (4.2.34.B)',
    'INKONTINANS': 'İnkontinans / Antimuskarinik (4.2.16.B)',
    'BPH_PROSTAT': 'BPH / Prostat Tedavisi',
    'DEMIR_IV': 'IV Demir Tedavisi',
    'DESMOPRESIN': 'Desmopresin (Enürezis/DI)',
    'NOROPATIK_AGRI': 'Nöropatik Ağrı (Gabapentin/Pregabalin/Duloksetin)',
    'ENTERAL_BESLENME': 'Enteral Beslenme Solüsyonları',
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
