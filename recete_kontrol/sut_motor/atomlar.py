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
    metin_sade = metin.replace('İ', 'i').lower()
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
        for m in re.findall(pattern, metin_sade):
            try:
                bulunanlar.append(int(m))
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
    metin_sade = metin.replace('İ', 'i').lower()
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
                          rapor_kodu_otoritesi: Optional[List[str]] = None
                          ) -> AtomSonuc:
    """Doktor uzmanlığı listedeki branşlardan birinden mi?

    anahtarlar: ['KARDIYOLOJI', 'KVC', 'NOROLOJI', ...] — substring eşleşme
    (TR-büyük harfli karşılaştırma; doktor_uzm zaten upper).

    rapor_kodu_otoritesi: ['04.02', '06', ...] — bu prefix'lerden biriyle
    başlayan rapor kodu varsa medula otoritesi olarak VAR sayılır
    (branş kontrolüne gerek yok). Listenin başında her zaman yoklanır.
    """
    rk = baglam.rapor_kodu
    if rapor_kodu_otoritesi:
        for p in rapor_kodu_otoritesi:
            if rk.startswith(str(p)):
                return AtomSonuc(SartDurumu.VAR,
                                 f"Rapor kodu {rk} medula otoritesi")
    du = baglam.doktor_uzm.upper()
    if not du:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "Doktor uzmanlığı bilgisi yok")
    for a in anahtarlar:
        if a.upper() in du:
            return AtomSonuc(SartDurumu.VAR,
                             f"Doktor uzmanlığı: {du} (eşleşen: {a})")
    return AtomSonuc(SartDurumu.YOK,
                     f"Doktor uzmanlığı yetkili değil: {du}")


# ═════════════════════════════════════════════════════════════════════════
# KV hastalık atomları (Fibrat Yol-b özelleştirilmiş — diyabet hariç hepsi
# basit metin/regex kontrol; bunlar metin_regex + teshis_icd_in kompozit
# atomları olarak da yazılabilir, ancak okunaklılık için ayrı atom)
# ═════════════════════════════════════════════════════════════════════════

@atom("kv_dm")
def atom_kv_dm(baglam) -> AtomSonuc:
    """Diabetes mellitus — ICD E10-E14 ya da metinde DM/diyabet."""
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
            return AtomSonuc(SartDurumu.VAR, f"DM ibaresi: /{p}/")
    return AtomSonuc(SartDurumu.YOK, "DM bulunamadı")


@atom("kv_aks")
def atom_kv_aks(baglam) -> AtomSonuc:
    """Akut koroner sendrom — ICD I20-I24 ya da AKS/akut koroner."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I20', 'I21', 'I22', 'I23', 'I24']):
        return AtomSonuc(SartDurumu.VAR, "ICD I20-I24 (AKS)")
    if re.search(r'akut\s*koroner|\baks\b', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "AKS ibaresi")
    return AtomSonuc(SartDurumu.YOK, "AKS bulunamadı")


@atom("kv_mi")
def atom_kv_mi(baglam) -> AtomSonuc:
    """Geçirilmiş Mİ — ICD I21/I22/I25.2 ya da metinde infarktüs."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I21', 'I22', 'I25.2']):
        return AtomSonuc(SartDurumu.VAR, "ICD I21/I22/I25.2 (Mİ)")
    if re.search(r'miyokard\s*infar|miyokard\s*enfark|geçirilmiş\s*mi\b'
                 r'|\bstemi\b|\bnstemi\b', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "Mİ ibaresi")
    return AtomSonuc(SartDurumu.YOK, "Mİ bulunamadı")


@atom("kv_inme")
def atom_kv_inme(baglam) -> AtomSonuc:
    """Geçirilmiş inme — ICD I60-I69 ya da inme/stroke/SVO."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in
           ['I60', 'I61', 'I62', 'I63', 'I64', 'I65', 'I66', 'I69']):
        return AtomSonuc(SartDurumu.VAR, "ICD I60-I69 (İnme)")
    if re.search(r'\binme\b|\bstroke\b|serebrovask|\bsvo\b'
                 r'|geçirilmiş\s*inme', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "İnme ibaresi")
    return AtomSonuc(SartDurumu.YOK, "İnme bulunamadı")


@atom("kv_kah")
def atom_kv_kah(baglam) -> AtomSonuc:
    """Koroner arter hastalığı — rapor_kodu 04.02/04.04, ICD I20-I25,
    veya 'koroner arter' (aile öyküsü hariç).
    """
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
        return AtomSonuc(SartDurumu.VAR, "Koroner arter (hastada)")
    if re.search(r'\bkah\b|iskemik\s*kalp|\bkabg\b|by[-\s]?pass|\bstent\b',
                 metin):
        return AtomSonuc(SartDurumu.VAR, "KAH/iskemik/bypass/stent ibaresi")
    return AtomSonuc(SartDurumu.YOK, "KAH bulunamadı")


@atom("kv_pah")
def atom_kv_pah(baglam) -> AtomSonuc:
    """Periferik arter hastalığı — ICD I70/I73/I74 ya da PAH ibaresi."""
    teshis = baglam.teshis_metin
    if any(k in teshis for k in ['I70', 'I73', 'I74']):
        return AtomSonuc(SartDurumu.VAR, "ICD I70/I73/I74 (PAH)")
    if re.search(r'periferik\s*arter|\bpah\b|\bpaod\b', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "PAH ibaresi")
    return AtomSonuc(SartDurumu.YOK, "PAH bulunamadı")


@atom("kv_aaa")
def atom_kv_aaa(baglam) -> AtomSonuc:
    """Abdominal aort anevrizması."""
    if re.search(r'abdominal\s*aort\s*anevrizm|\baaa\b|aort\s*diseks',
                 baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "AAA ibaresi")
    return AtomSonuc(SartDurumu.YOK, "AAA bulunamadı")


@atom("kv_karotid")
def atom_kv_karotid(baglam) -> AtomSonuc:
    """Karotid arter hastalığı."""
    if re.search(r'karotid|karotis', baglam.metin_lower):
        return AtomSonuc(SartDurumu.VAR, "Karotid ibaresi")
    return AtomSonuc(SartDurumu.YOK, "Karotid bulunamadı")
