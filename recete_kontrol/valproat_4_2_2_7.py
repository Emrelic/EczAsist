# -*- coding: utf-8 -*-
"""SUT 4.2.2(7) — Sodyum valproat / valproik asit (kombinasyonları dahil).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:4740-4741`` (mevzuat.gov.tr,
MevzuatNo=17229):

    "(7) Sodyum valproat (kombinasyonları dahil), 'bipolar bozukluk'
    endikasyonunda psikiyatri ve nöroloji uzmanları tarafından veya bu
    hekimlerden birinin düzenlediği uzman hekim raporuna dayanılarak tüm
    hekimlerce reçete edilebilir."

ÖNEMLİ: SUT 4.2.25 (antiepileptik) valproatı resmî listesinde SAYMAZ —
epilepsi/migren endikasyonunda valproat SUT kısıtı taşımaz (tüm hekimler,
raporsuz). Tek kısıt "bipolar bozukluk" endikasyonundadır.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (üst-VEYA çifti ‖E‖ ‖B‖)
═══════════════════════════════════════════════════════════════════════════

    UYGUN ⇔ E1 ∨ (B1a ∨ B1b ∨ B2)

    ‖E‖  E1 : endikasyon bipolar DEĞİL — epilepsi (G40/G41/nöbet/diğer AEP
              raporu) veya migren (G43) kanıtı VAR ∧ bipolar sinyali YOK.
              Bipolar sinyali (F31/lafız) → YOK; sessiz → KE-şartlı.
    ‖B‖  B1a: reçeteci psikiyatri uzmanı
         B1b: reçeteci nöroloji uzmanı
         B2 : psikiyatri/nöroloji uzman hekim raporu
         → bipolar endikasyonunda geçerli yetki yolu (SUT 4.2.2(7))

(bilgi) atomları (matematiğe girmez — kullanıcı onayı 2026-07-06):
  - Uzun etkili form (CHRONO/XR/uzun etkili) KÜB şartı ≥12 yaş + >50 kg:
    yaş DB'den okunur (rapor metninden yaş okuma YASAK), kilo DB'de yok;
    DB yaş <12 → KE uyarısı.
  - Raporda antipsikotik kokteyl (ketiapin/risperidon/haloperidol/...) →
    bipolar/psikoz bağlamı İPUCU (kanıt DEĞİL — şizofrenide valproat 4.2.2(7)
    kapsamına girmez, kısıt lafzen 'bipolar bozukluk endikasyonu').

Ana entrypoint: ``valproat_kontrol_4_2_2_7(ilac_sonuc)`` → ``KontrolRaporu``.
İki yüzey: PSİKİYATRİ/ANTİEPİLEPTİK butonu (antiepileptik_4_2_25 delege +
kontrol_psikiyatri valproat dalı delege) + anlık genel dispatcher (psikiyatri/
antiepileptik kategorileri — _EK_MODUL_DISPATCH'e EKLENMEZ, çakışma istisnası).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower
from recete_kontrol.noropatik_4_2_35 import (
    _rapor_metni, _rapor_var, _teshis_upper, _arama_metni, _iceriyor,
)
from recete_kontrol.snri_4_2_2 import (
    _atom_receteci, _atom_rapor_brans, _grup_degerlendir, _veya,
    PSIKIYATRI, NOROLOJI,
)

# ═══════════════════════════════════════════════════════════════════════
# KAPSAM
# ═══════════════════════════════════════════════════════════════════════

VALPROAT_ETKEN = {'VALPROIK', 'VALPROİK', 'VALPROAT', 'VALPROIC', 'VALPROATE',
                  'VALPROMID'}
VALPROAT_TICARI = {'DEPAKIN', 'DEPAKINE', 'CONVULEX', 'DEPALEX', 'DEPAMID'}
# ATC: N03AG01 valproik asit / N03AG02 valpromid
VALPROAT_ATC = ('N03AG01', 'N03AG02')

GRUP_E = '‖E‖ (4.2.2-7) Endikasyon bipolar DEĞİL (epilepsi/migren)'
GRUP_B = '‖B‖ (4.2.2-7) Bipolar yolu: psikiyatri/nöroloji reçeteci veya raporu (≥1)'
GRUP_BILGI_KUB = '(bilgi) Uzun etkili form KÜB şartı (≥12 yaş, >50 kg)'
GRUP_BILGI_KOKTEYL = '(bilgi) Raporda antipsikotik kokteyl (bipolar/psikoz ipucu)'

# Raporda geçen diğer antiepileptikler → epilepsi bağlamı kanıtı
_AEP_IPUC = ('topiramat', 'levetirasetam', 'levatirasetam', 'karbamazepin',
             'okskarbazepin', 'lamotrijin', 'lamotrigin', 'fenitoin',
             'fenobarbital', 'lakozamid', 'lakosamid', 'zonisamid',
             'klobazam', 'klonazepam', 'etosuksimid', 'rufinamid',
             'perampanel', 'brivarasetam', 'vigabatrin', 'stiripentol',
             'keppra', 'tegretol', 'trileptal', 'topamax', 'vimpat',
             'frisium', 'rivotril', 'zonegran', 'fycompa')

# Raporda geçen antipsikotik/duygudurum ilaçları → bipolar/psikoz bağlamı İPUCU
_ANTIPSIKOTIK_IPUC = ('ketiapin', 'ketiyapin', 'kuetiapin', 'risperidon',
                      'haloperidol', 'olanzapin', 'aripiprazol', 'klozapin',
                      'paliperidon', 'amisulpirid', 'amisülpirid', 'lityum',
                      'ziprasidon', 'kariprazin', 'lurasidon')


def valproat_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Satır SUT 4.2.2(7) valproat (kombinasyonları dahil) kapsamında mı?"""
    atc = norm_tr_upper(str(ilac_sonuc.get('atc_kodu') or '')).strip()
    if atc and any(atc.startswith(a) for a in VALPROAT_ATC):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, VALPROAT_ETKEN) or _iceriyor(m, VALPROAT_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ENDİKASYON SİNYALLERİ
# ═══════════════════════════════════════════════════════════════════════

def _sinyaller(ilac_sonuc: Dict) -> Dict[str, bool]:
    metin = _rapor_metni(ilac_sonuc) + ' ' + norm_tr_lower(_teshis_upper(ilac_sonuc))
    icd = _teshis_upper(ilac_sonuc)
    s: Dict[str, bool] = {}
    s['bipolar'] = (
        any(k in metin for k in ('bipolar', 'iki uclu', 'manik depres',
                                 'manik atak', 'mani nobet'))
        or bool(re.search(r'\bF31', icd)))
    s['epilepsi'] = (
        any(k in metin for k in ('epilepsi', 'nobet', 'konvulsiy',
                                 'status epilept', 'jeneralize', 'parsiyel',
                                 'absans', 'miyoklonik'))
        or bool(re.search(r'\bG4[01]', icd))
        or any(k in metin for k in _AEP_IPUC))
    s['migren'] = ('migren' in metin) or bool(re.search(r'\bG43', icd))
    s['kokteyl'] = any(k in metin for k in _ANTIPSIKOTIK_IPUC)
    return s


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def _atom_e1_endikasyon(sig: Dict[str, bool]) -> SartSonuc:
    """E1 — endikasyon bipolar DEĞİL (3-yönlü, örtük kabul yasak)."""
    if sig['bipolar']:
        return SartSonuc(
            ad='Endikasyon: bipolar bozukluk tespit edildi',
            durum=SartDurumu.YOK,
            neden='SUT 4.2.2(7): bipolar endikasyonunda psikiyatri/nöroloji '
                  'uzmanı veya raporu şartı aranır (‖B‖ yolu)',
            kaynak='ICD+rapor', grup=GRUP_E)
    if sig['epilepsi'] or sig['migren']:
        kaynak_ad = 'epilepsi/nöbet' if sig['epilepsi'] else 'migren'
        return SartSonuc(
            ad=f'Endikasyon: {kaynak_ad} (bipolar değil)',
            durum=SartDurumu.VAR,
            neden='Valproat SUT 4.2.25 listesinde yok; bipolar dışı '
                  'endikasyonda kısıt yok — tüm hekimler raporsuz yazabilir',
            kaynak='ICD+rapor', grup=GRUP_E)
    return SartSonuc(
        ad='Endikasyon (bipolar mı, epilepsi/migren mi?)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Endikasyon reçete/raporda net okunamadı — bipolar ise '
              'psikiyatri/nöroloji yetkisi gerekir, manuel',
        kaynak='ICD+rapor', grup=GRUP_E, sartli_atom=True)


def _yas_oku(ilac_sonuc: Dict) -> Optional[int]:
    """Hasta yaşı SADECE DB alanlarından (rapor metninden yaş okuma YASAK)."""
    for k in ('hasta_yasi', 'yas'):
        v = ilac_sonuc.get(k)
        if v in (None, ''):
            continue
        try:
            return int(float(str(v).strip()))
        except (ValueError, TypeError):
            continue
    return None


def _atom_bilgi_uzun_etkili(ilac_sonuc: Dict) -> Optional[SartSonuc]:
    """(bilgi) CHRONO/XR uzun etkili form — KÜB şartı ≥12 yaş + >50 kg."""
    ad = norm_tr_upper(str(ilac_sonuc.get('ilac_adi') or ''))
    if not any(k in ad for k in ('CHRONO', 'XR', 'UZUN ETK')):
        return None
    yas = _yas_oku(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    ibare = ('12 yas' in metin and ('50 kilo' in metin or '50 kg' in metin))
    if yas is not None and yas < 12:
        return SartSonuc(
            ad=f'Uzun etkili form + DB yaş {yas} (<12)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='KÜB: uzun etkili valproat formları ≥12 yaş + >50 kg — '
                  'yaş şartı sağlanmıyor görünüyor, manuel doğrulanmalı (bilgi)',
            kaynak='DB_yas+ilac_adi', grup=GRUP_BILGI_KUB, sartli_atom=True)
    if yas is not None:
        return SartSonuc(
            ad=f'Uzun etkili form + DB yaş {yas} (≥12)',
            durum=SartDurumu.VAR,
            neden='KÜB yaş şartı DB\'den sağlanıyor; kilo DB\'de yok'
                  + (' — raporda ≥12 yaş + >50 kg ibaresi de var' if ibare
                     else ' (kilo manuel)'),
            kaynak='DB_yas+ilac_adi', grup=GRUP_BILGI_KUB)
    if ibare:
        return SartSonuc(
            ad='Uzun etkili form — raporda ≥12 yaş + >50 kg ibaresi',
            durum=SartDurumu.VAR,
            neden='KÜB şartı rapor lafzında beyan edilmiş (DB yaşı okunamadı)',
            kaynak='rapor_metni', grup=GRUP_BILGI_KUB)
    return SartSonuc(
        ad='Uzun etkili form — KÜB şartı (≥12 yaş, >50 kg)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='DB yaşı ve rapor ibaresi okunamadı — manuel (bilgi)',
        kaynak='DB_yas+rapor_metni', grup=GRUP_BILGI_KUB, sartli_atom=True)


def _atom_bilgi_kokteyl(ilac_sonuc: Dict,
                        sig: Dict[str, bool]) -> Optional[SartSonuc]:
    """(bilgi) Raporda antipsikotik kokteyl — bipolar/psikoz bağlamı İPUCU."""
    if not sig['kokteyl'] or sig['bipolar']:
        return None  # bipolar zaten tespitli ise ipucuna gerek yok
    metin = _rapor_metni(ilac_sonuc)
    bulunan = sorted({k for k in _ANTIPSIKOTIK_IPUC if k in metin})
    return SartSonuc(
        ad='Raporda antipsikotik tanımlı: ' + ', '.join(bulunan[:4]),
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bipolar/psikoz bağlamı İPUCU (kanıt değil) — endikasyon '
              'bipolar ise psikiyatri/nöroloji yetkisi aranmalı, manuel (bilgi)',
        kaynak='rapor_metni', grup=GRUP_BILGI_KOKTEYL, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (üst-VEYA çifti ‖E‖ ‖B‖)
# ═══════════════════════════════════════════════════════════════════════

def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    e_atomlar = [s for s in sartlar if s.grup == GRUP_E]
    b_atomlar = [s for s in sartlar if s.grup == GRUP_B]
    if not e_atomlar and not b_atomlar:
        return KontrolSonucu.KONTROL_EDILEMEDI
    e = _grup_degerlendir(e_atomlar) if e_atomlar else ('yok', False)
    b = _grup_degerlendir(b_atomlar) if b_atomlar else ('yok', False)
    ust, sartli = _veya(e, b)
    if ust == 'var':
        return KontrolSonucu.UYGUN
    if ust == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    return (KontrolSonucu.SARTLI_UYGUN if sartli
            else KontrolSonucu.KONTROL_EDILEMEDI)


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI
          and '(bilgi)' not in (s.grup or '')]
    parcalar = ["SUT 4.2.2(7) / Valproat"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — bipolar dışı endikasyon veya psikiyatri/"
                        "nöroloji yetkisi sağlanıyor")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama "
                        "gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — bipolar endikasyonunda psikiyatri/"
                        "nöroloji uzmanı veya raporu yok ("
                        + '; '.join(s.ad for s in yok[:3]) + ")")
    else:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def valproat_kontrol_4_2_2_7(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.2(7) valproat ana kontrol fonksiyonu."""
    if not valproat_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.2(7) valproat kapsamında değil',
            sut_kurali='SUT 4.2.2(7)')

    sig = _sinyaller(ilac_sonuc)
    sartlar: List[SartSonuc] = []

    # ‖E‖ — endikasyon (bipolar değilse kısıt yok)
    sartlar.append(_atom_e1_endikasyon(sig))

    # ‖B‖ — bipolar yolu yetkisi (psikiyatri ∨ nöroloji; reçeteci ∨ rapor)
    sartlar.append(_atom_receteci(ilac_sonuc, PSIKIYATRI,
                                  'Reçeteci psikiyatri uzmanı', GRUP_B))
    sartlar.append(_atom_receteci(ilac_sonuc, NOROLOJI,
                                  'Reçeteci nöroloji uzmanı', GRUP_B))
    sartlar.append(_atom_rapor_brans(ilac_sonuc, PSIKIYATRI + NOROLOJI,
                                     'Psikiyatri/nöroloji uzman hekim raporu',
                                     GRUP_B))

    # (bilgi) atomları
    b1 = _atom_bilgi_uzun_etkili(ilac_sonuc)
    if b1:
        sartlar.append(b1)
    b2 = _atom_bilgi_kokteyl(ilac_sonuc, sig)
    if b2:
        sartlar.append(b2)

    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali='SUT 4.2.2(7) — Valproat: bipolar endikasyonunda '
                   'psikiyatri/nöroloji uzmanı veya raporu; diğer '
                   'endikasyonlarda kısıt yok (4.2.25 listesinde değil)',
        sartlar=sartlar,
        aranan_ibare='bipolar-değil ∨ (psikiyatri/nöroloji reçeteci veya raporu)',
        detaylar={'alt_grup': 'VALPROAT', 'yolak': 'VALPROAT_4_2_2_7',
                  'sinyaller': {k: v for k, v in sig.items() if v}})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Epilepsi teşhisi (G40) + aile hekimi raporsuz → UYGUN", {
            'etkin_madde': 'VALPROİK ASİT', 'ilac_adi': 'DEPAKIN 500MG',
            'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.UYGUN),
        ("Topiramat idame raporu (KADİR BIYIK tipi, CONVULEX şurup) → UYGUN", {
            'etkin_madde': 'VALPROİK ASİT',
            'ilac_adi': 'CONVULEX 50MG/ML 100ML PEDIATRIK ŞURUP',
            'rapor_kodu': '6',
            'rapor_aciklamalari': ['idame tedavi TOPIRAMAT Ağızdan katı '
                                   '1 Gün 1 400 Miligram'],
        }, KontrolSonucu.UYGUN),
        ("Migren profilaksisi (G43) → UYGUN", {
            'etkin_madde': 'VALPROAT', 'ilac_adi': 'DEPAKIN CHRONO',
            'brans': 'Aile Hekimliği', 'yas': '40',
            'recete_teshisleri': ['G43.9 MIGREN'],
        }, KontrolSonucu.UYGUN),
        ("Bipolar (F31) + reçeteci psikiyatri → UYGUN", {
            'etkin_madde': 'VALPROIK ASIT', 'brans': 'Psikiyatri',
            'recete_teshisleri': ['F31.1 BIPOLAR BOZUKLUK'],
        }, KontrolSonucu.UYGUN),
        ("Bipolar lafzı + aile hekimi + nöroloji raporu → UYGUN", {
            'etkin_madde': 'VALPROAT', 'brans': 'Aile Hekimliği',
            'rapor_kodu': '11', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_aciklamalari': ['bipolar affektif bozukluk idame'],
        }, KontrolSonucu.UYGUN),
        ("Bipolar lafzı + aile hekimi RAPORSUZ → UYGUN DEĞİL", {
            'etkin_madde': 'VALPROIK ASIT', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['F31 BIPOLAR'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Bipolar + aile hekimi + rapor var branş okunamadı → ŞARTLI UYGUN", {
            'etkin_madde': 'VALPROAT', 'brans': 'Aile Hekimliği',
            'rapor_kodu': '11.04',
            'rapor_aciklamalari': ['bipolar bozukluk tedavisi uygundur'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Sessiz rapor ('1 yıl geçerlidir', EBRU DOĞAN tipi) → ŞARTLI UYGUN", {
            'etkin_madde': 'VALPROİK ASİT',
            'ilac_adi': 'DEPAKIN CHRONO BT 500MG 30 TABLET',
            'rapor_kodu': '5', 'yas': '45',
            'rapor_aciklamalari': ['1 yıl süre ile geçerlidir.'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Antipsikotik kokteyl raporu (ELİF İREM tipi) → ŞARTLI + kokteyl bilgi", {
            'etkin_madde': 'VALPROİK ASİT',
            'ilac_adi': 'DEPAKIN CHRONO BT 500MG 30 TABLET',
            'rapor_kodu': '11', 'yas': '30',
            'rapor_aciklamalari': [
                'VALPROIK ASIT+SODYUM VALPROAT 1500 Miligram KETIAPIN '
                'FUMARAT 1200 Miligram HALOPERIDOL 15 Miligram RISPERIDON '
                '6 Miligram'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("DEPALEX XR + yaş 51 + '12 yaş/50 kg' raporu (MURAT tipi) → ŞARTLI", {
            'etkin_madde': 'VALPROİK ASİT',
            'ilac_adi': 'DEPALEX XR 500MG UZUN ETKILI 30 FİLM TABLET',
            'rapor_kodu': '9', 'yas': '51',
            'rapor_aciklamalari': ['HASTA 12 YAŞINDAN BÜYÜK (51 YAŞINDA) VE '
                                   '50 KİLODAN FAZLADIR (85 KG)'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Raporsuz sessiz şurup (MUSTAFA ÇERMİK tipi) → ŞARTLI UYGUN", {
            'etkin_madde': 'VALPROİK ASİT',
            'ilac_adi': 'DEPAKIN 57.64MG/ML 150ML ŞURUP',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol) → ATLANDI", {
            'etkin_madde': 'PARASETAMOL',
        }, KontrolSonucu.ATLANDI),
    ]


def akil_testi_calistir() -> bool:
    print("SUT 4.2.2(7) — Valproat — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = valproat_kontrol_4_2_2_7(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        if not ok:
            print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 64)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")
    return gecti == len(senaryolar)


if __name__ == '__main__':
    akil_testi_calistir()
