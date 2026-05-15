#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yedek Klasörü Boşaltma Modülü — Çoklu Profil Sürümü
====================================================
Botanik EOS otomasyonu her gün harici diske yedek alır. Bu modül:
  - Birden çok yedek klasörünü (PROFİL) ayrı ayrı yönetir.
  - Her profil için: klasör yolu, mod, uzantı filtresi, güvenlik checkbox.
  - 2 mod (radyo): "X günden eski sil" VEYA "en yeni N kopya hariç sil".
  - Güvenlik: silinecek dosyadan daha yeni dosya yoksa silmeyi ATLAR
    (yedek süreci durmuş olabilir; son yedekleri silersek hiç kalmaz).
  - Program açılışında günde 1 kez her aktif profil sessiz çalışır + log tutar.
  - Modül sayfası: SOL profil listesi + SAĞ seçili profilin dosya listesi.

Tek silme ucu: `os.remove(path)`. ASLA klasör/alt klasör silmez.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Optional


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
PROJE_KOK = Path(__file__).resolve().parent
AYAR_DOSYASI = PROJE_KOK / "yedek_temizlik_ayarlari.json"
LOG_DOSYASI = PROJE_KOK / "yedek_temizlik_log.txt"

MOD_GUN = "gun"
MOD_ADET = "adet"


# ---------------------------------------------------------------------------
# Profil veri yapısı
# ---------------------------------------------------------------------------
@dataclass
class YedekTemizlikProfil:
    ad: str = "Yeni Profil"
    klasor_yolu: str = ""
    mod: str = MOD_GUN                # "gun" veya "adet"
    gun_sayisi: int = 10              # MOD_GUN için
    kopya_sayisi: int = 5             # MOD_ADET için
    uzanti_filtresi: str = ""         # Boş = tüm dosyalar; örn. ".bak,.zip,.sql"
    yeni_dosya_kontrol_aktif: bool = True  # Güvenlik (sadece MOD_GUN'da anlamlı)
    aktif: bool = True                # Otomatik tetikte işlenir mi?
    son_calisma_tarihi: str = ""      # ISO "YYYY-MM-DD"

    def uzantilar_listesi(self) -> list[str]:
        if not self.uzanti_filtresi.strip():
            return []
        return [
            ("." + u.strip().lstrip(".").lower())
            for u in self.uzanti_filtresi.split(",")
            if u.strip()
        ]


# ---------------------------------------------------------------------------
# Depo: tüm profilleri + global ayarları diskte tutar
# ---------------------------------------------------------------------------
class YedekTemizlikDepo:
    def __init__(self, ayar_yolu: Path = AYAR_DOSYASI, log_yolu: Path = LOG_DOSYASI):
        self.ayar_yolu = ayar_yolu
        self.log_yolu = log_yolu
        self.profiller: list[YedekTemizlikProfil] = []
        self.otomatik_calistir: bool = True
        self._yukle()

    # ---- IO ---------------------------------------------------------------
    def _yukle(self) -> None:
        if not self.ayar_yolu.exists():
            return
        try:
            data = json.loads(self.ayar_yolu.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        # Yeni format
        if isinstance(data, dict) and "profiller" in data:
            self.otomatik_calistir = bool(data.get("otomatik_calistir", True))
            for p in data.get("profiller", []):
                self.profiller.append(self._profil_dict_to_obj(p))
            return

        # Eski format (tek profil) → migrate
        if isinstance(data, dict) and "klasor_yolu" in data:
            self.otomatik_calistir = bool(data.get("otomatik_calistir", True))
            eski = self._profil_dict_to_obj({
                "ad": "Varsayılan",
                "klasor_yolu": data.get("klasor_yolu", ""),
                "mod": data.get("mod", MOD_GUN),
                "gun_sayisi": data.get("gun_sayisi", 10),
                "kopya_sayisi": data.get("kopya_sayisi", 5),
                "uzanti_filtresi": data.get("uzanti_filtresi", ""),
                "yeni_dosya_kontrol_aktif": data.get("yeni_dosya_kontrol_aktif", True),
                "son_calisma_tarihi": data.get("son_calisma_tarihi", ""),
                "aktif": True,
            })
            self.profiller.append(eski)
            # Yeni formatta sakla
            try:
                self.kaydet()
            except OSError:
                pass

    @staticmethod
    def _profil_dict_to_obj(d: dict) -> YedekTemizlikProfil:
        bilinen = {f for f in YedekTemizlikProfil.__dataclass_fields__}
        d2 = {k: v for k, v in d.items() if k in bilinen}
        return YedekTemizlikProfil(**d2)

    def kaydet(self) -> None:
        data = {
            "otomatik_calistir": self.otomatik_calistir,
            "profiller": [asdict(p) for p in self.profiller],
        }
        self.ayar_yolu.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- profil yönetimi --------------------------------------------------
    def benzersiz_ad(self, taban: str = "Yeni Profil") -> str:
        mevcut = {p.ad for p in self.profiller}
        if taban not in mevcut:
            return taban
        i = 2
        while f"{taban} {i}" in mevcut:
            i += 1
        return f"{taban} {i}"

    def profil_ekle(self, ad: Optional[str] = None) -> YedekTemizlikProfil:
        profil = YedekTemizlikProfil(ad=self.benzersiz_ad(ad or "Yeni Profil"))
        self.profiller.append(profil)
        self.kaydet()
        return profil

    def profil_sil(self, ad: str) -> bool:
        for i, p in enumerate(self.profiller):
            if p.ad == ad:
                del self.profiller[i]
                self.kaydet()
                return True
        return False

    def profil_yeniden_adlandir(self, eski_ad: str, yeni_ad: str) -> bool:
        yeni_ad = yeni_ad.strip()
        if not yeni_ad:
            return False
        if any(p.ad == yeni_ad for p in self.profiller if p.ad != eski_ad):
            return False
        for p in self.profiller:
            if p.ad == eski_ad:
                p.ad = yeni_ad
                self.kaydet()
                return True
        return False

    def profil_bul(self, ad: str) -> Optional[YedekTemizlikProfil]:
        for p in self.profiller:
            if p.ad == ad:
                return p
        return None


# ---------------------------------------------------------------------------
# Yönetici: tek profil için temizleme mantığı
# ---------------------------------------------------------------------------
class YedekTemizlikYonetici:
    def __init__(self, profil: YedekTemizlikProfil, depo: YedekTemizlikDepo):
        self.profil = profil
        self.depo = depo

    def dosyalari_listele(self) -> list[tuple[Path, datetime, int]]:
        if not self.profil.klasor_yolu:
            return []
        klasor = Path(self.profil.klasor_yolu)
        if not klasor.exists() or not klasor.is_dir():
            return []
        uzantilar = self.profil.uzantilar_listesi()
        sonuc: list[tuple[Path, datetime, int]] = []
        for giris in klasor.iterdir():
            if not giris.is_file():
                continue
            if uzantilar and giris.suffix.lower() not in uzantilar:
                continue
            try:
                stat = giris.stat()
            except OSError:
                continue
            sonuc.append((giris, datetime.fromtimestamp(stat.st_mtime), stat.st_size))
        sonuc.sort(key=lambda t: t[1], reverse=True)
        return sonuc

    def silinecekleri_hesapla(
        self, simdiki_zaman: Optional[datetime] = None
    ) -> tuple[list[Path], list[Path], str]:
        simdi = simdiki_zaman or datetime.now()
        dosyalar = self.dosyalari_listele()
        if not dosyalar:
            return [], [], "Klasör boş ya da bulunamadı."

        if self.profil.mod == MOD_ADET:
            n = max(1, int(self.profil.kopya_sayisi))
            korunan = dosyalar[:n]
            silinecek = dosyalar[n:]
            if not silinecek:
                return [], [d[0] for d in korunan], f"Toplam {len(dosyalar)} dosya ≤ {n}; silinecek yok."
            return [d[0] for d in silinecek], [d[0] for d in korunan], ""

        gun = max(1, int(self.profil.gun_sayisi))
        esik = simdi - timedelta(days=gun)
        silinecek_aday = [d for d in dosyalar if d[1] < esik]
        korunan = [d for d in dosyalar if d[1] >= esik]
        if not silinecek_aday:
            return [], [d[0] for d in korunan], f"{gun} günden eski dosya yok."
        if self.profil.yeni_dosya_kontrol_aktif and not korunan:
            return (
                [],
                [d[0] for d in dosyalar],
                f"GÜVENLİK: {gun} günden yeni dosya YOK. Yedek süreci durmuş olabilir; "
                "silme ATLANDI. Yeni bir yedek geldiğinde tekrar çalışacak.",
            )
        return [d[0] for d in silinecek_aday], [d[0] for d in korunan], ""

    def temizle(self, simdiki_zaman: Optional[datetime] = None) -> dict:
        silinecek, korunan, atlama = self.silinecekleri_hesapla(simdiki_zaman)
        sonuc = {
            "profil": self.profil.ad,
            "silinen_sayi": 0,
            "silinen_yollar": [],
            "korunan_sayi": len(korunan),
            "atlama_nedeni": atlama,
            "hatalar": [],
        }
        if atlama or not silinecek:
            self._log_yaz(
                f"profil='{self.profil.ad}' | mod={self.profil.mod} | silinen=0 "
                f"| korunan={len(korunan)} | atlandi: {atlama or 'silinecek yok'}"
            )
            return sonuc
        for yol in silinecek:
            try:
                os.remove(yol)
                sonuc["silinen_yollar"].append(str(yol))
                sonuc["silinen_sayi"] += 1
            except OSError as exc:
                sonuc["hatalar"].append(f"{yol}: {exc}")
        self._log_yaz(
            f"profil='{self.profil.ad}' | mod={self.profil.mod} "
            f"| silinen={sonuc['silinen_sayi']} | korunan={len(korunan)} "
            f"| hata={len(sonuc['hatalar'])}"
        )
        return sonuc

    def gunluk_otomatik_calistir(self, bugun: Optional[date] = None) -> Optional[dict]:
        if not self.depo.otomatik_calistir or not self.profil.aktif:
            return None
        if not self.profil.klasor_yolu:
            return None
        bugun = bugun or date.today()
        try:
            son = (
                date.fromisoformat(self.profil.son_calisma_tarihi)
                if self.profil.son_calisma_tarihi else None
            )
        except ValueError:
            son = None
        if son == bugun:
            return None
        sonuc = self.temizle()
        self.profil.son_calisma_tarihi = bugun.isoformat()
        try:
            self.depo.kaydet()
        except OSError:
            pass
        return sonuc

    def _log_yaz(self, mesaj: str) -> None:
        try:
            with self.depo.log_yolu.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} | TEMIZLIK | {mesaj}\n")
        except OSError:
            pass


def son_log_satirlari(depo: YedekTemizlikDepo, n: int = 20) -> list[str]:
    if not depo.log_yolu.exists():
        return []
    try:
        return depo.log_yolu.read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []


def tum_profilleri_gunluk_calistir(
    depo: YedekTemizlikDepo, bugun: Optional[date] = None
) -> list[dict]:
    """Tüm aktif profilleri sırayla işler. None dönenler atlanmış demektir."""
    sonuclar: list[dict] = []
    for profil in list(depo.profiller):
        y = YedekTemizlikYonetici(profil, depo)
        s = y.gunluk_otomatik_calistir(bugun=bugun)
        if s is not None:
            sonuclar.append(s)
    return sonuclar


# ---------------------------------------------------------------------------
# Profil ayar penceresi
# ---------------------------------------------------------------------------
class YedekTemizlikAyarPenceresi(tk.Toplevel):
    def __init__(self, parent, depo: YedekTemizlikDepo,
                 profil: YedekTemizlikProfil, kaydet_callback=None):
        super().__init__(parent)
        self.depo = depo
        self.profil = profil
        self.kaydet_callback = kaydet_callback
        self.title(f"Yedek Temizlik — Ayarlar — {profil.ad}")
        self.configure(bg="#ECEFF1")
        self.geometry("640x560")
        self.transient(parent)
        self.grab_set()
        self._kur()

    def _kur(self) -> None:
        ana = tk.Frame(self, bg="#ECEFF1", padx=16, pady=14)
        ana.pack(fill="both", expand=True)

        tk.Label(
            ana, text=f"Profil: {self.profil.ad}",
            font=("Arial", 13, "bold"), bg="#ECEFF1", fg="#1A237E",
        ).pack(anchor="w", pady=(0, 12))

        # Klasör
        kf = tk.LabelFrame(ana, text="Yedek Klasörü", bg="#ECEFF1", fg="#1A237E",
                          font=("Arial", 10, "bold"), padx=10, pady=8)
        kf.pack(fill="x", pady=4)
        self.klasor_var = tk.StringVar(value=self.profil.klasor_yolu)
        tk.Entry(kf, textvariable=self.klasor_var, font=("Arial", 10)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        tk.Button(kf, text="📁 Gözat…", command=self._gozat,
                  bg="#1976D2", fg="white", font=("Arial", 9, "bold")).pack(side="left")

        # Uzantı
        uf = tk.Frame(ana, bg="#ECEFF1")
        uf.pack(fill="x", pady=(8, 4))
        tk.Label(uf, text="Uzantı filtresi (boş = tüm dosyalar):",
                bg="#ECEFF1", font=("Arial", 9)).pack(side="left")
        self.uzanti_var = tk.StringVar(value=self.profil.uzanti_filtresi)
        tk.Entry(uf, textvariable=self.uzanti_var, width=28, font=("Arial", 9)).pack(
            side="left", padx=8)
        tk.Label(uf, text="örn:  .bak, .zip, .sql",
                bg="#ECEFF1", fg="#607D8B", font=("Arial", 8, "italic")).pack(side="left")

        # Mod
        mf = tk.LabelFrame(ana, text="Silme Kuralı (birini seç)",
                          bg="#ECEFF1", fg="#1A237E",
                          font=("Arial", 10, "bold"), padx=10, pady=8)
        mf.pack(fill="x", pady=10)
        self.mod_var = tk.StringVar(value=self.profil.mod)

        r1 = tk.Frame(mf, bg="#ECEFF1"); r1.pack(fill="x", pady=3)
        tk.Radiobutton(r1, text="Tarih bazlı: ", variable=self.mod_var, value=MOD_GUN,
                      bg="#ECEFF1", font=("Arial", 10)).pack(side="left")
        self.gun_var = tk.IntVar(value=self.profil.gun_sayisi)
        tk.Spinbox(r1, from_=1, to=3650, textvariable=self.gun_var, width=6,
                  font=("Arial", 10)).pack(side="left")
        tk.Label(r1, text="günden eski dosyaları sil",
                bg="#ECEFF1", font=("Arial", 10)).pack(side="left", padx=4)

        r2 = tk.Frame(mf, bg="#ECEFF1"); r2.pack(fill="x", pady=3)
        tk.Radiobutton(r2, text="Adet bazlı: en yeni ", variable=self.mod_var, value=MOD_ADET,
                      bg="#ECEFF1", font=("Arial", 10)).pack(side="left")
        self.adet_var = tk.IntVar(value=self.profil.kopya_sayisi)
        tk.Spinbox(r2, from_=1, to=10000, textvariable=self.adet_var, width=6,
                  font=("Arial", 10)).pack(side="left")
        tk.Label(r2, text="kopya kalsın, gerisini sil",
                bg="#ECEFF1", font=("Arial", 10)).pack(side="left", padx=4)

        # Güvenlik + bu profil aktif mi
        sf = tk.LabelFrame(ana, text="Güvenlik & Otomatik",
                          bg="#ECEFF1", fg="#1A237E",
                          font=("Arial", 10, "bold"), padx=10, pady=8)
        sf.pack(fill="x", pady=4)
        self.yeni_kontrol_var = tk.BooleanVar(value=self.profil.yeni_dosya_kontrol_aktif)
        tk.Checkbutton(
            sf,
            text="Yeni dosya varlığını kontrol et: eşikten yeni dosya yoksa silmeyi atla "
                 "(yedek süreci durmuş olabilir)",
            variable=self.yeni_kontrol_var, bg="#ECEFF1", font=("Arial", 9),
            wraplength=560, justify="left", anchor="w",
        ).pack(fill="x", anchor="w")
        self.aktif_var = tk.BooleanVar(value=self.profil.aktif)
        tk.Checkbutton(
            sf,
            text="Bu profil otomatik tetikte işlensin",
            variable=self.aktif_var, bg="#ECEFF1", font=("Arial", 9),
            wraplength=560, justify="left", anchor="w",
        ).pack(fill="x", anchor="w")

        # Butonlar
        bf = tk.Frame(ana, bg="#ECEFF1")
        bf.pack(fill="x", pady=(14, 0))
        tk.Button(bf, text="💾 Kaydet", command=self._kaydet,
                  bg="#2E7D32", fg="white", font=("Arial", 10, "bold"),
                  padx=20, pady=6).pack(side="right", padx=4)
        tk.Button(bf, text="İptal", command=self.destroy,
                  bg="#90A4AE", fg="white", font=("Arial", 10),
                  padx=20, pady=6).pack(side="right")

    def _gozat(self) -> None:
        baslangic = self.klasor_var.get() or str(Path.home())
        secilen = filedialog.askdirectory(
            initialdir=baslangic, title="Yedek klasörünü seçin", parent=self)
        if secilen:
            self.klasor_var.set(secilen)

    def _kaydet(self) -> None:
        klasor = self.klasor_var.get().strip()
        if klasor and not Path(klasor).is_dir():
            if not messagebox.askyesno(
                "Klasör bulunamadı",
                f"'{klasor}' şu an mevcut değil (USB takılı değil olabilir).\n"
                "Yine de bu yolu kaydetmek ister misiniz?",
                parent=self):
                return
        self.profil.klasor_yolu = klasor
        self.profil.mod = self.mod_var.get()
        self.profil.gun_sayisi = max(1, int(self.gun_var.get() or 1))
        self.profil.kopya_sayisi = max(1, int(self.adet_var.get() or 1))
        self.profil.uzanti_filtresi = self.uzanti_var.get().strip()
        self.profil.yeni_dosya_kontrol_aktif = bool(self.yeni_kontrol_var.get())
        self.profil.aktif = bool(self.aktif_var.get())
        try:
            self.depo.kaydet()
        except OSError as exc:
            messagebox.showerror("Ayar kaydedilemedi", str(exc), parent=self)
            return
        if self.kaydet_callback:
            self.kaydet_callback()
        self.destroy()


# ---------------------------------------------------------------------------
# Ana modül penceresi (SOL profil listesi + SAĞ detay)
# ---------------------------------------------------------------------------
class YedekTemizlikAnaPencere(tk.Toplevel):
    def __init__(self, parent, depo: Optional[YedekTemizlikDepo] = None):
        super().__init__(parent)
        self.depo = depo or YedekTemizlikDepo()
        self.aktif_profil: Optional[YedekTemizlikProfil] = (
            self.depo.profiller[0] if self.depo.profiller else None
        )
        self.title("Yedek Klasörü Boşaltma — Çoklu Profil")
        self.configure(bg="#E8EAF6")
        self.geometry("1040x640")
        self._kur()
        self._yenile()

    def _kur(self) -> None:
        # Üst bar
        ust = tk.Frame(self, bg="#E8EAF6", padx=12, pady=10)
        ust.pack(fill="x")
        tk.Label(ust, text="🗑️ Yedek Klasörü Boşaltma — Çoklu Profil",
                font=("Arial", 14, "bold"), bg="#E8EAF6", fg="#1A237E").pack(side="left")

        self.global_oto_var = tk.BooleanVar(value=self.depo.otomatik_calistir)
        tk.Checkbutton(
            ust,
            text="Program açılışında günde 1 kez otomatik temizlik (tüm aktif profiller)",
            variable=self.global_oto_var, command=self._global_oto_degisti,
            bg="#E8EAF6", font=("Arial", 9),
        ).pack(side="right", padx=8)
        tk.Button(ust, text="🧹 Tümünü Şimdi Temizle", command=self._tumunu_temizle,
                 bg="#C62828", fg="white", font=("Arial", 10, "bold"),
                 padx=14, pady=4).pack(side="right", padx=4)

        # 2. satır: son tetik özeti
        oto_alt = tk.Frame(self, bg="#E8EAF6", padx=12)
        oto_alt.pack(fill="x")
        self.oto_durum_label = tk.Label(
            oto_alt, text="", bg="#E8EAF6", fg="#37474F",
            font=("Arial", 9, "italic"), anchor="e", justify="right",
        )
        self.oto_durum_label.pack(side="right")

        # Ana split
        gov = tk.Frame(self, bg="#E8EAF6")
        gov.pack(fill="both", expand=True, padx=12, pady=4)

        # SOL — profil listesi
        sol = tk.LabelFrame(gov, text="Profiller", bg="#E8EAF6", fg="#1A237E",
                           font=("Arial", 10, "bold"), padx=6, pady=6)
        sol.pack(side="left", fill="y")
        self.profil_listbox = tk.Listbox(sol, width=24, height=22, font=("Arial", 10),
                                        exportselection=False, activestyle="dotbox")
        self.profil_listbox.pack(fill="y", expand=False)
        self.profil_listbox.bind("<<ListboxSelect>>", self._profil_secildi)

        bf = tk.Frame(sol, bg="#E8EAF6")
        bf.pack(fill="x", pady=(6, 0))
        tk.Button(bf, text="➕ Ekle", command=self._profil_ekle,
                 bg="#2E7D32", fg="white", font=("Arial", 9, "bold"), width=8).pack(side="left", padx=2)
        tk.Button(bf, text="✏ Ad", command=self._profil_yeniden_adlandir,
                 bg="#F57C00", fg="white", font=("Arial", 9, "bold"), width=6).pack(side="left", padx=2)
        tk.Button(bf, text="🗙 Sil", command=self._profil_sil,
                 bg="#B71C1C", fg="white", font=("Arial", 9, "bold"), width=6).pack(side="left", padx=2)

        # SAĞ — seçili profil detayı
        sag = tk.Frame(gov, bg="#E8EAF6")
        sag.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # SAĞ üst — başlık + butonlar
        sag_ust = tk.Frame(sag, bg="#E8EAF6")
        sag_ust.pack(fill="x")
        self.profil_baslik = tk.Label(sag_ust, text="(profil seçili değil)",
                                     font=("Arial", 12, "bold"), bg="#E8EAF6", fg="#1A237E")
        self.profil_baslik.pack(side="left")
        tk.Button(sag_ust, text="⚙ Ayarlar", command=self._ayar_ac,
                 bg="#3949AB", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=2).pack(side="right", padx=2)
        tk.Button(sag_ust, text="🔄 Yenile", command=self._yenile,
                 bg="#00897B", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=2).pack(side="right", padx=2)
        tk.Button(sag_ust, text="🧹 Şimdi Temizle", command=self._manuel_temizle,
                 bg="#C62828", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=2).pack(side="right", padx=2)

        # Durum
        self.durum_label = tk.Label(sag, text="", bg="#FFF8E1", fg="#5D4037",
                                   anchor="w", font=("Arial", 9), padx=10, pady=6,
                                   justify="left")
        self.durum_label.pack(fill="x", pady=4)

        # Dosya listesi
        liste_frame = tk.Frame(sag, bg="#E8EAF6")
        liste_frame.pack(fill="both", expand=True)
        kolonlar = ("ad", "boyut", "tarih", "yas")
        self.tree = ttk.Treeview(liste_frame, columns=kolonlar, show="headings", height=16)
        for kol, txt, w, anchor in [
            ("ad", "Dosya Adı", 360, "w"),
            ("boyut", "Boyut", 100, "e"),
            ("tarih", "Değiştirilme", 160, "center"),
            ("yas", "Yaş (gün)", 90, "center"),
        ]:
            self.tree.heading(kol, text=txt)
            self.tree.column(kol, width=w, anchor=anchor)
        self.tree.tag_configure("silinecek", background="#FFCDD2")
        self.tree.tag_configure("korunan", background="#C8E6C9")
        scroll = ttk.Scrollbar(liste_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Log
        log_frame = tk.LabelFrame(sag, text="Son log kayıtları (son 10 satır)",
                                 bg="#E8EAF6", fg="#1A237E",
                                 font=("Arial", 9, "bold"), padx=8, pady=4)
        log_frame.pack(fill="x", pady=(8, 0))
        self.log_text = tk.Text(log_frame, height=6, font=("Consolas", 9), bg="#FAFAFA")
        self.log_text.pack(fill="x")
        self.log_text.configure(state="disabled")

    # ---- yardımcı ---------------------------------------------------------
    def _profilleri_doldur(self) -> None:
        self.profil_listbox.delete(0, tk.END)
        for p in self.depo.profiller:
            etiket = ("✓ " if p.aktif else "⏸ ") + p.ad
            self.profil_listbox.insert(tk.END, etiket)
        if self.aktif_profil:
            try:
                idx = next(i for i, p in enumerate(self.depo.profiller)
                          if p.ad == self.aktif_profil.ad)
                self.profil_listbox.selection_clear(0, tk.END)
                self.profil_listbox.selection_set(idx)
                self.profil_listbox.see(idx)
            except StopIteration:
                self.aktif_profil = None

    def _yenile(self) -> None:
        self._profilleri_doldur()
        self._oto_durumu_yaz()

        for r in self.tree.get_children():
            self.tree.delete(r)

        if not self.depo.profiller:
            self.profil_baslik.configure(text="(henüz profil yok)")
            self.durum_label.configure(
                text="Henüz profil yok. Sol paneldeki '➕ Ekle' ile yeni profil oluşturun.",
                bg="#FFF3E0")
            self._log_yenile()
            return

        if not self.aktif_profil:
            self.aktif_profil = self.depo.profiller[0]
            self._profilleri_doldur()

        p = self.aktif_profil
        self.profil_baslik.configure(text=p.ad)

        if not p.klasor_yolu:
            self.durum_label.configure(
                text="⚠ Bu profilde klasör seçili değil. ⚙ Ayarlar'a tıklayın.",
                bg="#FFF3E0")
        else:
            klasor = Path(p.klasor_yolu)
            mod_aciklama = (f"{p.gun_sayisi} günden eski sil"
                           if p.mod == MOD_GUN
                           else f"en yeni {p.kopya_sayisi} kopya kalsın")
            if not klasor.is_dir():
                self.durum_label.configure(
                    text=f"⚠ Klasör erişilemiyor: {klasor}  (USB takılı değil olabilir)",
                    bg="#FFEBEE")
            else:
                self.durum_label.configure(
                    text=(
                        f"Klasör: {klasor}    |    Kural: {mod_aciklama}    |    "
                        f"Profil aktif: {'EVET' if p.aktif else 'HAYIR (pasif)'}    |    "
                        f"Güvenlik: {'AÇIK' if p.yeni_dosya_kontrol_aktif else 'KAPALI'}"),
                    bg="#E0F2F1")

        try:
            y = YedekTemizlikYonetici(p, self.depo)
            silinecek, korunan, atlama = y.silinecekleri_hesapla()
            silinecek_set = {Path(x) for x in silinecek}
        except Exception as exc:
            silinecek_set = set()
            atlama = f"Hesaplama hatası: {exc}"
            y = None

        if y is not None:
            simdi = datetime.now()
            for yol, mtime, boyut in y.dosyalari_listele():
                yas = (simdi - mtime).days
                tag = "silinecek" if yol in silinecek_set else "korunan"
                self.tree.insert("", "end",
                                values=(yol.name, self._boyut_yaz(boyut),
                                       mtime.strftime("%Y-%m-%d %H:%M"), yas),
                                tags=(tag,))
        if atlama:
            self.durum_label.configure(
                text=self.durum_label.cget("text") + f"\n→ {atlama}",
                bg="#FFFDE7")
        self._log_yenile()

    def _log_yenile(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for satir in son_log_satirlari(self.depo, 10):
            self.log_text.insert("end", satir + "\n")
        self.log_text.configure(state="disabled")

    @staticmethod
    def _boyut_yaz(b: int) -> str:
        for birim in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {birim}"
            b /= 1024
        return f"{b:.1f} PB"

    # ---- olaylar ----------------------------------------------------------
    def _profil_secildi(self, _evt=None) -> None:
        sel = self.profil_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.depo.profiller):
            self.aktif_profil = self.depo.profiller[idx]
            self._yenile()

    def _profil_ekle(self) -> None:
        ad = simpledialog.askstring("Yeni Profil", "Profil adı:", parent=self)
        if ad is None:
            return
        ad = ad.strip() or "Yeni Profil"
        # benzersizleştir
        if self.depo.profil_bul(ad):
            ad = self.depo.benzersiz_ad(ad)
        profil = YedekTemizlikProfil(ad=ad)
        self.depo.profiller.append(profil)
        self.depo.kaydet()
        self.aktif_profil = profil
        self._yenile()
        # Hemen ayar penceresini aç
        self._ayar_ac()

    def _profil_yeniden_adlandir(self) -> None:
        if not self.aktif_profil:
            return
        yeni = simpledialog.askstring(
            "Yeniden Adlandır", "Yeni ad:",
            initialvalue=self.aktif_profil.ad, parent=self)
        if not yeni:
            return
        eski = self.aktif_profil.ad
        if not self.depo.profil_yeniden_adlandir(eski, yeni.strip()):
            messagebox.showerror("Hata",
                                f"'{yeni}' adı geçersiz veya zaten kullanılıyor.",
                                parent=self)
            return
        self._yenile()

    def _profil_sil(self) -> None:
        if not self.aktif_profil:
            return
        if not messagebox.askyesno(
            "Profili sil",
            f"'{self.aktif_profil.ad}' profili silinsin mi?\n"
            "(Bu sadece ayarı siler, klasördeki dosyalar etkilenmez.)",
            parent=self):
            return
        self.depo.profil_sil(self.aktif_profil.ad)
        self.aktif_profil = self.depo.profiller[0] if self.depo.profiller else None
        self._yenile()

    def _ayar_ac(self) -> None:
        if not self.aktif_profil:
            return
        YedekTemizlikAyarPenceresi(self, self.depo, self.aktif_profil,
                                   kaydet_callback=self._yenile)

    def _global_oto_degisti(self) -> None:
        self.depo.otomatik_calistir = bool(self.global_oto_var.get())
        try:
            self.depo.kaydet()
        except OSError:
            pass
        self._oto_durumu_yaz()

    def _oto_durumu_yaz(self) -> None:
        if not hasattr(self, "oto_durum_label"):
            return
        toplam = len(self.depo.profiller)
        aktif = sum(1 for p in self.depo.profiller if p.aktif and p.klasor_yolu)
        son_tarihler = [p.son_calisma_tarihi for p in self.depo.profiller
                       if p.son_calisma_tarihi]
        son_str = max(son_tarihler) if son_tarihler else "—"
        durum = "AÇIK" if self.depo.otomatik_calistir else "KAPALI"
        bugun = date.today().isoformat()
        bugun_isareti = " ✓ bugün çalıştı" if son_str == bugun else ""
        self.oto_durum_label.configure(
            text=(f"Otomatik tetik: {durum}   |   "
                  f"Profil: {toplam} (aktif {aktif})   |   "
                  f"Son tetik: {son_str}{bugun_isareti}")
        )

    def _manuel_temizle(self) -> None:
        if not self.aktif_profil:
            return
        y = YedekTemizlikYonetici(self.aktif_profil, self.depo)
        silinecek, _, atlama = y.silinecekleri_hesapla()
        if atlama and not silinecek:
            messagebox.showinfo("Silme yok", atlama, parent=self)
            return
        if not messagebox.askyesno("Onayla",
                                   f"'{self.aktif_profil.ad}' profilinde {len(silinecek)} dosya silinecek. Devam?",
                                   parent=self):
            return
        sonuc = y.temizle()
        self._yenile()
        mesaj = (f"Profil: {sonuc['profil']}\n"
                f"Silinen: {sonuc['silinen_sayi']}\n"
                f"Korunan: {sonuc['korunan_sayi']}\n"
                f"Hata: {len(sonuc['hatalar'])}")
        if sonuc["hatalar"]:
            mesaj += "\n\nHatalar:\n" + "\n".join(sonuc["hatalar"][:5])
        messagebox.showinfo("Temizlik bitti", mesaj, parent=self)

    def _tumunu_temizle(self) -> None:
        aktif_say = sum(1 for p in self.depo.profiller if p.aktif and p.klasor_yolu)
        if not aktif_say:
            messagebox.showinfo("Yapılacak iş yok",
                               "Aktif ve klasörü ayarlı profil bulunamadı.",
                               parent=self)
            return
        if not messagebox.askyesno("Onayla",
                                   f"{aktif_say} aktif profil için temizlik çalıştırılacak. Devam?",
                                   parent=self):
            return
        ozet = []
        for p in self.depo.profiller:
            if not (p.aktif and p.klasor_yolu):
                continue
            y = YedekTemizlikYonetici(p, self.depo)
            s = y.temizle()
            satir = f"• {s['profil']}: silinen={s['silinen_sayi']}, korunan={s['korunan_sayi']}"
            if s["atlama_nedeni"]:
                satir += f" — {s['atlama_nedeni']}"
            ozet.append(satir)
        self._yenile()
        messagebox.showinfo("Tümü tamamlandı", "\n".join(ozet) or "(işlem yok)", parent=self)


# ---------------------------------------------------------------------------
# Dış entry point'ler (botanik_gui.py bunları çağırır)
# ---------------------------------------------------------------------------
def yedek_temizlik_modulu_ac(parent: tk.Misc) -> YedekTemizlikAnaPencere:
    """Modül penceresini açar."""
    return YedekTemizlikAnaPencere(parent)


def gunluk_otomatik_temizlik_calistir(parent: Optional[tk.Misc] = None) -> list[dict]:
    """Program açılışında çağrılır. Tüm aktif profilleri sırayla işler.
    Güvenlik atlamaları olursa kullanıcıyı uyarır."""
    depo = YedekTemizlikDepo()
    sonuclar = tum_profilleri_gunluk_calistir(depo)
    uyari_satirlari = [
        f"• {s['profil']}: {s['atlama_nedeni']}"
        for s in sonuclar
        if s.get("atlama_nedeni") and "GÜVENLİK" in s["atlama_nedeni"]
    ]
    if parent is not None and uyari_satirlari:
        try:
            messagebox.showwarning(
                "Yedek Temizlik — Uyarı",
                "Bazı profillerde silme ATLANDI (yeni yedek yok):\n\n"
                + "\n".join(uyari_satirlari)
                + "\n\nLütfen yedek alma sürecinin çalıştığını doğrulayın.",
                parent=parent)
        except tk.TclError:
            pass
    return sonuclar


# ---------------------------------------------------------------------------
# Manuel çalıştırma
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = yedek_temizlik_modulu_ac(root)
    pencere.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
