"""
Timing Optimizasyon Aracı
İstatistiklere göre optimal timing değerlerini hesaplar ve uygular
"""

import json
import sys
import io

# UTF-8 çıktı için
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# İstatistikleri oku
with open('timing_stats.json', 'r', encoding='utf-8') as f:
    stats = json.load(f)

# Optimal değerleri hesapla (%30 fazla)
MULTIPLIER = 1.3

optimal_values = {}
for key, data in stats.items():
    count = data['count']
    total_time = data['total_time']

    if count > 0:
        average = total_time / count
        optimal = round(average * MULTIPLIER, 3)
        optimal_values[key] = {
            'average': round(average, 3),
            'optimal': optimal,
            'count': count
        }

# Rapor yazdır
print("=" * 80)
print("TİMİNG OPTİMİZASYON RAPORU")
print("=" * 80)
print(f"\nÇarpan: {MULTIPLIER}x (%{int((MULTIPLIER-1)*100)} fazla güvenlik marjı)\n")

print(f"{'İşlem':<30} {'Gerçek Ort.':<15} {'Optimal':<15} {'Ölçüm':<10}")
print("-" * 80)

for key, values in sorted(optimal_values.items(), key=lambda x: x[1]['average'], reverse=True):
    print(f"{key:<30} {values['average']:<15.3f} {values['optimal']:<15.3f} {values['count']:<10}")

print("\n" + "=" * 80)

# Mevcut ayarları oku
with open('timing_settings.json', 'r', encoding='utf-8') as f:
    current_settings = json.load(f)

# Güncellemeleri uygula
updated_settings = current_settings.copy()
changes = []

for key, values in optimal_values.items():
    old_value = current_settings.get(key, 3.0)
    new_value = values['optimal']

    if abs(old_value - new_value) > 0.1:  # 0.1 saniyeden fazla fark varsa
        updated_settings[key] = new_value
        diff = new_value - old_value
        changes.append({
            'key': key,
            'old': old_value,
            'new': new_value,
            'diff': diff
        })

# Değişiklikleri göster
print("\nUYGULANACAK DEĞİŞİKLİKLER:")
print("-" * 80)
print(f"{'İşlem':<30} {'Eski':<10} {'Yeni':<10} {'Fark':<10}")
print("-" * 80)

for change in sorted(changes, key=lambda x: abs(x['diff']), reverse=True):
    symbol = "🔴" if change['diff'] < -1 else "🟢" if change['diff'] < 0 else "⚠️"
    print(f"{symbol} {change['key']:<28} {change['old']:<10.3f} {change['new']:<10.3f} {change['diff']:>+9.3f}s")

# Toplam kazanç hesapla
total_saving = sum(change['diff'] * optimal_values[change['key']]['count'] for change in changes if change['diff'] < 0)
total_loss = sum(change['diff'] * optimal_values[change['key']]['count'] for change in changes if change['diff'] > 0)

print("\n" + "=" * 80)
print(f"Toplam Zaman Tasarrufu (ölçülen işlemler için): {abs(total_saving):.1f} saniye")
print(f"Toplam Zaman Artışı (güvenlik için): {abs(total_loss):.1f} saniye")
print(f"Net Kazanç: {abs(total_saving) - abs(total_loss):.1f} saniye")
print("=" * 80)

# Kaydet
with open('timing_settings.json', 'w', encoding='utf-8') as f:
    json.dump(updated_settings, f, indent=2, ensure_ascii=False)

print("\n✅ Ayarlar timing_settings.json dosyasına kaydedildi!")
