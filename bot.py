#!/usr/bin/env python3
"""
Telegram Bot para subir videos a Facebook (24+ minutos)
"""

import os
import logging
import asyncio
import json
import tempfile
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

from facebook_uploader import FacebookUploader
from database import Database
from config import Config
from video_downloader import VideoDownloader, get_telethon_client

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Estados de conversación
(
    WAITING_FB_TOKEN,
    WAITING_PAGE_SELECTION,
    WAITING_VIDEO,
    WAITING_TITLE,
    WAITING_DESCRIPTION,
    WAITING_PRIVACY,
    CONFIRMING_UPLOAD
) = range(7)

db = Database()
config = Config()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando /start"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    user = db.get_user(user_id)

    keyboard = []
    if user and user.get('fb_token'):
        keyboard = [
            [InlineKeyboardButton("📹 Subir Video", callback_data="upload_video")],
            [InlineKeyboardButton("📄 Mis Páginas", callback_data="list_pages")],
            [InlineKeyboardButton("🔄 Cambiar Cuenta FB", callback_data="change_account")],
            [InlineKeyboardButton("ℹ️ Ayuda", callback_data="help")]
        ]
        status = "✅ *Conectado a Facebook*"
    else:
        keyboard = [
            [InlineKeyboardButton("🔑 Conectar Facebook", callback_data="connect_fb")],
            [InlineKeyboardButton("ℹ️ Ayuda", callback_data="help")]
        ]
        status = "❌ *No conectado a Facebook*"

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 ¡Hola, {user_name}!\n\n"
        f"🤖 *Bot de Subida de Videos a Facebook*\n\n"
        f"{status}\n\n"
        f"📌 Este bot sube videos de *24 minutos o más* directamente a tus páginas de Facebook.\n\n"
        f"Selecciona una opción:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    text = (
        "📖 *Guía de Uso*\n\n"
        "1️⃣ *Conectar Facebook*\n"
        "   → Usa /login para conectar tu cuenta\n"
        "   → Necesitas un Token de Acceso de Facebook\n\n"
        "2️⃣ *Subir Video*\n"
        "   → Usa /upload o el botón del menú\n"
        "   → El video debe durar *24 minutos o más*\n"
        "   → Formatos: MP4, AVI, MOV, MKV\n\n"
        "3️⃣ *Comandos disponibles*\n"
        "   /start - Menú principal\n"
        "   /login - Conectar Facebook\n"
        "   /upload - Subir video\n"
        "   /pages - Ver páginas conectadas\n"
        "   /logout - Desconectar cuenta\n"
        "   /status - Estado de la conexión\n"
        "   /help - Esta ayuda\n\n"
        "🔑 *¿Cómo obtener el Token de Facebook?*\n"
        "Visita: developers.facebook.com/tools/explorer\n\n"
        "⚠️ *Requisitos del video:*\n"
        "• Duración mínima: 24 minutos\n"
        "• Tamaño máximo: 10 GB\n"
        "• Resolución recomendada: 720p o superior"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de login con Facebook"""
    await update.message.reply_text(
        "🔑 *Conectar con Facebook*\n\n"
        "Para conectar tu cuenta de Facebook, necesitas un *Token de Acceso*.\n\n"
        "📋 *Pasos para obtenerlo:*\n"
        "1. Ve a: `developers.facebook.com/tools/explorer`\n"
        "2. Selecciona tu aplicación\n"
        "3. Haz clic en 'Obtener Token'\n"
        "4. Selecciona los permisos: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`\n"
        "5. Copia el token generado\n\n"
        "🔐 Ahora envíame tu *Token de Acceso de Facebook*:\n\n"
        "_(Puedes cancelar con /cancel)_",
        parse_mode='Markdown'
    )
    return WAITING_FB_TOKEN


async def receive_fb_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida el token de Facebook"""
    token = update.message.text.strip()
    user_id = update.effective_user.id

    # Eliminar el mensaje con el token por seguridad
    await update.message.delete()

    processing_msg = await update.message.reply_text("🔄 Validando token de Facebook...")

    uploader = FacebookUploader(token)
    result = await uploader.validate_token()

    if result['success']:
        # Guardar token en base de datos
        db.save_user(user_id, {
            'fb_token': token,
            'fb_user_id': result['user_id'],
            'fb_user_name': result['user_name']
        })

        # Obtener páginas disponibles
        pages_result = await uploader.get_pages()

        if pages_result['success'] and pages_result['pages']:
            db.save_pages(user_id, pages_result['pages'])

            pages_text = "\n".join([
                f"  • {p['name']} (ID: {p['id']})"
                for p in pages_result['pages']
            ])

            await processing_msg.edit_text(
                f"✅ *¡Conectado exitosamente!*\n\n"
                f"👤 Usuario: {result['user_name']}\n\n"
                f"📄 *Páginas encontradas:*\n{pages_text}\n\n"
                f"Usa /upload para subir tu primer video.",
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                f"✅ Token válido para {result['user_name']}\n\n"
                f"⚠️ No se encontraron páginas de Facebook asociadas.\n"
                f"Asegúrate de tener páginas en tu cuenta y los permisos correctos.",
                parse_mode='Markdown'
            )
    else:
        await processing_msg.edit_text(
            f"❌ *Token inválido*\n\n"
            f"Error: {result.get('error', 'Token no válido')}\n\n"
            f"Por favor verifica el token e intenta de nuevo con /login",
            parse_mode='Markdown'
        )

    return ConversationHandler.END


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de subida de video"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user or not user.get('fb_token'):
        await update.message.reply_text(
            "❌ No estás conectado a Facebook.\n"
            "Usa /login para conectar tu cuenta primero."
        )
        return ConversationHandler.END

    pages = db.get_pages(user_id)

    if not pages:
        await update.message.reply_text(
            "❌ No tienes páginas de Facebook configuradas.\n"
            "Usa /login para reconectar y cargar tus páginas."
        )
        return ConversationHandler.END

    if len(pages) == 1:
        context.user_data['selected_page'] = pages[0]
        return await request_video(update, context)

    # Mostrar selector de páginas
    keyboard = [
        [InlineKeyboardButton(f"📄 {p['name']}", callback_data=f"page_{p['id']}")]
        for p in pages
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])

    await update.message.reply_text(
        "📄 *Selecciona la página de Facebook*\n\n"
        "¿En qué página quieres subir el video?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_PAGE_SELECTION


async def select_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de página"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return ConversationHandler.END

    page_id = query.data.replace("page_", "")
    user_id = update.effective_user.id
    pages = db.get_pages(user_id)

    selected_page = next((p for p in pages if p['id'] == page_id), None)
    if not selected_page:
        await query.edit_message_text("❌ Página no encontrada.")
        return ConversationHandler.END

    context.user_data['selected_page'] = selected_page

    await query.edit_message_text(
        f"✅ Página seleccionada: *{selected_page['name']}*",
        parse_mode='Markdown'
    )

    return await request_video_via_query(update, context)


VIDEO_PROMPT = (
    "📹 *Subir Video a Facebook*\n\n"
    "📄 Página: *{page_name}*\n\n"
    "Envíame el video de una de estas formas:\n\n"
    "1️⃣ *Archivo directo* — hasta 20 MB (límite de Telegram)\n"
    "2️⃣ *Enlace de Telegram* — sin límite de tamaño\n"
    "   `https://t.me/canal/123`\n"
    "3️⃣ *URL directa* — Google Drive, Dropbox, HTTP\n"
    "4️⃣ *YouTube / TikTok / Vimeo* — requiere yt-dlp\n\n"
    "⚠️ Duración mínima: *24 minutos*\n\n"
    "_(Cancela con /cancel)_"
)


async def request_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Solicita el video al usuario (mensaje directo)"""
    page = context.user_data.get('selected_page', {})
    await update.message.reply_text(
        VIDEO_PROMPT.format(page_name=page.get('name', 'N/A')),
        parse_mode='Markdown'
    )
    return WAITING_VIDEO


async def request_video_via_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Solicita el video vía callback query"""
    page = context.user_data.get('selected_page', {})
    await update.callback_query.message.reply_text(
        VIDEO_PROMPT.format(page_name=page.get('name', 'N/A')),
        parse_mode='Markdown'
    )
    return WAITING_VIDEO


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe el video: puede ser un archivo adjunto (≤20 MB)
    o un mensaje de texto con URL/enlace de Telegram (sin límite).
    """
    MIN_DURATION = 24 * 60  # 1440 segundos

    # ── CASO A: archivo adjunto directo ──────────────────────────
    video = update.message.video or update.message.document
    if video:
        if hasattr(video, 'duration') and video.duration and video.duration < MIN_DURATION:
            d_min = video.duration // 60
            d_sec = video.duration % 60
            await update.message.reply_text(
                f"❌ *Video demasiado corto*\n\n"
                f"Duración: *{d_min}m {d_sec}s* — se requieren mínimo *24 minutos*.\n\n"
                f"Envía otro video o usa un enlace.",
                parse_mode='Markdown'
            )
            return WAITING_VIDEO

        size_mb = (video.file_size or 0) / (1024 * 1024)
        if size_mb > 20:
            await update.message.reply_text(
                f"⚠️ *Archivo demasiado grande para descarga directa* ({size_mb:.0f} MB)\n\n"
                f"Los bots de Telegram solo pueden descargar hasta *20 MB*.\n\n"
                f"Usa uno de estos métodos:\n"
                f"• Enlace de Telegram: `t.me/canal/ID`\n"
                f"• Google Drive / Dropbox\n"
                f"• URL directa de descarga",
                parse_mode='Markdown'
            )
            return WAITING_VIDEO

        context.user_data['video_source'] = 'bot_file'
        context.user_data['video_file_id'] = video.file_id
        context.user_data['video_file_name'] = getattr(video, 'file_name', 'video.mp4')
        context.user_data['video_duration'] = getattr(video, 'duration', 0)
        context.user_data['video_size'] = video.file_size or 0

        d_min = context.user_data['video_duration'] // 60
        d_sec = context.user_data['video_duration'] % 60
        size_mb = context.user_data['video_size'] / (1024 * 1024)

        await update.message.reply_text(
            f"✅ *Video recibido*\n"
            f"📁 {context.user_data['video_file_name']}\n"
            f"⏱️ {d_min}m {d_sec}s  |  💾 {size_mb:.1f} MB\n\n"
            f"📝 Escribe el *título* del video:",
            parse_mode='Markdown'
        )
        return WAITING_TITLE

    # ── CASO B: URL o enlace de Telegram ─────────────────────────
    if update.message.text:
        url = update.message.text.strip()
        if not (url.startswith('http') or 't.me/' in url or 'telegram.me/' in url):
            await update.message.reply_text(
                "❌ No entiendo ese mensaje.\n\n"
                "Envía un *archivo de video* adjunto, un *enlace de Telegram* "
                "(t.me/...) o una *URL* de descarga.",
                parse_mode='Markdown'
            )
            return WAITING_VIDEO

        context.user_data['video_source'] = 'url'
        context.user_data['video_url'] = url
        context.user_data['video_file_name'] = 'video.mp4'
        context.user_data['video_duration'] = 0
        context.user_data['video_size'] = 0

        source_icon = "🔗" if 't.me/' in url else "🌐"
        await update.message.reply_text(
            f"{source_icon} *Enlace recibido*\n`{url[:80]}{'...' if len(url) > 80 else ''}`\n\n"
            f"ℹ️ La duración se verificará al descargar.\n\n"
            f"📝 Escribe el *título* del video:",
            parse_mode='Markdown'
        )
        return WAITING_TITLE

    await update.message.reply_text("❌ Envía un archivo de video o una URL válida.")
    return WAITING_VIDEO


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el título del video"""
    title = update.message.text.strip()

    if len(title) > 255:
        await update.message.reply_text(
            f"❌ El título es muy largo ({len(title)} caracteres).\n"
            f"Máximo 255 caracteres. Intenta de nuevo:"
        )
        return WAITING_TITLE

    context.user_data['video_title'] = title

    await update.message.reply_text(
        f"✅ Título: *{title}*\n\n"
        f"📝 Ahora escribe la *descripción* del video\n"
        f"(o envía /skip para omitir):",
        parse_mode='Markdown'
    )
    return WAITING_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción del video"""
    if update.message.text == '/skip':
        context.user_data['video_description'] = ''
    else:
        context.user_data['video_description'] = update.message.text.strip()

    # Seleccionar privacidad
    keyboard = [
        [InlineKeyboardButton("🌍 Público", callback_data="privacy_EVERYONE")],
        [InlineKeyboardButton("👥 Amigos", callback_data="privacy_FRIENDS")],
        [InlineKeyboardButton("🔒 Solo yo", callback_data="privacy_SELF")],
    ]

    await update.message.reply_text(
        "🔐 *Privacidad del video:*\n\n"
        "¿Quién puede ver este video?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_PRIVACY


async def receive_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la configuración de privacidad"""
    query = update.callback_query
    await query.answer()

    privacy_map = {
        'privacy_EVERYONE': ('🌍 Público', 'EVERYONE'),
        'privacy_FRIENDS': ('👥 Amigos', 'FRIENDS'),
        'privacy_SELF': ('🔒 Solo yo', 'SELF')
    }

    privacy_label, privacy_value = privacy_map.get(query.data, ('🌍 Público', 'EVERYONE'))
    context.user_data['video_privacy'] = privacy_value

    # Mostrar resumen para confirmación
    page = context.user_data.get('selected_page', {})
    title = context.user_data.get('video_title', '')
    description = context.user_data.get('video_description', 'Sin descripción')
    duration = context.user_data.get('video_duration', 0)
    size = context.user_data.get('video_size', 0)

    duration_min = duration // 60
    duration_sec = duration % 60
    size_mb = size / (1024 * 1024) if size else 0

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar y Subir", callback_data="confirm_upload"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_upload")
        ]
    ]

    await query.edit_message_text(
        f"📋 *Resumen de subida*\n\n"
        f"📄 Página: *{page.get('name', 'N/A')}*\n"
        f"🎬 Título: *{title}*\n"
        f"📝 Descripción: {description[:100]}{'...' if len(description) > 100 else ''}\n"
        f"⏱️ Duración: *{duration_min}m {duration_sec}s*\n"
        f"💾 Tamaño: *{size_mb:.1f} MB*\n"
        f"🔐 Privacidad: *{privacy_label}*\n\n"
        f"¿Confirmas la subida?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRMING_UPLOAD


async def confirm_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma y ejecuta la descarga + subida del video"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_upload":
        await query.edit_message_text("❌ Subida cancelada.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    user = db.get_user(user_id)
    page = context.user_data['selected_page']
    source = context.user_data.get('video_source', 'bot_file')
    downloader = VideoDownloader(config.TEMP_DIR)
    tmp_path = None

    # ── Mensaje de progreso editable ─────────────────────────────
    status_msg = query.message
    last_text = {'v': ''}

    async def update_progress(pct: int, detail: str):
        bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
        text = (
            f"⬇️ *Descargando video...*\n\n"
            f"`[{bar}]` {pct}%\n"
            f"💾 {detail}"
        )
        if text != last_text['v']:
            last_text['v'] = text
            try:
                await status_msg.edit_text(text, parse_mode='Markdown')
            except Exception:
                pass

    await status_msg.edit_text(
        "⬇️ *Iniciando descarga del video...*\n\nPor favor espera.",
        parse_mode='Markdown'
    )

    try:
        # ── DESCARGA ─────────────────────────────────────────────
        if source == 'bot_file':
            dl_result = await downloader.download_bot_file(
                bot=context.bot,
                file_id=context.user_data['video_file_id'],
                filename=context.user_data.get('video_file_name', 'video.mp4'),
                progress_callback=update_progress
            )
        else:
            # URL o enlace de Telegram
            dl_result = await downloader.download(
                source=context.user_data['video_url'],
                progress_callback=update_progress
            )

        if not dl_result['success']:
            await status_msg.edit_text(
                f"❌ *Error al descargar el video*\n\n{dl_result['error']}",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        tmp_path = dl_result['path']
        size_mb = dl_result['size'] / (1024 * 1024)

        # ── Verificar duración con ffprobe (si disponible) ───────
        duration_sec = await _get_video_duration(tmp_path)
        MIN_DURATION = 24 * 60

        if duration_sec and duration_sec < MIN_DURATION:
            os.unlink(tmp_path)
            d_min = duration_sec // 60
            d_sec = duration_sec % 60
            await status_msg.edit_text(
                f"❌ *Video demasiado corto*\n\n"
                f"Duración detectada: *{d_min}m {d_sec}s*\n"
                f"Mínimo requerido: *24 minutos*",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # ── SUBIDA A FACEBOOK ─────────────────────────────────────
        d_min = (duration_sec or 0) // 60
        d_sec = (duration_sec or 0) % 60
        await status_msg.edit_text(
            f"✅ *Video descargado* ({size_mb:.1f} MB"
            f"{f', {d_min}m {d_sec}s' if duration_sec else ''})\n\n"
            f"📤 *Subiendo a Facebook...*\n"
            f"Esto puede demorar varios minutos. Te avisaré al terminar.",
            parse_mode='Markdown'
        )

        uploader = FacebookUploader(user['fb_token'])
        result = await uploader.upload_video(
            page_id=page['id'],
            page_token=page.get('access_token', user['fb_token']),
            video_path=tmp_path,
            title=context.user_data['video_title'],
            description=context.user_data.get('video_description', ''),
            privacy=context.user_data.get('video_privacy', 'EVERYONE')
        )

        os.unlink(tmp_path)

        if result['success']:
            video_url = f"https://www.facebook.com/{page['id']}/videos/{result['video_id']}"
            await status_msg.edit_text(
                f"🎉 *¡Video subido exitosamente!*\n\n"
                f"📄 Página: *{page['name']}*\n"
                f"🎬 Título: *{context.user_data['video_title']}*\n"
                f"🆔 Video ID: `{result['video_id']}`\n\n"
                f"🔗 {video_url}",
                parse_mode='Markdown'
            )
            db.save_upload(user_id, page['id'], result['video_id'],
                           context.user_data['video_title'], 'success')
        else:
            await status_msg.edit_text(
                f"❌ *Error al subir a Facebook*\n\n"
                f"{result.get('error', 'Error desconocido')}\n\n"
                f"Intenta de nuevo con /upload",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error en confirm_upload: {e}")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        await status_msg.edit_text(
            f"❌ *Error inesperado*\n\n`{str(e)}`\n\nIntenta de nuevo con /upload",
            parse_mode='Markdown'
        )

    return ConversationHandler.END


async def _get_video_duration(path: str) -> int | None:
    """Intenta obtener la duración del video con ffprobe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        import json
        info = json.loads(stdout)
        return int(float(info['format']['duration']))
    except Exception:
        return None

    except Exception as e:
        logger.error(f"Error en subida: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        await query.edit_message_text(
            f"❌ *Error inesperado*\n\n"
            f"Error: {str(e)}\n\n"
            f"Intenta de nuevo con /upload",
            parse_mode='Markdown'
        )

    return ConversationHandler.END


async def pages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las páginas conectadas"""
    user_id = update.effective_user.id
    pages = db.get_pages(user_id)

    if not pages:
        await update.message.reply_text(
            "❌ No tienes páginas configuradas.\n"
            "Usa /login para conectar tu cuenta de Facebook."
        )
        return

    pages_text = "\n".join([
        f"• *{p['name']}* (ID: `{p['id']}`)"
        for p in pages
    ])

    await update.message.reply_text(
        f"📄 *Tus páginas de Facebook:*\n\n{pages_text}",
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de la conexión"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user and user.get('fb_token'):
        pages = db.get_pages(user_id)
        pages_count = len(pages) if pages else 0

        await update.message.reply_text(
            f"✅ *Estado: Conectado*\n\n"
            f"👤 Usuario FB: *{user.get('fb_user_name', 'N/A')}*\n"
            f"📄 Páginas: *{pages_count}*\n\n"
            f"Usa /upload para subir un video.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *Estado: No conectado*\n\n"
            "Usa /login para conectar tu cuenta de Facebook.",
            parse_mode='Markdown'
        )


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desconecta la cuenta de Facebook"""
    user_id = update.effective_user.id
    db.delete_user(user_id)

    await update.message.reply_text(
        "✅ *Cuenta desconectada*\n\n"
        "Tu información de Facebook ha sido eliminada.\n"
        "Usa /login para conectar de nuevo.",
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación actual"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operación cancelada.\n"
        "Usa /start para ver el menú principal."
    )
    return ConversationHandler.END


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador de botones inline del menú principal"""
    query = update.callback_query
    await query.answer()

    if query.data == "connect_fb":
        await query.message.reply_text(
            "🔑 *Conectar con Facebook*\n\n"
            "Envíame tu *Token de Acceso de Facebook*.\n\n"
            "📋 *Pasos:*\n"
            "1. Ve a: `developers.facebook.com/tools/explorer`\n"
            "2. Genera un token con permisos:\n"
            "   `pages_manage_posts`, `pages_read_engagement`\n"
            "3. Copia y envía el token aquí\n\n"
            "_(Cancela con /cancel)_",
            parse_mode='Markdown'
        )
    elif query.data == "upload_video":
        # Simular comando /upload
        fake_update = Update(update.update_id, message=query.message)
        fake_update.message.from_user = update.effective_user
        await upload_command(query.message, context)
    elif query.data == "list_pages":
        user_id = update.effective_user.id
        pages = db.get_pages(user_id)
        if pages:
            text = "\n".join([f"• *{p['name']}*" for p in pages])
            await query.message.reply_text(f"📄 *Tus páginas:*\n\n{text}", parse_mode='Markdown')
        else:
            await query.message.reply_text("No tienes páginas configuradas.")
    elif query.data == "change_account":
        await query.message.reply_text(
            "🔄 Para cambiar de cuenta, primero desconecta la actual:\n"
            "Usa /logout y luego /login"
        )
    elif query.data == "help":
        await query.message.reply_text(
            "ℹ️ Usa /help para ver la guía completa."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja errores globales"""
    logger.error(f"Error: {context.error}", exc_info=context.error)


def main():
    """Función principal"""
    token = config.TELEGRAM_TOKEN
    if not token:
        raise ValueError("❌ TELEGRAM_TOKEN no configurado en .env")

    app = Application.builder().token(token).build()

    # ConversationHandler para login
    login_conv = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_command),
        ],
        states={
            WAITING_FB_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fb_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # ConversationHandler para subida de video
    upload_conv = ConversationHandler(
        entry_points=[
            CommandHandler("upload", upload_command),
        ],
        states={
            WAITING_PAGE_SELECTION: [CallbackQueryHandler(select_page, pattern="^page_|^cancel")],
            WAITING_VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_video),  # URLs y enlaces
            ],
            WAITING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            WAITING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description),
                CommandHandler("skip", receive_description)
            ],
            WAITING_PRIVACY: [CallbackQueryHandler(receive_privacy, pattern="^privacy_")],
            CONFIRMING_UPLOAD: [CallbackQueryHandler(confirm_upload, pattern="^confirm_|^cancel_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Registrar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("pages", pages_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(login_conv)
    app.add_handler(upload_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    logger.info("🤖 Bot iniciado correctamente")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
