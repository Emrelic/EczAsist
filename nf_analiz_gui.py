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
import calendar
import math


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
        self.emekli_katilim_bekleyen = {} # {odeme_tarihi: tutar} - Emekli katilim payi (gunluk birikim)
        self.emekli_katilim_alacak = {}   # {odeme_tarihi: tutar} - SGK'ya yazilmis emekli k.p. alacagi

        # ========== KREDİ TAKİBİ ==========
        self.kredi_borclari = {}  # {cekilis_tarihi: {'tutar': x, 'kalan': y}} - Bankadan cekilen krediler

        # ========== HAREKET LOGLARI ==========
        self.hareket_loglari = []  # [{'tarih': x, 'tip': y, 'aciklama': z, 'tutar': t}]

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
        self.emekli_katilim_alacak = {}
        self.kredi_borclari = {}
        self.hareket_loglari = []
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
        self.son_simulasyon_tarihi = None  # Simülasyondaki son tarih
        self.uyari_bekliyor = False  # Uyarı gösterilirken True
        self.gunluk_bildirimler = []  # Gün içi hesap hareketleri
        self.senaryo_duraklatildi = {}  # {idx: True/False} - Her senaryo için ayrı duraklatma
        self.stok_uyari_gosterildi = {}  # {idx: True/False} - Stok uyarısı gösterildi mi
        self.mal_bitis_senaryosu = None  # Hangi senaryonun mal bitişinde durulacak (idx)
        self.mal_bitis_modu = False  # Mal bitişine kadar oynat modu aktif mi

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

        # Kopyala ve Sil butonları
        kopyala_frame = tk.Frame(tab_frame, bg=self.colors['panel_bg'])
        kopyala_frame.pack(fill=tk.X, padx=5)

        # Sil butonu (solda)
        sil_btn = tk.Button(
            kopyala_frame,
            text="Bu Senaryoyu Sil",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['danger'],
            fg='white',
            relief='flat',
            cursor='hand2',
            command=lambda i=idx: self._senaryo_sil(i)
        )
        sil_btn.pack(side=tk.LEFT, padx=10, pady=5)

        # Log penceresi butonu
        log_btn = tk.Button(
            kopyala_frame,
            text="Hareket Logları",
            font=('Segoe UI', 10, 'bold'),
            bg='#8e44ad',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=lambda i=idx: self._hareket_log_penceresi(i)
        )
        log_btn.pack(side=tk.LEFT, padx=5, pady=5)

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
            'otomatik_alim': tk.BooleanVar(value=False),  # Mal bitince otomatik alim
            'bir_sifir_alim': tk.BooleanVar(value=False),  # 1+0 alim (aylik bazda, sarkitmasiz)

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

        # Alim Tarihi - Takvim + Son Tarih Butonu
        row2 = tk.Frame(content, bg=self.colors['card_bg'])
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="Alim Tarihi:", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)

        # Sağ taraf container (tarih + buton)
        tarih_container = tk.Frame(row2, bg=self.colors['card_bg'])
        tarih_container.pack(side=tk.RIGHT)

        # Son tarihi getir butonu
        son_tarih_btn = tk.Button(tarih_container, text="◄",
                                  font=('Segoe UI', 8, 'bold'),
                                  bg=self.colors['info'], fg='white',
                                  relief='flat', cursor='hand2', width=2,
                                  command=lambda v=vars: self._son_tarihi_getir(v))
        son_tarih_btn.pack(side=tk.LEFT, padx=(0, 3))

        DateEntry(tarih_container, textvariable=vars['alim_tarihi'],
                 font=('Segoe UI', 10), width=10,
                 background='#0f3460', foreground='white',
                 headersbackground='#e94560', headersforeground='white',
                 selectbackground='#e94560', selectforeground='white',
                 normalbackground='#1a1a2e', normalforeground='white',
                 date_pattern='dd.mm.yyyy', locale='tr_TR').pack(side=tk.LEFT)

        # Vade
        row3 = tk.Frame(content, bg=self.colors['card_bg'])
        row3.pack(fill=tk.X, pady=4)
        tk.Label(row3, text="Vade (gun):", font=('Segoe UI', 10),
                fg=self.colors['text_dim'], bg=self.colors['card_bg'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=vars['vade_gun'], font=('Segoe UI', 11),
                bg=self.colors['entry_bg'], fg=self.colors['text'],
                relief='flat', width=8, justify='center').pack(side=tk.RIGHT)

        # Otomatik Alım Checkbox
        row4 = tk.Frame(content, bg=self.colors['card_bg'])
        row4.pack(fill=tk.X, pady=6)
        tk.Checkbutton(row4, text="Otomatik Alim",
                      variable=vars['otomatik_alim'],
                      font=('Segoe UI', 10, 'bold'),
                      fg=self.colors['success'], bg=self.colors['card_bg'],
                      selectcolor=self.colors['entry_bg'],
                      activebackground=self.colors['card_bg'],
                      activeforeground=self.colors['success'],
                      cursor='hand2').pack(side=tk.LEFT)
        tk.Label(row4, text="(Mal bitince tekrar al)",
                font=('Segoe UI', 8), fg=self.colors['text_dim'],
                bg=self.colors['card_bg']).pack(side=tk.LEFT, padx=5)

        # 1+0 Alım Checkbox (ayın sonuna kadar yetecek kadar)
        row5 = tk.Frame(content, bg=self.colors['card_bg'])
        row5.pack(fill=tk.X, pady=4)
        tk.Checkbutton(row5, text="1+0 Alim",
                      variable=vars['bir_sifir_alim'],
                      font=('Segoe UI', 10, 'bold'),
                      fg='#e67e22', bg=self.colors['card_bg'],
                      selectcolor=self.colors['entry_bg'],
                      activebackground=self.colors['card_bg'],
                      activeforeground='#e67e22',
                      cursor='hand2').pack(side=tk.LEFT)
        tk.Label(row5, text="(Ay sonuna yetecek kadar)",
                font=('Segoe UI', 8), fg=self.colors['text_dim'],
                bg=self.colors['card_bg']).pack(side=tk.LEFT, padx=5)

    def _son_tarihi_getir(self, vars):
        """Simülasyondaki son tarihi Alım Tarihi alanına getirir"""
        if self.son_simulasyon_tarihi:
            vars['alim_tarihi'].set(self.son_simulasyon_tarihi.strftime("%d.%m.%Y"))
        else:
            messagebox.showinfo("Bilgi", "Henüz simülasyon başlatılmadı.\nÖnce simülasyonu başlatın.")

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
            'sgk_acik', 'sgk_kesin',
            'depo_acik', 'depo_kesin',
            'pos_bekleyen', 'emk_bekleyen', 'emk_alacak',
            'kredi_borc', 'faiz_gelir', 'faiz_gider', 'ozkaynak'
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
            'depo_acik': ('Dpo Açk', 65),
            'depo_kesin': ('Dpo Ksn', 65),
            'pos_bekleyen': ('POS Bkl', 60),
            'emk_bekleyen': ('Emk Bkl', 60),
            'emk_alacak': ('Emk Alc', 60),
            'kredi_borc': ('Kredi', 60),
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

    def _birlesik_hesap_paneli_olustur(self, parent):
        """Butonların altına birleşik hesap durumu paneli - 4 kategori yan yana, satır satır detay"""
        # Referanslar
        self.hesap_treeler = {}
        self.hesap_toplamlari = {}

        # Ana container - mavi arka plan
        hesap_frame = tk.Frame(parent, bg=self.colors['panel_bg'])
        hesap_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 4 sütunlu grid
        for i in range(4):
            hesap_frame.columnconfigure(i, weight=1)
        hesap_frame.rowconfigure(0, weight=1)

        # Kategori tanımları: (başlık, renk, tip, alacak_mi)
        kategoriler = [
            ('SGK FATURALARI', '#0f3460', 'sgk', True),
            ('DEPO SENETLERİ', '#8b4513', 'depo', False),
            ('EMEKLİ KATILIM PAYI', '#2e7d32', 'emekli', True),
            ('BANKA KREDİLERİ', '#c62828', 'kredi', False),
        ]

        for col, (baslik, renk, tip, alacak_mi) in enumerate(kategoriler):
            # Kategori kartı
            kart = tk.Frame(hesap_frame, bg=self.colors['card_bg'], bd=1, relief='solid')
            kart.grid(row=0, column=col, sticky='nsew', padx=3, pady=3)

            # Başlık
            header = tk.Frame(kart, bg=renk, height=28)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            tk.Label(header, text=baslik, font=('Segoe UI', 10, 'bold'),
                    fg='white', bg=renk).pack(expand=True)

            # Liste container
            list_frame = tk.Frame(kart, bg=self.colors['card_bg'])
            list_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

            # Mini treeview
            columns = ('vade', 'tutar')
            tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=5)

            tree.heading('vade', text='Vade')
            tree.heading('tutar', text='Tutar')
            tree.column('vade', width=85, anchor='center')
            tree.column('tutar', width=90, anchor='e')

            # Tag renkleri - koyu tonlar okunabilirlik için
            tree.tag_configure('acik', foreground='#333333')
            tree.tag_configure('kesin', foreground='#000000')

            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self.hesap_treeler[tip] = tree

            # Alt toplam satırı
            toplam_frame = tk.Frame(kart, bg=self.colors['accent2'], padx=5, pady=4)
            toplam_frame.pack(fill=tk.X)

            renk_toplam = self.colors['success'] if alacak_mi else self.colors['danger']
            toplam_lbl = tk.Label(toplam_frame, text="TOPLAM: 0.00 TL",
                                 font=('Segoe UI', 9, 'bold'),
                                 fg=renk_toplam, bg=self.colors['accent2'])
            toplam_lbl.pack()

            self.hesap_toplamlari[tip] = toplam_lbl

    def _panel_detay_goster(self, tip, idx, renk, baslik):
        """Panel detaylarını popup'ta göster - vadeli liste"""
        if idx not in self.senaryolar:
            return

        senaryo = self.senaryolar[idx]

        popup = tk.Toplevel(self.root)
        popup.title(f"{baslik} - Detay")
        popup.geometry("500x400")
        popup.configure(bg=self.colors['panel_bg'])
        popup.transient(self.root)

        # Başlık
        header = tk.Frame(popup, bg=renk, height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=baslik, font=('Segoe UI', 14, 'bold'),
                fg='white', bg=renk).pack(expand=True)

        # Liste container
        list_frame = tk.Frame(popup, bg=self.colors['panel_bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Treeview
        columns = ('vade', 'tutar', 'durum')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        tree.heading('vade', text='Vade Tarihi')
        tree.heading('tutar', text='Tutar')
        tree.heading('durum', text='Durum')

        tree.column('vade', width=120, anchor='center')
        tree.column('tutar', width=150, anchor='e')
        tree.column('durum', width=150, anchor='center')

        # Verileri doldur
        toplam = 0

        if tip == 'sgk':
            # Açık hesaplar (fatura kesilmemiş)
            for ay_key, tutar in sorted(senaryo.sgk_acik_hesap.items()):
                tree.insert('', 'end', values=(
                    f"{ay_key} (Açık)",
                    f"{tutar:,.2f} TL",
                    "Fatura Bekliyor"
                ), tags=('acik',))
                toplam += tutar
            # Kesinleşmiş alacaklar
            for vade, tutar in sorted(senaryo.sgk_alacak.items()):
                tree.insert('', 'end', values=(
                    vade.strftime('%d.%m.%Y'),
                    f"{tutar:,.2f} TL",
                    "Tahsilat Bekliyor"
                ), tags=('kesin',))
                toplam += tutar

        elif tip == 'depo':
            # Açık hesaplar (senet kesilmemiş)
            for ay_key, tutar in sorted(senaryo.depo_acik_hesap.items()):
                tree.insert('', 'end', values=(
                    f"{ay_key} (Açık)",
                    f"{tutar:,.2f} TL",
                    "Senet Bekliyor"
                ), tags=('acik',))
                toplam += tutar
            # Kesinleşmiş borçlar
            for vade, tutar in sorted(senaryo.depo_borc.items()):
                tree.insert('', 'end', values=(
                    vade.strftime('%d.%m.%Y'),
                    f"{tutar:,.2f} TL",
                    "Ödeme Bekliyor"
                ), tags=('kesin',))
                toplam += tutar

        elif tip == 'emekli':
            # Bekleyen (ay içi birikim)
            for key, tutar in sorted(senaryo.emekli_katilim_bekleyen.items()):
                if isinstance(key, str):
                    tree.insert('', 'end', values=(
                        f"{key} (Birikim)",
                        f"{tutar:,.2f} TL",
                        "SGK'ya Yazılacak"
                    ), tags=('acik',))
                    toplam += tutar
            # SGK'ya yazılmış alacaklar
            for vade, tutar in sorted(senaryo.emekli_katilim_alacak.items()):
                tree.insert('', 'end', values=(
                    vade.strftime('%d.%m.%Y'),
                    f"{tutar:,.2f} TL",
                    "Tahsilat Bekliyor"
                ), tags=('kesin',))
                toplam += tutar

        elif tip == 'kredi':
            # Krediler
            for cekilis, data in sorted(senaryo.kredi_borclari.items()):
                if data['kalan'] > 0:
                    tree.insert('', 'end', values=(
                        cekilis.strftime('%d.%m.%Y'),
                        f"{data['kalan']:,.2f} TL",
                        f"Çekilen: {data['tutar']:,.2f}"
                    ), tags=('kesin',))
                    toplam += data['kalan']

        # Tag renkleri - koyu tonlar okunabilirlik için
        tree.tag_configure('acik', foreground='#333333')
        tree.tag_configure('kesin', foreground='#000000')

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Toplam
        toplam_frame = tk.Frame(popup, bg=self.colors['accent2'], padx=15, pady=10)
        toplam_frame.pack(fill=tk.X, padx=15, pady=5)

        renk_toplam = self.colors['success'] if tip in ['sgk', 'emekli'] else self.colors['danger']
        tk.Label(toplam_frame, text=f"TOPLAM: {toplam:,.2f} TL",
                font=('Segoe UI', 12, 'bold'),
                fg=renk_toplam, bg=self.colors['accent2']).pack()

        # Kapat butonu
        tk.Button(popup, text="KAPAT", font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['danger'], fg='white', relief='flat',
                 cursor='hand2', width=12, command=popup.destroy).pack(pady=10)

    def _ozet_panelleri_guncelle(self, idx, senaryo):
        """Birleşik hesap durumu panellerini güncelle"""
        if not hasattr(self, 'hesap_treeler'):
            return

        treeler = self.hesap_treeler
        toplamlari = self.hesap_toplamlari

        # ========== SGK ==========
        if 'sgk' in treeler:
            tree = treeler['sgk']
            tree.delete(*tree.get_children())
            toplam = 0

            # Açık hesaplar (fatura kesilmemiş) - biriken alacaklar
            for ay_key, tutar in sorted(senaryo.sgk_acik_hesap.items()):
                tree.insert('', 'end', values=(f"{ay_key} (Brkm)", f"{tutar:,.2f}"), tags=('acik',))
                toplam += tutar
            # Kesinleşmiş alacaklar
            for vade, tutar in sorted(senaryo.sgk_alacak.items()):
                tree.insert('', 'end', values=(vade.strftime('%d.%m.%Y'), f"{tutar:,.2f}"), tags=('kesin',))
                toplam += tutar

            toplamlari['sgk'].config(text=f"TOPLAM: {toplam:,.2f} TL")

        # ========== DEPO ==========
        if 'depo' in treeler:
            tree = treeler['depo']
            tree.delete(*tree.get_children())
            toplam = 0

            # Açık hesaplar (senet kesilmemiş) - biriken borçlar
            for ay_key, tutar in sorted(senaryo.depo_acik_hesap.items()):
                tree.insert('', 'end', values=(f"{ay_key} (Brkm)", f"{tutar:,.2f}"), tags=('acik',))
                toplam += tutar
            # Kesinleşmiş borçlar (senet kesilmiş)
            for vade, tutar in sorted(senaryo.depo_borc.items()):
                tree.insert('', 'end', values=(vade.strftime('%d.%m.%Y'), f"{tutar:,.2f}"), tags=('kesin',))
                toplam += tutar

            toplamlari['depo'].config(text=f"TOPLAM: {toplam:,.2f} TL")

        # ========== EMEKLİ K.P. ==========
        if 'emekli' in treeler:
            tree = treeler['emekli']
            tree.delete(*tree.get_children())
            toplam = 0

            # Bekleyen (ay içi birikim)
            for key, tutar in sorted(senaryo.emekli_katilim_bekleyen.items()):
                if isinstance(key, str):
                    tree.insert('', 'end', values=(f"{key} (Brkm)", f"{tutar:,.2f}"), tags=('acik',))
                    toplam += tutar
            # SGK'ya yazılmış alacaklar
            for vade, tutar in sorted(senaryo.emekli_katilim_alacak.items()):
                tree.insert('', 'end', values=(vade.strftime('%d.%m.%Y'), f"{tutar:,.2f}"), tags=('kesin',))
                toplam += tutar

            toplamlari['emekli'].config(text=f"TOPLAM: {toplam:,.2f} TL")

        # ========== KREDİ ==========
        if 'kredi' in treeler:
            tree = treeler['kredi']
            tree.delete(*tree.get_children())
            toplam = 0

            # Krediler
            for cekilis, data in sorted(senaryo.kredi_borclari.items()):
                if data['kalan'] > 0:
                    tree.insert('', 'end', values=(cekilis.strftime('%d.%m.%Y'), f"{data['kalan']:,.2f}"), tags=('kesin',))
                    toplam += data['kalan']

            toplamlari['kredi'].config(text=f"TOPLAM: {toplam:,.2f} TL")

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

    def _senaryo_sil(self, idx):
        """Senaryo sekmesini sil"""
        if self.aktif_senaryo_sayisi <= 1:
            messagebox.showwarning("Uyari", "En az bir senaryo olmali!")
            return

        if not messagebox.askyesno("Onay", f"Senaryo {idx + 1} silinecek. Emin misiniz?"):
            return

        # Sekmeyi notebook'tan kaldir
        if idx in self.senaryo_tabs:
            self.notebook.forget(self.senaryo_tabs[idx])

        # Verileri temizle
        if idx in self.senaryolar:
            del self.senaryolar[idx]
        if idx in self.senaryo_vars:
            del self.senaryo_vars[idx]
        if idx in self.senaryo_tabs:
            del self.senaryo_tabs[idx]
        if idx in self.senaryo_frames:
            del self.senaryo_frames[idx]
        if idx in self.senaryo_trees:
            del self.senaryo_trees[idx]

        self.aktif_senaryo_sayisi -= 1

        # Ilk sekmeyi sec
        if self.notebook.tabs():
            self.notebook.select(0)

        messagebox.showinfo("Bilgi", f"Senaryo {idx + 1} silindi!")

    def _hareket_log_penceresi(self, idx):
        """Senaryo icin hareket loglarini gosteren pencere"""
        senaryo = self.senaryolar.get(idx)
        if not senaryo:
            messagebox.showwarning("Uyari", "Senaryo bulunamadi!")
            return

        # Pencere olustur
        log_win = tk.Toplevel(self.root)
        log_win.title(f"Senaryo {idx + 1} - Hareket Loglari")
        log_win.geometry("700x500")
        log_win.configure(bg=self.colors['bg'])

        # Baslik
        header = tk.Frame(log_win, bg='#8e44ad', height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"SENARYO {idx + 1} - HAREKET LOGLARI",
                font=('Segoe UI', 12, 'bold'), fg='white', bg='#8e44ad').pack(expand=True)

        # Log listesi (Treeview)
        tree_frame = tk.Frame(log_win, bg=self.colors['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('tarih', 'tip', 'aciklama', 'tutar')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        tree.heading('tarih', text='Tarih')
        tree.heading('tip', text='Tip')
        tree.heading('aciklama', text='Aciklama')
        tree.heading('tutar', text='Tutar')

        tree.column('tarih', width=100, anchor='center')
        tree.column('tip', width=120, anchor='center')
        tree.column('aciklama', width=300, anchor='w')
        tree.column('tutar', width=120, anchor='e')

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Loglari yukle
        if hasattr(senaryo, 'hareket_loglari'):
            for log in senaryo.hareket_loglari:
                tree.insert('', 'end', values=(
                    log.get('tarih', ''),
                    log.get('tip', ''),
                    log.get('aciklama', ''),
                    f"{log.get('tutar', 0):,.2f} TL"
                ))

        # Temizle butonu
        btn_frame = tk.Frame(log_win, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, pady=10)

        def temizle():
            if hasattr(senaryo, 'hareket_loglari'):
                senaryo.hareket_loglari.clear()
            for item in tree.get_children():
                tree.delete(item)

        tk.Button(btn_frame, text="Loglari Temizle",
                 font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['danger'], fg='white',
                 relief='flat', cursor='hand2',
                 command=temizle).pack(side=tk.LEFT, padx=20)

        tk.Button(btn_frame, text="Kapat",
                 font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['secondary'], fg='white',
                 relief='flat', cursor='hand2',
                 command=log_win.destroy).pack(side=tk.RIGHT, padx=20)

        # Pencereyi referans olarak sakla (guncelleme icin)
        if not hasattr(self, 'log_pencereleri'):
            self.log_pencereleri = {}
        self.log_pencereleri[idx] = {'window': log_win, 'tree': tree}

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

        # Basit Hesaplayici butonu
        self.hesaplayici_btn = tk.Button(inner, text="HESAPLAYICI",
                                        bg='#0ea5e9', fg='white',
                                        command=self._basit_hesaplayici_ac, **btn_style)
        self.hesaplayici_btn.pack(side=tk.LEFT, padx=5)

        # Mal Bitisine Kadar Oynat butonu
        self.mal_bitis_btn = tk.Button(inner, text="MAL BİTİŞİ",
                                       bg='#e67e22', fg='white',
                                       command=self._mal_bitisine_kadar_popup, **btn_style)
        self.mal_bitis_btn.pack(side=tk.LEFT, padx=5)

        # Mevcut gun
        tk.Label(inner, text="Mevcut Gun:", font=('Segoe UI', 9),
                fg=self.colors['text'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=(20, 5))

        self.mevcut_gun_label = tk.Label(inner, text="0", font=('Segoe UI', 11, 'bold'),
                                        fg=self.colors['accent'], bg=self.colors['accent2'])
        self.mevcut_gun_label.pack(side=tk.LEFT)

        # Ozet labels icin bos dict (popup acildiginda doldurulacak)
        self.ozet_labels = {}
        self.en_karli_label = None

        # === DETAYLI HESAP DURUMU PANELİ (En altta) ===
        self._birlesik_hesap_paneli_olustur(parent)

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
        basliklar = ['', 'Kasa', 'Mal', 'Banka', 'SGK Açk', 'SGK Ksn',
                    'Dpo Açk', 'Dpo Ksn', 'POS Bkl', 'Emk Bkl', 'Emk Alc', 'Kredi',
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
        self.son_simulasyon_tarihi = None
        return True

    def _bir_gun_hesapla(self, idx):
        """Tek senaryo icin bir gun hesapla - Yeni hesaplama mantigi"""
        senaryo = self.senaryolar[idx]
        d = senaryo.durum

        if not d:
            return False

        gun = self.mevcut_gun
        mevcut_tarih = d['bugun'] + timedelta(days=gun)
        self.son_simulasyon_tarihi = mevcut_tarih  # Son tarihi kaydet

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

                # Alım yapıldı - stok uyarı durumunu sıfırla (tekrar devam edebilsin)
                self.stok_uyari_gosterildi[idx] = False
                self.senaryo_duraklatildi[idx] = False

        # ============ GÜNÜN BAŞI: Dünkü kasa → Banka ============
        # Ertesi gün mantığı: Dün kasaya giren para bugün bankaya yatar
        if d['kasa'] > 0:
            d['banka'] += d['kasa']
            d['kasa'] = 0

        # Zam kontrolu - her gün vars'tan zam tarihini kontrol et (yeni zam girilmiş olabilir)
        vars = self.senaryo_vars[idx]
        if vars['zam_tarihi'].get().strip():
            try:
                yeni_zam_tarihi = datetime.strptime(vars['zam_tarihi'].get(), "%d.%m.%Y")
                yeni_zam_orani = float(vars['zam_orani'].get()) / 100
                # Zam tarihi geldiyse ve bu zam daha önce uygulanmadıysa
                if mevcut_tarih >= yeni_zam_tarihi and d.get('son_uygulanan_zam') != yeni_zam_tarihi:
                    zam_carpani = 1 + yeni_zam_orani
                    eski_depocu = d['depocu_fiyat']
                    eski_kamu = d['kamu_fiyat']
                    eski_piyasa = d['piyasa_fiyat']
                    eski_fark = d['ilac_farki']

                    d['depocu_fiyat'] *= zam_carpani
                    d['kamu_fiyat'] *= zam_carpani
                    d['piyasa_fiyat'] *= zam_carpani
                    d['ilac_farki'] *= zam_carpani

                    # GUI textbox'ları güncelle
                    vars['depocu_fiyat'].set(f"{d['depocu_fiyat']:.2f}")
                    vars['kamu_fiyat'].set(f"{d['kamu_fiyat']:.2f}")
                    vars['piyasa_fiyat'].set(f"{d['piyasa_fiyat']:.2f}")
                    vars['ilac_farki'].set(f"{d['ilac_farki']:.2f}")

                    # Bildirim ekle
                    self._bildirim_ekle('zam', yeni_zam_orani * 100,
                        f"ZAM UYGULANDI (%{yeni_zam_orani*100:.1f})\n"
                        f"DSF: {eski_depocu:.2f} → {d['depocu_fiyat']:.2f}\n"
                        f"KSF: {eski_kamu:.2f} → {d['kamu_fiyat']:.2f}\n"
                        f"PSF: {eski_piyasa:.2f} → {d['piyasa_fiyat']:.2f}\n"
                        f"Fark: {eski_fark:.2f} → {d['ilac_farki']:.2f}",
                        '#ff9800')

                    d['son_uygulanan_zam'] = yeni_zam_tarihi  # Bu zamı bir daha uygulama
            except:
                pass

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

            # Satış sonrası kontroller - Stok kritik seviyede mi?
            if d['stok'] <= d['gunluk_sarf']:
                # Stok bitti veya yarın bitecek - Otomatik alım kontrolü
                vars = self.senaryo_vars[idx]
                otomatik_alim = vars['otomatik_alim'].get()

                # "Mal bitişine kadar" modunda mıyız ve bu senaryo durdurulacak mı?
                durdurulacak = self.mal_bitis_modu and self.mal_bitis_senaryosu == idx

                if durdurulacak:
                    # Bu senaryo bitince durdur
                    if not self.stok_uyari_gosterildi.get(idx, False):
                        self.stok_uyari_gosterildi[idx] = True
                        self.senaryo_duraklatildi[idx] = True
                        self.simulasyon_calisyor = False
                        self.uyari_bekliyor = True
                        messagebox.showinfo(
                            f"Senaryo {idx+1} - MAL BİTTİ",
                            f"🛑 SENARYO {idx+1} MALI BİTTİ!\n\n"
                            f"Tarih: {tarih_str}\n"
                            f"Simülasyon durduruldu."
                        )
                        self.uyari_bekliyor = False
                        self.root.after(0, lambda: self._butonlari_ayarla(False))
                elif otomatik_alim:
                    # Otomatik alım yap
                    bir_sifir_modu = vars['bir_sifir_alim'].get()

                    if bir_sifir_modu:
                        # 1+0 Alım: Ayın sonuna kadar yetecek kadar al
                        ayin_son_gunu = calendar.monthrange(mevcut_tarih.year, mevcut_tarih.month)[1]
                        kalan_gun = ayin_son_gunu - mevcut_tarih.day + 1  # Bugün dahil
                        gereken_stok = kalan_gun * d['gunluk_sarf']
                        eksik = gereken_stok - d['stok']
                        alim_adet = math.ceil(eksik) if eksik > 0 else 0
                        mf_bedava = 0  # 1+0'da bedava mal yok
                        toplam_alim = alim_adet
                    else:
                        # Normal alım: Ayarlardaki miktar
                        alim_adet = self._int_parse(vars['alim_adet'].get())
                        mf_bedava = self._int_parse(vars['mf_bedava'].get())
                        toplam_alim = alim_adet + mf_bedava

                    if toplam_alim > 0:
                        # Stok ekle
                        d['stok'] += toplam_alim

                        # Depo borcuna ekle
                        depo_borc = alim_adet * d['depocu_fiyat']
                        ay_key = mevcut_tarih.strftime("%Y-%m")
                        if ay_key not in senaryo.depo_acik_hesap:
                            senaryo.depo_acik_hesap[ay_key] = 0
                        senaryo.depo_acik_hesap[ay_key] += depo_borc

                        # Uyarı durumunu sıfırla
                        self.stok_uyari_gosterildi[idx] = False
                        self.senaryo_duraklatildi[idx] = False
                else:
                    # Otomatik alım yok - duruma göre uyarı ver
                    if not self.stok_uyari_gosterildi.get(idx, False):
                        self.stok_uyari_gosterildi[idx] = True
                        self.senaryo_duraklatildi[idx] = True
                        self.simulasyon_calisyor = False
                        self.uyari_bekliyor = True

                        if d['stok'] == 0:
                            messagebox.showwarning(
                                f"Senaryo {idx+1} - STOK UYARI",
                                f"⚠️ STOK SIFIRA DÜŞTÜ!\n\n"
                                f"Tarih: {tarih_str}\n"
                                f"Gün: {gun + 1}\n\n"
                                f"Simülasyon durdu!\n"
                                f"DEPODAN MAL ALIN, sonra tekrar OYNAT'a basın."
                            )
                        else:
                            messagebox.showwarning(
                                f"Senaryo {idx+1} - STOK UYARI",
                                f"⚠️ YARIN STOK BİTECEK!\n\n"
                                f"Tarih: {tarih_str}\n"
                                f"Kalan stok: {d['stok']:.2f}\n"
                                f"Günlük sarf: {d['gunluk_sarf']:.2f}\n\n"
                                f"SİMÜLASYON DURDU!\n"
                                f"Senaryo {idx+1} için DEPODAN ALIM YAPIN,\n"
                                f"sonra tekrar OYNAT'a basın."
                            )

                        self.uyari_bekliyor = False
                        self.root.after(0, lambda: self._butonlari_ayarla(False))

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

        # ============ EMEKLI KATILIM (ay içi birikir, ay başında SGK'ya yazılır) ============
        # Emekli katılım payı ay içinde birikir, ayın 1'inde SGK'ya alacak olarak yazılır
        emekli_ay_key = mevcut_tarih.strftime("%Y-%m")
        if emekli_ay_key not in senaryo.emekli_katilim_bekleyen:
            senaryo.emekli_katilim_bekleyen[emekli_ay_key] = 0
        senaryo.emekli_katilim_bekleyen[emekli_ay_key] += emekli_katilim

        # ============ AYIN 1'İ İŞLEMLERİ (Fatura & Senet Kesimi) ============
        if mevcut_tarih.day == 1:
            # Önceki ayın key'i
            onceki_ay = mevcut_tarih - timedelta(days=1)
            onceki_ay_key = onceki_ay.strftime("%Y-%m")

            sgk_fatura_tutar = 0
            muayene_borc_tutar = 0
            depo_senet_tutar = 0
            emekli_kp_tutar = 0

            # --- Muayene Borcu (SGK faturasından mahsup edilecek) ---
            if onceki_ay_key in senaryo.muayene_acik_borc:
                muayene_borc_tutar = senaryo.muayene_acik_borc.pop(onceki_ay_key)

            # --- SGK Fatura Kesimi (önceki ay açık hesap - muayene mahsubu = net alacak) ---
            if onceki_ay_key in senaryo.sgk_acik_hesap:
                sgk_brut = senaryo.sgk_acik_hesap.pop(onceki_ay_key)
                # Muayene tutarı SGK'dan mahsup edilir
                sgk_fatura_tutar = sgk_brut - muayene_borc_tutar
                # 75 gün sonra tahsil edilecek (ayın 15'inde)
                tahsil_tarihi = mevcut_tarih + timedelta(days=75)
                tahsil_tarihi = tahsil_tarihi.replace(day=15)
                if tahsil_tarihi not in senaryo.sgk_alacak:
                    senaryo.sgk_alacak[tahsil_tarihi] = 0
                senaryo.sgk_alacak[tahsil_tarihi] += sgk_fatura_tutar
                # Bildirim ekle
                ay_adi = onceki_ay.strftime("%B")
                self._bildirim_ekle('sgk_fatura', sgk_fatura_tutar,
                    f"SGK Faturası Kesildi ({ay_adi}) - Tahsil: {tahsil_tarihi.strftime('%d.%m.%Y')}",
                    '#17a2b8', senaryo=senaryo, tarih=mevcut_tarih)

            # --- Emekli Katılım Payı (SGK'ya alacak olarak yazılır) ---
            # Önceki ayda biriken emekli katılım payları
            emekli_kp_tutar = 0
            for tarih_key in list(senaryo.emekli_katilim_bekleyen.keys()):
                if isinstance(tarih_key, str) and tarih_key == onceki_ay_key:
                    emekli_kp_tutar += senaryo.emekli_katilim_bekleyen.pop(tarih_key)

            if emekli_kp_tutar > 0:
                # Ayın son günü vadeli (yaklaşık 60 gün sonra)
                # Örn: 1 Şubat'ta yazılır -> 31 Mart vadeli
                vade_tarihi = (mevcut_tarih.replace(day=1) + relativedelta(months=2)) - timedelta(days=1)
                if vade_tarihi not in senaryo.emekli_katilim_alacak:
                    senaryo.emekli_katilim_alacak[vade_tarihi] = 0
                senaryo.emekli_katilim_alacak[vade_tarihi] += emekli_kp_tutar
                # Bildirim ekle
                self._bildirim_ekle('emekli_kp_yaz', emekli_kp_tutar,
                    f"Emekli K.P. SGK'ya Yazıldı - Vade: {vade_tarihi.strftime('%d.%m.%Y')}",
                    '#2e7d32', senaryo=senaryo, tarih=mevcut_tarih)

            # --- Depo Senet Kesimi (SGK tahsilat tarihiyle aynı gün ödeme) ---
            if onceki_ay_key in senaryo.depo_acik_hesap:
                depo_senet_tutar = senaryo.depo_acik_hesap.pop(onceki_ay_key)
                # SGK ile aynı tarihte ödeme (önce SGK yatar, sonra depo ödenir)
                odeme_tarihi = mevcut_tarih + timedelta(days=75)
                odeme_tarihi = odeme_tarihi.replace(day=15)
                if odeme_tarihi not in senaryo.depo_borc:
                    senaryo.depo_borc[odeme_tarihi] = 0
                senaryo.depo_borc[odeme_tarihi] += depo_senet_tutar
                # Bildirim ekle
                ay_adi = onceki_ay.strftime("%B")
                self._bildirim_ekle('depo_senet', depo_senet_tutar,
                    f"Depo Senedi Kesildi ({ay_adi}) - Ödeme: {odeme_tarihi.strftime('%d.%m.%Y')}",
                    '#8b4513', senaryo=senaryo, tarih=mevcut_tarih)

            # --- BİLDİRİMLERİ GÖSTER (ay başı işlemleri) ---
            if self.gunluk_bildirimler:
                self._bildirimleri_goster(mevcut_tarih)

        # Kredi karti tahsilatlari (Blokeli POS)
        for tarih in list(senaryo.kredi_karti_bekleyen.keys()):
            if tarih <= mevcut_tarih:
                pos_tutar = senaryo.kredi_karti_bekleyen.pop(tarih)
                d['banka'] += pos_tutar
                # Bildirim ekle
                self._bildirim_ekle('pos_tahsil', pos_tutar,
                    "POS Blokesi Çözüldü - Bankaya Yatırıldı",
                    self.colors['success'], senaryo=senaryo, tarih=mevcut_tarih)

        # Emekli Katılım Payı Alacağı tahsilatları (SGK'dan gelen)
        for tarih in list(senaryo.emekli_katilim_alacak.keys()):
            if tarih <= mevcut_tarih:
                emk_tutar = senaryo.emekli_katilim_alacak.pop(tarih)
                d['banka'] += emk_tutar
                # Bildirim ekle
                self._bildirim_ekle('emekli_tahsil', emk_tutar,
                    "Emekli Katılım Payı Tahsil Edildi (SGK'dan)",
                    self.colors['success'], senaryo=senaryo, tarih=mevcut_tarih)

        # ============ SGK + DEPO İŞLEMLERİ (Aynı gün, sıralı) ============
        # Önce SGK tahsil edilir, sonra depo ödenir (hesap eksiye düşmesin)
        for tarih in list(senaryo.sgk_alacak.keys()):
            if tarih <= mevcut_tarih:
                # 1) SGK tahsilatı bankaya girer
                sgk_tahsilat = senaryo.sgk_alacak.pop(tarih)
                d['banka'] += sgk_tahsilat
                # Bildirim ekle
                self._bildirim_ekle('sgk_tahsil', sgk_tahsilat,
                    "SGK Fatura Tahsilatı - Bankaya Yatırıldı",
                    self.colors['success'], senaryo=senaryo, tarih=mevcut_tarih)

                # 2) Aynı tarihteki depo borcu ödenir
                if tarih in senaryo.depo_borc:
                    depo_odeme = senaryo.depo_borc.pop(tarih)
                    if d['banka'] >= depo_odeme:
                        d['banka'] -= depo_odeme
                        # Bildirim ekle
                        self._bildirim_ekle('depo_odeme', depo_odeme,
                            "Depo Senedi Ödendi - Bankadan Çıkış",
                            self.colors['danger'], senaryo=senaryo, tarih=mevcut_tarih)
                    else:
                        # Eksik kısım için bankadan kredi çekilir
                        eksik = depo_odeme - d['banka']
                        onceki_banka = d['banka']
                        d['banka'] = 0
                        d['banka_borc'] += eksik
                        # Kredi kaydı tut
                        if mevcut_tarih not in senaryo.kredi_borclari:
                            senaryo.kredi_borclari[mevcut_tarih] = {'tutar': 0, 'kalan': 0}
                        senaryo.kredi_borclari[mevcut_tarih]['tutar'] += eksik
                        senaryo.kredi_borclari[mevcut_tarih]['kalan'] += eksik
                        # Bildirimler ekle
                        if onceki_banka > 0:
                            self._bildirim_ekle('depo_odeme', onceki_banka,
                                "Depo Senedi Kısmi Ödeme - Bankadan Çıkış",
                                self.colors['danger'], senaryo=senaryo, tarih=mevcut_tarih)
                        self._bildirim_ekle('kredi_cek', eksik,
                            f"BANKADAN KREDİ ÇEKİLDİ - Depo ödemesi için",
                            self.colors['warning'], senaryo=senaryo, tarih=mevcut_tarih)
                        self._bildirim_ekle('depo_odeme', eksik,
                            "Depo Senedi Kalan Ödeme - Krediden",
                            self.colors['danger'], senaryo=senaryo, tarih=mevcut_tarih)

        # SGK tarihi dışında kalan depo ödemeleri (olmamalı ama güvenlik için)
        for tarih in list(senaryo.depo_borc.keys()):
            if tarih <= mevcut_tarih:
                borc = senaryo.depo_borc.pop(tarih)
                if d['banka'] >= borc:
                    d['banka'] -= borc
                    self._bildirim_ekle('depo_odeme', borc,
                        "Depo Senedi Ödendi - Bankadan Çıkış",
                        self.colors['danger'], senaryo=senaryo, tarih=mevcut_tarih)
                else:
                    eksik = borc - d['banka']
                    onceki_banka = d['banka']
                    d['banka'] = 0
                    d['banka_borc'] += eksik
                    if mevcut_tarih not in senaryo.kredi_borclari:
                        senaryo.kredi_borclari[mevcut_tarih] = {'tutar': 0, 'kalan': 0}
                    senaryo.kredi_borclari[mevcut_tarih]['tutar'] += eksik
                    senaryo.kredi_borclari[mevcut_tarih]['kalan'] += eksik
                    if onceki_banka > 0:
                        self._bildirim_ekle('depo_odeme', onceki_banka,
                            "Depo Senedi Kısmi Ödeme - Bankadan Çıkış",
                            self.colors['danger'], senaryo=senaryo, tarih=mevcut_tarih)
                    self._bildirim_ekle('kredi_cek', eksik,
                        f"BANKADAN KREDİ ÇEKİLDİ - Depo ödemesi için",
                        self.colors['warning'], senaryo=senaryo, tarih=mevcut_tarih)

        # ============ KREDİ OTOMATİK ÖDEME ============
        # Banka bakiyesi TÜM BORCU kapatacak kadar olunca kredi ödenir
        if d['banka_borc'] > 0 and d['banka'] >= d['banka_borc']:
            odeme = d['banka_borc']  # Tüm borcu öde
            d['banka'] -= odeme
            d['banka_borc'] = 0
            # Kredi borçları kaydını temizle
            senaryo.kredi_borclari.clear()
            # Bildirim ekle
            self._bildirim_ekle('kredi_ode', odeme,
                "BANKA KREDİSİ TAMAMEN ÖDENDİ",
                '#9c27b0', senaryo=senaryo, tarih=mevcut_tarih)

        # ============ TAHSİLAT/ÖDEME BİLDİRİMLERİNİ GÖSTER ============
        if self.gunluk_bildirimler:
            self._bildirimleri_goster(mevcut_tarih)

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
        muayene_borc_toplam = sum(senaryo.muayene_acik_borc.values())  # Mahsup bekleyen (ay içi)
        depo_acik_toplam = sum(senaryo.depo_acik_hesap.values())    # Senet kesilmemiş
        depo_kesin_toplam = sum(senaryo.depo_borc.values())         # Senet kesilmiş
        pos_bekleyen_toplam = sum(senaryo.kredi_karti_bekleyen.values())  # Blokeli POS
        # Emekli katılım: ay içi bekleyen + SGK'ya yazılmış alacak
        emk_bekleyen_toplam = sum(v for k, v in senaryo.emekli_katilim_bekleyen.items() if isinstance(k, str))
        emk_alacak_toplam = sum(senaryo.emekli_katilim_alacak.values())  # SGK'ya yazılmış
        # Kredi borçları toplamı
        kredi_toplam = sum(k['kalan'] for k in senaryo.kredi_borclari.values())

        # Stok degeri (güncel depocu fiyatı ile)
        mal_degeri = d['stok'] * d['depocu_fiyat']

        # Ozkaynak (tüm alacaklar - tüm borçlar)
        sgk_toplam = sgk_acik_toplam + sgk_kesin_toplam
        depo_toplam = depo_acik_toplam + depo_kesin_toplam
        emk_toplam = emk_bekleyen_toplam + emk_alacak_toplam
        # Aktifler: Kasa + Banka + SGK Alacak + POS Bekleyen + Emekli K.P. + Mal
        # NOT: SGK'dan muayene mahsup edildiği için sgk_toplam zaten net değer
        aktifler = d['kasa'] + d['banka'] + sgk_toplam + pos_bekleyen_toplam + emk_toplam + mal_degeri
        # Pasifler: Depo Borç + Banka Kredisi (muayene artık mahsup edildiği için borç değil)
        pasifler = depo_toplam + d['banka_borc']
        ozkaynak = aktifler - pasifler

        # Data grid'e ekle
        self._satir_ekle(idx, gun + 1, mevcut_tarih, d['stok'], satis_miktari,
                        d['kasa'], d['banka'],
                        sgk_acik_toplam, sgk_kesin_toplam,
                        depo_acik_toplam, depo_kesin_toplam,
                        pos_bekleyen_toplam, emk_bekleyen_toplam, emk_alacak_toplam,
                        kredi_toplam, d['toplam_faiz_gelir'], d['toplam_faiz_gider'], ozkaynak)

        # Ozet guncelle
        senaryo.ozet = {
            'kasa': d['kasa'],
            'mal': mal_degeri,
            'banka': d['banka'],
            'sgk_acik': sgk_acik_toplam,
            'sgk_kesin': sgk_kesin_toplam,
            'depo_acik': depo_acik_toplam,
            'depo_kesin': depo_kesin_toplam,
            'pos_bekleyen': pos_bekleyen_toplam,
            'emk_bekleyen': emk_bekleyen_toplam,
            'emk_alacak': emk_alacak_toplam,
            'kredi_borc': kredi_toplam,
            'banka_borc': d['banka_borc'],
            'faiz_gelir': d['toplam_faiz_gelir'],
            'faiz_gider': d['toplam_faiz_gider'],
            'ozkaynak': ozkaynak,
        }

        # Özet panelleri güncelle
        self._ozet_panelleri_guncelle(idx, senaryo)

        # Her zaman devam et - kullanıcı alım ekleyebilir
        return True

    def _satir_ekle(self, idx, gun, tarih, stok, satis, kasa, banka,
                   sgk_acik, sgk_kesin,
                   depo_acik, depo_kesin,
                   pos_bekleyen, emk_bekleyen, emk_alacak,
                   kredi_borc, faiz_gelir, faiz_gider, ozkaynak):
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
                f"{depo_acik:.2f}",
                f"{depo_kesin:.2f}",
                f"{pos_bekleyen:.2f}",
                f"{emk_bekleyen:.2f}",
                f"{emk_alacak:.2f}",
                f"{kredi_borc:.2f}",
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
                    ozet.get('depo_acik', 0),
                    ozet.get('depo_kesin', 0),
                    ozet.get('pos_bekleyen', 0),
                    ozet.get('emk_bekleyen', 0),
                    ozet.get('emk_alacak', 0),
                    ozet.get('kredi_borc', 0),
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

            # Herhangi bir senaryoda stok bittiyse veya duraklatıldıysa dur
            # (1 gün önceden uyarı _bir_gun_hesapla içinde verilir ve simülasyon durdurulur)
            stok_bitti = False
            for idx in range(self.aktif_senaryo_sayisi):
                d = self.senaryolar[idx].durum
                if d:
                    # Stok tamamen bittiyse
                    if d.get('stok', 0) <= 0:
                        stok_bitti = True
                        break
                    # Senaryo duraklatıldıysa (1 gün önceden uyarı verildi)
                    if self.senaryo_duraklatildi.get(idx, False):
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
        self.son_simulasyon_tarihi = None
        self.mevcut_gun_label.config(text="0")

        # Senaryo durum değişkenlerini sıfırla
        self.senaryo_duraklatildi = {}
        self.stok_uyari_gosterildi = {}
        self.mal_bitis_modu = False
        self.mal_bitis_senaryosu = None

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

    # ==================== HESAP HAREKETİ BİLDİRİM SİSTEMİ ====================

    def _bildirim_ekle(self, tip, tutar, aciklama, renk='#17a2b8', senaryo=None, tarih=None):
        """Günlük bildirimlere yeni hareket ekle ve senaryo loguna kaydet"""
        self.gunluk_bildirimler.append({
            'tip': tip,
            'tutar': tutar,
            'aciklama': aciklama,
            'renk': renk
        })

        # Senaryo loguna da kaydet
        if senaryo and hasattr(senaryo, 'hareket_loglari'):
            tarih_str = tarih.strftime('%d.%m.%Y') if tarih else ''
            senaryo.hareket_loglari.append({
                'tarih': tarih_str,
                'tip': tip,
                'aciklama': aciklama,
                'tutar': tutar
            })

    def _bildirimleri_goster(self, tarih):
        """Biriken bildirimleri popup'ta göster ve listeyi temizle"""
        if not self.gunluk_bildirimler:
            return

        # Sadece kredi ile ilgili bildirimler varsa popup göster
        kredi_bildirimleri = [b for b in self.gunluk_bildirimler
                             if b['tip'] in ('kredi_cek', 'kredi_ode')]

        if not kredi_bildirimleri:
            # Kredi bildirimi yoksa popup açma, listeyi temizle
            self.gunluk_bildirimler = []
            return

        # Simülasyon duraklatılsın
        self.uyari_bekliyor = True

        popup = tk.Toplevel(self.root)
        popup.title(f"KREDİ İŞLEMİ - {tarih.strftime('%d.%m.%Y')}")
        popup.geometry("550x450")
        popup.configure(bg=self.colors['panel_bg'])
        popup.transient(self.root)
        popup.grab_set()

        # Başlık
        baslik = tk.Label(popup,
                         text=f"📊 {tarih.strftime('%d.%m.%Y')} TARİHLİ HESAP HAREKETLERİ",
                         font=('Segoe UI', 14, 'bold'),
                         fg=self.colors['accent'], bg=self.colors['panel_bg'])
        baslik.pack(pady=15)

        # Scrollable container
        canvas_frame = tk.Frame(popup, bg=self.colors['panel_bg'])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        canvas = tk.Canvas(canvas_frame, bg=self.colors['panel_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['panel_bg'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Toplam hesapları
        toplam_giris = 0
        toplam_cikis = 0

        # Sadece kredi bildirimleri için kart oluştur
        for bildirim in kredi_bildirimleri:
            kart = tk.Frame(scrollable_frame, bg=self.colors['card_bg'], bd=1, relief='solid')
            kart.pack(fill=tk.X, pady=3, padx=5)

            # Sol: tip ikonu ve açıklama
            sol = tk.Frame(kart, bg=self.colors['card_bg'])
            sol.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=8)

            # İkon belirle
            ikon_map = {
                'sgk_fatura': '📄',
                'depo_senet': '📝',
                'emekli_kp_yaz': '💰',
                'sgk_tahsil': '✅',
                'depo_odeme': '💳',
                'emekli_tahsil': '💵',
                'kredi_cek': '🏦',
                'kredi_ode': '✔️',
                'pos_tahsil': '💳',
                'zam': '📈',
            }
            ikon = ikon_map.get(bildirim['tip'], '📌')

            tk.Label(sol, text=f"{ikon} {bildirim['aciklama']}",
                    font=('Segoe UI', 10),
                    fg=self.colors['text'], bg=self.colors['card_bg'],
                    anchor='w').pack(side=tk.LEFT)

            # Sağ: tutar
            sag = tk.Frame(kart, bg=self.colors['card_bg'])
            sag.pack(side=tk.RIGHT, padx=10, pady=8)

            # Tutar rengi (giriş yeşil, çıkış kırmızı)
            tutar_renk = bildirim['renk']
            tutar_text = f"{bildirim['tutar']:,.2f} TL"

            # Giriş/çıkış hesabı
            if bildirim['tip'] in ['sgk_tahsil', 'emekli_tahsil', 'pos_tahsil', 'kredi_cek']:
                toplam_giris += bildirim['tutar']
                tutar_text = f"+{tutar_text}"
            elif bildirim['tip'] in ['depo_odeme', 'kredi_ode']:
                toplam_cikis += bildirim['tutar']
                tutar_text = f"-{tutar_text}"

            tk.Label(sag, text=tutar_text,
                    font=('Segoe UI', 11, 'bold'),
                    fg=tutar_renk, bg=self.colors['card_bg']).pack(side=tk.RIGHT)

        # Özet satırı
        ozet_frame = tk.Frame(popup, bg=self.colors['accent2'], padx=15, pady=10)
        ozet_frame.pack(fill=tk.X, padx=20, pady=10)

        ozet_row = tk.Frame(ozet_frame, bg=self.colors['accent2'])
        ozet_row.pack(fill=tk.X)

        if toplam_giris > 0:
            tk.Label(ozet_row, text=f"Toplam Giriş: +{toplam_giris:,.2f} TL",
                    font=('Segoe UI', 10, 'bold'),
                    fg=self.colors['success'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=10)

        if toplam_cikis > 0:
            tk.Label(ozet_row, text=f"Toplam Çıkış: -{toplam_cikis:,.2f} TL",
                    font=('Segoe UI', 10, 'bold'),
                    fg=self.colors['danger'], bg=self.colors['accent2']).pack(side=tk.LEFT, padx=10)

        net = toplam_giris - toplam_cikis
        net_renk = self.colors['success'] if net >= 0 else self.colors['danger']
        net_text = f"+{net:,.2f}" if net >= 0 else f"{net:,.2f}"
        tk.Label(ozet_row, text=f"Net: {net_text} TL",
                font=('Segoe UI', 10, 'bold'),
                fg=net_renk, bg=self.colors['accent2']).pack(side=tk.RIGHT, padx=10)

        # Tamam butonu
        def kapat():
            self.uyari_bekliyor = False
            popup.destroy()

        tamam_btn = tk.Button(popup, text="TAMAM",
                             font=('Segoe UI', 11, 'bold'),
                             bg=self.colors['info'], fg='white',
                             relief='flat', cursor='hand2', width=15,
                             command=kapat)
        tamam_btn.pack(pady=15)

        # Bildirimleri temizle
        self.gunluk_bildirimler = []

        # Pencere kapatılınca da flag sıfırlansın
        popup.protocol("WM_DELETE_WINDOW", kapat)

        # Pencereyi bekle
        popup.wait_window()

    def _ay_basi_popup_goster(self, mevcut_tarih, onceki_ay, sgk_fatura, muayene_borc, depo_senet, emekli_kp, vade):
        """Ayın 1'inde SGK fatura ve Depo senet bilgilerini popup pencerede göster"""
        # Ana popup pencere
        popup = tk.Toplevel(self.root)
        popup.title(f"AY BAŞI BİLDİRİMİ - {mevcut_tarih.strftime('%d.%m.%Y')}")
        popup.geometry("600x550")
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

            # Tahsil tarihi (75 gün)
            tahsil_tarihi = mevcut_tarih + timedelta(days=75)
            tahsil_tarihi = tahsil_tarihi.replace(day=15)
            row4 = tk.Frame(sgk_content, bg=self.colors['card_bg'])
            row4.pack(fill=tk.X, pady=5)
            tk.Label(row4, text="Tahsil Tarihi:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row4, text=f"📅 {tahsil_tarihi.strftime('%d.%m.%Y')} (75 gün)",
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

            # Ödeme tarihi (SGK ile aynı gün - 75 gün)
            odeme_tarihi = mevcut_tarih + timedelta(days=75)
            odeme_tarihi = odeme_tarihi.replace(day=15)
            row2 = tk.Frame(depo_content, bg=self.colors['card_bg'])
            row2.pack(fill=tk.X, pady=5)
            tk.Label(row2, text="Ödeme Tarihi:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row2, text=f"📅 {odeme_tarihi.strftime('%d.%m.%Y')} (SGK ile aynı gün)",
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['warning'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

        # ==================== EMEKLİ KATILIM PAYI BÖLÜMÜ ====================
        if emekli_kp > 0:
            emk_frame = tk.Frame(container, bg=self.colors['card_bg'], bd=2, relief='solid')
            emk_frame.pack(fill=tk.X, pady=10)

            emk_header = tk.Frame(emk_frame, bg='#2e7d32', height=35)
            emk_header.pack(fill=tk.X)
            emk_header.pack_propagate(False)
            tk.Label(emk_header, text="💰 EMEKLİ KATILIM PAYI SGK'YA YAZILDI",
                    font=('Segoe UI', 12, 'bold'),
                    fg='white', bg='#2e7d32').pack(expand=True)

            emk_content = tk.Frame(emk_frame, bg=self.colors['card_bg'], padx=15, pady=15)
            emk_content.pack(fill=tk.X)

            # Tutar
            row1 = tk.Frame(emk_content, bg=self.colors['card_bg'])
            row1.pack(fill=tk.X, pady=5)
            tk.Label(row1, text="Emekli K.P. Alacağı:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row1, text=f"{emekli_kp:,.2f} TL", font=('Segoe UI', 12, 'bold'),
                    fg=self.colors['success'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

            # Vade tarihi (ayın son günü, yaklaşık 60 gün)
            vade_tarihi = (mevcut_tarih.replace(day=1) + relativedelta(months=2)) - timedelta(days=1)
            row2 = tk.Frame(emk_content, bg=self.colors['card_bg'])
            row2.pack(fill=tk.X, pady=5)
            tk.Label(row2, text="Tahsil Tarihi:", font=('Segoe UI', 11),
                    fg=self.colors['text_dim'], bg=self.colors['card_bg']).pack(side=tk.LEFT)
            tk.Label(row2, text=f"📅 {vade_tarihi.strftime('%d.%m.%Y')} (ayın son günü)",
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['warning'], bg=self.colors['card_bg']).pack(side=tk.RIGHT)

        # Bilgi notu
        bilgi_frame = tk.Frame(container, bg=self.colors['accent2'], padx=10, pady=10)
        bilgi_frame.pack(fill=tk.X, pady=15)
        tk.Label(bilgi_frame,
                text="ℹ️ Açık hesaplar kesinleşmiş hesaplara dönüştürüldü.\n" +
                     "SGK faturasından muayene borcu mahsup edilmiştir.\n" +
                     "Depo ödemesi SGK tahsilatı ile aynı gün yapılacaktır.",
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

    def _mal_bitisine_kadar_popup(self):
        """Mal bitisine kadar oynat - senaryo secim popup'i"""
        # En az bir senaryo var mi kontrol et
        if not self.senaryolar:
            messagebox.showwarning("Uyari", "Henuz bir senaryo eklenmemis!")
            return

        popup = tk.Toplevel(self.root)
        popup.title("Mal Bitisine Kadar Oynat")
        popup.configure(bg=self.colors['bg'])
        popup.transient(self.root)
        popup.grab_set()

        # Baslik
        header = tk.Frame(popup, bg='#e67e22', height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="MAL BİTİŞİNE KADAR OYNAT",
                font=('Segoe UI', 12, 'bold'), fg='white', bg='#e67e22').pack(expand=True)

        # Aciklama
        aciklama = tk.Label(popup, text="Hangi senaryonun mali bitince simülasyon dursun?\n"
                                        "(Diger senaryolar otomatik alim yapacak)",
                           font=('Segoe UI', 10), fg=self.colors['text'], bg=self.colors['bg'],
                           justify='center')
        aciklama.pack(pady=15)

        # Senaryo secim alani
        secim_frame = tk.Frame(popup, bg=self.colors['panel_bg'], bd=1, relief='solid')
        secim_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Senaryo radio butonlari
        secim_var = tk.IntVar(value=-1)  # Secili senaryo indexi

        for idx, senaryo in enumerate(self.senaryolar):
            vars = self.senaryo_vars.get(idx, {})
            isim = vars.get('isim', tk.StringVar(value=f"Senaryo {idx+1}")).get()
            stok = vars.get('baslangic_stok', tk.StringVar(value="0")).get()
            sarf = vars.get('gunluk_sarf', tk.StringVar(value="0")).get()

            row = tk.Frame(secim_frame, bg=self.colors['panel_bg'])
            row.pack(fill=tk.X, padx=10, pady=5)

            rb = tk.Radiobutton(row, text=f"{isim} (Stok: {stok}, Günlük Sarf: {sarf})",
                               variable=secim_var, value=idx,
                               font=('Segoe UI', 11), fg=self.colors['text'],
                               bg=self.colors['panel_bg'], selectcolor=self.colors['entry_bg'],
                               activebackground=self.colors['panel_bg'],
                               activeforeground=self.colors['accent'],
                               cursor='hand2')
            rb.pack(side=tk.LEFT, padx=5)

        # Butonlar
        btn_frame = tk.Frame(popup, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, pady=15)

        def baslat():
            secilen = secim_var.get()
            if secilen < 0:
                messagebox.showwarning("Uyari", "Lütfen bir senaryo seçin!")
                return

            popup.destroy()

            # Diger senaryolarin otomatik alim'ini ac
            for idx in self.senaryo_vars:
                if idx != secilen:
                    self.senaryo_vars[idx]['otomatik_alim'].set(True)
                else:
                    # Secilen senaryonun otomatik alimini kapat
                    self.senaryo_vars[idx]['otomatik_alim'].set(False)

            # Mal bitis modunu aktifle
            self.mal_bitis_senaryosu = secilen
            self.mal_bitis_modu = True

            # Simulasyonu baslat
            self._sonuna_kadar_oynat()

        baslat_btn = tk.Button(btn_frame, text="OYNAT",
                              font=('Segoe UI', 11, 'bold'),
                              bg='#00d26a', fg='white', relief='flat',
                              cursor='hand2', width=15, command=baslat)
        baslat_btn.pack(side=tk.LEFT, padx=20)

        iptal_btn = tk.Button(btn_frame, text="İptal",
                             font=('Segoe UI', 11, 'bold'),
                             bg=self.colors['danger'], fg='white', relief='flat',
                             cursor='hand2', width=15, command=popup.destroy)
        iptal_btn.pack(side=tk.RIGHT, padx=20)

        # Pencereyi ortala
        popup.update_idletasks()
        w = max(400, popup.winfo_reqwidth())
        h = popup.winfo_reqheight()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")

    def _basit_hesaplayici_ac(self):
        """Basit MF Hesaplayici penceresini ac"""
        hesap_win = tk.Toplevel(self.root)
        hesap_win.title("MF Hesaplayici - Alim Karsilastirma")
        hesap_win.geometry("900x700")
        hesap_win.configure(bg=self.colors['bg'])
        hesap_win.transient(self.root)

        # Renk paleti
        c = self.colors

        # ===== ÜST KISIM: GİRDİ PARAMETRELERİ =====
        girdi_frame = tk.LabelFrame(hesap_win, text=" Parametreler ",
                                    font=('Segoe UI', 11, 'bold'),
                                    fg=c['text'], bg=c['panel_bg'],
                                    relief='flat', bd=2)
        girdi_frame.pack(fill=tk.X, padx=10, pady=10)

        # Satir 1: Stok, Sarf, Gun
        row1 = tk.Frame(girdi_frame, bg=c['panel_bg'])
        row1.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(row1, text="Mevcut Stok:", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        stok_var = tk.StringVar(value="5")
        tk.Entry(row1, textvariable=stok_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=8).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row1, text="Aylik Sarf:", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        sarf_var = tk.StringVar(value="10")
        tk.Entry(row1, textvariable=sarf_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=8).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row1, text="Ayin Gunu:", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        gun_var = tk.StringVar(value=str(datetime.now().day))
        tk.Entry(row1, textvariable=gun_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=6).pack(side=tk.LEFT, padx=(0, 20))

        # Satir 2: Fiyat, Faiz
        row2 = tk.Frame(girdi_frame, bg=c['panel_bg'])
        row2.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(row2, text="Depocu Fiyat (TL):", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        fiyat_var = tk.StringVar(value="100")
        tk.Entry(row2, textvariable=fiyat_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=10).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row2, text="Yillik Faiz (%):", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        faiz_var = tk.StringVar(value="45")
        tk.Entry(row2, textvariable=faiz_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=8).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row2, text="SGK Vadesi (gun):", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        vade_var = tk.StringVar(value="75")
        tk.Entry(row2, textvariable=vade_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=6).pack(side=tk.LEFT)

        # Satir 3: Zam bilgileri
        row3 = tk.Frame(girdi_frame, bg=c['panel_bg'])
        row3.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(row3, text="Beklenen Zam (%):", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        zam_var = tk.StringVar(value="0")
        tk.Entry(row3, textvariable=zam_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=8).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row3, text="Zam Kac Gun Sonra:", font=('Segoe UI', 10),
                fg=c['text'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=(0, 5))
        zam_gun_var = tk.StringVar(value="30")
        tk.Entry(row3, textvariable=zam_gun_var, font=('Segoe UI', 10),
                bg=c['entry_bg'], fg=c['text'], relief='flat', width=6).pack(side=tk.LEFT)

        # ===== ORTA KISIM: MF ŞARTLARI =====
        mf_frame = tk.LabelFrame(hesap_win, text=" MF Sartlari (Al + Bedava) ",
                                font=('Segoe UI', 11, 'bold'),
                                fg=c['text'], bg=c['panel_bg'],
                                relief='flat', bd=2)
        mf_frame.pack(fill=tk.X, padx=10, pady=5)

        mf_inner = tk.Frame(mf_frame, bg=c['panel_bg'])
        mf_inner.pack(fill=tk.X, padx=10, pady=8)

        # Varsayilan MF sartlari
        varsayilan_mf = [
            (1, 0), (5, 1), (10, 3), (20, 7), (50, 25), (100, 60)
        ]

        mf_vars = []  # [(al_var, bedava_var), ...]

        for i, (al, bedava) in enumerate(varsayilan_mf):
            frame = tk.Frame(mf_inner, bg=c['panel_bg'])
            frame.pack(side=tk.LEFT, padx=10)

            al_var = tk.StringVar(value=str(al))
            bedava_var = tk.StringVar(value=str(bedava))

            tk.Entry(frame, textvariable=al_var, font=('Segoe UI', 9),
                    bg=c['entry_bg'], fg=c['text'], relief='flat',
                    width=4, justify='center').pack(side=tk.LEFT)
            tk.Label(frame, text="+", font=('Segoe UI', 10, 'bold'),
                    fg=c['accent'], bg=c['panel_bg']).pack(side=tk.LEFT, padx=2)
            tk.Entry(frame, textvariable=bedava_var, font=('Segoe UI', 9),
                    bg=c['entry_bg'], fg=c['text'], relief='flat',
                    width=4, justify='center').pack(side=tk.LEFT)

            mf_vars.append((al_var, bedava_var))

        # ===== HESAPLA BUTONU =====
        btn_frame = tk.Frame(hesap_win, bg=c['bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def hesapla():
            try:
                # Parametreleri al
                mevcut_stok = int(stok_var.get())
                aylik_sarf = float(sarf_var.get())
                ayin_gunu = int(gun_var.get())
                depocu_fiyat = float(fiyat_var.get().replace(',', '.'))
                yillik_faiz = float(faiz_var.get().replace(',', '.')) / 100
                sgk_vade_gun = int(vade_var.get())
                zam_orani = float(zam_var.get().replace(',', '.')) / 100
                zam_gun_sonra = int(zam_gun_var.get())

                aylik_faiz = yillik_faiz / 12
                gunluk_sarf = aylik_sarf / 30

                # Zam kac ay sonra
                zam_ay_sonra = zam_gun_sonra / 30 if zam_gun_sonra > 0 else 999

                # Sonuc tablosunu temizle
                for item in sonuc_tree.get_children():
                    sonuc_tree.delete(item)

                en_karli = None
                en_karli_net = float('-inf')
                sonuclar = []

                for al_var, bedava_var in mf_vars:
                    try:
                        al = int(al_var.get())
                        bedava = int(bedava_var.get())
                    except:
                        continue

                    if al <= 0:
                        continue

                    toplam_gelen = al + bedava
                    yeni_stok = mevcut_stok + toplam_gelen
                    odenen_para = al * depocu_fiyat
                    birim_maliyet = odenen_para / toplam_gelen

                    # Stok kac ay yeter
                    stok_ay = (yeni_stok / aylik_sarf) if aylik_sarf > 0 else 999
                    toplam_ay = int(stok_ay) + (1 if stok_ay % 1 > 0 else 0)  # Yukarı yuvarla

                    # MF oranı
                    mf_oran = (bedava / toplam_gelen) * 100 if toplam_gelen > 0 else 0

                    # ===== NPV HESAPLAMASI =====
                    # Senaryo A: MF'siz - her ay ihtiyac kadar al
                    # Senaryo B: MF'li - bugun toplu al
                    # Kazanc = NPV_A - NPV_B

                    # Senaryo A: Her ay aylik_sarf kadar al (toplam_ay boyunca)
                    npv_mfsiz = 0
                    kalan_ihtiyac = yeni_stok  # MF'li senaryodaki toplam stok kadar ihtiyac
                    for ay in range(toplam_ay):
                        # Bu ay ne kadar alinacak
                        bu_ay_alim = min(aylik_sarf, kalan_ihtiyac)
                        if bu_ay_alim <= 0:
                            break

                        # Zam sonrasi mi?
                        if zam_orani > 0 and ay >= zam_ay_sonra:
                            fiyat = depocu_fiyat * (1 + zam_orani)
                        else:
                            fiyat = depocu_fiyat

                        # Bu ayki odemenin bugunku degeri
                        odeme = bu_ay_alim * fiyat
                        iskonto_faktor = (1 + aylik_faiz) ** ay
                        npv_mfsiz += odeme / iskonto_faktor

                        kalan_ihtiyac -= bu_ay_alim

                    # Senaryo B: Bugun toplu odeme (MF'li)
                    npv_mfli = odenen_para  # Bugun odeniyor, iskonto yok

                    # Net kazanc = MF'siz maliyet - MF'li maliyet
                    net_kazanc = npv_mfsiz - npv_mfli

                    # Sonuclari kaydet
                    sonuclar.append({
                        'sart': f"{al}+{bedava}",
                        'birim': birim_maliyet,
                        'mf_oran': mf_oran,
                        'stok_ay': stok_ay,
                        'npv_mfsiz': npv_mfsiz,
                        'npv_mfli': npv_mfli,
                        'net': net_kazanc
                    })

                    if net_kazanc > en_karli_net:
                        en_karli_net = net_kazanc
                        en_karli = f"{al}+{bedava}"

                # Tabloya ekle
                for s in sonuclar:
                    tag = 'karli' if s['sart'] == en_karli else ''
                    if s['net'] < 0:
                        tag = 'zarali'

                    sonuc_tree.insert('', 'end', values=(
                        s['sart'],
                        f"{s['birim']:.2f} TL",
                        f"%{s['mf_oran']:.1f}",
                        f"{s['stok_ay']:.1f} ay",
                        f"{s['npv_mfsiz']:.2f} TL",
                        f"{s['npv_mfli']:.2f} TL",
                        f"{s['net']:+.2f} TL"
                    ), tags=(tag,))

                # En karli etiketi guncelle
                if en_karli:
                    if en_karli_net > 0:
                        en_karli_label.config(
                            text=f"EN KARLI: {en_karli} → {en_karli_net:+.2f} TL",
                            fg=c['success'])
                    elif en_karli_net < 0:
                        en_karli_label.config(
                            text=f"EN AZ ZARARLI: {en_karli} → {en_karli_net:+.2f} TL",
                            fg=c['warning'])
                    else:
                        en_karli_label.config(
                            text=f"NÖTR: {en_karli} → 0 TL",
                            fg=c['text'])
                else:
                    en_karli_label.config(text="", fg=c['text'])

            except Exception as e:
                messagebox.showerror("Hata", f"Hesaplama hatasi: {e}")

        tk.Button(btn_frame, text="HESAPLA", font=('Segoe UI', 12, 'bold'),
                 bg=c['success'], fg='white', relief='flat', cursor='hand2',
                 width=15, command=hesapla).pack(pady=5)

        # ===== ALT KISIM: SONUÇ TABLOSU =====
        sonuc_frame = tk.LabelFrame(hesap_win, text=" Sonuclar ",
                                    font=('Segoe UI', 11, 'bold'),
                                    fg=c['text'], bg=c['panel_bg'],
                                    relief='flat', bd=2)
        sonuc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Treeview
        columns = ('sart', 'birim', 'mf_oran', 'stok', 'npv_mfsiz', 'npv_mfli', 'net')
        sonuc_tree = ttk.Treeview(sonuc_frame, columns=columns, show='headings', height=8)

        sonuc_tree.heading('sart', text='Alim Sarti')
        sonuc_tree.heading('birim', text='Birim Maliyet')
        sonuc_tree.heading('mf_oran', text='MF Orani')
        sonuc_tree.heading('stok', text='Stok Suresi')
        sonuc_tree.heading('npv_mfsiz', text="MF'siz Maliyet")
        sonuc_tree.heading('npv_mfli', text="MF'li Maliyet")
        sonuc_tree.heading('net', text='NET KAZANC')

        sonuc_tree.column('sart', width=80, anchor='center')
        sonuc_tree.column('birim', width=100, anchor='center')
        sonuc_tree.column('mf_oran', width=80, anchor='center')
        sonuc_tree.column('stok', width=80, anchor='center')
        sonuc_tree.column('npv_mfsiz', width=110, anchor='center')
        sonuc_tree.column('npv_mfli', width=110, anchor='center')
        sonuc_tree.column('net', width=110, anchor='center')

        # Tag renkleri
        sonuc_tree.tag_configure('karli', background='#1a472a', foreground='#4ade80')
        sonuc_tree.tag_configure('zarali', background='#4a1a1a', foreground='#f87171')

        sonuc_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # En karli etiketi
        en_karli_label = tk.Label(sonuc_frame, text="", font=('Segoe UI', 14, 'bold'),
                                 fg=c['success'], bg=c['panel_bg'])
        en_karli_label.pack(pady=10)

        # ===== AÇIKLAMA =====
        aciklama_frame = tk.Frame(hesap_win, bg=c['bg'])
        aciklama_frame.pack(fill=tk.X, padx=10, pady=5)

        aciklama = """Hesaplama Mantigi (NPV - Net Bugunku Deger):
• MF'siz Maliyet = Her ay ayri alim yapilsa odenecek toplam paranin bugunku degeri
• MF'li Maliyet = Bugun toplu odenen tutar (iskonto yok)
• NET KAZANC = MF'siz Maliyet - MF'li Maliyet
• Zam varsa: MF'siz senaryoda zam sonrasi fiyat artar, MF'li senaryoda etkilenmez"""

        tk.Label(aciklama_frame, text=aciklama, font=('Segoe UI', 9),
                fg=c['text_dim'], bg=c['bg'], justify='left').pack(anchor='w')

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
