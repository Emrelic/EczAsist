# -*- coding: utf-8 -*-
"""SUT EK-4/F m.37.1 — Alprostadil 10 ve 20 mcg/ml (erektil disfonksiyon).

Resmî lafız (EK-4/F ek listesi, m.37.1):
    "Alprostadil 10 ve 20 mcg/ml: Yetişkin erkek hastalarda nörojenik,
     vaskülojenik, psikojenik ya da karışık etiyoloji kaynaklı erektil
     disfonksiyon tedavisinde veya erektil disfonksiyon teşhisinde diğer
     tanı testlerine yardımcı olarak kullanılması durumunda, üroloji uzman
     hekimlerince düzenlenen 1 yıl süreli uzman hekim raporuna istinaden
     üroloji uzman hekimlerince ilk reçetede tek doz olarak, yan etki
     oluşmayan hastalarda devamında bu durum reçetede belirtilerek en fazla
     2 haftalık dozlarda reçete edilmesi halinde bedelleri Kurumca karşılanır."

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ. Tek yolak (kontrendikasyon/NOT atomu yok), içinde
İLK reçete ⊻ DEVAM alt-dispatcher'ı var.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ A1(yetişkin≥18) ∧ A2(erkek)
          ∧ B1(ED endikasyonu: nöro∨vaskülo∨psiko∨karışık ∨ tanı-yardımcı)
          ∧ C1(rapor üroloji uzman hekimince düzenlenmiş)
          ∧ D1(reçete eden üroloji uzmanı)
          ∧ DOZ
          [bilgi: C3 rapor süresi 1 yıl]

  DOZ = ┌ İLK   (EOS'ta başlangıç rapor / geçmiş yok) → E1(tek doz)
        └ DEVAM (EOS'ta 2.+ rapor / "devam" ibaresi)  → E2a("yan etki yok/
                                                          devam" notu) ∧ E2b(≤2 hafta)

İLK/DEVAM dispatcher (kullanıcı kararı 2026-06-04): rapor ordinalitesi —
hastanın bu etkeni aldığı İLK (başlangıç) rapor → İLK; 2., 3. ve sonraki
raporlar → DEVAM. Sinyal sırası: EOS RaporAna ordinalitesi
(``recete_tipi_eos_bazli``) > reçete/rapor açıklamalarında "devam/yan etki"
ibaresi. EOS sessiz + ibare yok → İLK varsayılır (dispatcher_belirsiz notu).

Doz miktarı parse edilir (kullanıcı kararı 2026-06-04 "hesaplansın"):
  - İLK  → tek doz: adet == 1 → VAR; >1 → YOK
  - DEVAM→ ≤ 2 haftalık: on-demand max ~3/hafta kabulüyle ≤6 doz → VAR;
           >6 → KE (manuel); okunamazsa KE+şartlı.

Ana entrypoint: ``alprostadil_kontrol_ek4f_37_1(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — etken + ticari + ATC
# ═══════════════════════════════════════════════════════════════════════
# EK-4/F 37.1 yalnız 10/20 mcg/ml (intrakavernöz/üretral) erektil disfonksiyon
# formu. ATC G04BE01 = alprostadil (ürolojik). Neonatal/kardiyak IV form
# (C01EA01, duktus açıklığı) bu kapsamda DEĞİL — adult/erkek/ED gate'i
# zaten o formu eler.
ALPROSTADIL_ETKEN: Set[str] = {'ALPROSTADIL', 'ALPROSTADİL'}
ALPROSTADIL_TICARI: Set[str] = {
    'CAVERJECT', 'KAVERJECT', 'VITAROS', 'VIRIDAL', 'MUSE',
}
ATC_ALPROSTADIL_UROLOJIK = 'G04BE01'

# Üroloji branş anahtarları (norm_tr_lower substring)
UROLOJI = ['uroloji']  # 'üroloji' → norm_tr_lower → 'uroloji'

# Erektil disfonksiyon ICD-10 + metin sinyalleri
ED_ICD = ('N48.4', 'N484', 'F52.2', 'F522', 'N52')  # N52 = erkek erektil disfonksiyon
ED_METIN = (
    'erektil disfonksiyon', 'erektil disfonsiyon', 'ereksiyon bozuk',
    'sertlesme', 'sertleşme', 'empotans', 'impotans', 'iktidarsiz',
    'penil', 'kavernoz',
)
ED_ETIYOLOJI = {
    'norojenik': 'nörojenik',
    'vaskulojenik': 'vaskülojenik',
    'psikojenik': 'psikojenik',
    'karisik etiyoloji': 'karışık etiyoloji',
    'karisik tip': 'karışık',
}
ED_TANI_TEST = ('tani test', 'tanı test', 'tanisal', 'tanısal',
                'test yardim', 'yardimci olarak', 'farmakolojik test')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume: Set[str]) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


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


def _recete_aciklama_metni(ilac_sonuc: Dict) -> str:
    """Yalnız reçete açıklamaları + medula mesajı (devam ibaresi için)."""
    parcalar: List[str] = []
    for anahtar in ('recete_aciklamalari', 'rapor_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    for anahtar in ('mesaj_metni', 'rec_ack'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
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


def _yas_oku(ilac_sonuc: Dict) -> Optional[int]:
    """Hasta yaşı — yalnız DB alanından (rapor metninden yaş okuma YASAK)."""
    for anahtar in ('hasta_yasi', 'yas', 'hasta_yas'):
        v = ilac_sonuc.get(anahtar)
        if v in (None, ''):
            continue
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            continue
    return None


def _adet_oku(ilac_sonuc: Dict) -> Optional[float]:
    """Reçetedeki ampul/flakon (doz) adedi — kutu_sayisi/kutu/adet."""
    for anahtar in ('adet', 'kutu_sayisi', 'kutu', 'miktar'):
        v = ilac_sonuc.get(anahtar)
        if v in (None, ''):
            continue
        try:
            return float(str(v).replace(',', '.').strip())
        except (TypeError, ValueError):
            continue
    return None


def alprostadil_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """EK-4/F 37.1 alprostadil (ürolojik 10/20 mcg/ml) mı?"""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_ALPROSTADIL_UROLOJIK):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, ALPROSTADIL_ETKEN) or _iceriyor(m, ALPROSTADIL_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# İLK / DEVAM DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def _alprostadil_eos_keywords() -> Tuple[str, ...]:
    return tuple(sorted(ALPROSTADIL_ETKEN | ALPROSTADIL_TICARI))


def alprostadil_recete_tipi(ilac_sonuc: Dict) -> Tuple[str, str]:
    """İLK reçete mi DEVAM mı? → ('ILK'|'DEVAM', gerekçe).

    Sinyal sırası (kullanıcı kararı 2026-06-04):
      1) EOS RaporAna ordinalitesi (recete_tipi_eos_bazli) — en güvenilir.
         Aktif rapor en eski (1. sıra) → İLK; 2.+ sıra → DEVAM.
      2) Reçete/rapor açıklamalarında "devam"/"yan etki yok" ibaresi → DEVAM.
      3) Hiçbiri net değil → İLK varsayılır (dispatcher belirsiz notu).
    """
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('RaporAnaRaporTakipNo') or '').strip()

    # 1) EOS ordinalitesi
    if hasta_tc:
        try:
            from recete_kontrol.baslangic_rapor_bulucu import recete_tipi_eos_bazli
            tip, gerekce, _detay = recete_tipi_eos_bazli(
                hasta_tc, _alprostadil_eos_keywords(),
                aktif_rapor_takip_no=aktif_takip or None)
            if tip == 'BASLANGIC':
                return ('ILK', f'EOS: {gerekce}')
            if tip == 'DEVAM':
                return ('DEVAM', f'EOS: {gerekce}')
            # BELIRSIZ_EOS / YOK_EOS → ibareye düş
        except Exception:  # pragma: no cover - EOS yoksa
            pass

    # 2) Açıklama ibaresi
    ack = _recete_aciklama_metni(ilac_sonuc)
    devam_ibare = bool(re.search(r'\bdevam\b', ack)) or 'yan etki' in ack \
        or 'idame' in ack
    if devam_ibare:
        return ('DEVAM', 'Reçete/rapor açıklamasında "devam/yan etki" ibaresi')

    # 3) Belirsiz → İLK varsayımı
    return ('ILK', 'EOS\'ta geçmiş rapor bulunamadı ve açıklamada "devam" '
                   'ibaresi yok — ilk reçete varsayıldı (manuel doğrula)')


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_HASTA = '(1) Yetişkin erkek hasta'
GRUP_ENDIKASYON = '(2) Erektil disfonksiyon endikasyonu'
GRUP_RAPOR = '(3) Üroloji uzman hekim raporu'
GRUP_RAPOR_SURE = '(3) Rapor süresi 1 yıl (bilgi)'
GRUP_RECETE = '(4) Üroloji uzman hekimince reçete'
GRUP_DOZ_ILK = '(5) Doz — ilk reçete (tek doz)'
GRUP_DOZ_DEVAM = '(5) Doz — devam (≤2 haftalık + not)'


def atom_yetiskin(ilac_sonuc: Dict) -> SartSonuc:
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yetişkin (≥18 yaş)', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel doğrula',
                         kaynak='hasta_yas', grup=GRUP_HASTA, sartli_atom=True)
    if yas >= 18:
        return SartSonuc(ad=f'Yetişkin ({yas} yaş)', durum=SartDurumu.VAR,
                         neden='18 yaş ve üzeri', kaynak='hasta_yas', grup=GRUP_HASTA)
    return SartSonuc(ad=f'Yetişkin ({yas} yaş)', durum=SartDurumu.YOK,
                     neden='18 yaş altı — yetişkin değil', kaynak='hasta_yas', grup=GRUP_HASTA)


def atom_erkek(ilac_sonuc: Dict) -> SartSonuc:
    cins = norm_tr_lower(ilac_sonuc.get('cinsiyet') or ilac_sonuc.get('cins') or '')
    if not cins:
        return SartSonuc(ad='Erkek hasta', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Cinsiyet DB\'de yok — manuel doğrula',
                         kaynak='cinsiyet', grup=GRUP_HASTA, sartli_atom=True)
    erkek = ('erkek' in cins) or cins in ('e', 'm') or cins.startswith('erk')
    kadin = ('kadin' in cins) or cins in ('k', 'f') or cins.startswith('kad')
    if erkek and not kadin:
        return SartSonuc(ad='Erkek hasta', durum=SartDurumu.VAR,
                         neden=f'Cinsiyet: {cins}', kaynak='cinsiyet', grup=GRUP_HASTA)
    if kadin:
        return SartSonuc(ad='Erkek hasta', durum=SartDurumu.YOK,
                         neden=f'Cinsiyet: {cins} — erkek değil (ED endikasyonu erkeğe özel)',
                         kaynak='cinsiyet', grup=GRUP_HASTA)
    return SartSonuc(ad='Erkek hasta', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Cinsiyet belirsiz: {cins} — manuel doğrula',
                     kaynak='cinsiyet', grup=GRUP_HASTA, sartli_atom=True)


def atom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    """B1: erektil disfonksiyon endikasyonu (tedavi/tanı-yardımcı).

    Etiyoloji (nöro/vaskülo/psiko/karışık) ve tanı-test alt sinyalleri
    alt_liste'de bilgi olarak gösterilir; gating "ED var mı" üzerinden.
    """
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    icd_var = any(k in icd for k in ED_ICD)
    metin_var = any(k in metin for k in ED_METIN)

    # Bilgi alt-listesi (etiyoloji + tanı)
    alt: List[Tuple[str, str]] = []
    for kw, label in ED_ETIYOLOJI.items():
        alt.append((f'{label} etiyoloji', 'var' if kw in metin else 'kontrol_edilemedi'))
    tani_var = any(k in metin for k in ED_TANI_TEST)
    alt.append(('Tanı testine yardımcı', 'var' if tani_var else 'kontrol_edilemedi'))

    if icd_var or metin_var:
        neden_kaynak = ('ICD ' + next(k for k in ED_ICD if k in icd)) if icd_var \
            else 'rapor metni: erektil disfonksiyon'
        return SartSonuc(ad='Erektil disfonksiyon endikasyonu', durum=SartDurumu.VAR,
                         neden=neden_kaynak, kaynak='ICD+rapor',
                         grup=GRUP_ENDIKASYON, alt_liste=alt)
    return SartSonuc(ad='Erektil disfonksiyon endikasyonu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='ED tanısı (ICD N48.4/N52/F52.2 veya metin) okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_ENDIKASYON,
                     alt_liste=alt, sartli_atom=True)


def atom_rapor_uroloji(ilac_sonuc: Dict) -> SartSonuc:
    """C1: üroloji uzman hekimince düzenlenmiş uzman hekim raporu."""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans')
          or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _brans_listede(rb, UROLOJI):
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
                         kaynak='rapor', grup=GRUP_RAPOR)
    # Rapor var ama branş üroloji değil/bilinmiyor
    if rb:
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — üroloji değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş üroloji olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_RAPOR, sartli_atom=True)


def atom_rapor_suresi(ilac_sonuc: Dict) -> SartSonuc:
    """C3 (bilgi): 1 yıl süreli rapor. Tarih/metin parse zayıf → KE+şartlı."""
    from datetime import date, datetime
    bas = ilac_sonuc.get('rapor_baslangic_tarihi') or ilac_sonuc.get('rapor_bas_tarihi')
    bit = ilac_sonuc.get('rapor_bitis_tarihi') or ilac_sonuc.get('rapor_son_tarihi')

    def _parse(d):
        if isinstance(d, date):
            return d
        if not d:
            return None
        s = str(d).strip()
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt).date()
            except ValueError:
                continue
        return None

    d_bas, d_bit = _parse(bas), _parse(bit)
    if d_bas and d_bit:
        gun = (d_bit - d_bas).days
        if 330 <= gun <= 400:
            return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi {gun} gün — ~1 yıl',
                             kaynak='rapor_tarihleri', grup=GRUP_RAPOR_SURE)
        return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Rapor süresi {gun} gün — 1 yıl değil, manuel doğrula',
                         kaynak='rapor_tarihleri', grup=GRUP_RAPOR_SURE, sartli_atom=True)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'1\s*y[ıi]l|12\s*ay|360\s*g[üu]n', metin):
        return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.VAR,
                         neden='Rapor metninde "1 yıl/12 ay" ibaresi',
                         kaynak='rapor_metni', grup=GRUP_RAPOR_SURE)
    return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor tarihleri/süre ibaresi okunamadı — manuel',
                     kaynak='rapor_tarihleri', grup=GRUP_RAPOR_SURE, sartli_atom=True)


def atom_recete_uroloji(ilac_sonuc: Dict) -> SartSonuc:
    """D1: reçeteyi yazan hekim üroloji uzmanı."""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden hekim branşı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(brans, UROLOJI):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Üroloji uzmanı — yetkili', kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yalnız üroloji uzman hekimi reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def atom_doz_ilk(ilac_sonuc: Dict) -> SartSonuc:
    """E1: İlk reçetede tek doz (adet == 1)."""
    adet = _adet_oku(ilac_sonuc)
    if adet is None:
        return SartSonuc(ad='İlk reçete — tek doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_DOZ_ILK, sartli_atom=True)
    if adet <= 1:
        return SartSonuc(ad='İlk reçete — tek doz', durum=SartDurumu.VAR,
                         neden=f'Adet {adet:g} — tek doz', kaynak='doz', grup=GRUP_DOZ_ILK)
    return SartSonuc(ad='İlk reçete — tek doz', durum=SartDurumu.YOK,
                     neden=f'Adet {adet:g} — ilk reçetede yalnız tek doz karşılanır',
                     kaynak='doz', grup=GRUP_DOZ_ILK)


def atom_doz_devam_not(ilac_sonuc: Dict) -> SartSonuc:
    """E2a: Devam reçetesinde "yan etki yok / devam" ibaresi belirtilmiş."""
    ack = _recete_aciklama_metni(ilac_sonuc)
    not_var = bool(re.search(r'\bdevam\b', ack)) or 'yan etki' in ack or 'idame' in ack
    if not_var:
        return SartSonuc(ad='Reçetede "devam/yan etki yok" notu', durum=SartDurumu.VAR,
                         neden='Reçete/rapor açıklamasında devam ibaresi bulundu',
                         kaynak='recete_aciklama', grup=GRUP_DOZ_DEVAM)
    return SartSonuc(ad='Reçetede "devam/yan etki yok" notu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='SUT: devam reçetesinde bu durum reçetede belirtilmeli; '
                           'açıklamada ibare okunamadı — manuel doğrula',
                     kaynak='recete_aciklama', grup=GRUP_DOZ_DEVAM, sartli_atom=True)


def atom_doz_devam_miktar(ilac_sonuc: Dict) -> SartSonuc:
    """E2b: En fazla 2 haftalık doz (on-demand ~3/hafta → ≤6 doz kabulü)."""
    adet = _adet_oku(ilac_sonuc)
    if adet is None:
        return SartSonuc(ad='Devam — ≤2 haftalık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_DOZ_DEVAM, sartli_atom=True)
    if adet <= 6:
        return SartSonuc(ad='Devam — ≤2 haftalık doz', durum=SartDurumu.VAR,
                         neden=f'Adet {adet:g} — 2 haftalık (~≤6 doz) için makul',
                         kaynak='doz', grup=GRUP_DOZ_DEVAM)
    return SartSonuc(ad='Devam — ≤2 haftalık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Adet {adet:g} — 2 haftalık dozu aşıyor olabilir, manuel doğrula',
                     kaynak='doz', grup=GRUP_DOZ_DEVAM, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# ŞART LİSTESİ ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════

def _alprostadil_sartlari(ilac_sonuc: Dict, recete_tipi: str) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yetiskin(ilac_sonuc))
    s.append(atom_erkek(ilac_sonuc))
    s.append(atom_endikasyon(ilac_sonuc))
    s.append(atom_rapor_uroloji(ilac_sonuc))
    s.append(atom_recete_uroloji(ilac_sonuc))
    s.append(atom_rapor_suresi(ilac_sonuc))  # bilgi
    if recete_tipi == 'DEVAM':
        s.append(atom_doz_devam_not(ilac_sonuc))
        s.append(atom_doz_devam_miktar(ilac_sonuc))
    else:  # ILK
        s.append(atom_doz_ilk(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (eritropoietin kalıbı — grup bazlı)
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


def _mesaj_uret(sonuc: KontrolSonucu, recete_tipi: str,
                sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    tip_ad = {'ILK': 'ilk reçete (tek doz)', 'DEVAM': 'devam (≤2 hafta)'}.get(
        recete_tipi, recete_tipi)
    parcalar = [f'EK-4/F 37.1 Alprostadil / {tip_ad}']
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

def alprostadil_kontrol_ek4f_37_1(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.37.1 — Alprostadil 10/20 mcg/ml (erektil disfonksiyon)."""
    if not alprostadil_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F 37.1 kapsamı dışı — alprostadil (ürolojik) değil',
            sut_kurali='SUT EK-4/F m.37.1')

    recete_tipi, tip_gerekce = alprostadil_recete_tipi(ilac_sonuc)
    sartlar = _alprostadil_sartlari(ilac_sonuc, recete_tipi)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, recete_tipi, sartlar)

    detaylar = {
        'alt_grup': 'ALPROSTADIL',
        'sut_maddesi': 'EK-4/F 37.1',
        'recete_tipi': recete_tipi,
        'recete_tipi_gerekce': tip_gerekce,
        'ilac_adi': (ilac_sonuc.get('ilac_adi') or '').upper(),
        'etkin_madde': (ilac_sonuc.get('etkin_madde') or '').upper(),
        'sart_sayisi': len(sartlar),
        'verdict_sartlar': [
            {'ad': s.ad, 'durum': s.durum.value, 'neden': s.neden,
             'kaynak': s.kaynak, 'grup': s.grup, 'veya_grubu': s.veya_grubu,
             'sartli_atom': s.sartli_atom,
             'alt_liste': s.alt_liste}
            for s in sartlar
        ],
    }
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali='SUT EK-4/F m.37.1 — Alprostadil (erektil disfonksiyon)',
        aranan_ibare='yetişkin erkek + ED + üroloji uzman raporu + üroloji reçete + doz',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("İLK tam UYGUN (üroloji, erkek 45, ED, tek doz)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 45, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon vaskülojenik tedavi',
        }, KontrolSonucu.UYGUN),
        ("İLK UYGUN DEĞİL (tek doz değil, 3 adet)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 50, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '3',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (kadın hasta)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 40, 'cinsiyet': 'Kadın',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (18 yaş altı)", {
            'etkin_madde': 'CAVERJECT', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 16, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor branş üroloji değil)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 55, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Kardiyoloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (reçete eden üroloji değil)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 55, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji',
            'recete_hekim_uzmanligi': 'Dahiliye', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (yaş yok, diğer her şey VAR)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (ED endikasyonu okunamadı — şartlı atom)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 50, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['Z00.0'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'kontrol muayenesi',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("DEVAM UYGUN (açıklama 'devam', 4 adet)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 60, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234', 'kutu_sayisi': '4',
            'recete_aciklamalari': ['yan etki olmadı, tedaviye devam'],
            'rapor_metni': 'erektil disfonksiyon psikojenik',
        }, KontrolSonucu.UYGUN),
        ("DEVAM ŞARTLI (devam ibaresi var ama adet okunamadı)", {
            'etkin_madde': 'ALPROSTADIL', 'atc_kodu': 'G04BE01',
            'hasta_yasi': 60, 'cinsiyet': 'Erkek',
            'recete_teshisleri': ['N48.4'],
            'rapor_doktor_brans': 'Üroloji', 'doktor_uzmanligi': 'Üroloji',
            'rapor_kodu': '1234',
            'recete_aciklamalari': ['devam reçetesi'],
            'rapor_metni': 'erektil disfonksiyon',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("İLK UYGUN (ticari MUSE, ICD N52)", {
            'ilac_adi': 'MUSE 1000 MCG', 'etkin_madde': 'ALPROSTADIL',
            'hasta_yasi': 48, 'cinsiyet': 'E',
            'recete_teshisleri': ['N52.9'],
            'rapor_doktor_brans': 'ÜROLOJİ', 'doktor_uzmanligi': 'ÜROLOJİ',
            'rapor_kodu': '9', 'kutu_sayisi': '1',
            'rapor_metni': 'organik erektil disfonksiyon norojenik',
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F 37.1 Alprostadil — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = alprostadil_kontrol_ek4f_37_1(ilac_sonuc)
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
