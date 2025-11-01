# 📋 Reçete İşleme Döngüsü ve Süre Analizi

## 🔄 Reçete İşleme Döngüsü

```
┌─────────────────────────────────────────────────────────────────┐
│                    REÇETE İŞLEME DÖNGÜSÜ                        │
└─────────────────────────────────────────────────────────────────┘

🔄 BAŞLANGIÇ (Her reçete için tekrar eder)
│
├─ 1️⃣ REÇETE KONTROL AŞAMASI                      (~1.5s)
│  ├─ Reçete kaydı var mı kontrol                 (0.5s)
│  ├─ "REÇETE İÇİN NOT" penceresi kapat           (0.5s)
│  └─ "UYARIDIR" penceresi kapat                  (0.5s)
│
├─ 2️⃣ REÇETE NUMARASI OKUMA                       (anlık)
│  └─ Ekrandaki reçete numarasını oku
│
├─ 3️⃣ İLAÇ LİSTESİ AÇMA                          (~2.5s)
│  ├─ "İlaç" butonuna tıkla                       (0.4s)
│  ├─ İlaç ekranı yüklensin                       (1.5s)
│  └─ "Y" butonuna tıkla                          (0.4s)
│
├─ 4️⃣ LABA/LAMA KONTROLÜ (sadece %1 reçetede)    (~2.3s)
│  ├─ İlaç Listesi penceresi açıldı mı?           (0.1s)
│  ├─ ❌ Hayır → LABA/LAMA uyarısı var!
│  │   ├─ Uyarıyı kapat                           (2.0s)
│  │   └─ Tekrar "Y" butonuna bas                 (0.5s)
│  └─ ✅ Evet → Devam et
│
├─ 5️⃣ İLAÇ SEÇİMİ VE TAKİP                       (~0.5s)
│  ├─ "Bizden Alınmayanları Seç" butonuna bas     (0.1s)
│  ├─ Seçili ilaç var mı kontrol                  (0.05s)
│  ├─ ✅ Var → İlk ilaca sağ tık ve "Takip Et"    (0.2s)
│  └─ ❌ Yok → Atla
│
├─ 6️⃣ PENCERE KAPATMA VE GERİ DÖN               (~0.7s)
│  ├─ İlaç Listesi penceresini kapat              (0.1s)
│  └─ "Geri Dön" butonuna tıkla                   (0.6s)
│
└─ 7️⃣ SONRAKİ REÇETEYE GEÇ                       (~0.6s)
   ├─ "SONRA >" butonuna tıkla                    (0.6s)
   ├─ ✅ Başarılı → Döngü başa döner (1️⃣)
   └─ ❌ Buton yok → DÖNGÜ BİTER (son reçete)
```

## 📊 Oturum İstatistikleri

```
┌──────────────────────────────────────────────────┐
│  BAŞLAT'a basıldığında:                          │
│  ├─ Oturum zamanlayıcı BAŞLAR ⏱️                │
│  ├─ Reçete sayacı sıfırlanır (ilk başlatmada)   │
│  └─ Döngü başlar                                 │
│                                                  │
│  DURDUR'a basıldığında:                          │
│  ├─ Oturum zamanlayıcı DURUR ⏸️                 │
│  ├─ Süre kaydedilir                             │
│  └─ Tekrar BAŞLAT → Kaldığı yerden devam        │
└──────────────────────────────────────────────────┘
```

## 🎯 Performans Özeti

| Metrik | Değer |
|--------|-------|
| **Toplam Adım Sayısı** | 7 ana adım |
| **Normal Reçete Süresi** | ~6 saniye |
| **LABA/LAMA Reçete Süresi** | ~8.3 saniye |
| **Saatte İşlenebilir Reçete** | ~550 reçete |
| **En Uzun Adım** | İlaç ekranı yükleme (1.5s) |
| **LABA/LAMA Görülme Oranı** | %1 |

## 🔍 Detaylı Adım Açıklamaları

### 1️⃣ Reçete Kontrol Aşaması
- **Amaç:** Reçetenin geçerli olduğunu ve hata pencerelerinin kapatıldığını doğrular
- **Hata Durumları:**
  - "Reçete kaydı bulunamadı" → İşlem durur
  - "Sistem hatası" → İşlem durur

### 2️⃣ Reçete Numarası Okuma
- **Amaç:** Ekrandaki reçete numarasını (örn: 3HKE0T4) okur ve kaydeder
- **Format:** 6-8 karakter, alfanumerik

### 3️⃣ İlaç Listesi Açma
- **Amaç:** Kullanılan ilaç listesi ekranını açar
- **Bekleme:** İlaç ekranının tamamen yüklenmesini bekler

### 4️⃣ LABA/LAMA Kontrolü
- **Tetikleyici:** İlaç Listesi penceresi bulunamazsa çalışır
- **Desteklenen Uyarılar:**
  - LABA/LAMA uyarısı
  - İlaç çakışması uyarısı
- **Aksiyon:** "Tamam" butonuna otomatik tıklar ve Y'ye tekrar basar

### 5️⃣ İlaç Seçimi ve Takip
- **Amaç:** Bizden alınmayan ilaçları seçer ve takip eder
- **Seçim Mantığı:**
  - Bizden alınmayanları otomatik seçer
  - Seçili ilaç varsa ilk ilaca sağ tıkla → "Takip Et"
  - Yoksa atla

### 6️⃣ Pencere Kapatma ve Geri Dön
- **Amaç:** İlaç Listesi penceresini kapatır ve ana reçete ekranına döner

### 7️⃣ Sonraki Reçeteye Geç
- **Amaç:** "SONRA >" butonuna basarak sıradaki reçeteye geçer
- **Döngü Kontrolü:**
  - Buton varsa → Yeni reçete, döngü devam
  - Buton yoksa → Son reçete, döngü biter

## 📈 Aylık İstatistikler

Her grup için JSON dosyasında saklanır (`grup_durumlari.json`):

```json
{
  "A": {
    "son_recete": "3I03V0U",
    "toplam_recete": 373,
    "toplam_takip": 8,
    "toplam_sure": 2881.51
  }
}
```

### İstatistik Bilgileri:
- **son_recete:** Son işlenen reçete numarası (otomatik açılır)
- **toplam_recete:** Ay boyunca işlenen toplam reçete sayısı
- **toplam_takip:** Ay boyunca takip edilen toplam ilaç sayısı
- **toplam_sure:** Ay boyunca toplam çalışma süresi (saniye)

### Sıfırlama:
- Her grubun yanındaki "✕" butonuna basarak ay sonu sıfırlanabilir

## 🛠️ Hata Yönetimi

### Otomatik Kapatılan Pencereler:
1. ✅ "REÇETE İÇİN NOT" → Kapat butonu
2. ✅ "UYARIDIR" → Kapat butonu
3. ✅ "GENEL MUAYENE TANISI VARDIR" → Kapat butonu
4. ✅ "LABA/LAMA" → Tamam butonu
5. ✅ "İLAÇ ÇAKIŞMASI" → Tamam butonu

### İşlemi Durduran Hatalar:
- ❌ Reçete kaydı bulunamadı
- ❌ Sistem hatası
- ❌ MEDULA bağlantı hatası
- ❌ İlaç Listesi penceresi 2 denemede açılmadı

## 💡 Optimizasyon Notları

### Cache Sistemi:
- ✅ Sık kullanılan butonlar cache'lenir (Y butonu, Sorgula, vb.)
- ✅ Web kontrolleri cache'lenmez (İlaç butonu, Geri Dön)

### Performans İyileştirmeleri:
- Bekleme süreleri minimize edildi (0.3s → 0.15s)
- Element arama optimizasyonları (control_type filtreleri)
- Tek taramada seçili ilaç kontrolü

---

**Son Güncelleme:** 2025-10-28
**Versiyon:** Botanik Bot v3
