# -*- coding: utf-8 -*-
"""SUT 4.2.19 — Migrende ilaç kullanım ilkeleri.

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:7321-7327, mevzuat.gov.tr
MevzuatNo=17229):

    "(1) Triptanlar, nöroloji uzman hekimleri tarafından reçete edilir. Bu
     grup ilaçlardan yalnız bir etken madde reçete edilebilir ve ayda en
     fazla 6 doz/adet yazılabilir. Aynı ilacın farklı farmasötik formlarının
     aynı anda reçete edilmesi halinde birisinin bedeli ödenir.
     (2) Topiramat tedavisine, diğer profilaktik migren ilaçlarının 6 ay
     süreyle kullanılıp etkisiz kaldığı durumlarda nöroloji uzman hekimince
     düzenlenen uzman hekim raporunda bu husus belirtilerek nöroloji uzman
     hekimince başlanır.
     (3) Uzman hekim raporu 1 yıl süreyle geçerlidir ve nöroloji uzman
     hekimince düzenlenen uzman hekim raporuna dayanılarak diğer hekimler
     tarafından en fazla birer aylık dozda reçete edilmesi halinde bedeli
     ödenir."

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
KAPSAM & DISPATCH (2 yolak)
═══════════════════════════════════════════════════════════════════════════
  Y_TRIPTAN   : triptanlar (ATC N02CC*) — akut migren atak tedavisi
  Y_TOPIRAMAT : topiramat (ATC N03AX11) — migren proflaksisi

  SUT 4.2.19 yalnız bu iki grubu sayar. Diğer migren proflaktikleri
  (propranolol, amitriptilin, flunarizin, CGRP-mAb erenumab vb.) bu madde
  kapsamında DEĞİL → ATLANDI.

  Topiramat aynı zamanda antiepileptiktir (N03AX11). Reçete/rapor teşhisi
  net olarak EPİLEPSİ (G40/G41) ve MİGREN (G43) yoksa → bu madde kapsamı
  dışı (epilepsi başka mevzuatla yönetilir) → ATLANDI.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  Y_TRIPTAN_UYGUN  ⇔ ( T1a: reçete eden nöroloji uzmanı
                       ∨ T1b: nöroloji uzmanınca düzenlenmiş rapor VAR )
                     ∧ ( T2: gruptan yalnız bir etken madde — başka triptan YOK )
                     ∧ ( T3: aylık doz/adet ≤ 6 )
                   ( T4 aynı-ilaç-farklı-form = bilgi, hesap dışı )

  Y_TOPIRAMAT_UYGUN ⇔ ( TP1: nöroloji uzmanınca düzenlenmiş uzman hekim raporu VAR )
                      ∧ ( TP2: "diğer proflaktik migren ilaçları 6 ay etkisiz"
                              ibaresi raporda VAR )
                      ∧ ( TP_end: migren endikasyonu VAR )
                    ( TP3 rapor 1 yıl, TP4 birer aylık doz = bilgi, hesap dışı )

  Mantık notu — Topiramatta rapor HER DURUMDA zorunlu (paragraf 2). Paragraf
  3 "diğer hekimler" reçete edebilir dediği için reçete eden branşı GATE
  DEĞİL — kapı nöroloji raporunun varlığıdır (glokom felsefesi). Triptanda
  rapor opsiyonel (nöroloji uzmanı doğrudan da yazar = T1a).

  Sessizlik (örtük kabul yasağı): TP2 ibaresi raporda yoksa "şart sağlandı"
  varsayılmaz → KONTROL_EDILEMEDI (şartlı). T1/TP1 branşı okunamazsa KE-şartlı.

Ana entrypoint: ``migren_kontrol_4_2_19(ilac_sonuc)`` → ``KontrolRaporu``.
Yolak tespiti : ``migren_yolak_belirle(ilac_sonuc)`` → 'TRIPTAN'|'TOPIRAMAT'|None
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ TESPİTİ — triptan (N02CC*) + topiramat (N03AX11)
# ═══════════════════════════════════════════════════════════════════════
ATC_TRIPTAN_PREFIX = 'N02CC'   # N02CC01..07 — selektif 5HT1 agonistleri
ATC_TOPIRAMAT = 'N03AX11'

# Triptan etken maddeleri — kanonik ad → eş anlamlı/ticari/ATC suffix kümesi.
# T2 ("yalnız bir etken madde") için diğer reçete kalemlerinde başka bir
# triptan ETKEN MADDESİ olup olmadığını bu haritayla tespit ederiz.
TRIPTAN_KANON: Dict[str, Set[str]] = {
    'SUMATRIPTAN': {'SUMATRIPTAN', 'IMIGRAN', 'SUMAMIGREN', 'SUMATRAN',
                    'MIGRANED', 'N02CC01'},
    'NARATRIPTAN': {'NARATRIPTAN', 'NARAMIG', 'N02CC02'},
    'ZOLMITRIPTAN': {'ZOLMITRIPTAN', 'ZOMIG', 'N02CC03'},
    'RIZATRIPTAN': {'RIZATRIPTAN', 'MAXALT', 'N02CC04'},
    'ALMOTRIPTAN': {'ALMOTRIPTAN', 'ALMOGRAN', 'N02CC05'},
    'ELETRIPTAN': {'ELETRIPTAN', 'RELPAX', 'RELERT', 'N02CC06'},
    'FROVATRIPTAN': {'FROVATRIPTAN', 'FROVA', 'N02CC07'},
}

TOPIRAMAT_ANAHTAR: Set[str] = {
    'TOPIRAMAT', 'TOPIRAMATE', 'TOPAMAX', 'TOPIRAX', 'EPITOP', 'TROKEN',
    'TPM', 'TOPALEX', 'TOPIRAN',
}

# Migren / epilepsi endikasyon anahtarları (norm_tr_upper substring + ICD)
MIGREN_ANAHTAR = ('MIGREN',)
MIGREN_ICD = ('G43',)
EPILEPSI_ANAHTAR = ('EPILEPSI', 'EPILEPTIK', 'KONVULSIYON')
EPILEPSI_ICD = ('G40', 'G41')

# Nöroloji branş anahtarları (norm_tr_lower substring)
NORO_BRANS = ('noroloji', 'norolji', 'sinir hastaliklari')


# ═══════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _atc(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _noro_uzmani_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in NORO_BRANS)


def _triptan_etken_belirle(metin_upper: str, atc: str = '') -> Optional[str]:
    """Verilen metin/ATC hangi triptan etken maddesine ait? Kanonik ad döner."""
    for kanon, esler in TRIPTAN_KANON.items():
        if atc:
            for e in esler:
                if e.startswith('N02CC') and atc.startswith(e):
                    return kanon
        if any(e in metin_upper for e in esler if not e.startswith('N02CC')):
            return kanon
    return None


def _endikasyon_metni(ilac_sonuc: Dict) -> str:
    """Reçete + rapor teşhis/açıklama metinlerini birleştir (endikasyon araması)."""
    parcalar: List[str] = []
    for k in ('rec_tesh', 'rap_tesh', 'rap_ack', 'rapor_metni',
              'teshis_tum', 'recete_teshisleri', 'rapor_aciklamalari',
              'recete_aciklamalari'):
        v = ilac_sonuc.get(k)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v)
        elif v:
            parcalar.append(str(v))
    return norm_tr_upper(' '.join(parcalar))


def _migren_var_mi(end_metin: str) -> bool:
    return _iceriyor(end_metin, MIGREN_ANAHTAR) or _iceriyor(end_metin, MIGREN_ICD)


def _epilepsi_var_mi(end_metin: str) -> bool:
    return _iceriyor(end_metin, EPILEPSI_ANAHTAR) or _iceriyor(end_metin, EPILEPSI_ICD)


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        s = str(v).strip().replace(',', '.')
        if not s:
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════
# KAPSAM / DISPATCH
# ═══════════════════════════════════════════════════════════════════════

def migren_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """SUT 4.2.19 kapsamı + yolak. İlaç bazlı (teşhis bakmaz).

    'TRIPTAN' | 'TOPIRAMAT' | None (kapsam dışı).
    """
    atc = _atc(ilac_sonuc)
    metin = _arama_metni(ilac_sonuc)
    if atc.startswith(ATC_TRIPTAN_PREFIX) or _triptan_etken_belirle(metin, atc):
        return 'TRIPTAN'
    if atc.startswith(ATC_TOPIRAMAT) or _iceriyor(metin, TOPIRAMAT_ANAHTAR):
        return 'TOPIRAMAT'
    return None


def migren_kapsami_mi(ilac_sonuc: Dict) -> bool:
    return migren_yolak_belirle(ilac_sonuc) is not None


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 1 — TRIPTAN (paragraf 1 + 3)
# ═══════════════════════════════════════════════════════════════════════
GRUP_T_YETKI = '(1) Yetki — nöroloji reçete VEYA nöroloji raporu'
GRUP_T_TEKETKEN = '(1) Gruptan yalnız bir etken madde'
GRUP_T_DOZ = '(1) Aylık doz/adet ≤ 6'
GRUP_T_FORM = '(bilgi) Aynı ilaç farklı farmasötik form'


def atom_t1a_recete_noro(ilac_sonuc: Dict) -> SartSonuc:
    """T1a: reçeteyi yazan hekim nöroloji uzmanı mı?"""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden nöroloji uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_T_YETKI,
                         veya_grubu=True, sartli_atom=True)
    if _noro_uzmani_mi(brans):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nöroloji uzmanı — triptan reçete edebilir',
                         kaynak='hekim_brans', grup=GRUP_T_YETKI, veya_grubu=True)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Nöroloji uzmanı değil — nöroloji raporu gerekir',
                     kaynak='hekim_brans', grup=GRUP_T_YETKI, veya_grubu=True)


def atom_t1b_rapor_noro(ilac_sonuc: Dict) -> SartSonuc:
    """T1b: nöroloji uzmanınca düzenlenmiş uzman hekim raporu VAR mı? (paragraf 3)"""
    rb = (ilac_sonuc.get('rapor_doktor_brans')
          or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _noro_uzmani_mi(rb):
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb} — diğer hekimler reçete edebilir',
                         kaynak='rapor_brans', grup=GRUP_T_YETKI, veya_grubu=True)
    if not rapor_var:
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı nöroloji raporu yok',
                         kaynak='rapor', grup=GRUP_T_YETKI, veya_grubu=True)
    if rb:
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — nöroloji değil',
                         kaynak='rapor_brans', grup=GRUP_T_YETKI, veya_grubu=True)
    return SartSonuc(ad='Nöroloji uzman hekim raporu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş nöroloji olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_T_YETKI, veya_grubu=True, sartli_atom=True)


def atom_t2_tek_etken(ilac_sonuc: Dict) -> SartSonuc:
    """T2: gruptan yalnız bir etken madde — diğer kalemde BAŞKA triptan YOK."""
    bu_etken = _triptan_etken_belirle(_arama_metni(ilac_sonuc), _atc(ilac_sonuc))
    digerleri = ilac_sonuc.get('recete_ilaclari') or []
    diger_etkenler: Set[str] = set()
    for it in digerleri:
        ad = it.get('ad') if isinstance(it, dict) else str(it)
        e = _triptan_etken_belirle(norm_tr_upper(ad or ''))
        if e and e != bu_etken:
            diger_etkenler.add(e)
    if diger_etkenler:
        return SartSonuc(ad='Yalnız bir triptan etken maddesi',
                         durum=SartDurumu.YOK,
                         neden='Reçetede başka triptan etkeni de var: '
                               + ', '.join(sorted(diger_etkenler)),
                         kaynak='recete_ilaclari', grup=GRUP_T_TEKETKEN)
    return SartSonuc(ad='Yalnız bir triptan etken maddesi', durum=SartDurumu.VAR,
                     neden=f'Tek triptan etkeni: {bu_etken or "—"}',
                     kaynak='recete_ilaclari', grup=GRUP_T_TEKETKEN)


def atom_t3_doz(ilac_sonuc: Dict) -> SartSonuc:
    """T3: ayda en fazla 6 doz/adet.

    Öncelik: GUI'nin hesapladığı aylık toplam (``triptan_aylik_toplam_adet``);
    yoksa satırın ``kutu`` (RIAdet) değeri. Net > 6 → YOK; net ≤ 6 → VAR;
    okunamazsa → KE-şartlı (manuel doz doğrulaması).
    """
    aylik = _to_int(ilac_sonuc.get('triptan_aylik_toplam_adet'))
    kaynak = 'aylik_toplam_adet'
    if aylik is None:
        aylik = _to_int(ilac_sonuc.get('kutu') or ilac_sonuc.get('adet'))
        kaynak = 'kutu'
    if aylik is None:
        return SartSonuc(ad='Aylık doz/adet ≤ 6', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete miktar/adet okunamadı — manuel doz kontrolü',
                         kaynak='miktar', grup=GRUP_T_DOZ, sartli_atom=True)
    if aylik > 6:
        return SartSonuc(ad='Aylık doz/adet ≤ 6', durum=SartDurumu.YOK,
                         neden=f'Aylık {aylik} adet/kutu > 6 — SUT sınırı aşıldı',
                         kaynak=kaynak, grup=GRUP_T_DOZ)
    return SartSonuc(ad='Aylık doz/adet ≤ 6', durum=SartDurumu.VAR,
                     neden=f'Aylık {aylik} adet/kutu ≤ 6',
                     kaynak=kaynak, grup=GRUP_T_DOZ)


def atom_t4_form(ilac_sonuc: Dict) -> SartSonuc:
    """T4 (bilgi): aynı ilacın farklı formları aynı anda → biri ödenir."""
    bu_etken = _triptan_etken_belirle(_arama_metni(ilac_sonuc), _atc(ilac_sonuc))
    digerleri = ilac_sonuc.get('recete_ilaclari') or []
    ayni_etken_baska_kalem = False
    for it in digerleri:
        ad = it.get('ad') if isinstance(it, dict) else str(it)
        e = _triptan_etken_belirle(norm_tr_upper(ad or ''))
        if e and e == bu_etken:
            ayni_etken_baska_kalem = True
            break
    if ayni_etken_baska_kalem:
        return SartSonuc(ad='Aynı ilaç farklı form', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Aynı etken ({bu_etken}) birden fazla kalemde — '
                               'farklı form ise yalnız birinin bedeli ödenir (manuel)',
                         kaynak='recete_ilaclari', grup=GRUP_T_FORM, sartli_atom=True)
    return SartSonuc(ad='Aynı ilaç farklı form', durum=SartDurumu.VAR,
                     neden='Tek kalem — form çakışması yok',
                     kaynak='recete_ilaclari', grup=GRUP_T_FORM)


def _triptan_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_t1a_recete_noro(ilac_sonuc),
        atom_t1b_rapor_noro(ilac_sonuc),
        atom_t2_tek_etken(ilac_sonuc),
        atom_t3_doz(ilac_sonuc),
        atom_t4_form(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 2 — TOPIRAMAT (paragraf 2 + 3)
# ═══════════════════════════════════════════════════════════════════════
GRUP_TP_RAPOR = '(2) Nöroloji uzman hekim raporu'
GRUP_TP_ETKISIZ = '(2) Diğer proflaktikler 6 ay etkisiz (raporda)'
GRUP_TP_END = '(2) Migren endikasyonu'
GRUP_TP_SURE = '(bilgi) Rapor 1 yıl geçerli'
GRUP_TP_DOZ = '(bilgi) Diğer hekim → birer aylık doz'

# "diğer profilaktik migren ilaçları 6 ay süreyle kullanılıp etkisiz kaldı"
# ibaresini yakalayan kalıplar (norm_tr_upper metinde aranır).
_RE_ETKISIZ = re.compile(
    r'(6\s*AY|ALTI\s*AY).{0,60}(ETKISIZ|YANIT\s*ALINAMA|YETERSIZ|CEVAP\s*ALINAMA|FAYDA\s*GORMEDI)'
    r'|(PROFLAKTIK|PROFILAKTIK|KORUYUCU).{0,80}(ETKISIZ|YETERSIZ|YANIT\s*ALINAMA)'
    r'|(ETKISIZ|YANIT\s*ALINAMA|YETERSIZ).{0,40}(6\s*AY|ALTI\s*AY)')


def atom_tp1_rapor_noro(ilac_sonuc: Dict) -> SartSonuc:
    """TP1: nöroloji uzmanınca düzenlenmiş uzman hekim raporu VAR mı? (zorunlu)"""
    rb = (ilac_sonuc.get('rapor_doktor_brans')
          or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if not rapor_var:
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Topiramat için rapor zorunlu — reçeteye bağlı rapor yok',
                         kaynak='rapor', grup=GRUP_TP_RAPOR)
    if _noro_uzmani_mi(rb):
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}',
                         kaynak='rapor_brans', grup=GRUP_TP_RAPOR)
    if rb:
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — nöroloji değil',
                         kaynak='rapor_brans', grup=GRUP_TP_RAPOR)
    return SartSonuc(ad='Nöroloji uzman hekim raporu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor var ama düzenleyen branş nöroloji olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_TP_RAPOR, sartli_atom=True)


def atom_tp2_etkisiz_ibare(ilac_sonuc: Dict) -> SartSonuc:
    """TP2: "diğer proflaktik migren ilaçları 6 ay etkisiz" ibaresi raporda mı?

    Örtük kabul yasağı: ibare bulunamazsa "sağlandı" varsayılmaz → KE-şartlı.
    """
    metin = _endikasyon_metni(ilac_sonuc)
    if _RE_ETKISIZ.search(metin):
        return SartSonuc(ad='Diğer proflaktikler 6 ay etkisiz (rapor)',
                         durum=SartDurumu.VAR,
                         neden='Raporda "6 ay diğer proflaktik etkisiz" ibaresi bulundu',
                         kaynak='rapor_metni', grup=GRUP_TP_ETKISIZ)
    return SartSonuc(ad='Diğer proflaktikler 6 ay etkisiz (rapor)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor metninde "6 ay diğer proflaktik etkisiz" ibaresi '
                           'tespit edilemedi — manuel doğrulama',
                     kaynak='rapor_metni', grup=GRUP_TP_ETKISIZ, sartli_atom=True)


def atom_tp_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    """TP_end: migren endikasyonu VAR mı? (topiramat migren bağlamında)"""
    metin = _endikasyon_metni(ilac_sonuc)
    if _migren_var_mi(metin):
        return SartSonuc(ad='Migren endikasyonu', durum=SartDurumu.VAR,
                         neden='Reçete/rapor teşhisinde migren bulundu',
                         kaynak='teshis', grup=GRUP_TP_END)
    return SartSonuc(ad='Migren endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Migren teşhisi metinde tespit edilemedi — manuel',
                     kaynak='teshis', grup=GRUP_TP_END, sartli_atom=True)


def atom_tp3_sure(ilac_sonuc: Dict) -> SartSonuc:
    """TP3 (bilgi): rapor 1 yıl geçerli (paragraf 3)."""
    return SartSonuc(ad='Rapor 1 yıl geçerli', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor geçerlilik süresi (1 yıl) — manuel kontrol',
                     kaynak='rapor', grup=GRUP_TP_SURE, sartli_atom=True)


def atom_tp4_doz(ilac_sonuc: Dict) -> SartSonuc:
    """TP4 (bilgi): diğer hekim reçete ederse en fazla birer aylık doz."""
    return SartSonuc(ad='Diğer hekim → birer aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Diğer hekimce reçete ise en fazla 1 aylık doz — manuel',
                     kaynak='miktar', grup=GRUP_TP_DOZ, sartli_atom=True)


def _topiramat_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_tp1_rapor_noro(ilac_sonuc),
        atom_tp2_etkisiz_ibare(ilac_sonuc),
        atom_tp_endikasyon(ilac_sonuc),
        atom_tp3_sure(ilac_sonuc),
        atom_tp4_doz(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup bazlı — glokom kalıbı; (bilgi) skip)
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
    ad = 'Triptan' if yolak == 'TRIPTAN' else 'Topiramat'
    parcalar = [f'SUT 4.2.19 Migren / {ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm zorunlu şartlar sağlandı')
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

def migren_kontrol_4_2_19(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.19 — Migrende ilaç kullanım ilkeleri kontrolü."""
    yolak = migren_yolak_belirle(ilac_sonuc)
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.19 kapsamı dışı — triptan (N02CC*) / topiramat değil',
            sut_kurali='SUT 4.2.19')

    # Topiramat dispatch: net epilepsi + migren yok → bu madde kapsamı dışı
    if yolak == 'TOPIRAMAT':
        end_metin = _endikasyon_metni(ilac_sonuc)
        if _epilepsi_var_mi(end_metin) and not _migren_var_mi(end_metin):
            return KontrolRaporu(
                sonuc=KontrolSonucu.ATLANDI,
                mesaj='SUT 4.2.19 kapsamı dışı — topiramat epilepsi bağlamında '
                      '(migren teşhisi yok); epilepsi ayrı mevzuatla yönetilir',
                sut_kurali='SUT 4.2.19')
        sartlar = _topiramat_sartlari(ilac_sonuc)
        aranan = ('nöroloji raporu ∧ "6 ay diğer proflaktik etkisiz" ibaresi '
                  '∧ migren endikasyonu')
    else:
        sartlar = _triptan_sartlari(ilac_sonuc)
        aranan = ('(reçete nöroloji ∨ nöroloji raporu) ∧ tek triptan etkeni '
                  '∧ aylık doz ≤ 6')

    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'alt_grup': yolak,
        'sut_maddesi': '4.2.19',
        'ilac_adi': (ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '').upper(),
        'etkin_madde': (ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '').upper(),
        'sart_sayisi': len(sartlar),
        'verdict_sartlar': [
            {'ad': s.ad, 'durum': s.durum.value, 'neden': s.neden,
             'kaynak': s.kaynak, 'grup': s.grup, 'veya_grubu': s.veya_grubu,
             'sartli_atom': s.sartli_atom, 'alt_liste': s.alt_liste}
            for s in sartlar
        ],
    }
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali='SUT 4.2.19 — Migrende ilaç kullanım ilkeleri',
        aranan_ibare=aranan, sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # ── TRIPTAN ──
        ("Triptan UYGUN (nöroloji reçete + 2 kutu)", {
            'etkin_madde': 'SUMATRIPTAN', 'atc_kodu': 'N02CC01',
            'doktor_uzmanligi': 'Nöroloji', 'kutu': '2',
        }, KontrolSonucu.UYGUN),
        ("Triptan UYGUN (dahiliye reçete + nöroloji raporu)", {
            'ilac_adi': 'ZOMIG', 'etkin_madde': 'ZOLMITRIPTAN', 'atc_kodu': 'N02CC03',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '123', 'kutu': '1',
        }, KontrolSonucu.UYGUN),
        ("Triptan UYGUN DEĞİL (dahiliye + rapor yok)", {
            'etkin_madde': 'RIZATRIPTAN', 'atc_kodu': 'N02CC04',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu': '1',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Triptan UYGUN DEĞİL (doz 8 > 6)", {
            'etkin_madde': 'ELETRIPTAN', 'atc_kodu': 'N02CC06',
            'doktor_uzmanligi': 'Nöroloji', 'kutu': '8',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Triptan UYGUN DEĞİL (iki farklı triptan etkeni)", {
            'etkin_madde': 'SUMATRIPTAN', 'atc_kodu': 'N02CC01',
            'doktor_uzmanligi': 'Nöroloji', 'kutu': '2',
            'recete_ilaclari': [{'ad': 'MAXALT 10 MG'}],  # rizatriptan
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Triptan ŞARTLI (nöroloji reçete + adet bilinmiyor)", {
            'etkin_madde': 'NARATRIPTAN', 'atc_kodu': 'N02CC02',
            'doktor_uzmanligi': 'Nöroloji',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Triptan ŞARTLI (branş bilinmiyor + 1 kutu)", {
            'etkin_madde': 'SUMATRIPTAN', 'atc_kodu': 'N02CC01', 'kutu': '1',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Triptan UYGUN (aynı etken 2 form — bilgi, hesabı bozmaz)", {
            'etkin_madde': 'SUMATRIPTAN', 'atc_kodu': 'N02CC01',
            'doktor_uzmanligi': 'Nöroloji', 'kutu': '2',
            'recete_ilaclari': [{'ad': 'IMIGRAN NAZAL SPREY'}],  # aynı etken farklı form
        }, KontrolSonucu.UYGUN),
        # ── TOPIRAMAT ──
        ("Topiramat UYGUN (nöro rapor + 6ay etkisiz + migren)", {
            'etkin_madde': 'TOPIRAMAT', 'atc_kodu': 'N03AX11',
            'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '55',
            'rap_ack': 'Migren proflaksisi. Diğer profilaktik ilaçlar 6 ay '
                       'kullanıldı, etkisiz kaldı.',
            'rec_tesh': 'G43.0 Migren',
        }, KontrolSonucu.UYGUN),
        ("Topiramat UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'TOPIRAMAT', 'atc_kodu': 'N03AX11',
            'doktor_uzmanligi': 'Nöroloji',
            'rec_tesh': 'G43 Migren',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Topiramat UYGUN DEĞİL (rapor kardiyoloji)", {
            'etkin_madde': 'TOPAMAX', 'atc_kodu': 'N03AX11',
            'rapor_doktor_brans': 'Kardiyoloji', 'rapor_kodu': '7',
            'rap_ack': 'Migren. 6 ay diğer proflaktik etkisiz.',
            'rec_tesh': 'Migren',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Topiramat ŞARTLI (nöro rapor + migren, ibare yok)", {
            'etkin_madde': 'TOPIRAMAT', 'atc_kodu': 'N03AX11',
            'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '9',
            'rec_tesh': 'G43 Migren',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Topiramat ATLANDI (epilepsi, migren yok)", {
            'etkin_madde': 'TOPIRAMAT', 'atc_kodu': 'N03AX11',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_kodu': '3', 'rec_tesh': 'G40.9 Epilepsi',
        }, KontrolSonucu.ATLANDI),
        # ── KAPSAM DIŞI ──
        ("Kapsam dışı (propranolol — diğer proflaktik)", {
            'etkin_madde': 'PROPRANOLOL', 'atc_kodu': 'C07AA05',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.19 Migren — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = migren_kontrol_4_2_19(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} :: {s.neden}")
    print("=" * 64)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
