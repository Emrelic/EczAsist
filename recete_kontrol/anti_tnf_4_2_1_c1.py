# -*- coding: utf-8 -*-
"""SUT 4.2.1.C-1 — Anti-TNF (tümör nekrozis faktör) ilaçlar.

Etken maddeler: adalimumab, etanersept, infliksimab, sertolizumab pegol,
golimumab (ATC L04AB*).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:4083-4213`` (+ genel ilkeler
4065-4082). mevzuat.gov.tr MevzuatNo=17229. Protokol: ``docs/SUT_AI_PROTOKOL_v1.md``
+ ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ``ATOMİK DEVRE ŞEMASI``.

═══════════════════════════════════════════════════════════════════════════
İÇ DİSPATCHER — 12 ENDİKASYON YOLAĞI (ICD + teşhis metni + yaş)
═══════════════════════════════════════════════════════════════════════════

  RA       (1)a  Erişkin romatoid artrit          M05/M06,   yaş ≥18
  JRA      (1)b  Juvenil RA (poliartiküler)       M08,       yaş <18 (18+ devam)
  AS       (2)   Aksiyel AS / aksiyel spondilartrit  M45/M46
  PAS      (3)   Periferik eklem tutulumlu AS     M45/M46 + "periferik"
  PSA      (5)   Psöriyatik artrit                L40.5/M07
  PSO      (9)   Psoriazis vulgaris/plak tip      L40
  CROHN_E  (10)a Crohn — yetişkin                 K50,       yaş ≥18
  CROHN_C  (10)b Crohn — çocuk                    K50,       yaş <18
  UK       (11)  Ülseratif kolit                  K51
  UVEIT_E  (12)a Üveit — yetişkin                 H20/H30/H44 + "üveit"
  UVEIT_C  (12)b Üveit — çocuk (≥2 yaş)           H20 + "üveit"
  HS       (13)  Hidradenitis suppurativa         L73.2

═══════════════════════════════════════════════════════════════════════════
KARAR (kullanıcı onayı 2026-06-04)
═══════════════════════════════════════════════════════════════════════════
  1. Klinik şartlar (DAS28/BASDAİ/PASI/CDAI skorları, önceki tedavi) →
     PARSE-DENE: rapor metninde ara; ölçülmüş değer bulunup geçerse VAR,
     ölçülmüş değer net başarısızsa YOK, sessiz/operatörlü(SUT echo) → KE+şartlı.
     Önceki-tedavi ibareleri (yokluğu kanıtlanamaz) → KE+şartlı, asla YOK.
  2. Genel ilke (1) tedaviye ara + (3) iki tanı+iki biyolojik → BİLGİ atomu
     (şemada görünür, matematiği bozmaz; EOS/çapraz entegrasyon pilot sonrası).
  3. Başlangıç/idame → TEK ŞEMA: skor atomu hem başlangıç eşiğini hem idame
     (düşüş/devam ibaresi) kabul eder (VEYA mantığı).

Yapısal AND atomlar (endikasyon/SK raporu/heyet/branş/yaş/ilaç-kısıtı) net YOK
→ UYGUN DEĞİL. Klinik KE+şartlı atomlar → SARTLI_UYGUN (yapısal tamsa) ya da
ŞÜPHELİ. Sessizlik → örtük kabul YASAK (CLAUDE.md §2.5).

Ana entrypoint: ``anti_tnf_kontrol_4_2_1_c1(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# Anti-TNF ilaç setleri (etken + ticari, ASCII-upper)
# ═══════════════════════════════════════════════════════════════════════
ATC_ANTI_TNF_PREFIX = 'L04AB'  # TNF-alfa inhibitörleri

ADALIMUMAB: Set[str] = {
    'ADALIMUMAB', 'HUMIRA', 'AMGEVITA', 'IMRALDI', 'HYRIMOZ', 'HULIO',
    'YUFLYMA', 'IDACIO', 'HEFIYA', 'HADLIMA',
}
ETANERSEPT: Set[str] = {
    'ETANERSEPT', 'ETANERCEPT', 'ENBREL', 'BENEPALI', 'ERELZI', 'NEPEXTO',
}
INFLIKSIMAB: Set[str] = {
    'INFLIKSIMAB', 'INFLIXIMAB', 'REMICADE', 'INFLECTRA', 'REMSIMA',
    'FLIXABI', 'ZESSLY',
}
SERTOLIZUMAB: Set[str] = {
    'SERTOLIZUMAB', 'CERTOLIZUMAB', 'SERTOLIZUMAB PEGOL', 'CIMZIA',
}
GOLIMUMAB: Set[str] = {'GOLIMUMAB', 'SIMPONI'}

ANTI_TNF_HEPSI: Set[str] = (
    ADALIMUMAB | ETANERSEPT | INFLIKSIMAB | SERTOLIZUMAB | GOLIMUMAB
)

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower ile alt-string eşleşmesi)
# ═══════════════════════════════════════════════════════════════════════
ROMATOLOJI = ['romatoloji', 'romatizma']
KLINIK_IMMUN = ['klinik immun', 'immunoloji', 'immunoloj']
FTR = ['fiziksel tip', 'fizik tedavi', 'rehabilitasyon', 'ftr']
IC_HAST = ['ic hastalik', 'dahiliye']
COCUK_HAST = ['cocuk sagligi', 'cocuk hastalik', 'pediatri']
DERMATOLOJI = ['dermatoloji', 'deri ', 'cildiye']
GASTRO = ['gastroenteroloji', 'gastro']
GENEL_CERRAHI = ['genel cerrahi']
GOZ = ['goz hastalik', 'goz hekim', 'oftalmoloji', 'goz ']
COCUK_GASTRO = ['cocuk gastro']
COCUK_CERRAHI = ['cocuk cerrah']
PRATISYEN = ['pratisyen', 'aile hek', 'genel pratisyen']

# (6) Romatolojik endikasyonlarda reçete edebilecek branşlar
ROMATOLOJIK_RECETE_BRANS = (ROMATOLOJI + KLINIK_IMMUN + FTR +
                            IC_HAST + COCUK_HAST)
# (6) Raporda/heyette bulunması beklenen uzmanlar
ROMATOLOJIK_HEYET_BRANS = ROMATOLOJI + KLINIK_IMMUN + FTR

# ═══════════════════════════════════════════════════════════════════════
# ICD prefix setleri (endikasyon dispatcher)
# ═══════════════════════════════════════════════════════════════════════
ICD_RA = ('M05', 'M06')
ICD_JRA = ('M08',)
ICD_AS = ('M45', 'M46')
ICD_PSA = ('L40.5', 'M07')
ICD_PSO = ('L40',)
ICD_CROHN = ('K50',)
ICD_UK = ('K51',)
ICD_UVEIT = ('H20', 'H30', 'H44', 'H15', 'H22')
ICD_HS = ('L73.2', 'L73')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _rapor_metni(ilac_sonuc: Dict) -> str:
    """Rapor + reçete açıklama birleşik metni (norm_tr_lower — regex için)."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari',
                    'diger_ilac_adlari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_lower(' '.join(parcalar))


def _teshis_birlesik(ilac_sonuc: Dict) -> str:
    teshisler: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi', 'teshis_tum', 'diger_raporlar_icd'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            teshisler.extend(str(x) for x in v if x)
        elif v:
            teshisler.append(str(v))
    return norm_tr_upper(' '.join(teshisler))


def _icd_var(teshis_upper: str, prefixler) -> bool:
    """Teşhis metninde verilen ICD prefix'lerinden biri kelime başında var mı?"""
    for p in prefixler:
        pu = norm_tr_upper(p)
        # Kelime sınırı: prefix ya başta ya boşluk/noktalama sonrası
        if re.search(r'(^|[^A-Z0-9])' + re.escape(pu), teshis_upper):
            return True
    return False


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


def _bmi_oku(ilac_sonuc: Dict) -> Optional[float]:
    """BMI: alan / boy+kilo / rapor metni."""
    for anahtar in ('bmi', 'vki', 'beden_kitle_indeksi'):
        v = ilac_sonuc.get(anahtar)
        if v not in (None, ''):
            try:
                return float(str(v).replace(',', '.'))
            except (TypeError, ValueError):
                pass
    try:
        boy = float(str(ilac_sonuc.get('boy') or '').replace(',', '.'))
        kilo = float(str(ilac_sonuc.get('kilo') or '').replace(',', '.'))
        if boy > 3:           # cm girilmiş
            boy = boy / 100.0
        if boy > 0:
            return kilo / (boy * boy)
    except (TypeError, ValueError):
        pass
    metin = _rapor_metni(ilac_sonuc)
    val, _ = _lab_deger(metin, ['beden kitle indeksi', 'vki', 'bmi'])
    return val


def _lab_deger(metin: str, ibareler: List[str]) -> Tuple[Optional[float], bool]:
    """metin (norm_tr_lower) içinde ibare + sayısal değer ara.

    Returns: (değer, operatorlu). operatorlu=True ise sayı bir karşılaştırma
    operatörü ile yazılmış (>5,1 gibi) → büyük olasılıkla SUT lafzı/eşik echo'su,
    ölçülmüş hasta değeri değil → atom KE'ye düşürür (yanlış YOK önlenir).
    """
    for ib in ibareler:
        m = re.search(re.escape(ib) + r'\s*([<>≤≥]?=?)\s*[:=]?\s*(\d+[.,]?\d*)',
                      metin)
        if m:
            try:
                return float(m.group(2).replace(',', '.')), bool(m.group(1))
            except ValueError:
                continue
    return None, False


def _heyet_branslari(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [h.get('brans') or '' for h in heyet if isinstance(h, dict)]


def _rapor_var_mi(ilac_sonuc: Dict) -> bool:
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or
                   ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_turu = (ilac_sonuc.get('rapor_turu') or ilac_sonuc.get('rapor_turu_adi') or '').strip()
    return bool(rapor_kodu or rapor_takip or rapor_turu or _heyet_branslari(ilac_sonuc))


def _hangi_ilac(ilac_sonuc: Dict) -> Set[str]:
    """Bu kalem hangi anti-TNF etken? (etiketleme için)."""
    m = _arama_metni(ilac_sonuc)
    etiketler = set()
    if _iceriyor(m, ADALIMUMAB):
        etiketler.add('adalimumab')
    if _iceriyor(m, ETANERSEPT):
        etiketler.add('etanersept')
    if _iceriyor(m, INFLIKSIMAB):
        etiketler.add('infliksimab')
    if _iceriyor(m, SERTOLIZUMAB):
        etiketler.add('sertolizumab')
    if _iceriyor(m, GOLIMUMAB):
        etiketler.add('golimumab')
    return etiketler


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def anti_tnf_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_ANTI_TNF_PREFIX):
        return True
    return _iceriyor(_arama_metni(ilac_sonuc), ANTI_TNF_HEPSI)


def anti_tnf_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Endikasyon yolağını belirle. Returns yolak kodu | None (kapsam dışı)."""
    if not anti_tnf_kapsami_mi(ilac_sonuc):
        return None
    teshis = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    yas = _yas_oku(ilac_sonuc)

    # 1) Psöriyatik artrit (L40.5 / M07) — psoriazisten önce (eklem tutulumu)
    if _icd_var(teshis, ICD_PSA) or 'psoriyatik artrit' in metin or \
            'psoriatik artrit' in metin:
        return 'PSA'
    # 2) Psoriazis (plak)
    if _icd_var(teshis, ICD_PSO) or 'plak psoriazis' in metin or \
            'psoriazis vulgaris' in metin or 'plak tip psoriazis' in metin:
        return 'PSO'
    # 3) Juvenil RA
    if _icd_var(teshis, ICD_JRA) or 'juvenil' in metin:
        return 'JRA'
    # 4) Erişkin RA
    if _icd_var(teshis, ICD_RA) or 'romatoid artrit' in metin:
        if yas is not None and yas < 18:
            return 'JRA'
        return 'RA'
    # 5) Ankilozan spondilit — periferik mi aksiyel mi?
    if _icd_var(teshis, ICD_AS) or 'ankilozan spondilit' in metin or \
            'spondilartrit' in metin or 'spondiloartrit' in metin:
        if 'periferik' in metin:
            return 'PAS'
        return 'AS'
    # 6) Crohn
    if _icd_var(teshis, ICD_CROHN) or 'crohn' in metin:
        if yas is not None and yas < 18:
            return 'CROHN_C'
        return 'CROHN_E'
    # 7) Ülseratif kolit
    if _icd_var(teshis, ICD_UK) or 'ulseratif kolit' in metin:
        return 'UK'
    # 8) Üveit
    if 'uveit' in metin or 'panuveit' in metin or _icd_var(teshis, ICD_UVEIT):
        if yas is not None and yas < 18:
            return 'UVEIT_C'
        return 'UVEIT_E'
    # 9) Hidradenitis suppurativa
    if _icd_var(teshis, ICD_HS) or 'hidradenit' in metin or \
            'hidradenitis' in metin:
        return 'HS'
    return 'BELIRSIZ'


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_saglik_kurulu_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """SAĞLIK KURULU raporu (heyet raporu) zorunlu (tüm C-1 endikasyonları)."""
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or
                               ilac_sonuc.get('rapor_turu_adi') or '')
    heyet = _heyet_branslari(ilac_sonuc)
    heyet_n = len([b for b in heyet if b])
    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman' in rapor_turu) and ('kurul' not in rapor_turu)
    if kurul_isaret:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=f"Sağlık kurulu raporu "
                               f"({rapor_turu or 'heyet ' + str(heyet_n) + ' uzman'})",
                         kaynak='rapor_turu+heyet', grup=grup)
    if uzman_tek and heyet_n <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor "uzman hekim raporu" — 4.2.1.C-1 sağlık '
                               'kurulu raporu ister (heyet ≤1)',
                         kaynak='rapor_turu+heyet', grup=grup)
    if not _rapor_var_mi(ilac_sonuc):
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı — SK raporu zorunlu',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor türü/heyeti sağlık kurulu olarak doğrulanamadı — manuel',
                     kaynak='rapor_turu+heyet', grup=grup, sartli_atom=True)


def atom_yas_op(ilac_sonuc: Dict, grup: str, op: str, deger: int,
                etiket: str) -> SartSonuc:
    """Hasta yaşı karşılaştırma (>=18, <18, >=2 ...)."""
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı (DB) okunamadı — manuel doğrulama',
                         kaynak='hasta_yasi', grup=grup, sartli_atom=True)
    ok = {'>=': yas >= deger, '<': yas < deger, '>': yas > deger,
          '<=': yas <= deger}[op]
    return SartSonuc(ad=etiket, durum=SartDurumu.VAR if ok else SartDurumu.YOK,
                     neden=f'Hasta yaşı {yas} ({"uygun" if ok else "uygun değil"})',
                     kaynak='hasta_yasi', grup=grup)


def atom_recete_brans(ilac_sonuc: Dict, grup: str, izinli: List[str],
                      etiket: str) -> SartSonuc:
    """Reçeteyi düzenleyen hekim izinli branşta mı? Pratisyen/aile → YOK."""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, PRATISYEN):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — uzman hekim ister',
                         kaynak='hekim_brans', grup=grup)
    if _brans_listede(brans, izinli):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='İzinli branş', kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden=f'{etiket} gerekli — branş izinli listede değil',
                     kaynak='hekim_brans', grup=grup)


def atom_heyet_brans(ilac_sonuc: Dict, grup: str, gerekli: List[str],
                     etiket: str) -> SartSonuc:
    """Heyette gerekli branşlardan ≥1 var mı?"""
    heyet = _heyet_branslari(ilac_sonuc)
    if not heyet:
        return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — manuel doğrulama',
                         kaynak='heyet', grup=grup, sartli_atom=True)
    bulunan = [b for b in heyet if _brans_listede(b, gerekli)]
    if bulunan:
        return SartSonuc(ad=etiket, durum=SartDurumu.VAR,
                         neden=f"Heyette uygun branş: {', '.join(bulunan)}",
                         kaynak='heyet', grup=grup)
    return SartSonuc(ad=etiket, durum=SartDurumu.YOK,
                     neden=f"Heyette gerekli uzman yok (heyet: {', '.join(heyet)})",
                     kaynak='heyet', grup=grup)


def atom_ucuncu_basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """3. basamak resmi sağlık hizmeti sunucusu mu? (veri çoğu kez yok → KE)."""
    basamak = norm_tr_lower(str(ilac_sonuc.get('tesis_basamak') or
                                ilac_sonuc.get('saglik_tesisi_basamak') or
                                ilac_sonuc.get('basamak') or ''))
    if not basamak:
        return SartSonuc(ad='3. basamak resmi sağlık kurumu',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Tesis basamağı bilgisi yok — manuel doğrulama',
                         kaynak='tesis', grup=grup, sartli_atom=True)
    if '3' in basamak or 'ucuncu' in basamak:
        return SartSonuc(ad='3. basamak resmi sağlık kurumu', durum=SartDurumu.VAR,
                         neden=f'Tesis basamağı: {basamak}', kaynak='tesis', grup=grup)
    return SartSonuc(ad='3. basamak resmi sağlık kurumu', durum=SartDurumu.YOK,
                     neden=f'Tesis basamağı: {basamak} — 3. basamak gerekli',
                     kaynak='tesis', grup=grup)


def atom_ilac_kisiti(ilac_sonuc: Dict, grup: str, izinli: Set[str],
                     izinli_ad: str) -> SartSonuc:
    """Bu endikasyonda yalnız belirli anti-TNF'ler ödenir."""
    etiketler = _hangi_ilac(ilac_sonuc)
    if not etiketler:
        return SartSonuc(ad=f'İzinli etken: {izinli_ad}',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Etken madde tespit edilemedi — manuel',
                         kaynak='etken', grup=grup, sartli_atom=True)
    izinli_l = {x.lower() for x in izinli}
    if etiketler & izinli_l:
        return SartSonuc(ad=f'İzinli etken ({", ".join(etiketler)})',
                         durum=SartDurumu.VAR, neden=f'Bu endikasyonda izinli: {izinli_ad}',
                         kaynak='etken', grup=grup)
    return SartSonuc(ad=f'Etken: {", ".join(etiketler)}', durum=SartDurumu.YOK,
                     neden=f'Bu endikasyonda yalnız {izinli_ad} ödenir',
                     kaynak='etken', grup=grup)


# ── Genel ilke bilgi atomları (matematik dışı) ──────────────────────────

def atom_genel_ara_bilgi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """(1) Tedaviye ara → yeniden başlangıç (anti-TNF 6 ay). BİLGİ (EOS pilot sonrası)."""
    return SartSonuc(ad='(1) Tedaviye ara → yeniden başlangıç (anti-TNF: 6 ay)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='6 ay+ ara verildiyse başlangıç kriterleri aranır — '
                           'ilaç geçmişi (EOS) manuel kontrol',
                     kaynak='ilac_gecmisi', grup=grup, sartli_atom=True)


def atom_genel_iki_biyolojik_bilgi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """(3) İki farklı tanı + iki farklı biyolojik birlikte → karşılanmaz. BİLGİ."""
    # Aynı reçetede başka bir biyolojik var mı? (kaba kontrol — diger_ilac_adlari)
    metin_up = norm_tr_upper(' '.join(
        str(x) for x in (ilac_sonuc.get('diger_ilac_adlari') or [])
        if isinstance(ilac_sonuc.get('diger_ilac_adlari'), (list, tuple)) and x))
    bu = _hangi_ilac(ilac_sonuc)
    diger_anti_tnf = {a for a in ANTI_TNF_HEPSI if norm_tr_upper(a) in metin_up}
    if diger_anti_tnf and not (bu & {x.lower() for x in diger_anti_tnf}):
        return SartSonuc(ad='(3) İki farklı biyolojik birlikteliği',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetede/geçmişte başka biyolojik ajan işareti '
                               'var — iki tanı+iki biyolojik ise karşılanmaz, manuel',
                         kaynak='diger_ilac', grup=grup, sartli_atom=True)
    return SartSonuc(ad='(3) İki farklı biyolojik birlikteliği',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İki tanı + iki farklı biyolojik birlikteliği çapraz '
                           'reçete/rapor ile manuel doğrulanmalı',
                     kaynak='diger_ilac', grup=grup, sartli_atom=True)


# ── Klinik skor/önceki tedavi atomları (parse-dene + KE şartlı) ──────────

def _onceki_tedavi_atom(ilac_sonuc: Dict, grup: str, etiket: str,
                        ibareler: List[str]) -> SartSonuc:
    """Önceki tedavi ibaresi — yokluğu kanıtlanamaz → VAR (ibare) / KE+şartlı."""
    metin = _rapor_metni(ilac_sonuc)
    if any(ib in metin for ib in ibareler):
        return SartSonuc(ad=etiket, durum=SartDurumu.VAR,
                         neden='Önceki tedavi/yetersizlik ibaresi raporda bulundu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Önceki tedavi ibaresi metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def _skor_atom(ilac_sonuc: Dict, grup: str, etiket: str, ibareler: List[str],
               op: str, esik: float, idame_ibareler: List[str]) -> SartSonuc:
    """Hastalık aktivite skoru (DAS28>5,1 / BASDAİ>5 ...).

    Ölçülmüş değer (operatörsüz) bulunup eşiği geçerse VAR (başlangıç).
    Değer eşiğin altındaysa: idame/devam/düşüş ibaresi varsa VAR (idame),
    yoksa YOK. Sessiz/operatörlü (SUT echo) → KE+şartlı.
    """
    metin = _rapor_metni(ilac_sonuc)
    val, oplu = _lab_deger(metin, ibareler)
    idame = any(ib in metin for ib in idame_ibareler)
    if val is not None and not oplu:
        gecer = {'>': val > esik, '>=': val >= esik, '<': val < esik}[op]
        if gecer:
            return SartSonuc(ad=f'{etiket} = {val:g}', durum=SartDurumu.VAR,
                             neden=f'Başlangıç kriteri sağlandı ({etiket} {op} {esik:g})',
                             kaynak='rapor_metni', grup=grup)
        if idame:
            return SartSonuc(ad=f'{etiket} = {val:g} (idame)', durum=SartDurumu.VAR,
                             neden='Eşik altı ama idame/yanıt ibaresi var (devam kriteri)',
                             kaynak='rapor_metni', grup=grup)
        return SartSonuc(ad=f'{etiket} = {val:g}', durum=SartDurumu.YOK,
                         neden=f'{etiket} {op} {esik:g} başlangıç kriteri sağlanmıyor '
                               f've idame ibaresi yok',
                         kaynak='rapor_metni', grup=grup)
    if idame:
        return SartSonuc(ad=f'{etiket} (idame)', durum=SartDurumu.VAR,
                         neden='İdame/yanıt ibaresi var — devam kriteri (skor manuel)',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'{etiket} ölçülmüş değeri metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def _akut_faz_veya_atom(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """AS/PAS: ESH>28 VEYA CRP>ÜSN VEYA MR/sintigrafi aktif sakroilit (≥1)."""
    metin = _rapor_metni(ilac_sonuc)
    esh, esh_op = _lab_deger(metin, ['sedimantasyon', 'sedimentasyon', 'esh',
                                     'eritrosit sedim'])
    crp_var = 'crp' in metin
    goruntu = ('sakroilit' in metin or 'spondilit' in metin) and \
              ('mr' in metin or 'sintigrafi' in metin or 'manyetik' in metin)
    if (esh is not None and not esh_op and esh > 28) or crp_var or goruntu:
        nedenler = []
        if esh is not None and esh > 28:
            nedenler.append(f'ESH {esh:g}>28')
        if crp_var:
            nedenler.append('CRP ibaresi')
        if goruntu:
            nedenler.append('MR/sintigrafi aktif sakroilit/spondilit')
        return SartSonuc(ad='ESH>28 ∨ CRP>ÜSN ∨ MR/sintigrafi (≥1)',
                         durum=SartDurumu.VAR, neden='; '.join(nedenler),
                         kaynak='rapor_metni', grup=grup, veya_grubu=True)
    return SartSonuc(ad='ESH>28 ∨ CRP>ÜSN ∨ MR/sintigrafi (≥1)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Akut faz / görüntüleme bulgusu metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, veya_grubu=True, sartli_atom=True)


def _infliksimab_oncel_atom(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """RA/AS/PAS/PSA infliksimab özel: diğer anti-TNF'den ≥1 kullanıp cevapsız.

    İstisna: dirençli GİS tutulumu VEYA BMI≥35 → bu şart aranmaz. Yalnız
    infliksimab kalemi için eklenir.
    """
    if 'infliksimab' not in _hangi_ilac(ilac_sonuc):
        return None
    metin = _rapor_metni(ilac_sonuc)
    bmi = _bmi_oku(ilac_sonuc)
    gis = ('gastrointestinal' in metin or 'gis tutulum' in metin) and \
          ('direncli' in metin or 'dirençli' in metin)
    if (bmi is not None and bmi >= 35) or gis:
        neden = (f'BMI {bmi:g}≥35' if (bmi is not None and bmi >= 35)
                 else 'dirençli GİS tutulumu') + ' → önceki anti-TNF şartı aranmaz'
        return SartSonuc(ad='İnfliksimab: önceki anti-TNF şartı (istisna)',
                         durum=SartDurumu.VAR, neden=neden,
                         kaynak='rapor_metni', grup=grup)
    if 'anti-tnf' in metin or 'anti tnf' in metin or 'tnf' in metin:
        return SartSonuc(ad='İnfliksimab: önceki anti-TNF kullanımı + cevapsız',
                         durum=SartDurumu.VAR,
                         neden='Raporda önceki anti-TNF/cevapsızlık ibaresi var',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='İnfliksimab: ≥1 diğer anti-TNF kullanıp cevapsız',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İnfliksimab için önceki anti-TNF denemesi (ya da GİS/BMI≥35 '
                           'istisnası) raporda doğrulanmalı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def _form_flakon_atom(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """Crohn'da adalimumab flakon formu → bedeli karşılanmaz."""
    if 'adalimumab' not in _hangi_ilac(ilac_sonuc):
        return None
    form = norm_tr_lower(str(ilac_sonuc.get('form') or ilac_sonuc.get('ilac_form') or
                             _arama_metni(ilac_sonuc)))
    if 'flakon' in form:
        return SartSonuc(ad='Adalimumab flakon (Crohn)', durum=SartDurumu.YOK,
                         neden='Crohn hastalığında adalimumab FLAKON formu '
                               'karşılanmaz', kaynak='form', grup=grup)
    return SartSonuc(ad='Adalimumab form (flakon değil)', durum=SartDurumu.VAR,
                     neden='Flakon formu işareti yok', kaynak='form', grup=grup,
                     sartli_atom=True)


def _genel_bilgi_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_genel_ara_bilgi(ilac_sonuc, grup='(Genel) Tedaviye ara (bilgi)'),
        atom_genel_iki_biyolojik_bilgi(
            ilac_sonuc, grup='(Genel) İki biyolojik (bilgi)'),
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK KONTROL FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════

def ra_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(1a) Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(1a) ≥3 DMARD (biri MTX) 3\'er ay',
        '≥3 DMARD (biri methotrexat) en az 3\'er ay',
        ['methotrexat', 'metotreksat', 'dmard', 'hastalik modifiye',
         'leflunomid', 'sulfasalazin']))
    s.append(_skor_atom(ilac_sonuc, '(1a) DAS28 > 5,1', 'DAS28',
                        ['das 28', 'das28', 'das-28'], '>', 5.1,
                        ['idame', 'devam', 'dusme', 'puan dusus', 'yanit']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(1a) Sağlık kurulu raporu'))
    s.append(atom_recete_brans(ilac_sonuc, '(6) Reçete eden yetkili branş',
                               ROMATOLOJIK_RECETE_BRANS,
                               'Romatoloji/immün/FTR/iç hast./çocuk'))
    inf = _infliksimab_oncel_atom(ilac_sonuc, '(1a-1) İnfliksimab özel şart')
    if inf:
        s.append(inf)
    return s


def jra_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(1b) NSAİ + ≥1 DMARD 3 ay',
        'NSAİ + ≥1 DMARD en az 3 ay',
        ['nsai', 'nonsteroid', 'dmard', 'hastalik modifiye', 'methotrexat',
         'metotreksat']))
    s.append(_skor_atom(ilac_sonuc, '(1b) ACR pediatrik 30 yanıt yok', 'ACR pediatrik',
                        ['acr pediatrik', 'acr-pediatrik', 'acr 30'], '>', 0,
                        ['idame', 'devam', 'yanit alindi', 'acr pediatrik 50',
                         'acr 50']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(1b) Sağlık kurulu raporu'))
    s.append(atom_recete_brans(ilac_sonuc, '(6) Reçete eden yetkili branş',
                               ROMATOLOJIK_RECETE_BRANS,
                               'Romatoloji/immün/FTR/iç hast./çocuk'))
    return s


def as_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(2) ≥3 NSAİ (biri max indometazin) max doz',
        '≥3 NSAİ (biri maks. indometazin) maksimum dozda',
        ['indometazin', 'nsai', 'nonsteroid', 'antiinflamatuar']))
    s.append(_skor_atom(ilac_sonuc, '(2) BASDAİ > 5', 'BASDAİ',
                        ['basdai', 'basda'], '>', 5,
                        ['idame', 'devam', 'birim', 'duzelme', 'yanit']))
    s.append(_akut_faz_veya_atom(ilac_sonuc, '(2) ESH>28 ∨ CRP ∨ MR/sintigrafi (≥1)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(2) Sağlık kurulu raporu'))
    s.append(atom_recete_brans(ilac_sonuc, '(6) Reçete eden yetkili branş',
                               ROMATOLOJIK_RECETE_BRANS,
                               'Romatoloji/immün/FTR/iç hast./çocuk'))
    inf = _infliksimab_oncel_atom(ilac_sonuc, '(2a) İnfliksimab özel şart')
    if inf:
        s.append(inf)
    return s


def pas_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(3) Max NSAİ + (sulfasalazin ∨ MTX)',
        'Maks. doz NSAİ + sulfasalazin veya methotrexat',
        ['sulfasalazin', 'methotrexat', 'metotreksat', 'nsai', 'nonsteroid']))
    s.append(_skor_atom(ilac_sonuc, '(3) BASDAİ > 5', 'BASDAİ',
                        ['basdai', 'basda'], '>', 5,
                        ['idame', 'devam', 'birim', 'duzelme', 'yanit']))
    s.append(_akut_faz_veya_atom(ilac_sonuc, '(3) ESH>28 ∨ CRP>ÜSN (≥1)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(3) Sağlık kurulu raporu'))
    s.append(atom_recete_brans(ilac_sonuc, '(6) Reçete eden yetkili branş',
                               ROMATOLOJIK_RECETE_BRANS,
                               'Romatoloji/immün/FTR/iç hast./çocuk'))
    inf = _infliksimab_oncel_atom(ilac_sonuc, '(3a) İnfliksimab özel şart')
    if inf:
        s.append(inf)
    return s


def psa_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(5) ≥3 DMARD uygun doz 3\'er ay',
        '≥3 DMARD uygun dozunda en az 3\'er ay',
        ['dmard', 'hastalik modifiye', 'methotrexat', 'metotreksat',
         'leflunomid', 'sulfasalazin']))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(5) Aktif hastalık (≥3 hassas + ≥3 şiş eklem)',
        'Aktif (≥3 hassas + ≥3 şiş eklem, 1 ay arayla 2 muayene)',
        ['hassas eklem', 'sis eklem', 'şiş eklem', 'psarc']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(5) Sağlık kurulu raporu'))
    s.append(atom_recete_brans(ilac_sonuc, '(6) Reçete eden yetkili branş',
                               ROMATOLOJIK_RECETE_BRANS,
                               'Romatoloji/immün/FTR/iç hast./çocuk'))
    inf = _infliksimab_oncel_atom(ilac_sonuc, '(5a) İnfliksimab özel şart')
    if inf:
        s.append(inf)
    return s


def pso_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(9) Diğer DMARD\'a dirençli',
        'Diğer hastalık modifiye edici ilaçlara dirençli',
        ['direncli', 'dirençli', 'dmard', 'hastalik modifiye', 'sistemik tedavi']))
    s.append(_skor_atom(ilac_sonuc, '(9) PASI / doz-süre raporda', 'PASI',
                        ['pasi'], '>', 0, ['doz', 'sure', 'idame', 'devam']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, '(9) 3. basamak resmi kurum'))
    s.append(atom_heyet_brans(ilac_sonuc, '(9) Heyette dermatoloji uzmanı',
                              DERMATOLOJI, 'Heyette dermatoloji uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, '(9) Reçete eden dermatoloji uzmanı',
                               DERMATOLOJI, 'Dermatoloji uzmanı'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(9) Sağlık kurulu raporu (6 ay)'))
    return s


def crohn_e_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(10a) Yetişkin (yaş ≥18)', '>=', 18,
                         'Yetişkin (yaş ≥18)'))
    s.append(atom_ilac_kisiti(ilac_sonuc, '(10a) İzinli etken',
                              {'adalimumab', 'sertolizumab', 'infliksimab'},
                              'adalimumab / sertolizumab / infliksimab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(10a) Kortikosteroid &/veya immünsupresif 12 hf yetersiz',
        'Sistemik kortikosteroid &/veya immünsupresif 12 hafta yetersiz/tolere edemez',
        ['kortikosteroid', 'immunsupres', 'immünsupres', 'azatiyopurin', 'azathioprin']))
    s.append(_skor_atom(ilac_sonuc, '(10a) CDAI (idame: ↓≥70)', 'CDAI',
                        ['cdai', 'crohn hastalik aktivite'], '>', 0,
                        ['idame', 'devam', '70 puan', 'dusus', 'düşüş']))
    s.append(atom_heyet_brans(ilac_sonuc, '(10a) Heyette gastro ∨ genel cerrahi',
                              GASTRO + GENEL_CERRAHI, 'Heyette gastroenteroloji ∨ genel cerrahi'))
    s.append(atom_recete_brans(ilac_sonuc, '(10a) Reçete eden gastro/iç hast./genel cer.',
                               GASTRO + IC_HAST + GENEL_CERRAHI,
                               'Gastro / iç hastalıkları / genel cerrahi'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(10a) Sağlık kurulu raporu (4 ay)'))
    flk = _form_flakon_atom(ilac_sonuc, '(10a) Adalimumab flakon yasağı')
    if flk:
        s.append(flk)
    return s


def crohn_c_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(10b) Çocuk (yaş <18)', '<', 18,
                         'Çocuk (yaş <18)'))
    s.append(atom_ilac_kisiti(ilac_sonuc, '(10b) İzinli etken',
                              {'adalimumab', 'infliksimab'},
                              'adalimumab / infliksimab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(10b) Kortikosteroid &/veya immünsupresif 12 hf yetersiz',
        'Sistemik kortikosteroid &/veya immünsupresif 12 hafta yetersiz/tolere edemez',
        ['kortikosteroid', 'immunsupres', 'immünsupres', 'azatiyopurin']))
    s.append(_skor_atom(ilac_sonuc, '(10b) PCDAI (idame: ↓≥15)', 'PCDAI',
                        ['pcdai', 'pediatric crohn'], '>', 0,
                        ['idame', 'devam', '15 puan', 'dusus', 'düşüş']))
    s.append(atom_heyet_brans(ilac_sonuc, '(10b) Heyette çocuk gastro ∨ çocuk cerrahi',
                              COCUK_GASTRO + COCUK_CERRAHI,
                              'Heyette çocuk gastro ∨ çocuk cerrahi'))
    s.append(atom_recete_brans(ilac_sonuc, '(10b) Reçete eden çocuk gastro/çocuk hast./çocuk cer.',
                               COCUK_GASTRO + COCUK_HAST + COCUK_CERRAHI,
                               'Çocuk gastro / çocuk hast. / çocuk cerrahi'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(10b) Sağlık kurulu raporu (4 ay)'))
    return s


def uk_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_ilac_kisiti(ilac_sonuc, '(11) İzinli etken',
                              {'infliksimab', 'adalimumab'},
                              'infliksimab / adalimumab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(11) Kortikosteroid + 6-MP/AZA ≥8 hf yetersiz',
        'Kortikosteroid + 6-MP veya AZA en az 8 hafta yetersiz/tolere/kontrendike',
        ['kortikosteroid', '6-mp', '6 mp', 'azatiyopurin', 'azathioprin', 'aza ']))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(11) Şiddetli aktif ÜK',
        'Şiddetli aktif ülseratif kolit bulguları devam',
        ['siddetli aktif', 'şiddetli aktif', 'aktif ulseratif']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, '(11) 3. basamak kurum'))
    s.append(atom_heyet_brans(ilac_sonuc, '(11) Heyette gastro ∨ genel cerrahi',
                              GASTRO + GENEL_CERRAHI, 'Heyette gastroenteroloji ∨ genel cerrahi'))
    s.append(atom_recete_brans(ilac_sonuc, '(11) Reçete eden gastro/genel cer./iç hast.',
                               GASTRO + GENEL_CERRAHI + IC_HAST,
                               'Gastro / genel cerrahi / iç hastalıkları'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(11) Sağlık kurulu raporu (4 ay)'))
    return s


def uveit_e_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(12a) Yetişkin (yaş ≥18)', '>=', 18,
                         'Yetişkin (yaş ≥18)'))
    s.append(atom_ilac_kisiti(ilac_sonuc, '(12a) İzinli etken', {'adalimumab'},
                              'adalimumab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(12a) Non-enf. orta/arka/panüveit + kortikosteroide yetersiz',
        'Non-enfeksiyöz orta/arka/panüveit; kortikosteroide yetersiz/uygun değil',
        ['non-enfeksiyoz', 'noninfeksiyoz', 'kortikosteroid', 'panuveit',
         'arka uveit', 'orta uveit']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, '(12a) 3. basamak kurum'))
    s.append(atom_heyet_brans(ilac_sonuc, '(12a) Heyette göz hastalıkları uzmanı (3)',
                              GOZ, 'Heyette göz hastalıkları uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, '(12a) Reçete eden göz hastalıkları uzmanı',
                               GOZ, 'Göz hastalıkları uzmanı'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(12a) Sağlık kurulu raporu (3 ay)'))
    return s


def uveit_c_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(12b) Çocuk (yaş ≥2)', '>=', 2,
                         'Çocuk (yaş ≥2)'))
    s.append(atom_ilac_kisiti(ilac_sonuc, '(12b) İzinli etken', {'adalimumab'},
                              'adalimumab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(12b) Non-enf. kronik anterior üveit + konvansiyonele yetersiz',
        'Non-enfeksiyöz kronik anterior üveit; konvansiyonele yetersiz/uygun değil',
        ['non-enfeksiyoz', 'noninfeksiyoz', 'kronik anterior', 'konvansiyonel']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, '(12b) 3. basamak kurum'))
    s.append(atom_heyet_brans(ilac_sonuc, '(12b) Heyette göz hastalıkları uzmanı (3)',
                              GOZ, 'Heyette göz hastalıkları uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, '(12b) Reçete eden göz hastalıkları uzmanı',
                               GOZ, 'Göz hastalıkları uzmanı'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(12b) Sağlık kurulu raporu (3 ay)'))
    return s


def hs_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, '(13) Yetişkin (yaş ≥18)', '>=', 18,
                         'Yetişkin (yaş ≥18)'))
    s.append(atom_ilac_kisiti(ilac_sonuc, '(13) İzinli etken', {'adalimumab'},
                              'adalimumab'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, '(13) 6 hf sistemik antibiyotik yetersiz',
        'Orta/şiddetli HS; 6 hafta sistemik antibiyotiğe yetersiz yanıt',
        ['antibiyotik', 'orta', 'siddetli', 'şiddetli']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, '(13) 3. basamak kurum'))
    s.append(atom_heyet_brans(ilac_sonuc, '(13) Heyette dermatoloji uzmanı (3)',
                              DERMATOLOJI, 'Heyette dermatoloji uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, '(13) Reçete eden dermatoloji uzmanı',
                               DERMATOLOJI, 'Dermatoloji uzmanı'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, '(13) Sağlık kurulu raporu (3 ay)'))
    return s


def belirsiz_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [SartSonuc(ad='Endikasyon tespiti', durum=SartDurumu.KONTROL_EDILEMEDI,
                      neden='Anti-TNF kapsamında ama endikasyon (ICD/teşhis) '
                            'belirlenemedi — manuel yolak seçimi',
                      kaynak='teshis', grup='Endikasyon (belirsiz)', sartli_atom=True)]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (kanser/G-CSF modülü ile aynı disiplin)
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


YOLAK_METADATA: Dict[str, str] = {
    'RA': 'Erişkin romatoid artrit (1a)',
    'JRA': 'Juvenil RA (1b)',
    'AS': 'Aksiyel ankilozan spondilit (2)',
    'PAS': 'Periferik AS (3)',
    'PSA': 'Psöriyatik artrit (5)',
    'PSO': 'Psoriazis vulgaris/plak (9)',
    'CROHN_E': 'Crohn — yetişkin (10a)',
    'CROHN_C': 'Crohn — çocuk (10b)',
    'UK': 'Ülseratif kolit (11)',
    'UVEIT_E': 'Üveit — yetişkin (12a)',
    'UVEIT_C': 'Üveit — çocuk (12b)',
    'HS': 'Hidradenitis suppurativa (13)',
    'BELIRSIZ': 'Endikasyon belirsiz',
}

YOLAK_FN_MAP = {
    'RA': ra_kontrol, 'JRA': jra_kontrol, 'AS': as_kontrol, 'PAS': pas_kontrol,
    'PSA': psa_kontrol, 'PSO': pso_kontrol, 'CROHN_E': crohn_e_kontrol,
    'CROHN_C': crohn_c_kontrol, 'UK': uk_kontrol, 'UVEIT_E': uveit_e_kontrol,
    'UVEIT_C': uveit_c_kontrol, 'HS': hs_kontrol, 'BELIRSIZ': belirsiz_kontrol,
}


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = [f"SUT 4.2.1.C-1 / {YOLAK_METADATA.get(yolak, yolak)}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — yapısal şartlar VAR; {len(ke)} klinik şart "
                        f"manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def anti_tnf_kontrol_4_2_1_c1(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.1.C-1 Anti-TNF ana kontrol fonksiyonu."""
    yolak = anti_tnf_yolak_belirle(ilac_sonuc)
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.1.C-1 kapsamı dışı — anti-TNF ilaç tespit edilemedi',
            sut_kurali='SUT 4.2.1.C-1')
    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc)
    # Genel ilke bilgi atomları (matematiği bozmaz)
    sartlar.extend(_genel_bilgi_atomlari(ilac_sonuc))
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f"SUT 4.2.1.C-1 / {YOLAK_METADATA.get(yolak, yolak)}",
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'yolak_ad': YOLAK_METADATA.get(yolak, yolak)})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (CLAUDE.md §7.7 — ≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # 1) RA tam UYGUN: DAS28 ölçülü>5.1 + DMARD ibaresi + kurul + romatoloji
        ("RA tam UYGUN", {
            'ilac_adi': 'HUMIRA', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['M06.9'], 'hasta_yasi': 45,
            'doktor_uzmanligi': 'Romatoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}, {'brans': 'FTR'}],
            'rapor_metni': 'methotrexat ve leflunomid kullanildi DAS28: 5.8',
        }, KontrolSonucu.UYGUN),
        # 2) RA ŞARTLI: klinik veriler sessiz ama yapısal tam
        ("RA ŞARTLI (klinik sessiz)", {
            'ilac_adi': 'ENBREL', 'etkin_madde': 'ETANERSEPT', 'atc_kodu': 'L04AB01',
            'recete_teshisleri': ['M05.9'], 'hasta_yasi': 50,
            'doktor_uzmanligi': 'Romatoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}, {'brans': 'İç Hastalıkları'}],
            'rapor_metni': 'romatoid artrit tedavisi',
        }, KontrolSonucu.SARTLI_UYGUN),
        # 3) RA UYGUN DEĞİL: pratisyen reçete
        ("RA UYGUN DEĞİL (pratisyen)", {
            'ilac_adi': 'HUMIRA', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['M06.9'], 'hasta_yasi': 45,
            'doktor_uzmanligi': 'Aile Hekimliği', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}, {'brans': 'FTR'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 4) RA UYGUN DEĞİL: uzman hekim raporu (kurul değil)
        ("RA UYGUN DEĞİL (uzman hekim raporu)", {
            'ilac_adi': 'ENBREL', 'etkin_madde': 'ETANERSEPT', 'atc_kodu': 'L04AB01',
            'recete_teshisleri': ['M06.9'], 'hasta_yasi': 45,
            'doktor_uzmanligi': 'Romatoloji', 'rapor_turu': 'Uzman Hekim Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 5) AS UYGUN: BASDAİ ölçülü>5 + ESH>28 + kurul + romatoloji
        ("AS tam UYGUN", {
            'ilac_adi': 'SIMPONI', 'etkin_madde': 'GOLIMUMAB', 'atc_kodu': 'L04AB06',
            'recete_teshisleri': ['M45'], 'doktor_uzmanligi': 'Romatoloji',
            'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}, {'brans': 'FTR'}],
            'rapor_metni': 'indometazin kullanildi basdai: 6.2 sedimantasyon: 35',
        }, KontrolSonucu.UYGUN),
        # 6) PSO UYGUN DEĞİL: dermatoloji yok (romatoloji reçete)
        ("PSO UYGUN DEĞİL (dermatoloji değil)", {
            'ilac_adi': 'HUMIRA', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['L40.0'], 'doktor_uzmanligi': 'Romatoloji',
            'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Romatoloji'}, {'brans': 'İç Hastalıkları'}],
            'rapor_metni': 'plak psoriazis dmard direncli', 'tesis_basamak': '3. basamak',
        }, KontrolSonucu.UYGUN_DEGIL),
        # 7) Crohn yetişkin ŞARTLI: kurul + gastro heyet + gastro reçete; klinik sessiz
        ("Crohn yetişkin ŞARTLI", {
            'ilac_adi': 'REMICADE', 'etkin_madde': 'INFLIKSIMAB', 'atc_kodu': 'L04AB02',
            'recete_teshisleri': ['K50.0'], 'hasta_yasi': 35,
            'doktor_uzmanligi': 'Gastroenteroloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Gastroenteroloji'}, {'brans': 'Genel Cerrahi'}],
        }, KontrolSonucu.SARTLI_UYGUN),
        # 8) Crohn UYGUN DEĞİL: adalimumab flakon
        ("Crohn UYGUN DEĞİL (adalimumab flakon)", {
            'ilac_adi': 'HUMIRA FLAKON', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['K50.9'], 'hasta_yasi': 40, 'form': 'Flakon',
            'doktor_uzmanligi': 'Gastroenteroloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Gastroenteroloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 9) ÜK UYGUN DEĞİL: izinsiz etken (etanersept)
        ("ÜK UYGUN DEĞİL (etanersept izinsiz)", {
            'ilac_adi': 'ENBREL', 'etkin_madde': 'ETANERSEPT', 'atc_kodu': 'L04AB01',
            'recete_teshisleri': ['K51.0'], 'doktor_uzmanligi': 'Gastroenteroloji',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'tesis_basamak': '3',
            'heyet_doktorlari': [{'brans': 'Gastroenteroloji'}, {'brans': 'Genel Cerrahi'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 10) Üveit yetişkin UYGUN DEĞİL: göz değil + izinsiz etken
        ("Üveit UYGUN DEĞİL (etanersept + göz değil)", {
            'ilac_adi': 'ENBREL', 'etkin_madde': 'ETANERSEPT', 'atc_kodu': 'L04AB01',
            'recete_teshisleri': ['H20.0'], 'hasta_yasi': 40,
            'doktor_uzmanligi': 'Romatoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rapor_metni': 'panuveit', 'tesis_basamak': '3',
            'heyet_doktorlari': [{'brans': 'Göz Hastalıkları'}, {'brans': 'Göz Hastalıkları'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 11) HS ŞARTLI: adalimumab + dermatoloji heyet/reçete + 3.basamak
        ("HS ŞARTLI", {
            'ilac_adi': 'HUMIRA', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['L73.2'], 'hasta_yasi': 30,
            'doktor_uzmanligi': 'Dermatoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'tesis_basamak': '3. basamak',
            'heyet_doktorlari': [{'brans': 'Dermatoloji'}, {'brans': 'Dermatoloji'}],
        }, KontrolSonucu.SARTLI_UYGUN),
        # 12) Kapsam dışı
        ("Kapsam dışı (parasetamol)", {
            'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        # 13) JRA ŞARTLI: çocuk + M08 + kurul + çocuk hast.
        ("JRA ŞARTLI", {
            'ilac_adi': 'HUMIRA', 'etkin_madde': 'ADALIMUMAB', 'atc_kodu': 'L04AB04',
            'recete_teshisleri': ['M08.0'], 'hasta_yasi': 12,
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
            'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [{'brans': 'Çocuk Romatoloji'}, {'brans': 'Çocuk Sağlığı'}],
        }, KontrolSonucu.SARTLI_UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.1.C-1 Anti-TNF — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = anti_tnf_kontrol_4_2_1_c1(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        isaret = "✓" if ok else "✗"
        print(f"{isaret} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
