# -*- coding: utf-8 -*-
"""SUT EK-4/F — İvermektin (2 endikasyon yolağı: paraziter enf. / uyuz).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — EK-4/F ek liste):

    1- İntestinal strongiloidiyaz (anguillulosis) tedavisinde veya Wuchereria
       bancrofti'ye bağlı lenfatik filariasisi olan hastalarda şüpheli ya da
       tanısı konmuş mikrofilaremi tedavisinde enfeksiyon hastalıkları ve
       klinik mikrobiyoloji uzman hekimlerince reçete edilmesi halinde,
    2- Önceki tedavinin (topikal tedavi) başarısız olduğu ve uyuz tanısının
       klinik olarak veya parazitolojik inceleme ile doğrulandığının reçete
       açıklama kısmında belirtilen insan sarkoptik uyuzunun tedavisinde
       enfeksiyon hastalıkları ve klinik mikrobiyoloji veya dermatoloji uzman
       hekimlerince reçete edilmesi halinde bedelleri Kurumca karşılanır.
    3- Kısa Ürün Bilgisinde (KÜB) yer alan pozolojisini aşmayacak dozda
       reçetelenecektir.

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

⚠️ Rapor GEREKMİYOR (raporsuz) — yalnız "reçete edilmesi" ibaresi var. Bu yüzden
hiçbir yolakta uzman hekim raporu atomu yoktur; yalnız REÇETE EDEN hekimin
branşı denetlenir (desmopressin kalıbı).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: endikasyon)
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ Y1 ∨ Y2

  Y1 (paraziter enfeksiyon):
        A1( strongiloidiyaz/anguillulosis
            ∨ (W. bancrofti lenfatik filariasis ∧ mikrofilaremi) )   [VEYA grubu]
      ∧ B1( reçete eden: enfeksiyon hastalıkları ve klinik mikrobiyoloji )
      ∧ D ( doz ≤ KÜB pozoloji )                                     [bilgi]

  Y2 (insan sarkoptik uyuzu):
        A2( uyuz / scabies / sarkoptik )
      ∧ C2( önceki topikal tedavi başarısız — reçete açıklamasında )
      ∧ C3( tanı klinik VEYA parazitolojik doğrulanmış — reçete açıkl. ) [VEYA grubu]
      ∧ B2( reçete eden: enfeksiyon hastalıkları ∨ dermatoloji )      [VEYA grubu]
      ∧ D ( doz ≤ KÜB pozoloji )                                     [bilgi]

Dispatcher: endikasyon sinyallerine göre yolak seçilir; ikisi de varsa reçete
branşı ile tiebreak; hiçbiri yoksa → KONTROL_EDILEMEDI (ŞÜPHELİ).

Örtük kabul yasağı (CLAUDE.md §2.5): Y2'de C2/C3 reçete açıklamasında lafzen
yoksa "şart sağlanıyor" varsayılmaz → KE+şartlı (manuel doğrula).

Ana entrypoint: ``ivermektin_kontrol_ek4f(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC P02CF01 ivermektin (sistemik antiparaziter)
# ═══════════════════════════════════════════════════════════════════════
ATC_IVERMEKTIN = 'P02CF01'
IVERMEKTIN_ETKEN: Set[str] = {'IVERMEKTIN', 'IVERMECTIN', 'IVERMEKTINE'}
# Topikal ivermektin (rozasea — Soolantra, D11AX22) bu SUT kapsamında DEĞİL;
# yine de aynı SUT lafzı sistemik formu hedefler. Ticari ad listesi dar tutuldu.
IVERMEKTIN_TICARI: Set[str] = {'STROMECTOL', 'IVEROTOX', 'IVERZINE', 'SCABO'}

# Branş anahtarları (norm_tr_lower substring)
ENFEKSIYON_BRANS = ('enfeksiyon', 'klinik mikrobiyoloji', 'mikrobiyoloji',
                    'infeksiyon')
DERMATOLOJI_BRANS = ('dermatoloji', 'deri ve zuhrevi', 'cildiye', 'deri hastalik')

# Endikasyon sinyalleri
# Y1 — strongiloidiyaz (B78) / lenfatik filariasis-W.bancrofti (B74.0)
Y1_ICD = ('B78', 'B78.0', 'B780', 'B78.1', 'B78.7', 'B78.9',
          'B74.0', 'B740', 'B74')
Y1_STRONGILO_METIN = ('strongiloidiyaz', 'strongyloidiaz', 'strongyloides',
                      'anguillulosis', 'anguillula', 'intestinal strongiloid')
Y1_FILARIA_METIN = ('filariasis', 'filaryazis', 'filaryasis', 'wuchereria',
                    'bancrofti', 'lenfatik filaria', 'mikrofilaremi',
                    'mikrofilari')
# Y2 — uyuz / scabies (B86)
Y2_ICD = ('B86', 'B860', 'B86.0')
Y2_METIN = ('uyuz', 'scabies', 'sarkoptik', 'sarcoptes', 'skabies')


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


def _serbest_metin(ilac_sonuc: Dict) -> str:
    """Endikasyon + açıklama metinleri (reçete + rapor) tek normalize string."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama', 'rap_ack',
                    'mesaj_metni'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_lower(' '.join(parcalar))


def _recete_aciklama(ilac_sonuc: Dict) -> str:
    """Yalnız REÇETE açıklaması — Y2'de 'reçete açıklama kısmında belirtilen'
    şartı bu kaynaktan aranır (rapor metni değil)."""
    parcalar: List[str] = []
    for anahtar in ('recete_aciklamalari', 'rec_ack', 'mesaj_metni'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
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


def _brans_listede(brans: Optional[str], anahtarlar) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _recete_brans(ilac_sonuc: Dict) -> str:
    return (ilac_sonuc.get('recete_hekim_uzmanligi')
            or ilac_sonuc.get('doktor_uzmanligi')
            or ilac_sonuc.get('brans') or '')


def ivermektin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_IVERMEKTIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, IVERMEKTIN_ETKEN) or _iceriyor(m, IVERMEKTIN_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — endikasyon yolağı
# ═══════════════════════════════════════════════════════════════════════

def _y1_sinyal(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    icd_var = any(k in icd for k in Y1_ICD)
    metin_var = (any(k in metin for k in Y1_STRONGILO_METIN)
                 or any(k in metin for k in Y1_FILARIA_METIN))
    return icd_var or metin_var


def _y2_sinyal(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    return any(k in icd for k in Y2_ICD) or any(k in metin for k in Y2_METIN)


def ivermektin_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """'Y1' (paraziter enf.) | 'Y2' (uyuz) | None (belirsiz)."""
    y1 = _y1_sinyal(ilac_sonuc)
    y2 = _y2_sinyal(ilac_sonuc)
    if y1 and not y2:
        return 'Y1'
    if y2 and not y1:
        return 'Y2'
    if y1 and y2:
        # tiebreak: reçete branşı dermatoloji ise uyuz daha olası
        rb = _recete_brans(ilac_sonuc)
        if _brans_listede(rb, DERMATOLOJI_BRANS):
            return 'Y2'
        return 'Y1'  # her ikisi de — paraziter enf. öncelik
    return None


# ═══════════════════════════════════════════════════════════════════════
# ORTAK doz atomu (madde 3 — KÜB pozoloji, parser zayıf → bilgi)
# ═══════════════════════════════════════════════════════════════════════

GRUP_DOZ = '(3) KÜB pozolojisini aşmayan doz (bilgi)'


def atom_doz_kub(ilac_sonuc: Dict) -> SartSonuc:
    """KÜB pozolojisi (ivermektin tipik ~200 mcg/kg tek doz). Kutu/doz parse'ı
    güvenilir değil → (bilgi) KE: matematiği bozmaz, manuel doğrulama notu."""
    return SartSonuc(
        ad='Doz KÜB pozolojisini aşmıyor', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='KÜB pozolojisi (kilo bazlı tek doz) otomatik doğrulanamadı — '
              'reçete dozu manuel kontrol edilmeli',
        kaynak='kutu/doz', grup=GRUP_DOZ, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 1 atomları (strongiloidiyaz / lenfatik filariasis)
# ═══════════════════════════════════════════════════════════════════════

GRUP_Y1_ENDIK = '(Y1) Endikasyon — strongiloidiyaz VEYA W.bancrofti filariasis (mikrofilaremi)'
GRUP_Y1_RECETE = '(Y1) Reçete: enfeksiyon hast. ve klinik mikrobiyoloji'


def atom_y1_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    strongilo = (any(k in metin for k in Y1_STRONGILO_METIN)
                 or any(c in icd for c in ('B78',)))
    filaria = (any(k in metin for k in Y1_FILARIA_METIN)
               or any(c in icd for c in ('B74.0', 'B740', 'B74')))
    mikrofil = ('mikrofilaremi' in metin or 'mikrofilari' in metin)
    # Filariasis için mikrofilaremi de gerekir; lafzen filariasis varsa ve
    # mikrofilaremi ibaresi yoksa ŞÜPHELİ (şüpheli/tanılı mikrofilaremi şartı).
    filaria_tam = filaria and (mikrofil or 'B74.0' in icd or 'B740' in icd)
    alt = [
        ('İntestinal strongiloidiyaz (anguillulosis)',
         'var' if strongilo else 'kontrol_edilemedi'),
        ('W. bancrofti lenfatik filariasis + mikrofilaremi',
         'var' if filaria_tam else ('kontrol_edilemedi' if filaria else 'yok')),
    ]
    if strongilo or filaria_tam:
        return SartSonuc(
            ad='Endikasyon (strongiloidiyaz / W.bancrofti mikrofilaremi)',
            durum=SartDurumu.VAR, veya_grubu=True,
            neden=('strongiloidiyaz' if strongilo
                   else 'W. bancrofti lenfatik filariasis + mikrofilaremi'),
            kaynak='ICD+metin', grup=GRUP_Y1_ENDIK, alt_liste=alt)
    if filaria and not mikrofil:
        return SartSonuc(
            ad='Endikasyon (strongiloidiyaz / W.bancrofti mikrofilaremi)',
            durum=SartDurumu.KONTROL_EDILEMEDI, veya_grubu=True,
            neden='Lenfatik filariasis var ancak mikrofilaremi (şüpheli/tanılı) '
                  'ibaresi okunamadı — manuel doğrula',
            kaynak='ICD+metin', grup=GRUP_Y1_ENDIK, alt_liste=alt,
            sartli_atom=True)
    return SartSonuc(
        ad='Endikasyon (strongiloidiyaz / W.bancrofti mikrofilaremi)',
        durum=SartDurumu.KONTROL_EDILEMEDI, veya_grubu=True,
        neden='Strongiloidiyaz / filariasis endikasyonu okunamadı — manuel',
        kaynak='ICD+metin', grup=GRUP_Y1_ENDIK, alt_liste=alt, sartli_atom=True)


def atom_y1_recete(ilac_sonuc: Dict) -> SartSonuc:
    rb = _recete_brans(ilac_sonuc)
    if not _brans_l(rb):
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_Y1_RECETE, sartli_atom=True)
    if _brans_listede(rb, ENFEKSIYON_BRANS):
        return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.VAR,
                         neden='Enfeksiyon hastalıkları ve klinik mikrobiyoloji — yetkili',
                         kaynak='hekim_brans', grup=GRUP_Y1_RECETE)
    return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.YOK,
                     neden='Yalnız enfeksiyon hastalıkları ve klinik mikrobiyoloji '
                           'uzmanı reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_Y1_RECETE)


def _y1_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_y1_endikasyon(ilac_sonuc),
        atom_y1_recete(ilac_sonuc),
        atom_doz_kub(ilac_sonuc),  # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 2 atomları (insan sarkoptik uyuzu)
# ═══════════════════════════════════════════════════════════════════════

GRUP_Y2_ENDIK = '(Y2) Endikasyon — insan sarkoptik uyuzu (scabies)'
GRUP_Y2_TOPIKAL = '(Y2) Önceki topikal tedavi başarısız (reçete açıklamasında)'
GRUP_Y2_TANI = '(Y2) Tanı klinik VEYA parazitolojik doğrulanmış (reçete açıklamasında)'
GRUP_Y2_RECETE = '(Y2) Reçete: enfeksiyon hast. VEYA dermatoloji'


def atom_y2_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    uyuz = any(k in metin for k in Y2_METIN) or any(c in icd for c in Y2_ICD)
    if uyuz:
        return SartSonuc(ad='İnsan sarkoptik uyuzu (scabies)', durum=SartDurumu.VAR,
                         neden='Uyuz/scabies tanısı', kaynak='ICD+metin',
                         grup=GRUP_Y2_ENDIK)
    return SartSonuc(ad='İnsan sarkoptik uyuzu (scabies)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Uyuz/scabies endikasyonu okunamadı — manuel',
                     kaynak='ICD+metin', grup=GRUP_Y2_ENDIK, sartli_atom=True)


def atom_y2_topikal_basarisiz(ilac_sonuc: Dict) -> SartSonuc:
    """Önceki topikal tedavi başarısız — REÇETE açıklamasında belirtilmeli.
    Sessiz ise örtük kabul yasağı (CLAUDE.md §2.5) → KE+şartlı."""
    metin = _recete_aciklama(ilac_sonuc)
    basarisiz_kw = ('basarisiz', 'yanit alinamadi', 'yanitsiz', 'etkisiz',
                    'cevap alinamadi', 'yetersiz yanit', 'gerilemedi',
                    'devam etmekte', 'persist', 'duzelmedi')
    topikal_kw = ('topikal', 'permetrin', 'permethrin', 'krem', 'losyon',
                  'lindan', 'benzil benzoat', 'kukurt', 'topik')
    topikal_var = any(k in metin for k in topikal_kw)
    basarisiz_var = any(k in metin for k in basarisiz_kw)
    if topikal_var and basarisiz_var:
        return SartSonuc(ad='Önceki topikal tedavi başarısız', durum=SartDurumu.VAR,
                         neden='Reçete açıklamasında topikal tedavi başarısızlığı belirtilmiş',
                         kaynak='recete_aciklama', grup=GRUP_Y2_TOPIKAL)
    if topikal_var or basarisiz_var:
        return SartSonuc(ad='Önceki topikal tedavi başarısız',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Topikal tedavi/başarısızlık ibaresinin biri eksik — '
                               'reçete açıklaması manuel doğrulanmalı',
                         kaynak='recete_aciklama', grup=GRUP_Y2_TOPIKAL,
                         sartli_atom=True)
    return SartSonuc(ad='Önceki topikal tedavi başarısız',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Reçete açıklamasında önceki topikal tedavi başarısızlığı '
                           'belirtilmemiş — manuel doğrula (örtük kabul edilmez)',
                     kaynak='recete_aciklama', grup=GRUP_Y2_TOPIKAL, sartli_atom=True)


def atom_y2_tani_dogrulama(ilac_sonuc: Dict) -> SartSonuc:
    """Tanı klinik VEYA parazitolojik inceleme ile doğrulanmış — REÇETE
    açıklamasında belirtilmeli. VEYA grubu içinde tek başına yeterli."""
    metin = _recete_aciklama(ilac_sonuc)
    klinik = ('klinik' in metin)
    parazitolojik = ('parazitolojik' in metin or 'parazitoloji' in metin
                     or 'mikroskop' in metin or 'kazinti' in metin
                     or 'deri kazinti' in metin or 'dermoskop' in metin)
    alt = [('Klinik olarak doğrulanmış', 'var' if klinik else 'kontrol_edilemedi'),
           ('Parazitolojik inceleme ile doğrulanmış',
            'var' if parazitolojik else 'kontrol_edilemedi')]
    if klinik or parazitolojik:
        return SartSonuc(ad='Tanı klinik / parazitolojik doğrulanmış',
                         durum=SartDurumu.VAR, veya_grubu=True,
                         neden=('parazitolojik inceleme' if parazitolojik
                                else 'klinik doğrulama'),
                         kaynak='recete_aciklama', grup=GRUP_Y2_TANI, alt_liste=alt)
    return SartSonuc(ad='Tanı klinik / parazitolojik doğrulanmış',
                     durum=SartDurumu.KONTROL_EDILEMEDI, veya_grubu=True,
                     neden='Reçete açıklamasında tanının klinik/parazitolojik '
                           'doğrulandığı belirtilmemiş — manuel doğrula',
                     kaynak='recete_aciklama', grup=GRUP_Y2_TANI, alt_liste=alt,
                     sartli_atom=True)


def atom_y2_recete(ilac_sonuc: Dict) -> SartSonuc:
    rb = _recete_brans(ilac_sonuc)
    if not _brans_l(rb):
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_Y2_RECETE, sartli_atom=True)
    if _brans_listede(rb, ENFEKSIYON_BRANS) or _brans_listede(rb, DERMATOLOJI_BRANS):
        return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.VAR, veya_grubu=True,
                         neden='Enfeksiyon hastalıkları / klinik mikrobiyoloji veya '
                               'dermatoloji — yetkili',
                         kaynak='hekim_brans', grup=GRUP_Y2_RECETE)
    return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.YOK, veya_grubu=True,
                     neden='Yalnız enfeksiyon hastalıkları ve klinik mikrobiyoloji '
                           'veya dermatoloji uzmanı reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_Y2_RECETE)


def _y2_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_y2_endikasyon(ilac_sonuc),
        atom_y2_topikal_basarisiz(ilac_sonuc),
        atom_y2_tani_dogrulama(ilac_sonuc),
        atom_y2_recete(ilac_sonuc),
        atom_doz_kub(ilac_sonuc),  # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (ortak grup-bazlı kalıp — fludrokortizon ile aynı)
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
    yolak_ad = {'Y1': 'strongiloidiyaz / W.bancrofti filariasis',
                'Y2': 'insan sarkoptik uyuzu (scabies)'}.get(yolak, yolak)
    parcalar = [f'EK-4/F İvermektin / {yolak_ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm şartlar sağlandı')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

YOLAK_FN = {'Y1': _y1_sartlari, 'Y2': _y2_sartlari}


def ivermektin_kontrol_ek4f(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F — İvermektin (strongiloidiyaz/filariasis / insan uyuzu)."""
    if not ivermektin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F İvermektin kapsamı dışı — ivermektin değil',
            sut_kurali='SUT EK-4/F İvermektin')

    yolak = ivermektin_yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='EK-4/F İvermektin — endikasyon (strongiloidiyaz/filariasis / '
                  'uyuz) tespit edilemedi — manuel doğrulama',
            sut_kurali='SUT EK-4/F İvermektin',
            sartlar=[SartSonuc(ad='Endikasyon (paraziter enf. / uyuz)',
                               durum=SartDurumu.KONTROL_EDILEMEDI,
                               neden='ICD/metinde endikasyon okunamadı',
                               kaynak='ICD+metin', grup='Endikasyon dispatcher',
                               sartli_atom=True)])

    sartlar = YOLAK_FN[yolak](ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'alt_grup': 'IVERMEKTIN',
        'sut_maddesi': 'EK-4/F İvermektin',
        'yolak': yolak,
        'ilac_adi': (ilac_sonuc.get('ilac_adi') or '').upper(),
        'etkin_madde': (ilac_sonuc.get('etkin_madde') or '').upper(),
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
        sut_kurali='SUT EK-4/F — İvermektin (strongiloidiyaz/filariasis / insan uyuzu)',
        aranan_ibare='endikasyon + reçete branşı (+ uyuzda topikal başarısız & '
                     'tanı doğrulama) + KÜB doz',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Y1 UYGUN (strongiloidiyaz + enfeksiyon reçete)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B78.0'], 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_aciklamalari': ['intestinal strongiloidiyaz tedavisi'],
        }, KontrolSonucu.UYGUN),  # doz (bilgi) genel sonuca dahil değil
        ("Y1 UYGUN DEĞİL (reçete eden dahiliye)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B78.0'], 'doktor_uzmanligi': 'İç Hastalıkları',
            'recete_aciklamalari': ['strongiloidiyaz'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (reçete eden dermatoloji — Y1'de yetkisiz)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B78.0'], 'doktor_uzmanligi': 'Dermatoloji',
            'recete_aciklamalari': ['anguillulosis'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 filariasis mikrofilaremi yok → ŞÜPHELİ endikasyon", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_aciklamalari': ['lenfatik filariasis wuchereria bancrofti'],
        }, KontrolSonucu.SARTLI_UYGUN),  # endikasyon KE-şartlı + doz KE-şartlı
        ("Y1 UYGUN (W.bancrofti + mikrofilaremi + enf. reçete)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B74.0'], 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_aciklamalari': ['wuchereria bancrofti lenfatik filariasis mikrofilaremi'],
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN (uyuz + topikal başarısız + parazitolojik + dermatoloji)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B86'], 'doktor_uzmanligi': 'Dermatoloji',
            'recete_aciklamalari': ['uyuz; topikal permetrin tedavisi başarısız; '
                                    'parazitolojik inceleme ile doğrulandı'],
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN (uyuz + topikal başarısız + klinik + enfeksiyon)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B86'], 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_aciklamalari': ['scabies klinik olarak doğrulandı topikal tedavi yanıt alınamadı'],
        }, KontrolSonucu.UYGUN),
        ("Y2 ŞÜPHELİ (uyuz ama topikal/tanı açıklaması yok)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B86'], 'doktor_uzmanligi': 'Dermatoloji',
            'recete_aciklamalari': ['uyuz'],
        }, KontrolSonucu.SARTLI_UYGUN),  # C2/C3 KE-şartlı → ŞARTLI
        ("Y2 UYGUN DEĞİL (uyuz + reçete eden çocuk hastalıkları)", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B86'], 'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
            'recete_aciklamalari': ['uyuz topikal başarısız parazitolojik doğrulandı'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon belirsiz → ŞÜPHELİ", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['Z00.0'], 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_aciklamalari': ['kontrol'],
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("Branş bilinmiyor (Y1) → ŞARTLI", {
            'etkin_madde': 'IVERMEKTIN', 'atc_kodu': 'P02CF01',
            'recete_teshisleri': ['B78.0'],
            'recete_aciklamalari': ['strongiloidiyaz'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("Ticari ad STROMECTOL + uyuz tam şart", {
            'ilac_adi': 'STROMECTOL 3 MG TABLET', 'etkin_madde': 'IVERMEKTIN',
            'recete_teshisleri': ['B86'], 'doktor_uzmanligi': 'Deri ve Zührevi Hastalıklar',
            'recete_aciklamalari': ['sarkoptik uyuz topikal lindan başarısız klinik doğrulandı'],
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F İvermektin — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = ivermektin_kontrol_ek4f(ilac_sonuc)
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
