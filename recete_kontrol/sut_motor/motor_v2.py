# -*- coding: utf-8 -*-
"""SUT Motor v2 — JSON v2 (atomlar + boolean formül) → KontrolRaporu.

v1 farkı:
    - v1: ağaç-tabanlı JSON ({tip:AND/OR/USTOR, alt:[{atom:"ad", params:{...}}]})
    - v2: atomlar bölümü + boolean formül string ("(A1 ∨ A2) ∧ ¬B1")
    - v2: inline atom tipleri (regex/icd_in/lab_olcum/...) — Python atom yazmaya
          gerek yok; JSON'dan tanımlanır
    - v2: çoklu yolak + dispatcher built-in (USTOR'un üst seviyesi)
    - v2: yerleşik senaryo testleri

Pilot: SUT 4.2.13(3) Akut Hepatit B (2026-05-23).

Şema referansı: sut_kurallari/v2/SCHEMA.md
Üretim protokolü: docs/SUT_AI_PROTOKOL_v1.md
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc
)
from .atomlar import atom_kayit, AtomSonuc
from .baglam import Baglam
from .formul_parser import parse_formul, kullanilan_atomlar, ParserHatasi

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Yardımcı sözlükler
# ─────────────────────────────────────────────────────────────────────────

_DURUM_HARITA = {
    'VAR': SartDurumu.VAR,
    'YOK': SartDurumu.YOK,
    'KONTROL_EDILEMEDI': SartDurumu.KONTROL_EDILEMEDI,
    'KE': SartDurumu.KONTROL_EDILEMEDI,
    'NA': SartDurumu.NA,
}

_SONUC_HARITA = {
    'UYGUN': KontrolSonucu.UYGUN,
    'UYGUN_DEGIL': KontrolSonucu.UYGUN_DEGIL,
    'KONTROL_EDILEMEDI': KontrolSonucu.KONTROL_EDILEMEDI,
    'KE': KontrolSonucu.KONTROL_EDILEMEDI,
    'ŞÜPHELI': KontrolSonucu.KONTROL_EDILEMEDI,
    'SUPHELI': KontrolSonucu.KONTROL_EDILEMEDI,
    'MANUEL_KONTROL': KontrolSonucu.MANUEL_KONTROL,
    'SARTLI_UYGUN': KontrolSonucu.SARTLI_UYGUN,
    'TIBBEN_UYGUN_DEGIL': KontrolSonucu.TIBBEN_UYGUN_DEGIL,
    'ATLANDI': KontrolSonucu.ATLANDI,
    'DIGER_RAPOR_UYGUN': getattr(KontrolSonucu, 'DIGER_RAPOR_UYGUN',
                                  KontrolSonucu.UYGUN),
}

# Tip → varsayılan sessizlik
_TIP_DEFAULT_SESSIZLIK = {
    'regex': 'YOK',
    'regex_negatif': 'KE',
    'metin_regex': 'YOK',
    'icd_in': 'YOK',
    'rapor_kodu_in': 'KE',
    'rapor_kodu_var': 'YOK',
    'rapor_metni_var': 'YOK',
    'lab_olcum': 'KE',
    'lab_var': 'YOK',
    'doktor_brans': 'KE',
    'yas_op': 'KE',
    'kombi_iceriyor': 'YOK',
    'etken_iceriyor': 'YOK',
    'manuel_kontrol': 'KE',
    'her_zaman_var': 'VAR',
    'custom_python': 'KE',
}


# ─────────────────────────────────────────────────────────────────────────
# Inline atom çalıştırıcıları
# ─────────────────────────────────────────────────────────────────────────


def _atom_regex(baglam: Baglam, params: Dict, kaynak_alani: str = '') -> AtomSonuc:
    """Verilen regex desenlerinden ≥1 metinde eşleşiyor mu? VAR/YOK/KE."""
    desenler = params.get('desenler', []) or []
    etiket = params.get('etiket', 'desen')
    metin = _kaynak_metin(baglam, kaynak_alani or 'rapor_metni')
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Metin boş — {etiket} aranamadı")
    for d in desenler:
        if re.search(d, metin, re.IGNORECASE):
            return AtomSonuc(SartDurumu.VAR,
                             f"{etiket} eşleşti: /{d}/")
    return AtomSonuc(SartDurumu.YOK, f"{etiket} bulunamadı")


def _atom_regex_negatif(baglam: Baglam, params: Dict,
                         kaynak_alani: str = '') -> AtomSonuc:
    """Üç-yönlü parser: pozitif desen varsa YOK, negatif desen varsa VAR,
    ikisi de yoksa KE (sessizlik → örtük kabul yasak)."""
    poz = params.get('poz_desenler', []) or []
    neg = params.get('neg_desenler', []) or []
    etiket = params.get('etiket', 'sart')
    metin = _kaynak_metin(baglam, kaynak_alani or 'rapor_metni')
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Metin boş — {etiket} aranamadı (manuel)")
    for d in poz:
        if re.search(d, metin, re.IGNORECASE):
            return AtomSonuc(SartDurumu.YOK,
                             f"{etiket} POZ ibare: /{d}/ (kontrendikasyon)")
    for d in neg:
        if re.search(d, metin, re.IGNORECASE):
            return AtomSonuc(SartDurumu.VAR,
                             f"{etiket} NEG ibare: /{d}/")
    return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                     f"{etiket} hiç bahsedilmemiş — manuel doğrulama")


def _atom_icd_in(baglam: Baglam, params: Dict,
                  kaynak_alani: str = '') -> AtomSonuc:
    """Teşhislerde verilen ICD prefix'lerinden ≥1 var mı?"""
    prefixler = params.get('prefixler', []) or []
    kaynak = kaynak_alani or params.get('kaynak_alani', 'teshis')
    if kaynak == 'diger_icd':
        ham = baglam.diger_icd or []
        teshis_str = ' '.join(str(x) for x in ham).upper()
    else:
        teshis_str = baglam.teshis_metin or ''
    if not teshis_str:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{kaynak} boş — ICD aranamadı")
    bulunanlar = [p for p in prefixler if p.upper() in teshis_str]
    if bulunanlar:
        return AtomSonuc(SartDurumu.VAR, f"ICD bulundu: {bulunanlar}")
    return AtomSonuc(SartDurumu.YOK, f"ICD listede yok ({prefixler})")


def _atom_rapor_kodu_in(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    prefixler = params.get('prefixler', []) or []
    rk = baglam.rapor_kodu
    if not rk:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI, "Rapor kodu yok")
    for p in prefixler:
        if rk.startswith(str(p)):
            return AtomSonuc(SartDurumu.VAR,
                             f"Rapor kodu {rk} ∈ {prefixler}")
    return AtomSonuc(SartDurumu.YOK,
                     f"Rapor kodu {rk} listede değil ({prefixler})")


def _atom_rapor_kodu_var(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    if baglam.rapor_kodu_yok_mu():
        return AtomSonuc(SartDurumu.YOK, "Rapor kodu boş")
    return AtomSonuc(SartDurumu.VAR, f"Rapor kodu: {baglam.rapor_kodu}")


def _atom_rapor_metni_var(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    if baglam.metin_bos_mu():
        return AtomSonuc(SartDurumu.YOK, "Rapor/mesaj metni boş")
    return AtomSonuc(SartDurumu.VAR, "Metin mevcut")


def _atom_lab_olcum(baglam: Baglam, params: Dict,
                    kaynak_alani: str = '') -> AtomSonuc:
    """Lab sayısal değer + karşılaştırma. Ondalık (INR=2.1) ve tamsayı
    (TG=500) ikisini de destekler.

    params:
      ibare: ana arama anahtarı ('inr', 'trigliserid', ...)
      alternatif_ibareler: liste (opsiyonel)
      op: '>'|'>='|'<'|'<='|'='
      deger: float eşik
      min_hane: minimum hane (default 1; lab parser için)
    """
    ibare = params.get('ibare', '')
    alternatif = params.get('alternatif_ibareler', []) or []
    op = params.get('op', '>=')
    deger = float(params.get('deger', 0))
    if not ibare:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "lab_olcum: 'ibare' parametresi gerekli")
    metin = _kaynak_metin(baglam, kaynak_alani or 'rapor_metni') or ''
    # Birleşik metin (teşhis dahil) için fallback
    if not metin:
        metin = baglam.metin_lower or ''
    if not metin:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{ibare} ölçümü için metin yok")
    # Türkçe normalize (İ→i, ı→i)
    metin_sade = metin.replace('İ', 'i').replace('I', 'i').replace('ı', 'i').lower()
    # Tarih bloklarını sil (DD/MM/YYYY HH:MM tarih bileşeni sayı sanılmasın)
    metin_sade = re.sub(
        r'\(?\s*ekleme\s*[=:]\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}'
        r'(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\)?',
        ' ', metin_sade, flags=re.IGNORECASE,
    )

    bulunan_degerler: List[float] = []
    anahtarlar = [ibare] + list(alternatif)
    for k in anahtarlar:
        kk = k.lower().replace('İ', 'i').replace('I', 'i').replace('ı', 'i')
        # Pattern: ibare + opsiyonel araya 0-20 karakter + sayı (tam ya da ondalık)
        # word-boundary ibare için (kısa kısaltma 'inr' 'tg' vs.)
        if len(kk) <= 4:
            pattern = (rf'\b{re.escape(kk)}\b\.?\s*[:=]?\s*'
                       rf'(\d{{1,4}}(?:[.,]\d+)?)')
        else:
            pattern = (rf'{re.escape(kk)}[a-z]*[^0-9]{{0,20}}'
                       rf'(\d{{1,4}}(?:[.,]\d+)?)')
        for m in re.finditer(pattern, metin_sade):
            captured = m.group(1).replace(',', '.')
            # Tarih bileşeni reddi (01/11/2023 → "01" yakalanmasın)
            son_idx = m.start(1) + len(m.group(1))
            sonrasi = metin_sade[son_idx:son_idx + 8]
            if re.match(r'[./\-]\d{1,2}[./\-]\d', sonrasi):
                continue
            try:
                bulunan_degerler.append(float(captured))
            except ValueError:
                pass

    if not bulunan_degerler:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"{ibare} sayısal değeri raporda yok")
    # En yüksek değeri seç (en kötü senaryo)
    en_yuksek = max(bulunan_degerler)
    karsilastir = {
        '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
        '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
        '=': lambda a, b: a == b,
    }.get(op)
    if karsilastir is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Geçersiz operatör: {op}")
    if karsilastir(en_yuksek, deger):
        return AtomSonuc(SartDurumu.VAR,
                         f"{ibare}={en_yuksek:g} {op} {deger:g}")
    return AtomSonuc(SartDurumu.YOK,
                     f"{ibare}={en_yuksek:g} {op} {deger:g} sağlanmıyor")


def _atom_lab_var(baglam: Baglam, params: Dict,
                  kaynak_alani: str = '') -> AtomSonuc:
    fn = atom_kayit.get('rapor_lab_var')
    if fn is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "lab_var atom kaydı bulunamadı")
    return fn(baglam, **params)


def _atom_doktor_brans(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    fn = atom_kayit.get('doktor_brans_in')
    if fn is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "doktor_brans atom kaydı bulunamadı")
    return fn(baglam, **params)


def _atom_yas_op(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    """Hasta yaşı karşılaştırması. ham veride 'hasta_yasi' int olarak gelmeli."""
    yas = baglam.ham.get('hasta_yasi')
    if yas is None or yas == '':
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "Hasta yaşı verisi yok")
    try:
        yas = int(yas)
    except (ValueError, TypeError):
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Hasta yaşı parse edilemedi: {yas!r}")
    op = params.get('op', '>=')
    deger = params.get('deger', 0)
    karsilastir = {
        '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
        '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
        '=': lambda a, b: a == b,
    }.get(op)
    if karsilastir is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"Geçersiz operatör: {op}")
    if karsilastir(yas, deger):
        return AtomSonuc(SartDurumu.VAR, f"Yaş={yas} {op} {deger}")
    return AtomSonuc(SartDurumu.YOK, f"Yaş={yas} {op} {deger} sağlanmıyor")


def _atom_kombi_iceriyor(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    fn = atom_kayit.get('ayni_recete_etken_iceriyor')
    if fn is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "kombi_iceriyor atom kaydı bulunamadı")
    return fn(baglam, **params)


def _atom_etken_iceriyor(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    fn = atom_kayit.get('etkin_madde_iceriyor')
    if fn is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "etken_iceriyor atom kaydı bulunamadı")
    return fn(baglam, **params)


def _atom_manuel_kontrol(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    fn = atom_kayit.get('manuel_kontrol_gerekli')
    if fn is None:
        # Inline fallback
        durum = _DURUM_HARITA.get(
            params.get('varsayilan_durum', 'KE').upper(),
            SartDurumu.KONTROL_EDILEMEDI)
        neden = params.get('neden', 'Sistem sorgulayamıyor — manuel doğrulama')
        return AtomSonuc(durum, neden)
    return fn(baglam, **params)


def _atom_her_zaman_var(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    return AtomSonuc(SartDurumu.VAR,
                     params.get('neden', 'Trivial true (raporsuz serbest)'))


def _atom_custom_python(baglam: Baglam, params: Dict, **_) -> AtomSonuc:
    """v1 atom kaydını çağır (geriye dönük uyum)."""
    atom_adi = params.get('atom_adi')
    if not atom_adi:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         "custom_python: atom_adi belirtilmemiş")
    fn = atom_kayit.get(atom_adi)
    if fn is None:
        return AtomSonuc(SartDurumu.KONTROL_EDILEMEDI,
                         f"custom_python: bilinmeyen atom: {atom_adi}")
    alt_params = params.get('params', {}) or {}
    return fn(baglam, **alt_params)


# Inline tip dispatcher
_INLINE_TIPLER: Dict[str, Callable] = {
    'regex': _atom_regex,
    'metin_regex': _atom_regex,
    'regex_negatif': _atom_regex_negatif,
    'icd_in': _atom_icd_in,
    'rapor_kodu_in': _atom_rapor_kodu_in,
    'rapor_kodu_var': _atom_rapor_kodu_var,
    'rapor_metni_var': _atom_rapor_metni_var,
    'lab_olcum': _atom_lab_olcum,
    'lab_var': _atom_lab_var,
    'doktor_brans': _atom_doktor_brans,
    'yas_op': _atom_yas_op,
    'kombi_iceriyor': _atom_kombi_iceriyor,
    'etken_iceriyor': _atom_etken_iceriyor,
    'manuel_kontrol': _atom_manuel_kontrol,
    'her_zaman_var': _atom_her_zaman_var,
    'custom_python': _atom_custom_python,
}


def _kaynak_metin(baglam: Baglam, kaynak_alani: str) -> str:
    """Atom kaynak alanına göre metin getir.

    rapor_metni → tum_metin (lower)
    teshis → teshis_metin
    diger_rapor_metinleri → tüm geçmiş rapor metinleri birleşik
    birlesik → birlesik_metin (varsayılan)
    """
    if kaynak_alani in ('rapor_metni', 'tum_metin'):
        return (baglam.tum_metin or '').lower()
    if kaynak_alani == 'teshis':
        return baglam.teshis_metin or ''
    if kaynak_alani == 'diger_rapor_metinleri':
        return ' '.join(baglam.diger_rapor_metinleri or []).lower()
    if kaynak_alani == 'birlesik':
        return baglam.metin_lower or ''
    # Default: tum_metin
    return (baglam.tum_metin or '').lower()


# ─────────────────────────────────────────────────────────────────────────
# Atom çalıştırma + sessizlik default uygulama
# ─────────────────────────────────────────────────────────────────────────


def _atom_calistir_v2(atom_def: Dict, baglam: Baglam) -> AtomSonuc:
    """Tek bir atom tanımını çalıştır + sessizlik default uygula."""
    tip = atom_def.get('tip')
    if tip not in _INLINE_TIPLER:
        raise ValueError(f"Bilinmeyen atom tipi: {tip!r}. "
                         f"Geçerli tipler: {sorted(_INLINE_TIPLER)}")
    fn = _INLINE_TIPLER[tip]
    params = atom_def.get('params', {}) or {}
    kaynak_alani = atom_def.get('kaynak', '')
    try:
        sonuc = fn(baglam, params, kaynak_alani=kaynak_alani)
    except TypeError:
        # Bazı çağrı yolları kaynak_alani parametresini almaz
        sonuc = fn(baglam, params)

    # Sessizlik default: motor KE döndü ama JSON daha spesifik default verdiyse
    # uygula (örn. NEGATİF atomda sessiz → KE; POZİTİF atomda sessiz → YOK)
    if sonuc.durum == SartDurumu.KONTROL_EDILEMEDI:
        sd = atom_def.get('sessizlik_default', '').upper()
        if sd and sd in _DURUM_HARITA:
            yeni_durum = _DURUM_HARITA[sd]
            if yeni_durum != SartDurumu.KONTROL_EDILEMEDI:
                sonuc = AtomSonuc(yeni_durum,
                                  f"{sonuc.neden} "
                                  f"(sessizlik default: {sd})")
    return sonuc


def _negatif_uygula(durum: SartDurumu, neg: bool) -> SartDurumu:
    if not neg:
        return durum
    if durum == SartDurumu.VAR:
        return SartDurumu.YOK
    if durum == SartDurumu.YOK:
        return SartDurumu.VAR
    return durum


def _and_birlestir(durumlar: List[SartDurumu]) -> SartDurumu:
    if not durumlar:
        return SartDurumu.NA
    if any(d == SartDurumu.YOK for d in durumlar):
        return SartDurumu.YOK
    if any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.VAR


def _or_birlestir(durumlar: List[SartDurumu]) -> SartDurumu:
    if not durumlar:
        return SartDurumu.NA
    if any(d == SartDurumu.VAR for d in durumlar):
        return SartDurumu.VAR
    if any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.YOK


# ─────────────────────────────────────────────────────────────────────────
# Formül ağacı yorumlayıcı (v2 — atom_ref ile)
# ─────────────────────────────────────────────────────────────────────────


def _formul_calistir(agac: Dict, atom_sonuclari: Dict[str, Tuple[SartDurumu, str]]
                      ) -> SartDurumu:
    """Formül ağacını çalıştır. atom_sonuclari önceden hesaplanmış olmalı."""
    if 'atom_ref' in agac:
        ad = agac['atom_ref']
        if ad not in atom_sonuclari:
            raise ValueError(f"Formülde tanımsız atom: {ad!r}")
        durum, _ = atom_sonuclari[ad]
        return _negatif_uygula(durum, bool(agac.get('negatif')))
    tip = agac.get('tip')
    alt_durumlar = [_formul_calistir(a, atom_sonuclari)
                     for a in agac.get('alt', [])]
    if tip == 'AND':
        return _and_birlestir(alt_durumlar)
    if tip == 'OR':
        return _or_birlestir(alt_durumlar)
    if tip == 'NOT':
        if not alt_durumlar:
            return SartDurumu.NA
        return _negatif_uygula(alt_durumlar[0], True)
    raise ValueError(f"Bilinmeyen formül tipi: {tip!r}")


# ─────────────────────────────────────────────────────────────────────────
# JSON v2 doğrulama
# ─────────────────────────────────────────────────────────────────────────


def _v2_dogrula(kural: Dict) -> None:
    """JSON v2 dosyasını şema açısından doğrula (yükleme zamanı)."""
    if kural.get('schema_version') != 'v2':
        raise ValueError(f"schema_version 'v2' olmalı, "
                         f"bulundu: {kural.get('schema_version')!r}")
    atomlar = kural.get('atomlar')
    yolaklar = kural.get('yolaklar')
    if not atomlar and not yolaklar:
        raise ValueError("'atomlar' veya 'yolaklar' bölümü en az birisi olmalı")
    if yolaklar and not kural.get('dispatcher'):
        raise ValueError("'yolaklar' varsa 'dispatcher' da olmalı")

    # Tek-yolak: formül → atomlar referans tutarlılığı
    if atomlar and kural.get('formul'):
        try:
            agac = parse_formul(kural['formul'])
        except ParserHatasi as e:
            raise ValueError(f"Formül parse hatası: {e}")
        kullanilanlar = kullanilan_atomlar(agac)
        tanimsiz = kullanilanlar - set(atomlar)
        if tanimsiz:
            raise ValueError(
                f"Formülde tanımlı olmayan atomlar: {sorted(tanimsiz)}. "
                f"atomlar bölümünde tanımla.")

    # Atom tipleri geçerli mi?
    def _atom_tipi_dogrula(atoms: Dict, baglam_ad: str):
        for ad, tanim in atoms.items():
            tip = tanim.get('tip')
            if tip not in _INLINE_TIPLER:
                raise ValueError(
                    f"{baglam_ad}.{ad}: bilinmeyen atom tipi {tip!r}. "
                    f"Geçerli tipler: {sorted(_INLINE_TIPLER)}")
            sd = tanim.get('sessizlik_default', '').upper()
            if sd and sd not in _DURUM_HARITA:
                raise ValueError(
                    f"{baglam_ad}.{ad}: geçersiz sessizlik_default {sd!r}. "
                    f"Geçerli: VAR/YOK/KE")

    if atomlar:
        _atom_tipi_dogrula(atomlar, 'atomlar')
    if yolaklar:
        for ad, yolak_def in yolaklar.items():
            y_atomlar = yolak_def.get('atomlar', {})
            _atom_tipi_dogrula(y_atomlar, f'yolaklar.{ad}.atomlar')
            if yolak_def.get('formul'):
                try:
                    y_agac = parse_formul(yolak_def['formul'])
                    y_kullanilan = kullanilan_atomlar(y_agac)
                    tanimsiz = y_kullanilan - set(y_atomlar)
                    if tanimsiz:
                        raise ValueError(
                            f"yolaklar.{ad}: formülde tanımsız atomlar: "
                            f"{sorted(tanimsiz)}")
                except ParserHatasi as e:
                    raise ValueError(f"yolaklar.{ad}: formül parse hatası: {e}")


# ─────────────────────────────────────────────────────────────────────────
# Dispatcher (yolak seçici)
# ─────────────────────────────────────────────────────────────────────────


def _dispatcher_calistir(disp: Dict, baglam: Baglam) -> Tuple[Optional[str], str]:
    """Yolak seç. Dönen: (yolak_adi, dispatcher_nedeni)."""
    for sinyal in sorted(disp.get('sinyaller', []),
                          key=lambda s: s.get('oncelik', 99)):
        tip = sinyal.get('tip')
        kurallar = sinyal.get('kurallar', {}) or {}
        if tip == 'rapor_kodu_prefix':
            rk = baglam.rapor_kodu
            if not rk:
                continue
            for prefix, yolak in kurallar.items():
                if rk.startswith(str(prefix)):
                    return yolak, f"rapor kodu {rk} → {yolak}"
        elif tip == 'icd_prefix':
            teshis = baglam.teshis_metin or ''
            diger = ' '.join(str(x) for x in (baglam.diger_icd or [])).upper()
            havuz = teshis + ' ' + diger
            for prefix, yolak in kurallar.items():
                if prefix.upper() in havuz:
                    return yolak, f"ICD {prefix} bulundu → {yolak}"
        elif tip == 'regex_metin':
            metin = (baglam.tum_metin or '').lower()
            for desen, yolak in kurallar.items():
                if re.search(desen, metin, re.IGNORECASE):
                    return yolak, f"metin /{desen}/ → {yolak}"
        elif tip == 'etken_iceriyor':
            aday = (baglam.etkin_madde + ' ' + baglam.ilac_adi).upper()
            for anahtar, yolak in kurallar.items():
                if anahtar.upper() in aday:
                    return yolak, f"etken {anahtar} → {yolak}"
    return None, "Hiçbir dispatcher sinyali eşleşmedi"


# ─────────────────────────────────────────────────────────────────────────
# Erken çıkış (on_kontrol)
# ─────────────────────────────────────────────────────────────────────────


def _on_kontrol_calistir(kural: Dict, baglam: Baglam) -> Optional[KontrolRaporu]:
    """on_kontrol kurallarını sırayla dener; ilk eşleşeni döner."""
    sut_etiketi = kural.get('sut_kurali_etiketi') or kural.get('adi') or ''
    atomlar_global = kural.get('atomlar', {}) or {}
    for ek in kural.get('on_kontrol', []) or []:
        kosul_str = ek.get('kosul')
        if not kosul_str:
            continue
        # Yerel atomları küresel atomlarla birleştir
        yerel_atomlar = {**atomlar_global, **(ek.get('atomlar_ek') or {})}
        try:
            agac = parse_formul(kosul_str)
            kullanilanlar = kullanilan_atomlar(agac)
            atom_sonuclari = {}
            for ad in kullanilanlar:
                if ad not in yerel_atomlar:
                    raise ValueError(f"on_kontrol kosul'da tanımsız atom: {ad}")
                a_sonuc = _atom_calistir_v2(yerel_atomlar[ad], baglam)
                atom_sonuclari[ad] = (a_sonuc.durum, a_sonuc.neden)
            durum = _formul_calistir(agac, atom_sonuclari)
        except (ValueError, ParserHatasi) as e:
            logger.warning("on_kontrol değerlendirme hatası: %s", e)
            continue
        if durum != SartDurumu.VAR:
            continue
        # Eşleşti
        sartlar = []
        for s_dict in ek.get('sartlar_ekle', []) or []:
            sartlar.append(SartSonuc(
                ad=s_dict.get('ad', ''),
                durum=_DURUM_HARITA.get(s_dict.get('durum', 'KE').upper(),
                                         SartDurumu.KONTROL_EDILEMEDI),
                neden=s_dict.get('neden', ''),
                kaynak=s_dict.get('kaynak', ''),
                grup=s_dict.get('grup', '')))
        return KontrolRaporu(
            sonuc=_SONUC_HARITA.get(
                ek.get('sonuc', 'KONTROL_EDILEMEDI').upper(),
                KontrolSonucu.KONTROL_EDILEMEDI),
            mesaj=ek.get('mesaj', ''),
            sut_kurali=sut_etiketi,
            detaylar={'erken_cikis': ek.get('ad', ''),
                      'sut_kodu': kural.get('sut_kodu', '')},
            sartlar=sartlar,
            aranan_ibare=ek.get('aranan_ibare'))
    return None


# ─────────────────────────────────────────────────────────────────────────
# Tek yolak değerlendirme (atomlar + formül → SartSonuc listesi + kök durum)
# ─────────────────────────────────────────────────────────────────────────


def _yolak_degerlendir(atomlar: Dict, formul_str: str, baglam: Baglam,
                        yolak_prefix: str = ''
                        ) -> Tuple[SartDurumu, List[SartSonuc],
                                   List[SartSonuc]]:
    """Tek yolak için tüm atomları çalıştır + formülü hesapla.

    Dönen: (kök_durum, sartlar_listesi, sartli_atomlar)
    yolak_prefix: SartSonuc.grup için kullanılır (örn. 'D-1:').
    """
    atom_sonuclari: Dict[str, Tuple[SartDurumu, str]] = {}
    sartlar: List[SartSonuc] = []

    for ad, tanim in atomlar.items():
        a_sonuc = _atom_calistir_v2(tanim, baglam)
        atom_sonuclari[ad] = (a_sonuc.durum, a_sonuc.neden)
        grup_ham = tanim.get('grup', '') or yolak_prefix
        sartlar.append(SartSonuc(
            ad=tanim.get('ad', ad),
            durum=a_sonuc.durum,
            neden=a_sonuc.neden,
            kaynak=tanim.get('kaynak', ''),
            grup=grup_ham,
            veya_grubu=bool(tanim.get('veya_grubu', False)),
            sartli_atom=bool(tanim.get('sartli_atom', False)
                              or tanim.get('bilgi', False))))

    if not formul_str:
        # Formül yoksa AND varsayalım
        formul_str = ' ∧ '.join(atomlar.keys())
    try:
        agac = parse_formul(formul_str)
    except ParserHatasi as e:
        raise ValueError(f"Formül parse hatası: {e}")
    kok_durum = _formul_calistir(agac, atom_sonuclari)

    sartli_atomlar = [s for s in sartlar
                       if s.sartli_atom
                       and s.durum == SartDurumu.KONTROL_EDILEMEDI]
    return kok_durum, sartlar, sartli_atomlar


# ─────────────────────────────────────────────────────────────────────────
# Ana giriş noktası
# ─────────────────────────────────────────────────────────────────────────


def _ilac_sonuc_normalize(ham: Dict) -> Dict:
    """Senaryo input'larında yaygın alias'ları Baglam'ın beklediği isimlere
    çevirir (geriye dönük; gerçek pipeline'da çağrılmaz, sadece input
    tutarsızlığını gidermek için).

    - etken_madde → etkin_madde
    - tum_metin   → mesaj_metni (Baglam birleştiricisi mesaj_metni'ni okur)
    """
    if not ham:
        return ham
    yeni = dict(ham)
    if 'etkin_madde' not in yeni and 'etken_madde' in yeni:
        yeni['etkin_madde'] = yeni['etken_madde']
    if 'mesaj_metni' not in yeni and 'tum_metin' in yeni:
        yeni['mesaj_metni'] = yeni['tum_metin']
    return yeni


def degerlendir_v2(kural: Dict, ilac_sonuc: Dict) -> KontrolRaporu:
    """JSON v2 kuralı ilac_sonuc reçete satırına uygula → KontrolRaporu.

    Adımlar:
      1. Şema doğrulaması (yükleme zamanında zaten yapılmıştır ama defensive)
      2. on_kontrol erken-çıkışları
      3. (Çoklu yolak ise) dispatcher → yolak seç
      4. Atomları çalıştır → formülü hesapla → kök durum
      5. Verdict eşleme → KontrolRaporu
    """
    ilac_sonuc = _ilac_sonuc_normalize(ilac_sonuc)
    baglam = Baglam(ilac_sonuc)
    sut_etiketi = kural.get('sut_kurali_etiketi') or kural.get('adi') or ''
    aranan = kural.get('aranan_ibare')

    detaylar: Dict[str, Any] = {
        'sut_kodu': kural.get('sut_kodu', ''),
        'ilac_adi': baglam.ilac_adi,
        'rapor_kodu': baglam.rapor_kodu,
        'doktor_uzm': baglam.doktor_uzm,
        'schema_version': 'v2',
    }

    # 1) Şema doğrulama (defensive — yükleme zamanı kaçırılmışsa)
    try:
        _v2_dogrula(kural)
    except ValueError as e:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f"v2 kural şeması hatalı: {e}",
            sut_kurali=sut_etiketi, detaylar=detaylar)

    # 2) on_kontrol
    erken = _on_kontrol_calistir(kural, baglam)
    if erken is not None:
        return erken

    # 3) Yolak seçimi (varsa)
    yolaklar = kural.get('yolaklar')
    if yolaklar:
        disp = kural.get('dispatcher', {})
        secilen, neden = _dispatcher_calistir(disp, baglam)
        detaylar['dispatcher_neden'] = neden
        if secilen is None or secilen not in yolaklar:
            return KontrolRaporu(
                sonuc=_SONUC_HARITA.get(
                    disp.get('belirsiz_default', 'KE').upper(),
                    KontrolSonucu.KONTROL_EDILEMEDI),
                mesaj=disp.get('belirsiz_mesaj',
                                'Yolak belirsiz — manuel doğrulama'),
                sut_kurali=sut_etiketi, detaylar=detaylar)
        yolak_def = yolaklar[secilen]
        detaylar['aktif_yolak'] = secilen
        detaylar['alt_dal'] = yolak_def.get('ad', secilen)
        atomlar_aktif = yolak_def.get('atomlar', {})
        formul_aktif = yolak_def.get('formul', '')
        yolak_prefix = f'{secilen}:'
    else:
        atomlar_aktif = kural.get('atomlar', {})
        formul_aktif = kural.get('formul', '')
        yolak_prefix = ''

    # 4) Atomları çalıştır + formülü hesapla
    try:
        kok_durum, sartlar, sartli_atomlar = _yolak_degerlendir(
            atomlar_aktif, formul_aktif, baglam, yolak_prefix=yolak_prefix)
    except ValueError as e:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f"Değerlendirme hatası: {e}",
            sut_kurali=sut_etiketi, detaylar=detaylar)

    # Üst-VEYA çiftleri metadata'sını detaylar'a aktar (GUI okur)
    if kural.get('ust_or_ciftleri'):
        detaylar['ust_or_ciftleri'] = kural['ust_or_ciftleri']
    if yolaklar and yolak_def.get('ust_or_ciftleri'):
        detaylar['ust_or_ciftleri'] = yolak_def['ust_or_ciftleri']

    # 5) Verdict eşleme
    eslesme = kural.get('verdict_eslemesi', {}) or {}
    eksik_gruplar = sorted({s.grup for s in sartlar
                            if s.durum == SartDurumu.YOK and s.grup})
    ke_gruplar = sorted({s.grup for s in sartlar
                          if s.durum == SartDurumu.KONTROL_EDILEMEDI and s.grup})
    sartli_olmayan_ke = [s for s in sartlar
                          if s.durum == SartDurumu.KONTROL_EDILEMEDI
                          and not s.sartli_atom]

    if kok_durum == SartDurumu.VAR:
        if sartli_atomlar:
            sonuc_kod = eslesme.get('VAR_with_sartli', 'SARTLI_UYGUN')
            sartli_adlar = [s.ad for s in sartli_atomlar]
            return KontrolRaporu(
                sonuc=_SONUC_HARITA[sonuc_kod.upper()],
                mesaj=(f"{kural.get('adi', 'SUT')} ŞARTLI UYGUN — sistem "
                       f"sorgulayamıyor: {', '.join(sartli_adlar)} "
                       f"(eczacı manuel doğrulamalı)"),
                sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
                uyari='Şartlı atom(lar) eczacı tarafından doğrulanmalı',
                aranan_ibare=aranan)
        sonuc_kod = eslesme.get('VAR', 'UYGUN')
        return KontrolRaporu(
            sonuc=_SONUC_HARITA[sonuc_kod.upper()],
            mesaj=f"{kural.get('adi', 'SUT')} şartları sağlanıyor",
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan)

    if kok_durum == SartDurumu.YOK:
        sonuc_kod = eslesme.get('YOK', 'UYGUN_DEGIL')
        return KontrolRaporu(
            sonuc=_SONUC_HARITA[sonuc_kod.upper()],
            mesaj=(f"{kural.get('adi', 'SUT')} şartları sağlanmıyor"
                   + (f" — eksik: {', '.join(eksik_gruplar)}"
                      if eksik_gruplar else '')),
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan)

    # KE
    if sartli_atomlar and not sartli_olmayan_ke:
        sonuc_kod = eslesme.get('KE_sadece_sartli', 'SARTLI_UYGUN')
        sartli_adlar = [s.ad for s in sartli_atomlar]
        return KontrolRaporu(
            sonuc=_SONUC_HARITA[sonuc_kod.upper()],
            mesaj=(f"{kural.get('adi', 'SUT')} ŞARTLI UYGUN — sistem "
                   f"sorgulayamıyor: {', '.join(sartli_adlar)} "
                   f"(eczacı manuel doğrulamalı)"),
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            uyari='Şartlı atom(lar) eczacı tarafından doğrulanmalı',
            aranan_ibare=aranan)
    sonuc_kod = eslesme.get('KE', 'KONTROL_EDILEMEDI')
    return KontrolRaporu(
        sonuc=_SONUC_HARITA[sonuc_kod.upper()],
        mesaj=(f"{kural.get('adi', 'SUT')} ŞÜPHELİ — manuel doğrulanmalı"
               + (f": {', '.join(ke_gruplar)}" if ke_gruplar else '')),
        sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
        uyari='Bazı şartlar metinden tespit edilemedi',
        aranan_ibare=aranan)


# ─────────────────────────────────────────────────────────────────────────
# v2 kural yükleyici
# ─────────────────────────────────────────────────────────────────────────


def kural_yukle_v2(yol: str) -> Dict:
    """v2 JSON dosyasını yükle + doğrula. Hata varsa ValueError fırlatır."""
    with open(yol, 'r', encoding='utf-8') as f:
        kural = json.load(f)
    _v2_dogrula(kural)
    return kural


def senaryo_calistir(kural: Dict, senaryo_idx: int) -> Tuple[bool, KontrolRaporu, str]:
    """JSON dosyasındaki yerleşik senaryolardan birini çalıştır.

    Dönen: (basarili_mi, rapor, mesaj)
    """
    senaryolar = kural.get('senaryolar', []) or []
    if senaryo_idx >= len(senaryolar):
        return False, None, f"Senaryo {senaryo_idx} yok"
    sen = senaryolar[senaryo_idx]
    rapor = degerlendir_v2(kural, sen.get('ilac_sonuc', {}))
    beklenen = sen.get('beklenen_verdict', '').upper()
    gercek = rapor.sonuc.value if hasattr(rapor.sonuc, 'value') else str(rapor.sonuc)

    # TR-insensitive normalize (Ş→S, Ü→U, Ç→C, İ/ı→I, Ö→O, Ğ→G)
    _tr_norm = str.maketrans({
        'Ş': 'S', 'ş': 's', 'Ü': 'U', 'ü': 'u', 'Ç': 'C', 'ç': 'c',
        'İ': 'I', 'ı': 'i', 'Ö': 'O', 'ö': 'o', 'Ğ': 'G', 'ğ': 'g',
    })
    bek_n = beklenen.translate(_tr_norm).upper()
    ger_n = gercek.translate(_tr_norm).upper()
    basarili = (bek_n == ger_n) or (bek_n in ger_n) or (ger_n in bek_n)
    mesaj = (f"Beklenen: {beklenen}, Gerçek: {gercek}, "
             f"{'✓' if basarili else '✗'}")
    return basarili, rapor, mesaj
