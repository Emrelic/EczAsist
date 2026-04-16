"""
Loglama sistemi
"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from .config import LOG_DIR


def setup_logger(name="BotSiparis"):
    """Logger oluştur"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # .env dosyasını yükle (logger oluşturulmadan önce)
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)

    # DEBUG_LOGGING ayarını oku
    debug_logging = os.getenv("DEBUG_LOGGING", "false").lower() == "true"

    # Dosya handler
    log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')

    # DEBUG_LOGGING ayarına göre dosya log seviyesi
    if debug_logging:
        file_handler.setLevel(logging.DEBUG)  # Tüm loglar
        print(f"[Logger] DEBUG_LOGGING=true - Tüm loglar dosyaya yazılacak")
    else:
        file_handler.setLevel(logging.WARNING)  # Sadece WARNING ve ERROR
        print(f"[Logger] DEBUG_LOGGING=false - Sadece WARNING/ERROR dosyaya yazılacak")

    # Konsol handler (her zaman INFO seviyesinde, kullanıcı görsün)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Global logger
logger = setup_logger()
