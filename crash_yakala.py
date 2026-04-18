"""
Global hata/çökme yakalayıcı.

Programın başında `from crash_yakala import kur; kur()` çağrılır.
- faulthandler: C-level segfault için stack trace yazar
- sys.excepthook: ana thread uncaught exception'ları loglar
- threading.excepthook: arka plan thread'lerinde uncaught exception'ları loglar

Loglar: BOT takip 20/crash_log.txt
"""

import faulthandler
import logging
import os
import sys
import threading
import traceback
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_YOLU = os.path.join(_SCRIPT_DIR, "crash_log.txt")

logger = logging.getLogger(__name__)


def _yaz(baslik: str, metin: str):
    try:
        with open(LOG_YOLU, "a", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {baslik}\n")
            f.write("=" * 70 + "\n")
            f.write(metin)
            if not metin.endswith("\n"):
                f.write("\n")
            f.write("\n")
    except Exception:
        pass


def _excepthook(tip, deger, tb):
    metin = "".join(traceback.format_exception(tip, deger, tb))
    _yaz("UNCAUGHT EXCEPTION (main thread)", metin)
    logger.error(f"UNCAUGHT: {tip.__name__}: {deger}")
    sys.__excepthook__(tip, deger, tb)


def _thread_excepthook(args):
    metin = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    thread_adi = getattr(args.thread, "name", "?")
    _yaz(
        f"UNCAUGHT EXCEPTION (thread: {thread_adi})",
        metin,
    )
    logger.error(
        f"UNCAUGHT (thread {thread_adi}): "
        f"{args.exc_type.__name__}: {args.exc_value}"
    )


def kur():
    """Global yakalayıcıları kur. Programın başında bir kez çağır."""
    # 1) C-level segfault (Windows kilitlenme)
    try:
        fh = open(LOG_YOLU, "a", encoding="utf-8")
        fh.write(
            f"\n--- faulthandler aktif "
            f"[{datetime.now().isoformat(timespec='seconds')}] ---\n"
        )
        fh.flush()
        faulthandler.enable(file=fh, all_threads=True)
    except Exception as e:
        logger.debug(f"faulthandler kurulamadı: {e}")

    # 2) Ana thread uncaught exceptions
    sys.excepthook = _excepthook

    # 3) Arka plan thread uncaught exceptions (Python 3.8+)
    try:
        threading.excepthook = _thread_excepthook
    except AttributeError:
        # Eski Python
        pass

    # 4) Başlangıç kaydı
    _yaz("PROGRAM BAŞLATILDI", f"Python: {sys.version}\nArgs: {sys.argv}")
