"""
Configuración del bot desde variables de entorno
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Token del bot de Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # Credenciales de la app de Telegram (para Telethon - descarga sin límite)
    # Obtenlas en: my.telegram.org/apps
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")

    # Directorio temporal para videos
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/fb_videos")

    # Duración mínima del video en segundos (24 minutos)
    MIN_VIDEO_DURATION: int = int(os.getenv("MIN_VIDEO_DURATION", "1440"))

    # Tamaño máximo en bytes (10 GB)
    MAX_VIDEO_SIZE: int = int(os.getenv("MAX_VIDEO_SIZE", str(10 * 1024 * 1024 * 1024)))

    def __init__(self):
        # Crear directorio temporal si no existe
        Path(self.TEMP_DIR).mkdir(parents=True, exist_ok=True)
