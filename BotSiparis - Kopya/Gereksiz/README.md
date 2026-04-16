# Botanik Sipariş Yardımcısı

Botanik EOS'taki "Yok" ürünleri otomatik olarak 3 depoda (Alliance, Selçuk, Yusuf Paşa) sorgulayan ve sipariş veren Python otomasyon aracı.

## Özellikler

- **Otomatik Depo Sorgulama**: Yok ürünleri 3 depoda otomatik sorgular
- **Akıllı Sipariş Hesaplama**: MF, MinStk ve mevcut stok bilgilerine göre sipariş adedini hesaplar
- **Kullanıcı Dostu GUI**: Tkinter tabanlı, kolay kullanımlı arayüz
- **Renkli Görselleştirme**: Stok durumlarını renklerle gösterir (Yeşil: Var, Kırmızı: Yok)
- **Loglama**: Tüm işlemleri detaylı olarak loglar

## Kurulum

### 1. Python Kurulumu

Python 3.8 veya üzeri gereklidir. [Python İndir](https://www.python.org/downloads/)

Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin!

### 2. Bağımlılıkları Yükleyin

Proje klasöründe bir terminal açın ve şu komutu çalıştırın:

```bash
pip install -r requirements.txt
```

### 3. Chrome Tarayıcı

Chrome tarayıcısının yüklü olması gerekir. Program ChromeDriver'ı otomatik indirecektir.

## Kullanım

### Adım 1: Botanik EOS'u Açın

- Botanik EOS uygulamasını açın
- "Sipariş Yardımcısı" penceresine gidin

### Adım 2: Depoları Açın

Tarayıcınızda şu depo sayfalarını açın ve giriş yapın:

1. **Alliance**: https://esiparisv2.alliance-healthcare.com.tr/Sales/QuickOrder
2. **Selçuk**: https://webdepo.selcukecza.com.tr/Siparis/hizlisiparis.aspx
3. **Yusuf Paşa**: http://eticaret.yusufpasa.com/Orders.asp

### Adım 3: Programı Çalıştırın

Proje klasöründe terminal açın ve:

```bash
python main.py
```

### Adım 4: Taramayı Başlatın

1. Program açıldığında **"Taramayı Başlat"** butonuna tıklayın
2. Program otomatik olarak:
   - Botanik EOS'taki "Yoklar" butonuna tıklar
   - Tüm yok ürünlerin barkodunu okur
   - Her ürünü 3 depoda sorgular
   - Sipariş adedini hesaplar
   - Sonuçları tabloda gösterir

### Adım 5: Sipariş Verin

1. Tabloda stokta olan ürünleri göreceksiniz (yeşil)
2. **"Seçilenleri Sipariş Et"** butonuna tıklayın
3. Onay verin
4. Program otomatik olarak Botanik EOS'ta ADET kolonuna değerleri yazacaktır

## Sipariş Adedi Hesaplama Mantığı

Program sipariş adedini şu mantıkla hesaplar:

### MF Dolu İse:
```
Sipariş Adedi = MF değeri
```

### MF Boş/0 İse:
```
Hedef Stok = MinStk + 1
Sipariş Adedi = Hedef Stok - Mevcut Stok
```

**Örnek:**
- Ürün: HIPERSAR
- Mevcut Stok: -2
- MF: 6
- MinStk: 3
- **Sipariş = 6** (MF direkt kullanıldı)

**Örnek 2:**
- Ürün: FLUNIT
- Mevcut Stok: -1
- MF: 0
- MinStk: 2
- Hedef = 2 + 1 = 3
- **Sipariş = 3 - (-1) = 4**

## Proje Yapısı

```
BotSiparis/
├── main.py                 # Ana giriş noktası
├── requirements.txt        # Python bağımlılıkları
├── README.md              # Bu dosya
├── .env.example           # Örnek konfigürasyon
├── src/
│   ├── botanik/           # Botanik EOS otomasyon
│   │   └── eos_controller.py
│   ├── depolar/           # Depo sorgulama modülleri
│   │   ├── base_depo.py
│   │   ├── alliance.py
│   │   ├── selcuk.py
│   │   └── yusufpasa.py
│   ├── gui/               # GUI modülü
│   │   └── main_window.py
│   ├── utils/             # Yardımcı modüller
│   │   ├── config.py
│   │   └── logger.py
│   └── controller.py      # Ana koordinasyon
├── logs/                  # Log dosyaları
└── data/                  # Veri dosyaları
```

## Loglar

Tüm işlemler otomatik olarak loglanır. Log dosyaları `logs/` klasöründe bulunur:

```
logs/bot_20231113.log
```

## Sorun Giderme

### "Botanik EOS bulunamadı" Hatası

- Botanik EOS'un açık olduğundan emin olun
- "Sipariş Yardımcısı" penceresinin açık olduğunu kontrol edin

### Depo Sorgu Hataları

- Depo sayfalarına giriş yaptığınızdan emin olun
- İnternet bağlantınızı kontrol edin
- Chrome tarayıcısının güncel olduğundan emin olun

### Element Bulunamadı Hataları

- Botanik EOS'un güncellenmiş olabileceğini düşünün
- Element isimlerinin değişip değişmediğini kontrol edin
- Log dosyalarını inceleyin

## Gelecek Geliştirmeler

- [ ] Top/Ort değerini otomatik okuma (MF=0 durumunda)
- [ ] Depo login otomasyonu
- [ ] Excel export özelliği
- [ ] Çoklu tarayıcı desteği
- [ ] Daha detaylı stok bilgileri

## Lisans

Bu proje kişisel kullanım içindir.

## İletişim

Sorularınız için: [GitHub Issues](https://github.com/)

---

**Not:** Bu araç Botanik EOS ve depo web sitelerinin mevcut yapısına göre geliştirilmiştir. Bu sitelerde yapılacak değişiklikler aracın çalışmasını etkileyebilir.
