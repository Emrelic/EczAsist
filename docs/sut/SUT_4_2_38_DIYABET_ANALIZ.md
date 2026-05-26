# SUT 4.2.38 + 4.2.74 — Diyabet & SGLT-2 KY/KBH İlaç Kullanım İlkeleri
## Atomik Devre Şeması + Mantıksal Formülasyon

> Kaynaklar:
> - SUT 4.2.38 (8 fıkra) — mevzuat.gov.tr MevzuatNo=17229, `docs/sut/SUT_tam_metin.txt:8238–8287`
> - SUT 4.2.74 (Ek:RG-8/4/2026-33218) — `docs/sut/SUT_tam_metin.txt:8932–8946`
> - Pilot metodoloji: `docs/SUT_MANTIK_SEMA_PROTOKOLU.md` (YOAK 4.2.15.D)
>
> Bu belge `recete_kontrol/diyabet_4_2_38.py` motorunun **donmuş tasarım belgesi**dir.
> Mevzuat değişirse buradan başlanır; kod buna göre güncellenir.

---

## 0. Yolak haritası

| Yolak | İlaç sınıfı | SUT |
|---|---|---|
| **Y1** | Metformin / Sülfonilüre / Met+Sulfo / Akarboz / İnsan insülini | 4.2.38 (1) |
| **Y2** | Repaglinid (+kombi) / Nateglinid / OAD kombineleri | 4.2.38 (2) |
| **Y3** | Analog insülin / Pioglitazon / Pio+OAD / Pio+insülin | 4.2.38 (3) |
| **Y3b** | İnsülin Degludek+Aspart (Ryzodeg) | 4.2.38 (3)(b) |
| **Y4** | DPP-4 antagonistleri (sita/vilda/saksa/lina/alo) + kombineleri | 4.2.38 (4) |
| **Y5** | Eksenatid | 4.2.38 (5) |
| **Y6** | SGLT-2 (dapa/empa) + kombineleri — diyabet yolağı | 4.2.38 (6) |
| **Y7** | İnsülin Glarjin+Liksisenatid (Soliqua) | 4.2.38 (7) |
| **Y8** | Empagliflozin+Linagliptin kombi (Glyxambi) | 4.2.38 (8) |
| **Y9_KAPSAM_DISI** | Diğer GLP-1 (liraglutid/semaglutid/dulaglutid/tirzepatid) | yok |
| **Y_KY** | SGLT-2 (dapa/empa) → Kalp Yetmezliği endikasyonu | **4.2.74 (1)** |
| **Y_KBH** | SGLT-2 (dapa/empa) → Kronik Böbrek Hastalığı endikasyonu | **4.2.74 (2)** |

---

## 1. Dispatcher (etken madde + endikasyon → yolak)

### 1.1 Etken madde önceliği (Y1–Y8/Y9)

```
1. Sabit kombi preparat? (en spesifik)
   - Empagliflozin + Linagliptin     → Y8 (veya Y_KY/Y_KBH? — empa bileşeni)
   - İnsülin Glarjin + Liksisenatid  → Y7
   - İnsülin Degludek + Aspart       → Y3b
2. Eksenatid (tek başına)              → Y5
3. Diğer GLP-1 (lira/sema/dula/tirze)  → Y9_KAPSAM_DISI (UYGUN_DEĞİL)
4. DPP-4 (sita/vilda/saksa/lina/alo)
   + Met/Sulfo/SGLT2 kombineleri      → Y4
5. SGLT-2 (dapa/empa) + kombineleri    → ENDİKASYON DİSPATCHER (alt §1.2)
6. Analog insülin / Pioglitazon
   + Pio kombineleri                  → Y3
7. Repaglinid / Nateglinid /
   OAD kombineleri                    → Y2
8. Met / Sulfo / Akarboz / İnsan ins. → Y1
```

### 1.2 SGLT-2 alt-dispatcher (Y6 vs Y_KY vs Y_KBH)

Dapa/empa reçetelerinde 3 endikasyon yolağı yarışır. Sinyal öncelik sırası:

| Sinyal | Y_KY | Y_KBH | Y6 (DM) |
|---|---|---|---|
| Aktif rapor metni | "kalp yetersizliği" / "düşük EF" / NYHA II-IV | "KBH" / "ACR ≥200" / "PCR >300" / proteinüri | "DM" / "yetersiz glisemik kontrol" |
| ICD teşhis | I50.x | N18.x | E10.x / E11.x |
| Heyet | Kardiyoloji uzmanı VAR | Nefroloji uzmanı VAR | (Endo / IH) |
| Bypass | Geçmiş rapor "EF/KY" lafzı | Geçmiş rapor "ACR/PCR/proteinüri" | Geçmiş rapor "glisemik kontrol sağlanamadı" |

**Karar mantığı:**
1. **Aktif rapor lafzı** kazanır (en güçlü sinyal). Birden fazla varsa: aktif raporda hangi yolağın atomları tam karşılanıyorsa o seçilir.
2. Aktif rapor sessizse → **geçmiş rapor bypass** (memory: `project_diger_rapor_uygun_bypass`) çalıştırılır:
   - Y6 için "glisemik" ibaresi (mevcut bypass)
   - Y_KY için "EF/NYHA/KY" ibaresi (yeni eklenecek)
   - Y_KBH için "ACR/PCR/proteinüri" ibaresi (yeni eklenecek)
3. Hiçbiri yoksa → varsayılan **Y6** (en eski, en yaygın endikasyon) + `dispatcher_belirsiz=True` (manuel uyarı).

**Önemli:** 4.2.74 yolağı kazanırsa Y6'nın `Met/Sulfo max yet.` şartı **sorulmaz** (farklı endikasyon, farklı SUT lafzı). Y6 kazanırsa 4.2.74 atomları (EF, eGFR, vs.) sorulmaz.

---

## 2. Paylaşımlı atomlar

| # | Atom | Kaynak | Sessiz default |
|---|---|---|---|
| O1 | Tip 2 DM teşhisi VAR | rapor metni + ICD (E11.x) | YOK |
| O2 | BMI > 35 (tedavi başlangıcı) | hasta kilo+boy → yoksa rapor BMI/VKİ ibaresi → yoksa KE | KE |
| O3 | Akut pankreatit öyküsü YOK (NEG) | rapor metni + teşhis (K85.x) | **KE** (DeMorgan, örtük kabul yasak) |
| O4 | Metformin max doz yetersiz | rapor metni ("max doz", "yeterli kontrol sağlanamadı") | KE |
| O5 | Sülfonilüre max doz yetersiz | rapor metni | KE |
| O6 | Endokrinoloji uzman raporu VAR | rapor verisi (heyet/rapor doktoru) | YOK |
| O7 | İç hastalıkları uzman raporu VAR | rapor verisi | YOK |
| O8 | Reçete eden hekim endokrinoloji uzmanı | hekim_branş | YOK |
| O9 | Reçete eden hekim iç hastalıkları uzmanı | hekim_branş | YOK |
| O10 | Sağlık kurulu raporu VAR | rapor tip | YOK |
| O11 | Heyette ≥1 endokrinoloji uzmanı | rapor heyet | YOK |
| O12 | Heyette ≥1 IH uzmanı | rapor heyet | YOK |
| O13 | KBY VAR (Y4 düşük doz için) | ICD N18.x + rapor metni ("KBY/diyaliz") | YOK |
| O14 | İlk reçete (hasta satış geçmişi) | hasta satış geçmişi | KE (geçmiş yok) |
| **O15** | **Kardiyoloji uzmanı heyette VAR** | rapor heyet | YOK |
| **O16** | **Nefroloji uzmanı heyette VAR** | rapor heyet | YOK |
| **O17** | **EF ≤ %40 (sol ventrikül)** | rapor metni (`EF[^a-z]{0,5}%?\d+`) | KE |
| **O18** | **NYHA sınıf II–IV** | rapor metni (`NYHA[^a-z]{0,5}[IV]+`) | KE |
| **O19** | **eGFR ≥ X (dapa=25, empa=20)** | rapor metni (`eGFR[^a-z]{0,5}\d+`) | KE |
| **O20** | **RAAS-İ kullanıyor (ACE-İ veya ARB)** | hasta ilaç geçmişi + rapor metni + aktif reçete diğer kalemleri | KE |
| **O21** | **Persistan proteinüri ≥ 3 ay (ACR ≥ 200 mg/g VEYA PCR > 300 mg/g)** | rapor metni (`ACR/PCR\s*\d+`) | KE |
| **O22** | **Standart KY tedavi VAR ((ACE-İ ∨ ARB) ∧ BB ∧ MRA)** | hasta ilaç geçmişi + aktif reçete diğer kalemleri | KE |
| **O23** | **Kullanılamama gerekçesi raporda VAR** | rapor metni ("kullanılamadı/kontrendike/intolerans") | KE |
| **O24** | **Önceden analog karışım VEYA uzun etkili insülin kullanılmış** | hasta ilaç geçmişi (satış) | YOK |
| **O25** | **Yetersiz glisemik kontrol (genel)** | rapor metni (`yetersiz.{0,15}kontrol` veya `kontrol.{0,15}sağlanam`) | KE |
| **O26** | **Metformin altyapısı VAR (diyet+egzersiz + Met)** | hasta ilaç geçmişi (met sınıfı) + rapor metni | KE |
| **O27** | **İlk rapor üzerinden ≥24 ay geçti mi** (Y3b dispatcher) | hasta ilk satış tarihi / rapor başlangıcı | KE |

NEG atomlar (O3, O22/O23 kombi) için **örtük kabul yasak** — sessiz olunca KE; "yok" lafzen yazılıysa VAR; "var" lafzen yazılıysa kontrendikasyon → şart YOK.

---

## 3. Yolak atomları (TAM detay)

### Y1 — Tüm hekimler (Fıkra 1)

```
Y1_UYGUN ⇔ kalem ∈ Y1-sınıfı  (rapor/uzman şartı YOK)
```

| # | Atom | Operatör | Kaynak |
|---|---|---|---|
| Y1.1 | İlaç Y1 sınıfında (dispatcher zaten yaptı) | tek-atom | ilac_sinifi |

---

### Y2 — Repaglinid/Nateglinid/OAD kombi (Fıkra 2) — **PARALEL-YOL kalıbı**

Klinik şart yok; sadece yetki yolu.

```
Y2_UYGUN ⇔ [ Y2.1 ]    ; RAPORSUZ YOL
           ∨
           [ Y2.2 ]    ; RAPORLU YOL
```

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y2.1 | Reçete hekimi ∈ {Endo, IH, Pediatri, Kardiyo, Aile Hek} | RAPORSUZ yol (tek-atom) | hekim_brans | YOK |
| Y2.2 | Uzman raporu (yukarıdaki branşlardan biri) | RAPORLU yol (tek-atom) | rapor_brans | YOK |

---

### Y3 — Analog insülin / Pioglitazon (Fıkra 3) — **PARALEL-YOL kalıbı**

Klinik şart yok; sadece yetki yolu.

```
Y3_UYGUN ⇔ [ Y3.1 ]    ; RAPORSUZ YOL
           ∨
           [ Y3.2 ]    ; RAPORLU YOL
```

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y3.1 | Reçete hekimi ∈ {Endo, IH, Pediatri, Kardiyo}    *(Aile hek YOK!)* | RAPORSUZ yol (tek-atom) | hekim_brans | YOK |
| Y3.2 | Uzman raporu (yukarıdaki branşlardan) | RAPORLU yol (tek-atom) | rapor_brans | YOK |

---

### Y3b — Degludek+Aspart / Ryzodeg (Fıkra 3-b)

**SUT lafzı (8248–8252):**
> "…analog karışım veya uzun etkili insülinlerden birini kullanmış olmasına rağmen kan şekeri labil seyreden ve/veya sık hipoglisemik olay geçiren ve/veya hipoglisemi riski yüksek ya da regülasyon sağlanamayan hastalarda bu durumun belirtildiği en az bir endokrinoloji uzman hekiminin yer aldığı sağlık kurulu raporuna dayanılarak endokrinoloji veya iç hastalıkları uzman hekimlerince reçete edilebilir. **İlk rapordan (24 ay) sonraki sağlık kurulu raporlarında iç hastalıkları uzman hekimlerinin yer alması halinde de bedelleri Kurumca karşılanır.**"

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y3b.1 | Önceden analog karışım VEYA uzun etkili insülin kullanılmış | AND-zorunlu | hasta ilaç geçmişi | YOK |
| Y3b.2a | Kan şekeri labil VAR | OR-klinik (≥1) | rapor metni | YOK |
| Y3b.2b | Sık hipoglisemik olay VAR | OR-klinik | rapor metni | YOK |
| Y3b.2c | Hipoglisemi riski yüksek VAR | OR-klinik | rapor metni | YOK |
| Y3b.2d | Regülasyon sağlanamadı VAR | OR-klinik | rapor metni | YOK |
| Y3b.3 | SK raporu VAR | AND | rapor_tip | YOK |
| Y3b.4 | Heyette ≥1 endokrinoloji uzmanı | (koşullu — alttaki dispatcher) | rapor_heyet | YOK |
| Y3b.5 | Heyette ≥1 IH uzmanı | (koşullu — alttaki dispatcher) | rapor_heyet | YOK |
| Y3b.6 | Reçete hekimi ∈ {Endo, IH} | AND-yetki | hekim_brans | YOK |
| Y3b.7 | İlk rapordan ≥24 ay geçti mi (dispatcher) | meta | hasta_gecmis | KE |

**Boolean formülü (zaman koşullu dallanma):**
```
Y3b_UYGUN ⇔ Y3b.1 ∧ (Y3b.2a ∨ Y3b.2b ∨ Y3b.2c ∨ Y3b.2d) ∧ Y3b.3 ∧ Y3b.6 ∧
            ( (¬Y3b.7 → Y3b.4)                          ; ilk 24 ay → endo zorunlu
              ∧
              ( Y3b.7  → (Y3b.4 ∨ Y3b.5)) )             ; sonrası → endo ∨ IH
```

Y3b.7 KE ise (geçmiş yok) → güvenli yaklaşım: ilk rapor varsayımıyla Y3b.4 (endo) zorunlu.

---

### Y4 — DPP-4 antagonistleri (Fıkra 4) — **PARALEL-YOL kalıbı** (2026-05-25)

**SUT lafzı (8253–8257):**
> "DPP-4 antagonistleri (sitagliptin, vildagliptin, saksagliptin, linagliptin, alogliptin), DPP-4 antagonistlerinin diğer oral antidiyabetiklerle kombine preperatları; metformin ve/veya sülfonilürelerin maksimum tolere edilebilir dozlarında yeterli glisemik kontrol sağlanamamış hastalarda; **endokrinoloji uzman hekimleri ile iç hastalıkları uzman hekimlerince** **veya** **bu hekimlerce düzenlenen uzman hekim raporu ile tüm hekimlerce** reçete edilebilir."

İki paralel yetki yolu var (üst-VEYA çifti):
- **RAPORSUZ YOL**: Endo/IH uzman hekimi doğrudan yazar — rapor şartı yok. Klinik şart (Met/Sulfo max yetersiz) hekim sorumluluğunda kalır; sistem rapor metni yoksa bunu doğrulayamaz → bilgi atomu olarak görünür (matematiğe katmaz).
- **RAPORLU YOL**: Endo/IH branşlı uzman hekim raporu varsa, reçeteyi tüm hekimler yazabilir. Bu yolda klinik şart raporda lafzen aranır.

```
Y4_UYGUN ⇔ [ Y4.2 ]                                    ; RAPORSUZ YOL
           ∨
           [ Y4.3 ∧ Y4.1 ]                              ; RAPORLU YOL
         ∧ (saksa2.5 → Y4.4) ∧ (alo12.5 → Y4.5) ∧ KY4.1
```

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y4.1 | Met max doz yet. ∨ Sulfo max doz yet. (klinik şart) | RAPORLU yolda AND | rapor metni | KE (RAPORSUZ yolda **bilgi**, matematiğe katmaz) |
| Y4.2 | Reçete hekimi ∈ {Endo, IH} | RAPORSUZ yol (tek-atom) | hekim_brans | YOK |
| Y4.3 | Uzman raporu (Endo veya IH) | RAPORLU yol AND | rapor_brans | YOK |
| Y4.4 | Saksa 2.5 mg form? → KBY VAR | koşullu | etken+doz + ICD N18.x | YOK (form değilse NA) |
| Y4.5 | Alo 12.5 mg form? → KBY VAR | koşullu | etken+doz + ICD N18.x | YOK (form değilse NA) |
| KY4.1 | Aynı reçetede GLP-1 analoğu YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE (bilinmiyorsa) |

---

### Y5 — Eksenatid (Fıkra 5) — TAM detay

**SUT lafzı (8259–8270):**
> "(5) Eksenatid; **vücut kitle indeksi tedavi başlangıcında 35 kg/m²'nin üzerinde** olan ve **tedavi öncesi anamnezde akut pankreatit geçirilme öyküsü bulunmayan tip 2 diyabet hastalarında**;
> **(a) Metformin ve/veya sülfonilürelerin maksimum tolere edilebilir dozlarında yeterli glisemik kontrol sağlanamamış** hastalarda kombinasyon şeklinde,
> **(b) Metformin ve/veya pioglitazon ile kombine ya da tek başına bazal insülin ile yeterli glisemik kontrol sağlanamamış** hastalarda bazal insüline ek olarak kullanılabilir.
> (c) Başlangıç dozu (2x5mcg) (1 kutu) — endokrinoloji uzman hekimlerince. Başlama kriterleri ilk reçetede belirtilecektir. Devam: 6 ay süreli endo rapor → 1 yıl süreli endo rapor. Endo/IH uzman hekim reçeteler. **Akut pankreatit geçirilirse ilaç kesilir.**
> (ç) **DPP-4 antagonistleri ile birlikte ödenmez.**"

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y5.1 | Tip 2 DM VAR | AND-zorunlu | ICD E11.x + rapor metni | YOK |
| Y5.2 | BMI > 35 (tedavi başlangıcı) | AND-zorunlu | hasta kilo+boy → rapor BMI lafzı → KE | KE |
| Y5.3 | Akut pankreatit öyküsü YOK (NEG) | AND-zorunlu | rapor metni + ICD K85.x | **KE** (örtük kabul yasak) |
| Y5.4a | Met ve/veya Sulfo max yet. → kombi (a-yolu) | OR (üst) | rapor metni | KE |
| Y5.4b | (Met ve/veya Pio kombi VEYA tek bazal insülin) yetersiz → bazal insüline ek (b-yolu) | OR (üst) | rapor metni + hasta ilaç geçmişi | KE |
| Y5.5 | İlk reçete mi (hasta satış geçmişi)? | meta | hasta_gecmis | KE |
| Y5.6 | (ilk) Reçete hekimi = Endo ∧ 1 kutu (2x5mcg) | İlk-dal AND | hekim_brans + miktar | YOK |
| Y5.7 | (devam) Endo SK raporu VAR (6 ay → 1 yıl) | Devam-dal AND | rapor_brans + rapor_tip | YOK |
| Y5.8 | (devam) Rapor içeriği: devam kararı + başlama kriterleri + max dozlar | Devam-dal AND | rapor metni | KE (parse zor → bilgi) |
| Y5.9 | (devam) Reçete hekimi ∈ {Endo, IH} | Devam-dal AND | hekim_brans | YOK |
| KY5.1 | Aynı reçetede DPP-4 antagonisti YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE |
| KY5.2 | Aktif tedavi sırasında akut pankreatit gelişmedi (NEG) | AND-kombi (NOT) | hasta_gecmis + rapor | KE |

**Boolean formülü:**
```
Y5_UYGUN ⇔ Y5.1 ∧ Y5.2 ∧ Y5.3 ∧ (Y5.4a ∨ Y5.4b) ∧
           ( (Y5.5 → Y5.6) ∧ (¬Y5.5 → (Y5.7 ∧ Y5.8 ∧ Y5.9)) ) ∧
           KY5.1 ∧ KY5.2
```

---

### Y6 — SGLT-2 inhibitörleri / DİYABET yolağı (Fıkra 6) — **PARALEL-YOL kalıbı** (2026-05-25)

**SUT lafzı:** Y4'le aynı yapıda — "endokrinoloji veya iç hastalıkları uzman hekimlerince **veya** bu hekimlerce düzenlenen uzman hekim raporu ile tüm hekimlerce".

```
Y6_UYGUN ⇔ [ Y6.2 ]                ; RAPORSUZ YOL
           ∨
           [ Y6.3 ∧ Y6.1 ]          ; RAPORLU YOL
```

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y6.1 | Met max doz yet. ∨ Sulfo max doz yet. | RAPORLU yolda AND | rapor metni (bypass: geçmiş raporlar) | KE (RAPORSUZ yolda **bilgi**) |
| Y6.2 | Reçete hekimi ∈ {Endo, IH} | RAPORSUZ yol (tek-atom) | hekim_brans | YOK |
| Y6.3 | Uzman raporu (Endo/IH) | RAPORLU yol AND | rapor_brans | YOK |

**Bypass kuralı:** Aktif rapor "glisemik" ibaresi içermiyorsa hastanın geçmiş raporlarında aynı ibareler aranır (memory: `project_diger_rapor_uygun_bypass`). Bulunursa Y6.1 VAR + `bypass_kaynak="DIGER_RAPOR"`.

---

### Y7 — Glarjin+Liksisenatid (Soliqua, Fıkra 7) — TAM detay

**SUT lafzı (8276–8281):**
> "(7) İnsülin glarjin, liksisenatid kombinasyonu; **vücut kitle indeksi tedavi başlangıcında 35 kg/m²'nin üzerinde** olan ve **tedavi öncesi anamnezde akut pankreatit geçirilme öyküsü bulunmayan tip 2 diyabet hastalarında**; **yeterli kontrol sağlanamayan tip 2 diabetes mellitusu olan yetişkinlerde** glisemik kontrolü iyileştirmek için, **SGLT-2 inhibitörleri ile beraber veya SGLT-2 inhibitörleri olmaksızın metformin ile birlikte, diyet ve egzersize ek tedavi** olarak kullanılması halinde bu durumların belirtildiği **1 yıl süreli endokrinoloji uzman hekim raporuna** dayanılarak **endokrinoloji veya iç hastalıkları uzman hekimlerince** reçete edilmesi halinde bedelleri Kurumca karşılanır. **Akut pankreatit geçirilmesi durumunda ilaç kesilir.** **DPP-4 antagonistleri ile birlikte ödenmez.**"

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y7.1 | Tip 2 DM VAR + yetişkin (≥18) | AND-zorunlu | ICD E11.x + rapor metni + hasta yaşı (DB) | YOK |
| Y7.2 | BMI > 35 (tedavi başlangıcı) | AND-zorunlu | hasta kilo+boy → rapor BMI lafzı → KE | KE |
| Y7.3 | Akut pankreatit öyküsü YOK (NEG) | AND-zorunlu | rapor metni + ICD K85.x | **KE** (örtük kabul yasak) |
| Y7.4 | Yetersiz glisemik kontrol VAR | AND-klinik | rapor metni | KE |
| Y7.5 | Metformin altyapısı (Met VEYA Met+SGLT-2) + diyet/egzersiz | AND-zorunlu | hasta ilaç geçmişi + rapor metni | KE |
| Y7.6 | 1 yıl süreli endo SK raporu VAR | AND-yetki | rapor_brans + rapor_tip + süre | KE (süre parse → bilgi) |
| Y7.7 | Reçete hekimi ∈ {Endo, IH} | AND-yetki | hekim_brans | YOK |
| KY7.1 | Aynı reçetede DPP-4 antagonisti YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE |
| KY7.2 | Aktif tedavi sırasında akut pankreatit gelişmedi (NEG) | AND-kombi (NOT) | hasta_gecmis + rapor | KE |

**Boolean formülü:**
```
Y7_UYGUN ⇔ Y7.1 ∧ Y7.2 ∧ Y7.3 ∧ Y7.4 ∧ Y7.5 ∧ Y7.6 ∧ Y7.7 ∧ KY7.1 ∧ KY7.2
```

---

### Y8 — Empa+Lina kombi (Glyxambi, Fıkra 8) — TAM detay

**SUT lafzı (8283–8287):**
> "(8) Empagliflozin (SGLT2) ve linagliptin (DPP-4) kombine preperatları; **metformin ve/veya sülfonilüre ve empagliflozin veya linagliptinden biri ile birlikte kullanılmasına rağmen yeterli glisemik kontrol sağlanamamış** hastalarda, **endokrinoloji uzman hekimleri ile iç hastalıkları uzman hekimlerince veya bu hekimlerce düzenlenen uzman hekim raporu ile tüm hekimlerce** reçete edilebilir. Linagliptin ve empagliflozin kombinasyonu, **diğer DPP-4 antagonistleri, SGLT2 inhibitörleri ve GLP-1 analogları ile birlikte ödenmez.**"

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| Y8.1 | Hasta önceden (Met ve/veya Sulfo) KULLANMIŞ | AND-zorunlu | hasta ilaç geçmişi | YOK |
| Y8.2 | Hasta önceden Empa VEYA Lina'dan biri KULLANMIŞ | AND-zorunlu | hasta ilaç geçmişi | YOK |
| Y8.3 | Bu altyapıya rağmen yetersiz glisemik kontrol VAR | RAPORLU yolda AND | rapor metni | KE (RAPORSUZ yolda **bilgi**) |
| Y8.4 | Reçete hekimi ∈ {Endo, IH} | RAPORSUZ yol (tek-atom) | hekim_brans | YOK |
| Y8.5 | Uzman raporu (Endo/IH) | RAPORLU yol AND | rapor_brans | YOK |
| KY8.1 | Aynı reçetede diğer DPP-4 (lina hariç) YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE |
| KY8.2 | Aynı reçetede diğer SGLT-2 (empa hariç) YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE |
| KY8.3 | Aynı reçetede GLP-1 analoğu YOK (NEG) | AND-kombi (NOT) | recete_ilaclari | KE |

**Boolean formülü (PARALEL-YOL kalıbı, 2026-05-25):**
```
Y8_UYGUN ⇔ Y8.1 ∧ Y8.2 ∧
           ( [ Y8.4 ]                  ; RAPORSUZ YOL
             ∨
             [ Y8.5 ∧ Y8.3 ] )         ; RAPORLU YOL
           ∧ KY8.1 ∧ KY8.2 ∧ KY8.3
```

> **Açık soru:** SUT lafzı "diğer DPP-4" mü yoksa "DPP-4 dahil her" mı? Yorum: Glyxambi zaten lina içeriyor; başka bir DPP-4 (lina/sita/vilda/...) ek eklenirse dup-tedavi → ödenmez. Bu yorumla KY8.1 lina HARİÇ tüm DPP-4'leri sayar.

---

### Y9_KAPSAM_DISI — Diğer GLP-1

```
Liraglutid, semaglutid, dulaglutid, tirzepatid SUT 4.2.38 kapsamında değil.
→ Her zaman UYGUN_DEĞİL ("SUT 4.2.38 kapsamı dışı")
```

---

### Y_KY — SGLT-2 / Kalp Yetmezliği endikasyonu (SUT 4.2.74-1) **YENİ**

**SUT lafzı (8935–8940):**
> "(1) Dapagliflozin veya empagliflozin; **standart kalp yetmezliği tedavisini (anjiyotensin dönüştürücü enzim inhibitörleri veya anjiyotensin reseptör blokörleri grubundan birini ve beta blokör ve aldosteron antagonistleri) kullanıyor olması veya kullanamıyorsa, her birinin kullanılamama gerekçesinin raporda belirtilmesi koşuluyla**; **düşük ejeksiyon fraksiyonlu (sol ventrikül EF değeri ≤ %40) semptomatik (NYHA sınıf II-IV) kronik kalp yetersizliği bulunan** ve **eGFR düzeyi uygun olan (empagliflozin için eGFR ≥20 mL/dak/1,73 m², dapagliflozin için eGFR ≥ 25 mL/dak/1,73 m²)** hastalarda, standart tedaviye ilave olarak kullanılması halinde tedaviye başlanır. Bu durumların belirtildiği **en az bir kardiyoloji uzman hekiminin yer aldığı 1 yıl süreli sağlık kurulu raporuna** istinaden tüm hekimler tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır."

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| KY1a | Standart KY tedavi VAR: (ACE-İ ∨ ARB) ∧ BB ∧ MRA hepsi kullanılıyor | OR (üst, ≥1) | hasta ilaç geçmişi + aktif reçete diğer kalemleri | KE |
| KY1b | Kullanılamama gerekçesi raporda belirtildi (her biri için) | OR (üst, ≥1) | rapor metni ("kullanılamadı/kontrendike/intolerans") | KE |
| KY2 | Kronik kalp yetersizliği VAR | AND-zorunlu | ICD I50.x + rapor metni | YOK |
| KY3 | EF ≤ %40 (sol ventrikül) | AND-zorunlu | rapor metni (`EF[^a-z]{0,5}%?(\d+)`) | KE |
| KY4 | NYHA sınıf II–IV (semptomatik) | AND-zorunlu | rapor metni (`NYHA[^a-z]{0,5}([IV]+)`) | KE |
| KY5 | eGFR uygun (dapa ≥25 / empa ≥20) | AND-zorunlu | rapor metni (`eGFR[^a-z]{0,5}(\d+)`) | KE |
| KY6 | SK raporu VAR (1 yıl süreli — süre bilgi/KE) | AND-yetki | rapor_tip + süre | YOK (süre→bilgi) |
| KY7 | Heyette ≥1 kardiyoloji uzmanı | AND-yetki | rapor_heyet | YOK |

**Boolean formülü:**
```
Y_KY_UYGUN ⇔ (KY1a ∨ KY1b) ∧ KY2 ∧ KY3 ∧ KY4 ∧ KY5 ∧ KY6 ∧ KY7
```

> **Açık soru:** KY1a için "her üç sınıf da kullanıyor" mu yoksa "her sınıftan en az bir kullanım" mı? Lafzen: "ACE-İ VEYA ARB grubundan birini" (alt-OR) + "BB" + "aldosteron antagonisti" → toplamda 3 sınıfın hepsi gerekiyor: `((ACE-İ ∨ ARB) ∧ BB ∧ MRA)`. KY1a bu kompozit atomu temsil eder.

---

### Y_KBH — SGLT-2 / Kronik Böbrek Hastalığı endikasyonu (SUT 4.2.74-2) **YENİ**

**SUT lafzı (8942–8946):**
> "(2) Dapagliflozin veya empagliflozin, kronik böbrek hastalığının tedavisinde; **renin-anjiyotensin-aldosteron sistemi inhibitörü alan** ve **en az 3 ay süreli persistan proteinürisi olan (idrar ACR (Albumin/Kreatinin oranı) ≥ 200mg/g veya PCR (Protein/Kreatinin oranı) >300mg/g)** ve **eGFR düzeyi uygun olan (empagliflozin için eGFR ≥ 20 mL/dak/1,73 m², dapagliflozin için eGFR ≥ 25 mL/dak/1,73 m²)** hastalarda tedaviye başlanır. Bu durumların belirtildiği **en az bir nefroloji uzman hekiminin yer aldığı sağlık kurulu raporuna** istinaden tüm hekimler tarafından reçete edilmesi halinde bedelleri Kurumca karşılanır."

| # | Atom | Op | Kaynak | Sessiz |
|---|---|---|---|---|
| KBH1 | KBH endikasyonu VAR | AND-zorunlu | ICD N18.x + rapor metni ("KBH/kronik böbrek hastalığı") | YOK |
| KBH2 | RAAS-İ kullanıyor (ACE-İ veya ARB) | AND-zorunlu | hasta ilaç geçmişi + aktif reçete diğer kalemleri + rapor metni | KE |
| KBH3 | Persistan proteinüri ≥ 3 ay (süre lafzı) | AND-zorunlu | rapor metni (`persistan` + `3 ay` veya benzeri) | KE |
| KBH4a | ACR ≥ 200 mg/g | OR (≥1) | rapor metni (`ACR[^a-z]{0,5}(\d+)`) | KE |
| KBH4b | PCR > 300 mg/g | OR (≥1) | rapor metni (`PCR[^a-z]{0,5}(\d+)`) | KE |
| KBH5 | eGFR uygun (dapa ≥25 / empa ≥20) | AND-zorunlu | rapor metni | KE |
| KBH6 | SK raporu VAR | AND-yetki | rapor_tip | YOK |
| KBH7 | Heyette ≥1 nefroloji uzmanı | AND-yetki | rapor_heyet | YOK |

**Boolean formülü:**
```
Y_KBH_UYGUN ⇔ KBH1 ∧ KBH2 ∧ KBH3 ∧ (KBH4a ∨ KBH4b) ∧ KBH5 ∧ KBH6 ∧ KBH7
```

> **Açık soru:** 4.2.74-2'de süre lafzı "1 yıl" geçmiyor. Default rapor süresi mi (1 yıl) yoksa süresiz mi? Mevcut 4.2.74-1'de "1 yıl" var, 4.2.74-2'de yok. Tasarım kararı: süre kontrolünü KBH için kaldır (bilgi olarak rapor süresi gösterilebilir ama atom olmaz).

---

## 3b. Üst-VEYA çifti grup-adı konvansiyonu (PARALEL-YOL)

`_genel_sonuc` paralel-yol gruplarını otomatik tanımak için grup adında `‖<yolak>‖` marker'ı arar. Marker iki grup arasında ortak ise bu çift üst-VEYA olarak değerlendirilir:

| Yolak | RAPORSUZ Yol grup adı | RAPORLU Yol grup adı |
|---|---|---|
| Y2 | `‖Y2‖ Raporsuz Yol — Hekim Endo/IH/Pediatri/Kardio/AileHek` | `‖Y2‖ Raporlu Yol — Rapor Endo/IH/Pediatri/Kardio/AileHek` |
| Y3 | `‖Y3‖ Raporsuz Yol — Hekim Endo/IH/Pediatri/Kardio` | `‖Y3‖ Raporlu Yol — Rapor Endo/IH/Pediatri/Kardio` |
| Y4 | `‖Y4‖ Raporsuz Yol — Hekim Endo/IH` | `‖Y4‖ Raporlu Yol — Rapor Endo/IH + Klinik şart` |
| Y6 | `‖Y6‖ Raporsuz Yol — Hekim Endo/IH` | `‖Y6‖ Raporlu Yol — Rapor Endo/IH + Klinik şart` |
| Y8 | `‖Y8‖ Raporsuz Yol — Hekim Endo/IH` | `‖Y8‖ Raporlu Yol — Rapor Endo/IH + Klinik şart` |

**Üst-VEYA hesap tablosu (`_genel_sonuc` davranışı):**

| RAPORSUZ | RAPORLU | Sonuç (üst-OR) |
|---|---|---|
| VAR | * | **VAR** (raporsuz yol geçti) |
| * | VAR | **VAR** (raporlu yol geçti) |
| YOK | YOK | **YOK** (ikisi de geçemedi → UYGUN_DEĞİL) |
| KE  | KE  | **KE** (ikisi de belirsiz → ŞÜPHELİ/ŞARTLI) |
| KE  | YOK | **KE** (rapor branşı yok ama hekim belirsiz → manuel) |
| YOK | KE  | **KE** (hekim Endo değil ama rapor belirsiz → manuel) |

> **NOT:** Bilgi atomları (örn. RAPORSUZ yolda klinik şart) grup adında ekstra `(bilgi)` suffix taşır — matematiğe katılmaz, sadece görsel.

---

## 4. Çapraz Kombi Yasakları (reçete bütünü kontrolü)

Reçete birden fazla diyabet kalemi içeriyorsa **reçete bütünü UYGUN_DEĞİL** olur:

```
¬(DPP-4 ∧ GLP-1)                  ; SUT 4(ç) ve 5(ç)
¬(Y8 ∧ diğer DPP-4 (lina hariç))  ; SUT 8
¬(Y8 ∧ diğer SGLT-2 (empa hariç)) ; SUT 8
¬(Y8 ∧ GLP-1)                     ; SUT 8
¬(Y5 ∧ DPP-4)                     ; SUT 5(ç)
¬(Y7 ∧ DPP-4)                     ; SUT 7
```

**4.2.74 etkileşimleri (yeni):**
- Y_KY / Y_KBH yolakları **4.2.38 kombi yasaklarını miras alır** — dapa/empa hangi SUT'tan ödenirse ödensin, GLP-1/DPP-4 kombi yasakları (Y4-GLP1, Y8) reçete bütününde çalışır.
- Y_KY / Y_KBH yolakları için **ek SGLT-2 yasağı YOK** (4.2.74 lafzında belirtilmemiş).

---

## 5. Akım Şeması (üst seviye)

```
┌─────────────────────────────────────────────────┐
│ Reçete kalemleri (her biri) + rapor + hasta     │
└─────────────────────┬───────────────────────────┘
                      │ her kalem için
                      ▼
        ┌──────────────────────────────┐
        │  DISPATCHER §1.1             │
        │  (etken madde → yolak)       │
        └─────────┬────────────────────┘
                  │
   ┌──┬──┬──┬──┬──┴──┬──┬──┬──┬──┬──┐
   ▼  ▼  ▼  ▼  ▼     ▼  ▼  ▼  ▼  ▼  ▼
   Y1 Y2 Y3 Y3b Y4   Y5 [SGLT-2] Y7 Y8 Y9
                       │
                       ▼
             ┌─────────────────────┐
             │ ALT-DISPATCHER §1.2 │
             │ (KY ∨ KBH ∨ DM)     │
             └────┬─────┬─────┬────┘
                  ▼     ▼     ▼
                 Y_KY  Y_KBH  Y6
                       (her yolak atomları işler)
   │  │  │  │  │     │   │     │    │  │  │
   └──┴──┴──┴──┴──┬──┴───┴─────┴────┴──┴──┘
                  │ kalem-bazlı SartSonuc listesi
                  ▼
   ┌──────────────────────────────────────────────┐
   │  ÇAPRAZ KOMBİ YASAĞI (reçete bütünü)         │
   │  - DPP-4 + GLP-1                            │
   │  - Y8 + diğer DPP-4 / SGLT-2 / GLP-1         │
   │  - Y5 + DPP-4                                │
   │  - Y7 + DPP-4                                │
   └─────────────┬────────────────────────────────┘
                 │
                 ▼
       UYGUN / ŞARTLI / ŞÜPHELİ / UYGUN_DEĞİL
```

---

## 6. Atomik Devre — Y5 Eksenatid (örnek)

```
⊕──[Y5.1 Tip2DM]──[Y5.2 BMI>35]──[Y5.3 Pankreatit YOK(NEG)]──┐
                                                              │
       ┌────── üst-OR (a/b geçiş yolu) ──────┐                │
       │                                     │                │
       ├──[Y5.4a Met/Sulfo max yet → kombi]──┤                │
       │                                     │                │
       └──[Y5.4b Met/Pio+bazal ins yet]──────┘                │
                       │                                      │
       ┌──── ilk/devam dispatcher ─────┐                      │
       │                               │                      │
       ├──İLK──[Y5.6 endo + 1 kutu]────┤                      │
       │                               │                      │
       └─DEVAM─[Y5.7 6ay/1yıl endo rap]┤                      │
                [Y5.8 içerik]          │                      │
                [Y5.9 reçete Endo/IH]──┘                      │
                                                              │
              ──[KY5.1 DPP-4 YOK]──[KY5.2 aktif pankreatit YOK]──⊖
```

---

## 7. Atomik Devre — Y_KY Kalp Yetmezliği (YENİ)

```
⊕──[KY2 Kronik KY VAR (I50.x)]──[KY3 EF≤%40]──[KY4 NYHA II-IV]──┐
                                                                 │
       ┌────── üst-OR (standart tedavi VAR ∨ gerekçe) ──┐        │
       │                                                │        │
       ├──[KY1a (ACE/ARB ∧ BB ∧ MRA) kullanıyor]────────┤        │
       │                                                │        │
       └──[KY1b Kullanılamama gerekçesi raporda]────────┘        │
                       │                                         │
                       ▼                                         │
                [KY5 eGFR dapa≥25 / empa≥20]                     │
                       │                                         │
                       ▼                                         │
                [KY6 SK raporu]──[KY7 Kardiyolog heyette]────────⊖
```

---

## 8. Atomik Devre — Y_KBH Kronik Böbrek (YENİ)

```
⊕──[KBH1 KBH VAR (N18.x)]──[KBH2 RAAS-İ kullanıyor]──[KBH3 Persistan ≥3 ay]──┐
                                                                              │
                       ┌──── üst-OR (proteinüri kriteri) ──┐                  │
                       │                                   │                  │
                       ├──[KBH4a ACR ≥ 200 mg/g]──────────┤                  │
                       │                                   │                  │
                       └──[KBH4b PCR > 300 mg/g]──────────┘                  │
                                  │                                          │
                                  ▼                                          │
                  [KBH5 eGFR dapa≥25 / empa≥20]                              │
                                  │                                          │
                                  ▼                                          │
                  [KBH6 SK raporu]──[KBH7 Nefrolog heyette]──────────────────⊖
```

---

## 9. KARAR DEFTERİ (2026-05-24 — kullanıcı onaylı)

| Karar | Yorum | Davranış |
|---|---|---|
| **S1** | KY1a (standart KY tedavi) yerel ilaç DB'sinde yoksa → **KE** | Başka eczane bilgi eksikliğini KE say (memory: [[feedback-baska-eczane-ke]]). ŞÜPHELİ olur. |
| **S2** | Y3b.7 (24 ay sonra mı) → **rapor metninden "ilk rapor tarihi" parse**, yoksa KE | Aktif raporda `\bilk\s*rapor.{0,30}(\d{2}[./-]\d{2}[./-]\d{2,4})` ara. Bulamazsa KE → ŞÜPHELİ. |
| **S3** | Y5/Y7 BMI > 35 → **rapor lafzı öncelikli**, yoksa şu anki BMI (DB) | Rapor metninde "tedavi başlangıcında BMI/VKİ \d+" varsa onu kullan; yoksa hasta kilo/boy → BMI. |
| **S4** | Y8.1/Y8.2 önceki tedavi → **yerel DB'de varsa VAR**, yoksa KE | S1 ile aynı kalıp; başka eczane bilinmiyor → KE. |
| **S5** | SGLT-2 alt-dispatcher → **aktif rapor ibaresi belirler** | "kalp yetersizliği/EF/NYHA/I50" → Y_KY; "böbrek/proteinüri/ACR/PCR/N18" → Y_KBH; "diyabet/glisemik/E11" → Y6. Hiçbiri yoksa Y6 default + `dispatcher_belirsiz=True` manuel uyarı. |
| **S6** | 4.2.74 yolaklarında **4.2.38 kombi yasakları aynen geçerli** | DPP-4+GLP-1 ve Y8/Y5/Y7 özel yasakları Y_KY/Y_KBH için de reçete bütününde çalışır. |
| **S7** | Glyxambi (Empa+Lina sabit kombi) → **her zaman Y8** | 4.2.74 lafzen "dapagliflozin veya empagliflozin" tek başına demek; sabit kombiyi kapsamaz. |
| **S8** | Eski `kontrol_diyabet_dpp4_sglt2` → **wrapper/alias** | `kontrol_diyabet_dpp4_sglt2 = diyabet_kontrol_4_2_38` alias. GUI'de hiçbir değişiklik yok. |

### S1 — Y_KY KY1a (standart KY tedavi) bypass kaynağı
Aktif reçetede dapa/empa varsa, hasta zaten ACE-İ/ARB+BB+MRA reçetelerini başka eczanelerden alıyor olabilir. Yerel `hasta_satis` DB'de bulunamayan ACE/ARB/BB/MRA için:
- **Seçenek A:** Bulunmazsa KE (memory: [[feedback-baska-eczane-ke]] kuralına uy)
- **Seçenek B:** Rapor metnine "kullanılamama gerekçesi" yazılmamışsa YOK (mevzuat lafzı sıkı yorumu)
- **Seçenek C:** Hasta geçmiş raporlarında "standart KY tedavisi altında" lafzı varsa bypass VAR

### S2 — Y3b.7 (24 ay dispatcher)
Hasta önceki rapor başlangıç tarihi yoksa varsayım:
- **Seçenek A:** İlk rapor varsay (Y3b.4 endo zorunlu) — sıkı
- **Seçenek B:** KE → ŞÜPHELİ (manuel doğrulama)

### S3 — Y5/Y7 BMI tedavi başlangıcı şartı
"Tedavi başlangıcında BMI > 35" — şu an mı yoksa ilk reçete tarihinde mi? Hasta zaman içinde kilo kaybetmiş olabilir.
- **Seçenek A:** Mevcut BMI (DB) yeterli — pratik
- **Seçenek B:** Rapor metninde "tedavi başlangıcında BMI" lafzını ara, yoksa KE — sıkı

### S4 — Y8.1/Y8.2 (önceden Met/Sulfo + Empa/Lina kullanım)
Hasta önceki ilaç geçmişi yerel DB'de yoksa:
- **Seçenek A:** KE → ŞÜPHELİ (memory: [[feedback-baska-eczane-ke]] kuralına uy)
- **Seçenek B:** Rapor metnine "önceden empa/lina + met/sulfo" lafzını ara, varsa VAR

### S5 — Dispatcher §1.2 (SGLT-2 → Y6 / Y_KY / Y_KBH)
Hasta hem KY hem KBH hem DM hastası (sık görülen kombinasyon). Yolak seçimi:
- **Seçenek A:** En spesifik (en çok atom karşılayan) yolak kazanır — heuristik
- **Seçenek B:** Aktif rapor "kalp yetersizliği" / "böbrek hastalığı" / "diyabet" ana endikasyon ibarelerinden hangisini öncüllüyorsa o
- **Seçenek C:** Sırayla 3 yolak çalıştırılır + en yüksek skorlu rapor edilir (UI'da 3 sekme)

### S6 — Y_KY ve Y_KBH için DPP-4/GLP-1 kombi yasağı uygulanır mı?
4.2.74 lafzında kombi yasağı YOK. Ama dapa/empa farklı SUT'tan da ödense aynı ilaç (4.2.38'in çapraz kombi'sine takılır).
- **Seçenek A:** Çapraz kombi sadece 4.2.38 yolaklarında — Y_KY/Y_KBH muaf (lafzen sıkı)
- **Seçenek B:** Çapraz kombi tüm SGLT-2 reçetelerinde — pratik (memory: [[feedback-sut-baslik-ortak-ayri-sema]] ile çelişebilir)

### S7 — Glyxambi (Y8) için 4.2.74 endikasyonu var mı?
Empa+Lina kombi 4.2.74 yolağına (KY/KBH) düşer mi yoksa sadece Y8 (4.2.38-8) mu?
- **Seçenek A:** Sabit kombi her zaman Y8 (en spesifik)
- **Seçenek B:** Aktif rapor KY/KBH ise Y_KY/Y_KBH'a yönlendir (empa bileşeni endikasyonu karşılıyor)

### S8 — Mevcut `kontrol_diyabet_dpp4_sglt2` (eski motor) ne olacak?
- **Seçenek A:** Wrapper yap — `kontrol_diyabet_dpp4_sglt2 = diyabet_kontrol_4_2_38` alias
- **Seçenek B:** Sil — GUI yeni motoru doğrudan çağırsın
- **Seçenek C:** Bırak — geriye dönük uyumluluk için kalsın (memory: [[project-diyabet-4-2-74-ek-yolak]] referans verir)

---

## 10. İmplementasyon haritası (kod yapısı)

`recete_kontrol/diyabet_4_2_38.py` (yeni motor, hâlihazırda kısmî):

```
diyabet_kontrol_4_2_38(ilac_sonuc)                  # Public entrypoint
  ├─ yolak_belirle(ilac_sonuc)                       # §1.1 dispatcher
  │    └─ _sglt2_alt_dispatcher(ilac_sonuc)          # §1.2 SGLT-2 → Y6/Y_KY/Y_KBH (YENİ)
  ├─ Paylaşımlı atomlar (mevcut + yeni):
  │    ├─ atom_hekim_brans_uygun(...)
  │    ├─ atom_uzman_raporu_brans(...)
  │    ├─ atom_metformin_sulfo_max_yetersiz(...)
  │    ├─ atom_bmi_35_ustu(...)                       (yeni)
  │    ├─ atom_akut_pankreatit_yok_neg(...)           (yeni)
  │    ├─ atom_tip2_dm_var(...)                       (yeni)
  │    ├─ atom_ef_40_alti(...)                        (yeni — Y_KY)
  │    ├─ atom_nyha_2_4(...)                          (yeni — Y_KY)
  │    ├─ atom_egfr_uygun(...)                        (yeni — Y_KY/Y_KBH)
  │    ├─ atom_raas_kullaniyor(...)                   (yeni — Y_KBH)
  │    ├─ atom_proteinuri_persistan(...)              (yeni — Y_KBH)
  │    ├─ atom_standart_ky_tedavi(...)                (yeni — Y_KY)
  │    ├─ atom_kullanilamama_gerekce(...)             (yeni — Y_KY)
  │    ├─ atom_heyet_uzman_var(brans=...)             (yeni — Y_KY/Y_KBH/Y3b)
  │    ├─ atom_onceden_kullanilmis_insulin(...)       (yeni — Y3b)
  │    ├─ atom_labil_hipo_regulasyon_yok(...)         (yeni — Y3b)
  │    ├─ atom_yetersiz_glisemik_kontrol(...)         (yeni — Y7/Y8)
  │    ├─ atom_kombi_yasak_neg(grup=...)              (yeni — KY5/KY7/KY8)
  │    └─ atom_24_ay_sonra_mi(...)                    (yeni — Y3b)
  ├─ Yolak fonksiyonları:
  │    ├─ y1_kontrol      (mevcut)
  │    ├─ y2_kontrol      (mevcut)
  │    ├─ y3_kontrol      (mevcut)
  │    ├─ y3b_kontrol     (REWRITE)
  │    ├─ y4_kontrol      (mevcut)
  │    ├─ y5_kontrol      (REWRITE)
  │    ├─ y6_kontrol      (mevcut + bypass geliştirme)
  │    ├─ y7_kontrol      (REWRITE)
  │    ├─ y8_kontrol      (REWRITE)
  │    ├─ y9_kapsam_disi_kontrol (mevcut)
  │    ├─ y_ky_kontrol    (YENİ)
  │    └─ y_kbh_kontrol   (YENİ)
  └─ capraz_kombi_yasak(ilac_sonuc, aktif_yolak)     # §4 (mevcut + 4.2.74 entegrasyonu)
```

Test: `test_diyabet_4_2_38.py` (yeni dosya) — her yolak için ≥1 UYGUN + ≥1 UYGUN_DEĞİL + ≥1 ŞÜPHELİ + çapraz kombi + DeMorgan + sessizlik edge case.

GUI rewire: `aylik_recete_sorgu_gui.py::_diyabet_kontrol_baslat` (line ~23437) → `diyabet_kontrol_4_2_38` çağır. Eski `kontrol_diyabet_dpp4_sglt2` wrapper veya silinir (S8 cevabına göre).
