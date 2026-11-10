import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "database.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Admin qo'shish
cur.execute("INSERT OR REPLACE INTO admins (user_id, username, full_name) VALUES (?, ?, ?)",
            (2050806082, "iskandarov_developer", "SHAHRIYOR"))

# Majburiy obunani hozircha 0 (o'chiq) qilib qo'yish
cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('force_sub_enabled', '0')")
conn.commit()
conn.close()
print("Settings updated: admin added and force_sub_enabled set to 0")
