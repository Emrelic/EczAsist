# Proje: BotanikTakip

## KRİTİK GÜVENLİK KURALI - VERİTABANI ERİŞİMİ

### Botanik EOS Veritabanı (SQL Server)
**SADECE SELECT SORGUSU ÇALIŞTIRILABİLİR!**

Aşağıdaki işlemler **KESİNLİKLE YASAKTIR:**
- `INSERT` - Yeni kayıt ekleme
- `UPDATE` - Kayıt güncelleme
- `DELETE` - Kayıt silme
- `ALTER` - Tablo/yapı değiştirme
- `DROP` - Tablo/veritabanı silme
- `CREATE` - Yeni tablo/yapı oluşturma
- `TRUNCATE` - Tablo temizleme
- `EXEC/EXECUTE` - Prosedür çalıştırma
- Diğer tüm veri değiştirme komutları

**Neden?**
- Botanik EOS eczanenin ana iş sistemidir
- Veri bütünlüğü kritik önem taşır
- Yanlış bir UPDATE/DELETE geri dönüşü olmayan hasara yol açabilir
- Sadece Botanik EOS programının kendisi veritabanını değiştirebilir

**Yerel SQLite Veritabanları (İzin Verilen):**
- `oturum_raporlari.db` - Bot oturum kayıtları
- `siparis_calismalari.db` - Sipariş çalışmaları
- Bunlara INSERT/UPDATE/DELETE yapılabilir

**botanik_db.py Güvenlik Kontrolü:**
```python
YASAKLI_KOMUTLAR = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
    'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE', 'DENY',
    'BACKUP', 'RESTORE', 'SHUTDOWN', 'KILL'
]
```

---

## KRİTİK KURAL - MEDULA OTOMASYON

### Koordinat Bazlı Tıklama KESİNLİKLE YASAKTIR!

`pyautogui.click(x, y)` ile element tıklama **ASLA YAPILMAZ**. Medula web elementleri y=0,x=0 pozisyonunda görünür, koordinat güvenilmez.

**Doğru yöntemler:**
- Menü linkleri / Butonlar → `elem.invoke()`
- Combobox → `elem.click_input()` + `pyautogui.press("up/down/enter")`
- Checkbox → `elem.click_input()`
- pyautogui SADECE keyboard için: `press()`, `hotkey()` - tıklama için ASLA

---

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

---

## Eczane Finansman Sistemi (TEMEL PRENSİPLER)

Bu bölüm, sipariş verme ve stok optimizasyonu modüllerinin temelini oluşturan finansal prensipleri açıklar.

### Ödeme ve Tahsilat Döngüsü

#### Depo Ödemeleri (Senet)
- Ayın 1-31'i arasında depodan alınan mallar için **sonraki ayın 1'inde senet kesilir**
- Senet, kesildiği tarihten **75 gün sonra** tahsil edilir
- Örnek: 1-31 Ocak alımları → 1 Şubat senet → **17 Nisan ödeme** (yaklaşık)

#### SGK Tahsilatı (Fatura)
- Ayın 1-31'i arasında SGK'lı hastalara satılan ilaçlar için **sonraki ayın 1'inde fatura kesilir**
- Faturadan **75 gün sonra** SGK ödemeyi yapar
- Örnek: 1-31 Ocak satışları → 1 Şubat fatura → **17 Nisan tahsilat**

#### İdeal Durum Prensibi
**Ay içinde alınan malların ay içinde satılması idealdir.**
- Bu durumda depo ödemesi ve SGK tahsilatı aynı günde denk gelir
- Stok maliyeti / finansman gereği oluşmaz
- Nakit akışı dengelenir

### Stok Yapmanın Geçerli Sebepleri

Malların ertesi aya sarkmasının **üç meşru gerekçesi** vardır:

#### 1. Zam Beklentisi
- Zam öncesi alınan ilaçlar daha ucuza mal edilir
- **ANCAK:** Erken ödeme nedeniyle finansman maliyeti oluşur
- Sipariş miktarı arttıkça kar önce artar, **pik noktasına** ulaşır, sonra azalır
- Fazla stok yapıldığında kar zarara dönebilir

#### 2. Mal Fazlası (MF) Kampanyaları
- 5+1, 10+3, 20+7, 100+30 gibi oranlarla ilaç daha ucuza gelir
- **ANCAK:** Fazla stok finansman maliyeti yaratır
- MF oranları kademeli artabilir (5+1 → 10+3 → 20+7 → 50+20 → 100+50)
- Her kademe için karlılık analizi yapılmalı

#### 3. İlaç Yokluğu Riski
- İlaç piyasadan çekilecekse önceden stok yapılabilir
- "Şu tarihe kadar ihtiyacı hesapla" özelliği bu amaçla kullanılır

### Stok Maliyeti Hesaplama Mantığı

#### Örnek Senaryo
- Ayın 10'u, elimizde 10 adet, aylık gidiş 30 adet
- 100+30 MF ile alım yapılıyor (130 adet)

| Dönem | Miktar | SGK Tahsilat Gecikme | Finansman Maliyeti |
|-------|--------|---------------------|-------------------|
| Bu ay (20 adet) | 20 | 75 gün | Yok (normal) |
| 1. ay sonrası | 30 | 105 gün | 1 ay |
| 2. ay sonrası | 30 | 135 gün | 2 ay |
| 3. ay sonrası | 30 | 165 gün | 3 ay |
| 4. ay (20 gün) | 20 | 195 gün | 4 ay |

#### NPV (Net Bugünkü Değer) Prensibi
MF'li/zamdan önce toplu alım ile ay be ay alımın karşılaştırılması:
- Her dönemin ödemesi bugüne faiz oranı kadar **indirgenir**
- İndirgenmiş nakit akışları karşılaştırılır
- Pozitif fark = Stok yapmanın avantajı

### Karar Noktaları (Sipariş Miktarı Belirleme)

Zam veya MF durumunda **artan sipariş miktarının avantajı bir noktadan sonra azalır:**

1. **Verimlilik Noktası (Maksimum ROI):** Her 100 TL yatırım için en yüksek getiri
2. **Pareto Noktası (%80 Kazanç):** Toplam potansiyel kazancın %80'ine ulaşılan miktar
3. **Optimum/Pik Noktası:** Maksimum mutlak kazancın elde edildiği miktar
4. **Sınır Noktası:** Karlılığın sıfıra düştüğü, bundan sonra zarar başlayan miktar

### Sipariş Verme Modülü Çalışma Mantığı

#### Varsayılan Hesaplama (Parametre seçilmemiş)
1. Ay sonuna kadar ihtiyaç hesaplanır
2. Mevcut stok düşülür
3. Net sipariş miktarı belirlenir

#### Minimum Tutar Kontrolü
- Hesaplanan miktar minimum tutarın altındaysa, minimum tutara tamamlanır

#### Hedef Tarih Seçeneği
- Belirtilen tarihe kadar ihtiyaç hesaplanır
- Stok düşülerek sipariş oluşturulur

#### Zam Optimizasyonu
- Zam oranı ve tarihi girilir
- Sistem, pareto/optimum/verimlilik noktalarından birini referans alarak optimal sipariş miktarını hesaplar
- Zam avantajı ile stok maliyeti dengelenir

#### MF Analizi
- Her MF şartı için karlılık hesaplanır (5+1, 10+3, 20+7 vb.)
- 100 TL başına avantaj hesaplanarak en karlı MF belirlenir
- Zam tarihi ile birlikte değerlendirilebilir

### Formüller

#### Günlük/Aylık İskonto
```
Günlük faiz = (1 + yıllık_faiz/12)^(1/30) - 1
NPV = Ödeme / (1 + günlük_faiz)^gün_sayısı
```

#### MF Birim Maliyet
```
Birim_maliyet = (Alınan × Fiyat) / (Alınan + Bedava)
Örnek: 100+30 MF, 100 TL fiyat → 10000/130 = 76.92 TL/adet
```

#### Stok Finansman Maliyeti
```
Maliyet = Stok_değeri × (gün/365) × faiz_oranı
```
