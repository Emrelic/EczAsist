"""
Eczasist masaüstü kısayolu oluşturur.

Çalıştırmak için:
    python kisayol_olustur.py

Windows'ta pywin32 varsa gerçek .lnk dosyası üretir.
Yoksa .bat alternatifi oluşturulur ve masaüstüne kopyalanır.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(SCRIPT_DIR, "main.py")
ICON_PATH = os.path.join(SCRIPT_DIR, "assets", "eczasist.ico")
PROGRAM_ADI = "Eczasist"


def masaustu_yolu() -> str:
    """Windows'ta kullanıcının masaüstü klasörü."""
    profil = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    masaustu = os.path.join(profil, "Desktop")
    if os.path.isdir(masaustu):
        return masaustu
    # OneDrive masaüstü (bazı Win10/11 kullanıcılarında)
    one = os.path.join(profil, "OneDrive", "Desktop")
    if os.path.isdir(one):
        return one
    return masaustu  # en azından isim dön


def pyw_bul() -> str:
    """pythonw.exe yolunu bul (konsol penceresi olmadan açılsın diye)."""
    pyw = sys.executable
    if pyw.lower().endswith("python.exe"):
        alt = pyw[:-10] + "pythonw.exe"
        if os.path.exists(alt):
            return alt
    return pyw


def lnk_olustur(hedef: str) -> bool:
    """Windows .lnk kısayolu — pywin32 gerekir."""
    try:
        from win32com.client import Dispatch
    except ImportError:
        logger.warning("pywin32 yok — .lnk oluşturulamıyor, .bat kullanılacak.")
        return False

    shell = Dispatch("WScript.Shell")
    kisayol = shell.CreateShortcut(hedef)
    kisayol.TargetPath = pyw_bul()
    kisayol.Arguments = f'"{MAIN_PY}"'
    kisayol.WorkingDirectory = SCRIPT_DIR
    kisayol.IconLocation = ICON_PATH
    kisayol.Description = "Eczasist - Eczane Takip Sistemi"
    kisayol.Save()
    logger.info(f"Kısayol oluşturuldu: {hedef}")
    return True


def bat_olustur(hedef: str) -> None:
    """.bat fallback — ikon doğrudan gömülemez."""
    icerik = (
        f'@echo off\r\n'
        f'cd /d "{SCRIPT_DIR}"\r\n'
        f'start "" "{pyw_bul()}" "{MAIN_PY}"\r\n'
    )
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(icerik)
    logger.info(f".bat kısayolu oluşturuldu: {hedef}")
    logger.info("Not: .bat dosyasına ikon gömülmez. Sağ tık → Özellikler → İkon Değiştir ile manuel set edilebilir.")


def main():
    if not os.path.exists(MAIN_PY):
        logger.error(f"main.py bulunamadı: {MAIN_PY}")
        sys.exit(1)
    if not os.path.exists(ICON_PATH):
        logger.warning(f"İkon bulunamadı: {ICON_PATH}")
        logger.warning("Önce: python assets/ikon_olustur.py")

    masaustu = masaustu_yolu()
    lnk_hedef = os.path.join(masaustu, f"{PROGRAM_ADI}.lnk")
    bat_hedef = os.path.join(masaustu, f"{PROGRAM_ADI}.bat")

    # Önce .lnk dene
    if lnk_olustur(lnk_hedef):
        # Varsa eski .bat kalıntısını temizle
        if os.path.exists(bat_hedef):
            try:
                os.remove(bat_hedef)
            except OSError:
                pass
        print(f"\n[OK] Masaustunde '{PROGRAM_ADI}.lnk' kisayolu olusturuldu.")
        print(f"     Konum: {lnk_hedef}")
    else:
        bat_olustur(bat_hedef)
        print(f"\n[UYARI] pywin32 olmadigi icin .bat olusturuldu: {bat_hedef}")
        print("        Ikonlu .lnk icin: pip install pywin32  ve bu scripti tekrar calistirin.")


if __name__ == "__main__":
    main()
