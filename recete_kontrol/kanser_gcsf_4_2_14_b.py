# -*- coding: utf-8 -*-
"""SUT 4.2.14.B — Tedavi protokolünü gösterir sağlık kurulu raporuna dayanılarak
uzman hekimlerce reçetelendirilecek ilaçlar.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:5665-5676`` (mevzuat.gov.tr,
MevzuatNo=17229). Protokol metodolojisi: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md``
+ CLAUDE.md ``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
İKİ YOLAKLI DİSPATCHER
═══════════════════════════════════════════════════════════════════════════

  YOLAK-1 → Kanser/hormon ilaçları (Fıkra 1)
            amifostin, anastrazol, bikalutamid, buserelin, dosetaksel,
            eksemestan, gemsitabin, goserelin, ibandronik asit, interferon
            alfa 2a-2b, irinotekan, kapesitabin, klodronat, letrozol,
            löprolid, medroksiprogesteron, oksaliplatin, paklitaksel,
            pamidronat, siproteron, tegafur-urasil, topotekan, triptorelin,
            vinorelbin, zoledronik asit
            → "Tedavi protokolünü gösterir SAĞLIK KURULU raporuna dayanılarak
               UZMAN HEKİMLERCE reçetelendirilir."

  YOLAK-2 → G-CSF (Fıkra 2)
            filgrastim, lenograstim, pegfilgrastim, lipegfilgrastim
            → 6 ay süreli SK raporu (heyette ≥1: hematoloji / tıbbi onkoloji /
              enfeksiyon / radyasyon onk. / göğüs hast. / üroloji / kadın doğum)
              + reçete eden: bu 7 + iç hastalıkları / çocuk hastalıkları (9 branş)
              + en fazla birer aylık doz.
              (Lenograstim günde 4 flakon yalnız PBPC mobilizasyonu — bilgi.)

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  YOLAK-1:  Y1_UYGUN ⇔ A1(SK raporu) ∧ A2(uzman hekim)
                       [∧ A3_bilgi(protokol) ∧ A4_bilgi(kanser ICD)
                        ∧ A5_bilgi(oral vinorelbin)]

  YOLAK-2:  Y2_UYGUN ⇔ B1(SK raporu) ∧ B2(heyette ≥1/7 uzman)
                       ∧ B3(reçete eden 9 branş)
                       [∧ B4_sartli(6 ay) ∧ B5_sartli(birer aylık doz)
                        ∧ B6_bilgi(lenograstim/PBPC)]

Bilgi/şartlı atomlar matematiği bozmaz; KE kalırsa SARTLI_UYGUN (eczacı
manuel doğrular). Sessizlik → örtük kabul YASAK (CLAUDE.md §2.5):
rapor hiç yoksa A1/B1 = YOK (UYGUN_DEĞİL), tespit edilemiyorsa KE (ŞÜPHELİ).

Ana entrypoint: ``kanser_gcsf_kontrol_4_2_14_b(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı listeleri (etken madde + ticari ad — TR/INN + norm ASCII)
# ═══════════════════════════════════════════════════════════════════════
# NOT: Eşleştirme norm_tr_upper ile yapılır (Türkçe karakter tuzağı). Set
# üyeleri ASCII-büyük tutulur. Etken madde (ATCTurkce) birincil sinyaldir;
# yaygın ticari adlar destek olarak eklenmiştir.

YOLAK1_ILACLAR: Set[str] = {
    # Amifostin
    'AMIFOSTIN', 'AMIFOSTINE', 'ETHYOL',
    # Anastrazol
    'ANASTRAZOL', 'ANASTROZOL', 'ANASTROZOLE', 'ARIMIDEX', 'ANASTRA',
    # Bikalutamid
    'BIKALUTAMID', 'BICALUTAMID', 'BICALUTAMIDE', 'CASODEX', 'BIKALEN',
    # Buserelin
    'BUSERELIN', 'SUPREFACT',
    # Dosetaksel
    'DOSETAKSEL', 'DOSETAXEL', 'DOCETAXEL', 'TAXOTERE', 'DAXOTEL', 'ONTAXEL',
    # Eksemestan
    'EKSEMESTAN', 'EXEMESTANE', 'AROMASIN', 'EKSEMES',
    # Gemsitabin
    'GEMSITABIN', 'GEMCITABINE', 'GEMZAR', 'GEMKO', 'DBL GEMSITABIN',
    # Goserelin
    'GOSERELIN', 'ZOLADEX',
    # İbandronik asit
    'IBANDRONIK', 'IBANDRONAT', 'IBANDRONIC', 'IBANDRONATE', 'BONDRONAT', 'BONVIVA',
    # İnterferon alfa 2a/2b
    'INTERFERON ALFA', 'INTERFERON ALFA-2A', 'INTERFERON ALFA-2B',
    'INTERFERON ALFA 2A', 'INTERFERON ALFA 2B', 'ROFERON', 'INTRONA',
    # İrinotekan
    'IRINOTEKAN', 'IRINOTECAN', 'CAMPTO', 'IRINOTESIN',
    # Kapesitabin
    'KAPESITABIN', 'CAPECITABINE', 'XELODA', 'KAPETSIN', 'EZACITAB',
    # Klodronat
    'KLODRONAT', 'CLODRONATE', 'CLODRONAT', 'BONEFOS', 'CLASTEON', 'LODRONAT',
    # Letrozol
    'LETROZOL', 'LETROZOLE', 'FEMARA', 'LETROFEM', 'LORATIN',
    # Löprolid asetat
    'LOPROLID', 'LEUPROLID', 'LEUPRORELIN', 'LEUPROLIDE', 'LUCRIN', 'ELIGARD',
    # Medroksiprogesteron asetat
    'MEDROKSIPROGESTERON', 'MEDROXYPROGESTERONE', 'FARLUTAL', 'DEPO-PROVERA',
    # Oksaliplatin
    'OKSALIPLATIN', 'OXALIPLATIN', 'OXALIPLATINE', 'ELOXATIN', 'OKSAMED',
    # Paklitaksel
    'PAKLITAKSEL', 'PACLITAXEL', 'TAXOL', 'ABRAXANE', 'ANZATAX', 'SINDAXEL',
    # Pamidronat
    'PAMIDRONAT', 'PAMIDRONATE', 'AREDIA', 'PAMIDRON',
    # Siproteron asetat
    'SIPROTERON', 'CYPROTERONE', 'CIPROTERON', 'ANDROCUR',
    # Tegafur-urasil
    'TEGAFUR', 'URASIL', 'TEGAFUR-URASIL', 'TEGAFUR URASIL', 'UFT',
    # Topotekan
    'TOPOTEKAN', 'TOPOTECAN', 'HYCAMTIN',
    # Triptorelin asetat
    'TRIPTORELIN', 'DECAPEPTYL', 'DIPHERELINE', 'DECAMAX', 'GONAPEPTYL',
    # Vinorelbin
    'VINORELBIN', 'VINORELBINE', 'NAVELBINE', 'VINORTEX', 'NAVIREL',
    # Zoledronik asit
    'ZOLEDRONIK', 'ZOLEDRONAT', 'ZOLEDRONIC', 'ZOLENDRONIK', 'ZOLENDRONIC',
    'ZOMETA', 'ACLASTA', 'ZOLDESIN', 'ZOLENDRO', 'OSTEOZOLED',
}

# Oral vinorelbin alt-koşulu (A5): kür protokolünde belirtilmeli + enjektabl başlangıç
ORAL_VINORELBIN_ISARET: Set[str] = {'NAVELBINE ORAL', 'VINORELBIN ORAL', 'KAPSUL', 'YUMUSAK KAPSUL'}

GCSF_ILACLAR: Set[str] = {
    'FILGRASTIM', 'NEUPOGEN', 'LEUCOSTIM', 'GRANULOKINE', 'TEVAGRASTIM', 'NIVESTIM',
    'LENOGRASTIM', 'GRANOCYTE',
    'PEGFILGRASTIM', 'NEULASTA', 'PEGGRANS', 'FULPHILA', 'PELGRAZ', 'ZIEXTENZO',
    'LIPEGFILGRASTIM', 'LONQUEX',
}

LENOGRASTIM_ISARET: Set[str] = {'LENOGRASTIM', 'GRANOCYTE'}

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower ile alt-string eşleşmesi)
# ═══════════════════════════════════════════════════════════════════════
# Fıkra (2) — heyette bulunması gereken 7 uzman branşı (≥1 yeterli)
GCSF_HEYET_BRANSLAR: List[str] = [
    'hematoloji',
    'onkoloji',          # tıbbi onkoloji + radyasyon onkolojisi (ikisi de izinli)
    'enfeksiyon',
    'radyasyon',         # radyasyon onkolojisi (onkoloji ile örtüşür, güvenli)
    'gogus',             # göğüs hastalıkları
    'uroloji',
    'kadin',             # kadın hastalıkları ve doğum
    'dogum',
    'jinekoloji',
]

# Fıkra (2) — reçete edebilecek 9 branş (7 + iç hastalıkları + çocuk)
GCSF_RECETE_BRANSLAR: List[str] = GCSF_HEYET_BRANSLAR + [
    'ic hastalik',       # iç hastalıkları
    'dahiliye',
    'cocuk',             # çocuk hastalıkları
    'pediatri',
]

# Uzman hekim sayılmayan branşlar (Fıkra 1 A2 — "uzman hekimlerce")
PRATISYEN_BRANSLAR: List[str] = [
    'pratisyen', 'aile hek', 'aile hekimligi', 'genel pratisyen',
]


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    """İlaç adı + etken madde birleşik (dispatcher eşleşmesi için, ASCII-upper)."""
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume: Set[str]) -> bool:
    """metin_upper (zaten norm_tr_upper edilmiş) içinde kümeden biri geçiyor mu?"""
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _rapor_metni(ilac_sonuc: Dict) -> str:
    """Rapor + reçete açıklama birleşik metni (norm_tr_lower — regex için)."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_lower(' '.join(parcalar))


def _brans_l(brans: Optional[str]) -> str:
    """Branş string'ini ASCII-lower'a indir (eşleşme için)."""
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    if not bl:
        return False
    return any(a in bl for a in anahtarlar)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def kanser_gcsf_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Reçete kalemi 4.2.14.B kapsamında hangi yolağa düşer?

    Returns: 'YOLAK1' | 'YOLAK2' | None (kapsam dışı).
    G-CSF (Yolak-2) önce kontrol edilir — daha spesifik liste.
    """
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, GCSF_ILACLAR):
        return 'YOLAK2'
    if _iceriyor(m, YOLAK1_ILACLAR):
        return 'YOLAK1'
    return None


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOM: Sağlık kurulu raporu (A1 / B1)
# ═══════════════════════════════════════════════════════════════════════

def atom_saglik_kurulu_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """4.2.14.B: rapor bir SAĞLIK KURULU raporu olmalı (uzman hekim raporu değil).

    Tespit (kullanıcı kuralı 2026-06-03 — RaporTuruAdi + heyet birlikte):
      - rapor_turu 'kurul' içeriyor  VEYA  heyet ≥2 doktor  → VAR (sağlık kurulu)
      - rapor_turu açıkça 'uzman hekim' + heyet ≤1          → YOK (kurul değil)
      - hiç rapor sinyali yok (kod/takip/türü/heyet hepsi boş) → YOK (rapor zorunlu)
      - aksi (belirsiz)                                      → KE (manuel)
    """
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or
                               ilac_sonuc.get('rapor_turu_adi') or '')
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    heyet_n = len([h for h in heyet if (h.get('ad') or h.get('brans'))]) \
        if isinstance(heyet, (list, tuple)) else 0
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or
                   ilac_sonuc.get('rap_tak_no') or '').strip()

    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman' in rapor_turu) and ('kurul' not in rapor_turu)
    rapor_var = bool(rapor_kodu or rapor_takip or rapor_turu or heyet_n)

    if kurul_isaret:
        neden = f"Sağlık kurulu raporu ({rapor_turu or 'heyet ' + str(heyet_n) + ' uzman'})"
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=neden, kaynak='rapor_turu+heyet', grup=grup)
    if uzman_tek and heyet_n <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor "uzman hekim raporu" — 4.2.14.B sağlık '
                               'kurulu raporu ister (heyet ≤1)',
                         kaynak='rapor_turu+heyet', grup=grup)
    if not rapor_var:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı — 4.2.14.B SK '
                               'raporu zorunlu',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama türü/heyeti sağlık kurulu olarak '
                           'doğrulanamadı — manuel kontrol',
                     kaynak='rapor_turu+heyet', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK-1 atomları (Kanser/hormon — Fıkra 1)
# ═══════════════════════════════════════════════════════════════════════

def atom_uzman_hekim_recete(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A2: reçeteyi düzenleyen UZMAN hekim mi (pratisyen/aile hek. değil)?"""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden uzman hekim', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel doğrulama',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, PRATISYEN_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — 4.2.14.B uzman hekim ister',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden uzman hekim: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim branşı', kaynak='hekim_brans', grup=grup)


def atom_tedavi_protokolu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A3 (bilgi): raporda tedavi protokolü / kür / kemoterapi gösteriliyor mu?

    Parser zayıf — bilgi atomu (matematiği bozmaz). Bulunursa görsel destek.
    """
    metin = _rapor_metni(ilac_sonuc)
    isaretler = ['protokol', 'kur ', 'kür', 'kemoterapi', 'tedavi plani',
                 'tedavi protokol', 'siklus', 'rejim', 'kemoterapotik']
    bulundu = any(i in metin for i in isaretler)
    if bulundu:
        return SartSonuc(ad='Tedavi protokolü (rapor)', durum=SartDurumu.VAR,
                         neden='Raporda tedavi protokolü/kür ibaresi bulundu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Tedavi protokolü (rapor)', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Tedavi protokolü/kür ibaresi metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_kanser_teshisi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A4 (bilgi): kanser teşhisi (ICD C00–C97 / D00-D48) var mı?

    4.2.14.B endikasyon şartı koymuyor; bu atom destek/bilgi amaçlıdır.
    """
    teshisler: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh', 'teshis_kodu_listesi'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            teshisler.extend(str(x) for x in v if x)
        elif v:
            teshisler.append(str(v))
    birlesik = norm_tr_upper(' '.join(teshisler))
    # Kanser ICD: C00-C97 (malign), D00-D09 (in situ), D37-D48 (belirsiz davranış)
    import re as _re
    kanser = bool(_re.search(r'\bC\d{2}\b|\bC\d{2}\.', birlesik) or
                  _re.search(r'\bD0[0-9]\b|\bD3[7-9]\b|\bD4[0-8]\b', birlesik))
    if kanser:
        return SartSonuc(ad='Kanser teşhisi (ICD)', durum=SartDurumu.VAR,
                         neden='Malign/neoplazm ICD bulundu', kaynak='ICD', grup=grup)
    return SartSonuc(ad='Kanser teşhisi (ICD)', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Reçete/rapor teşhisinde kanser ICD okunamadı — manuel',
                     kaynak='ICD', grup=grup, sartli_atom=True)


def atom_oral_vinorelbin(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """A5 (bilgi, koşullu): oral vinorelbin → kür protokolünde belirtilmeli +
    tedaviye enjektabl form ile başlanmış olmalı. Sadece oral vinorelbin için."""
    m = _arama_metni(ilac_sonuc)
    if 'VINORELBIN' not in m:
        return None
    # Oral form sinyali (kapsül/oral)
    if not _iceriyor(m, ORAL_VINORELBIN_ISARET):
        return None
    return SartSonuc(
        ad='Oral vinorelbin: kür protokolü + enjektabl başlangıç',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Oral vinorelbin kür protokolünde belirtilmeli ve tedaviye '
              'enjektabl form ile başlanmalı — manuel doğrulama',
        kaynak='rapor_metni', grup=grup, sartli_atom=True)


def y1_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """YOLAK-1: Kanser/hormon ilaçları (Fıkra 1)."""
    sartlar: List[SartSonuc] = []
    # Gating atomlar (AND)
    sartlar.append(atom_saglik_kurulu_raporu(
        ilac_sonuc, grup='(1) Sağlık kurulu raporu'))
    sartlar.append(atom_uzman_hekim_recete(
        ilac_sonuc, grup='(1) Reçete eden uzman hekim'))
    # Bilgi atomları (matematiği bozmaz)
    sartlar.append(atom_tedavi_protokolu(
        ilac_sonuc, grup='(1) Tedavi protokolü (bilgi)'))
    sartlar.append(atom_kanser_teshisi(
        ilac_sonuc, grup='(1) Kanser endikasyonu (bilgi)'))
    a5 = atom_oral_vinorelbin(ilac_sonuc, grup='(1) Oral vinorelbin (bilgi)')
    if a5:
        sartlar.append(a5)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK-2 atomları (G-CSF — Fıkra 2)
# ═══════════════════════════════════════════════════════════════════════

def atom_heyet_uzman_var(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B2: heyette ≥1 uygun uzman var mı (7 branştan biri)?"""
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)) or not heyet:
        return SartSonuc(ad='Heyette uygun uzman (≥1/7)', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — manuel doğrulama',
                         kaynak='heyet', grup=grup, sartli_atom=True)
    bulunan = [h.get('brans') for h in heyet
               if _brans_listede(h.get('brans'), GCSF_HEYET_BRANSLAR)]
    if bulunan:
        return SartSonuc(ad='Heyette uygun uzman (≥1/7)', durum=SartDurumu.VAR,
                         neden=f"Heyette uygun branş: {', '.join(b for b in bulunan if b)}",
                         kaynak='heyet', grup=grup)
    branslar = ', '.join(h.get('brans') or '?' for h in heyet)
    return SartSonuc(ad='Heyette uygun uzman (≥1/7)', durum=SartDurumu.YOK,
                     neden=f'Heyette hematoloji/onkoloji/enfeksiyon/radyasyon onk./'
                           f'göğüs/üroloji/kadın doğum yok (heyet: {branslar})',
                     kaynak='heyet', grup=grup)


def atom_gcsf_recete_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B3: reçete eden hekim 9 izinli branştan biri mi?"""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden branş (9 izinli)', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel doğrulama',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, GCSF_RECETE_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='İzinli branş (hemat/onko/enf/radonk/göğüs/üro/'
                               'kadındoğum/iç hast./çocuk)', kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='9 izinli branştan biri olmalı', kaynak='hekim_brans', grup=grup)


def atom_rapor_6ay(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B4 (şartlı): rapor süresi 6 ay mı? rapor_sure_gun varsa hesapla.

    ~6 ay (150–210 gün) → VAR; belirgin >210 gün → YOK; veri yok → KE+şartlı.
    """
    sure = ilac_sonuc.get('rapor_sure_gun')
    try:
        sure = int(sure) if sure not in (None, '') else None
    except (TypeError, ValueError):
        sure = None
    if sure is None:
        return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor başlangıç/bitiş tarihi okunamadı — manuel',
                         kaynak='rapor_tarih', grup=grup, sartli_atom=True)
    if 150 <= sure <= 210:
        return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.VAR,
                         neden=f'Rapor süresi ~{sure} gün (≈6 ay)',
                         kaynak='rapor_tarih', grup=grup)
    if sure > 210:
        return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.YOK,
                         neden=f'Rapor süresi {sure} gün — 6 ayı aşıyor',
                         kaynak='rapor_tarih', grup=grup)
    # < 150 gün — kısa rapor, 6 aylık şarta tam oturmuyor ama engel değil → şartlı KE
    return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Rapor süresi {sure} gün — 6 aydan kısa, manuel doğrula',
                     kaynak='rapor_tarih', grup=grup, sartli_atom=True)


def atom_birer_aylik_doz(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B5 (şartlı): en fazla birer aylık doz. Kutu sayısı ile kaba hesap.

    Kutu ≤ ~makul aylık miktar → VAR; çok yüksek → KE (manuel, doz hesabı zor).
    """
    kutu = ilac_sonuc.get('kutu_sayisi')
    try:
        kutu = float(kutu) if kutu not in (None, '') else None
    except (TypeError, ValueError):
        kutu = None
    if kutu is None:
        kutu_s = (ilac_sonuc.get('kutu') or '').strip()
        try:
            kutu = float(kutu_s) if kutu_s else None
        except ValueError:
            kutu = None
    if kutu is None:
        return SartSonuc(ad='En fazla birer aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Kutu/doz bilgisi okunamadı — manuel doğrulama',
                         kaynak='doz', grup=grup, sartli_atom=True)
    # G-CSF doz şemaları değişkendir; kesin 1-aylık hesap güvenilmez. Makul
    # kutu adedi (≤6) bir aylık kullanım için tipik → VAR. Yüksek adet KE+şartlı
    # (birer aylık dozu aşma şüphesi — manuel doğrula). B5 asla YOK dönmez
    # (yanlış-pozitif UYGUN_DEĞİL riskini önler).
    if kutu <= 6:
        return SartSonuc(ad='En fazla birer aylık doz', durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {kutu:g} — birer aylık doz için makul',
                         kaynak='doz', grup=grup)
    return SartSonuc(ad='En fazla birer aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Kutu adedi {kutu:g} — birer aylık dozu aşıyor olabilir, '
                           f'manuel doğrula', kaynak='doz', grup=grup, sartli_atom=True)


def atom_lenograstim_pbpc(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """B6 (bilgi, koşullu): lenograstim günde >... flakon → yalnız PBPC mobilizasyonu.
    Sadece lenograstim için bilgi atomu olarak eklenir."""
    m = _arama_metni(ilac_sonuc)
    if not _iceriyor(m, LENOGRASTIM_ISARET):
        return None
    metin = _rapor_metni(ilac_sonuc)
    pbpc = ('mobilizasyon' in metin or 'kok hucre' in metin or
            'progenitor' in metin or 'periferik kan' in metin or 'aferez' in metin)
    if pbpc:
        return SartSonuc(ad='Lenograstim ≤4 flakon/gün (PBPC)', durum=SartDurumu.VAR,
                         neden='PBPC mobilizasyonu ibaresi var — günde 4 flakona kadar',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Lenograstim günde 4 flakon (yalnız PBPC)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Günde 4 flakon yalnız PBPC mobilizasyonunda mümkün — '
                           'kullanım amacı manuel doğrulanmalı',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def y2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """YOLAK-2: G-CSF (Fıkra 2)."""
    sartlar: List[SartSonuc] = []
    # Gating atomlar (AND)
    sartlar.append(atom_saglik_kurulu_raporu(
        ilac_sonuc, grup='(2) Sağlık kurulu raporu'))
    sartlar.append(atom_heyet_uzman_var(
        ilac_sonuc, grup='(2) Heyette uygun uzman (≥1/7)'))
    sartlar.append(atom_gcsf_recete_brans(
        ilac_sonuc, grup='(2) Reçete eden branş (9 izinli)'))
    # Şartlı atomları (hesaplamayı dene — kullanıcı kuralı 2026-06-03):
    # veri varsa kapı olarak değerlendirilir, yoksa KE+şartlı → SARTLI_UYGUN.
    sartlar.append(atom_rapor_6ay(
        ilac_sonuc, grup='(2) Rapor süresi 6 ay'))
    sartlar.append(atom_birer_aylik_doz(
        ilac_sonuc, grup='(2) Birer aylık doz'))
    b6 = atom_lenograstim_pbpc(ilac_sonuc, grup='(2) Lenograstim/PBPC (bilgi)')
    if b6:
        sartlar.append(b6)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup + veya_grubu + şartlı atom mantığı)
# ═══════════════════════════════════════════════════════════════════════

def _grup_degerlendir(gs: List[SartSonuc]) -> Tuple[str, bool]:
    """Bir grubu değerlendir → ('var'|'yok'|'ke', sadece_sartli_ke).

    veya_grubu=True → grup içi OR (≥1 VAR yeterli).
    veya_grubu=False → AND (hepsi VAR olmalı).
    """
    veya = any(s.veya_grubu for s in gs)
    durumlar = [s.durum for s in gs]
    ke_atomlar = [s for s in gs if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    ke_sartli = bool(ke_atomlar) and all(s.sartli_atom for s in ke_atomlar)
    if veya:
        if any(d == SartDurumu.VAR for d in durumlar):
            return ('var', False)
        if all(d == SartDurumu.YOK for d in durumlar):
            return ('yok', False)
        return ('ke', ke_sartli)
    # AND
    if any(d == SartDurumu.YOK for d in durumlar):
        return ('yok', False)
    if all(d == SartDurumu.VAR for d in durumlar):
        return ('var', False)
    return ('ke', ke_sartli)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    """SartSonuc listesinden genel sonuç (CLAUDE.md disiplini).

    '(bilgi)' grupları matematik dışı (görsel). Bir grup YOK → UYGUN_DEGIL.
    KE varsa: hepsi şartlı atom KE ise SARTLI_UYGUN, değilse ŞÜPHELİ.
    """
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)

    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI

    grup_sonuclari: List[str] = []
    sadece_sartli_ke = True
    for gs in gruplar.values():
        durum, sartli = _grup_degerlendir(gs)
        grup_sonuclari.append(durum)
        if durum == 'yok':
            sadece_sartli_ke = False
        elif durum == 'ke' and not sartli:
            sadece_sartli_ke = False

    if 'yok' in grup_sonuclari:
        return KontrolSonucu.UYGUN_DEGIL
    if 'ke' in grup_sonuclari:
        return (KontrolSonucu.SARTLI_UYGUN if sadece_sartli_ke
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    yolak_ad = {'YOLAK1': 'Kanser/hormon ilacı', 'YOLAK2': 'G-CSF'}.get(yolak, yolak)
    parcalar = [f"SUT 4.2.14.B / {yolak_ad}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

YOLAK_FN_MAP = {'YOLAK1': y1_kontrol, 'YOLAK2': y2_kontrol}

YOLAK_METADATA: Dict[str, Dict[str, str]] = {
    'YOLAK1': {'ad': 'Kanser/hormon ilaçları', 'sut': '4.2.14.B (1)'},
    'YOLAK2': {'ad': 'G-CSF (filgrastim/lenograstim/peg/lipeg)', 'sut': '4.2.14.B (2)'},
}


def kanser_gcsf_kontrol_4_2_14_b(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.14.B ana kontrol fonksiyonu.

    Akış:
      1. Etken madde → yolak belirle (dispatcher)
      2. Yolak fonksiyonu → SartSonuc[]
      3. Genel sonuç (UYGUN / ŞARTLI_UYGUN / ŞÜPHELİ / UYGUN_DEĞİL)
    """
    yolak = kanser_gcsf_yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.14.B kapsamı dışı — kanser/hormon veya G-CSF ilacı '
                  'tespit edilemedi',
            sut_kurali='SUT 4.2.14.B')

    yolak_fn = YOLAK_FN_MAP[yolak]
    sartlar = yolak_fn(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc,
        mesaj=mesaj,
        sut_kurali=f"SUT 4.2.14.B / {YOLAK_METADATA[yolak]['sut']}",
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'yolak_ad': YOLAK_METADATA[yolak]['ad']})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (CLAUDE.md §7.7 — ≥8 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # 1) Yolak-1 tam UYGUN: kurul raporu + onkolog reçete
        ("Y1 tam UYGUN (kurul + onkolog)", {
            'ilac_adi': 'XELODA', 'etkin_madde': 'KAPESITABIN',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Tıbbi Onkoloji',
            'rapor_kodu': '02.01', 'recete_teshisleri': ['C50.9'],
            'rapor_metni': 'tedavi protokolü kapesitabin küR', 'kutu': '1',
            'heyet_doktorlari': [{'brans': 'Tıbbi Onkoloji'}, {'brans': 'Genel Cerrahi'}],
        }, KontrolSonucu.UYGUN),
        # 2) Yolak-1: heyet>=2 ile kurul (rapor_turu boş) + uzman
        ("Y1 UYGUN (heyet≥2, türü boş)", {
            'ilac_adi': 'FEMARA', 'etkin_madde': 'LETROZOL',
            'doktor_uzmanligi': 'Kadın Hastalıkları ve Doğum',
            'rapor_kodu': '02.01', 'recete_teshisleri': ['C50.1'],
            'rapor_metni': 'protokol', 'kutu': '1',
            'heyet_doktorlari': [{'brans': 'Tıbbi Onkoloji'}, {'brans': 'Radyasyon Onkolojisi'}],
        }, KontrolSonucu.UYGUN),
        # 3) Yolak-1 UYGUN_DEGIL: pratisyen reçete
        ("Y1 UYGUN DEĞİL (pratisyen)", {
            'ilac_adi': 'ZOLADEX', 'etkin_madde': 'GOSERELIN',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Pratisyen Hekim',
            'rapor_kodu': '02.01', 'heyet_doktorlari': [{'brans': 'Üroloji'}, {'brans': 'Onkoloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 4) Yolak-1 UYGUN_DEGIL: uzman hekim raporu (kurul değil)
        ("Y1 UYGUN DEĞİL (uzman hekim raporu)", {
            'ilac_adi': 'TAXOL', 'etkin_madde': 'PAKLITAKSEL',
            'rapor_turu': 'Uzman Hekim Raporu', 'doktor_uzmanligi': 'Tıbbi Onkoloji',
            'rapor_kodu': '02.01', 'heyet_doktorlari': [{'brans': 'Tıbbi Onkoloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 5) Yolak-1 ŞÜPHELİ: rapor var ama türü/heyet belirsiz + branş bilinmiyor
        ("Y1 ŞÜPHELİ (belirsiz rapor+branş)", {
            'ilac_adi': 'GEMZAR', 'etkin_madde': 'GEMSITABIN',
            'rapor_kodu': '02.01', 'doktor_uzmanligi': '',
            'heyet_doktorlari': [{'brans': 'Tıbbi Onkoloji'}],  # heyet=1 → belirsiz
        }, KontrolSonucu.SARTLI_UYGUN),  # SK=KE(şartlı) + branş=KE(şartlı) → SARTLI
        # 6) Yolak-1 UYGUN_DEGIL: rapor hiç yok
        ("Y1 UYGUN DEĞİL (rapor yok)", {
            'ilac_adi': 'CASODEX', 'etkin_madde': 'BIKALUTAMID',
            'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        # 7) Yolak-2 tam UYGUN: kurul (heyet onkolog) + hematolog reçete + 6 ay
        ("Y2 tam UYGUN", {
            'ilac_adi': 'NEULASTA', 'etkin_madde': 'PEGFILGRASTIM',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Hematoloji',
            'rapor_kodu': '02.01', 'rapor_sure_gun': 180, 'kutu': '1',
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN),  # kutu=1 → B5 VAR; 6 ay VAR → tam UYGUN
        # 7b) Yolak-2 SARTLI: doz okunamadı (kutu yok)
        ("Y2 ŞARTLI (doz okunamadı)", {
            'ilac_adi': 'NEULASTA', 'etkin_madde': 'PEGFILGRASTIM',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Hematoloji',
            'rapor_kodu': '02.01', 'rapor_sure_gun': 180,
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.SARTLI_UYGUN),  # B5 doz KE+şartlı → SARTLI
        # 8) Yolak-2 UYGUN_DEGIL: heyette uygun uzman yok
        ("Y2 UYGUN DEĞİL (heyet uygunsuz)", {
            'ilac_adi': 'NEUPOGEN', 'etkin_madde': 'FILGRASTIM',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Hematoloji',
            'rapor_sure_gun': 180,
            'heyet_doktorlari': [{'brans': 'Ortopedi'}, {'brans': 'Genel Cerrahi'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 9) Yolak-2 UYGUN_DEGIL: reçete eden branş izinsiz
        ("Y2 UYGUN DEĞİL (reçete branşı izinsiz)", {
            'ilac_adi': 'GRANOCYTE', 'etkin_madde': 'LENOGRASTIM',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Ortopedi',
            'rapor_sure_gun': 180,
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'Onkoloji'}],
            'rapor_metni': 'periferik kan progenitör mobilizasyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        # 10) Yolak-2 UYGUN_DEGIL: rapor 6 ayı aşıyor
        ("Y2 UYGUN DEĞİL (rapor >6 ay)", {
            'ilac_adi': 'LONQUEX', 'etkin_madde': 'LIPEGFILGRASTIM',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Tıbbi Onkoloji',
            'rapor_sure_gun': 365, 'kutu': '1',
            'heyet_doktorlari': [{'brans': 'Tıbbi Onkoloji'}, {'brans': 'Enfeksiyon'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 11) Kapsam dışı
        ("Kapsam dışı (parasetamol)", {
            'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.14.B — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = kanser_gcsf_kontrol_4_2_14_b(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        isaret = "✓" if ok else "✗"
        print(f"{isaret} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
