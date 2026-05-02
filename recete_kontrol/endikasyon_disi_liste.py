# -*- coding: utf-8 -*-
"""
SUT EK-4/A — Sağlık Bakanlığı Ek Onayı Alınmadan Kullanılabilecek
Endikasyon Dışı İlaç Listesi

Kaynak: TİTCK (Türkiye İlaç ve Tıbbi Cihaz Kurumu) Resmi Liste
- Ana liste: https://www.titck.gov.tr/dinamikmodul/45
- Son güncelleme: 17.03.2023 (Onkoloji Ek Listesi dahil)

Medula uyarı kodu: **272 — "Sağlık Bakanlığı Ek Onayı Alınmadan
Kullanılabilecek Endikasyon Dışı İlaçlar"**

Bu uyarı kodu seçildiğinde 20.00 katılım paylı sisteme girilir.
İlaç-tanı-branş kombinasyonu bu listede yer aldığı sürece SB ek onayı
gerekmez.

YAPIYI GENİŞLETME: Yeni ilaç eklemek için EK_ONAYSIZ_LISTE'ye yeni dict
ekle. Format:
{
    'isim': 'kısa açıklayıcı isim',
    'etkin_maddeler': ['ETKIN1', 'ETKIN2'],
    'ticari_adlar': ['TICARI1', 'TICARI2'],
    'branslar': ['nöroloji', 'iç hastalıkları'],
    'icd_kodlari': ['G43', 'G44.2'],
    'tanilar': ['migren', 'baş ağrısı'],
    'sut_kurali': 'TİTCK EK-4/A — açıklama',
    'ozel_kosullar': 'opsiyonel açıklama',
}
"""

import re
from typing import List, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════
# ENDİKASYON DIŞI LİSTE
# ═══════════════════════════════════════════════════════════════════════

EK_ONAYSIZ_LISTE: List[Dict] = [
    # ── NÖROLOJİ ─────────────────────────────────────────────────────────
    {
        'isim': 'Gabapentinoidler — Migren / Gerilim baş ağrısı / Nöropatik ağrı',
        'etkin_maddeler': ['PREGABALIN', 'GABAPENTIN'],
        'ticari_adlar': ['LYRICA', 'NEURONTIN', 'NERUDA', 'GABATEVA',
                          'GABAGAMMA', 'GABRICA', 'PREGALIN', 'PREGABEX',
                          'GABALEPT'],
        'branslar': ['nöroloji'],
        'icd_kodlari': ['G43', 'G44.2', 'G44', 'G54', 'G62', 'M79.7', 'F45.4'],
        'tanilar': ['migren', 'gerilim baş ağrısı', 'gerilim tipi baş ağrısı',
                    'nöropatik ağrı', 'fibromiyalji', 'kronik ağrı',
                    'sciatica', 'siyatik', 'lomber radikülopati',
                    'diyabetik nöropati', 'postherpetik nevralji'],
        'sut_kurali': 'TİTCK EK-4/A — Gabapentin/Pregabalin nöropatik ağrı, migren profilaksisi, gerilim baş ağrısı',
    },
    {
        'isim': 'Amitriptilin/Nortriptilin — Migren / Kronik ağrı',
        'etkin_maddeler': ['AMITRIPTILIN', 'NORTRIPTILIN', 'AMITRIPTYLINE'],
        'ticari_adlar': ['LAROXYL', 'TRIPTILIN', 'TRIPTILEN', 'AMITRIP'],
        'branslar': ['nöroloji', 'algoloji', 'ağrı', 'iç hastalıkları'],
        'icd_kodlari': ['G43', 'G44', 'M79.7', 'F45.4', 'G54.4'],
        'tanilar': ['migren', 'gerilim baş ağrısı', 'kronik ağrı',
                    'fibromiyalji', 'nöropatik ağrı'],
        'sut_kurali': 'TİTCK EK-4/A — Trisiklik antidepresanlar migren profilaksisi/kronik ağrı',
    },
    {
        'isim': 'Topiramat — Migren profilaksisi',
        'etkin_maddeler': ['TOPIRAMAT', 'TOPIRAMATE'],
        'ticari_adlar': ['TOPAMAX', 'TOPIRA', 'TOPRAGAL'],
        'branslar': ['nöroloji'],
        'icd_kodlari': ['G43'],
        'tanilar': ['migren', 'kronik migren'],
        'sut_kurali': 'TİTCK EK-4/A — Topiramat migren profilaksisi (≥4 atak/ay)',
    },
    {
        'isim': 'Botulinum Toksin — Kronik migren / Spastisite',
        'etkin_maddeler': ['BOTULINUM TOKSIN', 'BOTULINUM TOXIN', 'BOTULINUM',
                            'ABOBOTULINUM', 'INKOBOTULINUM'],
        'ticari_adlar': ['BOTOX', 'DYSPORT', 'XEOMIN', 'NEURONOX'],
        'branslar': ['nöroloji', 'fizik tedavi', 'frtr'],
        'icd_kodlari': ['G43', 'G24', 'G81', 'G82', 'G80', 'R25.2'],
        'tanilar': ['kronik migren', 'distoni', 'spastisite', 'serebral palsi',
                    'blefarospazm', 'hemifasiyal spazm'],
        'sut_kurali': 'TİTCK EK-4/A — Botulinum toksin kronik migren (PREEMPT protokolü), spastisite',
    },
    {
        'isim': 'Duloksetin — Diyabetik nöropati / Fibromiyalji / Kronik bel ağrısı',
        'etkin_maddeler': ['DULOKSETIN', 'DULOXETINE'],
        'ticari_adlar': ['CYMBALTA', 'DUXET', 'DULSEDA', 'DULOX'],
        'branslar': ['nöroloji', 'algoloji', 'fizik tedavi', 'iç hastalıkları',
                      'psikiyatri', 'ortopedi'],
        'icd_kodlari': ['G62', 'M79.7', 'M54', 'E11.4', 'E10.4'],
        'tanilar': ['diyabetik nöropati', 'fibromiyalji', 'kronik bel ağrısı',
                    'nöropatik ağrı', 'kronik kas iskelet ağrısı'],
        'sut_kurali': 'TİTCK EK-4/A — Duloksetin diyabetik periferal nöropatik ağrı/fibromiyalji',
    },

    # ── DERMATOLOJİ ──────────────────────────────────────────────────────
    {
        'isim': 'Hidroksiklorokin — Diskoid lupus / Seboreik dermatit',
        'etkin_maddeler': ['HIDROKSIKLOROKIN', 'HYDROXYCHLOROQUINE'],
        'ticari_adlar': ['PLAQUENIL', 'QUENSYL', 'HCQ'],
        'branslar': ['dermatoloji', 'romatoloji', 'iç hastalıkları'],
        'icd_kodlari': ['L93.0', 'L93', 'L21', 'M32', 'M35.0'],
        'tanilar': ['diskoid lupus', 'lupus eritematozus', 'seboreik dermatit',
                    'sjögren sendromu', 'kutanöz lupus'],
        'sut_kurali': 'TİTCK EK-4/A — Hidroksiklorokin diskoid lupus (L93.0), inatçı seboreik dermatit (L21)',
    },
    {
        'isim': 'Düşük doz Metotreksat — Psoriazis / Romatoid artrit',
        'etkin_maddeler': ['METOTREKSAT', 'METHOTREXATE'],
        'ticari_adlar': ['METOJECT', 'EMTEXATE', 'TREXAN', 'METEX'],
        'branslar': ['dermatoloji', 'romatoloji', 'iç hastalıkları'],
        'icd_kodlari': ['L40', 'M05', 'M06', 'L94'],
        'tanilar': ['psoriazis', 'sedef', 'romatoid artrit', 'psoriatik artrit',
                    'lokalize skleroderma'],
        'sut_kurali': 'TİTCK EK-4/A — Düşük doz MTX dermatolojik/romatolojik endikasyonlar',
    },
    {
        'isim': 'Doksisiklin (uzun süreli düşük doz) — Rozasea / Akne',
        'etkin_maddeler': ['DOKSISIKLIN', 'DOXYCYCLINE'],
        'ticari_adlar': ['MONODOX', 'DOKSIN', 'TETRADOX'],
        'branslar': ['dermatoloji'],
        'icd_kodlari': ['L70', 'L71'],
        'tanilar': ['akne', 'akne vulgaris', 'rozasea', 'rosacea', 'periorbital dermatit'],
        'sut_kurali': 'TİTCK EK-4/A — Doksisiklin rozasea/akne (uzun süreli, antiinflamatuar doz)',
    },

    # ── KARDİYOLOJİ ─────────────────────────────────────────────────────
    {
        'isim': 'Spironolakton — Sistolik kalp yetmezliği',
        'etkin_maddeler': ['SPIRONOLAKTON', 'SPIRONOLACTONE'],
        'ticari_adlar': ['ALDACTONE', 'SPIRONO', 'ALDOCAR'],
        'branslar': ['kardiyoloji', 'iç hastalıkları'],
        'icd_kodlari': ['I50', 'I11.0', 'I13.0'],
        'tanilar': ['kalp yetmezliği', 'heart failure', 'NYHA III', 'NYHA IV',
                    'sistolik kalp yetmezliği', 'HFrEF'],
        'sut_kurali': 'TİTCK EK-4/A — Spironolakton kalp yetmezliği (NYHA III-IV)',
    },
    {
        'isim': 'Sildenafil/Tadalafil — Pulmoner arteriyel hipertansiyon',
        'etkin_maddeler': ['SILDENAFIL', 'TADALAFIL'],
        'ticari_adlar': ['REVATIO', 'ADCIRCA', 'VIAGRA', 'CIALIS', 'SILDENA'],
        'branslar': ['kardiyoloji', 'göğüs hastalıkları', 'pediatrik kardiyoloji'],
        'icd_kodlari': ['I27.0', 'I27.2', 'I27'],
        'tanilar': ['pulmoner arteriyel hipertansiyon', 'pah',
                    'pulmoner hipertansiyon'],
        'sut_kurali': 'TİTCK EK-4/A — Sildenafil/Tadalafil PAH (kardiyoloji/göğüs uzman raporu)',
    },
    {
        'isim': 'Tadalafil 5 mg — Benign prostat hiperplazisi',
        'etkin_maddeler': ['TADALAFIL'],
        'ticari_adlar': ['CIALIS', 'TADAFIL'],
        'branslar': ['üroloji'],
        'icd_kodlari': ['N40'],
        'tanilar': ['bph', 'benign prostat hiperplazi', 'prostat hiperplazi'],
        'ozel_kosullar': 'Sadece 5 mg/gün doz',
        'sut_kurali': 'TİTCK EK-4/A — Tadalafil 5 mg BPH (LUTS)',
    },

    # ── ROMATOLOJİ / İMMUNOLOJİ ──────────────────────────────────────────
    {
        'isim': 'Anakinra — Ailevi Akdeniz Ateşi (kolşisin dirençli)',
        'etkin_maddeler': ['ANAKINRA'],
        'ticari_adlar': ['KINERET'],
        'branslar': ['romatoloji', 'iç hastalıkları', 'çocuk romatoloji'],
        'icd_kodlari': ['M04.1', 'E85.0'],
        'tanilar': ['ailevi akdeniz ateşi', 'fmf', 'familial mediterranean fever',
                    'kolşisin direnç', 'colchicine resistant'],
        'ozel_kosullar': 'Kolşisin dirençli/intolerans gerekli',
        'sut_kurali': 'TİTCK EK-4/A — Anakinra kolşisin dirençli/intoleranslı FMF',
    },
    {
        'isim': 'Tocilizumab — Dev hücreli arterit / sJIA',
        'etkin_maddeler': ['TOSILIZUMAB', 'TOCILIZUMAB'],
        'ticari_adlar': ['ACTEMRA', 'ROACTEMRA'],
        'branslar': ['romatoloji', 'çocuk romatoloji'],
        'icd_kodlari': ['M31.5', 'M31.6', 'M08.2'],
        'tanilar': ['dev hücreli arterit', 'gca', 'temporal arterit',
                    'sistemik jia', 'sjıa', 'sistemik juvenil idyopatik artrit'],
        'sut_kurali': 'TİTCK EK-4/A — Tocilizumab dev hücreli arterit, sJIA',
    },
    {
        'isim': 'Rituksimab — ITP / AIHA / Vaskülit (MS dışı)',
        'etkin_maddeler': ['RITUKSIMAB', 'RITUXIMAB'],
        'ticari_adlar': ['MABTHERA', 'RIXATHON', 'TRUXIMA', 'RIABNI'],
        'branslar': ['hematoloji', 'romatoloji', 'iç hastalıkları', 'nöroloji'],
        'icd_kodlari': ['D69.3', 'D59.1', 'M31.3', 'M31.7', 'M31.30', 'G70.0',
                         'M05', 'L12'],
        'tanilar': ['itp', 'idiyopatik trombositopenik purpura',
                    'otoimmün hemolitik anemi', 'aiha', 'wegener',
                    'granülomatöz polianjitis', 'gpa', 'mikroskopik polianjitis',
                    'mpa', 'pemfigus', 'myasteni', 'romatoid artrit',
                    'nöromiyelitis optika', 'nmo'],
        'sut_kurali': 'TİTCK EK-4/A — Rituksimab ITP, AIHA, ANCA vaskülit, pemfigus, NMO',
    },
    {
        'isim': 'IVIG — Otoimmün hastalıklar / Kawasaki / GBS',
        'etkin_maddeler': ['IMMUNGLOBULIN', 'IMMUNOGLOBULIN', 'IGG',
                            'INSAN IMMUNGLOBULINI'],
        'ticari_adlar': ['GAMMAGARD', 'PRIVIGEN', 'OCTAGAM', 'KIOVIG',
                          'INTRATECT', 'IGVENA'],
        'branslar': ['hematoloji', 'nöroloji', 'romatoloji', 'pediatri',
                      'çocuk sağlığı', 'iç hastalıkları'],
        'icd_kodlari': ['M30.3', 'D69.3', 'G61.0', 'G61.8', 'G70.0', 'G35'],
        'tanilar': ['kawasaki', 'kawasaki hastalığı', 'guillain-barre', 'gbs',
                    'cidp', 'kronik inflamatuar demiyelinizan polineuropati',
                    'myasteni', 'multifokal motor', 'mmn',
                    'itp', 'otoimmün ensefalit'],
        'sut_kurali': 'TİTCK EK-4/A — IVIG Kawasaki, GBS, CIDP, Myasteni, ITP',
    },

    # ── ONKOLOJİ (Ek Liste 17.03.2023) ────────────────────────────────────
    {
        'isim': 'Bevacizumab — Yaş tipi makula dejenerasyonu (intravitreal)',
        'etkin_maddeler': ['BEVACIZUMAB', 'BEVASIZUMAB'],
        'ticari_adlar': ['AVASTIN'],
        'branslar': ['göz hastalıkları', 'oftalmoloji'],
        'icd_kodlari': ['H35.3', 'H35'],
        'tanilar': ['yaş tipi makula', 'amd', 'yaşa bağlı makula dejenerasyonu',
                    'koroidal neovaskularizasyon', 'cnv', 'diabetik makula ödemi',
                    'rvo', 'retinal ven oklüzyonu'],
        'ozel_kosullar': 'İntravitreal uygulama, off-label oftalmik kullanım',
        'sut_kurali': 'TİTCK EK-4/A Onkoloji Eki — Bevacizumab göz içi (yaş AMD/DME/RVO)',
    },
    {
        'isim': 'Trastuzumab — HER2+ mide kanseri',
        'etkin_maddeler': ['TRASTUZUMAB'],
        'ticari_adlar': ['HERCEPTIN', 'HERZUMA', 'KANJINTI', 'TRAZIMERA'],
        'branslar': ['onkoloji', 'tıbbi onkoloji'],
        'icd_kodlari': ['C16'],
        'tanilar': ['mide kanseri', 'gastrik kanser', 'gastric cancer'],
        'ozel_kosullar': 'HER2 pozitif olmalı (IHC 3+ veya FISH amplifikasyon)',
        'sut_kurali': 'TİTCK EK-4/A Onkoloji Eki — Trastuzumab HER2+ ileri evre mide kanseri',
    },
    {
        'isim': 'Cetuximab — KRAS wild-type kolorektal kanser',
        'etkin_maddeler': ['CETUKSIMAB', 'CETUXIMAB'],
        'ticari_adlar': ['ERBITUX'],
        'branslar': ['onkoloji', 'tıbbi onkoloji'],
        'icd_kodlari': ['C18', 'C19', 'C20'],
        'tanilar': ['kolorektal kanser', 'kolon kanseri', 'rektum kanseri',
                    'metastatik kolorektal'],
        'ozel_kosullar': 'KRAS wild-type (mutasyonsuz) gerekli',
        'sut_kurali': 'TİTCK EK-4/A Onkoloji Eki — Cetuximab metastatik KRAS wt kolorektal',
    },

    # ── PEDİATRİ / ÇOCUK PSİKİYATRİSİ ─────────────────────────────────────
    {
        'isim': 'Risperidon — Otizm spektrum bozukluğu (agresyon)',
        'etkin_maddeler': ['RISPERIDON', 'RISPERIDONE'],
        'ticari_adlar': ['RISPERDAL', 'RIXPER', 'RISPOLEPT'],
        'branslar': ['çocuk psikiyatrisi', 'psikiyatri', 'çocuk sağlığı'],
        'icd_kodlari': ['F84', 'F84.0', 'F84.5', 'F90', 'F91'],
        'tanilar': ['otizm', 'asperger', 'otistik', 'pdd', 'davranış bozukluğu',
                    'agresyon', 'irritabilite', 'kendine zarar verme'],
        'sut_kurali': 'TİTCK EK-4/A — Risperidon otizm spektrum bozukluğunda agresyon/irritabilite (5-16 yaş)',
    },
    {
        'isim': 'Aripiprazol — Otizm + agresyon',
        'etkin_maddeler': ['ARIPIPRAZOL', 'ARIPIPRAZOLE'],
        'ticari_adlar': ['ABILIFY', 'ARIPIRA', 'ABZOL'],
        'branslar': ['çocuk psikiyatrisi', 'psikiyatri'],
        'icd_kodlari': ['F84', 'F84.0'],
        'tanilar': ['otizm', 'otistik', 'asperger', 'agresyon', 'irritabilite'],
        'sut_kurali': 'TİTCK EK-4/A — Aripiprazol otizm spektrum (6-17 yaş)',
    },
    {
        'isim': 'Modafinil — Narkolepsi / Aşırı gündüz uykululuğu',
        'etkin_maddeler': ['MODAFINIL'],
        'ticari_adlar': ['VIGIL', 'PROVIGIL', 'MODIODAL'],
        'branslar': ['nöroloji', 'çocuk nörolojisi', 'göğüs hastalıkları'],
        'icd_kodlari': ['G47.4', 'G47.8'],
        'tanilar': ['narkolepsi', 'aşırı gündüz uykululuğu', 'osas',
                    'shift work disorder', 'idiopatik hipersomnia'],
        'sut_kurali': 'TİTCK EK-4/A — Modafinil narkolepsi, OSAS rezidüel uykululuk',
    },

    # ── PSİKİYATRİ ───────────────────────────────────────────────────────
    {
        'isim': 'Fluoksetin — Premenstrüel disforik bozukluk (PMDB)',
        'etkin_maddeler': ['FLUOKSETIN', 'FLUOXETINE'],
        'ticari_adlar': ['PROZAC', 'DEPRINA', 'ZEDPRES', 'FLUXEN'],
        'branslar': ['psikiyatri', 'kadın hastalıkları', 'jinekoloji'],
        'icd_kodlari': ['N94.3', 'F32', 'F33'],
        'tanilar': ['premenstrüel disforik', 'pmdb', 'pmdd',
                    'premenstrüel sendrom'],
        'sut_kurali': 'TİTCK EK-4/A — Fluoksetin PMDB',
    },
    {
        'isim': 'Mirtazapin — Yaşlı iştahsızlık + depresyon + uyku',
        'etkin_maddeler': ['MIRTAZAPIN', 'MIRTAZAPINE'],
        'ticari_adlar': ['REMERON', 'MIRTARON', 'NORSET'],
        'branslar': ['psikiyatri', 'iç hastalıkları', 'geriatri', 'onkoloji'],
        'icd_kodlari': ['F32', 'F33', 'R63.0'],
        'tanilar': ['depresyon', 'iştahsızlık', 'kilo kaybı', 'uyku bozukluğu',
                    'kanser kaşeksisi'],
        'sut_kurali': 'TİTCK EK-4/A — Mirtazapin yaşlı/onkoloji depresyon + iştahsızlık',
    },

    # ── HEMATOLOJİ ───────────────────────────────────────────────────────
    {
        'isim': 'Eltrombopag — ITP / Aplastik anemi',
        'etkin_maddeler': ['ELTROMBOPAG'],
        'ticari_adlar': ['REVOLADE', 'PROMACTA'],
        'branslar': ['hematoloji', 'çocuk hematolojisi'],
        'icd_kodlari': ['D69.3', 'D61'],
        'tanilar': ['itp', 'idiyopatik trombositopenik purpura',
                    'aplastik anemi', 'kronik itp'],
        'sut_kurali': 'TİTCK EK-4/A — Eltrombopag kronik ITP, ağır aplastik anemi',
    },
    {
        'isim': 'Romiplostim — ITP',
        'etkin_maddeler': ['ROMIPLOSTIM'],
        'ticari_adlar': ['NPLATE'],
        'branslar': ['hematoloji'],
        'icd_kodlari': ['D69.3'],
        'tanilar': ['itp', 'kronik itp'],
        'sut_kurali': 'TİTCK EK-4/A — Romiplostim kronik ITP',
    },

    # ── ENDOKRIN / METABOLIK ──────────────────────────────────────────────
    {
        'isim': 'Metformin — PCOS / Prediabetes',
        'etkin_maddeler': ['METFORMIN'],
        'ticari_adlar': ['GLUKOFEN', 'GLIFOR', 'DIAFORMIN', 'GLUCOPHAGE'],
        'branslar': ['kadın hastalıkları', 'jinekoloji', 'endokrinoloji',
                      'iç hastalıkları'],
        'icd_kodlari': ['E28.2', 'R73', 'R73.9'],
        'tanilar': ['pcos', 'polikistik over', 'prediabet', 'glukoz tolerans',
                    'insülin direnç', 'metabolik sendrom'],
        'sut_kurali': 'TİTCK EK-4/A — Metformin PCOS/insülin direnci/prediabet',
    },

    # ── PULMONOLOJİ ───────────────────────────────────────────────────────
    {
        'isim': 'Pirfenidon / Nintedanib — İdiyopatik pulmoner fibrozis',
        'etkin_maddeler': ['PIRFENIDON', 'PIRFENIDONE', 'NINTEDANIB'],
        'ticari_adlar': ['ESBRIET', 'OFEV'],
        'branslar': ['göğüs hastalıkları', 'romatoloji'],
        'icd_kodlari': ['J84.1', 'J84'],
        'tanilar': ['ipf', 'idiyopatik pulmoner fibrozis',
                    'progresif fibrozan ild', 'sklerodermaya bağlı ild'],
        'sut_kurali': 'TİTCK EK-4/A — Antifibrotik IPF/PF-ILD',
    },

    # ── ÜROLOJİ ──────────────────────────────────────────────────────────
    {
        'isim': 'Mirabegron — Overaktif mesane',
        'etkin_maddeler': ['MIRABEGRON'],
        'ticari_adlar': ['BETMIGA'],
        'branslar': ['üroloji', 'kadın hastalıkları'],
        'icd_kodlari': ['N32.8', 'N31', 'N39.4'],
        'tanilar': ['overaktif mesane', 'oab', 'urge inkontinans',
                    'sıkışma inkontinansı'],
        'sut_kurali': 'TİTCK EK-4/A — Mirabegron OAB (antimuskarinik intoleransı)',
    },
]


# ═══════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════

def _normalize(metin: str) -> str:
    """Türkçe karakter farkı gözetmeden, küçük harfe çevir."""
    if not metin:
        return ""
    t = metin.upper()
    tr_map = str.maketrans({
        'İ': 'I', 'I': 'I', 'Ö': 'O', 'Ü': 'U', 'Ş': 'S', 'Ç': 'C', 'Ğ': 'G',
    })
    return t.translate(tr_map).lower()


def _ilac_eslesir_mi(kayit: Dict, ilac_adi: str, etkin_madde: str) -> bool:
    """İlaç adı veya etkin maddesi listedeki kayıtla eşleşiyor mu?"""
    ilac_norm = _normalize(ilac_adi or '')
    etkin_norm = _normalize(etkin_madde or '')
    for em in kayit.get('etkin_maddeler', []):
        if _normalize(em) in etkin_norm or _normalize(em) in ilac_norm:
            return True
    for ta in kayit.get('ticari_adlar', []):
        if _normalize(ta) in ilac_norm:
            return True
    return False


def _brans_eslesir_mi(kayit: Dict, doktor_uzmanligi: str) -> bool:
    """Doktor uzmanlığı listedeki branşlardan biriyle eşleşiyor mu?

    Boş doktor branşı = kontrol edilemiyor → True döner (manuel kontrol).
    """
    if not doktor_uzmanligi:
        return True  # branş bilgisi yok, kısıtlama yapma
    doktor_norm = _normalize(doktor_uzmanligi)
    for brans in kayit.get('branslar', []):
        if _normalize(brans) in doktor_norm:
            return True
    return False


def _tani_eslesir_mi(kayit: Dict, teshis_metin: str) -> tuple:
    """Tanı metni listedeki tanılarla veya ICD kodlarıyla eşleşiyor mu?

    Returns: (bool, str) — eşleşme durumu + bulunan tanı/kod
    """
    if not teshis_metin:
        return False, ""
    teshis_norm = _normalize(teshis_metin)
    teshis_upper = teshis_metin.upper()

    # ICD kodu kontrolü (orijinal büyük harf, başta nokta yok)
    for icd in kayit.get('icd_kodlari', []):
        if icd.upper() in teshis_upper:
            return True, f"ICD {icd}"

    # Tanı metni kontrolü
    for tani in kayit.get('tanilar', []):
        if _normalize(tani) in teshis_norm:
            return True, tani

    return False, ""


# ═══════════════════════════════════════════════════════════════════════
# ANA KONTROL FONKSİYONU
# ═══════════════════════════════════════════════════════════════════════

def endikasyon_disi_kontrol(ilac_adi: str, etkin_madde: str,
                              doktor_uzmanligi: str = "",
                              recete_teshisleri: Optional[List[str]] = None,
                              rapor_tanilari: Optional[List[str]] = None,
                              rapor_aciklamalari: Optional[List[str]] = None) -> Dict:
    """
    SUT EK-4/A kontrol — Uyarı kodu 272 ile çağrılır.

    İlaç + tanı + branş kombinasyonunu listede arar. Eşleşirse UYGUN.

    Args:
        ilac_adi: Reçetedeki ilaç adı
        etkin_madde: İlacın etkin maddesi
        doktor_uzmanligi: Doktor branşı (uzmanlık)
        recete_teshisleri: Reçete teşhis listesi
        rapor_tanilari: Rapor tanı listesi
        rapor_aciklamalari: Rapor açıklama metinleri

    Returns:
        dict: {
            'durum': 'UYGUN' | 'UYGUN_DEGIL' | 'KONTROL_EDILEMEDI',
            'mesaj': str,
            'eslesen_kayit': dict | None,
            'eslesen_tani': str,
            'sut_kurali': str,
        }
    """
    teshis_metin = ' '.join((recete_teshisleri or []) +
                              (rapor_tanilari or []) +
                              (rapor_aciklamalari or []))

    # 1. İlaç listede mi?
    eslesen_ilaclar = []
    for kayit in EK_ONAYSIZ_LISTE:
        if _ilac_eslesir_mi(kayit, ilac_adi, etkin_madde):
            eslesen_ilaclar.append(kayit)

    if not eslesen_ilaclar:
        return {
            'durum': 'KONTROL_EDILEMEDI',
            'mesaj': f'İlaç ({ilac_adi}) TİTCK EK-4/A listesinde bulunamadı — '
                     f'manuel kontrol gerekli',
            'eslesen_kayit': None,
            'eslesen_tani': '',
            'sut_kurali': 'TİTCK EK-4/A — Ek Onaysız Endikasyon Dışı İlaç Listesi',
        }

    # 2. Her aday kayıt için tanı + branş kontrolü
    en_iyi_eslesme = None
    eksik_neden = []

    for kayit in eslesen_ilaclar:
        tani_ok, eslesen_tani = _tani_eslesir_mi(kayit, teshis_metin)
        brans_ok = _brans_eslesir_mi(kayit, doktor_uzmanligi)

        if tani_ok and brans_ok:
            return {
                'durum': 'UYGUN',
                'mesaj': f'TİTCK EK-4/A: {kayit["isim"]} — {eslesen_tani} '
                         f'tanısı + uygun branş ({doktor_uzmanligi or "branş kontrolü atlandı"})',
                'eslesen_kayit': kayit,
                'eslesen_tani': eslesen_tani,
                'sut_kurali': kayit.get('sut_kurali', ''),
            }

        # En iyi (kısmi) eşleşmeyi takip et
        if tani_ok and not brans_ok:
            en_iyi_eslesme = (kayit, eslesen_tani, 'brans')
            eksik_neden.append(f'{kayit["isim"]}: tanı ({eslesen_tani}) eşleşti '
                                 f'ama doktor branşı ({doktor_uzmanligi}) liste dışı '
                                 f'(beklenen: {", ".join(kayit["branslar"])})')
        elif brans_ok and not tani_ok:
            en_iyi_eslesme = (kayit, '', 'tani')
            eksik_neden.append(f'{kayit["isim"]}: branş uygun ama tanı eşleşmedi '
                                 f'(beklenen tanılar: {", ".join(kayit["tanilar"][:3])}...)')

    if en_iyi_eslesme:
        kayit, eslesen_tani, eksik = en_iyi_eslesme
        return {
            'durum': 'UYGUN_DEGIL',
            'mesaj': f'TİTCK EK-4/A: İlaç listede ama '
                     + ('branş uygun değil' if eksik == 'brans' else 'tanı eşleşmedi')
                     + ' — ' + (eksik_neden[0] if eksik_neden else ''),
            'eslesen_kayit': kayit,
            'eslesen_tani': eslesen_tani,
            'sut_kurali': kayit.get('sut_kurali', ''),
        }

    # İlaç var ama tanı/branş hiç eşleşmedi
    aday = eslesen_ilaclar[0]
    return {
        'durum': 'UYGUN_DEGIL',
        'mesaj': f'TİTCK EK-4/A: {aday["isim"]} kapsamında ama '
                 f'gerekli tanı veya branş eşleşmedi (tanılar: '
                 f'{", ".join(aday["tanilar"][:3])}...)',
        'eslesen_kayit': aday,
        'eslesen_tani': '',
        'sut_kurali': aday.get('sut_kurali', ''),
    }


def liste_istatistikleri() -> Dict:
    """Liste hakkında özet istatistik."""
    branslar = set()
    icd_kodlari = set()
    for k in EK_ONAYSIZ_LISTE:
        branslar.update(k.get('branslar', []))
        icd_kodlari.update(k.get('icd_kodlari', []))
    return {
        'toplam_kayit': len(EK_ONAYSIZ_LISTE),
        'toplam_brans': len(branslar),
        'toplam_icd': len(icd_kodlari),
        'branslar': sorted(branslar),
    }
