"""
Kıyas Motoru - Tüm ilaçları depolar arasında karşılaştır
"""
import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


class KiyasmotoruWindow:
    """Kıyas Motoru penceresi"""

    def __init__(self, parent, main_window=None):
        self.parent = parent
        self.main_window = main_window
        self.controller = main_window.controller if main_window else None

        # CSV dosya yolu
        self.csv_path = r"C:\Users\fmazi\Documents\BotSiparis\src\Tüm İlaç ListesiTam.csv"

        # İlaç listesi
        self.ilac_listesi = []
        self.toplam_ilac = 0

        # Tarama durumu
        self.is_scanning = False
        self.current_index = 0
        self.scan_thread = None

        # Pencereyi oluştur
        self.window = tk.Toplevel(parent)
        self.window.title("⚖ Kıyas Motoru")
        self.window.geometry("700x750")
        self.window.minsize(700, 700)
        self.window.configure(bg="#1a1a2e")
        self.window.transient(parent)

        # Renk paleti
        self.colors = {
            "bg_dark": "#1a1a2e",
            "bg_medium": "#16213e",
            "bg_light": "#1f4068",
            "accent": "#e94560",
            "text": "#eaeaea",
            "success": "#4ecca3",
            "warning": "#ffc107",
            "info": "#17a2b8"
        }

        # CSV'yi yükle
        self.load_csv()

        # Arayüzü oluştur
        self.create_widgets()

        # Pencereyi ortala
        self.center_window()

    def load_csv(self):
        """CSV dosyasından ilaç listesini yükle"""
        try:
            if os.path.exists(self.csv_path):
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.ilac_listesi = list(reader)
                    self.toplam_ilac = len(self.ilac_listesi)
        except Exception as e:
            messagebox.showerror("Hata", f"CSV dosyası okunamadı: {e}")
            self.ilac_listesi = []
            self.toplam_ilac = 0

    def create_widgets(self):
        """Arayüz bileşenlerini oluştur"""
        # Ana frame
        main_frame = tk.Frame(self.window, bg=self.colors["bg_dark"], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Başlık
        title_label = tk.Label(
            main_frame,
            text="⚖ KIYAS MOTORU",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["accent"]
        )
        title_label.pack(pady=(0, 10))

        # Açıklama
        desc_label = tk.Label(
            main_frame,
            text="Tüm ilaçları aktif depolarda karşılaştır\n(Botanik'ten okumaz, Botanik'e yazmaz)",
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"]
        )
        desc_label.pack(pady=(0, 15))

        # Toplam ilaç sayısı
        info_frame = tk.Frame(main_frame, bg=self.colors["bg_medium"], padx=15, pady=10)
        info_frame.pack(fill=tk.X, pady=10)

        self.total_label = tk.Label(
            info_frame,
            text=f"📦 Toplam İlaç: {self.toplam_ilac}",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["bg_medium"],
            fg=self.colors["success"]
        )
        self.total_label.pack()

        # Aralık seçimi frame
        range_frame = tk.LabelFrame(
            main_frame,
            text="Tarama Aralığı",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            padx=15,
            pady=15
        )
        range_frame.pack(fill=tk.X, pady=15)

        # Başlangıç
        start_frame = tk.Frame(range_frame, bg=self.colors["bg_dark"])
        start_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            start_frame,
            text="Başlangıç:",
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            width=12,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.start_entry = tk.Entry(
            start_frame,
            font=("Segoe UI", 11),
            width=15,
            bg=self.colors["bg_medium"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"]
        )
        self.start_entry.insert(0, "1")
        self.start_entry.pack(side=tk.LEFT, padx=10)

        # Bitiş
        end_frame = tk.Frame(range_frame, bg=self.colors["bg_dark"])
        end_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            end_frame,
            text="Bitiş:",
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            width=12,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.end_entry = tk.Entry(
            end_frame,
            font=("Segoe UI", 11),
            width=15,
            bg=self.colors["bg_medium"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"]
        )
        self.end_entry.insert(0, str(min(100, self.toplam_ilac)))
        self.end_entry.pack(side=tk.LEFT, padx=10)

        # Sonuna kadar checkbox
        self.scan_all_var = tk.BooleanVar(value=False)
        self.scan_all_check = tk.Checkbutton(
            range_frame,
            text="Sonuna kadar tara",
            variable=self.scan_all_var,
            command=self.toggle_scan_all,
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            selectcolor=self.colors["bg_medium"],
            activebackground=self.colors["bg_dark"],
            activeforeground=self.colors["text"]
        )
        self.scan_all_check.pack(pady=10)

        # Aktif depolar bilgisi
        depo_frame = tk.LabelFrame(
            main_frame,
            text="Aktif Depolar",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            padx=15,
            pady=10
        )
        depo_frame.pack(fill=tk.X, pady=10)

        # Aktif depoları listele
        if self.main_window and hasattr(self.main_window, 'available_depolar'):
            aktif_depolar = list(self.main_window.available_depolar.keys())
            depo_text = ", ".join([d.upper() for d in aktif_depolar])
        else:
            depo_text = "Bilinmiyor"

        self.depo_label = tk.Label(
            depo_frame,
            text=depo_text,
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["info"],
            wraplength=600
        )
        self.depo_label.pack()

        # İlerleme çubuğu
        progress_frame = tk.Frame(main_frame, bg=self.colors["bg_dark"])
        progress_frame.pack(fill=tk.X, pady=15)

        self.progress_label = tk.Label(
            progress_frame,
            text="Bekleniyor...",
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"]
        )
        self.progress_label.pack()

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=600
        )
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.current_drug_label = tk.Label(
            progress_frame,
            text="",
            font=("Segoe UI", 9),
            bg=self.colors["bg_dark"],
            fg=self.colors["warning"],
            wraplength=600
        )
        self.current_drug_label.pack()

        # Butonlar
        button_frame = tk.Frame(main_frame, bg=self.colors["bg_dark"])
        button_frame.pack(fill=tk.X, pady=20)

        self.start_button = tk.Button(
            button_frame,
            text="▶ Kıyası Başlat",
            command=self.start_kiyas,
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["success"],
            fg="white",
            padx=30,
            pady=10,
            cursor="hand2",
            relief=tk.FLAT
        )
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = tk.Button(
            button_frame,
            text="⏹ Durdur",
            command=self.stop_kiyas,
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["accent"],
            fg="white",
            padx=30,
            pady=10,
            cursor="hand2",
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)

        self.close_button = tk.Button(
            button_frame,
            text="✕ Kapat",
            command=self.close_window,
            font=("Segoe UI", 12),
            bg=self.colors["bg_light"],
            fg=self.colors["text"],
            padx=30,
            pady=10,
            cursor="hand2",
            relief=tk.FLAT
        )
        self.close_button.pack(side=tk.RIGHT, padx=10)

        # Sonuç özeti
        self.result_frame = tk.LabelFrame(
            main_frame,
            text="Sonuç Özeti",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"],
            padx=15,
            pady=10
        )
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.result_text = tk.Text(
            self.result_frame,
            font=("Consolas", 9),
            bg=self.colors["bg_medium"],
            fg=self.colors["text"],
            height=6,
            wrap=tk.WORD
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.result_text, command=self.result_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)

    def toggle_scan_all(self):
        """Sonuna kadar tara seçeneğini toggle et"""
        if self.scan_all_var.get():
            self.end_entry.delete(0, tk.END)
            self.end_entry.insert(0, str(self.toplam_ilac))
            self.end_entry.config(state=tk.DISABLED)
        else:
            self.end_entry.config(state=tk.NORMAL)

    def _open_depolar(self):
        """Depoları otomatik aç - Normal tarama modu gibi"""
        try:
            from ..utils import HEADLESS

            # .env dosyasını yükle
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)

            # Depo kullanıcı bilgilerini oku
            credentials = {
                "alliance": {
                    "eczane_kodu": os.getenv("ALLIANCE_ECZANE_KODU", ""),
                    "username": os.getenv("ALLIANCE_USERNAME", ""),
                    "password": os.getenv("ALLIANCE_PASSWORD", "")
                },
                "selcuk": {
                    "hesap_kodu": os.getenv("SELCUK_HESAP_KODU", ""),
                    "username": os.getenv("SELCUK_USERNAME", ""),
                    "password": os.getenv("SELCUK_PASSWORD", "")
                },
                "yusufpasa": {
                    "eczane_kodu": os.getenv("YUSUFPASA_ECZANE_KODU", ""),
                    "username": os.getenv("YUSUFPASA_USERNAME", ""),
                    "password": os.getenv("YUSUFPASA_PASSWORD", "")
                },
                "iskoop": {
                    "username": os.getenv("ISKOOP_USERNAME", ""),
                    "password": os.getenv("ISKOOP_PASSWORD", "")
                },
                "bursa": {
                    "username": os.getenv("BURSA_USERNAME", ""),
                    "password": os.getenv("BURSA_PASSWORD", "")
                },
                "farmazon": {
                    "username": os.getenv("FARMAZON_USERNAME", ""),
                    "password": os.getenv("FARMAZON_PASSWORD", "")
                },
                "sancak": {
                    "username": os.getenv("SANCAK_USERNAME", ""),
                    "password": os.getenv("SANCAK_PASSWORD", "")
                }
            }

            shared_driver = None
            first_depo = True
            acilan_depo_sayisi = 0

            for depo_name, depo in self.main_window.available_depolar.items():
                # Önce credentials kontrolü
                creds = credentials.get(depo_name, {})

                has_credentials = False
                if depo_name == "alliance":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "selcuk":
                    has_credentials = bool(creds.get("hesap_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "yusufpasa":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                    has_credentials = bool(creds.get("username") and creds.get("password"))

                if not has_credentials:
                    continue

                try:
                    self.progress_label.config(text=f"⏳ {depo.name} açılıyor...")
                    self.window.update()

                    # İlk aktif depo yeni Chrome, diğerleri aynı Chrome'da yeni tab
                    if first_depo:
                        if not depo.init_driver(headless=HEADLESS):
                            continue
                        shared_driver = depo.driver
                        first_depo = False
                    else:
                        if not shared_driver:
                            continue
                        if not depo.init_driver(headless=HEADLESS, shared_driver=shared_driver):
                            continue

                    if not depo.open_page():
                        continue

                    time.sleep(2)

                    # Otomatik giriş yap
                    self.progress_label.config(text=f"⏳ {depo.name} - Giriş yapılıyor...")
                    self.window.update()

                    if depo_name == "alliance":
                        depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name == "selcuk":
                        depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                    elif depo_name == "yusufpasa":
                        depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                        depo.login(creds["username"], creds["password"])

                    time.sleep(2)
                    acilan_depo_sayisi += 1

                except Exception as e:
                    self._add_result_line(f"❌ {depo.name} açılırken hata: {str(e)[:40]}")

            self.progress_label.config(text=f"✅ {acilan_depo_sayisi} depo açıldı")
            self.window.update()

            return acilan_depo_sayisi > 0

        except Exception as e:
            self._add_result_line(f"❌ Depo açma hatası: {str(e)[:50]}")
            return False

    def start_kiyas(self):
        """Kıyas işlemini başlat"""
        try:
            start_idx = int(self.start_entry.get()) - 1  # 0-indexed
            end_idx = int(self.end_entry.get())

            if start_idx < 0:
                start_idx = 0
            if end_idx > self.toplam_ilac:
                end_idx = self.toplam_ilac
            if start_idx >= end_idx:
                messagebox.showwarning("Uyarı", "Başlangıç, bitişten küçük olmalı!")
                return

            # Depoların açık olup olmadığını kontrol et
            if not self.main_window or not hasattr(self.main_window, 'available_depolar'):
                messagebox.showerror("Hata", "Ana pencere bulunamadı!")
                return

            if not self.main_window.available_depolar:
                messagebox.showwarning("Uyarı", "Aktif depo yok! Önce ayarlardan depoları etkinleştirin.")
                return

            # En az bir depo açık mı? Değilse otomatik aç
            acik_depo = False
            for depo_name, depo in self.main_window.available_depolar.items():
                if depo.driver:
                    acik_depo = True
                    break

            if not acik_depo:
                # Depoları otomatik aç
                self.progress_label.config(text="⏳ Depolar açılıyor...")
                self.window.update()

                if not self._open_depolar():
                    messagebox.showwarning(
                        "Uyarı",
                        "Hiçbir depo açılamadı!\n\n"
                        "Lütfen ayarlardan depo bilgilerini kontrol edin."
                    )
                    return

            # Ana tabloya temizle
            self.main_window.tree.delete(*self.main_window.tree.get_children())
            self.main_window.products.clear()

            # Arayüzü güncelle
            self.is_scanning = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.start_entry.config(state=tk.DISABLED)
            self.end_entry.config(state=tk.DISABLED)
            self.scan_all_check.config(state=tk.DISABLED)

            # Progress bar'ı ayarla
            total_to_scan = end_idx - start_idx
            self.progress_bar["maximum"] = total_to_scan
            self.progress_bar["value"] = 0

            # Sonuç alanını temizle
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"Kıyas başlatılıyor... ({start_idx + 1} - {end_idx})\n")
            self.result_text.insert(tk.END, f"Toplam taranacak: {total_to_scan} ilaç\n")
            self.result_text.insert(tk.END, "-" * 50 + "\n")

            # Thread ile taramayı başlat
            self.scan_thread = threading.Thread(
                target=self._run_kiyas,
                args=(start_idx, end_idx),
                daemon=True
            )
            self.scan_thread.start()

        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli sayılar girin!")

    def _run_kiyas(self, start_idx, end_idx):
        """Kıyas işlemini arka planda çalıştır"""
        try:
            results = []
            scanned_count = 0
            row_number = 1  # Satır numarası

            for i in range(start_idx, end_idx):
                if not self.is_scanning:
                    break

                ilac = self.ilac_listesi[i]
                ilac_adi = ilac.get("İlaç Adı", "")
                barkod = ilac.get("Barkod", "")

                # İlerlemeyi güncelle
                scanned_count += 1
                self.window.after(0, self._update_progress, scanned_count, end_idx - start_idx, ilac_adi, barkod)

                # Depolarda ara (Botanik olmadan, main_window üzerinden)
                if self.main_window:
                    try:
                        # Kıyas araması yap
                        result = self.main_window.search_barcode_kiyas(barkod, ilac_adi)
                        if result:
                            results.append(result)

                            # Sonucu ana GUI tablosuna ekle
                            depolar = result.get("depolar", {})

                            # Ürün verisi oluştur (Botanik verisi yok)
                            product_data = {
                                "row": row_number,
                                "urun_adi": ilac_adi,
                                "barkod": barkod,
                                "stok": 0,  # Botanik'ten gelmedi
                                "mf": 0,
                                "minstk": 0,
                                "siparis_adet": 0
                            }

                            # Depo durumlarını ekle
                            for depo_name, depo_info in depolar.items():
                                product_data[f"{depo_name}_durum"] = depo_info

                            # Açıklama metni oluştur
                            stokta_var = [d.upper() for d, info in depolar.items() if info.get("stok_var")]
                            if stokta_var:
                                product_data["aciklama_ozeti"] = f"✅ {', '.join(stokta_var)}"
                            else:
                                product_data["aciklama_ozeti"] = "❌ Stok yok"

                            # Ana tabloya ekle
                            self.window.after(0, self._add_to_main_table, product_data)

                            row_number += 1

                            # Özet göster
                            stokta_yok = [d for d, info in depolar.items() if not info.get("stok_var")]
                            ozet = f"{ilac_adi[:35]} → "
                            if stokta_var:
                                ozet += f"✅{len(stokta_var)} "
                            if stokta_yok:
                                ozet += f"❌{len(stokta_yok)}"

                            self.window.after(0, self._add_result_line, ozet)

                    except Exception as e:
                        self.window.after(0, self._add_result_line, f"HATA ({barkod}): {str(e)[:50]}")

            # Tamamlandı
            self.window.after(0, self._kiyas_completed, results, scanned_count)

        except Exception as e:
            self.window.after(0, self._kiyas_error, str(e))

    def _add_to_main_table(self, product_data):
        """Ürünü ana GUI tablosuna ekle"""
        try:
            if self.main_window:
                # Tabloya satır ekle (add_product_row zaten products'a ekliyor)
                self.main_window.add_product_row(product_data)

                # Şartlar tablosunu güncelle
                self.main_window.on_tree_select(None)

                # Status'u güncelle
                self.main_window.status_label.config(
                    text=f"🔍 Kıyas: {product_data.get('urun_adi', '')[:40]}"
                )
        except Exception as e:
            self._add_result_line(f"❌ Tablo hatası: {str(e)[:40]}")

    def _update_progress(self, current, total, ilac_adi, barkod):
        """İlerleme çubuğunu güncelle"""
        self.progress_bar["value"] = current
        percentage = (current / total) * 100 if total > 0 else 0
        self.progress_label.config(text=f"İlerleme: {current}/{total} ({percentage:.1f}%)")
        self.current_drug_label.config(text=f"📋 {ilac_adi} ({barkod})")

    def _add_result_line(self, text):
        """Sonuç alanına satır ekle"""
        self.result_text.insert(tk.END, text + "\n")
        self.result_text.see(tk.END)

    def _kiyas_completed(self, results, total_scanned):
        """Kıyas tamamlandığında"""
        self.is_scanning = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.start_entry.config(state=tk.NORMAL)
        if not self.scan_all_var.get():
            self.end_entry.config(state=tk.NORMAL)
        self.scan_all_check.config(state=tk.NORMAL)

        self.progress_label.config(text=f"✅ Tamamlandı! {total_scanned} ilaç tarandı.")
        self.current_drug_label.config(text="")

        # Özet
        self.result_text.insert(tk.END, "\n" + "=" * 50 + "\n")
        self.result_text.insert(tk.END, f"TAMAMLANDI!\n")
        self.result_text.insert(tk.END, f"Taranan: {total_scanned} ilaç\n")
        self.result_text.insert(tk.END, f"Sonuç: {len(results)} kayıt\n")
        self.result_text.see(tk.END)

    def _kiyas_error(self, error_msg):
        """Hata durumunda"""
        self.is_scanning = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_label.config(text=f"❌ Hata: {error_msg}")

    def stop_kiyas(self):
        """Kıyas işlemini durdur"""
        self.is_scanning = False
        self.progress_label.config(text="⏹ Durduruldu")
        self.result_text.insert(tk.END, "\n⏹ Kullanıcı tarafından durduruldu.\n")

    def close_window(self):
        """Pencereyi kapat"""
        if self.is_scanning:
            if messagebox.askyesno("Onay", "Kıyas devam ediyor. Kapatmak istiyor musunuz?"):
                self.is_scanning = False
                self.window.destroy()
        else:
            self.window.destroy()

    def center_window(self):
        """Pencereyi ekranın ortasına al"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"+{x}+{y}")
