"""
Botanik Bot - Rapor Ayarları Modülü
WhatsApp ve Yazıcı raporları için özelleştirilebilir ayarlar
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Varsayılan rapor ayarları
VARSAYILAN_RAPOR_AYARLARI = {
    # WhatsApp raporu ayarları
    "whatsapp": {
        "baslangic_kasasi_toplam": True,
        "baslangic_kasasi_detay": False,
        "gun_sonu_nakit_toplam": True,
        "gun_sonu_nakit_detay": False,
        "pos_raporlari": True,
        "pos_toplamlari": True,
        "iban_verileri": True,
        "iban_toplamlari": True,
        "sayim_botanik_ozet": True,
        "sayim_botanik_detay": False,
        "girilmeyen_masraflar": True,
        "silinen_etkiler": True,
        "alinan_paralar": True,
        "duzeltmeler_toplam": True,
        "botanik_detay": False,
        "botanik_toplam": True,
        "ertesi_gun_detay": False,
        "ertesi_gun_toplam": True,
        "ayrilan_para": True,
    },
    # Yazıcı raporu ayarları
    "yazici": {
        "baslangic_kasasi_toplam": True,
        "baslangic_kasasi_detay": True,
        "gun_sonu_nakit_toplam": True,
        "gun_sonu_nakit_detay": True,
        "pos_raporlari": True,
        "pos_toplamlari": True,
        "iban_verileri": True,
        "iban_toplamlari": True,
        "sayim_botanik_ozet": True,
        "sayim_botanik_detay": True,
        "girilmeyen_masraflar": True,
        "silinen_etkiler": True,
        "alinan_paralar": True,
        "duzeltmeler_toplam": True,
        "botanik_detay": True,
        "botanik_toplam": True,
        "ertesi_gun_detay": True,
        "ertesi_gun_toplam": True,
        "ayrilan_para": True,
    }
}

# Ayar açıklamaları (Türkçe)
AYAR_ACIKLAMALARI = {
    "baslangic_kasasi_toplam": "Başlangıç Kasası Toplamı",
    "baslangic_kasasi_detay": "Başlangıç Kasası Detayı (küpürler)",
    "gun_sonu_nakit_toplam": "Gün Sonu Nakit Toplamı",
    "gun_sonu_nakit_detay": "Gün Sonu Nakit Detayı (küpürler)",
    "pos_raporlari": "POS Raporları",
    "pos_toplamlari": "POS Toplamları",
    "iban_verileri": "IBAN Verileri",
    "iban_toplamlari": "IBAN Toplamları",
    "sayim_botanik_ozet": "Sayım-Botanik Özet Tablosu",
    "sayim_botanik_detay": "Sayım-Botanik Detaylı Tablo",
    "girilmeyen_masraflar": "Girilmeyen Masraflar",
    "silinen_etkiler": "Silinenden Etkiler",
    "alinan_paralar": "Alınan Paralar Verileri",
    "duzeltmeler_toplam": "Düzeltmeler Toplamı (masraf+silinen+alınan)",
    "botanik_detay": "Botanik Verileri Detaylı",
    "botanik_toplam": "Botanik Verileri Genel Toplam",
    "ertesi_gun_detay": "Ertesi Gün Kasası Detaylı",
    "ertesi_gun_toplam": "Ertesi Gün Kasası Toplam",
    "ayrilan_para": "Ayrılan Para",
}


def rapor_ayarlarini_yukle():
    """Rapor ayarlarını dosyadan yükle"""
    try:
        script_dir = Path(__file__).parent
        ayar_dosyasi = script_dir / "rapor_ayarlari.json"

        if ayar_dosyasi.exists():
            with open(ayar_dosyasi, 'r', encoding='utf-8') as f:
                ayarlar = json.load(f)
                # Eksik ayarları varsayılanla tamamla
                for kanal in ["whatsapp", "yazici"]:
                    if kanal not in ayarlar:
                        ayarlar[kanal] = VARSAYILAN_RAPOR_AYARLARI[kanal].copy()
                    else:
                        for key, val in VARSAYILAN_RAPOR_AYARLARI[kanal].items():
                            if key not in ayarlar[kanal]:
                                ayarlar[kanal][key] = val
                return ayarlar
        else:
            # Varsayılan ayarları kaydet
            rapor_ayarlarini_kaydet(VARSAYILAN_RAPOR_AYARLARI)
            return VARSAYILAN_RAPOR_AYARLARI.copy()
    except Exception as e:
        logger.error(f"Rapor ayarları yüklenemedi: {e}")
        return VARSAYILAN_RAPOR_AYARLARI.copy()


def rapor_ayarlarini_kaydet(ayarlar):
    """Rapor ayarlarını dosyaya kaydet"""
    try:
        script_dir = Path(__file__).parent
        ayar_dosyasi = script_dir / "rapor_ayarlari.json"

        with open(ayar_dosyasi, 'w', encoding='utf-8') as f:
            json.dump(ayarlar, f, ensure_ascii=False, indent=2)

        logger.info("Rapor ayarları kaydedildi")
        return True
    except Exception as e:
        logger.error(f"Rapor ayarları kaydedilemedi: {e}")
        return False


class RaporAyarlariPenceresi:
    """Rapor ayarları düzenleme penceresi"""

    def __init__(self, parent):
        self.parent = parent
        self.pencere = None
        self.ayarlar = rapor_ayarlarini_yukle()
        self.checkbox_vars = {"whatsapp": {}, "yazici": {}}

    def goster(self):
        """Ayarlar penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Rapor Ayarları")
        self.pencere.geometry("700x650")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 700) // 2
        y = (self.pencere.winfo_screenheight() - 650) // 2
        self.pencere.geometry(f"700x650+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#1565C0', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="RAPOR AYARLARI",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(expand=True)

        # Açıklama
        tk.Label(
            self.pencere,
            text="WhatsApp ve Yazıcı raporlarında hangi bilgilerin görüneceğini seçin:",
            font=("Arial", 10),
            bg='#FAFAFA',
            fg='#666'
        ).pack(pady=10)

        # İki sütunlu ana frame
        ana_frame = tk.Frame(self.pencere, bg='#FAFAFA')
        ana_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # WhatsApp sütunu
        self._kanal_olustur(ana_frame, "whatsapp", "WhatsApp Raporu", "#25D366", 0)

        # Yazıcı sütunu
        self._kanal_olustur(ana_frame, "yazici", "Yazıcı Raporu", "#FF5722", 1)

        # Buton frame
        buton_frame = tk.Frame(self.pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill="x")

        tk.Button(
            buton_frame,
            text="Tümünü Aç",
            font=("Arial", 9),
            bg='#4CAF50',
            fg='white',
            width=12,
            command=lambda: self._tumunu_sec(True)
        ).pack(side="left", padx=10)

        tk.Button(
            buton_frame,
            text="Tümünü Kapat",
            font=("Arial", 9),
            bg='#F44336',
            fg='white',
            width=12,
            command=lambda: self._tumunu_sec(False)
        ).pack(side="left", padx=5)

        tk.Button(
            buton_frame,
            text="Varsayılana Dön",
            font=("Arial", 9),
            bg='#9E9E9E',
            fg='white',
            width=12,
            command=self._varsayilana_don
        ).pack(side="left", padx=5)

        tk.Button(
            buton_frame,
            text="Kaydet ve Kapat",
            font=("Arial", 11, "bold"),
            bg='#2196F3',
            fg='white',
            width=15,
            command=self._kaydet_ve_kapat
        ).pack(side="right", padx=10)

        tk.Button(
            buton_frame,
            text="İptal",
            font=("Arial", 10),
            bg='#757575',
            fg='white',
            width=10,
            command=self.pencere.destroy
        ).pack(side="right", padx=5)

    def _kanal_olustur(self, parent, kanal, baslik, renk, sutun):
        """Bir kanal için checkbox listesi oluştur"""
        frame = tk.LabelFrame(
            parent,
            text=baslik,
            font=("Arial", 11, "bold"),
            bg='#FAFAFA',
            fg=renk,
            padx=10,
            pady=10
        )
        frame.grid(row=0, column=sutun, sticky="nsew", padx=5, pady=5)
        parent.columnconfigure(sutun, weight=1)
        parent.rowconfigure(0, weight=1)

        # Canvas ve scrollbar
        canvas = tk.Canvas(frame, bg='#FAFAFA', highlightthickness=0, height=400)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        check_frame = tk.Frame(canvas, bg='#FAFAFA')

        check_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=check_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Mouse scroll
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Checkbox'ları oluştur
        for key, aciklama in AYAR_ACIKLAMALARI.items():
            aktif = self.ayarlar.get(kanal, {}).get(key, True)
            var = tk.BooleanVar(value=aktif)
            self.checkbox_vars[kanal][key] = var

            cb = tk.Checkbutton(
                check_frame,
                text=aciklama,
                variable=var,
                font=("Arial", 9),
                bg='#FAFAFA',
                activebackground='#FAFAFA',
                anchor='w'
            )
            cb.pack(anchor='w', pady=1, fill='x')

    def _tumunu_sec(self, deger):
        """Tüm checkbox'ları aç/kapat"""
        for kanal in self.checkbox_vars:
            for key in self.checkbox_vars[kanal]:
                self.checkbox_vars[kanal][key].set(deger)

    def _varsayilana_don(self):
        """Varsayılan ayarlara dön"""
        for kanal in self.checkbox_vars:
            for key in self.checkbox_vars[kanal]:
                varsayilan = VARSAYILAN_RAPOR_AYARLARI.get(kanal, {}).get(key, True)
                self.checkbox_vars[kanal][key].set(varsayilan)

    def _kaydet_ve_kapat(self):
        """Ayarları kaydet ve pencereyi kapat"""
        # Checkbox değerlerini ayarlara aktar
        for kanal in self.checkbox_vars:
            if kanal not in self.ayarlar:
                self.ayarlar[kanal] = {}
            for key, var in self.checkbox_vars[kanal].items():
                self.ayarlar[kanal][key] = var.get()

        # Kaydet
        if rapor_ayarlarini_kaydet(self.ayarlar):
            messagebox.showinfo("Kaydedildi", "Rapor ayarları kaydedildi!")
            self.pencere.destroy()
        else:
            messagebox.showerror("Hata", "Ayarlar kaydedilemedi!")
