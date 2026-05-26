# -*- coding: utf-8 -*-
"""Atom kütüphanesi — yeniden kullanılabilir SUT şart doğrulayıcıları.

Her atom imzası: `(baglam: Baglam, **params) -> AtomSonuc`.
AtomSonuc = (durum: SartDurumu, neden: str).

Yeni atom eklemek: `@atom("ad")` dekoratörü; motor JSON kuralında atom adını
görünce kayıttan çağırır. Atom kütüphanesi büyüdükçe yeni SUT kuralları için
genelde sadece JSON yazmak yeter — yeni Python kodu gerekmez.

PILOT (Fibrat 4.2.28.B): 12 atom yeterli. Çoğu mevcut Fibrat parserlarını
ince sarmalar (kontaminasyon olmasın diye birebir kopyalamadık — ortak
helperları doğrudan çağırıyoruz).
"""
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import SartDurumu
from recete_kontrol.tr_normalize import norm_tr_upper


@dataclass
class AtomSonuc:
    """Tek bir atomun çıktısı — motor SartSonuc'a sarar."""
    durum: SartDurumu
    neden: str = ""


# ─────────────────────────────────────────────────────────────────────────
# Atom registry
# ─────────────────────────────────────────────────────────────────────────
atom_kayit: Dict[str, Callable] = {}


def atom(ad: str):
    """Atomu motor için kayıt eden dekoratör.

    Örnek:
        @atom("rapor_lab_olcum")
        def _atom_lab(baglam, *, ibare, op, deger):
            ...
    """
    def _wrap(fn):
        if ad in atom_kayit:
            raise ValueError(f"Atom '{ad}' zaten kayıtlı: {atom_kayit[ad]}")
        atom_kayit[ad] = fn
        return fn
    return _wrap


# ═════════════════════════════════════════════════════════════════════════
# Genel amaçlı atomlar (her SUT'ta işe yarar)
# ═════════════════════════════════════════════════════════════════════════

@atom("rapor_metni_var")
def atom_rapor_metni_var(baglam) -> AtomSonuc:
    """Rapor/mesaj metni boş değil mi?"""
    if baglam.metin_bos_mu():
        return AtomSonuc(SartDurumu.YOK, "Rapor/mesaj metni boş")
    return AtomSonuc(SartDurumu.VAR, "Metin mevcut")


@atom("manuel_kontrol_gerekli")
def atom_manuel_kontrol_gerekli(baglam, *,
                                 varsayilan_durum: str = "kontrol_edilemedi",
                                 neden: str = "Sistem sorgulayamıyor — manuel doğrulama gerekli"
                                 ) -> AtomSonuc:
    """Parse edilemeyen / sistem verisinde olmayan şartlar için yer tutucu.

    Hasta satış geçmişi, kişisel tedavi takvimi gibi sistemde olmayan
    bilgiler için kullanılır. Her zaman 'kontrol_edilemedi' döner;
    SartSonuc.sartli_atom=True ile birleşince genel sonuç SARTLI_UYGUN
    olur (eczacı manuel doğrularsa kesin UYGUN'a çevirir).
    """
    durum_map = {
        "var": SartDurumu.VAR,
        "yok": SartDurumu.YOK,
        "kontrol_edilemedi": SartDurumu.KONTROL_EDILEMEDI,
    }
    return AtomSonuc(
        durum_map.get(varsayilan_durum, SartDurumu.KONTROL_EDILEMEDI),
        neden,
    )


@atom("rapor_kodu_var")
def atom_rapor_kodu_var(baglam) -> AtomSonuc:
    """Reçete satırında rapor kodu var mı?"""
    if baglam.rapor_kodu_yok_mu():
        return AtomSonuc(SartDurumu.YOK, "Rapor kodu boş")
    return AtomSonuc(SartDurumu.VAR, f"Rapor kodu: {baglam.rapor_kodu}")


@atom("rapor_kodu_in")
def atom_rapor_kodu_in(baglam, *, prefixler: List[str]) -> AtomSonuc:
    """Rapor kodu listedeki prefix'lerden biri ile başlıyor mu?

    Genelde "medula otoritesi" rapor kodları için kullanılır
    (04.02 KAH, 04.04 vs. bilen otorite).
    """
    rk = baglam.rapor_kodu
    if not rk:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI, "Rapor kodu yok")
    for p in prefixler:
        if rk.startswith(str(p)):
            return AtomSonuc(SartDurumu.VAR, f"Rapor kodu {rk} ∈ {prefixler}")
    return AtomSonuc(SartDurumu.YOK,
                     f"Rapor kodu {rk} listede değil ({prefixler})")


@atom("teshis_icd_in")
def atom_teshis_icd_in(baglam, *, prefixler: List[str]) -> AtomSonuc:
    """Reçete teşhislerinde verilen ICD prefix'lerinden en az biri var mı?

    prefixler: ["E10", "E11", ...] gibi. Substring değil, prefix kontrolü.
    """
    teshis = baglam.teshis_metin
    if not teshis:
        return AtomSonuc(SartDurumu.YOK, "Teşhis listesi boş")
    bulunanlar = [p for p in prefixler if p in teshis]
    if bulunanlar:
        return AtomSonuc(SartDurumu.VAR, f"ICD bulundu: {bulunanlar}")
    return AtomSonuc(SartDurumu.YOK, f"ICD eşleşmedi ({prefixler})")


@atom("metin_regex")
def atom_metin_regex(baglam, *, desenler: List[str],
                     etiket: str = "") -> AtomSonuc:
    """Birleşik metinde verilen regex desenlerinden en az biri eşleşiyor mu?

    desenler: ham regex string listesi (Python re sözdizimi).
    Türkçe-normalize edilmiş `metin_lower` üzerinde çalışır.
    """
    metin = baglam.metin_lower
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Metin boş — {etiket or 'desen'} aranamadı")
    for d in desenler:
        if re.search(d, metin):
            return AtomSonuc(SartDurumu.VAR,
                             f"{etiket or 'Desen'} eşleşti: /{d}/")
    return AtomSonuc(SartDurumu.YOK,
                     f"{etiket or 'Desen'} bulunamadı")


@atom("rapor_lab_olcum")
def atom_rapor_lab_olcum(baglam, *, ibare: str, op: str,
                         deger: float, alternatif_ibareler: Optional[List[str]] = None
                         ) -> AtomSonuc:
    """Lab değeri parse + karşılaştırma (TG/LDL/HDL/HbA1c/eGFR/INR vb.)

    ibare: ana arama anahtarı ("trigliserid").
    alternatif_ibareler: ["tg", "trig", "t.g.", "triglyceride"] gibi varyantlar.
    op: ">", ">=", "<", "<=", "=" — KATİ karşılaştırma (mevzuat lafzına dikkat!).
    deger: eşik değer.

    Metinden ibare yakınında 2-4 haneli sayı çeker, en yüksek değeri seçer
    (rapor metninde birden çok ölçüm olabilir → en kötü senaryo).
    """
    metin = baglam.birlesik_metin or ''
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{ibare} ölçümü için metin yok")
    # (Ekleme=DD/MM/YYYY HH:MM) bloklarını sil — tarih bileşeni TG sanılmasın.
    # (HASAN ÖZÇİÇEK 3DSL57J, 2026-05-16 — statin LDL parser kalıbı.)
    metin = re.sub(
        r'\(?\s*ekleme\s*[=:]\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}'
        r'(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\)?',
        ' ', metin, flags=re.IGNORECASE,
    )
    metin_sade = metin.replace('İ', 'i').replace('ı', 'i').lower()
    bulunanlar: List[int] = []

    # Ana ibare + alternatifler — her biri için "ibare ... sayı" kalıbı
    anahtarlar = [ibare] + list(alternatif_ibareler or [])
    for k in anahtarlar:
        kk = k.lower()
        # Pattern: ibare (esnek 0-20 karakter ara) + sayı
        # Özel: kısaltma için word-boundary (\btg\b) — yoksa "stage" yakalar
        if len(kk) <= 4:
            pattern = rf'\b{re.escape(kk)}\b\.?\s*[:=]?\s*(\d{{2,4}})'
        else:
            pattern = rf'{re.escape(kk)}[a-z]*[^0-9]{{0,20}}(\d{{2,4}})'
        for m in re.finditer(pattern, metin_sade):
            captured = m.group(1)
            # Tarih bileşeni reddi: "01" + "/11/2023" → tarih, lab değil.
            son_idx = m.start(1) + len(captured)
            sonrasi = metin_sade[son_idx:son_idx + 8]
            if re.match(r'[./\-]\d{1,2}[./\-]\d', sonrasi):
                continue
            try:
                bulunanlar.append(int(captured))
            except ValueError:
                pass

    # ALTERNATİF: "DEĞER TARİH ETİKET" — Medula düzeltme yazımı
    # Örn: "/ 304.8 7/6/2023 TRIGLISERID" — değer önce, etiket sonra.
    # Her ibare ve alternatifi için ayrı pattern kurulmaz; tek pattern
    # tüm anahtarları (?:a|b|c) içine alır.
    if len(anahtarlar) > 0:
        ibare_alt = '|'.join(
            re.escape(k.lower()) + r'[a-z]*'
            for k in anahtarlar if len(k) > 1
        )
        if ibare_alt:
            deger_once = re.compile(
                rf'(?<![/.\d\-])(\d{{2,4}})(?:[.,]\d+)?\s+'
                rf'\d{{1,2}}[./\-]\d{{1,2}}[./\-]\d{{2,4}}\s+'
                rf'(?:{ibare_alt})'
            )
            for m in deger_once.finditer(metin_sade):
                try:
                    bulunanlar.append(int(m.group(1)))
                except ValueError:
                    pass
            # ALT FORMAT 2: TARİH İBARE : DEĞER (MUSTAFA ÖZLÜ 2CUHRVG)
            # Örn: '30.10.2020 Triglised : 780 mg/dl'
            tarih_once = re.compile(
                rf'\d{{1,2}}[./\-]\d{{1,2}}[./\-]\d{{2,4}}\s+'
                rf'(?:{ibare_alt})\s*[:=]\s*(\d{{2,4}})'
            )
            for m in tarih_once.finditer(metin_sade):
                try:
                    bulunanlar.append(int(m.group(1)))
                except ValueError:
                    pass

    if not bulunanlar:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{ibare} sayısal değeri raporda yok")

    en_yuksek = max(bulunanlar)
    karsilastir = {
        '>':  lambda a, b: a > b,
        '>=': lambda a, b: a >= b,
        '<':  lambda a, b: a < b,
        '<=': lambda a, b: a <= b,
        '=':  lambda a, b: a == b,
    }.get(op)
    if karsilastir is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Geçersiz operatör: {op}")

    if karsilastir(en_yuksek, deger):
        return AtomSonuc(SartDurumu.VAR,
                         f"{ibare}={en_yuksek} {op} {deger}")
    return AtomSonuc(SartDurumu.YOK,
                     f"{ibare}={en_yuksek} {op} {deger} sağlanmıyor")


@atom("rapor_lab_var")
def atom_rapor_lab_var(baglam, *, ibare: str,
                        alternatif_ibareler: Optional[List[str]] = None
                        ) -> AtomSonuc:
    """Lab değeri (sayısal) raporda var mı? Karşılaştırma yapmaz, sadece varlık.

    `rapor_lab_olcum` ile aynı parser; ama op/deger yok — sadece "sayı yakaladık mı?"
    Endikasyon önkoşul kontrolleri için (örn. "TG değeri raporda VAR mı?").
    """
    metin = baglam.birlesik_metin or ''
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{ibare} için metin yok")
    metin_sade = metin.replace('İ', 'i').replace('ı', 'i').lower()
    bulunanlar: List[int] = []
    anahtarlar = [ibare] + list(alternatif_ibareler or [])
    for k in anahtarlar:
        kk = k.lower()
        if len(kk) <= 4:
            pattern = rf'\b{re.escape(kk)}\b\.?\s*[:=]?\s*(\d{{2,4}})'
        else:
            pattern = rf'{re.escape(kk)}[a-z]*[^0-9]{{0,20}}(\d{{2,4}})'
        for m in re.findall(pattern, metin_sade):
            try:
                bulunanlar.append(int(m))
            except ValueError:
                pass
    if not bulunanlar:
        return AtomSonuc(SartDurumu.YOK,
                         f"{ibare} sayısal değeri raporda yok")
    return AtomSonuc(SartDurumu.VAR,
                     f"{ibare} = {max(bulunanlar)} (raporda tespit)")


@atom("doktor_brans_in")
def atom_doktor_brans_in(baglam, *, anahtarlar: List[str],
                          rapor_kodu_otoritesi: Optional[List[str]] = None,
                          alt_liste_dallari: Optional[Dict[str, List[str]]] = None,
                          ) -> AtomSonuc:
    """Doktor uzmanlığı listedeki branşlardan birinden mi?

    anahtarlar: ['KARDIYOLOJI', 'KVC', 'NOROLOJI', ...] — substring eşleşme
    (TR-büyük harfli karşılaştırma; doktor_uzm zaten upper).

    rapor_kodu_otoritesi: ['04.02', '06', ...] — bu prefix'lerden biriyle
    başlayan rapor kodu varsa medula otoritesi olarak VAR sayılır
    (branş kontrolüne gerek yok). Listenin başında her zaman yoklanır.

    alt_liste_dallari: opsiyonel görsel meta — şema render'da branş başına
    alt grup gösterimi için (örn. {'Kardiyoloji': ['KARDIYOLOJI',...]}).
    Atom mantığında kullanılmaz; sadece JSON'da bulunan UI-yönlendirici
    veridir. Geçmiş yıllardan kalan param, motor uyumluluğu için tutulur.
    """
    _ = alt_liste_dallari  # noqa: F841 — explicit unused (UI metadata)
    rk = baglam.rapor_kodu
    if rapor_kodu_otoritesi:
        for p in rapor_kodu_otoritesi:
            if rk.startswith(str(p)):
                return AtomSonuc(SartDurumu.VAR,
                                 f"Rapor kodu {rk} medula otoritesi")
    du = norm_tr_upper(baglam.doktor_uzm or '')
    if not du:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "Doktor uzmanlığı bilgisi yok")
    for a in anahtarlar:
        if norm_tr_upper(a) in du:
            return AtomSonuc(SartDurumu.VAR,
                             f"Doktor uzmanlığı: {du} (eşleşen: {a})")
    return AtomSonuc(SartDurumu.YOK,
                     f"Doktor uzmanlığı yetkili değil: {du}")


# ═════════════════════════════════════════════════════════════════════════
# KV hastalık atomları (Fibrat Yol-b özelleştirilmiş — diyabet hariç hepsi
# basit metin/regex kontrol; bunlar metin_regex + teshis_icd_in kompozit
# atomları olarak da yazılabilir, ancak okunaklılık için ayrı atom)
# ═════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# kv_* atomları — 4-katmanlı KV kanıt taraması:
#   1. aktif reçete teşhisi ICD  → "aktif_teshis"
#   2. aktif rapor metni         → "aktif_metin"
#   3. geçmiş raporların ICD'si  → "gecmis_icd:<satir>"
#   4. geçmiş rapor metinleri    → "gecmis_rapor:<parca>"
# FERİDE EGE 3KTNEKA (2026-05-16) ile motor pariteye getirildi —
# Python kontrol_fibrat/kontrol_statin ile aynı kanıt katmanlarını kullanır.
# ─────────────────────────────────────────────────────────────

@atom("kv_dm")
def atom_kv_dm(baglam) -> AtomSonuc:
    """Diabetes mellitus — 4 katman + DOLAYLI KANIT (HÜSEYİN SAAT 2RCDQJV).

    Katmanlar:
      1. aktif teşhis ICD (E10-E14)
      2. aktif rapor metni (diyabet/DM lafzen)
      3. AKTİF METİN DOLAYLI: metformin/sulfanilür/OAD/insülin/glisemik/
         HbA1c≥6.5 (DM tedavisi/şablonu ima eder)
      4. geçmiş raporların ICD listesi
      5. geçmiş rapor metinleri (lafzen + dolaylı)
    """
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['E10', 'E11', 'E12', 'E13', 'E14']):
        return AtomSonuc(SartDurumu.VAR, "ICD E10-E14 (DM)")
    metin = baglam.metin_lower
    patterns = [r'\bdiyabet', r'\bdiabet', r'\bdm\b', r'\bt[12]dm\b',
                r'\bniddm\b', r'\biddm\b',
                r'tip\s*[12]\s*(?:dm|diyabet|diabet)',
                r'şeker\s*hastal', r'seker\s*hastal']
    for p in patterns:
        if re.search(p, metin):
            return AtomSonuc(SartDurumu.VAR, f"DM ibaresi (aktif): /{p}/")
    # DOLAYLI KANITLAR (aktif metin)
    oad_patterns = [
        r'\bmetformin', r'\bglukofa', r'\bdiabinor',
        r'\bsülfanilür', r'\bsulfanilur', r'\bsülfonilür',
        r'\bsulfonilur', r'\bglikla[zs]i', r'\bglimepir',
        r'\bgliben(?:klamid|klamit)',
        r'\boad\b', r'oral\s*antidiyabet', r'oral\s*antidiabet',
        r'\binsulin\b', r'\binsülin\b',
        r'\bdpp[- ]?4', r'glipti[nz]',
        r'\bsglt[- ]?2',
        r'\bakar?boz\b',
    ]
    for p in oad_patterns:
        m = re.search(p, metin)
        if m:
            return AtomSonuc(SartDurumu.VAR,
                             f"DM (dolaylı: {m.group(0)})")
    if re.search(r'glisemik\s*kontrol|kan\s*[şs]ekeri\s*kontrol', metin):
        return AtomSonuc(SartDurumu.VAR,
                         "DM (dolaylı: glisemik kontrol ibaresi)")
    # HbA1c ≥ 6.5 (DM tanı eşiği)
    a1c_pat = re.compile(
        r'(?:hemoglobin\s*a?1?c|hba?1?c|\ba1c)\s*[:=]?\s*'
        r'(\d{1,2})[.,](\d)')
    for m in a1c_pat.finditer(metin):
        try:
            tam = int(m.group(1)); ond = int(m.group(2))
            if tam > 6 or (tam == 6 and ond >= 5):
                return AtomSonuc(SartDurumu.VAR,
                                 f"DM (dolaylı: HbA1c={tam}.{ond} ≥6.5)")
        except ValueError:
            pass
    # Geçmiş ICD
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd, ('E10', 'E11', 'E12', 'E13', 'E14'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"DM (geçmiş ICD: {gs})")
    # Geçmiş metin (lafzen + dolaylı kanıtlar)
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri,
        '|'.join(patterns + oad_patterns
                 + [r'glisemik\s*kontrol', r'kan\s*[şs]ekeri\s*kontrol']))
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"DM ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "DM bulunamadı (aktif + dolaylı + geçmiş raporlar tarandı)")


@atom("kv_aks")
def atom_kv_aks(baglam) -> AtomSonuc:
    """Akut koroner sendrom — 4 katman."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I20', 'I21', 'I22', 'I23', 'I24']):
        return AtomSonuc(SartDurumu.VAR, "ICD I20-I24 (AKS)")
    if re.search(r'akut\s*koroner|\baks\b', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "AKS ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd, ('I20', 'I21', 'I22', 'I23', 'I24'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"AKS (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri,
        r'akut\s*koroner|\baks\b', aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"AKS ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "AKS bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_mi")
def atom_kv_mi(baglam) -> AtomSonuc:
    """Geçirilmiş Mİ — 4 katman."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I21', 'I22', 'I25.2']):
        return AtomSonuc(SartDurumu.VAR, "ICD I21/I22/I25.2 (Mİ)")
    mi_regex = (r'miyokard\s*infar|miyokard\s*enfark|geçirilmiş\s*mi\b'
                r'|\bstemi\b|\bnstemi\b')
    if re.search(mi_regex, baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "Mİ ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd, ('I21', 'I22', 'I25.2'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"Mİ (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri, mi_regex, aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"Mİ ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "Mİ bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_inme")
def atom_kv_inme(baglam) -> AtomSonuc:
    """Geçirilmiş inme — 4 katman."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in
           ['I60', 'I61', 'I62', 'I63', 'I64', 'I65', 'I66', 'I69']):
        return AtomSonuc(SartDurumu.VAR, "ICD I60-I69 (İnme)")
    inme_regex = (r'\binme\b|\bstroke\b|serebrovask|\bsvo\b'
                  r'|geçirilmiş\s*inme')
    if re.search(inme_regex, baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "İnme ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd,
        ('I60', 'I61', 'I62', 'I63', 'I64', 'I65', 'I66', 'I69'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"İnme (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri, inme_regex, aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"İnme ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "İnme bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_kah")
def atom_kv_kah(baglam) -> AtomSonuc:
    """Koroner arter hastalığı — 4 katman + rapor_kodu otoritesi."""
    rk = baglam.rapor_kodu
    if rk.startswith(('04.02', '04.04')):
        return AtomSonuc(SartDurumu.VAR, f"Rapor kodu {rk} (KAH otoritesi)")
    teshis = baglam.teshis_metin
    if any(k in teshis for k in
           ['I20', 'I21', 'I22', 'I23', 'I24', 'I25']):
        return AtomSonuc(SartDurumu.VAR, "ICD I20-I25 (KAH)")
    metin = baglam.metin_lower
    for m in re.finditer(r'koroner\s*arter', metin):
        on40 = metin[max(0, m.start() - 40):m.start()]
        if any(k in on40 for k in ('aile', 'ailesel', 'öykü', 'oyku')):
            continue
        return AtomSonuc(SartDurumu.VAR, "Koroner arter (aktif, hastada)")
    if re.search(r'\bkah\b|iskemik\s*kalp|\bkabg\b|by[-\s]?pass|\bstent\b',
                 metin):
        return AtomSonuc(SartDurumu.VAR,
                         "KAH/iskemik/bypass/stent ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd, ('I20', 'I21', 'I22', 'I23', 'I24', 'I25'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"KAH (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri,
        r'koroner\s*arter|\bkah\b|iskemik\s*kalp|\bkabg\b|by[-\s]?pass|\bstent\b',
        aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"KAH ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "KAH bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_pah")
def atom_kv_pah(baglam) -> AtomSonuc:
    """Periferik arter hastalığı — 4 katman."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I70', 'I73', 'I74']):
        return AtomSonuc(SartDurumu.VAR, "ICD I70/I73/I74 (PAH)")
    if re.search(r'periferik\s*arter|\bpah\b|\bpaod\b', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "PAH ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(
        baglam.diger_icd, ('I70', 'I73', 'I74'))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"PAH (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri,
        r'periferik\s*arter|\bpah\b|\bpaod\b', aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"PAH ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "PAH bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_aaa")
def atom_kv_aaa(baglam) -> AtomSonuc:
    """Abdominal aort anevrizması — 4 katman (ICD I71)."""
    aaa_regex = r'abdominal\s*aort\s*anevrizm|\baaa\b|aort\s*diseks'
    if re.search(aaa_regex, baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "AAA ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(baglam.diger_icd, ('I71',))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"AAA (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri, aaa_regex, aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"AAA ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "AAA bulunamadı (aktif + geçmiş raporlar tarandı)")


@atom("kv_karotid")
def atom_kv_karotid(baglam) -> AtomSonuc:
    """Karotid arter hastalığı — 4 katman (ICD I65)."""
    if re.search(r'karotid|karotis', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "Karotid ibaresi (aktif)")
    gv, gs = baglam._sk._lipid_gecmis_icd_var(baglam.diger_icd, ('I65',))
    if gv:
        return AtomSonuc(SartDurumu.VAR, f"Karotid (geçmiş ICD: {gs})")
    gv2, gs2 = baglam._sk._lipid_gecmis_metin_ara(
        baglam.diger_rapor_metinleri,
        r'karotid|karotis', aile_oykusu_redder=True)
    if gv2:
        return AtomSonuc(SartDurumu.VAR, f"Karotid ({gs2})")
    return AtomSonuc(SartDurumu.YOK,
                     "Karotid bulunamadı (aktif + geçmiş raporlar tarandı)")


# ═════════════════════════════════════════════════════════════════════════
# ANTİHİPERTANSİF ATOMLARI (EK-4/F m.51 + mono + ARB-dışı kombi)
# Kaynak: docs/sut/EK_4_F_m51_ARB.txt (2026-05-21 proje sahibi onaylı)
# ═════════════════════════════════════════════════════════════════════════

# Kombi tespiti — etken/ticari isim markerları
_ARB_KOMBI_TICARI = (
    'EXFORGE', 'SEVIKAR', 'TWYNSTA', 'MICARDISPLUS', 'MICARDIS PLUS',
    'CO-DIOVAN', 'CO-APROVEL', 'CO-OLMETEC', 'HYZAAR', 'KARVEZIDE',
    'COSAAR PLUS', 'FORZATEN', 'TRIVERAM', 'AVALOX',
)
_ARB_HCT_KEYS = (
    'HIDROKLOROTIAZID', 'HİDROKLOROTİAZİD', 'HIDROKLORTIAZID',
    'HYDROCHLOROTHIAZID', 'HCTZ',
)
# Diüretik (genel) — Botanik EOS ATC.ATCTurkce alanında C09DA* grubu için
# "VALSARTAN VE DİÜRETİKLER" / "KANDESARTAN VE DİÜRETİKLER" gibi yazılır.
# SGK 17.10.2016 duyurusu: "diüretikli kombinasyonlar 1300/51 kapsamı DIŞINDA"
# — HCT'ye özel değil, tüm ARB+diüretik kombi. ARB+HCT'nin yanı sıra
# klortalidon, indapamid içeren ARB kombileri de Y2 yoluna düşmeli.
# Pilot 2026-05-23 (NADİDE ASLAN/FERAYİ KAYA/... 26 vaka): etken
# "VE DİÜRETİKLER" yazınca hct_var=False kalıyordu → Y2 atlanıp Y3 KE → ŞÜPHELİ.
_ARB_DIURETIK_GENEL_KEYS = (
    'DIURETIK', 'DİÜRETİK', 'DIURETIKLER', 'DİÜRETİKLER',
    'KLORTALIDON', 'KLORTALİDON', 'CHLORTHALIDONE',
    'INDAPAMID', 'İNDAPAMİD', 'INDAPAMIDE',
)
_ARB_CCB_KEYS = (
    'AMLODIPIN', 'AMLODIPINE', 'LERKANIDIPIN', 'LERKANIDIPINE',
    'FELODIPIN', 'FELODIPINE', 'NIFEDIPIN', 'NIFEDIPINE',
    'NITRENDIPIN', 'BARNIDIPIN', 'NIKARDIPIN', 'ISRADIPIN',
)
_ARB_ACE_KEYS = (
    'PERINDOPRIL', 'ENALAPRIL', 'LISINOPRIL', 'RAMIPRIL',
    'KAPTOPRIL', 'KAPTOPRİL', 'BENAZEPRIL', 'KILAZAPRIL', 'KİLAZAPRİL',
    'TRANDOLAPRIL', 'KINAPRIL', 'KİNAPRİL', 'FOSINOPRIL', 'FOSİNOPRİL',
    'DELAPRIL', 'MOEKSIPRIL', 'MOEKSİPRİL', 'SPIRAPRIL', 'SPİRAPRİL',
    'IMIDAPRIL', 'İMİDAPRİL', 'ZOFENOPRIL',
)
_ARB_ETKEN_KEYS = (
    'IRBESARTAN', 'İRBESARTAN', 'VALSARTAN', 'LOSARTAN', 'TELMISARTAN',
    'TELMİSARTAN', 'OLMESARTAN', 'KANDESARTAN', 'CANDESARTAN',
    'EPROSARTAN', 'AZILSARTAN', 'RILMENIDEN', 'RİLMENİDEN',
    'MOKSONIDIN', 'MOKSONİDİN',
)


def _arb_kombi_analiz(baglam):
    """Tek geçişte kombi analizi yapar. Dönen sözlük:
      is_kombi, hct_var, ccb_var, ace_var, hct_only

    Türkçe karakter güvenli (_tr_lower normalize): AMLODİPİN ↔ AMLODIPIN,
    PERİNDOPRİL ↔ PERINDOPRIL gibi İ/I varyantları otomatik eşleşir.
    Pilot 2026-05-23: EXFORGE/VALSARTAN+AMLODİPİN için CCB tespit
    edilemeyince 3'lü kombiler yanlışlıkla HCT_ONLY sayılıyordu.
    """
    _trl = baglam._sk._tr_lower
    aday = _trl(baglam.etkin_madde + ' ' + baglam.ilac_adi)
    et = baglam.etkin_madde
    is_kombi = ('/' in et) or (' VE ' in f' {et} ')
    if not is_kombi and any(_trl(t) in _trl(baglam.ilac_adi)
                             for t in _ARB_KOMBI_TICARI):
        is_kombi = True
    hct_var = (any(_trl(k) in aday for k in _ARB_HCT_KEYS)
               or ' hct' in (' ' + aday + ' ') or '/hct' in aday
               or any(_trl(k) in aday for k in _ARB_DIURETIK_GENEL_KEYS))
    ccb_var = any(_trl(k) in aday for k in _ARB_CCB_KEYS)
    ace_var = any(_trl(k) in aday for k in _ARB_ACE_KEYS)
    hct_only = is_kombi and hct_var and not ccb_var and not ace_var
    return {
        'is_kombi': is_kombi, 'hct_var': hct_var,
        'ccb_var': ccb_var, 'ace_var': ace_var, 'hct_only': hct_only,
    }


@atom("arb_kombi_mi")
def atom_arb_kombi_mi(baglam) -> AtomSonuc:
    """ARB etken maddesi başka bir antihipertansifle kombi mi?

    `/` ya da kombi ticari isim (Exforge, Sevikar vb.) varsa VAR.
    Mono ARB ise YOK.
    """
    a = _arb_kombi_analiz(baglam)
    if a['is_kombi']:
        bilesen = []
        if a['hct_var']: bilesen.append('HCT')
        if a['ccb_var']: bilesen.append('CCB')
        if a['ace_var']: bilesen.append('ACE-i')
        return AtomSonuc(SartDurumu.VAR,
                         f"ARB kombi (içerik: {'+'.join(bilesen) or 'belirsiz'})")
    return AtomSonuc(SartDurumu.YOK, f"Mono ARB: {baglam.etkin_madde}")


@atom("arb_kombi_tipi")
def atom_arb_kombi_tipi(baglam, *, tip: str) -> AtomSonuc:
    """Kombi tipi sorgu. tip ∈ {'HCT_ONLY', 'CCB_ICEREN', 'ACE_ICEREN'}.

    HCT_ONLY: SGK 17.10.2016 istisnası kapsamı (sadece ARB+HCT).
    CCB_ICEREN / ACE_ICEREN: 3'lü kombide istisna geçersiz.
    """
    a = _arb_kombi_analiz(baglam)
    t = tip.upper()
    if t == 'HCT_ONLY':
        if a['hct_only']:
            return AtomSonuc(SartDurumu.VAR,
                             "ARB+HCT diüretik kombi (SGK 17.10.2016 istisnası)")
        return AtomSonuc(SartDurumu.YOK,
                         "Sadece-HCT kombi değil (mono ya da CCB/ACE içeriyor)")
    if t == 'CCB_ICEREN':
        if a['ccb_var']:
            return AtomSonuc(SartDurumu.VAR, "Kombide CCB var")
        return AtomSonuc(SartDurumu.YOK, "Kombide CCB yok")
    if t == 'ACE_ICEREN':
        if a['ace_var']:
            return AtomSonuc(SartDurumu.VAR, "Kombide ACE-i var")
        return AtomSonuc(SartDurumu.YOK, "Kombide ACE-i yok")
    return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI, f"Bilinmeyen tip: {tip}")


@atom("arb_monoterapi_ibaresi")
def atom_arb_monoterapi_ibaresi(baglam) -> AtomSonuc:
    """Raporda "monoterapi ile kan basıncı kontrol altına alınamadığı"
    ibaresi (2-yönlü: VAR / YOK).

    SUT EK-4/F m.51 (2): bu ibare RAPORDA belirtilmesi gerekir; YOKSA şart
    sağlanmamış demektir. Sessizlik KE değil YOK döner — kullanıcı kuralı
    (2026-05-23): "monoterapi ibaresi YOK → UYGUN_DEĞİL etiketi basılır;
    diğer raporlarda varsa bypass devreye girer ve DİĞER RAPOR UYGUN olur".
    ŞÜPHELİ etiketi monoterapi atomu için kullanılmaz.

    POZ ibareler (VAR): monoterapi yetersiz, kombi gerekli, tek ilaç
        kontrol edemiyor.
    NEG ibareler (YOK): monoterapi yeterli, tek ilaç başarılı (kontrendikasyon).
    Sessiz (YOK): metin var ama ibare yok — şart sağlanmamış.
    Rapor metni TAMAMEN BOŞ (YOK): aktif raporda hiç metin yok — yine YOK
        kabul (post-process bypass diğer raporlara bakar).
    """
    ml = (baglam.tum_metin or '')
    if not ml.strip():
        return AtomSonuc(SartDurumu.YOK,
                         "Rapor/mesaj metni boş — monoterapi ibaresi yok")
    ml = ml.replace('İ', 'i').replace('I', 'i').replace('ı', 'i').lower()

    poz_ibareler = (
        'monoterapiye dirençli', 'monoterapiye direncli',
        'monoterapiye yanit', 'monoterapi yetersiz', 'monoterapi yeter siz',
        'kombine terapi endikasyon', 'kombine tedavi endikasyon',
        'kombine tedavi gerek', 'kombine tedavi şart', 'kombine tedavi sart',
        'kombine tedavi endike', 'kombinasyon tedavi gerek',
        'ikili tedavi gerek', 'üçlü tedavi gerek', 'uclu tedavi gerek',
    )
    for ib in poz_ibareler:
        if ib in ml:
            return AtomSonuc(SartDurumu.VAR, f'İbare bulundu: "{ib}"')

    # 'monoterapi' tek başına geçiyorsa POZ kabul (mevcut kod kalıbı)
    if 'monoterapi' in ml:
        return AtomSonuc(SartDurumu.VAR, 'İbare: "monoterapi"')

    kompozit = (
        (('tek ilaç', 'tek ilac', 'tek antihipertansif'),
         ('yeter', 'kontrol', 'sağlanama', 'saglanama',
          'yanit', 'alinama')),
        (('kan basinci', 'tansiyon'),
         ('kontrol altina alinama',
          'yeterli kontrol sağlanama', 'yeterli kontrol saglanama',
          'kontrol edilemem')),
        (('kombinasyon',), ('gerek', 'şart', 'sart', 'endike')),
        (('yeterli',), ('kontrol sağlanama', 'kontrol saglanama')),
    )
    for anchors, helpers in kompozit:
        if (any(a in ml for a in anchors)
                and any(h in ml for h in helpers)):
            anc = next(a for a in anchors if a in ml)
            return AtomSonuc(SartDurumu.VAR,
                             f'Kompozit ibare: "{anc}" + yetersiz çağrışım')

    # NEG ibareler (nadir): "monoterapi yeterli" — buraya gelene kadar
    # "monoterapi" zaten yakalanırdı; bu kol sadece NEG kalıpları için.
    neg_ibareler = (
        'monoterapi yeterli', 'tek ilaç kontrol altinda',
        'tek ilac kontrol altinda',
    )
    for ib in neg_ibareler:
        if ib in ml:
            return AtomSonuc(SartDurumu.YOK,
                             f'NEG ibare: "{ib}" — kombi endikasyonu yok')

    return AtomSonuc(SartDurumu.YOK,
                     'Monoterapi/yetersizlik ibaresi raporda geçmiyor '
                     '— şart sağlanmamış')


# Aile hekimliği yetkisi için sabit tesis kodları
# (kontrol_arb_ek4f_m51 ile aynı liste — tek kaynak için ileride taşınmalı)
_AILE_HEKIMLIGI_TESIS_KODLARI = frozenset({'11349904'})
_KRONIK_HASTALIK_HEKIMI_TESIS_KODLARI = frozenset({'11990099'})


@atom("aile_hekimi_yetkisi")
def atom_aile_hekimi_yetkisi(baglam) -> AtomSonuc:
    """Aile hekimi reçete yazma yetkisi — 4 yoldan ≥1 sağlanmalı.

    Yollar (OR):
      1. doktor_uzmanligi 'AİLE HEK' içeriyor (sertifika)
      2. kurum_adi ASM/AHM/Aile Sağlığı içeriyor
      3. tesis_kodu sabit listede
      4. Kronik Hastalık Hekimi (doktor_adi + tesis_kodu)

    Üç-yönlü:
      VAR : yetki tespit edildi (en az 1 yol)
      KE  : pratisyen branşı ama sertifika/ASM kaydı yok (manuel)
      YOK : yetkili branş (uzman) ya da kesin uygunsuz
    """
    du = baglam.doktor_uzm.upper()
    ku = baglam.kurum_adi.upper()
    tk = baglam.tesis_kodu
    da = baglam.doktor_adi
    nedenler = []

    if 'AILE HEK' in du or 'AİLE HEK' in du:
        nedenler.append('branş: aile hekimliği')
    if ku and (
            'AILE SAGLIGI' in ku or 'AİLE SAĞLIĞI' in ku
            or 'AILE SAĞLIĞI' in ku or 'AİLE SAGLIGI' in ku
            or 'AILE HEKIMLIGI' in ku or 'AİLE HEKİMLİĞİ' in ku
            or any(tok in ku.split() for tok in ('ASM', 'AHM'))):
        nedenler.append(f'kurum: {baglam.kurum_adi[:40]}')
    if tk and tk in _AILE_HEKIMLIGI_TESIS_KODLARI:
        nedenler.append(f'tesis kodu: {tk}')
    if tk and tk in _KRONIK_HASTALIK_HEKIMI_TESIS_KODLARI:
        if 'kronik hastalik hekimi' in baglam._sk._tr_lower(da or ''):
            nedenler.append(f'kronik hastalık hekimi (tesis {tk})')

    if nedenler:
        return AtomSonuc(SartDurumu.VAR, ' + '.join(nedenler))

    # Pratisyen hekim + sertifika/ASM/tesis kanıtı yok → YOK
    # (Gerçekten sertifikalı pratisyenler için kullanıcı tesis kodunu listeye
    # ekleyebilir; default davranış raporsuz ARB kombiyi UYGUN_DEGIL'e sürer.)
    if 'PRATISYEN' in du or 'PRATİSYEN' in du:
        return AtomSonuc(SartDurumu.YOK,
                         f'Pratisyen hekim — aile hekimliği sertifikası/ASM '
                         f'kaydı tespit edilemedi (tesis: {baglam.tesis_kodu or "?"})')

    # Branş bilgisi tamamen yoksa KE
    if not du:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         'Doktor branş bilgisi yok — manuel doğrulama')

    return AtomSonuc(SartDurumu.YOK,
                     f'Aile hekimi yetkisi yok (branş: {du})')


@atom("kutu_sayisi_op")
def atom_kutu_sayisi_op(baglam, *, op: str, deger: float) -> AtomSonuc:
    """Kutu sayısı karşılaştırması.

    op ∈ {'<=', '<', '>=', '>', '='}
    deger: eşik (örn. 1.0 → "ayda 1 kutu" sınırı).
    """
    k = baglam.kutu_sayisi
    karsilastir = {
        '<=': lambda a, b: a <= b, '<':  lambda a, b: a < b,
        '>=': lambda a, b: a >= b, '>':  lambda a, b: a > b,
        '=':  lambda a, b: a == b,
    }.get(op)
    if karsilastir is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f'Geçersiz operatör: {op}')
    if karsilastir(k, float(deger)):
        return AtomSonuc(SartDurumu.VAR,
                         f'Kutu={k:g} {op} {deger:g}')
    return AtomSonuc(SartDurumu.YOK,
                     f'Kutu={k:g} {op} {deger:g} sağlanmıyor')


@atom("ayni_recete_etken_iceriyor")
def atom_ayni_recete_etken_iceriyor(baglam, *, anahtarlar: List[str]
                                     ) -> AtomSonuc:
    """Aynı reçetenin DİĞER kalemlerinde verilen etken/ilaç markerlarından
    biri geçiyor mu? (ACE+ARB kontrendikasyon kontrolü için.)

    anahtarlar: ['PRIL', 'SARTAN', 'AMLODIPIN', ...]. Substring eşleşme.
    Bu satırın kendi etken/ilaç adına BAKMAZ — sadece diğer satırlara.
    Türkçe karakter güvenli (PERİNDOPRİL ↔ PRIL).
    """
    if not baglam.diger_etken_maddeler and not baglam.diger_ilac_adlari:
        return AtomSonuc(SartDurumu.YOK,
                         'Aynı reçetede başka kalem yok')
    hep = baglam._sk._tr_lower(
        ' '.join(baglam.diger_etken_maddeler + baglam.diger_ilac_adlari))
    bulunanlar = [a for a in anahtarlar
                  if baglam._sk._tr_lower(a) in hep]
    if bulunanlar:
        return AtomSonuc(SartDurumu.VAR,
                         f'Diğer kalemde: {bulunanlar} — '
                         f'aynı reçete kombinasyonu')
    return AtomSonuc(SartDurumu.YOK,
                     f'Diğer kalemlerde {anahtarlar} yok')


# Mono antihipertansif maksimum doz tablosu (etken bazlı, mg/gün)
# Kaynak: ilaç prospektüs ruhsat maks dozları. Eksik etken eklemek için
# prospektüsten ruhsat dozu doğrulanmalı.
_MONO_AHT_MAKS_DOZ = {
    # ACE inhibitörleri (C09A)
    'RAMIPRIL': 10, 'ENALAPRIL': 40, 'LISINOPRIL': 40, 'PERINDOPRIL': 10,
    'KAPTOPRIL': 150, 'FOSINOPRIL': 40, 'TRANDOLAPRIL': 4,
    'KINAPRIL': 80, 'QUINAPRIL': 80, 'BENAZEPRIL': 80, 'SILAZAPRIL': 5,
    'ZOFENOPRIL': 60, 'IMIDAPRIL': 20,
    # ARB (C09C) — ARB dispatcher'ı kullanır ama mono fallback için
    'VALSARTAN': 320, 'LOSARTAN': 100, 'IRBESARTAN': 300,
    'TELMISARTAN': 80, 'KANDESARTAN': 32, 'CANDESARTAN': 32,
    'OLMESARTAN': 40, 'EPROSARTAN': 800,
    # Kalsiyum kanal blokerleri (C08)
    'AMLODIPIN': 10, 'NIFEDIPIN': 60, 'FELODIPIN': 10, 'LERKANIDIPIN': 20,
    'LASIDIPIN': 6, 'BARNIDIPIN': 20, 'MANIDIPIN': 20, 'NISOLDIPIN': 60,
    'BENIDIPIN': 16,  # BENIPIN markası — max 16 mg/gün (TR ruhsat)
    'VERAPAMIL': 480, 'DILTIAZEM': 360,
    # Beta blokerler (C07)
    'METOPROLOL': 200, 'BISOPROLOL': 10, 'NEBIVOLOL': 5, 'ATENOLOL': 100,
    'KARVEDILOL': 50, 'CARVEDILOL': 50, 'PROPRANOLOL': 320,
    'SOTALOL': 320, 'TALINOLOL': 100, 'CELIPROLOL': 600,
    # Alfa blokerler (C02C)
    'DOKSAZOSIN': 16, 'DOXAZOSIN': 16, 'TERAZOSIN': 20, 'PRAZOSIN': 20,
    # Santral etkili (C02AC)
    'RILMENIDEN': 2, 'RILMENIDIN': 2, 'MOKSONIDIN': 0.6, 'MOXONIDIN': 0.6,
    'KLONIDIN': 0.9, 'CLONIDIN': 0.9, 'METILDOPA': 3000, 'METHYLDOPA': 3000,
    # Diüretikler (C03)
    'HIDROKLOROTIAZID': 50, 'INDAPAMID': 2.5, 'FUROSEMID': 80,
    'SPIRONOLAKTON': 100, 'TORASEMID': 200, 'EPLERENON': 50,
    'AMILORID': 20, 'KLORTALIDON': 100,
    # Vasodilatörler
    'HIDRALAZIN': 200, 'MINOKSIDIL': 100,
}


@atom("doz_asimi_kontrol")
def atom_doz_asimi_kontrol(baglam) -> AtomSonuc:
    """İlaç adından mg parse + etken bazlı maks doz tablosu karşılaştırma.

    VAR: doz aşımı tespit edildi (UYGUN_DEGIL'e yol açar — formülde negatif
         kullanılır, ¬doz_asimi → VAR).
    YOK: doz tablo sınırında veya altında.
    KE : mg parse edilemedi ya da etken tablo dışı.
    """
    mg_match = re.search(r'(\d+(?:[.,]\d+)?)\s*MG', baglam.ilac_adi)
    if not mg_match:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         'İlaç adından mg bilgisi parse edilemedi')
    try:
        doz_mg = float(mg_match.group(1).replace(',', '.'))
    except ValueError:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f'mg parse hatası: {mg_match.group(0)}')
    # Türkçe karakter güvenli karşılaştırma (ENALAPRİL ↔ ENALAPRIL)
    etkin_norm = baglam._sk._tr_lower(baglam.etkin_madde)
    for madde, maks in _MONO_AHT_MAKS_DOZ.items():
        if baglam._sk._tr_lower(madde) in etkin_norm:
            if doz_mg > maks:
                # Mono antihipertansif raporsuz serbest → SUT ödüyor;
                # doz aşımı tespitinde sertifikalı klinik karar gerekir.
                # KE döndür → sartli_atom ile SARTLI_UYGUN (eczacı uyarısı).
                return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                                 f'POSSIBLE DOZ AŞIMI: {madde} {doz_mg}mg > '
                                 f'maks {maks}mg/gün (etken parse/ruhsat farkı '
                                 f'olabilir; eczacı manuel doğrula)')
            return AtomSonuc(SartDurumu.YOK,
                             f'{madde} {doz_mg}mg ≤ maks {maks}mg/gün')
    return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                     f'{baglam.etkin_madde} maks doz tablosunda yok '
                     f'— manuel doğrulama')


@atom("her_zaman_var")
def atom_her_zaman_var(baglam) -> AtomSonuc:
    """Her zaman VAR döner. Trivial formül kompozisyonu için
    (örn. mono antihipertansif SUT 4.1.8 — ek şart yok, raporsuz serbest)."""
    return AtomSonuc(SartDurumu.VAR, 'SUT genel hüküm — ek şart yok')


@atom("etkin_madde_iceriyor")
def atom_etkin_madde_iceriyor(baglam, *, anahtarlar: List[str]) -> AtomSonuc:
    """Etken madde / ilaç adı verilen substring listesinden ≥1 içeriyor mu?

    Genel amaçlı sınıflandırma atomu (ARB / ACE / KKB / BB tespiti vs.).
    Türkçe karakter güvenli (PERİNDOPRİL ↔ PRIL, AMLODİPİN ↔ DIPIN).
    """
    aday = baglam._sk._tr_lower(baglam.etkin_madde + ' ' + baglam.ilac_adi)
    bulunanlar = [a for a in anahtarlar
                  if baglam._sk._tr_lower(a) in aday]
    if bulunanlar:
        return AtomSonuc(SartDurumu.VAR,
                         f'Etken/ad markeri eşleşti: {bulunanlar[0]}')
    return AtomSonuc(SartDurumu.YOK,
                     f'Markerlardan hiçbiri yok ({anahtarlar[:3]}...)')
