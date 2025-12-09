"""
Fonksiyon içindeki gereksiz beklemeleri kaldırır
Sadece ana akışta, retry sonrası bekleme yapılacak
"""

import re

# Dosyayı oku
with open('botanik_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Her fonksiyon içindeki tüm timed_sleep çağrılarını bul
# İlgili fonksiyonlar: ilac_butonuna_tikla, y_butonuna_tikla, geri_don_butonuna_tikla,
# sonra_butonuna_tikla, kapat_butonuna_tikla

fonksiyonlar = [
    'ilac_butonuna_tikla',
    'y_butonuna_tikla',
    'geri_don_butonuna_tikla',
    'sonra_butonuna_tikla',
    'kapat_butonuna_tikla',
    'ilac_ekrani_bekleme_optimized',
]

print("GEREKSİZ BEKLEMELERİ KALDIRMA İŞLEMİ")
print("=" * 80)

for func_name in fonksiyonlar:
    # Fonksiyonu bul
    pattern = rf'(def {func_name}\(.*?\):.*?)(def \w+\(|class \w+:|$)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        func_body = match.group(1)

        # Fonksiyon içindeki timed_sleep çağrılarını say
        timed_sleeps = re.findall(r'self\.timed_sleep\("([^"]+)"\)', func_body)

        if timed_sleeps:
            print(f"\n{func_name}():")
            print(f"  Toplam {len(timed_sleeps)} adet timed_sleep bulundu: {set(timed_sleeps)}")

            # Sadece son return öncesindeki timed_sleep'i koru, diğerlerini kaldır
            # Strateji: Tüm timed_sleep'leri kaldır (çağıran tarafta yapılacak)

            # Timed_sleep satırlarını kaldır
            lines = func_body.split('\n')
            new_lines = []
            removed_count = 0

            for line in lines:
                # Eğer sadece timed_sleep içeren satır ise kaldır
                if re.search(r'^\s*self\.timed_sleep\([^)]+\)\s*$', line):
                    removed_count += 1
                    # Satırı kaldır (ekleme)
                    continue
                else:
                    new_lines.append(line)

            if removed_count > 0:
                print(f"  ✓ {removed_count} satır kaldırıldı")

                # Fonksiyonu güncelle
                new_func_body = '\n'.join(new_lines)
                content = content.replace(func_body, new_func_body)

print("\n" + "=" * 80)
print("NOT: Beklemeler ana akışta (retry_with_popup_check sonrası) yapılacak")
print("=" * 80)

# Kaydet
with open('botanik_bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nbotanik_bot.py güncellendi!")
