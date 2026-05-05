"""
Aylık İnceleme & Filtreleme Tablosu (Botanik EOS)

Kullanıcının manuel inceleme akışı için tek tablo + çoklu filtre + boyama.
Her satır = bir reçete-ilaç kombinasyonu.

GÜVENLİK: Yalnızca SELECT — BotanikDB.sorgu_calistir güvenlik filtresi kullanılır.
Hiçbir INSERT/UPDATE/DELETE yapılmaz.

Akış:
1. Yıl-Ay seç → Sorgula → tüm aylık reçete-ilaç satırları tabloya gelir (BEYAZ)
2. Üstteki sütun arama kutuları ve sağdaki hızlı filtre butonları ile filtre uygula
3. Filtreden geçen satırları "Filtreliyi Yeşile Boya" ile toplu boya
4. Renk filtre (Yeşil/Sarı/Kırmızı/Beyaz/Turuncu checkbox'ları) ile gösterimi daralt
5. Çember daraldıkça → kalan satırlar gerçek manuel kontrol gerektirenler
6. Excel export ile renkleri koruyarak çıktı al

State: aylik_inceleme_state.json — {dönem: {ri_id: renk}} mapping'i.
"""

import json
import logging
import os
import re
import threading
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# RENK SİSTEMİ
# ═══════════════════════════════════════════════════════════════════════
RENK_BEYAZ = "beyaz"
RENK_YESIL = "yesil"
RENK_SARI = "sari"
RENK_TURUNCU = "turuncu"
RENK_KIRMIZI = "kirmizi"
RENK_GRI = "gri"          # Kontrol gerekmez — bu ilacı dışlama listesine ekler

RENK_BG = {
    RENK_BEYAZ:   "#FFFFFF",
    RENK_YESIL:   "#C8E6C9",
    RENK_SARI:    "#FFF9C4",
    RENK_TURUNCU: "#FFE0B2",
    RENK_KIRMIZI: "#FFCDD2",
    RENK_GRI:     "#E0E0E0",
}
RENK_FG = {
    RENK_BEYAZ:   "#212121",
    RENK_YESIL:   "#1B5E20",
    RENK_SARI:    "#827717",
    RENK_TURUNCU: "#E65100",
    RENK_KIRMIZI: "#B71C1C",
    RENK_GRI:     "#616161",
}
RENK_ETIKET = {
    RENK_BEYAZ:   "Beklemede",
    RENK_YESIL:   "Uygun (Elendi)",
    RENK_SARI:    "Manuel Kontrol",
    RENK_TURUNCU: "Şüpheli",
    RENK_KIRMIZI: "Uygunsuz",
    RENK_GRI:     "Kontrol Gerekmez (dışla)",
}


# ═══════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════
UYARI_KODU_REGEX = re.compile(r"\((\d{3,7})\)")


def uyari_kodlarini_ayikla(metin: str) -> list:
    if not metin:
        return []
    return list(dict.fromkeys(UYARI_KODU_REGEX.findall(metin)))


def _tarihi_parse(d):
    """DB'den gelen tarih (datetime/date/str) → date veya None."""
    if not d:
        return None
    if hasattr(d, "year"):
        return d
    # String — "YYYY-MM-DD" veya "YYYY-MM-DD HH:MM:SS"
    try:
        from datetime import datetime
        s = str(d)[:10]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def tarih_format(d, fmt="%d.%m.%Y") -> str:
    """DB'den gelen tarihi (datetime/date/str) güvenli şekilde formatla."""
    if not d:
        return ""
    if hasattr(d, "strftime"):
        try:
            return d.strftime(fmt)
        except Exception:
            pass
    # String fallback
    s = str(d)
    if len(s) >= 10:
        # "YYYY-MM-DD" → "DD.MM.YYYY" varsayılan
        if fmt == "%d.%m.%Y":
            try:
                return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
            except Exception:
                return s[:10]
        elif fmt == "%Y-%m":
            return s[:7]
        return s[:10]
    return s


def yas_hesapla(dogum_tarihi) -> str:
    dt = _tarihi_parse(dogum_tarihi)
    if not dt:
        return ""
    try:
        bugun = date.today()
        yas = bugun.year - dt.year - (
            (bugun.month, bugun.day) < (dt.month, dt.day)
        )
        return str(yas)
    except Exception:
        return ""


def cinsiyet_etiket(c) -> str:
    if not c:
        return ""
    s = str(c).strip().upper()
    return {"E": "Erkek", "K": "Kadın", "M": "Erkek", "F": "Kadın"}.get(s, s)


_PERIYOT_AD = {
    3: "günde",
    4: "haftada",
    5: "ayda",
    6: "yılda",
    1: "saatte",
    2: "saatte",
}


def _sayi_kisa(d) -> str:
    """Decimal/float'ı kısa formatta göster — 1.00 → 1, 0.50 → 0.5"""
    if d is None or d == "":
        return ""
    try:
        f = float(d)
        if f == int(f):
            return str(int(f))
        return f"{f:g}"
    except Exception:
        return str(d)


def doz_metin(aralik, periyot_id, tekrar, doz) -> str:
    """Reçete dozunu '<aralık> <periyot> <tekrar> x <doz>' formatında göster.

    Örnek:
      aralik=1, periyot=3 (Günde), tekrar=2, doz=1   → '1 günde 2 x 1'
      aralik=7, periyot=3 (Günde), tekrar=1, doz=2   → '7 günde 1 x 2'
      aralik=1, periyot=5 (Ayda),  tekrar=1, doz=1   → '1 ayda 1 x 1'
    """
    aralik_s = _sayi_kisa(aralik) or "1"
    tekrar_s = _sayi_kisa(tekrar) or "1"
    doz_s = _sayi_kisa(doz) or "1"
    try:
        pid = int(periyot_id) if periyot_id is not None else 3
    except Exception:
        pid = 3
    periyot_ad = _PERIYOT_AD.get(pid, "günde")
    return f"{aralik_s} {periyot_ad} {tekrar_s} x {doz_s}"


# ═══════════════════════════════════════════════════════════════════════
# SUT KATEGORİLERİ
# ═══════════════════════════════════════════════════════════════════════
def sut_madde_tespit(ilac_adi: str, etkin_madde: str, rapor_kodu: str) -> str:
    """sut_kontrolleri'nden SUT maddesini tespit et (4.2.x formatında)."""
    try:
        from recete_kontrol.sut_kontrolleri import (
            sut_kategorisi_tespit_et, KATEGORI_ISIMLERI,
        )
        kategori = sut_kategorisi_tespit_et({
            "ilac_adi": ilac_adi or "",
            "etkin_madde": etkin_madde or "",
            "rapor_kodu": rapor_kodu or "",
        })
        if kategori:
            return KATEGORI_ISIMLERI.get(kategori, kategori)
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════════════════
# SÜTUN TANIMLARI (26 sütun)
# ═══════════════════════════════════════════════════════════════════════
SUTUNLAR = [
    # (kod, başlık, genişlik, tooltip)
    ("secim",      "✓",            32,  "Seçim — tıklayınca işaretle/kaldır"),
    ("grup",       "Grup",         45,  "A/B/C/GK/CK"),
    ("donem",      "Dönem",        70,  "Yıl-Ay"),
    ("rec_tar",    "Reç.Tarih",    80,  "Reçete tarihi"),
    ("rec_no",     "Reçete No",    80,  "E-reçete numarası"),
    ("rec_tip",    "Reç.Türü",     75,  "Reçete türü (Normal/Kırmızı/Yeşil/Mor)"),
    ("rec_alttur", "Reç.Alt Türü", 95,  "Reçete alt türü (Ayaktan/Yatan/A/B/C/GK/Kan)"),
    ("hasta",      "Hasta Adı",    140, "Hasta adı"),
    ("tc",         "TC No",        95,  "Hasta TC kimlik no"),
    ("yas",        "Yaş",          35,  "Hasta yaşı"),
    ("cins",       "Cin.",         38,  "Cinsiyet"),
    ("hasta_tip",  "Hasta Tipi",   90,  "Yeşil Kart/SSK/Emekli/Çalışan"),
    ("doktor",     "Doktor",       130, "Doktor adı"),
    ("brans",      "Branş",        110, "Doktor branşı"),
    ("ilac",       "İlaç",         180, "İlaç adı"),
    ("etkin",      "Etken Madde",  130, "Etken madde"),
    ("atc",        "ATC",          70,  "ATC kodu"),
    ("esdeger",    "Eşdeğer",      70,  "Eşdeğer grubu"),
    ("kutu",       "Kutu",         42,  "Kutu sayısı (kaç kutu verildiği)"),
    ("sut",        "SUT Maddesi",  130, "SUT 4.2.x kategorisi"),
    ("rap_kod",    "Rapor Kod",    65,  "Rapor kodu"),
    ("rec_doz",    "Reçete Doz",   90,  "Reçete dozu"),
    ("rap_doz",    "Rapor Doz",    80,  "Rapor dozu"),
    ("msj",        "Msj",          35,  "İlaç mesaj durumu"),
    ("uyari",      "Uyarı Kod",    150, "Bu ilaç için reçeteye girilen uyarı kodları (ReceteTeshis)"),
    ("medula_msj", "Medula Msj",   220, "Medula provizyon yanıt metni (RxUyarilari)"),
    ("rec_tesh",   "Reç.Teşhis",   150, "Reçete teşhisleri"),
    ("rap_tesh",   "Rap.Teşhis",   150, "Rapor teşhisleri"),
    ("rec_ack",    "Reç.Açk",      180, "Reçete açıklamaları"),
    ("rap_ack",    "Rap.Açk",      180, "Rapor açıklamaları"),
    ("verdict",    "SONUÇ",        130,
     "STATİN KONTROL butonu çalıştırıldığında doldurulur: "
     "UYGUN / UYGUN DEĞİL / ŞÜPHELİ / ATLANDI"),
]
SUTUN_KOD = [s[0] for s in SUTUNLAR]


# ═══════════════════════════════════════════════════════════════════════
# HIZLI FİLTRE TANIMLARI
# ═══════════════════════════════════════════════════════════════════════
# Her filtre: (etiket, fonksiyon(satir) -> bool, açıklama)
def _f_raporlu(s: dict) -> bool:
    return (s.get("msj") or "").strip().lower() == "var"


def _f_raporsuz(s: dict) -> bool:
    return (s.get("msj") or "").strip().lower() == "yok"


def _f_mesajsiz(s: dict) -> bool:
    """Raporsuz ilaç mesajı yoktur — Mesajsız raporsuz ile aynıdır."""
    return (s.get("msj") or "").strip().lower() == "yok"


def _f_doz_uygun(s: dict) -> bool:
    rd = s.get("rec_doz_sayi") or 0
    rpd = s.get("rap_doz_sayi") or 0
    if not rpd:
        return False
    return rd > 0 and rd <= rpd


def _f_klasik_oad(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    klasikler = ["METFORMIN", "GLIKLAZID", "GLIMEPIRID", "GLIBENKLAMID",
                 "GLIPIZID", "REPAGLINID", "NATEGLINID", "PIOGLITAZON",
                 "AKARBOZ"]
    ticari = ["GLIFOR", "GLUKOFEN", "DIAFORMIN", "DIAMICRON", "AMARYL",
              "GLIFIX", "GLUCOBAY", "GLIMAX", "ACTOS", "GLIBEDAL",
              "NOVONORM", "STARLIX"]
    return any(k in et for k in klasikler) or any(t in ad for t in ticari)


def _f_dpp4_sglt2_glp1(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    sinif = ["SITAGLIPTIN", "VILDAGLIPTIN", "SAKSAGLIPTIN", "LINAGLIPTIN",
             "ALOGLIPTIN", "EMPAGLIFLOZIN", "DAPAGLIFLOZIN", "KANAGLIFLOZIN",
             "ERTUGLIFLOZIN", "LIRAGLUTID", "SEMAGLUTID", "DULAGLUTID"]
    ticari = ["JANUVIA", "GALVUS", "ONGLYZA", "TRAJENTA", "NESINA",
              "JARDIANCE", "FORZIGA", "INVOKANA", "JANUMET", "GALVUSMET",
              "VICTOZA", "OZEMPIC", "TRULICITY"]
    return any(k in et for k in sinif) or any(t in ad for t in ticari)


def _f_klopidogrel(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("KLOPIDOGREL" in et or "PRASUGREL" in et or "TIKAGRELOR" in et
            or any(t in ad for t in ["PLAVIX", "PLANOR", "KARUM", "EFFIENT", "BRILINTA"]))


def _f_yoak(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("RIVAROKSABAN" in et or "APIKSABAN" in et or "EDOKSABAN" in et
            or "DABIGATRAN" in et
            or any(t in ad for t in ["XARELTO", "ELIQUIS", "LIXIANA", "PRADAXA"]))


def _f_statin(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("STATIN" in et or "ATORVASTATIN" in et or "ROSUVASTATIN" in et
            or "SIMVASTATIN" in et or "PRAVASTATIN" in et or "FLUVASTATIN" in et
            or any(t in ad for t in ["LIPITOR", "CRESTOR", "ATOR", "ULTROX",
                                       "ZOCOR", "LIPVAS", "ALVASTIN"]))


def _f_noropatik(s: dict) -> bool:
    """Nöropatik ağrı uyarı kodu içeren reçete."""
    uy = (s.get("uyari") or "")
    return ("noropatik" in uy.lower() or "nöropatik" in uy.lower()
            or _f_gabapentinoid(s))


def _f_gabapentinoid(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("GABAPENTIN" in et or "PREGABALIN" in et
            or any(t in ad for t in ["NEURONTIN", "LYRICA", "NERUDA",
                                       "GABAGAMMA", "PREGALIN", "PREGABEX"]))


def _f_uriner_antibiyotik(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("FOSFOMISIN" in et or "NITROFURANTOIN" in et
            or any(t in ad for t in ["MONUROL", "UROMSIN"]))


def _f_immunsupresif(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("TAKROLIMUS" in et or "MIKOFENOLAT" in et or "SIROLIMUS" in et
            or "EVEROLIMUS" in et or "SIKLOSPORIN" in et or "AZATIYOPRIN" in et
            or any(t in ad for t in ["ADVAGRAF", "PROGRAF", "MYFORTIC",
                                       "CELLCEPT", "RAPAMUNE", "CERTICAN",
                                       "SANDIMMUN", "IMURAN"]))


def _f_ms_dmt(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return ("DIMETIL FUMARAT" in et or "INTERFERON BETA" in et or "FINGOLIMOD" in et
            or "GLATIRAMER" in et or "TERIFLUNOMID" in et or "OKRELIZUMAB" in et
            or any(t in ad for t in ["TENIPRA", "TECFIDERA", "AVONEX", "REBIF",
                                       "GILENYA", "AUBAGIO", "OCREVUS"]))


def _f_solunum(s: dict) -> bool:
    et = (s.get("etkin") or "").upper()
    ad = (s.get("ilac") or "").upper()
    return any(k in et for k in ["FORMOTEROL", "SALMETEROL", "VILANTEROL",
                                    "INDAKATEROL", "TIOTROPIUM", "GLIKOPIRONYUM",
                                    "BUDESONID", "BUDEZONID", "FLUTIKAZON",
                                    "MOMETAZON", "MONTELUKAST"]) or \
           any(t in ad for t in ["SERETIDE", "SYMBICORT", "FOSTER", "RELVAR",
                                   "TRELEGY", "TRIMBOW", "BREZTRI", "SPIRIVA",
                                   "ANORO", "ULTIBRO", "SINGULAIR"])


# Hızlı filtre listesi (sıralı buton düzeni)
HIZLI_FILTRELER = [
    ("● Raporlu ilaçlar",         _f_raporlu),
    ("○ Raporsuz ilaçlar",        _f_raporsuz),
    ("Mesajsız",                  _f_mesajsiz),
    ("Doz Uygun (≤Rapor)",        _f_doz_uygun),
    ("Klasik OAD",                _f_klasik_oad),
    ("DPP-4/SGLT-2/GLP-1",        _f_dpp4_sglt2_glp1),
    ("Klopidogrel/Antiplatelet",  _f_klopidogrel),
    ("YOAK",                      _f_yoak),
    ("Statin",                    _f_statin),
    ("Gabapentinoid/Nöropatik",   _f_noropatik),
    ("Üriner Antibiyotik",        _f_uriner_antibiyotik),
    ("İmmünsüpresif",             _f_immunsupresif),
    ("MS DMT",                    _f_ms_dmt),
    ("Solunum (LABA/ICS/LTRA)",   _f_solunum),
]


# ═══════════════════════════════════════════════════════════════════════
# TOOLTIP HELPER (1 sn gecikmeli hover ipucu)
# ═══════════════════════════════════════════════════════════════════════
class _Tooltip:
    """Widget üzerinde 1 saniye bekleyince çıkan açıklama balonu."""

    def __init__(self, widget, text: str, delay_ms: int = 1000):
        self.widget = widget
        self.text = text
        self.delay = delay_ms
        self._tip = None
        self._after_id = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _leave(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except Exception:
            return
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        try:
            self._tip.attributes("-topmost", True)
        except Exception:
            pass
        tk.Label(self._tip, text=self.text,
                  bg="#FFFDE7", fg="#37474F",
                  relief="solid", bd=1, padx=8, pady=4,
                  font=("Segoe UI", 9), wraplength=340, justify="left"
                  ).pack()


def _tt(widget, text: str):
    """Kısa kısayol — widget'a tooltip ekler ve widget'ı geri döndürür."""
    _Tooltip(widget, text)
    return widget


# ═══════════════════════════════════════════════════════════════════════
# ANA SINIF
# ═══════════════════════════════════════════════════════════════════════
class AylikReceteSorguGUI:
    """Aylık reçete-ilaç inceleme & filtreleme tablosu."""

    STATE_DOSYASI = "aylik_inceleme_state.json"
    SUTUN_AYAR_DOSYASI = "aylik_inceleme_sutun_ayarlari.json"

    def __init__(self, root: tk.Tk, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("📋  AYLIK İNCELEME & FİLTRELEME  ·  BOTANİK EOS  ·  SALT OKUNUR")
        # Geçici varsayılan boyut (zoomed çalışmazsa fallback)
        self.root.geometry("1700x920")
        # Pencere açılır açılmaz tam ekrana (maximized) gelsin
        try:
            # Windows ve çoğu modern Tk için
            self.root.state("zoomed")
        except tk.TclError:
            try:
                # Linux varyantı
                self.root.attributes("-zoomed", True)
            except Exception:
                # Son fallback: ekran boyutuna oturt
                try:
                    sw = self.root.winfo_screenwidth()
                    sh = self.root.winfo_screenheight()
                    self.root.geometry(f"{sw}x{sh}+0+0")
                except Exception:
                    pass
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        self.db: BotanikDB = None

        # Lookup cache
        self._lookup_kapsam = {}
        self._lookup_brans = {}
        self._lookup_etkin_madde = {}
        self._lookup_alttur = {}
        self._lookup_renk = {}
        self._lookup_provizyon = {}
        self._lookup_rapor_kodu = {}
        self._lookup_kurum = {}

        # Veri
        self.tum_satirlar = []        # tüm sorgu sonucu (filtresiz)
        self.gosterilen_iids = set()  # şu anda görünen iid'ler
        self.satir_indeks = {}        # {iid: satir_dict}
        self.satir_renkleri = {}      # {iid: renk}
        self.secili_iidler = set()    # checkbox ile seçilmiş satırlar

        # Filtre durumu
        self.aktif_sutun_filtre = {}  # {sutun_kod: arama_metni}
        self.aktif_deger_filtre = {}  # {sutun_kod: set(secili_degerler)}  Excel-benzeri
        self.aktif_metin_filtre = {}  # {sutun_kod: (op, deger)}  Başlar/Biter/İçerir vb.
        self.aktif_renk_filtre = {RENK_BEYAZ, RENK_YESIL, RENK_SARI,
                                    RENK_TURUNCU, RENK_KIRMIZI, RENK_GRI}
        # "Boş satırları gizle" — uyarı kodu / mesaj / rapor kodu olmayan
        # satırları liste dışı tutar (kontrol gerektirmeyen temiz satırlar).
        # Varsayılan AÇIK: kullanıcı kontrol gerektirebilecek satırlara
        # odaklansın diye temiz satırlar baştan elenir.
        self.gizle_bos_satirlar = tk.BooleanVar(value=True)

        # Detaylı filtre ayarları (⚙ butonundan açılan pencere ile yönetilir)
        try:
            import aylik_filtre_ayarlari as fa
            self._filtre_ayarlari_aktif = fa.ayarlari_yukle()
        except Exception:
            self._filtre_ayarlari_aktif = None

        # Aktif dönem (yıl-ay) — state için anahtar
        self.aktif_donem = ""

        # Sütun görünüm ayarı — varsayılan tüm sütunlar açık
        self.sutun_gosterim = {kod: True for kod in SUTUN_KOD}
        self._sutun_ayarlarini_yukle()

        # Sıralama durumu (Excel benzeri tıkla-sırala)
        self._siralama_kolonu = None
        self._siralama_yonu = None  # "asc" | "desc"

        # Arayüz
        self._arayuz_olustur()

        # Async başlat
        self.root.after(100, self._db_baglan_async)

    # ------------------------------------------------------------------ DB
    def _db_baglan_async(self):
        threading.Thread(target=self._db_baglan_ve_lookup, daemon=True).start()

    def _db_baglan_ve_lookup(self):
        try:
            self.db = BotanikDB(production=True)
            if not self.db.baglan():
                raise RuntimeError("Botanik veritabanına bağlanılamadı")
            self.root.after(0, self._durum_yaz, "DB bağlandı (salt-okunur). Lookup yükleniyor…")
            self._lookup_yukle()
            self.root.after(0, self._lookup_bitti)
        except Exception as e:
            logger.error("DB bağlantı hatası: %s", e)
            self.root.after(0, self._durum_yaz, f"DB hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror(
                "Bağlantı Hatası",
                f"Botanik EOS veritabanına bağlanılamadı:\n{e}"))

    def _lookup_yukle(self):
        if not self.db:
            return
        try:
            for r in self.db.sorgu_calistir("SELECT KapsamId, KapsamAdi FROM Kapsam"):
                self._lookup_kapsam[r["KapsamId"]] = r["KapsamAdi"]
            for r in self.db.sorgu_calistir(
                "SELECT BransId, BransAdi FROM Brans WHERE BransSilme=0"):
                self._lookup_brans[r["BransId"]] = r["BransAdi"]
            for r in self.db.sorgu_calistir(
                "SELECT EtkinMaddeId, EtkinMaddeSGKKodu, EtkinMaddeAdi "
                "FROM EtkinMadde WHERE EtkinMaddeSilme=0"):
                self._lookup_etkin_madde[r["EtkinMaddeId"]] = (
                    r["EtkinMaddeSGKKodu"] or "", r["EtkinMaddeAdi"] or "")
            for r in self.db.sorgu_calistir(
                "SELECT ReceteAltTuruId, ReceteAltTuruAdi FROM ReceteAltTuru "
                "WHERE ReceteAltTuruSilme=0"):
                self._lookup_alttur[r["ReceteAltTuruId"]] = r["ReceteAltTuruAdi"]
            for r in self.db.sorgu_calistir(
                "SELECT ReceteRenkId, ReceteRenkAdi FROM ReceteRenk "
                "WHERE ReceteRenkSilme=0"):
                self._lookup_renk[r["ReceteRenkId"]] = r["ReceteRenkAdi"]
            # Kırmızı/Yeşil/Mor reçete tipi ID setleri (renkli reçete kontrolü
            # için her zaman gelmeli — boş satır filtresinden muaf)
            self._renkli_recete_idler = {
                rid: ad for rid, ad in self._lookup_renk.items()
                if ad and ad.strip().lower() in ("kırmızı", "kirmizi",
                                                    "yeşil", "yesil", "mor")
            }
            for r in self.db.sorgu_calistir(
                "SELECT ProvizyonTipId, ProvizyonTipAdi FROM ProvizyonTipi "
                "WHERE ProvizyonTipSilme=0"):
                self._lookup_provizyon[r["ProvizyonTipId"]] = r["ProvizyonTipAdi"]
            for r in self.db.sorgu_calistir(
                "SELECT RaporKodId, RaporKodu, RaporKodAciklama FROM RaporKodlari "
                "WHERE RaporKodSilme=0"):
                self._lookup_rapor_kodu[r["RaporKodId"]] = (
                    r["RaporKodu"] or "", r["RaporKodAciklama"] or "")
            for r in self.db.sorgu_calistir(
                "SELECT KurumId, KurumAdi FROM Kurum WHERE KurumSilme=0"):
                self._lookup_kurum[r["KurumId"]] = r["KurumAdi"]
        except Exception as e:
            logger.exception("Lookup hatası: %s", e)

    def _lookup_bitti(self):
        self._durum_yaz(
            f"Hazır — {len(self._lookup_etkin_madde)} etkin madde, "
            f"{len(self._lookup_brans)} branş, "
            f"{len(self._lookup_rapor_kodu)} rapor kodu yüklendi"
        )
        self._ay_listesini_yukle()

    # --------------------------------------------------------------- LAYOUT
    def _arayuz_olustur(self):
        # ═══════════════════════════════════════════════════════════════════
        # 2 KATMAN — ÜST: Veri/Sayım/Araçlar | ALT: Renkli kontrol panelleri
        # ═══════════════════════════════════════════════════════════════════

        HEADER_BG = "#37474F"
        HEADER_FG = "#FFFFFF"
        HEADER_LBL_FG = "#B0BEC5"
        FONT_PRIMARY = ("Segoe UI", 11, "bold")
        FONT_GROUP = ("Segoe UI", 9, "bold")
        FONT_BUTON = ("Segoe UI", 9, "bold")
        FONT_LABEL_SM = ("Segoe UI", 8, "bold")

        renk_kisa = {
            RENK_YESIL:   "🟢", RENK_SARI:    "🟡",
            RENK_TURUNCU: "🟠", RENK_KIRMIZI: "🔴",
            RENK_BEYAZ:   "⚪", RENK_GRI:     "🩶",
        }
        renk_aciklama = {
            RENK_YESIL:   "YEŞİL — Uygun (elendi)",
            RENK_SARI:    "SARI — Manuel kontrol gerekli",
            RENK_TURUNCU: "TURUNCU — Şüpheli",
            RENK_KIRMIZI: "KIRMIZI — Uygunsuz",
            RENK_BEYAZ:   "BEYAZ — Renksiz / sıfırla",
            RENK_GRI:     "GRİ — Kontrol gerekmez "
                            "(ilaç dışlama listesine eklenir)",
        }
        renk_etiket = {
            RENK_BEYAZ:   "⚪ Beyaz",
            RENK_YESIL:   "🟢 Yeşil",
            RENK_SARI:    "🟡 Sarı",
            RENK_TURUNCU: "🟠 Turuncu",
            RENK_KIRMIZI: "🔴 Kırmızı",
            RENK_GRI:     "🩶 Gri",
        }

        # ════════════════════════════════════════════════════════════════
        # ÜST SATIR — DATA + STATUS + TOOLS (koyu zemin)
        # ════════════════════════════════════════════════════════════════
        row1 = tk.Frame(self.root, bg=HEADER_BG, height=44)
        row1.pack(fill="x")
        row1.pack_propagate(False)

        # ── SOL: DÖNEM grubu (Yıl + Ay + SORGULA) ──
        sol = tk.Frame(row1, bg=HEADER_BG)
        sol.pack(side="left", padx=10, pady=5)

        tk.Label(sol, text="📅 DÖNEM", bg=HEADER_BG, fg=HEADER_LBL_FG,
                 font=FONT_LABEL_SM).pack(side="left", padx=(0, 8))

        tk.Label(sol, text="Yıl", bg=HEADER_BG, fg=HEADER_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
        self.var_yil = tk.StringVar()
        self.cb_yil = ttk.Combobox(sol, textvariable=self.var_yil,
                                    width=6, state="readonly")
        self.cb_yil.pack(side="left", padx=2)
        self.cb_yil.bind("<<ComboboxSelected>>", self._yil_degisti)
        _Tooltip(self.cb_yil,
                  "Yıl seçimi.\n'Tümü' = tüm yıllar (büyük veri seti)")

        tk.Label(sol, text="Ay", bg=HEADER_BG, fg=HEADER_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 3))
        self.var_ay = tk.StringVar()
        self.cb_ay = ttk.Combobox(sol, textvariable=self.var_ay,
                                   width=12, state="readonly")
        self.cb_ay.pack(side="left", padx=2)
        _Tooltip(self.cb_ay,
                  "Ay seçimi.\n'Tümü' = seçili yıldaki tüm aylar")

        btn = tk.Button(sol, text="🔍 SORGULA", bg="#1976D2", fg="white",
                         activebackground="#1565C0", bd=0,
                         command=self._receteleri_sorgula,
                         padx=14, pady=4, font=FONT_PRIMARY)
        btn.pack(side="left", padx=(10, 0))
        _Tooltip(btn,
                  "Seçili yıl/ay için Botanik EOS'tan reçete-ilaç satırlarını "
                  "yükle (sadece okuma).")

        # ── SAĞ: ARAÇLAR (Excel + Sütunlar) ──
        sag = tk.Frame(row1, bg=HEADER_BG)
        sag.pack(side="right", padx=10, pady=5)

        btn = tk.Button(sag, text="📊 Excel", bg="#43A047", fg="white",
                         activebackground="#388E3C", bd=0,
                         command=self._excel_export, padx=12, pady=3,
                         font=FONT_BUTON)
        btn.pack(side="right", padx=2)
        _Tooltip(btn, "Tabloyu (renk + sütunlarla) Excel dosyasına aktar")

        btn = tk.Button(sag, text="⚙ Sütunlar", bg="#546E7A", fg="white",
                         activebackground="#455A64", bd=0,
                         command=self._sutun_ayar_penceresi, padx=12, pady=3,
                         font=FONT_BUTON)
        btn.pack(side="right", padx=2)
        _Tooltip(btn, "Görünür sütunları ayarla (göster/gizle)")

        # ── ORTA: SAYIM (lbl_sayim) ──
        self.lbl_sayim = tk.Label(row1, text="", bg=HEADER_BG, fg=HEADER_FG,
                                    font=("Segoe UI", 10, "bold"))
        self.lbl_sayim.pack(side="left", padx=20, expand=True)
        _Tooltip(self.lbl_sayim,
                  "Toplam yüklenen / filtrelenmiş satır sayısı")

        # ════════════════════════════════════════════════════════════════
        # ALT SATIR(LAR) — KONTROL PANELLERİ (sıkışmayı önlemek için 2 sıra)
        # Sıra A: Seçim + Boyama (eylemler)
        # Sıra B: Göster + Reçete Türü + Boş Sat + Sıfırla (filtreler)
        # ════════════════════════════════════════════════════════════════
        row2 = tk.Frame(self.root, bg="#FAFAFA")
        row2.pack(fill="x", padx=4, pady=(2, 0))

        row3 = tk.Frame(self.root, bg="#FAFAFA")
        row3.pack(fill="x", padx=4, pady=(2, 2))

        def _panel_olustur(parent, baslik, baslik_fg, panel_bg):
            """Renkli arka planlı, başlık etiketli kompakt panel."""
            p = tk.Frame(parent, bg=panel_bg, bd=1, relief="solid")
            p.pack(side="left", padx=2, pady=1, fill="y")
            tk.Label(p, text=baslik, bg=panel_bg, fg=baslik_fg,
                     font=FONT_GROUP).pack(side="left", padx=(6, 6),
                                              pady=4)
            return p

        # ─── PANEL 1: SEÇİM (açık mavi) ───
        P_SECIM_BG = "#E3F2FD"
        p1 = _panel_olustur(row2, "🎯 Seçim", "#0D47A1", P_SECIM_BG)
        for txt, cmd, tip in [
            ("☑ Tümü", self._tumunu_sec,
             "Filtreden geçen tüm satırları SEÇ"),
            ("☐ Hiçbiri", self._hicbirini_secme,
             "Filtreden geçen satırların seçimini KALDIR"),
            ("↻ Tersine", self._secimi_tersine_cevir,
             "Seçimi tersine çevir (filtreli satırlarda)"),
        ]:
            b = tk.Button(p1, text=txt, bg="white", bd=1,
                          command=cmd, padx=8, pady=3, font=FONT_BUTON)
            b.pack(side="left", padx=2, pady=4)
            _Tooltip(b, tip)
        tk.Frame(p1, bg=P_SECIM_BG, width=4).pack(side="left")

        # ─── PANEL 2: BOYAMA (açık sarı) ───
        P_BOYA_BG = "#FFF8E1"
        p2 = _panel_olustur(row2, "🎨 Boyama", "#E65100", P_BOYA_BG)

        # Seçiliyi boya
        sub = tk.Frame(p2, bg=P_BOYA_BG)
        sub.pack(side="left", padx=(0, 4), pady=4)
        tk.Label(sub, text="Seçili →", bg=P_BOYA_BG, fg="#5D4037",
                 font=("Segoe UI", 8, "bold")
                 ).pack(side="left", padx=(2, 3))
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU,
                       RENK_KIRMIZI, RENK_BEYAZ, RENK_GRI]:
            b = tk.Button(sub, text=renk_kisa[renk],
                          bg=RENK_BG[renk], fg=RENK_FG[renk], bd=1,
                          command=lambda r=renk: self._secilenleri_renge_boya(r),
                          padx=4, width=2, font=("Segoe UI", 11))
            b.pack(side="left", padx=1)
            _Tooltip(b,
                      f"SEÇİLİ satırları boya:\n{renk_aciklama[renk]}\n"
                      "(Boyamadan sonra seçim temizlenir)")

        tk.Frame(p2, width=1, bg="#FFE082").pack(side="left", fill="y",
                                                   padx=4, pady=4)

        # Filtreliyi boya
        sub = tk.Frame(p2, bg=P_BOYA_BG)
        sub.pack(side="left", padx=(0, 6), pady=4)
        tk.Label(sub, text="Filtreli →", bg=P_BOYA_BG, fg="#5D4037",
                 font=("Segoe UI", 8, "bold")
                 ).pack(side="left", padx=(2, 3))
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU,
                       RENK_KIRMIZI, RENK_BEYAZ, RENK_GRI]:
            b = tk.Button(sub, text=renk_kisa[renk],
                          bg=RENK_BG[renk], fg=RENK_FG[renk], bd=1,
                          command=lambda r=renk: self._gorunenleri_boya(r),
                          padx=4, width=2, font=("Segoe UI", 11))
            b.pack(side="left", padx=1)
            _Tooltip(b,
                      f"FİLTRELİ tüm satırları boya:\n{renk_aciklama[renk]}\n"
                      "(Listede kalan tüm satırlar — scroll dışındakiler dahil)")

        # ─── PANEL 3: FİLTRE (açık yeşil) — alt sıraya geçiyor ───
        P_FLT_BG = "#E8F5E9"
        p3 = _panel_olustur(row3, "👁 Göster", "#1B5E20", P_FLT_BG)

        self.var_renk = {}
        for renk in [RENK_BEYAZ, RENK_YESIL, RENK_SARI,
                       RENK_TURUNCU, RENK_KIRMIZI, RENK_GRI]:
            v = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(p3, text=renk_etiket[renk],
                                  variable=v, bg=RENK_BG[renk],
                                  fg=RENK_FG[renk],
                                  selectcolor=RENK_BG[renk],
                                  font=("Segoe UI", 9, "bold"),
                                  padx=4, bd=1, relief="solid",
                                  command=self._renk_filtre_degisti)
            cb.pack(side="left", padx=1, pady=4)
            self.var_renk[renk] = v
            _Tooltip(cb,
                      f"{renk_aciklama[renk]}\n"
                      "renkli satırları tabloda GÖSTER / GİZLE")

        tk.Frame(p3, width=1, bg="#A5D6A7").pack(side="left", fill="y",
                                                   padx=6, pady=4)

        cb_bos = tk.Checkbutton(
            p3, text="🚫 Boş Satırları Gizle",
            variable=self.gizle_bos_satirlar,
            bg=P_FLT_BG, fg="#1B5E20", selectcolor="#FFFFFF",
            font=FONT_GROUP, padx=4, bd=0,
            command=self._bos_satir_filtre_degisti)
        cb_bos.pack(side="left", padx=(2, 2), pady=4)
        _Tooltip(cb_bos,
                  "Detaylı filtre kurallarının AÇIK/KAPALI anahtarı.\n\n"
                  "✅ İŞARETLİ: yandaki ⚙ butonundan tanımlanan kurallar "
                  "SQL'e uygulanır. (uyarı/mesaj/rapor/KYM içerik filtresi "
                  "+ ilaç/etken/atc/farma/tesis liste filtreleri)\n\n"
                  "☐ İŞARETSİZ: hiçbir filtre uygulanmaz, tüm kayıtlar "
                  "tabloya gelir.")

        btn_ayar = tk.Button(p3, text="⚙",
                              bg="#1976D2", fg="white",
                              activebackground="#1565C0",
                              bd=0, padx=4, pady=0,
                              font=("Segoe UI", 10, "bold"),
                              command=self._filtre_ayar_penceresi_ac)
        btn_ayar.pack(side="left", padx=(0, 6), pady=4)
        _Tooltip(btn_ayar,
                  "Detaylı filtre ayarları:\n"
                  "• Hangi içerikler gelsin (renkli reçete / mesaj / "
                  "uyarı / rapor)\n"
                  "• İlaç / etken madde / ATC / farmasötik form / tesis "
                  "için whitelist veya blacklist\n"
                  "Kaydet & Uygula sonrası SQL yeniden çalışır.")

        # ─── PANEL 3b: REÇETE TÜRÜ FİLTRESİ (Beyaz/Kırmızı/Yeşil/Mor) ───
        P_RT_BG = "#F3E5F5"   # açık mor zemin
        p3b = tk.Frame(row3, bg=P_RT_BG, bd=1, relief="solid")
        p3b.pack(side="left", padx=2, pady=1, fill="y")
        tk.Label(p3b, text="📋 Reçete", bg=P_RT_BG, fg="#4A148C",
                 font=FONT_GROUP).pack(side="left", padx=(6, 6), pady=4)

        recete_renk_renkler = {
            "Beyaz":   ("#FFFFFF", "#37474F"),
            "Kırmızı": ("#FFCDD2", "#B71C1C"),
            "Yeşil":   ("#C8E6C9", "#1B5E20"),
            "Mor":     ("#E1BEE7", "#4A148C"),
        }
        self.var_recete_turu = {}
        for ad, (bg_c, fg_c) in recete_renk_renkler.items():
            v = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(p3b, text=ad,
                                  variable=v, bg=bg_c, fg=fg_c,
                                  selectcolor=bg_c,
                                  font=("Segoe UI", 9, "bold"),
                                  padx=4, bd=1, relief="solid",
                                  command=self._recete_turu_filtre_degisti)
            cb.pack(side="left", padx=1, pady=4)
            self.var_recete_turu[ad] = v
            _Tooltip(cb,
                      f"{ad} reçeteleri TABLODA GÖSTER / GİZLE.\n"
                      "(SQL düzeyinde değil — yüklenen veri arasında filtreler)")
        tk.Frame(p3b, bg=P_RT_BG, width=4).pack(side="left")

        # ─── PANEL 4: SIFIRLA (açık kırmızı/sarı vurgu) ───
        P_RST_BG = "#FFEBEE"
        p4 = tk.Frame(row3, bg=P_RST_BG, bd=1, relief="solid")
        p4.pack(side="left", padx=2, pady=1, fill="y")
        btn = tk.Button(p4, text="🧹 Filtreleri Sıfırla",
                         bg="#FFE082", fg="#5D4037",
                         activebackground="#FFD54F", bd=1,
                         command=self._tum_filtreleri_temizle,
                         font=FONT_BUTON, padx=10, pady=4)
        btn.pack(side="left", padx=6, pady=4)
        _Tooltip(btn,
                  "Tüm filtreleri SIFIRLA:\n"
                  "• Sütun arama kutuları\n"
                  "• Excel-benzeri değer/metin filtreleri\n"
                  "• Renk filtresi (5 renk açık)\n"
                  "• 🚫 Boş Satırları Gizle (varsayılana döner)\n"
                  "• Sıralama")

        # ───── ANA TABLO (artık tüm genişlikte) ─────
        tablo_frame = tk.Frame(self.root, bg="white")
        tablo_frame.pack(fill="both", expand=True, padx=6, pady=(2, 4))
        self._tablo_kur(tablo_frame)

        # ───── DURUM ÇUBUĞU ─────
        self._durum_frame = tk.Frame(self.root, bg="#ECEFF1")
        self._durum_frame.pack(fill="x", side="bottom")

        # ── EN SOLDA: STATİN / LİPİD KONTROL butonu ──
        # Buton tıklanınca yüklenen satırlardan ATC C10* (statin + non-statin
        # lipid) olanlar SUT 4.2.28.A/B kuralına göre denetlenir; sonuç en sağdaki
        # SONUÇ sütununa UYGUN / UYGUN DEĞİL / ŞÜPHELİ olarak yazılır.
        self.btn_statin = tk.Button(
            self._durum_frame, text="🩺 STATİN KONTROL",
            font=("Segoe UI", 9, "bold"),
            fg="white", bg="#C62828", activebackground="#8E0000",
            bd=0, padx=12, pady=3, cursor="hand2",
            command=self._statin_kontrol_baslat
        )
        self.btn_statin.pack(side="left", padx=(4, 4), pady=2)

        # ── DİYABET KONTROL butonu (SUT 4.2.38) ──
        # ATC A10* (insülin + oral antidiyabetikler) — DPP-4/SGLT-2/GLP-1 RA
        # + klasik OAD + insülin SUT 4.2.38'e göre denetlenir.
        self.btn_diyabet = tk.Button(
            self._durum_frame, text="💉 DİYABET KONTROL",
            font=("Segoe UI", 9, "bold"),
            fg="white", bg="#0D47A1", activebackground="#002171",
            bd=0, padx=12, pady=3, cursor="hand2",
            command=self._diyabet_kontrol_baslat
        )
        self.btn_diyabet.pack(side="left", padx=(0, 8), pady=2)

        self.durum_bar = tk.Label(self._durum_frame, text="Hazır", anchor="w",
                                    bg="#ECEFF1", fg="#37474F", padx=10)
        self.durum_bar.pack(fill="x", side="left", expand=True)
        # Sağda renk dağılımı sayacı
        self.lbl_durum_dagilim = tk.Label(self._durum_frame, text="",
                                            bg="#ECEFF1", fg="#37474F", padx=10,
                                            font=("Segoe UI", 9))
        self.lbl_durum_dagilim.pack(side="right")

        # ───── HÜCRE İÇERİĞİ GÖSTERGE BARI ─────
        # Bir hücreye tıklanınca tüm metni burada (kesilmeden, alta
        # sarmalanarak) göster
        self._hucre_frame = tk.Frame(self.root, bg="#FFF9C4",
                                       bd=1, relief="solid")
        self._hucre_frame.pack(fill="x", side="bottom", padx=0, pady=0)

        # Üst sıra: ikon + sütun başlığı (sabit genişlikte)
        ust_satir = tk.Frame(self._hucre_frame, bg="#FFF9C4")
        ust_satir.pack(fill="x", side="top")
        tk.Label(ust_satir, text="📋",
                 bg="#FFF9C4", fg="#5D4037",
                 font=("Segoe UI", 10, "bold"),
                 padx=6).pack(side="left")
        self.lbl_hucre_baslik = tk.Label(
            ust_satir, text="—",
            bg="#FFF9C4", fg="#1565C0",
            font=("Segoe UI", 9, "bold"), padx=4, anchor="w")
        self.lbl_hucre_baslik.pack(side="left", fill="x", expand=True)

        # Alt: tam metni göster — sarmalama açık (wraplength dinamik)
        self.lbl_hucre_icerik = tk.Label(
            self._hucre_frame,
            text="(Hücreye tıkla → içeriği burada görüntülenir, "
                 "uzun metinler alt satırlara sarmalanır)",
            bg="#FFF9C4", fg="#37474F",
            font=("Segoe UI", 9), anchor="w", padx=10, pady=4,
            justify="left", wraplength=1000)
        self.lbl_hucre_icerik.pack(fill="x", side="top", padx=2, pady=(0, 2))

        # Pencere/frame genişliği değiştikçe wraplength'i güncelle
        def _hucre_wrap_guncelle(_event=None):
            try:
                w = self._hucre_frame.winfo_width() - 30
                if w > 100:
                    self.lbl_hucre_icerik.config(wraplength=w)
            except Exception:
                pass
        self._hucre_frame.bind("<Configure>", _hucre_wrap_guncelle)

    def _tablo_kur(self, parent):
        """Tablo + sütun-hizalı filtre satırı (tek yatay scroll ile birlikte)."""
        cont = tk.Frame(parent, bg="white")
        cont.pack(fill="both", expand=True, padx=4, pady=4)

        # Style: kompakt satırlar
        style = ttk.Style()
        try:
            style.configure("Inceleme.Treeview", rowheight=22, font=("Segoe UI", 9))
            style.configure("Inceleme.Treeview.Heading",
                            font=("Segoe UI", 9, "bold"))
        except Exception:
            pass

        # Yatay ölçüler — filtre ve tablo görünür alanı eşitlemek için
        FILTRE_H = 28           # filtre satırı yüksekliği (px)
        SAG_PAD = 18            # ttk Scrollbar genişliği (yaklaşık ysb)

        # ─────────── Yatay scrollbar (en altta) ───────────
        # Önce alta sabitliyoruz ki filtre + tablo onun üstünde dizilsin.
        xsb = ttk.Scrollbar(cont, orient="horizontal")
        xsb.pack(fill="x", side="bottom", padx=(0, SAG_PAD))

        # ─────────── Filtre satırı (sütunların ÜSTÜNDE — Excel benzeri) ───────────
        # Tablonun ysb genişliği kadar sağdan boşluk bırakıyoruz ki filtre
        # alanı tablo görünür alanıyla pixel-pixel aynı olsun.
        filtre_satir = tk.Frame(cont, bg="#ECEFF1", height=FILTRE_H)
        filtre_satir.pack(fill="x", side="top", pady=(0, 2))
        filtre_satir.pack_propagate(False)

        tk.Frame(filtre_satir, width=SAG_PAD, bg="#ECEFF1"
                 ).pack(side="right", fill="y")

        self._filtre_canvas = tk.Canvas(filtre_satir, bg="#ECEFF1",
                                         highlightthickness=0,
                                         height=FILTRE_H)
        self._filtre_canvas.pack(side="left", fill="both", expand=True)

        filtre_inner = tk.Frame(self._filtre_canvas, bg="#ECEFF1")
        self._filtre_canvas.create_window((0, 0), window=filtre_inner,
                                            anchor="nw")

        self.arama_varlari = {}
        # Placeholder durum izleyici — True iken filtreye etki etmez
        self._placeholder_aktif = {}
        self._placeholder_metni = {}
        toplam_gen = 0
        PH_FG = "#9E9E9E"      # silik gri
        AKTIF_FG = "#000000"   # kullanıcı yazısı
        for kod, baslik, gen, _tip in SUTUNLAR:
            slot = tk.Frame(filtre_inner, bg="#ECEFF1",
                            width=gen, height=FILTRE_H)
            slot.pack(side="left")
            slot.pack_propagate(False)
            v = tk.StringVar()
            ent = tk.Entry(slot, textvariable=v,
                            font=("Segoe UI", 8, "italic"),
                            relief="solid", bd=1, fg=PH_FG)
            ent.place(x=1, y=4, width=gen - 2, height=20)

            # Placeholder mantığı — başlık silik gri/italik olarak içeride
            self._placeholder_metni[kod] = baslik

            def _ph_goster(k=kod, e=ent, vv=v, ph=baslik):
                if not vv.get():
                    self._placeholder_aktif[k] = True
                    vv.set(ph)
                    e.config(fg=PH_FG, font=("Segoe UI", 8, "italic"))

            def _ph_gizle(k=kod, e=ent, vv=v):
                if self._placeholder_aktif.get(k):
                    self._placeholder_aktif[k] = False
                    vv.set("")
                    e.config(fg=AKTIF_FG, font=("Segoe UI", 8))

            ent.bind("<FocusIn>", lambda _e, fn=_ph_gizle: fn())
            ent.bind("<FocusOut>", lambda _e, fn=_ph_goster: fn())

            v.trace_add("write",
                         lambda *a, k=kod: self._sutun_filtre_degisti(k))
            self.arama_varlari[kod] = v
            # Başlangıçta placeholder göster
            _ph_goster()
            toplam_gen += gen

        filtre_inner.update_idletasks()
        self._filtre_canvas.config(scrollregion=(0, 0, toplam_gen, FILTRE_H))

        # ─────────── Tablo (filtrenin altında, kalan alanı doldurur) ───────────
        tree_frame = tk.Frame(cont, bg="white")
        tree_frame.pack(fill="both", expand=True, side="top")

        kolonlar = tuple(SUTUN_KOD)
        self.tv = ttk.Treeview(tree_frame, columns=kolonlar, show="headings",
                                selectmode="extended", style="Inceleme.Treeview")
        for kod, baslik, gen, _tip in SUTUNLAR:
            self.tv.heading(kod, text=baslik,
                            command=lambda k=kod: self._sutuna_gore_sirala(k))
            self.tv.column(kod, width=gen, minwidth=30, stretch=False)

        ysb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tv.yview)
        ysb.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)
        self.tv.configure(yscrollcommand=ysb.set)

        # Renk tag'leri
        for renk, bg in RENK_BG.items():
            fg = RENK_FG[renk]
            self.tv.tag_configure(renk, background=bg, foreground=fg)

        # Olay bind'leri
        self.tv.bind("<Button-3>", self._sag_tik_dispatch)
        self.tv.bind("<Double-1>", self._satir_detay)
        self.tv.bind("<Button-1>", self._sol_tik_dispatch, add="+")
        # Sütun genişlikleri değiştiğinde filtre slotlarını yeniden hizala.
        # Treeview'in column-resize özel event'i yok; mouse release sonrası
        # küçük bir gecikme ile güncel genişlikleri okuruz.
        def _siralama_sonrasi_hizala(_e=None):
            self.root.after(60, self._filtre_slotlarini_hizala)
        self.tv.bind("<ButtonRelease-1>", _siralama_sonrasi_hizala, add="+")
        self.tv.bind("<Configure>",
                       lambda _e: self.root.after(60,
                                                    self._filtre_slotlarini_hizala),
                       add="+")

        # ─────────── Yatay scroll senkronu (filtre + tablo birlikte) ───────────

        def _xview_birlikte(*args):
            self.tv.xview(*args)
            try:
                self._filtre_canvas.xview(*args)
            except Exception:
                pass
        xsb.configure(command=_xview_birlikte)

        def _on_tv_x_set(first, last):
            xsb.set(first, last)
            try:
                self._filtre_canvas.xview_moveto(float(first))
            except Exception:
                pass
        self.tv.configure(xscrollcommand=_on_tv_x_set)

        # Sütun yeniden boyutlandırma sonrası filtre slotlarını da güncellemek
        # için gecikmeli yenileme — başlık tıklamaları sonrası tetiklenir
        self._filtre_inner = filtre_inner
        self._filtre_slotlar = filtre_inner.winfo_children()
        self._filtre_h = FILTRE_H

    # ----------------------------------------------------------- AY/YIL
    def _ay_listesini_yukle(self):
        if not self.db:
            return
        try:
            rows = self.db.sorgu_calistir(
                "SELECT DISTINCT YEAR(RxKayitTarihi) AS Y FROM ReceteAna "
                "WHERE RxSilme=0 ORDER BY Y DESC")
            yillar = [str(r["Y"]) for r in rows if r["Y"]]
            self.cb_yil["values"] = ["Tümü"] + yillar
            if yillar:
                bugun = date.today()
                hedef = str(bugun.year)
                self.var_yil.set(hedef if hedef in yillar else yillar[0])
                self._yil_degisti()
        except Exception as e:
            logger.exception("Yıl listesi: %s", e)

    def _yil_degisti(self, *args):
        self.cb_ay["values"] = ["Tümü"] + [self._ay_etiketi(i)
                                              for i in range(1, 13)]
        bugun = date.today()
        self.var_ay.set(self._ay_etiketi(bugun.month))

    @staticmethod
    def _ay_etiketi(no: int) -> str:
        adlar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        return f"{no:02d}-{adlar[no - 1]}"

    @staticmethod
    def _ay_no_cek(et: str) -> int:
        try:
            return int(et.split("-")[0])
        except Exception:
            return 0

    # ----------------------------------------------------------- SORGU
    def _receteleri_sorgula(self):
        if not self.db:
            self._durum_yaz("DB bağlı değil")
            return
        yil_str = (self.var_yil.get() or "").strip()
        ay_str = (self.var_ay.get() or "").strip()

        # "Tümü" → None (filtre yok)
        if yil_str == "" or yil_str == "Tümü":
            yil = None
        else:
            try:
                yil = int(yil_str)
            except ValueError:
                messagebox.showwarning("Uyarı", "Geçersiz yıl")
                return
        if ay_str == "" or ay_str == "Tümü":
            ay = None
        else:
            ay = self._ay_no_cek(ay_str)
            if ay == 0:
                ay = None

        # Hem yıl hem ay 'Tümü' ise kullanıcıyı uyar (büyük veri seti)
        if yil is None and ay is None:
            if not messagebox.askyesno(
                "Tüm Reçeteler",
                "Yıl ve ay 'Tümü' — TÜM reçeteler yüklenecek.\n"
                "Bu uzun sürebilir ve çok bellek kullanabilir.\n\n"
                "Devam edilsin mi?"):
                return

        # Önce mevcut state kaydet
        self._state_kaydet()
        # Tabloyu temizle
        self.tum_satirlar = []
        self.satir_indeks = {}
        self.satir_renkleri = {}
        self.tv.delete(*self.tv.get_children())
        # Dönem etiketi (renk state'i bu anahtara kaydedilir)
        if yil is not None and ay is not None:
            self.aktif_donem = f"{yil}-{ay:02d}"
        elif yil is not None:
            self.aktif_donem = f"{yil}-TUM"
        elif ay is not None:
            self.aktif_donem = f"TUM-{ay:02d}"
        else:
            self.aktif_donem = "TUM"
        self.lbl_sayim.config(text="Sorgulanıyor…")
        self._durum_yaz(f"{self.aktif_donem} dönemi sorgulanıyor (ilaç bazlı)…")
        threading.Thread(target=self._sorgu_threadi, args=(yil, ay),
                          daemon=True).start()

    def _sorgu_threadi(self, yil, ay):
        """yil/ay None ise o filtre uygulanmaz (Tümü).
        gizle_bos_satirlar AÇIKsa: SQL düzeyinde uyarı kodu / mesaj / rapor
        kodu hiçbiri olmayan satırlar baştan elenir → daha az veri, daha
        hızlı yükleme."""
        try:
            # Ana SQL: ReceteAna × ReceteIlaclari × Musteri × Doktor × Urun × ATC × RaporAna
            # İlaç-rapor bağlantısı: RIRaporKodId + RRKIRaporKodId + Hasta + tarih aralığı
            # OUTER APPLY ile her ilaç için en uygun (en yeni) aktif raporu seç
            where_parts = ["ra.RxSilme = 0"]
            params = []
            if yil is not None:
                where_parts.append("YEAR(ra.RxKayitTarihi) = ?")
                params.append(int(yil))
            if ay is not None:
                where_parts.append("MONTH(ra.RxKayitTarihi) = ?")
                params.append(int(ay))

            # 🚫 Boş Satırları Gizle — detaylı filtre ayarlarını uygula
            try:
                bos_gizle = self.gizle_bos_satirlar.get()
            except Exception:
                bos_gizle = False
            if bos_gizle:
                try:
                    import aylik_filtre_ayarlari as fa
                    ay = self._filtre_ayarlari_aktif or fa.ayarlari_yukle()
                    renkli_idler = sorted(
                        (self._renkli_recete_idler or {}).keys())
                    icerik_kos = fa.sql_icerik_kosullari(ay, renkli_idler)
                    if icerik_kos:
                        where_parts.append(icerik_kos)
                    liste_kos = fa.sql_liste_kosullari(ay)
                    if liste_kos:
                        where_parts.append(liste_kos)
                except Exception as e:
                    logger.warning("Filtre ayarları SQL'e dönüştürülemedi: %s", e)

            where_sql = " AND ".join(where_parts)

            sql = f"""
                SELECT
                    ra.RxId, ra.RxEReceteNo,
                    ra.RxIslemTarihi, ra.RxKayitTarihi,
                    ra.RxBransId, ra.RxKurumId, ra.RxMusteriId, ra.RxDoktorId,
                    ra.RxReceteRenkId, ra.RxReceteAltTuruId, ra.RxProvizyonTipId,
                    m.MusteriAdiSoyadi, m.MusteriTCKN, m.MusteriDogumTarihi,
                    m.MusteriCinsiyet, m.MusteriKapsamId, m.MusteriEmeklilik,
                    d.DoktorAdiSoyadi,
                    ri.RIId, ri.RIUrunId, ri.RIRaporKodId, ri.RIRaporNo,
                    ri.RIAdet, ri.RIDoz, ri.RITekrar, ri.RIAralik, ri.RIPeriyotId,
                    ri.RIToplam, ri.RIFiyatFarki,
                    u.UrunAdi, u.UrunATCId, u.UrunEsdegerId,
                    atc.ATCKodu, atc.ATCTurkce,
                    rapinfo.RaporAnaId, rapinfo.RaporAnaRaporNo,
                    rapinfo.RaporAnaRaporTarihi, rapinfo.RaporAnaAciklamalar
                FROM ReceteAna ra
                INNER JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
                                              AND ri.RISilme = 0
                LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
                LEFT JOIN Doktor d ON d.DoktorId = ra.RxDoktorId
                LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
                LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId
                OUTER APPLY (
                    SELECT TOP 1
                        rap.RaporAnaId, rap.RaporAnaRaporNo,
                        rap.RaporAnaRaporTarihi, rap.RaporAnaAciklamalar
                    FROM RaporRaporKodlariICD rrki
                    INNER JOIN RaporAna rap ON rap.RaporAnaId = rrki.RRKIRaporAnaId
                                            AND rap.RaporAnaMusteriId = ra.RxMusteriId
                                            AND rap.RaporAnaSilme = 0
                    WHERE rrki.RRKIRaporKodId = ri.RIRaporKodId
                      AND rrki.RRKISilme = 0
                      AND rrki.RRKIBaslamaTarihi <= ra.RxKayitTarihi
                      AND rrki.RRKIBitisTarihi >= ra.RxKayitTarihi
                    ORDER BY rap.RaporAnaRaporTarihi DESC
                ) rapinfo
                WHERE {where_sql}
                ORDER BY ra.RxKayitTarihi DESC, ri.RIId
            """
            try:
                rows = self.db.sorgu_calistir(sql, tuple(params))
                logger.info(f"Sorgu OK: {len(rows)} ilaç satırı")
            except Exception as e_sql:
                logger.error("Tam sorgu fail: %s", e_sql)
                # Hata kullanıcıya göster
                hata_msg = str(e_sql)
                self.root.after(0, lambda: messagebox.showerror(
                    "SQL Hatası", f"Sorgu fail:\n{hata_msg[:300]}"))
                self.root.after(0, lambda: self.lbl_sayim.config(text=f"SQL Hata"))
                self.root.after(0, self._durum_yaz, f"SQL Hata: {hata_msg[:120]}")
                return

            # Doktor branş bilgisi
            doktor_idleri = list({r["RxDoktorId"] for r in rows if r.get("RxDoktorId")})
            doktor_brans = self._doktor_branslarini_getir(doktor_idleri)

            # Reçete bazlı toplu sorgular
            rx_idler = list({r["RxId"] for r in rows})
            recete_teshis = self._toplu_recete_teshis_getir(rx_idler)
            recete_aciklama = self._toplu_recete_aciklama_getir(rx_idler)
            medula_yaniti = self._toplu_medula_yanit_getir(rx_idler)
            uyari_per_ilac, uyari_recete_geneli = (
                self._toplu_uyari_kodu_per_ilac_getir(rx_idler))

            # Rapor bazlı toplu sorgular (ana SQL'den gelen RaporAnaId'ler)
            rapor_ana_idler = list({r["RaporAnaId"] for r in rows
                                       if r.get("RaporAnaId")})
            rapor_detay = self._toplu_rapor_detay_getir(rapor_ana_idler)

            # Ürün bazlı UMTMesaj (her ilacın gerçek ilaç mesajı)
            urun_idler = list({r["RIUrunId"] for r in rows if r.get("RIUrunId")})
            urun_mesaj = self._toplu_urun_mesaj_getir(urun_idler)

            # Sonuçları yapıya çevir
            satirlar = []
            for r in rows:
                satir = self._satir_olustur(
                    r, doktor_brans, recete_teshis, recete_aciklama,
                    medula_yaniti, uyari_per_ilac, uyari_recete_geneli,
                    rapor_detay, urun_mesaj)
                satirlar.append(satir)

            self.root.after(0, self._sorgu_bitti, satirlar)
        except Exception as e:
            logger.exception("Sorgu hatası: %s", e)
            self.root.after(0, self._durum_yaz, f"Sorgu hatası: {e}")
            self.root.after(0, lambda: self.lbl_sayim.config(text="Hata"))

    def _doktor_branslarini_getir(self, doktor_idleri: list) -> dict:
        if not doktor_idleri:
            return {}
        try:
            ph = ",".join("?" * len(doktor_idleri))
            rows = self.db.sorgu_calistir(
                f"""SELECT DoktorBransDoktorId, DoktorBransBransId
                    FROM DoktorBrans WHERE DoktorBransDoktorId IN ({ph})""",
                tuple(doktor_idleri))
            result = {}
            for r in rows:
                did = r["DoktorBransDoktorId"]
                ad = self._lookup_brans.get(r["DoktorBransBransId"], "")
                if ad:
                    result.setdefault(did, []).append(ad)
            return {k: ", ".join(v) for k, v in result.items()}
        except Exception:
            return {}

    def _toplu_recete_teshis_getir(self, rx_idler: list) -> dict:
        """Reçete teşhislerini RxId bazında topla.
        İki kaynak:
        1) ReceteICD + ICD tablosu (ICD kodu + açıklama)
        2) ReceteTeshis + Teshis tablosu (eski Teshis sistemi)
        """
        if not rx_idler:
            return {}
        result = {}
        # 1) ReceteICD üzerinden (yeni sistem — ICD-10 kodu)
        try:
            for i in range(0, len(rx_idler), 1000):
                chunk = rx_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT ricd.ReceteICDRxId, icd.ICDKodu, icd.ICDAciklamasi
                        FROM ReceteICD ricd
                        LEFT JOIN ICD icd ON icd.ICDId = ricd.ReceteICDICDId
                        WHERE ricd.ReceteICDRxId IN ({ph})
                          AND ricd.ReceteICDSilme = 0""",
                    tuple(chunk))
                for r in rows:
                    rxid = r["ReceteICDRxId"]
                    kod = (r.get("ICDKodu") or "").strip()
                    aciklama = (r.get("ICDAciklamasi") or "").strip()
                    if kod and aciklama:
                        result.setdefault(rxid, []).append(f"{kod} {aciklama}")
                    elif kod:
                        result.setdefault(rxid, []).append(kod)
        except Exception as e:
            logger.warning("ReceteICD sorgu fail: %s", e)

        # 2) ReceteTeshis + Teshis (eski sistem — TeshisId üzerinden)
        try:
            for i in range(0, len(rx_idler), 1000):
                chunk = rx_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT rt.RTRxId, rt.RTTeshisKodu, t.TeshisAciklama
                        FROM ReceteTeshis rt
                        LEFT JOIN Teshis t ON t.TeshisId = rt.RTTeshisId
                        WHERE rt.RTRxId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    rxid = r["RTRxId"]
                    aciklama = (r.get("TeshisAciklama") or "").strip()
                    kod = (r.get("RTTeshisKodu") or "").strip()
                    if aciklama:
                        # "001 - Teşhisi yok" formatında geliyor; "Seçiniz" gibi anlamsızları atla
                        if "Seçiniz" not in aciklama:
                            result.setdefault(rxid, []).append(aciklama)
        except Exception as e:
            logger.warning("ReceteTeshis sorgu fail: %s", e)
        return {k: " | ".join(dict.fromkeys(v)) for k, v in result.items()}

    def _toplu_recete_aciklama_getir(self, rx_idler: list) -> dict:
        """Reçete açıklamalarını RxId bazında topla.
        Bağlantı zinciri: ReceteAna.RxEReceteNo = ERecete.EReceteNo,
                            ERecete.EReceteId = EReceteAciklamalari.ERAEReceteId
        Yani RxId → EReceteId → açıklamalar (e-reçete ID'si üzerinden)
        """
        if not rx_idler:
            return {}
        result = {}
        try:
            for i in range(0, len(rx_idler), 1000):
                chunk = rx_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT ra.RxId,
                               eat.EReceteAciklamaTuruAdi,
                               ea.EReceteAciklamaAdi
                        FROM ReceteAna ra
                        INNER JOIN ERecete er ON er.EReceteNo = ra.RxEReceteNo
                                              AND er.EReceteSilme = 0
                        INNER JOIN EReceteAciklamalari era
                                 ON era.ERAEReceteId = er.EReceteId
                        LEFT JOIN EReceteAciklama ea
                                 ON ea.EReceteAciklamaId = era.ERAEReceteAciklamaId
                        LEFT JOIN EReceteAciklamaTuru eat
                                 ON eat.EReceteAciklamaTuruId = era.ERAEReceteAciklamaTuruId
                        WHERE ra.RxId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    rxid = r["RxId"]
                    tur = r.get("EReceteAciklamaTuruAdi") or ""
                    ad = (r.get("EReceteAciklamaAdi") or "").strip()
                    # Boş veya anlamsız ("." gibi) açıklamaları atla
                    if not ad or ad in (".", ",", "-", "--"):
                        continue
                    if tur and tur != "Seçiniz":
                        txt = f"[{tur}] {ad}"
                    else:
                        txt = ad
                    result.setdefault(rxid, []).append(txt)
        except Exception as e:
            logger.warning("Reçete açıklama sorgu fail: %s", e)
        return {k: " | ".join(v) for k, v in result.items()}

    def _toplu_urun_mesaj_getir(self, urun_idler: list) -> dict:
        """UrunId → [mesaj1, mesaj2, ...] mapping (UMTUrunMesaj + UMTMesaj).
        Bu Botanik EOS'un ilaç mesaj sistemi — Medula'nın bir ürün için
        gösterdiği SUT mesajlarını (272, EK-4/E, 4.2.14.A vb.) içerir.
        """
        if not urun_idler:
            return {}
        result = {}
        try:
            for i in range(0, len(urun_idler), 1000):
                chunk = urun_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT umt.UMTUMUrunId, m.UMTMMesaj, m.UMTMSutKodu
                        FROM UMTUrunMesaj umt
                        LEFT JOIN UMTMesaj m ON m.UMTMId = umt.UMTUMUMTMesajId
                        WHERE umt.UMTUMUrunId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    uid = r["UMTUMUrunId"]
                    mesaj = (r.get("UMTMMesaj") or "").strip()
                    sut = (r.get("UMTMSutKodu") or "").strip()
                    if mesaj:
                        result.setdefault(uid, []).append({
                            "mesaj": mesaj,
                            "sut": sut,
                        })
        except Exception as e:
            logger.warning("UMTUrunMesaj sorgu fail: %s", e)
        return result

    def _toplu_medula_yanit_getir(self, rx_idler: list) -> dict:
        """Medula provizyon yanıt mesajları (RxUyarilari.RUAciklama).
        Bunlar Medula'nın reçeteye verdiği yanıt mesajlarıdır
        (örn: "uyarı kodları uyumsuz (367)").
        Returns: {rxid: "mesaj1 | mesaj2"}
        """
        if not rx_idler:
            return {}
        result = {}
        try:
            for i in range(0, len(rx_idler), 1000):
                chunk = rx_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT RxId, RUAciklama FROM RxUyarilari
                        WHERE RxId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    rxid = r["RxId"]
                    txt = r.get("RUAciklama") or ""
                    if txt:
                        result.setdefault(rxid, []).append(txt)
        except Exception as e:
            logger.warning("Medula yanıt sorgu fail: %s", e)
        return {k: " | ".join(v) for k, v in result.items()}

    def _toplu_uyari_kodu_per_ilac_getir(self, rx_idler: list):
        """Reçeteye GİRİLMİŞ uyarı kodları (ReceteTeshis tablosu).
        TAMPROST → 256 gibi: kullanıcının reçete kaydı sırasında
        ilaca atadığı uyarı kodları burada tutulur.
        Returns:
            per_ilac: {(rxid, urun_id): "256 - Benign prostat hiperplazisi"}
            recete_geneli: {rxid: "..."}  # RTUrunId boş olanlar (reçete genel)
        """
        per_ilac: dict = {}
        recete_geneli: dict = {}
        if not rx_idler:
            return per_ilac, recete_geneli
        try:
            for i in range(0, len(rx_idler), 1000):
                chunk = rx_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT rt.RTRxId, rt.RTUrunId, rt.RTTeshisKodu,
                               t.TeshisAciklama
                        FROM ReceteTeshis rt
                        LEFT JOIN Teshis t ON t.TeshisId = rt.RTTeshisId
                        WHERE rt.RTRxId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    rxid = r["RTRxId"]
                    urun_id = r.get("RTUrunId")
                    kod = (r.get("RTTeshisKodu") or "").strip()
                    aciklama = (r.get("TeshisAciklama") or "").strip()
                    if not kod:
                        continue
                    # Aciklama zaten "256 - Benign prostat..." formatında
                    txt = aciklama if aciklama else kod
                    if "Seçiniz" in txt:
                        continue
                    if urun_id:
                        per_ilac.setdefault((rxid, urun_id), []).append(txt)
                    else:
                        recete_geneli.setdefault(rxid, []).append(txt)
        except Exception as e:
            logger.warning("ReceteTeshis uyarı kodu sorgu fail: %s", e)
        per_ilac = {k: " | ".join(dict.fromkeys(v)) for k, v in per_ilac.items()}
        recete_geneli = {k: " | ".join(dict.fromkeys(v))
                          for k, v in recete_geneli.items()}
        return per_ilac, recete_geneli

    def _toplu_rapor_detay_getir(self, rapor_ana_idler: list) -> dict:
        """RaporAnaId → {teshisler, etkin_madde_doz, ek_bilgiler}.
        Tek sorgu yerine 3 ayrı toplu sorgu (ek bilgi, etken madde, ICD).
        """
        if not rapor_ana_idler:
            return {}
        result = {rid: {"ek_bilgi": [], "etkin_doz": [], "icd": []}
                   for rid in rapor_ana_idler}

        # 0) Rapor ICD/teşhis (RaporRaporKodlariICD + ICD)
        try:
            for i in range(0, len(rapor_ana_idler), 1000):
                chunk = rapor_ana_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT rrki.RRKIRaporAnaId,
                               icd1.ICDKodu AS K1, icd1.ICDAciklamasi AS A1,
                               icd2.ICDKodu AS K2, icd2.ICDAciklamasi AS A2,
                               icd3.ICDKodu AS K3, icd3.ICDAciklamasi AS A3,
                               icd4.ICDKodu AS K4, icd4.ICDAciklamasi AS A4,
                               icd5.ICDKodu AS K5, icd5.ICDAciklamasi AS A5
                        FROM RaporRaporKodlariICD rrki
                        LEFT JOIN ICD icd1 ON icd1.ICDId = rrki.RRKIICDId
                        LEFT JOIN ICD icd2 ON icd2.ICDId = rrki.RRKIICDId2
                        LEFT JOIN ICD icd3 ON icd3.ICDId = rrki.RRKIICDId3
                        LEFT JOIN ICD icd4 ON icd4.ICDId = rrki.RRKIICDId4
                        LEFT JOIN ICD icd5 ON icd5.ICDId = rrki.RRKIICDId5
                        WHERE rrki.RRKIRaporAnaId IN ({ph})
                          AND rrki.RRKISilme = 0""",
                    tuple(chunk))
                for r in rows:
                    rid = r["RRKIRaporAnaId"]
                    if rid not in result:
                        result[rid] = {"ek_bilgi": [], "etkin_doz": [], "icd": []}
                    for n in (1, 2, 3, 4, 5):
                        kod = (r.get(f"K{n}") or "").strip()
                        ack = (r.get(f"A{n}") or "").strip()
                        if kod and ack:
                            result[rid]["icd"].append(f"{kod} {ack}")
                        elif kod:
                            result[rid]["icd"].append(kod)
        except Exception as e:
            logger.warning("RaporICD sorgu fail: %s", e)

        # 1) RaporEkBilgi — ek açıklamalar
        try:
            for i in range(0, len(rapor_ana_idler), 1000):
                chunk = rapor_ana_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT REBRaporAnaId, REBTuru, REBDeger, REBAciklama
                        FROM RaporEkBilgi WHERE REBRaporAnaId IN ({ph})""",
                    tuple(chunk))
                for r in rows:
                    rid = r["REBRaporAnaId"]
                    parts = []
                    if r.get("REBTuru"):
                        parts.append(str(r["REBTuru"]))
                    if r.get("REBDeger"):
                        parts.append(str(r["REBDeger"]))
                    if r.get("REBAciklama"):
                        parts.append(str(r["REBAciklama"]))
                    if parts:
                        result[rid]["ek_bilgi"].append(": ".join(parts))
        except Exception as e:
            logger.warning("RaporEkBilgi sorgu fail: %s", e)

        # 2) RaporEtkinMadde — rapor doz bilgisi
        try:
            for i in range(0, len(rapor_ana_idler), 1000):
                chunk = rapor_ana_idler[i:i + 1000]
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT EtkinMaddeRaporAnaId, EtkinMaddeId,
                               EtkinMaddeDoz, EtkinMaddeAdetMiktar,
                               EtkinMaddeTekrar, EtkinMaddeAralik,
                               EtkinMaddePeriyotId
                        FROM RaporEtkinMadde
                        WHERE EtkinMaddeRaporAnaId IN ({ph})
                          AND EtkinMaddeSilme = 0""",
                    tuple(chunk))
                for r in rows:
                    rid = r["EtkinMaddeRaporAnaId"]
                    em_id = r.get("EtkinMaddeId")
                    em_kod, em_ad = self._lookup_etkin_madde.get(em_id, ("", ""))
                    parts = []
                    if em_ad:
                        parts.append(em_ad)
                    doz = r.get("EtkinMaddeDoz")
                    adet = r.get("EtkinMaddeAdetMiktar")
                    tekrar = r.get("EtkinMaddeTekrar")
                    if doz:
                        parts.append(f"Doz:{doz}")
                    if adet:
                        parts.append(f"Adt:{adet}")
                    if tekrar:
                        parts.append(f"x{tekrar}")
                    if parts:
                        result[rid]["etkin_doz"].append({
                            "etkin_id": em_id,
                            "etkin_ad": em_ad,
                            "metin": " ".join(parts),
                            "doz": doz, "adet": adet, "tekrar": tekrar,
                        })
        except Exception as e:
            logger.warning("RaporEtkinMadde sorgu fail: %s", e)

        return result

    def _satir_olustur(self, r, doktor_brans, recete_teshis, recete_aciklama,
                        medula_yaniti, uyari_per_ilac, uyari_recete_geneli,
                        rapor_detay, urun_mesaj=None) -> dict:
        urun_mesaj = urun_mesaj or {}
        uyari_per_ilac = uyari_per_ilac or {}
        uyari_recete_geneli = uyari_recete_geneli or {}
        medula_yaniti = medula_yaniti or {}
        rxid = r.get("RxId")
        riid = r.get("RIId")

        # Rapor kodu (RIRaporKodId üzerinden lookup)
        rk_id = r.get("RIRaporKodId") or 0
        rap_kod_str, rap_kod_acik = self._lookup_rapor_kodu.get(rk_id, ("", ""))

        # ATC (ana sorgudan, ATC tablosu join'lendi)
        atc_kodu = r.get("ATCKodu") or ""
        atc_ad = r.get("ATCTurkce") or ""

        # ───────────────────────────────────────────────────────────────
        # ETKEN MADDE — ATC.ATCTurkce her satırda dolu (raporlu/raporsuz fark etmez).
        # Raporlu ilaçlarda ek olarak RaporEtkinMadde'deki etken maddeler de gösterilir.
        # ───────────────────────────────────────────────────────────────
        atc_turkce = (r.get("ATCTurkce") or "").strip()
        rapor_ana_id = r.get("RaporAnaId")
        em_ad_rapor = ""
        rap_doz_metin = ""
        rap_doz_sayi = 0.0
        rapor_aciklamalari = []
        rap_tesh_listesi = []

        if rapor_ana_id and rapor_ana_id in rapor_detay:
            rd = rapor_detay[rapor_ana_id]
            # Rapor ICD/teşhisleri
            rap_tesh_listesi = rd.get("icd", [])
            # Etkin madde bilgisi rapor üzerinden
            em_listesi = rd.get("etkin_doz", [])
            if em_listesi:
                em_ad_rapor = " + ".join(e.get("etkin_ad", "") for e in em_listesi
                                           if e.get("etkin_ad"))
                doz_metinleri = [e.get("metin", "") for e in em_listesi
                                  if e.get("metin")]
                rap_doz_metin = " | ".join(doz_metinleri)
                ilk = em_listesi[0]
                try:
                    d = float(ilk.get("doz") or 0)
                    a_ = float(ilk.get("adet") or 0)
                    t_ = float(ilk.get("tekrar") or 1)
                    rap_doz_sayi = max(d, a_) * t_
                except Exception:
                    pass
            # Rapor açıklamaları: ana açıklama + ek bilgi listesi
            ana_ack = r.get("RaporAnaAciklamalar") or ""
            if ana_ack:
                rapor_aciklamalari.append(ana_ack)
            rapor_aciklamalari.extend(rd.get("ek_bilgi", []))

        # Etken madde finali: ÖNCE bu ilacın kendi ATC'si (drug-specific).
        # Raporun etken maddeleri (em_ad_rapor) raporun TÜM ilaçları için
        # ortaktır — her bir ilaç satırına kopyalandığında karışıklık
        # yapar (ör: BENIPIN satırında ŞEKER ÇUBUĞU görünmesi). Bu yüzden
        # em_ad SADECE ATC.ATCTurkce'den alınır; ATC boşsa rapor etkenine
        # düşer.
        if atc_turkce:
            em_ad = atc_turkce
        elif em_ad_rapor:
            em_ad = em_ad_rapor
        else:
            em_ad = ""

        rap_ack = " | ".join(rapor_aciklamalari) if rapor_aciklamalari else ""
        rap_tesh = " | ".join(dict.fromkeys(rap_tesh_listesi)) if rap_tesh_listesi else ""

        # Tarih
        tar = r.get("RxIslemTarihi") or r.get("RxKayitTarihi")
        tar_str = tarih_format(tar, "%d.%m.%Y")

        # Hasta tipi
        kapsam_id = r.get("MusteriKapsamId")
        hasta_tip = self._lookup_kapsam.get(kapsam_id, "")

        # Reçete türü (Normal/Kırmızı/Yeşil/Mor) ve Alt türü (Ayaktan/Yatan/A/B/C/GK)
        renk_id = r.get("RxReceteRenkId")
        rec_tip = self._lookup_renk.get(renk_id, "")
        alttur_id = r.get("RxReceteAltTuruId")
        rec_alttur = self._lookup_alttur.get(alttur_id, "")

        # Grup belirleme
        grup = self._grup_belirle(r)

        # Reçete dozu — "<aralık> <periyot> <tekrar> x <doz>" formatında
        # ÖRNEKLER: "1 günde 2 x 1" / "7 günde 1 x 2" / "1 ayda 1 x 1"
        # NOT: RIAdet (kutu sayısı) BURAYA dahil edilmez — ayrı "kutu" sütununda gösterilir.
        rd_metin = doz_metin(
            r.get("RIAralik"),     # aralık (1, 7, vs.)
            r.get("RIPeriyotId"),  # periyot türü (3=günde, 4=haftada, 5=ayda)
            r.get("RITekrar"),     # tekrar (kez)
            r.get("RIDoz"),        # doz (her keferinde alınan miktar)
        )
        rd_sayi = float(r.get("RIDoz") or 0) * float(r.get("RITekrar") or 1)

        # SUT maddesi tespiti
        sut_madde = sut_madde_tespit(r.get("UrunAdi") or "", em_ad,
                                       rap_kod_str)

        # Dönem
        donem = (r.get("RxKayitTarihi") or r.get("RxIslemTarihi"))
        donem_str = tarih_format(donem, "%Y-%m")

        # Mesaj durumu: bu ürünün UMTUrunMesaj'da kayıtlı SUT mesajı var mı?
        # (Medula reçete kayıt sırasında gösterdiği "Msj: var/yok" bu tabloya geliyor)
        urun_id = r.get("RIUrunId")
        ilac_mesajlari = urun_mesaj.get(urun_id, []) if urun_id else []
        msj = "var" if ilac_mesajlari else "yok"

        # Uyarı kodu: bu reçetede bu ilaç için ReceteTeshis'e girilmiş kodlar.
        # Öncelik:
        #  1) Reçete-ilaç bazlı kod (RTUrunId = bu ilaç)
        #  2) Reçete geneline yazılmış kod (RTUrunId boş)
        ilac_kodu = uyari_per_ilac.get((rxid, urun_id), "") if urun_id else ""
        recete_kodu = uyari_recete_geneli.get(rxid, "")
        if ilac_kodu and recete_kodu:
            uyari_text = f"{ilac_kodu} | (Reç: {recete_kodu})"
        elif ilac_kodu:
            uyari_text = ilac_kodu
        elif recete_kodu:
            uyari_text = f"(Reç: {recete_kodu})"
        else:
            uyari_text = ""

        # Medula provizyon yanıt metni (RxUyarilari) — ayrı sütun
        medula_msj_text = medula_yaniti.get(rxid, "")

        return {
            "ri_id": riid, "rx_id": rxid,
            "rapor_ana_id": rapor_ana_id,
            "musteri_id": r.get("RxMusteriId"),
            "secim": "☐",  # tablo render sırasında secili_iidler'e göre güncellenir
            "grup": grup,
            "donem": donem_str,
            "rec_tar": tar_str,
            "rec_no": r.get("RxEReceteNo") or "",
            "rec_tip": rec_tip,
            "rec_alttur": rec_alttur,
            "hasta": r.get("MusteriAdiSoyadi") or "",
            "tc": r.get("MusteriTCKN") or "",
            "yas": yas_hesapla(r.get("MusteriDogumTarihi")),
            "cins": cinsiyet_etiket(r.get("MusteriCinsiyet")),
            "hasta_tip": hasta_tip,
            "doktor": r.get("DoktorAdiSoyadi") or "",
            "brans": doktor_brans.get(r.get("RxDoktorId"), ""),
            "ilac": r.get("UrunAdi") or "",
            "etkin": em_ad,
            "atc": atc_kodu,
            "esdeger": str(r.get("UrunEsdegerId") or ""),
            "kutu": str(r.get("RIAdet") or ""),
            "sut": sut_madde,
            "rap_kod": rap_kod_str,
            "rec_doz": rd_metin,
            "rec_doz_sayi": rd_sayi,
            "rap_doz": rap_doz_metin,
            "rap_doz_sayi": rap_doz_sayi,
            "msj": msj,
            "uyari": uyari_text,
            "medula_msj": medula_msj_text,
            "rec_tesh": recete_teshis.get(rxid, ""),
            "rap_tesh": rap_tesh,
            "rec_ack": recete_aciklama.get(rxid, ""),
            "rap_ack": rap_ack,
        }

    def _grup_belirle(self, r) -> str:
        """A/B/C/GK/CK tespiti (kural-bazlı tahmin).

        NOT: A/B/C/CK/GK grupları Botanik EOS DB'sinde reçete bazında
        doğrudan kayıtlı değil (SGK fatura kesimi sırasında belirleniyor).
        Bu fonksiyon kural-bazlı tahmin yapar:
          - Kan ürünü ATC kodları (J06, B05) → CK
          - Hasta kapsamı 60/c1 (yeşil kart benzeri) → GK
          - Reçete tipi 50 (Magistral) → "M"
          - Diğer → boş (eczacı manuel kategorize eder)
        """
        atc_kodu = (r.get("ATCKodu") or "").upper()
        kapsam_id = r.get("MusteriKapsamId")
        kapsam_ad = (self._lookup_kapsam.get(kapsam_id, "") or "").upper()
        recete_tipi = r.get("RxReceteTipi")

        # 1) CK — Kan ürünü tespiti (immünglobulin, kan/plazma türevleri)
        if atc_kodu:
            if (atc_kodu.startswith("J06A") or       # İmmünglobulin
                    atc_kodu.startswith("B05A") or   # Plazma türevleri (faktörler)
                    atc_kodu.startswith("B02") or    # Antihemorrhagic
                    atc_kodu.startswith("B03X")):    # ESA + diğer hematolojikler
                return "CK"

        # 2) GK — Geçici Koruma (genelde sığınmacı/yabancı kapsamı)
        # Botanik EOS'ta direkt "Geçici Koruma" kapsamı yok ama bazı
        # özel kodlar olabilir
        if "GEÇICI KORUMA" in kapsam_ad or "GEÇİCİ KORUMA" in kapsam_ad:
            return "GK"
        if "MÜLTECİ" in kapsam_ad or "SIĞINMACI" in kapsam_ad:
            return "GK"

        # 3) Magistral
        if recete_tipi == 50:
            return "M"

        # 4) A/B/C ayrımı için güvenilir alan yok — eczacı manuel kategorize eder
        return ""

    def _sorgu_bitti(self, satirlar: list):
        """SQL sonucu geldi, tabloyu doldur."""
        self.tum_satirlar = satirlar
        self.satir_indeks = {}
        # State'i yükle (önceki boyamalar)
        kayitli_renkler = self._state_yukle_donem(self.aktif_donem)

        for s in satirlar:
            riid = s["ri_id"]
            iid = str(riid)
            self.satir_indeks[iid] = s
            renk = kayitli_renkler.get(iid, RENK_BEYAZ)
            self.satir_renkleri[iid] = renk

        # Sütun görünüm ayarını uygula (kullanıcının tercihi varsa)
        self._sutun_gorunumunu_uygula()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._durum_yaz(f"{len(satirlar)} satır geldi (ilaç bazlı)")

    # ----------------------------------------------------------- TABLO RENDER
    def _tabloyu_yenile(self):
        """tum_satirlar + filtreler + renk filtresi → tv'ye doldur.
        Filtreyle gizlenen satırlar seçim setinden de düşer; bu sayede sonraki
        boyama işlemlerinde sadece ekrandaki seçimler işleme alınır."""
        self.tv.delete(*self.tv.get_children())
        self.gosterilen_iids = set()

        # Reçete türü filtresi — SADECE kapatılan tipler dışlanır.
        # Default (hepsi açık) ya da bilinmeyen tip → satır geçer.
        gizli_recete_turleri = {
            ad for ad, v in (self.var_recete_turu or {}).items()
            if not v.get()
        } if hasattr(self, "var_recete_turu") and self.var_recete_turu else set()

        for s in self.tum_satirlar:
            iid = str(s["ri_id"])
            if not self._satir_filtreden_geciyor_mu(s):
                continue
            renk = self.satir_renkleri.get(iid, RENK_BEYAZ)
            if renk not in self.aktif_renk_filtre:
                continue
            # Reçete türü filtresi: sadece kullanıcının kapattığı tipleri ele
            if gizli_recete_turleri:
                rec_tip = (s.get("rec_tip") or "").strip()
                if rec_tip in gizli_recete_turleri:
                    continue
            # Seçim göstergesi (☐/☑)
            s["secim"] = "☑" if iid in self.secili_iidler else "☐"
            values = tuple(str(s.get(k, "")) for k in SUTUN_KOD)
            self.tv.insert("", "end", iid=iid, values=values, tags=(renk,))
            self.gosterilen_iids.add(iid)

        # Filtre ile gizlenen satırların seçimini de düşür — kullanıcının
        # "sadece görünenleri boyuyorum" beklentisini garanti eder.
        if self.secili_iidler:
            self.secili_iidler &= self.gosterilen_iids

    def _satir_filtreden_geciyor_mu(self, s: dict, haric_kod: str = None) -> bool:
        """Sütun arama kutuları + Excel-benzeri değer filtreleri ile filtre.

        haric_kod: Verildiğinde o sütunun kendi filtresi yoksayılır.
                   (Kaskad filtre popup'ı için — bir sütunun filtre popup'ı
                   açıldığında o sütunun filtresi diğer sütunlardaki seçenekleri
                   kısıtlamamalı, ama diğer sütunların filtreleri uygulanmalı.)
        """
        # 1) Alt sütun arama kutuları (içerir) — placeholder metni filtreye
        # etki etmesin diye atla.
        for kod, var in self.arama_varlari.items():
            if kod == haric_kod:
                continue
            if (getattr(self, "_placeholder_aktif", {})
                    .get(kod)):
                continue
            ara = (var.get() or "").strip().lower()
            if not ara:
                continue
            deger = str(s.get(kod, "")).lower()
            if ara not in deger:
                return False
        # 2) Excel-benzeri değer filtreleri (set içinde mi?)
        for kod, secili in self.aktif_deger_filtre.items():
            if kod == haric_kod:
                continue
            if not secili:
                continue
            if str(s.get(kod, "")) not in secili:
                return False
        # 3) Excel-tarzı metin operatör filtreleri (başlar/biter/içerir...)
        for kod, (op, deger) in self.aktif_metin_filtre.items():
            if kod == haric_kod:
                continue
            s_str = str(s.get(kod, "") or "").lower()
            d_str = (deger or "").lower()
            if op == "icerir":
                if d_str and d_str not in s_str:
                    return False
            elif op == "icermez":
                if d_str and d_str in s_str:
                    return False
            elif op == "baslar":
                if d_str and not s_str.startswith(d_str):
                    return False
            elif op == "biter":
                if d_str and not s_str.endswith(d_str):
                    return False
            elif op == "esit":
                if d_str and s_str != d_str:
                    return False
            elif op == "esit_degil":
                if d_str and s_str == d_str:
                    return False
            elif op == "bos":
                if s_str:
                    return False
            elif op == "bos_degil":
                if not s_str:
                    return False
            elif op == "regex":
                if d_str:
                    try:
                        import re as _re
                        if not _re.search(d_str, s_str, _re.IGNORECASE):
                            return False
                    except _re.error:
                        pass
        return True

    def _sutun_filtre_degisti(self, kod: str):
        # Placeholder yazımları filtre tetiklemesin
        if (getattr(self, "_placeholder_aktif", {})
                .get(kod)):
            return
        # Kısa debounce ile çağırılabilir; şimdilik direkt
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _renk_filtre_degisti(self):
        self.aktif_renk_filtre = {r for r, v in self.var_renk.items()
                                    if v.get()}
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _bos_satir_filtre_degisti(self):
        """🚫 Boş Satırları Gizle değişti → SQL düzeyinde filtre değişti
        demektir, sorguyu yeniden çalıştır. Henüz veri çekilmediyse hiç
        bir şey yapma."""
        if not self.tum_satirlar:
            return
        self._durum_yaz("🚫 Boş satır filtresi değişti — sorgu yenileniyor…")
        self._receteleri_sorgula()

    def _filtre_ayar_penceresi_ac(self):
        """⚙ butonu — detaylı filtre ayar penceresini açar."""
        try:
            import aylik_filtre_ayarlari as fa
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Hata",
                                  f"Filtre ayar modülü yüklenemedi:\n{e}")
            return

        def _on_save(yeni_ayarlar):
            # Yeni ayarları memory'e al ve sorguyu yenile
            self._filtre_ayarlari_aktif = yeni_ayarlar
            if self.tum_satirlar:
                # Yalnızca bos_gizle açıkken yeniden sorgu mantıklı
                self._durum_yaz(
                    "⚙ Filtre ayarları güncellendi — sorgu yenileniyor…")
                self._receteleri_sorgula()
            else:
                self._durum_yaz("⚙ Filtre ayarları kaydedildi "
                                  "(sonraki Sorgula çalışmasında uygulanır)")

        fa.ayar_penceresini_ac(self.root, db=self.db, on_save=_on_save)

    def _recete_turu_filtre_degisti(self):
        """📋 Reçete türü checkbox'ı (Beyaz/Kırmızı/Yeşil/Mor) değişti.
        Yüklü veri arasında filtreleme — SQL'e gitmeden tablo yenilenir."""
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _tum_filtreleri_temizle(self):
        """Tüm aktif filtreleri sıfırla:
        - Sütun arama kutuları (alt satır)
        - Excel-benzeri değer filtreleri (sağ tık popup'tan)
        - Renk filtreleri (5 renk de açık)
        - Sıralama
        """
        # Sütun arama kutularını temizle (placeholder geri gelsin)
        for kod, var in self.arama_varlari.items():
            try:
                # Placeholder durumunu sıfırla — temiz başla
                if hasattr(self, "_placeholder_aktif"):
                    self._placeholder_aktif[kod] = False
                var.set("")
            except Exception:
                pass
        # Entry'lere placeholder geri yerleştir (focus out gibi davran)
        try:
            self._filtre_inner.focus_set()
        except Exception:
            pass
        # Excel-benzeri değer filtrelerini sıfırla
        self.aktif_deger_filtre.clear()
        # Metin filtrelerini sıfırla (başlar/biter/içerir...)
        self.aktif_metin_filtre.clear()
        # Renk filtrelerini hepsini aç
        for v in self.var_renk.values():
            try:
                v.set(True)
            except Exception:
                pass
        self.aktif_renk_filtre = {RENK_BEYAZ, RENK_YESIL, RENK_SARI,
                                    RENK_TURUNCU, RENK_KIRMIZI, RENK_GRI}
        # "Boş Satırları Gizle" — varsayılana (AÇIK) döndür
        try:
            self.gizle_bos_satirlar.set(True)
        except Exception:
            pass
        # Reçete türü filtresi → hepsi açık (varsayılan)
        try:
            for v in (self.var_recete_turu or {}).values():
                v.set(True)
        except Exception:
            pass
        # Sıralamayı sıfırla
        self._siralama_kolonu = None
        self._siralama_yonu = None
        # Tabloyu ve göstergeleri yenile
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._siralama_gostergesini_guncelle()
        self._durum_yaz("Tüm filtreler sıfırlandı — tüm satırlar görünür")

    def _sayaclari_guncelle(self):
        # Renk dağılımı (tek satırda kompakt)
        say = {r: 0 for r in RENK_BG.keys()}
        for r in self.satir_renkleri.values():
            say[r] = say.get(r, 0) + 1
        toplam = len(self.tum_satirlar)
        gor = len(self.gosterilen_iids)
        sec = len(self.secili_iidler)
        txt = (f"Toplam: {toplam}  |  Filtreli: {gor}  |  Seçili: {sec}  ||  "
               f"⚪ {say[RENK_BEYAZ]}  🟢 {say[RENK_YESIL]}  "
               f"🟡 {say[RENK_SARI]}  🟠 {say[RENK_TURUNCU]}  🔴 {say[RENK_KIRMIZI]}")
        try:
            self.lbl_durum_dagilim.config(text=txt)
        except Exception:
            pass
        try:
            if toplam:
                self.lbl_sayim.config(text=f"{toplam} satır  |  Filtrelenmiş: {gor}")
            else:
                self.lbl_sayim.config(text="")
        except Exception:
            pass

    # ----------------------------------------------------------- BOYAMA
    def _gri_iclac_disla(self, iidler):
        """RENK_GRI ile boyanan satırların ilaç adlarını filtre ayar
        dosyasındaki 'ilac' dışlama listesine ekler. Aynı SORGUDA
        bir daha gelmez (ana sorgu yenilenince devre dışı kalır)."""
        try:
            import aylik_filtre_ayarlari as fa
        except Exception as e:
            logger.warning("Filtre ayar modülü yok: %s", e)
            return 0
        try:
            ay = fa.ayarlari_yukle()
        except Exception as e:
            logger.warning("Filtre ayarları okunamadı: %s", e)
            return 0
        ilac_kurallari = ay.get("ilac") or []
        mevcut = {(k.get("deger") or "").strip().upper()
                   for k in ilac_kurallari
                   if k.get("mod") == "icermez"}
        eklendi = 0
        for iid in iidler:
            s = self.satir_indeks.get(iid)
            if not s:
                continue
            ilac_adi = (s.get("ilac") or "").strip()
            if not ilac_adi:
                continue
            if ilac_adi.upper() in mevcut:
                continue
            ilac_kurallari.append({"deger": ilac_adi, "mod": "icermez"})
            mevcut.add(ilac_adi.upper())
            eklendi += 1
        if eklendi:
            ay["ilac"] = ilac_kurallari
            try:
                fa.ayarlari_kaydet(ay)
                self._filtre_ayarlari_aktif = ay
            except Exception as e:
                logger.warning("Filtre ayarları yazılamadı: %s", e)
        return eklendi

    def _secilenleri_renge_boya(self, renk: str):
        """secili_iidler set'indeki satırları renge boya.
        İşlem sonrası seçim seti TEMİZLENİR. Renk RENK_GRI ise ilaç adı
        otomatik olarak dışlama listesine eklenir."""
        if not self.secili_iidler:
            messagebox.showinfo("Bilgi", "Önce satırları seç (☐ kutucukları)")
            return
        n = len(self.secili_iidler)
        # Gri ise dışlama listesine ekle (boyamadan önce — iidler üzerinden)
        eklendi = 0
        if renk == RENK_GRI:
            eklendi = self._gri_iclac_disla(list(self.secili_iidler))
        for iid in self.secili_iidler:
            self.satir_renkleri[iid] = renk
        self.secili_iidler.clear()
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        ek = (f" — {eklendi} ilaç dışlama listesine eklendi"
              if renk == RENK_GRI and eklendi else "")
        self._durum_yaz(f"{n} satır → {RENK_ETIKET[renk]} "
                          f"(seçim temizlendi){ek}")

    def _hizli_filtre_menu(self, event=None):
        """Hızlı filtre seçim menüsü (dropdown)."""
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="── Hızlı Filtreler ──", state="disabled")
        for etiket, fn in HIZLI_FILTRELER:
            m.add_command(label=etiket,
                            command=lambda f=fn: self._hizli_filtre_uygula(f))
        m.add_separator()
        m.add_command(label="(Filtreyi temizle)",
                        command=self._tabloyu_yenile)
        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _gorunenleri_boya(self, renk: str):
        """Filtreden geçip listede kalan tüm satırları boyar
        (ekrana sığan değil — scroll dışındakiler de dahil).
        Renk RENK_GRI ise ilaçlar dışlama listesine eklenir."""
        if not self.gosterilen_iids:
            self._durum_yaz("Filtreli satır yok")
            return
        n = len(self.gosterilen_iids)
        ek_uyari = ""
        if renk == RENK_GRI:
            ek_uyari = ("\n\n⚠ Bu satırlardaki ilaçlar dışlama listesine "
                         "(ilaç → İçermez) eklenecektir.")
        if not messagebox.askyesno(
                "Filtreli Satırları Boya",
                f"Filtreden geçen {n} satır '{RENK_ETIKET[renk]}' rengine "
                f"boyanacak.\n(Listedeki tüm satırlar — scroll dışındakiler "
                f"dahil){ek_uyari}\n\nEmin misin?"):
            return
        eklendi = 0
        if renk == RENK_GRI:
            eklendi = self._gri_iclac_disla(list(self.gosterilen_iids))
        for iid in list(self.gosterilen_iids):
            self.satir_renkleri[iid] = renk
            self.secili_iidler.discard(iid)
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        ek = (f" — {eklendi} ilaç dışlama listesine eklendi"
              if renk == RENK_GRI and eklendi else "")
        self._durum_yaz(f"{n} satır → {RENK_ETIKET[renk]}{ek}")

    def _secilenleri_boya(self):
        secimler = list(self.tv.selection())
        if not secimler:
            self._durum_yaz("Seçili satır yok")
            return
        # Renk seçim popup
        win = tk.Toplevel(self.root)
        win.title("Renk Seç")
        win.geometry("260x200")
        win.transient(self.root)
        tk.Label(win, text=f"{len(secimler)} satır için renk:",
                 font=("Segoe UI", 10, "bold")).pack(pady=8)
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU, RENK_KIRMIZI, RENK_BEYAZ]:
            tk.Button(win, text=RENK_ETIKET[renk],
                      bg=RENK_BG[renk], fg=RENK_FG[renk],
                      command=lambda r=renk: (self._secilenleri_boya_uygula(secimler, r),
                                                win.destroy())
                      ).pack(fill="x", padx=20, pady=2)

    def _secilenleri_boya_uygula(self, iids, renk):
        eklendi = 0
        if renk == RENK_GRI:
            eklendi = self._gri_iclac_disla(iids)
        for iid in iids:
            self.satir_renkleri[iid] = renk
            self.secili_iidler.discard(iid)
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        ek = (f" — {eklendi} ilaç dışlama listesine eklendi"
              if renk == RENK_GRI and eklendi else "")
        self._durum_yaz(f"{len(iids)} seçili satır → {RENK_ETIKET[renk]}{ek}")

    def _tum_renkleri_sifirla(self):
        if not messagebox.askyesno("Tüm Renkleri Sıfırla",
                                     "Tüm satırlar BEYAZ olacak. Emin misin?"):
            return
        for iid in self.satir_renkleri:
            self.satir_renkleri[iid] = RENK_BEYAZ
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    # ----------------------------------------------------------- HIZLI FİLTRE
    def _hizli_filtre_uygula(self, fn):
        """Hızlı filtreyi uygula (sadece görünenleri filtrele)."""
        # Sütun filtrelerini koruyarak ek bir filtre uygulamak için:
        # Kullanıcı arama kutularını temizleyip sadece bu filtreyi uygulasın
        # Daha kullanıcı dostu: tablodaki iid'lerden filtrelenmiş kümeyi göster
        secilenler = set()
        for s in self.tum_satirlar:
            try:
                if fn(s):
                    secilenler.add(str(s["ri_id"]))
            except Exception:
                pass
        # Renk filtreden de geç
        gor = []
        self.tv.delete(*self.tv.get_children())
        self.gosterilen_iids = set()
        for iid in secilenler:
            s = self.satir_indeks.get(iid)
            if not s:
                continue
            renk = self.satir_renkleri.get(iid, RENK_BEYAZ)
            if renk not in self.aktif_renk_filtre:
                continue
            values = tuple(str(s.get(k, "")) for k in SUTUN_KOD)
            self.tv.insert("", "end", iid=iid, values=values, tags=(renk,))
            self.gosterilen_iids.add(iid)
        self._sayaclari_guncelle()
        self._durum_yaz(f"Hızlı filtre: {len(self.gosterilen_iids)} satır")

    def _hizli_filtre_uygula_ve_boya(self, fn):
        self._hizli_filtre_uygula(fn)
        if self.gosterilen_iids:
            n = len(self.gosterilen_iids)
            if messagebox.askyesno(
                    "Hızlı Filtre + Boya",
                    f"{n} satır filtreden geçti. Yeşile boyansın mı?"):
                self._gorunenleri_boya(RENK_YESIL)

    # ----------------------------------------------------------- SOL TIK (CHECKBOX TOGGLE)
    def _sol_tik_dispatch(self, event):
        """Sol tık — secim sütununda checkbox toggle, başka sütunlarda
        tıklanan hücrenin tam içeriğini alttaki gösterge satırında yansıt."""
        try:
            region = self.tv.identify_region(event.x, event.y)
        except Exception:
            return
        if region != "cell":
            return
        col_id = self.tv.identify_column(event.x)
        kod = self._col_id_to_kod(col_id)
        iid = self.tv.identify_row(event.y)
        if not iid:
            return

        # Secim sütunu → checkbox toggle (eski davranış)
        if kod == "secim":
            if iid in self.secili_iidler:
                self.secili_iidler.discard(iid)
                self.tv.set(iid, "secim", "☐")
            else:
                self.secili_iidler.add(iid)
                self.tv.set(iid, "secim", "☑")
            s = self.satir_indeks.get(iid)
            if s:
                s["secim"] = "☑" if iid in self.secili_iidler else "☐"
            self._sayaclari_guncelle()
            return

        # Diğer sütunlar → hücre içeriğini alt label'a bas
        try:
            deger = ""
            if kod:
                deger = self.tv.set(iid, kod)
            # Sütun başlığı
            baslik = ""
            for k, b, _g, _t in SUTUNLAR:
                if k == kod:
                    baslik = b
                    break
            self.lbl_hucre_baslik.config(text=f"[{baslik}]")
            self.lbl_hucre_icerik.config(
                text=deger if deger else "(boş)")
        except Exception as e:
            logger.debug("hücre içeriği gösterimi: %s", e)

    def _tumunu_sec(self):
        """Görünen tüm satırları işaretle."""
        for iid in self.gosterilen_iids:
            self.secili_iidler.add(iid)
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _hicbirini_secme(self):
        """Görünen satırların seçimini kaldır (gizli satırların seçimi korunur).
        Bu Excel benzeri tutarlı davranış için: 'Tümü Seç' görünenleri seçer,
        'Hiçbiri' de görünenlerin işaretini kaldırır.
        """
        for iid in self.gosterilen_iids:
            self.secili_iidler.discard(iid)
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _secimi_tersine_cevir(self):
        """Görünen satırlardan seçili olanları kaldır, olmayanları işaretle."""
        for iid in self.gosterilen_iids:
            if iid in self.secili_iidler:
                self.secili_iidler.discard(iid)
            else:
                self.secili_iidler.add(iid)
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    # ----------------------------------------------------------- SAĞ TIK & DETAY
    def _sag_tik_dispatch(self, event):
        """Başlığa mı satıra mı tıklandı? Doğru menüyü aç."""
        try:
            region = self.tv.identify_region(event.x, event.y)
        except Exception:
            region = ""
        if region == "heading" or region == "separator":
            col_id = self.tv.identify_column(event.x)
            kod = self._col_id_to_kod(col_id)
            if kod:
                self._sutun_basligi_menu(event, kod)
                return
        # Satır
        self._sag_tik_menu(event)

    def _col_id_to_kod(self, col_id: str):
        """Treeview '#1', '#2' formatından sütun kodunu çıkart."""
        if not col_id or not col_id.startswith("#"):
            return None
        try:
            idx = int(col_id[1:]) - 1
            # Görünen sütunlar (displaycolumns) varsa ona göre
            disp = self.tv["displaycolumns"]
            if disp and disp != "#all":
                if isinstance(disp, str):
                    return None
                if 0 <= idx < len(disp):
                    return disp[idx]
            else:
                if 0 <= idx < len(SUTUN_KOD):
                    return SUTUN_KOD[idx]
        except Exception:
            pass
        return None

    def _sutun_basligi_menu(self, event, kod: str):
        """Excel-benzeri sütun başlığı sağ tık menüsü."""
        baslik = next((b for k, b, _g, _t in SUTUNLAR if k == kod), kod)
        m = tk.Menu(self.root, tearoff=0)
        # Sıralama
        m.add_command(label="▲ Artan sırala (A→Z)",
                        command=lambda: self._kolon_sirala_belirli(kod, "asc"))
        m.add_command(label="▼ Azalan sırala (Z→A)",
                        command=lambda: self._kolon_sirala_belirli(kod, "desc"))
        m.add_command(label="↕ Sıralamayı temizle",
                        command=lambda: self._kolon_sirala_belirli(kod, None))
        m.add_separator()
        # Excel-benzeri değer filtresi
        m.add_command(label=f"🔍 '{baslik}' sütununda filtrele (değer listesi)…",
                        command=lambda: self._sutun_deger_filtre_popup(kod))
        # Metin filtresi (başlar/biter/içerir/regex...)
        m.add_command(label=f"🔎 '{baslik}' metin filtresi (başlar/biter/içerir...)…",
                        command=lambda: self._metin_filtre_popup(kod))
        if kod in self.aktif_deger_filtre or kod in self.aktif_metin_filtre:
            m.add_command(label=f"⊘ '{baslik}' filtresini temizle",
                            command=lambda: self._sutun_filtresini_temizle(kod))
        m.add_separator()
        # Hızlı bu değere göre filtrele
        m.add_command(label=f"⚙ '{baslik}' sütununu gizle",
                        command=lambda: self._sutunu_hizli_gizle(kod))
        m.add_command(label="⚙ Sütun ayarları...",
                        command=self._sutun_ayar_penceresi)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _kolon_sirala_belirli(self, kod, yon):
        """Belirli yönde sırala."""
        if yon is None:
            self._siralama_kolonu = None
            self._siralama_yonu = None
        else:
            self._siralama_kolonu = kod
            self._siralama_yonu = yon
        self._siralama_gostergesini_guncelle()
        if self._siralama_kolonu:
            ornekler = [s.get(kod, "") for s in self.tum_satirlar[:50] if s.get(kod)]
            sayisal = bool(ornekler) and all(
                self._sayiya_cevrilebilir_mi(o) for o in ornekler[:10])
            rev = (yon == "desc")
            if sayisal:
                self.tum_satirlar.sort(
                    key=lambda s: self._sayiya_cevir(s.get(kod, "")), reverse=rev)
            else:
                self.tum_satirlar.sort(
                    key=lambda s: str(s.get(kod, "") or "").lower(), reverse=rev)
        self._tabloyu_yenile()

    def _sutun_deger_filtre_popup(self, kod: str):
        """Excel-benzeri sütun değer filtre popup'ı.
        Tüm benzersiz değerler checkbox listesi olarak gösterilir.
        """
        baslik = next((b for k, b, _g, _t in SUTUNLAR if k == kod), kod)
        win = tk.Toplevel(self.root)
        win.title(f"Filtrele — {baslik}")
        win.geometry("440x560")
        win.transient(self.root)

        # KASKAD FİLTRE — sadece DİĞER filtreler uygulandıktan sonra GÖRÜNECEK
        # satırların değerleri listelensin. Bu sütunun kendi filtresi yoksayılır
        # (yoksa popup tek seçili değerle gelir).
        from collections import Counter
        sayim = Counter()
        for s in self.tum_satirlar:
            # Diğer sütun filtrelerini uygula (bu sütun hariç)
            if not self._satir_filtreden_geciyor_mu(s, haric_kod=kod):
                continue
            # Renk filtresini de uygula
            iid = str(s.get("ri_id"))
            renk = self.satir_renkleri.get(iid, RENK_BEYAZ)
            if renk not in self.aktif_renk_filtre:
                continue
            sayim[str(s.get(kod, "") or "")] += 1
        # Sıralı liste — boşları sona, geri kalanı alfabetik
        degerler = sorted(sayim.keys(),
                            key=lambda d: (d == "", d.lower()))

        tk.Label(win, text=f"📋 {baslik}",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Label(win,
                 text=f"{len(degerler)} farklı değer | Diğer filtrelerden geçen: "
                       f"{sum(sayim.values())} satır",
                 fg="#546E7A", font=("Segoe UI", 8)).pack(anchor="w", padx=8)

        # Arama kutusu — değerleri filtrele
        ara_frame = tk.Frame(win)
        ara_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(ara_frame, text="🔍").pack(side="left")
        var_ara = tk.StringVar()
        ent = tk.Entry(ara_frame, textvariable=var_ara)
        ent.pack(side="left", fill="x", expand=True, padx=4)
        ent.focus_set()

        # Tümü Seç / Tümü Kaldır
        ust = tk.Frame(win)
        ust.pack(fill="x", padx=8)
        tk.Button(ust, text="Tümünü Seç", bg="#C8E6C9",
                  command=lambda: self._popup_tumu(var_dict, True)
                  ).pack(side="left", padx=2)
        tk.Button(ust, text="Tümünü Kaldır", bg="#FFCDD2",
                  command=lambda: self._popup_tumu(var_dict, False)
                  ).pack(side="left", padx=2)
        tk.Button(ust, text="Aramaya Uyanları Seç", bg="#BBDEFB",
                  command=lambda: self._popup_aranana_uygula(var_dict, var_ara, True)
                  ).pack(side="left", padx=2)

        # Liste (scrollable, checkbox'lı)
        list_frame = tk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)
        canvas = tk.Canvas(list_frame, highlightthickness=0, bg="white")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner = tk.Frame(canvas, bg="white")
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Mevcut filtre durumu
        secili = self.aktif_deger_filtre.get(kod, set(degerler))
        var_dict = {}
        cb_dict = {}

        def _populate(filtre_metni=""):
            # Mevcut widget'ları temizle
            for w in inner.winfo_children():
                w.destroy()
            cb_dict.clear()
            f = filtre_metni.lower()
            for d in degerler:
                if f and f not in str(d).lower():
                    continue
                v = var_dict.get(d)
                if v is None:
                    v = tk.BooleanVar(value=(d in secili))
                    var_dict[d] = v
                etiket = d if d else "(boş)"
                cnt = sayim[d]
                cb = tk.Checkbutton(
                    inner, text=f"{etiket}   ({cnt})",
                    variable=v, anchor="w", bg="white",
                    font=("Segoe UI", 9), padx=4)
                cb.pack(fill="x", anchor="w")
                cb_dict[d] = cb
            inner.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))

        _populate()

        # Arama değişikliğinde liste güncelle
        var_ara.trace_add("write", lambda *a: _populate(var_ara.get()))

        # Uygula / İptal
        alt = tk.Frame(win)
        alt.pack(fill="x", padx=8, pady=8)

        def _uygula():
            secimler = {d for d, v in var_dict.items() if v.get()}
            # Tümü seçiliyse filtre yok
            if len(secimler) == len(degerler):
                self.aktif_deger_filtre.pop(kod, None)
            elif not secimler:
                # Hiçbiri seçili değil — kullanıcı tüm satırları gizliyor
                self.aktif_deger_filtre[kod] = set()
            else:
                self.aktif_deger_filtre[kod] = secimler
            self._tabloyu_yenile()
            self._sayaclari_guncelle()
            self._siralama_gostergesini_guncelle()
            win.destroy()

        tk.Button(alt, text="Uygula", bg="#1976D2", fg="white",
                  command=_uygula, padx=14, font=("Segoe UI", 9, "bold")
                  ).pack(side="right", padx=4)
        tk.Button(alt, text="İptal", command=win.destroy, padx=12
                  ).pack(side="right", padx=4)

    def _popup_tumu(self, var_dict, deger):
        for v in var_dict.values():
            v.set(deger)

    def _popup_aranana_uygula(self, var_dict, var_ara, deger):
        f = (var_ara.get() or "").lower()
        for d, v in var_dict.items():
            if not f or f in str(d).lower():
                v.set(deger)

    def _metin_filtre_popup(self, kod: str):
        """Excel-tarzı metin filtre popup'ı: Başlar/Biter/İçerir/Eşit/Boş/Regex."""
        baslik = next((b for k, b, _g, _t in SUTUNLAR if k == kod), kod)
        win = tk.Toplevel(self.root)
        win.title(f"Metin Filtresi — {baslik}")
        win.geometry("440x220")
        win.transient(self.root)

        tk.Label(win, text=f"📋 {baslik}",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

        # Mevcut filtre
        mevcut_op, mevcut_deger = self.aktif_metin_filtre.get(kod, ("icerir", ""))

        op_listesi = [
            ("İçerir",       "icerir"),
            ("İçermez",      "icermez"),
            ("Başlar",       "baslar"),
            ("Biter",        "biter"),
            ("Eşittir",      "esit"),
            ("Eşit değil",   "esit_degil"),
            ("Boş",          "bos"),
            ("Boş değil",    "bos_degil"),
            ("Regex (gelişmiş)", "regex"),
        ]
        kod_to_disp = {k: d for d, k in op_listesi}

        # Operatör
        op_frame = tk.Frame(win)
        op_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(op_frame, text="Operatör:", width=10, anchor="w"
                 ).pack(side="left")
        op_cb = ttk.Combobox(op_frame,
                              values=[d for d, _k in op_listesi],
                              width=22, state="readonly")
        op_cb.set(kod_to_disp.get(mevcut_op, "İçerir"))
        op_cb.pack(side="left", padx=4)

        # Değer
        deg_frame = tk.Frame(win)
        deg_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(deg_frame, text="Değer:", width=10, anchor="w"
                 ).pack(side="left")
        var_deg = tk.StringVar(value=mevcut_deger)
        ent = tk.Entry(deg_frame, textvariable=var_deg, font=("Segoe UI", 10))
        ent.pack(side="left", padx=4, fill="x", expand=True)
        ent.focus_set()

        # Bilgi
        bilgi = tk.Label(win,
                          text="• İçerir/Başlar/Biter: metin parçası ara\n"
                               "• Eşittir/Eşit değil: tam eşleşme\n"
                               "• Boş/Boş değil: değer alanı kullanılmaz\n"
                               "• Regex: gelişmiş, örn ^A.*B$",
                          fg="#546E7A", font=("Segoe UI", 8),
                          justify="left", anchor="w")
        bilgi.pack(fill="x", padx=10, pady=(6, 4))

        # Butonlar
        alt = tk.Frame(win)
        alt.pack(fill="x", padx=10, pady=10)

        def _uygula():
            op_disp = op_cb.get()
            op_kod = next((k for d, k in op_listesi if d == op_disp), "icerir")
            deger = var_deg.get()
            # Boş değer + boş olmayan op → filtreyi kaldır
            if not deger and op_kod not in ("bos", "bos_degil"):
                self.aktif_metin_filtre.pop(kod, None)
            else:
                self.aktif_metin_filtre[kod] = (op_kod, deger)
            self._tabloyu_yenile()
            self._sayaclari_guncelle()
            self._siralama_gostergesini_guncelle()
            win.destroy()

        def _temizle():
            self.aktif_metin_filtre.pop(kod, None)
            self._tabloyu_yenile()
            self._sayaclari_guncelle()
            self._siralama_gostergesini_guncelle()
            win.destroy()

        tk.Button(alt, text="Uygula", bg="#1976D2", fg="white",
                  command=_uygula, padx=14, font=("Segoe UI", 9, "bold")
                  ).pack(side="right", padx=4)
        tk.Button(alt, text="Filtreyi Kaldır",
                  command=_temizle, padx=10
                  ).pack(side="right", padx=4)
        tk.Button(alt, text="İptal",
                  command=win.destroy, padx=10
                  ).pack(side="right", padx=4)

        ent.bind("<Return>", lambda e: _uygula())

    def _sutun_filtresini_temizle(self, kod):
        self.aktif_deger_filtre.pop(kod, None)
        self.aktif_metin_filtre.pop(kod, None)
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._siralama_gostergesini_guncelle()

    def _sutunu_hizli_gizle(self, kod):
        self.sutun_gosterim[kod] = False
        self._sutun_ayarlarini_kaydet()
        self._sutun_gorunumunu_uygula()

    def _sag_tik_menu(self, event):
        iid = self.tv.identify_row(event.y)
        if iid and iid not in self.tv.selection():
            self.tv.selection_set(iid)
        if not self.tv.selection():
            return
        m = tk.Menu(self.root, tearoff=0)
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU, RENK_KIRMIZI, RENK_BEYAZ]:
            m.add_command(label=f"→ {RENK_ETIKET[renk]}",
                            command=lambda r=renk: self._secilenleri_boya_uygula(
                                list(self.tv.selection()), r))
        m.add_separator()
        m.add_command(label="Detay Göster", command=self._satir_detay)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _satir_detay(self, event=None):
        sec = self.tv.selection()
        if not sec:
            return
        iid = sec[0]
        s = self.satir_indeks.get(iid)
        if not s:
            return
        win = tk.Toplevel(self.root)
        win.title(f"Detay — {s.get('rec_no')} / {s.get('ilac')}")
        win.geometry("780x600")
        txt = tk.Text(win, wrap="word", font=("Segoe UI", 9))
        txt.pack(fill="both", expand=True)
        for kod, baslik, _gen, _tip in SUTUNLAR:
            txt.insert("end", f"{baslik}: ", "lbl")
            txt.insert("end", f"{s.get(kod, '')}\n\n")
        txt.tag_configure("lbl", font=("Segoe UI", 9, "bold"), foreground="#1976D2")
        txt.config(state="disabled")

    def _sutuna_gore_sirala(self, kod: str):
        """Excel benzeri sütun başlığına tıklayarak sırala (asc/desc/reset toggle)."""
        # 3-aşamalı toggle: önce asc, sonra desc, sonra orijinal
        if self._siralama_kolonu == kod:
            if self._siralama_yonu == "asc":
                self._siralama_yonu = "desc"
            elif self._siralama_yonu == "desc":
                # Reset
                self._siralama_kolonu = None
                self._siralama_yonu = None
            else:
                self._siralama_yonu = "asc"
        else:
            self._siralama_kolonu = kod
            self._siralama_yonu = "asc"

        # Başlıklarda göstergeyi güncelle (▲ ▼ ↕)
        self._siralama_gostergesini_guncelle()

        # Sıralama uygula
        if self._siralama_kolonu is None:
            # Orijinal sıraya dön — DB'den yüklenen sıra zaten korundu mu?
            # Güvenlik: tum_satirlar yeni sıraya göre değişmiş olabilir.
            # Sadece tabloyu yenile (filtreleri uygulayarak)
            self._tabloyu_yenile()
            return

        # Sayısal vs string kararı (ilk dolu değere bak)
        ornekler = [s.get(kod, "") for s in self.tum_satirlar[:50] if s.get(kod)]
        sayisal_mi = bool(ornekler) and all(
            self._sayiya_cevrilebilir_mi(o) for o in ornekler[:10])

        rev = (self._siralama_yonu == "desc")
        if sayisal_mi:
            self.tum_satirlar.sort(
                key=lambda s: self._sayiya_cevir(s.get(kod, "")), reverse=rev)
        else:
            self.tum_satirlar.sort(
                key=lambda s: str(s.get(kod, "") or "").lower(), reverse=rev)
        self._tabloyu_yenile()

    @staticmethod
    def _sayiya_cevrilebilir_mi(v) -> bool:
        try:
            float(str(v).replace(",", "."))
            return True
        except Exception:
            return False

    @staticmethod
    def _sayiya_cevir(v) -> float:
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return -float("inf")

    def _siralama_gostergesini_guncelle(self):
        """Sütun başlıklarına ▲/▼ (sıralama) ve 🔽 (filtre) göstergeleri ekle."""
        try:
            for kod, baslik, _gen, _tip in SUTUNLAR:
                etiket = baslik
                # Sıralama göstergesi
                if kod == self._siralama_kolonu:
                    etiket += " ▲" if self._siralama_yonu == "asc" else " ▼"
                # Filtre göstergesi (Excel'deki gibi) — değer veya metin filtresi
                if kod in self.aktif_deger_filtre or kod in self.aktif_metin_filtre:
                    etiket += " 🔽"
                self.tv.heading(kod, text=etiket)
        except Exception:
            pass

    # ----------------------------------------------------------- SÜTUN AYAR
    def _sutun_ayarlarini_yukle(self):
        """Hangi sütunların görünür olduğunu JSON'dan yükle."""
        try:
            if os.path.exists(self.SUTUN_AYAR_DOSYASI):
                with open(self.SUTUN_AYAR_DOSYASI, "r", encoding="utf-8") as f:
                    kayit = json.load(f)
                for kod in SUTUN_KOD:
                    if kod in kayit:
                        self.sutun_gosterim[kod] = bool(kayit[kod])
        except Exception:
            pass

    def _sutun_ayarlarini_kaydet(self):
        try:
            with open(self.SUTUN_AYAR_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.sutun_gosterim, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sutun_ayar_penceresi(self):
        """Sütun göster/gizle popup penceresi."""
        win = tk.Toplevel(self.root)
        win.title("Sütun Ayarları")
        win.geometry("420x680")
        win.transient(self.root)

        tk.Label(win, text="Görünmesini istediğin sütunları işaretle:",
                 font=("Segoe UI", 10, "bold")).pack(pady=8, padx=8, anchor="w")

        # Scroll
        cont = tk.Frame(win)
        cont.pack(fill="both", expand=True, padx=8)
        canvas = tk.Canvas(cont, highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        gecici = {kod: tk.BooleanVar(value=self.sutun_gosterim.get(kod, True))
                   for kod in SUTUN_KOD}
        for kod, baslik, _gen, tip in SUTUNLAR:
            row = tk.Frame(inner)
            row.pack(fill="x", padx=6, pady=1)
            tk.Checkbutton(row, text=f"{baslik}", variable=gecici[kod],
                            anchor="w", font=("Segoe UI", 9)
                            ).pack(side="left", padx=4)
            tk.Label(row, text=f"({tip[:50]})", fg="#9E9E9E",
                     font=("Segoe UI", 8)).pack(side="left", padx=4)
        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # Hızlı işlemler
        ust = tk.Frame(win)
        ust.pack(fill="x", padx=8, pady=4)
        tk.Button(ust, text="Tümü Göster", bg="#C8E6C9",
                  command=lambda: [v.set(True) for v in gecici.values()]
                  ).pack(side="left", padx=2)
        tk.Button(ust, text="Tümü Gizle", bg="#FFCDD2",
                  command=lambda: [v.set(False) for v in gecici.values()]
                  ).pack(side="left", padx=2)
        tk.Button(ust, text="Varsayılan",
                  command=lambda: [v.set(True) for v in gecici.values()]
                  ).pack(side="left", padx=2)

        # Kaydet/iptal
        alt = tk.Frame(win)
        alt.pack(fill="x", padx=8, pady=8)

        def _uygula():
            for kod, var in gecici.items():
                self.sutun_gosterim[kod] = var.get()
            self._sutun_ayarlarini_kaydet()
            self._sutun_gorunumunu_uygula()
            win.destroy()

        tk.Button(alt, text="Uygula", bg="#1976D2", fg="white",
                  command=_uygula, padx=14
                  ).pack(side="right", padx=4)
        tk.Button(alt, text="İptal", command=win.destroy
                  ).pack(side="right", padx=4)

    def _sutun_gorunumunu_uygula(self):
        """sutun_gosterim'e göre Treeview'da kolon görünürlüğünü ve
        filtre satırındaki slot'ları senkron ayarla."""
        try:
            gorunenler = [k for k in SUTUN_KOD if self.sutun_gosterim.get(k, True)]
            self.tv["displaycolumns"] = gorunenler
        except Exception:
            pass
        # Filtre satırı slot'larını gizle/göster + güncel sütun genişliklerine
        # göre boyutlandır (sütun yeniden boyutlandırma sonrası hizalı kalsın)
        try:
            slotlar = getattr(self, "_filtre_slotlar", []) or []
            toplam_gen = 0
            for (kod, _baslik, gen, _tip), slot in zip(SUTUNLAR, slotlar):
                if self.sutun_gosterim.get(kod, True):
                    # Tablodaki anlık genişliği oku
                    try:
                        w = int(self.tv.column(kod, "width"))
                    except Exception:
                        w = gen
                    slot.config(width=w)
                    # İçerideki Entry'yi de güncelle
                    for child in slot.winfo_children():
                        if isinstance(child, tk.Entry):
                            child.place_configure(width=max(10, w - 2))
                    slot.pack(side="left")
                    toplam_gen += w
                else:
                    slot.pack_forget()
            if hasattr(self, "_filtre_canvas"):
                self._filtre_canvas.config(
                    scrollregion=(0, 0, toplam_gen,
                                   getattr(self, "_filtre_h", 28)))
        except Exception as e:
            logger.debug("filtre slot görünürlüğü: %s", e)

    def _filtre_slotlarini_hizala(self):
        """Tablonun anlık sütun genişliklerine göre filtre slotlarını
        yeniden boyutlandır. Sütun manuel resize edildiğinde çağrılır."""
        try:
            slotlar = getattr(self, "_filtre_slotlar", []) or []
            if not slotlar:
                return
            toplam = 0
            for (kod, _baslik, gen, _tip), slot in zip(SUTUNLAR, slotlar):
                if not self.sutun_gosterim.get(kod, True):
                    continue
                try:
                    w = int(self.tv.column(kod, "width"))
                except Exception:
                    w = gen
                slot.config(width=w)
                for child in slot.winfo_children():
                    if isinstance(child, tk.Entry):
                        child.place_configure(width=max(10, w - 2))
                toplam += w
            if hasattr(self, "_filtre_canvas"):
                self._filtre_canvas.config(
                    scrollregion=(0, 0, toplam,
                                   getattr(self, "_filtre_h", 28)))
        except Exception as e:
            logger.debug("filtre slot hizalama: %s", e)

    # ----------------------------------------------------------- STATE
    def _state_kaydet(self):
        """Tüm renk durumlarını dönem bazında JSON'a yaz."""
        if not self.aktif_donem:
            return
        try:
            tum = {}
            if os.path.exists(self.STATE_DOSYASI):
                with open(self.STATE_DOSYASI, "r", encoding="utf-8") as f:
                    tum = json.load(f)
            # Sadece beyaz olmayanları kaydet (yer tasarrufu)
            donem_state = {iid: r for iid, r in self.satir_renkleri.items()
                            if r != RENK_BEYAZ}
            if donem_state:
                tum[self.aktif_donem] = donem_state
            elif self.aktif_donem in tum:
                del tum[self.aktif_donem]
            with open(self.STATE_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(tum, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("State kaydet: %s", e)

    def _state_yukle_donem(self, donem: str) -> dict:
        try:
            if not os.path.exists(self.STATE_DOSYASI):
                return {}
            with open(self.STATE_DOSYASI, "r", encoding="utf-8") as f:
                tum = json.load(f)
            return tum.get(donem, {}) or {}
        except Exception:
            return {}

    # ----------------------------------------------------------- EXCEL EXPORT
    def _excel_export(self):
        if not self.tum_satirlar:
            messagebox.showwarning("Uyarı", "Aktarılacak veri yok")
            return
        try:
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment
        except ImportError:
            messagebox.showerror("Hata", "openpyxl yüklü değil")
            return

        donem = self.aktif_donem or "tum"
        masa = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        if not os.path.exists(masa):
            masa = os.path.expanduser("~")
        path = filedialog.asksaveasfilename(
            initialdir=masa,
            initialfile=f"Aylik_Inceleme_{donem}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = donem

        # Başlıklar
        for c, (kod, baslik, _gen, _tip) in enumerate(SUTUNLAR, 1):
            cell = ws.cell(row=1, column=c, value=baslik)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="263238")
            cell.alignment = Alignment(horizontal="center")

        # Renk fill mapping
        excel_fill = {
            RENK_BEYAZ:   None,
            RENK_YESIL:   PatternFill("solid", fgColor="C8E6C9"),
            RENK_SARI:    PatternFill("solid", fgColor="FFF9C4"),
            RENK_TURUNCU: PatternFill("solid", fgColor="FFE0B2"),
            RENK_KIRMIZI: PatternFill("solid", fgColor="FFCDD2"),
        }

        for ri, s in enumerate(self.tum_satirlar, 2):
            iid = str(s["ri_id"])
            renk = self.satir_renkleri.get(iid, RENK_BEYAZ)
            fill = excel_fill.get(renk)
            for ci, kod in enumerate(SUTUN_KOD, 1):
                cell = ws.cell(row=ri, column=ci, value=str(s.get(kod, "")))
                if fill:
                    cell.fill = fill

        # Sütun genişlikleri
        for ci, (_kod, _baslik, gen, _tip) in enumerate(SUTUNLAR, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = max(8, gen / 7)

        try:
            wb.save(path)
            self._durum_yaz(f"Excel kaydedildi: {path}")
            if messagebox.askyesno("Tamamlandı",
                                     f"Excel kaydedildi:\n{path}\n\nAçılsın mı?"):
                os.startfile(path)
        except Exception as e:
            messagebox.showerror("Hata", f"Excel kaydedilemedi: {e}")

    # ───────────────────────────────────────────────────────────────────
    # STATİN / LİPİD SUT KONTROLÜ
    # ───────────────────────────────────────────────────────────────────
    # Lipid sınıfı tespiti için ATC C10* öncelikli; ATC dolu olmayan eski
    # kayıtlar için ticari isim fallback'leri.
    _LIPID_AD_FALLBACK = (
        "STATIN", "ATORVAS", "ROSUVAS", "SIMVAS", "PRAVAS", "FLUVAS",
        "PITAVAS", "EZETIMIB", "EZETROL", "INEGY",
        "LIPITOR", "CRESTOR", "ROZACT", "ROSUVA", "ATOR", "LIPVAS",
        "ULTROX", "ZOCOR", "ALVASTIN", "KOLESTER", "PRAVATOR",
        "FENOFIB", "GEMFIB", "BEZAFIB", "SIPROFIB",
        "LIPANTHYL", "LIPANTIL", "TRALIP", "LIPOFEN", "LOPID",
        "OMACOR", "REPATHA", "PRALUENT", "EVOLOKUMAB", "ALIROKUMAB",
    )

    @staticmethod
    def _lipid_kategori(ilac_adi: str, etkin: str, atc: str) -> str:
        """Satırın STATIN / FIBRAT / DIGER_LIPID / NONE olarak sınıflandırması.

        ATC önceliklidir (WHO ATC C10):
          - C10AA / C10BA / C10BX → STATIN (statin veya statin-kombin)
          - C10AB                 → FIBRAT
          - C10AC / C10AD / C10AX → DIGER_LIPID (ezetimib tek başına dahil)
        ATC boşsa ticari isim/etken ipuçları kullanılır.
        """
        a = (atc or "").upper().strip()
        if a.startswith("C10AA") or a.startswith("C10BA") or a.startswith("C10BX"):
            return "STATIN"
        if a.startswith("C10AB"):
            return "FIBRAT"
        if a.startswith("C10AC") or a.startswith("C10AD") or a.startswith("C10AX"):
            return "DIGER_LIPID"
        ad = (ilac_adi or "").upper()
        et = (etkin or "").upper()
        statin_ipuc = ("STATIN", "ATORVAS", "ROSUVAS", "SIMVAS", "PRAVAS",
                       "FLUVAS", "PITAVAS", "LIPITOR", "CRESTOR", "ROZACT",
                       "EZETIMIB", "EZETROL", "INEGY")
        fibrat_ipuc = ("FENOFIB", "GEMFIB", "BEZAFIB", "SIPROFIB",
                       "LIPANTHYL", "LIPANTIL", "TRALIP", "LIPOFEN", "LOPID")
        if any(s in ad for s in statin_ipuc) or any(s in et for s in statin_ipuc):
            return "STATIN"
        if any(s in ad for s in fibrat_ipuc) or any(s in et for s in fibrat_ipuc):
            return "FIBRAT"
        return "NONE"

    @staticmethod
    def _ilac_sonuc_olustur(s: dict) -> dict:
        """Satır dict'inden kontrol_statin/kontrol_fibrat'ın beklediği
        ilac_sonuc dict'ini üret."""
        def _bol(metin):
            if not metin:
                return []
            # Bu modülün satır birleştiricisi " | " kullanıyor.
            return [p.strip() for p in str(metin).split(" | ") if p.strip()]

        rapor_aciklamalari = []
        rap_ack = s.get("rap_ack")
        if rap_ack:
            rapor_aciklamalari.append(str(rap_ack).strip())
        # Rapor teşhisleri de rapor metnine dahil — LDL/risk faktörü
        # ICD'leri burada olabilir (RaporRaporKodlariICD)
        for t in _bol(s.get("rap_tesh")):
            rapor_aciklamalari.append(t)

        return {
            "ilac_adi": s.get("ilac") or "",
            "rapor_kodu": (s.get("rap_kod") or "").strip(),
            "rapor_kodu_aciklama": "",
            "recete_teshisleri": _bol(s.get("rec_tesh")),
            "rapor_aciklamalari": rapor_aciklamalari,
            "recete_aciklamalari": _bol(s.get("rec_ack")),
            "mesaj_metni": "",
        }

    # ───────────────────────────────────────────────────────────────────
    # DİYABET (SUT 4.2.38) KATEGORİ TESPİTİ + ilac_sonuc üreticisi
    # ───────────────────────────────────────────────────────────────────
    @staticmethod
    def _diyabet_kategori(ilac_adi: str, etkin: str, atc: str) -> str:
        """Satırın diyabet ilacı olup olmadığını ATC A10* önceliği ve
        ad/etken fallback'i ile sınıflandırır.

        Dönüş: "DIYABET" / "NONE"
        """
        a = (atc or "").upper().strip()
        if a.startswith("A10"):
            return "DIYABET"
        ad = (ilac_adi or "").upper()
        et = (etkin or "").upper()
        arama = ad + " " + et
        diyabet_etken = (
            "METFORMIN", "GLIKLAZID", "GLICLAZID", "GLIMEPIRID",
            "GLIBENKLAMID", "GLIPIZID", "REPAGLINID", "NATEGLINID",
            "PIOGLITAZON", "AKARBOZ", "ACARBOSE",
            "SITAGLIPTIN", "VILDAGLIPTIN", "SAKSAGLIPTIN", "LINAGLIPTIN",
            "ALOGLIPTIN",
            "EMPAGLIFLOZIN", "DAPAGLIFLOZIN", "KANAGLIFLOZIN",
            "CANAGLIFLOZIN", "ERTUGLIFLOZIN",
            "LIRAGLUTID", "SEMAGLUTID", "DULAGLUTID", "EKSENATID",
            "EXENATID", "LIKSISENATID", "LIXISENATID",
            "INSULIN", "INSÜLIN", "GLARGIN", "DETEMIR", "DEGLUDEC",
            "ASPART", "LISPRO", "GLULIZIN",
        )
        diyabet_ticari = (
            "GLIFOR", "GLUKOFEN", "DIAFORMIN", "GLUCOPHAGE", "MATOFIN",
            "DIAMICRON", "BETANORM", "DIAMERID", "AMARYL", "GLIMAX",
            "MERIDIA", "GLIBEDAL", "DAONIL", "GLUKOMID",
            "MINIDIAB", "GLUCOTROL", "NOVONORM", "STARLIX",
            "ACTOS", "GLUSTIN", "PIONORM", "GLUCOBAY",
            "JANUVIA", "GALVUS", "ONGLYZA", "TRAJENTA", "NESINA",
            "JANUMET", "GALVUSMET", "KOMBOGLYZE", "JENTADUETO", "VIPDOMET",
            "JARDIANCE", "FORZIGA", "FORXIGA", "INVOKANA", "STEGLATRO",
            "SYNJARDY", "XIGDUO", "VOKANAMET", "SEGLUROMET",
            "GLYXAMBI", "QTERN", "STEGLUJAN",
            "VICTOZA", "OZEMPIC", "RYBELSUS", "TRULICITY", "BYETTA",
            "BYDUREON", "SAXENDA", "LYXUMIA", "WEGOVY",
            "LANTUS", "TOUJEO", "TRESIBA", "LEVEMIR", "BASAGLAR",
            "ABASAGLAR", "NOVORAPID", "HUMALOG", "APIDRA", "ACTRAPID",
            "HUMULIN", "NOVOMIX", "RYZODEG", "XULTOPHY", "SOLIQUA",
        )
        if any(k in arama for k in diyabet_etken):
            return "DIYABET"
        if any(k in arama for k in diyabet_ticari):
            return "DIYABET"
        return "NONE"

    @staticmethod
    def _diyabet_alt_sinif(ilac_adi: str, etkin: str, atc: str) -> str:
        """Diyabet ilacı için alt sınıf (rapor tablosu kategori sütunu).

        ATC A10* alt-kodlarına göre:
          A10A*  → INSULIN
          A10BA  → BIGUANID (metformin)
          A10BB  → SULFONILURE
          A10BD  → KOMBI_OAD (sabit kombi: DPP4+met, SGLT2+met, vb.)
          A10BG  → TZD (pioglitazon)
          A10BH  → DPP4
          A10BJ  → GLP1
          A10BK  → SGLT2
          A10BX  → DIGER (glinid, alfa-glukozidaz vb.)
        ATC boşsa ad/etken bazlı fallback uygulanır.
        """
        a = (atc or "").upper().strip()
        if a.startswith("A10A"):
            return "INSULIN"
        if a.startswith("A10BA"): return "BIGUANID"
        if a.startswith("A10BB"): return "SULFONILURE"
        if a.startswith("A10BD"): return "KOMBI_OAD"
        if a.startswith("A10BG"): return "TZD"
        if a.startswith("A10BH"): return "DPP4"
        if a.startswith("A10BJ"): return "GLP1"
        if a.startswith("A10BK"): return "SGLT2"
        if a.startswith("A10BX"): return "DIGER"
        ad = (ilac_adi or "").upper()
        et = (etkin or "").upper()
        arama = ad + " " + et
        if any(k in arama for k in ("DAPAGLIFLOZIN", "EMPAGLIFLOZIN",
                                     "KANAGLIFLOZIN", "CANAGLIFLOZIN",
                                     "ERTUGLIFLOZIN", "JARDIANCE", "FORZIGA",
                                     "FORXIGA", "INVOKANA", "STEGLATRO")):
            # SGLT-2 sabit kombiler
            if any(k in arama for k in ("SYNJARDY", "XIGDUO", "VOKANAMET",
                                          "SEGLUROMET", "GLYXAMBI", "QTERN",
                                          "STEGLUJAN")):
                return "KOMBI_OAD"
            return "SGLT2"
        if any(k in arama for k in ("SITAGLIPTIN", "VILDAGLIPTIN",
                                     "SAKSAGLIPTIN", "LINAGLIPTIN", "ALOGLIPTIN",
                                     "JANUVIA", "GALVUS", "ONGLYZA", "TRAJENTA",
                                     "NESINA")):
            if any(k in arama for k in ("JANUMET", "GALVUSMET", "KOMBOGLYZE",
                                          "JENTADUETO", "VIPDOMET")):
                return "KOMBI_OAD"
            return "DPP4"
        if any(k in arama for k in ("LIRAGLUTID", "SEMAGLUTID", "DULAGLUTID",
                                     "EKSENATID", "EXENATID", "LIKSISENATID",
                                     "LIXISENATID", "VICTOZA", "OZEMPIC",
                                     "RYBELSUS", "TRULICITY", "BYETTA",
                                     "BYDUREON", "SAXENDA", "WEGOVY", "LYXUMIA")):
            return "GLP1"
        if any(k in arama for k in ("METFORMIN", "GLIFOR", "GLUKOFEN",
                                     "DIAFORMIN", "GLUCOPHAGE", "MATOFIN")):
            return "BIGUANID"
        if any(k in arama for k in ("GLIKLAZID", "GLICLAZID", "GLIMEPIRID",
                                     "GLIBENKLAMID", "GLIPIZID", "DIAMICRON",
                                     "AMARYL", "GLIMAX", "DAONIL", "GLUKOMID",
                                     "MINIDIAB", "GLUCOTROL", "BETANORM",
                                     "DIAMERID", "GLIBEDAL")):
            return "SULFONILURE"
        if any(k in arama for k in ("REPAGLINID", "NATEGLINID", "NOVONORM",
                                     "STARLIX")):
            return "GLINID"
        if any(k in arama for k in ("PIOGLITAZON", "ACTOS", "GLUSTIN", "PIONORM")):
            return "TZD"
        if any(k in arama for k in ("AKARBOZ", "ACARBOSE", "GLUCOBAY")):
            return "AKARBOZ"
        if any(k in arama for k in ("INSULIN", "INSÜLIN", "GLARGIN", "DETEMIR",
                                     "DEGLUDEC", "ASPART", "LISPRO", "GLULIZIN",
                                     "LANTUS", "TOUJEO", "TRESIBA", "LEVEMIR",
                                     "BASAGLAR", "ABASAGLAR", "NOVORAPID",
                                     "HUMALOG", "APIDRA", "ACTRAPID", "HUMULIN",
                                     "NOVOMIX", "RYZODEG", "XULTOPHY", "SOLIQUA")):
            return "INSULIN"
        return "DIGER"

    @staticmethod
    def _ilac_sonuc_olustur_diyabet(s: dict, diger_ilac_adlari: list) -> dict:
        """Satır dict'inden kontrol_diyabet_dpp4_sglt2'nin beklediği
        ilac_sonuc dict'ini üret.

        diger_ilac_adlari: aynı reçetedeki DİĞER ilaçların adları
                            (kombinasyon yasağı kontrolü — DPP-4 + GLP-1 vb.)
        """
        def _bol(metin):
            if not metin:
                return []
            return [p.strip() for p in str(metin).split(" | ") if p.strip()]

        rapor_aciklamalari = []
        rap_ack = s.get("rap_ack")
        if rap_ack:
            rapor_aciklamalari.append(str(rap_ack).strip())
        for t in _bol(s.get("rap_tesh")):
            rapor_aciklamalari.append(t)

        return {
            "ilac_adi": s.get("ilac") or "",
            "etkin_madde": s.get("etkin") or "",
            "atc_kodu": s.get("atc") or "",
            "rapor_kodu": (s.get("rap_kod") or "").strip(),
            "rapor_kodu_aciklama": "",
            "recete_teshisleri": _bol(s.get("rec_tesh")),
            "rapor_aciklamalari": rapor_aciklamalari,
            "recete_aciklamalari": _bol(s.get("rec_ack")),
            "mesaj_metni": "",
            "doktor_uzmanligi": s.get("brans") or "",
            "hasta_yasi": s.get("yas") or "",
            "recete_dozu": s.get("rec_doz") or "",
            "recete_ilaclari": [{"ad": x} for x in (diger_ilac_adlari or []) if x],
        }

    def _hasta_tum_icd_kodlarini_topla(self, musteri_idler: List[int]) -> Dict[int, List[str]]:
        """Verilen hastaların TÜM aktif raporlarındaki ICD kodlarını + rapor
        kodlarını + ICD açıklamalarını toplu olarak çek.

        Returns: {musteri_id: ['E11.9 Tip 2 DM', 'I25 Koroner', ...]}

        Bu sayede statin denetimi sırasında, ilgili hastanın bir BAŞKA
        raporunda DM/KAH varsa o tanı statin satırına da yansıtılır → risk
        faktörü algoritmik olarak doğru değerlendirilir.
        """
        if not musteri_idler or not self.db:
            return {}
        result: Dict[int, List[str]] = {}
        try:
            for i in range(0, len(musteri_idler), 500):
                chunk = [m for m in musteri_idler[i:i + 500] if m]
                if not chunk:
                    continue
                ph = ",".join("?" * len(chunk))
                rows = self.db.sorgu_calistir(
                    f"""SELECT
                            ra.RaporAnaMusteriId AS musteri_id,
                            i.ICDKodu             AS icd_kodu,
                            i.ICDAciklamasi       AS icd_aciklamasi,
                            rk.RaporKodu          AS rapor_kodu,
                            rk.RaporKodAciklama   AS rapor_kod_aciklama
                        FROM RaporRaporKodlariICD rrki
                        INNER JOIN RaporAna ra
                                ON ra.RaporAnaId = rrki.RRKIRaporAnaId
                        LEFT JOIN ICD i
                                ON i.ICDId = rrki.RRKIICDId
                        LEFT JOIN RaporKodlari rk
                                ON rk.RaporKodId = rrki.RRKIRaporKodId
                        WHERE ra.RaporAnaMusteriId IN ({ph})
                          AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)
                          AND (ra.RaporAnaSilme IS NULL OR ra.RaporAnaSilme = 0)""",
                    tuple(chunk))
                for r in rows:
                    mid = r.get("musteri_id")
                    if not mid:
                        continue
                    parcalar = []
                    icd_k = (r.get("icd_kodu") or "").strip()
                    icd_a = (r.get("icd_aciklamasi") or "").strip()
                    if icd_k and icd_a:
                        parcalar.append(f"{icd_k} {icd_a}")
                    elif icd_k:
                        parcalar.append(icd_k)
                    rk_k = (r.get("rapor_kodu") or "").strip()
                    rk_a = (r.get("rapor_kod_aciklama") or "").strip()
                    if rk_k and rk_a:
                        parcalar.append(f"[Rap {rk_k}] {rk_a}")
                    for p in parcalar:
                        if p:
                            result.setdefault(mid, []).append(p)
        except Exception as e:
            logger.warning("Hasta ICD toplu sorgu fail: %s", e)
        # Tekrarsız + temiz
        return {k: list(dict.fromkeys(v)) for k, v in result.items()}

    def _statin_kontrol_baslat(self):
        """STATİN KONTROL butonu — yüklenen satırlardan statin/lipid (ATC C10*)
        olanları SUT 4.2.28.A/B kuralına göre denetler ve sonucu en sağdaki
        SONUÇ sütununa yazar.

        ÖNEMLİ: Hasta'nın bu reçetede sadece statinin kendi raporu değil, TÜM
        aktif raporlarındaki ICD kodları da risk faktörü tespiti için
        kullanılır (DM/KAH/inme ayrı bir raporda olabilir)."""
        if not self.tum_satirlar:
            messagebox.showinfo(
                "Statin Kontrol",
                "Önce DÖNEM seçip 🔍 SORGULA ile reçeteleri yükleyin.",
                parent=self.root)
            return
        try:
            from recete_kontrol.sut_kontrolleri import (
                kontrol_statin, kontrol_fibrat,
            )
            from recete_kontrol.base_kontrol import KontrolSonucu
        except Exception as e:
            self._durum_yaz(f"SUT kontrol modülü yüklenemedi: {e}")
            messagebox.showerror(
                "Modül Hatası",
                f"recete_kontrol modülü yüklenemedi:\n{e}",
                parent=self.root)
            return

        # Hastaların TÜM raporlarındaki ICD kodlarını topla (cross-rapor risk)
        musteri_idler = list({
            s.get("musteri_id") for s in self.tum_satirlar
            if s.get("musteri_id")
        })
        self._durum_yaz(
            f"Statin kontrol — {len(musteri_idler)} hastanın "
            "diğer raporları taranıyor…")
        self.root.update_idletasks()
        hasta_tum_icd = self._hasta_tum_icd_kodlarini_topla(musteri_idler)

        VERDICT_ETIKET = {
            KontrolSonucu.UYGUN:             "UYGUN",
            KontrolSonucu.UYGUN_DEGIL:       "UYGUN DEĞİL",
            KontrolSonucu.KONTROL_EDILEMEDI: "ŞÜPHELİ",
            KontrolSonucu.ATLANDI:           "ATLANDI",
        }
        sayac = {"UYGUN": 0, "UYGUN DEĞİL": 0,
                 "ŞÜPHELİ": 0, "ATLANDI": 0, "_lipid_disi": 0}
        # Rapor için kategoriye göre ayrım da tutulur
        kategori_sayac = {"STATIN": 0, "FIBRAT": 0, "DIGER_LIPID": 0}
        denetlenen_satirlar = []  # rapor için (lipid olanlar)

        # Önceki çalıştırmadan kalan verdict'leri temizle (lipid olmayanlar
        # her zaman boş kalsın, lipid olanlar yeniden hesaplansın)
        for s in self.tum_satirlar:
            kategori = self._lipid_kategori(
                s.get("ilac"), s.get("etkin"), s.get("atc"))
            if kategori == "NONE":
                # Sadece kendi kategorimizin (lipid) önceki artığını sil —
                # diyabet vb. başka kontrollerin verdict'lerine dokunma.
                if s.get("verdict_kategori") in ("STATIN", "FIBRAT", "DIGER_LIPID"):
                    s["verdict"] = ""
                    s["verdict_detay"] = ""
                    s["verdict_kategori"] = ""
                    s["verdict_uyari"] = ""
                    s["verdict_sut"] = ""
                    s["verdict_aranan"] = ""
                    s["verdict_bulunan"] = ""
                    s["verdict_detaylar"] = ""
                sayac["_lipid_disi"] += 1
                continue
            kategori_sayac[kategori] = kategori_sayac.get(kategori, 0) + 1
            ilac_sonuc = self._ilac_sonuc_olustur(s)
            # Hastanın diğer raporlarındaki ICD/rapor kodlarını da
            # recete_teshisleri'ne ekle — DM/KAH ayrı raporda yazılıysa
            # risk faktörü tespiti için statin algoritması bunları görsün.
            mid = s.get("musteri_id")
            ek_icd = hasta_tum_icd.get(mid, []) if mid else []
            if ek_icd:
                # Çift kayıt önlemek için tekilleştir
                mevcut = set(ilac_sonuc.get("recete_teshisleri", []))
                for code in ek_icd:
                    if code not in mevcut:
                        ilac_sonuc.setdefault(
                            "recete_teshisleri", []).append(code)
            try:
                if kategori == "FIBRAT":
                    rapor = kontrol_fibrat(ilac_sonuc)
                else:
                    # STATIN ve DIGER_LIPID için aynı kural (LDL/risk mantığı)
                    rapor = kontrol_statin(ilac_sonuc)
            except Exception as e:
                logger.warning("Statin kontrol hata (rx %s): %s",
                                s.get("rec_no"), e)
                s["verdict"] = "ŞÜPHELİ"
                s["verdict_detay"] = f"Hata: {e}"
                s["verdict_kategori"] = kategori
                s["verdict_uyari"] = ""
                s["verdict_sut"] = ""
                s["verdict_aranan"] = ""
                s["verdict_bulunan"] = ""
                s["verdict_detaylar"] = ""
                sayac["ŞÜPHELİ"] += 1
                denetlenen_satirlar.append(s)
                continue
            etiket = VERDICT_ETIKET.get(rapor.sonuc, "ŞÜPHELİ")
            s["verdict"] = etiket
            s["verdict_detay"] = rapor.mesaj or ""
            s["verdict_kategori"] = kategori
            s["verdict_uyari"] = rapor.uyari or ""
            s["verdict_sut"] = rapor.sut_kurali or ""
            s["verdict_aranan"] = rapor.aranan_ibare or ""
            s["verdict_bulunan"] = rapor.bulunan_metin or ""
            # detaylar dict — string'e çevir (Excel'e güvenle yazılsın)
            try:
                s["verdict_detaylar"] = json.dumps(rapor.detaylar or {},
                                                    ensure_ascii=False)
            except Exception:
                s["verdict_detaylar"] = str(rapor.detaylar or {})
            sayac[etiket] = sayac.get(etiket, 0) + 1
            denetlenen_satirlar.append(s)

        # Tabloyu yenile (mevcut filtre/renk durumuna saygı duyarak)
        self._tabloyu_yenile()
        self._durum_yaz(
            f"Statin/Lipid SUT kontrolü: "
            f"✓ UYGUN {sayac['UYGUN']}  "
            f"✗ UYGUN DEĞİL {sayac['UYGUN DEĞİL']}  "
            f"? ŞÜPHELİ {sayac['ŞÜPHELİ']}  "
            f"− ATLANDI {sayac['ATLANDI']}  "
            f"(lipid dışı {sayac['_lipid_disi']} satır boş bırakıldı)"
        )

        # ── KONTROL RAPORU ÜRET ──
        toplam_lipid = (sayac["UYGUN"] + sayac["UYGUN DEĞİL"]
                        + sayac["ŞÜPHELİ"] + sayac["ATLANDI"])
        if toplam_lipid == 0:
            messagebox.showinfo(
                "Statin Kontrol",
                "Bu dönemde statin/lipid grubuna giren reçete bulunamadı.",
                parent=self.root)
            return

        cevap = messagebox.askyesno(
            "Kontrol Raporu",
            f"Statin/Lipid SUT kontrolü tamamlandı.\n\n"
            f"Toplam lipid satırı : {toplam_lipid}\n"
            f"  ✓ UYGUN          : {sayac['UYGUN']}\n"
            f"  ✗ UYGUN DEĞİL    : {sayac['UYGUN DEĞİL']}\n"
            f"  ? ŞÜPHELİ        : {sayac['ŞÜPHELİ']}\n"
            f"  − ATLANDI        : {sayac['ATLANDI']}\n"
            f"Lipid dışı (atlanan): {sayac['_lipid_disi']}\n\n"
            f"Kontrol raporu Excel olarak masaüstündeki "
            f"'Reçete Kontrol' klasörüne kaydedilecek.\n\n"
            f"Rapor oluşturulup açılsın mı?",
            parent=self.root)
        if not cevap:
            return

        try:
            rapor_yolu = self._statin_rapor_excel_olustur(
                sayac=sayac,
                kategori_sayac=kategori_sayac,
                denetlenen_satirlar=denetlenen_satirlar,
            )
        except Exception as e:
            logger.exception("Statin rapor üretim hatası")
            messagebox.showerror(
                "Rapor Hatası",
                f"Kontrol raporu oluşturulamadı:\n{e}",
                parent=self.root)
            return

        # Aç
        try:
            os.startfile(rapor_yolu)
            self._durum_yaz(f"Kontrol raporu: {rapor_yolu}")
        except Exception as e:
            messagebox.showinfo(
                "Rapor Kaydedildi",
                f"Rapor kaydedildi ama otomatik açılamadı:\n{rapor_yolu}\n\n{e}",
                parent=self.root)

    # ── KONTROL RAPORU EXCEL ÜRETİCİ ────────────────────────────────────
    def _statin_rapor_excel_olustur(self, *, sayac: dict, kategori_sayac: dict,
                                      denetlenen_satirlar: list) -> str:
        """Masaüstü/Reçete Kontrol/ klasörüne kapsamlı Excel raporu yazar.

        3 sayfa:
          - Özet : Toplam sayım, kategori dağılımı, çalışma zamanı, dönem
          - Lipid Reçeteleri : Denetlenen her satır + SUT detayları + verdict
          - Lipid Dışı : Atlanan satırların kısa özeti (sadece sayım/listeleme)

        Returns: oluşturulan dosyanın tam yolu.
        """
        try:
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError as e:
            raise RuntimeError("openpyxl yüklü değil") from e

        from datetime import datetime as _dt

        # Hedef klasör: ~/Desktop/Reçete Kontrol  (OneDrive\Desktop varsa o)
        masa = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        if not os.path.exists(masa):
            masa = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(masa):
                masa = os.path.expanduser("~")
        klasor = os.path.join(masa, "Reçete Kontrol")
        os.makedirs(klasor, exist_ok=True)

        donem = self.aktif_donem or "tum"
        zaman = _dt.now().strftime("%Y%m%d_%H%M%S")
        dosya_adi = f"Statin_Kontrol_{donem}_{zaman}.xlsx"
        path = os.path.join(klasor, dosya_adi)

        wb = openpyxl.Workbook()

        # ────────── SAYFA 1: ÖZET ──────────
        ws1 = wb.active
        ws1.title = "Özet"

        VERDICT_RENK = {
            "UYGUN":       "C8E6C9",  # yeşil
            "UYGUN DEĞİL": "FFCDD2",  # kırmızı
            "ŞÜPHELİ":     "FFE0B2",  # turuncu
            "ATLANDI":     "ECEFF1",  # gri
        }
        baslik_font = Font(bold=True, color="FFFFFF", size=11)
        baslik_fill = PatternFill("solid", fgColor="263238")
        toplam_lipid = (sayac["UYGUN"] + sayac["UYGUN DEĞİL"]
                        + sayac["ŞÜPHELİ"] + sayac["ATLANDI"])

        ws1.cell(row=1, column=1, value="STATİN / LİPİD SUT KONTROL RAPORU")
        ws1.cell(row=1, column=1).font = Font(bold=True, size=14, color="0D47A1")
        ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)

        bilgi_satirlari = [
            ("Dönem (Yıl-Ay)", donem),
            ("Rapor Üretim Tarihi", _dt.now().strftime("%d.%m.%Y %H:%M:%S")),
            ("Toplam Yüklenen Satır", str(len(self.tum_satirlar))),
            ("Lipid Olarak Tespit Edilen", str(toplam_lipid)),
            ("Lipid Dışı (Atlanan)", str(sayac["_lipid_disi"])),
            ("", ""),
            ("Uygulanan SUT Kuralları",
             "SUT 4.2.28.A (Statin) · SUT 4.2.28.B (Fibrat)"),
            ("Filtreleme",
             "ATC C10* (lipid modifying agents) + ticari isim fallback"),
            ("Veri Kaynağı",
             "Botanik EOS DB (SADECE SELECT) — hiçbir veri değiştirilmedi"),
        ]
        for i, (etk, deg) in enumerate(bilgi_satirlari, start=3):
            c1 = ws1.cell(row=i, column=1, value=etk)
            c2 = ws1.cell(row=i, column=2, value=deg)
            if etk:
                c1.font = Font(bold=True, color="37474F")
            c2.font = Font(color="0D47A1")
            ws1.merge_cells(start_row=i, start_column=2, end_row=i, end_column=4)

        # Sonuç dağılımı tablosu
        bas = len(bilgi_satirlari) + 4
        ws1.cell(row=bas, column=1, value="SONUÇ DAĞILIMI")
        ws1.cell(row=bas, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas, start_column=1,
                        end_row=bas, end_column=4)

        bas += 1
        for col, hd in enumerate(["Sonuç", "Adet", "Yüzde", ""], start=1):
            c = ws1.cell(row=bas, column=col, value=hd)
            c.font = baslik_font
            c.fill = baslik_fill
            c.alignment = Alignment(horizontal="center")
        for i, etiket in enumerate(["UYGUN", "UYGUN DEĞİL",
                                     "ŞÜPHELİ", "ATLANDI"], start=bas + 1):
            adet = sayac[etiket]
            yuzde = (adet / toplam_lipid * 100) if toplam_lipid else 0
            c1 = ws1.cell(row=i, column=1, value=etiket)
            c2 = ws1.cell(row=i, column=2, value=adet)
            c3 = ws1.cell(row=i, column=3, value=f"%{yuzde:.1f}")
            fill = PatternFill("solid", fgColor=VERDICT_RENK[etiket])
            for c in (c1, c2, c3):
                c.fill = fill
                c.font = Font(bold=True)
            c2.alignment = Alignment(horizontal="center")
            c3.alignment = Alignment(horizontal="center")

        # Kategori dağılımı
        bas2 = bas + 6
        ws1.cell(row=bas2, column=1, value="KATEGORİ DAĞILIMI (lipid satırları)")
        ws1.cell(row=bas2, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas2, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas2, start_column=1,
                        end_row=bas2, end_column=4)
        bas2 += 1
        for col, hd in enumerate(["Kategori", "Adet", "Açıklama", ""],
                                  start=1):
            c = ws1.cell(row=bas2, column=col, value=hd)
            c.font = baslik_font
            c.fill = baslik_fill
            c.alignment = Alignment(horizontal="center")
        kat_aciklama = {
            "STATIN":       "ATC C10AA/C10BA/C10BX — atorvastatin, rosuvastatin, simvastatin, pravastatin, fluvastatin, pitavastatin + statin kombinleri",
            "FIBRAT":       "ATC C10AB — fenofibrat (Lipanthyl/Lipantil/Tralip/Lipofen), gemfibrozil, bezafibrat",
            "DIGER_LIPID":  "ATC C10AC/AD/AX — ezetimib tek başına, kolestiramin, omega-3, PCSK9 (Repatha/Praluent)",
        }
        for i, k in enumerate(["STATIN", "FIBRAT", "DIGER_LIPID"],
                               start=bas2 + 1):
            ws1.cell(row=i, column=1, value=k).font = Font(bold=True)
            ws1.cell(row=i, column=2, value=kategori_sayac.get(k, 0)
                     ).alignment = Alignment(horizontal="center")
            ws1.cell(row=i, column=3, value=kat_aciklama[k])

        # Notlar
        bas3 = bas2 + 5
        ws1.cell(row=bas3, column=1, value="NOTLAR")
        ws1.cell(row=bas3, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas3, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas3, start_column=1,
                        end_row=bas3, end_column=4)
        notlar = [
            "• UYGUN = SUT kuralı algoritmik olarak doğrulandı (LDL eşik + risk faktörü vb.)",
            "• UYGUN DEĞİL = Algoritmik kural net şekilde ihlal — manuel inceleme önerilir",
            "• ŞÜPHELİ = Karar verilemedi (eksik LDL/TG değeri, eksik teşhis vb.) — manuel kontrol",
            "• ATLANDI = SUT denetimi gerekmeyen satır",
            "• Lipid dışı = ATC C10* dışında olduğu için bu butonun kapsamına girmiyor",
            "• 'Lipid Reçeteleri' sayfasında her satırın hangi metni okuduğu, "
            "neyi aradığı ve ne bulduğu yazılır.",
        ]
        for i, n in enumerate(notlar, start=bas3 + 1):
            ws1.cell(row=i, column=1, value=n)
            ws1.merge_cells(start_row=i, start_column=1,
                            end_row=i, end_column=8)

        # Sütun genişlikleri (özet)
        for col, w in enumerate([34, 22, 60, 12], start=1):
            ws1.column_dimensions[get_column_letter(col)].width = w

        # ────────── SAYFA 2: LİPİD REÇETELERİ (denetlenen) ──────────
        ws2 = wb.create_sheet("Lipid Reçeteleri")
        # Sütunlar: tabloya yansıyanların hepsi + SUT denetim detayları
        kolonlar = [
            ("rec_tar",          "Reç.Tarih",       12),
            ("rec_no",           "Reçete No",       18),
            ("hasta",            "Hasta",           24),
            ("tc",               "TC",              13),
            ("yas",              "Yaş",             6),
            ("cins",             "Cin.",            6),
            ("doktor",           "Doktor",          22),
            ("brans",            "Branş",           18),
            ("ilac",             "İlaç",            28),
            ("etkin",            "Etken Madde",     22),
            ("atc",              "ATC",             10),
            ("verdict_kategori", "Kategori",        12),
            ("rap_kod",          "Rapor Kod",       11),
            ("rec_doz",          "Reçete Doz",      14),
            ("rap_doz",          "Rapor Doz",       14),
            ("kutu",             "Kutu",            6),
            ("msj",              "Msj",             7),
            ("uyari",            "Uyarı Kod",       18),
            ("medula_msj",       "Medula Msj",      30),
            ("rec_tesh",         "Reçete Teşhis",   30),
            ("rap_tesh",         "Rapor Teşhis",    30),
            ("rec_ack",          "Reçete Açıklama", 30),
            ("rap_ack",          "Rapor Açıklama",  30),
            ("verdict_sut",      "Uygulanan SUT",   30),
            ("verdict_aranan",   "Aranan İbare",    28),
            ("verdict_bulunan",  "Bulunan Metin",   28),
            ("verdict_detaylar", "SUT Detaylar (LDL/risk/...)", 38),
            ("verdict_uyari",    "Uyarı",           34),
            ("verdict_detay",    "Açıklama",        50),
            ("verdict",          "SONUÇ",           14),
        ]
        for c, (_kod, baslik, _g) in enumerate(kolonlar, 1):
            cell = ws2.cell(row=1, column=c, value=baslik)
            cell.font = baslik_font
            cell.fill = baslik_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        ws2.row_dimensions[1].height = 28
        ws2.freeze_panes = "A2"

        # Veri satırları
        for ri, s in enumerate(denetlenen_satirlar, start=2):
            for ci, (kod, _baslik, _g) in enumerate(kolonlar, start=1):
                deger = s.get(kod, "")
                cell = ws2.cell(row=ri, column=ci, value=str(deger))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            # SONUÇ sütununu (en sondaki) renge boya
            verdict = s.get("verdict") or ""
            renk = VERDICT_RENK.get(verdict)
            if renk:
                son_col = len(kolonlar)
                vcell = ws2.cell(row=ri, column=son_col)
                vcell.fill = PatternFill("solid", fgColor=renk)
                vcell.font = Font(bold=True)
                vcell.alignment = Alignment(horizontal="center", vertical="center")

        # Sütun genişlikleri
        for ci, (_kod, _baslik, gen) in enumerate(kolonlar, 1):
            ws2.column_dimensions[get_column_letter(ci)].width = gen

        # Otomatik filtre
        ws2.auto_filter.ref = ws2.dimensions

        # ────────── SAYFA 3: LİPİD DIŞI (atlanmış) ──────────
        ws3 = wb.create_sheet("Lipid Dışı (Atlanan)")
        ws3.cell(row=1, column=1,
                 value="Aşağıdaki ilaçlar ATC C10* (lipid) sınıfına girmediği "
                       "için statin/lipid butonu KAPSAMI DIŞINDA bırakıldı.").font = (
            Font(italic=True, color="546E7A"))
        ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)

        atlanan_kolonlar = [
            ("rec_tar", "Reç.Tarih", 12),
            ("rec_no",  "Reçete No", 18),
            ("hasta",   "Hasta",     24),
            ("ilac",    "İlaç",      30),
            ("etkin",   "Etken",     22),
            ("atc",     "ATC",       10),
        ]
        for c, (_k, b, _g) in enumerate(atlanan_kolonlar, 1):
            cell = ws3.cell(row=3, column=c, value=b)
            cell.font = baslik_font
            cell.fill = baslik_fill
            cell.alignment = Alignment(horizontal="center")
        # Atlananları topla
        ri = 4
        for s in self.tum_satirlar:
            kategori = self._lipid_kategori(
                s.get("ilac"), s.get("etkin"), s.get("atc"))
            if kategori != "NONE":
                continue
            for ci, (kod, _b, _g) in enumerate(atlanan_kolonlar, 1):
                ws3.cell(row=ri, column=ci, value=str(s.get(kod, "")))
            ri += 1
        for ci, (_k, _b, gen) in enumerate(atlanan_kolonlar, 1):
            ws3.column_dimensions[get_column_letter(ci)].width = gen
        ws3.freeze_panes = "A4"

        wb.save(path)
        return path

    # ───────────────────────────────────────────────────────────────────
    # DİYABET (SUT 4.2.38) SUT KONTROLÜ — DPP-4 / SGLT-2 / GLP-1 + klasik OAD + insülin
    # ───────────────────────────────────────────────────────────────────
    def _diyabet_kontrol_baslat(self):
        """DİYABET KONTROL butonu — yüklenen satırlardan diyabet ilaçları
        (ATC A10*) SUT 4.2.38'e göre denetlenir; sonuç en sağdaki SONUÇ
        sütununa UYGUN / UYGUN DEĞİL / ŞÜPHELİ olarak yazılır.

        Kapsanan ilaç sınıfları:
          • Biguanid (metformin), Sülfonilüre, Glinid, Akarboz, TZD
          • DPP-4 inhibitörleri (sitagliptin, vildagliptin, ...)
          • SGLT-2 inhibitörleri (empa/dapa/kana/ertugliflozin)
          • GLP-1 RA (liraglutid, semaglutid, dulaglutid, ...)
          • İnsülinler (kısa/orta/uzun etkili, kombi)
          • Sabit kombiler (DPP4+met, SGLT2+met, SGLT2+DPP4)

        SUT 4.2.38(7): GLP-1 RA → BMI ≥ 30 + HbA1c ≥ %7 + metformin maks doz
        SUT 4.2.38(8): DPP-4 + GLP-1 RA birlikte ödenmez (kombinasyon yasağı)
        """
        if not self.tum_satirlar:
            messagebox.showinfo(
                "Diyabet Kontrol",
                "Önce DÖNEM seçip 🔍 SORGULA ile reçeteleri yükleyin.",
                parent=self.root)
            return
        try:
            from recete_kontrol.sut_kontrolleri import kontrol_diyabet_dpp4_sglt2
            from recete_kontrol.base_kontrol import KontrolSonucu
        except Exception as e:
            self._durum_yaz(f"SUT kontrol modülü yüklenemedi: {e}")
            messagebox.showerror(
                "Modül Hatası",
                f"recete_kontrol modülü yüklenemedi:\n{e}",
                parent=self.root)
            return

        VERDICT_ETIKET = {
            KontrolSonucu.UYGUN:             "UYGUN",
            KontrolSonucu.UYGUN_DEGIL:       "UYGUN DEĞİL",
            KontrolSonucu.KONTROL_EDILEMEDI: "ŞÜPHELİ",
            KontrolSonucu.ATLANDI:           "ATLANDI",
        }
        sayac = {"UYGUN": 0, "UYGUN DEĞİL": 0,
                 "ŞÜPHELİ": 0, "ATLANDI": 0, "_diyabet_disi": 0}
        # Alt sınıf bazlı sayım (raporlama için)
        kategori_sayac = {"INSULIN": 0, "BIGUANID": 0, "SULFONILURE": 0,
                          "GLINID": 0, "TZD": 0, "AKARBOZ": 0,
                          "DPP4": 0, "SGLT2": 0, "GLP1": 0,
                          "KOMBI_OAD": 0, "DIGER": 0}
        denetlenen_satirlar = []

        # ── Reçete bazlı ilaç gruplaması (kombinasyon yasağı kontrolü için) ──
        # Aynı rec_no'ya sahip diğer ilaçların adları → DPP-4 + GLP-1 yasağı vb.
        recete_ilac_grup: Dict[str, List[str]] = {}
        for s in self.tum_satirlar:
            rno = s.get("rec_no")
            if rno:
                recete_ilac_grup.setdefault(str(rno), []).append(
                    s.get("ilac") or "")

        # ── Hastanın diğer raporlarındaki ICD/rapor kodlarını çek ──
        # (KY/KBH varsa SGLT-2 kuralı buna göre değişir)
        musteri_idler = []
        for s in self.tum_satirlar:
            mid = s.get("musteri_id")
            if mid and mid not in musteri_idler:
                musteri_idler.append(mid)
        hasta_tum_icd = self._hasta_tum_icd_kodlarini_topla(musteri_idler)

        for s in self.tum_satirlar:
            kategori = self._diyabet_kategori(
                s.get("ilac"), s.get("etkin"), s.get("atc"))
            if kategori == "NONE":
                # Sadece kendi kategorimizin (DIYABET) önceki artığını sil —
                # statin/lipid verdict'lerine dokunma.
                if s.get("verdict_kategori") == "DIYABET":
                    s["verdict"] = ""
                    s["verdict_detay"] = ""
                    s["verdict_kategori"] = ""
                    s["verdict_uyari"] = ""
                    s["verdict_sut"] = ""
                    s["verdict_aranan"] = ""
                    s["verdict_bulunan"] = ""
                    s["verdict_detaylar"] = ""
                sayac["_diyabet_disi"] += 1
                continue

            alt_sinif = self._diyabet_alt_sinif(
                s.get("ilac"), s.get("etkin"), s.get("atc"))
            kategori_sayac[alt_sinif] = kategori_sayac.get(alt_sinif, 0) + 1

            # Aynı reçetedeki diğer ilaçların adları (kendisi hariç)
            rno = str(s.get("rec_no") or "")
            kendi_ad = (s.get("ilac") or "").upper()
            diger_adlar = [x for x in recete_ilac_grup.get(rno, [])
                            if x and x.upper() != kendi_ad]

            ilac_sonuc = self._ilac_sonuc_olustur_diyabet(s, diger_adlar)

            # Hastanın diğer raporlarındaki ICD'leri ekle (KY/KBH tespiti için)
            mid = s.get("musteri_id")
            ek_icd = hasta_tum_icd.get(mid, []) if mid else []
            if ek_icd:
                mevcut = set(ilac_sonuc.get("recete_teshisleri", []))
                for code in ek_icd:
                    if code not in mevcut:
                        ilac_sonuc.setdefault(
                            "recete_teshisleri", []).append(code)

            try:
                rapor = kontrol_diyabet_dpp4_sglt2(ilac_sonuc)
            except Exception as e:
                logger.warning("Diyabet kontrol hata (rx %s): %s",
                                s.get("rec_no"), e)
                s["verdict"] = "ŞÜPHELİ"
                s["verdict_detay"] = f"Hata: {e}"
                s["verdict_kategori"] = "DIYABET"
                s["verdict_alt_sinif"] = alt_sinif
                s["verdict_uyari"] = ""
                s["verdict_sut"] = ""
                s["verdict_aranan"] = ""
                s["verdict_bulunan"] = ""
                s["verdict_detaylar"] = ""
                sayac["ŞÜPHELİ"] += 1
                denetlenen_satirlar.append(s)
                continue

            etiket = VERDICT_ETIKET.get(rapor.sonuc, "ŞÜPHELİ")
            s["verdict"] = etiket
            s["verdict_detay"] = rapor.mesaj or ""
            s["verdict_kategori"] = "DIYABET"
            s["verdict_alt_sinif"] = alt_sinif
            s["verdict_uyari"] = rapor.uyari or ""
            s["verdict_sut"] = rapor.sut_kurali or ""
            s["verdict_aranan"] = rapor.aranan_ibare or ""
            s["verdict_bulunan"] = rapor.bulunan_metin or ""
            try:
                s["verdict_detaylar"] = json.dumps(rapor.detaylar or {},
                                                    ensure_ascii=False)
            except Exception:
                s["verdict_detaylar"] = str(rapor.detaylar or {})
            sayac[etiket] = sayac.get(etiket, 0) + 1
            denetlenen_satirlar.append(s)

        # Tabloyu yenile (mevcut filtre/renk durumuna saygı duyarak)
        self._tabloyu_yenile()
        self._durum_yaz(
            f"Diyabet SUT 4.2.38 kontrolü: "
            f"✓ UYGUN {sayac['UYGUN']}  "
            f"✗ UYGUN DEĞİL {sayac['UYGUN DEĞİL']}  "
            f"? ŞÜPHELİ {sayac['ŞÜPHELİ']}  "
            f"− ATLANDI {sayac['ATLANDI']}  "
            f"(diyabet dışı {sayac['_diyabet_disi']} satır boş bırakıldı)"
        )

        toplam_diyabet = (sayac["UYGUN"] + sayac["UYGUN DEĞİL"]
                          + sayac["ŞÜPHELİ"] + sayac["ATLANDI"])
        if toplam_diyabet == 0:
            messagebox.showinfo(
                "Diyabet Kontrol",
                "Bu dönemde diyabet ilacı (ATC A10*) bulunamadı.",
                parent=self.root)
            return

        cevap = messagebox.askyesno(
            "Kontrol Raporu",
            f"Diyabet SUT 4.2.38 kontrolü tamamlandı.\n\n"
            f"Toplam diyabet satırı : {toplam_diyabet}\n"
            f"  ✓ UYGUN          : {sayac['UYGUN']}\n"
            f"  ✗ UYGUN DEĞİL    : {sayac['UYGUN DEĞİL']}\n"
            f"  ? ŞÜPHELİ        : {sayac['ŞÜPHELİ']}\n"
            f"  − ATLANDI        : {sayac['ATLANDI']}\n"
            f"Diyabet dışı (atlanan): {sayac['_diyabet_disi']}\n\n"
            f"Kontrol raporu Excel olarak masaüstündeki "
            f"'Reçete Kontrol' klasörüne kaydedilecek.\n\n"
            f"Rapor oluşturulup açılsın mı?",
            parent=self.root)
        if not cevap:
            return

        try:
            rapor_yolu = self._diyabet_rapor_excel_olustur(
                sayac=sayac,
                kategori_sayac=kategori_sayac,
                denetlenen_satirlar=denetlenen_satirlar,
            )
        except Exception as e:
            logger.exception("Diyabet rapor üretim hatası")
            messagebox.showerror(
                "Rapor Hatası",
                f"Kontrol raporu oluşturulamadı:\n{e}",
                parent=self.root)
            return

        try:
            os.startfile(rapor_yolu)
            self._durum_yaz(f"Kontrol raporu: {rapor_yolu}")
        except Exception as e:
            messagebox.showinfo(
                "Rapor Kaydedildi",
                f"Rapor kaydedildi ama otomatik açılamadı:\n{rapor_yolu}\n\n{e}",
                parent=self.root)

    # ── DİYABET KONTROL RAPORU EXCEL ÜRETİCİ ────────────────────────────
    def _diyabet_rapor_excel_olustur(self, *, sayac: dict, kategori_sayac: dict,
                                       denetlenen_satirlar: list) -> str:
        """Masaüstü/Reçete Kontrol/ klasörüne kapsamlı Excel raporu yazar.

        3 sayfa:
          - Özet : Toplam sayım, alt sınıf dağılımı, çalışma zamanı, dönem
          - Diyabet Reçeteleri : Denetlenen her satır + SUT detayları + verdict
          - Diyabet Dışı : Atlanan satırların kısa özeti

        Returns: oluşturulan dosyanın tam yolu.
        """
        try:
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError as e:
            raise RuntimeError("openpyxl yüklü değil") from e

        from datetime import datetime as _dt

        masa = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        if not os.path.exists(masa):
            masa = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(masa):
                masa = os.path.expanduser("~")
        klasor = os.path.join(masa, "Reçete Kontrol")
        os.makedirs(klasor, exist_ok=True)

        donem = self.aktif_donem or "tum"
        zaman = _dt.now().strftime("%Y%m%d_%H%M%S")
        dosya_adi = f"Diyabet_Kontrol_{donem}_{zaman}.xlsx"
        path = os.path.join(klasor, dosya_adi)

        wb = openpyxl.Workbook()

        # ────────── SAYFA 1: ÖZET ──────────
        ws1 = wb.active
        ws1.title = "Özet"

        VERDICT_RENK = {
            "UYGUN":       "C8E6C9",
            "UYGUN DEĞİL": "FFCDD2",
            "ŞÜPHELİ":     "FFE0B2",
            "ATLANDI":     "ECEFF1",
        }
        baslik_font = Font(bold=True, color="FFFFFF", size=11)
        baslik_fill = PatternFill("solid", fgColor="0D47A1")
        toplam_diyabet = (sayac["UYGUN"] + sayac["UYGUN DEĞİL"]
                          + sayac["ŞÜPHELİ"] + sayac["ATLANDI"])

        ws1.cell(row=1, column=1, value="DİYABET SUT 4.2.38 KONTROL RAPORU")
        ws1.cell(row=1, column=1).font = Font(bold=True, size=14, color="0D47A1")
        ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)

        bilgi_satirlari = [
            ("Dönem (Yıl-Ay)", donem),
            ("Rapor Üretim Tarihi", _dt.now().strftime("%d.%m.%Y %H:%M:%S")),
            ("Toplam Yüklenen Satır", str(len(self.tum_satirlar))),
            ("Diyabet Olarak Tespit Edilen", str(toplam_diyabet)),
            ("Diyabet Dışı (Atlanan)", str(sayac["_diyabet_disi"])),
            ("", ""),
            ("Uygulanan SUT Kuralı",
             "SUT 4.2.38 — Diyabet (DPP-4 / SGLT-2 / GLP-1 RA + klasik OAD + insülin)"),
            ("Kapsam",
             "ATC A10* (insülin + oral antidiyabetikler) + ad/etken fallback"),
            ("Aranan İbare (DPP-4/SGLT-2/GLP-1)",
             "Metformin ve sülfonilürelerin maksimum tolere edilebilir "
             "dozlarında yeterli glisemik kontrol sağlanamamıştır"),
            ("Veri Kaynağı",
             "Botanik EOS DB (SADECE SELECT) — hiçbir veri değiştirilmedi"),
        ]
        for i, (etk, deg) in enumerate(bilgi_satirlari, start=3):
            c1 = ws1.cell(row=i, column=1, value=etk)
            c2 = ws1.cell(row=i, column=2, value=deg)
            if etk:
                c1.font = Font(bold=True, color="37474F")
            c2.font = Font(color="0D47A1")
            c2.alignment = Alignment(wrap_text=True, vertical="top")
            ws1.merge_cells(start_row=i, start_column=2, end_row=i, end_column=4)

        # Sonuç dağılımı
        bas = len(bilgi_satirlari) + 4
        ws1.cell(row=bas, column=1, value="SONUÇ DAĞILIMI")
        ws1.cell(row=bas, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas, start_column=1, end_row=bas, end_column=4)
        bas += 1
        for col, hd in enumerate(["Sonuç", "Adet", "Yüzde", ""], start=1):
            c = ws1.cell(row=bas, column=col, value=hd)
            c.font = baslik_font
            c.fill = baslik_fill
            c.alignment = Alignment(horizontal="center")
        for i, etiket in enumerate(["UYGUN", "UYGUN DEĞİL",
                                     "ŞÜPHELİ", "ATLANDI"], start=bas + 1):
            adet = sayac[etiket]
            yuzde = (adet / toplam_diyabet * 100) if toplam_diyabet else 0
            c1 = ws1.cell(row=i, column=1, value=etiket)
            c2 = ws1.cell(row=i, column=2, value=adet)
            c3 = ws1.cell(row=i, column=3, value=f"%{yuzde:.1f}")
            fill = PatternFill("solid", fgColor=VERDICT_RENK[etiket])
            for c in (c1, c2, c3):
                c.fill = fill
                c.font = Font(bold=True)
            c2.alignment = Alignment(horizontal="center")
            c3.alignment = Alignment(horizontal="center")

        # Alt sınıf dağılımı
        bas2 = bas + 6
        ws1.cell(row=bas2, column=1, value="ALT SINIF DAĞILIMI (diyabet ilaçları)")
        ws1.cell(row=bas2, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas2, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas2, start_column=1, end_row=bas2, end_column=4)
        bas2 += 1
        for col, hd in enumerate(["Alt Sınıf", "Adet", "Açıklama", ""], start=1):
            c = ws1.cell(row=bas2, column=col, value=hd)
            c.font = baslik_font
            c.fill = baslik_fill
            c.alignment = Alignment(horizontal="center")
        sinif_aciklama = {
            "INSULIN":     "ATC A10A — bazal/hızlı/orta/uzun etkili insülinler + kombi",
            "BIGUANID":    "ATC A10BA — METFORMIN (Glifor, Glukofen, Diaformin)",
            "SULFONILURE": "ATC A10BB — gliklazid, glimepirid, glibenklamid, glipizid",
            "GLINID":      "ATC A10BX — repaglinid (Novonorm), nateglinid (Starlix)",
            "TZD":         "ATC A10BG — pioglitazon (Actos)",
            "AKARBOZ":     "ATC A10BF — alfa-glukozidaz inhibitörü (Glucobay)",
            "DPP4":        "ATC A10BH — sitagliptin/Januvia, vildagliptin/Galvus, linagliptin/Trajenta",
            "SGLT2":       "ATC A10BK — empagliflozin/Jardiance, dapagliflozin/Forziga, kanagliflozin/Invokana",
            "GLP1":        "ATC A10BJ — liraglutid/Victoza, semaglutid/Ozempic, dulaglutid/Trulicity",
            "KOMBI_OAD":   "ATC A10BD — sabit kombiler (Janumet, Galvusmet, Synjardy, Xigduo, Glyxambi)",
            "DIGER":       "Yukarıdaki sınıflara girmeyen diyabet ilaçları",
        }
        sinif_sira = ["INSULIN", "BIGUANID", "SULFONILURE", "GLINID", "TZD",
                      "AKARBOZ", "DPP4", "SGLT2", "GLP1", "KOMBI_OAD", "DIGER"]
        for i, k in enumerate(sinif_sira, start=bas2 + 1):
            ws1.cell(row=i, column=1, value=k).font = Font(bold=True)
            ws1.cell(row=i, column=2, value=kategori_sayac.get(k, 0)
                     ).alignment = Alignment(horizontal="center")
            ws1.cell(row=i, column=3, value=sinif_aciklama[k])

        # Notlar
        bas3 = bas2 + len(sinif_sira) + 3
        ws1.cell(row=bas3, column=1, value="NOTLAR")
        ws1.cell(row=bas3, column=1).font = Font(bold=True, color="FFFFFF")
        ws1.cell(row=bas3, column=1).fill = baslik_fill
        ws1.merge_cells(start_row=bas3, start_column=1, end_row=bas3, end_column=4)
        notlar = [
            "• UYGUN = SUT 4.2.38 algoritmik olarak doğrulandı (rapor + glisemik şart + uzman/branş + lab)",
            "• UYGUN DEĞİL = Algoritmik kural net ihlal — manuel inceleme önerilir",
            "• ŞÜPHELİ = Karar verilemedi (eksik HbA1c/BMI/eGFR, eksik teşhis, vb.) — manuel kontrol",
            "• ATLANDI = SUT denetimi gerekmeyen satır (klasik OAD + diyabet tanısı + raporsuz)",
            "• Diyabet dışı = ATC A10* dışında olduğu için bu butonun kapsamına girmiyor",
            "• DPP-4/SGLT-2/GLP-1 için aranan ibare: 'metformin ve sülfonilürelerin maksimum "
            "tolere edilebilir dozlarında yeterli glisemik kontrol sağlanamamıştır'",
            "• GLP-1 RA için ek şart: BMI ≥ 30 + HbA1c ≥ %7 (rapor metninden taranır)",
            "• DPP-4 + GLP-1 RA aynı reçetede ÖDENMEZ (SUT 4.2.38(8) — kombinasyon yasağı)",
            "• 'Diyabet Reçeteleri' sayfasında her satırın hangi metni okuduğu, "
            "neyi aradığı ve ne bulduğu yazılır.",
        ]
        for i, n in enumerate(notlar, start=bas3 + 1):
            ws1.cell(row=i, column=1, value=n)
            ws1.merge_cells(start_row=i, start_column=1, end_row=i, end_column=8)

        for col, w in enumerate([34, 22, 60, 12], start=1):
            ws1.column_dimensions[get_column_letter(col)].width = w

        # ────────── SAYFA 2: DİYABET REÇETELERİ (denetlenen) ──────────
        ws2 = wb.create_sheet("Diyabet Reçeteleri")
        kolonlar = [
            ("rec_tar",          "Reç.Tarih",       12),
            ("rec_no",           "Reçete No",       18),
            ("hasta",            "Hasta",           24),
            ("tc",               "TC",              13),
            ("yas",              "Yaş",             6),
            ("cins",             "Cin.",            6),
            ("doktor",           "Doktor",          22),
            ("brans",            "Branş",           18),
            ("ilac",             "İlaç",            28),
            ("etkin",            "Etken Madde",     22),
            ("atc",              "ATC",             10),
            ("verdict_alt_sinif", "Alt Sınıf",      12),
            ("rap_kod",          "Rapor Kod",       11),
            ("rec_doz",          "Reçete Doz",      14),
            ("rap_doz",          "Rapor Doz",       14),
            ("kutu",             "Kutu",            6),
            ("msj",              "Msj",             7),
            ("uyari",            "Uyarı Kod",       18),
            ("medula_msj",       "Medula Msj",      30),
            ("rec_tesh",         "Reçete Teşhis",   30),
            ("rap_tesh",         "Rapor Teşhis",    30),
            ("rec_ack",          "Reçete Açıklama", 30),
            ("rap_ack",          "Rapor Açıklama",  30),
            ("verdict_sut",      "Uygulanan SUT",   30),
            ("verdict_aranan",   "Aranan İbare",    28),
            ("verdict_bulunan",  "Bulunan Metin",   28),
            ("verdict_detaylar", "SUT Detaylar (HbA1c/BMI/eGFR/...)", 38),
            ("verdict_uyari",    "Uyarı",           34),
            ("verdict_detay",    "Açıklama",        50),
            ("verdict",          "SONUÇ",           14),
        ]
        for c, (_kod, baslik, _g) in enumerate(kolonlar, 1):
            cell = ws2.cell(row=1, column=c, value=baslik)
            cell.font = baslik_font
            cell.fill = baslik_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        ws2.row_dimensions[1].height = 28
        ws2.freeze_panes = "A2"

        for ri, s in enumerate(denetlenen_satirlar, start=2):
            for ci, (kod, _baslik, _g) in enumerate(kolonlar, start=1):
                deger = s.get(kod, "")
                cell = ws2.cell(row=ri, column=ci, value=str(deger))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            verdict = s.get("verdict") or ""
            renk = VERDICT_RENK.get(verdict)
            if renk:
                son_col = len(kolonlar)
                vcell = ws2.cell(row=ri, column=son_col)
                vcell.fill = PatternFill("solid", fgColor=renk)
                vcell.font = Font(bold=True)
                vcell.alignment = Alignment(horizontal="center", vertical="center")

        for ci, (_kod, _baslik, gen) in enumerate(kolonlar, 1):
            ws2.column_dimensions[get_column_letter(ci)].width = gen

        ws2.auto_filter.ref = ws2.dimensions

        # ────────── SAYFA 3: DİYABET DIŞI (atlanmış) ──────────
        ws3 = wb.create_sheet("Diyabet Dışı (Atlanan)")
        ws3.cell(row=1, column=1,
                 value="Aşağıdaki ilaçlar ATC A10* (diyabet) sınıfına girmediği "
                       "için diyabet butonu KAPSAMI DIŞINDA bırakıldı.").font = (
            Font(italic=True, color="546E7A"))
        ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)

        atlanan_kolonlar = [
            ("rec_tar", "Reç.Tarih", 12),
            ("rec_no",  "Reçete No", 18),
            ("hasta",   "Hasta",     24),
            ("ilac",    "İlaç",      30),
            ("etkin",   "Etken",     22),
            ("atc",     "ATC",       10),
        ]
        for c, (_k, b, _g) in enumerate(atlanan_kolonlar, 1):
            cell = ws3.cell(row=3, column=c, value=b)
            cell.font = baslik_font
            cell.fill = baslik_fill
            cell.alignment = Alignment(horizontal="center")
        ri = 4
        for s in self.tum_satirlar:
            kategori = self._diyabet_kategori(
                s.get("ilac"), s.get("etkin"), s.get("atc"))
            if kategori != "NONE":
                continue
            for ci, (kod, _b, _g) in enumerate(atlanan_kolonlar, 1):
                ws3.cell(row=ri, column=ci, value=str(s.get(kod, "")))
            ri += 1
        for ci, (_k, _b, gen) in enumerate(atlanan_kolonlar, 1):
            ws3.column_dimensions[get_column_letter(ci)].width = gen
        ws3.freeze_panes = "A4"

        wb.save(path)
        return path

    # ----------------------------------------------------------- DURUM
    def _durum_yaz(self, msg: str):
        try:
            self.durum_bar.config(text=msg)
        except Exception:
            pass

    def _kapat(self):
        try:
            self._state_kaydet()
        except Exception:
            pass
        try:
            if self.db:
                self.db.kapat()
        except Exception:
            pass
        if self.ana_menu_callback:
            try:
                self.root.destroy()
                self.ana_menu_callback()
                return
            except Exception:
                pass
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    root = tk.Tk()
    AylikReceteSorguGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
