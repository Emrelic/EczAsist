"""
Eczasist program ikonu — tek giriş noktası.
Tüm Tk/Toplevel pencereleri bu yardımcı ile ikon alır.
"""

import logging
import os

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_SCRIPT_DIR, "assets", "eczasist.ico")


def ikon_uygula(pencere) -> None:
    """Tk/Toplevel penceresine Eczasist ikonunu uygula (hata sessiz geçilir)."""
    try:
        if os.path.exists(ICON_PATH):
            pencere.iconbitmap(ICON_PATH)
    except Exception as e:
        logger.debug("İkon uygulanamadı: %s", e)
