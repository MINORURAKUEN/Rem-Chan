"""
Módulo para descargar videos desde múltiples fuentes:
- Archivos enviados directamente al bot (≤20 MB, límite de Telegram bots)
- Enlace t.me/... de Telegram SIN límite de tamaño (vía Telethon)
- URL HTTP directa / Dropbox
- Google Drive
- YouTube / TikTok / Instagram / Vimeo (vía yt-dlp)
"""

import os
import re
import asyncio
import logging
import aiohttp
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Sesión Telethon compartida (se inicializa una sola vez) ───
_telethon_client = None


async def get_telethon_client():
    """Devuelve el cliente Telethon, iniciándolo si es necesario."""
    global _telethon_client
    if _telethon_client and _telethon_client.is_connected():
        return _telethon_client

    from telethon import TelegramClient
    from config import Config
    cfg = Config()

    if not cfg.TELEGRAM_API_ID or not cfg.TELEGRAM_API_HASH:
        raise ValueError(
            "Configura TELEGRAM_API_ID y TELEGRAM_API_HASH en el archivo .env\n"
            "Obtenlos en: my.telegram.org/apps"
        )

    session_path = Path(__file__).parent / "telethon_session"
    client = TelegramClient(str(session_path), cfg.TELEGRAM_API_ID, cfg.TELEGRAM_API_HASH)
    await client.start(bot_token=cfg.TELEGRAM_TOKEN)
    _telethon_client = client
    logger.info("✅ Cliente Telethon iniciado")
    return client


class VideoDownloader:
    def __init__(self, temp_dir: str = "/tmp/fb_videos"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────
    # MÉTODO PRINCIPAL
    # ─────────────────────────────────────────────
    async def download(self, source: str, progress_callback=None) -> dict:
        """
        Detecta automáticamente el tipo de fuente y descarga el video.

        source puede ser:
          - file_id de Telegram  (≤20 MB, descargado por python-telegram-bot)
          - https://t.me/canal/123  (SIN límite, descargado por Telethon)
          - https://drive.google.com/...
          - https://www.dropbox.com/...
          - https://youtube.com/... (requiere yt-dlp)
          - Cualquier URL HTTP directa
        """
        source = source.strip()

        if 't.me/' in source or 'telegram.me/' in source:
            return await self._download_telegram_link(source, progress_callback)

        if any(x in source for x in ['youtube.com', 'youtu.be', 'tiktok.com',
                                      'instagram.com', 'vimeo.com', 'twitter.com', 'x.com']):
            return await self._download_ytdlp(source, progress_callback)

        if 'drive.google.com' in source:
            return await self._download_google_drive(source, progress_callback)

        if 'dropbox.com' in source:
            source = source.replace('?dl=0', '?dl=1').replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            return await self._download_http(source, progress_callback)

        if source.startswith('http://') or source.startswith('https://'):
            return await self._download_http(source, progress_callback)

        return {
            'success': False,
            'error': (
                "No reconozco ese tipo de enlace.\n\n"
                "Envía uno de estos:\n"
                "• Enlace de Telegram: `t.me/canal/123`\n"
                "• Google Drive, Dropbox\n"
                "• URL directa de video (.mp4)\n"
                "• YouTube, TikTok, Vimeo"
            )
        }

    # ─────────────────────────────────────────────
    # DESCARGA DESDE ARCHIVO DIRECTO DEL BOT (≤20 MB)
    # ─────────────────────────────────────────────
    async def download_bot_file(self, bot, file_id: str, filename: str = "video.mp4",
                                progress_callback=None) -> dict:
        """Descarga un archivo enviado directamente al bot (máx 20 MB)."""
        try:
            output_path = self.temp_dir / filename
            tg_file = await bot.get_file(file_id)

            if progress_callback:
                await progress_callback(0, "Descargando desde Telegram...")

            await tg_file.download_to_drive(str(output_path))

            if progress_callback:
                await progress_callback(100, "¡Descarga completa!")

            size = output_path.stat().st_size
            return {'success': True, 'path': str(output_path), 'filename': filename, 'size': size}

        except Exception as e:
            logger.error(f"Error descargando archivo del bot: {e}")
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────
    # DESCARGA ENLACE TELEGRAM SIN LÍMITE (Telethon)
    # ─────────────────────────────────────────────
    async def _download_telegram_link(self, url: str, progress_callback=None) -> dict:
        """
        Descarga el video de un mensaje de Telegram usando Telethon.
        No tiene límite de 20 MB — puede descargar archivos de varios GB.
        """
        try:
            # Parsear el enlace: https://t.me/canal/123 o https://t.me/c/123456/789
            match_public = re.search(r't\.me/([^/]+)/(\d+)', url)
            match_private = re.search(r't\.me/c/(\d+)/(\d+)', url)

            if not match_public and not match_private:
                return {
                    'success': False,
                    'error': 'Formato de enlace Telegram inválido.\nEjemplo válido: https://t.me/canal/123'
                }

            client = await get_telethon_client()

            if progress_callback:
                await progress_callback(0, "Conectando con Telegram (Telethon)...")

            if match_private:
                # Canal privado: t.me/c/ID_CHAT/ID_MENSAJE
                chat_id = int('-100' + match_private.group(1))
                msg_id = int(match_private.group(2))
                entity = await client.get_entity(chat_id)
            else:
                # Canal público: t.me/username/ID_MENSAJE
                username = match_public.group(1)
                msg_id = int(match_public.group(2))
                entity = await client.get_entity(username)

            message = await client.get_messages(entity, ids=msg_id)

            if not message or not message.media:
                return {'success': False, 'error': 'El mensaje no contiene ningún archivo multimedia.'}

            # Detectar nombre de archivo
            filename = "video.mp4"
            if hasattr(message.media, 'document') and message.media.document:
                for attr in message.media.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        filename = attr.file_name
                        break

            output_path = self.temp_dir / filename
            total_size = {'bytes': 0}

            # Obtener tamaño total
            if hasattr(message.media, 'document'):
                total_size['bytes'] = message.media.document.size

            last_pct = {'v': -1}

            async def _progress(current, total):
                if total and progress_callback:
                    pct = int((current / total) * 100)
                    if pct != last_pct['v']:
                        last_pct['v'] = pct
                        mb_done = current / (1024 * 1024)
                        mb_total = total / (1024 * 1024)
                        await progress_callback(pct, f"{mb_done:.1f} / {mb_total:.1f} MB")

            await client.download_media(message, file=str(output_path), progress_callback=_progress)

            if not output_path.exists():
                return {'success': False, 'error': 'La descarga falló o el archivo no se guardó correctamente.'}

            size = output_path.stat().st_size
            logger.info(f"✅ Descargado via Telethon: {filename} ({size/(1024*1024):.1f} MB)")
            return {'success': True, 'path': str(output_path), 'filename': filename, 'size': size}

        except ValueError as e:
            return {'success': False, 'error': f'No se pudo acceder al chat: {e}\n¿El bot está en ese canal?'}
        except Exception as e:
            logger.error(f"Error Telethon: {e}")
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────
    # DESCARGA HTTP DIRECTA
    # ─────────────────────────────────────────────
    async def _download_http(self, url: str, progress_callback=None) -> dict:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; VideoBot/1.0)'}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        return {'success': False, 'error': f'Error HTTP {resp.status}'}

                    content_disp = resp.headers.get('Content-Disposition', '')
                    filename = self._extract_filename(content_disp, url)
                    total_size = int(resp.headers.get('Content-Length', 0))
                    output_path = self.temp_dir / filename
                    downloaded = 0
                    CHUNK = 2 * 1024 * 1024  # 2 MB

                    async with aiofiles.open(output_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(CHUNK):
                            await f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size:
                                pct = int((downloaded / total_size) * 100)
                                mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                await progress_callback(pct, f"{mb:.1f} / {total_mb:.1f} MB")

            size = output_path.stat().st_size
            return {'success': True, 'path': str(output_path), 'filename': filename, 'size': size}

        except Exception as e:
            logger.error(f"Error HTTP download: {e}")
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────
    # DESCARGA GOOGLE DRIVE
    # ─────────────────────────────────────────────
    async def _download_google_drive(self, url: str, progress_callback=None) -> dict:
        try:
            file_id = None
            for pattern in [r'/file/d/([a-zA-Z0-9_-]+)', r'id=([a-zA-Z0-9_-]+)', r'/d/([a-zA-Z0-9_-]+)']:
                m = re.search(pattern, url)
                if m:
                    file_id = m.group(1)
                    break

            if not file_id:
                return {'success': False, 'error': 'No se pudo extraer el ID del archivo de Google Drive.'}

            if progress_callback:
                await progress_callback(0, "Conectando con Google Drive...")

            # Para archivos grandes, Drive requiere confirmación de antivirus
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t&uuid=1"
            return await self._download_http(download_url, progress_callback)

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────
    # DESCARGA YOUTUBE / REDES SOCIALES (yt-dlp)
    # ─────────────────────────────────────────────
    async def _download_ytdlp(self, url: str, progress_callback=None) -> dict:
        try:
            import yt_dlp
        except ImportError:
            return {
                'success': False,
                'error': 'yt-dlp no está instalado.\nEjecuta: pip install yt-dlp'
            }

        result_path = {'path': None, 'error': None}
        loop = asyncio.get_event_loop()

        def _run():
            def hook(d):
                if d['status'] == 'downloading' and progress_callback:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    done = d.get('downloaded_bytes', 0)
                    if total:
                        pct = int((done / total) * 100)
                        mb = done / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        asyncio.run_coroutine_threadsafe(
                            progress_callback(pct, f"{mb:.1f} / {total_mb:.1f} MB"), loop
                        )
                elif d['status'] == 'finished':
                    result_path['path'] = d.get('filename')

            opts = {
                'outtmpl': str(self.temp_dir / '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'progress_hooks': [hook],
                'quiet': True,
                'no_warnings': True,
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not result_path['path']:
                        result_path['path'] = ydl.prepare_filename(info)
            except Exception as e:
                result_path['error'] = str(e)

        await loop.run_in_executor(None, _run)

        if result_path['error']:
            return {'success': False, 'error': result_path['error']}
        if result_path['path'] and os.path.exists(result_path['path']):
            size = os.path.getsize(result_path['path'])
            filename = os.path.basename(result_path['path'])
            return {'success': True, 'path': result_path['path'], 'filename': filename, 'size': size}

        return {'success': False, 'error': 'yt-dlp no pudo descargar el video.'}

    # ─────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────
    def _extract_filename(self, content_disposition: str, url: str) -> str:
        """Extrae el nombre de archivo del header o la URL."""
        if content_disposition:
            m = re.search(r'filename[^;=\n]*=([\'"](.*?)[\'"]|[^\n]*)', content_disposition)
            if m:
                return m.group(2) or m.group(1).strip('\'"')
        # Extraer de la URL
        path = urlparse(url).path
        name = os.path.basename(unquote(path))
        if name and '.' in name:
            return name
        return "video.mp4"


# Import necesario para _extract_filename
from urllib.parse import urlparse, unquote
