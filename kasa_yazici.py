"""
Botanik Bot - Kasa Termal Yazıcı Desteği
Termal yazıcıdan kasa raporu ve etiket basma
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
        Gün sonu kasa raporu oluştur

        kasa_verileri: dict - Kasa kapatma verileri
        """
        tarih = datetime.now().strftime("%d.%m.%Y")
        saat = datetime.now().strftime("%H:%M")

        lines = []
        lines.append("=" * 40)
        lines.append("        GUN SONU KASA RAPORU")
        lines.append("=" * 40)
        lines.append(f"Tarih: {tarih}  Saat: {saat}")
        lines.append("-" * 40)

        # Başlangıç kasası
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        lines.append(f"Baslangic Kasasi: {baslangic:>18,.2f} TL")
        lines.append("-" * 40)

        # Kasa sayımı
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)

        lines.append("KASA SAYIMI:")
        lines.append(f"  Nakit Toplam:   {nakit:>18,.2f} TL")
        lines.append(f"  POS Toplam:     {pos:>18,.2f} TL")
        lines.append(f"  IBAN Toplam:    {iban:>18,.2f} TL")
        lines.append("-" * 40)

        # Genel toplam
        genel = kasa_verileri.get('genel_toplam', 0)
        lines.append(f"GENEL TOPLAM:     {genel:>18,.2f} TL")
        lines.append("-" * 40)

        # Ek kalemler
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)

        if masraf > 0 or silinen > 0 or alinan > 0:
            lines.append("EK KALEMLER:")
            if masraf > 0:
                lines.append(f"  Masraflar:      {masraf:>18,.2f} TL")
            if silinen > 0:
                lines.append(f"  Silinen Recete: {silinen:>18,.2f} TL")
            if alinan > 0:
                lines.append(f"  Alinan Para:    {alinan:>18,.2f} TL")
            lines.append("-" * 40)

        # Son genel toplam
        son_genel = kasa_verileri.get('son_genel_toplam', genel)
        lines.append(f"SON GENEL TOPLAM: {son_genel:>18,.2f} TL")
        lines.append("=" * 40)

        # Botanik verileri
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)

        lines.append("BOTANIK VERILERI:")
        lines.append(f"  Nakit:          {botanik_nakit:>18,.2f} TL")
        lines.append(f"  POS:            {botanik_pos:>18,.2f} TL")
        lines.append(f"  IBAN:           {botanik_iban:>18,.2f} TL")
        lines.append(f"  BOTANIK TOPLAM: {botanik_toplam:>18,.2f} TL")
        lines.append("-" * 40)

        # Fark
        fark = kasa_verileri.get('fark', 0)
        fark_text = f"+{fark:,.2f}" if fark > 0 else f"{fark:,.2f}"
        lines.append(f"FARK:             {fark_text:>18} TL")

        if abs(fark) < 0.01:
            lines.append("                   [TUTTU]")
        elif fark > 0:
            lines.append("                   [FAZLA]")
        else:
            lines.append("                   [EKSIK]")

        lines.append("=" * 40)

        # Ertesi gün kasası
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        lines.append("")
        lines.append(f"ERTESI GUN KASASI: {ertesi_gun:>17,.2f} TL")

        # Ayrılan para
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        if ayrilan > 0:
            lines.append(f"AYRILAN PARA:      {ayrilan:>17,.2f} TL")

        lines.append("=" * 40)
        lines.append("")

        return "\n".join(lines)

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
