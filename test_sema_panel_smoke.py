# -*- coding: utf-8 -*-
"""Atomik şema paneli smoke testi.

Mock satır dict (verdict_sartlar JSON dahil) üretir, paneli render eder,
kullanıcı pencerede görsel doğrulama yapar.
"""
import sys
import json
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, '.')
from recete_kontrol import sut_kontrolleri as sk

# ── Mock reçete: AF + 78 yaş + SK + varfarin altı SVO → UYGUN ──
ilac_sonuc = {
    'ilac_adi': 'XARELTO 20 MG',
    'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': [
        'Atriyal fibrilasyon tanısı, 78 yaşındadır, sağlık kurulu raporu — '
        'kardiyoloji + iç hastalıkları + nöroloji uzmanları onaylamıştır. '
        'Varfarin tedavisi altında iken serebrovasküler olay geçirmiştir.'
    ],
    'recete_teshisleri': ['I48 ATRIYAL FIBRILASYON'],
    'hasta_yasi': 78,
    'recete_ilaclari': [],
    'doktor_uzmanligi': 'KARDİYOLOJİ',
}
rapor = sk.kontrol_yoak(ilac_sonuc)

# Mock satır
satir = {
    'ri_id': 'TEST_001',
    'ilac': 'XARELTO 20 MG',
    'verdict': 'UYGUN' if rapor.sonuc.value == 'uygun' else
               'UYGUN DEĞİL' if rapor.sonuc.value == 'uygun_degil' else
               'ŞÜPHELİ',
    'verdict_sartlar': json.dumps([
        {'ad': p.ad,
         'durum': p.durum.value,
         'neden': p.neden,
         'kaynak': p.kaynak,
         'grup': p.grup,
         'veya_grubu': p.veya_grubu}
        for p in rapor.sartlar
    ], ensure_ascii=False),
    'verdict_sut': rapor.sut_kurali or '',
    'verdict_detaylar': json.dumps(rapor.detaylar or {}, ensure_ascii=False),
}

# ── Test penceresi ──
root = tk.Tk()
root.title('Atomik Şart Paneli — Yatay Devre Şeması (D-1 AF)')
root.geometry('1500x420')

# Sahte AylikReceteSorguGUI sınıfından sadece sema panel methodlarını test edelim
from aylik_recete_sorgu_gui import AylikReceteSorguGUI

# Minimal mock — sadece sema panel methodları için
# AylikReceteSorguGUI'nin tüm sema-related attribute/metodlarını otomatik kopyala
_SEMA_ATTR_PREFIX = ('_SEMA_', '_DEVRE_', '_sema_', '_devre_', '_grup_',
                     '_pasif_', '_bilgi_', '_fta_', '_madde_', '_dmn_',
                     '_aktif_', '_kontrol_')

class MockGUI:
    def __init__(self, root):
        self.root = root
        self.tum_satirlar = [satir]
        # YATAY layout testi — sema_frame full width, height sabit
        sema_frame = tk.Frame(root, bg="#FAFBFC", height=380,
                               relief="solid", bd=1)
        sema_frame.pack(side="bottom", fill="x", padx=8, pady=8)
        sema_frame.pack_propagate(False)
        self._sema_kur(sema_frame)
        # Hemen render et
        self.root.after(100, lambda: self._sema_render(satir))

for _attr in dir(AylikReceteSorguGUI):
    if _attr.startswith(_SEMA_ATTR_PREFIX):
        setattr(MockGUI, _attr, getattr(AylikReceteSorguGUI, _attr))

mock = MockGUI(root)

print(f"\nMock rapor sonucu: {rapor.sonuc.value}")
print(f"Şart sayısı: {len(rapor.sartlar)}")
print(f"Gruplar: {sorted(set(p.grup for p in rapor.sartlar))}")
print("\nPanel açıldı. Kapatmak için pencereyi kapatın.")

root.mainloop()
