"""
Endeks Grafik Modülü

Satış Raporları penceresinden açılan grafik paneli. matplotlib FigureCanvasTkAgg
ile gömülü canvas. 3 grafik tipi destekler:

1. Endeks Zaman Serisi — Tek endeksin / sepetin tarihsel değişimi
2. Ciro / Endeks Oranı — Aylık ciro ÷ endeks değeri (kira-cinsinden ciro vb.)
3. Tüm Endeksler Normalize — 2017 Nisan = 100 baz, tüm endekslerin trendi

Modül bağımsızdır; satis_raporlari_gui.EndeksGrafikPenceresi.ac() ile çağrılır.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Tuple

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

logger = logging.getLogger(__name__)


GRAFIK_TIPLERI = [
    ('endeks_seri',    '📈 Endeks Zaman Serisi'),
    ('ciro_orani',     '💰 Ciro / Endeks Oranı'),
    ('tum_normalize',  '📊 Tüm Endeksler (2017=100)'),
]


class EndeksGrafikPenceresi:
    """Endeks/ciro grafiklerini gösteren Toplevel pencere."""

    def __init__(self, parent_root, baslangic_tarih=None, bitis_tarih=None,
                 ilk_endeks_secim: Optional[str] = None):
        self.parent_root = parent_root
        self.win = tk.Toplevel(parent_root)
        self.win.title("📊 Endeks Grafiği")
        try:
            self.win.state('zoomed')
        except Exception:
            self.win.geometry("1200x800")

        self.bg_color = '#F5F5F5'
        self.header_color = '#1565C0'
        self.win.configure(bg=self.bg_color)

        self.bdb = None
        self.edb = None

        self.bas_var = tk.StringVar(value=(baslangic_tarih or '2018-01-01'))
        self.bit_var = tk.StringVar(value=(bitis_tarih or date.today().isoformat()))
        self.grafik_tip_var = tk.StringVar(value='endeks_seri')
        self.endeks_secim_var = tk.StringVar(value=(ilk_endeks_secim or ''))
        self.log_olcek_var = tk.BooleanVar(value=False)

        self.endeks_secim_haritasi: Dict[str, Tuple[str, int, str, str]] = {}
        # display_str -> (tip, id, kod, birim)

        self._arayuz_olustur()
        self._db_baglan()
        self._endeks_listesini_yenile()

        # İlk grafik
        self.win.after(200, self.cizdir)

    # ------------------------------------------------------------------
    def _arayuz_olustur(self):
        # Header
        header = tk.Frame(self.win, bg=self.header_color, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊 Endeks Grafiği", font=("Segoe UI", 13, "bold"),
                 bg=self.header_color, fg='white').pack(side="left", padx=15, pady=8)
        tk.Button(header, text="✕ Kapat", bg='#C62828', fg='white', bd=0,
                  font=("Segoe UI", 9), cursor='hand2', padx=12,
                  command=self.win.destroy).pack(side="right", padx=10, pady=8)

        # Filtre satır
        ust = tk.Frame(self.win, bg='#E3F2FD')
        ust.pack(fill="x", padx=5, pady=5)

        tk.Label(ust, text="Başlangıç:", bg='#E3F2FD',
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 3))
        tk.Entry(ust, textvariable=self.bas_var, width=12,
                 font=("Segoe UI", 9)).pack(side="left", padx=2)

        tk.Label(ust, text="Bitiş:", bg='#E3F2FD',
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 3))
        tk.Entry(ust, textvariable=self.bit_var, width=12,
                 font=("Segoe UI", 9)).pack(side="left", padx=2)

        tk.Label(ust, text="  |  Grafik Tipi:", bg='#E3F2FD',
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(15, 3))
        for kod, etiket in GRAFIK_TIPLERI:
            tk.Radiobutton(ust, text=etiket, value=kod, variable=self.grafik_tip_var,
                           bg='#E3F2FD', font=("Segoe UI", 9),
                           command=self.cizdir).pack(side="left", padx=4)

        tk.Checkbutton(ust, text="log ölçek", variable=self.log_olcek_var, bg='#E3F2FD',
                       font=("Segoe UI", 9), command=self.cizdir).pack(side="left", padx=15)

        # Endeks seçim satırı
        ust2 = tk.Frame(self.win, bg='#E3F2FD')
        ust2.pack(fill="x", padx=5, pady=(0, 5))

        tk.Label(ust2, text="Endeks/Sepet:", bg='#E3F2FD',
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 3))
        self.endeks_combo = ttk.Combobox(
            ust2, textvariable=self.endeks_secim_var, width=50, state="readonly"
        )
        self.endeks_combo.pack(side="left", padx=4)
        self.endeks_combo.bind('<<ComboboxSelected>>', lambda e: self.cizdir())

        tk.Button(ust2, text="🔄 Yenile", bg='#90A4AE', fg='white', bd=0,
                  font=("Segoe UI", 9, "bold"), padx=10, cursor='hand2',
                  command=self.cizdir).pack(side="left", padx=10)

        # Bilgi notu (grafik tipine göre değişir)
        self.bilgi_lbl = tk.Label(ust2, text="", bg='#E3F2FD',
                                   font=("Segoe UI", 9, "italic"), fg='#37474F')
        self.bilgi_lbl.pack(side="left", padx=12)

        # Grafik alanı
        self.fig_frame = tk.Frame(self.win, bg='white')
        self.fig_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.fig = Figure(figsize=(13, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.fig_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.fig_frame)
        self.toolbar.update()

        # Status
        self.status_lbl = tk.Label(self.win, text="Hazır.", bg='#37474F', fg='white',
                                    font=("Segoe UI", 9), anchor='w', padx=10)
        self.status_lbl.pack(fill="x", side="bottom")

    def _status(self, msg: str, hata: bool = False):
        self.status_lbl.config(text=msg, fg='#FFCDD2' if hata else 'white')

    # ------------------------------------------------------------------
    def _db_baglan(self):
        try:
            from endeksler_db import get_endeks_db
            self.edb = get_endeks_db()
        except Exception as e:
            logger.error(f"EndeksDB yüklenemedi: {e}", exc_info=True)
            messagebox.showerror("Hata", f"Endeks DB açılamadı:\n{e}")
            return
        try:
            from botanik_db import get_botanik_db
            self.bdb = get_botanik_db()
        except Exception as e:
            logger.warning(f"Botanik DB yüklenemedi (ciro grafiği yok): {e}")

    def _endeks_listesini_yenile(self):
        if not self.edb:
            return
        secimler = ['TL (sadece ciro)']
        haritasi = {'TL (sadece ciro)': ('tl', 0, 'TL', 'TL')}

        try:
            for e in self.edb.endeksleri_getir():
                txt = f"E:{e['kod']} — {e['ad']} ({e['birim']})"
                secimler.append(txt)
                haritasi[txt] = ('endeks', e['id'], e['kod'], e['birim'])
            for s in self.edb.sepet_listesi():
                txt = f"S:{s['id']} — SEPET: {s['ad']}"
                secimler.append(txt)
                haritasi[txt] = ('sepet', s['id'], s['ad'], 'sepet')
        except Exception as e:
            logger.error(f"Endeks listesi alınamadı: {e}")

        self.endeks_secim_haritasi = haritasi
        self.endeks_combo['values'] = secimler
        if self.endeks_secim_var.get() not in secimler and secimler:
            # Varsayılan: dolar (varsa)
            varsayilan = next((s for s in secimler if 'usd' in s.lower()), secimler[0])
            self.endeks_secim_var.set(varsayilan)

    # ------------------------------------------------------------------
    def _tarihleri_oku(self) -> Tuple[Optional[date], Optional[date]]:
        try:
            bas = datetime.strptime(self.bas_var.get(), '%Y-%m-%d').date()
        except Exception:
            try:
                bas = datetime.strptime(self.bas_var.get(), '%d.%m.%Y').date()
            except Exception:
                return None, None
        try:
            bit = datetime.strptime(self.bit_var.get(), '%Y-%m-%d').date()
        except Exception:
            try:
                bit = datetime.strptime(self.bit_var.get(), '%d.%m.%Y').date()
            except Exception:
                return None, None
        return bas, bit

    # ------------------------------------------------------------------
    def cizdir(self):
        bas, bit = self._tarihleri_oku()
        if not (bas and bit):
            self._status("Geçersiz tarih (YYYY-MM-DD veya GG.AA.YYYY).", hata=True)
            return
        if bas >= bit:
            self._status("Başlangıç < Bitiş olmalı.", hata=True)
            return

        tip = self.grafik_tip_var.get()
        secim_txt = self.endeks_secim_var.get()
        secim = self.endeks_secim_haritasi.get(secim_txt)

        self.fig.clear()

        try:
            if tip == 'endeks_seri':
                self._cizdir_endeks_seri(bas, bit, secim)
            elif tip == 'ciro_orani':
                self._cizdir_ciro_orani(bas, bit, secim)
            elif tip == 'tum_normalize':
                self._cizdir_tum_normalize(bas, bit)
        except Exception as e:
            logger.error(f"Grafik çizim hatası: {e}", exc_info=True)
            self._status(f"Hata: {e}", hata=True)
            return

        self.fig.tight_layout()
        self.canvas.draw()
        self._status(f"Grafik güncellendi: {tip} ({bas} → {bit}).")

    # ------------------------------------------------------------------
    def _cizdir_endeks_seri(self, bas, bit, secim):
        """Tek endeks/sepet zaman serisi."""
        if not secim or secim[0] == 'tl':
            self.bilgi_lbl.config(text="Bir endeks veya sepet seçin.")
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "Bir endeks veya sepet seçin",
                    ha='center', va='center', fontsize=14, color='gray',
                    transform=ax.transAxes)
            ax.axis('off')
            return

        tip, eid_or_sid, kod, birim = secim
        ax = self.fig.add_subplot(111)

        if tip == 'endeks':
            kayitlar = self.edb.degerleri_getir(eid_or_sid, bas, bit)
            tarih = [r['tarih'] for r in kayitlar]
            deger = [r['deger'] for r in kayitlar]
            ad = next((e['ad'] for e in self.edb.endeksleri_getir() if e['id'] == eid_or_sid), kod)
        else:
            # Sepet: aylık ortalama olarak çek
            from calendar import monthrange
            tarih, deger = [], []
            cur = date(bas.year, bas.month, 1)
            while cur <= bit:
                son_gun = date(cur.year, cur.month, monthrange(cur.year, cur.month)[1])
                d = self.edb.sepet_donem_ortalama(eid_or_sid, cur, son_gun)
                if d is not None:
                    tarih.append(cur)
                    deger.append(d)
                cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
            ad = next((s['ad'] for s in self.edb.sepet_listesi() if s['id'] == eid_or_sid), 'Sepet')

        if not tarih:
            ax.text(0.5, 0.5, "Bu aralıkta veri yok",
                    ha='center', va='center', fontsize=14, color='gray',
                    transform=ax.transAxes)
            ax.axis('off')
            return

        ax.plot(tarih, deger, marker='o', linewidth=1.8, markersize=4, color='#1565C0')
        if self.log_olcek_var.get():
            ax.set_yscale('log')
        ax.set_title(f"{ad}  ({bas} → {bit})", fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel("Tarih", fontsize=10)
        ax.set_ylabel(f"Değer ({birim})", fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

        # İlk-son değer notu
        ilk, son = deger[0], deger[-1]
        carpan = son / ilk if ilk else 0
        ax.annotate(f"Başlangıç: {ilk:,.2f}\nBitiş: {son:,.2f}\nDeğişim: {carpan:.2f}×",
                    xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=10, va='top', ha='left',
                    bbox=dict(boxstyle='round', facecolor='#FFF9C4', alpha=0.9))

        self.bilgi_lbl.config(text=f"Endeksin ham değeri (forward-fill ile aylık)")

    # ------------------------------------------------------------------
    def _cizdir_ciro_orani(self, bas, bit, secim):
        """Aylık ciro ÷ endeks değeri (örn. kira-cinsinden ciro)."""
        if not self.bdb:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "Botanik DB yok — ciro çekilemiyor",
                    ha='center', va='center', fontsize=14, color='red',
                    transform=ax.transAxes)
            ax.axis('off')
            return

        # Ciro verisi
        aylik = self.bdb.satis_raporu_getir(bas, bit, periyot='aylik')
        tarih_l, ciro_l, oran_l = [], [], []

        for r in aylik:
            ds = r['Donem'] if isinstance(r['Donem'], str) else r['Donem'].isoformat()
            d = date.fromisoformat(ds.split(' ')[0])
            tl = r.get('TLTutar') or 0
            if tl <= 0:
                continue
            tarih_l.append(d)
            ciro_l.append(tl)
            if secim and secim[0] != 'tl':
                tip, eid_or_sid, _, _ = secim
                if tip == 'endeks':
                    e_deg = self.edb.deger_getir(eid_or_sid, d)
                elif tip == 'sepet':
                    from calendar import monthrange
                    son_gun = date(d.year, d.month, monthrange(d.year, d.month)[1])
                    e_deg = self.edb.sepet_donem_ortalama(eid_or_sid, d, son_gun)
                else:
                    e_deg = None
                oran_l.append(tl / e_deg if e_deg and e_deg > 0 else None)
            else:
                oran_l.append(None)

        if not tarih_l:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "Bu aralıkta ciro verisi yok",
                    ha='center', va='center', fontsize=14, color='gray',
                    transform=ax.transAxes)
            ax.axis('off')
            return

        if not secim or secim[0] == 'tl':
            # Sadece ciro grafiği
            ax = self.fig.add_subplot(111)
            ax.plot(tarih_l, ciro_l, marker='o', linewidth=1.6, markersize=3, color='#2E7D32')
            if self.log_olcek_var.get():
                ax.set_yscale('log')
            ax.set_title(f"Aylık Ciro (TL)  ({bas} → {bit})", fontsize=12, fontweight='bold')
            ax.set_ylabel("Ciro (TL)")
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            self.bilgi_lbl.config(text="Bir endeks seçilirse 'kaç endeks' cinsinden de gösterilir")
            return

        # İki panelli: üstte oran, altta ham ciro vs endeks (log)
        ax1 = self.fig.add_subplot(2, 1, 1)
        oran_clean = [(t, o) for t, o in zip(tarih_l, oran_l) if o is not None]
        if oran_clean:
            tx = [t for t, _ in oran_clean]
            ox = [o for _, o in oran_clean]
            ax1.plot(tx, ox, marker='o', linewidth=1.6, markersize=3, color='#2E7D32')
            birim = secim[3]
            tip_etiket = secim[2]
            ax1.set_title(f"Aylık Ciro / {tip_etiket}  ({bas} → {bit})",
                          fontsize=12, fontweight='bold')
            ax1.set_ylabel(f"Ciro ÷ Endeks ({birim})")
            ax1.grid(True, alpha=0.3)

        # Alt panel: ham karşılaştırma (log)
        ax2 = self.fig.add_subplot(2, 1, 2)
        ax2.semilogy(tarih_l, ciro_l, marker='o', linewidth=1.4, markersize=3,
                     color='#1565C0', label='Aylık ciro (TL)')

        # Endeks ham serisi
        endeks_tarih, endeks_deger = [], []
        for t in tarih_l:
            if secim[0] == 'endeks':
                d = self.edb.deger_getir(secim[1], t)
            else:
                from calendar import monthrange
                son_gun = date(t.year, t.month, monthrange(t.year, t.month)[1])
                d = self.edb.sepet_donem_ortalama(secim[1], t, son_gun)
            if d:
                endeks_tarih.append(t)
                endeks_deger.append(d)
        if endeks_deger:
            ax2.semilogy(endeks_tarih, endeks_deger, marker='s', linewidth=1.8,
                         markersize=3, color='#C62828', label=f'{secim[2]} ({secim[3]})')

        ax2.set_ylabel("Değer (log)")
        ax2.set_xlabel("Tarih")
        ax2.grid(True, alpha=0.3, which='both')
        ax2.legend(loc='upper left', fontsize=9)

        for ax in [ax1, ax2]:
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

        self.bilgi_lbl.config(text=f"Üst: ciro ÷ endeks · Alt: ham TL ve endeks (log)")

    # ------------------------------------------------------------------
    def _cizdir_tum_normalize(self, bas, bit):
        """Tüm endeksler 2017 Nisan = 100 normalize (veya bas tarihi=100)."""
        ax = self.fig.add_subplot(111)
        endeksler = self.edb.endeksleri_getir()
        # Kategori filtreleri (yoğun olmasın)
        gostermek = [
            ('usd', '#1976D2'), ('eur', '#0288D1'), ('altin_gram', '#F9A825'),
            ('benzin_95', '#5D4037'), ('asgari_ucret', '#388E3C'),
            ('dukkan_kirasi', '#C62828'), ('ilac_sepeti_toplam', '#7B1FA2'),
        ]
        cizilen = 0
        for kod, renk in gostermek:
            eid = self.edb._endeks_id_kod(kod)
            if eid is None:
                continue
            ad = next((e['ad'] for e in endeksler if e['id'] == eid), kod)
            kayitlar = self.edb.degerleri_getir(eid, bas, bit)
            if not kayitlar:
                continue
            baz = kayitlar[0]['deger']
            if baz <= 0:
                continue
            tx = [r['tarih'] for r in kayitlar]
            ox = [(r['deger'] / baz) * 100 for r in kayitlar]
            ax.plot(tx, ox, marker='o', linewidth=1.6, markersize=2.5,
                    color=renk, label=f"{ad}  ({kayitlar[-1]['deger']/baz:.1f}×)")
            cizilen += 1

        if cizilen == 0:
            ax.text(0.5, 0.5, "Bu aralıkta veri yok",
                    ha='center', va='center', fontsize=14, color='gray',
                    transform=ax.transAxes)
            ax.axis('off')
            return

        if self.log_olcek_var.get():
            ax.set_yscale('log')
        ax.set_title(f"Tüm Endeksler — {bas} = 100 baz",
                     fontsize=12, fontweight='bold', pad=10)
        ax.set_ylabel("Endeks (baz = 100)")
        ax.set_xlabel("Tarih")
        ax.grid(True, alpha=0.3, which='both')
        ax.axhline(y=100, color='gray', linestyle=':', linewidth=0.8, alpha=0.5)
        ax.legend(loc='upper left', fontsize=9, framealpha=0.85)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        self.bilgi_lbl.config(text=f"Baz: {bas} = 100. Çarpan paranteziçinde.")


# ----------------------------------------------------------------------
def ac(parent_root, baslangic_tarih=None, bitis_tarih=None,
       ilk_endeks_secim: Optional[str] = None):
    """Convenience launcher — Satış Raporları penceresinden çağrılır."""
    return EndeksGrafikPenceresi(parent_root, baslangic_tarih, bitis_tarih,
                                  ilk_endeks_secim)
