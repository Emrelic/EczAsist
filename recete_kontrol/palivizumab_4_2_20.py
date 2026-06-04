# -*- coding: utf-8 -*-
"""SUT 4.2.20 — Palivizumab (RSV immünglobülini / SYNAGIS) kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:7328-7342`` (mevzuat.gov.tr,
MevzuatNo=17229; Değişik:RG-16/6/2020-31157 Mükerrer). EK-4/F Madde-52 aynı
4.2.20 esaslarına gönderir. Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` +
CLAUDE.md ``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
SUT LAFZI (özet)
═══════════════════════════════════════════════════════════════════════════
(1) Palivizumab; RSV sezonu boyunca (EKİM ile MART arası) çocuk alerjisi,
    çocuk immünolojisi ve alerji hastalıkları, çocuk enfeksiyon hastalıkları,
    çocuk göğüs hastalıkları, çocuk kardiyolojisi VEYA neonatoloji uzman
    hekimlerinden biri tarafından düzenlenen 1 YIL süreli uzman hekim raporuna
    dayanılarak; bu uzman hekimler VEYA çocuk sağlığı ve hastalıkları uzman
    hekimlerince EN FAZLA 5 DOZ ve MAKSİMUM 2 YAŞA KADAR reçete edilmesi
    halinde karşılanır.
(2) Yüksek risk taşıyan bebeklerde RSV'nin ciddi alt solunum yolu hastalığını
    önlemede aşağıdakilerden ≥1:
    a) takvim yaşı ≤12 ay ∧ (gebelik yaşı <29 0/7 hf ∨ doğum ağırlığı <1000 g)
       preterm,
    b) takvim yaşı ≤90 gün ∧ gebelik yaşı 29 0/7 – 31 6/7 hf preterm,
    c) RSV sezonu öncesi son 6 ayda kronik akciğer hastalığı için
       bronkodilatör ∨ oksijen ∨ diüretik ∨ kortikosteroid tedavilerinden ≥1
       alan, <2 yaş bebek,
    ç) <2 yaş; siyanotik doğuştan kalp hastalığı ∨ konjestif KY gerektiren
       asiyanotik doğuştan kalp hastalığı ∨ opere rezidiv hemodinamik bozukluk
       KY tedavisi devam ∨ pulmoner arteriyel hipertansiyon ∨ hemodinamik
       bozukluk kardiyomiyopatisi olan bebek.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  KARŞILANIR ⇔ P1 ∧ P2 ∧ P3 ∧ P4 ∧ (Q_a ∨ Q_b ∨ Q_c ∨ Q_ç)
               ∧ P5[bilgi] ∧ P6[bilgi]

  P1: Ekim–Mart RSV sezonunda reçete  (dönem dışı → UYGUN DEĞİL)
  P2: Yaş < 2 yıl (24 ay)             (≥2 yaş → UYGUN DEĞİL)
  P3: RAPOR düzenleyen uzman ∈ {çocuk alerji, çocuk immünoloji-alerji,
      çocuk enfeksiyon, çocuk göğüs, çocuk kardiyoloji, neonatoloji}
  P4: REÇETE eden ∈ P3 uzmanları ∨ çocuk sağlığı ve hastalıkları (pediatri)
  P5: 1 yıl süreli uzman hekim raporu  (bilgi/KE — manuel)
  P6: En fazla 5 doz                   (bilgi/KE — manuel)

Sessizlik = KONTROL_EDİLEMEDİ (örtük kabul YASAK). Gebelik haftası / doğum
ağırlığı / spesifik kalp tanıları yapısal veride çoğu kez bulunmadığından Q
atomları metin/ICD'de bulunamazsa `sartli_atom` ile KE → genel sonuç ŞARTLI
UYGUN. Branş (P3/P4) açıkça pediatrik dışı ise YOK → UYGUN DEĞİL.

Ana entrypoint: ``palivizumab_kontrol_4_2_20(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# KAPSAM — palivizumab tespiti
# ═══════════════════════════════════════════════════════════════════════
# ATC: J06BD01 (güncel WHO — antiviral monoklonal antikorlar) veya J06BB16
# (eski). Diğer spesifik immünglobulinleri (J06BB* genel) KAPSAMA ALMA —
# yalnız palivizumab. Ticari ad: SYNAGIS.
_ATC_RE = re.compile(r'J06B(?:B16|D01)')

PALIVIZUMAB_TICARI = {'SYNAGIS', 'PALIVIZUMAB'}


def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def palivizumab_kapsamda_mi(ilac_sonuc: Dict) -> bool:
    """ATC J06BD01/J06BB16 veya SYNAGIS/PALIVIZUMAB ad/etken lafzı."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if _ATC_RE.search(atc):
        return True
    m = _arama_metni(ilac_sonuc)
    return any(t in m for t in PALIVIZUMAB_TICARI)


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


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip())


def _rapor_brans(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('rapor_doktor_brans')
                         or ilac_sonuc.get('rapor_dr_brans') or '')


def _recete_brans(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('doktor_uzmanligi')
                         or ilac_sonuc.get('brans') or '')


def _yas_toplam_ay(ilac_sonuc: Dict) -> Optional[int]:
    """Hastanın yaşını AY cinsinden döndür.

    Kabul edilen biçimler: '8 AY', '18 AY', '1 YAS', '2 YIL', '0' (yıl),
    '1' (yıl). 'AY' geçiyorsa ay; aksi halde sayı yıl kabul edilip *12.
    """
    for anahtar in ('hasta_yasi', 'yas'):
        v = ilac_sonuc.get(anahtar)
        if v is None or v == '':
            continue
        s = norm_tr_upper(str(v))
        m = re.search(r'\d+', s)
        if not m:
            continue
        try:
            sayi = int(m.group())
        except ValueError:
            continue
        if 'AY' in s and 'YAS' not in s and 'YIL' not in s:
            return sayi
        return sayi * 12
    return None


def _recete_ay(ilac_sonuc: Dict) -> Optional[int]:
    """Reçete tarihinin ay'ı (1-12). rec_tar 'dd.mm.yyyy' / donem 'YYYY-MM'."""
    rt = (ilac_sonuc.get('rec_tar') or ilac_sonuc.get('recete_tarihi')
          or ilac_sonuc.get('tarih') or '').strip()
    m = re.match(r'\d{1,2}\.(\d{1,2})\.\d{4}', rt)
    if m:
        try:
            ay = int(m.group(1))
            if 1 <= ay <= 12:
                return ay
        except ValueError:
            pass
    donem = (ilac_sonuc.get('donem') or '').strip()  # 'YYYY-MM'
    m = re.match(r'\d{4}-(\d{1,2})', donem)
    if m:
        try:
            ay = int(m.group(1))
            if 1 <= ay <= 12:
                return ay
        except ValueError:
            pass
    return None


def _iceriyor(metin: str, anahtarlar) -> bool:
    return any(k in metin for k in anahtarlar)


# ═══════════════════════════════════════════════════════════════════════
# Branş eşleştirme
# ═══════════════════════════════════════════════════════════════════════
# norm_tr_upper sonrası: ç→C, ö→O, ş→S, ü→U, ğ→G, ı/İ→I.

def _brans_rapor_alt_uzman(b: str) -> bool:
    """RAPOR düzenleyebilen 6 alt-uzmanlık: çocuk alerji / çocuk immünoloji-
    alerji / çocuk enfeksiyon / çocuk göğüs / çocuk kardiyoloji ∨ neonatoloji."""
    if 'NEONATOLOJI' in b or 'YENIDOGAN' in b:
        return True
    if 'COCUK' in b:
        return any(k in b for k in ('ALERJI', 'IMMUNOLOJI', 'ENFEKSIYON',
                                    'GOGUS', 'KARDIYOLOJI'))
    return False


def _brans_recete_yetkili(b: str) -> bool:
    """REÇETE edebilen: 6 alt-uzman ∨ çocuk sağlığı ve hastalıkları (genel
    pediatri). Tüm 'çocuk ...' branşları + pediatri kabul edilir."""
    if _brans_rapor_alt_uzman(b):
        return True
    return ('COCUK' in b) or ('PEDIATRI' in b)


# ═══════════════════════════════════════════════════════════════════════
# Fıkra (1) — Genel kurallar (AND)
# ═══════════════════════════════════════════════════════════════════════

_RSV_SEZON_AYLAR = {10, 11, 12, 1, 2, 3}  # Ekim–Mart
_AY_AD = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
          7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}

_GRUP_P1 = '(4.2.20-1) RSV sezonu (Ekim–Mart)'
_GRUP_P2 = '(4.2.20-1) Maksimum 2 yaş'
_GRUP_P3 = '(4.2.20-1) Rapor düzenleyen uzman (6 alt-uzmandan biri)'
_GRUP_P4 = '(4.2.20-1) Reçete eden uzman (6 alt-uzman ∨ pediatri)'
_GRUP_Q = '(4.2.20-2) Yüksek risk endikasyonu (≥1)'


def atom_p1_sezon(ilac_sonuc: Dict) -> SartSonuc:
    ay = _recete_ay(ilac_sonuc)
    if ay is None:
        return SartSonuc(ad='Ekim–Mart RSV sezonunda reçete',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete tarihi okunamadı — manuel',
                         kaynak='rec_tar', grup=_GRUP_P1, sartli_atom=True)
    if ay in _RSV_SEZON_AYLAR:
        return SartSonuc(ad=f'Ekim–Mart RSV sezonunda reçete ({_AY_AD[ay]})',
                         durum=SartDurumu.VAR,
                         neden='Reçete RSV sezonu (Ekim-Mart) içinde',
                         kaynak='rec_tar', grup=_GRUP_P1)
    return SartSonuc(ad=f'Ekim–Mart RSV sezonunda reçete ({_AY_AD[ay]})',
                     durum=SartDurumu.YOK,
                     neden='Reçete RSV sezonu dışında (Nisan-Eylül) — karşılanmaz',
                     kaynak='rec_tar', grup=_GRUP_P1)


def atom_p2_yas(ilac_sonuc: Dict) -> SartSonuc:
    ay = _yas_toplam_ay(ilac_sonuc)
    if ay is None:
        return SartSonuc(ad='Maksimum 2 yaşa kadar (< 24 ay)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı bilinmiyor — manuel',
                         kaynak='DB_yas', grup=_GRUP_P2, sartli_atom=True)
    if ay < 24:
        return SartSonuc(ad=f'Maksimum 2 yaşa kadar ({ay} ay)',
                         durum=SartDurumu.VAR,
                         neden='2 yaşından küçük — yaş kriteri uygun',
                         kaynak='DB_yas', grup=_GRUP_P2)
    return SartSonuc(ad=f'Maksimum 2 yaşa kadar ({ay} ay)',
                     durum=SartDurumu.YOK,
                     neden='2 yaş ve üzeri — palivizumab yaş sınırı aşıldı',
                     kaynak='DB_yas', grup=_GRUP_P2)


def atom_p3_rapor_brans(ilac_sonuc: Dict) -> SartSonuc:
    b = _rapor_brans(ilac_sonuc)
    if not b:
        return SartSonuc(ad='Rapor: çocuk alerji/immün/enfeksiyon/göğüs/kardiyo ∨ neonatoloji',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor düzenleyen hekim branşı sistemde yok — manuel',
                         kaynak='rapor_doktor_brans', grup=_GRUP_P3, sartli_atom=True)
    if _brans_rapor_alt_uzman(b):
        return SartSonuc(ad=f'Rapor uzmanı yetkili ({b.title()})',
                         durum=SartDurumu.VAR,
                         neden='Rapor, 6 yetkili alt-uzmanlıktan biri tarafından düzenlenmiş',
                         kaynak='rapor_doktor_brans', grup=_GRUP_P3)
    return SartSonuc(ad=f'Rapor uzmanı yetkili ({b.title()})',
                     durum=SartDurumu.YOK,
                     neden='Rapor; çocuk alerji/immün/enfeksiyon/göğüs/kardiyo veya '
                           'neonatoloji dışı bir branşça düzenlenmiş',
                     kaynak='rapor_doktor_brans', grup=_GRUP_P3)


def atom_p4_recete_brans(ilac_sonuc: Dict) -> SartSonuc:
    b = _recete_brans(ilac_sonuc)
    if not b:
        return SartSonuc(ad='Reçete: yetkili 6 alt-uzman ∨ çocuk sağlığı ve hastalıkları',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı sistemde yok — manuel',
                         kaynak='brans', grup=_GRUP_P4, sartli_atom=True)
    if _brans_recete_yetkili(b):
        return SartSonuc(ad=f'Reçete eden yetkili ({b.title()})',
                         durum=SartDurumu.VAR,
                         neden='Reçete; yetkili alt-uzman veya çocuk sağlığı ve '
                               'hastalıkları uzmanınca düzenlenmiş',
                         kaynak='brans', grup=_GRUP_P4)
    return SartSonuc(ad=f'Reçete eden yetkili ({b.title()})',
                     durum=SartDurumu.YOK,
                     neden='Reçete; yetkili uzman (6 alt-uzman ∨ pediatri) dışı bir branşça',
                     kaynak='brans', grup=_GRUP_P4)


def bilgi_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        SartSonuc(ad='1 yıl süreli uzman hekim raporu',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Rapor süresi (1 yıl) parse edilemedi — manuel',
                  kaynak='-', grup='(bilgi) 1 yıl rapor süresi', sartli_atom=True),
        SartSonuc(ad='En fazla 5 doz',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Sezon boyu toplam doz (≤5) takibi yapılamadı — manuel',
                  kaynak='-', grup='(bilgi) En fazla 5 doz', sartli_atom=True),
    ]


# ═══════════════════════════════════════════════════════════════════════
# Fıkra (2) — Yüksek risk endikasyonu (OR ≥1)
# ═══════════════════════════════════════════════════════════════════════

def _q_atom(varsa: bool, ad: str, neden_var: str) -> SartSonuc:
    if varsa:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden_var,
                         kaynak='ICD+rapor', grup=_GRUP_Q, veya_grubu=True)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Endikasyon ICD/rapor metninde tespit edilemedi — manuel',
                     kaynak='ICD+rapor', grup=_GRUP_Q, veya_grubu=True,
                     sartli_atom=True)


def risk_endikasyon_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    s: List[SartSonuc] = []

    # Q_a — ≤12 ay ∧ (gebelik <29 hf ∨ doğum ağırlığı <1000 g)
    # P07.0 = aşırı düşük doğum ağırlığı (<1000 g), P07.2 = aşırı immatürite (<28 hf)
    qa_icd = bool(re.search(r'\bP07\.?[02]', icd))
    qa_kw = _iceriyor(metin, ('1000 g', '1000g', 'cok dusuk dogum agirlig',
                              'asiri dusuk dogum', 'asiri prematur', '29 haftadan kucuk',
                              'gebelik yasi 2', '<29', '28 hafta', '27 hafta',
                              '26 hafta', '25 hafta', '24 hafta'))
    s.append(_q_atom(
        qa_icd or qa_kw,
        'a) ≤12 ay + gebelik <29 hf VEYA doğum ağırlığı <1000 g preterm',
        'Çok düşük gebelik haftası (<29) veya doğum ağırlığı (<1000 g) ibaresi/ICD'))

    # Q_b — ≤90 gün ∧ gebelik 29 0/7 – 31 6/7 hf
    qb_kw = _iceriyor(metin, ('29-31 hafta', '29 - 31 hafta', '30 hafta', '31 hafta',
                              'gebelik yasi 30', 'gebelik yasi 31', 'gebelik yasi 29'))
    s.append(_q_atom(
        qb_kw,
        'b) ≤90 gün + gebelik yaşı 29 0/7 – 31 6/7 hf preterm',
        'Gebelik haftası 29–31 6/7 (orta preterm) ibaresi raporda'))

    # Q_c — <2 yaş ∧ kronik akciğer hastalığı ∧ son 6 ayda bronkodilatör ∨
    # oksijen ∨ diüretik ∨ kortikosteroid. P27.* = prematüriteden kaynaklanan
    # kronik solunum hastalığı (P27.1 = bronkopulmoner displazi).
    qc_akciger_icd = bool(re.search(r'\bP27|\bJ44|\bJ98', icd))
    qc_akciger_kw = _iceriyor(metin, ('kronik akciger', 'bronkopulmoner displazi',
                                      'bronkopulmoner displazisi', 'bpd',
                                      'kronik solunum'))
    qc_tedavi_kw = _iceriyor(metin, ('bronkodilator', 'oksijen tedavi', 'oksijen destek',
                                     'diuretik', 'kortikosteroid', 'steroid'))
    s.append(_q_atom(
        (qc_akciger_icd or qc_akciger_kw) and (qc_tedavi_kw or qc_akciger_icd),
        'c) <2 yaş + kronik akciğer hast. + son 6 ay bronkodilatör/oksijen/'
        'diüretik/kortikosteroid',
        'Kronik akciğer hastalığı (BPD vb.) + ilgili tedavi ibaresi/ICD'))

    # Q_ç — <2 yaş ∧ (siyanotik DKH ∨ asiyanotik DKH+KY ∨ opere rezidiv KY ∨
    # PAH ∨ hemodinamik kardiyomiyopati). Q20-Q26 doğuştan kalp/büyük damar
    # malformasyonları, I27.0/I27.2 PAH, I42.* kardiyomiyopati.
    qc2_icd = bool(re.search(r'\bQ2[0-6]|\bI27\.?[02]|\bI42', icd))
    qc2_kw = _iceriyor(metin, ('siyanotik', 'dogustan kalp', 'konjenital kalp',
                               'konjestif kalp', 'pulmoner arteriyel hipertansiyon',
                               'kardiyomiyopati', 'hemodinamik bozukluk',
                               'asiyanotik'))
    s.append(_q_atom(
        qc2_icd or qc2_kw,
        'ç) <2 yaş + doğuştan kalp hast. / konjestif KY / PAH / kardiyomiyopati',
        'Doğuştan kalp hastalığı / PAH / kardiyomiyopati ibaresi/ICD'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# Tüm şartlar
# ═══════════════════════════════════════════════════════════════════════

def palivizumab_sartlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_p1_sezon(ilac_sonuc))
    s.append(atom_p2_yas(ilac_sonuc))
    s.append(atom_p3_rapor_brans(ilac_sonuc))
    s.append(atom_p4_recete_brans(ilac_sonuc))
    s.extend(risk_endikasyon_atomlar(ilac_sonuc))
    s.extend(bilgi_atomlar(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (tüm gruplar AND; Fıkra-2 grubu iç-OR)
# ═══════════════════════════════════════════════════════════════════════

def _grup_durum(gs: List[SartSonuc]) -> Tuple[str, bool]:
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


def _and_birlestir(sonuclar: List[Tuple[str, bool]]) -> Tuple[str, bool]:
    if any(d == 'yok' for d, _ in sonuclar):
        return ('yok', False)
    ke = [(d, s) for d, s in sonuclar if d == 'ke']
    if ke:
        return ('ke', all(s for _, s in ke))
    return ('var', False)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)
    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI

    grup_sonuclari = [_grup_durum(gs) for gs in gruplar.values()]
    durum, sartli = _and_birlestir(grup_sonuclari)
    if durum == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    if durum == 'ke':
        return (KontrolSonucu.SARTLI_UYGUN if sartli
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['SUT 4.2.20 / Palivizumab (RSV)']
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

def palivizumab_kontrol_4_2_20(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.20 — Palivizumab (RSV) ana kontrol fonksiyonu."""
    if not palivizumab_kapsamda_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.20 kapsamı dışı — palivizumab (SYNAGIS) değil',
            sut_kurali='SUT 4.2.20')

    sartlar = palivizumab_sartlar(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, sut_kurali='SUT 4.2.20',
        sartlar=sartlar, detaylar={'kontrol': 'palivizumab_4_2_20'})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    UZMAN = 'Çocuk Göğüs Hastalıkları'
    NEO = 'Neonatoloji'
    PEDI = 'Çocuk Sağlığı ve Hastalıkları'
    return [
        # ── Kapsam ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01'}, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (hepatit B Ig J06BB04)", {
            'ilac_adi': 'HEPBBULIN', 'atc_kodu': 'J06BB04'}, KontrolSonucu.ATLANDI),
        # ── Tam UYGUN: sezon + yaş + branşlar + kardiyak endikasyon ──
        ("UYGUN (5 ay, Kasım, neonatoloji rapor, pedi reçete, Q20 DKH)", {
            'ilac_adi': 'SYNAGIS', 'atc_kodu': 'J06BD01', 'hasta_yasi': '5 AY',
            'rec_tar': '10.11.2025', 'rapor_doktor_brans': NEO, 'brans': PEDI,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN),
        ("UYGUN (8 ay, Ocak, çocuk göğüs rapor+reçete, BPD P27.1)", {
            'atc_kodu': 'J06BB16', 'hasta_yasi': '8 AY', 'rec_tar': '15.01.2026',
            'rapor_doktor_brans': UZMAN, 'brans': UZMAN,
            'recete_teshisleri': ['P27.1'],
            'rapor_metni': 'kronik akciger hastaligi oksijen tedavisi'},
         KontrolSonucu.UYGUN),
        ("UYGUN (1 yaş=12 ay sınır altı değil? 11 ay, PAH I27.0, Aralık)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '11 AY', 'rec_tar': '01.12.2025',
            'rapor_doktor_brans': 'Çocuk Kardiyolojisi', 'brans': 'Çocuk Kardiyolojisi',
            'recete_teshisleri': ['I27.0']}, KontrolSonucu.UYGUN),
        # ── Dönem dışı → UYGUN DEĞİL ──
        ("Dönem dışı UYGUN DEĞİL (5 ay, Temmuz, tam branş+endikasyon)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '5 AY', 'rec_tar': '15.07.2025',
            'rapor_doktor_brans': NEO, 'brans': PEDI,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN_DEGIL),
        # ── Yaş ≥ 2 → UYGUN DEĞİL ──
        ("Yaş ≥2 UYGUN DEĞİL (3 yaş, Kasım, tam branş)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '3 YAS', 'rec_tar': '10.11.2025',
            'rapor_doktor_brans': NEO, 'brans': PEDI,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN_DEGIL),
        ("Yaş 24 ay tam sınır UYGUN DEĞİL (Aralık)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '24 AY', 'rec_tar': '01.12.2025',
            'rapor_doktor_brans': NEO, 'brans': PEDI,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN_DEGIL),
        # ── Rapor branşı yetkisiz → UYGUN DEĞİL ──
        ("Rapor branşı yetkisiz UYGUN DEĞİL (kardiyoloji ERİŞKİN rapor)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '6 AY', 'rec_tar': '10.11.2025',
            'rapor_doktor_brans': 'Kardiyoloji', 'brans': PEDI,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN_DEGIL),
        ("Reçete branşı yetkisiz UYGUN DEĞİL (rapor neo, reçete dahiliye)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '6 AY', 'rec_tar': '10.11.2025',
            'rapor_doktor_brans': NEO, 'brans': 'İç Hastalıkları',
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.UYGUN_DEGIL),
        # ── Endikasyon sessiz → ŞARTLI (tüm branş+yaş+sezon VAR, Q hepsi KE) ──
        ("ŞARTLI (6 ay, Kasım, branşlar VAR, endikasyon sessiz)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '6 AY', 'rec_tar': '10.11.2025',
            'rapor_doktor_brans': NEO, 'brans': PEDI}, KontrolSonucu.SARTLI_UYGUN),
        # ── Branş sessiz → ŞARTLI ──
        ("ŞARTLI (5 ay, Aralık, branş yok ama endikasyon VAR Q21)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '5 AY', 'rec_tar': '01.12.2025',
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (yaş yok, Kasım, branşlar VAR, kardiyak endikasyon VAR)", {
            'atc_kodu': 'J06BD01', 'rec_tar': '10.11.2025',
            'rapor_doktor_brans': NEO, 'brans': NEO,
            'recete_teshisleri': ['Q21.0']}, KontrolSonucu.SARTLI_UYGUN),
        # ── Prematürite metin ibaresi → Q_a VAR ──
        ("UYGUN (4 ay, Şubat, neo rapor+reçete, <1000g ibaresi)", {
            'atc_kodu': 'J06BD01', 'hasta_yasi': '4 AY', 'rec_tar': '05.02.2026',
            'rapor_doktor_brans': NEO, 'brans': NEO,
            'rapor_metni': 'preterm bebek dogum agirligi 1000 g altinda'},
         KontrolSonucu.UYGUN),
        # ── Tümü sessiz (yaş yok, branş yok, endikasyon yok) → ŞARTLI ──
        ("ŞARTLI (sadece sezon VAR, kalan tümü sessiz)", {
            'atc_kodu': 'J06BD01', 'rec_tar': '20.10.2025'},
         KontrolSonucu.SARTLI_UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.20 — Palivizumab — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = palivizumab_kontrol_4_2_20(ilac_sonuc)
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
