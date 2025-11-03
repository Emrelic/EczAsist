"""
Botanik Bot - MEDULA Kurulum Wizard
İlk kurulum için adım adım rehber
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


class MedulaWizard:
    """MEDULA ayarları için kurulum wizard'ı"""

    def __init__(self, parent, medula_settings):
        """
        Args:
            parent: Ana pencere (tkinter root)
            medula_settings: MedulaSettings instance
        """
        self.parent = parent
        self.medula_settings = medula_settings
        self.sonuc = None  # Wizard sonucu (True: Tamamlandı, False: İptal)

        # Wizard penceresi - basit Toplevel, modal yok
        self.window = tk.Toplevel(parent)
        self.window.title("MEDULA Kurulum Wizard")
        self.window.geometry("800x750")
        self.window.resizable(False, False)

        # Adımlar
        self.adimlar = [
            {"baslik": "Hoş Geldiniz", "aciklama": "MEDULA ayarlarını yapılandıralım"},
            {"baslik": "Giriş Bilgileri", "aciklama": "Kullanıcı adı ve şifre girin"},
            {"baslik": "Kaydet", "aciklama": "Ayarları kaydedin"}
        ]
        self.aktif_adim = 0

        # Geçici ayarlar
        self.temp_settings = {
            "kullanici_adi": "",
            "sifre": "",
            "kullanici_index": 0
        }

        self.ui_olustur()
        self.adim_goster(0)

        # Pencere kapatma olayı
        self.window.protocol("WM_DELETE_WINDOW", self.iptal_et)

    def ui_olustur(self):
        """UI elementlerini oluştur"""
        # Üst kısım - Adım göstergesi
        ust_frame = tk.Frame(self.window)
        ust_frame.pack(fill="x", side="top", pady=10)

        self.baslik_label = tk.Label(
            ust_frame,
            text="",
            font=("Arial", 14, "bold")
        )
        self.baslik_label.pack(pady=5)

        self.aciklama_label = tk.Label(
            ust_frame,
            text="",
            font=("Arial", 10)
        )
        self.aciklama_label.pack(pady=5)

        # İlerleme çubuğu
        ilerleme_frame = tk.Frame(self.window)
        ilerleme_frame.pack(fill="x", padx=50)

        self.progress = ttk.Progressbar(
            ilerleme_frame,
            orient="horizontal",
            mode="determinate",
            maximum=len(self.adimlar)
        )
        self.progress.pack(fill="x", pady=10)

        # Orta kısım - İçerik alanı
        self.icerik_frame = tk.Frame(self.window)
        self.icerik_frame.pack(fill="both", expand=False, padx=20, pady=10)

        # Alt kısım - Butonlar (daha belirgin)
        alt_frame = tk.Frame(self.window, relief="raised", borderwidth=2)
        alt_frame.pack(fill="x", side="bottom", pady=5)

        button_frame = tk.Frame(alt_frame)
        button_frame.pack(pady=15)

        self.geri_button = tk.Button(
            button_frame,
            text="< Geri",
            width=15,
            height=2,
            font=("Arial", 11),
            command=self.geri_git
        )
        self.geri_button.pack(side="left", padx=10)

        self.ileri_button = tk.Button(
            button_frame,
            text="Ileri >",
            width=15,
            height=2,
            font=("Arial", 11, "bold"),
            command=self.ileri_git
        )
        self.ileri_button.pack(side="left", padx=10)

        self.iptal_button = tk.Button(
            button_frame,
            text="Iptal / Cikis",
            width=15,
            height=2,
            font=("Arial", 11),
            command=self.iptal_et
        )
        self.iptal_button.pack(side="left", padx=10)

    def temizle_icerik(self):
        """İçerik frame'ini temizle"""
        for widget in self.icerik_frame.winfo_children():
            widget.destroy()

    def adim_goster(self, adim_no):
        """Belirtilen adımı göster"""
        self.aktif_adim = adim_no

        # Başlık ve açıklamayı güncelle
        adim = self.adimlar[adim_no]
        self.baslik_label.config(text=adim["baslik"])
        self.aciklama_label.config(text=adim["aciklama"])

        # İlerleme çubuğunu güncelle
        self.progress["value"] = adim_no + 1

        # Buton durumlarını güncelle
        self.geri_button.config(state="normal" if adim_no > 0 else "disabled")

        if adim_no == len(self.adimlar) - 1:
            self.ileri_button.config(text="Tamamla")
        else:
            self.ileri_button.config(text="Ileri >")

        # İçeriği temizle ve yeni adımı göster
        self.temizle_icerik()

        if adim_no == 0:
            self.adim_hosgeldiniz()
        elif adim_no == 1:
            self.adim_giris_bilgileri()
        elif adim_no == 2:
            self.adim_kaydet()

    def adim_hosgeldiniz(self):
        """Adım 0: Hoş geldiniz ekranı"""
        # Ana başlık
        title = tk.Label(
            self.icerik_frame,
            text="MEDULA Kurulum Wizard'a Hos Geldiniz",
            font=("Arial", 14, "bold")
        )
        title.pack(pady=20)

        # Açıklama metni
        aciklama_text = """Bu wizard, MEDULA otomasyonu icin gerekli ayarlari
yapilandirmaniza yardimci olacaktir.

Yapilacaklar:
- MEDULA kullanici adi ve sifre ayarlama
- Ayarlari kaydetme

MEDULA programi otomatik olarak su adresten baslatilacak:
C:\\BotanikEczane\\BotanikMedula.exe

Ilerlemek icin 'Ileri' butonuna basin."""

        aciklama = tk.Label(
            self.icerik_frame,
            text=aciklama_text,
            font=("Arial", 10),
            justify="left"
        )
        aciklama.pack(pady=20, padx=40)

    def adim_masaustu_simgesi(self):
        """Adım 1: Masaüstü simgesi tespiti"""
        # Başlık
        title = tk.Label(
            self.icerik_frame,
            text="Masaustu MEDULA Simgesi",
            font=("Arial", 12, "bold")
        )
        title.pack(pady=10)

        # Açıklama
        aciklama = tk.Label(
            self.icerik_frame,
            text="MEDULA programinin .exe dosyasini secin:",
            font=("Arial", 10),
            justify="center"
        )
        aciklama.pack(pady=15)

        # Buton frame
        button_frame = tk.Frame(self.icerik_frame)
        button_frame.pack(pady=15)

        # Otomatik bul butonu (BÜYÜK VE BELİRGİN)
        auto_button = tk.Button(
            button_frame,
            text="OTOMATIK BUL\n(Tavsiye Edilen)",
            font=("Arial", 12, "bold"),
            command=self.otomatik_bul,
            width=30,
            height=3,
            relief="raised",
            borderwidth=3
        )
        auto_button.pack(pady=5)

        # Manuel seç butonu
        manuel_button = tk.Button(
            button_frame,
            text="Manuel Olarak Sec (.exe dosyasi)",
            font=("Arial", 11),
            command=self.manuel_sec,
            width=30,
            height=2
        )
        manuel_button.pack(pady=5)

        # Seçilen dosya göstergesi
        self.secilen_label = tk.Label(
            self.icerik_frame,
            text="Secilen: " + self.temp_settings.get("medula_exe_path", "(Henuz secilmedi)"),
            font=("Arial", 9, "bold"),
            wraplength=600,
            justify="center"
        )
        self.secilen_label.pack(pady=20)

    def otomatik_bul(self):
        """Masaüstünde MEDULA kısayolunu bul ve exe yolunu al"""
        try:
            import os
            import win32com.client

            # Masaüstü yolu
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

            # Alternatif: OneDrive masaüstü
            onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")

            search_paths = [desktop_path]
            if os.path.exists(onedrive_desktop):
                search_paths.append(onedrive_desktop)

            shell = win32com.client.Dispatch("WScript.Shell")
            bulunan_exeler = []

            # Tüm .lnk dosyalarını tara
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    continue

                for file in os.listdir(search_path):
                    if file.endswith(".lnk"):
                        lnk_path = os.path.join(search_path, file)
                        try:
                            shortcut = shell.CreateShortCut(lnk_path)
                            target = shortcut.Targetpath

                            # BotanikEczane veya Medula içeren exe'leri bul
                            if target.lower().endswith(".exe") and ("botanik" in target.lower() or "medula" in target.lower()):
                                bulunan_exeler.append((file.replace(".lnk", ""), target))
                        except:
                            pass

            if bulunan_exeler:
                # Eğer birden fazla bulunduysa kullanıcıya sor
                if len(bulunan_exeler) == 1:
                    isim, exe_path = bulunan_exeler[0]
                    self.temp_settings["medula_exe_path"] = exe_path
                    self.secilen_label.config(text=f"Secilen: {exe_path}")
                    messagebox.showinfo("Basarili", f"MEDULA bulundu:\n{exe_path}")
                else:
                    # Listeden seçtir
                    secim_mesaji = "Birden fazla program bulundu. Hangisini kullanmak istersiniz?\n\n"
                    for i, (isim, exe_path) in enumerate(bulunan_exeler, 1):
                        secim_mesaji += f"{i}. {isim}\n"

                    # İlkini kullan
                    isim, exe_path = bulunan_exeler[0]
                    self.temp_settings["medula_exe_path"] = exe_path
                    self.secilen_label.config(text=f"Secilen: {exe_path}")
                    messagebox.showinfo("Basarili", f"MEDULA bulundu:\n{exe_path}\n\n(Ilk bulunani sectim)")
            else:
                messagebox.showwarning(
                    "Bulunamadi",
                    "Masaustunde MEDULA kisayolu bulunamadi.\n\n"
                    "Lutfen 'Manuel Olarak Sec' butonunu kullanin."
                )

        except Exception as e:
            logger.error(f"Otomatik bulma hatası: {e}")
            messagebox.showerror("Hata", f"Otomatik bulma basarisiz:\n{str(e)}\n\nLutfen manuel secim yapin.")

    def manuel_sec(self):
        """File dialog ile exe dosyasını seç"""
        try:
            from tkinter import filedialog

            exe_path = filedialog.askopenfilename(
                title="MEDULA .exe dosyasini secin",
                filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
                initialdir="C:\\Program Files"
            )

            if exe_path:
                self.temp_settings["medula_exe_path"] = exe_path
                self.secilen_label.config(text=f"Secilen: {exe_path}")
                messagebox.showinfo("Basarili", f"Dosya secildi:\n{exe_path}")

        except Exception as e:
            logger.error(f"Manuel seçim hatası: {e}")
            messagebox.showerror("Hata", f"Dosya secilemedi:\n{str(e)}")

    def adim_giris_bilgileri(self):
        """Adım 2: Kullanıcı adı ve şifre girişi"""
        # Başlık
        title = tk.Label(
            self.icerik_frame,
            text="MEDULA Giris Bilgileri",
            font=("Arial", 12, "bold")
        )
        title.pack(pady=10)

        # Açıklama
        aciklama = tk.Label(
            self.icerik_frame,
            text="MEDULA giris bilgilerinizi girin:",
            font=("Arial", 10),
            justify="center"
        )
        aciklama.pack(pady=10)

        # Input frame
        input_frame = tk.Frame(self.icerik_frame)
        input_frame.pack(pady=20)

        # Kullanıcı sırası
        tk.Label(input_frame, text="Kacinci Kullanici:", font=("Arial", 11, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")

        kullanici_secim_frame = tk.Frame(input_frame)
        kullanici_secim_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.kullanici_index_var = tk.IntVar(value=self.temp_settings.get("kullanici_index", 0))

        tk.Radiobutton(
            kullanici_secim_frame,
            text="Birinci (0)",
            variable=self.kullanici_index_var,
            value=0,
            font=("Arial", 10)
        ).pack(anchor="w")

        tk.Radiobutton(
            kullanici_secim_frame,
            text="Ikinci (1)",
            variable=self.kullanici_index_var,
            value=1,
            font=("Arial", 10)
        ).pack(anchor="w")

        tk.Radiobutton(
            kullanici_secim_frame,
            text="Ucuncu (2)",
            variable=self.kullanici_index_var,
            value=2,
            font=("Arial", 10)
        ).pack(anchor="w")

        tk.Radiobutton(
            kullanici_secim_frame,
            text="Dorduncu (3)",
            variable=self.kullanici_index_var,
            value=3,
            font=("Arial", 10)
        ).pack(anchor="w")

        # Şifre
        tk.Label(input_frame, text="Sifre:", font=("Arial", 10)).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.sifre_var = tk.StringVar(value=self.temp_settings.get("sifre", ""))
        sifre_entry = tk.Entry(input_frame, textvariable=self.sifre_var, font=("Arial", 10), width=30, show="*")
        sifre_entry.grid(row=1, column=1, padx=10, pady=10)

        # Şifreyi göster checkbox
        self.show_password_var = tk.BooleanVar(value=False)
        show_check = tk.Checkbutton(
            input_frame,
            text="Sifreyi goster",
            variable=self.show_password_var,
            command=lambda: sifre_entry.config(show="" if self.show_password_var.get() else "*")
        )
        show_check.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # Açıklama
        aciklama_frame = tk.Frame(self.icerik_frame, relief="solid", borderwidth=1, padx=15, pady=10)
        aciklama_frame.pack(pady=20)

        aciklama = tk.Label(
            aciklama_frame,
            text="ONEMLI!\nMEDULA giris ekranindaki kullanici listesinde\nKAÇINCI SIRADA oldugunuzu sayın!\n\nOrnek: Listenin en ustunde ise -> Birinci (0)\n        Listede ikinci sirada ise -> Ikinci (1)",
            font=("Arial", 9, "bold"),
            justify="center",
            fg="#D32F2F"
        )
        aciklama.pack()

    def adim_kaydet(self):
        """Adım 2: Kaydetme"""
        # Başlık
        title = tk.Label(
            self.icerik_frame,
            text="Ayarlari Kaydet",
            font=("Arial", 12, "bold")
        )
        title.pack(pady=10)

        # Açıklama
        aciklama = tk.Label(
            self.icerik_frame,
            text="Ayarlarinizi kontrol edin ve 'Tamamla' butonuna basin.",
            font=("Arial", 9),
            justify="center"
        )
        aciklama.pack(pady=5)

        # Ayarlar özeti
        ozet_frame = tk.LabelFrame(self.icerik_frame, text="Ayarlar Ozeti", font=("Arial", 10, "bold"), padx=20, pady=10)
        ozet_frame.pack(pady=15, fill="x", padx=40)

        # EXE yolu
        exe_text = "MEDULA .exe: C:\\BotanikEczane\\BotanikMedula.exe"
        tk.Label(ozet_frame, text=exe_text, font=("Arial", 9), wraplength=500, justify="left").pack(anchor="w", pady=3)

        # Kullanıcı index
        kullanici_index = self.temp_settings.get("kullanici_index", 0)
        index_isimler = {0: "Birinci", 1: "Ikinci", 2: "Ucuncu", 3: "Dorduncu"}
        kullanici_text = f"Kullanici: {index_isimler.get(kullanici_index, 'Birinci')} ({kullanici_index})"
        tk.Label(ozet_frame, text=kullanici_text, font=("Arial", 10)).pack(anchor="w", pady=3)

        # Şifre (gizli)
        sifre_text = "Sifre: " + ("*" * len(self.temp_settings.get("sifre", "")))
        tk.Label(ozet_frame, text=sifre_text, font=("Arial", 10)).pack(anchor="w", pady=3)

    def test_ayarlar(self):
        """Ayarları test et"""
        self.test_sonuc_label.config(text="Test ediliyor...")
        self.test_button.config(state="disabled")
        self.window.update()

        try:
            import os

            # Test 1: EXE dosyası var mı?
            exe_path = self.temp_settings.get("medula_exe_path", "")
            if not exe_path:
                raise Exception("EXE dosyasi secilmemis")

            if not os.path.exists(exe_path):
                raise Exception(f"EXE dosyasi bulunamadi:\n{exe_path}")

            # Test başarılı
            self.test_sonuc_label.config(text="TEST BASARILI! EXE dosyasi dogrulandi.")
            messagebox.showinfo(
                "Test Basarili",
                f"MEDULA .exe dosyasi dogrulandi!\n{exe_path}\n\n"
                "'Tamamla' butonuna basarak ayarlari kaydedin."
            )

        except Exception as e:
            self.test_sonuc_label.config(text=f"Test basarisiz: {str(e)}")
            messagebox.showwarning(
                "Test Basarisiz",
                f"Test basarisiz oldu:\n{str(e)}\n\n"
                "Ancak 'Tamamla' butonuna basarak yine de kaydedebilirsiniz.\n"
                "Dosya yolunu kontrol edip tekrar deneyin."
            )

        finally:
            self.test_button.config(state="normal")

    def geri_git(self):
        """Önceki adıma git"""
        if self.aktif_adim > 0:
            # Mevcut adımdaki verileri kaydet
            self.adim_verileri_kaydet()
            self.adim_goster(self.aktif_adim - 1)

    def ileri_git(self):
        """Sonraki adıma git veya tamamla"""
        # Mevcut adımdaki verileri kaydet
        if not self.adim_verileri_kaydet():
            return

        if self.aktif_adim < len(self.adimlar) - 1:
            # Sonraki adıma geç
            self.adim_goster(self.aktif_adim + 1)
        else:
            # Son adım, tamamla
            self.tamamla()

    def adim_verileri_kaydet(self):
        """Mevcut adımdaki verileri geçici ayarlara kaydet"""
        try:
            if self.aktif_adim == 1:
                # Kullanıcı index ve şifre
                sifre = self.sifre_var.get().strip()

                if not sifre:
                    messagebox.showwarning("Uyari", "Lutfen sifre girin!")
                    return False

                self.temp_settings["kullanici_index"] = self.kullanici_index_var.get()
                self.temp_settings["sifre"] = sifre

            return True

        except Exception as e:
            logger.error(f"Veri kaydetme hatası: {e}")
            return False

    def tamamla(self):
        """Wizard'ı tamamla ve ayarları kaydet"""
        try:
            # Ayarları kalıcı olarak kaydet
            for key, value in self.temp_settings.items():
                self.medula_settings.set(key, value)

            if self.medula_settings.kaydet():
                messagebox.showinfo(
                    "Basarili",
                    "MEDULA ayarlari basariyla kaydedildi!\n\n"
                    "Artik programi kullanmaya baslayabilirsiniz."
                )
                self.sonuc = True
                self.window.destroy()
            else:
                messagebox.showerror("Hata", "Ayarlar kaydedilemedi!")

        except Exception as e:
            logger.error(f"Tamamlama hatası: {e}")
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi:\n{str(e)}")

    def iptal_et(self):
        """Wizard'ı iptal et"""
        # Son adımda ise, sadece kapat
        if self.aktif_adim == len(self.adimlar) - 1:
            self.sonuc = False
            self.window.destroy()
            return

        # Diğer adımlarda onay sor
        cevap = messagebox.askyesno(
            "Emin misiniz?",
            "Wizard'dan cikmak istediginizden emin misiniz?\nAyarlar kaydedilmeyecek."
        )

        if cevap:
            self.sonuc = False
            self.window.destroy()

    def goster(self):
        """Wizard penceresini göster ve sonucu döndür"""
        self.window.wait_window()
        return self.sonuc


def wizard_goster(parent, medula_settings):
    """
    Wizard penceresini göster

    Args:
        parent: Ana tkinter penceresi
        medula_settings: MedulaSettings instance

    Returns:
        bool: True ise tamamlandı, False ise iptal
    """
    wizard = MedulaWizard(parent, medula_settings)
    return wizard.goster()
