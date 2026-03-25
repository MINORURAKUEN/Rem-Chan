"""
Configuración del bot desde variables de entorno
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Detectar si estamos en Termux (Android)
_is_termux = 'com.termux' in os.environ.get('PREFIX', '') or \
             os.path.exists('/data/data/com.termux')

_default_temp = (
    '/data/data/com.termux/files/home/fb_videos'
    if _is_termux else '/tmp/fb_videos'
)


class Config:
    # Token del bot de Telegram (desde @BotFather)
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # Credenciales de la App de Telegram para descargas sin límite (Telethon)
    # Obtenlas en: https://my.telegram.org/apps
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")

    # Directorio temporal para videos (Termux-compatible)
    TEMP_DIR: str = os.getenv("TEMP_DIR", _default_temp)

    # Duración mínima del video en segundos (24 minutos)
    MIN_VIDEO_DURATION: int = int(os.getenv("MIN_VIDEO_DURATION", "1440"))

    # Tamaño máximo en bytes (10 GB)
    MAX_VIDEO_SIZE: int = int(os.getenv("MAX_VIDEO_SIZE", str(10 * 1024 * 1024 * 1024)))

    def __init__(self):
        Path(self.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        
