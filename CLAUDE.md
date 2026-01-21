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

### MF Analiz Modülü - Botanikten Çek (AKTİF GELİŞTİRME - 2026-01-21)

**KALDIĞIMIZ YER:**
Fiyat farkı veritabanından alınacak şekilde güncellendi. Test edilmedi.

**Tamamlanan:**
1. Eşdeğer grup bazlı ilaç arama (`mf_esdeger_ilaclar_getir`)
2. İlaç fiyat detayları (`mf_ilac_fiyat_detay_getir`)
   - PSF, Kamu Fiyatı, Stok
   - Depocu Fiyat: PSF × 0.71 × 1.10 × (1 - İskonto/100)
   - Fiyat Farkı: ReceteIlaclari.RIFiyatFarki'dan son kayıt
3. Aylık satış verileri (`mf_aylik_satis_getir`) - RxKayitTarihi bazlı
4. Tek ilaç seçimi için "Fiyat İçin Seç" butonu
5. Konsolidasyon tablosu (tksheet)

**Yapılacak:**
1. TEST - Fiyat farkı doğru gelip gelmediğini test et (AUGMENTIN 1000mg için ~24.21 TL olmalı)
2. Konsolidasyon sonrası ana panele aktarım butonu (Stok Toplam + Aylık Ortalama Gidiş)
3. Eczane profili parametreleri (SONA BIRAKILDI)

**Fiyat Formülleri:**
- Depocu (KDV Hariç) = PSF × 0.71
- Depocu (KDV Dahil) = Depocu × 1.10
- Depocu (İskontolu) = Depocu (KDV Dahil) × (1 - UrunIskontoKamu/100)
- Fiyat Farkı = ReceteIlaclari.RIFiyatFarki (veritabanından)

**Veritabanı Bilgileri:**
- UrunIskontoKamu: Kamu iskonto yüzdesi
- UrunIskontoYedek: Depocu Fiyat (KDV Hariç) - 113.19 gibi
- ReceteIlaclari.RIFiyatFarki: İlaç fiyat farkı (her reçete satırı için)
- RxKayitTarihi: Reçete kayıt tarihi (aylık satış için kullanılır)

### Kullanıcı Giriş ve Yetkilendirme Sistemi (TODO - İleri Tarih)
- Programa girilirken kullanıcı girişi olacak
- İki kullanıcı tipi: **Eczacı** ve **Personel**
- Kullanıcı oluşturma, şifre belirleme ekranları
- Kullanıcı profilleri ve yetki alanları
- Bazı işlemler sadece eczacı yapabilecek:
  - Manuel başlangıç kasası girişi
  - Diğer kritik işlemler (belirlenecek)
- Geniş bir implementasyon gerektirir, detaylı planlama yapılmalı
