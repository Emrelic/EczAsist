"""
Aylık İnceleme & Filtreleme Tablosu (Botanik EOS)

Kullanıcının manuel inceleme akışı için tek tablo + çoklu filtre + boyama.
Her satır = bir reçete-ilaç kombinasyonu.

GÜVENLİK: Yalnızca SELECT — BotanikDB.sorgu_calistir güvenlik filtresi kullanılır.
Hiçbir INSERT/UPDATE/DELETE yapılmaz.

Akış:
1. Yıl-Ay seç → Sorgula → tüm aylık reçete-ilaç satırları tabloya gelir (BEYAZ)
2. Üstteki sütun arama kutuları ve sağdaki hızlı filtre butonları ile filtre uygula
3. Filtre sonucu görünenleri "Görünenleri Yeşile Boya" ile ele
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

RENK_BG = {
    RENK_BEYAZ:   "#FFFFFF",
    RENK_YESIL:   "#C8E6C9",
    RENK_SARI:    "#FFF9C4",
    RENK_TURUNCU: "#FFE0B2",
    RENK_KIRMIZI: "#FFCDD2",
}
RENK_FG = {
    RENK_BEYAZ:   "#212121",
    RENK_YESIL:   "#1B5E20",
    RENK_SARI:    "#827717",
    RENK_TURUNCU: "#E65100",
    RENK_KIRMIZI: "#B71C1C",
}
RENK_ETIKET = {
    RENK_BEYAZ:   "Beklemede",
    RENK_YESIL:   "Uygun (Elendi)",
    RENK_SARI:    "Manuel Kontrol",
    RENK_TURUNCU: "Şüpheli",
    RENK_KIRMIZI: "Uygunsuz",
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
    ("uyari",      "Uyarı Kod",    90,  "Reçete uyarı kodları"),
    ("rec_tesh",   "Reç.Teşhis",   150, "Reçete teşhisleri"),
    ("rap_tesh",   "Rap.Teşhis",   150, "Rapor teşhisleri"),
    ("rec_ack",    "Reç.Açk",      180, "Reçete açıklamaları"),
    ("rap_ack",    "Rap.Açk",      180, "Rapor açıklamaları"),
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
# ANA SINIF
# ═══════════════════════════════════════════════════════════════════════
class AylikReceteSorguGUI:
    """Aylık reçete-ilaç inceleme & filtreleme tablosu."""

    STATE_DOSYASI = "aylik_inceleme_state.json"
    SUTUN_AYAR_DOSYASI = "aylik_inceleme_sutun_ayarlari.json"

    def __init__(self, root: tk.Tk, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("Aylık İnceleme & Filtreleme (Botanik EOS — Salt Okunur)")
        self.root.geometry("1700x920")
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
                                    RENK_TURUNCU, RENK_KIRMIZI}

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
        # ───── ÜST BAŞLIK ─────
        ust = tk.Frame(self.root, bg="#263238", height=42)
        ust.pack(fill="x")
        ust.pack_propagate(False)
        tk.Label(ust, text="📋 Aylık İnceleme & Filtreleme (Botanik EOS — Salt Okunur)",
                 font=("Arial", 12, "bold"), bg="#263238", fg="white"
                ).pack(side="left", padx=15, pady=8)
        tk.Button(ust, text="Ana Menüye Dön", command=self._kapat,
                  bg="#455A64", fg="white", bd=0, padx=12
                  ).pack(side="right", padx=15, pady=6)

        # ───── SATIR 1: Yıl/Ay/Sorgula + Sayım + Sağ butonlar ─────
        ust2 = tk.Frame(self.root, bg="#ECEFF1", pady=4)
        ust2.pack(fill="x", padx=6)

        tk.Label(ust2, text="Yıl:", bg="#ECEFF1").pack(side="left", padx=(6, 2))
        self.var_yil = tk.StringVar()
        self.cb_yil = ttk.Combobox(ust2, textvariable=self.var_yil,
                                    width=6, state="readonly")
        self.cb_yil.pack(side="left", padx=2)
        self.cb_yil.bind("<<ComboboxSelected>>", self._yil_degisti)

        tk.Label(ust2, text="Ay:", bg="#ECEFF1").pack(side="left", padx=(8, 2))
        self.var_ay = tk.StringVar()
        self.cb_ay = ttk.Combobox(ust2, textvariable=self.var_ay,
                                   width=12, state="readonly")
        self.cb_ay.pack(side="left", padx=2)

        tk.Button(ust2, text="🔍 Sorgula", bg="#1976D2", fg="white",
                  command=self._receteleri_sorgula, padx=12, bd=0,
                  font=("Arial", 9, "bold")).pack(side="left", padx=10)

        self.lbl_sayim = tk.Label(ust2, text="", bg="#ECEFF1",
                                    fg="#37474F", font=("Arial", 9, "bold"))
        self.lbl_sayim.pack(side="left", padx=8)

        # Sağ butonlar
        tk.Button(ust2, text="📊 Excel", bg="#43A047", fg="white",
                  command=self._excel_export, bd=0, padx=8
                  ).pack(side="right", padx=4)
        tk.Button(ust2, text="⚙ Sütunlar", bg="#607D8B", fg="white",
                  command=self._sutun_ayar_penceresi, bd=0, padx=8
                  ).pack(side="right", padx=4)
        tk.Button(ust2, text="🔥 Hızlı Filtreler ▾", bg="#7B1FA2", fg="white",
                  command=self._hizli_filtre_menu, bd=0, padx=8
                  ).pack(side="right", padx=4)

        # ───── SATIR 2: Seçim + Boyama + Renk Filtreleri ─────
        ust3 = tk.Frame(self.root, bg="#FAFAFA", pady=4)
        ust3.pack(fill="x", padx=6)

        # SEÇIM grubu
        tk.Label(ust3, text="🎯 Seçim:", bg="#FAFAFA",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 2))
        tk.Button(ust3, text="☑ Tümü", bg="#E1F5FE", bd=1,
                  command=self._tumunu_sec, padx=4
                  ).pack(side="left", padx=1)
        tk.Button(ust3, text="☐ Hiçbiri", bg="#FFEBEE", bd=1,
                  command=self._hicbirini_secme, padx=4
                  ).pack(side="left", padx=1)
        tk.Button(ust3, text="↻ Tersine", bg="#FFF3E0", bd=1,
                  command=self._secimi_tersine_cevir, padx=4
                  ).pack(side="left", padx=1)

        # Boyama grubu
        tk.Label(ust3, text="  🎨 Seçili →", bg="#FAFAFA",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 2))
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU, RENK_KIRMIZI, RENK_BEYAZ]:
            tk.Button(ust3, text=RENK_ETIKET[renk],
                      bg=RENK_BG[renk], fg=RENK_FG[renk], bd=1,
                      command=lambda r=renk: self._secilenleri_renge_boya(r),
                      padx=4, font=("Segoe UI", 9)
                      ).pack(side="left", padx=1)

        # Görünen → Boya (5 renk tam)
        tk.Label(ust3, text="  Görünen →", bg="#FAFAFA",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 2))
        # Renk → ikisi etiketi (kullanıcı dostu sembol/kısaltma)
        renk_kisa = {
            RENK_YESIL:   "🟢",
            RENK_SARI:    "🟡",
            RENK_TURUNCU: "🟠",
            RENK_KIRMIZI: "🔴",
            RENK_BEYAZ:   "⚪",
        }
        for renk in [RENK_YESIL, RENK_SARI, RENK_TURUNCU, RENK_KIRMIZI, RENK_BEYAZ]:
            tk.Button(ust3, text=renk_kisa[renk],
                      bg=RENK_BG[renk], fg=RENK_FG[renk], bd=1,
                      command=lambda r=renk: self._gorunenleri_boya(r),
                      padx=4, width=2, font=("Segoe UI", 10)
                      ).pack(side="left", padx=1)

        # Renk filtre
        tk.Label(ust3, text="  👁 Göster:", bg="#FAFAFA",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 2))
        self.var_renk = {}
        for renk in [RENK_BEYAZ, RENK_YESIL, RENK_SARI, RENK_TURUNCU, RENK_KIRMIZI]:
            v = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(ust3, text=RENK_ETIKET[renk][:3],
                                  variable=v, bg=RENK_BG[renk], fg=RENK_FG[renk],
                                  selectcolor=RENK_BG[renk],
                                  font=("Segoe UI", 8), padx=2,
                                  command=self._renk_filtre_degisti)
            cb.pack(side="left", padx=1)
            self.var_renk[renk] = v

        # 🧹 Tüm filtreleri sıfırla
        tk.Button(ust3, text="🧹 Filtreleri Sıfırla",
                  bg="#FFE082", fg="#5D4037", bd=1,
                  command=self._tum_filtreleri_temizle,
                  font=("Segoe UI", 9, "bold"), padx=8
                  ).pack(side="right", padx=(10, 4))

        # ───── ANA TABLO (artık tüm genişlikte) ─────
        tablo_frame = tk.Frame(self.root, bg="white")
        tablo_frame.pack(fill="both", expand=True, padx=6, pady=(2, 4))
        self._tablo_kur(tablo_frame)

        # ───── DURUM ÇUBUĞU ─────
        self._durum_frame = tk.Frame(self.root, bg="#ECEFF1")
        self._durum_frame.pack(fill="x", side="bottom")
        self.durum_bar = tk.Label(self._durum_frame, text="Hazır", anchor="w",
                                    bg="#ECEFF1", fg="#37474F", padx=10)
        self.durum_bar.pack(fill="x", side="left", expand=True)
        # Sağda renk dağılımı sayacı
        self.lbl_durum_dagilim = tk.Label(self._durum_frame, text="",
                                            bg="#ECEFF1", fg="#37474F", padx=10,
                                            font=("Segoe UI", 9))
        self.lbl_durum_dagilim.pack(side="right")

    def _tablo_kur(self, parent):
        # Sütun başlıkları üstünde arama kutuları — frame yapısı:
        # [arama bar] [tablo (başlık + satırlar)]
        cont = tk.Frame(parent, bg="white")
        cont.pack(fill="both", expand=True, padx=4, pady=4)

        # Tablo + scroll
        tree_frame = tk.Frame(cont, bg="white")
        tree_frame.pack(fill="both", expand=True)

        # Style: kompakt satırlar
        style = ttk.Style()
        try:
            style.configure("Inceleme.Treeview", rowheight=22, font=("Segoe UI", 9))
            style.configure("Inceleme.Treeview.Heading",
                            font=("Segoe UI", 9, "bold"))
        except Exception:
            pass

        kolonlar = tuple(SUTUN_KOD)
        self.tv = ttk.Treeview(tree_frame, columns=kolonlar, show="headings",
                                selectmode="extended", style="Inceleme.Treeview")
        for kod, baslik, gen, _tip in SUTUNLAR:
            self.tv.heading(kod, text=baslik,
                            command=lambda k=kod: self._sutuna_gore_sirala(k))
            self.tv.column(kod, width=gen, minwidth=30, stretch=False)

        ysb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tv.yview)
        xsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")
        self.tv.pack(side="left", fill="both", expand=True)

        # Renk tag'leri
        for renk, bg in RENK_BG.items():
            fg = RENK_FG[renk]
            self.tv.tag_configure(renk, background=bg, foreground=fg)

        # Sağ tık dispatcher (başlık ↔ satır)
        self.tv.bind("<Button-3>", self._sag_tik_dispatch)

        # Çift tık — detay
        self.tv.bind("<Double-1>", self._satir_detay)

        # Sol tık — checkbox sütununa tıklamada toggle
        self.tv.bind("<Button-1>", self._sol_tik_dispatch, add="+")

        # Sütun başlıkları altında ARAMA KUTULARI (her sütun için)
        # Bu Treeview ile aynı x-scroll'a bağlı küçük bir frame
        # Basit yaklaşım: arama kutuları büyük tek satır altta, sütun adı + entry
        arama_cerceve = tk.LabelFrame(cont, text="Sütun Arama Kutuları",
                                        bg="#FAFAFA", fg="#37474F",
                                        font=("Segoe UI", 8, "bold"))
        arama_cerceve.pack(fill="x", pady=(4, 0))

        # 6 sütun arama kutusu yatay, scrollable canvas
        arama_canvas = tk.Canvas(arama_cerceve, height=48, bg="#FAFAFA",
                                  highlightthickness=0)
        arama_scrollbar = ttk.Scrollbar(arama_cerceve, orient="horizontal",
                                          command=arama_canvas.xview)
        arama_canvas.configure(xscrollcommand=arama_scrollbar.set)
        arama_canvas.pack(fill="x", expand=False, padx=2)
        arama_scrollbar.pack(fill="x")

        arama_inner = tk.Frame(arama_canvas, bg="#FAFAFA")
        arama_canvas.create_window((0, 0), window=arama_inner, anchor="nw")

        self.arama_varlari = {}
        for kod, baslik, gen, _tip in SUTUNLAR:
            cer = tk.Frame(arama_inner, bg="#FAFAFA", padx=2)
            cer.pack(side="left")
            tk.Label(cer, text=baslik, font=("Segoe UI", 7), bg="#FAFAFA",
                     fg="#546E7A").pack(anchor="w")
            v = tk.StringVar()
            ent = tk.Entry(cer, textvariable=v, width=max(8, gen // 8),
                            font=("Segoe UI", 8))
            ent.pack(anchor="w")
            v.trace_add("write", lambda *a, k=kod: self._sutun_filtre_degisti(k))
            self.arama_varlari[kod] = v

        arama_inner.update_idletasks()
        arama_canvas.config(scrollregion=arama_canvas.bbox("all"))

    # ----------------------------------------------------------- AY/YIL
    def _ay_listesini_yukle(self):
        if not self.db:
            return
        try:
            rows = self.db.sorgu_calistir(
                "SELECT DISTINCT YEAR(RxKayitTarihi) AS Y FROM ReceteAna "
                "WHERE RxSilme=0 ORDER BY Y DESC")
            yillar = [str(r["Y"]) for r in rows if r["Y"]]
            self.cb_yil["values"] = yillar
            if yillar:
                bugun = date.today()
                hedef = str(bugun.year)
                self.var_yil.set(hedef if hedef in yillar else yillar[0])
                self._yil_degisti()
        except Exception as e:
            logger.exception("Yıl listesi: %s", e)

    def _yil_degisti(self, *args):
        self.cb_ay["values"] = [self._ay_etiketi(i) for i in range(1, 13)]
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
        yil = self.var_yil.get()
        ay = self._ay_no_cek(self.var_ay.get())
        if not yil or not ay:
            messagebox.showwarning("Uyarı", "Yıl ve ay seçiniz")
            return
        # Önce mevcut state kaydet
        self._state_kaydet()
        # Tabloyu temizle
        self.tum_satirlar = []
        self.satir_indeks = {}
        self.satir_renkleri = {}
        self.tv.delete(*self.tv.get_children())
        self.aktif_donem = f"{yil}-{ay:02d}"
        self.lbl_sayim.config(text="Sorgulanıyor…")
        self._durum_yaz(f"{self.aktif_donem} dönemi sorgulanıyor (ilaç bazlı)…")
        threading.Thread(target=self._sorgu_threadi, args=(int(yil), ay),
                          daemon=True).start()

    def _sorgu_threadi(self, yil: int, ay: int):
        try:
            # Ana SQL: ReceteAna × ReceteIlaclari × Musteri × Doktor × Urun × ATC × RaporAna
            # İlaç-rapor bağlantısı: RIRaporKodId + RRKIRaporKodId + Hasta + tarih aralığı
            # OUTER APPLY ile her ilaç için en uygun (en yeni) aktif raporu seç
            sql = """
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
                WHERE ra.RxSilme = 0
                  AND YEAR(ra.RxKayitTarihi) = ?
                  AND MONTH(ra.RxKayitTarihi) = ?
                ORDER BY ra.RxKayitTarihi DESC, ri.RIId
            """
            try:
                rows = self.db.sorgu_calistir(sql, (yil, ay))
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
            uyari_kodlari = self._toplu_uyari_getir(rx_idler)

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
                    uyari_kodlari, rapor_detay, urun_mesaj)
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

    def _toplu_uyari_getir(self, rx_idler: list) -> dict:
        """Uyarı kodlarını RxId bazında topla. Kolon: RUAciklama (RUMetni DEĞİL!)"""
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
            logger.warning("Uyarı sorgu fail: %s", e)
        return {k: " | ".join(v) for k, v in result.items()}

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
                        uyari_kodlari, rapor_detay, urun_mesaj=None) -> dict:
        urun_mesaj = urun_mesaj or {}
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

        # Etken madde finali: rapor varsa rapor + ATC, yoksa sadece ATC
        if em_ad_rapor and atc_turkce:
            em_ad = f"{em_ad_rapor} ({atc_turkce})"
        elif em_ad_rapor:
            em_ad = em_ad_rapor
        else:
            em_ad = atc_turkce

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

        # Uyarı kodu: ürün mesajlarındaki kısa kodlar (272, EK-4/E vs.)
        # UMTMMesaj formatı: "1014(1) - 4.2.14.A- ..." veya "215 - EK-4/E ..."
        # Kısa form: "kod - sut" formatında ilk 2-3 mesaj
        uyari_kodlari_kisa = []
        for m in ilac_mesajlari[:5]:  # En fazla 5 mesaj
            mesaj_text = m.get("mesaj", "")
            sut = m.get("sut", "")
            # Mesajın başındaki kodu çek (ör "1014(1)")
            import re as _re
            kod_match = _re.match(r'^(\d+(?:\(\d+\))?)', mesaj_text)
            if kod_match:
                kod = kod_match.group(1)
                if sut:
                    uyari_kodlari_kisa.append(f"{kod}/{sut}")
                else:
                    uyari_kodlari_kisa.append(kod)
        # Reçete bazlı sistem uyarılarını da ekle (RxUyarilari)
        sistem_uyarisi = uyari_kodlari.get(rxid, "")
        uyari_text = " | ".join(uyari_kodlari_kisa)
        if sistem_uyarisi:
            uyari_text = (uyari_text + " || SİS: " + sistem_uyarisi[:60]
                            if uyari_text else sistem_uyarisi)

        return {
            "ri_id": riid, "rx_id": rxid,
            "rapor_ana_id": rapor_ana_id,
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
        self.lbl_sayim.config(text=f"{len(satirlar)} satır")

    # ----------------------------------------------------------- TABLO RENDER
    def _tabloyu_yenile(self):
        """tum_satirlar + filtreler + renk filtresi → tv'ye doldur."""
        self.tv.delete(*self.tv.get_children())
        self.gosterilen_iids = set()

        for s in self.tum_satirlar:
            iid = str(s["ri_id"])
            if not self._satir_filtreden_geciyor_mu(s):
                continue
            renk = self.satir_renkleri.get(iid, RENK_BEYAZ)
            if renk not in self.aktif_renk_filtre:
                continue
            # Seçim göstergesi (☐/☑)
            s["secim"] = "☑" if iid in self.secili_iidler else "☐"
            values = tuple(str(s.get(k, "")) for k in SUTUN_KOD)
            self.tv.insert("", "end", iid=iid, values=values, tags=(renk,))
            self.gosterilen_iids.add(iid)

    def _satir_filtreden_geciyor_mu(self, s: dict, haric_kod: str = None) -> bool:
        """Sütun arama kutuları + Excel-benzeri değer filtreleri ile filtre.

        haric_kod: Verildiğinde o sütunun kendi filtresi yoksayılır.
                   (Kaskad filtre popup'ı için — bir sütunun filtre popup'ı
                   açıldığında o sütunun filtresi diğer sütunlardaki seçenekleri
                   kısıtlamamalı, ama diğer sütunların filtreleri uygulanmalı.)
        """
        # 1) Alt sütun arama kutuları (içerir)
        for kod, var in self.arama_varlari.items():
            if kod == haric_kod:
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
        # Kısa debounce ile çağırılabilir; şimdilik direkt
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _renk_filtre_degisti(self):
        self.aktif_renk_filtre = {r for r, v in self.var_renk.items()
                                    if v.get()}
        self._tabloyu_yenile()
        self._sayaclari_guncelle()

    def _tum_filtreleri_temizle(self):
        """Tüm aktif filtreleri sıfırla:
        - Sütun arama kutuları (alt satır)
        - Excel-benzeri değer filtreleri (sağ tık popup'tan)
        - Renk filtreleri (5 renk de açık)
        - Sıralama
        """
        # Sütun arama kutularını temizle
        for var in self.arama_varlari.values():
            try:
                var.set("")
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
                                    RENK_TURUNCU, RENK_KIRMIZI}
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
        txt = (f"Toplam: {toplam}  |  Görünen: {gor}  |  Seçili: {sec}  ||  "
               f"⚪ {say[RENK_BEYAZ]}  🟢 {say[RENK_YESIL]}  "
               f"🟡 {say[RENK_SARI]}  🟠 {say[RENK_TURUNCU]}  🔴 {say[RENK_KIRMIZI]}")
        try:
            self.lbl_durum_dagilim.config(text=txt)
        except Exception:
            pass

    # ----------------------------------------------------------- BOYAMA
    def _secilenleri_renge_boya(self, renk: str):
        """secili_iidler set'indeki satırları renge boya."""
        if not self.secili_iidler:
            messagebox.showinfo("Bilgi", "Önce satırları seç (☐ kutucukları)")
            return
        n = len(self.secili_iidler)
        for iid in self.secili_iidler:
            self.satir_renkleri[iid] = renk
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._durum_yaz(f"{n} seçili satır → {RENK_ETIKET[renk]}")

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
        if not self.gosterilen_iids:
            self._durum_yaz("Görünen satır yok")
            return
        n = len(self.gosterilen_iids)
        if not messagebox.askyesno(
                "Görünenleri Boya",
                f"{n} görünen satırı '{RENK_ETIKET[renk]}' rengine boyayacak. Emin misin?"):
            return
        for iid in list(self.gosterilen_iids):
            self.satir_renkleri[iid] = renk
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._durum_yaz(f"{n} satır → {RENK_ETIKET[renk]}")

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
        for iid in iids:
            self.satir_renkleri[iid] = renk
        self._state_kaydet()
        self._tabloyu_yenile()
        self._sayaclari_guncelle()
        self._durum_yaz(f"{len(iids)} seçili satır → {RENK_ETIKET[renk]}")

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
        """Sol tık — secim sütununa tıklandıysa checkbox toggle, başka yere bırak."""
        try:
            region = self.tv.identify_region(event.x, event.y)
        except Exception:
            return
        if region != "cell":
            return
        col_id = self.tv.identify_column(event.x)
        kod = self._col_id_to_kod(col_id)
        if kod != "secim":
            return
        # Hangi satıra tıklandı?
        iid = self.tv.identify_row(event.y)
        if not iid:
            return
        # Toggle
        if iid in self.secili_iidler:
            self.secili_iidler.discard(iid)
            self.tv.set(iid, "secim", "☐")
        else:
            self.secili_iidler.add(iid)
            self.tv.set(iid, "secim", "☑")
        # tum_satirlar içindeki secim'i de güncelle
        s = self.satir_indeks.get(iid)
        if s:
            s["secim"] = "☑" if iid in self.secili_iidler else "☐"
        self._sayaclari_guncelle()

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
        """sutun_gosterim'e göre Treeview'da kolon görünürlüğünü ayarla."""
        try:
            gorunenler = [k for k in SUTUN_KOD if self.sutun_gosterim.get(k, True)]
            self.tv["displaycolumns"] = gorunenler
        except Exception:
            pass

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
