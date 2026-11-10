import sqlite3
import os
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Adminlar jadvali
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Kanallar jadvali (Majburiy obuna va post joylanadigan kanallar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        title TEXT,
        username TEXT,
        invite_link TEXT,
        is_mandatory INTEGER DEFAULT 1,
        is_post_target INTEGER DEFAULT 0
    )
    """)

    # 3. O'yinlar va Dasturlar jadvali
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT, -- 'game' yoki 'app'
        title TEXT,
        description TEXT,
        genre TEXT,
        android_ver TEXT,
        version TEXT,
        mod_info TEXT,
        photo_file_id TEXT,
        file_id TEXT, -- APK yoki fayl file_id
        file_name TEXT,
        channel_id TEXT,
        post_message_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. Foydalanuvchilar jadvali
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Sozlamalar jadvali
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

# --- Admin amallari ---
def add_admin(user_id: int, username: str = "", full_name: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO admins (user_id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name))
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    if user_id == 2050806082:
        return True
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    res = cur.fetchone()
    cur.execute("SELECT COUNT(*) as cnt FROM admins")
    count = cur.fetchone()['cnt']
    conn.close()
    if count == 0:
        return True
    return res is not None

def get_all_admins():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Kanallar amallari ---
def add_channel(channel_id: str, title: str, username: str, invite_link: str, is_mandatory: int = 1, is_post_target: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO channels (channel_id, title, username, invite_link, is_mandatory, is_post_target)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (str(channel_id), title, username, invite_link, is_mandatory, is_post_target))
    conn.commit()
    conn.close()

def remove_channel(channel_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE channel_id = ? OR id = ?", (str(channel_id), channel_id))
    conn.commit()
    conn.close()

def get_mandatory_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels WHERE is_mandatory = 1")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_target_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels WHERE is_post_target = 1")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- O'yinlar / Dasturlar amallari ---
def add_item(item_type: str, title: str, description: str, genre: str,
             android_ver: str, version: str, mod_info: str,
             photo_file_id: str, file_id: str = None, file_name: str = None,
             channel_id: str = None, post_message_id: int = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO items (item_type, title, description, genre, android_ver, version, mod_info, photo_file_id, file_id, file_name, channel_id, post_message_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (item_type, title, description, genre, android_ver, version, mod_info, photo_file_id, file_id, file_name, channel_id, post_message_id))
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return item_id

def get_item(item_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_items(item_type: str = None, genre: str = None, query: str = None, limit: int = 20, offset: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if item_type:
        sql += " AND item_type = ?"
        params.append(item_type)
    if genre:
        sql += " AND genre LIKE ?"
        params.append(f"%{genre}%")
    if query:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        params.append(f"%{query}%")
        params.append(f"%{query}%")
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_genres(item_type: str = 'game'):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT genre FROM items WHERE item_type = ? AND genre IS NOT NULL AND genre != ''", (item_type,))
    rows = cur.fetchall()
    conn.close()
    return [r['genre'] for r in rows]

def delete_item(item_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# --- Foydalanuvchilar amallari ---
def add_user(user_id: int, username: str = "", full_name: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO users (user_id, username, full_name)
    VALUES (?, ?, ?)
    """, (user_id, username, full_name))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def count_users() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM users")
    res = cur.fetchone()['c']
    conn.close()
    return res

def count_items(item_type: str = None) -> int:
    conn = get_connection()
    cur = conn.cursor()
    if item_type:
        cur.execute("SELECT COUNT(*) as c FROM items WHERE item_type = ?", (item_type,))
    else:
        cur.execute("SELECT COUNT(*) as c FROM items")
    res = cur.fetchone()['c']
    conn.close()
    return res

# Sozlamalar
def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Baza muvaffaqiyatli ishga tushirildi!")
