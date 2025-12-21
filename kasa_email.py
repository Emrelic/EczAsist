"""
Botanik Bot - Kasa E-Posta Modülü
Kasa kapatma raporlarını e-posta ile gönderme
PDF eki ve Botanik screenshot desteği
"""

import tkinter as tk
from tkinter import ttk, messagebox
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Ayar dosyası
EMAIL_AYAR_DOSYASI = os.path.join(os.path.dirname(__file__), "email_ayarlari.json")

# Önceden tanımlı SMTP sunucuları
SMTP_SUNUCULARI = {
    "Gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
    "Outlook/Hotmail": {"host": "smtp.office365.com", "port": 587, "tls": True},
    "Yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "tls": True},
    "Yandex": {"host": "smtp.yandex.com", "port": 587, "tls": True},
    "Özel SMTP": {"host": "", "port": 587, "tls": True}
}

# Varsayılan ayarlar
VARSAYILAN_AYARLAR = {
    "smtp_saglayici": "Gmail",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_tls": True,
    "gonderen_email": "",
    "gonderen_sifre": "",
    "alicilar": [],
    "konu_sablonu": "Kasa Raporu - {tarih}",
    "pdf_ekle": True,
    "screenshot_ekle": True,
    "otomatik_gonder": False
}


def email_ayarlarini_yukle() -> Dict:
    """E-posta ayarlarını JSON dosyasından yükle"""
    try:
        if os.path.exists(EMAIL_AYAR_DOSYASI):
            with open(EMAIL_AYAR_DOSYASI, 'r', encoding='utf-8') as f:
                ayarlar = json.load(f)
                # Eksik anahtarları varsayılanlarla doldur
                for key, value in VARSAYILAN_AYARLAR.items():
                    if key not in ayarlar:
                        ayarlar[key] = value
                return ayarlar
    except Exception as e:
        logger.error(f"E-posta ayarları yüklenemedi: {e}")
    return VARSAYILAN_AYARLAR.copy()


def email_ayarlarini_kaydet(ayarlar: Dict) -> bool:
    """E-posta ayarlarını JSON dosyasına kaydet"""
    try:
        with open(EMAIL_AYAR_DOSYASI, 'w', encoding='utf-8') as f:
            json.dump(ayarlar, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"E-posta ayarları kaydedilemedi: {e}")
        return False


class KasaEmailRapor:
    """E-posta ile kasa raporu gönderme"""

    def __init__(self, ayarlar: Dict = None):
        self.email_ayarlari = email_ayarlarini_yukle()
        self.kasa_ayarlari = ayarlar or {}

    def rapor_html_olustur(self, kasa_verileri: Dict) -> str:
        """Kasa verilerinden HTML e-posta içeriği oluştur"""
        gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
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

        # Düzeltilmiş hesaplamalar
        duz_nakit = nakit + masraf + silinen + alinan
        duz_toplam = duz_nakit + pos + iban

        # Farklar
        nakit_fark = duz_nakit - botanik_nakit
        pos_fark = pos - botanik_pos
        iban_fark = iban - botanik_iban
        genel_fark = duz_toplam - botanik_toplam

        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)

        def fmt(n):
            return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def fark_renk(n):
            if abs(n) < 0.01:
                return "#28a745", "0,00"  # Yeşil
            elif n > 0:
                return "#dc3545", f"+{fmt(n)}"  # Kırmızı (fazla)
            else:
                return "#dc3545", fmt(n)  # Kırmızı (eksik)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header .tarih {{
            margin-top: 5px;
            opacity: 0.9;
        }}
        .content {{
            padding: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        .money {{
            text-align: right;
            font-family: 'Consolas', monospace;
            font-weight: 500;
        }}
        .section-title {{
            background-color: #e9ecef;
            padding: 10px 12px;
            font-weight: bold;
            color: #495057;
            border-left: 4px solid #667eea;
        }}
        .highlight {{
            background-color: #fff3cd;
        }}
        .total-row {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .fark-table th {{
            text-align: center;
        }}
        .fark-table td {{
            text-align: right;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 15px 20px;
            text-align: center;
            color: #6c757d;
            font-size: 12px;
            border-top: 1px solid #eee;
        }}
        .ayrilan-box {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            border-radius: 8px;
        }}
        .ayrilan-box .label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .ayrilan-box .amount {{
            font-size: 32px;
            font-weight: bold;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Kasa Kapatma Raporu</h1>
            <div class="tarih">{gun}, {tarih} - {saat}</div>
        </div>

        <div class="content">
            <!-- Ana Veriler -->
            <table>
                <tr class="section-title">
                    <td colspan="2">Kasa Özeti</td>
                </tr>
                <tr>
                    <td>Başlangıç Kasası</td>
                    <td class="money">{fmt(baslangic)} TL</td>
                </tr>
                <tr>
                    <td>Nakit Toplam</td>
                    <td class="money">{fmt(nakit)} TL</td>
                </tr>
                <tr>
                    <td>POS Toplam</td>
                    <td class="money">{fmt(pos)} TL</td>
                </tr>
                <tr>
                    <td>IBAN Toplam</td>
                    <td class="money">{fmt(iban)} TL</td>
                </tr>
            </table>

            <!-- Düzeltmeler -->
            <table>
                <tr class="section-title">
                    <td colspan="2">Düzeltmeler</td>
                </tr>
                <tr>
                    <td>Masraflar (-)</td>
                    <td class="money">{fmt(masraf)} TL</td>
                </tr>
                <tr>
                    <td>Silinen Reçeteler (-)</td>
                    <td class="money">{fmt(silinen)} TL</td>
                </tr>
                <tr>
                    <td>Alınan Paralar (+)</td>
                    <td class="money">{fmt(alinan)} TL</td>
                </tr>
            </table>

            <!-- Sayım - Botanik Karşılaştırma -->
            <table class="fark-table">
                <tr class="section-title">
                    <td colspan="4">Sayım - Botanik Karşılaştırma</td>
                </tr>
                <tr>
                    <th></th>
                    <th>Sayım</th>
                    <th>Botanik</th>
                    <th>Fark</th>
                </tr>
                <tr>
                    <td style="text-align:left">Nakit</td>
                    <td class="money">{fmt(duz_nakit)}</td>
                    <td class="money">{fmt(botanik_nakit)}</td>
                    <td class="money" style="color:{fark_renk(nakit_fark)[0]}">{fark_renk(nakit_fark)[1]}</td>
                </tr>
                <tr>
                    <td style="text-align:left">POS</td>
                    <td class="money">{fmt(pos)}</td>
                    <td class="money">{fmt(botanik_pos)}</td>
                    <td class="money" style="color:{fark_renk(pos_fark)[0]}">{fark_renk(pos_fark)[1]}</td>
                </tr>
                <tr>
                    <td style="text-align:left">IBAN</td>
                    <td class="money">{fmt(iban)}</td>
                    <td class="money">{fmt(botanik_iban)}</td>
                    <td class="money" style="color:{fark_renk(iban_fark)[0]}">{fark_renk(iban_fark)[1]}</td>
                </tr>
                <tr class="total-row">
                    <td style="text-align:left"><strong>TOPLAM</strong></td>
                    <td class="money"><strong>{fmt(duz_toplam)}</strong></td>
                    <td class="money"><strong>{fmt(botanik_toplam)}</strong></td>
                    <td class="money" style="color:{fark_renk(genel_fark)[0]}"><strong>{fark_renk(genel_fark)[1]}</strong></td>
                </tr>
            </table>

            <!-- Sonuç -->
            <table>
                <tr>
                    <td>Ertesi Gün Kasası</td>
                    <td class="money">{fmt(ertesi_gun)} TL</td>
                </tr>
            </table>

            <div class="ayrilan-box">
                <div class="label">AYRILAN PARA</div>
                <div class="amount">{fmt(ayrilan)} TL</div>
            </div>
        </div>

        <div class="footer">
            Bu rapor otomatik olarak oluşturulmuştur.<br>
            Botanik Kasa Takip Sistemi - {datetime.now().strftime("%d.%m.%Y %H:%M")}
        </div>
    </div>
</body>
</html>
"""
        return html

    def rapor_text_olustur(self, kasa_verileri: Dict) -> str:
        """Düz metin rapor oluştur (HTML desteklemeyen istemciler için)"""
        gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        gun = gun_isimleri[datetime.now().weekday()]
        tarih = datetime.now().strftime("%d/%m/%Y")
        saat = datetime.now().strftime("%H:%M")

        baslangic = kasa_verileri.get('baslangic_kasasi', 0)
        nakit = kasa_verileri.get('nakit_toplam', 0)
        pos = kasa_verileri.get('pos_toplam', 0)
        iban = kasa_verileri.get('iban_toplam', 0)
        ertesi_gun = kasa_verileri.get('ertesi_gun_kasasi', 0)
        ayrilan = kasa_verileri.get('ayrilan_para', 0)

        def fmt(n):
            return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        text = f"""
KASA KAPATMA RAPORU
{gun}, {tarih} - {saat}
{'=' * 40}

KASA ÖZETİ
-----------
Başlangıç Kasası: {fmt(baslangic)} TL
Nakit Toplam:     {fmt(nakit)} TL
POS Toplam:       {fmt(pos)} TL
IBAN Toplam:      {fmt(iban)} TL

SONUÇ
------
Ertesi Gün Kasası: {fmt(ertesi_gun)} TL
AYRILAN PARA:      {fmt(ayrilan)} TL

{'=' * 40}
Bu rapor otomatik olarak oluşturulmuştur.
Botanik Kasa Takip Sistemi
"""
        return text

    def email_gonder(self, kasa_verileri: Dict, alicilar: List[str] = None,
                     pdf_dosyasi: str = None, screenshot_dosyasi: str = None) -> tuple:
        """
        E-posta gönder

        Returns:
            (basarili: bool, mesaj: str)
        """
        ayarlar = self.email_ayarlari

        # Gönderen bilgilerini kontrol et
        if not ayarlar.get('gonderen_email') or not ayarlar.get('gonderen_sifre'):
            return False, "E-posta ayarları yapılandırılmamış!\nAyarlar > E-posta Ayarları bölümünden yapılandırın."

        # Alıcıları belirle
        if alicilar is None:
            alicilar = ayarlar.get('alicilar', [])

        if not alicilar:
            return False, "Alıcı e-posta adresi belirtilmemiş!"

        try:
            # E-posta oluştur
            msg = MIMEMultipart('alternative')

            # Konu
            tarih = datetime.now().strftime("%d.%m.%Y")
            konu = ayarlar.get('konu_sablonu', 'Kasa Raporu - {tarih}').format(tarih=tarih)
            msg['Subject'] = konu
            msg['From'] = ayarlar['gonderen_email']
            msg['To'] = ', '.join(alicilar)

            # Metin ve HTML içerik
            text_content = self.rapor_text_olustur(kasa_verileri)
            html_content = self.rapor_html_olustur(kasa_verileri)

            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')

            msg.attach(part1)
            msg.attach(part2)

            # PDF eki
            if pdf_dosyasi and os.path.exists(pdf_dosyasi):
                with open(pdf_dosyasi, 'rb') as f:
                    pdf_part = MIMEBase('application', 'pdf')
                    pdf_part.set_payload(f.read())
                    encoders.encode_base64(pdf_part)
                    pdf_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="Kasa_Raporu_{tarih.replace(".", "_")}.pdf"'
                    )
                    msg.attach(pdf_part)

            # Screenshot eki
            if screenshot_dosyasi and os.path.exists(screenshot_dosyasi):
                with open(screenshot_dosyasi, 'rb') as f:
                    img_part = MIMEBase('image', 'png')
                    img_part.set_payload(f.read())
                    encoders.encode_base64(img_part)
                    img_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="Botanik_Screenshot_{tarih.replace(".", "_")}.png"'
                    )
                    msg.attach(img_part)

            # SMTP bağlantısı ve gönderim
            smtp_host = ayarlar.get('smtp_host', 'smtp.gmail.com')
            smtp_port = ayarlar.get('smtp_port', 587)
            use_tls = ayarlar.get('smtp_tls', True)

            context = ssl.create_default_context()

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if use_tls:
                    server.starttls(context=context)
                server.login(ayarlar['gonderen_email'], ayarlar['gonderen_sifre'])
                server.sendmail(
                    ayarlar['gonderen_email'],
                    alicilar,
                    msg.as_string()
                )

            logger.info(f"E-posta gönderildi: {', '.join(alicilar)}")
            return True, f"E-posta başarıyla gönderildi!\nAlıcılar: {', '.join(alicilar)}"

        except smtplib.SMTPAuthenticationError:
            return False, "Kimlik doğrulama hatası!\n\nGmail kullanıyorsanız:\n1. Google Hesabı > Güvenlik > 2 Adımlı Doğrulama açık olmalı\n2. Uygulama Şifreleri bölümünden özel şifre oluşturun"
        except smtplib.SMTPException as e:
            return False, f"SMTP hatası: {str(e)}"
        except Exception as e:
            logger.error(f"E-posta gönderme hatası: {e}")
            return False, f"E-posta gönderilemedi:\n{str(e)}"


class EmailAyarPenceresi:
    """E-posta ayarları penceresi"""

    def __init__(self, parent):
        self.parent = parent
        self.pencere = None
        self.ayarlar = email_ayarlarini_yukle()

    def goster(self):
        """Ayarlar penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("E-posta Ayarları")
        self.pencere.geometry("480x550")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#f0f0f0')
        self.pencere.resizable(True, True)
        self.pencere.minsize(450, 500)

        # Pencereyi ekranın ortasına konumlandır
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 480) // 2
        y = (self.pencere.winfo_screenheight() - 550) // 2
        self.pencere.geometry(f"480x550+{x}+{y}")

        # === BAŞLIK ===
        baslik_frame = tk.Frame(self.pencere, bg='#667eea', height=45)
        baslik_frame.pack(fill='x')
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="E-posta Ayarları",
            font=('Arial', 13, 'bold'),
            bg='#667eea',
            fg='white'
        ).pack(expand=True)

        # === İÇERİK ===
        main_frame = tk.Frame(self.pencere, bg='#f0f0f0', padx=15, pady=10)
        main_frame.pack(fill='both', expand=True)

        # SMTP Sağlayıcı
        smtp_frame = tk.LabelFrame(main_frame, text="SMTP Sunucu", bg='#f0f0f0', padx=8, pady=5)
        smtp_frame.pack(fill='x', pady=3)

        row1 = tk.Frame(smtp_frame, bg='#f0f0f0')
        row1.pack(fill='x', pady=2)
        tk.Label(row1, text="Sağlayıcı:", bg='#f0f0f0', width=10, anchor='w').pack(side='left')
        self.saglayici_var = tk.StringVar(value=self.ayarlar.get('smtp_saglayici', 'Gmail'))
        saglayici_combo = ttk.Combobox(row1, textvariable=self.saglayici_var, values=list(SMTP_SUNUCULARI.keys()), state='readonly', width=22)
        saglayici_combo.pack(side='left', padx=5)
        saglayici_combo.bind('<<ComboboxSelected>>', self.saglayici_degisti)

        row2 = tk.Frame(smtp_frame, bg='#f0f0f0')
        row2.pack(fill='x', pady=2)
        tk.Label(row2, text="SMTP Host:", bg='#f0f0f0', width=10, anchor='w').pack(side='left')
        self.host_var = tk.StringVar(value=self.ayarlar.get('smtp_host', 'smtp.gmail.com'))
        tk.Entry(row2, textvariable=self.host_var, width=25).pack(side='left', padx=5)

        row3 = tk.Frame(smtp_frame, bg='#f0f0f0')
        row3.pack(fill='x', pady=2)
        tk.Label(row3, text="Port:", bg='#f0f0f0', width=10, anchor='w').pack(side='left')
        self.port_var = tk.StringVar(value=str(self.ayarlar.get('smtp_port', 587)))
        tk.Entry(row3, textvariable=self.port_var, width=8).pack(side='left', padx=5)

        # Gönderen Bilgileri
        gonderen_frame = tk.LabelFrame(main_frame, text="Gönderen Bilgileri", bg='#f0f0f0', padx=8, pady=5)
        gonderen_frame.pack(fill='x', pady=5)

        row4 = tk.Frame(gonderen_frame, bg='#f0f0f0')
        row4.pack(fill='x', pady=2)
        tk.Label(row4, text="E-posta:", bg='#f0f0f0', width=10, anchor='w').pack(side='left')
        self.email_var = tk.StringVar(value=self.ayarlar.get('gonderen_email', ''))
        tk.Entry(row4, textvariable=self.email_var, width=30).pack(side='left', padx=5)

        row5 = tk.Frame(gonderen_frame, bg='#f0f0f0')
        row5.pack(fill='x', pady=2)
        tk.Label(row5, text="Şifre:", bg='#f0f0f0', width=10, anchor='w').pack(side='left')
        self.sifre_var = tk.StringVar(value=self.ayarlar.get('gonderen_sifre', ''))
        tk.Entry(row5, textvariable=self.sifre_var, show='*', width=30).pack(side='left', padx=5)

        # Gmail yardım
        yardim_row = tk.Frame(gonderen_frame, bg='#f0f0f0')
        yardim_row.pack(fill='x', pady=3)
        tk.Label(yardim_row, text="Gmail için Uygulama Şifresi gerekli", font=('Arial', 8), fg='#666', bg='#f0f0f0').pack(side='left', padx=5)
        tk.Button(yardim_row, text="Nasıl Yapılır?", font=('Arial', 8), bg='#ffc107', command=self.gmail_yardim_goster, cursor='hand2', padx=5).pack(side='left', padx=5)

        # Alıcılar
        alici_frame = tk.LabelFrame(main_frame, text="Alıcılar (her satıra bir e-posta)", bg='#f0f0f0', padx=8, pady=5)
        alici_frame.pack(fill='x', pady=5)
        self.alici_text = tk.Text(alici_frame, height=3, width=40)
        self.alici_text.pack(fill='x', pady=3)
        self.alici_text.insert('1.0', '\n'.join(self.ayarlar.get('alicilar', [])))

        # Konu Şablonu
        konu_frame = tk.LabelFrame(main_frame, text="E-posta Konusu", bg='#f0f0f0', padx=8, pady=5)
        konu_frame.pack(fill='x', pady=5)
        self.konu_var = tk.StringVar(value=self.ayarlar.get('konu_sablonu', 'Kasa Raporu - {tarih}'))
        tk.Entry(konu_frame, textvariable=self.konu_var, width=40).pack(fill='x', pady=3)
        tk.Label(konu_frame, text="{tarih} = Günün tarihi", font=('Arial', 8), fg='#666', bg='#f0f0f0').pack(anchor='w')

        # Seçenekler
        self.screenshot_var = tk.BooleanVar(value=self.ayarlar.get('screenshot_ekle', True))
        tk.Checkbutton(main_frame, text="Botanik ekran görüntüsünü e-postaya ekle", variable=self.screenshot_var, bg='#f0f0f0').pack(anchor='w', pady=5)

        # === BUTONLAR ===
        buton_frame = tk.Frame(self.pencere, bg='#e0e0e0', pady=12)
        buton_frame.pack(fill='x', side='bottom')

        tk.Button(
            buton_frame,
            text="Test Gönder",
            command=self.test_gonder,
            bg='#17a2b8',
            fg='white',
            font=('Arial', 10),
            width=12,
            cursor='hand2'
        ).pack(side='left', padx=15)

        tk.Button(
            buton_frame,
            text="KAYDET",
            command=self.kaydet,
            bg='#28a745',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12,
            cursor='hand2'
        ).pack(side='right', padx=15)

        tk.Button(
            buton_frame,
            text="İptal",
            command=self.pencere.destroy,
            bg='#6c757d',
            fg='white',
            font=('Arial', 10),
            width=10,
            cursor='hand2'
        ).pack(side='right', padx=5)

    def saglayici_degisti(self, event=None):
        """SMTP sağlayıcı değiştiğinde ayarları güncelle"""
        saglayici = self.saglayici_var.get()
        if saglayici in SMTP_SUNUCULARI:
            ayar = SMTP_SUNUCULARI[saglayici]
            self.host_var.set(ayar['host'])
            self.port_var.set(str(ayar['port']))

    def gmail_yardim_goster(self):
        """Gmail uygulama şifresi nasıl alınır açıklaması"""
        yardim_pencere = tk.Toplevel(self.pencere)
        yardim_pencere.title("Gmail Uygulama Şifresi Nasıl Alınır?")
        yardim_pencere.geometry("550x500")
        yardim_pencere.transient(self.pencere)
        yardim_pencere.configure(bg='white')

        # Başlık
        baslik_frame = tk.Frame(yardim_pencere, bg='#4285f4', height=50)
        baslik_frame.pack(fill='x')
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="Gmail Uygulama Şifresi Kurulumu",
            font=('Arial', 13, 'bold'),
            bg='#4285f4',
            fg='white'
        ).pack(expand=True)

        # İçerik
        content = tk.Frame(yardim_pencere, bg='white', padx=25, pady=20)
        content.pack(fill='both', expand=True)

        yardim_metni = """
Gmail ile e-posta göndermek için normal şifrenizi kullanamazsınız.
Google güvenlik politikası gereği "Uygulama Şifresi" oluşturmanız gerekir.

ADIM 1: 2 Adımlı Doğrulamayı Açın
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Google Hesabınıza giriş yapın
• Güvenlik bölümüne gidin
• "2 Adımlı Doğrulama" seçeneğini açın
• Telefon numaranızı doğrulayın

ADIM 2: Uygulama Şifresi Oluşturun
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Google Hesabı > Güvenlik bölümüne gidin
• "Uygulama Şifreleri" seçeneğine tıklayın
  (2FA açık değilse bu seçenek görünmez!)
• Uygulama olarak "Posta" seçin
• Cihaz olarak "Windows Bilgisayar" seçin
• "Oluştur" butonuna tıklayın

ADIM 3: Şifreyi Kopyalayın
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 16 karakterlik sarı kutudaki şifreyi kopyalayın
• Bu şifreyi bu programdaki "Şifre" alanına yapıştırın
• NOT: Şifre boşluksuz 16 karakterdir (xxxx xxxx xxxx xxxx)

ÖNEMLİ NOTLAR:
• Bu şifre sadece bir kez gösterilir
• Şifreyi güvenli bir yere kaydedin
• Her uygulama için ayrı şifre oluşturabilirsiniz
"""

        text_widget = tk.Text(
            content,
            wrap='word',
            font=('Consolas', 10),
            bg='#f8f9fa',
            relief='flat',
            padx=15,
            pady=15
        )
        text_widget.pack(fill='both', expand=True)
        text_widget.insert('1.0', yardim_metni)
        text_widget.config(state='disabled')

        # Google hesap linki
        link_frame = tk.Frame(yardim_pencere, bg='white', pady=10)
        link_frame.pack(fill='x')

        def google_hesap_ac():
            import webbrowser
            webbrowser.open('https://myaccount.google.com/security')

        tk.Button(
            link_frame,
            text="Google Hesap Güvenlik Sayfasını Aç",
            font=('Arial', 10, 'bold'),
            bg='#4285f4',
            fg='white',
            command=google_hesap_ac,
            cursor='hand2',
            padx=15,
            pady=8
        ).pack()

        # Kapat butonu
        tk.Button(
            yardim_pencere,
            text="Kapat",
            command=yardim_pencere.destroy,
            bg='#6c757d',
            fg='white',
            width=15,
            pady=5
        ).pack(pady=15)

    def kaydet(self):
        """Ayarları kaydet"""
        alicilar = [a.strip() for a in self.alici_text.get('1.0', 'end').split('\n') if a.strip()]

        self.ayarlar = {
            'smtp_saglayici': self.saglayici_var.get(),
            'smtp_host': self.host_var.get(),
            'smtp_port': int(self.port_var.get()),
            'smtp_tls': True,
            'gonderen_email': self.email_var.get(),
            'gonderen_sifre': self.sifre_var.get(),
            'alicilar': alicilar,
            'konu_sablonu': self.konu_var.get(),
            'screenshot_ekle': self.screenshot_var.get()
        }

        if email_ayarlarini_kaydet(self.ayarlar):
            messagebox.showinfo("Başarılı", "E-posta ayarları kaydedildi!")
            self.pencere.destroy()
        else:
            messagebox.showerror("Hata", "Ayarlar kaydedilemedi!")

    def test_gonder(self):
        """Test e-postası gönder"""
        # Önce ayarları geçici olarak güncelle
        alicilar = [a.strip() for a in self.alici_text.get('1.0', 'end').split('\n') if a.strip()]

        test_ayarlar = {
            'smtp_host': self.host_var.get(),
            'smtp_port': int(self.port_var.get()),
            'smtp_tls': True,
            'gonderen_email': self.email_var.get(),
            'gonderen_sifre': self.sifre_var.get(),
            'alicilar': alicilar,
            'konu_sablonu': 'TEST - ' + self.konu_var.get()
        }

        if not test_ayarlar['gonderen_email'] or not test_ayarlar['gonderen_sifre']:
            messagebox.showwarning("Uyarı", "Gönderen e-posta ve şifre gerekli!")
            return

        if not alicilar:
            messagebox.showwarning("Uyarı", "En az bir alıcı e-posta adresi gerekli!")
            return

        # Test verisi
        test_verileri = {
            'baslangic_kasasi': 1000,
            'nakit_toplam': 5000,
            'pos_toplam': 3000,
            'iban_toplam': 500,
            'masraf_toplam': 200,
            'silinen_toplam': 100,
            'alinan_toplam': 50,
            'botanik_nakit': 4950,
            'botanik_pos': 3000,
            'botanik_iban': 500,
            'botanik_toplam': 8450,
            'ertesi_gun_kasasi': 1000,
            'ayrilan_para': 7350
        }

        email_rapor = KasaEmailRapor()
        email_rapor.email_ayarlari = test_ayarlar

        basarili, mesaj = email_rapor.email_gonder(test_verileri, alicilar)

        if basarili:
            messagebox.showinfo("Başarılı", "Test e-postası gönderildi!\nLütfen gelen kutunuzu kontrol edin.")
        else:
            messagebox.showerror("Hata", mesaj)


class KasaEmailPenceresi:
    """E-posta gönderme penceresi (WhatsApp benzeri)"""

    def __init__(self, parent, kasa_verileri: Dict):
        self.parent = parent
        self.kasa_verileri = kasa_verileri
        self.email_rapor = KasaEmailRapor()
        self.pencere = None

    def goster(self):
        """E-posta gönderme penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("E-posta ile Rapor Gönder")
        self.pencere.geometry("500x450")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#FAFAFA')

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#667eea', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="E-posta Kasa Raporu",
            font=("Arial", 14, "bold"),
            bg='#667eea',
            fg='white'
        ).pack(expand=True)

        # İçerik
        content_frame = tk.Frame(self.pencere, bg='#FAFAFA', padx=20, pady=15)
        content_frame.pack(fill='both', expand=True)

        # Alıcı bilgisi
        ayarlar = email_ayarlarini_yukle()
        alicilar = ayarlar.get('alicilar', [])

        tk.Label(
            content_frame,
            text="Alıcılar:",
            font=("Arial", 10, "bold"),
            bg='#FAFAFA'
        ).pack(anchor='w')

        alici_text = ', '.join(alicilar) if alicilar else "Ayarlanmamış"
        alici_renk = '#28a745' if alicilar else '#dc3545'

        tk.Label(
            content_frame,
            text=alici_text,
            font=("Arial", 10),
            bg='#FAFAFA',
            fg=alici_renk,
            wraplength=400
        ).pack(anchor='w', pady=(0, 15))

        # Özet bilgi
        ozet_frame = tk.LabelFrame(content_frame, text="Rapor Özeti", bg='#FAFAFA', padx=10, pady=10)
        ozet_frame.pack(fill='x', pady=10)

        def fmt(n):
            return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        ayrilan = self.kasa_verileri.get('ayrilan_para', 0)
        nakit = self.kasa_verileri.get('nakit_toplam', 0)
        pos = self.kasa_verileri.get('pos_toplam', 0)

        tk.Label(ozet_frame, text=f"Nakit: {fmt(nakit)} TL", bg='#FAFAFA').pack(anchor='w')
        tk.Label(ozet_frame, text=f"POS: {fmt(pos)} TL", bg='#FAFAFA').pack(anchor='w')
        tk.Label(
            ozet_frame,
            text=f"Ayrılan Para: {fmt(ayrilan)} TL",
            font=("Arial", 11, "bold"),
            bg='#FAFAFA',
            fg='#28a745'
        ).pack(anchor='w', pady=(10, 0))

        # Screenshot seçeneği
        self.screenshot_var = tk.BooleanVar(value=ayarlar.get('screenshot_ekle', True))
        tk.Checkbutton(
            content_frame,
            text="Botanik ekran görüntüsünü ekle",
            variable=self.screenshot_var,
            bg='#FAFAFA'
        ).pack(anchor='w', pady=15)

        # Butonlar
        buton_frame = tk.Frame(self.pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill='x')

        tk.Button(
            buton_frame,
            text="Ayarlar",
            font=("Arial", 10),
            bg='#6c757d',
            fg='white',
            width=12,
            cursor='hand2',
            command=self.ayarlari_ac
        ).pack(side='left', padx=20)

        tk.Button(
            buton_frame,
            text="E-posta Gönder",
            font=("Arial", 11, "bold"),
            bg='#667eea',
            fg='white',
            width=15,
            cursor='hand2',
            command=self.gonder
        ).pack(side='right', padx=20)

    def ayarlari_ac(self):
        """Ayarlar penceresini aç"""
        EmailAyarPenceresi(self.pencere).goster()

    def gonder(self):
        """E-postayı gönder"""
        screenshot_dosyasi = None

        # Screenshot eklenecekse al
        if self.screenshot_var.get():
            try:
                from botanik_veri_cek import kasa_kapatma_screenshot
                screenshot_dosyasi = kasa_kapatma_screenshot()
            except Exception as e:
                logger.warning(f"Screenshot alınamadı: {e}")

        # E-posta gönder
        basarili, mesaj = self.email_rapor.email_gonder(
            self.kasa_verileri,
            screenshot_dosyasi=screenshot_dosyasi
        )

        if basarili:
            messagebox.showinfo("Başarılı", mesaj)
            self.pencere.destroy()
        else:
            messagebox.showerror("Hata", mesaj)


# Test için
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    # Ayarlar penceresini test et
    EmailAyarPenceresi(root).goster()

    root.mainloop()
