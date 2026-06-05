# -*- coding: utf-8 -*-
"""SUT 4.2.3 — Enjektabl alerji aşılarının kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:4746-4767`` (mevzuat.gov.tr,
MevzuatNo=17229). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
KAPSAM (dispatcher: aşı tipi)
═══════════════════════════════════════════════════════════════════════════

  Kapsam ilaçları: alerjen ekstreleri / immünoterapi aşıları — ATC V01AA*.

  DİSPATCHER (iki yolak):
    venom mı?  (venom ticari ad ∨ "venom/arı venom" lafzı ∨ ICD T63.4* arı
                venom alerjisi)
       → evet  → Y_VENOM   (madde 7)  — uzman hekim raporu yeterli, SK gerekmez
       → hayır → Y_SOLUNUM (madde 1–5, 8) — sağlık kurulu raporu zorunlu

  ORTAK ROUTE GATE (madde 6):
    oral / sublingual form (STALORAL/GRAZAX/ORALAIR/ACARIZAX… ∨ "sublingual/
    dilaltı/oral/damla") → ödenmez → UYGUN DEĞİL.

═══════════════════════════════════════════════════════════════════════════
ATOMİK ŞARTLAR — Y_SOLUNUM (madde 1–5, 8)
═══════════════════════════════════════════════════════════════════════════

  R  — Route (md.6):       enjektabl (¬oral/sublingual)              [GATE]
  E  — Endikasyon (md.1):  alerjik astım ∨ alerjik rinit ∨           [VEYA]
                           alerjik konjonktivit
  SK — Rapor türü (md.1):  sağlık kurulu raporu (RaporTuruAdi)       [AND]
  H  — Heyet (md.1):       raporda immünoloji ∨ alerji hastalıkları  [AND]
                           ∨ immünoloji-alerji uzmanı
  P  — Reçete eden (md.1/4):
         İLK reçete   → immünoloji ∨ alerji ∨ immünoloji-alerji      [AND]
         DEVAM reçete → +çocuk/KBB/göz/göğüs/dermatoloji/iç hast./aile hek.
         (İLK/DEVAM hasta EOS geçmişinden tespit edilir)

  Bilgi/KE (parser zayıf → matematiği bozmaz):
    • duyarlılık (cilt testi ∨ spesifik IgE) + ≥3 ay medikal tedavi yetersizliği
      → başlangıç raporundan (EOS) okunur (md.1)                   [(bilgi)]
    • en fazla 2 farklı grup solunum alerjeni (md.2)               [(bilgi)]
    • her raporda ilk başlangıç tarihi (md.5)                      [(bilgi)]
    • toplam ≤5 yıl (md.8) — temporal, takip edilemez             [(bilgi)]

═══════════════════════════════════════════════════════════════════════════
ATOMİK ŞARTLAR — Y_VENOM (madde 7)
═══════════════════════════════════════════════════════════════════════════

  R  — Route:              enjektabl                                 [GATE]
  VE — Endikasyon:         arı venom alerjisi                        [AND]
  VR — Rapor (uzman hekim, SK DEĞİL): düzenleyen alerji ∨ immünoloji [AND]
                           ∨ immünoloji-alerji ∨ çocuk sağlığı uzmanı
  VP — Reçete eden:        uzman hekim                               [AND]
  (5 yıl sınırı YOK — md.8 "arı venom hariç")

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  Y_SOLUNUM:  UYGUN ⇔ R ∧ (E_astım ∨ E_rinit ∨ E_konj) ∧ SK ∧ H ∧ P
  Y_VENOM:    UYGUN ⇔ R ∧ VE ∧ VR ∧ VP

Sessizlik = KONTROL_EDİLEMEDİ (örtük kabul YASAK). Heyet/rapor türü EOS
enrichment ile (kanser_gcsf kalıbı); İLK/DEVAM EOS başlangıç dispatch ile
(sevelamer kalıbı). Tespit edilemeyen şartlar → KE+şartlı → ŞARTLI UYGUN.

Ana entrypoint: ``alerji_asisi_kontrol_4_2_3(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# KAPSAM — alerjen ekstreleri / immünoterapi aşıları (ATC V01AA*)
# ═══════════════════════════════════════════════════════════════════════
_ATC_RE = re.compile(r'V01AA')

# Solunum yolu alerjeni (enjektabl) ticari adlar
SOLUNUM_TICARI = {
    'ALUTARD', 'ALUSTAL', 'PHOSTAL', 'NOVO-HELISEN', 'NOVO HELISEN',
    'POLLINEX', 'PURETHAL', 'DEPIGOID', 'CLUSTOID', 'TYROSINE',
    'ALK SQ', 'ALLERGOVIT', 'AVANZ',
}
# Arı venom (enjektabl) ticari adlar
VENOM_TICARI = {
    'PHARMALGEN', 'VENOMIL', 'ALYOSTAL VENOM', 'ALK VENOM', 'VENOMENHAL',
    'RELESS VENOM', 'AQUAGEN VENOM', 'ALUTARD VENOM',
}
# Oral / sublingual (ödenmez — md.6) ticari adlar + form keyword'leri
ORAL_TICARI = {
    'STALORAL', 'GRAZAX', 'ORALAIR', 'ACARIZAX', 'SLITONE', 'SUBLIVAC',
    'ORALGEN', 'SLIT', 'ITULAZAX', 'STALLERGENES SUBLINGUAL',
}
_ORAL_KW = ('sublingual', 'dilalti', 'dil alti', 'oral form', 'oral damla',
            'agizdan', 'dil altina')


def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def alerji_asisi_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """ATC V01AA* veya bilinen alerji aşısı ticari adı."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if _ATC_RE.search(atc):
        return True
    m = _arama_metni(ilac_sonuc)
    return (_iceriyor(m, SOLUNUM_TICARI) or _iceriyor(m, VENOM_TICARI)
            or _iceriyor(m, ORAL_TICARI))


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _rapor_metni(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama', 'rap_ack'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_lower(' '.join(parcalar))


def _teshis_birlesik(ilac_sonuc: Dict) -> str:
    teshisler: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi', 'diger_raporlar_icd'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            teshisler.extend(str(x) for x in v if x)
        elif v:
            teshisler.append(str(v))
    return norm_tr_upper(' '.join(teshisler))


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _heyet_brans_listesi(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    out: List[str] = []
    for h in heyet:
        if isinstance(h, dict):
            b = h.get('brans') or ''
            if b:
                out.append(b)
        elif h:
            out.append(str(h))
    return out


# Branş kümeleri (norm_tr_lower alt-string)
IMMUN_ALERJI = ['immunoloji', 'alerji', 'allerji', 'immunoloji-alerji',
                'immunoloji ve alerji']
COCUK = ['cocuk', 'pediatri']
# md.4 devam reçetesi yazabilen ek branşlar
DEVAM_EK_BRANS = (COCUK + ['kulak burun', 'kbb', 'goz', 'oftalmoloji',
                           'gogus', 'dermatoloji', 'cildiye',
                           'ic hastalik', 'dahiliye', 'aile hek'])
# md.7 venom raporu düzenleyen branşlar
VENOM_RAPOR_BRANS = IMMUN_ALERJI + COCUK


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — venom mu, solunum mu, oral mı?
# ═══════════════════════════════════════════════════════════════════════

def _venom_mu(ilac_sonuc: Dict) -> bool:
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, VENOM_TICARI):
        return True
    if 'VENOM' in m or 'ARI VENOM' in m or 'ARI ZEHIR' in m:
        return True
    icd = _teshis_birlesik(ilac_sonuc)
    if re.search(r'\bT63\.?4', icd) or re.search(r'\bZ91\.?03', icd):
        return True
    metin = _rapor_metni(ilac_sonuc)
    return ('ari venom' in metin or 'venom aler' in metin
            or 'ari zehir' in metin or 'bal arisi' in metin)


def _oral_mu(ilac_sonuc: Dict) -> bool:
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, ORAL_TICARI):
        return True
    metin = _rapor_metni(ilac_sonuc)
    return any(k in metin for k in _ORAL_KW) or any(
        norm_tr_lower(k) in norm_tr_lower(m) for k in _ORAL_KW)


def _yolak(ilac_sonuc: Dict) -> str:
    """'VENOM' | 'SOLUNUM'."""
    return 'VENOM' if _venom_mu(ilac_sonuc) else 'SOLUNUM'


# ═══════════════════════════════════════════════════════════════════════
# ORTAK — Route gate (md.6)
# ═══════════════════════════════════════════════════════════════════════

GRUP_ROUTE = '(6) Enjektabl form (oral/sublingual ödenmez)'


def atom_route(ilac_sonuc: Dict) -> SartSonuc:
    if _oral_mu(ilac_sonuc):
        return SartSonuc(ad='Enjektabl form', durum=SartDurumu.YOK,
                         neden='Oral / sublingual alerji aşısı — SUT md.6 ödenmez',
                         kaynak='ilac_adi', grup=GRUP_ROUTE)
    return SartSonuc(ad='Enjektabl form', durum=SartDurumu.VAR,
                     neden='Oral/sublingual form ibaresi yok — enjektabl kabul',
                     kaynak='ilac_adi', grup=GRUP_ROUTE)


# ═══════════════════════════════════════════════════════════════════════
# Y_SOLUNUM — Endikasyon (md.1)  [VEYA]
# ═══════════════════════════════════════════════════════════════════════

GRUP_ENDIKASYON = '(1) Endikasyon: alerjik astım ∨ rinit ∨ konjonktivit (≥1)'


def _endikasyon_atom(varsa: bool, ad: str, neden_var: str) -> SartSonuc:
    if varsa:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden_var,
                         kaynak='ICD+rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                     neden='ICD/rapor metninde tespit edilmedi',
                     kaynak='ICD+rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)


def endikasyon_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    astim = bool(re.search(r'\bJ4[56]', icd)) or 'alerjik astim' in metin \
        or 'allerjik astim' in metin or ('astim' in metin and 'alerj' in metin)
    rinit = bool(re.search(r'\bJ30', icd)) or 'alerjik rinit' in metin \
        or 'allerjik rinit' in metin or 'allerjik nezle' in metin
    konj = bool(re.search(r'\bH10\.?1', icd)) or 'alerjik konjonktivit' in metin \
        or 'allerjik konjonktivit' in metin
    return [
        _endikasyon_atom(astim, 'Alerjik astım', 'Alerjik astım tespit edildi'),
        _endikasyon_atom(rinit, 'Alerjik rinit', 'Alerjik rinit tespit edildi'),
        _endikasyon_atom(konj, 'Alerjik konjonktivit',
                         'Alerjik konjonktivit tespit edildi'),
    ]


# ═══════════════════════════════════════════════════════════════════════
# Y_SOLUNUM — SK rapor türü (md.1)
# ═══════════════════════════════════════════════════════════════════════

GRUP_SK = '(1) Sağlık kurulu raporu (1 yıl süreli)'


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip()
                or _heyet_brans_listesi(ilac_sonuc))


def atom_sk_rapor(ilac_sonuc: Dict) -> SartSonuc:
    turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or '')
    if 'saglik kurul' in turu or 'kurul' in turu:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden='Rapor türü: sağlık kurulu', kaynak='rapor_turu',
                         grup=GRUP_SK)
    if turu and ('uzman hekim' in turu or 'uzman' in turu):
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor türü uzman hekim raporu — solunum alerjeni '
                               'için SUT md.1 sağlık kurulu raporu zorunlu',
                         kaynak='rapor_turu', grup=GRUP_SK)
    if not _rapor_var(ilac_sonuc):
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı',
                         kaynak='rapor', grup=GRUP_SK)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama türü (sağlık kurulu/uzman) '
                           'doğrulanamadı — manuel', kaynak='rapor_turu',
                     grup=GRUP_SK, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# Y_SOLUNUM — Heyet uzmanı (md.1)
# ═══════════════════════════════════════════════════════════════════════

GRUP_HEYET = '(1) Raporda immünoloji ∨ alerji ∨ immünoloji-alerji uzmanı'


def atom_heyet_uzman(ilac_sonuc: Dict) -> SartSonuc:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    adaylar = [rb] + _heyet_brans_listesi(ilac_sonuc)
    if any(_brans_listede(b, IMMUN_ALERJI) for b in adaylar):
        return SartSonuc(ad='İmmünoloji/alerji uzmanı (raporda)', durum=SartDurumu.VAR,
                         neden='Raporda immünoloji/alerji/immünoloji-alerji uzmanı',
                         kaynak='heyet', grup=GRUP_HEYET)
    if not any(adaylar):
        return SartSonuc(ad='İmmünoloji/alerji uzmanı (raporda)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti/branşı sistemde yok — manuel doğrula',
                         kaynak='heyet', grup=GRUP_HEYET, sartli_atom=True)
    return SartSonuc(ad='İmmünoloji/alerji uzmanı (raporda)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor branşları arasında immünoloji/alerji uzmanı '
                           'görülemedi — manuel doğrula', kaynak='heyet',
                     grup=GRUP_HEYET, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# Y_SOLUNUM — Reçete eden branş (md.1 İLK / md.4 DEVAM)
# ═══════════════════════════════════════════════════════════════════════

GRUP_PRESCRIBER = '(1/4) Reçete eden branş (İLK / DEVAM)'


def _ilk_mi(ilac_sonuc: Dict) -> Tuple[Optional[bool], str]:
    """Bu reçete İLK reçete mi (EOS başlangıç ordinalitesi)?

    Returns (ilk_mi, kaynak). ilk_mi None → tespit edilemedi.
    """
    bm = ilac_sonuc.get('baslangic_rapor_metni')
    if bm:
        return (False, 'önceki başlangıç raporu mevcut (devam)')
    durum = (ilac_sonuc.get('baslangic_durum') or '').strip().upper()
    if durum in ('BASLANGIC', 'AKTIF_ZATEN_BASLANGIC'):
        return (True, f'aktif reçete başlangıç ({durum})')
    if durum in ('DEVAM', 'BASKA_ECZANE_RISKI', 'YOK_EOS'):
        return (False, f'devam reçetesi ({durum})')

    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if hasta_tc:
        try:  # pragma: no cover - DB'ye bağlı
            from recete_kontrol.baslangic_rapor_bulucu import baslangic_raporu_bul
            aktif = _rapor_metni(ilac_sonuc)
            aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                           or ilac_sonuc.get('rap_tak_no') or '')
            anahtarlar = tuple(sorted(SOLUNUM_TICARI | VENOM_TICARI)) + (
                'ALERJEN', 'ALLERGEN', 'IMMUNOTERAPI', 'ASI')
            sonuc = baslangic_raporu_bul(
                hasta_tc, anahtarlar, aktif_rapor_takip_no=aktif_takip or None,
                aktif_rapor_metni=aktif)
            if sonuc:
                d = (sonuc.get('durum') or '').upper()
                if d == 'AKTIF_ZATEN_BASLANGIC':
                    return (True, 'EOS: aktif reçete başlangıç')
                if d in ('BULUNDU', 'BULUNDU_LAFIZ', 'BULUNDU_TABLO'):
                    return (False, f'EOS: önceki başlangıç bulundu ({d})')
        except Exception:  # pragma: no cover
            pass
    return (None, 'İLK/DEVAM tespit edilemedi — manuel')


def atom_recete_brans(ilac_sonuc: Dict) -> SartSonuc:
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    ilk, ilk_kaynak = _ilk_mi(ilac_sonuc)
    strict = _brans_listede(brans, IMMUN_ALERJI)
    devam_ek = _brans_listede(brans, DEVAM_EK_BRANS)

    if not bl:
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_PRESCRIBER, sartli_atom=True)
    # İmmünoloji/alerji → hem ilk hem devam için geçerli
    if strict:
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='İmmünoloji/alerji uzmanı — ilk ve devam için yetkili',
                         kaynak='hekim_brans', grup=GRUP_PRESCRIBER)
    # Genişletilmiş devam branşları (çocuk/KBB/göz/göğüs/derma/iç/aile)
    if devam_ek:
        if ilk is True:
            return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                             neden=f'İLK reçete yalnız immünoloji/alerji uzmanınca '
                                   f'yazılabilir ({ilk_kaynak})',
                             kaynak='hekim_brans', grup=GRUP_PRESCRIBER)
        if ilk is False:
            return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                             neden=f'Devam reçetesi — yetkili branş ({ilk_kaynak})',
                             kaynak='hekim_brans', grup=GRUP_PRESCRIBER)
        return SartSonuc(ad=f'Reçete eden: {brans}',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Devam branşı yetkili; ancak İLK reçete olup '
                               'olmadığı tespit edilemedi (ilk reçete bu branşta '
                               'geçersiz) — manuel', kaynak='hekim_brans',
                         grup=GRUP_PRESCRIBER, sartli_atom=True)
    # Hiçbir yetkili listede değil
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Reçete eden branş ne immünoloji/alerji ne de devam '
                           'reçetesi yetkili branşlarından',
                     kaynak='hekim_brans', grup=GRUP_PRESCRIBER)


# ═══════════════════════════════════════════════════════════════════════
# Y_SOLUNUM — Bilgi / KE atomları
# ═══════════════════════════════════════════════════════════════════════

def solunum_bilgi_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    corpus = _rapor_metni(ilac_sonuc)
    bm = ilac_sonuc.get('baslangic_rapor_metni')
    if bm:
        corpus = norm_tr_lower(str(bm) + ' ' + corpus)

    # duyarlılık + 3 ay medikal tedavi yetersizliği
    duyarlilik = ('cilt test' in corpus or 'deri test' in corpus
                  or 'prick' in corpus or 'spesifik ig' in corpus
                  or 'spesifik ige' in corpus or 'ig e' in corpus)
    uc_ay = bool(re.search(r'\b3\s*ay', corpus)) or 'uc ay' in corpus
    if duyarlilik and uc_ay:
        d1 = SartSonuc(ad='Duyarlılık (cilt testi/IgE) + ≥3 ay medikal tedavi',
                       durum=SartDurumu.VAR,
                       neden='Raporda duyarlılık testi + ≥3 ay medikal tedavi ibaresi',
                       kaynak='baslangic', grup='(bilgi) Başlangıç kriteri (md.1)')
    else:
        d1 = SartSonuc(ad='Duyarlılık (cilt testi/IgE) + ≥3 ay medikal tedavi',
                       durum=SartDurumu.KONTROL_EDILEMEDI,
                       neden='Başlangıç raporu duyarlılık/3 ay tedavi ibaresi '
                             'metinden okunamadı — manuel',
                       kaynak='baslangic', grup='(bilgi) Başlangıç kriteri (md.1)',
                       sartli_atom=True)
    return [
        d1,
        SartSonuc(ad='En fazla 2 farklı grup solunum alerjeni',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Alerjen grup sayısı (polen/akar/küf/hayvan epiteli) '
                        'metinden sayılamadı — manuel',
                  kaynak='-', grup='(bilgi) ≤2 alerjen grubu (md.2)',
                  sartli_atom=True),
        SartSonuc(ad='Raporda ilk başlangıç tarihi',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Tedaviye ilk başlangıç tarihi raporda belirtilmeli — manuel',
                  kaynak='-', grup='(bilgi) Başlangıç tarihi (md.5)',
                  sartli_atom=True),
        SartSonuc(ad='Toplam tedavi süresi ≤5 yıl',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Toplam tedavi süresi (≤5 yıl) takip edilemedi — manuel',
                  kaynak='-', grup='(bilgi) Toplam ≤5 yıl (md.8)',
                  sartli_atom=True),
    ]


# ═══════════════════════════════════════════════════════════════════════
# Y_VENOM atomları (md.7)
# ═══════════════════════════════════════════════════════════════════════

GRUP_VENOM_END = '(7) Arı venom alerjisi endikasyonu'
GRUP_VENOM_RAPOR = '(7) Uzman hekim raporu (alerji/immün/çocuk düzenler)'
GRUP_VENOM_RECETE = '(7) Reçete eden uzman hekim'


def atom_venom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    m = _arama_metni(ilac_sonuc)
    var = (bool(re.search(r'\bT63\.?4', icd)) or 'ari venom' in metin
           or 'venom aler' in metin or 'ari zehir' in metin or 'VENOM' in m)
    if var:
        return SartSonuc(ad='Arı venom alerjisi', durum=SartDurumu.VAR,
                         neden='Arı venom alerjisi endikasyonu tespit edildi',
                         kaynak='ICD+rapor', grup=GRUP_VENOM_END)
    return SartSonuc(ad='Arı venom alerjisi', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Arı venom alerjisi endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_VENOM_END, sartli_atom=True)


def atom_venom_rapor(ilac_sonuc: Dict) -> SartSonuc:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    adaylar = [rb] + _heyet_brans_listesi(ilac_sonuc)
    if any(_brans_listede(b, VENOM_RAPOR_BRANS) for b in adaylar):
        return SartSonuc(ad='Uzman hekim raporu (alerji/immün/çocuk)',
                         durum=SartDurumu.VAR,
                         neden='Rapor alerji/immünoloji/çocuk sağlığı uzmanınca',
                         kaynak='rapor_brans', grup=GRUP_VENOM_RAPOR)
    if not _rapor_var(ilac_sonuc) and not any(adaylar):
        return SartSonuc(ad='Uzman hekim raporu (alerji/immün/çocuk)',
                         durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
                         kaynak='rapor', grup=GRUP_VENOM_RAPOR)
    return SartSonuc(ad='Uzman hekim raporu (alerji/immün/çocuk)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş alerji/immün/çocuk '
                           'olarak doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_VENOM_RAPOR, sartli_atom=True)


_PRATISYEN = ('pratisyen', 'genel pratisyen', 'tabip')


def atom_venom_recete(ilac_sonuc: Dict) -> SartSonuc:
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden uzman hekim',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_VENOM_RECETE,
                         sartli_atom=True)
    if any(p in bl for p in _PRATISYEN) and 'uzman' not in bl:
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen hekim — venom aşısı uzman hekimce '
                               'reçete edilmeli (md.7)', kaynak='hekim_brans',
                         grup=GRUP_VENOM_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim branşı — venom reçetesi yetkili',
                     kaynak='hekim_brans', grup=GRUP_VENOM_RECETE)


# ═══════════════════════════════════════════════════════════════════════
# ŞART ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════

def _solunum_sartlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = [atom_route(ilac_sonuc)]
    s.extend(endikasyon_atomlar(ilac_sonuc))
    s.append(atom_sk_rapor(ilac_sonuc))
    s.append(atom_heyet_uzman(ilac_sonuc))
    s.append(atom_recete_brans(ilac_sonuc))
    s.extend(solunum_bilgi_atomlar(ilac_sonuc))
    return s


def _venom_sartlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_route(ilac_sonuc),
        atom_venom_endikasyon(ilac_sonuc),
        atom_venom_rapor(ilac_sonuc),
        atom_venom_recete(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (sevelamer 4.2.9.B kalıbı — AND-of-groups)
# ═══════════════════════════════════════════════════════════════════════

def _grup_degerlendir(gs: List[SartSonuc]) -> Tuple[str, bool]:
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
    if any(d == SartDurumu.YOK for d in durumlar):
        return ('yok', False)
    if all(d == SartDurumu.VAR for d in durumlar):
        return ('var', False)
    return ('ke', ke_sartli)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
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
    etiket = 'Arı venom' if yolak == 'VENOM' else 'Solunum alerjeni'
    parcalar = [f'SUT 4.2.3 / {etiket}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm şartlar sağlandı')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — hesaplanabilir şartlar VAR; '
                        f'{len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def alerji_asisi_kontrol_4_2_3(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.3 — Enjektabl alerji aşıları ana kontrol fonksiyonu."""
    if not alerji_asisi_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.3 kapsamı dışı — alerji aşısı (ATC V01AA*) değil',
            sut_kurali='SUT 4.2.3')

    yolak = _yolak(ilac_sonuc)
    if yolak == 'VENOM':
        sartlar = _venom_sartlar(ilac_sonuc)
    else:
        sartlar = _solunum_sartlar(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, sut_kurali='SUT 4.2.3',
        sartlar=sartlar, detaylar={'yolak': yolak, 'kontrol': 'alerji_asisi_4_2_3'})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥15 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    SK = 'Sağlık Kurulu Raporu'
    UZ = 'Uzman Hekim Raporu'
    imm_heyet = [{'ad': 'Dr A', 'brans': 'İmmünoloji ve Alerji Hastalıkları'}]
    return [
        # ── Kapsam ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01'},
         KontrolSonucu.ATLANDI),
        # ── ROUTE gate (md.6) ──
        ("Oral form UYGUN DEĞİL (STALORAL sublingual)", {
            'ilac_adi': 'STALORAL 300', 'atc_kodu': 'V01AA02',
            'rapor_turu': SK, 'recete_teshisleri': ['J30.1'],
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '1'},
         KontrolSonucu.UYGUN_DEGIL),
        # ── Y_SOLUNUM İLK reçete ──
        ("Solunum İLK UYGUN (immünoloji + SK + rinit + başlangıç)", {
            'ilac_adi': 'ALUTARD SQ', 'atc_kodu': 'V01AA03',
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_doktor_brans': 'İmmünoloji ve Alerji Hastalıkları',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '10', 'rapor_turu': SK,
            'recete_teshisleri': ['J30.1'], 'baslangic_durum': 'BASLANGIC',
            'rapor_metni': 'alerjik rinit cilt testi pozitif spesifik ige yuksek '
                           '3 ay medikal tedavi ile kontrol altina alinamadi'},
         KontrolSonucu.UYGUN),
        ("Solunum İLK UYGUN DEĞİL (ilk reçete aile hekimi)", {
            'ilac_adi': 'ALUTARD SQ', 'atc_kodu': 'V01AA03',
            'brans': 'Aile Hekimliği', 'rapor_doktor_brans': 'İmmünoloji',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '11', 'rapor_turu': SK,
            'recete_teshisleri': ['J45'], 'baslangic_durum': 'BASLANGIC'},
         KontrolSonucu.UYGUN_DEGIL),
        # ── Y_SOLUNUM DEVAM reçete ──
        ("Solunum DEVAM UYGUN (aile hekimi + SK + astım)", {
            'ilac_adi': 'PURETHAL', 'atc_kodu': 'V01AA02',
            'brans': 'Aile Hekimliği', 'rapor_doktor_brans': 'İmmünoloji',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '12', 'rapor_turu': SK,
            'recete_teshisleri': ['J45'], 'baslangic_durum': 'DEVAM'},
         KontrolSonucu.UYGUN),
        ("Solunum DEVAM UYGUN (göğüs hast. + SK + konjonktivit)", {
            'ilac_adi': 'POLLINEX', 'atc_kodu': 'V01AA10',
            'brans': 'Göğüs Hastalıkları', 'rapor_doktor_brans': 'Alerji Hastalıkları',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '13', 'rapor_turu': SK,
            'recete_teshisleri': ['H10.1'], 'baslangic_durum': 'BASKA_ECZANE_RISKI'},
         KontrolSonucu.UYGUN),
        # ── Y_SOLUNUM branş geçersiz ──
        ("Solunum UYGUN DEĞİL (kardiyoloji reçete — yetkisiz)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'Kardiyoloji', 'rapor_doktor_brans': 'İmmünoloji',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '14', 'rapor_turu': SK,
            'recete_teshisleri': ['J30.1'], 'baslangic_durum': 'DEVAM'},
         KontrolSonucu.UYGUN_DEGIL),
        # ── Y_SOLUNUM SK eksik ──
        ("Solunum UYGUN DEĞİL (uzman hekim raporu — SK değil)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_doktor_brans': 'İmmünoloji', 'heyet_doktorlari': imm_heyet,
            'rapor_kodu': '15', 'rapor_turu': UZ,
            'recete_teshisleri': ['J30.1'], 'baslangic_durum': 'BASLANGIC'},
         KontrolSonucu.UYGUN_DEGIL),
        # ── Y_SOLUNUM endikasyon yok ──
        ("Solunum UYGUN DEĞİL (endikasyon yok)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_doktor_brans': 'İmmünoloji', 'heyet_doktorlari': imm_heyet,
            'rapor_kodu': '16', 'rapor_turu': SK,
            'recete_teshisleri': ['Z00'], 'baslangic_durum': 'BASLANGIC'},
         KontrolSonucu.UYGUN_DEGIL),
        # ── Y_SOLUNUM heyet doğrulanamadı → ŞARTLI ──
        ("Solunum ŞARTLI (heyet branşı yok, SK var, devam)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'Kulak Burun Boğaz', 'rapor_kodu': '17', 'rapor_turu': SK,
            'recete_teshisleri': ['J30.1'], 'baslangic_durum': 'DEVAM'},
         KontrolSonucu.SARTLI_UYGUN),
        # ── Y_SOLUNUM ilk/devam bilinmiyor + devam branşı → ŞARTLI ──
        ("Solunum ŞARTLI (devam branşı ama ilk/devam bilinmiyor)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'Dermatoloji', 'rapor_doktor_brans': 'İmmünoloji',
            'heyet_doktorlari': imm_heyet, 'rapor_kodu': '18', 'rapor_turu': SK,
            'recete_teshisleri': ['J30.1']},
         KontrolSonucu.SARTLI_UYGUN),
        # ── Y_VENOM ──
        ("Venom UYGUN (alerji uzmanı rapor + uzman reçete)", {
            'ilac_adi': 'PHARMALGEN BEE VENOM', 'atc_kodu': 'V01AA07',
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_doktor_brans': 'Alerji Hastalıkları', 'rapor_kodu': '20',
            'rapor_turu': UZ, 'recete_teshisleri': ['T63.4']},
         KontrolSonucu.UYGUN),
        ("Venom UYGUN (çocuk sağlığı rapor + venom adı)", {
            'ilac_adi': 'VENOMIL ARI VENOM', 'atc_kodu': 'V01AA07',
            'brans': 'Çocuk Sağlığı ve Hastalıkları',
            'rapor_doktor_brans': 'Çocuk Sağlığı ve Hastalıkları',
            'rapor_kodu': '21', 'rapor_turu': UZ,
            'rapor_metni': 'ari venom alerjisi anafilaksi'},
         KontrolSonucu.UYGUN),
        ("Venom UYGUN DEĞİL (pratisyen reçete)", {
            'ilac_adi': 'PHARMALGEN', 'atc_kodu': 'V01AA07',
            'brans': 'Pratisyen', 'rapor_doktor_brans': 'Alerji Hastalıkları',
            'rapor_kodu': '22', 'rapor_turu': UZ,
            'recete_teshisleri': ['T63.4']},
         KontrolSonucu.UYGUN_DEGIL),
        ("Venom ŞARTLI (rapor düzenleyen kardiyoloji — branş doğrulanamadı)", {
            'ilac_adi': 'PHARMALGEN', 'atc_kodu': 'V01AA07',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'Kardiyoloji',
            'heyet_doktorlari': [{'ad': 'Dr X', 'brans': 'Kardiyoloji'}],
            'rapor_kodu': '23', 'rapor_turu': UZ, 'recete_teshisleri': ['T63.4']},
         KontrolSonucu.SARTLI_UYGUN),
        # ── Belirsiz solunum → ŞARTLI ──
        ("Solunum ŞARTLI (her şey var, heyet/SK belirsiz)", {
            'ilac_adi': 'ALUTARD', 'atc_kodu': 'V01AA03',
            'brans': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_kodu': '30', 'recete_teshisleri': ['J30.1'],
            'baslangic_durum': 'DEVAM'},
         KontrolSonucu.SARTLI_UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.3 — Enjektabl Alerji Aşıları — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = alerji_asisi_kontrol_4_2_3(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
