# -*- coding: utf-8 -*-
"""SUT 4.2.23 — Sistemik antifungaller (amfoterisin-B/kaspofungin/anidulafungin/
vorikonazol/posakonazol/itrakonazol/mikafungin) kullanım ilkeleri.

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:7355-7395). Bu modül madde (2) +
(7) GENEL ÇERÇEVESİNİ uygular (kullanıcı 2026-06-04). İlaç-spesifik alt-
endikasyonlar (madde 3 itrakonazol / 4 posakonazol / 5 anidulafungin / 6
mikafungin — AML/MDS/HSCT/nötropeni/refrakter aspergilloz vb.) → (bilgi)/manuel:
    (1) Mülga.
    (2) Bu maddedeki etken maddeli ilaçlar sistemik mantar enfeksiyonları
        tedavisinde kullanılırsa karşılanır.
    (7) Lipozomal/lipid/kolloidal amfoterisin-B parenteral, kaspofungin,
        anidulafungin, vorikonazol, mikafungin, posakonazol veya itrakonazol
        (infüzyon): uzman hekim raporu + enfeksiyon hastalıkları uzmanı onayı
        ile YATARAK tedavide. Bu ilaçların ORAL formları ise enfeksiyon
        hastalıkları uzmanınca düzenlenen uzman hekim raporuna dayanılarak TÜM
        uzman hekimlerce reçetelenirse AYAKTA tedavide de kullanılır.

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI. FORM (oral/parenteral) dispatcher.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: form)
═══════════════════════════════════════════════════════════════════════════

  PARENTERAL/infüzyon → YATARAK tedavi (enfeksiyon uzmanı onayı) →
      ayakta eczane reçetesinde KARŞILANMAZ → UYGUN DEĞİL

  ORAL ⇔ A1(sistemik mantar enfeksiyonu endikasyonu)
         ∧ C1(enfeksiyon hastalıkları uzmanı raporu)
         ∧ D1(reçete eden uzman hekim)
         [bilgi: ilaç-spesifik alt-endikasyon (madde 3-6) manuel]

Echinocandinler (kaspofungin/anidulafungin/mikafungin) + amfoterisin = yalnız
parenteral. Azoller (vori/posa/itra) oral∨parenteral — form metninden.

Ana entrypoint: ``antifungal_kontrol_4_2_23(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — 4.2.23 spesifik etkenler (flukonazol J02AC01 HARİÇ)
# ═══════════════════════════════════════════════════════════════════════
# Yalnız parenteral (oral formu yok) → form text önemsiz
AMFOTERISIN: Set[str] = {'AMFOTERISIN', 'AMPHOTERICIN', 'AMBISOME', 'ABELCET',
                         'AMPHOCIL', 'FUNGIZONE'}
EKINOKANDIN: Set[str] = {'KASPOFUNGIN', 'CASPOFUNGIN', 'CANCIDAS',
                         'ANIDULAFUNGIN', 'ANIDILOFUNGIN', 'ECALTA',
                         'MIKAFUNGIN', 'MICAFUNGIN', 'MYCAMINE'}
# Oral ∨ parenteral (azoller)
AZOL: Set[str] = {'VORIKONAZOL', 'VORICONAZOLE', 'VORIKANAZOL', 'VFEND',
                  'POSAKONAZOL', 'POSACONAZOLE', 'NOXAFIL',
                  'ITRAKONAZOL', 'ITRACONAZOLE', 'SPORANOX', 'ITRASPOR'}

ATC_4223 = ('J02AA01', 'J02AX04', 'J02AX05', 'J02AX06',  # ampho, kaspo, mika, anidula
            'J02AC02', 'J02AC03', 'J02AC04')              # itra, vori, posa
ATC_PARENTERAL_FORCED = ('J02AA01', 'J02AX04', 'J02AX05', 'J02AX06')

ORAL_FORM = ('tablet', 'tb', 'kapsul', 'kapsül', 'suspansiyon', 'süspansiyon',
             'solusyon', 'solüsyon', 'oral', 'draje', 'film')
PARENTERAL_FORM = ('infuzyon', 'infüzyon', 'flakon', 'ampul', 'enjeksiyon',
                   'parenteral', 'liyofilize', ' iv', 'i.v', 'vial')

# Sistemik mantar endikasyonu
MANTAR_ICD = ('B37', 'B38', 'B39', 'B40', 'B41', 'B42', 'B43', 'B44', 'B45',
              'B46', 'B48', 'B49')
MANTAR_METIN = ('mantar enfeksiyon', 'fungal', 'aspergill', 'kandid', 'candid',
                'kriptokok', 'cryptococ', 'mukormikoz', 'mucor', 'fusarioz',
                'invaziv fungal', 'invazif fungal', 'sistemik mantar',
                'koksidio', 'fungemi', 'kandidemi')

ENFEKSIYON_BRANS = ('enfeksiyon', 'enfeksiyon hastalik', 'klinik mikrobiyoloji')
NON_UZMAN = ('pratisyen', 'aile hek', 'genel pratisyen', 'pratisyen tabip')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _ad(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')


def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume) -> bool:
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


def _brans_listede(brans: Optional[str], anahtarlar) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def antifungal_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if any(atc.startswith(p) for p in ATC_4223):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, AMFOTERISIN) or _iceriyor(m, EKINOKANDIN) or _iceriyor(m, AZOL)


def _form_belirle(ilac_sonuc: Dict) -> str:
    """'PARENTERAL' | 'ORAL' | 'BELIRSIZ'."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    m = _arama_metni(ilac_sonuc)
    # Echinocandin + amfoterisin → yalnız parenteral
    if any(atc.startswith(p) for p in ATC_PARENTERAL_FORCED) \
            or _iceriyor(m, AMFOTERISIN) or _iceriyor(m, EKINOKANDIN):
        return 'PARENTERAL'
    ad_l = norm_tr_lower(_ad(ilac_sonuc))
    if any(f in ad_l for f in PARENTERAL_FORM):
        return 'PARENTERAL'
    if any(f in ad_l for f in ORAL_FORM):
        return 'ORAL'
    return 'BELIRSIZ'  # azol, form metni yok


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_ENDIK = '(2) Sistemik mantar enfeksiyonu endikasyonu'
GRUP_RAPOR = '(oral) Enfeksiyon hastalıkları uzmanı raporu'
GRUP_RECETE = '(oral) Reçete eden uzman hekim'
GRUP_ALT_ENDIK = '(3-6) İlaç-spesifik alt-endikasyon (bilgi)'
GRUP_PARENTERAL = '(7) Parenteral form — yatarak tedavi'


def atom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    icd_var = any(k in icd for k in MANTAR_ICD)
    metin_var = any(k in metin for k in MANTAR_METIN)
    if icd_var or metin_var:
        return SartSonuc(ad='Sistemik mantar enfeksiyonu endikasyonu',
                         durum=SartDurumu.VAR,
                         neden=('ICD ' + next(k for k in MANTAR_ICD if k in icd))
                               if icd_var else 'rapor: mantar/fungal enfeksiyon',
                         kaynak='ICD+rapor', grup=GRUP_ENDIK)
    return SartSonuc(ad='Sistemik mantar enfeksiyonu endikasyonu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Sistemik mantar enfeksiyonu (ICD B37-B49 / metin) okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_ENDIK, sartli_atom=True)


def atom_enfeksiyon_rapor(ilac_sonuc: Dict) -> SartSonuc:
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _brans_listede(rb, ENFEKSIYON_BRANS):
        return SartSonuc(ad='Enfeksiyon hastalıkları uzmanı raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Enfeksiyon hastalıkları uzmanı raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor yok (oral form için enfeksiyon '
                               'hastalıkları uzmanı raporu zorunlu)',
                         kaynak='rapor', grup=GRUP_RAPOR)
    if rb:
        return SartSonuc(ad='Enfeksiyon hastalıkları uzmanı raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — enfeksiyon hastalıkları değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Enfeksiyon hastalıkları uzmanı raporu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş enfeksiyon hastalıkları olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_RAPOR, sartli_atom=True)


def atom_recete_uzman(ilac_sonuc: Dict) -> SartSonuc:
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden uzman hekim', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if any(k in bl for k in NON_UZMAN):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — yalnız uzman hekim reçete edebilir',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim — yetkili (enfeksiyon uzmanı raporuna dayanarak)',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def atom_alt_endikasyon_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    m = _arama_metni(ilac_sonuc)
    ilac = ('posakonazol' if _iceriyor(m, {'POSAKONAZOL', 'POSACONAZOLE', 'NOXAFIL'})
            else 'mikafungin' if _iceriyor(m, {'MIKAFUNGIN', 'MICAFUNGIN', 'MYCAMINE'})
            else 'anidulafungin' if _iceriyor(m, {'ANIDULAFUNGIN', 'ANIDILOFUNGIN', 'ECALTA'})
            else 'itrakonazol' if _iceriyor(m, {'ITRAKONAZOL', 'ITRACONAZOLE', 'SPORANOX'})
            else None)
    if ilac:
        return SartSonuc(ad=f'{ilac.capitalize()} alt-endikasyon şartları',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'SUT 4.2.23 madde 3-6: {ilac} için spesifik endikasyon/'
                               f'profilaksi şartları (AML/MDS/HSCT/nötropeni/refrakter vb.) '
                               f'— manuel doğrula', kaynak='ilac_endikasyon',
                         grup=GRUP_ALT_ENDIK, sartli_atom=True)
    return SartSonuc(ad='İlaç-spesifik alt-endikasyon', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Madde 3-6 ilaç-spesifik şartları varsa manuel doğrula',
                     kaynak='ilac_endikasyon', grup=GRUP_ALT_ENDIK, sartli_atom=True)


def atom_parenteral_yatarak(ilac_sonuc: Dict) -> SartSonuc:
    return SartSonuc(
        ad='Parenteral form — yatarak tedavi', durum=SartDurumu.YOK,
        neden='Parenteral/infüzyon antifungal yalnız YATARAK tedavide (enfeksiyon '
              'hastalıkları uzmanı onayı ile) kullanılır — ayakta eczane reçetesinde '
              'karşılanmaz (oral form gerekir)',
        kaynak='form', grup=GRUP_PARENTERAL)


def _antifungal_sartlari(ilac_sonuc: Dict, form: str) -> List[SartSonuc]:
    if form == 'PARENTERAL':
        return [atom_parenteral_yatarak(ilac_sonuc)]
    # ORAL veya BELIRSIZ (azol, ayakta bağlam → oral varsayım)
    return [
        atom_endikasyon(ilac_sonuc),
        atom_enfeksiyon_rapor(ilac_sonuc),
        atom_recete_uzman(ilac_sonuc),
        atom_alt_endikasyon_bilgi(ilac_sonuc),  # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (ortak grup-bazlı kalıp)
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


def _mesaj_uret(sonuc: KontrolSonucu, form: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    form_ad = {'PARENTERAL': 'parenteral (yatarak)', 'ORAL': 'oral (ayakta)',
               'BELIRSIZ': 'oral varsayım (ayakta)'}.get(form, form)
    parcalar = [f'SUT 4.2.23 Sistemik antifungal / {form_ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — enfeksiyon uzmanı raporu + uzman hekim reçete + endikasyon')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:2]))
    else:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def antifungal_kontrol_4_2_23(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.23 — Sistemik antifungal kullanım ilkeleri kontrolü."""
    if not antifungal_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.23 kapsamı dışı — 4.2.23 sistemik antifungali değil',
            sut_kurali='SUT 4.2.23')

    form = _form_belirle(ilac_sonuc)
    sartlar = _antifungal_sartlari(ilac_sonuc, form)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, form, sartlar)

    detaylar = {
        'alt_grup': 'ANTIFUNGAL',
        'sut_maddesi': '4.2.23',
        'form': form,
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
        sut_kurali='SUT 4.2.23 — Sistemik antifungaller (form: oral/parenteral)',
        aranan_ibare='oral: enfeksiyon uzmanı raporu + uzman hekim reçete + sistemik '
                     'mantar / parenteral: yatarak tedavi',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("ORAL UYGUN (vorikonazol tablet + enfeksiyon rapor + uzman + aspergilloz)", {
            'ilac_adi': 'VFEND 200 MG TABLET', 'etkin_madde': 'VORIKONAZOL',
            'atc_kodu': 'J02AC03', 'rapor_doktor_brans': 'Enfeksiyon Hastalıkları',
            'doktor_uzmanligi': 'Göğüs Hastalıkları', 'rapor_kodu': '1',
            'recete_teshisleri': ['B44.0'], 'rapor_aciklamalari': ['invaziv aspergilloz'],
        }, KontrolSonucu.UYGUN),
        ("ORAL UYGUN (posakonazol süspansiyon + enfeksiyon rapor)", {
            'ilac_adi': 'NOXAFIL ORAL SÜSPANSİYON', 'etkin_madde': 'POSAKONAZOL',
            'atc_kodu': 'J02AC04', 'rapor_doktor_brans': 'Enfeksiyon Hastalıkları',
            'doktor_uzmanligi': 'Hematoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['invazif fungal enfeksiyon profilaksisi'],
        }, KontrolSonucu.UYGUN),
        ("ORAL UYGUN DEĞİL (rapor enfeksiyon değil)", {
            'ilac_adi': 'VFEND TABLET', 'etkin_madde': 'VORIKONAZOL', 'atc_kodu': 'J02AC03',
            'rapor_doktor_brans': 'Göğüs Hastalıkları', 'doktor_uzmanligi': 'Göğüs',
            'rapor_kodu': '1', 'recete_teshisleri': ['B44.0'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ORAL UYGUN DEĞİL (rapor yok)", {
            'ilac_adi': 'SPORANOX SOLÜSYON', 'etkin_madde': 'ITRAKONAZOL',
            'atc_kodu': 'J02AC02', 'doktor_uzmanligi': 'Dermatoloji',
            'recete_teshisleri': ['B37.0'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ORAL UYGUN DEĞİL (reçete pratisyen)", {
            'ilac_adi': 'VFEND TABLET', 'etkin_madde': 'VORIKONAZOL', 'atc_kodu': 'J02AC03',
            'rapor_doktor_brans': 'Enfeksiyon Hastalıkları', 'doktor_uzmanligi': 'Pratisyen Tabip',
            'rapor_kodu': '1', 'recete_teshisleri': ['B44.0'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ORAL ŞARTLI (endikasyon okunamadı)", {
            'ilac_adi': 'VFEND TABLET', 'etkin_madde': 'VORIKONAZOL', 'atc_kodu': 'J02AC03',
            'rapor_doktor_brans': 'Enfeksiyon Hastalıkları', 'doktor_uzmanligi': 'Hematoloji',
            'rapor_kodu': '1', 'recete_teshisleri': ['Z00.0'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("PARENTERAL UYGUN DEĞİL (kaspofungin IV — yatarak)", {
            'ilac_adi': 'CANCIDAS 50 MG FLAKON', 'etkin_madde': 'KASPOFUNGIN',
            'atc_kodu': 'J02AX04', 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
            'recete_teshisleri': ['B37.7'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("PARENTERAL UYGUN DEĞİL (lipozomal amfoterisin)", {
            'ilac_adi': 'AMBISOME 50 MG FLAKON', 'etkin_madde': 'AMFOTERISIN B',
            'atc_kodu': 'J02AA01', 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("PARENTERAL UYGUN DEĞİL (vorikonazol infüzyon)", {
            'ilac_adi': 'VFEND 200 MG İV İNFÜZYON FLAKON', 'etkin_madde': 'VORIKONAZOL',
            'atc_kodu': 'J02AC03', 'doktor_uzmanligi': 'Enfeksiyon Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Kapsam dışı (flukonazol — 4.2.23 değil)", {
            'ilac_adi': 'FLUCAN KAPSUL', 'etkin_madde': 'FLUKONAZOL', 'atc_kodu': 'J02AC01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.23 Sistemik antifungal — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = antifungal_kontrol_4_2_23(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
