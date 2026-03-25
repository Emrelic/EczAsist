#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reçete/Rapor Kontrol modülünü bağımsız olarak başlatır."""
import os
import sys
import tkinter as tk

# Proje dizinine geç
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_rapor_kontrol_gui import ReceteRaporKontrolGUI

root = tk.Tk()
app = ReceteRaporKontrolGUI(root)
root.mainloop()
