# EczAsist - Eczane Asistan Sistemi

Eczane operasyonlarini otomatize eden kapsamli bir yonetim sistemi.

## Moduller

### 1. Medula Recete Otomasyon
- Otomatik recete isleme (A, B, C gruplari)
- Hata durumlarinda otomatik yeniden baslatma
- Sayfa yukleme sureleri istatistikleri
- Ozellestirebilir bekleme sureleri
- Grup bazli islem yonetimi

### 2. Kasa Kapatma Modulu
- Gunluk kasa sayimi ve mutabakat
- Kupur bazli nakit takibi
- POS ve IBAN raporlari
- Botanik EOS ile karsilastirma
- Fark analizi ve kontrol listeleri
- Ertesi gun kasasi belirleme
- Termal yazici destegi
- WhatsApp rapor gonderme

### 3. Depo Ekstre Modulu
- Depo ekstre takibi ve filtreleme

### 4. Kullanici Yonetimi
- Coklu kullanici destegi
- Yetkilendirme sistemi

## Kurulum

1. Gerekli bagimliliklari yukleyin:
```bash
pip install -r requirements.txt
```

2. Uygulamayi baslatin:
```bash
python main.py
```

## Dosya Yapisi

```
EczAsist/
├── main.py                    # Ana giris noktasi
├── ana_menu.py                # Ana menu arayuzu
├── giris_penceresi.py         # Giris ekrani
├── botanik_gui.py             # Medula GUI
├── botanik_bot.py             # Medula otomasyon motoru
├── kasa_takip_modul.py        # Kasa kapatma ana modulu
├── kasa_wizard.py             # Kasa kapatma wizard
├── kasa_kontrol_listesi.py    # Fark kontrol listesi
├── kasa_gecmis.py             # Gecmis kayitlar
├── kasa_whatsapp.py           # WhatsApp entegrasyonu
├── kasa_yazici.py             # Termal yazici
├── kasa_api_server.py         # REST API (coklu terminal)
├── kasa_api_client.py         # API istemci
├── depo_ekstre_modul.py       # Depo ekstre
├── kullanici_yonetimi.py      # Kullanici yonetimi
├── kullanici_yonetimi_gui.py  # Kullanici GUI
├── database.py                # Veritabani islemleri
├── timing_settings.py         # Zamanlama ayarlari
├── medula_settings.py         # Medula ayarlari
└── session_logger.py          # Oturum loglama
```

## Gereksinimler

- Python 3.8+
- Windows 10/11
- PyAutoGUI
- Tkinter
- Flask (API icin)
- pywin32 (yazici icin)

## Lisans

Bu proje ozel kullanim icindir.

## Iletisim

Sorun bildirimi icin GitHub Issues kullanin.
