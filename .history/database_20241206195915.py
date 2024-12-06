# database.py
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

def update_reviews_target_id_from_username(username: str, new_tg_id: int):
    """
    Обновляет target_id в таблице reviews для отзывов, связанных с username.
    """
    cursor.execute("""
        UPDATE reviews
        SET target_id = ?
        WHERE target_id IS NULL AND EXISTS (
            SELECT 1 FROM users WHERE username = ?
        )
    """, (new_tg_id, username))
    affected_rows = cursor.rowcount
    conn.commit()
    logger.info(f"Отзывы для @{username} привязаны к tg_id {new_tg_id}. Обновлено {affected_rows} записей.")

def update_related_tg_id(old_tg_id: int, new_tg_id: int):
    """
    Обновляет tg_id в связанных таблицах, если профиль был обновлен.
    """
    # Обновляем tg_id в таблице отзывов
    cursor.execute("UPDATE reviews SET target_id = ? WHERE target_id = ?", (new_tg_id, old_tg_id))
    cursor.execute("UPDATE reviews SET changer_id = ? WHERE changer_id = ?", (new_tg_id, old_tg_id))

    # Обновляем tg_id в таблице репутации
    cursor.execute("UPDATE reputation_changes SET target_id = ? WHERE target_id = ?", (new_tg_id, old_tg_id))
    cursor.execute("UPDATE reputation_changes SET changer_id = ? WHERE changer_id = ?", (new_tg_id, old_tg_id))

    conn.commit()
    logger.info(f"tg_id обновлен во всех связанных таблицах: {old_tg_id} -> {new_tg_id}")


def add_user(tg_id: int, username: str):
    if tg_id is None:
        raise ValueError("tg_id не может быть None.")
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    logger.info(f"Пользователь {tg_id} (@{username}) добавлен в базу.")

def update_tg_id_for_user(username: str, tg_id: int):
    """
    Обновляет tg_id для пользователя с данным username.
    """
    cursor.execute("UPDATE users SET tg_id = ? WHERE username = ?", (tg_id, username))
    conn.commit()
    logger.info(f"tg_id пользователя @{username} обновлен на {tg_id}.")

def update_username(tg_id: int, username: str):
    cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    conn.commit()
    logger.info(f"Username пользователя {tg_id} обновлен на @{username}.")

def get_user_by_tg_id(tg_id: int):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def get_user_by_username(username: str):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone()

def create_or_get_user(tg_id: int, username: str):
    user = get_user_by_tg_id(tg_id)
    if not user:
        user = get_user_by_username(username)
        if not user:
            add_user(tg_id, username)
            user = get_user_by_tg_id(tg_id)
    return user

def update_reputation(target_id: int, value: int):
    cursor.execute("UPDATE users SET reputation = reputation + ? WHERE tg_id = ?", (value, target_id))
    conn.commit()

def reset_reputation(target_id: int):
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (target_id,))
    conn.commit()

def add_review(target_id: int, changer_id: int, review: str, username: str = None):
    """
    Добавляет отзыв. Если target_id отсутствует, используется username.
    """
    if not target_id and username:
        cursor.execute("""
            INSERT INTO reviews (target_id, changer_id, review)
            VALUES ((SELECT tg_id FROM users WHERE username = ?), ?, ?)
        """, (username, changer_id, review))
    elif target_id:
        cursor.execute("""
            INSERT INTO reviews (target_id, changer_id, review)
            VALUES (?, ?, ?)
        """, (target_id, changer_id, review))
    else:
        logger.error("Не удалось добавить отзыв: отсутствуют target_id и username.")
        raise ValueError("Необходимо указать target_id или username.")
    conn.commit()
    logger.info(f"Отзыв добавлен: changer_id={changer_id}, target_id={target_id}, review='{review}'.")

def get_reviews(target_id: int, limit: int, offset: int):
    cursor.execute("""
        SELECT reviews.review, reviews.timestamp, users.username
        FROM reviews
        JOIN users ON reviews.changer_id = users.tg_id
        WHERE reviews.target_id = ?
        ORDER BY reviews.timestamp DESC
        LIMIT ? OFFSET ?
    """, (target_id, limit, offset))
    return cursor.fetchall()

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