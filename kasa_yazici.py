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
        Gün sonu kasa raporu oluştur - 80mm termal yazıcı için optimize
        Kompakt format, minimum kağıt ve yan boşluk

        kasa_verileri: dict - Kasa kapatma verileri
        """
        tarih = datetime.now().strftime("%d.%m.%Y")
        saat = datetime.now().strftime("%H:%M")

        # 80mm termal = 32 karakter (standart)
        W = 32

        lines = []

        # BAŞLIK - Tarih/Saat
        lines.append("=" * W)
        lines.append(f"KASA RAPORU {tarih} {saat}")
        lines.append("=" * W)

        # BAŞLANGIÇ KASASI
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        lines.append(f"Baslangic:{baslangic:>10,.0f}TL")

        # KÜPÜR SAYIMLARI
        lines.append("")  # Grup arası boşluk
        kupurler = kasa_verileri.get('kupurler', {})
        if kupurler:
            kupur_sirasi = [200, 100, 50, 20, 10, 5, 1, 0.5]
            for k in kupur_sirasi:
                adet = kupurler.get(str(k), kupurler.get(k, 0))
                if adet and int(adet) > 0:
                    tutar = int(adet) * k
                    if k >= 1:
                        lines.append(f"{int(k):>3}TLx{int(adet):>2}={tutar:>7,.0f}TL")
                    else:
                        kr = int(k * 100)
                        lines.append(f"{kr:>2}Krx{int(adet):>2}={tutar:>7,.2f}TL")

        # NAKİT/POS/IBAN TOPLAMLARI
        lines.append("")  # Grup arası boşluk
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        lines.append(f"Nakit:{nakit:>13,.0f}TL")
        lines.append(f"POS:{pos:>15,.0f}TL")
        lines.append(f"IBAN:{iban:>14,.0f}TL")
        genel = kasa_verileri.get('genel_toplam', nakit + pos + iban)
        lines.append("-" * W)
        lines.append(f"TOPLAM:{genel:>12,.0f}TL")

        # EK KALEMLER (sadece varsa)
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)
        if masraf > 0 or silinen > 0 or alinan > 0:
            lines.append("")  # Grup arası boşluk
            if masraf > 0:
                lines.append(f"Masraf:{masraf:>12,.0f}TL")
            if silinen > 0:
                lines.append(f"Silinen:{silinen:>11,.0f}TL")
            if alinan > 0:
                lines.append(f"Alinan:{alinan:>12,.0f}TL")

        # BOTANİK VERİLERİ
        lines.append("")  # Grup arası boşluk
        lines.append("-BOTANIK-".center(W, '-'))
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)
        lines.append(f"Nakit:{botanik_nakit:>13,.0f}TL")
        lines.append(f"POS:{botanik_pos:>15,.0f}TL")
        lines.append(f"IBAN:{botanik_iban:>14,.0f}TL")
        lines.append(f"Toplam:{botanik_toplam:>12,.0f}TL")

        # FARK
        lines.append("")  # Grup arası boşluk
        fark = kasa_verileri.get('fark', 0)
        if abs(fark) < 0.01:
            lines.append("***FARK:0 [TUTTU]***".center(W))
        elif fark > 0:
            lines.append(f"FARK:+{fark:,.0f}TL [FAZLA]".center(W))
        else:
            lines.append(f"FARK:{fark:,.0f}TL [EKSIK]".center(W))

        # ERTESİ GÜN KASASI
        lines.append("")  # Grup arası boşluk
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        lines.append(f"ErtesiGun:{ertesi_gun:>9,.0f}TL")
        lines.append("=" * W)

        # AYRILAN PARA - Büyük font işareti
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        lines.append("")
        lines.append("{{BUYUK}}")
        lines.append(f"AYRILAN:{ayrilan:,.0f}TL")
        lines.append("{{/BUYUK}}")

        # TARİH - Büyük font
        lines.append("")
        lines.append("{{BUYUK}}")
        lines.append(tarih)
        lines.append("{{/BUYUK}}")
        lines.append("")

        return "\n".join(lines)

    def gun_sonu_raporu_olustur_bytes(self, kasa_verileri):
        """
        Gün sonu kasa raporu - ESC/POS binary format
        80mm termal yazıcı için kompakt format
        """
        tarih = datetime.now().strftime("%d.%m.%Y")
        saat = datetime.now().strftime("%H:%M")

        data = bytearray()
        data.extend(INIT_PRINTER)

        W = 32  # 80mm = 32 karakter

        def add_text(text, font=FONT_NORMAL, align=ALIGN_LEFT, newline=True):
            data.extend(font)
            data.extend(align)
            data.extend(text.encode('cp857', errors='replace'))
            if newline:
                data.extend(LINE_FEED)

        def add_line(text):
            add_text(text)

        def add_empty():
            data.extend(LINE_FEED)

        # BAŞLIK
        add_line("=" * W)
        add_text(f"KASA RAPORU {tarih} {saat}", FONT_BOLD, ALIGN_CENTER)
        add_line("=" * W)

        # BAŞLANGIÇ KASASI
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        add_line(f"Baslangic:{baslangic:>10,.0f}TL")

        # KÜPÜR SAYIMLARI
        add_empty()
        kupurler = kasa_verileri.get('kupurler', {})
        if kupurler:
            kupur_sirasi = [200, 100, 50, 20, 10, 5, 1, 0.5]
            for k in kupur_sirasi:
                adet = kupurler.get(str(k), kupurler.get(k, 0))
                if adet and int(adet) > 0:
                    tutar = int(adet) * k
                    if k >= 1:
                        add_line(f"{int(k):>3}TLx{int(adet):>2}={tutar:>7,.0f}TL")
                    else:
                        kr = int(k * 100)
                        add_line(f"{kr:>2}Krx{int(adet):>2}={tutar:>7,.2f}TL")

        # NAKİT/POS/IBAN
        add_empty()
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        add_line(f"Nakit:{nakit:>13,.0f}TL")
        add_line(f"POS:{pos:>15,.0f}TL")
        add_line(f"IBAN:{iban:>14,.0f}TL")
        add_line("-" * W)
        genel = kasa_verileri.get('genel_toplam', nakit + pos + iban)
        add_text(f"TOPLAM:{genel:>12,.0f}TL", FONT_BOLD)

        # EK KALEMLER
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)
        if masraf > 0 or silinen > 0 or alinan > 0:
            add_empty()
            if masraf > 0:
                add_line(f"Masraf:{masraf:>12,.0f}TL")
            if silinen > 0:
                add_line(f"Silinen:{silinen:>11,.0f}TL")
            if alinan > 0:
                add_line(f"Alinan:{alinan:>12,.0f}TL")

        # BOTANİK
        add_empty()
        add_text("-BOTANIK-".center(W, '-'), FONT_BOLD)
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)
        add_line(f"Nakit:{botanik_nakit:>13,.0f}TL")
        add_line(f"POS:{botanik_pos:>15,.0f}TL")
        add_line(f"IBAN:{botanik_iban:>14,.0f}TL")
        add_text(f"Toplam:{botanik_toplam:>12,.0f}TL", FONT_BOLD)

        # FARK
        add_empty()
        fark = kasa_verileri.get('fark', 0)
        if abs(fark) < 0.01:
            add_text("***FARK:0 [TUTTU]***".center(W), FONT_BOLD, ALIGN_CENTER)
        elif fark > 0:
            add_text(f"FARK:+{fark:,.0f}TL [FAZLA]", FONT_BOLD, ALIGN_CENTER)
        else:
            add_text(f"FARK:{fark:,.0f}TL [EKSIK]", FONT_BOLD, ALIGN_CENTER)

        # ERTESİ GÜN KASASI
        add_empty()
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        add_line(f"ErtesiGun:{ertesi_gun:>9,.0f}TL")
        add_line("=" * W)

        # AYRILAN PARA - EN BÜYÜK FONT
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        add_empty()
        data.extend(FONT_DOUBLE_WH)
        data.extend(ALIGN_CENTER)
        data.extend("AYRILAN".encode('cp857', errors='replace'))
        data.extend(LINE_FEED)
        data.extend(FONT_XLARGE)
        data.extend(ALIGN_CENTER)
        data.extend(f"{ayrilan:,.0f}TL".encode('cp857', errors='replace'))
        data.extend(LINE_FEED)

        # TARİH - BÜYÜK FONT
        add_empty()
        data.extend(FONT_DOUBLE_WH)
        data.extend(ALIGN_CENTER)
        data.extend(tarih.encode('cp857', errors='replace'))
        data.extend(LINE_FEED)

        # Bitir
        data.extend(FONT_NORMAL)
        data.extend(LINE_FEED)
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
