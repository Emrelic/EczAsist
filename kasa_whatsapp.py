"""
Botanik Bot - Kasa WhatsApp Entegrasyonu
WhatsApp üzerinden kasa raporu gönderme
"""

import tkinter as tk
from tkinter import messagebox
import webbrowser
import urllib.parse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KasaWhatsAppRapor:
    """WhatsApp üzerinden kasa raporu gönderme"""

    def __init__(self, ayarlar):
        """
        ayarlar: kasa_ayarlari.json içeriği
        """
        self.ayarlar = ayarlar
        self.whatsapp_numara = ayarlar.get("whatsapp_numara", "")

    def rapor_olustur(self, kasa_verileri):
        """
        Kasa verilerinden WhatsApp mesajı oluştur

        kasa_verileri: dict - Kasa kapatma verileri
        """
        tarih = datetime.now().strftime("%d.%m.%Y")
        saat = datetime.now().strftime("%H:%M")

        # Rapor metni oluştur
        rapor = []
        rapor.append("=" * 30)
        rapor.append("KASA KAPAMA RAPORU")
        rapor.append("=" * 30)
        rapor.append(f"Tarih: {tarih}")
        rapor.append(f"Saat: {saat}")
        rapor.append("-" * 30)

        # Başlangıç kasası
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        rapor.append(f"Başlangıç Kasası: {baslangic:,.2f} TL")
        rapor.append("-" * 30)

        # Sayım sonuçları
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        genel = kasa_verileri.get('genel_toplam', 0)

        rapor.append("KASA SAYIMI:")
        rapor.append(f"  Nakit: {nakit:,.2f} TL")
        rapor.append(f"  POS: {pos:,.2f} TL")
        rapor.append(f"  IBAN: {iban:,.2f} TL")
        rapor.append(f"  GENEL TOPLAM: {genel:,.2f} TL")
        rapor.append("-" * 30)

        # Ek kalemler
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)

        if masraf > 0 or silinen > 0 or alinan > 0:
            rapor.append("EK KALEMLER:")
            if masraf > 0:
                rapor.append(f"  Masraflar: {masraf:,.2f} TL")
            if silinen > 0:
                rapor.append(f"  Silinen Reçete: {silinen:,.2f} TL")
            if alinan > 0:
                rapor.append(f"  Alınan Para: {alinan:,.2f} TL")
            rapor.append("-" * 30)

        # Son genel toplam
        son_genel = kasa_verileri.get('son_genel_toplam', genel)
        rapor.append(f"SON GENEL TOPLAM: {son_genel:,.2f} TL")
        rapor.append("-" * 30)

        # Botanik verileri
        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)

        rapor.append("BOTANİK VERİLERİ:")
        rapor.append(f"  Nakit: {botanik_nakit:,.2f} TL")
        rapor.append(f"  POS: {botanik_pos:,.2f} TL")
        rapor.append(f"  IBAN: {botanik_iban:,.2f} TL")
        rapor.append(f"  BOTANİK TOPLAM: {botanik_toplam:,.2f} TL")
        rapor.append("-" * 30)

        # Fark
        fark = kasa_verileri.get('fark', 0)
        fark_text = f"+{fark:,.2f}" if fark > 0 else f"{fark:,.2f}"
        fark_emoji = "✅" if abs(fark) < 0.01 else "⚠️" if fark > 0 else "❌"

        rapor.append(f"FARK: {fark_text} TL {fark_emoji}")
        rapor.append("=" * 30)

        # Ertesi gün kasası
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        rapor.append(f"ERTESİ GÜN KASASI: {ertesi_gun:,.2f} TL")

        # Ayrılan para
        ayrilan = kasa_verileri.get('ayrilan_para', 0)
        rapor.append(f"AYRILAN PARA: {ayrilan:,.2f} TL")

        rapor.append("=" * 30)

        return "\n".join(rapor)

    def whatsapp_gonder(self, mesaj):
        """
        WhatsApp üzerinden mesaj gönder

        mesaj: str - Gönderilecek mesaj
        """
        if not self.whatsapp_numara:
            messagebox.showwarning(
                "WhatsApp Numarası Eksik",
                "WhatsApp numarası ayarlanmamış!\n\n"
                "Ayarlar bölümünden WhatsApp numarasını giriniz."
            )
            return False

        try:
            # Numarayı formatla (başında + veya 0 varsa kaldır)
            numara = self.whatsapp_numara.strip()
            if numara.startswith("+"):
                numara = numara[1:]
            if numara.startswith("0"):
                numara = "90" + numara[1:]  # Türkiye için
            if not numara.startswith("90"):
                numara = "90" + numara

            # Mesajı URL encode et
            encoded_mesaj = urllib.parse.quote(mesaj)

            # WhatsApp API URL'i
            # wa.me kullanarak doğrudan mesaj penceresi açar
            url = f"https://wa.me/{numara}?text={encoded_mesaj}"

            # Tarayıcıda aç
            webbrowser.open(url)

            logger.info(f"WhatsApp mesajı gönderildi: {numara}")
            return True

        except Exception as e:
            logger.error(f"WhatsApp gönderme hatası: {e}")
            messagebox.showerror("Hata", f"WhatsApp açılırken hata oluştu:\n{e}")
            return False

    def rapor_gonder(self, kasa_verileri):
        """
        Kasa raporunu WhatsApp ile gönder

        kasa_verileri: dict - Kasa kapatma verileri
        """
        mesaj = self.rapor_olustur(kasa_verileri)
        return self.whatsapp_gonder(mesaj)

    def panoya_kopyala(self, kasa_verileri):
        """
        Raporu panoya kopyala

        kasa_verileri: dict - Kasa kapatma verileri
        """
        try:
            mesaj = self.rapor_olustur(kasa_verileri)

            # Tkinter root oluştur (clipboard için gerekli)
            root = tk.Tk()
            root.withdraw()

            # Panoya kopyala
            root.clipboard_clear()
            root.clipboard_append(mesaj)
            root.update()
            root.destroy()

            messagebox.showinfo(
                "Kopyalandı",
                "Kasa raporu panoya kopyalandı!\n\n"
                "WhatsApp'a yapıştırabilirsiniz."
            )
            return True

        except Exception as e:
            logger.error(f"Panoya kopyalama hatası: {e}")
            messagebox.showerror("Hata", f"Panoya kopyalama hatası:\n{e}")
            return False


class KasaWhatsAppPenceresi:
    """WhatsApp rapor gönderme penceresi"""

    def __init__(self, parent, ayarlar, kasa_verileri):
        self.parent = parent
        self.ayarlar = ayarlar
        self.kasa_verileri = kasa_verileri
        self.whatsapp = KasaWhatsAppRapor(ayarlar)
        self.pencere = None

    def goster(self):
        """WhatsApp penceresi göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("WhatsApp Rapor Gönder")
        self.pencere.geometry("550x500")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#FAFAFA')

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#25D366', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="WhatsApp Kasa Raporu",
            font=("Arial", 14, "bold"),
            bg='#25D366',
            fg='white'
        ).pack(expand=True)

        # Rapor önizleme
        onizleme_frame = tk.LabelFrame(
            self.pencere,
            text="Rapor Önizleme",
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            padx=10,
            pady=10
        )
        onizleme_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Text widget
        rapor_text = tk.Text(
            onizleme_frame,
            font=("Courier", 9),
            wrap='word',
            height=18,
            bg='#F5F5F5'
        )
        rapor_text.pack(fill="both", expand=True)

        # Raporu göster
        rapor = self.whatsapp.rapor_olustur(self.kasa_verileri)
        rapor_text.insert('1.0', rapor)
        rapor_text.config(state='disabled')

        # WhatsApp numarası
        numara_frame = tk.Frame(self.pencere, bg='#FAFAFA')
        numara_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(
            numara_frame,
            text="WhatsApp No:",
            font=("Arial", 10),
            bg='#FAFAFA'
        ).pack(side="left")

        numara = self.ayarlar.get("whatsapp_numara", "")
        numara_gosterim = numara if numara else "Ayarlanmamış"

        tk.Label(
            numara_frame,
            text=numara_gosterim,
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            fg='#25D366' if numara else '#F44336'
        ).pack(side="left", padx=10)

        # Butonlar
        buton_frame = tk.Frame(self.pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill="x")

        tk.Button(
            buton_frame,
            text="Panoya Kopyala",
            font=("Arial", 10),
            bg='#2196F3',
            fg='white',
            width=15,
            cursor='hand2',
            command=lambda: self.whatsapp.panoya_kopyala(self.kasa_verileri)
        ).pack(side="left", padx=20)

        tk.Button(
            buton_frame,
            text="WhatsApp ile Gönder",
            font=("Arial", 11, "bold"),
            bg='#25D366',
            fg='white',
            width=18,
            cursor='hand2',
            command=self.gonder
        ).pack(side="right", padx=20)

    def gonder(self):
        """Raporu WhatsApp ile gönder"""
        if self.whatsapp.rapor_gonder(self.kasa_verileri):
            self.pencere.destroy()
