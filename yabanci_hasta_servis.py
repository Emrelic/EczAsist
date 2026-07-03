# -*- coding: utf-8 -*-
"""Yabancı Uyruklu Hasta Uyarı Servisi — bağımsız arka plan uygulaması.

EczAsist (etiket) programından TAMAMEN bağımsız çalışır. Bilgisayar açıkken
sistem tepsisinde (tray) küçük bir ikon olarak arka planda durur; Botanik EOS'a
60 sn'de bir SELECT yoklaması yapar. Yeni kaydedilen bir reçetenin hasta TC'si
'98'/'99' ile başlıyor (yabancı uyruklu) AMA geçici koruma kapsamında DEĞİLSE
(yani A/B/C gibi normal SGK gruplarına düşüyorsa), ekranı kaplayan kırmızı bir
"Topkapı SGK'dan kağıt getirildi mi?" uyarısı verir + sesli alarm.

🚨 Botanik EOS'a yalnızca SELECT yapar (BotanikDB güvenlik filtresi). Asla yazmaz.

Kendini kurar:
  • Ağdaki merkez klasörden çalıştırılınca kendini yerel klasöre (C:\\BotanikTakip)
    kopyalar ve Windows Başlangıç klasörüne kısayol ekler → her açılışta otomatik.
  • Tüm Python bağımlılıkları PyInstaller ile exe'ye gömülüdür; kullanıcının
    ayrıca bir şey kurmasına gerek yoktur (tek gereksinim: makinedeki SQL Server
    ODBC sürücüsü — Botanik kurulu makinelerde zaten vardır; yoksa uyarır).

Kullanım (geliştirme):  python yabanci_hasta_servis.py
Derleme:                build_servis.bat  (PyInstaller onefile, --noconsole)
"""

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

import yabanci_hasta_tespit as yht

# ── Sabitler ────────────────────────────────────────────────────────────
UYGULAMA_ADI = "BotanikYabanciUyari"
YEREL_KLASOR = r"C:\BotanikTakip"
EXE_ADI = "YabanciHastaUyari.exe"
POLL_SANIYE = 60

logger = logging.getLogger("yabanci_servis")


def _uygulama_dizini() -> str:
    """Çalışan exe'nin (frozen) ya da .py'nin bulunduğu dizin."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _exe_yolu() -> str:
    """Çalışan exe'nin tam yolu (frozen değilse python betiği)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)


def _log_kur():
    try:
        os.makedirs(YEREL_KLASOR, exist_ok=True)
        log_yolu = os.path.join(YEREL_KLASOR, "yabanci_servis.log")
    except Exception:
        log_yolu = os.path.join(_uygulama_dizini(), "yabanci_servis.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_yolu, encoding="utf-8")],
    )


# ── Tek örnek (single instance) kilidi ──────────────────────────────────
def _tek_ornek_kilidi() -> bool:
    """Aynı anda yalnızca bir kopya çalışsın (named mutex). True=ilk kopya."""
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Global\\BotanikYabanciUyariServis")
        ERROR_ALREADY_EXISTS = 183
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return False
        _tek_ornek_kilidi._mutex = mutex  # GC'den koru
    except Exception:
        pass
    return True


# ── Ayar (uyarı aç/kapa) — yerel JSON ───────────────────────────────────
def _ayar_yolu() -> str:
    return os.path.join(_uygulama_dizini(), "servis_ayar.json")


def uyari_aktif_mi() -> bool:
    try:
        with open(_ayar_yolu(), "r", encoding="utf-8") as f:
            return bool(json.load(f).get("aktif", True))
    except Exception:
        return True


def uyari_aktif_ayarla(aktif: bool):
    try:
        with open(_ayar_yolu(), "w", encoding="utf-8") as f:
            json.dump({"aktif": bool(aktif)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Ayar kaydedilemedi: %s", e)


# ── Kurulum (kendini yerele kopyala + Başlangıç kısayolu) ────────────────
def _baslangic_klasoru() -> str:
    return os.path.join(os.environ.get("APPDATA", ""),
                        r"Microsoft\Windows\Start Menu\Programs\Startup")


def _kisayol_yolu() -> str:
    return os.path.join(_baslangic_klasoru(), f"{UYGULAMA_ADI}.lnk")


def kurulu_mu() -> bool:
    """Yerel klasördeki exe Başlangıç'a eklenmiş mi?"""
    return os.path.exists(_kisayol_yolu()) and os.path.exists(
        os.path.join(YEREL_KLASOR, EXE_ADI))


def _baslangic_kisayolu_olustur(hedef_exe: str) -> bool:
    """shell:startup içine PowerShell + WScript.Shell ile .lnk oluştur."""
    try:
        ps = (
            "$s=(New-Object -ComObject WScript.Shell)."
            f"CreateShortcut('{_kisayol_yolu()}');"
            f"$s.TargetPath='{hedef_exe}';"
            f"$s.WorkingDirectory='{os.path.dirname(hedef_exe)}';"
            "$s.WindowStyle=7;"
            "$s.Description='Botanik Yabancı Uyruklu Hasta Uyarı Servisi';"
            "$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            check=True, creationflags=0x08000000)  # CREATE_NO_WINDOW
        return True
    except Exception as e:
        logger.error("Kısayol oluşturulamadı: %s", e)
        return False


def kurulumu_yap(sessiz: bool = False) -> bool:
    """Exe'yi yerel klasöre kopyala + Başlangıç kısayolu ekle.

    Ağdaki merkez klasörden çalıştırılınca her makineye yerel kurulum yapar
    (açılışta otomatik başlama ağ bağlantısına bağlı kalmasın diye)."""
    try:
        os.makedirs(YEREL_KLASOR, exist_ok=True)
        kaynak = _exe_yolu()
        hedef = os.path.join(YEREL_KLASOR, EXE_ADI)
        if os.path.abspath(kaynak).lower() != os.path.abspath(hedef).lower():
            shutil.copy2(kaynak, hedef)
            # db_config.json varsa onu da yanına kopyala (opsiyonel override)
            yan_cfg = os.path.join(os.path.dirname(kaynak), "db_config.json")
            if os.path.exists(yan_cfg):
                try:
                    shutil.copy2(yan_cfg, os.path.join(YEREL_KLASOR,
                                                       "db_config.json"))
                except Exception:
                    pass
        ok = _baslangic_kisayolu_olustur(hedef)
        if ok and not sessiz:
            messagebox.showinfo(
                "Kurulum Tamamlandı",
                f"Servis '{YEREL_KLASOR}' klasörüne kuruldu ve Windows "
                "açılışında otomatik başlayacak şekilde ayarlandı.\n\n"
                "Artık arka planda çalışıyor; sistem tepsisindeki 🌍 ikonundan "
                "yönetebilirsiniz.")
        return ok
    except Exception as e:
        logger.error("Kurulum hatası: %s", e)
        if not sessiz:
            messagebox.showerror("Kurulum Hatası",
                                 f"Kurulum yapılamadı:\n{e}")
        return False


def kurulumu_kaldir():
    """Başlangıç kısayolunu sil (yerel exe kalır)."""
    try:
        if os.path.exists(_kisayol_yolu()):
            os.remove(_kisayol_yolu())
        return True
    except Exception as e:
        logger.error("Kaldırma hatası: %s", e)
        return False


# ── Veritabanı (BotanikDB — yalnız SELECT) ───────────────────────────────
def _db_olustur():
    """BotanikDB örneği. Exe yanında db_config.json varsa onu kullanır,
    yoksa BotanikDB'nin kendi (production) fallback ayarını kullanır."""
    from botanik_db import BotanikDB
    cfg = None
    yan_cfg = os.path.join(_uygulama_dizini(), "db_config.json")
    if os.path.exists(yan_cfg):
        try:
            with open(yan_cfg, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if veri.get("kurulum_tamamlandi"):
                cfg = veri
        except Exception:
            pass
    return BotanikDB(config=cfg) if cfg else BotanikDB()


# ── Çekirdek servis ──────────────────────────────────────────────────────
class YabanciHastaServis:
    def __init__(self):
        self.db = None
        self.son_rxid = None
        self.stop = threading.Event()
        self.root = None
        self.tray = None

    # — DB —
    def _baglan(self) -> bool:
        try:
            self.db = _db_olustur()
            if self.db.baglan():
                logger.info("Botanik EOS bağlandı (salt-okuma).")
                return True
        except Exception as e:
            logger.error("DB bağlantı hatası: %s", e)
        return False

    def _max_rxid(self):
        try:
            rows = self.db.sorgu_calistir(
                "SELECT MAX(RxId) AS m FROM ReceteAna WHERE RxSilme = 0")
            if rows and rows[0].get("m") is not None:
                return int(rows[0]["m"])
        except Exception as e:
            logger.warning("MAX(RxId) alınamadı: %s", e)
        return None

    def _yeni_yabancilar(self, son_rxid: int) -> list:
        """RxId > son_rxid olan, TC 98/99 + geçici koruma DEĞİL reçeteler."""
        sql = """
            SELECT ra.RxId               AS RxId,
                   ra.RxEReceteNo        AS ReceteNo,
                   m.MusteriTCKN         AS TC,
                   m.MusteriAdiSoyadi    AS Hasta,
                   k.KapsamAdi           AS Kapsam
            FROM ReceteAna ra
            LEFT JOIN Musteri m ON ra.RxMusteriId = m.MusteriId
            LEFT JOIN Kapsam  k ON m.MusteriKapsamId = k.KapsamId
            WHERE ra.RxSilme = 0
              AND ra.RxId > ?
              AND (m.MusteriTCKN LIKE '98%' OR m.MusteriTCKN LIKE '99%')
            ORDER BY ra.RxId
        """
        try:
            rows = self.db.sorgu_calistir(sql, (int(son_rxid),))
        except Exception as e:
            logger.warning("Yeni reçete sorgusu hatası: %s", e)
            return []
        sonuc = []
        for r in rows or []:
            tc = (r.get("TC") or "").strip()
            kapsam = (r.get("Kapsam") or "").strip()
            if yht.topkapi_kagit_uyarisi_gerekir_mi(tc, kapsam):
                sonuc.append({
                    "hasta": r.get("Hasta") or "",
                    "tc": tc,
                    "rec_no": r.get("ReceteNo") or "",
                    "kapsam": kapsam,
                })
        return sonuc

    # — Yoklama döngüsü —
    def _poll_dongu(self):
        # Bağlanana kadar dene (DB/ağ hazır olmayabilir)
        while not self.stop.is_set() and not self._baglan():
            self.stop.wait(30)
        if self.stop.is_set():
            return
        self.son_rxid = self._max_rxid()  # geçmişi alarmlamadan başla
        logger.info("Servis başladı, baz RxId=%s", self.son_rxid)
        while not self.stop.is_set():
            if self.stop.wait(POLL_SANIYE):
                break
            try:
                yeni_max = self._max_rxid()
                if yeni_max is None:
                    # Bağlantı koptu olabilir → yeniden bağlan
                    self._baglan()
                    continue
                if self.son_rxid is None:
                    self.son_rxid = yeni_max
                    continue
                if yeni_max > self.son_rxid:
                    yabancilar = self._yeni_yabancilar(self.son_rxid)
                    self.son_rxid = yeni_max
                    if yabancilar and uyari_aktif_mi():
                        self.root.after(0, self._uyari_goster, yabancilar)
            except Exception as e:
                logger.warning("Poll döngü hatası: %s", e)

    # — Tam ekran uyarı —
    def _uyari_goster(self, yabancilar: list):
        if not yabancilar:
            return
        try:
            import winsound
            for _ in range(3):
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass

        pop = tk.Toplevel(self.root)
        pop.title("⚠️ DİKKAT — YABANCI UYRUKLU HASTA")
        pop.configure(bg="#B71C1C")
        try:
            pop.attributes("-fullscreen", True)
        except Exception:
            try:
                pop.state("zoomed")
            except Exception:
                pop.geometry("1100x800")
        try:
            pop.attributes("-topmost", True)
        except Exception:
            pass

        ic = tk.Frame(pop, bg="#B71C1C")
        ic.pack(fill="both", expand=True, padx=40, pady=30)
        tk.Label(ic, text="⚠️  DİKKAT  DİKKAT  ⚠️", bg="#B71C1C", fg="#FFEB3B",
                 font=("Segoe UI", 48, "bold")).pack(pady=(10, 4))
        tk.Label(ic, text="YABANCI SGK'LI HASTA REÇETESİ", bg="#B71C1C",
                 fg="white", font=("Segoe UI", 34, "bold")).pack(pady=4)
        tk.Label(ic, text="TOPKAPI SGK'DAN KAĞIT GETİRİLDİ Mİ?", bg="white",
                 fg="#B71C1C", font=("Segoe UI", 30, "bold"),
                 padx=24, pady=12).pack(pady=18)
        tk.Label(ic,
                 text="Yabancı uyruklu (98/99 ile başlayan TC) SGK'lı hastalar,\n"
                      "reçeteleri için TOPKAPI SGK'dan kağıt getirmelidir.",
                 bg="#B71C1C", fg="white", justify="center",
                 font=("Segoe UI", 18)).pack(pady=(0, 16))

        liste = tk.Frame(ic, bg="#FFF3E0")
        liste.pack(fill="x", padx=60, pady=10)
        tk.Label(liste, text=f"{len(yabancilar)} reçete:", bg="#FFF3E0",
                 fg="#B71C1C", font=("Segoe UI", 14, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(8, 2))
        for y in yabancilar[:12]:
            satir = (f"   •  {y.get('hasta','')}   (TC: {y.get('tc','')})"
                     f"   —  Reçete {y.get('rec_no','')}")
            if (y.get("kapsam") or "").strip():
                satir += f"   [{y['kapsam']}]"
            tk.Label(liste, text=satir, bg="#FFF3E0", fg="#3E2723",
                     font=("Segoe UI", 13), anchor="w").pack(fill="x", padx=14)
        if len(yabancilar) > 12:
            tk.Label(liste, text=f"   … ve {len(yabancilar) - 12} reçete daha",
                     bg="#FFF3E0", fg="#3E2723",
                     font=("Segoe UI", 12, "italic"), anchor="w").pack(
                         fill="x", padx=14, pady=(0, 8))
        else:
            tk.Label(liste, text="", bg="#FFF3E0").pack(pady=2)

        tk.Button(ic, text="✔  ANLADIM  (Esc)", command=pop.destroy,
                  bg="#1B5E20", fg="white", font=("Segoe UI", 20, "bold"),
                  padx=40, pady=14, cursor="hand2").pack(pady=26)
        pop.bind("<Escape>", lambda _e: pop.destroy())
        try:
            pop.grab_set()
        except Exception:
            pass
        pop.focus_force()
        pop.lift()

    # — Sistem tepsisi (tray) —
    def _tray_ikon_resmi(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, 60, 60), fill=(183, 28, 28, 255))  # kırmızı daire
        d.ellipse((4, 4, 60, 60), outline=(255, 255, 255, 255), width=3)
        d.text((20, 20), "🌍", fill=(255, 255, 255, 255))
        return img

    def _tray_baslat(self):
        try:
            import pystray
            from pystray import MenuItem as Item
        except Exception as e:
            logger.warning("pystray yok, tray başlatılamadı: %s", e)
            return

        def _durum(_i, _it):
            messagebox.showinfo(
                "Yabancı Uyruklu Hasta Uyarı Servisi",
                f"Durum: ÇALIŞIYOR\n"
                f"Uyarı: {'AÇIK' if uyari_aktif_mi() else 'KAPALI'}\n"
                f"Son RxId: {self.son_rxid}\n"
                f"Yoklama: {POLL_SANIYE} sn\n"
                f"Kurulu: {'EVET' if kurulu_mu() else 'HAYIR'}")

        def _uyari_toggle(_i, _it):
            uyari_aktif_ayarla(not uyari_aktif_mi())
            self.tray.update_menu()

        def _test(_i, _it):
            self.root.after(0, self._uyari_goster, [{
                "hasta": "TEST HASTA", "tc": "99999999999",
                "rec_no": "TEST", "kapsam": "SGK"}])

        def _kur(_i, _it):
            self.root.after(0, lambda: kurulumu_yap(sessiz=False))

        def _cik(_i, _it):
            self.stop.set()
            try:
                self.tray.stop()
            except Exception:
                pass
            self.root.after(0, self.root.quit)

        menu = pystray.Menu(
            Item(lambda _it: f"Uyarı: {'AÇIK' if uyari_aktif_mi() else 'KAPALI'}",
                 _uyari_toggle),
            Item("Durum / Bilgi", _durum),
            Item("Test uyarısı göster", _test),
            Item("Açılışa kur / yenile", _kur),
            Item("Çıkış", _cik),
        )
        self.tray = pystray.Icon(
            UYGULAMA_ADI, self._tray_ikon_resmi(),
            "Yabancı Uyruklu Hasta Uyarı Servisi", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    # — Çalıştır —
    def calistir(self):
        self.root = tk.Tk()
        self.root.withdraw()  # gizli ana pencere (tray uygulaması)
        self._tray_baslat()
        threading.Thread(target=self._poll_dongu, daemon=True).start()
        self.root.mainloop()


def main():
    _log_kur()
    if not _tek_ornek_kilidi():
        logger.info("Zaten çalışıyor; ikinci kopya kapanıyor.")
        return

    # Açılışa kurulu değilse ve ağdan/yerel-dışı çalıştırıldıysa kurulum öner.
    if not kurulu_mu():
        try:
            _k = tk.Tk()
            _k.withdraw()
            cevap = messagebox.askyesno(
                "Yabancı Uyruklu Hasta Uyarı Servisi",
                "Bu servis arka planda çalışarak, 98/99 ile başlayan TC'li "
                "(yabancı uyruklu) ama geçici koruma kapsamında OLMAYAN "
                "reçeteler için 'Topkapı SGK kağıdı' uyarısı verir.\n\n"
                "Bu bilgisayara kurulsun mu? (Windows açılışında otomatik "
                "başlayacak şekilde yerel klasöre kopyalanır.)")
            _k.destroy()
            if cevap:
                kurulumu_yap(sessiz=False)
        except Exception as e:
            logger.warning("Kurulum önerisi gösterilemedi: %s", e)

    YabanciHastaServis().calistir()


if __name__ == "__main__":
    main()
