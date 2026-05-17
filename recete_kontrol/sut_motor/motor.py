# -*- coding: utf-8 -*-
"""SUT Motor — JSON formül ağacı → SartSonuc listesi → KontrolRaporu.

Kural şeması (PILOT v1):
{
  "sut_kodu": "4.2.28.B",
  "adi": "Fibrat",
  "aciklama": "...",
  "sut_kurali_etiketi": "SUT 4.2.28.B — Fibrat (atomik şema)",

  "on_kontrol": [           # erken-çıkış kuralları (sırayla denenir)
    {
      "ad": "Raporsuz koruması",
      "kosul": {            # bir formül düğümü; tüm AND/OR/ATOM çalışır
        "tip": "AND",
        "alt": [
          {"atom": "rapor_metni_var", "negatif": true},
          {"atom": "rapor_kodu_var",  "negatif": true}
        ]
      },
      "sonuc": "UYGUN_DEGIL",
      "mesaj": "Raporsuz fibrat — uzman raporu zorunlu (4.2.28.B)",
      "sartlar_ekle": [
        {"ad": "Rapor kodu", "durum": "YOK", "neden": "Reçete satırında rap_kod boş", "kaynak": "rap_kod"},
        {"ad": "Rapor/mesaj metni", "durum": "YOK", "neden": "Metin boş ve rapor da yok", "kaynak": "tum_metin"}
      ]
    }
  ],

  "formul": {               # Ana formül — kök tipik AND
    "tip": "AND",
    "alt": [
      {                                                     # Endikasyon önkoşul
        "tip": "AND",
        "grup": "Endikasyon önkoşul [(1)]",
        "alt": [
          {
            "ad": "TG sayısal değer raporda VAR",
            "atom": "rapor_lab_olcum",
            "params": {"ibare": "trigliserid", "op": ">=", "deger": 0,
                       "alternatif_ibareler": ["tg", "trig", "t.g"]},
            "var_neden": "TG = $deger mg/dL (raporda tespit)",
            "yok_neden": "TG değeri (mg/dL) rapor metninde bulunamadı",
            "kaynak": "rapor_metni"
          }
        ]
      },
      {                                                     # Üst-VEYA: yol-a ∨ yol-b
        "tip": "USTOR",
        "ozet_grup": "Başlama yolu [(a)∨(b)]",
        "yollar": [
          {"grup": "Yol-a — TG>500 [(1)(a)]", "tip": "AND", "alt": [...]},
          {"grup": "Yol-b — TG>200 + KV hastalık [(1)(b)]", "tip": "AND", "alt": [...]}
        ]
      },
      {                                                     # D1 — uzman branş
        "tip": "AND",
        "grup": "Uzman branşı [(1) son cümle]",
        "alt": [
          {"ad": "Uzman branşı (...)", "atom": "doktor_brans_in", "params": {...}}
        ]
      }
    ]
  }
}

Kök node döner: VAR → UYGUN; YOK → UYGUN_DEGIL; KE → KONTROL_EDILEMEDI.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (KontrolRaporu, KontrolSonucu,
                                          SartDurumu, SartSonuc)
from .baglam import Baglam
from .atomlar import atom_kayit, AtomSonuc


# ─────────────────────────────────────────────────────────────────────────
# JSON yükleme
# ─────────────────────────────────────────────────────────────────────────

def kural_yukle(yol: str) -> Dict:
    """JSON kural dosyasını yükler (UTF-8)."""
    with open(yol, 'r', encoding='utf-8') as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────
# Yardımcılar
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
    'MANUEL_KONTROL': KontrolSonucu.MANUEL_KONTROL,
    'SARTLI_UYGUN': KontrolSonucu.SARTLI_UYGUN,
    'ATLANDI': KontrolSonucu.ATLANDI,
}


def _negatif_uygula(durum: SartDurumu, neg: bool) -> SartDurumu:
    """negatif=True ise VAR↔YOK takas. KE/NA değişmez."""
    if not neg:
        return durum
    if durum == SartDurumu.VAR:
        return SartDurumu.YOK
    if durum == SartDurumu.YOK:
        return SartDurumu.VAR
    return durum


def _and_birlestir(durumlar: List[SartDurumu]) -> SartDurumu:
    """AND mantığı: bir tane YOK varsa YOK; KE varsa KE; hepsi VAR → VAR."""
    if not durumlar:
        return SartDurumu.NA
    if any(d == SartDurumu.YOK for d in durumlar):
        return SartDurumu.YOK
    if any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.VAR


def _or_birlestir(durumlar: List[SartDurumu]) -> SartDurumu:
    """OR≥1 mantığı: bir tane VAR yeter; hiç VAR yok ama KE varsa KE; hepsi YOK → YOK."""
    if not durumlar:
        return SartDurumu.NA
    if any(d == SartDurumu.VAR for d in durumlar):
        return SartDurumu.VAR
    if any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.YOK


def _atom_calistir(node: Dict, baglam: Baglam) -> AtomSonuc:
    """JSON ATOM düğümünü çalıştır — atomu kayıttan bul, params ile çağır."""
    atom_adi = node.get('atom')
    if not atom_adi:
        raise ValueError(f"ATOM düğümünde 'atom' alanı yok: {node}")
    fn = atom_kayit.get(atom_adi)
    if fn is None:
        raise KeyError(f"Bilinmeyen atom: '{atom_adi}'. "
                       f"Kayıtlı atomlar: {list(atom_kayit)}")
    params = node.get('params', {}) or {}
    return fn(baglam, **params)


# ─────────────────────────────────────────────────────────────────────────
# Formül ağacı yorumlayıcı
# ─────────────────────────────────────────────────────────────────────────

def _node_calistir(node: Dict, baglam: Baglam,
                    sartlar: List[SartSonuc],
                    grup_override: str = "",
                    veya_override: bool = False
                    ) -> SartDurumu:
    """Bir formül düğümünü değerlendirir.

    Yan etki: `sartlar` listesine atom-seviye SartSonuc kayıtları ekler.
    Dönüş: düğümün boolean durumu (VAR/YOK/KE).
    """
    # ATOM düğümü (içinde 'atom' var)
    if 'atom' in node:
        sonuc = _atom_calistir(node, baglam)
        durum = _negatif_uygula(sonuc.durum, bool(node.get('negatif')))
        # Sadece ana ağaca ekle (erken-çıkış 'kosul' içinde sartlar=None gönderilirse atla)
        if sartlar is not None:
            ad = node.get('ad') or node.get('atom')
            grup = node.get('grup') or grup_override or ''
            veya = bool(node.get('veya_grubu') or veya_override)
            sartlar.append(SartSonuc(
                ad=ad, durum=durum, neden=sonuc.neden,
                kaynak=node.get('kaynak', ''),
                grup=grup, veya_grubu=veya,
                sartli_atom=bool(node.get('sartli_atom'))))
        return durum

    tip = node.get('tip', 'AND').upper()

    # USTOR — alternatif yollar (her yol kendi grubunda; üst-OR ile birleşir)
    if tip == 'USTOR':
        yol_durumlar: List[SartDurumu] = []
        for yol in node.get('yollar', []):
            yol_grup = yol.get('grup', '')
            yol_durum = _node_calistir(
                {'tip': yol.get('tip', 'AND'), 'alt': yol.get('alt', [])},
                baglam, sartlar,
                grup_override=yol_grup,
                veya_override=False)
            yol_durumlar.append(yol_durum)
        # Üst-OR: en az 1 yol VAR ise VAR
        return _or_birlestir(yol_durumlar)

    # AND / OR konteyner
    alt_node_lar = node.get('alt', [])
    grup = node.get('grup') or grup_override or ''
    veya = (tip == 'OR') or bool(node.get('veya_grubu')) or veya_override
    alt_durumlar: List[SartDurumu] = []
    for child in alt_node_lar:
        alt_durumlar.append(_node_calistir(
            child, baglam, sartlar,
            grup_override=grup,
            veya_override=veya if tip == 'OR' else False))
    if tip == 'OR':
        return _or_birlestir(alt_durumlar)
    return _and_birlestir(alt_durumlar)


# ─────────────────────────────────────────────────────────────────────────
# Erken çıkış (on_kontrol)
# ─────────────────────────────────────────────────────────────────────────

def _on_kontrol_calistir(kural: Dict, baglam: Baglam
                          ) -> Optional[KontrolRaporu]:
    """on_kontrol koşullarını sırayla dener; ilk eşleşen erken-çıkış raporu döner."""
    sut_etiketi = kural.get('sut_kurali_etiketi') or kural.get('adi') or ''
    for ek in kural.get('on_kontrol', []):
        kosul_node = ek.get('kosul')
        if not kosul_node:
            continue
        # Geçici sartlar — koşul atomları ana SartSonuc listesini kirletmesin
        gecici_sartlar: List[SartSonuc] = []
        durum = _node_calistir(kosul_node, baglam, gecici_sartlar)
        if durum != SartDurumu.VAR:
            continue
        # Eşleşti — sonuç döndür
        sartlar: List[SartSonuc] = []
        for s_dict in ek.get('sartlar_ekle', []):
            sartlar.append(SartSonuc(
                ad=s_dict.get('ad', ''),
                durum=_DURUM_HARITA.get(s_dict.get('durum', 'KE').upper(),
                                        SartDurumu.KONTROL_EDILEMEDI),
                neden=s_dict.get('neden', ''),
                kaynak=s_dict.get('kaynak', ''),
                grup=s_dict.get('grup', '')))
        return KontrolRaporu(
            sonuc=_SONUC_HARITA.get(ek.get('sonuc', 'KONTROL_EDILEMEDI').upper(),
                                    KontrolSonucu.KONTROL_EDILEMEDI),
            mesaj=ek.get('mesaj', ''),
            sut_kurali=sut_etiketi,
            detaylar={'erken_cikis': ek.get('ad', '')},
            sartlar=sartlar,
            aranan_ibare=ek.get('aranan_ibare'))
    return None


# ─────────────────────────────────────────────────────────────────────────
# Ana giriş noktası
# ─────────────────────────────────────────────────────────────────────────

def degerlendir(kural: Dict, ilac_sonuc: Dict) -> KontrolRaporu:
    """JSON kuralı `ilac_sonuc` reçete satırına uygula → KontrolRaporu.

    Adımlar:
      1. on_kontrol erken-çıkışları (raporsuz, ilgisiz ilaç vs.)
      2. Formül ağacını çalıştır → SartSonuc listesi + kök durum
      3. Kök durumu KontrolSonucu'na çevir, mesaj/detayları doldur
    """
    baglam = Baglam(ilac_sonuc)

    # 1) Erken çıkış
    erken = _on_kontrol_calistir(kural, baglam)
    if erken is not None:
        return erken

    # 2) Formül
    sartlar: List[SartSonuc] = []
    formul = kural.get('formul')
    if not formul:
        raise ValueError(f"Kuralda 'formul' alanı yok: {kural.get('adi')}")
    kok_durum = _node_calistir(formul, baglam, sartlar)

    # 3) Verdict
    sut_etiketi = kural.get('sut_kurali_etiketi') or kural.get('adi') or ''
    aranan = kural.get('aranan_ibare')

    detaylar = {
        'sut_kodu': kural.get('sut_kodu', ''),
        'ilac_adi': baglam.ilac_adi,
        'rapor_kodu': baglam.rapor_kodu,
        'doktor_uzm': baglam.doktor_uzm,
    }

    # YOK gruplarını listele (görsel mesaj için)
    eksik_gruplar = sorted({s.grup for s in sartlar
                            if s.durum == SartDurumu.YOK and s.grup})
    ke_gruplar = sorted({s.grup for s in sartlar
                         if s.durum == SartDurumu.KONTROL_EDILEMEDI and s.grup})

    # Şartlı atomlar: KE + sartli_atom=True (sistem sorgulayamadı, eczacı
    # manuel doğrularsa kesin UYGUN). Genellikle '(bilgi)' grupta yer alır.
    # Bu atomlar varsa KE olan tek atom onlar olabilir → SARTLI_UYGUN.
    sartli_atomlar = [s for s in sartlar
                      if s.sartli_atom
                      and s.durum == SartDurumu.KONTROL_EDILEMEDI]
    # Şartlı olmayan KE atomlar (sistemin gerçekten karar veremediği)
    sartli_olmayan_ke = [s for s in sartlar
                         if s.durum == SartDurumu.KONTROL_EDILEMEDI
                         and not s.sartli_atom]

    if kok_durum == SartDurumu.VAR:
        # Tüm zorunlu şartlar VAR. Şartlı KE varsa SARTLI_UYGUN.
        if sartli_atomlar:
            sartli_adlar = [s.ad for s in sartli_atomlar]
            return KontrolRaporu(
                sonuc=KontrolSonucu.SARTLI_UYGUN,
                mesaj=(f"{kural.get('adi', 'SUT')} ŞARTLI UYGUN — sistem "
                       f"sorgulayamıyor: {', '.join(sartli_adlar)} "
                       f"(eczacı manuel doğrulamalı)"),
                sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
                uyari='Şartlı atom(lar) eczacı tarafından doğrulanmalı',
                aranan_ibare=aranan)
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=f"{kural.get('adi', 'SUT')} şartları sağlanıyor",
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan)
    if kok_durum == SartDurumu.YOK:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f"{kural.get('adi', 'SUT')} şartları sağlanmıyor"
                   + (f" — eksik: {', '.join(eksik_gruplar)}"
                      if eksik_gruplar else '')),
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan)
    # KE: kök ağaç KE döndü. Tek KE neden 'sartli_atom' ise → SARTLI_UYGUN.
    if sartli_atomlar and not sartli_olmayan_ke:
        sartli_adlar = [s.ad for s in sartli_atomlar]
        return KontrolRaporu(
            sonuc=KontrolSonucu.SARTLI_UYGUN,
            mesaj=(f"{kural.get('adi', 'SUT')} ŞARTLI UYGUN — sistem "
                   f"sorgulayamıyor: {', '.join(sartli_adlar)} "
                   f"(eczacı manuel doğrulamalı)"),
            sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
            uyari='Şartlı atom(lar) eczacı tarafından doğrulanmalı',
            aranan_ibare=aranan)
    return KontrolRaporu(
        sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
        mesaj=(f"{kural.get('adi', 'SUT')} ŞÜPHELİ — manuel doğrulanmalı"
               + (f": {', '.join(ke_gruplar)}" if ke_gruplar else '')),
        sut_kurali=sut_etiketi, detaylar=detaylar, sartlar=sartlar,
        uyari='Bazı şartlar metinden tespit edilemedi',
        aranan_ibare=aranan)
