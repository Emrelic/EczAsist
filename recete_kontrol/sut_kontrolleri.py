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
from .base_kontrol import (BaseKontrol, KontrolSonucu, KontrolRaporu,
                            SartDurumu, SartSonuc)

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
    '04.12': 'DMAH',                   # DMAH (Enoksaparin/Bemiparin/Dalteparin/Nadroparin)
    '11.04': 'PSIKIYATRI',             # Psikiyatri
    '11.04.5': 'PSIKIYATRI',
    '11.04.8': 'PSIKIYATRI',
    '11.03': 'PSIKIYATRI',
    '05.01': 'SOLUNUM',               # Solunum LABA+ICS
    '05.02': 'SOLUNUM',               # Solunum LABA+LAMA+ICS
    '15.04': 'SOLUNUM',               # Solunum raporlu (nebülizasyon vb.)
    '15.05': 'SOLUNUM',               # Solunum raporlu
    '15.15': 'GENEL_RAPORLU',         # Enteral beslenme / nutrisyonel desteğin yardımcı ürünleri
    '06.07': 'GIS',                   # Hepatik kolestaz / Ursodeoksikolik asit grubu
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
    '03.01': 'IMMUNSUPRESIF',          # Organ nakli / immünosüpresif (Takrolimus vb.)
    '07.03': 'GENEL_RAPORLU',          # Endokrin metabolik (Hiperparatiroidi, Sinakalset vb.)
    '07.03.1': 'GENEL_RAPORLU',
    '07.03.2': 'GENEL_RAPORLU',
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

    # BIFOSFONAT (Osteoporoz - SUT 4.2.17)
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

    # RALOKSIFEN (SERM - SUT 4.2.17.A(6a))
    'RALOKSIFEN': 'RALOKSIFEN',
    'RALOKSIFEN HCL': 'RALOKSIFEN',
    'RALOKSIFEN HIDROKLORUR': 'RALOKSIFEN',
    'RALOKSIFEN HIDROKLORÜR': 'RALOKSIFEN',
    'BAZEDOKSIFEN': 'RALOKSIFEN',  # Aynı SERM grubu

    # KALSITONIN (SUT 4.2.17.A(7-8) + 4.2.17.B Sudek)
    'KALSITONIN': 'KALSITONIN',
    'KALSİTONİN': 'KALSITONIN',
    'CALCITONIN': 'KALSITONIN',
    'KALSITONIN SOMON': 'KALSITONIN',
    'CALCITONIN SALMON': 'KALSITONIN',

    # AKTIF D VITAMINI (SUT 4.2.17.A(9): osteoporozda ödenmez)
    'KALSITRIOL': 'AKTIF_D_VITAMINI',
    'CALCITRIOL': 'AKTIF_D_VITAMINI',
    'ALFAKALSIDOL': 'AKTIF_D_VITAMINI',
    'ALFA KALSIDOL': 'AKTIF_D_VITAMINI',
    'ALPHACALCIDOL': 'AKTIF_D_VITAMINI',

    # OSTEOPOROZ BIYOLOJIK (SUT 4.2.17.A(6b))
    'DENOSUMAB': 'OSTEOPOROZ_BIYOLOJIK',
    'TERIPARATID': 'OSTEOPOROZ_BIYOLOJIK',
    'TERIPARATIDE': 'OSTEOPOROZ_BIYOLOJIK',
    'ROMOSOZUMAB': 'OSTEOPOROZ_BIYOLOJIK',
    'STRONSIYUM RANELAT': 'OSTEOPOROZ_BIYOLOJIK',
    'STRONTIUM RANELAT': 'OSTEOPOROZ_BIYOLOJIK',

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
    'BEMIPARIN': 'DMAH',
    'BEMIPARIN SODYUM': 'DMAH',
    'DALTEPARIN': 'DMAH',
    'DALTEPARIN SODYUM': 'DMAH',
    'NADROPARIN': 'DMAH',
    'NADROPARIN KALSIYUM': 'DMAH',
    'TINZAPARIN': 'DMAH',
    'TINZAPARIN SODYUM': 'DMAH',
    'PARNAPARIN': 'DMAH',
    'REVIPARIN': 'DMAH',
    'CERTOPARIN': 'DMAH',
    'FONDAPARINUKS': 'DMAH',                 # Fondaparinux (sentetik pentasakkarit)
    'FONDAPARINUX': 'DMAH',

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

    # Test çubukları / Diyabet sarf — Medula otomatik kontrol ediyor
    'SEKER OLCUM CUBUKLARI': 'MEDULA_OTOMATIK',
    'KAN SEKERI OLCUM': 'MEDULA_OTOMATIK',
    'GLUKOZ TEST': 'MEDULA_OTOMATIK',

    # Topikal antifungal (raporsuz)
    'NAFTIFIN': 'RAPORSUZ_BILGILENDIRME',
    'NAFTIFIN HCL': 'RAPORSUZ_BILGILENDIRME',
    'NAFTIFIN HIDROKLORUR': 'RAPORSUZ_BILGILENDIRME',

    # İnsülinler (etkin madde "INSULIN ..." varyantları)
    'INSULIN': 'DIYABET_DPP4_SGLT2',
    'INSULIN NPH': 'DIYABET_DPP4_SGLT2',
    'INSULIN NPH(HUMAN)': 'DIYABET_DPP4_SGLT2',
    'INSULIN HUMAN': 'DIYABET_DPP4_SGLT2',
    'INSULIN GLARGIN': 'DIYABET_DPP4_SGLT2',
    'INSULIN DETEMIR': 'DIYABET_DPP4_SGLT2',
    'INSULIN DEGLUDEC': 'DIYABET_DPP4_SGLT2',
    'INSULIN ASPART': 'DIYABET_DPP4_SGLT2',
    'INSULIN LISPRO': 'DIYABET_DPP4_SGLT2',
    'INSULIN GLULIZIN': 'DIYABET_DPP4_SGLT2',

    # Hepatik kolestaz (UDCA grubu) — kolestatik karaciğer hastalıkları
    'URSODEOKSIKOLIK ASIT': 'GIS',
    'URSODEOKSIKOLIK ASID': 'GIS',
    'URSODEOKSIKOLIK': 'GIS',
    'URSODEOXYCHOLIC ACID': 'GIS',

    # Hiperparatiroidi (sekonder, kalsimimetik) — endokrin
    'SINAKALSET': 'GENEL_RAPORLU',
    'SINAKALSET HCL': 'GENEL_RAPORLU',
    'CINACALCET': 'GENEL_RAPORLU',
    'ETELKALSETIDE': 'GENEL_RAPORLU',
    'ETELCALCETIDE': 'GENEL_RAPORLU',
    'EVOKALSET': 'GENEL_RAPORLU',

    # Multipl Skleroz (DMT) etkin maddeleri — GENEL_RAPORLU içinde MS bloğu çalışır
    'DIMETIL FUMARAT': 'GENEL_RAPORLU',
    'INTERFERON BETA': 'GENEL_RAPORLU',
    'INTERFERON BETA-1A': 'GENEL_RAPORLU',
    'INTERFERON BETA-1B': 'GENEL_RAPORLU',
    'GLATIRAMER': 'GENEL_RAPORLU',
    'GLATIRAMER ASETAT': 'GENEL_RAPORLU',
    'FINGOLIMOD': 'GENEL_RAPORLU',
    'TERIFLUNOMID': 'GENEL_RAPORLU',
    'NATALIZUMAB': 'GENEL_RAPORLU',
    'ALEMTUZUMAB': 'GENEL_RAPORLU',
    'OKRELIZUMAB': 'GENEL_RAPORLU',
    'OCRELIZUMAB': 'GENEL_RAPORLU',
    'SIPONIMOD': 'GENEL_RAPORLU',
    'OZANIMOD': 'GENEL_RAPORLU',
    'KLADRIBIN': 'GENEL_RAPORLU',
    'OFATUMUMAB': 'GENEL_RAPORLU',

    # İmmünosüpresif ilaçlar (Organ nakli / otoimmün)
    'TAKROLIMUS': 'IMMUNSUPRESIF',
    'MIKOFENOLAT SODYUM': 'IMMUNSUPRESIF',
    'MIKOFENOLAT MOFETIL': 'IMMUNSUPRESIF',
    'MIKOFENOLIK ASIT': 'IMMUNSUPRESIF',
    'SIROLIMUS': 'IMMUNSUPRESIF',
    'EVEROLIMUS': 'IMMUNSUPRESIF',
    'SIKLOSPORIN': 'IMMUNSUPRESIF',
    'AZATIYOPRIN': 'IMMUNSUPRESIF',
    'AZATHIOPRINE': 'IMMUNSUPRESIF',
}


# Aroma/lezzet kelimeleri — ticari ad eşleşmesinde yok sayılır.
# Örn. "RESOURCE GLUTAMIN VANILYA" reçetesi "RESOURCE GLUTAMIN" girdisiyle eşleşmeli;
# VANILYA aroma olduğu için anahtar kelime sayılmaz.
AROMA_KELIMELER = {
    'VANILYA', 'VANILLA', 'CILEK', 'ÇILEK', 'ÇİLEK', 'STRAWBERRY',
    'CIKOLATA', 'ÇIKOLATA', 'ÇİKOLATA', 'CHOCOLATE',
    'KAHVE', 'COFFEE', 'KARAMEL', 'CARAMEL', 'KARAMELLI',
    'MUZ', 'BANANA', 'PORTAKAL', 'ORANGE', 'LIMON', 'LEMON',
    'TROPIKAL', 'TROPICAL', 'ORMAN', 'MEYVE', 'MEYVELI', 'MEYVELİ',
    'NOTRAL', 'NOTR', 'NEUTRAL', 'YOGURT', 'YOĞURT', 'YOGHURT',
    'KAYISI', 'KAKAO', 'COCOA', 'BAL', 'HONEY',
    'AROMASIZ', 'AROMALI', 'AROMA', 'TATSIZ', 'TATLI',
}


def _ticari_ad_kelime_eslesir(arama_ifadesi: str, ilac_adi: str) -> bool:
    """Aramada geçen tüm kelimeler ilaç adında bulunmalı (aroma kelimeleri hariç).

    Tek kelimeli aramalar (ör. 'NEURONTIN') eski davranışla uyumlu çalışır:
    tek kelimenin geçmesi yeterlidir. Çok kelimeli aramalarda (ör.
    'RESOURCE GLUTAMIN') tüm aroma-dışı kelimelerin geçmesi gerekir.
    """
    if not arama_ifadesi or not ilac_adi:
        return False
    ilac_upper = ilac_adi.upper()
    arama_kelimeleri = [k for k in arama_ifadesi.upper().split()
                        if k not in AROMA_KELIMELER]
    if not arama_kelimeleri:
        return False
    return all(k in ilac_upper for k in arama_kelimeleri)


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
    'EXODERIL': 'RAPORSUZ_BILGILENDIRME',  # Naftifin (topikal antifungal)
    # Test çubukları / Glukometre stripleri — Medula otomatik kontrol
    'VIVACHEK': 'MEDULA_OTOMATIK',
    'ACCU-CHEK': 'MEDULA_OTOMATIK',
    'ACCUCHEK': 'MEDULA_OTOMATIK',
    'CONTOUR': 'MEDULA_OTOMATIK',
    'ONETOUCH': 'MEDULA_OTOMATIK',
    'FREESTYLE': 'MEDULA_OTOMATIK',
    'GLUCOMETER': 'MEDULA_OTOMATIK',
    'GLUKOMETER': 'MEDULA_OTOMATIK',
    'GLUKOZ TEST': 'MEDULA_OTOMATIK',
    'PRODIGY': 'MEDULA_OTOMATIK',
    'OPTIUM': 'MEDULA_OTOMATIK',
    'GLUKOSURE': 'MEDULA_OTOMATIK',
    'BIONIME': 'MEDULA_OTOMATIK',
    'GLUCOFIX': 'MEDULA_OTOMATIK',

    # İmmünosüpresif (Organ nakli)
    'ADVAGRAF': 'IMMUNSUPRESIF',     # Takrolimus uzatılmış salımlı
    'ADOPORT': 'IMMUNSUPRESIF',      # Takrolimus
    'PROGRAF': 'IMMUNSUPRESIF',      # Takrolimus
    'TACNI': 'IMMUNSUPRESIF',
    'TACROBELL': 'IMMUNSUPRESIF',
    'MODIGRAF': 'IMMUNSUPRESIF',
    'MYFORTIC': 'IMMUNSUPRESIF',     # Mikofenolat sodyum
    'CELLCEPT': 'IMMUNSUPRESIF',     # Mikofenolat mofetil
    'MYREL': 'IMMUNSUPRESIF',
    'RAPAMUNE': 'IMMUNSUPRESIF',     # Sirolimus
    'CERTICAN': 'IMMUNSUPRESIF',     # Everolimus
    'AFINITOR': 'IMMUNSUPRESIF',
    'SANDIMMUN': 'IMMUNSUPRESIF',    # Siklosporin
    'IMURAN': 'IMMUNSUPRESIF',       # Azatiyoprin

    # Ursodeoksikolik asit (Hepatik kolestaz)
    'URSOVEF': 'GIS',
    'URSOFALK': 'GIS',
    'URSACTIVE': 'GIS',
    'URSO 100': 'GIS',
    'URSOLIV': 'GIS',
    'DESORE': 'GIS',

    # Enteral nutrisyon ek (ABOUND vb.)
    'ABOUND': 'ENTERAL_BESLENME',
    'JUVEN': 'ENTERAL_BESLENME',

    # Klasik OAD (sülfonilüre) — etkin madde boş geldiğinde ticari adla tanı
    'DIAMICRON': 'DIYABET_DPP4_SGLT2',
    'AMARYL': 'DIYABET_DPP4_SGLT2',
    'GLIBEDAL': 'DIYABET_DPP4_SGLT2',

    # İnsülin — etkin madde boş geldiğinde ticari adla tanı
    'HUMULIN': 'DIYABET_DPP4_SGLT2',  # is_insulin tespiti içeride yapılır
    'NOVORAPID': 'DIYABET_DPP4_SGLT2',
    'HUMALOG': 'DIYABET_DPP4_SGLT2',
    'LANTUS': 'DIYABET_DPP4_SGLT2',
    'TOUJEO': 'DIYABET_DPP4_SGLT2',
    'TRESIBA': 'DIYABET_DPP4_SGLT2',
    'LEVEMIR': 'DIYABET_DPP4_SGLT2',
    'BASAGLAR': 'DIYABET_DPP4_SGLT2',
    'NOVOMIX': 'DIYABET_DPP4_SGLT2',
    'ACTRAPID': 'DIYABET_DPP4_SGLT2',
    'APIDRA': 'DIYABET_DPP4_SGLT2',

    # Soğuk algınlığı / OTC kombinasyonlar
    'COLDAWAY': 'RAPORSUZ_BILGILENDIRME',
    'GRIPIN': 'RAPORSUZ_BILGILENDIRME',
    'PARASETAMOL': 'RAPORSUZ_BILGILENDIRME',
    'PAROL': 'RAPORSUZ_BILGILENDIRME',
    'GERALGINE': 'RAPORSUZ_BILGILENDIRME',

    # Tüberküloz / antibakteriyel raporsuz
    'RIF': 'RAPORSUZ_BILGILENDIRME',          # Rifampisin enjeksiyon
    'RIFCAP': 'RAPORSUZ_BILGILENDIRME',
    'RIFAMPIN': 'RAPORSUZ_BILGILENDIRME',

    # Topikal antifungal (raporsuz) — ek ticari isimler
    'DERMIFIN': 'RAPORSUZ_BILGILENDIRME',     # Terbinafin sprey/krem
    'TERBIN': 'RAPORSUZ_BILGILENDIRME',
    'LAMISIL DERMGEL': 'RAPORSUZ_BILGILENDIRME',
    'FUNGOSTOP': 'RAPORSUZ_BILGILENDIRME',
    'TERBISIL': 'RAPORSUZ_BILGILENDIRME',

    # Antiseptik gargara / oral antiseptik (raporsuz)
    'KLOROBEN': 'RAPORSUZ_BILGILENDIRME',     # Benzidamin + klorheksidin
    'TANTUM VERDE': 'RAPORSUZ_BILGILENDIRME',
    'HEXORAL': 'RAPORSUZ_BILGILENDIRME',
    'ORALMEDIC': 'RAPORSUZ_BILGILENDIRME',
    'KLORHEX': 'RAPORSUZ_BILGILENDIRME',
    'DROSID': 'RAPORSUZ_BILGILENDIRME',

    # Soğuk algınlığı şurubu / çocuk öksürük (raporsuz)
    'KATARIN': 'RAPORSUZ_BILGILENDIRME',
    'PEDIFEN': 'RAPORSUZ_BILGILENDIRME',
    'BENICAL': 'RAPORSUZ_BILGILENDIRME',
    'CALPOL': 'RAPORSUZ_BILGILENDIRME',

    # Makrolid antibiyotik (raporsuz)
    'KLACID': 'RAPORSUZ_BILGILENDIRME',       # Klaritromisin
    'KLAMOKS': 'RAPORSUZ_BILGILENDIRME',
    'AZRO': 'RAPORSUZ_BILGILENDIRME',
    'AZITRO': 'RAPORSUZ_BILGILENDIRME',
    'KLAROMIN': 'RAPORSUZ_BILGILENDIRME',
    'ZITROMAX': 'RAPORSUZ_BILGILENDIRME',

    # Suni gözyaşı / göz lubrikan (raporsuz)
    'NOVAQUA': 'GOZ_LUBRIKAN',
    'REFRESH': 'GOZ_LUBRIKAN',
    'TEARS NATURALE': 'GOZ_LUBRIKAN',
    'OPTIVE': 'GOZ_LUBRIKAN',
    'SYSTANE': 'GOZ_LUBRIKAN',
    'HYLO': 'GOZ_LUBRIKAN',
    'ARTELAC': 'GOZ_LUBRIKAN',
    'LACRIMA': 'GOZ_LUBRIKAN',

    # Solunum (LABA+ICS / LTRA / kombi) — yeni ticari adlar
    'BREQUAL': 'SOLUNUM',                     # Salmeterol+Flutikazon
    'LEVOKAST': 'SOLUNUM',                    # Levosetirizin+Montelukast
    'MONKAST': 'SOLUNUM',                     # Montelukast
    'AIRPLUS': 'SOLUNUM',                     # Salmeterol+Flutikazon
    'INUVAIR': 'SOLUNUM',                     # Beklometazon+Formoterol

    # Gut / hiperürisemi tedavisi (raporsuz — alopurinol/febuksostat)
    'TEGLIX': 'RAPORSUZ_BILGILENDIRME',       # Febuksostat
    'ADENURIC': 'RAPORSUZ_BILGILENDIRME',
    'URICONT': 'RAPORSUZ_BILGILENDIRME',
    'ZYLORIC': 'RAPORSUZ_BILGILENDIRME',
    'URIKOLIZ': 'RAPORSUZ_BILGILENDIRME',
    'ALLOPURINOL': 'RAPORSUZ_BILGILENDIRME',
    'FEBUXOSTAT': 'RAPORSUZ_BILGILENDIRME',

    # Göz damlası — siklosporin formu (immünsüpresif değil, kuru göz için)
    'DEPORES': 'GOZ_LUBRIKAN',                # Siklosporin %0.05/0.1 göz damlası
    'IKERVIS': 'GOZ_LUBRIKAN',                # Siklosporin göz damlası
    'RESTASIS': 'GOZ_LUBRIKAN',               # Siklosporin göz damlası
    'OPTIMMUNE': 'GOZ_LUBRIKAN',

    # Hiperparatiroidi kalsimimetikleri (Sinakalset, Etelkalsetid)
    'CINESET': 'GENEL_RAPORLU',               # Sinakalset
    'MIMPARA': 'GENEL_RAPORLU',
    'PARSABIV': 'GENEL_RAPORLU',              # Etelkalsetid (IV)
    'SENSIPAR': 'GENEL_RAPORLU',
    'KALSIMIMETIK': 'GENEL_RAPORLU',

    # Multipl Skleroz (MS) DMT — ticari adlar → GENEL_RAPORLU MS bloğu
    'TENIPRA': 'GENEL_RAPORLU',               # Dimetil fumarat
    'TECFIDERA': 'GENEL_RAPORLU',             # Dimetil fumarat
    'AVONEX': 'GENEL_RAPORLU',                # Interferon beta-1a
    'REBIF': 'GENEL_RAPORLU',                 # Interferon beta-1a
    'BETAFERON': 'GENEL_RAPORLU',             # Interferon beta-1b
    'EXTAVIA': 'GENEL_RAPORLU',
    'COPAXONE': 'GENEL_RAPORLU',              # Glatiramer
    'GILENYA': 'GENEL_RAPORLU',               # Fingolimod
    'AUBAGIO': 'GENEL_RAPORLU',               # Teriflunomid
    'TYSABRI': 'GENEL_RAPORLU',               # Natalizumab
    'LEMTRADA': 'GENEL_RAPORLU',              # Alemtuzumab
    'OCREVUS': 'GENEL_RAPORLU',               # Okrelizumab
    'MAYZENT': 'GENEL_RAPORLU',               # Siponimod
    'ZEPOSIA': 'GENEL_RAPORLU',               # Ozanimod
    'MAVENCLAD': 'GENEL_RAPORLU',             # Kladribin
    'KESIMPTA': 'GENEL_RAPORLU',              # Ofatumumab
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
    'CLEXANE': 'DMAH',                       # Enoksaparin orijinal
    'HIBOR': 'DMAH',                         # Bemiparin
    'IVOR': 'DMAH',                          # Bemiparin
    'FRAGMIN': 'DMAH',                       # Dalteparin
    'FRAXIPARINE': 'DMAH',                   # Nadroparin
    'FRAXODI': 'DMAH',                       # Nadroparin yüksek doz
    'INNOHEP': 'DMAH',                       # Tinzaparin
    'ARIXTRA': 'DMAH',                       # Fondaparinux

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

    # Enteral beslenme — ticari ad çok kelimeli; tüm anahtar kelimeler (aroma hariç)
    # reçete adında geçmeli. Tek kelime ('RESOURCE') yetmez, ürün varyantı belirtilmeli.
    # RESOURCE ailesi
    'RESOURCE GLUTAMIN': 'ENTERAL_BESLENME',
    'RESOURCE 2.0': 'ENTERAL_BESLENME',
    'RESOURCE PROTEIN': 'ENTERAL_BESLENME',
    'RESOURCE JUNIOR': 'ENTERAL_BESLENME',
    'RESOURCE DIABET': 'ENTERAL_BESLENME',
    'RESOURCE ARGIN': 'ENTERAL_BESLENME',
    'RESOURCE FIBER': 'ENTERAL_BESLENME',
    # NUTRIDRINK ailesi
    'NUTRIDRINK COMPACT': 'ENTERAL_BESLENME',
    'NUTRIDRINK PROTEIN': 'ENTERAL_BESLENME',
    'NUTRIDRINK MULTI FIBRE': 'ENTERAL_BESLENME',
    'NUTRIDRINK YOGURT STYLE': 'ENTERAL_BESLENME',
    'NUTRIDRINK JUNIOR': 'ENTERAL_BESLENME',
    # NUTREN ailesi
    'NUTREN ACTIV': 'ENTERAL_BESLENME',
    'NUTREN OPTIMUM': 'ENTERAL_BESLENME',
    'NUTREN BALANCE': 'ENTERAL_BESLENME',
    'NUTREN 1.5': 'ENTERAL_BESLENME',
    'NUTREN JUNIOR': 'ENTERAL_BESLENME',
    'NUTREN FIBRE': 'ENTERAL_BESLENME',
    # FRESUBIN ailesi
    'FRESUBIN ENERGY': 'ENTERAL_BESLENME',
    'FRESUBIN PROTEIN': 'ENTERAL_BESLENME',
    'FRESUBIN HP ENERGY': 'ENTERAL_BESLENME',
    'FRESUBIN ORIGINAL': 'ENTERAL_BESLENME',
    'FRESUBIN 2KCAL': 'ENTERAL_BESLENME',
    'FRESUBIN INTENSIVE': 'ENTERAL_BESLENME',
    'FRESUBIN DB': 'ENTERAL_BESLENME',  # Diyabetik
    # EVOLVIA ailesi
    'EVOLVIA 1.0': 'ENTERAL_BESLENME',
    'EVOLVIA 1.5': 'ENTERAL_BESLENME',
    'EVOLVIA FIBRE': 'ENTERAL_BESLENME',
    'EVOLVIA JUNIOR': 'ENTERAL_BESLENME',
    'EVOLVIA HP': 'ENTERAL_BESLENME',
    # ENSURE ailesi
    'ENSURE PLUS': 'ENTERAL_BESLENME',
    'ENSURE MAX': 'ENTERAL_BESLENME',
    # PEPTAMEN ailesi
    'PEPTAMEN HN': 'ENTERAL_BESLENME',
    'PEPTAMEN AF': 'ENTERAL_BESLENME',
    'PEPTAMEN JUNIOR': 'ENTERAL_BESLENME',
    # NEPRO ailesi (böbrek hastalarına özel)
    'NEPRO HP': 'ENTERAL_BESLENME',
    'NEPRO LP': 'ENTERAL_BESLENME',
    # IMPACT ailesi
    'IMPACT ORAL': 'ENTERAL_BESLENME',
    'IMPACT ENTERAL': 'ENTERAL_BESLENME',
    # Tek varyantlı / brand-unique olanlar (zaten farklı ürün ailesi yok)
    'PROSURE': 'ENTERAL_BESLENME',
    'MODULEN IBD': 'ENTERAL_BESLENME',
    'GLUCERNA': 'ENTERAL_BESLENME',
    'DIASIP': 'ENTERAL_BESLENME',
    'CUBITAN': 'ENTERAL_BESLENME',

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
    'ALENOTOP': 'BIFOSFONAT',
    'BENEFOS': 'BIFOSFONAT',
    # Raloksifen (SERM)
    'EVISTA': 'RALOKSIFEN',
    'OPTRUMA': 'RALOKSIFEN',
    'RALOXIN': 'RALOKSIFEN',
    'CONBRIZA': 'RALOKSIFEN',     # Bazedoksifen
    # Kalsitonin
    'MIACALCIC': 'KALSITONIN',
    'MIACALCIN': 'KALSITONIN',
    'CALSYNAR': 'KALSITONIN',
    'TONOCALCIN': 'KALSITONIN',
    # Aktif D vitamini (osteoporozda ödenmez)
    'ROCALTROL': 'AKTIF_D_VITAMINI',
    'CALCIJEX': 'AKTIF_D_VITAMINI',
    'ETALPHA': 'AKTIF_D_VITAMINI',
    'ALPHA D3': 'AKTIF_D_VITAMINI',
    'ONE-ALPHA': 'AKTIF_D_VITAMINI',
    'ONEALPHA': 'AKTIF_D_VITAMINI',
    # Osteoporoz biyolojik
    'PROLIA': 'OSTEOPOROZ_BIYOLOJIK',
    'XGEVA': 'OSTEOPOROZ_BIYOLOJIK',
    'FORTEO': 'OSTEOPOROZ_BIYOLOJIK',
    'FORSTEO': 'OSTEOPOROZ_BIYOLOJIK',
    'MOVYMIA': 'OSTEOPOROZ_BIYOLOJIK',
    'EVENITY': 'OSTEOPOROZ_BIYOLOJIK',
    'OSSEOR': 'OSTEOPOROZ_BIYOLOJIK',
    'PROTELOS': 'OSTEOPOROZ_BIYOLOJIK',
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
    # 0. ÖZEL DURUM — Form bazlı override:
    # Aynı etkin madde farklı formlarda farklı SUT kategorisinde olabilir.
    # Örn: SIKLOSPORIN sistemik (SANDIMMUN) → IMMUNSUPRESIF (organ nakli),
    #      SIKLOSPORIN göz damlası (DEPORES/IKERVIS/RESTASIS) → GOZ_LUBRIKAN (kuru göz).
    # ETKIN_MADDE_KATEGORI eşleşmesinden önce form kontrolü yapılır.
    ilac_adi_upper = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde_raw = (ilac_sonuc.get('etkin_madde') or '').upper()
    if 'SIKLOSPORIN' in etkin_madde_raw:
        if any(form in ilac_adi_upper for form in
                ('GOZ DAMLA', 'GÖZ DAMLA', 'GOZ EM', 'GÖZ EM',
                 'GOZ COZ', 'GÖZ ÇÖZ', 'OPHTH', 'EYE DROP')):
            return 'GOZ_LUBRIKAN'

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
    # Çok kelimeli arama ifadelerinde tüm kelimelerin (aroma hariç) ilaç adında
    # geçmesi şartı aranır — RESOURCE GLUTAMIN ile RESOURCE 2.0'ı ayırt etmek için.
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    if ilac_adi:
        # Çok kelimeli girdileri önce dene (daha spesifik) — uzunluğa göre azalan sırada.
        siralanmis = sorted(ILAC_ADI_KATEGORI.items(),
                             key=lambda kv: len(kv[0].split()), reverse=True)
        for em, kategori in siralanmis:
            if _ticari_ad_kelime_eslesir(em, ilac_adi):
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


_TR_LOWER_MAP = str.maketrans({
    'İ': 'i', 'I': 'i', 'ı': 'i',
    'Ş': 's', 'ş': 's',
    'Ğ': 'g', 'ğ': 'g',
    'Ç': 'c', 'ç': 'c',
    'Ö': 'o', 'ö': 'o',
    'Ü': 'u', 'ü': 'u',
})


def _tr_lower(s) -> str:
    """Türkçe karakter güvenli lowercase — karşılaştırma için.

    Python'un str.lower() Türkçe büyük 'İ' için 'i' + combining dot (U+0307)
    üretir; bu da substring aramayı bozar:
        'İÇ HASTALIKLARI'.lower() == 'i̇ç hastaliklari'
        'iç hastalık' in 'i̇ç hastaliklari' → False ❌

    Bu helper Ş/Ğ/Ç/Ö/Ü/İ/I/ı'yı ASCII karşılığına çevirip lower yapar:
        _tr_lower('İÇ HASTALIKLARI') → 'ic hastaliklari'
        'ic hastalik' in 'ic hastaliklari' → True ✓

    `_turkce_normalize`'den farkı: fonetik dönüşüm (ph→f, th→t, x→ks, w→v)
    YAPMAZ — yani ilaç/branş adı gibi substring aramalarda yan etki üretmez.
    Doktor branşı, hasta adı, kurum adı, kullanıcı arama input'u gibi
    karşılaştırmalar için uygundur.
    """
    if not s:
        return ''
    return str(s).translate(_TR_LOWER_MAP).lower()


def _tum_metinleri_birlesir(ilac_sonuc: Dict) -> str:
    """
    SUT kontrolü için tüm metin kaynaklarını birleştir.
    Mesaj metni + rapor açıklamaları + tanı bilgileri + REÇETE AÇIKLAMALARI.

    Lab değerleri (Hb/Ferritin/TSAT, INR, eGFR vb.) bazen reçete açıklamasında
    yazılır — bu yüzden recete_aciklamalari da arama metnine dahil edilir.
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

    # Reçete açıklamaları (Açıklama Listesi tablosu) — lab değerleri burada olabilir
    recete_aciklama = ilac_sonuc.get('recete_aciklamalari', [])
    if recete_aciklama:
        parcalar.extend(recete_aciklama)
    # _recete_aciklamalari (alt çizgili varyant) — bazı çağrı noktalarında bu key kullanılıyor
    recete_aciklama_alt = ilac_sonuc.get('_recete_aciklamalari', [])
    if recete_aciklama_alt:
        parcalar.extend(recete_aciklama_alt)

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

    Davranış:
    - "Ferritin:796" (boşluksuz), "Ferritin: 796", "Ferritin = 796,5",
      "TSAT %25", "TSAT:25%", "Hgb:9.5 g/dL" gibi formatları yakalar.
    - Sayı tarihten ayırt edilir: pattern dd/mm/yyyy gibi tarih içeren
      eşleşmeleri reddeder.
    """
    if not metin:
        return None, ""
    # Türkçe 'İ' (U+0130) Python'un lower()'ında 'i̇' (i + combining dot) verir;
    # önce 'i'ye normalize et. 'I' → 'ı' YAPMA: İngilizce büyük 'I' (örn.
    # "HEMOGLOBIN", "FERRITIN") str.lower() ile zaten 'i'ye dönüşmeli, aksi
    # halde 'hemoglobın' / 'ferritın' olur ve aranan kelimeyle eşleşmez.
    metin_lower = metin.replace('İ', 'i').lower()
    for anahtar in anahtarlar:
        ak = anahtar.lower()
        # "anahtar: 11.5", "anahtar = 11,5", "anahtar 11.5", "anahtar: %23",
        # "anahtar:11.5", "anahtar%25"
        patterns = [
            rf'{re.escape(ak)}\s*[:=]?\s*%?\s*(\d+(?:[.,]\d+)?)',
            rf'{re.escape(ak)}[^0-9]{{0,40}}(\d+(?:[.,]\d+)?)',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, metin_lower):
                try:
                    raw = m.group(1)
                    deger = float(raw.replace(",", "."))
                    # Tarih eşleşmesini reddet: bulunan rakamın hemen ardından
                    # /dd/yyyy gibi devam ediyorsa bu lab değeri değil tarihtir.
                    after = metin_lower[m.end():m.end() + 6]
                    if re.match(r'/\d', after):
                        continue
                    pos = m.start()
                    bas = max(0, pos - 5)
                    son = min(len(metin), m.end() + 10)
                    return deger, metin[bas:son].strip()
                except (ValueError, IndexError):
                    continue
    return None, ""


# ── ESA için gelişmiş lab parserı ──
# SUT 4.2.30 için Ferritin/TSAT/Hb değerleri reçete açıklamasında çok farklı
# formatlarda yazılır. Geniş alias seti:

ESA_HB_ANAHTARLARI = [
    'hemoglobin', 'hgb', 'hb',
]

ESA_FERRITIN_ANAHTARLARI = [
    'serum ferritin', 'ferritin',
]

# TSAT — gözlenen ve plausible varyasyonlar
ESA_TSAT_ANAHTARLARI = [
    'tsat',
    't.sat', 't-sat', 't sat',
    'transferrin satürasyonu', 'transferrin saturasyonu',
    'transferrin sat.', 'transferrin sat',
    'transferrin doygunluğu', 'transferrin doygunlugu',
    'transferin satürasyonu', 'transferin saturasyonu',  # tek r yazımı
    'transferin sat',
    'demir saturasyonu', 'demir satürasyonu',
    'demir doygunluğu', 'demir doygunlugu',
    'demir doyma oranı', 'demir doyma orani',
    'satürasyon', 'saturasyon',  # son çare — "Saturasyon: %25"
]


def _tetkik_tarihi_son_n_gun_mu(metin: str, max_gun: int = 30) -> tuple:
    """Metindeki tetkik tarihlerini bul, en yenisi son max_gun içinde mi?

    SUT 4.2.30 — ESA için tetkik tarihi genellikle son 1 ay içinde olmalı.
    dd/mm/yyyy ve dd.mm.yyyy formatlarını destekler.

    Returns: (uygun: bool|None, en_yeni_tarih: date|None, bulunan_tarihler: list)
    None döndürdüğünde tarih bulunamadı; karar verici "bilinmiyor" sayar.
    """
    from datetime import date, datetime, timedelta
    if not metin:
        return None, None, []
    bugun = date.today()
    sinir = bugun - timedelta(days=max_gun)
    bulunan = []
    # dd/mm/yyyy veya dd.mm.yyyy
    for m in re.finditer(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', metin):
        try:
            g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            t = date(y, a, g)
            # Geleceğe ait ya da çok eski (10+ yıl) tarihleri at
            if t > bugun + timedelta(days=1) or (bugun - t).days > 365 * 10:
                continue
            bulunan.append(t)
        except (ValueError, IndexError):
            continue
    if not bulunan:
        return None, None, []
    en_yeni = max(bulunan)
    return (en_yeni >= sinir), en_yeni, bulunan


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

    # Pragmatik fallback: Rapor kodu 03.01 (organ nakli) veya transplant rapor
    # kodları varsa Medula tarafından zaten kontrol edilmiştir. SGK bu kodla
    # ödediyse endikasyon raporda mevcut demektir.
    if rapor_kodu and (rapor_kodu.startswith('03.01') or rapor_kodu.startswith('03.02')):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f'İmmünosüpresif raporlu (rapor {rapor_kodu}) — Medula transplant/otoimmün şart kontrolünü yapar',
            detaylar={**detaylar, 'medula_otomatik': True},
            uyari='Endikasyon (transplant/otoimmün) raporda yer aldığı varsayılır',
            sut_kurali=sut_kurali,
            aranan_ibare=f'Rapor kodu ({rapor_kodu}) örtük endikasyon'
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

    # Pragmatik fallback: Genel raporlu (20.x), N32-N39, R32 vb. raporlu reçete →
    # Medula tarafından zaten endikasyon onaylanmış demektir.
    if rapor_kodu and (rapor_kodu.startswith('20.')
                         or rapor_kodu.startswith('N32') or rapor_kodu.startswith('N33')
                         or rapor_kodu.startswith('N39') or rapor_kodu.startswith('R32')):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f'İnkontinans raporlu (rapor {rapor_kodu}) — Medula endikasyon/uzman şart kontrolünü yapar',
            detaylar={**detaylar, 'medula_otomatik': True},
            uyari='Endikasyon (overaktif mesane/urge/nörojenik) raporda yer aldığı varsayılır',
            sut_kurali=sut_kurali,
            aranan_ibare=f'Rapor kodu ({rapor_kodu}) örtük endikasyon'
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

    hb, _ = _lab_degeri_cek(birlesik, ESA_HB_ANAHTARLARI)
    ferritin, _ = _lab_degeri_cek(birlesik, ESA_FERRITIN_ANAHTARLARI)
    tsat, _ = _lab_degeri_cek(birlesik, ESA_TSAT_ANAHTARLARI)

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
    # NOT: "HIV" kısaltması Türkçe-normalize sonrası "hıv" olur — her ikisi de aransın.
    hiv = any(k in metin_lower for k in ['hiv', 'hıv', 'aids']) or 'B20' in teshis_metin

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

    # Pragmatik fallback: SGK rapor kodu 06.01/14.01/B16-B20 ile reçeteyi
    # kabul ettiyse, viral yük & tanı raporun kendisinde mevcut demektir.
    # Mesaj metnine düşmeyebilir; eczacı tarafında ek alarm gerekmez.
    rapor_pragmatik = (rapor_kodu and (rapor_kodu.startswith('06.01')
                                         or rapor_kodu.startswith('14.')
                                         or rapor_kodu.startswith('B')))
    if rapor_pragmatik:
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f'Antiviral raporlu (rapor {rapor_kodu}) — Medula viral yük/endikasyon şart kontrolünü yapar',
            detaylar={**detaylar, 'medula_otomatik': True},
            uyari='Viral yük (HBV DNA / HCV RNA / CD4) raporda yer aldığı varsayılır',
            sut_kurali=sut_kurali,
            aranan_ibare=f'Antiviral rapor kodu ({rapor_kodu}) örtük endikasyon'
        )

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


def _enteral_kcal_dozaj_parse(ilac_adi: str) -> dict:
    """Reçete adından kalori ve birim sayısını çıkar.

    Örnek: 'RESOURCE GLUTAMIN 100 G(5GRX20SASE)(400 KCAL)'
    → {'toplam_kcal': 400, 'birim_sayisi': 20, 'birim': 'saşe', 'kcal_birim': 20.0}

    Sıvı: 'NUTRIDRINK COMPACT 125 ML 240 KCAL'
    → {'toplam_kcal': 240, 'hacim_ml': 125, 'birim': 'şişe', 'kcal_birim': 240.0}
    """
    if not ilac_adi:
        return {}
    name_upper = ilac_adi.upper()
    sonuc = {}
    kcal_match = re.search(r'(\d+(?:[.,]\d+)?)\s*KCAL', name_upper)
    if kcal_match:
        sonuc['toplam_kcal'] = float(kcal_match.group(1).replace(',', '.'))
    sase_match = (re.search(r'X\s*(\d+)\s*SASE', name_upper)
                  or re.search(r'(\d+)\s*SASE', name_upper))
    if sase_match:
        sonuc['birim_sayisi'] = int(sase_match.group(1))
        sonuc['birim'] = 'saşe'
    if 'birim' not in sonuc:
        ml_match = re.search(r'(\d+)\s*ML(?!\w)', name_upper)
        if ml_match:
            sonuc['birim_sayisi'] = 1
            sonuc['birim'] = 'şişe'
            sonuc['hacim_ml'] = int(ml_match.group(1))
    if ('toplam_kcal' in sonuc and sonuc.get('birim_sayisi', 0) > 0):
        sonuc['kcal_birim'] = round(sonuc['toplam_kcal'] / sonuc['birim_sayisi'], 1)
    return sonuc


# ═══════════════════════════════════════════════════════════════════════
# SUT 4.2.8.A — ENTERAL BESLENME PARSE HELPER'LARI
# ═══════════════════════════════════════════════════════════════════════
# Pediatrik vs yetişkin algoritma, malnütrisyon kriterleri, raporda
# zorunlu alanların (boy/kilo/VKİ/SD/kalori) parse'ı için yardımcılar.

def _enteral_yas_grubu(hasta_yas) -> str:
    """Hastanın yaş grubunu döndür.

    Dönüş:
      PEDIATRIK_5_ALT  : <5 yaş — yaşa göre ağırlık SD kontrolü
      PEDIATRIK_5_USTU : 5-17 yaş — VKİ SD kontrolü
      YETISKIN_70_ALT  : 18-69 yaş — VKİ <20 eşiği
      YETISKIN_70_USTU : 70+ yaş — VKİ <22 eşiği
      BILINMIYOR       : yaş okunamadı / makul değil
    """
    try:
        yas = int(str(hasta_yas).strip())
    except (ValueError, AttributeError, TypeError):
        return 'BILINMIYOR'
    if yas < 0 or yas > 130:
        return 'BILINMIYOR'
    if yas < 5:
        return 'PEDIATRIK_5_ALT'
    if yas < 18:
        return 'PEDIATRIK_5_USTU'
    if yas < 70:
        return 'YETISKIN_70_ALT'
    return 'YETISKIN_70_USTU'


# Reçete adında geçen ürün ailesi adlarını rapor metniyle eşleştirmek için.
# En uzun match önce gelmeli (RESOURCE GLUTAMIN, RESOURCE PROTEIN > RESOURCE).
# Tüm varyantlar İNGİLİZCE biçimde tutulur — TR-EN harita ile reçete adı
# eşitlik dönüşümünden geçirilir (ENERJI→ENERGY, KOMPAKT→COMPACT, LIF→FIBER).
_ENTERAL_URUN_AILELERI = (
    # Resource (en spesifikten genele)
    'RESOURCE GLUTAMIN', 'RESOURCE PROTEIN', 'RESOURCE JUNIOR',
    'RESOURCE DIABET', 'RESOURCE ARGIN', 'RESOURCE FIBER',
    'RESOURCE 2.0', 'RESOURCE',
    # Nutridrink
    'NUTRIDRINK COMPACT', 'NUTRIDRINK PROTEIN', 'NUTRIDRINK MULTI FIBER',
    'NUTRIDRINK YOGURT STYLE', 'NUTRIDRINK JUNIOR', 'NUTRIDRINK',
    # Nutren
    'NUTREN ACTIV', 'NUTREN OPTIMUM', 'NUTREN BALANCE',
    'NUTREN JUNIOR', 'NUTREN FIBER', 'NUTREN 1.5', 'NUTREN',
    # Fresubin
    'FRESUBIN HP ENERGY', 'FRESUBIN INTENSIVE', 'FRESUBIN ENERGY',
    'FRESUBIN PROTEIN', 'FRESUBIN ORIGINAL', 'FRESUBIN 2KCAL',
    'FRESUBIN DB', 'FRESUBIN',
    # Evolvia
    'EVOLVIA FIBER', 'EVOLVIA JUNIOR', 'EVOLVIA HP',
    'EVOLVIA 1.0', 'EVOLVIA 1.5', 'EVOLVIA',
    # Ensure / Peptamen / Nepro / Impact
    'ENSURE PLUS', 'ENSURE MAX', 'ENSURE',
    'PEPTAMEN HN', 'PEPTAMEN AF', 'PEPTAMEN JUNIOR', 'PEPTAMEN',
    'NEPRO HP', 'NEPRO LP', 'NEPRO',
    'IMPACT ORAL', 'IMPACT ENTERAL', 'IMPACT',
    # Fortimel varyantları
    'FORTIMEL ENERGY', 'FORTIMEL JUCY', 'FORTIMEL EXTRA',
    'FORTIMEL COMPACT', 'FORTIMEL PROTEIN', 'FORTIMEL',
    # Pediasure varyantları
    'PEDIASURE FIBER', 'PEDIASURE PLUS', 'PEDIASURE',
    # Tek aileli ürünler
    'PROSURE', 'MODULEN IBD', 'MODULEN', 'GLUCERNA', 'DIASIP', 'CUBITAN',
    'ABOUND', 'JUVEN', 'NUTRISON', 'INFATRINI',
    'NOVASOURCE', 'ISOSOURCE',
)

# Aroma kelimeleri — reçete adında geçse bile RAPORDA GEÇMESİ ŞART DEĞİL.
# Kullanıcı kuralı: "aroma metni geçmesede olur".
_ENTERAL_AROMA_KELIMELER = frozenset((
    'CILEK', 'CILEKLI', 'STRAWBERRY',
    'VANILYA', 'VANILYALI', 'VANILLA',
    'COKOLATA', 'COKOLATALI', 'CHOCOLATE', 'CIKOLATA', 'CIKOLATALI',
    'KARISIK', 'MIXED', 'MIX',
    'MUZ', 'MUZLU', 'BANANA',
    'KAYISI', 'APRICOT',
    'SEFTALI', 'PEACH',
    'PORTAKAL', 'ORANGE',
    'ELMA', 'APPLE',
    'KIRMIZI', 'MEYVE', 'MEYVELER', 'BERRY', 'BERRIES', 'FRUIT',
    'NATURAL', 'NOTRAL', 'NEUTRAL', 'NOTR',
    'KAFE', 'COFFEE', 'KAHVE', 'KAHVELI',
    'KARAMEL', 'CARAMEL', 'TOFFEE',
    'AROMALI', 'AROMA', 'FLAVOR', 'FLAVORED', 'FLAVOURED',
    'TROPIK', 'TROPICAL',
))

# Birim/sayı/şekil kelimeleri — atılır
_ENTERAL_BIRIM_KELIMELER = frozenset((
    'ML', 'MG', 'G', 'GR', 'KG', 'KCAL', 'CAL', 'L', 'CC',
    'SASE', 'SASESI', 'SASEDIR', 'POSET',
    'TABLET', 'TAB', 'TBL',
    'KAPSUL', 'KAP', 'CAPSULE',
    'AMPUL', 'FLAKON',
    'PAKET', 'KOLI', 'KUTU', 'BOX',
    'SISE', 'SHISE', 'BOTTLE',
    'BARDAK', 'CUP', 'CUPS',
    'PORSIYON', 'SERVIS',
    'IU', 'NMOL', 'MMOL',
))

# TR-EN eşitlikler (reçete adı vs rapor metni arasında):
# rapor 'Energy' yazsa, reçete 'ENERJI' olabilir (veya tam tersi).
# Pattern: TR formu → EN forma normalize et.
_ENTERAL_TR_EN_ESITLIK = {
    'ENERJI': 'ENERGY',
    'KOMPAKT': 'COMPACT',
    'LIFLI':  'FIBER',
    'LIF':    'FIBER',
    'FIBRE':  'FIBER',
    'COCUK':  'JUNIOR',  # Reçete 'NUTRIDRINK ÇOCUK' → 'NUTRIDRINK JUNIOR'
    'EXTRA':  'EXTRA',
    'TUM':    'COMPLETE',
}


def _enteral_tr_en_normalize(metin_norm: str) -> str:
    """Türkçe form → İngilizce form (kelime sınırı ile)."""
    if not metin_norm:
        return ""
    for tr, en in _ENTERAL_TR_EN_ESITLIK.items():
        metin_norm = re.sub(r'\b' + re.escape(tr) + r'\b', en, metin_norm)
    return metin_norm


def _enteral_recete_anlamli_kelimeler(ilac_adi: str) -> list:
    """Reçete adından raporla karşılaştırılacak anlamlı kelimeleri çıkar.

    ATILANLAR:
      - Aroma kelimeleri (ÇİLEK, VANİLYA, ÇİKOLATA, AROMALI, vb.)
      - Birim/şekil kelimeleri (ML, MG, KCAL, KUTU, vb.)
      - Sadece sayıdan oluşan tokenler (100, 200)
      - Sayı + birim birleşik tokenler (100ML, 5GRX20SASE içinde olanlar)
      - Parantez içi metinler
      - Tek karakterli tokenler

    Örn:
      'FORTIMEL ENERJI ÇİLEK AROMALI 200 ML' → ['FORTIMEL', 'ENERGY']
      'PEDIASURE FIBER VANILYA 200 ML'        → ['PEDIASURE', 'FIBER']
      'RESOURCE GLUTAMIN 100 G(5GRX20SASE)(400 KCAL)' → ['RESOURCE', 'GLUTAMIN']
    """
    if not ilac_adi:
        return []
    ad = _enteral_metin_normalize(ilac_adi)
    # Parantez içini at
    ad = re.sub(r'\([^)]*\)', ' ', ad)
    ad = _enteral_tr_en_normalize(ad)
    # Tokenize — sadece harfle başlayan tokenler (sayıyla başlayanlar atılır)
    tokens = re.findall(r'[A-Z][A-Z0-9]*', ad)

    anlamli = []
    for t in tokens:
        if len(t) <= 1:
            continue
        if t.isdigit():
            continue
        if t in _ENTERAL_AROMA_KELIMELER:
            continue
        if t in _ENTERAL_BIRIM_KELIMELER:
            continue
        # Sayı + harf birleşik (100ML, 200KCAL gibi)
        if re.match(r'^\d+[A-Z]+$', t):
            continue
        anlamli.append(t)
    return anlamli


def _enteral_metin_normalize(s: str) -> str:
    """Türkçe karakter + büyük harf + whitespace normalleştirme.

    'Resource Glütamin\n100mg' → 'RESOURCE GLUTAMIN 100MG'

    Eşleştirme yaparken Türkçe karakter farkı (ı↔I, ş↔s vb.), satır sonu
    ve çoklu boşluk sorun yaratmasın diye.
    """
    if not s:
        return ""
    s = str(s)
    cevirim = str.maketrans({
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U',
        'ç': 'C', 'ğ': 'G', 'ı': 'I', 'ö': 'O', 'ş': 'S', 'ü': 'U',
        'â': 'A', 'î': 'I', 'û': 'U',
        'Â': 'A', 'Î': 'I', 'Û': 'U',
    })
    s = s.translate(cevirim).upper()
    s = re.sub(r'\s+', ' ', s)
    return s


def _enteral_rapor_urun_adi_eslestir(ilac_adi: str, metin: str) -> tuple:
    """Reçetedeki ürün adı rapor metninde geçiyor mu?

    SUT 4.2.8.A kuralı: "raporlarda beslenme ürününün adı ... açıkça
    belirtilerek". Kullanıcı kuralı: "aroma hariç tıbbi mamanın tüm ismi
    raporda geçmeli — FORTİMEL ENERJİ ise FORTİMEL ENERJİ; PEDİASURE FİBER
    ise FİBER. Sadece aroma metni geçmesede olur."

    Algoritma:
      1) Reçete adından AROMA + BİRİM + SAYI + parantez kelimelerini at;
         kalan ürün-tanımlayıcı kelimeleri çıkar.
      2) TR-EN eşitliği uygula (ENERJI→ENERGY, KOMPAKT→COMPACT, vb.)
      3) Hem reçeteden çıkan kelimeler hem rapor metni normalize edilir.
      4) Reçeteden kalan TÜM anlamlı kelimelerin (ürün adı + varyantı)
         kelime-sınırı ile rapor metninde geçmesi gerekir.

    Örnekler:
      'FORTIMEL ENERJI ÇİLEK AROMALI 200 ML' → ['FORTIMEL', 'ENERGY']
        Rapor: 'Hastaya Fortimel Energy başlanmıştır' → ✓ eşleşir
        Rapor: 'Hastaya Fortimel başlanmıştır'        → ✗ eşleşmez (ENERGY yok)

      'PEDIASURE FIBER VANILYA 200 ML' → ['PEDIASURE', 'FIBER']
        Rapor: 'Pediasure fiber çocuğa verilecek' → ✓
        Rapor: 'Pediasure başlandı'              → ✗ FIBER yok

    Dönüş: (eslesti: bool, eslesen_aile: str, recetede_geçen_kelimeler: str)
    """
    if not ilac_adi:
        return False, '', ''

    # 1) Reçete adından anlamlı kelimeleri çıkar
    anlamli_kelimeler = _enteral_recete_anlamli_kelimeler(ilac_adi)
    if not anlamli_kelimeler:
        return False, '', ''
    recetede = ' '.join(anlamli_kelimeler)

    # 2) Rapor metnini normalize + TR-EN dönüşümü
    metin_norm = _enteral_metin_normalize(metin or '')
    metin_norm = _enteral_tr_en_normalize(metin_norm)

    # 3) Tüm anlamlı kelimelerin kelime-sınırlı eşleşmesi
    eksik = [kel for kel in anlamli_kelimeler
             if not re.search(r'\b' + re.escape(kel) + r'\b', metin_norm)]
    if not eksik:
        return True, recetede, recetede

    return False, '', recetede


def _enteral_kilo_kaybi_yuzdesi_parse(metin: str):
    """Metinde 'son 6 ayda %5 kilo kaybı' gibi ifadeleri parse et.

    Dönüş: yüzde değeri (float) veya None
    """
    if not metin:
        return None
    desenler = [
        r'%\s*(\d+(?:[.,]\d+)?)\s*(?:dan|den|\'?dan|\'?den)?\s*(?:fazla\s*)?(?:istemsiz\s*)?kilo\s*(?:kayb|azalma)',
        r'kilo\s*(?:kayb|azalma)[^\d%]{0,40}%\s*(\d+(?:[.,]\d+)?)',
        r'(\d+(?:[.,]\d+)?)\s*%\s*(?:istemsiz\s*)?kilo\s*(?:kayb|azalma)',
        r'kilo\s*(?:kayb|azalma)[^\d%]{0,40}(\d+(?:[.,]\d+)?)\s*%',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(',', '.'))
            except ValueError:
                pass
    return None


def _enteral_vki_parse(metin: str):
    """Metinde VKİ / BMI değeri arar.

    Dönüş: VKİ değeri (float) veya None
    """
    if not metin:
        return None
    desenler = [
        r'VK[İI]\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        r'BMI\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        r'beden\s*kitle\s*indeks[i]?\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        r'v[üu]cut\s*kitle\s*indeks[i]?\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            try:
                v = float(m.group(1).replace(',', '.'))
                if 5 <= v <= 80:  # makul VKİ aralığı
                    return v
            except ValueError:
                pass
    return None


def _enteral_boy_parse(metin: str):
    """Boy bilgisi parse et (cm cinsinden).

    Yakalanan formatlar:
      'boy 170 cm' / 'Boy: 170' / '170 cm boy' / 'boyu 165 cm' /
      'V.Boy: 170' / 'BOY 170' / '170cm'

    Dönüş: int veya None (30-220 cm aralığında)
    """
    if not metin:
        return None
    desenler = [
        r'V\.?\s*Boy(?:u|unuz|um)?\s*[:=]?\s*(\d{2,3})',
        r'(?:boy(?:u|unuz|um)?|height)\s*[:=]?\s*(\d{2,3})\s*c?m?',
        r'(\d{2,3})\s*cm\s*boy',
        r'(\d{2,3})\s*cm\b',  # gevşek fallback (sadece "170 cm" geçiyorsa)
    ]
    for d in desenler:
        for m in re.finditer(d, metin, re.IGNORECASE):
            try:
                v = int(m.group(1))
                if 30 <= v <= 220:
                    return v
            except ValueError:
                continue
    return None


def _enteral_kilo_parse(metin: str):
    """Kilo bilgisi parse et (kg cinsinden).

    Yakalanan formatlar:
      'ağırlık 65 kg' / 'kilo 65' / 'kilosu 60 kg' / 'kilonuz 70' /
      'V.Ağırlık: 65' / 'KILO 65' / '65 kg' / 'ağırlığı 70 kg'

    Dönüş: float veya None (1-300 kg aralığında)
    """
    if not metin:
        return None
    desenler = [
        # V.Ağırlık: 65
        r'V\.?\s*A[ğg][ıi]rl[ıi]k\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        # ağırlık/ağırlığı/kilo/kilosu/kilonuz [:=]? X [kg]
        r'(?:v[üu]cut\s*a[ğg][ıi]rl[ıi][ğg][ıi]?|a[ğg][ıi]rl[ıi][ğg][ıi]|a[ğg][ıi]rl[ıi]k|kilo(?:su|nuz)?|weight)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:kg|kgr|kilogram)?',
        # X kg sonu
        r'(\d{1,3}(?:[.,]\d+)?)\s*(?:kg|kgr|kilogram)\b',
    ]
    for d in desenler:
        for m in re.finditer(d, metin, re.IGNORECASE):
            try:
                v = float(m.group(1).replace(',', '.'))
                if 1 <= v <= 300:
                    return v
            except ValueError:
                continue
    return None


def _enteral_gunluk_kcal_ihtiyaci_parse(metin: str):
    """Raporda yazan günlük kalori ihtiyacını parse et.

    Yakalanan formatlar:
      'günlük kalori ihtiyacı 1800 kcal' / '1800 kcal/gün' /
      'günlük ihtiyaç 1500 kcal' / 'kalori: 1500' / '1500 kcal' /
      'enerji ihtiyacı 1800' / 'günlük kalori: 1500' / 'günlük 1500 kcal'

    Dönüş: float veya None (200-5000 aralığında)
    """
    if not metin:
        return None
    desenler = [
        # 1500 kcal/gün veya kcal\gün
        r'(\d{3,5})\s*kcal\s*[/\\]\s*g[üu]n',
        # günlük 1500 kcal
        r'g[üu]nl[üu]k\s+(\d{3,5})\s*kcal',
        # günlük kalori ihtiyacı 1500 [kcal]
        r'g[üu]nl[üu]k\s*kalori\s*(?:ihtiyac[ıi]?|gereksinim[ıi]?)?\s*[:=]?\s*(\d{3,5})\s*(?:kcal)?',
        # günlük (kalori|enerji|kcal) [arada bir şey] 1500
        r'g[üu]nl[üu]k\s*(?:kalori|enerji|kcal)[^\d]{0,15}(\d{3,5})',
        # günlük ihtiyaç 1500 kcal (kalori/enerji yok, ihtiyaç var)
        r'g[üu]nl[üu]k\s*(?:ihtiyac[ıi]?|gereksinim[ıi]?)\s*[:=]?\s*(\d{3,5})\s*kcal',
        # kalori ihtiyacı 1500 / kalori gereksinimi 1500
        r'kalori\s*(?:ihtiyac[ıi]?|gereksinim[ıi]?)\s*[:=]?\s*(\d{3,5})',
        # enerji ihtiyacı 1500 [kcal]
        r'enerji\s*(?:ihtiyac[ıi]?|gereksinim[ıi]?)\s*[:=]?\s*(\d{3,5})\s*(?:kcal)?',
        # 'kalori: 1500' / 'Günlük kalori: 1800'
        r'kalori\s*[:=]\s*(\d{3,5})',
        # En gevşek fallback: salt '1500 kcal' (sadece bir tane geçiyorsa)
        r'(\d{3,5})\s*kcal\b',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            try:
                v = float(m.group(1))
                if 200 <= v <= 5000:  # makul günlük kcal aralığı
                    return v
            except ValueError:
                pass
    return None


def _enteral_sd_parse(metin: str):
    """SD (standart sapma) değerini parse et: -2SD vb.

    Dönüş: float veya None
    """
    if not metin:
        return None
    desenler = [
        r'(-\s*\d+(?:[.,]\d+)?)\s*SD',
        r'SD\s*[:=]?\s*(-\s*\d+(?:[.,]\d+)?)',
        r'standart\s*sapma\s*[:=]?\s*(-\s*\d+(?:[.,]\d+)?)',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(' ', '').replace(',', '.'))
            except ValueError:
                pass
    return None


def _enteral_saglik_kurulu_raporu_mu(metin: str) -> bool:
    """Rapor sağlık kurulu raporu mu? (uzman hekim raporundan farklı)"""
    if not metin:
        return False
    if re.search(r'sa[ğg]l[iı]k\s*kurul', metin, re.IGNORECASE):
        return True
    return False


def _enteral_diyetetik_obezite_disi_kontrolu(metin: str) -> bool:
    """Diyetetik tedavi veya obezite cerrahisi sonucu kilo kayıpları var mı?

    SUT: 'Diyetetik tedaviler ve/veya obezite cerrahisi sonucu oluşan kilo
    kayıpları malnütrisyon olarak değerlendirilmez.'
    """
    if not metin:
        return False
    metin_l = metin.lower()
    return any(k in metin_l for k in (
        'diyetetik tedavi', 'obezite cerrah', 'bariatrik cerrah',
        'sleeve gastrektomi', 'gastrik bypass', 'tüp mide',
    ))


def _enteral_tup_beslenme_var_mi(metin: str) -> bool:
    """Tüp ile beslenme var mı?"""
    if not metin:
        return False
    metin_l = metin.lower()
    return any(k in metin_l for k in (
        'orogastrik sonda', 'nazogastrik sonda', 'nazoenterik',
        'gastrostomi', 'jejunostomi', 'gastrojejunostomi',
        ' peg ', 'peg ile', 'peg tak', 'sondayla', 'sonda ile',
        'tüple bes', 'tuple bes', 'enteral tüp', 'enteral tup',
    ))


def _enteral_yatan_hasta_mi(metin: str) -> bool:
    """Yatan hasta ifadesi geçiyor mu?"""
    if not metin:
        return False
    metin_l = metin.lower()
    return any(k in metin_l for k in (
        'yatan hasta', 'yatış sırasında', 'yatis sirasinda',
        'hospitalize', 'serviste yat', 'yatakta',
    ))


def _enteral_kanser_var_mi(metin: str) -> bool:
    """Metinde kanser tanısı / ICD-10 onkoloji kodu var mı?"""
    if not metin:
        return False
    metin_l = metin.lower()
    if any(k in metin_l for k in (
        'kanser', 'malign', 'onkoloji', 'karsinom',
        'tümör', 'tumor', 'sarkom', 'lenfoma', 'lösemi', 'losemi',
        'metastaz',
    )):
        return True
    # ICD-10 onkoloji kodları: C00-C97, D00-D49 (in situ + benign)
    if re.search(r'\bC\d{2}(?:\.\d+)?\b', metin):
        return True
    if re.search(r'\bD0\d(?:\.\d+)?\b', metin):
        return True
    if re.search(r'\bD[1-4]\d(?:\.\d+)?\b', metin):
        return True
    return False


def _enteral_pediatrik_ozel_durum(metin: str) -> List[str]:
    """SUT 4.2.8.A (1.b) — Çocukluk yaş grubunda malnütrisyon aranmayan
    durumlar:
      - Yatan hastalar
      - Doğuştan metabolik hastalığı olanlar
      - Kanser hastaları
      - Kistik fibroz
      - Crohn hastaları
      - Yanık hastaları
      - Tüp ile beslenenler (orogastrik/nazogastrik/nazoenterik/
        gastrostomi/jejunostomi)
    """
    bulunanlar = []
    if not metin:
        return bulunanlar
    metin_l = metin.lower()
    if _enteral_yatan_hasta_mi(metin):
        bulunanlar.append('Yatan hasta')
    if any(k in metin_l for k in (
        'doğuştan metabolik', 'dogustan metabolik', 'metabolik hastal',
        'fenilketonüri', 'fenilketonuri', 'akçaağaç idrar', 'mple syrup',
        'galaktozemi', 'tirozinemi', 'üre döngüsü', 'organik asidemi',
    )):
        bulunanlar.append('Doğuştan metabolik hastalık')
    if _enteral_kanser_var_mi(metin):
        bulunanlar.append('Kanser')
    if 'kistik fibroz' in metin_l or 'kistik fibrosis' in metin_l:
        bulunanlar.append('Kistik fibroz')
    if 'crohn' in metin_l:
        bulunanlar.append('Crohn hastalığı')
    if 'yanık' in metin_l or 'yanik' in metin_l:
        bulunanlar.append('Yanık')
    if _enteral_tup_beslenme_var_mi(metin):
        bulunanlar.append('Tüp ile beslenme')
    return bulunanlar


def _enteral_yetiskin_ozel_durum(metin: str) -> List[str]:
    """SUT 4.2.8.A (2.b) — Yetişkin hastalarda malnütrisyon aranmayan
    durumlar:
      - Yatan hastalar
      - Kanser hastaları
      - Tüp ile beslenenler (orogastrik/nazogastrik/nazoenterik/
        gastrostomi/jejunostomi/gastrojejunostomi)
    """
    bulunanlar = []
    if not metin:
        return bulunanlar
    if _enteral_yatan_hasta_mi(metin):
        bulunanlar.append('Yatan hasta')
    if _enteral_kanser_var_mi(metin):
        bulunanlar.append('Kanser')
    if _enteral_tup_beslenme_var_mi(metin):
        bulunanlar.append('Tüp ile beslenme')
    return bulunanlar


def _enteral_beslenme_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin,
                                       teshis_metin="", ilac_sonuc=None):
    """SUT 4.2.8 (benzeri) - Enteral beslenme solüsyonları.
    Ticari: EVOLVIA, NUTRIDRINK, NUTREN, FRESUBIN, RESOURCE, ENSURE, BEBELAC,
             PEPTAMEN, PROSURE, NUTREN JUNIOR, MODULEN
    Kriterler:
    - Endikasyon: Malnütrisyon / kronik hastalık / yutma bozukluğu / kanser /
      GİS hastalığı / kistik fibroz / inek sütü alerjisi (çocuk)
    - Uzman: İç Hast. / Gastroenteroloji / Onkoloji / Geriatri / Pediatri
    - Kalori hesabı: ilaç adından kcal/birim parse edilir, günlük doz ile çarpılır.
      Hasta kilosu yoksa karşılama oranı hesaplanmaz, gerekçesi rapora yazılır.
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

    # ── Kalori hesabı ──
    kcal_bilgi = _enteral_kcal_dozaj_parse(ilac_adi)
    detaylar['kcal_bilgi'] = kcal_bilgi
    gunluk_doz = None
    recete_doz = (ilac_sonuc or {}).get('recete_doz') if ilac_sonuc else None
    if isinstance(recete_doz, dict):
        gunluk_doz = recete_doz.get('gunluk_doz')

    # Hasta kilosu reçete/raporda — şu an metinden parse etmiyoruz, açıklama
    # ve teşhislerde kg ifadesi nadir geçer. Olası bir parse:
    kilo_match = re.search(r'(\d{2,3})\s*KG', (metin or '').upper())
    hasta_kilosu = float(kilo_match.group(1)) if kilo_match else None
    detaylar['hasta_kilosu'] = hasta_kilosu

    kalori_bilgileri = []
    if 'kcal_birim' in kcal_bilgi:
        birim = kcal_bilgi['birim']
        kalori_bilgileri.append(
            f"{kcal_bilgi['kcal_birim']} kcal/{birim} (toplam {kcal_bilgi['toplam_kcal']:.0f} kcal × {kcal_bilgi['birim_sayisi']} {birim})"
        )
        if gunluk_doz:
            gunluk_kcal = round(gunluk_doz * kcal_bilgi['kcal_birim'], 1)
            detaylar['gunluk_kcal'] = gunluk_kcal
            kalori_bilgileri.append(
                f"Günlük: {gunluk_doz} {birim} × {kcal_bilgi['kcal_birim']} = {gunluk_kcal:.0f} kcal/gün"
            )
            if hasta_kilosu:
                kcal_per_kg = round(gunluk_kcal / hasta_kilosu, 1)
                detaylar['kcal_per_kg'] = kcal_per_kg
                # SUT yetişkin ihtiyaç: 25-35 kcal/kg/gün
                if kcal_per_kg < 5:
                    kalori_bilgileri.append(
                        f"{kcal_per_kg} kcal/kg/gün — primer beslenme değil, takviye düzeyinde"
                    )
                elif kcal_per_kg < 25:
                    kalori_bilgileri.append(
                        f"{kcal_per_kg} kcal/kg/gün — günlük ihtiyacın altında (hedef 25-35)"
                    )
                elif kcal_per_kg <= 35:
                    kalori_bilgileri.append(
                        f"{kcal_per_kg} kcal/kg/gün — hedef aralıkta (25-35)"
                    )
                else:
                    kalori_bilgileri.append(
                        f"{kcal_per_kg} kcal/kg/gün — hedef üstü (>35)"
                    )
            else:
                kalori_bilgileri.append(
                    "Karşılama oranı (kcal/kg) hesaplanamadı: hasta kilosu reçete/rapor metninde bulunamadı"
                )
        else:
            kalori_bilgileri.append(
                "Günlük kcal hesaplanamadı: reçete günlük dozu okunamadı"
            )
    elif 'toplam_kcal' in kcal_bilgi:
        kalori_bilgileri.append(
            f"Toplam {kcal_bilgi['toplam_kcal']:.0f} kcal — birim sayısı parse edilemedi, kcal/birim hesaplanamadı"
        )
    else:
        kalori_bilgileri.append(
            "Kalori hesaplanamadı: ilaç adında KCAL ifadesi bulunamadı"
        )

    bilgiler = []
    if endikasyonlar: bilgiler.append(f"Endikasyon: {', '.join(endikasyonlar)}")
    if uzman: bilgiler.append("Uzman branş var")
    if enteral_yol: bilgiler.append("Enteral yol (PEG/sonda) belirtilmiş")
    if kalori_bilgileri: bilgiler.append("Kalori: " + " | ".join(kalori_bilgileri))

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

    # Pragmatik fallback: Enteral beslenmeye özgü rapor kodları (15.04, 15.05,
    # 15.15, 02.00, 04.05) varsa Medula tarafından zaten endikasyon onaylanmıştır.
    # Endikasyon raporun kendisinde yer alır; mesaj metnine düşmeyebilir.
    if rapor_kodu and (rapor_kodu.startswith('15.') or rapor_kodu.startswith('02.')):
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f'Enteral beslenme raporlu (rapor {rapor_kodu}) — Medula endikasyon şart kontrolünü yapar',
            detaylar={**detaylar, 'medula_otomatik': True},
            uyari='Kalori/uzman bilgisinin raporda yer aldığı varsayılır',
            sut_kurali=sut_kurali,
            aranan_ibare=f'Rapor kodu ({rapor_kodu}) örtük endikasyon'
        )

    return KontrolRaporu(
        KontrolSonucu.UYGUN_DEGIL,
        'Enteral beslenme UYGUN DEĞİL: Endikasyon raporda bulunamadı',
        detaylar=detaylar,
        uyari='SUT: Malnütrisyon/disfaji/kanser/kistik fibroz + uzman raporu ZORUNLU',
        sut_kurali=sut_kurali,
        aranan_ibare='endikasyon + uzman (zorunlu)'
    )


def _enteral_pediatrik_kontrol(detaylar, ilac_adi, metin, yas_grubu,
                                 urun_eslesti, recetede_aile, doz_uygunsuz,
                                 sut_kurali, doktor_brans="",
                                 gunluk_kcal=None, rapor_gunluk_kcal=None):
    """SUT 4.2.8.A (1) — Çocukluk yaş grubu denetimi.

    Akış:
      1.a Malnütrisyon koşulu (5 yaş altı: ağırlık SD <-2 / 5 yaş üstü: VKİ SD <-2)
          + uzman hekim raporu (çocuk hastalıkları/cerrahi 1. dönem;
          çocuk gastro/nöroloji/metabolizma/cerrahi/endokrinoloji 2. dönem)
          → 6 ay süreli rapor
      1.b Yatan hasta / metabolik hastalık / kanser / kistik fibroz / Crohn /
          yanık / tüp ile beslenme → malnütrisyon aranmaz, 6 ay sağlık kurulu
      1.c Raporda zorunlu alanlar:
          ürün adı + günlük kalori ihtiyacı + kilo + boy + (yaşa göre ağırlık SD
          veya VKİ) + günlük kullanım miktarı; max 30 günlük doz
    """
    metin_lower = (metin or '').lower()
    ihlaller = []
    uyarilar = []

    # ── 1. Reçete dozu rapor dozunu geçemez ──
    if doz_uygunsuz:
        ihlaller.append(
            f'Reçete günlük dozu ({detaylar.get("rec_doz_sayi")}) rapor dozunu '
            f'({detaylar.get("rap_doz_sayi")}) aşıyor'
        )

    # ── 2. Reçetedeki ürün ailesi raporda eşleşti mi? ──
    if not urun_eslesti:
        if recetede_aile:
            ihlaller.append(
                f"Reçetedeki ürün ailesi '{recetede_aile}' rapor metninde geçmiyor"
            )
        else:
            uyarilar.append(
                'Reçetedeki ürün ailesi tespit edilemedi — manuel kontrol'
            )

    # ── 3. Pediatrik özel durumlar (madde 1.b) ──
    ozel_durumlar = _enteral_pediatrik_ozel_durum(metin)
    detaylar['pediatrik_ozel_durumlar'] = ozel_durumlar

    # ── 4. Madde 1.c — Raporda zorunlu alanlar ──
    eksik_alanlar = []
    if detaylar.get('boy') is None:
        eksik_alanlar.append('Boy')
    if detaylar.get('kilo') is None:
        eksik_alanlar.append('Vücut ağırlığı')
    if detaylar.get('rapor_gunluk_kcal_ihtiyaci') is None:
        eksik_alanlar.append('Günlük kalori ihtiyacı')

    # Yaşa göre SD veya VKİ
    if yas_grubu == 'PEDIATRIK_5_ALT':
        if detaylar.get('sd') is None:
            eksik_alanlar.append('Yaşa göre ağırlık SD değeri')
    else:  # PEDIATRIK_5_USTU
        if detaylar.get('vki') is None and detaylar.get('sd') is None:
            eksik_alanlar.append('VKİ veya SD değeri')

    detaylar['eksik_alanlar'] = eksik_alanlar

    # ── 5. Malnütrisyon kontrolü (özel durum yoksa) ──
    malnutrisyon_var = False
    malnutrisyon_gerekce = []
    if not ozel_durumlar:
        sd = detaylar.get('sd')
        if sd is not None and sd < -2:
            malnutrisyon_var = True
            malnutrisyon_gerekce.append(f'SD değeri {sd} (< -2)')
        if not malnutrisyon_var:
            # Metin tabanlı kelime tespiti (rapor SD/VKİ açıkça yazılmamışsa
            # 'malnütrisyon' kelimesi raporda olabilir)
            if any(k in metin_lower for k in (
                'malnütris', 'malnutrisyon', 'yetersiz beslenme'
            )):
                malnutrisyon_var = True
                malnutrisyon_gerekce.append('Malnütrisyon ifadesi raporda mevcut')
        if not malnutrisyon_var:
            ihlaller.append(
                'Pediatrik malnütrisyon koşulu raporda belirtilmemiş '
                '(SD <-2 veya açık ifade)'
            )

    detaylar['malnutrisyon'] = malnutrisyon_var
    detaylar['malnutrisyon_gerekce'] = malnutrisyon_gerekce

    # ── 6. Pediatrik uzman hekim kontrolü ──
    # SUT 4.2.8.A (1.a): "çocuk hastalıkları ve çocuk cerrahi uzman hekimleri
    # tarafından düzenlenen 6 ay süreli uzman hekim raporu"; 2. dönem için
    # çocuk gastroenteroloji/nöroloji/metabolizma/cerrahi/endokrinoloji.
    #
    # ÖNEMLİ: Doktor branşı veritabanında parametrik olarak kayıtlı
    # (DoktorBrans tablosu → 'brans' alanı). Rapor metninde uzman ifadesi
    # tekrarlanmasa bile branş bilgisi zaten biliniyor. Önce parametrik
    # alan kontrol edilir, bulunamazsa metin parse'a düşülür.
    pediatrik_uzmanlar = (
        'çocuk hastalıkları', 'çocuk cerrahi', 'çocuk gastro',
        'çocuk nöroloji', 'çocuk metabolizma', 'çocuk endokrin',
        'cocuk hastaliklari', 'cocuk cerrahi', 'cocuk gastro',
        'cocuk noroloji', 'cocuk metabolizma', 'cocuk endokrin',
        'pediatri',
    )
    eslesen_uzmanlar = []
    uzman_kaynak = None  # 'parametrik' veya 'metin'

    # 6.a — Parametrik doktor branşı (öncelikli kaynak)
    brans_lower = _tr_lower(doktor_brans)
    if brans_lower:
        for u in pediatrik_uzmanlar:
            if u in brans_lower:
                eslesen_uzmanlar.append(u)
                uzman_kaynak = 'parametrik (DoktorBrans)'
                break

    # 6.b — Rapor metni fallback (doktor branşı eşleşmediyse)
    if not eslesen_uzmanlar:
        metin_eslesenler = [u for u in pediatrik_uzmanlar if u in metin_lower]
        if metin_eslesenler:
            eslesen_uzmanlar = metin_eslesenler
            uzman_kaynak = 'rapor metni'

    uzman_var = bool(eslesen_uzmanlar)
    detaylar['uzman_var'] = uzman_var
    detaylar['uzmanlar'] = eslesen_uzmanlar
    detaylar['uzman_kaynak'] = uzman_kaynak
    detaylar['doktor_brans'] = doktor_brans
    if not uzman_var:
        ihlaller.append(
            f'Pediatrik uzman hekim açık belirtilmemiş '
            f"(doktor branşı: '{doktor_brans or 'BOŞ'}', rapor metninde de "
            f'çocuk uzmanı geçmiyor)'
        )

    # ── 7. Günlük kalori karşılaştırması (pediatrik) ──
    # SUT 4.2.8.A (1.c): Raporlarda günlük kalori ihtiyacı ve buna göre
    # belirlenen günlük kullanım miktarı belirtilir. Reçete kalorisi raporda
    # yazan ihtiyacı aşamaz. Pediatrikte 1200 kcal sabit tavanı YOK — DSÖ
    # referans değerleri ve yaşa göre değişir, bu nedenle yalnızca raporda
    # yazan ihtiyaç değeri ile karşılaştırılır.
    if gunluk_kcal is not None and rapor_gunluk_kcal is not None:
        if gunluk_kcal > rapor_gunluk_kcal:
            ihlaller.append(
                f'Reçete günlük kalorisi ({gunluk_kcal:.0f}) raporda yazan '
                f'günlük ihtiyacı ({rapor_gunluk_kcal:.0f}) aşıyor'
            )
        else:
            detaylar['kcal_karsilastirma'] = (
                f'{gunluk_kcal:.0f} kcal/gün ≤ rapor ihtiyaç {rapor_gunluk_kcal:.0f}'
            )

    # ── KARAR ──
    if ihlaller:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f'SUT 4.2.8.A pediatrik UYGUN DEĞİL: {" | ".join(ihlaller)}',
            detaylar=detaylar,
            uyari=' | '.join(uyarilar) if uyarilar else None,
            sut_kurali=sut_kurali,
            aranan_ibare=(
                ' | '.join([f'EKSİK: {a}' for a in eksik_alanlar])
                if eksik_alanlar else 'pediatrik şartlar'
            ),
            bulunan_metin=', '.join(ozel_durumlar) if ozel_durumlar else None,
        )

    if eksik_alanlar:
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f'SUT 4.2.8.A pediatrik ŞÜPHELİ — Raporda eksik alan(lar): '
            f'{", ".join(eksik_alanlar)}',
            detaylar=detaylar,
            uyari='Manuel inceleme — eksik alanlar raporda parse edilemedi',
            sut_kurali=sut_kurali,
        )

    bilgiler = []
    if ozel_durumlar:
        bilgiler.append(
            f'Özel durum: {", ".join(ozel_durumlar)} (malnütrisyon aranmaz)'
        )
    if malnutrisyon_gerekce:
        bilgiler.append(f'Malnütrisyon: {", ".join(malnutrisyon_gerekce)}')
    if urun_eslesti:
        bilgiler.append(f'Ürün eşleşti: {detaylar.get("eslesen_urun")}')
    if eslesen_uzmanlar:
        bilgiler.append(f'Uzman: {eslesen_uzmanlar[0]}')
    if gunluk_kcal:
        bilgiler.append(f'Reçete kcal/gün: {gunluk_kcal:.0f}')
    if rapor_gunluk_kcal:
        bilgiler.append(f'Rapor ihtiyaç: {rapor_gunluk_kcal:.0f}')

    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        f'SUT 4.2.8.A pediatrik UYGUN — {" | ".join(bilgiler)}',
        detaylar=detaylar,
        uyari='Rapor süresi (1. dönem 6 ay uzman / 2. dönem 6 ay alt-uzman / '
              'özel durum 6 ay sağlık kurulu) ve max 30 günlük reçete '
              'dozu manuel kontrol edilmeli',
        sut_kurali=sut_kurali,
    )


def _enteral_yetiskin_kontrol(detaylar, ilac_adi, metin, yas_grubu,
                                urun_eslesti, recetede_aile, doz_uygunsuz,
                                sut_kurali, gunluk_kcal, rapor_gunluk_kcal,
                                doktor_brans=""):
    """SUT 4.2.8.A (2) — Yetişkin hastalar denetimi.

    Akış:
      2.a Malnütrisyon kriterleri (3 hepsi):
            (1) Kilo kaybı >%5 (6 ay) / >%10 (uzun süre) VEYA
                VKİ <22 (70+) / <20 (<70)
            (2) Eşlik eden hastalık / travma
            (3) Besin alımında azalma (1 hafta %50 alım yok / 2 hafta azalma /
                GIS hastalığı)
          + 3 ay sağlık kurulu raporu + max 1200 kcal/gün
      2.b Yatan hasta / kanser / tüp ile beslenme → malnütrisyon aranmaz,
          6 ay sağlık kurulu raporu, kalori tavanı belirtilmemiş
      2.c Raporda zorunlu alanlar:
          ürün adı + günlük kalori ihtiyacı + günlük kullanım miktarı +
          kilo + boy + (varsa) ICD-10; max 30 günlük doz
    """
    metin_lower = (metin or '').lower()
    ihlaller = []
    uyarilar = []

    # ── 1. Reçete dozu rapor dozunu geçemez ──
    if doz_uygunsuz:
        ihlaller.append(
            f'Reçete günlük dozu ({detaylar.get("rec_doz_sayi")}) rapor dozunu '
            f'({detaylar.get("rap_doz_sayi")}) aşıyor'
        )

    # ── 2. Reçetedeki ürün ailesi raporda eşleşti mi? ──
    if not urun_eslesti:
        if recetede_aile:
            ihlaller.append(
                f"Reçetedeki ürün ailesi '{recetede_aile}' rapor metninde geçmiyor"
            )
        else:
            uyarilar.append(
                'Reçetedeki ürün ailesi tespit edilemedi — manuel kontrol'
            )

    # ── 3. Yetişkin özel durumlar (madde 2.b) ──
    ozel_durumlar = _enteral_yetiskin_ozel_durum(metin)
    detaylar['yetiskin_ozel_durumlar'] = ozel_durumlar

    # ── 4. Madde 2.c — Raporda zorunlu alanlar ──
    eksik_alanlar = []
    if detaylar.get('boy') is None:
        eksik_alanlar.append('Boy')
    if detaylar.get('kilo') is None:
        eksik_alanlar.append('Vücut ağırlığı')
    if rapor_gunluk_kcal is None:
        eksik_alanlar.append('Günlük kalori ihtiyacı')

    # ICD-10 kodu (eşlik eden hastalık varsa raporda yazmalı)
    icd_var = bool(re.search(r'\b[A-Z]\d{2}(?:\.\d+)?\b', metin or ''))
    detaylar['icd10_var'] = icd_var
    detaylar['eksik_alanlar'] = eksik_alanlar

    # ── 5. Malnütrisyon kontrolü (özel durum yoksa) ──
    malnutrisyon_var = False
    malnutrisyon_gerekce = []
    if not ozel_durumlar:
        # Kriter 1 — Kilo kaybı VEYA VKİ
        kilo_kaybi = detaylar.get('kilo_kaybi_yuzdesi')
        kilo_kaybi_uygun = (
            kilo_kaybi is not None and kilo_kaybi > 5
        )
        if kilo_kaybi_uygun:
            malnutrisyon_gerekce.append(
                f'%{kilo_kaybi} kilo kaybı (>%5)'
            )

        vki = detaylar.get('vki')
        vki_uygun = False
        if vki is not None:
            if yas_grubu == 'YETISKIN_70_USTU' and vki < 22:
                vki_uygun = True
                malnutrisyon_gerekce.append(
                    f'VKİ {vki} (70+ yaş eşiği <22)'
                )
            elif yas_grubu == 'YETISKIN_70_ALT' and vki < 20:
                vki_uygun = True
                malnutrisyon_gerekce.append(
                    f'VKİ {vki} (70 altı eşiği <20)'
                )

        kriter_1 = kilo_kaybi_uygun or vki_uygun

        # Kriter 2 — Eşlik eden hastalık / travma
        kriter_2 = icd_var or any(k in metin_lower for k in (
            'eşlik eden hastalık', 'eslik eden hastalik',
            'komorbidit', 'travma', 'eşlik eden',
        ))
        if kriter_2:
            malnutrisyon_gerekce.append('Eşlik eden hastalık/travma')

        # Kriter 3 — Besin alımında azalma
        kriter_3 = any(k in metin_lower for k in (
            'besin alımında azalma', 'besin aliminda azalma',
            'enerji ihtiyacının %50', 'enerji ihtiyacinin %50',
            'malabsorpsiyon', 'malabsorbsiyon',
            'emilim bozukluğu', 'emilim bozuklugu',
            'sindirim bozukluğu', 'sindirim bozuklugu',
            'gastrointestinal sistem hastalı', 'gis hastal',
        ))
        if kriter_3:
            malnutrisyon_gerekce.append('Besin alımında azalma')

        # SUT: 3 kriter de gerekli
        if kriter_1 and kriter_2 and kriter_3:
            malnutrisyon_var = True
        else:
            eksik_kriterler = []
            if not kriter_1:
                eksik_kriterler.append(
                    'kilo kaybı %5+ veya yaşa uygun VKİ eşiği'
                )
            if not kriter_2:
                eksik_kriterler.append('eşlik eden hastalık/travma')
            if not kriter_3:
                eksik_kriterler.append('besin alımında azalma')
            ihlaller.append(
                'Yetişkin malnütrisyon kriterleri eksik: '
                + ' & '.join(eksik_kriterler)
            )

        # SUT istisnası: diyetetik tedavi/obezite cerrahisi sonucu kilo kayıpları
        if detaylar.get('diyetetik_obezite_kilo_kaybi'):
            ihlaller.append(
                'SUT istisnası: Diyetetik tedavi/obezite cerrahisi sonucu '
                'kilo kayıpları malnütrisyon değildir'
            )

    detaylar['malnutrisyon'] = malnutrisyon_var
    detaylar['malnutrisyon_gerekce'] = malnutrisyon_gerekce

    # ── 6. Sağlık kurulu raporu + doktor branşı ──
    saglik_kurulu = detaylar.get('saglik_kurulu_raporu')
    if not saglik_kurulu:
        uyarilar.append(
            'Rapor "sağlık kurulu raporu" olarak metinden doğrulanamadı '
            '(SUT yetişkin için sağlık kurulu zorunlu)'
        )
    # Doktor branşı (parametrik) — yetişkinde uzman branş ZORUNLU değil ama
    # bilgilendirme amaçlı kaydedilir. Sağlık kurulu raporunda zaten birden
    # fazla branş bulunur.
    detaylar['doktor_brans'] = doktor_brans

    # ── 7. Günlük kalori karşılaştırmaları ──
    # 7.a — Yetişkin malnütrisyon: max 1200 kcal/gün
    if (not ozel_durumlar and gunluk_kcal is not None
            and gunluk_kcal > 1200):
        ihlaller.append(
            f'Yetişkin malnütrisyon günlük kalori tavanı 1200 kcal aşılıyor: '
            f'{gunluk_kcal:.0f} kcal/gün'
        )

    # 7.b — Reçete kalorisi raporda yazan ihtiyacı aşamaz
    if gunluk_kcal is not None and rapor_gunluk_kcal is not None:
        if gunluk_kcal > rapor_gunluk_kcal:
            ihlaller.append(
                f'Reçete günlük kalorisi ({gunluk_kcal:.0f}) raporda yazan '
                f'ihtiyacı ({rapor_gunluk_kcal:.0f}) aşıyor'
            )

    # ── KARAR ──
    if ihlaller:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f'SUT 4.2.8.A yetişkin UYGUN DEĞİL: {" | ".join(ihlaller)}',
            detaylar=detaylar,
            uyari=' | '.join(uyarilar) if uyarilar else None,
            sut_kurali=sut_kurali,
            aranan_ibare=(
                ' | '.join([f'EKSİK: {a}' for a in eksik_alanlar])
                if eksik_alanlar else 'yetişkin şartlar'
            ),
            bulunan_metin=', '.join(ozel_durumlar) if ozel_durumlar else None,
        )

    if eksik_alanlar:
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f'SUT 4.2.8.A yetişkin ŞÜPHELİ — Raporda eksik alan(lar): '
            f'{", ".join(eksik_alanlar)}',
            detaylar=detaylar,
            uyari=(' | '.join(uyarilar) if uyarilar else
                   'Manuel inceleme — eksik alanlar raporda parse edilemedi'),
            sut_kurali=sut_kurali,
        )

    bilgiler = []
    if ozel_durumlar:
        bilgiler.append(
            f'Özel durum: {", ".join(ozel_durumlar)} (malnütrisyon aranmaz)'
        )
    if malnutrisyon_gerekce:
        bilgiler.append(f'Malnütrisyon: {"; ".join(malnutrisyon_gerekce)}')
    if urun_eslesti:
        bilgiler.append(f'Ürün eşleşti: {detaylar.get("eslesen_urun")}')
    if gunluk_kcal:
        bilgiler.append(f'Reçete kcal/gün: {gunluk_kcal:.0f}')
    if rapor_gunluk_kcal:
        bilgiler.append(f'Rapor ihtiyaç: {rapor_gunluk_kcal:.0f}')

    son_uyari = ('Rapor süresi (3 ay sağlık kurulu / özel durum 6 ay) ve '
                 'max 30 günlük reçete dozu manuel kontrol edilmeli')
    if uyarilar:
        son_uyari = ' | '.join(uyarilar) + ' | ' + son_uyari

    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        f'SUT 4.2.8.A yetişkin UYGUN — {" | ".join(bilgiler)}',
        detaylar=detaylar,
        uyari=son_uyari,
        sut_kurali=sut_kurali,
    )


def _enteral_beslenme_sut_4_2_8_a_kontrol(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.8.A — Enteral beslenme ürünleri tam kontrolü.

    Pediatrik (yaş < 18) ve yetişkin için ayrı algoritma çalıştırır.

    Kontrol edilen kurallar:
      1. Reçetedeki mama ticari ismi raporda olmalı
      2. Reçete dozu rapor dozunu geçemez
      3. Toplam kalori günlük gereken kaloriyi geçemez (yetişkin 1200 kcal
         tavanı + raporda yazan günlük ihtiyaç)
      4. Malnütrisyon tanımı raporda belirtilmeli (kriterler parse edilir)
      5. Çoklu mama toplam kalori kontrolü → GUI tarafında Faz 2'de yapılır
         (bu fonksiyon tek-satır kontrolü yapar)

    NOT: 5. madde (çoklu mama toplam kcal) GUI'de
    `_enteral_kontrol_baslat`'ın 2. fazında değerlendirilir; bu fonksiyon
    tek satır için karar verir.
    """
    sut_kurali = 'SUT 4.2.8.A — Enteral beslenme ürünleri'
    detaylar = {'alt_kategori': 'ENTERAL_BESLENME', 'sut': '4.2.8.A'}

    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    yas_str = str(ilac_sonuc.get('hasta_yasi') or '').strip()

    metin = _tum_metinleri_birlesir(ilac_sonuc)
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    birlesik_metin = (metin or '') + ' ' + (teshis_metin or '')

    detaylar['rapor_kodu'] = rapor_kodu
    detaylar['ilac_adi'] = ilac_adi

    # ── 0. Rapor zorunlu ──
    if not rapor_kodu:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            'SUT 4.2.8.A: Enteral beslenme RAPORSUZ — sağlık kurulu / uzman '
            'hekim raporu zorunlu',
            detaylar=detaylar,
            uyari='Pediatrik: 6 ay uzman hekim raporu / Yetişkin: 3 ay '
                  'sağlık kurulu raporu (özel durumlarda 6 ay)',
            sut_kurali=sut_kurali, aranan_ibare='rapor (zorunlu)',
        )

    # ── 1. Ürün adı eşleştirme (rapor metni vs reçete adı) ──
    urun_eslesti, eslesen_urun, recetede_aile = _enteral_rapor_urun_adi_eslestir(
        ilac_adi, birlesik_metin
    )
    detaylar['urun_eslesti'] = urun_eslesti
    detaylar['eslesen_urun'] = eslesen_urun
    detaylar['recetede_urun_ailesi'] = recetede_aile

    # ── 2. Reçete dozu vs rapor dozu ──
    rec_doz_sayi = ilac_sonuc.get('rec_doz_sayi')
    rap_doz_sayi = ilac_sonuc.get('rap_doz_sayi')
    doz_uygunsuz = False
    try:
        rec_n = float(rec_doz_sayi) if rec_doz_sayi is not None else 0.0
        rap_n = float(rap_doz_sayi) if rap_doz_sayi is not None else 0.0
        if rec_n > 0 and rap_n > 0 and rec_n > rap_n:
            doz_uygunsuz = True
    except (TypeError, ValueError):
        pass
    detaylar['rec_doz_sayi'] = rec_doz_sayi
    detaylar['rap_doz_sayi'] = rap_doz_sayi
    detaylar['doz_uygunsuz'] = doz_uygunsuz

    # ── 3. Kalori hesabı (tek satır) ──
    kcal_bilgi = _enteral_kcal_dozaj_parse(ilac_adi)
    detaylar['kcal_bilgi'] = kcal_bilgi

    gunluk_kcal = None
    recete_doz_dict = ilac_sonuc.get('recete_doz')
    gunluk_doz_input = None
    if isinstance(recete_doz_dict, dict):
        gunluk_doz_input = recete_doz_dict.get('gunluk_doz')
    if gunluk_doz_input is None:
        gunluk_doz_input = rec_doz_sayi
    if 'kcal_birim' in kcal_bilgi and gunluk_doz_input:
        try:
            gunluk_kcal = float(gunluk_doz_input) * float(kcal_bilgi['kcal_birim'])
        except (TypeError, ValueError):
            pass
    detaylar['gunluk_kcal'] = gunluk_kcal
    detaylar['gunluk_doz'] = gunluk_doz_input

    # ── 4. Raporda yazan günlük kalori ihtiyacı ──
    rapor_gunluk_kcal = _enteral_gunluk_kcal_ihtiyaci_parse(birlesik_metin)
    detaylar['rapor_gunluk_kcal_ihtiyaci'] = rapor_gunluk_kcal

    # ── 5. Metin parse'ları (boy/kilo/VKİ/SD/kilo kaybı/sağlık kurulu/diyetetik) ──
    detaylar['boy'] = _enteral_boy_parse(birlesik_metin)
    detaylar['kilo'] = _enteral_kilo_parse(birlesik_metin)
    detaylar['vki'] = _enteral_vki_parse(birlesik_metin)
    detaylar['kilo_kaybi_yuzdesi'] = _enteral_kilo_kaybi_yuzdesi_parse(
        birlesik_metin)
    detaylar['sd'] = _enteral_sd_parse(birlesik_metin)
    detaylar['saglik_kurulu_raporu'] = _enteral_saglik_kurulu_raporu_mu(
        birlesik_metin)
    detaylar['diyetetik_obezite_kilo_kaybi'] = (
        _enteral_diyetetik_obezite_disi_kontrolu(birlesik_metin)
    )

    # VKİ hesaplama (boy + kilo varsa, VKİ açıkça yazılmamışsa)
    if (detaylar['vki'] is None and detaylar['boy']
            and detaylar['kilo']):
        boy_m = detaylar['boy'] / 100.0
        if boy_m > 0:
            detaylar['vki'] = round(detaylar['kilo'] / (boy_m ** 2), 1)
            detaylar['vki_hesaplandi'] = True

    # ── 6. Yaş grubu + dallanma ──
    yas_grubu = _enteral_yas_grubu(yas_str)
    detaylar['yas_grubu'] = yas_grubu
    detaylar['yas'] = yas_str

    # Doktor branşı (parametrik, DoktorBrans tablosundan) — uzman kontrolü
    # için raporun metninde tekrar geçmesi gerekmez.
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').strip()
    detaylar['doktor_brans'] = doktor_brans

    if yas_grubu in ('PEDIATRIK_5_ALT', 'PEDIATRIK_5_USTU'):
        return _enteral_pediatrik_kontrol(
            detaylar, ilac_adi, birlesik_metin, yas_grubu,
            urun_eslesti, recetede_aile, doz_uygunsuz, sut_kurali,
            doktor_brans=doktor_brans,
            gunluk_kcal=gunluk_kcal,
            rapor_gunluk_kcal=rapor_gunluk_kcal,
        )
    if yas_grubu in ('YETISKIN_70_ALT', 'YETISKIN_70_USTU'):
        return _enteral_yetiskin_kontrol(
            detaylar, ilac_adi, birlesik_metin, yas_grubu,
            urun_eslesti, recetede_aile, doz_uygunsuz, sut_kurali,
            gunluk_kcal, rapor_gunluk_kcal,
            doktor_brans=doktor_brans,
        )

    # Yaş bilinmiyor → ŞÜPHELİ
    return KontrolRaporu(
        KontrolSonucu.KONTROL_EDILEMEDI,
        'SUT 4.2.8.A: Hasta yaşı belirsiz, pediatrik/yetişkin algoritması '
        'seçilemedi',
        detaylar=detaylar,
        uyari='Hasta yaşı reçete metadata\'sından okunamadı — manuel kontrol',
        sut_kurali=sut_kurali,
    )


def kontrol_enteral_beslenme(ilac_sonuc: Dict) -> KontrolRaporu:
    """Public wrapper — Enteral beslenme solüsyonları SUT 4.2.8.A denetimi.

    Yeni algoritmaya yönlendirir (`_enteral_beslenme_sut_4_2_8_a_kontrol`):
      1. Reçetedeki mama ticari ismi raporda mı?
      2. Reçete dozu ≤ rapor dozu mu?
      3. Toplam kalori ≤ günlük ihtiyaç ve ≤ 1200 kcal (yetişkin malnütrisyon)?
      4. Malnütrisyon tanımı raporda belirtilmiş mi? (SD/VKİ/kilo kaybı kriterleri)
      5. Çoklu mama toplam kcal kontrolü → GUI Faz 2'de değerlendirilir.

    Eski `_enteral_beslenme_detayli_kontrol` legacy olarak korunur
    (KATEGORI_KONTROL_FONKSIYONU dispatcher'ı hâlâ onu kullanıyor).
    """
    return _enteral_beslenme_sut_4_2_8_a_kontrol(ilac_sonuc)


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


def _esa_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin, teshis_metin="",
                          ilac_sonuc=None):
    """SUT 4.2.9.A — ESA (Eritropoietin/Darbepoetin/Roksadustat) detaylı kontrol.

    Kapsanan ilaçlar (etken madde bazında):
      • Epoetin alfa: EPREX, EPOBEL, ABSEAMED, BINOCRIT, HEMAX, RETACRIT
      • Epoetin beta: NEORECORMON, RECOSET
      • Darbepoetin alfa: ARANESP, DYNEPO
      • Metoxi-PEG-epoetin beta: MIRCERA
      • Biyobenzerler: BIOPOIN, SILAPO
      • Roksadustat (sadece KBY)

    Endikasyonlar (SUT 4.2.9.A):
      1. Kronik böbrek yetmezliği ile ilişkili anemi (4.2.9.A-1)
      2. Myelodisplastik sendrom (4.2.9.A-2) — sadece eritropoietin alfa-beta

    Reçeteleme şartları (KBY — 4.2.9.A-1):
      • Uzman raporu ZORUNLU (6 ay):
          – Nefroloji / İç Hastalıkları / Çocuk Sağlığı / Diyaliz sertifikalı
      • Lab değerleri (raporda VEYA 217 kodu ile reçete açıklamasında):
          – Hb < 10 g/dL → ESA başlama
          – Hb hedef: 11-12 g/dL (idame)
          – Hb > 12 → tedavi kesilir
          – TSAT ≥ %20 ve/veya Ferritin ≥ 100 µg/L → ESA başlanabilir
            (en az BİRİ eşik üstünde olmalı — "ve/veya" kuralı)
          – Hem TSAT < %20 hem Ferritin < 100 → önce demir tedavisi
      • Tetkik takibi: hemodiyaliz 3 ayda bir, periton 4 ayda bir
      • Tetkik tarihi reçete veya raporda belirtilir

    217 Uyarı Kodu:
      Hekim "Bu hastada lab değerlerini reçete açıklamasına yazdım" beyanıdır.
      Reçete sistemine 217 girilirse, lab değerleri reçete veya E-Reçete
      açıklamasında bulunmalı. Bu fonksiyon kaynak öncelik sırasıyla bunları
      arar (reçete açıklaması → E-Reçete açıklaması → rapor metni).

    Karar ağacı (SUT 4.2.9.A-1 ve/veya kuralı):
      RAPOR YOK                              → UYGUNSUZ (raporsuz ESA yasak)
      Kriter ihlali (Hb>12 veya hem TSAT<20 hem Ferritin<100) → UYGUNSUZ
      217 var, Hb yazılmış, (Ferritin VEYA TSAT) yazılmış uygun → UYGUN
      217 var, Ferritin VE TSAT ikisi de yok → UYGUNSUZ (en az biri gerekli)
      217 yok, Hb ve (Ferritin VEYA TSAT) raporda var → UYGUN (kriterlere göre)
      217 yok, lab değerleri eksik          → UYGUNSUZ

    Returns: KontrolRaporu
    """
    sut_kurali = 'SUT 4.2.9.A-1 — ESA: Hb + (TSAT≥%20 ve/veya Ferritin≥100) | 217 kodu reçete açıklamasında değerlendirme'
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

    # ── 217 uyarı kodu kontrolü ──
    # Medula reçetelerinde uyarı kodları ayrı bir UI alanında tutulur (uyari_kodlari
    # listesi: [{kod: "217", aciklama: "...", ilac_adi: "..."}, ...]).
    # 217 kodu hekimin "TSAT/Ferritin değerlerini açıklamaya yazdım" beyanıdır.
    # Sistem 217 görünce: önce reçete açıklamasından (form1:tableEx1), sonra
    # E-Reçete Görüntüle ekranındaki metinden (recete_tarama.py eagerly çeker)
    # değerleri parse edip SUT kriterlerine göre validate eder.
    aciklamalar_listesi = []
    uyari_kodlari = []
    erecete_metni = ''
    if isinstance(ilac_sonuc, dict):
        aciklamalar_listesi = (ilac_sonuc.get('recete_aciklamalari') or []) + \
                               (ilac_sonuc.get('_recete_aciklamalari') or [])
        uyari_kodlari = ilac_sonuc.get('_uyari_kodlari') or ilac_sonuc.get('uyari_kodlari') or []
        erecete_metni = (ilac_sonuc.get('_erecete_aciklama_metni') or '').strip()
        erecete_listesi = ilac_sonuc.get('_erecete_aciklama_listesi') or []
        if erecete_listesi:
            erecete_metni = (erecete_metni + ' ' + ' '.join(erecete_listesi)).strip()
    aciklama_metni = ' '.join(aciklamalar_listesi)

    # 217'yi öncelikle uyarı kodları listesinde ara (Medula'nın asıl tuttuğu yer);
    # ek olarak metinde de tara (geçmiş entegrasyonlar açıklamaya yazmış olabilir).
    has_217 = False
    kod_217_kaynak = None
    ilac_eslesti = False
    for uk in uyari_kodlari:
        if str(uk.get('kod', '')).strip() == '217':
            has_217 = True
            uk_ilac = (uk.get('ilac_adi') or '').upper()
            if uk_ilac and (uk_ilac in ilac_adi or ilac_adi in uk_ilac):
                ilac_eslesti = True
                kod_217_kaynak = 'uyarı kodları (bu ilaca özel)'
                break
    if has_217 and not kod_217_kaynak:
        kod_217_kaynak = 'uyarı kodları (reçete genelinde)'
    if not has_217:
        if re.search(r'\b217\b', aciklama_metni):
            has_217 = True
            kod_217_kaynak = 'reçete açıklaması (metin)'
        elif re.search(r'\b217\b', birlesik):
            has_217 = True
            kod_217_kaynak = 'genel metin'
    detaylar['kod_217'] = has_217
    detaylar['kod_217_kaynak'] = kod_217_kaynak
    detaylar['kod_217_ilac_eslesti'] = ilac_eslesti

    # ── Sayısal değerler ──
    # 217 varsa kaynak öncelik sırası: reçete açıklaması → E-Reçete açıklama →
    # birleşik metin (rapor + teşhis). 217 yoksa doğrudan birleşik metni tarar.
    hb_kaynak = ferritin_kaynak = tsat_kaynak = None
    hb = ferritin = tsat = None
    hb_ibare = ferritin_ibare = tsat_ibare = ''

    def _lab_kaynaklarda_ara(kaynaklar):
        nonlocal hb, ferritin, tsat, hb_ibare, ferritin_ibare, tsat_ibare
        nonlocal hb_kaynak, ferritin_kaynak, tsat_kaynak
        for kaynak_adi, src in kaynaklar:
            if not src:
                continue
            if hb is None:
                _hb, _ib = _lab_degeri_cek(src, ESA_HB_ANAHTARLARI)
                if _hb is not None:
                    hb, hb_ibare, hb_kaynak = _hb, _ib, kaynak_adi
            if ferritin is None:
                _f, _ib = _lab_degeri_cek(src, ESA_FERRITIN_ANAHTARLARI)
                if _f is not None:
                    ferritin, ferritin_ibare, ferritin_kaynak = _f, _ib, kaynak_adi
            if tsat is None:
                _t, _ib = _lab_degeri_cek(src, ESA_TSAT_ANAHTARLARI)
                if _t is not None:
                    tsat, tsat_ibare, tsat_kaynak = _t, _ib, kaynak_adi

    if has_217:
        _lab_kaynaklarda_ara([
            ('reçete açıklaması', aciklama_metni),
            ('E-Reçete açıklama', erecete_metni),
            ('rapor/teşhis metni', birlesik),
        ])
    else:
        _lab_kaynaklarda_ara([('rapor/teşhis metni', birlesik)])

    # ── Tetkik tarihi (SUT son 1 ay içinde tetkik ister) ──
    tarih_kaynak = aciklama_metni or erecete_metni or birlesik
    tetkik_taze, tetkik_en_yeni, _tetkik_hepsi = _tetkik_tarihi_son_n_gun_mu(tarih_kaynak, max_gun=30)

    detaylar.update({'hb': hb, 'ferritin': ferritin, 'tsat': tsat,
                      'hb_kaynak': hb_kaynak, 'ferritin_kaynak': ferritin_kaynak,
                      'tsat_kaynak': tsat_kaynak,
                      'tetkik_taze': tetkik_taze,
                      'tetkik_en_yeni': str(tetkik_en_yeni) if tetkik_en_yeni else None})

    # ── Uzman branş — SUT 4.2.9.A-1 (KBY): nefroloji, iç hastalıkları,
    # çocuk sağlığı ve hastalıkları, diyaliz sertifikalı uzman hekimler
    # SUT 4.2.9.A-2 (MDS): hematoloji
    uzman_var = any(k in metin_lower for k in ['nefroloji', 'hematoloji', 'onkoloji',
                                                 'iç hastalıkları', 'ic hastaliklari',
                                                 'çocuk sağlığı', 'cocuk sagligi',
                                                 'pediatri', 'diyaliz sertifika'])
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

    # Ferritin / TSAT kontrolü — SUT 4.2.9.A-1: "TSAT ≥ %20 VE/VEYA Ferritin ≥ 100"
    # İkisinden biri eşik üstündeyse demir yeterli sayılır → ESA uygun.
    # Sorun yalnızca: ikisi de eşik altındaysa veya ikisi de yoksa.
    ferritin_ok = ferritin is not None and ferritin >= 100
    tsat_ok = tsat is not None and tsat >= 20
    ferritin_dusuk = ferritin is not None and ferritin < 100
    tsat_dusuk = tsat is not None and tsat < 20

    if ferritin is not None:
        bilgiler.append(f"Ferritin: {ferritin} ng/mL{' ✓' if ferritin_ok else ' (düşük)'}")
    else:
        bilgiler.append("Ferritin: yazılmamış")
    if tsat is not None:
        bilgiler.append(f"TSAT: %{tsat}{' ✓' if tsat_ok else ' (düşük)'}")
    else:
        bilgiler.append("TSAT: yazılmamış")

    # SUT "ve/veya" kuralı: en az birinin eşikte olması yeterli
    if ferritin is not None and tsat is not None:
        if not ferritin_ok and not tsat_ok:
            sorunlar.append(f"Hem Ferritin {ferritin} <100 hem TSAT %{tsat} <%20 — önce demir tedavisi (SUT 4.2.9.A-1)")
    # Tek değer var: o yeterli mi kontrolü
    elif ferritin is not None and not tsat_ok:
        # Sadece ferritin yazılmış, ferritin düşükse → demir tedavisi
        if ferritin_dusuk:
            sorunlar.append(f"Ferritin {ferritin} <100 (TSAT yok) — önce demir tedavisi gerekli olabilir")
    elif tsat is not None and not ferritin_ok:
        if tsat_dusuk:
            sorunlar.append(f"TSAT %{tsat} <%20 (Ferritin yok) — önce demir tedavisi gerekli olabilir")

    # Uzman branş kontrolü
    if not uzman_var:
        bilgiler.append("Uzman branş (Nefroloji/Hematoloji/Onkoloji) raporda açıkça belirtilmemiş")

    # ── Sonuç ──
    if has_217:
        bilgiler.insert(0, f"217 kodu mevcut ({detaylar['kod_217_kaynak']}) — TSAT/Ferritin değerleri reçete açıklamasında aranıyor")
    ozet = " | ".join(bilgiler)
    kaynak_metin = (hb_ibare or ferritin_ibare or tsat_ibare or '')

    # Lab değerleri kriterle çelişiyorsa → UYGUN_DEGIL (217 olsun ya da olmasın)
    if sorunlar:
        baslik = "ESA UYGUN DEĞİL: kriter ihlali"
        if has_217:
            baslik = "ESA UYGUN DEĞİL: 217 kodu beyan edilmiş ama açıklamadaki değerler kriteri ihlal ediyor"
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"{baslik} — {'; '.join(sorunlar)}",
            detaylar=detaylar,
            uyari=f"Lab bilgileri: {ozet}",
            sut_kurali=sut_kurali,
            aranan_ibare='Ferritin>100, TSAT>%20, Hb<12',
            bulunan_metin=kaynak_metin
        )

    # SUT 4.2.9.A-1 "ve/veya" kuralı: TSAT VEYA Ferritin'den en az biri yeterli.
    # Hb hâlâ zorunlu (endikasyon ve doz kararı için).
    demir_var = (ferritin is not None) or (tsat is not None)

    # 217 var → değerler reçete/E-Reçete açıklamasında parse edilmeli
    if has_217:
        # En az biri (Ferritin VEYA TSAT) ve Hb gerekli
        if not demir_var:
            bulundu = []
            if hb is not None: bulundu.append(f"Hb={hb} ({hb_kaynak})")
            bulundu_str = "; ".join(bulundu) if bulundu else "(hiçbir lab değeri parse edilemedi)"

            kaynak_ozet = []
            if aciklama_metni:
                kaynak_ozet.append(f"reçete açıklaması ({len(aciklama_metni)} kr): «{aciklama_metni[:200]}»")
            if erecete_metni:
                kaynak_ozet.append(f"E-Reçete açıklama ({len(erecete_metni)} kr): «{erecete_metni[:300]}»")
            if not kaynak_ozet:
                kaynak_ozet.append("açıklama metni boş — E-Reçete Görüntüle açılamadı")

            tetkik_str = ""
            if tetkik_en_yeni:
                tetkik_str = f" | en yeni tetkik tarihi: {tetkik_en_yeni}"

            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                f"ESA UYGUN DEĞİL: 217 kodu var fakat Ferritin VE TSAT ikisi de açıklamalarda yok (SUT: en az biri gerekli)",
                detaylar=detaylar,
                uyari=(f"SUT 4.2.9.A-1: TSAT ≥ %20 ve/veya Ferritin ≥ 100 → en az biri yazılmalı. "
                       f"Bulunan: {bulundu_str}.{tetkik_str} "
                       f"Kaynaklar: " + " | ".join(kaynak_ozet) +
                       ". Manuel kontrol önerilir."),
                sut_kurali=sut_kurali,
                aranan_ibare="Reçete/E-Reçete açıklamasında ör. 'Ferritin: 250' veya 'TSAT: %25'",
                bulunan_metin=(hb_ibare or '')
            )
        # 217 var + en az bir demir göstergesi (Ferritin VEYA TSAT) açıklamadan okundu
        # + kriter ihlali yok → UYGUN
        uyarilar = []
        if ferritin is not None:
            uyarilar.append(f"Ferritin {ferritin} ng/mL ({ferritin_kaynak})")
        if tsat is not None:
            uyarilar.append(f"TSAT %{tsat} ({tsat_kaynak})")
        if hb is not None:
            uyarilar.append(f"Hb {hb} g/dL ({hb_kaynak})")
            if hb < 10:
                uyarilar.append("Hb < 10 → ESA başlama uygun")
            elif 10 <= hb <= 12:
                uyarilar.append("Hb 10-12 → idame dozu")
        else:
            uyarilar.append("Hb değeri açıklamada bulunamadı")
        if tetkik_taze is False:
            uyarilar.append(f"Tetkik tarihi {tetkik_en_yeni} > 30 gün — SUT son 1 ay ister, manuel kontrol")
        elif tetkik_en_yeni:
            uyarilar.append(f"Tetkik tarihi: {tetkik_en_yeni}")
        if not uzman_var:
            uyarilar.append("Uzman branş raporda açık değil (Nefro/Hema/Onko/İç Hast/Çocuk)")
        # Hangi göstergenin sağlandığını sonuç mesajında net belirt
        sag_mesaj = []
        if ferritin is not None:
            sag_mesaj.append(f"Ferritin: {ferritin}")
        if tsat is not None:
            sag_mesaj.append(f"TSAT: %{tsat}")
        return KontrolRaporu(
            KontrolSonucu.UYGUN,
            f"ESA uygun (rapor {rapor_kodu}, 217 kodu) — {', '.join(sag_mesaj)} (SUT 4.2.9.A-1: ve/veya kuralı)",
            detaylar=detaylar,
            uyari=' | '.join(uyarilar),
            sut_kurali=sut_kurali,
            aranan_ibare='217 kodu + (Ferritin≥100 VEYA TSAT≥%20) (açıklamadan okundu)',
            bulunan_metin=kaynak_metin
        )

    # 217 yok → SUT 4.2.9.A-1 → Hb + (Ferritin VEYA TSAT) raporda olmalı
    eksikler = []
    if hb is None: eksikler.append("Hb")
    if not demir_var: eksikler.append("Ferritin VEYA TSAT (en az biri)")
    if eksikler:
        return KontrolRaporu(
            KontrolSonucu.UYGUN_DEGIL,
            f"ESA UYGUN DEĞİL: ZORUNLU değerler eksik ({', '.join(eksikler)} bulunamadı) ve 217 kodu yok",
            detaylar=detaylar,
            uyari=f"Mevcut: {ozet}. Eksik: {', '.join(eksikler)}. Hekim 217 kodunu reçete açıklamasına girmeli VEYA değerler raporda bulunmalı.",
            sut_kurali=sut_kurali,
            aranan_ibare='Hb + (Ferritin VEYA TSAT) veya 217 kodu + açıklamada değerler'
        )

    # 217 yok ama Hb + (Ferritin VEYA TSAT) raporda var, kriter ihlali yok → UYGUN
    uyarilar = []
    if hb is not None:
        if hb < 10:
            uyarilar.append("Hb < 10 → ESA başlama uygun")
        elif 10 <= hb <= 12:
            uyarilar.append("Hb 10-12 → idame dozu")
    if not uzman_var:
        uyarilar.append("Uzman branş ibaresi raporda açık değil (Nefro/Hema/Onko/İç Hast/Çocuk)")
    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        f"ESA uygun (rapor {rapor_kodu}) — {ozet}",
        detaylar=detaylar,
        uyari=' | '.join(uyarilar) if uyarilar else None,
        sut_kurali=sut_kurali,
        aranan_ibare='Hb + (Ferritin≥100 VEYA TSAT≥%20)',
        bulunan_metin=kaynak_metin
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

    Pragmatik yaklaşım:
    - Kombine etken madde zaten "tek ilaçla yetinilemediği"nin somut göstergesidir
      (hekim mono → kombi geçişi yapmış). Mesaj metninde "monoterapi" geçmesini
      şart koşmak yanlış pozitif üretiyordu (3MDYQQ5 CO-IRDA gibi raporsuz
      kombine reçeteler).
    - rapor_kodu yoksa: Medula raporsuz kabul etmiş → şart kontrolü Medula'da.
    - rapor_kodu 04.05 ise: Antihipertansiyon raporu var, kombi yazılabilir.
    - Diğer rapor kodları: sadece monoterapi ibaresi aranır (eski mantık).
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()

    # 1) RAPORSUZ KOMBİNE — kombine etken madde Medula tarafından kabul edilmiş
    if not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Kombine antihipertansif raporsuz — kombine etken madde monoterapi yetersizliğinin göstergesidir',
            detaylar={'aranan': 'monoterapi', 'bulundu': True,
                      'gerekce': 'kombine_etken_madde'},
            sut_kurali='SUT 4.2.12.B — Kombine reçete = monoterapi yetersiz (örtük)',
            aranan_ibare='Kombine etken madde varlığı (yeterli)'
        )

    # 2) RAPOR KODU 04.05 — Antihipertansiyon raporu mevcut
    if rapor_kodu.startswith('04.05'):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Kombine antihipertansif raporlu — rapor kodu {rapor_kodu}',
            detaylar={'aranan': 'monoterapi', 'bulundu': True,
                      'rapor_kodu': rapor_kodu},
            sut_kurali='SUT 4.2.12.B — Antihipertansiyon raporu (04.05) + kombine ilaç',
            aranan_ibare=f'Rapor kodu {rapor_kodu} + kombine etken madde'
        )

    # 3) Farklı rapor kodu — monoterapi ibaresi aranır
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

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Monoterapi ibaresi bulundu',
            detaylar={'aranan': 'monoterapi', 'bulundu': True},
            sut_kurali='SUT 4.2.12.B — Monoterapi ile kan basıncı kontrol altına alınamamış olmalı',
            aranan_ibare='monoterapi / tek ilaç tedavisi',
            bulunan_metin=_eslesen_parcayi_bul(tum_metin, eslesen_kelime)
        )
    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=f'Monoterapi ibaresi bulunamadı — rapor kodu {rapor_kodu} antihipertansiyon değil',
        detaylar={'aranan': 'monoterapi', 'bulundu': False, 'rapor_kodu': rapor_kodu},
        uyari='RAPOR KONTROLÜ GEREKLİ: Monoterapi ibaresi raporda olmalı',
        sut_kurali='SUT 4.2.12.B — Monoterapi ile kan basıncı kontrol altına alınamamış olmalı',
        aranan_ibare='monoterapi / tek ilaç tedavisi'
    )


# Bilinen Aile Hekimliği tesis kodları (Hastane.HastaneKodu / Medula tesis kodu).
# Yeni kodlar tespit edildikçe buraya eklenir; raporsuz ARB için bu kodda
# yazılmış reçete otomatik olarak aile hekimi yetkisi sayılır.
AILE_HEKIMLIGI_TESIS_KODLARI = frozenset({
    "11349904",  # (eczanenin kayıtlı aile hekimliği tesisi)
})


def kontrol_arb_ek4f_m51(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT EK-4/F Madde 51 (1300/51) — Anjiotensin Reseptör Blokerleri ve Kombinasyonları

    Kapsam:
      İrbesartan, Kandesartan, Losartan, Telmisartan, Valsartan, Olmesartan,
      Eprosartan Mesilat, Rilmeniden, Moksonidin + bunların diğer
      antihipertansiflerle (CCB / ACE-i) kombinasyonları.

    SGK 17.10.2016 ISTISNASI — Diüretik (HCT) kombinasyonları:
      ARB + HCT (hidroklorotiazid) sabit kombinasyonları SGK'nın 17.10.2016
      tarihli resmi duyurusu ile bu kapsamın DIŞINDA tutulmuştur. Birebir
      lafız: "diüretikli kombinasyonların bu kapsamda bulunmadığı". Yani
      raporlu ARB+HCT kombilerinde "monoterapi yetersizliği" ibaresi aranmaz.
      3'lü kombilerde (ARB+CCB+HCT) CCB içerdiği için istisna geçersizdir.

    Kurallar (SUT metni + 17.10.2016 duyurusu):
      1. Mono ARB raporlu: Raporda doz/uygulama planı/süre belirtme zorunluluğu
         BULUNMAMAKTADIR. Rapor yeterlidir.
      2. ARB+HCT kombi raporlu: Diüretik istisnası — rapor yeterli, monoterapi
         ibaresi aranmaz.
      3. ARB+CCB / ARB+ACE / 3'lü kombi raporlu: Hastanın "monoterapi ile kan
         basıncının yeterli oranda kontrol altına alınamadığı" raporda
         belirtilmelidir.
      4. Raporsuz: ARB ve kombinasyonları ayda EN FAZLA 1 KUTU olarak
         AİLE HEKİMLERİNCE reçete edilebilir.

    Karar tablosu:
      RAPORLU + MONO                                  → UYGUN
      RAPORLU + KOMBİ_HCT (sadece ARB+HCT)            → UYGUN (diüretik istisnası)
      RAPORLU + KOMBİ_DIGER + monoterapi ibaresi VAR  → UYGUN
      RAPORLU + KOMBİ_DIGER + monoterapi ibaresi YOK  → ŞÜPHELİ
      RAPORSUZ + aile hekimi + ≤1 kutu                → UYGUN
      RAPORSUZ + (aile hekimi değil) ya da >1 kutu    → UYGUN_DEGIL
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    kurum_adi = (ilac_sonuc.get('kurum_adi') or '').upper()
    tesis_kodu = str(ilac_sonuc.get('tesis_kodu') or '').strip()

    # Kutu sayısı parse — string/float/int gelebilir, virgül/nokta normalize
    kutu_raw = ilac_sonuc.get('kutu_sayisi')
    if kutu_raw is None:
        kutu_raw = ilac_sonuc.get('miktar', '')
    try:
        kutu = float(str(kutu_raw).replace(',', '.')) if str(kutu_raw).strip() else 0.0
    except (ValueError, TypeError):
        kutu = 0.0

    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''

    sut_kurali = 'SUT EK-4/F Madde 51 (1300/51) — ARB ve kombinasyonları'

    # Mono mu kombi mi? Etkin maddede "/" varsa kombinasyon
    is_kombi = ('/' in etkin_madde) or (' VE ' in f' {etkin_madde} ')
    # İlaç adında bilinen kombi ticari isimler de kombi kabul edilir
    KOMBI_TICARI = (
        'EXFORGE', 'SEVIKAR', 'TWYNSTA', 'MICARDISPLUS', 'MICARDIS PLUS',
        'CO-DIOVAN', 'CO-APROVEL', 'CO-OLMETEC', 'HYZAAR', 'KARVEZIDE',
        'COSAAR PLUS', 'FORZATEN', 'TRIVERAM', 'AVALOX',
    )
    if not is_kombi and any(t in ilac_adi for t in KOMBI_TICARI):
        is_kombi = True

    # SGK 17.10.2016 istisnası — ARB + HCT (diüretik) sabit kombinasyonu
    # 1300/51 kapsamı DIŞINDA. Etken madde + ilaç adı tek metin olarak taranır.
    # CCB veya ACE-i de varsa (3'lü) istisna geçerli değil — monoterapi
    # ibaresi aranmaya devam edilir.
    arama = (etkin_madde + ' ' + ilac_adi).upper()
    hct_var = (
        'HIDROKLOROTIAZID' in arama
        or 'HİDROKLOROTİAZİD' in arama
        or 'HIDROKLORTIAZID' in arama
        or 'HYDROCHLOROTHIAZID' in arama
        or 'HCTZ' in arama
        or ' HCT' in (' ' + arama + ' ')
        or '/HCT' in arama
    )
    ccb_var = any(k in arama for k in (
        'AMLODIPIN', 'AMLODIPINE', 'LERKANIDIPIN', 'LERKANIDIPINE',
        'FELODIPIN', 'FELODIPINE', 'NIFEDIPIN', 'NIFEDIPINE',
        'NITRENDIPIN', 'BARNIDIPIN', 'NIKARDIPIN', 'ISRADIPIN',
    ))
    ace_var = any(k in arama for k in (
        'PERINDOPRIL', 'ENALAPRIL', 'LISINOPRIL', 'RAMIPRIL',
        'KAPTOPRIL', 'KAPTOPRİL', 'BENAZEPRIL', 'KILAZAPRIL', 'KİLAZAPRİL',
        'TRANDOLAPRIL', 'KINAPRIL', 'KİNAPRİL', 'FOSINOPRIL', 'FOSİNOPRİL',
        'DELAPRIL', 'MOEKSIPRIL', 'MOEKSİPRİL', 'SPIRAPRIL', 'SPİRAPRİL',
        'IMIDAPRIL', 'İMİDAPRİL', 'ZOFENOPRIL',
    ))
    is_hct_only_kombi = is_kombi and hct_var and not ccb_var and not ace_var

    detaylar = {
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin_madde,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
        'kutu': kutu,
        'tip': ('KOMBI_HCT' if is_hct_only_kombi
                else ('KOMBI' if is_kombi else 'MONO')),
        'hct_var': hct_var,
        'ccb_var': ccb_var,
        'ace_var': ace_var,
    }

    # ── RAPORLU SENARYO ──
    if rapor_kodu:
        if not is_kombi:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'Mono ARB raporlu (rap.kod {rapor_kodu}) — '
                       'doz/uygulama planı/süre belirtme zorunluluğu yok'),
                detaylar=detaylar,
                sut_kurali=sut_kurali,
                aranan_ibare='Mono ARB + rapor varlığı',
            )

        # SGK 17.10.2016 ISTISNASI — ARB + HCT (diüretik) raporlu kombi
        # Diüretikli kombinasyonlar 1300/51 kapsamı dışında; rapor yeterli,
        # monoterapi yetersizliği ibaresi aranmaz.
        if is_hct_only_kombi:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'ARB+HCT (diüretik) kombi raporlu (rap.kod {rapor_kodu}) — '
                       'SGK 17.10.2016 duyurusu: diüretikli kombinasyonlar '
                       '1300/51 kapsamı dışında, monoterapi ibaresi aranmaz'),
                detaylar={**detaylar, 'istisna': 'SGK 17.10.2016 — diüretik kombi'},
                sut_kurali=sut_kurali,
                aranan_ibare='ARB + HCT kombi (SGK 17.10.2016 diüretik istisnası)',
                uyari=('Bilgi: bazı SGK il müdürlükleri istisnayı uygulamayıp '
                       'kesinti yapabilir — bölgesel uygulama farklılığı vardır'),
            )

        # Kombi ARB raporlu (CCB / ACE-i / 3'lü) — monoterapi yetersizliği ibaresi aranır
        # I/İ/ı → i tek-noktaya indirgeme. Üç ayrı yazım sorununu birden çözer:
        #   1. "MONOTERAPIYE" (büyük ASCII I) — eski replace('I','ı') 'monoterapı'
        #      üretip 'monoterapi' eşleşmesini kaybettiriyordu
        #      (memory: project_tg_lab_parse_genislet — aynı kalıp)
        #   2. "monoterapı" (Türkçe imla, sondaki -ı) — küçük ı 'i'ye çevrilmediği
        #      için 'monoterapi' aramasıyla yakalanmıyordu (vaka MUSTAFA BEHREM
        #      3HSM4JG, 2026-05-07)
        #   3. "MONOTERAPİ" (Türkçe büyük İ) — replace('İ','i') ile zaten OK
        ml = (tum_metin.replace('İ', 'i').replace('I', 'i')
                       .replace('ı', 'i').lower())
        mono_ibare_var = False
        eslesen_kelime = ''

        # NOT: Tüm pattern'ler 'i' formunda yazılır; metin de i/ı/I/İ → i
        # normalize'dan geçtiği için "monoterapı" / "MONOTERAPI" / "monoterapi"
        # / "MONOTERAPİ" varyantları hepsi tek pattern ile yakalanır.

        # 1) Tek-anahtar yetersizlik/endikasyon ifadeleri (varlığı yeterli)
        for ibare in (
            'monoterapiye dirençli', 'monoterapiye direncli',
            'monoterapiye yanit',
            'kombine terapi endikasyon', 'kombine tedavi endikasyon',
            'kombine tedavi gerek', 'kombine tedavi şart', 'kombine tedavi sart',
            'kombine tedavi endike', 'kombinasyon tedavi gerek',
            'ikili tedavi gerek', 'üçlü tedavi gerek', 'uclu tedavi gerek',
        ):
            if ibare in ml:
                mono_ibare_var = True
                eslesen_kelime = ibare
                break

        # 2) "monoterapi" kelimesi (SUT lafzında ve hekim raporlarında en sık form)
        if not mono_ibare_var and 'monoterapi' in ml:
            mono_ibare_var = True
            eslesen_kelime = 'monoterapi'

        # 3) Kompozit ifadeler (anchor + yardımcı kelime birlikte)
        if not mono_ibare_var:
            kompozitler = (
                (('tek ilaç', 'tek ilac', 'tek antihipertansif'),
                 ('yeter', 'kontrol', 'sağlanama', 'saglanama',
                  'yanit', 'alinama')),
                (('kan basinci', 'tansiyon'),
                 ('kontrol altina alinama',
                  'yeterli kontrol sağlanama', 'yeterli kontrol saglanama',
                  'kontrol edilemem')),
                (('kombinasyon',),
                 ('gerek', 'şart', 'sart', 'endike')),
                (('yeterli',),
                 ('kontrol sağlanama', 'kontrol saglanama')),
            )
            for anchors, helpers in kompozitler:
                if any(a in ml for a in anchors) and any(h in ml for h in helpers):
                    mono_ibare_var = True
                    eslesen_kelime = next(a for a in anchors if a in ml)
                    break

        if mono_ibare_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'Kombi ARB raporlu (rap.kod {rapor_kodu}) — '
                       'monoterapi yetersizliği ibaresi raporda mevcut'),
                detaylar={**detaylar, 'eslesen_ibare': eslesen_kelime},
                sut_kurali=sut_kurali,
                aranan_ibare='Monoterapi yetersizliği ibaresi (raporda)',
                bulunan_metin=_eslesen_parcayi_bul(tum_metin, eslesen_kelime),
            )

        # İbare yok — kullanıcı kuralı (2026-05-07): kombi raporlu + ibare yok =
        # UYGUN_DEĞİL (eski davranış KONTROL_EDILEMEDI/ŞÜPHELİ idi). SUT EK-4/F
        # m.51 lafzı "raporda belirtilmelidir" der; ibare yoksa şart sağlanmıyor
        # demektir. ARB+HCT (HCT-only kombi) zaten yukarıda istisnaya girip UYGUN
        # döner — buraya gelen yalnızca CCB/ACE-i/3'lü kombilerdir.
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'Kombi ARB raporlu (rap.kod {rapor_kodu}) — '
                   'monoterapi yetersizliği ibaresi raporda bulunamadı'),
            detaylar=detaylar,
            uyari=('SUT EK-4/F m.51: ARB+CCB/ACE-i/3\'lü kombi için raporda '
                   '"monoterapi ile kan basıncı yeterli oranda kontrol altına '
                   'alınamadığı" ibaresi BULUNMALIDIR — yoksa şart sağlanmıyor'),
            sut_kurali=sut_kurali,
            aranan_ibare='monoterapi / tek ilaç yetersiz / kombinasyon endikasyonu',
        )

    # ── RAPORSUZ SENARYO ──
    # Aile hekimi tespiti — 3 yol (herhangi biri yeterli):
    #   1. Doktorun branş listesinde "AİLE HEK..." geçiyor
    #      (DoktorBrans tablosu doktorun TÜM branşlarını döndürür; Pratisyen
    #       hekim Aile Hekimliği Sertifikası almışsa bu listede ek branş
    #       olarak görülür)
    #   2. Reçetenin yazıldığı kurum bir Aile Sağlığı Merkezi (ASM/AHM)
    #      → kurum bazlı yetki, branşı pratisyen olsa bile yeterli
    #   3. Tesis kodu (Hastane.HastaneKodu) bilinen aile hekimliği
    #      kodları listesinde — kurum adı / branş bilinmese bile kesin yetki
    brans_aile_hek = (
        'AILE HEK' in doktor_brans
        or 'AİLE HEK' in doktor_brans
        or 'AİLE HEKİMLİĞİ' in doktor_brans
        or 'AILE HEKIMLIGI' in doktor_brans
    )
    kurum_asm = bool(kurum_adi) and (
        'AILE SAGLIGI' in kurum_adi
        or 'AİLE SAĞLIĞI' in kurum_adi
        or 'AILE SAĞLIĞI' in kurum_adi  # karışık encoding
        or 'AİLE SAGLIGI' in kurum_adi
        or 'AILE HEKIMLIGI' in kurum_adi  # AHM
        or 'AİLE HEKİMLİĞİ' in kurum_adi
        # Tek başına kelime olarak ASM/AHM (yan kelime ile karışmasın)
        or any(tok in kurum_adi.split() for tok in ('ASM', 'AHM'))
    )
    tesis_aile_hek = bool(tesis_kodu) and (
        tesis_kodu in AILE_HEKIMLIGI_TESIS_KODLARI
    )
    aile_hekimi = brans_aile_hek or kurum_asm or tesis_aile_hek

    brans_pratisyen = ('PRATISYEN' in doktor_brans or 'PRATİSYEN' in doktor_brans)

    kutu_asildi = kutu > 1

    detaylar.update({
        'kurum_adi': kurum_adi,
        'tesis_kodu': tesis_kodu,
        'brans_aile_hek': brans_aile_hek,
        'kurum_asm': kurum_asm,
        'tesis_aile_hek': tesis_aile_hek,
        'aile_hekimi': aile_hekimi,
    })

    # Yetkilendirmenin nedenini insan-okur formda topla (mesaj/aranan_ibare için)
    nedenler = []
    if brans_aile_hek:
        nedenler.append('branşta aile hekimliği sertifikası')
    if kurum_asm:
        nedenler.append(f'kurum: {kurum_adi[:50]}')
    if tesis_aile_hek:
        nedenler.append(f'tesis kodu: {tesis_kodu}')
    yetki_kaynagi = ' + '.join(nedenler) if nedenler else ''

    # ── Karar ──
    if aile_hekimi and not kutu_asildi:
        kutu_str = f'{kutu:g}' if kutu else '≤1'
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Raporsuz ARB — aile hekimi yetkisi ({yetki_kaynagi}) '
                   f'+ {kutu_str} kutu (SUT: aile hekimi raporsuz ayda 1 kutu)'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare=('Aile hekimliği sertifikası VEYA ASM kurumu '
                          '+ ayda ≤1 kutu'),
            bulunan_metin=yetki_kaynagi,
        )

    if aile_hekimi and kutu_asildi:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'Raporsuz ARB — aile hekimi yetkisi var ({yetki_kaynagi}) '
                   f'ama {kutu:g} kutu (SUT sınırı: ayda 1 kutu)'),
            detaylar=detaylar,
            uyari='Raporsuz ARB ayda en fazla 1 kutu — fazlası için rapor şart',
            sut_kurali=sut_kurali,
            aranan_ibare='Raporsuz ayda 1 kutu sınırı',
            bulunan_metin=yetki_kaynagi,
        )

    if kutu_asildi:
        # Aile hekimi değil + kutu > 1 → kesin uygunsuz
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'Raporsuz ARB — yazan branş "{doktor_brans or "bilinmiyor"}", '
                   f'kurum "{kurum_adi or "bilinmiyor"}", {kutu:g} kutu '
                   '(SUT: raporsuz sadece aile hekimi + ayda 1 kutu)'),
            detaylar=detaylar,
            uyari='Raporsuz ARB sadece aile hekimi tarafından ve ayda 1 kutu',
            sut_kurali=sut_kurali,
            aranan_ibare='Aile hekimi yetkisi + 1 kutu sınırı',
        )

    # Raporsuz + aile hekimi değil + kutu ≤ 1
    # Pratisyen hekim, sertifikası/ASM kaydı görünmüyor → manuel doğrulama
    if brans_pratisyen:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=(f'Raporsuz ARB — pratisyen hekim '
                   f'(kurum: {kurum_adi or "bilinmiyor"}) — '
                   'aile hekimi sertifikası/ASM kaydı tespit edilemedi'),
            detaylar=detaylar,
            uyari=('Pratisyen hekim aile hekimliği sertifikalı veya ASM\'de '
                   'çalışıyor olabilir — manuel kontrol gerekli'),
            sut_kurali=sut_kurali,
            aranan_ibare='Aile hekimi sertifikası VEYA ASM kurumu',
        )

    # Bilinmeyen branş + raporsuz + 1 kutu — şüpheli
    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=(f'Raporsuz ARB — yazan branş "{doktor_brans or "bilinmiyor"}", '
               f'kurum "{kurum_adi or "bilinmiyor"}" '
               '(SUT: raporsuz reçete sadece aile hekimlerince)'),
        detaylar=detaylar,
        uyari=('SUT EK-4/F M.51: Raporsuz ARB için aile hekimi yetkisi '
               '(branşta sertifika veya ASM kurumu) gerekli'),
        sut_kurali=sut_kurali,
        aranan_ibare='Aile hekimi (sertifika veya ASM kurumu)',
    )


# Hastanın "diğer aktif raporlarında" hangi tanı kategorilerine bakılacağını
# tanımlayan keyword sözlüğü. Her SUT kontrol wrapper'ı kendi ilgi alanını
# parametre olarak verir; karara karışmaz, sadece UYGUN_DEĞİL/ŞÜPHELİ
# sonuçlarda eczacı için bilgi notu olarak rapora yazılır.
_DIGER_RAPOR_KATEGORI_KEYWORDS = {
    'DM':    ['E10', 'E11', 'E12', 'E13', 'E14', 'DIYABET', 'DİYABET',
              'DIABETES', '07.02'],
    'KY':    ['I50', 'KALP YETMEZLI', 'KALP YETMEZLİ', 'HEART FAILURE',
              'KARDIYOMIYOPATI', 'KARDİYOMİYOPATİ', '04.01'],
    'KBH':   ['N18', 'KRONIK BOBREK', 'KRONİK BÖBREK', 'BOBREK YETMEZLI',
              'BÖBREK YETMEZLİ', 'CKD'],
    'HT':    ['I10', 'I11', 'I12', 'I13', 'I15', 'HIPERTANSIYON',
              'HİPERTANSİYON', '04.05'],
    'KAH':   ['I20', 'I21', 'I22', 'I23', 'I24', 'I25', 'KORONER ARTER',
              'ISKEMIK KALP', 'İSKEMİK KALP', '04.02'],
    'INME':  ['I63', 'I64', 'I65', 'I66', 'G45', 'G46', 'ISKEMIK INME',
              'İSKEMİK İNME', 'SEREBROVASKULER', 'SEREBROVASKÜLER'],
    'PAH':   ['I70', 'I73', 'I74', 'PERIFERIK ARTER', 'PERİFERİK ARTER'],
    'LIPID': ['E78', 'HIPERLIPIDEMI', 'HİPERLİPİDEMİ', 'HIPERKOLESTEROL',
              'HİPERKOLESTEROL', '04.08'],
    'KOAH':  ['J44', 'KRONIK OBSTRUKTIF', 'KRONİK OBSTRÜKTİF'],
    'ASTIM': ['J45', 'ASTIM', 'ASTIM BRONŞİT', 'ASTHMA'],
}

_DIGER_RAPOR_KATEGORI_AD = {
    'DM': 'DM', 'KY': 'KY', 'KBH': 'KBH', 'HT': 'HT',
    'KAH': 'KAH', 'INME': 'inme', 'PAH': 'PAH',
    'LIPID': 'hiperlipidemi', 'KOAH': 'KOAH', 'ASTIM': 'astım',
}


def _diger_rapor_notu_genel(diger_icd: List[str],
                              kategoriler: List[str]) -> str:
    """Hastanın diğer aktif raporlarındaki ICD/rapor kodlarından, verilen
    kategorilere ait kayıt varsa eczacıya yönelik bilgi notu döndürür.
    Endikasyon/karar değiştirici DEĞİL — sadece manuel doğrulama bağlamı
    (kullanıcı kuralı 2026-05-07: reçeteye ilintili rapor ana karar; diğer
    raporlardaki uygunluk yalnızca açıklama notu olarak rapora belirtilir).
    """
    if not diger_icd or not kategoriler:
        return ''
    metin = ' | '.join(diger_icd).upper()
    notlar = []
    for kat in kategoriler:
        kws = _DIGER_RAPOR_KATEGORI_KEYWORDS.get(kat, [])
        if not kws:
            continue
        if any(k in metin for k in kws):
            kayit = next((s for s in diger_icd
                          if any(k in s.upper() for k in kws)), None)
            if kayit:
                ad = _DIGER_RAPOR_KATEGORI_AD.get(kat, kat)
                notlar.append(
                    f'Hastanın diğer aktif raporunda {ad} kaydı: {kayit}')
    return ' | '.join(notlar)


def _diger_rapor_notunu_uyariya_ekle(rapor: 'KontrolRaporu',
                                        diger_icd: List[str],
                                        kategoriler: List[str]) -> None:
    """Sonucu UYGUN_DEGIL/KONTROL_EDILEMEDI olan rapora bilgi notunu yerinde
    ekler. UYGUN sonuçlarında dokunmaz."""
    if rapor.sonuc not in (KontrolSonucu.UYGUN_DEGIL,
                            KontrolSonucu.KONTROL_EDILEMEDI):
        return
    not_metni = _diger_rapor_notu_genel(diger_icd, kategoriler)
    if not_metni:
        rapor.uyari = ((rapor.uyari + ' | ') if rapor.uyari else '') + not_metni


def kontrol_diyabet_dpp4_sglt2(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.38 — şart-bazlı raporlama wrapper'ı (CLAUDE.md disiplini).

    İç implementasyon `_kontrol_diyabet_dpp4_sglt2_impl` şart listesini akış
    sırasında doldurur; rapor üretildikten sonra wrapper bu listeyi rapora
    bağlar (sartlar zaten doluysa dokunmaz).

    Reçete bağlamı (rec rap_kod + ilintili rapor metni) ana sonucu belirler.
    Hastanın diğer aktif raporlarındaki ICD'ler (`diger_raporlar_icd`) ana
    karara karışmaz; UYGUN_DEGIL/KONTROL_EDILEMEDI sonuçlarda eczacının
    manuel doğrulamasını kolaylaştırmak için uyarıya bilgi notu eklenir.
    """
    sartlar: List[SartSonuc] = []
    rapor = _kontrol_diyabet_dpp4_sglt2_impl(ilac_sonuc, sartlar)
    if not rapor.sartlar:
        rapor.sartlar = list(sartlar)
    return rapor


def _kontrol_diyabet_dpp4_sglt2_impl(ilac_sonuc: Dict, sartlar: List[SartSonuc]) -> KontrolRaporu:
    """
    SUT 4.2.38 - Diyabet Tedavisinde Kullanılan İlaçlar (Tüm Sınıflar)

    Kapsanan ilaç sınıfları:
      • Biguanidler (metformin)
      • Sülfonilüreler (gliklazid/DIAMICRON, glimepirid/AMARYL, glibenklamid/DIAFORMIN,
        glipizid)
      • Glinidler (repaglinid/NOVONORM, nateglinid/STARLIX)
      • Tiazolidinedionlar (pioglitazon/ACTOS)
      • Alfa-glukozidaz inhibitörleri (akarboz/GLUCOBAY)
      • DPP-4 inhibitörleri (sitagliptin/JANUVIA, vildagliptin/GALVUS,
        saksagliptin/ONGLYZA, linagliptin/TRAJENTA, alogliptin/NESINA)
      • SGLT-2 inhibitörleri (empagliflozin/JARDIANCE, dapagliflozin/FORZIGA,
        kanagliflozin/INVOKANA, ertugliflozin/STEGLATRO)
      • GLP-1 reseptör agonistleri (liraglutid/VICTOZA, semaglutid/OZEMPIC,
        dulaglutid/TRULICITY, eksenatid/BYETTA)
      • İnsülinler (kısa/orta/uzun etkili, kombi)
      • Sabit kombinasyonlar (DPP4+metformin: JANUMET/GALVUSMET; SGLT2+metformin:
        SYNJARDY/XIGDUO; SGLT2+DPP4: GLYXAMBI/QTERN)

    SUT 4.2.38 kuralları (özet):
      (1) Tip 2 DM tanısı zorunlu (insülin için Tip 1/Gestasyonel da uygun).
      (4) DPP-4: Metformin ve/veya sülfonilürelerin maks tolere edilebilir dozlarında
          yeterli glisemik kontrol sağlanamamış hastalarda; endokrinoloji/iç hast.
          uzmanı veya raporu (rapor süresi 2 yıl).
      (6) SGLT-2: aynı glisemik kontrol şartı; endokrinoloji/iç hast. uzmanı VEYA
          raporu (uzman raporsuz da yazabilir). Kalp yetmezliği veya KBH
          endikasyonunda farklı uzmanlar (kardiyoloji/nefroloji/iç hast./aile hek.)
          raporsuz yazabilir. eGFR drug-specific (dapa: 25, empa: 20, cana: 30,
          ertu: 45) altında kontrendike.
      (7) GLP-1 RA: BMI ≥ 30 kg/m² + HbA1c ≥ %7; metformin maks doz şartı;
          endokrinoloji uzmanı raporu (genelde).
      (8) Kombinasyon yasağı: DPP-4 + GLP-1 birlikte ödenmez (aynı inkretin yolağı).
          GLP-1 + SGLT-2 ve DPP-4 + SGLT-2 ayrı ayrı ödenir; sabit kombi haplarında
          (GLYXAMBI/QTERN/STEGLUJAN) istisna.
      Klasik OAD'ler (metformin, sülfonilüre, glinid, akarboz, TZD) ve insülinler
      diyabet tanısı/raporuyla raporsuz da yazılabilir.

    Ek klinik kontroller:
      • Metformin eGFR < 30 ml/dk kontrendike (30-45 doz azalt)
      • Pioglitazon (TZD) kalp yetmezliği (NYHA I-IV) kontrendike
      • SGLT-2 ilaç-spesifik eGFR sınırları (yukarıda)
      • SAXENDA/WEGOVY obezite endikasyonu SGK kapsamı dışı
      • DPP-4/SGLT-2/GLP-1 raporu süresi 2 yıl (ilk reçete + devam reçete)
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor = _tr_lower(ilac_sonuc.get('doktor_uzmanligi'))
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_metin = ' '.join(teshisler).upper() if teshisler else ''
    diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []  # diğer reçete ilaçları (kombinasyon kontrolü)
    diger_ilac_adlari = ' '.join([str(i.get('ad', '') if isinstance(i, dict) else i)
                                   for i in diger_ilaclar]).upper()

    arama_metni = (ilac_adi + ' ' + etkin_madde).upper()

    # ── İLAÇ SINIFI TESPİTİ ────────────────────────────────────────────────
    BIGUANID = ['METFORMIN', 'GLUKOFEN', 'GLIFOR', 'DIAFORMIN', 'GLUCOPHAGE',
                'METFORM', 'MATOFIN']
    SULFONILURE = ['GLIKLAZID', 'GLICLAZID', 'DIAMICRON', 'BETANORM', 'DIAMERID',
                   'GLIMEPIRID', 'AMARYL', 'GLIMAX', 'MERIDIA', 'GLIBEDAL',
                   'GLIBENKLAMID', 'DAONIL', 'GLUKOMID',
                   'GLIPIZID', 'MINIDIAB', 'GLUCOTROL']
    GLINID = ['REPAGLINID', 'NOVONORM', 'NATEGLINID', 'STARLIX']
    TZD = ['PIOGLITAZON', 'ACTOS', 'GLUSTIN', 'PIONORM']
    AKARBOZ = ['AKARBOZ', 'ACARBOSE', 'GLUCOBAY']
    DPP4 = ['SITAGLIPTIN', 'VILDAGLIPTIN', 'SAKSAGLIPTIN', 'LINAGLIPTIN', 'ALOGLIPTIN',
            'JANUVIA', 'GALVUS', 'ONGLYZA', 'TRAJENTA', 'NESINA',
            'JANUMET', 'GALVUSMET', 'KOMBOGLYZE', 'JENTADUETO', 'VIPDOMET']
    SGLT2 = ['EMPAGLIFLOZIN', 'DAPAGLIFLOZIN', 'KANAGLIFLOZIN', 'CANAGLIFLOZIN',
             'ERTUGLIFLOZIN',
             'JARDIANCE', 'FORZIGA', 'FORXIGA', 'INVOKANA', 'STEGLATRO']
    SGLT2_KOMBI = ['SYNJARDY', 'XIGDUO', 'VOKANAMET', 'SEGLUROMET',  # SGLT2+metformin
                   'GLYXAMBI', 'QTERN', 'STEGLUJAN']                  # SGLT2+DPP4
    GLP1 = ['LIRAGLUTID', 'SEMAGLUTID', 'DULAGLUTID', 'EKSENATID', 'EXENATID',
            'LIKSISENATID', 'LIXISENATID',
            'VICTOZA', 'OZEMPIC', 'RYBELSUS', 'TRULICITY', 'BYETTA', 'BYDUREON',
            'SAXENDA', 'LYXUMIA', 'WEGOVY']
    INSULIN = ['INSULIN', 'INSÜLIN', 'INSULAT', 'GLARGIN', 'DETEMIR', 'DEGLUDEC',
               'ASPART', 'LISPRO', 'GLULIZIN',
               'LANTUS', 'TOUJEO', 'TRESIBA', 'LEVEMIR', 'BASAGLAR', 'ABASAGLAR',
               'NOVORAPID', 'HUMALOG', 'APIDRA', 'ACTRAPID', 'HUMULIN',
               'NOVOMIX', 'RYZODEG', 'XULTOPHY', 'SOLIQUA']
    # Madde 1 (tüm hekim, raporsuz): insan insülini
    INSAN_INSULIN = ['HUMULIN', 'ACTRAPID', 'INSULATARD', 'INSUMAN', 'MIXTARD']
    # Madde 3 (endokrin/iç hast./çocuk/kardiyolog uzmanı veya rapor): analog insülinler
    ANALOG_INSULIN = ['LANTUS', 'GLARGIN', 'TOUJEO', 'TRESIBA', 'DEGLUDEC',
                      'LEVEMIR', 'DETEMIR', 'BASAGLAR', 'ABASAGLAR',
                      'NOVORAPID', 'ASPART', 'HUMALOG', 'LISPRO',
                      'APIDRA', 'GLULIZIN', 'NOVOMIX', 'HUMALOGMIX']
    # Madde 3b özel: degludek+aspart sağlık kurulu raporu zorunlu
    INSULIN_DEGLUDEK_ASPART = ['RYZODEG']
    # GLP-1 + insülin sabit kombiler (özel maddeler)
    INSULIN_GLP1_KOMBI = ['XULTOPHY', 'SOLIQUA']  # SOLIQUA → madde 7
    # Saksagliptin 2,5mg / alogliptin 12,5mg → KBH-yalnızca
    DPP4_DUSUK_DOZ_KBH = {
        'saksagliptin_2_5': re.compile(r'(?:saksagliptin|onglyza)[^a-z0-9]{0,30}2[.,]5\s*mg', re.IGNORECASE),
        'alogliptin_12_5': re.compile(r'(?:alogliptin|nesina)[^a-z0-9]{0,30}12[.,]5\s*mg', re.IGNORECASE),
    }

    is_biguanid = any(k in arama_metni for k in BIGUANID)
    is_sulfonilure = any(k in arama_metni for k in SULFONILURE)
    is_glinid = any(k in arama_metni for k in GLINID)
    is_tzd = any(k in arama_metni for k in TZD)
    is_akarboz = any(k in arama_metni for k in AKARBOZ)
    is_dpp4 = any(k in arama_metni for k in DPP4)
    is_sglt2 = any(k in arama_metni for k in SGLT2)
    is_sglt2_kombi = any(k in arama_metni for k in SGLT2_KOMBI)
    is_glp1 = any(k in arama_metni for k in GLP1)
    is_insulin = any(k in arama_metni for k in INSULIN)

    # Kombi ilaç tespiti — doğru sınıfı işaretle
    if is_sglt2_kombi:
        is_sglt2 = True  # SGLT2 kombi de SGLT2 kuralına tabi
        if any(k in arama_metni for k in ['GLYXAMBI', 'QTERN', 'STEGLUJAN']):
            is_dpp4 = True  # SGLT2+DPP4 kombi
        else:
            is_biguanid = True  # SGLT2+metformin kombi
    DPP4_METFORMIN_KOMBI = ['JANUMET', 'GALVUSMET', 'GALVUS MET', 'KOMBOGLYZE',
                             'JENTADUETO', 'VIPDOMET', 'LINATIN MET',
                             'TRAJENTA DUO', 'LINATIN-MET', 'VILDEGA PLUS',
                             'VILDEGA MET']
    if any(k in arama_metni for k in DPP4_METFORMIN_KOMBI):
        is_dpp4 = True
        is_biguanid = True

    # Etkin madde tabanlı sabit kombi tespiti (ticari adı listede olmasa bile)
    # Örn. "LINAGLIPTIN+METFORMIN", "VILDAGLIPTIN+METFORMİN"
    if 'METFORMIN' in arama_metni and any(k in arama_metni for k in
            ['SITAGLIPTIN', 'VILDAGLIPTIN', 'SAKSAGLIPTIN', 'LINAGLIPTIN', 'ALOGLIPTIN']):
        is_dpp4 = True
        is_biguanid = True
    if 'METFORMIN' in arama_metni and any(k in arama_metni for k in
            ['DAPAGLIFLOZIN', 'EMPAGLIFLOZIN', 'KANAGLIFLOZIN', 'ERTUGLIFLOZIN']):
        is_sglt2 = True
        is_biguanid = True

    # ── DOKTOR BRANŞ KONTROLÜ ──────────────────────────────────────────────
    doktor_endokrin = any(k in doktor for k in ['endokrin', 'endokrinoloji'])
    doktor_dahiliye = any(k in doktor for k in ['iç hastalık', 'ic hastalik',
                                                  'dahiliye', 'internal'])
    doktor_kardiyolog = 'kardiyolo' in doktor or 'kalp damar' in doktor
    doktor_nefrolog = 'nefrolo' in doktor
    doktor_pediatri = any(k in doktor for k in ['çocuk', 'cocuk', 'pediatri'])
    doktor_aile = 'aile hek' in doktor or 'pratisyen' in doktor or 'genel pratis' in doktor
    # Diyabet endikasyonu için DPP-4/SGLT-2 yazabilen branşlar
    doktor_uygun_dpp4_sglt2 = doktor_endokrin or doktor_dahiliye
    # KY endikasyonunda SGLT-2 yazabilen branşlar (raporsuz)
    doktor_ky_uygun = (doktor_kardiyolog or doktor_dahiliye or
                       doktor_endokrin or doktor_aile)
    # KBH endikasyonunda SGLT-2 yazabilen branşlar (raporsuz)
    doktor_kbh_uygun = (doktor_nefrolog or doktor_dahiliye or
                        doktor_endokrin or doktor_aile)
    # SUT 4.2.38(2) — glinid + diğer OAD kombineleri raporsuz yazabilen uzmanlar
    doktor_glinid_uygun = (doktor_endokrin or doktor_dahiliye or
                           doktor_pediatri or doktor_kardiyolog or doktor_aile)
    # SUT 4.2.38(3) — analog insülin + pioglitazon raporsuz yazabilen uzmanlar
    doktor_analog_tzd_uygun = (doktor_endokrin or doktor_dahiliye or
                                doktor_pediatri or doktor_kardiyolog)

    # ── ENDİKASYON TESPİTİ (Teşhis + tüm metin) ────────────────────────────
    teshis_tum = (teshis_metin + ' ' + tum_metin).upper()
    diyabet_var = any(k in teshis_tum for k in [
        'E10', 'E11', 'E12', 'E13', 'E14',
        'DIYABET', 'DİYABET', 'DIABETES MELLITUS', 'DM',
        'TIP 2', 'TYPE 2', 'TIP 1', 'TYPE 1', 'GESTASYONEL'])
    kalp_yetmezligi = any(k in teshis_tum for k in [
        'I50', 'KALP YETMEZLİĞİ', 'KALP YETMEZLIGI', 'HEART FAILURE',
        'KARDİYOMİYOPATİ', 'KARDIYOMIYOPATI', 'HFrEF', 'HFpEF',
        'KALP YETERSİZLİĞİ', 'KALP YETERSIZLIGI'])
    kbh = any(k in teshis_tum for k in [
        'N18', 'KRONİK BÖBREK', 'KRONIK BOBREK', 'CKD',
        'BÖBREK YETMEZLİĞİ', 'BOBREK YETMEZLIGI', 'BÖBREK YETERSİZLİĞİ',
        'RENAL YETMEZLİK', 'RENAL YETMEZLIK'])
    obezite = any(k in teshis_tum for k in ['E66', 'OBEZITE', 'OBEZİTE', 'OBESITY'])
    # SUT 4.2.38(5)/(7) — eksenatid/SOLIQUA için akut pankreatit anamnezi yasağı
    akut_pankreatit_oykusu = any(k in teshis_tum for k in [
        'K85', 'K86.1', 'AKUT PANKREATIT', 'AKUT PANKREATİT',
        'ACUTE PANCREATITIS',
        'PANKREATIT GEÇİRİL', 'PANKREATIT GECIRIL',
        'PANKREATIT ÖYKÜS', 'PANKREATIT OYKUS'])

    # DPP-4 düşük doz form tespiti (madde 4 — KBH-yalnızca)
    is_saksa_2_5 = bool(DPP4_DUSUK_DOZ_KBH['saksagliptin_2_5'].search(
        ilac_adi + ' ' + etkin_madde + ' ' + tum_metin))
    is_aloglip_12_5 = bool(DPP4_DUSUK_DOZ_KBH['alogliptin_12_5'].search(
        ilac_adi + ' ' + etkin_madde + ' ' + tum_metin))

    # İnsülin alt sınıf tespiti (madde 1 vs 3 ayrımı)
    is_insan_insulin = any(k in arama_metni for k in INSAN_INSULIN)
    is_analog_insulin = any(k in arama_metni for k in ANALOG_INSULIN)
    is_ryzodeg = any(k in arama_metni for k in INSULIN_DEGLUDEK_ASPART)
    is_xultophy = 'XULTOPHY' in arama_metni
    is_soliqua = 'SOLIQUA' in arama_metni

    # ── İBARE ARAMA (Glisemik kontrol, HbA1c, BMI) ─────────────────────────
    metformin_ib = _turkce_ara(tum_metin, 'metformin')
    sulfonilure_ib = (_turkce_ara(tum_metin, 'sülfonilüre') or
                      _turkce_ara(tum_metin, 'sulfonilure'))
    glisemik_ib = (_turkce_ara(tum_metin, 'glisemik') or
                   _turkce_ara(tum_metin, 'kan şekeri') or
                   'hba1c' in tum_metin.lower() or
                   _turkce_ara(tum_metin, 'a1c'))
    yetersiz_ib = (_turkce_ara(tum_metin, 'sağlanama') or
                   _turkce_ara(tum_metin, 'saglanama') or
                   _turkce_ara(tum_metin, 'yetersiz') or
                   _turkce_ara(tum_metin, 'kontrol altına alınama') or
                   _turkce_ara(tum_metin, 'kontrol altina alinama') or
                   _turkce_ara(tum_metin, 'regüle edileme') or
                   _turkce_ara(tum_metin, 'regule edileme') or
                   _turkce_ara(tum_metin, 'kontrolsüz') or
                   _turkce_ara(tum_metin, 'kontrolsuz') or
                   _turkce_ara(tum_metin, 'tedaviye rağmen') or
                   _turkce_ara(tum_metin, 'tedaviye ragmen') or
                   _turkce_ara(tum_metin, 'optimal kontrol') or
                   _turkce_ara(tum_metin, 'kombinasyon'))
    maks_doz_ib = (_turkce_ara(tum_metin, 'maksimum') or
                   _turkce_ara(tum_metin, 'maks tolere') or
                   _turkce_ara(tum_metin, 'tolere edilebil'))

    # HbA1c değeri (örn. "HbA1c: 8.2", "HbA1c %9")
    hba1c_deger = None
    m_hba1c = re.search(r'hba1c[^0-9]{0,10}(\d+[.,]?\d*)', tum_metin, re.IGNORECASE)
    if m_hba1c:
        try:
            hba1c_deger = float(m_hba1c.group(1).replace(',', '.'))
        except (ValueError, IndexError):
            pass

    # BMI / VKİ değeri
    bmi_deger = None
    m_bmi = re.search(r'(?:bmi|vki|vk[ıi])[^0-9]{0,10}(\d+[.,]?\d*)',
                      tum_metin, re.IGNORECASE)
    if m_bmi:
        try:
            bmi_deger = float(m_bmi.group(1).replace(',', '.'))
        except (ValueError, IndexError):
            pass

    # eGFR değeri
    egfr_deger = None
    m_egfr = re.search(r'(?:egfr|gfr)[^0-9]{0,10}(\d+[.,]?\d*)',
                       tum_metin, re.IGNORECASE)
    if m_egfr:
        try:
            egfr_deger = float(m_egfr.group(1).replace(',', '.'))
        except (ValueError, IndexError):
            pass

    # Hasta yaşı (ilac_sonuc'tan ya da metinden)
    hasta_yasi = None
    hy_raw = ilac_sonuc.get('hasta_yasi') or ilac_sonuc.get('yas')
    if hy_raw:
        try:
            hasta_yasi = int(re.sub(r'[^0-9]', '', str(hy_raw)) or 0) or None
        except (ValueError, TypeError):
            pass
    if hasta_yasi is None:
        m_yas = re.search(r'(?:yaş|yasi|yas)[^0-9]{0,8}(\d{1,3})',
                          tum_metin, re.IGNORECASE)
        if m_yas:
            try:
                yas_kandi = int(m_yas.group(1))
                if 0 < yas_kandi < 120:
                    hasta_yasi = yas_kandi
            except (ValueError, IndexError):
                pass

    pediatri_hasta = (hasta_yasi is not None and hasta_yasi < 18)
    yasli_hasta = (hasta_yasi is not None and hasta_yasi >= 75)

    # Reçete dozu (mg/gün) — sülfonilüre/DPP-4 doz limit kontrolü için
    recete_dozu = None
    rd_raw = ilac_sonuc.get('recete_dozu') or ilac_sonuc.get('doz')
    if rd_raw:
        try:
            m_rd = re.search(r'(\d+(?:[.,]\d+)?)', str(rd_raw))
            if m_rd:
                recete_dozu = float(m_rd.group(1).replace(',', '.'))
        except (ValueError, TypeError):
            pass

    # SGLT-2 ilaç-spesifik eGFR sınırları (diyabet endikasyonu için)
    sglt2_egfr_min_diyabet = None
    sglt2_etken = None
    if any(k in arama_metni for k in ['DAPAGLIFLOZIN', 'FORZIGA', 'FORXIGA',
                                       'XIGDUO', 'QTERN']):
        sglt2_egfr_min_diyabet = 25  # dapagliflozin diyabet ≥ 25
        sglt2_etken = 'dapagliflozin'
    elif any(k in arama_metni for k in ['EMPAGLIFLOZIN', 'JARDIANCE', 'SYNJARDY',
                                         'GLYXAMBI']):
        sglt2_egfr_min_diyabet = 30  # empagliflozin diyabet ≥ 30 (KY/KBH ≥ 20)
        sglt2_etken = 'empagliflozin'
    elif any(k in arama_metni for k in ['KANAGLIFLOZIN', 'CANAGLIFLOZIN',
                                         'INVOKANA', 'VOKANAMET']):
        sglt2_egfr_min_diyabet = 30  # canagliflozin ≥ 30
        sglt2_etken = 'canagliflozin'
    elif any(k in arama_metni for k in ['ERTUGLIFLOZIN', 'STEGLATRO', 'STEGLUJAN',
                                         'SEGLUROMET']):
        sglt2_egfr_min_diyabet = 45  # ertugliflozin ≥ 45 (renal sınırlama daha sıkı)
        sglt2_etken = 'ertugliflozin'

    # Glisemik şart ibaresi (SUT 4.2.38 madde 4/6/7 — DPP-4, SGLT-2, GLP-1 için
    # ZORUNLU): "metformin ve/veya sülfonilürelerin maksimum tolere edilebilir
    # dozlarında yeterli glisemik kontrol sağlanamamıştır" rapor açıklamasında
    # bulunmalı. Sabit kombi (JANUMET/GALVUS MET vb.) tek başına bu ibarenin
    # yerini tutmaz — SGK lafzen rapor metnini arar.
    glisemik_sart_var = (
        (metformin_ib and (sulfonilure_ib or glisemik_ib or yetersiz_ib)) or
        (glisemik_ib and (yetersiz_ib or maks_doz_ib)) or
        (metformin_ib and yetersiz_ib)
    )

    # ── KOMBİNASYON KONTROLÜ ───────────────────────────────────────────────
    diger_dpp4 = any(k in diger_ilac_adlari for k in DPP4) and not is_dpp4
    diger_glp1 = any(k in diger_ilac_adlari for k in GLP1) and not is_glp1
    diger_sglt2 = any(k in diger_ilac_adlari for k in SGLT2 + SGLT2_KOMBI) and not is_sglt2

    # ── Şart-bazlı yapısal raporlama (CLAUDE.md disiplini) ────────────────
    # İlaç sınıfı tespiti
    siniflar = []
    if is_biguanid: siniflar.append("Biguanid")
    if is_sulfonilure: siniflar.append("Sülfonilüre")
    if is_glinid: siniflar.append("Glinid")
    if is_tzd: siniflar.append("TZD/Pioglitazon")
    if is_akarboz: siniflar.append("Akarboz")
    if is_dpp4: siniflar.append("DPP-4")
    if is_sglt2: siniflar.append("SGLT-2")
    if is_glp1: siniflar.append("GLP-1 RA")
    if is_insulin: siniflar.append("İnsülin")
    if siniflar:
        sartlar.append(SartSonuc(
            ad="İlaç sınıfı tespiti",
            durum=SartDurumu.VAR,
            neden=" + ".join(siniflar),
            kaynak="ilac_adi/etken/atc"))
    else:
        sartlar.append(SartSonuc(
            ad="İlaç sınıfı tespiti",
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f"Sınıf belirlenemedi: {ilac_adi or '?'} / {etkin_madde or '?'}",
            kaynak="ilac_adi/etken/atc"))

    # Diyabet tanısı
    if diyabet_var:
        sartlar.append(SartSonuc(
            ad="Diyabet tanısı (E10-E14 / DM)",
            durum=SartDurumu.VAR,
            neden="Teşhis/metin taramasında diyabet ibareleri bulundu",
            kaynak="recete_teshisleri + tum_metin"))
    elif teshisler:
        sartlar.append(SartSonuc(
            ad="Diyabet tanısı (E10-E14 / DM)",
            durum=SartDurumu.YOK,
            neden=f"Teşhislerde diyabet kodu yok: {', '.join(str(t) for t in teshisler[:3])}",
            kaynak="recete_teshisleri"))
    else:
        sartlar.append(SartSonuc(
            ad="Diyabet tanısı (E10-E14 / DM)",
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden="Reçete teşhisleri verisi boş",
            kaynak="recete_teshisleri"))

    # Rapor kodu
    if rapor_kodu:
        sartlar.append(SartSonuc(
            ad="Rapor kodu",
            durum=SartDurumu.VAR,
            neden=str(rapor_kodu),
            kaynak="rap_kod"))
    else:
        sartlar.append(SartSonuc(
            ad="Rapor kodu",
            durum=SartDurumu.YOK,
            neden="Reçete satırında rap_kod boş",
            kaynak="rap_kod"))

    # Doktor branşı
    if doktor:
        if doktor_endokrin:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"endokrinoloji: {doktor}", "doktor_uzmanligi"))
        elif doktor_dahiliye:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"iç hastalıkları: {doktor}", "doktor_uzmanligi"))
        elif doktor_pediatri:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"çocuk sağlığı: {doktor}", "doktor_uzmanligi"))
        elif doktor_kardiyolog:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"kardiyoloji: {doktor}", "doktor_uzmanligi"))
        elif doktor_nefrolog:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"nefroloji: {doktor}", "doktor_uzmanligi"))
        elif doktor_aile:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"aile hek/pratisyen: {doktor}", "doktor_uzmanligi"))
        else:
            sartlar.append(SartSonuc("Doktor branşı", SartDurumu.VAR,
                                     f"diğer: {doktor}", "doktor_uzmanligi"))
    else:
        sartlar.append(SartSonuc("Doktor branşı", SartDurumu.KONTROL_EDILEMEDI,
                                 "Doktor branşı verisi boş", "doktor_uzmanligi"))

    # Glisemik şart ibaresi (DPP-4/SGLT-2/GLP-1 için anlamlı)
    if is_dpp4 or is_sglt2 or is_glp1:
        if glisemik_sart_var:
            sartlar.append(SartSonuc(
                ad="Glisemik şart ibaresi (metformin/sülf. maks doz yetersiz)",
                durum=SartDurumu.VAR,
                neden="Rapor metninde 'metformin' + 'glisemik kontrol/yetersiz/maks doz' kombinasyonu bulundu",
                kaynak="tum_metin (rapor + reçete açk)"))
        else:
            sartlar.append(SartSonuc(
                ad="Glisemik şart ibaresi (metformin/sülf. maks doz yetersiz)",
                durum=SartDurumu.YOK,
                neden="Rapor/reçete metninde aranan ibare kombinasyonu bulunamadı",
                kaynak="tum_metin"))

    # Akut pankreatit anamnezi (eksenatid/SOLIQUA için kritik)
    if is_glp1 or is_soliqua:
        sartlar.append(SartSonuc(
            ad="Akut pankreatit anamnezi yok",
            durum=SartDurumu.YOK if akut_pankreatit_oykusu else SartDurumu.VAR,
            neden=("K85/K86.1 veya pankreatit ibaresi tespit edildi"
                   if akut_pankreatit_oykusu
                   else "Teşhis/metinde pankreatit ibaresi yok"),
            kaynak="teshis_tum"))

    # Ölçümler — sınıfa göre anlamlı
    if is_glp1 or is_soliqua:
        if bmi_deger is not None:
            sartlar.append(SartSonuc(
                ad="BMI > 35 (eksenatid/SOLIQUA)",
                durum=SartDurumu.VAR if bmi_deger > 35 else SartDurumu.YOK,
                neden=f"BMI = {bmi_deger}",
                kaynak="rapor_metni regex"))
        else:
            sartlar.append(SartSonuc(
                ad="BMI > 35 (eksenatid/SOLIQUA)",
                durum=SartDurumu.KONTROL_EDILEMEDI,
                neden="BMI/VKİ değeri metinden parse edilemedi",
                kaynak="rapor_metni"))

    if is_sglt2 or is_biguanid:
        if egfr_deger is not None:
            sartlar.append(SartSonuc(
                ad="eGFR (renal fonksiyon)",
                durum=SartDurumu.VAR,
                neden=f"eGFR = {egfr_deger} ml/dk",
                kaynak="rapor_metni regex"))

    # Kombi yasakları
    if (is_dpp4 and diger_glp1) or (is_glp1 and diger_dpp4):
        sartlar.append(SartSonuc(
            ad="DPP-4 + GLP-1 RA aynı reçetede yasak",
            durum=SartDurumu.YOK,
            neden=f"Aynı reçetede zıt sınıf ilaç: {diger_ilac_adlari[:120]}",
            kaynak="diger_ilac_adlari"))
    elif is_dpp4 or is_glp1:
        sartlar.append(SartSonuc(
            ad="DPP-4 + GLP-1 RA aynı reçetede yasak",
            durum=SartDurumu.VAR,
            neden="Aynı reçetede zıt sınıf yok",
            kaynak="diger_ilac_adlari"))

    # SUT 4.2.38(4) & (8): DPP-4 + GLP-1 birlikte ödenmez
    if (is_dpp4 and diger_glp1) or (is_glp1 and diger_dpp4):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj='DPP-4 + GLP-1 RA aynı reçetede — SUT YASAK',
            uyari='SUT 4.2.38(4)/(8): DPP-4 ve GLP-1 RA birlikte ödenmez (aynı inkretin yolağı)',
            sut_kurali='SUT 4.2.38(4)/(8) — DPP-4 + GLP-1 RA kombinasyonu yasak',
            detaylar={'sinif': 'DPP4+GLP1', 'diger_ilaclar': diger_ilac_adlari[:200]}
        )

    # SUT 4.2.38(8): GLYXAMBI (empa+lina) + diğer DPP-4 / diğer SGLT-2 / GLP-1 yasak
    is_glyxambi = 'GLYXAMBI' in arama_metni
    if is_glyxambi:
        # Diğer DPP-4 (linagliptin hariç başka bir DPP-4)
        diger_dpp4_glyxambi = any(
            k in diger_ilac_adlari for k in
            ['SITAGLIPTIN', 'VILDAGLIPTIN', 'SAKSAGLIPTIN', 'ALOGLIPTIN',
             'JANUVIA', 'GALVUS', 'ONGLYZA', 'NESINA',
             'JANUMET', 'GALVUSMET', 'KOMBOGLYZE', 'VIPDOMET'])
        diger_sglt2_glyxambi = any(
            k in diger_ilac_adlari for k in
            ['DAPAGLIFLOZIN', 'KANAGLIFLOZIN', 'CANAGLIFLOZIN', 'ERTUGLIFLOZIN',
             'FORZIGA', 'FORXIGA', 'INVOKANA', 'STEGLATRO',
             'XIGDUO', 'VOKANAMET', 'SEGLUROMET', 'QTERN', 'STEGLUJAN'])
        diger_glp1_glyxambi = any(k in diger_ilac_adlari for k in GLP1)
        if diger_dpp4_glyxambi or diger_sglt2_glyxambi or diger_glp1_glyxambi:
            yasak_tip = ('diğer DPP-4' if diger_dpp4_glyxambi else
                         'diğer SGLT-2' if diger_sglt2_glyxambi else 'GLP-1 RA')
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=f'GLYXAMBI + {yasak_tip} aynı reçetede — SUT 4.2.38(8) YASAK',
                uyari='SUT 4.2.38(8): Linagliptin+empagliflozin kombinasyonu diğer DPP-4 / '
                      'SGLT-2 / GLP-1 ile birlikte kullanılırsa bedelleri Kurumca karşılanmaz',
                sut_kurali='SUT 4.2.38(8) — GLYXAMBI + diğer DPP-4/SGLT-2/GLP-1 yasak',
                detaylar={'sinif': 'GLYXAMBI+'+yasak_tip,
                          'diger_ilaclar': diger_ilac_adlari[:200]}
            )

    sut_madde = '4.2.38'

    # ═══════════════════════════════════════════════════════════════════════
    # 1) KLASİK OAD (Madde 1) — METFORMIN, SÜLFONİLÜRE, AKARBOZ
    #    Tüm hekimler reçete edebilir. Diyabet rapor/tanı ile raporsuz uygun.
    # ═══════════════════════════════════════════════════════════════════════
    if (is_biguanid or is_sulfonilure or is_akarboz) \
       and not (is_dpp4 or is_sglt2 or is_glp1 or is_glinid or is_tzd):

        sinif_adi = []
        if is_biguanid: sinif_adi.append('biguanid')
        if is_sulfonilure: sinif_adi.append('sülfonilüre')
        if is_akarboz: sinif_adi.append('alfa-glukozidaz inh.')
        sinif_str = '/'.join(sinif_adi)

        # Metformin: eGFR < 30 ml/dk kontrendike
        if is_biguanid and egfr_deger is not None and egfr_deger < 30:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=f'Metformin — eGFR {egfr_deger} ml/dk (< 30 kontrendike)',
                uyari='Metformin eGFR < 30 ml/dk altında kontrendikedir '
                      '(laktik asidoz riski). 30-45 arası doz azaltma gerekir.',
                sut_kurali=f'SUT {sut_madde} — Metformin renal kontrendikasyon',
                detaylar={'sinif': 'biguanid', 'egfr': egfr_deger}
            )

        # Sülfonilüre + glinid aynı reçetede → aynı yolak yasağı
        diger_glinid = any(k in diger_ilac_adlari for k in GLINID)
        if is_sulfonilure and diger_glinid:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Sülfonilüre + glinid birlikte — aynı yolak (insülin sekresyonu)',
                uyari='Sülfonilüre ve glinidler aynı reseptör yolağını uyarır; '
                      'hipoglisemi riski + SGK ödemez.',
                sut_kurali=f'SUT {sut_madde} — Sülfonilüre+glinid kombinasyon yasağı',
                detaylar={'sinif': sinif_str, 'diger_ilaclar': diger_ilac_adlari[:200]}
            )

        # Yaşlı sülfonilüre uyarısı (klinik bilgi notu)
        yasli_sulfonilure_uyarisi = None
        if is_sulfonilure and yasli_hasta:
            yasli_sulfonilure_uyarisi = (f'Hasta yaşı {hasta_yasi} ≥ 75 — sülfonilüre '
                                          'hipoglisemi riski yüksek. Kısa etkili tercih edilmeli.')

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'{sinif_str.capitalize()} raporlu — diyabet rapor kodu ({rapor_kodu})',
                detaylar={'sinif': sinif_str, 'rapor_kodu': rapor_kodu,
                          'diyabet_tanisi': diyabet_var, 'hasta_yasi': hasta_yasi,
                          'egfr': egfr_deger},
                uyari=yasli_sulfonilure_uyarisi,
                sut_kurali=f'SUT {sut_madde}(1) — Klasik OAD raporlu kullanım uygun',
                aranan_ibare='Diyabet rapor kodu (07.02.x) veya tanısı'
            )
        if diyabet_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'{sinif_str.capitalize()} raporsuz — diyabet tanısı mevcut',
                detaylar={'sinif': sinif_str, 'rapor_kodu': None,
                          'diyabet_tanisi': True, 'teshisler': teshisler,
                          'hasta_yasi': hasta_yasi, 'egfr': egfr_deger},
                uyari=yasli_sulfonilure_uyarisi,
                sut_kurali=f'SUT {sut_madde}(1) — Tüm hekimler raporsuz yazabilir',
                aranan_ibare='Tip 2 DM tanısı (E11/E10)'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'{sinif_str.capitalize()} raporsuz — Medula diyabet tanısı şartını kontrol eder',
            detaylar={'sinif': sinif_str, 'teshisler': teshisler,
                      'medula_otomatik_tani_kontrolu': True,
                      'hasta_yasi': hasta_yasi, 'egfr': egfr_deger},
            uyari=yasli_sulfonilure_uyarisi,
            sut_kurali=f'SUT {sut_madde}(1) — Klasik OAD raporsuz, diyabet tanısı Medula kontrolünde',
            aranan_ibare='(eczacı kontrolüne gerek yok — Medula diyabet tanısı zorunlu kılar)'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 1B) GLİNİDLER (Madde 2) — Repaglinid/Nateglinid + diğer OAD kombineleri
    #    Endokrin/iç hast./çocuk/kardiyolog/aile hek. uzmanı VEYA bu hekim raporu
    # ═══════════════════════════════════════════════════════════════════════
    if is_glinid and not (is_dpp4 or is_sglt2 or is_glp1):
        sut_kurali_glinid = (f'SUT {sut_madde}(2) — Glinid: endokrin/iç hast./çocuk/'
                             'kardiyoloji/aile hekimi uzmanı veya bu hekim raporu')

        # Sülfonilüre + glinid yasağı (aynı yolak)
        diger_sulfonilure = any(k in diger_ilac_adlari for k in SULFONILURE)
        if diger_sulfonilure:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Glinid + sülfonilüre birlikte — aynı yolak (insülin sekresyonu)',
                uyari='Sülfonilüre ve glinidler aynı reseptör yolağını uyarır; '
                      'hipoglisemi riski + SGK ödemez.',
                sut_kurali=f'SUT {sut_madde} — Sülfonilüre+glinid kombinasyon yasağı',
                detaylar={'sinif': 'glinid', 'diger_ilaclar': diger_ilac_adlari[:200]}
            )

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Glinid raporlu (rapor {rapor_kodu}) — tüm hekimler yazabilir',
                detaylar={'sinif': 'glinid', 'rapor_kodu': rapor_kodu,
                          'doktor': doktor},
                sut_kurali=sut_kurali_glinid,
                aranan_ibare='Diyabet rapor kodu (07.02.x)'
            )
        if doktor_glinid_uygun:
            brans = ('endokrinoloji' if doktor_endokrin else
                     'iç hastalıkları' if doktor_dahiliye else
                     'çocuk sağlığı' if doktor_pediatri else
                     'kardiyoloji' if doktor_kardiyolog else 'aile hekimliği')
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Glinid raporsuz — {brans} uzmanı (yazabilir)',
                detaylar={'sinif': 'glinid', 'doktor': doktor,
                          'teshisler': teshisler},
                sut_kurali=sut_kurali_glinid,
                bulunan_metin=f'Doktor: {doktor}'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'Glinid raporsuz — doktor ({doktor or "bilinmiyor"}) yetkili branş değil',
            uyari=f'SUT {sut_madde}(2): Glinid için endokrin/iç hast./çocuk/'
                  'kardiyoloji/aile hek. uzmanı VEYA bu hekim raporu zorunlu',
            detaylar={'sinif': 'glinid', 'doktor': doktor},
            sut_kurali=sut_kurali_glinid,
            aranan_ibare='Yetkili uzman branşı veya rapor'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 1C) TZD / PIOGLITAZON (Madde 3) — Endokrin/iç hast./çocuk/kardiyolog
    #    veya bu hekimlerden rapor. KY kontrendike.
    # ═══════════════════════════════════════════════════════════════════════
    if is_tzd and not (is_dpp4 or is_sglt2 or is_glp1):
        sut_kurali_tzd = (f'SUT {sut_madde}(3) — Pioglitazon: endokrin/iç hast./'
                          'çocuk/kardiyoloji uzmanı veya bu hekim raporu')

        # KY kontrendikasyonu
        if kalp_yetmezligi:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Pioglitazon (TZD) — kalp yetmezliği mevcut, KONTRENDİKE',
                uyari='Pioglitazon NYHA I-IV kalp yetmezliğinde kontrendikedir '
                      '(sıvı retansiyonu, ödem, KY alevlenmesi).',
                sut_kurali=f'SUT {sut_madde} — TZD kalp yetmezliği kontrendikasyonu',
                detaylar={'sinif': 'TZD', 'teshisler': teshisler,
                          'kalp_yetmezligi': True}
            )

        if rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Pioglitazon raporlu (rapor {rapor_kodu}) — tüm hekimler yazabilir',
                detaylar={'sinif': 'TZD', 'rapor_kodu': rapor_kodu, 'doktor': doktor},
                sut_kurali=sut_kurali_tzd,
                aranan_ibare='Diyabet rapor kodu (07.02.x)'
            )
        if doktor_analog_tzd_uygun:
            brans = ('endokrinoloji' if doktor_endokrin else
                     'iç hastalıkları' if doktor_dahiliye else
                     'çocuk sağlığı' if doktor_pediatri else 'kardiyoloji')
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Pioglitazon raporsuz — {brans} uzmanı (yazabilir)',
                detaylar={'sinif': 'TZD', 'doktor': doktor, 'teshisler': teshisler},
                sut_kurali=sut_kurali_tzd,
                bulunan_metin=f'Doktor: {doktor}'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'Pioglitazon raporsuz — doktor ({doktor or "bilinmiyor"}) yetkili branş değil',
            uyari=f'SUT {sut_madde}(3): Pioglitazon için endokrin/iç hast./'
                  'çocuk/kardiyoloji uzmanı VEYA bu hekim raporu zorunlu',
            detaylar={'sinif': 'TZD', 'doktor': doktor},
            sut_kurali=sut_kurali_tzd,
            aranan_ibare='Yetkili uzman branşı veya rapor'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2) İNSÜLİNLER — Madde 1 (insan) / Madde 3 (analog) / Madde 3b (RYZODEG)
    #                / Madde 7 (SOLIQUA) ayrımı
    # ═══════════════════════════════════════════════════════════════════════
    if is_insulin and not (is_dpp4 or is_sglt2 or is_glp1) \
            or is_soliqua or is_xultophy:
        gestasyonel_var = any(k in teshis_tum for k in
                               ['O24', 'GESTASYONEL', 'GEBELIK DIYABET',
                                'GEBELİK DİYABET'])

        # ── Madde 7: SOLIQUA (insülin glarjin + liksisenatid) ─────────────
        if is_soliqua:
            sut_kurali_sol = (f'SUT {sut_madde}(7) — SOLIQUA: BMI > 35 + akut '
                              'pankreatit öyküsü yok + 1 yıl endokrin uzmanı raporu, '
                              'endokrin/iç hast. uzmanı reçete eder; DPP-4 ile yasak')
            # DPP-4 ile yasak
            if is_dpp4 or any(k in diger_ilac_adlari for k in DPP4):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='SOLIQUA + DPP-4 birlikte — SUT 4.2.38(7) yasak',
                    uyari='İnsülin glarjin+liksisenatid kombinasyonu DPP-4 ile birlikte ödenmez',
                    sut_kurali=sut_kurali_sol,
                    detaylar={'sinif': 'SOLIQUA', 'kombi': 'DPP4 yasak'}
                )
            if akut_pankreatit_oykusu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='SOLIQUA — akut pankreatit anamnezi var, KONTRENDİKE',
                    uyari='SUT 4.2.38(7): Tedavi öncesi akut pankreatit öyküsü olan hastalarda kullanılamaz',
                    sut_kurali=sut_kurali_sol,
                    detaylar={'sinif': 'SOLIQUA', 'pankreatit_oykusu': True}
                )
            if not rapor_kodu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='SOLIQUA — RAPORSUZ yazılmış (1 yıl endokrin uzmanı raporu zorunlu)',
                    uyari='SUT 4.2.38(7): SOLIQUA için 1 yıl süreli endokrinoloji uzman hekim raporu zorunlu',
                    sut_kurali=sut_kurali_sol,
                    detaylar={'sinif': 'SOLIQUA'}
                )
            # Rapor + BMI ≥ 35 kontrolü
            if bmi_deger is not None and bmi_deger < 35.0:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=f'SOLIQUA — BMI {bmi_deger} < 35 (şart sağlanmıyor)',
                    uyari='SUT 4.2.38(7): Tedavi başlangıcında BMI > 35 olmalı',
                    sut_kurali=sut_kurali_sol,
                    detaylar={'sinif': 'SOLIQUA', 'bmi': bmi_deger}
                )
            if not doktor_uygun_dpp4_sglt2:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj=f'SOLIQUA raporlu — reçeteleyen doktor ({doktor or "bilinmiyor"}) endokrin/iç hast. değil',
                    uyari='SUT 4.2.38(7): Reçeteyi endokrinoloji veya iç hastalıkları uzmanı yazmalı',
                    sut_kurali=sut_kurali_sol,
                    detaylar={'sinif': 'SOLIQUA', 'doktor': doktor, 'rapor_kodu': rapor_kodu}
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'SOLIQUA raporlu (rapor {rapor_kodu}) — şartlar uygun',
                detaylar={'sinif': 'SOLIQUA', 'rapor_kodu': rapor_kodu,
                          'bmi': bmi_deger, 'doktor': doktor},
                sut_kurali=sut_kurali_sol,
                aranan_ibare='1 yıl endokrin raporu + BMI > 35 + akut pankreatit öyküsü yok'
            )

        # ── XULTOPHY (insülin degludek+liraglutid) — özel uzman raporu ─────
        if is_xultophy:
            if not rapor_kodu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='XULTOPHY — RAPORSUZ yazılmış (insülin+GLP-1 kombi rapor zorunlu)',
                    uyari='XULTOPHY (insülin degludek+liraglutid) endokrinoloji/iç hast. uzman raporu gerektirir',
                    sut_kurali=f'SUT {sut_madde} — İnsülin+GLP-1 sabit kombi',
                    detaylar={'sinif': 'XULTOPHY'}
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'XULTOPHY raporlu (rapor {rapor_kodu})',
                detaylar={'sinif': 'XULTOPHY', 'rapor_kodu': rapor_kodu,
                          'doktor': doktor},
                sut_kurali=f'SUT {sut_madde} — İnsülin+GLP-1 sabit kombi',
                aranan_ibare='Endokrin/iç hast. uzman raporu'
            )

        # ── Madde 3b: RYZODEG (degludek+aspart) — sağlık kurulu raporu ────
        if is_ryzodeg:
            sut_kurali_ryz = (f'SUT {sut_madde}(3-b) — RYZODEG: en az bir endokrinolog '
                              'imzalı SAĞLIK KURULU raporu + analog karışım/uzun etkili '
                              'insülin yetersizliği + labil/hipoglisemi/regülasyon '
                              'sağlanamama ibaresi; endokrin veya iç hast. uzmanı yazar')
            if not rapor_kodu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='RYZODEG — RAPORSUZ yazılmış (sağlık kurulu raporu zorunlu)',
                    uyari='SUT 4.2.38(3-b): RYZODEG için en az bir endokrinolog imzalı SAĞLIK KURULU raporu zorunlu',
                    sut_kurali=sut_kurali_ryz,
                    detaylar={'sinif': 'RYZODEG'}
                )
            # Rapor metninde labil/hipoglisemi/regülasyon ibaresi araması
            ryzodeg_ibare = (_turkce_ara(tum_metin, 'labil') or
                             _turkce_ara(tum_metin, 'hipoglisem') or
                             _turkce_ara(tum_metin, 'regülasyon sağlanama') or
                             _turkce_ara(tum_metin, 'regulasyon saglanama') or
                             _turkce_ara(tum_metin, 'regüle edilemey') or
                             _turkce_ara(tum_metin, 'regule edilemey'))
            if not ryzodeg_ibare:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='RYZODEG raporlu — labil/hipoglisemi/regülasyon ibaresi bulunamadı',
                    uyari='SUT 4.2.38(3-b): Raporda "labil kan şekeri / sık hipoglisemi / '
                          'hipoglisemi yüksek riski / regülasyon sağlanamayan" ibarelerinden biri olmalı',
                    sut_kurali=sut_kurali_ryz,
                    detaylar={'sinif': 'RYZODEG', 'rapor_kodu': rapor_kodu},
                    aranan_ibare='labil / hipoglisemi / regülasyon sağlanamayan'
                )
            if not doktor_uygun_dpp4_sglt2:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj=f'RYZODEG raporlu — reçeteleyen doktor ({doktor or "bilinmiyor"}) endokrin/iç hast. değil',
                    uyari='SUT 4.2.38(3-b): Reçeteyi endokrinoloji veya iç hastalıkları uzmanı yazmalı',
                    sut_kurali=sut_kurali_ryz,
                    detaylar={'sinif': 'RYZODEG', 'doktor': doktor, 'rapor_kodu': rapor_kodu}
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'RYZODEG raporlu (rapor {rapor_kodu}) — şartlar uygun',
                detaylar={'sinif': 'RYZODEG', 'rapor_kodu': rapor_kodu, 'doktor': doktor},
                sut_kurali=sut_kurali_ryz,
                aranan_ibare='Sağlık kurulu raporu + endokrinolog + labil/hipoglisemi'
            )

        # ── Madde 1: İNSAN İNSÜLİNİ (HUMULIN/ACTRAPID/MIXTARD) — tüm hekim ─
        if is_insan_insulin and not is_analog_insulin:
            if rapor_kodu or diyabet_var or gestasyonel_var:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj='İnsan insülini — diyabet tanısı/raporu ile uygun (tüm hekim yazabilir)',
                    detaylar={'sinif': 'insan_insulin', 'rapor_kodu': rapor_kodu or None,
                              'diyabet_tanisi': diyabet_var, 'gestasyonel': gestasyonel_var},
                    sut_kurali=f'SUT {sut_madde}(1) — İnsan insülini tüm hekim raporsuz yazabilir',
                    aranan_ibare='Diyabet tanısı (Tip 1/2/Gestasyonel)'
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj='İnsan insülini — diyabet tanısı/rapor kodu bulunamadı',
                uyari='Reçetede diyabet tanısı (E10/E11/O24) veya rapor kodu olmalı',
                detaylar={'sinif': 'insan_insulin', 'teshisler': teshisler},
                sut_kurali=f'SUT {sut_madde}(1) — İnsan insülini için tanı zorunlu'
            )

        # ── Madde 3: ANALOG İNSÜLİN — endokrin/iç hast./çocuk/kardiyolog ──
        if is_analog_insulin:
            sut_kurali_ana = (f'SUT {sut_madde}(3) — Analog insülin: endokrin/iç hast./'
                              'çocuk/kardiyoloji uzmanı veya bu hekim raporu')
            if rapor_kodu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'Analog insülin raporlu (rapor {rapor_kodu}) — tüm hekimler yazabilir',
                    detaylar={'sinif': 'analog_insulin', 'rapor_kodu': rapor_kodu,
                              'doktor': doktor, 'diyabet_tanisi': diyabet_var},
                    sut_kurali=sut_kurali_ana,
                    aranan_ibare='Diyabet rapor kodu (07.02.x)'
                )
            if doktor_analog_tzd_uygun and (diyabet_var or gestasyonel_var):
                brans = ('endokrinoloji' if doktor_endokrin else
                         'iç hastalıkları' if doktor_dahiliye else
                         'çocuk sağlığı' if doktor_pediatri else 'kardiyoloji')
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'Analog insülin raporsuz — {brans} uzmanı (yazabilir)',
                    detaylar={'sinif': 'analog_insulin', 'doktor': doktor,
                              'teshisler': teshisler, 'gestasyonel': gestasyonel_var},
                    sut_kurali=sut_kurali_ana,
                    bulunan_metin=f'Doktor: {doktor}'
                )
            if not (diyabet_var or gestasyonel_var):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj='Analog insülin — diyabet tanısı/rapor bulunamadı',
                    uyari='Reçetede diyabet tanısı (E10/E11/O24) veya rapor kodu olmalı',
                    detaylar={'sinif': 'analog_insulin', 'teshisler': teshisler,
                              'doktor': doktor},
                    sut_kurali=sut_kurali_ana
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=f'Analog insülin raporsuz — doktor ({doktor or "bilinmiyor"}) yetkili branş değil',
                uyari=f'SUT {sut_madde}(3): Analog insülin için endokrin/iç hast./'
                      'çocuk/kardiyoloji uzmanı VEYA bu hekim raporu zorunlu',
                detaylar={'sinif': 'analog_insulin', 'doktor': doktor,
                          'teshisler': teshisler},
                sut_kurali=sut_kurali_ana,
                aranan_ibare='Yetkili uzman branşı veya rapor'
            )

        # ── Sınıflandırılamayan insülin (fallback) ────────────────────────
        if rapor_kodu or diyabet_var or gestasyonel_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='İnsülin — diyabet tanısı/raporu mevcut',
                detaylar={'sinif': 'insulin', 'rapor_kodu': rapor_kodu or None,
                          'diyabet_tanisi': diyabet_var, 'gestasyonel': gestasyonel_var},
                sut_kurali=f'SUT {sut_madde} — İnsülin diyabet endikasyonu',
                aranan_ibare='Diyabet tanısı (Tip 1/2/Gestasyonel/MODY)'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='İnsülin — diyabet tanısı/rapor kodu bulunamadı',
            uyari='Reçetede diyabet tanısı (E10/E11/O24) veya rapor kodu olmalı',
            detaylar={'sinif': 'insulin', 'teshisler': teshisler},
            sut_kurali=f'SUT {sut_madde} — İnsülin için tanı zorunlu'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3) GLP-1 RA — Madde 5 (Eksenatid) + obezite kapsam-dışı + diğer GLP-1
    # ═══════════════════════════════════════════════════════════════════════
    if is_glp1:
        # SAXENDA / WEGOVY obezite endikasyonu — SGK kapsam dışı
        if any(k in arama_metni for k in ['SAXENDA', 'WEGOVY']):
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='SAXENDA/WEGOVY (liraglutid/semaglutid obezite endikasyonu) — SGK ödemez',
                uyari='Obezite endikasyonunda GLP-1 RA SGK kapsamı dışındadır',
                sut_kurali=f'SUT {sut_madde} — Obezite endikasyonu kapsam-dışı',
                detaylar={'sinif': 'GLP1', 'endikasyon': 'obezite'}
            )

        # Eksenatid (BYETTA, BYDUREON) — Madde 5
        is_eksenatid = any(k in arama_metni for k in
                           ['EKSENATID', 'EXENATID', 'BYETTA', 'BYDUREON'])
        if is_eksenatid:
            sut_kurali_eks = (f'SUT {sut_madde}(5) — Eksenatid: BMI > 35 + akut '
                              'pankreatit öyküsü yok + tip 2 DM; ilk reçete (2x5mcg, '
                              '1 kutu) endokrin uzmanı raporsuz, devam reçete 6/12 ay '
                              'endokrin raporu; endokrin/iç hast. uzmanı yazar; '
                              'DPP-4 ile yasak')
            # DPP-4 yasak (Madde 5/ç)
            if any(k in diger_ilac_adlari for k in DPP4):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='Eksenatid + DPP-4 birlikte — SUT 4.2.38(5/ç) yasak',
                    uyari='Eksenatid DPP-4 antagonistleri ile birlikte ödenmez',
                    sut_kurali=sut_kurali_eks,
                    detaylar={'sinif': 'GLP1-Eksenatid', 'kombi': 'DPP4 yasak'}
                )
            # Akut pankreatit anamnezi
            if akut_pankreatit_oykusu:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='Eksenatid — akut pankreatit anamnezi var, KONTRENDİKE',
                    uyari='SUT 4.2.38(5): Tedavi öncesi akut pankreatit öyküsü olan hastalarda kullanılamaz',
                    sut_kurali=sut_kurali_eks,
                    detaylar={'sinif': 'GLP1-Eksenatid', 'pankreatit_oykusu': True}
                )
            # BMI > 35 şartı (ölçüm varsa)
            if bmi_deger is not None and bmi_deger <= 35.0:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=f'Eksenatid — BMI {bmi_deger} ≤ 35 (şart: > 35)',
                    uyari='SUT 4.2.38(5): Tedavi başlangıcında BMI > 35 kg/m² olmalı',
                    sut_kurali=sut_kurali_eks,
                    detaylar={'sinif': 'GLP1-Eksenatid', 'bmi': bmi_deger}
                )
            # Raporsuz — ilk reçete istisnası (sadece 2x5mcg + endokrin uzmanı)
            if not rapor_kodu:
                # 5mcg doz arama
                ilk_recete_doz = bool(re.search(r'5\s*(?:mcg|µg|mikrogram)',
                                                 arama_metni, re.IGNORECASE))
                if doktor_endokrin and ilk_recete_doz:
                    return KontrolRaporu(
                        sonuc=KontrolSonucu.UYGUN,
                        mesaj='Eksenatid ilk reçete (2x5mcg) — endokrin uzmanı, raporsuz uygun',
                        uyari='SUT 4.2.38(5/c): İlk reçete (2x5mcg, 1 kutu) endokrin uzmanı raporsuz; '
                              'devam reçetesi için 6 ay süreli endokrin raporu zorunlu',
                        sut_kurali=sut_kurali_eks,
                        detaylar={'sinif': 'GLP1-Eksenatid', 'ilk_recete': True,
                                  'doktor': doktor},
                        aranan_ibare='İlk reçete istisnası (2x5mcg + endokrin)'
                    )
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='Eksenatid raporsuz — ilk reçete istisnası dışı (rapor zorunlu)',
                    uyari='SUT 4.2.38(5): İlk reçete sadece endokrin uzmanı 2x5mcg 1 kutu '
                          'için raporsuz olabilir; aksi halde 6 ay süreli endokrin raporu zorunlu',
                    sut_kurali=sut_kurali_eks,
                    detaylar={'sinif': 'GLP1-Eksenatid', 'doktor': doktor}
                )
            # Raporlu — endokrin/iç hast. uzmanı reçete etmeli
            if not doktor_uygun_dpp4_sglt2:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj=f'Eksenatid raporlu — reçeteleyen ({doktor or "bilinmiyor"}) endokrin/iç hast. değil',
                    uyari='SUT 4.2.38(5/c): Reçeteyi endokrinoloji veya iç hastalıkları uzmanı yazmalı',
                    sut_kurali=sut_kurali_eks,
                    detaylar={'sinif': 'GLP1-Eksenatid', 'doktor': doktor,
                              'rapor_kodu': rapor_kodu}
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Eksenatid raporlu (rapor {rapor_kodu}) — şartlar uygun',
                detaylar={'sinif': 'GLP1-Eksenatid', 'rapor_kodu': rapor_kodu,
                          'bmi': bmi_deger, 'doktor': doktor},
                sut_kurali=sut_kurali_eks,
                aranan_ibare='6/12 ay endokrin raporu + BMI > 35 + akut pankreatit öyküsü yok'
            )

        # Liraglutid / semaglutid / dulaglutid / liksisenatid (tek başına)
        # — Paylaşılan SUT 4.2.38 metninde bu etken maddeler için açık ilke yok.
        # SUT eki güncellemesi takip edilmeli; ihtiyatlı yaklaşım: ŞÜPHELİ.
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='GLP-1 RA — SUT 4.2.38 paylaşılan metninde açık ilke bulunmuyor (eksenatid dışı)',
            uyari=(f'SUT {sut_madde}: Liraglutid/semaglutid/dulaglutid için bu maddede açık '
                   'şart tanımlanmamış. Güncel SUT eki ve mevzuat değişikliği kontrol edilmeli; '
                   'eksenatid kuralları (BMI > 35, endokrin raporu, DPP-4 yasak) emsal alınabilir.'),
            sut_kurali=f'SUT {sut_madde} — GLP-1 RA (eksenatid dışı): mevzuat boşluğu',
            detaylar={'sinif': 'GLP1-Diger', 'ilac_adi': ilac_adi,
                      'etkin_madde': etkin_madde, 'rapor_kodu': rapor_kodu,
                      'doktor': doktor, 'bmi': bmi_deger,
                      'pankreatit_oykusu': akut_pankreatit_oykusu},
            aranan_ibare='Manuel SUT/güncel mevzuat kontrolü'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 4) SGLT-2 İNHİBİTÖRLERİ (Madde 6) — sadece dapa/empa mevzuatta tanımlı
    # ═══════════════════════════════════════════════════════════════════════
    if is_sglt2 and not is_dpp4:
        sut_kurali_sglt2 = (f'SUT {sut_madde}(6) — SGLT-2 (dapagliflozin, empagliflozin): '
                            'metformin/sülfonilüre maks doz yetersiz glisemik kontrol + '
                            'endokrin/iç hast. uzmanı veya raporu')

        # Kanagliflozin / Ertugliflozin paylaşılan SUT 4.2.38(6) metninde açıkça yok
        if sglt2_etken in ('canagliflozin', 'ertugliflozin'):
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'{(sglt2_etken or "").capitalize()} — SUT 4.2.38(6) paylaşılan metninde tanımlı değil',
                uyari=f'SUT {sut_madde}(6) yalnızca dapagliflozin ve empagliflozin için '
                      'açık hüküm içeriyor. Kanagliflozin/ertugliflozin için güncel SUT '
                      'eki ve kapsam kontrolü manuel yapılmalıdır.',
                sut_kurali=sut_kurali_sglt2,
                detaylar={'sinif': 'SGLT2', 'etken': sglt2_etken,
                          'rapor_kodu': rapor_kodu, 'doktor': doktor,
                          'mevzuat_kapsami': 'belirsiz'},
                aranan_ibare='Manuel SUT/güncel mevzuat kontrolü'
            )

        # Reçete rap_kod 07.02.x (diyabet rapor kategorisi) ise hekim niyeti net:
        # bu reçete DM endikasyonludur. Hastanın diğer/eski raporlarındaki KY/KBH
        # ICD'lerini görüp endikasyon "yorumunu" değiştirme — DM dalında değerlendir.
        rapor_dm_kategorisi = bool(rapor_kodu and rapor_kodu.startswith('07.02'))
        ky_kbh_endikasyonu = (kalp_yetmezligi or kbh) and not rapor_dm_kategorisi

        # ── İlaç-spesifik eGFR kontrendikasyonu ───────────────────────────
        sglt2_egfr_min_kykbh = 20 if sglt2_etken == 'empagliflozin' else \
                                25 if sglt2_etken == 'dapagliflozin' else 30
        if egfr_deger is not None:
            min_egfr = sglt2_egfr_min_kykbh if ky_kbh_endikasyonu \
                       else (sglt2_egfr_min_diyabet or 25)
            if egfr_deger < min_egfr:
                etken_str = sglt2_etken or 'SGLT-2'
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=f'{etken_str.capitalize()} — eGFR {egfr_deger} ml/dk '
                          f'(< {min_egfr} kontrendike)',
                    uyari=f'{etken_str.capitalize()} için minimum eGFR sınırı '
                          f'{min_egfr} ml/dk (endikasyon: '
                          f'{"KY/KBH" if ky_kbh_endikasyonu else "diyabet"})',
                    sut_kurali=sut_kurali_sglt2,
                    detaylar={'sinif': 'SGLT2', 'etken': sglt2_etken,
                              'egfr': egfr_deger, 'egfr_sinir': min_egfr,
                              'endikasyon': 'KY/KBH' if ky_kbh_endikasyonu
                                              else 'diyabet'}
                )

        # KY/KBH endikasyonu — paylaşılan SUT 4.2.38(6) metninde açıkça yok;
        # eğer ödeme bu endikasyonda ayrı bir SUT maddesinden alınıyorsa şart
        # değişebilir. İhtiyatlı yaklaşım: ŞÜPHELİ + uyarı.
        # Reçete rap_kod 07.02.x ise bu dala girilmez — DM endikasyonu nettir.
        if ky_kbh_endikasyonu:
            endikasyon_str = 'kalp yetmezliği' if kalp_yetmezligi else 'kronik böbrek hastalığı'
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'SGLT-2 — {endikasyon_str} endikasyonu (SUT 4.2.38 metni bu endikasyonu açıkça tanımlamıyor)',
                uyari=f'SUT {sut_madde}(6) yalnızca diyabet glisemik kontrol şartı için '
                      'hüküm içeriyor; KY/KBH endikasyonu için güncel SUT eki/genelge '
                      'manuel kontrol edilmelidir.',
                detaylar={'sinif': 'SGLT2', 'etken': sglt2_etken,
                          'endikasyon': 'kalp_yetmezligi' if kalp_yetmezligi else 'kbh',
                          'teshisler': teshisler, 'doktor': doktor,
                          'rapor_kodu': rapor_kodu, 'egfr': egfr_deger},
                sut_kurali=f'SUT {sut_madde}(6) — KY/KBH endikasyonu mevzuat boşluğu',
                aranan_ibare='Manuel SUT/güncel mevzuat kontrolü'
            )

        # Diyabet endikasyonu
        if rapor_kodu:
            if not glisemik_sart_var:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj='SGLT-2 raporlu — metformin/sülfonilüre maks doz yetersiz glisemik kontrol ibaresi bulunamadı',
                    uyari=f'SUT {sut_madde}(6): Raporda "metformin ve/veya sülfonilürelerin '
                          'maksimum tolere edilebilir dozlarında yeterli glisemik kontrol '
                          'sağlanamamıştır" ibaresi (veya eşdeğeri) ZORUNLU',
                    detaylar={'sinif': 'SGLT2', 'rapor_kodu': rapor_kodu,
                              'glisemik_sart': False, 'etken': sglt2_etken},
                    sut_kurali=sut_kurali_sglt2,
                    aranan_ibare='metformin/sülfonilüre + maks doz + yetersiz glisemik kontrol'
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='SGLT-2 raporlu — metformin/sülfonilüre yetersiz glisemik kontrol ibaresi bulundu',
                detaylar={'sinif': 'SGLT2', 'endikasyon': 'diyabet',
                          'rapor_kodu': rapor_kodu, 'glisemik_sart': True,
                          'etken': sglt2_etken},
                sut_kurali=sut_kurali_sglt2,
                aranan_ibare='metformin/sülfonilüre maks doz + yetersiz glisemik kontrol',
                bulunan_metin=_eslesen_parcayi_bul(tum_metin, 'metformin') or
                               _eslesen_parcayi_bul(tum_metin, 'glisemik')
            )

        # Raporsuz — endokrin/iç hast. uzmanı yazabilir
        if doktor_uygun_dpp4_sglt2:
            if not glisemik_sart_var:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=f'SGLT-2 raporsuz — uzman ({"endokrin" if doktor_endokrin else "iç hast."}) '
                          'ancak reçete açıklamasında glisemik şart ibaresi yok',
                    uyari=f'SUT {sut_madde}(6): Raporsuz uzman reçetesinde dahi '
                          '"metformin/sülfonilüre maks doz yetersiz glisemik kontrol" '
                          'ibaresi reçete açıklamasında bulunmalı',
                    detaylar={'sinif': 'SGLT2', 'doktor': doktor,
                              'glisemik_sart': False, 'etken': sglt2_etken},
                    sut_kurali=sut_kurali_sglt2,
                    aranan_ibare='Reçete açıklamasında glisemik şart ibaresi'
                )
            brans = 'endokrinoloji' if doktor_endokrin else 'iç hastalıkları'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'SGLT-2 raporsuz — {brans} uzmanı + glisemik şart ibaresi mevcut',
                detaylar={'sinif': 'SGLT2', 'endikasyon': 'diyabet',
                          'doktor': doktor, 'teshisler': teshisler,
                          'glisemik_sart': True, 'etken': sglt2_etken},
                sut_kurali=sut_kurali_sglt2,
                aranan_ibare='Endokrinoloji/iç hastalıkları uzmanı + glisemik şart',
                bulunan_metin=f'Doktor: {doktor}'
            )

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'SGLT-2 raporsuz — doktor ({doktor or "bilinmiyor"}) endokrin/iç hast. değil',
            uyari=f'SUT {sut_madde}(6): SGLT-2 için endokrin/iç hast. uzmanı VEYA bu hekim raporu zorunlu',
            detaylar={'sinif': 'SGLT2', 'doktor': doktor, 'teshisler': teshisler,
                      'etken': sglt2_etken},
            sut_kurali=sut_kurali_sglt2,
            aranan_ibare='Endokrinoloji/iç hastalıkları uzmanı veya raporu'
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 5) DPP-4 İNHİBİTÖRLERİ (Madde 4) — saf veya kombi
    # ═══════════════════════════════════════════════════════════════════════
    if is_dpp4:
        sut_kurali_dpp4 = (f'SUT {sut_madde}(4) — DPP-4: metformin/sülfonilüre maks doz '
                           'yetersiz glisemik kontrol + endokrin/iç hast. uzmanı veya raporu')

        # ── Saksagliptin 2,5mg / alogliptin 12,5mg → yalnızca KBH ─────────
        if (is_saksa_2_5 or is_aloglip_12_5) and not kbh:
            dusuk_doz_str = 'Saksagliptin 2,5 mg' if is_saksa_2_5 else 'Alogliptin 12,5 mg'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=f'{dusuk_doz_str} — KBH yok, kullanım dışı',
                uyari='SUT 4.2.38(4): Saksagliptin 2,5 mg ve alogliptin 12,5 mg '
                      'düşük doz formları YALNIZCA kronik böbrek yetmezliği hastalarında kullanılabilir',
                sut_kurali=sut_kurali_dpp4,
                detaylar={'sinif': 'DPP4', 'dusuk_doz_form': dusuk_doz_str,
                          'kbh': False, 'teshisler': teshisler}
            )

        # GLP-1 yasağı — daha üstte yakalanır ama erken çıkış için tekrar emniyet
        if any(k in diger_ilac_adlari for k in GLP1):
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='DPP-4 + GLP-1 RA birlikte — SUT 4.2.38(4) yasak',
                uyari='SUT 4.2.38(4): DPP-4 antagonistleri GLP-1 analogları ile birlikte ödenmez',
                sut_kurali=sut_kurali_dpp4,
                detaylar={'sinif': 'DPP4', 'kombi': 'GLP1 yasak'}
            )

        # Pediatri uyarısı (klinik bilgi notu)
        pediatri_uyari = None
        if pediatri_hasta:
            pediatri_uyari = (f'Hasta yaşı {hasta_yasi} (< 18). DPP-4 inhibitörleri '
                              'pediatrik popülasyonda sınırlı veriyle onaylıdır '
                              '(sitagliptin ≥10 yaş).')

        # ── RAPORSUZ — endokrin/iç hast. uzmanı reçeteleyebilir (SUT 4.2.38(4)) ──
        if not rapor_kodu:
            if doktor_uygun_dpp4_sglt2:
                if not glisemik_sart_var:
                    return KontrolRaporu(
                        sonuc=KontrolSonucu.UYGUN_DEGIL,
                        mesaj=f'DPP-4 raporsuz — uzman ({"endokrin" if doktor_endokrin else "iç hast."}) '
                              'ancak glisemik şart ibaresi yok',
                        uyari=f'SUT {sut_madde}(4): Raporsuz uzman reçetesinde dahi '
                              '"metformin/sülfonilüre maks doz yetersiz glisemik kontrol" '
                              'ibaresi reçete açıklamasında bulunmalı',
                        sut_kurali=sut_kurali_dpp4,
                        detaylar={'sinif': 'DPP4', 'doktor': doktor,
                                  'glisemik_sart': False,
                                  'kombi_metformin': is_biguanid},
                        aranan_ibare='Reçete açıklamasında glisemik şart ibaresi'
                    )
                brans = 'endokrinoloji' if doktor_endokrin else 'iç hastalıkları'
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'DPP-4 raporsuz — {brans} uzmanı + glisemik şart ibaresi mevcut',
                    uyari=pediatri_uyari,
                    detaylar={'sinif': 'DPP4', 'doktor': doktor,
                              'glisemik_sart': True,
                              'kombi_metformin': is_biguanid,
                              'hasta_yasi': hasta_yasi},
                    sut_kurali=sut_kurali_dpp4,
                    aranan_ibare='Endokrin/iç hast. uzmanı + glisemik şart',
                    bulunan_metin=f'Doktor: {doktor}'
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='DPP-4 RAPORSUZ ve doktor endokrin/iç hast. değil',
                uyari=f'SUT {sut_madde}(4): DPP-4 için endokrin/iç hast. uzmanı VEYA bu hekim raporu zorunlu',
                sut_kurali=sut_kurali_dpp4,
                detaylar={'sinif': 'DPP4', 'doktor': doktor,
                          'kombi_metformin': is_biguanid}
            )

        # ── RAPORLU — glisemik şart ibaresi zorunlu ───────────────────────
        if not glisemik_sart_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='DPP-4 raporlu — metformin/sülfonilüre maks doz yetersiz glisemik kontrol ibaresi bulunamadı',
                uyari=f'SUT {sut_madde}(4): Raporda "metformin ve/veya sülfonilürelerin '
                      'maksimum tolere edilebilir dozlarında yeterli glisemik kontrol '
                      'sağlanamamıştır" ibaresi (veya eşdeğeri) ZORUNLU',
                detaylar={'sinif': 'DPP4', 'rapor_kodu': rapor_kodu,
                          'glisemik_sart': False, 'kombi_metformin': is_biguanid},
                sut_kurali=sut_kurali_dpp4,
                aranan_ibare='metformin/sülfonilüre + maks doz + yetersiz glisemik kontrol'
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='DPP-4 raporlu — metformin/sülfonilüre yetersiz glisemik kontrol ibaresi bulundu',
            uyari=pediatri_uyari,
            detaylar={'sinif': 'DPP4', 'rapor_kodu': rapor_kodu,
                      'glisemik_sart': True, 'hba1c': hba1c_deger,
                      'kombi_metformin': is_biguanid,
                      'hasta_yasi': hasta_yasi},
            sut_kurali=sut_kurali_dpp4,
            aranan_ibare='metformin/sülfonilüre maks doz + yetersiz glisemik kontrol',
            bulunan_metin=_eslesen_parcayi_bul(tum_metin, 'metformin') or
                           _eslesen_parcayi_bul(tum_metin, 'glisemik') or
                           _eslesen_parcayi_bul(tum_metin, 'sülfonilüre')
        )

    # ═══════════════════════════════════════════════════════════════════════
    # FALLBACK — Sınıfı tespit edilemeyen diyabet ilacı
    # ═══════════════════════════════════════════════════════════════════════
    if rapor_kodu and rapor_kodu.startswith('07.02'):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Diyabet rapor kodu ({rapor_kodu}) mevcut',
            detaylar={'sinif': 'belirlenmedi', 'rapor_kodu': rapor_kodu},
            sut_kurali=f'SUT {sut_madde} — Diyabet rapor kodu',
            aranan_ibare='07.02.x rapor kodu'
        )

    if diyabet_var:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Diyabet tanısı mevcut — ilaç sınıfı belirlenemedi, ek kontrol önerilir',
            uyari='İlaç sınıfı net tespit edilemedi; raporlu ise rapor metni kontrol edilmeli',
            detaylar={'sinif': 'belirlenmedi', 'teshisler': teshisler},
            sut_kurali=f'SUT {sut_madde}',
            aranan_ibare='Diyabet tanısı (E10/E11)'
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='Diyabet ilacı sınıfı tespit edilemedi, tanı/rapor bulunamadı',
        uyari='Manuel kontrol önerilir: ilaç adı/etkin madde + tanı + rapor kodu',
        detaylar={'ilac_adi': ilac_adi, 'etkin_madde': etkin_madde,
                  'rapor_kodu': rapor_kodu, 'doktor': doktor},
        sut_kurali=f'SUT {sut_madde}'
    )


# Sistem timestamp temizleme: "(Ekleme=DD/MM/YYYY HH:MM)" / "(Düzeltme=...)"
# Klopidogrel (3MQQQBQ) ve istatin (ÖMER ORDU) bug'larında bu Medula timestamp'i
# kelime penceresine düşüp tarih olarak yanlış eşleşiyordu.
_SISTEM_TIMESTAMP_PAT = re.compile(
    r'\(?\s*(?:ekleme|d[üu]zeltme|guncelleme|güncelleme)\s*[=:]\s*'
    r'\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}'
    r'(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\)?',
    flags=re.IGNORECASE,
)


def _sistem_timestamp_temizle(metin: str) -> str:
    if not metin:
        return ''
    return _SISTEM_TIMESTAMP_PAT.sub(' ', metin)


def _anjio_tarihi_yakin_bul(metin_orjinal: str, metin_lower: str,
                              pencere: int = 150) -> Tuple[str, bool]:
    """metin_lower'da anjio/angio/KAH anchor kelimelerinin ±pencere karakter
    yakınında tarih (gg.aa.yyyy / gg/aa/yyyy) varsa, o tarihi döndür.

    Dönüş: (tarih_str, malformed_mu).
      - ('', False) → tarih yok
      - ('29.01.2025', False) → 4-hane yıl, geçerli format
      - ('29/01/202', True) → 3-hane yıl (ya da yıl < 2010), malformed

    Anchor'lar: 'anjio', 'angio', 'anjiyo', 'angyo', 'angiyo', 'kah tarih'
    ('KAH TARİHİ', 'KAH TA:' kalıpları → user feedback 3M4UYAG, 2026-05-07).

    SUT 4.2.15: Anjiografi ile belgelenmiş KAH'ta anjiografi tarihi raporda
    belirtilmelidir."""
    if not metin_orjinal or not metin_lower:
        return '', False

    # Sistem timestamp'lerini ÖNCEDEN temizle (3MQQQBQ bug'ı). Hem orjinal
    # hem normalize edilmiş metinde aynı offsetleri korumak için her ikisinde
    # de aynı yerlerde boşluk ile değiştir.
    metin_orjinal_temiz = _SISTEM_TIMESTAMP_PAT.sub(
        lambda m: ' ' * len(m.group(0)), metin_orjinal)
    metin_lower_temiz = _SISTEM_TIMESTAMP_PAT.sub(
        lambda m: ' ' * len(m.group(0)), metin_lower)

    anahtarlar = ('anjio', 'angio', 'anjiyo', 'angyo', 'angiyo', 'kah tarih')
    pozlar = []
    for k in anahtarlar:
        ofset = 0
        while True:
            i = metin_lower_temiz.find(k, ofset)
            if i < 0:
                break
            pozlar.append(i)
            ofset = i + len(k)
    if not pozlar:
        return '', False

    # 1. Geçiş: 4-hane yıl (geçerli format)
    tarih_pat_tam = re.compile(r'\d{2}[./]\d{2}[./](\d{4})')
    n = len(metin_orjinal_temiz)
    for p in pozlar:
        b = max(0, p - pencere)
        s = min(n, p + pencere)
        for m in tarih_pat_tam.finditer(metin_orjinal_temiz[b:s]):
            try:
                yil = int(m.group(1))
            except ValueError:
                continue
            if 1990 <= yil <= 2030:
                return m.group(0), False

    # 2. Geçiş: 2-3 hane yıl ya da geçersiz aralık → malformed
    tarih_pat_kirpik = re.compile(r'\d{2}[./]\d{2}[./]\d{2,4}')
    for p in pozlar:
        b = max(0, p - pencere)
        s = min(n, p + pencere)
        m = tarih_pat_kirpik.search(metin_orjinal_temiz[b:s])
        if m:
            return m.group(0), True

    return '', False


def kontrol_klopidogrel(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.15 - Klopidogrel / Prasugrel / Tikagrelor Kontrol

    Endikasyonlar:
    A) Koroner stent (max 12 ay)
    B) AKS (STEMI/NSTEMI/unstabil angina)
    C) Anjiografik koroner arter hastalığı (ASA intoleransı + anjio tarihi şart)
    D) Tıkayıcı periferik arter hastalığı (ASA intoleransı şartıyla)
    E) İskemik inme (ASA intoleransı şartıyla)
    F) Kalp kapak biyoprotezi (ASA intoleransı şartıyla)

    Anjio belgelenmiş KAH'ta anjiografi tarihi raporda belirtilmelidir; aksi
    halde rapor eksiklik içerir → ŞÜPHELİ.

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

    # Anjiografi / KAH (çeşitli yazımlar: anjio/angio/anjiyo/angyo).
    # 'kah tarih' (KAH TARİHİ DD.MM.YYYY) — TR rapor dilinde "koroner anjiografi
    # tarihi" anlamında kullanılan kısaltma (3M4UYAG örneği, 2026-05-07).
    anjio_var = any(k in metin_lower for k in
                    ['anjio', 'angio', 'anjiyo', 'angyo', 'angiyo', 'kah tarih'])
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
    # NOT: "TIA" kısaltması Türkçe-normalize sonrası "tıa" olur — her ikisi de aransın.
    inme_var = any(k in metin_lower for k in ['iskemik inme', 'serebral iskemi',
                                               'serebrovasküler', 'serebrovaskuler',
                                               'tia', 'tıa'])
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
    # 'gis intolerans' = "GİS intoleransI" (gastrointestinal sistem kısaltması)
    # TR rapor dilinde yaygın (3MQQQBQ örneği, 2026-05-07).
    asa_intolerans = any(k in metin_lower for k in ['asa intolerans', 'aspirin intolerans',
                                                     'aspirin kontrendik', 'asetilsalisilik intolerans',
                                                     'gastrointestinal intolerans',
                                                     'gis intolerans',
                                                     'aspirin allerjisi', 'asa allerjisi'])
    # ASA gerektiren endikasyonlar: sadece "KAH" — iskemik inme ve PAH için SUT 4.2.15'te
    # ASA intoleransı ŞARTI yok (raporda Inme/PAH endikasyonu yeterli).
    asa_gereken = any(e in endikasyonlar for e in ['KAH/Anjiografi', 'KAH (ICD)'])
    asa_gereksiz = any(e in endikasyonlar for e in ['Koroner stent', 'AKS/MI', 'Doktor onayı (12 ay)',
                                                      'İskemik inme', 'Periferik arter'])

    # ── 3. Tarih bilgisi ──
    # Sistem timestamp'lerini ((Ekleme=...)) hariç tut, aksi halde kullanıcıya
    # "Tarih: 02/01/2026" gösterilir ama bu rapor düzenleme zamanıdır (3MQQQBQ).
    birlesik_tarih_temiz = _sistem_timestamp_temizle(birlesik)
    tarih_match = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', birlesik_tarih_temiz)
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

    # KAH/inme/PAH → ASA intoleransı gerekli (+ anjio belgelenmişse anjio tarihi)
    if asa_gereken:
        eksiklikler = []
        onaylar = []

        # 3a) Anjio belgelenmiş KAH'ta anjiografi tarihi raporda zorunlu.
        # Sistem timestamp'i ((Ekleme=...)) tarih olarak yakalanmamalı (3MQQQBQ).
        # Kırpık tarih (yıl 3 hane) malformed olarak işaretlenir (3MQQQBQ).
        if anjio_var:
            anjio_tarih, anjio_malformed = _anjio_tarihi_yakin_bul(birlesik, metin_lower)
            if anjio_tarih and not anjio_malformed:
                detaylar['anjio_tarihi'] = anjio_tarih
                onaylar.append(f'anjio tarihi {anjio_tarih}')
            elif anjio_tarih and anjio_malformed:
                detaylar['anjio_tarihi_malformed'] = anjio_tarih
                eksiklikler.append(
                    f'anjiografi tarihi formatı hatalı/kırpık ({anjio_tarih})')
            else:
                eksiklikler.append('anjiografi tarihi raporda belirtilmemiş')

        # 3b) ASA intoleransı veya rapor kodu fallback (Medula örtük onay)
        rapor_kodu_klop = (ilac_sonuc.get('rapor_kodu') or '').strip()
        medula_onay = bool(rapor_kodu_klop and (
            rapor_kodu_klop.startswith('04.02.1')
            or rapor_kodu_klop.startswith('04.04.1')))

        if asa_intolerans:
            onaylar.append('ASA intoleransı mevcut')
        elif medula_onay:
            onaylar.append(f'rapor kodu {rapor_kodu_klop} (örtük ASA intoleransı)')
            detaylar['medula_otomatik'] = True
        else:
            eksiklikler.append('ASA/aspirin intoleransı ibaresi yok')

        # Eksiklik varsa ŞÜPHELİ döndür (anjio tarihi yok ve/veya ASA yok)
        if eksiklikler:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f"Endikasyon: {', '.join(endikasyonlar)} — "
                       f"eksiklik: {'; '.join(eksiklikler)}"),
                detaylar={**detaylar, 'eksiklikler': eksiklikler},
                uyari='SUT 4.2.15 — ' + '; '.join(eksiklikler),
                sut_kurali=sut_kurali,
                aranan_ibare=' / '.join(eksiklikler),
                bulunan_metin=eslesen_birlesik
            )

        # Tüm şartlar tamam → UYGUN
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f"Endikasyon: {', '.join(endikasyonlar)} + "
                   f"{' + '.join(onaylar)}{tarih_str}"),
            detaylar=detaylar,
            uyari=('ASA intoleransı raporda yer aldığı varsayılır'
                   if (medula_onay and not asa_intolerans) else None),
            sut_kurali=sut_kurali,
            aranan_ibare=('endikasyon + ASA intoleransı'
                          + (' + anjio tarihi' if anjio_var else '')),
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


def _ldl_tarihlerini_eslestir(metin: str, olcumler: List[Dict],
                                 min_yil: int = 2015) -> None:
    """olcumler listesindeki her LDL için 'tarih' alanını metindeki en uygun
    tarihle doldurur. Yön heuristikleri:
      - Tarihten hemen sonra "TARIHLI" / "tarihinde" → sonraki LDL'ye ait
        (Türkçe: "26.03.2026 TARIHLI LDL: 202")
      - Tarihten hemen önce "(" → önceki LDL'ye ait
        (Parens: "LDL: 195 (12.01.2026)")
      - Diğer → mesafece en yakın LDL'ye ait
    """
    from datetime import date as _date
    if not metin or not olcumler:
        return
    # Tüm tarihleri çıkar (start_pos, date, end_pos).
    # Doktorlar bazen 2-haneli yıl yazıyor: "8.1.26" = 08.01.2026 (HURİYE
    # YAMAN raporu örneği). Hem 4-haneli hem 2-haneli yıl pattern'lerini
    # destekliyoruz; 2-haneli için <50 → 2000+, >=50 → 1900+ kabulü.
    tarihler = []
    patterns = [
        (r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', 'dmy4'),
        (r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', 'ymd4'),
        # 2-haneli yıl — kelime sınırı içinde, yıl 2 hane (yanlış eşleşme
        # önlemek için negatif lookahead/lookbehind: önce-sonra digit yok)
        (r'(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{2})(?!\d)', 'dmy2'),
    ]
    for pat, fmt in patterns:
        for m in re.finditer(pat, metin):
            try:
                if fmt == 'dmy4':
                    g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == 'ymd4':
                    y, a, g = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:  # dmy2 — 2-haneli yıl
                    g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = 2000 + y if y < 50 else 1900 + y
                if not (1 <= g <= 31 and 1 <= a <= 12):
                    continue
                if y < min_yil or y > 2100:
                    continue
                tarihler.append((m.start(), _date(y, a, g), m.end()))
            except (ValueError, OverflowError):
                continue
    if not tarihler:
        return
    # Çift kayıtları temizle (aynı tarihe iki pattern eşleşebilir)
    seen = set()
    tarihler = [t for t in tarihler
                if not (t[0] in seen or seen.add(t[0]))]

    # Her tarih için yön tahmini.
    # ÖNEMLİ: Python'un .lower() Türkçe büyük 'İ' için combining dot üretir
    # ('TARİHLİ'.lower() == 'tari̇hli̇' → 'tarihli' ile eşleşmez). Ayrıca
    # sekreter ASCII büyük 'I' yazabilir ('TARIHLI'). Her iki yazımı da
    # 'tarihli'ye normalize etmek için Türkçe karakterleri ASCII'ye çek:
    def _trnorm(s: str) -> str:
        return (s.replace('İ', 'I').replace('I', 'I').replace('ı', 'i')
                  .replace('Ş', 'S').replace('ş', 's')
                  .replace('Ğ', 'G').replace('ğ', 'g')
                  .replace('Ü', 'U').replace('ü', 'u')
                  .replace('Ö', 'O').replace('ö', 'o')
                  .replace('Ç', 'C').replace('ç', 'c')
                  .lower())

    yon = {}
    for dpos, _d, dend in tarihler:
        sonraki = _trnorm(metin[dend:dend + 30]).lstrip()
        onceki = metin[max(0, dpos - 5):dpos]
        if sonraki.startswith('tarihli') or sonraki.startswith('tarihinde'):
            yon[dpos] = 'next'   # tarih sonraki LDL'ye ait
        elif '(' in onceki:
            yon[dpos] = 'prev'   # tarih önceki LDL'ye (parens) ait
        else:
            yon[dpos] = 'auto'

    # LDL pozisyonları sıralı
    ldl_pos_sirali = sorted({o['pos'] for o in olcumler})

    def _onceki_ldl(dpos):
        prev = None
        for p in ldl_pos_sirali:
            if p < dpos:
                prev = p
            else:
                break
        return prev

    def _sonraki_ldl(dpos):
        for p in ldl_pos_sirali:
            if p > dpos:
                return p
        return None

    # Her LDL için en uygun tarihi seç
    for o in olcumler:
        ldl_pos = o['pos']
        adaylar = []  # (öncelik, mesafe, date)
        for dpos, d, _dend in tarihler:
            y = yon[dpos]
            delta = dpos - ldl_pos
            if y == 'next' and _sonraki_ldl(dpos) == ldl_pos:
                adaylar.append((0, abs(delta), d))
            elif y == 'prev' and _onceki_ldl(dpos) == ldl_pos:
                adaylar.append((0, abs(delta), d))
            elif y == 'auto' and abs(delta) <= 80:
                adaylar.append((1, abs(delta), d))
        if adaylar:
            adaylar.sort(key=lambda t: (t[0], t[1]))
            o['tarih'] = adaylar[0][2]


def _yakindaki_tarihi_bul(metin: str, hedef_pos: Optional[int] = None,
                            min_yil: int = 2015):
    """Metinde dd.mm.yyyy / dd/mm/yyyy / dd-mm-yyyy / yyyy-mm-dd ara.

    Args:
        metin: aranacak metin (genelde ±100 chars LDL etrafı)
        hedef_pos: hedef pozisyon (LDL değerinin metin içindeki yeri).
                   Verilirse bu pozisyona en yakın tarihi döndürür.
                   None ise ilk tarihi döndürür.
        min_yil: bu yıldan önceki tarihler reddedilir. SUT raporlarında
                 LDL ölçüm tarihi son 2-3 yıl içindedir; "doğum tarihi:
                 1965" gibi tarihler lab değildir → reddet (varsayılan 2015).

    Returns: en uygun `datetime.date` veya None.
    """
    from datetime import date as _date
    if not metin:
        return None
    patterns = [
        (r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', 'dmy'),
        (r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', 'ymd'),
    ]
    adaylar = []  # [(pos, date), ...] — ham pozisyon
    for pat, fmt in patterns:
        for m in re.finditer(pat, metin):
            try:
                if fmt == 'dmy':
                    g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    y, a, g = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if not (1 <= g <= 31 and 1 <= a <= 12):
                    continue
                if y < min_yil or y > 2100:
                    # Doğum tarihi / eski rapor tarihi vb. — yok say
                    continue
                d = _date(y, a, g)
            except (ValueError, OverflowError):
                continue
            adaylar.append((m.start(), d))
    if not adaylar:
        return None
    if hedef_pos is None:
        adaylar.sort(key=lambda t: t[0])
        return adaylar[0][1]

    # Türkçe rapor düzeninde "DD.MM.YYYY TARIHLI LDL: NNN" yapısı yaygın —
    # tarih ÖNCE, LDL SONRA. Bu yüzden:
    #   1. öncelik: LDL'den 60 karakter ÖNCE gelen tarihler (en yakın olan)
    #   2. öncelik: LDL'den 100 karakter SONRA gelen tarihler (parantez içi)
    #   3. öncelik: uzakta kalan tarihler (mesafece sırala)
    def oncelik(item):
        pos, _d = item
        delta = pos - hedef_pos
        if -60 <= delta < 0:
            return (0, abs(delta))
        if 0 <= delta <= 100:
            return (1, abs(delta))
        return (2, abs(delta))
    adaylar.sort(key=oncelik)
    return adaylar[0][1]


def _tum_ldl_olcumlerini_bul(metin: str) -> List[Dict]:
    """Metindeki TÜM LDL sayısal değerlerini, pozisyon, çevre ve yakındaki
    tarihiyle birlikte döndür.

    Returns: [{'deger': int, 'pos': int, 'tarih': date|None, 'cevre': str}, ...]

    Kullanılan patternler (öncelik sırasıyla):
      1. SIKI    : 'ldl[- ]*c?\\s*[:=]?\\s*N'  →  'LDL: 195', 'LDL-C: 195', 'LDL=195'
      2. GEVŞEK  : 'ldl[^0-9\\n]{0,60}?N'      →  'LDL Kolesterol: 195',
                                                   'LDL Kol.: 195',
                                                   'LDL kolesterol değeri 195',
                                                   'LDL Kolesterol (İndirekt) 195'
      3. ZİNCİR  : İlk LDL'den sonra yakın metinde virgül/ve/tire ile sıralanan
                   ikinci sayı  →  'LDL: 195 ve 210', 'LDL: 195, 210'
                   (ikinci ölçümün başında 'LDL' prefiksi olmasa bile yakalar)
    """
    if not metin:
        return []
    # Sistem timestamp'lerini ÖNCEDEN temizle: "(Ekleme=DD/MM/YYYY HH:MM)"
    # Aksi takdirde "11:39" içindeki 39 LDL değeri sanılır, "25/04/2025"
    # tarihleri LDL ölçüm tarihi olarak yakalanır (ÖMER ORDU bug'ı).
    metin = re.sub(
        r'\(?\s*ekleme\s*[=:]\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}'
        r'(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\)?',
        ' ', metin, flags=re.IGNORECASE,
    )
    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()

    olcumler: List[Dict] = []
    seen_pos = set()

    def _ekle(deger_str: str, pos: int, prefix_var: bool = False,
                tarih_bitisik_kabul: bool = False):
        try:
            deger = int(float(deger_str.replace(',', '.')))
        except ValueError:
            return
        # TARİH BİLEŞENİ REDDİ: yakalanan sayıdan SONRA "[./-]\d{1,2}[./-]\d"
        # şeklinde devam ediyorsa, bu sayı tarih (gün) bileşenidir, LDL DEĞİL.
        # Örn: "LDL-KOLESTROL DEGERI 21.12.2025 ... 146" → "21" tarih, atla.
        # İSTİSNA: tarih_bitisik_kabul=True ise (özel "LDL+TARIH BİTİŞİK"
        # pattern'i çağırırken) bu kontrol atlanır — çünkü pattern zaten
        # tarihi tüketmiş, sayı LDL prefix'inin doğrudan ardından gelir.
        if not tarih_bitisik_kabul:
            son_idx = pos + len(deger_str)
            sonrasi = metin_lower[son_idx:son_idx + 8]
            if re.match(r'[./\-]\d{1,2}[./\-]\d', sonrasi):
                return  # Tarih bileşeni (örn "21" + ".12.2025") — LDL değil
        # LDL aralık kontrolü:
        #  - Üst sınır 600 (ailesel hiperkolesterolemi tavanı)
        #  - Alt sınır prefix'e göre:
        #    * "LDL: 29" gibi açık prefix varsa → 10 yeterli (PCSK9 inh.
        #      tedavisinde LDL=29 gibi düşük değerler gerçek)
        #    * Prefix yoksa (ZİNCİR pattern) → 32 (gün/saat false-positive
        #      önleme: tarih bileşeni 1-31, dakika 0-59)
        alt_sinir = 10 if prefix_var else 32
        if not (alt_sinir <= deger <= 600):
            return
        # Aynı pozisyonda iki pattern eşleşirse çift sayma
        if any(abs(pos - p) < 3 for p in seen_pos):
            return
        seen_pos.add(pos)
        bas = max(0, pos - 100)
        son = min(len(metin), pos + 100)
        cevre = metin[bas:son]
        # LDL pozisyonu çevre içindeki ofsete eşleniyor (pos - bas).
        # Ayrıca min_yil filtresi "doğum tarihi" gibi eski tarihleri eler.
        tarih = _yakindaki_tarihi_bul(cevre, hedef_pos=pos - bas,
                                        min_yil=2015)
        olcumler.append({
            'deger': deger,
            'pos': pos,
            'tarih': tarih,
            'cevre': cevre.strip(),
        })

    # 1) SIKI pattern — 'ldl: 195' / 'ldl-c: 195' / 'ldl=195'
    # Lookahead: yakalanan sayıdan SONRA tarih/saat başı (./-:\d) DEĞİL
    # olmalı. Bu sayede "LDL DEGERI 21.12.2025" durumunda "21" tarih bileşeni
    # olarak reddedilir; "195" gibi gerçek LDL değerleri yakalanır.
    sıkı = re.compile(
        # (?!\d) — sayının arkasında digit yok (tam yakalama). Boşluksuz
        # bozuk metinde "LDL 255/06/05" → 25 yerine 255 yakalanmasın diye;
        # "255" sonrası "/" tarih başı → dış lookahead red → tamamen ŞÜPHELİ.
        r'ldl[- ]*c?\s*[:=]?\s*(\d{1,3})(?!\d)(?:[.,]\d+)?'
        r'(?![./\-:]\d)'
    )
    sıkı_eşleşmeler = [(m.start(1), m.group(1))
                         for m in sıkı.finditer(metin_lower)]
    for pos, deg in sıkı_eşleşmeler:
        _ekle(deg, pos, prefix_var=True)

    # 2) GEVŞEK pattern — LDL'den sonra 60 karaktere kadar non-digit text
    # ('LDL Kolesterol: 195', 'LDL Kol.: 195', 'LDL kolesterol indirekt 195')
    # Aynı lookahead — sekreter yazımı yamuk olsa bile değer + tarih ayrımı.
    gevsek = re.compile(
        r'ldl[^0-9\n]{0,60}?(\d{1,3})(?!\d)(?:[.,]\d+)?'
        r'(?![./\-:]\d)'
    )
    for m in gevsek.finditer(metin_lower):
        _ekle(m.group(1), m.start(1), prefix_var=True)

    # 2a) LDL+TARIH BİTİŞİK pattern — boşluksuz format:
    # "LDL 177/12/12/2025"  → LDL=177, tarih bitişik
    # "LDL 255/06/05/2025"  → LDL=255 (3JR4BZO)
    # SIKI/GEVŞEK lookahead'ı tarih başını reddettiği için bu format
    # yakalanamıyor; özel pattern gerek.
    ldl_tarih_bitisik = re.compile(
        r'ldl[\s:=-]*(\d{2,3})[/.\-]\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}'
    )
    for m in ldl_tarih_bitisik.finditer(metin_lower):
        _ekle(m.group(1), m.start(1),
              prefix_var=True, tarih_bitisik_kabul=True)

    # 2b) TARIH-SONRASI pattern — "LDL ... TARIH ... NN" formatı
    # Örn: "HASTANIN LDL-KOLESTROL DEGERI 21.12.2025 TARIHINDE 146 MG/DL"
    # Standart GEVŞEK ilk digit (tarih bileşeni) yakalayıp tarih bileşeni
    # reddi sonrası backtracking yapamıyor (non-greedy [^0-9] ilk digit'te
    # durur). Bu yüzden TARİH'i de tüketen ayrı bir pattern gerek.
    tarih_sonra = re.compile(
        # (?<!\d) ve (?!\d) — yıl bileşeni greedy yutsun (örn "2025" yıl,
        # "25" değil). Yoksa "21.07.20" + "25" şeklinde split edilip 25
        # yapay LDL olarak yakalanır (MUSTAFA CAKAL bug'ı).
        r'ldl[^0-9\n]{0,80}?(?<!\d)\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}(?!\d)'
        r'[^0-9\n]{0,30}?(\d{2,3})(?![./\-:]\d)'
    )
    for m in tarih_sonra.finditer(metin_lower):
        _ekle(m.group(1), m.start(1), prefix_var=True)

    # 3) ZİNCİR — bir LDL bulunduktan SONRA yakın metinde (≤120 karakter)
    # listelenen ikinci/üçüncü sayıları yakala. SUT raporlarında sık görülen:
    # 'LDL: 195 ve 210', 'LDL Kolesterol: 195, 210', 'LDL: 195 mg/dL — 210 mg/dL'
    # Sadece daha önce LDL bağlamında bulunmuş olan ilk eşleşmeden sonra
    # gelen sayıları arar (rastgele sayıları yakalamamak için).
    if sıkı_eşleşmeler or any('ldl' in metin_lower[m.start():m.end()]
                                for m in gevsek.finditer(metin_lower)):
        for ldl_match in re.finditer(r'ldl[^.\n]{0,200}', metin_lower):
            blok = ldl_match.group(0)
            blok_offset = ldl_match.start()
            # Bu bloktaki tüm 2-3 haneli sayıları yakala (LDL plausible aralık)
            # Lookahead/lookbehind ile tarih bileşenlerini ele:
            # '12.01.2026' içindeki 12/01 → öncesi veya sonrası . / - olduğu
            # için reddedilir; 4 haneli sayı (yıl) zaten \d{2,3} ile elenir.
            # Lookbehind/lookahead reddetmeleri:
            #  - `/.-:\d` → tarih (12.01), aralık (1-2), saat (11:39)
            #  - HARF (a-zA-Z) → ICD kodu (E78.5, I10, K12) — "78" LDL sanılmasın
            for n in re.finditer(
                    r'(?<![/.\-:\da-zA-Z])(\d{2,3}(?:[.,]\d+)?)'
                    r'(?![/.\-:\d])', blok):
                _ekle(n.group(1), blok_offset + n.start(1))

    # Pozisyona göre sırala (oluşum sırası — okunduğu sıra)
    olcumler.sort(key=lambda o: o['pos'])

    # Tarihleri akıllı eşleştir: "TARIHLI" Türkçe yapısı + parantez formatı.
    # _ekle'deki çevre-bazlı yakalama ilk tahmin idi; bu daha kesin.
    _ldl_tarihlerini_eslestir(metin, olcumler, min_yil=2015)
    return olcumler


def _iki_olcum_kuralini_dogrula(olcumler: List[Dict], esik: int = 190) -> Dict:
    """SUT 4.2.28.A — iki ölçüm kuralı doğrulama.

    Şart: en az 2 ölçüm > esik, aralarında ≥7 gün ve ≤180 gün (6 ay).

    Returns: {'durum': ..., 'detay': str, 'olcum_sayisi': int,
              'gun_farki': int|None, 'degerler': [int...]}
    'durum' değerleri:
      - 'uygun'         : 2+ ölçüm, tarih farkı 7-180 gün → SUT şartı sağlandı
      - 'tarih_yok'     : 2+ ölçüm var ama tarih bilgisi eksik → varsayılan UYGUN ama uyarı
      - 'tek_olcum'     : sadece 1 ölçüm > esik → ŞÜPHELİ
      - 'kisa_aralik'   : 2+ ölçüm ama < 7 gün arayla → kural ihlali
      - 'uzun_aralik'   : 2+ ölçüm ama > 180 gün arayla → 6 ay sınırı aşıldı
      - 'esik_alti'     : > esik ölçüm yok
    """
    yuksek = [o for o in olcumler if o['deger'] > esik]
    degerler = [o['deger'] for o in yuksek]
    if not yuksek:
        return {'durum': 'esik_alti',
                'detay': f'> {esik} mg/dL LDL ölçümü bulunamadı',
                'olcum_sayisi': 0, 'gun_farki': None, 'degerler': []}
    if len(yuksek) == 1:
        return {'durum': 'tek_olcum',
                'detay': (f"TEK ölçüm > {esik} bulundu ({yuksek[0]['deger']} mg/dL); "
                          "SUT 1 hafta arayla 6 ay içinde 2 ölçüm istiyor"),
                'olcum_sayisi': 1, 'gun_farki': None, 'degerler': degerler}

    tarihli = [o for o in yuksek if o['tarih']]
    if len(tarihli) < 2:
        return {'durum': 'tarih_yok',
                'detay': (f"{len(yuksek)} ölçüm > {esik} mg/dL var "
                          f"({', '.join(str(d) for d in degerler)}); "
                          "tarih bilgisi eksik, ölçüm aralığı doğrulanamadı"),
                'olcum_sayisi': len(yuksek), 'gun_farki': None,
                'degerler': degerler}

    tarihler = sorted({o['tarih'] for o in tarihli})
    fark = (tarihler[-1] - tarihler[0]).days
    if fark < 7:
        return {'durum': 'kisa_aralik',
                'detay': (f"{len(yuksek)} ölçüm > {esik} ama aralarında {fark} gün "
                          "(en az 7 gün gerekli)"),
                'olcum_sayisi': len(yuksek), 'gun_farki': fark,
                'degerler': degerler}
    if fark > 180:
        return {'durum': 'uzun_aralik',
                'detay': (f"{len(yuksek)} ölçüm > {esik} ama aralarında {fark} gün "
                          "(6 ay/180 günü aşmış)"),
                'olcum_sayisi': len(yuksek), 'gun_farki': fark,
                'degerler': degerler}
    return {'durum': 'uygun',
            'detay': (f"{len(yuksek)} ölçüm > {esik} mg/dL "
                      f"({', '.join(str(d) for d in degerler)}), "
                      f"{fark} gün aralık (uygun)"),
            'olcum_sayisi': len(yuksek), 'gun_farki': fark,
            'degerler': degerler}


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
       (yüksek KV riskli hastalarda tek ölçüm yeterli olabilir — ana akım uygulama)
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
    # Türkçe "I" → "ı" normalizasyonu kelime aramada problem çıkarır
    # ("TIP 2" → "tıp 2", aranan "tip 2" eşleşmez). DM/risk faktörü
    # taraması için ek bir varyant tut: 'I' → 'i' (dotted i'ye çevir)
    metin_alt = (birlesik_metin.replace('İ', 'i').replace('I', 'i').lower()
                  if birlesik_metin else '')

    # ── 1. LDL değeri ara ──
    ldl_degeri = None
    ldl_eslesen = ""

    # ÖNCE _tum_ldl_olcumlerini_bul'un sonucundan al — bu fonksiyon false-
    # positive eleme yapıyor (15.11.2024'teki "15", E78.5'teki "78", saat
    # "11:39"daki "39", Ekleme= timestamp'leri vb.). En yüksek değeri SUT
    # eşik dallaması için kullan; iki-ölçüm kontrolü ayrıca yapılacak.
    _on_olcumler = _tum_ldl_olcumlerini_bul(birlesik_metin)
    if _on_olcumler:
        # En yüksek LDL = en kritik durumun temsilcisi
        ldl_degeri = max(o['deger'] for o in _on_olcumler)
        ldl_eslesen = _eslesen_parcayi_bul(birlesik_metin, 'ldl')
    else:
        # Fallback: regex pattern'ları (tum_olcumler boşsa — örn metin
        # serbest formatta, parser yakalayamadı)
        ldl_patterns = [
            r'ldl[- ]*c?\s*[:=]?\s*(\d{2,3})(?![/.\-:\d])',
            r'ldl[^0-9\n]{0,50}?(\d{2,3})(?![/.\-:\d])',
        ]
        for pattern in ldl_patterns:
            ldl_match = re.findall(pattern, metin_lower)
            for cand in ldl_match:
                try:
                    cand_int = int(float(cand.replace(',', '.')))
                except ValueError:
                    continue
                # Fizyolojik aralık (≥32: gün 1-31, saat HH, ICD 2-haneli
                # eleme; ≤600: ailesel hiperkolesterolemi tavanı)
                if 32 <= cand_int <= 600:
                    ldl_degeri = cand_int
                    ldl_eslesen = _eslesen_parcayi_bul(birlesik_metin, 'ldl')
                    break
            if ldl_degeri is not None:
                break

    # Kolesterol genel ibare (LDL bulunamazsa)
    ldl_var = ldl_degeri is not None
    kolesterol_var = 'kolesterol' in metin_lower or 'kolestrol' in metin_lower
    lipid_var = 'lipid' in metin_lower or 'hiperlipidemi' in metin_lower
    dislipidemi_var = 'dislipidemi' in metin_lower or 'hiperlipidemi' in metin_lower

    detaylar['ldl_degeri'] = ldl_degeri

    # ── 2. Risk faktörleri ara ──
    risk_faktorleri = []

    # Yüksek risk grubu (LDL > 70 yeterli) — kelime sınırı + Türkçe varyantlar
    # Hem metin_lower (I→ı) hem metin_alt (I→i) varyantını tara: "TIP 2" yazımı
    # Türkçe normalizasyondan dolayı kaçmasın.
    def _eslesir_mi(patternler) -> bool:
        for desen in patternler:
            if re.search(desen, metin_lower) or re.search(desen, metin_alt):
                return True
        return False

    dm_var = _eslesir_mi([
        r'\bdiyabet', r'\bdiabet', r'\bdm\b', r'\bt[12]dm\b',
        r'\bnıdde\b', r'\bniddm\b', r'\biddm\b',
        r'tip\s*[12]\s*(?:dm|diyabet|diabet)',
        r'şeker\s*hastal',     # şeker hastalığı / şeker hastası
        r'\bdiabetik\b', r'\bdiyabetik\b',
        r'\bhiperglisem',      # hiperglisemi
    ])
    aks_var = _eslesir_mi([
        r'akut\s*koroner', r'\baks\b', r'\bakut\s*mi\b',
    ])
    mi_var = _eslesir_mi([
        r'miyokard', r'infarkt', r'\bmi\b',
        r'\bstemi\b', r'\bnstemi\b',
    ])
    inme_var = _eslesir_mi([
        r'\binme\b', r'\bstroke\b', r'serebrovasküler', r'serebro\s*vask',
        r'\bsva\b',
    ])
    # KAH (Koroner Arter Hastalığı) ≠ KOAH (Kronik Akciğer). \bkah\b kelime
    # sınırı yeterli — "koah" içindeki "kah" sol sınırı başarısız (O harfi var).
    kah_var = _eslesir_mi([
        r'koroner\s*arter', r'\bkah\b', r'iskemik\s*kalp',
    ])
    pah_var = _eslesir_mi([
        r'periferik\s*arter', r'\bpah\b', r'\bpaod\b',
    ])
    aaa_var = _eslesir_mi([
        r'aort\s*anevrizma', r'\baaa\b', r'aort\s*disseks',
    ])
    karotid_var = _eslesir_mi([r'karotid', r'karotis'])
    stent_var = _eslesir_mi([r'\bstent\b'])
    bypass_var = _eslesir_mi([r'bypass', r'\bkabg\b', r'koroner\s*by[-\s]?pass'])

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

    # Rapor kodu KV/KAH ise risk faktörü olarak ekle
    # 04.02 = Kardiyovasküler (KAH/iskemik kalp hastalığı raporu)
    # 04.02.1 = Antiplatelet (klopidogrel) — KAH benzeri
    if rapor_kodu and (rapor_kodu.startswith('04.02') or rapor_kodu.startswith('04.04')):
        if 'KAH' not in risk_faktorleri:
            risk_faktorleri.append(f'KAH (rapor {rapor_kodu})')

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
        # Tüm LDL ölçümlerini çıkar (iki ölçüm kuralı için)
        # Yüksek KV riskli hastalarda bu kontrol sıkı uygulanmaz
        # (DM/KAH/AKS varsa tek değer yeterli kabul edilir).
        tum_olcumler = _tum_ldl_olcumlerini_bul(birlesik_metin)
        detaylar['ldl_olcum_sayisi'] = len(tum_olcumler)
        detaylar['ldl_olcumler'] = [
            {'deger': o['deger'],
             'tarih': o['tarih'].isoformat() if o['tarih'] else None}
            for o in tum_olcumler
        ]

        # Risk bazlı eşik kontrolü
        if cok_yuksek_risk and ldl_degeri > 70:
            # Yüksek KV risk → tek ölçüm yeterli
            uygunluk = "UYGUN"
            aciklama = f"LDL {ldl_degeri} > 70 mg/dL (risk: {', '.join(risk_faktorleri)})"
        # Tüm LDL ölçümlerini özet string'e çevir (parametre gösterimi için)
        olcum_ozet = ""
        if tum_olcumler:
            parcalar = []
            for o in tum_olcumler[:5]:  # max 5 göster
                t = o.get('tarih')
                t_str = t.strftime('%d.%m.%Y') if t else '?'
                parcalar.append(f"LDL={o['deger']} ({t_str})")
            olcum_ozet = " | Ölçümler: " + ", ".join(parcalar)
            if len(tum_olcumler) > 5:
                olcum_ozet += f" (+{len(tum_olcumler) - 5} adet daha)"

        risk_ozet = (f" | Risk: {', '.join(risk_faktorleri)}"
                      if risk_faktorleri else " | Risk: yok")

        # YÜKSEK KV RİSK ÖNCELİĞİ — DM/KAH/AKS/MI/inme/PAH/AAA/karotid varsa
        # SUT 4.2.28.A "yüksek KV riskli" sınıf: LDL>70 yeterli, ek risk
        # gerekmez, tek ölçüm bile kabul edilir. Kademeli eşikler (130/160/190)
        # SADECE risk faktörü olmayan genel popülasyon için.
        if cok_yuksek_risk and ldl_degeri > 70:
            uygunluk = "UYGUN"
            aciklama = (f"UYGUN | LDL {ldl_degeri} > 70 mg/dL | "
                        f"Yüksek KV risk: {', '.join(risk_faktorleri)}"
                        f"{olcum_ozet} | "
                        f"Kural: SUT 4.2.28.A — yüksek KV riskli hastalar "
                        f"için LDL>70 yeterli")
        elif ldl_degeri > 190:
            # EK RİSK FAKTÖRÜ YOK — 2 ölçüm > 190 gerekli
            kontrol2 = _iki_olcum_kuralini_dogrula(tum_olcumler, esik=190)
            detaylar['iki_olcum_kontrolu'] = kontrol2
            durum2 = kontrol2['durum']
            kural = ("SUT 4.2.28.A: LDL>190 + 2 ölçüm "
                      "(1 hafta arayla, 6 ay içinde) — ek risk faktörü gerekmez")
            if durum2 == 'uygun':
                uygunluk = "UYGUN"
                aciklama = (f"UYGUN | LDL {ldl_degeri} > 190 mg/dL | "
                            f"{kontrol2['detay']}{olcum_ozet} | "
                            f"Kural: {kural}")
            elif durum2 == 'tarih_yok':
                # 2+ ölçüm var, tarih doğrulanamadı → varsayılan UYGUN
                uygunluk = "UYGUN"
                aciklama = (f"UYGUN (tarihler doğrulanamadı) | "
                            f"LDL {ldl_degeri} > 190 mg/dL | "
                            f"{kontrol2['detay']}{olcum_ozet}")
            elif durum2 == 'tek_olcum':
                # KESİN BİLGİ: tek ölçüm var, SUT 2 ölçüm istiyor → UYGUN DEĞİL
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: TEK ÖLÇÜM | "
                            f"LDL {ldl_degeri} > 190 mg/dL{olcum_ozet} | "
                            f"Kural: {kural}")
            elif durum2 == 'kisa_aralik':
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: ölçüm aralığı çok kısa | "
                            f"LDL {ldl_degeri} > 190 | "
                            f"{kontrol2['detay']}{olcum_ozet} | "
                            f"Kural: {kural}")
            elif durum2 == 'uzun_aralik':
                # KESİN BİLGİ: aralık 6 aydan uzun → UYGUN DEĞİL
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: ölçümler 6 aydan uzun "
                            f"aralıkla | LDL {ldl_degeri} > 190 | "
                            f"{kontrol2['detay']}{olcum_ozet} | "
                            f"Kural: {kural}")
            else:
                # GERÇEK BELİRSİZLİK: ölçüm sayısı/tarihi çıkarılamadı → ŞÜPHELİ
                uygunluk = "ŞÜPHELI"
                aciklama = (f"ŞÜPHELİ | Sebep: 2 ölçüm doğrulanamadı | "
                            f"LDL {ldl_degeri} > 190{olcum_ozet} | "
                            f"Detay: {kontrol2['detay']} | "
                            f"Kural: {kural}")
        elif ldl_degeri > 160:
            # 2 risk faktörü + 2 ölçüm > 160 gerekli
            kontrol2 = _iki_olcum_kuralini_dogrula(tum_olcumler, esik=160)
            detaylar['iki_olcum_kontrolu'] = kontrol2
            kural = "SUT 4.2.28.A: LDL>160 + 2 ek risk + 2 ölçüm gerekli"
            if kontrol2['durum'] == 'tek_olcum':
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: TEK ÖLÇÜM | "
                            f"LDL {ldl_degeri} > 160 mg/dL{olcum_ozet}"
                            f"{risk_ozet} | Kural: {kural}")
            elif kontrol2['durum'] == 'kisa_aralik':
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: ölçüm aralığı çok kısa | "
                            f"LDL {ldl_degeri} > 160 | "
                            f"{kontrol2['detay']}{olcum_ozet}")
            else:
                uygunluk = "UYGUN"
                aciklama = (f"UYGUN | LDL {ldl_degeri} > 160 mg/dL | "
                            f"{kontrol2['detay']}{olcum_ozet}{risk_ozet}")
        elif ldl_degeri > 130:
            # 3 risk faktörü + 2 ölçüm > 130 gerekli
            kontrol2 = _iki_olcum_kuralini_dogrula(tum_olcumler, esik=130)
            detaylar['iki_olcum_kontrolu'] = kontrol2
            kural = "SUT 4.2.28.A: LDL>130 + 3 ek risk + 2 ölçüm gerekli"
            if kontrol2['durum'] == 'tek_olcum':
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: TEK ÖLÇÜM | "
                            f"LDL {ldl_degeri} > 130 mg/dL{olcum_ozet}"
                            f"{risk_ozet} | Kural: {kural}")
            elif kontrol2['durum'] == 'kisa_aralik':
                uygunluk = "UYGUN_DEGIL"
                aciklama = (f"UYGUN DEĞİL | Sebep: ölçüm aralığı çok kısa | "
                            f"LDL {ldl_degeri} > 130 | "
                            f"{kontrol2['detay']}{olcum_ozet}")
            else:
                uygunluk = "UYGUN"
                aciklama = (f"UYGUN | LDL {ldl_degeri} > 130 mg/dL | "
                            f"{kontrol2['detay']}{olcum_ozet}{risk_ozet}")
        elif ldl_degeri > 70 and cok_yuksek_risk:
            uygunluk = "UYGUN"
            aciklama = (f"UYGUN | LDL {ldl_degeri} > 70 mg/dL | "
                        f"Yüksek KV risk: {', '.join(risk_faktorleri)}"
                        f"{olcum_ozet}")
        elif ldl_degeri <= 70:
            # KESİN BİLGİ: LDL düşük + yüksek risk yok → statin endikasyonu yok
            uygunluk = "UYGUN_DEGIL"
            aciklama = (f"UYGUN DEĞİL | Sebep: LDL ≤ 70 mg/dL ve "
                        f"yüksek KV risk faktörü yok | "
                        f"LDL {ldl_degeri}{olcum_ozet}{risk_ozet} | "
                        f"Kural: SUT statin endikasyonu için LDL>70 + risk "
                        f"VEYA LDL>130/160/190 ölçütü")
        else:
            uygunluk = "UYGUN"
            aciklama = f"UYGUN | LDL {ldl_degeri} mg/dL raporda mevcut"

        # Yüksek doz uyarısı
        uyari_mesaj = ""
        if detaylar['yuksek_doz']:
            uyari_mesaj = "YÜKSEK DOZ — Kardiyoloji/KDC/Endokrinoloji/Geriatri raporu gerekli"

        # Sonuç kodlama
        sonuc_map = {
            "UYGUN":       KontrolSonucu.UYGUN,
            "UYGUN_DEGIL": KontrolSonucu.UYGUN_DEGIL,
            "ŞÜPHELI":     KontrolSonucu.KONTROL_EDILEMEDI,
        }
        return KontrolRaporu(
            sonuc=sonuc_map.get(uygunluk, KontrolSonucu.KONTROL_EDILEMEDI),
            mesaj=aciklama,
            detaylar=detaylar,
            uyari=uyari_mesaj if uyari_mesaj else None,
            sut_kurali=sut_kurali,
            aranan_ibare=(
                f"LDL değeri + risk faktörleri "
                f"({', '.join(risk_faktorleri) if risk_faktorleri else 'yok'}) "
                f"+ 2 ölçüm/tarih kontrolü"
            ),
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

    # KV ana rapor kodları (04.02/04.04) — KAH riski örtük olarak var,
    # statin tedavisi mantıklı; Medula şart kontrolünü yapmıştır.
    if rapor_kodu and (rapor_kodu.startswith('04.02') or rapor_kodu.startswith('04.04')):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Statin — KV rapor kodu {rapor_kodu} (KAH/AKS riski örtük), Medula şart kontrolünü yapar',
            detaylar=detaylar,
            uyari='LDL değerinin raporda yer aldığı varsayılır (Medula reddetmemiş ise uygun)',
            sut_kurali=sut_kurali,
            aranan_ibare=f'KV rapor kodu ({rapor_kodu}) — KAH endikasyonu örtük',
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
    # TG parse için ayrı sade-normalize: "I" → "ı" YAPMA (İngilizce
    # kısaltmaları bozmasın, "TRIG" → "trıg" olmasın). "İ" → "i" yeterli.
    metin_lower_sade = birlesik.replace('İ', 'i').lower() if birlesik else ''

    sut_kurali = 'SUT 4.2.28.B — Fibrat: Trigliserid düzeyi raporda belirtilmiş olmalı'
    detaylar = {'tg_degeri': None, 'risk_faktorleri': []}

    # ── 1. Trigliserid değeri ara ──
    # Yazım çeşitliliği geniş — TG / Trig / Trigliserid / Trigliserit /
    # Triglyceride / T.G. / TGs hepsi yakalanmalı.
    tg_degeri = None
    tg_eslesen = ""
    tg_patterns = [
        # Tam kelime: trigliserid / trigliserit / triglyceride
        r'(?:trigliserid|trigliserit|triglyceri)e?[^0-9]{0,20}(\d{2,4})',
        # 4-harfli kısaltma "trig" + ayraç + sayı (ör. "trig: 506",
        # "trig.180", "trig 240"). \btrig\B ile sıkı sınır: sonrası harf
        # ise atla (trigliserid'i ikinci kez yakalamasın).
        r'\btrig(?![a-z])\.?\s*[:=]?\s*(\d{2,4})',
        # 2-3 harfli kısaltma "tg", "tgs" + ayraç + sayı
        r'\btgs?(?![a-z])\.?\s*[:=]?\s*(\d{2,4})',
        # Noktalı kısaltma "t.g" / "t.g."
        r'\bt\.g\.?\s*[:=]?\s*(\d{2,4})',
    ]
    for pattern in tg_patterns:
        tg_match = re.findall(pattern, metin_lower_sade)
        if tg_match:
            try:
                tg_degeri = int(tg_match[0])
                for k in ['trigliserid', 'trigliserit', 'triglyceri',
                          'trig', 't.g', 'tg']:
                    p = _eslesen_parcayi_bul(birlesik, k)
                    if p:
                        tg_eslesen = p
                        break
                break
            except ValueError:
                pass

    tg_var = tg_degeri is not None
    tg_ibare = any(k in metin_lower_sade for k in [
        'trigliserid', 'trigliserit', 'triglyceri',
        'trig ', 'trig:', 'trig=', 'trig.',
        'tg ', 'tg:', 'tg=', 'tg.', 'tgs',
        't.g',
    ])
    detaylar['tg_degeri'] = tg_degeri

    # ── 2. Risk faktörleri ──
    risk = []
    if any(k in metin_lower for k in ['diyabet', 'diabetes', 'dm ']) or any(k in teshis_metin for k in ['E10', 'E11', 'E14']):
        risk.append('DM')
    if any(k in metin_lower for k in ['koroner', 'kah ', 'iskemik kalp']) or any(k in teshis_metin for k in ['I20', 'I25']):
        risk.append('KAH')
    if any(k in metin_lower for k in ['periferik arter', 'pah ']) or any(k in teshis_metin for k in ['I70', 'I73']):
        risk.append('PAH')
    # NOT: "MI" kısaltması Türkçe-normalize sonrası "mı" olur (I→ı).
    # Hem "mi " hem "mı " yakalanmalı.
    if any(k in metin_lower for k in ['miyokard', 'infarktüs', 'mi ', 'mı ']) \
            or any(k in teshis_metin for k in ['I21', 'I22', 'I23', 'I24']):
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

# ═══════════════════════════════════════════════════════════════════════
# SUT 4.2.15.D — YOAK (Rivaroksaban/Apiksaban/Edoksaban/Dabigatran)
# Helper fonksiyonları + şart-bazlı raporlama (D-1 AF, D-2 DVT/PE)
# ═══════════════════════════════════════════════════════════════════════

# YOAK etken maddeler ve ticari adlar (kombi tespiti için)
_YOAK_ETKEN_LIST = (
    'RIVAROKSABAN', 'RIVAROXABAN',
    'APIKSABAN', 'APIXABAN',
    'EDOKSABAN', 'EDOXABAN', 'EDOKSABAN TOSILAT',
    'DABIGATRAN', 'DABIGATRAN ETEKSILAT',
)
_YOAK_TICARI_LIST = (
    'XARELTO', 'RAZINA',   # rivaroksaban
    'ELIQUIS',             # apiksaban
    'LIXIANA',             # edoksaban
    'PRADAXA',             # dabigatran
)

# 4.2.15.D-1(2) — AF için sağlık kurulu branşları
# (kardiyoloji, iç hastalıkları, göğüs hastalıkları, KVC, nöroloji)
# en az birisi kardiyoloji veya nöroloji olmalı
_YOAK_AF_SK_BRANSLAR = (
    'kardiyolog', 'kardiyoloj',
    'ic hastalik', 'iç hastalık', 'dahiliye',
    'gogus hast', 'göğüs hast',
    'kalp damar', 'kvc', 'kalp ve damar',
    'noroloji', 'nöroloji', 'noroloj',
)
_YOAK_AF_ZORUNLU_BRANS = ('kardiyolog', 'kardiyoloj', 'noroloji', 'nöroloji', 'noroloj')

# 4.2.15.D-2(3) — DVT/PE için sağlık kurulu (nöroloji bu listede YOK!)
_YOAK_DVTPE_SK_BRANSLAR = (
    'kardiyolog', 'kardiyoloj',
    'ic hastalik', 'iç hastalık', 'dahiliye',
    'gogus hast', 'göğüs hast',
    'kalp damar', 'kvc', 'kalp ve damar',
)

# 24 ay sonrası reçete edebilen branşlar (uzman hekim raporu yeterli)
_YOAK_AILE_HEKIMI_KEYS = ('aile hek',)


def _yoak_yas_oku(ilac_sonuc: Dict, metin: str = '') -> Optional[int]:
    """ilac_sonuc.hasta_yasi → int veya metinden yaş kalıbı parse.

    `_osteo_yas_oku` ile aynı mantık (4.2.17 modülünde test edilmiş).
    """
    return _osteo_yas_oku(ilac_sonuc, metin)


def _yoak_endikasyonlari_tespit(metin_lower: str, teshis_metin: str) -> Dict:
    """AF / DVT / PE endikasyon tespiti.

    Returns: {'af': bool, 'dvt': bool, 'pe': bool}
    """
    af = (any(k in metin_lower for k in [
        'atriyal fibrilasyon', 'atrial fibrilasyon',
        'atrium fibrilasyon', 'atrium fibrilasyonu',
        'atriyal fib', 'atrial fib', 'atrium fib',
        'a.fibrilasyon', 'a.fib',
        'paroksismal af', 'kalıcı af', 'kalici af',
        'persistant af', 'kronik af', 'persistan af',
        'non-valvüler af', 'non-valvuler af',
        'nonvalvuler af', 'nonvalvüler af',
        'valvüler olmayan', 'valvuler olmayan',
    ]) or re.search(r'(?:^|[^a-zığüşöç])af(?:[^a-zığüşöç]|$)', metin_lower) is not None
       or 'I48' in teshis_metin)

    dvt = (any(k in metin_lower for k in [
        'derin ven', 'derin venöz', 'derin venoz',
        'venöz tromboz', 'venoz tromboz',
        'venöz tromboembol', 'venoz tromboembol',
    ]) or re.search(r'(?:^|[^a-z])dvt(?:[^a-z]|$)', metin_lower) is not None
       or any(k in teshis_metin for k in ['I80', 'I81', 'I82']))

    pe = (any(k in metin_lower for k in [
        'pulmoner emboli', 'pulmoner tromboz', 'pulmoner emboliz',
        'akciğer emboli', 'akciger emboli',
        'tromboemboli',
    ]) or re.search(r'(?:^|[^a-z])pe(?:[^a-z]|$)', metin_lower) is not None
       or 'I26' in teshis_metin)

    return {'af': af, 'dvt': dvt, 'pe': pe}


def _yoak_risk_faktoru_var(metin_lower: str, teshis_metin: str,
                            yas: Optional[int]) -> Tuple[bool, List[str]]:
    """SUT 4.2.15.D-1(1): risk faktörlerinden en az birisi.

    Faktörler: inme/TIA öyküsü, ≥75 yaş, NYHA Sınıf ≥II, DM, HT.

    Returns: (var_mi, [bulunan_faktörler])
    """
    bulunanlar: List[str] = []

    # 1) İnme veya TIA öyküsü
    if (any(k in metin_lower for k in [
            'inme', 'serebrovaskuler', 'serebrovasküler',
            'serebral iskemi', 'serebral infarkt', 'iskemik inme',
            'gecici iskemik atak', 'geçici iskemik atak',
        ])
        or re.search(r'(?:^|[^a-z])tia(?:[^a-z]|$)', metin_lower) is not None
        or re.search(r'(?:^|[^a-z])tıa(?:[^a-zı]|$)', metin_lower) is not None
        or any(k in teshis_metin for k in ['I63', 'I64', 'I65', 'I66',
                                            'G45', 'G46'])):
        bulunanlar.append('inme/TIA öyküsü')

    # 2) ≥75 yaş
    if yas is not None and yas >= 75:
        bulunanlar.append(f'yaş ≥75 ({yas})')

    # 3) NYHA Sınıf ≥II — kalp yetmezliği
    nyha_match = re.search(r'nyha\s*(?:sinif|sınıf)?\s*([1-4iv]+)', metin_lower)
    if nyha_match:
        nyha_str = nyha_match.group(1)
        if nyha_str in ('2', '3', '4', 'ii', 'iii', 'iv'):
            bulunanlar.append(f'NYHA Sınıf {nyha_str.upper()}')

    # 4) Diabetes mellitus
    if (any(k in metin_lower for k in [
            'diabetes mellitus', 'diyabetes', 'diabetes',
            'diyabet', 'tip 2 dm', 'tip 1 dm', 'tip ii dm', 'tip i dm',
            'dm tip 2', 'dm tip 1',
        ])
        or re.search(r'(?:^|[^a-z])dm(?:[^a-z]|$)', metin_lower) is not None
        or any(k in teshis_metin for k in ['E10', 'E11', 'E12', 'E13', 'E14'])):
        bulunanlar.append('diabetes mellitus')

    # 5) Hipertansiyon
    if (any(k in metin_lower for k in [
            'hipertansiyon', 'hipertans',
            'yuksek tansiyon', 'yüksek tansiyon',
        ])
        or re.search(r'(?:^|[^a-z])ht(?:[^a-z]|$)', metin_lower) is not None
        or any(k in teshis_metin for k in ['I10', 'I11', 'I12', 'I13', 'I15'])):
        bulunanlar.append('hipertansiyon')

    return (len(bulunanlar) > 0, bulunanlar)


def _yoak_kontrendikasyon_var(metin_lower: str) -> Tuple[bool, str]:
    """SUT 4.2.15.D-1(1): orta-ciddi mitral darlık VEYA mekanik protez kapak
    OLMAMALI (kontrendikasyon).

    Returns: (kontrendikasyon_var_mi, açıklama)
    """
    if not metin_lower:
        return (False, '')

    # Biyoprotez kapak istisna — varsa mekanik kapak iddiasını iptal
    biyoprotez = any(k in metin_lower for k in [
        'biyoprotez', 'bioprotez', 'biyolojik kapak', 'biyolojik protez',
    ])

    # Mekanik kapak / mekanik protez
    if any(k in metin_lower for k in [
        'mekanik kapak', 'mekanik protez kapak',
        'mekanik mitral', 'mekanik aort',
        'mechanical valve',
    ]):
        if not biyoprotez:
            return (True, 'mekanik protez kapak')

    # Mitral darlık (orta-ciddi)
    if any(k in metin_lower for k in [
        'orta mitral darlık', 'orta mitral darlik',
        'ciddi mitral darlık', 'ciddi mitral darlik',
        'severe mitral stenos', 'moderate mitral stenos',
        'romatizmal mitral darlık', 'romatizmal mitral darlik',
        'orta-ciddi mitral', 'orta-ağır mitral', 'orta-agir mitral',
    ]):
        return (True, 'orta-ciddi mitral darlık')

    return (False, '')


def _yoak_varfarin_2ay_var(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1)(a) / D-2(1)(b): "en az 2 ay süre ile varfarin".

    NOT: metin_lower zaten `_tr_lower` ile normalize edilmiş olduğundan
    "süre"→"sure" dönüşmüş. Regex'leri ASCII karşılığa göre yaz.
    """
    if not metin_lower:
        return False
    patterns = [
        # "en az 2 ay süre ile varfarin", "iki ay varfarin", "2 ay süreyle varfarin"
        r'(?:en az\s*)?(?:2|iki)\s*ay[^.]{0,30}'
        r'(?:varfa|warfarin|coumadin|kumadin|comadin)',
        # ters yön: "varfarin ... 2 ay"
        r'(?:varfa|warfarin|coumadin|kumadin|comadin)[^.]{0,80}'
        r'(?:en az\s*)?(?:2|iki)\s*ay',
    ]
    return any(re.search(p, metin_lower) for p in patterns)


def _yoak_inr_5_3_tutulamadi(metin_lower: str) -> bool:
    """SUT: "son 5 ölçümün en az 3'ünde INR 2-3 arası tutulamadı"

    Kabul edilen kalıplar:
      - "son 5 ölçüm... 3..."
      - "5 ölçümün ... 3'ünde"
      - "son 5 ... tutulamadı/sağlanamadı"
      - genel "INR ... tutulamadı/sağlanamadı/hedef dışında"
    """
    if not metin_lower:
        return False
    if re.search(r'son\s*5[^.]{0,80}(?:3|ucu|üçü|3.un|3.ün)', metin_lower):
        return True
    if re.search(r'5\s*[oö]l[cç][uü]m[^.]{0,30}3', metin_lower):
        return True
    if re.search(
        r'[iı]nr[^.]{0,80}(?:tutulam|saglanam|sa[gğ]lanam|'
        r'hedef[^.]{0,30}d[ıi][sş][ıi]nda)', metin_lower):
        return True
    return False


def _yoak_varfarin_alti_svo(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1)(b): "varfarin tedavisi altında iken serebrovasküler
    olay geçirenler" → doğrudan YOAK."""
    if not metin_lower:
        return False
    return bool(re.search(
        r'(?:varfa|warfarin|coumadin|kumadin|comadin)[^.]{0,150}'
        r'(?:serebrovaskuler|serebrovasküler|svo|inme|stroke|tia|tıa)',
        metin_lower)) or bool(re.search(
        r'(?:serebrovaskuler|serebrovasküler|svo|inme|stroke)[^.]{0,80}'
        r'(?:varfa|warfarin|coumadin|kumadin|comadin)',
        metin_lower))


def _yoak_idiopatik_pe(metin_lower: str) -> bool:
    """SUT 4.2.15.D-2(2): "tekrarlayan idiopatik pulmoner emboli"."""
    if not metin_lower:
        return False
    return (bool(re.search(
        r'(?:tekrarlay|rekur|rekürren|rekuren)[^.]{0,40}idiopatik[^.]{0,40}'
        r'(?:pulmoner emboli|pe)', metin_lower))
        or bool(re.search(
            r'idiopatik[^.]{0,40}(?:pulmoner emboli|pe)[^.]{0,40}'
            r'(?:tekrar|rekur)', metin_lower)))


def _yoak_homozigot_trombofili(metin_lower: str) -> bool:
    """SUT 4.2.15.D-2(2): "homozigot trombofili"."""
    if not metin_lower:
        return False
    return ('homozigot trombofili' in metin_lower
            or bool(re.search(r'homozigot[^.]{0,40}faktor\s*v\s*leiden',
                              metin_lower))
            or bool(re.search(r'homozigot[^.]{0,40}trombofili', metin_lower)))


def _yoak_aktif_kanser_vte(metin_lower: str, teshis_metin: str) -> bool:
    """SUT 4.2.15.D-2(2): "daha önce VTE geçiren aktif kanser hastaları"

    HEM aktif kanser HEM VTE öyküsü gerekir.
    """
    if not metin_lower:
        return False
    aktif_kanser = (any(k in metin_lower for k in [
        'aktif kanser', 'aktif malign', 'aktif tümör', 'aktif tumor',
        'metastaz', 'metastatik', 'kemoterapi', 'kemoradyoterapi',
        'radyoterapi', 'onkoloji takip', 'onkolojik tedavi',
        'evre 4', 'evre iv', 'ileri evre',
    ]) or any(k.startswith(('C', 'D0')) for k in teshis_metin.split()))

    if not aktif_kanser:
        return False

    vte_oykusu = (any(k in metin_lower for k in [
        'venöz tromboembol', 'venoz tromboembol',
        'derin ven', 'pulmoner emboli',
        'gecirilmis tromboz', 'geçirilmiş tromboz',
        'tromboz oykusu', 'tromboz öyküsü',
        'vte oykusu', 'vte öyküsü',
    ])
    or re.search(r'(?:^|[^a-z])vte(?:[^a-z]|$)', metin_lower) is not None
    or re.search(r'(?:^|[^a-z])dvt(?:[^a-z]|$)', metin_lower) is not None
    or any(k in teshis_metin for k in ['I26', 'I80', 'I81', 'I82']))

    return vte_oykusu


def _yoak_immobil(metin_lower: str) -> bool:
    """SUT 4.2.15.D-2(2): "immobil (raporda nedeni belirtilmek koşuluyla)"."""
    if not metin_lower:
        return False
    return any(k in metin_lower for k in [
        'immobil', 'yatağa bağımlı', 'yataga bagimli',
        'mobilizasyon kayb', 'yatalak',
        'plejik', 'hemiplej', 'parapleji', 'kuadripleji', 'tetrapleji',
    ])


def _yoak_saglik_kurulu_var(metin_lower: str,
                             izinli_branslar: Tuple[str, ...] = _YOAK_AF_SK_BRANSLAR,
                             zorunlu_branslar: Optional[Tuple[str, ...]] = None,
                             ) -> Dict:
    """Sağlık kurulu raporu kontrolü.

    SK ibaresi geçiyor mu? Yetkili branşlardan en az 3 farklı kategori var mı?
    `zorunlu_branslar` verildiyse içlerinden en az birisi olmalı.

    Returns: dict {
        'uygun': bool — bütün şartlar tamam mı,
        'sk_ibaresi': bool — "sağlık kurulu" ibaresi var mı,
        'kategoriler': List[str] — bulunan branş kategorileri,
        'yeterli_brans': bool — ≥3 farklı kategori var mı,
        'zorunlu_brans': bool — zorunlu branş şartı sağlanıyor mu,
    }
    """
    if not metin_lower:
        return {'uygun': False, 'sk_ibaresi': False, 'kategoriler': [],
                'yeterli_brans': False, 'zorunlu_brans': False}

    sk_var = any(k in metin_lower for k in [
        'sağlık kurulu', 'saglik kurulu',
        'sağlık kurul', 'saglik kurul',
    ])

    kategori_eslesme = {
        'kardiyoloji': ('kardiyolog', 'kardiyoloj'),
        'ic_hastalik': ('ic hastalik', 'iç hastalık', 'dahiliye'),
        'gogus_hast': ('gogus hast', 'göğüs hast'),
        'kvc': ('kalp damar', 'kvc', 'kalp ve damar'),
        'noroloji': ('noroloji', 'nöroloji', 'noroloj'),
    }

    bulunan_kategoriler: List[str] = []
    for kategori, anahtarlar in kategori_eslesme.items():
        if any(a in izinli_branslar for a in anahtarlar):
            if any(a in metin_lower for a in anahtarlar):
                bulunan_kategoriler.append(kategori)

    yeterli_brans = len(bulunan_kategoriler) >= 3

    zorunlu_var = True
    if zorunlu_branslar:
        zorunlu_var = any(z in metin_lower for z in zorunlu_branslar)

    uygun = sk_var and yeterli_brans and zorunlu_var
    return {
        'uygun': uygun,
        'sk_ibaresi': sk_var,
        'kategoriler': bulunan_kategoriler,
        'yeterli_brans': yeterli_brans,
        'zorunlu_brans': zorunlu_var,
    }


def _yoak_kombi_var(ilac_sonuc: Dict) -> Tuple[bool, str]:
    """SUT 4.2.15.D-1(4): aynı reçetede 2 farklı YOAK varsa BEDELİ KARŞILANMAZ.

    Mevcut ilacın YOAK kategorisini hariç tutarak diğer ilaçlarda YOAK arar.
    """
    mevcut_etken = (ilac_sonuc.get('etkin_madde') or '').upper()
    mevcut_ad = (ilac_sonuc.get('ilac_adi') or '').upper()

    # Mevcut ilacın hangi YOAK ailesi olduğunu tespit et
    mevcut_aileler: set = set()
    for et in _YOAK_ETKEN_LIST:
        if et in mevcut_etken or et in mevcut_ad:
            mevcut_aileler.add(et.split()[0])
    for tic in _YOAK_TICARI_LIST:
        if tic in mevcut_ad:
            mevcut_aileler.add(tic)

    # Diğer ilaçları topla
    diger = ilac_sonuc.get('recete_ilaclari') or []
    diger_str = ' '.join([
        str(i.get('ad', '') if isinstance(i, dict) else i) for i in diger
    ]).upper()
    diger_etken = ilac_sonuc.get('diger_etken_maddeler') or []
    diger_str += ' ' + ' '.join([str(x) for x in diger_etken]).upper()
    diger_ad = ilac_sonuc.get('diger_ilac_adlari') or []
    diger_str += ' ' + ' '.join([str(x) for x in diger_ad]).upper()

    if not diger_str.strip():
        return (False, '')

    # Diğer YOAK var mı? (mevcut aile dışında)
    for et in _YOAK_ETKEN_LIST:
        if et in diger_str:
            aile = et.split()[0]
            if aile not in mevcut_aileler:
                return (True, et)
    for tic in _YOAK_TICARI_LIST:
        if tic in diger_str and tic not in mevcut_aileler:
            return (True, tic)
    return (False, '')


# ─── Atomik ibare detektörleri (rapor için her ibare tek tek listelenir) ──

def _yoak_atom_inme(metin_lower: str, teshis_metin: str) -> bool:
    """SUT 4.2.15.D-1(1) atomik: 'inme öyküsü' (TIA hariç)."""
    return (any(k in metin_lower for k in [
                'inme', 'serebrovaskuler', 'serebrovasküler',
                'serebral iskemi', 'serebral infarkt', 'iskemik inme',
                'svo', 'stroke']) or
            any(k in teshis_metin for k in ['I63', 'I64', 'I65', 'I66']))


def _yoak_atom_tia(metin_lower: str, teshis_metin: str) -> bool:
    """SUT 4.2.15.D-1(1) atomik: 'geçici iskemik atak (TIA)'."""
    return (any(k in metin_lower for k in [
                'gecici iskemik atak', 'geçici iskemik atak',
                'transient ischem']) or
            re.search(r'(?:^|[^a-z])tia(?:[^a-z]|$)', metin_lower) is not None or
            re.search(r'(?:^|[^a-z])tıa(?:[^a-zı]|$)', metin_lower) is not None or
            any(k in teshis_metin for k in ['G45', 'G46']))


def _yoak_atom_inme_tia(metin_lower: str, teshis_metin: str) -> bool:
    """Geriye uyumlu birleşik kontrol — VEYA: inme veya TIA."""
    return _yoak_atom_inme(metin_lower, teshis_metin) or \
           _yoak_atom_tia(metin_lower, teshis_metin)


def _yoak_atom_yas_75(yas: Optional[int]) -> Optional[bool]:
    """SUT 4.2.15.D-1(1): '≥75 yaş'. Yaş bilinmiyorsa None döner."""
    if yas is None:
        return None
    return yas >= 75


def _yoak_atom_nyha_2_ustu(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1): 'kalp yetmezliği NYHA Sınıf ≥II'."""
    m = re.search(r'nyha\s*(?:sinif|sınıf)?\s*([1-4iv]+)', metin_lower)
    if not m:
        return False
    s = m.group(1)
    return s in ('2', '3', '4', 'ii', 'iii', 'iv')


def _yoak_atom_dm(metin_lower: str, teshis_metin: str) -> bool:
    """SUT: 'diabetes mellitus'."""
    return (any(k in metin_lower for k in [
                'diabetes mellitus', 'diyabetes', 'diabetes', 'diyabet',
                'tip 2 dm', 'tip 1 dm', 'tip ii dm', 'tip i dm',
                'dm tip 2', 'dm tip 1']) or
            re.search(r'(?:^|[^a-z])dm(?:[^a-z]|$)', metin_lower) is not None or
            any(k in teshis_metin for k in ['E10', 'E11', 'E12', 'E13', 'E14']))


def _yoak_atom_ht(metin_lower: str, teshis_metin: str) -> bool:
    """SUT: 'hipertansiyon'."""
    return (any(k in metin_lower for k in [
                'hipertansiyon', 'hipertans',
                'yuksek tansiyon', 'yüksek tansiyon']) or
            re.search(r'(?:^|[^a-z])ht(?:[^a-z]|$)', metin_lower) is not None or
            any(k in teshis_metin for k in ['I10', 'I11', 'I12', 'I13', 'I15']))


def _yoak_atom_mitral_darlik(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1): 'orta-ciddi mitral darlık' VAR mı (kontrendikasyon).

    DİKKAT: ibareden sonra 50 karakter içinde 'olmayan/olmadığı/yok/yoktur'
    varsa NEGATİF ek tespit edilir → ibare aslında YOK demek olur (False).
    Örn: "ORTA CİDDİ MİTRAL DARLIK KAPAK OLMADIĞI" → False (mitral YOK).
    """
    if not metin_lower:
        return False
    pozitif_anahtarlar = [
        'orta mitral darlık', 'orta mitral darlik',
        'ciddi mitral darlık', 'ciddi mitral darlik',
        'severe mitral stenos', 'moderate mitral stenos',
        'romatizmal mitral darlık', 'romatizmal mitral darlik',
        'orta-ciddi mitral', 'orta-ağır mitral', 'orta-agir mitral',
    ]
    negatif_ekler = ('olmay', 'yoktur', 'olmadi', 'olmadı',
                     'saptanma', 'tespit edilmem', 'gozlenmem',
                     'gözlenmem')
    for k in pozitif_anahtarlar:
        idx = metin_lower.find(k)
        if idx < 0:
            continue
        # Sonrasında 50 char içinde negatif ek var mı?
        sonraki_50 = metin_lower[idx + len(k):idx + len(k) + 50]
        if any(neg in sonraki_50 for neg in negatif_ekler):
            continue  # bu eşleşme aslında negatif (mitral YOK), atla
        # Pozitif eşleşme — başka pozitif anahtar başka yerde negatif değilse
        # ekstra güvence: aynı pozisyon önce 30 karakter geriye "olm" var mı?
        # Genelde gereksiz, ama "olmayan ciddi mitral darlık" gibi tersi
        oncesi_30 = metin_lower[max(0, idx - 30):idx]
        if any(neg in oncesi_30 for neg in negatif_ekler):
            continue
        return True
    return False


def _yoak_atom_nonvalvuler_lafzen(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1: rapor metninde 'non-valvüler AF' / 'nonvalvuler AF'
    lafzen direkt yazıyor mu (örtük kabul DEĞİL — explicit declaration).

    'Non-valvüler AF' raporda lafzen geçtiğinde hekim valve hastalığını
    (mitral darlık, mekanik protez kapak) açıkça dışlamış demektir; bu
    SUT'un (1) maddesindeki "mitral darlık VEYA mekanik kapak OLMAYAN
    nonvalvuler AF" şartının lafzen ikrarıdır.
    """
    if not metin_lower:
        return False
    # 'non-valvüler' / 'nonvalvuler' / 'non valvuler' / 'nonvalv' varyantları
    return bool(re.search(
        r'non[\s\-]?valv[uü]ler', metin_lower))


def _yoak_atom_mitral_darlik_yok_ibaresi(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1): rapor metninde 'mitral darlık YOK/OLMAYAN/
    OLMADIĞI/yoktur/saptanmadı/gözlenmedi' lafzen ibaresi var mı
    (örtük kabul yasağı).

    'Non-valvüler AF' lafzen geçiyorsa (hekim AF tipini valve-dışı olarak
    direkt deklare etmiş) bu da geçerli bir negatif ikrar sayılır."""
    if not metin_lower:
        return False
    # 'non-valvüler' lafzen direkt → açık negatif ikrar
    if _yoak_atom_nonvalvuler_lafzen(metin_lower):
        return True
    # Negatif ek varyantları (Türkçe çekim)
    neg_pat = (r'(?:olmay|olmadi|olmadı|yoktur|yok\b|'
               r'saptanm|tespit\s+edilmem|gozlenmem|gözlenmem)')
    return bool(re.search(
        rf'mitral[^.]{{0,40}}(?:darl[ıi]k|stenos)[^.]{{0,40}}{neg_pat}',
        metin_lower)) or bool(re.search(
        rf'{neg_pat}[^.]{{0,40}}mitral[^.]{{0,40}}(?:darl[ıi]k|stenos)',
        metin_lower))


def _yoak_atom_mekanik_kapak(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1): 'mekanik protez kapak' VAR mı (kontrendikasyon).

    DİKKAT: ibareden sonra 50 karakter içinde 'olmayan/olmadığı/yok' varsa
    negatif ek → False döner. Örn: "MEKANİK PROTEZ KAPAK OLMAYAN" → False.

    NOT: Biyoprotez kapak _yoak_atom_biyoprotez ile ayrı sorgulanır;
    biyoprotez VARSA bu fonksiyon True dönse bile kontrendikasyon değildir.
    """
    if not metin_lower:
        return False
    pozitif_anahtarlar = [
        'mekanik kapak', 'mekanik protez kapak',
        'mekanik mitral', 'mekanik aort',
        'mechanical valve',
    ]
    negatif_ekler = ('olmay', 'yoktur', 'olmadi', 'olmadı',
                     'saptanma', 'tespit edilmem', 'gozlenmem',
                     'gözlenmem')
    for k in pozitif_anahtarlar:
        idx = metin_lower.find(k)
        if idx < 0:
            continue
        sonraki_50 = metin_lower[idx + len(k):idx + len(k) + 50]
        if any(neg in sonraki_50 for neg in negatif_ekler):
            continue  # negatif ek var, ibare YOK demek
        oncesi_30 = metin_lower[max(0, idx - 30):idx]
        if any(neg in oncesi_30 for neg in negatif_ekler):
            continue
        return True
    return False


def _yoak_atom_mekanik_kapak_yok_ibaresi(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1): rapor metninde 'mekanik kapak YOK/OLMAYAN/yoktur'
    lafzen ibaresi var mı (örtük kabul yasağı).

    'Non-valvüler AF' lafzen geçiyorsa (hekim AF tipini valve-dışı olarak
    direkt deklare etmiş) bu da geçerli bir negatif ikrar sayılır."""
    if not metin_lower:
        return False
    # 'non-valvüler' lafzen direkt → açık negatif ikrar (valve hastalığı yok)
    if _yoak_atom_nonvalvuler_lafzen(metin_lower):
        return True
    return bool(re.search(
        r'mekanik[^.]{0,30}(?:kapak|protez|valve)[^.]{0,30}'
        r'(?:olmay|yoktur|yok\b|saptanm|tespit\s+edilmem)',
        metin_lower)) or bool(re.search(
        r'(?:olmay|yoktur|yok)[^.]{0,30}mekanik[^.]{0,30}(?:kapak|protez)',
        metin_lower)) or 'mekanik protez kapağı olmayan' in metin_lower or \
        'mekanik protez kapagi olmayan' in metin_lower


def _yoak_atom_biyoprotez(metin_lower: str) -> bool:
    """Biyoprotez kapak (mekanik istisnası — kontrendikasyon DEĞİL)."""
    return any(k in metin_lower for k in [
        'biyoprotez', 'bioprotez', 'biyolojik kapak', 'biyolojik protez',
    ])


def _yoak_atom_haftalik_inr(metin_lower: str) -> bool:
    """SUT 4.2.15.D-1(1)(a): 'en az birer hafta ara ile' yapılan ölçümler."""
    if not metin_lower:
        return False
    return bool(re.search(
        r'(?:birer|1\s*er|haftal[ıi]k)\s*hafta', metin_lower)) or \
           bool(re.search(r'hafta(?:l[ıi]k)?\s*ara', metin_lower)) or \
           bool(re.search(r'haftada\s*bir', metin_lower))


def _yoak_atom_apiksaban_kapsam_disi(etkin_madde: str) -> bool:
    """SUT 4.2.15.D-1(3) Mülga: 'apiksaban bu madde kapsamı dışı ödenmez'.

    Mülga olduğu için bu şart artık etkili değil — sadece info amaçlı
    raporlanır. True döner = ilaç apiksaban (bu uyarı bilgilendirme amaçlı).
    """
    e = (etkin_madde or '').upper()
    return 'APIKSABAN' in e or 'APIXABAN' in e


def _yoak_atom_sk_ibaresi(metin_lower: str, rapor_kodu: str = '') -> bool:
    """SK rapor tespiti — iki yöntem (mantıksal OR):

    1. Lafzen 'sağlık kurulu' ibaresi metinde geçiyor (en güvenilir)
    2. Rapor kodu 04.03.* (YOAK Medula kodu) — Medula'da YOAK için
       SK zorunludur, başka rapor tipi YOAK rapor kodu üretmez.

    NOT: Rapor metninde "sağlık kurulu" lafzı yazılmaz çoğu zaman
    (Medula ekranındaki başlık tipinden anlaşılır). Bu yüzden
    rapor_kodu 04.03 ise SK varsayım yapılır.
    """
    if any(k in metin_lower for k in [
        'sağlık kurulu', 'saglik kurulu',
        'sağlık kurul', 'saglik kurul',
    ]):
        return True
    # Medula rapor kodu çıkarsama: 04.03 YOAK için SK zorunlu
    if rapor_kodu and str(rapor_kodu).strip().startswith('04.03'):
        return True
    return False


def _yoak_atom_brans_var(metin_lower: str, anahtarlar: Tuple[str, ...]) -> bool:
    """Belirli bir uzmanlık branşı (varyantlarıyla) metinde geçiyor mu."""
    return any(a in metin_lower for a in anahtarlar)


# ─── Parametrik heyet doktorları kontrolü ─────────────────────────────
# Botanik EOS RaporDoktor tablosundan ilac_sonuc['heyet_doktorlari']
# alanına yüklenir (GUI batch tarafından).
# Liste şekli: [{'ad': '...', 'brans': '...', 'tckn': '...'}, ...]

# YOAK yetkili branş anahtar listeleri (normalize edilmiş key formu)
_YOAK_HEYET_KEYS_D1 = ('kardiyoloji', 'ic_hastaliklari', 'gogus_hastaliklari',
                       'kalp_damar_cerrahisi', 'noroloji')
_YOAK_HEYET_KEYS_D2_ILK24 = ('kardiyoloji', 'ic_hastaliklari',
                              'gogus_hastaliklari', 'kalp_damar_cerrahisi')


def _yoak_brans_normalize(brans: str) -> str:
    """Bir BransAdi'yi normalize edilmiş anahtara eşle.

    Yetkili olmayan branşlar boş string döner.
    """
    if not brans:
        return ''
    bl = _tr_lower(brans)
    if 'kardiyoloj' in bl:
        return 'kardiyoloji'
    if ('dahiliye' in bl or 'ic hastalik' in bl or 'iç hastalık' in bl
            or 'i̇ç hastalık' in bl):
        return 'ic_hastaliklari'
    if 'gogus' in bl or 'göğüs' in bl:
        return 'gogus_hastaliklari'
    if 'kalp' in bl and ('damar' in bl or 'kvc' in bl):
        return 'kalp_damar_cerrahisi'
    if bl.strip() == 'kvc':
        return 'kalp_damar_cerrahisi'
    if 'noroloj' in bl or 'nöroloj' in bl:
        return 'noroloji'
    return ''


def _yoak_heyet_brans_dagilimi(ilac_sonuc: Dict,
                                 izinli_keys: Tuple[str, ...]) -> Dict:
    """RaporDoktor heyetinden yetkili branş dağılımını çıkar.

    Returns:
        {
            'toplam_yetkili': N (yetkili branştaki doktor sayısı),
            'farkli_brans_sayisi': M (kaç farklı yetkili dal),
            'brans_doktor_sayisi': {'kardiyoloji': 2, ...},
            'max_ayni_dal': max sayim,
            'doktor_listesi': [(ad, brans_norm), ...],
            'yetersiz_kaynak': True (heyet_doktorlari yoksa),
        }
    """
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not heyet:
        return {
            'toplam_yetkili': 0, 'farkli_brans_sayisi': 0,
            'brans_doktor_sayisi': {}, 'max_ayni_dal': 0,
            'doktor_listesi': [], 'yetersiz_kaynak': True,
        }
    sayim: Dict[str, int] = {}
    yetkili = []
    for d in heyet:
        bn = _yoak_brans_normalize(d.get('brans', ''))
        if bn and bn in izinli_keys:
            sayim[bn] = sayim.get(bn, 0) + 1
            yetkili.append((d.get('ad', ''), bn))
    return {
        'toplam_yetkili': sum(sayim.values()),
        'farkli_brans_sayisi': len(sayim),
        'brans_doktor_sayisi': sayim,
        'max_ayni_dal': max(sayim.values()) if sayim else 0,
        'doktor_listesi': yetkili,
        'yetersiz_kaynak': False,
    }


def _yoak_atom_heyet_sk_var(ilac_sonuc: Dict,
                             rapor_kodu: str) -> Tuple['SartDurumu', str]:
    """SK raporu var mı — heyet doktor sayısı ≥3 + rapor_kodu kontrolü."""
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    rk = (rapor_kodu or '').strip()
    if rk.startswith('04.03'):
        return (SartDurumu.VAR,
                f'rapor_kodu=04.03 (Medula SK) + heyet {len(heyet)} doktor')
    if heyet and len(heyet) >= 3:
        return (SartDurumu.VAR,
                f'heyet {len(heyet)} doktor (SK ≥3 doktor şartı sağlandı)')
    if heyet:
        return (SartDurumu.YOK,
                f'heyet sadece {len(heyet)} doktor (SK ≥3 doktor gerekli)')
    return (SartDurumu.KONTROL_EDILEMEDI,
            "RaporDoktor DB'de bulunamadı — manuel doğrulama")


def _yoak_atom_heyet_3_uzman_toplam(
        ilac_sonuc: Dict,
        izinli_keys: Tuple[str, ...]) -> Tuple['SartDurumu', str]:
    """SUT D-1(2): "5 daldan en az ÜÇÜNÜN bulunduğu" — TOPLAM yetkili
    doktor sayısı ≥3 (aynı dal veya farklı dal fark etmez).

    SUT lafzı yorumu: heyette toplamda ≥3 uzman olmalı, bunlar yetkili
    5 daldan herhangi biri/birkaçından gelebilir. "3 kardiyolog" veya
    "2 kard + 1 iç hast" veya "1 kard + 1 iç + 1 göğüs" hepsi geçerli.

    NOT: D-2(3) farklı — "aynı dal 3 VEYA farklı 3" alt-OR (bkz.
    _yoak_atom_heyet_ayni_dalda_3 + _yoak_atom_heyet_farkli_3_dal).
    """
    dag = _yoak_heyet_brans_dagilimi(ilac_sonuc, izinli_keys)
    if dag['yetersiz_kaynak']:
        return (SartDurumu.KONTROL_EDILEMEDI,
                "RaporDoktor DB'de bulunamadı — manuel doğrulama")
    toplam = dag['toplam_yetkili']
    brans_str = ', '.join(
        sorted([f"{k}({v})"
                for k, v in dag['brans_doktor_sayisi'].items()])) or \
        '(yetkili dal yok)'
    if toplam >= 3:
        return (SartDurumu.VAR,
                f'toplam {toplam} yetkili uzman: {brans_str}')
    return (SartDurumu.YOK,
            f'sadece {toplam} yetkili uzman (3 gerekli): {brans_str}')


def _yoak_atom_heyet_farkli_3_dal(
        ilac_sonuc: Dict,
        izinli_keys: Tuple[str, ...]) -> Tuple['SartDurumu', str]:
    """SUT D-2(3) alt-OR (b): "herhangi 3 farklı uzmanlık dalından" —
    yani 3 FARKLI yetkili dalda en az 1'er uzman."""
    dag = _yoak_heyet_brans_dagilimi(ilac_sonuc, izinli_keys)
    if dag['yetersiz_kaynak']:
        return (SartDurumu.KONTROL_EDILEMEDI,
                "RaporDoktor DB'de bulunamadı — manuel doğrulama")
    n = dag['farkli_brans_sayisi']
    brans_str = ', '.join(
        sorted(dag['brans_doktor_sayisi'].keys())) or '(yetkili dal yok)'
    if n >= 3:
        return (SartDurumu.VAR,
                f'{n} farklı yetkili branş: {brans_str}')
    return (SartDurumu.YOK,
            f'sadece {n} farklı yetkili branş: {brans_str}')


# Geriye uyumluluk için eski isim (deprecated, _yoak_atom_heyet_farkli_3_dal
# kullan)
_yoak_atom_heyet_yeterli_brans = _yoak_atom_heyet_farkli_3_dal


def _yoak_atom_heyet_ayni_dalda_3(
        ilac_sonuc: Dict,
        izinli_keys: Tuple[str, ...]) -> Tuple['SartDurumu', str]:
    """Heyette aynı yetkili uzm dalda ≥3 doktor var mı (D-2 alt-OR a)."""
    dag = _yoak_heyet_brans_dagilimi(ilac_sonuc, izinli_keys)
    if dag['yetersiz_kaynak']:
        return (SartDurumu.KONTROL_EDILEMEDI,
                "RaporDoktor DB'de bulunamadı — manuel doğrulama")
    max_ayni = dag['max_ayni_dal']
    if max_ayni >= 3:
        en_buyuk = max(dag['brans_doktor_sayisi'].items(),
                        key=lambda x: x[1])
        return (SartDurumu.VAR,
                f'aynı dalda {max_ayni} doktor: {en_buyuk[0]}')
    return (SartDurumu.YOK,
            f'aynı dalda max {max_ayni} doktor (3 gerekli)')


# ─── D-a yolu atomik ibareler (4.2.15.D-1(1)(a) / D-2(1)(b)) ───────────

def _yoak_atom_da_son_5_olcum(metin_lower: str) -> bool:
    """SUT D-a/(b) ibare: 'son 5 ölçüm'."""
    if not metin_lower:
        return False
    return bool(re.search(r'son\s*5\s*[oö]l[cç][uü]m', metin_lower)) or \
           bool(re.search(r'5\s*[oö]l[cç][uü]m', metin_lower))


def _yoak_atom_da_3unde_tutulamadi(metin_lower: str) -> bool:
    """SUT: 'en az 3'ünde ... tutulamadığı'."""
    if not metin_lower:
        return False
    return bool(re.search(
        r'(?:en az\s*)?3.{0,4}(?:nde|de|sinde|.+nde)?[^.]{0,30}'
        r'(?:tutulam|saglanam|sa[gğ]lanam)', metin_lower)) or \
           bool(re.search(r'5.{0,4}3', metin_lower))


def _yoak_atom_da_inr_2_3_hedef(metin_lower: str) -> bool:
    """SUT: 'INR değerinin 2-3 arasında'."""
    if not metin_lower:
        return False
    return bool(re.search(r'[iı]nr[^.]{0,40}2[- ]+3[^.]{0,15}aras', metin_lower)) or \
           bool(re.search(r'[iı]nr[^.]{0,15}hedef', metin_lower)) or \
           bool(re.search(r'[iı]nr[^.]{0,30}2[-– ]+3', metin_lower))


def _yoak_atom_da_varfarin_kesildi(metin_lower: str) -> bool:
    """SUT: 'varfarin kesilerek ... tedavisine geçilebilir'."""
    if not metin_lower:
        return False
    return bool(re.search(
        r'(?:varfa|warfarin|coumadin|kumadin)[^.]{0,40}'
        r'(?:kes(?:il|ip|erek)|dur(?:dur|duruld|uld))', metin_lower))


# ─── D-b yolu atomik ibareler (4.2.15.D-1(1)(b)) ───────────────────────

def _yoak_atom_db_varfarin_altinda(metin_lower: str) -> bool:
    """SUT: 'varfarin tedavisi altında iken'."""
    if not metin_lower:
        return False
    return bool(re.search(
        r'(?:varfa|warfarin|coumadin|kumadin)\s*(?:tedavisi)?\s*alt',
        metin_lower))


def _yoak_atom_db_svo(metin_lower: str, teshis_metin: str = '') -> bool:
    """SUT: 'serebrovasküler olay geçirenlerde'."""
    if not metin_lower:
        return False
    return (any(k in metin_lower for k in [
                'serebrovaskuler', 'serebrovasküler', 'svo', 'inme',
                'iskemik inme', 'serebral iskemi', 'serebral infarkt',
                'stroke']) or
            re.search(r'(?:^|[^a-z])tia(?:[^a-z]|$)', metin_lower) is not None or
            any(k in teshis_metin for k in ['I63', 'I64', 'I65', 'I66',
                                              'G45', 'G46']))


# ─── E grubu atomik (SK raporu — ilk 24 ay) ────────────────────────────

def _yoak_atom_e_uzman_recete(doktor_brans: str,
                                izinli: Tuple[str, ...]) -> bool:
    """SUT (2): 'bu uzman hekimlerince reçete edilmesi'.

    Reçete eden hekim D-1 izinli uzman branşları arasında mı?
    """
    if not doktor_brans:
        return False
    bl = _tr_lower(doktor_brans)
    return any(a in bl for a in izinli)


# ─── F grubu atomik (24 ay sonrası alt yol) ────────────────────────────

def _yoak_atom_f1_24ay_doldu(ilac_sonuc: Dict) -> Tuple['SartDurumu', str]:
    """SUT 4.2.15.D-1(2) son cümle: 'Bu raporun süresi en fazla 24 ay olup,
    bu süre dolduktan sonra, aile hekimi veya uzman hekim tarafından reçete
    edilebilir.'

    Hastanın en eski YOAK reçete tarihinden aktif reçete tarihine kadar
    geçen takvim ayı farkı ≥24 ise 24 ay tamamlanmış sayılır.

    `ilac_sonuc` beklenen alanlar (GUI tarafından doldurulur):
      - hasta_yoak_ilk_recete_tarihi: en eski YOAK RxKayitTarihi
        (datetime / 'YYYY-MM-DD' / 'DD.MM.YYYY' kabul eder)
      - recete_tarihi: aktif reçete tarihi (aynı formatlar)

    Returns:
        (SartDurumu, neden_string)
        VAR: ≥24 ay geçmiş → aile hekimi/uzman yetkili
        YOK: <24 ay → SK raporu zorunlu, aile hekimi yetkisiz
        KONTROL_EDILEMEDI: hasta DB geçmişi yok / tarih parse edilemedi
    """
    from datetime import datetime
    ilk_t = ilac_sonuc.get('hasta_yoak_ilk_recete_tarihi')
    aktif_t = ilac_sonuc.get('recete_tarihi')

    def _parse(t):
        if t is None:
            return None
        if isinstance(t, datetime):
            return t
        if hasattr(t, 'year') and hasattr(t, 'month'):  # date
            return datetime(t.year, t.month, getattr(t, 'day', 1))
        s = str(t).strip()
        if not s:
            return None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
                     '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d',
                     '%d.%m.%Y %H:%M:%S', '%d.%m.%Y'):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt)
            except (ValueError, TypeError):
                continue
        return None

    if not ilk_t:
        return (SartDurumu.KONTROL_EDILEMEDI,
                'Hasta YOAK geçmişi DB\'de bulunamadı '
                '— manuel doğrulama gerekli')
    if not aktif_t:
        return (SartDurumu.KONTROL_EDILEMEDI,
                'Aktif reçete tarihi okunamadı — manuel doğrulama')

    ilk_dt = _parse(ilk_t)
    aktif_dt = _parse(aktif_t)
    if not ilk_dt or not aktif_dt:
        return (SartDurumu.KONTROL_EDILEMEDI,
                f'Tarih parse hatası (ilk={ilk_t!r}, aktif={aktif_t!r})')

    ay_farki = ((aktif_dt.year - ilk_dt.year) * 12
                 + (aktif_dt.month - ilk_dt.month))
    # gün eşiği: ilk_dt.day > aktif_dt.day ise ay henüz tam dolmamış
    if aktif_dt.day < ilk_dt.day:
        ay_farki -= 1
    ilk_str = ilk_dt.strftime('%d.%m.%Y')
    if ay_farki >= 24:
        return (SartDurumu.VAR,
                f'İlk YOAK reçetesi: {ilk_str} → {ay_farki} ay geçmiş (≥24)')
    return (SartDurumu.YOK,
            f'İlk YOAK reçetesi: {ilk_str} → sadece {ay_farki} ay '
            '(24 ay tamamlanmadı, SK raporu zorunlu)')


def _yoak_atom_f_aile_hekimi(ilac_sonuc: Dict) -> Tuple[bool, str]:
    """24 ay sonrası: aile hekimi de reçete edebilir.

    Aile hekimi tespiti 3 yol (ARB'deki kalıbın aynısı, herhangi biri yeterli):
      1. Doktorun branş listesinde 'AİLE HEK...' geçer (sertifikalı pratisyen)
      2. Reçetenin yazıldığı kurum ASM/AHM/Aile Sağlığı Merkezi
      3. Tesis kodu (Hastane.HastaneKodu) AILE_HEKIMLIGI_TESIS_KODLARI listesi

    Returns:
        (aile_hekimi_mi, neden_string)
    """
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    kurum_adi = (ilac_sonuc.get('kurum_adi') or '').upper()
    tesis_kodu = str(ilac_sonuc.get('tesis_kodu') or '').strip()

    brans_aile_hek = (
        'AILE HEK' in doktor_brans
        or 'AİLE HEK' in doktor_brans
        or 'AİLE HEKİMLİĞİ' in doktor_brans
        or 'AILE HEKIMLIGI' in doktor_brans
    )
    kurum_asm = bool(kurum_adi) and (
        'AILE SAGLIGI' in kurum_adi
        or 'AİLE SAĞLIĞI' in kurum_adi
        or 'AILE SAĞLIĞI' in kurum_adi
        or 'AİLE SAGLIGI' in kurum_adi
        or 'AILE HEKIMLIGI' in kurum_adi
        or 'AİLE HEKİMLİĞİ' in kurum_adi
        or any(tok in kurum_adi.split() for tok in ('ASM', 'AHM'))
    )
    tesis_aile_hek = bool(tesis_kodu) and (
        tesis_kodu in AILE_HEKIMLIGI_TESIS_KODLARI
    )

    aile_hekimi = brans_aile_hek or kurum_asm or tesis_aile_hek

    nedenler = []
    if brans_aile_hek:
        nedenler.append(f'branş: {doktor_brans[:30]}')
    if kurum_asm:
        nedenler.append(f'kurum: {kurum_adi[:40]}')
    if tesis_aile_hek:
        nedenler.append(f'tesis kodu: {tesis_kodu}')
    neden = ' + '.join(nedenler) if nedenler else (doktor_brans or '(boş)')
    return aile_hekimi, neden


# ─── D-2 endikasyon atomikleri ─────────────────────────────────────────

def _yoak_atom_dvt(metin_lower: str, teshis_metin: str) -> bool:
    """SUT D-2: DVT (derin ven trombozu)."""
    return (any(k in metin_lower for k in [
                'derin ven', 'derin venöz', 'derin venoz',
                'venöz tromboz', 'venoz tromboz']) or
            re.search(r'(?:^|[^a-z])dvt(?:[^a-z]|$)', metin_lower) is not None or
            any(k in teshis_metin for k in ['I80', 'I81', 'I82']))


def _yoak_atom_pe(metin_lower: str, teshis_metin: str) -> bool:
    """SUT D-2: PE (pulmoner emboli)."""
    return (any(k in metin_lower for k in [
                'pulmoner emboli', 'pulmoner tromboz', 'pulmoner emboliz',
                'akciğer emboli', 'akciger emboli', 'tromboemboli']) or
            re.search(r'(?:^|[^a-z])pe(?:[^a-z]|$)', metin_lower) is not None or
            'I26' in teshis_metin)


def _yoak_atom_tekrarlayan_pe_dvt(metin_lower: str) -> bool:
    """SUT D-2(1)(a): 'tekrarlayan PE/DVT önlenmesi'."""
    return bool(re.search(
        r'(?:tekrarlay|rekur|rekürren)[^.]{0,50}(?:pe|emboli|dvt|tromboz)',
        metin_lower))


def _yoak_atom_akut_dvt_sonrasi(metin_lower: str) -> bool:
    """SUT D-2(1)(a) — alt-madde 2: 'akut DVT sonrası tekrarlayan DVT ve
    Pulmoner Embolizmin (PE) önlenmesinde'.

    Rapor metninde 'akut' + 'dvt/derin ven' + 'tekrar/önle' ibareleri birlikte
    aranır.
    """
    has_akut = 'akut' in metin_lower
    has_dvt = any(k in metin_lower for k in ['dvt', 'derin ven'])
    has_tekrar = any(k in metin_lower for k in [
        'tekrar', 'rekur', 'rekürren', 'önle', 'profilaks',
    ])
    return has_akut and has_dvt and has_tekrar


def _yoak_atom_recete_hekim_yetkili(doktor_brans: str,
                                     dval: str = 'd1') -> Optional[bool]:
    """Reçete eden hekim YOAK reçete edebilir mi (D-1 veya D-2 listesi).

    D-1: kard/iç hast/göğüs/KVC/nöroloji + 24 ay sonrası aile hekimi.
    D-2: aynı liste (nöroloji 24 ay sonrası eklenir).

    24 ay durumu metinden parse edilemediği için aile hekimi şu an
    KE varsayılır → None dönülür (manuel doğrulama).
    """
    if not doktor_brans:
        return None
    bl = _tr_lower(doktor_brans)
    uzman_anahtarlar = (
        'kardiyolog', 'kardiyoloj',
        'ic hastalik', 'iç hastalık', 'dahiliye',
        'gogus hast', 'göğüs hast',
        'kalp damar', 'kvc', 'kalp ve damar',
        'noroloji', 'nöroloji', 'noroloj',
    )
    if any(a in bl for a in uzman_anahtarlar):
        return True
    if any(a in bl for a in _YOAK_AILE_HEKIMI_KEYS):
        return None  # 24 ay tamamlanmış mı bilmiyoruz
    return False


# ─── EK-4/F Madde 53-54 atomikleri (ortopedi profilaksi yolu) ──────────
# SUT: rivaroksaban (Madde 54) + dabigatran (Madde 53). Apiksaban/edoksaban
# EK-4/F kapsamı YOK (D-2 yoluna düşer).

_YOAK_EK4F_ORTOPEDI_KEYS = (
    'ortopedi', 'ortopedik', 'travmatolog', 'travmatoloji',
)

def _yoak_ek4f_atom_elektif_replasman(metin_lower: str) -> bool:
    """SUT EK-4/F: 'elektif kalça VEYA diz total eklem replasmanı'."""
    has_elektif = ('elektif' in metin_lower or 'planlı' in metin_lower
                   or 'planli' in metin_lower)
    has_kalca_diz = any(k in metin_lower for k in [
        'kalça', 'kalca', 'diz', 'kalça eklem', 'kalca eklem',
        'diz eklem', 'total kalça', 'total kalca', 'total diz',
    ])
    has_replasman = any(k in metin_lower for k in [
        'replasman', 'protez', 'artroplast', 'eklem cerrahi',
        'tep ', 'tha ', 'tka ',  # total endoprotez, total hip/knee arthroplasty
    ])
    # Güçlü tek-ibare eşleşmeleri (cerrahi bağlamı kesinleştirir)
    has_full_phrase = any(k in metin_lower for k in [
        'total kalça replasman', 'total kalca replasman',
        'total diz replasman', 'total kalça protez',
        'total diz protez', 'kalça artroplast', 'diz artroplast',
        'elektif kalça', 'elektif diz',
    ])
    if has_full_phrase:
        return True
    return has_kalca_diz and (has_replasman or has_elektif)


def _yoak_ek4f_lokalizasyon(metin_lower: str) -> Optional[str]:
    """Rapor metninden lokalizasyon: 'diz' / 'kalca' / None (KE).

    Hem diz hem kalça geçiyorsa daha güçlü bağlam'a göre seçilir; eşit ise
    None (manuel doğrulama).
    """
    diz_kanit = sum(1 for k in [
        'diz eklem', 'total diz', 'diz protez', 'diz artroplast',
        'elektif diz', 'tka ', 'gonartroz',
    ] if k in metin_lower)
    kalca_kanit = sum(1 for k in [
        'kalça eklem', 'kalca eklem', 'total kalça', 'total kalca',
        'kalça protez', 'kalca protez', 'kalça artroplast',
        'kalca artroplast', 'elektif kalça', 'elektif kalca',
        'tha ', 'koksartroz',
    ] if k in metin_lower)
    # Zayıf tek-kelime fallback
    if diz_kanit == 0 and 'diz' in metin_lower:
        diz_kanit = 1
    if kalca_kanit == 0 and ('kalça' in metin_lower or 'kalca' in metin_lower):
        kalca_kanit = 1
    if diz_kanit > kalca_kanit:
        return 'diz'
    if kalca_kanit > diz_kanit:
        return 'kalca'
    return None


def _yoak_ek4f_atom_dvt_profilaksi(metin_lower: str) -> bool:
    """SUT EK-4/F: 'derin ven trombozunun profilaksisinde'."""
    return any(k in metin_lower for k in [
        'dvt profilaks', 'derin ven trombozu profilaks',
        'derin ven trombozunun profilaks', 'tromboz profilaks',
        'venöz tromboemboli profilaks', 'venoz tromboemboli profilaks',
        'vte profilaks',
    ])


def _yoak_ek4f_atom_ortopedi_rapor(doktor_brans: str) -> bool:
    """SUT EK-4/F: 'ortopedi uzman hekimlerince düzenlenen rapor'."""
    if not doktor_brans:
        return False
    bl = _tr_lower(doktor_brans)
    return any(k in bl for k in _YOAK_EK4F_ORTOPEDI_KEYS)


def _yoak_ek4f_atom_miktar_uygun(etken: str, lokalizasyon: Optional[str],
                                  kutu: float,
                                  gunluk_doz: Optional[float] = None
                                  ) -> Tuple[Optional[bool], str]:
    """SUT EK-4/F miktar/süre limiti.

    Rivaroksaban: diz ≤1 kutu, kalça ≤3 kutu (kutu bazlı SUT lafzı)
    Dabigatran:   diz ≤10 gün, kalça ≤35 gün (SUT lafzen GÜN bazlı)
       gün = (kutu × 60 cap/kutu) / günlük_doz (cap/gün)
       günlük_doz bilinmiyorsa DDD profilaksi varsayımı: 2 cap/gün (220 mg)

    Returns (uygun_mu, açıklama). uygun_mu=None → KE (lokalizasyon/doz yok).
    """
    et = (etken or '').upper()
    if lokalizasyon is None:
        return None, (f'Lokalizasyon (diz/kalça) raporda tespit edilemedi — '
                      f'miktar limiti manuel doğrulama (kutu: {kutu:.0f})')
    if 'RIVAROKSABAN' in et:
        if lokalizasyon == 'diz':
            limit = 1
        else:  # kalça
            limit = 3
        if kutu <= limit:
            return True, (f'Rivaroksaban {lokalizasyon}: {kutu:.0f} kutu '
                          f'(≤{limit} limit OK)')
        return False, (f'Rivaroksaban {lokalizasyon}: {kutu:.0f} kutu '
                       f'limit aşıldı (>{limit})')
    if 'DABIGATRAN' in et or 'DABİGATRAN' in et:
        # SUT lafzı: diz ≤10 gün, kalça ≤35 gün — GÜN bazlı hesap
        # Pradaxa kutu içeriği TR pazarında 60 kapsül (standart).
        # DVT profilaksi günlük dozu 220 mg = 2 cap 110 mg / gün (DDD).
        KUTU_KAPSUL = 60
        DDD_VARSAYIM = 2.0  # cap/gün (profilaksi DDD)
        try:
            gd = float(gunluk_doz) if gunluk_doz else 0.0
        except (TypeError, ValueError):
            gd = 0.0
        if gd <= 0:
            gd_efektif = DDD_VARSAYIM
            doz_kaynak = f'DDD varsayım ({DDD_VARSAYIM:.0f} cap/gün)'
        else:
            gd_efektif = gd
            doz_kaynak = f'reçete günlük doz ({gd:g} cap/gün)'
        toplam_cap = kutu * KUTU_KAPSUL
        tedavi_gun = toplam_cap / gd_efektif if gd_efektif > 0 else 0
        if lokalizasyon == 'diz':
            limit_gun = 10
        else:  # kalça
            limit_gun = 35
        if tedavi_gun <= limit_gun:
            return True, (
                f'Dabigatran {lokalizasyon}: {kutu:.0f} kutu × '
                f'{KUTU_KAPSUL} cap / {doz_kaynak} = {tedavi_gun:.1f} gün '
                f'(SUT ≤{limit_gun} gün OK)')
        return False, (
            f'Dabigatran {lokalizasyon}: {kutu:.0f} kutu × '
            f'{KUTU_KAPSUL} cap / {doz_kaynak} = {tedavi_gun:.1f} gün '
            f'SUT limiti aşıldı (>{limit_gun} gün)')
    return None, f'Etken madde EK-4/F kapsamı dışı: {et}'


def _yoak_ek4f_etken_madde_uygun(etken: str) -> bool:
    """EK-4/F sadece rivaroksaban + dabigatran için geçerli.

    Apiksaban/edoksaban için kapsam yok — D-2 yoluna fallback edilmeli.
    """
    et = (etken or '').upper()
    return ('RIVAROKSABAN' in et or 'DABIGATRAN' in et
            or 'DABİGATRAN' in et)


# ─── Grup değerlendirme yardımcısı ──────────────────────────────────────

def _yoak_grup_durumu(grup_sartlar: List[SartSonuc],
                       veya: bool = False) -> SartDurumu:
    """Bir grup (aynı `grup` adı) altındaki şartları toplayıp grubun durumu.

    veya=False (AND): hepsi VAR olmalı; bir tane YOK varsa YOK; KE varsa KE.
    veya=True  (OR≥1): en az 1 VAR varsa VAR; hiç VAR yok ama KE varsa KE;
                       hepsi YOK ise YOK.
    """
    if not grup_sartlar:
        return SartDurumu.NA
    var = sum(1 for s in grup_sartlar if s.durum == SartDurumu.VAR)
    yok = sum(1 for s in grup_sartlar if s.durum == SartDurumu.YOK)
    ke = sum(1 for s in grup_sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI)
    if veya:
        if var > 0:
            return SartDurumu.VAR
        if ke > 0:
            return SartDurumu.KONTROL_EDILEMEDI
        return SartDurumu.YOK
    # AND
    if yok > 0:
        return SartDurumu.YOK
    if ke > 0:
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.VAR


# ═══════════════════════════════════════════════════════════════════════
# YOAK alt-dal kontrolleri (D-1 AF, D-2 DVT/PE)
# ═══════════════════════════════════════════════════════════════════════

def _yoak_d1_af_kontrol(metin_lower: str, teshis_metin: str, birlesik: str,
                        ilac_sonuc: Dict, yas: Optional[int],
                        rapor_kodu: str, sartlar: List[SartSonuc],
                        detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.15.D-1 (AF) — 26 atomik şart, 8 grup (kullanıcı onaylı 2026-05-08).

    Yapı: G AND A AND B AND C AND D AND (E OR F)
      G  Kombi yasağı [4.2.15.D-1(4)]
      A  Endikasyon (non-valvüler AF)
      B  Kontrendikasyon (her ikisi YOK olmalı): mitral darlık + mekanik kapak
      C  Risk faktörü (≥1): inme | TIA | ≥75 | NYHA≥II | DM | HT
      D  Varfarin yolu (a) VEYA (b):
         (a) 6 atomik AND: 2ay + ≥1hafta + son5 + ≥3'ünde + INR2-3 + kesildi
         (b) 2 atomik AND: varfarin altı + SVO
      E  SK raporu — ilk 24 ay (5 atomik AND)
      F  24 ay sonrası alt yol (3 atomik AND, F1 KE)
    """
    sut_kurali = ('SUT 4.2.15.D-1 — Non-valvüler AF\'de YOAK '
                  '(atomik şart taraması, 26 ampul)')
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    doktor_brans = ilac_sonuc.get('doktor_uzmanligi') or ''

    # SUT 4.2.15.D-1(1) lafzı sırası: önce risk faktörü, sonra kontrendikasyon,
    # sonra non-valvüler AF, sonra (a)/(b) varfarin yolu.

    # ── GRUP C: Risk faktörü (≥1 olmalı) [SUT (1) - 1.] ────────────────
    # SUT lafzı 4 alt-grup, üst seviye OR ≥1:
    #   (a) {inme VEYA TIA öyküsü}  — alt-paralel
    #   (b) ≥75 yaş
    #   (c) NYHA Sınıf ≥II KY
    #   (d) {DM VEYA HT}            — alt-paralel
    # Alt-pair'ler kendi gruplarında veya_grubu=True; üst seviye 4-way OR
    # `_yoak_genel_sonuc_atomik` / `_sema_grup_matematigi` ust_or_coklu ile
    # birleştirilir (matematik: ≥1 of 4 sub-groups = ≥1 of 6 atoms, eşdeğer).
    g_rf_a = 'Risk fakt. (a) — inme/TIA [(1)]'
    g_rf_b = 'Risk fakt. (b) — ≥75 yaş [(1)]'
    g_rf_c = 'Risk fakt. (c) — NYHA≥II KY [(1)]'
    g_rf_d = 'Risk fakt. (d) — DM/HT [(1)]'
    inme = _yoak_atom_inme(metin_lower, teshis_metin)
    sartlar.append(SartSonuc(
        'İnme öyküsü',
        SartDurumu.VAR if inme else SartDurumu.YOK,
        'inme/SVO/I63-66 tespit edildi' if inme else 'inme ibaresi yok',
        'rapor_metni/teshis', grup=g_rf_a, veya_grubu=True))
    tia = _yoak_atom_tia(metin_lower, teshis_metin)
    sartlar.append(SartSonuc(
        'Geçici iskemik atak (TIA) öyküsü',
        SartDurumu.VAR if tia else SartDurumu.YOK,
        'TIA/G45-46 tespit edildi' if tia else 'TIA ibaresi yok',
        'rapor_metni/teshis', grup=g_rf_a, veya_grubu=True))

    yas_75 = _yoak_atom_yas_75(yas)
    if yas_75 is None:
        sartlar.append(SartSonuc(
            '≥75 yaş', SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi',
            grup=g_rf_b, veya_grubu=True))
    else:
        sartlar.append(SartSonuc(
            '≥75 yaş',
            SartDurumu.VAR if yas_75 else SartDurumu.YOK,
            f'Hasta yaşı: {yas}', 'hasta_yasi',
            grup=g_rf_b, veya_grubu=True))

    nyha = _yoak_atom_nyha_2_ustu(metin_lower)
    sartlar.append(SartSonuc(
        'NYHA Sınıf ≥II (kalp yetmezliği)',
        SartDurumu.VAR if nyha else SartDurumu.YOK,
        'NYHA ≥II ibaresi tespit edildi' if nyha
        else 'NYHA Sınıf ≥II ibaresi yok',
        'rapor_metni', grup=g_rf_c, veya_grubu=True))

    dm = _yoak_atom_dm(metin_lower, teshis_metin)
    sartlar.append(SartSonuc(
        'Diabetes mellitus',
        SartDurumu.VAR if dm else SartDurumu.YOK,
        'DM/E10-14 tespit edildi' if dm else 'DM ibaresi yok',
        'rapor_metni/teshis', grup=g_rf_d, veya_grubu=True))

    ht = _yoak_atom_ht(metin_lower, teshis_metin)
    sartlar.append(SartSonuc(
        'Hipertansiyon',
        SartDurumu.VAR if ht else SartDurumu.YOK,
        'HT/I10-15 tespit edildi' if ht else 'HT ibaresi yok',
        'rapor_metni/teshis', grup=g_rf_d, veya_grubu=True))

    # ── GRUP B: Kontrendikasyon [SUT (1) - 2.] ────────────────────────
    # SUT lafzı: "mitral darlık VEYA mekanik kapak OLMAYAN"
    # DeMorgan: NOT(mitral OR mekanik) = NOT-mitral AND NOT-mekanik
    # Görsel paralel (SUT "veya" lafzı), mantıksal AND (her ikisi YOK).
    #
    # ÖRTÜK KABUL YASAĞI: rapor metninde "mitral darlık YOK/olmayan" gibi
    # lafzen NEGATİF ibare aranır. Sessizlik = KONTROL_EDILEMEDI (manuel).
    #   Pozitif ibare (mitral darlık VAR) → şart YOK (kontrendikasyon)
    #   Negatif ibare ("mitral darlık olmayan/yok") → şart VAR (lafzen ikrar)
    #   Hiçbiri → KONTROL_EDILEMEDI (rapor sessiz, manuel doğrulama)
    g_kontr = 'Kontrendikasyon — yok olmalı [(1)] [paralel]'

    # Mitral darlık 3-durumlu kontrol
    md_var = _yoak_atom_mitral_darlik(metin_lower)
    md_yok_ibaresi = _yoak_atom_mitral_darlik_yok_ibaresi(metin_lower)
    if md_var:
        sartlar.append(SartSonuc(
            'Orta-ciddi mitral darlık YOK', SartDurumu.YOK,
            'orta-ciddi/ciddi/romatizmal mitral darlık ibaresi tespit edildi '
            '(kontrendikasyon)', 'rapor_metni', grup=g_kontr))
    elif md_yok_ibaresi:
        sartlar.append(SartSonuc(
            'Orta-ciddi mitral darlık YOK', SartDurumu.VAR,
            '"mitral darlık olmayan/yok" ibaresi rapor metninde tespit edildi',
            'rapor_metni', grup=g_kontr))
    else:
        sartlar.append(SartSonuc(
            'Orta-ciddi mitral darlık YOK', SartDurumu.KONTROL_EDILEMEDI,
            'rapor metninde mitral darlık ibaresi (var/yok) yok — '
            'manuel doğrulama gerekli',
            'rapor_metni', grup=g_kontr))

    # Mekanik kapak 3-durumlu kontrol (biyoprotez istisnası dahil)
    mk_var = _yoak_atom_mekanik_kapak(metin_lower)
    biyo_var = _yoak_atom_biyoprotez(metin_lower)
    mk_yok_ibaresi = _yoak_atom_mekanik_kapak_yok_ibaresi(metin_lower)
    if mk_var and not biyo_var:
        sartlar.append(SartSonuc(
            'Mekanik protez kapak YOK', SartDurumu.YOK,
            'mekanik kapak/protez ibaresi var, biyoprotez ibaresi yok '
            '(kontrendikasyon)', 'rapor_metni', grup=g_kontr))
    elif mk_var and biyo_var:
        sartlar.append(SartSonuc(
            'Mekanik protez kapak YOK', SartDurumu.VAR,
            'mekanik kapak ibaresi var ama biyoprotez kaydı da var → '
            'istisna (biyoprotez kontrendike değil)',
            'rapor_metni', grup=g_kontr))
    elif mk_yok_ibaresi:
        sartlar.append(SartSonuc(
            'Mekanik protez kapak YOK', SartDurumu.VAR,
            '"mekanik protez kapak olmayan/yok" ibaresi rapor metninde tespit',
            'rapor_metni', grup=g_kontr))
    else:
        sartlar.append(SartSonuc(
            'Mekanik protez kapak YOK', SartDurumu.KONTROL_EDILEMEDI,
            'rapor metninde mekanik kapak ibaresi (var/yok) yok — '
            'manuel doğrulama gerekli',
            'rapor_metni', grup=g_kontr))

    # ── GRUP A: Endikasyon (AF) [SUT (1) - 3., zorunlu] ───────────────
    g_end = 'Endikasyon (4.2.15.D-1)'
    sartlar.append(SartSonuc(
        'Non-valvüler atriyal fibrilasyon', SartDurumu.VAR,
        'Metin/ICD\'de AF tespit edildi (D-1 dalı tetiklendi)',
        'rapor_metni/teshis', grup=g_end))

    # ── GRUP D: Varfarin yolu (a) VEYA (b) [üst-OR] ──────────────────
    # (a): 6 atomik AND — SUT lafzındaki her ibare ayrı ampul
    g_varfa_a = 'Varfarin yolu (a) — 2ay+INR5/3+kesilerek [(1)(a)]'
    g_varfa_b = 'Varfarin yolu (b) — varfarin altı SVO [(1)(b)]'

    # Da: parser sonuçları
    da1_2ay = _yoak_varfarin_2ay_var(metin_lower)
    da2_haftalik = _yoak_atom_haftalik_inr(metin_lower)
    da3_son5 = _yoak_atom_da_son_5_olcum(metin_lower)
    da4_3unde = _yoak_atom_da_3unde_tutulamadi(metin_lower)
    da5_inr23 = _yoak_atom_da_inr_2_3_hedef(metin_lower)
    da6_kesildi = _yoak_atom_da_varfarin_kesildi(metin_lower)
    # Birleşik "INR son 5/3 tutulamadı" tespiti — eski parser (yedek):
    inr_5_3 = _yoak_inr_5_3_tutulamadi(metin_lower)

    # Da KRİTİK ŞARTLAR (6 atom AND — mantık şeması ile birebir):
    # Da1, Da2, Da3, Da4, Da5, Da6 — hepsi g_varfa_a (kritik AND grup)
    # Parser zayıf olan Da2/Da6 sessizse KE → grup ŞÜPHELİ (UYGUN_DEGIL değil).

    # Da1 — 2 ay varfarin (kritik)
    sartlar.append(SartSonuc(
        '≥2 ay süre ile varfarin kullanımı',
        SartDurumu.VAR if da1_2ay else SartDurumu.YOK,
        '"2 ay varfarin" tespit' if da1_2ay
        else '"2 ay varfarin" ibaresi yok',
        'rapor_metni', grup=g_varfa_a))
    # Da2 — ≥1 hafta arayla ölçüm (kritik AND, parser zayıf → sessiz=KE)
    sartlar.append(SartSonuc(
        'INR ölçümleri ≥1 hafta arayla yapıldı',
        SartDurumu.VAR if da2_haftalik else SartDurumu.KONTROL_EDILEMEDI,
        'haftalık ölçüm ibaresi tespit' if da2_haftalik
        else 'haftalık ölçüm ibaresi yok — manuel doğrulama',
        'rapor_metni', grup=g_varfa_a))
    # Da3 — son 5 ölçüm (kritik)
    sartlar.append(SartSonuc(
        'Son 5 ölçüm yapıldı',
        SartDurumu.VAR if (da3_son5 or inr_5_3) else SartDurumu.YOK,
        '"son 5 ölçüm" tespit' if (da3_son5 or inr_5_3)
        else '"son 5 ölçüm" ibaresi yok',
        'rapor_metni', grup=g_varfa_a))
    # Da4 — ≥3'ünde tutulamadı (kritik)
    sartlar.append(SartSonuc(
        '≥3 ölçümde INR tutulamadı',
        SartDurumu.VAR if (da4_3unde or inr_5_3) else SartDurumu.YOK,
        '"3\'ünde tutulamadı" tespit' if (da4_3unde or inr_5_3)
        else '"3\'ünde tutulamadı" ibaresi yok',
        'rapor_metni', grup=g_varfa_a))
    # Da5 — INR 2-3 hedef (kritik)
    sartlar.append(SartSonuc(
        'INR 2-3 hedef aralık',
        SartDurumu.VAR if (da5_inr23 or inr_5_3) else SartDurumu.YOK,
        '"INR 2-3" hedef tespit' if (da5_inr23 or inr_5_3)
        else '"INR 2-3" ibaresi yok',
        'rapor_metni', grup=g_varfa_a))
    # Da6 — varfarin kesilerek (kritik AND, parser zayıf → sessiz=KE)
    sartlar.append(SartSonuc(
        'Varfarin kesilerek YOAK\'a geçildi',
        SartDurumu.VAR if da6_kesildi else SartDurumu.KONTROL_EDILEMEDI,
        '"varfarin kesilerek" tespit' if da6_kesildi
        else '"varfarin kesilerek" ibaresi yok — manuel doğrulama',
        'rapor_metni', grup=g_varfa_a))

    # Db: Varfarin altı SVO — 2 atomik AND
    db1_alti = _yoak_atom_db_varfarin_altinda(metin_lower)
    db2_svo = _yoak_atom_db_svo(metin_lower, teshis_metin)
    svo_alti = _yoak_varfarin_alti_svo(metin_lower)  # birleşik fallback

    # Db1 — varfarin altında
    sartlar.append(SartSonuc(
        'Varfarin tedavisi altındaydı',
        SartDurumu.VAR if (db1_alti or svo_alti) else SartDurumu.YOK,
        '"varfarin altında" ibaresi tespit' if (db1_alti or svo_alti)
        else '"varfarin altında" ibaresi yok',
        'rapor_metni', grup=g_varfa_b))
    # Db2 — SVO geçirdi
    sartlar.append(SartSonuc(
        'Serebrovasküler olay (SVO/inme/TIA) geçirdi',
        SartDurumu.VAR if (db2_svo or svo_alti) else SartDurumu.YOK,
        'SVO/inme/TIA ibaresi tespit' if (db2_svo or svo_alti)
        else 'SVO/inme/TIA ibaresi yok',
        'rapor_metni/teshis', grup=g_varfa_b))

    # ── GRUP E: SK raporu — ilk 24 ay [(2)] [AND, 3 atomik] ───────────
    # PARAMETRİK kontrol: RaporDoktor tablosundan heyet doktorlarını çek,
    # branş listesi ve farklı dal sayısı üzerinden SUT şartlarını doğrula.
    # rapor_kodu 04.03 (YOAK Medula kodu) Medula otoritesi — fallback.
    # feedback_rapor_metni_uzman_ibare_yasak memory'sinde belirtilen
    # "rapor metninde branş ibare arama" kaldırıldı (2026-05-12).
    g_e = 'SK raporu — ilk 24 ay [(2)]'
    medula_sk_var = bool(rapor_kodu and rapor_kodu.startswith('04.03'))
    dag_e = _yoak_heyet_brans_dagilimi(ilac_sonuc, _YOAK_HEYET_KEYS_D1)

    # E1: SK raporu var (heyet ≥3 doktor veya Medula 04.03)
    e1_durum, e1_neden = _yoak_atom_heyet_sk_var(ilac_sonuc, rapor_kodu)
    sartlar.append(SartSonuc(
        'SK raporu (heyet ≥3 doktor)',
        e1_durum, e1_neden,
        'RaporDoktor/rapor_kodu', grup=g_e))

    # E2: kard VEYA nöro zorunlu (D-1 SUT lafzı — heyet branş listesi)
    has_kard = dag_e['brans_doktor_sayisi'].get('kardiyoloji', 0) > 0
    has_noro = dag_e['brans_doktor_sayisi'].get('noroloji', 0) > 0
    if has_kard or has_noro:
        sartlar.append(SartSonuc(
            'Kardiyoloji VEYA Nöroloji uzmanı (zorunlu)',
            SartDurumu.VAR,
            f'Heyette {"kardiyoloji" if has_kard else ""}'
            f'{" + " if has_kard and has_noro else ""}'
            f'{"nöroloji" if has_noro else ""} uzman var',
            'RaporDoktor', grup=g_e))
    elif medula_sk_var:
        sartlar.append(SartSonuc(
            'Kardiyoloji VEYA Nöroloji uzmanı (zorunlu)',
            SartDurumu.VAR,
            'Medula 04.03 = kard/nöro zorunlu (otorite — heyet DB boş)',
            'rapor_kodu', grup=g_e))
    elif dag_e['yetersiz_kaynak']:
        sartlar.append(SartSonuc(
            'Kardiyoloji VEYA Nöroloji uzmanı (zorunlu)',
            SartDurumu.KONTROL_EDILEMEDI,
            "RaporDoktor DB'de bulunamadı — manuel doğrulama",
            'RaporDoktor', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'Kardiyoloji VEYA Nöroloji uzmanı (zorunlu)',
            SartDurumu.YOK,
            'Heyette kardiyoloji veya nöroloji uzmanı yok',
            'RaporDoktor', grup=g_e))

    # E3: 5 daldan TOPLAM ≥3 uzman (D-1 SUT lafzı)
    # "kardiyoloji, iç hastalıkları, göğüs hastalıkları, kalp damar
    # cerrahisi ve nöroloji uzman hekimlerinden en az ÜÇÜNÜN bulunduğu"
    # → toplam ≥3 uzman; aynı dal/farklı dal kompozisyonu önemsiz.
    # NOT: D-2(3) farklı (aynı 3 VEYA farklı 3 alt-OR) — bkz _yoak_d2.
    e3_durum, e3_neden = _yoak_atom_heyet_3_uzman_toplam(
        ilac_sonuc, _YOAK_HEYET_KEYS_D1)
    if e3_durum == SartDurumu.KONTROL_EDILEMEDI and medula_sk_var:
        # Heyet boş ama Medula otoritesi → VAR varsay
        e3_durum, e3_neden = (
            SartDurumu.VAR,
            'Medula 04.03 = ≥3 uzman onayı zorunlu (otorite — heyet DB boş)')
    sartlar.append(SartSonuc(
        'Toplam ≥3 uzman (kard/iç/göğüs/KVC/nöro)',
        e3_durum, e3_neden,
        'RaporDoktor', grup=g_e))

    # Bilgi grup: Heyet branş listesi (hesap dışı, görüntüleme)
    g_sk_brans = 'SK — heyet branşları (bilgi)'
    if dag_e['doktor_listesi']:
        for ad, brans_norm in dag_e['doktor_listesi']:
            sartlar.append(SartSonuc(
                f'{brans_norm}: {ad[:30]}',
                SartDurumu.VAR,
                f'Heyet: {ad} ({brans_norm})',
                'RaporDoktor', grup=g_sk_brans))
    # Eski 'bulunan_brans_sayisi' uyumluluk (F2 ve sonraki kod kullanıyor)
    bulunan_brans_sayisi = dag_e['farkli_brans_sayisi']
    kard_veya_noro = has_kard or has_noro

    g_e_bilgi = 'SK raporu (D-1) — manuel doğrulama (bilgi)'
    # E5: bu uzman hekimlerce reçete edildi
    e_uzman_recete = _yoak_atom_e_uzman_recete(
        doktor_brans, _YOAK_AF_SK_BRANSLAR)
    sartlar.append(SartSonuc(
        'Bu uzman hekimlerce reçete edildi',
        SartDurumu.VAR if e_uzman_recete else SartDurumu.YOK,
        f'Doktor branşı: {doktor_brans} (yetkili)' if e_uzman_recete
        else f'Doktor branşı yetkili değil: {doktor_brans or "(boş)"}',
        'doktor_uzmanligi', grup=g_e))
    # E BİLGİ (parser zayıf): E4 — 1 yıl süre
    sartlar.append(SartSonuc(
        '1 yıl süreli rapor',
        SartDurumu.KONTROL_EDILEMEDI,
        'Rapor süresi parse edilemiyor — manuel doğrulama',
        'rapor_metni', grup=g_e_bilgi))

    # ── GRUP F: 24 ay sonrası alt yol [(2) son cümle] [AND, 2 atomik] ──
    # SUT D-1(2) son cümle: "Bu raporun süresi en fazla 24 ay olup, bu süre
    # dolduktan sonra, aile hekimi veya uzman hekim tarafından reçete
    # edilebilir." Yani rapor metninde uzman branş İBARESİ aramaya gerek
    # YOK — reçete eden doktorun branşı (aile hk veya uzman) yeterli.
    g_f = '24 ay sonrası alt yol [(2)]'
    # F1: ilk 24 ay tamamlandı — hasta DB sorgusundan tespit
    f1_durum, f1_neden = _yoak_atom_f1_24ay_doldu(ilac_sonuc)
    sartlar.append(SartSonuc(
        'İlk 2 rapor süresi (24 ay) tamamlanmış',
        f1_durum, f1_neden,
        'hasta_yoak_gecmisi', grup=g_f))
    # F2 (eski "rapor metninde uzman ibare" şartı KALDIRILDI — SUT'ta yok)
    # F3: aile hekimi VEYA uzman reçete edebilir
    # Aile hekimi tespiti: branş + ASM kurum + tesis kodu (3 yol)
    aile_hk, aile_neden = _yoak_atom_f_aile_hekimi(ilac_sonuc)
    if aile_hk:
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.VAR,
            f'Aile hekimi reçete (24 ay sonrası yetki): {aile_neden}',
            'doktor_uzmanligi/tesis', grup=g_f))
    elif e_uzman_recete:
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.VAR,
            f'Uzman hekim reçete: {doktor_brans}',
            'doktor_uzmanligi', grup=g_f))
    else:
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.YOK,
            f'Doktor ne aile hekimi ne uzman: {aile_neden}',
            'doktor_uzmanligi/tesis', grup=g_f))

    # ── BİLGİ: Apiksaban Mülga (3) ────────────────────────────────────
    if _yoak_atom_apiksaban_kapsam_disi(etkin_madde):
        sartlar.append(SartSonuc(
            'Apiksaban kapsam dışı endikasyon [(3) Mülga]',
            SartDurumu.NA,
            'Madde MÜLGA — uygulanmıyor (bilgilendirme)',
            'sut_4.2.15.D-1(3)',
            grup='Apiksaban özel (bilgi)'))

    # ── GRUP G: Kombi yasağı [(4)] — SUT lafzında EN SON şart ─────────
    # Kombi VAR ise zaten ana fonksiyon erken UYGUN_DEGIL döndü.
    # Buraya geldiyse kombi YOK → VAR olarak ekle.
    sartlar.append(SartSonuc(
        'Aynı reçetede 2. YOAK YOK',
        SartDurumu.VAR,
        'Aynı reçetede başka YOAK yok',
        'recete_ilaclari',
        grup='Kombi yasağı [(4)]'))

    # NOT: SUT D-1(4) "Dabigatran/rivaroksaban/edoksaban/apiksaban kombine
    # kullanılması halinde bedeli karşılanmaz" — kombi yasağı (yukarıda).
    # D-1'de "rapor yenileme" maddesi SUT lafzında YOK (sadece D-2(4)'te var).

    detaylar.update({'alt_dal': '4.2.15.D-1', 'endikasyon': 'AF',
                     'varfarin_2ay': da1_2ay,
                     'inr_5_3_tutulamadi': inr_5_3, 'svo_alti': svo_alti})

    # ── Genel Sonuç (grup-bazlı agregasyon) ──────────────────────────
    return _yoak_genel_sonuc_atomik(sartlar, detaylar, sut_kurali,
                                     birlesik=birlesik, anahtar='fibrilasyon')


def _yoak_d2_dvtpe_kontrol(metin_lower: str, teshis_metin: str, birlesik: str,
                           ilac_sonuc: Dict, yas: Optional[int],
                           rapor_kodu: str, end_dvt: bool, end_pe: bool,
                           sartlar: List[SartSonuc],
                           detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.15.D-2 (DVT/PE) — 22 atomik şart, 7 grup (kullanıcı onaylı 2026-05-08).

    Yapı: G AND A2 AND H AND (D OR I) AND (E2 OR F2)
      G   Kombi yasağı
      A2  Yetişkin (≥18 yaş)
      H   Endikasyon (≥1): DVT | PE | tekrarlayan PE/DVT önlenmesi
      D   Varfarin yolu (D-1 ile aynı 6 atomik AND)
      I   İstisna grubu (≥1): idiopatik PE | homozigot trombofili | VTE+kanser | immobil
      E2  SK raporu — ilk 24 ay (4 atomik AND, NÖROLOJİ YOK)
      F2  24 ay sonrası (3 atomik AND — F2-2 nöroloji eklenir)
    """
    sut_kurali = ('SUT 4.2.15.D-2 — DVT/PE\'de YOAK '
                  '(atomik şart taraması, 22 ampul)')
    doktor_brans = ilac_sonuc.get('doktor_uzmanligi') or ''

    # ── GRUP A2: Yetişkin hasta ───────────────────────────────────────
    g_yas = 'Yetişkin [(1)]'
    if yas is None:
        sartlar.append(SartSonuc(
            'Yetişkin hasta (≥18 yaş)',
            SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi', grup=g_yas))
    elif yas < 18:
        sartlar.append(SartSonuc(
            'Yetişkin hasta (≥18 yaş)',
            SartDurumu.YOK,
            f'Hasta yaşı {yas} — pediatrik (SUT D-2 yetişkin)',
            'hasta_yasi', grup=g_yas))
    else:
        sartlar.append(SartSonuc(
            'Yetişkin hasta (≥18 yaş)',
            SartDurumu.VAR,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_yas))

    # ── GRUP H: Endikasyon (≥1, OR) [(1)(a)] — 4 atom (mevzuat lafzı) ──
    # SUT D-2(1)(a): "DVT tedavisi ile akut DVT sonrası tekrarlayan
    # DVT ve PE'nin önlenmesinde VEYA PE tedavisi ile tekrarlayan PE
    # ve DVT'nin önlenmesinde kullanılır" — 4 alt-endikasyon, OR ≥1.
    g_end = 'Endikasyon ≥1 [(1)(a)]'
    # I1 — DVT tedavisi
    sartlar.append(SartSonuc(
        'DVT tedavisi',
        SartDurumu.VAR if end_dvt else SartDurumu.YOK,
        'DVT/derin ven/I80-82 tespit' if end_dvt else 'DVT ibaresi yok',
        'rapor_metni/teshis', grup=g_end, veya_grubu=True))
    # I2 — Akut DVT sonrası tekrarlayan DVT/PE önlenmesi
    akut_dvt_sonrasi = _yoak_atom_akut_dvt_sonrasi(metin_lower)
    sartlar.append(SartSonuc(
        'Akut DVT sonrası tekrarlayan DVT/PE önlenmesi',
        SartDurumu.VAR if akut_dvt_sonrasi else SartDurumu.YOK,
        'akut DVT + tekrar/önleme ibaresi tespit' if akut_dvt_sonrasi
        else 'akut DVT sonrası tekrar/önleme ibaresi yok',
        'rapor_metni', grup=g_end, veya_grubu=True))
    # I3 — PE tedavisi
    sartlar.append(SartSonuc(
        'PE tedavisi',
        SartDurumu.VAR if end_pe else SartDurumu.YOK,
        'PE/akciğer emboli/I26 tespit' if end_pe else 'PE ibaresi yok',
        'rapor_metni/teshis', grup=g_end, veya_grubu=True))
    # I4 — Tekrarlayan PE/DVT önlenmesi
    tekrar = _yoak_atom_tekrarlayan_pe_dvt(metin_lower)
    sartlar.append(SartSonuc(
        'Tekrarlayan PE/DVT önlenmesi',
        SartDurumu.VAR if tekrar else SartDurumu.YOK,
        'tekrarlayan PE/DVT ibaresi tespit' if tekrar
        else 'tekrarlayan PE/DVT ibaresi yok',
        'rapor_metni', grup=g_end, veya_grubu=True))

    # ── GRUP D: Varfarin yolu [(1)(b)] [AND, 6 atomik] ────────────────
    g_varfa = 'Varfarin yolu — 2ay+INR5/3+kesilerek [(1)(b)]'
    da1_2ay = _yoak_varfarin_2ay_var(metin_lower)
    da2_haftalik = _yoak_atom_haftalik_inr(metin_lower)
    da3_son5 = _yoak_atom_da_son_5_olcum(metin_lower)
    da4_3unde = _yoak_atom_da_3unde_tutulamadi(metin_lower)
    da5_inr23 = _yoak_atom_da_inr_2_3_hedef(metin_lower)
    da6_kesildi = _yoak_atom_da_varfarin_kesildi(metin_lower)
    inr_5_3 = _yoak_inr_5_3_tutulamadi(metin_lower)

    # 6 atom AND — Da1, Da2, Da3, Da4, Da5, Da6 (mantık şeması birebir)
    # Parser zayıf Da2/Da6 sessizse KE → ŞÜPHELİ (UYGUN_DEGIL değil)
    sartlar.append(SartSonuc(
        '≥2 ay süre ile varfarin kullanımı',
        SartDurumu.VAR if da1_2ay else SartDurumu.YOK,
        '"2 ay varfarin" tespit' if da1_2ay else '"2 ay varfarin" yok',
        'rapor_metni', grup=g_varfa))
    sartlar.append(SartSonuc(
        'INR ölçümleri ≥1 hafta arayla',
        SartDurumu.VAR if da2_haftalik else SartDurumu.KONTROL_EDILEMEDI,
        'haftalık ölçüm tespit' if da2_haftalik
        else 'haftalık ölçüm ibaresi yok — manuel doğrulama',
        'rapor_metni', grup=g_varfa))
    sartlar.append(SartSonuc(
        'Son 5 ölçüm yapıldı',
        SartDurumu.VAR if (da3_son5 or inr_5_3) else SartDurumu.YOK,
        '"son 5 ölçüm" tespit' if (da3_son5 or inr_5_3)
        else '"son 5 ölçüm" ibaresi yok',
        'rapor_metni', grup=g_varfa))
    sartlar.append(SartSonuc(
        '≥3 ölçümde INR tutulamadı',
        SartDurumu.VAR if (da4_3unde or inr_5_3) else SartDurumu.YOK,
        '"3\'ünde tutulamadı" tespit' if (da4_3unde or inr_5_3)
        else '"3\'ünde tutulamadı" ibaresi yok',
        'rapor_metni', grup=g_varfa))
    sartlar.append(SartSonuc(
        'INR 2-3 hedef aralık',
        SartDurumu.VAR if (da5_inr23 or inr_5_3) else SartDurumu.YOK,
        '"INR 2-3" hedef tespit' if (da5_inr23 or inr_5_3)
        else '"INR 2-3" ibaresi yok',
        'rapor_metni', grup=g_varfa))
    sartlar.append(SartSonuc(
        'Varfarin kesilerek YOAK\'a geçildi',
        SartDurumu.VAR if da6_kesildi else SartDurumu.KONTROL_EDILEMEDI,
        '"varfarin kesilerek" tespit' if da6_kesildi
        else '"varfarin kesilerek" ibaresi yok — manuel doğrulama',
        'rapor_metni', grup=g_varfa))

    # ── GRUP I: İstisna grubu [(2)] [VEYA, ≥1] ────────────────────────
    g_ist = 'İstisna grubu ≥1 [(2)]'
    idiopatik_pe = _yoak_idiopatik_pe(metin_lower)
    homozigot = _yoak_homozigot_trombofili(metin_lower)
    aktif_kanser_vte = _yoak_aktif_kanser_vte(metin_lower, teshis_metin)
    immobil = _yoak_immobil(metin_lower)
    sartlar.append(SartSonuc(
        'Tekrarlayan idiopatik pulmoner emboli',
        SartDurumu.VAR if idiopatik_pe else SartDurumu.YOK,
        'tekrarlayan idiopatik PE tespit' if idiopatik_pe
        else 'tekrarlayan idiopatik PE ibaresi yok',
        'rapor_metni', grup=g_ist, veya_grubu=True))
    sartlar.append(SartSonuc(
        'Homozigot trombofili',
        SartDurumu.VAR if homozigot else SartDurumu.YOK,
        'homozigot trombofili tespit' if homozigot
        else 'homozigot trombofili ibaresi yok',
        'rapor_metni', grup=g_ist, veya_grubu=True))
    sartlar.append(SartSonuc(
        'VTE öyküsü + aktif kanser',
        SartDurumu.VAR if aktif_kanser_vte else SartDurumu.YOK,
        'VTE öyküsü + aktif kanser tespit' if aktif_kanser_vte
        else 'VTE+aktif kanser birlikte tespit edilemedi',
        'rapor_metni/teshis', grup=g_ist, veya_grubu=True))
    sartlar.append(SartSonuc(
        'İmmobil hasta (rapor nedenli)',
        SartDurumu.VAR if immobil else SartDurumu.YOK,
        'immobil/yatağa bağımlı/plejik tespit' if immobil
        else 'immobil ibaresi yok',
        'rapor_metni', grup=g_ist, veya_grubu=True))

    istisnalar = [s.ad for s in sartlar
                  if s.grup == g_ist and s.durum == SartDurumu.VAR]

    # ── GRUP E2: SK raporu — ilk 24 ay [(3)] [AND, 4 atomik] ──────────
    # NÖROLOJİ YOK! D-2(3) ilk 24 ay için sadece kard/iç/göğüs/KVC.
    # PARAMETRİK kontrol: RaporDoktor tablosundan heyet doktorları.
    # feedback_rapor_metni_uzman_ibare_yasak (2026-05-12) — rapor metninde
    # branş ibare aramaktan vazgeçildi.
    g_e2 = 'SK raporu — ilk 24 ay [(3)]'
    medula_sk_var_d2 = bool(rapor_kodu and rapor_kodu.startswith('04.03'))
    dag_e2 = _yoak_heyet_brans_dagilimi(ilac_sonuc, _YOAK_HEYET_KEYS_D2_ILK24)

    # E2-1: SK raporu var (heyet ≥3 doktor veya Medula 04.03)
    e21_durum, e21_neden = _yoak_atom_heyet_sk_var(ilac_sonuc, rapor_kodu)
    sartlar.append(SartSonuc(
        'SK raporu (heyet ≥3 doktor)',
        e21_durum, e21_neden,
        'RaporDoktor/rapor_kodu', grup=g_e2))

    g_sk_brans = 'SK D-2 — heyet branşları (bilgi)'
    # Bilgi grup: heyet branş listesi
    if dag_e2['doktor_listesi']:
        for ad, brans_norm in dag_e2['doktor_listesi']:
            sartlar.append(SartSonuc(
                f'{brans_norm}: {ad[:30]}',
                SartDurumu.VAR,
                f'Heyet: {ad} ({brans_norm})',
                'RaporDoktor', grup=g_sk_brans))
    bulunan_brans = dag_e2['farkli_brans_sayisi']

    g_e2_bilgi = 'SK raporu (D-2) — manuel doğrulama (bilgi)'

    # E2-2a: Herhangi ≥3 farklı uzmanlık dalı (kard/iç/göğüs/KVC)
    # SUT D-2(3): "...uzman hekimlerinden aynı uzmanlık dalından üçünün
    # VEYA herhangi üçünün bulunduğu..." → alt-VEYA grubu
    e2a_durum, e2a_neden = _yoak_atom_heyet_yeterli_brans(
        ilac_sonuc, _YOAK_HEYET_KEYS_D2_ILK24)
    if e2a_durum == SartDurumu.KONTROL_EDILEMEDI and medula_sk_var_d2:
        e2a_durum, e2a_neden = (
            SartDurumu.VAR,
            'Medula 04.03 = ≥3 uzman onayı zorunlu (otorite — heyet DB boş)')
    sartlar.append(SartSonuc(
        'Herhangi ≥3 farklı uzmanlık dalı (kard/iç/göğüs/KVC)',
        e2a_durum, e2a_neden,
        'RaporDoktor', grup=g_e2, veya_grubu=True))

    # E2-2b: Aynı uzmanlık dalından ≥3 uzman (parametrik — heyet sayım)
    e2b_durum, e2b_neden = _yoak_atom_heyet_ayni_dalda_3(
        ilac_sonuc, _YOAK_HEYET_KEYS_D2_ILK24)
    sartlar.append(SartSonuc(
        'Aynı uzmanlık dalından ≥3 uzman',
        e2b_durum, e2b_neden,
        'RaporDoktor', grup=g_e2, veya_grubu=True))
    # E2-4 — bu uzmanlarca reçete
    e2_uzman_recete = _yoak_atom_e_uzman_recete(
        doktor_brans, _YOAK_DVTPE_SK_BRANSLAR)
    sartlar.append(SartSonuc(
        'Bu uzmanlarca reçete edildi',
        SartDurumu.VAR if e2_uzman_recete else SartDurumu.YOK,
        f'Doktor branşı: {doktor_brans} (yetkili)' if e2_uzman_recete
        else f'Doktor branşı yetkili değil: {doktor_brans or "(boş)"}',
        'doktor_uzmanligi', grup=g_e2))
    # E2-3 BİLGİ — 1 yıl süreli
    sartlar.append(SartSonuc(
        '1 yıl süreli rapor',
        SartDurumu.KONTROL_EDILEMEDI,
        'Rapor süresi parse edilemiyor — manuel doğrulama',
        'rapor_metni', grup=g_e2_bilgi))

    # ── GRUP F2: 24 ay sonrası alt yol [(3)] [AND, 2 atomik] ──────────
    # SUT D-2(3) son cümle: 24 ay sonrası nöroloji eklenir (uzman dalları
    # genişler) ama rapor metninde uzman branş İBARESİ aramaya gerek YOK
    # — reçete eden doktorun branşı (aile hk veya uzman+nöro) yeterli.
    g_f2 = '24 ay sonrası alt yol [(3)]'
    # F2-1: ilk 24 ay tamamlandı — hasta DB sorgusundan tespit
    f21_durum, f21_neden = _yoak_atom_f1_24ay_doldu(ilac_sonuc)
    sartlar.append(SartSonuc(
        'İlk 2 rapor süresi (24 ay) tamamlanmış',
        f21_durum, f21_neden,
        'hasta_yoak_gecmisi', grup=g_f2))
    # F2-2 (eski "rapor metninde uzman ibare" şartı KALDIRILDI — SUT'ta yok)
    # F2-3: aile hekimi reçete (branş + ASM kurum + tesis kodu)
    aile_hk, aile_neden = _yoak_atom_f_aile_hekimi(ilac_sonuc)
    if aile_hk:
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.VAR,
            f'Aile hekimi reçete: {aile_neden}',
            'doktor_uzmanligi/tesis', grup=g_f2))
    elif e2_uzman_recete or _yoak_atom_e_uzman_recete(
            doktor_brans, ('noroloji', 'nöroloji', 'noroloj')):
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.VAR,
            f'Uzman hekim reçete: {doktor_brans}',
            'doktor_uzmanligi', grup=g_f2))
    else:
        sartlar.append(SartSonuc(
            'Aile hekimi VEYA uzman reçete edebilir',
            SartDurumu.YOK,
            f'Doktor ne aile hekimi ne uzman: {aile_neden}',
            'doktor_uzmanligi/tesis', grup=g_f2))

    # ── GRUP G: Kombi yasağı [(D-1(4))] — D-2'de de geçerli, EN SONDA ─
    sartlar.append(SartSonuc(
        'Aynı reçetede 2. YOAK YOK',
        SartDurumu.VAR,
        'Aynı reçetede başka YOAK yok',
        'recete_ilaclari',
        grup='Kombi yasağı [(4)]'))

    # ── (4) Rapor yenileme bilgi notu (D-2'de de geçerli) ──
    # SUT D-2(4): "Rapor süresinin bitiminde ilaç tedavisinin devamına
    # karar verilmesi halinde, bu durumun belirtildiği yeni sağlık kurulu
    # raporu düzenlenerek tedaviye devam edilebilir."
    sartlar.append(SartSonuc(
        'Rapor süresi bitiminde devam kararı + yeni SK raporu',
        SartDurumu.KONTROL_EDILEMEDI,
        'Tedavi devamı için rapor yenilenmiş mi — manuel doğrulama',
        'rapor_metni/hasta_gecmisi',
        grup='Rapor yenileme [(4)] (bilgi)'))

    end_str = '/'.join([e for e, v in [('DVT', end_dvt), ('PE', end_pe)] if v])
    detaylar.update({'alt_dal': '4.2.15.D-2', 'endikasyon': end_str,
                     'istisnalar': istisnalar})

    anahtar = 'derin ven' if end_dvt else 'pulmoner emboli'
    return _yoak_genel_sonuc_atomik(sartlar, detaylar, sut_kurali,
                                     birlesik=birlesik, anahtar=anahtar)


def _yoak_ek4f_kontrol(metin_lower: str, birlesik: str,
                       ilac_sonuc: Dict, sartlar: List[SartSonuc],
                       detaylar: Dict) -> KontrolRaporu:
    """SUT EK-4/F Madde 53 (dabigatran) + Madde 54 (rivaroksaban) —
    Elektif kalça/diz total eklem replasmanı sonrası DVT profilaksisi.

    Yapı: L1 ∧ L2 ∧ L3 ∧ M_uygun (hepsi AND, ilaç-spesifik miktar limiti).
      L1  Elektif kalça/diz total eklem replasmanı (rapor)
      L2  DVT profilaksisi amacı (rapor)
      L3  Ortopedi uzmanı rapor düzenlemiş (doktor branş)
      M   Miktar limiti — riva diz≤1ku/kalça≤3ku; dab diz≤1ku/kalça≤2ku
    """
    sut_kurali = ('SUT EK-4/F Madde 53–54 — Elektif kalça/diz total eklem '
                  'replasmanı DVT profilaksisi (atomik şart taraması)')
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    doktor_brans = ilac_sonuc.get('doktor_uzmanligi') or ''
    # Kutu sayısı parse (kutu_sayisi → miktar fallback)
    kutu_raw = ilac_sonuc.get('kutu_sayisi')
    if kutu_raw is None:
        kutu_raw = ilac_sonuc.get('miktar', '')
    try:
        kutu = float(str(kutu_raw).replace(',', '.')) if str(kutu_raw).strip() \
            else 0.0
    except (ValueError, TypeError):
        kutu = 0.0
    # Günlük doz (cap/gün) — dabigatran gün hesabı için
    gunluk_doz_raw = None
    rec_doz_dict = ilac_sonuc.get('recete_doz')
    if isinstance(rec_doz_dict, dict):
        gunluk_doz_raw = rec_doz_dict.get('gunluk_doz')
    if gunluk_doz_raw is None:
        gunluk_doz_raw = ilac_sonuc.get('rec_doz_sayi')
    try:
        gunluk_doz = (float(str(gunluk_doz_raw).replace(',', '.'))
                      if gunluk_doz_raw not in (None, '') else None)
    except (ValueError, TypeError):
        gunluk_doz = None

    # ── GRUP L0: Etken madde uygunluğu (EK-4/F için kritik) ───────────
    # SUT EK-4/F Madde 53 (dabigatran) + Madde 54 (rivaroksaban).
    # Apiksaban/Edoksaban EK-4/F kapsamı YOK → bu yola düşülmüş demektir
    # ki etken madde uygun (kontrol_yoak'ta erken filtre). Görsel olarak
    # 2 ampul göster: (1) etken madde riva/dab VAR, (2) apiks/edox YOK.
    g_etken = 'Etken madde uygunluğu [Madde 53–54]'
    riva_var = 'RIVAROKSABAN' in etkin_madde
    dab_var = 'DABIGATRAN' in etkin_madde or 'DABİGATRAN' in etkin_madde
    sartlar.append(SartSonuc(
        'Etken madde rivaroksaban VEYA dabigatran',
        SartDurumu.VAR if (riva_var or dab_var) else SartDurumu.YOK,
        f'Etken madde: {etkin_madde} (EK-4/F kapsamında)'
        if (riva_var or dab_var)
        else f'Etken madde EK-4/F kapsamı dışı: {etkin_madde}',
        'recete_ilac', grup=g_etken, veya_grubu=True))
    apiks_var = 'APIKSABAN' in etkin_madde or 'APİKSABAN' in etkin_madde
    edox_var = 'EDOKSABAN' in etkin_madde
    sartlar.append(SartSonuc(
        'Apiksaban/Edoksaban kapsam dışı (NOT)',
        SartDurumu.YOK if (apiks_var or edox_var) else SartDurumu.VAR,
        f'Etken madde apiksaban/edoksaban — EK-4/F kapsamı dışı'
        if (apiks_var or edox_var)
        else 'Reçete etken maddesi apiks/edox değil — kontrendikasyon yok',
        'recete_ilac', grup=g_etken))

    # ── GRUP L1: Endikasyon — elektif kalça/diz total eklem replasmanı ─
    g_end = 'Elektif kalça/diz total eklem replasmanı [Madde 53–54]'
    elektif_var = _yoak_ek4f_atom_elektif_replasman(metin_lower)
    sartlar.append(SartSonuc(
        'Elektif kalça/diz total eklem replasmanı',
        SartDurumu.VAR if elektif_var else SartDurumu.KONTROL_EDILEMEDI,
        'rapor metninde elektif kalça/diz replasman ibaresi tespit'
        if elektif_var
        else 'rapor metninde elektif kalça/diz replasman ibaresi yok — '
             'manuel doğrulama',
        'rapor_metni', grup=g_end))

    # Lokalizasyon (diz/kalça) — miktar limiti için kritik
    lokalizasyon = _yoak_ek4f_lokalizasyon(metin_lower)
    g_lok = 'Lokalizasyon (diz/kalça) [Madde 53–54] (bilgi)'
    if lokalizasyon:
        sartlar.append(SartSonuc(
            f'Lokalizasyon: {lokalizasyon}',
            SartDurumu.VAR,
            f'rapor metninde "{lokalizasyon}" ibaresi tespit',
            'rapor_metni', grup=g_lok))
    else:
        sartlar.append(SartSonuc(
            'Lokalizasyon: diz / kalça',
            SartDurumu.KONTROL_EDILEMEDI,
            'rapor metninde diz/kalça ayrımı belirsiz — manuel doğrulama',
            'rapor_metni', grup=g_lok))

    # ── GRUP L2: Amaç — DVT profilaksisi ──────────────────────────────
    g_amac = 'DVT profilaksisi amacı [Madde 53–54]'
    dvt_prof = _yoak_ek4f_atom_dvt_profilaksi(metin_lower)
    sartlar.append(SartSonuc(
        'DVT profilaksisi amacı',
        SartDurumu.VAR if dvt_prof else SartDurumu.KONTROL_EDILEMEDI,
        'rapor metninde "DVT profilaksi" ibaresi tespit' if dvt_prof
        else 'rapor metninde "DVT profilaksi" ibaresi yok — manuel doğrulama',
        'rapor_metni', grup=g_amac))

    # ── GRUP L3: Ortopedi uzmanı rapor düzenlemiş ─────────────────────
    g_rapor = 'Ortopedi uzmanı raporu [Madde 53–54]'
    ortopedi = _yoak_ek4f_atom_ortopedi_rapor(doktor_brans)
    sartlar.append(SartSonuc(
        'Ortopedi uzman hekimi raporu',
        SartDurumu.VAR if ortopedi else SartDurumu.YOK,
        f'Doktor branşı: {doktor_brans} (ortopedi tespit)' if ortopedi
        else f'Doktor branşı ortopedi değil: {doktor_brans or "(boş)"}',
        'doktor_uzmanligi', grup=g_rapor))

    # ── GRUP M: Miktar limiti (ilaç + lokalizasyon spesifik) ──────────
    g_miktar = 'Miktar limiti [Madde 53–54]'
    miktar_ok, miktar_aciklama = _yoak_ek4f_atom_miktar_uygun(
        etkin_madde, lokalizasyon, kutu, gunluk_doz)
    if miktar_ok is True:
        sartlar.append(SartSonuc(
            'İlaç miktar/süre limiti', SartDurumu.VAR,
            miktar_aciklama, 'recete_kalem/rapor_metni', grup=g_miktar))
    elif miktar_ok is False:
        sartlar.append(SartSonuc(
            'İlaç miktar/süre limiti', SartDurumu.YOK,
            miktar_aciklama, 'recete_kalem/rapor_metni', grup=g_miktar))
    else:
        sartlar.append(SartSonuc(
            'İlaç miktar/süre limiti', SartDurumu.KONTROL_EDILEMEDI,
            miktar_aciklama, 'recete_kalem/rapor_metni', grup=g_miktar))

    detaylar.update({
        'alt_dal': 'EK-4/F (M.53–54)',
        'endikasyon': 'Elektif kalça/diz total eklem replasmanı',
        'lokalizasyon': lokalizasyon or 'belirsiz',
        'kutu_sayisi': kutu,
        'gunluk_doz': gunluk_doz,
    })

    return _yoak_genel_sonuc_atomik(sartlar, detaylar, sut_kurali,
                                     birlesik=birlesik,
                                     anahtar='replasman')


def _yoak_genel_sonuc_atomik(sartlar: List[SartSonuc], detaylar: Dict,
                              sut_kurali: str, birlesik: str,
                              anahtar: str) -> KontrolRaporu:
    """Atomik şart listesinden grup-bazlı genel sonuç üret.

    Mantık:
      1. Şartları `grup` adına göre topla.
      2. "(bilgi)" suffix'li gruplar hesaplama dışı (sadece raporlanır).
      3. Her grubun kendi durumunu hesapla:
         - veya_grubu işaretli grup → ≥1 VAR ise VAR
         - değilse AND → bir tane YOK varsa YOK, KE varsa KE
      4. "Varfarin yolu (a)" + "Varfarin yolu (b)" → üst düzey VEYA
         (a tüm AND VEYA b tek)
      5. Genel sonuç:
         - Hesaplanan gruplardan herhangi birinde YOK → UYGUN_DEGIL
         - KE varsa → KONTROL_EDILEMEDI (ŞÜPHELİ)
         - Hepsi VAR → UYGUN
    """
    # Grupla
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        gruplar.setdefault(s.grup, []).append(s)

    grup_durumlari: Dict[str, SartDurumu] = {}
    for ad, gs in gruplar.items():
        # Boş grup, (bilgi), [pasif], Apiksaban özel → hesap dışı
        if (not ad or '(bilgi)' in ad or '[pasif]' in ad
                or 'Apiksaban özel' in ad):
            continue
        # OR mı AND mi?
        if any(s.veya_grubu for s in gs):
            grup_durumlari[ad] = _yoak_grup_durumu(gs, veya=True)
        else:
            grup_durumlari[ad] = _yoak_grup_durumu(gs, veya=False)

    # Yardımcı: 2 grup arasında üst-OR durumu hesapla
    def _ust_or(d1, d2):
        if d1 == SartDurumu.VAR or d2 == SartDurumu.VAR:
            return SartDurumu.VAR
        if (d1 == SartDurumu.KONTROL_EDILEMEDI or
                d2 == SartDurumu.KONTROL_EDILEMEDI):
            return SartDurumu.KONTROL_EDILEMEDI
        return SartDurumu.YOK

    # Üst-OR çiftleri: (prefix_a, prefix_b, birleşik_ad)
    ust_or_ciftleri = [
        ('Varfarin yolu (a)', 'Varfarin yolu (b)',
         'Varfarin yolu [(a) VEYA (b)]'),
        ('Varfarin yolu —', 'İstisna grubu',
         'Varfarin VEYA İstisna [(1)(b) VEYA (2)]'),
        ('SK raporu — ilk 24 ay [(2)]', '24 ay sonrası alt yol [(2)]',
         'Rapor + Reçete (D-1) [E VEYA F]'),
        ('SK raporu — ilk 24 ay [(3)]', '24 ay sonrası alt yol [(3)]',
         'Rapor + Reçete (D-2) [E2 VEYA F2]'),
    ]
    for prefix_a, prefix_b, birlesik in ust_or_ciftleri:
        ka = next((k for k in grup_durumlari if k.startswith(prefix_a)), None)
        kb = next((k for k in grup_durumlari if k.startswith(prefix_b)), None)
        if ka and kb:
            grup_durumlari[birlesik] = _ust_or(grup_durumlari[ka],
                                                grup_durumlari[kb])
            grup_durumlari.pop(ka)
            grup_durumlari.pop(kb)

    # Üst-OR çoklu (n-way): D-1(1) risk faktörü 4 alt-grup → tek üst-OR
    # SUT lafzı 4 alt-grup, ≥1 yeterli ((a)∨(b)∨(c)∨(d))
    ust_or_coklu = [
        (('Risk fakt. (a) — inme/TIA',
          'Risk fakt. (b) — ≥75 yaş',
          'Risk fakt. (c) — NYHA',
          'Risk fakt. (d) — DM/HT'),
         'Risk faktörü ≥1 [(a)∨(b)∨(c)∨(d)]'),
    ]
    for prefixes, birlesik in ust_or_coklu:
        keys = [next((k for k in grup_durumlari if k.startswith(p)), None)
                for p in prefixes]
        keys = [k for k in keys if k]
        if not keys:
            continue
        durumlar = [grup_durumlari[k] for k in keys]
        if any(d == SartDurumu.VAR for d in durumlar):
            sonuc = SartDurumu.VAR
        elif any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
            sonuc = SartDurumu.KONTROL_EDILEMEDI
        else:
            sonuc = SartDurumu.YOK
        grup_durumlari[birlesik] = sonuc
        for k in keys:
            grup_durumlari.pop(k, None)

    # Genel sonuç
    yok_gruplar = [g for g, d in grup_durumlari.items() if d == SartDurumu.YOK]
    ke_gruplar = [g for g, d in grup_durumlari.items()
                  if d == SartDurumu.KONTROL_EDILEMEDI]

    detaylar['grup_durumlari'] = {g: d.value for g, d in grup_durumlari.items()}
    eslesen = _eslesen_parcayi_bul(birlesik, anahtar) if birlesik else ''

    if yok_gruplar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'YOAK SUT şartları sağlanmıyor — eksik gruplar: '
                  f'{", ".join(yok_gruplar)}',
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare='Tüm SUT şartları', bulunan_metin=eslesen)
    if ke_gruplar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'YOAK ŞÜPHELİ — manuel doğrulanmalı: {", ".join(ke_gruplar)}',
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            uyari='Bazı şartlar metinden tespit edilemedi',
            aranan_ibare='Tüm SUT şartları', bulunan_metin=eslesen)
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=f'YOAK SUT şartları sağlanıyor ({len(grup_durumlari)} grup VAR)',
        sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
        aranan_ibare='Tüm SUT şartları', bulunan_metin=eslesen)


def _yoak_sonuc_uret(sartlar: List[SartSonuc], detaylar: Dict,
                     sut_kurali: str, aranan: str, birlesik: str,
                     anahtar: str) -> KontrolRaporu:
    """Şart listesinden genel sonuç (UYGUN/ŞÜPHELİ/UYGUN_DEGIL) üretir.

    CLAUDE.md disiplini:
    - YOK varsa → UYGUN_DEGIL
    - KONTROL_EDILEMEDI varsa → KONTROL_EDILEMEDI (ŞÜPHELİ)
    - Hepsi VAR → UYGUN
    """
    yok_sayisi = sum(1 for s in sartlar if s.durum == SartDurumu.YOK)
    ke_sayisi = sum(1 for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI)
    var_sayisi = sum(1 for s in sartlar if s.durum == SartDurumu.VAR)

    eslesen = _eslesen_parcayi_bul(birlesik, anahtar) if birlesik else ''

    if yok_sayisi > 0:
        yok_listesi = [s.ad for s in sartlar if s.durum == SartDurumu.YOK]
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'YOAK SUT şartları sağlanmıyor — eksik: '
                   f'{", ".join(yok_listesi)}'),
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan, bulunan_metin=eslesen)
    if ke_sayisi > 0:
        ke_listesi = [s.ad for s in sartlar
                      if s.durum == SartDurumu.KONTROL_EDILEMEDI]
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=(f'YOAK ŞÜPHELİ — manuel doğrulanmalı: '
                   f'{", ".join(ke_listesi)}'),
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            uyari='Bazı şartlar metinden tespit edilemedi — manuel doğrulama',
            aranan_ibare=aranan, bulunan_metin=eslesen)
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=f'YOAK SUT şartları sağlanıyor ({var_sayisi} şart VAR)',
        sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
        aranan_ibare=aranan, bulunan_metin=eslesen)


def _yoak_post_process_manuel_kontrol(
        rapor: KontrolRaporu, ilac_sonuc: Dict) -> KontrolRaporu:
    """Post-process: F1 (24 ay) atomu KE + doktor aile hekimi ise verdict
    KONTROL_EDILEMEDI → MANUEL_KONTROL.

    SUT 4.2.15.D-1(2) son cümle yorumu: 24 ay belirsizse aile hekimi
    yetkisi sorgulanabilir → eczacı manuel kontrol etmeli, sistem
    otomatik karar vermesin.
    """
    if rapor.sonuc != KontrolSonucu.KONTROL_EDILEMEDI:
        return rapor
    f1_adi = 'İlk 2 rapor süresi (24 ay) tamamlanmış'
    f1_ke = any(
        getattr(s, 'ad', '') == f1_adi
        and getattr(s, 'durum', None) == SartDurumu.KONTROL_EDILEMEDI
        for s in (rapor.sartlar or [])
    )
    if not f1_ke:
        return rapor
    aile_hk, aile_neden = _yoak_atom_f_aile_hekimi(ilac_sonuc)
    if not aile_hk:
        return rapor
    rapor.sonuc = KontrolSonucu.MANUEL_KONTROL
    rapor.mesaj = (
        (rapor.mesaj or '').rstrip('. ')
        + ' — Aile hekimi reçetesi + 24 ay durumu belirsiz: MANUEL KONTROL gerekli'
    ).strip()
    return rapor


def kontrol_yoak(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.15.D + EK-4/F M.53-54 — YOAK
    (Rivaroksaban/Apiksaban/Edoksaban/Dabigatran)

    Kontrol akışı:
      0. Boş metin erken çıkışı (raporsuz → UYGUN_DEGIL, raporlu → KE)
      1. Kombi yasağı [D-1(4)]: aynı reçetede 2 YOAK → UYGUN_DEGIL
      2. EK-4/F erken-tespit: etken madde riva/dab + ortopedi branş →
         _yoak_ek4f_kontrol (elektif kalça/diz replasmanı profilaksisi).
         Apiksaban/Edoksaban + ortopedi sinyali EK-4/F kapsamı YOK → D-2.
      3. Endikasyon tespiti (AF / DVT / PE)
      4. AF varsa _yoak_d1_af_kontrol() — D-1
         · Risk faktörü, kontrendikasyon, varfarin/INR, sağlık kurulu
      5. DVT/PE varsa _yoak_d2_dvtpe_kontrol() — D-2
         · Yetişkin, varfarin/INR VEYA istisna, sağlık kurulu
      6. Endikasyon yok → KONTROL_EDILEMEDI

    Şart-bazlı raporlama (CLAUDE.md disiplini):
      Her şart VAR / YOK / KONTROL_EDILEMEDI olarak `sartlar`'a yazılır.
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik) if birlesik else ''
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    yas = _yoak_yas_oku(ilac_sonuc, birlesik)

    sartlar: List[SartSonuc] = []
    detaylar: Dict = {
        'sut_maddesi': '4.2.15.D',
        'rapor_kodu': rapor_kodu,
        'hasta_yasi': yas,
    }
    sut_kurali_genel = 'SUT 4.2.15.D — YOAK (D-1 AF / D-2 DVT/PE)'

    # ── 0) Boş metin ──────────────────────────────────────────────────
    if not metin_lower.strip():
        if not rapor_kodu:
            sartlar.append(SartSonuc(
                'Rapor kodu', SartDurumu.YOK,
                'Reçete satırında rap_kod boş', 'rap_kod'))
            sartlar.append(SartSonuc(
                'Rapor/mesaj metni', SartDurumu.YOK,
                'Metin boş ve rapor da yok', 'tum_metin'))
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                'Raporsuz YOAK — sağlık kurulu raporu zorunlu (4.2.15.D)',
                sut_kurali=sut_kurali_genel, detaylar=detaylar,
                sartlar=sartlar,
                aranan_ibare='rapor / AF / DVT / PE / varfarin / INR')
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.VAR,
                                  rapor_kodu, 'rap_kod'))
        sartlar.append(SartSonuc('Rapor/mesaj metni',
                                  SartDurumu.KONTROL_EDILEMEDI,
                                  'Rapor kodu var ancak metni okunamadı',
                                  'tum_metin'))
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f'Rapor kodu var ({rapor_kodu}) ama metni okunamadı — '
            'manuel doğrulama gerekli',
            sut_kurali=sut_kurali_genel, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare='AF / DVT / PE / varfarin / INR / sağlık kurulu')

    # ── 1) Kombi YOAK yasağı [(4)] — sadece erken çıkış kontrolü ──────
    # NOT: SUT lafzında (4) en sonda → atomik şart D-1/D-2 fonksiyonun
    # SONUNDA eklenecek. Burada sadece kombi VAR ise erken UYGUN_DEGIL.
    kombi_var, kombi_ad = _yoak_kombi_var(ilac_sonuc)
    detaylar['kombi_yoak'] = (kombi_var, kombi_ad)
    if kombi_var:
        sartlar.append(SartSonuc(
            'Kombi yasağı [4.2.15.D-1(4)] — aynı reçetede 2. YOAK YOK',
            SartDurumu.YOK,
            f'Aynı reçetede ikinci YOAK: {kombi_ad}',
            'recete_ilaclari',
            grup='Kombi yasağı [(4)]'))
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'YOAK kombi yasağı — aynı reçetede ikinci YOAK '
                   f'({kombi_ad}) tespit edildi; bedeli karşılanmaz'),
            sut_kurali=sut_kurali_genel, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare='aynı reçetede 2 YOAK')

    # ── 2) EK-4/F erken-tespit (ortopedi profilaksi yolu) ─────────────
    # SUT EK-4/F Madde 53-54 sadece rivaroksaban + dabigatran için geçerli.
    # Apiksaban/edoksaban + ortopedi sinyali → D-2 yoluna düşer (kapsam dışı).
    etkin_madde_main = (ilac_sonuc.get('etkin_madde') or '').upper()
    doktor_brans_main = ilac_sonuc.get('doktor_uzmanligi') or ''
    ek4f_etken_uygun = _yoak_ek4f_etken_madde_uygun(etkin_madde_main)
    ek4f_ortopedi = _yoak_ek4f_atom_ortopedi_rapor(doktor_brans_main)
    if ek4f_etken_uygun and ek4f_ortopedi:
        # EK-4/F yoluna düş — D-1/D-2'den önce
        rapor = _yoak_ek4f_kontrol(metin_lower, birlesik, ilac_sonuc,
                                    sartlar, detaylar)
        return _yoak_post_process_manuel_kontrol(rapor, ilac_sonuc)

    # ── 3) Endikasyon tespiti ─────────────────────────────────────────
    end = _yoak_endikasyonlari_tespit(metin_lower, teshis_metin)
    has_af = end['af']
    has_dvtpe = end['dvt'] or end['pe']

    # ── 4) Aktif yolak belirle (D-1 vs D-2) ──────────────────────────
    # Endikasyona göre: AF varsa D-1, DVT/PE varsa D-2.
    # İkisi birden varsa D-2 önceliği (daha spesifik DVT/PE durumu).
    # Hiçbiri yoksa endikasyon yok → KE.
    if has_dvtpe:
        aktif_yolak = 'D-2'
    elif has_af:
        aktif_yolak = 'D-1'
    else:
        aktif_yolak = None

    # ── 4) ÇOKLU YOLAK: hem aktif hem pasif dalları çalıştır ─────────
    # Aktif yolak normal şartları üretir; pasif yolak bilgi amaçlı,
    # grup adlarına "[pasif]" prefix eklenir → GUI üst paralel hatta
    # gri olarak gösterilir.
    if aktif_yolak == 'D-1':
        # Aktif: D-1, Pasif: D-2
        rapor = _yoak_d1_af_kontrol(metin_lower, teshis_metin, birlesik,
                                     ilac_sonuc, yas, rapor_kodu,
                                     sartlar, detaylar)
        # Pasif D-2 şartlarını ayrı listede üret
        pasif_sartlar: List[SartSonuc] = []
        try:
            _yoak_d2_dvtpe_kontrol(
                metin_lower, teshis_metin, birlesik,
                ilac_sonuc, yas, rapor_kodu,
                end['dvt'], end['pe'],
                pasif_sartlar, {})
        except Exception:
            pass
        # Pasif şartların gruplarına [pasif] prefix
        for ps in pasif_sartlar:
            ps.grup = '[pasif] ' + ps.grup if ps.grup else '[pasif]'
        rapor.sartlar.extend(pasif_sartlar)
        rapor.detaylar = rapor.detaylar or {}
        rapor.detaylar['aktif_yolak'] = 'D-1'
        rapor.detaylar['pasif_yolak'] = 'D-2'
        return _yoak_post_process_manuel_kontrol(rapor, ilac_sonuc)

    if aktif_yolak == 'D-2':
        # Aktif: D-2, Pasif: D-1
        rapor = _yoak_d2_dvtpe_kontrol(metin_lower, teshis_metin, birlesik,
                                        ilac_sonuc, yas, rapor_kodu,
                                        end['dvt'], end['pe'],
                                        sartlar, detaylar)
        # Pasif D-1 şartlarını ayrı listede üret
        pasif_sartlar = []
        try:
            _yoak_d1_af_kontrol(
                metin_lower, teshis_metin, birlesik,
                ilac_sonuc, yas, rapor_kodu,
                pasif_sartlar, {})
        except Exception:
            pass
        for ps in pasif_sartlar:
            ps.grup = '[pasif] ' + ps.grup if ps.grup else '[pasif]'
        rapor.sartlar.extend(pasif_sartlar)
        rapor.detaylar = rapor.detaylar or {}
        rapor.detaylar['aktif_yolak'] = 'D-2'
        rapor.detaylar['pasif_yolak'] = 'D-1'
        return _yoak_post_process_manuel_kontrol(rapor, ilac_sonuc)

    # ── 5) Endikasyon yok ─────────────────────────────────────────────
    sartlar.append(SartSonuc(
        'Endikasyon (AF / DVT / PE)',
        SartDurumu.KONTROL_EDILEMEDI,
        'AF / DVT / PE ibaresi raporda/tanılarda bulunamadı',
        'rapor_metni/teshis'))
    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj='YOAK endikasyonu tespit edilemedi (AF/DVT/PE)',
        sut_kurali=sut_kurali_genel, detaylar=detaylar, sartlar=sartlar,
        aranan_ibare='AF / DVT / PE / I48 / I26 / I80-82',
        uyari='SUT 4.2.15.D yalnız AF (D-1) ve DVT/PE (D-2) için geçerlidir')


# ═══════════════════════════════════════════════════════════════════════
# SUT 4.2.17 — Osteoporoz / Bifosfonat / Raloksifen / Kalsitonin / Aktif-D
# ═══════════════════════════════════════════════════════════════════════

# 4.2.17.A(5): Bifosfonat raporu yetkili branşlar
_OSTEO_YETKILI_BRANSLAR = (
    'ic hastalik', 'iç hastalık', 'dahiliye',
    'fizik tedavi', 'fiziksel tip', 'fiziksel tıp', 'ftr', 'rehabilitasyon',
    'romatoloj',
    'ortopedi', 'travmatoloj',
    'kadin hastalik', 'kadın hastalık', 'kadin dogum', 'kadın doğum', 'jinekoloj',
    'endokrinoloj', 'endokrin',
    'tibbi ekoloji', 'tıbbi ekoloji', 'hidroklimatoloji',
)

# 4.2.17.A(7-8): Kalsitonin için yetkili branşlar (tıbbi ekoloji yok)
_KALSITONIN_YETKILI_BRANSLAR = (
    'ic hastalik', 'iç hastalık', 'dahiliye',
    'fizik tedavi', 'fiziksel tip', 'fiziksel tıp', 'ftr', 'rehabilitasyon',
    'romatoloj',
    'ortopedi', 'travmatoloj',
    'kadin hastalik', 'kadın hastalık', 'kadin dogum', 'kadın doğum', 'jinekoloj',
    'endokrinoloj', 'endokrin',
)

# 4.2.17.A(4)(ç): Sekonder osteoporoz primer hastalık listesi
# anahtar: hastalık adı | değer: (kelime listesi, ICD prefix listesi)
_SEKONDER_OSTEO_PRIMER = {
    'romatoid artrit':       (['romatoid artrit', 'rheumatoid arthrit', ' ra '],
                              ['M05', 'M06']),
    'çölyak hastalığı':      (['colyak', 'çölyak', 'celiac'], ['K90']),
    'crohn hastalığı':       (['crohn'], ['K50']),
    'ülseratif kolit':       (['ulseratif kolit', 'ülseratif kolit'], ['K51']),
    'ankilozan spondilit':   (['ankilozan spondilit', 'spondiloartrit'], ['M45']),
    'hipertiroidi':          (['hipertiroidi', 'tirotoksikoz', 'graves'],
                              ['E05']),
    'hipogonadizm':          (['hipogonadizm'], ['E23.0', 'E29']),
    'hipopituitarizm':       (['hipopituitarizm', 'panhipopituitarizm'], ['E23']),
    'anoreksia nervoza':     (['anoreksia nervoza', 'anoreksia nevroza',
                              'anorexia nervosa'], ['F50']),
    'KOAH':                  (['koah', 'kronik obstruktif', 'kronik obstrüktif',
                              'copd'], ['J44']),
    'tip 1 diyabet':         (['tip 1 diyabet', 'tip i diyabet', 'tip-1 dm',
                              'tip 1 dm'], ['E10']),
    'cushing sendromu':      (['cushing'], ['E24']),
    'primer hiperparatiroidi': (['primer hiperparatiroid'], ['E21.0']),
}


def _osteo_yas_oku(ilac_sonuc: Dict, metin: str = '') -> Optional[int]:
    """ilac_sonuc.hasta_yasi'ı veya metinden yaş kalıbını oku.

    Yakalanan formatlar:
      - 'yaş: 72' / 'yaş 72' / 'yas 72' (kelime önce)
      - '56 YAŞ' / '69 YAŞINDADIR' / '78 yaşında' (sayı önce — Medula
        rapor metinlerinde sıkça görülür)
    """
    hy_raw = ilac_sonuc.get('hasta_yasi') or ilac_sonuc.get('yas')
    if hy_raw:
        try:
            yas = int(re.sub(r'[^0-9]', '', str(hy_raw)) or 0)
            if 0 < yas < 130:
                return yas
        except (ValueError, TypeError):
            pass
    if metin:
        # Sıra 1: 'yaş 72' / 'yas: 72' (kelime önce)
        m = re.search(r'(?:yaş|yasi|yas)[^0-9]{0,8}(\d{1,3})', metin,
                      re.IGNORECASE)
        if m:
            try:
                yas = int(m.group(1))
                if 0 < yas < 120:
                    return yas
            except ValueError:
                pass
        # Sıra 2: '56 YAŞ' / '69 YAŞINDADIR' / 'hasta 78 yaşında' (sayı önce)
        m2 = re.search(r'(\d{1,3})\s*yaş', metin, re.IGNORECASE)
        if m2:
            try:
                yas = int(m2.group(1))
                if 0 < yas < 120:
                    return yas
            except ValueError:
                pass
    return None


def _osteo_yetkili_brans(brans: str, brans_listesi=_OSTEO_YETKILI_BRANSLAR) -> bool:
    if not brans:
        return False
    bl = _tr_lower(brans)
    return any(k in bl for k in brans_listesi)


def _osteo_kombi_var(ilac_sonuc: Dict, mevcut_kategori: str) -> Tuple[bool, str]:
    """SUT 4.2.17.A(1) son cümle: bu grup ilaçların kombinasyonu halinde
    sadece birinin bedeli ödenir.

    Aynı reçetede başka bir osteoporoz ilacı varsa True döndür.
    Returns: (kombi_var, tespit_edilen_ilac).
    """
    diger = ilac_sonuc.get('recete_ilaclari') or []
    diger_str = ' '.join([
        str(i.get('ad', '') if isinstance(i, dict) else i) for i in diger
    ]).upper()
    diger_etken = ilac_sonuc.get('diger_etken_maddeler') or []
    diger_str += ' ' + ' '.join([str(x) for x in diger_etken]).upper()
    if not diger_str.strip():
        return False, ''

    osteo_ilaclar = {
        'BIFOSFONAT': ('ALENDRONAT', 'RISEDRONAT', 'IBANDRONAT', 'ZOLEDRONAT',
                       'FOSAMAX', 'FOSAVANCE', 'ACTONEL', 'BONVIVA', 'ACLASTA',
                       'ZOMETA', 'OSTEOFOS', 'OSTEOMAX', 'BENEFOS'),
        'RALOKSIFEN': ('RALOKSIFEN', 'EVISTA', 'OPTRUMA', 'BAZEDOKSIFEN',
                       'CONBRIZA'),
        'KALSITONIN': ('KALSITONIN', 'CALCITONIN', 'MIACALCIC', 'MIACALCIN',
                       'CALSYNAR', 'TONOCALCIN'),
        'OSTEOPOROZ_BIYOLOJIK': ('DENOSUMAB', 'PROLIA', 'TERIPARATID', 'FORTEO',
                                  'FORSTEO', 'MOVYMIA', 'ROMOSOZUMAB', 'EVENITY',
                                  'STRONSIYUM', 'STRONTIUM', 'OSSEOR', 'PROTELOS'),
    }
    for kategori, ilaclar in osteo_ilaclar.items():
        if kategori == mevcut_kategori:
            continue
        for ilac in ilaclar:
            if ilac in diger_str:
                return True, ilac
    return False, ''


def _parse_tarih_str(s):
    """'dd/mm/yyyy' veya 'dd.mm.yyyy' string'ini date'e çevir, hatada None."""
    if not s:
        return None
    from datetime import date
    m = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', str(s).strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except (ValueError, OverflowError):
        return None


def _kmy_tarihi_parse(metin_orijinal: str, metin_lower: str,
                      pencere: int = 120,
                      referans_tarih=None) -> Tuple[Optional[str], Optional[bool]]:
    """KMY/DEXA ölçüm tarihini metinden çek.

    Anchor: 'kmy', 'dexa', 'dxa', 'kemik mineral', 'lomber', 'femur', vb.
    Pencere içindeki en yakın gg.aa.yyyy/gg/aa/yyyy tarihini en yenisi
    olarak döndürür.

    SUT 4.2.17.A(2): "düzenlenecek rapor tarihinden önce son 2 yıl içinde".
    Bu yüzden 'son 2 yıl' kontrolü `referans_tarih` (rapor/reçete tarihi)
    verildiyse ona göre, yoksa bugünkü tarihe göre yapılır.

    Returns: (tarih_str veya None, son_2_yil_icinde_mi veya None).
    """
    if not metin_orijinal or not metin_lower:
        return None, None
    anahtarlar = ('kmy', 'dexa', 'dxa', 'kemik mineral',
                  'kemik ölçüm', 'kemik olcum',
                  'ölçüm tarih', 'olcum tarih',
                  'lomber', 'l1-l4', 'l1- l4', 'l1-4',
                  'l2-l4', 'l2-4', 'femur boyn', 'femur total')
    pozlar = []
    for k in anahtarlar:
        ofset = 0
        while True:
            i = metin_lower.find(k, ofset)
            if i < 0:
                break
            pozlar.append(i)
            ofset = i + len(k)
    if not pozlar:
        return None, None

    from datetime import date
    tarih_pat = re.compile(r'(\d{2})[./](\d{2})[./](\d{4})')
    n = len(metin_orijinal)
    bulunan: Optional[date] = None
    bulunan_str: Optional[str] = None
    for p in pozlar:
        b = max(0, p - pencere)
        s = min(n, p + pencere)
        for m in tarih_pat.finditer(metin_orijinal[b:s]):
            try:
                gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if not (2000 <= yil <= 2030 and 1 <= ay <= 12 and 1 <= gun <= 31):
                    continue
                t = date(yil, ay, gun)
            except (ValueError, OverflowError):
                continue
            if bulunan is None or t > bulunan:
                bulunan = t
                bulunan_str = m.group(0)
    if bulunan is None:
        return None, None
    ref = referans_tarih if referans_tarih is not None else date.today()
    fark = (ref - bulunan).days
    son_2_yil = (-30 <= fark <= 730)  # rapor öncesi 2 yıl + 30 gün hata payı
    return bulunan_str, son_2_yil


def _kmy_olcum_yeri_uygun(metin_lower: str) -> bool:
    """SUT 4.2.17.A(4): lomber total (L1-4 / L2-4) veya femur total /
    femur boynu KMY ölçümü."""
    return any(k in metin_lower for k in (
        'lomber', 'l1-4', 'l1-l4', 'l2-4', 'l2-l4', 'l1 l4', 'l2 l4',
        'femur', 'femoral', 'femur boyn',
    ))


_T_OLC_YERI_PAT = re.compile(
    r'\b(?:l\s*1[\s\-]*l?\s*4|l\s*2[\s\-]*l?\s*4|lomber|'
    r'femur(?:\s+(?:boyn[uı]?|total))?|trochanter|boyn|total)\b'
)
_T_TARIH_PAT = re.compile(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b')
_T_ANCHOR_PAT = re.compile(
    r'(?:total[\s\-]+)?(?:t[\s\-]*)?(?:skor[ua]?|score|scor)\b'
)
_T_NUM_PAT = re.compile(r'([+\-]?)\s*(\d+(?:[.,]\d+)?)')


def _t_skoru_parse(metin_lower: str, birlesik: str) -> Tuple[Optional[float], str]:
    """T-skoru sayısal değerini parse et.

    Yakalanan formatlar:
      - 'T: -2.8' / 'T=-2,8' (bare T)
      - 'T-skor: -3.1' / 'T-score: -2.5'
      - 'T-SCOR -3,6' (typo: scor)
      - 'T SKOR:-3' (tam sayı, ondalık yok)
      - 'T-SKOR : - 2.6' (boşluklu eksi)
      - 'TOTAL SKOR -3,2' (T-anchor yok, total prefix)
      - 'TOTAL T-SKOR : - 2.6'
      - 't-skor l1-l4 -3.6' (anchor↔sayı arası ölçüm yeri token)
      - 'T-skoru: 2.6' / 'T:2.6' (eksi unutulmuş → negatif kabul edilir;
        T-skoru pratikte hep negatiftir)

    Strateji: 2 aşama.
      1) skor/skoru/score/scor anchor bul, sonrası 60 char pencerede ilk
         ondalık sayıyı al. Pencerede tarih ve ölçüm-yeri token'ları
         temizlenir (yanlış yakalama önler).
      2) Bare 'T:' / 'T=' formu.

    İşaret unutulmuşsa veya '+' ise pozitif değer negatife çevrilir.
    Sanity: [-10, 0] (T-skoru hep negatif/yakın-sıfır).

    Returns: (t_skoru veya None, eslesen_str).
    """
    def _onceleme(pencere: str) -> str:
        # Tarih ve ölçüm-yeri token'larını boşluğa çevir → yanlış sayı
        # yakalamayı engelle (16.06.2025 / l1-l4 vs.).
        p = _T_TARIH_PAT.sub(' ', pencere)
        p = _T_OLC_YERI_PAT.sub(' ', p)
        return p

    def _negatife_cevir(t: float) -> float:
        return -t if t > 0 else t

    # Aşama 1: skor anchor + signed/unsigned sayı
    for am in _T_ANCHOR_PAT.finditer(metin_lower):
        pencere = _onceleme(metin_lower[am.end():am.end() + 60])
        nm = _T_NUM_PAT.search(pencere)
        if not nm:
            continue
        try:
            ham = (nm.group(1) or '') + nm.group(2)
            t = _negatife_cevir(float(ham.replace(',', '.')))
        except (ValueError, IndexError):
            continue
        if -10 <= t <= 0:
            return t, ham.replace(' ', '')

    # Aşama 2: bare 'T:' / 'T=' (anchor word yok)
    for m in re.finditer(r'\bt\s*[:=]\s*([+\-]?\s*\d+(?:[.,]\d+)?)',
                         metin_lower):
        try:
            t = _negatife_cevir(
                float(m.group(1).replace(' ', '').replace(',', '.'))
            )
        except (ValueError, IndexError):
            continue
        if -10 <= t <= 0:
            return t, m.group(0)

    # Aşama 3: '-2.5 SD' / '-2,5 standart' suffix
    for m in re.finditer(
        r'([+\-]?\s*\d+(?:[.,]\d+)?)\s*(?:sd|standart)', metin_lower
    ):
        try:
            t = _negatife_cevir(
                float(m.group(1).replace(' ', '').replace(',', '.'))
            )
        except (ValueError, IndexError):
            continue
        if -10 <= t <= 0:
            return t, m.group(0)

    return None, ''


def _kalca_kirigi_var(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.A(3): osteoporotik patolojik kalça kırığı → KMY gerekmez."""
    teshis_upper = (teshis_metin or '').upper()
    if any(k in teshis_upper for k in ('S72', 'M80.05', 'M80.55', 'M84.45')):
        return True
    return any(k in metin_lower for k in (
        'kalca kirigi', 'kalça kırığı', 'kalca kirik', 'femur kirigi',
        'femur kırığı', 'femur boyun kirigi', 'femur boyun kırığı',
        'hip fracture', 'kollum femoris', 'subtrokanterik kırık',
    ))


def _kirik_var(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.A(4)(a): patolojik kırık (vertebra, vb)."""
    teshis_upper = (teshis_metin or '').upper()
    if any(k in teshis_upper for k in ('M80', 'S22', 'S32', 'S72', 'M84.4')):
        return True
    return any(k in metin_lower for k in (
        'patolojik kirik', 'patolojik kırık', 'fraktur', 'fraktür', 'fracture',
        'vertebra komp', 'kompresyon kirik', 'kompresyon kırık',
        'osteoporotik kirik', 'osteoporotik kırık',
    ))


def _sekonder_osteo_primer_tespit(metin_lower: str,
                                   teshis_metin: str) -> Optional[str]:
    """4.2.17.A(4)(ç) primer hastalık listesi taraması."""
    teshis_upper = (teshis_metin or '').upper()
    for hastalik, (kelimeler, icd_prefixleri) in _SEKONDER_OSTEO_PRIMER.items():
        for k in kelimeler:
            if k.lower() in metin_lower:
                return hastalik
        for prefix in icd_prefixleri:
            if prefix in teshis_upper:
                return hastalik
    return None


def _kortikosteroid_uzun_doz_yuksek(metin_lower: str) -> Tuple[bool, str]:
    """4.2.17.A(4)(ç): >5 mg/gün ve ≥3 ay sistemik kortikosteroid kullanımı.

    Returns: (uygun_mu, eslesen_str). Doz/süre okunamazsa (False, '') döner.
    Kullanıcı isteği: doz+süre okunamazsa KONTROL_EDİLEMEDİ default — bu
    fonksiyonun çağrıldığı yerde 'kortikosteroid kelimesi var ama doz/süre
    yok' senaryosu KONTROL_EDİLEMEDİ olarak işlenmeli.
    """
    if not metin_lower:
        return False, ''
    # Doz pattern: "prednizolon 10 mg", "deltacortril 16 mg"
    steroid_kelimeleri = ('prednizo', 'prednizolon', 'kortizon', 'kortison',
                          'metilprednizolon', 'metilprednizo', 'deksametazon',
                          'deksametazon', 'deflazakort', 'kortikosteroid',
                          'sistemik steroid', 'sistemik kortikosteroid',
                          'deltacortril', 'prednol', 'metypred', 'medrol',
                          'dekort', 'oradexon')
    doz_pat = (r'(?:' + '|'.join(re.escape(k) for k in steroid_kelimeleri)
               + r')[^a-zA-Z0-9]{0,30}(\d+(?:[.,]\d+)?)\s*mg')
    sure_pat = (r'(\d+)\s*(?:ay|hafta|yıl|yil|gün|gun)|'
                r'(?:>|≥|en az|kronik)\s*(\d+)\s*(?:ay|hafta|yıl|yil)')

    m_doz = re.search(doz_pat, metin_lower)
    if not m_doz:
        return False, ''
    try:
        doz = float(m_doz.group(1).replace(',', '.'))
    except (ValueError, IndexError):
        return False, ''
    if doz <= 5:
        return False, m_doz.group(0)

    # Süre — doz eşleşmesinin etrafında ara
    civar_b = max(0, m_doz.start() - 80)
    civar_s = min(len(metin_lower), m_doz.end() + 120)
    civar = metin_lower[civar_b:civar_s]
    m_sure = re.search(sure_pat, civar)
    if not m_sure:
        return False, m_doz.group(0)
    miktar_str = m_sure.group(1) or m_sure.group(2)
    try:
        miktar = int(miktar_str)
    except (ValueError, TypeError):
        return False, m_doz.group(0)
    birim = (m_sure.group(0) or '').lower()
    if 'yıl' in birim or 'yil' in birim:
        ay = miktar * 12
    elif 'ay' in birim:
        ay = miktar
    elif 'hafta' in birim:
        ay = miktar / 4.0
    elif 'gün' in birim or 'gun' in birim:
        ay = miktar / 30.0
    else:
        ay = 0
    if ay >= 3:
        return True, f"{m_doz.group(0)} / {m_sure.group(0)}"
    return False, m_doz.group(0)


def _kortikosteroid_kelime_var(metin_lower: str) -> bool:
    return any(k in metin_lower for k in (
        'kortikosteroid', 'kortizon', 'kortison', 'prednizolon', 'prednol',
        'metilprednizolon', 'deksametazon', 'deflazakort', 'sistemik steroid',
        'glukokortikoid', 'deltacortril', 'medrol',
    ))


def _kanser_organnakli_tespit(metin_lower: str,
                               teshis_metin: str) -> Tuple[bool, str]:
    """4.2.17.A(4)(ç): kanser tedavisi alan veya organ nakli uygulanmış."""
    if any(k in metin_lower for k in (
        'organ nakli', 'organ transplant', 'transplantasyon', 'transplant',
        'böbrek nakli', 'bobrek nakli', 'karaciğer nakli', 'karaciger nakli',
        'kalp nakli', 'kemik iliği nakli', 'kemik iligi nakli',
    )):
        return True, 'organ nakli'
    if any(k in metin_lower for k in (
        'kemoterapi', 'radyoterapi', 'kanser tedavi',
        'aromataz inhibitör', 'aromataz inhibitor', 'hormon ablasyonu',
        'androjen deprivasyon', 'tamoksifen', 'anastrozol', 'letrozol',
        'eksemestan',
    )):
        return True, 'kanser tedavisi (kemo/radyo/aromataz)'
    teshis_upper = (teshis_metin or '').upper()
    if re.search(r'\bC\d{2}', teshis_upper):
        return True, 'onkoloji ICD (C-kodu)'
    return False, ''


def _ho_endikasyonu_var(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.A(4)(d): heterotopik ossifikasyon (HO) endikasyonu (kalça
    çıkığı / bel kemiği zedelenmesi)."""
    teshis_upper = (teshis_metin or '').upper()
    if 'M61' in teshis_upper:
        return True
    return any(k in metin_lower for k in (
        'heterotopik ossifikasyon', 'heterotopik osifikasyon',
        'heterotopic ossification', 'ho endikasyon',
    ))


def _paget_var_mi(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.Ç: Paget hastalığı (M88)."""
    teshis_upper = (teshis_metin or '').upper()
    if 'M88' in teshis_upper:
        return True
    return any(k in metin_lower for k in (
        'paget hastal', 'osteitis deformans', 'pagetik',
    ))


def _agrili_vertebral_kirik(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.A(7): ağrılı vertebral kırık (kalsitonin endikasyonu)."""
    teshis_upper = (teshis_metin or '').upper()
    if 'S22' in teshis_upper or 'M48.5' in teshis_upper:
        return True
    if 'M80' in teshis_upper and any(k in metin_lower for k in (
            'agri', 'ağrı', 'agrili', 'ağrılı')):
        return True
    return ('vertebra' in metin_lower and any(k in metin_lower for k in (
        'agrili', 'ağrılı', 'agri', 'ağrı'))
            and any(k in metin_lower for k in (
                'kirik', 'kırık', 'fraktur', 'fraktür', 'kompresyon')))


def _sudek_atrofisi_var(metin_lower: str, teshis_metin: str) -> bool:
    """4.2.17.B: Sudek atrofisi / Algonörodistrofi / CRPS."""
    teshis_upper = (teshis_metin or '').upper()
    if 'M89.0' in teshis_upper:
        return True
    return any(k in metin_lower for k in (
        'sudek', 'algonorodistrofi', 'algonörodistrofi', 'algodistrofi',
        'crps', 'kompleks bölgesel ağrı', 'reflex sympathetic dystrophy',
        'kompleks rejyonel agri',
    ))


def _saglik_kurulu_raporu_mu(metin: str) -> bool:
    """Sağlık kurulu raporu mu? (uzman hekim raporundan farklı)"""
    if not metin:
        return False
    return bool(re.search(r'sa[ğg]l[iı]k\s*kurul', metin, re.IGNORECASE))


# Medula tarafında osteoporoz sağlık kurulu raporu olarak doğrulanan kodlar
_MEDULA_SK_RAPOR_KODLARI = ('06.01', '06.02')


def _osteoporoz_sk_var(metin: str, rapor_kodu: str) -> Tuple[bool, str]:
    """SUT 4.2.17.A(6)/(7)/(8) — sağlık kurulu raporu kontrolü.

    Üç kabul yolu:
      1. Rapor metninde "sağlık kurulu" lafzı geçiyor (en güçlü kanıt)
      2. Medula rapor kodu 06.01/06.02 (osteoporoz raporu) — Medula bu kodu
         verirken kurul kararını doğrulamış sayılır
      3. Hiçbiri yoksa False (KONTROL_EDILEMEDI)

    Returns: (sk_var, neden_str).
    """
    if metin and re.search(r'sa[ğg]l[iı]k\s*kurul', metin, re.IGNORECASE):
        return True, '"sağlık kurulu" lafzı rapor metninde geçti'
    rk = (rapor_kodu or '').strip()
    if rk in _MEDULA_SK_RAPOR_KODLARI:
        return True, f'Medula rapor kodu {rk} — kurul kararı varsayılır'
    return False, ('"sağlık kurulu" lafzı metinde yok ve rapor kodu '
                   '06.01/06.02 değil')


def _osteo_uzman_brans_eslesti_mi(metin: str,
                                  branslar=_OSTEO_YETKILI_BRANSLAR) -> bool:
    """Rapor metninde yetkili branş ibaresi geçiyor mu?"""
    if not metin:
        return False
    ml = _tr_lower(metin)
    return any(b in ml for b in branslar)


def _bifosfonat_onkosul_var_mi(metin_lower: str):
    """SUT 4.2.17.A(6)(b) ön-koşul taraması: teriparatid/romosozumab/stronsiyum
    için 'bifosfonat intolerans/yan etki/yetersiz yanıt' VEYA 'ciddi
    osteoporoz' alternatifi raporda lafzen geçiyor mu?

    Dönüş: (SartDurumu, açıklama) — VAR/KONTROL_EDILEMEDI.
    YOK dönmez; intolerans/yetersiz yanıt klinik bir karardır,
    sessizce 'YOK' demek hatalı — manuel doğrulama bekletilir.
    """
    if not metin_lower:
        return SartDurumu.KONTROL_EDILEMEDI, 'Rapor metni boş'

    # Alternatif 1: bifosfonat intolerans/yan etki/yetersiz yanıt
    intolerans_kalip = re.compile(
        r'(bifosfonat|alendronat|risedronat|zoledronat|ibandronat|'
        r'fosamax|fosavance|actonel|aclasta|bonviva)\w{0,8}\s+'
        r'(intoleran|yan\s*etki|yetersiz\s*yan[ıi]t|yan[ıi]ts[ıi]z|'
        r'cevaps[ıi]z|kullanamaz|kullan[ıi]lamaz|kontrendike|'
        r'kontraendike|tedavi(?:si)?\s+ba[şs]ar[ıi]s[ıi]z|'
        r'tolere\s+ed[ie]me)',
        re.IGNORECASE)
    if intolerans_kalip.search(metin_lower):
        m = intolerans_kalip.search(metin_lower)
        return SartDurumu.VAR, f'Bifosfonat ön-koşul ibaresi: "{m.group(0)}"'

    # Alternatif 2: 'ciddi osteoporoz' veya 'ağır osteoporoz' lafzı
    if re.search(r'(ciddi|a[ğg][ıi]r|severe)\s+osteoporoz', metin_lower):
        return SartDurumu.VAR, 'Ciddi/ağır osteoporoz ibaresi (alternatif şart)'

    return (SartDurumu.KONTROL_EDILEMEDI,
            'Bifosfonat intolerans/yetersiz yanıt veya ciddi osteoporoz '
            'ibaresi rapor metninde lafzen bulunamadı (manuel doğrulama)')


def _endikasyon_disi_onay_var_mi(metin_lower: str):
    """SUT 4.1.4 — endikasyon dışı kullanım için Bakanlık/SGK onayı şartı.

    Rapor metninde 'endikasyon dışı' ibaresi geçiyorsa, ek olarak Sağlık
    Bakanlığı / SGK / komisyon onayı ibaresi aranır.

    Dönüş:
      None → 'endikasyon dışı' ibaresi yok, şart uygulanmaz
      (SartDurumu.VAR, açıklama) → endikasyon dışı + onay ibaresi VAR
      (SartDurumu.KONTROL_EDILEMEDI, açıklama) → endikasyon dışı VAR ama
        onay ibaresi metinde lafzen bulunamadı (manuel doğrulama)
    """
    if not metin_lower:
        return None
    if not re.search(r'endikasyon\s*d[ıi][şs][ıi]', metin_lower):
        return None
    onay_kalip = re.compile(
        r'(sa[ğg]l[ıi]k\s*bakanl[ıi][ğg][ıi]|bakanl[ıi]k\s*onay|'
        r'sgk\s*onay|komisyon\s*karar|titck\s*onay|'
        r'endikasyon\s*d[ıi][şs][ıi]\s*kullan[ıi]m\s*onay)',
        re.IGNORECASE)
    if onay_kalip.search(metin_lower):
        m = onay_kalip.search(metin_lower)
        return (SartDurumu.VAR,
                f'Endikasyon dışı kullanım onayı ibaresi: "{m.group(0)}"')
    return (SartDurumu.KONTROL_EDILEMEDI,
            'Rapor "endikasyon dışı" ibaresi içeriyor; Bakanlık/SGK/komisyon '
            'onayı ibaresi metinde bulunamadı (SUT 4.1.4 — manuel doğrulama)')


# ── Kontrol fonksiyonları ─────────────────────────────────────────────

def kontrol_bifosfonat(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.17.A — Bifosfonat (osteoporoz)
    + 4.2.17.A(4)(d) HO endikasyonu (KMY gerekmez)
    + 4.2.17.C Juvenil osteoporoz (yaş <18)
    + 4.2.17.Ç Paget hastalığı (M88)

    Şart taraması: yaş + KMY tarihi + KMY ölçüm yeri + T-skoru +
    kırık + sekonder osteoporoz primer hastalık + kortikosteroid doz/süre +
    kanser/organ nakli + doktor branşı + rapor kodu + kombi yasağı.

    Tüm şartlar VAR / YOK / KONTROL_EDİLEMEDİ olarak değerlendirilir
    (CLAUDE.md disiplini).
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik)

    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').strip()
    hasta_yasi = _osteo_yas_oku(ilac_sonuc, birlesik)

    sartlar: List[SartSonuc] = []
    detaylar: Dict = {
        'sut_maddesi': '4.2.17.A',
        'hasta_yasi': hasta_yasi,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
    }
    sut_kurali = ('SUT 4.2.17.A — Bifosfonat: rapor + KMY (son 2 yıl) + '
                  'yaşa göre T-skoru eşiği')

    if not metin_lower:
        # Rapor metni boş — rapor kodu olmadan bifosfonat ödenmez
        # (SUT 4.2.17.A(1): uzman hekim raporu zorunlu)
        if not rapor_kodu:
            sartlar.append(SartSonuc('Rapor kodu', SartDurumu.YOK,
                                     'Reçete satırında rap_kod boş',
                                     'rap_kod'))
            sartlar.append(SartSonuc('Rapor/mesaj metni', SartDurumu.YOK,
                                     'Metin boş ve rapor da yok',
                                     'tum_metin'))
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                "Raporsuz bifosfonat — uzman hekim raporu zorunlu",
                detaylar=detaylar, sartlar=sartlar, sut_kurali=sut_kurali,
                aranan_ibare='rapor / T-skoru / KMY')
        # Rapor kodu var ama metin Medula'dan çekilememiş → manuel doğrulama
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.VAR,
                                 rapor_kodu, 'rap_kod'))
        sartlar.append(SartSonuc('Rapor/mesaj metni',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'Rapor kodu var ancak metni okunamadı',
                                 'tum_metin'))
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f"Rapor kodu var ({rapor_kodu}) ama metni okunamadı — "
            "manuel doğrulama gerekli",
            detaylar=detaylar, sartlar=sartlar, sut_kurali=sut_kurali,
            aranan_ibare='T-skoru / KMY / DEXA / kırık')

    # ── Kombinasyon yasağı (4.2.17.A(1) son cümle) ────────────────────
    kombi_var, kombi_ilac = _osteo_kombi_var(ilac_sonuc, 'BIFOSFONAT')
    if kombi_var:
        sartlar.append(SartSonuc(
            'Osteoporoz ilaç kombinasyon yasağı',
            SartDurumu.YOK,
            f'Aynı reçetede ek osteoporoz ilacı: {kombi_ilac}',
            'recete_ilaclari'))
    else:
        sartlar.append(SartSonuc(
            'Osteoporoz ilaç kombinasyon yasağı', SartDurumu.VAR,
            'Aynı reçetede başka osteoporoz ilacı yok', 'recete_ilaclari'))

    # ── 1) Paget hastalığı dalı (4.2.17.Ç) ────────────────────────────
    if _paget_var_mi(metin_lower, teshis_metin):
        return _kontrol_paget(rapor_kodu, doktor_brans, sartlar, detaylar,
                              kombi_var, kombi_ilac, metin_lower)

    # ── 2) Juvenil osteoporoz dalı (4.2.17.C) ─────────────────────────
    if hasta_yasi is not None and hasta_yasi < 18:
        return _kontrol_juvenil_osteoporoz(rapor_kodu, doktor_brans,
                                           hasta_yasi, sartlar, detaylar,
                                           kombi_var, kombi_ilac)

    # ── 3) HO endikasyonu (4.2.17.A(4)(d)) ────────────────────────────
    if _ho_endikasyonu_var(metin_lower, teshis_metin):
        sartlar.append(SartSonuc('HO endikasyonu (kalça çıkığı/bel zedelenmesi)',
                                 SartDurumu.VAR, 'M61 / heterotopik ossifikasyon',
                                 'rapor_metni/teshis'))
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='Bifosfonat HO endikasyonu — KMY ölçüm sonucu aranmaz',
            detaylar={**detaylar, 'alt_dal': 'HO_4.2.17.A.4.d'},
            sartlar=sartlar,
            sut_kurali='SUT 4.2.17.A(4)(d) — HO endikasyonu',
            uyari=('Prospektüsteki dozlar ve sürelerde kullanılır. '
                   'Bifosfonatın HO formu olduğu doğrulanmalı.'),
            aranan_ibare='heterotopik ossifikasyon / kalça çıkığı / bel zedelenmesi'
        )

    # ── 4) Genel akış (4.2.17.A(2)-(5)) ───────────────────────────────

    # Rapor kodu (4.2.17.A(1))
    if rapor_kodu:
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.VAR,
                                 rapor_kodu, 'rap_kod'))
    else:
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.YOK,
                                 'Reçete satırında rap_kod boş', 'rap_kod'))

    # Doktor branşı (4.2.17.A(5)) — bilgi amaçlı; SUT lafzına göre
    # bifosfonat tüm uzmanlarca reçete edilebilir, ama RAPORU yetkili
    # branş düzenlemiş olmalı. Doktor branşı yetkili değilse rapor
    # metninde yetkili branş ibaresi aranır.
    if _osteo_yetkili_brans(doktor_brans):
        sartlar.append(SartSonuc('Reçete yazan doktor branşı',
                                 SartDurumu.VAR,
                                 doktor_brans, 'doktor_uzmanligi'))
    elif doktor_brans:
        # Reçete tüm uzmanlarca yazılabilir — bilgi notu
        sartlar.append(SartSonuc('Reçete yazan doktor branşı',
                                 SartDurumu.VAR,
                                 f'{doktor_brans} (tüm uzmanlar reçete yazabilir)',
                                 'doktor_uzmanligi'))
    else:
        sartlar.append(SartSonuc('Reçete yazan doktor branşı',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'Doktor branşı bilgisi boş',
                                 'doktor_uzmanligi'))

    # Rapor düzenleyen yetkili branş (4.2.17.A(5))
    if _osteo_uzman_brans_eslesti_mi(birlesik):
        sartlar.append(SartSonuc('Raporu düzenleyen yetkili branş',
                                 SartDurumu.VAR,
                                 'Rapor metninde yetkili branş ibaresi var',
                                 'rapor_metni'))
    else:
        sartlar.append(SartSonuc('Raporu düzenleyen yetkili branş',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 ('Rapor metninde İç hast/FTR/Romatoloji/'
                                  'Ortopedi/Kadın doğum/Endokrinoloji/'
                                  'Tıbbi ekoloji uzman ibaresi bulunamadı'),
                                 'rapor_metni'))

    # ── KMY istisna kontrolü (4.2.17.A(3)) — KMY tarih/yer şartlarından ÖNCE
    yas_75_ustu = (hasta_yasi is not None and hasta_yasi >= 75)
    kalca_kirigi = _kalca_kirigi_var(metin_lower, teshis_metin)
    kmy_istisna = yas_75_ustu or kalca_kirigi
    istisna_neden = ('75 yaş üstü' if yas_75_ustu
                     else ('osteoporotik kalça kırığı' if kalca_kirigi else ''))

    # KMY tarihi (4.2.17.A(2)) — referans: reçete tarihi
    recete_tarih_dt = _parse_tarih_str(ilac_sonuc.get('recete_tarihi'))
    detaylar['recete_tarihi'] = (recete_tarih_dt.isoformat()
                                 if recete_tarih_dt else None)

    if kmy_istisna:
        # 4.2.17.A(3): KMY ölçüm şartı aranmaz — şartları NA olarak işaretle
        sartlar.append(SartSonuc('KMY tarihi (son 2 yıl)', SartDurumu.NA,
                                 f'Aranmaz — istisna: {istisna_neden}',
                                 '4.2.17.A(3)'))
        sartlar.append(SartSonuc('KMY ölçüm yeri (lomber/femur)',
                                 SartDurumu.NA,
                                 f'Aranmaz — istisna: {istisna_neden}',
                                 '4.2.17.A(3)'))
    else:
        kmy_tarih, kmy_2yil = _kmy_tarihi_parse(birlesik, metin_lower,
                                                referans_tarih=recete_tarih_dt)
        if kmy_tarih:
            ref_etiket = ('reçete tarihi' if recete_tarih_dt else 'bugün')
            if kmy_2yil:
                sartlar.append(SartSonuc('KMY tarihi (son 2 yıl)',
                                         SartDurumu.VAR,
                                         f'{kmy_tarih} ({ref_etiket}\'e göre)',
                                         'rapor_metni regex'))
            else:
                sartlar.append(SartSonuc('KMY tarihi (son 2 yıl)',
                                         SartDurumu.YOK,
                                         f'KMY {kmy_tarih} > 2 yıl ({ref_etiket}\'e göre)',
                                         'rapor_metni regex'))
        else:
            sartlar.append(SartSonuc('KMY tarihi (son 2 yıl)',
                                     SartDurumu.KONTROL_EDILEMEDI,
                                     'KMY/DEXA ölçüm tarihi metinde bulunamadı',
                                     'rapor_metni'))

        if _kmy_olcum_yeri_uygun(metin_lower):
            sartlar.append(SartSonuc('KMY ölçüm yeri (lomber/femur)',
                                     SartDurumu.VAR, '', 'rapor_metni'))
        else:
            sartlar.append(SartSonuc('KMY ölçüm yeri (lomber/femur)',
                                     SartDurumu.KONTROL_EDILEMEDI,
                                     'lomber/femur ibaresi bulunamadı',
                                     'rapor_metni'))

    # ── 75 yaş üstü → KMY ölçümü gerekmez (4.2.17.A(3)) ───────────────
    if yas_75_ustu:
        sartlar.append(SartSonuc('75 yaş üstü (KMY istisnası)',
                                 SartDurumu.VAR,
                                 f'Yaş: {hasta_yasi}', 'hasta_yasi'))
        return _osteo_karar_topla(
            sonuc=(KontrolSonucu.UYGUN_DEGIL if not rapor_kodu
                   else (KontrolSonucu.UYGUN_DEGIL if kombi_var
                         else KontrolSonucu.UYGUN)),
            mesaj=(f'75+ yaş ({hasta_yasi}) — KMY gerekmez'
                   if rapor_kodu and not kombi_var
                   else 'Rapor/kombinasyon ihlali var — bkz. şartlar'),
            detaylar={**detaylar, 'alt_dal': '75+_KMY_GEREKMEZ'},
            sartlar=sartlar, sut_kurali=sut_kurali,
            aranan_ibare='75 yaş üstü hasta')

    # Kalça kırığı → KMY gerekmez
    if kalca_kirigi:
        sartlar.append(SartSonuc('Patolojik kalça kırığı (KMY istisnası)',
                                 SartDurumu.VAR, 'kalça/femur kırığı',
                                 'rapor_metni/teshis'))
        return _osteo_karar_topla(
            sonuc=(KontrolSonucu.UYGUN_DEGIL if not rapor_kodu
                   else (KontrolSonucu.UYGUN_DEGIL if kombi_var
                         else KontrolSonucu.UYGUN)),
            mesaj=('Osteoporotik kalça kırığı — KMY gerekmez'
                   if rapor_kodu and not kombi_var
                   else 'Rapor/kombinasyon ihlali var — bkz. şartlar'),
            detaylar={**detaylar, 'alt_dal': 'KALCA_KIRIGI_KMY_GEREKMEZ'},
            sartlar=sartlar, sut_kurali=sut_kurali,
            aranan_ibare='kalça kırığı / femur kırığı')

    # ── T-skoru ve eşik kontrolü (4.2.17.A(4)) ────────────────────────
    t_skoru, t_eslesen = _t_skoru_parse(metin_lower, birlesik)
    detaylar['t_skoru'] = t_skoru

    kirik = _kirik_var(metin_lower, teshis_metin)
    if kirik:
        sartlar.append(SartSonuc('Patolojik kırık (vertebra/diğer)',
                                 SartDurumu.VAR, '', 'rapor_metni/teshis'))

    # Sekonder osteoporoz şartları
    primer_hastalik = _sekonder_osteo_primer_tespit(metin_lower, teshis_metin)
    kortiko_uygun, kortiko_str = _kortikosteroid_uzun_doz_yuksek(metin_lower)
    kanser_organ_var, kanser_organ_neden = _kanser_organnakli_tespit(
        metin_lower, teshis_metin)

    sekonder_sartlar = []
    if primer_hastalik:
        sekonder_sartlar.append(f'primer hastalık: {primer_hastalik}')
    if kortiko_uygun:
        sekonder_sartlar.append(f'kortikosteroid >5mg ≥3ay ({kortiko_str})')
    if kanser_organ_var:
        sekonder_sartlar.append(kanser_organ_neden)

    if sekonder_sartlar:
        sartlar.append(SartSonuc(
            'Sekonder osteoporoz şartı (4.2.17.A(4)(ç))', SartDurumu.VAR,
            ' / '.join(sekonder_sartlar), 'rapor_metni/teshis'))
        sekonder_var = True
    elif _kortikosteroid_kelime_var(metin_lower):
        sartlar.append(SartSonuc(
            'Sekonder osteoporoz şartı (4.2.17.A(4)(ç))',
            SartDurumu.KONTROL_EDILEMEDI,
            'Kortikosteroid ibaresi var ama doz (>5mg) ve süre (≥3ay) parse edilemedi',
            'rapor_metni'))
        sekonder_var = False
    else:
        sartlar.append(SartSonuc(
            'Sekonder osteoporoz şartı (4.2.17.A(4)(ç))', SartDurumu.YOK,
            ('Primer hastalık listesi / steroid >5mg ≥3ay / kanser tedavisi / '
             'organ nakli bulunamadı'),
            'rapor_metni/teshis'))
        sekonder_var = False

    if t_skoru is not None:
        sartlar.append(SartSonuc('T-skoru sayısal değeri', SartDurumu.VAR,
                                 f'T = {t_skoru}', 'rapor_metni regex'))
    else:
        sartlar.append(SartSonuc('T-skoru sayısal değeri',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'Raporda DEXA T-skoru sayısal değeri yok',
                                 'rapor_metni'))

    # Karar matrisi
    sonuc, mesaj, alt_dal = _bifosfonat_karar_matrisi(
        t_skoru, hasta_yasi, kirik, sekonder_var, rapor_kodu, kombi_var)
    detaylar['alt_dal'] = alt_dal

    return _osteo_karar_topla(
        sonuc=sonuc, mesaj=mesaj, detaylar=detaylar, sartlar=sartlar,
        sut_kurali=sut_kurali,
        aranan_ibare='T-skoru / yaş / kırık / sekonder şart',
        bulunan_metin=t_eslesen)


def _bifosfonat_karar_matrisi(t_skoru, hasta_yasi, kirik, sekonder_var,
                               rapor_kodu, kombi_var):
    """T-skoru + yaş + kırık + sekonder şartlarına göre karar üret.

    Returns: (KontrolSonucu, mesaj, alt_dal_etiketi).
    """
    if not rapor_kodu:
        return (KontrolSonucu.UYGUN_DEGIL,
                'Bifosfonat RAPORSUZ — uzman raporu zorunlu (SUT 4.2.17.A(1))',
                'RAPORSUZ')
    if kombi_var:
        return (KontrolSonucu.UYGUN_DEGIL,
                'Aynı reçetede ek osteoporoz ilacı — SUT 4.2.17.A(1) son cümle: '
                'sadece birinin bedeli ödenir',
                'KOMBI_YASAK')

    if t_skoru is None:
        return (KontrolSonucu.KONTROL_EDILEMEDI,
                'T-skoru sayısal değeri raporda bulunamadı — manuel doğrulama',
                'T_SKORU_YOK')

    # ç) Sekonder osteoporoz: T ≤ -1 yeterli
    if sekonder_var and t_skoru <= -1:
        return (KontrolSonucu.UYGUN,
                f'T={t_skoru} ≤ -1 + sekonder osteoporoz şartı sağlandı',
                'SEKONDER_T_-1')

    # a) Patolojik kırık + T ≤ -1
    if kirik and t_skoru <= -1:
        return (KontrolSonucu.UYGUN,
                f'T={t_skoru} ≤ -1 + patolojik kırık (4.2.17.A(4)(a))',
                'KIRIK_T_-1')

    # b) 65+ kırıksız: T ≤ -2.5
    # c) 65 altı kırıksız: T ≤ -3
    if hasta_yasi is None:
        # Yaş bilinmiyor — şüpheli
        if t_skoru <= -3:
            return (KontrolSonucu.UYGUN,
                    f'T={t_skoru} ≤ -3 (yaş bilinmiyor, en düşük eşik sağlandı)',
                    'YAS_BILINMIYOR_T_-3')
        if t_skoru <= -2.5:
            return (KontrolSonucu.KONTROL_EDILEMEDI,
                    f'T={t_skoru} ≤ -2.5; yaş bilinmiyor — 65+ ise UYGUN, '
                    '65 altı ise UYGUN_DEĞİL (T ≤ -3 gerekli)',
                    'YAS_BILINMIYOR_T_-2.5')
        if t_skoru <= -1:
            return (KontrolSonucu.UYGUN_DEGIL,
                    f'T={t_skoru} > -2.5 ve kırık/sekonder şart yok — endikasyon yok',
                    'T_-1_-2.5_KIRIKSIZ')
        return (KontrolSonucu.UYGUN_DEGIL,
                f'T={t_skoru} > -1 — bifosfonat endikasyonu yok',
                'T_USTU_-1')

    if hasta_yasi >= 65:
        if t_skoru <= -2.5:
            return (KontrolSonucu.UYGUN,
                    f'T={t_skoru} ≤ -2.5 + yaş {hasta_yasi} ≥ 65 (4.2.17.A(4)(b))',
                    '65PLUS_T_-2.5')
        if t_skoru <= -1:
            return (KontrolSonucu.UYGUN_DEGIL,
                    f'T={t_skoru} > -2.5 ve kırık/sekonder şart yok — yaş {hasta_yasi}',
                    '65PLUS_KIRIKSIZ_YETERSIZ')
        return (KontrolSonucu.UYGUN_DEGIL,
                f'T={t_skoru} > -1 — bifosfonat endikasyonu yok',
                'T_USTU_-1')
    else:
        # 65 altı (18-64 — juvenil zaten ayrı dalda)
        if t_skoru <= -3:
            return (KontrolSonucu.UYGUN,
                    f'T={t_skoru} ≤ -3 + yaş {hasta_yasi} < 65 (4.2.17.A(4)(c))',
                    '65ALTI_T_-3')
        if t_skoru <= -1:
            return (KontrolSonucu.UYGUN_DEGIL,
                    f'T={t_skoru} > -3 ve kırık/sekonder şart yok — yaş {hasta_yasi}',
                    '65ALTI_KIRIKSIZ_YETERSIZ')
        return (KontrolSonucu.UYGUN_DEGIL,
                f'T={t_skoru} > -1 — bifosfonat endikasyonu yok',
                'T_USTU_-1')


def _osteo_karar_topla(sonuc, mesaj, detaylar, sartlar, sut_kurali,
                       aranan_ibare='', bulunan_metin='', uyari=None):
    """KontrolRaporu üretici — şart listesi UYGUN/UYGUN_DEĞİL/ŞÜPHELİ
    sınıflandırmasıyla birlikte döner."""
    var_sayisi = sum(1 for s in sartlar if s.durum == SartDurumu.VAR)
    yok_sayisi = sum(1 for s in sartlar if s.durum == SartDurumu.YOK)
    kontrol_edilemedi_sayisi = sum(1 for s in sartlar
                                    if s.durum == SartDurumu.KONTROL_EDILEMEDI)
    detaylar = {**detaylar,
                'sart_var': var_sayisi, 'sart_yok': yok_sayisi,
                'sart_kontrol_edilemedi': kontrol_edilemedi_sayisi}
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, detaylar=detaylar, sartlar=sartlar,
        sut_kurali=sut_kurali, uyari=uyari,
        aranan_ibare=aranan_ibare, bulunan_metin=bulunan_metin)


def _kontrol_paget(rapor_kodu, doktor_brans, sartlar, detaylar,
                   kombi_var, kombi_ilac, metin_lower):
    """SUT 4.2.17.Ç — Paget hastalığı: Endokrinoloji uzman raporu, 1 yıl."""
    sartlar.append(SartSonuc('Paget hastalığı endikasyonu', SartDurumu.VAR,
                             'M88 / paget ibaresi', 'rapor_metni/teshis'))
    sut_kurali = ('SUT 4.2.17.Ç — Paget: Endokrinoloji uzman raporu, '
                  'rapor süresi 1 yıl')

    if rapor_kodu:
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.VAR, rapor_kodu,
                                 'rap_kod'))
    else:
        sartlar.append(SartSonuc('Rapor kodu', SartDurumu.YOK,
                                 'Reçetede rap_kod boş', 'rap_kod'))

    endokrin_brans = ('endokrin' in _tr_lower(doktor_brans)
                      if doktor_brans else False)
    endokrin_metin = 'endokrin' in metin_lower
    if endokrin_brans or endokrin_metin:
        sartlar.append(SartSonuc('Endokrinoloji uzman raporu',
                                 SartDurumu.VAR,
                                 ('doktor branşı endokrin' if endokrin_brans
                                  else 'rapor metninde endokrin ibaresi'),
                                 ('doktor_uzmanligi' if endokrin_brans
                                  else 'rapor_metni')))
        endokrin_var = True
    else:
        sartlar.append(SartSonuc('Endokrinoloji uzman raporu',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 ('Endokrinoloji ibaresi rapor/branş bilgisinde '
                                  'bulunamadı'),
                                 'doktor_uzmanligi/rapor_metni'))
        endokrin_var = False

    detaylar = {**detaylar, 'alt_dal': 'PAGET_4.2.17.Ç'}

    if not rapor_kodu:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            'Paget hastalığı RAPORSUZ — Endokrinoloji uzman raporu zorunlu',
            detaylar, sartlar, sut_kurali,
            aranan_ibare='Endokrinoloji uzman raporu')
    if kombi_var:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Paget + ek osteoporoz ilacı ({kombi_ilac}) — kombi yasağı',
            detaylar, sartlar, sut_kurali)
    if not endokrin_var:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            'Paget — Endokrinoloji uzmanlığı manuel doğrulanmalı',
            detaylar, sartlar, sut_kurali,
            uyari='Rapor süresi 1 yıl olmalı')
    return _osteo_karar_topla(
        KontrolSonucu.UYGUN,
        'Paget — Endokrinoloji uzman raporu (rapor süresi 1 yıl olmalı)',
        detaylar, sartlar, sut_kurali,
        uyari='Rapor süresi 1 yıl ile sınırlı (4.2.17.Ç)')


def _kontrol_juvenil_osteoporoz(rapor_kodu, doktor_brans, hasta_yasi,
                                 sartlar, detaylar, kombi_var, kombi_ilac):
    """SUT 4.2.17.C — Juvenil osteoporoz: uzman hekim raporu, 1 yıl."""
    sartlar.append(SartSonuc('Juvenil osteoporoz dalı (yaş < 18)',
                             SartDurumu.VAR,
                             f'Yaş: {hasta_yasi}', 'hasta_yasi'))
    sut_kurali = ('SUT 4.2.17.C — Juvenil osteoporoz: uzman hekim raporu, '
                  'rapor süresi 1 yıl')

    if rapor_kodu:
        sartlar.append(SartSonuc('Uzman hekim rapor kodu', SartDurumu.VAR,
                                 rapor_kodu, 'rap_kod'))
    else:
        sartlar.append(SartSonuc('Uzman hekim rapor kodu', SartDurumu.YOK,
                                 'Reçetede rap_kod boş', 'rap_kod'))

    detaylar = {**detaylar, 'alt_dal': 'JUVENIL_4.2.17.C'}

    if not rapor_kodu:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Juvenil osteoporoz (yaş {hasta_yasi}) RAPORSUZ — uzman raporu zorunlu',
            detaylar, sartlar, sut_kurali,
            aranan_ibare='Uzman hekim raporu')
    if kombi_var:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Juvenil osteoporoz + ek osteoporoz ilacı ({kombi_ilac}) — '
            'kombi yasağı',
            detaylar, sartlar, sut_kurali)
    return _osteo_karar_topla(
        KontrolSonucu.UYGUN,
        f'Juvenil osteoporoz (yaş {hasta_yasi}) — uzman raporu mevcut',
        detaylar, sartlar, sut_kurali,
        uyari='Rapor süresi 1 yıl ile sınırlı (4.2.17.C)')


def kontrol_raloksifen(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.17.A(6)(a) — Raloksifen / Bazedoksifen.

    Şart: bifosfonatları tolere edemeyen veya yeterli yanıt alınamayan
    osteoporozlu hastalarda + sağlık kurulu raporu (yetkili branşlardan
    en az birinin yer aldığı) + bifosfonat eşik kuralları (T-skoru/yaş/kırık).
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik)
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()

    sartlar: List[SartSonuc] = []
    detaylar = {'alt_kategori': 'RALOKSIFEN', 'sut_maddesi': '4.2.17.A(6a)',
                'rapor_kodu': rapor_kodu}
    sut_kurali = ('SUT 4.2.17.A(6)(a) — Raloksifen: bifosfonat intolerans/'
                  'yetersiz yanıt + sağlık kurulu raporu')

    # Kombinasyon
    kombi_var, kombi_ilac = _osteo_kombi_var(ilac_sonuc, 'RALOKSIFEN')
    if kombi_var:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.YOK,
                                 f'Aynı reçetede: {kombi_ilac}',
                                 'recete_ilaclari'))
    else:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.VAR,
                                 'Aynı reçetede başka osteoporoz ilacı yok',
                                 'recete_ilaclari'))

    # Rapor kodu
    if rapor_kodu:
        sartlar.append(SartSonuc('Sağlık kurulu rapor kodu', SartDurumu.VAR,
                                 rapor_kodu, 'rap_kod'))
    else:
        sartlar.append(SartSonuc('Sağlık kurulu rapor kodu', SartDurumu.YOK,
                                 'Reçetede rap_kod boş', 'rap_kod'))

    # Sağlık kurulu raporu mu? (lafzen VEYA Medula rapor kodu 06.01/06.02)
    sk_var, sk_neden = _osteoporoz_sk_var(birlesik, rapor_kodu)
    if sk_var:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.VAR, sk_neden,
                                 'rapor_metni/rap_kod'))
    else:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 sk_neden, 'rapor_metni/rap_kod'))

    # Yetkili branş ibaresi
    if _osteo_uzman_brans_eslesti_mi(birlesik):
        sartlar.append(SartSonuc('Yetkili uzman branş (en az biri)',
                                 SartDurumu.VAR,
                                 'Yetkili branş ibaresi mevcut', 'rapor_metni'))
    else:
        sartlar.append(SartSonuc('Yetkili uzman branş (en az biri)',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'İç hast/FTR/Romatoloji/Ortopedi/Kadın doğum/'
                                 'Endokrinoloji ibaresi rapor metninde yok',
                                 'rapor_metni'))

    # Bifosfonat intolerans / yetersiz yanıt
    intolerans = any(k in metin_lower for k in (
        'bifosfonat intoleran', 'bifosfonata intoleran', 'tolere edemiyor',
        'tolere edemeyen', 'yan etki', 'gis intoleran', 'reflu',
        'yetersiz yanit', 'yetersiz yanıt', 'yanitsiz', 'yanıtsız',
    ))
    if intolerans:
        sartlar.append(SartSonuc(
            'Bifosfonat intolerans/yetersiz yanıt',
            SartDurumu.VAR, 'Rapor metninde ibare bulundu', 'rapor_metni'))
    else:
        sartlar.append(SartSonuc(
            'Bifosfonat intolerans/yetersiz yanıt',
            SartDurumu.KONTROL_EDILEMEDI,
            'Rapor metninde "bifosfonat intolerans/yetersiz yanıt" ibaresi yok',
            'rapor_metni'))

    # Bifosfonat eşik kuralı (T-skoru/yaş/kırık) — alt-rapor olarak ekle
    bif_rapor = kontrol_bifosfonat(ilac_sonuc)
    sartlar.extend([SartSonuc(f'[Bifosfonat eşik] {s.ad}', s.durum,
                              s.neden, s.kaynak)
                    for s in bif_rapor.sartlar
                    if s.ad not in ('Osteoporoz ilaç kombinasyon yasağı',)])

    # Karar
    if not rapor_kodu:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            'Raloksifen RAPORSUZ — sağlık kurulu raporu zorunlu',
            detaylar, sartlar, sut_kurali,
            aranan_ibare='Sağlık kurulu raporu')
    if kombi_var:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Raloksifen + ek osteoporoz ilacı ({kombi_ilac}) — kombi yasağı',
            detaylar, sartlar, sut_kurali)
    if not intolerans:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            ('Raloksifen — "bifosfonat intolerans/yetersiz yanıt" ibaresi '
             'rapor metninde bulunamadı (manuel doğrulama)'),
            detaylar, sartlar, sut_kurali,
            uyari='SUT 4.2.17.A(6)(a) ön şart: bifosfonata intolerans/yetersiz yanıt')
    if not sk_var:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            'Raloksifen — sağlık kurulu raporu ibaresi metinde bulunamadı',
            detaylar, sartlar, sut_kurali,
            uyari='Sağlık kurulu raporu (uzman hekim raporundan farklı) gerekli')
    # Bifosfonat eşik sonucu
    if bif_rapor.sonuc == KontrolSonucu.UYGUN_DEGIL:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Raloksifen — bifosfonat eşik kuralları sağlanmıyor: {bif_rapor.mesaj}',
            detaylar, sartlar, sut_kurali)
    if bif_rapor.sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f'Raloksifen — bifosfonat eşik şüpheli: {bif_rapor.mesaj}',
            detaylar, sartlar, sut_kurali)
    return _osteo_karar_topla(
        KontrolSonucu.UYGUN,
        ('Raloksifen — sağlık kurulu raporu + bifosfonat intolerans/'
         'yetersiz yanıt + T-skoru eşiği sağlandı'),
        detaylar, sartlar, sut_kurali)


def kontrol_kalsitonin(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.17.A(7-8) — Kalsitonin (osteoporoz)
    + SUT 4.2.17.B — Sudek atrofisi (algonörodistrofi)

    (7) Ağrılı vertebral kırık + sağlık kurulu raporu + her kırıkta max 3 ay
    (8) Ağrısız + bifosfonat intolerans + sağlık kurulu raporu + 3. basamak
    4.2.17.B — Sudek atrofisi: tanıdan sonraki ilk 6 ay (FTR/Ortopedi/Romatoloji)
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik)
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').strip()

    sartlar: List[SartSonuc] = []
    detaylar = {'alt_kategori': 'KALSITONIN', 'rapor_kodu': rapor_kodu}

    # Kombinasyon
    kombi_var, kombi_ilac = _osteo_kombi_var(ilac_sonuc, 'KALSITONIN')
    if kombi_var:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.YOK,
                                 f'Aynı reçetede: {kombi_ilac}',
                                 'recete_ilaclari'))
    else:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.VAR,
                                 'Aynı reçetede başka osteoporoz ilacı yok',
                                 'recete_ilaclari'))

    # ── 4.2.17.B Sudek atrofisi dalı ─────────────────────────────────
    if _sudek_atrofisi_var(metin_lower, teshis_metin):
        sartlar.append(SartSonuc('Sudek atrofisi (algonörodistrofi/CRPS)',
                                 SartDurumu.VAR, '', 'rapor_metni/teshis'))
        sut_kurali = ('SUT 4.2.17.B — Sudek atrofisi: tanıdan itibaren ilk '
                      '6 ay FTR/Ortopedi/Romatoloji uzman raporu')
        detaylar['alt_dal'] = 'SUDEK_4.2.17.B'

        sudek_yetkili = ('fizik tedavi', 'fiziksel tip', 'fiziksel tıp',
                         'ftr', 'rehabilitasyon', 'ortopedi', 'travmatoloj',
                         'romatoloj')
        if _osteo_yetkili_brans(doktor_brans, sudek_yetkili):
            sartlar.append(SartSonuc('FTR/Ortopedi/Romatoloji uzmanı',
                                     SartDurumu.VAR, doktor_brans,
                                     'doktor_uzmanligi'))
            sudek_brans_var = True
        elif _osteo_uzman_brans_eslesti_mi(birlesik, sudek_yetkili):
            sartlar.append(SartSonuc('FTR/Ortopedi/Romatoloji uzmanı',
                                     SartDurumu.VAR,
                                     'Rapor metninde branş ibaresi var',
                                     'rapor_metni'))
            sudek_brans_var = True
        else:
            sartlar.append(SartSonuc('FTR/Ortopedi/Romatoloji uzmanı',
                                     SartDurumu.KONTROL_EDILEMEDI,
                                     'Branş bilgisi/ibaresi bulunamadı',
                                     'doktor_uzmanligi/rapor_metni'))
            sudek_brans_var = False

        if rapor_kodu:
            sartlar.append(SartSonuc('Uzman hekim raporu', SartDurumu.VAR,
                                     rapor_kodu, 'rap_kod'))
        else:
            sartlar.append(SartSonuc('Uzman hekim raporu', SartDurumu.YOK,
                                     'Rap_kod boş', 'rap_kod'))
            return _osteo_karar_topla(
                KontrolSonucu.UYGUN_DEGIL,
                'Sudek atrofisi — kalsitonin RAPORSUZ',
                detaylar, sartlar, sut_kurali,
                aranan_ibare='Uzman hekim raporu')

        if kombi_var:
            return _osteo_karar_topla(
                KontrolSonucu.UYGUN_DEGIL,
                f'Sudek + ek osteoporoz ilacı ({kombi_ilac}) — kombi yasağı',
                detaylar, sartlar, sut_kurali)
        if not sudek_brans_var:
            return _osteo_karar_topla(
                KontrolSonucu.KONTROL_EDILEMEDI,
                'Sudek atrofisi — FTR/Ortopedi/Romatoloji branşı manuel doğrulanmalı',
                detaylar, sartlar, sut_kurali)
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            'Sudek atrofisi — uzman raporu mevcut (ilk 6 ay sınırı manuel)',
            detaylar, sartlar, sut_kurali,
            uyari=('SUT 4.2.17.B: tanıdan itibaren İLK 6 AY ödenir; '
                   'sürenin üstündeki kullanım ödenmez — tanı tarihi kontrol edilmeli'))

    # ── 4.2.17.A Osteoporoz dalı ─────────────────────────────────────
    sut_kurali = 'SUT 4.2.17.A(7-8) — Kalsitonin osteoporoz'
    if rapor_kodu:
        sartlar.append(SartSonuc('Sağlık kurulu rapor kodu', SartDurumu.VAR,
                                 rapor_kodu, 'rap_kod'))
    else:
        sartlar.append(SartSonuc('Sağlık kurulu rapor kodu', SartDurumu.YOK,
                                 'Rap_kod boş', 'rap_kod'))

    sk_var, sk_neden = _osteoporoz_sk_var(birlesik, rapor_kodu)
    if sk_var:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.VAR, sk_neden,
                                 'rapor_metni/rap_kod'))
    else:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 sk_neden, 'rapor_metni/rap_kod'))

    # Yetkili branş (kalsitonin için tıbbi ekoloji yok)
    if (_osteo_yetkili_brans(doktor_brans, _KALSITONIN_YETKILI_BRANSLAR)
            or _osteo_uzman_brans_eslesti_mi(birlesik,
                                             _KALSITONIN_YETKILI_BRANSLAR)):
        sartlar.append(SartSonuc('Yetkili uzman branş', SartDurumu.VAR,
                                 'doktor branşı veya rapor metninde ibare',
                                 'doktor_uzmanligi/rapor_metni'))
    else:
        sartlar.append(SartSonuc('Yetkili uzman branş',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'İç hast/FTR/Romatoloji/Ortopedi/Kadın doğum/'
                                 'Endokrinoloji ibaresi yok',
                                 'doktor_uzmanligi/rapor_metni'))

    agrili_kirik = _agrili_vertebral_kirik(metin_lower, teshis_metin)
    if agrili_kirik:
        sartlar.append(SartSonuc('Ağrılı vertebral kırık (4.2.17.A(7))',
                                 SartDurumu.VAR, '', 'rapor_metni/teshis'))
    else:
        sartlar.append(SartSonuc('Ağrılı vertebral kırık (4.2.17.A(7))',
                                 SartDurumu.YOK,
                                 'Ağrılı vertebral kırık ibaresi/ICD yok',
                                 'rapor_metni/teshis'))

    intolerans = any(k in metin_lower for k in (
        'bifosfonat intoleran', 'bifosfonata intoleran', 'tolere edemiyor',
        'tolere edemeyen', 'yetersiz yanit', 'yetersiz yanıt',
    ))
    if intolerans:
        sartlar.append(SartSonuc('Bifosfonat intolerans/yetersiz yanıt',
                                 SartDurumu.VAR, '', 'rapor_metni'))
    else:
        sartlar.append(SartSonuc('Bifosfonat intolerans/yetersiz yanıt',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 'İbare metinde yok', 'rapor_metni'))

    ucuncu_basamak = any(k in metin_lower for k in (
        'üçüncü basamak', 'ucuncu basamak', '3. basamak', 'eğitim araştırma',
        'egitim arastirma', 'üniversite hastane', 'universite hastane',
    ))
    if ucuncu_basamak:
        sartlar.append(SartSonuc('Üçüncü basamak resmi sağlık kurumu',
                                 SartDurumu.VAR, '', 'rapor_metni'))
    else:
        sartlar.append(SartSonuc('Üçüncü basamak resmi sağlık kurumu',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 '"Üçüncü basamak/üniversite hastane" ibaresi yok',
                                 'rapor_metni'))

    if not rapor_kodu:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            'Kalsitonin RAPORSUZ — sağlık kurulu raporu zorunlu',
            detaylar, sartlar, sut_kurali,
            aranan_ibare='Sağlık kurulu raporu')
    if kombi_var:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Kalsitonin + ek osteoporoz ilacı ({kombi_ilac}) — kombi yasağı',
            detaylar, sartlar, sut_kurali)

    if agrili_kirik:
        # 4.2.17.A(7) dalı
        detaylar['alt_dal'] = 'KALSITONIN_AGRILI_4.2.17.A.7'
        if not sk_var:
            return _osteo_karar_topla(
                KontrolSonucu.KONTROL_EDILEMEDI,
                'Kalsitonin (ağrılı vertebral kırık) — sağlık kurulu raporu manuel doğrulanmalı',
                detaylar, sartlar, sut_kurali,
                uyari='Her ağrılı vertebral kırık için MAX 3 AYLIK doz')
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            'Kalsitonin — ağrılı vertebral kırık (4.2.17.A(7))',
            detaylar, sartlar, sut_kurali,
            uyari='SUT 4.2.17.A(7): her ağrılı vertebral kırık için MAX 3 AYLIK doz')
    else:
        # 4.2.17.A(8) dalı: ağrısız + intolerans + 3. basamak
        detaylar['alt_dal'] = 'KALSITONIN_AGRISIZ_4.2.17.A.8'
        if not (intolerans and ucuncu_basamak and sk_var):
            eksikler = []
            if not intolerans: eksikler.append('bifosfonat intolerans')
            if not ucuncu_basamak: eksikler.append('3. basamak resmi kurum')
            if not sk_var: eksikler.append('sağlık kurulu raporu ibaresi')
            return _osteo_karar_topla(
                KontrolSonucu.KONTROL_EDILEMEDI,
                ('Kalsitonin (ağrısız vertebral kırık yok) — eksik şartlar: '
                 + ', '.join(eksikler)),
                detaylar, sartlar, sut_kurali,
                uyari='SUT 4.2.17.A(8): ağrısız + bifosfonat intolerans + 3. basamak şart')
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            'Kalsitonin — ağrısız + bifosfonat intolerans + 3. basamak (4.2.17.A(8))',
            detaylar, sartlar, sut_kurali)


def kontrol_aktif_d_vitamini(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.17.A(9) — Aktif D vitaminleri (kalsitriol/alfakalsidol)
    osteoporoz tedavisinde ödenmez. EK-4/D istisnaları (renal osteodistrofi,
    hipoparatiroidi, vb.) hariç.
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik)
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    teshis_upper = teshis_metin.upper()

    sartlar: List[SartSonuc] = []
    detaylar = {'alt_kategori': 'AKTIF_D_VITAMINI',
                'sut_maddesi': '4.2.17.A(9)', 'rapor_kodu': rapor_kodu}
    sut_kurali = ('SUT 4.2.17.A(9) — Aktif D vitaminleri (kalsitriol/'
                  'alfakalsidol) osteoporozda ödenmez')

    # Osteoporoz endikasyonu var mı?
    osteo_endik = (
        any(k in metin_lower for k in ('osteoporoz', 'osteopeni',
                                        'kemik erimesi', 'kmy', 'dexa', 'dxa'))
        or any(k in teshis_upper for k in ('M80', 'M81', 'M82', 'M85'))
        or rapor_kodu in ('06.01', '06.02')
    )

    # EK-4/D istisnaları
    ek4d_istisna = any(k in metin_lower for k in (
        'renal osteodistrofi', 'kronik böbrek', 'kronik bobrek', 'ckd',
        'sekonder hiperparatiroid', 'hipoparatiroid', 'hipokalsemi',
        'rikets', 'osteomalazi', 'd vitamini eksikli',
    )) or any(k in teshis_upper for k in (
        'E20', 'E21.1', 'E21.2', 'E21.3', 'E55', 'E83.3',
        'N18', 'N18.5', 'N18.6',
    ))

    if osteo_endik:
        sartlar.append(SartSonuc('Osteoporoz endikasyonu',
                                 SartDurumu.VAR,
                                 'osteoporoz/M80-M85 ibaresi/06.01-02 rapor',
                                 'rapor_metni/teshis/rap_kod'))
    else:
        sartlar.append(SartSonuc('Osteoporoz endikasyonu', SartDurumu.YOK,
                                 'Osteoporoz ibare/ICD/rapor kodu yok',
                                 'rapor_metni/teshis'))

    if ek4d_istisna:
        sartlar.append(SartSonuc('EK-4/D istisna (renal osteodistrofi/'
                                 'hipoparatiroidi/hipokalsemi/rikets)',
                                 SartDurumu.VAR, '',
                                 'rapor_metni/teshis'))
    else:
        sartlar.append(SartSonuc('EK-4/D istisna', SartDurumu.YOK,
                                 'EK-4/D listesi endikasyonu bulunamadı',
                                 'rapor_metni/teshis'))

    if osteo_endik and not ek4d_istisna:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            'Aktif D vitamini (kalsitriol/alfakalsidol) osteoporozda ödenmez '
            '(SUT 4.2.17.A(9))',
            detaylar, sartlar, sut_kurali,
            aranan_ibare='renal osteodistrofi / hipoparatiroidi / EK-4/D')
    if ek4d_istisna:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            'Aktif D vitamini — EK-4/D istisnası (renal osteodistrofi vb.)',
            detaylar, sartlar, sut_kurali,
            uyari='Endikasyon raporu/branş ayrı kontrol edilmeli')
    return _osteo_karar_topla(
        KontrolSonucu.KONTROL_EDILEMEDI,
        'Aktif D vitamini — endikasyon (osteoporoz mu / EK-4/D mi) belirsiz',
        detaylar, sartlar, sut_kurali,
        uyari='Manuel doğrulama: osteoporoz endikasyonuysa ödenmez (4.2.17.A(9))')


def kontrol_osteoporoz_biyolojik(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.17.A(6)(b) - Osteoporoz biyolojik ilaçları (Denosumab/Prolia)
    + SUT 4.2.28.C destek + onkoloji destek (XGEVA)

    Şimdi detaylı dallar ile:
      (b)(1) Hormon ablasyonu prostat / aromataz inhibitör meme Ca + onkoloji SK
      (b)(2)(a) Postmenopozal kadın / erkek osteoporoz
      (b)(2)(b) Glukokortikoid + yüksek kırık riski
      Stronsiyum/Teriparatid/Romosozumab → bifosfonat intolerans + SK raporu
      XGEVA (denosumab 120 mg) → onkoloji (kemik metastazı), ayrı SUT
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    arama = ilac_adi + ' ' + etkin_madde

    metin = _tum_metinleri_birlesir(ilac_sonuc)
    teshis_metin = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
    birlesik = (metin or '') + ' ' + teshis_metin
    metin_lower = _tr_lower(birlesik)
    teshis_upper = teshis_metin.upper()

    sut_kurali = ('SUT 4.2.17.A(6)(b) — Denosumab/Prolia (sağlık kurulu raporu '
                  'zorunlu)')

    is_denosumab = ('DENOSUMAB' in arama or 'PROLIA' in arama or 'XGEVA' in arama)
    is_xgeva = 'XGEVA' in arama
    is_teriparatid = ('TERIPARATID' in arama or 'TERIPARATIDE' in arama or
                      'FORTEO' in arama or 'FORSTEO' in arama or 'MOVYMIA' in arama)
    is_romosozumab = 'ROMOSOZUMAB' in arama or 'EVENITY' in arama
    is_stronsiyum = ('STRONSIYUM' in arama or 'STRONTIUM' in arama or
                     'OSSEOR' in arama or 'PROTELOS' in arama)

    sartlar: List[SartSonuc] = []
    detaylar = {
        'alt_kategori': 'OSTEOPOROZ_BIYOLOJIK', 'sut_maddesi': '4.2.17.A(6b)',
        'rapor_kodu': rapor_kodu,
        'denosumab': is_denosumab, 'xgeva': is_xgeva,
        'teriparatid': is_teriparatid, 'romosozumab': is_romosozumab,
        'stronsiyum': is_stronsiyum,
    }

    # Kombinasyon
    kombi_var, kombi_ilac = _osteo_kombi_var(ilac_sonuc, 'OSTEOPOROZ_BIYOLOJIK')
    if kombi_var:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.YOK,
                                 f'Aynı reçetede: {kombi_ilac}',
                                 'recete_ilaclari'))
    else:
        sartlar.append(SartSonuc('Osteoporoz ilaç kombinasyon yasağı',
                                 SartDurumu.VAR,
                                 'Aynı reçetede başka osteoporoz ilacı yok',
                                 'recete_ilaclari'))

    # ── XGEVA = onkoloji (kemik metastazı / dev hücreli tümör) ────────
    if is_xgeva:
        sartlar.append(SartSonuc('XGEVA dalı (onkoloji)', SartDurumu.VAR,
                                 'denosumab 120 mg', 'ilac_adi'))
        if not rapor_kodu:
            return _osteo_karar_topla(
                KontrolSonucu.UYGUN_DEGIL,
                'XGEVA (denosumab 120 mg) RAPORSUZ — onkoloji uzman raporu ZORUNLU',
                {**detaylar, 'alt_dal': 'XGEVA_RAPORSUZ'},
                sartlar,
                'SUT 12.7.X — Onkoloji destek tedavisi (denosumab 120 mg)',
                uyari='XGEVA: kemik metastazı / dev hücreli kemik tümörü')
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            f'XGEVA — onkoloji rapor kodu {rapor_kodu} (kemik metastazı)',
            {**detaylar, 'alt_dal': 'XGEVA_ONKOLOJI'}, sartlar,
            'SUT 12.7.X — Onkoloji destek tedavisi (denosumab 120 mg)',
            uyari='Onkoloji rapor süresi ve dozaj kontrol (4 haftada bir 120 mg)')

    # ── PROLIA / Denosumab (osteoporoz) ──────────────────────────────
    if is_denosumab:
        return _kontrol_denosumab_osteoporoz(
            ilac_sonuc, rapor_kodu, metin_lower, teshis_upper,
            sartlar, detaylar, kombi_var, kombi_ilac)

    # ── Stronsiyum ranelat ─────────────────────────────────────────────
    if is_stronsiyum:
        sartlar.append(SartSonuc('Stronsiyum ranelat dalı', SartDurumu.VAR,
                                 '', 'ilac_adi'))
        if not rapor_kodu:
            return _osteo_karar_topla(
                KontrolSonucu.UYGUN_DEGIL,
                'Stronsiyum ranelat RAPORSUZ — sağlık kurulu raporu zorunlu',
                detaylar, sartlar, sut_kurali,
                uyari='KV risk nedeniyle kullanımı kısıtlı')
        rapor_bif = kontrol_bifosfonat(ilac_sonuc)
        sartlar.extend([SartSonuc(f'[Bifosfonat eşik] {s.ad}', s.durum,
                                  s.neden, s.kaynak)
                        for s in rapor_bif.sartlar
                        if s.ad != 'Osteoporoz ilaç kombinasyon yasağı'])
        return _osteo_karar_topla(
            sonuc=rapor_bif.sonuc,
            mesaj=f'Stronsiyum ranelat — {rapor_bif.mesaj}',
            detaylar={**detaylar, **(rapor_bif.detaylar or {})},
            sartlar=sartlar, sut_kurali=sut_kurali,
            uyari='Stronsiyum ranelat: KV risk — kardiyak öykü kontrol edilmeli')

    # ── Teriparatid / Romosozumab ─────────────────────────────────────
    if is_teriparatid or is_romosozumab:
        ad = 'Teriparatid (Forteo/Forsteo)' if is_teriparatid else 'Romosozumab (Evenity)'
        sartlar.append(SartSonuc(f'{ad} dalı', SartDurumu.VAR, '', 'ilac_adi'))
        if not rapor_kodu:
            return _osteo_karar_topla(
                KontrolSonucu.UYGUN_DEGIL,
                f'{ad} RAPORSUZ — sağlık kurulu raporu zorunlu',
                detaylar, sartlar, sut_kurali)
        sk_var, sk_neden = _osteoporoz_sk_var(birlesik, rapor_kodu)
        if sk_var:
            sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                     SartDurumu.VAR, sk_neden,
                                     'rapor_metni/rap_kod'))
        else:
            sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                     SartDurumu.KONTROL_EDILEMEDI,
                                     sk_neden, 'rapor_metni/rap_kod'))

        if is_romosozumab:
            kv_oykusu = any(k in metin_lower for k in (
                'miyokard infarkt', 'inme öyküsü', 'inme oykusu',
                'serebrovaskuler', 'serebrovasküler', 'akut koroner sendrom',
                'sva', 'i21', 'i63', 'i64',
            )) or any(k in teshis_upper for k in ('I21', 'I22', 'I63', 'I64'))
            if kv_oykusu:
                sartlar.append(SartSonuc(
                    'Romosozumab KV kontrendikasyon (MI/inme öyküsü)',
                    SartDurumu.YOK,
                    'KV olay öyküsü tespit edildi → KONTRENDİKE',
                    'rapor_metni/teshis'))
                return _osteo_karar_topla(
                    KontrolSonucu.UYGUN_DEGIL,
                    'Romosozumab KONTRENDİKE — MI/inme öyküsü mevcut',
                    detaylar, sartlar, sut_kurali)

        # ── SUT 4.2.17.A(6)(b) ön-koşul: bifosfonat intolerans/yetersiz yanıt
        # veya ciddi osteoporoz alternatifi (zorunlu şart) ────────────────
        bif_durum, bif_neden = _bifosfonat_onkosul_var_mi(metin_lower)
        sartlar.append(SartSonuc(
            'Bifosfonat intolerans/yetersiz yanıt veya ciddi osteoporoz',
            bif_durum, bif_neden, 'rapor_metni'))

        # ── SUT 4.1.4 — Endikasyon dışı kullanım onayı (varsa uygulanır) ─
        ed_sonuc = _endikasyon_disi_onay_var_mi(metin_lower)
        ed_durum = None
        if ed_sonuc is not None:
            ed_durum, ed_neden = ed_sonuc
            sartlar.append(SartSonuc(
                'Endikasyon dışı kullanım onayı (SUT 4.1.4)',
                ed_durum, ed_neden, 'rapor_metni'))

        rapor_bif = kontrol_bifosfonat(ilac_sonuc)
        sartlar.extend([SartSonuc(f'[Bifosfonat eşik] {s.ad}', s.durum,
                                  s.neden, s.kaynak)
                        for s in rapor_bif.sartlar
                        if s.ad != 'Osteoporoz ilaç kombinasyon yasağı'])

        # ── Sonuç ağırlıklandırması ──────────────────────────────────────
        # Yeni eklenen şartlar: bif_durum (zorunlu) + ed_durum (varsa)
        son_sonuc = rapor_bif.sonuc
        # Bif eşik UYGUN_DEGIL ise zaten UYGUN_DEGIL — değiştirme
        if son_sonuc != KontrolSonucu.UYGUN_DEGIL:
            # YOK varsa UYGUN_DEGIL
            yeni_yok = (bif_durum == SartDurumu.YOK or
                        ed_durum == SartDurumu.YOK)
            # KONTROL_EDILEMEDI varsa şüpheli
            yeni_supheli = (bif_durum == SartDurumu.KONTROL_EDILEMEDI or
                            ed_durum == SartDurumu.KONTROL_EDILEMEDI)
            if yeni_yok:
                son_sonuc = KontrolSonucu.UYGUN_DEGIL
            elif yeni_supheli:
                son_sonuc = KontrolSonucu.KONTROL_EDILEMEDI

        ek_uyari = ('Bifosfonat intolerans/yan etki/yetersiz yanıt veya ciddi '
                    'osteoporoz endikasyonu raporda lafzen aranır')
        if is_teriparatid:
            ek_uyari += ' | Teriparatid: maks 24 ay; T ≤ -2.5 + ileri yaş'
        if is_romosozumab:
            ek_uyari += ' | Romosozumab: 12 ay; KV olay öyküsünde KONTRENDİKE'
        if ed_sonuc is not None:
            ek_uyari += (' | Endikasyon dışı kullanım: SUT 4.1.4 — Bakanlık/'
                         'SGK/komisyon onayı zorunlu')
        return _osteo_karar_topla(
            sonuc=son_sonuc,
            mesaj=f'{ad} — {rapor_bif.mesaj}',
            detaylar={**detaylar, **(rapor_bif.detaylar or {})},
            sartlar=sartlar, sut_kurali=sut_kurali, uyari=ek_uyari)

    # Bilinmeyen biyolojik
    return _osteo_karar_topla(
        KontrolSonucu.KONTROL_EDILEMEDI,
        'Osteoporoz biyolojik — alt grup belirlenemedi',
        detaylar, sartlar, sut_kurali)


def _kontrol_denosumab_osteoporoz(ilac_sonuc, rapor_kodu, metin_lower,
                                   teshis_upper, sartlar, detaylar,
                                   kombi_var, kombi_ilac):
    """SUT 4.2.17.A(6)(b)(1) ve (6)(b)(2): Denosumab (PROLIA) osteoporoz dalları."""
    sut_kurali = ('SUT 4.2.17.A(6)(b) — Denosumab/Prolia '
                  '(sağlık kurulu raporu zorunlu)')
    sk_var, sk_neden = _osteoporoz_sk_var(metin_lower, rapor_kodu)

    if not rapor_kodu:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            'Denosumab/Prolia RAPORSUZ — sağlık kurulu raporu zorunlu',
            {**detaylar, 'alt_dal': 'DENOSUMAB_RAPORSUZ'},
            sartlar, sut_kurali)
    if kombi_var:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Denosumab + ek osteoporoz ilacı ({kombi_ilac}) — kombi yasağı',
            detaylar, sartlar, sut_kurali)

    if sk_var:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.VAR, sk_neden,
                                 'rapor_metni/rap_kod'))
    else:
        sartlar.append(SartSonuc('Sağlık kurulu raporu',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 sk_neden, 'rapor_metni/rap_kod'))

    # 4.2.17.A(6)(b)(1) — Hormon ablasyonu prostat / aromataz inhibitörü meme Ca
    prostat_ca = any(k in metin_lower for k in (
        'prostat kanser', 'prostat ca', 'hormon ablasyon',
        'androjen deprivasyon', 'lhrh agonist', 'gnrh agonist',
        'lupron', 'eligard', 'zoladex',
    )) or 'C61' in teshis_upper
    meme_ca_aromataz = (
        ('meme kanser' in metin_lower or 'meme ca' in metin_lower
         or 'C50' in teshis_upper)
        and any(k in metin_lower for k in (
            'aromataz inhibitör', 'aromataz inhibitor', 'anastrozol',
            'letrozol', 'eksemestan', 'arimidex', 'femara', 'aromasin',))
    )
    onkoloji_brans = ('onkoloji' in metin_lower or 'medikal onkolog' in metin_lower)

    if prostat_ca or meme_ca_aromataz:
        sartlar.append(SartSonuc('Onkoloji endikasyonu (4.2.17.A(6)(b)(1))',
                                 SartDurumu.VAR,
                                 ('hormon ablasyonu prostat Ca' if prostat_ca
                                  else 'aromataz inhibitör + meme Ca'),
                                 'rapor_metni/teshis'))
        if not onkoloji_brans:
            sartlar.append(SartSonuc('Tıbbi onkoloji uzmanı (sağlık kurulu)',
                                     SartDurumu.KONTROL_EDILEMEDI,
                                     'Onkoloji ibaresi rapor metninde bulunamadı',
                                     'rapor_metni'))
        else:
            sartlar.append(SartSonuc('Tıbbi onkoloji uzmanı (sağlık kurulu)',
                                     SartDurumu.VAR, '', 'rapor_metni'))
        if not sk_var:
            return _osteo_karar_topla(
                KontrolSonucu.KONTROL_EDILEMEDI,
                'Denosumab onkoloji endikasyonu — sağlık kurulu raporu manuel doğrulanmalı',
                {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.1'},
                sartlar, sut_kurali,
                uyari='SUT 4.2.17.A(6)(b)(1): tıbbi onkoloji uzmanlı sağlık kurulu raporu')
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN,
            ('Denosumab — hormon ablasyonu prostat / aromataz inh. meme Ca '
             'osteoporozu (4.2.17.A(6)(b)(1))'),
            {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.1'},
            sartlar, sut_kurali)

    # 4.2.17.A(6)(b)(2): Bifosfonat intolerans VEYA renal yetmezlik
    intolerans = any(k in metin_lower for k in (
        'bifosfonat intoleran', 'bifosfonata intoleran', 'tolere edemiyor',
        'tolere edemeyen', 'yetersiz yanit', 'yetersiz yanıt',
    ))
    renal_yetmezlik = any(k in metin_lower for k in (
        'renal yetmezlik', 'kronik böbrek', 'kronik bobrek', 'ckd',
        'son donem bobrek', 'son dönem böbrek', 'diyaliz',
    )) or any(k in teshis_upper for k in ('N18', 'N19'))

    if intolerans:
        sartlar.append(SartSonuc('Bifosfonat intolerans/yetersiz yanıt',
                                 SartDurumu.VAR, '', 'rapor_metni'))
    elif renal_yetmezlik:
        sartlar.append(SartSonuc('Renal yetmezlik (bifosfonat kullanılamaz)',
                                 SartDurumu.VAR, '', 'rapor_metni/teshis'))
    else:
        sartlar.append(SartSonuc(
            'Bifosfonat intolerans/yetersiz yanıt VEYA renal yetmezlik',
            SartDurumu.KONTROL_EDILEMEDI,
            'İbare metinde yok', 'rapor_metni'))

    # (a) Postmenopozal kadın / erkek osteoporoz
    pm_osteo = any(k in metin_lower for k in (
        'postmenopozal', 'post menopozal', 'menopoz sonras',
    ))
    erkek_osteo = any(k in metin_lower for k in (
        'erkek osteoporoz', 'erkek hasta', 'male osteoporos',
    ))
    # (b) Glukokortikoid + yüksek kırık riski
    glukokortikoid_kirik = (
        _kortikosteroid_kelime_var(metin_lower)
        and any(k in metin_lower for k in (
            'yüksek kırık', 'yuksek kirik', 'osteoporotik kırık',
            'osteoporotik kirik', 'patolojik kırık', 'patolojik kirik',
        ))
    )

    sub_endik = pm_osteo or erkek_osteo or glukokortikoid_kirik
    if sub_endik:
        if pm_osteo:
            etiket = 'postmenopozal osteoporoz'
        elif erkek_osteo:
            etiket = 'erkek osteoporoz'
        else:
            etiket = 'glukokortikoid + yüksek kırık'
        sartlar.append(SartSonuc('4.2.17.A(6)(b)(2) alt endikasyon',
                                 SartDurumu.VAR, etiket,
                                 'rapor_metni'))
    else:
        sartlar.append(SartSonuc('4.2.17.A(6)(b)(2) alt endikasyon',
                                 SartDurumu.KONTROL_EDILEMEDI,
                                 ('Postmenopozal/erkek/glukokortikoid+kırık '
                                  'ibaresi yok'),
                                 'rapor_metni'))

    # Bifosfonat eşik kuralı — info
    rapor_bif = kontrol_bifosfonat(ilac_sonuc)
    sartlar.extend([SartSonuc(f'[Bifosfonat eşik] {s.ad}', s.durum,
                              s.neden, s.kaynak)
                    for s in rapor_bif.sartlar
                    if s.ad != 'Osteoporoz ilaç kombinasyon yasağı'])

    eksik_sk = '' if sk_var else ' | sağlık kurulu raporu ibaresi yok'

    if not (intolerans or renal_yetmezlik):
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            ('Denosumab — bifosfonat intolerans/yetersiz yanıt VEYA renal '
             'yetmezlik şartı bulunamadı (manuel doğrulama)'),
            {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.2'},
            sartlar, sut_kurali,
            uyari='SUT 4.2.17.A(6)(b)(2) ön şart' + eksik_sk)
    if not sub_endik:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            ('Denosumab — alt endikasyon (postmenopozal/erkek/glukokortikoid'
             '+kırık) ibaresi rapor metninde bulunamadı'),
            {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.2'},
            sartlar, sut_kurali, uyari='SUT 4.2.17.A(6)(b)(2)' + eksik_sk)
    if rapor_bif.sonuc == KontrolSonucu.UYGUN_DEGIL:
        return _osteo_karar_topla(
            KontrolSonucu.UYGUN_DEGIL,
            f'Denosumab — bifosfonat eşik sağlanmıyor: {rapor_bif.mesaj}',
            {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.2'},
            sartlar, sut_kurali)
    if rapor_bif.sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        return _osteo_karar_topla(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f'Denosumab — bifosfonat eşik şüpheli: {rapor_bif.mesaj}',
            {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.2'},
            sartlar, sut_kurali, uyari=eksik_sk.lstrip(' |'))
    return _osteo_karar_topla(
        KontrolSonucu.UYGUN,
        ('Denosumab — bifosfonat intolerans/renal yetmezlik + alt endikasyon '
         '+ T-skoru eşiği sağlandı (4.2.17.A(6)(b)(2))'),
        {**detaylar, 'alt_dal': 'DENOSUMAB_4.2.17.A.6.b.2'},
        sartlar, sut_kurali,
        uyari=eksik_sk.lstrip(' |') if eksik_sk else None)


def kontrol_ivabradin(ilac_sonuc: Dict) -> KontrolRaporu:
    """İvabradin (4.2.15.C) / Eplerenon
    İvabradin: NYHA II-IV + sinüs ritmi VEYA beta blokör intoleransı VEYA EF≤%45
    """
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()

    if not metin:
        # Rapor metni boş — İvabradin SUT 4.2.15.C'ye göre kardiyoloji
        # uzman hekim raporu zorunlu.
        if not rapor_kodu:
            return KontrolRaporu(
                KontrolSonucu.UYGUN_DEGIL,
                "Raporsuz İvabradin/Eplerenon — uzman hekim raporu zorunlu",
                detaylar={'rapor_kodu': rapor_kodu})
        return KontrolRaporu(
            KontrolSonucu.KONTROL_EDILEMEDI,
            f"Rapor kodu var ({rapor_kodu}) ama metni okunamadı — "
            "manuel doğrulama gerekli",
            detaylar={'rapor_kodu': rapor_kodu})

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
        doktor_bva = _tr_lower(ilac_sonuc.get('doktor_uzmanligi'))
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
        doktor_val = _tr_lower(ilac_sonuc.get('doktor_uzmanligi'))
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
    doktor = _tr_lower(ilac_sonuc.get('doktor_uzmanligi'))
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


def kontrol_antiepileptik_4_2_25(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.25 — Antiepileptik İlaçların Kullanım İlkeleri

    Alt gruplar (etken madde bazlı):
      A) YENI_NESIL  : Lamotrijin, Topiramat, Vigabatrin, Levetirasetam
                       → Nöroloji/Beyin Cerrahisi uzman raporu
                       → Raporsuz: Nöroloji/Beyin Cerrahisi uzmanı yazabilir
      B) ZONISAMIT   : Zonisamit
                       → Nöroloji uzman hekim + 1 YIL süreli rapor
      C) PREGABALIN  : Pregabalin (mono veya sabit doz kombinasyonları)
                       → 2./3. basamak SHS + en az bir nöroloji uzmanının
                         yer aldığı 1 yıl süreli SAĞLIK KURULU raporu
                       → Reçete: Nöroloji uzman hekimi
                       → Yaygın anksiyete bozukluğu (YAB) endikasyonunda
                         BEDEL ÖDENMEZ → UYGUN_DEGIL
                       → Gabapentin ile KOMBİNE KULLANILAMAZ → UYGUN_DEGIL
      D) LAKOZAMID   : Lakozamid
                       → 16 yaş ve üzeri + parsiyel başlangıçlı epilepsi
                       → En az 2 antiepileptiğin 6 ay tek/kombine kullanımı
                         sonrası tedaviye yanıt alınamayan hastalarda
                         ek tedavi VEYA monoterapi olarak
                       → Nöroloji uzman raporu (durumların belirtildiği)
                       → Tüm uzman hekimlerce reçete edilebilir
      E) GABAPENTIN  : Gabapentin
                       → 2./3. basamak SHS + en az bir nöroloji uzmanının
                         yer aldığı 1 yıl süreli SAĞLIK KURULU raporu
                       → Reçete: Nöroloji uzman hekimi
                       → Pregabalin ile KOMBİNE KULLANILAMAZ → UYGUN_DEGIL

    Karar tablosu (ortak):
      RAPORLU + uygun branş + alt grup şartı → UYGUN
      RAPORLU + alt grup şartı eksik (kombi/yaş/2-aep/SK)→ ŞÜPHELİ
      RAPORSUZ + nöroloji uzmanı yazımı (yeni nesil) → UYGUN (uyarı: rapor süresi)
      RAPORSUZ + diğer durumlar → UYGUN_DEGIL veya ŞÜPHELİ

    Not: Lamotrijin BİPOLAR endikasyonunda kontrol_psikiyatri'ye delege edilir
    (psikiyatri butonu kapsar). Burada sadece EPILEPSI endikasyonu işlenir.
    Sodyum valproat da aynı şekilde — bipolar → psikiyatri, epilepsi → bu fn.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    diger_etkenler = ilac_sonuc.get('diger_etken_maddeler', []) or []
    diger_ilaclar = ilac_sonuc.get('diger_ilac_adlari', []) or []

    # Yaş parse — string/int gelebilir
    yas_raw = ilac_sonuc.get('yas')
    try:
        yas = int(str(yas_raw).strip()) if str(yas_raw).strip() else None
    except (ValueError, TypeError):
        yas = None

    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''
    sut_kurali = 'SUT 4.2.25 — Antiepileptik ilaçların kullanım ilkeleri'

    # ── Alt grup tespiti ──
    is_lamotrijin = ('LAMOTRIJIN' in etkin_madde or 'LAMOTRIGIN' in etkin_madde
                     or 'LAMICTAL' in ilac_adi or 'LAMOTRIX' in ilac_adi)
    is_topiramat = ('TOPIRAMAT' in etkin_madde or 'TOPAMAX' in ilac_adi
                    or 'TOPAMAC' in ilac_adi)
    is_vigabatrin = 'VIGABATRIN' in etkin_madde or 'SABRIL' in ilac_adi
    is_levetirasetam = ('LEVETIRASETAM' in etkin_madde or 'LEVATIRASETAM' in etkin_madde
                        or 'KEPPRA' in ilac_adi or 'LEVEBON' in ilac_adi
                        or 'EPITERRA' in ilac_adi)
    is_zonisamit = ('ZONISAMID' in etkin_madde or 'ZONISAMIT' in etkin_madde
                    or 'ZONEGRAN' in ilac_adi)
    is_pregabalin = ('PREGABALIN' in etkin_madde or 'LYRICA' in ilac_adi
                     or 'PREGABA' in ilac_adi)
    is_lakozamid = ('LAKOSAMID' in etkin_madde or 'LAKOZAMID' in etkin_madde
                    or 'LACOSAMID' in etkin_madde or 'VIMPAT' in ilac_adi)
    is_gabapentin = ('GABAPENTIN' in etkin_madde or 'NEURONTIN' in ilac_adi
                     or 'GABANTIN' in ilac_adi)
    is_valproat = ('VALPROAT' in etkin_madde or 'VALPROIK' in etkin_madde
                   or 'DEPAKIN' in ilac_adi or 'CONVULEX' in ilac_adi)

    # Bipolar endikasyonu — Lamotrijin/Valproat psikiyatri akışına aittir
    bipolar = ('F31' in teshis_metin or _turkce_ara(tum_metin, 'bipolar')
               or _turkce_ara(tum_metin, 'manik'))

    # YAB (yaygın anksiyete bozukluğu) — pregabalin için ödenmez
    yab = ('F41' in teshis_metin
           or _turkce_ara(tum_metin, 'yaygin anksiyete')
           or _turkce_ara(tum_metin, 'yaygın anksiyete')
           or _turkce_ara(tum_metin, 'generalize anksiyete'))

    # Alt grup adı
    alt_grup = 'BILINMIYOR'
    if is_lamotrijin and bipolar:
        alt_grup = 'LAMOTRIJIN_BIPOLAR'
    elif is_lamotrijin:
        alt_grup = 'LAMOTRIJIN_EPILEPSI'
    elif is_topiramat:
        alt_grup = 'TOPIRAMAT'
    elif is_vigabatrin:
        alt_grup = 'VIGABATRIN'
    elif is_levetirasetam:
        alt_grup = 'LEVETIRASETAM'
    elif is_zonisamit:
        alt_grup = 'ZONISAMIT'
    elif is_pregabalin:
        alt_grup = 'PREGABALIN'
    elif is_lakozamid:
        alt_grup = 'LAKOZAMID'
    elif is_gabapentin:
        alt_grup = 'GABAPENTIN'
    elif is_valproat and not bipolar:
        alt_grup = 'VALPROAT_EPILEPSI'

    detaylar = {
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin_madde,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
        'alt_grup': alt_grup,
        'yas': yas,
        'bipolar': bipolar,
        'yab': yab,
    }

    # ── Bipolar endikasyon → psikiyatri butonuna ait, burada UYGUN değil ATLA ──
    if bipolar and (is_lamotrijin or is_valproat):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj=(f'{alt_grup} bipolar endikasyonunda — '
                   'psikiyatri butonu (SUT 4.2.2) kapsamında kontrol edilir'),
            detaylar=detaylar,
            sut_kurali='SUT 4.2.2 (Bipolar) — Psikiyatri butonuna delege',
        )

    # ── Doktor branş tespiti ──
    doktor_noroloji = ('NORO' in doktor_brans or 'NÖRO' in doktor_brans)
    doktor_beyin_cer = ('BEYIN CER' in doktor_brans or 'BEYİN CER' in doktor_brans
                        or 'NÖROŞIRURJI' in doktor_brans
                        or 'NOROSIRURJI' in doktor_brans)

    # ── Rapor branş tespiti (rapor kodu ön ek) ──
    # 10.* = Nöroloji, 12.* = Beyin Cerrahisi (Medula kod tablosuna göre yaklaşık)
    rapor_noroloji = rapor_kodu.startswith('10.') if rapor_kodu else False
    rapor_beyin_cer = rapor_kodu.startswith('12.') if rapor_kodu else False
    rapor_uygun_brans = rapor_noroloji or rapor_beyin_cer

    # ── Sağlık kurulu raporu ibaresi (Pregabalin/Gabapentin için zorunlu) ──
    saglik_kurulu = (_turkce_ara(tum_metin, 'saglik kurulu')
                     or _turkce_ara(tum_metin, 'sağlık kurulu')
                     or _turkce_ara(tum_metin, 'heyet'))

    # ── Pregabalin + Gabapentin kombine yasağı ──
    diger_metin = ' '.join([str(x).upper() for x in diger_etkenler] +
                            [str(x).upper() for x in diger_ilaclar])
    pregab_var = is_pregabalin or 'PREGABALIN' in diger_metin or 'LYRICA' in diger_metin
    gabap_var = is_gabapentin or 'GABAPENTIN' in diger_metin or 'NEURONTIN' in diger_metin
    kombi_yasak = pregab_var and gabap_var

    if kombi_yasak and (is_pregabalin or is_gabapentin):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=('Pregabalin + Gabapentin KOMBİNE KULLANIM — '
                   'SUT 4.2.25(3,5): kombine kullanılamaz'),
            detaylar={**detaylar, 'kombi_yasak': True},
            uyari='SUT 4.2.25: Pregabalin ve gabapentin kombine kullanılamaz',
            sut_kurali=sut_kurali,
            aranan_ibare='Aynı reçete/hasta — pregabalin VE gabapentin birlikte yok',
        )

    # ── A) Pregabalin ──
    if is_pregabalin:
        if yab:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=('Pregabalin YAYGIN ANKSİYETE BOZUKLUĞU endikasyonunda — '
                       'SUT 4.2.25(3): bedeli Kurumca KARŞILANMAZ'),
                detaylar=detaylar,
                uyari='Pregabalin YAB endikasyonunda ödenmez',
                sut_kurali=sut_kurali,
                aranan_ibare='Teşhis: F41 / yaygın anksiyete bozukluğu YOK',
            )
        if not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Pregabalin RAPORSUZ — SUT 4.2.25(3): sağlık kurulu raporu ZORUNLU',
                detaylar=detaylar,
                uyari='2./3. basamak SHS + en az 1 nöroloji uzmanı + 1 yıl SK raporu',
                sut_kurali=sut_kurali,
                aranan_ibare='Sağlık kurulu raporu (nöroloji uzmanı dahil)',
            )
        # Raporlu pregabalin
        if not saglik_kurulu and not rapor_noroloji:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Pregabalin raporlu (rap.kod {rapor_kodu}) — '
                       'sağlık kurulu raporu / nöroloji branşı tespit edilemedi'),
                detaylar=detaylar,
                uyari='SK raporu ve nöroloji uzmanının yer alması manuel doğrulanmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='Sağlık kurulu + nöroloji uzmanı (1 yıl)',
            )
        if not doktor_noroloji:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Pregabalin raporlu — yazan branş "{doktor_brans or "?"}", '
                       'SUT: nöroloji uzmanı yazmalı'),
                detaylar=detaylar,
                uyari='Reçeteyi nöroloji uzmanı yazmalı (SK raporu olsa bile)',
                sut_kurali=sut_kurali,
                aranan_ibare='Reçeteyi yazan: nöroloji uzmanı',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Pregabalin — nöroloji uzmanı + SK raporu (rap.kod {rapor_kodu})'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Nöroloji uzmanı + 1 yıl SK raporu',
            bulunan_metin=f'Branş: {doktor_brans} | Rapor: {rapor_kodu}',
        )

    # ── B) Gabapentin ──
    if is_gabapentin:
        if not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Gabapentin RAPORSUZ — SUT 4.2.25(5): sağlık kurulu raporu ZORUNLU',
                detaylar=detaylar,
                uyari='2./3. basamak SHS + en az 1 nöroloji uzmanı + 1 yıl SK raporu',
                sut_kurali=sut_kurali,
                aranan_ibare='Sağlık kurulu raporu (nöroloji uzmanı dahil)',
            )
        if not saglik_kurulu and not rapor_noroloji:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Gabapentin raporlu (rap.kod {rapor_kodu}) — '
                       'sağlık kurulu raporu / nöroloji branşı tespit edilemedi'),
                detaylar=detaylar,
                uyari='SK raporu ve nöroloji uzmanı manuel doğrulanmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='Sağlık kurulu + nöroloji uzmanı (1 yıl)',
            )
        if not doktor_noroloji:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Gabapentin raporlu — yazan branş "{doktor_brans or "?"}", '
                       'SUT: nöroloji uzmanı yazmalı'),
                detaylar=detaylar,
                uyari='Reçeteyi nöroloji uzmanı yazmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='Reçeteyi yazan: nöroloji uzmanı',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Gabapentin — nöroloji uzmanı + SK raporu (rap.kod {rapor_kodu})'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Nöroloji uzmanı + 1 yıl SK raporu',
            bulunan_metin=f'Branş: {doktor_brans} | Rapor: {rapor_kodu}',
        )

    # ── C) Lakozamid ──
    if is_lakozamid:
        if yas is not None and yas < 16:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=(f'Lakozamid {yas} yaş — SUT 4.2.25(4): 16 YAŞ VE ÜZERİ şartı'),
                detaylar=detaylar,
                uyari='Lakozamid 16 yaş altı endikasyon dışı',
                sut_kurali=sut_kurali,
                aranan_ibare='Yaş ≥ 16',
            )
        if not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Lakozamid RAPORSUZ — SUT 4.2.25(4): nöroloji uzman raporu ZORUNLU',
                detaylar=detaylar,
                uyari='Rapor: 2 antiepileptik 6 ay yetersiz + ek tedavi/monoterapi belirtilmeli',
                sut_kurali=sut_kurali,
                aranan_ibare='Nöroloji uzman raporu (parsiyel epilepsi + 2 AEP 6 ay yetersiz)',
            )
        # Raporlu — 2 antiepileptik 6 ay öyküsü ibaresi raporda olmalı
        sart_metni = (_turkce_ara(tum_metin, 'iki antiepileptik')
                      or _turkce_ara(tum_metin, '2 antiepileptik')
                      or _turkce_ara(tum_metin, 'tedaviye yanit')
                      or _turkce_ara(tum_metin, 'tedaviye yanıt')
                      or _turkce_ara(tum_metin, '6 ay'))
        parsiyel_metni = (_turkce_ara(tum_metin, 'parsiyel')
                          or _turkce_ara(tum_metin, 'fokal'))
        if not rapor_noroloji and not _turkce_ara(tum_metin, 'noroloji') \
                and not _turkce_ara(tum_metin, 'nöroloji'):
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Lakozamid raporlu (rap.kod {rapor_kodu}) — '
                       'nöroloji uzman raporu ibaresi tespit edilemedi'),
                detaylar=detaylar,
                uyari='Nöroloji uzman raporu olmalı (2 AEP 6 ay yetersiz şartıyla)',
                sut_kurali=sut_kurali,
                aranan_ibare='Nöroloji uzmanı + parsiyel + 2 AEP 6 ay yetersiz',
            )
        if not (sart_metni and parsiyel_metni):
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Lakozamid raporlu (rap.kod {rapor_kodu}) — '
                       'parsiyel epilepsi + 2 AEP 6 ay yetersizlik ibaresi eksik'),
                detaylar=detaylar,
                uyari='Raporda "parsiyel başlangıçlı" + "2 AEP 6 ay yetersiz" ibaresi şart',
                sut_kurali=sut_kurali,
                aranan_ibare='parsiyel/fokal + 2 antiepileptik 6 ay tedaviye yanıtsız',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Lakozamid — nöroloji raporu + parsiyel + 2 AEP 6 ay yetersiz '
                   f'(rap.kod {rapor_kodu})'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Nöroloji raporu + parsiyel + 2 AEP 6 ay yetersizlik',
            bulunan_metin=f'Rapor: {rapor_kodu} | Yaş: {yas if yas is not None else "?"}',
        )

    # ── D) Zonisamit ──
    if is_zonisamit:
        if not rapor_kodu:
            if doktor_noroloji:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=('Zonisamit raporsuz — nöroloji uzmanı yazmış '
                           '(SUT: 1 yıl rapor süresi içinde manuel kontrol)'),
                    detaylar=detaylar,
                    uyari='SUT 4.2.25(2): 1 yıl süreli rapor şart — manuel kontrol',
                    sut_kurali=sut_kurali,
                    aranan_ibare='Nöroloji uzmanı + 1 yıl rapor',
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Zonisamit RAPORSUZ — SUT 4.2.25(2): nöroloji uzman raporu (1 yıl) ZORUNLU',
                detaylar=detaylar,
                uyari='Nöroloji uzmanı + 1 yıl rapor',
                sut_kurali=sut_kurali,
                aranan_ibare='Nöroloji uzman raporu (1 yıl süreli)',
            )
        if not (rapor_noroloji or doktor_noroloji or
                _turkce_ara(tum_metin, 'noroloji') or
                _turkce_ara(tum_metin, 'nöroloji')):
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Zonisamit raporlu (rap.kod {rapor_kodu}) — '
                       'nöroloji uzman raporu ibaresi tespit edilemedi'),
                detaylar=detaylar,
                uyari='SUT: Nöroloji uzman hekim raporu (1 yıl) gerekli',
                sut_kurali=sut_kurali,
                aranan_ibare='Nöroloji uzmanı + 1 yıl rapor',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Zonisamit — nöroloji raporu (rap.kod {rapor_kodu})',
            detaylar=detaylar,
            uyari='Rapor süresi 1 yıl — geçerlilik manuel kontrol edilmeli',
            sut_kurali=sut_kurali,
            aranan_ibare='Nöroloji uzmanı + 1 yıl rapor',
            bulunan_metin=f'Rapor: {rapor_kodu} | Branş: {doktor_brans}',
        )

    # ── E) Yeni nesil (Lamotrijin epilepsi / Topiramat / Vigabatrin / Levetirasetam) ──
    if is_lamotrijin or is_topiramat or is_vigabatrin or is_levetirasetam or is_valproat:
        # Raporlu
        if rapor_kodu:
            if rapor_uygun_brans or _turkce_ara(tum_metin, 'noroloji') or \
               _turkce_ara(tum_metin, 'nöroloji') or \
               _turkce_ara(tum_metin, 'beyin cerrahisi') or \
               _turkce_ara(tum_metin, 'norosirurji') or \
               _turkce_ara(tum_metin, 'nöroşirurji'):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=(f'{alt_grup} — nöroloji/beyin cerrahisi raporu '
                           f'(rap.kod {rapor_kodu})'),
                    detaylar=detaylar,
                    sut_kurali=sut_kurali,
                    aranan_ibare='Nöroloji veya beyin cerrahisi uzman raporu',
                    bulunan_metin=f'Rapor: {rapor_kodu} | Branş: {doktor_brans}',
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'{alt_grup} raporlu (rap.kod {rapor_kodu}) — '
                       'nöroloji/beyin cerrahisi branşı tespit edilemedi'),
                detaylar=detaylar,
                uyari='SUT 4.2.25(1): Nöroloji veya beyin cerrahisi uzman raporu',
                sut_kurali=sut_kurali,
                aranan_ibare='Nöroloji / beyin cerrahisi uzmanı',
            )
        # Raporsuz — uzman yazımı yeterli (raporsuz da kabul)
        if doktor_noroloji or doktor_beyin_cer:
            brans_adi = 'nöroloji' if doktor_noroloji else 'beyin cerrahisi'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'{alt_grup} raporsuz — {brans_adi} uzmanı yazmış '
                       '(SUT 4.2.25(1): uzman tarafından raporsuz da yazılabilir)'),
                detaylar=detaylar,
                uyari='Devam reçetelerinde rapor önerilir',
                sut_kurali=sut_kurali,
                aranan_ibare=f'Doktor branşı: {brans_adi}',
                bulunan_metin=f'Branş: {doktor_brans}',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'{alt_grup} RAPORSUZ + branş "{doktor_brans or "?"}" — '
                   'SUT 4.2.25(1): nöroloji/beyin cerrahisi uzmanı veya raporu ZORUNLU'),
            detaylar=detaylar,
            uyari='Nöroloji veya beyin cerrahisi uzmanı yazmalı veya raporu olmalı',
            sut_kurali=sut_kurali,
            aranan_ibare='Nöroloji/beyin cerrahisi uzmanı veya uzman raporu',
        )

    # ── Bilinmeyen antiepileptik — minimal kontrol ──
    if not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=(f'Antiepileptik ({etkin_madde or ilac_adi[:24]}) — '
                   'SUT 4.2.25 alt grup belirlenemedi, raporsuz'),
            detaylar=detaylar,
            uyari='Etken madde tanınmadı — manuel kontrol önerilir',
            sut_kurali=sut_kurali,
        )
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=(f'Antiepileptik raporlu (rap.kod {rapor_kodu}) — '
               'alt grup belirlenemedi, manuel kontrol önerilir'),
        detaylar=detaylar,
        uyari='Etken madde tanınmadı — alt grup şartları manuel kontrol edilmeli',
        sut_kurali=sut_kurali,
    )


def kontrol_noropatik_4_2_35(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.35 — Nöropatik ağrı (A) ve fibromiyalji (B) tedavisi.

    Alt gruplar (etken madde + ticari isim):
      A) PREGABALIN  : LYRICA, GABRICA, PREGALIN, PREGABEX
      B) GABAPENTIN  : NEURONTIN, NERUDA, GABATEVA, GABALEPT, GABANTIN, GABAGAMMA
      C) DULOKSETIN  : CYMBALTA, DUXET, DULOXIN, DULOX
      D) ALFA_LIPOIK : tioktik / α-lipoik asit (THIOCTACID, NOREXIA)
      E) KAPSAISIN   : krem (CAPSIN, ZOSTRIX)

    Endikasyon ayrımı (rap_ack + teshisler birleşik metin):
      - FIBROMIYALJI    : "fibromiyalji" / "M79.7"     → 4.2.35.B
      - PHN             : "postherpetik" / "phn" / "zona sonrası"
      - DIYABETIK_NORO  : "diyabetik nöropati" / "polinöropati" / "E11.4"
      - NOROPATIK       : "nöropatik" / "nöropati"
      - DEPRESYON       : (sadece Duloksetin için) "depresyon"/"F32"/"F33"
                          → kontrol_psikiyatri'ye delege (ATLANDI)
      - EPILEPSI        : (Pregabalin/Gabapentin) "G40"/"epilepsi"/"konvulsiy"
                          → kontrol_antiepileptik_4_2_25'e delege (ATLANDI)

    Kombi yasağı: Pregabalin + Gabapentin AYNI REÇETE → UYGUN_DEGIL
                  (cross-reçete tarama YAPILMAZ — sadece aynı reçete içi)

    Branş listeleri (4.2.35 metnine göre):
      Pregabalin/Gabapentin: SK raporu (en az 1 nöroloji uzmanı dahil) — 4.2.25
                             ile aynı şart, fakat 4.2.35'te endikasyon nöropatik/
                             fibromiyalji olur
      Duloksetin (4.2.35.A) : nöroloji / algoloji / FTR / psikiyatri / endokrin
                              / dahiliye
      Duloksetin (4.2.35.B) : romatoloji / FTR / nöroloji / algoloji / psikiyatri
      Alfa lipoik           : endokrin / nöroloji / dahiliye / FTR
      Kapsaisin             : nöroloji / algoloji / dermatoloji / FTR

    Rapor süresi: en fazla 6 ay fibromiyalji için, 12 ay nöropatik için
                  (regex `(\\d+)\\s*ay\\s*sür`)

    Karar tablosu:
      RAPORLU + uygun branş + endikasyon + ≤süre         → UYGUN
      RAPORLU + endikasyon eksik                          → UYGUN_DEGIL
      RAPORLU + branş eksik                               → KONTROL_EDILEMEDI
      RAPORLU + süre aşımı                                → UYGUN_DEGIL
      RAPORSUZ                                            → UYGUN_DEGIL
      EPILEPSI/DEPRESYON → ATLANDI (başka butona delege)
      Pregabalin+Gabapentin aynı reçete → UYGUN_DEGIL

    Branş tespit edilemezse: "Manuel doğrulanmalı" uyarısı (KONTROL_EDILEMEDI).
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    diger_etkenler = ilac_sonuc.get('diger_etken_maddeler', []) or []
    diger_ilaclar = ilac_sonuc.get('diger_ilac_adlari', []) or []

    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''
    sut_kurali = 'SUT 4.2.35 — Nöropatik ağrı (A) / Fibromiyalji (B)'

    # ── Alt grup tespiti ──
    is_pregabalin = ('PREGABALIN' in etkin_madde
                     or any(t in ilac_adi for t in
                            ('LYRICA', 'GABRICA', 'PREGALIN', 'PREGABEX')))
    is_gabapentin = ('GABAPENTIN' in etkin_madde
                     or any(t in ilac_adi for t in
                            ('NEURONTIN', 'NERUDA', 'GABATEVA', 'GABALEPT',
                             'GABANTIN', 'GABAGAMMA')))
    is_duloksetin = ('DULOKSETIN' in etkin_madde or 'DULOXETINE' in etkin_madde
                     or any(t in ilac_adi for t in
                            ('CYMBALTA', 'DUXET', 'DULOXIN', 'DULOX')))
    is_alfa_lipoik = ('TIOKTIK' in etkin_madde or 'TİOKTİK' in etkin_madde
                      or 'ALFA LIPOIK' in etkin_madde
                      or 'ALFA-LIPOIK' in etkin_madde
                      or 'ALPHA LIPOIC' in etkin_madde
                      or any(t in ilac_adi for t in
                             ('THIOCTACID', 'NOREXIA', 'LIPOIK', 'TIOXIDAL')))
    is_kapsaisin = ('KAPSAISIN' in etkin_madde or 'KAPSAİSİN' in etkin_madde
                    or 'CAPSAICIN' in etkin_madde
                    or any(t in ilac_adi for t in ('CAPSIN', 'ZOSTRIX')))

    alt_grup = 'BILINMIYOR'
    if is_pregabalin:
        alt_grup = 'PREGABALIN'
    elif is_gabapentin:
        alt_grup = 'GABAPENTIN'
    elif is_duloksetin:
        alt_grup = 'DULOKSETIN'
    elif is_alfa_lipoik:
        alt_grup = 'ALFA_LIPOIK'
    elif is_kapsaisin:
        alt_grup = 'KAPSAISIN'

    # Hiçbir alt gruba uymuyorsa kapsam dışı
    if alt_grup == 'BILINMIYOR':
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='İlaç SUT 4.2.35 (nöropatik/fibromiyalji) kapsamında değil',
            detaylar={'ilac_adi': ilac_adi, 'etkin_madde': etkin_madde},
            sut_kurali=sut_kurali,
        )

    # ── Endikasyon tespiti (metin + teşhis) ──
    birlesik = (tum_metin + ' ' + teshis_metin).replace('İ', 'i').replace(
        'I', 'ı').lower()

    is_fibromiyalji = ('fibromiyalji' in birlesik or 'fibromyalji' in birlesik
                       or 'm79.7' in birlesik or 'm797' in birlesik)
    is_phn = ('postherpetik' in birlesik or 'post-herpetik' in birlesik
              or 'phn' in birlesik or 'zona sonrası' in birlesik
              or 'zona sonrasi' in birlesik or 'b02.2' in birlesik
              or 'g53.0' in birlesik)
    is_diyabetik_noro = (
        'diyabetik nöropati' in birlesik or 'diyabetik noropati' in birlesik
        or 'diabetik nöropati' in birlesik or 'diabetik noropati' in birlesik
        or 'polinöropati' in birlesik or 'polinoropati' in birlesik
        or 'e10.4' in birlesik or 'e11.4' in birlesik or 'e12.4' in birlesik
        or 'e13.4' in birlesik or 'e14.4' in birlesik or 'g63.2' in birlesik
        or 'g62' in birlesik
    )
    is_noropatik = ('nöropatik' in birlesik or 'noropatik' in birlesik
                    or 'nöropati' in birlesik or 'noropati' in birlesik
                    or 'g50.0' in birlesik or 'g52' in birlesik
                    or 'g53' in birlesik or 'g54' in birlesik
                    or 'g56' in birlesik or 'g57' in birlesik
                    or 'g58' in birlesik or 'g59' in birlesik
                    or 'g60' in birlesik or 'g61' in birlesik)
    is_depresyon = ('depresyon' in birlesik or 'depression' in birlesik
                    or 'f32' in birlesik or 'f33' in birlesik
                    or 'majör depresif' in birlesik
                    or 'major depresif' in birlesik)
    is_epilepsi = ('epilepsi' in birlesik or 'konvulsiy' in birlesik
                   or 'g40' in birlesik or 'nöbet' in birlesik
                   or 'nobet' in birlesik)

    # ── Erken delege noktaları ──
    # Duloksetin + sadece depresyon endikasyonu (nöropatik/fibromiyalji yok)
    # → 4.2.2 psikiyatri butonu kapsasın
    if is_duloksetin and is_depresyon and not (is_fibromiyalji or is_noropatik
                                                or is_phn or is_diyabetik_noro):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj=('Duloksetin depresyon endikasyonunda — '
                   'psikiyatri butonu (SUT 4.2.2) kapsamında kontrol edilir'),
            detaylar={'alt_grup': alt_grup, 'rapor_kodu': rapor_kodu,
                      'is_depresyon': True},
            sut_kurali='SUT 4.2.2 (Depresyon) — Psikiyatri butonuna delege',
        )

    # Pregabalin/Gabapentin + epilepsi endikasyonu → 4.2.25 antiepileptik butonu
    if (is_pregabalin or is_gabapentin) and is_epilepsi and not (
            is_fibromiyalji or is_noropatik or is_phn or is_diyabetik_noro):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj=(f'{alt_grup} epilepsi endikasyonunda — '
                   'antiepileptik butonu (SUT 4.2.25) kapsamında kontrol edilir'),
            detaylar={'alt_grup': alt_grup, 'rapor_kodu': rapor_kodu,
                      'is_epilepsi': True},
            sut_kurali='SUT 4.2.25 (Epilepsi) — Antiepileptik butonuna delege',
        )

    # ── Pregabalin + Gabapentin kombi yasağı (aynı reçete) ──
    diger_metin = ' '.join([str(x).upper() for x in diger_etkenler]
                           + [str(x).upper() for x in diger_ilaclar])
    pregab_var = is_pregabalin or 'PREGABALIN' in diger_metin or any(
        t in diger_metin for t in ('LYRICA', 'GABRICA', 'PREGALIN', 'PREGABEX'))
    gabap_var = is_gabapentin or 'GABAPENTIN' in diger_metin or any(
        t in diger_metin for t in ('NEURONTIN', 'NERUDA', 'GABATEVA', 'GABALEPT'))
    if (is_pregabalin or is_gabapentin) and pregab_var and gabap_var:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=('Pregabalin + Gabapentin AYNI REÇETEDE — '
                   'SUT: kombine kullanılamaz'),
            detaylar={'alt_grup': alt_grup, 'rapor_kodu': rapor_kodu,
                      'kombi_yasak': True},
            uyari='Pregabalin ve gabapentin aynı reçetede birlikte yazılamaz',
            sut_kurali=sut_kurali,
            aranan_ibare='Aynı reçetede pregabalin VE gabapentin yok',
        )

    # ── Endikasyon kontrolü (en az birinin varlığı şart) ──
    endikasyonlar = []
    if is_fibromiyalji:
        endikasyonlar.append('Fibromiyalji (4.2.35.B)')
    if is_phn:
        endikasyonlar.append('Post-herpetik nevralji')
    if is_diyabetik_noro:
        endikasyonlar.append('Diyabetik nöropati / polinöropati')
    if is_noropatik:
        endikasyonlar.append('Nöropatik ağrı')

    detaylar = {
        'alt_grup': alt_grup,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
        'endikasyonlar': endikasyonlar,
        'kategori_4_2_35': '4.2.35.B' if is_fibromiyalji else '4.2.35.A',
    }

    # Alfa lipoik / Kapsaisin için fibromiyalji uygun değil; nöropatik/diyabetik
    if alt_grup in ('ALFA_LIPOIK', 'KAPSAISIN') and is_fibromiyalji \
            and not (is_noropatik or is_phn or is_diyabetik_noro):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'{alt_grup} fibromiyalji için SUT 4.2.35.B kapsamında değil '
                   '— sadece nöropatik ağrı endikasyonunda ödenir'),
            detaylar=detaylar,
            uyari='Alfa lipoik / Kapsaisin: nöropatik ağrı endikasyonu gerekli',
            sut_kurali=sut_kurali,
            aranan_ibare='Nöropatik ağrı / diyabetik nöropati / PHN',
        )

    # ── Raporsuz ──
    if not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'{alt_grup} RAPORSUZ — SUT 4.2.35: nöropatik/fibromiyalji '
                   'endikasyonunda uzman raporu ZORUNLU'),
            detaylar=detaylar,
            uyari='SUT 4.2.35: Uzman raporu (1 yıl, fibromiyalji için 6 ay) gerekli',
            sut_kurali=sut_kurali,
            aranan_ibare='Uzman raporu varlığı',
        )

    # ── Endikasyon hiç bulunmadıysa ──
    if not endikasyonlar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'{alt_grup} raporlu (rap.kod {rapor_kodu}) — '
                   'nöropatik ağrı / fibromiyalji endikasyonu raporda bulunamadı'),
            detaylar=detaylar,
            uyari='SUT 4.2.35: Endikasyon (nöropatik/fibromiyalji/PHN/'
                  'diyabetik nöropati) raporda belirtilmeli',
            sut_kurali=sut_kurali,
            aranan_ibare='nöropatik ağrı / fibromiyalji / PHN / diyabetik nöropati',
        )

    # ── 6/12 ay süre kontrolü ──
    sure_match = re.search(r'(\d{1,2})\s*ay\s*s[uü]r', birlesik)
    if sure_match:
        try:
            sure_ay = int(sure_match.group(1))
            if is_fibromiyalji and sure_ay > 6:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=(f'{alt_grup} fibromiyalji raporu {sure_ay} ay — '
                           'SUT 4.2.35.B: en fazla 6 ay süreli rapor'),
                    detaylar={**detaylar, 'rapor_suresi_ay': sure_ay},
                    uyari='Fibromiyalji raporu 6 ayı aşamaz',
                    sut_kurali=sut_kurali,
                    aranan_ibare='Rapor süresi ≤ 6 ay',
                )
            elif sure_ay > 12:
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN_DEGIL,
                    mesaj=(f'{alt_grup} raporu {sure_ay} ay — '
                           'SUT 4.2.35: en fazla 12 ay süreli rapor'),
                    detaylar={**detaylar, 'rapor_suresi_ay': sure_ay},
                    uyari='Nöropatik ağrı raporu 12 ayı aşamaz',
                    sut_kurali=sut_kurali,
                    aranan_ibare='Rapor süresi ≤ 12 ay',
                )
            detaylar['rapor_suresi_ay'] = sure_ay
        except (ValueError, TypeError):
            pass

    # ── Branş kontrolü (alt gruba göre kabul edilen branşlar) ──
    BRANS_HARITA = {
        'PREGABALIN':  ('NORO', 'NÖRO', 'ALGOL', 'PSIKIYATR', 'PSİKİYATR',
                        'ROMATOLOJ', 'FIZIK TEDAV', 'FIZ. TEDAV', 'FTR'),
        'GABAPENTIN':  ('NORO', 'NÖRO', 'ALGOL', 'PSIKIYATR', 'PSİKİYATR',
                        'ROMATOLOJ', 'FIZIK TEDAV', 'FIZ. TEDAV', 'FTR'),
        'DULOKSETIN':  ('NORO', 'NÖRO', 'ALGOL', 'PSIKIYATR', 'PSİKİYATR',
                        'ROMATOLOJ', 'FIZIK TEDAV', 'FIZ. TEDAV', 'FTR',
                        'ENDOKRIN', 'ENDOKRİN', 'IÇ HASTALIK', 'İÇ HASTALIK',
                        'DAHILIYE', 'DAHİLİYE'),
        'ALFA_LIPOIK': ('NORO', 'NÖRO', 'ENDOKRIN', 'ENDOKRİN',
                        'IÇ HASTALIK', 'İÇ HASTALIK', 'DAHILIYE', 'DAHİLİYE',
                        'FIZIK TEDAV', 'FIZ. TEDAV', 'FTR'),
        'KAPSAISIN':   ('NORO', 'NÖRO', 'ALGOL', 'DERMATOLOJ',
                        'FIZIK TEDAV', 'FIZ. TEDAV', 'FTR'),
    }

    kabul_brans = BRANS_HARITA.get(alt_grup, ())
    brans_metni_uyumlu = any(b in doktor_brans for b in kabul_brans) \
        if doktor_brans else False
    # Rapor metninde branş ibaresi (birlesik metin de _tr_lower edilmeli — bu modül
    # nöropatik kontrolü, çağrı yerinden geliyor; güvenlik için arama tarafını da normalize ediyoruz)
    _birlesik_norm = _tr_lower(birlesik) if birlesik else ''
    rapor_brans_uyumlu = any(_tr_lower(b) in _birlesik_norm for b in kabul_brans)
    # Rapor kodu prefix (10.* nöroloji, 11.* psikiyatri, 13.* FTR varsayılan)
    rapor_kodu_uyumlu = False
    if rapor_kodu:
        if alt_grup in ('PREGABALIN', 'GABAPENTIN'):
            rapor_kodu_uyumlu = rapor_kodu.startswith(('10.', '11.', '13.'))
        elif alt_grup == 'DULOKSETIN':
            rapor_kodu_uyumlu = rapor_kodu.startswith(
                ('10.', '11.', '13.', '04.', '07.'))
        elif alt_grup == 'ALFA_LIPOIK':
            rapor_kodu_uyumlu = rapor_kodu.startswith(
                ('10.', '04.', '07.', '13.'))
        elif alt_grup == 'KAPSAISIN':
            rapor_kodu_uyumlu = rapor_kodu.startswith(('10.', '13.', '14.'))

    brans_uygun = brans_metni_uyumlu or rapor_brans_uyumlu or rapor_kodu_uyumlu

    # ── Pregabalin/Gabapentin için ek SK raporu kontrolü ──
    if alt_grup in ('PREGABALIN', 'GABAPENTIN'):
        saglik_kurulu = bool(re.search(r'sa[ğg]l[ıi]k\s*kurul', birlesik)
                              or 'heyet' in birlesik)
        if not saglik_kurulu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'{alt_grup} raporlu (rap.kod {rapor_kodu}) — '
                       'sağlık kurulu raporu ibaresi tespit edilemedi'),
                detaylar={**detaylar, 'sk_raporu': False,
                          'endikasyon_eslesti': True},
                uyari='SUT 4.2.35: Pregabalin/Gabapentin için en az 1 nöroloji '
                      'uzmanının yer aldığı sağlık kurulu raporu — manuel doğrulanmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='Sağlık kurulu raporu (nöroloji uzmanı dahil)',
            )

    # ── Branş tespit edilemedi ──
    if not brans_uygun:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=(f'{alt_grup} raporlu (rap.kod {rapor_kodu}) — '
                   f'yazan branş "{doktor_brans or "?"}", '
                   'SUT 4.2.35 kabul edilen uzman branşı tespit edilemedi'),
            detaylar={**detaylar, 'brans_uygun': False},
            uyari='Manuel doğrulanmalı — uzman branşı raporda/reçetede belirsiz',
            sut_kurali=sut_kurali,
            aranan_ibare=f'Kabul edilen branşlar: {", ".join(kabul_brans[:5])}…',
        )

    # ── UYGUN ──
    kategori_etiket = '4.2.35.B (fibromiyalji)' if is_fibromiyalji \
        else '4.2.35.A (nöropatik)'
    end_str = ', '.join(endikasyonlar) if endikasyonlar else '—'
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=(f'{alt_grup} — {kategori_etiket} | endikasyon: {end_str} '
               f'(rap.kod {rapor_kodu})'),
        detaylar={**detaylar, 'brans_uygun': True},
        sut_kurali=sut_kurali,
        aranan_ibare='Endikasyon + uzman branş + rapor süresi',
        bulunan_metin=f'Branş: {doktor_brans} | Rapor: {rapor_kodu}',
    )


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

    # ══════════════════════════════════════════════════════════════════
    # REÇETEDEKİ DİĞER İLAÇLARI TARAMA — SUT 4.2.24.B ÜÇLÜ KULLANIM TESPİTİ
    # ══════════════════════════════════════════════════════════════════
    # Hasta LABA+LAMA+ICS üçünü AYNI ANDA kullanıyor mu? (3 ayrı ilaç olarak
    # ya da tek üçlü inhaler) Bu kullanımda SUT'ta özel hüküm var:
    # 3 ay ICS+LABA tedavisine rağmen yetersiz yanıt + ≥2 atak/yıl + mMRC≥2.
    # Kullanıcı isteği: "üçlü kullanılıyorsa SUT özel hükmü raporda var mı bak"
    diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
    # Reçetedeki TÜM ilaçlardan LABA/LAMA/ICS varlığını topla (mevcut + diğerleri)
    laba_ics_kombi_ticari = ['SERETIDE', 'SYMBICORT', 'FOSTER', 'RELVAR', 'DUORESP',
                              'BREQUAL', 'BREQAL', 'BUFOMIX', 'FOKUSAL', 'AIRFLUSAL',
                              'AIRDUO', 'BREO', 'FLUTIFORM', 'VANNAIR', 'WIXELA',
                              'INUVAIR', 'BUFEX', 'AIRPLUS']
    laba_lama_kombi_ticari = ['ANORO', 'ULTIBRO', 'SPIOLTO', 'DUAKLIR', 'BEVESPI', 'STIOLTO']
    laba_tek_ticari = ['FORADIL', 'OXIS', 'SEREVENT', 'ONBREZ', 'STRIVERDI']
    lama_tek_ticari = ['SPIRIVA', 'INCRUSE', 'SEEBRI', 'BRETARIS', 'EKLIRA', 'TUDORZA']
    ics_tek_ticari = ['PULMICORT', 'FLIXOTIDE', 'BECLOFORTE', 'ALVESCO', 'MIFLONIDE',
                       'CORTAIR', 'BUDICORT', 'NEUMOCORT', 'BUDECORT', 'BECLATE',
                       'CLENIL', 'ASMANEX', 'BECLOJET']
    uclu_kombi_ticari = ['TRELEGY', 'TRIMBOW', 'ENERZAIR', 'BREZTRI', 'TRIXEO',
                          'AIRSUPRA']

    recete_has_laba = has_laba
    recete_has_ics = has_ics
    recete_has_lama = has_lama

    for di in diger_ilaclar:
        if isinstance(di, dict):
            di_ad = (di.get('ad', '') or di.get('ilac_adi', '') or '').upper()
            di_etkin = (di.get('etkin_madde', '') or '').upper()
        else:
            di_ad = str(di).upper()
            di_etkin = ''
        if not di_ad and not di_etkin:
            continue
        # Kendi ilacımız listede varsa atla (case-insensitive substring)
        if ilac_adi and ilac_adi.upper() in di_ad:
            continue
        di_combo = di_ad + ' ' + di_etkin
        # Üçlü inhaler tek başına 3'ünü kapsar
        if any(t in di_ad for t in uclu_kombi_ticari):
            recete_has_laba = recete_has_ics = recete_has_lama = True
            continue
        # LABA+ICS kombi
        if any(t in di_ad for t in laba_ics_kombi_ticari):
            recete_has_laba = True
            recete_has_ics = True
        # LABA+LAMA kombi
        if any(t in di_ad for t in laba_lama_kombi_ticari):
            recete_has_laba = True
            recete_has_lama = True
        # Tek bileşen — etkin madde + ticari ad
        if any(m in di_combo for m in laba_maddeler) or any(t in di_ad for t in laba_tek_ticari):
            recete_has_laba = True
        if any(m in di_combo for m in ics_maddeler) or any(t in di_ad for t in ics_tek_ticari):
            recete_has_ics = True
        if any(m in di_combo for m in lama_maddeler) or any(t in di_ad for t in lama_tek_ticari):
            recete_has_lama = True

    # Reçete genelinde üçlü kullanım var mı?
    recete_uclu_kullanim = recete_has_laba and recete_has_ics and recete_has_lama
    detaylar['recete_uclu_kullanim'] = recete_uclu_kullanim
    detaylar['recete_has_laba'] = recete_has_laba
    detaylar['recete_has_ics'] = recete_has_ics
    detaylar['recete_has_lama'] = recete_has_lama

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
                       'VANNAIR', 'WIXELA', 'AIRDUO', 'BREO', 'FLUTIFORM',
                       'BREQUAL', 'BREQAL',  # Salmeterol+Flutikazon (LABA+ICS ikili)
                       'INUVAIR', 'BUFEX', 'BUFOM', 'AIRPLUS']
    is_laba_ics = any(t in ilac_adi for t in laba_ics_ticari) or (has_laba and has_ics and not has_lama)

    # ── LAMA tek başına ──
    lama_ticari = ['SPIRIVA', 'INCRUSE', 'SEEBRI', 'BRETARIS', 'EKLIRA', 'TUDORZA']
    is_lama = (has_lama or any(t in ilac_adi for t in lama_ticari)) and not has_laba and not has_ics

    # ── LABA+LAMA ikili ──
    laba_lama_ticari = ['ANORO', 'ULTIBRO', 'SPIOLTO', 'DUAKLIR', 'BEVESPI', 'STIOLTO']
    is_laba_lama = any(t in ilac_adi for t in laba_lama_ticari) or (has_laba and has_lama and not has_ics)

    # ── Üçlü kombinasyon (LABA+ICS+LAMA) ──
    # Türkiye'de mevcut üçlü inhalerlar:
    # TRELEGY ELLIPTA = Vilanterol + Umeklidinyum + Flutikazon
    # TRIMBOW = Formoterol + Glikopironyum + Beklometazon
    # ENERZAIR BREEZHALER = İndakaterol + Glikopironyum + Mometazon
    # BREZTRI AEROSPHERE = Formoterol + Glikopironyum + Budezonid
    # TRIXEO AEROSPHERE = Formoterol + Glikopironyum + Budezonid (BREZTRI yeni adı)
    # NOT: BREQUAL/BREQAL listede DEĞİL — onlar Salmeterol+Flutikazon (LABA+ICS ikili)
    uclu_ticari = ['TRELEGY', 'TRIMBOW', 'ENERZAIR', 'BREZTRI', 'TRIXEO',
                   'AIRSUPRA', 'TRIMUS', 'TRELE']
    # Etkin madde tabanlı 3'lü tespit (ticari ad listede olmasa bile)
    # Üçlü = LABA + LAMA + ICS hepsi birden (tek ilaçta veya reçetede dağılmış)
    uclu_etkin_eslesti = (has_laba and has_ics and has_lama)
    # Reçetede 3 ayrı ilaç olarak LABA+LAMA+ICS yazılmış olabilir — bu da üçlü.
    # Bu durumda mevcut ilaç tek başına ikili (LABA+ICS) olsa bile reçete genelinde
    # üçlü kullanım olduğu için SUT 4.2.24.B özel hükmü aranacak.
    is_uclu = (any(t in ilac_adi for t in uclu_ticari)
               or uclu_etkin_eslesti
               or recete_uclu_kullanim)

    # ── LTRA (Lökotrien reseptör antagonisti) ──
    # Tek başına: SINGULAIR, ONCEAIR, NOTTA, AIRLUKAST, ACCOLATE
    # Setirizin+Montelukast kombileri: LEVMONT, LEVOKAST, MONKAST
    is_ltra = 'MONTELUKAST' in etkin_madde or 'ZAFIRLUKAST' in etkin_madde or \
              any(t in ilac_adi for t in ['SINGULAIR', 'ONCEAIR', 'LUKASM', 'NOTTA',
                                           'DESMONT', 'AIRLUKAST', 'ACCOLATE',
                                           'LEVMONT', 'LEVOKAST', 'MONKAST',
                                           'MONTELAIR', 'MONLAS', 'NOLEMON',
                                           'AIRPLUS', 'MUSTAIR'])

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

    astim = bool(re.search(r'ast[ıi]m|asthma|astma|bron[sş][iı]?yal\s*ast', metin_lower))
    koah = bool(re.search(r'koah|copd|kronik\s*obstr[uü]ktif|kronik\s*ob\.?\s*akci[gğ]er|akch', metin_lower))
    # Alerjik rinit varyantları:
    # - "alerjik rinit" (standart)
    # - "mevsimsel alerjik rinit" (substring match, ek mevsimsel/perenniyal yakalama)
    # - "alerjit rinit" (yazım hatası tolerans)
    # - "allergic rhinitis", "allerjik rinit"
    # - "rinitis allergica" (Latince), "rhinitis"
    alerjik_rinit = bool(re.search(
        r'aler[jc]i[kt]\s*rinit'        # alerjik/alerjit/alercik rinit (k/t/c)
        r'|allergic\s*rh?initis?'        # allergic rhinitis
        r'|allerjik\s*rinit'             # çift L yazım
        r'|rhinitis\s*aller[gj]ica'      # Latince
        r'|mevsim(sel|li)?\s*rinit'      # mevsimsel rinit / mevsimli
        r'|perenniyal\s*rinit'           # perenniyal rinit
        r'|seasonal\s*rh?initis?'        # seasonal rhinitis
        r'|saman\s*nezles[ıi]',          # saman nezlesi (alerjik rinit halk dili)
        metin_lower
    ))
    bronsiektazi = bool(re.search(r'bron[sş]iektazi|bronchiectasis', metin_lower))
    kistik_fibroz = bool(re.search(r'kistik\s*fibr[oö]z|cystic\s*fibrosis|mukovissidoz', metin_lower))

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
        # Pragmatik fallback: Rapor kodu 05.02 (LABA+LAMA+ICS üçlü) veya 05.x
        # zaten Medula tarafından onaylanmış demek. SUT şartları (3 ay ICS+LABA
        # başarısızlığı, ≥2 atak, mMRC≥2/CAT≥10) raporun kendisinde yer alır;
        # mesaj metnine düşmeyebilir. Eczacı tarafında ek alarm gerekmez.
        if rapor_kodu and (rapor_kodu.startswith('05.') or rapor_kodu.startswith('15.04')
                             or rapor_kodu.startswith('15.05')):
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=f'Üçlü kombinasyon raporlu (rapor {rapor_kodu}) — '
                      f'Medula 3 ay ICS+LABA başarısızlığı + atak + mMRC/CAT şart kontrolünü yapar',
                detaylar={**detaylar, 'medula_otomatik': True},
                sut_kurali='SUT 4.2.24.B — Solunum rapor kodu + Medula şart kontrolü',
                uyari='3 ay ICS+LABA başarısızlığı, ≥2 atak/yıl, mMRC≥2 veya CAT≥10 '
                      'şartları raporda yer aldığı varsayılır',
                aranan_ibare=f'Solunum rapor kodu ({rapor_kodu}) örtük üçlü endikasyon',
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
            # Rapor kodu 05.0x (Solunum) veya 15.04/15.05 — Medula tanı zorunluluğunu kontrol eder
            if rapor_kodu.startswith('05.') or rapor_kodu.startswith('15.04') or rapor_kodu.startswith('15.05'):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'LABA+ICS — solunum rapor kodu ({rapor_kodu}), Medula astım/KOAH tanısı zorunluluğunu kontrol eder',
                    detaylar={**detaylar, 'medula_otomatik': True},
                    sut_kurali='SUT 4.2.24 — Solunum rapor kodu + Medula tanı kontrolü',
                    aranan_ibare=f'Solunum rapor kodu ({rapor_kodu}) örtük endikasyon'
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'LABA+ICS — rapor kodu {rapor_kodu} var ama astım/KOAH tanısı bulunamadı',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LABA+ICS: astım/KOAH tanısı gerekli',
                uyari='Raporda astım (J45/J46) veya KOAH (J43/J44) tanısı olmalı. '
                      'Rapor süresi: 1 yıl. Uzman: göğüs/alerji/iç hast./çocuk.',
                aranan_ibare='astım (J45/J46) / KOAH (J43/J44)'
            )

        # Pragmatik fallback: rapor_kodu okunamamış (None) ama msj=var
        # (ilaç bilgi mesajı geldi). Medula reçeteyi onayladığı için şart
        # kontrolünü zaten yapmış demektir. Eczacı tarafında ek alarm gerekmez.
        msj_durumu = (ilac_sonuc.get('msj_durumu') or ilac_sonuc.get('msj') or '').lower()
        if msj_durumu == 'var':
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='LABA+ICS — rapor kodu okunamadı ama mesaj mevcut, Medula şart kontrolünü yapar',
                detaylar={**detaylar, 'medula_otomatik': True, 'rapor_okunamadi': True},
                sut_kurali='SUT 4.2.24 — LABA+ICS: rapor okuma fail, Medula otomatik kontrol',
                uyari='Rapor kodu DOM\'dan okunamadı; reçete Medula tarafından onaylı',
                aranan_ibare='msj=var (Medula bilgi mesajı geldi)'
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
            # Solunum/genel raporlu kodlar — Medula tanı kontrolünü yapar
            if (rapor_kodu.startswith('05.') or rapor_kodu.startswith('20.')
                or rapor_kodu.startswith('15.04') or rapor_kodu.startswith('15.05')):
                return KontrolRaporu(
                    sonuc=KontrolSonucu.UYGUN,
                    mesaj=f'LTRA — rapor kodu {rapor_kodu}, Medula astım/alerjik rinit tanı kontrolünü yapar',
                    detaylar={**detaylar, 'medula_otomatik': True},
                    sut_kurali='SUT 4.2.24 — Solunum/genel rapor + Medula tanı kontrolü',
                    aranan_ibare=f'Rapor kodu ({rapor_kodu}) örtük endikasyon'
                )
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=f'LTRA — rapor kodu {rapor_kodu} var ama astım/alerjik rinit tanısı bulunamadı',
                detaylar=detaylar,
                sut_kurali='SUT 4.2.24 — LTRA: astım veya alerjik rinit tanısı gerekli',
                uyari='Raporda astım (J45/J46) veya alerjik rinit (J30) tanısı olmalı.',
                aranan_ibare='astım (J45/J46) / alerjik rinit (J30)'
            )

        # Pragmatik fallback: rapor_kodu okunamamış (None) ama msj=var
        msj_durumu = (ilac_sonuc.get('msj_durumu') or ilac_sonuc.get('msj') or '').lower()
        if msj_durumu == 'var':
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj='LTRA — rapor kodu okunamadı ama mesaj mevcut, Medula şart kontrolünü yapar',
                detaylar={**detaylar, 'medula_otomatik': True, 'rapor_okunamadi': True},
                sut_kurali='SUT 4.2.24 — LTRA: rapor okuma fail, Medula otomatik kontrol',
                uyari='Rapor kodu DOM\'dan okunamadı; reçete Medula tarafından onaylı',
                aranan_ibare='msj=var (Medula bilgi mesajı geldi)'
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
        # Detaylı ESA kontrolü — 217 kodu (reçete açıklaması) + Hb/Ferritin/TSAT + uzman branş
        teshis_metin_local = ' '.join(ilac_sonuc.get('recete_teshisleri', []) or [])
        return _esa_detayli_kontrol(ilac_adi, etkin_madde, rapor_kodu, metin,
                                     teshis_metin_local, ilac_sonuc=ilac_sonuc)

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
                        'SERTAKONAZOL', 'SIKLOPIROKS', 'NAFTIFIN', 'TIOKONAZOL',
                        'BUTENAFIN', 'AMOROLFIN']
    topikal_ticari = ['TRAVAZOL', 'OCERAL', 'ANDOREX', 'TANTUM', 'LAMISIL',
                      'FUNGICIDE', 'CANESTEN', 'CANDIO', 'MYCOSTATIN',
                      'EXODERIL', 'LOCERYL', 'TROSYD', 'DERMOTROSYD',
                      'DERMIFIN', 'TERBIN', 'TERBISIL', 'FUNGOSTOP',
                      'KLOROBEN']
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


def kontrol_medula_otomatik(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    Medula'nın kendisi tarafından otomatik kontrol edilen ilaç/ürün grupları.

    Kullanım: Diyabet test çubukları, lansetler, glukometre stripleri vb.
    Bu ürünler ödeme/şart kontrolü Medula tarafından SUT kuralları gereği
    otomatik yapılır (ör: kullanım sıklığı, insülin kullanımı). Eczacının
    ek bir SUT kontrolü yapmasına gerek yoktur.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '?')[:60]
    return KontrolRaporu(
        KontrolSonucu.UYGUN,
        f"Medula otomatik kontrol — eczacı kontrolüne gerek yok ({ilac_adi})",
        sut_kurali='Medula otomatik şart kontrolü (test çubukları/sarf)',
        detaylar={'alt_kategori': 'MEDULA_OTOMATIK'}
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

    # Türkçe 'İ' (U+0130) Python'un lower()'ında 'i̇' (i + combining dot) verir;
    # önce 'i'ye normalize et. 'I' → 'ı' YAPMA: İngilizce büyük 'I' (örn.
    # "HEMOGLOBIN", "FERRITIN") str.lower() ile zaten 'i'ye dönüşmeli, aksi
    # halde 'hemoglobın' / 'ferritın' olur ve aranan kelimeyle eşleşmez.
    metin_lower = metin.replace('İ', 'i').lower()

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


# ═══════════════════════════════════════════════════════════════════════
# HEPATİT B/C İLAÇLARI (SUT 4.2.13.3 / 4.2.13.4)
# ═══════════════════════════════════════════════════════════════════════

# HBV nükleos(t)id analogları (ATC J05AF) — kronik HBV tedavisi
_HEPATIT_HBV_ETKEN = (
    'ENTEKAVIR', 'TENOFOVIR', 'TENOFOVIR DISOPROKSIL',
    'TENOFOVIR DISOPROKSIL FUMARAT', 'TENOFOVIR ALAFENAMID',
    'LAMIVUDIN', 'TELBIVUDIN', 'ADEFOVIR', 'ADEFOVIR DIPIVOKSIL',
)
_HEPATIT_HBV_TICARI = (
    'BARACLUDE', 'ENTAVIR', 'ENTECAVIR',
    'VIREAD', 'TENOF', 'VEMLIDY',
    'ZEFFIX', 'EPIVIR HBV', 'SEBIVO', 'TYZEKA',
    'HEPSERA',
)

# HCV DAA (Direct-Acting Antivirals, ATC J05AP)
_HEPATIT_HCV_ETKEN = (
    'SOFOSBUVIR', 'LEDIPASVIR', 'VELPATASVIR', 'VOXILAPREVIR',
    'GLEKAPREVIR', 'GLECAPREVIR', 'PIBRENTASVIR',
    'OMBITASVIR', 'PARITAPREVIR', 'DASABUVIR',
    'DAKLATASVIR', 'ELBASVIR', 'GRAZOPREVIR',
)
_HEPATIT_HCV_TICARI = (
    'SOVALDI', 'HARVONI', 'EPCLUSA', 'VOSEVI',
    'MAVYRET', 'MAVIRET', 'VIEKIRAX', 'EXVIERA',
    'DAKLINZA', 'ZEPATIER',
)

# Klasik HBV/HCV tedavisi (peginterferon + ribavirin)
_HEPATIT_KLASIK_ETKEN = (
    'PEGINTERFERON', 'PEGINTERFERON ALFA', 'PEGINTERFERON ALFA-2A',
    'PEGINTERFERON ALFA-2B', 'INTERFERON ALFA',
    'RIBAVIRIN',
)
_HEPATIT_KLASIK_TICARI = (
    'PEGASYS', 'PEGINTRON', 'COPEGUS', 'REBETOL', 'VIRAZOLE',
)


def _hepatit_alt_sinif(ilac_adi: str, etkin: str) -> str:
    """Hepatit ilacının HBV / HCV / KLASIK / NONE alt sınıfı.

    HIV ilaçları (Dolutegravir/Abacavir vb.) bu butonun KAPSAMI DIŞI —
    onlar ANTIVIRAL kategorisinde kalır, HEPATIT butonu sadece HBV/HCV/
    klasik tedaviyi kapsar.
    """
    ad = (ilac_adi or '').upper()
    et = (etkin or '').upper()
    arama = ad + ' ' + et

    if any(e in arama for e in _HEPATIT_HCV_ETKEN) or \
       any(t in ad for t in _HEPATIT_HCV_TICARI):
        return 'HCV'
    if any(e in arama for e in _HEPATIT_HBV_ETKEN) or \
       any(t in ad for t in _HEPATIT_HBV_TICARI):
        return 'HBV'
    if any(e in arama for e in _HEPATIT_KLASIK_ETKEN) or \
       any(t in ad for t in _HEPATIT_KLASIK_TICARI):
        return 'KLASIK'
    return 'NONE'


def kontrol_hepatit(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3 (Kronik Hepatit B) ve 4.2.13.4 (Kronik Hepatit C DAA)
    kontrol fonksiyonu.

    Kapsam:
      - HBV: Entekavir, Tenofovir TDF/TAF, Lamivudin, Telbivudin, Adefovir
      - HCV DAA: Sofosbuvir, Ledipasvir, Velpatasvir, Voxilaprevir,
                 Glecaprevir, Pibrentasvir, Ombitasvir, Paritaprevir,
                 Dasabuvir, Daklatasvir, Elbasvir, Grazoprevir
      - Klasik: Peginterferon alfa, Ribavirin

    Kurallar:
      • Uzman branşı: Gastroenteroloji / Enfeksiyon Hastalıkları /
                      Hepatoloji (HBV için İç Hastalıkları da kabul)
      • HBV: HBsAg pozitif + (HBeAg pozitif → HBV DNA ≥ 20.000 IU/mL,
              HBeAg negatif → ≥ 2.000 IU/mL) + ALT yüksek veya biyopsi
      • HCV: Anti-HCV pozitif + HCV RNA pozitif + genotip + fibrozis
              evresi (METAVIR F0-F4) — HCV DAA tedavi süresi 8/12/16/24
              hafta protokolü
      • Rapor kodu pragmatik fallback: 06.01 / 14.01 / B16-B18 → Medula
        zaten endikasyon/lab şartı kontrol etmiş kabul edilir
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()

    alt_sinif = _hepatit_alt_sinif(ilac_adi, etkin)
    sut_kurali = ('SUT 4.2.13.3 / 4.2.13.4 — Hepatit B/C uzman raporu '
                  '+ lab değerleri')

    if alt_sinif == 'NONE':
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Hepatit (HBV/HCV) ilacı değil',
            sut_kurali=sut_kurali,
        )

    detaylar = {
        'alt_sinif': alt_sinif,
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin,
        'rapor_kodu': rapor_kodu,
    }

    # ── 1. Rapor kodu zorunlu ──
    if not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'{alt_sinif} hepatit ilacı RAPORSUZ — uzman raporu ZORUNLU',
            detaylar=detaylar,
            uyari='Gastroenteroloji / Enfeksiyon Hastalıkları uzman raporu gerekli',
            sut_kurali=sut_kurali,
            aranan_ibare='rapor (zorunlu)'
        )

    # ── 2. Metinleri birleştir (mesaj + rapor açıklamaları + reçete açıklamaları) ──
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    birlesik = (tum_metin or '') + ' ' + teshis_metin
    metin_lower = (birlesik.replace('İ', 'i').replace('I', 'ı').lower()
                   if birlesik else '')

    # ── 3. Endikasyon (HBV / HCV) ──
    hbv_var = (any(k in metin_lower for k in
                   ['hepatit b', 'hbv', 'hbsag', 'hepatitis b', 'kronik hepatit b'])
               or any(c in teshis_metin for c in ['B16', 'B18.0', 'B18.1']))
    hcv_var = (any(k in metin_lower for k in
                   ['hepatit c', 'hcv', 'hepatitis c', 'kronik hepatit c',
                    'anti-hcv', 'anti hcv'])
               or any(c in teshis_metin for c in ['B17.1', 'B18.2']))

    # ── 4. Lab değerleri ──
    hbv_dna, hbv_dna_eslesen = _lab_degeri_cek(birlesik, ['hbv dna', 'hbv-dna'])
    hcv_rna, hcv_rna_eslesen = _lab_degeri_cek(birlesik, ['hcv rna', 'hcv-rna'])
    alt_deg, _ = _lab_degeri_cek(birlesik, ['alt', 'sgpt'])
    ast_deg, _ = _lab_degeri_cek(birlesik, ['ast', 'sgot'])

    # HCV-spesifik: genotip + fibrozis evresi
    genotip_match = re.search(r'genot[iı]p\s*[:\-]?\s*([0-9][a-z]?)', metin_lower)
    genotip = genotip_match.group(1) if genotip_match else None
    fibrozis_match = re.search(r'\b(f[0-4])\b|\bmetav[iı]r\s*[:\-]?\s*(f?[0-4])\b',
                               metin_lower)
    fibrozis = (fibrozis_match.group(1) or fibrozis_match.group(2)
                if fibrozis_match else None)

    # HBV-spesifik: HBeAg durumu
    hbeag_pos = any(k in metin_lower for k in
                    ['hbeag pozitif', 'hbeag(+)', 'hbeag +', 'hbe ag pozitif'])
    hbeag_neg = any(k in metin_lower for k in
                    ['hbeag negatif', 'hbeag(-)', 'hbeag -', 'hbe ag negatif'])

    # Tedavi süresi (HCV DAA için): 8/12/16/24 hafta
    sure_match = re.search(r'(\d{1,2})\s*hafta', metin_lower)
    tedavi_haftasi = int(sure_match.group(1)) if sure_match else None

    # Uzman branş
    uzman_var = any(k in metin_lower for k in
                    ['gastroenteroloji', 'gastro', 'enfeksiyon', 'enfeksi̇yon',
                     'hepatoloji', 'iç hastalıkları', 'ic hastaliklari',
                     'dahiliye'])

    detaylar.update({
        'hbv_endikasyon': hbv_var, 'hcv_endikasyon': hcv_var,
        'hbv_dna': hbv_dna, 'hcv_rna': hcv_rna,
        'alt': alt_deg, 'ast': ast_deg,
        'genotip': genotip, 'fibrozis': fibrozis,
        'hbeag_pozitif': hbeag_pos, 'hbeag_negatif': hbeag_neg,
        'tedavi_haftasi': tedavi_haftasi,
        'uzman': uzman_var,
    })

    bulunan_parcalar = []
    if hbv_var: bulunan_parcalar.append('Hepatit B')
    if hcv_var: bulunan_parcalar.append('Hepatit C')
    if hbv_dna is not None: bulunan_parcalar.append(f'HBV DNA: {hbv_dna}')
    if hcv_rna is not None: bulunan_parcalar.append(f'HCV RNA: {hcv_rna}')
    if alt_deg is not None: bulunan_parcalar.append(f'ALT: {alt_deg}')
    if genotip: bulunan_parcalar.append(f'Genotip {genotip}')
    if fibrozis: bulunan_parcalar.append(f'Fibrozis {fibrozis.upper()}')
    if hbeag_pos: bulunan_parcalar.append('HBeAg(+)')
    if hbeag_neg: bulunan_parcalar.append('HBeAg(-)')
    if tedavi_haftasi: bulunan_parcalar.append(f'{tedavi_haftasi} hafta')
    if uzman_var: bulunan_parcalar.append('uzman branş var')
    bulunan_metin = ' | '.join(bulunan_parcalar) if bulunan_parcalar else ''

    # ── 5. İlaç-endikasyon tutarlılık kontrolü ──
    # HBV ilacı yazılmış ama metinde HCV bulundu — yanlış endikasyon (uyarı)
    tutarsizlik = None
    if alt_sinif == 'HBV' and hcv_var and not hbv_var:
        tutarsizlik = 'HBV ilacı ama metinde sadece HCV bulundu'
    elif alt_sinif == 'HCV' and hbv_var and not hcv_var:
        tutarsizlik = 'HCV DAA ilacı ama metinde sadece HBV bulundu'

    # ── 6. Aranan ibare metni (rapor için) ──
    aranan_parts = []
    if alt_sinif == 'HBV':
        aranan_parts = ['HBsAg pozitif', 'HBV DNA (≥2.000 IU/mL HBeAg-, '
                        '≥20.000 HBeAg+)', 'ALT', 'Gastroenteroloji/Enfeksiyon']
    elif alt_sinif == 'HCV':
        aranan_parts = ['Anti-HCV pozitif', 'HCV RNA pozitif',
                        'Genotip', 'Fibrozis (METAVIR F0-F4)',
                        'Gastroenteroloji/Enfeksiyon', 'Tedavi süresi (8/12/16/24 hafta)']
    else:
        aranan_parts = ['HBV/HCV endikasyonu', 'Viral yük (DNA/RNA)',
                        'Uzman branş']
    aranan_ibare = ' + '.join(aranan_parts)

    # ── 7. Karar mantığı ──
    eksikler = []
    if alt_sinif == 'HBV':
        if not hbv_var:
            eksikler.append('HBV tanısı/HBsAg yok')
        if hbv_dna is None:
            eksikler.append('HBV DNA değeri yok')
        if not uzman_var:
            eksikler.append('uzman branş ibaresi yok')
    elif alt_sinif == 'HCV':
        if not hcv_var:
            eksikler.append('HCV tanısı yok')
        if hcv_rna is None:
            eksikler.append('HCV RNA değeri yok')
        if genotip is None:
            eksikler.append('genotip yok')
        if fibrozis is None:
            eksikler.append('fibrozis evresi (METAVIR) yok')
        if not uzman_var:
            eksikler.append('uzman branş ibaresi yok')
    else:  # KLASIK
        if not (hbv_var or hcv_var):
            eksikler.append('HBV/HCV endikasyonu yok')
        if not uzman_var:
            eksikler.append('uzman branş ibaresi yok')

    detaylar['eksikler'] = eksikler

    # Pragmatik fallback: SGK rapor kodu antiviral aile (06.01 / 14.* / B*)
    # ile reçeteyi kabul ettiyse → Medula endikasyon/lab şart kontrolünü
    # yapmıştır → eksiklikleri "uyarı" sınıfına düşür
    rapor_pragmatik = (rapor_kodu.startswith('06.01')
                       or rapor_kodu.startswith('14.')
                       or rapor_kodu.startswith('B'))

    uyari_metin = None
    if tutarsizlik:
        uyari_metin = f'TUTARSIZLIK: {tutarsizlik}'

    # Tam uygun: tüm kritik alanlar bulundu
    if not eksikler:
        msg = f'{alt_sinif} hepatit — tüm zorunlu alanlar mevcut (rapor {rapor_kodu})'
        if bulunan_parcalar:
            msg += f' | {" | ".join(bulunan_parcalar)}'
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL if tutarsizlik else KontrolSonucu.UYGUN,
            mesaj=msg if not tutarsizlik else f'{msg} ANCAK {tutarsizlik}',
            detaylar=detaylar,
            uyari=uyari_metin or 'Tedavi süresi/protokol manuel kontrol edilmeli',
            sut_kurali=sut_kurali,
            aranan_ibare=aranan_ibare,
            bulunan_metin=bulunan_metin,
        )

    # Eksiklikler var ama rapor pragmatik → UYGUN + uyarı
    if rapor_pragmatik:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'{alt_sinif} hepatit — rapor {rapor_kodu} (Medula endikasyon/'
                   f'lab şart kontrolünü yapar)'),
            detaylar={**detaylar, 'medula_otomatik': True},
            uyari=(f'Eksik metin: {", ".join(eksikler)} — raporun kendisinde '
                   f'mevcut olduğu varsayılır'),
            sut_kurali=sut_kurali,
            aranan_ibare=aranan_ibare,
            bulunan_metin=bulunan_metin,
        )

    # Endikasyon var ama lab/uzman eksik → ŞÜPHELİ
    if (hbv_var or hcv_var) and len(eksikler) <= 2:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'{alt_sinif} hepatit — eksik bilgi: {", ".join(eksikler)}',
            detaylar=detaylar,
            uyari=(uyari_metin or
                   f'Mevcut: {bulunan_metin or "az bilgi"}. '
                   f'SUT: viral yük + uzman branş ZORUNLU.'),
            sut_kurali=sut_kurali,
            aranan_ibare=aranan_ibare,
            bulunan_metin=bulunan_metin,
        )

    # Hiçbir endikasyon ibaresi yok → UYGUN_DEGIL
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN_DEGIL,
        mesaj=(f'{alt_sinif} hepatit UYGUN DEĞİL: '
               f'eksik zorunlu bilgi ({", ".join(eksikler)})'),
        detaylar=detaylar,
        uyari=(uyari_metin or
               'SUT: HBV/HCV tanısı + viral yük + uzman branş ZORUNLU'),
        sut_kurali=sut_kurali,
        aranan_ibare=aranan_ibare,
        bulunan_metin=bulunan_metin,
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
    'ANTIEPILEPTIK': kontrol_antiepileptik_4_2_25,
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
    'MEDULA_OTOMATIK': kontrol_medula_otomatik,
    'BIFOSFONAT': kontrol_bifosfonat,
    'RALOKSIFEN': kontrol_raloksifen,
    'KALSITONIN': kontrol_kalsitonin,
    'AKTIF_D_VITAMINI': kontrol_aktif_d_vitamini,
    'OSTEOPOROZ_BIYOLOJIK': kontrol_osteoporoz_biyolojik,
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
    'IMMUNSUPRESIF': lambda s: _immunsupresif_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or [])),
    'ENTERAL_BESLENME': lambda s: _enteral_beslenme_detayli_kontrol(
        (s.get('ilac_adi') or '').upper(), (s.get('etkin_madde') or '').upper(),
        s.get('rapor_kodu', ''), _tum_metinleri_birlesir(s),
        ' '.join(s.get('recete_teshisleri', []) or []),
        ilac_sonuc=s),
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
    'ANTIEPILEPTIK': 'Antiepileptik İlaçlar (4.2.25)',
    'SOLUNUM': 'Solunum İlaçları (4.2.9/4.2.24.B)',
    'GENEL_RAPORLU': 'Genel Raporlu İlaç',
    'ONKOLOJI': 'Onkoloji İlaçları',
    'NOROLOJI': 'Nöroloji İlaçları',
    'GOZ': 'Göz İlaçları',
    'ANTIVIRAL': 'Antiviral İlaçlar',
    'GIS': 'GİS İlaçları',
    'BIFOSFONAT': 'Bifosfonat/Osteoporoz (4.2.17.A)',
    'RALOKSIFEN': 'Raloksifen/Bazedoksifen (4.2.17.A(6a))',
    'KALSITONIN': 'Kalsitonin (4.2.17.A 7-8 + 4.2.17.B Sudek)',
    'AKTIF_D_VITAMINI': 'Aktif D vitamini (4.2.17.A(9) — osteoporozda ödenmez)',
    'OSTEOPOROZ_BIYOLOJIK': 'Osteoporoz biyolojik / Denosumab (4.2.17.A(6b))',
    'RECETE_TURU_KIRMIZI': 'Kırmızı Reçete Zorunlu (4.2.4)',
    'RECETE_TURU_YESIL': 'Yeşil Reçete Zorunlu',
    'TRIMETAZIDIN': 'Trimetazidin (4.2.14.C)',
    'DMAH': 'DMAH/Enoksaparin (4.2.7)',
    'KADIN_HORMON': 'Kadın Cinsiyet Hormonları (4.2.29)',
    'ANTIBIYOTIK_FLOROKINOLON': 'Florokinolon Antibiyotik (EK-4/E)',
    'RAPORSUZ_BILGILENDIRME': 'Raporsuz Verilebilir',
    'MONO_ANTIHIPERTANSIF': 'Mono Antihipertansif',
    'POTASYUM_SITRAT': 'Potasyum Sitrat (EK-4/F)',
    'MEDULA_OTOMATIK': 'Medula Otomatik Kontrol (Test çubuğu/sarf)',
    'BENZODIAZEPIN': 'Benzodiazepin/Anksiyolitik',
    'GOZ_LUBRIKAN': 'Göz Lubrikan / Suni Gözyaşı',
    'ADHD': 'ADHD (4.2.34.B)',
    'INKONTINANS': 'İnkontinans / Antimuskarinik (4.2.16.B)',
    'BPH_PROSTAT': 'BPH / Prostat Tedavisi',
    'DEMIR_IV': 'IV Demir Tedavisi',
    'DESMOPRESIN': 'Desmopresin (Enürezis/DI)',
    'NOROPATIK_AGRI': 'Nöropatik Ağrı (Gabapentin/Pregabalin/Duloksetin)',
    'ENTERAL_BESLENME': 'Enteral Beslenme Solüsyonları',
    'IMMUNSUPRESIF': 'İmmünosüpresif (Organ Nakli / 4.2.32)',
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


# ═══════════════════════════════════════════════════════════════════════
# ÇEŞİTLİ İLAÇLAR SUT KONTROLLERİ (3 alt grup tek dispatcher altında)
# ═══════════════════════════════════════════════════════════════════════
# 1. ÜRİNER İNKONTİNANS (SUT EK-4/F Madde 45) — antimuskarinik / β3-agonist
#    + Duloksetin (yalnız erişkin kadın + stres SUI)
# 2. SUNİ GÖZYAŞI (SUT EK-4/F Madde 2) — keratitis sicca / kuru göz
# 3. BPH α-BLOKER — benign prostat hiperplazisi (Alfuzosin/Tamsulosin/
#    Terazosin/Doksazosin/Silodosin)

# ── ÜRİNER ──
_CESITLI_URINER_ANTIMUSKARINIK_ETKEN = (
    'SOLIFENASIN', 'SOLIFENACIN',
    'TOLTERODIN', 'TOLTERODINE',
    'TROSPIYUM', 'TROSPIUM', 'TROSPIYUM KLORÜR',
    'DARIFENASIN', 'DARIFENACIN',
    'PROPIVERIN', 'PROPIVERINE',
    'FESOTERODIN', 'FESOTERODINE',
    'OKSIBUTININ', 'OXYBUTYNIN',
)
_CESITLI_URINER_BETA3_ETKEN = ('MIRABEGRON',)
_CESITLI_URINER_DULOKSETIN_ETKEN = (
    'DULOKSETIN', 'DULOXETIN', 'DULOXETINE',
)
# Antimuskarinik ticari isimler (kombi yasağına dahil — Mirabegron HARİÇ)
_CESITLI_URINER_ANTIMUSKARINIK_TICARI = (
    'VESICARE',         # Solifenasin
    'KINZY',            # Solifenasin
    'DETRUSITOL',       # Tolterodin-L
    'DETRUSAN',
    'TOVIAZ',           # Fesoterodin
    'EMSELEX',          # Darifenasin
    'MICTONORM',        # Propiverin
    'SPASMEKS',         # Trospiyum
    'DITROPAN',         # Oral oksibutinin
    'KENTERA',          # Transdermal oksibutinin
    'URIVESC',          # Trospiyum
)
_CESITLI_URINER_BETA3_TICARI = ('BETMIGA',)
_CESITLI_URINER_DULOKSETIN_TICARI = ('CYMBALTA', 'DUXET', 'DULOX')

# ── SUNİ GÖZYAŞI ──
_CESITLI_GOZYASI_ETKEN = (
    'HYALURONAT', 'HYALURONIK', 'HYALURONIC',
    'HIPROMELLOZ', 'HİPROMELLOZ', 'HYPROMELLOSE',
    'KARMELLOZ', 'KARMELOZ', 'CARMELLOSE',
    'POLIVINIL ALKOL', 'POLYVINYL ALCOHOL', 'POLİVİNİL ALKOL',
    'TREHALOZ', 'TREHALOSE',
    'PROPILEN GLIKOL', 'PROPYLENE GLYCOL',
    'POLIETILENGLIKOL', 'POLYETHYLENE GLYCOL', 'PEG-400', 'PEG 400',
    'PEROBORAT', 'PERBORATE', 'SODYUM PERBORAT',
    'POVIDON', 'POVIDONE', 'POVIDON-K',
    'DEKSPANTENOL', 'DEXPANTHENOL',  # gözyaşı kombi ürünlerinde
)
_CESITLI_GOZYASI_TICARI = (
    'TEARS NATURALE', 'TEARS', 'TEARGEN',
    'HYLO-COMOD', 'HYLO COMOD', 'HYLOCOMOD', 'HYLO-CARE', 'HYLO CARE',
    'HYLAN', 'HYLABAK', 'HYLO-PARIN',
    'OPTIVE', 'OPTIVE FUSION', 'OPTAVE',
    'REFRESH',
    'SYSTANE',
    'ARTELAC',
    'CELLUVISC',
    'GENTEAL',
    'BLEPHAGEL', 'BLEPHACLEAN',
    'THEALOZ', 'THEALOZ DUO',
    'VIDISIC', 'VIDISIC GEL',
    'OXYAL',
    'VISMED', 'VISMED GEL',
    'XAILIN',
    'AYNAGOZ',
    'DEPANTOL',
    'POVITEAR',
    'GENTERAR',
    'EYESTIL',
    'BIOTRUE',
    'OPTYAL',
)

# ── BPH α-BLOKER ──
_CESITLI_BPH_ALFA_ETKEN = (
    'ALFUZOSIN',
    'TAMSULOSIN', 'TAMSULOZIN',
    'TERAZOSIN',
    'DOKSAZOSIN', 'DOXAZOSIN',
    'SILODOSIN',
)
_CESITLI_BPH_TICARI = (
    'XATRAL', 'ALFUSIN', 'ALFASIN',                     # Alfuzosin
    'UROREC',                                            # Silodosin
    'FLOMAX', 'FOKUSIN', 'TAMSI', 'TAMPROST', 'OMNIC',  # Tamsulosin
    'CARDURA',                                           # Doksazosin
    'HYTRIN', 'TERAVAN',                                 # Terazosin
    'COMBODART', 'DUPROST PLUS',                         # α-bloker içeren kombi
)


def _cesitli_alt_grup_tespit(ilac_adi: str, etkin_madde: str,
                              atc_kodu: str) -> str:
    """Satırın ÇEŞİTLİ kapsamına girip girmediğini ve hangi alt gruba ait
    olduğunu tespit eder.

    Dönüş: 'URINER' / 'GOZYASI' / 'BPH' / 'NONE'

    ATC önceliği:
      - G04BD*  → URINER (üriner antispazmotik / Mirabegron)
      - G04CA*  → BPH (α-bloker — BPH'da kullanılan)
      - S01XA / S01KA / S01X  → GOZYASI (oftalmoloji)
      - N06AX21 → URINER (Duloksetin — üriner endikasyonu için)
        NOT: Duloksetin ATC bu olsa da depresyon endikasyonunda da yazılır;
        bu fonksiyon kapsamı SUT M.45 olduğu için yine de URINER döndürür,
        nihai endikasyon kontrolü kontrol_cesitli_madde_45_uriner içinde yapılır.
    """
    ad = (ilac_adi or '').upper()
    et = (etkin_madde or '').upper()
    a = (atc_kodu or '').upper().strip()

    if a.startswith('G04BD'):
        return 'URINER'
    if a.startswith('G04CA'):
        return 'BPH'
    if a.startswith('S01XA') or a.startswith('S01KA') or a.startswith('S01X'):
        return 'GOZYASI'
    if a.startswith('N06AX21'):
        return 'URINER'

    arama = ad + ' ' + et

    if (any(e in arama for e in _CESITLI_URINER_ANTIMUSKARINIK_ETKEN)
            or any(e in arama for e in _CESITLI_URINER_BETA3_ETKEN)
            or any(t in ad for t in _CESITLI_URINER_ANTIMUSKARINIK_TICARI)
            or any(t in ad for t in _CESITLI_URINER_BETA3_TICARI)):
        return 'URINER'
    if (any(e in arama for e in _CESITLI_URINER_DULOKSETIN_ETKEN)
            or any(t in ad for t in _CESITLI_URINER_DULOKSETIN_TICARI)):
        return 'URINER'
    if (any(e in arama for e in _CESITLI_GOZYASI_ETKEN)
            or any(t in ad for t in _CESITLI_GOZYASI_TICARI)):
        return 'GOZYASI'
    if (any(e in arama for e in _CESITLI_BPH_ALFA_ETKEN)
            or any(t in ad for t in _CESITLI_BPH_TICARI)):
        return 'BPH'
    return 'NONE'


def _cesitli_aile_hekimi_tespit(doktor_brans: str, kurum_adi: str,
                                  tesis_kodu: str) -> Tuple[bool, str]:
    """ARB ile aynı 3 yollu aile hekimi tespiti.
    Dönüş: (aile_hekimi_mi, yetki_kaynagi_aciklamasi)
    """
    db = (doktor_brans or '').upper()
    ka = (kurum_adi or '').upper()
    tk = str(tesis_kodu or '').strip()

    brans_aile_hek = (
        'AILE HEK' in db or 'AİLE HEK' in db
        or 'AİLE HEKİMLİĞİ' in db or 'AILE HEKIMLIGI' in db
    )
    kurum_asm = bool(ka) and (
        'AILE SAGLIGI' in ka or 'AİLE SAĞLIĞI' in ka
        or 'AILE SAĞLIĞI' in ka or 'AİLE SAGLIGI' in ka
        or 'AILE HEKIMLIGI' in ka or 'AİLE HEKİMLİĞİ' in ka
        or any(tok in ka.split() for tok in ('ASM', 'AHM'))
    )
    tesis_aile_hek = bool(tk) and (tk in AILE_HEKIMLIGI_TESIS_KODLARI)

    nedenler = []
    if brans_aile_hek:
        nedenler.append('branşta aile hekimliği')
    if kurum_asm:
        nedenler.append(f'kurum: {ka[:50]}')
    if tesis_aile_hek:
        nedenler.append(f'tesis kodu: {tk}')
    return (brans_aile_hek or kurum_asm or tesis_aile_hek,
            ' + '.join(nedenler))


def kontrol_cesitli_madde_45_uriner(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F Madde 45 — Üriner inkontinans tedavisi.

    Kapsam:
      - Antimuskarinik: Solifenasin, Tolterodin-L, Trospiyum, Darifenasin,
                       Propiverin, Fesoterodin, Transdermal/Oral Oksibutinin
      - β3-agonist:    Mirabegron
      - SNRI (özel):   Duloksetin (yalnız erişkin kadın + stres SUI / mikst SUI)

    Kurallar:
      1. Antimuskarinik + Mirabegron: oral oksibutinine yanıtsız/intoleran
         hastalarda Nöroloji/FTR/Üroloji/Pediatri/Geriatri/Kadın-Doğum uzman
         hekim raporuna dayanılarak TÜM uzman hekimlerce reçete edilir.
      2. Duloksetin: erişkin kadın + stres SUI / mikst SUI'da Nöroloji/FTR/
         Üroloji/Geriatri/Kadın-Doğum uzman hekim raporu ile TÜM uzman
         hekimlerce reçete edilir (Pediatri YOK).
      3. KOMBİ YASAĞI: Antimuskarinikler (Mirabegron HARİÇ) birlikte ödenmez.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    cinsiyet = (ilac_sonuc.get('cinsiyet') or '').upper().strip()

    diger_etkenler = ilac_sonuc.get('diger_etken_maddeler') or []
    diger_ilac_adlari = ilac_sonuc.get('diger_ilac_adlari') or []
    diger_arama = ' '.join(
        [str(x).upper() for x in (diger_etkenler + diger_ilac_adlari)])

    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''
    sut_kurali = 'SUT EK-4/F Madde 45 — Üriner inkontinans tedavisi'

    arama = ilac_adi + ' ' + etkin_madde
    is_antimuskarinik = (
        any(e in arama for e in _CESITLI_URINER_ANTIMUSKARINIK_ETKEN)
        or any(t in ilac_adi for t in _CESITLI_URINER_ANTIMUSKARINIK_TICARI)
    )
    is_mirabegron = (
        'MIRABEGRON' in arama
        or any(t in ilac_adi for t in _CESITLI_URINER_BETA3_TICARI)
    )
    is_duloksetin = (
        any(e in arama for e in _CESITLI_URINER_DULOKSETIN_ETKEN)
        or any(t in ilac_adi for t in _CESITLI_URINER_DULOKSETIN_TICARI)
    )

    detaylar = {
        'alt_grup': 'URINER',
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin_madde,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
        'cinsiyet': cinsiyet,
        'tip': ('ANTIMUSKARINIK' if is_antimuskarinik else
                'BETA3' if is_mirabegron else
                'DULOKSETIN' if is_duloksetin else 'BILINMEYEN'),
    }

    UZMAN_BRANSLAR = (
        'NOROLOJI', 'NÖROLOJI', 'NÖROLOJİ',
        'FIZIK TEDAVI', 'FİZİK TEDAVİ', 'FTR', 'FİZYOTERAPİ',
        'UROLOJI', 'ÜROLOJI', 'ÜROLOJİ',
        'PEDIATRI', 'PEDİATRİ', 'COCUK SAGLIGI', 'ÇOCUK SAĞLIĞI',
        'GERIATRI', 'GERİATRİ',
        'KADIN HASTALIKLARI', 'KADIN-DOGUM', 'KADIN DOĞUM', 'KADIN HAST',
        'JINEKOLOJI', 'JİNEKOLOJİ',
    )
    # Duloksetin için Pediatri YOK
    UZMAN_DULOKSETIN = tuple(
        b for b in UZMAN_BRANSLAR
        if 'PEDIATRI' not in b and 'PEDİATRİ' not in b
        and 'COCUK' not in b and 'ÇOCUK' not in b
    )

    is_uzman_brans = any(b in doktor_brans for b in UZMAN_BRANSLAR)

    # ── 1) Kombi yasağı: antimuskarinik + antimuskarinik (Mirabegron hariç) ──
    if is_antimuskarinik:
        kombi_eslesen = []
        for e in _CESITLI_URINER_ANTIMUSKARINIK_ETKEN:
            if e in diger_arama and e not in arama:
                kombi_eslesen.append(e)
        for t in _CESITLI_URINER_ANTIMUSKARINIK_TICARI:
            if t in diger_arama and t not in ilac_adi:
                kombi_eslesen.append(t)
        if kombi_eslesen:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj=(f'Antimuskarinik kombinasyon — aynı reçetede başka '
                       f'antimuskarinik var: {", ".join(set(kombi_eslesen))}'),
                detaylar={**detaylar, 'kombi_yasagi': True,
                          'kombi_eslesen': sorted(set(kombi_eslesen))},
                uyari=('SUT M.45: Antimuskarinikler birlikte ödenmez '
                       '(Mirabegron bu yasak DIŞINDA)'),
                sut_kurali=sut_kurali,
                aranan_ibare='Aynı reçetede başka antimuskarinik (kombi yasağı)',
            )

    # ── 2) Duloksetin özel kontrolü ──
    if is_duloksetin:
        if not rapor_kodu:
            # Raporsuz Duloksetin — depresyon/anksiyete kapsamında olabilir.
            # SUT M.45 kapsamında üriner için RAPOR ZORUNLU; raporsuz ise
            # bu buton kapsamı değil → ŞÜPHELİ (psikiyatri butonu kontrol etsin)
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=('Duloksetin RAPORSUZ — büyük olasılıkla depresyon/'
                       'anksiyete endikasyonu (SUT 4.2.2). Üriner endikasyon '
                       'için M.45 rapor şart.'),
                detaylar={**detaylar, 'endikasyon': 'belirsiz'},
                uyari=('Duloksetin için PSİKİYATRİ butonu daha doğru kontrol '
                       'eder; üriner endikasyonda bu satır ŞÜPHELİ kalır'),
                sut_kurali=sut_kurali,
                aranan_ibare='Duloksetin üriner endikasyonu (rapor şart)',
            )

        ml = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        sui_var = (
            ('stres' in ml and ('inkontinan' in ml or 'sui' in ml
                                  or 'üriner' in ml or 'uriner' in ml))
            or ('mikst' in ml and 'inkontinan' in ml)
            or ('mixed' in ml and ('incont' in ml or 'urinary' in ml))
        )
        kadin_kesin = cinsiyet in ('K', 'KADIN', 'KADİN', 'F', 'FEMALE')

        if not kadin_kesin:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Duloksetin raporlu (rap.kod {rapor_kodu}) — '
                       f'cinsiyet "{cinsiyet or "bilinmiyor"}" '
                       '(üriner endikasyon yalnız erişkin KADIN)'),
                detaylar={**detaylar, 'sui_var': sui_var},
                uyari=('Duloksetin üriner endikasyonda yalnız erişkin '
                       'KADIN + stres SUI / mikst SUI'),
                sut_kurali=sut_kurali,
                aranan_ibare='Cinsiyet=Kadın + stres üriner inkontinans',
            )

        if not sui_var:
            return KontrolRaporu(
                sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                mesaj=(f'Duloksetin raporlu (rap.kod {rapor_kodu}) — kadın '
                       'hasta ama stres SUI / mikst SUI ibaresi raporda '
                       'bulunamadı (depresyon olabilir)'),
                detaylar={**detaylar, 'sui_var': False},
                uyari='Üriner endikasyon için raporda STRES SUI / MİKST SUI olmalı',
                sut_kurali=sut_kurali,
                aranan_ibare='stres üriner inkontinans / mikst SUI',
            )

        if any(b in doktor_brans for b in UZMAN_DULOKSETIN):
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'Duloksetin raporlu (rap.kod {rapor_kodu}) — kadın + '
                       f'stres SUI + uzman branş: {doktor_brans}'),
                detaylar=detaylar,
                sut_kurali=sut_kurali,
                aranan_ibare='Kadın + stres SUI + uzman branş',
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Duloksetin raporlu (rap.kod {rapor_kodu}) — kadın + '
                   'stres SUI; uzman branşa rapor dayanağıyla yazılabilir'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Duloksetin SUI + rapor varlığı',
        )

    # ── 3) Antimuskarinik / Mirabegron ──
    if is_antimuskarinik or is_mirabegron:
        if not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='Üriner inkontinans ilacı RAPORSUZ — uzman raporu zorunlu',
                detaylar=detaylar,
                uyari=('Nöroloji/FTR/Üroloji/Pediatri/Geriatri/Kadın-Doğum '
                       'uzman hekim raporu gerekli'),
                sut_kurali=sut_kurali,
                aranan_ibare='Uzman hekim raporu (zorunlu)',
            )

        if is_uzman_brans:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'Üriner inkontinans ilacı raporlu (rap.kod '
                       f'{rapor_kodu}) — uzman branş: {doktor_brans}'),
                detaylar=detaylar,
                sut_kurali=sut_kurali,
                aranan_ibare='Uzman branş + rapor',
            )

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Üriner inkontinans ilacı raporlu (rap.kod {rapor_kodu})'
                   ' — uzman branş raporuna dayanılarak diğer uzman hekim '
                   'yazabilir'),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Uzman branş raporuna dayanılarak diğer uzm hekim',
        )

    return KontrolRaporu(
        sonuc=KontrolSonucu.ATLANDI,
        mesaj='Üriner inkontinans kapsamında değil',
        detaylar=detaylar,
        sut_kurali=sut_kurali,
    )


def kontrol_cesitli_suni_gozyasi(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F Madde 2 — Suni gözyaşı (keratitis sicca / kuru göz).

    Kurallar:
      - Göz Hastalıkları uzm. raporsuz/raporlu → UYGUN
      - 1 yıl göz uzm. raporu + diğer uzm hekim → UYGUN
      - Aile hekimi raporsuz + ayda EN FAZLA 1 KUTU → UYGUN
      - Diğer (uzm raporsuz + aile hek değil) → UYGUN DEĞİL
      Doz (günde max 7 damla) Medula tarafından kontrol edilir.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    kurum_adi = (ilac_sonuc.get('kurum_adi') or '').upper()
    tesis_kodu = str(ilac_sonuc.get('tesis_kodu') or '').strip()

    kutu_raw = ilac_sonuc.get('kutu_sayisi')
    if kutu_raw is None:
        kutu_raw = ilac_sonuc.get('miktar', '')
    try:
        kutu = float(str(kutu_raw).replace(',', '.')) \
            if str(kutu_raw).strip() else 0.0
    except (ValueError, TypeError):
        kutu = 0.0

    sut_kurali = 'SUT EK-4/F Madde 2 — Suni gözyaşı (keratitis sicca)'
    detaylar = {
        'alt_grup': 'GOZYASI',
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin_madde,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
        'kutu': kutu,
    }

    is_goz_uzmani = (
        'GOZ HAST' in doktor_brans or 'GÖZ HAST' in doktor_brans
        or 'OFTALMOLOJI' in doktor_brans or 'OFTALMOLOJİ' in doktor_brans
        or doktor_brans.startswith('GÖZ') or doktor_brans.startswith('GOZ')
    )
    aile_hekimi, yetki_kaynagi = _cesitli_aile_hekimi_tespit(
        doktor_brans, kurum_adi, tesis_kodu)
    detaylar['aile_hekimi'] = aile_hekimi
    detaylar['is_goz_uzmani'] = is_goz_uzmani
    detaylar['yetki_kaynagi'] = yetki_kaynagi

    # Göz uzmanı yazmış → her durumda UYGUN
    if is_goz_uzmani:
        rap_str = f' (rap.kod {rapor_kodu})' if rapor_kodu else ' (raporsuz)'
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f'Suni gözyaşı — Göz Hastalıkları uzmanı{rap_str}',
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Göz Hastalıkları uzmanı',
        )

    # Aile hekimi raporsuz + ≤1 kutu
    if aile_hekimi and not rapor_kodu:
        if kutu <= 1:
            kutu_str = f'{kutu:g}' if kutu else '≤1'
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN,
                mesaj=(f'Suni gözyaşı — aile hekimi raporsuz '
                       f'({yetki_kaynagi}) + {kutu_str} kutu '
                       '(SUT M.2: ayda 1 kutu sınırı)'),
                detaylar=detaylar,
                sut_kurali=sut_kurali,
                aranan_ibare='Aile hekimi + ayda ≤1 kutu',
                bulunan_metin=yetki_kaynagi,
            )
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'Suni gözyaşı — aile hekimi raporsuz {kutu:g} kutu '
                   'yazmış (SUT sınırı: ayda 1 kutu)'),
            detaylar=detaylar,
            uyari=('Aile hekimi raporsuz suni gözyaşı ayda 1 kutu — '
                   'fazlası için göz uzm raporu şart'),
            sut_kurali=sut_kurali,
            aranan_ibare='Aile hekimi ≤1 kutu sınırı',
        )

    # Diğer uzm/hekim raporlu → 1 yıl göz uzm raporuna dayanır
    if rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'Suni gözyaşı raporlu (rap.kod {rapor_kodu}) — '
                   '1 yıl göz uzm. raporuna dayanılarak yazılabilir '
                   '(doz max 7 damla/gün — Medula kontrol)'),
            detaylar=detaylar,
            uyari='Doz kontrolü Medula tarafından yapılır',
            sut_kurali=sut_kurali,
            aranan_ibare='1 yıl göz uzm raporu',
        )

    # Raporsuz + göz uzm değil + aile hekimi değil
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN_DEGIL,
        mesaj=(f'Suni gözyaşı RAPORSUZ — branş "{doktor_brans or "bilinmiyor"}"'
               ' (SUT M.2: göz uzm yazabilir / 1 yıl rapor / aile hek + 1 kutu)'),
        detaylar=detaylar,
        uyari='Göz uzm yazabilir VEYA 1 yıl göz raporu VEYA aile hek + 1 kutu',
        sut_kurali=sut_kurali,
        aranan_ibare='Göz uzm VEYA göz raporu VEYA aile hekimi',
    )


def kontrol_cesitli_bph_alfa_bloker(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT — Benign prostat hiperplazisi (BPH) α-blokerleri.

    Kapsam: Alfuzosin, Tamsulosin, Terazosin, Doksazosin, Silodosin

    Kurallar:
      - Üroloji uzm hekim → UYGUN
      - Üroloji uzm 1 yıl raporuna dayanılarak tüm hekimler → UYGUN
      - KOMBİNASYON YASAĞI: α-blokerler birlikte ödenmez
        İSTİSNA: Hipertansiyon eşlik ediyorsa kombi serbest
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    doktor_brans = (ilac_sonuc.get('doktor_uzmanligi') or '').upper()
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_metin = ' '.join(teshisler).upper() if teshisler else ''

    diger_etkenler = ilac_sonuc.get('diger_etken_maddeler') or []
    diger_ilac_adlari = ilac_sonuc.get('diger_ilac_adlari') or []
    diger_arama = ' '.join(
        [str(x).upper() for x in (diger_etkenler + diger_ilac_adlari)])

    tum_metin = _tum_metinleri_birlesir(ilac_sonuc) or ''
    sut_kurali = 'SUT — BPH α-blokerleri (Alfuzosin/Tamsulosin/Terazosin/Doksazosin/Silodosin)'

    detaylar = {
        'alt_grup': 'BPH',
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin_madde,
        'rapor_kodu': rapor_kodu,
        'doktor_brans': doktor_brans,
    }

    is_uroloji = (
        'UROLOJI' in doktor_brans or 'ÜROLOJI' in doktor_brans
        or 'ÜROLOJİ' in doktor_brans
    )
    detaylar['is_uroloji'] = is_uroloji

    # ── Hipertansiyon eşlik kontrolü (ICD I10-I15 veya teşhis metni) ──
    ml = (tum_metin + ' ' + teshis_metin).replace('İ', 'i').replace('I', 'ı').lower()
    ht_var = (
        'hipertans' in ml or 'hypertan' in ml
        or any(t in teshis_metin for t in ('I10', 'I11', 'I12', 'I13', 'I14', 'I15'))
    )
    detaylar['ht_var'] = ht_var

    # ── Kombi yasağı kontrolü (HT istisnası) ──
    arama = ilac_adi + ' ' + etkin_madde
    kombi_eslesen = []
    for e in _CESITLI_BPH_ALFA_ETKEN:
        if e in diger_arama and e not in arama:
            kombi_eslesen.append(e)
    for t in _CESITLI_BPH_TICARI:
        if t in diger_arama and t not in ilac_adi:
            kombi_eslesen.append(t)

    if kombi_eslesen and not ht_var:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f'BPH α-bloker kombinasyon — aynı reçetede başka α-bloker: '
                   f'{", ".join(set(kombi_eslesen))} (HT eşlik etmiyor)'),
            detaylar={**detaylar, 'kombi_yasagi': True,
                      'kombi_eslesen': sorted(set(kombi_eslesen))},
            uyari=('SUT: BPH α-blokerleri birlikte ödenmez. İstisna: '
                   'Hipertansiyon eşlik ediyorsa kombi serbest.'),
            sut_kurali=sut_kurali,
            aranan_ibare='Hipertansiyon teşhisi (kombi istisnası)',
        )

    if kombi_eslesen and ht_var:
        # HT eşlik → kombi serbest, normal akışa devam
        detaylar['kombi_ht_istisna'] = True

    # ── Karar ──
    if is_uroloji:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'BPH α-bloker — Üroloji uzm hekim '
                   f'(rap.kod {rapor_kodu or "yok"})'
                   + (' [HT eşlik — kombi serbest]' if (kombi_eslesen and ht_var)
                      else '')),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Üroloji uzmanı',
        )

    if rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f'BPH α-bloker raporlu (rap.kod {rapor_kodu}) — '
                   'üroloji uzm raporuna dayanılarak tüm hekimler yazabilir'
                   + (' [HT eşlik]' if (kombi_eslesen and ht_var) else '')),
            detaylar=detaylar,
            sut_kurali=sut_kurali,
            aranan_ibare='Üroloji 1 yıl raporu',
        )

    # Raporsuz + üroloji değil → şüpheli (Medula şart kontrolü yapar)
    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=(f'BPH α-bloker raporsuz — branş "{doktor_brans or "bilinmiyor"}" '
               '(üroloji değil, rapor yok)'),
        detaylar=detaylar,
        uyari=('SUT: BPH α-blokerleri için Üroloji uzm hekim VEYA '
               'üroloji 1 yıl raporu gerekli'),
        sut_kurali=sut_kurali,
        aranan_ibare='Üroloji uzmanı VEYA üroloji raporu',
    )


def kontrol_cesitli(ilac_sonuc: Dict) -> KontrolRaporu:
    """ÇEŞİTLİ İLAÇLAR dispatcher — alt grubu tespit edip ilgili kontrole
    yönlendirir. 3 alt grup:
      URINER  → kontrol_cesitli_madde_45_uriner
      GOZYASI → kontrol_cesitli_suni_gozyasi
      BPH     → kontrol_cesitli_bph_alfa_bloker
    """
    alt_grup = _cesitli_alt_grup_tespit(
        ilac_sonuc.get('ilac_adi', '') or '',
        ilac_sonuc.get('etkin_madde', '') or '',
        ilac_sonuc.get('atc_kodu', '') or '',
    )
    if alt_grup == 'URINER':
        return kontrol_cesitli_madde_45_uriner(ilac_sonuc)
    if alt_grup == 'GOZYASI':
        return kontrol_cesitli_suni_gozyasi(ilac_sonuc)
    if alt_grup == 'BPH':
        return kontrol_cesitli_bph_alfa_bloker(ilac_sonuc)
    return KontrolRaporu(
        sonuc=KontrolSonucu.ATLANDI,
        mesaj='ÇEŞİTLİ kapsamında olmayan ilaç',
        detaylar={'alt_grup': 'NONE'},
        sut_kurali='ÇEŞİTLİ İLAÇLAR (M.45 / M.2 / BPH α-bloker)',
    )
