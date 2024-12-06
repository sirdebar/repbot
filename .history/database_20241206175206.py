import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Инициализация базы данных
conn = sqlite3.connect("reputation.db")
cursor = conn.cursor()

# Создание таблиц
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    reputation INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS reputation_changes (
    changer_id INTEGER,
    target_id INTEGER,
    last_change TIMESTAMP,
    PRIMARY KEY (changer_id, target_id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    changer_id INTEGER,
    review TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# Функции работы с пользователями
def add_user(tg_id: int, username: str):
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    logger.info(f"Пользователь {tg_id} (@{username}) добавлен в базу.")

def update_username(tg_id: int, username: str):
    cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    conn.commit()

def get_user_by_tg_id(tg_id: int):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def get_user_by_username(username: str):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone()

# Функции работы с репутацией
def update_reputation(target_id: int, value: int):
    cursor.execute("UPDATE users SET reputation = reputation + ? WHERE tg_id = ?", (value, target_id))
    conn.commit()

def reset_reputation(target_id: int):
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (target_id,))
    conn.commit()

def can_change_reputation(changer_id: int, target_id: int):
    cursor.execute("""
        SELECT last_change FROM reputation_changes
        WHERE changer_id = ? AND target_id = ?
    """, (changer_id, target_id))
    result = cursor.fetchone()

    if result:
        last_change = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now() - last_change > timedelta(weeks=1)
    return True

def update_reputation_change_time(changer_id: int, target_id: int):
    cursor.execute("""
        INSERT OR REPLACE INTO reputation_changes (changer_id, target_id, last_change)
        VALUES (?, ?, ?)
    """, (changer_id, target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# Функции работы с отзывами
def add_review(target_id: int, changer_id: int, review: str):
    cursor.execute("INSERT INTO reviews (target_id, changer_id, review) VALUES (?, ?, ?)", (target_id, changer_id, review))
    conn.commit()

def get_reviews(target_id: int, limit: int, offset: int):
    cursor.execute("""
        SELECT review, changer_id, timestamp FROM reviews
        WHERE target_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (target_id, limit, offset))
    return cursor.fetchall()
