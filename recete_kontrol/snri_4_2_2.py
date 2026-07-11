# -*- coding: utf-8 -*-
"""SUT 4.2.2(1) ikinci hüküm — SNRI / SSRE / RIMA / NaSSA antidepresanlar.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:4717-4721`` (mevzuat.gov.tr,
MevzuatNo=17229, Değişik cümleler:RG-4/9/2019-30878 Mükerrer):

    "SNRI, SSRE, RIMA, NASSA grubu antidepresanların psikiyatri, nöroloji
    veya geriatri uzman hekimlerinden biri tarafından reçete edilmesi veya
    bu uzman hekimlerden biri tarafından düzenlenen uzman hekim raporuna
    dayanılarak tüm hekimlerce reçete edilmesi halinde, 6 aydan uzun süre
    kullanılması gereken durumlarda ise psikiyatri uzman hekimlerince
    reçete edilmesi veya psikiyatri uzman hekimlerince düzenlenen uzman
    hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde
    bedelleri Kurumca karşılanır."

Ek: fıkra (9) — "düzenlenecek uzman hekim raporunda ilacın kullanılacağı
süre belirtilir" → raporlularda (bilgi) atomu.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (üst-VEYA çifti ‖P‖ ‖N‖)
═══════════════════════════════════════════════════════════════════════════

    UYGUN ⇔ (P1 ∨ P2) ∨ [ (N1a ∨ N1b ∨ N2) ∧ T1 ]

    ‖P‖  P1: reçeteci psikiyatri uzmanı
         P2: psikiyatri uzman hekim raporu
         → psikiyatri yetkisi SÜREDEN BAĞIMSIZ yeter (6 ay+ dahil)
    ‖N‖  N1a: reçeteci nöroloji  N1b: reçeteci geriatri
         N2: nöroloji/geriatri uzman hekim raporu
         T1: kullanım süresi ≤ 6 ay (hasta ilaç geçmişi — yerel/EOS
             enrichment `hasta_snri_ilk_recete_tarihi`; yoksa KE-şartlı,
             başka eczaneden alınmış olabilir — örtük kabul YASAK)

DULOKSETİN ÖN-DISPATCH (üst dispatcher — sinyal önceliği):
    1. stres SUI / mikst SUI (+rapor +kadın) → EK-4/F M.45 üriner kontrolü
    2. diyabetik nöropati / nöropatik ağrı / fibromiyalji → SUT 4.2.35
       (noropatik_4_2_35 modülü, D_A3 / D_B1 yolakları)
    3. aksi her durum (depresyon / anksiyete / SESSİZ) → bu modül (4.2.2-1)

Diğer etkenler (venlafaksin, desvenlafaksin, milnasipran, mirtazapin,
tianeptin, moklobemid) doğrudan 4.2.2(1) şartlarından geçer.

Ana entrypoint: ``snri_kontrol_4_2_2(ilac_sonuc)`` → ``KontrolRaporu``.
İki yüzey: PSİKİYATRİ butonu (kontrol_psikiyatri delege) + ÜROLOJİ butonu
(kontrol_cesitli_madde_45_uriner duloksetin delege) + anlık genel dispatcher
(psikiyatri kategorisi — _EK_MODUL_DISPATCH'e EKLENMEZ, çakışma istisnası).
"""

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower
from recete_kontrol.noropatik_4_2_35 import (
    _endikasyonlar as _nor_endikasyonlar,
    _rapor_metni, _rapor_var, _rapor_brans_adaylar,
    _brans_l, _brans_listede, _iceriyor, _arama_metni,
)

# ═══════════════════════════════════════════════════════════════════════
# KAPSAM — SNRI / SSRE / RIMA / NaSSA (SUT 4.2.2(1) 2. cümle)
# ═══════════════════════════════════════════════════════════════════════
# NOT: Bupropion / vortioksetin / agomelatin / trazodon-uzatılmış-salımlı
# AYRI hükümde (4.2.2(1) son cümle — yalnız psikiyatri) → bu modüle GİRMEZ,
# kontrol_psikiyatri BVA dalında kalır. Trisiklik/tetrasiklik/SSRI da girmez.

SNRI_ETKEN = {'DULOKSETIN', 'DULOXETINE', 'DULOXETIN',
              'VENLAFAKSIN', 'VENLAFAXIN', 'VENLAFAXINE',
              'DESVENLAFAKSIN', 'DESVENLAFAXIN',
              'MILNASIPRAN', 'MILNACIPRAN'}
SSRE_ETKEN = {'TIANEPTIN', 'TIANEPTINE'}
RIMA_ETKEN = {'MOKLOBEMID', 'MOCLOBEMID', 'MOKLOBEMIDE'}
NASSA_ETKEN = {'MIRTAZAPIN', 'MIRTAZAPINE'}

KAPSAM_ETKEN = SNRI_ETKEN | SSRE_ETKEN | RIMA_ETKEN | NASSA_ETKEN

DULOKSETIN_ETKEN = {'DULOKSETIN', 'DULOXETINE', 'DULOXETIN'}
DULOKSETIN_TICARI = {'CYMBALTA', 'DUXET', 'DULOXIN', 'DULOX', 'DULOXX',
                     'DYLOXIA', 'DULESS', 'DULNEX', 'DULJADE'}

KAPSAM_TICARI = DULOKSETIN_TICARI | {
    'EFEXOR', 'EFFEXOR', 'VENEGIS', 'FAXINE',            # venlafaksin
    'IXEL',                                              # milnasipran
    'REMERON', 'MIRTARON', 'REDEPRES', 'ZESTAT',         # mirtazapin
    'STABLON',                                           # tianeptin
    'AURORIX',                                           # moklobemid
}

# ATC: N06AX21 dulo / N06AX16 venla / N06AX23 desvenla / N06AX17 milna /
#      N06AX11 mirta / N06AX14 tianeptin / N06AG02 moklobemid
KAPSAM_ATC = ('N06AX21', 'N06AX16', 'N06AX23', 'N06AX17',
              'N06AX11', 'N06AX14', 'N06AG02')

# Branş kümeleri (norm_tr_lower alt-string)
PSIKIYATRI = ['psikiyatri', 'ruh sag', 'ruh ve sinir']
NOROLOJI = ['noroloji', 'norolog']
GERIATRI = ['geriatri']

GRUP_P = '‖P‖ (4.2.2-1) Psikiyatri yetkisi: reçeteci veya raporu (≥1)'
GRUP_N_YETKI = '‖N‖ (4.2.2-1) Nöroloji/geriatri yetkisi: reçeteci veya raporu (≥1)'
GRUP_N_SURE = '‖N‖ (4.2.2-1) Kullanım süresi ≤ 6 ay'
GRUP_BILGI_SURE = '(bilgi) Raporda kullanım süresi belirtilmiş (fıkra 9)'
GRUP_BILGI_END_DISI = '(bilgi) Endikasyon dışı kullanım onayı'


# ═══════════════════════════════════════════════════════════════════════
# KAPSAM TESPİTİ
# ═══════════════════════════════════════════════════════════════════════

def snri_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Satır SUT 4.2.2(1) SNRI/SSRE/RIMA/NaSSA kapsamında mı?"""
    atc = norm_tr_upper(str(ilac_sonuc.get('atc_kodu') or '')).strip()
    if atc and any(atc.startswith(a) for a in KAPSAM_ATC):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, KAPSAM_ETKEN) or _iceriyor(m, KAPSAM_TICARI)


def _duloksetin_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(str(ilac_sonuc.get('atc_kodu') or '')).strip()
    if atc.startswith('N06AX21'):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, DULOKSETIN_ETKEN) or _iceriyor(m, DULOKSETIN_TICARI)


def _etken_sinif(ilac_sonuc: Dict) -> str:
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, SSRE_ETKEN) or 'STABLON' in m:
        return 'SSRE'
    if _iceriyor(m, RIMA_ETKEN) or 'AURORIX' in m:
        return 'RIMA'
    if _iceriyor(m, NASSA_ETKEN) or any(
            t in m for t in ('REMERON', 'MIRTARON', 'REDEPRES')):
        return 'NaSSA'
    return 'SNRI'


def _sui_sinyali(ilac_sonuc: Dict) -> bool:
    """Stres SUI / mikst SUI ibaresi rapor/teşhis metninde var mı?"""
    ml = _rapor_metni(ilac_sonuc)
    return (
        ('stres' in ml and ('inkontinan' in ml or 'sui' in ml or 'uriner' in ml))
        or ('mikst' in ml and 'inkontinan' in ml)
        or ('mixed' in ml and ('incont' in ml or 'urinary' in ml))
    )


# ═══════════════════════════════════════════════════════════════════════
# TARİH yardımcıları (T1 — 6 ay)
# ═══════════════════════════════════════════════════════════════════════

def _tarih_parse(v) -> Optional[date]:
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:19]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d',
                '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # 'YYYY-MM-DD...' öneki dene
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def _atom_receteci(ilac_sonuc: Dict, brans_list: List[str], ad: str,
                   grup: str) -> SartSonuc:
    """Reçete eden hekim verilen branş listesinde mi? (3-yönlü)."""
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, veya_grubu=True,
                         sartli_atom=True)
    if _brans_listede(brans, brans_list):
        return SartSonuc(ad=f'{ad}: {brans}', durum=SartDurumu.VAR,
                         neden='SUT 4.2.2(1): bu uzman hekim doğrudan reçete edebilir',
                         kaynak='hekim_brans', grup=grup, veya_grubu=True)
    return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                     neden=f'Reçeteci branşı ({brans}) bu listede değil',
                     kaynak='hekim_brans', grup=grup, veya_grubu=True)


def _atom_rapor_brans(ilac_sonuc: Dict, brans_list: List[str], ad: str,
                      grup: str) -> SartSonuc:
    """Uzman hekim raporunu verilen branşlardan biri mi düzenlemiş? (3-yönlü).

    Kaynaklar: rapor_doktor_brans + heyet branşları + rapor metninde branş
    ibaresi. Rapor var ama branş okunamıyor → KE-şartlı (örtük kabul yasak).
    """
    if not _rapor_var(ilac_sonuc):
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu yok',
                         kaynak='rapor_brans', grup=grup, veya_grubu=True)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, brans_list) for a in adaylar):
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden='SUT branşının düzenlediği rapora dayanılarak '
                               'tüm hekimlerce reçete edilebilir',
                         kaynak='rapor_brans', grup=grup, veya_grubu=True)
    # Rapor metninde branş ibaresi fallback
    metin = _rapor_metni(ilac_sonuc)
    if any(a in metin for a in brans_list):
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden='Rapor metninde bu uzman branş ibaresi geçiyor',
                         kaynak='rapor_metni', grup=grup, veya_grubu=True)
    if not any(_brans_l(a) for a in adaylar):
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama düzenleyen/heyet branşı okunamadı '
                               '— manuel',
                         kaynak='rapor_brans', grup=grup, veya_grubu=True,
                         sartli_atom=True)
    return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                     neden='Rapor düzenleyen branş bu listede değil',
                     kaynak='rapor_brans', grup=grup, veya_grubu=True)


def _atom_sure_6ay(ilac_sonuc: Dict) -> SartSonuc:
    """T1 — kullanım süresi ≤ 6 ay (yalnız ‖N‖ nöroloji/geriatri yolunda).

    Kaynak: ``hasta_snri_ilk_recete_tarihi`` (GUI runner'ın EOS SELECT
    enrichment'i, satırın etkenine/ATC'sine göre en eski reçete tarihi) +
    ``recete_tarihi``. Enrichment yoksa KE-şartlı — hasta ilacı başka
    eczaneden almış olabilir (örtük kabul yasak, bkz.
    feedback_drug_history_db_ke).
    """
    ilk = _tarih_parse(ilac_sonuc.get('hasta_snri_ilk_recete_tarihi'))
    rt = _tarih_parse(ilac_sonuc.get('recete_tarihi'))
    if ilk is None:
        return SartSonuc(ad='Kullanım süresi ≤ 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='İlk SNRI reçete tarihi tespit edilemedi (yerel '
                               'kayıt yok / enrichment yok) — başka eczaneden '
                               'alınmış olabilir, manuel',
                         kaynak='hasta_ilac_gecmisi', grup=GRUP_N_SURE,
                         sartli_atom=True)
    if rt is None:
        rt = date.today()
    gun = (rt - ilk).days
    if gun <= 183:
        return SartSonuc(ad=f'Kullanım süresi {gun} gün (≤6 ay)', durum=SartDurumu.VAR,
                         neden=f'İlk reçete {ilk.isoformat()} — 6 ay dolmamış, '
                               'nöroloji/geriatri yetkisi yeterli',
                         kaynak='hasta_ilac_gecmisi', grup=GRUP_N_SURE)
    return SartSonuc(ad=f'Kullanım süresi {gun} gün (>6 ay)', durum=SartDurumu.YOK,
                     neden=f'İlk reçete {ilk.isoformat()} — 6 ay aşılmış; SUT '
                           '4.2.2(1): 6 aydan uzun kullanımda psikiyatri '
                           'uzmanı/raporu gerekli',
                     kaynak='hasta_ilac_gecmisi', grup=GRUP_N_SURE)


def _atom_bilgi_rapor_sure(ilac_sonuc: Dict) -> Optional[SartSonuc]:
    """(bilgi) Fıkra 9 — raporda kullanım süresi belirtilmiş mi (yalnız raporlu)."""
    if not _rapor_var(ilac_sonuc):
        return None
    metin = _rapor_metni(ilac_sonuc)
    m = re.search(r'(\d{1,2})\s*(ay|yil)\b', metin)
    if m:
        return SartSonuc(ad=f'Raporda süre: {m.group(1)} {m.group(2)}',
                         durum=SartDurumu.VAR,
                         neden='Fıkra (9): raporda kullanım süresi belirtilmiş',
                         kaynak='rapor_metni', grup=GRUP_BILGI_SURE)
    return SartSonuc(ad='Raporda kullanım süresi', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Fıkra (9): raporda süre ibaresi okunamadı — manuel (bilgi)',
                     kaynak='rapor_metni', grup=GRUP_BILGI_SURE, sartli_atom=True)


def _atom_bilgi_endikasyon_disi(ilac_sonuc: Dict) -> Optional[SartSonuc]:
    """(bilgi) Rapor SGKEYR / endikasyon dışı onay içeriyorsa göster."""
    metin = _rapor_metni(ilac_sonuc)
    if 'sgkeyr' in metin or 'endikasyon disi' in metin:
        return SartSonuc(ad='Endikasyon dışı kullanım onayı (SGKEYR) tespit edildi',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Raporda endikasyon dışı onay ibaresi var — onay '
                               'kapsamı/geçerliliği manuel doğrulanmalı (bilgi)',
                         kaynak='rapor_metni', grup=GRUP_BILGI_END_DISI,
                         sartli_atom=True)
    return None


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (üst-VEYA çifti ‖P‖ ‖N‖)
# ═══════════════════════════════════════════════════════════════════════

def _grup_degerlendir(gs: List[SartSonuc]) -> Tuple[str, bool]:
    """('var'|'yok'|'ke', ke_atomlarin_hepsi_sartli_mi)."""
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


def _ve(a: Tuple[str, bool], b: Tuple[str, bool]) -> Tuple[str, bool]:
    if a[0] == 'yok' or b[0] == 'yok':
        return ('yok', False)
    if a[0] == 'var' and b[0] == 'var':
        return ('var', False)
    sartli = all(s for d, s in (a, b) if d == 'ke')
    return ('ke', sartli)


def _veya(a: Tuple[str, bool], b: Tuple[str, bool]) -> Tuple[str, bool]:
    if a[0] == 'var' or b[0] == 'var':
        return ('var', False)
    if a[0] == 'yok' and b[0] == 'yok':
        return ('yok', False)
    sartli = all(s for d, s in (a, b) if d == 'ke')
    return ('ke', sartli)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    p_atomlar = [s for s in sartlar if s.grup == GRUP_P]
    n_yetki = [s for s in sartlar if s.grup == GRUP_N_YETKI]
    n_sure = [s for s in sartlar if s.grup == GRUP_N_SURE]
    if not p_atomlar and not n_yetki:
        return KontrolSonucu.KONTROL_EDILEMEDI
    p = _grup_degerlendir(p_atomlar) if p_atomlar else ('yok', False)
    n = _ve(_grup_degerlendir(n_yetki) if n_yetki else ('yok', False),
            _grup_degerlendir(n_sure) if n_sure else ('var', False))
    ust, sartli = _veya(p, n)
    if ust == 'var':
        return KontrolSonucu.UYGUN
    if ust == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    return (KontrolSonucu.SARTLI_UYGUN if sartli
            else KontrolSonucu.KONTROL_EDILEMEDI)


def _mesaj_uret(sonuc: KontrolSonucu, sinif: str,
                sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI
          and '(bilgi)' not in (s.grup or '')]
    parcalar = [f"SUT 4.2.2(1) / {sinif} antidepresan"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — psikiyatri/nöroloji/geriatri yetkisi sağlanıyor")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama "
                        "gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    else:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def snri_kontrol_4_2_2(ilac_sonuc: Dict,
                       _delege_kaynak: Optional[str] = None) -> KontrolRaporu:
    """SUT 4.2.2(1) SNRI/SSRE/RIMA/NaSSA ana kontrol fonksiyonu.

    _delege_kaynak: 'uriner' / 'noropatik' — ping-pong delegasyonu önler
    (üriner→snri→üriner döngüsü olamaz).
    """
    if not snri_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.2(1) SNRI/SSRE/RIMA/NaSSA kapsamında değil',
            sut_kurali='SUT 4.2.2(1)')

    # ── Duloksetin üst dispatcher (sinyal önceliği) ──
    if _duloksetin_mi(ilac_sonuc):
        if (_delege_kaynak != 'uriner' and _rapor_var(ilac_sonuc)
                and _sui_sinyali(ilac_sonuc)):
            # Stres/mikst SUI sinyali → EK-4/F M.45 üriner kontrolü
            from recete_kontrol.sut_kontrolleri import (
                kontrol_cesitli_madde_45_uriner)
            return kontrol_cesitli_madde_45_uriner(ilac_sonuc)
        if _delege_kaynak != 'noropatik':
            e = _nor_endikasyonlar(ilac_sonuc)
            if (e['diyabetik_noro'] or e['noropatik'] or e['phn']
                    or e['fibromiyalji'] or e['kronik_kas_iskelet']):
                # Nöropati / fibromiyalji kanıtı → SUT 4.2.35 (D_A3 / D_B1)
                from recete_kontrol.noropatik_4_2_35 import (
                    noropatik_kontrol_4_2_35)
                return noropatik_kontrol_4_2_35(ilac_sonuc)

    sinif = _etken_sinif(ilac_sonuc)
    sartlar: List[SartSonuc] = []

    # ‖P‖ — psikiyatri yetkisi (süreden bağımsız)
    sartlar.append(_atom_receteci(ilac_sonuc, PSIKIYATRI,
                                  'Reçeteci psikiyatri uzmanı', GRUP_P))
    sartlar.append(_atom_rapor_brans(ilac_sonuc, PSIKIYATRI,
                                     'Psikiyatri uzman hekim raporu', GRUP_P))

    # ‖N‖ — nöroloji/geriatri yetkisi + 6 ay şartı
    sartlar.append(_atom_receteci(ilac_sonuc, NOROLOJI,
                                  'Reçeteci nöroloji uzmanı', GRUP_N_YETKI))
    sartlar.append(_atom_receteci(ilac_sonuc, GERIATRI,
                                  'Reçeteci geriatri uzmanı', GRUP_N_YETKI))
    sartlar.append(_atom_rapor_brans(ilac_sonuc, NOROLOJI + GERIATRI,
                                     'Nöroloji/geriatri uzman hekim raporu',
                                     GRUP_N_YETKI))
    sartlar.append(_atom_sure_6ay(ilac_sonuc))

    # (bilgi) atomları — matematiğe girmez
    b1 = _atom_bilgi_rapor_sure(ilac_sonuc)
    if b1:
        sartlar.append(b1)
    b2 = _atom_bilgi_endikasyon_disi(ilac_sonuc)
    if b2:
        sartlar.append(b2)

    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sinif, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali='SUT 4.2.2(1) — SNRI/SSRE/RIMA/NaSSA: psikiyatri/nöroloji/'
                   'geriatri uzmanı veya raporu; 6 ay+ yalnız psikiyatri',
        sartlar=sartlar,
        aranan_ibare='psikiyatri ∨ (nöroloji/geriatri ∧ ≤6 ay) — reçeteci veya rapor',
        detaylar={'alt_grup': sinif, 'yolak': 'SNRI_4_2_2',
                  'duloksetin': _duloksetin_mi(ilac_sonuc),
                  'delege_kaynak': _delege_kaynak or ''})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Reçeteci psikiyatri, raporsuz → UYGUN", {
            'etkin_madde': 'DULOKSETIN', 'ilac_adi': 'DUXET 30MG',
            'brans': 'Psikiyatri',
        }, KontrolSonucu.UYGUN),
        ("Reçeteci Ruh Sağlığı ve Hastalıkları (TR-İ), raporsuz → UYGUN", {
            'etkin_madde': 'DULOKSETİN', 'ilac_adi': 'DULOXX 30MG',
            'brans': 'RUH SAĞLIĞI VE HASTALIKLARI',
        }, KontrolSonucu.UYGUN),
        ("Reçeteci nöroloji, ilk reçete bu ay (≤6 ay) → UYGUN", {
            'etkin_madde': 'VENLAFAKSIN', 'brans': 'Nöroloji',
            'recete_tarihi': '2026-06-15',
            'hasta_snri_ilk_recete_tarihi': '2026-05-01',
        }, KontrolSonucu.UYGUN),
        ("Reçeteci nöroloji, ilk reçete 8 ay önce (>6 ay), psik. rapor yok → UYGUN DEĞİL", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Nöroloji',
            'recete_tarihi': '2026-06-15',
            'hasta_snri_ilk_recete_tarihi': '2025-10-01',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Reçeteci nöroloji, geçmiş bilinmiyor → ŞARTLI UYGUN (6 ay manuel)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Nöroloji',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Aile hekimi + psikiyatri raporu → UYGUN", {
            'etkin_madde': 'MIRTAZAPIN', 'brans': 'Aile Hekimliği',
            'rapor_kodu': '11.04', 'rapor_doktor_brans': 'Psikiyatri',
        }, KontrolSonucu.UYGUN),
        ("Aile hekimi + raporsuz → UYGUN DEĞİL", {
            'etkin_madde': 'DULOKSETIN', 'ilac_adi': 'DYLOXIA 30MG',
            'brans': 'Aile Hekimliği',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Branş bilinmiyor + raporsuz → ŞARTLI UYGUN (branş manuel)", {
            'etkin_madde': 'DULOKSETIN', 'ilac_adi': 'DUXET 60MG',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Dahiliye + rapor var, branş okunamadı → ŞARTLI UYGUN", {
            'etkin_madde': 'VENLAFAKSIN', 'brans': 'İç Hastalıkları',
            'rapor_kodu': '11.04',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Duloksetin + diyabetik nöropati teşhisi → 4.2.35 delege (D_A3 UYGUN)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Endokrinoloji ve Metabolizma',
            'recete_teshisleri': ['E11.4 DIYABETIK NOROPATI'],
        }, KontrolSonucu.UYGUN),
        ("Duloksetin + SUI raporu + kadın → M.45 delege (UYGUN)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Üroloji', 'cinsiyet': 'K',
            'rapor_kodu': '20.01',
            'rapor_aciklamalari': ['stres üriner inkontinans'],
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol) → ATLANDI", {
            'etkin_madde': 'PARASETAMOL',
        }, KontrolSonucu.ATLANDI),
        ("Trazodon kapsam dışı (ayrı hüküm) → ATLANDI", {
            'etkin_madde': 'TRAZODON HCL', 'ilac_adi': 'DESYREL 100 MG',
        }, KontrolSonucu.ATLANDI),
    ]


def akil_testi_calistir() -> bool:
    print("SUT 4.2.2(1) — SNRI/SSRE/RIMA/NaSSA — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = snri_kontrol_4_2_2(ilac_sonuc)
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
