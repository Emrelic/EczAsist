"""
Botanik Bot - Kasa WhatsApp Entegrasyonu
WhatsApp üzerinden kasa raporu gönderme
WhatsApp mesaj formatına özel optimize edilmiş rapor
"""

import tkinter as tk
from tkinter import messagebox
import webbrowser
import urllib.parse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Botanik screenshot fonksiyonları
try:
    from botanik_veri_cek import kasa_kapatma_screenshot, screenshot_clipboard_kopyala, botanik_penceresi_acik_mi
    SCREENSHOT_DESTEGI = True
except ImportError:
    SCREENSHOT_DESTEGI = False
    logger.warning("botanik_veri_cek modülü yüklenemedi, screenshot desteği devre dışı")

# Rapor ayarlarını yükle
try:
    from rapor_ayarlari import rapor_ayarlarini_yukle
except ImportError:
    def rapor_ayarlarini_yukle():
        return {"whatsapp": {}}


class KasaWhatsAppRapor:
    """WhatsApp üzerinden kasa raporu gönderme"""

    def __init__(self, ayarlar):
        """
        ayarlar: kasa_ayarlari.json içeriği
        """
        self.ayarlar = ayarlar
        self.whatsapp_numara = ayarlar.get("whatsapp_numara", "")

    def rapor_olustur(self, kasa_verileri, ayarlar=None):
        """
        Kasa verilerinden WhatsApp mesajı oluştur
        WhatsApp'a özel format - tek mesajda, satır kesiksiz
        Tüm noktalarla dolgu, rakamlar sağa hizalı
        """
        # Ayarları yükle
        if ayarlar is None:
            rapor_ayarlari = rapor_ayarlarini_yukle()
            ayarlar = rapor_ayarlari.get("whatsapp", {})

        gun_isimleri = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        gun = gun_isimleri[datetime.now().weekday()]
        tarih = datetime.now().strftime("%d/%m/%Y")
        saat = datetime.now().strftime("%H:%M")

        # Verileri al
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)

        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)

        # Düzeltilmiş nakit (9 nolu tablo için)
        duz_nakit = nakit + masraf + silinen + alinan
        duz_toplam = duz_nakit + pos + iban

        # Farklar
        nakit_fark = duz_nakit - botanik_nakit
        pos_fark = pos - botanik_pos
        iban_fark = iban - botanik_iban
        genel_fark = duz_toplam - botanik_toplam

        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)

        # Manuel başlangıç bilgisi
        manuel_baslangic = kasa_verileri.get('manuel_baslangic', {})
        manuel_aktif = manuel_baslangic.get('aktif', False)

        # ============================================
        # FORMAT AYARLARI
        # ============================================
        W = 32  # Satır genişliği (WhatsApp'ta tek satır)

        def fmt(n):
            """Sayı formatla (binlik ayraç, virgül)"""
            return f"{n:,.0f}"

        def fark_fmt(n):
            """Fark formatla (+/- işaretli)"""
            if abs(n) < 0.01:
                return "0"
            return f"+{n:,.0f}" if n > 0 else f"{n:,.0f}"

        def satir(etiket, rakam, num_w=10):
            """
            Nokta dolgulu satır - rakam sağa hizalı
            etiket: Sol taraftaki yazı
            rakam: Sağa hizalanacak sayı
            num_w: Rakam için ayrılan genişlik
            """
            num_str = fmt(rakam)
            num_fmt = num_str.rjust(num_w)
            etiket_w = W - num_w
            pad = etiket_w - len(etiket)
            return etiket + "." * max(pad, 1) + num_fmt

        # ============================================
        # MESAJ OLUŞTUR
        # ============================================
        L = []

        # Başlık
        baslik = f"{gun}.{tarih}.{saat}"
        L.append(f"*{baslik.center(W)}*")
        L.append("=" * W)

        # Ana veriler
        if ayarlar.get("baslangic_kasasi_toplam", True):
            lbl = "Baslangic*" if manuel_aktif else "Baslangic"
            L.append(satir(lbl, baslangic))

        if ayarlar.get("gun_sonu_nakit_toplam", True):
            L.append(satir("Nakit", nakit))

        if ayarlar.get("pos_toplamlari", True):
            L.append(satir("POS", pos))

        if ayarlar.get("iban_toplamlari", True):
            L.append(satir("IBAN", iban))

        L.append("-" * W)

        # Düzeltmeler
        if ayarlar.get("girilmeyen_masraflar", True) and masraf > 0:
            L.append(satir("Masraf.(-)", masraf))
        if ayarlar.get("silinen_etkiler", True) and silinen > 0:
            L.append(satir("Silinen(-)", silinen))
        if ayarlar.get("alinan_paralar", True) and alinan > 0:
            L.append(satir("Alinan.(+)", alinan))

        L.append("=" * W)

        # ============================================
        # SAYIM - BOTANİK KARŞILAŞTIRMA TABLOSU
        # ============================================
        if ayarlar.get("sayim_botanik_ozet", True):
            # Sütun genişlikleri: ETK(5) + SAY(8) + BOT(9) + FRK(8) + 2 nokta = 32
            ETK_W = 5
            SAY_W = 8
            BOT_W = 9
            FRK_W = 8

            # Başlık
            h = f"{'SAY'.rjust(SAY_W)}.{'BOT'.rjust(BOT_W)}.{'FARK'.rjust(FRK_W)}"
            L.append(h.rjust(W))
            L.append("-" * W)

            def tablo(lbl, say, bot, frk):
                """Tablo satırı - tüm sütunlar sağa hizalı, noktalarla ayrılmış"""
                lbl_fmt = (lbl + ".")[:ETK_W].ljust(ETK_W, ".")
                say_fmt = fmt(say).rjust(SAY_W)
                bot_fmt = fmt(bot).rjust(BOT_W)
                frk_fmt = fark_fmt(frk).rjust(FRK_W)
                return f"{lbl_fmt}{say_fmt}.{bot_fmt}.{frk_fmt}"

            L.append(tablo("Nakt", duz_nakit, botanik_nakit, nakit_fark))
            L.append(tablo("POS", pos, botanik_pos, pos_fark))
            L.append(tablo("IBAN", iban, botanik_iban, iban_fark))
            L.append("-" * W)
            L.append(f"*{tablo('TOP', duz_toplam, botanik_toplam, genel_fark)}*")

        L.append("=" * W)

        # Ertesi gün ve ayrılan
        if ayarlar.get("ertesi_gun_toplam", True):
            L.append(satir("Ertesi.Gun", ertesi_gun))

        if ayarlar.get("ayrilan_para", True):
            L.append(satir("*AYRILAN*", ayrilan))

        L.append("=" * W)

        # Son satır - vurgulu
        L.append(f"*{fmt(ayrilan)}.TL*".center(W))

        return "\n".join(L)

    def rapor_olustur_monospace(self, kasa_verileri, ayarlar=None):
        """
        Kasa verilerinden WhatsApp mesajı oluştur
        Monospace (```) formatlı versiyon
        """
        # Ayarları yükle
        if ayarlar is None:
            rapor_ayarlari = rapor_ayarlarini_yukle()
            ayarlar = rapor_ayarlari.get("whatsapp", {})

        gun_isimleri = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        gun = gun_isimleri[datetime.now().weekday()]
        tarih = datetime.now().strftime("%d/%m/%Y")
        saat = datetime.now().strftime("%H:%M")

        W = 34  # WhatsApp için genişlik

        # Verileri al
        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        genel = kasa_verileri.get('genel_toplam', nakit + pos + iban)
        masraf = kasa_verileri.get('masraf_toplam', 0)
        silinen = kasa_verileri.get('silinen_toplam', 0)
        alinan = kasa_verileri.get('alinan_toplam', 0)
        son_genel = genel - masraf - silinen + alinan

        botanik_nakit = kasa_verileri.get('botanik_nakit', 0)
        botanik_pos = kasa_verileri.get('botanik_pos', 0)
        botanik_iban = kasa_verileri.get('botanik_iban', 0)
        botanik_toplam = kasa_verileri.get('botanik_toplam', 0)

        # Düzeltilmiş nakit hesaplama (9 nolu tablo için)
        duzeltilmis_nakit = nakit + masraf + silinen + alinan
        duzeltilmis_toplam = duzeltilmis_nakit + pos + iban

        # Farklar (düzeltilmiş nakit ile botanik karşılaştırması)
        nakit_fark = duzeltilmis_nakit - botanik_nakit
        pos_fark = pos - botanik_pos
        iban_fark = iban - botanik_iban
        genel_fark = duzeltilmis_toplam - botanik_toplam

        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)

        def fmt(n):
            """Sayıyı formatla"""
            return f"{n:,.0f}"

        def fark_fmt(n):
            """Farkı formatla"""
            if abs(n) < 0.01:
                return "0"
            elif n > 0:
                return f"+{n:,.0f}"
            else:
                return f"{n:,.0f}"

        def row(label, num):
            """Nokta dolgulu satır"""
            num_str = fmt(num)
            pad = W - len(label) - len(num_str)
            return label + "." * max(pad, 1) + num_str

        L = []
        L.append("```")

        # Başlık
        baslik = f"{gun} {tarih} {saat}"
        L.append(baslik.center(W))
        L.append("=" * W)

        # Toplamlar
        if ayarlar.get("baslangic_kasasi_toplam", True):
            L.append(row("BASLANGIC", baslangic))

        if ayarlar.get("gun_sonu_nakit_toplam", True):
            L.append(row("NAKIT", nakit))

        if ayarlar.get("pos_toplamlari", True):
            L.append(row("POS", pos))

        if ayarlar.get("iban_toplamlari", True):
            L.append(row("IBAN", iban))

        L.append("-" * W)

        # Düzeltmeler
        if ayarlar.get("girilmeyen_masraflar", True) and masraf > 0:
            L.append(row("MASRAF(-)", masraf))
        if ayarlar.get("silinen_etkiler", True) and silinen > 0:
            L.append(row("SILINEN(-)", silinen))
        if ayarlar.get("alinan_paralar", True) and alinan > 0:
            L.append(row("ALINAN(+)", alinan))

        L.append("=" * W)

        # Sayım-Botanik özet tablosu - sağa hizalı format
        if ayarlar.get("sayim_botanik_ozet", True):
            # Sütun genişlikleri (toplam W=34 olacak şekilde)
            LBL_W = 6
            SAY_W = 8
            BOT_W = 9
            FRK_W = 9

            baslik = f"{'SAYIM'.rjust(SAY_W)}..{'BOTANIK'.rjust(BOT_W)}..{'FARK'.rjust(FRK_W)}"
            L.append(baslik)
            L.append("-" * W)

            def tablo_satir(lbl, duz, bot, frk):
                """Sağa hizalı satır, noktalarla dolgulu"""
                duz_s = fmt(duz)
                bot_s = fmt(bot)
                frk_s = fark_fmt(frk)

                lbl_dots = (lbl + ".")[:LBL_W].ljust(LBL_W, ".")
                duz_fmt = duz_s.rjust(SAY_W)
                bot_fmt = bot_s.rjust(BOT_W)
                frk_fmt = frk_s.rjust(FRK_W)

                return f"{lbl_dots}{duz_fmt}..{bot_fmt}..{frk_fmt}"

            L.append(tablo_satir("Nakit", duzeltilmis_nakit, botanik_nakit, nakit_fark))
            L.append(tablo_satir("POS", pos, botanik_pos, pos_fark))
            L.append(tablo_satir("IBAN", iban, botanik_iban, iban_fark))
            L.append("-" * W)
            L.append(tablo_satir("TOPLAM", duzeltilmis_toplam, botanik_toplam, genel_fark))
            L.append("=" * W)

        # Sonuçlar
        if ayarlar.get("ertesi_gun_toplam", True):
            L.append(row("ERTESI GUN", ertesi_gun))

        if ayarlar.get("ayrilan_para", True):
            L.append(row("AYRILAN", ayrilan))

        L.append("=" * W)

        # Son bilgi
        L.append(f"AYRILAN: {fmt(ayrilan)}".center(W))

        L.append("```")

        return "\n".join(L)

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
        self.screenshot_var = None  # Checkbox değişkeni

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

        # Screenshot seçeneği
        if SCREENSHOT_DESTEGI:
            screenshot_frame = tk.Frame(self.pencere, bg='#FAFAFA')
            screenshot_frame.pack(fill="x", padx=10, pady=5)

            self.screenshot_var = tk.BooleanVar(value=False)

            # Botanik penceresi açık mı kontrol et
            botanik_acik = botanik_penceresi_acik_mi()

            screenshot_cb = tk.Checkbutton(
                screenshot_frame,
                text="Botanik Kasa Kapatma ekran görüntüsü ekle",
                variable=self.screenshot_var,
                font=("Arial", 10),
                bg='#FAFAFA',
                activebackground='#FAFAFA',
                state='normal' if botanik_acik else 'disabled'
            )
            screenshot_cb.pack(side="left")

            if not botanik_acik:
                tk.Label(
                    screenshot_frame,
                    text="(Botanik penceresi kapalı)",
                    font=("Arial", 9),
                    bg='#FAFAFA',
                    fg='#999999'
                ).pack(side="left", padx=5)

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
        screenshot_eklendi = False

        # Screenshot seçeneği işaretliyse önce ekran görüntüsü al
        if self.screenshot_var and self.screenshot_var.get():
            try:
                # Botanik penceresi screenshot'ı al
                dosya_yolu = kasa_kapatma_screenshot()
                if dosya_yolu:
                    # Clipboard'a kopyala
                    if screenshot_clipboard_kopyala(dosya_yolu):
                        screenshot_eklendi = True
                        logger.info("Botanik screenshot clipboard'a kopyalandı")
                    else:
                        logger.warning("Screenshot clipboard'a kopyalanamadı")
                else:
                    logger.warning("Screenshot alınamadı")
            except Exception as e:
                logger.error(f"Screenshot hatası: {e}")

        # WhatsApp mesajını gönder
        if self.whatsapp.rapor_gonder(self.kasa_verileri):
            # Screenshot eklendiyse bilgi ver
            if screenshot_eklendi:
                messagebox.showinfo(
                    "Ekran Görüntüsü Hazır",
                    "Botanik Kasa Kapatma ekran görüntüsü panoya kopyalandı!\n\n"
                    "WhatsApp'ta mesajı gönderdikten sonra\n"
                    "Ctrl+V ile resmi yapıştırabilirsiniz."
                )
            self.pencere.destroy()
