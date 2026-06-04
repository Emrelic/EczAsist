# -*- coding: utf-8 -*-
"""SUT EK-4/F m.69 — Pentosan polisülfat sodyum (interstisyel sistit).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste m.69):
    "Pentosan polisülfat sodyum; interstisyel sistite bağlı ağrılı mesane ve
     kronik ağrılı işeme semptomları bulunan, sistoskopik olarak mesanede
     glomerülasyon bulgusunun gösterildiği ve idrar kültürü negatif olan
     hastalarda; bu durumların belirtildiği üroloji uzman hekimleri tarafından
     düzenlenen 3 ay süreli uzman hekim raporuna dayanılarak tedaviye başlanır.
     Tedaviye başlandıktan 3 ay sonra üroloji uzman hekimi tarafından tedaviye
     yanıt alındığının ve tedaviyi kesmeyi gerektirecek yan etkilerin ortaya
     çıkmadığının raporda belirtilmesi koşulu ile 3 ay daha tedaviye devam
     edilir. Tedaviye yanıt alınamayan hastalarda 6. ayın sonunda tedavi
     kesilir. Tedaviden fayda gören hastalarda ... 6 ay süreli uzman hekim
     raporlarıyla ve üroloji uzman hekimlerince reçete düzenlenmek suretiyle
     tedaviye devam edilebilir."

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI. Başlangıç ⊻ devam çok-fazlı yapı
(EOS rapor-ordinalitesi dispatcher — alprostadil kalıbı). Konum: ÜROLOJİ butonu.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: başlangıç / devam)
═══════════════════════════════════════════════════════════════════════════

  ORTAK: C1(üroloji uzman hekim raporu)

  BAŞLANGIÇ ⇔ C1 ∧ A1(interstisyel sistit: ağrılı mesane ∧ kronik ağrılı işeme)
              ∧ A2(sistoskopik glomerülasyon bulgusu)
              ∧ A3(idrar kültürü negatif)   [bilgi: 3 ay rapor]

  DEVAM     ⇔ C1 ∧ D1(tedaviye yanıt alındı, raporda)
              ∧ D2(kesmeyi gerektiren yan etki çıkmadı, raporda)
              [bilgi: 3/6 ay rapor süresi; reçete üroloji]

Klinik ibareler (glomerülasyon/kültür/yanıt/yan etki) rapor metninden parse;
sessizlik → KE+şartlı (örtük kabul yasağı). C1 (üroloji rapor) tek hard gate;
endikasyon (A1) net YOK ise UYGUN DEĞİL.

Ana entrypoint: ``pentosan_kontrol_ek4f_69(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC G04BX15 pentosan polisülfat sodyum
# ═══════════════════════════════════════════════════════════════════════
ATC_PENTOSAN = 'G04BX15'
PENTOSAN_ETKEN: Set[str] = {'PENTOSAN', 'PENTOSAN POLISULFAT', 'PENTOSAN POLYSULFATE',
                            'PENTOSAN POLISULFAT SODYUM'}
PENTOSAN_TICARI: Set[str] = {'ELMIRON'}

UROLOJI = ('uroloji',)


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


def _recete_aciklama(ilac_sonuc: Dict) -> str:
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


def _uroloji_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in UROLOJI)


def pentosan_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_PENTOSAN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, PENTOSAN_ETKEN) or _iceriyor(m, PENTOSAN_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# BAŞLANGIÇ / DEVAM DİSPATCHER (EOS rapor-ordinalitesi)
# ═══════════════════════════════════════════════════════════════════════

def _pentosan_keywords() -> Tuple[str, ...]:
    return ('PENTOSAN', 'ELMIRON')


def pentosan_recete_tipi(ilac_sonuc: Dict) -> Tuple[str, str]:
    """('BASLANGIC'|'DEVAM', gerekçe). EOS RaporAna ordinalitesi > açıklama ibaresi."""
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('RaporAnaRaporTakipNo') or '').strip()
    if hasta_tc:
        try:
            from recete_kontrol.baslangic_rapor_bulucu import recete_tipi_eos_bazli
            tip, gerekce, _d = recete_tipi_eos_bazli(
                hasta_tc, _pentosan_keywords(), aktif_rapor_takip_no=aktif_takip or None)
            if tip == 'BASLANGIC':
                return ('BASLANGIC', f'EOS: {gerekce}')
            if tip == 'DEVAM':
                return ('DEVAM', f'EOS: {gerekce}')
        except Exception:
            pass
    ack = _recete_aciklama(ilac_sonuc)
    if re.search(r'\bdevam\b', ack) or 'yanit alind' in ack or 'tedaviye yanit' in ack:
        return ('DEVAM', 'Reçete/rapor açıklamasında "devam/yanıt alındı" ibaresi')
    return ('BASLANGIC', 'EOS\'ta geçmiş rapor yok ve "devam" ibaresi yok — '
                         'başlangıç varsayıldı (manuel doğrula)')


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_RAPOR = 'Üroloji uzman hekim raporu'
GRUP_B_ENDIK = '(Başlangıç) İnterstisyel sistit — ağrılı mesane + kronik ağrılı işeme'
GRUP_B_GLOM = '(Başlangıç) Sistoskopik glomerülasyon bulgusu'
GRUP_B_KULTUR = '(Başlangıç) İdrar kültürü negatif'
GRUP_B_SURE = '(Başlangıç) Rapor 3 ay süreli (bilgi)'
GRUP_D_YANIT = '(Devam) Tedaviye yanıt alındı (raporda)'
GRUP_D_YANETKI = '(Devam) Kesmeyi gerektiren yan etki çıkmadı (raporda)'
GRUP_D_SURE = '(Devam) Rapor süresi 3/6 ay (bilgi)'


def atom_uroloji_rapor(ilac_sonuc: Dict) -> SartSonuc:
    """C1 (ortak): üroloji uzman hekim raporu."""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _uroloji_mi(rb):
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı üroloji uzman hekim raporu yok',
                         kaynak='rapor', grup=GRUP_RAPOR)
    if rb:
        return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — üroloji değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Üroloji uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş üroloji olarak doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_RAPOR, sartli_atom=True)


def atom_b_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    sistit = ('N30.1' in icd or 'N301' in icd or 'interstisyel sistit' in metin
              or 'agrili mesane' in metin or 'mesane agri sendrom' in metin
              or 'bladder pain' in metin)
    isem = ('agrili iseme' in metin or 'kronik agrili iseme' in metin
            or 'dizuri' in metin)
    alt = [('İnterstisyel sistit / ağrılı mesane', 'var' if sistit else 'kontrol_edilemedi'),
           ('Kronik ağrılı işeme', 'var' if isem else 'kontrol_edilemedi')]
    if sistit:
        return SartSonuc(ad='İnterstisyel sistit endikasyonu', durum=SartDurumu.VAR,
                         neden='interstisyel sistit / ağrılı mesane' +
                               (' + ağrılı işeme' if isem else ''),
                         kaynak='ICD+rapor', grup=GRUP_B_ENDIK, alt_liste=alt)
    return SartSonuc(ad='İnterstisyel sistit endikasyonu', durum=SartDurumu.YOK,
                     neden='İnterstisyel sistit / ağrılı mesane endikasyonu (ICD N30.1 / '
                           'metin) saptanmadı', kaynak='ICD+rapor', grup=GRUP_B_ENDIK,
                     alt_liste=alt)


def atom_b_glomerulasyon(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'glomerulasyon' in metin or 'glomerülasyon' in metin:
        return SartSonuc(ad='Sistoskopik glomerülasyon bulgusu', durum=SartDurumu.VAR,
                         neden='Rapor: glomerülasyon bulgusu', kaynak='rapor_metni',
                         grup=GRUP_B_GLOM)
    return SartSonuc(ad='Sistoskopik glomerülasyon bulgusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Glomerülasyon bulgusu rapor metninde okunamadı — manuel',
                     kaynak='rapor_metni', grup=GRUP_B_GLOM, sartli_atom=True)


def atom_b_kultur_negatif(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'idrar kultur' in metin and ('negatif' in metin or 'ureme yok' in metin
                                    or 'ureme olmad' in metin or 'steril' in metin):
        return SartSonuc(ad='İdrar kültürü negatif', durum=SartDurumu.VAR,
                         neden='Rapor: idrar kültürü negatif/üreme yok',
                         kaynak='rapor_metni', grup=GRUP_B_KULTUR)
    if 'idrar kultur' in metin and ('pozitif' in metin or 'ureme var' in metin):
        return SartSonuc(ad='İdrar kültürü negatif', durum=SartDurumu.YOK,
                         neden='Rapor: idrar kültüründe üreme var (pozitif)',
                         kaynak='rapor_metni', grup=GRUP_B_KULTUR)
    return SartSonuc(ad='İdrar kültürü negatif', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İdrar kültürü sonucu rapor metninde okunamadı — manuel',
                     kaynak='rapor_metni', grup=GRUP_B_KULTUR, sartli_atom=True)


def atom_d_yanit(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'yanit alinamad' in metin or 'yanit yok' in metin or 'fayda gormed' in metin:
        return SartSonuc(ad='Tedaviye yanıt alındı', durum=SartDurumu.YOK,
                         neden='Rapor: tedaviye yanıt alınamadı — 6. ay sonunda kesilir',
                         kaynak='rapor_metni', grup=GRUP_D_YANIT)
    if 'yanit alind' in metin or 'tedaviye yanit' in metin or 'fayda gor' in metin \
            or 'klinik yanit' in metin or 'iyilesme' in metin:
        return SartSonuc(ad='Tedaviye yanıt alındı', durum=SartDurumu.VAR,
                         neden='Rapor: tedaviye yanıt alındı / fayda görüldü',
                         kaynak='rapor_metni', grup=GRUP_D_YANIT)
    return SartSonuc(ad='Tedaviye yanıt alındı', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Tedaviye yanıt ibaresi rapor metninde okunamadı — manuel',
                     kaynak='rapor_metni', grup=GRUP_D_YANIT, sartli_atom=True)


def atom_d_yan_etki(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'yan etki yok' in metin or 'yan etki gozlenmedi' in metin \
            or 'yan etki ortaya cikmad' in metin or 'yan etki cikmad' in metin \
            or 'tedaviyi kesmeyi gerektir' in metin:
        return SartSonuc(ad='Kesmeyi gerektiren yan etki çıkmadı', durum=SartDurumu.VAR,
                         neden='Rapor: tedaviyi kesmeyi gerektiren yan etki çıkmadı',
                         kaynak='rapor_metni', grup=GRUP_D_YANETKI)
    return SartSonuc(ad='Kesmeyi gerektiren yan etki çıkmadı',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Yan etki durumu rapor metninde belirtilmemiş — manuel '
                           '(devam raporunda bu husus belirtilmeli)',
                     kaynak='rapor_metni', grup=GRUP_D_YANETKI, sartli_atom=True)


def _sure_bilgi(grup: str, label: str) -> SartSonuc:
    return SartSonuc(ad=label, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor süresi tarih alanından manuel doğrulanmalı',
                     kaynak='rapor_tarihleri', grup=grup, sartli_atom=True)


def _pentosan_sartlari(ilac_sonuc: Dict, tip: str) -> List[SartSonuc]:
    s: List[SartSonuc] = [atom_uroloji_rapor(ilac_sonuc)]
    if tip == 'DEVAM':
        s.append(atom_d_yanit(ilac_sonuc))
        s.append(atom_d_yan_etki(ilac_sonuc))
        s.append(_sure_bilgi(GRUP_D_SURE, 'Rapor süresi 3/6 ay'))
    else:  # BASLANGIC
        s.append(atom_b_endikasyon(ilac_sonuc))
        s.append(atom_b_glomerulasyon(ilac_sonuc))
        s.append(atom_b_kultur_negatif(ilac_sonuc))
        s.append(_sure_bilgi(GRUP_B_SURE, 'Rapor süresi 3 ay'))
    return s


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


def _mesaj_uret(sonuc: KontrolSonucu, tip: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    tip_ad = {'BASLANGIC': 'başlangıç (3 ay)', 'DEVAM': 'devam'}.get(tip, tip)
    parcalar = [f'EK-4/F m.69 Pentosan / {tip_ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm şartlar sağlandı')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} klinik şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    else:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def pentosan_kontrol_ek4f_69(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.69 — Pentosan polisülfat sodyum (interstisyel sistit)."""
    if not pentosan_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F m.69 kapsamı dışı — pentosan polisülfat değil',
            sut_kurali='SUT EK-4/F m.69')

    tip, tip_gerekce = pentosan_recete_tipi(ilac_sonuc)
    sartlar = _pentosan_sartlari(ilac_sonuc, tip)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, tip, sartlar)

    detaylar = {
        'alt_grup': 'PENTOSAN',
        'sut_maddesi': 'EK-4/F m.69',
        'recete_tipi': tip,
        'recete_tipi_gerekce': tip_gerekce,
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
        sut_kurali='SUT EK-4/F m.69 — Pentosan polisülfat (interstisyel sistit)',
        aranan_ibare='üroloji raporu + (başlangıç: sistit+glomerülasyon+kültür neg / '
                     'devam: yanıt+yan etki yok)',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("BAŞLANGIÇ UYGUN (tüm bulgular + üroloji rapor)", {
            'etkin_madde': 'PENTOSAN POLISULFAT', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['interstisyel sistit ağrılı mesane kronik ağrılı işeme '
                                   'sistoskopik glomerülasyon idrar kültürü negatif'],
        }, KontrolSonucu.UYGUN),
        ("BAŞLANGIÇ ŞARTLI (endikasyon var, glomerülasyon/kültür okunamadı)", {
            'ilac_adi': 'ELMIRON', 'etkin_madde': 'PENTOSAN',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['interstisyel sistit'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("BAŞLANGIÇ UYGUN DEĞİL (endikasyon yok)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N39.0'],
            'rapor_aciklamalari': ['idrar yolu enfeksiyonu'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("BAŞLANGIÇ UYGUN DEĞİL (kültür pozitif)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['interstisyel sistit glomerülasyon idrar kültürü '
                                   'pozitif üreme var'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor branş kardiyoloji)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Kardiyoloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['interstisyel sistit glomerülasyon kültür negatif'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['interstisyel sistit glomerülasyon kültür negatif'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("DEVAM UYGUN (yanıt + yan etki yok + üroloji rapor)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['devam tedaviye yanıt alındı yan etki yok'],
        }, KontrolSonucu.UYGUN),
        ("DEVAM UYGUN DEĞİL (yanıt alınamadı)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['devam tedaviye yanıt alınamadı'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("DEVAM ŞARTLI (yanıt var, yan etki ibaresi yok)", {
            'etkin_madde': 'PENTOSAN', 'atc_kodu': 'G04BX15',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '1',
            'recete_teshisleri': ['N30.1'],
            'rapor_aciklamalari': ['devam tedaviye yanıt alındı'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F m.69 Pentosan — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = pentosan_kontrol_ek4f_69(ilac_sonuc)
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
