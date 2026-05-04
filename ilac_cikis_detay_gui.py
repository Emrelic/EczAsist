"""
Ilac Cikis Detay Penceresi

Hastasi Olan Ilaclar penceresinde bir satirin "Detay" hucresine tiklaninca
acilir. Secilen ilacin son 12 ayda tum cikislarini (receteli + elden) listeler.

Ust kisimda "Ilgili Hasta" filtresi: o satirin ait oldugu hastanin alimlarini
filtreler. "Tumunu Goster" ile filtre kalkar.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class IlacCikisDetayGUI:
    """Tek bir ilac icin son 12 ay cikis detay penceresi."""

    def __init__(self, parent, urun_id: int, urun_adi: str,
                 ilgili_hasta: Optional[Dict] = None, db=None):
        """
        Args:
            parent: Ust pencere (HastasiOlanIlacGUI'nin Toplevel'i).
            urun_id: Detayini gostermek istedigimiz urunun id'si.
            urun_adi: Urunun adi (baslik icin).
            ilgili_hasta: Tetikleyen satirin hasta bilgisi (varsa).
                          {'MusteriId', 'MusteriAdiSoyadi', 'MusteriTCKN'}
            db: Opsiyonel BotanikDB.
        """
        self.parent = parent
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.ilgili_hasta = ilgili_hasta or {}
        self.db = db

        self.window = tk.Toplevel(parent)
        self.window.title(f"Ilac Cikis Detayi - {urun_adi}")
        self.window.geometry("1000x600")

        self.tum_kayitlar: List[Dict] = []
        self.gosterilen: List[Dict] = []
        self.filtre_aktif = False  # Ilgili hasta filtresi acik mi?

        self._ui_olustur()
        self.window.after(80, self._verileri_yukle)

    def _ui_olustur(self):
        # Ust baslik + filtre cubugu
        ust = tk.Frame(self.window, bg='#37474F')
        ust.pack(fill=tk.X, padx=4, pady=4)

        baslik = tk.Label(
            ust,
            text=f"📦 {self.urun_adi}",
            bg='#37474F', fg='white', font=('Arial', 11, 'bold'),
        )
        baslik.pack(side=tk.LEFT, padx=8, pady=6)

        if self.ilgili_hasta.get('MusteriId'):
            hasta_ad = self.ilgili_hasta.get('MusteriAdiSoyadi', '?').strip()
            self.filtre_btn = tk.Button(
                ust,
                text=f"👤 Ilgili Hasta: {hasta_ad}",
                command=self._ilgili_hasta_filtre_toggle,
                bg='#1565C0', fg='white', font=('Arial', 9, 'bold'),
                relief='raised', bd=2, padx=10
            )
            self.filtre_btn.pack(side=tk.LEFT, padx=12, pady=4)

            self.tumunu_btn = tk.Button(
                ust, text="Tumunu Goster",
                command=self._tumunu_goster,
                bg='#455A64', fg='white', font=('Arial', 9),
                relief='flat', padx=10
            )
            self.tumunu_btn.pack(side=tk.LEFT, padx=4, pady=4)
            self.tumunu_btn.config(state=tk.DISABLED)

        self.durum_label = tk.Label(
            ust, text="Yukleniyor...",
            bg='#37474F', fg='#B0BEC5', font=('Arial', 9)
        )
        self.durum_label.pack(side=tk.RIGHT, padx=12, pady=6)

        # Tablo
        orta = tk.Frame(self.window)
        orta.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        kolonlar = [
            ('Tarih', 'Tarih', 100),
            ('Saat', 'Saat', 70),
            ('HastaAdi', 'Hasta Adi', 200),
            ('TCKN', 'TCKN', 110),
            ('Adet', 'Adet', 60),
            ('Tur', 'Tur', 80),
            ('ReceteNo', 'Recete/Belge No', 140),
        ]

        self.tree = ttk.Treeview(
            orta, columns=[k[0] for k in kolonlar],
            show='headings', selectmode='browse', height=20
        )
        for kod, baslik, w in kolonlar:
            self.tree.heading(kod, text=baslik)
            anchor = 'center' if kod in ('Adet', 'Tur', 'Saat') else 'w'
            self.tree.column(kod, width=w, minwidth=30, anchor=anchor)

        vsb = ttk.Scrollbar(orta, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        style = ttk.Style()
        style.configure('Detay.Treeview', font=('Arial', 10), rowheight=24)
        style.configure('Detay.Treeview.Heading', font=('Arial', 10, 'bold'))
        self.tree.configure(style='Detay.Treeview')

        self.tree.tag_configure('elden', background='#FFF3E0',
                                foreground='#E65100')
        self.tree.tag_configure('receteli', background='#E3F2FD',
                                foreground='#0D47A1')
        self.tree.tag_configure('vurgulu', background='#FFE082',
                                foreground='#33691E')

        # Alt
        alt = tk.Frame(self.window, bg='#263238')
        alt.pack(fill=tk.X, padx=4, pady=4)
        tk.Button(
            alt, text="Kapat", command=self.window.destroy,
            bg='#455A64', fg='white', font=('Arial', 9),
            relief='flat', padx=14
        ).pack(side=tk.RIGHT, padx=4, pady=4)

    def _verileri_yukle(self):
        try:
            from hastasi_olan_ilac_db import HastasiOlanIlacDB
            sorgulayici = HastasiOlanIlacDB(db=self.db)
            self.tum_kayitlar = sorgulayici.ilac_cikis_gecmisi_getir(
                self.urun_id
            )
            self.filtre_aktif = False
            self._listeyi_uygula()
        except Exception as e:
            logger.exception("Ilac cikis gecmisi yukleme hatasi")
            messagebox.showerror(
                "Hata", f"Veri yuklenemedi:\n{e}", parent=self.window
            )
            self.durum_label.config(text=f"Hata: {e}")

    def _listeyi_uygula(self):
        if self.filtre_aktif and self.ilgili_hasta.get('MusteriId'):
            mid = self.ilgili_hasta['MusteriId']
            self.gosterilen = [r for r in self.tum_kayitlar
                               if r.get('MusteriId') == mid]
        else:
            self.gosterilen = list(self.tum_kayitlar)
        self._tabloyu_doldur()

    def _tabloyu_doldur(self):
        self.tree.delete(*self.tree.get_children())
        ilgili_mid = self.ilgili_hasta.get('MusteriId')

        toplam_adet = 0
        for r in self.gosterilen:
            tarih = r.get('Tarih')
            tarih_str = ''
            if isinstance(tarih, (date, datetime)):
                tarih_str = (tarih.date() if isinstance(tarih, datetime)
                             else tarih).strftime('%Y-%m-%d')
            elif tarih is not None:
                tarih_str = str(tarih)[:10]

            saat = r.get('Saat') or ''
            if saat:
                saat = str(saat)[:8]

            hasta_ad = (r.get('HastaAdi') or '').strip()
            tckn = (r.get('TCKN') or '').strip() if r.get('TCKN') else ''
            adet = r.get('Adet', 0) or 0
            tur = r.get('Tur') or ''
            recete = (r.get('ReceteNo') or '').strip()

            try:
                toplam_adet += int(adet)
            except (TypeError, ValueError):
                pass

            tags = ['elden' if tur == 'Elden' else 'receteli']
            if (not self.filtre_aktif and ilgili_mid is not None
                    and r.get('MusteriId') == ilgili_mid):
                tags = ['vurgulu']

            self.tree.insert('', tk.END, values=(
                tarih_str, saat, hasta_ad, tckn, adet, tur, recete
            ), tags=tuple(tags))

        durum = (f"Gosterilen: {len(self.gosterilen)} satir | "
                 f"Toplam adet: {toplam_adet}")
        if self.filtre_aktif:
            durum += "  |  🔎 Ilgili hasta filtresi AKTIF"
        self.durum_label.config(text=durum)

    def _ilgili_hasta_filtre_toggle(self):
        if not self.ilgili_hasta.get('MusteriId'):
            return
        self.filtre_aktif = True
        if hasattr(self, 'tumunu_btn'):
            self.tumunu_btn.config(state=tk.NORMAL)
        if hasattr(self, 'filtre_btn'):
            self.filtre_btn.config(bg='#0D47A1', text=(
                f"👤 Ilgili Hasta: {self.ilgili_hasta.get('MusteriAdiSoyadi', '?').strip()} ✓"
            ))
        self._listeyi_uygula()

    def _tumunu_goster(self):
        self.filtre_aktif = False
        if hasattr(self, 'tumunu_btn'):
            self.tumunu_btn.config(state=tk.DISABLED)
        if hasattr(self, 'filtre_btn'):
            self.filtre_btn.config(bg='#1565C0', text=(
                f"👤 Ilgili Hasta: {self.ilgili_hasta.get('MusteriAdiSoyadi', '?').strip()}"
            ))
        self._listeyi_uygula()
