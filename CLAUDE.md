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
