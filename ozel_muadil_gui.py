"""
Özel Muadil Grupları Penceresi
==============================
İlaç-dışı ürünleri (Botanik'te UrunEsdegerId'si olmayan) kendi aramızda
"muadil" kabul edip ortak bir kod/ad altında konsolide değerlendirmek için.

Botanik EOS'a YAZILMAZ (kırmızı çizgi) — eşleme yalnızca yerel SQLite
(siparis_db.ozel_muadil_gruplari) tablosunda tutulur. Sipariş tablosu ve
raporlar bu ortak kodu paylaşan ürünleri tek grup gibi gösterir.

Kaynak ürün listesi: Sipariş Ver'in o an yüklü analiz verisi (tum_veriler).
İlaç-dışı ürünleri görmek için önce ürün tipi seçip "Verileri Getir" ile
listeyi doldurmak gerekir.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


class OzelMuadilGUI:
    def __init__(self, parent, urunler, db):
        """
        Args:
            parent: Üst pencere.
            urunler: [{'UrunId','UrunAdi','EsdegerId',...}, ...] (tum_veriler).
            db: get_siparis_db() örneği.
        """
        self.parent = parent
        self.db = db
        # UrunId → ad (tekilleştir)
        self.urun_map = {}
        for u in (urunler or []):
            uid = u.get('UrunId')
            if uid is not None and uid not in self.urun_map:
                self.urun_map[uid] = u.get('UrunAdi', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Özel Muadil Grupları (İlaç-dışı Ortak Kod)")
        self.window.geometry("1000x680")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.window)
        except Exception:
            pass

        self._ui_olustur()
        self._urun_listesi_doldur()
        self._gruplari_yenile()

    def _ui_olustur(self):
        # Üst açıklama
        tk.Label(
            self.window,
            text=("İlaç-dışı ürünleri ortak kodla grupla → sipariş tablosu ve "
                  "raporlarda konsolide görünür. (Botanik'e yazılmaz, yerel eşleme.)"),
            font=('Arial', 9), fg='#00695C', wraplength=980, justify='left'
        ).pack(fill=tk.X, padx=10, pady=(8, 4))

        orta = tk.Frame(self.window)
        orta.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # ── Sol: ürün seçimi ────────────────────────────────────────────
        sol = tk.LabelFrame(orta, text="1) Ürün seç (çoklu)", font=('Arial', 9, 'bold'))
        sol.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        arama_fr = tk.Frame(sol)
        arama_fr.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(arama_fr, text="🔍", font=('Arial', 10)).pack(side=tk.LEFT)
        self.arama_var = tk.StringVar()
        self.arama_var.trace('w', lambda *a: self._urun_listesi_doldur())
        tk.Entry(arama_fr, textvariable=self.arama_var, font=('Arial', 9)).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        liste_fr = tk.Frame(sol)
        liste_fr.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.urun_liste = tk.Listbox(liste_fr, selectmode=tk.EXTENDED, font=('Arial', 9))
        usb = ttk.Scrollbar(liste_fr, orient='vertical', command=self.urun_liste.yview)
        self.urun_liste.configure(yscrollcommand=usb.set)
        self.urun_liste.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        usb.pack(side=tk.RIGHT, fill=tk.Y)
        self._liste_uidler = []  # listbox index → UrunId

        # ── Orta: kod/ad girişi + ata ───────────────────────────────────
        ortacol = tk.Frame(orta)
        ortacol.pack(side=tk.LEFT, fill=tk.Y, padx=6)
        tk.Label(ortacol, text="2) Ortak kod / ad", font=('Arial', 9, 'bold')).pack(pady=(30, 4))
        tk.Label(ortacol, text="Ortak Kod:", font=('Arial', 9)).pack(anchor='w')
        self.kod_var = tk.StringVar()
        tk.Entry(ortacol, textvariable=self.kod_var, font=('Arial', 9), width=22).pack()
        tk.Label(ortacol, text="Ortak Ad (opsiyonel):", font=('Arial', 9)).pack(anchor='w', pady=(8, 0))
        self.ad_var = tk.StringVar()
        tk.Entry(ortacol, textvariable=self.ad_var, font=('Arial', 9), width=22).pack()
        tk.Button(ortacol, text="➕ Seçilenlere Ata", command=self._ata,
                  bg='#2E7D32', fg='white', font=('Arial', 9, 'bold'),
                  relief='raised', padx=10, pady=6).pack(pady=16, fill=tk.X)
        tk.Label(ortacol, text="(Mevcut gruba eklemek için\no grubun kodunu yaz)",
                 font=('Arial', 8), fg='#666').pack()

        # ── Sağ: mevcut gruplar ─────────────────────────────────────────
        sag = tk.LabelFrame(orta, text="Mevcut gruplar", font=('Arial', 9, 'bold'))
        sag.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self.grup_tree = ttk.Treeview(sag, columns=('kod', 'ad', 'adet'),
                                      show='headings', height=18)
        self.grup_tree.heading('kod', text='Kod')
        self.grup_tree.heading('ad', text='Ad')
        self.grup_tree.heading('adet', text='Ürün')
        self.grup_tree.column('kod', width=120)
        self.grup_tree.column('ad', width=180)
        self.grup_tree.column('adet', width=45, anchor='center')
        self.grup_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.grup_tree.bind('<<TreeviewSelect>>', self._grup_secildi)

        self.uye_label = tk.Label(sag, text="", font=('Arial', 8), fg='#333',
                                  wraplength=340, justify='left', anchor='w')
        self.uye_label.pack(fill=tk.X, padx=4)

        grup_btn = tk.Frame(sag)
        grup_btn.pack(fill=tk.X, padx=4, pady=4)
        tk.Button(grup_btn, text="🗑 Grubu Dağıt", command=self._grup_sil,
                  bg='#C62828', fg='white', font=('Arial', 8), relief='flat',
                  padx=8).pack(side=tk.LEFT)

        # Alt kapat
        tk.Button(self.window, text="Kapat", command=self.window.destroy,
                  bg='#455A64', fg='white', font=('Arial', 9), relief='flat',
                  padx=16, pady=4).pack(side=tk.RIGHT, padx=10, pady=6)

    def _urun_listesi_doldur(self):
        ara = self.arama_var.get().strip().lower()
        self.urun_liste.delete(0, tk.END)
        self._liste_uidler = []
        for uid, ad in sorted(self.urun_map.items(), key=lambda x: x[1]):
            if ara and ara not in ad.lower():
                continue
            self.urun_liste.insert(tk.END, f"{ad}  [#{uid}]")
            self._liste_uidler.append(uid)

    def _ata(self):
        kod = self.kod_var.get().strip()
        if not kod:
            messagebox.showwarning("Eksik", "Ortak kod girin.", parent=self.window)
            return
        secili = self.urun_liste.curselection()
        if not secili:
            messagebox.showwarning("Eksik", "Soldan en az bir ürün seçin.",
                                   parent=self.window)
            return
        urunler = [{'urun_id': self._liste_uidler[i],
                    'urun_adi': self.urun_map.get(self._liste_uidler[i], '')}
                   for i in secili]
        n = self.db.ozel_muadil_ata(kod, self.ad_var.get().strip() or kod, urunler)
        if n:
            messagebox.showinfo(
                "Tamam",
                f"{n} ürün '{kod}' grubuna atandı.\n\n"
                "Sipariş tablosunu yenilediğinizde konsolide görünecek.",
                parent=self.window)
            self.kod_var.set(''); self.ad_var.set('')
            self._gruplari_yenile()
        else:
            messagebox.showerror("Hata", "Atama başarısız.", parent=self.window)

    def _gruplari_yenile(self):
        self.grup_tree.delete(*self.grup_tree.get_children())
        self._gruplar = self.db.ozel_muadil_gruplari_getir()
        for kod, bilgi in sorted(self._gruplar.items()):
            self.grup_tree.insert('', tk.END, iid=kod, values=(
                kod, bilgi.get('ad', kod), len(bilgi.get('urunler', []))))
        self.uye_label.config(text="")

    def _grup_secildi(self, event=None):
        sel = self.grup_tree.selection()
        if not sel:
            return
        kod = sel[0]
        bilgi = getattr(self, '_gruplar', {}).get(kod, {})
        adlar = [u.get('urun_adi', '') for u in bilgi.get('urunler', [])]
        self.uye_label.config(text="Üyeler: " + ", ".join(adlar))

    def _grup_sil(self):
        sel = self.grup_tree.selection()
        if not sel:
            messagebox.showinfo("Bilgi", "Önce bir grup seçin.", parent=self.window)
            return
        kod = sel[0]
        if messagebox.askyesno(
                "Grubu Dağıt",
                f"'{kod}' grubundaki tüm ürün eşlemeleri silinsin mi?\n"
                "(Ürünler tekrar tek tek gösterilir.)", parent=self.window):
            self.db.ozel_muadil_grup_sil(kod)
            self._gruplari_yenile()
