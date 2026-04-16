"""
Botanik Siparis Yardimcisi - Kurulum Scripti
Tum gereklilikleri otomatik kurar.
"""
import subprocess
import sys
import os

def print_banner():
    print("=" * 50)
    print("  Botanik Siparis Yardimcisi - Kurulum")
    print("=" * 50)
    print()

def check_python_version():
    print("[1/4] Python surumu kontrol ediliyor...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"  HATA: Python 3.8+ gerekli. Mevcut: {version.major}.{version.minor}")
        return False
    print(f"  OK: Python {version.major}.{version.minor}.{version.micro}")
    return True

def install_requirements():
    print("\n[2/4] Python paketleri kuruluyor...")
    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")

    if not os.path.exists(req_file):
        print("  HATA: requirements.txt bulunamadi!")
        return False

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"
        ])
        print("  OK: Tum paketler kuruldu")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  HATA: Paket kurulumu basarisiz: {e}")
        return False

def create_directories():
    print("\n[3/4] Klasorler olusturuluyor...")
    base_dir = os.path.dirname(__file__)
    directories = ["data", "logs"]

    for dir_name in directories:
        dir_path = os.path.join(base_dir, dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"  Olusturuldu: {dir_name}/")
        else:
            print(f"  Mevcut: {dir_name}/")
    return True

def setup_env_file():
    print("\n[4/4] .env dosyasi kontrol ediliyor...")
    base_dir = os.path.dirname(__file__)
    env_file = os.path.join(base_dir, ".env")
    env_example = os.path.join(base_dir, "Gereksiz", ".env.example")

    if os.path.exists(env_file):
        print("  OK: .env dosyasi mevcut")
        return True

    if os.path.exists(env_example):
        import shutil
        shutil.copy(env_example, env_file)
        print("  Olusturuldu: .env (lutfen icini doldurun!)")
        print("  ONEMLI: .env dosyasini acip kendi bilgilerinizi girin!")
        return True
    else:
        print("  UYARI: .env.example bulunamadi")
        print("  Manuel olarak .env dosyasi olusturmaniz gerekiyor")
        return False

def main():
    print_banner()

    steps = [
        ("Python surumu", check_python_version),
        ("Paket kurulumu", install_requirements),
        ("Klasor olusturma", create_directories),
        ("Env dosyasi", setup_env_file),
    ]

    success = True
    for name, func in steps:
        if not func():
            success = False
            break

    print("\n" + "=" * 50)
    if success:
        print("  KURULUM TAMAMLANDI!")
        print("  Programi calistirmak icin: start.bat")
    else:
        print("  KURULUM BASARISIZ!")
        print("  Lutfen hatalari duzeltin ve tekrar deneyin.")
    print("=" * 50)

    input("\nDevam etmek icin Enter'a basin...")

if __name__ == "__main__":
    main()
