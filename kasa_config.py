"""
Kasa Modulu Konfigurasyon Yoneticisi
Ana Makine / Terminal ayarlarini yonetir
"""

import os
import sys
import json
import logging

logger = logging.getLogger(__name__)

def get_config_path():
    """Config dosyasinin yolunu bul - kurulum dizinini kullan"""
    # Oncelik 1: Calistirilan script'in dizini (frozen exe veya py)
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmis
        base_dir = os.path.dirname(sys.executable)
    else:
        # Normal Python - ana script'in dizini
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    config_path = os.path.join(base_dir, "kasa_config.json")

    # Eger bulunamazsa, bu dosyanin dizinine bak
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kasa_config.json")

    logger.debug(f"Config dosya yolu: {config_path}")
    return config_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = get_config_path()

# Varsayilan konfigurasyon
DEFAULT_CONFIG = {
    "makine_tipi": "standalone",  # standalone, ana_makine, terminal
    "ana_makine_ip": "127.0.0.1",
    "api_port": 5000,
    "api_host": "0.0.0.0",
    "local_ip": "127.0.0.1"
}


def config_yukle():
    """Konfigurasyon dosyasini yukle"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"Konfigurasyon yuklendi: {config.get('makine_tipi', 'bilinmiyor')}")
                return config
        except Exception as e:
            logger.error(f"Konfigurasyon yuklenemedi: {e}")

    return DEFAULT_CONFIG.copy()


def config_kaydet(config):
    """Konfigurasyonu dosyaya kaydet"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info("Konfigurasyon kaydedildi")
        return True
    except Exception as e:
        logger.error(f"Konfigurasyon kaydedilemedi: {e}")
        return False


def makine_tipi_al():
    """Makine tipini al (standalone, ana_makine, terminal)"""
    config = config_yukle()
    return config.get("makine_tipi", "standalone")


def ana_makine_ip_al():
    """Ana makine IP adresini al"""
    config = config_yukle()
    return config.get("ana_makine_ip", "127.0.0.1")


def api_port_al():
    """API port numarasini al"""
    config = config_yukle()
    return config.get("api_port", 5000)


def terminal_mi():
    """Bu makine terminal mi?"""
    return makine_tipi_al() == "terminal"


def ana_makine_mi():
    """Bu makine ana makine mi?"""
    return makine_tipi_al() == "ana_makine"


def api_url_al():
    """API URL'ini olustur"""
    config = config_yukle()

    if config.get("makine_tipi") == "terminal":
        ip = config.get("ana_makine_ip", "127.0.0.1")
    else:
        ip = "127.0.0.1"

    port = config.get("api_port", 5000)
    return f"http://{ip}:{port}"


# Komut satiri argumanlari ile konfigurasyon
def argumanlardan_config_al():
    """Komut satiri argumanlarindan konfigurasyon al"""
    import sys

    config = config_yukle()

    for i, arg in enumerate(sys.argv):
        if arg == "--server" and i + 1 < len(sys.argv):
            server = sys.argv[i + 1]
            if ":" in server:
                ip, port = server.split(":")
                config["ana_makine_ip"] = ip
                config["api_port"] = int(port)
                config["makine_tipi"] = "terminal"
            else:
                config["ana_makine_ip"] = server
                config["makine_tipi"] = "terminal"

        elif arg == "--ana-makine":
            config["makine_tipi"] = "ana_makine"

        elif arg == "--standalone":
            config["makine_tipi"] = "standalone"

    return config


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Kasa Konfigurasyon Test")
    print("=" * 40)

    config = config_yukle()
    print(f"Makine Tipi: {config.get('makine_tipi')}")
    print(f"Ana Makine IP: {config.get('ana_makine_ip')}")
    print(f"API Port: {config.get('api_port')}")
    print(f"API URL: {api_url_al()}")
