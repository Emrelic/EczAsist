"""
Depo konfigürasyon ayarları
BotSiparis/src/utils/config.py'den adapte edilmiştir.
"""

# Depo URL'leri ve element tanımlamaları
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
    "iskoop": {
        "name": "İstanbul Ecza Koop",
        "url": "https://esube.iskoop.org/irj/portal",
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
            "search_input": "q",
            "no_stock_text": "Stokta yok"
        }
    },
    "sancak": {
        "name": "Sancak Ecza",
        "url": "https://eticaret.sancakecza.com.tr/",
        "elements": {
            "username_input": "Customer_username",
            "password_input": "Customer_password",
            "search_input": "search",
            "no_stock_text": "Stokta yok"
        }
    }
}

# Tarayıcı ayarları
WAIT_TIMEOUT = 10  # Saniye
