"""
Optimize Profil Test Aracı
Farklı optimize profillerini test et ve sonuçları göster
"""

import sys
import io
from timing_settings import get_timing_settings

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

timing = get_timing_settings()

print("=" * 100)
print("OPTİMİZASYON PROFİLLERİ TEST ARACI")
print("=" * 100)

profiles = [
    {
        "name": "cok_guvenli",
        "title": "1. ÇOK GÜVENLİ",
        "desc": "Yavaş/kararsız sistemler için",
        "multiplier": 1.5,
        "baslangic": 3.0,
        "risk": "🟢 Çok Düşük",
        "hiz": "⚪ Yavaş",
        "kullanim": "İlk kurulum, yavaş bilgisayarlar"
    },
    {
        "name": "guvenli",
        "title": "2. GÜVENLİ (ÖNERİLEN)",
        "desc": "Standart kullanım",
        "multiplier": 1.3,
        "baslangic": 3.0,
        "risk": "🟢 Düşük",
        "hiz": "🟡 Orta",
        "kullanim": "Genel kullanım (varsayılan)"
    },
    {
        "name": "dengeli",
        "title": "3. DENGELİ",
        "desc": "Stabil sistemler için",
        "multiplier": 1.2,
        "baslangic": 1.0,
        "risk": "🟡 Orta",
        "hiz": "🟢 Hızlı",
        "kullanim": "Stabil çalışan sistemler"
    },
    {
        "name": "agresif",
        "title": "4. AGRESİF",
        "desc": "Çok hızlı/stabil sistemler",
        "multiplier": 1.1,
        "baslangic": 0.5,
        "risk": "🟠 Yüksek",
        "hiz": "🟢 Çok Hızlı",
        "kullanim": "Hızlı bilgisayarlar, deneyimli kullanıcılar"
    },
    {
        "name": "cok_agresif",
        "title": "5. ÇOK AGRESİF (RİSKLİ!)",
        "desc": "SADECE test/debug için",
        "multiplier": 1.1,
        "baslangic": 0.1,
        "risk": "🔴 Çok Yüksek",
        "hiz": "⚡ Maksimum",
        "kullanim": "Test ve hata ayıklama amaçlı"
    }
]

print("\nMEVCUT PROFİLLER:\n")

for p in profiles:
    print(f"{p['title']}")
    print(f"  Açıklama: {p['desc']}")
    print(f"  Çarpan: {p['multiplier']}x (%{int((p['multiplier']-1)*100)} güvenlik marjı)")
    print(f"  Başlangıç: {p['baslangic']}s")
    print(f"  Risk: {p['risk']}")
    print(f"  Hız: {p['hiz']}")
    print(f"  Kullanım: {p['kullanim']}")
    print()

print("=" * 100)
print("KARŞILAŞTIRMA - Örnek İşlem: ilac_butonu (gerçek: 1.595s)")
print("=" * 100)
print(f"\n{'Profil':<20} {'Başlangıç':<15} {'İlk Deneme Risk':<20} {'Optimize Sonrası':<20}")
print("-" * 100)

gercek_sure = 1.595  # ilac_butonu gerçek ortalaması

for p in profiles:
    ilk_deneme_risk = "YOK" if p['baslangic'] >= gercek_sure else f"{((gercek_sure - p['baslangic']) / gercek_sure * 100):.0f}%"
    optimize_sonrasi = gercek_sure * p['multiplier']

    print(f"{p['name']:<20} {p['baslangic']:<15.1f}s {ilk_deneme_risk:<20} {optimize_sonrasi:<20.3f}s")

print("\n" + "=" * 100)
print("TOPLAM ZAMAN TAHMİNİ (2500 işlem için)")
print("=" * 100)

# İstatistiklerden gerçek verileri al
import json
try:
    with open('timing_stats.json', 'r', encoding='utf-8') as f:
        stats = json.load(f)

    print(f"\n{'Profil':<20} {'Toplam Sure':<15} {'Guvenli Göre':<20}")
    print("-" * 100)

    for p in profiles:
        toplam = 0
        for key, data in stats.items():
            count = data['count']
            avg = data['total_time'] / count
            optimal = avg * p['multiplier']
            toplam += optimal * count

        guvenli_toplam = sum((d['total_time']/d['count']) * 1.3 * d['count'] for d in stats.values())
        fark = toplam - guvenli_toplam

        print(f"{p['name']:<20} {toplam/60:<15.1f}dk {fark:>+18.1f}s")

except Exception as e:
    print(f"İstatistik dosyası okunamadı: {e}")

print("\n" + "=" * 100)
print("PROFİL UYGULAMA ÖRNEKLERİ")
print("=" * 100)

print("""
Python'dan:
    from timing_settings import get_timing_settings
    timing = get_timing_settings()

    # Güvenli profil (önerilen)
    timing.optimize_profile_uygula("guvenli")

    # Dengeli profil
    timing.optimize_profile_uygula("dengeli")

    # Agresif profil (0.1s başlangıç + 1.1x çarpan)
    timing.optimize_profile_uygula("cok_agresif")

Manuel ayarlama:
    timing.optimize_mode_ac(multiplier=1.1, baslangic_suresi=0.1)
""")

print("=" * 100)
print("ÖNERİ")
print("=" * 100)

print("""
🎯 SİSTEMİNİZ İÇİN ÖNERİ:

Ortalama işlem süresi: 2.454s (yavaş sistem)

1. İLK ÇALIŞTIRMA: "guvenli" profil kullanın
   timing.optimize_profile_uygula("guvenli")

2. 10-20 REÇETE TEST EDİN

3. BAŞARILI İSE: "dengeli" profil deneyin
   timing.optimize_profile_uygula("dengeli")

4. ÇOK HIZLI SİSTEM İSE: "agresif" deneyin
   timing.optimize_profile_uygula("agresif")

⚠️  "cok_agresif" profil SADECE test için önerilir!
   İlk çalıştırmalarda %97 hata riski var.
""")

print("=" * 100)
