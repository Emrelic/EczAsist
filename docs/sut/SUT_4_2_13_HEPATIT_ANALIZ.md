# SUT 4.2.13 — Hepatit Tedavisi
## Atomik Devre Şeması + Mantıksal Formülasyon (12 Yolak)

> Kaynak: mevzuat.gov.tr, MevzuatNo=17229 (SGK SUT) — `docs/sut/SUT_tam_metin.txt:5452-5646`.
> Çalışılmış pilot: YOAK 4.2.15.D (bkz. `docs/SUT_MANTIK_SEMA_PROTOKOLU.md`).
> Bu belge `recete_kontrol/hepatit_kontrol.py` (3381 satır) implementasyonunun
> **donmuş tasarım belgesi**dir. Mevzuat değişirse buradan başlanır.
> Versiyon: 2026-07-12 (revize 4 — DENETİM DÜZELTMELERİ, aşağıya bakınız)
> Test sayısı: `test_hepatit_atomik.py` 16/16 ∧ `test_hepatit_baslangic_devam.py` 21/21
> ∧ `test_hepatit_denetim_2026_07.py` 9/9 = 46/46 pass

---

## ⚠️ 2026-07-12 DENETİM DÜZELTMELERİ (revize 4)

Tam yolak denetiminde bulunan YANLIŞ-ONAY (false-positive) hataları düzeltildi.
Kök neden: düz `ust_or_ciftleri` + grup-içi `veya_grubu` modeli "VEYA-kolu-içinde-VE"
(`(A∧B)∨(C∧D)`) ifade edemiyordu; bir gruptaki tek `veya_grubu=True` atom TÜM
grubu OR'a çeviriyordu (`_hep_genel_sonuc:veya_flag=any(...)`).

**Çözüm:** iç-içe dallar Python'da tek verdict atomuna indirgeniyor
(`_hep_and_durum` / `_hep_or_durum` / `_hep_esik_durum` / `_hep_uc_deger`);
detay koşulları `(bilgi)` gruplarında şema görünürlüğü için tutuluyor.

| # | Yolak | Hata → Düzeltme |
|---|-------|-----------------|
| K1 | Y9/Y10 | Rejim OR'u endikasyon kilidini bypass ediyordu (dekompanse+SVV → UYGUN). Her dal (hasta grubu ∧ rejim) tek atomda AND ile çözülüyor. |
| B1 | Y1 | (1)(a)(2) `ALT ∧ (FIB-4∨APRI)` zinciri düz 3'lü OR'a düşmüştü (ALT tek başına geçiyordu). Yol-a tek atom: `DNA≥2000 ∧ [(HAI≥6∨fib≥2) ∨ (ALT>ÜS∧(FIB4∨APRI))]`. |
| PIF | Y1 | Pegile IFN kolu (1)(a/b)'ye alternatif OR'du. Artık ek-AND: `(1)(a) endikasyon ∧ (2)(a)`; yol-b (oral-only) PIF için kapalı. |
| Y6 | Akut B | `INR∨PT∨sarılık` üçlü OR idi. Düzeltildi: `(INR≥1,5 ∨ PT>4sn) ∧ (sarılık>4hafta)`. |
| Y2 | Çocuk B | İlaç-yaş uyumu sadece bilgi atomuydu (10 yaşa ETV UYGUN). Sert atom: ETV 16-18 / TDF-TAF 12-18 / LAM 2-18 dışı → YOK. |
| K2 | Y9/Y10 | Dekompanse kanıt (asit∨ensefalopati∨bilirubin>3∨varis) parse edilmiyordu → `_hep_dekompanse_kanit` dala AND. |
| O1 | Y9/Y10 | Kompanse biyopsisiz kriteri (trombosit<150k∨PT≥3sn) HCV'de yoktu → `_hep_kompanse_biyopsisiz_kanit`. |
| K3 | Y10/11/12 | 2./3. basamak (madde 5) yalnız Y9'daydı → tüm HCV yolaklarına eklendi. |
| K4 | Y10 | NS5A türü belirsizken "almamış" (izinli dal) örtük kabul ediliyordu → `tur_belirsiz` bayrağı, belirsizde KE. |
| Y7 | Delta | HBV DNA bulunamayınca YOK (hard-fail) idi → KE (Anti-HDV ile simetrik). |
| Y4 | İmmünsüp | Rapor tarih/sayı reçetede şartı (madde 1) için atom eklendi. |
| O3 | Y10 | Yaş bilinmiyorken erişkin atomu düşüyordu → KE atomu (Y9 ile simetrik). |
| — | test | `test_hepatit_baslangic_devam.py` bozuk import'u (`_hep_atom_etken_devam` → `_hep_etken_degisim_atomlari` refactor'ı) düzeltildi. |

Not: `hep_parse_fib4/apri/...` gibi sayısal parser'lar `[\d\.,]+` greedy olduğundan
cümle-sonu noktasını ("FIB-4: 1.0.") sayıya katıp None dönebilir — bilinen küçük
sağlamlık boşluğu, bu denetim kapsamı dışında (ayrı iş).

### 🔍 İlaç Geçmişini Raporlardan Tara (SUT 4.2.13.1/4 belirsizliği)

DEVAM reçetelerinde "/4 aktif etken önceki tedaviyle aynı mı" atomu, önceki HBV
oral etkeni bilinmediğinde KE (şüpheli) kalır. Kaynak sınırları: Medula ilaç
geçmişi ~1 yıl; kendi-eczane EOS yalnız bu eczane. Raporlar eczane-ötesi ve
kalıcı olduğundan çözüm rapor taramasıdır:

- **Çekirdek:** `hepatit_onceki_etken_raporlardan(tc, ilac, etken, aktif_rapor_tarih)`
  → `rapor_etken_madde_tablosu.hasta_etken_tablo` ile tüm raporların "Rapor Etkin
  Madde Bilgileri" bölümünü tarar, önceki HBV oral etkeni + alt-tip + tarih
  döndürür, aktifle karşılaştırır (`ayni_mi`), `gecmis_etken_gerekce` üretir.
- **Enjeksiyon:** `ilac_sonuc['_gecmis_etken_override']` → `_hep_recete_tipi_tespit`
  bunu `extra['gecmis_etken']` yapar (DB/EOS'tan öncelikli) → /4 atomu KE'den çıkar.
- **GUI:** sağ tık "🔍 İlaç Geçmişini Raporlardan Tara" + "🔍 Raporlardan Etken"
  butonu → sonuç diyaloğu + "Uygula → Kontrolü Yenile" (override enjekte edip tek
  satır yeniden denetlenir). Rapor cache boşsa "🩺 MEDULA Geçmiş Raporlarını Tara"ya
  yönlendirir.
- Test: `test_hepatit_rapor_tarama.py` 8/8.

**Batch EOS ikinci geçişi:** "🦠 HEPATİT B/C" toplu kontrolü ilk geçişte
hasta_tc taşımaz (EOS sorgusuyla batch yavaşlamasın). Sonuç **ŞÜPHELİ** ya da
**DEVAM/BELİRSİZ** olan satırlarda hasta_tc (+rapor_ana_id) enjekte edilip
kontrol tekrar çalıştırılır → `_hep_recete_tipi_tespit` EOS Sinyal 4 (RaporAna
karşılaştırması) + DB drug-history (Sinyal 1/3) çalışır, başlangıç/devam ve /4
önceki-etken netleşir. Yalnız bu satırlar EOS maliyeti öder; EOS hatasında ilk
sonuç korunur (`aylik_recete_sorgu_gui.py:_hepatit_kontrol_baslat`). Kendi
eczane dışı/eski tedaviler EOS'ta yoksa manuel "🔍 Raporlardan Etken" komutu
devreye girer.

---

## 0. Yolak haritası

| Yolak | İlaç sınıfı | SUT Maddesi | Endikasyon |
|---|---|---|---|
| **Y1** | HBV oral + Pegile IFN | 4.2.13.1 | Kronik B Erişkin ≥18 |
| **Y2** | HBV oral + Pegile IFN | 4.2.13.1 (5) | Kronik B Çocuk 2–18 |
| **Y3** | HBV oral | 4.2.13.1.1 | Hepatit B + Siroz |
| **Y4** | HBV oral | 4.2.13.1.2 | Hepatit B + İmmünsüpresif/kemo/monoklonal |
| **Y5** | HBV oral | 4.2.13.1.3 | Karaciğer transplantasyonu (HBV / Anti-HBc+ donör) |
| **Y6** | HBV oral | 4.2.13 (3) | Akut Hepatit B (ciddi klinik) |
| **Y7** | Pegile IFN (+ opsiyonel HBV oral) | 4.2.13.2 | Kronik D / Delta (Anti-HDV+) |
| **Y8** | Pegile IFN | 4.2.13.3.1 | Akut Hepatit C (Ribavirin YASAK) |
| **Y9** | HCV DAA (SVV / GP) | 4.2.13.3.2.A.1 | HCV Erişkin Naive |
| **Y10** | HCV DAA (± Ribavirin) | 4.2.13.3.2.A.2 | HCV Erişkin Deneyimli (NS5A önceki yok ya da var) |
| **Y11** | Pegile IFN + Ribavirin / IFN + Rib / GP | 4.2.13.3.2.B | HCV Çocuk Naive |
| **Y12** | SOF+LED / GP | 4.2.13.3.2.B.1 | HCV Çocuk 12–18 Deneyimli |
| **Y0_KAPSAM_DISI** | HIV ATC J05A* (dolutegravir/abacavir/efavirenz vb.) | — | HEPATIT butonu kapsam dışı — ANTIVIRAL kategorisinde |

---

## 1. Dispatcher (ilaç + endikasyon → yolak)

**Öncelik sırası** (yukarıdan aşağı, ilk eşleşen kazanır). Sinyaller:
1. Etkin madde tipi (HBV_ORAL / HCV_DAA / PEG_IFN / IFN / RIBAVIRIN)
2. ICD-10 (B16 akut B, B17.0 akut D, B17.1 akut C, B18.0/B18.1 kronik B, B18.2 kronik C)
3. Rapor metni anahtar ibareler (akut/kronik/siroz/transplant/immünsüpresif/delta)
4. Yaş (çocuk <18 / erişkin)
5. Önceki HCV tedavisi (naive vs deneyimli — rapor metni + DB)

### 1.1 Yolak seçim akım şeması (ASCII)

```
                         ┌──────────────────────────────┐
                         │  ETKEN TİP TESPİTİ           │
                         │  (_hep_etken_tip → HBV_ORAL/ │
                         │   HCV_DAA/PEG_IFN/IFN/RBV/   │
                         │   NONE)                      │
                         └─────────────┬────────────────┘
                                       │
                            NONE? ─Y──▶ ATLANDI (HIV vs.)
                                       │ N
                                       ▼
                        ┌──────────────────────────────┐
                        │ ENDİKASYON SİNYALLERİ        │
                        │ ICD+metin: akut B / akut C / │
                        │  Delta / transplant / imsup /│
                        │  siroz                       │
                        └─────────────┬────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼ HBV_ORAL                    ▼ PEG_IFN                     ▼ HCV_DAA / IFN(¬akutC) / RBV
   ┌─────────────────┐         ┌──────────────────┐         ┌──────────────────────┐
   │ Akut B?  ─Y▶ Y6│         │ Akut C? ─Y▶ Y8   │         │ Önceki HCV tedavi?   │
   │ Delta?   ─Y▶ Y7│         │ Delta?  ─Y▶ Y7   │         │ (hep_onceki_hcv_*    │
   │ Transp.? ─Y▶ Y5│         │ Y1 (PIF aday)*   │         │  metin + DB)         │
   │ İmsup?   ─Y▶ Y4│         └──────────────────┘         └──────────┬───────────┘
   │ Siroz?   ─Y▶ Y3│                                                 │
   │ Yaş<18?  ─Y▶ Y2│                                  ┌──────────────┴──────────────┐
   │ Default ───▶ Y1│                                  ▼ Yaş <18                     ▼ Erişkin
   └─────────────────┘                          ┌─────────────────┐         ┌─────────────────┐
                                                │ Deneyimli? ─Y▶12│         │ Deneyimli? ─Y▶10│
                                                │ Default ─────▶11│         │ Default ──────▶9│
                                                └─────────────────┘         └─────────────────┘

* Y1'de etken=PEG_IFN ise PIF kolu üst-VEYA çiftine alternatif olarak katılır
  (SUT 4.2.13.1(2)(a) — 2026-05-23 fix, bkz. §3 Boolean formül).
```

### 1.2 Sözel dispatcher (kod ile birebir)

```
ETKİN_TİP=NONE                           → KAPSAM DIŞI (ATLANDI)
Akut B (ICD B16 ∨ "akut hepatit B") ∧ HBV_ORAL  → Y6
Akut C (ICD B17.1 ∨ "akut hepatit C") ∧ PEG_IFN → Y8
Delta (ICD B17.0/B18.0 ∨ "hdv"/"delta"/"anti-hdv") ∧ (PEG_IFN ∨ HBV_ORAL) → Y7
HBV_ORAL ∨ PEG_IFN:
   • transplant ibaresi → Y5
   • immünsüpresif/kemo/monoklonal/rituximab → Y4
   • siroz ibaresi → Y3
   • yaş < 18 → Y2
   • aksi → Y1 (default; PEG_IFN ise Y1 içinde PIF kolu da çalışır)
HCV_DAA ∨ (IFN ∧ ¬akut C) ∨ RIBAVIRIN:
   • yaş < 18:
       önceki HCV tedavi VAR → Y12, aksi Y11
   • erişkin:
       önceki HCV tedavi VAR → Y10, aksi Y9
```

**Belirsiz**: Etkin madde tanınıyor ama hiçbir endikasyon eşleşmiyor → `BELIRSIZ` yolak, KE+manuel.

### 1.3 Başlangıç/devam dallanması (2026-05-21, tüm HBV yolaklarında)

Y1/Y2/Y3 (ve Y4/Y5/Y7 helper çağrısı ile) reçete tipi tespit eder ve atom setini buna göre filtreler:

```
        ┌────────────────────────────────────────────────────┐
        │ _hep_recete_tipi_tespit(ilac_sonuc, metin)         │
        │ Sinyaller:                                         │
        │   • Metin: "başlanması"/"ilk tedavi" → BASLANGIC   │
        │   • Metin: "tedavinin devamı"/"yenileme" → DEVAM   │
        │   • DB (oturum_raporlari.db): aynı etken/hasta     │
        │     önceki reçete VAR → DEVAM güvenli              │
        │   • Çelişki → DEVAM (güvenli karar)                │
        │   • Hiçbiri → BELİRSİZ (atomlar (bilgi) suffix'li) │
        └─────────────────────┬──────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼ BASLANGIC       ▼ DEVAM           ▼ BELİRSİZ
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │ /1 HBV DNA+yol-a │ │ /4 etken değişim │ │ İkisi de (bilgi) │
   │ /1.b 40+ DNA≥20k │ │   gerekçe        │ │ → matematiğe     │
   │ /3 erişkin doz   │ │ /6.a HBsAg/AntiHBs│ │   girmez         │
   │ /2 PIF (opsiyon) │ │ /6.b ≤12 ay son  │ │ → SARTLI_UYGUN   │
   │                  │ │ /7 HBsAg+ devam  │ │                  │
   └──────────────────┘ └──────────────────┘ └──────────────────┘
            │                 │                 │
            └────────┬────────┴─────────────────┘
                     ▼
            ┌──────────────────────────────────────┐
            │ Ortak atomlar (her tip için aktif):  │
            │   • R1 uzman raporu                  │
            │   • R2 reçete yetkili branş          │
            │   • /8 rapor süresi (6 ay/1 yıl)     │
            │   • Geçmiş rapor DB (MEDULA)         │
            └──────────────────────────────────────┘
```

Helper: `_hep_y_baslangic_devam_uygula(ilac_sonuc, metin, kat, etkin_tip, sartlar, detaylar)` — Y1/Y2/Y3/Y7 başında çağrılır, atomları ortak `sartlar` listesine ekler.

---

## 2. Paylaşımlı atomlar (her yolakta veya çoğunda)

| # | Atom | Kaynak | Sessiz default |
|---|---|---|---|
| **R1** | Uzman raporu VAR (gastroenteroloji / enfeksiyon hastalıkları / hepatoloji) | rapor kodu (06.01/14.*/B*) + rapor doktoru branşı + metin | YOK |
| **R2** | Reçete eden hekim yetkili branş (HBV: GE/Enf/Hep/Çocuk SH/İç Hast; HCV: GE/Enf/Çocuk SH/İç Hast) | reçete doktor branşı | YOK |
| **R3** | (HCV özel) Rapor 2./3. basamak sağlık kurumu | rapor "tesis kodu" + metin "2. basamak"/"3. basamak"/"üniversite hastanesi" | KE (ibare yok) |
| **R4** | Rapor süresi limitleri (ilk 6 ay, sonraki 1 yıl; HBV) | rapor başlangıç/bitiş tarihi | KE + (bilgi) |

---

## 3. Y1 — Kronik Hepatit B Erişkin (4.2.13.1)

### SUT lafzı (özet, mevzuat satırları 5462–5519)
> **(1)(a)(1)** HBV DNA ≥ 10.000 kopya/ml (2.000 IU/ml) **VE** [erişkin: HAI ≥ 6 **VEYA** fibrozis ≥ 2]
> **(1)(a)(2)** Erişkin: 3 ay ara ile ALT normalin üst sınırının üzerinde **VE** [FIB-4 > 1.45 **VEYA** APRI > 0.5]
> **(1)(b)** ≥40 yaş **VE** HBV DNA ≥ 20.000 IU/ml → biyopsi yapılmadan oral antiviral
> **(2)** Pegile IFN ek: ALT > 2×ÜS **VE** [(HBeAg(−) ∧ HBV DNA ≤ 10⁷ kopya/ml) **VEYA** (HBeAg(+) ∧ HBV DNA ≤ 10⁹)]; süre ≤ 48 hafta
> **(3)** Oral antiviral başlangıç doz: 100 mg LAM / 600 mg TBV / 245 mg TDF / 0.5 mg ETV / 25 mg TAF
> **(6)** Sonlandırma: HBsAg(+) varsa devam, HBsAg(−) & Anti-HBs(+) sonra ≤12 ay
> **(8)** İlk rapor ≤ 6 ay, sonrakiler ≤ 1 yıl

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Kronik HBV tanısı (ICD B18.0/B18.1 ∨ "kronik hepatit B") | teşhis+metin | AND-endikasyon | KE |
| **A1** | HBV DNA ≥ 2000 IU/ml | rapor metni | AND-yol-a | KE |
| A2 | HAI ≥ 6 | rapor metni | OR-(a-hist) | KE |
| A3 | Fibrozis ≥ 2 | rapor metni | OR-(a-hist) | KE |
| A4 | ALT > ÜS (3 ay ara ile 2 ölçüm) | rapor metni | AND-yol-a-alt | KE |
| A5 | FIB-4 > 1.45 | rapor metni | OR-(a-alt-iç) | KE |
| A6 | APRI > 0.5 | rapor metni | OR-(a-alt-iç) | KE |
| B1 | Yaş > 40 | hasta yaşı | AND-yol-b | KE |
| B2 | HBV DNA ≥ 20.000 IU/ml | rapor metni | AND-yol-b | KE |
| B3 | Reçete oral antiviral (interferon değil) | reçete | AND-yol-b | — |
| P1 | (Pegile IFN için) ALT > 2× ÜS | rapor metni | AND-pif | KE |
| P2 | (Pegile IFN için) HBeAg(−) ∧ DNA ≤ 10⁷ kopya/ml | rapor metni | OR-pif-eag | KE |
| P3 | (Pegile IFN için) HBeAg(+) ∧ DNA ≤ 10⁹ kopya/ml | rapor metni | OR-pif-eag | KE |
| P4 | (Pegile IFN için) Süre ≤ 48 hafta | rapor metni | bilgi | KE+(bilgi) |
| R4 | Rapor süresi limitleri | rapor tarihleri | bilgi | KE+(bilgi) |

### Boolean formül

```
Y1_UYGUN ⇔ R1 ∧ R2 ∧ E1 ∧ [
    YOL-A : A1 ∧ [ (A2 ∨ A3)   ⟵ histoloji
                  ∨ (A4 ∧ (A5 ∨ A6))   ⟵ ALT+skor zinciri
                 ]
    ∨
    YOL-B : B1 ∧ B2 ∧ B3
    ∨
    YOL-PIF : P1 ∧ P_eag   ⟵ etkin=PEG_IFN ise (üst-VEYA'ya eklenir)
              P_eag = (HBeAg(-)∧DNA≤10⁷) ∨ (HBeAg(+)∧DNA≤10⁹)
              (POZ/NEG ayrı atom değil — tek birleşik atom, atom içinde
               OR mantığı durumda çözülür → grup saf AND kalır)
]
```

### Mini akım şeması (Y1 — kronik B erişkin)

```
    ⊕──[R1: Uzman rapor]──[R2: Reçete yetki]──[E1: HBV tanı]──┐
                                                              │
                                            ┌─────────────────┼─────────────────┐
                                            │                 │                 │
                                            ▼ YOL-A           ▼ YOL-B           ▼ YOL-PIF (etken=PEG_IFN)
                                  ┌───────────────────┐ ┌──────────┐ ┌──────────────────┐
                                  │ A1: HBV DNA≥2000  │ │ B1: Yaş  │ │ P1: ALT>2×ÜS     │
                                  │ ∧ (hist ∨ ALT yol)│ │  >40     │ │ ∧ (HBeAg+DNA     │
                                  │                   │ │ ∧ B2: DNA│ │   eşik VAR)      │
                                  │ hist: HAI≥6 ∨    │ │  ≥20.000 │ │                  │
                                  │       fibr≥2     │ │ ∧ B3: po │ │ (HBeAg(-)∧≤10⁷)  │
                                  │ ALT yol: ALT yük │ │  oral    │ │  veya            │
                                  │       ∧ (FIB-4>  │ │  antivir │ │ (HBeAg(+)∧≤10⁹)  │
                                  │     1.45∨APRI>0.5│ │          │ │                  │
                                  └─────────┬─────────┘ └────┬─────┘ └────────┬─────────┘
                                            │  ∨               │  ∨            │
                                            └──────────────────┴───────────────┘
                                                              │
                                                              ▼
                                                          ⊖ (UYGUN)
```

### Mevcut kod uyum (2026-05-23)
✅ `_hep_yolak1_eriskin_b` (line 1631–1875): tüm atomlar üretiliyor, **PIF kolu üst-VEYA çiftine dahil edildi** (`ust_or` listesine etkin=PEG_IFN ise `'(2)(a) Pegile interferon'` prefix'i eklenir).
✅ HBeAg POZ/NEG iki ayrı atom yerine **tek birleşik atom** (POZ/NEG mantığı atom durumunda çözülür) → PIF grubu saf AND, aggregator doğru hesaplar.
✅ Üst-VEYA çiftleri: `[('(1)(a) HBV DNA', '(1)(b) ≥40 yaş', ['(2)(a) Pegile interferon' opt]), ('(1)(a)(1) Histoloji', '(1)(a)(2) ALT yüksek', '(1)(a)(2) FIB-4')]`.

⚠ **Kalan iyileştirme adayları (low priority):**
1. "3 ay arayla 2 ölçüm" ibaresi tek atomda kontrol ediliyor; ölçüm tarih farkı parser eklenebilir.
2. Yol-a-alt'ta `(a-alt)` ALT atomu ve `(a-alt-iç)` FIB-4/APRI ayrı gruplar; aggregator otomatik AND'lerken iç-iç-OR doğru çözülüyor (test #16 ile yansıması doğrulandı).

---

## 4. Y2 — Kronik Hepatit B Çocuk 2–18 (4.2.13.1 (1)(a)(1), (5))

### SUT lafzı (satır 5466-5467, 5499-5501)
> 2–18 yaş grubu hastalarda: **"ALT normalin üst sınırının 2 katından daha yüksek VE karaciğer biyopsisinde HAI ≥ 4" VEYA "ALT düzeyine bakılmaksızın fibrozis ≥ 2"** olan hastalarda
> Yaş bazlı doz: LAM 2-18, TDF/TAF 12-18, ETV 16-18

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| Y1 | Yaş 2–18 | hasta yaşı | AND-yaş | KE |
| E1 | Kronik HBV tanısı | teşhis+metin | AND-endikasyon | KE |
| A1 | HBV DNA ≥ 2000 IU/ml | rapor metni | AND-yol-a | KE |
| C1 | ALT > 2× ÜS **AND** HAI ≥ 4 | rapor metni | OR-yol-c1 | KE |
| C2 | Fibrozis ≥ 2 (ALT bakılmaksızın) | rapor metni | OR-yol-c2 | KE |
| D1 | Yaş-ilaç uyumu: LAM 2-18 / TDF-TAF 12-18 / ETV 16-18 | reçete+yaş | AND-doz | KE+(bilgi) |

### Boolean formül

```
Y2_UYGUN ⇔ R1 ∧ R2 ∧ Y1 ∧ E1 ∧ A1 ∧ (C1 ∨ C2) ∧ D1
```

### Mini akım şeması (Y2 — çocuk B 2-18)

```
    ⊕──[R1 uzman]──[R2 yetki]──[Y1: yaş 2-18]──[E1: HBV]──[A1: DNA≥2000]──┐
                                                                          │
                                                ┌─────────────────────────┼──────────────────┐
                                                ▼ ALT yolu                ▼ Fibrozis yolu
                                       ┌──────────────────┐      ┌──────────────────┐
                                       │ C1: ALT>2×ÜS     │      │ C2: Fibrozis≥2   │
                                       │     ∧ HAI≥4      │      │ (ALT bakılmaks.) │
                                       └────────┬─────────┘      └────────┬─────────┘
                                                │       ∨                  │
                                                └──────────┬───────────────┘
                                                           ▼
                                                  [D1: yaş-doz uyumu (bilgi)]
                                                           │
                                                           ▼
                                                       ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak2_cocuk_b` (line 1882–1971) — atomlar mevcut, üst-VEYA çifti `[('(1)(a)(1) ALT>2×ÜS', '(1)(a)(1) Fibrozis ≥ 2')]`.
✅ D1 yaş-doz uyumu **bilgi atomu** olarak eklendi (LAM 3mg/kg 2-18, TDF/TAF 245mg/25mg 12-18, ETV 0.5mg 16-18) — matematiği bozmaz, eczacı doğrular.
✅ Başlangıç/devam helper çağrılıyor (`ekle_eriskin_doz=False` — çocuk için /3 erişkin doz tablosu uygulanmaz).

---

## 5. Y3 — Hepatit B + Karaciğer Sirozu (4.2.13.1.1)

### SUT lafzı (satır 5523-5527)
> Karaciğer sirozunda HBV DNA (+) olan hastalarda tedaviye başlanabilir.
> **Biyopsi kanıtı olmayan hastalarda**, trombosit < 150.000/mm³ **VEYA** PT ≥ 3 sn uzun olması koşulu aranır.

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Karaciğer sirozu ibaresi | teşhis+metin | AND | YOK |
| E2 | HBV ICD (B18.0/B18.1) ∨ "hepatit B" | teşhis+metin | AND-endikasyon | KE |
| A1 | HBV DNA pozitif (kalitatif veya sayısal) | rapor metni | AND | KE |
| B1 | Biyopsi kanıtı VAR | rapor metni ("biyopsi yapıldı" / "HAI"/"fibrozis" rakamı) | OR-bypass | YOK |
| B2 | Trombosit < 150.000/mm³ | rapor metni | OR-bypass-B | KE |
| B3 | PT ≥ 3 sn uzun | rapor metni | OR-bypass-B | KE |

### Boolean formül

```
Y3_UYGUN ⇔ R1 ∧ R2 ∧ E1 ∧ E2 ∧ A1 ∧ [ B1 ∨ (B2 ∨ B3) ]
                                       ⟵ biyopsi varsa veya biyopsisiz şartlar
```

### Mini akım şeması (Y3 — B + siroz)

```
    ⊕──[R1]──[R2]──[E1: siroz]──[E2: HBV ICD]──[A1: HBV DNA+]──┐
                                                               │
                                          ┌────────────────────┼─────────────────────┐
                                          ▼ Yol-A: Biyopsi VAR ▼ Yol-B: Biyopsi YOK
                                  ┌──────────────────┐ ┌──────────────────────┐
                                  │ B1: HAI/fibrozis │ │ B2: Trombo<150.000   │
                                  │     raporlanmış  │ │   ∨ B3: PT≥3sn       │
                                  └────────┬─────────┘ └──────────┬───────────┘
                                           │       ∨               │
                                           └───────┬───────────────┘
                                                   ▼
                                              ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak3_b_siroz` (line 1978–2063) mevcut, üst-VEYA çifti `[('(1)(A) Biyopsi VAR', '(1)(B) Biyopsi YOK')]`.
✅ Biyopsi VAR sinyali: HAI/fibrozis sayısal değer + metin ibareleri ("biyopsi yapıldı/kanıt/sonuc/metavir/ishak skor").
✅ Başlangıç/devam helper çağrılıyor (siroz hastasında oral antiviral devamı için /4/6/7 atomları geçerli).

---

## 6. Y4 — Hepatit B + İmmünsüpresif/Kemo/Monoklonal (4.2.13.1.2)

### SUT lafzı (satır 5529-5545)
> **(1)** İmmünsüpresif / sitotoksik kemoterapi / monoklonal antikor uygulanmakta olan **HBsAg(+)** hastalarda; ALT yüksekliği, HBV DNA pozitifliği ve karaciğer biyopsisi koşulu **aranmaksızın** — tedavi süresince + sonraki ≤12 ay LAM/TBV/TDF/TAF/ETV.
> **(2)** Aynı hastalardan zaten kronik HBV: tedavi 4.2.13.1 prensiplerine göre.
> **(3)** HBsAg(−) olduğunda: HBV DNA(+) **VE/VEYA** Anti-HBc(+) durumunda biyopsi aranmaksızın LAM/TBV/TDF/TAF/ETV.

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| I1 | İmmünsüpresif / kemo / monoklonal / rituximab / TNF-i / biyolojik ibare | rapor metni | AND-bağlam | YOK |
| **YOL-(1)** |
| S1 | HBsAg pozitif | rapor metni | AND-(1) | KE |
| **YOL-(3)** |
| S2 | HBsAg negatif | rapor metni | AND-(3) | KE |
| S3 | HBV DNA pozitif | rapor metni | OR-(3) | KE |
| S4 | Anti-HBc pozitif | rapor metni | OR-(3) | KE |
| D1 | Reçete ilacı LAM/TBV/TDF/TAF/ETV | reçete | AND-doz | — |
| T1 | Tedavi süresi ≤ immünsüp+12 ay | rapor metni | bilgi | KE+(bilgi) |

### Boolean formül

```
Y4_UYGUN ⇔ R1 ∧ R2 ∧ I1 ∧ D1 ∧ [
    (S1)              ⟵ Yol (1): HBsAg+
    ∨
    (S2 ∧ (S3 ∨ S4))  ⟵ Yol (3): HBsAg- + (DNA+ ∨ Anti-HBc+)
]
```

### Mini akım şeması (Y4 — B + immünsüpresif)

```
    ⊕──[R1]──[R2]──[I1: immünsüp/kemo/monoklonal]──[D1: HBV oral]──┐
                                                                   │
                                          ┌────────────────────────┼──────────────────────────┐
                                          ▼ Yol (1): HBsAg(+)      ▼ Yol (3): HBsAg(−)
                                  ┌──────────────────┐    ┌─────────────────────────────┐
                                  │ S1: HBsAg(+)     │    │ S2: HBsAg(−) ∧             │
                                  │  (lab koşulu     │    │     (S3: HBV DNA+ ∨        │
                                  │   aranmaz)       │    │      S4: Anti-HBc+)         │
                                  └────────┬─────────┘    └──────────┬──────────────────┘
                                           │     ∨                    │
                                           └─────┬────────────────────┘
                                                 ▼
                                            ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak4_b_immunsup` (line 2070–2164), üst-VEYA çifti `[('(1) HBsAg(+) yolu', '(3) HBsAg(-) ∧ (DNA+ ∨ AntiHBc+)')]`.

---

## 7. Y5 — Karaciğer Transplant + HBV (4.2.13.1.3)

### SUT lafzı (satır 5547-5551)
> HBV'ye bağlı transplant **VEYA** Anti-HBc(+) kişiden karaciğer alan hastalara; biyopsi, viral seroloji, ALT, HBV DNA **bakılmaksızın** oral antiviral verilebilir.

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| T1 | Karaciğer transplantasyonu ibaresi | rapor metni | OR-endikasyon | YOK |
| T2 | Anti-HBc(+) donörden karaciğer | rapor metni | OR-endikasyon | YOK |
| D1 | Reçete: HBV oral antiviral | reçete | AND | — |

### Boolean formül

```
Y5_UYGUN ⇔ R1 ∧ R2 ∧ (T1 ∨ T2) ∧ D1
```

Lab/biyopsi şartı **YOK** (SUT açıkça "bakılmaksızın" diyor).

### Mini akım şeması (Y5 — transplant)

```
    ⊕──[R1]──[R2]──┬─[T1: KC nakli (HBV)]─┐
                   │                       │ ∨
                   └─[T2: Anti-HBc(+) donör KC]──┘──[D1: HBV oral]──⊖
                            (lab/biyopsi/HBV DNA aranmaz)
```

### Mevcut kod uyum
✅ `_hep_yolak5_b_transplant` (line 2166–2212). Lab/biyopsi atomu yok (SUT lafzına uygun).

---

## 8. Y6 — Akut Hepatit B (4.2.13 (3))

### SUT lafzı (satır 5457-5460)
> Akut hepatit B nedeniyle izlenen hastalarda **ciddi akut HBV kliniği VE laboratuvar bulguları** olan (**İNR ≥ 1,5 VEYA PT > ÜS + 4 sn VE sarılık dönemi > 4 hafta**) hastalarda; 4 hafta arayla iki kere HBsAg negatifliği elde edilene kadar antiviral.

### Atomik tablo (parantez yorumu)

> Lafız: "İNR ≥ 1,5 **veya** PT normalin üst sınırından 4 saniyeden daha uzun olanlar **ve** sarılık dönemi > 4 hafta olanlar"
>
> Yoruma açık: **(INR ≥ 1.5 ∨ PT uzun) ∧ sarılık > 4 hafta** mı? Yoksa **INR ≥ 1.5 ∨ (PT uzun ∧ sarılık)** mı?
>
> SUT genel disipline göre "ciddi klinik" tanımının çoklu kriter ile yapılması, **(INR yüksek ∨ PT uzun ∨ sarılık)** OR-grubu olarak yorumlamak en doğal okuma — kullanıcı onayına sunulur.

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Akut Hepatit B (ICD B16 ∨ metin) | teşhis+metin | AND | KE |
| C1 | INR ≥ 1.5 | rapor metni | OR-ciddi | KE |
| C2 | PT > ÜS + 4 sn uzun | rapor metni | OR-ciddi | KE |
| C3 | Sarılık dönemi > 4 hafta | rapor metni | OR-ciddi | KE |
| T1 | (Bilgi) Süre: 4 hafta arayla 2× HBsAg(−) | rapor metni | bilgi | KE+(bilgi) |

### Boolean formül (öneri)

```
Y6_UYGUN ⇔ R1 ∧ R2 ∧ E1 ∧ (C1 ∨ C2 ∨ C3)
```

### Mini akım şeması (Y6 — Akut B)

```
    ⊕──[R1]──[R2]──[E1: Akut B (B16 ∨ "akut hepatit B")]──┐
                                                          │
                              ┌───────────────────────────┼───────────────────┐
                              ▼ C1                        ▼ C2                ▼ C3
                       [INR≥1.5]              [PT>ÜS+4sn]         [Sarılık>4 hf]
                              │      ∨                   │      ∨           │
                              └──────────────────────────┴──────────────────┘
                                                          │
                                          [SB onaylı antiviral ilaç]──⊖
                                          [Bitiş kriteri (bilgi): 4hf×2 HBsAg(−)]
```

### Mevcut kod uyum
✅ `_hep_yolak6_akut_b` (line 2214–2267). 3-OR çiddi klinik grubu (kullanıcı onaylı yorum, 2026-05-17).

---

## 9. Y7 — Kronik Hepatit D / Delta (4.2.13.2)

### SUT lafzı (satır 5565-5569)
> Delta ajanlı Kronik Hepatit B tanısı konmuş **anti HDV(+)** hastalarda pegile interferonlar, kronik B süre/dozunda. Kronik HBV tedavi koşullarını taşıyanlarda tedaviye **oral antiviral eklenebilir** (Anti-HDV+ ve HBV DNA raporda belirtilir).

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Delta / HDV ibaresi (ICD B17.0/B18.0 ∨ "delta"/"hdv"/"anti-hdv") | teşhis+metin | AND-endikasyon | KE |
| A1 | Anti-HDV pozitif | rapor metni | AND | KE |
| A2 | HBV DNA değeri raporda belirtilmiş (pozitif/sayısal) | rapor metni | AND-bilgi | KE+(bilgi) |
| D1 | Reçete: PEG_IFN ∨ HBV_ORAL | reçete | AND | — |
| (4.2.13.1 koşulu) | (Sadece oral antiviral eklendiyse) kronik B şartları (Y1 atomları) | — | AND-(oral eklendiyse) | KE |

### Boolean formül

```
Y7_UYGUN ⇔ R1 ∧ R2 ∧ E1 ∧ A1 ∧ D1
   (∧ A2 bilgi)
   (∧ etkin=HBV_ORAL ise: KB-A-hist ∨ KB-A-alt-iç)   ⟵ Kronik B tedavi koşulları
```

### Mini akım şeması (Y7 — Delta/HDV)

```
    ⊕──[R1]──[R2]──[E1: Anti-HDV(+)]──[HBV DNA raporda]──[D1: PEG-IFN ∨ HBV oral]──┐
                                                                                   │
                              ┌─ etkin=PEG_IFN: doğrudan UYGUN ────────────────────┤
                              │                                                    │
                              └─ etkin=HBV_ORAL: + Kronik B koşulları──────────────┤
                                 ┌──────────────────────┐                          │
                                 │ KB-A-hist:           │      ∨                   │
                                 │   HAI≥6 ∨ fibroz≥2  │ ────────────┐             │
                                 │ KB-A-alt-iç:         │             ├─────────────┘
                                 │   FIB-4>1.45 ∨ APRI  │             │
                                 │     >0.5             │ ────────────┘
                                 └──────────────────────┘
                                                                       │
                                                                       ▼
                                          [EK-4E 11/A/10: Enf Uzm yokluğunda yetki devri (bilgi)]
                                                                       ▼
                                                                  ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak7_kronik_d` (line 2274–2388). HBV_ORAL ise Y1 atomları inline (KB-A-hist ∨ KB-A-alt-iç) eklenip üst-VEYA çiftine alınıyor.
✅ EK-4E 11/A/10 yetki devri bilgi atomu (reçete açıklamasında "Enf Uzm yok" regex'i kontrol ediliyor).

---

## 10. Y8 — Akut Hepatit C (4.2.13.3.1) — Ribavirin YASAK

### SUT lafzı (satır 5572-5578)
> Akut Hepatit C tedavisinde kullanılan ilaçlar GE/Enf uzman raporuna dayanılarak GE/Enf/Çocuk SH/İç Hast tarafından reçete.
> **HCV RNA pozitif** sonuç raporda belirtilir. 24 hafta süreyle pegile interferon alfa **monoterapisi**.
> **Bu hastalarda tedaviye Ribavirin EKLENEMEZ.** Biyopsi ve 12. haftada HCV RNA 2 log azalma koşulu **aranmaz**.

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Akut Hepatit C (ICD B17.1 ∨ "akut hepatit C") | teşhis+metin | AND-endikasyon | KE |
| A1 | HCV RNA pozitif | rapor metni | AND | KE |
| D1 | Reçete: PEG_IFN (monoterapi) | reçete | AND | — |
| **B1** | **Reçetede Ribavirin YOK** | reçete `diger_ilac_adlari` | AND-(NOT) | **KE (sessizlik=KE)** |
| T1 | Süre ≤ 24 hafta (bilgi) | — | bilgi | KE+(bilgi) |

### Boolean formül

```
Y8_UYGUN ⇔ R1 ∧ R2 ∧ E1 ∧ A1 ∧ D1 ∧ B1
```

**B1 NEGATİF atom — DeMorgan disiplini:** Reçetede Ribavirin görünürse şart YOK → UYGUN_DEĞİL. Reçete kalemleri biliniyorsa VAR (yok ise) ya da YOK (varsa). Reçete `recete_ilaclari` listesinde "RIBAVIRIN/COPEGUS/REBETOL/VIRAZOLE" sorgulanır.

### Mini akım şeması (Y8 — Akut C, Ribavirin YASAK)

```
    ⊕──[R1]──[R2]──[E1: Akut C (B17.1)]──[A1: HCV RNA+]──[D1: PEG-IFN monoterapi]──┐
                                                                                   │
                                                                                   ▼
                                                                ┌──────────────────────────┐
                                                                │ B1: Reçetede Ribavirin   │
                                                                │     YOK (negatif atom)   │
                                                                │  (RIBAVIRIN/COPEGUS/     │
                                                                │   REBETOL/VIRAZOLE       │
                                                                │   diger_ilaclar'da yok)  │
                                                                └────────────┬─────────────┘
                                                                             │
                                                                             ▼
                                                                         ⊖ (UYGUN)
                                                  (B1 YOK → UYGUN_DEĞİL — Ribavirin yasağı ihlali)
```

### Mevcut kod uyum
✅ `_hep_yolak8_akut_c` (line 2395–2480). Test #6 başarılı: "Akut C + Ribavirin → UYGUN_DEĞİL".

---

## 11. Y9 — Kronik HCV Erişkin Naive (4.2.13.3.2.A.1)

### SUT lafzı (satır 5596-5603)
> **(1) Nonsirotik:** (SOF+VEL+VOX) 8 hafta **VEYA** (GLE+PIB) 8 hafta.
> **(2) Kompanse sirotik (Child-Pugh A):** (SOF+VEL+VOX) 12 hafta **VEYA** (GLE+PIB) 8 hafta.
> **(3) Dekompanse (Child-Pugh B/C) Genotip 1a, 1b, 4, 5, 6:** (SOF+LED) + Ribavirin 12 hafta.

### 4.2.13.3.2 genel hükümler (satır 5579-5594)
> (1) HCV RNA pozitif
> (2) Kompanse sirozda histopatoloji yoksa: trombosit < 150.000 ∨ PT ≥ 3 sn
> (3) Dekompanse sirozda: asit ∨ ensefalopati ∨ sarılık (bilirubin > 3 mg/dl) ∨ özofagus varis kanaması; genotip tayini gerekli (erişkin)
> (5) 2./3. basamak sağlık kurumu — GE/Enf uzman raporu
> (6) Rapor: HCV RNA+, sirotik/nonsirotik durumu, Child-Pugh B/C kanıtı, genotip (dekompanse veya çocuk), önceki HCV tedavisi (NS5A kullanmış mı)

### Atomik tablo

| # | Atom | Kaynak | Operatör | Sessiz |
|---|---|---|---|---|
| E1 | Kronik HCV tanısı (ICD B18.2 ∨ metin) | teşhis+metin | AND | KE |
| E2 | HCV RNA pozitif (sayısal ∨ kalitatif) | rapor metni | AND | KE |
| E3 | Erişkin (≥18) | hasta yaşı | AND | KE |
| E4 | (R3) Rapor 2./3. basamak | rapor metni | AND-bilgi | KE+(bilgi) |
| **YOL-N (Nonsirotik)** |
| N1 | Sirotik DEĞİL (nonsirotik ibaresi) | rapor metni | AND-(N) | KE |
| N2 | Rejim ∈ {SOF+VEL+VOX, GLE+PIB} | reçete kombinasyonu | AND-(N) | — |
| **YOL-KA (Kompanse Child-A)** |
| KA1 | Kompanse siroz (Child-Pugh A) | rapor metni | AND-(KA) | KE |
| KA2 | (Biyopsi yoksa) Trombosit < 150.000 ∨ PT ≥ 3 sn | rapor metni | OR-bypass | KE |
| KA3 | Rejim ∈ {SOF+VEL+VOX, GLE+PIB} | reçete | AND-(KA) | — |
| **YOL-DA (Dekompanse Child-B/C)** |
| DA1 | Dekompanse siroz (Child-Pugh B ∨ C) | rapor metni | AND-(DA) | KE |
| DA2 | Asit ∨ ensefalopati ∨ sarılık ∨ varis kanaması | rapor metni | OR-(DA-kanıt) | KE |
| DA3 | Genotip 1a/1b/4/5/6 | rapor metni | AND-(DA) | KE |
| DA4 | Rejim = (SOF+LED) + Ribavirin | reçete | AND-(DA) | — |
| T1 | (Bilgi) Tedavi süresi: 8/12/12 hafta | rapor | bilgi | KE+(bilgi) |

### Boolean formül

```
Y9_UYGUN ⇔ R1 ∧ R2 ∧ R3 ∧ E1 ∧ E2 ∧ E3 ∧ [
    (N1 ∧ N2)               ⟵ Nonsirotik
    ∨
    (KA1 ∧ KA2 ∧ KA3)       ⟵ Kompanse Child-A
    ∨
    (DA1 ∧ DA2 ∧ DA3 ∧ DA4) ⟵ Dekompanse
]
```

### Mini akım şeması (Y9 — HCV erişkin naive)

```
    ⊕──[R1/R2/R3]──[E1: kronik C]──[E2: HCV RNA+]──[E3: erişkin]──┐
                                                                  │
              ┌───────────────────────────┬──────────────────────┴──────────────────────┐
              ▼ N (Nonsirotik)            ▼ KA (Kompanse Child-A)                       ▼ DA (Dekompanse)
       ┌──────────────────┐        ┌────────────────────────┐              ┌──────────────────────────┐
       │ N1: nonsirotik   │        │ KA1: kompanse (Child A)│              │ DA1: dekompanse (B/C)    │
       │ N2: SVV ∨ GP     │        │ KA2: (trombo<150k ∨    │              │ DA2: asit ∨ enseph ∨     │
       │  8 hafta         │        │       PT≥3sn) eğer     │              │       sarılık ∨ varis    │
       │                  │        │       biyopsi yok      │              │ DA3: Genotip 1a/1b/4/5/6 │
       │                  │        │ KA3: SVV ∨ GP          │              │ DA4: SOF+LED+RBV 12 hf   │
       └────────┬─────────┘        └──────────┬─────────────┘              └──────────┬───────────────┘
                │        ∨                    │           ∨                            │
                └──────────────────────────────┴────────────────────────────────────────┘
                                                          │
                                                          ▼
                                                      ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak9_kronik_c_eriskin_naive` (line 2534–2684). 3 alt-yol üst-VEYA çiftinde aggregator'a verildi.

---

## 12. Y10 — Kronik HCV Erişkin Deneyimli (4.2.13.3.2.A.2)

### SUT lafzı (satır 5605-5615)
> **(1) NS5A haricindeki ilaçlarla deneyimli, nonsirotik:** (SOF+VEL+VOX) 12 hafta ∨ (GLE+PIB) 8 hafta.
> **(2) NS5A haricindeki, kompanse sirotik:** (SOF+VEL+VOX) 12 hafta ∨ (GLE+PIB) 12 hafta.
> **(3) NS5A ∨ proteaz inhibitörü ile deneyimli, nonsirotik ∨ kompanse:** (SOF+VEL+VOX) 12 hafta **VEYA** (Sağlık Bakanlığı onayı ile) (GLE+PIB)+Rib ∨ (GLE+PIB) 16 hafta.
> **(4) NS5A ∨ proteaz inhibitörü ile deneyimli, dekompanse Genotip 1a/1b/4/5/6:** (SOF+LED) + Ribavirin 24 hafta.

### Atomik tablo (yol bazlı)

| # | Atom | Kaynak | Operatör |
|---|---|---|---|
| E1-E4 | (Y9'la ortak) endikasyon + erişkin + 2./3. basamak | — | AND |
| **H1** | Daha önce HCV tedavisi (deneyimli) | rapor metni + hasta DB | AND-(deneyimli) |
| **H2** | NS5A kullanmış mı? | rapor metni + hasta DB | dispatcher |
| **H3** | Proteaz inh. kullanmış mı? | rapor metni + hasta DB | dispatcher |
| **YOL-(1)** Nonsirotik + NS5A-DEĞİL |
| Y1a | Nonsirotik | rapor | AND |
| Y1b | NS5A önceki YOK ∧ Proteaz önceki YOK | metin+DB | AND-(NOT) |
| Y1c | Rejim ∈ {SOF+VEL+VOX, GLE+PIB} | reçete | AND |
| **YOL-(2)** Kompanse + NS5A-DEĞİL |
| Y2a | Kompanse Child-A | rapor | AND |
| Y2b | NS5A önceki YOK ∧ Proteaz önceki YOK | metin+DB | AND-(NOT) |
| Y2c | Rejim ∈ {SOF+VEL+VOX, GLE+PIB} | reçete | AND |
| **YOL-(3)** Nonsirotik ∨ Kompanse + NS5A/Proteaz |
| Y3a | Nonsirotik ∨ Kompanse | rapor | AND |
| Y3b | NS5A ∨ Proteaz önceki VAR | metin+DB | AND |
| Y3c | Rejim ∈ {SOF+VEL+VOX, (GLE+PIB)+Rib, GLE+PIB} | reçete | AND |
| **YOL-(4)** Dekompanse + NS5A/Proteaz |
| Y4a | Dekompanse Child-B/C | rapor | AND |
| Y4b | Genotip 1a/1b/4/5/6 | rapor | AND |
| Y4c | NS5A ∨ Proteaz önceki VAR | metin+DB | AND |
| Y4d | Rejim = (SOF+LED) + Ribavirin | reçete | AND |

### Boolean formül

```
Y10_UYGUN ⇔ R1 ∧ R2 ∧ R3 ∧ E1 ∧ E2 ∧ E3 ∧ H1 ∧ [
    (Y1a ∧ Y1b ∧ Y1c)   ⟵ (1) NS5A−/proteaz− nonsirotik
    ∨ (Y2a ∧ Y2b ∧ Y2c) ⟵ (2) NS5A−/proteaz− kompanse
    ∨ (Y3a ∧ Y3b ∧ Y3c) ⟵ (3) NS5A+/proteaz+ nonsirot/kompans
    ∨ (Y4a ∧ Y4b ∧ Y4c ∧ Y4d) ⟵ (4) NS5A+/proteaz+ dekomp G1a/1b/4/5/6
]
```

### Mini akım şeması (Y10 — HCV erişkin deneyimli, 4 alt-yol)

```
    ⊕──[R1/R2/R3]──[E1-E3]──[H1: deneyimli]──┐
                                              │
        ┌────────────────┬────────────────────┼─────────────────┬──────────────────┐
        ▼ (1) EX1        ▼ (2) EX2            ▼ (3) EX3         ▼ (4) EX4
   ┌───────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌────────────────────┐
   │ NS5A−/PI−     │ │ NS5A−/PI−       │ │ NS5A+ ∨ PI+     │ │ NS5A+ ∨ PI+        │
   │ ∧ nonsirot    │ │ ∧ kompanse      │ │ ∧ nonsirot/komp │ │ ∧ dekompanse       │
   │ ∧ (SVV ∨ GP)  │ │ ∧ (SVV ∨ GP)    │ │ ∧ (SVV ∨ GP±RBV)│ │ ∧ G1a/1b/4/5/6     │
   │   12hf/8hf    │ │   12hf/12hf     │ │   12hf/16hf+SBon│ │ ∧ SOF+LED+RBV 24hf │
   └───────┬───────┘ └────────┬────────┘ └────────┬────────┘ └─────────┬──────────┘
           │   ∨               │      ∨            │      ∨             │
           └───────────────────┴───────────────────┴────────────────────┘
                                                  │
                                                  ▼
                                              ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak10_kronik_c_eriskin_exp` (line 2691–2839). 4 alt-yol üst-VEYA çiftinde aggregator'a verildi.

---

## 13. Y11 — HCV Çocuk Naive (4.2.13.3.2.B)

### SUT lafzı (satır 5617-5630)
> (1) HCV RNA pozitif + Genotip tayini ile tedaviye başlanabilir.
> (2) İnterferon+Ribavirin **VEYA** Pegile IFN+Ribavirin. Ribavirin kontrendikeyse tek başına IFN ∨ PegIFN. **Tek başına Ribavirin endikasyonu YOK.**
> (3) Genotip 1 ∧ Genotip 4: 48 hafta. 12. haftada HCV RNA 2 log azalmayanlarda ≤ 16 hafta; 24. haftada RNA(+) devam ediyorsa ≤ 28 hafta.
> (4) 3–18 yaş: Ribavirin 15 mg/kg/gün max 1200 mg. Pegile IFN daha önce IFN almamış hastalarda.
> (5) **12–18 yaş, naive: (GLE+PIB) 8 hafta** — genotip tayini gerekmez.

### Atomik tablo

| # | Atom | Kaynak | Operatör |
|---|---|---|---|
| E1 | Kronik HCV tanısı (B18.2) | teşhis+metin | AND |
| E2 | HCV RNA pozitif | rapor metni | AND |
| E3 | Yaş 3–18 (çocuk) | hasta yaşı | AND |
| G1 | Genotip raporda belirtilmiş (1, 2, 3, 4, 5, 6) | rapor metni | AND-(bilgi, GP hariç) |
| **YOL-A** Klasik (IFN-bazlı) |
| A1 | Rejim ∈ {IFN+Rib, PegIFN+Rib} ∨ (Rib kontrendike → IFN ∨ PegIFN tek) | reçete | AND |
| A2 | Daha önce IFN ALMAMIŞ (PegIFN için) | rapor metni + DB | AND-(NOT) |
| **YOL-B** Yeni (GP, 12–18 naive) |
| B1 | Yaş 12–18 | hasta yaşı | AND |
| B2 | Rejim = GLE+PIB | reçete | AND |
| B3 | Naive (önceki HCV tedavisi YOK) | rapor metni + DB | AND-(NOT) |
| **YASAK** |
| Z1 | Reçetede tek başına Ribavirin YOK (kombi olmalı) | reçete | AND-(NOT) |

### Boolean formül

```
Y11_UYGUN ⇔ R1 ∧ R2 ∧ R3 ∧ E1 ∧ E2 ∧ E3 ∧ Z1 ∧ [
    (A1 ∧ (A2 ∨ ¬PegIFN-kullanımı))   ⟵ Klasik yol
    ∨
    (B1 ∧ B2 ∧ B3)                     ⟵ GP yolu (12-18 naive)
]
```

### Mini akım şeması (Y11 — HCV çocuk naive)

```
    ⊕──[R1/R2/R3]──[E1: kronik C]──[E2: HCV RNA+]──[E3: yaş 3-18]──[Genotip raporda]──┐
                                                                                       │
                                                                                       ▼
                                                              ┌─ Z1: Tek başına Rib YASAĞI ─┐
                                                              │ (RBV var ∧ partner yok ─    │
                                                              │   UYGUN_DEĞİL)              │
                                                              └─────────────┬───────────────┘
                                                                            │
                                            ┌───────────────────────────────┼────────────────────────────────┐
                                            ▼ Yol-A klasik                  ▼ Yol-B yeni (12-18 GP)
                                  ┌──────────────────────────┐  ┌─────────────────────────────┐
                                  │ A1: IFN+RBV ∨ peg-IFN+   │  │ B1: yaş 12-18               │
                                  │   RBV ∨ (RBV kontrend. → │  │ B2: Reçete = GLE+PIB        │
                                  │   tek IFN/peg-IFN)       │  │ B3: naive (önceki HCV YOK)  │
                                  │ (+RBV dozu 15mg/kg bilgi)│  │     8 hafta                 │
                                  └────────────┬─────────────┘  └────────────┬────────────────┘
                                               │     ∨                        │
                                               └──────────────┬───────────────┘
                                                              ▼
                                                          ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak11_kronik_c_cocuk_naive` (line 2846–2964). Tek başına Ribavirin yasağı atomu (SUT 4.2.13.3.2.B(2)) ve üst-VEYA çifti eklendi.

---

## 14. Y12 — HCV Çocuk 12–18 Deneyimli (4.2.13.3.2.B.1)

### SUT lafzı (satır 5632-5646)
> (1) IFN/PegIFN+Rib almış, komplikasyon nedeniyle 12. haftadan önce kesilmiş → naive gibi.
> (2) Tedavi deneyimli 12–18 yaş:
>   **a) SOF+LED:** Genotip 1 nonsirot 12 hafta, kompanse 24 hafta; Genotip 4/5/6 nonsirot/kompanse 12 hafta.
>   **b) GLE+PIB:** Genotip 1/2/4/5/6 nonsirot NS5A-/Proteaz- 8 hafta; kompanse 12 hafta; Genotip 3 nonsirot/kompanse (IFN almış ∨ SOF almış) NS5A-/Proteaz- 16 hafta; Genotip 1 nonsirot/kompanse Proteaz+ NS5A- 12 hafta; Genotip 1 nonsirot/kompanse NS5A+ Proteaz- 16 hafta.

### Atomik tablo (yol bazlı, basitleştirilmiş)

| # | Atom | Kaynak | Operatör |
|---|---|---|---|
| E1-E3 | Endikasyon (Y9 ile ortak) | — | AND |
| Y12 | Yaş 12–18 | hasta yaşı | AND |
| H1 | Daha önce HCV tedavisi VAR (deneyimli) | metin+DB | AND |
| G1 | Genotip raporda belirtilmiş | rapor | AND |
| **YOL-A SOF+LED** |
| SLA | Rejim = SOF+LED | reçete | AND |
| SLB | Genotip ∈ {1, 4, 5, 6} | rapor | AND |
| SLC | Sirotik durumu (nonsirot ∨ kompanse) | rapor | AND |
| **YOL-B GLE+PIB** |
| GPA | Rejim = GLE+PIB | reçete | AND |
| GPB | Sirotik durum + NS5A/Proteaz geçmişi alt-kombinasyonlar | rapor+DB | AND-(varyant) |

### Boolean formül (sadeleştirilmiş)

```
Y12_UYGUN ⇔ R1 ∧ R2 ∧ R3 ∧ E1 ∧ E2 ∧ Y12 ∧ H1 ∧ G1 ∧ [
    (SLA ∧ SLB ∧ SLC)   ⟵ SOF+LED yolu
    ∨
    (GPA ∧ GPB)         ⟵ GLE+PIB yolu (alt-varyantlar bilgi atomu)
]
```

### Mini akım şeması (Y12 — HCV çocuk deneyimli 12-18)

```
    ⊕──[R1/R2/R3]──[E1-E2]──[Y12: yaş 12-18]──[H1: deneyimli]──[G1: Genotip raporda]──┐
                                                                                       │
                              ┌────────────────────────────────────────────────────────┴────┐
                              ▼ Yol-A SOF+LED                                               ▼ Yol-B GLE+PIB
                       ┌─────────────────────────────┐                          ┌─────────────────────────────┐
                       │ SLA: Rejim = SOF+LED        │                          │ GPA: Rejim = GLE+PIB         │
                       │ SLB: Genotip ∈ {1, 4, 5, 6}│                          │ GPB: NS5A/PI geçmiş + sirot   │
                       │ SLC: nonsirot ∨ kompanse    │                          │   alt-varyant (bilgi)        │
                       │   (G1 nonsirot 12hf,       │                          │   8/12/16 hafta tablosu     │
                       │    G1 komp 24hf,           │                          │   eczacı doğrular           │
                       │    G4/5/6 her ikisi 12hf) │                          │                              │
                       └────────────┬────────────────┘                          └────────────┬─────────────────┘
                                    │      ∨                                                  │
                                    └────────────────────────┬─────────────────────────────────┘
                                                             ▼
                                                         ⊖ (UYGUN)
```

### Mevcut kod uyum
✅ `_hep_yolak12_kronik_c_cocuk_exp` (line 2971–3112). 4 ana atom (rejim+genotip+sirotik+geçmiş) + GLE+PIB alt-varyantları (bilgi) — kullanıcı onaylı (2026-05-17, karar #4).

---

## 15. Kombi yasakları + ortak kurallar

| Yasak | Yer | Atom |
|---|---|---|
| Tek başına Ribavirin (HCV çocuk) | 4.2.13.3.2.B (2) | Y11 Z1 |
| Ribavirin + Akut C | 4.2.13.3.1 (2) | Y8 B1 |
| HBV oral değişimi: Lamivudin/Telbivudin 24. haftada DNA < 50 IU/ml ise başka antivirale geçilemez | 4.2.13.1 (4)(a) | bilgi/KE |

---

## 16. KAPSAM DIŞI (HIV ATC J05A* — başka buton)

| Etken madde | Kategori |
|---|---|
| Dolutegravir / Bictegravir / Raltegravir | HIV → ANTIVIRAL |
| Abacavir / Emtricitabine / Lamivudin (HIV doz/kombi) | HIV → ANTIVIRAL |
| Efavirenz / Nevirapine / Rilpivirine | HIV → ANTIVIRAL |
| Atazanavir / Darunavir / Ritonavir | HIV → ANTIVIRAL |

**Not:** Lamivudin etken maddesi hem HBV (Zeffix 100 mg) hem HIV (Epivir 150 mg) için kullanılır. Doz/marka ayrımı dispatcher'da yapılır:
- ZEFFIX / EPIVIR HBV → HBV (HEPATIT)
- EPIVIR (HIV doz) / 3TC kombileri → HIV (ANTIVIRAL)

---

## 17. SUT lafzından kod uyum özeti (✓/⚠/✗) — 2026-05-23 güncel

| Yolak | SUT ↔ Kod | Durum | Not |
|---|---|---|---|
| Y1 Kronik B Erişkin | ✅ | TAM | PIF kolu üst-VEYA çiftine eklendi (2026-05-23 fix); HBeAg POZ/NEG tek birleşik atom |
| Y2 Kronik B Çocuk | ✅ | TAM | Yaş-doz uyumu bilgi atomu; biyopsi kontrendikasyon bilgi atomu |
| Y3 B + Siroz | ✅ | TAM | Biyopsi VAR/YOK üst-VEYA çifti aktif; biyopsi sinyal regex'i sağlıklı |
| Y4 B + İmmünsüpresif | ✅ | TAM | HBsAg(+) ↔ HBsAg(−)∧(DNA+∨AntiHBc+) üst-VEYA çifti |
| Y5 Transplant | ✅ | TAM | Lab/biyopsi atomu yok (SUT lafzına uygun) |
| Y6 Akut B | ✅ | TAM | "Ciddi klinik" 3-OR; kullanıcı onaylı yorum (2026-05-17) |
| Y7 Delta | ✅ | TAM | HBV oral varsa Y1 atomları inline + üst-VEYA çifti; EK-4E yetki devri bilgi atomu |
| Y8 Akut C | ✅ | TAM | Ribavirin yasağı çalışıyor (test #6 pass) |
| Y9 HCV Erişkin Naive | ✅ | TAM | 3 alt-yol (Nonsirot/Kompanse/Dekompanse) üst-VEYA aggregator |
| Y10 HCV Erişkin Exp | ✅ | TAM | 4 alt-yol (NS5A var/yok × sirotik durumu) üst-VEYA aggregator |
| Y11 HCV Çocuk Naive | ✅ | TAM | Tek başına Ribavirin yasağı atomu (test #15 pass) |
| Y12 HCV Çocuk Exp | ✅ | TAM | 4 ana atom + GLE+PIB alt-varyantları bilgi (kullanıcı onaylı, 2026-05-17 karar #4) |

---

## 18. Kullanıcı kararları (2026-05-17 onaylı, uygulandı)

| # | Soru | Karar | Kod |
|---|---|---|---|
| 1 | Y6 (Akut B) "ciddi klinik" lafzı | **3-OR**: (INR ≥ 1,5) ∨ (PT > ÜS+4sn) ∨ (sarılık > 4hf) — herhangi 1 yeterli | Mevcut, korundu |
| 2 | Y7 (Delta) yan-şartı | **Etken=HBV_ORAL ise Y1 atomları inline üret** (HAI/fibrozis/ALT/FIB-4/APRI) | `_hep_yolak7_kronik_d` revize edildi, `(KB-A-hist)` ve `(KB-A-alt-iç)` üst-VEYA çifti eklendi |
| 3 | Y10 (HCV Eri Exp) 4 alt-yol | **Tek üst-VEYA çiftinde:** ('YOL-(1)','YOL-(2)','YOL-(3)','YOL-(4)') | Mevcut, doğrulandı |
| 4 | Y12 (HCV Çocuk Exp) GLE+PIB alt-varyantları | **4 ana atom (rejim+genotip+sirotik+geçmiş) + süre KE+(bilgi)** | Mevcut yapı korundu |
| 5 | sartli_atom → SARTLI_UYGUN | **Korunsun (mevcut tasarım)** | Kod aynı, ayrıca (bilgi) atomları sartli_atomlar listesinden filtrelendi |
| 6 | Kombi yasakları | **Yolak-özel (mevcut tarz)** | Y8 + Y11 ayrı atomlar |
| 7 | 4.1.1/8 Aile hekimi yetkisi | **Y1/Y2/Y3/Y4/Y5/Y7 için ekle** (HCV ve Y6 hariç) | `hep_atom_recete_yetkisi` revize: `aile_hekimi_yetkili` parametresi |
| 8 | Eksik mevzuat (1/3,/4,/6,/7,/8,/1.4 + EK-4E) | **KE+(bilgi) atomları** (şemada görünür, matematiği bozmaz) | `_hep_bilgi_atom` helper + 12 yeni bilgi atomu |

---

## 19. Uygulanan revizyonlar (kod düzeyinde)

| Görev | Dosya / yer | Durum |
|---|---|---|
| A. Y10 üst-VEYA çiftleri | `hepatit_kontrol.py:2083-2087` | ✅ Mevcut, doğrulandı |
| B. Y9 üst-VEYA çiftleri | `hepatit_kontrol.py:1933-1936` | ✅ Mevcut, doğrulandı |
| C. Y11 tek başına Rib yasağı | Y11 (`_hep_yolak11_kronik_c_cocuk_naive`) sonuna eklendi + dispatcher RIBAVIRIN'i HCV yolaklarına route ediyor | ✅ Yeni atom |
| D. Aile hekimi (SUT 4.1.1/8) | `hep_atom_recete_yetkisi` + dispatcher Y1-Y5,Y7 için True | ✅ Yeni davranış |
| E. Y7 yan-şart (HBV_ORAL → Y1 atomları) | `_hep_yolak7_kronik_d` revize | ✅ Inline atomlar |
| F. Y4 HBsAg+/HBsAg− üst-VEYA | `hepatit_kontrol.py:1498-1499` | ✅ Mevcut, doğrulandı |
| G. Y3 biyopsi VAR/YOK üst-VEYA | Y3 yeniden tasarlandı (yol-A biyopsi VAR vs yol-B biyopsi YOK + trombosit/PT) | ✅ Yeni atomlar |
| H1. 4.2.13.1/3 erişkin doz | Y1 bilgi atomu | ✅ KE+(bilgi) |
| H2. 4.2.13.1/4 tedavi değişim | Y1+Y2 bilgi atomu | ✅ KE+(bilgi) |
| H3. 4.2.13.1/5 çocuk yaş-doz | Y2 bilgi atomu | ✅ KE+(bilgi) |
| H4. 4.2.13.1/6 sonlandırma | Y1 bilgi atomu | ✅ KE+(bilgi) |
| H5. 4.2.13.1/7 HBsAg+ devam | Y1 bilgi atomu | ✅ KE+(bilgi) |
| H6. 4.2.13.1/8 rapor süresi | Y1+Y2+Y3+Y4+Y5+Y7 bilgi atomu | ✅ KE+(bilgi) |
| H7. 4.2.13.1.4 biyopsi bypass | Y1+Y2 bilgi atomu | ✅ KE+(bilgi) |
| H8. EK-4E 11/A/10 Delta | Y7 bilgi atomu + reçete açıklama regex | ✅ KE+(bilgi) |
| Bonus. (bilgi) atomları sartli_atomlar listesinden filtrelendi | `_hep_genel_sonuc` | ✅ Bug fix |
| Bonus. GUI verdict_sartlar JSON serialization | `aylik_recete_sorgu_gui.py:_hepatit_kontrol_baslat` | ✅ Şema render aktif |

---

## 20. Test sonuçları (2026-05-23)

### `test_hepatit_atomik.py` — **16/16 senaryo başarılı**
- Test 1-12: Mevcut senaryolar regresyon korundu
- **Test 13**: Aile hekimi Y1 raporlu → SARTLI_UYGUN (aile hekimi yetkili)
- **Test 14**: Aile hekimi HCV → UYGUN_DEĞİL (HCV'de aile hekimi yetkisiz, SUT 4.1.1/8 sadece 4.2.13.1/4.2.13.2)
- **Test 15**: Y11 tek başına Ribavirin → UYGUN_DEĞİL (SUT 4.2.13.3.2.B(2) yasağı)
- **Test 16** (2026-05-23): Y1 PEG_IFN PIF kolu — yol-a/yol-b atomları YOK olsa bile PIF kolu (ALT>2×ÜS + HBeAg+DNA eşik) tam ise UYGUN/SARTLI_UYGUN olduğunu doğrular (PIF üst-VEYA fix regresyon koruması)

### `test_hepatit_baslangic_devam.py` — **21/21 senaryo başarılı** (2026-05-21)
SUT 4.2.13.1 Y1 başlangıç ↔ devam ayrımı:
- Tespit: BASLANGIC / DEVAM / BELIRSIZ + çelişki çözümü (DEVAM güvenli)
- Atom testleri: /3 erişkin doz (LAM/TBV/TDF/TAF/ETV), /6.a HBsAg/AntiHBs raporda, /6.b ≤12 ay sonlandırma, /7 HBsAg(+) devam, /4 etken değişim gerekçesi
- Entegrasyon: Y1-BASLANGIC, Y1-DEVAM, Y1-BELIRSIZ, Y1-DEVAM gerekçesiz senaryoları

**Toplam: 37/37 pass.**

---

## 21. 2026-05-23 Revizyon — PIF üst-VEYA fix + başlangıç/devam belgeye işleme

### Yapılanlar

| # | Değişiklik | Dosya/Yer | Test |
|---|---|---|---|
| 1 | Y1 PIF kolu (`'(2)(a) Pegile interferon'` prefix) üst-VEYA çiftine eklendi | `hepatit_kontrol.py:1856-1865` | test #16 |
| 2 | HBeAg POZ/NEG iki ayrı atom → **tek birleşik atom** (atom durumunda OR çözümü) | `hepatit_kontrol.py:1816-1834` | test #16 (regresyon: test #1, #2 korundu) |
| 3 | Belgeye dispatcher ASCII akım şeması (§1.1) | `docs/sut/SUT_4_2_13_HEPATIT_ANALIZ.md` | — |
| 4 | Belgeye başlangıç/devam dallanması ASCII şeması (§1.3) | aynı belge | — |
| 5 | 12 yolak için mini ASCII boolean şeması (§3-14) | aynı belge | — |
| 6 | Versiyon tagı 2026-05-17 → 2026-05-23 | aynı belge başlığı | — |

### Neden PIF kolu kritikti
SUT 4.2.13.1: "Tedaviye pegile interferonlar **VEYA** oral antiviraller ile başlanabilir." → PIF yol-a/yol-b'nin alternatifidir. Eski kodda `ust_or_ciftleri` sadece `[('(1)(a) HBV DNA', '(1)(b) ≥40 yaş')]` içerirken PIF kolu bağımsız AND-grup olarak hesaplanıyordu. Bu, PEG_IFN reçetelerinde yol-a/yol-b atomları YOK ise (HBV DNA <2000 ∨ yaş <40) PIF kolu uygun olsa bile **yanlış UYGUN_DEĞİL** üretiyordu.

### HBeAg birleştirme gerekçesi
`_hep_grup_durumu` herhangi bir atomun `veya_grubu=True` olması durumunda tüm grubu OR olarak değerlendirir. PIF kolunda ALT > 2×ÜS (AND mantığı) ve HBeAg+DNA eşik (POZ/NEG arası OR) atomları **aynı PIF grubunda** olmalıydı (SUT lafzı: "ALT > 2×ÜS **VE** [HBeAg eşik]"). İki ayrı atom (POZ ∨ NEG) `veya_grubu=True` kullanılırsa ALT atomu da OR sayılırdı → matematik bozulurdu. Çözüm: HBeAg POZ/NEG mantığını **tek atomun durumunda** çöz (atom durumunda VAR/YOK/KE üretiliyor, grup saf AND kalıyor).
