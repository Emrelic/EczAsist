"""
Konfigürasyon ayarları
"""
import os
from pathlib import Path

# Proje kök dizini
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Log dizini
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Data dizini
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Depo URL'leri
DEPOLAR = {
    "alliance": {
        "name": "Alliance",
        "url": "https://esiparisv2.alliance-healthcare.com.tr/Sales/QuickOrder",
        "elements": {
            "search_input": "searchText",
            "result_tbody": "searchedItems",
            "no_stock_text": "Ürün Stokta Yok"
        }
    },
    "selcuk": {
        "name": "Selçuk",
        "url": "https://webdepo.selcukecza.com.tr/Siparis/hizlisiparis.aspx",
        "elements": {
            "search_input": "txtIlcArama",
            "icinde_gecen_checkbox": "chkInc",
            "stoktakiler_checkbox": "chkStoktakiler",
            "no_stock_text": "Şu An Stokta Bulunmamaktadır!"
        }
    },
    "yusufpasa": {
        "name": "Yusuf Paşa",
        "url": "http://eticaret.yusufpasa.com/Orders.asp",
        "elements": {
            "search_input": "ItemName",
            "baslayan_checkbox": "SearchType",
            "no_stock_text": "Şu An Stokta Bulunmamaktadır!"
        }
    },
    "iskoop": {
        "name": "İstanbul Ecza Koop",
        "url": "https://esube.iskoop.org/irj/portal",
        "elements": {
            "search_input": "TBD",  # Kullanıcıdan alınacak
            "no_stock_text": "TBD"  # Kullanıcıdan alınacak
        }
    },
    "bursa": {
        "name": "Bursa Ecza Koop",
        "url": "https://esube.bek.org.tr/",
        "elements": {
            "search_input": "TBD",
            "no_stock_text": "TBD"
        }
    },
    "farmazon": {
        "name": "Farmazon",
        "url": "https://www.farmazon.com.tr/account/login",
        "elements": {
            "username_input": "loginUsername",
            "password_input": "loginPassword",
            "search_input": "q",  # Ana sayfada input[name="q"]
            "no_stock_text": "Stokta yok"  # Arama sonrası belirlenecek
        }
    },
    "sancak": {
        "name": "Sancak Ecza",
        "url": "https://eticaret.sancakecza.com.tr/",
        "elements": {
            "username_input": "Customer_username",
            "password_input": "Customer_password",
            "search_input": "search",  # Ana sayfada arama kutusu (id="search")
            "no_stock_text": "Stokta yok"  # Arama sonrası belirlenecek
        }
    }
}

# Tarayıcı ayarları
BROWSER = "chrome"
HEADLESS = False
WAIT_TIMEOUT = 10  # Saniye

# Depo ödeme vadeleri (kaç ay sonraki 15'inde ödenir)
# 1 = Sonraki ayın 15'i (örn: Aralık alımları → 15 Ocak)
# 2 = 2 ay sonraki 15'i (örn: Aralık alımları → 15 Şubat)
# 3 = 3 ay sonraki 15'i (örn: Aralık alımları → 15 Mart)
DEPO_VADE_SECENEKLERI = {
    1: "Sonraki ayın 15'i",
    2: "2 ay sonraki 15'i",
    3: "3 ay sonraki 15'i"
}

VARSAYILAN_VADELER = {
    "alliance": 1,
    "selcuk": 1,
    "yusufpasa": 1,
    "iskoop": 1,
    "bursa": 1,
    "farmazon": 1,
    "sancak": 1
}

# Botanik EOS element isimleri
BOTANIK_ELEMENTS = {
    "yoklar_button": "Yoklar",
    "row_prefix": "Satır",
    "stok": "Stok satır {row}",
    "urun_adi": "Ürün Adı satır {row}",
    "tarih": "Tarih satır {row}",
    "depo_personel": "Depo/Personel satır {row}",
    "adet": "Adet satır {row}",
    "mf_iht": "MF/İht satır {row}",
    "minstk": "MinStk satır {row}",
    "aciklama": "Açıklama satır {row}"
}
