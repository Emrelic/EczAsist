# -*- coding: utf-8 -*-
"""Diğer Rapor Uygun — bypass helper.

Bir SUT şartı ilintilenen raporda sağlanmıyor ama hastanın geçmiş
raporlarından birinde bulunuyorsa, atomu VAR olarak işaretler ve
`SartSonuc.bypass_kaynak` alanına hangi raporun hangi tarihinde
bulunduğunu yazar. Tüm atomlar OK olduğunda kontrol fonksiyonu
`KontrolSonucu.DIGER_RAPOR_UYGUN` döndürür.

Kapsam (öncelik sırasıyla):
  • ARB EK-4/F m.51 — "monoterapi ile kan basıncı kontrolü sağlanamadı"
  • Diyabet 4.2.38 / 4.2.74 — "metformin ve sülfonilürelerin maks tolere
    edilebilir dozlarında yeterli glisemik kontrol sağlanamamıştır"
  • Klopidogrel/Prasugrel/Tikagrelor (4.2.15) — "anjiyografi tarihi"

Kullanım:
    from recete_kontrol.diger_rapor_bypass import gecmis_raporlarda_ibare_ara

    sonuc = gecmis_raporlarda_ibare_ara(
        hasta_tc="12345678901",
        ibareler=["monoterapi", "monoterapi yetersiz", "tek ilaç yetersiz"],
        aktif_rapor_takip_no="RP001",   # bunu hariç tut
    )
    if sonuc:
        # atom durumu VAR + bypass_kaynak set et
        atom.durum = SartDurumu.VAR
        atom.bypass_kaynak = sonuc["ozet"]   # "Rapor RP002 (12/03/2024)"

Bu modül yalnızca YEREL SQLite cache okur — MEDULA'ya bağlanmaz.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# 1. METİN NORMALİZASYON (Türkçe karakter güvenli arama)
# ═════════════════════════════════════════════════════════════════════════

def _normalize(s: str) -> str:
    """Türkçe karakter güvenli lowercase + ASCII'ye indirgenmiş eşleme.

    'İ→i, I→ı→i, Ş→s, Ğ→g, Ü→u, Ö→o, Ç→c' — parser'ı bozan İ/I tuzaklarını
    önler. Memory: feedback_tr_lower_parser_tuzagi.md.
    """
    if not s:
        return ""
    s = s.replace("İ", "i").replace("I", "ı")
    s = s.lower()
    s = (s.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
          .replace("ü", "u").replace("ö", "o").replace("ç", "c"))
    return s


def _snippet_cikar(metin: str, ibare: str, oncesi: int = 60,
                    sonrasi: int = 80) -> str:
    """İbarenin etrafından bir parça çıkar (raporda görsel ipucu için).

    Eşleşme bulunamazsa boş string döner.
    """
    if not metin or not ibare:
        return ""
    m = re.search(re.escape(ibare), metin, re.IGNORECASE)
    if not m:
        # Normalize edilmiş aramayla yeniden dene
        n_metin = _normalize(metin)
        n_ibare = _normalize(ibare)
        m = re.search(re.escape(n_ibare), n_metin)
        if not m:
            return ""
        # Normalize'da eşleşti ama orijinal indeks farklı — yine de yaklaşık
        # konum üretmeye çalış
        idx = m.start()
        bas = max(0, idx - oncesi)
        son = min(len(metin), idx + len(ibare) + sonrasi)
        return ("..." if bas > 0 else "") + metin[bas:son].strip() + (
            "..." if son < len(metin) else "")
    bas = max(0, m.start() - oncesi)
    son = min(len(metin), m.end() + sonrasi)
    return ("..." if bas > 0 else "") + metin[bas:son].strip() + (
        "..." if son < len(metin) else "")


# ═════════════════════════════════════════════════════════════════════════
# 2. ANA HELPER — geçmiş raporlarda ibare ara
# ═════════════════════════════════════════════════════════════════════════

def gecmis_raporlarda_ibare_ara(
        hasta_tc: str,
        ibareler: List[str],
        aktif_rapor_takip_no: str = "",
        kategori: Optional[str] = None,
) -> Optional[Dict]:
    """Hasta'nın yerel cache'indeki raporlarda verilen ibareleri ara.

    Args:
        hasta_tc: 11 haneli TC. Boşsa None döner.
        ibareler: aranan ibare listesi (case-insensitive, Türkçe karakter
            güvenli). En az biri bulunursa eşleşme döner.
        aktif_rapor_takip_no: aktif (ilintilenen) rapor takip no — bu rapor
            arama kapsamından çıkarılır. Boş bırakılırsa tüm raporlar taranır.
        kategori: 'HEPATIT_B', 'DIYABET' vb. — None ise tüm raporlar.

    Returns:
        None — hiçbir rapor uymadı (boş cache, ibare yok, ya da hasta_tc boş).
        Dict — eşleşme bulundu:
          {
            'rapor_takip_no': 'RP002',
            'baslangic_tarihi': '12/03/2024',
            'bitis_tarihi': '12/03/2026',
            'rapor_kodu': '04.05',
            'tani': 'Esansiyel hipertansiyon (I10)',
            'bulunan_ibare': 'monoterapi',
            'snippet': '... monoterapi ile yeterli kan basıncı sağlanamadı ...',
            'ozet': 'Rapor RP002 (12/03/2024): "monoterapi" bulundu',
            'taranan_rapor_sayisi': 7,
            'detayli_rapor_sayisi': 3,
            'detaysiz_rapor_sayisi': 4,
          }
    """
    if not hasta_tc or not hasta_tc.strip():
        return None

    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            hasta_raporlarini_oku, sema_olustur)
        sema_olustur()
        tum_raporlar = hasta_raporlarini_oku(hasta_tc.strip(),
                                                kategori=kategori)
    except Exception as e:
        logger.debug("hasta_rapor_gecmisi okuma hatası: %s", e)
        return None

    if not tum_raporlar:
        return None

    aktif_tno = (aktif_rapor_takip_no or "").strip()
    detayli_sayim = 0
    detaysiz_sayim = 0
    n_ibareler = [_normalize(ib) for ib in ibareler if ib and ib.strip()]
    if not n_ibareler:
        return None

    for rapor in tum_raporlar:
        # Aktif raporu hariç tut (kendi raporunda arayıp bulmasın)
        if aktif_tno and (rapor.rapor_takip_no or "").strip() == aktif_tno:
            continue
        detay = (rapor.detay_metni or "").strip()
        if not detay:
            detaysiz_sayim += 1
            continue
        detayli_sayim += 1
        n_detay = _normalize(detay)
        # İbarelerin hangisi geçiyor?
        for orig_ibare, n_ibare in zip(ibareler, n_ibareler):
            if not n_ibare:
                continue
            if n_ibare in n_detay:
                snippet = _snippet_cikar(detay, orig_ibare) or _snippet_cikar(
                    detay, n_ibare)
                tarih = rapor.baslangic_tarihi or rapor.bitis_tarihi or "?"
                ozet = (f'Rapor {rapor.rapor_takip_no} ({tarih}): '
                        f'"{orig_ibare}" bulundu')
                return {
                    'rapor_takip_no': rapor.rapor_takip_no or '',
                    'baslangic_tarihi': rapor.baslangic_tarihi or '',
                    'bitis_tarihi': rapor.bitis_tarihi or '',
                    'rapor_kodu': rapor.rapor_kodu or '',
                    'tani': rapor.tani or '',
                    'icd_kodu': rapor.icd_kodu or '',
                    'bulunan_ibare': orig_ibare,
                    'snippet': snippet,
                    'ozet': ozet,
                    'taranan_rapor_sayisi': len(tum_raporlar),
                    'detayli_rapor_sayisi': detayli_sayim,
                    'detaysiz_rapor_sayisi': detaysiz_sayim,
                }

    # Hiçbir raporda ibare bulunamadı
    if detayli_sayim == 0 and detaysiz_sayim > 0:
        logger.debug(
            "gecmis_raporlarda_ibare_ara: hasta_tc=%s, %d rapor var ama "
            "tümünün detay_metni boş — detaylı tarama yapın",
            hasta_tc, detaysiz_sayim)
    return None


# ═════════════════════════════════════════════════════════════════════════
# 3. KONTROL FONKSİYONLARI İÇİN HAZIR İBARE LİSTELERİ
# ═════════════════════════════════════════════════════════════════════════

# ARB EK-4/F m.51 — "monoterapi ile kan basıncı kontrolünün sağlanamadığı"
IBARELER_ARB_MONOTERAPI = (
    "monoterapi ile kan basıncı",
    "monoterapi ile kan basinci",
    "monoterapi yetersiz",
    "monoterapi yetmedi",
    "monoterapi ile yeterli",
    "tek ilaç ile kan basıncı",
    "tek ilac ile kan basinci",
    "tek ilaçla yeterli",
    "tek ilacla yeterli",
)

# Diyabet 4.2.38 / 4.2.74 — "metformin ve sülfonilürelerin maks tolere
# edilebilir dozlarında yeterli glisemik kontrol sağlanamamıştır"
IBARELER_DIYABET_GLISEMIK = (
    "metformin ve sülfonilüre",
    "metformin ve sulfonilure",
    "metformin+sülfonilüre",
    "metformin+sulfonilure",
    "maksimum tolere edilebilir",
    "yeterli glisemik kontrol sağlanamadı",
    "yeterli glisemik kontrol saglanamadi",
    "glisemik kontrol sağlanamamıştır",
    "glisemik kontrol saglanamamistir",
    "metformin yetersiz",
)

# P2Y12 (Klopidogrel/Prasugrel/Tikagrelor) — "anjiyografi tarihi"
IBARELER_P2Y12_ANJIYO = (
    "anjiyografi tarihi",
    "anjiografi tarihi",
    "koroner anjiyografi",
    "koroner anjiografi",
    "kag tarihi",
    "kateterizasyon tarihi",
    "pci tarihi",
    "perkütan koroner girişim",
    "perkutan koroner girisim",
)


# ═════════════════════════════════════════════════════════════════════════
# 4. GENERIC ATOMIK BYPASS — atomların adına bakarak otomatik bypass uygular
# ═════════════════════════════════════════════════════════════════════════

def atomlari_otomatik_bypass(sartlar: list,
                                 ilac_sonuc: Dict,
                                 ad_anahtar_kelimeleri: tuple,
                                 ibareler: tuple,
                                 kategori: Optional[str] = None,
                                 ) -> int:
    """Sartlar listesinde verilen anahtar kelimelerden birini içeren ve
    durumu VAR olmayan (YOK/KE) atomları geçmiş rapor bypass'ı ile dener.

    Bulunursa atomun durumu SartDurumu.VAR'a yükseltilir ve `bypass_kaynak`
    alanına raporun özeti yazılır.

    Args:
        sartlar: List[SartSonuc] — kontrol fonksiyonunun ürettiği şart listesi.
        ilac_sonuc: ilaç dict — `hasta_tc` ve `rapor_takip_no` alanları okunur.
        ad_anahtar_kelimeleri: ('monoterapi', 'metformin', 'glisemik', ...) gibi
            tuple — atom.ad alanında bu kelimelerden biri (lowercase) varsa
            bypass aday sayılır.
        ibareler: tuple — geçmiş raporda aranacak ibareler.
        kategori: 'DIYABET', 'HIPERTANSIYON' vb. (None ise tüm raporlar).

    Returns:
        Bypass uygulanan atom sayısı (0 ise hiçbir atom değişmedi).
    """
    try:
        from recete_kontrol.base_kontrol import SartDurumu
    except Exception:
        return 0

    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if not hasta_tc:
        return 0

    aktif_tno = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    n_anahtar = [_normalize(k) for k in ad_anahtar_kelimeleri if k]
    if not n_anahtar:
        return 0

    bypass_sayisi = 0
    bypass_ortak = None  # ilk bulunan bypass kaydı — sonraki atomlarda da
                          # aynısını kullan (her atom için DB taraması yapma)

    for sart in sartlar:
        if sart.durum == SartDurumu.VAR:
            continue
        n_ad = _normalize(sart.ad or '')
        if not any(k in n_ad for k in n_anahtar):
            continue
        # Eşleşen atom — bypass dene
        if bypass_ortak is None:
            bypass_ortak = gecmis_raporlarda_ibare_ara(
                hasta_tc, list(ibareler),
                aktif_rapor_takip_no=aktif_tno,
                kategori=kategori)
            if bypass_ortak is None:
                # İlk denemede bulunamadı — diğer atomlar için de boş
                return 0
        # Atomu bypass ile VAR'a yükselt
        sart.durum = SartDurumu.VAR
        sart.bypass_kaynak = bypass_ortak["ozet"]
        sart.neden = (f'{sart.neden} | BYPASS: {bypass_ortak["ozet"]}'
                      if sart.neden else f'BYPASS: {bypass_ortak["ozet"]}')
        bypass_sayisi += 1

    return bypass_sayisi


def sonuc_bypass_uygula_genel(rapor, sartlar: list):
    """Eğer rapor.sonuc UYGUN ve en az bir atom bypass_kaynak ile VAR
    olduysa → sonucu DIGER_RAPOR_UYGUN'a yükselt.

    Bu kontrol fonksiyonunun en sonunda çağrılır:
        sartlar = ...  # atomik şartlar hazır
        atomlari_otomatik_bypass(sartlar, ilac_sonuc, ('monoterapi',), IBARELER_ARB_MONOTERAPI)
        sonuc = _genel_sonuc(sartlar)
        rapor = KontrolRaporu(sonuc=sonuc, ..., sartlar=sartlar)
        sonuc_bypass_uygula_genel(rapor, sartlar)
        return rapor
    """
    try:
        from recete_kontrol.base_kontrol import KontrolSonucu
    except Exception:
        return rapor
    if rapor.sonuc != KontrolSonucu.UYGUN:
        return rapor
    bypass_atomlari = [s for s in (sartlar or [])
                        if getattr(s, 'bypass_kaynak', None)]
    if not bypass_atomlari:
        return rapor
    rapor.sonuc = KontrolSonucu.DIGER_RAPOR_UYGUN
    ozetler = '; '.join(s.bypass_kaynak for s in bypass_atomlari[:3])
    suffix = f' | BYPASS: {ozetler}'
    rapor.mesaj = (rapor.mesaj or '') + suffix
    if rapor.detaylar is None:
        rapor.detaylar = {}
    rapor.detaylar['bypass_atom_sayisi'] = len(bypass_atomlari)
    rapor.detaylar['bypass_kaynaklari'] = [s.bypass_kaynak
                                             for s in bypass_atomlari]
    return rapor


__all__ = [
    'gecmis_raporlarda_ibare_ara',
    'atomlari_otomatik_bypass',
    'sonuc_bypass_uygula_genel',
    'IBARELER_ARB_MONOTERAPI',
    'IBARELER_DIYABET_GLISEMIK',
    'IBARELER_P2Y12_ANJIYO',
]
