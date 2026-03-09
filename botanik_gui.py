#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Botanik Bot GUI - Reçete Grup Takip Sistemi
A: Raporlu, B: Normal, C: İş Yeri
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import json
from pathlib import Path
import logging
import winsound
from datetime import datetime
from botanik_bot import (
    BotanikBot,
    RaporTakip,
    tek_recete_isle,
    tek_recete_rapor_kontrol,
    recete_turu_oku,
    popup_kontrol_ve_kapat,
    recete_kaydi_bulunamadi_mi,
    medula_taskkill,
    medula_ac_ve_giris_yap,
    SistemselHataException,
    medula_yeniden_baslat_ve_giris_yap,
    sonraki_gruba_gec_islemi,
    console_pencereyi_ayarla
)
from timing_settings import get_timing_settings
from database import get_database
from session_logger import SessionLogger
from medula_settings import get_medula_settings

# Tema yönetimi
try:
    from tema_yonetimi import get_tema, TEMALAR
    TEMA_YUKLENDI = True
except ImportError:
    TEMA_YUKLENDI = False
    TEMALAR = {"koyu": {"ad": "Koyu Tema", "icon": "🌙"}, "acik": {"ad": "Açık Tema", "icon": "☀️"}}

# Logging ayarları - Saat:Dakika:Saniye:Milisaniye formatı
class MillisecondFormatter(logging.Formatter):
    """Milisaniye + önceki satırdan geçen süre içeren özel formatter"""
    _last_time = None

    def formatTime(self, record, datefmt=None):
        from datetime import datetime
        ct = datetime.fromtimestamp(record.created)
        s = ct.strftime("%H:%M:%S")
        s = f"{s}.{int(record.msecs):03d}"

        # Önceki satırdan geçen süreyi hesapla (her zaman saniye cinsinden)
        if MillisecondFormatter._last_time is not None:
            delta = record.created - MillisecondFormatter._last_time
            s = f"{s} (+{delta:.2f}s)"
        else:
            s = f"{s} (start)"

        MillisecondFormatter._last_time = record.created
        return s

# Root logger'ı temizle ve yeniden yapılandır
root_logger = logging.getLogger()
# Eski handler'ları kaldır
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Console handler oluştur
console_handler = logging.StreamHandler()
console_handler.setFormatter(MillisecondFormatter('%(asctime)s: %(message)s'))

# Root logger'ı yapılandır
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)


class RenkliReceteYonetici:
    """Renkli reçete listesini yönetir (yeşil/kırmızı reçeteli ilaçlar)"""

    def __init__(self):
        self.recete_listesi = set()  # Hızlı arama için set kullan
        self.dosya_adi = None
        self.yukleme_tarihi = None
        self.toplam_kayit = 0

    def excel_yukle(self, dosya_yolu: str) -> tuple:
        """
        Excel dosyasından renkli reçete listesini yükle.

        Returns:
            tuple: (basari, mesaj, kayit_sayisi)
        """
        try:
            import pandas as pd

            df = pd.read_excel(dosya_yolu)

            # ReceteNo sütunu var mı kontrol et
            if 'ReceteNo' not in df.columns:
                return (False, "Excel'de 'ReceteNo' sütunu bulunamadı!", 0)

            # Mevcut listeyi temizle
            self.recete_listesi.clear()

            # ReceteNo'ları işle (birden fazla olabilir: "ABC123 / DEF456")
            for idx, row in df.iterrows():
                recete_no = str(row['ReceteNo']).strip()
                if recete_no and recete_no != 'nan':
                    # " / " ile ayrılmış birden fazla reçete olabilir
                    parcalar = recete_no.split(' / ')
                    for parca in parcalar:
                        parca = parca.strip()
                        if parca:
                            self.recete_listesi.add(parca)

            self.dosya_adi = Path(dosya_yolu).name
            self.yukleme_tarihi = datetime.now()
            self.toplam_kayit = len(self.recete_listesi)

            return (True, f"Yüklendi: {self.toplam_kayit} reçete", self.toplam_kayit)

        except ImportError:
            return (False, "pandas veya openpyxl kütüphanesi yüklü değil!", 0)
        except Exception as e:
            return (False, f"Hata: {str(e)}", 0)

    def recete_var_mi(self, recete_no: str) -> bool:
        """
        Verilen reçete numarasının listede olup olmadığını kontrol et.

        Args:
            recete_no: Kontrol edilecek reçete numarası

        Returns:
            bool: Listede varsa True
        """
        if not recete_no:
            return False
        return recete_no.strip() in self.recete_listesi

    def liste_yuklu_mu(self) -> bool:
        """Liste yüklenmiş mi?"""
        return len(self.recete_listesi) > 0

    def temizle(self):
        """Listeyi temizle"""
        self.recete_listesi.clear()
        self.dosya_adi = None
        self.yukleme_tarihi = None
        self.toplam_kayit = 0

    def durum_bilgisi(self) -> str:
        """Mevcut durum bilgisini döndür"""
        if not self.liste_yuklu_mu():
            return "Yüklü değil"
        return f"{self.dosya_adi} ({self.toplam_kayit} reçete)"


class GrupDurumu:
    """Grup durumlarını JSON dosyasında sakla"""

    def __init__(self, dosya_yolu="grup_durumlari.json"):
        # Dosyayı script'in bulunduğu dizine kaydet (database.py gibi)
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu
        self.veriler = self.yukle()

    def _varsayilan_grup_yapisi(self):
        """Bir grup için varsayılan veri yapısı"""
        return {
            # Üçlü hafıza sistemi - her fonksiyon için ayrı son reçete
            "son_recete_ilac_takip": "",
            "son_recete_rapor_toplama": "",
            "son_recete_rapor_kontrol": "",
            # Eski uyumluluk için (genel son reçete - en gerideki)
            "son_recete": "",
            # İstatistikler
            "toplam_recete": 0,
            "toplam_takip": 0,
            "toplam_takipli_recete": 0,
            "toplam_sure": 0.0,
            "bitti_tarihi": None,
            "bitti_recete_sayisi": None
        }

    def _varsayilan_fonksiyon_ayarlari(self):
        """Fonksiyon ayarları için varsayılan yapı"""
        return {
            "ilac_takip_aktif": True,
            "rapor_toplama_aktif": True,
            "rapor_kontrol_aktif": True
        }

    def yukle(self):
        """JSON dosyasından verileri yükle"""
        guncellendi = False
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    veriler = json.load(f)

                    # Eski dosyaları yeni formata güncelle (backwards compatibility)
                    for grup in ["A", "B", "C", "GK"]:
                        if grup not in veriler:
                            # Yeni grup ekle (GK için)
                            veriler[grup] = self._varsayilan_grup_yapisi()
                            guncellendi = True
                        else:
                            # Eksik alanları ekle
                            if "toplam_takipli_recete" not in veriler[grup]:
                                veriler[grup]["toplam_takipli_recete"] = 0
                                guncellendi = True
                            if "bitti_tarihi" not in veriler[grup]:
                                veriler[grup]["bitti_tarihi"] = None
                                guncellendi = True
                            if "bitti_recete_sayisi" not in veriler[grup]:
                                veriler[grup]["bitti_recete_sayisi"] = None
                                guncellendi = True
                            # Üçlü hafıza sistemi alanları
                            if "son_recete_ilac_takip" not in veriler[grup]:
                                veriler[grup]["son_recete_ilac_takip"] = veriler[grup].get("son_recete", "")
                                guncellendi = True
                            if "son_recete_rapor_toplama" not in veriler[grup]:
                                veriler[grup]["son_recete_rapor_toplama"] = veriler[grup].get("son_recete", "")
                                guncellendi = True
                            if "son_recete_rapor_kontrol" not in veriler[grup]:
                                veriler[grup]["son_recete_rapor_kontrol"] = ""
                                guncellendi = True

                    # aktif_mod alanı yoksa ekle
                    if "aktif_mod" not in veriler:
                        veriler["aktif_mod"] = None
                        guncellendi = True

                    # Fonksiyon ayarları yoksa ekle
                    if "fonksiyon_ayarlari" not in veriler:
                        veriler["fonksiyon_ayarlari"] = self._varsayilan_fonksiyon_ayarlari()
                        guncellendi = True
                    else:
                        # Eksik fonksiyon ayarlarını ekle
                        varsayilan = self._varsayilan_fonksiyon_ayarlari()
                        for key, value in varsayilan.items():
                            if key not in veriler["fonksiyon_ayarlari"]:
                                veriler["fonksiyon_ayarlari"][key] = value
                                guncellendi = True

                    # Eğer güncelleme yapıldıysa dosyaya kaydet
                    if guncellendi:
                        try:
                            temp_dosya = self.dosya_yolu.with_suffix('.tmp')
                            with open(temp_dosya, 'w', encoding='utf-8') as f:
                                json.dump(veriler, f, indent=2, ensure_ascii=False)
                            import shutil
                            shutil.move(str(temp_dosya), str(self.dosya_yolu))
                        except Exception as e:
                            logger.debug(f"Operation failed: {type(e).__name__}")

                    return veriler
            except Exception as e:
                logger.debug(f"Operation failed: {type(e).__name__}")

        # Varsayılan yapı
        return {
            "aktif_mod": None,  # "tumunu_kontrol", "A", "B", "C", "GK" veya None
            "fonksiyon_ayarlari": self._varsayilan_fonksiyon_ayarlari(),
            "A": self._varsayilan_grup_yapisi(),
            "B": self._varsayilan_grup_yapisi(),
            "C": self._varsayilan_grup_yapisi(),
            "GK": self._varsayilan_grup_yapisi()
        }

    def kaydet(self):
        """Verileri JSON dosyasına kaydet"""
        try:
            # Dizin yoksa oluştur
            self.dosya_yolu.parent.mkdir(parents=True, exist_ok=True)

            # Dosya açıksa veya kullanımdaysa, geçici dosya kullan
            temp_dosya = self.dosya_yolu.with_suffix('.tmp')

            with open(temp_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.veriler, f, indent=2, ensure_ascii=False)

            # Geçici dosyayı asıl dosyanın üzerine taşı
            import shutil
            shutil.move(str(temp_dosya), str(self.dosya_yolu))

        except PermissionError:
            # İzin hatası - sessizce devam et (critical değil)
            logger.debug(f"Grup durumları kaydetme izni yok (devam ediliyor)")
        except Exception as e:
            # Diğer hatalar
            logger.warning(f"Grup durumları kaydedilemedi: {e}")

    def son_recete_al(self, grup):
        """Grubun son reçete numarasını al"""
        return self.veriler.get(grup, {}).get("son_recete", "")

    def son_recete_guncelle(self, grup, recete_no):
        """Grubun son reçete numarasını güncelle"""
        if grup in self.veriler:
            self.veriler[grup]["son_recete"] = recete_no
            self.kaydet()

    def istatistik_guncelle(self, grup, recete_sayisi=0, takip_sayisi=0, takipli_recete_sayisi=0, sure=0.0):
        """Grup istatistiklerini güncelle"""
        if grup in self.veriler:
            # Eksik alanları güvenli şekilde handle et
            if "toplam_takipli_recete" not in self.veriler[grup]:
                self.veriler[grup]["toplam_takipli_recete"] = 0

            self.veriler[grup]["toplam_recete"] += recete_sayisi
            self.veriler[grup]["toplam_takip"] += takip_sayisi
            self.veriler[grup]["toplam_takipli_recete"] += takipli_recete_sayisi
            self.veriler[grup]["toplam_sure"] += sure
            self.kaydet()

    def istatistik_al(self, grup):
        """Grup istatistiklerini al"""
        return self.veriler.get(grup, {})

    def grup_sifirla(self, grup):
        """Grubu sıfırla (ay sonu) - BİTTİ bilgisini de temizler"""
        if grup in self.veriler:
            self.veriler[grup] = {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_takipli_recete": 0,
                "toplam_sure": 0.0,
                "bitti_tarihi": None,
                "bitti_recete_sayisi": None
            }
            self.kaydet()

    def aktif_mod_ayarla(self, mod):
        """Aktif modu ayarla: "tumunu_kontrol", "A", "B", "C" veya None"""
        self.veriler["aktif_mod"] = mod
        self.kaydet()

    def aktif_mod_al(self):
        """Aktif modu al"""
        return self.veriler.get("aktif_mod", None)

    def bitti_bilgisi_ayarla(self, grup, tarih, recete_sayisi):
        """Grup bitiş bilgisini kaydet"""
        if grup in self.veriler:
            self.veriler[grup]["bitti_tarihi"] = tarih
            self.veriler[grup]["bitti_recete_sayisi"] = recete_sayisi
            self.kaydet()

    def bitti_bilgisi_al(self, grup):
        """Grup bitiş bilgisini al - (tarih, recete_sayisi) tuple döner"""
        if grup in self.veriler:
            tarih = self.veriler[grup].get("bitti_tarihi", None)
            sayisi = self.veriler[grup].get("bitti_recete_sayisi", None)
            return (tarih, sayisi)
        return (None, None)

    def bitti_bilgisi_temizle(self, grup):
        """Grup bitiş bilgisini temizle (yeni işlem başladığında)"""
        if grup in self.veriler:
            self.veriler[grup]["bitti_tarihi"] = None
            self.veriler[grup]["bitti_recete_sayisi"] = None
            self.kaydet()

    # ===== ÜÇLü HAFIZA SİSTEMİ =====
    def son_recete_al_fonksiyon(self, grup, fonksiyon):
        """
        Belirli bir fonksiyon için son reçete numarasını al

        Args:
            grup: "A", "B", "C" veya "GK"
            fonksiyon: "ilac_takip", "rapor_toplama" veya "rapor_kontrol"
        """
        alan_adi = f"son_recete_{fonksiyon}"
        return self.veriler.get(grup, {}).get(alan_adi, "")

    def son_recete_guncelle_fonksiyon(self, grup, fonksiyon, recete_no):
        """
        Belirli bir fonksiyon için son reçete numarasını güncelle

        Args:
            grup: "A", "B", "C" veya "GK"
            fonksiyon: "ilac_takip", "rapor_toplama" veya "rapor_kontrol"
            recete_no: Reçete numarası
        """
        if grup in self.veriler:
            alan_adi = f"son_recete_{fonksiyon}"
            self.veriler[grup][alan_adi] = recete_no
            # Genel son_recete'yi de güncelle (en gerideki)
            self._genel_son_recete_guncelle(grup)
            self.kaydet()

    def _genel_son_recete_guncelle(self, grup):
        """Genel son_recete'yi aktif fonksiyonların en geridekindenAL"""
        if grup not in self.veriler:
            return

        # Aktif fonksiyonların son reçetelerini al
        aktif_receteler = []
        ayarlar = self.fonksiyon_ayarlari_al()

        if ayarlar.get("ilac_takip_aktif", True):
            recete = self.veriler[grup].get("son_recete_ilac_takip", "")
            if recete:
                aktif_receteler.append(recete)

        if ayarlar.get("rapor_toplama_aktif", True):
            recete = self.veriler[grup].get("son_recete_rapor_toplama", "")
            if recete:
                aktif_receteler.append(recete)

        if ayarlar.get("rapor_kontrol_aktif", True):
            recete = self.veriler[grup].get("son_recete_rapor_kontrol", "")
            if recete:
                aktif_receteler.append(recete)

        # En gerideki reçeteyi bul (en küçük numara)
        if aktif_receteler:
            # Reçete numaraları string, sayısal karşılaştırma için
            try:
                en_gerideki = min(aktif_receteler, key=lambda x: int(x) if x.isdigit() else float('inf'))
                self.veriler[grup]["son_recete"] = en_gerideki
            except (ValueError, TypeError):
                # Sayısal olmayan reçete numaraları için string karşılaştırma
                self.veriler[grup]["son_recete"] = min(aktif_receteler)

    def en_gerideki_recete_al(self, grup):
        """
        Aktif fonksiyonlar arasından en gerideki reçete numarasını al

        Args:
            grup: "A", "B", "C" veya "GK"

        Returns:
            tuple: (recete_no, fonksiyon_adi) veya ("", None)
        """
        if grup not in self.veriler:
            return ("", None)

        ayarlar = self.fonksiyon_ayarlari_al()
        receteler = []  # [(recete_no, fonksiyon_adi), ...]

        if ayarlar.get("ilac_takip_aktif", True):
            recete = self.veriler[grup].get("son_recete_ilac_takip", "")
            if recete:
                receteler.append((recete, "ilac_takip"))

        if ayarlar.get("rapor_toplama_aktif", True):
            recete = self.veriler[grup].get("son_recete_rapor_toplama", "")
            if recete:
                receteler.append((recete, "rapor_toplama"))

        if ayarlar.get("rapor_kontrol_aktif", True):
            recete = self.veriler[grup].get("son_recete_rapor_kontrol", "")
            if recete:
                receteler.append((recete, "rapor_kontrol"))

        if not receteler:
            return ("", None)

        # En gerideki (en küçük numara)
        try:
            en_gerideki = min(receteler, key=lambda x: int(x[0]) if x[0].isdigit() else float('inf'))
            return en_gerideki
        except (ValueError, TypeError):
            return min(receteler, key=lambda x: x[0])

    # ===== FONKSİYON AYARLARI =====
    def fonksiyon_ayarlari_al(self):
        """Fonksiyon ayarlarını al"""
        return self.veriler.get("fonksiyon_ayarlari", self._varsayilan_fonksiyon_ayarlari())

    def fonksiyon_ayari_al(self, ayar_adi):
        """Tek bir fonksiyon ayarını al"""
        ayarlar = self.fonksiyon_ayarlari_al()
        varsayilan = self._varsayilan_fonksiyon_ayarlari()
        return ayarlar.get(ayar_adi, varsayilan.get(ayar_adi, True))

    def fonksiyon_ayari_guncelle(self, ayar_adi, deger):
        """Tek bir fonksiyon ayarını güncelle"""
        if "fonksiyon_ayarlari" not in self.veriler:
            self.veriler["fonksiyon_ayarlari"] = self._varsayilan_fonksiyon_ayarlari()
        self.veriler["fonksiyon_ayarlari"][ayar_adi] = deger
        self.kaydet()

    def fonksiyon_ayarlari_guncelle(self, ayarlar):
        """Tüm fonksiyon ayarlarını güncelle"""
        if "fonksiyon_ayarlari" not in self.veriler:
            self.veriler["fonksiyon_ayarlari"] = {}
        self.veriler["fonksiyon_ayarlari"].update(ayarlar)
        self.kaydet()

    # ===== GRUP SIFIRLAMA (GÜNCELLENMİŞ) =====
    def grup_sifirla_v2(self, grup):
        """Grubu sıfırla (ay sonu) - Üçlü hafıza dahil"""
        if grup in self.veriler:
            self.veriler[grup] = self._varsayilan_grup_yapisi()
            self.kaydet()


class BotanikGUI:
    """Botanik Bot GUI"""

    def __init__(self, root, ana_menu_callback=None):
        """
        Args:
            root: Tkinter root veya Toplevel pencere
            ana_menu_callback: Ana menüye dönüş callback fonksiyonu (opsiyonel)
        """
        self.root = root
        self.ana_menu_callback = ana_menu_callback
        self.root.title("Botanik Bot v3 - İlaç Takip")

        # Ekran boyutlarını al
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Ekran düzeni:
        # Sol 3/5 (0-60%): MEDULA
        # Orta 1/5 (60-80%): Konsol
        # Sağ 1/5 (80-100%): GUI

        # GUI için boyutlar (ekranın sağ 1/5'i, tam yükseklik)
        self.gui_width = int(screen_width * 0.20)  # Ekranın %20'si
        self.gui_height = screen_height - 40  # Taskbar için boşluk

        # GUI konumu (sağ kenar, %80'den başla)
        gui_x = int(screen_width * 0.80)  # Sağdaki 1/5'in başlangıcı
        gui_y = 0  # Üst kenara bitişik

        self.root.geometry(f"{self.gui_width}x{self.gui_height}+{gui_x}+{gui_y}")
        self.root.resizable(False, False)

        # Ekran boyutlarını sakla (diğer pencereler için)
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Konsol penceresini arka plana gönder (küçültülmüş)
        self.konsolu_arkaya_gonder()

        # Renkler
        self.bg_color = '#2E7D32'  # Koyu yeşil
        self.root.configure(bg=self.bg_color)

        # Grup durumları
        self.grup_durumu = GrupDurumu()

        # Rapor takip (CSV)
        self.rapor_takip = RaporTakip()
        self.son_kopyalama_tarihi = None
        self.son_kopyalama_button = None

        # Renkli reçete yönetici (yeşil/kırmızı reçeteli ilaçlar)
        self.renkli_recete = RenkliReceteYonetici()

        # Renkli reçete kontrol (PDF'den yüklenen liste ile karşılaştırma)
        self.renkli_recete_kontrol = None  # Lazy init - PDF yüklenince oluşturulur

        # Bot
        self.bot = None
        self.automation_thread = None
        self.is_running = False
        self.stop_requested = False

        # Seçili grup
        self.secili_grup = tk.StringVar(value="")
        self.aktif_grup = None  # Şu anda çalışan grup (A/B/C/GK)

        # Tümünü Kontrol Et (C→A→B→GK) değişkenleri
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modu aktif mi?
        self.tumu_kontrol_grup_sirasi = ["C", "A", "B", "GK"]  # Sıralı gruplar (C'den başla)
        self.tumu_kontrol_mevcut_index = 0  # Şu anda hangi grup işleniyor (index)

        # Oturum istatistikleri
        self.oturum_recete = 0
        self.oturum_takip = 0
        self.oturum_takipli_recete = 0  # Takipli ilaç bulunan reçete sayısı
        self.oturum_baslangic = None
        self.oturum_sure_toplam = 0.0  # Toplam çalışma süresi (durdur/başlat arası)
        self.oturum_duraklatildi = False
        self.son_recete_sureleri = []  # Son 5 reçetenin süreleri (saniye)

        # Yeniden başlatma sayacı
        self.yeniden_baslatma_sayaci = 0
        self.taskkill_sayaci = 0  # Taskkill sayacı
        self.ardisik_basarisiz_deneme = 0  # Ardışık başarısız yeniden başlatma denemesi (max 5)

        # Aşama geçmişi
        self.log_gecmisi = []

        # Zamanlama ayarları
        self.timing = get_timing_settings()
        self.ayar_entry_widgets = {}  # Ayar entry widget'larını sakla
        self.ayar_kaydet_timer = None  # Debounce timer

        # MEDULA ayarları
        self.medula_settings = get_medula_settings()

        # Database ve oturum tracking
        self.database = get_database()
        self.aktif_oturum_id = None  # Aktif oturum ID
        self.session_logger = None  # Oturum log dosyası

        # CAPTCHA modu kaldırıldı - Botanik program kendi çözüyor

        self.create_widgets()
        self.load_grup_verileri()

        # Başlangıç logu
        self.log_ekle("Beklemede...")

        # MEDULA'yı başlangıçta sol %80'e yerleştir
        self.root.after(800, self.medula_pencere_ayarla)

        # Wizard kontrolü (ayarlar eksikse göster)
        self.root.after(1000, self.wizard_kontrol)

    def medula_pencere_ayarla(self):
        """MEDULA penceresini sol 3/5'lik kesime yerleştir"""
        try:
            import ctypes
            import win32gui
            import win32con
            from pywinauto import Desktop

            # MEDULA penceresini bul (MEDULA adıyla)
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            medula_hwnd = None
            for window in windows:
                try:
                    window_text = window.window_text()
                    if "MEDULA" in window_text:
                        medula_hwnd = window.handle
                        logger.info(f"MEDULA penceresi bulundu: {window_text}")
                        break
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            if medula_hwnd is None:
                logger.debug("MEDULA penceresi bulunamadı (henüz açılmamış olabilir)")
                return

            # Ekran çözünürlüğünü al
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)

            # Sol 3/5 (60%) boyutlandırma
            medula_x = 0
            medula_y = 0
            medula_width = int(screen_width * 0.60)  # Ekranın %60'ı (3/5)
            medula_height = screen_height - 40  # Taskbar için boşluk

            # Minimize veya Maximize ise restore et
            try:
                placement = win32gui.GetWindowPlacement(medula_hwnd)
                current_state = placement[1]

                if current_state == win32con.SW_SHOWMINIMIZED or current_state == win32con.SW_SHOWMAXIMIZED:
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.2)
            except Exception as e:
                logger.debug(f"Restore hatası: {type(e).__name__}")

            # Pencereyi yerleştir
            win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)
            logger.info(f"✓ MEDULA sol 3/5'e yerleştirildi ({medula_width}x{medula_height})")

            # Konsol penceresini de ayarla
            self.root.after(300, self._konsolu_konumlandir)

        except Exception as e:
            logger.debug(f"MEDULA pencere ayarlanamadı: {e}")

    def wizard_kontrol(self):
        """MEDULA ayarlarını kontrol et, eksikse wizard'ı göster"""
        try:
            # Ayarları kontrol et
            # Ayarların dolu olup olmadığını kontrol et
            if not self.medula_settings.kullanici_bilgileri_dolu_mu():
                logger.info("MEDULA ayarları eksik, wizard açılıyor...")

                from medula_wizard import wizard_goster

                # Wizard'ı göster
                sonuc = wizard_goster(self.root, self.medula_settings)

                if sonuc:
                    logger.info("✓ Wizard tamamlandı, ayarlar kaydedildi")
                    self.log_ekle("✓ MEDULA ayarları yapılandırıldı")
                else:
                    logger.warning("⚠ Wizard iptal edildi")
                    self.log_ekle("⚠ MEDULA ayarları yapılandırılmadı")
            else:
                logger.info("✓ MEDULA ayarları mevcut, wizard atlanıyor")

        except Exception as e:
            logger.error(f"Wizard kontrol hatası: {e}")

    def konsolu_arkaya_gonder(self):
        """Konsol penceresini hemen konumlandır"""
        try:
            import ctypes
            import sys

            # Windows için konsol penceresini hemen konumlandır
            if sys.platform == "win32":
                # 100ms sonra konumlandır (pencere hazır olsun)
                self.root.after(100, self._konsolu_konumlandir)
        except Exception as e:
            logger.warning(f"Konsol konumlandırılamadı: {e}")

    def _konsolu_konumlandir(self):
        """Konsolu 2. dilime (%60-%80) yerleştir"""
        try:
            import ctypes
            import win32gui
            import win32con

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()

            if hwnd:
                # 2. dilim: %60-%80 arası (MEDULA'nın sağı, GUI'nin solu)
                console_x = int(self.screen_width * 0.60)  # %60'tan başla
                console_y = 0
                console_width = int(self.screen_width * 0.20)  # Ekranın %20'si
                console_height = self.screen_height - 40  # Taskbar için boşluk

                # Konsolu göster ve yerleştir
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

                # Yerleştir
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, console_x, console_y, console_width, console_height, win32con.SWP_SHOWWINDOW)
                win32gui.MoveWindow(hwnd, console_x, console_y, console_width, console_height, True)

                logger.info(f"✓ Konsol 2. dilime yerleşti ({console_width}x{console_height})")

                # GUI'yi öne al
                self.root.lift()
            else:
                logger.warning("❌ Konsol penceresi bulunamadı")
        except Exception as e:
            logger.error(f"Konsol konumlandırma hatası: {e}")

    def tum_pencereleri_yerlestir(self):
        """
        Tüm pencereleri yerleştir (ayara göre):

        Standart:
        - MEDULA: Sol 3/5 (0-60%)
        - Konsol: Orta 1/5 (60-80%)
        - GUI: Sağ 1/5 (80-100%)

        Geniş MEDULA:
        - MEDULA: Sol 4/5 (0-80%)
        - GUI: Sağ 1/5 (80-100%)
        - Konsol: GUI'nin arkasında (80-100%)
        """
        try:
            import win32gui
            import win32con
            import ctypes

            # Yerleşim ayarını al
            yerlesim = self.medula_settings.get("pencere_yerlesimi", "standart")
            logger.info(f"🖼 Tüm pencereler yerleştiriliyor... (mod: {yerlesim})")

            if yerlesim == "genis_medula":
                # ===== GENİŞ MEDULA MODU =====
                # MEDULA: %0-%80, GUI: %80-%100, Konsol: GUI arkasında

                # 1. MEDULA penceresini yerleştir (Sol 4/5 = %80)
                if self.bot and self.bot.main_window:
                    try:
                        medula_hwnd = self.bot.main_window.handle

                        medula_x = 0
                        medula_y = 0
                        medula_width = int(self.screen_width * 0.80)  # %80
                        medula_height = self.screen_height - 40

                        # Restore (minimize ise)
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.1)

                        # Yerleştir
                        win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)

                        logger.info(f"✓ MEDULA sol 4/5'e yerleştirildi ({medula_width}x{medula_height})")
                    except Exception as e:
                        logger.warning(f"MEDULA yerleştirilemedi: {e}")

                # 2. Konsol penceresini GUI'nin arkasına yerleştir (Sağ 1/5 = %80-%100)
                try:
                    hwnd = ctypes.windll.kernel32.GetConsoleWindow()

                    if hwnd:
                        console_x = int(self.screen_width * 0.80)  # %80'den başla
                        console_y = 0
                        console_width = int(self.screen_width * 0.20)  # %20
                        console_height = self.screen_height - 40

                        # Restore ve yerleştir (GUI'nin arkasına - HWND_BOTTOM)
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        time.sleep(0.05)
                        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, console_x, console_y, console_width, console_height, win32con.SWP_SHOWWINDOW)

                        logger.info(f"✓ Konsol GUI arkasına yerleştirildi ({console_width}x{console_height})")
                except Exception as e:
                    logger.warning(f"Konsol yerleştirilemedi: {e}")

                # 3. GUI penceresini yerleştir (Sağ 1/5 = %80-%100) - EN ÖNDE
                try:
                    gui_x = int(self.screen_width * 0.80)  # %80'den başla
                    gui_y = 0
                    gui_width = int(self.screen_width * 0.20)  # %20
                    gui_height = self.screen_height - 40

                    self.root.geometry(f"{gui_width}x{gui_height}+{gui_x}+{gui_y}")
                    self.root.update()

                    logger.info(f"✓ GUI sağ 1/5'e yerleştirildi ({gui_width}x{gui_height})")
                except Exception as e:
                    logger.warning(f"GUI yerleştirilemedi: {e}")

            else:
                # ===== STANDART MOD =====
                # MEDULA: %0-%60, Konsol: %60-%80, GUI: %80-%100

                # 1. MEDULA penceresini yerleştir (Sol 3/5 = %60)
                if self.bot and self.bot.main_window:
                    try:
                        medula_hwnd = self.bot.main_window.handle

                        medula_x = 0
                        medula_y = 0
                        medula_width = int(self.screen_width * 0.60)  # %60
                        medula_height = self.screen_height - 40

                        # Restore (minimize ise)
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.1)

                        # Yerleştir
                        win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)

                        logger.info(f"✓ MEDULA sol 3/5'e yerleştirildi ({medula_width}x{medula_height})")
                    except Exception as e:
                        logger.warning(f"MEDULA yerleştirilemedi: {e}")

                # 2. GUI penceresini yerleştir (Sağ 1/5 = %80-%100)
                try:
                    gui_x = int(self.screen_width * 0.80)  # %80'den başla
                    gui_y = 0
                    gui_width = int(self.screen_width * 0.20)  # %20
                    gui_height = self.screen_height - 40

                    self.root.geometry(f"{gui_width}x{gui_height}+{gui_x}+{gui_y}")
                    self.root.update()

                    logger.info(f"✓ GUI sağ 1/5'e yerleştirildi ({gui_width}x{gui_height})")
                except Exception as e:
                    logger.warning(f"GUI yerleştirilemedi: {e}")

                # 3. Konsol penceresini yerleştir (Orta 1/5 = %60-%80)
                try:
                    hwnd = ctypes.windll.kernel32.GetConsoleWindow()

                    if hwnd:
                        console_x = int(self.screen_width * 0.60)  # %60'tan başla
                        console_y = 0
                        console_width = int(self.screen_width * 0.20)  # %20
                        console_height = self.screen_height - 40

                        # Restore ve yerleştir
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        time.sleep(0.1)
                        win32gui.MoveWindow(hwnd, console_x, console_y, console_width, console_height, True)

                        logger.info(f"✓ Konsol 2. dilime yerleştirildi ({console_width}x{console_height})")
                    else:
                        logger.debug("Konsol penceresi bulunamadı")
                except Exception as e:
                    logger.warning(f"Konsol yerleştirilemedi: {e}")

            # GUI'yi öne al
            self.root.lift()
            self.root.focus_force()

            logger.info("✅ Tüm pencereler yerleştirildi")

        except Exception as e:
            logger.error(f"Pencere yerleştirme hatası: {e}", exc_info=True)

    def create_widgets(self):
        """Arayüzü oluştur"""
        # Ana container
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Üst bar - Her zaman göster (tema butonu için)
        top_bar = tk.Frame(main_container, bg=self.bg_color)
        top_bar.pack(fill="x", pady=(0, 5))

        # Ana Sayfa butonu (eğer callback varsa göster)
        if self.ana_menu_callback:
            ana_sayfa_btn = tk.Button(
                top_bar,
                text="🏠 Ana Sayfa",
                font=("Arial", 9, "bold"),
                bg="#1565C0",
                fg="white",
                activebackground="#0D47A1",
                activeforeground="white",
                cursor="hand2",
                bd=0,
                padx=10,
                pady=5,
                command=self.ana_sayfaya_don
            )
            ana_sayfa_btn.pack(side="left")

        # Tema değiştir butonu (sağda)
        self._tema_butonu_olustur(top_bar)

        # Başlık
        title_label = tk.Label(
            main_container,
            text="Botanik Bot v3 - İlaç Takip",
            font=("Arial", 12, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        title_label.pack(pady=(5, 5))

        # Sekmeler oluştur
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill="both", expand=True)

        # Ana sekme
        ana_sekme = tk.Frame(notebook, bg=self.bg_color)
        notebook.add(ana_sekme, text="  Ana  ")

        # Ayarlar sekmesi
        ayarlar_sekme = tk.Frame(notebook, bg='#E8F5E9')
        notebook.add(ayarlar_sekme, text="  ⚙ Ayarlar  ")

        # Depo Ekstre Karşılaştırma sekmesi
        ekstre_sekme = tk.Frame(notebook, bg='#E3F2FD')
        notebook.add(ekstre_sekme, text="  📊 Ekstre Karşılaştır  ")

        # Ana sekme içeriği
        self.create_main_tab(ana_sekme)

        # Ayarlar sekmesi içeriği
        self.create_settings_tab(ayarlar_sekme)

        # Ekstre karşılaştırma sekmesi içeriği
        self.create_ekstre_tab(ekstre_sekme)

    def _tema_butonu_olustur(self, parent):
        """Tema değiştir butonunu oluştur"""
        if TEMA_YUKLENDI:
            tema_yonetici = get_tema()
            aktif_tema = tema_yonetici.aktif_tema
        else:
            aktif_tema = "koyu"

        # Diğer temanın bilgisini al
        diger_tema = "acik" if aktif_tema == "koyu" else "koyu"
        diger_tema_bilgi = TEMALAR.get(diger_tema, {"ad": "Tema", "icon": "🎨"})

        tema_btn = tk.Button(
            parent,
            text=f"{diger_tema_bilgi['icon']} {diger_tema_bilgi['ad']}",
            font=("Arial", 8),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            activeforeground="white",
            cursor="hand2",
            bd=1,
            relief="raised",
            padx=8,
            pady=3,
            command=self._tema_degistir
        )
        tema_btn.pack(side="right", padx=(5, 0))

    def _tema_degistir(self):
        """Tema değiştir"""
        if TEMA_YUKLENDI:
            tema_yonetici = get_tema()
            yeni_tema = tema_yonetici.degistir()
            tema_bilgi = TEMALAR.get(yeni_tema, {"ad": yeni_tema, "icon": "🎨"})
            messagebox.showinfo(
                "Tema Değiştirildi",
                f"{tema_bilgi['icon']} {tema_bilgi['ad']} seçildi.\n\n"
                "Değişikliğin tam olarak uygulanması için\n"
                "programı yeniden başlatmanız gerekiyor."
            )
        else:
            messagebox.showwarning(
                "Tema Modülü Yok",
                "Tema yönetimi modülü (tema_yonetimi.py) bulunamadı."
            )

    def create_main_tab(self, parent):
        """Ana sekme içeriğini oluştur"""
        main_frame = tk.Frame(parent, bg=self.bg_color, padx=5, pady=5)
        main_frame.pack(fill="both", expand=True)

        subtitle_label = tk.Label(
            main_frame,
            text="Grup seçin ve BAŞLAT'a basın",
            font=("Arial", 8),
            bg=self.bg_color,
            fg="white"
        )
        subtitle_label.pack(pady=(0, 5))

        # Gruplar frame
        groups_frame = tk.Frame(main_frame, bg=self.bg_color)
        groups_frame.pack(fill="x", pady=(0, 10))

        # 4 Grup (C, A, B, GK) - C'den başlayarak sıralı
        grup_isimleri = {
            "A": "Raporlu",
            "B": "Normal",
            "C": "İş Yeri",
            "GK": "Geçici Koruma"
        }

        self.grup_labels = {}
        self.grup_rapor_kontrol_labels = {}  # Rapor kontrol reçete labelları
        self.grup_buttons = {}
        self.grup_x_buttons = {}
        self.grup_stat_labels = {}  # Aylık istatistik labelları
        self.grup_bitti_labels = {}  # ✅ BİTTİ bilgi labelları
        self.grup_frames = {}  # Grup frame'leri (renk değiştirmek için)

        for grup in ["C", "A", "B", "GK"]:
            # Grup container
            grup_outer = tk.Frame(groups_frame, bg=self.bg_color)
            grup_outer.pack(fill="x", pady=3)

            # Üst kısım - tıklanabilir
            grup_frame = tk.Frame(grup_outer, bg="#E8F5E9", relief="raised", bd=2, cursor="hand2")
            grup_frame.pack(fill="x")
            grup_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            # Frame'i kaydet (renk değiştirmek için)
            self.grup_frames[grup] = {
                'main': grup_frame,
                'widgets': []  # Alt widget'ları da saklayacağız
            }

            # Sol: Radio button + Grup adı
            left_frame = tk.Frame(grup_frame, bg="#E8F5E9")
            self.grup_frames[grup]['widgets'].append(left_frame)
            left_frame.pack(side="left", fill="y", padx=5, pady=5)
            left_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            radio = tk.Radiobutton(
                left_frame,
                text=f"{grup} ({grup_isimleri[grup]})",
                variable=self.secili_grup,
                value=grup,
                bg="#E8F5E9",
                fg="#1B5E20",
                font=("Arial", 9, "bold"),
                selectcolor="#81C784",
                command=lambda g=grup: self.grup_secildi(g)
            )
            radio.pack(anchor="w")
            self.grup_buttons[grup] = radio
            self.grup_frames[grup]['widgets'].append(radio)

            # Orta: Reçete numarası + X butonu container
            middle_frame = tk.Frame(grup_frame, bg="#E8F5E9")
            self.grup_frames[grup]['widgets'].append(middle_frame)
            middle_frame.pack(side="left", fill="both", expand=True, padx=5)
            middle_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            # Labels container (iki satırlı: ilaç takip + rapor kontrol)
            labels_container = tk.Frame(middle_frame, bg="#E8F5E9")
            labels_container.pack(side="left", fill="both", expand=True)
            labels_container.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))
            self.grup_frames[grup]['widgets'].append(labels_container)

            recete_label = tk.Label(
                labels_container,
                text="—",
                font=("Arial", 10),
                bg="#E8F5E9",
                fg="#2E7D32",
                anchor="center"
            )
            recete_label.pack(fill="x")
            recete_label.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))
            self.grup_labels[grup] = recete_label
            self.grup_frames[grup]['widgets'].append(recete_label)

            rapor_kontrol_label = tk.Label(
                labels_container,
                text="",
                font=("Arial", 7),
                bg="#E8F5E9",
                fg="#E65100",
                anchor="center"
            )
            rapor_kontrol_label.pack(fill="x")
            rapor_kontrol_label.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))
            self.grup_rapor_kontrol_labels[grup] = rapor_kontrol_label
            self.grup_frames[grup]['widgets'].append(rapor_kontrol_label)

            # X butonu - reçete numarasının hemen yanında
            x_button = tk.Button(
                middle_frame,
                text="✕",
                font=("Arial", 9, "bold"),
                bg="#FFCDD2",
                fg="#C62828",
                width=2,
                height=1,
                relief="raised",
                bd=1,
                command=lambda g=grup: self.grup_sifirla(g)
            )
            x_button.pack(side="left", padx=(2, 0))
            self.grup_x_buttons[grup] = x_button

            # Alt kısım - Aylık istatistikler
            stat_label = tk.Label(
                grup_outer,
                text="Ay: Rç:0 | Takipli:0 | İlaç:0 | 0s 0ms",
                font=("Arial", 6),
                bg="#C8E6C9",
                fg="#1B5E20",
                anchor="w",
                padx=5,
                pady=1
            )
            stat_label.pack(fill="x")
            self.grup_stat_labels[grup] = stat_label

            # ✅ YENİ: BİTTİ bilgi label'ı (stat_label altında)
            bitti_label = tk.Label(
                grup_outer,
                text="",  # Başlangıçta boş
                font=("Arial", 7, "bold"),
                bg="#FFF9C4",  # Açık sarı arka plan
                fg="#F57F17",  # Koyu sarı yazı
                anchor="center",
                padx=5,
                pady=2
            )
            # Başlangıçta gizli (pack etmiyoruz, sadece kaydediyoruz)
            self.grup_bitti_labels[grup] = bitti_label

        # HEPSİNİ KONTROL ET butonu (C grubu altında)
        tumu_kontrol_frame = tk.Frame(groups_frame, bg=self.bg_color)
        tumu_kontrol_frame.pack(fill="x", pady=(10, 5))

        self.tumu_kontrol_button = tk.Button(
            tumu_kontrol_frame,
            text="🔄 HEPSİNİ KONTROL ET (A→B→C)",
            font=("Arial", 10, "bold"),
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            disabledforeground="#E0E0E0",
            height=2,
            relief="raised",
            bd=3,
            command=self.tumu_kontrol_et
        )
        self.tumu_kontrol_button.pack(fill="x", padx=5)

        # Başlat/Durdur butonları
        buttons_frame = tk.Frame(main_frame, bg=self.bg_color)
        buttons_frame.pack(fill="x", pady=(5, 10))

        self.start_button = tk.Button(
            buttons_frame,
            text="BAŞLAT",
            font=("Arial", 10, "bold"),
            bg="#388E3C",
            fg="white",
            activebackground="#2E7D32",
            disabledforeground="#E0E0E0",
            width=14,
            height=2,
            relief="raised",
            bd=2,
            command=self.basla
        )
        self.start_button.pack(side="left", padx=(0, 5), expand=True)

        self.stop_button = tk.Button(
            buttons_frame,
            text="DURDUR",
            font=("Arial", 10, "bold"),
            bg="#616161",
            fg="white",
            activebackground="#D32F2F",
            disabledforeground="#E0E0E0",
            width=14,
            height=2,
            relief="raised",
            bd=2,
            state="disabled",
            command=self.durdur
        )
        self.stop_button.pack(side="left", expand=True)

        # CAPTCHA butonu kaldırıldı - Botanik program kendi çözüyor

        # CSV Kopyala Butonları
        # CSV Kopyala Butonu (Başlat/Durdur'un hemen altında)
        csv_button = tk.Button(
            main_frame,
            text="📋 CSV Kopyala",
            font=("Arial", 9, "bold"),
            bg="#FFA726",
            fg="white",
            activebackground="#FB8C00",
            relief="raised",
            bd=2,
            command=self.csv_temizle_kopyala
        )
        csv_button.pack(fill="x", pady=(10, 5))

        # Son Kopyalamayı Tekrarla Butonu
        self.son_kopyalama_button = tk.Button(
            main_frame,
            text="📋 Son Kopyalama (---)",
            font=("Arial", 9, "bold"),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            relief="raised",
            bd=2,
            command=self.csv_son_kopyalamayi_tekrarla
        )
        self.son_kopyalama_button.pack(fill="x", pady=(5, 5))

        # Renkli Reçete Listesi Yükle Butonu
        renkli_frame = tk.Frame(main_frame, bg=self.bg_color)
        renkli_frame.pack(fill="x", pady=(5, 5))

        self.renkli_recete_button = tk.Button(
            renkli_frame,
            text="🔴🟢 Renkli Reçete Yükle",
            font=("Arial", 9, "bold"),
            bg="#9C27B0",
            fg="white",
            activebackground="#7B1FA2",
            relief="raised",
            bd=2,
            command=self.renkli_liste_penceresi_ac
        )
        self.renkli_recete_button.pack(fill="x")

        # Renkli Reçete Durum Label
        self.renkli_recete_label = tk.Label(
            renkli_frame,
            text="Yüklü değil",
            font=("Arial", 7),
            bg="#E1BEE7",
            fg="#4A148C",
            anchor="center",
            padx=5,
            pady=2
        )
        self.renkli_recete_label.pack(fill="x")

        # Öğrenme Modu Checkbox
        ogrenme_frame = tk.Frame(main_frame, bg=self.bg_color)
        ogrenme_frame.pack(fill="x", pady=(5, 5))

        self.ogrenme_modu_aktif = tk.BooleanVar(value=False)
        self.ogrenme_modu_checkbox = tk.Checkbutton(
            ogrenme_frame,
            text="🎓 Öğrenme Modu",
            variable=self.ogrenme_modu_aktif,
            font=("Arial", 9, "bold"),
            bg=self.bg_color,
            fg="#00897B",
            activebackground=self.bg_color,
            selectcolor="#1e1e1e",
            command=self._ogrenme_modu_toggle
        )
        self.ogrenme_modu_checkbox.pack(fill="x")

        self.ogrenme_modu_label = tk.Label(
            ogrenme_frame,
            text="Kapalı - Mesajlı ilaçlarda durmaz",
            font=("Arial", 7),
            bg="#455A64",
            fg="#B0BEC5",
            anchor="center",
            padx=5,
            pady=2
        )
        self.ogrenme_modu_label.pack(fill="x")

        # Görev Raporları Butonu
        report_btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        report_btn_frame.pack(fill="x", pady=(0, 5))

        self.report_button = tk.Button(
            report_btn_frame,
            text="📊 Görev Raporları",
            font=("Arial", 9),
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            width=30,
            height=1,
            relief="raised",
            bd=1,
            command=self.gorev_raporlari_goster
        )
        self.report_button.pack()

        # İstatistikler
        stats_frame = tk.Frame(main_frame, bg=self.bg_color)
        stats_frame.pack(fill="x", pady=(0, 10))

        stats_title = tk.Label(
            stats_frame,
            text="Bu Oturum:",
            font=("Arial", 9, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        stats_title.pack()

        self.stats_label = tk.Label(
            stats_frame,
            text="Rç:0 | Takipli:0 | İlaç:0 | R:0 | Süre:0s 0ms | Ort(5):-",
            font=("Arial", 8),
            bg="#C8E6C9",
            fg="#1B5E20",
            relief="sunken",
            bd=1,
            height=2
        )
        self.stats_label.pack(fill="x", pady=2)

        # Yeniden başlatma sayacı
        self.restart_label = tk.Label(
            stats_frame,
            text="Program 0 kez yeniden başlatıldı",
            font=("Arial", 7),
            bg="#FFF3E0",
            fg="#E65100",
            relief="sunken",
            bd=1,
            height=1
        )
        self.restart_label.pack(fill="x", pady=(2, 0))

        # Durum
        status_frame = tk.Frame(main_frame, bg=self.bg_color)
        status_frame.pack(fill="both", expand=True)

        status_title = tk.Label(
            status_frame,
            text="Durum:",
            font=("Arial", 8, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        status_title.pack()

        self.status_label = tk.Label(
            status_frame,
            text="Hazır",
            font=("Arial", 8),
            bg="#A5D6A7",
            fg="#1B5E20",
            relief="sunken",
            bd=1,
            height=2
        )
        self.status_label.pack(fill="x", pady=2)

        # Log alanı
        log_title = tk.Label(
            status_frame,
            text="İşlem Logu:",
            font=("Arial", 7, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        log_title.pack(pady=(5, 0))

        # ScrolledText ile kaydırılabilir log alanı
        self.log_text = scrolledtext.ScrolledText(
            status_frame,
            font=("Arial", 7),
            bg="#E8F5E9",
            fg="#2E7D32",
            relief="sunken",
            bd=1,
            height=10,
            wrap=tk.WORD,
            state="disabled"  # Kullanıcı yazamasın
        )
        self.log_text.pack(fill="both", expand=True)

        # Stats timer - başlangıçta KAPALI (BAŞLAT'a basınca açılacak)
        self.stats_timer_running = False

    def load_grup_verileri(self):
        """Başlangıçta grup verilerini yükle"""
        for grup in ["C", "A", "B", "GK"]:
            son_recete = self.grup_durumu.son_recete_al(grup)
            if son_recete:
                self.grup_labels[grup].config(text=son_recete)
            else:
                self.grup_labels[grup].config(text="—")

            # Rapor kontrol reçetesini göster
            rk_recete = self.grup_durumu.son_recete_al_fonksiyon(grup, "rapor_kontrol")
            if rk_recete:
                self.grup_rapor_kontrol_labels[grup].config(text=f"RK: {rk_recete}")
            else:
                self.grup_rapor_kontrol_labels[grup].config(text="")

            # Aylık istatistikleri göster
            self.aylik_istatistik_guncelle(grup)

            # ✅ BİTTİ bilgisini göster
            self.bitti_bilgisi_guncelle(grup)

    def aylik_istatistik_guncelle(self, grup):
        """Grubun aylık istatistiklerini label'a yaz"""
        stats = self.grup_durumu.istatistik_al(grup)
        recete_sayi = stats.get("toplam_recete", 0)
        takip_sayi = stats.get("toplam_takip", 0)
        takipli_recete_sayi = stats.get("toplam_takipli_recete", 0)
        sure_saniye = stats.get("toplam_sure", 0.0)

        # Süreyi dakika/saat formatına çevir (milisaniye ile)
        milisaniye = int((sure_saniye * 1000) % 1000)
        if sure_saniye >= 3600:
            sure_saat = int(sure_saniye // 3600)
            sure_dk = int((sure_saniye % 3600) // 60)
            sure_text = f"{sure_saat}s{sure_dk}dk {milisaniye}ms"
        elif sure_saniye >= 60:
            sure_dk = int(sure_saniye // 60)
            sure_sn = int(sure_saniye % 60)
            sure_text = f"{sure_dk}dk {sure_sn}s {milisaniye}ms"
        else:
            sure_text = f"{int(sure_saniye)}s {milisaniye}ms"

        text = f"Ay: Rç:{recete_sayi} | Takipli:{takipli_recete_sayi} | İlaç:{takip_sayi} | {sure_text}"
        self.grup_stat_labels[grup].config(text=text)

    def bitti_bilgisi_guncelle(self, grup):
        """
        Grubun BİTTİ bilgisini label'a yaz ve göster/gizle

        Args:
            grup: Grup adı ("A", "B" veya "C")
        """
        tarih, sayisi = self.grup_durumu.bitti_bilgisi_al(grup)

        if tarih and sayisi is not None:
            # BİTTİ bilgisi var - göster
            text = f"✅ BİTTİ {tarih} | {sayisi} reçete"
            self.grup_bitti_labels[grup].config(text=text)
            self.grup_bitti_labels[grup].pack(fill="x", pady=(0, 2))  # Göster
        else:
            # BİTTİ bilgisi yok - gizle
            self.grup_bitti_labels[grup].pack_forget()

    def grup_secildi_click(self, grup):
        """Grup alanına tıklandığında (frame veya label tıklaması)"""
        # Radio button'ı seç
        self.secili_grup.set(grup)
        # Normal grup seçimi işlemini çalıştır
        self.grup_secildi(grup)

    def grup_secildi(self, grup):
        """Grup seçildiğinde"""
        logger.info(f"Grup {grup} seçildi")
        self.log_ekle(f"📁 Grup {grup} seçildi")

        # ✅ Aktif modu ayarla (sadece manuel seçimde, tumu_kontrol değilse)
        if not self.tumu_kontrol_aktif:
            self.grup_durumu.aktif_mod_ayarla(grup)
            logger.info(f"Aktif mod: {grup}")

        # Tüm grupların rengini normale çevir (açık yeşil)
        for g in ["C", "A", "B", "GK"]:
            if g in self.grup_frames:
                # Ana frame
                self.grup_frames[g]['main'].config(bg="#E8F5E9")
                # Alt widget'lar
                for widget in self.grup_frames[g]['widgets']:
                    try:
                        widget.config(bg="#E8F5E9")
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")  # X butonu gibi bazı widget'larda bg olmayabilir

        # Seçili grubu mavi yap
        if grup in self.grup_frames:
            # Ana frame
            self.grup_frames[grup]['main'].config(bg="#BBDEFB")  # Açık mavi
            # Alt widget'lar
            for widget in self.grup_frames[grup]['widgets']:
                try:
                    widget.config(bg="#BBDEFB")
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

        # Son reçete numarasını kontrol et
        son_recete = self.grup_durumu.son_recete_al(grup)

        # Medula hazırlama + reçete akışını thread'de başlat
        def _grup_akisi():
            """Medula'yı hazırla ve gruba göre reçete akışını başlat"""
            # Önce Medula'yı hazırla ve bağlan
            if not self.medula_hazirla_ve_baglan():
                self.root.after(0, lambda: self.log_ekle("❌ Medula hazırlanamadı, işlem iptal"))
                return

            if son_recete:
                self.root.after(0, lambda r=son_recete: self.log_ekle(f"📋 Son reçete: {r}"))
                self.recete_ac(grup, son_recete)
            else:
                self.root.after(0, lambda: self.log_ekle(f"ℹ İlk reçete - Başlatılıyor..."))
                self.ilk_recete_akisi(grup)

        thread = threading.Thread(target=_grup_akisi)
        thread.daemon = True
        thread.start()

    def medula_hazirla_ve_baglan(self):
        """
        Medula penceresini hazırla ve bağlan.
        1. Pencere var mı kontrol et
        2. Yoksa aç ve giriş yap
        3. Varsa ama düşmüşse: geri butonu → giriş butonu (3 kere) → taskkill
        4. Toplam 7 deneme, her turda 3 giriş denemesi, sonra taskkill

        Returns:
            bool: Medula hazır ve bağlı ise True
        """
        from botanik_bot import medula_taskkill, medula_ac_ve_giris_yap
        from pywinauto import Desktop
        import win32gui
        import win32con

        MAX_TUR = 7  # Toplam deneme turu

        for tur in range(1, MAX_TUR + 1):
            self.root.after(0, lambda t=tur: self.log_ekle(f"🔄 Medula hazırlama turu {t}/{MAX_TUR}"))

            # ─── 1. Pencere var mı kontrol et ───
            medula_hwnd = None
            try:
                desktop = Desktop(backend="uia")
                for window in desktop.windows():
                    try:
                        if "MEDULA" in window.window_text():
                            medula_hwnd = window.handle
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Pencere kontrol hatası: {e}")

            # ─── 2. Pencere yok → aç ve giriş yap ───
            if not medula_hwnd:
                self.root.after(0, lambda: self.log_ekle("📍 MEDULA penceresi bulunamadı, açılıyor..."))
                try:
                    if medula_ac_ve_giris_yap(self.medula_settings):
                        time.sleep(1)
                        if self.bot is None:
                            self.bot = BotanikBot()
                        if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                            self.root.after(0, lambda: self.log_ekle("✓ MEDULA açıldı ve bağlandı"))
                            try:
                                console_pencereyi_ayarla()
                            except Exception:
                                pass
                            return True
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açıldı ama bağlantı kurulamadı"))
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açılamadı"))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Hata: {err}"))

                if tur < MAX_TUR:
                    time.sleep(2)
                continue

            # ─── 3. Pencere var → restore et ve bağlan ───
            try:
                placement = win32gui.GetWindowPlacement(medula_hwnd)
                if placement[1] == win32con.SW_SHOWMINIMIZED:
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)

                win32gui.SetForegroundWindow(medula_hwnd)
                time.sleep(0.2)
            except Exception as e:
                logger.debug(f"Pencere restore hatası: {e}")

            # Bot'a bağlan
            if self.bot is None:
                self.bot = BotanikBot()

            if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                self.root.after(0, lambda: self.log_ekle("⚠ MEDULA penceresine bağlanılamadı, taskkill..."))
                medula_taskkill()
                self.bot = None
                if tur < MAX_TUR:
                    time.sleep(2)
                continue

            # ─── 4. Bağlandı, oturum düşmüş mü kontrol et ───
            if self.bot.cikis_butonu_var_mi() or self.bot.genel_duyurular_sayfasi_mi():
                self.root.after(0, lambda: self.log_ekle("✓ MEDULA oturumu aktif"))
                try:
                    console_pencereyi_ayarla()
                except Exception:
                    pass
                return True

            # ─── 5. Oturum düşmüş → geri butonu + giriş butonu ───
            self.root.after(0, lambda: self.log_ekle("⚠ Oturum düşmüş, kurtarma başlıyor..."))

            # Önce geri butonuna bas
            try:
                self.bot.geri_don_butonuna_tikla()
                time.sleep(0.5)
            except Exception:
                pass

            # 3 kere giriş butonuna bas
            giris_basarili = False
            for giris_deneme in range(1, 4):
                self.root.after(0, lambda d=giris_deneme: self.log_ekle(f"  🔑 Giriş denemesi {d}/3..."))
                try:
                    if self.bot.giris_butonuna_tikla():
                        time.sleep(2)
                        # Önce Genel Duyurular sayfası kontrol et (giriş başarılı demek)
                        if self.bot.genel_duyurular_sayfasi_mi():
                            self.root.after(0, lambda: self.log_ekle("✓ Genel Duyurular sayfası tespit edildi - giriş başarılı"))
                            giris_basarili = True
                            break
                        # Çıkış butonu kontrolü (yedek)
                        if self.bot.cikis_butonu_var_mi():
                            self.root.after(0, lambda: self.log_ekle("✓ Giriş başarılı"))
                            giris_basarili = True
                            break
                        else:
                            self.root.after(0, lambda: self.log_ekle("  ⚠ Giriş butonu tıklandı ama oturum açılmadı"))
                    else:
                        self.root.after(0, lambda: self.log_ekle("  ⚠ Giriş butonu bulunamadı"))
                except Exception as e:
                    logger.debug(f"Giriş denemesi hatası: {e}")

                time.sleep(1)

            if giris_basarili:
                try:
                    console_pencereyi_ayarla()
                except Exception:
                    pass
                return True

            # ─── 6. 3 giriş denemesi başarısız → taskkill ───
            self.root.after(0, lambda: self.log_ekle("⚠ 3 giriş denemesi başarısız, taskkill yapılıyor..."))
            medula_taskkill()
            self.taskkill_sayaci += 1
            if self.aktif_oturum_id:
                self.database.artir(self.aktif_oturum_id, "taskkill_sayisi")
            self.bot = None

            if tur < MAX_TUR:
                time.sleep(2)

        # 7 tur başarısız
        self.root.after(0, lambda: self.log_ekle(f"❌ {MAX_TUR} deneme başarısız, Medula hazırlanamadı!"))
        self.root.after(0, self.hata_sesi_calar)
        return False

    def _mevcut_ekrandan_cik(self):
        """
        Mevcut ekrandan kademeli kurtarma ile cik.
        Sira: Geri Don -> Ana Sayfa -> ESC -> taskkill
        """
        import pyautogui

        # 1. Geri Don butonu
        try:
            self.root.after(0, lambda: self.log_ekle("◀ Geri Don butonu deneniyor..."))
            if self.bot.geri_don_butonuna_tikla():
                time.sleep(0.5)
                self.root.after(0, lambda: self.log_ekle("✓ Geri Don basarili"))
                return True
        except Exception as e:
            logger.debug("Geri Don hatasi: {}".format(e))

        # 2. Ana Sayfa butonu
        try:
            self.root.after(0, lambda: self.log_ekle("◀ Ana Sayfa butonu deneniyor..."))
            if self.bot.ana_sayfaya_don():
                time.sleep(0.75)
                self.root.after(0, lambda: self.log_ekle("✓ Ana Sayfa basarili"))
                return True
        except Exception as e:
            logger.debug("Ana Sayfa hatasi: {}".format(e))

        # 3. ESC tuslari
        try:
            self.root.after(0, lambda: self.log_ekle("◀ ESC tuslari deneniyor..."))
            for _ in range(3):
                pyautogui.press('escape')
                time.sleep(0.2)
            time.sleep(0.5)
            # ESC sonrasi ana sayfaya donmeyi dene
            try:
                self.bot.ana_sayfaya_don()
                time.sleep(0.5)
            except Exception:
                pass
            self.root.after(0, lambda: self.log_ekle("✓ ESC ile kurtarma denendi"))
            return True
        except Exception as e:
            logger.debug("ESC hatasi: {}".format(e))

        # 4. Hicbiri calismadiysa - taskkill + yeniden giris
        self.root.after(0, lambda: self.log_ekle("⚠ Ekrandan cikilamadi, TASKKILL yapiliyor..."))
        try:
            self.bot = None
            if self.medula_ac_ve_giris_5_deneme_yap():
                self.root.after(0, lambda: self.log_ekle("✓ MEDULA yeniden baslatildi"))
                return True
            else:
                self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden baslatma basarisiz"))
                return False
        except Exception as e:
            logger.error("Taskkill kurtarma hatasi: {}".format(e))
            return False

    def medula_ac_ve_giris_5_deneme_yap(self):
        """
        MEDULA'yı açmayı 5 kere dener. İlk denemede:
        1. Medula penceresi mevcutsa, oturumu yenilemeyi dener (3 kere Ana Sayfa butonu)
        2. Başarısız olursa, taskkill ile kapatıp yeniden açar

        Diğer denemelerde:
        1. Taskkill ile MEDULA'yı kapatır
        2. MEDULA'yı açıp giriş yapar

        Returns:
            bool: Başarılıysa True, 5 deneme de başarısız olursa False
        """
        MAX_DENEME = 5

        for deneme in range(1, MAX_DENEME + 1):
            self.root.after(0, lambda d=deneme: self.log_ekle(f"🔄 MEDULA açma denemesi {d}/{MAX_DENEME}"))

            # İLK DENEME: Önce mevcut Medula penceresini yenilemeyi dene
            if deneme == 1:
                self.root.after(0, lambda: self.log_ekle("📍 Mevcut Medula penceresi kontrol ediliyor..."))

                # Medula penceresini kontrol et
                medula_mevcut = False
                try:
                    from pywinauto import Desktop
                    desktop = Desktop(backend="uia")
                    for window in desktop.windows():
                        try:
                            if "MEDULA" in window.window_text():
                                medula_mevcut = True
                                self.root.after(0, lambda: self.log_ekle("✓ MEDULA penceresi bulundu"))
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Pencere kontrolü hatası: {e}")

                # Eğer Medula mevcutsa, doğrudan bağlan (oturum yenilemesi YAPMA!)
                if medula_mevcut:
                    self.root.after(0, lambda: self.log_ekle("🔄 Mevcut MEDULA'ya bağlanılıyor..."))

                    try:
                        # Bot yoksa oluştur
                        if self.bot is None:
                            self.bot = BotanikBot()

                        # Bağlantı kurmayı dene
                        if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                            self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

                            # NOT: medula_oturumu_yenile() KALDIRILDI!
                            # Giriş butonuna basarak reçeteden çıkılıyordu

                            # Konsol penceresini MEDULA'nın sağına yerleştir
                            try:
                                console_pencereyi_ayarla()
                                self.root.after(0, lambda: self.log_ekle("✓ Konsol penceresi yerleştirildi"))
                            except Exception as e:
                                logger.error(f"Konsol yerleştirme hatası: {e}", exc_info=True)
                                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Konsol yerleştirme hatası: {err}"))

                            return True
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ Medula penceresine bağlanılamadı"))
                    except Exception as e:
                        logger.error(f"Bağlantı hatası: {e}")
                        self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Bağlantı hatası: {err}"))

                    # Bağlantı başarısız, taskkill yap
                    self.root.after(0, lambda: self.log_ekle("⚠ Bağlantı başarısız, taskkill yapılacak..."))

            # TASKKILL VE YENİDEN AÇ (İlk denemede oturum yenileme başarısızsa veya diğer denemelerde)
            # 1. Taskkill ile MEDULA'yı kapat
            self.root.after(0, lambda: self.log_ekle("📍 MEDULA kapatılıyor (taskkill)..."))
            if medula_taskkill():
                self.taskkill_sayaci += 1
                self.root.after(0, lambda: self.log_ekle(f"✓ MEDULA kapatıldı (Taskkill: {self.taskkill_sayaci})"))

                # Database'e kaydet
                if self.aktif_oturum_id:
                    self.database.artir(self.aktif_oturum_id, "taskkill_sayisi")
                    if self.session_logger:
                        self.session_logger.warning(f"Taskkill yapıldı (#{self.taskkill_sayaci})")
            else:
                self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız, devam ediliyor..."))

            # Taskkill sonrası bekleme
            time.sleep(1)

            # 2. MEDULA'yı aç ve giriş yap
            self.root.after(0, lambda: self.log_ekle("📍 MEDULA açılıyor ve giriş yapılıyor..."))

            try:
                if medula_ac_ve_giris_yap(self.medula_settings):
                    self.root.after(0, lambda: self.log_ekle("✓ MEDULA açıldı ve giriş yapıldı"))
                    time.sleep(1.5)

                    # Başarılı, bot'a bağlanmayı dene
                    if self.bot is None:
                        self.bot = BotanikBot()

                    if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                        self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

                        # Konsol penceresini MEDULA'nın sağına yerleştir
                        try:
                            console_pencereyi_ayarla()
                            self.root.after(0, lambda: self.log_ekle("✓ Konsol penceresi yerleştirildi"))
                        except Exception as e:
                            logger.error(f"Konsol yerleştirme hatası: {e}", exc_info=True)
                            self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Konsol yerleştirme hatası: {err}"))

                        return True
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Bağlantı kurulamadı, yeniden denenecek..."))
                else:
                    self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açılamadı veya giriş yapılamadı"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Hata: {err}"))

            # Son deneme değilse biraz bekle
            if deneme < MAX_DENEME:
                self.root.after(0, lambda: self.log_ekle("⏳ 3 saniye bekleniyor..."))
                time.sleep(3)

        # 5 deneme de başarısız
        self.root.after(0, lambda: self.log_ekle("❌ 5 deneme de başarısız oldu!"))
        return False

    def recete_ac(self, grup, recete_no):
        """Reçeteyi otomatik aç (thread'de çalışır) - 3 deneme + taskkill mantığı ile"""
        try:
            from botanik_bot import masaustu_medula_ac, medula_giris_yap, medula_taskkill
            import pyautogui

            MAX_DENEME = 3  # Her işlem için maksimum deneme sayısı

            # Mevcut recete ekranindaysa kademeli kurtarma ile cik
            if self.bot is not None:
                self._mevcut_ekrandan_cik()
                # Pencereyi yenile (elementler degismis olabilir)
                if self.bot is not None:
                    self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                    time.sleep(0.5)

            # Bot yoksa oluştur ve bağlan
            if self.bot is None:
                self.bot = BotanikBot()

                # MEDULA'ya bağlanmayı dene
                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    # MEDULA açık değil, 5 kere deneyerek otomatik olarak aç ve giriş yap
                    self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açık değil, otomatik başlatılıyor (5 deneme)..."))

                    if not self.medula_ac_ve_giris_5_deneme_yap():
                        self.root.after(0, lambda: self.log_ekle("❌ MEDULA açılamadı (5 deneme başarısız)"))
                        self.root.after(0, self.hata_sesi_calar)
                        return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

            # NOT: medula_oturumu_yenile() KALDIRILDI - Giriş butonuna basarak reçeteden çıkılıyordu!
            # Doğrudan Reçete Sorgu'ya gidiyoruz
            time.sleep(0.3)

            # === REÇETE SORGU BUTONU - 3 DENEME ===
            recete_sorgu_acildi = False
            for deneme in range(1, MAX_DENEME + 1):
                self.root.after(0, lambda d=deneme: self.log_ekle(f"🔘 Reçete Sorgu ({d}/{MAX_DENEME})..."))

                if self.bot.recete_sorgu_ac():
                    recete_sorgu_acildi = True
                    break

                # Başarısız - ESC gönder ve Ana Sayfa'ya dön
                self.root.after(0, lambda d=deneme: self.log_ekle(f"⚠ Reçete Sorgu başarısız ({d}/{MAX_DENEME}), kurtarma..."))

                # 3x ESC gönder
                for _ in range(3):
                    pyautogui.press('escape')
                    time.sleep(0.2)

                # Ana Sayfa'ya dön
                if self.bot.ana_sayfaya_don():
                    time.sleep(0.75)
                else:
                    self.root.after(0, lambda: self.log_ekle("⚠ Ana Sayfa bulunamadı"))
                    time.sleep(0.5)

            # 3 deneme de başarısız - TASKKILL
            if not recete_sorgu_acildi:
                self.root.after(0, lambda: self.log_ekle("❌ Reçete Sorgu 3 denemede açılamadı, TASKKILL yapılıyor..."))
                self.bot = None

                if not self.medula_ac_ve_giris_5_deneme_yap():
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA yeniden başlatıldı"))
                time.sleep(1)

                # Son bir deneme daha
                if not self.bot.recete_sorgu_ac():
                    self.root.after(0, lambda: self.log_ekle("❌ Reçete Sorgu açılamadı (taskkill sonrası)"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

            # Reçete Sorgu ekranı açıldı, kısa bekle
            time.sleep(0.75)  # Güvenli hasta takibi için: 0.5 → 0.75

            # Pencereyi yenile (reçete sorgu ekranı için)
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # === REÇETE NUMARASI YAZMA - 3 DENEME ===
            recete_yazildi = False
            for deneme in range(1, MAX_DENEME + 1):
                self.root.after(0, lambda d=deneme: self.log_ekle(f"✍ Numara yazılıyor ({d}/{MAX_DENEME}): {recete_no}"))

                if self.bot.recete_no_yaz(recete_no):
                    recete_yazildi = True
                    break

                # Başarısız - ESC gönder ve tekrar dene
                self.root.after(0, lambda d=deneme: self.log_ekle(f"⚠ Numara yazılamadı ({d}/{MAX_DENEME}), kurtarma..."))

                # 3x ESC gönder
                for _ in range(3):
                    pyautogui.press('escape')
                    time.sleep(0.2)

                # Ana Sayfa'ya dön ve Reçete Sorgu'ya tekrar git
                if self.bot.ana_sayfaya_don():
                    time.sleep(0.75)
                    if self.bot.recete_sorgu_ac():
                        time.sleep(0.75)
                        self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # 3 deneme de başarısız - TASKKILL
            if not recete_yazildi:
                self.root.after(0, lambda: self.log_ekle("❌ Numara 3 denemede yazılamadı, TASKKILL yapılıyor..."))
                self.bot = None

                if not self.medula_ac_ve_giris_5_deneme_yap():
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA yeniden başlatıldı"))
                time.sleep(1)

                # Tam akışı tekrar dene
                if self.bot.recete_sorgu_ac():
                    time.sleep(0.75)
                    self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                    if not self.bot.recete_no_yaz(recete_no):
                        self.root.after(0, lambda: self.log_ekle("❌ Numara yazılamadı (taskkill sonrası)"))
                        self.root.after(0, self.hata_sesi_calar)
                        return

            # === SORGULA BUTONU - 3 DENEME ===
            sorgula_basarili = False
            for deneme in range(1, MAX_DENEME + 1):
                self.root.after(0, lambda d=deneme: self.log_ekle(f"🔍 Sorgula ({d}/{MAX_DENEME})..."))

                if self.bot.sorgula_butonuna_tikla():
                    sorgula_basarili = True
                    break

                # Başarısız - ESC gönder ve tekrar dene
                self.root.after(0, lambda d=deneme: self.log_ekle(f"⚠ Sorgula başarısız ({d}/{MAX_DENEME}), kurtarma..."))

                # 3x ESC gönder
                for _ in range(3):
                    pyautogui.press('escape')
                    time.sleep(0.2)

                # Ana Sayfa'ya dön ve tam akışı tekrar dene
                if self.bot.ana_sayfaya_don():
                    time.sleep(0.75)
                    if self.bot.recete_sorgu_ac():
                        time.sleep(0.75)
                        self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                        self.bot.recete_no_yaz(recete_no)
                        time.sleep(0.3)

            # 3 deneme de başarısız - TASKKILL
            if not sorgula_basarili:
                self.root.after(0, lambda: self.log_ekle("❌ Sorgula 3 denemede başarısız, TASKKILL yapılıyor..."))
                self.bot = None

                if not self.medula_ac_ve_giris_5_deneme_yap():
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA yeniden başlatıldı"))
                time.sleep(1)

                # Tam akışı tekrar dene
                if self.bot.recete_sorgu_ac():
                    time.sleep(0.75)
                    self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                    if self.bot.recete_no_yaz(recete_no):
                        time.sleep(0.3)
                        if not self.bot.sorgula_butonuna_tikla():
                            self.root.after(0, lambda: self.log_ekle("❌ Sorgula başarısız (taskkill sonrası)"))
                            self.root.after(0, self.hata_sesi_calar)
                            return

            # Sorgula sonrası popup kontrolü
            time.sleep(0.5)  # Popup için zaman tanı
            try:
                if popup_kontrol_ve_kapat():
                    self.root.after(0, lambda: self.log_ekle("✓ Sorgula sonrası popup kapatıldı"))
                    if self.session_logger:
                        self.session_logger.info("Sorgula sonrası popup kapatıldı")
            except Exception as e:
                logger.warning(f"Sorgula popup kontrol hatası: {e}")

            self.root.after(0, lambda: self.log_ekle(f"✅ Reçete açıldı: {recete_no}"))

            # Tüm pencereleri yerleştir
            self.root.after(0, lambda: self.log_ekle("🖼 Pencereler yerleştiriliyor..."))
            self.tum_pencereleri_yerlestir()
            time.sleep(0.5)

            self.root.after(0, lambda: self.log_ekle("▶ Otomatik olarak başlatılıyor..."))

            # 1 saniye bekle ve otomatik olarak başlat
            time.sleep(1)
            self.root.after(0, self.basla)

        except Exception as e:
            logger.error(f"Reçete açma hatası: {e}")
            self.root.after(0, lambda: self.log_ekle(f"❌ Hata: {e}"))

    def ilk_recete_akisi(self, grup):
        """
        İlk reçete için tam akış (masaüstü simgesi → giriş → reçete listesi → grup seçimi → ilk reçete)
        """
        try:
            # Mevcut recete ekranindaysa kademeli kurtarma ile cik
            if self.bot is not None:
                self._mevcut_ekrandan_cik()
                # Pencereyi yenile (elementler degismis olabilir)
                if self.bot is not None:
                    self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                    time.sleep(0.5)

            from botanik_bot import (
                masaustu_medula_ac,
                medula_giris_yap,
                recete_listesi_ac,
                donem_sec,
                grup_butonuna_tikla,
                bulunamadi_mesaji_kontrol,
                ilk_recete_ac,
                SistemselHataException
            )
            from pywinauto import Desktop
            import win32gui
            import win32con

            self.root.after(0, lambda: self.log_ekle("🚀 Grup {} için tam akış başlatılıyor...".format(grup)))

            # MEDULA zaten açık mı kontrol et
            medula_zaten_acik = False
            medula_hwnd = None

            try:
                desktop = Desktop(backend="uia")
                for window in desktop.windows():
                    try:
                        if "MEDULA" in window.window_text():
                            medula_zaten_acik = True
                            medula_hwnd = window.handle
                            self.root.after(0, lambda: self.log_ekle("ℹ MEDULA zaten açık, restore ediliyor..."))
                            break
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")
            except Exception as e:
                logger.debug(f"MEDULA kontrol hatası: {e}")

            # Eğer MEDULA açıksa, restore et ve giriş adımını atla
            if medula_zaten_acik and medula_hwnd:
                try:
                    # Minimize ise restore et
                    placement = win32gui.GetWindowPlacement(medula_hwnd)
                    current_state = placement[1]

                    if current_state == win32con.SW_SHOWMINIMIZED:
                        self.root.after(0, lambda: self.log_ekle("📍 MEDULA minimize durumda, restore ediliyor..."))
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.5)

                    # Koordinat kontrolü
                    rect = win32gui.GetWindowRect(medula_hwnd)
                    if rect[0] < -10000 or rect[1] < -10000:
                        self.root.after(0, lambda: self.log_ekle("📍 MEDULA gizli konumda, görünür yapılıyor..."))
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.3)
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_SHOW)
                        time.sleep(0.3)

                    self.root.after(0, lambda: self.log_ekle("✓ MEDULA restore edildi"))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA restore hatası: {err}"))

                # Bot'a bağlan
                self.root.after(0, lambda: self.log_ekle("🔌 MEDULA'ya bağlanılıyor..."))
                if self.bot is None:
                    self.bot = BotanikBot()

                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA'ya bağlanılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                time.sleep(0.5)

                # NOT: medula_oturumu_yenile() KALDIRILDI - Giriş butonuna basarak reçeteden çıkılıyordu!
                # Doğrudan Reçete Listesi'ne gidiyoruz

            else:
                # MEDULA açık değil, 5 kere deneyerek aç ve giriş yap
                self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açık değil, otomatik başlatılıyor (5 deneme)..."))

                if not self.medula_ac_ve_giris_5_deneme_yap():
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA açılamadı (5 deneme başarısız)"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                time.sleep(1)  # Adım arası bekleme

            # 4. Reçete Listesi'ne tıkla
            self.root.after(0, lambda: self.log_ekle("📋 Reçete Listesi açılıyor..."))
            try:
                if not recete_listesi_ac(self.bot):
                    self.root.after(0, lambda: self.log_ekle("❌ Reçete Listesi açılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return
            except SistemselHataException as e:
                self.root.after(0, lambda: self.log_ekle(f"⚠️ SİSTEMSEL HATA: {e}"))
                self.root.after(0, lambda: self.log_ekle("🔄 MEDULA YENİDEN BAŞLATILIYOR..."))
                from botanik_bot import medula_yeniden_baslat_ve_giris_yap
                # Son reçeteden devam et
                son_recete = self.grup_durumu.son_recete_al(self.grup)
                if son_recete:
                    self.root.after(0, lambda r=son_recete: self.log_ekle(f"📍 Kaldığı yerden devam edilecek: {r}"))
                if medula_yeniden_baslat_ve_giris_yap(self.bot, self.grup, son_recete):
                    self.root.after(0, lambda: self.log_ekle("✅ MEDULA başarıyla yeniden başlatıldı"))
                    # Göreve devam et
                    self.root.after(100, self.baslat_worker)
                    return
                else:
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatma başarısız!"))
                    self.root.after(0, self.hata_sesi_calar)
                    self.root.after(0, self.gorevi_bitir)
                    return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 5. Dönem seç (index=2, yani 3. sıradaki)
            self.root.after(0, lambda: self.log_ekle("📅 Dönem seçiliyor (3. sıra)..."))
            if not donem_sec(self.bot, index=2):
                self.root.after(0, lambda: self.log_ekle("❌ Dönem seçilemedi"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 6. Grup butonuna tıkla
            self.root.after(0, lambda: self.log_ekle(f"📁 {grup} grubu sorgulanıyor..."))
            if not grup_butonuna_tikla(self.bot, grup):
                self.root.after(0, lambda: self.log_ekle(f"❌ {grup} grubu sorgulanamadı"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 7. "Bulunamadı" mesajı kontrolü
            self.root.after(0, lambda: self.log_ekle("🔍 Reçete varlığı kontrol ediliyor..."))
            if bulunamadi_mesaji_kontrol(self.bot):
                # Mesaj var, 2. dönemi dene (index=1)
                self.root.after(0, lambda: self.log_ekle("⚠ 3. dönemde reçete yok, 2. dönem deneniyor..."))

                # Dönem seç (index=1, yani 2. sıradaki)
                if not donem_sec(self.bot, index=1):
                    self.root.after(0, lambda: self.log_ekle("❌ 2. dönem seçilemedi"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                # Pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                time.sleep(1)

                # Grup butonuna tekrar tıkla
                self.root.after(0, lambda: self.log_ekle(f"📁 {grup} grubu (2. dönem) sorgulanıyor..."))
                if not grup_butonuna_tikla(self.bot, grup):
                    self.root.after(0, lambda: self.log_ekle(f"❌ {grup} grubu sorgulanamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                # Pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                time.sleep(1)

                # Tekrar kontrol et
                if bulunamadi_mesaji_kontrol(self.bot):
                    self.root.after(0, lambda: self.log_ekle("❌ 2. dönemde de reçete bulunamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

            # 8. İlk reçete aç
            self.root.after(0, lambda: self.log_ekle("🔘 İlk reçete açılıyor..."))
            if not ilk_recete_ac(self.bot):
                self.root.after(0, lambda: self.log_ekle("❌ İlk reçete açılamadı"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # İlk reçete açıldıktan sonra popup kontrolü
            time.sleep(0.5)  # Popup için zaman tanı
            try:
                if popup_kontrol_ve_kapat():
                    self.root.after(0, lambda: self.log_ekle("✓ İlk reçete popup kapatıldı"))
                    if self.session_logger:
                        self.session_logger.info("İlk reçete popup kapatıldı")
            except Exception as e:
                logger.warning(f"İlk reçete popup kontrol hatası: {e}")

            self.root.after(0, lambda: self.log_ekle("✅ İlk reçete başarıyla açıldı"))

            # Tüm pencereleri yerleştir
            self.root.after(0, lambda: self.log_ekle("🖼 Pencereler yerleştiriliyor..."))
            self.tum_pencereleri_yerlestir()
            time.sleep(0.5)

            self.root.after(0, lambda: self.log_ekle("▶ Otomatik olarak başlatılıyor..."))

            # 1 saniye bekle ve otomatik olarak başlat
            time.sleep(1)
            self.root.after(0, self.basla)

        except Exception as e:
            logger.error(f"İlk reçete akışı hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Hata: {err}"))
            self.root.after(0, self.hata_sesi_calar)

    def grup_sifirla(self, grup):
        """X butonuna basıldığında grubu sıfırla"""
        self.grup_durumu.grup_sifirla(grup)
        self.grup_labels[grup].config(text="—")
        self.grup_rapor_kontrol_labels[grup].config(text="")
        self.aylik_istatistik_guncelle(grup)  # Aylık istatistiği de güncelle
        self.log_ekle(f"Grup {grup} sıfırlandı")
        logger.info(f"Grup {grup} sıfırlandı")

    def renkli_recete_yukle(self):
        """Renkli reçete listesini Excel'den yükle"""
        dosya_yolu = filedialog.askopenfilename(
            title="Renkli Reçete Listesi Seçin",
            filetypes=[
                ("Excel dosyaları", "*.xlsx *.xls"),
                ("Tüm dosyalar", "*.*")
            ],
            initialdir=Path.home() / "Desktop"
        )

        if not dosya_yolu:
            return  # Kullanıcı iptal etti

        # Excel'i yükle
        basari, mesaj, kayit_sayisi = self.renkli_recete.excel_yukle(dosya_yolu)

        if basari:
            self.renkli_recete_label.config(
                text=self.renkli_recete.durum_bilgisi(),
                bg="#C8E6C9",  # Yeşil - başarılı
                fg="#1B5E20"
            )
            self.log_ekle(f"✅ Renkli reçete: {mesaj}")
            logger.info(f"Renkli reçete listesi yüklendi: {mesaj}")
        else:
            self.renkli_recete_label.config(
                text="Yükleme hatası!",
                bg="#FFCDD2",  # Kırmızı - hata
                fg="#C62828"
            )
            self.log_ekle(f"❌ Renkli reçete: {mesaj}")
            logger.error(f"Renkli reçete yükleme hatası: {mesaj}")
            messagebox.showerror("Hata", mesaj)

    def renkli_recete_temizle(self):
        """Renkli reçete listesini temizle"""
        self.renkli_recete.temizle()
        self.renkli_recete_label.config(
            text="Yüklü değil",
            bg="#E1BEE7",
            fg="#4A148C"
        )
        self.log_ekle("🗑️ Renkli reçete listesi temizlendi")

    def csv_temizle_kopyala(self):
        """Kopyalanmamış + geçerli raporları CSV olarak kaydet ve panoya kopyala"""
        try:
            from datetime import datetime
            import csv
            from pathlib import Path

            # Kopyalanmamış + geçerli raporları al
            raporlar, silinen_sayisi = self.rapor_takip.kopyalanmamis_raporlari_al()

            if not raporlar:
                if silinen_sayisi > 0:
                    self.log_ekle(f"ℹ️ {silinen_sayisi} geçmiş rapor atlandı, kopyalanacak yeni rapor yok")
                else:
                    self.log_ekle("ℹ️ Kopyalanacak yeni rapor yok")
                return

            # Varsayılan dosya adı (tarih-saat damgalı)
            simdi = datetime.now()
            varsayilan_dosya_adi = f"Raporlar_{simdi.strftime('%Y%m%d_%H%M%S')}.csv"

            # Kullanıcıdan dosya adı ve kayıt yeri seç
            dosya_yolu = filedialog.asksaveasfilename(
                title="Raporları Kaydet",
                initialfile=varsayilan_dosya_adi,
                defaultextension=".csv",
                filetypes=[("CSV Dosyaları", "*.csv"), ("Tüm Dosyalar", "*.*")]
            )

            # Kullanıcı iptal ettiyse
            if not dosya_yolu:
                self.log_ekle("ℹ️ Kaydetme iptal edildi")
                return

            # CSV'ye yaz (Mesajlar format: Ad Soyad, Telefon, Rapor Tanısı, Bitiş Tarihi, Kayıt Tarihi)
            with open(dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = ['Ad Soyad', 'Telefon', 'Rapor Tanısı', 'Bitiş Tarihi', 'Kayıt Tarihi']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for rapor in raporlar:
                    writer.writerow({
                        'Ad Soyad': rapor['ad'],
                        'Telefon': rapor['telefon'],
                        'Rapor Tanısı': rapor['tani'],
                        'Bitiş Tarihi': rapor['bitis'],
                        'Kayıt Tarihi': rapor['kayit']
                    })

            # Aynı içeriği SonRaporlar.csv'ye de kaydet (son kopyalama özelliği için)
            son_raporlar_yolu = Path("SonRaporlar.csv")
            with open(son_raporlar_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = ['Ad Soyad', 'Telefon', 'Rapor Tanısı', 'Bitiş Tarihi', 'Kayıt Tarihi']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for rapor in raporlar:
                    writer.writerow({
                        'Ad Soyad': rapor['ad'],
                        'Telefon': rapor['telefon'],
                        'Rapor Tanısı': rapor['tani'],
                        'Bitiş Tarihi': rapor['bitis'],
                        'Kayıt Tarihi': rapor['kayit']
                    })

            # CSV içeriğini panoya kopyala
            with open(dosya_yolu, 'r', encoding='utf-8-sig') as f:
                csv_icerik = f.read()

            self.root.clipboard_clear()
            self.root.clipboard_append(csv_icerik)
            self.root.update()

            # Kopyalanan raporları işaretle
            isaretlenen = self.rapor_takip.kopyalandi_isaretle(raporlar)

            # Dosya adını al (path olmadan)
            dosya_adi = Path(dosya_yolu).name

            # Bildirim
            if silinen_sayisi > 0:
                self.log_ekle(f"✓ {silinen_sayisi} geçmiş rapor atlandı")
            self.log_ekle(f"✓ {len(raporlar)} rapor '{dosya_adi}' olarak kaydedildi ve panoya kopyalandı")

            # Son kopyalama tarihini güncelle
            self.son_kopyalama_tarihi = datetime.now()
            self._guncelle_son_kopyalama_butonu()

        except Exception as e:
            self.log_ekle(f"❌ CSV kopyalama hatası: {e}")
            logger.error(f"CSV kopyalama hatası: {e}")

    def csv_son_kopyalamayi_tekrarla(self):
        """SonRaporlar.csv dosyasını tekrar panoya kopyala"""
        try:
            from pathlib import Path

            son_raporlar_yolu = Path("SonRaporlar.csv")

            if not son_raporlar_yolu.exists():
                self.log_ekle("❌ SonRaporlar.csv dosyası bulunamadı. Önce normal kopyalama yapın.")
                return

            # Dosyayı oku ve panoya kopyala
            with open(son_raporlar_yolu, 'r', encoding='utf-8-sig') as f:
                csv_icerik = f.read()

            # Satır sayısını hesapla (header hariç)
            satir_sayisi = csv_icerik.count('\n') - 1
            if satir_sayisi < 0:
                satir_sayisi = 0

            self.root.clipboard_clear()
            self.root.clipboard_append(csv_icerik)
            self.root.update()

            self.log_ekle(f"✓ Son kopyalama ({satir_sayisi} rapor) tekrar panoya kopyalandı")

        except Exception as e:
            self.log_ekle(f"❌ Son kopyalama hatası: {e}")
            logger.error(f"Son kopyalama hatası: {e}")

    def _guncelle_son_kopyalama_butonu(self):
        """Son kopyalama butonunun metnini güncelle"""
        if self.son_kopyalama_button and self.son_kopyalama_tarihi:
            tarih_str = self.son_kopyalama_tarihi.strftime("%d/%m/%Y %H:%M")
            self.son_kopyalama_button.config(text=f"📋 Son Kopyalama ({tarih_str})")

    def hata_sesi_calar(self):
        """Hata durumunda 3 kez bip sesi çıkar"""
        def calar():
            try:
                for _ in range(3):
                    winsound.Beep(1000, 300)  # 1000Hz, 300ms
                    time.sleep(0.2)
            except Exception as e:
                logger.debug(f"Operation failed: {type(e).__name__}")

        thread = threading.Thread(target=calar)
        thread.daemon = True
        thread.start()

    def log_ekle(self, mesaj):
        """Log alanına mesaj ekle ve otomatik kaydır"""
        self.log_gecmisi.append(mesaj)
        if len(self.log_gecmisi) > 100:  # Daha fazla log saklayalım
            self.log_gecmisi = self.log_gecmisi[-100:]

        # ScrolledText'e yaz
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", "\n".join(self.log_gecmisi))
        self.log_text.config(state="disabled")

        # Otomatik kaydır (en alta)
        self.log_text.see(tk.END)

    def create_settings_tab(self, parent):
        """Ayarlar sekmesi içeriğini oluştur - Dört alt sekme ile"""
        # Alt sekmeler için notebook oluştur
        settings_notebook = ttk.Notebook(parent)
        settings_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Fonksiyon Ayarları sekmesi (YENİ - en başta)
        fonksiyon_tab = tk.Frame(settings_notebook, bg='#F3E5F5')  # Mor tonu
        settings_notebook.add(fonksiyon_tab, text="  Fonksiyonlar  ")

        # Giriş Ayarları sekmesi
        giris_tab = tk.Frame(settings_notebook, bg='#E3F2FD')
        settings_notebook.add(giris_tab, text="  Giriş Ayarları  ")

        # Timing Ayarları sekmesi
        timing_tab = tk.Frame(settings_notebook, bg='#E8F5E9')
        settings_notebook.add(timing_tab, text="  Timing Ayarları  ")

        # İnsan Davranışı sekmesi
        insan_tab = tk.Frame(settings_notebook, bg='#FFF3E0')
        settings_notebook.add(insan_tab, text="  İnsan Davranışı  ")

        # İçerikleri oluştur
        self.create_fonksiyon_ayarlari_tab(fonksiyon_tab)
        self.create_giris_ayarlari_tab(giris_tab)
        self.create_timing_ayarlari_tab(timing_tab)
        self.create_insan_davranisi_tab(insan_tab)

    def create_fonksiyon_ayarlari_tab(self, parent):
        """Fonksiyon Ayarları sekmesi - İlaç Takip, Rapor Toplama, Rapor Kontrol"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#F3E5F5')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Başlık
        tk.Label(
            main_frame,
            text="Aktif Fonksiyonlar",
            font=("Arial", 12, "bold"),
            bg='#F3E5F5',
            fg='#4A148C'
        ).pack(pady=(0, 5))

        tk.Label(
            main_frame,
            text="Her reçete için hangi işlemlerin yapılacağını seçin",
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#7B1FA2'
        ).pack(pady=(0, 15))

        # Fonksiyon seçim frame'i
        fonksiyon_frame = tk.LabelFrame(
            main_frame,
            text="Reçete İşlemleri",
            font=("Arial", 10, "bold"),
            bg='#F3E5F5',
            fg='#4A148C',
            padx=15,
            pady=15
        )
        fonksiyon_frame.pack(fill="x", pady=(0, 10))

        # Checkbox değişkenleri
        self.ilac_takip_var = tk.BooleanVar(value=self.grup_durumu.fonksiyon_ayari_al("ilac_takip_aktif"))
        self.rapor_toplama_var = tk.BooleanVar(value=self.grup_durumu.fonksiyon_ayari_al("rapor_toplama_aktif"))
        self.rapor_kontrol_var = tk.BooleanVar(value=self.grup_durumu.fonksiyon_ayari_al("rapor_kontrol_aktif"))

        # 1. İlaç Takip
        ilac_frame = tk.Frame(fonksiyon_frame, bg='#F3E5F5')
        ilac_frame.pack(fill="x", pady=5)

        ilac_checkbox = tk.Checkbutton(
            ilac_frame,
            text="İlaç Takip",
            variable=self.ilac_takip_var,
            font=("Arial", 10, "bold"),
            bg='#F3E5F5',
            fg='#1B5E20',
            activebackground='#F3E5F5',
            selectcolor='#E1BEE7',
            command=self.fonksiyon_ayarlarini_kaydet
        )
        ilac_checkbox.pack(side="left")

        tk.Label(
            ilac_frame,
            text="Bizden alınmayan ilaçları takip et",
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#666666'
        ).pack(side="left", padx=(10, 0))

        # 2. Rapor Toplama
        rapor_frame = tk.Frame(fonksiyon_frame, bg='#F3E5F5')
        rapor_frame.pack(fill="x", pady=5)

        rapor_checkbox = tk.Checkbutton(
            rapor_frame,
            text="Rapor Toplama",
            variable=self.rapor_toplama_var,
            font=("Arial", 10, "bold"),
            bg='#F3E5F5',
            fg='#0D47A1',
            activebackground='#F3E5F5',
            selectcolor='#E1BEE7',
            command=self.fonksiyon_ayarlarini_kaydet
        )
        rapor_checkbox.pack(side="left")

        tk.Label(
            rapor_frame,
            text="Hasta rapor bilgilerini CSV'ye kaydet",
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#666666'
        ).pack(side="left", padx=(10, 0))

        # 3. Rapor Kontrol (SUT Uygunluk)
        kontrol_frame = tk.Frame(fonksiyon_frame, bg='#F3E5F5')
        kontrol_frame.pack(fill="x", pady=5)

        kontrol_checkbox = tk.Checkbutton(
            kontrol_frame,
            text="Rapor Kontrol",
            variable=self.rapor_kontrol_var,
            font=("Arial", 10, "bold"),
            bg='#F3E5F5',
            fg='#E65100',
            activebackground='#F3E5F5',
            selectcolor='#E1BEE7',
            command=self.fonksiyon_ayarlarini_kaydet
        )
        kontrol_checkbox.pack(side="left")

        tk.Label(
            kontrol_frame,
            text="Renkli reçete kontrolü",
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#666666'
        ).pack(side="left", padx=(10, 0))

        # Ayırıcı
        tk.Label(
            main_frame,
            text="─" * 40,
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#CE93D8'
        ).pack(pady=10)

        # Açıklama
        aciklama_frame = tk.LabelFrame(
            main_frame,
            text="Bilgi",
            font=("Arial", 9, "bold"),
            bg='#F3E5F5',
            fg='#7B1FA2',
            padx=10,
            pady=10
        )
        aciklama_frame.pack(fill="x")

        aciklama_text = """• Birden fazla fonksiyon aktifse, en gerideki
  reçeteden başlanır.

• Örnek: İlaç takip 50. reçetede, rapor toplama
  30. reçetede kaldıysa → 30'dan başlar.

• Her fonksiyon kendi reçete hafızasını tutar.

• En az bir fonksiyon aktif olmalıdır."""

        tk.Label(
            aciklama_frame,
            text=aciklama_text,
            font=("Arial", 8),
            bg='#F3E5F5',
            fg='#4A148C',
            justify="left"
        ).pack(anchor="w")

    def fonksiyon_ayarlarini_kaydet(self):
        """Fonksiyon ayarlarını kaydet"""
        # En az bir fonksiyon aktif olmalı
        if not (self.ilac_takip_var.get() or self.rapor_toplama_var.get() or self.rapor_kontrol_var.get()):
            messagebox.showwarning(
                "Uyarı",
                "En az bir fonksiyon aktif olmalıdır!"
            )
            # Son değiştirilen checkbox'ı geri al (ilac_takip varsayılan)
            self.ilac_takip_var.set(True)
            return

        # Ayarları kaydet
        self.grup_durumu.fonksiyon_ayarlari_guncelle({
            "ilac_takip_aktif": self.ilac_takip_var.get(),
            "rapor_toplama_aktif": self.rapor_toplama_var.get(),
            "rapor_kontrol_aktif": self.rapor_kontrol_var.get()
        })

        # Log
        aktif_fonksiyonlar = []
        if self.ilac_takip_var.get():
            aktif_fonksiyonlar.append("İlaç Takip")
        if self.rapor_toplama_var.get():
            aktif_fonksiyonlar.append("Rapor Toplama")
        if self.rapor_kontrol_var.get():
            aktif_fonksiyonlar.append("Rapor Kontrol")

        logger.info(f"✓ Aktif fonksiyonlar güncellendi: {', '.join(aktif_fonksiyonlar)}")

    def renkli_liste_penceresi_ac(self):
        """Renkli reçete listesi yükleme penceresi aç"""
        # Pencere oluştur
        liste_pencere = tk.Toplevel(self.root)
        liste_pencere.title("Renkli Reçete Listesi Yükle")
        liste_pencere.geometry("600x550")
        liste_pencere.configure(bg='#FFFFFF')
        liste_pencere.transient(self.root)
        liste_pencere.grab_set()
        liste_pencere.resizable(True, True)

        # ===== ALT BUTONLAR (ÖNCELİKLİ - side=bottom için önce pack edilmeli) =====
        btn_frame = tk.Frame(liste_pencere, bg='#E8E8E8', height=70)
        btn_frame.pack(side="bottom", fill="x")
        btn_frame.pack_propagate(False)

        btn_inner = tk.Frame(btn_frame, bg='#E8E8E8')
        btn_inner.pack(expand=True, pady=15)

        # Mevcut liste durumu
        from recete_kontrol import get_renkli_recete_kontrol
        kontrol = get_renkli_recete_kontrol()
        if kontrol.pdf_yuklu and len(kontrol.pdf_receteler) > 0:
            durum_label = tk.Label(
                btn_inner,
                text=f"📋 Mevcut: {len(kontrol.pdf_receteler)} reçete",
                font=("Arial", 9, "bold"),
                bg='#E8E8E8',
                fg='#4CAF50'
            )
            durum_label.pack(side="left", padx=(0, 20))

        # Başlık
        tk.Label(
            liste_pencere,
            text="📋 Renkli Reçete Listesi Yükle",
            font=("Arial", 14, "bold"),
            bg='#FFFFFF',
            fg='#333333'
        ).pack(pady=(15, 10))

        # ===== ÜST BUTONLAR - DOSYADAN YÜKLEME =====
        dosya_frame = tk.LabelFrame(
            liste_pencere,
            text="Dosyadan Yükle",
            font=("Arial", 10, "bold"),
            bg='#FFFFFF',
            fg='#1976D2',
            padx=10,
            pady=10
        )
        dosya_frame.pack(fill="x", padx=15, pady=(0, 10))

        dosya_btn_frame = tk.Frame(dosya_frame, bg='#FFFFFF')
        dosya_btn_frame.pack()

        # Excel'den Yükle butonu
        tk.Button(
            dosya_btn_frame,
            text="📊 Excel'den Yükle",
            font=("Arial", 10),
            bg='#4CAF50',
            fg='white',
            activebackground='#388E3C',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=8,
            command=lambda: self._excel_yukle(liste_pencere)
        ).pack(side="left", padx=10)

        # PDF'den Yükle butonu
        tk.Button(
            dosya_btn_frame,
            text="📄 PDF'den Yükle",
            font=("Arial", 10),
            bg='#2196F3',
            fg='white',
            activebackground='#1976D2',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=8,
            command=lambda: self._pdf_yukle(liste_pencere)
        ).pack(side="left", padx=10)

        # ===== MANUEL GİRİŞ - TEXTBOX =====
        manuel_frame = tk.LabelFrame(
            liste_pencere,
            text="Manuel Giriş (Kopyala-Yapıştır)",
            font=("Arial", 10, "bold"),
            bg='#FFFFFF',
            fg='#E65100',
            padx=10,
            pady=10
        )
        manuel_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Açıklama
        tk.Label(
            manuel_frame,
            text="Renkli reçete sisteminden verileri kopyalayıp aşağıya yapıştırın:",
            font=("Arial", 9),
            bg='#FFFFFF',
            fg='#666666'
        ).pack(anchor="w")

        # Text widget frame
        text_frame = tk.Frame(manuel_frame, bg='#FFFFFF')
        text_frame.pack(fill="both", expand=True, pady=(5, 0))

        # Scrollbar
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        # Text widget
        text_widget = tk.Text(
            text_frame,
            font=("Consolas", 10),
            bg='#F5F5F5',
            fg='#333333',
            wrap='word',
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)

        # Örnek metin
        ornek = """Örnek formatlar:

EBJMFHNF / 2KBNU50
9X2GPX8O / 2K9RBDY

veya sadece reçete numaraları:
2KBNU50
2K9RBDY
"""
        text_widget.insert('1.0', ornek)
        text_widget.tag_add("placeholder", "1.0", "end")
        text_widget.tag_config("placeholder", foreground="#AAAAAA")

        # Tıklandığında örneği temizle
        def temizle_ornek(event):
            if text_widget.tag_ranges("placeholder"):
                text_widget.delete('1.0', 'end')
                text_widget.tag_remove("placeholder", "1.0", "end")

        text_widget.bind("<FocusIn>", temizle_ornek)

        # Text widget referansını sakla
        self._renkli_text_widget = text_widget
        self._renkli_pencere = liste_pencere

        # Butonları btn_inner'a ekle (text_widget tanımlandıktan sonra)
        # Metinden Yükle butonu
        tk.Button(
            btn_inner,
            text="✓ METİNDEN YÜKLE",
            font=("Arial", 11, "bold"),
            bg='#FF9800',
            fg='white',
            activebackground='#F57C00',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=10,
            command=lambda: self._metinden_yukle(text_widget, liste_pencere)
        ).pack(side="left", padx=8)

        # İptal butonu
        tk.Button(
            btn_inner,
            text="✗ Kapat",
            font=("Arial", 11),
            bg='#9E9E9E',
            fg='white',
            activebackground='#757575',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=10,
            command=liste_pencere.destroy
        ).pack(side="left", padx=8)

    def _metinden_yukle(self, text_widget, pencere):
        """Textbox'tan reçete listesi yükle"""
        metin = text_widget.get('1.0', 'end').strip()

        # Placeholder mı kontrol et
        if text_widget.tag_ranges("placeholder") or not metin:
            messagebox.showwarning("Uyarı", "Lütfen reçete listesini yapıştırın.")
            return

        # Metni parse et
        receteler = self._renkli_liste_parse(metin)

        if not receteler:
            messagebox.showwarning("Uyarı", "Geçerli reçete numarası bulunamadı.\n\nReçete numarası formatı: 2XXXXXX")
            return

        self._recete_listesi_kaydet(receteler, pencere)

    def _excel_yukle(self, pencere):
        """Excel dosyasından reçete listesi yükle"""
        from tkinter import filedialog

        dosya_yolu = filedialog.askopenfilename(
            title="Renkli Reçete Excel Dosyası Seç",
            filetypes=[("Excel Dosyaları", "*.xlsx *.xls"), ("Tüm Dosyalar", "*.*")],
            initialdir="C:\\Users\\ana\\OneDrive\\Desktop"
        )

        if not dosya_yolu:
            return

        try:
            import pandas as pd
            df = pd.read_excel(dosya_yolu)

            # Reçete No sütununu bul
            recete_sutun = None
            for col in df.columns:
                if 'reçete' in col.lower() or 'recete' in col.lower():
                    recete_sutun = col
                    break

            if recete_sutun is None:
                recete_sutun = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            receteler = []
            import re
            for val in df[recete_sutun]:
                if pd.isna(val):
                    continue
                val_str = str(val)
                # "XXX / YYY" formatı
                if '/' in val_str:
                    parcalar = val_str.split('/')
                    if len(parcalar) >= 2:
                        ikinci = parcalar[1].strip()
                        temiz = re.sub(r'[^A-Za-z0-9]', '', ikinci)
                        if re.match(r'^2[A-Za-z0-9]{6}$', temiz):
                            receteler.append(temiz)
                else:
                    temiz = re.sub(r'[^A-Za-z0-9]', '', val_str)
                    if re.match(r'^2[A-Za-z0-9]{6}$', temiz):
                        receteler.append(temiz)

            if not receteler:
                messagebox.showwarning("Uyarı", "Excel dosyasında geçerli reçete numarası bulunamadı.")
                return

            self._recete_listesi_kaydet(list(set(receteler)), pencere)

        except Exception as e:
            messagebox.showerror("Hata", f"Excel okuma hatası:\n{e}")

    def _pdf_yukle(self, pencere):
        """PDF dosyasından reçete listesi yükle"""
        from tkinter import filedialog

        dosya_yolu = filedialog.askopenfilename(
            title="Renkli Reçete PDF Dosyası Seç",
            filetypes=[("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")],
            initialdir="C:\\Users\\ana\\OneDrive\\Desktop"
        )

        if not dosya_yolu:
            return

        try:
            import pdfplumber
            import re

            receteler = []
            with pdfplumber.open(dosya_yolu) as pdf:
                for sayfa in pdf.pages:
                    metin = sayfa.extract_text() or ""
                    # 2XXXXXX formatındaki reçete numaralarını bul
                    matches = re.findall(r'2[A-Za-z0-9]{6}', metin)
                    receteler.extend(matches)

            if not receteler:
                messagebox.showwarning("Uyarı", "PDF dosyasında geçerli reçete numarası bulunamadı.\n\nPDF görüntü tabanlı olabilir, manuel giriş kullanın.")
                return

            self._recete_listesi_kaydet(list(set(receteler)), pencere)

        except ImportError:
            messagebox.showerror("Hata", "pdfplumber kütüphanesi yüklü değil.\n\npip install pdfplumber")
        except Exception as e:
            messagebox.showerror("Hata", f"PDF okuma hatası:\n{e}")

    def _recete_listesi_kaydet(self, receteler, pencere):
        """Reçete listesini kaydet ve UI güncelle"""
        from recete_kontrol import get_renkli_recete_kontrol
        self.renkli_recete_kontrol = get_renkli_recete_kontrol()
        self.renkli_recete_kontrol.liste_yukle(receteler)

        # Ana ekrandaki label'ı güncelle
        self.renkli_recete_label.config(
            text=f"✓ {len(receteler)} reçete yüklü",
            bg="#C8E6C9",
            fg="#1B5E20"
        )
        self.log_ekle(f"📋 Renkli reçete listesi yüklendi: {len(receteler)} reçete")

        messagebox.showinfo("Başarılı", f"{len(receteler)} reçete yüklendi!")
        pencere.destroy()

    def _renkli_liste_parse(self, metin):
        """
        Yapıştırılan metinden reçete numaralarını çıkar.

        Desteklenen formatlar:
        - "EBJMFHNF / 2KBNU50" → 2KBNU50 (ikinci kısım)
        - "2KBNU50" → 2KBNU50 (direkt numara)
        - Excel'den kopyalanan tab-separated veriler
        """
        import re
        receteler = []

        for satir in metin.split('\n'):
            satir = satir.strip()
            if not satir:
                continue

            # Tab veya çoklu boşlukla ayrılmış hücreleri ayır (Excel formatı)
            hucreler = re.split(r'\t+|\s{2,}', satir)

            for hucre in hucreler:
                hucre = hucre.strip()
                if not hucre:
                    continue

                # Format 1: "XXX / YYY" - ikinci kısmı al
                if '/' in hucre:
                    parcalar = hucre.split('/')
                    if len(parcalar) >= 2:
                        ikinci = parcalar[1].strip()
                        # Sadece alfanumerik karakterler (5-10 karakter arası - reçete no formatı)
                        ikinci_temiz = re.sub(r'[^A-Za-z0-9]', '', ikinci)
                        if 5 <= len(ikinci_temiz) <= 10:
                            receteler.append(ikinci_temiz)
                            continue

                # Format 2: Direkt reçete numarası (2 ile başlayan, 7 karakter)
                # Medula reçete no formatı: 2XXXXXX (2 ile başlar, 7 karakter)
                temiz = re.sub(r'[^A-Za-z0-9]', '', hucre)
                if re.match(r'^2[A-Za-z0-9]{6}$', temiz):
                    receteler.append(temiz)

        return list(set(receteler))  # Tekrarları kaldır

    def renkli_kontrol_raporu_goster(self):
        """Renkli reçete kontrol raporunu göster"""
        if not self.renkli_recete_kontrol:
            messagebox.showinfo("Bilgi", "Henüz kontrol yapılmadı.")
            return

        rapor = self.renkli_recete_kontrol.rapor_ozeti_al()

        # Rapor penceresi
        rapor_pencere = tk.Toplevel(self.root)
        rapor_pencere.title("Renkli Reçete Kontrol Raporu")
        rapor_pencere.geometry("500x400")
        rapor_pencere.configure(bg='#FFFFFF')

        # Rapor metni
        text_widget = tk.Text(
            rapor_pencere,
            font=("Consolas", 10),
            bg='#FFFFFF',
            fg='#333333',
            wrap='word',
            padx=10,
            pady=10
        )
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert('1.0', rapor)
        text_widget.config(state='disabled')

        # Kapat butonu
        tk.Button(
            rapor_pencere,
            text="Kapat",
            font=("Arial", 10),
            bg='#2196F3',
            fg='white',
            command=rapor_pencere.destroy
        ).pack(pady=10)

    def create_giris_ayarlari_tab(self, parent):
        """Giriş Ayarları sekmesi içeriğini oluştur"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#E3F2FD')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== MEDULA GİRİŞ BİLGİLERİ =====
        medula_frame = tk.LabelFrame(
            main_frame,
            text="🔐 MEDULA Giriş Bilgileri",
            font=("Arial", 11, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        medula_frame.pack(fill="x", pady=(0, 10))

        # Kullanıcı Seçimi
        tk.Label(
            medula_frame,
            text="👤 Kullanıcı Seç:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).grid(row=0, column=0, sticky="w", padx=5, pady=8)

        kullanici_listesi = [k.get("ad", f"Kullanıcı {i+1}") for i, k in enumerate(self.medula_settings.get_kullanicilar())]
        aktif_index = self.medula_settings.get("aktif_kullanici", 0)

        self.kullanici_secim_var = tk.StringVar(value=kullanici_listesi[aktif_index] if kullanici_listesi else "Kullanıcı 1")
        self.kullanici_secim_combo = ttk.Combobox(
            medula_frame,
            textvariable=self.kullanici_secim_var,
            values=kullanici_listesi,
            state="readonly",
            font=("Arial", 9),
            width=27
        )
        self.kullanici_secim_combo.grid(row=0, column=1, padx=5, pady=8)
        self.kullanici_secim_combo.bind("<<ComboboxSelected>>", self.kullanici_secimi_degisti)

        # Ayırıcı
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=1, column=0, columnspan=2, pady=5)

        # Kullanıcı Adı (Opsiyonel Etiket)
        tk.Label(
            medula_frame,
            text="Kullanıcı Etiketi:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=2, column=0, sticky="w", padx=5, pady=5)

        self.medula_kullanici_ad_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30
        )
        self.medula_kullanici_ad_entry.grid(row=2, column=1, padx=5, pady=5)

        # MEDULA Kullanıcı Index
        tk.Label(
            medula_frame,
            text="MEDULA Kullanıcı:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=3, column=0, sticky="w", padx=5, pady=5)

        self.medula_index_var = tk.StringVar()
        self.medula_index_combo = ttk.Combobox(
            medula_frame,
            textvariable=self.medula_index_var,
            values=[
                "1. Kullanıcı (Index 0)",
                "2. Kullanıcı (Index 1)",
                "3. Kullanıcı (Index 2)",
                "4. Kullanıcı (Index 3)",
                "5. Kullanıcı (Index 4)",
                "6. Kullanıcı (Index 5)"
            ],
            state="readonly",
            font=("Arial", 9),
            width=27
        )
        self.medula_index_combo.grid(row=3, column=1, padx=5, pady=5)

        # Şifre
        tk.Label(
            medula_frame,
            text="Şifre:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=4, column=0, sticky="w", padx=5, pady=5)

        self.medula_sifre_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30,
            show="*"
        )
        self.medula_sifre_entry.grid(row=4, column=1, padx=5, pady=5)

        # Seçili kullanıcının bilgilerini yükle
        self.secili_kullanici_bilgilerini_yukle()

        # Kaydet Butonu
        tk.Button(
            medula_frame,
            text="💾 Kullanıcı Bilgilerini Kaydet",
            font=("Arial", 9, "bold"),
            bg='#1976D2',
            fg='white',
            width=30,
            command=self.medula_bilgilerini_kaydet
        ).grid(row=5, column=0, columnspan=2, pady=10)

        # Uyarı
        tk.Label(
            medula_frame,
            text="⚠ Bilgiler şifrelenmeden kaydedilir. Güvenli bir bilgisayarda kullanın.",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#D32F2F'
        ).grid(row=6, column=0, columnspan=2)

        tk.Label(
            medula_frame,
            text="ℹ Her kullanıcı için farklı MEDULA hesabı kullanabilirsiniz.",
            font=("Arial", 7),
            bg='#E3F2FD',
            fg='#1565C0'
        ).grid(row=7, column=0, columnspan=2, pady=(0, 5))

        # Ayırıcı (Giriş Yöntemi için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=8, column=0, columnspan=2, pady=5)

        # Giriş Yöntemi Seçimi
        tk.Label(
            medula_frame,
            text="🔐 Giriş Yöntemi:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).grid(row=9, column=0, sticky="w", padx=5, pady=(5, 0))

        # Giriş yöntemi için frame
        giris_yontemi_frame = tk.Frame(medula_frame, bg='#E3F2FD')
        giris_yontemi_frame.grid(row=9, column=1, sticky="w", padx=5, pady=(5, 0))

        self.giris_yontemi_var = tk.StringVar(value=self.medula_settings.get("giris_yontemi", "indeks"))

        # İndeks radio button
        tk.Radiobutton(
            giris_yontemi_frame,
            text="İndeks ile (örn: 4. kullanıcı)",
            variable=self.giris_yontemi_var,
            value="indeks",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.giris_yontemi_degisti
        ).pack(anchor="w")

        # Kullanıcı adı radio button
        tk.Radiobutton(
            giris_yontemi_frame,
            text="Kullanıcı adı ile (örn: Ali Veli)",
            variable=self.giris_yontemi_var,
            value="kullanici_adi",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.giris_yontemi_degisti
        ).pack(anchor="w")

        # Kullanıcı Adı Girişi (sadece kullanici_adi seçiliyse aktif)
        tk.Label(
            medula_frame,
            text="MEDULA Kullanıcı Adı:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=10, column=0, sticky="w", padx=5, pady=5)

        self.kullanici_adi_giris_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30
        )
        self.kullanici_adi_giris_entry.grid(row=10, column=1, padx=5, pady=5)

        # Varsayılan değeri yükle
        kullanici_adi_giris = self.medula_settings.get("kullanici_adi_giris", "")
        if kullanici_adi_giris:
            self.kullanici_adi_giris_entry.insert(0, kullanici_adi_giris)

        # İlk durumu ayarla
        self.giris_yontemi_degisti()

        # Bilgi notu
        tk.Label(
            medula_frame,
            text="ℹ İndeks: Combobox'ta kaç kere DOWN tuşuna basılacağını belirler (0-5 arası)\nKullanıcı Adı: MEDULA giriş ekranında bu kullanıcı adı aranır",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161',
            justify="left"
        ).grid(row=11, column=0, columnspan=2, pady=(0, 5))

        # Kaydet butonu (Giriş Yöntemi için)
        tk.Button(
            medula_frame,
            text="💾 Giriş Yöntemi Ayarlarını Kaydet",
            font=("Arial", 8, "bold"),
            bg='#1976D2',
            fg='white',
            width=35,
            command=self.giris_yontemi_ayarlarini_kaydet
        ).grid(row=12, column=0, columnspan=2, pady=5)

        # Ayırıcı (Telefon Kontrolü için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=13, column=0, columnspan=2, pady=5)

        # Telefon Kontrolü Checkbox
        self.telefonsuz_atla_var = tk.BooleanVar(value=self.medula_settings.get("telefonsuz_atla", False))
        telefon_checkbox = tk.Checkbutton(
            medula_frame,
            text="📵 Telefon numarası olmayan hastaları atla",
            variable=self.telefonsuz_atla_var,
            font=("Arial", 9),
            bg='#E3F2FD',
            fg='#D32F2F',
            activebackground='#E3F2FD',
            command=self.telefon_ayarini_kaydet
        )
        telefon_checkbox.grid(row=14, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))

        tk.Label(
            medula_frame,
            text="ℹ Telefon yoksa hasta işleme alınmadan direkt sonraki hastaya geçilir.",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161'
        ).grid(row=15, column=0, columnspan=2, pady=(0, 5))

        # Ayırıcı (Yasaklı Tesis Numaraları için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=16, column=0, columnspan=2, pady=5)

        # B Grubu Yasaklı Tesis Numaraları
        tk.Label(
            medula_frame,
            text="🚫 B Grubu Yasaklı Tesis Numaraları:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#D32F2F'
        ).grid(row=17, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))

        tk.Label(
            medula_frame,
            text="ℹ Bu listedeki tesislerden gelen B grubu reçeteler tarama sırasında otomatik atlanır.",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161'
        ).grid(row=18, column=0, columnspan=2, pady=(0, 3))

        # Tesis ekleme frame
        tesis_frame = tk.Frame(medula_frame, bg='#E3F2FD')
        tesis_frame.grid(row=19, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        tk.Label(
            tesis_frame,
            text="Tesis No:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).pack(side="left", padx=(0, 5))

        self.tesis_entry = tk.Entry(
            tesis_frame,
            font=("Arial", 9),
            width=15
        )
        self.tesis_entry.pack(side="left", padx=(0, 5))

        tk.Button(
            tesis_frame,
            text="Ekle",
            font=("Arial", 8),
            bg='#4CAF50',
            fg='white',
            command=self.yasakli_tesis_ekle,
            width=6
        ).pack(side="left", padx=2)

        tk.Button(
            tesis_frame,
            text="Sil",
            font=("Arial", 8),
            bg='#F44336',
            fg='white',
            command=self.yasakli_tesis_sil,
            width=6
        ).pack(side="left", padx=2)

        # Yasaklı tesis listesi
        tesis_liste_frame = tk.Frame(medula_frame, bg='#E3F2FD')
        tesis_liste_frame.grid(row=20, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 5))

        self.tesis_listbox = tk.Listbox(
            tesis_liste_frame,
            font=("Arial", 9),
            height=4,
            width=30,
            selectmode="single",
            bg='#FFFFFF',
            fg='#333333',
            selectbackground='#2196F3',
            selectforeground='white'
        )
        self.tesis_listbox.pack(side="left", fill="x", expand=True)

        tesis_scrollbar = tk.Scrollbar(tesis_liste_frame, orient="vertical", command=self.tesis_listbox.yview)
        tesis_scrollbar.pack(side="right", fill="y")
        self.tesis_listbox.config(yscrollcommand=tesis_scrollbar.set)

        # Mevcut yasaklı tesisleri yükle
        yasakli_tesisler = self.medula_settings.get("yasakli_tesis_numaralari", [])
        for tesis in yasakli_tesisler:
            self.tesis_listbox.insert(tk.END, tesis)

        # Ayırıcı (Pencere Yerleşimi için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=21, column=0, columnspan=2, pady=5)

        # Pencere Yerleşimi Seçimi
        tk.Label(
            medula_frame,
            text="🖼 Pencere Yerleşimi:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).grid(row=22, column=0, sticky="w", padx=5, pady=(5, 0))

        # Pencere yerleşimi için frame
        yerlesim_frame = tk.Frame(medula_frame, bg='#E3F2FD')
        yerlesim_frame.grid(row=22, column=1, sticky="w", padx=5, pady=(5, 0))

        self.pencere_yerlesimi_var = tk.StringVar(value=self.medula_settings.get("pencere_yerlesimi", "standart"))

        # Standart radio button
        tk.Radiobutton(
            yerlesim_frame,
            text="Standart (MEDULA %60 | Konsol %20 | GUI %20)",
            variable=self.pencere_yerlesimi_var,
            value="standart",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.pencere_yerlesimi_degisti
        ).pack(anchor="w")

        # Geniş MEDULA radio button
        tk.Radiobutton(
            yerlesim_frame,
            text="Geniş MEDULA (MEDULA %80 | GUI %20, Konsol arkada)",
            variable=self.pencere_yerlesimi_var,
            value="genis_medula",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.pencere_yerlesimi_degisti
        ).pack(anchor="w")

        # Bilgi notu
        tk.Label(
            medula_frame,
            text="ℹ Geniş MEDULA: MEDULA ekranın %80'ini kaplar, GUI sağ %20'de, Konsol GUI'nin arkasında",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161',
            justify="left"
        ).grid(row=23, column=0, columnspan=2, pady=(0, 5))

    def create_timing_ayarlari_tab(self, parent):
        """Timing Ayarları sekmesi içeriğini oluştur"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#E8F5E9')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== ZAMANLAMA AYARLARI =====
        timing_title = tk.Label(
            main_frame,
            text="⏱ Zamanlama Ayarları",
            font=("Arial", 12, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        )
        timing_title.pack(pady=(10, 5))

        subtitle = tk.Label(
            main_frame,
            text="Her işlem için bekleme sürelerini ayarlayın (saniye)",
            font=("Arial", 8),
            bg='#E8F5E9',
            fg='#2E7D32'
        )
        subtitle.pack(pady=(0, 5))

        # Hızlı ayar butonları
        quick_frame = tk.Frame(main_frame, bg='#E8F5E9')
        quick_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            quick_frame,
            text="Hızlı:",
            font=("Arial", 8, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        ).pack(side="left", padx=(0, 5))

        hizli_butonlar = [
            ("Çok Hızlı (x0.5)", 0.5),
            ("Normal (x1.0)", 1.0),
            ("Yavaş (x1.5)", 1.5),
            ("Çok Yavaş (x2.0)", 2.0),
        ]

        for text, carpan in hizli_butonlar:
            btn = tk.Button(
                quick_frame,
                text=text,
                font=("Arial", 6),
                bg='#81C784',
                fg='white',
                width=11,
                height=1,
                command=lambda c=carpan: self.hizli_ayarla(c)
            )
            btn.pack(side="left", padx=1)

        # Optimize Mode Checkbox
        optimize_frame = tk.Frame(main_frame, bg='#E8F5E9')
        optimize_frame.pack(fill="x", pady=(5, 0))

        self.optimize_mode_var = tk.BooleanVar(value=False)
        optimize_checkbox = tk.Checkbutton(
            optimize_frame,
            text="🔧 Otomatik Optimize:",
            variable=self.optimize_mode_var,
            font=("Arial", 9, "bold"),
            bg='#E8F5E9',
            fg='#FF6F00',
            activebackground='#E8F5E9',
            command=self.optimize_mode_toggle
        )
        optimize_checkbox.pack(side="left", padx=5)

        # Çarpan label
        tk.Label(
            optimize_frame,
            text="Çarpan:",
            font=("Arial", 8),
            bg='#E8F5E9',
            fg='#424242'
        ).pack(side="left", padx=(5, 2))

        # Çarpan input (0.8 - 2.0 arası)
        self.optimize_multiplier_var = tk.StringVar(value="1.3")
        multiplier_spinbox = tk.Spinbox(
            optimize_frame,
            from_=0.8,
            to=2.0,
            increment=0.1,
            textvariable=self.optimize_multiplier_var,
            width=5,
            font=("Arial", 8),
            bg='white'
        )
        multiplier_spinbox.pack(side="left", padx=2)

        # Açıklama
        tk.Label(
            optimize_frame,
            text="x (0.8=-%20, 1.0=aynı, 1.3=+%30, 1.5=+%50)",
            font=("Arial", 7),
            bg='#E8F5E9',
            fg='#757575'
        ).pack(side="left", padx=(2, 5))

        # Optimize açıklama (ikinci satır)
        optimize_info_frame = tk.Frame(main_frame, bg='#E8F5E9')
        optimize_info_frame.pack(fill="x", pady=(0, 5))

        optimize_info = tk.Label(
            optimize_info_frame,
            text="(İlk çalıştırmada tüm süreler 3s başlar, sonra reel süre × çarpan ile otomatik ayarlanır)",
            font=("Arial", 7),
            bg='#E8F5E9',
            fg='#757575'
        )
        optimize_info.pack(side="left", padx=5)

        # Scrollable canvas (height belirtildi böylece scroll düzgün çalışır)
        canvas = tk.Canvas(main_frame, bg='#E8F5E9', highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#E8F5E9')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scroll desteği
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Kategorilere göre ayarları göster
        kategoriler = self.timing.kategori_listesi()

        for kategori_adi, ayarlar in kategoriler.items():
            # Kategori frame
            kategori_frame = tk.LabelFrame(
                scrollable_frame,
                text=kategori_adi,
                font=("Arial", 8, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                padx=5,
                pady=3
            )
            kategori_frame.pack(fill="x", padx=3, pady=3)

            # Her ayar için satır
            for ayar_key, ayar_label in ayarlar:
                row_frame = tk.Frame(kategori_frame, bg='#C8E6C9')
                row_frame.pack(fill="x", pady=1)

                # Label
                label = tk.Label(
                    row_frame,
                    text=ayar_label + ":",
                    font=("Arial", 7),
                    bg='#C8E6C9',
                    fg='#1B5E20',
                    width=18,
                    anchor="w"
                )
                label.pack(side="left", padx=(0, 5))

                # Entry
                entry_var = tk.StringVar(value=str(self.timing.get(ayar_key)))
                entry = tk.Entry(
                    row_frame,
                    textvariable=entry_var,
                    font=("Arial", 7),
                    width=8,
                    justify="right"
                )
                entry.pack(side="left", padx=(0, 3))

                # Entry değiştiğinde otomatik kaydet
                entry_var.trace_add("write", lambda *args, key=ayar_key, var=entry_var: self.ayar_degisti(key, var))

                self.ayar_entry_widgets[ayar_key] = entry_var

                # Birim
                tk.Label(
                    row_frame,
                    text="sn",
                    font=("Arial", 6),
                    bg='#C8E6C9',
                    fg='#2E7D32'
                ).pack(side="left")

                # İstatistik label
                stats = self.timing.istatistik_al(ayar_key)
                count = stats.get("count", 0)
                avg = self.timing.ortalama_al(ayar_key)

                if count > 0 and avg is not None:
                    stat_text = f"({count}x, ort:{avg:.3f}s)"
                else:
                    stat_text = "(0x, ort:-)"

                tk.Label(
                    row_frame,
                    text=stat_text,
                    font=("Arial", 7),
                    bg='#C8E6C9',
                    fg='#616161',
                    anchor="w"
                ).pack(side="left", padx=(3, 0))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Alt butonlar
        button_frame = tk.Frame(main_frame, bg='#E8F5E9')
        button_frame.pack(fill="x", pady=(5, 0))

        tk.Button(
            button_frame,
            text="Varsayılana Döndür",
            font=("Arial", 8),
            bg='#FFA726',
            fg='white',
            width=13,
            height=1,
            command=self.varsayilana_don
        ).pack(side="left", padx=(0, 3))

        tk.Button(
            button_frame,
            text="Şimdi Kaydet",
            font=("Arial", 8, "bold"),
            bg='#388E3C',
            fg='white',
            width=13,
            height=1,
            command=self.ayarlari_kaydet
        ).pack(side="left", padx=(0, 3))

        tk.Button(
            button_frame,
            text="İstatistik Sıfırla",
            font=("Arial", 8),
            bg='#D32F2F',
            fg='white',
            width=13,
            height=1,
            command=self.istatistikleri_sifirla
        ).pack(side="left")

        # Durum mesajı
        self.ayar_durum_label = tk.Label(
            main_frame,
            text="Ayarlar otomatik kaydedilir",
            font=("Arial", 6),
            bg='#E8F5E9',
            fg='#2E7D32'
        )
        self.ayar_durum_label.pack(pady=(3, 0))

    def create_insan_davranisi_tab(self, parent):
        """İnsan Davranışı sekmesi içeriğini oluştur"""
        import json

        # JSON dosyasını yükle
        self.insan_davranisi_json_path = "insan_davranisi_settings.json"
        self.insan_davranisi_ayarlar = self._insan_davranisi_yukle()

        # Ana frame (scrollable)
        main_frame = tk.Frame(parent, bg='#FFF3E0')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Başlık
        title = tk.Label(
            main_frame,
            text="🧠 İnsan Davranışı Simülasyonu",
            font=("Arial", 12, "bold"),
            bg='#FFF3E0',
            fg='#E65100'
        )
        title.pack(pady=(5, 2))

        subtitle = tk.Label(
            main_frame,
            text="Bu ayarlar bot davranışını daha insan benzeri yapar",
            font=("Arial", 8),
            bg='#FFF3E0',
            fg='#F57C00'
        )
        subtitle.pack(pady=(0, 10))

        # Uyarı mesajı (gizli başlangıçta)
        self.insan_uyari_label = tk.Label(
            main_frame,
            text="⚠️ Değişiklikler bir sonraki oturum için geçerli olacaktır.\nHemen uygulamak için oturumu sonlandırıp yeniden başlatın.",
            font=("Arial", 8, "bold"),
            bg='#FFECB3',
            fg='#E65100',
            pady=5,
            padx=10
        )
        # Başlangıçta gizli
        self.insan_uyari_gosterildi = False

        # Scrollable canvas
        canvas = tk.Canvas(main_frame, bg='#FFF3E0', highlightthickness=0, height=350)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#FFF3E0')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # ===== 1. RİTİM BOZUCU =====
        ritim_frame = tk.LabelFrame(
            scrollable_frame,
            text="🎵 Ritim Bozucu",
            font=("Arial", 9, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            padx=10,
            pady=5
        )
        ritim_frame.pack(fill="x", padx=5, pady=5)

        self.ritim_aktif_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("ritim_bozucu", {}).get("aktif", False))
        ritim_check = tk.Checkbutton(
            ritim_frame,
            text="Aktif",
            variable=self.ritim_aktif_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        ritim_check.grid(row=0, column=0, sticky="w")

        tk.Label(ritim_frame, text="Max ek süre (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=0, column=1, padx=(15, 5))
        self.ritim_ms_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("ritim_bozucu", {}).get("max_ms", 3000)))
        self.ritim_ms_entry = tk.Entry(ritim_frame, textvariable=self.ritim_ms_var, width=8, font=("Arial", 8))
        self.ritim_ms_entry.grid(row=0, column=2)
        self.ritim_ms_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(ritim_frame, text="(Her adıma 0-X ms arası random eklenir)", font=("Arial", 7), bg='#FFE0B2', fg='#757575').grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))

        # ===== 2. DİKKAT BOZUCU =====
        dikkat_frame = tk.LabelFrame(
            scrollable_frame,
            text="👀 Dikkat Bozucu",
            font=("Arial", 9, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            padx=10,
            pady=5
        )
        dikkat_frame.pack(fill="x", padx=5, pady=5)

        self.dikkat_aktif_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("dikkat_bozucu", {}).get("aktif", False))
        dikkat_check = tk.Checkbutton(
            dikkat_frame,
            text="Aktif",
            variable=self.dikkat_aktif_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        dikkat_check.grid(row=0, column=0, sticky="w")

        tk.Label(dikkat_frame, text="Aralık max (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=0, column=1, padx=(15, 5))
        self.dikkat_aralik_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("dikkat_bozucu", {}).get("aralik_max_ms", 100000)))
        tk.Entry(dikkat_frame, textvariable=self.dikkat_aralik_var, width=8, font=("Arial", 8)).grid(row=0, column=2)
        self.dikkat_aralik_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(dikkat_frame, text="Duraklama max (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=0, column=3, padx=(15, 5))
        self.dikkat_duraklama_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("dikkat_bozucu", {}).get("duraklama_max_ms", 10000)))
        tk.Entry(dikkat_frame, textvariable=self.dikkat_duraklama_var, width=8, font=("Arial", 8)).grid(row=0, column=4)
        self.dikkat_duraklama_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(dikkat_frame, text="(0-Aralık ms sonra 0-Duraklama ms bekler, döngü tekrar)", font=("Arial", 7), bg='#FFE0B2', fg='#757575').grid(row=1, column=0, columnspan=5, sticky="w", pady=(3, 0))

        # ===== 3. YORGUNLUK MODU =====
        yorgunluk_frame = tk.LabelFrame(
            scrollable_frame,
            text="😴 Yorgunluk Modu",
            font=("Arial", 9, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            padx=10,
            pady=5
        )
        yorgunluk_frame.pack(fill="x", padx=5, pady=5)

        self.yorgunluk_aktif_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("yorgunluk", {}).get("aktif", False))
        yorgunluk_check = tk.Checkbutton(
            yorgunluk_frame,
            text="Aktif",
            variable=self.yorgunluk_aktif_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        yorgunluk_check.grid(row=0, column=0, sticky="w")

        # Çalışma süresi
        tk.Label(yorgunluk_frame, text="Çalışma MIN (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=1, column=0, sticky="w", pady=2)
        self.yorgunluk_calisma_min_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("yorgunluk", {}).get("calisma_min_ms", 1200000)))
        tk.Entry(yorgunluk_frame, textvariable=self.yorgunluk_calisma_min_var, width=10, font=("Arial", 8)).grid(row=1, column=1, padx=5)
        self.yorgunluk_calisma_min_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(yorgunluk_frame, text="MAX (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=1, column=2, padx=(10, 5))
        self.yorgunluk_calisma_max_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("yorgunluk", {}).get("calisma_max_ms", 1800000)))
        tk.Entry(yorgunluk_frame, textvariable=self.yorgunluk_calisma_max_var, width=10, font=("Arial", 8)).grid(row=1, column=3)
        self.yorgunluk_calisma_max_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(yorgunluk_frame, text="(20-30 dk)", font=("Arial", 7), bg='#FFE0B2', fg='#757575').grid(row=1, column=4, padx=5)

        # Dinlenme süresi
        tk.Label(yorgunluk_frame, text="Dinlenme MIN (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=2, column=0, sticky="w", pady=2)
        self.yorgunluk_dinlenme_min_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("yorgunluk", {}).get("dinlenme_min_ms", 300000)))
        tk.Entry(yorgunluk_frame, textvariable=self.yorgunluk_dinlenme_min_var, width=10, font=("Arial", 8)).grid(row=2, column=1, padx=5)
        self.yorgunluk_dinlenme_min_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(yorgunluk_frame, text="MAX (ms):", font=("Arial", 8), bg='#FFE0B2').grid(row=2, column=2, padx=(10, 5))
        self.yorgunluk_dinlenme_max_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("yorgunluk", {}).get("dinlenme_max_ms", 480000)))
        tk.Entry(yorgunluk_frame, textvariable=self.yorgunluk_dinlenme_max_var, width=10, font=("Arial", 8)).grid(row=2, column=3)
        self.yorgunluk_dinlenme_max_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(yorgunluk_frame, text="(5-8 dk)", font=("Arial", 7), bg='#FFE0B2', fg='#757575').grid(row=2, column=4, padx=5)

        # ===== 4. HATA DURUMUNDA BEKLE =====
        hata_frame = tk.LabelFrame(
            scrollable_frame,
            text="🛑 Hata Yönetimi",
            font=("Arial", 9, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            padx=10,
            pady=5
        )
        hata_frame.pack(fill="x", padx=5, pady=5)

        self.hata_bekle_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("hata_durumunda_bekle", {}).get("aktif", False))
        hata_check = tk.Checkbutton(
            hata_frame,
            text="Hata durumunda otomatik yeniden girişi devre dışı bırak",
            variable=self.hata_bekle_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        hata_check.pack(anchor="w")

        tk.Label(hata_frame, text="(Aktif olunca: taskkill, otomatik giriş yapılmaz - kullanıcı müdahalesi beklenir)", font=("Arial", 7), bg='#FFE0B2', fg='#757575').pack(anchor="w")

        # ===== 5. TEXTBOX 122 AYARLARI =====
        textbox_frame = tk.LabelFrame(
            scrollable_frame,
            text="📝 Textbox 122 Ayarları",
            font=("Arial", 9, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            padx=10,
            pady=5
        )
        textbox_frame.pack(fill="x", padx=5, pady=5)

        self.textbox_devre_disi_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("textbox_122", {}).get("yazmayi_devre_disi_birak", False))
        textbox_devre_disi_check = tk.Checkbutton(
            textbox_frame,
            text="122 yazmayı devre dışı bırak (mevcut veri kalır)",
            variable=self.textbox_devre_disi_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        textbox_devre_disi_check.grid(row=0, column=0, columnspan=4, sticky="w")

        self.textbox_ozel_var = tk.BooleanVar(value=self.insan_davranisi_ayarlar.get("textbox_122", {}).get("ozel_deger_kullan", False))
        textbox_ozel_check = tk.Checkbutton(
            textbox_frame,
            text="Özel değer kullan:",
            variable=self.textbox_ozel_var,
            font=("Arial", 9),
            bg='#FFE0B2',
            activebackground='#FFE0B2',
            command=self._insan_ayar_degisti
        )
        textbox_ozel_check.grid(row=1, column=0, sticky="w", pady=(5, 0))

        tk.Label(textbox_frame, text="TB1:", font=("Arial", 8), bg='#FFE0B2').grid(row=1, column=1, padx=(10, 2), pady=(5, 0))
        self.textbox_deger1_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("textbox_122", {}).get("deger_1", "122")))
        tk.Entry(textbox_frame, textvariable=self.textbox_deger1_var, width=6, font=("Arial", 8)).grid(row=1, column=2, pady=(5, 0))
        self.textbox_deger1_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        tk.Label(textbox_frame, text="TB2:", font=("Arial", 8), bg='#FFE0B2').grid(row=1, column=3, padx=(10, 2), pady=(5, 0))
        self.textbox_deger2_var = tk.StringVar(value=str(self.insan_davranisi_ayarlar.get("textbox_122", {}).get("deger_2", "122")))
        tk.Entry(textbox_frame, textvariable=self.textbox_deger2_var, width=6, font=("Arial", 8)).grid(row=1, column=4, pady=(5, 0))
        self.textbox_deger2_var.trace_add("write", lambda *args: self._insan_ayar_degisti())

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Kaydet butonu
        button_frame = tk.Frame(main_frame, bg='#FFF3E0')
        button_frame.pack(fill="x", pady=(10, 0))

        tk.Button(
            button_frame,
            text="💾 Ayarları Kaydet",
            font=("Arial", 9, "bold"),
            bg='#FF9800',
            fg='white',
            width=15,
            command=self._insan_davranisi_kaydet
        ).pack(side="left", padx=5)

        self.insan_durum_label = tk.Label(
            button_frame,
            text="",
            font=("Arial", 8),
            bg='#FFF3E0',
            fg='#2E7D32'
        )
        self.insan_durum_label.pack(side="left", padx=10)

    def _insan_davranisi_yukle(self):
        """İnsan davranışı ayarlarını JSON'dan yükle"""
        import json
        try:
            with open(self.insan_davranisi_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "ritim_bozucu": {"aktif": False, "max_ms": 3000},
                "dikkat_bozucu": {"aktif": False, "aralik_max_ms": 100000, "duraklama_max_ms": 10000},
                "yorgunluk": {"aktif": False, "calisma_min_ms": 1200000, "calisma_max_ms": 1800000, "dinlenme_min_ms": 300000, "dinlenme_max_ms": 480000},
                "hata_durumunda_bekle": {"aktif": False},
                "textbox_122": {"yazmayi_devre_disi_birak": False, "ozel_deger_kullan": False, "deger_1": "122", "deger_2": "122"}
            }
        except Exception as e:
            logger.error(f"İnsan davranışı ayarları yükleme hatası: {e}")
            return {}

    def _insan_ayar_degisti(self):
        """İnsan davranışı ayarı değiştiğinde uyarı göster"""
        if not self.insan_uyari_gosterildi:
            self.insan_uyari_label.pack(pady=(0, 10))
            self.insan_uyari_gosterildi = True

    def _insan_davranisi_kaydet(self):
        """İnsan davranışı ayarlarını JSON'a kaydet"""
        import json
        try:
            ayarlar = {
                "ritim_bozucu": {
                    "aktif": self.ritim_aktif_var.get(),
                    "max_ms": int(self.ritim_ms_var.get() or 3000)
                },
                "dikkat_bozucu": {
                    "aktif": self.dikkat_aktif_var.get(),
                    "aralik_max_ms": int(self.dikkat_aralik_var.get() or 100000),
                    "duraklama_max_ms": int(self.dikkat_duraklama_var.get() or 10000)
                },
                "yorgunluk": {
                    "aktif": self.yorgunluk_aktif_var.get(),
                    "calisma_min_ms": int(self.yorgunluk_calisma_min_var.get() or 1200000),
                    "calisma_max_ms": int(self.yorgunluk_calisma_max_var.get() or 1800000),
                    "dinlenme_min_ms": int(self.yorgunluk_dinlenme_min_var.get() or 300000),
                    "dinlenme_max_ms": int(self.yorgunluk_dinlenme_max_var.get() or 480000)
                },
                "hata_durumunda_bekle": {
                    "aktif": self.hata_bekle_var.get()
                },
                "textbox_122": {
                    "yazmayi_devre_disi_birak": self.textbox_devre_disi_var.get(),
                    "ozel_deger_kullan": self.textbox_ozel_var.get(),
                    "deger_1": self.textbox_deger1_var.get() or "122",
                    "deger_2": self.textbox_deger2_var.get() or "122"
                }
            }

            with open(self.insan_davranisi_json_path, "w", encoding="utf-8") as f:
                json.dump(ayarlar, f, indent=2, ensure_ascii=False)

            self.insan_durum_label.config(text="✓ Kaydedildi!", fg='#2E7D32')
            self.root.after(3000, lambda: self.insan_durum_label.config(text=""))
            logger.info("İnsan davranışı ayarları kaydedildi")

        except Exception as e:
            self.insan_durum_label.config(text=f"❌ Hata: {e}", fg='#C62828')
            logger.error(f"İnsan davranışı ayarları kaydetme hatası: {e}")

    def ayar_degisti(self, key, var):
        """Bir ayar değiştiğinde otomatik kaydet (debounced)"""
        # Önce timer'ı iptal et
        if self.ayar_kaydet_timer:
            self.root.after_cancel(self.ayar_kaydet_timer)

        # Ayarı bellekte güncelle (henüz kaydetme)
        try:
            deger = float(var.get())
            if deger >= 0:
                self.timing.set(key, deger)
                self.ayar_durum_label.config(text="Değişiklik kaydediliyor...", fg='#F57F17')
                # 1 saniye sonra kaydet (debounce)
                self.ayar_kaydet_timer = self.root.after(1000, self._gercek_kaydet)
        except ValueError:
            pass  # Geçersiz değer girildi, sessizce yoksay

    def _gercek_kaydet(self):
        """Debounce sonrası gerçek kaydetme"""
        try:
            if self.timing.kaydet():
                self.ayar_durum_label.config(text="✓ Otomatik kaydedildi", fg='#1B5E20')
                self.root.after(2000, lambda: self.ayar_durum_label.config(text="Ayarlar otomatik kaydedilir", fg='#2E7D32'))
            else:
                self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')

    def hizli_ayarla(self, carpan):
        """Tüm değerleri çarpan ile güncelle"""
        for key, entry_var in self.ayar_entry_widgets.items():
            varsayilan = self.timing.varsayilan_ayarlar.get(key, 0.1)
            yeni_deger = round(varsayilan * carpan, 3)
            entry_var.set(str(yeni_deger))
        self.ayar_durum_label.config(text=f"✓ Tüm ayarlar {carpan}x olarak güncellendi", fg='#1B5E20')

    def optimize_mode_toggle(self):
        """Optimize mode checkbox'ı değiştiğinde"""
        if self.optimize_mode_var.get():
            # Çarpanı al
            try:
                multiplier = float(self.optimize_multiplier_var.get())
                if multiplier < 0.8 or multiplier > 2.0:
                    multiplier = 1.3
                    self.optimize_multiplier_var.set("1.3")
            except Exception as e:
                logger.debug(f"Multiplier parse error: {type(e).__name__}")
                multiplier = 1.3
                self.optimize_multiplier_var.set("1.3")

            # Optimize mode açıldı
            self.timing.optimize_mode_ac(multiplier)
            self.log_ekle(f"🚀 Otomatik optimize aktif - Çarpan: {multiplier}x - Tüm ayarlar 3s")
            logger.info(f"🚀 Otomatik optimize mode aktif - Çarpan: {multiplier}x")

            # GUI'deki entry'leri de güncelle
            for key, entry_var in self.ayar_entry_widgets.items():
                entry_var.set("3.0")
        else:
            # Optimize mode kapatıldı
            self.timing.optimize_mode_kapat()
            self.log_ekle("⏹ Otomatik optimize kapatıldı")
            logger.info("⏹ Otomatik optimize mode kapatıldı")

    def varsayilana_don(self):
        """Tüm değerleri varsayılana döndür"""
        for key, entry_var in self.ayar_entry_widgets.items():
            varsayilan = self.timing.varsayilan_ayarlar.get(key, 0.1)
            entry_var.set(str(varsayilan))
        self.ayar_durum_label.config(text="✓ Varsayılan değerler yüklendi", fg='#1B5E20')

    def ayarlari_kaydet(self):
        """Tüm ayarları manuel kaydet"""
        try:
            for key, entry_var in self.ayar_entry_widgets.items():
                try:
                    deger = float(entry_var.get())
                    if deger < 0:
                        raise ValueError("Negatif değer")
                    self.timing.set(key, deger)
                except ValueError:
                    self.ayar_durum_label.config(text=f"❌ Hata: {key} geçersiz", fg='#C62828')
                    return

            if self.timing.kaydet():
                self.ayar_durum_label.config(text="✓ Ayarlar kaydedildi", fg='#1B5E20')
                self.log_ekle("✓ Zamanlama ayarları güncellendi")
            else:
                self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')
        except Exception as e:
            self.ayar_durum_label.config(text=f"❌ Hata: {e}", fg='#C62828')

    def ana_sayfaya_don(self):
        """Ana sayfaya (ana menüye) dön"""
        from tkinter import messagebox

        # Eğer işlem devam ediyorsa uyar
        if self.is_running:
            cevap = messagebox.askyesno(
                "İşlem Devam Ediyor",
                "Şu anda bir işlem devam ediyor. Durdurup ana sayfaya dönmek istiyor musunuz?"
            )
            if not cevap:
                return
            # İşlemi durdur
            self.stop_requested = True
            self.is_running = False

        # Pencereyi kapat ve callback'i çağır
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()

    def istatistikleri_sifirla(self):
        """Tüm istatistikleri sıfırla"""
        from tkinter import messagebox
        cevap = messagebox.askyesno(
            "İstatistikleri Sıfırla",
            "Tüm sayfa yükleme istatistikleri silinecek. Emin misiniz?"
        )
        if cevap:
            self.timing.istatistik_sifirla()
            self.ayar_durum_label.config(text="✓ İstatistikler sıfırlandı", fg='#1B5E20')
            self.log_ekle("✓ Sayfa yükleme istatistikleri sıfırlandı")
            # Ayarlar sekmesini yenile (istatistikleri güncellemek için)
            messagebox.showinfo("Bilgi", "İstatistikler sıfırlandı. Ayarlar sekmesi kapanıp açılırsa güncel değerler görünecektir.")

    def kullanici_secimi_degisti(self, event=None):
        """Kullanıcı seçimi değiştiğinde form alanlarını güncelle"""
        self.secili_kullanici_bilgilerini_yukle()

    def secili_kullanici_bilgilerini_yukle(self):
        """Seçili kullanıcının bilgilerini form alanlarına yükle"""
        # Seçili kullanıcı index'ini bul
        secili_ad = self.kullanici_secim_var.get()
        kullanicilar = self.medula_settings.get_kullanicilar()

        secili_index = 0
        for i, k in enumerate(kullanicilar):
            if k.get("ad") == secili_ad:
                secili_index = i
                break

        # Kullanıcı bilgilerini al
        kullanici = self.medula_settings.get_kullanici(secili_index)

        if kullanici:
            # Form alanlarını temizle ve yeni değerleri yükle
            self.medula_kullanici_ad_entry.delete(0, tk.END)
            self.medula_kullanici_ad_entry.insert(0, kullanici.get("ad", ""))

            # MEDULA Index combobox'ını ayarla
            medula_index = kullanici.get("kullanici_index", 0)
            if medula_index == 0:
                self.medula_index_var.set("1. Kullanıcı (Index 0)")
            elif medula_index == 1:
                self.medula_index_var.set("2. Kullanıcı (Index 1)")
            elif medula_index == 2:
                self.medula_index_var.set("3. Kullanıcı (Index 2)")
            elif medula_index == 3:
                self.medula_index_var.set("4. Kullanıcı (Index 3)")
            elif medula_index == 4:
                self.medula_index_var.set("5. Kullanıcı (Index 4)")
            elif medula_index == 5:
                self.medula_index_var.set("6. Kullanıcı (Index 5)")

            # Şifreyi yükle
            self.medula_sifre_entry.delete(0, tk.END)
            self.medula_sifre_entry.insert(0, kullanici.get("sifre", ""))

    def medula_bilgilerini_kaydet(self):
        """Seçili kullanıcının MEDULA bilgilerini kaydet"""
        # Formdaki değerleri al
        kullanici_ad = self.medula_kullanici_ad_entry.get().strip()
        sifre = self.medula_sifre_entry.get().strip()

        # MEDULA index'i parse et
        medula_index_str = self.medula_index_var.get()
        if "Index 0" in medula_index_str:
            medula_index = 0
        elif "Index 1" in medula_index_str:
            medula_index = 1
        elif "Index 2" in medula_index_str:
            medula_index = 2
        elif "Index 3" in medula_index_str:
            medula_index = 3
        elif "Index 4" in medula_index_str:
            medula_index = 4
        elif "Index 5" in medula_index_str:
            medula_index = 5
        else:
            messagebox.showwarning("Uyarı", "Lütfen MEDULA kullanıcısını seçin!")
            return

        if not sifre:
            messagebox.showwarning("Uyarı", "Şifre boş olamaz!")
            return

        # Seçili kullanıcı index'ini bul
        secili_ad = self.kullanici_secim_var.get()
        kullanicilar = self.medula_settings.get_kullanicilar()

        secili_index = 0
        for i, k in enumerate(kullanicilar):
            if k.get("ad") == secili_ad:
                secili_index = i
                break

        # Kullanıcı bilgilerini güncelle
        self.medula_settings.update_kullanici(
            secili_index,
            ad=kullanici_ad if kullanici_ad else None,
            kullanici_index=medula_index,
            sifre=sifre
        )

        # Aktif kullanıcıyı ayarla
        self.medula_settings.set_aktif_kullanici(secili_index)

        # Kaydet
        if self.medula_settings.kaydet():
            # Combobox'ı güncelle (kullanıcı adı değiştiyse)
            if kullanici_ad:
                kullanici_listesi = [k.get("ad", f"Kullanıcı {i+1}") for i, k in enumerate(self.medula_settings.get_kullanicilar())]
                self.kullanici_secim_combo['values'] = kullanici_listesi
                self.kullanici_secim_var.set(kullanici_ad)

            messagebox.showinfo("Başarılı", f"{kullanici_ad if kullanici_ad else secili_ad} bilgileri kaydedildi!")
            self.log_ekle(f"✓ {kullanici_ad if kullanici_ad else secili_ad} MEDULA bilgileri güncellendi")
        else:
            messagebox.showerror("Hata", "Kaydetme başarısız!")
            self.log_ekle("❌ MEDULA bilgileri kaydedilemedi")

    def giris_yontemi_degisti(self):
        """Giriş yöntemi değiştiğinde kullanıcı adı entry'sini aktif/pasif yap"""
        yontem = self.giris_yontemi_var.get()
        if yontem == "kullanici_adi":
            self.kullanici_adi_giris_entry.config(state="normal")
        else:
            self.kullanici_adi_giris_entry.config(state="disabled")

    def giris_yontemi_ayarlarini_kaydet(self):
        """Giriş yöntemi ayarlarını kaydet"""
        yontem = self.giris_yontemi_var.get()
        kullanici_adi = self.kullanici_adi_giris_entry.get().strip()

        # Kullanıcı adı yöntemi seçiliyse ama ad girilmemişse uyar
        if yontem == "kullanici_adi" and not kullanici_adi:
            messagebox.showwarning("Uyarı", "Kullanıcı adı ile giriş seçiliyse MEDULA Kullanıcı Adı alanını doldurmalısınız!")
            return

        # Ayarları güncelle
        self.medula_settings.set("giris_yontemi", yontem)
        self.medula_settings.set("kullanici_adi_giris", kullanici_adi)

        if self.medula_settings.kaydet():
            yontem_text = "İndeks" if yontem == "indeks" else f"Kullanıcı Adı ({kullanici_adi})"
            messagebox.showinfo("Başarılı", f"Giriş yöntemi kaydedildi: {yontem_text}")
            self.log_ekle(f"✓ Giriş yöntemi: {yontem_text}")
            logger.info(f"✓ Giriş yöntemi ayarı: {yontem_text}")
        else:
            messagebox.showerror("Hata", "Ayar kaydedilemedi!")
            self.log_ekle("❌ Giriş yöntemi kaydedilemedi")

    def telefon_ayarini_kaydet(self):
        """Telefon kontrolü ayarını kaydet"""
        telefonsuz_atla = self.telefonsuz_atla_var.get()
        self.medula_settings.set("telefonsuz_atla", telefonsuz_atla)

        if self.medula_settings.kaydet():
            durum = "AÇIK" if telefonsuz_atla else "KAPALI"
            self.log_ekle(f"✓ Telefon kontrolü: {durum}")
            logger.info(f"✓ Telefon kontrolü ayarı: {durum}")
        else:
            self.log_ekle("❌ Ayar kaydedilemedi")

    def yasakli_tesis_ekle(self):
        """Yasaklı tesis numarası listesine ekle"""
        tesis_no = self.tesis_entry.get().strip()
        if not tesis_no:
            messagebox.showwarning("Uyarı", "Tesis numarası giriniz!")
            return

        if not tesis_no.isdigit():
            messagebox.showwarning("Uyarı", "Tesis numarası sadece rakamlardan oluşmalıdır!")
            return

        yasakli_tesisler = self.medula_settings.get("yasakli_tesis_numaralari", [])

        if tesis_no in yasakli_tesisler:
            messagebox.showinfo("Bilgi", f"{tesis_no} zaten listede!")
            return

        yasakli_tesisler.append(tesis_no)
        self.medula_settings.set("yasakli_tesis_numaralari", yasakli_tesisler)

        if self.medula_settings.kaydet():
            self.tesis_listbox.insert(tk.END, tesis_no)
            self.tesis_entry.delete(0, tk.END)
            self.log_ekle(f"✓ Yasaklı tesis eklendi: {tesis_no}")
            logger.info(f"✓ Yasaklı tesis eklendi: {tesis_no}")
        else:
            self.log_ekle("❌ Ayar kaydedilemedi")

    def yasakli_tesis_sil(self):
        """Seçili yasaklı tesis numarasını listeden sil"""
        secili = self.tesis_listbox.curselection()
        if not secili:
            messagebox.showwarning("Uyarı", "Silmek için listeden bir tesis seçiniz!")
            return

        index = secili[0]
        tesis_no = self.tesis_listbox.get(index)

        yasakli_tesisler = self.medula_settings.get("yasakli_tesis_numaralari", [])

        if tesis_no in yasakli_tesisler:
            yasakli_tesisler.remove(tesis_no)
            self.medula_settings.set("yasakli_tesis_numaralari", yasakli_tesisler)

            if self.medula_settings.kaydet():
                self.tesis_listbox.delete(index)
                self.log_ekle(f"✓ Yasaklı tesis silindi: {tesis_no}")
                logger.info(f"✓ Yasaklı tesis silindi: {tesis_no}")
            else:
                self.log_ekle("❌ Ayar kaydedilemedi")

    def pencere_yerlesimi_degisti(self):
        """Pencere yerleşimi ayarını kaydet"""
        yerlesim = self.pencere_yerlesimi_var.get()
        self.medula_settings.set("pencere_yerlesimi", yerlesim)

        if self.medula_settings.kaydet():
            if yerlesim == "standart":
                aciklama = "Standart (MEDULA %60 | Konsol %20 | GUI %20)"
            else:
                aciklama = "Geniş MEDULA (MEDULA %80 | GUI %20, Konsol arkada)"
            self.log_ekle(f"✓ Pencere yerleşimi: {aciklama}")
            logger.info(f"✓ Pencere yerleşimi ayarı: {yerlesim}")

            # Pencereleri hemen yeniden yerleştir
            self.root.after(100, self.tum_pencereleri_yerlestir)
        else:
            self.log_ekle("❌ Ayar kaydedilemedi")

    def _ogrenme_modu_toggle(self):
        """Öğrenme modu checkbox değiştiğinde"""
        if self.ogrenme_modu_aktif.get():
            self.ogrenme_modu_label.config(
                text="Aktif - Mesajlı ilaçlarda durup soracak",
                bg="#00897B", fg="white"
            )
            self.log_ekle("🎓 Öğrenme Modu AKTİF - Mesajlı ilaçlarda duracak")
        else:
            self.ogrenme_modu_label.config(
                text="Kapalı - Mesajlı ilaçlarda durmaz",
                bg="#455A64", fg="#B0BEC5"
            )
            self.log_ekle("🎓 Öğrenme Modu KAPALI")

    def ogrenme_modu_basla(self):
        """Öğrenme modu checkbox aktifse BAŞLAT'a basıldığında otomatik çalışır"""
        self.ogrenme_modu_aktif.set(True)
        self._ogrenme_modu_toggle()

    def basla(self):
        """Başlat butonuna basıldığında"""
        logger.info(f"basla() çağrıldı: is_running={self.is_running}, secili_grup={self.secili_grup.get()}")

        if self.is_running:
            logger.warning("Başlatma iptal: is_running=True")
            return

        secili = self.secili_grup.get()
        if not secili:
            self.log_ekle("❌ Lütfen bir grup seçin!")
            logger.warning("Başlatma iptal: grup seçilmemiş")
            return

        # UI güncelle
        self.is_running = True
        self.stop_requested = False
        self.aktif_grup = secili  # Aktif grubu sakla
        self.ardisik_basarisiz_deneme = 0  # Yeni başlatmada sayacı sıfırla

        # İlk kez başlatılıyorsa sıfırla, duraklatılmışsa devam et
        if not self.oturum_duraklatildi:
            self.oturum_recete = 0
            self.oturum_takip = 0
            self.oturum_takipli_recete = 0
            self.oturum_sure_toplam = 0.0
            self.son_recete_sureleri = []  # Son 5 reçete sürelerini sıfırla

            # ✅ YENİ: BİTTİ bilgisini temizle (yeni işlem başlıyor)
            self.grup_durumu.bitti_bilgisi_temizle(secili)
            self.root.after(0, lambda g=secili: self.bitti_bilgisi_guncelle(g))  # GUI'yi güncelle

            # Yeni oturum başlat (database + log dosyası)
            # En gerideki reçeteden başla (aktif fonksiyonlara göre)
            son_recete, baslangic_fonksiyon = self.grup_durumu.en_gerideki_recete_al(secili)
            if baslangic_fonksiyon:
                logger.info(f"En gerideki reçete: {son_recete} ({baslangic_fonksiyon} için)")
            self.aktif_oturum_id = self.database.yeni_oturum_baslat(secili, son_recete)
            self.session_logger = SessionLogger(self.aktif_oturum_id, secili)
            self.log_ekle(f"📝 Yeni oturum başlatıldı (ID: {self.aktif_oturum_id})")
            if son_recete:
                self.log_ekle(f"📍 Başlangıç reçetesi: {son_recete}")
            self.session_logger.info(f"Grup {secili} için yeni oturum başlatıldı")

        self.oturum_baslangic = time.time()
        self.oturum_duraklatildi = False

        self.start_button.config(state="disabled", bg="#616161")
        self.stop_button.config(state="normal", bg="#D32F2F", fg="white")
        self.status_label.config(text="Çalışıyor...", bg="#FFEB3B", fg="#F57F17")

        self.log_ekle(f"▶ Grup {secili} başlatıldı")

        # Süre sayacını başlat
        self.start_stats_timer()

        # Thread başlat
        self.automation_thread = threading.Thread(target=self.otomasyonu_calistir, args=(secili,))
        self.automation_thread.daemon = True
        self.automation_thread.start()

    def tumu_kontrol_et(self):
        """HEPSİNİ KONTROL ET butonuna basıldığında (A→B→C sırayla)"""
        logger.info("tumu_kontrol_et() çağrıldı")

        # Çalışıyorsa engelle
        if self.is_running:
            self.log_ekle("❌ Sistem zaten çalışıyor! Önce durdurun.")
            logger.warning("Tümünü kontrol iptal: is_running=True")
            return

        # ✅ YENİ: Hafızayı SİLME! Sadece aktif modu ayarla
        self.grup_durumu.aktif_mod_ayarla("tumunu_kontrol")
        logger.info("Aktif mod: tumunu_kontrol")

        # Tümünü kontrol modunu aktif et
        self.tumu_kontrol_aktif = True
        self.tumu_kontrol_mevcut_index = 0  # C grubundan başla

        # C grubunu seç (ilk grup)
        ilk_grup = self.tumu_kontrol_grup_sirasi[0]  # "C"
        self.secili_grup.set(ilk_grup)
        self.grup_buttons[ilk_grup].invoke()  # Radio button'ı seç

        self.log_ekle(f"🚀 TÜMÜNÜ KONTROL ET BAŞLATILDI: C → A → B → GK")
        self.log_ekle(f"📍 Başlangıç: Grup {ilk_grup} (kaldığı yerden devam)")

        # NOT: basla() çağırmaya gerek yok, çünkü grup_buttons[ilk_grup].invoke()
        # zaten grup_secildi() → ilk_recete_akisi() → basla() akışını tetikliyor

    def durdur(self):
        """Durdur butonuna basıldığında - HEMEN DURDUR"""
        if not self.is_running:
            return

        # Süreyi kaydet
        if self.oturum_baslangic:
            self.oturum_sure_toplam += (time.time() - self.oturum_baslangic)
            self.oturum_baslangic = None

        # HEMEN DURDUR - is_running'i False yap
        self.is_running = False
        self.oturum_duraklatildi = True
        self.stop_requested = True
        self.aktif_grup = None  # Manuel durdurma - otomatik başlatmayı engelle
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modunu iptal et
        self.stop_button.config(state="disabled", bg="#616161")
        self.status_label.config(text="Durduruluyor...", bg="#FFF9C4", fg="#F9A825")
        self.log_ekle("⏸ DURDUR butonuna basıldı - İşlemler sonlandırılıyor...")

        # Süre sayacını durdur
        self.stats_timer_running = False

        # UI'yi hemen reset et
        self.root.after(500, self.reset_ui)

    def otomatik_yeniden_baslat(self):
        """
        Gelişmiş otomatik yeniden başlatma: Ana Sayfa → Taskkill → Yeniden aç → Login

        Returns:
            bool: Başarılıysa True, başarısızsa False
        """
        try:
            if not self.aktif_grup:
                logger.warning("Aktif grup bulunamadı, yeniden başlatma iptal")
                self.root.after(0, self.reset_ui)
                return False

            # Sayacı artır ve güncelle
            self.yeniden_baslatma_sayaci += 1
            self.root.after(0, lambda: self.restart_label.config(
                text=f"Program {self.yeniden_baslatma_sayaci} kez yeniden başlatıldı"
            ))

            # Database'e kaydet
            if self.aktif_oturum_id:
                self.database.artir(self.aktif_oturum_id, "yeniden_baslatma_sayisi")
                if self.session_logger:
                    self.session_logger.info(f"Yeniden başlatma #{self.yeniden_baslatma_sayaci}")

            self.root.after(0, lambda: self.log_ekle(f"🔄 Otomatik yeniden başlatma #{self.yeniden_baslatma_sayaci}: Grup {self.aktif_grup}"))

            # 1. Adım: 3 sefer "Ana Sayfa" butonuna bas
            self.root.after(0, lambda: self.log_ekle("📍 1. Deneme: Ana Sayfa butonuna basılıyor..."))
            baglanti_basarili = False

            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")

                for deneme in range(1, 4):
                    try:
                        # Ana Sayfa butonunu bul
                        medula_window = desktop.window(title_re=".*MEDULA.*")
                        ana_sayfa_btn = medula_window.child_window(title="Ana Sayfa", control_type="Button")

                        if ana_sayfa_btn.exists(timeout=2):
                            ana_sayfa_btn.click()
                            self.root.after(0, lambda d=deneme: self.log_ekle(f"✓ Ana Sayfa butonu tıklandı ({d}/3)"))
                            time.sleep(1)

                            # Bağlantıyı kontrol et
                            if self.bot and self.bot.baglanti_kur("MEDULA", ilk_baglanti=False):
                                baglanti_basarili = True
                                self.root.after(0, lambda: self.log_ekle("✓ Bağlantı yeniden kuruldu!"))
                                break
                        else:
                            self.root.after(0, lambda d=deneme: self.log_ekle(f"⚠ Ana Sayfa butonu bulunamadı ({d}/3)"))
                    except Exception as e:
                        self.root.after(0, lambda d=deneme, err=str(e): self.log_ekle(f"⚠ Deneme {d}/3 başarısız: {err}"))

                    if deneme < 3:
                        time.sleep(1)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA penceresi bulunamadı: {err}"))

            # 2. Adım: Bağlantı kurulamadıysa taskkill → yeniden aç → login (5 kere dene)
            if not baglanti_basarili:
                self.root.after(0, lambda: self.log_ekle("⚠ 3 deneme başarısız, MEDULA yeniden açılıyor (5 deneme)..."))

                MAX_DENEME = 5
                yeniden_acma_basarili = False

                for deneme in range(1, MAX_DENEME + 1):
                    self.root.after(0, lambda d=deneme: self.log_ekle(f"🔄 Yeniden açma denemesi {d}/{MAX_DENEME}"))

                    # Taskkill
                    self.root.after(0, lambda: self.log_ekle("📍 MEDULA kapatılıyor (taskkill)..."))
                    if medula_taskkill():
                        self.taskkill_sayaci += 1
                        self.root.after(0, lambda: self.log_ekle(f"✓ MEDULA kapatıldı (Taskkill: {self.taskkill_sayaci})"))

                        # Database'e kaydet
                        if self.aktif_oturum_id:
                            self.database.artir(self.aktif_oturum_id, "taskkill_sayisi")
                            if self.session_logger:
                                self.session_logger.warning(f"Taskkill yapıldı (#{self.taskkill_sayaci})")
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız, devam ediliyor..."))

                    # Taskkill sonrası ek bekleme (taskkill fonksiyonu içinde 5 sn bekliyor, buradan ek 2 sn)
                    time.sleep(2)

                    # MEDULA'yı aç ve giriş yap
                    self.root.after(0, lambda: self.log_ekle("📍 MEDULA açılıyor ve giriş yapılıyor..."))
                    try:
                        if medula_ac_ve_giris_yap(self.medula_settings):
                            self.root.after(0, lambda: self.log_ekle("✓ MEDULA açıldı ve giriş yapıldı"))
                            time.sleep(5)  # Botanik kendi CAPTCHA'yı çözüyor, bekleme süresi

                            # Bot'a yeniden bağlan
                            if not self.bot:
                                self.bot = BotanikBot()

                            if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

                                # Konsol penceresini MEDULA'nın sağına yerleştir
                                try:
                                    console_pencereyi_ayarla()
                                    self.root.after(0, lambda: self.log_ekle("✓ Konsol penceresi yerleştirildi"))
                                except Exception as e:
                                    logger.error(f"Konsol yerleştirme hatası: {e}", exc_info=True)

                                yeniden_acma_basarili = True
                                break  # Başarılı, döngüden çık
                            else:
                                self.root.after(0, lambda: self.log_ekle("⚠ MEDULA'ya bağlanılamadı, yeniden denenecek..."))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açılamadı veya giriş yapılamadı, yeniden denenecek..."))
                    except Exception as e:
                        self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA açma/giriş hatası: {err}"))

                    # Son deneme değilse biraz bekle
                    if deneme < MAX_DENEME:
                        self.root.after(0, lambda: self.log_ekle("⏳ 3 saniye bekleniyor..."))
                        time.sleep(3)

                # 5 deneme sonucu kontrol et
                if not yeniden_acma_basarili:
                    self.root.after(0, lambda: self.log_ekle("❌ 5 deneme de başarısız oldu!"))
                    return False  # Başarısız

            # 3. Adım: GUI'deki grup butonuna bas
            self.root.after(0, lambda: self.log_ekle(f"📍 Grup {self.aktif_grup} seçiliyor..."))
            time.sleep(1)

            # Grup butonunu bul ve tıkla
            if self.aktif_grup in self.grup_buttons:
                self.grup_buttons[self.aktif_grup].invoke()
                self.root.after(0, lambda: self.log_ekle(f"✓ Grup {self.aktif_grup} seçildi"))
            else:
                self.root.after(0, lambda: self.log_ekle(f"⚠ Grup {self.aktif_grup} butonu bulunamadı"))
                return False  # Başarısız

            time.sleep(1)

            # 4. Adım: SON REÇETEYE GİT (Kaldığı yerden devam)
            son_recete = self.grup_durumu.son_recete_al(self.aktif_grup)
            if son_recete:
                self.root.after(0, lambda: self.log_ekle(f"📍 Son reçeteye gidiliyor: {son_recete}"))
                try:
                    # Reçete Sorgu'ya git
                    if self.bot.recete_sorgu_ac():
                        self.root.after(0, lambda: self.log_ekle("✓ Reçete Sorgu açıldı"))
                        time.sleep(1)

                        # Reçete numarasını yaz
                        if self.bot.recete_no_yaz(son_recete):
                            self.root.after(0, lambda: self.log_ekle(f"✓ Reçete No yazıldı: {son_recete}"))
                            time.sleep(0.5)

                            # Sorgula butonuna bas
                            if self.bot.sorgula_butonuna_tikla():
                                self.root.after(0, lambda: self.log_ekle("✓ Sorgula butonuna basıldı"))
                                time.sleep(2)  # Reçetenin açılmasını bekle

                                self.root.after(0, lambda: self.log_ekle(f"✅ Kaldığı yerden devam ediliyor: {son_recete}"))

                                # 5. Adım: Başlat butonuna bas (devam için)
                                self.root.after(0, lambda: self.log_ekle("📍 Başlat butonuna basılıyor..."))
                                time.sleep(1)
                                self.root.after(0, self.basla)
                                self.root.after(0, lambda: self.log_ekle("✓ Otomatik yeniden başlatıldı (kaldığı yerden devam)"))

                                # Başarılı yeniden başlatma - sayacı sıfırla
                                self.ardisik_basarisiz_deneme = 0
                                return True  # Başarılı
                            else:
                                self.root.after(0, lambda: self.log_ekle("⚠ Sorgula butonuna basılamadı"))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ Reçete No yazılamadı"))
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Reçete Sorgu açılamadı"))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Reçete bulma hatası: {err}"))
                    logger.error(f"Reçete bulma hatası: {e}", exc_info=True)

                # Reçete bulunamazsa normal başlat
                self.root.after(0, lambda: self.log_ekle("⚠ Son reçete bulunamadı, gruptan başlatılıyor"))

            # 5. Adım: Başlat butonuna bas (normal başlatma veya fallback)
            self.root.after(0, lambda: self.log_ekle("📍 Başlat butonuna basılıyor..."))
            time.sleep(1)
            self.root.after(0, self.basla)
            self.root.after(0, lambda: self.log_ekle("✓ Otomatik yeniden başlatıldı"))

            # Başarılı yeniden başlatma - sayacı sıfırla
            self.ardisik_basarisiz_deneme = 0
            return True  # Başarılı

        except Exception as e:
            logger.error(f"Otomatik yeniden başlatma hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Yeniden başlatma hatası: {err}"))
            return False  # Başarısız

    def otomasyonu_calistir(self, grup):
        """Ana otomasyon döngüsü"""
        try:
            # Bot yoksa oluştur ve bağlan
            if self.bot is None:
                self.bot = BotanikBot()
                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA'ya bağlanılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

                # NOT: 3x Giriş butonuna basma KALDIRILDI!
                # Reçete açıkken giriş butonuna basmak reçeteden çıkılmasına neden oluyordu
                time.sleep(0.5)
                self.root.after(0, lambda: self.log_ekle("✓ MEDULA oturumu hazır"))
            else:
                # Bot zaten var, pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

                # NOT: 3x Giriş butonuna basma KALDIRILDI!
                # Reçete açıkken giriş butonuna basmak reçeteden çıkılmasına neden oluyordu
                time.sleep(0.5)
                self.root.after(0, lambda: self.log_ekle("✓ MEDULA oturumu hazır"))

            # Reçete zaten açık (grup seçiminde açıldı)
            self.root.after(0, lambda: self.log_ekle("▶ Reçete takibi başlıyor..."))

            time.sleep(0.75)  # Güvenli hasta takibi için: 0.5 → 0.75

            # Reçete döngüsü
            recete_sira = 1
            oturum_sure_toplam = 0.0

            # ✅ YENİ: Reçete takip değişkenleri (takılma önleme)
            son_basarili_recete_no = None  # Son başarılı reçete numarası
            onceki_recete_no = None  # Bir önceki denenen reçete numarası
            ayni_recete_deneme = 0  # Aynı reçete için ardışık deneme sayısı
            ardisik_atlanan = 0  # Ardışık atlanan reçete sayısı (5'te dur)
            MAX_AYNI_RECETE_DENEME = 3  # Aynı reçetede max deneme
            MAX_ARDISIK_ATLAMA = 5  # Ardışık max atlama sayısı

            try:
                while not self.stop_requested and self.is_running:
                    # Her iterasyonda kontrol et - DUR butonuna hızlı yanıt
                    if self.stop_requested or not self.is_running:
                        self.root.after(0, lambda: self.log_ekle("⏸ İşlem durduruldu (kullanıcı talebi)"))
                        break

                    recete_baslangic = time.time()

                    self.root.after(0, lambda r=recete_sira: self.log_ekle(f"📋 Reçete {r} işleniyor..."))

                    # Popup kontrolü (reçete açılmadan önce)
                    try:
                        if popup_kontrol_ve_kapat():
                            self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                            if self.session_logger:
                                self.session_logger.info("Popup tespit edilip kapatıldı")
                    except Exception as e:
                        logger.warning(f"Popup kontrol hatası: {e}")

                    # Reçete numarasını oku
                    medula_recete_no = self.bot.recete_no_oku()
                    if medula_recete_no:
                        # Grup label'ını güncelle
                        self.root.after(0, lambda no=medula_recete_no: self.grup_labels[grup].config(text=no))
                        # Hafızaya kaydet
                        self.grup_durumu.son_recete_guncelle(grup, medula_recete_no)
                        self.root.after(0, lambda no=medula_recete_no: self.log_ekle(f"🏷 No: {no}"))

                        # Fonksiyona göre reçete hafızası ve label güncelle
                        _fa = self.grup_durumu.fonksiyon_ayarlari_al()
                        _sadece_rk = (
                            _fa.get("rapor_kontrol_aktif", False) and
                            not _fa.get("ilac_takip_aktif", True) and
                            not _fa.get("rapor_toplama_aktif", True)
                        )
                        if _sadece_rk:
                            self.grup_durumu.son_recete_guncelle_fonksiyon(grup, "rapor_kontrol", medula_recete_no)
                            self.root.after(0, lambda no=medula_recete_no: self.grup_rapor_kontrol_labels[grup].config(text=f"RK: {no}"))
                        else:
                            self.grup_durumu.son_recete_guncelle_fonksiyon(grup, "ilac_takip", medula_recete_no)

                        # ✅ YENİ: Aynı reçete kontrolü (takılma önleme)
                        if medula_recete_no == onceki_recete_no:
                            ayni_recete_deneme += 1
                            self.root.after(0, lambda d=ayni_recete_deneme: self.log_ekle(f"⚠️ Aynı reçete tekrar deneniyor ({d}/{MAX_AYNI_RECETE_DENEME})"))

                            # "Başka eczaneye aittir" kontrolü
                            if self.bot.baska_eczane_uyarisi_var_mi():
                                self.root.after(0, lambda: self.log_ekle("🚨 BAŞKA ECZANE UYARISI! Son başarılı reçeteden devam edilecek..."))
                                if self.session_logger:
                                    self.session_logger.warning(f"Başka eczane uyarısı: {medula_recete_no}")

                                # Son başarılı reçeteden devam et
                                if son_basarili_recete_no:
                                    self.root.after(0, lambda r=son_basarili_recete_no: self.log_ekle(f"📍 Son başarılı reçeteye dönülüyor: {r}"))
                                    # Yeniden başlat ve son başarılı reçeteden devam
                                    if medula_yeniden_baslat_ve_giris_yap(self.bot, grup, son_basarili_recete_no):
                                        self.root.after(0, lambda: self.log_ekle("✅ Son başarılı reçeteden devam ediliyor"))
                                        onceki_recete_no = None
                                        ayni_recete_deneme = 0
                                        continue
                                    else:
                                        self.root.after(0, lambda: self.log_ekle("❌ Yeniden başlatma başarısız!"))
                                        break
                                else:
                                    self.root.after(0, lambda: self.log_ekle("⚠️ Son başarılı reçete yok, sistem durduruluyor"))
                                    break

                            # Max deneme aşıldı - bu reçeteyi atla
                            if ayni_recete_deneme >= MAX_AYNI_RECETE_DENEME:
                                self.root.after(0, lambda: self.log_ekle(f"⏭️ {MAX_AYNI_RECETE_DENEME} deneme başarısız, reçete atlanıyor..."))
                                if self.session_logger:
                                    self.session_logger.warning(f"Reçete atlandı (max deneme): {medula_recete_no}")

                                # SONRA butonuna bas ve geç
                                try:
                                    if self.bot.sonra_butonuna_tikla():
                                        ardisik_atlanan += 1
                                        self.root.after(0, lambda a=ardisik_atlanan: self.log_ekle(f"⏭️ Reçete atlandı (ardışık: {a}/{MAX_ARDISIK_ATLAMA})"))
                                        ayni_recete_deneme = 0
                                        onceki_recete_no = None

                                        # Çok fazla ardışık atlama - sistemi durdur
                                        if ardisik_atlanan >= MAX_ARDISIK_ATLAMA:
                                            self.root.after(0, lambda: self.log_ekle(f"🛑 {MAX_ARDISIK_ATLAMA} ardışık reçete atlandı! Sistem durduruluyor..."))
                                            if self.session_logger:
                                                self.session_logger.error(f"Sistem durduruldu: {MAX_ARDISIK_ATLAMA} ardışık atlama")
                                            break
                                        continue
                                    else:
                                        self.root.after(0, lambda: self.log_ekle("❌ SONRA butonu başarısız!"))
                                        break
                                except Exception as e:
                                    self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Atlama hatası: {err}"))
                                    break
                        else:
                            # Farklı reçete - sayaçları sıfırla
                            ayni_recete_deneme = 0

                        onceki_recete_no = medula_recete_no

                    # Görev tamamlandı mı kontrol et (reçete bulunamadı mesajı)
                    try:
                        if recete_kaydi_bulunamadi_mi(self.bot):
                            self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))

                            # ✅ YENİ: Popup'ı kapat (grup geçişinden önce!)
                            try:
                                logger.info("🔄 Görev tamamlama popup'ı kapatılıyor...")
                                popup_kapatildi = popup_kontrol_ve_kapat()
                                if popup_kapatildi:
                                    self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                                    logger.info("✓ Popup başarıyla kapatıldı")
                                time.sleep(0.5)  # Popup'ın tamamen kapanması için bekle
                            except Exception as popup_err:
                                logger.warning(f"Popup kapatma hatası (devam ediliyor): {popup_err}")

                            if self.session_logger:
                                self.session_logger.basari("Görev başarıyla tamamlandı")

                            # ✅ YENİ: BİTTİ bilgisini kaydet
                            from datetime import datetime
                            bugun = datetime.now().strftime("%Y-%m-%d")
                            self.grup_durumu.bitti_bilgisi_ayarla(grup, bugun, self.oturum_recete)
                            self.root.after(0, lambda g=grup: self.bitti_bilgisi_guncelle(g))  # GUI'yi güncelle
                            logger.info(f"✅ Grup {grup} BİTTİ: {bugun}, {self.oturum_recete} reçete")

                            # Database'i güncelle ve oturumu bitir
                            if self.aktif_oturum_id:
                                ortalama_sure = oturum_sure_toplam / self.oturum_recete if self.oturum_recete > 0 else 0
                                self.database.oturum_guncelle(
                                    self.aktif_oturum_id,
                                    toplam_recete=self.oturum_recete,
                                    toplam_takip=self.oturum_takip,
                                    ortalama_recete_suresi=ortalama_sure
                                )
                                son_recete = self.grup_durumu.son_recete_al(grup)
                                self.database.oturum_bitir(self.aktif_oturum_id, bitis_recete=son_recete)

                                if self.session_logger:
                                    self.session_logger.ozet_yaz(
                                        self.oturum_recete,
                                        self.oturum_takip,
                                        ortalama_sure,
                                        self.yeniden_baslatma_sayaci,
                                        self.taskkill_sayaci
                                    )
                                    self.session_logger.kapat()

                            # TÜMÜNÜ KONTROL ET modu kontrolü
                            if self.tumu_kontrol_aktif:
                                # Mevcut grubu tamamlandı, sonrakine geç
                                self.tumu_kontrol_mevcut_index += 1

                                if self.tumu_kontrol_mevcut_index < len(self.tumu_kontrol_grup_sirasi):
                                    # Sonraki grup var
                                    sonraki_grup = self.tumu_kontrol_grup_sirasi[self.tumu_kontrol_mevcut_index]
                                    self.root.after(0, lambda g=grup, sg=sonraki_grup:
                                        self.log_ekle(f"✅ Grup {g} tamamlandı! → Sıradaki: Grup {sg}"))

                                    # Oturumu bitir (mevcut grup için)
                                    if self.session_logger:
                                        self.session_logger.ozet_yaz(
                                            self.oturum_recete,
                                            self.oturum_takip,
                                            ortalama_sure,
                                            self.yeniden_baslatma_sayaci,
                                            self.taskkill_sayaci
                                        )
                                        self.session_logger.kapat()
                                        self.session_logger = None

                                    # Sonraki gruba geçiş işlemi
                                    def sonraki_gruba_gec():
                                        try:
                                            self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"🔄 {sg} grubuna geçiliyor..."))
                                            logger.info(f"🔄 Sonraki gruba geçiliyor: {sonraki_grup}")

                                            # Son reçeteyi al - kaldığı yerden devam için
                                            son_recete_gecis = self.grup_durumu.son_recete_al(sonraki_grup)
                                            if son_recete_gecis:
                                                self.root.after(0, lambda r=son_recete_gecis: self.log_ekle(f"📍 Kaldığı yerden devam edilecek: {r}"))

                                            # Grup geçiş işlemini yap (son_recete varsa kaldığı yerden, yoksa en baştan)
                                            if sonraki_gruba_gec_islemi(self.bot, sonraki_grup, son_recete_gecis):
                                                self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"✅ {sg} grubuna geçildi"))

                                                # UI durumunu güncelle
                                                self.is_running = False
                                                self.oturum_duraklatildi = False
                                                self.secili_grup.set(sonraki_grup)
                                                self.aktif_grup = sonraki_grup

                                                # Yeni oturum başlat
                                                self.oturum_recete = 0
                                                self.oturum_takip = 0
                                                self.oturum_takipli_recete = 0
                                                self.oturum_sure_toplam = 0.0
                                                self.son_recete_sureleri = []

                                                # Database ve logger
                                                son_recete = self.grup_durumu.son_recete_al(sonraki_grup)
                                                self.aktif_oturum_id = self.database.yeni_oturum_baslat(sonraki_grup, son_recete)
                                                self.session_logger = SessionLogger(self.aktif_oturum_id, sonraki_grup)
                                                self.root.after(0, lambda: self.log_ekle(f"📝 Yeni oturum başlatıldı (ID: {self.aktif_oturum_id})"))

                                                # Grup rengini güncelle
                                                for g in ["C", "A", "B", "GK"]:
                                                    if g in self.grup_frames:
                                                        bg_color = "#BBDEFB" if g == sonraki_grup else "#E8F5E9"
                                                        self.grup_frames[g]['main'].config(bg=bg_color)
                                                        for widget in self.grup_frames[g]['widgets']:
                                                            try:
                                                                widget.config(bg=bg_color)
                                                            except Exception as e:
                                                                logger.debug(f"Widget bg config failed: {type(e).__name__}")

                                                # İşleme başla
                                                self.root.after(500, lambda: self.basla())
                                            else:
                                                raise Exception("Grup geçişi başarısız")

                                        except Exception as e:
                                            # Hata - taskkill + yeniden başlat
                                            logger.error(f"Grup geçişi hatası: {e}")
                                            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Grup geçişi hatası: {err}"))
                                            self.root.after(0, lambda: self.log_ekle("🔄 MEDULA yeniden başlatılıyor..."))

                                            # Taskkill
                                            if medula_taskkill():
                                                self.root.after(0, lambda: self.log_ekle("✓ MEDULA kapatıldı"))
                                                self.taskkill_sayaci += 1
                                                time.sleep(3)
                                            else:
                                                self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız"))

                                            # Yeniden başlat ve giriş yap (aktif grupla, son reçeteden devam)
                                            son_recete = self.grup_durumu.son_recete_al(sonraki_grup)
                                            if son_recete:
                                                self.root.after(0, lambda r=son_recete: self.log_ekle(f"📍 Kaldığı yerden devam edilecek: {r}"))
                                            if medula_yeniden_baslat_ve_giris_yap(self.bot, sonraki_grup, son_recete):
                                                self.root.after(0, lambda: self.log_ekle("✅ MEDULA yeniden başlatıldı"))
                                                self.yeniden_baslatma_sayaci += 1

                                                # Konsol penceresini MEDULA'nın sağına yerleştir
                                                try:
                                                    console_pencereyi_ayarla()
                                                except Exception as e:
                                                    logger.error(f"Konsol yerleştirme hatası: {e}", exc_info=True)

                                                # Sonraki gruba tekrar geç
                                                self.root.after(0, lambda: self.log_ekle(f"🔄 {sonraki_grup} grubuna tekrar geçiliyor..."))
                                                try:
                                                    # Son reçeteyi al - kaldığı yerden devam için
                                                    son_recete_gecis2 = self.grup_durumu.son_recete_al(sonraki_grup)
                                                    if sonraki_gruba_gec_islemi(self.bot, sonraki_grup, son_recete_gecis2):
                                                        self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"✅ {sg} grubuna geçildi"))
                                                        # UI güncelle ve başlat
                                                        self.is_running = False
                                                        self.oturum_duraklatildi = False
                                                        self.secili_grup.set(sonraki_grup)
                                                        self.aktif_grup = sonraki_grup
                                                        self.oturum_recete = 0
                                                        self.oturum_takip = 0
                                                        self.oturum_takipli_recete = 0
                                                        self.oturum_sure_toplam = 0.0
                                                        self.son_recete_sureleri = []
                                                        son_recete = self.grup_durumu.son_recete_al(sonraki_grup)
                                                        self.aktif_oturum_id = self.database.yeni_oturum_baslat(sonraki_grup, son_recete)
                                                        self.session_logger = SessionLogger(self.aktif_oturum_id, sonraki_grup)
                                                        self.root.after(500, lambda: self.basla())
                                                    else:
                                                        raise Exception("2. deneme de başarısız")
                                                except Exception as e2:
                                                    logger.error(f"2. deneme de başarısız: {e2}")
                                                    self.root.after(0, lambda: self.log_ekle("❌ Grup geçişi 2. deneme de başarısız!"))
                                                    self.root.after(0, self.reset_ui)
                                            else:
                                                self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı!"))
                                                self.root.after(0, self.reset_ui)

                                    self.root.after(0, sonraki_gruba_gec)

                                    break  # Mevcut grup thread'ini bitir
                                else:
                                    # Tüm gruplar tamamlandı
                                    self.tumu_kontrol_aktif = False
                                    self.root.after(0, lambda: self.log_ekle("🎉 TÜMÜ TAMAMLANDI! A, B, C gruplarının hepsi kontrol edildi."))
                                    self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                                    break
                            else:
                                # Normal mod - sadece raporu göster
                                self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                                break
                    except Exception as e:
                        logger.warning(f"Görev tamamlama kontrolü hatası: {e}")

                    # Renkli reçete kontrolü - listede varsa atla
                    if self.renkli_recete.liste_yuklu_mu() and self.renkli_recete.recete_var_mi(medula_recete_no):
                        logger.info(f"🔴🟢 Renkli reçete listesinde var, atlanıyor: {medula_recete_no}")
                        self.root.after(0, lambda r=medula_recete_no: self.log_ekle(f"🔴🟢 Renkli reçetede var: {r}"))

                        # Sonraki reçeteye geç
                        try:
                            sonra = self.bot.retry_with_popup_check(
                                lambda: self.bot.sonra_butonuna_tikla(),
                                "SONRA butonu",
                                max_retries=5
                            )
                            if sonra:
                                recete_sira += 1
                                onceki_recete_no = medula_recete_no
                                continue  # Sonraki reçeteye geç
                        except Exception as e:
                            logger.warning(f"Renkli reçete atlama - SONRA butonu hatası: {e}")

                    # Tek reçete işle
                    try:
                        # stop_check: DURDUR butonuna basıldığında hemen durması için
                        # onceden_okunan_recete_no: GUI'de zaten okundu, tekrar okuma yapılmasın
                        # onceki_recete_no: Ardışık aynı reçete kontrolü için (optimize)
                        # fonksiyon_ayarlari: Aktif fonksiyonlar (ilaç takip, rapor toplama, rapor kontrol)
                        fonksiyon_ayarlari = self.grup_durumu.fonksiyon_ayarlari_al()

                        # SADECE rapor kontrol aktifse (ilaç takip ve rapor toplama pasif)
                        sadece_rapor_kontrol = (
                            fonksiyon_ayarlari.get("rapor_kontrol_aktif", False) and
                            not fonksiyon_ayarlari.get("ilac_takip_aktif", True) and
                            not fonksiyon_ayarlari.get("rapor_toplama_aktif", True)
                        )

                        # ═══ ÖĞRENME MODU ═══
                        if self.ogrenme_modu_aktif.get():
                            from ogrenme_modu import (
                                ogrenme_modu_reçete_isle,
                                ogrenme_modu_thread_safe_callback,
                                OgrenmeModuKayit
                            )

                            # Renkli reçete kontrol instance
                            if not self.renkli_recete_kontrol:
                                from recete_kontrol import get_renkli_recete_kontrol
                                self.renkli_recete_kontrol = get_renkli_recete_kontrol()

                            # Kullanıcı callback (thread-safe popup)
                            def _ogrenme_callback(ilac_bilgi):
                                tip = ilac_bilgi.get('tip', '')
                                if tip == 'renkli_recete_uyari':
                                    self.root.after(0, lambda m=ilac_bilgi.get('mesaj', ''): self.log_ekle(f"⚠️ RENKLI: {m}"))
                                    return "devam"
                                elif tip == 'mesajli_ilac':
                                    ilac_adi = ilac_bilgi.get('ilac_adi', '?')
                                    self.root.after(0, lambda a=ilac_adi: self.log_ekle(f"🎓 Mesajlı ilaç: {a} - popup gösteriliyor..."))
                                    return ogrenme_modu_thread_safe_callback(self.root, ilac_bilgi)
                                return "devam"

                            ogrenme_sonuc = ogrenme_modu_reçete_isle(
                                self.bot, recete_sira,
                                grup=self.aktif_grup,
                                session_logger=self.session_logger,
                                stop_check=lambda: self.stop_requested or not self.is_running,
                                onceden_okunan_recete_no=medula_recete_no,
                                renkli_kontrol=self.renkli_recete_kontrol,
                                kullanici_callback=_ogrenme_callback
                            )

                            basari = ogrenme_sonuc.get('basari', False)
                            medula_no = ogrenme_sonuc.get('recete_no')
                            takip_adet = 0

                            # Algoritmik öğrenme bekliyor mu?
                            if ogrenme_sonuc.get('algoritmik_ogren_bekliyor'):
                                bekleyen = ogrenme_sonuc.get('bekleyen_ilac', {})
                                ilac_adi_bek = bekleyen.get('ilac_adi', '?')
                                mesaj_bek = bekleyen.get('mesaj_metni', '')[:100]
                                self.root.after(0, lambda a=ilac_adi_bek, m=mesaj_bek: self.log_ekle(
                                    f"📚 ALGORİTMİK ÖĞRENME: {a}\n   Mesaj: {m}...\n   Claude Code'da kuralı öğretin, sonra sistemi devam ettirin."))
                                # Sistemi durdur - kullanıcı Claude Code'da kuralı öğretecek
                                self.stop_requested = True
                                break

                            # Öğrenme sonucunu logla
                            msj_sayi = ogrenme_sonuc.get('mesajli_ilac_sayisi', 0)
                            doz_sayi = ogrenme_sonuc.get('doz_asimi_sayisi', 0)
                            toplam = ogrenme_sonuc.get('toplam_ilac', 0)
                            self.root.after(0, lambda t=toplam, m=msj_sayi, d=doz_sayi: self.log_ekle(
                                f"🎓 İlaç:{t} Mesajlı:{m} DozAşımı:{d}"))

                            hata_nedeni = ogrenme_sonuc.get('hata')

                        elif sadece_rapor_kontrol:
                            # Renkli recete kontrol instance yoksa otomatik yukle
                            if not self.renkli_recete_kontrol:
                                from recete_kontrol import get_renkli_recete_kontrol
                                self.renkli_recete_kontrol = get_renkli_recete_kontrol()
                                if self.renkli_recete_kontrol.pdf_yuklu:
                                    self.root.after(0, lambda: self.log_ekle(
                                        "Renkli recete listesi otomatik yuklendi: {} recete".format(
                                            len(self.renkli_recete_kontrol.pdf_receteler))))
                                else:
                                    self.root.after(0, lambda: self.log_ekle(
                                        "Renkli recete listesi yuklenmemis! Once liste yukleyin."))

                            # Sadece renkli reçete kontrolü yap
                            basari, medula_no, sorun_var, hata_nedeni = tek_recete_rapor_kontrol(
                                self.bot, recete_sira,
                                grup=self.aktif_grup,
                                session_logger=self.session_logger,
                                stop_check=lambda: self.stop_requested or not self.is_running,
                                onceden_okunan_recete_no=medula_recete_no,
                                renkli_kontrol=self.renkli_recete_kontrol
                            )
                            takip_adet = 0  # Rapor kontrolde takip yok

                            # Sorunlu reçete varsa logla
                            if sorun_var and hata_nedeni:
                                self.root.after(0, lambda m=hata_nedeni: self.log_ekle(f"⚠️ {m}"))
                        else:
                            # Normal akış (ilaç takip ve/veya rapor toplama)
                            basari, medula_no, takip_adet, hata_nedeni = tek_recete_isle(
                                self.bot, recete_sira, self.rapor_takip,
                                grup=self.aktif_grup,
                                session_logger=self.session_logger,
                                onceden_okunan_recete_no=medula_recete_no,
                                onceki_recete_no=onceki_recete_no,
                                stop_check=lambda: self.stop_requested or not self.is_running,
                                fonksiyon_ayarlari=fonksiyon_ayarlari
                            )
                    except SistemselHataException as e:
                        # ✅ Sistemsel hata yakalandı!
                        self.root.after(0, lambda: self.log_ekle("⚠️ SİSTEMSEL HATA TESPİT EDİLDİ!"))
                        logger.error(f"Sistemsel hata: {e}")

                        # MEDULA'yı yeniden başlat
                        self.root.after(0, lambda: self.log_ekle("🔄 MEDULA yeniden başlatılıyor..."))
                        # Aktif grubu al
                        aktif_mod = self.grup_durumu.aktif_mod_al()
                        aktif_grup = aktif_mod if aktif_mod in ["C", "A", "B", "GK"] else self.aktif_grup

                        # Son reçeteden devam et
                        son_recete = self.grup_durumu.son_recete_al(aktif_grup)
                        if son_recete:
                            self.root.after(0, lambda r=son_recete: self.log_ekle(f"📍 Kaldığı yerden devam edilecek: {r}"))

                        if medula_yeniden_baslat_ve_giris_yap(self.bot, aktif_grup, son_recete):
                            self.root.after(0, lambda: self.log_ekle("✅ MEDULA başarıyla yeniden başlatıldı"))

                            # Konsol penceresini MEDULA'nın sağına yerleştir
                            try:
                                console_pencereyi_ayarla()
                            except Exception as e:
                                logger.error(f"Konsol yerleştirme hatası: {e}", exc_info=True)

                            # Aktif modu kontrol et ve devam et
                            self.root.after(0, lambda m=aktif_mod: self.log_ekle(f"📍 Aktif mod: {m}"))

                            if aktif_mod == "tumunu_kontrol":
                                # Tümünü kontrol et modunu yeniden aktif et
                                self.tumu_kontrol_aktif = True
                                self.root.after(0, lambda: self.log_ekle("🔄 Tümünü kontrol et modu devam ediyor..."))

                            # Kaldığı yerden devam et (reçete zaten açık, işlemi tekrarla)
                            continue
                        else:
                            self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı!"))
                            break

                    # Popup kontrolü (reçete işlendikten sonra)
                    try:
                        if popup_kontrol_ve_kapat():
                            self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                            if self.session_logger:
                                self.session_logger.info("Popup tespit edilip kapatıldı")
                    except Exception as e:
                        logger.warning(f"Popup kontrol hatası: {e}")

                    recete_sure = time.time() - recete_baslangic
                    oturum_sure_toplam += recete_sure

                    if basari:
                        self.oturum_recete += 1
                        self.oturum_takip += takip_adet

                        # ✅ YENİ: Başarılı reçete - takip değişkenlerini güncelle
                        son_basarili_recete_no = medula_recete_no  # Son başarılı reçeteyi kaydet
                        ardisik_atlanan = 0  # Ardışık atlama sayacını sıfırla

                        # Takipli ilaç varsa takipli reçete sayacını artır
                        if takip_adet > 0:
                            self.oturum_takipli_recete += 1

                        # Son 5 reçete süresini sakla
                        self.son_recete_sureleri.append(recete_sure)
                        if len(self.son_recete_sureleri) > 5:
                            self.son_recete_sureleri.pop(0)  # En eskiyi sil

                        # Süreyi formatla (saniye.milisaniye)
                        sure_sn = int(recete_sure)
                        sure_ms = int((recete_sure * 1000) % 1000)

                        self.root.after(0, lambda r=recete_sira, t=takip_adet, s=sure_sn, ms=sure_ms:
                                       self.log_ekle(f"✅ Reçete {r} | {t} ilaç takip | {s}.{ms:03d}s"))

                        # İstatistikleri güncelle
                        takipli_recete = 1 if takip_adet > 0 else 0
                        self.grup_durumu.istatistik_guncelle(grup, 1, takip_adet, takipli_recete, recete_sure)

                        # Aylık istatistik labelını güncelle
                        self.root.after(0, lambda g=grup: self.aylik_istatistik_guncelle(g))

                        # Database'e kaydet (her reçete sonrası)
                        if self.aktif_oturum_id:
                            ortalama_sure = oturum_sure_toplam / self.oturum_recete if self.oturum_recete > 0 else 0
                            self.database.oturum_guncelle(
                                self.aktif_oturum_id,
                                toplam_recete=self.oturum_recete,
                                toplam_takip=self.oturum_takip,
                                ortalama_recete_suresi=ortalama_sure
                            )

                        recete_sira += 1
                    else:
                        # Hata nedenini loga yaz
                        if hata_nedeni:
                            # Kullanıcı tarafından durdurulduysa özel mesaj
                            if "Kullanıcı tarafından durduruldu" in hata_nedeni:
                                self.root.after(0, lambda: self.log_ekle("⏸ İşlem kullanıcı tarafından durduruldu"))
                            else:
                                self.root.after(0, lambda h=hata_nedeni: self.log_ekle(f"❌ Program Durdu: {h}"))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ Reçete işlenemedi veya son reçete"))
                        break

                    if self.stop_requested:
                        break

            except SistemselHataException as e:
                # ✅ Döngü dışında sistemsel hata (genel catch)
                self.root.after(0, lambda: self.log_ekle("⚠️ SİSTEMSEL HATA (DÖNGÜ DIŞI)"))
                logger.error(f"Sistemsel hata (döngü dışı): {e}")
                # Yeniden başlatma zaten tek_recete_isle içinde yapılıyor
                pass

            # Normal sonlanma (son reçete veya break)
            # Görev sonu kontrolü
            gorev_tamamlandi = False
            try:
                # Global import kullan (local import kaldırıldı - scope hatası önlendi)
                if self.bot and recete_kaydi_bulunamadi_mi(self.bot):
                    gorev_tamamlandi = True
                    self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))
            except Exception as e:
                logger.warning(f"Görev tamamlama kontrolü hatası: {e}")

            # Otomatik yeniden başlatma kontrolü
            if self.aktif_grup and not self.stop_requested and not gorev_tamamlandi:
                # Hata veya beklenmeyen durma - otomatik yeniden başlat
                self.is_running = False
                self.ardisik_basarisiz_deneme += 1

                if self.ardisik_basarisiz_deneme >= 5:
                    self.root.after(0, lambda: self.log_ekle("❌ 5 DENEME BAŞARISIZ! Sistem durduruluyor..."))
                    self.root.after(0, lambda: messagebox.showerror(
                        "Yeniden Başlatma Başarısız",
                        f"5 deneme sonrası MEDULA yeniden başlatılamadı.\n\n"
                        f"Lütfen MEDULA'yı manuel olarak kontrol edin ve tekrar deneyin."
                    ))
                    self.root.after(0, self.reset_ui)
                    return

                self.root.after(0, lambda d=self.ardisik_basarisiz_deneme: self.log_ekle(f"⏳ 2 saniye sonra otomatik yeniden başlatılacak... (Deneme {d}/5)"))
                time.sleep(2)

                # Yeniden başlat
                def yeniden_baslat_ve_kontrol():
                    basarili = self.otomatik_yeniden_baslat()
                    if not basarili:
                        self.root.after(0, lambda: self.log_ekle(f"⚠ Yeniden başlatma başarısız (Deneme {self.ardisik_basarisiz_deneme}/5)"))

                recovery_thread = threading.Thread(target=yeniden_baslat_ve_kontrol)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma, aktif grup yok veya görev tamamlandı - UI'yi resetle
                self.root.after(0, self.reset_ui)

        except Exception as e:
            logger.error(f"Otomasyon hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Hata: {err}"))
            self.root.after(0, self.hata_sesi_calar)

            # 1. ADIM: Görev sonu kontrolü (Reçete kaydı bulunamadı mesajı)
            gorev_tamamlandi = False
            try:
                # Global import kullan (local import kaldırıldı - scope hatası önlendi)
                if self.bot and recete_kaydi_bulunamadi_mi(self.bot):
                    gorev_tamamlandi = True
                    self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))
                    if self.session_logger:
                        self.session_logger.basari("Görev başarıyla tamamlandı (hata sonrası kontrol)")

                    # Database'i güncelle ve oturumu bitir
                    if self.aktif_oturum_id:
                        son_recete = self.grup_durumu.son_recete_al(grup) if grup else None
                        self.database.oturum_bitir(self.aktif_oturum_id, bitis_recete=son_recete)

                        if self.session_logger:
                            self.session_logger.ozet_yaz(
                                self.oturum_recete,
                                self.oturum_takip,
                                0.0,
                                self.yeniden_baslatma_sayaci,
                                self.taskkill_sayaci
                            )
                            self.session_logger.kapat()

                    # Görev tamamlama raporu göster
                    self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                    self.root.after(0, self.reset_ui)
                    return
            except Exception as kontrol_hatasi:
                logger.warning(f"Görev tamamlama kontrolü hatası: {kontrol_hatasi}")

            # 2. ADIM: Görev sonu değilse, otomatik yeniden başlatma yap
            otomatik_baslatilacak = self.aktif_grup and not self.stop_requested and not gorev_tamamlandi

            if otomatik_baslatilacak:
                # Ardışık başarısız deneme sayısını kontrol et
                if self.ardisik_basarisiz_deneme >= 5:
                    self.root.after(0, lambda: self.log_ekle("❌ 5 DENEME BAŞARISIZ! Sistem durduruluyor..."))
                    self.root.after(0, lambda: messagebox.showerror(
                        "Yeniden Başlatma Başarısız",
                        f"5 deneme sonrası MEDULA yeniden başlatılamadı.\n\n"
                        f"Lütfen MEDULA'yı manuel olarak kontrol edin ve tekrar deneyin.\n\n"
                        f"Yeniden Başlatma: {self.yeniden_baslatma_sayaci}\n"
                        f"Taskkill: {self.taskkill_sayaci}"
                    ))

                    if self.session_logger:
                        self.session_logger.hata(f"3 deneme başarısız! Sistem durdu.")

                    # UI'yi resetle
                    self.root.after(0, self.reset_ui)
                    return

                # Otomatik yeniden başlatılacak
                self.is_running = False
                self.ardisik_basarisiz_deneme += 1
                self.root.after(0, lambda d=self.ardisik_basarisiz_deneme: self.log_ekle(f"⏳ 2 saniye sonra otomatik yeniden başlatılacak... (Deneme {d}/5)"))
                time.sleep(2)

                # Yeniden başlat ve sonucu kontrol et
                def yeniden_baslat_ve_kontrol():
                    basarili = self.otomatik_yeniden_baslat()
                    if not basarili:
                        # Başarısız oldu, tekrar kontrol edilecek (exception handler'a geri dönecek)
                        self.root.after(0, lambda: self.log_ekle(f"⚠ Yeniden başlatma başarısız (Deneme {self.ardisik_basarisiz_deneme}/5)"))
                        if self.ardisik_basarisiz_deneme < 5:
                            self.root.after(0, lambda: self.log_ekle("🔄 Yeniden denenecek..."))
                    # Başarılı ise `ardisik_basarisiz_deneme` zaten 0'lanmış

                recovery_thread = threading.Thread(target=yeniden_baslat_ve_kontrol)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma, aktif grup yok veya görev tamamlandı - UI'yi resetle
                self.root.after(0, self.reset_ui)

    def reset_ui(self):
        """UI'yi sıfırla"""
        self.is_running = False
        self.stop_requested = False
        self.aktif_grup = None  # Aktif grubu temizle
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modunu sıfırla
        self.ardisik_basarisiz_deneme = 0  # Ardışık deneme sayacını sıfırla

        self.start_button.config(state="normal", bg="#388E3C", fg="white")
        self.stop_button.config(state="disabled", bg="#616161")
        self.status_label.config(text="Hazır", bg="#A5D6A7", fg="#1B5E20")

        # İstatistik timer'ını durdur
        self.stats_timer_running = False

        self.log_ekle("⏹ Durduruldu")

    def start_stats_timer(self):
        """İstatistik timer'ını başlat"""
        if not self.stats_timer_running:
            self.stats_timer_running = True
            self._stats_timer_tick()

    def _stats_timer_tick(self):
        """Stats timer tick"""
        if not self.stats_timer_running:
            return

        self.update_stats_display()
        self.root.after(200, self._stats_timer_tick)  # 200ms için daha akıcı milisaniye güncellemesi

    def update_stats_display(self):
        """İstatistikleri güncelle"""
        # Toplam süre = Daha önce biriken + Şu anki çalışma süresi
        sure_toplam = self.oturum_sure_toplam
        if self.oturum_baslangic:
            sure_toplam += (time.time() - self.oturum_baslangic)

        # Saniye ve milisaniye hesapla
        sure = int(sure_toplam)
        milisaniye = int((sure_toplam * 1000) % 1000)

        # Süre formatını oluştur (milisaniye ile)
        if sure >= 60:
            dk = sure // 60
            sn = sure % 60
            sure_text = f"{dk}dk {sn}s {milisaniye}ms"
        else:
            sure_text = f"{sure}s {milisaniye}ms"

        # Son 5 reçetenin ortalama süresini hesapla
        if len(self.son_recete_sureleri) > 0:
            ortalama_sure = sum(self.son_recete_sureleri) / len(self.son_recete_sureleri)
            ort_text = f"{ortalama_sure:.1f}s"
        else:
            ort_text = "-"

        text = f"Rç:{self.oturum_recete} | Takipli:{self.oturum_takipli_recete} | İlaç:{self.oturum_takip} | R:{self.rapor_takip.toplam_kayit} | Süre:{sure_text} | Ort(5):{ort_text}"
        self.stats_label.config(text=text)

    # captcha_devam_et fonksiyonu kaldırıldı - artık gerekli değil

    def gorev_tamamlandi_raporu(self, grup, toplam_recete, toplam_takip):
        """Görev tamamlandığında rapor göster"""
        try:
            from tkinter import messagebox

            # Oturum bilgilerini al
            ortalama_sure = 0
            if self.aktif_oturum_id:
                oturum = self.database.oturum_getir(self.aktif_oturum_id)
                if oturum:
                    ortalama_sure = oturum.get("ortalama_recete_suresi", 0)

            rapor = f"""
╔════════════════════════════════════════════╗
║          🎯 GÖREV TAMAMLANDI! 🎯          ║
╚════════════════════════════════════════════╝

✓ Grup: {grup}
✓ Toplam Reçete: {toplam_recete}
✓ Toplam Takip: {toplam_takip}
✓ Ortalama Süre: {ortalama_sure:.2f} saniye
✓ Yeniden Başlatma: {self.yeniden_baslatma_sayaci} kez
✓ Taskkill: {self.taskkill_sayaci} kez

Tüm reçeteler başarıyla işlendi!
            """

            messagebox.showinfo("Görev Tamamlandı", rapor)
            self.log_ekle("🎯 Görev tamamlama raporu gösterildi")

        except Exception as e:
            logger.error(f"Rapor gösterme hatası: {e}")

    def gorev_raporlari_goster(self):
        """Görev raporları penceresini aç"""
        try:
            from tkinter import Toplevel, ttk
            from datetime import datetime
            import csv

            # Yeni pencere
            rapor_pencere = Toplevel(self.root)
            rapor_pencere.title("Görev Raporları")
            rapor_pencere.geometry("900x550")

            # Üst frame (tablo için)
            tablo_frame = tk.Frame(rapor_pencere)
            tablo_frame.pack(side="top", fill="both", expand=True)

            # Treeview (tablo)
            columns = ("ID", "Grup", "Başlangıç", "Bitiş", "Reçete", "Takip", "Y.Başlatma", "Taskkill", "Ort.Süre", "Durum")
            tree = ttk.Treeview(tablo_frame, columns=columns, show="headings", height=20)

            # Başlıklar
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=90, anchor="center")

            # Scrollbar
            scrollbar = ttk.Scrollbar(tablo_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            # Verileri yükle
            oturumlar = self.database.tum_oturumlari_getir(limit=100)
            for oturum in oturumlar:
                tree.insert("", "end", values=(
                    oturum['id'],
                    oturum['grup'],
                    oturum['baslangic_zamani'],
                    oturum['bitis_zamani'] or "-",
                    oturum['toplam_recete'],
                    oturum['toplam_takip'],
                    oturum['yeniden_baslatma_sayisi'],
                    oturum['taskkill_sayisi'],
                    f"{oturum['ortalama_recete_suresi']:.2f}s",
                    oturum['durum']
                ))

            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Alt frame (export butonu için)
            alt_frame = tk.Frame(rapor_pencere)
            alt_frame.pack(side="bottom", fill="x", padx=10, pady=10)

            # Export butonu
            def export_raporlar():
                """Raporları CSV olarak export et"""
                try:
                    if not oturumlar:
                        messagebox.showinfo("Bilgi", "Export edilecek rapor yok")
                        return

                    # Varsayılan dosya adı
                    simdi = datetime.now()
                    varsayilan_dosya_adi = f"Gorev_Raporlari_{simdi.strftime('%Y%m%d_%H%M%S')}.csv"

                    # Kullanıcıdan dosya adı ve kayıt yeri seç
                    dosya_yolu = filedialog.asksaveasfilename(
                        title="Görev Raporlarını Kaydet",
                        initialfile=varsayilan_dosya_adi,
                        defaultextension=".csv",
                        filetypes=[("CSV Dosyaları", "*.csv"), ("Tüm Dosyalar", "*.*")]
                    )

                    if not dosya_yolu:
                        return

                    # CSV'ye yaz
                    with open(dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                        fieldnames = ['ID', 'Grup', 'Başlangıç', 'Bitiş', 'Reçete', 'Takip', 'Y.Başlatma', 'Taskkill', 'Ort.Süre', 'Durum']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()

                        for oturum in oturumlar:
                            writer.writerow({
                                'ID': oturum['id'],
                                'Grup': oturum['grup'],
                                'Başlangıç': oturum['baslangic_zamani'],
                                'Bitiş': oturum['bitis_zamani'] or "-",
                                'Reçete': oturum['toplam_recete'],
                                'Takip': oturum['toplam_takip'],
                                'Y.Başlatma': oturum['yeniden_baslatma_sayisi'],
                                'Taskkill': oturum['taskkill_sayisi'],
                                'Ort.Süre': f"{oturum['ortalama_recete_suresi']:.2f}s",
                                'Durum': oturum['durum']
                            })

                    dosya_adi = Path(dosya_yolu).name
                    messagebox.showinfo("Başarılı", f"{len(oturumlar)} rapor '{dosya_adi}' olarak kaydedildi")
                    self.log_ekle(f"✓ {len(oturumlar)} görev raporu '{dosya_adi}' olarak export edildi")

                except Exception as e:
                    messagebox.showerror("Hata", f"Export hatası: {e}")
                    logger.error(f"Rapor export hatası: {e}")

            export_btn = tk.Button(
                alt_frame,
                text="📥 CSV Olarak Kaydet",
                font=("Arial", 10, "bold"),
                bg="#4CAF50",
                fg="white",
                command=export_raporlar
            )
            export_btn.pack(side="left", padx=5)

            self.log_ekle("📊 Görev raporları açıldı")
        except Exception as e:
            logger.error(f"Görev raporları hatası: {e}", exc_info=True)
            self.log_ekle(f"❌ Raporlar açılamadı: {e}")

    def on_closing(self):
        """Pencere kapatma"""
        if self.is_running:
            self.durdur()
            if self.automation_thread and self.automation_thread.is_alive():
                self.automation_thread.join(timeout=2)

        # Aktif oturumu bitir
        if self.aktif_oturum_id:
            son_recete = self.grup_durumu.son_recete_al(self.aktif_grup) if self.aktif_grup else None
            self.database.oturum_bitir(self.aktif_oturum_id, son_recete)

            if self.session_logger:
                self.session_logger.ozet_yaz(
                    self.oturum_recete,
                    self.oturum_takip,
                    sum(self.son_recete_sureleri) / len(self.son_recete_sureleri) if self.son_recete_sureleri else 0,
                    self.yeniden_baslatma_sayaci,
                    self.taskkill_sayaci
                )
                self.session_logger.kapat()

        # Database bağlantısını kapat
        try:
            if self.database:
                self.database.kapat()
        except Exception as e:
            logger.error(f"Database kapatma hatası: {e}")

        self.stats_timer_running = False
        self.root.destroy()

    # ==================== DEPO EKSTRE KARŞILAŞTIRMA SEKMESİ ====================

    def create_ekstre_tab(self, parent):
        """Depo Ekstre Karşılaştırma sekmesi - dosya seçim arayüzü"""
        main_frame = tk.Frame(parent, bg='#E3F2FD', padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Başlık
        title = tk.Label(
            main_frame,
            text="📊 Depo Ekstre Karşılaştırma",
            font=("Arial", 14, "bold"),
            bg='#E3F2FD',
            fg='#1565C0'
        )
        title.pack(pady=(5, 2))

        subtitle = tk.Label(
            main_frame,
            text="Depo ekstresi ile Eczane otomasyonunu karşılaştırın",
            font=("Arial", 9),
            bg='#E3F2FD',
            fg='#1976D2'
        )
        subtitle.pack(pady=(0, 15))

        # Dosya seçim alanları - yan yana
        files_frame = tk.Frame(main_frame, bg='#E3F2FD')
        files_frame.pack(fill="x", pady=5)
        files_frame.columnconfigure(0, weight=1)
        files_frame.columnconfigure(1, weight=1)

        # Dosya 1 - DEPO EKSTRESİ (Sol)
        self.ekstre_dosya1_path = tk.StringVar(value="")
        file1_frame = tk.LabelFrame(
            files_frame,
            text="📁 DEPO EKSTRESİ",
            font=("Arial", 10, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        file1_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)

        self.drop_area1 = tk.Label(
            file1_frame,
            text="📥 Depo Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=4,
            cursor="hand2"
        )
        self.drop_area1.pack(fill="x", pady=5)
        self.drop_area1.bind("<Button-1>", lambda e: self.ekstre_dosya_sec(1))

        self.file1_label = tk.Label(
            file1_frame,
            textvariable=self.ekstre_dosya1_path,
            font=("Arial", 8),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=250
        )
        self.file1_label.pack(fill="x")

        # Dosya 2 - ECZANE OTOMASYONU (Sağ)
        self.ekstre_dosya2_path = tk.StringVar(value="")
        file2_frame = tk.LabelFrame(
            files_frame,
            text="📁 ECZANE OTOMASYONU",
            font=("Arial", 10, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        file2_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)

        self.drop_area2 = tk.Label(
            file2_frame,
            text="📥 Eczane Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=4,
            cursor="hand2"
        )
        self.drop_area2.pack(fill="x", pady=5)
        self.drop_area2.bind("<Button-1>", lambda e: self.ekstre_dosya_sec(2))

        self.file2_label = tk.Label(
            file2_frame,
            textvariable=self.ekstre_dosya2_path,
            font=("Arial", 8),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=250
        )
        self.file2_label.pack(fill="x")

        # Filtre ayarlarını yükle
        self.ekstre_filtreler = self._ekstre_filtre_yukle()

        # Butonlar ana frame
        button_main_frame = tk.Frame(main_frame, bg='#E3F2FD')
        button_main_frame.pack(fill="x", pady=15)

        # Butonları ortalamak için iç frame
        button_center_frame = tk.Frame(button_main_frame, bg='#E3F2FD')
        button_center_frame.pack(expand=True)

        # Karşılaştır butonu (büyük, ortada)
        self.karsilastir_btn = tk.Button(
            button_center_frame,
            text="🔍 KARŞILAŞTIR",
            font=("Arial", 14, "bold"),
            bg='#1976D2',
            fg='white',
            width=20,
            height=2,
            cursor="hand2",
            activebackground='#1565C0',
            activeforeground='white',
            relief="raised",
            bd=3,
            command=self.ekstre_karsilastir_pencere_ac
        )
        self.karsilastir_btn.pack(side="left", padx=10)

        # Ayarlar butonu (yanında, küçük)
        self.ekstre_ayarlar_btn = tk.Button(
            button_center_frame,
            text="⚙️ Filtre\nAyarları",
            font=("Arial", 10, "bold"),
            bg='#FF9800',
            fg='white',
            width=10,
            height=2,
            cursor="hand2",
            activebackground='#F57C00',
            activeforeground='white',
            relief="raised",
            bd=2,
            command=self.ekstre_filtre_ayarlari_ac
        )
        self.ekstre_ayarlar_btn.pack(side="left", padx=10)

        # Aktif filtre bilgisi göster
        self._ekstre_filtre_bilgi_label = tk.Label(
            button_main_frame,
            text="",
            font=("Arial", 9),
            bg='#E3F2FD',
            fg='#E65100'
        )
        self._ekstre_filtre_bilgi_label.pack(pady=(5, 0))
        self._ekstre_filtre_bilgi_guncelle()

        # Renk açıklamaları
        legend_frame = tk.LabelFrame(
            main_frame,
            text="🎨 Renk Kodları",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#1565C0',
            padx=10,
            pady=5
        )
        legend_frame.pack(fill="x", pady=10)

        legends = [
            ("🟢 YEŞİL", "Fatura No + Tutar eşleşiyor", "#C8E6C9"),
            ("🟡 SARI", "Tutar eşleşiyor, Fatura No eşleşmiyor", "#FFF9C4"),
            ("🟠 TURUNCU", "Fatura No eşleşiyor, Tutar eşleşmiyor", "#FFE0B2"),
            ("🔴 KIRMIZI", "İkisi de eşleşmiyor", "#FFCDD2"),
        ]

        for text, desc, color in legends:
            row = tk.Frame(legend_frame, bg='#E3F2FD')
            row.pack(fill="x", pady=2)
            tk.Label(row, text=text, font=("Arial", 9, "bold"), bg=color, width=12).pack(side="left", padx=5)
            tk.Label(row, text=desc, font=("Arial", 8), bg='#E3F2FD', fg='#333').pack(side="left", padx=5)

        # Sürükle-bırak desteği - ana pencereye bağla
        self.root.after(100, self._setup_drag_drop)

    def _ekstre_filtre_bilgi_guncelle(self):
        """Aktif filtre sayısını göster"""
        if not hasattr(self, '_ekstre_filtre_bilgi_label'):
            return
        depo_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('depo', {}).values())
        eczane_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('eczane', {}).values())

        if depo_sayisi > 0 or eczane_sayisi > 0:
            text = f"⚠️ Aktif filtre: Depo({depo_sayisi}) | Eczane({eczane_sayisi})"
            self._ekstre_filtre_bilgi_label.config(text=text, fg='#E65100')
        else:
            self._ekstre_filtre_bilgi_label.config(text="✓ Filtre yok - tüm satırlar dahil", fg='#388E3C')

    def _ekstre_filtre_yukle(self):
        """Kaydedilmiş filtre ayarlarını yükle"""
        import json
        import os
        filtre_dosya = os.path.join(os.path.dirname(__file__), 'ekstre_filtre_ayarlari.json')
        varsayilan = {
            'depo': {},      # {'sutun_adi': ['deger1', 'deger2']}
            'eczane': {},
            'hatirla': True
        }
        try:
            if os.path.exists(filtre_dosya):
                with open(filtre_dosya, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Filtre ayarları yüklenemedi: {e}")
        return varsayilan

    def _ekstre_filtre_kaydet(self):
        """Filtre ayarlarını kaydet"""
        import json
        import os
        filtre_dosya = os.path.join(os.path.dirname(__file__), 'ekstre_filtre_ayarlari.json')
        try:
            with open(filtre_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.ekstre_filtreler, f, ensure_ascii=False, indent=2)
            logger.info("Filtre ayarları kaydedildi")
        except Exception as e:
            logger.error(f"Filtre ayarları kaydedilemedi: {e}")

    def ekstre_filtre_ayarlari_ac(self):
        """Filtre ayarları penceresini aç"""
        import pandas as pd

        # Dosyaları kontrol et
        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()

        if not dosya1 and not dosya2:
            messagebox.showinfo("Bilgi", "Önce en az bir Excel dosyası yükleyin.\nBöylece sütunları ve değerleri görebilirsiniz.")
            return

        # Ayarlar penceresi
        ayar_pencere = tk.Toplevel(self.root)
        ayar_pencere.title("⚙️ Ekstre Filtre Ayarları")
        ayar_pencere.geometry("800x600")
        ayar_pencere.configure(bg='#ECEFF1')
        ayar_pencere.transient(self.root)
        ayar_pencere.grab_set()

        # Pencereyi ortala
        ayar_pencere.update_idletasks()
        x = (ayar_pencere.winfo_screenwidth() - 800) // 2
        y = (ayar_pencere.winfo_screenheight() - 600) // 2
        ayar_pencere.geometry(f"800x600+{x}+{y}")

        # Ana frame
        main_frame = tk.Frame(ayar_pencere, bg='#ECEFF1')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Başlık
        tk.Label(
            main_frame,
            text="⚙️ Satır Filtreleme Ayarları",
            font=("Arial", 14, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack(pady=(0, 5))

        tk.Label(
            main_frame,
            text="İşaretlenen değerlere sahip satırlar karşılaştırmada dikkate alınmayacak",
            font=("Arial", 9),
            bg='#ECEFF1',
            fg='#666'
        ).pack(pady=(0, 10))

        # Notebook (sekmeli panel)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=5)

        # Checkbox değişkenleri saklamak için
        self._filtre_checkboxes = {'depo': {}, 'eczane': {}}

        # DEPO sekmesi
        if dosya1:
            depo_frame = tk.Frame(notebook, bg='#E3F2FD')
            notebook.add(depo_frame, text="📦 DEPO EKSTRESİ")
            self._filtre_sekme_olustur(depo_frame, dosya1, 'depo')

        # ECZANE sekmesi
        if dosya2:
            eczane_frame = tk.Frame(notebook, bg='#E8F5E9')
            notebook.add(eczane_frame, text="🏪 ECZANE OTOMASYONU")
            self._filtre_sekme_olustur(eczane_frame, dosya2, 'eczane')

        # Alt butonlar
        btn_frame = tk.Frame(main_frame, bg='#ECEFF1')
        btn_frame.pack(fill="x", pady=10)

        # Hatırla checkbox
        self._hatirla_var = tk.BooleanVar(value=self.ekstre_filtreler.get('hatirla', True))
        tk.Checkbutton(
            btn_frame,
            text="Ayarları hatırla",
            variable=self._hatirla_var,
            bg='#ECEFF1',
            font=("Arial", 10)
        ).pack(side="left", padx=10)

        # Kaydet butonu
        tk.Button(
            btn_frame,
            text="💾 Kaydet ve Kapat",
            font=("Arial", 11, "bold"),
            bg='#4CAF50',
            fg='white',
            width=18,
            cursor="hand2",
            command=lambda: self._filtre_kaydet_ve_kapat(ayar_pencere)
        ).pack(side="right", padx=5)

        # İptal butonu
        tk.Button(
            btn_frame,
            text="❌ İptal",
            font=("Arial", 10),
            bg='#f44336',
            fg='white',
            width=10,
            cursor="hand2",
            command=ayar_pencere.destroy
        ).pack(side="right", padx=5)

        # Tümünü Temizle butonu
        tk.Button(
            btn_frame,
            text="🗑️ Tümünü Temizle",
            font=("Arial", 10),
            bg='#FF9800',
            fg='white',
            width=14,
            cursor="hand2",
            command=self._filtre_tumunu_temizle
        ).pack(side="right", padx=5)

    def _filtre_sekme_olustur(self, parent, dosya_yolu, kaynak):
        """Bir Excel dosyası için filtre sekmesi oluştur"""
        import pandas as pd

        try:
            df = pd.read_excel(dosya_yolu)
        except Exception as e:
            tk.Label(parent, text=f"Dosya okunamadı: {e}", bg='#FFCDD2').pack(pady=20)
            return

        # Canvas ve scrollbar
        canvas = tk.Canvas(parent, bg=parent.cget('bg'), highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=parent.cget('bg'))

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Her sütun için
        mevcut_filtreler = self.ekstre_filtreler.get(kaynak, {})

        for col in df.columns:
            # Benzersiz değerleri al (NaN hariç)
            benzersiz = df[col].dropna().astype(str).unique()
            benzersiz = sorted([v for v in benzersiz if v and v != 'nan'])

            if len(benzersiz) == 0 or len(benzersiz) > 50:  # Çok fazla değer varsa atla
                continue

            # Sütun frame
            col_frame = tk.LabelFrame(
                scroll_frame,
                text=f"📋 {col} ({len(benzersiz)} değer)",
                font=("Arial", 10, "bold"),
                bg=parent.cget('bg'),
                padx=5,
                pady=5
            )
            col_frame.pack(fill="x", padx=5, pady=5)

            # Checkbox'ları oluştur
            self._filtre_checkboxes[kaynak][col] = {}
            secili_degerler = mevcut_filtreler.get(col, [])

            # Her satırda 4 değer göster
            row_frame = None
            for i, deger in enumerate(benzersiz):
                if i % 4 == 0:
                    row_frame = tk.Frame(col_frame, bg=parent.cget('bg'))
                    row_frame.pack(fill="x", pady=1)

                var = tk.BooleanVar(value=(deger in secili_degerler))
                self._filtre_checkboxes[kaynak][col][deger] = var

                cb = tk.Checkbutton(
                    row_frame,
                    text=deger[:25] + "..." if len(deger) > 25 else deger,
                    variable=var,
                    bg=parent.cget('bg'),
                    font=("Arial", 9),
                    anchor="w",
                    width=20
                )
                cb.pack(side="left", padx=2)

    def _filtre_kaydet_ve_kapat(self, pencere):
        """Filtre ayarlarını kaydet ve pencereyi kapat"""
        # Checkbox değerlerini topla
        for kaynak in ['depo', 'eczane']:
            self.ekstre_filtreler[kaynak] = {}
            if kaynak in self._filtre_checkboxes:
                for col, degerler in self._filtre_checkboxes[kaynak].items():
                    secili = [d for d, var in degerler.items() if var.get()]
                    if secili:
                        self.ekstre_filtreler[kaynak][col] = secili

        self.ekstre_filtreler['hatirla'] = self._hatirla_var.get()

        # Kaydet
        if self._hatirla_var.get():
            self._ekstre_filtre_kaydet()

        # Özet göster
        depo_filtre_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('depo', {}).values())
        eczane_filtre_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('eczane', {}).values())

        if depo_filtre_sayisi > 0 or eczane_filtre_sayisi > 0:
            messagebox.showinfo(
                "Filtreler Kaydedildi",
                f"Depo: {depo_filtre_sayisi} değer filtrelenecek\n"
                f"Eczane: {eczane_filtre_sayisi} değer filtrelenecek"
            )

        # Ana penceredeki filtre bilgisini güncelle
        self._ekstre_filtre_bilgi_guncelle()

        pencere.destroy()

    def _filtre_tumunu_temizle(self):
        """Tüm filtreleri temizle"""
        for kaynak in ['depo', 'eczane']:
            if kaynak in self._filtre_checkboxes:
                for col, degerler in self._filtre_checkboxes[kaynak].items():
                    for var in degerler.values():
                        var.set(False)

    def _setup_drag_drop(self):
        """Sürükle-bırak desteğini ayarla - ana pencereye hook"""
        try:
            import windnd

            def handle_drop(files):
                """Ana pencereye bırakılan dosyaları işle"""
                if not files:
                    return
                try:
                    # Türkçe karakterler için farklı encoding'ler dene
                    raw = files[0]
                    if isinstance(raw, bytes):
                        # Önce cp1254 (Türkçe Windows), sonra diğerleri
                        for encoding in ['cp1254', 'utf-8', 'latin-1', 'cp1252']:
                            try:
                                file_path = raw.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            file_path = raw.decode('utf-8', errors='replace')
                    else:
                        file_path = raw
                    logger.info(f"Dosya bırakıldı: {file_path}")

                    if not file_path.lower().endswith(('.xlsx', '.xls')):
                        messagebox.showwarning("Uyarı", "Lütfen Excel dosyası (.xlsx, .xls) seçin!")
                        return

                    # Hangi alana yüklenecek? Boş olana veya ilkine
                    if not self.ekstre_dosya1_path.get():
                        self.ekstre_dosya1_path.set(file_path)
                        self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                        logger.info("Dosya Depo alanına yüklendi")
                    elif not self.ekstre_dosya2_path.get():
                        self.ekstre_dosya2_path.set(file_path)
                        self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                        logger.info("Dosya Eczane alanına yüklendi")
                    else:
                        # İkisi de dolu, kullanıcıya sor
                        secim = messagebox.askyesnocancel(
                            "Dosya Seçimi",
                            f"Hangi alana yüklensin?\n\nEvet = Depo Exceli\nHayır = Eczane Exceli\nİptal = Vazgeç"
                        )
                        if secim is True:
                            self.ekstre_dosya1_path.set(file_path)
                            self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                        elif secim is False:
                            self.ekstre_dosya2_path.set(file_path)
                            self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Drop hatası: {e}")

            # Ana pencereye (root) hook - tüm pencere alanında çalışır
            windnd.hook_dropfiles(self.root, func=handle_drop)
            logger.info("Sürükle-bırak desteği aktif (windnd - root window)")
        except ImportError:
            logger.info("windnd bulunamadı - sürükle-bırak için tıklama kullanılacak")
        except Exception as e:
            logger.error(f"Sürükle-bırak kurulumu hatası: {e}")

    def ekstre_dosya_sec(self, dosya_no):
        """Dosya seçme dialogu aç"""
        dosya_yolu = filedialog.askopenfilename(
            title=f"{'Depo Ekstresi' if dosya_no == 1 else 'Eczane Otomasyonu'} Seçin",
            filetypes=[
                ("Excel Dosyaları", "*.xlsx *.xls"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        if dosya_yolu:
            if dosya_no == 1:
                self.ekstre_dosya1_path.set(dosya_yolu)
                self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
            else:
                self.ekstre_dosya2_path.set(dosya_yolu)
                self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')

    def ekstre_karsilastir_pencere_ac(self):
        """Büyük karşılaştırma penceresini aç"""
        import pandas as pd

        dosya1 = self.ekstre_dosya1_path.get()  # Depo
        dosya2 = self.ekstre_dosya2_path.get()  # Eczane

        if not dosya1 or not dosya2:
            messagebox.showwarning("Uyarı", "Lütfen her iki Excel dosyasını da seçin!")
            return

        try:
            # Excel dosyalarını oku
            df_depo = pd.read_excel(dosya1)
            df_eczane = pd.read_excel(dosya2)

            # Büyük pencere aç
            self._ekstre_sonuc_penceresi_olustur(df_depo, df_eczane, dosya1, dosya2)

        except PermissionError as e:
            dosya_adi = dosya1 if 'DEPO' in str(e).upper() else dosya2
            dosya_adi = dosya_adi.split('\\')[-1] if '\\' in dosya_adi else dosya_adi.split('/')[-1]
            messagebox.showerror(
                "Dosya Erişim Hatası",
                f"❌ Dosya okunamıyor: {dosya_adi}\n\n"
                f"Muhtemel sebepler:\n"
                f"• Dosya şu anda Excel'de açık durumda\n"
                f"• Dosya başka bir program tarafından kullanılıyor\n"
                f"• Dosya salt okunur (read-only) olabilir\n\n"
                f"✅ Çözüm:\n"
                f"• Excel dosyasını kapatın\n"
                f"• Dosyanın başka bir programda açık olmadığından emin olun\n"
                f"• Tekrar deneyin"
            )
            logger.error(f"Ekstre dosya erişim hatası: {e}")
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya okuma hatası: {str(e)}")
            logger.error(f"Ekstre dosya okuma hatası: {e}")

    def _ekstre_sonuc_penceresi_olustur(self, df_depo, df_eczane, dosya1_yol, dosya2_yol):
        """Büyük karşılaştırma sonuç penceresi"""
        import pandas as pd

        # Yeni pencere oluştur - Optimize edilmiş boyut
        pencere = tk.Toplevel(self.root)
        pencere.title("📊 Depo Ekstre Karşılaştırma Sonuçları")
        pencere.configure(bg='#ECEFF1')

        # Optimal boyut ayarla (bilgileri sığdıracak kadar büyük ama gereksiz değil)
        window_width = 1000
        window_height = 800

        # Ekran merkezine konumlandır
        screen_width = pencere.winfo_screenwidth()
        screen_height = pencere.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        pencere.geometry(f"{window_width}x{window_height}+{x}+{y}")
        pencere.minsize(950, 700)  # Minimum boyut belirle

        # Sütun eşleştirmeleri
        # Depo: Evrak No, Borc, Alacak
        # Eczane: Fatura No, Fatura Tutarı, İade/Çık Tut

        # Sütunları bul - genişletilmiş arama listeleri
        depo_fatura_col = self._bul_sutun(df_depo, [
            'Evrak No', 'EvrakNo', 'EVRAK NO', 'Fatura No', 'FaturaNo', 'FATURA NO',
            'Belge No', 'BelgeNo', 'BELGE NO', 'Fiş No', 'FişNo', 'FİŞ NO'
        ])
        depo_borc_col = self._bul_sutun(df_depo, [
            'Borc', 'Borç', 'BORC', 'BORÇ', 'Tutar', 'TUTAR',
            'Borç Tutar', 'BorçTutar', 'BORÇ TUTAR', 'Toplam', 'TOPLAM',
            'Fatura Tutarı', 'FaturaTutarı', 'FATURA TUTARI', 'Net Tutar', 'NET TUTAR'
        ])
        depo_alacak_col = self._bul_sutun(df_depo, [
            'Alacak', 'ALACAK', 'Alacak Tutar', 'AlacakTutar', 'ALACAK TUTAR',
            'İade', 'IADE', 'İade Tutar', 'İadeTutar', 'İADE TUTAR'
        ])

        eczane_fatura_col = self._bul_sutun(df_eczane, [
            'Fatura No', 'FaturaNo', 'FATURA NO', 'Evrak No', 'EvrakNo', 'EVRAK NO',
            'Belge No', 'BelgeNo', 'BELGE NO', 'Fiş No', 'FişNo', 'FİŞ NO'
        ])
        eczane_borc_col = self._bul_sutun(df_eczane, [
            'Fatura Tutarı', 'FaturaTutarı', 'FATURA TUTARI', 'Fatura Tutar',
            'Tutar', 'TUTAR', 'Borç', 'Borc', 'BORÇ', 'BORC',
            'Toplam', 'TOPLAM', 'Net Tutar', 'NET TUTAR', 'Toplam Tutar', 'TOPLAM TUTAR'
        ])
        eczane_alacak_col = self._bul_sutun(df_eczane, [
            'İade/Çık Tut', 'Iade/Cik Tut', 'İade Tutarı', 'İade/Çıkış Tut',
            'İade', 'IADE', 'İade Tutar', 'İadeTutar', 'İADE TUTAR', 'Alacak', 'ALACAK'
        ])

        # Fatura tarihi sütunları
        depo_tarih_col = self._bul_sutun(df_depo, [
            'Tarih', 'TARİH', 'Fatura Tarihi', 'FaturaTarihi', 'FATURA TARİHİ',
            'Evrak Tarihi', 'EvrakTarihi', 'EVRAK TARİHİ', 'İşlem Tarihi', 'İşlemTarihi'
        ])
        eczane_tarih_col = self._bul_sutun(df_eczane, [
            'Tarih', 'TARİH', 'Fatura Tarihi', 'FaturaTarihi', 'FATURA TARİHİ',
            'Evrak Tarihi', 'EvrakTarihi', 'EVRAK TARİHİ', 'İşlem Tarihi', 'İşlemTarihi'
        ])

        # Tip/Tür sütunları
        depo_tip_col = self._bul_sutun(df_depo, [
            'Tip', 'TİP', 'Tür', 'TÜR', 'İşlem Tipi', 'İşlemTipi', 'İŞLEM TİPİ',
            'Fiş Tipi', 'FişTipi', 'FİŞ TİPİ', 'Evrak Tipi', 'EvrakTipi'
        ])
        eczane_tip_col = self._bul_sutun(df_eczane, [
            'Tip', 'TİP', 'Tür', 'TÜR', 'İşlem Tipi', 'İşlemTipi', 'İŞLEM TİPİ',
            'Fiş Tipi', 'FişTipi', 'FİŞ TİPİ', 'Evrak Tipi', 'EvrakTipi'
        ])

        # Debug: Sütun bilgilerini logla ve kullanıcıya göster
        logger.info(f"DEPO Sütunları: {list(df_depo.columns)}")
        logger.info(f"DEPO - Fatura: {depo_fatura_col}, Borç: {depo_borc_col}, Alacak: {depo_alacak_col}")
        logger.info(f"ECZANE Sütunları: {list(df_eczane.columns)}")
        logger.info(f"ECZANE - Fatura: {eczane_fatura_col}, Borç: {eczane_borc_col}, Alacak: {eczane_alacak_col}")

        # Sütun eşleşme bilgisini göster
        print("=" * 60)
        print("DEPO SÜTUNLARI:", list(df_depo.columns))
        print(f"  Fatura No -> {depo_fatura_col}")
        print(f"  Borç/Tutar -> {depo_borc_col}")
        print(f"  Alacak -> {depo_alacak_col}")
        print("-" * 60)
        print("ECZANE SÜTUNLARI:", list(df_eczane.columns))
        print(f"  Fatura No -> {eczane_fatura_col}")
        print(f"  Borç/Tutar -> {eczane_borc_col}")
        print(f"  Alacak -> {eczane_alacak_col}")
        print("=" * 60)

        # Sütun bulunamadıysa kullanıcıya göster
        hatalar = []
        if not depo_fatura_col:
            hatalar.append(f"DEPO'da Fatura No sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_depo.columns)}")
        if not depo_borc_col:
            hatalar.append(f"DEPO'da Borç/Tutar sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_depo.columns)}")
        if not eczane_fatura_col:
            hatalar.append(f"ECZANE'de Fatura No sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_eczane.columns)}")
        if not eczane_borc_col:
            hatalar.append(f"ECZANE'de Fatura Tutarı sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_eczane.columns)}")

        if hatalar:
            messagebox.showerror("Sütun Bulunamadı", "\n\n".join(hatalar))
            if not depo_fatura_col or not eczane_fatura_col:
                pencere.destroy()
                return

        # Filtre fonksiyonu
        def satir_filtreli_mi(row, kaynak):
            """Satırın filtrelenip filtrelenmeyeceğini kontrol et"""
            filtreler = self.ekstre_filtreler.get(kaynak, {})
            for col, degerler in filtreler.items():
                if col in row.index:
                    satir_degeri = str(row[col]).strip() if pd.notna(row[col]) else ""
                    if satir_degeri in degerler:
                        return True  # Bu satır filtrelenmeli
            return False

        # Filtrelenen satır sayısını say ve sakla
        depo_filtreli = 0
        eczane_filtreli = 0
        filtrelenen_depo_satirlar = []
        filtrelenen_eczane_satirlar = []

        # Verileri hazırla
        depo_data = {}
        for _, row in df_depo.iterrows():
            # Filtre kontrolü
            if satir_filtreli_mi(row, 'depo'):
                depo_filtreli += 1
                # Filtrelenen satırı sakla
                fatura = str(row[depo_fatura_col]).strip() if pd.notna(row[depo_fatura_col]) else ""
                borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
                alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
                tarih = str(row[depo_tarih_col]).strip() if depo_tarih_col and pd.notna(row[depo_tarih_col]) else ""
                tip = str(row[depo_tip_col]).strip() if depo_tip_col and pd.notna(row[depo_tip_col]) else ""
                filtrelenen_depo_satirlar.append((fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip}))
                continue  # Bu satırı atla

            fatura = str(row[depo_fatura_col]).strip() if pd.notna(row[depo_fatura_col]) else ""
            if fatura and fatura != 'nan':
                borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
                alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
                tarih = str(row[depo_tarih_col]).strip() if depo_tarih_col and pd.notna(row[depo_tarih_col]) else ""
                tip = str(row[depo_tip_col]).strip() if depo_tip_col and pd.notna(row[depo_tip_col]) else ""
                depo_data[fatura] = {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row}

        eczane_data = {}
        for _, row in df_eczane.iterrows():
            # Filtre kontrolü
            if satir_filtreli_mi(row, 'eczane'):
                eczane_filtreli += 1
                # Filtrelenen satırı sakla
                fatura = str(row[eczane_fatura_col]).strip() if pd.notna(row[eczane_fatura_col]) else ""
                borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
                alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
                tarih = str(row[eczane_tarih_col]).strip() if eczane_tarih_col and pd.notna(row[eczane_tarih_col]) else ""
                tip = str(row[eczane_tip_col]).strip() if eczane_tip_col and pd.notna(row[eczane_tip_col]) else ""
                filtrelenen_eczane_satirlar.append((fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip}))
                continue  # Bu satırı atla

            fatura = str(row[eczane_fatura_col]).strip() if pd.notna(row[eczane_fatura_col]) else ""
            if fatura and fatura != 'nan':
                borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
                alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
                tarih = str(row[eczane_tarih_col]).strip() if eczane_tarih_col and pd.notna(row[eczane_tarih_col]) else ""
                tip = str(row[eczane_tip_col]).strip() if eczane_tip_col and pd.notna(row[eczane_tip_col]) else ""
                eczane_data[fatura] = {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row}

        # Filtre bilgisini logla
        if depo_filtreli > 0 or eczane_filtreli > 0:
            logger.info(f"Filtre uygulandı - Depo: {depo_filtreli} satır, Eczane: {eczane_filtreli} satır atlandı")

        # Karşılaştırma yap
        tum_faturalar = set(depo_data.keys()) | set(eczane_data.keys())

        # Renk kodlaması:
        # YEŞİL: Fatura No + Tutar eşleşiyor
        # SARI: Tutar eşleşiyor, Fatura No eşleşmiyor
        # TURUNCU: Fatura No eşleşiyor, Tutar eşleşmiyor
        # KIRMIZI: İkisi de eşleşmiyor

        yesil_satirlar = []     # Fatura No + Tutar eşleşiyor
        sari_satirlar = []      # Tutar eşleşiyor, Fatura No eşleşmiyor
        turuncu_satirlar = []   # Fatura No eşleşiyor, Tutar eşleşmiyor
        kirmizi_depo = []       # Depo'da var, hiçbir eşleşme yok
        kirmizi_eczane = []     # Eczane'de var, hiçbir eşleşme yok

        # Önce fatura numarası bazlı eşleştirme
        eslesen_faturalar = set()
        for fatura in tum_faturalar:
            depo_kayit = depo_data.get(fatura)
            eczane_kayit = eczane_data.get(fatura)

            if depo_kayit and eczane_kayit:
                # Fatura numarası eşleşiyor - tutarları karşılaştır
                eslesen_faturalar.add(fatura)

                # İşlem tipini belirle (BORÇ mu ALACAK mı)
                depo_is_borc = abs(depo_kayit['borc']) > 0.01
                eczane_is_borc = abs(eczane_kayit['borc']) > 0.01

                # İşlem tipleri aynı olmalı (borç-borç veya alacak-alacak)
                if depo_is_borc == eczane_is_borc:
                    # Tutar hesapla
                    depo_tutar = depo_kayit['borc'] if depo_is_borc else abs(depo_kayit['alacak'])
                    eczane_tutar = eczane_kayit['borc'] if eczane_is_borc else abs(eczane_kayit['alacak'])
                    tutar_esit = abs(depo_tutar - eczane_tutar) < 0.01

                    if tutar_esit:
                        # YEŞİL: Fatura No + Tutar eşleşiyor (aynı işlem tipi)
                        yesil_satirlar.append((fatura, depo_kayit, eczane_kayit))
                    else:
                        # TURUNCU: Fatura No eşleşiyor, Tutar eşleşmiyor (aynı işlem tipi)
                        turuncu_satirlar.append((fatura, depo_kayit, eczane_kayit))
                else:
                    # TURUNCU: Fatura No eşleşiyor, ama farklı işlem tipi (borç/alacak)
                    turuncu_satirlar.append((fatura, depo_kayit, eczane_kayit))

        # Eşleşmeyen kayıtlar için tutar bazlı eşleştirme dene
        eslesmeyen_depo = {f: d for f, d in depo_data.items() if f not in eslesen_faturalar}
        eslesmeyen_eczane = {f: d for f, d in eczane_data.items() if f not in eslesen_faturalar}

        # Tutar bazlı eşleştirme
        tutar_eslesen_depo = set()
        tutar_eslesen_eczane = set()

        # Tarih parse fonksiyonu
        def parse_tarih(tarih_str):
            """Tarih string'ini parse et, hata varsa çok eski bir tarih döndür"""
            if not tarih_str or tarih_str == '' or tarih_str == 'nan':
                return pd.Timestamp('1900-01-01')
            try:
                return pd.to_datetime(tarih_str)
            except Exception as e:
                return pd.Timestamp('1900-01-01')

        for depo_fatura, depo_kayit in eslesmeyen_depo.items():
            if depo_fatura in tutar_eslesen_depo:
                continue  # Bu depo kaydı zaten eşleşti

            # İşlem tipini belirle
            depo_is_borc = abs(depo_kayit['borc']) > 0.01
            depo_tutar = depo_kayit['borc'] if depo_is_borc else abs(depo_kayit['alacak'])
            depo_tarih = parse_tarih(depo_kayit.get('tarih', ''))

            # Bu depo kaydı için tüm uygun eczane adaylarını bul
            adaylar = []
            for eczane_fatura, eczane_kayit in eslesmeyen_eczane.items():
                if eczane_fatura in tutar_eslesen_eczane:
                    continue  # Bu eczane kaydı zaten eşleşti

                # İşlem tiplerini belirle
                eczane_is_borc = abs(eczane_kayit['borc']) > 0.01

                # Sadece aynı işlem tipinde eşleştir (borç-borç veya alacak-alacak)
                if depo_is_borc == eczane_is_borc:
                    # Tutar hesapla
                    eczane_tutar = eczane_kayit['borc'] if eczane_is_borc else abs(eczane_kayit['alacak'])

                    # Tutarlar eşleşiyor mu?
                    if abs(depo_tutar - eczane_tutar) < 0.01 and depo_tutar > 0:
                        # Aday olarak ekle (tarih farkını hesapla)
                        eczane_tarih = parse_tarih(eczane_kayit.get('tarih', ''))
                        tarih_fark = abs((depo_tarih - eczane_tarih).days)
                        adaylar.append((tarih_fark, eczane_fatura, eczane_kayit))

            # En yakın tarihli adayı seç
            if adaylar:
                # Tarih farkına göre sırala, en küçük fark en başta
                adaylar.sort(key=lambda x: x[0])
                en_yakin_tarih_fark, en_yakin_fatura, en_yakin_kayit = adaylar[0]

                # SARI: Tutar eşleşiyor, Fatura No eşleşmiyor (aynı işlem tipi, en yakın tarih)
                sari_satirlar.append((depo_fatura, en_yakin_fatura, depo_kayit, en_yakin_kayit))
                tutar_eslesen_depo.add(depo_fatura)
                tutar_eslesen_eczane.add(en_yakin_fatura)

        # Hiç eşleşmeyenler - KIRMIZI
        for depo_fatura, depo_kayit in eslesmeyen_depo.items():
            if depo_fatura not in tutar_eslesen_depo:
                kirmizi_depo.append((depo_fatura, depo_kayit))

        for eczane_fatura, eczane_kayit in eslesmeyen_eczane.items():
            if eczane_fatura not in tutar_eslesen_eczane:
                kirmizi_eczane.append((eczane_fatura, eczane_kayit))

        # Ana frame
        main_frame = tk.Frame(pencere, bg='#ECEFF1')
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Başlık
        header_frame = tk.Frame(main_frame, bg='#ECEFF1')
        header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            header_frame,
            text="📊 DEPO - ECZANE EKSTRE KARŞILAŞTIRMA",
            font=("Arial", 14, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack()

        # Borç bilgileri
        borc_frame = tk.Frame(header_frame, bg='#ECEFF1')
        borc_frame.pack(fill="x", pady=(5, 5))

        # Depo'ya göre borç (Depo Excel) - Borç - Alacak
        depo_toplam_borc = sum(kayit['borc'] for kayit in depo_data.values())
        depo_toplam_alacak = sum(kayit['alacak'] for kayit in depo_data.values())
        depo_net_borc = depo_toplam_borc - depo_toplam_alacak

        depo_borc_frame = tk.Frame(borc_frame, bg='#E3F2FD', relief="raised", bd=1)
        depo_borc_frame.pack(side="left", fill="both", expand=True, padx=3)

        tk.Label(
            depo_borc_frame,
            text="📦 Depo Excel'e Göre - Depoya Ödenmesi Gereken",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#01579B'
        ).pack(pady=(3, 0))

        tk.Label(
            depo_borc_frame,
            text=f"{depo_net_borc:,.2f} ₺",
            font=("Arial", 12, "bold"),
            bg='#E3F2FD',
            fg='#01579B'
        ).pack(pady=(0, 3))

        # Eczane programına göre borç - Borç - Alacak
        eczane_toplam_borc = sum(kayit['borc'] for kayit in eczane_data.values())
        eczane_toplam_alacak = sum(kayit['alacak'] for kayit in eczane_data.values())
        eczane_net_borc = eczane_toplam_borc - eczane_toplam_alacak

        eczane_borc_frame = tk.Frame(borc_frame, bg='#E8F5E9', relief="raised", bd=1)
        eczane_borc_frame.pack(side="left", fill="both", expand=True, padx=3)

        tk.Label(
            eczane_borc_frame,
            text="🏥 Eczane Programına Göre - Depoya Ödenmesi Gereken",
            font=("Arial", 9, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        ).pack(pady=(3, 0))

        tk.Label(
            eczane_borc_frame,
            text=f"{eczane_net_borc:,.2f} ₺",
            font=("Arial", 12, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        ).pack(pady=(0, 3))

        # Filtre bilgisi göster
        if depo_filtreli > 0 or eczane_filtreli > 0:
            filtre_text = f"⚙️ Filtre uygulandı: Depo'dan {depo_filtreli}, Eczane'den {eczane_filtreli} satır atlandı"
            tk.Label(
                header_frame,
                text=filtre_text,
                font=("Arial", 9),
                bg='#FFF3E0',
                fg='#E65100',
                padx=10,
                pady=3
            ).pack(pady=(5, 0))

        # ===== SCROLLABLE CANVAS İÇİN CONTAINER =====
        canvas_container = tk.Frame(main_frame, bg='#ECEFF1')
        canvas_container.pack(fill="both", expand=True)

        # Canvas ve scrollbar
        canvas = tk.Canvas(canvas_container, bg='#ECEFF1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ECEFF1')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ===== ACCORDION HELPER FUNCTION =====
        def create_accordion_panel(parent, title, bg_color, fg_color, content_builder):
            """Genişleyebilen panel oluştur"""
            # Panel container
            panel_frame = tk.Frame(parent, bg='#ECEFF1')
            panel_frame.pack(fill="x", pady=2)

            # Başlık (tıklanabilir)
            header_frame = tk.Frame(panel_frame, bg=bg_color, cursor="hand2", relief="raised", bd=2)
            header_frame.pack(fill="x")

            # Açık/kapalı durumu için değişken
            is_expanded = tk.BooleanVar(value=False)
            arrow_label = tk.Label(header_frame, text="▶", bg=bg_color, fg=fg_color, font=("Arial", 12, "bold"))
            arrow_label.pack(side="left", padx=5)

            title_label = tk.Label(header_frame, text=title, bg=bg_color, fg=fg_color,
                                  font=("Arial", 10, "bold"), anchor="w")
            title_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            # İçerik frame (başlangıçta gizli)
            content_frame = tk.Frame(panel_frame, bg=bg_color, relief="sunken", bd=2)

            def toggle():
                if is_expanded.get():
                    # Kapat
                    content_frame.pack_forget()
                    arrow_label.config(text="▶")
                    is_expanded.set(False)
                else:
                    # Aç
                    content_frame.pack(fill="both", expand=True, padx=2, pady=2)
                    arrow_label.config(text="▼")
                    is_expanded.set(True)
                    # İçeriği sadece ilk açılışta oluştur
                    if not content_frame.winfo_children():
                        content_builder(content_frame)

            header_frame.bind("<Button-1>", lambda e: toggle())
            arrow_label.bind("<Button-1>", lambda e: toggle())
            title_label.bind("<Button-1>", lambda e: toggle())

            return panel_frame

        # ===== PANEL 1: TÜM KAYITLAR (KONSOLİDE GÖRÜNÜM) =====
        def build_tum_kayitlar(content_frame):
            """Tüm kayıtları konsolide görünüm olarak göster"""
            # Toplamları hesapla
            yesil_tutar = sum(d['borc'] for _, d, _ in yesil_satirlar)
            sari_tutar = sum(d['borc'] for _, _, d, _ in sari_satirlar)
            turuncu_depo_tutar = sum(d['borc'] for _, d, _ in turuncu_satirlar)
            turuncu_eczane_tutar = sum(e['borc'] for _, _, e in turuncu_satirlar)
            kirmizi_eczane_tutar = sum((k['borc'] if abs(k['borc']) > 0.01 else abs(k['alacak'])) for _, k in kirmizi_eczane)
            kirmizi_depo_tutar = sum((k['borc'] if abs(k['borc']) > 0.01 else abs(k['alacak'])) for _, k in kirmizi_depo)

            toplam_kayit = len(yesil_satirlar) + len(sari_satirlar) + len(turuncu_satirlar) + len(kirmizi_eczane) + len(kirmizi_depo)

            # Bilgi label
            info_label = tk.Label(
                content_frame,
                text=f"📋 Toplam {toplam_kayit} kayıt | 🟢 {len(yesil_satirlar)} | 🟡 {len(sari_satirlar)} | 🟠 {len(turuncu_satirlar)} | 🔴 {len(kirmizi_eczane) + len(kirmizi_depo)}",
                bg='#E3F2FD',
                font=("Arial", 10, "bold"),
                fg='#1565C0',
                padx=10,
                pady=5
            )
            info_label.pack(fill="x", padx=0, pady=5)

            # Treeview - 2 kolonlu (Depo | Eczane) + Tarih ve Tip
            tree_container = tk.Frame(content_frame, bg='white')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='white')
            header_frame.pack(fill="x", side="top")

            # DEPO TARAFI başlığı
            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 10, "bold"),
                bg='#B3E5FC',
                fg='#01579B',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            depo_header.pack(side="left", fill="both", expand=True)

            # Ayırıcı
            sep_header = tk.Label(
                header_frame,
                text="║",
                font=("Arial", 11, "bold"),
                bg='white',
                width=2
            )
            sep_header.pack(side="left")

            # ECZANE TARAFI başlığı
            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 10, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Treeview frame
            tree_frame = tk.Frame(tree_container, bg='white')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=15
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")
            tree.column("depo_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("depo_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("depo_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("depo_tutar", width=110, minwidth=110, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("eczane_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("eczane_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=110, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            # Yeşil satırlar - Tam eşleşme
            for fatura, depo, eczane in yesil_satirlar:
                tree.insert("", "end", values=(
                    fatura, depo.get('tarih', ''), depo.get('tip', ''), f"{depo['borc']:,.2f} ₺",
                    "║",
                    fatura, eczane.get('tarih', ''), eczane.get('tip', ''), f"{eczane['borc']:,.2f} ₺"
                ), tags=('yesil',))

            # Sarı satırlar - Tutar eşleşiyor, fatura no eşleşmiyor
            for depo_fatura, eczane_fatura, depo, eczane in sari_satirlar:
                tree.insert("", "end", values=(
                    depo_fatura, depo.get('tarih', ''), depo.get('tip', ''), f"{depo['borc']:,.2f} ₺",
                    "║",
                    eczane_fatura, eczane.get('tarih', ''), eczane.get('tip', ''), f"{eczane['borc']:,.2f} ₺"
                ), tags=('sari', 'sari_fatura'))

            # Turuncu satırlar - Fatura no eşleşiyor, tutar eşleşmiyor
            for fatura, depo, eczane in turuncu_satirlar:
                tree.insert("", "end", values=(
                    fatura, depo.get('tarih', ''), depo.get('tip', ''), f"{depo['borc']:,.2f} ₺",
                    "║",
                    fatura, eczane.get('tarih', ''), eczane.get('tip', ''), f"{eczane['borc']:,.2f} ₺"
                ), tags=('turuncu', 'turuncu_tutar'))

            # Kırmızı satırlar - Eczane'de var, Depo'da yok
            for fatura, kayit in kirmizi_eczane:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    "", "", "", "",
                    "║",
                    fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺"
                ), tags=('kirmizi',))

            # Kırmızı satırlar - Depo'da var, Eczane'de yok
            for fatura, kayit in kirmizi_depo:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺",
                    "║",
                    "", "", "", ""
                ), tags=('kirmizi',))

            # Renk yapılandırması
            tree.tag_configure('yesil', background='#C8E6C9')
            tree.tag_configure('sari', background='#FFF9C4')
            tree.tag_configure('turuncu', background='#FFE0B2')
            tree.tag_configure('kirmizi', background='#FFCDD2')

        tum_kayitlar_count = len(yesil_satirlar) + len(sari_satirlar) + len(turuncu_satirlar) + len(kirmizi_eczane) + len(kirmizi_depo)
        create_accordion_panel(
            scrollable_frame,
            f"📊 TÜM KAYITLAR - KONSOLİDE GÖRÜNÜM ({tum_kayitlar_count} kayıt)",
            "#E3F2FD",
            "#0D47A1",
            build_tum_kayitlar
        )

        # ===== PANEL 2: YEŞİL (TAM EŞLEŞENLER) =====
        def build_yesil_panel(content_frame):
            tree_container = tk.Frame(content_frame, bg='#E8F5E9')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='white')
            header_frame.pack(fill="x", side="top")

            # DEPO TARAFI başlığı
            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 11, "bold"),
                bg='#B3E5FC',  # Light blue
                fg='#01579B',
                relief="raised",
                bd=2,
                padx=5,
                pady=5
            )
            depo_header.pack(side="left", fill="both", expand=True)

            # Ayırıcı
            sep_header = tk.Label(header_frame, text="║", font=("Arial", 10, "bold"), bg='white', width=2)
            sep_header.pack(side="left")

            # ECZANE TARAFI başlığı
            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 11, "bold"),
                bg='#C8E6C9',  # Light green
                fg='#1B5E20',
                relief="raised",
                bd=2,
                padx=5,
                pady=5
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Tree frame
            tree_frame = tk.Frame(tree_container, bg='#E8F5E9')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=10
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")

            tree.column("depo_fatura", width=180, minwidth=180, anchor="center", stretch=False)
            tree.column("depo_tarih", width=110, minwidth=110, anchor="center", stretch=False)
            tree.column("depo_tip", width=110, minwidth=110, anchor="center", stretch=False)
            tree.column("depo_tutar", width=130, minwidth=130, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=180, minwidth=180, anchor="center", stretch=False)
            tree.column("eczane_tarih", width=110, minwidth=110, anchor="center", stretch=False)
            tree.column("eczane_tip", width=110, minwidth=110, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=130, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            for fatura, depo, eczane in yesil_satirlar:
                tree.insert("", "end", values=(
                    fatura, depo.get('tarih', ''), depo.get('tip', ''), f"{depo['borc']:,.2f} ₺",
                    "║",
                    fatura, eczane.get('tarih', ''), eczane.get('tip', ''), f"{eczane['borc']:,.2f} ₺"
                ), tags=('yesil',))
            tree.tag_configure('yesil', background='#C8E6C9')

        create_accordion_panel(
            scrollable_frame,
            f"🟢 TAM EŞLEŞENLER (Fatura No + Tutar) - {len(yesil_satirlar)} kayıt",
            "#E8F5E9",
            "#2E7D32",
            build_yesil_panel
        )

        # ===== PANEL 3: SARI (TUTAR EŞLEŞENLER) =====
        def build_sari_panel(content_frame):
            tree_container = tk.Frame(content_frame, bg='#FFFDE7')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='#FFFDE7')
            header_frame.pack(fill="x", side="top")

            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 10, "bold"),
                bg='#B3E5FC',
                fg='#01579B',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            depo_header.pack(side="left", fill="both", expand=True)

            sep_header = tk.Label(header_frame, text="║", font=("Arial", 11, "bold"), bg='#FFFDE7', width=2)
            sep_header.pack(side="left")

            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 10, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Treeview frame
            tree_frame = tk.Frame(tree_container, bg='#FFFDE7')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=10
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")
            tree.column("depo_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("depo_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("depo_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("depo_tutar", width=110, minwidth=110, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("eczane_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("eczane_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=110, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            for depo_fatura, eczane_fatura, depo, eczane in sari_satirlar:
                tree.insert("", "end", values=(
                    depo_fatura,
                    depo.get('tarih', ''),
                    depo.get('tip', ''),
                    f"{depo['borc']:,.2f} ₺",
                    "║",
                    eczane_fatura,
                    eczane.get('tarih', ''),
                    eczane.get('tip', ''),
                    f"{eczane['borc']:,.2f} ₺"
                ), tags=('sari',))
            tree.tag_configure('sari', background='#FFF9C4')

        create_accordion_panel(
            scrollable_frame,
            f"🟡 TUTAR EŞLEŞENLER (Fatura No Farklı) - {len(sari_satirlar)} kayıt",
            "#FFFDE7",
            "#F9A825",
            build_sari_panel
        )

        # ===== PANEL 4: TURUNCU (FATURA NO EŞLEŞENLER) =====
        def build_turuncu_panel(content_frame):
            tree_container = tk.Frame(content_frame, bg='#FFF3E0')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='#FFF3E0')
            header_frame.pack(fill="x", side="top")

            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 10, "bold"),
                bg='#B3E5FC',
                fg='#01579B',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            depo_header.pack(side="left", fill="both", expand=True)

            sep_header = tk.Label(header_frame, text="║", font=("Arial", 11, "bold"), bg='#FFF3E0', width=2)
            sep_header.pack(side="left")

            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 10, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Treeview frame
            tree_frame = tk.Frame(tree_container, bg='#FFF3E0')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=10
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")
            tree.column("depo_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("depo_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("depo_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("depo_tutar", width=110, minwidth=110, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("eczane_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("eczane_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=110, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            for fatura, depo, eczane in turuncu_satirlar:
                tree.insert("", "end", values=(
                    fatura,
                    depo.get('tarih', ''),
                    depo.get('tip', ''),
                    f"{depo['borc']:,.2f} ₺",
                    "║",
                    fatura,
                    eczane.get('tarih', ''),
                    eczane.get('tip', ''),
                    f"{eczane['borc']:,.2f} ₺"
                ), tags=('turuncu',))
            tree.tag_configure('turuncu', background='#FFE0B2')

        create_accordion_panel(
            scrollable_frame,
            f"🟠 FATURA NO EŞLEŞENLER (Tutar Farklı) - {len(turuncu_satirlar)} kayıt",
            "#FFF3E0",
            "#E65100",
            build_turuncu_panel
        )

        # ===== PANEL 5: KIRMIZI (EŞLEŞMEYENLER) =====
        def build_kirmizi_panel(content_frame):
            # Konsolide yapı: Sol Depo, Sağ Eczane
            tree_container = tk.Frame(content_frame, bg='#FFEBEE')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='#FFEBEE')
            header_frame.pack(fill="x", side="top")

            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 10, "bold"),
                bg='#B3E5FC',
                fg='#01579B',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            depo_header.pack(side="left", fill="both", expand=True)

            sep_header = tk.Label(header_frame, text="║", font=("Arial", 11, "bold"), bg='#FFEBEE', width=2)
            sep_header.pack(side="left")

            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 10, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Treeview frame
            tree_frame = tk.Frame(tree_container, bg='#FFEBEE')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=10
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")
            tree.column("depo_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("depo_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("depo_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("depo_tutar", width=110, minwidth=110, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("eczane_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("eczane_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=110, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            # Depo'da var, Eczane'de yok - sol tarafta göster
            for fatura, kayit in kirmizi_depo:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    fatura,
                    kayit.get('tarih', ''),
                    kayit.get('tip', ''),
                    f"{tutar:,.2f} ₺",
                    "║",
                    "", "", "", ""
                ), tags=('kirmizi',))

            # Eczane'de var, Depo'da yok - sağ tarafta göster
            for fatura, kayit in kirmizi_eczane:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    "", "", "", "",
                    "║",
                    fatura,
                    kayit.get('tarih', ''),
                    kayit.get('tip', ''),
                    f"{tutar:,.2f} ₺"
                ), tags=('kirmizi',))

            tree.tag_configure('kirmizi', background='#FFCDD2')

        create_accordion_panel(
            scrollable_frame,
            f"🔴 EŞLEŞMEYENLER - {len(kirmizi_eczane) + len(kirmizi_depo)} kayıt (Eczane: {len(kirmizi_eczane)}, Depo: {len(kirmizi_depo)})",
            "#FFEBEE",
            "#C62828",
            build_kirmizi_panel
        )

        # ===== TOPLAMLAR PANELİ =====
        def build_toplam_panel(content_frame):
            # Toplamları hesapla
            yesil_tutar = sum(d['borc'] for _, d, _ in yesil_satirlar)
            sari_tutar = sum(d['borc'] for _, _, d, _ in sari_satirlar)
            turuncu_depo_tutar = sum(d['borc'] for _, d, _ in turuncu_satirlar)
            turuncu_eczane_tutar = sum(e['borc'] for _, _, e in turuncu_satirlar)
            kirmizi_eczane_tutar = sum((k['borc'] if abs(k['borc']) > 0.01 else abs(k['alacak'])) for _, k in kirmizi_eczane)
            kirmizi_depo_tutar = sum((k['borc'] if abs(k['borc']) > 0.01 else abs(k['alacak'])) for _, k in kirmizi_depo)

            tree_frame = tk.Frame(content_frame, bg='#E3F2FD')
            tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

            tree = ttk.Treeview(
                tree_frame,
                columns=("kategori", "kayit", "tutar"),
                show="headings",
                height=6
            )
            tree.heading("kategori", text="Kategori")
            tree.heading("kayit", text="Kayıt Sayısı")
            tree.heading("tutar", text="Toplam Tutar")
            tree.column("kategori", width=350)
            tree.column("kayit", width=120, anchor="center")
            tree.column("tutar", width=200, anchor="e")

            # Yeşil toplam
            tree.insert("", "end", values=(
                "🟢 Fatura No + Tutar Eşleşiyor",
                len(yesil_satirlar),
                f"{yesil_tutar:,.2f} ₺"
            ), tags=('yesil',))

            # Sarı toplam
            tree.insert("", "end", values=(
                "🟡 Tutar Eşleşiyor - Fatura No Eşleşmiyor",
                len(sari_satirlar),
                f"{sari_tutar:,.2f} ₺"
            ), tags=('sari',))

            # Turuncu toplam
            tree.insert("", "end", values=(
                f"🟠 Fatura No Eşleşiyor - Tutar Eşleşmiyor (Fark: {turuncu_depo_tutar - turuncu_eczane_tutar:,.2f} ₺)",
                len(turuncu_satirlar),
                f"Depo: {turuncu_depo_tutar:,.2f} / Eczane: {turuncu_eczane_tutar:,.2f} ₺"
            ), tags=('turuncu',))

            # Kırmızı toplam - Eczane
            tree.insert("", "end", values=(
                "🔴 Eczane'de Var - Eşleşmiyor",
                len(kirmizi_eczane),
                f"{kirmizi_eczane_tutar:,.2f} ₺"
            ), tags=('kirmizi',))

            # Kırmızı toplam - Depo
            tree.insert("", "end", values=(
                "🔴 Depo'da Var - Eşleşmiyor",
                len(kirmizi_depo),
                f"{kirmizi_depo_tutar:,.2f} ₺"
            ), tags=('kirmizi',))

            tree.tag_configure('yesil', background='#C8E6C9')
            tree.tag_configure('sari', background='#FFF9C4')
            tree.tag_configure('turuncu', background='#FFE0B2')
            tree.tag_configure('kirmizi', background='#FFCDD2')

            tree.pack(fill="both", expand=True)

        create_accordion_panel(
            scrollable_frame,
            "📊 TOPLAMLAR",
            "#E3F2FD",
            "#1565C0",
            build_toplam_panel
        )

        # ===== PANEL 6: FİLTRELENEN SATIRLAR =====
        def build_filtrelenen_panel(content_frame):
            # Konsolide yapı: Sol Depo, Sağ Eczane
            tree_container = tk.Frame(content_frame, bg='#F5F5F5')
            tree_container.pack(fill="both", expand=True, padx=0, pady=5)

            # Üst başlık - DEPO TARAFI / ECZANE TARAFI
            header_frame = tk.Frame(tree_container, bg='white')
            header_frame.pack(fill="x", side="top")

            # DEPO TARAFI başlığı
            depo_header = tk.Label(
                header_frame,
                text="📦 DEPO TARAFI",
                font=("Arial", 10, "bold"),
                bg='#B3E5FC',
                fg='#01579B',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            depo_header.pack(side="left", fill="both", expand=True)

            # Ayırıcı
            sep_header = tk.Label(header_frame, text="║", font=("Arial", 10, "bold"), bg='white', width=2)
            sep_header.pack(side="left")

            # ECZANE TARAFI başlığı
            eczane_header = tk.Label(
                header_frame,
                text="🏥 ECZANE TARAFI",
                font=("Arial", 10, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                relief="raised",
                bd=1,
                padx=3,
                pady=3
            )
            eczane_header.pack(side="left", fill="both", expand=True)

            # Tree frame
            tree_frame = tk.Frame(tree_container, bg='#F5F5F5')
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_frame,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=10
            )
            tree.heading("depo_fatura", text="Fatura No")
            tree.heading("depo_tarih", text="Tarih")
            tree.heading("depo_tip", text="Tip")
            tree.heading("depo_tutar", text="Tutar")
            tree.heading("sep", text="║")
            tree.heading("eczane_fatura", text="Fatura No")
            tree.heading("eczane_tarih", text="Tarih")
            tree.heading("eczane_tip", text="Tip")
            tree.heading("eczane_tutar", text="Tutar")

            tree.column("depo_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("depo_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("depo_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("depo_tutar", width=110, minwidth=110, anchor="e", stretch=False)
            tree.column("sep", width=15, minwidth=15, anchor="center", stretch=False)
            tree.column("eczane_fatura", width=140, minwidth=140, anchor="w", stretch=False)
            tree.column("eczane_tarih", width=100, minwidth=100, anchor="center", stretch=False)
            tree.column("eczane_tip", width=90, minwidth=90, anchor="center", stretch=False)
            tree.column("eczane_tutar", width=150, minwidth=110, anchor="e", stretch=True)

            tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            # Filtrelenen Depo satırları
            for fatura, kayit in filtrelenen_depo_satirlar:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺",
                    "║",
                    "", "", "", ""
                ), tags=('filtrelenen',))

            # Filtrelenen Eczane satırları
            for fatura, kayit in filtrelenen_eczane_satirlar:
                tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
                tree.insert("", "end", values=(
                    "", "", "", "",
                    "║",
                    fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺"
                ), tags=('filtrelenen',))

            tree.tag_configure('filtrelenen', background='#E0E0E0')

        create_accordion_panel(
            scrollable_frame,
            f"⚙️ AYARLAMALAR SAYESİNDE YOK SAYILAN/TASNİF EDİLMEYEN SATIRLAR - {len(filtrelenen_depo_satirlar) + len(filtrelenen_eczane_satirlar)} kayıt (Depo: {len(filtrelenen_depo_satirlar)}, Eczane: {len(filtrelenen_eczane_satirlar)})",
            "#F5F5F5",
            "#757575",
            build_filtrelenen_panel
        )

        # Butonlar
        button_frame = tk.Frame(main_frame, bg='#ECEFF1')
        button_frame.pack(fill="x", pady=5)

        # Sonuçları sakla
        self.ekstre_sonuclar = {
            'yesil': yesil_satirlar,
            'sari': sari_satirlar,
            'turuncu': turuncu_satirlar,
            'kirmizi_eczane': kirmizi_eczane,
            'kirmizi_depo': kirmizi_depo,
            'df_depo': df_depo,
            'df_eczane': df_eczane,
            'depo_fatura_col': depo_fatura_col,
            'eczane_fatura_col': eczane_fatura_col
        }

        tk.Button(
            button_frame,
            text="📥 Excel'e Aktar",
            font=("Arial", 11, "bold"),
            bg='#388E3C',
            fg='white',
            width=20,
            cursor="hand2",
            command=lambda: self.ekstre_sonuc_excel_aktar_v2(pencere)
        ).pack(side="left", padx=10)

        tk.Button(
            button_frame,
            text="❌ Kapat",
            font=("Arial", 11),
            bg='#757575',
            fg='white',
            width=15,
            cursor="hand2",
            command=pencere.destroy
        ).pack(side="right", padx=10)

    def _bul_sutun(self, df, alternatifler):
        """DataFrame'de sütun bul"""
        for alt in alternatifler:
            if alt in df.columns:
                return alt
        # Kısmi eşleşme
        for alt in alternatifler:
            alt_lower = alt.lower().replace(" ", "").replace("_", "").replace("/", "")
            for col in df.columns:
                col_lower = col.lower().replace(" ", "").replace("_", "").replace("/", "")
                if alt_lower in col_lower or col_lower in alt_lower:
                    return col
        return None

    def ekstre_sonuc_excel_aktar_v2(self, pencere):
        """Karşılaştırma sonuçlarını Excel'e aktar - yeni versiyon"""
        import pandas as pd

        if not hasattr(self, 'ekstre_sonuclar') or not self.ekstre_sonuclar:
            messagebox.showwarning("Uyarı", "Önce karşılaştırma yapın!")
            return

        dosya_yolu = filedialog.asksaveasfilename(
            title="Sonuçları Kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")],
            initialname=f"ekstre_karsilastirma_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not dosya_yolu:
            return

        try:
            sonuclar = self.ekstre_sonuclar

            with pd.ExcelWriter(dosya_yolu, engine='openpyxl') as writer:
                # Yeşil - Tam eşleşenler
                if sonuclar['yesil']:
                    yesil_data = []
                    for fatura, depo, eczane in sonuclar['yesil']:
                        yesil_data.append({
                            'Fatura No': fatura,
                            'Borç': depo['borc'],
                            'Alacak': depo['alacak'],
                            'Durum': 'Tam Eşleşme'
                        })
                    pd.DataFrame(yesil_data).to_excel(writer, sheet_name='Yeşil-Tam Eşleşme', index=False)

                # Turuncu - Kısmi eşleşenler
                if sonuclar['turuncu']:
                    turuncu_data = []
                    for fatura, depo, eczane, borc_esit, alacak_esit in sonuclar['turuncu']:
                        turuncu_data.append({
                            'Fatura No': fatura,
                            'Depo Borç': depo['borc'],
                            'Eczane Borç': eczane['borc'],
                            'Depo Alacak': depo['alacak'],
                            'Eczane Alacak': eczane['alacak'],
                            'Borç Eşit': 'Evet' if borc_esit else 'Hayır',
                            'Alacak Eşit': 'Evet' if alacak_esit else 'Hayır'
                        })
                    pd.DataFrame(turuncu_data).to_excel(writer, sheet_name='Turuncu-Kısmi Eşleşme', index=False)

                # Kırmızı Sol - Eczane'de var, Depo'da yok
                if sonuclar['kirmizi_sol']:
                    kirmizi_sol_data = []
                    for fatura, kayit in sonuclar['kirmizi_sol']:
                        kirmizi_sol_data.append({
                            'Fatura No': fatura,
                            'Borç (Fatura Tutarı)': kayit['borc'],
                            'Alacak (İade/Çık)': kayit['alacak']
                        })
                    pd.DataFrame(kirmizi_sol_data).to_excel(writer, sheet_name='Eczanede Var-Depoda Yok', index=False)

                # Kırmızı Sağ - Depo'da var, Eczane'de yok
                if sonuclar['kirmizi_sag']:
                    kirmizi_sag_data = []
                    for fatura, kayit in sonuclar['kirmizi_sag']:
                        kirmizi_sag_data.append({
                            'Fatura No': fatura,
                            'Borç': kayit['borc'],
                            'Alacak': kayit['alacak']
                        })
                    pd.DataFrame(kirmizi_sag_data).to_excel(writer, sheet_name='Depoda Var-Eczanede Yok', index=False)

                # Özet
                ozet_data = {
                    'Kategori': [
                        'Tam Eşleşen (Yeşil)',
                        'Kısmi Eşleşen (Turuncu)',
                        'Eczanede Var - Depoda Yok (Kırmızı)',
                        'Depoda Var - Eczanede Yok (Kırmızı)'
                    ],
                    'Kayıt Sayısı': [
                        len(sonuclar['yesil']),
                        len(sonuclar['turuncu']),
                        len(sonuclar['kirmizi_sol']),
                        len(sonuclar['kirmizi_sag'])
                    ]
                }
                pd.DataFrame(ozet_data).to_excel(writer, sheet_name='Özet', index=False)

            messagebox.showinfo("Başarılı", f"Sonuçlar kaydedildi:\n{dosya_yolu}")

        except Exception as e:
            messagebox.showerror("Hata", f"Excel kaydedilemedi: {str(e)}")
            logger.error(f"Excel kaydetme hatası: {e}")


def main():
    """Ana fonksiyon"""
    root = tk.Tk()
    app = BotanikGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Konsol penceresini yerleştir (MEDULA açıldıktan sonra tekrar yerleştirilecek)
    try:
        console_pencereyi_ayarla()
    except Exception as e:
        logger.debug(f"İlk konsol yerleştirme hatası (normal): {e}")

    root.mainloop()


if __name__ == "__main__":
    main()
