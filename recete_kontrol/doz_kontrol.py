# -*- coding: utf-8 -*-
"""
Doz Karşılaştırma Kontrolü

Reçete dozu ile rapor dozunu (RaporEtkinMadde + serbest açıklama metni)
karşılaştırır. Reçete dozu, rapordaki maks dozu geçemez.

Çalışma kaynakları:
  1) RaporEtkinMadde (yapısal): doz, adet, tekrar, aralık, periyot_id
  2) RaporEkBilgi (serbest metin): "ilaç_adı 3x1" / "günde 2x1" türü ifadeler
  3) Reçete: ReceteIlaclari.RIDoz/RITekrar/RIAralik/RIPeriyotId

Çıktı, base_kontrol.KontrolRaporu nesnesi olarak GUI tarafına döner.
GUI bunu satıra yazıp tabloda "Doz Karş." sütununda gösterir ve Excel
raporunu üretir.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

from .base_kontrol import KontrolSonucu, KontrolRaporu

logger = logging.getLogger(__name__)


# ── Periyot eşlemeleri ────────────────────────────────────────────────
# Medula RIPeriyotId / EtkinMaddePeriyotId değerleri:
#   3 = Günde, 4 = Haftada, 5 = Ayda, 6 = Yılda
PERIYOT_GUN = {3: 1.0, 4: 7.0, 5: 30.0, 6: 365.0}
PERIYOT_AD = {3: "Günde", 4: "Haftada", 5: "Ayda", 6: "Yılda"}


def periyot_id_to_gun(pid) -> float:
    """Periyot kimliğini gün cinsine çevirir; bilinmiyorsa 1 (gün)."""
    try:
        return PERIYOT_GUN.get(int(pid), 1.0)
    except Exception:
        return 1.0


def gunluk_doz_hesapla(doz, tekrar, aralik, periyot_id) -> float:
    """Reçete/rapor doz parametrelerinden günlük tüketim miktarı.

    Formül: (doz × tekrar) / (aralık × periyot_gün)
    Örn: 1 günde 2 x 1     → 1*2 / (1*1)  = 2.0/gün
         7 günde 1 x 2     → 2*1 / (7*1)  = 0.286/gün (haftada 2)
         1 ayda 1 x 1      → 1*1 / (1*30) = 0.033/gün
    """
    try:
        d = float(doz or 0)
        t = float(tekrar or 1) or 1.0
        a = float(aralik or 1) or 1.0
        g = periyot_id_to_gun(periyot_id)
        if a * g == 0:
            return 0.0
        return (d * t) / (a * g)
    except Exception:
        return 0.0


def doz_metin_kisa(doz, tekrar, aralik, periyot_id, tur="") -> str:
    """Ham değerleri okunabilir 'Günde 2 x 1 Adet' biçimine çevirir."""
    try:
        d = float(doz or 0)
        t = int(float(tekrar or 1))
        a = int(float(aralik or 1))
    except Exception:
        d, t, a = 0.0, 1, 1
    p_ad = PERIYOT_AD.get(int(periyot_id) if periyot_id else 3, "Günde")
    d_str = f"{d:g}"
    on = f"{a} {p_ad.lower()}" if a != 1 else p_ad
    parts = [on, f"{t} x {d_str}"]
    if tur:
        parts.append(str(tur))
    return " ".join(parts)


# ── Birim normalizasyonu ─────────────────────────────────────────────
_BIRIM_KANONIK = {
    "adet": "adet", "tablet": "adet", "tb": "adet", "tab": "adet",
    "kapsul": "adet", "kapsül": "adet", "kp": "adet",
    "draje": "adet", "drj": "adet", "flakon": "adet", "fl": "adet",
    "ampul": "adet", "amp": "adet", "şişe": "adet", "sise": "adet",
    "ml": "ml", "cc": "ml",
    "mg": "mg",
    "g": "g", "gr": "g",
    "mcg": "mcg", "µg": "mcg",
    "ünite": "unite", "unite": "unite", "iu": "unite", "u": "unite",
    "damla": "damla", "dmg": "damla",
}


def birim_normalize(birim: str) -> str:
    """Birim metnini kanonik forma getirir (Adet/Tablet → adet, Ünite → unite)."""
    if not birim:
        return ""
    b = str(birim).strip().lower()
    b = b.replace(".", "").replace("(", "").replace(")", "")
    return _BIRIM_KANONIK.get(b, b)


def birim_uyumlu_mu(rec_birim: str, rap_birim: str) -> bool:
    """İki birim aynı ölçü tipinde mi? Boşsa toleranslı (uyumlu kabul)."""
    a = birim_normalize(rec_birim)
    b = birim_normalize(rap_birim)
    if not a or not b:
        return True
    return a == b


# ── Etken madde eşleşmesi ────────────────────────────────────────────
def _norm(s: str) -> str:
    if not s:
        return ""
    # x ↔ ks yazım toleransı: reçete etken adı "EDOXABAN" (x), rapor metni
    # "EDOKSABAN" (ks) yazmış olabilir. Her iki taraf da _norm'dan geçtiği
    # için X→KS dönüşümü simetriktir (yalnız temsili birleştirir).
    return (str(s).upper()
            .replace("İ", "I").replace("Ş", "S").replace("Ç", "C")
            .replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O")
            .replace("X", "KS")
            .strip())


def etken_madde_eslestir(rec_etkin: str, rec_atc: str,
                          rapor_etken_listesi: List[Dict]) -> Optional[Dict]:
    """Reçetedeki ilacın etken maddesini rapor etkin madde listesinde
    eşleştirir.

    Strateji:
      1) Etken adı tam (normalize) eşleşme
      2) Etken adının kelimelerinden biri ad içinde geçiyor mu?
      3) Tek aday varsa onu döndür (rapor tek ilaçlık)
    """
    if not rapor_etken_listesi:
        return None
    if len(rapor_etken_listesi) == 1:
        return rapor_etken_listesi[0]
    rec_n = _norm(rec_etkin)
    if rec_n:
        # 1) Tam eşleşme
        for em in rapor_etken_listesi:
            if _norm(em.get("etkin_ad")) == rec_n:
                return em
        # 2) Kelime bazlı (uzun olan kazanır)
        rec_kelimeler = [k for k in rec_n.split() if len(k) >= 4]
        en_iyi, en_uzun = None, 0
        for em in rapor_etken_listesi:
            ea = _norm(em.get("etkin_ad"))
            if not ea:
                continue
            for k in rec_kelimeler:
                if k in ea and len(k) > en_uzun:
                    en_iyi, en_uzun = em, len(k)
        if en_iyi:
            return en_iyi
    return None


# ── Serbest metin doz parser (RaporEkBilgi açıklamasından) ───────────
_DOZ_RE = re.compile(
    r"(?:(?P<periyot>g[uü]nde|haftada|ayda|y[ıi]lda)\s+)?"
    r"(?P<tekrar>\d+)\s*[xX×*]\s*(?P<doz>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_PERIYOT_TXT_ID = {
    "gunde": 3, "günde": 3,
    "haftada": 4,
    "ayda": 5,
    "yilda": 6, "yılda": 6,
}


def parse_serbest_metin(metin: str, ilac_adi: str = "",
                         etkin: str = "") -> Optional[Dict]:
    """Açıklama metninden bağlamlı doz çıkar.
    'CRESTOR günde 1x1' → {periyot_id:3, tekrar:1, doz:1, ...}
    """
    if not metin:
        return None
    metin_n = str(metin)

    # Anahtar bul (ilaç adının ilk kelimesi veya etken)
    aday_anahtarlar = []
    if ilac_adi:
        ilk = ilac_adi.split()[0] if ilac_adi.split() else ""
        if ilk and len(ilk) >= 3:
            aday_anahtarlar.append(ilk)
    if etkin:
        for parca in re.split(r"[\s+,/]+", etkin):
            if len(parca) >= 4:
                aday_anahtarlar.append(parca)

    # x ↔ ks yazım toleransı (EDOXABAN ↔ EDOKSABAN): her çıpa için 'x'→'ks'
    # ve 'ks'→'x' varyantını da aday yap. Çıpa eşleşmesini etkiler; doz
    # regex'i orijinal pencere üzerinde çalıştığı için "1x1" bozulmaz.
    genis = []
    for ah in aday_anahtarlar:
        genis.append(ah)
        al = ah.lower()
        if "x" in al:
            genis.append(al.replace("x", "ks"))
        if "ks" in al:
            genis.append(al.replace("ks", "x"))
    aday_anahtarlar = genis

    metin_low = metin_n.lower()
    pos = -1
    bulunan_anahtar = ""
    for ah in aday_anahtarlar:
        ah_low = ah.lower()
        p = metin_low.find(ah_low)
        if p >= 0:
            pos = p
            bulunan_anahtar = ah
            break

    # Anahtar yoksa metin tek doz ifadesi içeriyorsa onu kabul et
    if pos < 0:
        all_matches = list(_DOZ_RE.finditer(metin_n))
        if len(all_matches) != 1:
            return None
        m = all_matches[0]
    else:
        # Anahtar etrafında 80 karakter pencere
        bas = max(0, pos)
        son = min(len(metin_n), pos + len(bulunan_anahtar) + 80)
        pencere = metin_n[bas:son]
        m = _DOZ_RE.search(pencere)
        if not m:
            return None

    tekrar = int(m.group("tekrar"))
    doz = float(m.group("doz").replace(",", "."))
    periyot_txt = (m.group("periyot") or "günde").lower()
    periyot_id = _PERIYOT_TXT_ID.get(periyot_txt, 3)

    return {
        "doz": doz,
        "tekrar": tekrar,
        "aralik": 1,
        "periyot_id": periyot_id,
        "tur": "",
        "kaynak": "ek_bilgi",
        "bulunan_metin": m.group(0),
        "anahtar": bulunan_anahtar,
    }


# ── Ana kontrol fonksiyonu ───────────────────────────────────────────
def kontrol_doz(ilac_sonuc: Dict) -> KontrolRaporu:
    """Reçete dozunun rapor dozunu geçip geçmediğini değerlendirir.

    Beklenen ilac_sonuc anahtarları:
        ilac_adi:        str
        etkin_madde:     str
        atc:             str
        rec_doz_raw:     {'doz','tekrar','aralik','periyot_id'}
        rap_doz_listesi: [{'etkin_ad','etkin_id','doz','adet','tekrar',
                           'aralik','periyot_id'}, ...]
        rapor_aciklamalari: [str, ...]   (RaporEkBilgi)
        rapor_kodu:      str (bağlam için)
        raporlu:         bool — rapor_ana_id var mı? (Raporsuz ilaç doz
                          kontrolüne girmez; rapor dozu yoksa
                          karşılaştırma anlamsız.)

    Dönüş: KontrolRaporu — UYGUN / UYGUN_DEGIL / KONTROL_EDILEMEDI / ATLANDI
    """
    ilac_adi = ilac_sonuc.get("ilac_adi") or ""
    etkin = ilac_sonuc.get("etkin_madde") or ""
    rec_raw = ilac_sonuc.get("rec_doz_raw") or {}
    rap_listesi = ilac_sonuc.get("rap_doz_listesi") or []
    rap_acks = ilac_sonuc.get("rapor_aciklamalari") or []

    # Raporlu mu? Açıkça verilmişse onu kullan; verilmemişse rapor verisi
    # var mı diye bak.
    raporlu = ilac_sonuc.get("raporlu")
    if raporlu is None:
        raporlu = bool(rap_listesi) or bool(rap_acks)

    sut_kurali = "Doz: reçete ≤ rapor maks doz"

    # ── 0) Raporsuz ilaç → kontrol etme ──
    # Rapor yoksa karşılaştıracak rapor dozu da yok; doz kontrolü kapsam dışı.
    if not raporlu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj="Raporsuz ilaç — doz kontrolü kapsam dışı",
            sut_kurali=sut_kurali,
            detaylar={"sebep": "raporsuz"},
        )

    # ── 1) Reçete günlük dozu ──
    rec_doz = rec_raw.get("doz")
    rec_tekrar = rec_raw.get("tekrar")
    rec_aralik = rec_raw.get("aralik")
    rec_pid = rec_raw.get("periyot_id")
    if not rec_doz or float(rec_doz or 0) <= 0:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj="Reçete dozu okunamadı",
            sut_kurali=sut_kurali,
            aranan_ibare="reçete günlük doz",
            bulunan_metin="",
            detaylar={"sebep": "rec_doz_eksik"},
        )
    rec_gunluk = gunluk_doz_hesapla(rec_doz, rec_tekrar, rec_aralik, rec_pid)
    rec_metin = doz_metin_kisa(rec_doz, rec_tekrar, rec_aralik, rec_pid, "")

    detaylar = {
        "rec_gunluk": round(rec_gunluk, 4),
        "rec_metin": rec_metin,
        "rec_raw": dict(rec_raw),
        "kaynak": "yok",
        "esleme": "",
        "rap_gunluk": None,
        "rap_metin": "",
    }

    # ── 3) RaporEtkinMadde'den eşleşen kalemi bul ──
    eslesen = etken_madde_eslestir(etkin, ilac_sonuc.get("atc") or "",
                                     rap_listesi)
    rap_kaynak = ""
    rap_gunluk = 0.0
    rap_metin = ""
    rap_birim = ""

    if eslesen:
        rd = float(eslesen.get("doz") or 0)
        ra = float(eslesen.get("adet") or 0)
        rt = float(eslesen.get("tekrar") or 1) or 1.0
        rar = float(eslesen.get("aralik") or 1) or 1.0
        rpid = eslesen.get("periyot_id")
        # Bir alımda alınan miktar: adet (tablet sayısı) genelde reçete
        # birimiyle uyumlu; doz (mg/ml) farklı birim olabilir.
        # Adet > 0 ise onu kullan (birim eşleşmesi için), yoksa doz.
        kullanilan = ra if ra > 0 else rd
        rap_gunluk = (kullanilan * rt) / (rar * periyot_id_to_gun(rpid))
        rap_metin = doz_metin_kisa(kullanilan, rt, rar, rpid, "")
        rap_kaynak = "RaporEtkinMadde"
        # Birim: Adet kullanıldıysa adet; doz kullanıldıysa belirsiz
        rap_birim = "adet" if ra > 0 else ""
        detaylar["esleme"] = eslesen.get("etkin_ad") or ""

    # ── 4) Yapısal değer 0 ya da eşleşme yoksa → açıklama metninden parse ──
    if not eslesen or rap_gunluk <= 0:
        for ack in rap_acks:
            ps = parse_serbest_metin(ack, ilac_adi=ilac_adi, etkin=etkin)
            if ps:
                rap_gunluk = gunluk_doz_hesapla(
                    ps["doz"], ps["tekrar"],
                    ps["aralik"], ps["periyot_id"])
                rap_metin = doz_metin_kisa(
                    ps["doz"], ps["tekrar"],
                    ps["aralik"], ps["periyot_id"], "")
                rap_kaynak = "RaporEkBilgi (parse)"
                detaylar["bulunan_anahtar"] = ps.get("anahtar", "")
                detaylar["bulunan_metin"] = ps.get("bulunan_metin", "")
                break

    detaylar["kaynak"] = rap_kaynak or "yok"
    detaylar["rap_gunluk"] = round(rap_gunluk, 4) if rap_gunluk else None
    detaylar["rap_metin"] = rap_metin

    # ── 5) Rapor dozu çıkarılamadı → ŞÜPHELİ ──
    if rap_gunluk <= 0:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=("Rapor dozu çıkarılamadı "
                   "(yapısal alan boş, açıklamada eşleşme yok)"),
            sut_kurali=sut_kurali,
            aranan_ibare=f"{etkin or ilac_adi} dozu",
            bulunan_metin="",
            detaylar=detaylar,
        )

    # ── 6) Karşılaştırma ──
    # Küçük bir tolerans: ondalık yuvarlamadan kaynaklı 0.0001 gibi farklara
    # takılmamak için rec ≤ rap × 1.001
    tolerans = 1.001
    if rec_gunluk <= rap_gunluk * tolerans:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN,
            mesaj=(f"Reçete {rec_gunluk:g}/gün ≤ rapor {rap_gunluk:g}/gün "
                   f"({rap_kaynak})"),
            sut_kurali=sut_kurali,
            aranan_ibare=f"{etkin or ilac_adi} günlük doz",
            bulunan_metin=rap_metin,
            detaylar=detaylar,
        )
    else:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=(f"DOZ AŞIMI: reçete {rec_gunluk:g}/gün > "
                   f"rapor {rap_gunluk:g}/gün ({rap_kaynak})"),
            sut_kurali=sut_kurali,
            aranan_ibare=f"{etkin or ilac_adi} günlük doz",
            bulunan_metin=rap_metin,
            uyari="Rapor dozu aşılmış — manuel kontrol önerilir",
            detaylar=detaylar,
        )
