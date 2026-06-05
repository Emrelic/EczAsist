# -*- coding: utf-8 -*-
"""SUT metni kayıt — kategori → resmi SUT madde lafzı eşlemesi.

Atomik şema panelinin sağ tarafında "📖 SUT Kuralı" olarak gösterilir
(Medula ilaç bilgisi mesajı ile karıştırılmamalı: o ekrandaki
'medula_msj' alanı Medula provizyon yanıtıdır; bu modül SGK SUT
mevzuat lafzını verir).

Kaynak öncelik sırası:
  1. `sut_kurallari/<kategori>.json` dosyasında `sut_metni` alanı
     (motor üzerinden değerlendirilen kategoriler — tek kaynak)
  2. Bu modülde inline `_FALLBACK_METINLER` sözlüğü
     (henüz motora göçmemiş kategoriler için geçici)

Yeni kategori ekleme:
  - Motor üzerinden değerlendiriliyorsa → JSON kuralında `sut_metni` alanı
  - Henüz motor yoksa → `_FALLBACK_METINLER` içine kategori → metin ekle

Kaynak: docs/sut/SUT_tam_metin.txt (mevzuat.gov.tr MevzuatNo=17229).
"""
import json
import os
from functools import lru_cache
from typing import Dict, Optional


# Motor JSON kural dosyaları (uyumluluk.py'dekiyle aynı yapı)
_PROJE_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MOTOR_KURAL_DOSYALARI: Dict[str, str] = {
    'FIBRAT': os.path.join(_PROJE_KOK, 'sut_kurallari', 'fibrat_4_2_28_b.json'),
}


# Henüz motora geçmemiş kategoriler için inline fallback.
# Yeni kategori burada veya tercihen motor JSON'da tanımlanmalı.
# Kaynak: docs/sut/SUT_tam_metin.txt (mevzuat.gov.tr SUT).
_FALLBACK_METINLER: Dict[str, str] = {
    # SUT 4.2.28.A — Statinler (özet — tam metin için docs/sut)
    # Eklenmesi planlanan; şimdilik boş, GUI fallback davranışı devreye girer.

    # SUT 4.2.19 — Migrende ilaç kullanım ilkeleri
    'MIGREN': (
        "4.2.19 - Migrende ilaç kullanım ilkeleri\n"
        "(1) Triptanlar, nöroloji uzman hekimleri tarafından reçete edilir. "
        "Bu grup ilaçlardan yalnız bir etken madde reçete edilebilir ve ayda "
        "en fazla 6 doz/adet yazılabilir. Aynı ilacın farklı farmasötik "
        "formlarının aynı anda reçete edilmesi halinde birisinin bedeli ödenir.\n"
        "(2) Topiramat tedavisine, diğer profilaktik migren ilaçlarının 6 ay "
        "süreyle kullanılıp etkisiz kaldığı durumlarda nöroloji uzman hekimince "
        "düzenlenen uzman hekim raporunda bu husus belirtilerek nöroloji uzman "
        "hekimince başlanır.\n"
        "(3) Uzman hekim raporu 1 yıl süreyle geçerlidir ve nöroloji uzman "
        "hekimince düzenlenen uzman hekim raporuna dayanılarak diğer hekimler "
        "tarafından en fazla birer aylık dozda reçete edilmesi halinde bedeli "
        "ödenir."
    ),

    # SUT 4.2.14.C-(çç) — Ruksolitinib (Değişik:RG-19/10/2023-32344)
    'RUKSOLITINIB': (
        "4.2.14.C-(çç) Ruksolitinib\n"
        "(1) Primer miyelofibrozis, post polistemik miyelofibrosis veya "
        "esansiyel trombositemi sonrası ikincil miyelofibrosis tanılı "
        "hastalarda splenomegaliye bağlı semptomların tedavisinde aşağıdaki "
        "koşulların tümünü taşıyan hastalarda ilaca başlanır: "
        "a) Semptomatik masif splenomegalisi bulunan, "
        "b) DIPPS plus skorlama sistemine göre orta veya yüksek risk grubu olan, "
        "c) En az bir seri tedavi almış ve uluslararası çalışma grubu uzlaşı "
        "kriterlerine göre 8 haftadan fazla süren kot kavsi altında fizik "
        "muayene ile ölçülen dalak boyutunda başlangıca göre ≥%50 (USG ile "
        "ölçülen dalak hacminde ≥%35) azalma elde edilemeyen veya elde edilen "
        "yanıtı kaybolan, "
        "ç) Güncel kan sayım değerlerinde trombosit sayısının ≥100.000/mm3, "
        "hemoglobin düzeyinin ≥8 g/dl, nötrofil sayısının ≥1000/mm3 ve çevresel "
        "kan blast oranı <%10 olan, d) Kemik iliği nakline uygun olmayan.\n"
        "(2) Tedaviye başlandıktan 6 ay sonra yapılan yanıt değerlendirmesinde "
        "dalak boyutunda bir azalma yoksa veya konstitusyonel semptomlarda "
        "(ateş, gece terlemesi, kilo kaybı veya kaşıntı) tedavinin başlangıcından "
        "beri bir iyileşme görülmemişse tedavi kesilir.\n"
        "(3) Kortikosteroidler veya diğer sistemik tedavilere yetersiz yanıt "
        "veren; derece 2-4 akut Graft versus Host hastalığı (aGvHD) olan veya "
        "orta-ağır kronik Graft versus Host hastalığı (kGvHD) olan 12 yaş ve "
        "üzerindeki hastaların tedavisine ruxolitinib başlanabilir. aGvHD'de "
        "14. günde, kGvHD'de 6. ayda tam veya kısmi yanıt alınan hastalarda "
        "devam edilir.\n"
        "(4) JAK 2 (V617F veya Exon 12) mutasyonlarının varlığı ile Polisitemi "
        "Vera (PV) tanısı konulmuş olgularda; en az birini karşıladığı raporda "
        "belirtilmek koşuluyla: 1- ≥2 g/gün veya maksimum dozda hidroksiüre ile "
        "≥3 aylık tedaviye rağmen (a. Hct<%45 için ayda >1 flebotomi, b. "
        "trombosit>400000 ve beyaz küre>10000, c. dalakta USG ile küçülme yok, "
        "ç. yeni tromboz); 2- en düşük HÜ dozunda nötrofil<1000 ya da "
        "trombosit<100000 ya da hemoglobin<10; 3- HÜ ilişkili bacak ülseri / "
        "kontrol edilemeyen mukokutanöz belirti.\n"
        "(5) PV tanılı hastaların 32 haftalık tedavi sonunda dalakta minimum "
        "%35 küçülme ve tam kan sayımının normalize olması halinde devam edilir.\n"
        "(6) Üçüncü basamak resmi sağlık hizmeti sunucularında en az bir "
        "hematoloji uzmanının bulunduğu 3 ay süreli sağlık kurulu raporuna "
        "dayanılarak hematoloji uzman hekimlerince reçete edilir."
    ),
}


@lru_cache(maxsize=32)
def _motor_kuralindan_metin(kategori: str) -> Optional[str]:
    """Motor JSON kuralı varsa içinden `sut_metni` alanını oku."""
    yol = _MOTOR_KURAL_DOSYALARI.get(kategori.upper())
    if not yol or not os.path.exists(yol):
        return None
    try:
        with open(yol, 'r', encoding='utf-8') as f:
            kural = json.load(f)
        metin = kural.get('sut_metni')
        if metin:
            return str(metin).strip()
    except (OSError, json.JSONDecodeError):
        return None
    return None


def sut_metni_getir(kategori: Optional[str]) -> Optional[str]:
    """Kategori adı (FIBRAT/STATIN/YOAK/...) → resmî SUT madde lafzı.

    Args:
        kategori: 'verdict_kategori' alanı (örn. "FIBRAT", "STATIN").
                  Boş/None ise None döner.

    Returns:
        SUT lafzı (str). Bulunamazsa None.
    """
    if not kategori:
        return None
    k = kategori.upper().strip()
    metin = _motor_kuralindan_metin(k)
    if metin:
        return metin
    metin = _FALLBACK_METINLER.get(k)
    if metin:
        return metin.strip()
    return None


def sut_metni_var_mi(kategori: Optional[str]) -> bool:
    """Bu kategori için kayıtlı SUT lafzı var mı?"""
    return sut_metni_getir(kategori) is not None
