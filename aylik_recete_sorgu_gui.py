"""
Aylik Recete & Rapor Sorgu Modulu (GENISLETILMIS)
Botanik EOS DB'den ay bazli recete sorgulamasi.
GUVENLIK: Yalnizca SELECT — BotanikDB.sorgu_calistir guvenlik filtresi kullanilir.

Gosterilen alanlar:
- Recete: tarih, e-recete, sgk no, protokol no, alt tur, renk, provizyon tipi
- Hasta: ad, TC, DT, yas, cinsiyet, kurum (SGK/yesil kart vs.), kapsam,
         emeklilik, mustehaklik, katilim muaf, yakinlik turu, tel
- Doktor: ad, TC, dip no, dip tes no, tipi, medula, branslari (DoktorBrans)
- Tesis: ad, kod, sinif, basamak
- Recete: branş + reçete branşı
- Ilaclar: RIDoz, tekrar/periyot, bitis, rapor kod, tutar/fark
- Uyarilar: RxUyarilari (regex ile kod cikartma)
- Raporlar: RaporAna + ICD/SUT zinciri + RaporDoktor + RaporEtkinMadde + RaporEkBilgi
- Recete aciklamalari: EReceteAciklamalari + EReceteAciklama + EReceteAciklamaTuru
- Recete tani: ReceteICD + ReceteTeshis
- Hasta gecmisi: son 6 ay tum receteler
"""

import logging
import re
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)


UYARI_KODU_REGEX = re.compile(r"\((\d{3,7})\)")


def uyari_kodlarini_ayikla(metin: str) -> list:
    if not metin:
        return []
    return list(dict.fromkeys(UYARI_KODU_REGEX.findall(metin)))


def yas_hesapla(dogum_tarihi) -> str:
    if not dogum_tarihi:
        return "—"
    try:
        if hasattr(dogum_tarihi, 'year'):
            dt = dogum_tarihi
        else:
            return "—"
        bugun = date.today()
        yas = bugun.year - dt.year - (
            (bugun.month, bugun.day) < (dt.month, dt.day)
        )
        return str(yas)
    except Exception:
        return "—"


class AylikReceteSorguGUI:

    def __init__(self, root: tk.Tk, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("Aylik Recete & Rapor Sorgu (Botanik EOS)")
        self.root.geometry("1560x900")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        self.db: BotanikDB = None
        self._mevcut_recete_listesi = []
        self._secili_rx_id = None
        self._secili_musteri_id = None

        # Lookup cache
        self._lookup_kurum = {}        # {KurumId: KurumAdi}
        self._lookup_kapsam = {}       # {KapsamId: KapsamAdi}
        self._lookup_provizyon = {}    # {ProvizyonTipId: ProvizyonTipAdi}
        self._lookup_alttur = {}       # {ReceteAltTuruId: ReceteAltTuruAdi}
        self._lookup_renk = {}         # {ReceteRenkId: ReceteRenkAdi}
        self._lookup_brans = {}        # {BransId: BransAdi}
        self._lookup_etkin_madde = {}  # {EtkinMaddeId: (sgkkod, ad)}
        self._lookup_kullanim = {}     # {KullanimId: KullanimSekli}
        self._lookup_birim = {}        # {BirimId: BirimAdi}
        self._lookup_rapor_turu = {}   # {RaporTuruId: RaporTuruAdi}
        self._lookup_rapor_kodu = {}   # {RaporKodId: (RaporKodu, RaporKodAciklama)}

        # Yakinlik turu (manuel eslestirme — DB'de YakinlikTuru tablosu var ama kucuk)
        self._yakinlik = {0: "—", 1: "Sigortalı", 2: "Eş",
                           3: "Çocuk", 4: "Anne/Baba", 5: "Diğer"}
        self._cinsiyet = {"E": "Erkek", "K": "Kadın", " ": "—", "B": "Belirsiz"}
        self._periyot = {1: "günde", 2: "haftada", 3: "ayda", 4: "yılda"}

        self.root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._arayuz_olustur()
        self._db_baglan()
        self._lookup_yukle()
        self._ay_listesini_yukle()

    # ------------------------------------------------------------------ DB
    def _db_baglan(self):
        try:
            self.db = BotanikDB(production=True)
            if not self.db.baglan():
                raise RuntimeError("Botanik veritabanina baglanilamadi")
            self._durum_yaz("Veritabanina baglandi (salt-okunur).")
        except Exception as e:
            logger.error("DB baglanti hatasi: %s", e)
            messagebox.showerror(
                "Baglanti Hatasi",
                f"Botanik EOS veritabanina baglanilamadi:\n{e}",
            )

    def _lookup_yukle(self):
        """Sik kullanilan lookup tablolarini bir defa yukle."""
        if not self.db:
            return
        try:
            for r in self.db.sorgu_calistir("SELECT KurumId, KurumAdi FROM Kurum WHERE KurumSilme=0"):
                self._lookup_kurum[r["KurumId"]] = r["KurumAdi"]
            for r in self.db.sorgu_calistir("SELECT KapsamId, KapsamAdi FROM Kapsam"):
                self._lookup_kapsam[r["KapsamId"]] = r["KapsamAdi"]
            for r in self.db.sorgu_calistir("SELECT ProvizyonTipId, ProvizyonTipAdi FROM ProvizyonTipi WHERE ProvizyonTipSilme=0"):
                self._lookup_provizyon[r["ProvizyonTipId"]] = r["ProvizyonTipAdi"]
            for r in self.db.sorgu_calistir("SELECT ReceteAltTuruId, ReceteAltTuruAdi FROM ReceteAltTuru WHERE ReceteAltTuruSilme=0"):
                self._lookup_alttur[r["ReceteAltTuruId"]] = r["ReceteAltTuruAdi"]
            for r in self.db.sorgu_calistir("SELECT ReceteRenkId, ReceteRenkAdi FROM ReceteRenk WHERE ReceteRenkSilme=0"):
                self._lookup_renk[r["ReceteRenkId"]] = r["ReceteRenkAdi"]
            for r in self.db.sorgu_calistir("SELECT BransId, BransAdi FROM Brans WHERE BransSilme=0"):
                self._lookup_brans[r["BransId"]] = r["BransAdi"]
            for r in self.db.sorgu_calistir("SELECT EtkinMaddeId, EtkinMaddeSGKKodu, EtkinMaddeAdi FROM EtkinMadde WHERE EtkinMaddeSilme=0"):
                self._lookup_etkin_madde[r["EtkinMaddeId"]] = (
                    r["EtkinMaddeSGKKodu"] or "", r["EtkinMaddeAdi"] or ""
                )
            for r in self.db.sorgu_calistir("SELECT KullanimId, KullanimSekli FROM Kullanim WHERE KullanimSilme=0"):
                self._lookup_kullanim[r["KullanimId"]] = r["KullanimSekli"]
            for r in self.db.sorgu_calistir("SELECT BirimId, BirimAdi FROM Birim WHERE BirimSilme=0"):
                self._lookup_birim[r["BirimId"]] = r["BirimAdi"]
            for r in self.db.sorgu_calistir("SELECT RaporTuruId, RaporTuruAdi FROM RaporTuru WHERE RaporTuruSilme=0"):
                self._lookup_rapor_turu[r["RaporTuruId"]] = r["RaporTuruAdi"]
            for r in self.db.sorgu_calistir("SELECT RaporKodId, RaporKodu, RaporKodAciklama FROM RaporKodlari WHERE RaporKodSilme=0"):
                self._lookup_rapor_kodu[r["RaporKodId"]] = (
                    r["RaporKodu"] or "", r["RaporKodAciklama"] or ""
                )
            self._durum_yaz(
                f"Lookup'lar yuklendi: {len(self._lookup_kurum)} kurum, "
                f"{len(self._lookup_kapsam)} kapsam, {len(self._lookup_brans)} brans, "
                f"{len(self._lookup_etkin_madde)} etkin madde, "
                f"{len(self._lookup_rapor_kodu)} rapor kodu."
            )
        except Exception as e:
            logger.exception("Lookup yukleme hatasi: %s", e)
            self._durum_yaz(f"Lookup yukleme hatasi: {e}")

    def _doktor_branslarini_getir(self, doktor_idleri: list) -> dict:
        """Bir doktor ID listesi icin DoktorBrans junction'dan branş adlarını getir."""
        if not doktor_idleri:
            return {}
        try:
            ph = ",".join("?" * len(doktor_idleri))
            rows = self.db.sorgu_calistir(
                f"""SELECT DoktorBransDoktorId, DoktorBransBransId
                    FROM DoktorBrans WHERE DoktorBransDoktorId IN ({ph})""",
                tuple(doktor_idleri),
            )
            result = {}
            for r in rows:
                did = r["DoktorBransDoktorId"]
                brans_ad = self._lookup_brans.get(r["DoktorBransBransId"], "?")
                result.setdefault(did, []).append(brans_ad)
            return {k: ", ".join(v) for k, v in result.items()}
        except Exception as e:
            logger.warning("Doktor branş alinamadi: %s", e)
            return {}

    # --------------------------------------------------------------- LAYOUT
    def _arayuz_olustur(self):
        ust = tk.Frame(self.root, bg="#263238", height=50)
        ust.pack(fill="x")
        tk.Label(
            ust, text="📋 Aylik Recete & Rapor Sorgu (Botanik EOS — Salt Okunur)",
            font=("Arial", 13, "bold"), bg="#263238", fg="white",
        ).pack(side="left", padx=15, pady=10)
        tk.Button(
            ust, text="Ana Menuye Don", command=self._kapat,
            bg="#455A64", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=15, pady=10)

        filtre = tk.Frame(self.root, bg="#ECEFF1", pady=8)
        filtre.pack(fill="x", padx=10)

        tk.Label(filtre, text="Yıl:", bg="#ECEFF1").pack(side="left", padx=(8, 2))
        self.var_yil = tk.StringVar()
        self.cb_yil = ttk.Combobox(filtre, textvariable=self.var_yil,
                                    width=6, state="readonly")
        self.cb_yil.pack(side="left", padx=2)
        self.cb_yil.bind("<<ComboboxSelected>>", self._yil_degisti)

        tk.Label(filtre, text="Ay:", bg="#ECEFF1").pack(side="left", padx=(10, 2))
        self.var_ay = tk.StringVar()
        self.cb_ay = ttk.Combobox(filtre, textvariable=self.var_ay,
                                   width=12, state="readonly")
        self.cb_ay.pack(side="left", padx=2)

        tk.Label(filtre, text="Arama:", bg="#ECEFF1").pack(side="left", padx=(20, 2))
        self.var_arama = tk.StringVar()
        ent = tk.Entry(filtre, textvariable=self.var_arama, width=28)
        ent.pack(side="left", padx=2)
        ent.bind("<Return>", lambda e: self._receteleri_sorgula())

        self.var_sadece_raporlu = tk.BooleanVar(value=False)
        tk.Checkbutton(filtre, text="Raporlu", bg="#ECEFF1",
                       variable=self.var_sadece_raporlu,
                       command=self._receteleri_sorgula).pack(side="left", padx=10)

        self.var_sadece_uyarili = tk.BooleanVar(value=False)
        tk.Checkbutton(filtre, text="Uyarılı", bg="#ECEFF1",
                       variable=self.var_sadece_uyarili,
                       command=self._receteleri_sorgula).pack(side="left", padx=2)

        tk.Button(filtre, text="🔍 Sorgula", bg="#1976D2", fg="white",
                  command=self._receteleri_sorgula, padx=14, bd=0).pack(side="left", padx=15)

        self.lbl_sayim = tk.Label(filtre, text="", bg="#ECEFF1", fg="#37474F")
        self.lbl_sayim.pack(side="left", padx=10)

        ana = tk.PanedWindow(self.root, orient="horizontal", sashwidth=6,
                             bg="#CFD8DC")
        ana.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        sol = tk.Frame(ana, bg="white")
        ana.add(sol, minsize=620)
        self._recete_listesi_kur(sol)

        sag = tk.Frame(ana, bg="white")
        ana.add(sag, minsize=700)
        self._detay_paneli_kur(sag)

        self._durum_frame = tk.Frame(self.root, bg="#ECEFF1")
        self._durum_frame.pack(fill="x", side="bottom")
        self.durum_bar = tk.Label(
            self._durum_frame, text="Hazır", anchor="w",
            bg="#ECEFF1", fg="#37474F", padx=10,
        )
        self.durum_bar.pack(fill="x", side="left", expand=True)

    def _recete_listesi_kur(self, parent):
        tk.Label(parent, text="Reçete Listesi", bg="white",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=8, pady=4)

        tree_frame = tk.Frame(parent, bg="white")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        kolonlar = ("tarih", "erecete", "hasta", "doktor", "tesis", "kurum",
                    "ilac_say", "rapor_say", "uyari_say", "tutar")
        self.tv_recete = ttk.Treeview(tree_frame, columns=kolonlar,
                                       show="headings", selectmode="browse",
                                       height=22)
        basliklar = {
            "tarih": ("Tarih", 88),
            "erecete": ("E-Reçete", 78),
            "hasta": ("Hasta", 170),
            "doktor": ("Doktor", 140),
            "tesis": ("Tesis", 180),
            "kurum": ("Kurum", 90),
            "ilac_say": ("İlç", 38),
            "rapor_say": ("Rp", 35),
            "uyari_say": ("Uyr", 35),
            "tutar": ("Tutar", 70),
        }
        for k, (b, w) in basliklar.items():
            self.tv_recete.heading(k, text=b)
            self.tv_recete.column(k, width=w, anchor="w" if k in
                                  ("hasta", "doktor", "tesis", "kurum") else "center")

        vbar = ttk.Scrollbar(tree_frame, orient="vertical",
                              command=self.tv_recete.yview)
        self.tv_recete.configure(yscrollcommand=vbar.set)
        self.tv_recete.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        self.tv_recete.bind("<<TreeviewSelect>>", self._recete_secildi)

        self.tv_recete.tag_configure("uyarili", background="#FFEBEE")
        self.tv_recete.tag_configure("raporlu", background="#E8F5E9")

    def _detay_paneli_kur(self, parent):
        ozet = tk.Frame(parent, bg="#F5F5F5", relief="ridge", bd=1)
        ozet.pack(fill="x", padx=8, pady=(8, 4))

        self.lbl_ozet_baslik = tk.Label(
            ozet, text="Reçete seçin", bg="#F5F5F5",
            font=("Arial", 11, "bold"), anchor="w",
        )
        self.lbl_ozet_baslik.pack(fill="x", padx=8, pady=(6, 2))

        self.lbl_ozet_detay = tk.Label(
            ozet, text="", bg="#F5F5F5", anchor="w", justify="left",
            font=("Consolas", 9),
        )
        self.lbl_ozet_detay.pack(fill="x", padx=8, pady=(0, 6))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.tab_hasta = self._tab_hasta_kur()
        self.tab_ilaclar = self._tab_ilaclar_kur()
        self.tab_uyarilar = self._tab_uyarilar_kur()
        self.tab_raporlar = self._tab_raporlar_kur()
        self.tab_recete_aciklama = self._tab_recete_aciklama_kur()
        self.tab_recete_icd = self._tab_recete_icd_kur()
        self.tab_gecmis = self._tab_gecmis_kur()

        self.notebook.add(self.tab_hasta, text="👤 Hasta")
        self.notebook.add(self.tab_ilaclar, text="💊 İlaçlar")
        self.notebook.add(self.tab_uyarilar, text="⚠ Uyarılar")
        self.notebook.add(self.tab_raporlar, text="📑 Raporlar + ICD + Doz")
        self.notebook.add(self.tab_recete_aciklama, text="📝 Reçete Açıklama")
        self.notebook.add(self.tab_recete_icd, text="🔬 Reçete Tanı")
        self.notebook.add(self.tab_gecmis, text="📅 Hasta Geçmişi")

    def _tab_hasta_kur(self):
        f = tk.Frame(self.notebook, bg="white")
        self.txt_hasta = tk.Text(f, wrap="word", font=("Consolas", 10),
                                   bg="#FAFAFA", state="disabled", height=20)
        vbar = ttk.Scrollbar(f, orient="vertical", command=self.txt_hasta.yview)
        self.txt_hasta.configure(yscrollcommand=vbar.set)
        self.txt_hasta.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")
        return f

    def _tab_ilaclar_kur(self):
        f = tk.Frame(self.notebook, bg="white")
        kolonlar = ("ilac", "adet", "doz", "tekrar", "bitis",
                    "rapor_kod", "tutar", "fark")
        tv = ttk.Treeview(f, columns=kolonlar, show="headings", height=12)
        basliklar = {
            "ilac": ("İlaç Adı", 280),
            "adet": ("Adet", 50),
            "doz": ("Doz", 70),
            "tekrar": ("Tekrar", 110),
            "bitis": ("Bitiş", 95),
            "rapor_kod": ("Rapor Kod", 130),
            "tutar": ("Tutar", 80),
            "fark": ("Fark", 70),
        }
        for k, (b, w) in basliklar.items():
            tv.heading(k, text=b)
            tv.column(k, width=w, anchor="w" if k == "ilac" else "center")
        vbar = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vbar.set)
        tv.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")
        tv.tag_configure("raporlu", background="#E8F5E9")
        self.tv_ilaclar = tv
        return f

    def _tab_uyarilar_kur(self):
        f = tk.Frame(self.notebook, bg="white")

        ust_f = tk.Frame(f, bg="#FFF8E1")
        ust_f.pack(fill="x", padx=4, pady=(4, 0))
        tk.Label(ust_f, text="Tespit edilen uyarı kodları:",
                 bg="#FFF8E1", font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=2)
        self.lbl_uyari_kodlari = tk.Label(
            ust_f, text="—", bg="#FFF8E1", fg="#D32F2F",
            font=("Consolas", 11, "bold"), anchor="w",
        )
        self.lbl_uyari_kodlari.pack(fill="x", padx=4, pady=(0, 4))

        text_f = tk.Frame(f, bg="white")
        text_f.pack(fill="both", expand=True, padx=4, pady=4)

        self.txt_uyarilar = tk.Text(text_f, wrap="word", font=("Consolas", 9),
                                     bg="#FAFAFA", state="disabled")
        vbar = ttk.Scrollbar(text_f, orient="vertical",
                              command=self.txt_uyarilar.yview)
        self.txt_uyarilar.configure(yscrollcommand=vbar.set)
        self.txt_uyarilar.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        return f

    def _tab_raporlar_kur(self):
        f = tk.Frame(self.notebook, bg="white")

        # Üst: rapor listesi
        list_f = tk.Frame(f, bg="white")
        list_f.pack(fill="x", padx=4, pady=4)
        tk.Label(list_f, text="Hastanın Raporları (en yeni üstte):",
                 bg="white", font=("Arial", 9, "bold")).pack(anchor="w")

        kolonlar = ("rapor_no", "tarih", "tur", "tesis",
                    "doktor", "doktor_brans", "icd_say", "kod_say")
        tv_r = ttk.Treeview(list_f, columns=kolonlar, show="headings", height=7)
        for k, (b, w) in {
            "rapor_no": ("Rapor No", 80),
            "tarih": ("Tarih", 85),
            "tur": ("Tür", 110),
            "tesis": ("Tesis", 200),
            "doktor": ("Rapor Doktoru", 140),
            "doktor_brans": ("Doktor Branşı", 140),
            "icd_say": ("ICD#", 45),
            "kod_say": ("SUT#", 45),
        }.items():
            tv_r.heading(k, text=b)
            tv_r.column(k, width=w,
                         anchor="w" if k in ("tur", "tesis", "doktor", "doktor_brans") else "center")
        vbar = ttk.Scrollbar(list_f, orient="vertical", command=tv_r.yview)
        tv_r.configure(yscrollcommand=vbar.set)
        tv_r.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self.tv_raporlar = tv_r
        tv_r.bind("<<TreeviewSelect>>", self._rapor_secildi)

        # Alt: 3 panel — ICD/Kod | Etken Madde+Doz | Açıklama+EkBilgi
        alt_split = tk.PanedWindow(f, orient="horizontal", sashwidth=4,
                                    bg="#CFD8DC")
        alt_split.pack(fill="both", expand=True, padx=4, pady=4)

        # Sol: ICD/SUT kod
        sol_f = tk.Frame(alt_split, bg="white")
        alt_split.add(sol_f, minsize=300)
        tk.Label(sol_f, text="ICD + SUT Kodları:", bg="white",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=2)
        kol_icd = ("icd_kodu", "icd_aciklama", "rapor_kod", "baslangic", "bitis")
        tv_i = ttk.Treeview(sol_f, columns=kol_icd, show="headings", height=8)
        for k, (b, w) in {
            "icd_kodu": ("ICD", 60),
            "icd_aciklama": ("ICD Adı", 160),
            "rapor_kod": ("SUT", 80),
            "baslangic": ("Baş", 75),
            "bitis": ("Bit", 75),
        }.items():
            tv_i.heading(k, text=b)
            tv_i.column(k, width=w, anchor="w" if "Adı" in b else "center")
        vbar2 = ttk.Scrollbar(sol_f, orient="vertical", command=tv_i.yview)
        tv_i.configure(yscrollcommand=vbar2.set)
        tv_i.pack(side="left", fill="both", expand=True)
        vbar2.pack(side="right", fill="y")
        self.tv_icd = tv_i

        # Orta: Etken Madde + Rapor Dozu
        orta_f = tk.Frame(alt_split, bg="white")
        alt_split.add(orta_f, minsize=280)
        tk.Label(orta_f, text="Rapor Etken Madde + Doz:", bg="white",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=2)
        kol_em = ("etken", "doz", "tekrar", "kullanim")
        tv_em = ttk.Treeview(orta_f, columns=kol_em, show="headings", height=8)
        for k, (b, w) in {
            "etken": ("Etken Madde", 180),
            "doz": ("Doz", 70),
            "tekrar": ("Tekrar/Periyot", 110),
            "kullanim": ("Kullanım", 100),
        }.items():
            tv_em.heading(k, text=b)
            tv_em.column(k, width=w, anchor="w" if k in ("etken", "kullanim") else "center")
        vbar4 = ttk.Scrollbar(orta_f, orient="vertical", command=tv_em.yview)
        tv_em.configure(yscrollcommand=vbar4.set)
        tv_em.pack(side="left", fill="both", expand=True)
        vbar4.pack(side="right", fill="y")
        self.tv_etken_madde = tv_em

        # Sağ: Açıklama + Ek Bilgi
        sag_f = tk.Frame(alt_split, bg="white")
        alt_split.add(sag_f, minsize=260)

        tk.Label(sag_f, text="Rapor Açıklaması:", bg="white",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=2)
        self.txt_rapor_aciklama = tk.Text(sag_f, wrap="word",
                                           font=("Arial", 9),
                                           bg="#FAFAFA", state="disabled",
                                           height=8)
        vbar3 = ttk.Scrollbar(sag_f, orient="vertical",
                               command=self.txt_rapor_aciklama.yview)
        self.txt_rapor_aciklama.configure(yscrollcommand=vbar3.set)
        self.txt_rapor_aciklama.pack(fill="both", expand=True, padx=2)

        tk.Label(sag_f, text="Rapor Ek Bilgileri (Lab/Klinik):",
                 bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=(6, 2))
        kol_eb = ("turu", "deger", "tarih")
        tv_eb = ttk.Treeview(sag_f, columns=kol_eb, show="headings", height=4)
        for k, (b, w) in {
            "turu": ("Tür", 130),
            "deger": ("Değer", 80),
            "tarih": ("Tarih", 100),
        }.items():
            tv_eb.heading(k, text=b)
            tv_eb.column(k, width=w, anchor="w" if k == "turu" else "center")
        tv_eb.pack(fill="x", padx=2, pady=(0, 4))
        self.tv_ek_bilgi = tv_eb
        return f

    def _tab_recete_aciklama_kur(self):
        f = tk.Frame(self.notebook, bg="white")
        tk.Label(f, text="Reçete Açıklamaları (Hekim notları, EReceteAciklamalari):",
                 bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=4)
        kol = ("turu", "aciklama")
        tv = ttk.Treeview(f, columns=kol, show="headings", height=14)
        for k, (b, w) in {
            "turu": ("Açıklama Türü", 200),
            "aciklama": ("Açıklama", 700),
        }.items():
            tv.heading(k, text=b)
            tv.column(k, width=w, anchor="w")
        vbar = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vbar.set)
        tv.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")
        self.tv_recete_aciklama = tv
        return f

    def _tab_recete_icd_kur(self):
        f = tk.Frame(self.notebook, bg="white")
        kol = ("kaynak", "icd_kodu", "icd_aciklama")
        tv = ttk.Treeview(f, columns=kol, show="headings", height=10)
        for k, (b, w) in {
            "kaynak": ("Kaynak", 130),
            "icd_kodu": ("ICD Kodu", 100),
            "icd_aciklama": ("ICD Açıklaması", 500),
        }.items():
            tv.heading(k, text=b)
            tv.column(k, width=w, anchor="w" if k == "icd_aciklama" else "center")
        vbar = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vbar.set)
        tv.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")
        self.tv_recete_icd = tv
        return f

    def _tab_gecmis_kur(self):
        f = tk.Frame(self.notebook, bg="white")
        kol = ("tarih", "erecete", "ilac", "adet", "doz", "rapor_kod")
        tv = ttk.Treeview(f, columns=kol, show="headings", height=14)
        for k, (b, w) in {
            "tarih": ("Tarih", 100),
            "erecete": ("E-Reçete", 80),
            "ilac": ("İlaç Adı", 320),
            "adet": ("Adet", 50),
            "doz": ("Doz", 60),
            "rapor_kod": ("Rapor Kod ID", 100),
        }.items():
            tv.heading(k, text=b)
            tv.column(k, width=w, anchor="w" if k == "ilac" else "center")
        vbar = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vbar.set)
        tv.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        vbar.pack(side="right", fill="y")
        self.tv_gecmis = tv
        return f

    # -------------------------------------------------------------- LOGIC
    def _ay_listesini_yukle(self):
        if not self.db:
            return
        try:
            rows = self.db.sorgu_calistir(
                "SELECT DISTINCT YEAR(RxKayitTarihi) AS Y FROM ReceteAna "
                "WHERE RxSilme=0 AND RxKayitTarihi IS NOT NULL "
                "ORDER BY Y DESC"
            )
            yillar = [str(r["Y"]) for r in rows if r.get("Y")]
            self.cb_yil["values"] = yillar
            if yillar:
                bugun = date.today()
                hedef = str(bugun.year)
                self.var_yil.set(hedef if hedef in yillar else yillar[0])
                self._yil_degisti()
                self.var_ay.set(self._ay_etiketi(bugun.month))
        except Exception as e:
            logger.exception("Yil listesi yuklenemedi: %s", e)
            self._durum_yaz(f"Yil listesi yuklenemedi: {e}")

    def _ay_etiketi(self, ay_no: int) -> str:
        adlar = ["", "01-Ocak", "02-Şubat", "03-Mart", "04-Nisan",
                 "05-Mayıs", "06-Haziran", "07-Temmuz", "08-Ağustos",
                 "09-Eylül", "10-Ekim", "11-Kasım", "12-Aralık"]
        if 1 <= ay_no <= 12:
            return adlar[ay_no]
        return ""

    def _ay_no_cek(self, etiket: str) -> int:
        if etiket and "-" in etiket:
            try:
                return int(etiket.split("-")[0])
            except ValueError:
                return 0
        return 0

    def _yil_degisti(self, *args):
        self.cb_ay["values"] = [self._ay_etiketi(i) for i in range(1, 13)]

    def _periyot_str(self, tekrar, aralik, periyot_id):
        per_ad = self._periyot.get(periyot_id, "?")
        try:
            t = int(tekrar) if tekrar else 0
            a = int(aralik) if aralik else 0
            return f"{a} {per_ad} {t}×"
        except Exception:
            return "—"

    # ----- recete sorgu (ana liste) -----
    def _receteleri_sorgula(self):
        if not self.db:
            return
        yil = self.var_yil.get()
        ay = self._ay_no_cek(self.var_ay.get())
        if not yil or not ay:
            self._durum_yaz("Yıl ve ay seçiniz")
            return
        arama = self.var_arama.get().strip()
        sadece_raporlu = self.var_sadece_raporlu.get()
        sadece_uyarili = self.var_sadece_uyarili.get()

        self._durum_yaz(f"{yil}-{ay:02d} sorgulanıyor...")
        self.tv_recete.delete(*self.tv_recete.get_children())
        self.lbl_sayim.config(text="...")

        threading.Thread(
            target=self._sorgu_threadi,
            args=(int(yil), ay, arama, sadece_raporlu, sadece_uyarili),
            daemon=True,
        ).start()

    def _sorgu_threadi(self, yil, ay, arama, sadece_raporlu, sadece_uyarili):
        try:
            sql = """
                SELECT ra.RxId, ra.RxEReceteNo, ra.RxSgkIslemNo, ra.RxProtokolNo,
                       ra.RxReceteTarihi, ra.RxIslemTarihi, ra.RxKayitTarihi,
                       ra.RxBransId, ra.RxReceteRenkId, ra.RxReceteAltTuruId,
                       ra.RxProvizyonTipId, ra.RxReceteTipi, ra.RxKurumId,
                       ra.RxMusteriId, ra.RxDoktorId, ra.RxHastaneId,
                       m.MusteriAdiSoyadi, m.MusteriTCKN, m.MusteriDogumTarihi,
                       m.MusteriCinsiyet, m.MusteriEmeklilik, m.MusteriMustehaklik,
                       m.MusteriKatilimMuaf, m.MusteriYakinlikTuru,
                       m.MusteriKapsamId, m.MusteriKurumId,
                       m.MusteriTelCep, m.MusteriAdresi,
                       d.DoktorAdiSoyadi, d.DoktorTCKN, d.DoktorDipNo,
                       d.DoktorDipTesNo, d.DoktorTipi, d.DoktorMedula,
                       h.HastaneAdi, h.HastaneKodu, h.HastaneSinifKodu,
                       h.HastaneBasamak, h.HastaneBasamakNo,
                       (SELECT COUNT(*) FROM RxUyarilari u WHERE u.RxId=ra.RxId) AS UyariSayisi,
                       (SELECT COUNT(*) FROM ReceteIlaclari ri
                          WHERE ri.RIRxId=ra.RxId AND ri.RIRaporKodId>0
                                AND ri.RISilme=0) AS RaporluIlacSayisi,
                       (SELECT COUNT(*) FROM ReceteIlaclari ri
                          WHERE ri.RIRxId=ra.RxId AND ri.RISilme=0) AS IlacSayisi,
                       (SELECT SUM(ri.RIToplam) FROM ReceteIlaclari ri
                          WHERE ri.RIRxId=ra.RxId AND ri.RISilme=0) AS Tutar
                FROM ReceteAna ra
                LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
                LEFT JOIN Doktor d ON d.DoktorId = ra.RxDoktorId
                LEFT JOIN Hastane h ON h.HastaneId = ra.RxHastaneId
                WHERE ra.RxSilme = 0
                  AND YEAR(ra.RxKayitTarihi) = ?
                  AND MONTH(ra.RxKayitTarihi) = ?
            """
            params = [yil, ay]
            if arama:
                arama_p = f"%{arama}%"
                sql += (" AND (m.MusteriAdiSoyadi LIKE ? "
                        "OR ra.RxEReceteNo LIKE ? OR ra.RxSgkIslemNo LIKE ? "
                        "OR m.MusteriTCKN LIKE ?)")
                params.extend([arama_p, arama_p, arama_p, arama_p])
            sql += " ORDER BY ra.RxIslemTarihi DESC"

            rows = self.db.sorgu_calistir(sql, tuple(params))

            if sadece_raporlu:
                rows = [r for r in rows if (r.get("RaporluIlacSayisi") or 0) > 0]
            if sadece_uyarili:
                rows = [r for r in rows if (r.get("UyariSayisi") or 0) > 0]

            doktor_idleri = list({r["RxDoktorId"] for r in rows if r.get("RxDoktorId")})
            doktor_brans = self._doktor_branslarini_getir(doktor_idleri)
            for r in rows:
                r["DoktorBranslari"] = doktor_brans.get(r.get("RxDoktorId"), "")

            self.root.after(0, self._sorgu_sonuc_doldur, rows)
        except Exception as e:
            logger.exception("Sorgu hatasi: %s", e)
            self.root.after(0, self._durum_yaz, f"Sorgu hatasi: {e}")

    def _sorgu_sonuc_doldur(self, rows):
        self._mevcut_recete_listesi = rows
        for r in rows:
            tarih = r.get("RxIslemTarihi") or r.get("RxReceteTarihi")
            tarih_str = tarih.strftime("%d.%m.%Y") if tarih else "—"
            tutar = r.get("Tutar") or 0
            tutar_str = f"{float(tutar):.2f}" if tutar else "0.00"

            uyari = r.get("UyariSayisi") or 0
            rapor = r.get("RaporluIlacSayisi") or 0
            tags = []
            if uyari > 0:
                tags.append("uyarili")
            elif rapor > 0:
                tags.append("raporlu")

            kurum_ad = self._lookup_kurum.get(r.get("RxKurumId"), "—")

            self.tv_recete.insert(
                "", "end",
                iid=str(r["RxId"]),
                values=(
                    tarih_str,
                    r.get("RxEReceteNo") or "",
                    r.get("MusteriAdiSoyadi") or "",
                    r.get("DoktorAdiSoyadi") or "",
                    (r.get("HastaneAdi") or "")[:50],
                    kurum_ad[:25],
                    r.get("IlacSayisi") or 0,
                    rapor,
                    uyari,
                    tutar_str,
                ),
                tags=tags,
            )
        toplam_tutar = sum(float(r.get("Tutar") or 0) for r in rows)
        self.lbl_sayim.config(
            text=f"{len(rows)} reçete  |  Toplam: {toplam_tutar:,.2f} TL"
        )
        self._durum_yaz(f"{len(rows)} reçete listelendi.")

    # ----- recete secildi -> detay -----
    def _recete_secildi(self, event=None):
        sec = self.tv_recete.selection()
        if not sec:
            return
        rx_id = int(sec[0])
        self._secili_rx_id = rx_id
        recete = next((r for r in self._mevcut_recete_listesi
                       if r["RxId"] == rx_id), None)
        if not recete:
            return
        self._secili_musteri_id = recete.get("RxMusteriId")
        self._ozet_doldur(recete)
        self._hasta_paneli_doldur(recete)
        threading.Thread(target=self._detay_yukle_thread,
                          args=(rx_id, recete.get("RxMusteriId"),
                                recete.get("RxEReceteNo")),
                          daemon=True).start()

    def _ozet_doldur(self, r):
        tarih = r.get("RxIslemTarihi") or r.get("RxReceteTarihi")
        tarih_str = tarih.strftime("%d.%m.%Y %H:%M") if tarih else "—"
        rec_tarih = r.get("RxReceteTarihi")
        rec_tarih_str = rec_tarih.strftime("%d.%m.%Y") if rec_tarih else "—"

        baslik = (f"{r.get('MusteriAdiSoyadi') or '?'}   "
                  f"E-Reçete: {r.get('RxEReceteNo') or '—'}   "
                  f"SGK No: {r.get('RxSgkIslemNo') or '—'}   "
                  f"Protokol: {(r.get('RxProtokolNo') or '').strip() or '—'}")

        renk = self._lookup_renk.get(r.get("RxReceteRenkId"), "—")
        alttur = self._lookup_alttur.get(r.get("RxReceteAltTuruId"), "—")
        provizyon = self._lookup_provizyon.get(r.get("RxProvizyonTipId"), "—")
        rec_brans = self._lookup_brans.get(r.get("RxBransId"), "—")
        kurum = self._lookup_kurum.get(r.get("RxKurumId"), "—")
        dok_brans = r.get("DoktorBranslari") or "—"

        detay = (
            f"İşlem Tarihi: {tarih_str}    Reçete Tarihi: {rec_tarih_str}    "
            f"Renk: {renk}    Alt Tür: {alttur}    Provizyon: {provizyon}    "
            f"Kurum: {kurum}\n"
            f"Doktor: {r.get('DoktorAdiSoyadi') or '—'}    "
            f"Branş(genel): {dok_brans}    "
            f"Reçete Branşı: {rec_brans}    "
            f"Dip No: {r.get('DoktorDipNo') or '—'}\n"
            f"Tesis: {r.get('HastaneAdi') or '—'} "
            f"(Kod: {r.get('HastaneKodu') or '—'})    "
            f"İlaç: {r.get('IlacSayisi') or 0}  |  "
            f"Raporlu: {r.get('RaporluIlacSayisi') or 0}  |  "
            f"Uyarı: {r.get('UyariSayisi') or 0}"
        )
        self.lbl_ozet_baslik.config(text=baslik)
        self.lbl_ozet_detay.config(text=detay)

    def _hasta_paneli_doldur(self, r):
        dt = r.get("MusteriDogumTarihi")
        dt_str = dt.strftime("%d.%m.%Y") if dt else "—"
        yas = yas_hesapla(dt)
        cinsiyet = self._cinsiyet.get((r.get("MusteriCinsiyet") or "").strip() or " ", "—")
        kurum_recete = self._lookup_kurum.get(r.get("RxKurumId"), "—")
        kurum_kayit = self._lookup_kurum.get(r.get("MusteriKurumId"), "—")
        kapsam = self._lookup_kapsam.get(r.get("MusteriKapsamId"), "—")
        yakinlik = self._yakinlik.get(r.get("MusteriYakinlikTuru") or 0, "—")
        emekli = "Evet" if r.get("MusteriEmeklilik") else "Hayır"
        mustehak = ("Evet" if r.get("MusteriMustehaklik")
                    else ("Hayır" if r.get("MusteriMustehaklik") is False else "—"))
        muaf = ("Evet" if r.get("MusteriKatilimMuaf")
                else ("Hayır" if r.get("MusteriKatilimMuaf") is False else "—"))

        tc = (r.get("MusteriTCKN") or "").strip() or "—"
        tel = (r.get("MusteriTelCep") or "").strip() or "—"
        adres = (r.get("MusteriAdresi") or "").strip() or "—"

        metin = (
            f"════════════════════════════════════════════════════════════════\n"
            f"  HASTA BİLGİLERİ\n"
            f"════════════════════════════════════════════════════════════════\n"
            f"  Ad Soyad      : {r.get('MusteriAdiSoyadi') or '—'}\n"
            f"  TC Kimlik No  : {tc}\n"
            f"  Doğum Tarihi  : {dt_str}    (Yaş: {yas})\n"
            f"  Cinsiyet      : {cinsiyet}\n"
            f"  Telefon       : {tel}\n"
            f"  Adres         : {adres}\n"
            f"\n"
            f"════════════════════════════════════════════════════════════════\n"
            f"  SOSYAL GÜVENLİK / SİGORTA\n"
            f"════════════════════════════════════════════════════════════════\n"
            f"  Bu Reçetedeki Kurum : {kurum_recete}\n"
            f"  Hasta Kayıtlı Kurum : {kurum_kayit}\n"
            f"  Kapsam              : {kapsam}\n"
            f"  Yakınlık Türü       : {yakinlik}\n"
            f"  Emekli              : {emekli}\n"
            f"  Müstahak            : {mustehak}\n"
            f"  Katılım Payından Muaf: {muaf}\n"
        )
        self.txt_hasta.config(state="normal")
        self.txt_hasta.delete("1.0", "end")
        self.txt_hasta.insert("end", metin)
        self.txt_hasta.config(state="disabled")

    def _detay_yukle_thread(self, rx_id, musteri_id, e_recete):
        try:
            ilaclar = self.db.sorgu_calistir(
                """SELECT ri.*, u.UrunAdi
                   FROM ReceteIlaclari ri
                   LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
                   WHERE ri.RIRxId = ? AND ri.RISilme = 0
                   ORDER BY ri.RIId""",
                (rx_id,),
            )

            uyarilar = self.db.sorgu_calistir(
                "SELECT * FROM RxUyarilari WHERE RxId = ? ORDER BY RUId",
                (rx_id,),
            )

            recete_icd = self.db.sorgu_calistir(
                """SELECT ri.ReceteICDICDId, i.ICDKodu, i.ICDAciklamasi,
                          ri.ReceteICDICDAciklama AS DirektAciklama
                   FROM ReceteICD ri
                   LEFT JOIN ICD i ON i.ICDId = ri.ReceteICDICDId
                   WHERE ri.ReceteICDRxId = ? AND ri.ReceteICDSilme = 0""",
                (rx_id,),
            )

            recete_teshis = self.db.sorgu_calistir(
                """SELECT rt.RTTeshisKodu, rt.RTSecilenIlacAdi,
                          i.ICDKodu, i.ICDAciklamasi
                   FROM ReceteTeshis rt
                   LEFT JOIN ICD i ON i.ICDId = rt.RTTeshisId
                   WHERE rt.RTRxId = ?""",
                (rx_id,),
            )

            # Recete açıklamaları (e-recete)
            recete_aciklamalari = []
            try:
                # Once ERecete'den EReceteId'yi bul
                er = self.db.sorgu_calistir(
                    "SELECT EReceteId FROM ERecete WHERE EReceteNo = ?",
                    (e_recete,),
                ) if e_recete else []
                if er:
                    e_id = er[0]["EReceteId"]
                    recete_aciklamalari = self.db.sorgu_calistir(
                        """SELECT eat.EReceteAciklamaTuruAdi, ea.EReceteAciklamaAdi
                           FROM EReceteAciklamalari era
                           LEFT JOIN EReceteAciklamaTuru eat
                                ON eat.EReceteAciklamaTuruId = era.ERAEReceteAciklamaTuruId
                           LEFT JOIN EReceteAciklama ea
                                ON ea.EReceteAciklamaId = era.ERAEReceteAciklamaId
                           WHERE era.ERAEReceteId = ?""",
                        (e_id,),
                    )
            except Exception as e:
                logger.warning("Recete aciklamasi alinamadi: %s", e)

            # Hastanın Raporları + RaporDoktor
            raporlar = []
            zincir_by_rapor = {}
            etken_by_rapor = {}
            ek_bilgi_by_rapor = {}
            doktor_by_rapor = {}
            if musteri_id:
                raporlar = self.db.sorgu_calistir(
                    """SELECT ra.RaporAnaId, ra.RaporAnaRaporNo,
                              ra.RaporAnaRaporTakipNo, ra.RaporAnaProtokolNo,
                              ra.RaporAnaRaporTarihi, ra.RaporAnaRaporTuruId,
                              ra.RaporAnaHastaneId, h.HastaneAdi,
                              ra.RaporAnaAciklamalar
                       FROM RaporAna ra
                       LEFT JOIN Hastane h ON h.HastaneId = ra.RaporAnaHastaneId
                       WHERE ra.RaporAnaMusteriId = ? AND ra.RaporAnaSilme = 0
                       ORDER BY ra.RaporAnaRaporTarihi DESC""",
                    (musteri_id,),
                )
                if raporlar:
                    ids = [r["RaporAnaId"] for r in raporlar]
                    ph = ",".join("?" * len(ids))

                    zincir = self.db.sorgu_calistir(
                        f"""SELECT rrki.RRKIRaporAnaId,
                                   i.ICDKodu, i.ICDAciklamasi,
                                   rrki.RRKIRaporKodId,
                                   rrki.RRKIBaslamaTarihi, rrki.RRKIBitisTarihi
                            FROM RaporRaporKodlariICD rrki
                            LEFT JOIN ICD i ON i.ICDId = rrki.RRKIICDId
                            WHERE rrki.RRKIRaporAnaId IN ({ph})
                              AND rrki.RRKISilme = 0
                            ORDER BY rrki.RRKIRaporAnaId""",
                        tuple(ids),
                    )
                    for z in zincir:
                        zincir_by_rapor.setdefault(
                            z["RRKIRaporAnaId"], []
                        ).append(z)

                    etken = self.db.sorgu_calistir(
                        f"""SELECT * FROM RaporEtkinMadde
                            WHERE EtkinMaddeRaporAnaId IN ({ph})
                              AND EtkinMaddeSilme = 0""",
                        tuple(ids),
                    )
                    for e in etken:
                        etken_by_rapor.setdefault(
                            e["EtkinMaddeRaporAnaId"], []
                        ).append(e)

                    eb = self.db.sorgu_calistir(
                        f"""SELECT * FROM RaporEkBilgi
                            WHERE REBRaporAnaId IN ({ph})""",
                        tuple(ids),
                    )
                    for x in eb:
                        ek_bilgi_by_rapor.setdefault(
                            x["REBRaporAnaId"], []
                        ).append(x)

                    rd = self.db.sorgu_calistir(
                        f"""SELECT rd.RaporDoktorRaporAnaId,
                                   rd.RaporDoktorBransId,
                                   d.DoktorAdiSoyadi, d.DoktorDipNo
                            FROM RaporDoktor rd
                            LEFT JOIN Doktor d ON d.DoktorId = rd.RaporDoktorDoktorId
                            WHERE rd.RaporDoktorRaporAnaId IN ({ph})
                              AND rd.RaporDoktorSilme = 0""",
                        tuple(ids),
                    )
                    for x in rd:
                        doktor_by_rapor.setdefault(
                            x["RaporDoktorRaporAnaId"], []
                        ).append(x)

            gecmis = []
            if musteri_id:
                gecmis = self.db.sorgu_calistir(
                    """SELECT TOP 60 ra.RxIslemTarihi, ra.RxEReceteNo,
                              u.UrunAdi, ri.RIAdet, ri.RIDoz, ri.RIRaporKodId
                       FROM ReceteAna ra
                       JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
                       LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
                       WHERE ra.RxMusteriId = ? AND ra.RxSilme = 0
                         AND ri.RISilme = 0
                         AND ra.RxIslemTarihi >= DATEADD(month, -6, GETDATE())
                       ORDER BY ra.RxIslemTarihi DESC""",
                    (musteri_id,),
                )

            self.root.after(
                0, self._detay_doldur,
                ilaclar, uyarilar, recete_icd, recete_teshis, recete_aciklamalari,
                raporlar, zincir_by_rapor, etken_by_rapor, ek_bilgi_by_rapor,
                doktor_by_rapor, gecmis,
            )
        except Exception as e:
            logger.exception("Detay yukleme hatasi: %s", e)
            self.root.after(0, self._durum_yaz, f"Detay hatasi: {e}")

    def _detay_doldur(self, ilaclar, uyarilar, recete_icd, recete_teshis,
                       recete_aciklamalari, raporlar, zincir_by_rapor,
                       etken_by_rapor, ek_bilgi_by_rapor, doktor_by_rapor, gecmis):
        # İlaçlar
        self.tv_ilaclar.delete(*self.tv_ilaclar.get_children())
        for i in ilaclar:
            tags = []
            rapor_kod = i.get("RIRaporKodId") or 0
            if rapor_kod and rapor_kod > 0:
                tags.append("raporlu")
            tekrar = i.get("RITekrar") or 0
            aralik = i.get("RIAralik") or 0
            tekrar_str = self._periyot_str(tekrar, aralik, i.get("RIPeriyotId"))
            bitis = i.get("RIBitisTarihi")
            bitis_str = bitis.strftime("%d.%m.%Y") if bitis else "—"
            rk_kod, _ = self._lookup_rapor_kodu.get(rapor_kod, ("—", ""))
            rapor_kod_str = rk_kod if rk_kod else (str(rapor_kod) if rapor_kod else "—")
            self.tv_ilaclar.insert(
                "", "end",
                values=(
                    i.get("UrunAdi") or f"#{i.get('RIUrunId')}",
                    i.get("RIAdet") or 0,
                    i.get("RIDoz") or "",
                    tekrar_str,
                    bitis_str,
                    rapor_kod_str,
                    f"{float(i.get('RIToplam') or 0):.2f}",
                    f"{float(i.get('RIFiyatFarki') or 0):.2f}",
                ),
                tags=tags,
            )

        # Uyarılar
        self.txt_uyarilar.config(state="normal")
        self.txt_uyarilar.delete("1.0", "end")
        kodlar = []
        for u in uyarilar:
            metin = u.get("RUAciklama") or ""
            kodlar.extend(uyari_kodlarini_ayikla(metin))
            self.txt_uyarilar.insert("end", f"• {metin}\n\n")
        self.txt_uyarilar.config(state="disabled")
        kodlar_uniq = list(dict.fromkeys(kodlar))
        self.lbl_uyari_kodlari.config(
            text=", ".join(kodlar_uniq) if kodlar_uniq else "—"
        )

        # Reçete açıklamaları
        self.tv_recete_aciklama.delete(*self.tv_recete_aciklama.get_children())
        for ra in recete_aciklamalari:
            self.tv_recete_aciklama.insert(
                "", "end",
                values=(
                    ra.get("EReceteAciklamaTuruAdi") or "—",
                    ra.get("EReceteAciklamaAdi") or "—",
                ),
            )

        # Reçete tanı
        self.tv_recete_icd.delete(*self.tv_recete_icd.get_children())
        for ri in recete_icd:
            kod = ri.get("ICDKodu") or "—"
            ack = ri.get("ICDAciklamasi") or ri.get("DirektAciklama") or "—"
            self.tv_recete_icd.insert("", "end", values=("ReceteICD", kod, ack))
        for rt in recete_teshis:
            kod = rt.get("ICDKodu") or rt.get("RTTeshisKodu") or "—"
            ack = rt.get("ICDAciklamasi") or rt.get("RTSecilenIlacAdi") or "—"
            self.tv_recete_icd.insert("", "end", values=("ReceteTeshis", kod, ack))

        # Raporlar
        self.tv_raporlar.delete(*self.tv_raporlar.get_children())
        self._zincir_by_rapor = zincir_by_rapor
        self._etken_by_rapor = etken_by_rapor
        self._ek_bilgi_by_rapor = ek_bilgi_by_rapor
        self._doktor_by_rapor = doktor_by_rapor
        self._raporlar = raporlar
        for r in raporlar:
            zincir = zincir_by_rapor.get(r["RaporAnaId"], [])
            icd_say = len({z.get("ICDKodu") for z in zincir if z.get("ICDKodu")})
            kod_say = len({z.get("RRKIRaporKodId") for z in zincir
                            if z.get("RRKIRaporKodId")})
            tarih = r.get("RaporAnaRaporTarihi")
            tarih_str = tarih.strftime("%d.%m.%Y") if tarih else "—"
            tur_ad = self._lookup_rapor_turu.get(r.get("RaporAnaRaporTuruId"), "—")

            doktorlar = doktor_by_rapor.get(r["RaporAnaId"], [])
            dok_adlar = ", ".join((d.get("DoktorAdiSoyadi") or "?")
                                   for d in doktorlar) or "—"
            dok_branslar = ", ".join({
                self._lookup_brans.get(d.get("RaporDoktorBransId"), "?")
                for d in doktorlar
            }) or "—"

            self.tv_raporlar.insert(
                "", "end",
                iid=str(r["RaporAnaId"]),
                values=(
                    r.get("RaporAnaRaporNo") or "—",
                    tarih_str,
                    tur_ad,
                    (r.get("HastaneAdi") or "")[:60],
                    dok_adlar[:50],
                    dok_branslar[:30],
                    icd_say,
                    kod_say,
                ),
            )

        # ICD/EtkinMadde/Aciklama temizle
        self.tv_icd.delete(*self.tv_icd.get_children())
        self.tv_etken_madde.delete(*self.tv_etken_madde.get_children())
        self.tv_ek_bilgi.delete(*self.tv_ek_bilgi.get_children())
        self.txt_rapor_aciklama.config(state="normal")
        self.txt_rapor_aciklama.delete("1.0", "end")
        self.txt_rapor_aciklama.config(state="disabled")
        if raporlar:
            ilk = str(raporlar[0]["RaporAnaId"])
            self.tv_raporlar.selection_set(ilk)
            self.tv_raporlar.see(ilk)

        # Hasta geçmişi
        self.tv_gecmis.delete(*self.tv_gecmis.get_children())
        for g in gecmis:
            tarih = g.get("RxIslemTarihi")
            tarih_str = tarih.strftime("%d.%m.%Y") if tarih else "—"
            self.tv_gecmis.insert(
                "", "end",
                values=(
                    tarih_str,
                    g.get("RxEReceteNo") or "",
                    g.get("UrunAdi") or "—",
                    g.get("RIAdet") or 0,
                    g.get("RIDoz") or "",
                    g.get("RIRaporKodId") or "—",
                ),
            )

        self._durum_yaz(
            f"Detay yüklendi: {len(ilaclar)} ilaç, {len(uyarilar)} uyarı, "
            f"{len(raporlar)} rapor, {len(recete_aciklamalari)} açıklama, "
            f"{len(gecmis)} geçmiş kayıt."
        )

    def _rapor_secildi(self, event=None):
        sec = self.tv_raporlar.selection()
        if not sec:
            return
        rapor_ana_id = int(sec[0])
        rapor = next((r for r in self._raporlar
                      if r["RaporAnaId"] == rapor_ana_id), None)
        if not rapor:
            return

        # ICD listesi
        zincir = self._zincir_by_rapor.get(rapor_ana_id, [])
        self.tv_icd.delete(*self.tv_icd.get_children())
        for z in zincir:
            bsl = z.get("RRKIBaslamaTarihi")
            bts = z.get("RRKIBitisTarihi")
            rk_kod, rk_ack = self._lookup_rapor_kodu.get(
                z.get("RRKIRaporKodId"), ("—", "")
            )
            sut_str = f"{rk_kod} - {rk_ack[:40]}" if rk_kod else "—"
            self.tv_icd.insert(
                "", "end",
                values=(
                    z.get("ICDKodu") or "—",
                    (z.get("ICDAciklamasi") or "—")[:80],
                    sut_str,
                    bsl.strftime("%d.%m.%Y") if bsl else "—",
                    bts.strftime("%d.%m.%Y") if bts else "—",
                ),
            )

        # Etken madde + doz
        self.tv_etken_madde.delete(*self.tv_etken_madde.get_children())
        for em in self._etken_by_rapor.get(rapor_ana_id, []):
            sgk_kod, ad = self._lookup_etkin_madde.get(
                em.get("EtkinMaddeId"), ("?", f"#{em.get('EtkinMaddeId')}")
            )
            tekrar_str = self._periyot_str(em.get("EtkinMaddeTekrar"),
                                            em.get("EtkinMaddeAralik"),
                                            em.get("EtkinMaddePeriyotId"))
            doz = em.get("EtkinMaddeDoz")
            birim = self._lookup_birim.get(em.get("EtkinMaddeBirimId"), "")
            doz_str = f"{doz} {birim}".strip()
            kullanim = self._lookup_kullanim.get(em.get("EtkinMaddeKullanimId"), "—")
            self.tv_etken_madde.insert(
                "", "end",
                values=(ad or sgk_kod, doz_str, tekrar_str, kullanim),
            )

        # Açıklama
        self.txt_rapor_aciklama.config(state="normal")
        self.txt_rapor_aciklama.delete("1.0", "end")
        self.txt_rapor_aciklama.insert(
            "end", rapor.get("RaporAnaAciklamalar") or "(açıklama yok)"
        )
        self.txt_rapor_aciklama.config(state="disabled")

        # Ek bilgi
        self.tv_ek_bilgi.delete(*self.tv_ek_bilgi.get_children())
        for x in self._ek_bilgi_by_rapor.get(rapor_ana_id, []):
            t = x.get("REBEklemeTarihi")
            tar_str = t.strftime("%d.%m.%Y") if t else "—"
            self.tv_ek_bilgi.insert(
                "", "end",
                values=(
                    x.get("REBTuru") or x.get("REBAciklama") or "—",
                    x.get("REBDeger") or "—",
                    tar_str,
                ),
            )

    # ---------------------------------------------------------- yardımcı
    def _durum_yaz(self, msg: str):
        try:
            self.durum_bar.config(text=msg)
        except Exception:
            pass

    def _kapat(self):
        try:
            if self.db:
                self.db.kapat()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        if self.ana_menu_callback:
            self.ana_menu_callback()


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
