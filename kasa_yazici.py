"""
Botanik Bot - Kasa Termal Yazıcı Desteği
80mm Termal yazıcı için optimize edilmiş kasa raporu
ESC/POS komutları ile büyük font desteği
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ESC/POS Komutları (80mm termal yazıcılar için)
ESC = b'\x1b'
GS = b'\x1d'

# Font boyutları
FONT_NORMAL = ESC + b'\x21\x00'          # Normal font
FONT_BOLD = ESC + b'\x21\x08'            # Kalın
FONT_DOUBLE_H = ESC + b'\x21\x10'        # Çift yükseklik
FONT_DOUBLE_W = ESC + b'\x21\x20'        # Çift genişlik
FONT_DOUBLE_WH = ESC + b'\x21\x30'       # Çift genişlik + yükseklik
FONT_LARGE = GS + b'\x21\x11'            # Büyük font (2x2)
FONT_XLARGE = GS + b'\x21\x22'           # Çok büyük (3x3)

# Hizalama
ALIGN_LEFT = ESC + b'\x61\x00'
ALIGN_CENTER = ESC + b'\x61\x01'
ALIGN_RIGHT = ESC + b'\x61\x02'

# Diğer
CUT_PAPER = GS + b'\x56\x00'             # Kağıt kes
LINE_FEED = b'\n'
INIT_PRINTER = ESC + b'\x40'             # Yazıcıyı sıfırla


class KasaYazici:
    """Termal yazıcı işlemleri"""

    def __init__(self, ayarlar):
        """
        ayarlar: kasa_ayarlari.json içeriği
        """
        self.ayarlar = ayarlar
        self.yazici_adi = ayarlar.get("yazici_adi", "")

    def yazicilari_listele(self):
        """Sistemdeki yazıcıları listele"""
        try:
            import win32print
            yazicilar = []
            for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                yazicilar.append(printer[2])
            return yazicilar
        except ImportError:
            # win32print yoksa, Windows komutunu kullan
            try:
                result = subprocess.run(
                    ['wmic', 'printer', 'get', 'name'],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                lines = result.stdout.strip().split('\n')
                yazicilar = [line.strip() for line in lines[1:] if line.strip()]
                return yazicilar
            except Exception as e:
                logger.error(f"Yazıcı listesi alınamadı: {e}")
                return []

    def varsayilan_yazici_al(self):
        """Varsayılan yazıcıyı al"""
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except ImportError:
            try:
                result = subprocess.run(
                    ['wmic', 'printer', 'where', 'default=true', 'get', 'name'],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            except Exception:
                pass
        return None

    def ayrilan_para_etiketi_olustur(self, kupurler, toplam, kasa_ozeti=None):
        """
        Ayrılan para etiketi oluştur

        kupurler: dict - Küpür adetleri
        toplam: float - Toplam tutar
        kasa_ozeti: dict - Opsiyonel kasa özeti
        """
        tarih = datetime.now().strftime("%d.%m.%Y")
        saat = datetime.now().strftime("%H:%M")

        lines = []
        lines.append("=" * 32)
        lines.append("    AYRILAN PARA ETIKETI")
        lines.append("=" * 32)
        lines.append(f"Tarih: {tarih}  Saat: {saat}")
        lines.append("-" * 32)
        lines.append("")
        lines.append(f"   TOPLAM: {toplam:,.2f} TL")
        lines.append("")
        lines.append("-" * 32)
        lines.append("KUPUR DOKUMU:")

        # Küpür sıralama (büyükten küçüğe)
        kupur_degerleri = [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 1, 0.5, 0.25, 0.1, 0.05]
        kupur_isimleri = {
            5000: "5000 TL", 2000: "2000 TL", 1000: "1000 TL", 500: "500 TL",
            200: "200 TL", 100: "100 TL", 50: "50 TL", 20: "20 TL",
            10: "10 TL", 5: "5 TL", 1: "1 TL",
            0.5: "50 Kr", 0.25: "25 Kr", 0.1: "10 Kr", 0.05: "5 Kr"
        }

        for deger in kupur_degerleri:
            adet = kupurler.get(str(deger), 0)
            if adet > 0:
                isim = kupur_isimleri.get(deger, str(deger))
                tutar = adet * deger
                lines.append(f"  {isim:8} x {adet:3} = {tutar:>10,.2f}")

        lines.append("-" * 32)

        # Kasa özeti varsa ekle
        if kasa_ozeti:
            lines.append("KASA OZETI:")
            lines.append(f"  Nakit: {kasa_ozeti.get('nakit', 0):>15,.2f} TL")
            lines.append(f"  POS:   {kasa_ozeti.get('pos', 0):>15,.2f} TL")
            lines.append(f"  IBAN:  {kasa_ozeti.get('iban', 0):>15,.2f} TL")
            lines.append(f"  GENEL: {kasa_ozeti.get('genel', 0):>15,.2f} TL")
            lines.append("-" * 32)

        lines.append("=" * 32)
        lines.append("")

        return "\n".join(lines)

    def gun_sonu_raporu_olustur(self, kasa_verileri):
        """
        Gün sonu kasa raporu - ULTRA KOMPAKT
        Etiket sola dayalı, rakam sağa dayalı
        """
        tarih = datetime.now().strftime("%d/%m/%Y")
        saat = datetime.now().strftime("%H:%M")

        W = 24  # Satır genişliği

        def row(label, num):
            # Etiket sola dayalı, rakam sağa dayalı (toplam W karakter)
            num_str = f"{num:,.0f}"
            spaces = W - len(label) - len(num_str)
            return label + " " * spaces + num_str

        L = []
        L.append(f"Tarih:{tarih} {saat}".ljust(W))
        L.append("-" * W)

        # Başlangıç kasası
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        L.append(row("Baslangic:", baslangic))

        # Nakit/POS/IBAN
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        L.append(row("Nakit:", nakit))
        L.append(row("POS:", pos))
        L.append(row("IBAN:", iban))
        genel = kasa_verileri.get('genel_toplam', nakit + pos + iban)
        L.append(row("TOPLAM:", genel))

        # Ek kalemler (sadece varsa)
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)
        if masraf > 0:
            L.append(row("Masraf:", masraf))
        if silinen > 0:
            L.append(row("Silinen:", silinen))
        if alinan > 0:
            L.append(row("Alinan:", alinan))

        # Botanik
        L.append("-" * W)
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)
        L.append(row("Bot.Nakit:", botanik_nakit))
        L.append(row("Bot.POS:", botanik_pos))
        L.append(row("Bot.IBAN:", botanik_iban))
        L.append(row("Bot.Toplam:", botanik_toplam))

        # Fark
        L.append("-" * W)
        fark = kasa_verileri.get('fark', 0)
        if abs(fark) < 0.01:
            fark_str = "0 TUTTU"
        elif fark > 0:
            fark_str = f"+{fark:,.0f}"
        else:
            fark_str = f"{fark:,.0f}"
        spaces = W - len("FARK:") - len(fark_str)
        L.append("FARK:" + " " * spaces + fark_str)

        # Ertesi gün kasası
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        L.append(row("Ertesi Gun:", ertesi_gun))

        # Ayrılan para (büyük font)
        L.append("=" * W)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        L.append("{{B}}")
        L.append(row("AYRILAN:", ayrilan))
        L.append(tarih)
        L.append("{{/B}}")

        return "\n".join(L)

    def gun_sonu_raporu_olustur_bytes(self, kasa_verileri):
        """
        Gün sonu kasa raporu - ESC/POS ULTRA KOMPAKT
        Etiket sola dayalı, rakam sağa dayalı
        """
        tarih = datetime.now().strftime("%d/%m/%Y")
        saat = datetime.now().strftime("%H:%M")

        data = bytearray()
        data.extend(INIT_PRINTER)
        data.extend(ESC + b'\x33\x00')  # Minimum satır aralığı

        W = 24  # Satır genişliği

        def row(label, num):
            num_str = f"{num:,.0f}"
            spaces = W - len(label) - len(num_str)
            return label + " " * spaces + num_str

        def add(text, bold=False):
            data.extend(FONT_BOLD if bold else FONT_NORMAL)
            data.extend(text.encode('cp857', errors='replace'))
            data.extend(LINE_FEED)

        def sep():
            add("-" * W)

        # Başlık
        add(f"Tarih:{tarih} {saat}".ljust(W), True)
        sep()

        # Başlangıç kasası
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        add(row("Baslangic:", baslangic))

        # Nakit/POS/IBAN
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        add(row("Nakit:", nakit))
        add(row("POS:", pos))
        add(row("IBAN:", iban))
        genel = kasa_verileri.get('genel_toplam', nakit + pos + iban)
        add(row("TOPLAM:", genel), True)

        # Ek kalemler (sadece varsa)
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)
        if masraf > 0:
            add(row("Masraf:", masraf))
        if silinen > 0:
            add(row("Silinen:", silinen))
        if alinan > 0:
            add(row("Alinan:", alinan))

        # Botanik
        sep()
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)
        add(row("Bot.Nakit:", botanik_nakit))
        add(row("Bot.POS:", botanik_pos))
        add(row("Bot.IBAN:", botanik_iban))
        add(row("Bot.Toplam:", botanik_toplam), True)

        # Fark
        sep()
        fark = kasa_verileri.get('fark', 0)
        if abs(fark) < 0.01:
            fark_str = "0 TUTTU"
        elif fark > 0:
            fark_str = f"+{fark:,.0f}"
        else:
            fark_str = f"{fark:,.0f}"
        spaces = W - len("FARK:") - len(fark_str)
        add("FARK:" + " " * spaces + fark_str, True)

        # Ertesi gün kasası
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        add(row("Ertesi Gun:", ertesi_gun))

        # Ayrılan para - Büyük font
        add("=" * W)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        data.extend(FONT_DOUBLE_WH)
        data.extend(ALIGN_CENTER)
        data.extend(row("AYRILAN:", ayrilan).encode('cp857', errors='replace'))
        data.extend(LINE_FEED)
        data.extend(tarih.encode('cp857', errors='replace'))
        data.extend(LINE_FEED)

        data.extend(FONT_NORMAL)
        data.extend(LINE_FEED)

        return bytes(data)

    def yazdir(self, metin, yazici_adi=None):
        """
        Metni yazıcıya gönder

        metin: str - Yazdırılacak metin
        yazici_adi: str - Opsiyonel yazıcı adı
        """
        kullanilacak_yazici = yazici_adi or self.yazici_adi

        try:
            # Geçici dosya oluştur
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(metin)
                temp_file = f.name

            # Yazıcıya gönder
            if kullanilacak_yazici:
                # Belirli yazıcıya gönder
                try:
                    import win32print
                    import win32api

                    win32api.ShellExecute(
                        0,
                        "printto",
                        temp_file,
                        f'"{kullanilacak_yazici}"',
                        ".",
                        0
                    )
                    logger.info(f"Yazıcıya gönderildi: {kullanilacak_yazici}")
                    return True
                except ImportError:
                    # Fallback: notepad ile yazdır
                    subprocess.run(['notepad', '/p', temp_file], check=False)
            else:
                # Varsayılan yazıcıya gönder (notepad)
                subprocess.run(['notepad', '/p', temp_file], check=False)

            # Geçici dosyayı sil (biraz bekle)
            import time
            time.sleep(2)
            try:
                os.unlink(temp_file)
            except Exception:
                pass

            return True

        except Exception as e:
            logger.error(f"Yazdırma hatası: {e}")
            messagebox.showerror("Yazici Hatasi", f"Yazdirma sirasinda hata olustu:\n{e}")
            return False

    def termal_yazdir(self, data_bytes, yazici_adi=None):
        """
        Binary ESC/POS verisini doğrudan termal yazıcıya gönder
        80mm termal yazıcılar için optimize

        data_bytes: bytes - ESC/POS formatında veri
        yazici_adi: str - Yazıcı adı (örn: "\\\\PC\\POS-80")
        """
        kullanilacak_yazici = yazici_adi or self.yazici_adi

        if not kullanilacak_yazici:
            messagebox.showwarning("Uyarı", "Yazıcı seçilmedi!")
            return False

        try:
            import win32print

            # Yazıcıyı aç
            printer_handle = win32print.OpenPrinter(kullanilacak_yazici)

            try:
                # Yazdırma işini başlat
                job_info = ("Kasa Raporu", None, "RAW")
                win32print.StartDocPrinter(printer_handle, 1, job_info)
                win32print.StartPagePrinter(printer_handle)

                # Veriyi gönder
                win32print.WritePrinter(printer_handle, data_bytes)

                # Bitir
                win32print.EndPagePrinter(printer_handle)
                win32print.EndDocPrinter(printer_handle)

                logger.info(f"Termal yazıcıya gönderildi: {kullanilacak_yazici}")
                return True

            finally:
                win32print.ClosePrinter(printer_handle)

        except ImportError:
            logger.warning("win32print modülü yok, metin modu kullanılıyor")
            # Fallback: Metin modunda yazdır
            return self.yazdir(data_bytes.decode('cp857', errors='replace'))

        except Exception as e:
            logger.error(f"Termal yazdırma hatası: {e}")
            messagebox.showerror("Yazıcı Hatası", f"Termal yazdırma hatası:\n{e}")
            return False

    def kasa_raporu_yazdir(self, kasa_verileri, yazici_adi=None):
        """
        Kasa raporunu termal yazıcıya gönder
        Otomatik olarak ESC/POS formatını kullanır

        kasa_verileri: dict - Kasa kapatma verileri
        yazici_adi: str - Yazıcı adı
        """
        try:
            # ESC/POS formatında rapor oluştur
            data = self.gun_sonu_raporu_olustur_bytes(kasa_verileri)

            # Termal yazıcıya gönder
            return self.termal_yazdir(data, yazici_adi)

        except Exception as e:
            logger.error(f"Rapor yazdırma hatası: {e}")
            # Fallback: Normal metin modu
            metin = self.gun_sonu_raporu_olustur(kasa_verileri)
            return self.yazdir(metin, yazici_adi)

    def dosyaya_kaydet(self, metin, dosya_adi=None):
        """
        Metni dosyaya kaydet

        metin: str - Kaydedilecek metin
        dosya_adi: str - Opsiyonel dosya adı
        """
        try:
            if not dosya_adi:
                tarih = datetime.now().strftime("%Y%m%d_%H%M%S")
                dosya_adi = f"kasa_rapor_{tarih}.txt"

            script_dir = os.path.dirname(os.path.abspath(__file__))
            dosya_yolu = Path(script_dir) / dosya_adi

            with open(dosya_yolu, 'w', encoding='utf-8') as f:
                f.write(metin)

            logger.info(f"Rapor dosyaya kaydedildi: {dosya_yolu}")
            return str(dosya_yolu)

        except Exception as e:
            logger.error(f"Dosya kaydetme hatası: {e}")
            return None


class YaziciSecimPenceresi:
    """Yazıcı seçim penceresi"""

    def __init__(self, parent, ayarlar, on_select=None):
        self.parent = parent
        self.ayarlar = ayarlar
        self.on_select = on_select
        self.secilen_yazici = None
        self.pencere = None

    def goster(self):
        """Yazıcı seçim penceresi göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Yazici Sec")
        self.pencere.geometry("400x350")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#FAFAFA')

        # Başlık
        tk.Label(
            self.pencere,
            text="Yazici Secin",
            font=("Arial", 14, "bold"),
            bg='#FAFAFA'
        ).pack(pady=15)

        # Yazıcı listesi
        liste_frame = tk.Frame(self.pencere, bg='#FAFAFA')
        liste_frame.pack(fill="both", expand=True, padx=20, pady=10)

        scrollbar = ttk.Scrollbar(liste_frame)
        scrollbar.pack(side="right", fill="y")

        self.yazici_listbox = tk.Listbox(
            liste_frame,
            font=("Arial", 10),
            yscrollcommand=scrollbar.set,
            height=10
        )
        self.yazici_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.yazici_listbox.yview)

        # Yazıcıları listele
        yazici = KasaYazici(self.ayarlar)
        yazicilar = yazici.yazicilari_listele()
        varsayilan = yazici.varsayilan_yazici_al()

        for y in yazicilar:
            if y == varsayilan:
                self.yazici_listbox.insert(tk.END, f"{y} (Varsayilan)")
            else:
                self.yazici_listbox.insert(tk.END, y)

        # Mevcut seçimi işaretle
        mevcut = self.ayarlar.get("yazici_adi", "")
        for i, item in enumerate(yazicilar):
            if item == mevcut:
                self.yazici_listbox.selection_set(i)
                self.yazici_listbox.see(i)
                break

        # Butonlar
        buton_frame = tk.Frame(self.pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill="x")

        tk.Button(
            buton_frame,
            text="Iptal",
            font=("Arial", 10),
            bg='#9E9E9E',
            fg='white',
            width=10,
            command=self.pencere.destroy
        ).pack(side="left", padx=20)

        tk.Button(
            buton_frame,
            text="Sec",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            width=10,
            command=self.sec
        ).pack(side="right", padx=20)

    def sec(self):
        """Seçilen yazıcıyı kaydet"""
        selection = self.yazici_listbox.curselection()
        if selection:
            secilen = self.yazici_listbox.get(selection[0])
            # "(Varsayilan)" kısmını kaldır
            if " (Varsayilan)" in secilen:
                secilen = secilen.replace(" (Varsayilan)", "")

            self.secilen_yazici = secilen

            if self.on_select:
                self.on_select(secilen)

        self.pencere.destroy()
