# -*- coding: utf-8 -*-
"""Başlangıç raporu bulucu — genel altyapı (tüm SUT kontrolleri kullanır).

Mantık (kullanıcı kararı 2026-05-25):
    Hasta VEMLIDY kullanıyorsa, VEMLIDY/etken-eşi ilacı ilk aldığı tarihteki
    rapor BAŞLANGIÇ raporu sayılır. Bu rapor metni alınıp aktif kontrol
    modülünün BAŞLANGIÇ kriterleriyle yeniden değerlendirilir.

Veri kaynakları (sırasıyla):
    1. Botanik EOS — `hasta_ilk_recete_etken_bazli()` ile en eski reçete +
       o reçetenin SecilenRapor üzerinden bağlı RaporAna metni
       (RaporAnaAciklamalar). Tek meşru "ilk reçete tarihi" kaynağı budur.
    2. hasta_rapor_gecmisi.db (Medula taramasından çekilmiş raporlar) —
       eğer EOS'taki RaporAnaAciklamalar boş ise, aynı rapor_takip_no için
       detay_metni (Medula raporundan).
    3. Yerel `oturum_raporlari.db` — şimdilik kullanılmıyor (proje DB
       şemasında reçete kalem tablosu yok); ileride satılan ilaç tablosu
       eklenirse buraya entegre edilir.

Kullanıcı kuralı (feedback_baska_eczane_ke):
    EOS'ta hiç reçete yoksa → hasta ilacı başka eczaneden başlamış olabilir,
    bu durum "BULUNAMADI" olarak döner — örtük kabul yapılmaz.

Modüle özel keyword listeleri:
    - HEPATIT_B  → HBV_ORAL_ETKEN + HBV_ORAL_TICARI
    - HEPATIT_C  → HCV_DAA_ETKEN + HCV_DAA_TICARI + PEG_IFN_ETKEN
    - HEPATIT_D  → HBV_ORAL + PEG_IFN
    - Diyabet vs → ileride eklenecek
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# AŞAMA 1 — AKTİF RAPOR LAFIZ PARSE (en güvenilir kaynak)
# ═════════════════════════════════════════════════════════════════════════
#
# Klinik pratikte devam raporları neredeyse her zaman başlangıç raporunun
# takip numarasını referans verir. Örnek (İSKAN ERDOĞMUŞ, 2026-05-25):
#   "17.09.2018 tarihli 2017909867 takip no raporuna istinaden
#    devam raporu olarak düzenlenmiştir"
# Bu lafzı yakalayıp DB'den (Medula taramasından gelen) eski rapor metnini
# direkt çekeriz — EOS sorgusundan çok daha hızlı + doğrudur (doktor
# kendisi başlangıç raporunu referans veriyor).

# Tarih + 6-12 haneli takip no — Türkçe varyantları
# Yakalanan örnekler:
#   "17.09.2018 tarihli 2017909867 takip no"
#   "17/09/2018 tarihli 2017909867 takip nolu"
#   "27.08.2018 başlangıç tarihli 2017909867"
_LAFIZ_TAKIP_NO_PATTERNS = (
    # "DD.MM.YYYY tarihli NNNNNN takip no/nolu"
    re.compile(
        r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})\s*tarihli\s+'
        r'(\d{6,12})\s*takip\s*no',
        re.IGNORECASE),
    # "NNNNNN takip no ... DD.MM.YYYY tarihli"
    re.compile(
        r'(\d{6,12})\s*takip\s*no(?:lu)?[^\d]{0,40}?'
        r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
        re.IGNORECASE),
    # "başlangıç raporu (NNNNNN)"
    re.compile(
        r'ba[şs]lang[ıi][cç]\s*rapor(?:[ıu])?\s*[\(:]\s*(\d{6,12})\s*\)?',
        re.IGNORECASE),
)


def aktif_rapordan_baslangic_takip_no_cikar(
    rapor_metni: str,
) -> Optional[Tuple[str, str]]:
    """Aktif rapor metninde başlangıç raporunun takip no'sunu ara.

    Çoklu eşleşmede en eski tarihli (ya da ilk yakalanan) takip no döner.

    Returns:
        (takip_no, tarih_str) — örn ('2017909867', '17.09.2018')
        None — lafzen yakalanmadı
    """
    if not rapor_metni:
        return None
    metin = str(rapor_metni)
    bulunan: List[Tuple[str, str]] = []
    for pat in _LAFIZ_TAKIP_NO_PATTERNS:
        for m in pat.finditer(metin):
            gruplar = m.groups()
            tarih = ''
            takip = ''
            for g in gruplar:
                if not g:
                    continue
                g = g.strip()
                if re.fullmatch(r'\d{6,12}', g):
                    takip = g
                elif re.fullmatch(
                        r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}', g):
                    tarih = g
            if takip:
                bulunan.append((takip, tarih))
    if not bulunan:
        return None
    # En eski tarihli olanı seç — tarih yoksa ilk yakalanan
    def _tarih_sort_key(t: Tuple[str, str]) -> str:
        d = t[1]
        if not d:
            return '9999-99-99'
        # DD.MM.YYYY → YYYY-MM-DD canonical
        parts = re.split(r'[.\-/]', d)
        if len(parts) == 3:
            dd, mm, yy = parts
            if len(yy) == 2:
                yy = '20' + yy if int(yy) < 50 else '19' + yy
            return f'{yy.zfill(4)}-{mm.zfill(2)}-{dd.zfill(2)}'
        return '9999-99-99'
    bulunan.sort(key=_tarih_sort_key)
    return bulunan[0]


def _eos_ilk_recete_getir(hasta_tc: str,
                            urun_keywords: Tuple[str, ...],
                            limit: int = 5) -> List[Dict]:
    """Botanik EOS sorgusu — etken eş keyword listesiyle en eski 5 reçete.

    Bağlantı/yetki hatası → boş liste. CLAUDE.md §2: SADECE SELECT.
    """
    try:
        from botanik_db import get_botanik_db
        db = get_botanik_db()
        if not db.baglan():
            logger.debug('Botanik EOS bağlantısı kurulamadı')
            return []
        return db.hasta_ilk_recete_etken_bazli(
            hasta_tc, urun_keywords, limit=limit)
    except Exception as e:
        logger.warning('EOS başlangıç sorgu hatası: %s', e)
        return []


def _gecmis_db_rapor_metni(rapor_takip_no: str) -> Optional[str]:
    """hasta_rapor_gecmisi.db'den verilen rapor_takip_no için detay_metni.

    EOS'taki RaporAnaAciklamalar boş ise Medula taraması cache'inden
    rapor metnini çek (eczacı 🩺 GEÇMİŞ RAPOR TARA basmışsa dolu olur).
    """
    if not rapor_takip_no:
        return None
    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            hasta_raporlarini_oku, sema_olustur)
        sema_olustur()
        # rapor_takip_no eşleşmesi için tüm raporları çek + filtrele
        # (modul TC bazlı oku, ama biz TC bilmeyebiliriz; bu yüzden
        # tum kayıt için ayrı bir helper yoksa şimdilik atla)
        return None
    except Exception as e:
        logger.debug('hasta_rapor_gecmisi cache okuma hatası: %s', e)
        return None


def _yerel_tablo_yolu_dene(
        hasta_tc: str,
        urun_keywords: Tuple[str, ...],
        aktif_rapor_takip_no: str) -> Optional[Dict]:
    """Aşama 0 — yerel hasta_rapor_gecmisi.db (Medula taraması) tablosunda
    etken keyword'lerle eşleşen EN ESKİ tarihli raporu bul.

    Kullanıcı kararı 2026-05-25: Medula nihai kaynak. Doktorun aktif rapor
    metnindeki "X tarihli NNNN takip no" lafzı (Aşama 1) yanıltıcı olabilir
    çünkü doktor devam raporu içine kendi başlangıç referansını yanlış
    yazabilir. Medula'dan çekilmiş tablo gerçektir.

    Returns:
        None — yerel tabloda hiç eşleşme yok (Medula taraması yapılmamış
                ya da hasta bu etkeni hiç almamış)
        Dict (durum='BULUNDU_TABLO' | 'AKTIF_ZATEN_BASLANGIC')
    """
    if not hasta_tc or not urun_keywords:
        return None
    try:
        from recete_kontrol.rapor_etken_madde_tablosu import hasta_etken_tablo
        tablo = hasta_etken_tablo(hasta_tc)
    except Exception as e:
        logger.warning('Yerel etken tablo okuma hatası: %s', e)
        return None
    if not tablo:
        return None

    # Keyword filtre — büyük harf substring match
    kw_upper = tuple(k.upper() for k in urun_keywords if k)
    eslesen = [
        s for s in tablo
        if s.etken_madde and any(
            kw in s.etken_madde.upper() for kw in kw_upper)
    ]
    if not eslesen:
        return None

    # is_baslangic flag'i zaten etken bazlı en eski tarihi işaretliyor.
    # Filtrelenmiş listede de aynı satır olmalı; yine de yedeğe sort key ile
    # en eski tarihli olanı seç.
    from recete_kontrol.rapor_etken_madde_tablosu import _tarih_sort_key
    en_eski = min(eslesen, key=lambda s: _tarih_sort_key(s.tarih))

    # Aktif rapor ile aynı mı?
    ayni_rapor = bool(
        aktif_rapor_takip_no
        and en_eski.rapor_takip_no
        and str(aktif_rapor_takip_no).strip() == en_eski.rapor_takip_no)
    durum = 'AKTIF_ZATEN_BASLANGIC' if ayni_rapor else 'BULUNDU_TABLO'

    # Metni yerel DB'den oku (etken tablo aciklama'yı kısa tutuyor)
    rapor_metni = ''
    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            takip_no_ile_oku)
        kayit = takip_no_ile_oku(en_eski.rapor_takip_no, hasta_tc=hasta_tc)
        if kayit:
            rapor_metni = kayit.detay_metni or ''
    except Exception as e:
        logger.debug('Yerel rapor metni okuma hatası: %s', e)

    return {
        'rxid': None,
        'recete_tarihi': '',
        'urun_adi': en_eski.etken_madde,
        'atc_kodu': '',
        'rapor_takip_no': en_eski.rapor_takip_no,
        'rapor_no': en_eski.rapor_no,
        'rapor_tarihi': en_eski.tarih,
        'rapor_metni': rapor_metni,
        'aktif_recete_mi': False,
        'ayni_rapor_mi': ayni_rapor,
        'toplam_eski_sayi': len(eslesen),
        'kaynak': 'medula_tablo',
        'durum': durum,
        'lafiz_takip_no': '',
        'lafiz_tarih': '',
        'eski_5_recete': [
            {'tarih': s.tarih, 'urun': s.etken_madde,
             'rapor_takip': s.rapor_takip_no}
            for s in sorted(
                eslesen, key=lambda s: _tarih_sort_key(s.tarih))[:5]
        ],
    }


def _lafiz_yolu_dene(hasta_tc: str,
                       aktif_rapor_metni: str,
                       aktif_rapor_takip_no: str) -> Optional[Dict]:
    """Aşama 1 — aktif rapor metnindeki "X tarihli NNNNNN takip no" lafzını
    parse edip hasta_rapor_gecmisi.db'de o takip no'yu ara.

    Returns:
        None — lafız yakalanmadı (EOS yoluna düş)
        Dict (durum='BULUNDU_LAFIZ'|'LAFIZ_TAKIP_NO_VAR_CACHE_YOK')
    """
    if not aktif_rapor_metni:
        return None
    bulgu = aktif_rapordan_baslangic_takip_no_cikar(aktif_rapor_metni)
    if not bulgu:
        return None
    takip_no, tarih_str = bulgu

    # Aktif rapor kendisinin takip no'sunu referans veriyorsa atla
    # (eski Medula raporlarında bazen aynı rapor kendi takip no'sunu
    # zikretmiştir — anlamsız)
    if aktif_rapor_takip_no and str(aktif_rapor_takip_no).strip() == takip_no:
        return None

    # DB'de ara — önce exact takip no, bulamazsa tarih+hasta fallback
    # (doktor yıl prefix'i birleşik yazmış olabilir: '2017909867' vs
    # gerçek '270909867' — tarih aynıysa fallback eşleştirir)
    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            takip_no_veya_tarih_ile_oku, sema_olustur)
        sema_olustur()
        kayit = takip_no_veya_tarih_ile_oku(
            takip_no, hasta_tc=hasta_tc or '', tarih_str=tarih_str)
    except Exception as e:
        logger.warning('hasta_rapor_gecmisi DB lookup hatası: %s', e)
        kayit = None

    if kayit and (kayit.detay_metni or '').strip():
        return {
            'rxid': None,
            'recete_tarihi': '',
            'urun_adi': '',
            'atc_kodu': '',
            'rapor_takip_no': takip_no,
            'rapor_no': '',
            'rapor_tarihi': (kayit.baslangic_tarihi or tarih_str),
            'rapor_metni': kayit.detay_metni or '',
            'aktif_recete_mi': False,
            'ayni_rapor_mi': False,
            'toplam_eski_sayi': 0,
            'kaynak': 'rapor_lafzi+gecmis_db',
            'durum': 'BULUNDU_LAFIZ',
            'lafiz_takip_no': takip_no,
            'lafiz_tarih': tarih_str,
            'eski_5_recete': [],
        }
    # Lafzen yakalandı ama DB'de detay metni yok → eczacı 🩺 basmalı
    return {
        'rxid': None,
        'recete_tarihi': '',
        'urun_adi': '',
        'atc_kodu': '',
        'rapor_takip_no': takip_no,
        'rapor_no': '',
        'rapor_tarihi': tarih_str,
        'rapor_metni': '',
        'aktif_recete_mi': False,
        'ayni_rapor_mi': False,
        'toplam_eski_sayi': 0,
        'kaynak': 'rapor_lafzi',
        'durum': 'LAFIZ_TAKIP_NO_VAR_CACHE_YOK',
        'lafiz_takip_no': takip_no,
        'lafiz_tarih': tarih_str,
        'eski_5_recete': [],
    }


def _eos_yolu_dene(
    hasta_tc: str,
    urun_keywords: Tuple[str, ...],
    aktif_recete_rxid: Optional[int],
    aktif_rapor_takip_no: Optional[str],
) -> Optional[Dict]:
    """Aşama 1 — Botanik EOS'tan etken-spesifik en eski reçete + RaporAna.

    EOS Botanik eczanesinin kesin kayıt kaynağı; etken-spesifik keyword
    daraltıldığında (örn. VEMLIDY için sadece TAF) en eski reçete = ilacın
    bu hastadaki gerçek başlangıcıdır.

    Hangi reçete "ilk" sayılır? RaporTakipNo'su olan en eski reçete
    (raporsuz çok eski reçeteler vardı — 2019 öncesi Medula sistemi)
    çünkü başlangıç KRİTERLERİNİ uygulayabilmemiz için rapor metni şart.
    """
    eski_receteler = _eos_ilk_recete_getir(
        hasta_tc, urun_keywords, limit=10)
    if not eski_receteler:
        return None
    # İlk raporlu reçeteyi bul (RaporTakipNo dolu)
    ilk: Optional[Dict] = None
    for r in eski_receteler:
        if (r.get('RaporAnaRaporTakipNo') or '').strip():
            ilk = r
            break
    if ilk is None:
        # Hiçbir reçetede rapor yok → başlangıç tespit edilemez
        return None

    rxid_eski = ilk.get('RxId')
    recete_tarihi_raw = ilk.get('RxIslemTarihi') or ilk.get('RxReceteTarihi')
    recete_tarihi = ''
    if recete_tarihi_raw:
        try:
            recete_tarihi = recete_tarihi_raw.strftime('%Y-%m-%d')
        except AttributeError:
            recete_tarihi = str(recete_tarihi_raw)[:10]
    rapor_takip = (ilk.get('RaporAnaRaporTakipNo') or '').strip()
    rapor_no = (ilk.get('RaporAnaRaporNo') or '').strip()
    rapor_tarihi_raw = ilk.get('RaporAnaRaporTarihi')
    rapor_tarihi = ''
    if rapor_tarihi_raw:
        try:
            rapor_tarihi = rapor_tarihi_raw.strftime('%Y-%m-%d')
        except AttributeError:
            rapor_tarihi = str(rapor_tarihi_raw)[:10]
    rapor_metni = (ilk.get('RaporAnaAciklamalar') or '').strip()

    aktif_zaten_baslangic = bool(
        aktif_recete_rxid and rxid_eski
        and int(aktif_recete_rxid) == int(rxid_eski))
    ayni_rapor = bool(
        aktif_rapor_takip_no
        and rapor_takip
        and str(aktif_rapor_takip_no).strip() == rapor_takip)

    if aktif_zaten_baslangic:
        durum = 'AKTIF_ZATEN_BASLANGIC'
    elif not rapor_metni:
        durum = 'METIN_BOS'
    else:
        durum = 'BULUNDU'

    return {
        'rxid': rxid_eski,
        'recete_tarihi': recete_tarihi,
        'urun_adi': ilk.get('UrunAdi') or '',
        'atc_kodu': ilk.get('ATCKodu') or '',
        'rapor_takip_no': rapor_takip,
        'rapor_no': rapor_no,
        'rapor_tarihi': rapor_tarihi,
        'rapor_metni': rapor_metni,
        'aktif_recete_mi': aktif_zaten_baslangic,
        'ayni_rapor_mi': ayni_rapor,
        'toplam_eski_sayi': len(eski_receteler),
        'kaynak': 'eos',
        'durum': durum,
        'lafiz_takip_no': '',
        'lafiz_tarih': '',
        'eski_5_recete': [
            {
                'tarih': (
                    r.get('RxIslemTarihi').strftime('%Y-%m-%d')
                    if hasattr(r.get('RxIslemTarihi'), 'strftime')
                    else str(r.get('RxIslemTarihi') or '')[:10]),
                'urun': r.get('UrunAdi') or '',
                'rapor_takip': r.get('RaporAnaRaporTakipNo') or '',
            }
            for r in eski_receteler[:5]
        ],
    }


def _yerel_db_detay_metni(rapor_takip_no: str, hasta_tc: str) -> str:
    """Yerel hasta_rapor_gecmisi.db'den verilen takip no için detay metni."""
    if not rapor_takip_no:
        return ''
    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            takip_no_ile_oku, sema_olustur)
        sema_olustur()
        kayit = takip_no_ile_oku(rapor_takip_no, hasta_tc=hasta_tc or '')
        if kayit:
            return kayit.detay_metni or ''
    except Exception as e:
        logger.debug('Yerel detay metni okuma hatası: %s', e)
    return ''


def _baska_eczane_riski_sonuc() -> Dict:
    """EOS + yerel tablo + lafız hepsi boş → başlangıç tespit edilemedi."""
    return {
        'rxid': None,
        'recete_tarihi': '',
        'urun_adi': '',
        'atc_kodu': '',
        'rapor_takip_no': '',
        'rapor_no': '',
        'rapor_tarihi': '',
        'rapor_metni': '',
        'aktif_recete_mi': False,
        'ayni_rapor_mi': False,
        'toplam_eski_sayi': 0,
        'kaynak': 'eos_yerel_bos',
        'durum': 'BASKA_ECZANE_RISKI',
        'lafiz_takip_no': '',
        'lafiz_tarih': '',
        'eski_5_recete': [],
    }


def baslangic_raporu_bul(
    hasta_tc: str,
    urun_keywords: Tuple[str, ...],
    aktif_recete_rxid: Optional[int] = None,
    aktif_rapor_takip_no: Optional[str] = None,
    aktif_rapor_metni: Optional[str] = None,
) -> Optional[Dict]:
    """Genel API — hastanın bu ilaç (etken-spesifik) başlangıç raporunu bul.

    Akış (2026-05-29 refactor — Yalçın Durdağı VEMLIDY bug fix):
        Aşama 1: Botanik EOS — etken-spesifik keyword'le en eski raporlu
                 reçete + bağlı RaporAna metni. NİHAİ KRONOLOJİ KAYNAĞI.
                 EOS Botanik eczanesinin kesin kayıtları olduğu için
                 "hasta bu eczanede bu etkeni ne zaman almaya başladı"
                 sorusunun cevabı buradadır. Detay metni boşsa yerel DB
                 takip_no_ile_oku ile zenginleştirilir.
        Aşama 2: Aktif rapor lafzında "DD.MM.YYYY tarihli NNNN takip no"
                 parse (fallback — EOS boşsa). Doktorun referans verdiği
                 başlangıç takip no'su yerel DB'de aranır.
        Aşama 3: Yerel hasta_rapor_gecmisi.db etken tablosu (son çare).
                 EOS boş ama Medula taramasında bu hastanın bu etkenle
                 rapor bulunduysa "başka eczane geçmişi" olarak gösterilir.
        BASKA_ECZANE_RISKI: tüm aşamalar boş → 🩺 GEÇMİŞ RAPOR TARA önerisi.

    Önemli (2026-05-29): Yerel tablo Aşama 0 değil Aşama 3 olarak konuldu.
    Eski sıralama yarım Medula taramasında yanlış pozitif veriyordu —
    eczacı sadece son raporu indirdiyse yerel tabloda tek aktif rapor
    görünür, kod onu "en eski" sanırdı. EOS daima paralel sorgulanır.

    Returns:
        Dict:
            'durum': 'BULUNDU' | 'AKTIF_ZATEN_BASLANGIC' | 'METIN_BOS' |
                     'BULUNDU_LAFIZ' | 'LAFIZ_TAKIP_NO_VAR_CACHE_YOK' |
                     'BULUNDU_TABLO' | 'BASKA_ECZANE_RISKI'
            'kaynak': 'eos' | 'eos+yerel_metin' | 'rapor_lafzi+gecmis_db' |
                      'rapor_lafzi' | 'medula_tablo_eos_bos' |
                      'eos_yerel_bos'
            ... (diğer alanlar — eski API ile aynı)
    """
    # ─ Aşama 1: EOS kronoloji (NİHAİ) ─────────────────────────────────────
    if hasta_tc and urun_keywords:
        eos_sonuc = _eos_yolu_dene(
            hasta_tc, urun_keywords,
            aktif_recete_rxid, aktif_rapor_takip_no)
        if eos_sonuc:
            # Detay metni zenginleştir — yerel Medula taramasından
            if (not eos_sonuc.get('rapor_metni')
                    and eos_sonuc.get('rapor_takip_no')):
                yerel_metin = _yerel_db_detay_metni(
                    eos_sonuc['rapor_takip_no'], hasta_tc)
                if yerel_metin:
                    eos_sonuc['rapor_metni'] = yerel_metin
                    eos_sonuc['kaynak'] = 'eos+yerel_metin'
                    if eos_sonuc.get('durum') == 'METIN_BOS':
                        eos_sonuc['durum'] = 'BULUNDU'
            return eos_sonuc

    # ─ Aşama 2: Aktif rapor lafzı (fallback) ──────────────────────────────
    lafiz_sonuc = _lafiz_yolu_dene(
        hasta_tc or '', aktif_rapor_metni or '',
        aktif_rapor_takip_no or '')
    if lafiz_sonuc and lafiz_sonuc.get('durum') == 'BULUNDU_LAFIZ':
        return lafiz_sonuc

    # ─ Aşama 3: Yerel tablo son çare ──────────────────────────────────────
    if hasta_tc and urun_keywords:
        yerel_sonuc = _yerel_tablo_yolu_dene(
            hasta_tc, urun_keywords, aktif_rapor_takip_no or '')
        if yerel_sonuc:
            yerel_sonuc['kaynak'] = 'medula_tablo_eos_bos'
            return yerel_sonuc

    # ─ Lafız parse buldu ama DB'de yok → eczacıya 🩺 öner ─────────────────
    if lafiz_sonuc:  # LAFIZ_TAKIP_NO_VAR_CACHE_YOK
        return lafiz_sonuc

    # ─ Hepsi boş → BAŞKA ECZANE RİSKİ ─────────────────────────────────────
    return _baska_eczane_riski_sonuc()


# ═════════════════════════════════════════════════════════════════════════
# EOS BAZLI DEVAM/BAŞLANGIÇ TESPİTİ — Sinyal 4 (en güvenilir)
# ═════════════════════════════════════════════════════════════════════════
#
# Mantık: Hastanın bu etken maddeli reçetelerinin bağlı olduğu DISTINCT
# RaporAna kayıtlarını çek. Aktif rapor takip no en eski rapor ise →
# BAŞLANGIÇ. Daha eski rapor varsa → DEVAM.
#
# Bu sinyal Botanik EOS'a doğrudan dayanır — yerel cache veya Medula
# tarama gerek değil. _hep_recete_tipi_tespit'in mevcut 3 sinyalinden
# (DB cache / metin / drug history) daha güvenilir, EN ÖNCE değerlendirilir.


def recete_tipi_eos_bazli(
    hasta_tc: str,
    urun_keywords: Tuple[str, ...],
    aktif_rapor_takip_no: Optional[str] = None,
    aktif_rapor_id: Optional[int] = None,
) -> Tuple[str, str, Dict]:
    """EOS'taki DISTINCT RaporAna kayıtlarını kullanarak BAŞLANGIÇ/DEVAM
    kararı ver.

    Args:
        hasta_tc: 11 haneli TC
        urun_keywords: etken/marka keyword tuple
        aktif_rapor_takip_no: aktif raporun RaporAnaRaporTakipNo'su
        aktif_rapor_id: aktif raporun RaporAnaId'si (varsa)

    Returns:
        (tip, gerekce, detay)
            tip: 'BASLANGIC' | 'DEVAM' | 'BELIRSIZ_EOS' | 'YOK_EOS'
            gerekce: insan-okur açıklama
            detay: {
                'eos_rapor_sayisi': int,
                'en_eski_takip_no': str,
                'en_eski_tarih': str,
                'aktif_rapor_sira': int,  # 1=en eski
                'rapor_listesi': [...],   # özet
            }
    """
    detay: Dict = {
        'eos_rapor_sayisi': 0,
        'en_eski_takip_no': '',
        'en_eski_tarih': '',
        'aktif_rapor_sira': 0,
        'rapor_listesi': [],
    }
    if not hasta_tc:
        return ('BELIRSIZ_EOS', 'Hasta TC yok — EOS sorgu atlandı', detay)
    if not urun_keywords:
        return ('BELIRSIZ_EOS',
                'Etken keyword listesi boş — EOS sorgu atlandı', detay)
    try:
        from botanik_db import get_botanik_db
        db = get_botanik_db()
        if not db.baglan():
            return ('BELIRSIZ_EOS',
                    'EOS bağlantı kurulamadı — fallback sinyallere düş',
                    detay)
        raporlar = db.hasta_etken_rapor_listesi(
            hasta_tc, urun_keywords, limit=50)
    except Exception as e:
        logger.warning('EOS rapor listesi sorgu hatası: %s', e)
        return ('BELIRSIZ_EOS', f'EOS hatası: {e}', detay)

    detay['eos_rapor_sayisi'] = len(raporlar)
    if not raporlar:
        return ('YOK_EOS',
                'EOS\'ta bu etken için hiç rapor bulunamadı — '
                'hasta ilacı başka eczaneden başlamış olabilir',
                detay)

    # Liste eskiden yeniye sıralı; özet detay'a ekle
    def _tarih_str(t):
        if not t:
            return ''
        try:
            return t.strftime('%Y-%m-%d')
        except AttributeError:
            return str(t)[:10]

    for i, r in enumerate(raporlar, start=1):
        detay['rapor_listesi'].append({
            'sira': i,
            'rapor_ana_id': r.get('RaporAnaId'),
            'rapor_no': r.get('RaporAnaRaporNo') or '',
            'takip_no': r.get('RaporAnaRaporTakipNo') or '',
            'rapor_tarihi': _tarih_str(r.get('RaporAnaRaporTarihi')),
            'ilk_recete_tarihi': _tarih_str(r.get('ilk_recete_tarihi')),
            'recete_sayisi': r.get('bu_rapora_bagli_recete_sayisi') or 0,
        })

    en_eski = raporlar[0]
    detay['en_eski_takip_no'] = (en_eski.get('RaporAnaRaporTakipNo')
                                 or '').strip()
    detay['en_eski_tarih'] = _tarih_str(en_eski.get('RaporAnaRaporTarihi'))

    # Aktif rapor sıra bul
    aktif_takip = (aktif_rapor_takip_no or '').strip()
    aktif_id = aktif_rapor_id
    for entry in detay['rapor_listesi']:
        if (aktif_takip and entry['takip_no']
                and aktif_takip == entry['takip_no']):
            detay['aktif_rapor_sira'] = entry['sira']
            break
        if (aktif_id and entry['rapor_ana_id']
                and int(aktif_id) == int(entry['rapor_ana_id'])):
            detay['aktif_rapor_sira'] = entry['sira']
            break

    if detay['aktif_rapor_sira'] == 0:
        # Aktif rapor EOS listesinde bulunamadı — belki SecilenRapor
        # sync sorunu var. Yine de tek rapor varsa BAŞLANGIÇ varsayılır.
        if len(raporlar) == 1:
            return ('BASLANGIC',
                    f'EOS\'ta bu etken için tek rapor var '
                    f'(takip: {detay["en_eski_takip_no"]}, '
                    f'tarih: {detay["en_eski_tarih"]}) — aktif rapor '
                    f'sıra eşleşmedi ama tek olduğu için başlangıç',
                    detay)
        return ('BELIRSIZ_EOS',
                f'EOS\'ta {len(raporlar)} rapor var ama aktif rapor takip '
                f'no ({aktif_takip or "?"}) listede bulunamadı '
                f'(SecilenRapor sync sorunu olabilir)', detay)

    if detay['aktif_rapor_sira'] == 1:
        if len(raporlar) == 1:
            return ('BASLANGIC',
                    f'EOS\'ta bu etken için tek rapor: aktif rapor '
                    f'(takip: {aktif_takip}, tarih: '
                    f'{detay["en_eski_tarih"]}) = başlangıç',
                    detay)
        return ('BASLANGIC',
                f'Aktif rapor EOS\'ta en eski rapor (1/{len(raporlar)}); '
                f'sonra {len(raporlar)-1} devam rapor daha var', detay)

    # aktif_rapor_sira > 1 → daha eski rapor var → DEVAM
    return ('DEVAM',
            f'Aktif rapor EOS\'ta {detay["aktif_rapor_sira"]}. sırada '
            f'(toplam {len(raporlar)}); en eski rapor '
            f'(takip: {detay["en_eski_takip_no"]}, '
            f'tarih: {detay["en_eski_tarih"]}) başlangıç',
            detay)


# ═════════════════════════════════════════════════════════════════════════
# MODÜL-SPESİFİK KEYWORD HELPER'LARI
# ═════════════════════════════════════════════════════════════════════════

def hepatit_keyword_listesi(etkin_tip: str,
                              ilac_adi: str = '',
                              etkin_madde: str = '') -> Tuple[str, ...]:
    """Etken tipine göre uygun keyword tuple'ı döndür.

    HBV oral için ilac_adi+etkin_madde verilirse ETKEN-SPESİFİK
    (TAF/TDF/ETV/LAM/TLB/ADV) dar liste döner. Verilmezse geniş HBV oral
    havuzu (eski davranış, backwards compat).

    HCV/PEG/IFN/RIBAVIRIN için etken bazlı daralma yapılmaz çünkü tedavi
    kombinasyon olarak yazılır ve "antiviral tedavi başlangıcı" SUT
    açısından grup bazlıdır.

    etkin_tip değerleri _hep_etken_tip()'ten gelir:
        HBV_ORAL, HCV_DAA, PEG_IFN, IFN, RIBAVIRIN, NONE
    """
    try:
        from recete_kontrol.hepatit_kontrol import (
            HBV_ORAL_ETKEN, HBV_ORAL_TICARI,
            HBV_ALT_TIP_KW, _hbv_oral_etken_alt_tip,
            HCV_DAA_ETKEN, HCV_DAA_TICARI,
            PEG_IFN_ETKEN, PEG_IFN_TICARI,
            INTERFERON_ETKEN, RIBAVIRIN_ETKEN, RIBAVIRIN_TICARI)
    except ImportError as e:
        logger.warning('hepatit_kontrol import hatası: %s', e)
        return ()
    if etkin_tip == 'HBV_ORAL':
        # Etken-spesifik dar liste (2026-05-29 Yalçın Durdağı bug fix)
        if ilac_adi or etkin_madde:
            alt_tip = _hbv_oral_etken_alt_tip(ilac_adi, etkin_madde)
            if alt_tip and alt_tip in HBV_ALT_TIP_KW:
                return HBV_ALT_TIP_KW[alt_tip]
        # Backwards-compat fallback
        return HBV_ORAL_ETKEN + HBV_ORAL_TICARI
    if etkin_tip == 'HCV_DAA':
        return HCV_DAA_ETKEN + HCV_DAA_TICARI
    if etkin_tip == 'PEG_IFN':
        return PEG_IFN_ETKEN + PEG_IFN_TICARI
    if etkin_tip == 'IFN':
        return INTERFERON_ETKEN
    if etkin_tip == 'RIBAVIRIN':
        return RIBAVIRIN_ETKEN + RIBAVIRIN_TICARI
    return ()


def hepatit_baslangic_raporu_bul(ilac_sonuc: Dict) -> Optional[Dict]:
    """Hepatit kontrolü için kısa wrapper — etkin tip'e göre uygun keyword
    seti seçer ve baslangic_raporu_bul()'u çağırır."""
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if not hasta_tc:
        return None
    try:
        from recete_kontrol.hepatit_kontrol import _hep_etken_tip
        ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
        etkin = (ilac_sonuc.get('etkin_madde') or '').upper()
        etkin_tip = _hep_etken_tip(ilac_adi, etkin)
    except Exception as e:
        logger.warning('Hepatit etkin_tip tespit hatası: %s', e)
        return None
    # HBV oral için etken-spesifik (TAF/TDF/ETV/LAM/...) dar keyword
    keywords = hepatit_keyword_listesi(
        etkin_tip, ilac_adi=ilac_adi, etkin_madde=etkin)
    if not keywords:
        return None
    aktif_rxid = ilac_sonuc.get('RxId') or ilac_sonuc.get('rxid')
    aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('RaporAnaRaporTakipNo')
                   or '')
    # Aktif rapor metnini birleştir — Aşama 2 lafız parse için
    rapor_aciklamalari = ilac_sonuc.get('rapor_aciklamalari') or []
    if isinstance(rapor_aciklamalari, list):
        aktif_rapor_metni = ' '.join(str(x) for x in rapor_aciklamalari)
    else:
        aktif_rapor_metni = str(rapor_aciklamalari)
    return baslangic_raporu_bul(
        hasta_tc, keywords,
        aktif_recete_rxid=aktif_rxid,
        aktif_rapor_takip_no=aktif_takip,
        aktif_rapor_metni=aktif_rapor_metni)


# ═════════════════════════════════════════════════════════════════════════
# DİSPATCHER — aktif modüle göre uygun baslangic_raporu_bul wrapper
# ═════════════════════════════════════════════════════════════════════════

# Modül adı → wrapper fonksiyon (yeni modül eklenirken buraya kaydedilir)
_MODUL_WRAPPER_MAP = {
    'hepatit': hepatit_baslangic_raporu_bul,
    # 'diyabet': diyabet_baslangic_raporu_bul,   # TODO
}


def baslangic_raporu_bul_dispatcher(modul: str,
                                      ilac_sonuc: Dict) -> Optional[Dict]:
    """Modül adına göre uygun başlangıç bulma wrapper'ını çağır."""
    wrapper = _MODUL_WRAPPER_MAP.get(modul)
    if not wrapper:
        return None
    try:
        return wrapper(ilac_sonuc)
    except Exception as e:
        logger.error('baslangic_raporu_bul_dispatcher (%s) hatası: %s',
                     modul, e)
        return None


__all__ = [
    'baslangic_raporu_bul',
    'baslangic_raporu_bul_dispatcher',
    'hepatit_baslangic_raporu_bul',
    'hepatit_keyword_listesi',
    'aktif_rapordan_baslangic_takip_no_cikar',
    'recete_tipi_eos_bazli',
]
