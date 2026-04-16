# 📦 Botanik Sipariş Yardımcısı - Kurulum Rehberi

## 🚀 Hızlı Başlangıç

### 1️⃣ Gereksinimler
- Windows 10/11
- Python 3.8 veya üzeri
- Google Chrome tarayıcı
- Botanik EOS programı

### 2️⃣ Kurulum Adımları

#### A) Python Kurulumu
1. https://www.python.org/downloads/ adresinden Python indirin
2. Kurulum sırasında **"Add Python to PATH"** seçeneğini işaretleyin ✅
3. Kurulumu tamamlayın

#### B) Gerekli Kütüphaneleri Yükleyin
```bash
# Komut satırını (CMD) yönetici olarak açın
# Proje klasörüne gidin
cd C:\Users\KULLANICI_ADINIZ\Documents\BotSiparis

# Kütüphaneleri yükleyin
pip install -r requirements.txt
```

#### C) Ayar Dosyasını Oluşturun
1. `.env.example` dosyasını kopyalayın
2. Kopyanın adını `.env` olarak değiştirin
3. `.env` dosyasını açın ve **kendi bilgilerinizi** girin:

```env
# Alliance Healthcare
ALLIANCE_ECZANE_KODU=12345
ALLIANCE_USERNAME=kullanici_adiniz
ALLIANCE_PASSWORD=sifreniz

# Selçuk Ecza
SELCUK_HESAP_KODU=1234567890
SELCUK_USERNAME=kullanici_adiniz
SELCUK_PASSWORD=sifreniz

# ... diğer depolar için aynı şekilde

# Eczane Bilgileri (WhatsApp mesajlarında görünecek)
ECZACI_ADI=Ahmet Yılmaz
ECZANE_ADI=Sağlık Eczanesi
ECZANE_TELEFONU=02125551234
ECZACI_TELEFONU=05321234567
```

### 3️⃣ Programı Başlatın

**Yöntem 1: Çift Tıklama (Önerilen)**
```
start.bat dosyasına çift tıklayın
```

**Yöntem 2: Komut Satırı**
```bash
python main.py
```

**Yöntem 3: CMD Penceresi Olmadan**
```
main.pyw dosyasına çift tıklayın
```

---

## 📱 WhatsApp Özelliği

### İlk Kullanım (Sadece Bir Kere)
1. Programı açın
2. Tarama yapın ve ürünleri seçin
3. 📱 butonuna tıklayın
4. Telefon numarası girin
5. **QR kodu** çıkacak - telefonunuzdan okutun
6. Artık her zaman otomatik gönderecek! ✅

### Sonraki Kullanımlar
- QR kod okutmanıza gerek yok
- Direkt mesaj gönderilir

---

## ⚙️ Ayarlar

### Depo Bilgilerini Güncellemek
1. Sağ üstteki **⚙️** (Ayarlar) butonuna tıklayın
2. Bilgilerinizi güncelleyin
3. **Kaydet** butonuna basın

### Eczane Bilgilerini Güncellemek
1. Ayarlar'a girin
2. **🏥 Eczane Bilgileri** bölümünü doldurun
3. Bu bilgiler WhatsApp mesajlarında görünecek

---

## 🔒 Güvenlik Notları

### ⚠️ ÖNEMLİ
- `.env` dosyasını **KİMSEYLE PAYLAŞMAYIN**
- İçinde depo şifreleriniz var!
- WhatsApp oturumunuz sadece sizin bilgisayarınızda saklanır
- Her kullanıcı kendi WhatsApp hesabını kullanır

### Programı Başkasına Göndermek İsterseniz
1. `.env` dosyasını **SİLİN** (ya da paylaşmayın)
2. `data/` klasörünü **SİLİN** (kişisel verileriniz var)
3. `logs/` klasörünü **SİLİN** (loglarınız var)
4. Sadece kod dosyalarını gönderin
5. Arkadaşınız `.env.example` dosyasını kopyalayıp kendi bilgilerini girecek

---

## 🐛 Sorun Giderme

### "Python bulunamadı" Hatası
- Python'u yükleyin: https://www.python.org/downloads/
- Kurulumda **"Add Python to PATH"** seçeneğini işaretleyin

### "Botanik EOS bulunamadı" Hatası
- Botanik EOS programını açın
- "Sipariş" ekranına gidin
- Programı yeniden başlatın

### WhatsApp QR Kodu Çıkmıyor
- Chrome tarayıcınızı güncelleyin
- `%LOCALAPPDATA%\BotanikWhatsApp` klasörünü silin
- Programı yeniden başlatın ve QR kodu okutun

### Depolar Açılmıyor
- requirements.txt'teki kütüphaneleri yükleyin:
  ```bash
  pip install -r requirements.txt
  ```
- Chrome tarayıcınızı güncelleyin

---

## 📞 Destek

Sorun yaşarsanız:
1. `logs/` klasöründeki log dosyasını kontrol edin
2. Hata mesajını okuyun
3. Gerekirse `.env` dosyanızı kontrol edin

---

## ✅ Başarıyla Kuruldu!

Artık programı kullanabilirsiniz:
1. Botanik EOS'u açın
2. start.bat'a çift tıklayın
3. Taramayı başlatın
4. Siparişlerinizi WhatsApp'tan gönderin! 🚀
