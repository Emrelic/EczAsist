# SUT Kuralı JSON v2 — Şema Referansı

> AI'nın ürettiği, motor_v2'nin yorumladığı, GUI'nin **kod dokunmadan** şemasını çizdiği format.
>
> Referans: `docs/SUT_AI_PROTOKOL_v1.md` (üretim protokolü)
> Pilot: `sut_kurallari/v2/akut_hepatit_b_4_2_13_3.json` (2026-05-23)

---

## ÜST DÜZEY YAPI

```jsonc
{
  "schema_version": "v2",          // sabit, "v2"
  "sut_kodu": "4.2.13(3)",         // SUT madde numarası (insan okur)
  "adi": "Akut Hepatit B",         // kısa ad (GUI mesajlarında)
  "sut_kurali_etiketi": "...",     // verdict'e eklenecek tam etiket
  "sut_metni_kaynak": "docs/sut/SUT_tam_metin.txt:5457-5460",
  "sut_metni": "...",              // resmî lafız tam metin
  "_yorum": "...",                 // free-form açıklama (motor okumaz)
  "_boolean_formul_aciklama": "...", // insan-okur formül açıklaması

  "atomlar": { ... },              // §1. Atom tanımları
  "formul": "...",                 // §2. Boolean formül (string)
  "yolaklar": { ... },             // §3. Çoklu yolak (opsiyonel, dispatcher ile)
  "dispatcher": { ... },           // §4. Yolak seçici (opsiyonel)
  "ust_or_ciftleri": [ ... ],      // §5. Üst-VEYA paralel metadata
  "on_kontrol": [ ... ],           // §6. Erken çıkış kuralları (opsiyonel)
  "verdict_eslemesi": { ... },     // §7. Kök durum → KontrolSonucu (opsiyonel, default var)
  "senaryolar": [ ... ]            // §8. pytest için yerleşik test senaryoları
}
```

---

## §1. Atomlar

`atomlar` bölümünde her atom benzersiz bir anahtar (örn. `A1`) altında tanımlanır.

```jsonc
"atomlar": {
  "A1": {
    "ad": "İnme öyküsü VAR",
    "tip": "icd_in",
    "params": {"prefixler": ["I60", "I61", "I62", "I63", "I64"]},
    "kaynak": "teshis",            // info amaçlı (rapor_metni/teshis/...)
    "sessizlik_default": "YOK",    // VAR | YOK | KE (motor sessiz veride bunu döner)
    "bilgi": false,                // true → matematiği etkilemez, sema'da görünür
    "neden_var": "ICD bulundu: {bulunanlar}",   // template, motor doldurur
    "neden_yok": "ICD listede yok ({prefixler})",
    "sartli_atom": false           // KE + true → SARTLI_UYGUN'a katkı
  }
}
```

### Atom tipleri (inline)

| tip | params | Üç-yönlü çıktı (VAR/YOK/KE) |
|---|---|---|
| `regex` | `desenler: [str]`, `etiket: str` | herhangi desen eşleşti → VAR; metin boş → KE; eşleşme yok → YOK |
| `regex_negatif` | `poz_desenler: [str]`, `neg_desenler: [str]`, `etiket: str` | poz var → YOK; neg var → VAR; ikisi yok → KE (sessiz) |
| `icd_in` | `prefixler: [str]`, `kaynak_alani: "teshis"|"diger_icd"` | prefix eşleşmesi → VAR; yok → YOK; teşhis boş → KE |
| `rapor_kodu_in` | `prefixler: [str]` | prefix var → VAR; yok → YOK; rapor_kodu boş → KE |
| `rapor_kodu_var` | — | rapor_kodu varsa VAR yoksa YOK |
| `rapor_metni_var` | — | metin doluysa VAR boşsa YOK |
| `lab_olcum` | `ibare`, `alternatif_ibareler: [str]`, `op: ">"|">="|"<"|"<="|"="`, `deger: float` | sayı + karşılaştırma sağlandı → VAR; sağlanmadı → YOK; sayı bulunamadı → KE |
| `lab_var` | `ibare`, `alternatif_ibareler: [str]` | sayı bulundu → VAR yoksa YOK (KE değil) |
| `doktor_brans` | `anahtarlar: [str]`, `rapor_kodu_otoritesi: [str]` | branş eşleşmesi → VAR; pratisyen+kanıt yok → YOK; branş bilgisi yok → KE |
| `yas_op` | `op: ">="|">"|...`, `deger: int` | hasta yaş + op sağlandı → VAR; sağlanmadı → YOK; yaş yok → KE |
| `kombi_iceriyor` | `anahtarlar: [str]` | aynı reçete diğer kalemlerde marker → VAR yoksa YOK |
| `etken_iceriyor` | `anahtarlar: [str]` | bu kalemin etken/ad'ında marker → VAR yoksa YOK |
| `metin_regex` | `desenler: [str]`, `etiket: str` | (`regex` ile aynı, geriye dönük) |
| `manuel_kontrol` | `neden: str`, `varsayilan_durum: "kontrol_edilemedi"|"var"|"yok"` | her zaman params'taki durum (default KE) |
| `her_zaman_var` | — | her zaman VAR (raporsuz serbest gibi trivial true) |
| `custom_python` | `atom_adi: str` (atomlar.py'deki kayıt), `params: {...}` | Python atom çağrısı (inline tipler yetmezse) |

### Kaynak alanları (info, hangi veriyi okuyor)

`rapor_metni`, `teshis`, `hasta_yasi`, `hasta_cinsiyet`, `doktor_brans`, `kurum_adi`, `tesis_kodu`, `recete_kalemleri`, `diger_etken_maddeler`, `diger_rapor_metinleri`, `diger_icd`, `etken_madde`, `ilac_adi`, `rapor_kodu`, `atc_kodu`, `kutu_sayisi`.

Motor `kaynak` alanını davranış için kullanmaz; sadece SartSonuc'a yazar (görsel).

---

## §2. Formül (boolean string)

Tek yolakta üst seviye formül. Çoklu yolakta her yolak kendi formülünü taşır.

**Operatörler:**
- `∧` veya `AND` veya `&&` veya `&` veya `VE` — AND
- `∨` veya `OR` veya `||` veya `|` veya `VEYA` — OR
- `¬` veya `NOT` veya `!` veya `DEGIL` — NOT (prefix)
- `(`, `)` — gruplama

**Atom referansları:** atomlar bölümündeki anahtar (örn. `A1`, `B1`).

**Örnek:**
```
"formul": "(A1 ∨ A2 ∨ A3) ∧ ¬B1 ∧ C1"
```

**Parser:** `recete_kontrol/sut_motor/formul_parser.py`. Hata mesajları konum + beklenen token gösterir.

**Üç-yönlü değerlendirme:**
- AND: hepsi VAR → VAR; bir YOK varsa YOK; aksi KE
- OR: bir VAR varsa VAR; hepsi YOK ise YOK; aksi KE
- NOT: VAR↔YOK takas, KE değişmez

---

## §3. Yolaklar (çoklu)

Hepatit, YOAK gibi tek ilaç grubunun farklı endikasyonlarda farklı kuralları olduğunda.

```jsonc
"yolaklar": {
  "D-1": {
    "ad": "D-1 · Atriyal Fibrilasyon",
    "atomlar": { "D1-A1": {...}, ... },
    "formul": "(D1-A1 ∨ D1-A2) ∧ D1-B1",
    "ust_or_ciftleri": [...],
    "verdict_eslemesi": {...}      // opsiyonel, üst seviyeyi override eder
  },
  "D-2": {
    "ad": "D-2 · DVT/PE",
    "atomlar": {...},
    "formul": "..."
  }
}
```

Üst seviyede `formul` yerine `yolaklar` kullanılır; `dispatcher` hangi yolağın aktif olduğunu belirler.

---

## §4. Dispatcher (yolak seçici)

```jsonc
"dispatcher": {
  "yolak_sayisi": 3,
  "sinyaller": [
    {
      "oncelik": 1,
      "tip": "rapor_kodu_prefix",
      "kurallar": {
        "04.02": "D-1",
        "06.01": "D-2"
      }
    },
    {
      "oncelik": 2,
      "tip": "icd_prefix",
      "kurallar": {
        "I48": "D-1",
        "I26": "D-2",
        "I80": "D-2",
        "I82": "D-2"
      }
    },
    {
      "oncelik": 3,
      "tip": "regex_metin",
      "kurallar": {
        "elektif.*kalça|elektif.*diz": "EK4F"
      }
    }
  ],
  "belirsiz_default": "KONTROL_EDILEMEDI",
  "belirsiz_mesaj": "Endikasyon yolu sinyallerden netleşmedi"
}
```

Sinyaller öncelik sırasıyla dener; ilk eşleşen yolağı seçer. Hiçbiri tutmuyorsa `belirsiz_default` döner.

---

## §5. Üst-VEYA çiftleri (paralel metadata)

GUI render'da (a) yolu VEYA (b) yolu paralel olarak gösterilmesi için.

```jsonc
"ust_or_ciftleri": [
  {
    "prefix_a": "Varfarin yolu (a)",
    "prefix_b": "Varfarin yolu (b)",
    "birlesik_ad": "Varfarin geçişi [(a) VEYA (b)]"
  }
]
```

GUI `_sema_grup_matematigi` bu listeyi JSON'dan okur (artık hard-coded değil).

---

## §6. Ön kontrol (erken çıkış)

Kontrendikasyon / raporsuz koruma gibi durumlar formül değerlendirilmeden önce yakalanır:

```jsonc
"on_kontrol": [
  {
    "ad": "ACE+ARB birlikteliği — TIBBEN_UYGUN_DEGIL",
    "kosul": "X1 ∧ X2",
    "atomlar_ek": {
      "X1": {"tip": "etken_iceriyor", "params": {"anahtarlar": ["PRIL"]}},
      "X2": {"tip": "kombi_iceriyor", "params": {"anahtarlar": ["SARTAN"]}}
    },
    "sonuc": "TIBBEN_UYGUN_DEGIL",
    "mesaj": "ACE-i + ARB aynı reçetede — klinik kontrendikasyon",
    "sartlar_ekle": [
      {"ad": "Aynı reçetede ACE+ARB", "durum": "VAR", "grup": "Kontrendikasyon"}
    ]
  }
]
```

`kosul` üst-seviye atomlar veya `atomlar_ek`'teki yerel atomlar kullanabilir.

---

## §7. Verdict eşleme

Default (motor_v2'de built-in):

```jsonc
"verdict_eslemesi": {
  "VAR": "UYGUN",
  "YOK": "UYGUN_DEGIL",
  "KE": "ŞÜPHELİ",
  "KE_sadece_bilgi": "SARTLI_UYGUN",   // tüm KE'ler bilgi atomlarındaysa
  "KE_sadece_sartli": "SARTLI_UYGUN"   // tüm KE'ler sartli_atom=true ise
}
```

Override etmek istersen JSON'da yaz; etmezsen default kullanılır.

---

## §8. Senaryolar (yerleşik testler)

```jsonc
"senaryolar": [
  {
    "ad": "Tam UYGUN",
    "_aciklama": "Tüm zorunlu şartlar tam, AND zinciri tutar",
    "ilac_sonuc": {
      "etken_madde": "TENOFOVIR",
      "ilac_adi": "VIREAD 245 MG TB",
      "rapor_kodu": "04.13.03",
      "recete_teshisleri": ["B16.9"],
      "tum_metin": "Akut hepatit B, INR: 2.1, ...",
      "kutu_sayisi": 1,
      "doktor_uzmanligi": "GASTROENTEROLOJI"
    },
    "beklenen_verdict": "UYGUN",
    "beklenen_grup_durumlari": {
      "Akut HBV klinik+lab": "VAR",
      "Antiviral SB onaylı": "VAR"
    }
  }
]
```

`pytest` yerleşik runner (`test_motor_v2_yerlesik_senaryolar.py`) bu listeyi okur ve her senaryoyu doğrular.

---

## DOĞRULAMA KURALLARI (motor_v2 yükleme aşaması)

1. `schema_version == "v2"` zorunlu
2. `atomlar` ya da `yolaklar` en az birisi olmalı
3. `yolaklar` varsa `dispatcher` da olmalı
4. `formul`daki her atom referansı `atomlar` (veya yolak içinde) tanımlı olmalı
5. Atom `tip` alanı bilinen tiplerden olmalı (yoksa hata)
6. Atom `params` o tipin beklediği parametrelere sahip olmalı (regex tipi `desenler` ister, lab_olcum `op`+`deger` ister, ...)
7. `sessizlik_default` ∈ {VAR, YOK, KE}; eksikse default değerle doldurulur (regex → YOK, regex_negatif → KE, lab → KE)
8. Boolean formül parser kabul etmelidir (parse hatası = yükleme hatası)
9. `ust_or_ciftleri` içindeki prefix'ler atom anahtarlarıyla başlamalı

Doğrulama başarısızsa motor `ValueError` fırlatır; sessizce devam etmez.

---

## v1 → v2 GEÇİŞ NOTLARI

- v1 (`{tip: AND/OR/USTOR, alt: [...], atom: ...}`) ağaç tabanlı; motor.py
- v2 (`atomlar + formul: "string"`) string + dict; motor_v2.py
- İkisi yan yana yaşar (`sut_kurallari/` v1, `sut_kurallari/v2/` v2)
- `uyumluluk.py` v2 dosyalarını da dispatch eder (kategori adıyla)
- Mevcut atom kayıt (`atom_kayit`) v2'de `custom_python` tipi olarak erişilebilir — geriye dönük uyum
