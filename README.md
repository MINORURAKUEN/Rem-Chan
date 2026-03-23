# 🤖 Bot de Telegram para Subir Videos a Facebook

Bot que permite subir videos de **24 minutos o más** directamente a páginas de Facebook desde Telegram.

---

## 📋 Requisitos

- Python 3.11+
- Una cuenta de Telegram
- Una app de Facebook (para obtener tokens)
- Páginas de Facebook donde subir los videos

---

## ⚙️ Instalación

### 1. Clonar / descargar los archivos

```bash
mkdir fb-video-bot && cd fb-video-bot
# Copia todos los archivos del bot aquí
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Edita el archivo `.env` y agrega tu token de Telegram:

```
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## 🔑 Crear el Bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Elige un nombre y username para tu bot
4. Copia el **token** que te da BotFather
5. Pégalo en el archivo `.env`

---

## 🔑 Obtener Token de Facebook

### Opción A: Graph API Explorer (recomendado para pruebas)

1. Ve a [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
2. Selecciona tu aplicación (o crea una nueva)
3. Haz clic en **"Generate Access Token"**
4. Selecciona los permisos:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `pages_show_list`
   - `publish_video`
5. Copia el token generado

### Opción B: Token de Larga Duración (recomendado para producción)

Los tokens del Explorer duran ~1 hora. Para tokens más duraderos:

```bash
# Intercambiar por token de larga duración (60 días)
curl "https://graph.facebook.com/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=TU_APP_ID
  &client_secret=TU_APP_SECRET
  &fb_exchange_token=TOKEN_CORTO"
```

### Crear una Aplicación de Facebook

1. Ve a [developers.facebook.com](https://developers.facebook.com)
2. Clic en **"Mis Apps"** → **"Crear App"**
3. Selecciona tipo: **"Empresa"**
4. Agrega el producto **"Facebook Login"**
5. En configuración, copia tu `App ID` y `App Secret`

---

## ▶️ Ejecutar el Bot

```bash
python bot.py
```

Para ejecutar en segundo plano (Linux):

```bash
nohup python bot.py > bot.log 2>&1 &
```

Con systemd (servicio permanente):

```ini
# /etc/systemd/system/fbbot.service
[Unit]
Description=Telegram FB Video Bot
After=network.target

[Service]
WorkingDirectory=/ruta/al/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
User=tu_usuario

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable fbbot
sudo systemctl start fbbot
```

---

## 🎮 Uso del Bot

### Comandos disponibles:

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal |
| `/login` | Conectar cuenta de Facebook |
| `/upload` | Subir un video |
| `/pages` | Ver páginas conectadas |
| `/status` | Estado de la conexión |
| `/logout` | Desconectar cuenta |
| `/help` | Ayuda completa |
| `/cancel` | Cancelar operación actual |

### Flujo de uso:

1. `/start` → Ver menú principal
2. `/login` → Pegar token de Facebook
3. `/upload` → Seleccionar página → Enviar video → Poner título → Descripción → Privacidad → Confirmar

---

## 📹 Requisitos del Video

| Parámetro | Valor |
|-----------|-------|
| Duración mínima | **24 minutos** |
| Tamaño máximo | 10 GB |
| Formatos | MP4, AVI, MOV, MKV |
| Resolución recomendada | 720p o superior |

---

## 🔒 Seguridad

- Los tokens de Facebook se almacenan en una base de datos SQLite local
- El mensaje con el token se elimina automáticamente del chat
- Los archivos temporales se eliminan después de la subida
- Cada usuario solo ve sus propias páginas y uploads

---

## 📁 Estructura del Proyecto

```
fb-video-bot/
├── bot.py              # Bot principal de Telegram
├── facebook_uploader.py # Módulo de subida a Facebook
├── database.py         # Base de datos SQLite
├── config.py           # Configuración
├── requirements.txt    # Dependencias Python
├── .env.example        # Ejemplo de configuración
├── .env                # Tu configuración (no subir a git)
├── bot_data.db         # Base de datos (se crea automáticamente)
└── README.md           # Esta documentación
```

---

## ⚠️ Notas Importantes

- La subida de videos grandes puede tomar varios minutos
- Telegram tiene un límite de descarga de bots; para videos muy grandes (>2GB) considera usar URLs directas
- Los tokens de Facebook del Explorer expiran en ~1 hora; usa tokens de larga duración para producción
- Asegúrate de tener los permisos correctos en tu app de Facebook antes de subir

---

## 🐛 Solución de Problemas

**Error: "Token inválido"**
→ Verifica que el token sea correcto y no haya expirado

**Error: "No se encontraron páginas"**
→ Asegúrate de tener el permiso `pages_show_list` y `pages_manage_posts`

**Error: "Video muy corto"**
→ El video debe durar al menos 24 minutos (1440 segundos)

**El bot no responde**
→ Verifica que `TELEGRAM_TOKEN` esté correctamente configurado en `.env`
