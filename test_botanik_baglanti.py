"""
Botanik EOS Bağlantı Test Scripti
UI Automation ve pencere erişim özelliklerini test eder
"""

import ctypes
from ctypes import wintypes
import sys

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_result(test_name, success, detail=""):
    status = "[+] BASARILI" if success else "[-] BASARISIZ"
    print(f"\n{status} {test_name}")
    if detail:
        print(f"    -> {detail}")

def test_1_modul_yukleme():
    """Test 1: Botanik veri çekme modülünün yüklenip yüklenmediğini kontrol et"""
    print_header("TEST 1: Modül Yükleme Kontrolü")

    try:
        from botanik_veri_cek import (
            botanik_verilerini_cek,
            botanik_penceresi_acik_mi,
            botanik_baslangic_kupurlerini_cek,
            _find_baslangic_kasasi_handle
        )
        print_result("botanik_veri_cek modülü", True, "Tüm fonksiyonlar import edildi")
        return True
    except ImportError as e:
        print_result("botanik_veri_cek modülü", False, str(e))
        return False

def test_2_comtypes():
    """Test 2: comtypes modülünün yüklenip yüklenmediğini kontrol et"""
    print_header("TEST 2: comtypes Modülü Kontrolü")

    try:
        import comtypes
        import comtypes.client
        print_result("comtypes modülü", True, f"Versiyon: {comtypes.__version__ if hasattr(comtypes, '__version__') else 'N/A'}")
        return True
    except ImportError as e:
        print_result("comtypes modülü", False, f"Yüklü değil: {e}")
        print("    → Çözüm: pip install comtypes")
        return False

def test_3_uiautomation():
    """Test 3: UI Automation COM interface erişimi"""
    print_header("TEST 3: UI Automation COM Interface")

    try:
        import comtypes.client
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import IUIAutomation

        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=IUIAutomation
        )
        print_result("UI Automation", True, "COM interface başarıyla oluşturuldu")
        return True, uia
    except Exception as e:
        print_result("UI Automation", False, str(e))
        return False, None

def test_4_pencere_arama():
    """Test 4: Açık pencereleri listele ve Botanik pencerelerini ara"""
    print_header("TEST 4: Pencere Arama")

    user32 = ctypes.windll.user32
    pencereler = []
    botanik_pencereler = []
    baslangic_kasasi = None
    kasa_kapatma = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def enum_callback(hwnd, lparam):
        nonlocal baslangic_kasasi, kasa_kapatma
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value

            if user32.IsWindowVisible(hwnd):
                if 'BotanikEOS' in title or 'Botanik' in title:
                    botanik_pencereler.append((hwnd, title))
                # Başlangıç Kasası veya KASA KAPATMA penceresi
                if 'Başlangıç Kasası' in title or 'KASA KAPATMA' in title or 'Kasa Kapatma' in title:
                    baslangic_kasasi = (hwnd, title)
                if title == 'Kasa Kapatma':
                    kasa_kapatma = (hwnd, title)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    print(f"\n  Bulunan Botanik pencereleri: {len(botanik_pencereler)}")
    for hwnd, title in botanik_pencereler:
        try:
            print(f"    - [{hwnd}] {title.encode('ascii', 'replace').decode()}")
        except:
            print(f"    - [{hwnd}] (ozel karakter iceriyor)")

    # Tüm görünür pencereleri listele (debug için)
    print("\n  Tüm görünür pencereler (Botanik ile ilgili olabilecek):")
    def list_all(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if user32.IsWindowVisible(hwnd) and ('Kasa' in title or 'kasa' in title or 'KASA' in title or 'Botanik' in title):
                try:
                    print(f"    - [{hwnd}] '{title.encode('ascii', 'replace').decode()}'")
                except:
                    print(f"    - [{hwnd}] (ozel karakter)")
        return True
    user32.EnumWindows(WNDENUMPROC(list_all), 0)

    if baslangic_kasasi:
        print_result("Başlangıç Kasası penceresi", True, f"Handle: {baslangic_kasasi[0]}, Title: '{baslangic_kasasi[1]}'")
    else:
        print_result("Başlangıç Kasası penceresi", False, "Pencere bulunamadı - Botanik EOS'ta açın")

    if kasa_kapatma:
        print_result("Kasa Kapatma penceresi", True, f"Handle: {kasa_kapatma[0]}")
    else:
        print_result("Kasa Kapatma penceresi", False, "Pencere bulunamadı - Botanik EOS'ta açın")

    return baslangic_kasasi, kasa_kapatma

def test_5_veri_cekme(baslangic_kasasi):
    """Test 5: Başlangıç Kasası'ndan veri çekme"""
    print_header("TEST 5: Başlangıç Kasası Veri Çekme")

    if not baslangic_kasasi:
        print_result("Veri çekme", False, "Başlangıç Kasası penceresi açık değil")
        return False

    try:
        from botanik_veri_cek import botanik_baslangic_kupurlerini_cek

        print("  Veriler çekiliyor...")
        kupurler = botanik_baslangic_kupurlerini_cek()

        if kupurler:
            print_result("Küpür verileri", True, "Veriler başarıyla çekildi")
            print("\n  Çekilen Küpürler:")
            toplam = 0
            for deger in [200, 100, 50, 20, 10, 5, 1, 0.5]:
                adet = kupurler.get(deger, 0)
                tutar = adet * deger
                toplam += tutar
                print(f"    {deger:>5} TL x {adet:>3} adet = {tutar:>10,.2f} TL")
            print(f"    {'─'*35}")
            print(f"    {'TOPLAM':>13} = {toplam:>10,.2f} TL")
            return True
        else:
            print_result("Küpür verileri", False, "Veriler çekilemedi")
            return False

    except Exception as e:
        print_result("Veri çekme", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def test_6_kasa_kapatma_veri(kasa_kapatma):
    """Test 6: Kasa Kapatma penceresinden veri çekme"""
    print_header("TEST 6: Kasa Kapatma Veri Çekme (Nakit/POS/IBAN)")

    if not kasa_kapatma:
        print_result("Veri çekme", False, "Kasa Kapatma penceresi açık değil")
        return False

    try:
        from botanik_veri_cek import botanik_verilerini_cek

        print("  Veriler çekiliyor...")
        veriler = botanik_verilerini_cek()

        if veriler:
            print_result("Kasa Kapatma verileri", True, "Veriler başarıyla çekildi")
            print("\n  Çekilen Veriler:")
            print(f"    Başlangıç Kasası: {veriler.get('baslangic', 0):>12,.2f} TL")
            print(f"    Nakit:            {veriler.get('nakit', 0):>12,.2f} TL")
            print(f"    POS:              {veriler.get('pos', 0):>12,.2f} TL")
            print(f"    IBAN:             {veriler.get('iban', 0):>12,.2f} TL")
            return True
        else:
            print_result("Kasa Kapatma verileri", False, "Veriler çekilemedi")
            return False

    except Exception as e:
        print_result("Veri çekme", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "#"*60)
    print("#" + " "*58 + "#")
    print("#    BOTANIK EOS BAGLANTI TEST ARACI                      #")
    print("#    UI Automation Terminal Ozelligi Testi                #")
    print("#" + " "*58 + "#")
    print("#"*60)

    results = {}

    # Test 1: Modül yükleme
    results['modul'] = test_1_modul_yukleme()

    # Test 2: comtypes
    results['comtypes'] = test_2_comtypes()

    # Test 3: UI Automation
    uia_result, uia = test_3_uiautomation()
    results['uiautomation'] = uia_result

    # Test 4: Pencere arama
    baslangic_kasasi, kasa_kapatma = test_4_pencere_arama()
    results['baslangic_pencere'] = baslangic_kasasi is not None
    results['kasa_kapatma_pencere'] = kasa_kapatma is not None

    # Test 5: Başlangıç Kasası veri çekme
    if baslangic_kasasi:
        results['baslangic_veri'] = test_5_veri_cekme(baslangic_kasasi)
    else:
        print_header("TEST 5: Başlangıç Kasası Veri Çekme")
        print_result("Veri çekme", False, "Pencere açık değil - TEST ATLANDI")
        results['baslangic_veri'] = None

    # Test 6: Kasa Kapatma veri çekme
    if kasa_kapatma:
        results['kasa_kapatma_veri'] = test_6_kasa_kapatma_veri(kasa_kapatma)
    else:
        print_header("TEST 6: Kasa Kapatma Veri Çekme")
        print_result("Veri çekme", False, "Pencere açık değil - TEST ATLANDI")
        results['kasa_kapatma_veri'] = None

    # Özet
    print_header("TEST SONUÇ ÖZETİ")

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\n  [+] Basarili: {passed}")
    print(f"  [-] Basarisiz: {failed}")
    print(f"  [o] Atlanan: {skipped}")

    print("\n  Detayli Sonuclar:")
    test_names = {
        'modul': 'Modul Yukleme',
        'comtypes': 'comtypes Modulu',
        'uiautomation': 'UI Automation',
        'baslangic_pencere': 'Baslangic Kasasi Penceresi',
        'kasa_kapatma_pencere': 'Kasa Kapatma Penceresi',
        'baslangic_veri': 'Baslangic Kasasi Veri',
        'kasa_kapatma_veri': 'Kasa Kapatma Veri'
    }

    for key, name in test_names.items():
        val = results.get(key)
        if val is True:
            status = "[+]"
        elif val is False:
            status = "[-]"
        else:
            status = "[o]"
        print(f"    {status} {name}")

    print("\n" + "="*60)

    if failed == 0 and skipped == 0:
        print("  TUM TESTLER BASARILI! Terminal ozelligi calisiyor.")
    elif failed == 0:
        print("  TEMEL TESTLER BASARILI!")
        print("  Pencere testleri icin Botanik EOS'u acin.")
    else:
        print("  BAZI TESTLER BASARISIZ!")
        print("  Yukaridaki hatalari kontrol edin.")

    print("="*60 + "\n")

    try:
        input("Cikmak icin Enter'a basin...")
    except EOFError:
        pass  # Non-interactive modda calisiyorsa atla

if __name__ == "__main__":
    main()
