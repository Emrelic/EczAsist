"""
time.sleep(self.timing.get(...)) çağrılarını self.timed_sleep(...)'e dönüştürür
"""

import re

# Dosyayı oku
with open('botanik_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern 1: time.sleep(self.timing.get("key"))
pattern1 = r'time\.sleep\(self\.timing\.get\("([^"]+)"\)\)'
replacement1 = r'self.timed_sleep("\1")'

# Pattern 2: time.sleep(self.timing.get("key", default))
pattern2 = r'time\.sleep\(self\.timing\.get\("([^"]+)",\s*([^)]+)\)\)'
replacement2 = r'self.timed_sleep("\1", \2)'

# Değiştir
content_new = re.sub(pattern2, replacement2, content)  # Önce uzun pattern
content_new = re.sub(pattern1, replacement1, content_new)  # Sonra kısa pattern

# Kaç değişiklik yapıldı?
changes1 = len(re.findall(pattern1, content))
changes2 = len(re.findall(pattern2, content))
total = changes1 + changes2

print(f"Toplam {total} değişiklik yapıldı:")
print(f"  - {changes1} adet: time.sleep(self.timing.get('key'))")
print(f"  - {changes2} adet: time.sleep(self.timing.get('key', default))")

# Kaydet
with open('botanik_bot.py', 'w', encoding='utf-8') as f:
    f.write(content_new)

print("\n✅ botanik_bot.py güncellendi!")
