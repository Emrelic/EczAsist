"""
Açık pencereleri listeler - Medulla penceresini bulmak için
"""

from pywinauto import Desktop

print("=" * 60)
print("AÇIK PENCERELER:")
print("=" * 60)

# Tüm açık pencereleri listele
windows = Desktop(backend="uia").windows()

for i, window in enumerate(windows, 1):
    try:
        title = window.window_text()
        class_name = window.class_name()

        if title:  # Sadece başlığı olanları göster
            print(f"\n{i}. Pencere:")
            print(f"   Başlık: {title}")
            print(f"   Class:  {class_name}")

            # MEDULLA içeren pencereleri vurgula
            if "MEDULLA" in title.upper():
                print("   >>> MEDULLA BULUNDU! <<<")

    except Exception as e:
        pass

print("\n" + "=" * 60)
print("Listele tamamlandı")
print("=" * 60)

input("\nDevam etmek için Enter'a basın...")
