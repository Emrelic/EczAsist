# SUT Mevzuatı → Mantık Şeması → Algoritma Protokolü

> **Bu belge zorunlu metodolojidir.** Yeni bir SUT kontrol butonu / ilaç grubu kontrolü implementasyonuna başlamadan **önce** bu belge okunur ve metodoloji adım adım uygulanır. CLAUDE.md `ATOMİK DEVRE ŞEMASI PRENSİPLERİ` bölümünün **çalışılmış örneği**dir.
>
> Pilot uygulama: **YOAK SUT 4.2.15.D** (Dabigatran/Rivaroksaban/Edoksaban/Apiksaban), 2026-05-11. Bu mevzuat üzerinden VE/VEYA/DeMorgan/çoklu yolak ayrıştırması doğru kurgulandı; aynı kalıp tüm gruplara uygulanacak.

---

## METODOLOJİ — 7 Adım

Yeni bir SUT mevzuatı / ilaç grubu için kontrol yazılırken **bu sırayla** ilerlenir. Aşamalar atlanmaz; özellikle 1–4 arası "kod öncesi" tasarım aşamalarıdır ve **kullanıcıyla onaylanmadan** koda geçilmez.

### 1. SUT mevzuat metnini topla
- İlgili maddenin **tam metnini** (parantezli alt-maddeler, mülga ibareleri, EK-4/F gönderimleri dahil) hizala
- Mülga / yürürlükten kaldırılmış maddeleri **ayrıca işaretle** (kontrol dışı bırakılacak)
- EK-4/F madde numaralarını ana maddenin sonuna ekle

### 2. Yolak (dispatcher) sayısını belirle
Bir ilaç grubu **tek bir endikasyonda** mı yoksa **birden çok ayrı yolakta** mı kullanılıyor?

- Tek yolak (örn. statin) → doğrudan adım 3'e
- Çoklu yolak (örn. YOAK: AF / DVT-PE / cerrahi profilaksi) → her yolak için ayrı atomik şema + üst düzey **dispatcher**

Dispatcher karar sinyalleri (öncelik sırası):
1. `rec_rap_kod` (reçeteye bağlı rapor kodu) — en güçlü sinyal
2. Teşhis ICD-10 kodları (`teshis_kodu_listesi`)
3. Rapor metni anahtar ibareleri
4. Doktor branşı / miktar (ortopedi cerrahi limiti gibi)

Yolaklardan biri net kazanıyorsa o yolağa düş; **belirsizse** en güçlü sinyale göre seç + `dispatcher_belirsiz=True` flag (manuel uyarı). Hiçbiri tutmuyorsa `KONTROL_EDILEMEDI`.

### 3. Her yolak için atomik şart tablosu çıkar
SUT lafzındaki **her ibare** bir satır olmalı. Tablo formatı:

| # | Atom | Kaynak | Operatör | Sessiz default |
|---|---|---|---|---|
| A1 | İnme öyküsü VAR | rapor+teşhis | OR-grup1 (≥1) | YOK |
| B1 | Mitral darlık YOK | rapor | AND-grup2 (NOT) | **KE** |

- **Kaynak:** ibare hangi veri kaynağında aranacak (rapor metni / teşhis / hasta özellikleri / reçete kalemleri / hasta geçmişi)
- **Operatör:** atom hangi gruba ait + grup içi mantık (AND / OR / NOT)
- **Sessiz default:** rapor sessiz kalırsa atom hangi duruma düşer (POZİTİF atomlarda genelde YOK; NEGATİF atomlarda **mutlaka KE** — örtük kabul yasak)

### 4. Operatör çözümleme — VE/VEYA/NOT/Parantez/DeMorgan
SUT lafzındaki bağlaçları **çok sıkı** çöz. Yanlış mantık = yanlış sonuç. CLAUDE.md §2.1–2.4'teki tablolarla aynı kuralları uygula:

| SUT lafzı | Mantık |
|---|---|
| "ve" / virgül liste | AND (hepsi) |
| "veya" / "ya da" | OR |
| "bir ya da daha fazlası" | OR (≥1 yeterli) |
| Paragraflar (a)/(b) | OR (alternatif yollar) |
| "olan/olmuş/saptanmış" | POZİTİF (VAR olmalı) |
| "olmayan/yok/değil/kontrendike" | NEGATİF (NOT) |

**DeMorgan zorunlu:**
- `NOT (A OR B)` = `(NOT A) AND (NOT B)` ← her ikisi de YOK olmalı
- `NOT (A AND B)` = `(NOT A) OR (NOT B)` ← en az biri YOK olmalı

Parantezsiz lafızda "OLMAYAN" tüm listeyi kapsar; örn. **"A VEYA B olmayan"** = `¬A ∧ ¬B`.

### 5. Genel sonuç formülünü yaz
Atomik tablolardan boolean ifade kur. YOAK D-1 örneği:

```
D1_UYGUN ⇔
    (A1∨A2∨A3∨A4∨A5∨A6) AND   ← Madde (1) risk grup
    (B1 AND B2)         AND   ← Madde (1) kontrendikasyon (DeMorgan)
    C1                  AND   ← Madde (1) endikasyon
    (D-a ∨ D-b)         AND   ← Madde (1)(a) ∨ (b) geçiş yolu
    (F1 ∧ F2 ∧ F3)      AND   ← Madde (2) rapor + heyet
    (F5a ∨ F5b)         AND   ← Madde (2) reçete yetkisi
    G1                        ← Madde (4) kombi yasağı
```

### 6. Şemayı kullanıcıyla onayla (\*sss)
Adım 1–5 tamamlanınca koda geçmeden **kullanıcıya sun**:
- Yolak sayısı + dispatcher kuralı
- Her yolağın atomik şart tablosu
- Boolean formülü
- Açık sorular (dispatcher öncelik, dönem ayrımı, sessizlik kararları, vs.)

Yanıt gelene kadar koda dokunma. Bu **adım atlanmaz** çünkü mantık hatası kodu yazdıktan sonra düzeltmek 10× pahalı.

### 7. Kodu üret + akıl testi
Onay sonrası:
1. Her atom için ayrı fonksiyon: `_<kontrol>_atom_<sart>` (örn. `_yoak_atom_inme`)
2. Yolak başına dispatcher: `_<kontrol>_<yolak>_kontrol` (örn. `_yoak_d1_af_kontrol`)
3. Üst-yolak dispatcher (varsa): `_<kontrol>_genel_sonuc_atomik` (örn. `_yoak_genel_sonuc_atomik`)
4. `SartSonuc` listesi: `grup` + `veya_grubu` flag doğru → sema panel otomatik render
5. Akıl testi: en az 5–10 senaryo (UYGUN / UYGUN_DEGIL / ŞÜPHELİ + edge case + DeMorgan + sessizlik)
6. Parse edilemeyen şartlar (süre/miktar/tarih) → `KONTROL_EDILEMEDI` + grup adında `(bilgi)` suffix → matematiği bozmaz

---

## ÇALIŞILMIŞ ÖRNEK — YOAK SUT 4.2.15.D

Pilot uygulama. 4 etken madde (Dabigatran / Rivaroksaban / Edoksaban / Apiksaban), 3 farklı yolak, çapraz-VEYA, DeMorgan, bypass şartları, kombi yasağı dahil.

### Mevzuat özet
- **4.2.15.D-1:** Atriyal fibrilasyon kronik antikoagülasyon (4 alt-madde + mülga + kombi yasağı)
- **4.2.15.D-2:** DVT/PE tedavi/profilaksi (4 alt-madde, varfarin bypass dahil)
- **EK-4/F Madde 53–54:** Elektif kalça/diz total eklem replasmanı DVT profilaksisi (sadece rivaroksaban + dabigatran)

### Yolak 0 — Üst-Düzey Dispatcher

```
       ┌──────────────────────────┐
       │ Reçete YOAK içeriyor mu? │
       └────────────┬─────────────┘
                    │ EVET
                    ▼
    ┌───────────────────────────────────┐
    │  ENDİKASYON DALLANMA KARARI       │
    │  (rec_rap_kod → ICD → metin)      │
    └───┬─────────────┬─────────────────┘
        │             │              │
    ┌───▼──┐     ┌────▼────┐    ┌────▼──────┐
    │ D-1  │     │ D-2     │    │ EK-4/F    │
    │ AF   │     │ DVT/PE  │    │ ortopedi  │
    └──────┘     └─────────┘    └───────────┘
```

| Sinyal | D-1 | D-2 | EK-4/F |
|---|---|---|---|
| ICD/teşhis | I48.x (AF) | I26.x (PE), I80.x/I82.x (DVT) | Z47.x / Z96.6 / cerrahi öyküsü |
| `rec_rap_kod` | AF rapor kodu | DVT/PE rapor kodu | Ortopedi cerrahi raporu |
| Doktor branşı | Heyet → kardiyo/nöro | Heyet → kardiyo/iç/göğüs/KDC | Ortopedi (tek uzman) |
| Miktar | 1 yıl rapor | 1 yıl rapor | Diz≤1ku/10gün, Kalça≤3ku/35gün |

### Yolak D-1: Atriyal Fibrilasyon (4.2.15.D-1)

**SUT lafzı (Madde 1):**
> "…inme veya TIA öyküsü, ≥75 yaş, KY NYHA≥II, DM veya HT durumlarından bir ya da daha fazlasına sahip olan, orta-ciddi mitral darlık veya mekanik protez kapağı olmayan, nonvalvuler atriyal fibrilasyonlu hastalarda…"

#### Atom tablosu

| # | Atom | Kaynak | Op | Sessiz |
|---|---|---|---|---|
| A1 | İnme öyküsü VAR | rapor+teşhis | OR-risk (≥1) | YOK |
| A2 | TIA öyküsü VAR | rapor+teşhis | OR-risk | YOK |
| A3 | Yaş ≥75 | hasta | OR-risk | KE (yaş yoksa) |
| A4 | NYHA ≥II KY VAR | rapor+teşhis | OR-risk | YOK |
| A5 | DM VAR | rapor+teşhis | OR-risk | YOK |
| A6 | HT VAR | rapor+teşhis | OR-risk | YOK |
| **B1** | **Mitral darlık (orta-ciddi) YOK** | rapor | AND-kont (NOT) | **KE** |
| **B2** | **Mekanik protez kapak YOK** | rapor | AND-kont (NOT) | **KE** |
| C1 | Non-valvüler AF VAR | rapor+teşhis | AND (zorunlu) | YOK |

**DeMorgan:** "(MD VEYA MK) OLMAYAN" → `¬MD ∧ ¬MK`. İkisi de YOK olmalı, her biri ayrı atom, sessizlik → KE.

#### Madde (1)(a) — Varfarin başarısızlık zinciri (D-a)
D1: ≥2 ay varfarin · D2: haftalık aralı ölçüm · D3: son 5 ölçüm · D4: ≥3'ünde INR 2–3 tutulamadı · D5: INR hedefi 2–3 ibare · D6: varfarin kesildi
→ Hepsi AND.

#### Madde (1)(b) — Varfarin altında SVO (D-b)
E1: varfarin tedavisi altında · E2: SVO/serebrovasküler olay öyküsü
→ Hepsi AND.

**Geçiş yolu = (D-a TAMAM) OR (D-b TAMAM)** ← üst-VEYA çifti

#### Madde (2) — Rapor + heyet
F1: SK raporu VAR · F2: heyette ≥3 uzman (Kardiyo/İç/Göğüs/KDC/Nöro) · F3: heyette **≥1 kardiyolog VEYA nörolog** · F4: rapor süresi 1 yıl (bilgi, KE) · F5a: reçete eden hekim 5 daldan biri **VEYA** F5b: 24 ay sonrası + aile hekimi/uzman raporu.

#### Madde (3) — MÜLGA, kontrol dışı

#### Madde (4) — Kombi yasağı
G1: aynı reçetede 2 farklı YOAK YOK (reçete kalemlerinden hesaplanır, D-1 ve D-2 paylaşımlı)

#### D-1 Genel formülü
```
D1_UYGUN ⇔ (A1∨…∨A6) ∧ (B1 ∧ B2) ∧ C1 ∧ (D-a ∨ D-b) ∧ (F1∧F2∧F3) ∧ (F5a∨F5b) ∧ G1
```

### Yolak D-2: DVT/PE (4.2.15.D-2)

#### Madde (1)(a) — Endikasyon (OR ≥1)
H1: yetişkin (≥18) · I1: DVT tedavisi · I2: akut DVT sonrası tekrar önleme · I3: PE tedavisi · I4: tekrar PE/DVT önleme

#### Madde (1)(b) — Varfarin zinciri
D-1(a) ile **aynı**: D1–D6 atomları paylaşımlı.

#### Madde (2) — Varfarin koşulu BYPASS (OR ≥1 yeterli)
J1: tekrarlayan idiopatik PE · J2: homozigot trombofili · J3: VTE öyküsü + aktif kanser (içeride AND) · J4: immobil (rapor nedeni belirtilmiş)

**Üst-VEYA:** `(D-a zinciri) ∨ (J1∨J2∨J3∨J4)` — bypass varsa varfarin zinciri sorulmaz.

#### Madde (3) — Rapor heyeti (D-1'den FARKLI!)
K1: SK VAR · K2: ≥3 uzman · K3: **kardiyo/iç/göğüs/KDC** (nöroloji **YOK**!) · K3a: aynı daldan 3 üye **VEYA** K3b: 4 daldan herhangi 3 · K4/K5: reçete yetkisi (24 ay öncesi/sonrası).

#### Madde (4) — Yenileme
Yeni SK raporu ile devam. Tek reçete kontrolünde KE + bilgi.

#### D-2 Genel formülü
```
D2_UYGUN ⇔ H1 ∧ (I1∨…∨I4) ∧ (D-a ∨ J1∨J2∨J3∨J4) ∧ (K1∧K2∧K3) ∧ (K4∨K5) ∧ G1
```

### Yolak EK-4/F: Ortopedi Profilaksi (Madde 53–54)

#### Endikasyon
L1: elektif kalça **VEYA** diz total eklem replasmanı · L2: DVT profilaksisi amacı (rapor metninde) · L3: rapor ortopedi uzmanı tarafından düzenlenmiş

#### Miktar şartları
| İlaç | Lokalizasyon | Limit |
|---|---|---|
| Rivaroksaban | Diz | ≤1 kutu |
| Rivaroksaban | Kalça | ≤3 kutu |
| Dabigatran | Diz | ≤10 gün |
| Dabigatran | Kalça | ≤35 gün |
| Apiksaban / Edoksaban | — | EK-4/F kapsamı YOK → **UYGUN_DEĞİL** |

Rapor "diz mi kalça mı" belirtmiyorsa → KE (manuel doğrulama).

---

## YAYGIN HATALAR — bu örnekte yakalandı, uyarı listesi

1. **DeMorgan unutmak.** "MD VEYA MK olmayan" → tek atom yazmak yerine ikisi ayrı NOT atomu olarak yazılır.
2. **Sessizlik → örtük kabul.** Rapor "mitral"den hiç bahsetmiyorsa "mitral darlık yok" varsayma — **KE** olur (memory: `feedback_sut_ortuk_kabul_yasak.md`).
3. **Çoklu yolağı tek algoritmaya sıkıştırmak.** D-1 ve D-2 farklı heyet listesi ister, dispatcher şart.
4. **Bypass şartlarını atlamak.** D-2(2) bypass'i varsa varfarin zincirini sormaya gerek yok — üst-VEYA atlanırsa false-negatif olur.
5. **Madde içi alt OR'ları görmezden gelmek.** Heyet "≥1 kardiyolog VEYA nörolog" → ayrı şart, ayrı atom.
6. **Mülga maddeleri kodlamak.** D-1(3) mülga — kontrol dışı.
7. **Süre/tarih şartlarını sessizce UYGUN saymak.** "1 yıl rapor süresi" parse edilemiyorsa **KE + (bilgi)** grupta tutulur, matematiği bozmaz.
8. **Erken çıkış (early-return).** Kontrendikasyon bulununca tüm atomları üretmeye devam et — şema eksik kalmasın.
9. **Kombi yasağını yolak-özel sanmak.** G1 (4. madde) hem D-1 hem D-2 için paylaşımlı.
10. **Aile hekimi yetkisini hep aktif sanmak.** F5b/K5 ancak 24 ay sonrası geçerli — hasta geçmişinden hesaplanmalı, veriyoksa KE + bilgi.

---

## NE ZAMAN BU PROTOKOLE BAK
- Yeni bir SUT madde butonu eklenecekken (örn. "SUT 4.2.X şu ilaç grubu")
- Mevcut bir kontrolde bug var ve mantık şüpheli (sessizlik / DeMorgan / VEYA-yolu)
- Mevzuat metni karmaşık (parantez, alt madde, "olmayan", "veya")
- Kullanıcı "bir grup ilaç implement et" dediğinde — adım 1'den başla.

CLAUDE.md `ATOMİK DEVRE ŞEMASI PRENSİPLERİ` (§1–9) bu belgenin **kuralları**, bu belge **çalışılmış örneği**dir. İkisi birlikte okunur.
