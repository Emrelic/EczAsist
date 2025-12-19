"""
Botanik Bot - Kullanıcı Yönetimi GUI
Admin paneli - kullanıcı ekleme, düzenleme, yetkilendirme
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from kullanici_yonetimi import get_kullanici_yonetimi, KullaniciYonetimi

logger = logging.getLogger(__name__)


class KullaniciYonetimiPenceresi:
    """Kullanıcı yönetimi penceresi"""

    def __init__(self, parent, aktif_kullanici):
        """
        Args:
            parent: Ana pencere (Toplevel için)
            aktif_kullanici: Şu an giriş yapmış kullanıcı bilgileri
        """
        self.parent = parent
        self.aktif_kullanici = aktif_kullanici
        self.kullanici_yonetimi = get_kullanici_yonetimi()

        # Yeni pencere oluştur
        self.pencere = tk.Toplevel(parent)
        self.pencere.title("Kullanıcı Yönetimi")

        # Boyut - daha büyük pencere
        pencere_genislik = 1100
        pencere_yukseklik = 700

        # Ortala
        ekran_genislik = self.pencere.winfo_screenwidth()
        ekran_yukseklik = self.pencere.winfo_screenheight()
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2

        self.pencere.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
        self.pencere.resizable(True, True)
        self.pencere.minsize(900, 600)

        # Renk şeması
        self.bg_color = '#F5F5F5'
        self.header_color = '#1565C0'
        self.pencere.configure(bg=self.bg_color)

        # Modal pencere
        self.pencere.transient(parent)
        self.pencere.grab_set()

        self.secili_kullanici_id = None

        self.arayuz_olustur()
        self.kullanici_listesini_yenile()

    def arayuz_olustur(self):
        """Arayüzü oluştur"""
        # Header
        header = tk.Frame(self.pencere, bg=self.header_color, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        baslik = tk.Label(
            header,
            text="👥 Kullanıcı Yönetimi",
            font=("Arial", 16, "bold"),
            bg=self.header_color,
            fg='white'
        )
        baslik.pack(pady=12)

        # Ana içerik
        main_frame = tk.Frame(self.pencere, bg=self.bg_color, padx=20, pady=15)
        main_frame.pack(fill="both", expand=True)

        # Sol panel - Kullanıcı listesi
        sol_panel = tk.Frame(main_frame, bg='white', padx=10, pady=10)
        sol_panel.pack(side="left", fill="both", expand=True)

        # Liste başlığı
        liste_baslik_frame = tk.Frame(sol_panel, bg='white')
        liste_baslik_frame.pack(fill="x", pady=(0, 10))

        liste_baslik = tk.Label(
            liste_baslik_frame,
            text="Kullanıcı Listesi",
            font=("Arial", 12, "bold"),
            bg='white',
            fg='#333'
        )
        liste_baslik.pack(side="left")

        # Yenile butonu
        yenile_btn = tk.Button(
            liste_baslik_frame,
            text="🔄",
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            bd=0,
            cursor='hand2',
            command=self.kullanici_listesini_yenile
        )
        yenile_btn.pack(side="right")

        # Treeview (liste)
        columns = ('id', 'kullanici', 'ad_soyad', 'profil', 'durum', 'son_giris')
        self.tree = ttk.Treeview(sol_panel, columns=columns, show='headings', height=15)

        # Kolon başlıkları
        self.tree.heading('id', text='ID')
        self.tree.heading('kullanici', text='Kullanıcı Adı')
        self.tree.heading('ad_soyad', text='Ad Soyad')
        self.tree.heading('profil', text='Profil')
        self.tree.heading('durum', text='Durum')
        self.tree.heading('son_giris', text='Son Giriş')

        # Kolon genişlikleri
        self.tree.column('id', width=40, anchor='center')
        self.tree.column('kullanici', width=100)
        self.tree.column('ad_soyad', width=120)
        self.tree.column('profil', width=80, anchor='center')
        self.tree.column('durum', width=60, anchor='center')
        self.tree.column('son_giris', width=120)

        # Scrollbar
        scrollbar = ttk.Scrollbar(sol_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Seçim event
        self.tree.bind('<<TreeviewSelect>>', self.kullanici_secildi)

        # Sağ panel - İşlemler (scrollable)
        sag_container = tk.Frame(main_frame, bg=self.bg_color, width=280)
        sag_container.pack(side="right", fill="y")
        sag_container.pack_propagate(False)

        # Canvas ve scrollbar
        sag_canvas = tk.Canvas(sag_container, bg=self.bg_color, highlightthickness=0, width=260)
        sag_scrollbar = ttk.Scrollbar(sag_container, orient="vertical", command=sag_canvas.yview)
        sag_panel = tk.Frame(sag_canvas, bg=self.bg_color, padx=10)

        sag_panel.bind(
            "<Configure>",
            lambda e: sag_canvas.configure(scrollregion=sag_canvas.bbox("all"))
        )

        sag_canvas.create_window((0, 0), window=sag_panel, anchor="nw")
        sag_canvas.configure(yscrollcommand=sag_scrollbar.set)

        # Mouse wheel for sag panel
        def on_sag_mousewheel(event):
            sag_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        sag_canvas.bind("<MouseWheel>", on_sag_mousewheel)
        sag_panel.bind("<MouseWheel>", on_sag_mousewheel)

        sag_canvas.pack(side="left", fill="both", expand=True)
        sag_scrollbar.pack(side="right", fill="y")

        # Yeni Kullanıcı Ekle
        yeni_frame = tk.LabelFrame(sag_panel, text="Yeni Kullanıcı", bg='white', padx=15, pady=10)
        yeni_frame.pack(fill="x", pady=(0, 10))

        # Kullanıcı adı
        tk.Label(yeni_frame, text="Kullanıcı Adı:", bg='white', anchor='w').pack(fill="x")
        self.yeni_kullanici_entry = ttk.Entry(yeni_frame, width=25)
        self.yeni_kullanici_entry.pack(fill="x", pady=(2, 8))

        # Ad Soyad
        tk.Label(yeni_frame, text="Ad Soyad:", bg='white', anchor='w').pack(fill="x")
        self.yeni_adsoyad_entry = ttk.Entry(yeni_frame, width=25)
        self.yeni_adsoyad_entry.pack(fill="x", pady=(2, 8))

        # Şifre
        tk.Label(yeni_frame, text="Şifre (min 6 karakter):", bg='white', anchor='w').pack(fill="x")
        self.yeni_sifre_entry = ttk.Entry(yeni_frame, width=25, show="●")
        self.yeni_sifre_entry.pack(fill="x", pady=(2, 8))

        # Profil seçimi
        tk.Label(yeni_frame, text="Profil:", bg='white', anchor='w').pack(fill="x")
        self.yeni_profil_combo = ttk.Combobox(
            yeni_frame,
            width=23,
            values=list(KullaniciYonetimi.PROFILLER.values()),
            state='readonly'
        )
        self.yeni_profil_combo.set("Stajyer")
        self.yeni_profil_combo.pack(fill="x", pady=(2, 10))

        # Ekle butonu
        ekle_btn = tk.Button(
            yeni_frame,
            text="➕ Kullanıcı Ekle",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            activebackground='#388E3C',
            cursor='hand2',
            bd=0,
            pady=8,
            command=self.kullanici_ekle
        )
        ekle_btn.pack(fill="x")

        # Seçili Kullanıcı İşlemleri
        islem_frame = tk.LabelFrame(sag_panel, text="Seçili Kullanıcı İşlemleri", bg='white', padx=15, pady=10)
        islem_frame.pack(fill="x", pady=(0, 10))

        # Yetki düzenle
        self.yetki_btn = tk.Button(
            islem_frame,
            text="🔑 Yetkileri Düzenle",
            font=("Arial", 10),
            bg='#2196F3',
            fg='white',
            activebackground='#1976D2',
            cursor='hand2',
            bd=0,
            pady=8,
            state='disabled',
            command=self.yetki_duzenle
        )
        self.yetki_btn.pack(fill="x", pady=(0, 8))

        # Şifre değiştir
        self.sifre_btn = tk.Button(
            islem_frame,
            text="🔒 Şifre Değiştir",
            font=("Arial", 10),
            bg='#FF9800',
            fg='white',
            activebackground='#F57C00',
            cursor='hand2',
            bd=0,
            pady=8,
            state='disabled',
            command=self.sifre_degistir
        )
        self.sifre_btn.pack(fill="x", pady=(0, 8))

        # Profil değiştir
        self.profil_btn = tk.Button(
            islem_frame,
            text="👤 Profil Değiştir",
            font=("Arial", 10),
            bg='#9C27B0',
            fg='white',
            activebackground='#7B1FA2',
            cursor='hand2',
            bd=0,
            pady=8,
            state='disabled',
            command=self.profil_degistir
        )
        self.profil_btn.pack(fill="x", pady=(0, 8))

        # Aktif/Pasif yap
        self.durum_btn = tk.Button(
            islem_frame,
            text="🔄 Aktif/Pasif Yap",
            font=("Arial", 10),
            bg='#607D8B',
            fg='white',
            activebackground='#455A64',
            cursor='hand2',
            bd=0,
            pady=8,
            state='disabled',
            command=self.durum_degistir
        )
        self.durum_btn.pack(fill="x")

        # Sistem Ayarları
        ayar_frame = tk.LabelFrame(sag_panel, text="Sistem Ayarları", bg='white', padx=15, pady=10)
        ayar_frame.pack(fill="x", pady=(0, 10))

        # Şifresiz kullanım checkbox
        self.sifresiz_var = tk.BooleanVar(value=self.kullanici_yonetimi.sifresiz_kullanim_aktif_mi())
        sifresiz_cb = tk.Checkbutton(
            ayar_frame,
            text="Şifresiz kullanıma izin ver",
            variable=self.sifresiz_var,
            font=("Arial", 10),
            bg='white',
            activebackground='white',
            command=self.sifresiz_ayar_degistir
        )
        sifresiz_cb.pack(fill="x")

        tk.Label(
            ayar_frame,
            text="(Açıldığında giriş ekranı\ndevre dışı kalır)",
            font=("Arial", 8),
            bg='white',
            fg='#666',
            justify='left'
        ).pack(fill="x", pady=(2, 0))

        # Kapat butonu
        kapat_btn = tk.Button(
            sag_panel,
            text="✖ Kapat",
            font=("Arial", 10),
            bg='#F44336',
            fg='white',
            activebackground='#D32F2F',
            cursor='hand2',
            bd=0,
            pady=8,
            command=self.pencere.destroy
        )
        kapat_btn.pack(fill="x", pady=(10, 0))

    def sifresiz_ayar_degistir(self):
        """Şifresiz kullanım ayarını değiştir"""
        aktif = self.sifresiz_var.get()
        if self.kullanici_yonetimi.sifresiz_kullanim_ayarla(aktif):
            durum = "aktif" if aktif else "devre dışı"
            messagebox.showinfo("Ayar Kaydedildi", f"Şifresiz kullanım {durum} edildi.\n\nBu ayar bir sonraki açılışta geçerli olacaktır.")
        else:
            messagebox.showerror("Hata", "Ayar kaydedilemedi!")
            # Checkbox'ı eski haline getir
            self.sifresiz_var.set(not aktif)

    def kullanici_listesini_yenile(self):
        """Kullanıcı listesini yenile"""
        # Listeyi temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Kullanıcıları al ve listele
        kullanicilar = self.kullanici_yonetimi.tum_kullanicilari_al()

        for k in kullanicilar:
            profil_adi = KullaniciYonetimi.PROFILLER.get(k['profil'], k['profil'])
            durum = "Aktif" if k['aktif'] else "Pasif"
            son_giris = k['son_giris'] or "-"

            self.tree.insert('', 'end', values=(
                k['id'],
                k['kullanici_adi'],
                k['ad_soyad'] or "-",
                profil_adi,
                durum,
                son_giris
            ))

    def kullanici_secildi(self, event):
        """Kullanıcı seçildiğinde"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.secili_kullanici_id = item['values'][0]

            # Butonları aktifleştir
            self.yetki_btn.config(state='normal')
            self.sifre_btn.config(state='normal')
            self.profil_btn.config(state='normal')
            self.durum_btn.config(state='normal')
        else:
            self.secili_kullanici_id = None
            self.yetki_btn.config(state='disabled')
            self.sifre_btn.config(state='disabled')
            self.profil_btn.config(state='disabled')
            self.durum_btn.config(state='disabled')

    def kullanici_ekle(self):
        """Yeni kullanıcı ekle"""
        kullanici_adi = self.yeni_kullanici_entry.get().strip()
        ad_soyad = self.yeni_adsoyad_entry.get().strip()
        sifre = self.yeni_sifre_entry.get()
        profil_adi = self.yeni_profil_combo.get()

        # Profil key'i bul
        profil = None
        for key, value in KullaniciYonetimi.PROFILLER.items():
            if value == profil_adi:
                profil = key
                break

        if not profil:
            profil = "stajyer"

        # Validasyon
        if not kullanici_adi:
            messagebox.showwarning("Uyarı", "Kullanıcı adı giriniz.")
            return

        if not sifre:
            messagebox.showwarning("Uyarı", "Şifre giriniz.")
            return

        # Kullanıcı ekle
        basarili, sonuc = self.kullanici_yonetimi.kullanici_ekle(
            kullanici_adi=kullanici_adi,
            sifre=sifre,
            ad_soyad=ad_soyad if ad_soyad else None,
            profil=profil,
            olusturan_id=self.aktif_kullanici['id']
        )

        if basarili:
            messagebox.showinfo("Başarılı", f"Kullanıcı eklendi: {kullanici_adi}")
            # Formu temizle
            self.yeni_kullanici_entry.delete(0, tk.END)
            self.yeni_adsoyad_entry.delete(0, tk.END)
            self.yeni_sifre_entry.delete(0, tk.END)
            self.yeni_profil_combo.set("Stajyer")
            # Listeyi yenile
            self.kullanici_listesini_yenile()
        else:
            messagebox.showerror("Hata", f"Kullanıcı eklenemedi:\n{sonuc}")

    def yetki_duzenle(self):
        """Seçili kullanıcının yetkilerini düzenle"""
        if not self.secili_kullanici_id:
            return

        YetkiDuzenlePenceresi(self.pencere, self.secili_kullanici_id, self.kullanici_yonetimi)

    def sifre_degistir(self):
        """Seçili kullanıcının şifresini değiştir"""
        if not self.secili_kullanici_id:
            return

        SifreDegistirPenceresi(self.pencere, self.secili_kullanici_id, self.kullanici_yonetimi)

    def profil_degistir(self):
        """Seçili kullanıcının profilini değiştir"""
        if not self.secili_kullanici_id:
            return

        ProfilDegistirPenceresi(self.pencere, self.secili_kullanici_id, self.kullanici_yonetimi, self.kullanici_listesini_yenile)

    def durum_degistir(self):
        """Seçili kullanıcıyı aktif/pasif yap"""
        if not self.secili_kullanici_id:
            return

        # Mevcut durumu bul
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            kullanici_adi = item['values'][1]
            mevcut_durum = item['values'][4]

            if kullanici_adi == "admin":
                messagebox.showwarning("Uyarı", "Admin kullanıcısının durumu değiştirilemez.")
                return

            if mevcut_durum == "Aktif":
                # Pasif yap
                if messagebox.askyesno("Onay", f"'{kullanici_adi}' kullanıcısını pasif yapmak istiyor musunuz?"):
                    basarili, mesaj = self.kullanici_yonetimi.kullanici_sil(self.secili_kullanici_id)
                    if basarili:
                        messagebox.showinfo("Başarılı", "Kullanıcı pasif yapıldı.")
                        self.kullanici_listesini_yenile()
                    else:
                        messagebox.showerror("Hata", mesaj)
            else:
                # Aktif yap
                if messagebox.askyesno("Onay", f"'{kullanici_adi}' kullanıcısını aktif yapmak istiyor musunuz?"):
                    basarili, mesaj = self.kullanici_yonetimi.kullanici_aktiflestir(self.secili_kullanici_id)
                    if basarili:
                        messagebox.showinfo("Başarılı", "Kullanıcı aktif yapıldı.")
                        self.kullanici_listesini_yenile()
                    else:
                        messagebox.showerror("Hata", mesaj)


class YetkiDuzenlePenceresi:
    """Kullanıcı yetkilerini düzenleme penceresi"""

    def __init__(self, parent, kullanici_id, kullanici_yonetimi):
        self.kullanici_id = kullanici_id
        self.kullanici_yonetimi = kullanici_yonetimi

        self.pencere = tk.Toplevel(parent)
        self.pencere.title("Yetki Düzenleme")
        self.pencere.geometry("400x450")
        self.pencere.resizable(False, False)
        self.pencere.transient(parent)
        self.pencere.grab_set()

        # Ortala
        ekran_genislik = self.pencere.winfo_screenwidth()
        ekran_yukseklik = self.pencere.winfo_screenheight()
        x = (ekran_genislik - 400) // 2
        y = (ekran_yukseklik - 450) // 2
        self.pencere.geometry(f"400x450+{x}+{y}")

        self.yetki_vars = {}
        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Arayüz oluştur"""
        # Başlık
        header = tk.Frame(self.pencere, bg='#1565C0', height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔑 Modül Yetkileri",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(pady=12)

        # İçerik
        content = tk.Frame(self.pencere, bg='white', padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Mevcut yetkileri al
        yetkiler = self.kullanici_yonetimi.kullanici_yetkilerini_al(self.kullanici_id)

        # Her modül için checkbox
        for modul_key, modul_adi in KullaniciYonetimi.MODULLER.items():
            var = tk.BooleanVar(value=yetkiler.get(modul_key, False))
            self.yetki_vars[modul_key] = var

            cb = tk.Checkbutton(
                content,
                text=modul_adi,
                variable=var,
                font=("Arial", 11),
                bg='white',
                activebackground='white',
                anchor='w'
            )
            cb.pack(fill="x", pady=5)

        # Butonlar
        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(fill="x", pady=(20, 0))

        kaydet_btn = tk.Button(
            btn_frame,
            text="💾 Kaydet",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.kaydet
        )
        kaydet_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        iptal_btn = tk.Button(
            btn_frame,
            text="✖ İptal",
            font=("Arial", 10),
            bg='#F44336',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.pencere.destroy
        )
        iptal_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def kaydet(self):
        """Yetkileri kaydet"""
        yetkiler = {key: var.get() for key, var in self.yetki_vars.items()}

        basarili = self.kullanici_yonetimi.kullanici_yetkilerini_guncelle(self.kullanici_id, yetkiler)

        if basarili:
            messagebox.showinfo("Başarılı", "Yetkiler güncellendi.")
            self.pencere.destroy()
        else:
            messagebox.showerror("Hata", "Yetkiler güncellenemedi.")


class SifreDegistirPenceresi:
    """Şifre değiştirme penceresi"""

    def __init__(self, parent, kullanici_id, kullanici_yonetimi):
        self.kullanici_id = kullanici_id
        self.kullanici_yonetimi = kullanici_yonetimi

        self.pencere = tk.Toplevel(parent)
        self.pencere.title("Şifre Değiştir")
        self.pencere.geometry("350x250")
        self.pencere.resizable(False, False)
        self.pencere.transient(parent)
        self.pencere.grab_set()

        # Ortala
        ekran_genislik = self.pencere.winfo_screenwidth()
        ekran_yukseklik = self.pencere.winfo_screenheight()
        x = (ekran_genislik - 350) // 2
        y = (ekran_yukseklik - 250) // 2
        self.pencere.geometry(f"350x250+{x}+{y}")

        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Arayüz oluştur"""
        # Başlık
        header = tk.Frame(self.pencere, bg='#FF9800', height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔒 Şifre Değiştir",
            font=("Arial", 14, "bold"),
            bg='#FF9800',
            fg='white'
        ).pack(pady=12)

        # İçerik
        content = tk.Frame(self.pencere, bg='white', padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Yeni şifre
        tk.Label(content, text="Yeni Şifre (min 6 karakter):", bg='white', anchor='w').pack(fill="x")
        self.sifre_entry = ttk.Entry(content, show="●")
        self.sifre_entry.pack(fill="x", pady=(5, 15))

        # Şifre tekrar
        tk.Label(content, text="Şifre Tekrar:", bg='white', anchor='w').pack(fill="x")
        self.sifre_tekrar_entry = ttk.Entry(content, show="●")
        self.sifre_tekrar_entry.pack(fill="x", pady=(5, 20))

        # Butonlar
        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(fill="x")

        kaydet_btn = tk.Button(
            btn_frame,
            text="💾 Değiştir",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.kaydet
        )
        kaydet_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        iptal_btn = tk.Button(
            btn_frame,
            text="✖ İptal",
            font=("Arial", 10),
            bg='#F44336',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.pencere.destroy
        )
        iptal_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def kaydet(self):
        """Şifreyi değiştir"""
        sifre = self.sifre_entry.get()
        sifre_tekrar = self.sifre_tekrar_entry.get()

        if sifre != sifre_tekrar:
            messagebox.showwarning("Uyarı", "Şifreler eşleşmiyor!")
            return

        basarili, mesaj = self.kullanici_yonetimi.sifre_degistir(self.kullanici_id, sifre)

        if basarili:
            messagebox.showinfo("Başarılı", "Şifre değiştirildi.")
            self.pencere.destroy()
        else:
            messagebox.showerror("Hata", mesaj)


class ProfilDegistirPenceresi:
    """Profil değiştirme penceresi"""

    def __init__(self, parent, kullanici_id, kullanici_yonetimi, yenile_callback):
        self.kullanici_id = kullanici_id
        self.kullanici_yonetimi = kullanici_yonetimi
        self.yenile_callback = yenile_callback

        self.pencere = tk.Toplevel(parent)
        self.pencere.title("Profil Değiştir")
        self.pencere.geometry("350x200")
        self.pencere.resizable(False, False)
        self.pencere.transient(parent)
        self.pencere.grab_set()

        # Ortala
        ekran_genislik = self.pencere.winfo_screenwidth()
        ekran_yukseklik = self.pencere.winfo_screenheight()
        x = (ekran_genislik - 350) // 2
        y = (ekran_yukseklik - 200) // 2
        self.pencere.geometry(f"350x200+{x}+{y}")

        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Arayüz oluştur"""
        # Başlık
        header = tk.Frame(self.pencere, bg='#9C27B0', height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="👤 Profil Değiştir",
            font=("Arial", 14, "bold"),
            bg='#9C27B0',
            fg='white'
        ).pack(pady=12)

        # İçerik
        content = tk.Frame(self.pencere, bg='white', padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Profil seçimi
        tk.Label(content, text="Yeni Profil:", bg='white', anchor='w').pack(fill="x")
        self.profil_combo = ttk.Combobox(
            content,
            values=list(KullaniciYonetimi.PROFILLER.values()),
            state='readonly'
        )
        self.profil_combo.pack(fill="x", pady=(5, 20))

        # Butonlar
        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(fill="x")

        kaydet_btn = tk.Button(
            btn_frame,
            text="💾 Değiştir",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.kaydet
        )
        kaydet_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        iptal_btn = tk.Button(
            btn_frame,
            text="✖ İptal",
            font=("Arial", 10),
            bg='#F44336',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.pencere.destroy
        )
        iptal_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def kaydet(self):
        """Profili değiştir"""
        profil_adi = self.profil_combo.get()

        if not profil_adi:
            messagebox.showwarning("Uyarı", "Profil seçiniz.")
            return

        # Profil key'i bul
        profil = None
        for key, value in KullaniciYonetimi.PROFILLER.items():
            if value == profil_adi:
                profil = key
                break

        if not profil:
            messagebox.showerror("Hata", "Geçersiz profil.")
            return

        basarili, mesaj = self.kullanici_yonetimi.kullanici_guncelle(self.kullanici_id, profil=profil)

        if basarili:
            messagebox.showinfo("Başarılı", "Profil değiştirildi.")
            self.pencere.destroy()
            if self.yenile_callback:
                self.yenile_callback()
        else:
            messagebox.showerror("Hata", mesaj)
