# Kaldığımız Yer - 6 Aralık 2025 (Güncelleme 8)

## Son Yapılan Düzeltmeler (Bu Oturum)

### 1. Yeni 5 Butonlu İlaç Mesajı Dialog Sistemi

**Pencere:**
- Boyut: 700x600 piksel (büyütüldü)
- Resize edilebilir (minsize: 650x550)
- Mesaj içeriği için scrollbar eklendi

**Butonlar:**
1. **UYGUN - Devam Et**: İlaç bu mesaja rağmen verilebilir, reçete geçilir
2. **UYGUN DEĞİL - Manuel Kontrol**: İlaç bu mesaja göre uygun değil, manuel listeye eklenir
3. **KALICI YOK SAY**: Bu mesaj bir daha sorulmaz (kalıcı yok sayma)
4. **1 YIL YOK SAY**: Bu mesaj 1 yıl boyunca otomatik geçilir (geçici yok sayma)
5. **SONRA KONTROL - Algoritmik İşlem İçin İşaretle**: Bu mesaj için ileride algoritmik kontrol yapılacak

### 2. Mesaj İçeriği Scrollbar

**Değişiklikler:**
- Mesaj içeriği her zaman gösteriliyor (boşsa uyarı yazısı)
- Scrollbar ile uzun mesajlar kaydırılabiliyor
- Text widget height=8 satır, fill="both" expand=True ile boyutlanıyor
- Arka plan rengi #f5f5f5 (açık gri)

### 3. Yeni Dönüş Formatları

**ilac_mesaji_isle_ve_kaydet() dönüş değeri:**
```python
{
    "mesaj_basligi": str,
    "mesaj_icerigi": str veya None,
    "mesaj_kodu": str,
    "devam_et": bool,      # True=reçete geçilebilir
    "uygun_degil": bool,   # True=ilaç uygun değil
    "yok_say": bool,       # True=mesaj yok sayıldı
    "sonra_kontrol": bool, # True=algoritmik kontrol için işaretlendi (YENİ)
    "kayit_id": int,
    "esdeger_kodu": str
}
```

**mesaj_karar_dialog_goster() dönüş değeri:**
```python
{
    "karar": int,      # 0=Uygun, 1=Uygun değil, 2=Kalıcı yok say, 3=1 yıl yok say, 4=Sonra kontrol, -1=Timeout
    "devam_et": bool,  # True=reçeteyi geç
    "yok_say": bool,   # True=mesajı yok say
    "sure_yil": int,   # Yok sayma süresi (yıl) veya None=kalıcı
    "sonra_kontrol": bool  # True=algoritmik kontrol için işaretlendi (YENİ)
}
```

### 4. Rapor Durumları

Yeni rapor durumları:
- `MESAJLI_YOK_SAYILDI`: Mesaj otomatik geçildi
- `MESAJLI_UYGUN_DEGIL`: Kullanıcı "Uygun Değil" dedi
- `MESAJLI_SONRA_KONTROL`: Kullanıcı "Sonra Kontrol" dedi (YENİ)
- `MESAJLI`: Belirsiz veya timeout

### 5. Manuel Kontrol Kayıtları

Yeni kayıt türleri:
- `MESAJ_UYGUN_DEGIL {mesaj_kodu}`: Uygun değil
- `MESAJ_SONRA_KONTROL {mesaj_kodu}`: Sonra kontrol edilecek (YENİ)
- `MESAJ_BELIRSIZ {mesaj_kodu}`: Belirsiz/timeout

## Test Edilmesi Gerekenler

1. **5 Butonlu Dialog Testi:**
   - [ ] Dialog 700x600 boyutunda açılıyor mu?
   - [ ] Mesaj içeriği scrollbar ile kaydırılabiliyor mu?
   - [ ] UYGUN - reçete geçiliyor mu?
   - [ ] UYGUN DEĞİL - manuel kontrol listesine ekleniyor mu?
   - [ ] KALICI YOK SAY - bir daha sorulmuyor mu?
   - [ ] 1 YIL YOK SAY - database'de kayıt oluşuyor mu?
   - [ ] SONRA KONTROL - raporda MESAJLI_SONRA_KONTROL görünüyor mu?
   - [ ] TIMEOUT - manuel kontrol olarak işaretleniyor mu?

2. **Rapor Testi:**
   - [ ] MESAJLI_SONRA_KONTROL durumu raporda görünüyor mu?
   - [ ] Manuel kontrol listesinde MESAJ_SONRA_KONTROL kaydı oluşuyor mu?

## Syntax Durumu
Tüm değişiklikler syntax kontrol edildi - **HATA YOK**

## Değişen Dosyalar
- `botanik_bot.py`:
  - `mesaj_karar_dialog_goster()`: 5 buton, scroll, büyük pencere
  - `ilac_mesaji_isle_ve_kaydet()`: sonra_kontrol desteği
- `botanik_gui.py`:
  - Mesaj kontrol kısmı sonra_kontrol desteği
  - Rapor ilac_durumu MESAJLI_SONRA_KONTROL

## Önceki Düzeltmeler (6 Aralık 2025 - Güncelleme 7)

### Database Güncellemeleri
- `yok_say_bitis_tarihi` sütunu eklendi
- `yok_say` değerleri: 0=Hayır, 1=Kalıcı, 2=Belirsiz, 3=Geçici
- `mesaj_yok_say_guncelle()` geçici yok sayma desteği
- `mesaj_yok_sayilsin_mi()` süre kontrolü
