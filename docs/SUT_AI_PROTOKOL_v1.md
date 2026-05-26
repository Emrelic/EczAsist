# SUT → AI Çözümleme → JSON v2 → Otomatik Şema Protokolü (v1)

> **Bu belge AI'nın (Claude'un) her yeni SUT maddesi / ilaç grubu için izleyeceği zorunlu protokoldür.**
>
> Çıktı: tek bir JSON v2 dosyası. Bu dosya `sut_motor_v2`'ye verildiğinde **kod dokunmadan** akım şeması otomatik üretilir.
>
> İlke: AI mantığı kurar; insan onaylar; sistem çizer.
>
> Pilot: SUT 4.2.13(3) Akut Hepatit B (2026-05-23). Çalışılmış örneği için bkz. §13.
>
> Referanslar:
> - CLAUDE.md `ATOMİK DEVRE ŞEMASI PRENSİPLERİ` §1–11 (kurallar)
> - `docs/SUT_MANTIK_SEMA_PROTOKOLU.md` (insan-eli 7-adım metodoloji, YOAK çalışılmış örneği)
> - `sut_kurallari/v2/SCHEMA.md` (JSON v2 şema referansı)
> - `recete_kontrol/sut_motor/motor_v2.py` (yorumlayıcı)

---

## AMAÇ

AI bu protokolü izleyerek:
1. Verilen SUT lafzını **resmî metinden** okur ve çözümler
2. Lafzı atomik şartlara ayırır, numaralar (A1, A2, B1, ...)
3. Atomları VE/VEYA/NOT mantığı + dispatcher ile birleştirip **boolean formül** üretir
4. Formülün lafza uygunluğunu kontrol eder
5. Kullanıcı onayı alır (\*sss)
6. Tek bir JSON v2 dosyası üretir
7. ≥5 senaryo testiyle doğrular

JSON v2 dosyası sisteme verildiğinde:
- `motor_v2` formülü çalıştırır → `SartSonuc` listesi
- GUI Canvas otomatik AND→seri, VEYA→paralel devre şemasını çizer

---

## ÖNKOŞULLAR (her zaman doğrulanmalı)

| # | Önkoşul | Neden |
|---|---|---|
| 1 | `docs/sut/SUT_tam_metin.txt` mevcut | Resmî mevzuat kaynağı (mevzuat.gov.tr) |
| 2 | `sut_kurallari/v2/SCHEMA.md` okunmuş | JSON v2 formatını biliyorum |
| 3 | `recete_kontrol/sut_motor/atomlar.py` taranmış | Mevcut atom kütüphanesi + inline tipler |
| 4 | Pilot SUT madde numarası belirli | Hangi maddeyi yazıyorum? |

---

## 12 ADIMLI PROTOKOL

Her adım atlanmaz. Özellikle adım 6 ve 11 **kullanıcı onayı zorunlu** kapılarıdır.

---

### ADIM 1 — Resmî SUT lafzını oku

**Yap:**
- `grep -nE "^\s*<MADDE_NO>" docs/sut/SUT_tam_metin.txt` ile madde başlangıcını bul
- Madde + tüm alt fıkralarını + EK-4/F gönderimlerini topla
- Lafzı **kullanıcıya ham metin olarak göster** ve "bu madde mi?" diye onayla

**YAPMA:**
- Hafızadan SUT metni türetme
- "Genelde böyle olur" tahmininde bulunma
- Mevzuat değişebilir; ezberden çalışma

**Çıktı:**
```
SUT <kod> tam metni (satır X-Y):
> "..." (kopyala)
```

---

### ADIM 2 — Mülga, Değişik, Ek ibarelerini işaretle

**Yap:**
- "Mülga:RG-..." işaretli fıkralar → **kontrol dışı** (atom üretme)
- "Değişik:RG-...", "Ek:RG-..." → güncel yürürlüktedir, kullan
- "Ek cümle", "Ek ibare" → ana lafza dahildir
- Mülga listesini ayrıca raporla

**Çıktı:**
```
Yürürlükteki fıkralar: (1), (3), (4), (5)
Mülga (kontrol dışı): (2) — RG-25/8/2022 ile kaldırıldı
```

---

### ADIM 3 — Yolak (dispatcher) sayısını belirle

**Soru:** Bu ilaç grubu **tek bir endikasyon** mu, yoksa **birden çok ayrı yolak** mı?

- Tek yolak → Adım 4'e doğrudan geç
- Çoklu yolak (örn. YOAK D-1/D-2/EK-4F) → Her yolak için ayrı atomik tablo + üst dispatcher

**Dispatcher sinyalleri (öncelik sırası):**
1. `rec_rap_kod` (reçeteye bağlı rapor kodu) — en güçlü
2. Teşhis ICD-10 kodları
3. Rapor metni anahtar ibareleri
4. Doktor branşı / yaş / miktar / form

**Çıktı:**
```json
"dispatcher": {
  "yolak_sayisi": 3,
  "sinyaller": [
    {"oncelik": 1, "kaynak": "rec_rap_kod", "kural": "AF rapor kodu → D-1"},
    {"oncelik": 2, "kaynak": "icd", "kural": "I48.x → D-1, I26.x → D-2"}
  ],
  "belirsiz_default": "KONTROL_EDILEMEDI"
}
```

---

### ADIM 4 — Atomik şart tablosunu çıkar

SUT lafzındaki **her ibare** bir satır. Tablo formatı:

| # | Atom adı | Kaynak | Operatör | Sessiz default | Bilgi mi? |
|---|---|---|---|---|---|
| A1 | İnme öyküsü VAR | rapor+teşhis | OR-grup1 (≥1) | YOK | Hayır |
| B1 | Mitral darlık YOK | rapor | AND-grup2 (NOT) | **KE** | Hayır |
| F4 | Rapor süresi 1 yıl | rapor | (bilgi) | KE | **Evet** |

**Her atom için zorunlu alanlar:**

| Alan | Açıklama | Örnek |
|---|---|---|
| `ad` | Kısa açıklayıcı isim | "İnme öyküsü VAR" |
| `tip` | Inline atom tipi (bkz. §11 atom tipleri) | `regex`, `icd_in`, `lab_olcum`, `doktor_brans`, ... |
| `params` | Tipe özel parametreler | `{"icd": ["I60","I61"]}` |
| `kaynak` | Hangi veride aranacak | `rapor_metni`, `teshis`, `hasta_yasi`, ... |
| `sessizlik_default` | Veri sessizse ne olsun | `YOK`, `VAR`, `KE` |
| `bilgi` | Matematiği bozmasın mı? | `true` (sema'da görünür ama verdict'i etkilemez) |

**Sessizlik default kuralı (CLAUDE.md §2.5):**
- POZİTİF atom ("X olmalı") + rapor sessiz → genelde `YOK`
- NEGATİF atom ("X olmayan") + rapor sessiz → **mutlaka `KE`** (örtük kabul yasak)
- Lab değer ("X ≥ 5") + sayı yok → `KE`
- Bilgi atomu (süre/tarih) → `KE` + `bilgi=true`

---

### ADIM 5 — Atomları numarala

**Kural:**
- Tek yolak: `A1, A2, ..., B1, B2, ..., C1, ...` (her grup farklı harf)
- Çoklu yolak: yolak prefix'i + atom numarası → `D1-A1, D1-A2, D2-A1, ...`
- Bilgi atomları farklı harf almaz, normal numara + `bilgi=true` flag

**Grup organizasyonu:**
- Aynı mantıksal gruptaki atomlar aynı harf altında (örn. risk faktörleri hepsi A)
- Kontrendikasyon atomları ayrı harf (örn. B)
- Endikasyon ayrı harf (örn. C)
- Heyet/rapor şartları ayrı harf (örn. F)

---

### ADIM 6 — Operatör çözümleme (VE/VEYA/NOT/Parantez/DeMorgan)

**SUT lafzındaki bağlaçları sıkı çöz:**

| SUT lafzı | Mantık |
|---|---|
| "ve" / virgül liste | AND (hepsi) |
| "veya" / "ya da" | OR |
| "bir ya da daha fazlası" / "≥1" | OR (≥1 yeterli) |
| Paragraflar (a)/(b) | OR (alternatif yollar) |
| "olan/olmuş/saptanmış" | POZİTİF (VAR olmalı) |
| "olmayan/yok/değil/kontrendike" | NEGATİF (NOT) |
| "yalnız/sadece" | XOR / tek seçenek |

**DeMorgan zorunlu:**
- `NOT (A OR B)` = `(NOT A) AND (NOT B)` ← her ikisi de YOK olmalı
- `NOT (A AND B)` = `(NOT A) OR (NOT B)` ← en az biri YOK olmalı

Parantezsiz "OLMAYAN" tüm listeyi kapsar: **"A VEYA B olmayan"** = `¬A ∧ ¬B`.

**Muğlak lafız:** "A ya da B ve C" → VE/VEYA önceliği belirsizse adım 8'de **kullanıcıya sor**.

---

### ADIM 7 — Boolean formülü yaz

Atomları VE/VEYA/NOT ile birleştirip okunaklı formül üret. Operatör glyph'leri:
- `∧` (AND) ya da yazıyla "AND"
- `∨` (OR) ya da yazıyla "OR"
- `¬` (NOT) ya da yazıyla "NOT"

**Örnek YOAK D-1:**
```
D1_UYGUN ⇔ (A1 ∨ A2 ∨ A3 ∨ A4 ∨ A5 ∨ A6) ∧ (B1 ∧ B2) ∧ C1 ∧ (D-a ∨ D-b) ∧ (F1 ∧ F2 ∧ F3) ∧ (F5a ∨ F5b) ∧ G1
```

**Üst-VEYA çiftleri varsa ayrıca metadata olarak listele:**
```
ust_or_ciftleri:
  - ["D-a", "D-b", "Geçiş yolu [(a) VEYA (b)]"]
```

---

### ADIM 8 — Kullanıcı onay kapısı #1 (atom tablosu + formül)

**Bu adım atlanmaz.** Kod yazmadan önce kullanıcıya sun:

```
📋 SUT <kod> — atomik çözümleme

Yolak sayısı: <N>
Dispatcher kuralı: <açıklama>

Atom tablosu:
| # | Ad | Kaynak | Tip | Sessiz | Bilgi |
| A1 | ... | ... | regex | YOK | - |
| B1 | ... | ... | regex_negatif | KE | - |
...

Boolean formül:
<formül>

Açık sorular:
1. "INR≥1,5 veya PT… ve sarılık" — VE/VEYA önceliği nasıl?
2. ...

Onayınız?
```

**Kullanıcı yanıtı:**
- Onay (\*sss yok) → Adım 9'a geç
- Düzeltme → Adım 4-7 arası geri dön, tabloyu güncelle
- Açık soruya yanıt → formüle dahil et

---

### ADIM 9 — JSON v2 dosyasını üret

`sut_kurallari/v2/<madde_kebab>.json` dosyası yaz. Şema için: `sut_kurallari/v2/SCHEMA.md`.

**Minimum zorunlu alanlar:**

```json
{
  "schema_version": "v2",
  "sut_kodu": "4.2.X",
  "adi": "<insan-okur ad>",
  "sut_kurali_etiketi": "<görsel mesaj>",
  "sut_metni_kaynak": "docs/sut/SUT_tam_metin.txt:satır-X",
  "sut_metni": "<resmî lafız tam metin>",
  "_yorum": "<kısa açıklama>",
  "atomlar": {
    "A1": {
      "ad": "...",
      "tip": "regex",
      "params": {"desenler": ["..."], "etiket": "..."},
      "kaynak": "rapor_metni",
      "sessizlik_default": "YOK",
      "neden_var": "...",
      "neden_yok": "..."
    }
  },
  "formul": "(A1 ∨ A2) ∧ ¬B1 ∧ C1",
  "ust_or_ciftleri": [],
  "verdict_eslemesi": {
    "VAR": "UYGUN",
    "YOK": "UYGUN_DEGIL",
    "KE": "ŞÜPHELİ"
  },
  "on_kontrol": [],
  "senaryolar": [
    {"ad": "Tam UYGUN", "ilac_sonuc": {...}, "beklenen_verdict": "UYGUN"},
    ...
  ]
}
```

Çoklu yolak için:
```json
{
  "dispatcher": {...},
  "yolaklar": {
    "D-1": {"atomlar": {...}, "formul": "..."},
    "D-2": {"atomlar": {...}, "formul": "..."}
  }
}
```

---

### ADIM 10 — Senaryo testlerini yaz

**Asgari 5 senaryo, ideali 8-10:**

| # | Senaryo | Beklenen verdict |
|---|---|---|
| 1 | Tüm şartlar tam, kanıt net | UYGUN |
| 2 | Bir zorunlu (AND) şart eksik | UYGUN_DEGIL |
| 3 | VEYA grubunda en az 1 şart var | UYGUN |
| 4 | NEGATİF atom + rapor sessiz | ŞÜPHELİ (KE) |
| 5 | Lab değeri yok | ŞÜPHELİ |
| 6 (edge) | Boş rapor | ŞÜPHELİ ya da UYGUN_DEGIL |
| 7 (edge) | Kontrendikasyon var | UYGUN_DEGIL (TIBBEN) |
| 8 (edge) | Bilgi atomu KE ama zorunlular tam | UYGUN |

Senaryolar JSON dosyasının kendisinde `"senaryolar": [...]` altında yer alır → `pytest` ile otomatik koşar.

---

### ADIM 11 — Verdict eşleme + erken çıkış kuralları

**Default eşleme (motor_v2'de built-in):**
- Formül kök VAR → `UYGUN`
- Formül kök YOK → `UYGUN_DEGIL`
- Formül kök KE → `ŞÜPHELİ` (eğer KE'ler sadece bilgi atomlarındaysa → `SARTLI_UYGUN`)

**Erken çıkış (on_kontrol):** Kontrendikasyon, raporsuz koruma gibi durumlar formül değerlendirilmeden önce uygulanır:

```json
"on_kontrol": [
  {
    "ad": "ACE+ARB birlikteliği — TIBBEN_UYGUN_DEGIL",
    "kosul": "X1 ∧ X2",
    "sonuc": "TIBBEN_UYGUN_DEGIL",
    "mesaj": "..."
  }
]
```

---

### ADIM 12 — Kullanıcı onay kapısı #2 (uçtan uca demo)

**Bu adım atlanmaz.** Senaryo testlerini koş, çıktıları kullanıcıya göster:

```
🧪 SUT <kod> — JSON v2 doğrulama

Senaryo 1: Tam UYGUN
  Beklenen: UYGUN
  Gerçek:   UYGUN ✓

Senaryo 2: Zorunlu eksik
  Beklenen: UYGUN_DEGIL
  Gerçek:   UYGUN_DEGIL ✓

...

🎨 GUI render testi:
  Reçete X seçildi → şema otomatik çıktı ✓
  AND seri ✓, VEYA paralel ✓, üst-VEYA çiftleri birleşti ✓

Tüm senaryolar geçti. Pilot tamamlanma onayınız?
```

Kullanıcı onaylarsa → Memory'ye proje kaydı + CLAUDE.md güncellemesi.

---

## ATOM TİPLERİ (inline, JSON'dan tanımlanabilir)

| Tip | Ne yapar | Params |
|---|---|---|
| `regex` | Metinde regex deseni arar | `desenler: [...]`, `etiket` |
| `regex_negatif` | Üç-yönlü parser: poz/neg/sessiz → VAR/YOK/KE | `poz_desenler`, `neg_desenler` |
| `icd_in` | Teşhislerde ICD prefix'i var mı | `prefixler: ["E10","E11"]` |
| `lab_olcum` | Sayısal lab değer + karşılaştırma | `ibare`, `alternatif_ibareler`, `op`, `deger` |
| `lab_var` | Sayısal değer varlığı (karşılaştırmasız) | `ibare`, `alternatif_ibareler` |
| `doktor_brans` | Doktor branşı listede mi | `anahtarlar`, `rapor_kodu_otoritesi` |
| `yas_op` | Hasta yaşı karşılaştırma | `op: ">="`, `deger: 18` |
| `kombi_iceriyor` | Aynı reçete diğer kalemlerde X var mı | `anahtarlar` |
| `etken_iceriyor` | Bu kalemin etken/ilaç adında X | `anahtarlar` |
| `rapor_kodu_var` | Rapor kodu boş değil mi | — |
| `rapor_kodu_in` | Rapor kodu prefix listesinde mi | `prefixler` |
| `rapor_metni_var` | Rapor metni boş değil mi | — |
| `manuel_kontrol` | Sistem sorgulayamıyor — eczacı doğrulayacak | `neden` |
| `her_zaman_var` | Trivial true (raporsuz serbest gibi) | — |
| `custom_python` | Yukarıdaki tipler yetmezse `atomlar.py`'deki Python atomu çağır | `atom_adi`, `params` |

---

## YAYGIN HATALAR (bu protokolde yakalama)

1. **DeMorgan unutmak.** "MD VEYA MK olmayan" → tek atom değil, iki ayrı NOT atomu.
2. **Sessizlik → örtük kabul.** NEGATİF atom + rapor sessiz → **KE**, asla VAR varsayma.
3. **Çoklu yolağı tek formüle sıkıştırmak.** D-1 ve D-2 farklı heyet listesi ister → dispatcher şart.
4. **Bypass şartlarını atlamak.** Üst-VEYA varsa diğer yolu sormaya gerek yok.
5. **Madde içi alt OR'ları görmezden gelmek.** "≥1 kardiyolog VEYA nörolog" → ayrı atom.
6. **Mülga maddeleri kodlamak.** Yürürlükten kalktıysa kontrol dışı.
7. **Süre/tarih şartlarını sessizce UYGUN saymak.** "1 yıl rapor süresi" parse edilemiyorsa **KE + bilgi**.
8. **Erken çıkış (early-return).** Kontrendikasyon bulununca tüm atomları üretmeye devam et — şema eksik kalmasın.
9. **Kombi yasağını yolak-özel sanmak.** Genel kontrendikasyon hem D-1 hem D-2 için.
10. **Aile hekimi yetkisini hep aktif sanmak.** 24 ay sonrası geçerli — hasta geçmişinden hesapla.
11. **Lafzı hafızadan yazmak.** Her zaman `docs/sut/SUT_tam_metin.txt`'ten oku.
12. **Kullanıcı onayı atlamak.** Adım 8 ve 12 zorunlu kapılar — koda direkt geçme.

---

## NE ZAMAN BU PROTOKOLE BAK

- Yeni bir SUT madde butonu eklenecekken (örn. "SUT 4.2.X şu ilaç grubu")
- Mevcut bir kontrolde bug var ve mantık şüpheli (sessizlik / DeMorgan / VEYA-yolu)
- Mevzuat metni karmaşık (parantez, alt madde, "olmayan", "veya")
- Kullanıcı "bir grup ilaç implement et" dediğinde — adım 1'den başla

---

## §13 — ÇALIŞILMIŞ ÖRNEK: SUT 4.2.13(3) Akut Hepatit B

(Pilot uygulama, 2026-05-23. Aşağıdaki tablolar JSON v2'nin nasıl üretildiğini gösterir.)

### Adım 1 — Resmî lafız
`docs/sut/SUT_tam_metin.txt:5457-5460`:
> (3) (Ek:RG-2/11/2024-32710)(115) Akut Hepatit B tedavisi
> a) Akut hepatit B nedeniyle izlenen hastalarda ciddi akut HBV kliniği ve laboratuvar bulguları olan (İNR ≥ 1,5 veya PT normalin üst sınırından 4 saniyeden daha uzun olanlar ve sarılık dönemi > 4 hafta olanlar) hastalarda 4 hafta arayla iki kere HBsAg negatifliği elde edilene kadar Sağlık Bakanlığınca onaylı endikasyonu bulunan antiviral ilaçların bedeli Kurumca karşılanır.

### Adım 2 — Mülga/değişik
- "(Ek:RG-2/11/2024-32710)(115)" → 2024 eklenmiş, yürürlükte
- Mülga ibare yok

### Adım 3 — Yolak
- Tek yolak: AKUT-B
- Dispatcher: ICD B16.x (akut HBV) + ilaç HBV oral antiviral → bu yolağa düş

### Adım 4 — Atom tablosu

| # | Ad | Kaynak | Tip | Sessiz default | Bilgi |
|---|---|---|---|---|---|
| A1 | Akut hepatit B teşhisi VAR | teşhis+rapor | `icd_in` (B16) + `regex` ("akut hepatit b") | YOK | - |
| B1 | INR ≥ 1,5 | rapor_metni | `lab_olcum` (ibare=INR, op=>=, deger=1.5) | KE | - |
| B2 | PT > normal üst sınır + 4 sn | rapor_metni | `regex` ("PT.*4 sn", "PT.*4 saniye") | KE | - |
| B3 | Sarılık > 4 hafta | rapor_metni | `regex` ("sarılık.*4 hafta", "ikterus.*4 hafta") | KE | - |
| C1 | Antiviral (SB onaylı) — HBV oral | etken/ilaç adı | `etken_iceriyor` (LAMIVUDIN/TENOFOVIR/ENTEKAVIR/...) | YOK | - |
| D1 | Tedavi süresi: 4 hafta arayla 2× HBsAg(-) | rapor_metni | `manuel_kontrol` (sistem süreyi sorgulayamıyor) | KE + bilgi | **Evet** |

### Adım 6 — Operatör çözümleme

Muğlak lafız: **"INR ≥ 1,5 veya PT … veya sarılık dönemi > 4 hafta olanlar"**

- Yorum 1 (klinik): "ciddi akut HBV laboratuvar bulguları" üst başlık + 3 alt kriterden **≥1 yeterli** → B1 ∨ B2 ∨ B3
- Yorum 2 (lafzi katı): "INR veya PT … VE sarılık" → (B1 ∨ B2) ∧ B3
- Yorum 3 (akut karaciğer yetmezliği King's College kriteri): INR/PT bağlı + sarılık süresi bağımsız

**Kullanıcıya sorulacak (Adım 8 onay kapısı).** Pilot için Yorum 1 default seçildi.

### Adım 7 — Boolean formül (Yorum 1)

```
AKUT_HBV_UYGUN ⇔ A1 ∧ (B1 ∨ B2 ∨ B3) ∧ C1 ∧ D1_bilgi
```

D1 bilgi atomu olduğu için matematiği etkilemez; eczacı manuel doğrularsa SARTLI_UYGUN.

### Adım 9 — JSON v2

→ `sut_kurallari/v2/akut_hepatit_b_4_2_13_3.json` (Adım 9 task'ında üretilecek)

### Adım 10 — Senaryolar

1. **Tam UYGUN:** teşhis B16, INR=2.1, antiviral=tenofovir → UYGUN
2. **Lab eksik (sessiz):** teşhis B16, INR yok, sarılık yok, antiviral=tenofovir → **ŞÜPHELİ** (B1/B2/B3 hepsi KE)
3. **VEYA tek dal:** teşhis B16, sarılık 6 hafta, INR yok → **UYGUN** (B3 yeterli)
4. **Teşhis yok:** ICD farklı (kronik B16.9 değil), rapor "akut" demiyor → UYGUN_DEGIL
5. **Yanlış ilaç:** akut B + ribavirin → UYGUN_DEGIL (C1 yok)
6. **Edge:** Boş rapor → ŞÜPHELİ

---

## EK — AI Hızlı Checklist (her seferinde)

```
[ ] 1. SUT_tam_metin.txt'ten lafzı oku, kullanıcıya göster
[ ] 2. Mülga/değişik/ek işaretle
[ ] 3. Yolak sayısı + dispatcher belirle
[ ] 4. Atom tablosu çıkar (ad, tip, kaynak, sessizlik, bilgi)
[ ] 5. Atomları numarala (A1, B1, ...)
[ ] 6. VE/VEYA/NOT + DeMorgan çözümle
[ ] 7. Boolean formül yaz
[ ] 8. ⛔ KULLANICI ONAY KAPISI #1 — tablo + formül sun, *sss
[ ] 9. JSON v2 dosyası üret
[ ] 10. ≥5 senaryo testi yaz
[ ] 11. Verdict eşleme + erken çıkış
[ ] 12. ⛔ KULLANICI ONAY KAPISI #2 — testleri koş, sonuçları sun
[ ] M. Memory + CLAUDE.md güncelle
```
