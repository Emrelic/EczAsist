"""
Agresif Optimizasyon Analizi
Başlangıç: 0.1s, Çarpan: 1.1 (yani %10 fazla)
"""

import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# İstatistikleri oku
with open('timing_stats.json', 'r', encoding='utf-8') as f:
    stats = json.load(f)

# Farklı senaryoları karşılaştır
print("=" * 100)
print("AGRESİF OPTİMİZASYON ANALİZİ")
print("=" * 100)
print("\nSenaryo Karşılaştırması:")
print("-" * 100)
print(f"{'İşlem':<30} {'Gerçek':<10} {'1.3x (Güvenli)':<18} {'1.1x (Agresif)':<18} {'Fark':<12}")
print("-" * 100)

total_saving = 0
risky_operations = []

for key, data in sorted(stats.items(), key=lambda x: x[1]['total_time'] / x[1]['count'], reverse=True):
    count = data['count']
    total_time = data['total_time']
    average = total_time / count

    safe_value = average * 1.3  # %30 fazla (güvenli)
    aggressive_value = average * 1.1  # %10 fazla (agresif)

    diff = safe_value - aggressive_value
    total_saving += diff * count

    # Risk analizi
    variance_margin = aggressive_value - average
    if variance_margin < 0.1:  # 100ms'den az güvenlik marjı
        risky_operations.append({
            'key': key,
            'average': average,
            'aggressive': aggressive_value,
            'margin': variance_margin,
            'count': count
        })

    print(f"{key:<30} {average:<10.3f} {safe_value:<18.3f} {aggressive_value:<18.3f} {diff:>+11.3f}s")

print("\n" + "=" * 100)
print(f"TOPLAM ZAMAN TASARRUFU: {total_saving:.1f} saniye")
print(f"İşlem Başına Ortalama: {total_saving / sum(d['count'] for d in stats.values()):.3f}s")
print("=" * 100)

# Başlangıç süresi analizi
print("\n\nBAŞLANGIÇ SÜRESİ ANALİZİ (0.1s vs 3.0s)")
print("=" * 100)

print("\n🎯 Senaryo: Tüm ayarlar 0.1s'den başlasın\n")

slow_ops = [(k, v['total_time']/v['count']) for k, v in stats.items() if v['total_time']/v['count'] > 1.0]
fast_ops = [(k, v['total_time']/v['count']) for k, v in stats.items() if v['total_time']/v['count'] < 0.5]

print(f"Yavaş işlemler (>1s): {len(slow_ops)} adet")
for key, avg in sorted(slow_ops, key=lambda x: x[1], reverse=True)[:10]:
    first_attempt_fail_risk = (avg - 0.1) / avg * 100
    print(f"  - {key:<30} Gerçek: {avg:.3f}s, İlk deneme: 0.1s → Risk: {first_attempt_fail_risk:.0f}%")

print(f"\nHızlı işlemler (<0.5s): {len(fast_ops)} adet")
for key, avg in sorted(fast_ops, key=lambda x: x[1]):
    print(f"  - {key:<30} Gerçek: {avg:.3f}s, İlk deneme: 0.1s → ✓ Makul")

# Risk analizi
print("\n\n" + "=" * 100)
print("RİSK ANALİZİ - 1.1x Çarpan")
print("=" * 100)

print(f"\nYüksek Riskli İşlemler (<100ms güvenlik marjı): {len(risky_operations)} adet\n")
for op in sorted(risky_operations, key=lambda x: x['margin']):
    risk_percent = (op['margin'] / op['average']) * 100
    print(f"⚠️  {op['key']:<30} Marj: {op['margin']*1000:>6.1f}ms ({risk_percent:>5.1f}%) × {op['count']} kere")

# Güvenlik marjı karşılaştırması
print("\n\nGÜVENLİK MARJI KARŞILAŞTIRMASI")
print("=" * 100)
print(f"\n{'Çarpan':<15} {'Güvenlik Marjı':<20} {'Risk Seviyesi':<20} {'Önerilen Kullanım'}")
print("-" * 100)
print(f"{'1.5x':<15} {'%50 fazla':<20} {'🟢 Çok Güvenli':<20} Yavaş/kararsız sistemler")
print(f"{'1.3x':<15} {'%30 fazla':<20} {'🟢 Güvenli':<20} Standart (önerilen)")
print(f"{'1.2x':<15} {'%20 fazla':<20} {'🟡 Dengeli':<20} Stabil sistemler")
print(f"{'1.1x':<15} {'%10 fazla':<20} {'🟠 Agresif':<20} Çok hızlı/stabil sistemler")
print(f"{'1.05x':<15} {'%5 fazla':<20} {'🔴 Çok Riskli':<20} Test/debug amaçlı")

# Öneriler
print("\n\n" + "=" * 100)
print("ÖNERİLER")
print("=" * 100)

print("\n✅ AVANTAJLAR (0.1s başlangıç + 1.1x çarpan):")
print("   • Çok daha hızlı sistem (297s tasarruf)")
print("   • İlk ölçümlerde agresif yaklaşım")
print("   • Hızlı sistemler için ideal")
print("   • Minimum bekleme süresi")

print("\n⚠️  DEZAVANTAJLAR:")
print("   • Yüksek hata riski (özellikle ilk çalıştırmalarda)")
print("   • Sistem yavaşladığında başarısızlık oranı artar")
print("   • Ağ gecikmesi/yük durumlarında sorun")
print("   • Sadece %10 tolerans")

print("\n💡 ÖNERILEN YAKLIŞIM:")
print("   1. İlk kez kullanım: 3.0s başlangıç + 1.3x çarpan (güvenli)")
print("   2. Sistem stabil çalışıyorsa: 1.0s başlangıç + 1.2x çarpan (dengeli)")
print("   3. Çok hızlı sistemler için: 0.5s başlangıç + 1.1x çarpan (agresif)")
print("   4. SADECE test/debug: 0.1s başlangıç + 1.1x çarpan (çok riskli)")

print("\n🎯 SİSTEMİNİZ İÇİN ÖNERİ:")
# Ortalama süreleri analiz et
avg_all = sum(d['total_time'] / d['count'] for d in stats.values()) / len(stats)
print(f"   Genel Ortalama İşlem Süresi: {avg_all:.3f}s")

if avg_all > 2.0:
    print("   → Sisteminiz yavaş, 1.0s + 1.3x önerilir (güvenli)")
elif avg_all > 1.0:
    print("   → Sisteminiz orta hızda, 0.5s + 1.2x önerilir (dengeli)")
else:
    print("   → Sisteminiz hızlı, 0.1s + 1.1x denenebilir (agresif)")

print("\n" + "=" * 100)
