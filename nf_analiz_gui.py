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
import json
import os


class SenaryoVerileri:
    """Tek bir senaryo icin tum verileri tutar"""

    def __init__(self):
        # Parametreler
        self.params = {}

        # Simulasyon durumu
        self.durum = {}

        # ========== SGK HESAPLARI ==========
        self.sgk_acik_hesap = {}       # {ay_key: tutar} - Fatura kesilmemis (ay ici)
        self.sgk_alacak = {}           # {odeme_tarihi: tutar} - Fatura kesilmis, tahsilat bekliyor
        self.muayene_acik_borc = {}    # {ay_key: tutar} - Muayene borcu (ay ici)
        self.muayene_borc = {}         # {odeme_tarihi: tutar} - Muayene borcu kesinlesmis

        # ========== DEPO HESAPLARI ==========
        self.depo_acik_hesap = {}      # {ay_key: tutar} - Senet kesilmemis (ay ici alimlar)
        self.depo_borc = {}            # {odeme_tarihi: tutar} - Senet kesilmis, odeme bekliyor

        # ========== DİĞER HESAPLAR ==========
        self.kredi_karti_bekleyen = {} # {odeme_tarihi: tutar} - Blokeli POS
        self.emekli_katilim_bekleyen = {} # {odeme_tarihi: tutar} - Emekli katilim payi

        # Gunluk veriler (data grid icin)
        self.gunluk_veriler = []

        # Ozet veriler
        self.ozet = {}

    def sifirla(self):
        """Tum verileri sifirla"""
        self.durum = {}
        self.sgk_acik_hesap = {}
        self.sgk_alacak = {}
        self.muayene_acik_borc = {}
        self.muayene_borc = {}
        self.depo_acik_hesap = {}
        self.depo_borc = {}
        self.kredi_karti_bekleyen = {}
        self.emekli_katilim_bekleyen = {}
        self.gunluk_veriler = []
        self.ozet = {}


class MFAnalizGUI:
    """MF Analiz ana penceresi - Coklu senaryo destekli"""

    MAX_SENARYO = 5
    AYARLAR_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mf_analiz_ayarlar.json")
    FATURA_SENET_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fatura_senet_kayitlari.json")

    # Varsayilan degerler (ayarlar dosyasi yoksa kullanilir)
    VARSAYILAN_DEGERLER = {
        "stok": "100",
        "aylik_sarf": "30",
        "depocu_fiyat": "100.00",
        "kamu_fiyat": "120.00",
        "piyasa_fiyat": "150.00",
        "ilac_farki": "0.00",
        "alim_adet": "100",
        "mf_bedava": "10",
        "vade_gun": "90",
        "zam_orani": "0",
        "mevduat_faizi": "45",
        "kredi_faizi": "65",
        "pos_komisyon": "2.75",
        "blokeli_gun": "30",
        "pos_modu": "blokeli",
        "sgk_elden_orani": "70/30",
        "raporlu_raporsuz_orani": "30/70",
        "emekli_calisan_orani": "40/60",
        "nakit_pos_orani": "40/60",
        "muayene_tahsilat_orani": "10",
        "banka_baslangic": "50000"
    }

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
        self.uyari_bekliyor = False  # Uyarı gösterilirken True

        # Widget referanslari
        self.senaryo_frames = {}
        self.senaryo_vars = {}
        self.senaryo_trees = {}
        self.senaryo_tabs = {}

        # Kayitli ayarlari yukle
        self.kayitli_ayarlar = self._ayarlari_yukle()

        # Fatura/Senet kayitlari
        self.fatura_senet_kayitlari = self._fatura_senet_yukle()

        self._arayuz_olustur()

        # Vadesi gelen kayitlar icin uyari goster
        self.root.after(500, self._vade_uyari_kontrol)

    def _arayuz_olustur(self):
        """Ana arayuzu olustur"""
        # Ana container
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Baslik
        self._baslik_olustur(main_frame)

        # Senaryo notebook (sekmeler) - tum alani kaplasın
        self._senaryo_notebook_olustur(main_frame)

        # Alt kisim: Ortak kontroller (karsilastirma butonu dahil)
        self._kontrol_paneli_olustur(main_frame)

        # Karsilastirma popup icin degiskenler
        self.karsilastirma_pencere = None

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

        # Ayarlar butonu
        ayarlar_btn = tk.Button(
            baslik_frame,
            text="Ayarlar",
            font=('Segoe UI', 10, 'bold'),
            bg='#607D8B',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=self._ayarlar_penceresi_ac
        )
        ayarlar_btn.pack(side=tk.RIGHT, padx=5)

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
        """Bir senaryo icin tum degiskenleri olustur - ayarlardan degerler yuklenir"""
        ayar = self.kayitli_ayarlar  # Kisa referans
        return {
            # A) Eczane Durumu
            'stok': tk.StringVar(value=ayar.get("stok", "100")),
            'aylik_sarf': tk.StringVar(value=ayar.get("aylik_sarf", "30")),
            'bugun_tarihi': tk.StringVar(value=datetime.now().strftime("%d.%m.%Y")),

            # B) Ilac Verileri
            'depocu_fiyat': tk.StringVar(value=ayar.get("depocu_fiyat", "100.00")),
            'kamu_fiyat': tk.StringVar(value=ayar.get("kamu_fiyat", "120.00")),
            'piyasa_fiyat': tk.StringVar(value=ayar.get("piyasa_fiyat", "150.00")),
            'ilac_farki': tk.StringVar(value=ayar.get("ilac_farki", "0.00")),

            # C) Satin Alma
            'alim_adet': tk.StringVar(value=ayar.get("alim_adet", "100")),    # Ana mal adedi
            'mf_bedava': tk.StringVar(value=ayar.get("mf_bedava", "10")),     # Mal fazlasi (bedava)
            'alim_tarihi': tk.StringVar(value=datetime.now().strftime("%d.%m.%Y")),
            'vade_gun': tk.StringVar(value=ayar.get("vade_gun", "90")),

            # D) Dis Etkenler
            'zam_tarihi': tk.StringVar(value=""),
            'zam_orani': tk.StringVar(value=ayar.get("zam_orani", "0")),
            'mevduat_faizi': tk.StringVar(value=ayar.get("mevduat_faizi", "45")),  # Yillik %
            'kredi_faizi': tk.StringVar(value=ayar.get("kredi_faizi", "65")),      # Yillik %
            'pos_komisyon': tk.StringVar(value=ayar.get("pos_komisyon", "2.75")),   # Ertesi gun %
            'blokeli_gun': tk.StringVar(value=ayar.get("blokeli_gun", "30")),      # Blokeli kac gun
            'pos_modu': tk.StringVar(value=ayar.get("pos_modu", "blokeli")),    # blokeli veya ertesi_gun

            # E) Eczane Profili
            'sgk_elden_orani': tk.StringVar(value=ayar.get("sgk_elden_orani", "70/30")),      # SGK/Elden satis orani
            'raporlu_raporsuz_orani': tk.StringVar(value=ayar.get("raporlu_raporsuz_orani", "30/70")), # Raporlu/Raporsuz orani
            'emekli_calisan_orani': tk.StringVar(value=ayar.get("emekli_calisan_orani", "40/60")),  # Emekli/Calisan orani
            'nakit_pos_orani': tk.StringVar(value=ayar.get("nakit_pos_orani", "40/60")),       # Nakit/POS orani
            'muayene_tahsilat_orani': tk.StringVar(value=ayar.get("muayene_tahsilat_orani", "10")),   # Muayene/Tahsilat yuzdesi
            'banka_baslangic': tk.StringVar(value=ayar.get("banka_baslangic", "50000")),
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

        # E) Eczane Profili (ozel panel - cok alan var)
        self._panel_e_olustur(parent, 4, vars)

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

        # Alim Adedi (Ana Mal)
        row1 = tk.Frame(content, bg=self.colors['card_bg'])
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="Alim Adet:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=vars['alim_adet'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # MF Bedava
        row1b = tk.Frame(content, bg=self.colors['card_bg'])
        row1b.pack(fill=tk.X, pady=4)
        tk.Label(row1b, text="MF Bedava:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row1b, textvariable=vars['mf_bedava'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['success'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Alim Tarihi - Takvim
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="Alim Tarihi:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        DateEntry(row2, textvariable=vars['alim_tarihi'],
                 font=('Segoe UI', 10), width=10,
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
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

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

        # Faizler (Yillik %)
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Mvdt(Y%):", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['mevduat_faizi'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=5).pack(side=tk.LEFT, padx=2)
        tk.Label(row2, text="Krd(Y%):", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['kredi_faizi'], font=('Segoe UI', 10),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=5).pack(side=tk.LEFT)

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
        tk.Label(row4, text="POS:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
        tk.Radiobutton(row4, text="Blokeli", variable=vars['pos_modu'],
                      value="blokeli", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT, padx=3)
        tk.Radiobutton(row4, text="Ertesi Gün", variable=vars['pos_modu'],
                      value="ertesi_gun", font=('Segoe UI', 9),
                      bg=self.colors['card_bg'], fg=self.colors['text'],
                      selectcolor=self.colors['entry_bg']).pack(side=tk.LEFT)

    def _panel_e_olustur(self, parent, col, vars):
        """E paneli - Eczane Profili (genisletilmis)"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=2, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        header = tk.Frame(kart, bg=self.colors['tab_colors'][4], height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="E) ECZANE PROFILI", font=('Segoe UI', 12, 'bold'),
                fg='white', bg=self.colors['tab_colors'][4]).pack(expand=True)

        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=8, pady=5)
        content.pack(fill=tk.BOTH, expand=True)

        # SGK/Elden oranı
        row1 = tk.Frame(content, bg=self.colors['card_bg'])
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="SGK/Elden:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=vars['sgk_elden_orani'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Raporlu/Raporsuz oranı
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Rplu/Rprsz:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=vars['raporlu_raporsuz_orani'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Emekli/Çalışan oranı
        row3 = tk.Frame(content, bg=self.colors['card_bg'])
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Emk/Çlşn:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=vars['emekli_calisan_orani'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Nakit/POS oranı
        row4 = tk.Frame(content, bg=self.colors['card_bg'])
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="Nakit/POS:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row4, textvariable=vars['nakit_pos_orani'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Muayene/Tahsilat oranı
        row5 = tk.Frame(content, bg=self.colors['card_bg'])
        row5.pack(fill=tk.X, pady=2)
        tk.Label(row5, text="Muayne %:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row5, textvariable=vars['muayene_tahsilat_orani'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Banka başlangıç
        row6 = tk.Frame(content, bg=self.colors['card_bg'])
        row6.pack(fill=tk.X, pady=2)
        tk.Label(row6, text="Banka TL:", font=('Segoe UI', 9),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=11, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row6, textvariable=vars['banka_baslangic'], font=('Segoe UI', 9),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

    def _data_grid_olustur(self, parent, idx):
        """Senaryo icin data grid"""
        # Stil - koyu tema (clam theme kullan - Windows native theme baslik rengini degistirmiyor)
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(f'Grid{idx}.Treeview',
                       background='#1a1a2e',
                       foreground='#ffffff',
                       fieldbackground='#1a1a2e',
                       rowheight=24,
                       font=('Segoe UI', 9))
        style.map(f'Grid{idx}.Treeview',
                 background=[('selected', '#e94560')],
                 foreground=[('selected', 'white')])

        # Baslik stili - koyu arka plan, beyaz yazi
        style.configure(f'Grid{idx}.Treeview.Heading',
                       background='#0f3460',
                       foreground='#ffffff',
                       font=('Segoe UI', 9, 'bold'),
                       relief='raised',
                       borderwidth=1)
        style.map(f'Grid{idx}.Treeview.Heading',
                 background=[('active', '#1a4a7a'), ('pressed', '#0a2540')],
                 foreground=[('active', '#ffffff')])

        # Container
        container = tk.Frame(parent, bg=self.colors['panel_bg'])
        container.pack(fill=tk.BOTH, expand=True)

        # Kolonlar
        columns = (
            'gun', 'tarih', 'stok', 'satis', 'kasa', 'banka',
            'sgk_acik', 'sgk_kesin', 'muayene_borc',
            'depo_acik', 'depo_kesin',
            'pos_bekleyen', 'emk_bekleyen', 'banka_borc',
            'faiz_gelir', 'faiz_gider', 'ozkaynak'
        )

        tree = ttk.Treeview(container, columns=columns, show='headings',
                           style=f'Grid{idx}.Treeview', height=8)

        # Kolon basliklari
        headers = {
            'gun': ('Gün', 32),
            'tarih': ('Tarih', 68),
            'stok': ('Stok', 42),
            'satis': ('Satış', 50),
            'kasa': ('Kasa', 60),
            'banka': ('Banka', 70),
            'sgk_acik': ('SGK Açk', 65),
            'sgk_kesin': ('SGK Ksn', 65),
            'muayene_borc': ('Mua Brç', 60),
            'depo_acik': ('Dpo Açk', 65),
            'depo_kesin': ('Dpo Ksn', 65),
            'pos_bekleyen': ('POS Bkl', 60),
            'emk_bekleyen': ('Emk Bkl', 60),
            'banka_borc': ('Bnk Brç', 60),
            'faiz_gelir': ('Fz Glr', 50),
            'faiz_gider': ('Fz Gdr', 50),
            'ozkaynak': ('Özkynk', 75)
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

        # Butonlar
        btn_style = {'font': ('Segoe UI', 10, 'bold'), 'relief': 'flat',
                    'cursor': 'hand2', 'width': 12}

        self.adim_btn = tk.Button(inner, text="ADIM (1 Gun)",
                                 bg='#6366f1', fg='white',
                                 command=self._adim_oynat, **btn_style)
        self.adim_btn.pack(side=tk.LEFT, padx=10)

        # Gun sayisi textbox + Gun Oynat butonu yan yana
        gun_frame = tk.Frame(inner, bg=self.colors['accent2'])
        gun_frame.pack(side=tk.LEFT, padx=5)

        self.gun_sayisi_var = tk.StringVar(value="30")
        tk.Entry(gun_frame, textvariable=self.gun_sayisi_var, font=('Segoe UI', 10, 'bold'),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=4, justify='center').pack(side=tk.LEFT, padx=(0, 2))

        tk.Label(gun_frame, text="Gün", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=(0, 5))

        self.gun_btn = tk.Button(gun_frame, text="OYNAT",
                                bg='#8b5cf6', fg='white', font=('Segoe UI', 10, 'bold'),
                                relief='flat', cursor='hand2', width=8,
                                command=self._x_gun_oynat)
        self.gun_btn.pack(side=tk.LEFT)

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

        # Karsilastirma butonu
        self.karsilastir_btn = tk.Button(inner, text="KARSILASTIR",
                                        bg='#9b59b6', fg='white',
                                        command=self._karsilastirma_ac, **btn_style)
        self.karsilastir_btn.pack(side=tk.LEFT, padx=5)

        # Mevcut gun
        tk.Label(inner, text="Mevcut Gun:", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=(20, 5))

        self.mevcut_gun_label = tk.Label(inner, text="0", font=('Segoe UI', 11, 'bold'),
                                        fg=self.colors['accent'], bg=self.colors['accent2'])
        self.mevcut_gun_label.pack(side=tk.LEFT)

        # Ozet labels icin bos dict (popup acildiginda doldurulacak)
        self.ozet_labels = {}
        self.en_karli_label = None

        # === FATURA/SENET TAKIP BOLUMU ===
        self._fatura_senet_paneli_olustur(parent)

    def _fatura_senet_paneli_olustur(self, parent):
        """Fatura ve Senet takip paneli - ikili gorunum (sol: senet, sag: fatura)"""
        fs_frame = tk.Frame(parent, bg=self.colors['panel_bg'], pady=5)
        fs_frame.pack(fill=tk.X, pady=(2, 0))

        # ========== SOL: SENET BOLUMU ==========
        senet_frame = tk.Frame(fs_frame, bg=self.colors['card_bg'], bd=1, relief='solid')
        senet_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5))

        # Senet baslik
        senet_header = tk.Frame(senet_frame, bg='#9b59b6', height=25)
        senet_header.pack(fill=tk.X)
        senet_header.pack_propagate(False)
        tk.Label(senet_header, text="SENETLER (Depo)", font=('Segoe UI', 9, 'bold'),
                fg='white', bg='#9b59b6').pack(side=tk.LEFT, padx=10)
        tk.Button(senet_header, text="+", font=('Segoe UI', 8, 'bold'),
                 bg='#00d26a', fg='white', relief='flat', cursor='hand2', width=3,
                 command=lambda: self._fatura_senet_ekle_popup('Senet')).pack(side=tk.RIGHT, padx=2)
        tk.Button(senet_header, text="-", font=('Segoe UI', 8, 'bold'),
                 bg='#ff6b6b', fg='white', relief='flat', cursor='hand2', width=3,
                 command=lambda: self._fatura_senet_sil('Senet')).pack(side=tk.RIGHT, padx=2)

        # Senet listesi (3 satir)
        self.senet_labels = []
        for i in range(3):
            row = tk.Frame(senet_frame, bg=self.colors['card_bg'])
            row.pack(fill=tk.X, padx=5, pady=1)
            lbl = tk.Label(row, text=f"Senet {i+1}: -", font=('Segoe UI', 9),
                          fg=self.colors['text_dim'], bg=self.colors['card_bg'], anchor='w')
            lbl.pack(fill=tk.X)
            self.senet_labels.append(lbl)

        # Senet toplam
        senet_toplam_frame = tk.Frame(senet_frame, bg=self.colors['accent2'])
        senet_toplam_frame.pack(fill=tk.X, pady=(2, 0))
        self.senet_toplam_label = tk.Label(senet_toplam_frame, text="TOPLAM: 0,00 ₺",
                                          font=('Segoe UI', 9, 'bold'),
                                          fg='white', bg=self.colors['accent2'])
        self.senet_toplam_label.pack(pady=2)

        # ========== SAG: FATURA BOLUMU ==========
        fatura_frame = tk.Frame(fs_frame, bg=self.colors['card_bg'], bd=1, relief='solid')
        fatura_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10))

        # Fatura baslik
        fatura_header = tk.Frame(fatura_frame, bg='#17a2b8', height=25)
        fatura_header.pack(fill=tk.X)
        fatura_header.pack_propagate(False)
        tk.Label(fatura_header, text="FATURALAR (SGK)", font=('Segoe UI', 9, 'bold'),
                fg='white', bg='#17a2b8').pack(side=tk.LEFT, padx=10)
        tk.Button(fatura_header, text="+", font=('Segoe UI', 8, 'bold'),
                 bg='#00d26a', fg='white', relief='flat', cursor='hand2', width=3,
                 command=lambda: self._fatura_senet_ekle_popup('Fatura')).pack(side=tk.RIGHT, padx=2)
        tk.Button(fatura_header, text="-", font=('Segoe UI', 8, 'bold'),
                 bg='#ff6b6b', fg='white', relief='flat', cursor='hand2', width=3,
                 command=lambda: self._fatura_senet_sil('Fatura')).pack(side=tk.RIGHT, padx=2)

        # Fatura listesi (3 satir)
        self.fatura_labels = []
        for i in range(3):
            row = tk.Frame(fatura_frame, bg=self.colors['card_bg'])
            row.pack(fill=tk.X, padx=5, pady=1)
            lbl = tk.Label(row, text=f"Fatura {i+1}: -", font=('Segoe UI', 9),
                          fg=self.colors['text_dim'], bg=self.colors['card_bg'], anchor='w')
            lbl.pack(fill=tk.X)
            self.fatura_labels.append(lbl)

        # Fatura toplam
        fatura_toplam_frame = tk.Frame(fatura_frame, bg=self.colors['accent2'])
        fatura_toplam_frame.pack(fill=tk.X, pady=(2, 0))
        self.fatura_toplam_label = tk.Label(fatura_toplam_frame, text="TOPLAM: 0,00 ₺",
                                           font=('Segoe UI', 9, 'bold'),
                                           fg='white', bg=self.colors['accent2'])
        self.fatura_toplam_label.pack(pady=2)

        # Paneli guncelle
        self._fatura_senet_tabloyu_guncelle()

    def _fatura_senet_tabloyu_guncelle(self):
        """Fatura/Senet panelini guncelle - ikili gorunum"""
        bugun = datetime.now().date()

        # Senet ve Faturalari ayir
        senetler = [k for k in self.fatura_senet_kayitlari if k.get('tur') == 'Senet']
        faturalar = [k for k in self.fatura_senet_kayitlari if k.get('tur') == 'Fatura']

        # Senetleri guncelle
        senet_toplam = 0
        for i, lbl in enumerate(self.senet_labels):
            if i < len(senetler):
                kayit = senetler[i]
                tutar = kayit.get('tutar', 0)
                vade = kayit.get('vade', '')
                senet_toplam += tutar

                # Vade durumuna gore renk
                try:
                    vade_tarih = datetime.strptime(vade, '%d.%m.%Y').date()
                    gun_fark = (vade_tarih - bugun).days
                    if gun_fark < 0:
                        renk = '#ff6b6b'  # Gecikmi - kirmizi
                    elif gun_fark <= 7:
                        renk = '#ffc107'  # Yakin - sari
                    else:
                        renk = self.colors['text']
                except:
                    renk = self.colors['text']

                lbl.config(text=f"{i+1}. {tutar:,.2f} ₺  |  {vade}", fg=renk)
            else:
                lbl.config(text=f"{i+1}. -", fg=self.colors['text_dim'])

        self.senet_toplam_label.config(text=f"TOPLAM: {senet_toplam:,.2f} ₺")

        # Faturalari guncelle
        fatura_toplam = 0
        for i, lbl in enumerate(self.fatura_labels):
            if i < len(faturalar):
                kayit = faturalar[i]
                tutar = kayit.get('tutar', 0)
                vade = kayit.get('vade', '')
                fatura_toplam += tutar

                # Vade durumuna gore renk
                try:
                    vade_tarih = datetime.strptime(vade, '%d.%m.%Y').date()
                    gun_fark = (vade_tarih - bugun).days
                    if gun_fark < 0:
                        renk = '#ff6b6b'  # Gecikmi - kirmizi
                    elif gun_fark <= 7:
                        renk = '#ffc107'  # Yakin - sari
                    else:
                        renk = self.colors['text']
                except:
                    renk = self.colors['text']

                lbl.config(text=f"{i+1}. {tutar:,.2f} ₺  |  {vade}", fg=renk)
            else:
                lbl.config(text=f"{i+1}. -", fg=self.colors['text_dim'])

        self.fatura_toplam_label.config(text=f"TOPLAM: {fatura_toplam:,.2f} ₺")

    def _fatura_senet_ekle_popup(self, tur='Fatura'):
        """Yeni fatura/senet ekleme popup penceresi"""
        # Hesap turu otomatik belirlenir
        hesap = 'SGK' if tur == 'Fatura' else 'Depo'

        popup = tk.Toplevel(self.root)
        popup.title(f"{tur} Ekle ({hesap})")
        popup.geometry("320x200")
        popup.configure(bg=self.colors['panel_bg'])
        popup.transient(self.root)
        popup.grab_set()

        # Baslik
        baslik_renk = '#17a2b8' if tur == 'Fatura' else '#9b59b6'
        tk.Label(popup, text=f"YENİ {tur.upper()} ({hesap})", font=('Segoe UI', 12, 'bold'),
                fg=baslik_renk, bg=self.colors['panel_bg']).pack(pady=(15, 10))

        # Tutar
        row1 = tk.Frame(popup, bg=self.colors['panel_bg'])
        row1.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(row1, text="Tutar (₺):", font=('Segoe UI', 10),
                fg=self.colors['text'], bg=self.colors['panel_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tutar_var = tk.StringVar(value="0.00")
        tutar_entry = tk.Entry(row1, textvariable=tutar_var, font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=15, justify='right')
        tutar_entry.pack(side=tk.RIGHT)
        tutar_entry.focus_set()
        tutar_entry.select_range(0, tk.END)

        # Vade tarihi
        row2 = tk.Frame(popup, bg=self.colors['panel_bg'])
        row2.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(row2, text="Vade Tarihi:", font=('Segoe UI', 10),
                fg=self.colors['text'], bg=self.colors['panel_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        vade_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
        DateEntry(row2, textvariable=vade_var, font=('Segoe UI', 10), width=13,
                 date_pattern='dd.mm.yyyy', locale='tr_TR').pack(side=tk.RIGHT)

        # Butonlar
        btn_frame = tk.Frame(popup, bg=self.colors['panel_bg'])
        btn_frame.pack(pady=15)

        def kaydet():
            try:
                tutar = float(tutar_var.get().replace(',', '.'))
                if tutar <= 0:
                    raise ValueError
            except:
                messagebox.showerror("Hata", "Geçerli bir tutar girin!", parent=popup)
                return

            yeni_kayit = {
                'tur': tur,
                'hesap': hesap,
                'tutar': tutar,
                'vade': vade_var.get()
            }
            self.fatura_senet_kayitlari.append(yeni_kayit)
            self._fatura_senet_kaydet()
            self._fatura_senet_tabloyu_guncelle()
            popup.destroy()

        tk.Button(btn_frame, text="Kaydet", font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['success'], fg='white', relief='flat',
                 cursor='hand2', width=10, command=kaydet).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="İptal", font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['danger'], fg='white', relief='flat',
                 cursor='hand2', width=10, command=popup.destroy).pack(side=tk.LEFT, padx=10)

        # Pencereyi ortala
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

    def _fatura_senet_sil(self, tur='Fatura'):
        """Belirtilen turdeki kayitlardan birini sil"""
        # Ilgili kayitlari filtrele
        kayitlar = [(i, k) for i, k in enumerate(self.fatura_senet_kayitlari) if k.get('tur') == tur]

        if not kayitlar:
            messagebox.showinfo("Bilgi", f"Silinecek {tur.lower()} kaydı bulunamadı!")
            return

        if len(kayitlar) == 1:
            # Tek kayit varsa direkt sil
            if messagebox.askyesno("Onay", f"{tur} kaydını silmek istediğinize emin misiniz?\n\n"
                                  f"Tutar: {kayitlar[0][1]['tutar']:,.2f} ₺\n"
                                  f"Vade: {kayitlar[0][1]['vade']}"):
                del self.fatura_senet_kayitlari[kayitlar[0][0]]
                self._fatura_senet_kaydet()
                self._fatura_senet_tabloyu_guncelle()
        else:
            # Birden fazla kayit varsa secim penceresi ac
            self._silme_secim_penceresi(tur, kayitlar)

    def _silme_secim_penceresi(self, tur, kayitlar):
        """Birden fazla kayit varsa silmek icin secim penceresi"""
        popup = tk.Toplevel(self.root)
        popup.title(f"{tur} Sil")
        popup.geometry("350x200")
        popup.configure(bg=self.colors['panel_bg'])
        popup.transient(self.root)
        popup.grab_set()

        baslik_renk = '#17a2b8' if tur == 'Fatura' else '#9b59b6'
        tk.Label(popup, text=f"SİLİNECEK {tur.upper()} SEÇİN", font=('Segoe UI', 11, 'bold'),
                fg=baslik_renk, bg=self.colors['panel_bg']).pack(pady=10)

        # Listbox
        listbox_frame = tk.Frame(popup, bg=self.colors['panel_bg'])
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        listbox = tk.Listbox(listbox_frame, font=('Segoe UI', 10),
                            bg=self.colors['card_bg'], fg=self.colors['text'],
                            selectbackground=baslik_renk, selectforeground='white',
                            height=4)
        listbox.pack(fill=tk.BOTH, expand=True)

        for idx, kayit in kayitlar:
            listbox.insert(tk.END, f"{kayit['tutar']:,.2f} ₺  |  Vade: {kayit['vade']}")

        # Butonlar
        btn_frame = tk.Frame(popup, bg=self.colors['panel_bg'])
        btn_frame.pack(pady=10)

        def sil_secili():
            secim = listbox.curselection()
            if not secim:
                messagebox.showwarning("Uyarı", "Lütfen silmek için bir kayıt seçin!", parent=popup)
                return

            gercek_idx = kayitlar[secim[0]][0]
            del self.fatura_senet_kayitlari[gercek_idx]
            self._fatura_senet_kaydet()
            self._fatura_senet_tabloyu_guncelle()
            popup.destroy()

        tk.Button(btn_frame, text="Sil", font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['danger'], fg='white', relief='flat',
                 cursor='hand2', width=8, command=sil_secili).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="İptal", font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['accent2'], fg='white', relief='flat',
                 cursor='hand2', width=8, command=popup.destroy).pack(side=tk.LEFT, padx=10)

        # Pencereyi ortala
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

    def _fatura_senet_yukle(self):
        """Fatura/Senet kayitlarini JSON dosyasından yukle"""
        try:
            if os.path.exists(self.FATURA_SENET_DOSYA):
                with open(self.FATURA_SENET_DOSYA, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Fatura/Senet kayitlari yuklenirken hata: {e}")
        return []

    def _fatura_senet_kaydet(self):
        """Fatura/Senet kayitlarini JSON dosyasina kaydet"""
        try:
            with open(self.FATURA_SENET_DOSYA, 'w', encoding='utf-8') as f:
                json.dump(self.fatura_senet_kayitlari, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Fatura/Senet kayitlari kaydedilirken hata: {e}")

    def _vade_uyari_kontrol(self):
        """Vadesi gelen veya gecen kayitlar icin uyari goster"""
        if not self.fatura_senet_kayitlari:
            return

        bugun = datetime.now().date()
        uyari_listesi = []

        for kayit in self.fatura_senet_kayitlari:
            try:
                vade_tarih = datetime.strptime(kayit.get('vade', ''), '%d.%m.%Y').date()
                gun_fark = (vade_tarih - bugun).days

                if gun_fark < 0:
                    uyari_listesi.append(f"⚠️ GECİKMİŞ: {kayit['tur']} ({kayit['hesap']}) - {kayit['tutar']:,.2f} ₺ - Vade: {kayit['vade']}")
                elif gun_fark <= 7:
                    uyari_listesi.append(f"⏰ YAKIN: {kayit['tur']} ({kayit['hesap']}) - {kayit['tutar']:,.2f} ₺ - Vade: {kayit['vade']} ({gun_fark} gün)")
            except:
                pass

        if uyari_listesi:
            mesaj = "FATURA / SENET VADE UYARISI\n\n" + "\n".join(uyari_listesi)
            messagebox.showwarning("Vade Uyarısı", mesaj)

    def _karsilastirma_ac(self):
        """Karsilastirma tablosunu popup pencerede ac"""
        # Eger zaten aciksa one getir
        if self.karsilastirma_pencere and self.karsilastirma_pencere.winfo_exists():
            self.karsilastirma_pencere.lift()
            self.karsilastirma_pencere.focus_force()
            self._ozet_guncelle()  # Verileri guncelle
            return

        # Yeni pencere olustur
        self.karsilastirma_pencere = tk.Toplevel(self.root)
        self.karsilastirma_pencere.title("Senaryo Karsilastirma")
        self.karsilastirma_pencere.geometry("1400x500")
        self.karsilastirma_pencere.configure(bg=self.colors['panel_bg'])

        # Baslik
        baslik = tk.Label(self.karsilastirma_pencere,
                         text="SENARYO KARSILASTIRMA TABLOSU",
                         font=('Segoe UI', 16, 'bold'),
                         fg=self.colors['accent'], bg=self.colors['panel_bg'])
        baslik.pack(pady=15)

        # Tablo container
        tablo_frame = tk.Frame(self.karsilastirma_pencere, bg=self.colors['panel_bg'])
        tablo_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Basliklar
        basliklar = ['', 'Kasa', 'Mal', 'Banka', 'SGK Açk', 'SGK Ksn', 'Mua Brç',
                    'Dpo Açk', 'Dpo Ksn', 'POS Bkl', 'Emk Bkl', 'Bnk Brç',
                    'Fz Glr', 'Fz Gdr', 'ÖZKYNK']

        for col, baslik_text in enumerate(basliklar):
            lbl = tk.Label(tablo_frame, text=baslik_text, font=('Segoe UI', 9, 'bold'),
                          fg=self.colors['text'], bg=self.colors['accent2'],
                          width=8, height=2, relief='solid', bd=1)
            lbl.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # Senaryo satirlari (5 adet)
        self.ozet_labels = {}
        for i in range(self.MAX_SENARYO):
            renk = self.colors['tab_colors'][i]

            # Senaryo adi
            lbl = tk.Label(tablo_frame, text=f"S{i+1}", font=('Segoe UI', 9, 'bold'),
                          fg='white', bg=renk, width=8, height=2, relief='solid', bd=1)
            lbl.grid(row=i+1, column=0, sticky='nsew', padx=1, pady=1)

            self.ozet_labels[i] = {}
            for col, _ in enumerate(basliklar[1:], 1):
                lbl = tk.Label(tablo_frame, text="-", font=('Segoe UI', 9),
                              fg=self.colors['text'], bg=self.colors['card_bg'],
                              width=8, height=2, relief='solid', bd=1)
                lbl.grid(row=i+1, column=col, sticky='nsew', padx=1, pady=1)
                self.ozet_labels[i][col-1] = lbl

        # En karli senaryo
        self.en_karli_label = tk.Label(self.karsilastirma_pencere, text="",
                                       font=('Segoe UI', 14, 'bold'),
                                       fg=self.colors['success'], bg=self.colors['panel_bg'])
        self.en_karli_label.pack(pady=15)

        # Kapat butonu
        kapat_btn = tk.Button(self.karsilastirma_pencere, text="KAPAT",
                             font=('Segoe UI', 11, 'bold'),
                             bg=self.colors['danger'], fg='white',
                             relief='flat', cursor='hand2', width=15,
                             command=self.karsilastirma_pencere.destroy)
        kapat_btn.pack(pady=10)

        # Verileri guncelle
        self._ozet_guncelle()

    # ==================== SIMULASYON FONKSIYONLARI ====================

    def _float_parse(self, value_str):
        """String'i float'a çevir (virgül/nokta uyumlu)"""
        if not value_str or value_str.strip() == '':
            return 0.0
        return float(value_str.replace(',', '.').strip())

    def _int_parse(self, value_str):
        """String'i int'e çevir"""
        if not value_str or value_str.strip() == '':
            return 0
        return int(float(value_str.replace(',', '.').strip()))

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

    def _senaryo_baslat(self, idx):
        """Tek bir senaryoyu baslat"""
        if idx not in self.senaryo_vars:
            return False

        vars = self.senaryo_vars[idx]
        senaryo = self.senaryolar[idx]
        senaryo.sifirla()

        try:
            # Parametreleri al (virgül/nokta uyumlu)
            stok = self._float_parse(vars['stok'].get())
            aylik_sarf = self._float_parse(vars['aylik_sarf'].get())
            gunluk_sarf = aylik_sarf / 30

            depocu_fiyat = self._float_parse(vars['depocu_fiyat'].get())
            kamu_fiyat = self._float_parse(vars['kamu_fiyat'].get())
            piyasa_fiyat = self._float_parse(vars['piyasa_fiyat'].get())
            ilac_farki = self._float_parse(vars['ilac_farki'].get())

            alim_adet = self._int_parse(vars['alim_adet'].get())
            mf_bedava = self._int_parse(vars['mf_bedava'].get())
            toplam_alim = alim_adet + mf_bedava
            vade = self._int_parse(vars['vade_gun'].get())

            # Yillik faizi gunluk faize cevir
            mevduat_faizi_yillik = self._float_parse(vars['mevduat_faizi'].get()) / 100
            kredi_faizi_yillik = self._float_parse(vars['kredi_faizi'].get()) / 100
            mevduat_faizi = mevduat_faizi_yillik / 365  # Gunluk faiz
            kredi_faizi = kredi_faizi_yillik / 365      # Gunluk faiz
            pos_komisyon = self._float_parse(vars['pos_komisyon'].get()) / 100
            blokeli_gun = self._int_parse(vars['blokeli_gun'].get())
            pos_modu = vars['pos_modu'].get()

            nakit_oran, pos_oran = self._oran_parse(vars['nakit_pos_orani'].get())
            sgk_oran, elden_oran = self._oran_parse(vars['sgk_elden_orani'].get())
            raporlu_oran, raporsuz_oran = self._oran_parse(vars['raporlu_raporsuz_orani'].get())
            emekli_oran, calisan_oran = self._oran_parse(vars['emekli_calisan_orani'].get())

            # Muayene oranı (tahsilatın içindeki muayene yüzdesi)
            muayene_oran = self._float_parse(vars['muayene_tahsilat_orani'].get()) / 100
            if muayene_oran == 0:
                muayene_oran = 0.10

            banka_baslangic = self._float_parse(vars['banka_baslangic'].get())

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

            # Alım kontrolü _bir_gun_hesapla'da yapılacak
            # Böylece kullanıcı simulasyon sırasında da alım ekleyebilir

            # Durum kaydet
            senaryo.durum = {
                'stok': stok,  # Başlangıç stoğu
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
                'nakit_oran': nakit_oran,
                'pos_oran': pos_oran,
                'sgk_oran': sgk_oran,
                'elden_oran': elden_oran,
                'raporlu_oran': raporlu_oran,
                'raporsuz_oran': raporsuz_oran,
                'emekli_oran': emekli_oran,
                'calisan_oran': calisan_oran,
                'muayene_oran': muayene_oran,
                'bugun': bugun,
                'zam_tarihi': zam_tarihi,
                'zam_orani': zam_orani,
                'yapilan_alimlar': set(),  # Yapılan alımları takip et
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
        """Tek senaryo icin bir gun hesapla - Yeni hesaplama mantigi"""
        senaryo = self.senaryolar[idx]
        d = senaryo.durum

        if not d:
            return False

        gun = self.mevcut_gun
        mevcut_tarih = d['bugun'] + timedelta(days=gun)

        # ============ ALIM KONTROLÜ (Satıştan önce!) ============
        # Her gün UI'daki güncel alım değerlerini kontrol et
        vars = self.senaryo_vars[idx]
        try:
            ui_alim_adet = self._int_parse(vars['alim_adet'].get())
            ui_mf_bedava = self._int_parse(vars['mf_bedava'].get())
            ui_toplam_alim = ui_alim_adet + ui_mf_bedava
            ui_alim_tarihi = datetime.strptime(vars['alim_tarihi'].get(), "%d.%m.%Y")
        except:
            ui_alim_tarihi = None
            ui_toplam_alim = 0
            ui_alim_adet = 0

        # Eğer alım tarihi geldiyse ve bu alım henüz yapılmadıysa
        if ui_alim_tarihi and mevcut_tarih >= ui_alim_tarihi:
            # Bu alım daha önce yapıldı mı kontrol et (aynı tarih + aynı miktar)
            yapildi_key = f"{ui_alim_tarihi.strftime('%Y-%m-%d')}_{ui_toplam_alim}"
            if yapildi_key not in d.get('yapilan_alimlar', set()):
                # Yeni alım yap
                d['stok'] += ui_toplam_alim

                # Depo açık hesabına sadece ana mal borcunu yaz
                depo_borc = ui_alim_adet * d['depocu_fiyat']
                ay_key = mevcut_tarih.strftime("%Y-%m")
                if ay_key not in senaryo.depo_acik_hesap:
                    senaryo.depo_acik_hesap[ay_key] = 0
                senaryo.depo_acik_hesap[ay_key] += depo_borc

                # Bu alımı kaydet (tekrar yapılmasın)
                if 'yapilan_alimlar' not in d:
                    d['yapilan_alimlar'] = set()
                d['yapilan_alimlar'].add(yapildi_key)

        # ============ GÜNÜN BAŞI: Dünkü kasa → Banka ============
        # Ertesi gün mantığı: Dün kasaya giren para bugün bankaya yatar
        if d['kasa'] > 0:
            d['banka'] += d['kasa']
            d['kasa'] = 0

        # Zam kontrolu
        if d['zam_tarihi'] and mevcut_tarih >= d['zam_tarihi']:
            d['kamu_fiyat'] *= (1 + d['zam_orani'])
            d['piyasa_fiyat'] *= (1 + d['zam_orani'])
            d['zam_tarihi'] = None

        # ============ STOK KONTROLÜ VE SATIŞ ============
        tarih_str = mevcut_tarih.strftime("%d.%m.%Y")

        # Stok sıfır veya altındaysa satış YAPMA, uyarı ver ve DUR
        if d['stok'] <= 0:
            d['stok'] = 0  # Eksiye düşmesin
            satis_miktari = 0
            # Simülasyonu durdur - kullanıcı mal almalı
            self.simulasyon_calisyor = False
            self.uyari_bekliyor = True
            messagebox.showwarning(
                f"Senaryo {idx+1} - STOK BİTTİ!",
                f"🛑 STOK BİTTİ - DEPODAN MAL AL!\n\n"
                f"Tarih: {tarih_str}\n"
                f"Gün: {gun + 1}\n\n"
                f"Simülasyon durdu!\n"
                f"Alım tarihi ve miktarı girin, sonra tekrar OYNAT'a basın."
            )
            self.uyari_bekliyor = False
            self.root.after(0, lambda: self._butonlari_ayarla(False))
        else:
            # Stok varsa satış yap
            satis_miktari = min(d['gunluk_sarf'], d['stok'])
            d['stok'] -= satis_miktari
            d['stok'] = max(0, d['stok'])  # Asla eksiye düşmesin

            # Satış sonrası kontroller
            if d['stok'] == 0:
                # Stok tam bitti - simülasyonu durdur
                self.simulasyon_calisyor = False
                self.uyari_bekliyor = True
                messagebox.showwarning(
                    f"Senaryo {idx+1} - STOK UYARI",
                    f"⚠️ STOK SIFIRA DÜŞTÜ!\n\n"
                    f"Tarih: {tarih_str}\n"
                    f"Gün: {gun + 1}\n\n"
                    f"Simülasyon durdu!\n"
                    f"DEPODAN MAL ALIN, sonra tekrar OYNAT'a basın."
                )
                self.uyari_bekliyor = False
                self.root.after(0, lambda: self._butonlari_ayarla(False))
            elif d['stok'] <= d['gunluk_sarf']:
                # Yarın bitecek uyarısı (simülasyon devam eder)
                self.uyari_bekliyor = True
                messagebox.showwarning(
                    f"Senaryo {idx+1} - STOK UYARI",
                    f"⚠️ YARIN STOK BİTECEK!\n\n"
                    f"Tarih: {tarih_str}\n"
                    f"Kalan stok: {d['stok']}\n"
                    f"Günlük sarf: {d['gunluk_sarf']}\n\n"
                    f"DEPODAN ALIM YAPIN!"
                )
                self.uyari_bekliyor = False

        # ============ ELDEN SATISLAR (PSF uzerinden) ============
        elden_ciro = satis_miktari * d['piyasa_fiyat'] * d['elden_oran']
        elden_nakit = elden_ciro * d['nakit_oran']
        elden_pos = elden_ciro * d['pos_oran']

        # ============ ILAC FARKI (SGK satislarindan, herkesten alinir) ============
        fark_tutar = satis_miktari * d['ilac_farki'] * d['sgk_oran']
        fark_nakit = fark_tutar * d['nakit_oran']
        fark_pos = fark_tutar * d['pos_oran']

        # ============ SGK SATISLARI (Kamu fiyati uzerinden) ============
        sgk_ciro = satis_miktari * d['kamu_fiyat'] * d['sgk_oran']

        # --- RAPORLU ILACLAR (katilim payi YOK, tamami SGK alacak) ---
        raporlu_ciro = sgk_ciro * d['raporlu_oran']
        # Raporlu emekli + calisan tamami SGK'ya
        sgk_raporlu_alacak = raporlu_ciro  # %100 SGK alacak

        # --- RAPORSUZ ILACLAR (katilim payi VAR) ---
        raporsuz_ciro = sgk_ciro * d['raporsuz_oran']

        # Raporsuz Emekli: %90 SGK, %10 katilim (2 ay sonra maas)
        raporsuz_emekli = raporsuz_ciro * d['emekli_oran']
        sgk_raporsuz_emekli = raporsuz_emekli * 0.90
        emekli_katilim = raporsuz_emekli * 0.10  # 2 ay sonra gelecek

        # Raporsuz Calisan: %80 SGK, %20 katilim (eczanede aninda tahsil)
        raporsuz_calisan = raporsuz_ciro * d['calisan_oran']
        sgk_raporsuz_calisan = raporsuz_calisan * 0.80
        calisan_katilim = raporsuz_calisan * 0.20  # Aninda tahsil

        # Calisan katilimi nakit/pos'a ayrilir
        calisan_nakit = calisan_katilim * d['nakit_oran']
        calisan_pos = calisan_katilim * d['pos_oran']

        # ============ MUAYENE UCRETI HESABI ============
        # Muayene sadece SGK reçetelerinde var (elden satışta YOK)
        # SGK reçetesinde eczanede tahsil edilen: çalışan katılım + ilaç farkı
        sgk_tahsilat = fark_tutar + calisan_katilim
        muayene_tutar = sgk_tahsilat * d['muayene_oran']
        # Muayene ek tahsilat olarak kasaya girer, SGK'ya borç yazılır
        muayene_nakit = muayene_tutar * d['nakit_oran']
        muayene_pos = muayene_tutar * d['pos_oran']

        # ============ KASAYA GIRISLER ============
        toplam_nakit = elden_nakit + fark_nakit + calisan_nakit + muayene_nakit
        d['kasa'] += toplam_nakit

        # ============ POS GIRISLERI ============
        toplam_pos = elden_pos + fark_pos + calisan_pos + muayene_pos

        if d['pos_modu'] == 'ertesi_gun':
            komisyon_sonrasi = toplam_pos * (1 - d['pos_komisyon'])
            d['kasa'] += komisyon_sonrasi
        else:
            # Blokeli - X gun sonra gelecek
            odeme_tarihi = mevcut_tarih + timedelta(days=d['blokeli_gun'])
            if odeme_tarihi not in senaryo.kredi_karti_bekleyen:
                senaryo.kredi_karti_bekleyen[odeme_tarihi] = 0
            senaryo.kredi_karti_bekleyen[odeme_tarihi] += toplam_pos

        # ============ SGK AÇIK HESAP (ay içi birikir) ============
        sgk_toplam_alacak = sgk_raporlu_alacak + sgk_raporsuz_emekli + sgk_raporsuz_calisan

        ay_key = mevcut_tarih.strftime("%Y-%m")
        if ay_key not in senaryo.sgk_acik_hesap:
            senaryo.sgk_acik_hesap[ay_key] = 0
        senaryo.sgk_acik_hesap[ay_key] += sgk_toplam_alacak

        # ============ MUAYENE AÇIK BORÇ (ay içi birikir) ============
        if ay_key not in senaryo.muayene_acik_borc:
            senaryo.muayene_acik_borc[ay_key] = 0
        senaryo.muayene_acik_borc[ay_key] += muayene_tutar

        # ============ EMEKLI KATILIM (2 ay sonra, ay sonu) ============
        # Ornegin Ocak satisi -> 31 Mart
        emekli_odeme = (mevcut_tarih.replace(day=1) + relativedelta(months=3)) - timedelta(days=1)
        if emekli_odeme not in senaryo.emekli_katilim_bekleyen:
            senaryo.emekli_katilim_bekleyen[emekli_odeme] = 0
        senaryo.emekli_katilim_bekleyen[emekli_odeme] += emekli_katilim

        # ============ AYIN 1'İ İŞLEMLERİ (Fatura & Senet Kesimi) ============
        if mevcut_tarih.day == 1:
            # Önceki ayın key'i
            onceki_ay = mevcut_tarih - timedelta(days=1)
            onceki_ay_key = onceki_ay.strftime("%Y-%m")

            sgk_fatura_tutar = 0
            muayene_borc_tutar = 0
            depo_senet_tutar = 0

            # --- SGK Fatura Kesimi (önceki ay açık hesap -> kesinleşmiş alacak) ---
            if onceki_ay_key in senaryo.sgk_acik_hesap:
                sgk_fatura_tutar = senaryo.sgk_acik_hesap.pop(onceki_ay_key)
                # 90 gün sonra tahsil edilecek (15'inde)
                tahsil_tarihi = mevcut_tarih + timedelta(days=90)
                # Ayın 15'ine yuvarla
                tahsil_tarihi = tahsil_tarihi.replace(day=15)
                if tahsil_tarihi not in senaryo.sgk_alacak:
                    senaryo.sgk_alacak[tahsil_tarihi] = 0
                senaryo.sgk_alacak[tahsil_tarihi] += sgk_fatura_tutar

            # --- Muayene Borcu Kesimi (önceki ay açık -> kesinleşmiş borç) ---
            if onceki_ay_key in senaryo.muayene_acik_borc:
                muayene_borc_tutar = senaryo.muayene_acik_borc.pop(onceki_ay_key)
                # SGK alacağından mahsup edilecek (aynı tarihte)
                tahsil_tarihi = mevcut_tarih + timedelta(days=90)
                tahsil_tarihi = tahsil_tarihi.replace(day=15)
                if tahsil_tarihi not in senaryo.muayene_borc:
                    senaryo.muayene_borc[tahsil_tarihi] = 0
                senaryo.muayene_borc[tahsil_tarihi] += muayene_borc_tutar

            # --- Depo Senet Kesimi (önceki ay açık hesap -> kesinleşmiş borç) ---
            if onceki_ay_key in senaryo.depo_acik_hesap:
                depo_senet_tutar = senaryo.depo_acik_hesap.pop(onceki_ay_key)
                # Vade: ayın 15'i + 90 gün
                odeme_tarihi = mevcut_tarih + timedelta(days=d['vade'])
                odeme_tarihi = odeme_tarihi.replace(day=15)
                if odeme_tarihi not in senaryo.depo_borc:
                    senaryo.depo_borc[odeme_tarihi] = 0
                senaryo.depo_borc[odeme_tarihi] += depo_senet_tutar

            # --- POPUP PENCERELER ---
            if sgk_fatura_tutar > 0 or depo_senet_tutar > 0:
                self._ay_basi_popup_goster(mevcut_tarih, onceki_ay,
                                          sgk_fatura_tutar, muayene_borc_tutar, depo_senet_tutar,
                                          d['vade'])

        # Kredi karti tahsilatlari
        for tarih in list(senaryo.kredi_karti_bekleyen.keys()):
            if tarih <= mevcut_tarih:
                d['banka'] += senaryo.kredi_karti_bekleyen.pop(tarih)

        # Emekli katilim tahsilatlari
        for tarih in list(senaryo.emekli_katilim_bekleyen.keys()):
            if tarih <= mevcut_tarih:
                d['banka'] += senaryo.emekli_katilim_bekleyen.pop(tarih)

        # SGK tahsilatlari (muayene borcu mahsup edilir)
        for tarih in list(senaryo.sgk_alacak.keys()):
            if tarih <= mevcut_tarih:
                sgk_tahsilat = senaryo.sgk_alacak.pop(tarih)
                # Aynı tarihteki muayene borcunu düş (mahsuplaşma)
                muayene_kesinti = senaryo.muayene_borc.pop(tarih, 0)
                net_tahsilat = sgk_tahsilat - muayene_kesinti
                d['banka'] += net_tahsilat

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
        # Açık ve Kesin hesapları ayrı hesapla
        sgk_acik_toplam = sum(senaryo.sgk_acik_hesap.values())      # Fatura kesilmemiş
        sgk_kesin_toplam = sum(senaryo.sgk_alacak.values())         # Fatura kesilmiş
        muayene_borc_toplam = sum(senaryo.muayene_acik_borc.values()) + sum(senaryo.muayene_borc.values())  # SGK'ya borç
        depo_acik_toplam = sum(senaryo.depo_acik_hesap.values())    # Senet kesilmemiş
        depo_kesin_toplam = sum(senaryo.depo_borc.values())         # Senet kesilmiş
        pos_bekleyen_toplam = sum(senaryo.kredi_karti_bekleyen.values())  # Blokeli POS
        emk_bekleyen_toplam = sum(senaryo.emekli_katilim_bekleyen.values())

        # Stok degeri
        mal_degeri = d['stok'] * d['birim_maliyet']

        # Ozkaynak (tüm alacaklar - tüm borçlar)
        # SGK net alacak = SGK alacak - Muayene borcu
        sgk_toplam = sgk_acik_toplam + sgk_kesin_toplam
        depo_toplam = depo_acik_toplam + depo_kesin_toplam
        aktifler = d['kasa'] + d['banka'] + sgk_toplam + pos_bekleyen_toplam + emk_bekleyen_toplam + mal_degeri
        pasifler = depo_toplam + muayene_borc_toplam + d['banka_borc']
        ozkaynak = aktifler - pasifler

        # Data grid'e ekle
        self._satir_ekle(idx, gun + 1, mevcut_tarih, d['stok'], satis_miktari,
                        d['kasa'], d['banka'],
                        sgk_acik_toplam, sgk_kesin_toplam, muayene_borc_toplam,
                        depo_acik_toplam, depo_kesin_toplam,
                        pos_bekleyen_toplam, emk_bekleyen_toplam, d['banka_borc'],
                        d['toplam_faiz_gelir'], d['toplam_faiz_gider'], ozkaynak)

        # Ozet guncelle
        senaryo.ozet = {
            'kasa': d['kasa'],
            'mal': mal_degeri,
            'banka': d['banka'],
            'sgk_acik': sgk_acik_toplam,
            'sgk_kesin': sgk_kesin_toplam,
            'muayene_borc': muayene_borc_toplam,
            'depo_acik': depo_acik_toplam,
            'depo_kesin': depo_kesin_toplam,
            'pos_bekleyen': pos_bekleyen_toplam,
            'emk_bekleyen': emk_bekleyen_toplam,
            'banka_borc': d['banka_borc'],
            'faiz_gelir': d['toplam_faiz_gelir'],
            'faiz_gider': d['toplam_faiz_gider'],
            'ozkaynak': ozkaynak,
        }

        # Her zaman devam et - kullanıcı alım ekleyebilir
        return True

    def _satir_ekle(self, idx, gun, tarih, stok, satis, kasa, banka,
                   sgk_acik, sgk_kesin, muayene_borc,
                   depo_acik, depo_kesin,
                   pos_bekleyen, emk_bekleyen, banka_borc,
                   faiz_gelir, faiz_gider, ozkaynak):
        """Data grid'e satir ekle"""
        if idx in self.senaryo_trees:
            tree = self.senaryo_trees[idx]
            tree.insert('', 'end', values=(
                gun,
                tarih.strftime("%d.%m.%Y"),
                f"{stok:.2f}",
                f"{satis:.2f}",
                f"{kasa:.2f}",
                f"{banka:.2f}",
                f"{sgk_acik:.2f}",
                f"{sgk_kesin:.2f}",
                f"{muayene_borc:.2f}",
                f"{depo_acik:.2f}",
                f"{depo_kesin:.2f}",
                f"{pos_bekleyen:.2f}",
                f"{emk_bekleyen:.2f}",
                f"{banka_borc:.2f}",
                f"{faiz_gelir:.2f}",
                f"{faiz_gider:.2f}",
                f"{ozkaynak:.2f}"
            ))
            # Son satira scroll
            children = tree.get_children()
            if children:
                tree.see(children[-1])

    def _ozet_guncelle(self):
        """Karsilastirma ozetini guncelle"""
        # Popup pencere acik degilse guncelleme yapma
        if not self.karsilastirma_pencere or not self.karsilastirma_pencere.winfo_exists():
            return
        if not self.ozet_labels:
            return

        en_yuksek_ozkaynak = None
        en_karli_idx = -1

        for idx in range(self.aktif_senaryo_sayisi):
            if idx in self.senaryolar and self.senaryolar[idx].ozet:
                ozet = self.senaryolar[idx].ozet

                degerler = [
                    ozet.get('kasa', 0),
                    ozet.get('mal', 0),
                    ozet.get('banka', 0),
                    ozet.get('sgk_acik', 0),
                    ozet.get('sgk_kesin', 0),
                    ozet.get('muayene_borc', 0),
                    ozet.get('depo_acik', 0),
                    ozet.get('depo_kesin', 0),
                    ozet.get('pos_bekleyen', 0),
                    ozet.get('emk_bekleyen', 0),
                    ozet.get('banka_borc', 0),
                    ozet.get('faiz_gelir', 0),
                    ozet.get('faiz_gider', 0),
                    ozet.get('ozkaynak', 0),
                ]

                if idx in self.ozet_labels:
                    for col, deger in enumerate(degerler):
                        if col in self.ozet_labels[idx]:
                            self.ozet_labels[idx][col].config(text=f"{deger:,.2f}")

                ozkaynak = ozet.get('ozkaynak', 0)
                if en_yuksek_ozkaynak is None or ozkaynak > en_yuksek_ozkaynak:
                    en_yuksek_ozkaynak = ozkaynak
                    en_karli_idx = idx

        # En karli senaryo
        if en_karli_idx >= 0 and self.en_karli_label:
            self.en_karli_label.config(
                text=f"EN KARLI: Senaryo {en_karli_idx + 1} (Ozkaynak: {en_yuksek_ozkaynak:,.2f} TL)"
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

            # Uyarı gösteriliyorsa bekle
            while self.uyari_bekliyor and self.simulasyon_calisyor:
                time.sleep(0.1)

            if not self.simulasyon_calisyor:
                break

            # Herhangi bir senaryoda stok bittiyse dur
            stok_bitti = False
            for idx in range(self.aktif_senaryo_sayisi):
                if self.senaryolar[idx].durum and self.senaryolar[idx].durum.get('stok', 0) <= 0:
                    stok_bitti = True
                    break

            if stok_bitti:
                self.simulasyon_calisyor = False
                break

            self.mevcut_gun += 1
            self.root.after(0, lambda g=self.mevcut_gun: self.mevcut_gun_label.config(text=str(g)))

            for idx in range(self.aktif_senaryo_sayisi):
                if self.senaryolar[idx].durum:
                    self.root.after(0, lambda i=idx: self._bir_gun_hesapla(i))

            self.root.after(0, self._ozet_guncelle)

            # Hesaplama tamamlanana kadar bekle
            time.sleep(0.15)

            # Uyarı gösteriliyorsa bekle
            while self.uyari_bekliyor and self.simulasyon_calisyor:
                time.sleep(0.1)

            # Hesaplama sonrası stok kontrolü
            if not self.simulasyon_calisyor:
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
            for col in range(14):
                if idx in self.ozet_labels and col in self.ozet_labels[idx]:
                    self.ozet_labels[idx][col].config(text="-")

        if self.en_karli_label:
            self.en_karli_label.config(text="")

    def _ay_basi_popup_goster(self, mevcut_tarih, onceki_ay, sgk_fatura, muayene_borc, depo_senet, vade):
        """Ayın 1'inde SGK fatura ve Depo senet bilgilerini popup pencerede göster"""
        # Ana popup pencere
        popup = tk.Toplevel(self.root)
        popup.title(f"AY BAŞI BİLDİRİMİ - {mevcut_tarih.strftime('%d.%m.%Y')}")
        popup.geometry("600x450")
        popup.configure(bg=self.colors['panel_bg'])
        popup.transient(self.root)
        popup.grab_set()

        # Başlık
        ay_adi = onceki_ay.strftime("%B %Y").upper()
        baslik = tk.Label(popup,
                         text=f"📋 {ay_adi} AY SONU KAPANIŞI",
                         font=('Segoe UI', 16, 'bold'),
                         fg=self.colors['accent'], bg=self.colors['panel_bg'])
        baslik.pack(pady=20)

        # Container
        container = tk.Frame(popup, bg=self.colors['panel_bg'])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # ==================== SGK FATURA BÖLÜMÜ ====================
        if sgk_fatura > 0:
            sgk_frame = tk.Frame(container, bg=self.colors['card_bg'], bd=2, relief='solid')
            sgk_frame.pack(fill=tk.X, pady=10)

            sgk_header = tk.Frame(sgk_frame, bg='#0f3460', height=35)
            sgk_header.pack(fill=tk.X)
            sgk_header.pack_propagate(False)
            tk.Label(sgk_header, text="📄 SGK FATURASI KESİLDİ",
                    font=('Segoe UI', 12, 'bold'),
                    fg='white', bg='#0f3460').pack(expand=True)

            sgk_content = tk.Frame(sgk_frame, bg=self.colors['card_bg'], padx=15, pady=15)
            sgk_content.pack(fill=tk.X)

            # Fatura tutarı
            row1 = tk.Frame(sgk_content, bg=self.colors['card_bg'])
            row1.pack(fill=tk.X, pady=5)
            tk.Label(row1, text="Fatura Tutarı:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row1, text=f"{sgk_fatura:,.2f} TL", font=('Segoe UI', 12, 'bold'),
                    fg=self.colors['success'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

            # Muayene mahsup
            if muayene_borc > 0:
                row2 = tk.Frame(sgk_content, bg=self.colors['card_bg'])
                row2.pack(fill=tk.X, pady=5)
                tk.Label(row2, text="Muayene Borcu (-):", font=('Segoe UI', 11),
                        fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
                tk.Label(row2, text=f"{muayene_borc:,.2f} TL", font=('Segoe UI', 12, 'bold'),
                        fg=self.colors['danger'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

                # Net alacak
                net_alacak = sgk_fatura - muayene_borc
                row3 = tk.Frame(sgk_content, bg=self.colors['card_bg'])
                row3.pack(fill=tk.X, pady=5)
                tk.Label(row3, text="Net Alacak:", font=('Segoe UI', 11, 'bold'),
                        fg=self.colors['text'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
                tk.Label(row3, text=f"{net_alacak:,.2f} TL", font=('Segoe UI', 12, 'bold'),
                        fg=self.colors['info'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

            # Tahsil tarihi
            tahsil_tarihi = mevcut_tarih + timedelta(days=90)
            tahsil_tarihi = tahsil_tarihi.replace(day=15)
            row4 = tk.Frame(sgk_content, bg=self.colors['card_bg'])
            row4.pack(fill=tk.X, pady=5)
            tk.Label(row4, text="Tahsil Tarihi:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row4, text=f"📅 {tahsil_tarihi.strftime('%d.%m.%Y')} (~90 gün)",
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['warning'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

        # ==================== DEPO SENET BÖLÜMÜ ====================
        if depo_senet > 0:
            depo_frame = tk.Frame(container, bg=self.colors['card_bg'], bd=2, relief='solid')
            depo_frame.pack(fill=tk.X, pady=10)

            depo_header = tk.Frame(depo_frame, bg='#8b4513', height=35)
            depo_header.pack(fill=tk.X)
            depo_header.pack_propagate(False)
            tk.Label(depo_header, text="📝 DEPO SENEDİ KESİLDİ",
                    font=('Segoe UI', 12, 'bold'),
                    fg='white', bg='#8b4513').pack(expand=True)

            depo_content = tk.Frame(depo_frame, bg=self.colors['card_bg'], padx=15, pady=15)
            depo_content.pack(fill=tk.X)

            # Senet tutarı
            row1 = tk.Frame(depo_content, bg=self.colors['card_bg'])
            row1.pack(fill=tk.X, pady=5)
            tk.Label(row1, text="Senet Tutarı:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row1, text=f"{depo_senet:,.2f} TL", font=('Segoe UI', 12, 'bold'),
                    fg=self.colors['danger'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

            # Ödeme tarihi
            odeme_tarihi = mevcut_tarih + timedelta(days=vade)
            odeme_tarihi = odeme_tarihi.replace(day=15)
            row2 = tk.Frame(depo_content, bg=self.colors['card_bg'])
            row2.pack(fill=tk.X, pady=5)
            tk.Label(row2, text="Ödeme Tarihi:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row2, text=f"📅 {odeme_tarihi.strftime('%d.%m.%Y')} ({vade} gün vade)",
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['warning'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

        # Bilgi notu
        bilgi_frame = tk.Frame(container, bg=self.colors['accent2'], padx=10, pady=10)
        bilgi_frame.pack(fill=tk.X, pady=15)
        tk.Label(bilgi_frame,
                text="ℹ️ Açık hesaplar kesinleşmiş hesaplara dönüştürüldü.\n" +
                     "SGK alacağından muayene borcu mahsup edilecektir.",
                font=('Segoe UI', 10),
                fg=self.colors['text'], bg=self.colors['accent2'],
                justify='center').pack()

        # Tamam butonu
        tamam_btn = tk.Button(popup, text="TAMAM",
                             font=('Segoe UI', 11, 'bold'),
                             bg=self.colors['success'], fg='white',
                             relief='flat', cursor='hand2', width=20,
                             command=popup.destroy)
        tamam_btn.pack(pady=15)

        # Pencereyi ortala
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f'{width}x{height}+{x}+{y}')

    # ==================== AYARLAR FONKSIYONLARI ====================

    def _ayarlari_yukle(self):
        """Ayarlar dosyasindan degerleri yukle"""
        try:
            if os.path.exists(self.AYARLAR_DOSYA):
                with open(self.AYARLAR_DOSYA, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("varsayilan_degerler", self.VARSAYILAN_DEGERLER.copy())
        except Exception as e:
            print(f"Ayarlar yuklenirken hata: {e}")
        return self.VARSAYILAN_DEGERLER.copy()

    def _ayarlari_kaydet(self, yeni_ayarlar):
        """Ayarlari JSON dosyasina kaydet"""
        try:
            data = {"varsayilan_degerler": yeni_ayarlar}
            with open(self.AYARLAR_DOSYA, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.kayitli_ayarlar = yeni_ayarlar.copy()
            return True
        except Exception as e:
            print(f"Ayarlar kaydedilirken hata: {e}")
            return False

    def _ayarlar_penceresi_ac(self):
        """Ayarlar penceresini ac"""
        ayar_pencere = tk.Toplevel(self.root)
        ayar_pencere.title("MF Analiz - Varsayilan Ayarlar")
        ayar_pencere.geometry("700x650")
        ayar_pencere.configure(bg=self.colors['bg'])
        ayar_pencere.resizable(False, False)

        # Modal yap
        ayar_pencere.transient(self.root)
        ayar_pencere.grab_set()

        # Baslik
        baslik_frame = tk.Frame(ayar_pencere, bg=self.colors['accent'], height=50)
        baslik_frame.pack(fill=tk.X)
        baslik_frame.pack_propagate(False)
        tk.Label(baslik_frame, text="VARSAYILAN DEGERLER AYARLARI",
                font=('Segoe UI', 14, 'bold'), fg='white',
                bg=self.colors['accent']).pack(expand=True)

        # Icerik scroll
        canvas = tk.Canvas(ayar_pencere, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(ayar_pencere, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.colors['bg'])

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Ayar degiskenleri
        ayar_vars = {}

        # Kategori sirasi ve basliklari
        kategoriler = [
            ("A) Eczane Durumu", [
                ("stok", "Stok (adet)"),
                ("aylik_sarf", "Aylik Sarf (adet)")
            ]),
            ("B) Ilac Verileri", [
                ("depocu_fiyat", "Depocu Fiyat (TL)"),
                ("kamu_fiyat", "Kamu Fiyat (TL)"),
                ("piyasa_fiyat", "Piyasa Fiyat (TL)"),
                ("ilac_farki", "Ilac Farki (TL)")
            ]),
            ("C) Satin Alma", [
                ("alim_adet", "Alim Adet"),
                ("mf_bedava", "MF Bedava"),
                ("vade_gun", "Vade (gun)")
            ]),
            ("D) Dis Etkenler", [
                ("zam_orani", "Zam Orani (%)"),
                ("mevduat_faizi", "Mevduat Faizi (Yillik %)"),
                ("kredi_faizi", "Kredi Faizi (Yillik %)"),
                ("pos_komisyon", "POS Komisyon (%)"),
                ("blokeli_gun", "Blokeli Gun"),
                ("pos_modu", "POS Modu (blokeli/ertesi_gun)")
            ]),
            ("E) Eczane Profili", [
                ("sgk_elden_orani", "SGK/Elden Orani"),
                ("raporlu_raporsuz_orani", "Raporlu/Raporsuz Orani"),
                ("emekli_calisan_orani", "Emekli/Calisan Orani"),
                ("nakit_pos_orani", "Nakit/POS Orani"),
                ("muayene_tahsilat_orani", "Muayene Tahsilat (%)"),
                ("banka_baslangic", "Banka Baslangic (TL)")
            ])
        ]

        for kategori_baslik, alanlar in kategoriler:
            # Kategori basligi
            kat_frame = tk.Frame(scroll_frame, bg=self.colors['card_bg'], bd=1, relief='solid')
            kat_frame.pack(fill=tk.X, padx=10, pady=5)

            kat_header = tk.Frame(kat_frame, bg=self.colors['accent2'])
            kat_header.pack(fill=tk.X)
            tk.Label(kat_header, text=kategori_baslik, font=('Segoe UI', 11, 'bold'),
                    fg='white', bg=self.colors['accent2'], pady=5).pack(anchor='w', padx=10)

            kat_content = tk.Frame(kat_frame, bg=self.colors['card_bg'], padx=10, pady=10)
            kat_content.pack(fill=tk.X)

            for key, label in alanlar:
                row = tk.Frame(kat_content, bg=self.colors['card_bg'])
                row.pack(fill=tk.X, pady=3)

                tk.Label(row, text=label + ":", font=('Segoe UI', 10),
                        fg=self.colors['text_dim'], bg=self.colors['card_bg'],
                        width=25, anchor='w').pack(side=tk.LEFT)

                var = tk.StringVar(value=self.kayitli_ayarlar.get(key, self.VARSAYILAN_DEGERLER.get(key, "")))
                ayar_vars[key] = var

                entry = tk.Entry(row, textvariable=var, font=('Segoe UI', 11),
                               bg=self.colors['entry_bg'], fg=self.colors['text'],
                               relief='flat', width=20, justify='center')
                entry.pack(side=tk.RIGHT)

        # Butonlar
        btn_frame = tk.Frame(ayar_pencere, bg=self.colors['bg'], pady=15)
        btn_frame.pack(fill=tk.X)

        def kaydet_ve_kapat():
            yeni_ayarlar = {key: var.get() for key, var in ayar_vars.items()}
            if self._ayarlari_kaydet(yeni_ayarlar):
                messagebox.showinfo("Basarili", "Ayarlar kaydedildi!\n\nYeni senaryolarda bu degerler kullanilacak.",
                                   parent=ayar_pencere)
                ayar_pencere.destroy()
            else:
                messagebox.showerror("Hata", "Ayarlar kaydedilemedi!", parent=ayar_pencere)

        def varsayilana_dondur():
            if messagebox.askyesno("Onay", "Tum degerler varsayilana donecek. Emin misiniz?",
                                  parent=ayar_pencere):
                for key, var in ayar_vars.items():
                    var.set(self.VARSAYILAN_DEGERLER.get(key, ""))

        kaydet_btn = tk.Button(btn_frame, text="Kaydet ve Kapat",
                              font=('Segoe UI', 11, 'bold'),
                              bg=self.colors['success'], fg='white',
                              relief='flat', cursor='hand2', width=18,
                              command=kaydet_ve_kapat)
        kaydet_btn.pack(side=tk.LEFT, padx=20)

        varsayilan_btn = tk.Button(btn_frame, text="Varsayilana Don",
                                  font=('Segoe UI', 11, 'bold'),
                                  bg=self.colors['warning'], fg='black',
                                  relief='flat', cursor='hand2', width=18,
                                  command=varsayilana_dondur)
        varsayilan_btn.pack(side=tk.LEFT, padx=10)

        iptal_btn = tk.Button(btn_frame, text="Iptal",
                             font=('Segoe UI', 11, 'bold'),
                             bg=self.colors['danger'], fg='white',
                             relief='flat', cursor='hand2', width=12,
                             command=ayar_pencere.destroy)
        iptal_btn.pack(side=tk.RIGHT, padx=20)

        # Pencereyi ortala
        ayar_pencere.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (ayar_pencere.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (ayar_pencere.winfo_height() // 2)
        ayar_pencere.geometry(f"+{x}+{y}")

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
