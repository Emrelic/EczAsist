# Proje: BotanikTakip

## KRİTİK GÜVENLİK KURALLARI

### 1. Medula Reçete/Rapor Verileri — SADECE OKUMA
**YASAK:** veri değiştirme/ekleme/silme, E-Reçete Kaydet, İlaç Ekle/Sil, Reçete Sil, herhangi bir form alanına giriş, yeniden kaydetme.

**İZİNLİ:** element text okuma (window_text, DataItem), checkbox toggle (sadece okuma amaçlı), Rapor/Geri Dön/Sonraki/Önceki/İlaç Bilgi/Kapat/Sorgula tıklama (navigasyon ve görüntüleme).

Sistem sadece okur, kontrol eder, loglar.

### 2. Botanik EOS Veritabanı (SQL Server) — SADECE SELECT
Yasaklı: `INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, EXEC, EXECUTE, GRANT, REVOKE, DENY, BACKUP, RESTORE, SHUTDOWN, KILL`. `botanik_db.py` bu komutları engeller.

Yerel SQLite DB'lere (`oturum_raporlari.db`, `siparis_calismalari.db`) yazma serbest.

### 3. Medula Otomasyon — Koordinat Tıklama YASAK
`pyautogui.click(x, y)` ile element tıklama **asla** yapılmaz (Medula elementleri y=0,x=0'da görünür, koordinat güvenilmez).

Doğru yöntem:
- Buton/menü → `elem.invoke()`
- Combobox → `elem.click_input()` + `pyautogui.press("up/down/enter")`
- Checkbox → `elem.click_input()`
- pyautogui sadece klavye için (`press`, `hotkey`) — tıklama için asla.

## SUT KONTROL DİSİPLİNİ (zorunlu prensip)

Reçete/rapor SUT kontrolü implementasyonlarında bu prensibe **kesinlikle** uyulur. Disiplinli ve titiz olunur, eksik/yüzeysel kontrol yapılmaz.

### Kapsam: Şart taraması nereden yapılır?
Bir SUT maddesindeki **her şart**, aşağıdaki tüm kaynaklarda taranarak değerlendirilir:
- Aktif reçete metni ve kalemleri (`diger_ilac_adlari` — eş-zamanlı yazılmış ilaçlar dahil)
- Aktif rapor metni (`tum_metin`, teşhisler, etken madde bilgisi)
- Hastanın diğer reçeteleri ve raporları (oturum DB / hasta geçmişi)
- Hastanın ilaç geçmişi (önceki tedavi denemeleri, kombinasyonlar)
- Hasta özellikleri: yaş, cinsiyet, kilo, boy, BMI, TC
- Doktor bilgileri: branş, tesis kodu, sağlık kurulu olup olmadığı
- Teşhisler (`teshis_tum`, ICD kodları)

### Şart başına 3 sınıf
Her bir şart için kod, **3 sonuçtan birini** üretmeli:
1. **VAR / SAĞLANIYOR** — şart kaynaklarda bulundu ve uygun
2. **YOK / SAĞLANMIYOR** — şart kaynaklarda arandı, sağlanmadığı NET
3. **KONTROL EDİLEMEDİ** — şart metin parse'ı ile sorgulanamadı / kaynak veride yok / belirsiz (manuel doğrulama gerekli)

"Kontrol edilemedi" sessizce "VAR" sayılmaz. Şüpheli durumda UYGUN denmez.

### Genel sonuç (3 etiket)
Tüm şartlar değerlendirildikten sonra reçete için:
- **UYGUN** — tüm zorunlu şartlar VAR; KONTROL_EDİLEMEDİ yok
- **ŞÜPHELİ** — bazı şartlar KONTROL_EDİLEMEDİ; UYGUN_DEĞİL şart yok (manuel doğrulama gerekli)
- **UYGUN DEĞİL** — en az bir zorunlu şart YOK/SAĞLANMIYOR

### Raporlama formatı (zorunlu)
Çıktıda mutlaka şu gruplandırma olmalı:
- ✓ **Sağlanan şartlar:** (liste)
- ✗ **Sağlanmayan şartlar:** (liste, neden ile)
- ? **Kontrol edilemeyen şartlar:** (liste, "manuel doğrulanmalı" notu ile)
- **Genel sonuç:** UYGUN / ŞÜPHELİ / UYGUN DEĞİL

10 şart varsa 10'u da raporda görünmeli; "5 var → uygun" gibi yüzeysel özet kabul edilmez.

### Yasaklar
- Sadece BMI + rapor kodu + branş gibi yüzeysel şartları kontrol edip madde içi alt şartları atlamak
- Bir şartı sorgulayamayınca sessizce UYGUN dönmek
- "VEYA"lı alternatif şıklarda sadece birini kontrol edip diğerlerini görmezden gelmek
- Kombinasyon şartlarını (`diger_ilac_adlari` ile) atlamak

Detaylı uygulama için `feedback_sut_kontrol_tum_sartlar.md` memory'sine bakılır.

## Kullanıcı Kısaltmaları
- **\*sss** = "Soracağın soru var ise sor". Bu kısaltma görüldüğünde sorularımı sormalıyım.

## Detaylı Dokümanlar (gerektiğinde oku)
- `KALDIGI_YER.md` — aktif modül geliştirme durumları (reçete kontrol, MF analiz, vs.)
- `MF_ANALIZ_MODULU_SPEC.md` — MF analiz modülü detayları
- `RECETE_ISLEME_SEMASI.md` — reçete işleme akışı
- `docs/FINANSMAN_PRENSIPLER.md` — sipariş/stok/zam/MF için finansal prensipler (sipariş modülü işlerinde yükle)
- `YAPILACAKLAR.md` — todo listesi

## Planlanan Modüller (Özet)
- **Ay Sonu Reçete Kontrol:** ayrı sekme, 4 grup butonu (C/A/GK/B) + "Hepsini Kontrol Et"
- **Kullanıcı Yetkilendirme:** Eczacı/Personel ayrımı, manuel kasa girişi gibi işlemler eczacıya özel (ileri tarih)
