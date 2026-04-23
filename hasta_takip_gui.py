"""
Hasta Takip & WhatsApp Mesaj Modülü - GUI

Ana sekmeler:
  1. Yazdırma Günü Gelen Hastalar     (tıklama → wa.me açar)
  2. Hasta Portföyü                    (geliş sıklığı, son geliş)
  3. Devamlılık Raporu                 (reçete adedi, kaç gün oldu)
  4. Ayarlar                           (mod, tolerans, saat, şablon)
  5. Gönderim Log                      (geçmiş mesajlar)
"""

import logging
import os
import shutil
import subprocess
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk
from typing import Dict, Optional  # noqa: F401 — method annotation

try:
    from tkcalendar import DateEntry
    _TAKVIM_VAR = True
except ImportError:
    DateEntry = None
    _TAKVIM_VAR = False

from hasta_takip_db import HastaTakipDB
from hasta_takip_kuyruk import HastaTakipAyarlari, MesajKuyrugu

logger = logging.getLogger(__name__)


class HastaTakipGUI:
    """Ana sekme — 5 alt sekme içerir."""

    def __init__(self, root: tk.Tk, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("Hasta Takip & WhatsApp Mesaj")
        self.root.geometry("1280x780")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        # Kaydedilmiş pencere yerleşimini uygula (varsa)
        try:
            from pencere_yerlesim import hasta_takibe_uygula
            hasta_takibe_uygula(self.root)
        except Exception as e:
            logger.debug(f"Pencere yerleşim uygulanamadı: {e}")

        self.ayarlar = HastaTakipAyarlari.yukle()
        self.kuyruk = MesajKuyrugu()
        self.db: HastaTakipDB = None

        self.root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._arayuz_olustur()

    # ----------------------------------------------------------------- UI
    def _arayuz_olustur(self):
        ust = tk.Frame(self.root, bg="#263238", height=50)
        ust.pack(fill="x")
        tk.Label(
            ust, text="👥 Hasta Takip & WhatsApp Mesaj",
            font=("Arial", 14, "bold"), bg="#263238", fg="white",
        ).pack(side="left", padx=15, pady=10)
        tk.Button(
            ust, text="Ana Menüye Dön", command=self._kapat,
            bg="#455A64", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=15, pady=10)
        tk.Button(
            ust, text="📐 Yerleşimi Kaydet", command=self._yerlesimi_kaydet,
            bg="#37474F", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=(0, 6), pady=10)
        tk.Button(
            ust, text="📐 Yerleşimi Uygula", command=self._yerlesimi_uygula,
            bg="#546E7A", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=(0, 6), pady=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Önce ayarlar sekmesi (var_mod vs. diğer sekmelerde kullanılıyor)
        self.sekme_ayarlar = self._sekme_ayarlar_olustur()
        self.sekme_yazdirma = self._sekme_yazdirma_olustur()
        self.sekme_portfoy = self._sekme_portfoy_olustur()
        self.sekme_devamlilik = self._sekme_devamlilik_olustur()
        self.sekme_rapor_bitis = self._sekme_rapor_bitis_olustur()
        self.sekme_log = self._sekme_log_olustur()

        self.notebook.add(self.sekme_yazdirma, text="📬 Yazdırma Günü Gelen")
        self.notebook.add(self.sekme_portfoy, text="📊 Hasta Portföyü")
        self.notebook.add(self.sekme_devamlilik, text="📅 Devamlılık")
        self.notebook.add(self.sekme_rapor_bitis, text="📑 Rapor Bitiş Takibi")
        self.notebook.add(self.sekme_ayarlar, text="⚙ Ayarlar")
        self.notebook.add(self.sekme_log, text="🧾 Gönderim Log")

        self._durum_frame = tk.Frame(self.root, bg="#ECEFF1")
        self._durum_frame.pack(fill="x", side="bottom")
        self.durum_bar = tk.Label(
            self._durum_frame, text="Hazır", anchor="w",
            bg="#ECEFF1", fg="#37474F", padx=10,
        )
        self.durum_bar.pack(fill="x", side="left", expand=True)
        self.durum_progress = ttk.Progressbar(
            self._durum_frame, mode="indeterminate", length=160,
        )
        self.durum_progress.pack(side="right", padx=(0, 8), pady=2)
        self._spinner_kareler = ["⏳", "⌛"]
        self._spinner_idx = 0
        self._spinner_after_id = None
        self._spinner_metin = ""
        self._yazdirma_calisiyor = False

        # Tüm sekmeler oluştuktan sonra kuyruğu ekrana yükle
        self._kuyruktan_yukle()

        # Ayarda açıksa oturum canlı tutmayı otomatik başlat
        if getattr(self.ayarlar, "oturum_canli_tut", False):
            try:
                self._oturum_canli_toggle()
            except Exception as e:
                logger.debug(f"Otomatik oturum başlatma hatası: {e}")

    # ================================================================= SEKME 1
    def _sekme_yazdirma_olustur(self) -> tk.Frame:
        """Dar ekran için iş akışına göre düzenlenmiş kompakt tasarım:

            [Üst]     Liste yönetimi    : Yenile · Sütunlar · Oturum
            [Filtre]  Tarih aralığı     : Baş(-15g) · Bit(bugün) · Uygula·Temizle
            [Tablo]   Hasta kuyruğu
            [Mini]    Mesaj hazırlığı   : İlaç Listesi · İlaç Geçmişinden Güncelle
            [Mesaj]   Önizleme kutusu
            [Alt]     Gönderim+durum    : WhatsApp · Kopyala │ Gönderildi · İptal
        """
        f = tk.Frame(self.notebook, bg="white")

        # ---- 1. Üst kontrol: LİSTE YÖNETİMİ ----------------------------
        kontrol = tk.Frame(f, bg="white")
        kontrol.pack(fill="x", padx=8, pady=(6, 2))

        tk.Button(
            kontrol, text="🔄 Yenile", command=self._yazdirma_yenile,
            bg="#1976D2", fg="white", bd=0, padx=10, pady=5,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            kontrol, text="⚙ Sütunlar", command=self._sutun_ayarlari_ac,
            bg="#546E7A", fg="white", bd=0, padx=8, pady=5,
            font=("Arial", 9),
        ).pack(side="left", padx=4)

        tk.Button(
            kontrol, text="💊 Kategoriler", command=self._kategori_ayarlari_ac,
            bg="#00897B", fg="white", bd=0, padx=8, pady=5,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=4)

        # Oturum canlı tutma (arka plan servisi) + canlı geri sayım
        self.var_oturum_canli = tk.BooleanVar(
            value=bool(getattr(self.ayarlar, "oturum_canli_tut", False))
        )
        self.lbl_oturum_durum = tk.Label(
            kontrol, text="", bg="white", fg="#455A64",
            font=("Arial", 9),
        )
        self.lbl_oturum_durum.pack(side="right", padx=(0, 4))
        tk.Button(
            kontrol, text="⚡ Şimdi Tazele",
            command=self._oturum_simdi_yenile,
            bg="#EF6C00", fg="white", bd=0, padx=8, pady=4,
            font=("Arial", 9),
        ).pack(side="right", padx=4)
        tk.Checkbutton(
            kontrol, text="🔒 Oturum",
            variable=self.var_oturum_canli,
            command=self._oturum_canli_toggle,
            bg="white", fg="#37474F", font=("Arial", 9, "bold"),
            activebackground="white",
        ).pack(side="right", padx=4)

        # ---- 2. Sayaç satırı -------------------------------------------
        self.lbl_sayac = tk.Label(
            f, text="", font=("Arial", 9, "bold"),
            bg="white", fg="#37474F", anchor="w",
        )
        self.lbl_sayac.pack(fill="x", padx=10, pady=(0, 2))

        # ---- 3a. Seçenek checkbox'ları (filtre satırının üstünde) ------
        secenek_bar = tk.Frame(f, bg="white")
        secenek_bar.pack(fill="x", padx=8, pady=(2, 2))

        self.var_haber_gizle = tk.BooleanVar(
            value=bool(getattr(self.ayarlar, "haber_verilenleri_gizle", False))
        )
        tk.Checkbutton(
            secenek_bar, text="📢 Haber verilenleri getirme (Botanik)",
            variable=self.var_haber_gizle, bg="white",
            font=("Arial", 9),
            command=self._haber_gizle_degisti,
        ).pack(side="left", padx=(2, 10))

        self.var_haber_gizle_yerel = tk.BooleanVar(
            value=bool(getattr(self.ayarlar, "haber_verilenleri_gizle_yerel", False))
        )
        tk.Checkbutton(
            secenek_bar, text="🏠 Haber verilenleri getirme (Yerel)",
            variable=self.var_haber_gizle_yerel, bg="white",
            font=("Arial", 9),
            command=self._haber_gizle_yerel_degisti,
        ).pack(side="left", padx=(0, 10))

        self.var_gonderilenleri_goster = tk.BooleanVar(
            value=bool(getattr(self.ayarlar, "gonderilenleri_goster", False))
        )
        tk.Checkbutton(
            secenek_bar, text="📬 Mesaj atılanları da getir",
            variable=self.var_gonderilenleri_goster, bg="white",
            font=("Arial", 9),
            command=self._gonderilenleri_goster_degisti,
        ).pack(side="left", padx=2)

        self.var_ilac_rapor_birlesik = tk.BooleanVar(
            value=bool(getattr(self.ayarlar, "ilac_rapor_birlesik", False))
        )
        tk.Checkbutton(
            secenek_bar,
            text="💊+📑 Rapor bitişini de ekle",
            variable=self.var_ilac_rapor_birlesik, bg="white",
            font=("Arial", 9),
            command=self._ilac_rapor_birlesik_degisti,
        ).pack(side="left", padx=(10, 2))

        # ---- 3b. Filtre (varsayılan: -15 gün → bugün, aktif) -----------
        filtre = tk.Frame(f, bg="white")
        filtre.pack(fill="x", padx=8, pady=(0, 4))

        tk.Label(filtre, text="📅", bg="white",
                 font=("Arial", 10)).pack(side="left", padx=(0, 4))

        # Varsayılan: filtre aktif, aralık: bugün-eski_kayit_gun → bugün
        # (spinbox ile senkron; tarama ile aynı aralığı kapsasın)
        self._filt_bas_aktif = tk.BooleanVar(value=True)
        self._filt_bit_aktif = tk.BooleanVar(value=True)
        _eski = int(getattr(self.ayarlar, "eski_kayit_gun", 30) or 30)
        varsayilan_bas = date.today() - timedelta(days=_eski)
        varsayilan_bit = date.today()

        tk.Label(filtre, text="Baş:", bg="white",
                 font=("Arial", 9)).pack(side="left")
        if _TAKVIM_VAR:
            self.dt_filt_bas = DateEntry(
                filtre, width=10, date_pattern="dd.mm.yyyy",
                background="#1976D2", foreground="white",
                borderwidth=2, locale="tr_TR",
            )
            self.dt_filt_bas.set_date(varsayilan_bas)
            self.dt_filt_bas.pack(side="left", padx=4)
        else:
            self.var_filt_bas = tk.StringVar(value=varsayilan_bas.isoformat())
            tk.Entry(filtre, textvariable=self.var_filt_bas, width=10).pack(
                side="left", padx=4)

        tk.Label(filtre, text="Bit:", bg="white",
                 font=("Arial", 9)).pack(side="left", padx=(6, 0))
        if _TAKVIM_VAR:
            self.dt_filt_bit = DateEntry(
                filtre, width=10, date_pattern="dd.mm.yyyy",
                background="#1976D2", foreground="white",
                borderwidth=2, locale="tr_TR",
            )
            self.dt_filt_bit.set_date(varsayilan_bit)
            self.dt_filt_bit.pack(side="left", padx=4)
        else:
            self.var_filt_bit = tk.StringVar(value=varsayilan_bit.isoformat())
            tk.Entry(filtre, textvariable=self.var_filt_bit, width=10).pack(
                side="left", padx=4)

        tk.Button(
            filtre, text="Uygula", command=self._filtre_uygula,
            bg="#455A64", fg="white", bd=0, padx=8, pady=2,
            font=("Arial", 9),
        ).pack(side="left", padx=(6, 2))
        tk.Button(
            filtre, text="Temizle", command=self._filtre_temizle,
            bg="#90A4AE", fg="white", bd=0, padx=8, pady=2,
            font=("Arial", 9),
        ).pack(side="left", padx=2)

        # Batch pencere spinbox — ayarlar.batch_bekleme_gun ile senkron
        tk.Label(filtre, text=" 🔗 Batch:", bg="white",
                 font=("Arial", 9, "bold")).pack(side="left", padx=(10, 2))
        self.var_batch = tk.IntVar(
            value=int(getattr(self.ayarlar, "batch_bekleme_gun", 5) or 0)
        )
        self.sp_batch = tk.Spinbox(
            filtre, from_=0, to=60, width=3, increment=1,
            textvariable=self.var_batch, font=("Arial", 9, "bold"),
            command=self._batch_degisti,
        )
        self.sp_batch.pack(side="left")
        tk.Label(filtre, text="gün", bg="white",
                 font=("Arial", 9)).pack(side="left", padx=(2, 0))
        self.sp_batch.bind("<Return>", lambda e: self._batch_degisti())
        self.sp_batch.bind("<FocusOut>", lambda e: self._batch_degisti())

        # Eski kayıt penceresi — bitişi kaç gün öncesinden itibaren taransın
        tk.Label(filtre, text=" 📅 Son:", bg="white",
                 font=("Arial", 9, "bold")).pack(side="left", padx=(10, 2))
        self.var_eski_gun = tk.IntVar(
            value=int(getattr(self.ayarlar, "eski_kayit_gun", 30) or 0)
        )
        self.sp_eski = tk.Spinbox(
            filtre, from_=0, to=365, width=4, increment=5,
            textvariable=self.var_eski_gun, font=("Arial", 9, "bold"),
            command=self._eski_gun_degisti,
        )
        self.sp_eski.pack(side="left")
        tk.Label(filtre, text="gün önce bitmiş", bg="white",
                 font=("Arial", 9)).pack(side="left", padx=(2, 0))
        self.sp_eski.bind("<Return>", lambda e: self._eski_gun_degisti())
        self.sp_eski.bind("<FocusOut>", lambda e: self._eski_gun_degisti())

        self._filt_durum_lbl = tk.Label(
            filtre, text="", bg="white", fg="#455A64", font=("Arial", 8, "italic"),
        )
        self._filt_durum_lbl.pack(side="left", padx=6)

        # ---- 4. Dikey bölme: TABLO (üst) + MESAJ ÖNİZLEME (alt) --------
        bol = tk.PanedWindow(
            f, orient="vertical", sashrelief="raised",
            bg="#CFD8DC", sashwidth=6,
        )
        bol.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # ÜST: hasta tablosu
        ust = tk.Frame(bol, bg="white")
        bol.add(ust, minsize=180, stretch="always")

        kols = ("planli_tarih", "hasta", "tc", "tel", "ilac_sayi",
                "menzil", "ziyaret", "son_gelis", "gun", "takip")
        self.tv_yaz = ttk.Treeview(
            ust, columns=kols, show="headings", selectmode="browse",
        )
        self._sutun_tanimlari = [
            ("planli_tarih", "📅 Planlı",   110, "center"),
            ("hasta",        "Hasta",       160, "w"),
            ("tc",           "T.C.",        100, "center"),
            ("tel",          "Telefon",     100, "center"),
            ("ilac_sayi",    "İlaç",         45, "center"),
            ("menzil",       "🔗 Menzil",    70, "center"),
            ("ziyaret",      "Ziyaret",      60, "center"),
            ("son_gelis",    "Son Geliş",    90, "center"),
            ("gun",          "Gün Önce",     65, "center"),
            ("takip",        "Takipli",      55, "center"),
        ]
        for k, b, w, a in self._sutun_tanimlari:
            self.tv_yaz.heading(k, text=b)
            self.tv_yaz.column(k, width=w, anchor=a, stretch=False)
        self._sutun_gorunurlugu_uygula()
        self.tv_yaz.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(ust, orient="vertical", command=self.tv_yaz.yview)
        self.tv_yaz.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_yaz.bind("<<TreeviewSelect>>", lambda e: self._secim_guncelle())
        self.tv_yaz.bind("<Control-Shift-C>", lambda e: self._tc_kopyala())
        self.tv_yaz.bind("<Control-Shift-c>", lambda e: self._tc_kopyala())
        self.root.bind("<Control-Shift-C>", lambda e: self._tc_kopyala())
        self.root.bind("<Control-Shift-c>", lambda e: self._tc_kopyala())
        # Sağ tık menüsü
        self.menu_yaz = tk.Menu(self.tv_yaz, tearoff=0)
        self.menu_yaz.add_command(label="📋 T.C. Kimlik No Kopyala (Ctrl+Shift+C)",
                                  command=self._tc_kopyala)
        self.menu_yaz.add_command(label="📋 Telefonu Kopyala",
                                  command=self._tel_kopyala)
        self.menu_yaz.add_command(label="📋 Hasta Adını Kopyala",
                                  command=self._ad_kopyala)
        self.menu_yaz.add_separator()
        self.menu_yaz.add_command(label="💊 Medulada İlaç Listesi Aç",
                                  command=self._medulada_ilac_listesi_ac)
        self.menu_yaz.add_command(label="👤 Başka Hastaya At...",
                                  command=self._farkli_kisiye_gonder)
        self.tv_yaz.bind("<Button-3>", self._yaz_sagtik)

        # ALT: mesaj hazırlık mini-bar + önizleme
        alt = tk.Frame(bol, bg="#FAFAFA")
        bol.add(alt, minsize=160, stretch="always")

        baslik = tk.Frame(alt, bg="#FAFAFA")
        baslik.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(
            baslik, text="💬 Mesaj Önizleme", font=("Arial", 10, "bold"),
            bg="#FAFAFA", fg="#1976D2",
        ).pack(side="left")

        # 5. Mesaj HAZIRLIK butonları — mesaj kutusunun hemen üstünde
        hazirlik = tk.Frame(alt, bg="#FAFAFA")
        hazirlik.pack(fill="x", padx=10, pady=(0, 4))
        tk.Button(
            hazirlik, text="💊 İlaç Listesi Aç",
            command=self._medulada_ilac_listesi_ac,
            bg="#0288D1", fg="white", bd=0, padx=10, pady=5,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=(0, 4))
        tk.Button(
            hazirlik, text="🔄 İlaç Geçmişinden Güncelle",
            command=self._mesaji_ilac_gecmisinden_guncelle,
            bg="#1976D2", fg="white", bd=0, padx=10, pady=5,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=4)
        # Otobüsten yolcu indir: ileri tarihli ilaçları kayıttan çıkar,
        # bugünkü ilaçlar hemen gönderilebilir olsun, satır açık sarı görünsün
        tk.Button(
            hazirlik, text="🚏 Bekleteni İndir",
            command=self._bekleteni_indir,
            bg="#F9A825", fg="white", bd=0, padx=10, pady=5,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=4)

        mesaj_sarma = tk.Frame(alt, bg="#FAFAFA")
        mesaj_sarma.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.txt_mesaj = tk.Text(
            mesaj_sarma, wrap="word", font=("Consolas", 10),
            bg="white", relief="solid", bd=1, height=6,
        )
        self.txt_mesaj.pack(side="left", fill="both", expand=True)
        msb = ttk.Scrollbar(mesaj_sarma, orient="vertical",
                            command=self.txt_mesaj.yview)
        self.txt_mesaj.configure(yscrollcommand=msb.set)
        msb.pack(side="right", fill="y")

        # ---- 6. Alt bar: GÖNDER + DURUM işaretleme ---------------------
        # Sol: gönder aksiyonları | Sağ: kuyruk durum işaretleme
        aksiyon = tk.Frame(f, bg="#ECEFF1")
        aksiyon.pack(fill="x", padx=8, pady=(2, 6))

        sol_aks = tk.Frame(aksiyon, bg="#ECEFF1")
        sol_aks.pack(side="left", pady=4)
        tk.Button(
            sol_aks, text="📱 WhatsApp'ta Aç", command=self._wa_ac,
            bg="#25D366", fg="white", bd=0, padx=12, pady=6,
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(0, 4))
        tk.Button(
            sol_aks, text="📋 Kopyala", command=self._panoya_kopyala,
            bg="#546E7A", fg="white", bd=0, padx=10, pady=6,
            font=("Arial", 9),
        ).pack(side="left", padx=2)
        tk.Button(
            sol_aks, text="👤 Farklı Kişiye Gönder", command=self._farkli_kisiye_gonder,
            bg="#00796B", fg="white", bd=0, padx=10, pady=6,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=2)

        sag_aks = tk.Frame(aksiyon, bg="#ECEFF1")
        sag_aks.pack(side="right", pady=4)
        tk.Button(
            sag_aks, text="✔ Gönderildi", command=self._gonderildi_manuel,
            bg="#7B1FA2", fg="white", bd=0, padx=10, pady=6,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=2)
        tk.Button(
            sag_aks, text="💊 İlacını Aldı", command=self._ilac_alindi,
            bg="#2E7D32", fg="white", bd=0, padx=10, pady=6,
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=2)
        tk.Button(
            sag_aks, text="❌ İptal", command=self._secili_iptal,
            bg="#E53935", fg="white", bd=0, padx=10, pady=6,
            font=("Arial", 9),
        ).pack(side="left", padx=2)

        self._kuyruk_sonuclari: list = []
        return f

    # ================================================================= SEKME 2
    def _sekme_portfoy_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")

        # ---- Filtre paneli ---------------------------------------------
        filt = tk.LabelFrame(
            f, text="Filtreler", bg="white", fg="#1976D2",
            font=("Arial", 10, "bold"), padx=10, pady=8,
        )
        filt.pack(fill="x", padx=10, pady=(8, 4))

        bugun = date.today()
        # Tarih aralığı
        tk.Label(filt, text="Reçete tarih aralığı:", bg="white").grid(row=0, column=0, sticky="w")
        self.var_pf_bas = tk.StringVar(value=(bugun.replace(year=bugun.year - 1)).isoformat())
        self.var_pf_bit = tk.StringVar(value=bugun.isoformat())
        tk.Entry(filt, textvariable=self.var_pf_bas, width=12).grid(row=0, column=1, padx=4)
        tk.Label(filt, text="—", bg="white").grid(row=0, column=2)
        tk.Entry(filt, textvariable=self.var_pf_bit, width=12).grid(row=0, column=3, padx=4)

        # Son geliş sonra
        tk.Label(filt, text="   Son geliş ≥:", bg="white").grid(row=0, column=4, sticky="w")
        self.var_pf_songelis = tk.StringVar(value="")
        tk.Entry(filt, textvariable=self.var_pf_songelis, width=12).grid(row=0, column=5, padx=4)
        tk.Label(filt, text="(YYYY-AA-GG, boş=filtresiz)", bg="white", fg="#9E9E9E", font=("Arial", 8)).grid(row=0, column=6, sticky="w")

        # Ziyaret min/max
        tk.Label(filt, text="Ziyaret sayısı:", bg="white").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_pf_min = tk.StringVar(value="")
        self.var_pf_max = tk.StringVar(value="")
        tk.Entry(filt, textvariable=self.var_pf_min, width=6).grid(row=1, column=1, sticky="w", pady=(6, 0))
        tk.Label(filt, text="≤ ≤", bg="white").grid(row=1, column=2, pady=(6, 0))
        tk.Entry(filt, textvariable=self.var_pf_max, width=6).grid(row=1, column=3, sticky="w", pady=(6, 0))

        # Telefonlu & takipli
        self.var_pf_tel = tk.BooleanVar(value=False)
        self.var_pf_takip = tk.BooleanVar(value=False)
        tk.Checkbutton(
            filt, text="Sadece telefonu olanlar", variable=self.var_pf_tel, bg="white",
        ).grid(row=1, column=4, sticky="w", pady=(6, 0), padx=(10, 4))
        tk.Checkbutton(
            filt, text="Sadece takipli", variable=self.var_pf_takip, bg="white",
        ).grid(row=1, column=5, sticky="w", pady=(6, 0), columnspan=2)

        # Yenile butonu + sayac
        btn_frame = tk.Frame(filt, bg="white")
        btn_frame.grid(row=2, column=0, columnspan=7, sticky="we", pady=(8, 0))
        tk.Button(
            btn_frame, text="🔄 Filtreyi Uygula / Yenile", command=self._portfoy_yukle,
            bg="#1976D2", fg="white", bd=0, padx=16, pady=6,
        ).pack(side="left")
        self.lbl_portfoy = tk.Label(btn_frame, text="", bg="white", fg="#455A64")
        self.lbl_portfoy.pack(side="left", padx=12)

        # ---- Liste + detay paneli --------------------------------------
        bol = tk.PanedWindow(f, orient="horizontal", sashrelief="raised", bg="white")
        bol.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        sol = tk.Frame(bol, bg="white")
        bol.add(sol, minsize=520)

        kols = ("hasta", "tel", "ziyaret", "recete", "ilk", "son", "gun", "takip")
        self.tv_portfoy = ttk.Treeview(
            sol, columns=kols, show="headings", selectmode="browse",
        )
        baslik = {
            "hasta": ("Hasta", 220, "w"),
            "tel": ("Telefon", 100, "center"),
            "ziyaret": ("Ziyaret", 60, "center"),
            "recete": ("Reçete", 60, "center"),
            "ilk": ("İlk Geliş", 90, "center"),
            "son": ("Son Geliş", 90, "center"),
            "gun": ("Gün Önce", 70, "center"),
            "takip": ("Takipli", 60, "center"),
        }
        for k, (b, w, a) in baslik.items():
            self.tv_portfoy.heading(k, text=b)
            self.tv_portfoy.column(k, width=w, anchor=a)
        self.tv_portfoy.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sol, orient="vertical", command=self.tv_portfoy.yview)
        self.tv_portfoy.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_portfoy.bind("<<TreeviewSelect>>", lambda e: self._portfoy_hasta_detay())

        # Detay paneli — sağda Notebook
        sag = tk.Frame(bol, bg="#FAFAFA")
        bol.add(sag, minsize=560)

        self.lbl_pf_detay = tk.Label(
            sag, text="◀ Soldan bir hasta seçin",
            bg="#FAFAFA", fg="#607D8B",
            font=("Arial", 11, "bold"), anchor="w",
        )
        self.lbl_pf_detay.pack(fill="x", padx=10, pady=(10, 6))

        self.nb_detay = ttk.Notebook(sag)
        self.nb_detay.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Raporlar
        f_rap = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_rap = ttk.Treeview(
            f_rap, columns=("no", "tur", "tarih", "bitis", "kalan", "hastane"),
            show="headings",
        )
        for k, b, w in [
            ("no", "Rapor No", 90), ("tur", "Tür", 140),
            ("tarih", "Tarih", 90), ("bitis", "Bitiş", 90),
            ("kalan", "Bitiş kalan", 80), ("hastane", "Hastane", 150),
        ]:
            self.tv_pf_rap.heading(k, text=b)
            self.tv_pf_rap.column(k, width=w)
        self.tv_pf_rap.pack(fill="both", expand=True)
        self.nb_detay.add(f_rap, text="📋 Raporlar")

        # Yaklaşan yazdırma
        f_yaz = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_yaz = ttk.Treeview(
            f_yaz, columns=("urun", "bitis", "yazdirma", "kalan", "rapor"),
            show="headings",
        )
        for k, b, w in [
            ("urun", "İlaç", 220), ("bitis", "Bitiş", 90),
            ("yazdirma", "Yazdırma", 90), ("kalan", "Kalan Gün", 80),
            ("rapor", "Rapor No", 100),
        ]:
            self.tv_pf_yaz.heading(k, text=b)
            self.tv_pf_yaz.column(k, width=w)
        self.tv_pf_yaz.pack(fill="both", expand=True)
        self.nb_detay.add(f_yaz, text="📬 Yaklaşan/Geçen Yazdırmalar")

        # İlaç geçmişi
        f_il = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_il = ttk.Treeview(
            f_il, columns=("tarih", "urun", "adet", "bitis", "rapor"),
            show="headings",
        )
        for k, b, w in [
            ("tarih", "Reçete Tarihi", 100), ("urun", "İlaç", 250),
            ("adet", "Adet", 50), ("bitis", "Bitiş", 90),
            ("rapor", "Rapor No", 100),
        ]:
            self.tv_pf_il.heading(k, text=b)
            self.tv_pf_il.column(k, width=w)
        self.tv_pf_il.pack(fill="both", expand=True)
        self.nb_detay.add(f_il, text="💊 İlaç Geçmişi")

        return f

    # ================================================================= SEKME 3
    def _sekme_devamlilik_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(
            top, text="🔄 Yenile", command=self._devamlilik_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left")
        self.lbl_devam = tk.Label(top, text="", bg="white", fg="#455A64")
        self.lbl_devam.pack(side="left", padx=12)

        kols = ("hasta", "tel", "dogum", "recete", "son", "gun", "takip")
        self.tv_devam = ttk.Treeview(f, columns=kols, show="headings")
        for k, b, w, a in [
            ("hasta", "Hasta", 260, "w"),
            ("tel", "Telefon", 110, "center"),
            ("dogum", "Doğum", 100, "center"),
            ("recete", "Reçete Adedi", 100, "center"),
            ("son", "Son Reçete", 110, "center"),
            ("gun", "Kaç Gün Oldu", 110, "center"),
            ("takip", "Takipli", 70, "center"),
        ]:
            self.tv_devam.heading(k, text=b)
            self.tv_devam.column(k, width=w, anchor=a)
        self.tv_devam.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        sb = ttk.Scrollbar(self.tv_devam, orient="vertical", command=self.tv_devam.yview)
        self.tv_devam.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        return f

    # ================================================================= SEKME 4
    def _sekme_ayarlar_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        kanvas = tk.Canvas(f, bg="white", highlightthickness=0)
        scroll = ttk.Scrollbar(f, orient="vertical", command=kanvas.yview)
        icerik = tk.Frame(kanvas, bg="white")
        icerik.bind(
            "<Configure>",
            lambda e: kanvas.configure(scrollregion=kanvas.bbox("all")),
        )
        kanvas.create_window((0, 0), window=icerik, anchor="nw")
        kanvas.configure(yscrollcommand=scroll.set)
        kanvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scroll.pack(side="right", fill="y")

        def grup(baslik):
            g = tk.LabelFrame(
                icerik, text=baslik, bg="white", fg="#1976D2",
                font=("Arial", 10, "bold"), padx=12, pady=10,
            )
            g.pack(fill="x", pady=8, padx=4)
            return g

        # Gönderim modu
        g1 = grup("Gönderim Modu")
        self.var_mod = tk.StringVar(value=self.ayarlar.gonderim_modu)
        for kod, et in [
            ("anlik", "Anlık (her tarama sonrası hemen listele)"),
            ("pazartesi", "Pazartesi birleşik (hafta içi biriktir, pazartesi gönder)"),
            ("periyodik", "Periyodik (her X günde bir listele)"),
        ]:
            tk.Radiobutton(
                g1, text=et, variable=self.var_mod, value=kod,
                bg="white", anchor="w",
            ).pack(fill="x", anchor="w")

        self.var_periyot = tk.IntVar(value=self.ayarlar.periyot_gun)
        self.var_gonderim_gun = tk.IntVar(value=self.ayarlar.toplu_gonderim_gunu)
        fr = tk.Frame(g1, bg="white")
        fr.pack(fill="x", pady=(6, 0))
        tk.Label(fr, text="Periyot (gün):", bg="white").pack(side="left")
        tk.Spinbox(fr, from_=1, to=30, width=4, textvariable=self.var_periyot).pack(side="left", padx=4)
        tk.Label(fr, text="   Toplu gönderim günü:", bg="white").pack(side="left", padx=(16, 4))
        ttk.Combobox(
            fr, state="readonly", width=14,
            values=["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
        ).pack(side="left")
        # NOTE: combobox'ı sakla, açıkken seçimi var_gonderim_gun'e yaz
        self._cb_gun = fr.winfo_children()[-1]
        self._cb_gun.current(self.ayarlar.toplu_gonderim_gunu)
        self._cb_gun.bind("<<ComboboxSelected>>", lambda e: self.var_gonderim_gun.set(self._cb_gun.current()))

        # Tolerans
        g2 = grup("Tolerans")
        fr2 = tk.Frame(g2, bg="white")
        fr2.pack(fill="x")
        tk.Label(fr2, text="Hafta sonu tolerans (gün):", bg="white").grid(row=0, column=0, sticky="w")
        self.var_hs = tk.IntVar(value=self.ayarlar.hafta_sonu_tolerans_gun)
        tk.Spinbox(fr2, from_=0, to=14, width=4, textvariable=self.var_hs).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(fr2, text="   Rapor yazdırma tolerans (gün):", bg="white").grid(row=0, column=2, sticky="w", padx=(16, 4))
        self.var_rt = tk.IntVar(value=self.ayarlar.rapor_yazdirma_tolerans_gun)
        tk.Spinbox(fr2, from_=0, to=30, width=4, textvariable=self.var_rt).grid(row=0, column=3, sticky="w")
        tk.Label(fr2, text="   Eski kayıt gün (gürültü filtresi):", bg="white").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_eski = tk.IntVar(value=self.ayarlar.eski_kayit_gun)
        tk.Spinbox(fr2, from_=0, to=365, width=5, textvariable=self.var_eski).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))

        # Filtreler
        g3 = grup("Filtreler")
        self.var_takipli = tk.BooleanVar(value=self.ayarlar.sadece_takipli)
        tk.Checkbutton(
            g3, text="Sadece Takipli Hastalar (Musteri.MusteriTakipli=1)",
            variable=self.var_takipli, bg="white", anchor="w",
        ).pack(fill="x", anchor="w")

        self.var_sadece_raporlu = tk.BooleanVar(
            value=getattr(self.ayarlar, "sadece_raporlu", True)
        )
        tk.Checkbutton(
            g3, text="Sadece Raporlu İlaçlar (raporsuz ilaçlar listelenmesin)",
            variable=self.var_sadece_raporlu, bg="white", anchor="w",
        ).pack(fill="x", anchor="w")

        # Raporsuz istisna ürün listesi
        istisna_fr = tk.Frame(g3, bg="white")
        istisna_fr.pack(fill="x", pady=(6, 0))
        tk.Label(
            istisna_fr, text="Raporsuz olsa da listelenecek ürünler (UrunId, virgülle):",
            bg="white",
        ).pack(anchor="w")
        self.var_raporsuz_istisna = tk.StringVar(
            value=",".join(str(x) for x in getattr(self.ayarlar, "raporsuz_istisna_urunler", []))
        )
        tk.Entry(istisna_fr, textvariable=self.var_raporsuz_istisna, width=70).pack(
            anchor="w", pady=(2, 0)
        )
        tk.Label(
            istisna_fr,
            text="(UrunId'leri Botanik'ten öğrenip buraya yazın. Ör: 23638,1702,1706)",
            bg="white", fg="#607D8B", font=("Arial", 8),
        ).pack(anchor="w")

        fr3 = tk.Frame(g3, bg="white")
        fr3.pack(fill="x", pady=(6, 0))
        tk.Label(fr3, text="Veri kaynağı:", bg="white").pack(side="left")
        self.var_kaynak = tk.StringVar(value=self.ayarlar.kaynak)
        for v in ("RECETE", "MEDULA", "BIRLESIK"):
            tk.Radiobutton(
                fr3, text=v, variable=self.var_kaynak, value=v, bg="white",
            ).pack(side="left", padx=6)

        # Çalışma saatleri
        g4 = grup("Çalışma Saatleri (dışında gönderim penceresi kapalı)")
        fr4 = tk.Frame(g4, bg="white")
        fr4.pack(fill="x")
        self.var_bas = tk.StringVar(value=self.ayarlar.calisma_baslangic)
        self.var_bit = tk.StringVar(value=self.ayarlar.calisma_bitis)
        tk.Label(fr4, text="Başlangıç:", bg="white").pack(side="left")
        tk.Entry(fr4, textvariable=self.var_bas, width=7).pack(side="left", padx=4)
        tk.Label(fr4, text="   Bitiş:", bg="white").pack(side="left")
        tk.Entry(fr4, textvariable=self.var_bit, width=7).pack(side="left", padx=4)

        # Eczane bilgisi
        g5 = grup("Eczane Bilgisi")
        fr5 = tk.Frame(g5, bg="white")
        fr5.pack(fill="x")
        self.var_ec_ad = tk.StringVar(value=self.ayarlar.eczane_adi)
        self.var_ec_tel = tk.StringVar(value=self.ayarlar.eczane_tel)
        tk.Label(fr5, text="Eczane Adı:", bg="white").grid(row=0, column=0, sticky="w")
        tk.Entry(fr5, textvariable=self.var_ec_ad, width=40).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(fr5, text="Telefon:", bg="white").grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Entry(fr5, textvariable=self.var_ec_tel, width=40).grid(row=1, column=1, sticky="w", padx=4, pady=(4, 0))

        # Şablon
        g6 = grup("Mesaj Şablonu (placeholders: {hasta_adi} {ilac_listesi} {eczane_adi} {eczane_tel})")
        self.txt_sablon = tk.Text(g6, height=6, font=("Consolas", 10))
        self.txt_sablon.pack(fill="x")
        self.txt_sablon.insert("1.0", self.ayarlar.mesaj_sablonu)

        tk.Label(g6, text="İlaç satır formatı ({urun_adi}):", bg="white").pack(anchor="w", pady=(8, 2))
        self.var_satir = tk.StringVar(value=self.ayarlar.ilac_satir_formati)
        tk.Entry(g6, textvariable=self.var_satir, width=60).pack(anchor="w")

        # Rapor bitiş şablonu
        g7 = grup(
            "Rapor Bitiş Mesaj Şablonu "
            "(placeholders: {hasta_adi} {rapor_listesi} {eczane_adi} {eczane_tel})"
        )
        self.var_rb_uyari = tk.IntVar(value=self.ayarlar.rapor_bitis_uyari_gun)
        uy = tk.Frame(g7, bg="white")
        uy.pack(fill="x")
        tk.Label(uy, text="Varsayılan 'bitişe kalan gün':", bg="white").pack(side="left")
        tk.Spinbox(uy, from_=0, to=365, width=5, textvariable=self.var_rb_uyari).pack(side="left", padx=4)

        tk.Label(g7, text="Mesaj şablonu:", bg="white").pack(anchor="w", pady=(6, 2))
        self.txt_rb_sablon = tk.Text(g7, height=6, font=("Consolas", 10))
        self.txt_rb_sablon.pack(fill="x")
        self.txt_rb_sablon.insert("1.0", self.ayarlar.rapor_bitis_mesaj_sablonu)

        tk.Label(
            g7,
            text="Her tanı satırı formatı (placeholders: {rapor_kodu} {rapor_kod_aciklama} "
                 "{icd_kodu} {icd_aciklamasi} {baslama} {bitis} {kalan_gun} "
                 "{etkin_maddeler} {ilaclar}):",
            bg="white", fg="#607D8B", font=("Arial", 8), wraplength=700, justify="left",
        ).pack(anchor="w", pady=(8, 2))
        self.txt_rb_tani_sablon = tk.Text(g7, height=6, font=("Consolas", 10))
        self.txt_rb_tani_sablon.pack(fill="x")
        self.txt_rb_tani_sablon.insert("1.0", self.ayarlar.rapor_bitis_tani_satir_formati)

        # Kaydet
        tk.Button(
            icerik, text="💾 Ayarları Kaydet", command=self._ayarlari_kaydet,
            bg="#1976D2", fg="white", bd=0, padx=20, pady=10,
            font=("Arial", 11, "bold"),
        ).pack(pady=16)

        return f

    # ================================================================= SEKME RAPOR BITIS
    def _sekme_rapor_bitis_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")

        # Üst filtre satırı
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="Bitişe kalan (gün):", bg="white").pack(side="left")
        self.var_rb_gun = tk.IntVar(value=self.ayarlar.rapor_bitis_uyari_gun)
        tk.Spinbox(top, from_=0, to=365, width=5, textvariable=self.var_rb_gun).pack(side="left", padx=4)

        tk.Label(top, text="   Geçmişten geri (gün):", bg="white").pack(side="left", padx=(10, 0))
        self.var_rb_geri = tk.IntVar(value=0)
        tk.Spinbox(top, from_=0, to=90, width=5, textvariable=self.var_rb_geri).pack(side="left", padx=4)

        self.var_rb_takipli = tk.BooleanVar(value=False)
        self.var_rb_telefonlu = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Sadece takipli", variable=self.var_rb_takipli, bg="white").pack(side="left", padx=(10, 0))
        tk.Checkbutton(top, text="Sadece telefonu olanlar", variable=self.var_rb_telefonlu, bg="white").pack(side="left", padx=(6, 0))

        tk.Button(
            top, text="🔄 Listele", command=self._rapor_bitis_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left", padx=10)

        self.lbl_rb_sayac = tk.Label(top, text="", bg="white", fg="#455A64")
        self.lbl_rb_sayac.pack(side="left", padx=8)

        # Ana bölmesi: sol hasta listesi, sağ detay + mesaj
        bol = tk.PanedWindow(f, orient="horizontal", sashrelief="raised", bg="white")
        bol.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sol = tk.Frame(bol, bg="white")
        bol.add(sol, minsize=430)

        kols = ("hasta", "tc", "tel", "tani_sayi", "en_yakin", "kalan", "takip")
        self.tv_rb = ttk.Treeview(sol, columns=kols, show="headings", selectmode="browse")
        for k, b, w, a in [
            ("hasta", "Hasta", 190, "w"),
            ("tc", "T.C.", 95, "center"),
            ("tel", "Telefon", 95, "center"),
            ("tani_sayi", "Tanı", 45, "center"),
            ("en_yakin", "En Yakın Bitiş", 100, "center"),
            ("kalan", "Kalan", 55, "center"),
            ("takip", "Takipli", 55, "center"),
        ]:
            self.tv_rb.heading(k, text=b)
            self.tv_rb.column(k, width=w, anchor=a)
        self.tv_rb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sol, orient="vertical", command=self.tv_rb.yview)
        self.tv_rb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_rb.bind("<<TreeviewSelect>>", lambda e: self._rapor_bitis_detay())

        # Sağ: üstte detay tabloları, altta mesaj önizleme + WA gönder
        sag = tk.Frame(bol, bg="#FAFAFA")
        bol.add(sag, minsize=680)

        self.lbl_rb_hasta = tk.Label(
            sag, text="◀ Soldan bir hasta seçin",
            bg="#FAFAFA", fg="#607D8B",
            font=("Arial", 11, "bold"), anchor="w",
        )
        self.lbl_rb_hasta.pack(fill="x", padx=10, pady=(8, 4))

        # Tanı tablosu
        tk.Label(
            sag, text="Tanı / ICD / Bitiş Tarihleri", bg="#FAFAFA",
            fg="#1976D2", font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(4, 2))
        self.tv_rb_tani = ttk.Treeview(
            sag, columns=("kod", "aciklama", "icd", "icd_ad", "bas", "bit", "kalan"),
            show="headings", height=6,
        )
        for k, b, w in [
            ("kod", "Kod", 70), ("aciklama", "Tanı Açıklama", 200),
            ("icd", "ICD", 70), ("icd_ad", "ICD Açıklama", 200),
            ("bas", "Başlama", 90), ("bit", "Bitiş", 90), ("kalan", "Kalan", 55),
        ]:
            self.tv_rb_tani.heading(k, text=b)
            self.tv_rb_tani.column(k, width=w)
        self.tv_rb_tani.pack(fill="x", padx=10)

        # Etken maddeler + İlaçlar (yan yana)
        alt = tk.Frame(sag, bg="#FAFAFA")
        alt.pack(fill="x", padx=10, pady=(6, 0))

        em_frame = tk.Frame(alt, bg="#FAFAFA")
        em_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(em_frame, text="Etken Maddeler → Kullandığı İlaç", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tv_rb_em = ttk.Treeview(em_frame, columns=("em", "sgk", "doz", "hasta_ilac"), show="headings", height=4)
        self.tv_rb_em.heading("em", text="Etken Madde")
        self.tv_rb_em.heading("sgk", text="SGK")
        self.tv_rb_em.heading("doz", text="Doz")
        self.tv_rb_em.heading("hasta_ilac", text="Hasta İlacı")
        self.tv_rb_em.column("em", width=150)
        self.tv_rb_em.column("sgk", width=70, anchor="center")
        self.tv_rb_em.column("doz", width=55, anchor="center")
        self.tv_rb_em.column("hasta_ilac", width=220)
        self.tv_rb_em.pack(fill="both", expand=True)

        il_frame = tk.Frame(alt, bg="#FAFAFA")
        il_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(il_frame, text="Kullanılan İlaçlar", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tv_rb_il = ttk.Treeview(il_frame, columns=("ilac", "bitis", "tarih"), show="headings", height=4)
        self.tv_rb_il.heading("ilac", text="İlaç")
        self.tv_rb_il.heading("bitis", text="Bitiş")
        self.tv_rb_il.heading("tarih", text="Reçete Tarihi")
        self.tv_rb_il.column("ilac", width=220)
        self.tv_rb_il.column("bitis", width=80, anchor="center")
        self.tv_rb_il.column("tarih", width=90, anchor="center")
        self.tv_rb_il.pack(fill="both", expand=True)

        # Mesaj önizleme
        tk.Label(sag, text="Mesaj Önizleme", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.txt_rb_mesaj = tk.Text(sag, wrap="word", font=("Consolas", 10), height=14, bg="white", relief="solid", bd=1)
        self.txt_rb_mesaj.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        btn_frame = tk.Frame(sag, bg="#FAFAFA")
        btn_frame.pack(fill="x", padx=10, pady=8)
        tk.Button(
            btn_frame, text="📱 WhatsApp Web'de Aç", command=self._rb_wa_ac,
            bg="#25D366", fg="white", bd=0, padx=16, pady=8, font=("Arial", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            btn_frame, text="📋 Panoya Kopyala", command=self._rb_panoya,
            bg="#546E7A", fg="white", bd=0, padx=12, pady=8,
        ).pack(side="left", padx=8)

        self._rb_sonuc: list = []     # ham tanı satırları
        self._rb_hasta_map: dict = {} # musteri_id -> tanı satırları
        return f

    # ================================================================= SEKME LOG
    ISARET_SECENEK = [
        "", "✅ Gönderildi", "📞 Yanıt Geldi", "🧍 Geldi",
        "❌ Gelmedi", "🔁 Tekrar Dene", "🛒 Başka Yerden Aldı",
    ]

    def _sekme_log_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(
            top, text="🔄 Yenile", command=self._log_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left")

        tk.Label(top, text="  Dönem:", bg="white").pack(side="left", padx=(10, 2))
        self.var_log_filtre = tk.StringVar(value="hepsi")
        for etik, deger in [("Bugün", "bugun"), ("Hafta", "hafta"), ("Ay", "ay"), ("Hepsi", "hepsi")]:
            tk.Radiobutton(
                top, text=etik, value=deger, variable=self.var_log_filtre,
                bg="white", command=self._log_yukle,
            ).pack(side="left")

        tk.Button(
            top, text="📤 Excel Aktar", command=self._log_excel_aktar,
            bg="#2E7D32", fg="white", bd=0, padx=12, pady=6,
        ).pack(side="left", padx=(10, 0))

        self.lbl_log_sayac = tk.Label(top, text="", bg="white", fg="#455A64", font=("Arial", 9, "bold"))
        self.lbl_log_sayac.pack(side="left", padx=12)

        tk.Label(
            top, text="Sağ tıkla → işaret / not düş",
            bg="white", fg="#607D8B", font=("Arial", 9, "italic"),
        ).pack(side="right", padx=12)

        # Üst: tablo, alt: mesaj önizleme — dikey bölme
        bol_log = tk.PanedWindow(
            f, orient="vertical", sashrelief="raised",
            bg="#CFD8DC", sashwidth=6,
        )
        bol_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ust_log = tk.Frame(bol_log, bg="white")
        bol_log.add(ust_log, minsize=180, stretch="always")

        kols = ("zaman", "hasta", "tel", "isaret", "not", "sonuc")
        self.tv_log = ttk.Treeview(
            ust_log, columns=kols, show="headings", selectmode="browse",
        )
        for k, b, w in [
            ("zaman", "Zaman", 150),
            ("hasta", "Hasta", 220),
            ("tel", "Telefon", 110),
            ("isaret", "İşaret", 140),
            ("not", "Not", 240),
            ("sonuc", "Sonuç", 80),
        ]:
            self.tv_log.heading(k, text=b)
            self.tv_log.column(k, width=w, anchor="w")
        self.tv_log.pack(fill="both", expand=True)

        # Alt: atılan mesaj önizleme
        alt_log = tk.Frame(bol_log, bg="#ECEFF1")
        bol_log.add(alt_log, minsize=100, stretch="never")
        tk.Label(
            alt_log, text="📄 Atılan mesaj içeriği",
            bg="#ECEFF1", fg="#455A64", font=("Arial", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=4, pady=(2, 0))
        self.txt_log_mesaj = tk.Text(
            alt_log, height=8, wrap="word", bg="#FAFAFA",
            font=("Consolas", 9),
        )
        self.txt_log_mesaj.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.txt_log_mesaj.insert("1.0", "(Bir kayıt seçin — mesaj içeriği burada görünecek.)")

        # Sağ tık menüsü
        self.menu_log = tk.Menu(self.tv_log, tearoff=0)
        for isaret in self.ISARET_SECENEK:
            etiket = f"  İşaret: {isaret}" if isaret else "  İşareti Temizle"
            self.menu_log.add_command(
                label=etiket,
                command=lambda i=isaret: self._log_isaret(i),
            )
        self.menu_log.add_separator()
        self.menu_log.add_command(label="📝 Not Düş / Düzenle...", command=self._log_not)
        self.tv_log.bind("<Button-3>", self._log_sagtik)
        self.tv_log.bind("<Double-1>", lambda e: self._log_not())
        self.tv_log.bind("<<TreeviewSelect>>", lambda e: self._log_mesaj_onizleme())
        return f

    # -----------------------------------------------------------------
    # Sürec göstergesi (progress bar + spinner)
    # -----------------------------------------------------------------
    def _progress_baslat(self, metin: str = "İşleniyor..."):
        """İndeterminate progress bar'ı başlat ve durum barında spinner göster."""
        try:
            self.durum_progress.start(80)
        except Exception:
            pass
        self._spinner_metin = metin
        self._spinner_idx = 0
        self._spinner_tik()

    def _spinner_tik(self):
        try:
            kare = self._spinner_kareler[self._spinner_idx % len(self._spinner_kareler)]
            self.durum_bar.config(text=f"{kare} {self._spinner_metin}")
            self._spinner_idx += 1
            self._spinner_after_id = self.root.after(500, self._spinner_tik)
        except Exception:
            self._spinner_after_id = None

    def _progress_durdur(self, metin: str = "Hazır"):
        """Progress bar'ı durdur ve durum metnini güncelle."""
        try:
            if self._spinner_after_id is not None:
                self.root.after_cancel(self._spinner_after_id)
                self._spinner_after_id = None
        except Exception:
            pass
        try:
            self.durum_progress.stop()
        except Exception:
            pass
        self.durum_bar.config(text=metin)

    # -----------------------------------------------------------------
    # Sekme 1 davranışları
    # -----------------------------------------------------------------
    def _yazdirma_yenile(self):
        """DB'yi sorgula → kuyruğa upsert → ekrandaki listeyi güncelle."""
        if self._yazdirma_calisiyor:
            logger.info("Yazdırma yenileme zaten çalışıyor, yeni istek yok sayıldı.")
            return
        self._yazdirma_calisiyor = True
        self._progress_baslat("DB sorgulanıyor...")
        self.root.update_idletasks()

        def _calis():
            try:
                if self.db is None:
                    self.db = HastaTakipDB()
                # Güncel ayarları çek (kaydedilmemiş olsa bile radio'dan)
                a = self._ayarlar_snapshot()
                # Batch penceresi kadar ileriye bakmak için tarama toleransını genişlet
                batch_gun = max(0, getattr(a, "batch_bekleme_gun", 0) or 0)
                tolerans = max(a.hafta_sonu_tolerans_gun, batch_gun)
                sonuc = self.db.yazdirma_gunu_gelen_ilaclar(
                    tolerans_gun=tolerans,
                    rapor_tolerans_gun=a.rapor_yazdirma_tolerans_gun,
                    sadece_takipli=a.sadece_takipli,
                    eski_kayit_gun=a.eski_kayit_gun,
                    kaynak=a.kaynak,
                    sadece_raporlu=getattr(a, "sadece_raporlu", True),
                    raporsuz_istisna_urunler=getattr(a, "raporsuz_istisna_urunler", []),
                    kategori_takibi=getattr(a, "kategori_takibi", {}),
                    kategori_ozel_anahtarlar=getattr(a, "kategori_ozel_anahtarlar", ""),
                    haber_verilenleri_gizle=getattr(a, "haber_verilenleri_gizle", False),
                )
                yeni = self.kuyruk.hasta_mesajlarini_upsert(sonuc, a)
                self.root.after(0, lambda: self._yazdirma_tamam(len(sonuc), yeni))
            except Exception as e:
                logger.exception("yazdirma_yenile hatası")
                self.root.after(0, lambda: self._progress_durdur("❌ Hata"))
                self.root.after(0, lambda: messagebox.showerror("Hata", str(e)))
            finally:
                self.root.after(0, lambda: setattr(self, "_yazdirma_calisiyor", False))

        threading.Thread(target=_calis, daemon=True).start()

    def _yazdirma_tamam(self, ilac_sayi: int, yeni_hasta: int):
        self._kuyruktan_yukle()
        gosterilen = len(self._kuyruk_sonuclari)
        self._progress_durdur(
            f"✅ DB tarandı: {ilac_sayi} ilaç | {yeni_hasta} yeni hasta kuyruğa eklendi | "
            f"Ekranda gösterilen: {gosterilen}"
        )
        if gosterilen == 0 and ilac_sayi > 0:
            messagebox.showinfo(
                "Liste Boş Görünüyor",
                f"Veritabanından {ilac_sayi} ilaç eşleşti ve kuyruğa yazıldı,\n"
                f"ancak ekranda gösterilmiyor.\n\n"
                f"Nedeni büyük ihtimalle ÇALIŞMA SAATİ ayarınızdır:\n"
                f"   {self.ayarlar.calisma_baslangic} - {self.ayarlar.calisma_bitis}\n\n"
                f"Ayarlar sekmesinden çalışma saatlerini genişletip 'Kaydet' yapın,\n"
                f"sonra yeniden 'Listeyi Yenile' deyin."
            )

    def _kuyruktan_yukle(self):
        for i in self.tv_yaz.get_children():
            self.tv_yaz.delete(i)
        a = self._ayarlar_snapshot()
        self._kuyruk_sonuclari = self.kuyruk.gosterilecek_mesajlar(a)

        # Yerel haber filtresi: yerel log'da kaydı olan (hasta, ilaç, bitiş)
        # üçlülerini düş. Yeni reçete → yeni bitiş → log eşleşmez → tekrar görünür.
        if getattr(a, "haber_verilenleri_gizle_yerel", False) and self._kuyruk_sonuclari:
            haber_seti = self.kuyruk.yerel_haber_verilenler_seti()
            if haber_seti:
                temiz: list = []
                for m in self._kuyruk_sonuclari:
                    mid = int(m.get("musteri_id") or 0)
                    kalan_ilac = []
                    for il in m.get("ilaclar", []) or []:
                        urun = (il.get("urun_adi") or "").strip().upper()
                        bitis = str(il.get("bitis_tarihi") or "")[:10]
                        if (mid, urun, bitis) in haber_seti:
                            continue
                        kalan_ilac.append(il)
                    if kalan_ilac:
                        m["ilaclar"] = kalan_ilac
                        temiz.append(m)
                self._kuyruk_sonuclari = temiz

        # eski_kayit_gun filtresi: kuyrukta önceden yazılmış ama artık
        # bitişi çok gerilere kaymış ilaçları gizle. DB sorgusu bu filtreyi
        # zaten uygular; ancak kullanıcı ayarı küçülttüğünde eski kuyruk
        # kayıtları upsert edilmediği için görünmeye devam eder.
        eski_gun = int(getattr(a, "eski_kayit_gun", 30) or 30)
        if eski_gun >= 0 and self._kuyruk_sonuclari:
            esik_str = (date.today() - timedelta(days=eski_gun)).isoformat()
            temiz = []
            for m in self._kuyruk_sonuclari:
                ilaclar = m.get("ilaclar", []) or []
                filtreli = [
                    il for il in ilaclar
                    if str(il.get("bitis_tarihi") or "")[:10] >= esik_str
                ]
                if filtreli:
                    m["ilaclar"] = filtreli
                    temiz.append(m)
            self._kuyruk_sonuclari = temiz

        # Tarih aralığı filtresi (üç aşamalı):
        #   Kayıt aralıkta SAYILIR eğer
        #     (a) planli_gonderim aralıktaysa VEYA
        #     (b) kayıt içindeki HERHANGİ bir ilacın yazdırma tarihi aralıktaysa
        # (b) çok önemli: bir kaydın ilaçları çok eskiden bugüne dağılmış
        # olabilir. en_erken çok eskide, en_geç çok ileride olabilir — ama
        # aralarında aralıkta kalan ilaç(lar) olabilir. Bu durumda kayıt
        # listede görünmeli ki eczacı farkedebilsin.
        bas_str, bit_str = self._filtre_aralik_iso()
        if bas_str or bit_str:
            filtrelenmis = []
            for m in self._kuyruk_sonuclari:
                p = (m.get("planli_gonderim") or "")[:10]
                yazdirma_tarihleri = []
                for il in m.get("ilaclar", []) or []:
                    yt = str(il.get("yazdirma_tarihi") or "")[:10]
                    if yt:
                        yazdirma_tarihleri.append(yt)

                def aralikta(ts: str) -> bool:
                    if not ts:
                        return False
                    if bas_str and ts < bas_str:
                        return False
                    if bit_str and ts > bit_str:
                        return False
                    return True

                herhangi = any(aralikta(t) for t in yazdirma_tarihleri)
                if aralikta(p) or herhangi:
                    filtrelenmis.append(m)
            self._kuyruk_sonuclari = filtrelenmis
            if hasattr(self, "_filt_durum_lbl"):
                parca = []
                if bas_str:
                    parca.append(f"≥ {bas_str}")
                if bit_str:
                    parca.append(f"≤ {bit_str}")
                self._filt_durum_lbl.config(
                    text=f"Filtre: {' ve '.join(parca)} (planlı ya da en erken ilaç)"
                )
        elif hasattr(self, "_filt_durum_lbl"):
            self._filt_durum_lbl.config(text="")

        # Ertelenen satırlar için sarı arka plan — ttk.Treeview teması bazı
        # platformlarda tag background'ı bastırır, bu yüzden stili zorluyoruz.
        try:
            style = ttk.Style()
            style.map(
                "Treeview",
                background=[("selected", "#1976D2")],
                foreground=[("selected", "white")],
            )
        except Exception:
            pass
        self.tv_yaz.tag_configure("ertelenen", background="#FFEB3B", foreground="#000000")
        # Açık sarı: bekleteni indirilmiş (yolcu indirilen otobüs)
        self.tv_yaz.tag_configure("indirildi", background="#FFF9C4", foreground="#000000")
        # Açık yeşil: mesaj gönderilmiş
        self.tv_yaz.tag_configure("gonderildi", background="#C8E6C9", foreground="#000000")
        # Mavi ton: ilacını aldı (mesaj atılmadan hasta geldi)
        self.tv_yaz.tag_configure("ilac_alindi", background="#BBDEFB", foreground="#000000")

        bugun = date.today()
        bugun_iso = bugun.isoformat()
        # Menzil = X gün içindeki kalem sayısı (batch pencere)
        batch_gun = int(getattr(self.ayarlar, "batch_bekleme_gun", 5) or 0)
        menzil_son = (bugun + timedelta(days=batch_gun)).isoformat()
        GUN_ADI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        for m in self._kuyruk_sonuclari:
            indirildi = bool(m.get("bekleteni_indirildi"))
            ertelenen = bool(m.get("ertelenen"))
            gonderildi = m.get("durum") == "gonderildi"
            if gonderildi:
                tags = ("gonderildi",)
            elif indirildi:
                tags = ("indirildi",)
            elif ertelenen:
                tags = ("ertelenen",)
            else:
                tags = ()
            # Menzil sayısı
            menzil_sayisi = 0
            for il in m.get("ilaclar", []) or []:
                yt = str(il.get("yazdirma_tarihi") or "")[:10]
                if yt and bugun_iso <= yt <= menzil_son:
                    menzil_sayisi += 1

            planli_iso = (m.get("planli_gonderim") or "")[:10]
            planli_goster = "-"
            if planli_iso:
                try:
                    p = datetime.strptime(planli_iso, "%Y-%m-%d").date()
                    fark = (p - bugun).days
                    gun_ad = GUN_ADI[p.weekday()]
                    tarih_str = p.strftime("%d.%m.%Y")
                    if fark > 0:
                        planli_goster = f"{tarih_str} {gun_ad} (+{fark})"
                    elif fark == 0:
                        planli_goster = f"{tarih_str} (Bugün)"
                    else:
                        planli_goster = f"{tarih_str} ({fark})"
                except ValueError:
                    planli_goster = planli_iso
            self.tv_yaz.insert(
                "", "end", iid=str(m["kuyruk_id"]),
                values=(
                    planli_goster,
                    m["hasta_adi"],
                    m.get("tckn") or "-",
                    m["cep_tel"] or "-",
                    len(m["ilaclar"]),
                    menzil_sayisi,
                    m.get("toplam_ziyaret") if m.get("toplam_ziyaret") is not None else "-",
                    (m.get("son_ziyaret") or "")[:10] or "-",
                    m.get("son_gun_once") if m.get("son_gun_once") is not None else "-",
                    "Evet" if m.get("takipli") else "Hayır",
                ),
                tags=tags,
            )
        bekleyen = self.kuyruk.kuyrukta_bekleyen_sayisi()
        gosterilen = len(self._kuyruk_sonuclari)
        self.lbl_sayac.config(
            text=f"Kuyruktaki gösterilecek: {gosterilen}   |   "
                 f"Toplam bekleyen: {bekleyen}",
        )
        self.txt_mesaj.delete("1.0", "end")

        # Kullanıcıya neden boş olduğunu açıkla
        if gosterilen == 0 and bekleyen > 0:
            simdi = datetime.now().strftime("%H:%M")
            self.txt_mesaj.insert(
                "1.0",
                f"⚠ Kuyrukta {bekleyen} bekleyen kayıt var ama liste boş görünüyor.\n\n"
                f"OLASI NEDENLER:\n\n"
                f"1) ÇALIŞMA SAATİ DIŞINDASINIZ\n"
                f"   Şu an: {simdi}\n"
                f"   Ayarlar: {self.ayarlar.calisma_baslangic} - {self.ayarlar.calisma_bitis}\n"
                f"   → Ayarlar sekmesinden saatleri değiştirip 'Kaydet'e basın\n"
                f"     (ör. 00:00 - 23:59 yaparsanız her zaman görünür)\n\n"
                f"2) PLANLI GÖNDERİM İLERİDE\n"
                f"   Eğer 'Pazartesi birleşik' veya 'Periyodik' modundaysanız,\n"
                f"   kayıtlar o güne planlanmış olabilir.\n"
                f"   → Ayarlar sekmesinde 'Anlık' moduna geçin.",
            )
        elif gosterilen == 0 and bekleyen == 0:
            self.txt_mesaj.insert(
                "1.0",
                "Kuyrukta hiç kayıt yok.\n\n"
                "➤ Yukarıdaki '🔄 Listeyi Yenile (DB)' butonuna basarak\n"
                "  Botanik veritabanını tarayın."
            )

    def _secim_guncelle(self):
        sec = self.tv_yaz.selection()
        if not sec:
            return
        kid = int(sec[0])
        m = next((x for x in self._kuyruk_sonuclari if x["kuyruk_id"] == kid), None)
        if not m:
            return
        metin = m["mesaj_metni"]
        self._son_birlesik_mi = False
        # Birleşik mesaj ayarı açıksa rapor bilgisini ekle
        if getattr(self.ayarlar, "ilac_rapor_birlesik", False):
            try:
                if self.db is None:
                    self.db = HastaTakipDB()
                metin, birlesti = MesajKuyrugu.ilac_mesajina_rapor_ek(
                    metin, m.get("musteri_id"), m.get("hasta_adi") or "",
                    self.db, self.ayarlar,
                )
                self._son_birlesik_mi = bool(birlesti)
            except Exception as e:
                logger.warning("İlaç+Rapor birleşik mesaj hatası: %s", e)
        self.txt_mesaj.delete("1.0", "end")
        self.txt_mesaj.insert("1.0", metin)

    def _aktif_mesaj(self):
        sec = self.tv_yaz.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Lütfen bir hasta seçin.")
            return None
        kid = int(sec[0])
        return next((x for x in self._kuyruk_sonuclari if x["kuyruk_id"] == kid), None)

    @staticmethod
    def _chrome_yolu_bul() -> Optional[str]:
        """Chrome exe'nin yolunu bul — bulunamazsa None."""
        olasi = [
            shutil.which("chrome"),
            shutil.which("chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for y in olasi:
            if y and os.path.isfile(y):
                return y
        return None

    @classmethod
    def _chrome_ile_ac(cls, url: str) -> bool:
        """Verilen URL'yi Chrome'da açmayı dener.

        Sıra: webbrowser.get('chrome') → doğrudan chrome.exe çağrısı →
        varsayılan tarayıcıya düş. Başarılı olduysa True, default'a düştüyse False.
        """
        # 1) webbrowser modülü üzerinden
        try:
            b = webbrowser.get("chrome")
            if b.open(url):
                return True
        except Exception:
            pass
        # 2) Doğrudan exe
        yol = cls._chrome_yolu_bul()
        if yol:
            try:
                subprocess.Popen([yol, url])
                return True
            except Exception as e:
                logger.warning("Chrome exe çağrısı başarısız: %s", e)
        # 3) Fallback
        webbrowser.open(url)
        return False

    def _wa_ac(self):
        m = self._aktif_mesaj()
        if not m:
            return
        tel = (m["cep_tel"] or "").strip()
        if not tel or len(tel) < 10:
            messagebox.showwarning("Telefon Yok", f"{m['hasta_adi']} için cep telefonu tanımlı değil.")
            return
        if tel.startswith("+"):
            tel = tel[1:]
        if tel.startswith("0"):
            tel = "90" + tel[1:]
        if not tel.startswith("90"):
            tel = "90" + tel

        mesaj_onizleme = self.txt_mesaj.get("1.0", "end").rstrip("\n")
        # Hastaya giden metinden eczacı-özel gün etiketlerini temizle
        mesaj_metni = MesajKuyrugu.gun_etiketlerini_temizle(mesaj_onizleme)
        url = f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj_metni)}"

        kid = m["kuyruk_id"]
        # Anlık görsel geri bildirim — satırı hemen yeşile boya
        try:
            self.tv_yaz.item(str(kid), tags=("gonderildi",))
            self.root.update_idletasks()
        except Exception:
            pass

        chrome_acildi = self._chrome_ile_ac(url)
        isaret = "💊+📑 İlaç & Rapor" if getattr(self, "_son_birlesik_mi", False) else "💊 İlaç"
        try:
            self.kuyruk.gonderildi_isaretle(
                kid, "MESAJ GONDERILDI", manuel=True, isaret=isaret,
            )
        except Exception as e:
            logger.exception("gonderildi_isaretle hatası")
            messagebox.showerror("Hata", f"Kayıt işaretlenemedi: {e}")
            return
        self._kuyruktan_yukle()
        ek = "" if chrome_acildi else " (Chrome bulunamadı — varsayılan tarayıcı açıldı)"
        self.durum_bar.config(
            text=f"✅ {m['hasta_adi']} için WhatsApp açıldı, mesaj gönderildi olarak işaretlendi.{ek}"
        )

    def _farkli_kisiye_gonder(self):
        """Seçili hastanın mesajını başka bir kişiye gönder.

        Musteri tablosundan isim/TC ile arama yapılır, seçilen kişinin
        telefonuyla WhatsApp açılır. Orijinal kuyruk kaydı değişmez —
        asıl hasta bekliyor olarak kalır, kullanıcı ona ayrıca karar verir.
        """
        m = self._aktif_mesaj()
        if not m:
            return
        mesaj_onizleme = self.txt_mesaj.get("1.0", "end").rstrip("\n")
        mesaj_metni = MesajKuyrugu.gun_etiketlerini_temizle(mesaj_onizleme)
        if not mesaj_metni.strip():
            messagebox.showwarning("Mesaj Yok", "Gönderilecek mesaj boş.")
            return

        pencere = tk.Toplevel(self.root)
        pencere.title("👤 Farklı Kişiye Gönder")
        pencere.geometry("640x420")
        pencere.transient(self.root)
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(pencere)
        except Exception:
            pass

        ust = tk.Frame(pencere, bg="white")
        ust.pack(fill="x", padx=10, pady=10)
        tk.Label(
            ust, text=f"Asıl alıcı: {m['hasta_adi']} ({m.get('cep_tel','-')})",
            bg="white", fg="#455A64", font=("Arial", 9, "italic"),
        ).pack(anchor="w")
        tk.Label(
            ust, text="İsim / TC ile ara:", bg="white",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(6, 2))

        satir = tk.Frame(ust, bg="white")
        satir.pack(fill="x")
        var_arama = tk.StringVar()
        ent = tk.Entry(satir, textvariable=var_arama, font=("Arial", 11))
        ent.pack(side="left", fill="x", expand=True)
        ent.focus_set()

        kols = ("ad", "tc", "tel", "takipli")
        tv = ttk.Treeview(pencere, columns=kols, show="headings", selectmode="browse")
        for k, b, w in [
            ("ad", "Hasta Adı", 260),
            ("tc", "T.C.", 110),
            ("tel", "Telefon", 120),
            ("takipli", "Takipli", 70),
        ]:
            tv.heading(k, text=b)
            tv.column(k, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=(4, 4))

        durum_lbl = tk.Label(
            pencere, text="", bg=pencere.cget("bg"),
            fg="#607D8B", font=("Arial", 9, "italic"),
        )
        durum_lbl.pack(anchor="w", padx=10)

        def _ara():
            q = (var_arama.get() or "").strip()
            if len(q) < 2:
                durum_lbl.config(text="En az 2 karakter girin.")
                return
            for i in tv.get_children():
                tv.delete(i)
            try:
                from botanik_db import BotanikDB
                db = BotanikDB()
                if not db.baglan():
                    durum_lbl.config(text="❌ Botanik DB bağlanamadı.")
                    return
                # TC ise direkt eşle, değilse ad LIKE
                if q.isdigit() and len(q) >= 3:
                    sql = ("SELECT TOP 200 MusteriId, MusteriAdiSoyadi, "
                           "MusteriTCKN, MusteriTelCep, MusteriTakipli "
                           "FROM Musteri WHERE MusteriTCKN LIKE ? "
                           "ORDER BY MusteriAdiSoyadi")
                    params = (f"%{q}%",)
                else:
                    sql = ("SELECT TOP 200 MusteriId, MusteriAdiSoyadi, "
                           "MusteriTCKN, MusteriTelCep, MusteriTakipli "
                           "FROM Musteri WHERE MusteriAdiSoyadi LIKE ? "
                           "ORDER BY MusteriAdiSoyadi")
                    params = (f"%{q}%",)
                sonuc = db.sorgu_calistir(sql, params)
                db.kapat()
            except Exception as e:
                durum_lbl.config(text=f"Hata: {e}")
                return
            for r in sonuc:
                tv.insert("", "end", iid=str(r["MusteriId"]), values=(
                    (r.get("MusteriAdiSoyadi") or "").strip(),
                    (r.get("MusteriTCKN") or "").strip() or "-",
                    (r.get("MusteriTelCep") or "").strip() or "-",
                    "Evet" if r.get("MusteriTakipli") else "Hayır",
                ))
            durum_lbl.config(text=f"{len(sonuc)} kişi bulundu.")

        tk.Button(
            satir, text="🔍 Ara", command=_ara,
            bg="#1976D2", fg="white", bd=0, padx=12, pady=4,
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(6, 0))
        ent.bind("<Return>", lambda e: _ara())

        def _gonder():
            sec = tv.selection()
            if not sec:
                messagebox.showwarning("Seçim Yok", "Bir kişi seçin.", parent=pencere)
                return
            vals = tv.item(sec[0], "values")
            ad, tc, tel, _ = vals
            tel = (tel or "").strip()
            if not tel or tel == "-" or len(tel) < 10:
                messagebox.showwarning(
                    "Telefon Yok", f"{ad} için cep telefonu tanımlı değil.",
                    parent=pencere,
                )
                return
            if tel.startswith("+"):
                tel = tel[1:]
            if tel.startswith("0"):
                tel = "90" + tel[1:]
            if not tel.startswith("90"):
                tel = "90" + tel
            url = f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj_metni)}"
            self._chrome_ile_ac(url)
            self.durum_bar.config(
                text=f"✅ {m['hasta_adi']} mesajı farklı kişiye gönderildi: {ad}"
            )
            pencere.destroy()

        alt = tk.Frame(pencere)
        alt.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            alt, text="📱 Seçilene WhatsApp'ta Gönder", command=_gonder,
            bg="#25D366", fg="white", bd=0, padx=14, pady=6,
            font=("Arial", 10, "bold"),
        ).pack(side="right")
        tk.Button(
            alt, text="İptal", command=pencere.destroy,
            bg="#9E9E9E", fg="white", bd=0, padx=12, pady=6,
        ).pack(side="right", padx=(0, 6))

        tv.bind("<Double-1>", lambda e: _gonder())

    def _panoya_kopyala(self):
        mesaj_onizleme = self.txt_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj_onizleme:
            return
        # Hastaya giden metinden gün etiketlerini temizle
        mesaj = MesajKuyrugu.gun_etiketlerini_temizle(mesaj_onizleme)
        self.root.clipboard_clear()
        self.root.clipboard_append(mesaj)
        self.durum_bar.config(text="📋 Mesaj panoya kopyalandı (gün etiketleri çıkarıldı).")

    def _kopyala_yardimci(self, alan: str, etiket: str):
        m = self._aktif_mesaj()
        if not m:
            return
        deger = (m.get(alan) or "").strip()
        if not deger:
            self.durum_bar.config(text=f"⚠ {etiket} yok.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(deger)
        self.durum_bar.config(text=f"📋 {etiket} panoya kopyalandı: {deger}")

    def _tc_kopyala(self, *_):
        self._kopyala_yardimci("tckn", "T.C. Kimlik No")

    def _tel_kopyala(self, *_):
        self._kopyala_yardimci("cep_tel", "Telefon")

    def _ad_kopyala(self, *_):
        self._kopyala_yardimci("hasta_adi", "Hasta adı")

    def _yaz_sagtik(self, event):
        rid = self.tv_yaz.identify_row(event.y)
        if not rid:
            return
        self.tv_yaz.selection_set(rid)
        try:
            self.menu_yaz.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_yaz.grab_release()

    def _medulada_ilac_listesi_ac(self):
        """Seçili hastanın TC'si → pano → MEDULA f:t18 (temizle+yapıştır) →
        f:buttonIlacListesi tıkla. Mümkün olan en hızlı akış.

        Adımlar:
          1. Seçili hastanın TC'sini panoya koy
          2. MEDULA penceresini öne getir
          3. f:t18 Reçete Sahibi TC textbox'ına odaklan
          4. Ctrl+A → Del (temizle) → Ctrl+V (panodan yapıştır)
          5. f:buttonIlacListesi butonuna invoke()

        NOT: Veri değiştirmez; sadece sorgu/navigasyon.
        """
        m = self._aktif_mesaj()
        if not m:
            return
        tc = (m.get("tckn") or "").strip()
        if len(tc) != 11 or not tc.isdigit():
            messagebox.showwarning("Geçersiz TC", f"Hastanın TC'si geçersiz: '{tc}'")
            return

        # 1) Panoya kopyala (ana thread'de)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(tc)
            self.root.update()  # pano senkron
        except Exception as e:
            logger.warning(f"Panoya yazılamadı: {e}")

        self.durum_bar.config(text=f"⏳ MEDULA'da {tc} sorgulanıyor...")
        self.root.update_idletasks()

        # TEK YOL: HTML DOM (COM). Başarısızlık durumunda fallback (pywinauto
        # + Ctrl+A) YAPILMAZ — çünkü o akış "tüm sayfayı seçme" davranışı
        # gösterebilir ve kullanıcının istediği 5-adım akışı uygulamaz.
        try:
            from medula_html_dom import tc_yaz_ve_ilac_listesi_ac
            ok, msg = tc_yaz_ve_ilac_listesi_ac(tc)
            if ok:
                self.durum_bar.config(
                    text=f"💊 {m.get('hasta_adi')} ({tc}) — {msg}"
                )
            else:
                logger.warning(f"HTML DOM başarısız: {msg}")
                self.durum_bar.config(text=f"⚠ {msg[:160]}")
            return
        except Exception as e:
            logger.warning(f"HTML DOM istisna: {e}", exc_info=True)
            self.durum_bar.config(text=f"⚠ {type(e).__name__}: {e}"[:180])
            return

        # (pywinauto fallback kaldırıldı — Ctrl+A davranışı tüm sayfa seçimi
        # yaparak kullanıcıyı rahatsız ediyordu. Tek yol HTML DOM.)

    def _secilene_gonder(self):
        """Seçilen tek hasta için wa.me aç — _wa_ac ile aynı."""
        self._wa_ac()

    def _secili_iptal(self):
        m = self._aktif_mesaj()
        if not m:
            return
        if not messagebox.askyesno("Onay", f"{m['hasta_adi']} iptal edilsin mi?"):
            return
        self.kuyruk.iptal_et(m["kuyruk_id"])
        self._kuyruktan_yukle()
        self.durum_bar.config(text=f"❌ {m['hasta_adi']} iptal edildi.")

    def _gonderildi_manuel(self):
        """Seçili kuyruk kaydını 'gönderildi' olarak işaretle (WhatsApp açmadan).
        İleri tarihli ilaçlar otomatik yeni 'bekliyor' kaydına aktarılır."""
        m = self._aktif_mesaj()
        if not m:
            return
        if not messagebox.askyesno(
            "Gönderildi İşaretle",
            f"{m['hasta_adi']} — kuyruktaki bu kayıt "
            f"'gönderildi' olarak işaretlensin mi?\n\n"
            f"(Mesaj elle gönderildiyse veya atlandıysa kullanın)",
        ):
            return
        kid = m["kuyruk_id"]
        try:
            self.tv_yaz.item(str(kid), tags=("gonderildi",))
            self.root.update_idletasks()
        except Exception:
            pass
        try:
            self.kuyruk.gonderildi_isaretle(kid, sonuc="MESAJ GONDERILDI", manuel=True)
        except Exception as e:
            logger.exception("gonderildi_isaretle hatası")
            messagebox.showerror("Hata", f"Kayıt işaretlenemedi: {e}")
            return
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=f"✔ {m['hasta_adi']} mesaj gönderildi olarak işaretlendi, kuyruktan düşürüldü."
        )

    def _ilac_alindi(self):
        """Hasta ilacını eczaneden almış → kuyruktan düşür, log'a 'ALINDI'
        olarak yaz. İleri tarihli ilaçlar varsa otomatik yeni 'bekliyor'
        kaydına aktarılır (gonderildi_isaretle ile aynı davranış)."""
        m = self._aktif_mesaj()
        if not m:
            return
        if not messagebox.askyesno(
            "İlacını Aldı",
            f"{m['hasta_adi']} ilacını aldı olarak işaretlensin mi?\n\n"
            f"Kayıt kuyruktan düşer, log'a 'ALINDI' olarak kaydedilir.",
        ):
            return
        kid = m["kuyruk_id"]
        try:
            self.tv_yaz.item(str(kid), tags=("ilac_alindi",))
            self.root.update_idletasks()
        except Exception:
            pass
        try:
            self.kuyruk.gonderildi_isaretle(kid, sonuc="ILACINI ALDI", manuel=True)
        except Exception as e:
            logger.exception("gonderildi_isaretle hatası")
            messagebox.showerror("Hata", f"Kayıt işaretlenemedi: {e}")
            return
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=f"💊 {m['hasta_adi']} ilacını aldı olarak işaretlendi, kuyruktan düşürüldü."
        )

    def _filtre_uygula(self):
        """Filtre aktif edilir ve tablo yeniden yüklenir."""
        self._filt_bas_aktif.set(True)
        self._filt_bit_aktif.set(True)
        self._kuyruktan_yukle()

    def _filtre_temizle(self):
        self._filt_bas_aktif.set(False)
        self._filt_bit_aktif.set(False)
        if hasattr(self, "dt_filt_bas"):
            self.dt_filt_bas.set_date(date.today())
        if hasattr(self, "dt_filt_bit"):
            self.dt_filt_bit.set_date(date.today())
        if hasattr(self, "var_filt_bas"):
            self.var_filt_bas.set("")
        if hasattr(self, "var_filt_bit"):
            self.var_filt_bit.set("")
        if hasattr(self, "_filt_durum_lbl"):
            self._filt_durum_lbl.config(text="")
        self._kuyruktan_yukle()

    def _filtre_aralik_iso(self):
        """Aktif filtrenin (bas_iso, bit_iso) değerlerini döndür.
        Filtre pasifse ('', '') döner."""
        bas = ""
        bit = ""
        if getattr(self, "_filt_bas_aktif", None) and self._filt_bas_aktif.get():
            if hasattr(self, "dt_filt_bas"):
                try:
                    bas = self.dt_filt_bas.get_date().isoformat()
                except Exception:
                    bas = ""
            elif hasattr(self, "var_filt_bas"):
                bas = (self.var_filt_bas.get() or "").strip()
        if getattr(self, "_filt_bit_aktif", None) and self._filt_bit_aktif.get():
            if hasattr(self, "dt_filt_bit"):
                try:
                    bit = self.dt_filt_bit.get_date().isoformat()
                except Exception:
                    bit = ""
            elif hasattr(self, "var_filt_bit"):
                bit = (self.var_filt_bit.get() or "").strip()
        return bas, bit

    # -----------------------------------------------------------------
    # Sekme 2/3 davranışları
    # -----------------------------------------------------------------
    @staticmethod
    def _tarih_parse(s: str) -> "Optional[date]":
        s = (s or "").strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _int_parse(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None

    def _portfoy_yukle(self):
        bas = self._tarih_parse(self.var_pf_bas.get())
        bit = self._tarih_parse(self.var_pf_bit.get())
        son = self._tarih_parse(self.var_pf_songelis.get())
        if self.var_pf_songelis.get().strip() and son is None:
            messagebox.showwarning("Geçersiz Tarih", "Son geliş tarihini YYYY-AA-GG biçiminde girin.")
            return
        if (bas and not bit) or (bit and not bas):
            messagebox.showwarning("Geçersiz Aralık", "Başlangıç ve bitiş tarihini birlikte girin.")
            return

        self._progress_baslat("Hasta portföyü yükleniyor...")
        self.root.update_idletasks()
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.hasta_portfoyu_getir(
                baslangic=bas, bitis=bit,
                sadece_telefonlu=bool(self.var_pf_tel.get()),
                son_gelis_sonra=son,
                sadece_takipli=bool(self.var_pf_takip.get()),
                min_ziyaret=self._int_parse(self.var_pf_min.get()),
                max_ziyaret=self._int_parse(self.var_pf_max.get()),
            )
        except Exception as e:
            self._progress_durdur("❌ Hata")
            messagebox.showerror("Hata", str(e))
            return

        self._portfoy_sonuc = {}  # musteri_id -> row (detay için)
        for i in self.tv_portfoy.get_children():
            self.tv_portfoy.delete(i)
        for r in sonuc[:10000]:
            mid = r.get("musteri_id")
            self._portfoy_sonuc[str(mid)] = r
            self.tv_portfoy.insert("", "end", iid=str(mid), values=(
                r.get("hasta_adi") or "",
                r.get("cep_tel") or "",
                r.get("ziyaret_sayisi"),
                r.get("recete_sayisi"),
                r.get("ilk_ziyaret") or "",
                r.get("son_ziyaret") or "",
                r.get("son_ziyaretten_gun"),
                "Evet" if r.get("takipli") else "Hayır",
            ))
        self.lbl_portfoy.config(
            text=f"Toplam: {len(sonuc)} hasta (ilk {min(len(sonuc), 10000)} gösteriliyor)"
        )
        self._progress_durdur("Portföy yüklendi.")

    def _portfoy_hasta_detay(self):
        """Seçilen hastanın detay notebook'unu doldur."""
        sec = self.tv_portfoy.selection()
        if not sec:
            return
        mid = int(sec[0])
        r = self._portfoy_sonuc.get(str(mid), {})
        self.lbl_pf_detay.config(
            text=f"🧑 {r.get('hasta_adi','')}  |  📞 {r.get('cep_tel','-')}  |  "
                 f"ziyaret: {r.get('ziyaret_sayisi')}  |  son: {r.get('son_ziyaret','-')}"
        )

        if self.db is None:
            self.db = HastaTakipDB()

        # Raporlar
        for w in self.tv_pf_rap.get_children():
            self.tv_pf_rap.delete(w)
        try:
            raporlar = self.db.hastanin_aktif_raporlari(mid)
            for x in raporlar:
                self.tv_pf_rap.insert("", "end", values=(
                    x.get("rapor_no") or "", x.get("rapor_turu") or "",
                    x.get("rapor_tarihi") or "", x.get("bitis_tarihi") or "",
                    x.get("bitise_kac_gun") if x.get("bitise_kac_gun") is not None else "",
                    x.get("hastane") or "",
                ))
        except Exception as e:
            logger.warning("raporlar yüklenemedi: %s", e)

        # Yaklaşan yazdırmalar
        for w in self.tv_pf_yaz.get_children():
            self.tv_pf_yaz.delete(w)
        try:
            yazdirmalar = self.db.hastanin_yaklasan_yazdirmalari(
                mid, geri_gun=60, ileri_gun=30,
                rapor_tolerans_gun=self.ayarlar.rapor_yazdirma_tolerans_gun,
            )
            for x in yazdirmalar:
                self.tv_pf_yaz.insert("", "end", values=(
                    (x.get("urun_adi") or "")[:60],
                    x.get("bitis_tarihi") or "",
                    x.get("yazdirma_tarihi") or "",
                    x.get("kac_gun_kaldi") if x.get("kac_gun_kaldi") is not None else "",
                    x.get("rapor_no") or "",
                ))
        except Exception as e:
            logger.warning("yazdirmalar yüklenemedi: %s", e)

        # İlaç geçmişi
        for w in self.tv_pf_il.get_children():
            self.tv_pf_il.delete(w)
        try:
            ilaclar = self.db.hastanin_ilac_gecmisi(mid, limit=500)
            for x in ilaclar:
                self.tv_pf_il.insert("", "end", values=(
                    x.get("recete_tarihi") or "",
                    (x.get("urun_adi") or "")[:60],
                    x.get("adet"),
                    x.get("bitis_tarihi") or "",
                    x.get("rapor_no") or "",
                ))
        except Exception as e:
            logger.warning("ilac gecmisi yüklenemedi: %s", e)

    def _devamlilik_yukle(self):
        self._progress_baslat("Devamlılık raporu yükleniyor...")
        self.root.update_idletasks()
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.devamlilik_raporu()
        except Exception as e:
            self._progress_durdur("❌ Hata")
            messagebox.showerror("Hata", str(e))
            return
        for i in self.tv_devam.get_children():
            self.tv_devam.delete(i)
        for r in sonuc[:5000]:  # 90bin satır için UI don mamalı — top 5000
            self.tv_devam.insert("", "end", values=(
                r.get("hasta_adi") or "",
                r.get("cep_tel") or "",
                r.get("dogum_tarihi") or "",
                r.get("recete_adedi"),
                r.get("son_recete_tarihi") or "",
                r.get("kac_gun_oldu"),
                "Evet" if r.get("takipli") else "Hayır",
            ))
        self.lbl_devam.config(text=f"Toplam: {len(sonuc)} hasta (ilk 5000 gösteriliyor)")
        self._progress_durdur("Devamlılık raporu yüklendi.")

    # -----------------------------------------------------------------
    # Rapor Bitiş Takibi davranışları
    # -----------------------------------------------------------------
    def _rapor_bitis_yukle(self):
        self._progress_baslat("Rapor bitişleri taranıyor...")
        self.root.update_idletasks()
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.yaklasan_rapor_bitisleri(
                uyari_gun=int(self.var_rb_gun.get()),
                sadece_takipli=bool(self.var_rb_takipli.get()),
                sadece_telefonlu=bool(self.var_rb_telefonlu.get()),
                eski_gun=int(self.var_rb_geri.get()),
            )
        except Exception as e:
            self._progress_durdur("❌ Hata")
            messagebox.showerror("Hata", str(e))
            return

        # Yenileme kontrolü: aynı etken madde başka bir raporda daha geç
        # bitişle kapsanıyorsa, o raporun bitiş uyarısı gereksizdir.
        # Her rapor için: etken maddelerin TÜMÜ yenilenmişse raporu sonuçtan at.
        mids = {r["musteri_id"] for r in sonuc}
        self._rb_en_son_bitis: dict = {}  # mid -> {sgk: en_son_bitis}
        self._rb_rapor_em: dict = {}      # rid -> [em_list]
        rapor_yenilenmis: dict = {}       # rid -> bool (tüm EM'ler yenilenmişse True)
        for mid in mids:
            try:
                self._rb_en_son_bitis[mid] = self.db.hastanin_etkin_madde_en_son_bitis(mid)
            except Exception:
                self._rb_en_son_bitis[mid] = {}

        incelenen_rid = set()
        for r in sonuc:
            rid = r.get("rapor_id")
            if not rid or rid in incelenen_rid:
                continue
            incelenen_rid.add(rid)
            try:
                em_list = self.db.raporun_etkin_maddeleri(rid) or []
            except Exception:
                em_list = []
            self._rb_rapor_em[rid] = em_list
            if not em_list:
                rapor_yenilenmis[rid] = False
                continue
            rapor_bitis = str(r.get("bitis") or "")[:10]
            harita = self._rb_en_son_bitis.get(r["musteri_id"]) or {}
            tum_yenilenmis = True
            for em in em_list:
                sgk = (em.get("sgk_kodu") or "").strip()
                en_son = harita.get(sgk, "")
                if not (en_son and rapor_bitis and en_son > rapor_bitis):
                    tum_yenilenmis = False
                    break
            rapor_yenilenmis[rid] = tum_yenilenmis

        # Yenilenmiş raporların tanı satırlarını at
        sonuc = [r for r in sonuc if not rapor_yenilenmis.get(r.get("rapor_id"))]

        self._rb_sonuc = sonuc
        # Hasta bazında grupla
        gruplu: dict = {}
        for r in sonuc:
            gruplu.setdefault(r["musteri_id"], []).append(r)
        self._rb_hasta_map = gruplu

        for i in self.tv_rb.get_children():
            self.tv_rb.delete(i)

        for mid, satirlar in gruplu.items():
            ilk = satirlar[0]
            en_yakin = min((str(s.get("bitis") or "") for s in satirlar if s.get("bitis")), default="")
            en_yakin_kalan = min((s.get("kalan_gun") for s in satirlar if s.get("kalan_gun") is not None), default="")
            self.tv_rb.insert("", "end", iid=str(mid), values=(
                ilk.get("hasta_adi") or "",
                ilk.get("tckn") or "-",
                ilk.get("cep_tel") or "-",
                len(satirlar),
                (en_yakin or "")[:10],
                en_yakin_kalan,
                "Evet" if ilk.get("takipli") else "Hayır",
            ))

        self.lbl_rb_sayac.config(
            text=f"Toplam: {len(gruplu)} hasta | {len(sonuc)} tanı satırı"
        )
        self._progress_durdur(f"Rapor bitiş taraması tamam: {len(gruplu)} hasta")

    def _rapor_bitis_detay(self):
        sec = self.tv_rb.selection()
        if not sec:
            return
        mid = int(sec[0])
        satirlar = self._rb_hasta_map.get(mid, [])
        if not satirlar:
            return

        ilk = satirlar[0]
        self.lbl_rb_hasta.config(
            text=f"🧑 {ilk.get('hasta_adi','')}  |  📞 {ilk.get('cep_tel','-')}  |  "
                 f"T.C. {ilk.get('tckn','-')}  |  {len(satirlar)} tanı satırı"
        )

        # Tanı tablosu
        for w in self.tv_rb_tani.get_children():
            self.tv_rb_tani.delete(w)
        for t in satirlar:
            kod = (t.get("rapor_kodu") or "").strip()
            rapor_acikl = (t.get("rapor_kod_aciklama") or "").strip()
            icd_acikl = (t.get("icd_aciklamasi") or "").strip()
            # 20 kodlu raporlarda (EK-2 Listede Yer Almayan Hastalıklar)
            # rapor açıklaması genel bir ibaredir; ICD tanısı gösterilir.
            if kod.startswith("20") and icd_acikl:
                gosterilecek = self.kuyruk._tr_title(icd_acikl)
            else:
                gosterilecek = rapor_acikl
            self.tv_rb_tani.insert("", "end", values=(
                t.get("rapor_kodu") or "",
                gosterilecek[:50],
                t.get("icd_kodu") or "",
                icd_acikl[:50],
                str(t.get("baslama") or "")[:10],
                str(t.get("bitis") or "")[:10],
                t.get("kalan_gun") if t.get("kalan_gun") is not None else "",
            ))

        # Etken madde ve ilaç — tüm rapor_id'ler için birleştir
        rapor_ids = list({t.get("rapor_id") for t in satirlar if t.get("rapor_id")})
        em_map: dict = {}
        il_map: dict = {}
        tum_em = []
        tum_il = []
        # SGK kodu -> hastanın kullandığı ilaçlar (cache — aynı madde birkaç raporda geçebilir)
        hasta_ilac_cache: dict = {}
        for rid in rapor_ids:
            try:
                d = self.db.raporun_detayi(rid, mid)
            except Exception:
                d = {"etkin_maddeler": [], "ilaclar": []}
            em_list = d.get("etkin_maddeler") or []
            # Bu rapor için en geç bitiş (tanı satırlarından)
            rapor_bitis = ""
            for t in satirlar:
                if t.get("rapor_id") == rid:
                    b = str(t.get("bitis") or "")[:10]
                    if b > rapor_bitis:
                        rapor_bitis = b
            en_son_harita = getattr(self, "_rb_en_son_bitis", {}).get(mid, {}) or {}
            # Her etken madde için hastanın kullandığı ilaçları bağla
            for em in em_list:
                sgk = (em.get("sgk_kodu") or "").strip()
                # Yenilenmiş mi? (aynı EM başka raporda daha geç bitişle var)
                en_son = en_son_harita.get(sgk, "") if sgk else ""
                em["yenilenmis"] = bool(
                    en_son and rapor_bitis and en_son > rapor_bitis
                )
                if not sgk:
                    em["hasta_ilaclari"] = []
                    continue
                if sgk not in hasta_ilac_cache:
                    try:
                        hasta_ilac_cache[sgk] = self.db.hastanin_etkin_madde_ilaclari(mid, sgk)
                    except Exception:
                        hasta_ilac_cache[sgk] = []
                em["hasta_ilaclari"] = hasta_ilac_cache[sgk]
            em_map[rid] = em_list
            il_map[rid] = d.get("ilaclar") or []
            tum_em.extend(em_list)
            tum_il.extend(il_map[rid])

        for w in self.tv_rb_em.get_children():
            self.tv_rb_em.delete(w)
        # Yenilenmiş EM'ler gri görünsün
        self.tv_rb_em.tag_configure("yenilenmis", foreground="#9E9E9E")
        gorulen_em = set()
        for em in tum_em:
            k = (em.get("etkin_madde"), em.get("sgk_kodu"))
            if k in gorulen_em:
                continue
            gorulen_em.add(k)
            hi = em.get("hasta_ilaclari") or []
            hi_text = ", ".join((x.get("urun_adi") or "").strip() for x in hi if x.get("urun_adi"))
            em_adi = em.get("etkin_madde") or ""
            if em.get("yenilenmis"):
                em_adi = f"{em_adi}  ✓ yenilenmiş"
                tags = ("yenilenmis",)
            else:
                tags = ()
            self.tv_rb_em.insert("", "end", values=(
                em_adi,
                em.get("sgk_kodu") or "",
                em.get("doz") or "",
                hi_text or "—",
            ), tags=tags)

        for w in self.tv_rb_il.get_children():
            self.tv_rb_il.delete(w)
        gorulen_il = set()
        for il in tum_il:
            ad = il.get("urun_adi") or ""
            if ad in gorulen_il:
                continue
            gorulen_il.add(ad)
            self.tv_rb_il.insert("", "end", values=(
                ad[:60],
                str(il.get("bitis_tarihi") or "")[:10],
                str(il.get("recete_tarihi") or "")[:10],
            ))

        # Mesaj önizleme
        mesaj = self.kuyruk.rapor_bitis_mesaji_olustur(
            ilk.get("hasta_adi") or "", satirlar, em_map, il_map, self.ayarlar,
        )
        self.txt_rb_mesaj.delete("1.0", "end")
        self.txt_rb_mesaj.insert("1.0", mesaj)

    def _rb_aktif_hasta(self):
        sec = self.tv_rb.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Bir hasta seçin.")
            return None, None
        mid = int(sec[0])
        satirlar = self._rb_hasta_map.get(mid, [])
        return mid, satirlar[0] if satirlar else None

    def _rb_wa_ac(self):
        mid, ilk = self._rb_aktif_hasta()
        if not ilk:
            return
        tel = (ilk.get("cep_tel") or "").strip()
        if not tel or len(tel) < 10:
            messagebox.showwarning("Telefon Yok", f"{ilk.get('hasta_adi')} için telefon tanımlı değil.")
            return
        if tel.startswith("+"):
            tel = tel[1:]
        if tel.startswith("0"):
            tel = "90" + tel[1:]
        if not tel.startswith("90"):
            tel = "90" + tel
        mesaj = self.txt_rb_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj:
            return
        url = f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj)}"
        self._chrome_ile_ac(url)
        # Log'a yaz
        with self.kuyruk._conn() as c:
            c.execute(
                "INSERT INTO gonderim_log(musteri_id, hasta_adi, cep_tel, mesaj_metni, zaman, sonuc, isaret) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, ilk.get("hasta_adi"), tel, mesaj,
                 datetime.now().isoformat(timespec="seconds"), "OK", "📑 Rapor Bitiş"),
            )
        self.durum_bar.config(text=f"✅ {ilk.get('hasta_adi')} için rapor bitiş mesajı WhatsApp Web'de açıldı.")

    def _rb_panoya(self):
        mesaj = self.txt_rb_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(mesaj)
        self.durum_bar.config(text="📋 Rapor bitiş mesajı panoya kopyalandı.")

    # -----------------------------------------------------------------
    # Sekme 4 — Ayarları kaydet
    # -----------------------------------------------------------------
    def _ayarlar_snapshot(self) -> HastaTakipAyarlari:
        """Ekrandaki form değerlerinden anlık ayar nesnesi üret."""
        a = HastaTakipAyarlari.yukle()
        a.gonderim_modu = self.var_mod.get()
        a.periyot_gun = int(self.var_periyot.get())
        a.hafta_sonu_tolerans_gun = int(self.var_hs.get())
        a.rapor_yazdirma_tolerans_gun = int(self.var_rt.get())
        a.eski_kayit_gun = int(self.var_eski.get())
        if hasattr(self, "var_haber_gizle"):
            a.haber_verilenleri_gizle = bool(self.var_haber_gizle.get())
        if hasattr(self, "var_haber_gizle_yerel"):
            a.haber_verilenleri_gizle_yerel = bool(self.var_haber_gizle_yerel.get())
        if hasattr(self, "var_gonderilenleri_goster"):
            a.gonderilenleri_goster = bool(self.var_gonderilenleri_goster.get())
        if hasattr(self, "var_ilac_rapor_birlesik"):
            a.ilac_rapor_birlesik = bool(self.var_ilac_rapor_birlesik.get())
        a.sadece_takipli = bool(self.var_takipli.get())
        if hasattr(self, "var_sadece_raporlu"):
            a.sadece_raporlu = bool(self.var_sadece_raporlu.get())
        if hasattr(self, "var_raporsuz_istisna"):
            ham = self.var_raporsuz_istisna.get() or ""
            ids: list = []
            for p in ham.replace(";", ",").split(","):
                p = p.strip()
                if not p:
                    continue
                try:
                    ids.append(int(p))
                except ValueError:
                    pass
            a.raporsuz_istisna_urunler = ids
        a.kaynak = self.var_kaynak.get()
        a.calisma_baslangic = self.var_bas.get()
        a.calisma_bitis = self.var_bit.get()
        a.eczane_adi = self.var_ec_ad.get()
        a.eczane_tel = self.var_ec_tel.get()
        a.mesaj_sablonu = self.txt_sablon.get("1.0", "end").rstrip("\n")
        a.ilac_satir_formati = self.var_satir.get()
        a.toplu_gonderim_gunu = int(self.var_gonderim_gun.get())
        # Rapor bitiş şablonları
        if hasattr(self, "var_rb_uyari"):
            a.rapor_bitis_uyari_gun = int(self.var_rb_uyari.get())
        if hasattr(self, "txt_rb_sablon"):
            a.rapor_bitis_mesaj_sablonu = self.txt_rb_sablon.get("1.0", "end").rstrip("\n")
        if hasattr(self, "txt_rb_tani_sablon"):
            a.rapor_bitis_tani_satir_formati = self.txt_rb_tani_sablon.get("1.0", "end").rstrip("\n")
        return a

    def _ayarlari_kaydet(self):
        a = self._ayarlar_snapshot()
        a.kaydet()
        self.ayarlar = a
        messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi.")
        self.durum_bar.config(text="Ayarlar kaydedildi.")

    # -----------------------------------------------------------------
    # Sekme 5 — log
    # -----------------------------------------------------------------
    def _log_mesaj_onizleme(self):
        """Log tablosundan seçili satır için atılan mesajı önizleme alanına bas."""
        import json
        sec = self.tv_log.selection()
        if not sec:
            return
        try:
            lid = int(sec[0])
        except Exception:
            return
        kayit = None
        for r in self.kuyruk.log_getir(limit=5000):
            if r.get("id") == lid:
                kayit = r
                break
        self.txt_log_mesaj.delete("1.0", "end")
        if kayit is None:
            self.txt_log_mesaj.insert("1.0", "(Kayıt bulunamadı.)")
            return
        ham = kayit.get("mesaj_metni") or ""
        try:
            ilaclar = json.loads(ham)
            a = self._ayarlar_snapshot()
            from hasta_takip_kuyruk import MesajKuyrugu
            metin = MesajKuyrugu.mesaj_olustur(kayit.get("hasta_adi", ""), ilaclar, a)
        except Exception:
            metin = ham  # JSON değilse ham metni göster
        basliklar = (
            f"🧑 {kayit.get('hasta_adi','')}  "
            f"|  📞 {kayit.get('cep_tel','-')}  "
            f"|  🕐 {kayit.get('zaman','')}  "
            f"|  Sonuç: {kayit.get('sonuc') or '-'}\n"
            f"{'─' * 60}\n"
        )
        self.txt_log_mesaj.insert("1.0", basliklar + metin)

    def _log_yukle(self):
        for i in self.tv_log.get_children():
            self.tv_log.delete(i)
        filtre = getattr(self, "var_log_filtre", None)
        filtre_deger = filtre.get() if filtre else "hepsi"
        for r in self.kuyruk.log_getir(tarih_filtresi=filtre_deger):
            self.tv_log.insert("", "end", iid=str(r["id"]), values=(
                r.get("zaman"), r.get("hasta_adi"), r.get("cep_tel"),
                r.get("isaret") or "",
                (r.get("not_metni") or "")[:80],
                r.get("sonuc") or "",
            ))
        try:
            ozet = self.kuyruk.log_ozet()
            self.lbl_log_sayac.config(
                text=f"Toplam: {ozet['toplam']} | Bugün: {ozet['bugun']} "
                     f"({ozet['bugun_ok']} OK) | Son 7 gün: {ozet['hafta']}"
            )
        except Exception:
            pass

    def _log_excel_aktar(self):
        """Görünen filtre ile log kayıtlarını Excel'e aktarır."""
        try:
            import openpyxl  # type: ignore
        except ImportError:
            messagebox.showerror("Eksik Modül", "openpyxl kurulu değil.\n\npip install openpyxl")
            return
        filtre = getattr(self, "var_log_filtre", None)
        filtre_deger = filtre.get() if filtre else "hepsi"
        kayitlar = self.kuyruk.log_getir(limit=10000, tarih_filtresi=filtre_deger)
        if not kayitlar:
            messagebox.showinfo("Boş", "Aktarılacak kayıt yok.")
            return
        from tkinter import filedialog
        yol = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"gonderim_log_{filtre_deger}_{date.today().isoformat()}.xlsx",
            title="Log Excel olarak kaydet",
        )
        if not yol:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Gönderim Log"
        ws.append(["Zaman", "Hasta", "Telefon", "İşaret", "Not", "Sonuç", "Mesaj"])
        for r in kayitlar:
            ws.append([
                r.get("zaman") or "",
                r.get("hasta_adi") or "",
                r.get("cep_tel") or "",
                r.get("isaret") or "",
                r.get("not_metni") or "",
                r.get("sonuc") or "",
                (r.get("mesaj_metni") or "")[:500],
            ])
        # Kolon genişlikleri
        for idx, genislik in enumerate([20, 28, 14, 18, 40, 10, 60], start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = genislik
        wb.save(yol)
        messagebox.showinfo("Tamam", f"{len(kayitlar)} kayıt aktarıldı:\n{yol}")

    def _log_sagtik(self, event):
        rid = self.tv_log.identify_row(event.y)
        if not rid:
            return
        self.tv_log.selection_set(rid)
        try:
            self.menu_log.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_log.grab_release()

    def _log_secili_id(self) -> "Optional[int]":
        sec = self.tv_log.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Bir satır seçin.")
            return None
        return int(sec[0])

    def _log_isaret(self, isaret: str):
        lid = self._log_secili_id()
        if lid is None:
            return
        self.kuyruk.log_isaret_guncelle(lid, isaret)
        self._log_yukle()
        self.durum_bar.config(text=f"İşaret güncellendi: {isaret or '(temiz)'}")

    def _log_not(self):
        from tkinter import simpledialog
        lid = self._log_secili_id()
        if lid is None:
            return
        # Mevcut notu getir
        mevcut = ""
        for r in self.kuyruk.log_getir(limit=1000):
            if r["id"] == lid:
                mevcut = r.get("not_metni") or ""
                break
        yeni = simpledialog.askstring(
            "Not Düş", "Bu mesaj için not:", initialvalue=mevcut, parent=self.root,
        )
        if yeni is None:
            return
        self.kuyruk.log_not_guncelle(lid, yeni)
        self._log_yukle()
        self.durum_bar.config(text="Not güncellendi.")

    # -----------------------------------------------------------------
    def _batch_degisti(self):
        """Spinbox değeri değiştiğinde: ayarı kaydet. DB taraması YAPILMAZ —
        kullanıcının '🔄 Yenile' butonuna basması beklenir (gereksiz sorgu
        yükünü önlemek için)."""
        try:
            yeni = int(self.var_batch.get())
        except Exception:
            return
        yeni = max(0, min(60, yeni))
        mevcut = int(getattr(self.ayarlar, "batch_bekleme_gun", 5) or 0)
        if yeni == mevcut:
            # Değer değişmedi — menzil sütunu için tabloyu hafifçe tazele
            self._kuyruktan_yukle()
            return
        self.ayarlar.batch_bekleme_gun = yeni
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"Batch ayarı kaydedilemedi: {e}")
        # Yeni değer, ekrandaki menzil sütunu ve gösterim filtreleri için geçerli
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=f"🔗 Batch {yeni} güne ayarlandı — güncel sonuç için '🔄 Yenile'ye basın."
        )

    # -----------------------------------------------------------------
    def _ilac_rapor_birlesik_degisti(self):
        """'Rapor bitişini de ekle' checkbox'ı değişince ayarı kaydet ve
        varsa seçili mesajın önizlemesini yeniden üret."""
        yeni = bool(self.var_ilac_rapor_birlesik.get())
        self.ayarlar.ilac_rapor_birlesik = yeni
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"ilac_rapor_birlesik kaydedilemedi: {e}")
        # Seçili kayıt varsa önizlemeyi tazele
        try:
            self._secim_guncelle()
        except Exception:
            pass
        self.durum_bar.config(
            text=("💊+📑 İlaç mesajına rapor bitişi eklenecek" if yeni
                  else "💊 Sadece ilaç mesajı gönderilecek")
        )

    def _gonderilenleri_goster_degisti(self):
        """'Mesaj atılanları da getir' checkbox'ı değişince ayarı kaydet ve
        tabloyu kuyruktan yeniden yükle (DB'ye gidilmez)."""
        yeni = bool(self.var_gonderilenleri_goster.get())
        self.ayarlar.gonderilenleri_goster = yeni
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"gonderilenleri_goster kaydedilemedi: {e}")
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=("📬 Mesaj atılanlar da listede (yeşil)" if yeni
                  else "📬 Sadece bekleyenler listede")
        )

    def _haber_gizle_yerel_degisti(self):
        """'Haber verilenleri getirme (Yerel)' checkbox'ı değişince ayarı
        kaydet ve tabloyu kuyruktan yeniden yükle. DB'ye gitmez —
        gonderim_ilac_log yerel tabloya bakar."""
        yeni = bool(self.var_haber_gizle_yerel.get())
        self.ayarlar.haber_verilenleri_gizle_yerel = yeni
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"haber_verilenleri_gizle_yerel kaydedilemedi: {e}")
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=("🏠 Yerel log'daki haber verilenler gizlendi" if yeni
                  else "🏠 Yerel log filtresi kapalı")
        )

    def _haber_gizle_degisti(self):
        """'Haber verilenleri getirme' checkbox'ı değişince ayarı kaydet.
        DB taraması YAPILMAZ — kullanıcı '🔄 Yenile'ye basınca güncel sonuç alır."""
        yeni = bool(self.var_haber_gizle.get())
        self.ayarlar.haber_verilenleri_gizle = yeni
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"haber_verilenleri_gizle kaydedilemedi: {e}")
        self.durum_bar.config(
            text=("📢 Haber verilenler gizlenecek" if yeni
                  else "📢 Haber verilenler de listede")
            + " — güncel sonuç için '🔄 Yenile'ye basın."
        )

    def _eski_gun_degisti(self):
        """'Son N gün önce bitmiş' spinbox'ı değişince: ayarı kaydet +
        filtre baş tarihini otomatik geriye çek. DB taraması YAPILMAZ —
        kullanıcının '🔄 Yenile' butonuna basması beklenir.

        ayarlar.eski_kayit_gun → hasta_takip_db SQL'indeki bitiş filtresi:
            RIBitisTarihi >= DATEADD(DAY, -eski_kayit_gun, bugun)
        """
        try:
            yeni = int(self.var_eski_gun.get())
        except Exception:
            return
        yeni = max(0, min(365, yeni))
        self.ayarlar.eski_kayit_gun = yeni
        # Ayarlar sekmesindeki aynı değişkeni senkronla — aksi halde
        # _ayarlar_snapshot() eski değerle gelir ve filtre çalışmaz
        if hasattr(self, "var_eski"):
            try:
                self.var_eski.set(yeni)
            except Exception:
                pass
        try:
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"eski_kayit_gun kaydedilemedi: {e}")

        # Filtre baş tarihini geriye çek (ekran filtresi tarama ile uyumlu kalsın)
        yeni_bas = date.today() - timedelta(days=yeni)
        try:
            if hasattr(self, "dt_filt_bas"):
                self.dt_filt_bas.set_date(yeni_bas)
            elif hasattr(self, "var_filt_bas"):
                self.var_filt_bas.set(yeni_bas.isoformat())
            if hasattr(self, "_filt_bas_aktif"):
                self._filt_bas_aktif.set(True)
        except Exception as e:
            logger.debug(f"Filtre tarihi güncellenemedi: {e}")

        # Kuyruktaki eski kayıtları yeni eşiğe göre tabloda gizle (DB'ye gitmez)
        self._kuyruktan_yukle()
        self.durum_bar.config(
            text=f"📅 Son {yeni} gün önce bitmiş — güncel sonuç için '🔄 Yenile'ye basın."
        )

    # -----------------------------------------------------------------
    def _bekleteni_indir(self):
        """Seçili kaydın ileri tarihli ilaçlarını kayıttan çıkar.

        Otobüs benzetmesi: bekleyen yolcuları indir, otobüs (bugünkü ilaçlar)
        bugün yola çıkabilir. Satır açık sarıya (indirildi) döner. İleri
        tarihli ilaçlar bayrak korunduğu sürece yeniden eklenmez — kayıt
        gönderildikten sonra doğal olarak sonraki taramada yeni kayıt olurlar.
        """
        m = self._aktif_mesaj()
        if not m:
            return
        if bool(m.get("bekleteni_indirildi")):
            messagebox.showinfo(
                "Zaten İndirildi",
                f"{m['hasta_adi']} için bekleten ilaçlar zaten indirildi "
                f"(satır açık sarı).",
            )
            return
        # Önizleme: kaç ilaç indirilecek?
        bugun_iso = date.today().isoformat()
        kalacak = []
        indirilecek = []
        for il in m.get("ilaclar", []) or []:
            yt = str(il.get("yazdirma_tarihi") or "")[:10]
            if yt and yt > bugun_iso:
                indirilecek.append(il)
            else:
                kalacak.append(il)

        if not indirilecek:
            messagebox.showinfo(
                "İleri Tarihli İlaç Yok",
                f"{m['hasta_adi']} için bekleten (ileri tarihli) ilaç yok. "
                f"Kayıt zaten bugüne planlı.",
            )
            return
        if not kalacak:
            messagebox.showwarning(
                "Bugüne Hazır İlaç Yok",
                "Tüm ilaçlar ileri tarihli. İndirilecek bir şey yok — "
                "otobüs zaten kalkmamış.",
            )
            return

        indirilecek_isim = ", ".join(
            (il.get("urun_adi") or "") for il in indirilecek
        )
        if not messagebox.askyesno(
            "Bekleteni İndir",
            f"{m['hasta_adi']} — şu ileri tarihli {len(indirilecek)} ilaç "
            f"kayıttan çıkarılsın mı?\n\n"
            f"{indirilecek_isim}\n\n"
            f"Kalan {len(kalacak)} ilaç bugün gönderilebilir hale gelecek. "
            f"Satır açık sarı görünecek."
        ):
            return

        try:
            sayi = self.kuyruk.bekleteni_indir(m["kuyruk_id"])
        except Exception as e:
            messagebox.showerror("Hata", f"Bekleteni indirme başarısız:\n{e}")
            return
        if sayi <= 0:
            messagebox.showinfo("Değişiklik Yok", "İndirilecek ilaç bulunamadı.")
            return
        self.durum_bar.config(
            text=f"🚏 {m['hasta_adi']} — {sayi} bekleten ilaç indirildi. "
                 f"Otobüs kalkabilir."
        )
        self._kuyruktan_yukle()

    # -----------------------------------------------------------------
    def _mesaji_ilac_gecmisinden_guncelle(self):
        """MEDULA'da açık olan '{HASTA} İlaç Listesi' penceresinden günü
        gelmiş ilaçları oku, mesaj şablonuna göre önizlemeyi güncelle.

        SALT OKUMA: Hiçbir veri kaydedilmez; MEDULA'daki buton tıklamaz.
        """
        m = self._aktif_mesaj()
        if not m:
            return

        try:
            from medula_ilac_listesi_oku import (
                medula_bul,
                ilaclari_oku,
                hasta_dogrula,
            )
        except Exception as e:
            messagebox.showerror(
                "Import Hatası",
                f"medula_ilac_listesi_oku yüklenemedi:\n{type(e).__name__}: {e}",
            )
            return

        self.durum_bar.config(text="⏳ MEDULA Kullanılan İlaç Listesi okunuyor...")
        self.root.update_idletasks()

        # SENKRON ÇALIŞTIR — COM apartment affinity için tüm çağrılar ana thread
        medula = medula_bul()
        if not medula:
            try:
                import win32gui as _wg
                lst = []
                def _e(h, _):
                    if _wg.IsWindowVisible(h):
                        t = _wg.GetWindowText(h) or ""
                        c = _wg.GetClassName(h) or ""
                        if "MEDULA" in t or "BotanikEOS" in t:
                            lst.append(f"  [{c}] {t}")
                    return True
                _wg.EnumWindows(_e, None)
                ek = "\n\nGörünen pencereler:\n" + ("\n".join(lst) or "  (hiçbiri)")
            except Exception:
                ek = ""
            messagebox.showwarning(
                "MEDULA Yok",
                "MEDULA penceresi bulunamadı. BotanikEOS açık olmalı." + ek,
            )
            self.durum_bar.config(text="Hazır")
            return

        # KATI DOĞRULAMA: kuyruk hastası ile MEDULA hastası eşleşiyor mu?
        kuyruk_hasta = (m.get("hasta_adi") or "").strip()
        kuyruk_tc = (m.get("tckn") or "").strip()
        eslesti, dogr_mesaj, pencere_hasta, pencere_tc = hasta_dogrula(
            kuyruk_hasta, kuyruk_tc,
        )
        if not eslesti:
            messagebox.showerror(
                "Hasta Uyumsuzluğu — İŞLEM DURDURULDU",
                f"Mesajın ait olduğu hasta ile MEDULA'da açık İlaç Listesi "
                f"sayfasındaki hasta FARKLI.\n\n"
                f"Kuyruk hastası: {kuyruk_hasta} (TC: {kuyruk_tc})\n"
                f"MEDULA hastası: {pencere_hasta} (TC: {pencere_tc})\n\n"
                f"{dogr_mesaj}\n\n"
                f"Yanlış hastaya mesaj göndermemek için işlem iptal edildi. "
                f"Önce doğru hastanın 'Kullanılan İlaç Listesi' sayfasını aç.",
            )
            self.durum_bar.config(text="❌ Hasta uyumsuzluğu — işlem iptal.")
            return

        # Batch penceresi kadar gelecekteki ilaçları da dahil et (sarı)
        batch_gun = int(getattr(self.ayarlar, "batch_bekleme_gun", 5) or 0)
        ilaclar = ilaclari_oku(medula, gelecek_gun=batch_gun)
        if not ilaclar:
            messagebox.showinfo(
                "Uygun İlaç Yok",
                "Açık MEDULA sayfasında 'Yazdırma günü gelmiştir' "
                "etiketli VE rapor kodu dolu ilaç bulunamadı.\n\n"
                "Önce 💊 Medulada İlaç Listesi Aç ile 'Kullanılan "
                "İlaç Listesi' sayfasına girin.",
            )
            self.durum_bar.config(text="Uygun ilaç yok.")
            return

        hasta_adi = pencere_hasta or kuyruk_hasta
        bugun = date.today()
        # Aynı ürün adı birden fazla reçete satırı olarak gelebilir
        # (ör. hasta aynı ilacı farklı kutular olarak 4 reçete yapmış).
        # Kullanıcıya tek satır göstermek için ürün adına göre tekilleştir;
        # en erken yazdırma gününü referans al.
        tekil: Dict[str, Dict] = {}
        for il in ilaclar:
            ad = (il.get("urun_adi") or "").strip().upper()
            if not ad:
                continue
            gf = int(il.get("gun_farki") or 0)
            yazdirma = (bugun + timedelta(days=gf)).isoformat()
            kayit = {
                "urun_adi": il["urun_adi"],
                "yazdirma_tarihi": yazdirma,
                "bitis_tarihi": il.get("verilebilecegi_tarih") or "",
                "rapor_kodu": il.get("rapor_kodu") or "",
                "kaynak": "MEDULA",
                "gelecek": bool(il.get("gelecek")),
            }
            eski = tekil.get(ad)
            if eski is None or (
                kayit["yazdirma_tarihi"] < (eski.get("yazdirma_tarihi") or "")
            ):
                tekil[ad] = kayit
        ilac_dict = list(tekil.values())
        mesaj = self.kuyruk.mesaj_olustur(hasta_adi, ilac_dict, self.ayarlar)

        self.txt_mesaj.delete("1.0", "end")
        self.txt_mesaj.insert("1.0", mesaj)

        # Gelecek (ertelenen) ilaç satırlarını sarı tagle
        try:
            self.txt_mesaj.tag_configure("gelecek", background="#FFF9C4")
            import re as _re
            pat = _re.compile(r"\((?:yarın|\d+\s+gün\s+sonra)\)")
            for idx, satir in enumerate(mesaj.splitlines(), start=1):
                if pat.search(satir):
                    self.txt_mesaj.tag_add("gelecek", f"{idx}.0", f"{idx}.end")
        except Exception as e:
            logger.debug(f"Sarı tag uygulanamadı: {e}")

        gelecek_sayi = sum(1 for il in ilaclar if il.get("gelecek"))
        gunu_gelen = len(ilaclar) - gelecek_sayi
        self.durum_bar.config(
            text=(
                f"✓ {hasta_adi} — {gunu_gelen} günü gelmiş + "
                f"{gelecek_sayi} gelecek ({batch_gun} gün içinde) ilaç, "
                f"mesaj güncellendi."
            )
        )

    # -----------------------------------------------------------------
    def _oturum_canli_toggle(self):
        """'Oturumu Açık Tut' checkbox değiştiğinde servisi başlat/durdur."""
        try:
            from medula_oturum_canli import get_servis, IDLE_ESIK_SN
        except Exception as e:
            messagebox.showerror("Hata", f"Oturum modülü yüklenemedi:\n{e}")
            self.var_oturum_canli.set(False)
            return
        servis = get_servis()
        if self.var_oturum_canli.get():
            if servis.basla():
                self.durum_bar.config(
                    text=f"🔒 Oturum canlı tutma açık ({IDLE_ESIK_SN}s eşik)."
                )
                # Canlı geri sayımı başlat
                self._oturum_tik_baslat()
            else:
                self.var_oturum_canli.set(False)
                messagebox.showerror(
                    "Başlatılamadı",
                    "Oturum canlı tutma başlatılamadı.\n"
                    "pynput kurulu mu? (pip install pynput)",
                )
                return
        else:
            servis.dur()
            self.durum_bar.config(text="🔓 Oturum canlı tutma kapalı.")
            if hasattr(self, "lbl_oturum_durum"):
                self.lbl_oturum_durum.config(text="")
        # Ayarı kaydet
        try:
            self.ayarlar.oturum_canli_tut = bool(self.var_oturum_canli.get())
            self.ayarlar.kaydet()
        except Exception as e:
            logger.debug(f"Ayar kaydetme hatası: {e}")

    # -----------------------------------------------------------------
    def _oturum_tik_baslat(self):
        """Her 1 saniyede checkbox yanındaki etikete kalan süreyi yaz."""
        try:
            from medula_oturum_canli import get_servis, IDLE_ESIK_SN
            servis = get_servis()
            if not servis.aktif_mi() or not self.var_oturum_canli.get():
                if hasattr(self, "lbl_oturum_durum"):
                    self.lbl_oturum_durum.config(text="")
                return
            kalan = int(IDLE_ESIK_SN - servis.idle_saniye())
            if kalan < 0:
                kalan = 0
            if kalan <= 10:
                renk = "#D84315"
            elif kalan <= 30:
                renk = "#EF6C00"
            else:
                renk = "#455A64"
            if hasattr(self, "lbl_oturum_durum"):
                self.lbl_oturum_durum.config(
                    text=f"⏱ {kalan}s", fg=renk,
                )
        except Exception as e:
            logger.debug(f"Oturum tik hatası: {e}")
        # Yeniden zamanla
        try:
            self.root.after(1000, self._oturum_tik_baslat)
        except Exception:
            pass

    # -----------------------------------------------------------------
    def _oturum_simdi_yenile(self):
        """Manuel tetikleme: MEDULA'ya hemen F5 gönder (test için)."""
        try:
            from medula_oturum_canli import get_servis
            servis = get_servis()
            # Private method ama test butonu olduğu için OK
            import threading as _t
            _t.Thread(target=servis._oturumu_yenile, daemon=True).start()
            self.durum_bar.config(text="⚡ MEDULA tazeleniyor (F5 → Tamam → Enter)...")
        except Exception as e:
            messagebox.showerror("Hata", f"Tazeleme başarısız:\n{e}")

    # -----------------------------------------------------------------
    def _sutun_gorunurlugu_uygula(self):
        """Ayarlardaki sutun_gorunurlugu dict'ine göre sütunları göster/gizle."""
        try:
            gor = getattr(self.ayarlar, "sutun_gorunurlugu", {}) or {}
            gosterilen = [
                k for (k, _b, _w, _a) in self._sutun_tanimlari
                if gor.get(k, True)
            ]
            # En az bir sütun açık kalsın
            if not gosterilen:
                gosterilen = ["hasta"]
            self.tv_yaz.configure(displaycolumns=gosterilen)
        except Exception as e:
            logger.debug(f"Sütun görünürlüğü uygulanamadı: {e}")

    def _sutun_ayarlari_ac(self):
        """Sütun aç/kapat dialog'u."""
        win = tk.Toplevel(self.root)
        win.title("Sütun Ayarları")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(
            win, text="Yazdırma tablosunda gösterilecek sütunlar:",
            font=("Arial", 10, "bold"), pady=8, padx=12,
        ).pack(anchor="w")

        mevcut = dict(getattr(self.ayarlar, "sutun_gorunurlugu", {}) or {})
        varlar = {}
        frm = tk.Frame(win)
        frm.pack(fill="x", padx=16, pady=4)
        for k, b, _w, _a in self._sutun_tanimlari:
            v = tk.BooleanVar(value=bool(mevcut.get(k, True)))
            varlar[k] = v
            tk.Checkbutton(
                frm, text=b, variable=v, anchor="w",
                font=("Arial", 10),
            ).pack(fill="x", pady=2)

        btn_frm = tk.Frame(win)
        btn_frm.pack(fill="x", padx=12, pady=10)

        def kaydet():
            self.ayarlar.sutun_gorunurlugu = {k: bool(v.get()) for k, v in varlar.items()}
            self.ayarlar.kaydet()
            self._sutun_gorunurlugu_uygula()
            self.durum_bar.config(text="⚙ Sütun ayarları uygulandı.")
            win.destroy()

        def varsayilan():
            for k, v in varlar.items():
                vars_def = {
                    "planli_tarih": True, "hasta": True, "tc": False, "tel": False,
                    "ilac_sayi": True, "menzil": True,
                    "ziyaret": True, "son_gelis": False,
                    "gun": True, "takip": False,
                }
                v.set(vars_def.get(k, True))

        tk.Button(
            btn_frm, text="Varsayılana Dön", command=varsayilan,
            bg="#90A4AE", fg="white", bd=0, padx=10, pady=4,
        ).pack(side="left")
        tk.Button(
            btn_frm, text="İptal", command=win.destroy,
            bg="#B0BEC5", fg="white", bd=0, padx=12, pady=4,
        ).pack(side="right")
        tk.Button(
            btn_frm, text="Kaydet", command=kaydet,
            bg="#43A047", fg="white", bd=0, padx=14, pady=4,
        ).pack(side="right", padx=6)

    # -----------------------------------------------------------------
    def _kategori_ayarlari_ac(self):
        """Raporsuz olsa da takibe dahil edilecek ilaç kategorileri dialog'u."""
        win = tk.Toplevel(self.root)
        win.title("💊 Kategori Takibi")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(
            win, text="Raporsuz olsa da takip edilecek kategoriler:",
            font=("Arial", 10, "bold"), pady=8, padx=12,
        ).pack(anchor="w")
        tk.Label(
            win,
            text=(
                "İşaretli kategorilerdeki ilaçlar, raporlu olmasalar bile "
                "listeye dahil edilir.\n"
                "Takip bitiş tarihine göre yapılır (erken yazdırma yok — "
                "raporsuz olduğu için)."
            ),
            bg="white", fg="#546E7A", font=("Arial", 9),
            wraplength=540, justify="left", padx=12, pady=4,
        ).pack(anchor="w")

        kategoriler = dict(getattr(self.ayarlar, "kategori_takibi", {}) or {})
        etiketler = {
            "b12_vitamini":  "💉 B12 Vitamini  (DODEX, BENEXOL, APIKOBAL, METHYCOBAL, BEDODEKA…)",
            "d_vitamini":    "☀ D Vitamini  (DEVIT, DESIFEROL, OLEDAN, DEKRISTOL, DESUNIN…)",
            "mide_ilaclari": "🫃 Mide  (PPI: OMEPRAZOL/NEXIUM/LANSOR  +  H2: RANITIDIN/FAMOTIDIN…)",
            "demir":         "🩸 Demir  (FERRO SANOL, FERRUM, MALTOFER, FERRITON, FERINJECT…)",
            "magnezyum":     "💊 Magnezyum  (MAGNORM, MAGCEL, MAG 365, MAGNEX, MAGNERICH…)",
            "hemoroid":      "🩹 Hemoroid / Venotonic  (DOXIUM, MODET, DAFLON, DETRALEX, VENORUTON…)",
            "hormonlar":     "🦋 Hormonlar  (LEVOTIRON, EUTHYROX, PROPIL, PREDNOL, ANGELIQ, MINIRIN…)",
            "tansiyon":      "🩺 Tansiyon  (ACEi/ARB/BB/CCB — DELIX, MICARDIS, CONCOR, NORVASC, EXFORGE…)",
            "seker":         "🍬 Şeker  (Metformin, DIAMICRON, JARDIANCE, FORZIGA, OZEMPIC, LANTUS…)",
            "kalp":          "❤ Kalp  (Statin, Fibrat, antiagregan, antikoagülan, nitrat — CRESTOR, PLAVIX, XARELTO, VASTAREL…)",
            "depresyon":     "🧠 Depresyon  (SSRI/SNRI/TCA — CIPRALEX, LUSTRAL, EFFEXOR, CYMBALTA, REMERON…)",
            "antipsikotik":  "🌀 Antipsikotik  (ZYPREXA, RISPERDAL, SEROQUEL, ABILIFY, HALDOL, LEPONEX…)",
            "antiaritmik":   "⚡ Antiaritmik  (AMIODARON/CORDARON, SOTALOL, MULTAQ, PROPAFENON…)",
            "diuretik":      "💧 Diüretik  (LASIX, NATRILIX, ALDACTONE, ESIDREX, kombinasyonlar…)",
            "epilepsi":      "🧩 Epilepsi  (KEPPRA, LAMICTAL, LYRICA, DEPAKIN, TEGRETOL, VIMPAT, TOPAMAX…)",
            "ozel":          "⚙ Özel Liste  (aşağıda anahtar kelime girin)",
        }

        varlar = {}
        frm = tk.Frame(win)
        frm.pack(fill="x", padx=16, pady=4)
        for key in ("b12_vitamini", "d_vitamini", "mide_ilaclari",
                    "demir", "magnezyum", "hemoroid", "hormonlar",
                    "tansiyon", "seker", "kalp", "depresyon",
                    "antipsikotik", "antiaritmik", "diuretik", "epilepsi",
                    "ozel"):
            v = tk.BooleanVar(value=bool(kategoriler.get(key, False)))
            varlar[key] = v
            tk.Checkbutton(
                frm, text=etiketler.get(key, key), variable=v, anchor="w",
                font=("Arial", 10),
            ).pack(fill="x", pady=2)

        # Özel kategori için virgülle ayrılmış anahtar kelimeler
        tk.Label(
            win, text="Özel anahtar kelimeler (virgülle ayırın):",
            font=("Arial", 9, "bold"), pady=4, padx=16,
        ).pack(anchor="w")
        var_ozel = tk.StringVar(
            value=getattr(self.ayarlar, "kategori_ozel_anahtarlar", "") or ""
        )
        tk.Entry(
            win, textvariable=var_ozel, width=58,
        ).pack(padx=16, pady=(0, 8))
        tk.Label(
            win, text="Örn: KREATIN, OMEGA 3, ASPIRIN",
            bg="white", fg="#90A4AE", font=("Arial", 8, "italic"),
            padx=16,
        ).pack(anchor="w")

        btn_frm = tk.Frame(win)
        btn_frm.pack(fill="x", padx=12, pady=10)

        def kaydet():
            self.ayarlar.kategori_takibi = {
                k: bool(v.get()) for k, v in varlar.items()
            }
            self.ayarlar.kategori_ozel_anahtarlar = var_ozel.get().strip()
            self.ayarlar.kaydet()
            win.destroy()
            self.durum_bar.config(
                text="💊 Kategori ayarları uygulandı — DB yeniden taranıyor..."
            )
            self.root.update_idletasks()
            self._yazdirma_yenile()

        tk.Button(
            btn_frm, text="İptal", command=win.destroy,
            bg="#B0BEC5", fg="white", bd=0, padx=12, pady=4,
        ).pack(side="right")
        tk.Button(
            btn_frm, text="Kaydet & Yenile", command=kaydet,
            bg="#43A047", fg="white", bd=0, padx=14, pady=4,
            font=("Arial", 10, "bold"),
        ).pack(side="right", padx=6)

    # -----------------------------------------------------------------
    def _yerlesimi_kaydet(self):
        """Anki MEDULA + Hasta Takip pencere konumlarını JSON'a yaz."""
        try:
            from pencere_yerlesim import yerlesimi_kaydet_simdi, yerlesim_yukle
        except Exception as e:
            messagebox.showerror("Hata", f"pencere_yerlesim modülü yüklenemedi:\n{e}")
            return
        ok = yerlesimi_kaydet_simdi(tk_root=self.root)
        data = yerlesim_yukle()
        medula_var = "medula" in data
        ht_var = "hasta_takip" in data
        if ok:
            mesaj = (
                f"✓ Yerleşim kaydedildi.\n\n"
                f"MEDULA: {'✔' if medula_var else '✖ (pencere bulunamadı)'}\n"
                f"Hasta Takip: {'✔' if ht_var else '✖'}\n\n"
                f"Program bir sonraki açılışta bu konumlarda açılacak."
            )
            messagebox.showinfo("Yerleşim Kaydedildi", mesaj)
            self.durum_bar.config(text="📐 Pencere yerleşimi kaydedildi.")
        else:
            messagebox.showerror("Hata", "Yerleşim kaydedilemedi (log'a bakın).")

    # -----------------------------------------------------------------
    def _yerlesimi_uygula(self):
        """Kaydedilmiş yerleşimi MEDULA ve Hasta Takip penceresine uygula."""
        try:
            from pencere_yerlesim import (
                yerlesim_yukle, medulaya_uygula, hasta_takibe_uygula,
            )
        except Exception as e:
            messagebox.showerror("Hata", f"pencere_yerlesim modülü yüklenemedi:\n{e}")
            return

        data = yerlesim_yukle()
        if not data:
            messagebox.showwarning(
                "Kayıt Yok",
                "Kaydedilmiş yerleşim bulunamadı.\n\n"
                "Önce pencereleri istediğin yere getir ve "
                "📐 Yerleşimi Kaydet butonuna bas.",
            )
            return

        medula_ok = False
        ht_ok = False
        if "medula" in data:
            try:
                medula_ok = medulaya_uygula()
            except Exception as e:
                logger.error(f"MEDULA'ya yerleşim uygulanamadı: {e}")
        if "hasta_takip" in data:
            try:
                ht_ok = hasta_takibe_uygula(self.root)
            except Exception as e:
                logger.error(f"Hasta Takip'e yerleşim uygulanamadı: {e}")

        parca = []
        if "medula" in data:
            parca.append(f"MEDULA: {'✔' if medula_ok else '✖ (pencere açık değil?)'}")
        if "hasta_takip" in data:
            parca.append(f"Hasta Takip: {'✔' if ht_ok else '✖'}")

        if medula_ok or ht_ok:
            self.durum_bar.config(
                text="📐 Yerleşim uygulandı: " + "  ·  ".join(parca)
            )
        else:
            messagebox.showwarning(
                "Uygulanamadı",
                "Yerleşim uygulanamadı.\n\n" + "\n".join(parca),
            )

    # -----------------------------------------------------------------
    def _kapat(self):
        try:
            from medula_oturum_canli import get_servis
            get_servis().dur()
        except Exception:
            pass
        try:
            if self.db:
                self.db.kapat()
        except Exception:
            pass
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    HastaTakipGUI(root)
    root.mainloop()
