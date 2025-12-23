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

# Varsayılan rapor ayarları - Yeni detaylı yapı
VARSAYILAN_RAPOR_AYARLARI = {
    # WhatsApp raporu ayarları
    "whatsapp": {
        # 1) BAŞLANGIÇ KASASI
        "1a_baslangic_detay": False,        # Küpür detayları
        "1b_baslangic_toplam": True,        # Toplam tutar

        # 2) AKŞAM KASASI (Gün Sonu Nakit Sayım)
        "2a_aksam_detay": False,            # Küpür detayları
        "2b_aksam_toplam": True,            # Toplam tutar

        # 3) POS ve IBAN
        "3a_pos_iban_toplam": True,         # Genel toplam
        "3b_eczaci_pos_detay": True,        # Eczacı POS 4 satır
        "3b_eczaci_pos_toplam": True,       # Eczacı POS toplamı
        "3b_ingenico_detay": True,          # Ingenico 4 satır
        "3b_ingenico_toplam": True,         # Ingenico toplamı
        "3b_iban_detay": True,              # IBAN 4 satır
        "3b_iban_toplam": True,             # IBAN toplamı

        # 4) DÜZELTMELER
        "4a_duzeltilmis_nakit_toplam": True,  # Düzeltilmiş nakit toplamı
        "4b_masraflar": True,               # Girilmemiş masraflar (3 satır)
        "4b_silinen": True,                 # Silinenden etkiler (3 satır)
        "4b_alinan": True,                  # Alınan paralar (3 satır)

        # 5) BOTANİK EOS
        "5a_botanik_toplam": True,          # Genel toplam
        "5b_botanik_detay": False,          # Nakit, POS, IBAN detayları

        # 6) SAYIM-BOTANİK FARK TABLOSU
        "6a_fark_detay": True,              # Detaylı tablo (Nakit/POS/IBAN satırları)
        "6b_fark_ozet": True,               # Özet (sadece toplam fark)

        # 7) ERTESİ GÜN KASASI
        "7a_ertesi_gun_detay": False,       # Küpür detayları
        "7b_ertesi_gun_toplam": True,       # Toplam tutar
        "7c_ayrilan_para": True,            # Ayrılan para
    },
    # Yazıcı raporu ayarları
    "yazici": {
        # 1) BAŞLANGIÇ KASASI
        "1a_baslangic_detay": True,
        "1b_baslangic_toplam": True,

        # 2) AKŞAM KASASI
        "2a_aksam_detay": True,
        "2b_aksam_toplam": True,

        # 3) POS ve IBAN
        "3a_pos_iban_toplam": True,
        "3b_eczaci_pos_detay": True,
        "3b_eczaci_pos_toplam": True,
        "3b_ingenico_detay": True,
        "3b_ingenico_toplam": True,
        "3b_iban_detay": True,
        "3b_iban_toplam": True,

        # 4) DÜZELTMELER
        "4a_duzeltilmis_nakit_toplam": True,
        "4b_masraflar": True,
        "4b_silinen": True,
        "4b_alinan": True,

        # 5) BOTANİK EOS
        "5a_botanik_toplam": True,
        "5b_botanik_detay": True,

        # 6) SAYIM-BOTANİK FARK TABLOSU
        "6a_fark_detay": True,
        "6b_fark_ozet": True,

        # 7) ERTESİ GÜN KASASI
        "7a_ertesi_gun_detay": True,
        "7b_ertesi_gun_toplam": True,
        "7c_ayrilan_para": True,
    }
}

# Ayar kategorileri ve açıklamaları (Türkçe) - Gruplu yapı
AYAR_KATEGORILERI = {
    "1_baslangic": {
        "baslik": "1) BAŞLANGIÇ KASASI",
        "ayarlar": {
            "1a_baslangic_detay": "Küpür Detayları",
            "1b_baslangic_toplam": "Toplam Tutar",
        }
    },
    "2_aksam": {
        "baslik": "2) AKŞAM KASASI (Gün Sonu Nakit)",
        "ayarlar": {
            "2a_aksam_detay": "Küpür Detayları",
            "2b_aksam_toplam": "Toplam Tutar",
        }
    },
    "3_pos_iban": {
        "baslik": "3) POS ve IBAN",
        "ayarlar": {
            "3a_pos_iban_toplam": "Genel Toplam",
            "3b_eczaci_pos_detay": "Eczacı POS Detay (4 satır)",
            "3b_eczaci_pos_toplam": "Eczacı POS Toplamı",
            "3b_ingenico_detay": "Ingenico Detay (4 satır)",
            "3b_ingenico_toplam": "Ingenico Toplamı",
            "3b_iban_detay": "IBAN Detay (4 satır)",
            "3b_iban_toplam": "IBAN Toplamı",
        }
    },
    "4_duzeltmeler": {
        "baslik": "4) DÜZELTMELER",
        "ayarlar": {
            "4a_duzeltilmis_nakit_toplam": "Düzeltilmiş Nakit Toplamı",
            "4b_masraflar": "Girilmemiş Masraflar (3 satır)",
            "4b_silinen": "Silinenden Etkiler (3 satır)",
            "4b_alinan": "Alınan Paralar (3 satır)",
        }
    },
    "5_botanik": {
        "baslik": "5) BOTANİK EOS",
        "ayarlar": {
            "5a_botanik_toplam": "Genel Toplam",
            "5b_botanik_detay": "Detay (Nakit/POS/IBAN)",
        }
    },
    "6_fark": {
        "baslik": "6) SAYIM-BOTANİK FARK TABLOSU",
        "ayarlar": {
            "6a_fark_detay": "Detaylı Tablo",
            "6b_fark_ozet": "Özet (Sadece Toplam)",
        }
    },
    "7_ertesi": {
        "baslik": "7) ERTESİ GÜN KASASI",
        "ayarlar": {
            "7a_ertesi_gun_detay": "Küpür Detayları",
            "7b_ertesi_gun_toplam": "Toplam Tutar",
            "7c_ayrilan_para": "Ayrılan Para",
        }
    },
}

# Eski format için uyumluluk - düz liste
AYAR_ACIKLAMALARI = {
    "1a_baslangic_detay": "1A) Başlangıç Kasası Detayı",
    "1b_baslangic_toplam": "1B) Başlangıç Kasası Toplamı",
    "2a_aksam_detay": "2A) Akşam Kasası Detayı",
    "2b_aksam_toplam": "2B) Akşam Kasası Toplamı",
    "3a_pos_iban_toplam": "3A) POS+IBAN Genel Toplam",
    "3b_eczaci_pos_detay": "3B) Eczacı POS Detay",
    "3b_eczaci_pos_toplam": "3B) Eczacı POS Toplam",
    "3b_ingenico_detay": "3B) Ingenico Detay",
    "3b_ingenico_toplam": "3B) Ingenico Toplam",
    "3b_iban_detay": "3B) IBAN Detay",
    "3b_iban_toplam": "3B) IBAN Toplam",
    "4a_duzeltilmis_nakit_toplam": "4A) Düzeltilmiş Nakit Toplam",
    "4b_masraflar": "4B) Girilmemiş Masraflar",
    "4b_silinen": "4B) Silinenden Etkiler",
    "4b_alinan": "4B) Alınan Paralar",
    "5a_botanik_toplam": "5A) Botanik Genel Toplam",
    "5b_botanik_detay": "5B) Botanik Detay",
    "6a_fark_detay": "6A) Fark Tablosu Detaylı",
    "6b_fark_ozet": "6B) Fark Tablosu Özet",
    "7a_ertesi_gun_detay": "7A) Ertesi Gün Detay",
    "7b_ertesi_gun_toplam": "7B) Ertesi Gün Toplam",
    "7c_ayrilan_para": "7C) Ayrılan Para",
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
