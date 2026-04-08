# -*- coding: utf-8 -*-
"""
SUT Kontrolleri

5 SUT kuralı için algoritmik ilaç kontrolleri:
1. Kombine Antihipertansifler (4.2.12.B) - Monoterapi ibaresi
2. DPP-4 / SGLT-2 / GLP-1 İnhibitörleri (4.2.38) - Glisemik kontrol
3. Klopidogrel / Prasugrel / Tikagrelor (4.2.15) - Anjiografi tarihi
4. Statinler (4.2.28.A) - LDL düzeyi
5. Fibratlar (4.2.28.B) - Trigliserid düzeyi
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
    '04.08': 'STATIN',                 # Lipid düşürücü (statin veya fibrat)
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
    '14.01': 'ANTIVIRAL',             # Antiviral
    '20.00': 'GENEL_RAPORLU',         # Genel raporlu
    '20.02': 'GENEL_RAPORLU',
    '06.06': 'GIS',                    # GİS
    '03.00': 'POTASYUM_SITRAT',        # Üroloji/Nefroloji raporlu
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
    """Türkçe karakterleri ASCII karşılıklarına çevir + lowercase.
    İ→i, ı→i, Ü→u, ü→u, Ö→o, ö→o, Ş→s, ş→s, Ç→c, ç→c, Ğ→g, ğ→g"""
    t = metin
    for tr_char, ascii_char in [('İ','i'),('ı','i'),('Ü','u'),('ü','u'),
                                 ('Ö','o'),('ö','o'),('Ş','s'),('ş','s'),
                                 ('Ç','c'),('ç','c'),('Ğ','g'),('ğ','g'),
                                 ('I','i')]:
        t = t.replace(tr_char, ascii_char)
    return t.lower()


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


def kontrol_kombine_antihipertansif(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.12.B - Kombine Antihipertansif Kontrol

    Raporda "monoterapi ile hasta kan basıncının yeteri kadar
    kontrol altına alınamadığı" ibaresi olmalı.
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    if tum_metin:
        metin_lower = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        # "monoterapi" kelimesi yeterli bir gösterge
        if 'monoterapi' in metin_lower:
            bulundu = True
        # veya "tek ilaç tedavisi" ibaresi
        elif 'tek ilaç' in metin_lower and 'yeter' in metin_lower:
            bulundu = True
        # veya "kan basıncı" + "kontrol" ibaresi
        elif 'kan basıncı' in metin_lower and 'kontrol' in metin_lower:
            bulundu = True

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='SUT kuralı mesajda mevcut: Monoterapi ibaresi bulundu',
            detaylar={'aranan': 'monoterapi', 'bulundu': True},
            uyari='Raporda "monoterapi ile yeterli kontrol sağlanamadığı" ibaresi kontrol edilmeli'
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Monoterapi ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'monoterapi', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: Monoterapi ibaresi raporda olmalı'
        )


def kontrol_diyabet_dpp4_sglt2(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.38 - DPP-4 / SGLT-2 / GLP-1 Kontrol

    Raporda "metformin ve sülfonilürelerin yeterli/maksimum dozlarında
    yeterli glisemik kontrol/yanıt sağlanamaması" ibaresi olmalı.
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    if tum_metin:
        metformin_var = _turkce_ara(tum_metin, 'metformin')
        sulfonilure_var = _turkce_ara(tum_metin, 'sülfonilüre')
        glisemik_var = _turkce_ara(tum_metin, 'glisemik') or _turkce_ara(tum_metin, 'kan şekeri') or 'hba1c' in tum_metin.lower()
        kontrol_var = _turkce_ara(tum_metin, 'kontrol') or _turkce_ara(tum_metin, 'yeterli') or _turkce_ara(tum_metin, 'sağlana')

        if metformin_var and (sulfonilure_var or glisemik_var):
            bulundu = True
        elif glisemik_var and kontrol_var:
            bulundu = True
        elif metformin_var and kontrol_var:
            bulundu = True

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='SUT kuralı mesajda mevcut: Metformin/sülfonilüre glisemik kontrol ibaresi',
            detaylar={'aranan': 'metformin + sülfonilüre + glisemik', 'bulundu': True},
            uyari='Raporda "metformin ve sülfonilürelerin yeterli dozunda glisemik kontrol sağlanamadığı" ibaresi kontrol edilmeli'
        )
    else:
        # Raporsuz SGLT2/DPP4/GLP1 ilaçları → rapor zorunlu uyarısı
        ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
        rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
        sglt2_dpp4 = any(k in ilac_adi for k in ['SGLT2', 'DPP4', 'DPP-4', 'GLP-1', 'GLP1',
            'JARDIANCE', 'FORZIGA', 'INVOKANA', 'STEGLATRO',
            'JANUVIA', 'GALVUS', 'ONGLYZA', 'TRAJENTA', 'NESINA',
            'OZEMPIC', 'TRULICITY', 'VICTOZA', 'BYETTA'])
        metformin = 'METFORMIN' in ilac_adi or 'GLUKOFEN' in ilac_adi or 'DIAFORMIN' in ilac_adi or 'GLIFOR' in ilac_adi

        if sglt2_dpp4 and not rapor_kodu:
            return KontrolRaporu(
                sonuc=KontrolSonucu.UYGUN_DEGIL,
                mesaj='SGLT2/DPP4/GLP1 ilacı RAPORSUZ yazılmış! Rapor ZORUNLU',
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

    Raporda anjiografi tarihi bulunmalı (belirli süre içinde yapılmış olmalı).
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    tarih_bilgisi = None
    if tum_metin:
        metin_lower = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        anjiografi_var = 'anjio' in metin_lower or 'angiografi' in metin_lower or 'koroner' in metin_lower
        stent_var = 'stent' in metin_lower
        akut_koroner = 'akut koroner' in metin_lower
        bypass_var = 'bypass' in metin_lower or 'kabg' in metin_lower
        perkutan_var = 'perkütan' in metin_lower or 'perkutan' in metin_lower

        if anjiografi_var or stent_var or akut_koroner or bypass_var or perkutan_var:
            bulundu = True

            # Tarih formatı ara (GG.AA.YYYY veya GG/AA/YYYY)
            tarih_match = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', tum_metin)
            if tarih_match:
                tarih_bilgisi = tarih_match

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='SUT kuralı mesajda mevcut: Anjiografi/stent/AKS ibaresi',
            detaylar={
                'aranan': 'anjiografi/stent/akut koroner',
                'bulundu': True,
                'tarihler': tarih_bilgisi
            },
            uyari='Raporda anjiografi tarihi kontrol edilmeli'
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Anjiografi/stent ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'anjiografi/stent', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: Anjiografi tarihi raporda olmalı'
        )


def kontrol_statin(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.28.A - Statin Kontrol

    Raporda LDL düzeyi belirtilmiş olmalı.
    SUT'a göre LDL eşik değerleri:
    - Genel: LDL >= 130 mg/dL (diyet + egzersiz sonrası)
    - Diyabet/KAH: LDL >= 100 mg/dL
    - Çok yüksek risk: LDL >= 70 mg/dL (bazı durumlar)
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    ldl_degeri = None
    if tum_metin:
        metin_lower = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        ldl_var = 'ldl' in metin_lower
        kolesterol_var = 'kolesterol' in metin_lower

        if ldl_var or kolesterol_var:
            bulundu = True

            # LDL değeri ara (sayısal)
            ldl_match = re.findall(r'ldl[^0-9]*(\d+)', metin_lower)
            if ldl_match:
                try:
                    ldl_degeri = int(ldl_match[0])
                except ValueError:
                    pass

    if bulundu:
        detay = {
            'aranan': 'LDL düzeyi',
            'bulundu': True,
            'ldl_degeri': ldl_degeri
        }
        mesaj_text = f'SUT kuralı mesajda mevcut: LDL ibaresi (değer: {ldl_degeri})' if ldl_degeri else 'SUT kuralı mesajda mevcut: LDL ibaresi'

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=mesaj_text,
            detaylar=detay,
            uyari='Raporda LDL düzeyi kontrol edilmeli (eşik: 130/100/70 mg/dL)'
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='LDL ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'LDL', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: LDL düzeyi raporda olmalı'
        )


def kontrol_fibrat(ilac_sonuc: Dict) -> KontrolRaporu:
    """
    SUT 4.2.28.B - Fibrat Kontrol

    Raporda trigliserid düzeyi belirtilmiş olmalı.
    SUT'a göre:
    - Trigliserid >= 500 mg/dL VEYA
    - Trigliserid >= 200 mg/dL + DM/KAH/PAH/MI/İnme
    """
    tum_metin = _tum_metinleri_birlesir(ilac_sonuc)

    bulundu = False
    tg_degeri = None
    if tum_metin:
        metin_lower = tum_metin.replace('İ', 'i').replace('I', 'ı').lower()
        tg_var = 'trigliserid' in metin_lower or 'trigliserit' in metin_lower or 'tg ' in metin_lower or 'tg:' in metin_lower

        if tg_var:
            bulundu = True

            # TG değeri ara (sayısal)
            tg_match = re.findall(r'(?:trigliserid|trigliserit|tg)[^0-9]*(\d+)', metin_lower)
            if tg_match:
                try:
                    tg_degeri = int(tg_match[0])
                except ValueError:
                    pass

    if bulundu:
        detay = {
            'aranan': 'Trigliserid düzeyi',
            'bulundu': True,
            'tg_degeri': tg_degeri
        }
        mesaj_text = f'SUT kuralı mesajda mevcut: Trigliserid ibaresi (değer: {tg_degeri})' if tg_degeri else 'SUT kuralı mesajda mevcut: Trigliserid ibaresi'

        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=mesaj_text,
            detaylar=detay,
            uyari='Raporda trigliserid düzeyi kontrol edilmeli (eşik: 500 veya 200+risk mg/dL)'
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='Trigliserid ibaresi mesaj metninde bulunamadı',
            detaylar={'aranan': 'trigliserid', 'bulundu': False},
            uyari='RAPOR KONTROLÜ GEREKLİ: Trigliserid düzeyi raporda olmalı'
        )


# ═══════════════════════════════════════════════════════════════════════
# Ana Kontrol Fonksiyonu
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# YENİ KONTROL FONKSİYONLARI (2026-04-05 eklendi)
# ═══════════════════════════════════════════════════════════════════════

def kontrol_yoak(ilac_sonuc: Dict) -> KontrolRaporu:
    """YOAK (4.2.15.D) - Varfarin öncesi + INR koşulu veya istisna durumlar"""
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()

    # Rapor var mı?
    if not metin:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok - kontrol edilemedi")

    # Varfarin + INR koşulu
    varfarin = bool(re.search(r'varfarin|kumadin|coumadin', metin_lower))
    inr = bool(re.search(r'INR|inr', metin))
    af = bool(re.search(r'atriyal\s*fibrilasyon|AF\b|atrial\s*fib', metin, re.IGNORECASE))
    dvt_pe = bool(re.search(r'DVT|derin\s*ven|pulmoner\s*emboli|PE\b|tromboz', metin, re.IGNORECASE))
    kanser = bool(re.search(r'kanser|maligni|tümör|onkoloji', metin_lower))

    if varfarin and inr:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Varfarin + INR bilgisi raporda mevcut")
    if kanser or dvt_pe:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "İstisna durum (kanser/DVT/PE) - varfarin şartı aranmaz",
                             uyari="Kanser/DVT/PE nedeniyle doğrudan YOAK kullanımı")
    if af:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "AF tanısı var ama varfarin/INR bilgisi raporda bulunamadı",
                             uyari="Varfarin denenmiş mi kontrol et")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "YOAK endikasyonu tespit edilemedi")


def kontrol_ivabradin(ilac_sonuc: Dict) -> KontrolRaporu:
    """İvabradin (4.2.15.C) / Ranolazin (4.2.15.F) / Eplerenon
    İvabradin: NYHA II-IV + sinüs ritmi VEYA beta blokör intoleransı VEYA EF≤%45
    Ranolazin: Kronik stabil angina + semptomatik tedavi
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


def kontrol_psikiyatri(ilac_sonuc: Dict) -> KontrolRaporu:
    """Psikiyatri ilaçları (4.2.2) - Uzman raporu kontrolü"""
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()

    if not metin:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok")

    # Uzman raporu var mı?
    psikiyatri = bool(re.search(r'psikiyatri|ruh\s*sa.l', metin_lower))
    noroloji = bool(re.search(r'n.roloji|n\u00f6roloji', metin_lower))
    geriatri = bool(re.search(r'geriatri', metin_lower))

    if psikiyatri or noroloji or geriatri:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Uzman raporu mevcut (psikiyatri/nöroloji/geriatri)")
    # Tanı kontrol
    depresyon = bool(re.search(r'depres|anksiyete|panik|OKB|fobia|bipolar|.izofreni', metin_lower))
    if depresyon:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Psikiyatrik tanı raporda mevcut",
                             uyari="Uzman adı kontrol edilmeli")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Psikiyatri uzman raporu/tanısı tespit edilemedi")


def kontrol_solunum(ilac_sonuc: Dict) -> KontrolRaporu:
    """Solunum ilaçları (4.2.9/4.2.24.B) - Astım/KOAH raporu"""
    metin = _tum_metinleri_birlesir(ilac_sonuc)
    metin_lower = metin.replace('İ', 'i').replace('I', 'ı').lower()
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()

    if not metin:
        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                             "Rapor/mesaj metni yok")

    astim = bool(re.search(r'ast.m|asthma', metin_lower))
    koah = bool(re.search(r'KOAH|COPD|kronik\s*obstr', metin, re.IGNORECASE))
    gogus = bool(re.search(r'g..[gsş]\s*hastal|pulmonoloji', metin_lower))

    # Üçlü kombinasyon (TRELEGY vb.) - ek koşullar
    uclu = bool(re.search(r'TRELEGY|TRIMBOW|ENERZAIR', ilac_adi))
    if uclu:
        ics_laba_oncesi = bool(re.search(r'ICS.*LABA|IKS.*LABA|inhaler.*kortikosteroid', metin_lower))
        atak = bool(re.search(r'atak|alevlenme|eksaserbasyon', metin_lower))
        if ics_laba_oncesi or atak:
            return KontrolRaporu(KontrolSonucu.UYGUN,
                                 "Üçlü kombinasyon - ICS+LABA öncesi/atak öyküsü mevcut")
        if koah:
            return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                                 "KOAH tanısı var ama ICS+LABA öncesi tedavi bilgisi eksik",
                                 uyari="3 ay ICS+LABA kullanımı kontrol edilmeli")

    if astim or koah:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"{'Astım' if astim else 'KOAH'} tanısı raporda mevcut")
    if gogus:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             "Göğüs hastalıkları uzman raporu mevcut")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Astım/KOAH tanısı veya göğüs hastalıkları raporu tespit edilemedi")


def kontrol_genel_raporlu(ilac_sonuc: Dict) -> KontrolRaporu:
    """Genel raporlu ilaçlar (20.00/20.02) - Rapor var mı kontrolü"""
    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')
    if rapor_kodu:
        return KontrolRaporu(KontrolSonucu.UYGUN,
                             f"Rapor kodu mevcut ({rapor_kodu})",
                             uyari="Rapor içeriği manuel kontrol edilmeli")
    return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI,
                         "Rapor kodu bulunamadı")


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
    'RANOLAZIN': kontrol_ivabradin,  # Benzer koşullar (BB intoleransı)
    'RECETE_TURU_KIRMIZI': kontrol_recete_turu_kirmizi,
    'RECETE_TURU_YESIL': kontrol_recete_turu_yesil,
    'TRIMETAZIDIN': kontrol_trimetazidin,
    'DMAH': kontrol_dmah,
    'KADIN_HORMON': kontrol_kadin_hormon,
    'ANTIBIYOTIK_FLOROKINOLON': kontrol_antibiyotik_florokinolon,
    'RAPORSUZ_BILGILENDIRME': kontrol_raporsuz_bilgilendirme,
    'MONO_ANTIHIPERTANSIF': kontrol_mono_antihipertansif,
    'POTASYUM_SITRAT': kontrol_potasyum_sitrat,
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
