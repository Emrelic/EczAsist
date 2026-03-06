# -*- coding: utf-8 -*-
"""
SUT Kontrolleri

4 SUT kuralı için algoritmik ilaç kontrolleri:
1. Kombine Antihipertansifler (4.2.12.B) - Monoterapi ibaresi
2. DPP-4 / SGLT-2 / GLP-1 İnhibitörleri (4.2.38) - Glisemik kontrol
3. Klopidogrel / Prasugrel / Tikagrelor (4.2.15) - Anjiografi tarihi
4. Statinler (4.2.28.A) - LDL düzeyi
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
    '4.2.28': 'STATIN',
    '4.2.28.A': 'STATIN',
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

    # 3. SUT veritabanlarından ara (ilaç adı ile)
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

    return None


# ═══════════════════════════════════════════════════════════════════════
# SUT Kontrol Fonksiyonları (Mesaj metninden algoritmik kontrol)
# ═══════════════════════════════════════════════════════════════════════

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
    mesaj = ilac_sonuc.get('mesaj_metni', '')

    # Mesaj metninde monoterapi ibaresini ara
    monoterapi_kelimeleri = ['monoterapi']
    kontrol_altina = ['kontrol altına alına']
    kan_basinci = ['kan basıncı']

    bulundu = False
    if mesaj:
        mesaj_lower = mesaj.lower()
        # "monoterapi" kelimesi yeterli bir gösterge
        if 'monoterapi' in mesaj_lower:
            bulundu = True
        # veya "tek ilaç tedavisi" ibaresi
        elif 'tek ilaç' in mesaj_lower and 'yeter' in mesaj_lower:
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
    mesaj = ilac_sonuc.get('mesaj_metni', '')

    bulundu = False
    if mesaj:
        mesaj_lower = mesaj.lower()
        # metformin VE sülfonilüre ibareleri
        metformin_var = 'metformin' in mesaj_lower
        sulfonilure_var = 'sülfonilüre' in mesaj_lower or 'sulfonilurea' in mesaj_lower or 'sülfonilure' in mesaj_lower
        glisemik_var = 'glisemik' in mesaj_lower or 'kan şekeri' in mesaj_lower

        if metformin_var and (sulfonilure_var or glisemik_var):
            bulundu = True

    if bulundu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj='SUT kuralı mesajda mevcut: Metformin/sülfonilüre glisemik kontrol ibaresi',
            detaylar={'aranan': 'metformin + sülfonilüre + glisemik', 'bulundu': True},
            uyari='Raporda "metformin ve sülfonilürelerin yeterli dozunda glisemik kontrol sağlanamadığı" ibaresi kontrol edilmeli'
        )
    else:
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
    mesaj = ilac_sonuc.get('mesaj_metni', '')

    bulundu = False
    tarih_bilgisi = None
    if mesaj:
        mesaj_lower = mesaj.lower()
        anjiografi_var = 'anjio' in mesaj_lower or 'angiografi' in mesaj_lower or 'koroner' in mesaj_lower
        stent_var = 'stent' in mesaj_lower
        akut_koroner = 'akut koroner' in mesaj_lower

        if anjiografi_var or stent_var or akut_koroner:
            bulundu = True

            # Tarih formatı ara (GG.AA.YYYY veya GG/AA/YYYY)
            tarih_match = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', mesaj)
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
    mesaj = ilac_sonuc.get('mesaj_metni', '')

    bulundu = False
    ldl_degeri = None
    if mesaj:
        mesaj_lower = mesaj.lower()
        ldl_var = 'ldl' in mesaj_lower

        if ldl_var:
            bulundu = True

            # LDL değeri ara (sayısal)
            ldl_match = re.findall(r'ldl[^0-9]*(\d+)', mesaj_lower)
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


# ═══════════════════════════════════════════════════════════════════════
# Ana Kontrol Fonksiyonu
# ═══════════════════════════════════════════════════════════════════════

# Kategori -> kontrol fonksiyonu eşleştirme
KATEGORI_KONTROL_FONKSIYONU = {
    'KOMBINE_ANTIHIPERTANSIF': kontrol_kombine_antihipertansif,
    'DIYABET_DPP4_SGLT2': kontrol_diyabet_dpp4_sglt2,
    'KLOPIDOGREL': kontrol_klopidogrel,
    'STATIN': kontrol_statin,
}

KATEGORI_ISIMLERI = {
    'KOMBINE_ANTIHIPERTANSIF': 'Kombine Antihipertansif (4.2.12.B)',
    'DIYABET_DPP4_SGLT2': 'DPP-4/SGLT-2/GLP-1 (4.2.38)',
    'KLOPIDOGREL': 'Klopidogrel/Prasugrel/Tikagrelor (4.2.15)',
    'STATIN': 'Statin (4.2.28.A)',
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
