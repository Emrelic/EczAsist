# -*- coding: utf-8 -*-
"""SUT 4.2.29 — Kadın cinsiyet hormonları kullanım ilkeleri.

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:7835-7844, mevzuat.gov.tr
MevzuatNo=17229):

    (1) Bu grup ilaçların (aşağıda belirtilenler hariç) bütün formlarından;
        östrojenler ve hormon replasman tedavisinde kullanılanlar (östradiol
        ya da konjüge östrojen ve progestojen kombinasyonları, yalnız östrojen
        içerenler ve tibolon içerenler) ile progestojenler; endokrinoloji,
        kadın hastalıkları ve doğum, iç hastalıkları, ortopedi ve travmatoloji,
        fiziksel tıp ve rehabilitasyon ve aile hekimliği uzman hekimlerince
        veya bu uzman hekimler tarafından düzenlenen uzman hekim raporuna
        dayanılarak tüm hekimlerce reçete edilebilir.
    (2) Tek başına dienogest etkin maddesi içeren ilaçlar kadın hastalıkları
        ve doğum uzman hekimlerince veya bu uzman hekimler tarafından
        düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete
        edilmesi halinde bedeli Kurumca karşılanır.
    (3) Tek başına progesteron etkin maddesi içeren ve infertilite tedavisi
        endikasyonu olan topikal ilaçlar kadın hastalıkları ve doğum uzman
        hekimlerince veya bu hekimlerce düzenlenen prospektüs endikasyonlarıyla
        uyumlu uzman hekim raporuna istinaden diğer hekimlerce reçete edilmesi
        halinde bedeli Kurumca karşılanır.

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ. Üç fıkra = üç ilaç grubu = üç yolak (dispatcher). Hepsi
"uzman reçete VEYA uzman raporu" (üst-VEYA) yapısında; tek fark yetkili branş
kümesi. Cinsiyet / yaş / doz şartı SUT'ta YOK → eklenmez.

═══════════════════════════════════════════════════════════════════════════
DISPATCHER (ilaç tipine göre yol — en spesifik önce)
═══════════════════════════════════════════════════════════════════════════
  1) Tek başına dienogest (G03DB08, östrojensiz)        → Y2  (yalnız KHD)
  2) Tek başına progesteron + topikal/vajinal form      → Y3  (yalnız KHD)
  3) Östrojen / HRT komb. / progestojenler (kalanlar)   → Y1  (6 branş)
     · oral progesteron, kontraseptifler (G03A) burada
"(aşağıda belirtilenler hariç)" → (1) dienogest-tek ve progesteron-topikal'i
dışlar; bu yüzden Y2/Y3 önce sınanır.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════
  Y1_UYGUN ⇔ ( A1: reçete eden ∈ {endokrinoloji, kadın hast. ve doğum,
                                  iç hastalıkları, ortopedi ve travmatoloji,
                                  FTR, aile hekimliği} )
             ∨ ( B1: bu branşlardan biri tarafından düzenlenmiş uzman raporu )

  Y2_UYGUN ⇔ ( A2: reçete eden = KHD uzmanı ) ∨ ( B2: KHD uzmanı raporu )

  Y3_UYGUN ⇔ [ ( A3: reçete eden = KHD uzmanı ) ∨ ( B3: KHD uzmanı raporu ) ]
             ∧ ( C3: rapor prospektüs endikasyonlarıyla uyumlu )  ← (bilgi)/KE

  Her yolakta A/B tek VEYA grubu (≥1 yeterli). İkisi de YOK → UYGUN DEĞİL.
  Branş okunamazsa → KE + şartlı (ŞÜPHELİ). C3 parse edilemez → (bilgi),
  matematiği bozmaz (örtük kabul yasağına uygun).

Ana entrypoint: ``kadin_hormonlari_kontrol_4_2_29(ilac_sonuc)`` → KontrolRaporu.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC G03 (kadın cinsiyet hormonları) + etken
# ═══════════════════════════════════════════════════════════════════════
# G03A kontraseptifler (kullanıcı kararı: dahil), G03C östrojenler (tibolon
# G03CX01 dahil), G03D progestojenler (progesteron G03DA04 / dienogest
# G03DB08), G03F östrojen+progestojen kombinasyonları (HRT).
ATC_KAPSAM_PREFIX: Tuple[str, ...] = ('G03A', 'G03C', 'G03D', 'G03F')

DIENOGEST_ATC = 'G03DB08'
PROGESTERON_ATC = 'G03DA04'

DIENOGEST_KEYS: Set[str] = {'DIENOGEST', 'DIYENOGEST', 'DIENOGEST'}
PROGESTERON_KEYS: Set[str] = {'PROGESTERON', 'PROGESTERONE'}
# Östrojen ibareleri (kombinasyon tespiti için — tek-dienogest/progesteronu eler)
ESTROJEN_KEYS: Set[str] = {
    'ESTRADIOL', 'OSTRADIOL', 'ESTRADIYOL', 'ESTROJEN', 'OSTROJEN',
    'ESTRIOL', 'OSTRIOL', 'ETINIL', 'ETHINYL', 'KONJUGE',
}
# Topikal/vajinal/transdermal form anahtarları (progesteron Y3 yönlendirmesi)
TOPIKAL_KEYS: Set[str] = {
    'JEL', 'GEL', 'VAJINAL', 'VAGINAL', 'OVUL', 'KREM', 'CREAM',
    'TOPIKAL', 'TRANSDERMAL', 'BANT', 'PATCH', 'SPREY', 'PESSER',
}
# Kapsam fallback (ATC boş gelirse) — yaygın etken/ticari adlar
KAPSAM_ETKEN: Set[str] = {
    'ESTRADIOL', 'OSTRADIOL', 'ESTRADIYOL', 'KONJUGE OSTROJEN',
    'TIBOLON', 'TIBOLONE', 'PROGESTERON', 'PROGESTERONE', 'DIENOGEST',
    'DIDROGESTERON', 'DYDROGESTERON', 'NORETISTERON', 'NORETHISTERON',
    'MEDROKSIPROGESTERON', 'LINESTRENOL', 'LYNESTRENOL', 'DROSPIRENON',
    'LEVONORGESTREL', 'DESOGESTREL', 'GESTODEN', 'NOMEGESTROL',
}

# ── Yetkili branş kümeleri (norm_tr_lower substring) ──
# Y1: endo / KHD / iç hast. / ortopedi-travmatoloji / FTR / aile hekimliği
Y1_YETKI_SUBSTR: Tuple[str, ...] = (
    'endokrin',
    'kadin', 'jinekol', 'dogum',          # kadın hastalıkları ve doğum
    'ic hastalik', 'dahiliye',             # iç hastalıkları
    'ortopedi', 'travmatol',               # ortopedi ve travmatoloji
    'fiziksel tip', 'fizik tedavi', 'ftr', 'rehabilit', 'fizyoterapi',
    'aile hek',                            # aile hekimliği
)
# Y2/Y3: yalnız kadın hastalıkları ve doğum
KHD_YETKI_SUBSTR: Tuple[str, ...] = ('kadin', 'jinekol', 'dogum')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _ad_metni(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')


def _etken_metni(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '')


def _atc(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


def _iceriyor(metin_u: str, kume: Set[str]) -> bool:
    return any(norm_tr_upper(k) in metin_u for k in kume)


def _kombine_mi(etken_u: str) -> bool:
    """Kombinasyon ürünü mü? ('/' ya da '+' ya da östrojen+progestojen)."""
    return '/' in etken_u or '+' in etken_u


def _topikal_mi(ad_u: str, etken_u: str) -> bool:
    metin = f'{ad_u} {etken_u}'
    return _iceriyor(metin, TOPIKAL_KEYS)


def _brans_yetkili(brans: Optional[str], substr_set: Tuple[str, ...]) -> Optional[bool]:
    """True=yetkili, False=yetkisiz, None=branş bilinmiyor (KE)."""
    bl = norm_tr_lower(brans or '')
    if not bl:
        return None
    return any(k in bl for k in substr_set)


def kadin_hormonlari_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """SUT 4.2.29 kapsamındaki kadın cinsiyet hormonu mu?"""
    atc = _atc(ilac_sonuc)
    if any(atc.startswith(p) for p in ATC_KAPSAM_PREFIX):
        return True
    metin = f'{_ad_metni(ilac_sonuc)} {_etken_metni(ilac_sonuc)}'
    return _iceriyor(metin, KAPSAM_ETKEN)


# ═══════════════════════════════════════════════════════════════════════
# DISPATCHER — yolak belirleme
# ═══════════════════════════════════════════════════════════════════════

def kadin_hormonlari_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """'Y1' | 'Y2' | 'Y3' | None (kapsam dışı)."""
    if not kadin_hormonlari_kapsami_mi(ilac_sonuc):
        return None
    atc = _atc(ilac_sonuc)
    eu = _etken_metni(ilac_sonuc)
    adu = _ad_metni(ilac_sonuc)
    metin = f'{adu} {eu}'
    ostrojen_var = _iceriyor(metin, ESTROJEN_KEYS)
    kombine = _kombine_mi(eu)

    # (2) Tek başına dienogest → Y2
    dienogest = atc.startswith(DIENOGEST_ATC) or _iceriyor(metin, DIENOGEST_KEYS)
    if dienogest and not ostrojen_var and not kombine:
        return 'Y2'

    # (3) Tek başına progesteron + topikal → Y3 (oral progesteron → Y1)
    progesteron = (atc.startswith(PROGESTERON_ATC)
                   or (_iceriyor(eu, PROGESTERON_KEYS)
                       and 'MEDROKS' not in eu and 'HIDROKS' not in eu
                       and 'HYDROKS' not in eu))
    if progesteron and not ostrojen_var and not kombine:
        if _topikal_mi(adu, eu):
            return 'Y3'
        return 'Y1'  # oral progesteron → (1) progestojen grubu

    # (1) Östrojen / HRT / progestojen / kontraseptif → Y1
    return 'Y1'


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR — yetki (reçete uzmanı VEYA uzman raporu)
# ═══════════════════════════════════════════════════════════════════════

def _atom_recete_yetki(ilac_sonuc: Dict, substr_set: Tuple[str, ...],
                       grup: str, yetki_adi: str) -> SartSonuc:
    """A: reçeteyi yazan hekim yetkili branşta mı?"""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    yetkili = _brans_yetkili(brans, substr_set)
    if yetkili is None:
        return SartSonuc(ad='Reçete eden uzman branşı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, veya_grubu=True,
                         sartli_atom=True)
    if yetkili:
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden=f'{yetki_adi} — reçete edebilir',
                         kaynak='hekim_brans', grup=grup, veya_grubu=True)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden=f'{yetki_adi} değil — uzman hekim raporu gerekir',
                     kaynak='hekim_brans', grup=grup, veya_grubu=True)


def _atom_rapor_yetki(ilac_sonuc: Dict, substr_set: Tuple[str, ...],
                      grup: str, yetki_adi: str) -> SartSonuc:
    """B: yetkili branş uzmanınca düzenlenmiş uzman hekim raporu VAR mı?"""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    yetkili = _brans_yetkili(rb, substr_set)
    if yetkili:
        return SartSonuc(ad=f'{yetki_adi} uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb} — tüm hekimler reçete edebilir',
                         kaynak='rapor_brans', grup=grup, veya_grubu=True)
    if not rapor_var:
        return SartSonuc(ad=f'{yetki_adi} uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu yok',
                         kaynak='rapor', grup=grup, veya_grubu=True)
    if rb:
        return SartSonuc(ad=f'{yetki_adi} uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — {yetki_adi.lower()} değil',
                         kaynak='rapor_brans', grup=grup, veya_grubu=True)
    return SartSonuc(ad=f'{yetki_adi} uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=grup, veya_grubu=True, sartli_atom=True)


def _atom_prospektus_uyumu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """C3: rapor prospektüs endikasyonlarıyla uyumlu mu? (parse edilemez)."""
    return SartSonuc(
        ad='Prospektüs endikasyon uyumu', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor prospektüs endikasyonlarıyla uyumlu olmalı — manuel doğrulanmalı',
        kaynak='rapor', grup=grup, veya_grubu=False, sartli_atom=True)


# ── Yolak şart kümeleri ──
GRUP_Y1 = '(1) Yetki — endo/KHD/iç hast./ortopedi/FTR/aile hek. reçete VEYA raporu'
GRUP_Y2 = '(2) Yetki — kadın hast. ve doğum reçete VEYA KHD raporu'
GRUP_Y3 = '(3) Yetki — kadın hast. ve doğum reçete VEYA KHD raporu'
GRUP_Y3_BILGI = '(3) Prospektüs endikasyon uyumu (bilgi)'


def _y1_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    ad = 'Endo/KHD/iç hast./ortopedi/FTR/aile hek. uzmanı'
    return [
        _atom_recete_yetki(ilac_sonuc, Y1_YETKI_SUBSTR, GRUP_Y1, ad),
        _atom_rapor_yetki(ilac_sonuc, Y1_YETKI_SUBSTR, GRUP_Y1, ad),
    ]


def _y2_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    ad = 'Kadın hastalıkları ve doğum uzmanı'
    return [
        _atom_recete_yetki(ilac_sonuc, KHD_YETKI_SUBSTR, GRUP_Y2, ad),
        _atom_rapor_yetki(ilac_sonuc, KHD_YETKI_SUBSTR, GRUP_Y2, ad),
    ]


def _y3_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    ad = 'Kadın hastalıkları ve doğum uzmanı'
    return [
        _atom_recete_yetki(ilac_sonuc, KHD_YETKI_SUBSTR, GRUP_Y3, ad),
        _atom_rapor_yetki(ilac_sonuc, KHD_YETKI_SUBSTR, GRUP_Y3, ad),
        _atom_prospektus_uyumu(ilac_sonuc, GRUP_Y3_BILGI),
    ]


def _sartlari_uret(ilac_sonuc: Dict, yolak: str) -> List[SartSonuc]:
    if yolak == 'Y2':
        return _y2_sartlari(ilac_sonuc)
    if yolak == 'Y3':
        return _y3_sartlari(ilac_sonuc)
    return _y1_sartlari(ilac_sonuc)


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup bazlı — glokom/eritropoietin kalıbı)
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
    ke = [s for s in sartlar
          if s.durum == SartDurumu.KONTROL_EDILEMEDI and '(bilgi)' not in (s.grup or '')]
    yolak_ad = {'Y1': 'östrojen/HRT/progestojen',
                'Y2': 'tek başına dienogest',
                'Y3': 'tek başına progesteron (topikal)'}.get(yolak, yolak)
    parcalar = [f'SUT 4.2.29 Kadın hormonları ({yolak_ad})']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — yetkili uzman reçetesi veya uzman raporu var')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — yetki branşı doğrulanamadı '
                        f'({len(ke)} şart manuel)')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — reçete eden yetkili uzman değil ve '
                        'yetkili uzman raporu yok')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def kadin_hormonlari_kontrol_4_2_29(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.29 — Kadın cinsiyet hormonları kontrolü."""
    yolak = kadin_hormonlari_yolak_belirle(ilac_sonuc)
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.29 kapsamı dışı — kadın cinsiyet hormonu (G03A/C/D/F) değil',
            sut_kurali='SUT 4.2.29')

    sartlar = _sartlari_uret(ilac_sonuc, yolak)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'alt_grup': 'KADIN_HORMON',
        'yolak': yolak,
        'sut_maddesi': '4.2.29',
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
        sut_kurali='SUT 4.2.29 — Kadın cinsiyet hormonları',
        aranan_ibare='yetkili uzman reçetesi VEYA yetkili uzmanca düzenlenmiş uzman hekim raporu',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # ── Y1: östrojen / HRT / progestojen (6 branş) ──
        ("Y1 UYGUN (estradiol, endokrinoloji reçete)", {
            'etkin_madde': 'ESTRADIOL', 'atc_kodu': 'G03CA03',
            'doktor_uzmanligi': 'Endokrinoloji ve Metabolizma',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (tibolon, FTR reçete)", {
            'ilac_adi': 'LIVIAL', 'etkin_madde': 'TIBOLON', 'atc_kodu': 'G03CX01',
            'doktor_uzmanligi': 'Fiziksel Tıp ve Rehabilitasyon',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (HRT komb., aile hek + ortopedi raporu)", {
            'ilac_adi': 'ANGELIQ', 'etkin_madde': 'ESTRADIOL/DROSPIRENON',
            'atc_kodu': 'G03FA', 'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Ortopedi ve Travmatoloji', 'rapor_kodu': '321',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (oral progesteron, iç hastalıkları)", {
            'ilac_adi': 'PROGESTAN 100 MG KAPSUL', 'etkin_madde': 'PROGESTERON',
            'atc_kodu': 'G03DA04', 'doktor_uzmanligi': 'İç Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN DEĞİL (estradiol, kardiyoloji + rapor yok)", {
            'etkin_madde': 'ESTRADIOL', 'atc_kodu': 'G03CA03',
            'doktor_uzmanligi': 'Kardiyoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (estradiol, dermatoloji + nöroloji raporu)", {
            'etkin_madde': 'ESTRADIOL', 'atc_kodu': 'G03CA03',
            'doktor_uzmanligi': 'Dermatoloji',
            'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '7',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 ŞARTLI (estradiol, branş bilinmiyor + rapor yok)", {
            'etkin_madde': 'ESTRADIOL', 'atc_kodu': 'G03CA03',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y1 UYGUN (kontraseptif G03A, KHD reçete)", {
            'ilac_adi': 'YASMIN', 'etkin_madde': 'ETINILESTRADIOL/DROSPIRENON',
            'atc_kodu': 'G03AA12', 'doktor_uzmanligi': 'Kadın Hastalıkları ve Doğum',
        }, KontrolSonucu.UYGUN),

        # ── Y2: tek başına dienogest (yalnız KHD) ──
        ("Y2 UYGUN (dienogest tek, KHD reçete)", {
            'ilac_adi': 'VISANNE 2 MG', 'etkin_madde': 'DIENOGEST',
            'atc_kodu': 'G03DB08', 'doktor_uzmanligi': 'Kadın Hastalıkları ve Doğum',
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN (dienogest tek, dahiliye + KHD raporu)", {
            'ilac_adi': 'VISANNE', 'etkin_madde': 'DIENOGEST', 'atc_kodu': 'G03DB08',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_doktor_brans': 'Kadın Hastalıkları ve Doğum', 'rapor_takip_no': '55',
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN DEĞİL (dienogest tek, endokrinoloji reçete)", {
            'ilac_adi': 'VISANNE', 'etkin_madde': 'DIENOGEST', 'atc_kodu': 'G03DB08',
            'doktor_uzmanligi': 'Endokrinoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y2 UYGUN DEĞİL (dienogest tek, aile hek + endokrin raporu)", {
            'ilac_adi': 'VISANNE', 'etkin_madde': 'DIENOGEST', 'atc_kodu': 'G03DB08',
            'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Endokrinoloji', 'rapor_kodu': '12',
        }, KontrolSonucu.UYGUN_DEGIL),

        # ── Y3: tek başına progesteron topikal (yalnız KHD + prospektüs bilgi) ──
        ("Y3 UYGUN (progesteron jel, KHD reçete)", {
            'ilac_adi': 'CRINONE %8 VAJINAL JEL', 'etkin_madde': 'PROGESTERON',
            'atc_kodu': 'G03DA04', 'doktor_uzmanligi': 'Kadın Hastalıkları ve Doğum',
        }, KontrolSonucu.UYGUN),
        ("Y3 UYGUN (progesteron jel, pratisyen + KHD raporu)", {
            'ilac_adi': 'CRINONE VAJINAL JEL', 'etkin_madde': 'PROGESTERON',
            'atc_kodu': 'G03DA04', 'doktor_uzmanligi': 'Pratisyen',
            'rapor_doktor_brans': 'Kadın Hastalıkları ve Doğum', 'rapor_kodu': '90',
        }, KontrolSonucu.UYGUN),
        ("Y3 UYGUN DEĞİL (progesteron jel, dermatoloji + rapor yok)", {
            'ilac_adi': 'CRINONE VAJINAL JEL', 'etkin_madde': 'PROGESTERON',
            'atc_kodu': 'G03DA04', 'doktor_uzmanligi': 'Dermatoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y3 ŞARTLI (progesteron jel, branş bilinmiyor)", {
            'ilac_adi': 'CRINONE VAJINAL JEL', 'etkin_madde': 'PROGESTERON',
            'atc_kodu': 'G03DA04',
        }, KontrolSonucu.SARTLI_UYGUN),

        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (testosteron G03B)", {
            'etkin_madde': 'TESTOSTERON', 'atc_kodu': 'G03BA03',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.29 Kadın Cinsiyet Hormonları — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = kadin_hormonlari_kontrol_4_2_29(ilac_sonuc)
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
