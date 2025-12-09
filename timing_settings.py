"""
Botanik Bot - Zamanlama Ayarları Yöneticisi
Her işlem için bekleme sürelerini yönetir ve saklar
"""

import json
from pathlib import Path
import logging
import threading

logger = logging.getLogger(__name__)


class TimingSettings:
    """Zamanlama ayarlarını yöneten sınıf"""

    def __init__(self, dosya_yolu="timing_settings.json", istatistik_dosya="timing_stats.json", profile=None):
        # Dosyayı script'in bulunduğu dizine kaydet
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu
        self.istatistik_dosya = Path(script_dir) / istatistik_dosya

        # Profil desteği
        self.profile = profile  # None = active_profile kullan, "current", "optimum" vs.

        # İstatistikler: {anahtar: {"count": 0, "total_time": 0.0}}
        self.istatistikler = self.istatistik_yukle()

        # Optimize mode - otomatik süre ayarlama
        self.optimize_mode = False  # Optimize mode aktif mi?
        self.optimized_keys = set()  # Optimize edilmiş anahtarlar
        self.optimize_multiplier = 1.3  # Reel süre × 1.3

        # Thread safety
        self._lock = threading.Lock()  # Race condition önleme

        # Varsayılan ayarlar (saniye cinsinden)
        self.varsayilan_ayarlar = {
            # Pencere İşlemleri
            "pencere_restore": 0.225,           # Pencere restore edildiğinde
            "pencere_move": 0.075,              # Pencere taşındığında
            "pencere_bulma": 0.075,             # Yeni pencere aranırken

            # Buton Tıklamaları
            "ilac_butonu": 0.225,               # İlaç butonuna tıklama
            "y_butonu": 0.15,                   # Y butonuna tıklama
            "geri_don_butonu": 0.09,            # Geri Dön butonuna tıklama
            "sonra_butonu": 0.075,              # SONRA butonuna tıklama
            "kapat_butonu": 0.045,              # Pencere Kapat butonuna tıklama
            "takip_et": 0.09,                   # Takip Et tıklama
            "alinmayanlari_sec": 0.15,          # Alınmayanları Seç tıklama

            # Sayfa Geçişleri
            "recete_sorgu": 0.375,              # Reçete Sorgu açma
            "ana_sayfa": 0.75,                  # Ana Sayfa'ya dönme
            "sorgula_butonu": 0.375,            # Sorgula butonuna tıklama

            # Veri Girişi
            "text_focus": 0.15,                 # Metin kutusuna focus
            "text_clear": 0.075,                # Metin temizleme
            "text_write": 0.15,                 # Metin yazma

            # Popup/Dialog İşlemleri
            "popup_kapat": 0.03,                # Popup kapatma (hızlı)
            "uyari_kapat": 0.03,                # Uyarı kapatma (hızlı)
            "laba_uyari": 0.075,                # LABA/LAMA uyarısı kapatma
            "ilac_cakismasi_uyari": 0.075,      # İlaç Çakışması uyarısı kapatma
            "recete_kontrol": 0.05,             # Reçete kontrolü (hızlı)
            "recete_notu_kapat": 0.05,          # Reçete notu kapatma

            # Diğer İşlemler
            "ilac_ekran_bekleme": 0.15,         # İlaç ekranı yükleme kontrolü
            "ilac_secim_bekleme": 0.045,        # İlaç seçimi sonrası
            "sag_tik": 0.12,                    # Sağ tık menü açılması
            "genel_gecis": 0.045,               # Genel pencere geçişleri

            # LABA/LAMA ve Yeniden Deneme
            "laba_sonrasi_bekleme": 0.3,        # LABA kapatıldıktan sonra
            "y_ikinci_deneme": 0.225,           # Y butonu 2. deneme

            # Masaüstü İşlemleri
            "masaustu_simge_tiklama": 1.0,      # Masaüstü simgesine çift tıklama
            "masaustu_simge_bekleme": 3.0,      # Simge tıklandıktan sonra program açılmasını bekleme

            # MEDULA Giriş İşlemleri
            "giris_pencere_bekleme": 2.0,       # Giriş penceresinin açılmasını bekleme
            "kullanici_combobox_ac": 0.5,       # Kullanıcı combobox'ını açma
            "kullanici_secim": 0.5,             # Kullanıcı seçimi
            "sifre_yazma": 0.5,                 # Şifre yazma
            "giris_butonu": 1.0,                # Giriş butonuna tıklama
            "giris_sonrasi_bekleme": 5.0,       # Giriş sonrası ana sayfanın açılmasını bekleme

            # Reçete Listesi İşlemleri
            "recete_listesi_butonu": 1.0,       # Reçete Listesi butonuna tıklama
            "recete_listesi_acilma": 2.0,       # Reçete Listesi ekranının açılmasını bekleme
            "donem_combobox_tiklama": 0.5,      # Dönem combobox'ına tıklama
            "donem_secim": 1.0,                 # Dönem seçimi
            "grup_butonu_tiklama": 1.0,         # A/B/C grup butonuna tıklama
            "grup_sorgulama": 2.0,              # Grup sorgulama sonrası bekleme
            "bulunamadi_mesaji_kontrol": 1.0,   # "Bu döneme ait sonlandırılmamış reçete bulunamadı" mesajı kontrolü
            "ilk_recete_tiklama": 1.0,          # İlk reçeteye tıklama
            "recete_acilma": 2.0,               # Reçete ekranının açılmasını bekleme

            # Genel Adım Arası Bekleme
            "adim_arasi_bekleme": 1.0,          # Her adım arasında varsayılan bekleme (1 saniye)

            # Retry Mekanizması Beklemeleri
            "retry_after_popup": 0.3,           # Popup kapatıldıktan sonra bekleme
            "retry_after_reconnect": 0.3,       # Yeniden bağlantı sonrası bekleme
            "retry_after_error": 0.3,           # Hata sonrası bekleme
        }

        self.ayarlar = self.yukle()

    def yukle(self):
        """Ayarları JSON dosyasından yükle (profil desteği ile)"""
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Yeni format kontrolü (profil bazlı)
                if isinstance(data, dict) and "profiles" in data:
                    # Hangi profili kullanacağız?
                    if self.profile:
                        # Manuel belirtilmiş profil
                        selected_profile = self.profile
                    else:
                        # active_profile kullan
                        selected_profile = data.get("active_profile", "current")

                    yuklu_ayarlar = data["profiles"].get(selected_profile, {})

                    if not yuklu_ayarlar:
                        logger.warning(f"⚠ Profil '{selected_profile}' bulunamadı, varsayılan ayarlar kullanılıyor")
                        return self.varsayilan_ayarlar.copy()

                    # Yeni eklenen ayarları da ekle (varsa)
                    for key, value in self.varsayilan_ayarlar.items():
                        if key not in yuklu_ayarlar:
                            yuklu_ayarlar[key] = value

                    logger.info(f"✓ Zamanlama ayarları yüklendi (Profil: {selected_profile})")
                    return yuklu_ayarlar
                else:
                    # Eski format (backward compatibility)
                    yuklu_ayarlar = data

                    # Yeni eklenen ayarları da ekle (varsa)
                    for key, value in self.varsayilan_ayarlar.items():
                        if key not in yuklu_ayarlar:
                            yuklu_ayarlar[key] = value

                    logger.info("✓ Zamanlama ayarları yüklendi (Eski format)")
                    return yuklu_ayarlar
            except Exception as e:
                logger.error(f"Ayar yükleme hatası: {e}")
                return self.varsayilan_ayarlar.copy()
        else:
            logger.info("⚠ Ayar dosyası bulunamadı, varsayılan ayarlar kullanılıyor")
            return self.varsayilan_ayarlar.copy()

    def kaydet(self):
        """Ayarları JSON dosyasına kaydet (profil desteği ile)"""
        try:
            # Önce mevcut dosyayı oku
            if self.dosya_yolu.exists():
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Profil bazlı mı?
                if isinstance(data, dict) and "profiles" in data:
                    # Hangi profile kaydedelim?
                    if self.profile:
                        selected_profile = self.profile
                    else:
                        selected_profile = data.get("active_profile", "current")

                    # Profili güncelle
                    data["profiles"][selected_profile] = self.ayarlar

                    # Kaydet
                    with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    logger.info(f"✓ Zamanlama ayarları kaydedildi (Profil: {selected_profile})")
                    return True
                else:
                    # Eski format, direkt kaydet
                    with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                        json.dump(self.ayarlar, f, indent=2, ensure_ascii=False)
                    logger.info("✓ Zamanlama ayarları kaydedildi")
                    return True
            else:
                # Dosya yok, yeni oluştur (profil bazlı)
                data = {
                    "active_profile": "current",
                    "profiles": {
                        "current": self.ayarlar
                    }
                }
                with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info("✓ Zamanlama ayarları kaydedildi (Yeni dosya)")
                return True
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            return False

    def get(self, anahtar, varsayilan=0.1):
        """Bir ayar değerini al"""
        return self.ayarlar.get(anahtar, varsayilan)

    def set(self, anahtar, deger):
        """Bir ayar değerini güncelle"""
        if isinstance(deger, (int, float)) and deger >= 0:
            self.ayarlar[anahtar] = float(deger)
            return True
        return False

    def profil_degistir(self, profil_adi):
        """
        Aktif profili değiştir ve ayarları yeniden yükle

        Args:
            profil_adi: "current", "optimum" gibi profil adı

        Returns:
            bool: Başarılı ise True
        """
        try:
            # Dosyayı oku
            if not self.dosya_yolu.exists():
                logger.error("❌ Ayar dosyası bulunamadı")
                return False

            with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Profil bazlı mı?
            if isinstance(data, dict) and "profiles" in data:
                # Profil var mı?
                if profil_adi not in data["profiles"]:
                    logger.error(f"❌ Profil '{profil_adi}' bulunamadı")
                    logger.info(f"Mevcut profiller: {', '.join(data['profiles'].keys())}")
                    return False

                # active_profile'ı güncelle
                data["active_profile"] = profil_adi

                # Dosyaya kaydet
                with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Ayarları yeniden yükle
                self.profile = profil_adi
                self.ayarlar = self.yukle()

                logger.info(f"✓ Profil değiştirildi: {profil_adi}")
                return True
            else:
                logger.error("❌ Dosya profil bazlı değil")
                return False

        except Exception as e:
            logger.error(f"❌ Profil değiştirme hatası: {e}")
            return False

    def profil_listesi(self):
        """
        Mevcut profillerin listesini al

        Returns:
            list: Profil adları listesi veya None
        """
        try:
            if not self.dosya_yolu.exists():
                return None

            with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict) and "profiles" in data:
                return list(data["profiles"].keys())
            else:
                return None

        except Exception as e:
            logger.error(f"❌ Profil listesi alma hatası: {e}")
            return None

    def varsayilana_don(self):
        """Tüm ayarları varsayılana döndür"""
        self.ayarlar = self.varsayilan_ayarlar.copy()
        self.kaydet()
        logger.info("✓ Ayarlar varsayılana döndürüldü")

    def hepsini_carpanla_guncelle(self, carpan):
        """Tüm ayarları bir çarpan ile güncelle"""
        if isinstance(carpan, (int, float)) and carpan > 0:
            for key in self.ayarlar:
                self.ayarlar[key] = round(self.varsayilan_ayarlar[key] * carpan, 3)
            self.kaydet()
            logger.info(f"✓ Tüm ayarlar {carpan}x ile güncellendi")
            return True
        return False

    def hizli_mod_uygula(self):
        """
        Hızlı Mod: BotTak7'deki agresif bekleme sürelerini uygula
        Dikkat: Stabil sistemlerde hız kazancı sağlar, ancak hata oranı artabilir!
        """
        hizli_sureler = {
            # Pencere İşlemleri (30-40% daha hızlı)
            "pencere_restore": 0.15,        # 0.225'ten düşürüldü
            "pencere_move": 0.05,           # 0.075'ten düşürüldü
            "pencere_bulma": 0.05,          # 0.075'ten düşürüldü

            # Buton Tıklamaları (40-50% daha hızlı)
            "ilac_butonu": 0.12,            # 0.225'ten düşürüldü
            "y_butonu": 0.08,               # 0.15'ten düşürüldü
            "geri_don_butonu": 0.04,        # 0.09'dan düşürüldü
            "sonra_butonu": 0.03,           # 0.075'ten düşürüldü
            "kapat_butonu": 0.02,           # 0.045'ten düşürüldü
            "takip_et": 0.04,               # 0.09'dan düşürüldü
            "alinmayanlari_sec": 0.08,      # 0.15'ten düşürüldü

            # Sayfa Geçişleri (30-40% daha hızlı)
            "recete_sorgu": 0.25,           # 0.375'ten düşürüldü
            "ana_sayfa": 0.5,               # 0.75'ten düşürüldü
            "sorgula_butonu": 0.25,         # 0.375'ten düşürüldü

            # Veri Girişi (40-50% daha hızlı)
            "text_focus": 0.08,             # 0.15'ten düşürüldü
            "text_clear": 0.04,             # 0.075'ten düşürüldü
            "text_write": 0.08,             # 0.15'ten düşürüldü

            # Popup/Dialog İşlemleri (zaten düşük, çok değişmez)
            "popup_kapat": 0.02,            # 0.03'ten düşürüldü
            "uyari_kapat": 0.02,            # 0.03'ten düşürüldü
            "laba_uyari": 0.05,             # 0.075'ten düşürüldü
            "ilac_cakismasi_uyari": 0.05,   # 0.075'ten düşürüldü
            "recete_kontrol": 0.03,         # 0.05'ten düşürüldü
            "recete_notu_kapat": 0.03,      # 0.05'ten düşürüldü

            # Diğer İşlemler (30-40% daha hızlı)
            "ilac_ekran_bekleme": 0.08,     # 0.15'ten düşürüldü
            "ilac_secim_bekleme": 0.02,     # 0.045'ten düşürüldü
            "sag_tik": 0.06,                # 0.12'den düşürüldü
            "genel_gecis": 0.02,            # 0.045'ten düşürüldü
            "laba_sonrasi_bekleme": 0.15,   # 0.3'ten düşürüldü
            "y_ikinci_deneme": 0.12,        # 0.225'ten düşürüldü

            # Masaüstü ve MEDULA giriş (değişmedi)
            "masaustu_simge_tiklama": 1.0,
            "masaustu_simge_bekleme": 3.0,
            "giris_pencere_bekleme": 2.0,
            "kullanici_combobox_ac": 0.5,
            "kullanici_secim": 0.5,
            "sifre_yazma": 0.5,
            "giris_butonu": 1.0,
            "giris_sonrasi_bekleme": 5.0,

            # Reçete Listesi (değişmedi)
            "recete_listesi_butonu": 1.0,
            "recete_listesi_acilma": 2.0,
            "donem_combobox_tiklama": 0.5,
            "donem_secim": 1.0,
            "grup_butonu_tiklama": 1.0,
            "grup_sorgulama": 2.0,
            "bulunamadi_mesaji_kontrol": 1.0,
            "ilk_recete_tiklama": 1.0,
            "recete_acilma": 2.0,
            "adim_arasi_bekleme": 1.0,

            # Retry Mekanizması (optimize edildi)
            "retry_after_popup": 0.2,           # 0.3'ten düşürüldü
            "retry_after_reconnect": 0.2,       # 0.3'ten düşürüldü
            "retry_after_error": 0.2,           # 0.3'ten düşürüldü
        }

        self.ayarlar.update(hizli_sureler)
        self.kaydet()
        logger.info("⚡ Hızlı Mod aktif - Bekleme süreleri %30-50 azaltıldı (BotTak7 profili)")
        return True

    def kategori_listesi(self):
        """Ayarları kategorilere göre grupla"""
        return {
            "Pencere İşlemleri": [
                ("pencere_restore", "Pencere Restore"),
                ("pencere_move", "Pencere Taşıma"),
                ("pencere_bulma", "Pencere Bulma"),
            ],
            "Buton Tıklamaları": [
                ("ilac_butonu", "İlaç Butonu"),
                ("y_butonu", "Y Butonu"),
                ("geri_don_butonu", "Geri Dön"),
                ("sonra_butonu", "SONRA Butonu"),
                ("kapat_butonu", "Kapat Butonu"),
                ("takip_et", "Takip Et"),
                ("alinmayanlari_sec", "Alınmayanları Seç"),
            ],
            "Sayfa Geçişleri": [
                ("recete_sorgu", "Reçete Sorgu"),
                ("ana_sayfa", "Ana Sayfa"),
                ("sorgula_butonu", "Sorgula Butonu"),
            ],
            "Veri Girişi": [
                ("text_focus", "Metin Focus"),
                ("text_clear", "Metin Temizleme"),
                ("text_write", "Metin Yazma"),
            ],
            "Popup/Dialog": [
                ("popup_kapat", "Popup Kapat"),
                ("uyari_kapat", "Uyarı Kapat"),
                ("laba_uyari", "LABA/LAMA Uyarı"),
                ("recete_kontrol", "Reçete Kontrol"),
                ("recete_notu_kapat", "Reçete Notu Kapat"),
            ],
            "Masaüstü İşlemleri": [
                ("masaustu_simge_tiklama", "Simge Tıklama"),
                ("masaustu_simge_bekleme", "Simge Bekleme"),
            ],
            "MEDULA Giriş": [
                ("giris_pencere_bekleme", "Giriş Pencere"),
                ("kullanici_combobox_ac", "Kullanıcı Combobox Aç"),
                ("kullanici_secim", "Kullanıcı Seçim"),
                ("sifre_yazma", "Şifre Yazma"),
                ("giris_butonu", "Giriş Butonu"),
                ("giris_sonrasi_bekleme", "Giriş Sonrası"),
            ],
            "Reçete Listesi": [
                ("recete_listesi_butonu", "Liste Butonu"),
                ("recete_listesi_acilma", "Liste Açılma"),
                ("donem_combobox_tiklama", "Dönem Combobox"),
                ("donem_secim", "Dönem Seçim"),
                ("grup_butonu_tiklama", "Grup Butonu"),
                ("grup_sorgulama", "Grup Sorgulama"),
                ("bulunamadi_mesaji_kontrol", "Bulunamadı Mesaj"),
                ("ilk_recete_tiklama", "İlk Reçete Tıklama"),
                ("recete_acilma", "Reçete Açılma"),
            ],
            "Diğer İşlemler": [
                ("ilac_ekran_bekleme", "İlaç Ekran Kontrol"),
                ("ilac_secim_bekleme", "İlaç Seçim"),
                ("sag_tik", "Sağ Tık"),
                ("genel_gecis", "Genel Geçiş"),
                ("laba_sonrasi_bekleme", "LABA Sonrası"),
                ("y_ikinci_deneme", "Y 2. Deneme"),
                ("adim_arasi_bekleme", "Adım Arası Bekleme"),
            ],
        }

    def istatistik_yukle(self):
        """İstatistikleri JSON dosyasından yükle"""
        if self.istatistik_dosya.exists():
            try:
                with open(self.istatistik_dosya, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"İstatistik yükleme hatası: {e}")
                return {}
        return {}

    def istatistik_kaydet(self):
        """İstatistikleri JSON dosyasına kaydet"""
        try:
            with open(self.istatistik_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.istatistikler, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"İstatistik kaydetme hatası: {e}")
            return False

    def kayit_ekle(self, anahtar, gercek_sure):
        """
        Bir işlem için gerçek süreyi kaydet ve optimize mode ise ayarı güncelle
        Thread-safe implementation
        """
        with self._lock:  # Race condition önleme
            if anahtar not in self.istatistikler:
                self.istatistikler[anahtar] = {"count": 0, "total_time": 0.0}

            self.istatistikler[anahtar]["count"] += 1
            self.istatistikler[anahtar]["total_time"] += gercek_sure

            # Optimize mode: Reel süre × 1.3 ile ayarı güncelle (sadece bir kere)
            if self.optimize_mode and anahtar not in self.optimized_keys:
                yeni_deger = gercek_sure * self.optimize_multiplier
                self.set(anahtar, yeni_deger)
                self.optimized_keys.add(anahtar)  # Artık thread-safe
                logger.info(f"🔧 Optimize: {anahtar} = {yeni_deger:.3f}s (reel: {gercek_sure:.3f}s)")
                self.kaydet()  # Hemen kaydet

            # Her 10 kayıtta bir otomatik kaydet
            if self.istatistikler[anahtar]["count"] % 10 == 0:
                self.istatistik_kaydet()

    def ortalama_al(self, anahtar):
        """Bir işlem için ortalama süreyi hesapla"""
        if anahtar in self.istatistikler:
            stats = self.istatistikler[anahtar]
            if stats["count"] > 0:
                return stats["total_time"] / stats["count"]
        return None

    def istatistik_al(self, anahtar):
        """Bir işlem için tam istatistiği al"""
        return self.istatistikler.get(anahtar, {"count": 0, "total_time": 0.0})

    def istatistik_sifirla(self):
        """Tüm istatistikleri sıfırla"""
        self.istatistikler = {}
        self.istatistik_kaydet()
        logger.info("✓ İstatistikler sıfırlandı")

    def optimize_mode_ac(self, multiplier=1.3, baslangic_suresi=3.0):
        """Optimize mode'u aç ve tüm ayarları özel süreyle başlat

        Args:
            multiplier: Reel süreye uygulanacak çarpan
                - 1.5 = %50 fazla (çok güvenli) - Yavaş/kararsız sistemler
                - 1.3 = %30 fazla (güvenli) - Standart önerilen
                - 1.2 = %20 fazla (dengeli) - Stabil sistemler
                - 1.1 = %10 fazla (agresif) - Çok hızlı/stabil sistemler
            baslangic_suresi: İlk ölçümden önce kullanılacak süre
                - 3.0s = Güvenli (varsayılan)
                - 1.0s = Dengeli
                - 0.5s = Agresif
                - 0.1s = Çok agresif (riskli!)
        """
        self.optimize_mode = True
        self.optimize_multiplier = multiplier
        self.optimized_keys.clear()

        # Tüm ayarları başlangıç süresine ayarla
        for anahtar in self.ayarlar.keys():
            self.ayarlar[anahtar] = baslangic_suresi

        self.kaydet()
        logger.info(f"🚀 Optimize mode aktif - Çarpan: {multiplier}x - Başlangıç: {baslangic_suresi}s")

    def optimize_mode_kapat(self):
        """Optimize mode'u kapat"""
        self.optimize_mode = False
        logger.info("⏹ Optimize mode kapatıldı")

    def optimize_profile_uygula(self, profile="guvenli"):
        """
        Hazır optimizasyon profili uygula

        Args:
            profile: "cok_guvenli", "guvenli", "dengeli", "agresif", "cok_agresif"
        """
        profiles = {
            "cok_guvenli": {
                "multiplier": 1.5,
                "baslangic": 3.0,
                "aciklama": "Yavaş/kararsız sistemler için (%50 marj)"
            },
            "guvenli": {
                "multiplier": 1.3,
                "baslangic": 3.0,
                "aciklama": "Standart önerilen (%30 marj)"
            },
            "dengeli": {
                "multiplier": 1.2,
                "baslangic": 1.0,
                "aciklama": "Stabil sistemler için (%20 marj)"
            },
            "agresif": {
                "multiplier": 1.1,
                "baslangic": 0.5,
                "aciklama": "Çok hızlı/stabil sistemler için (%10 marj)"
            },
            "cok_agresif": {
                "multiplier": 1.1,
                "baslangic": 0.1,
                "aciklama": "SADECE test/debug için (%10 marj, çok riskli!)"
            }
        }

        if profile not in profiles:
            logger.error(f"Geçersiz profil: {profile}")
            return False

        p = profiles[profile]
        self.optimize_mode_ac(multiplier=p["multiplier"], baslangic_suresi=p["baslangic"])
        logger.info(f"✓ {profile.upper()} profil: {p['aciklama']}")
        return True


# Global singleton
_timing_settings = None

def get_timing_settings():
    """Global TimingSettings instance'ını al"""
    global _timing_settings
    if _timing_settings is None:
        _timing_settings = TimingSettings()
    return _timing_settings

def reset_timing_settings():
    """Singleton'ı sıfırla (yeniden yüklemek için)"""
    global _timing_settings
    _timing_settings = None
    logger.debug("TimingSettings singleton sıfırlandı")
