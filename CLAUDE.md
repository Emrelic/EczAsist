# Proje: BotanikTakip

## Kullanıcı Kısaltmaları

- **\*sss** = "Soracağın soru var ise sor" anlamına gelir. Kullanıcı bu kısaltmayı kullandığında, varsa sorularımı sormalıyım.

## Modül Bilgileri

### Ay Sonu Reçete Kontrol Modülü (Planlanan)
- Ayrı bir sekme olacak
- 4 grup butonu: C, A, GK (Geçici Koruma), B - bu sırayla
- 5. buton: "Hepsini Kontrol Et" - 4 grubu sırayla kontrol eder
- İlaç takip modülündeki buton stili kullanılacak

### Reçete Kontrol Modülü (AKTİF GELİŞTİRME - 2026-01-17)

**KALDIĞIMIZ YER:**
İlaç tablosu kontrol fonksiyonları yazıldı ve ana akışa entegre edildi. TEST EDİLMEDİ.

**Tamamlanan:**
1. Renkli reçete kontrolü (Yeşil/Kırmızı reçetelerin sisteme işlenip işlenmediği)
2. Ana ekranda "Renkli Reçete Yükle" butonu (Excel/PDF/Manuel yükleme)
3. İlaç tablosu kontrol fonksiyonları:
   - `ilac_tablosu_satir_sayisi_oku()` - Tablodaki satır sayısı
   - `ilac_satiri_msj_oku()` - Msj sütunu (var/yok)
   - `ilac_satiri_rapor_kodu_oku()` - Rapor kodu (04.05 vb.)
   - `ilac_satiri_checkbox_sec()` - Checkbox seçimi
   - `ilac_bilgi_butonuna_tikla()` - İlaç Bilgi butonu
   - `ilac_bilgi_penceresi_mesaj_oku()` - Mesaj metni okuma
   - `ilac_bilgi_penceresi_raporlu_doz_oku()` - Raporlu maks doz
   - `ilac_bilgi_penceresi_kapat()` - Pencere kapatma
   - `tum_ilaclari_kontrol_et()` - Ana kontrol fonksiyonu

**Yapılacak:**
1. TEST - Fonksiyonların çalışıp çalışmadığını test et
2. Reçete dozu okuma fonksiyonu (`ilac_satiri_recete_doz_oku`) tamamlanacak
3. Doz karşılaştırma mantığı (reçete dozu ≤ rapor dozu kontrolü)
4. Hata durumlarında kullanıcıya bildirim

**Element ID'leri:**
- Msj sütunu: `f:tbl1:{satır}:t11`
- Rapor sütunu: `f:tbl1:{satır}:t9`
- Checkbox: `f:tbl1:{satır}:checkbox7`
- İlaç Bilgi butonu: `f:buttonIlacBilgiGorme`
- Mesaj textarea: `form1:textarea1`
- Kapat butonu: `form1:buttonKapat`

### Kullanıcı Giriş ve Yetkilendirme Sistemi (TODO - İleri Tarih)
- Programa girilirken kullanıcı girişi olacak
- İki kullanıcı tipi: **Eczacı** ve **Personel**
- Kullanıcı oluşturma, şifre belirleme ekranları
- Kullanıcı profilleri ve yetki alanları
- Bazı işlemler sadece eczacı yapabilecek:
  - Manuel başlangıç kasası girişi
  - Diğer kritik işlemler (belirlenecek)
- Geniş bir implementasyon gerektirir, detaylı planlama yapılmalı
