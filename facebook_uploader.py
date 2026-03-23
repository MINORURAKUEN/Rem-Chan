"""
Módulo para subir videos a Facebook usando Graph API
"""

import os
import asyncio
import aiohttp
import aiofiles
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v19.0"
VIDEO_UPLOAD_URL = "https://graph-video.facebook.com/v19.0"


class FacebookUploader:
    def __init__(self, access_token: str):
        self.token = access_token

    async def validate_token(self) -> dict:
        """Valida el token de Facebook y obtiene info del usuario"""
        url = f"{GRAPH_API_URL}/me"
        params = {
            'access_token': self.token,
            'fields': 'id,name'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()

            if 'error' in data:
                return {
                    'success': False,
                    'error': data['error'].get('message', 'Token inválido')
                }

            return {
                'success': True,
                'user_id': data.get('id'),
                'user_name': data.get('name')
            }

        except Exception as e:
            logger.error(f"Error validando token: {e}")
            return {'success': False, 'error': str(e)}

    async def get_pages(self) -> dict:
        """Obtiene las páginas del usuario con sus tokens"""
        url = f"{GRAPH_API_URL}/me/accounts"
        params = {
            'access_token': self.token,
            'fields': 'id,name,access_token,category'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()

            if 'error' in data:
                return {
                    'success': False,
                    'error': data['error'].get('message', 'Error obteniendo páginas')
                }

            pages = data.get('data', [])
            return {'success': True, 'pages': pages}

        except Exception as e:
            logger.error(f"Error obteniendo páginas: {e}")
            return {'success': False, 'error': str(e)}

    async def upload_video(
        self,
        page_id: str,
        page_token: str,
        video_path: str,
        title: str,
        description: str = '',
        privacy: str = 'EVERYONE'
    ) -> dict:
        """
        Sube un video a Facebook usando la API de subida reanudable.
        Recomendada para videos grandes (>1GB).
        """
        file_size = os.path.getsize(video_path)
        logger.info(f"Iniciando subida de video: {video_path} ({file_size} bytes)")

        try:
            # Paso 1: Iniciar la sesión de subida
            session_result = await self._start_upload_session(
                page_id, page_token, file_size, title, description, privacy
            )

            if not session_result['success']:
                return session_result

            upload_session_id = session_result['upload_session_id']
            video_id = session_result['video_id']

            logger.info(f"Sesión de subida iniciada: {upload_session_id}")

            # Paso 2: Subir el video en chunks
            upload_result = await self._upload_chunks(
                page_id, page_token, upload_session_id, video_path, file_size
            )

            if not upload_result['success']:
                return upload_result

            # Paso 3: Finalizar la subida
            finish_result = await self._finish_upload(
                page_id, page_token, upload_session_id
            )

            if finish_result['success']:
                logger.info(f"Video subido exitosamente. ID: {video_id}")
                return {'success': True, 'video_id': video_id}
            else:
                return finish_result

        except Exception as e:
            logger.error(f"Error en subida de video: {e}")
            return {'success': False, 'error': str(e)}

    async def _start_upload_session(
        self,
        page_id: str,
        page_token: str,
        file_size: int,
        title: str,
        description: str,
        privacy: str
    ) -> dict:
        """Inicia una sesión de subida reanudable"""
        url = f"{VIDEO_UPLOAD_URL}/{page_id}/videos"

        payload = {
            'upload_phase': 'start',
            'file_size': str(file_size),
            'title': title,
            'description': description,
            'privacy': f'{{"value":"{privacy}"}}',
            'access_token': page_token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as resp:
                    data = await resp.json()

            if 'error' in data:
                return {
                    'success': False,
                    'error': data['error'].get('message', 'Error iniciando sesión')
                }

            return {
                'success': True,
                'upload_session_id': data.get('upload_session_id'),
                'video_id': data.get('video_id'),
                'start_offset': data.get('start_offset', 0),
                'end_offset': data.get('end_offset', 0)
            }

        except Exception as e:
            logger.error(f"Error iniciando sesión de subida: {e}")
            return {'success': False, 'error': str(e)}

    async def _upload_chunks(
        self,
        page_id: str,
        page_token: str,
        upload_session_id: str,
        video_path: str,
        file_size: int
    ) -> dict:
        """Sube el video en chunks"""
        CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB por chunk
        url = f"{VIDEO_UPLOAD_URL}/{page_id}/videos"

        start_offset = 0

        async with aiofiles.open(video_path, 'rb') as f:
            while start_offset < file_size:
                chunk = await f.read(CHUNK_SIZE)
                if not chunk:
                    break

                end_offset = min(start_offset + len(chunk), file_size)

                form_data = aiohttp.FormData()
                form_data.add_field('upload_phase', 'transfer')
                form_data.add_field('upload_session_id', upload_session_id)
                form_data.add_field('start_offset', str(start_offset))
                form_data.add_field('access_token', page_token)
                form_data.add_field(
                    'video_file_chunk',
                    chunk,
                    filename='chunk.bin',
                    content_type='application/octet-stream'
                )

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, data=form_data) as resp:
                            data = await resp.json()

                    if 'error' in data:
                        return {
                            'success': False,
                            'error': data['error'].get('message', 'Error subiendo chunk')
                        }

                    start_offset = int(data.get('start_offset', end_offset))
                    progress = (start_offset / file_size) * 100
                    logger.info(f"Progreso de subida: {progress:.1f}%")

                except Exception as e:
                    logger.error(f"Error subiendo chunk en offset {start_offset}: {e}")
                    return {'success': False, 'error': str(e)}

        return {'success': True}

    async def _finish_upload(
        self,
        page_id: str,
        page_token: str,
        upload_session_id: str
    ) -> dict:
        """Finaliza la sesión de subida"""
        url = f"{VIDEO_UPLOAD_URL}/{page_id}/videos"

        payload = {
            'upload_phase': 'finish',
            'upload_session_id': upload_session_id,
            'access_token': page_token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as resp:
                    data = await resp.json()

            if 'error' in data:
                return {
                    'success': False,
                    'error': data['error'].get('message', 'Error finalizando subida')
                }

            return {'success': True, 'data': data}

        except Exception as e:
            logger.error(f"Error finalizando subida: {e}")
            return {'success': False, 'error': str(e)}
