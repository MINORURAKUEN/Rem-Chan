"""
Base de datos SQLite para almacenar usuarios y páginas
"""

import sqlite3
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "bot_data.db"


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Crea las tablas si no existen"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    fb_token TEXT,
                    fb_user_id TEXT,
                    fb_user_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    page_id TEXT,
                    page_name TEXT,
                    page_token TEXT,
                    page_category TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    page_id TEXT,
                    video_id TEXT,
                    title TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_user(self, user_id: int, data: dict):
        """Guarda o actualiza un usuario"""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO users (user_id, fb_token, fb_user_id, fb_user_name, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    fb_token = excluded.fb_token,
                    fb_user_id = excluded.fb_user_id,
                    fb_user_name = excluded.fb_user_name,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                data.get('fb_token'),
                data.get('fb_user_id'),
                data.get('fb_user_name')
            ))
            conn.commit()

    def get_user(self, user_id: int) -> dict | None:
        """Obtiene un usuario por su ID"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT user_id, fb_token, fb_user_id, fb_user_name FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'fb_token': row[1],
                    'fb_user_id': row[2],
                    'fb_user_name': row[3]
                }
            return None

    def delete_user(self, user_id: int):
        """Elimina un usuario y sus páginas"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM pages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()

    def save_pages(self, user_id: int, pages: list):
        """Guarda las páginas de un usuario"""
        with self._get_conn() as conn:
            # Eliminar páginas anteriores
            conn.execute("DELETE FROM pages WHERE user_id = ?", (user_id,))
            # Insertar nuevas
            for page in pages:
                conn.execute("""
                    INSERT INTO pages (user_id, page_id, page_name, page_token, page_category)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    page.get('id'),
                    page.get('name'),
                    page.get('access_token', ''),
                    page.get('category', '')
                ))
            conn.commit()

    def get_pages(self, user_id: int) -> list:
        """Obtiene las páginas de un usuario"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT page_id, page_name, page_token, page_category FROM pages WHERE user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'access_token': row[2],
                    'category': row[3]
                }
                for row in rows
            ]

    def save_upload(self, user_id: int, page_id: str, video_id: str, title: str, status: str):
        """Guarda un registro de subida"""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO upload_history (user_id, page_id, video_id, title, status)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, page_id, video_id, title, status))
            conn.commit()
