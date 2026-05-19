"""
Endeks Ayarları Modülü (Faz 3)

Endeks tanımlarını, tarihsel değerlerini ve sepetleri yönetir.

Üç sekme:
1. Endeksler — tanım listesi (kategori bazlı), ekle/sil/düzenle, değer tarihçesi
2. Sepetler — birden fazla endeksin ağırlıklı ortalaması (örn. "Dolar+Euro")
3. Botanik Sync — ilaç endekslerini Botanik DB'den geriye dönük doldur
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import logging
import threading
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    TKCALENDAR_AVAILABLE = False

logger = logging.getLogger(__name__)


KATEGORI_ETIKETLERI = {
    'para':    'Para (Döviz/Altın)',
    'ucret':   'Ücret',
    'mal':     'Mal (Benzin vs.)',
    'ilac':    'İlaç (Botanik PSF)',
    'kira_vs': 'Diğer (Kira vs.)',
}


class EndeksAyarlariGUI:
    """Endeks tanım/değer/sepet yönetim penceresi."""

    def __init__(self, root, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback
        self.root.title("Endeks Ayarları")
        try:
            self.root.state('zoomed')
        except Exception:
            self.root.geometry("1200x700")

        self.bg_color = '#F5F5F5'
        self.header_color = '#5D4037'
        self.fg_color = 'white'
        self.root.configure(bg=self.bg_color)

        self.db = None
        self.botanik_db = None
        self.secili_endeks_id: Optional[int] = None
        self.secili_sepet_id: Optional[int] = None

        self._arayuz_olustur()
        self._db_baglan()

    # ------------------------------------------------------------------
    # Arayüz
    # ------------------------------------------------------------------
    def _arayuz_olustur(self):
        self._header_olustur()

        # Tab sistem
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._endeksler_sekmesi()
        self._sepetler_sekmesi()
        self._botanik_sync_sekmesi()

        self._status_bar_olustur()

    def _header_olustur(self):
        header = tk.Frame(self.root, bg=self.header_color, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="📈 Endeks Ayarları",
            font=("Segoe UI", 14, "bold"), bg=self.header_color, fg=self.fg_color
        ).pack(side="left", padx=15, pady=10)

        tk.Button(header, text="✕ Kapat", bg='#C62828', fg='white', bd=0,
                  font=("Segoe UI", 9), cursor='hand2', padx=12,
                  command=self._kapat).pack(side="right", padx=10, pady=10)

    def _status_bar_olustur(self):
        bar = tk.Frame(self.root, bg='#37474F', height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_lbl = tk.Label(bar, text="Hazır.", bg='#37474F', fg='white',
                                    font=("Segoe UI", 9), anchor='w', padx=10)
        self.status_lbl.pack(side="left", fill="x", expand=True)

    def _status(self, m: str, hata: bool = False):
        self.status_lbl.config(text=m, fg='#FFCDD2' if hata else 'white')

    def _kapat(self):
        try:
            self.root.destroy()
        finally:
            if self.ana_menu_callback:
                try: self.ana_menu_callback()
                except Exception: pass

    # ------------------------------------------------------------------
    # Sekme 1: Endeksler
    # ------------------------------------------------------------------
    def _endeksler_sekmesi(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Endeksler")

        # Sol: endeks listesi
        sol = ttk.Frame(tab)
        sol.pack(side="left", fill="both", expand=False, padx=5, pady=5)

        ttk.Label(sol, text="Endeks Listesi", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        liste_frame = ttk.Frame(sol)
        liste_frame.pack(fill="both", expand=True)

        self.endeks_tree = ttk.Treeview(
            liste_frame, columns=('kod', 'ad', 'birim', 'kategori', 'kaynak'),
            show='headings', height=22, selectmode='browse'
        )
        for col, txt, w in [('kod', 'Kod', 110), ('ad', 'Ad', 200),
                             ('birim', 'Birim', 60), ('kategori', 'Kategori', 90),
                             ('kaynak', 'Kaynak', 110)]:
            self.endeks_tree.heading(col, text=txt)
            self.endeks_tree.column(col, width=w, anchor='w')
        self.endeks_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(liste_frame, orient="vertical", command=self.endeks_tree.yview)
        sb.pack(side="right", fill="y")
        self.endeks_tree.configure(yscrollcommand=sb.set)
        self.endeks_tree.bind('<<TreeviewSelect>>', self._endeks_secildi)

        # Liste alt butonları
        btn_frame = ttk.Frame(sol)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="➕ Yeni Endeks", command=self._endeks_ekle_dlg, width=14
                   ).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✏ Düzenle", command=self._endeks_duzenle_dlg, width=10
                   ).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 Sil", command=self._endeks_sil, width=8
                   ).pack(side="left", padx=2)

        # Sağ: seçili endeksin değer tarihçesi
        sag = ttk.Frame(tab)
        sag.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        ttk.Label(sag, text="Değer Tarihçesi", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        deger_frame = ttk.Frame(sag)
        deger_frame.pack(fill="both", expand=True)

        self.deger_tree = ttk.Treeview(
            deger_frame, columns=('tarih', 'deger', 'kaynak'),
            show='headings', height=22
        )
        for col, txt, w in [('tarih', 'Tarih', 140), ('deger', 'Değer', 140),
                             ('kaynak', 'Kaynak', 140)]:
            self.deger_tree.heading(col, text=txt)
            self.deger_tree.column(col, width=w, anchor='center')
        self.deger_tree.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(deger_frame, orient="vertical", command=self.deger_tree.yview)
        sb2.pack(side="right", fill="y")
        self.deger_tree.configure(yscrollcommand=sb2.set)

        # Değer alt butonları
        deger_btn = ttk.Frame(sag)
        deger_btn.pack(fill="x", pady=5)
        ttk.Button(deger_btn, text="➕ Değer Ekle/Güncelle",
                   command=self._deger_ekle_dlg, width=22).pack(side="left", padx=2)
        ttk.Button(deger_btn, text="🗑 Değer Sil",
                   command=self._deger_sil, width=12).pack(side="left", padx=2)
        ttk.Button(deger_btn, text="📥 CSV İçe Aktar",
                   command=self._csv_import, width=15).pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Sekme 2: Sepetler
    # ------------------------------------------------------------------
    def _sepetler_sekmesi(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sepetler")

        # Sol: sepet listesi
        sol = ttk.Frame(tab)
        sol.pack(side="left", fill="both", expand=False, padx=5, pady=5)
        ttk.Label(sol, text="Sepet Listesi", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.sepet_listesi = tk.Listbox(sol, width=30, height=22, font=("Segoe UI", 10))
        self.sepet_listesi.pack(fill="both", expand=True)
        self.sepet_listesi.bind('<<ListboxSelect>>', self._sepet_secildi)

        btn = ttk.Frame(sol)
        btn.pack(fill="x", pady=5)
        ttk.Button(btn, text="➕ Yeni Sepet", command=self._sepet_ekle_dlg, width=14
                   ).pack(side="left", padx=2)
        ttk.Button(btn, text="🗑 Sil", command=self._sepet_sil, width=8
                   ).pack(side="left", padx=2)

        # Sağ: sepet üyeleri
        sag = ttk.Frame(tab)
        sag.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ttk.Label(sag, text="Sepet Üyeleri (ağırlık ile)", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        uye_frame = ttk.Frame(sag)
        uye_frame.pack(fill="both", expand=True)
        self.uye_tree = ttk.Treeview(
            uye_frame, columns=('kod', 'ad', 'kategori', 'agirlik'),
            show='headings', height=22
        )
        for col, txt, w in [('kod','Kod',110),('ad','Ad',200),
                             ('kategori','Kategori',100),('agirlik','Ağırlık',80)]:
            self.uye_tree.heading(col, text=txt)
            self.uye_tree.column(col, width=w, anchor='w')
        self.uye_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(uye_frame, orient="vertical", command=self.uye_tree.yview)
        sb.pack(side="right", fill="y")
        self.uye_tree.configure(yscrollcommand=sb.set)

        # Üye butonları
        uye_btn = ttk.Frame(sag)
        uye_btn.pack(fill="x", pady=5)
        ttk.Button(uye_btn, text="➕ Endeks Ekle (sepete)",
                   command=self._sepete_ekle_dlg, width=22).pack(side="left", padx=2)
        ttk.Button(uye_btn, text="🗑 Çıkar", command=self._sepetten_cikar, width=10
                   ).pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Sekme 3: Botanik İlaç Sync
    # ------------------------------------------------------------------
    def _botanik_sync_sekmesi(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Botanik İlaç Sync")

        ttk.Label(
            tab, text="İlaç endekslerini Botanik DB'den (RIEtiketFiyati) geriye dönük doldur.",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=10)

        ttk.Label(
            tab, text="Bir ilaç endeksi seç → arama ile Botanik UrunId eşle → tarih aralığı seç → Sync.",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=10)

        form = ttk.Frame(tab)
        form.pack(fill="x", padx=10, pady=10)

        # Endeks seçim
        ttk.Label(form, text="Endeks:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        self.sync_endeks_combo = ttk.Combobox(form, width=40, state="readonly")
        self.sync_endeks_combo.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        self.sync_endeks_combo.bind('<<ComboboxSelected>>', self._sync_endeks_secildi)

        ttk.Label(form, text="Botanik UrunId:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.sync_urunid_entry = ttk.Entry(form, width=10)
        self.sync_urunid_entry.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(form, text="Veya ara:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        self.sync_arama_entry = ttk.Entry(form, width=30)
        self.sync_arama_entry.grid(row=2, column=1, sticky="w", padx=5, pady=4)
        ttk.Button(form, text="🔍 Ara", command=self._urun_ara, width=10
                   ).grid(row=2, column=2, sticky="w", padx=5, pady=4)

        # Sonuç listesi
        self.urun_sonuc_tree = ttk.Treeview(
            tab, columns=('id', 'ad', 'fiyat'), show='headings', height=10
        )
        for col, txt, w in [('id','UrunId',80),('ad','Ürün Adı',400),('fiyat','Güncel PSF',100)]:
            self.urun_sonuc_tree.heading(col, text=txt)
            self.urun_sonuc_tree.column(col, width=w, anchor='w')
        self.urun_sonuc_tree.pack(fill="x", padx=10, pady=5)
        self.urun_sonuc_tree.bind('<Double-1>', self._urun_secildi)

        # Tarih ve sync butonu
        tarih_frame = ttk.Frame(tab)
        tarih_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(tarih_frame, text="Tarih Aralığı:").pack(side="left")
        if TKCALENDAR_AVAILABLE:
            self.sync_bas = DateEntry(tarih_frame, date_pattern='dd.mm.yyyy', width=12, locale='tr_TR')
            self.sync_bas.set_date(date(2017, 5, 23))
            self.sync_bit = DateEntry(tarih_frame, date_pattern='dd.mm.yyyy', width=12, locale='tr_TR')
            self.sync_bit.set_date(datetime.now())
        else:
            self.sync_bas = ttk.Entry(tarih_frame, width=12)
            self.sync_bas.insert(0, "23.05.2017")
            self.sync_bit = ttk.Entry(tarih_frame, width=12)
            self.sync_bit.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.sync_bas.pack(side="left", padx=5)
        ttk.Label(tarih_frame, text="→").pack(side="left")
        self.sync_bit.pack(side="left", padx=5)

        ttk.Button(tarih_frame, text="🔄 Botanik'ten Sync Et (aylık)",
                   command=self._botanik_sync_calistir, width=28).pack(side="left", padx=20)

        # Sonuç paneli
        self.sync_log = tk.Text(tab, height=15, font=("Consolas", 9), bg='#F5F5F5')
        self.sync_log.pack(fill="both", expand=True, padx=10, pady=5)

    # ------------------------------------------------------------------
    # DB
    # ------------------------------------------------------------------
    def _db_baglan(self):
        try:
            from endeksler_db import get_endeks_db
            self.db = get_endeks_db()
            self._tabloyu_yenile()
            self._sepet_listesini_yenile()
            self._sync_endeks_combosunu_doldur()
            self._status(f"Endeks DB yüklendi. ({len(self.db.endeksleri_getir())} tanım)")
        except Exception as e:
            logger.error(f"EndeksDB hatası: {e}", exc_info=True)
            self._status(f"DB hatası: {e}", hata=True)

    def _botanik_db_bagla(self):
        if self.botanik_db is not None:
            return True
        try:
            from botanik_db import get_botanik_db
            self.botanik_db = get_botanik_db()
            if not self.botanik_db.baglan():
                self._status("Botanik EOS bağlantısı kurulamadı.", hata=True)
                return False
            return True
        except Exception as e:
            logger.error(f"Botanik DB hatası: {e}")
            self._status(f"Botanik DB hatası: {e}", hata=True)
            return False

    # ------------------------------------------------------------------
    # Endeks listesi işlemleri
    # ------------------------------------------------------------------
    def _tabloyu_yenile(self):
        for c in self.endeks_tree.get_children():
            self.endeks_tree.delete(c)
        if self.db is None:
            return
        for e in self.db.endeksleri_getir():
            self.endeks_tree.insert('', 'end',
                values=(e['kod'], e['ad'], e['birim'] or '',
                        KATEGORI_ETIKETLERI.get(e['kategori'], e['kategori']),
                        e['kaynak']),
                iid=str(e['id'])
            )

    def _endeks_secildi(self, _evt):
        sec = self.endeks_tree.selection()
        if not sec:
            self.secili_endeks_id = None
            return
        try:
            self.secili_endeks_id = int(sec[0])
        except ValueError:
            return
        self._degerleri_yenile()

    def _degerleri_yenile(self):
        for c in self.deger_tree.get_children():
            self.deger_tree.delete(c)
        if self.db is None or self.secili_endeks_id is None:
            return
        degerler = self.db.degerleri_getir(self.secili_endeks_id)
        for r in degerler:
            self.deger_tree.insert('', 'end', values=(
                r['tarih'].strftime('%d.%m.%Y') if hasattr(r['tarih'], 'strftime') else r['tarih'],
                f"{r['deger']:,.4f}".rstrip('0').rstrip('.') if r['deger'] else "0",
                r.get('kaynak') or ''
            ))

    def _endeks_ekle_dlg(self):
        dlg = EndeksEkleDialog(self.root, mod='ekle')
        self.root.wait_window(dlg.top)
        if dlg.sonuc:
            try:
                self.db.endeks_ekle(**dlg.sonuc)
                self._tabloyu_yenile()
                self._sync_endeks_combosunu_doldur()
                self._status(f"Endeks eklendi: {dlg.sonuc['kod']}")
            except Exception as e:
                messagebox.showerror("Hata", f"Endeks eklenemedi:\n{e}")

    def _endeks_duzenle_dlg(self):
        if self.secili_endeks_id is None:
            messagebox.showinfo("Seçim yok", "Önce listeden endeks seçin.")
            return
        # Mevcut bilgiyi getir
        c = self.db.conn.cursor()
        row = c.execute("SELECT * FROM endeks_tanim WHERE id=?", (self.secili_endeks_id,)).fetchone()
        if not row:
            return
        dlg = EndeksEkleDialog(self.root, mod='duzenle', mevcut=dict(row))
        self.root.wait_window(dlg.top)
        if dlg.sonuc:
            sonuc = {k: v for k, v in dlg.sonuc.items() if k != 'kod'}  # kod değişmez
            try:
                self.db.endeks_guncelle(self.secili_endeks_id, **sonuc)
                self._tabloyu_yenile()
                self._status(f"Endeks güncellendi.")
            except Exception as e:
                messagebox.showerror("Hata", f"Güncellenemedi:\n{e}")

    def _endeks_sil(self):
        if self.secili_endeks_id is None:
            messagebox.showinfo("Seçim yok", "Önce endeks seçin.")
            return
        if not messagebox.askyesno("Silme onayı",
                                    "Bu endeks ve tüm değerleri silinecek. Emin misiniz?"):
            return
        try:
            self.db.endeks_sil(self.secili_endeks_id)
            self.secili_endeks_id = None
            self._tabloyu_yenile()
            self._degerleri_yenile()
            self._sync_endeks_combosunu_doldur()
            self._status("Endeks silindi.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    # ------------------------------------------------------------------
    # Değer işlemleri
    # ------------------------------------------------------------------
    def _deger_ekle_dlg(self):
        if self.secili_endeks_id is None:
            messagebox.showinfo("Seçim yok", "Önce endeks seçin.")
            return
        dlg = DegerEkleDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.sonuc:
            try:
                self.db.deger_ekle(self.secili_endeks_id, dlg.sonuc['tarih'],
                                   dlg.sonuc['deger'], kaynak='manuel')
                self._degerleri_yenile()
                self._status(f"Değer eklendi: {dlg.sonuc['tarih']} = {dlg.sonuc['deger']}")
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _deger_sil(self):
        if self.secili_endeks_id is None:
            return
        sec = self.deger_tree.selection()
        if not sec:
            messagebox.showinfo("Seçim yok", "Önce silinecek değeri seç.")
            return
        for sec_id in sec:
            vals = self.deger_tree.item(sec_id, 'values')
            if not vals:
                continue
            try:
                t = datetime.strptime(vals[0], '%d.%m.%Y').date()
                self.db.deger_sil(self.secili_endeks_id, t)
            except Exception as e:
                logger.warning(f"Değer silinemedi: {e}")
        self._degerleri_yenile()
        self._status("Seçili değer(ler) silindi.")

    def _csv_import(self):
        if self.secili_endeks_id is None:
            messagebox.showinfo("Seçim yok", "Önce endeks seçin.")
            return
        dosya = filedialog.askopenfilename(
            title="CSV Dosyası Seç",
            filetypes=[("CSV", "*.csv"), ("Tüm dosyalar", "*.*")]
        )
        if not dosya:
            return
        try:
            import csv
            with open(dosya, encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
            if rows and not rows[0][0].replace('-', '').replace('.', '').isdigit():
                rows = rows[1:]  # başlık satırını atla

            eklenen = 0
            for satir in rows:
                if len(satir) < 2:
                    continue
                try:
                    # Tarih: 2025-03-01 veya 01.03.2025
                    t_raw = satir[0].strip()
                    if '-' in t_raw:
                        t = datetime.strptime(t_raw, '%Y-%m-%d').date()
                    else:
                        t = datetime.strptime(t_raw, '%d.%m.%Y').date()
                    v = float(satir[1].replace(',', '.').strip())
                    self.db.deger_ekle(self.secili_endeks_id, t, v, kaynak='csv_import')
                    eklenen += 1
                except Exception as e:
                    logger.warning(f"CSV satır atlandı ({satir}): {e}")
            self._degerleri_yenile()
            messagebox.showinfo("Tamam", f"{eklenen} satır CSV'den içe aktarıldı.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    # ------------------------------------------------------------------
    # Sepet işlemleri
    # ------------------------------------------------------------------
    def _sepet_listesini_yenile(self):
        self.sepet_listesi.delete(0, tk.END)
        if self.db is None:
            return
        for s in self.db.sepet_listesi():
            self.sepet_listesi.insert(tk.END, f"[{s['id']}] {s['ad']}")

    def _sepet_secildi(self, _evt):
        sel = self.sepet_listesi.curselection()
        if not sel:
            self.secili_sepet_id = None
            return
        metin = self.sepet_listesi.get(sel[0])
        try:
            self.secili_sepet_id = int(metin.split(']')[0][1:])
        except Exception:
            return
        self._uyeleri_yenile()

    def _uyeleri_yenile(self):
        for c in self.uye_tree.get_children():
            self.uye_tree.delete(c)
        if self.db is None or self.secili_sepet_id is None:
            return
        for u in self.db.sepet_uyeleri_getir(self.secili_sepet_id):
            self.uye_tree.insert('', 'end',
                values=(u['kod'], u['ad'],
                        KATEGORI_ETIKETLERI.get(u['kategori'], u['kategori']),
                        f"{u['agirlik']:.2f}"),
                iid=str(u['endeks_id'])
            )

    def _sepet_ekle_dlg(self):
        ad = simpledialog.askstring("Yeni Sepet", "Sepet adı:")
        if not ad:
            return
        try:
            self.db.sepet_ekle(ad)
            self._sepet_listesini_yenile()
            self._status(f"Sepet eklendi: {ad}")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def _sepet_sil(self):
        if self.secili_sepet_id is None:
            messagebox.showinfo("Seçim yok", "Önce sepet seçin.")
            return
        if not messagebox.askyesno("Silme onayı", "Sepet silinecek. Emin misiniz?"):
            return
        try:
            self.db.sepet_sil(self.secili_sepet_id)
            self.secili_sepet_id = None
            self._sepet_listesini_yenile()
            self._uyeleri_yenile()
            self._status("Sepet silindi.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def _sepete_ekle_dlg(self):
        if self.secili_sepet_id is None:
            messagebox.showinfo("Seçim yok", "Önce sepet seçin.")
            return
        endeksler = self.db.endeksleri_getir()
        if not endeksler:
            messagebox.showinfo("Endeks yok", "Önce endeks tanımı oluşturun.")
            return

        dlg = SepetUyeDialog(self.root, endeksler)
        self.root.wait_window(dlg.top)
        if dlg.sonuc:
            try:
                self.db.sepete_endeks_ekle(self.secili_sepet_id,
                                            dlg.sonuc['endeks_id'],
                                            dlg.sonuc['agirlik'])
                self._uyeleri_yenile()
                self._status("Endeks sepete eklendi.")
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _sepetten_cikar(self):
        sec = self.uye_tree.selection()
        if not sec or self.secili_sepet_id is None:
            return
        for sec_id in sec:
            try:
                self.db.sepetten_endeks_cikar(self.secili_sepet_id, int(sec_id))
            except Exception:
                pass
        self._uyeleri_yenile()

    # ------------------------------------------------------------------
    # Botanik Sync
    # ------------------------------------------------------------------
    def _sync_endeks_combosunu_doldur(self):
        if self.db is None:
            return
        ilac_endeksleri = self.db.endeksleri_getir(kategori='ilac')
        degerler = [f"[{e['id']}] {e['kod']} - {e['ad']}" for e in ilac_endeksleri]
        self.sync_endeks_combo['values'] = degerler
        if degerler:
            self.sync_endeks_combo.set(degerler[0])

    def _sync_endeks_secildi(self, _evt):
        sec = self.sync_endeks_combo.get()
        if not sec:
            return
        try:
            endeks_id = int(sec.split(']')[0][1:])
            c = self.db.conn.cursor()
            row = c.execute("SELECT botanik_urun_id FROM endeks_tanim WHERE id=?",
                           (endeks_id,)).fetchone()
            if row and row['botanik_urun_id']:
                self.sync_urunid_entry.delete(0, tk.END)
                self.sync_urunid_entry.insert(0, str(row['botanik_urun_id']))
        except Exception:
            pass

    def _urun_ara(self):
        arama = self.sync_arama_entry.get().strip()
        if not arama:
            return
        if not self._botanik_db_bagla():
            return

        for c in self.urun_sonuc_tree.get_children():
            self.urun_sonuc_tree.delete(c)

        def _calis():
            try:
                sonuclar = self.botanik_db.urun_ara(arama, limit=50)
                self.root.after(0, lambda: self._urun_sonuclarini_goster(sonuclar))
            except Exception as e:
                logger.error(f"Ürün arama hatası: {e}")
                self.root.after(0, lambda: self._status(f"Ürün arama hatası: {e}", hata=True))

        self._status(f"Aranıyor: {arama}...")
        threading.Thread(target=_calis, daemon=True).start()

    def _urun_sonuclarini_goster(self, sonuclar: List[Dict]):
        for r in sonuclar:
            self.urun_sonuc_tree.insert('', 'end', values=(
                r.get('UrunId'),
                r.get('UrunAdi', '')[:80],
                f"{r.get('UrunFiyatEtiket') or 0:,.2f} ₺"
            ))
        self._status(f"{len(sonuclar)} ürün bulundu. Çift tıkla UrunId'yi yapıştırır.")

    def _urun_secildi(self, _evt):
        sec = self.urun_sonuc_tree.selection()
        if not sec:
            return
        vals = self.urun_sonuc_tree.item(sec[0], 'values')
        if vals:
            self.sync_urunid_entry.delete(0, tk.END)
            self.sync_urunid_entry.insert(0, vals[0])

    def _botanik_sync_calistir(self):
        sec = self.sync_endeks_combo.get()
        if not sec:
            messagebox.showinfo("Seçim yok", "Önce endeks seçin.")
            return
        try:
            endeks_id = int(sec.split(']')[0][1:])
        except Exception:
            messagebox.showerror("Hata", "Endeks ID parse edilemedi.")
            return

        urunid_str = self.sync_urunid_entry.get().strip()
        if not urunid_str.isdigit():
            messagebox.showinfo("UrunId gerek", "Botanik UrunId boş veya geçersiz.")
            return
        urun_id = int(urunid_str)

        try:
            if TKCALENDAR_AVAILABLE:
                bas = self.sync_bas.get_date()
                bit = self.sync_bit.get_date()
            else:
                bas = datetime.strptime(self.sync_bas.get(), '%d.%m.%Y').date()
                bit = datetime.strptime(self.sync_bit.get(), '%d.%m.%Y').date()
        except Exception as e:
            messagebox.showerror("Tarih hatası", str(e))
            return

        if not self._botanik_db_bagla():
            return

        # Endeks tanımına botanik_urun_id'yi de yaz
        try:
            self.db.endeks_guncelle(endeks_id, botanik_urun_id=urun_id)
        except Exception:
            pass

        self.sync_log.delete('1.0', tk.END)
        self.sync_log.insert(tk.END,
            f"Sync başladı: endeks_id={endeks_id}, UrunId={urun_id}\n"
            f"Tarih aralığı: {bas} → {bit}\n\n")
        self.sync_log.update()

        def _calis():
            try:
                eklenen = self.db.botanik_ilac_endeksi_sync(
                    endeks_id=endeks_id,
                    urun_id=urun_id,
                    baslangic=bas,
                    bitis=bit,
                    periyot='aylik',
                )
                self.root.after(0, lambda: self._sync_bitti(eklenen))
            except Exception as e:
                logger.error(f"Sync hatası: {e}", exc_info=True)
                self.root.after(0, lambda: self._sync_bitti(0, str(e)))

        threading.Thread(target=_calis, daemon=True).start()

    def _sync_bitti(self, eklenen: int, hata: str = ""):
        if hata:
            self.sync_log.insert(tk.END, f"HATA: {hata}\n")
            self._status(f"Sync hatası: {hata}", hata=True)
        else:
            self.sync_log.insert(tk.END, f"\nTamamlandı: {eklenen} aylık değer yazıldı.\n")
            self._status(f"Sync tamam: {eklenen} aylık değer.")
        # Tabloyu yenile (seçili endeks ise)
        if self.secili_endeks_id is not None:
            self._degerleri_yenile()


# ---------------------------------------------------------------------------
# Yardımcı dialoglar
# ---------------------------------------------------------------------------
class EndeksEkleDialog:
    def __init__(self, parent, mod='ekle', mevcut: Optional[Dict] = None):
        self.sonuc = None
        self.mod = mod
        self.top = tk.Toplevel(parent)
        self.top.title("Yeni Endeks" if mod == 'ekle' else "Endeks Düzenle")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=15)
        frm.pack()

        ttk.Label(frm, text="Kod (kısa, benzersiz):").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        self.kod_e = ttk.Entry(frm, width=25)
        self.kod_e.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        if mod == 'duzenle' and mevcut:
            self.kod_e.insert(0, mevcut.get('kod', ''))
            self.kod_e.config(state='readonly')

        ttk.Label(frm, text="Ad:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.ad_e = ttk.Entry(frm, width=40)
        self.ad_e.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        if mevcut: self.ad_e.insert(0, mevcut.get('ad', ''))

        ttk.Label(frm, text="Birim:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        self.birim_e = ttk.Entry(frm, width=15)
        self.birim_e.grid(row=2, column=1, sticky="w", padx=5, pady=4)
        if mevcut: self.birim_e.insert(0, mevcut.get('birim', '') or '')

        ttk.Label(frm, text="Kategori:").grid(row=3, column=0, sticky="e", padx=5, pady=4)
        self.kategori_c = ttk.Combobox(frm, width=22, state='readonly',
                                        values=list(KATEGORI_ETIKETLERI.keys()))
        self.kategori_c.grid(row=3, column=1, sticky="w", padx=5, pady=4)
        self.kategori_c.set(mevcut.get('kategori') if mevcut else 'para')

        ttk.Label(frm, text="Kaynak:").grid(row=4, column=0, sticky="e", padx=5, pady=4)
        self.kaynak_c = ttk.Combobox(frm, width=22,
                                      values=['manuel', 'botanik_db', 'csv_import', 'webfetch'])
        self.kaynak_c.grid(row=4, column=1, sticky="w", padx=5, pady=4)
        self.kaynak_c.set(mevcut.get('kaynak') if mevcut else 'manuel')

        ttk.Label(frm, text="Botanik UrunId (ilaç için):").grid(row=5, column=0, sticky="e", padx=5, pady=4)
        self.urunid_e = ttk.Entry(frm, width=15)
        self.urunid_e.grid(row=5, column=1, sticky="w", padx=5, pady=4)
        if mevcut and mevcut.get('botanik_urun_id'):
            self.urunid_e.insert(0, str(mevcut['botanik_urun_id']))

        ttk.Label(frm, text="Açıklama:").grid(row=6, column=0, sticky="e", padx=5, pady=4)
        self.aciklama_e = ttk.Entry(frm, width=40)
        self.aciklama_e.grid(row=6, column=1, sticky="w", padx=5, pady=4)
        if mevcut: self.aciklama_e.insert(0, mevcut.get('aciklama', '') or '')

        btn = ttk.Frame(frm)
        btn.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Kaydet", command=self._kaydet, width=12).pack(side="left", padx=5)
        ttk.Button(btn, text="İptal", command=self.top.destroy, width=10).pack(side="left", padx=5)

    def _kaydet(self):
        kod = self.kod_e.get().strip()
        ad = self.ad_e.get().strip()
        if not kod or not ad:
            messagebox.showwarning("Eksik", "Kod ve Ad zorunlu.", parent=self.top)
            return
        urunid = self.urunid_e.get().strip()
        urun_id = int(urunid) if urunid.isdigit() else None
        self.sonuc = {
            'kod': kod,
            'ad': ad,
            'birim': self.birim_e.get().strip(),
            'kategori': self.kategori_c.get(),
            'kaynak': self.kaynak_c.get(),
            'botanik_urun_id': urun_id,
            'aciklama': self.aciklama_e.get().strip(),
        }
        self.top.destroy()


class DegerEkleDialog:
    def __init__(self, parent):
        self.sonuc = None
        self.top = tk.Toplevel(parent)
        self.top.title("Değer Ekle/Güncelle")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=15)
        frm.pack()

        ttk.Label(frm, text="Tarih:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        if TKCALENDAR_AVAILABLE:
            self.tarih = DateEntry(frm, date_pattern='dd.mm.yyyy', width=14, locale='tr_TR')
        else:
            self.tarih = ttk.Entry(frm, width=14)
            self.tarih.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.tarih.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(frm, text="Değer:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.deger_e = ttk.Entry(frm, width=20)
        self.deger_e.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        btn = ttk.Frame(frm)
        btn.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Kaydet", command=self._kaydet, width=12).pack(side="left", padx=5)
        ttk.Button(btn, text="İptal", command=self.top.destroy, width=10).pack(side="left", padx=5)

    def _kaydet(self):
        try:
            if TKCALENDAR_AVAILABLE and hasattr(self.tarih, 'get_date'):
                t = self.tarih.get_date()
            else:
                t = datetime.strptime(self.tarih.get(), '%d.%m.%Y').date()
            v = float(self.deger_e.get().replace(',', '.').strip())
        except Exception as e:
            messagebox.showerror("Hata", f"Geçersiz veri: {e}", parent=self.top)
            return
        self.sonuc = {'tarih': t, 'deger': v}
        self.top.destroy()


class SepetUyeDialog:
    def __init__(self, parent, endeksler: List[Dict]):
        self.sonuc = None
        self.endeksler = endeksler
        self.top = tk.Toplevel(parent)
        self.top.title("Sepete Endeks Ekle")
        self.top.transient(parent)
        self.top.grab_set()

        frm = ttk.Frame(self.top, padding=15)
        frm.pack()

        ttk.Label(frm, text="Endeks:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        secimler = [f"[{e['id']}] {e['kod']} - {e['ad']}" for e in endeksler]
        self.endeks_c = ttk.Combobox(frm, width=40, state='readonly', values=secimler)
        self.endeks_c.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        if secimler:
            self.endeks_c.set(secimler[0])

        ttk.Label(frm, text="Ağırlık (default 1.0):").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.agirlik_e = ttk.Entry(frm, width=12)
        self.agirlik_e.insert(0, "1.0")
        self.agirlik_e.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        btn = ttk.Frame(frm)
        btn.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Ekle", command=self._kaydet, width=12).pack(side="left", padx=5)
        ttk.Button(btn, text="İptal", command=self.top.destroy, width=10).pack(side="left", padx=5)

    def _kaydet(self):
        sec = self.endeks_c.get()
        if not sec:
            return
        try:
            endeks_id = int(sec.split(']')[0][1:])
            agirlik = float(self.agirlik_e.get().replace(',', '.').strip())
        except Exception as e:
            messagebox.showerror("Hata", str(e), parent=self.top)
            return
        self.sonuc = {'endeks_id': endeks_id, 'agirlik': agirlik}
        self.top.destroy()


def endeks_ayarlari_ac(parent=None, ana_menu_callback=None):
    if parent is None:
        root = tk.Tk()
    else:
        root = tk.Toplevel(parent)
    EndeksAyarlariGUI(root, ana_menu_callback=ana_menu_callback)
    return root


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    root = tk.Tk()
    EndeksAyarlariGUI(root)
    root.mainloop()
