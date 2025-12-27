#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MF Analiz GUI - Nakit Fiyat Simulasyon Modulu
Detayli stok, kasa, borc ve alacak simulasyonu
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import threading
import time


class MFAnalizGUI:
    """MF Analiz ana penceresi"""

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

        self.root.title("MF Analiz - Nakit Fiyat Simulasyonu")
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
            'header_a': '#e94560',
            'header_b': '#00d26a',
            'header_c': '#ffc107',
            'header_d': '#17a2b8',
            'header_e': '#9b59b6',
        }

        self.root.configure(bg=self.colors['bg'])

        # Simulasyon degiskenleri
        self.simulasyon_calisyor = False
        self.simulasyon_thread = None
        self.mevcut_gun = 0
        self.simulasyon_durumu = {}  # Guncel simulasyon state'i

        # Veri degiskenleri - A) Ilacin Eczanedeki Durumu
        self.stok_durumu_var = tk.StringVar(value="100")
        self.aylik_sarf_var = tk.StringVar(value="30")
        self.bugun_tarihi_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))

        # B) Ilacla Alakali Veriler
        self.depocu_fiyat_var = tk.StringVar(value="100.00")
        self.kamu_fiyat_var = tk.StringVar(value="120.00")
        self.piyasa_satis_fiyat_var = tk.StringVar(value="150.00")

        # C) Satin Alma Verileri
        self.satin_alma_sarti_var = tk.StringVar(value="Pesin")
        self.alinma_tarihi_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
        self.vade_var = tk.StringVar(value="30")

        # D) Dis Etkenler
        self.zam_tarihi_var = tk.StringVar(value="")
        self.zam_orani_var = tk.StringVar(value="0")
        self.mevduat_faizi_var = tk.StringVar(value="0.15")
        self.kredi_faizi_var = tk.StringVar(value="0.20")

        # E) Eczane Profili
        self.nakit_sgk_orani_var = tk.StringVar(value="30/70")
        self.nakit_pos_orani_var = tk.StringVar(value="50/50")
        self.calisan_emekli_orani_var = tk.StringVar(value="60/40")

        # Simulasyon hizi ve gun sayisi
        self.simulasyon_hizi_var = tk.StringVar(value="100")
        self.gun_sayisi_var = tk.StringVar(value="30")

        self._arayuz_olustur()

    def _arayuz_olustur(self):
        """Ana arayuzu olustur"""
        # Ana container
        self.main_container = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Baslik
        self._baslik_olustur()

        # Ust panel - Veri girisi alanlari
        self._ust_panel_olustur()

        # Kontrol paneli
        self._kontrol_paneli_olustur()

        # Alt panel - Data Grid
        self._alt_panel_olustur()

    def _baslik_olustur(self):
        """Baslik alani"""
        baslik_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        baslik_frame.pack(fill=tk.X, pady=(0, 10))

        baslik = tk.Label(
            baslik_frame,
            text="MF ANALIZ - NAKIT FIYAT SIMULASYONU",
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg']
        )
        baslik.pack()

    def _ust_panel_olustur(self):
        """Ust veri girisi paneli - 5 bolum yan yana"""
        ust_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        ust_frame.pack(fill=tk.X, pady=(0, 10))

        # 5 sutun esit genislikte
        for i in range(5):
            ust_frame.columnconfigure(i, weight=1)

        # A) Ilacin Eczanedeki Durumu
        self._panel_a_olustur(ust_frame, 0)

        # B) Ilacla Alakali Veriler
        self._panel_b_olustur(ust_frame, 1)

        # C) Satin Alma Verileri
        self._panel_c_olustur(ust_frame, 2)

        # D) Dis Etkenler
        self._panel_d_olustur(ust_frame, 3)

        # E) Eczane Profili
        self._panel_e_olustur(ust_frame, 4)

    def _kart_olustur(self, parent, col, baslik, header_color):
        """Tek bir kart olustur"""
        kart = tk.Frame(parent, bg=self.colors['card_bg'], bd=1, relief='solid')
        kart.grid(row=0, column=col, sticky='nsew', padx=5, pady=5)

        # Baslik
        header = tk.Frame(kart, bg=header_color, height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        header_label = tk.Label(
            header,
            text=baslik,
            font=('Segoe UI', 10, 'bold'),
            fg='white',
            bg=header_color
        )
        header_label.pack(expand=True)

        # Icerik
        content = tk.Frame(kart, bg=self.colors['card_bg'], padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        return content

    def _entry_satiri(self, parent, label_text, variable, row):
        """Etiketli entry satiri olustur"""
        frame = tk.Frame(parent, bg=self.colors['card_bg'])
        frame.pack(fill=tk.X, pady=3)

        label = tk.Label(
            frame,
            text=label_text,
            font=('Segoe UI', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['card_bg'],
            anchor='w',
            width=18
        )
        label.pack(side=tk.LEFT)

        entry = tk.Entry(
            frame,
            textvariable=variable,
            font=('Segoe UI', 10),
            bg=self.colors['entry_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief='flat',
            width=12,
            justify='center'
        )
        entry.pack(side=tk.RIGHT, padx=(5, 0))

        return entry

    def _combo_satiri(self, parent, label_text, variable, values, row):
        """Etiketli combobox satiri olustur"""
        frame = tk.Frame(parent, bg=self.colors['card_bg'])
        frame.pack(fill=tk.X, pady=3)

        label = tk.Label(
            frame,
            text=label_text,
            font=('Segoe UI', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['card_bg'],
            anchor='w',
            width=18
        )
        label.pack(side=tk.LEFT)

        # ttk Combobox icin stil
        style = ttk.Style()
        style.configure('Dark.TCombobox',
                       fieldbackground=self.colors['entry_bg'],
                       background=self.colors['entry_bg'])

        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            font=('Segoe UI', 9),
            width=10,
            state='readonly'
        )
        combo.pack(side=tk.RIGHT, padx=(5, 0))

        return combo

    def _panel_a_olustur(self, parent, col):
        """A) Ilacin Eczanedeki Durumu"""
        content = self._kart_olustur(parent, col, "A) ECZANE DURUMU", self.colors['header_a'])

        self._entry_satiri(content, "Stok Durumu:", self.stok_durumu_var, 0)
        self._entry_satiri(content, "Aylik Sarf:", self.aylik_sarf_var, 1)
        self._entry_satiri(content, "Bugun Tarihi:", self.bugun_tarihi_var, 2)

    def _panel_b_olustur(self, parent, col):
        """B) Ilacla Alakali Veriler"""
        content = self._kart_olustur(parent, col, "B) ILAC VERILERI", self.colors['header_b'])

        self._entry_satiri(content, "Depocu Fiyati:", self.depocu_fiyat_var, 0)
        self._entry_satiri(content, "Kamu Fiyati:", self.kamu_fiyat_var, 1)
        self._entry_satiri(content, "Piyasa Satis Fiyati:", self.piyasa_satis_fiyat_var, 2)

    def _panel_c_olustur(self, parent, col):
        """C) Satin Alma Verileri"""
        content = self._kart_olustur(parent, col, "C) SATIN ALMA", self.colors['header_c'])

        self._combo_satiri(content, "Satin Alma Sarti:", self.satin_alma_sarti_var,
                          ["Pesin", "Vadeli", "Konsiye"], 0)
        self._entry_satiri(content, "Alinma Tarihi:", self.alinma_tarihi_var, 1)
        self._entry_satiri(content, "Vade (Gun):", self.vade_var, 2)

    def _panel_d_olustur(self, parent, col):
        """D) Dis Etkenler"""
        content = self._kart_olustur(parent, col, "D) DIS ETKENLER", self.colors['header_d'])

        self._entry_satiri(content, "Zam Tarihi:", self.zam_tarihi_var, 0)
        self._entry_satiri(content, "Zam Orani (%):", self.zam_orani_var, 1)
        self._entry_satiri(content, "Mevduat Faizi (%):", self.mevduat_faizi_var, 2)
        self._entry_satiri(content, "Kredi Faizi (%):", self.kredi_faizi_var, 3)

    def _panel_e_olustur(self, parent, col):
        """E) Eczane Profili"""
        content = self._kart_olustur(parent, col, "E) ECZANE PROFILI", self.colors['header_e'])

        self._entry_satiri(content, "Nakit/SGK Orani:", self.nakit_sgk_orani_var, 0)
        self._entry_satiri(content, "Nakit/POS Orani:", self.nakit_pos_orani_var, 1)
        self._entry_satiri(content, "Calisan/Emekli:", self.calisan_emekli_orani_var, 2)

    def _kontrol_paneli_olustur(self):
        """Kontrol butonlari"""
        kontrol_frame = tk.Frame(self.main_container, bg=self.colors['panel_bg'], pady=10)
        kontrol_frame.pack(fill=tk.X, pady=(0, 10))

        # Ust satir - Oynatma butonlari
        ust_inner = tk.Frame(kontrol_frame, bg=self.colors['panel_bg'])
        ust_inner.pack(pady=(0, 10))

        # ADIM ADIM butonu (1 gun ilerle)
        self.adim_btn = tk.Button(
            ust_inner,
            text="ADIM (1 Gun)",
            font=('Segoe UI', 11, 'bold'),
            bg='#6366f1',
            fg='white',
            activebackground='#4f46e5',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            width=14,
            command=self._adim_adim_oynat
        )
        self.adim_btn.pack(side=tk.LEFT, padx=10)

        # X GUN OYNAT
        gun_frame = tk.Frame(ust_inner, bg=self.colors['panel_bg'])
        gun_frame.pack(side=tk.LEFT, padx=10)

        gun_entry = tk.Entry(
            gun_frame,
            textvariable=self.gun_sayisi_var,
            font=('Segoe UI', 11),
            bg=self.colors['entry_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief='flat',
            width=5,
            justify='center'
        )
        gun_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.x_gun_btn = tk.Button(
            gun_frame,
            text="Gun Oynat",
            font=('Segoe UI', 11, 'bold'),
            bg='#8b5cf6',
            fg='white',
            activebackground='#7c3aed',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            width=10,
            command=self._x_gun_oynat
        )
        self.x_gun_btn.pack(side=tk.LEFT)

        # SONUNA KADAR butonu
        self.sonuna_btn = tk.Button(
            ust_inner,
            text="SONUNA KADAR",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['success'],
            fg='white',
            activebackground='#00b359',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            width=14,
            command=self._sonuna_kadar_oynat
        )
        self.sonuna_btn.pack(side=tk.LEFT, padx=10)

        # DURDUR butonu (animasyonlu oynatma icin)
        self.durdur_btn = tk.Button(
            ust_inner,
            text="DURDUR",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['danger'],
            fg='white',
            activebackground='#ff5252',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            width=10,
            command=self._durdur,
            state='disabled'
        )
        self.durdur_btn.pack(side=tk.LEFT, padx=10)

        # Alt satir - Hiz ve diger kontroller
        alt_inner = tk.Frame(kontrol_frame, bg=self.colors['panel_bg'])
        alt_inner.pack()

        # Simulasyon hizi
        hiz_label = tk.Label(
            alt_inner,
            text="Animasyon Hizi (ms):",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['panel_bg']
        )
        hiz_label.pack(side=tk.LEFT, padx=(0, 5))

        hiz_entry = tk.Entry(
            alt_inner,
            textvariable=self.simulasyon_hizi_var,
            font=('Segoe UI', 10),
            bg=self.colors['entry_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief='flat',
            width=6,
            justify='center'
        )
        hiz_entry.pack(side=tk.LEFT, padx=(0, 30))

        # Mevcut gun gosterimi
        gun_durum_label = tk.Label(
            alt_inner,
            text="Mevcut Gun:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['panel_bg']
        )
        gun_durum_label.pack(side=tk.LEFT, padx=(0, 5))

        self.mevcut_gun_label = tk.Label(
            alt_inner,
            text="0",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['panel_bg'],
            width=5
        )
        self.mevcut_gun_label.pack(side=tk.LEFT, padx=(0, 30))

        # SIFIRLA butonu
        self.sifirla_btn = tk.Button(
            alt_inner,
            text="SIFIRLA",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['warning'],
            fg='black',
            activebackground='#e6ac00',
            activeforeground='black',
            relief='flat',
            cursor='hand2',
            width=10,
            command=self._sifirla
        )
        self.sifirla_btn.pack(side=tk.LEFT, padx=10)

        # TABLOYU TEMIZLE butonu
        self.temizle_btn = tk.Button(
            alt_inner,
            text="TABLOYU TEMIZLE",
            font=('Segoe UI', 10, 'bold'),
            bg='#64748b',
            fg='white',
            activebackground='#475569',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            width=14,
            command=self._tabloyu_temizle
        )
        self.temizle_btn.pack(side=tk.LEFT, padx=10)

    def _alt_panel_olustur(self):
        """Alt panel - Data Grid"""
        alt_frame = tk.LabelFrame(
            self.main_container,
            text=" SIMULASYON SONUCLARI ",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['panel_bg'],
            bd=2
        )
        alt_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview icin stil
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Dark.Treeview',
                       background=self.colors['entry_bg'],
                       foreground=self.colors['text'],
                       fieldbackground=self.colors['entry_bg'],
                       rowheight=25)

        style.configure('Dark.Treeview.Heading',
                       background=self.colors['accent2'],
                       foreground='white',
                       font=('Segoe UI', 9, 'bold'))

        style.map('Dark.Treeview',
                 background=[('selected', self.colors['accent'])])

        # Treeview ve scrollbar container
        tree_container = tk.Frame(alt_frame, bg=self.colors['panel_bg'])
        tree_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Kolonlar
        columns = (
            'gun', 'tarih', 'stok', 'nakit_satis', 'sgk_satis',
            'kasa_nakit', 'kasa_pos', 'depoya_borc', 'sgk_alacak',
            'faiz_gelir', 'faiz_gider', 'net_durum'
        )

        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show='headings',
            style='Dark.Treeview'
        )

        # Kolon basliklari ve genislikleri
        headers = {
            'gun': ('Gun', 50),
            'tarih': ('Tarih', 90),
            'stok': ('Stok', 60),
            'nakit_satis': ('Nakit Satis', 90),
            'sgk_satis': ('SGK Satis', 90),
            'kasa_nakit': ('Kasa Nakit', 100),
            'kasa_pos': ('Kasa POS', 90),
            'depoya_borc': ('Depoya Borc', 100),
            'sgk_alacak': ('SGK Alacak', 100),
            'faiz_gelir': ('Faiz Gelir', 90),
            'faiz_gider': ('Faiz Gider', 90),
            'net_durum': ('Net Durum', 100)
        }

        for col, (header, width) in headers.items():
            self.tree.heading(col, text=header)
            self.tree.column(col, width=width, anchor='center')

        # Scrollbar
        scrollbar_y = ttk.Scrollbar(tree_container, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_container, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Grid yerlesimi
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')

        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

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

    def _simulasyon_baslat(self):
        """Simulasyon state'ini baslat veya devam ettir"""
        if not self.simulasyon_durumu:
            # Ilk kez baslatiliyor
            try:
                stok = float(self.stok_durumu_var.get())
                aylik_sarf = float(self.aylik_sarf_var.get())
                depocu_fiyat = float(self.depocu_fiyat_var.get())
                kamu_fiyat = float(self.kamu_fiyat_var.get())
                piyasa_fiyat = float(self.piyasa_satis_fiyat_var.get())
                vade = int(self.vade_var.get())
                satin_alma_sarti = self.satin_alma_sarti_var.get()
                mevduat_faizi = float(self.mevduat_faizi_var.get()) / 100
                kredi_faizi = float(self.kredi_faizi_var.get()) / 100
                zam_orani = float(self.zam_orani_var.get()) / 100

                zam_tarihi = None
                if self.zam_tarihi_var.get().strip():
                    try:
                        zam_tarihi = datetime.strptime(self.zam_tarihi_var.get(), "%d.%m.%Y")
                    except:
                        pass

                nakit_oran, sgk_oran = self._oran_parse(self.nakit_sgk_orani_var.get())
                nakit_pos_nakit, nakit_pos_pos = self._oran_parse(self.nakit_pos_orani_var.get())

                try:
                    baslangic_tarihi = datetime.strptime(self.bugun_tarihi_var.get(), "%d.%m.%Y")
                except:
                    baslangic_tarihi = datetime.now()

                try:
                    alinma_tarihi = datetime.strptime(self.alinma_tarihi_var.get(), "%d.%m.%Y")
                except:
                    alinma_tarihi = baslangic_tarihi

                baslangic_stok = stok

                self.simulasyon_durumu = {
                    'stok': stok,
                    'baslangic_stok': baslangic_stok,
                    'aylik_sarf': aylik_sarf,
                    'gunluk_sarf': aylik_sarf / 30,
                    'depocu_fiyat': depocu_fiyat,
                    'kamu_fiyat': kamu_fiyat,
                    'piyasa_fiyat': piyasa_fiyat,
                    'vade': vade,
                    'satin_alma_sarti': satin_alma_sarti,
                    'mevduat_faizi': mevduat_faizi,
                    'kredi_faizi': kredi_faizi,
                    'zam_orani': zam_orani,
                    'zam_tarihi': zam_tarihi,
                    'nakit_oran': nakit_oran,
                    'sgk_oran': sgk_oran,
                    'nakit_pos_nakit': nakit_pos_nakit,
                    'nakit_pos_pos': nakit_pos_pos,
                    'baslangic_tarihi': baslangic_tarihi,
                    'alinma_tarihi': alinma_tarihi,
                    'kasa_nakit': 0,
                    'kasa_pos': 0,
                    'depoya_borc': baslangic_stok * depocu_fiyat if satin_alma_sarti == "Vadeli" else 0,
                    'sgk_alacak': 0,
                    'toplam_faiz_gelir': 0,
                    'toplam_faiz_gider': 0,
                }
                self.mevcut_gun = 0
                return True

            except ValueError as e:
                messagebox.showerror("Hata", f"Gecersiz deger: {e}")
                return False
        return True

    def _bir_gun_hesapla(self):
        """Tek bir gun hesapla ve tabloya ekle. Stok bittiyse False doner."""
        d = self.simulasyon_durumu
        if not d or d['stok'] <= 0:
            return False

        self.mevcut_gun += 1
        mevcut_tarih = d['baslangic_tarihi'] + timedelta(days=self.mevcut_gun - 1)

        # Zam kontrolu
        if d['zam_tarihi'] and mevcut_tarih >= d['zam_tarihi']:
            d['kamu_fiyat'] = d['kamu_fiyat'] * (1 + d['zam_orani'])
            d['piyasa_fiyat'] = d['piyasa_fiyat'] * (1 + d['zam_orani'])
            d['zam_tarihi'] = None

        # Gunluk satis
        satis_miktari = min(d['gunluk_sarf'], d['stok'])
        d['stok'] -= satis_miktari

        # Satis geliri dagilimlari
        nakit_satis_tutar = satis_miktari * d['piyasa_fiyat'] * d['nakit_oran']
        sgk_satis_tutar = satis_miktari * d['kamu_fiyat'] * d['sgk_oran']

        # Nakit satisin nakit/pos dagilimi
        d['kasa_nakit'] += nakit_satis_tutar * d['nakit_pos_nakit']
        d['kasa_pos'] += nakit_satis_tutar * d['nakit_pos_pos']

        # SGK alacak
        d['sgk_alacak'] += sgk_satis_tutar

        # Vade kontrolu - borc odeme
        vade_doldu = (mevcut_tarih - d['alinma_tarihi']).days >= d['vade']
        if vade_doldu and d['depoya_borc'] > 0:
            odeme = min(d['depoya_borc'], d['kasa_nakit'])
            d['kasa_nakit'] -= odeme
            d['depoya_borc'] -= odeme

        # Faiz hesaplari
        faiz_gelir = (d['kasa_nakit'] + d['kasa_pos']) * d['mevduat_faizi'] / 365
        faiz_gider = d['depoya_borc'] * d['kredi_faizi'] / 365
        d['toplam_faiz_gelir'] += faiz_gelir
        d['toplam_faiz_gider'] += faiz_gider

        # Net durum
        net_durum = (d['kasa_nakit'] + d['kasa_pos'] + d['sgk_alacak'] -
                     d['depoya_borc'] + d['toplam_faiz_gelir'] - d['toplam_faiz_gider'])

        # Tabloya ekle
        self._satir_ekle(
            self.mevcut_gun,
            mevcut_tarih.strftime("%d.%m.%Y"),
            f"{d['stok']:.1f}",
            f"{nakit_satis_tutar:.2f}",
            f"{sgk_satis_tutar:.2f}",
            f"{d['kasa_nakit']:.2f}",
            f"{d['kasa_pos']:.2f}",
            f"{d['depoya_borc']:.2f}",
            f"{d['sgk_alacak']:.2f}",
            f"{d['toplam_faiz_gelir']:.2f}",
            f"{d['toplam_faiz_gider']:.2f}",
            f"{net_durum:.2f}"
        )

        # Gun label guncelle
        self.mevcut_gun_label.config(text=str(self.mevcut_gun))

        return d['stok'] > 0

    def _adim_adim_oynat(self):
        """Tek gun ilerle"""
        if not self._simulasyon_baslat():
            return

        if not self._bir_gun_hesapla():
            messagebox.showinfo("Bilgi", "Stok bitti!")

    def _x_gun_oynat(self):
        """Belirtilen gun kadar ilerle (animasyonlu)"""
        if not self._simulasyon_baslat():
            return

        try:
            gun_sayisi = int(self.gun_sayisi_var.get())
        except:
            messagebox.showerror("Hata", "Gecersiz gun sayisi!")
            return

        if gun_sayisi <= 0:
            return

        self.simulasyon_calisyor = True
        self._butonlari_devre_disi(True)
        self.simulasyon_thread = threading.Thread(
            target=self._x_gun_oynat_thread,
            args=(gun_sayisi,),
            daemon=True
        )
        self.simulasyon_thread.start()

    def _x_gun_oynat_thread(self, gun_sayisi):
        """X gun oynat thread fonksiyonu"""
        try:
            hiz = int(self.simulasyon_hizi_var.get())
        except:
            hiz = 100

        for i in range(gun_sayisi):
            if not self.simulasyon_calisyor:
                break

            devam = self.root.after(0, self._bir_gun_hesapla)
            # Thread-safe bir sekilde hesapla
            if self.simulasyon_durumu.get('stok', 0) <= 0:
                self.root.after(0, lambda: messagebox.showinfo("Bilgi", "Stok bitti!"))
                break

            time.sleep(hiz / 1000)

        self.root.after(0, lambda: self._butonlari_devre_disi(False))
        self.simulasyon_calisyor = False

    def _sonuna_kadar_oynat(self):
        """Stok bitene kadar oynat (animasyonlu)"""
        if not self._simulasyon_baslat():
            return

        self.simulasyon_calisyor = True
        self._butonlari_devre_disi(True)
        self.simulasyon_thread = threading.Thread(
            target=self._sonuna_kadar_thread,
            daemon=True
        )
        self.simulasyon_thread.start()

    def _sonuna_kadar_thread(self):
        """Sonuna kadar oynat thread fonksiyonu"""
        try:
            hiz = int(self.simulasyon_hizi_var.get())
        except:
            hiz = 100

        while self.simulasyon_calisyor and self.simulasyon_durumu.get('stok', 0) > 0:
            self.root.after(0, self._bir_gun_hesapla)
            time.sleep(hiz / 1000)

        self.root.after(0, lambda: self._butonlari_devre_disi(False))
        self.root.after(0, lambda: messagebox.showinfo("Bilgi", "Simulasyon tamamlandi!"))
        self.simulasyon_calisyor = False

    def _durdur(self):
        """Animasyonlu oynatmayi durdur"""
        self.simulasyon_calisyor = False

    def _butonlari_devre_disi(self, devre_disi):
        """Butonlari etkinlestir/devre disi birak"""
        durum = 'disabled' if devre_disi else 'normal'
        self.adim_btn.config(state=durum)
        self.x_gun_btn.config(state=durum)
        self.sonuna_btn.config(state=durum)
        self.sifirla_btn.config(state=durum)
        self.temizle_btn.config(state=durum)
        self.durdur_btn.config(state='normal' if devre_disi else 'disabled')

    def _satir_ekle(self, gun, tarih, stok, nakit_satis, sgk_satis,
                    kasa_nakit, kasa_pos, depoya_borc, sgk_alacak,
                    faiz_gelir, faiz_gider, net_durum):
        """Tabloya satir ekle"""
        self.tree.insert('', 'end', values=(
            gun, tarih, stok, nakit_satis, sgk_satis,
            kasa_nakit, kasa_pos, depoya_borc, sgk_alacak,
            faiz_gelir, faiz_gider, net_durum
        ))
        # En son satira scroll
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def _sifirla(self):
        """Tum degerleri varsayilana sifirla"""
        self.simulasyon_calisyor = False
        self.simulasyon_durumu = {}
        self.mevcut_gun = 0
        self.mevcut_gun_label.config(text="0")

        # A) Eczane Durumu
        self.stok_durumu_var.set("100")
        self.aylik_sarf_var.set("30")
        self.bugun_tarihi_var.set(datetime.now().strftime("%d.%m.%Y"))

        # B) Ilac Verileri
        self.depocu_fiyat_var.set("100.00")
        self.kamu_fiyat_var.set("120.00")
        self.piyasa_satis_fiyat_var.set("150.00")

        # C) Satin Alma
        self.satin_alma_sarti_var.set("Pesin")
        self.alinma_tarihi_var.set(datetime.now().strftime("%d.%m.%Y"))
        self.vade_var.set("30")

        # D) Dis Etkenler
        self.zam_tarihi_var.set("")
        self.zam_orani_var.set("0")
        self.mevduat_faizi_var.set("0.15")
        self.kredi_faizi_var.set("0.20")

        # E) Eczane Profili
        self.nakit_sgk_orani_var.set("30/70")
        self.nakit_pos_orani_var.set("50/50")
        self.calisan_emekli_orani_var.set("60/40")

    def _tabloyu_temizle(self):
        """Tablo verilerini temizle ve simulasyonu sifirla"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.simulasyon_durumu = {}
        self.mevcut_gun = 0
        self.mevcut_gun_label.config(text="0")

    def run(self):
        """Uygulamayi calistir"""
        if self.standalone:
            self.root.mainloop()


# Geriye uyumluluk icin alias
NFAnalizGUI = MFAnalizGUI


def main():
    """Ana fonksiyon"""
    app = MFAnalizGUI()
    app.run()


if __name__ == "__main__":
    main()
