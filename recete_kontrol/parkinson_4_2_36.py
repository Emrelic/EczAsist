# -*- coding: utf-8 -*-
"""SUT 4.2.36 — Parkinson tedavisinde ilaç kullanım ilkeleri (+ EK-4/F m.50).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:8204-8215`` (mevzuat.gov.tr,
MevzuatNo=17229). EK-4/F Madde-50 (Amantadin Sülfat oral — influenza A
profilaksi) ek listede. Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` +
CLAUDE.md ``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
BEŞ YOLAK (dispatcher: etken madde → yolak; amantadin sülfat alt-dispatcher)
═══════════════════════════════════════════════════════════════════════════

  Y1 → 4.2.36(1): Apomorfin, kabergolin, entakapon (ve kombinasyonları=Stalevo),
        rasajilin, pergolid mezilat, pramipeksol HCl, bornaprin HCl, ropinirol.
  Y2 → 4.2.36(2): Tolkapon.
  Y3 → 4.2.36(3): Amantadin SÜLFAT — parkinson / ilaca bağlı EPS reaksiyon.
  Y4 → 4.2.36(4): Amantadin HİDROKLORÜR — yalnız parkinson.
  Y5 → EK-4/F m.50: Amantadin SÜLFAT oral — influenza A profilaksi.

  Amantadin sülfat alt-dispatcher: influenza/grip endikasyonu → Y5;
  aksi halde (parkinson/EPS varsayılan) → Y3.

═══════════════════════════════════════════════════════════════════════════
ORTAK ÇEKİRDEK ATOM (Y1 = Y3 = Y4)
═══════════════════════════════════════════════════════════════════════════

  UZMAN_YETKİ ⇔ (reçeteci ∈ {nöroloji, geriatri})
              ∨ (uzman_hekim_raporu_VAR ∧ rapor_düzenleyen ∈ {nöroloji, geriatri})
  → tek `veya_grubu` (≥1 yol VAR yeterli).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  Y1 ⇔ UZMAN_YETKİ
  Y3 ⇔ ENDİKASYON(parkinson ∨ EPS-reaksiyon) ∧ UZMAN_YETKİ
  Y4 ⇔ ENDİKASYON(yalnız parkinson) ∧ UZMAN_YETKİ ; parkinson-dışı ⇒ UYGUN_DEĞİL

  Y2 ⇔ T1(entakapon etkisiz ∨ direnç) ∧ T2(3.basamak resmi SHS)
     ∧ T3(durumu belirten nöro/geriatri uzman hekim raporu)
     ∧ T4(reçeteci ∈ {nöroloji, iç hastalıkları}) ∧ T5(≤1 aylık miktar)[bilgi]

  Y5 ⇔ M1(influenza A salgını) ∧ M2(profilaktik amaç)
     ∧ M3[RİSK/YAŞ — OR grubu] ∧ M4(grip aşısı yapılamadı: kontrendike ∨ erken
       aşılama yapılamaması) ∧ M5(SK raporu ≤6 ay)[bilgi] ∧ M6(reçeteci uzman)
     M3 ⇔ (yaş<7 ∨ yaş>65) ∨ risk_grubu{HIV(+)∨malignite∨DM/kronik metabolik
       ∨ kronik renal disfonksiyon ∨ hemoglobinopati ∨ immün yetmezlik
       ∨ immünsupresif tedavi} ∨ (6ay≤yaş≤18 ∧ uzun süreli ASA tedavisi)

Sessizlik = KONTROL_EDİLEMEDİ (örtük kabul YASAK). Rapor lafzı parse edilemeyen
şartlar `sartli_atom`/`(bilgi)` ile işaretlenir → ŞARTLI UYGUN.

Ana entrypoint: ``parkinson_kontrol_4_2_36(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI listeleri (etken + ticari ad). ATC amantadin saltlarını
# ayırt edemediği için (her ikisi N04BB01) etken/ad metni esastır.
# ═══════════════════════════════════════════════════════════════════════

# Y1 — dopamin agonistleri / COMT inh / MAO-B inh grubu
Y1_ETKEN: Set[str] = {
    'APOMORFIN', 'APOMORPHINE',
    'KABERGOLIN', 'CABERGOLIN', 'CABERGOLINE',
    'ENTAKAPON', 'ENTACAPONE',  # + kombinasyonları (Stalevo)
    'RASAJILIN', 'RASAGILIN', 'RASAGILINE',
    'PERGOLID', 'PERGOLIDE',
    'PRAMIPEKSOL', 'PRAMIPEXOL', 'PRAMIPEXOLE',
    'BORNAPRIN', 'BORNAPRINE',
    'ROPINIROL', 'ROPINIROLE',
}
Y1_TICARI: Set[str] = {
    'APO-GO', 'APOGO', 'DACEPTON',
    'DOSTINEX', 'CABASER', 'KABASER',
    'COMTAN', 'COMTESS', 'STALEVO',  # Stalevo = levodopa+karbidopa+entakapon
    'AZILECT',
    'PERMAX',
    'PEXOLA', 'MIRAPEXIN', 'SIFROL', 'OPRYMEA',
    'SORMODREN',
    'REQUIP', 'ADARTREL', 'RONIROL',
}

# Y2 — Tolkapon
Y2_ETKEN: Set[str] = {'TOLKAPON', 'TOLCAPONE'}
Y2_TICARI: Set[str] = {'TASMAR'}

# Amantadin (Y3/Y4/Y5) — salt etken metninden ayrılır
AMANTADIN_GENEL: Set[str] = {'AMANTADIN', 'AMANTADINE'}
AMANTADIN_TICARI: Set[str] = {'PK-MERZ', 'PKMERZ', 'PK MERZ'}
_SULFAT_RE = re.compile(r'S[UÜ]LFAT|SULPHATE|SULFATE')
_HCL_RE = re.compile(r'H[İI]DROKLOR[UÜ]R|HYDROCHLORIDE|\bHCL\b|\bHCI\b')


# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
NOROLOJI = ['noroloji', 'norolog']
GERIATRI = ['geriatri']
IC_HAST = ['ic hastalik', 'dahiliye']
NORO_GER = NOROLOJI + GERIATRI
# "Uzman hekim" sayılmayan branşlar (aile hekimi / pratisyen)
PRATISYEN = ['aile hek', 'pratisyen', 'genel pratisyen', 'pratisyen hekim']


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
    return [h.get('brans') or '' for h in heyet if (h.get('ad') or h.get('brans'))]


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip())


def _rapor_brans_adaylar(ilac_sonuc: Dict) -> List[str]:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    return [rb] + _heyet_brans_listesi(ilac_sonuc)


def _yas_int(ilac_sonuc: Dict) -> Optional[int]:
    """hasta_yasi / yas alanından ilk tam sayı (yıl)."""
    for anahtar in ('hasta_yasi', 'yas'):
        v = ilac_sonuc.get(anahtar)
        if v is None or v == '':
            continue
        m = re.search(r'\d+', str(v))
        if m:
            try:
                return int(m.group())
            except ValueError:
                continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def _amantadin_salt(ilac_sonuc: Dict) -> Optional[str]:
    """'SULFAT' | 'HCL' | None (amantadin ama salt belirsiz)."""
    m = _arama_metni(ilac_sonuc)
    if not (_iceriyor(m, AMANTADIN_GENEL) or _iceriyor(m, AMANTADIN_TICARI)):
        return None
    if _SULFAT_RE.search(m):
        return 'SULFAT'
    if _HCL_RE.search(m):
        return 'HCL'
    return 'BELIRSIZ'


def _influenza_endikasyon(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bJ0?9|\bJ10|\bJ11', icd):
        return True
    return any(k in metin for k in ('influenza', 'grip', 'salgin', 'profilaks'))


def _parkinson_endikasyon(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bG2[01]', icd):  # G20 parkinson, G21 sekonder
        return True
    return 'parkinson' in metin


def _eps_endikasyon(ilac_sonuc: Dict) -> bool:
    """İlaca bağlı ekstrapiramidal reaksiyon (tremor/rijidite/hipo-akinezi)."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bG2[1-5]', icd):  # G21-G25 ekstrapiramidal/hareket boz.
        return True
    return any(k in metin for k in ('ekstrapiramidal', 'extrapiramidal', 'tremor',
                                    'rijidite', 'rigidite', 'akinezi', 'hipokinezi',
                                    'parkinsonizm'))


def parkinson_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Kapsam içi mi + hangi yolak? → 'Y1'|'Y2'|'Y3'|'Y4'|'Y5'|None.

    None = 4.2.36 kapsamı dışı (ATLANDI).
    """
    m = _arama_metni(ilac_sonuc)
    salt = _amantadin_salt(ilac_sonuc)
    if salt is not None:
        if salt == 'HCL':
            return 'Y4'
        if salt == 'SULFAT':
            return 'Y5' if (_influenza_endikasyon(ilac_sonuc)
                            and not _parkinson_endikasyon(ilac_sonuc)) else 'Y3'
        # Salt belirsiz: influenza endikasyonu → Y5, aksi halde parkinson Y3
        return 'Y5' if (_influenza_endikasyon(ilac_sonuc)
                        and not _parkinson_endikasyon(ilac_sonuc)) else 'Y3'
    if _iceriyor(m, Y2_ETKEN) or _iceriyor(m, Y2_TICARI):
        return 'Y2'
    if _iceriyor(m, Y1_ETKEN) or _iceriyor(m, Y1_TICARI):
        return 'Y1'
    return None


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ÇEKİRDEK ATOM — UZMAN_YETKİ (Y1/Y3/Y4)
# ═══════════════════════════════════════════════════════════════════════

def atom_uzman_yetki(ilac_sonuc: Dict, grup: str) -> List[SartSonuc]:
    """(reçeteci nöro/geriatri) ∨ (uzman raporu ∧ düzenleyen nöro/geriatri).

    Tek `veya_grubu` (≥1 VAR yeterli) — iki paralel atom döndürür.
    """
    s: List[SartSonuc] = []
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)

    # Atom A: reçeteyi yazan hekim bizzat nöroloji/geriatri uzmanı mı?
    if not bl:
        s.append(SartSonuc(ad='Reçete eden nöroloji/geriatri uzmanı',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Reçete eden hekim branşı bilinmiyor — manuel',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True,
                           sartli_atom=True))
    elif _brans_listede(brans, NORO_GER):
        s.append(SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                           neden='Nöroloji/geriatri uzmanı doğrudan reçete edebilir',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                           neden='Nöroloji/geriatri değil — uzman raporu gerekli',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))

    # Atom B: nöroloji/geriatri uzmanının düzenlediği uzman hekim raporu var mı?
    rapor_var = _rapor_var(ilac_sonuc)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    duzenleyen_noroger = any(_brans_listede(a, NORO_GER) for a in adaylar)
    aday_var = any(_brans_l(a) for a in adaylar)
    if duzenleyen_noroger:
        s.append(SartSonuc(ad='Uzman hekim raporu (nöroloji/geriatri düzenlemiş)',
                           durum=SartDurumu.VAR,
                           neden='Nöroloji/geriatri uzmanının düzenlediği rapora dayanılarak '
                                 'tüm hekimlerce reçete edilebilir',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    elif rapor_var and not aday_var:
        s.append(SartSonuc(ad='Uzman hekim raporu (düzenleyen branş bilinmiyor)',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Rapor var ama düzenleyen/heyet branşı okunamadı — manuel',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True,
                           sartli_atom=True))
    elif rapor_var and aday_var:
        s.append(SartSonuc(ad='Uzman hekim raporu (nöroloji/geriatri değil)',
                           durum=SartDurumu.YOK,
                           neden='Rapor düzenleyen nöroloji/geriatri uzmanı değil',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad='Uzman hekim raporu', durum=SartDurumu.YOK,
                           neden='Reçeteye bağlı uzman hekim raporu yok',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y1 — DA/COMT/MAO-B grubu (4.2.36/1)
# ═══════════════════════════════════════════════════════════════════════

def y1_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    return atom_uzman_yetki(ilac_sonuc, grup='(4.2.36/1) Nöroloji/geriatri uzmanı veya raporu (≥1)')


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y3 — Amantadin sülfat / parkinson + EPS (4.2.36/3)
# ═══════════════════════════════════════════════════════════════════════

def atom_y3_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    park = _parkinson_endikasyon(ilac_sonuc)
    eps = _eps_endikasyon(ilac_sonuc)
    if park or eps:
        neden = ('Parkinson hastalığı' if park else 'İlaca bağlı ekstrapiramidal reaksiyon')
        return SartSonuc(ad='Endikasyon (parkinson / EPS reaksiyon)', durum=SartDurumu.VAR,
                         neden=neden, kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Endikasyon (parkinson / EPS reaksiyon)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Parkinson/EPS endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def y3_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_y3_endikasyon(ilac_sonuc, grup='(4.2.36/3) Endikasyon'))
    s.extend(atom_uzman_yetki(
        ilac_sonuc, grup='(4.2.36/3) Nöroloji/geriatri uzmanı veya raporu (≥1)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y4 — Amantadin hidroklorür / yalnız parkinson (4.2.36/4)
# ═══════════════════════════════════════════════════════════════════════

def atom_y4_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    park = _parkinson_endikasyon(ilac_sonuc)
    if park:
        return SartSonuc(ad='Endikasyon (yalnız parkinson)', durum=SartDurumu.VAR,
                         neden='Parkinson hastalığı', kaynak='ICD+rapor', grup=grup)
    # Açıkça parkinson-dışı bir endikasyon var mı? (influenza vb. → kontrendike)
    if _influenza_endikasyon(ilac_sonuc):
        return SartSonuc(ad='Endikasyon (yalnız parkinson)', durum=SartDurumu.YOK,
                         neden='Amantadin HCl yalnız parkinsonda karşılanır; influenza/diğer '
                               'endikasyon kapsam dışı', kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Endikasyon (yalnız parkinson)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Parkinson endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def y4_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_y4_endikasyon(ilac_sonuc, grup='(4.2.36/4) Endikasyon'))
    s.extend(atom_uzman_yetki(
        ilac_sonuc, grup='(4.2.36/4) Nöroloji/geriatri uzmanı veya raporu (≥1)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y2 — Tolkapon (4.2.36/2) — AND zinciri
# ═══════════════════════════════════════════════════════════════════════

def atom_y2_entakapon_basarisiz(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'entakapon' in metin and any(
            k in metin for k in ('etkisiz', 'yetersiz', 'yanit alinama', 'yanit yok',
                                  'direnc', 'cevap alinama', 'fayda gormedi',
                                  'fayda saglamadi')):
        return SartSonuc(ad='Entakapon etkisiz / direnç (rapor lafzı)',
                         durum=SartDurumu.VAR,
                         neden='Raporda entakaponun etkisiz kaldığı/direnç geliştiği belirtilmiş',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Entakapon etkisiz / direnç (rapor lafzı)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Raporda "entakapon etkisiz/dirençli" ibaresi okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_y2_ucuncu_basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('ucuncu basamak', '3. basamak', '3.basamak',
                                'egitim arastirma', 'universite', 'sehir hastane')):
        return SartSonuc(ad='Üçüncü basamak resmi sağlık hizmeti sunucusu',
                         durum=SartDurumu.VAR, neden='Raporda 3. basamak SHS ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Üçüncü basamak resmi sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor düzenleyen tesisin 3. basamak olduğu doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_y2_rapor_noroger(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    rapor_var = _rapor_var(ilac_sonuc)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, NORO_GER) for a in adaylar):
        return SartSonuc(ad='Nöroloji/geriatri uzman hekim raporu',
                         durum=SartDurumu.VAR,
                         neden='Durumu belirten nöroloji/geriatri uzman hekim raporu',
                         kaynak='rapor_brans', grup=grup)
    if rapor_var and not any(_brans_l(a) for a in adaylar):
        return SartSonuc(ad='Nöroloji/geriatri uzman hekim raporu',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama düzenleyen branşı okunamadı — manuel',
                         kaynak='rapor_brans', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Nöroloji/geriatri uzman hekim raporu', durum=SartDurumu.YOK,
                     neden='Nöroloji/geriatri uzman hekim raporu yok',
                     kaynak='rapor_brans', grup=grup)


def atom_y2_recete_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden branş (nöroloji / iç hastalıkları)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, NOROLOJI + IC_HAST):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nöroloji veya iç hastalıkları uzman hekimi reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yalnız nöroloji / iç hastalıkları uzmanı reçete edebilir',
                     kaynak='hekim_brans', grup=grup)


def y2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_y2_entakapon_basarisiz(ilac_sonuc, grup='(4.2.36/2) Entakapon etkisiz/direnç'))
    s.append(atom_y2_ucuncu_basamak(ilac_sonuc, grup='(4.2.36/2) Üçüncü basamak SHS'))
    s.append(atom_y2_rapor_noroger(ilac_sonuc, grup='(4.2.36/2) Nöro/geriatri uzman raporu'))
    s.append(atom_y2_recete_brans(ilac_sonuc, grup='(4.2.36/2) Reçete eden branş'))
    s.append(SartSonuc(ad='En fazla 1 aylık ilaç miktarı', durum=SartDurumu.KONTROL_EDILEMEDI,
                       neden='Miktar/doz reçeteden hesaplanamadı — manuel',
                       kaynak='doz', grup='(4.2.36/2) En fazla 1 aylık miktar', sartli_atom=True))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y5 — Amantadin sülfat oral / influenza A profilaksi (EK-4/F m.50)
# ═══════════════════════════════════════════════════════════════════════

def atom_m1_salgin(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if ('influenza' in metin or 'grip' in metin) and 'salgin' in metin:
        return SartSonuc(ad='İnfluenza A salgını', durum=SartDurumu.VAR,
                         neden='Raporda influenza salgını ibaresi', kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='İnfluenza A salgını', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İnfluenza A salgın durumu raporda doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_m2_profilaksi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('profilaks', 'koruyucu', 'onleyici')):
        return SartSonuc(ad='Profilaktik (koruyucu) amaç', durum=SartDurumu.VAR,
                         neden='Raporda profilaktik kullanım ibaresi', kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Profilaktik (koruyucu) amaç', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Profilaktik amaç raporda doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_m3_risk_yas(ilac_sonuc: Dict, grup: str) -> List[SartSonuc]:
    """OR grubu: (yaş<7 ∨ yaş>65) ∨ risk_grubu ∨ (6ay-18 yaş ∧ uzun süreli ASA)."""
    s: List[SartSonuc] = []
    yas = _yas_int(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)

    # Atom 1: yaş < 7 veya yaş > 65
    if yas is None:
        s.append(SartSonuc(ad='Yaş < 7 veya yaş > 65', durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Hasta yaşı bilinmiyor — manuel', kaynak='DB_yas',
                           grup=grup, veya_grubu=True, sartli_atom=True))
    elif yas < 7 or yas > 65:
        s.append(SartSonuc(ad=f'Yaş {yas} ( <7 veya >65 )', durum=SartDurumu.VAR,
                           neden='Risk yaş grubunda', kaynak='DB_yas', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad=f'Yaş {yas} ( <7 veya >65 )', durum=SartDurumu.YOK,
                           neden='7-65 yaş arası — yaş kriteri sağlanmıyor',
                           kaynak='DB_yas', grup=grup, veya_grubu=True))

    # Atom 2: risk grubu (HIV / malignite / DM-metabolik / renal / hemoglobinopati /
    #          immün yetmezlik / immünsupresif)
    icd = _teshis_birlesik(ilac_sonuc)
    risk_kw = ('hiv', 'malignite', 'kanser', 'tumor', 'diabet', 'diyabet',
               'metabolik', 'kronik renal', 'bobrek yetmezlik', 'hemoglobinopati',
               'talasemi', 'orak hucre', 'immun yetmezlik', 'immun supres',
               'immunsupres', 'bagisiklik yetmezlik')
    risk_icd = bool(re.search(r'\bB2[0-4]|\bD46|\bC\d\d|\bE1[0-4]|\bN18|\bD56|\bD57|\bD80|\bD84', icd))
    if any(k in metin for k in risk_kw) or risk_icd:
        s.append(SartSonuc(ad='Risk grubu (HIV/malignite/DM/renal/hemoglobinopati/immün)',
                           durum=SartDurumu.VAR, neden='Risk grubu hastalık tespit edildi',
                           kaynak='ICD+rapor', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad='Risk grubu (HIV/malignite/DM/renal/hemoglobinopati/immün)',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Risk grubu hastalık raporda/ICD\'de okunamadı — manuel',
                           kaynak='ICD+rapor', grup=grup, veya_grubu=True, sartli_atom=True))

    # Atom 3: 6 ay - 18 yaş + uzun süreli asetilsalisilik asit tedavisi
    asa = any(k in metin for k in ('asetilsalisilik', 'aspirin', 'asa tedavi'))
    yas_aralik = (yas is not None and yas <= 18)
    if asa and yas_aralik:
        s.append(SartSonuc(ad='6ay-18 yaş + uzun süreli ASA tedavisi', durum=SartDurumu.VAR,
                           neden='ASA tedavisi alan çocuk/adölesan', kaynak='ICD+rapor',
                           grup=grup, veya_grubu=True))
    elif yas is not None and yas > 18:
        s.append(SartSonuc(ad='6ay-18 yaş + uzun süreli ASA tedavisi', durum=SartDurumu.YOK,
                           neden='18 yaş üstü — bu alt-kriter dışı', kaynak='DB_yas',
                           grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad='6ay-18 yaş + uzun süreli ASA tedavisi',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='ASA tedavisi / yaş aralığı doğrulanamadı — manuel',
                           kaynak='ICD+rapor', grup=grup, veya_grubu=True, sartli_atom=True))
    return s


def atom_m4_asi_yapilamadi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('asi yapilama', 'asi kontrendike', 'kontrendike',
                                'erken asilama', 'asi uygulanamad', 'asi yapilamad')):
        return SartSonuc(ad='Grip aşısı yapılamadı (kontrendike / erken aşılama yok)',
                         durum=SartDurumu.VAR, neden='Raporda aşı yapılamadığı ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Grip aşısı yapılamadı (kontrendike / erken aşılama yok)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Grip aşısının yapılamadığı durum raporda doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_m6_recete_uzman(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden uzman hekim', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, PRATISYEN):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Aile hekimi/pratisyen — uzman hekim değil',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim tarafından reçete', kaynak='hekim_brans', grup=grup)


def y5_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_m1_salgin(ilac_sonuc, grup='(m.50) İnfluenza A salgını'))
    s.append(atom_m2_profilaksi(ilac_sonuc, grup='(m.50) Profilaktik amaç'))
    s.extend(atom_m3_risk_yas(ilac_sonuc, grup='(m.50) Risk / yaş grubu (≥1)'))
    s.append(atom_m4_asi_yapilamadi(ilac_sonuc, grup='(m.50) Grip aşısı yapılamadı'))
    s.append(SartSonuc(ad='Sağlık kurulu raporu (≤6 ay süreli)',
                       durum=SartDurumu.KONTROL_EDILEMEDI,
                       neden='SK raporu ve ≤6 ay süre koşulu metinden doğrulanamadı — manuel',
                       kaynak='rapor', grup='(m.50) Sağlık kurulu raporu ≤6 ay', sartli_atom=True))
    s.append(atom_m6_recete_uzman(ilac_sonuc, grup='(m.50) Reçete eden uzman hekim'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA
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
    yolak_ad = YOLAK_METADATA.get(yolak, {}).get('ad', yolak)
    sut = YOLAK_METADATA.get(yolak, {}).get('sut', '4.2.36')
    parcalar = [f"SUT {sut} / {yolak_ad}"]
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

YOLAK_FN_MAP = {'Y1': y1_kontrol, 'Y2': y2_kontrol, 'Y3': y3_kontrol,
                'Y4': y4_kontrol, 'Y5': y5_kontrol}
YOLAK_METADATA = {
    'Y1': {'ad': 'DA/COMT/MAO-B grubu', 'sut': '4.2.36(1)'},
    'Y2': {'ad': 'Tolkapon', 'sut': '4.2.36(2)'},
    'Y3': {'ad': 'Amantadin sülfat (parkinson/EPS)', 'sut': '4.2.36(3)'},
    'Y4': {'ad': 'Amantadin hidroklorür', 'sut': '4.2.36(4)'},
    'Y5': {'ad': 'Amantadin sülfat oral (influenza profilaksi)', 'sut': 'EK-4/F m.50'},
}


def parkinson_kontrol_4_2_36(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.36 (+ EK-4/F m.50) ana kontrol fonksiyonu (parkinson ilaçları)."""
    yolak = parkinson_yolak_belirle(ilac_sonuc)
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.36 kapsamı dışı — parkinson ilacı (DA/COMT/MAO-B, '
                  'tolkapon, amantadin) değil',
            sut_kurali='SUT 4.2.36')

    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f"SUT {YOLAK_METADATA[yolak]['sut']}",
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'yolak_ad': YOLAK_METADATA[yolak]['ad']})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥12 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # ── Y1 ──
        ("Y1 UYGUN (ropinirol, reçeteci nöroloji)", {
            'etkin_madde': 'ROPINIROL', 'brans': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (pramipeksol, aile hek + nöroloji raporu)", {
            'etkin_madde': 'PRAMIPEKSOL', 'brans': 'Aile Hekimliği',
            'rapor_kodu': '1234', 'rapor_doktor_brans': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (Stalevo=entakapon kombi, geriatri)", {
            'ilac_adi': 'STALEVO 100 MG', 'etkin_madde': 'LEVODOPA KARBIDOPA ENTAKAPON',
            'brans': 'Geriatri',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN DEĞİL (kardiyoloji, rapor yok)", {
            'etkin_madde': 'RASAJILIN', 'brans': 'Kardiyoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 ŞARTLI (aile hek + rapor var, branş bilinmiyor)", {
            'etkin_madde': 'KABERGOLIN', 'brans': 'Aile Hekimliği',
            'rapor_kodu': '999',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y1 UYGUN DEĞİL (dahiliye + rapor dermatoloji)", {
            'etkin_madde': 'APOMORFIN', 'brans': 'İç Hastalıkları',
            'rapor_kodu': '7', 'rapor_doktor_brans': 'Dermatoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Y3 amantadin sülfat ──
        ("Y3 UYGUN (amantadin sülfat, parkinson, nöroloji)", {
            'etkin_madde': 'AMANTADIN SÜLFAT', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G20'],
        }, KontrolSonucu.UYGUN),
        ("Y3 ŞARTLI (amantadin sülfat, endikasyon sessiz, nöroloji)", {
            'ilac_adi': 'PK-MERZ', 'etkin_madde': 'AMANTADIN SÜLFAT',
            'brans': 'Nöroloji',
        }, KontrolSonucu.SARTLI_UYGUN),
        # ── Y4 amantadin HCl ──
        ("Y4 UYGUN (amantadin HCl, parkinson, geriatri)", {
            'etkin_madde': 'AMANTADIN HIDROKLORÜR', 'brans': 'Geriatri',
            'recete_teshisleri': ['G20'],
        }, KontrolSonucu.UYGUN),
        ("Y4 UYGUN DEĞİL (amantadin HCl, influenza endikasyon)", {
            'etkin_madde': 'AMANTADIN HCL', 'brans': 'Nöroloji',
            'rapor_metni': 'influenza profilaksi', 'recete_teshisleri': ['J10'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Y2 tolkapon ──
        ("Y2 ŞARTLI (tolkapon, tüm hesaplanabilir VAR, bilgi atomlar KE)", {
            'etkin_madde': 'TOLKAPON', 'brans': 'Nöroloji',
            'rapor_doktor_brans': 'Nöroloji',
            'rapor_metni': 'entakapon etkisiz kaldi ucuncu basamak universite hastanesi',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y2 UYGUN DEĞİL (tolkapon, reçeteci kardiyoloji)", {
            'etkin_madde': 'TOLKAPON', 'brans': 'Kardiyoloji',
            'rapor_doktor_brans': 'Nöroloji',
            'rapor_metni': 'entakapon etkisiz ucuncu basamak',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Y5 influenza profilaksi ──
        ("Y5 ŞARTLI (amantadin sülfat, influenza, 70 yaş, uzman)", {
            'etkin_madde': 'AMANTADIN SÜLFAT', 'brans': 'Enfeksiyon Hastalıkları',
            'hasta_yasi': '70',
            'rapor_metni': 'influenza salgini profilaksi asi yapilamadi kontrendike',
            'recete_teshisleri': ['J10'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y5 UYGUN DEĞİL (influenza, aile hekimi reçete)", {
            'etkin_madde': 'AMANTADIN SÜLFAT', 'brans': 'Aile Hekimliği',
            'hasta_yasi': '70',
            'rapor_metni': 'influenza salgini profilaksi asi yapilamadi',
            'recete_teshisleri': ['J10'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.36 — Parkinson — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = parkinson_kontrol_4_2_36(ilac_sonuc)
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
