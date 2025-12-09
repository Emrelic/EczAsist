"""
Kod içindeki beklemeleri analiz eder ve gereksiz beklemeleri tespit eder
"""

import re
import json

# İstatistikleri oku
with open('timing_stats.json', 'r', encoding='utf-8') as f:
    stats = json.load(f)

# botanik_bot.py'yi oku
with open('botanik_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# timed_sleep çağrılarını bul
pattern = r'self\.timed_sleep\("([^"]+)"(?:,\s*([^)]+))?\)'

waits = []
for line_num, line in enumerate(lines, 1):
    matches = re.finditer(pattern, line)
    for match in matches:
        key = match.group(1)
        default = match.group(2)
        waits.append({
            'line': line_num,
            'key': key,
            'default': default,
            'code': line.strip()
        })

print("=" * 100)
print("BEKLEME NOKTALARI ANALİZİ")
print("=" * 100)

# İstatistiklere göre grupla
has_stats = []
no_stats = []

for wait in waits:
    if wait['key'] in stats:
        wait['stats'] = stats[wait['key']]
        wait['avg'] = stats[wait['key']]['total_time'] / stats[wait['key']]['count']
        has_stats.append(wait)
    else:
        no_stats.append(wait)

# İstatistikli beklemeler
print(f"\n1. İSTATİSTİKLİ BEKLEMELER ({len(has_stats)} adet):")
print("-" * 100)
print(f"{'Satır':<8} {'Anahtar':<30} {'Ortalama':<12} {'Sayı':<8}")
print("-" * 100)
for wait in sorted(has_stats, key=lambda x: x['avg'], reverse=True):
    print(f"{wait['line']:<8} {wait['key']:<30} {wait['avg']:>10.3f}s  {wait['stats']['count']:<8}")

# İstatistiksiz beklemeler (henüz ölçülmemiş)
print(f"\n2. HİÇ ÖLÇÜLMEMİŞ BEKLEMELER ({len(no_stats)} adet):")
print("-" * 100)
print(f"{'Satır':<8} {'Anahtar':<30} {'Kod':<60}")
print("-" * 100)
for wait in no_stats:
    print(f"{wait['line']:<8} {wait['key']:<30} {wait['code'][:60]}")

# Tekrar eden beklemeler
print(f"\n3. TEKRAR EDEN BEKLEMELER:")
print("-" * 100)
key_counts = {}
for wait in waits:
    key = wait['key']
    key_counts[key] = key_counts.get(key, 0) + 1

duplicates = {k: v for k, v in key_counts.items() if v > 1}
for key, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
    if key in stats:
        avg = stats[key]['total_time'] / stats[key]['count']
        print(f"{key:<30} {count:>3}x kullanım  (Ort: {avg:.3f}s)")
    else:
        print(f"{key:<30} {count:>3}x kullanım  (Ölçülmemiş)")

print("\n" + "=" * 100)
print("ANALİZ ÖNERİLERİ:")
print("=" * 100)

# Çok yavaş işlemler
slow_ops = [w for w in has_stats if w['avg'] > 3.0]
if slow_ops:
    print(f"\n⚠️  3 saniyeden uzun beklemeler ({len(slow_ops)} adet):")
    for w in sorted(slow_ops, key=lambda x: x['avg'], reverse=True):
        print(f"   Satır {w['line']}: {w['key']} - {w['avg']:.2f}s (optimize edilebilir mi?)")

# Çok hızlı işlemler (<0.1s)
fast_ops = [w for w in has_stats if w['avg'] < 0.1]
if fast_ops:
    print(f"\n⚡ 0.1 saniyeden kısa beklemeler ({len(fast_ops)} adet):")
    for w in sorted(fast_ops, key=lambda x: x['avg']):
        print(f"   Satır {w['line']}: {w['key']} - {w['avg']:.3f}s (gereksiz olabilir)")

print("\n" + "=" * 100)
