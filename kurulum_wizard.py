# -*- coding: utf-8 -*-
"""
BotanikTakip Kurulum Sihirbazi
6 adimli kurulum wizard - Tkinter tabanli
"""

import os
import sys
import json
import socket
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Dizin ve dosya yollari
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG_PATH = os.path.join(SCRIPT_DIR, "db_config.json")
MEDULA_SETTINGS_PATH = os.path.join(SCRIPT_DIR, "medula_settings.json")


class KurulumWizard:
    """BotanikTakip kurulum sihirbazi ana sinifi"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BotanikTakip Kurulum Sihirbazi")
        self.root.geometry("700x550")
        self.root.resizable(False, False)

        # Adim takibi
        self.mevcut_adim = 0
        self.toplam_adim = 6
        self.adim_basliklar = [
            "Hos Geldiniz",
            "Python Gereksinimleri",
            "SQL Server Bulma",
            "Veritabani Baglantisi",
            "Botanik EOS Ayarlari",
            "Kurulum Tamamlandi"
        ]

        # Degiskenler
        self.db_server = tk.StringVar(value="")
        self.db_name = tk.StringVar(value="eczane")
        self.db_user = tk.StringVar(value="sa")
        self.db_password = tk.StringVar(value="")
        self.trusted_connection = tk.BooleanVar(value=False)
        self.botanik_exe_path = tk.StringVar(value=r"C:\BotanikEczane\BotanikMedula.exe")

        # Bulunan sunucular listesi
        self.bulunan_sunucular = []

        # Ana cerceve olustur
        self._arayuz_olustur()

        # Ilk adimi goster
        self._adim_goster(0)

    def _arayuz_olustur(self):
        """Ana arayuz elemanlarini olustur"""
        # Ust baslik alani (koyu mavi)
        self.baslik_frame = tk.Frame(self.root, bg="#2c3e50", height=70)
        self.baslik_frame.pack(fill="x")
        self.baslik_frame.pack_propagate(False)

        self.baslik_label = tk.Label(
            self.baslik_frame,
            text="BotanikTakip Kurulum Sihirbazi",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        self.baslik_label.pack(pady=(10, 0))

        self.adim_label = tk.Label(
            self.baslik_frame,
            text="Adim 1 / 6 - Hos Geldiniz",
            font=("Segoe UI", 10),
            fg="#bdc3c7",
            bg="#2c3e50"
        )
        self.adim_label.pack()

        # Icerik alani
        self.icerik_frame = tk.Frame(self.root, padx=20, pady=10)
        self.icerik_frame.pack(fill="both", expand=True)

        # Alt buton alani
        self.buton_frame = tk.Frame(self.root, padx=20, pady=10)
        self.buton_frame.pack(fill="x", side="bottom")

        # Ayirici cizgi
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", side="bottom")

        # Navigasyon butonlari
        self.geri_btn = tk.Button(
            self.buton_frame, text="< Geri", width=10,
            command=self._geri_git
        )
        self.geri_btn.pack(side="left")

        self.iptal_btn = tk.Button(
            self.buton_frame, text="Iptal", width=10,
            command=self._iptal
        )
        self.iptal_btn.pack(side="left", padx=10)

        self.ileri_btn = tk.Button(
            self.buton_frame, text="Ileri >", width=10,
            command=self._ileri_git
        )
        self.ileri_btn.pack(side="right")

    def _icerik_temizle(self):
        """Icerik alanindaki tum widget'lari temizle"""
        for widget in self.icerik_frame.winfo_children():
            widget.destroy()

    def _adim_goster(self, adim):
        """Belirtilen adimi goster"""
        self.mevcut_adim = adim

        # Baslik guncelle
        self.adim_label.config(
            text="Adim {0} / {1} - {2}".format(
                adim + 1, self.toplam_adim, self.adim_basliklar[adim]
            )
        )

        # Buton durumlarini guncelle
        if adim == 0:
            self.geri_btn.config(state="disabled")
        else:
            self.geri_btn.config(state="normal")

        if adim == self.toplam_adim - 1:
            self.ileri_btn.config(text="Bitir")
        else:
            self.ileri_btn.config(text="Ileri >")

        # Icerik temizle ve yeni adimi goster
        self._icerik_temizle()

        adim_fonksiyonlar = {
            0: self._adim_hosgeldiniz,
            1: self._adim_gereksinimler,
            2: self._adim_sql_bul,
            3: self._adim_db_baglanti,
            4: self._adim_botanik_eos,
            5: self._adim_tamamlandi,
        }

        fonksiyon = adim_fonksiyonlar.get(adim)
        if fonksiyon:
            fonksiyon()

    # =========================================================================
    # ADIM 0 - Hos Geldiniz
    # =========================================================================
    def _adim_hosgeldiniz(self):
        """Karsilama ekrani"""
        tk.Label(
            self.icerik_frame,
            text="BotanikTakip Kurulum Sihirbazina\nHos Geldiniz!",
            font=("Segoe UI", 18, "bold"),
            fg="#2c3e50",
            justify="center"
        ).pack(pady=(40, 20))

        tk.Label(
            self.icerik_frame,
            text=(
                "Bu sihirbaz asagidaki islemleri adim adim gerceklestirecektir:\n\n"
                "  1. Python gereksinimlerinin yuklenmesi\n"
                "  2. Agdaki SQL Server'in bulunmasi\n"
                "  3. Veritabani baglanti ayarlarinin yapilmasi\n"
                "  4. Botanik EOS program yolunun belirlenmesi\n"
                "  5. Medula ayarlarinin yapilandirilmasi\n\n"
                "Devam etmek icin 'Ileri' butonuna tiklayiniz."
            ),
            font=("Segoe UI", 11),
            justify="left",
            wraplength=600
        ).pack(pady=10)

    # =========================================================================
    # ADIM 1 - Python Gereksinimleri
    # =========================================================================
    def _adim_gereksinimler(self):
        """Python paket yukleme ekrani"""
        tk.Label(
            self.icerik_frame,
            text="Python Gereksinimlerinin Yuklenmesi",
            font=("Segoe UI", 14, "bold"),
            fg="#2c3e50"
        ).pack(pady=(5, 10))

        tk.Label(
            self.icerik_frame,
            text="Gerekli Python paketleri yuklenecektir. Bu islem birkac dakika surebilir.",
            font=("Segoe UI", 10),
            wraplength=600
        ).pack(pady=(0, 10))

        # Log alani - koyu arka plan, yesil yazi
        self.req_log = tk.Text(
            self.icerik_frame,
            height=16,
            bg="#1e1e1e",
            fg="#00ff00",
            font=("Consolas", 9),
            wrap="word",
            state="disabled"
        )
        self.req_log.pack(fill="both", expand=True, pady=(0, 10))

        # Yukle butonu
        self.yukle_btn = tk.Button(
            self.icerik_frame,
            text="Gereksinimleri Yukle",
            font=("Segoe UI", 10, "bold"),
            bg="#27ae60",
            fg="white",
            command=self._gereksinimleri_yukle
        )
        self.yukle_btn.pack()

    def _req_log_ekle(self, mesaj):
        """Log alanina mesaj ekle (thread-safe)"""
        def _ekle():
            self.req_log.config(state="normal")
            self.req_log.insert("end", mesaj + "\n")
            self.req_log.see("end")
            self.req_log.config(state="disabled")
        self.root.after(0, _ekle)

    def _gereksinimleri_yukle(self):
        """Gereksinimleri arka planda yukle"""
        self.yukle_btn.config(state="disabled", text="Yukleniyor...")

        def _yukle_thread():
            python_exe = sys.executable

            # pip guncelle
            self._req_log_ekle(">>> pip guncelleniyor...")
            try:
                sonuc = subprocess.run(
                    [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
                    capture_output=True, text=True, timeout=120
                )
                cikti = sonuc.stdout.strip() if sonuc.stdout else "pip guncel."
                self._req_log_ekle(cikti)
                if sonuc.returncode != 0 and sonuc.stderr:
                    self._req_log_ekle("UYARI: " + sonuc.stderr.strip())
            except Exception as e:
                self._req_log_ekle("pip guncelleme hatasi: {0}".format(str(e)))

            # Ekstra paketler
            ekstra_paketler = ["pyodbc", "openpyxl", "matplotlib", "tksheet"]
            for paket in ekstra_paketler:
                self._req_log_ekle("\n>>> {0} yukleniyor...".format(paket))
                try:
                    sonuc = subprocess.run(
                        [python_exe, "-m", "pip", "install", paket],
                        capture_output=True, text=True, timeout=120
                    )
                    if sonuc.returncode == 0:
                        cikti = sonuc.stdout.strip() if sonuc.stdout else ""
                        if "already satisfied" in cikti.lower():
                            self._req_log_ekle("{0} zaten yuklu.".format(paket))
                        else:
                            self._req_log_ekle("{0} basariyla yuklendi.".format(paket))
                    else:
                        self._req_log_ekle("HATA: {0}".format(
                            sonuc.stderr.strip() if sonuc.stderr else "Bilinmeyen hata"
                        ))
                except Exception as e:
                    self._req_log_ekle("{0} yukleme hatasi: {1}".format(paket, str(e)))

            # requirements.txt dosyasindan yukle
            req_dosya = os.path.join(SCRIPT_DIR, "requirements.txt")
            if os.path.exists(req_dosya):
                self._req_log_ekle("\n>>> requirements.txt dosyasindan yukleme yapiliyor...")
                try:
                    sonuc = subprocess.run(
                        [python_exe, "-m", "pip", "install", "-r", req_dosya],
                        capture_output=True, text=True, timeout=300
                    )
                    if sonuc.returncode == 0:
                        self._req_log_ekle("requirements.txt basariyla yuklendi.")
                    else:
                        self._req_log_ekle("UYARI: {0}".format(
                            sonuc.stderr.strip() if sonuc.stderr else "Bilinmeyen hata"
                        ))
                except Exception as e:
                    self._req_log_ekle("requirements.txt hatasi: {0}".format(str(e)))
            else:
                self._req_log_ekle("\nrequirements.txt bulunamadi, atlaniyor.")

            self._req_log_ekle("\n--- Yukleme islemi tamamlandi ---")
            self.root.after(0, lambda: self.yukle_btn.config(
                state="normal", text="Tamamlandi", bg="#2ecc71"
            ))

        thread = threading.Thread(target=_yukle_thread, daemon=True)
        thread.start()

    # =========================================================================
    # ADIM 2 - SQL Server Bulma
    # =========================================================================
    def _adim_sql_bul(self):
        """Agdaki SQL Server'i otomatik bul"""
        tk.Label(
            self.icerik_frame,
            text="SQL Server Otomatik Bulma",
            font=("Segoe UI", 14, "bold"),
            fg="#2c3e50"
        ).pack(pady=(5, 10))

        tk.Label(
            self.icerik_frame,
            text="Yerel agdaki SQL Server sunucularini taramak icin 'Taramayi Baslat' butonuna tiklayiniz.",
            font=("Segoe UI", 10),
            wraplength=600
        ).pack(pady=(0, 10))

        # Tarama log alani
        self.scan_log = tk.Text(
            self.icerik_frame,
            height=12,
            bg="#1e1e1e",
            fg="#00ff00",
            font=("Consolas", 9),
            wrap="word",
            state="disabled"
        )
        self.scan_log.pack(fill="both", expand=True, pady=(0, 10))

        # Tarama butonu
        btn_frame = tk.Frame(self.icerik_frame)
        btn_frame.pack(fill="x", pady=(0, 5))

        self.tara_btn = tk.Button(
            btn_frame,
            text="Taramayi Baslat",
            font=("Segoe UI", 10, "bold"),
            bg="#3498db",
            fg="white",
            command=self._sql_tarama_baslat
        )
        self.tara_btn.pack(side="left")

        # Sunucu adresi girisi
        sonuc_frame = tk.Frame(self.icerik_frame)
        sonuc_frame.pack(fill="x")

        tk.Label(
            sonuc_frame,
            text="SQL Server Adresi:",
            font=("Segoe UI", 10)
        ).pack(side="left")

        tk.Entry(
            sonuc_frame,
            textvariable=self.db_server,
            font=("Consolas", 10),
            width=40
        ).pack(side="left", padx=(10, 0))

    def _scan_log_ekle(self, mesaj):
        """Tarama log alanina mesaj ekle (thread-safe)"""
        def _ekle():
            self.scan_log.config(state="normal")
            self.scan_log.insert("end", mesaj + "\n")
            self.scan_log.see("end")
            self.scan_log.config(state="disabled")
        self.root.after(0, _ekle)

    def _sql_tarama_baslat(self):
        """SQL Server taramasini baslat"""
        self.tara_btn.config(state="disabled", text="Taraniyor...")
        self.bulunan_sunucular = []

        def _tarama_thread():
            # Yerel IP'yi bul
            yerel_ip = ""
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                yerel_ip = s.getsockname()[0]
                s.close()
                self._scan_log_ekle("Yerel IP: {0}".format(yerel_ip))
            except Exception as e:
                self._scan_log_ekle("Yerel IP bulunamadi: {0}".format(str(e)))
                self.root.after(0, lambda: self.tara_btn.config(
                    state="normal", text="Taramayi Baslat"
                ))
                return

            # Subnet hesapla
            ip_parcalar = yerel_ip.rsplit(".", 1)
            subnet = ip_parcalar[0]
            self._scan_log_ekle("Taranan subnet: {0}.1-254".format(subnet))
            self._scan_log_ekle("Port 1433 taraniyor...\n")

            # Localhost kontrolu
            self._port_kontrol("127.0.0.1", 1433)

            # Paralel tarama - subnet uzerindeki tum IP'ler
            tarama_threadleri = []
            for i in range(1, 255):
                ip = "{0}.{1}".format(subnet, i)
                t = threading.Thread(
                    target=self._port_kontrol, args=(ip, 1433), daemon=True
                )
                tarama_threadleri.append(t)
                t.start()

            # Tum threadlerin bitmesini bekle
            for t in tarama_threadleri:
                t.join(timeout=3)

            # Sonuclari raporla
            if self.bulunan_sunucular:
                self._scan_log_ekle("\n--- Bulunan sunucular ---")
                for sunucu in self.bulunan_sunucular:
                    self._scan_log_ekle("  {0}".format(sunucu))
                # Ilk bulunan sunucuyu otomatik sec
                ilk_sunucu = self.bulunan_sunucular[0]
                self.root.after(0, lambda s=ilk_sunucu: self.db_server.set(s))
            else:
                self._scan_log_ekle("\nHicbir SQL Server bulunamadi.")
                self._scan_log_ekle("Sunucu adresini manuel olarak girebilirsiniz.")

            self._scan_log_ekle("\n--- Tarama tamamlandi ---")
            self.root.after(0, lambda: self.tara_btn.config(
                state="normal", text="Taramayi Baslat", bg="#3498db"
            ))

        thread = threading.Thread(target=_tarama_thread, daemon=True)
        thread.start()

    def _port_kontrol(self, ip, port):
        """Belirtilen IP:port uzerinde SQL Server kontrolu yap"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            sonuc = s.connect_ex((ip, port))
            s.close()

            if sonuc == 0:
                self._scan_log_ekle("[+] {0}:{1} - SQL Server bulundu!".format(ip, port))
                # Instance name icin UDP 1434 dene
                instance_name = self._sql_browser_sorgula(ip)
                if instance_name:
                    sunucu_adi = "{0}\\{1}".format(ip, instance_name)
                    self._scan_log_ekle("    Instance: {0}".format(instance_name))
                else:
                    sunucu_adi = ip
                self.bulunan_sunucular.append(sunucu_adi)
        except Exception:
            pass

    def _sql_browser_sorgula(self, ip):
        """UDP 1434 uzerinden SQL Server Browser'dan instance name al"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.0)
            # SQL Server Browser protokolu: 0x02 = tum instance'lari listele
            s.sendto(b'\x02', (ip, 1434))
            veri, _ = s.recvfrom(4096)
            s.close()

            # Yaniti parse et - "InstanceName;XXX" seklinde aranir
            if veri:
                yanit = veri.decode("ascii", errors="ignore")
                parcalar = yanit.split(";")
                for idx, parca in enumerate(parcalar):
                    if parca == "InstanceName" and idx + 1 < len(parcalar):
                        return parcalar[idx + 1]
        except Exception:
            pass
        return None

    # =========================================================================
    # ADIM 3 - Veritabani Baglantisi
    # =========================================================================
    def _adim_db_baglanti(self):
        """Veritabani baglanti formu ve test"""
        tk.Label(
            self.icerik_frame,
            text="Veritabani Baglanti Ayarlari",
            font=("Segoe UI", 14, "bold"),
            fg="#2c3e50"
        ).pack(pady=(5, 15))

        # Form alani
        form_frame = tk.Frame(self.icerik_frame)
        form_frame.pack(fill="x", padx=40)

        # Sunucu
        tk.Label(form_frame, text="Sunucu Adresi:", font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w", pady=5
        )
        tk.Entry(form_frame, textvariable=self.db_server, font=("Consolas", 10), width=35).grid(
            row=0, column=1, pady=5, padx=(10, 0)
        )

        # Veritabani adi
        tk.Label(form_frame, text="Veritabani Adi:", font=("Segoe UI", 10)).grid(
            row=1, column=0, sticky="w", pady=5
        )
        tk.Entry(form_frame, textvariable=self.db_name, font=("Consolas", 10), width=35).grid(
            row=1, column=1, pady=5, padx=(10, 0)
        )

        # Kullanici adi
        tk.Label(form_frame, text="Kullanici Adi:", font=("Segoe UI", 10)).grid(
            row=2, column=0, sticky="w", pady=5
        )
        tk.Entry(form_frame, textvariable=self.db_user, font=("Consolas", 10), width=35).grid(
            row=2, column=1, pady=5, padx=(10, 0)
        )

        # Sifre
        tk.Label(form_frame, text="Sifre:", font=("Segoe UI", 10)).grid(
            row=3, column=0, sticky="w", pady=5
        )
        tk.Entry(
            form_frame, textvariable=self.db_password,
            font=("Consolas", 10), width=35, show="*"
        ).grid(row=3, column=1, pady=5, padx=(10, 0))

        # Windows Authentication
        tk.Checkbutton(
            form_frame,
            text="Windows Authentication Kullan (Trusted Connection)",
            variable=self.trusted_connection,
            font=("Segoe UI", 10)
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=10)

        # Sonuc label
        self.db_sonuc_label = tk.Label(
            self.icerik_frame,
            text="",
            font=("Segoe UI", 10),
            wraplength=600
        )
        self.db_sonuc_label.pack(pady=(10, 5))

        # Test butonu
        self.test_btn = tk.Button(
            self.icerik_frame,
            text="Baglanti Testi Yap",
            font=("Segoe UI", 10, "bold"),
            bg="#e67e22",
            fg="white",
            command=self._baglanti_testi
        )
        self.test_btn.pack(pady=5)

    def _baglanti_testi(self):
        """Veritabani baglanti testini arka planda calistir"""
        self.test_btn.config(state="disabled", text="Test ediliyor...")
        self.db_sonuc_label.config(text="Baglanti test ediliyor...", fg="black")

        def _test_thread():
            try:
                import pyodbc

                server = self.db_server.get().strip()
                database = self.db_name.get().strip()
                user = self.db_user.get().strip()
                password = self.db_password.get().strip()
                trusted = self.trusted_connection.get()

                if not server:
                    self.root.after(0, lambda: self._test_sonuc(False, "Sunucu adresi bos!"))
                    return

                # Baglanti dizesi olustur
                if trusted:
                    conn_str = (
                        "DRIVER={{SQL Server}};"
                        "SERVER={0};"
                        "DATABASE={1};"
                        "Trusted_Connection=yes;"
                        "TrustServerCertificate=yes"
                    ).format(server, database)
                else:
                    conn_str = (
                        "DRIVER={{SQL Server}};"
                        "SERVER={0};"
                        "DATABASE={1};"
                        "UID={2};"
                        "PWD={3};"
                        "TrustServerCertificate=yes"
                    ).format(server, database, user, password)

                conn = pyodbc.connect(conn_str, timeout=10)
                cursor = conn.cursor()

                # Test sorgusu - Urun tablosundaki kayit sayisi
                cursor.execute("SELECT COUNT(*) FROM Urun")
                urun_sayisi = cursor.fetchone()[0]

                # Veritabani adi
                cursor.execute("SELECT DB_NAME()")
                db_adi = cursor.fetchone()[0]

                conn.close()

                # Basarili - db_config.json kaydet
                config = {
                    "server": server,
                    "database": database,
                    "user": user,
                    "password": password,
                    "trusted_connection": trusted,
                    "trust_server_certificate": True,
                    "kurulum_tamamlandi": True
                }
                with open(DB_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)

                mesaj = (
                    "Baglanti basarili!\n"
                    "Veritabani: {0}\n"
                    "Urun sayisi: {1}\n"
                    "Ayarlar db_config.json dosyasina kaydedildi."
                ).format(db_adi, urun_sayisi)

                self.root.after(0, lambda m=mesaj: self._test_sonuc(True, m))

            except ImportError:
                self.root.after(0, lambda: self._test_sonuc(
                    False, "pyodbc modulu bulunamadi! Gereksinimler adimini tekrar calistirin."
                ))
            except Exception as e:
                hata_mesaj = "Baglanti hatasi:\n{0}".format(str(e))
                self.root.after(0, lambda m=hata_mesaj: self._test_sonuc(False, m))

        thread = threading.Thread(target=_test_thread, daemon=True)
        thread.start()

    def _test_sonuc(self, basarili, mesaj):
        """Baglanti testi sonucunu goster"""
        if basarili:
            self.db_sonuc_label.config(text=mesaj, fg="#27ae60")
            self.test_btn.config(state="normal", text="Basarili!", bg="#27ae60")
        else:
            self.db_sonuc_label.config(text=mesaj, fg="#e74c3c")
            self.test_btn.config(state="normal", text="Baglanti Testi Yap", bg="#e67e22")

    # =========================================================================
    # ADIM 4 - Botanik EOS Ayarlari
    # =========================================================================
    def _adim_botanik_eos(self):
        """Botanik EOS exe yolu ve medula ayarlari"""
        tk.Label(
            self.icerik_frame,
            text="Botanik EOS Ayarlari",
            font=("Segoe UI", 14, "bold"),
            fg="#2c3e50"
        ).pack(pady=(5, 15))

        # EXE yolu cercevesi
        exe_frame = tk.LabelFrame(
            self.icerik_frame,
            text="BotanikMedula.exe Yolu",
            font=("Segoe UI", 10),
            padx=10, pady=10
        )
        exe_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Yol girisi ve gozat butonu
        yol_frame = tk.Frame(exe_frame)
        yol_frame.pack(fill="x")

        tk.Entry(
            yol_frame,
            textvariable=self.botanik_exe_path,
            font=("Consolas", 9),
            width=50
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            yol_frame,
            text="Gozat...",
            command=self._exe_gozat
        ).pack(side="left", padx=(5, 0))

        # Otomatik bul butonu
        btn_frame2 = tk.Frame(exe_frame)
        btn_frame2.pack(pady=(10, 0))

        tk.Button(
            btn_frame2,
            text="Otomatik Bul",
            bg="#3498db",
            fg="white",
            command=self._exe_otomatik_bul
        ).pack(side="left")

        # EXE sonuc label
        self.exe_sonuc_label = tk.Label(
            exe_frame,
            text="",
            font=("Segoe UI", 9)
        )
        self.exe_sonuc_label.pack()

        # Medula ayarlari cercevesi
        medula_frame = tk.LabelFrame(
            self.icerik_frame,
            text="Medula Ayarlari",
            font=("Segoe UI", 10),
            padx=10, pady=10
        )
        medula_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(
            medula_frame,
            text=(
                "Bu islem medula_settings.json dosyasini varsayilan degerlerle\n"
                "yeniden olusturur. Mevcut ayarlar silinir."
            ),
            font=("Segoe UI", 9),
            justify="left"
        ).pack(anchor="w")

        tk.Button(
            medula_frame,
            text="Medula Ayarlarini Sifirla",
            font=("Segoe UI", 10, "bold"),
            bg="#e74c3c",
            fg="white",
            command=self._medula_sifirla
        ).pack(pady=(10, 0))

        # Medula sonuc label
        self.medula_sonuc_label = tk.Label(
            medula_frame,
            text="",
            font=("Segoe UI", 9)
        )
        self.medula_sonuc_label.pack()

    def _exe_gozat(self):
        """Dosya secme dialogu ac"""
        dosya = filedialog.askopenfilename(
            title="BotanikMedula.exe Secin",
            filetypes=[("EXE Dosyalari", "*.exe"), ("Tum Dosyalar", "*.*")],
            initialdir="C:\\"
        )
        if dosya:
            self.botanik_exe_path.set(dosya)

    def _exe_otomatik_bul(self):
        """Bilinen konumlarda BotanikMedula.exe ara"""
        olasi_yollar = [
            r"C:\BotanikEczane\BotanikMedula.exe",
            r"C:\BotanikEczane\BotanikEczane.exe",
            r"D:\BotanikEczane\BotanikMedula.exe",
            r"D:\BotanikEczane\BotanikEczane.exe",
            r"C:\Program Files\BotanikEczane\BotanikMedula.exe",
            r"C:\Program Files (x86)\BotanikEczane\BotanikMedula.exe",
            r"C:\Program Files\BotanikEczane\BotanikEczane.exe",
            r"C:\Program Files (x86)\BotanikEczane\BotanikEczane.exe",
        ]

        for yol in olasi_yollar:
            if os.path.exists(yol):
                self.botanik_exe_path.set(yol)
                self.exe_sonuc_label.config(
                    text="Bulundu: {0}".format(yol),
                    fg="#27ae60"
                )
                return

        self.exe_sonuc_label.config(
            text="Otomatik bulunamadi. Lutfen manuel olarak secin.",
            fg="#e74c3c"
        )

    def _medula_sifirla(self):
        """medula_settings.json dosyasini varsayilan degerlerle olustur"""
        onay = messagebox.askyesno(
            "Onay",
            "medula_settings.json dosyasi varsayilan degerlerle sifirlanacak.\n"
            "Mevcut ayarlar kaybolacaktir.\n\n"
            "Devam etmek istiyor musunuz?"
        )
        if not onay:
            return

        # Varsayilan medula ayarlari
        varsayilan_ayarlar = {
            "medula_exe_path": self.botanik_exe_path.get(),
            "giris_pencere_title": "",
            "giris_pencere_automation_id": "SifreSorForm",
            "kullanici_combobox_class": "WindowsForms10.COMBOBOX.app.0.134c08f_r8_ad1",
            "kullanici_dropdown_button_name": "Kapat",
            "sifre_textbox_automation_id": "txtSifre",
            "sifre_textbox_class": "WindowsForms10.EDIT.app.0.134c08f_r8_ad1",
            "medula_process_name": "BotanikEczane.exe",
            "giris_button_name": "Giris",
            "kullanicilar": [
                {"kullanici_adi": "", "sifre": ""},
                {"kullanici_adi": "", "sifre": ""},
                {"kullanici_adi": "", "sifre": ""},
                {"kullanici_adi": "", "sifre": ""},
                {"kullanici_adi": "", "sifre": ""},
                {"kullanici_adi": "", "sifre": ""}
            ],
            "aktif_kullanici": 0,
            "telefonsuz_atla": True,
            "giris_yontemi": "indeks",
            "kullanici_adi_giris": "",
            "yasakli_tesis_numaralari": [],
            "pencere_yerlesimi": "standart",
            "depo_ayarlari": {
                "selcuk": {"aktif": False, "kullanici_adi": "", "sifre": ""},
                "alliance": {"aktif": False, "kullanici_adi": "", "sifre": ""},
                "sancak": {"aktif": False, "kullanici_adi": "", "sifre": ""},
                "iskoop": {"aktif": False, "kullanici_adi": "", "sifre": ""},
                "farmazon": {"aktif": False, "kullanici_adi": "", "sifre": ""},
                "depo_siralama": ["selcuk", "alliance", "sancak", "iskoop", "farmazon"],
                "headless": False
            }
        }

        try:
            with open(MEDULA_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(varsayilan_ayarlar, f, indent=4, ensure_ascii=False)
            self.medula_sonuc_label.config(
                text="medula_settings.json basariyla sifirlandi.",
                fg="#27ae60"
            )
        except Exception as e:
            self.medula_sonuc_label.config(
                text="Hata: {0}".format(str(e)),
                fg="#e74c3c"
            )

    # =========================================================================
    # ADIM 5 - Kurulum Tamamlandi
    # =========================================================================
    def _adim_tamamlandi(self):
        """Kurulum tamamlandi ekrani"""
        tk.Label(
            self.icerik_frame,
            text="Kurulum Tamamlandi!",
            font=("Segoe UI", 20, "bold"),
            fg="#27ae60"
        ).pack(pady=(40, 20))

        tk.Label(
            self.icerik_frame,
            text="BotanikTakip kurulumu basariyla tamamlandi.",
            font=("Segoe UI", 12),
            fg="#2c3e50"
        ).pack(pady=(0, 20))

        # Yapilandirma ozeti
        ozet_frame = tk.LabelFrame(
            self.icerik_frame,
            text="Yapilandirma Ozeti",
            font=("Segoe UI", 11),
            padx=15, pady=10
        )
        ozet_frame.pack(fill="x", padx=40, pady=(0, 20))

        # db_config.json oku ve ozet goster
        if os.path.exists(DB_CONFIG_PATH):
            try:
                with open(DB_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

                bilgiler = [
                    ("Sunucu", config.get("server", "Belirtilmemis")),
                    ("Veritabani", config.get("database", "Belirtilmemis")),
                    ("Kullanici", config.get("user", "Belirtilmemis")),
                ]

                for i, (etiket, deger) in enumerate(bilgiler):
                    tk.Label(
                        ozet_frame,
                        text="{0}:".format(etiket),
                        font=("Segoe UI", 10, "bold"),
                        anchor="w",
                        width=15
                    ).grid(row=i, column=0, sticky="w", pady=2)

                    tk.Label(
                        ozet_frame,
                        text=deger,
                        font=("Consolas", 10),
                        anchor="w"
                    ).grid(row=i, column=1, sticky="w", pady=2)

            except Exception as e:
                tk.Label(
                    ozet_frame,
                    text="Yapilandirma dosyasi okunamadi: {0}".format(str(e)),
                    font=("Segoe UI", 10),
                    fg="#e74c3c"
                ).pack()
        else:
            tk.Label(
                ozet_frame,
                text="UYARI: db_config.json dosyasi bulunamadi!\n"
                     "Veritabani baglanti testi yapilmamis olabilir.",
                font=("Segoe UI", 10),
                fg="#e74c3c",
                justify="left"
            ).pack()

        tk.Label(
            self.icerik_frame,
            text="Programi kapatmak icin 'Bitir' butonuna tiklayiniz.",
            font=("Segoe UI", 10),
            fg="#7f8c8d"
        ).pack()

    # =========================================================================
    # Navigasyon
    # =========================================================================
    def _ileri_git(self):
        """Bir sonraki adima gec"""
        if self.mevcut_adim >= self.toplam_adim - 1:
            # Son adimda - programi kapat
            self.root.destroy()
            return
        self._adim_goster(self.mevcut_adim + 1)

    def _geri_git(self):
        """Bir onceki adima don"""
        if self.mevcut_adim > 0:
            self._adim_goster(self.mevcut_adim - 1)

    def _iptal(self):
        """Kurulumu iptal et"""
        onay = messagebox.askyesno(
            "Iptal",
            "Kurulum sihirbazindan cikmak istediginize emin misiniz?"
        )
        if onay:
            self.root.destroy()

    def calistir(self):
        """Sihirbazi baslat"""
        self.root.mainloop()


def main():
    wizard = KurulumWizard()
    wizard.calistir()


if __name__ == "__main__":
    main()
