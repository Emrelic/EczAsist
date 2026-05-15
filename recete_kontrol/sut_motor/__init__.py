# -*- coding: utf-8 -*-
"""SUT Motor — Deklaratif SUT kural değerlendirme motoru (PILOT v1).

Amaç: SUT lafzı → atomik şart + AND/OR/NOT formülü → JSON kural →
motor değerlendirir → KontrolRaporu (SartSonuc listesi + KontrolSonucu).

Aynı kural hem (a) uygunluk kararını verir hem de (b) atomik şema panelinin
beslediği SartSonuc listesini üretir. Yeni SUT/ilaç eklemek = JSON yazmak;
yeni Python kodu yazmak değil (atom kütüphanesinde olmayan bir doğrulayıcı
gerekirse @atom dekoratörüyle eklenir).

PILOT: Fibrat 4.2.28.B. Sonuçlar `recete_kontrol.sut_kontrolleri.kontrol_fibrat`
ile bire bir karşılaştırılır.
"""
from .baglam import Baglam
from .atomlar import atom, AtomSonuc, atom_kayit
from .motor import degerlendir, kural_yukle

__all__ = ['Baglam', 'atom', 'AtomSonuc', 'atom_kayit',
           'degerlendir', 'kural_yukle']
