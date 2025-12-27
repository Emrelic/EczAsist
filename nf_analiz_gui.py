#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MF Analiz GUI - Nakit Fiyat / Mal Fazlasi Simulasyon Modulu
Detayli stok, kasa, borc, alacak ve kredi simulasyonu
Coklu senaryo karsilastirma ozelligi
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from tkcalendar import DateEntry
import threading
import time
import copy


class SenaryoVerileri:
    """Tek bir senaryo icin tum verileri tutar"""

    def __init__(self):
        # Parametreler
        self.params = {}

        # Simulasyon durumu
        self.durum = {}

        # Acik hesaplar (tarih bazli bekleyen odemeler/tahsilatlar)
        self.sgk_acik_hesap = {}       # {ay: tutar} - fatura kesilmemis
        self.sgk_alacak = {}           # {odeme_tarihi: tutar} - fatura kesilmis, odeme bekliyor
        self.depo_acik_hesap = {}      # {ay: tutar} - senet kesilmemis
        self.depo_borc = {}            # {odeme_tarihi: tutar} - senet kesilmis
        self.kredi_karti_bekleyen = {} # {odeme_tarihi: tutar}
        self.emekli_katilim_bekleyen = {} # {odeme_tarihi: tutar}

        # Gunluk veriler (data grid icin)
        self.gunluk_veriler = []

        # Ozet veriler
        self.ozet = {}

    def sifirla(self):
        """Tum verileri sifirla"""
        self.durum = {}
        self.sgk_acik_hesap = {}
        self.sgk_alacak = {}
        self.depo_acik_hesap = {}
        self.depo_borc = {}
        self.kredi_karti_bekleyen = {}
        self.emekli_katilim_bekleyen = {}
        self.gunluk_veriler = []
        self.ozet = {}


class MFAnalizGUI:
    """MF Analiz ana penceresi - Coklu senaryo destekli"""

    MAX_SENARYO = 5

    def __init__(self, root=None, ana_menu_callback=None):
        self.ana_menu_callback = ana_menu_callback

        if root is None:
            self.root = tk.Tk()
            self.standalone = True
        else:
            if isinstance(root, tk.Toplevel):
                self.root = root
            else:
                self.root = tk.Toplevel(root)
            self.standalone = False

        self.root.title("MF Analiz - Mal Fazlasi Simulasyonu")
        self.root.state('zoomed')

        # Renk paleti
        self.colors = {
            'bg': '#1a1a2e',
            'panel_bg': '#16213e',
            'card_bg': '#1f3460',
            'accent': '#e94560',
            'accent2': '#0f3460',
            'text': '#ffffff',
            'text_dim': '#a0a0b0',
            'entry_bg': '#2a2a4a',
            'border': '#3a3a5a',
            'success': '#00d26a',
            'warning': '#ffc107',
            'danger': '#ff6b6b',
            'info': '#17a2b8',
            'tab_colors': ['#e94560', '#00d26a', '#ffc107', '#17a2b8', '#9b59b6'],
        }

        self.root.configure(bg=self.colors['bg'])

        # Senaryo verileri
        self.senaryolar = {}  # {sekme_id: SenaryoVerileri}
        self.aktif_senaryo_sayisi = 1

        # Simulasyon kontrol
        self.simulasyon_calisyor = False
        self.simulasyon_thread = None
        self.mevcut_gun = 0

        # Widget referanslari
        self.senaryo_frames = {}
        self.senaryo_vars = {}
        self.senaryo_trees = {}
        self.senaryo_tabs = {}

        self._arayuz_olustur()

    def _arayuz_olustur(self):
        """Ana arayuzu olustur"""
        # Ana container - PanedWindow ile bolunmus
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Ust kisim: Baslik + Senaryo sekmeleri
        ust_frame = tk.Frame(self.main_paned, bg=self.colors['bg'])
        self.main_paned.add(ust_frame, weight=3)

        # Baslik
        self._baslik_olustur(ust_frame)

        # Senaryo notebook (sekmeler)
        self._senaryo_notebook_olustur(ust_frame)

        # Alt kisim: Ortak kontroller + Karsilastirma ozeti
        alt_frame = tk.Frame(self.main_paned, bg=self.colors['bg'])
        self.main_paned.add(alt_frame, weight=1)

        # Ortak kontrol paneli
        self._kontrol_paneli_olustur(alt_frame)

        # Karsilastirma ozeti
        self._karsilastirma_ozeti_olustur(alt_frame)

    def _baslik_olustur(self, parent):
        """Baslik alani"""
        baslik_frame = tk.Frame(parent, bg=self.colors['bg'])
        baslik_frame.pack(fill=tk.X, pady=(0, 5))

        baslik = tk.Label(
            baslik_frame,
            text="MF ANALIZ - MAL FAZLASI SIMULASYONU",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg']
        )
        baslik.pack(side=tk.LEFT, padx=10)

        # Sekme ekleme butonu
        ekle_btn = tk.Button(
            baslik_frame,
            text="+ Senaryo Ekle",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'],
            fg='white',
            relief='flat',
            cursor='hand2',
            command=self._senaryo_ekle
        )
        ekle_btn.pack(side=tk.RIGHT, padx=10)

    def _senaryo_notebook_olustur(self, parent):
        """Senaryo sekmeleri"""
        # Notebook stili
        style = ttk.Style()
        style.configure('Senaryo.TNotebook', background=self.colors['bg'])
        style.configure('Senaryo.TNotebook.Tab',
                       padding=[15, 5],
                       font=('Segoe UI', 10, 'bold'))

        self.notebook = ttk.Notebook(parent, style='Senaryo.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Ilk senaryoyu ekle
        self._senaryo_sekme_olustur(0)

    def _senaryo_ekle(self):
        """Yeni senaryo sekmesi ekle"""
        if self.aktif_senaryo_sayisi >= self.MAX_SENARYO:
            messagebox.showwarning("Uyari", f"En fazla {self.MAX_SENARYO} senaryo ekleyebilirsiniz!")
            return

        self._senaryo_sekme_olustur(self.aktif_senaryo_sayisi)
        self.aktif_senaryo_sayisi += 1

    def _senaryo_sekme_olustur(self, idx):
        """Tek bir senaryo sekmesi olustur"""
        # Senaryo verisi
        self.senaryolar[idx] = SenaryoVerileri()

        # Sekme frame
        tab_frame = tk.Frame(self.notebook, bg=self.colors['panel_bg'])
        self.notebook.add(tab_frame, text=f"Senaryo {idx + 1}")
        self.senaryo_tabs[idx] = tab_frame

        # Degiskenler
        self.senaryo_vars[idx] = self._degiskenler_olustur()

        # Ust kisim: Parametreler
        param_frame = tk.Frame(tab_frame, bg=self.colors['panel_bg'])
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        self._parametre_panelleri_olustur(param_frame, idx)

        # Kopyala butonu
        kopyala_frame = tk.Frame(tab_frame, bg=self.colors['panel_bg'])
        kopyala_frame.pack(fill=tk.X, padx=5)

        kopyala_btn = tk.Button(
            kopyala_frame,
            text="Sonraki Sekmeye Kopyala →",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['info'],
            fg='white',
            relief='flat',
            cursor='hand2',
            command=lambda i=idx: self._sonraki_sekmeye_kopyala(i)
        )
        kopyala_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        # Alt kisim: Data Grid
        grid_frame = tk.Frame(tab_frame, bg=self.colors['panel_bg'])
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._data_grid_olustur(grid_frame, idx)

        self.senaryo_frames[idx] = tab_frame

    def _degiskenler_olustur(self):
        """Bir senaryo icin tum degiskenleri olustur"""
        return {
            # A) Eczane Durumu
            'stok': tk.StringVar(value="100"),
            'aylik_sarf': tk.StringVar(value="30"),
            'bugun_tarihi': tk.StringVar(value=datetime.now().strftime("%d.%m.%Y")),

            # B) Ilac Verileri
            'depocu_fiyat': tk.StringVar(value="100.00"),
            'kamu_fiyat': tk.StringVar(value="120.00"),
            'piyasa_fiyat': tk.StringVar(value="150.00"),
            'ilac_farki': tk.StringVar(value="0.00"),

            # C) Satin Alma
            'mf_miktar': tk.StringVar(value="100+10"),  # 100 al + 10 bedava
            'alim_tarihi': tk.StringVar(value=datetime.now().strftime("%d.%m.%Y")),
            'vade_gun': tk.StringVar(value="90"),

            # D) Dis Etkenler
            'zam_tarihi': tk.StringVar(value=""),
            'zam_orani': tk.StringVar(value="0"),
            'mevduat_faizi': tk.StringVar(value="0.12"),  # Gunluk %
            'kredi_faizi': tk.StringVar(value="0.18"),    # Gunluk %
            'pos_komisyon': tk.StringVar(value="2.75"),   # Ertesi gun %
            'blokeli_gun': tk.StringVar(value="30"),      # Blokeli kac gun
            'pos_modu': tk.StringVar(value="blokeli"),    # blokeli veya ertesi_gun
            'kasadan_bankaya': tk.StringVar(value="ertesi_gun"),  # ertesi_gun veya beklet

            # E) Eczane Profili
            'nakit_pos_orani': tk.StringVar(value="50/50"),
            'sgk_perakende_orani': tk.StringVar(value="80/20"),
            'emekli_calisan_orani': tk.StringVar(value="40/60"),
            'banka_baslangic': tk.StringVar(value="50000"),
        }

    def _parametre_panelleri_olustur(self, parent, idx):
        """5 bolumlu parametre paneli"""
        vars = self.senaryo_vars[idx]

        # 5 sutun
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.columnconfigure(4, weight=1)

        # A) Eczane Durumu (tarih alani var)
        self._panel_a_olustur(parent, 0, vars)

        # B) Ilac Verileri (fiyat alanlari - decimal)
        self._panel_b_olustur(parent, 1, vars)

        # C) Satin Alma (tarih alani var)
        self._panel_c_olustur(parent, 2, vars)

        # D) Dis Etkenler
        self._panel_d_olustur(parent, 3, vars)

        # E) Eczane Profili
        self._panel_olustur(parent, 4, "E) ECZANE PROFILI", self.colors['tab_colors'][4], [
            ("Nakit/POS:", vars['nakit_pos_orani']),
            ("SGK/Prknd:", vars['sgk_perakende_orani']),
            ("Emk/Clsn:", vars['emekli_calisan_orani']),
            ("Banka Basl:", vars['banka_baslangic']),
        ])

    def _panel_a_olustur(self, parent, col, vars):
        """A paneli - Eczane Durumu (tarih alani ile)"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        header = tk.Frame(kart, bg=self.colors['tab_colors'][0], height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="A) ECZANE DURUMU", font=('Segoe UI', 12, 'bold'),
                fg='white', bg=self.colors['tab_colors'][0]).pack(expand=True)

        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Stok
        row1 = tk.Frame(content, bg=self.colors['card_bg'])
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="Stok:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=vars['stok'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=12, justify='center').pack(side=tk.RIGHT)

        # Aylik Sarf
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="Aylik Sarf:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['aylik_sarf'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=12, justify='center').pack(side=tk.RIGHT)

        # Bugun - Takvim
        row3 = tk.Frame(content, bg=self.colors['card_bg'])
        row3.pack(fill=tk.X, pady=4)
        tk.Label(row3, text="Bugun:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        DateEntry(row3, textvariable=vars['bugun_tarihi'],
                 font=('Segoe UI', 10), width=12,
                 background='#0f3460', foreground='white',
                 headersbackground='#e94560', headersforeground='white',
                 selectbackground='#e94560', selectforeground='white',
                 normalbackground='#1a1a2e', normalforeground='white',
                 date_pattern='dd.mm.yyyy', locale='tr_TR').pack(side=tk.RIGHT)

    def _panel_b_olustur(self, parent, col, vars):
        """B paneli - Ilac Verileri (decimal fiyat alanlari)"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        header = tk.Frame(kart, bg=self.colors['tab_colors'][1], height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="B) ILAC VERILERI", font=('Segoe UI', 12, 'bold'),
                fg='white', bg=self.colors['tab_colors'][1]).pack(expand=True)

        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Fiyat alanlari (decimal)
        fiyat_alanlari = [
            ("Depocu (TL):", vars['depocu_fiyat']),
            ("Kamu (TL):", vars['kamu_fiyat']),
            ("Piyasa (TL):", vars['piyasa_fiyat']),
            ("Fark (TL):", vars['ilac_farki']),
        ]

        for label_text, var in fiyat_alanlari:
            row = tk.Frame(content, bg=self.colors['card_bg'])
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label_text, font=('Segoe UI', 10),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, textvariable=var, font=('Segoe UI', 11),
                           bg=self.colors['entry_bg'], fg=self.colors['text'],
                           relief='flat', width=12, justify='right')
            entry.pack(side=tk.RIGHT)
            # Decimal format icin event binding
            entry.bind('<FocusOut>', lambda e, v=var: self._format_decimal(v))

    def _panel_c_olustur(self, parent, col, vars):
        """C paneli - Satin Alma (tarih alani ile)"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        header = tk.Frame(kart, bg=self.colors['tab_colors'][2], height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="C) SATIN ALMA", font=('Segoe UI', 12, 'bold'),
                fg='white', bg=self.colors['tab_colors'][2]).pack(expand=True)

        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # MF Miktar
        row1 = tk.Frame(content, bg=self.colors['card_bg'])
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="MF (100+10):", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=vars['mf_miktar'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=12, justify='center').pack(side=tk.RIGHT)

        # Alim Tarihi - Takvim
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="Alim Tarihi:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        DateEntry(row2, textvariable=vars['alim_tarihi'],
                 font=('Segoe UI', 10), width=12,
                 background='#0f3460', foreground='white',
                 headersbackground='#e94560', headersforeground='white',
                 selectbackground='#e94560', selectforeground='white',
                 normalbackground='#1a1a2e', normalforeground='white',
                 date_pattern='dd.mm.yyyy', locale='tr_TR').pack(side=tk.RIGHT)

        # Vade
        row3 = tk.Frame(content, bg=self.colors['card_bg'])
        row3.pack(fill=tk.X, pady=4)
        tk.Label(row3, text="Vade (gun):", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=vars['vade_gun'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=12, justify='center').pack(side=tk.RIGHT)

    def _format_decimal(self, var):
        """Fiyat degerini 2 ondalik basamakli formata cevir"""
        try:
            value = var.get().replace(',', '.')
            num = float(value)
            var.set(f"{num:.2f}")
        except:
            pass

    def _panel_olustur(self, parent, col, baslik, renk, alanlar):
        """Standart parametre paneli"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        # Baslik
        header = tk.Frame(kart, bg=renk, height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text=baslik, font=('Segoe UI', 12, 'bold'),
                fg='white', bg=renk).pack(expand=True)

        # Alanlar
        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        for label_text, var in alanlar:
            row = tk.Frame(content, bg=self.colors['card_bg'])
            row.pack(fill=tk.X, pady=4)

            tk.Label(row, text=label_text, font=('Segoe UI', 10),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg'],
                    width=12, anchor='w').pack(side=tk.LEFT)

            tk.Entry(row, textvariable=var, font=('Segoe UI', 11),
                    bg=self.colors['entry_bg'], fg=self.colors['text'],
                    insertbackground=self.colors['text'], relief='flat',
                    width=12, justify='center').pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _panel_d_olustur(self, parent, col, vars):
        """D paneli - Dis etkenler (ozel kontroller)"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        # Baslik
        header = tk.Frame(kart, bg=self.colors['tab_colors'][3], height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="D) DIS ETKENLER", font=('Segoe UI', 12, 'bold'),
                fg='white', bg=self.colors['tab_colors'][3]).pack(expand=True)

        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=8)
        content.pack(fill=tk.BOTH, expand=True)

        # Zam Tarihi
        row1 = tk.Frame(content, bg=self.colors['card_bg'])
        row1.pack(fill=tk.X, pady=3)
        tk.Label(row1, text="Zam Tarihi:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)

        # Takvim ile tarih secimi
        zam_date = DateEntry(row1, textvariable=vars['zam_tarihi'],
                            font=('Segoe UI', 9), width=10,
                            background='#0f3460', foreground='white',
                            headersbackground='#e94560', headersforeground='white',
                            selectbackground='#e94560', selectforeground='white',
                            normalbackground='#1a1a2e', normalforeground='white',
                            weekendbackground='#2a2a4a', weekendforeground='#ff6b6b',
                            othermonthbackground='#16213e', othermonthforeground='gray',
                            date_pattern='dd.mm.yyyy', locale='tr_TR')
        zam_date.pack(side=tk.LEFT, padx=3)
        zam_date.delete(0, 'end')  # Bos baslat

        # Zam Orani
        row1b = tk.Frame(content, bg=self.colors['card_bg'])
        row1b.pack(fill=tk.X, pady=3)
        tk.Label(row1b, text="Zam Orani:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row1b, textvariable=vars['zam_orani'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=6).pack(side=tk.LEFT, padx=3)
        tk.Label(row1b, text="%", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)

        # Faizler
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Mvdt%:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['mevduat_faizi'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=6).pack(side=tk.LEFT, padx=3)
        tk.Label(row2, text="Krd%:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['kredi_faizi'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=6).pack(side=tk.LEFT)

        # POS
        row3 = tk.Frame(content, bg=self.colors['card_bg'])
        row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="POS%:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=vars['pos_komisyon'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=5).pack(side=tk.LEFT, padx=3)
        tk.Label(row3, text="Blk:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=vars['blokeli_gun'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=4).pack(side=tk.LEFT)

        # POS Modu
        row4 = tk.Frame(content, bg=self.colors['card_bg'])
        row4.pack(fill=tk.X, pady=3)
        tk.Radiobutton(row4, text="Blokeli", variable=vars['pos_modu'],
                      value="blokeli", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT)
        tk.Radiobutton(row4, text="Ertesi Gun", variable=vars['pos_modu'],
                      value="ertesi_gun", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT, padx=10)

        # Kasa -> Banka
        row5 = tk.Frame(content, bg=self.colors['card_bg'])
        row5.pack(fill=tk.X, pady=3)
        tk.Radiobutton(row5, text="Bankaya", variable=vars['kasadan_bankaya'],
                      value="ertesi_gun", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT)
        tk.Radiobutton(row5, text="Beklet", variable=vars['kasadan_bankaya'],
                      value="beklet", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT, padx=10)

    def _data_grid_olustur(self, parent, idx):
        """Senaryo icin data grid"""
        # Stil - koyu tema
        style = ttk.Style()
        style.configure(f'Grid{idx}.Treeview',
                       background='#1a1a2e',
                       foreground='#ffffff',
                       fieldbackground='#1a1a2e',
                       rowheight=24,
                       font=('Segoe UI', 9))
        style.map(f'Grid{idx}.Treeview',
                 background=[('selected', '#e94560')],
                 foreground=[('selected', 'white')])
        style.configure(f'Grid{idx}.Treeview.Heading',
                       background='#0f3460',
                       foreground='white',
                       font=('Segoe UI', 9, 'bold'),
                       relief='flat')
        style.map(f'Grid{idx}.Treeview.Heading',
                 background=[('active', '#16213e')])

        # Container
        container = tk.Frame(parent, bg=self.colors['panel_bg'])
        container.pack(fill=tk.BOTH, expand=True)

        # Kolonlar
        columns = (
            'gun', 'tarih', 'stok', 'satis', 'kasa', 'banka',
            'sgk_alacak', 'depo_borc', 'banka_borc',
            'kk_bekleyen', 'emk_bekleyen', 'faiz_gelir', 'faiz_gider', 'ozkaynak'
        )

        tree = ttk.Treeview(container, columns=columns, show='headings',
                           style=f'Grid{idx}.Treeview', height=8)

        # Kolon basliklari
        headers = {
            'gun': ('Gun', 40),
            'tarih': ('Tarih', 75),
            'stok': ('Stok', 50),
            'satis': ('Satis', 60),
            'kasa': ('Kasa', 70),
            'banka': ('Banka', 80),
            'sgk_alacak': ('SGK Alc', 80),
            'depo_borc': ('Depo Brc', 80),
            'banka_borc': ('Bnk Brc', 70),
            'kk_bekleyen': ('KK Bkl', 70),
            'emk_bekleyen': ('Emk Bkl', 70),
            'faiz_gelir': ('Fz Glr', 60),
            'faiz_gider': ('Fz Gdr', 60),
            'ozkaynak': ('Ozkynk', 90)
        }

        for col, (header, width) in headers.items():
            tree.heading(col, text=header)
            tree.column(col, width=width, anchor='center', minwidth=40)

        # Scrollbar
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.senaryo_trees[idx] = tree

    def _sonraki_sekmeye_kopyala(self, idx):
        """Mevcut sekmenin verilerini sonraki sekmeye kopyala"""
        sonraki_idx = idx + 1

        # Sonraki sekme yoksa olustur
        if sonraki_idx not in self.senaryo_vars:
            if self.aktif_senaryo_sayisi >= self.MAX_SENARYO:
                messagebox.showwarning("Uyari", f"En fazla {self.MAX_SENARYO} senaryo!")
                return
            self._senaryo_sekme_olustur(sonraki_idx)
            self.aktif_senaryo_sayisi += 1

        # Degiskenleri kopyala
        kaynak = self.senaryo_vars[idx]
        hedef = self.senaryo_vars[sonraki_idx]

        for key in kaynak:
            hedef[key].set(kaynak[key].get())

        # Sonraki sekmeye gec
        self.notebook.select(sonraki_idx)

        messagebox.showinfo("Bilgi", f"Veriler Senaryo {sonraki_idx + 1}'e kopyalandi!")

    def _kontrol_paneli_olustur(self, parent):
        """Ortak kontrol paneli"""
        kontrol_frame = tk.Frame(parent, bg=self.colors['accent2'], pady=8)
        kontrol_frame.pack(fill=tk.X, pady=(5, 0))

        inner = tk.Frame(kontrol_frame, bg=self.colors['accent2'])
        inner.pack()

        # Simulasyon hizi
        tk.Label(inner, text="Hiz(ms):", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=5)

        self.hiz_var = tk.StringVar(value="50")
        tk.Entry(inner, textvariable=self.hiz_var, font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=5, justify='center').pack(side=tk.LEFT)

        # Gun sayisi
        tk.Label(inner, text="Gun:", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=(20, 5))

        self.gun_sayisi_var = tk.StringVar(value="30")
        tk.Entry(inner, textvariable=self.gun_sayisi_var, font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=5, justify='center').pack(side=tk.LEFT)

        # Butonlar
        btn_style = {'font': ('Segoe UI', 10, 'bold'), 'relief': 'flat',
                    'cursor': 'hand2', 'width': 12}

        self.adim_btn = tk.Button(inner, text="ADIM (1 Gun)",
                                 bg='#6366f1', fg='white',
                                 command=self._adim_oynat, **btn_style)
        self.adim_btn.pack(side=tk.LEFT, padx=10)

        self.gun_btn = tk.Button(inner, text="Gun Oynat",
                                bg='#8b5cf6', fg='white',
                                command=self._x_gun_oynat, **btn_style)
        self.gun_btn.pack(side=tk.LEFT, padx=5)

        self.sonuna_btn = tk.Button(inner, text="SONUNA KADAR",
                                   bg=self.colors['success'], fg='white',
                                   command=self._sonuna_kadar_oynat, **btn_style)
        self.sonuna_btn.pack(side=tk.LEFT, padx=5)

        self.durdur_btn = tk.Button(inner, text="DURDUR",
                                   bg=self.colors['danger'], fg='white',
                                   command=self._durdur, state='disabled', **btn_style)
        self.durdur_btn.pack(side=tk.LEFT, padx=5)

        self.sifirla_btn = tk.Button(inner, text="SIFIRLA",
                                    bg=self.colors['warning'], fg='black',
                                    command=self._sifirla, **btn_style)
        self.sifirla_btn.pack(side=tk.LEFT, padx=5)

        # Mevcut gun
        tk.Label(inner, text="Mevcut Gun:", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=(20, 5))

        self.mevcut_gun_label = tk.Label(inner, text="0", font=('Segoe UI', 11, 'bold'),
                                        fg=self.colors['accent'], bg=self.colors['accent2'])
        self.mevcut_gun_label.pack(side=tk.LEFT)

    def _karsilastirma_ozeti_olustur(self, parent):
        """Karsilastirma ozeti tablosu"""
        ozet_frame = tk.LabelFrame(parent, text=" KARSILASTIRMA OZETI ",
                                  font=('Segoe UI', 12, 'bold'),
                                  fg=self.colors['accent'], bg=self.colors['panel_bg'])
        ozet_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tablo container
        tablo_frame = tk.Frame(ozet_frame, bg=self.colors['panel_bg'])
        tablo_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Basliklar
        basliklar = ['', 'Kasa', 'Mal', 'Banka', 'SGK Alc', 'KK Bkl', 'Emk Bkl',
                    'Depo Brc', 'Bnk Brc', 'Fz Glr', 'Fz Gdr', 'OZKAYNAK']

        for col, baslik in enumerate(basliklar):
            lbl = tk.Label(tablo_frame, text=baslik, font=('Segoe UI', 10, 'bold'),
                          fg=self.colors['text'], bg=self.colors['accent2'],
                          width=11, height=2, relief='solid', bd=1)
            lbl.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # Senaryo satirlari (5 adet)
        self.ozet_labels = {}
        for i in range(self.MAX_SENARYO):
            renk = self.colors['tab_colors'][i]

            # Senaryo adi
            lbl = tk.Label(tablo_frame, text=f"Senaryo {i+1}", font=('Segoe UI', 10, 'bold'),
                          fg='white', bg=renk, width=11, height=2, relief='solid', bd=1)
            lbl.grid(row=i+1, column=0, sticky='nsew', padx=1, pady=1)

            self.ozet_labels[i] = {}
            for col, _ in enumerate(basliklar[1:], 1):
                lbl = tk.Label(tablo_frame, text="-", font=('Segoe UI', 10),
                              fg=self.colors['text'], bg=self.colors['card_bg'],
                              width=11, height=2, relief='solid', bd=1)
                lbl.grid(row=i+1, column=col, sticky='nsew', padx=1, pady=1)
                self.ozet_labels[i][col-1] = lbl

        # En karli senaryo
        self.en_karli_label = tk.Label(ozet_frame, text="",
                                       font=('Segoe UI', 13, 'bold'),
                                       fg=self.colors['success'], bg=self.colors['panel_bg'])
        self.en_karli_label.pack(pady=8)

    # ==================== SIMULASYON FONKSIYONLARI ====================

    def _oran_parse(self, oran_str):
        """Oran stringini parse et (ornegin '30/70' -> (0.3, 0.7))"""
        try:
            parts = oran_str.replace(' ', '').split('/')
            if len(parts) == 2:
                a, b = float(parts[0]), float(parts[1])
                toplam = a + b
                return (a / toplam, b / toplam)
        except:
            pass
        return (0.5, 0.5)

    def _mf_parse(self, mf_str):
        """MF stringini parse et (ornegin '100+10' -> (100, 10))"""
        try:
            parts = mf_str.replace(' ', '').split('+')
            if len(parts) == 2:
                return (int(parts[0]), int(parts[1]))
            elif len(parts) == 1:
                return (int(parts[0]), 0)
        except:
            pass
        return (0, 0)

    def _senaryo_baslat(self, idx):
        """Tek bir senaryoyu baslat"""
        if idx not in self.senaryo_vars:
            return False

        vars = self.senaryo_vars[idx]
        senaryo = self.senaryolar[idx]
        senaryo.sifirla()

        try:
            # Parametreleri al
            stok = float(vars['stok'].get())
            aylik_sarf = float(vars['aylik_sarf'].get())
            gunluk_sarf = aylik_sarf / 30

            depocu_fiyat = float(vars['depocu_fiyat'].get())
            kamu_fiyat = float(vars['kamu_fiyat'].get())
            piyasa_fiyat = float(vars['piyasa_fiyat'].get())
            ilac_farki = float(vars['ilac_farki'].get())

            alim_adet, mf_bedava = self._mf_parse(vars['mf_miktar'].get())
            toplam_alim = alim_adet + mf_bedava
            vade = int(vars['vade_gun'].get())

            mevduat_faizi = float(vars['mevduat_faizi'].get()) / 100
            kredi_faizi = float(vars['kredi_faizi'].get()) / 100
            pos_komisyon = float(vars['pos_komisyon'].get()) / 100
            blokeli_gun = int(vars['blokeli_gun'].get())
            pos_modu = vars['pos_modu'].get()
            kasadan_bankaya = vars['kasadan_bankaya'].get()

            nakit_oran, pos_oran = self._oran_parse(vars['nakit_pos_orani'].get())
            sgk_oran, perakende_oran = self._oran_parse(vars['sgk_perakende_orani'].get())
            emekli_oran, calisan_oran = self._oran_parse(vars['emekli_calisan_orani'].get())

            banka_baslangic = float(vars['banka_baslangic'].get())

            # Tarihleri parse et
            try:
                bugun = datetime.strptime(vars['bugun_tarihi'].get(), "%d.%m.%Y")
            except:
                bugun = datetime.now()

            try:
                alim_tarihi = datetime.strptime(vars['alim_tarihi'].get(), "%d.%m.%Y")
            except:
                alim_tarihi = bugun

            zam_tarihi = None
            zam_orani = 0
            if vars['zam_tarihi'].get().strip():
                try:
                    zam_tarihi = datetime.strptime(vars['zam_tarihi'].get(), "%d.%m.%Y")
                    zam_orani = float(vars['zam_orani'].get()) / 100
                except:
                    pass

            # Birim maliyet (MF dahil)
            if toplam_alim > 0:
                birim_maliyet = (alim_adet * depocu_fiyat) / toplam_alim
            else:
                birim_maliyet = depocu_fiyat

            # Alim tarihi bugun veya oncesiyse, depo borcuna yaz
            depo_borc_toplam = 0
            if alim_tarihi <= bugun and toplam_alim > 0:
                depo_borc_toplam = alim_adet * depocu_fiyat
                # Vade hesapla - ay sonu senet, 90 gun sonra odeme
                ay_sonu = alim_tarihi.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
                odeme_tarihi = ay_sonu + timedelta(days=vade)
                senaryo.depo_borc[odeme_tarihi] = depo_borc_toplam

            # Durum kaydet
            senaryo.durum = {
                'stok': stok,
                'gunluk_sarf': gunluk_sarf,
                'depocu_fiyat': depocu_fiyat,
                'kamu_fiyat': kamu_fiyat,
                'piyasa_fiyat': piyasa_fiyat,
                'ilac_farki': ilac_farki,
                'birim_maliyet': birim_maliyet,
                'vade': vade,
                'mevduat_faizi': mevduat_faizi,
                'kredi_faizi': kredi_faizi,
                'pos_komisyon': pos_komisyon,
                'blokeli_gun': blokeli_gun,
                'pos_modu': pos_modu,
                'kasadan_bankaya': kasadan_bankaya,
                'nakit_oran': nakit_oran,
                'pos_oran': pos_oran,
                'sgk_oran': sgk_oran,
                'perakende_oran': perakende_oran,
                'emekli_oran': emekli_oran,
                'calisan_oran': calisan_oran,
                'bugun': bugun,
                'alim_tarihi': alim_tarihi,
                'zam_tarihi': zam_tarihi,
                'zam_orani': zam_orani,
                'kasa': 0,
                'banka': banka_baslangic,
                'banka_borc': 0,
                'toplam_faiz_gelir': 0,
                'toplam_faiz_gider': 0,
            }

            senaryo.params = dict(vars)
            return True

        except Exception as e:
            messagebox.showerror("Hata", f"Senaryo {idx+1} baslatilamadi: {e}")
            return False

    def _tum_senaryolari_baslat(self):
        """Tum aktif senaryolari baslat"""
        for idx in range(self.aktif_senaryo_sayisi):
            if not self._senaryo_baslat(idx):
                return False
        self.mevcut_gun = 0
        return True

    def _bir_gun_hesapla(self, idx):
        """Tek senaryo icin bir gun hesapla"""
        senaryo = self.senaryolar[idx]
        d = senaryo.durum

        if not d or d['stok'] <= 0:
            return False

        gun = self.mevcut_gun
        mevcut_tarih = d['bugun'] + timedelta(days=gun)

        # Zam kontrolu
        if d['zam_tarihi'] and mevcut_tarih >= d['zam_tarihi']:
            d['kamu_fiyat'] *= (1 + d['zam_orani'])
            d['piyasa_fiyat'] *= (1 + d['zam_orani'])
            d['zam_tarihi'] = None

        # Gunluk satis
        satis_miktari = min(d['gunluk_sarf'], d['stok'])
        d['stok'] -= satis_miktari

        # SGK satisi
        sgk_satis = satis_miktari * d['sgk_oran']
        sgk_tutar = sgk_satis * d['kamu_fiyat']

        # Emekli/Calisan katilim payi
        emekli_satis = sgk_satis * d['emekli_oran']
        calisan_satis = sgk_satis * d['calisan_oran']

        emekli_katilim = emekli_satis * d['kamu_fiyat'] * 0.10
        calisan_katilim = calisan_satis * d['kamu_fiyat'] * 0.20

        # Fark (tum SGK satislarindan)
        fark_tutar = sgk_satis * d['ilac_farki']

        # Perakende satis
        perakende_satis = satis_miktari * d['perakende_oran']
        perakende_tutar = perakende_satis * d['piyasa_fiyat']

        # Kasaya girenler (anlik)
        # Calisan katilimi + fark + perakende (nakit kismi)
        nakit_giris = (calisan_katilim + fark_tutar + perakende_tutar) * d['nakit_oran']
        d['kasa'] += nakit_giris

        # POS girisleri
        pos_giris = (calisan_katilim + fark_tutar + perakende_tutar) * d['pos_oran']

        if d['pos_modu'] == 'ertesi_gun':
            # Ertesi gun komisyon kesilip geliyor
            komisyon_sonrasi = pos_giris * (1 - d['pos_komisyon'])
            d['kasa'] += komisyon_sonrasi  # Basitlik icin ayni gun kasaya
        else:
            # Blokeli - X gun sonra gelecek
            odeme_tarihi = mevcut_tarih + timedelta(days=d['blokeli_gun'])
            if odeme_tarihi not in senaryo.kredi_karti_bekleyen:
                senaryo.kredi_karti_bekleyen[odeme_tarihi] = 0
            senaryo.kredi_karti_bekleyen[odeme_tarihi] += pos_giris

        # Emekli katilimi - 2 ay sonra
        emekli_odeme = mevcut_tarih + relativedelta(months=2)
        emekli_odeme = emekli_odeme.replace(day=1) - timedelta(days=1)  # Ay sonu
        if emekli_odeme not in senaryo.emekli_katilim_bekleyen:
            senaryo.emekli_katilim_bekleyen[emekli_odeme] = 0
        senaryo.emekli_katilim_bekleyen[emekli_odeme] += emekli_katilim

        # SGK alacak - ay sonu fatura, 90 gun sonra odeme
        ay_sonu = mevcut_tarih.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        sgk_net = sgk_tutar - emekli_katilim - calisan_katilim  # Katilimlar dusulmus

        ay_key = mevcut_tarih.strftime("%Y-%m")
        if ay_key not in senaryo.sgk_acik_hesap:
            senaryo.sgk_acik_hesap[ay_key] = 0
        senaryo.sgk_acik_hesap[ay_key] += sgk_net

        # Ay sonu ise SGK acik hesabi alacaga cevir
        if mevcut_tarih.day == ay_sonu.day:
            for ay, tutar in list(senaryo.sgk_acik_hesap.items()):
                odeme = ay_sonu + timedelta(days=90)
                if odeme not in senaryo.sgk_alacak:
                    senaryo.sgk_alacak[odeme] = 0
                senaryo.sgk_alacak[odeme] += tutar
            senaryo.sgk_acik_hesap = {}

        # Kasadan bankaya transfer
        if d['kasadan_bankaya'] == 'ertesi_gun' and d['kasa'] > 0:
            d['banka'] += d['kasa']
            d['kasa'] = 0

        # Kredi karti tahsilatlari
        for tarih in list(senaryo.kredi_karti_bekleyen.keys()):
            if tarih <= mevcut_tarih:
                d['banka'] += senaryo.kredi_karti_bekleyen.pop(tarih)

        # Emekli katilim tahsilatlari
        for tarih in list(senaryo.emekli_katilim_bekleyen.keys()):
            if tarih <= mevcut_tarih:
                d['banka'] += senaryo.emekli_katilim_bekleyen.pop(tarih)

        # SGK tahsilatlari
        for tarih in list(senaryo.sgk_alacak.keys()):
            if tarih <= mevcut_tarih:
                d['banka'] += senaryo.sgk_alacak.pop(tarih)

        # Depo odemeleri
        for tarih in list(senaryo.depo_borc.keys()):
            if tarih <= mevcut_tarih:
                borc = senaryo.depo_borc.pop(tarih)
                if d['banka'] >= borc:
                    d['banka'] -= borc
                else:
                    # Eksik kisim icin kredi
                    eksik = borc - d['banka']
                    d['banka'] = 0
                    d['banka_borc'] += eksik

        # Banka borcu odeme (kasada/bankada para varsa)
        if d['banka_borc'] > 0 and d['banka'] > 0:
            odeme = min(d['banka_borc'], d['banka'])
            d['banka'] -= odeme
            d['banka_borc'] -= odeme

        # Faiz hesaplari
        if d['banka'] > 0:
            faiz_gelir = d['banka'] * d['mevduat_faizi']
            d['banka'] += faiz_gelir
            d['toplam_faiz_gelir'] += faiz_gelir

        if d['banka_borc'] > 0:
            faiz_gider = d['banka_borc'] * d['kredi_faizi']
            d['banka_borc'] += faiz_gider
            d['toplam_faiz_gider'] += faiz_gider

        # Toplam bekleyen hesaplar
        sgk_alacak_toplam = sum(senaryo.sgk_alacak.values()) + sum(senaryo.sgk_acik_hesap.values())
        depo_borc_toplam = sum(senaryo.depo_borc.values())
        kk_bekleyen_toplam = sum(senaryo.kredi_karti_bekleyen.values())
        emk_bekleyen_toplam = sum(senaryo.emekli_katilim_bekleyen.values())

        # Stok degeri
        mal_degeri = d['stok'] * d['birim_maliyet']

        # Ozkaynak
        aktifler = d['kasa'] + d['banka'] + sgk_alacak_toplam + kk_bekleyen_toplam + emk_bekleyen_toplam + mal_degeri
        pasifler = depo_borc_toplam + d['banka_borc']
        ozkaynak = aktifler - pasifler

        # Data grid'e ekle
        self._satir_ekle(idx, gun + 1, mevcut_tarih, d['stok'], satis_miktari,
                        d['kasa'], d['banka'], sgk_alacak_toplam, depo_borc_toplam,
                        d['banka_borc'], kk_bekleyen_toplam, emk_bekleyen_toplam,
                        d['toplam_faiz_gelir'], d['toplam_faiz_gider'], ozkaynak)

        # Ozet guncelle
        senaryo.ozet = {
            'kasa': d['kasa'],
            'mal': mal_degeri,
            'banka': d['banka'],
            'sgk_alacak': sgk_alacak_toplam,
            'kk_bekleyen': kk_bekleyen_toplam,
            'emk_bekleyen': emk_bekleyen_toplam,
            'depo_borc': depo_borc_toplam,
            'banka_borc': d['banka_borc'],
            'faiz_gelir': d['toplam_faiz_gelir'],
            'faiz_gider': d['toplam_faiz_gider'],
            'ozkaynak': ozkaynak,
        }

        return d['stok'] > 0

    def _satir_ekle(self, idx, gun, tarih, stok, satis, kasa, banka,
                   sgk_alacak, depo_borc, banka_borc, kk_bekleyen, emk_bekleyen,
                   faiz_gelir, faiz_gider, ozkaynak):
        """Data grid'e satir ekle"""
        if idx in self.senaryo_trees:
            tree = self.senaryo_trees[idx]
            tree.insert('', 'end', values=(
                gun,
                tarih.strftime("%d.%m.%Y"),
                f"{stok:.1f}",
                f"{satis:.2f}",
                f"{kasa:.0f}",
                f"{banka:.0f}",
                f"{sgk_alacak:.0f}",
                f"{depo_borc:.0f}",
                f"{banka_borc:.0f}",
                f"{kk_bekleyen:.0f}",
                f"{emk_bekleyen:.0f}",
                f"{faiz_gelir:.0f}",
                f"{faiz_gider:.0f}",
                f"{ozkaynak:.0f}"
            ))
            # Son satira scroll
            children = tree.get_children()
            if children:
                tree.see(children[-1])

    def _ozet_guncelle(self):
        """Karsilastirma ozetini guncelle"""
        en_yuksek_ozkaynak = None
        en_karli_idx = -1

        for idx in range(self.aktif_senaryo_sayisi):
            if idx in self.senaryolar and self.senaryolar[idx].ozet:
                ozet = self.senaryolar[idx].ozet

                degerler = [
                    ozet.get('kasa', 0),
                    ozet.get('mal', 0),
                    ozet.get('banka', 0),
                    ozet.get('sgk_alacak', 0),
                    ozet.get('kk_bekleyen', 0),
                    ozet.get('emk_bekleyen', 0),
                    ozet.get('depo_borc', 0),
                    ozet.get('banka_borc', 0),
                    ozet.get('faiz_gelir', 0),
                    ozet.get('faiz_gider', 0),
                    ozet.get('ozkaynak', 0),
                ]

                for col, deger in enumerate(degerler):
                    self.ozet_labels[idx][col].config(text=f"{deger:,.0f}")

                ozkaynak = ozet.get('ozkaynak', 0)
                if en_yuksek_ozkaynak is None or ozkaynak > en_yuksek_ozkaynak:
                    en_yuksek_ozkaynak = ozkaynak
                    en_karli_idx = idx

        # En karli senaryo
        if en_karli_idx >= 0:
            self.en_karli_label.config(
                text=f"EN KARLI: Senaryo {en_karli_idx + 1} (Ozkaynak: {en_yuksek_ozkaynak:,.0f} TL)"
            )

    def _adim_oynat(self):
        """Tum senaryolarda tek gun ilerle"""
        if self.mevcut_gun == 0:
            if not self._tum_senaryolari_baslat():
                return

        self.mevcut_gun += 1
        self.mevcut_gun_label.config(text=str(self.mevcut_gun))

        devam = False
        for idx in range(self.aktif_senaryo_sayisi):
            if self._bir_gun_hesapla(idx):
                devam = True

        self._ozet_guncelle()

        if not devam:
            messagebox.showinfo("Bilgi", "Tum senaryolarda stok bitti!")

    def _x_gun_oynat(self):
        """Belirtilen gun kadar oynat"""
        if self.mevcut_gun == 0:
            if not self._tum_senaryolari_baslat():
                return

        try:
            gun_sayisi = int(self.gun_sayisi_var.get())
        except:
            messagebox.showerror("Hata", "Gecersiz gun sayisi!")
            return

        self.simulasyon_calisyor = True
        self._butonlari_ayarla(True)
        self.simulasyon_thread = threading.Thread(
            target=self._oynat_thread, args=(gun_sayisi,), daemon=True
        )
        self.simulasyon_thread.start()

    def _sonuna_kadar_oynat(self):
        """Stok bitene kadar oynat"""
        if self.mevcut_gun == 0:
            if not self._tum_senaryolari_baslat():
                return

        self.simulasyon_calisyor = True
        self._butonlari_ayarla(True)
        self.simulasyon_thread = threading.Thread(
            target=self._oynat_thread, args=(9999,), daemon=True
        )
        self.simulasyon_thread.start()

    def _oynat_thread(self, max_gun):
        """Thread icinde oynat"""
        try:
            hiz = int(self.hiz_var.get())
        except:
            hiz = 50

        for _ in range(max_gun):
            if not self.simulasyon_calisyor:
                break

            self.mevcut_gun += 1
            self.root.after(0, lambda g=self.mevcut_gun: self.mevcut_gun_label.config(text=str(g)))

            devam = False
            for idx in range(self.aktif_senaryo_sayisi):
                if self.senaryolar[idx].durum.get('stok', 0) > 0:
                    self.root.after(0, lambda i=idx: self._bir_gun_hesapla(i))
                    devam = True

            self.root.after(0, self._ozet_guncelle)

            if not devam:
                break

            time.sleep(hiz / 1000)

        self.root.after(0, lambda: self._butonlari_ayarla(False))
        self.simulasyon_calisyor = False

    def _durdur(self):
        """Simulasyonu durdur"""
        self.simulasyon_calisyor = False

    def _butonlari_ayarla(self, calisyor):
        """Butonlari etkinlestir/devre disi birak"""
        durum = 'disabled' if calisyor else 'normal'
        self.adim_btn.config(state=durum)
        self.gun_btn.config(state=durum)
        self.sonuna_btn.config(state=durum)
        self.sifirla_btn.config(state=durum)
        self.durdur_btn.config(state='normal' if calisyor else 'disabled')

    def _sifirla(self):
        """Tum verileri sifirla"""
        self.simulasyon_calisyor = False
        self.mevcut_gun = 0
        self.mevcut_gun_label.config(text="0")

        # Tum senaryolari sifirla
        for idx in self.senaryolar:
            self.senaryolar[idx].sifirla()
            if idx in self.senaryo_trees:
                for item in self.senaryo_trees[idx].get_children():
                    self.senaryo_trees[idx].delete(item)

        # Ozet sifirla
        for idx in range(self.MAX_SENARYO):
            for col in range(11):
                if idx in self.ozet_labels and col in self.ozet_labels[idx]:
                    self.ozet_labels[idx][col].config(text="-")

        self.en_karli_label.config(text="")

    def run(self):
        """Uygulamayi calistir"""
        if self.standalone:
            self.root.mainloop()


# Geriye uyumluluk
NFAnalizGUI = MFAnalizGUI


def main():
    app = MFAnalizGUI()
    app.run()


if __name__ == "__main__":
    main()
