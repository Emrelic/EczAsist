@echo off
cd /d "%~dp0"
start "" pythonw -c "import tkinter as tk; from recete_rapor_kontrol_gui import ReceteRaporKontrolGUI; root = tk.Tk(); app = ReceteRaporKontrolGUI(root); root.mainloop()"
