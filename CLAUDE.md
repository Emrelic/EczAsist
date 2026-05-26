# Proje: BotanikTakip

## 🚨 KIRMIZI ÇİZGİLER (asla aşılmaz)

1. **Botanik EOS (SQL Server) veritabanına ASLA yazma yapılmaz.** SADECE `SELECT`. Hiçbir koşulda, hiçbir akışta, hiçbir geçici çözümde `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/EXEC/EXECUTE/GRANT/REVOKE/DENY/BACKUP/RESTORE/SHUTDOWN/KILL` veya benzeri kayıt değiştiren/silen/ekleyen sorgu çalıştırılamaz. Bu kuralı geçici olarak bile esnetme önerisi getirilemez. Detay: §2.
2. **Medula reçete/rapor verisi ASLA değiştirilmez.** SADECE okuma + navigasyon. Detay: §1.
3. **Medula otomasyonunda koordinat tıklama YASAK** (`pyautogui.click(x, y)` asla). Detay: §3.

Bu üç kural, projenin var oluş şartıdır. Aksi davranış prod ortamında veri kaybı/tahribat anlamına gelir ve **kabul edilmez**.

## KRİTİK GÜVENLİK KURALLARI

### 1. Medula Reçete/Rapor Verileri — SADECE OKUMA
**YASAK:** veri değiştirme/ekleme/silme, E-Reçete Kaydet, İlaç Ekle/Sil, Reçete Sil, herhangi bir form alanına giriş, yeniden kaydetme.

**İZİNLİ:** element text okuma (window_text, DataItem), checkbox toggle (sadece okuma amaçlı), Rapor/Geri Dön/Sonraki/Önceki/İlaç Bilgi/Kapat/Sorgula tıklama (navigasyon ve görüntüleme).

Sistem sadece okur, kontrol eder, loglar.

### 2. 🚨 Botanik EOS Veritabanı (SQL Server) — SADECE SELECT (KIRMIZI ÇİZGİ)

**Bu kural mutlaktır. Hiçbir istisnası yoktur. Hiçbir geliştirme, hiçbir test, hiçbir "tek seferlik" gerekçe bunu esnetemez.**

#### Yasaklı komutlar (hiçbiri çalıştırılamaz)
`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `EXEC`, `EXECUTE`, `GRANT`, `REVOKE`, `DENY`, `BACKUP`, `RESTORE`, `SHUTDOWN`, `KILL` ve benzeri kayıtları **ekleyen, silen, değiştiren, şema/yetki/sistem durumu bozan** her komut.

#### İzinli olan tek şey
Sadece `SELECT` (alt sorgular dahil). Salt okuma. Veriyi ekrana getir, hesapla, raporla, yerel SQLite'a yaz — ama Botanik EOS'a **dokunma**.

#### Mimari guard
- **Tek meşru erişim noktası:** `botanik_db.py` içindeki `BotanikDB` sınıfı.
- `BotanikDB.sorgu_calistir()` her sorguyu `_guvenlik_kontrolu()` filtresinden geçirir; yasaklı komut bulursa **çalıştırmadan reddeder** ve loglar.
- **Yeni kod yazarken kural:** Botanik EOS'a erişim **yalnızca** `BotanikDB` üzerinden olur. `pyodbc.connect` ile doğrudan bağlanıp `cursor.execute` çağırmak (yani guard'ı bypass etmek) yasaktır. Tek istisna: `kurulum_wizard.py` içindeki bağlantı testi (sabit `SELECT COUNT(*)` ve `SELECT DB_NAME()` — kullanıcı girdisi yok).

#### Claude için davranış kuralı
- Kullanıcı Botanik EOS'a yazma yapan bir kod istese bile **YAPMA**. Önce kullanıcıya bu kuralı hatırlat, alternatif (yerel SQLite, raporlama, manuel Botanik UI) öner.
- "Sadece bir kerelik düzeltme", "test için", "geliştirme ortamında" gibi gerekçeler kuralı esnetmez.
- Botanik EOS DB'sinde herhangi bir veri düzeltmesi gerekiyorsa: **bu kullanıcının elle Botanik EOS UI'ı üzerinden yapacağı bir iştir**, kod yazma kapsamı dışındadır.

#### Yerel SQLite (serbest)
Yerel SQLite veritabanlarına (`oturum_raporlari.db`, `siparis_calismalari.db`, `kasa_kapatma.db`, `hasta_takip.db`, `kullanicilar.db`, `sut_kontrol.db`, vs.) `INSERT/UPDATE/DELETE/CREATE TABLE` serbesttir — bunlar EczAsist'in kendi yerel veritabanlarıdır, Botanik EOS değildir.

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

## ATOMİK DEVRE ŞEMASI PRENSİPLERİ (zorunlu — tüm SUT kontrollerinde uygulanır)

YOAK 4.2.15.D pilot uygulaması ile şekillenmiştir (commit `28b74b6`, 2026-05-08). Tüm SUT kontrolleri bu kalıba göre yazılır.

### 1. SUT lafzı → atomik şart üretimi
Her bir SUT ibaresi **bir atomik şart** = bir ampul. Birleştirme yapma:
- "inme veya TIA öyküsü" → 2 atomik (inme + TIA), VEYA grubunda
- "DM veya HT" → 2 atomik (DM + HT), VEYA grubunda
- "2 ay varfarin... son 5 ölçüm... 3'ünde tutulamadı... INR 2-3 hedef... varfarin kesildi" → 5+ atomik AND zincir

### 2. Mantık operatörleri (VE/VEYA/OLAN/OLMAYAN/parantez)

SUT lafzındaki bağlaçları **çok sıkı** çöz. Yanlış mantık = yanlış sonuç.

#### 2.1. Bağlaçlar
| SUT lafzı | Mantık |
|---|---|
| "ve" / virgül + ardışık liste | **AND** (hepsi) |
| "veya" / "ya da" | **OR** |
| "ile" (ardışık ibareler) | **AND** |
| "bir ya da daha fazlası" / "≥1" | **OR (≥1 yeterli)** |
| Paragraflar (a) / (b) | **OR** (alternatif yollar) |
| "yalnız" / "sadece" | **XOR** veya tek-seçenek |

#### 2.2. Olumlu/Olumsuz sıfat-fiil ekleri
| Türkçe | Mantık |
|---|---|
| "olan" / "olmuş" / "saptanmış" / "tespit edilmiş" | **POZİTİF** (VAR olmalı) |
| "olmayan" / "olamayan" / "olmayanlarda" | **NEGATİF** (NOT, YOK olmalı) |
| "yoksa" / "tespit edilmemişse" / "saptanmamışsa" | **NEGATİF** (NOT) |
| "değil" / "değilse" | **NEGATİF** (NOT) |
| "kontrendike" / "yasak" | **NEGATİF** (NOT) |

#### 2.3. Parantez ve operatör öncelik (Türkçe gramer)
SUT lafzında parantez nadir; sıralama ve sıfat-fiilin **kapsama alanı** kritik:

| Lafız | Doğru Yorum | Yanlış Yorum (kaçın!) |
|---|---|---|
| "(A VEYA B) OLMAYAN" | NOT(A OR B) = ¬A AND ¬B (DeMorgan) | A OR (NOT B) ✗ |
| "A VEYA B OLMAYAN" (parantezsiz) | "OLMAYAN" tüm listeyi kapsar → NOT(A OR B) | sadece B'yi kapsar ✗ |
| "A, B, C VEYA D durumlarından biri" | A OR B OR C OR D (≥1) | virgüller AND ✗ |
| "A olan, B olmayan, C'li hastalarda" | A=VAR AND B=YOK AND C=VAR (zincir) | virgüller OR ✗ |

#### 2.4. DeMorgan dönüşümü zorunlu
- `NOT (A OR B)` = `(NOT A) AND (NOT B)` ← her ikisi de YOK olmalı
- `NOT (A AND B)` = `(NOT A) OR (NOT B)` ← en az biri YOK olmalı

Örn: SUT "(orta-ciddi mitral darlık VEYA mekanik protez kapak) OLMAYAN" →
matematiksel olarak `mitral YOK AND mekanik YOK` (her ikisi YOK olmalı).

#### 2.5. Sessizlik = KONTROL_EDILEMEDI (örtük kabul yasağı)
Bir şartı NEGATİF parsing yaparken (örn. "mitral darlık YOK olmalı"):
- Rapor lafzen "mitral darlık olmayan/yok" diyorsa → ŞART VAR (lafzen ikrar)
- Rapor lafzen "mitral darlık var" diyorsa → ŞART YOK (kontrendikasyon)
- Rapor **sessiz** (mitral'dan bahsetmiyor) → **KONTROL_EDILEMEDI** (manuel)

**Yasak**: rapor sessiz olunca "şart sağlanıyor" varsayma — bu örtük kabuldür.
Memory: `feedback_sut_ortuk_kabul_yasak.md`.

#### 2.6. Parser üç-yönlü yapı (zorunlu kalıp)
```python
poz_var = _atom_pozitif_ibare(metin)     # "X var/saptandı"
neg_var = _atom_negatif_ibare(metin)     # "X yok/olmayan/saptanmadı"
if poz_var:
    durum = SartDurumu.YOK  # ya da VAR — kontrendikasyon mu, gerekli mi?
elif neg_var:
    durum = SartDurumu.VAR  # ya da YOK — tersi
else:
    durum = SartDurumu.KONTROL_EDILEMEDI  # sessiz, manuel doğrulama
```

### 3. Şart sırası SUT lafzına uymalı
SUT'ta hangi sırada yazılmışsa devre öyle akmalı:
- (1) ilk şart → ⊕'dan sonra ilk grup
- (4) son şart (örn. kombi yasağı) → ⊖'den önce son grup
- Erken çıkış (early-return) **YASAK** — tüm atomik şartlar üretilsin (kontrendikasyon olsa bile devam et)

### 4. Grup yapısı (`SartSonuc.grup`)
- Aynı SUT alt-maddesindeki şartlar tek grup adında
- Grup adında özel suffix:
  - `(bilgi)` → hesaplama dışı (parser zayıf, manuel doğrulama)
  - `[paralel]` → görsel paralel ama mantıksal AND (örn. "X VEYA Y OLMAYAN" — DeMorgan)
- `veya_grubu=True` → alt-OR mantığı (≥1 yeterli)
- `veya_grubu=False` (default) → AND (hepsi gerekir)

### 5. Üst-VEYA çiftleri (alternatif yollar)
Aynı seviyede 2 grup VEYA bağlı ise (örn. (a) yolu VEYA (b) yolu):
- `_yoak_genel_sonuc_atomik` içinde `ust_or_ciftleri` listesine prefix tanımla
- Çift gruplardan biri tam ise üst-OR VAR sayılır

### 6. Bilinemeyen şartlar (parser yetersiz) → KE + bilgi grubu
- "1 yıl rapor süresi" / "24 ay tamam" / "ölçümler ≥1 hafta arayla" gibi parse edilemeyen şartlar
- `SartDurumu.KONTROL_EDILEMEDI` ile işaretlenir
- `(bilgi)` suffix grupta tutulur → matematiği bozmaz, görsel olarak görünür

### 7. Görsel devre şeması (GUI yatay layout)
- ⊕ sol pil → seri/paralel ampuller → ⊖ sağ pil
- AND grup → seri (yatay aynı hatta)
- VEYA grup → paralel (Y kavşaklı dikey)
- Her ampul çerçeve içinde: ÜST=SUT lafzı (siyah), AMPUL=durum rengi, ALT=neden (renkli)
- Akım yolu: VAR ampullerden geçen kablo **yeşil kalın**, geçmeyen **gri ince**
- Renkler: VAR=yeşil, YOK(AND)=kırmızı, YOK(VEYA)=koyu gri, KE=sarı, bilgi=açık gri

### 8. Kullanıcı isteği üzerine eklenen / planlanan
- **Çoklu madde** (örn. D-1 + D-2): aynı şemada 2 ana yol paralel (aktif yolak renkli, diğeri pasif gri) — *planlandı*
- **Basit/Detaylı switch**: paralel grup kapanınca tek ampul + yan liste (✓/✗ ile) — *planlandı*
- **Ana yol göster/gizle switch**: kapalı = tek çizgi, açık = tüm detay — *planlandı*

### 9. Yeni kontrol yazarken kontrol listesi
1. SUT lafzını parça parça oku, her ibareyi atomik kabul et
2. VE/VEYA/NOT operatörlerini DeMorgan ile çöz
3. Atomik fonksiyon yaz (`_<kontrol>_atom_<sart>`) — her şart için ayrı
4. Dispatcher fonksiyon (`_<kontrol>_kontrol`) — atomikleri sırayla çağırır, `SartSonuc` listesi üretir
5. `_kontrol_raporunu_satira_yaz` veya inline çağrıda `verdict_sartlar` JSON'a yazıldığından emin ol
6. `grup` alanı + `veya_grubu` flag doğru → sema panel otomatik render eder
7. Akıl testi yaz: en az 5-10 senaryo (UYGUN / UYGUN_DEGIL / ŞÜPHELİ + edge case)

### 10. ⚠️ ZORUNLU: SUT mevzuat çözümleme protokolü
Yeni SUT kontrol / ilaç grubu implementasyonuna başlamadan **önce** mutlaka `docs/SUT_MANTIK_SEMA_PROTOKOLU.md` belgesini oku. Bu belge 7-adımlık metodolojiyi (SUT metni → yolak dispatcher → atomik tablo → DeMorgan → boolean formül → kullanıcı onayı → kod) ve YOAK SUT 4.2.15.D çalışılmış örneğini içerir. Bu protokole uymadan koda geçilmez; özellikle adım 1–6 "kod öncesi" tasarım aşamasıdır ve kullanıcı onayı şarttır. Pilot: YOAK D-1+D-2+EK-4/F (2026-05-11).

### 11. ⚠️ ZORUNLU: SUT lafzını resmî metinden oku (mevzuat.gov.tr)
Bir ilaç grubunun / SUT maddesinin kontrolünü yazmaya başlamadan **önce** mutlaka `docs/sut/SUT_tam_metin.txt` dosyasındaki **resmî SUT lafzını** oku. Hafızadan ya da örnek kodlardan SUT metni türetme **YASAK** — mevzuat değişebilir, ekleme/mülga ibareleri vardır.

- **Resmî kaynak**: mevzuat.gov.tr / SGK Sağlık Uygulama Tebliği (MevzuatNo=17229)
- **PDF**: `docs/sut/SUT_tam_metin.pdf` (resmî, indirme tarihi 2026-05-13)
- **TXT (grep/parse için)**: `docs/sut/SUT_tam_metin.txt` (UTF-8, ~10000 satır, layout korumalı)
- **Güncelleme**: Resmî metin güncellendiğinde yeniden indir: `curl -L -A "Mozilla/5.0" -o docs/sut/SUT_tam_metin.pdf "https://mevzuat.gov.tr/File/GeneratePdf?mevzuatNo=17229&mevzuatTur=Teblig&mevzuatTertip=5"` ardından `pdftotext -layout -enc UTF-8 docs/sut/SUT_tam_metin.pdf docs/sut/SUT_tam_metin.txt`

**Akış (zorunlu)**:
1. Kullanıcı "X ilaç grubunun kontrolünü implemente edelim" der.
2. `docs/sut/SUT_tam_metin.txt` içinde ilgili SUT maddesini grep ile bul (örn. `grep -nE "^\s*4\.2\.28" docs/sut/SUT_tam_metin.txt`).
3. Madde lafzını **resmî metinden** kullanıcıya tam olarak göster ve onayla.
4. Sonra adım 10'daki protokol (atomik tablo → DeMorgan → boolean formül → kod) işletilir.

Bu kural ezbere kontrol yazımını engeller; SUT'taki güncel "Ek ibare/Değişik/Mülga" değişiklikleri her zaman göz önündedir.

## Kullanıcı Kısaltmaları
- **\*sss** = "Soracağın soru var ise sor". Bu kısaltma görüldüğünde sorularımı sormalıyım.

## Detaylı Dokümanlar (gerektiğinde oku)
- `docs/sut/SUT_tam_metin.txt` — ⚠️ **Resmî SUT lafzı** (mevzuat.gov.tr, MevzuatNo=17229). Yeni ilaç grubu / SUT maddesi kontrolüne başlamadan **önce** ilgili madde buradan grep edilip kullanıcıya gösterilir (bkz. Atomik Devre Şeması Prensipleri §11). PDF orijinal: `docs/sut/SUT_tam_metin.pdf`.
- `docs/SUT_MANTIK_SEMA_PROTOKOLU.md` — ⚠️ **SUT kontrol implementasyonu için ZORUNLU metodoloji** (7-adım + YOAK çalışılmış örnek, insan-eli akış). Yeni SUT/ilaç grubu işlerinde mutlaka oku.
- `docs/SUT_AI_PROTOKOL_v1.md` — ⚠️ **AI-eli SUT→JSON v2→şema protokolü** (12-adım + Akut Hep B çalışılmış örnek, 2026-05-23). AI'nın SUT lafzını çözümleyip atomik JSON ürettiği ve sistemin **kod dokunmadan** şemayı otomatik çizdiği yeni pipeline. Yeni SUT kontrolü Python kodu yazmak yerine JSON üretmekle başlar.
- `sut_kurallari/v2/SCHEMA.md` — JSON v2 şema referansı (inline atom tipleri, dispatcher, üst-VEYA çiftleri, senaryolar).
- `recete_kontrol/sut_motor/motor_v2.py` — v2 motor (atomlar+formül string → SartSonuc). Pilot: `sut_kurallari/v2/akut_hepatit_b_4_2_13_3.json`. Test: `python test_hepatit_v2_pilot.py` (13/13 PASS). Demo: `python demo_v2_pipeline.py`.
- `KALDIGI_YER.md` — aktif modül geliştirme durumları (reçete kontrol, MF analiz, vs.)
- `MF_ANALIZ_MODULU_SPEC.md` — MF analiz modülü detayları
- `RECETE_ISLEME_SEMASI.md` — reçete işleme akışı
- `docs/FINANSMAN_PRENSIPLER.md` — sipariş/stok/zam/MF için finansal prensipler (sipariş modülü işlerinde yükle)
- `YAPILACAKLAR.md` — todo listesi

## Planlanan Modüller (Özet)
- **Ay Sonu Reçete Kontrol:** ayrı sekme, 4 grup butonu (C/A/GK/B) + "Hepsini Kontrol Et"
- **Kullanıcı Yetkilendirme:** Eczacı/Personel ayrımı, manuel kasa girişi gibi işlemler eczacıya özel (ileri tarih)
