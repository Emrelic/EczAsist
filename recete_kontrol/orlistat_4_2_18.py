# -*- coding: utf-8 -*-
"""SUT 4.2.18 — Orlistat kullanım ilkeleri.

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:7308-7319, mevzuat.gov.tr
MevzuatNo=17229, Değişik:RG-30/8/2014-29104):
    (1) Endokrinoloji ve metabolizma uzman hekimi tarafından düzenlenen en
        fazla üç ay süreli uzman hekim raporuna dayanılarak tüm hekimler
        tarafından reçete edilebilir. Her reçeteye bir önceki reçeteye göre
        kaybedilen kilo, diyet ve egzersize uyum, BMI değeri hekimce yazılıp
        kaşe ve imza onayı yapılır.
    (2) Daha önce 4 ardışık hafta yalnızca diyetle ≥2,5 kg kilo kaybı ve obez
        hastalarda BMI ≥ 40 kg/m² olmalıdır.
    (3) Reçeteler birer aylık düzenlenir.
    (4) 12 hafta sonunda başlangıç ağırlığının ≥%5'i kaybedilirse tedavi yeni
        raporla üçer aylık uzatılır; %5 kaybedilmezse kesilir. Kullanım ömür
        boyu 2 yılı geçemez.

Protokol: docs/SUT_MANTIK_SEMA_PROTOKOLU.md + CLAUDE.md ATOMİK DEVRE ŞEMASI.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ C1(endokrinoloji ve metabolizma uzmanı raporu)
          ∧ F1(başlangıç BMI ≥ 40)
          [bilgi: C2 rapor ≤3 ay · E1 reçete beyanı(kilo/diyet/egzersiz/BMI/kaşe)
                  · F2 4 hf diyetle ≥2,5 kg · G1 reçete birer aylık
                  · H1 12 hf %5 kayıp + ≤2 yıl]

Tek hard gate C1 (rapor branşı endokrinoloji değil/rapor yok → UYGUN DEĞİL).
F1 BMI: ≥40 → VAR; <40/okunamaz → KE+şartlı (devam reçetesinde BMI düşmüş
olabilir, başlangıç değilse YOK denmez). Temporal/beyan şartları parse-zayıf →
(bilgi) grupta KE+şartlı → matematiği bozmaz, manuel doğrulanır.

Ana entrypoint: ``orlistat_kontrol_4_2_18(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC A08AB01 orlistat
# ═══════════════════════════════════════════════════════════════════════
ATC_ORLISTAT = 'A08AB01'
ORLISTAT_ETKEN: Set[str] = {'ORLISTAT'}
ORLISTAT_TICARI: Set[str] = {'XENICAL', 'ORSLIM', 'REDUMED', 'ALLI', 'ORLIFIT',
                             'ORLEV', 'ORLISTAT'}

ENDOKRIN_BRANS = ('endokrin',)  # 'endokrinoloji ve metabolizma'
# SUT-anlatı eşik işaretleri (BMI parse'ında hasta değeri ≠ eşik 40)
_NARRATIVE = ('>=', '≥', 'esit', 'eşit', 'uzeri', 'üzeri', 'altinda', 'buyuk',
              'olmali', 'olması', 'olmalı')


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


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _bmi_oku(metin: str) -> Optional[float]:
    """Rapor metninden hasta BMI değerini parse et (SUT eşik sayısı 40 atlanır)."""
    anahtarlar = ['bmi', 'bki', 'vucut kitle indeksi', 'vücut kitle indeksi',
                  'beden kitle indeksi']
    for a in anahtarlar:
        for m in re.finditer(re.escape(a) + r'[^\d\n]{0,12}?(\d{2,3}(?:[.,]\d+)?)', metin):
            before = metin[max(0, m.start() - 6):m.start()]
            after = metin[m.end():m.end() + 25]
            ctx = before + ' ' + after
            if any(tok in ctx for tok in _NARRATIVE):
                continue
            try:
                val = float(m.group(1).replace(',', '.'))
            except ValueError:
                continue
            if 10 <= val <= 90:  # makul BMI aralığı
                return val
    return None


def orlistat_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_ORLISTAT):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, ORLISTAT_ETKEN) or _iceriyor(m, ORLISTAT_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_RAPOR = '(1) Endokrinoloji ve metabolizma uzmanı raporu'
GRUP_RAPOR_SURE = '(1) Rapor ≤3 ay süreli (bilgi)'
GRUP_BEYAN = '(1) Reçete beyanı: kilo/diyet/egzersiz/BMI/kaşe (bilgi)'
GRUP_BMI = '(2) Başlangıç BMI ≥40'
GRUP_DIYET = '(2) 4 hafta diyetle ≥2,5 kg kayıp (bilgi)'
GRUP_AYLIK = '(3) Reçete birer aylık (bilgi)'
GRUP_DEVAM = '(4) 12 hf %5 kayıp + ≤2 yıl (bilgi)'


def atom_rapor_endokrin(ilac_sonuc: Dict) -> SartSonuc:
    """C1: endokrinoloji ve metabolizma uzmanı raporu (ZORUNLU gate)."""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _brans_listede(rb, ENDOKRIN_BRANS):
        return SartSonuc(ad='Endokrinoloji ve metabolizma uzmanı raporu',
                         durum=SartDurumu.VAR, neden=f'Rapor düzenleyen: {rb}',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Endokrinoloji ve metabolizma uzmanı raporu',
                         durum=SartDurumu.YOK, neden='Reçeteye bağlı uzman hekim raporu yok',
                         kaynak='rapor', grup=GRUP_RAPOR)
    if rb:
        return SartSonuc(ad='Endokrinoloji ve metabolizma uzmanı raporu',
                         durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — endokrinoloji ve metabolizma değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Endokrinoloji ve metabolizma uzmanı raporu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş endokrinoloji olarak doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_RAPOR, sartli_atom=True)


def atom_bmi_40(ilac_sonuc: Dict) -> SartSonuc:
    """F1: başlangıç BMI ≥40. ≥40 VAR; <40/okunamaz KE+şartlı (devam olabilir)."""
    metin = _rapor_metni(ilac_sonuc)
    bmi = _bmi_oku(metin)
    if bmi is None:
        return SartSonuc(ad='Başlangıç BMI ≥40', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='BMI değeri rapor metninden okunamadı — manuel',
                         kaynak='rapor_bmi', grup=GRUP_BMI, sartli_atom=True)
    if bmi >= 40:
        return SartSonuc(ad=f'Başlangıç BMI {bmi:g} (≥40)', durum=SartDurumu.VAR,
                         neden=f'BMI {bmi:g} — başlangıç şartı sağlanıyor',
                         kaynak='rapor_bmi', grup=GRUP_BMI)
    return SartSonuc(ad=f'BMI {bmi:g} (<40)', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'BMI {bmi:g} <40 — başlangıç ise şart sağlanmıyor, '
                           f'devam reçetesinde düşmüş olabilir, manuel doğrula',
                     kaynak='rapor_bmi', grup=GRUP_BMI, sartli_atom=True)


def _atom_bilgi(ad: str, neden: str, grup: str, kaynak: str = 'manuel') -> SartSonuc:
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI, neden=neden,
                     kaynak=kaynak, grup=grup, sartli_atom=True)


def _orlistat_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_rapor_endokrin(ilac_sonuc))
    s.append(atom_bmi_40(ilac_sonuc))
    # (bilgi) — parse-zayıf / manuel doğrulanacak şartlar (matematiği bozmaz)
    s.append(_atom_bilgi('Rapor ≤3 ay süreli',
                         'Rapor süresi en fazla 3 ay — tarih alanından manuel doğrula',
                         GRUP_RAPOR_SURE, 'rapor_tarihleri'))
    s.append(_atom_bilgi('Reçete beyanı (kilo kaybı + diyet/egzersiz + BMI + kaşe/imza)',
                         'Madde (1): her reçeteye önceki reçeteye göre kaybedilen kilo, '
                         'diyet/egzersiz uyumu, BMI yazılıp kaşe+imza — hekim beyanı, manuel',
                         GRUP_BEYAN, 'recete_beyan'))
    s.append(_atom_bilgi('4 hafta diyetle ≥2,5 kg kayıp',
                         'Madde (2) başlangıç: 4 ardışık hafta yalnız diyetle ≥2,5 kg '
                         'kayıp — rapordan manuel doğrula', GRUP_DIYET, 'rapor_metni'))
    s.append(_atom_bilgi('Reçete birer aylık',
                         'Madde (3): reçeteler birer aylık düzenlenir — doz/süre manuel',
                         GRUP_AYLIK, 'doz'))
    s.append(_atom_bilgi('12 hf %5 kayıp + toplam ≤2 yıl',
                         'Madde (4): 12 hf sonunda ≥%5 kayıp → devam (yeni rapor, 3er ay); '
                         '%5 yoksa kes; ömür boyu ≤2 yıl — hasta geçmişinden manuel',
                         GRUP_DEVAM, 'hasta_gecmisi'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (ortak grup-bazlı kalıp; (bilgi) gruplar hesaba katılmaz)
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


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['SUT 4.2.18 Orlistat']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — endokrinoloji raporu + BMI≥40')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama gerektiriyor '
                        f'(BMI/kilo takibi/kaşe-imza/süre)')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    else:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def orlistat_kontrol_4_2_18(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.18 — Orlistat kullanım ilkeleri kontrolü."""
    if not orlistat_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.18 kapsamı dışı — orlistat değil',
            sut_kurali='SUT 4.2.18')

    sartlar = _orlistat_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'ORLISTAT',
        'sut_maddesi': '4.2.18',
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
        sut_kurali='SUT 4.2.18 — Orlistat kullanım ilkeleri',
        aranan_ibare='endokrinoloji/metabolizma raporu (≤3 ay) + BMI≥40 + kilo takibi beyanı',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (endokrin rapor + BMI 42)", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_doktor_brans': 'Endokrinoloji ve Metabolizma Hastalıkları',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['obezite BMI 42 kg/m2'],
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (endokrin rapor, BMI okunamadı)", {
            'ilac_adi': 'XENICAL 120 MG', 'etkin_madde': 'ORLISTAT',
            'rapor_doktor_brans': 'Endokrinoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['obezite tedavisi'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (endokrin rapor, BMI 35 — devam olabilir)", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_doktor_brans': 'Endokrinoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['BMI 35 kilo kaybı devam'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN DEĞİL (rapor branş kardiyoloji)", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_doktor_brans': 'Kardiyoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['BMI 42'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_aciklamalari': ['BMI 42'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (endokrin rapor branş bilinmiyor ama rapor var)", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['BMI 45'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (ticari XENICAL + endokrin + BMI 41)", {
            'ilac_adi': 'XENICAL', 'etkin_madde': 'ORLISTAT',
            'rapor_doktor_brans': 'Endokrinoloji ve Metabolizma Hastalıkları',
            'rapor_takip_no': '999', 'rapor_aciklamalari': ['vücut kitle indeksi 41'],
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("BMI eşik sayısı (40) hasta değeri sanılmamalı → KE", {
            'etkin_madde': 'ORLISTAT', 'atc_kodu': 'A08AB01',
            'rapor_doktor_brans': 'Endokrinoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['BMI 40 kg/m2 ve üzeri olmalı'],
        }, KontrolSonucu.SARTLI_UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.18 Orlistat — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = orlistat_kontrol_4_2_18(ilac_sonuc)
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
