"""
Botanik Bot - Kasa API Client
Terminal makineler için API istemcisi
Ana makineye bağlanarak veri okur/yazar
"""

import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class KasaAPIClient:
    """Kasa API İstemcisi"""

    def __init__(self, host='localhost', port=5000, timeout=10):
        self.base_url = f"http://{host}:{port}/api"
        self.timeout = timeout
        self.connected = False

    def baglanti_test(self):
        """Sunucuya bağlantı testi yap"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            if response.status_code == 200:
                self.connected = True
                logger.info(f"API sunucusuna bağlandı: {self.base_url}")
                return True, response.json()
            else:
                self.connected = False
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError as e:
            self.connected = False
            logger.error(f"Bağlantı hatası: {e}")
            return False, "Sunucuya baglanilamiyor. Ana makine calismiyor olabilir."
        except requests.exceptions.Timeout:
            self.connected = False
            return False, "Baglanti zamani asimi"
        except Exception as e:
            self.connected = False
            return False, str(e)

    def bugunun_kasasini_al(self):
        """Bugünün kasa verisini al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/bugun",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Bugünün kasası alınamadı: {e}")
            return False, str(e)

    def tarihe_gore_kasa_al(self, tarih):
        """Belirli bir tarihin kasa verisini al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/tarih/{tarih}",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Tarihli kasa alınamadı: {e}")
            return False, str(e)

    def kasa_kaydet(self, data):
        """Kasa verisini kaydet"""
        try:
            response = requests.post(
                f"{self.base_url}/kasa/kaydet",
                json=data,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Kasa kaydedilemedi: {e}")
            return False, str(e)

    def wizard_adim_kaydet(self, adim, veri, tarih=None):
        """Wizard adımını kaydet"""
        try:
            data = {
                'tarih': tarih or datetime.now().strftime("%Y-%m-%d"),
                'adim': adim,
                'veri': veri
            }
            response = requests.post(
                f"{self.base_url}/kasa/wizard/adim",
                json=data,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Wizard adımı kaydedilemedi: {e}")
            return False, str(e)

    def onceki_gun_kasasi_al(self):
        """Bir önceki günün kasasını al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/onceki-gun",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Önceki gün kasası alınamadı: {e}")
            return False, str(e)

    def kasa_gecmisi_al(self, limit=30, offset=0):
        """Kasa geçmişini al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/gecmis",
                params={'limit': limit, 'offset': offset},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Kasa geçmişi alınamadı: {e}")
            return False, str(e)

    def kasa_arsivle(self, tarih):
        """Kasa verisini arşivle"""
        try:
            response = requests.post(
                f"{self.base_url}/kasa/arsivle",
                json={'tarih': tarih},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Arşivleme hatası: {e}")
            return False, str(e)


# Singleton instance
_client_instance = None


def get_client(host='localhost', port=5000):
    """API istemcisi al (singleton)"""
    global _client_instance
    if _client_instance is None:
        _client_instance = KasaAPIClient(host, port)
    return _client_instance


def set_client_config(host, port):
    """İstemci yapılandırmasını güncelle"""
    global _client_instance
    _client_instance = KasaAPIClient(host, port)
    return _client_instance
