# -*- coding: utf-8 -*-
"""SUT 4.1.4 — Kalsiyum dobesilat (DOXIUM) genel raporlu-ilaç kontrolü.

Kalsiyum dobesilatın (ATC C05BX01) ÖZEL SUT maddesi YOKTUR (tarama 2026-07-05):
ana tebliğ `SUT_tam_metin.txt` negatif, EK-4/E negatif, EK-4/F negatif.
Kontrol genel çerçeve kurallarından kurulur — resmî lafız (SUT_tam_metin.txt):

  4.1.4(3) (satır 3918-3921):
    "İlacın reçete edilmesindeki özel düzenlemeler saklı kalmak kaydıyla, SUT
     eki EK-4/F ve EK-4/D listelerinde yer almamakla birlikte, uzun süreli
     kullanımı sağlık raporu ile belgelendirilen ilaçlar, katılım payı alınmak
     koşuluyla en fazla üç aylık tedavi dozunda reçete edilebilir."

  4.1.4(5)(a) (satır 3951-3955):
    "İlk defa reçete edilecek ilaçlar raporlu olsa dahi kullanım dozuna göre,
     bir ayı geçmeyecek sürelerde ödenir. Reçeteye yazılan ilacın miktarı,
     ambalaj boyutu dikkate alınarak toplamda 4 haftalık doza yetecek miktarda
     ise bu dozlar da bir aylık doz olarak kabul edilir."

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI. Kullanıcı onayı: 2026-07-05
(şema aynen; kapsam SADECE kalsiyum dobesilat; ÇEŞİTLİ altında).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: rapor varlığı)
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ ‖Y-RAPORSUZ‖ A1(miktar ≤ 1 aylık doz)
        ∨ ‖Y-RAPORLU‖  R1(rapor mevcut)
                      ∧ R2(etken madde raporda yazılı)
                      ∧ R3(ilk/devam tespiti — ilkse 1 ay, devamsa 3 ay)
                      ∧ R4(miktar ≤ R3 limitine göre 1/3 aylık doz)
  B1 endikasyon uyumu (KVY/hemoroid/diyabetik retinopati) → (bilgi), hesap dışı.

Sessizlik kararları (onaylı tablo):
  - R2 pozitif atom: rapor metni VAR ama etken geçmiyor → YOK;
    rapor metni hiç ulaşılamadı (EOS'a inmemiş olabilir) → KE (örtük ret yasağı).
  - R3/R4/A1 doz-geçmiş belirsizliği → KE + sartli_atom (ŞARTLI_UYGUN yolu).

Ana entrypoint: ``dobesilat_kontrol_genel_raporlu(ilac_sonuc)`` → ``KontrolRaporu``.
Kapsam tespiti: ``dobesilat_kapsami_mi(ilac_sonuc)``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC C05BX01 kalsiyum dobesilat + etken + ticari
# ═══════════════════════════════════════════════════════════════════════
ATC_DOBESILAT = ('C05BX01', 'C05BX51')  # tek + kombinasyon
DOBESILAT_ETKEN: Set[str] = {
    'KALSIYUM DOBESILAT', 'DOBESILAT KALSIYUM', 'DOBESILAT',
    'CALCIUM DOBESILATE', 'KALSIYUM DOBESILAT MONOHIDRAT',
}
DOBESILAT_TICARI: Set[str] = {'DOXIUM', 'DOBESIFAR', 'MODET'}

# KÜB günlük doz aralığı (mg) — DOXIUM KT: 500-1500 mg/gün
GUNLUK_DOZ_MIN_MG = 500.0
GUNLUK_DOZ_MAX_MG = 1500.0

# Gün limitleri (4.1.4(5)a ambalaj toleransı için +5 gün pay)
LIMIT_BIR_AY_GUN = 35.0
LIMIT_UC_AY_GUN = 95.0

# Endikasyon sinyalleri (KÜB: kronik venöz yetmezlik / hemoroid /
# diyabetik retinopati — bilgi grubu, hesap dışı)
ENDIKASYON_ICD = ('I83', 'I87.2', 'I87.8', 'K64', 'I84', 'H36.0',
                  'E10.3', 'E11.3', 'E13.3', 'E14.3')
ENDIKASYON_METIN = ('venoz yetmezlik', 'venöz yetmezlik', 'kronik venoz',
                    'varis', 'hemoroid', 'hemoroidal', 'retinopati',
                    'diyabetik retinopati', 'staz dermatit', 'bacak odem',
                    'bacak ödem')


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
    """Yalnız RAPOR kaynaklı metinler (reçete açıklaması karıştırılmaz —
    R2 'etken raporda yazılı' atomu rapor lafzına bakar)."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'rapor_kodu_aciklama', 'rap_ack'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'rapor_etken_maddeleri'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_upper(' '.join(parcalar))


def _teshis_birlesik(ilac_sonuc: Dict) -> str:
    teshisler: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            teshisler.extend(str(x) for x in v if x)
        elif v:
            teshisler.append(str(v))
    return norm_tr_upper(' '.join(teshisler))


def dobesilat_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if any(atc.startswith(p) for p in ATC_DOBESILAT):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, DOBESILAT_ETKEN) or _iceriyor(m, DOBESILAT_TICARI)


def _rapor_var_mi(ilac_sonuc: Dict) -> Tuple[bool, str]:
    """Rapor varlığı dispatcher'ı. Kod/takip no en güçlü sinyal."""
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    takip_no = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    if rapor_kodu:
        return True, f'Rapor kodu: {rapor_kodu}'
    if takip_no:
        return True, f'Rapor takip no: {takip_no}'
    if _rapor_metni(ilac_sonuc).strip():
        return True, 'Rapor metni/açıklaması mevcut (kodu satıra inmemiş)'
    return False, 'Rapor kodu/takip no/metin yok — raporsuz reçete'


def _doz_gun_hesabi(ilac_sonuc: Dict) -> Optional[Tuple[float, float, str]]:
    """(min_gün, max_gün, açıklama) — kutu × ambalaj × birim mg / KÜB günlük doz.
    Parse edilemezse None (→ KE+şartlı)."""
    ad = norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')
    kutu_raw = ilac_sonuc.get('kutu_sayisi')
    if kutu_raw is None or str(kutu_raw).strip() == '':
        kutu_raw = ilac_sonuc.get('miktar', '')
    try:
        kutu = float(str(kutu_raw).replace(',', '.'))
    except (ValueError, TypeError):
        return None
    if kutu <= 0:
        return None
    m_mg = re.search(r'(\d+(?:[.,]\d+)?)\s*MG', ad)
    m_adet = re.search(r'(\d+)\s*(?:X\s*)?(?:KAPSUL|KAPSÜL|KPS|TABLET|TB|FTB|'
                       r'FILM TABLET|DRAJE)', ad)
    if not m_mg or not m_adet:
        return None
    birim_mg = float(m_mg.group(1).replace(',', '.'))
    adet = float(m_adet.group(1))
    toplam_mg = kutu * adet * birim_mg
    min_gun = toplam_mg / GUNLUK_DOZ_MAX_MG
    max_gun = toplam_mg / GUNLUK_DOZ_MIN_MG
    aciklama = (f'{kutu:g} kutu × {adet:g} × {birim_mg:g}mg = {toplam_mg:g}mg '
                f'→ {min_gun:.0f}-{max_gun:.0f} gün (KÜB {GUNLUK_DOZ_MIN_MG:g}-'
                f'{GUNLUK_DOZ_MAX_MG:g} mg/gün)')
    return min_gun, max_gun, aciklama


# ═══════════════════════════════════════════════════════════════════════
# İLK / DEVAM tespiti (EOS rapor-ordinalitesi — pentosan kalıbı)
# ═══════════════════════════════════════════════════════════════════════

def _dobesilat_keywords() -> Tuple[str, ...]:
    return ('DOBESILAT', 'DOXIUM', 'DOBESIFAR', 'MODET')


def dobesilat_recete_tipi(ilac_sonuc: Dict) -> Tuple[str, str]:
    """('ILK'|'DEVAM'|'BELIRSIZ', gerekçe)."""
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    aktif_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    if hasta_tc:
        try:
            from recete_kontrol.baslangic_rapor_bulucu import recete_tipi_eos_bazli
            tip, gerekce, _d = recete_tipi_eos_bazli(
                hasta_tc, _dobesilat_keywords(),
                aktif_rapor_takip_no=aktif_takip or None)
            if tip == 'BASLANGIC':
                return ('ILK', f'EOS: {gerekce}')
            if tip == 'DEVAM':
                return ('DEVAM', f'EOS: {gerekce}')
        except Exception:
            pass
    ack = norm_tr_lower(' '.join(
        str(x) for x in (ilac_sonuc.get('recete_aciklamalari') or [])))
    if re.search(r'\bdevam\b', ack):
        return ('DEVAM', 'Reçete açıklamasında "devam" ibaresi')
    return ('BELIRSIZ', 'EOS geçmişi sorgulanamadı / kanıt yok — '
                        'ilk/devam belirsiz (manuel doğrula)')


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_A_DOZ = '‖Y-RAPORSUZ‖ (4.1.4) En fazla 1 aylık doz'
GRUP_R_RAPOR = '‖Y-RAPORLU‖ (4.1.4(3)) Sağlık raporu'
GRUP_R_ETKEN = '‖Y-RAPORLU‖ (4.1.4(3)) Etken madde raporda yazılı'
GRUP_R_ILKDEVAM = '‖Y-RAPORLU‖ (4.1.4(5)a) İlk/devam tespiti'
GRUP_R_DOZ = '‖Y-RAPORLU‖ (4.1.4(3)+(5)a) Miktar limiti'
GRUP_B_ENDIK = 'Endikasyon uyumu — KVY/hemoroid/diyabetik retinopati (bilgi)'


def atom_raporsuz_doz(ilac_sonuc: Dict) -> SartSonuc:
    """A1: raporsuz yolda miktar ≤ 1 aylık doz."""
    hesap = _doz_gun_hesabi(ilac_sonuc)
    if hesap is None:
        return SartSonuc(ad='Miktar ≤ 1 aylık doz',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Kutu/ambalaj/mg parse edilemedi — manuel doğrula',
                         kaynak='doz', grup=GRUP_A_DOZ, sartli_atom=True)
    min_gun, _max_gun, aciklama = hesap
    if min_gun <= LIMIT_BIR_AY_GUN:
        return SartSonuc(ad='Miktar ≤ 1 aylık doz', durum=SartDurumu.VAR,
                         neden=f'{aciklama} — 1 aylık için makul',
                         kaynak='doz', grup=GRUP_A_DOZ)
    return SartSonuc(ad='Miktar ≤ 1 aylık doz',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'{aciklama} — raporsuz 1 aylık dozu aşıyor '
                           f'olabilir, manuel doğrula',
                     kaynak='doz', grup=GRUP_A_DOZ, sartli_atom=True)


def atom_rapor_mevcut(ilac_sonuc: Dict, gerekce: str) -> SartSonuc:
    """R1: rapor mevcut (dispatcher bu yola soktuysa VAR)."""
    return SartSonuc(ad='Sağlık raporu mevcut', durum=SartDurumu.VAR,
                     neden=gerekce, kaynak='rapor_kodu', grup=GRUP_R_RAPOR)


def atom_etken_raporda(ilac_sonuc: Dict) -> SartSonuc:
    """R2: 'KALSIYUM DOBESILAT' rapor lafzında/etken listesinde yazılı.
    3-yönlü: yazılı→VAR; metin var ama geçmiyor→YOK; metin hiç yok→KE."""
    metin = _rapor_metni(ilac_sonuc)
    if not metin.strip():
        return SartSonuc(ad='Etken madde raporda yazılı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor metni/açıklaması ulaşılamadı (EOS\'a '
                               'inmemiş olabilir) — manuel doğrula',
                         kaynak='rapor_metni', grup=GRUP_R_ETKEN,
                         sartli_atom=True)
    if 'DOBESILAT' in metin or 'DOBESILATE' in metin:
        return SartSonuc(ad='Etken madde raporda yazılı', durum=SartDurumu.VAR,
                         neden='Rapor lafzında "DOBESILAT" ibaresi bulundu',
                         kaynak='rapor_metni', grup=GRUP_R_ETKEN)
    return SartSonuc(ad='Etken madde raporda yazılı', durum=SartDurumu.YOK,
                     neden='Rapor metni mevcut ancak KALSIYUM DOBESILAT '
                           'ibaresi yok — 4.1.4(3) "uzun süreli kullanımı '
                           'sağlık raporu ile belgelendirilen" şartı sağlanmıyor',
                     kaynak='rapor_metni', grup=GRUP_R_ETKEN)


def atom_ilk_devam(ilac_sonuc: Dict) -> Tuple[SartSonuc, str]:
    """R3: ilk/devam tespiti → (atom, tip). Limit R4'e taşınır."""
    tip, gerekce = dobesilat_recete_tipi(ilac_sonuc)
    if tip == 'DEVAM':
        return (SartSonuc(ad='İlk/devam tespiti', durum=SartDurumu.VAR,
                          neden=f'DEVAM reçetesi — {gerekce} → 3 aylık limit',
                          kaynak='hasta_gecmisi', grup=GRUP_R_ILKDEVAM), tip)
    if tip == 'ILK':
        return (SartSonuc(ad='İlk/devam tespiti', durum=SartDurumu.VAR,
                          neden=f'İLK reçete — {gerekce} → raporlu olsa dahi '
                                f'1 aylık limit (4.1.4(5)a)',
                          kaynak='hasta_gecmisi', grup=GRUP_R_ILKDEVAM), tip)
    return (SartSonuc(ad='İlk/devam tespiti',
                      durum=SartDurumu.KONTROL_EDILEMEDI,
                      neden=f'{gerekce} — 1 aylık limit varsayıldı',
                      kaynak='hasta_gecmisi', grup=GRUP_R_ILKDEVAM,
                      sartli_atom=True), tip)


def atom_raporlu_doz(ilac_sonuc: Dict, tip: str) -> SartSonuc:
    """R4: miktar limiti — DEVAM→3 ay, İLK/BELİRSİZ→1 ay (4.1.4(5)a)."""
    limit = LIMIT_UC_AY_GUN if tip == 'DEVAM' else LIMIT_BIR_AY_GUN
    etiket = '3 aylık' if tip == 'DEVAM' else '1 aylık'
    hesap = _doz_gun_hesabi(ilac_sonuc)
    if hesap is None:
        return SartSonuc(ad=f'Miktar ≤ {etiket} doz',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Kutu/ambalaj/mg parse edilemedi — manuel doğrula',
                         kaynak='doz', grup=GRUP_R_DOZ, sartli_atom=True)
    min_gun, _max_gun, aciklama = hesap
    if min_gun <= limit:
        return SartSonuc(ad=f'Miktar ≤ {etiket} doz', durum=SartDurumu.VAR,
                         neden=f'{aciklama} — {etiket} limit için makul',
                         kaynak='doz', grup=GRUP_R_DOZ)
    return SartSonuc(ad=f'Miktar ≤ {etiket} doz',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'{aciklama} — {etiket} dozu aşıyor olabilir, '
                           f'manuel doğrula',
                     kaynak='doz', grup=GRUP_R_DOZ, sartli_atom=True)


def atom_endikasyon_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """B1 (bilgi): KÜB endikasyonu sinyali — hesap dışı. KÜB dışı kullanımda
    4.1.4(4) Bakanlık endikasyon dışı onayı gerekir (manuel)."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = norm_tr_lower(' '.join(filter(None, [
        _rapor_metni(ilac_sonuc),
        ' '.join(str(x) for x in (ilac_sonuc.get('recete_aciklamalari') or [])),
        icd,
    ])))
    icd_hit = any(k in icd for k in ENDIKASYON_ICD)
    metin_hit = any(norm_tr_lower(k) in metin for k in ENDIKASYON_METIN)
    alt = [('KVY/varis', 'var' if ('varis' in metin or 'venoz' in metin
                                   or 'venöz' in metin or 'I83' in icd
                                   or 'I87' in icd) else 'yok'),
           ('Hemoroid', 'var' if ('hemoroid' in metin or 'K64' in icd
                                  or 'I84' in icd) else 'yok'),
           ('Diyabetik retinopati', 'var' if ('retinopati' in metin
                                              or 'H36' in icd) else 'yok')]
    if icd_hit or metin_hit:
        return SartSonuc(ad='Endikasyon uyumu (KÜB)', durum=SartDurumu.VAR,
                         neden='KÜB endikasyonu sinyali bulundu',
                         kaynak='ICD+metin', grup=GRUP_B_ENDIK, alt_liste=alt)
    return SartSonuc(ad='Endikasyon uyumu (KÜB)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='KÜB endikasyonu (KVY/hemoroid/diyabetik retinopati) '
                           'sinyali yok — KÜB dışı ise 4.1.4(4) Bakanlık onayı '
                           'gerekir, manuel doğrula',
                     kaynak='ICD+metin', grup=GRUP_B_ENDIK, alt_liste=alt)


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ
# ═══════════════════════════════════════════════════════════════════════

def _dobesilat_sartlari(ilac_sonuc: Dict) -> Tuple[List[SartSonuc], str]:
    rapor_var, gerekce = _rapor_var_mi(ilac_sonuc)
    sartlar: List[SartSonuc] = []
    if rapor_var:
        yol = 'RAPORLU'
        sartlar.append(atom_rapor_mevcut(ilac_sonuc, gerekce))
        sartlar.append(atom_etken_raporda(ilac_sonuc))
        r3, tip = atom_ilk_devam(ilac_sonuc)
        sartlar.append(r3)
        sartlar.append(atom_raporlu_doz(ilac_sonuc, tip))
    else:
        yol = 'RAPORSUZ'
        sartlar.append(atom_raporsuz_doz(ilac_sonuc))
    sartlar.append(atom_endikasyon_bilgi(ilac_sonuc))
    sartlar.append(_atom_muafiyet_bilgi(ilac_sonuc))
    return sartlar, yol


# EK-4/D m.4.4 "Periferik ve serebral damar hastalıkları, venöz yetmezlikler"
# muafiyet ICD prefixleri (dobesilat: yalnız 4.4 üzerinden muaf; Raynaud I73.0
# ve diyabetik retinopati H36/E1x.3 dobesilat için muaf DEĞİL — ödenir, paylı).
_MUAF_44_PREFIX = ('G46', 'I63', 'I65', 'I66', 'I67', 'I68', 'I69', 'I70',
                   'I71', 'I72', 'I74', 'I77', 'I79', 'I82', 'I83', 'I85', 'I87')
GRUP_MUAF_BILGI = 'Katılım payı muafiyeti EK-4/D 4.4 (bilgi)'


def _atom_muafiyet_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """EK-4/D katılım payı muafiyeti — bilgi grubu, hesap dışı (muafiyet
    ödemeyi engellemez, yalnız katılım payını etkiler)."""
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    takip_no = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    if not rapor_kodu and not takip_no and not _rapor_metni(ilac_sonuc).strip():
        return SartSonuc(ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
                         neden='Rapor yok — raporsuz ödenir (katılım payı '
                               'alınır); muafiyet için rapor + EK-4/D 4.4 ICD gerekir',
                         kaynak='rapor', grup=GRUP_MUAF_BILGI, sartli_atom=True)
    icd = _teshis_birlesik(ilac_sonuc).replace(' ', '')
    tokenlar = [t for t in re.split(r'[,;|]', icd) if t]
    if not tokenlar:
        return SartSonuc(ad='Katılım payı muafiyeti',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama teşhis ICD okunamadı — muafiyet '
                               '(EK-4/D 4.4) manuel doğrulanmalı',
                         kaynak='ICD', grup=GRUP_MUAF_BILGI, sartli_atom=True)
    muaf = next((t for t in tokenlar
                 if any(t.startswith(p) for p in _MUAF_44_PREFIX)
                 or (t.startswith('I73') and not t.startswith('I73.0')
                     and not t.startswith('I730'))), None)
    if muaf:
        return SartSonuc(ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
                         neden=f'ICD {muaf} → EK-4/D m.4.4 (damar/venöz) — '
                               f'katılım payından MUAF',
                         kaynak='ICD', grup=GRUP_MUAF_BILGI, sartli_atom=True)
    return SartSonuc(ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
                     neden='ICD EK-4/D 4.4 dışı (Raynaud/retinopati dahil '
                           'dobesilat muaf DEĞİL) — ödenir, katılım paylı',
                     kaynak='ICD', grup=GRUP_MUAF_BILGI, sartli_atom=True)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    hesap = [s for s in sartlar if '(bilgi)' not in (s.grup or '')]
    if any(s.durum == SartDurumu.YOK for s in hesap):
        return KontrolSonucu.UYGUN_DEGIL
    ke = [s for s in hesap if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    if not ke and hesap and all(s.durum == SartDurumu.VAR for s in hesap):
        return KontrolSonucu.UYGUN
    if ke and all(s.sartli_atom for s in ke) and all(
            s.durum == SartDurumu.VAR for s in hesap
            if s.durum != SartDurumu.KONTROL_EDILEMEDI):
        return KontrolSonucu.SARTLI_UYGUN
    return KontrolSonucu.KONTROL_EDILEMEDI


def _mesaj_uret(sonuc: KontrolSonucu, yol: str) -> str:
    on = f'SUT 4.1.4 Genel Raporlu — Kalsiyum dobesilat [{yol} yolu]'
    if sonuc == KontrolSonucu.UYGUN:
        return f'{on} | UYGUN'
    if sonuc == KontrolSonucu.SARTLI_UYGUN:
        return f'{on} | ŞARTLI UYGUN — doz/geçmiş şartlı atomlar manuel doğrulanmalı'
    if sonuc == KontrolSonucu.UYGUN_DEGIL:
        return f'{on} | UYGUN DEĞİL — etken madde raporda yazılı değil'
    return f'{on} | ŞÜPHELİ — manuel doğrulama gerekli'


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def dobesilat_kontrol_genel_raporlu(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.1.4(3)+(5)a — kalsiyum dobesilat genel raporlu-ilaç kontrolü."""
    if not dobesilat_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — kalsiyum dobesilat değil',
            sut_kurali='SUT 4.1.4 — Genel raporlu (kalsiyum dobesilat)')

    sartlar, yol = _dobesilat_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yol)

    detaylar = {
        'alt_grup': 'DOBESILAT',  # 'GENEL_RAPORLU' genel kategoriyle çakışmasın
        'sut_maddesi': '4.1.4(3) + 4.1.4(5)a',
        'yol': yol,
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
        sut_kurali='SUT 4.1.4(3)+(5)a — Özel maddesi olmayan raporlu ilaç '
                   '(kalsiyum dobesilat): raporsuz ≤1 ay / raporlu ≤3 ay, '
                   'ilk reçete raporlu olsa dahi ≤1 ay',
        aranan_ibare='rapor + KALSIYUM DOBESILAT etken kaydı + miktar limiti',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("RAPORLU DEVAM UYGUN olamaz — EOS'suz DEVAM ibaresi + etken raporda "
         "+ 60 kapsül (2 ay ≤ 3 ay)", {
            'ilac_adi': 'DOXIUM 1000MG 60 KAPSÜL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'rapor_kodu': '99.99', 'kutu_sayisi': '1',
            'rapor_aciklamalari': ['KALSIYUM DOBESILAT,PENTOKSIFILIN (Ekleme=05/06/2026)'],
            'recete_aciklamalari': ['devam'],
            'recete_teshisleri': ['I83.9'],
        }, KontrolSonucu.UYGUN),
        ("RAPORLU İLK-belirsiz ŞARTLI (etken raporda, 60 kapsül 1 ayı aşabilir)", {
            'ilac_adi': 'DOXIUM 1000MG 60 KAPSÜL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'rapor_kodu': '99.99', 'kutu_sayisi': '1',
            'rapor_aciklamalari': ['KALSIYUM DOBESILAT'],
            'recete_teshisleri': ['I83.9'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("RAPORLU UYGUN DEĞİL (rapor metni var, dobesilat yazmıyor)", {
            'ilac_adi': 'DOXIUM 500 MG 60 KAPSUL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'rapor_kodu': '10.01', 'kutu_sayisi': '1',
            'rapor_aciklamalari': ['METFORMIN, GLIKLAZID'],
            'recete_aciklamalari': ['devam'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("RAPORLU ŞARTLI (rapor kodu var ama metin EOS'a inmemiş)", {
            'ilac_adi': 'DOXIUM 500 MG 60 KAPSUL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'rapor_kodu': '10.01', 'kutu_sayisi': '1',
            'recete_aciklamalari': ['devam'], 'recete_teshisleri': ['K64.9'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("RAPORSUZ UYGUN (500mg 60 kapsül = 20-60 gün, min 20 ≤ 35)", {
            'ilac_adi': 'DOXIUM 500 MG 60 KAPSUL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'kutu_sayisi': '1', 'recete_teshisleri': ['I84.9'],
        }, KontrolSonucu.UYGUN),
        ("RAPORSUZ ŞARTLI (1000mg 60 kapsül × 2 kutu = min 80 gün > 35)", {
            'ilac_adi': 'DOXIUM 1000MG 60 KAPSÜL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'kutu_sayisi': '2', 'recete_teshisleri': ['I83.9'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("RAPORSUZ ŞARTLI (kutu bilinmiyor → doz KE)", {
            'ilac_adi': 'DOXIUM 1000MG 60 KAPSÜL',
            'etkin_madde': 'KALSIYUM DOBESILAT', 'atc_kodu': 'C05BX01',
            'recete_teshisleri': ['I83.9'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (pentoksifilin — kullanıcı kararı: yalnız dobesilat)", {
            'ilac_adi': 'TRENTAL 400 MG 20 TABLET',
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("RAPORLU DEVAM + ticari ad tespiti (MODET) + hemoroid ICD", {
            'ilac_adi': 'MODET 500 MG 60 KAPSUL', 'etkin_madde': '',
            'atc_kodu': '', 'rapor_kodu': '99.99', 'kutu_sayisi': '1',
            'rapor_aciklamalari': ['DOBESILAT KALSIYUM'],
            'recete_aciklamalari': ['devam tedavisi'],
            'recete_teshisleri': ['K64.0'],
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.1.4 Genel Raporlu — Kalsiyum dobesilat Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = dobesilat_kontrol_genel_raporlu(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
