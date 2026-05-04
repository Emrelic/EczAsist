"""
İlaç Bazlı SUT Matrisi — Toplevel pencere
recete_rapor_kontrol_gui.py içindeki butonla açılır.

Özellikleri:
  - Aylık ilaç satırı listesi (her RIId bir satır)
  - SUT Maddesi grup filtresi (kontrol_kurallari.db'den dinamik)
  - İlaç adı / etken madde arama
  - Çoklu kelime metin filtresi (İçerir/Başlar/Biter + VE/VEYA + kolon seçici)
  - tksheet ile hücre bazlı çoklu renk işaretleme (5 renk)
  - Satır bazlı not
  - Kalıcı kayıt: oturum_raporlari.db
  - SUT bilgi paneli sağda (kontrol_kurallari.db'den)

GÜVENLİK: Botanik DB'ye yalnızca SELECT.
"""

import logging
import re
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional, Tuple

import tksheet

from botanik_db import BotanikDB
from sut_kontrol_db import (DURUM_AD, DURUM_RENK, DURUMLAR, get_sut_db)
from sut_kural_eslestirici import SUTKuralEslestirici

logger = logging.getLogger(__name__)

UYARI_KODU_REGEX = re.compile(r"\((\d{3,7})\)")

# Tablo kolon tanımları (sıralı)
KOLONLAR = [
    ("tarih",          "Tarih",            85),
    ("hasta",          "Hasta",            150),
    ("ilac",           "İlaç",             220),
    ("adet",           "Adet",             45),
    ("doz",            "Doz",              55),
    ("recete_teshis",  "Reçete Teşhisi",   180),
    ("rapor_teshis",   "Rapor Teşhisi",    180),
    ("recete_aciklama","Reçete Açıklaması",200),
    ("rapor_aciklama", "Rapor Açıklaması", 280),
    ("birlesik",       "BİRLEŞİK METİN",   240),
    ("uyari_kod",      "Uyarı Kod",        90),
    ("sut_madde",      "SUT Mad.",         85),
    ("not",            "Not",              160),
]
KOLON_ANAHTARLARI = [k[0] for k in KOLONLAR]
KOLON_BASLIKLARI = [k[1] for k in KOLONLAR]
KOLON_GENISLIKLERI = [k[2] for k in KOLONLAR]
KOLON_INDEKS = {k: i for i, k in enumerate(KOLON_ANAHTARLARI)}

# İşaretlenebilir kolonlar (tarih, hasta, ilaç gibi sabitler hariç)
ISARETLENEBILIR_KOLONLAR = {
    "recete_teshis", "rapor_teshis", "recete_aciklama",
    "rapor_aciklama", "birlesik", "uyari_kod", "not",
}

# Filtre operatörleri
OPERATORLER = ["İçerir", "Başlar", "Biter", "Eşit"]
BAGLAYICILAR = ["VE", "VEYA"]


def uyari_kodlarini_ayikla(metin: str) -> str:
    if not metin:
        return ""
    kodlar = list(dict.fromkeys(UYARI_KODU_REGEX.findall(metin)))
    return ", ".join(kodlar)


def filtre_uygula(metin: str, kelime: str, operator: str) -> bool:
    """Tek kelimelik filtre kontrolü."""
    if not kelime:
        return True
    metin_ust = (metin or "").upper()
    kelime_ust = kelime.upper()
    if operator == "İçerir":
        return kelime_ust in metin_ust
    if operator == "Başlar":
        return metin_ust.startswith(kelime_ust)
    if operator == "Biter":
        return metin_ust.endswith(kelime_ust)
    if operator == "Eşit":
        return metin_ust == kelime_ust
    return True


class SUTMatrisiGUI:

    def __init__(self, root: tk.Toplevel, kullanici_id: Optional[int] = None,
                 ana_menu_callback=None):
        self.root = root
        self.kullanici_id = kullanici_id
        self.ana_menu_callback = ana_menu_callback

        self.root.title("🎯 İlaç Bazlı SUT Matrisi")
        self.root.geometry("1700x920")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        self.botanik: Optional[BotanikDB] = None
        self.eslestirici: Optional[SUTKuralEslestirici] = None
        self.kontrol_db = get_sut_db()

        self._satirlar: List[dict] = []   # tüm satırların ham verisi
        self._gosterilen_satirlar: List[dict] = []  # filtreli aktif liste
        self._isaretler: Dict[Tuple[int, int, str], str] = {}
        self._notlar: Dict[Tuple[int, int], str] = {}

        # Lookup'lar
        self._lookup_brans = {}
        self._lookup_renk = {}
        self._lookup_alttur = {}
        self._lookup_kurum = {}

        self.root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._arayuz_olustur()
        self._db_baglan_ve_yukle()
        self._ay_listesini_doldur()

    # =================================================================
    # DB
    # =================================================================
    def _db_baglan_ve_yukle(self):
        try:
            self.botanik = BotanikDB(production=True)
            if not self.botanik.baglan():
                raise RuntimeError("Botanik DB bağlantısı kurulamadı")
            self.eslestirici = SUTKuralEslestirici(self.botanik)
            self.eslestirici.yukle()
            # Ek lookup'lar
            for r in self.botanik.sorgu_calistir(
                    "SELECT BransId, BransAdi FROM Brans WHERE BransSilme=0"):
                self._lookup_brans[r["BransId"]] = r["BransAdi"]
            for r in self.botanik.sorgu_calistir(
                    "SELECT ReceteRenkId, ReceteRenkAdi FROM ReceteRenk WHERE ReceteRenkSilme=0"):
                self._lookup_renk[r["ReceteRenkId"]] = r["ReceteRenkAdi"]
            for r in self.botanik.sorgu_calistir(
                    "SELECT ReceteAltTuruId, ReceteAltTuruAdi FROM ReceteAltTuru WHERE ReceteAltTuruSilme=0"):
                self._lookup_alttur[r["ReceteAltTuruId"]] = r["ReceteAltTuruAdi"]
            for r in self.botanik.sorgu_calistir(
                    "SELECT KurumId, KurumAdi FROM Kurum WHERE KurumSilme=0"):
                self._lookup_kurum[r["KurumId"]] = r["KurumAdi"]
            self._durum_yaz("DB bağlantısı + eşleştirici hazır.")
            self._sut_grup_dropdown_doldur()
        except Exception as e:
            logger.exception("DB hazırlama hatası: %s", e)
            messagebox.showerror("Bağlantı Hatası", str(e))

    # =================================================================
    # UI
    # =================================================================
    def _arayuz_olustur(self):
        # Üst başlık
        ust = tk.Frame(self.root, bg="#0D2137", height=50)
        ust.pack(fill="x")
        tk.Label(
            ust, text="🎯 İlaç Bazlı SUT Matrisi (Botanik EOS)",
            font=("Segoe UI", 13, "bold"), fg="white", bg="#0D2137",
        ).pack(side="left", padx=15, pady=10)
        tk.Button(
            ust, text="✕ Kapat", command=self._kapat,
            bg="#455A64", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=15, pady=10)

        # FİLTRE ÇERÇEVESİ
        filtre_dis = tk.Frame(self.root, bg="#ECEFF1")
        filtre_dis.pack(fill="x", padx=8, pady=(8, 4))

        # Satır 1: Yıl/Ay + Grup + İlaç arama
        f1 = tk.Frame(filtre_dis, bg="#ECEFF1")
        f1.pack(fill="x", padx=4, pady=2)

        tk.Label(f1, text="Yıl:", bg="#ECEFF1").pack(side="left", padx=(4, 2))
        self.var_yil = tk.StringVar()
        self.cb_yil = ttk.Combobox(f1, textvariable=self.var_yil,
                                    width=6, state="readonly")
        self.cb_yil.pack(side="left", padx=2)

        tk.Label(f1, text="Ay:", bg="#ECEFF1").pack(side="left", padx=(8, 2))
        self.var_ay = tk.StringVar()
        self.cb_ay = ttk.Combobox(f1, textvariable=self.var_ay,
                                   width=12, state="readonly")
        self.cb_ay.pack(side="left", padx=2)

        tk.Label(f1, text="SUT Grubu:",
                 bg="#ECEFF1").pack(side="left", padx=(15, 2))
        self.var_grup = tk.StringVar(value="(Tümü)")
        self.cb_grup = ttk.Combobox(f1, textvariable=self.var_grup,
                                     width=42, state="readonly")
        self.cb_grup.pack(side="left", padx=2)
        self.cb_grup.bind("<<ComboboxSelected>>", lambda e: self._filtre_uygula())

        tk.Label(f1, text="İlaç/Etken:",
                 bg="#ECEFF1").pack(side="left", padx=(15, 2))
        self.var_ilac = tk.StringVar()
        ent_ilac = tk.Entry(f1, textvariable=self.var_ilac, width=22)
        ent_ilac.pack(side="left", padx=2)
        ent_ilac.bind("<Return>", lambda e: self._filtre_uygula())

        tk.Button(f1, text="🔍 Sorgula", bg="#1976D2", fg="white",
                  bd=0, padx=12, command=self._receteleri_sorgula
                  ).pack(side="left", padx=(15, 4))

        self.lbl_sayim = tk.Label(f1, text="", bg="#ECEFF1", fg="#37474F")
        self.lbl_sayim.pack(side="left", padx=10)

        # Satır 2: Çoklu kelime metin filtresi
        f2 = tk.Frame(filtre_dis, bg="#ECEFF1")
        f2.pack(fill="x", padx=4, pady=(2, 4))

        tk.Label(f2, text="Metin filtresi  →  Operatör:",
                 bg="#ECEFF1").pack(side="left", padx=(4, 2))

        self.var_op = tk.StringVar(value="İçerir")
        self.var_k1 = tk.StringVar()
        self.var_b1 = tk.StringVar(value="VE")
        self.var_k2 = tk.StringVar()
        self.var_b2 = tk.StringVar(value="VE")
        self.var_k3 = tk.StringVar()

        ttk.Combobox(f2, textvariable=self.var_op, values=OPERATORLER,
                      width=8, state="readonly").pack(side="left", padx=2)
        e1 = tk.Entry(f2, textvariable=self.var_k1, width=18)
        e1.pack(side="left", padx=2)
        e1.bind("<Return>", lambda e: self._filtre_uygula())
        ttk.Combobox(f2, textvariable=self.var_b1, values=BAGLAYICILAR,
                      width=5, state="readonly").pack(side="left", padx=2)
        e2 = tk.Entry(f2, textvariable=self.var_k2, width=18)
        e2.pack(side="left", padx=2)
        e2.bind("<Return>", lambda e: self._filtre_uygula())
        ttk.Combobox(f2, textvariable=self.var_b2, values=BAGLAYICILAR,
                      width=5, state="readonly").pack(side="left", padx=2)
        e3 = tk.Entry(f2, textvariable=self.var_k3, width=18)
        e3.pack(side="left", padx=2)
        e3.bind("<Return>", lambda e: self._filtre_uygula())

        tk.Label(f2, text="  Hangi kolonda:",
                 bg="#ECEFF1").pack(side="left", padx=(15, 2))
        self.var_kolon = tk.StringVar(value="(Birleşik)")
        kolon_secenek = ["(Birleşik)", "Reçete Teşhisi", "Rapor Teşhisi",
                          "Reçete Açıklaması", "Rapor Açıklaması", "Uyarı Kod"]
        ttk.Combobox(f2, textvariable=self.var_kolon, values=kolon_secenek,
                      width=18, state="readonly").pack(side="left", padx=2)

        tk.Button(f2, text="Uygula", bg="#388E3C", fg="white",
                  bd=0, padx=10, command=self._filtre_uygula
                  ).pack(side="left", padx=(10, 2))
        tk.Button(f2, text="Temizle", bg="#9E9E9E", fg="white",
                  bd=0, padx=10, command=self._filtreleri_sifirla
                  ).pack(side="left", padx=2)

        # ========== ANA SPLIT ==========
        ana = tk.PanedWindow(self.root, orient="horizontal", sashwidth=6,
                              bg="#CFD8DC")
        ana.pack(fill="both", expand=True, padx=8, pady=4)

        # Sol — tksheet
        sol = tk.Frame(ana, bg="white")
        ana.add(sol, minsize=900)
        self._tablo_olustur(sol)

        # Sağ — SUT bilgi paneli
        sag = tk.Frame(ana, bg="white", width=320)
        ana.add(sag, minsize=300)
        self._sag_panel_olustur(sag)

        # ========== ALT BAR ==========
        alt = tk.Frame(self.root, bg="#ECEFF1")
        alt.pack(fill="x", side="bottom", padx=8, pady=(2, 6))

        tk.Label(alt, text="Seçili hücre(ler) için durum:",
                 bg="#ECEFF1").pack(side="left", padx=(4, 6))

        durum_buton_renk = {
            "yesil":   ("🟢 Uygun",       "#4CAF50"),
            "kirmizi": ("🔴 Uygun değil", "#E53935"),
            "sari":    ("🟡 İncelemede",  "#FBC02D"),
            "turuncu": ("🟠 Şüpheli",     "#FB8C00"),
            "beyaz":   ("⚪ Sıfırla",     "#90A4AE"),
        }
        for d in DURUMLAR:
            txt, bg = durum_buton_renk[d]
            tk.Button(alt, text=txt, bg=bg, fg="white", bd=0, padx=10,
                       command=lambda dd=d: self._durum_uygula(dd)
                       ).pack(side="left", padx=2)

        tk.Label(alt, text="   |   Klavye: 1 2 3 4 0",
                 bg="#ECEFF1", fg="#546E7A").pack(side="left", padx=10)

        tk.Button(alt, text="📝 Satır Notu Ekle/Düzenle",
                   bg="#5C6BC0", fg="white", bd=0, padx=10,
                   command=self._not_duzenle).pack(side="right", padx=4)

        # Klavye kısayolları
        for d, k in zip(DURUMLAR, ["1", "2", "3", "4", "0"]):
            self.root.bind(f"<KeyPress-{k}>",
                            lambda e, dd=d: self._durum_uygula(dd))

        # Status bar
        self._durum_frame = tk.Frame(self.root, bg="#ECEFF1")
        self._durum_frame.pack(fill="x", side="bottom")
        self.durum_bar = tk.Label(self._durum_frame, text="Hazır",
                                    anchor="w", bg="#ECEFF1", fg="#37474F",
                                    padx=10)
        self.durum_bar.pack(fill="x", side="left", expand=True)

    def _tablo_olustur(self, parent):
        self.sheet = tksheet.Sheet(
            parent,
            headers=KOLON_BASLIKLARI,
            data=[],
            theme="light blue",
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            show_row_index=True,
            row_index_width=40,
        )
        self.sheet.pack(fill="both", expand=True, padx=4, pady=4)
        for i, w in enumerate(KOLON_GENISLIKLERI):
            self.sheet.column_width(i, w)
        self.sheet.enable_bindings(
            "single_select", "row_select", "drag_select",
            "column_width_resize", "double_click_column_resize",
            "row_height_resize", "arrowkeys", "copy",
            "rc_select", "right_click_popup_menu",
        )
        self.sheet.disable_bindings("edit_cell")
        # Çift tıklama → not düzenle
        self.sheet.bind("<Double-Button-1>",
                         lambda e: self._not_duzenle())
        # Tek tık → sağ panel güncelle (sheet selection eventi)
        try:
            self.sheet.extra_bindings(
                [("cell_select", lambda e: self._secim_degisti()),
                 ("row_select",  lambda e: self._secim_degisti())]
            )
        except Exception:
            self.sheet.bind("<Button-1>",
                             lambda e: self.root.after(80, self._secim_degisti))

    def _sag_panel_olustur(self, parent):
        tk.Label(parent, text="📜 SUT Kuralı (kontrol_kurallari.db)",
                 bg="white", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=8, pady=(8, 4))

        self.txt_sut = tk.Text(parent, wrap="word", font=("Consolas", 9),
                                bg="#FAFAFA", state="disabled")
        vbar = ttk.Scrollbar(parent, orient="vertical",
                              command=self.txt_sut.yview)
        self.txt_sut.configure(yscrollcommand=vbar.set)
        self.txt_sut.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")

        self.sheet_secim_callback_attached = False

    # =================================================================
    # Yıl/Ay listesi
    # =================================================================
    def _ay_etiketi(self, n: int) -> str:
        adlar = ["", "01-Ocak", "02-Şubat", "03-Mart", "04-Nisan",
                 "05-Mayıs", "06-Haziran", "07-Temmuz", "08-Ağustos",
                 "09-Eylül", "10-Ekim", "11-Kasım", "12-Aralık"]
        return adlar[n] if 1 <= n <= 12 else ""

    def _ay_no(self, etiket: str) -> int:
        if etiket and "-" in etiket:
            try:
                return int(etiket.split("-")[0])
            except ValueError:
                return 0
        return 0

    def _ay_listesini_doldur(self):
        if not self.botanik:
            return
        try:
            rows = self.botanik.sorgu_calistir(
                "SELECT DISTINCT YEAR(RxKayitTarihi) AS Y FROM ReceteAna "
                "WHERE RxSilme=0 AND RxKayitTarihi IS NOT NULL "
                "ORDER BY Y DESC"
            )
            yillar = [str(r["Y"]) for r in rows if r.get("Y")]
            self.cb_yil["values"] = yillar
            self.cb_ay["values"] = [self._ay_etiketi(i) for i in range(1, 13)]
            if yillar:
                bugun = date.today()
                self.var_yil.set(str(bugun.year) if str(bugun.year) in yillar
                                  else yillar[0])
                self.var_ay.set(self._ay_etiketi(bugun.month))
        except Exception as e:
            logger.exception("Yıl listesi: %s", e)

    def _sut_grup_dropdown_doldur(self):
        if not self.eslestirici:
            return
        gruplar = self.eslestirici.sut_madde_listesi()
        secenekler = ["(Tümü)"]
        for g in gruplar:
            secenekler.append(
                f"{g['sut_maddesi']} — {g['kategori']} ({g['etkin_madde_sayisi']} madde)"
            )
        self.cb_grup["values"] = secenekler

    # =================================================================
    # Sorgu (ana motor)
    # =================================================================
    def _receteleri_sorgula(self):
        if not self.botanik:
            return
        yil = self.var_yil.get()
        ay = self._ay_no(self.var_ay.get())
        if not yil or not ay:
            self._durum_yaz("Yıl/Ay seçin")
            return
        self._durum_yaz(f"{yil}-{ay:02d} sorgulanıyor...")
        threading.Thread(target=self._sorgu_threadi,
                          args=(int(yil), ay), daemon=True).start()

    def _sorgu_threadi(self, yil: int, ay: int):
        try:
            sql = """
                SELECT ra.RxId, ra.RxEReceteNo, ra.RxIslemTarihi,
                       ra.RxReceteTarihi, ra.RxKurumId, ra.RxBransId,
                       ra.RxReceteRenkId, ra.RxReceteAltTuruId,
                       ra.RxMusteriId, ra.RxDoktorId,
                       m.MusteriAdiSoyadi, m.MusteriTCKN,
                       d.DoktorAdiSoyadi,
                       ri.RIId, ri.RIUrunId, u.UrunAdi,
                       ri.RIAdet, ri.RIDoz, ri.RITekrar, ri.RIPeriyotId,
                       ri.RIBitisTarihi, ri.RIRaporKodId, ri.RIRaporNo,
                       sr.SRRaporNo AS SecilenRaporNo
                FROM ReceteAna ra
                JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId AND ri.RISilme=0
                LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
                LEFT JOIN Doktor d ON d.DoktorId = ra.RxDoktorId
                LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
                LEFT JOIN SecilenRapor sr ON sr.SRRxId = ra.RxId
                                          AND sr.SRUrunId = ri.RIUrunId
                WHERE ra.RxSilme = 0
                  AND YEAR(ra.RxKayitTarihi) = ?
                  AND MONTH(ra.RxKayitTarihi) = ?
                ORDER BY ra.RxIslemTarihi DESC, ri.RIId
            """
            ham = self.botanik.sorgu_calistir(sql, (yil, ay))

            # Per-RxId joinlenecek ek tablolar — toplu çekmek için RxId set
            rx_ids = list({r["RxId"] for r in ham})
            if not rx_ids:
                self.root.after(0, self._satirlari_doldur, [])
                return

            ph = ",".join("?" * len(rx_ids))

            # ReceteICD + ReceteTeshis
            recete_icd_dict = {}
            for r in self.botanik.sorgu_calistir(
                f"""SELECT ri.ReceteICDRxId, i.ICDKodu, i.ICDAciklamasi,
                           ri.ReceteICDICDAciklama
                    FROM ReceteICD ri
                    LEFT JOIN ICD i ON i.ICDId = ri.ReceteICDICDId
                    WHERE ri.ReceteICDRxId IN ({ph}) AND ri.ReceteICDSilme=0""",
                tuple(rx_ids),
            ):
                kod = r.get("ICDKodu") or ""
                ack = r.get("ICDAciklamasi") or r.get("ReceteICDICDAciklama") or ""
                metin = f"{kod} {ack}".strip(" -")
                recete_icd_dict.setdefault(r["ReceteICDRxId"], []).append(metin)
            for r in self.botanik.sorgu_calistir(
                f"""SELECT rt.RTRxId, rt.RTTeshisKodu,
                           i.ICDKodu, i.ICDAciklamasi
                    FROM ReceteTeshis rt
                    LEFT JOIN ICD i ON i.ICDId = rt.RTTeshisId
                    WHERE rt.RTRxId IN ({ph})""",
                tuple(rx_ids),
            ):
                kod = r.get("ICDKodu") or r.get("RTTeshisKodu") or ""
                ack = r.get("ICDAciklamasi") or ""
                metin = f"{kod} {ack}".strip(" -")
                recete_icd_dict.setdefault(r["RTRxId"], []).append(metin)

            # RxUyarilari (uyarı metinleri ve kodlar)
            uyari_dict = {}
            for r in self.botanik.sorgu_calistir(
                f"SELECT RxId, RUAciklama FROM RxUyarilari WHERE RxId IN ({ph})",
                tuple(rx_ids),
            ):
                uyari_dict.setdefault(r["RxId"], []).append(r["RUAciklama"] or "")

            # EReceteAciklamalari
            recete_aciklama_dict = {}
            er_id_to_rx = {}
            er_rows = self.botanik.sorgu_calistir(
                f"SELECT EReceteId, EReceteMusteriId, EReceteNo FROM ERecete "
                f"WHERE EReceteNo IN (SELECT RxEReceteNo FROM ReceteAna WHERE RxId IN ({ph}))",
                tuple(rx_ids),
            )
            er_no_to_rx = {}
            # Hangi RxId hangi EReceteNo'ya sahip
            for r in ham:
                if r.get("RxEReceteNo"):
                    er_no_to_rx[r["RxEReceteNo"]] = r["RxId"]
            for er in er_rows:
                rx_id_e = er_no_to_rx.get(er["EReceteNo"])
                if rx_id_e:
                    er_id_to_rx[er["EReceteId"]] = rx_id_e
            if er_id_to_rx:
                er_ids = list(er_id_to_rx.keys())
                ph2 = ",".join("?" * len(er_ids))
                for r in self.botanik.sorgu_calistir(
                    f"""SELECT era.ERAEReceteId,
                              eat.EReceteAciklamaTuruAdi,
                              ea.EReceteAciklamaAdi
                        FROM EReceteAciklamalari era
                        LEFT JOIN EReceteAciklamaTuru eat
                              ON eat.EReceteAciklamaTuruId = era.ERAEReceteAciklamaTuruId
                        LEFT JOIN EReceteAciklama ea
                              ON ea.EReceteAciklamaId = era.ERAEReceteAciklamaId
                        WHERE era.ERAEReceteId IN ({ph2})""",
                    tuple(er_ids),
                ):
                    rxid = er_id_to_rx.get(r["ERAEReceteId"])
                    if rxid:
                        tur = r.get("EReceteAciklamaTuruAdi") or ""
                        ack = r.get("EReceteAciklamaAdi") or ""
                        recete_aciklama_dict.setdefault(rxid, []).append(
                            f"[{tur}] {ack}".strip()
                        )

            # Müşteri bazlı RaporAna + RaporRaporKodlariICD
            musteri_ids = list({r["RxMusteriId"] for r in ham
                                  if r.get("RxMusteriId")})
            rapor_dict = {}    # RaporAnaId → rapor dict
            rapor_no_to_id = {}  # RaporAnaRaporNo → RaporAnaId
            rapor_kod_to_ids = {}  # (musteri_id, rapor_kod_id) → en uygun RaporAnaId listesi
            rapor_icd_dict = {}  # RaporAnaId → list of "kod açıklama"
            if musteri_ids:
                ph_m = ",".join("?" * len(musteri_ids))
                rap_rows = self.botanik.sorgu_calistir(
                    f"""SELECT RaporAnaId, RaporAnaMusteriId, RaporAnaRaporNo,
                              RaporAnaRaporTarihi, RaporAnaAciklamalar
                        FROM RaporAna
                        WHERE RaporAnaMusteriId IN ({ph_m}) AND RaporAnaSilme=0""",
                    tuple(musteri_ids),
                )
                for r in rap_rows:
                    rapor_dict[r["RaporAnaId"]] = r
                    if r.get("RaporAnaRaporNo"):
                        rapor_no_to_id[(r["RaporAnaMusteriId"],
                                         str(r["RaporAnaRaporNo"]).strip())] = r["RaporAnaId"]
                if rap_rows:
                    rapor_ids = [r["RaporAnaId"] for r in rap_rows]
                    ph_r = ",".join("?" * len(rapor_ids))
                    for r in self.botanik.sorgu_calistir(
                        f"""SELECT rrki.RRKIRaporAnaId, rrki.RRKIRaporKodId,
                                   i.ICDKodu, i.ICDAciklamasi
                            FROM RaporRaporKodlariICD rrki
                            LEFT JOIN ICD i ON i.ICDId = rrki.RRKIICDId
                            WHERE rrki.RRKIRaporAnaId IN ({ph_r})
                              AND rrki.RRKISilme=0""",
                        tuple(rapor_ids),
                    ):
                        kod = r.get("ICDKodu") or ""
                        ack = r.get("ICDAciklamasi") or ""
                        metin = f"{kod} {ack}".strip(" -")
                        rapor_icd_dict.setdefault(r["RRKIRaporAnaId"], []).append(metin)
                        # rapor kod indeksleme
                        if r.get("RRKIRaporKodId"):
                            mid = rapor_dict[r["RRKIRaporAnaId"]]["RaporAnaMusteriId"]
                            rapor_kod_to_ids.setdefault(
                                (mid, r["RRKIRaporKodId"]), []
                            ).append(r["RRKIRaporAnaId"])

            # Satırları zenginleştir
            satirlar = []
            for r in ham:
                rx_id = r["RxId"]
                ri_id = r["RIId"]
                musteri_id = r.get("RxMusteriId")

                # Rapor seçimi: SecilenRapor → en yeni eşleşen kod → boş
                rapor_id = None
                sr_no = r.get("SecilenRaporNo")
                if sr_no:
                    rapor_id = rapor_no_to_id.get(
                        (musteri_id, str(sr_no).strip())
                    )
                if not rapor_id and r.get("RIRaporKodId"):
                    aday_listesi = rapor_kod_to_ids.get(
                        (musteri_id, r["RIRaporKodId"]), []
                    )
                    if aday_listesi:
                        # En yeni rapor (RaporAnaRaporTarihi'ne göre)
                        en_yeni = max(
                            aday_listesi,
                            key=lambda rid: rapor_dict[rid].get("RaporAnaRaporTarihi") or "1900-01-01",
                        )
                        rapor_id = en_yeni

                rapor_aciklama = ""
                rapor_teshis = ""
                if rapor_id:
                    rapor_aciklama = rapor_dict[rapor_id].get("RaporAnaAciklamalar") or ""
                    rapor_teshis = " | ".join(rapor_icd_dict.get(rapor_id, []))

                recete_teshis = " | ".join(recete_icd_dict.get(rx_id, []))
                recete_aciklama = " | ".join(recete_aciklama_dict.get(rx_id, []))
                uyari_metni = " | ".join(uyari_dict.get(rx_id, []))
                uyari_kod = uyari_kodlarini_ayikla(uyari_metni)

                # SUT kuralı eşleşmesi
                kural = self.eslestirici.urun_kurali(r["RIUrunId"]) if self.eslestirici else None
                sut_madde = (kural or {}).get("sut_maddesi") or ""

                # Birleşik metin
                birlesik_parts = [
                    recete_teshis, rapor_teshis, recete_aciklama,
                    rapor_aciklama, uyari_metni
                ]
                birlesik = " ║ ".join(p for p in birlesik_parts if p)

                # Tarih
                tarih = r.get("RxIslemTarihi") or r.get("RxReceteTarihi")
                tarih_str = tarih.strftime("%d.%m.%Y") if tarih else "—"

                satirlar.append({
                    "rx_id": rx_id,
                    "ri_id": ri_id,
                    "urun_id": r["RIUrunId"],
                    "musteri_id": musteri_id,
                    "kural": kural,
                    "rapor_id": rapor_id,
                    "tarih": tarih_str,
                    "hasta": r.get("MusteriAdiSoyadi") or "",
                    "ilac": r.get("UrunAdi") or "",
                    "adet": r.get("RIAdet") or 0,
                    "doz": str(r.get("RIDoz") or ""),
                    "recete_teshis": recete_teshis,
                    "rapor_teshis": rapor_teshis,
                    "recete_aciklama": recete_aciklama,
                    "rapor_aciklama": rapor_aciklama,
                    "birlesik": birlesik,
                    "uyari_kod": uyari_kod,
                    "sut_madde": sut_madde,
                    "not": "",
                })

            # İşaretler + notları yükle
            isaretler = self.kontrol_db.isaretleri_getir(
                rx_ids, kullanici_id=self.kullanici_id
            )
            notlar = self.kontrol_db.notlari_getir(
                rx_ids, kullanici_id=self.kullanici_id
            )
            for s in satirlar:
                s["not"] = notlar.get((s["rx_id"], s["ri_id"]), "")

            self.root.after(0, self._satirlari_doldur,
                             satirlar, isaretler, notlar)
        except Exception as e:
            logger.exception("Sorgu hatası: %s", e)
            self.root.after(0, self._durum_yaz, f"Sorgu hatası: {e}")

    def _satirlari_doldur(self, satirlar, isaretler=None, notlar=None):
        self._satirlar = satirlar
        self._isaretler = isaretler or {}
        self._notlar = notlar or {}
        self._filtre_uygula()

    # =================================================================
    # Filtre
    # =================================================================
    def _filtre_uygula(self, *args):
        secili_grup = self.var_grup.get()
        ilac_arama = self.var_ilac.get().strip().upper()
        op = self.var_op.get()
        k1 = self.var_k1.get().strip()
        b1 = self.var_b1.get()
        k2 = self.var_k2.get().strip()
        b2 = self.var_b2.get()
        k3 = self.var_k3.get().strip()
        kolon_secim = self.var_kolon.get()

        # SUT grup filtresi: "(Tümü)" değilse sut_maddesi eşit kontrolü
        sut_filt = None
        if secili_grup and not secili_grup.startswith("(Tümü"):
            # "4.2.17 — Diyabet (..)" → "4.2.17"
            sut_filt = secili_grup.split(" — ")[0].strip()

        kolon_anahtarlari_haritasi = {
            "Reçete Teşhisi": "recete_teshis",
            "Rapor Teşhisi":  "rapor_teshis",
            "Reçete Açıklaması": "recete_aciklama",
            "Rapor Açıklaması":  "rapor_aciklama",
            "Uyarı Kod":         "uyari_kod",
        }

        sonuc = []
        for s in self._satirlar:
            # Grup filtresi
            if sut_filt and s["sut_madde"] != sut_filt:
                continue
            # İlaç adı arama
            if ilac_arama:
                if (ilac_arama not in s["ilac"].upper() and
                        ilac_arama not in (s["kural"] or {}).get("etkin_madde", "").upper()):
                    continue
            # Çoklu kelime metin filtresi
            if k1 or k2 or k3:
                if kolon_secim and not kolon_secim.startswith("(Birleşik"):
                    hedef = s.get(kolon_anahtarlari_haritasi.get(kolon_secim, "birlesik"), "")
                else:
                    hedef = s["birlesik"]
                # Soldan sağa değerlendir
                sonuclar = []
                if k1:
                    sonuclar.append(filtre_uygula(hedef, k1, op))
                if k2:
                    if k1:
                        # Önceki sonuçla birleştir (b1)
                        prev = sonuclar[-1]
                        cur = filtre_uygula(hedef, k2, op)
                        sonuclar[-1] = (prev and cur) if b1 == "VE" else (prev or cur)
                    else:
                        sonuclar.append(filtre_uygula(hedef, k2, op))
                if k3:
                    if sonuclar:
                        prev = sonuclar[-1]
                        cur = filtre_uygula(hedef, k3, op)
                        sonuclar[-1] = (prev and cur) if b2 == "VE" else (prev or cur)
                    else:
                        sonuclar.append(filtre_uygula(hedef, k3, op))
                if sonuclar and not sonuclar[-1]:
                    continue
            sonuc.append(s)

        self._gosterilen_satirlar = sonuc
        self._tabloya_yaz(sonuc)
        self.lbl_sayim.config(
            text=f"{len(sonuc)} ilaç satırı  |  Toplam: {len(self._satirlar)}"
        )
        self._durum_yaz(f"{len(sonuc)} satır gösteriliyor.")

    def _filtreleri_sifirla(self):
        self.var_grup.set("(Tümü)")
        self.var_ilac.set("")
        self.var_k1.set(""); self.var_k2.set(""); self.var_k3.set("")
        self.var_op.set("İçerir")
        self.var_b1.set("VE"); self.var_b2.set("VE")
        self.var_kolon.set("(Birleşik)")
        self._filtre_uygula()

    def _tabloya_yaz(self, satirlar: List[dict]):
        data = []
        for s in satirlar:
            satir = []
            for k in KOLON_ANAHTARLARI:
                if k == "tarih": satir.append(s["tarih"])
                elif k == "hasta": satir.append(s["hasta"])
                elif k == "ilac": satir.append(s["ilac"])
                elif k == "adet": satir.append(str(s["adet"]))
                elif k == "doz": satir.append(s["doz"])
                elif k == "recete_teshis": satir.append(s["recete_teshis"])
                elif k == "rapor_teshis": satir.append(s["rapor_teshis"])
                elif k == "recete_aciklama": satir.append(s["recete_aciklama"])
                elif k == "rapor_aciklama": satir.append(s["rapor_aciklama"])
                elif k == "birlesik": satir.append(s["birlesik"])
                elif k == "uyari_kod": satir.append(s["uyari_kod"])
                elif k == "sut_madde": satir.append(s["sut_madde"])
                elif k == "not": satir.append(s["not"])
                else: satir.append("")
            data.append(satir)
        self.sheet.set_sheet_data(data, reset_col_positions=False,
                                    reset_row_positions=True,
                                    redraw=True)
        # İşaretleri uygula
        self._isaretleri_renklendir()

    def _isaretleri_renklendir(self):
        """Hücre işaretlerini görsel olarak uygula."""
        try:
            self.sheet.dehighlight_all()
        except Exception:
            pass
        if not self._isaretler:
            self.sheet.refresh()
            return
        for satir_idx, s in enumerate(self._gosterilen_satirlar):
            for kolon_anahtar in ISARETLENEBILIR_KOLONLAR:
                kolon_idx = KOLON_INDEKS.get(kolon_anahtar)
                if kolon_idx is None:
                    continue
                durum = self._isaretler.get(
                    (s["rx_id"], s["ri_id"], kolon_anahtar)
                )
                if durum:
                    bg = DURUM_RENK.get(durum, "#FFFFFF")
                    try:
                        self.sheet.highlight_cells(
                            row=satir_idx, column=kolon_idx,
                            bg=bg, fg="#000000"
                        )
                    except Exception as e:
                        logger.debug("Highlight hatası: %s", e)
        self.sheet.refresh()

    # =================================================================
    # Hücre işaretleme
    # =================================================================
    def _durum_uygula(self, durum: str):
        """Seçili hücrelere durum (renk) uygula."""
        try:
            secili = self.sheet.get_selected_cells(
                get_rows=False, get_columns=False
            )
        except Exception:
            secili = self.sheet.get_selected_cells()
        if not secili:
            self._durum_yaz("Önce hücre seçin")
            return

        sayac = 0
        for cell in secili:
            try:
                row, col = cell
            except Exception:
                continue
            if row >= len(self._gosterilen_satirlar):
                continue
            kolon_ad = KOLON_ANAHTARLARI[col] if col < len(KOLON_ANAHTARLARI) else None
            if not kolon_ad or kolon_ad not in ISARETLENEBILIR_KOLONLAR:
                continue
            s = self._gosterilen_satirlar[row]
            if self.kontrol_db.isaret_koy(
                rx_id=s["rx_id"], ri_id=s["ri_id"], kolon_adi=kolon_ad,
                durum=durum, kullanici_id=self.kullanici_id,
            ):
                anahtar = (s["rx_id"], s["ri_id"], kolon_ad)
                if durum == "beyaz":
                    self._isaretler.pop(anahtar, None)
                else:
                    self._isaretler[anahtar] = durum
                sayac += 1

        self._isaretleri_renklendir()
        self._durum_yaz(f"{sayac} hücre {DURUM_AD.get(durum, durum)} olarak işaretlendi.")

    # =================================================================
    # Not düzenleme
    # =================================================================
    def _not_duzenle(self):
        try:
            secili = self.sheet.get_selected_cells()
            if not secili:
                self._durum_yaz("Önce satır/hücre seçin")
                return
            row = next(iter(secili))[0]
        except Exception:
            return
        if row >= len(self._gosterilen_satirlar):
            return
        s = self._gosterilen_satirlar[row]
        mevcut = s.get("not") or self._notlar.get((s["rx_id"], s["ri_id"]), "")
        yeni = simpledialog.askstring(
            "Satır Notu",
            f"{s['ilac']}  ({s['hasta']})\nNot:",
            initialvalue=mevcut, parent=self.root,
        )
        if yeni is None:
            return
        if self.kontrol_db.not_kaydet(
            rx_id=s["rx_id"], ri_id=s["ri_id"], not_metin=yeni,
            kullanici_id=self.kullanici_id,
        ):
            s["not"] = yeni.strip()
            self._notlar[(s["rx_id"], s["ri_id"])] = yeni.strip()
            # Tek satırı tabloda güncelle
            try:
                self.sheet.set_cell_data(row, KOLON_INDEKS["not"],
                                          yeni.strip(), redraw=True)
            except Exception:
                pass

    # =================================================================
    # Sağ panel — seçili satırın SUT bilgisi
    # =================================================================
    def _secim_degisti(self, *args):
        try:
            secili = self.sheet.get_selected_cells()
            if not secili:
                return
            row = next(iter(secili))[0]
        except Exception:
            return
        if row >= len(self._gosterilen_satirlar):
            return
        s = self._gosterilen_satirlar[row]
        kural = s.get("kural")
        self.txt_sut.config(state="normal")
        self.txt_sut.delete("1.0", "end")
        if not kural:
            self.txt_sut.insert("end",
                "Bu ilaç için kontrol_kurallari.db'de kayıt bulunamadı.\n\n"
                f"İlaç: {s.get('ilac')}\nÜrün ID: {s.get('urun_id')}\n")
        else:
            metin = (
                f"İlaç:           {s.get('ilac')}\n"
                f"Etken Madde:    {kural.get('etkin_madde','—')}\n"
                f"SGK Kodu:       {kural.get('sgk_kodu','—')}\n"
                f"SUT Maddesi:    {kural.get('sut_maddesi','—')}\n"
                f"Rapor Kodu:     {kural.get('rapor_kodu','—')}\n"
                f"Rapor Gerekli:  {'EVET' if kural.get('rapor_gerekli') else 'HAYIR'}\n"
                f"Maks Doz:       {kural.get('raporlu_maks_doz','—') or '—'}\n"
                f"Kontrol Tipi:   {kural.get('kontrol_tipi','—')}\n"
                f"\n--- AÇIKLAMA ---\n{kural.get('aciklama') or '(yok)'}\n"
            )
            yasak = kural.get("birlikte_yasaklar")
            if yasak:
                metin += f"\n--- BİRLİKTE YASAKLAR ---\n{yasak}\n"
            self.txt_sut.insert("end", metin)
        self.txt_sut.config(state="disabled")

    # =================================================================
    # Yardımcı
    # =================================================================
    def _durum_yaz(self, msg: str):
        try:
            self.durum_bar.config(text=msg)
        except Exception:
            pass

    def _kapat(self):
        try:
            if self.botanik:
                self.botanik.kapat()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        if self.ana_menu_callback:
            self.ana_menu_callback()


def matrisi_ac(parent_root: Optional[tk.Tk] = None,
                kullanici_id: Optional[int] = None) -> tk.Toplevel:
    """Pencere açma yardımcısı. recete_rapor_kontrol_gui'den çağrılır."""
    pencere = tk.Toplevel(parent_root) if parent_root else tk.Tk()
    SUTMatrisiGUI(pencere, kullanici_id=kullanici_id)
    return pencere


def main():
    """Standalone çalıştırma."""
    logging.basicConfig(level=logging.INFO,
                         format="%(asctime)s [%(levelname)s] %(message)s")
    root = tk.Tk()
    SUTMatrisiGUI(root)

    # Sağ panele otomatik update için sheet selection callback bağla
    # (çünkü tksheet'in select event'ini __init__'te bağlamak için
    # bu noktada sheet hazır olmalı — main fonksiyonu içinde bağlıyoruz)
    root.mainloop()


if __name__ == "__main__":
    main()
