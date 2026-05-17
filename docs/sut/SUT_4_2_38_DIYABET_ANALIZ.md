# SUT 4.2.38 — Diyabet Tedavisinde İlaç Kullanım İlkeleri
## Atomik Devre Şeması + Mantıksal Formülasyon

> Kaynak: mevzuat.gov.tr, MevzuatNo=17229 (SGK SUT). 8 fıkra, 9 yolak.
> Çalışılmış pilot: YOAK 4.2.15.D (bkz. `docs/SUT_MANTIK_SEMA_PROTOKOLU.md`).
> Bu belge `recete_kontrol/sut_kontrolleri.py` içindeki `kontrol_diyabet_dpp4_sglt2`
> implementasyonunun **donmuş tasarım belgesi**dir. Mevzuat değişirse buradan
> başlanır.

---

## 0. Yolak haritası

| Yolak | İlaç sınıfı | Fıkra |
|---|---|---|
| **Y1** | Metformin / Sülfonilüre / Met+Sulfo kombi / Akarboz / İnsan insülini | (1) |
| **Y2** | Repaglinid (+kombi) / Nateglinid / OAD kombineleri | (2) |
| **Y3** | Analog insülin / Pioglitazon / Pio+OAD / Pio+insülin | (3) |
| **Y3b** | İnsülin Degludek+Aspart (Ryzodeg) | (3)(b) |
| **Y4** | DPP-4 antagonistleri (sita/vilda/saksa/lina/alo) + kombineleri | (4) |
| **Y5** | Eksenatid | (5) |
| **Y6** | SGLT-2 inhibitörleri (dapa/empa) + kombineleri | (6) |
| **Y7** | İnsülin Glarjin+Liksisenatid (Soliqua) | (7) |
| **Y8** | Empagliflozin+Linagliptin kombi (Glyxambi) | (8) |
| **Y9_KAPSAM_DISI** | Diğer GLP-1 (liraglutid/semaglutid/dulaglutid/tirzepatid) | yok |

---

## 1. Dispatcher (etken madde → yolak)

Öncelik sırası (yukarıdan aşağı, ilk eşleşen kazanır):

```
1. Sabit kombi preparat? (en spesifik)
   - Empagliflozin + Linagliptin     → Y8
   - İnsülin Glarjin + Liksisenatid  → Y7
   - İnsülin Degludek + Aspart       → Y3b
2. Eksenatid (tek başına)              → Y5
3. Diğer GLP-1 (lira/sema/dula/tirze)  → Y9_KAPSAM_DISI (UYGUN_DEĞİL)
4. DPP-4 (sita/vilda/saksa/lina/alo)
   + Met/Sulfo/SGLT2 kombineleri      → Y4
5. SGLT-2 (dapa/empa) + kombineleri    → Y6
6. Analog insülin / Pioglitazon
   + Pio kombineleri                  → Y3
7. Repaglinid / Nateglinid /
   OAD kombineleri                    → Y2
8. Met / Sulfo / Akarboz / İnsan ins. → Y1
```

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
| O13 | KBY VAR | ICD N18.x + rapor metni ("KBY/kronik böbrek yetmezliği/diyaliz") | YOK |
| O14 | İlk reçete (hasta satış geçmişi) | hasta satış geçmişi | KE (geçmiş yok) |

---

## 3. Yolak atomları (özet)

### Y1 — Tüm hekimler (Fıkra 1)
```
Y1_UYGUN ⇔ kalem ∈ Y1-sınıfı  (rapor/uzman şartı YOK)
```

### Y2 — Repaglinid/Nateglinid/OAD kombi (Fıkra 2)
```
Y2.1 = hekim_branş ∈ {Endo, IH, Pediatri, Kardiyo, Aile Hek}
Y2.2 = uzman raporu (yukarıdaki branşlardan biri tarafından düzenlenmiş)
Y2_UYGUN ⇔ Y2.1 ∨ Y2.2
```

### Y3 — Analog insülin / Pioglitazon (Fıkra 3)
```
Y3.1 = hekim_branş ∈ {Endo, IH, Pediatri, Kardiyo}    (Aile hek YOK!)
Y3.2 = uzman raporu (yukarıdaki branşlardan)
Y3_UYGUN ⇔ Y3.1 ∨ Y3.2
```

### Y3b — Degludek+Aspart (Fıkra 3(b))
```
Y3b.1 = önceden analog karışım VEYA uzun etkili insülin kullanılmış
Y3b.2 = (labil ∨ sık hipo ∨ hipo risk yüksek ∨ regülasyon yok) — OR(≥1)
Y3b.3 = SK raporu
Y3b.4 = heyette ≥1 endokrinoloji uzmanı    (ilk 24 ay)
Y3b.5 = heyette ≥1 IH uzmanı (24 ay sonrası geçişli)
Y3b.6 = reçete hekimi ∈ {Endo, IH}
Y3b.7 = ilk rapordan 24 ay sonra mı? (hasta geçmişi)

Y3b_UYGUN ⇔ Y3b.1 ∧ Y3b.2 ∧ Y3b.3 ∧
            (¬Y3b.7 → Y3b.4) ∧ (Y3b.7 → (Y3b.4 ∨ Y3b.5)) ∧ Y3b.6
```

### Y4 — DPP-4 antagonistleri (Fıkra 4)
```
Y4.1 = Met max doz yet. ∨ Sulfo max doz yet.    (klinik şart)
Y4.2 = reçete hekimi ∈ {Endo, IH}
Y4.3 = uzman raporu (Endo veya IH)
Y4.4 = (saksa 2.5mg ise) → KBY VAR
Y4.5 = (alo 12.5mg ise) → KBY VAR
KY4.1 = aynı reçetede GLP-1 analoğu YOK

Y4_UYGUN ⇔ Y4.1 ∧ (Y4.2 ∨ Y4.3) ∧ (saksa2.5 → Y4.4) ∧ (alo12.5 → Y4.5) ∧ KY4.1
```

### Y5 — Eksenatid (Fıkra 5)
```
Y5.1 = Tip 2 DM VAR
Y5.2 = BMI > 35 (tedavi başlangıcı)
Y5.3 = akut pankreatit öyküsü YOK  (NEG, sessiz=KE)
Y5.4a = Met/Sulfo max doz yet. → kombi olarak (5-a yolu)
Y5.4b = Met/Pio kombi VEYA tek bazal insülin yet. → bazal ek (5-b yolu)
Y5.5 = ilk reçete mi? (hasta satış geçmişi)
Y5.6 = (ilk) endo uzmanı + 1 kutu (2x5mcg)
Y5.7 = (devam) 6 ay endo raporu VEYA 1 yıl endo raporu
Y5.8 = (devam) rapor içeriği: devam kararı + başlama kriterleri + max dozlar
Y5.9 = (devam) reçete hekimi ∈ {Endo, IH}
KY5.1 = aynı reçetede DPP-4 antagonisti YOK
KY5.2 = aktif tedavi sırasında akut pankreatit gelişmedi

Y5_UYGUN ⇔ Y5.1 ∧ Y5.2 ∧ Y5.3 ∧ (Y5.4a ∨ Y5.4b) ∧
           (Y5.5 → Y5.6) ∧ (¬Y5.5 → (Y5.7 ∧ Y5.8 ∧ Y5.9)) ∧ KY5.1 ∧ KY5.2
```

### Y6 — SGLT-2 inhibitörleri (Fıkra 6)
```
Y6.1 = Met max doz yet. ∨ Sulfo max doz yet.
Y6.2 = reçete hekimi ∈ {Endo, IH}
Y6.3 = uzman raporu (Endo/IH)
Y6_UYGUN ⇔ Y6.1 ∧ (Y6.2 ∨ Y6.3)
```

### Y7 — Glarjin+Liksisenatid (Soliqua, Fıkra 7)
```
Y7.1 = Yetişkin Tip 2 DM VAR
Y7.2 = BMI > 35
Y7.3 = akut pankreatit öyküsü YOK (NEG)
Y7.4 = yetersiz glisemik kontrol VAR
Y7.5 = metformin + diyet/egzersiz altyapı (zorunlu)
Y7.6 = 1 yıl endo SK raporu
Y7.7 = reçete hekimi ∈ {Endo, IH}
KY7.1 = aynı reçetede DPP-4 YOK
KY7.2 = aktif tedavi sırasında akut pankreatit gelişmedi

Y7_UYGUN ⇔ Y7.1 ∧ Y7.2 ∧ Y7.3 ∧ Y7.4 ∧ Y7.5 ∧ Y7.6 ∧ Y7.7 ∧ KY7.1 ∧ KY7.2
```

### Y8 — Empa+Lina kombi (Glyxambi, Fıkra 8)
```
Y8.1 = Met VE/VEYA Sulfo KULLANIYOR
Y8.2 = Empa VEYA Lina'dan biri zaten kullanılmış
Y8.3 = Y8.1 + Y8.2 birlikte yetersiz glisemik kontrol
Y8.4 = reçete hekimi ∈ {Endo, IH}
Y8.5 = uzman raporu
KY8.1 = diğer DPP-4 YOK (lina hariç)
KY8.2 = diğer SGLT-2 YOK (empa hariç)
KY8.3 = GLP-1 analoğu YOK

Y8_UYGUN ⇔ Y8.1 ∧ Y8.2 ∧ Y8.3 ∧ (Y8.4 ∨ Y8.5) ∧ KY8.1 ∧ KY8.2 ∧ KY8.3
```

### Y9_KAPSAM_DISI — Diğer GLP-1
```
Liraglutid, semaglutid, dulaglutid, tirzepatid SUT 4.2.38 kapsamında değil.
→ Her zaman UYGUN_DEĞİL ("SUT 4.2.38 kapsamı dışı")
```

---

## 4. Çapraz Kombi Yasakları (reçete bütünü kontrolü)

Reçete birden fazla diyabet kalemi içeriyorsa **reçete bütünü UYGUN_DEĞİL** olur:

```
¬(DPP-4 ∧ GLP-1)                  ; SUT 4(ç) ve 5(ç)
¬(Y8 ∧ diğer DPP-4)               ; SUT 8
¬(Y8 ∧ diğer SGLT-2)              ; SUT 8
¬(Y8 ∧ GLP-1)                     ; SUT 8
¬(Y5 ∧ DPP-4)                     ; SUT 5(ç)
¬(Y7 ∧ DPP-4)                     ; SUT 7
```

---

## 5. Akım Şeması (üst seviye)

```
┌─────────────────────────────────────────────────┐
│ Reçete kalemleri (her biri) + rapor + hasta     │
└─────────────────────┬───────────────────────────┘
                      │ her kalem için
                      ▼
        ┌──────────────────────────────┐
        │  DISPATCHER (etken madde →   │
        │  yolak, öncelik sırasıyla)   │
        └─────────┬────────────────────┘
                  │
   ┌──┬──┬──┬──┬──┴──┬──┬──┬──┬──┐
   ▼  ▼  ▼  ▼  ▼     ▼  ▼  ▼  ▼  ▼
   Y1 Y2 Y3 Y3b Y4   Y5 Y6 Y7 Y8 Y9_KAPSAM_DISI
                       (her yolak atomları işler)
   │  │  │  │  │     │  │  │  │  │
   └──┴──┴──┴──┴──┬──┴──┴──┴──┴──┘
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
       UYGUN / ŞÜPHELİ / UYGUN_DEĞİL
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

## 7. Karar Ağacı — Y4 DPP-4 (örnek)

```
                  Reçetede DPP-4 antagonisti var
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
  Saksa 2.5mg / Alo 12.5mg?                 Diğer DPP-4 formu
            │                                   │
      ┌─────┴─────┐                             ▼
      ▼           ▼                  Y4.1 Met/Sulfo max yet.?
   KBY var?    UYGUN_DEĞİL                      │
      │       (form yanlış)        ┌────────────┼────────────┐
   ┌──┴──┐                         KE           YOK         VAR
   ▼     ▼                          │            │           │
 Devam UYGUN_DEĞİL                ŞÜPHELİ    UYGUN_DEĞİL    Devam
                                                             │
                                                  Y4.2/Y4.3 hekim?
                                                  ┌─────────┼────────┐
                                                Endo/IH  Raporlu   Diğer
                                                  │         │        │
                                                Devam    Devam   UYGUN_DEĞİL
                                                  │         │
                                                  └────┬────┘
                                                       │
                                                  KY4.1 GLP-1 YOK?
                                                  ┌────┴────┐
                                                YOK       VAR
                                                  │        │
                                                UYGUN   UYGUN_DEĞİL
```

---

## 8. İmplementasyon haritası (kod yapısı)

`recete_kontrol/sut_kontrolleri.py` içinde:

```
kontrol_diyabet_dpp4_sglt2(ilac_sonuc)           # Public wrapper (var, korunur)
  └─ _kontrol_diyabet_dpp4_sglt2_impl              # Komple yeniden yazılır
       ├─ _diy_yolak_belirle(...)                  # Dispatcher
       ├─ _diy_atom_bmi_35_ustu(...)              # Paylaşımlı atomlar
       ├─ _diy_atom_akut_pankreatit_yok(...)
       ├─ _diy_atom_metformin_max_yetersiz(...)
       ├─ _diy_atom_sulfonilure_max_yetersiz(...)
       ├─ _diy_atom_hekim_brans(...)
       ├─ _diy_atom_uzman_raporu_brans(...)
       ├─ _diy_atom_kby(...)
       ├─ _diy_atom_ilk_recete_mi(...)
       ├─ _diy_y1_kontrol(...)                    # Yolak fonksiyonları
       ├─ _diy_y2_kontrol(...)
       ├─ _diy_y3_kontrol(...)
       ├─ _diy_y3b_kontrol(...)
       ├─ _diy_y4_kontrol(...)
       ├─ _diy_y5_kontrol(...)
       ├─ _diy_y6_kontrol(...)
       ├─ _diy_y7_kontrol(...)
       ├─ _diy_y8_kontrol(...)
       ├─ _diy_y9_kapsam_disi_kontrol(...)
       └─ _diy_capraz_kombi_yasak(...)             # Reçete bütünü çapraz
```

Test: `test_diyabet_4_2_38.py` — 10+ akıl testi (her yolak için ≥1 UYGUN + ≥1 UYGUN_DEĞİL + ≥1 ŞÜPHELİ + 1 çapraz kombi).
