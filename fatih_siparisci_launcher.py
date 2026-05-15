"""
Fatih Siparişçi Launcher
========================
Masaüstündeki kurulu "Botanik Sipariş Yardımcısı" (Siparisci) uygulamasını
ayrı bir process olarak başlatır. EczAsist tarafında hiçbir bağımlılık
oluşturmaz — Fatih kendi sanal ortamında çalışır.

Kurulu değilse: hata kutusu + "Kurulum dosyasını aç" butonu (Explorer'da
SiparisciKurulum.exe konumunu seçili getirir).
"""

import os
import subprocess
import logging
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

logger = logging.getLogger(__name__)

# Sabit kurulum yolu (Inno Setup default: AppData/Local/Siparisci)
SIPARISCI_KURULU_DIZIN = Path(os.environ.get("LOCALAPPDATA", "")) / "Siparisci"
SIPARISCI_ENTRY = SIPARISCI_KURULU_DIZIN / "Siparisci.pyw"

# Kurulum dosyası arama listesi (kullanıcı SiparisciKurulum.exe'yi
# masaüstünde, OneDrive masaüstünde veya İndirilenler'de tutuyor olabilir)
KURULUM_ARAMA_YERLERI = [
    Path.home() / "Desktop" / "SiparisciKurulum.exe",
    Path.home() / "OneDrive" / "Desktop" / "SiparisciKurulum.exe",
    Path.home() / "Downloads" / "SiparisciKurulum.exe",
    Path.home() / "İndirilenler" / "SiparisciKurulum.exe",
]


def _pythonw_yolu_bul() -> str:
    """
    Fatih Siparişçi'nin kurulu olduğu pythonw.exe'yi bulmaya çalış.

    Sırayla:
    1) Kurulum dizinindeki .python_path dosyası (Inno Setup yazdıysa)
    2) AppData/Local/Programs/Python/Python3*/pythonw.exe
    3) Sistem PATH'inde pythonw
    """
    # 1) Inno Setup'ın kaydettiği path dosyası
    path_dosyasi = SIPARISCI_KURULU_DIZIN / ".python_path"
    if path_dosyasi.exists():
        try:
            kaydedilen = path_dosyasi.read_text(encoding="utf-8").strip()
            if kaydedilen and Path(kaydedilen).exists():
                return kaydedilen
        except Exception:
            pass

    # 2) AppData Programs altında Python kurulumu ara
    programs_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    if programs_dir.exists():
        for py_dir in sorted(programs_dir.iterdir(), reverse=True):
            cand = py_dir / "pythonw.exe"
            if cand.exists():
                return str(cand)

    # 3) Fallback: PATH'teki pythonw
    return "pythonw"


def _kurulum_dosyasi_bul() -> Path | None:
    """Masaüstü/indirilenlerde SiparisciKurulum.exe ara"""
    for yol in KURULUM_ARAMA_YERLERI:
        if yol.exists():
            return yol
    return None


def _explorer_da_goster(yol: Path):
    """Dosya gezgininde verilen dosyayı seçili olarak aç"""
    try:
        subprocess.Popen(["explorer", "/select,", str(yol)])
    except Exception as e:
        logger.error(f"Explorer açma hatası: {e}")


def _kurulum_yok_uyarisi(parent=None):
    """Kurulum yoksa kullanıcıya bilgilendirici pencere göster"""
    kurulum_yolu = _kurulum_dosyasi_bul()

    pencere = tk.Toplevel(parent) if parent else tk.Tk()
    pencere.title("Fatih Siparişçi — Kurulum Bulunamadı")
    pencere.geometry("520x280")
    pencere.resizable(False, False)
    try:
        from eczasist_ikon import ikon_uygula
        ikon_uygula(pencere)
    except Exception:
        pass

    # Mesaj
    msg = tk.Label(
        pencere,
        text="🛒  Fatih Siparişçi (Botanik Sipariş Yardımcısı) kurulu değil.",
        font=("Arial", 11, "bold"),
        pady=20,
    )
    msg.pack()

    detay = tk.Label(
        pencere,
        text=(
            "Beklenen kurulum yolu:\n"
            f"   {SIPARISCI_KURULU_DIZIN}\n\n"
            "Kullanmak için SiparisciKurulum.exe dosyasını çalıştırın.\n"
            "Kurulum tamamlandıktan sonra bu butonu tekrar tıklayın."
        ),
        font=("Arial", 9),
        justify="left",
        pady=10,
    )
    detay.pack()

    btn_frame = tk.Frame(pencere, pady=15)
    btn_frame.pack()

    if kurulum_yolu:
        tk.Button(
            btn_frame,
            text=f"📁 Kurulum dosyasını göster\n({kurulum_yolu.name})",
            command=lambda: (_explorer_da_goster(kurulum_yolu), pencere.destroy()),
            bg="#FF6F00",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=10)
    else:
        konum_txt = "Aranan konumlar:\n" + "\n".join(f"  • {y}" for y in KURULUM_ARAMA_YERLERI)
        tk.Label(
            pencere,
            text=konum_txt,
            font=("Arial", 8),
            fg="#888",
            justify="left",
        ).pack(pady=(0, 8))

    tk.Button(
        btn_frame,
        text="Kapat",
        command=pencere.destroy,
        padx=15,
        pady=8,
    ).pack(side="left", padx=10)

    if not parent:
        pencere.mainloop()


def fatih_siparisci_baslat(parent=None):
    """
    Fatih Siparişçi'yi ayrı bir process olarak başlat.

    Args:
        parent: Üst Tk penceresi (uyarı pencereleri için)

    Returns:
        subprocess.Popen | None: Başlatılan process; başlatılamadıysa None
    """
    if not SIPARISCI_ENTRY.exists():
        logger.warning(f"Fatih Siparişçi bulunamadı: {SIPARISCI_ENTRY}")
        _kurulum_yok_uyarisi(parent)
        return None

    pythonw = _pythonw_yolu_bul()

    try:
        # CREATE_NO_WINDOW + DETACHED_PROCESS: konsol çıkmasın, bağımsız çalışsın
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.DETACHED_PROCESS
            )

        proc = subprocess.Popen(
            [pythonw, str(SIPARISCI_ENTRY)],
            cwd=str(SIPARISCI_KURULU_DIZIN),
            creationflags=creationflags,
            close_fds=True,
        )
        logger.info(f"Fatih Siparişçi başlatıldı: {pythonw} {SIPARISCI_ENTRY}")
        return proc

    except Exception as e:
        logger.error(f"Fatih Siparişçi başlatma hatası: {e}")
        messagebox.showerror(
            "Fatih Siparişçi — Başlatma Hatası",
            f"Program başlatılamadı:\n\n{e}\n\n"
            f"Beklenen yol: {SIPARISCI_ENTRY}\n"
            f"Python: {pythonw}",
            parent=parent,
        )
        return None


if __name__ == "__main__":
    # Standalone test
    logging.basicConfig(level=logging.INFO)
    fatih_siparisci_baslat()
