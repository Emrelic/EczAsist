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
        self.host = host
        self.port = port

    def baglanti_test(self):
        """Sunucuya bağlantı testi yap"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            if response.status_code == 200:
                self.connected = True
                data = response.json()
                logger.info(f"API sunucusuna bağlandı: {self.base_url}")
                logger.info(f"Sunucu DB: {data.get('db_path', 'bilinmiyor')}")
                return True, data
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
                # Hata durumunda JSON response'u parse et
                try:
                    error_data = response.json()
                    return False, error_data
                except:
                    return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Kasa kaydedilemedi: {e}")
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

    def kasa_detay_al(self, kayit_id):
        """Belirli bir kaydın detayını al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/detay/{kayit_id}",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Kasa detayı alınamadı: {e}")
            return False, str(e)

    def tarihe_gore_kasa_al(self, tarih):
        """Belirli bir tarihin kasa kayıtlarını al"""
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

    def son_kayit_al(self):
        """En son kaydı al"""
        try:
            response = requests.get(
                f"{self.base_url}/kasa/son-kayit",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Son kayıt alınamadı: {e}")
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
