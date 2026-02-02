"""
Minimum Stok Analizi GUI Modulu
Bilimsel yontemler ve finansal basabas noktasi bazli minimum stok hesaplama
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from min_stok_analiz import (
    tum_ilaclari_analiz_et,
    toplu_min_stok_guncelle,
    basabas_noktasi_hesapla
)
from siparis_db import get_siparis_db

logger = logging.getLogger(__name__)


class MinStokAnalizGUI:
    """Minimum Stok Analizi Ana Penceresi"""

    def __init__(self, parent, ana_menu_callback=None):
        self.parent = parent
        self.ana_menu_callback = ana_menu_callback

        self.parent.title("Minimum Stok Analizi - Bilimsel Hesaplama")
        self.parent.geometry("1600x850")
        self.parent.configure(bg='#ECEFF1')

        # Veritabani
        self.db = None
        self._db_baglan()

        # Analiz sonuclari
        self.analiz_sonuclari = []

        # Degiskenler
        self.ay_sayisi = tk.IntVar(value=12)
        self.kar_marji = tk.DoubleVar(value=22)
        self.yillik_faiz = tk.DoubleVar(value=40)
        self.sadece_stoklu = tk.BooleanVar(value=False)
        self.sadece_degisecek = tk.BooleanVar(value=False)
        self.hareket_yili = tk.IntVar(value=2)  # Son 2 yil varsayilan

        self._arayuz_olustur()

    def _db_baglan(self):
        """Veritabanina baglan"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if not self.db.baglan():
                self.db = None
                logger.warning("Veritabanina baglanilamadi")
        except Exception as e:
            logger.error(f"DB baglanti hatasi: {e}")
            self.db = None

    def _arayuz_olustur(self):
        """Ana arayuz - GRID TABANLI YENİ TASARIM"""
        # Baslik
        header = tk.Frame(self.parent, bg='#1976D2', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Minimum Stok Analizi",
            bg='#1976D2', fg='white', font=('Arial', 14, 'bold')
        ).pack(side=tk.LEFT, padx=20, pady=10)

        # Parametre paneli - GRID KULLANARAK
        self._parametre_panel_olustur()

        # Tablo (bilgi paneli kaldirildi - yer acmak icin)
        self._tablo_olustur()

        # Alt butonlar
        self._buton_panel_olustur()

    def _parametre_panel_olustur(self):
        """Parametre giris paneli - GRID LAYOUT"""
        param_frame = tk.Frame(self.parent, bg='#E3F2FD', relief='ridge', bd=2)
        param_frame.pack(fill=tk.X, padx=10, pady=5)

        # SATIR 1: Tum parametreler GRID ile
        # Col 0: Analiz Donemi
        tk.Label(param_frame, text="Analiz Dönemi:", font=('Arial', 10, 'bold'),
                bg='#E3F2FD').grid(row=0, column=0, padx=(10,5), pady=10, sticky='e')
        ay_combo = ttk.Combobox(param_frame, textvariable=self.ay_sayisi, width=5, state='readonly')
        ay_combo['values'] = [6, 12, 18, 24]
        ay_combo.grid(row=0, column=1, padx=(0,5), pady=10)
        tk.Label(param_frame, text="ay", font=('Arial', 10), bg='#E3F2FD').grid(row=0, column=2, padx=(0,20), pady=10)

        # Col 3: HAREKET YILI - TURUNCU VURGULU
        tk.Label(param_frame, text="Hareket Süresi:", font=('Arial', 10, 'bold'),
                bg='#FFECB3', fg='#E65100').grid(row=0, column=3, padx=(10,5), pady=10, sticky='e')
        hareket_combo = ttk.Combobox(param_frame, textvariable=self.hareket_yili, width=5, state='readonly')
        hareket_combo['values'] = [0, 1, 2, 3, 5, 10]
        hareket_combo.grid(row=0, column=4, padx=(0,5), pady=10)
        tk.Label(param_frame, text="yıl", font=('Arial', 10), bg='#E3F2FD').grid(row=0, column=5, padx=(0,20), pady=10)

        # Col 6: Kar Marji
        tk.Label(param_frame, text="Kar Marjı:", font=('Arial', 10, 'bold'),
                bg='#E3F2FD').grid(row=0, column=6, padx=(10,5), pady=10, sticky='e')
        ttk.Entry(param_frame, textvariable=self.kar_marji, width=5).grid(row=0, column=7, padx=(0,5), pady=10)
        tk.Label(param_frame, text="%", font=('Arial', 10), bg='#E3F2FD').grid(row=0, column=8, padx=(0,15), pady=10)

        # Col 9: Faiz
        tk.Label(param_frame, text="Faiz:", font=('Arial', 10, 'bold'),
                bg='#E3F2FD').grid(row=0, column=9, padx=(5,5), pady=10, sticky='e')
        ttk.Entry(param_frame, textvariable=self.yillik_faiz, width=5).grid(row=0, column=10, padx=(0,5), pady=10)
        tk.Label(param_frame, text="%", font=('Arial', 10), bg='#E3F2FD').grid(row=0, column=11, padx=(0,15), pady=10)

        # Col 12: Basabas
        self.basabas_label = tk.Label(param_frame, text="Başabaş: --", font=('Arial', 9, 'bold'),
                                       bg='#FFF9C4', fg='#F57F17', padx=8, pady=4)
        self.basabas_label.grid(row=0, column=12, padx=(5,15), pady=10)

        # Col 13: Checkboxlar
        tk.Checkbutton(param_frame, text="Stoklu", variable=self.sadece_stoklu,
                      bg='#E3F2FD', font=('Arial', 9)).grid(row=0, column=13, padx=(5,5), pady=10)
        tk.Checkbutton(param_frame, text="Değişecek", variable=self.sadece_degisecek,
                      bg='#E3F2FD', font=('Arial', 9), command=self._filtreyi_uygula).grid(row=0, column=14, padx=(5,10), pady=10)

        # Col 15: Analiz butonu
        tk.Button(param_frame, text="ANALİZ YAP", command=self._analiz_yap,
                 bg='#1976D2', fg='white', font=('Arial', 11, 'bold'),
                 relief='raised', bd=2, padx=20, pady=5).grid(row=0, column=15, padx=(10,10), pady=10)

        # Durum etiketi (ayri satirda)
        self.durum_label = tk.Label(param_frame, text="Hazır", font=('Arial', 9), bg='#E3F2FD', fg='#666')
        self.durum_label.grid(row=1, column=0, columnspan=16, pady=(0,5), sticky='w', padx=10)

        # Parametre degisikliklerini izle
        self.kar_marji.trace_add('write', self._basabas_guncelle)
        self.yillik_faiz.trace_add('write', self._basabas_guncelle)
        self._basabas_guncelle()

    def _basabas_guncelle(self, *args):
        """Basabas noktasini guncelle"""
        try:
            kar = self.kar_marji.get() / 100
            faiz = self.yillik_faiz.get() / 100
            basabas = basabas_noktasi_hesapla(kar, faiz)
            self.basabas_label.config(text=f"Başabaş: {basabas:.1f} ay")
        except:
            self.basabas_label.config(text="Başabaş: -- ay")

    def _tablo_olustur(self):
        """Ana tablo"""
        tablo_frame = tk.Frame(self.parent, bg='#ECEFF1')
        tablo_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Treeview - Uygunluk puanlaması eklendi
        columns = (
            'adi', 'stok', 'mevcut_min', 'aylik', 'talep', 'parti',
            'sinif', 'uyg_puan', 'uyg_karar', 'son_satis', 'yillik',
            'min_bil', 'min_fin', 'min_oner', 'aciklama'
        )
        self.tree = ttk.Treeview(tablo_frame, columns=columns, show='headings', height=20)

        # Basliklar
        self.tree.heading('adi', text='Ilac Adi')
        self.tree.heading('stok', text='Stok')
        self.tree.heading('mevcut_min', text='Mevcut')
        self.tree.heading('aylik', text='Aylik')
        self.tree.heading('talep', text='Talep')
        self.tree.heading('parti', text='Parti')
        self.tree.heading('sinif', text='Sinif')
        self.tree.heading('uyg_puan', text='Puan')
        self.tree.heading('uyg_karar', text='Karar')
        self.tree.heading('son_satis', text='Son(g)')
        self.tree.heading('yillik', text='Yillik')
        self.tree.heading('min_bil', text='Bilim')
        self.tree.heading('min_fin', text='Finans')
        self.tree.heading('min_oner', text='ONER')
        self.tree.heading('aciklama', text='Aciklama')

        # Sutun genislikleri
        self.tree.column('adi', width=200, anchor='w')
        self.tree.column('stok', width=45, anchor='center')
        self.tree.column('mevcut_min', width=50, anchor='center')
        self.tree.column('aylik', width=45, anchor='center')
        self.tree.column('talep', width=45, anchor='center')
        self.tree.column('parti', width=45, anchor='center')
        self.tree.column('sinif', width=85, anchor='center')
        self.tree.column('uyg_puan', width=45, anchor='center')
        self.tree.column('uyg_karar', width=85, anchor='center')
        self.tree.column('son_satis', width=50, anchor='center')
        self.tree.column('yillik', width=45, anchor='center')
        self.tree.column('min_bil', width=50, anchor='center')
        self.tree.column('min_fin', width=50, anchor='center')
        self.tree.column('min_oner', width=50, anchor='center')
        self.tree.column('aciklama', width=250, anchor='w')

        # Tag renkleri
        self.tree.tag_configure('degisecek', background='#FFF9C4')
        self.tree.tag_configure('artacak', background='#FFCDD2')
        self.tree.tag_configure('azalacak', background='#C8E6C9')
        self.tree.tag_configure('lumpy', background='#E1BEE7')
        self.tree.tag_configure('uygun_degil', background='#FFCDD2')  # Kirmizi
        self.tree.tag_configure('dikkatli', background='#FFF9C4')     # Sari
        self.tree.tag_configure('uygun', background='#C8E6C9')        # Yesil

        # Scrollbar
        scrollbar_y = ttk.Scrollbar(tablo_frame, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tablo_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

    def _buton_panel_olustur(self):
        """Alt buton paneli"""
        btn_frame = tk.Frame(self.parent, bg='#ECEFF1')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        # UYARI: Botanik EOS'a yazma YASAK - butonlar devre disi
        tk.Button(
            btn_frame, text="DB'ye Yaz (DEVRE DISI)",
            command=self._yazma_yasak_uyari,
            bg='#9E9E9E', fg='white', font=('Arial', 10),
            relief='flat', bd=1, padx=10, pady=5, state='disabled'
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame, text="TABLOYA KAYDET",
            command=self._tabloya_kaydet,
            bg='#4CAF50', fg='white', font=('Arial', 11, 'bold'),
            relief='raised', bd=2, padx=20, pady=5
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame, text="EXCEL'E AKTAR",
            command=self._excel_aktar,
            bg='#FF6F00', fg='white', font=('Arial', 11, 'bold'),
            relief='raised', bd=2, padx=20, pady=5
        ).pack(side=tk.LEFT, padx=(0, 20))

        # Uyari etiketi
        tk.Label(
            btn_frame, text="Tabloya Kaydet: Yerel DB'ye kaydeder | Excel'e Aktar: Dosya olusturur | Botanik EOS'a yazma YASAK!",
            font=('Arial', 9, 'italic'), bg='#ECEFF1', fg='#1565C0'
        ).pack(side=tk.LEFT, padx=10)

        # Ozet bilgi
        self.ozet_label = tk.Label(
            btn_frame, text="", font=('Arial', 10, 'bold'),
            bg='#ECEFF1', fg='#1565C0'
        )
        self.ozet_label.pack(side=tk.RIGHT, padx=10)

    def _analiz_yap(self):
        """Analiz yap ve tabloyu doldur"""
        if not self.db:
            messagebox.showerror("Hata", "Veritabani baglantisi yok!")
            return

        self.durum_label.config(text="Analiz yapiliyor...")
        self.parent.update()

        def progress_cb(current, total):
            self.durum_label.config(text=f"Analiz: {current}/{total} ilac...")
            self.parent.update()

        def analiz_thread():
            try:
                self.analiz_sonuclari = tum_ilaclari_analiz_et(
                    self.db,
                    ay_sayisi=self.ay_sayisi.get(),
                    kar_marji=self.kar_marji.get() / 100,
                    yillik_faiz=self.yillik_faiz.get() / 100,
                    sadece_stoklu=self.sadece_stoklu.get(),
                    hareket_yili=self.hareket_yili.get(),
                    progress_callback=progress_cb
                )
                self.parent.after(0, self._tabloyu_doldur)
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror("Hata", f"Analiz hatasi: {e}"))
                self.parent.after(0, lambda: self.durum_label.config(text=f"Hata!"))

        thread = threading.Thread(target=analiz_thread, daemon=True)
        thread.start()

    def _tabloyu_doldur(self):
        """Tabloyu sonuclarla doldur"""
        # Temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        degisecek = 0
        artacak = 0
        azalacak = 0

        for s in self.analiz_sonuclari:
            mevcut = s['MevcutMin']
            onerilen = s['MinOnerilen']
            uyg_karar = s.get('UygunlukKarar', '')

            # Filtre
            if self.sadece_degisecek.get() and mevcut == onerilen:
                continue

            # Tag - oncelik: uygunluk karari > sinif > degisim
            if uyg_karar == 'UYGUN_DEGIL':
                tag = 'uygun_degil'
            elif uyg_karar in ('DIKKATLI', 'SADECE_KRITIK'):
                tag = 'dikkatli'
            elif s['Sinif'] == 'LUMPY':
                tag = 'lumpy'
            elif mevcut != onerilen:
                degisecek += 1
                if onerilen > mevcut:
                    tag = 'artacak'
                    artacak += 1
                else:
                    tag = 'azalacak'
                    azalacak += 1
            else:
                tag = 'uygun'

            self.tree.insert('', 'end', values=(
                s['UrunAdi'][:35],
                s['Stok'],
                mevcut,
                s['AylikOrt'],
                s['TalepSayisi'],
                s['OrtParti'],
                s['Sinif'],
                s.get('UygunlukPuan', '-'),
                s.get('UygunlukKarar', '-'),
                s.get('SonSatisGun', '-'),
                s.get('YillikSatis', '-'),
                s['MinBilimsel'],
                s['MinFinansal'],
                s['MinOnerilen'],
                s['Aciklama'][:40]
            ), tags=(tag,), iid=str(s['UrunId']))

        # Filtre bilgisi
        hareket_yili = self.hareket_yili.get()
        filtre_bilgi = f" (son {hareket_yili} yil)" if hareket_yili > 0 else " (tum ilaclar)"

        self.durum_label.config(text=f"Tamamlandi: {len(self.analiz_sonuclari)} ilac{filtre_bilgi}")
        self.ozet_label.config(
            text=f"Degisecek: {degisecek} | Artacak: {artacak} | Azalacak: {azalacak}"
        )

    def _filtreyi_uygula(self):
        """Filtreyi uygula"""
        if self.analiz_sonuclari:
            self._tabloyu_doldur()

    def _yazma_yasak_uyari(self):
        """Botanik EOS'a yazma yasak uyarisi"""
        messagebox.showwarning(
            "YASAK ISLEM",
            "Botanik EOS veritabanina yazma YASAKTIR!\n\n"
            "Minimum stok degerlerini degistirmek icin:\n"
            "1. Sonuclari Excel'e aktarin\n"
            "2. Botanik EOS programindan manuel olarak guncelleyin\n\n"
            "Bu program sadece analiz ve oneri yapar,\n"
            "veritabanina mudahale edemez."
        )

    def _tumu_uygula(self):
        """DEVRE DISI - Botanik EOS'a yazma yasak"""
        self._yazma_yasak_uyari()

    def _secilileri_uygula(self):
        """DEVRE DISI - Botanik EOS'a yazma yasak"""
        self._yazma_yasak_uyari()

    def _tabloya_kaydet(self):
        """Analiz sonuclarini yerel SQLite veritabanina kaydet"""
        if not self.analiz_sonuclari:
            messagebox.showwarning("Uyari", "Once analiz yapin!")
            return

        # Onay al
        sonuc = messagebox.askyesno(
            "Tabloya Kaydet",
            f"{len(self.analiz_sonuclari)} adet minimum stok analizi kaydedilecek.\n\n"
            "Mevcut kayitlar guncellenecek.\n\nDevam edilsin mi?"
        )

        if not sonuc:
            return

        self.durum_label.config(text="Kaydediliyor...")
        self.parent.update()

        def progress_cb(current, total):
            self.durum_label.config(text=f"Kaydediliyor: {current}/{total}...")
            self.parent.update()

        try:
            siparis_db = get_siparis_db()
            basarili, hata = siparis_db.min_stok_toplu_kaydet(
                self.analiz_sonuclari,
                progress_callback=progress_cb
            )

            self.durum_label.config(text=f"Kaydedildi: {basarili} basarili, {hata} hata")

            if hata == 0:
                messagebox.showinfo(
                    "Basarili",
                    f"{basarili} adet minimum stok analizi yerel veritabanina kaydedildi.\n\n"
                    f"Konum: siparis_calismalari.db"
                )
            else:
                messagebox.showwarning(
                    "Kismi Basari",
                    f"Basarili: {basarili}\nHata: {hata}\n\n"
                    "Bazi kayitlar kaydedilemedi."
                )

        except Exception as e:
            self.durum_label.config(text="Kayit hatasi!")
            messagebox.showerror("Hata", f"Veritabanina kaydetme hatasi:\n{e}")

    def _excel_aktar(self):
        """Excel'e aktar"""
        if not self.analiz_sonuclari:
            messagebox.showwarning("Uyari", "Once analiz yapin!")
            return

        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyasi", "*.xlsx")],
            title="Excel Olarak Kaydet",
            initialfilename=f"min_stok_analiz_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )

        if not dosya_yolu:
            return

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Min Stok Analizi"

            # Basliklar
            headers = [
                'Ilac Adi', 'Stok', 'Mevcut Min', 'Aylik Ort', 'Talep Sayisi',
                'Ort Parti', 'CV', 'ADI', 'Sinif', 'Min (Bilim)', 'Min (Finans)',
                'ONERILEN', 'Aciklama'
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='1976D2', end_color='1976D2', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')

            # Veriler
            for row, s in enumerate(self.analiz_sonuclari, 2):
                ws.cell(row=row, column=1, value=s['UrunAdi'])
                ws.cell(row=row, column=2, value=s['Stok'])
                ws.cell(row=row, column=3, value=s['MevcutMin'])
                ws.cell(row=row, column=4, value=s['AylikOrt'])
                ws.cell(row=row, column=5, value=s['TalepSayisi'])
                ws.cell(row=row, column=6, value=s['OrtParti'])
                ws.cell(row=row, column=7, value=s['CV'])
                ws.cell(row=row, column=8, value=s['ADI'])
                ws.cell(row=row, column=9, value=s['Sinif'])
                ws.cell(row=row, column=10, value=s['MinBilimsel'])
                ws.cell(row=row, column=11, value=s['MinFinansal'])
                ws.cell(row=row, column=12, value=s['MinOnerilen'])
                ws.cell(row=row, column=13, value=s['Aciklama'])

                # Renklendirme
                if s['MevcutMin'] != s['MinOnerilen']:
                    color = 'FFCDD2' if s['MinOnerilen'] > s['MevcutMin'] else 'C8E6C9'
                    for col in range(1, 14):
                        ws.cell(row=row, column=col).fill = PatternFill(
                            start_color=color, end_color=color, fill_type='solid'
                        )

            wb.save(dosya_yolu)
            messagebox.showinfo("Basarili", f"Excel dosyasi kaydedildi:\n{dosya_yolu}")

        except Exception as e:
            messagebox.showerror("Hata", f"Excel kaydetme hatasi: {e}")


def min_stok_analiz_ac(parent=None, ana_menu_callback=None):
    """Minimum Stok Analizi modulunu ac"""
    if parent is None:
        root = tk.Tk()
        app = MinStokAnalizGUI(root)
        root.mainloop()
    else:
        app = MinStokAnalizGUI(parent, ana_menu_callback)
    return app


if __name__ == "__main__":
    min_stok_analiz_ac()
