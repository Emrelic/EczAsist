"""
Tema Yönetimi Modülü
Tüm ekranlar için merkezi tema yönetimi
"""

import json
import os
import tkinter as tk
from tkinter import ttk

# Ayar dosyası yolu
TEMA_AYAR_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tema_ayarlar.json")

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA TANIMLARI
# ═══════════════════════════════════════════════════════════════════════════════

TEMALAR = {
    "koyu": {
        "ad": "Koyu Tema",
        "icon": "🌙",
        # Ana renkler
        "bg": "#1E1E1E",              # Ana arkaplan (koyu gri)
        "bg_secondary": "#2D2D2D",    # İkincil arkaplan
        "bg_tertiary": "#3D3D3D",     # Üçüncül arkaplan
        "header_bg": "#0D2137",       # Header (koyu lacivert)
        "card_bg": "#2D2D2D",         # Kart arkaplan
        "input_bg": "#3D3D3D",        # Input arkaplan
        "input_fg": "#FFFFFF",        # Input metin

        # Metin renkleri
        "fg": "#FFFFFF",              # Ana metin (beyaz)
        "fg_secondary": "#B0B0B0",    # İkincil metin (gri)
        "fg_muted": "#707070",        # Soluk metin

        # Vurgu renkleri
        "accent": "#1976D2",          # Ana vurgu (mavi)
        "accent_hover": "#1565C0",    # Vurgu hover
        "success": "#4CAF50",         # Başarı (yeşil)
        "success_bg": "#1B3D1B",      # Başarı arkaplan
        "warning": "#FF9800",         # Uyarı (turuncu)
        "warning_bg": "#3D2E00",      # Uyarı arkaplan
        "error": "#F44336",           # Hata (kırmızı)
        "error_bg": "#3D1B1B",        # Hata arkaplan
        "info": "#2196F3",            # Bilgi (mavi)
        "info_bg": "#1B2D3D",         # Bilgi arkaplan

        # Kenarlık
        "border": "#404040",
        "border_light": "#505050",

        # Tablo renkleri
        "table_header_bg": "#1565C0",
        "table_header_fg": "#FFFFFF",
        "table_row_bg": "#2D2D2D",
        "table_row_alt_bg": "#353535",
        "table_selected_bg": "#1976D2",

        # LabelFrame renkleri
        "frame_bg": "#252525",
        "frame_fg": "#90CAF9",
    },
    "acik": {
        "ad": "Açık Tema",
        "icon": "☀️",
        # Ana renkler
        "bg": "#F5F5F5",              # Ana arkaplan (açık gri)
        "bg_secondary": "#FFFFFF",    # İkincil arkaplan (beyaz)
        "bg_tertiary": "#E8E8E8",     # Üçüncül arkaplan
        "header_bg": "#1976D2",       # Header (mavi)
        "card_bg": "#FFFFFF",         # Kart arkaplan (beyaz)
        "input_bg": "#FFFFFF",        # Input arkaplan
        "input_fg": "#212121",        # Input metin

        # Metin renkleri
        "fg": "#212121",              # Ana metin (koyu gri)
        "fg_secondary": "#757575",    # İkincil metin (gri)
        "fg_muted": "#9E9E9E",        # Soluk metin

        # Vurgu renkleri
        "accent": "#1976D2",          # Ana vurgu (mavi)
        "accent_hover": "#1565C0",    # Vurgu hover
        "success": "#388E3C",         # Başarı (yeşil)
        "success_bg": "#E8F5E9",      # Başarı arkaplan
        "warning": "#F57C00",         # Uyarı (turuncu)
        "warning_bg": "#FFF3E0",      # Uyarı arkaplan
        "error": "#D32F2F",           # Hata (kırmızı)
        "error_bg": "#FFEBEE",        # Hata arkaplan
        "info": "#1976D2",            # Bilgi (mavi)
        "info_bg": "#E3F2FD",         # Bilgi arkaplan

        # Kenarlık
        "border": "#E0E0E0",
        "border_light": "#EEEEEE",

        # Tablo renkleri
        "table_header_bg": "#1976D2",
        "table_header_fg": "#FFFFFF",
        "table_row_bg": "#FFFFFF",
        "table_row_alt_bg": "#F5F5F5",
        "table_selected_bg": "#BBDEFB",

        # LabelFrame renkleri
        "frame_bg": "#FAFAFA",
        "frame_fg": "#1565C0",
    }
}


class TemaYonetici:
    """Tema yönetimi için singleton sınıf"""

    _instance = None
    _tema = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tema = cls._instance._yukle()
        return cls._instance

    def _yukle(self):
        """Kayıtlı tema tercihini yükle"""
        try:
            if os.path.exists(TEMA_AYAR_DOSYA):
                with open(TEMA_AYAR_DOSYA, 'r', encoding='utf-8') as f:
                    ayar = json.load(f)
                    return ayar.get("tema", "koyu")
        except:
            pass
        return "koyu"

    def kaydet(self, tema_adi):
        """Tema tercihini kaydet"""
        try:
            self._tema = tema_adi
            with open(TEMA_AYAR_DOSYA, 'w', encoding='utf-8') as f:
                json.dump({"tema": tema_adi}, f)
            return True
        except Exception as e:
            print(f"Tema kaydetme hatası: {e}")
            return False

    @property
    def aktif_tema(self):
        """Aktif tema adı"""
        return self._tema

    @property
    def renkler(self):
        """Aktif tema renkleri"""
        return TEMALAR.get(self._tema, TEMALAR["koyu"])

    def renk(self, anahtar, varsayilan=None):
        """Belirli bir rengi getir"""
        return self.renkler.get(anahtar, varsayilan)

    def degistir(self):
        """Temayı değiştir (toggle)"""
        yeni_tema = "acik" if self._tema == "koyu" else "koyu"
        self.kaydet(yeni_tema)
        return yeni_tema

    def ttk_stili_uygula(self):
        """TTK widget'ları için stil uygula"""
        style = ttk.Style()
        r = self.renkler

        # Genel ttk teması
        try:
            if self._tema == "koyu":
                style.theme_use('clam')  # Koyu tema için en iyi temel
            else:
                style.theme_use('clam')
        except:
            pass

        # Treeview stili
        style.configure("Treeview",
            background=r["table_row_bg"],
            foreground=r["fg"],
            fieldbackground=r["table_row_bg"],
            rowheight=25
        )
        style.configure("Treeview.Heading",
            background=r["table_header_bg"],
            foreground=r["table_header_fg"],
            font=('Arial', 9, 'bold')
        )
        style.map("Treeview",
            background=[('selected', r["table_selected_bg"])],
            foreground=[('selected', r["fg"])]
        )

        # Entry stili
        style.configure("TEntry",
            fieldbackground=r["input_bg"],
            foreground=r["input_fg"],
            insertcolor=r["fg"]
        )

        # Combobox stili
        style.configure("TCombobox",
            fieldbackground=r["input_bg"],
            foreground=r["input_fg"],
            background=r["input_bg"],
            selectbackground=r["accent"],
            selectforeground="#FFFFFF"
        )
        style.map("TCombobox",
            fieldbackground=[('readonly', r["input_bg"])],
            foreground=[('readonly', r["input_fg"])]
        )

        # Button stili
        style.configure("TButton",
            background=r["accent"],
            foreground="#FFFFFF"
        )

        # Checkbutton stili
        style.configure("TCheckbutton",
            background=r["bg"],
            foreground=r["fg"]
        )

        # Radiobutton stili
        style.configure("TRadiobutton",
            background=r["bg"],
            foreground=r["fg"]
        )

        # LabelFrame stili
        style.configure("TLabelframe",
            background=r["frame_bg"],
            foreground=r["frame_fg"]
        )
        style.configure("TLabelframe.Label",
            background=r["frame_bg"],
            foreground=r["frame_fg"],
            font=('Arial', 10, 'bold')
        )

        # Notebook stili
        style.configure("TNotebook",
            background=r["bg"],
            foreground=r["fg"]
        )
        style.configure("TNotebook.Tab",
            background=r["bg_secondary"],
            foreground=r["fg"],
            padding=[10, 5]
        )
        style.map("TNotebook.Tab",
            background=[('selected', r["accent"])],
            foreground=[('selected', '#FFFFFF')]
        )

        # Scrollbar stili
        style.configure("Vertical.TScrollbar",
            background=r["bg_tertiary"],
            troughcolor=r["bg_secondary"],
            arrowcolor=r["fg"]
        )
        style.configure("Horizontal.TScrollbar",
            background=r["bg_tertiary"],
            troughcolor=r["bg_secondary"],
            arrowcolor=r["fg"]
        )


# Singleton instance
_tema_yonetici = None

def get_tema():
    """Tema yöneticisi singleton'ını getir"""
    global _tema_yonetici
    if _tema_yonetici is None:
        _tema_yonetici = TemaYonetici()
    return _tema_yonetici


def tema_uygula(widget, parent_bg=None):
    """
    Bir widget ve alt widget'larına tema uygula

    Args:
        widget: Tema uygulanacak widget
        parent_bg: Üst widget arkaplan rengi (None ise tema bg kullanılır)
    """
    tema = get_tema()
    r = tema.renkler
    bg = parent_bg or r["bg"]

    try:
        widget_class = widget.winfo_class()

        if widget_class == "Frame":
            widget.configure(bg=bg)
        elif widget_class == "Label":
            widget.configure(bg=bg, fg=r["fg"])
        elif widget_class == "Button":
            # Mevcut renkleri koru (özel butonlar için)
            pass
        elif widget_class == "Labelframe":
            widget.configure(bg=r["frame_bg"], fg=r["frame_fg"])
            bg = r["frame_bg"]
        elif widget_class == "Canvas":
            widget.configure(bg=bg)
        elif widget_class == "Toplevel" or widget_class == "Tk":
            widget.configure(bg=r["bg"])
            bg = r["bg"]
    except:
        pass

    # Alt widget'lara uygula
    for child in widget.winfo_children():
        tema_uygula(child, bg)


# Kolay erişim fonksiyonları
def koyu_mu():
    """Koyu tema aktif mi?"""
    return get_tema().aktif_tema == "koyu"

def renk(anahtar, varsayilan=None):
    """Tema rengini getir"""
    return get_tema().renk(anahtar, varsayilan)

def renkler():
    """Tüm tema renklerini getir"""
    return get_tema().renkler
