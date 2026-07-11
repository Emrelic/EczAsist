# -*- coding: utf-8 -*-
"""Antiaritmikler (amiodaron/dronedaron/propafenon/sotalol…) — EK-4/D muafiyet
+ EK-4/G form kontrolü.

Kapsam: ATC C01B* (sınıf I ve III antiaritmikler: amiodaron C01BD01,
dronedaron C01BD07, propafenon C01BC03, kinidin/meksiletin/flekainid…) +
SOTALOL (ATC C07AA07 — beta bloker ATC'sinde ama klinik kullanımı antiaritmik).

Resmî mevzuat bulgusu (2026-07-05, primary source taraması):
    • Ana SUT tebliğ (`docs/sut/SUT_tam_metin.txt`): amiodaron / dronedaron /
      propafenon / sotalol / "antiaritmik" HİÇ GEÇMİYOR → 4.2.x özel madde YOK.
    • EK-4/F (raporla verilebilecek ilaçlar): hiçbir antiaritmik YOK
      → RAPOR ZORUNLU DEĞİL; raporsuz da ödenir (SUT 4.1.4(3), katılım paylı).
    • EK-4/E (reçeteleme kuralları): YOK.
    • EK-4/G (sadece yatarak): amiodaronun PARENTERAL formları (CORDARONE
      ampul) sadece yatan hastada ödenir → ayakta reçetede UYGUN DEĞİL
      (SUT 4.1.7(2): "ayakta tedavilerde reçete edilmesi halinde bedeli ödenmez").
    • EK-4/D (katılım payı muafiyeti) — "Antiaritmikler" 4 başlıkta:
        - m.4.3  Disritmiler                    → ICD I44, I45, I47, I48, I49
        - m.4.7  ARA ve kapak hastalıkları      → ICD I05-I08, I34-I37, I39
        - m.4.9  Kardiyomiyopati                → ICD I42-I43
        - m.4.13 Kronik romatizmal kalp hast.   → ICD I09
      SOTALOL ayrıca "Beta blokerler ve kombinasyonları" girdileriyle
      şu başlıklarda da muaf: m.4.1 KY (I50), m.4.2 KAH (I20/I21/I25/Z95),
      m.4.6 doğuştan kalp (Q20-Q28), m.7.9.2.2 Turner (Q96).
      (EK-4/D'de hipertansiyon başlığı YOKTUR — I10 muafiyet sağlamaz.)
    • SUT 4.1.6(2): muafiyet için rapor "ilgili başlıktaki tanılara uygun"
      düzenlenmiş olmalı; 4.1.6(3): raporla TÜM hekimler reçete edebilir
      (branş şartı yok); 4.1.6(1): raporla en fazla 3 aylık doz.

═══════════════════════════════════════════════════════════════════════════
KARAR AKIŞI / MANTIK FORMÜLÜ (kullanıcı onayı 2026-07-05)
═══════════════════════════════════════════════════════════════════════════
  FORM kapısı (EK-4/G):
     parenteral (ampul/flakon)  → YOK  → UYGUN DEĞİL (ayakta ödenmez)
     oral                       → VAR

  Muafiyet değerlendirmesi (EK-4/D):
     rapor YOK                          → VAR  (raporsuz ödenir, katılım paylı)
     ICD ∈ muaf başlık ∨ rapor kodu ∈
       {04.03, 04.07, 04.09, 04.13}
       (+sotalol: 04.01/04.02/04.06)    → VAR  (katılım payından MUAF)
     rapor metninde disritmi/KMP lafzı  → VAR  (metin sinyali)
     ICD var ama muaf başlık DIŞI       → KE   → ŞÜPHELİ (kullanıcı kararı:
       ödeme engeli değil ama eczane muaf işaretlediyse KESİNTİ RİSKİ)
     rapor var, ICD/metin okunamadı     → KE   → ŞÜPHELİ (örtük kabul yasak)

Ana entrypoint: ``antiaritmik_kontrol_ek4d(ilac_sonuc)`` → ``KontrolRaporu``.
Kapsam tespiti: ``antiaritmik_kapsami_mi(ilac_sonuc)`` /
``antiaritmik_kategori(ilac_sonuc)``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti
# ═══════════════════════════════════════════════════════════════════════
ATC_SOTALOL = 'C07AA07'
ATC_C01B_PREFIX = 'C01B'   # sınıf I + III antiaritmikler

# kategori → (ATC prefiksleri, etken/ticari ad ibareleri)
_KATEGORI_TANIM: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ('AMIODARON',  ('C01BD01',), ('AMIODARON', 'AMIODARONE', 'CORDARONE')),
    ('DRONEDARON', ('C01BD07',), ('DRONEDARON', 'DRONEDARONE', 'MULTAQ')),
    ('PROPAFENON', ('C01BC03',), ('PROPAFENON', 'PROPAFENONE', 'RYTMONORM')),
    ('SOTALOL',    (ATC_SOTALOL,), ('SOTALOL', 'TALOZIN', 'DAROB')),
)
_DIGER_ETKEN: Set[str] = {
    'MEKSILETIN', 'MEXILETIN', 'FLEKAINID', 'FLECAINID',
    'KINIDIN', 'QUINIDIN', 'DIZOPIRAMID', 'DISOPIRAMID',
}
ANTIARITMIK_KATEGORILER: Tuple[str, ...] = (
    'AMIODARON', 'DRONEDARON', 'PROPAFENON', 'SOTALOL', 'ANTIARITMIK_DIGER')

# EK-4/G — parenteral form ibareleri (ilaç adında)
_PARENTERAL_IBARELER: Tuple[str, ...] = (
    'AMPUL', 'AMP.', 'FLAKON', 'ENJEKTABL', 'ENJEKSIYON', 'INFUZYON',
    'INFUSION', 'IV COZ',
)

# ═══════════════════════════════════════════════════════════════════════
# EK-4/D muafiyet ICD kümeleri (prefix eşleşme)
# ═══════════════════════════════════════════════════════════════════════
# Tüm antiaritmikler: 4.3 + 4.7 + 4.9 + 4.13 başlıkları
MUAF_ANTIARITMIK_PREFIX: Tuple[str, ...] = (
    'I44', 'I45', 'I47', 'I48', 'I49',                     # 4.3 disritmiler
    'I05', 'I06', 'I07', 'I08', 'I34', 'I35', 'I36', 'I37', 'I39',  # 4.7 kapak/ARA
    'I42', 'I43',                                          # 4.9 kardiyomiyopati
    'I09',                                                 # 4.13 kr. romatizmal KH
)
# Sotalol EK (beta bloker başlıkları): 4.1 + 4.2 + 4.6 + 7.9.2.2
MUAF_SOTALOL_EK_PREFIX: Tuple[str, ...] = (
    'I50',                                                 # 4.1 kalp yetmezliği
    'I20', 'I21', 'I25', 'Z95',                            # 4.2 koroner arter hast.
    'Q20', 'Q21', 'Q22', 'Q23', 'Q24', 'Q25', 'Q26', 'Q27', 'Q28',  # 4.6 doğuştan
    'Q96',                                                 # 7.9.2.2 Turner
)
# Medula rapor kodları = EK-4/D madde numaraları (örn. hepatit 06.01 kalıbı)
RAPOR_KODU_ANTIARITMIK: Tuple[str, ...] = ('04.03', '04.07', '04.09', '04.13')
RAPOR_KODU_SOTALOL_EK: Tuple[str, ...] = ('04.01', '04.02', '04.06')

# Rapor metninde muaf başlık tanısına işaret eden lafızlar (norm_tr_upper'lı)
_MUAF_METIN_IBARELERI: Tuple[str, ...] = (
    'ATRIYAL FIBRILASYON', 'ATRIAL FIBRILASYON', 'ATRIYAL FLUTTER',
    'ATRIAL FLUTTER', 'DISRITMI', 'ARITMI', 'TASIKARDI', 'TASIARITMI',
    'VENTRIKULER FIBRILASYON', 'HASTA SINUS', 'SICK SINUS',
    'WOLFF', 'WPW', 'KARDIYOMIYOPATI', 'KARDIOMIYOPATI', 'KARDIYOMYOPATI',
)


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _atc(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


def antiaritmik_kategori(ilac_sonuc: Dict) -> str:
    """Satırın antiaritmik kapsam kategorisini döndür.

    Dönüş: 'AMIODARON' / 'DRONEDARON' / 'PROPAFENON' / 'SOTALOL' /
           'ANTIARITMIK_DIGER' / 'NONE'
    """
    atc = _atc(ilac_sonuc)
    m = _arama_metni(ilac_sonuc)
    for kategori, atc_prefixler, ibareler in _KATEGORI_TANIM:
        if any(atc.startswith(p) for p in atc_prefixler):
            return kategori
        if any(norm_tr_upper(ib) in m for ib in ibareler):
            return kategori
    if atc.startswith(ATC_C01B_PREFIX):
        return 'ANTIARITMIK_DIGER'
    if any(norm_tr_upper(e) in m for e in _DIGER_ETKEN):
        return 'ANTIARITMIK_DIGER'
    return 'NONE'


def antiaritmik_kapsami_mi(ilac_sonuc: Dict) -> bool:
    return antiaritmik_kategori(ilac_sonuc) != 'NONE'


def _parenteral_mi(ilac_sonuc: Dict) -> bool:
    ad = norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')
    return any(ib in ad for ib in _PARENTERAL_IBARELER)


def _teshis_tokenlari(ilac_sonuc: Dict) -> List[str]:
    """Rapor/reçete teşhis ICD kodlarını normalize edilmiş liste olarak topla."""
    ham: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi', 'teshis_kodu', 'teshis_tum',
                    'diger_raporlar_icd', 'rapor_teshisleri'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            ham.extend(str(x) for x in v if x)
        elif v:
            ham.append(str(v))
    tokenlar: List[str] = []
    for parca in ham:
        for tok in norm_tr_upper(parca).replace(';', ',').replace('|', ',').split(','):
            tok = tok.strip().replace(' ', '')
            if tok:
                tokenlar.append(tok)
    return tokenlar


def _rapor_var_mi(ilac_sonuc: Dict) -> bool:
    for anahtar in ('rapor_kodu', 'rap_kod', 'rapor_takip_no', 'rapor_turu',
                    'rapor_metni', 'tum_metin', 'rapor_doktor_brans',
                    'rapor_aciklamalari', 'rapor_kodu_aciklama'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            if any(x for x in v):
                return True
        elif v and str(v).strip():
            return True
    return False


def _rapor_kodu_tokenlari(ilac_sonuc: Dict) -> List[str]:
    ham: List[str] = []
    for anahtar in ('rapor_kodu', 'rap_kod'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            ham.extend(str(x) for x in v if x)
        elif v:
            ham.append(str(v))
    tokenlar: List[str] = []
    for parca in ham:
        for tok in str(parca).replace(';', ',').replace('|', ',').split(','):
            tok = tok.strip()
            if tok:
                tokenlar.append(tok)
    return tokenlar


def _rapor_metinleri(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('rapor_aciklamalari', 'rapor_metni', 'tum_metin',
                    'rap_tesh', 'rapor_teshisleri'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_upper(' '.join(parcalar))


def _muaf_prefixler(kategori: str) -> Tuple[str, ...]:
    if kategori == 'SOTALOL':
        return MUAF_ANTIARITMIK_PREFIX + MUAF_SOTALOL_EK_PREFIX
    return MUAF_ANTIARITMIK_PREFIX


def _muaf_rapor_kodlari(kategori: str) -> Tuple[str, ...]:
    if kategori == 'SOTALOL':
        return RAPOR_KODU_ANTIARITMIK + RAPOR_KODU_SOTALOL_EK
    return RAPOR_KODU_ANTIARITMIK


def _muafiyet_degerlendir(ilac_sonuc: Dict, kategori: str
                          ) -> Tuple[str, Optional[str]]:
    """EK-4/D muafiyetini değerlendir.

    Dönüş: (durum, eslesen)
      'muaf_icd'   : teşhis ICD muaf başlık kümesinde
      'muaf_kod'   : Medula rapor kodu muaf EK-4/D maddesinde
      'muaf_metin' : rapor metninde disritmi/KMP lafzı (metin sinyali)
      'muaf_disi'  : ICD var ama muaf başlıkların dışında
      'okunamadi'  : hiç ICD/kod/metin sinyali yok
    """
    prefixler = _muaf_prefixler(kategori)
    tokenlar = _teshis_tokenlari(ilac_sonuc)
    for tok in tokenlar:
        if any(tok.startswith(p) for p in prefixler):
            return ('muaf_icd', tok)

    kod_kumesi = _muaf_rapor_kodlari(kategori)
    for kod in _rapor_kodu_tokenlari(ilac_sonuc):
        if kod in kod_kumesi:
            return ('muaf_kod', kod)

    metin = _rapor_metinleri(ilac_sonuc)
    for ibare in _MUAF_METIN_IBARELERI:
        if ibare in metin:
            return ('muaf_metin', ibare)

    if tokenlar:
        return ('muaf_disi', tokenlar[0])
    return ('okunamadi', None)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_FORM = 'Ödeme kapsamı (EK-4/G form kontrolü)'
GRUP_MUAF = 'Katılım payı muafiyeti (EK-4/D 4.3/4.7/4.9/4.13)'
GRUP_MIKTAR = 'Miktar/doz (bilgi)'
GRUP_ENDIK = 'Endikasyon (bilgi)'


def atom_form_ek4g(ilac_sonuc: Dict) -> SartSonuc:
    """EK-4/G form kapısı — parenteral antiaritmik ayakta ödenmez."""
    if _parenteral_mi(ilac_sonuc):
        return SartSonuc(
            ad='Oral form (EK-4/G)', durum=SartDurumu.YOK,
            neden='Parenteral form (ampul/flakon) EK-4/G kapsamında — sadece '
                  'YATAN hastada ödenir; ayakta reçetede bedeli ödenmez '
                  '(SUT 4.1.7(2))',
            kaynak='ilaç formu', grup=GRUP_FORM)
    return SartSonuc(
        ad='Oral form (EK-4/G)', durum=SartDurumu.VAR,
        neden='Oral form — EK-4/G kısıtı yok; ayakta ödenir',
        kaynak='ilaç formu', grup=GRUP_FORM)


def atom_muafiyet(ilac_sonuc: Dict, kategori: str) -> SartSonuc:
    """EK-4/D katılım payı muafiyeti değerlendirmesi (ana atom)."""
    if kategori == 'SOTALOL':
        basliklar = 'EK-4/D 4.3/4.7/4.9/4.13 + beta-bloker başlıkları 4.1/4.2/4.6'
    else:
        basliklar = 'EK-4/D 4.3/4.7/4.9/4.13'

    if not _rapor_var_mi(ilac_sonuc):
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden='Rapor yok — raporsuz ödenir (katılım payı alınır); muafiyet '
                  f'için rapor + uygun tanı ({basliklar}) gerekir',
            kaynak='rapor', grup=GRUP_MUAF)

    durum, eslesen = _muafiyet_degerlendir(ilac_sonuc, kategori)
    if durum == 'muaf_icd':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Rapor/reçete ICD {eslesen} → {basliklar} kapsamında — '
                  f'katılım payından MUAF',
            kaynak='ICD', grup=GRUP_MUAF)
    if durum == 'muaf_kod':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Medula rapor kodu {eslesen} = EK-4/D muaf maddesi — '
                  f'katılım payından MUAF',
            kaynak='rapor kodu', grup=GRUP_MUAF)
    if durum == 'muaf_metin':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Rapor metninde "{eslesen}" lafzı → muaf başlık tanısı '
                  f'({basliklar}) — katılım payından MUAF',
            kaynak='rapor metni', grup=GRUP_MUAF)
    if durum == 'muaf_disi':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Rapor ICD {eslesen} muaf başlıkların ({basliklar}) DIŞINDA '
                  f'→ ödeme engeli yok ama muafiyet tanısı YOK; eczane muaf '
                  f'işaretlediyse KESİNTİ RİSKİ — katılım payı alınmalı '
                  f'(manuel doğrula)',
            kaynak='ICD', grup=GRUP_MUAF)
    # okunamadi
    return SartSonuc(
        ad='Katılım payı muafiyeti', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor var ama teşhis ICD/rapor kodu/metin okunamadı — muafiyet '
              f'({basliklar}) manuel doğrulanmalı (örtük kabul yasağı)',
        kaynak='ICD', grup=GRUP_MUAF)


def atom_miktar_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Miktar/doz — parse zayıf, matematiği bozmaz."""
    return SartSonuc(
        ad='Miktar/doz sınırı', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Raporlu: en fazla 3 aylık doz (SUT 4.1.6(1)); raporsuz: kısa '
              'süreli — miktar manuel kontrol edilir',
        kaynak='miktar', grup=GRUP_MIKTAR, sartli_atom=True)


def atom_endikasyon_bilgi(ilac_sonuc: Dict, kategori: str) -> SartSonuc:
    """(bilgi) Onaylı endikasyon / EK-4/D yıldız farkındalığı."""
    if kategori == 'SOTALOL':
        neden = ('EK-4/D 4.3.1 "Antiaritmik ilaçlar" yıldızsız (muaf tanıda '
                 'endikasyon-dışı onay aranmaz, SUT 4.1.4(4)b); beta-bloker '
                 'girdileri (4.3.5*) YILDIZLI — o başlıkta endikasyon uygunluğu '
                 'manuel')
    else:
        neden = ('EK-4/D 4.3.1 "Antiaritmik ilaçlar" yıldızsız — muaf başlık '
                 'tanısında endikasyon-dışı onay aranmaz (SUT 4.1.4(4)b); '
                 'onaylı endikasyon dışı kullanım şüphesinde manuel')
    return SartSonuc(
        ad='Onaylı endikasyon', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden=neden, kaynak='endikasyon', grup=GRUP_ENDIK, sartli_atom=True)


def _sartlari_uret(ilac_sonuc: Dict, kategori: str) -> List[SartSonuc]:
    # Erken çıkış YOK — parenteral olsa bile tüm atomlar üretilir (şema tam)
    return [
        atom_form_ek4g(ilac_sonuc),
        atom_muafiyet(ilac_sonuc, kategori),
        atom_miktar_bilgi(ilac_sonuc),               # bilgi
        atom_endikasyon_bilgi(ilac_sonuc, kategori),  # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (grup-bazlı ortak kalıp — bilgi grupları hesaptan çıkar)
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


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc],
                kategori: str) -> str:
    form_atom = next((s for s in sartlar if s.grup == GRUP_FORM), None)
    muaf_atom = next((s for s in sartlar if s.grup == GRUP_MUAF), None)
    neden = (muaf_atom.neden if muaf_atom else '') or ''
    parcalar = [f'Antiaritmik {kategori} (EK-4/D)']
    if sonuc == KontrolSonucu.UYGUN_DEGIL:
        if form_atom is not None and form_atom.durum == SartDurumu.YOK:
            parcalar.append('UYGUN DEĞİL — parenteral form EK-4/G: sadece '
                            'yatan hastada ödenir, ayakta ödenmez')
        else:
            parcalar.append('UYGUN DEĞİL')
    elif sonuc == KontrolSonucu.UYGUN:
        if 'MUAF' in neden and 'muafiyet için' not in neden:
            parcalar.append('UYGUN — katılım payından MUAF (EK-4/D)')
        else:
            parcalar.append('UYGUN — ödenir (raporsuz/katılım paylı)')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        if 'KESİNTİ RİSKİ' in neden:
            parcalar.append('ŞÜPHELİ — rapor tanısı muaf başlık DIŞI; muaf '
                            'işaretlendiyse kesinti riski (katılım payı alınmalı)')
        else:
            parcalar.append('ŞÜPHELİ — rapor var, tanı okunamadı; muafiyeti '
                            'manuel doğrula')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append('ŞARTLI UYGUN — bilgi şartları manuel doğrula')
    else:
        parcalar.append(sonuc.value)
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def antiaritmik_kontrol_ek4d(ilac_sonuc: Dict) -> KontrolRaporu:
    """Antiaritmik (amiodaron/dronedaron/propafenon/sotalol…) — EK-4/D
    muafiyet + EK-4/G form kontrolü."""
    kategori = antiaritmik_kategori(ilac_sonuc)
    if kategori == 'NONE':
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — antiaritmik değil',
            sut_kurali='EK-4/D m.4.3/4.7/4.9/4.13 Antiaritmikler')

    sartlar = _sartlari_uret(ilac_sonuc, kategori)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar, kategori)

    detaylar = {
        'alt_grup': kategori,
        'etken': kategori,
        'sut_maddesi': 'EK-4/D m.4.3/4.7/4.9/4.13 (Antiaritmikler)'
                       + (' + beta-bloker başlıkları 4.1/4.2/4.6'
                          if kategori == 'SOTALOL' else ''),
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
        sut_kurali='EK-4/D m.4.3 disritmi + m.4.7 kapak/ARA + m.4.9 KMP + '
                   'm.4.13 kr.romatizmal (Antiaritmikler); EK-4/F dışı → '
                   'raporsuz ödenir; parenteral → EK-4/G yatan hasta',
        aranan_ibare='EK-4/G form + EK-4/D muafiyet ICD/rapor kodu/metin',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN raporsuz (CORDARONE tablet, rapor yok → paylı ödenir)", {
            'ilac_adi': 'CORDARONE BOLUNEBILIR 200MG 30 TABLET',
            'etkin_madde': 'AMIODARON HCL', 'atc_kodu': 'C01BD01',
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (CORDARONE + AF I48)", {
            'ilac_adi': 'CORDARONE BOLUNEBILIR 200MG 30 TABLET',
            'etkin_madde': 'AMIODARON HCL', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'recete_teshisleri': ['I48'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (amiodaron + I49.9 tanımlanmamış aritmi)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'rec_tesh': 'I49.9',
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (amiodaron + rapor kodu 04.03, ICD boş)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '04.03',
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (amiodaron + rapor metninde ATRİYAL FİBRİLASYON)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_aciklamalari': ['ATRİYAL FİBRİLASYON TANILI HASTADA '
                                   '1 YIL KULLANIMI UYGUNDUR'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (amiodaron + kardiyomiyopati I42.0)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'recete_teshisleri': ['I42.0'],
        }, KontrolSonucu.UYGUN),
        ("ŞÜPHELİ (amiodaron rapor var, ICD/metin okunamadı)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_doktor_brans': 'Kardiyoloji',
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("ŞÜPHELİ (amiodaron + muaf dışı ICD E11.9 → kesinti riski)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'recete_teshisleri': ['E11.9'],
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("UYGUN DEĞİL (CORDARONE AMPUL ayakta — EK-4/G)", {
            'ilac_adi': 'CORDARONE 150 MG/3 ML IV 6 AMPUL',
            'etkin_madde': 'AMIODARON HCL', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'recete_teshisleri': ['I48'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN muaf (SOTALOL + kalp yetmezliği I50 — beta-bloker başlığı)", {
            'etkin_madde': 'SOTALOL', 'atc_kodu': 'C07AA07',
            'rapor_kodu': '1', 'recete_teshisleri': ['I50.0'],
        }, KontrolSonucu.UYGUN),
        ("ŞÜPHELİ (AMİODARON + I50 KY — antiaritmik başlığı DIŞI)", {
            'etkin_madde': 'AMIODARON', 'atc_kodu': 'C01BD01',
            'rapor_kodu': '1', 'recete_teshisleri': ['I50.0'],
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("UYGUN muaf (SOTALOL + AF I48)", {
            'ilac_adi': 'TALOZIN 80 MG', 'etkin_madde': '',
            'rapor_kodu': '1', 'rec_tesh': 'I48',
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (RYTMONORM propafenon + SVT I47.1)", {
            'ilac_adi': 'RYTMONORM 300 MG 30 TABLET', 'etkin_madde': '',
            'rapor_kodu': '1', 'recete_teshisleri': ['I47.1'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (MULTAQ dronedaron + I48)", {
            'ilac_adi': 'MULTAQ 400 MG', 'etkin_madde': 'DRONEDARON',
            'rapor_kodu': '1', 'recete_teshisleri': ['I48'],
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (metoprolol — düz beta bloker)", {
            'ilac_adi': 'BELOC ZOK 50 MG', 'etkin_madde': 'METOPROLOL',
            'atc_kodu': 'C07AB02',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("Antiaritmik EK-4/D — Akıl Testi\n" + "=" * 58)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = antiaritmik_kontrol_ek4d(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 58)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
