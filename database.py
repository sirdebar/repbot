# database.py
import sqlite3
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

# Инициализация базы данных
conn = sqlite3.connect("reputation.db")
cursor = conn.cursor()

# Создание таблиц
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    captcha_passed BOOLEAN DEFAULT FALSE,
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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action TEXT DEFAULT '+REP'
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS profile_views (
    target_id INTEGER,
    viewer_id INTEGER,
    PRIMARY KEY (target_id, viewer_id)
);

""")
conn.commit()

def delete_reviews_for_user(target_id: int):
    """
    Удаляет все отзывы, связанные с целевым пользователем.
    """
    cursor.execute("DELETE FROM reviews WHERE target_id = ?", (target_id,))
    conn.commit()
    logger.info(f"Отзывы пользователя с ID {target_id} были удалены.")


def update_captcha_status(tg_id: int, status: bool):
    """
    Обновляет статус прохождения капчи для пользователя.
    """
    cursor.execute("UPDATE users SET captcha_passed = ? WHERE tg_id = ?", (status, tg_id))
    conn.commit()


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
    cursor.execute("""
        SELECT tg_id, username, reputation, captcha_passed 
        FROM users 
        WHERE tg_id = ?
    """, (tg_id,))
    return cursor.fetchone()


def get_user_by_username(username: str):
    cursor.execute("""
        SELECT tg_id, username, reputation, captcha_passed 
        FROM users 
        WHERE username = ?
    """, (username,))
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

def add_review(target_id: int, changer_id: int, review: str, action: str):
    """
    Добавление отзыва в базу данных.
    """
    cursor.execute("""
        INSERT INTO reviews (target_id, changer_id, review, action) 
        VALUES (?, ?, ?, ?)
    """, (target_id, changer_id, review, action))
    conn.commit()


def get_reviews(target_id: int, limit: int = 1, offset: int = 0):
    """
    Получение отзывов пользователя с учетом смещения и лимита.
    Конвертация времени в часовой пояс МСК.
    """
    cursor.execute("""
        SELECT reviews.review, reviews.timestamp, reviews.action,
               COALESCE(users.username, 'Unknown') AS username
        FROM reviews
        LEFT JOIN users ON reviews.changer_id = users.tg_id
        WHERE reviews.target_id = ?
        ORDER BY reviews.timestamp DESC
        LIMIT ? OFFSET ?
    """, (target_id, limit, offset))
    reviews = cursor.fetchall()

    # Конвертация времени из UTC в МСК
    msk_tz = pytz.timezone("Europe/Moscow")
    reviews_with_msk_time = []
    for review in reviews:
        review_text, timestamp, action, username = review
        utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        msk_time = utc_time.replace(tzinfo=pytz.utc).astimezone(msk_tz).strftime("%Y-%m-%d %H:%M:%S")
        reviews_with_msk_time.append((review_text, msk_time, action, username))

    return reviews_with_msk_time

def can_change_reputation(changer_id: int, target_id: int) -> bool:
    """
    Проверяет, может ли пользователь изменить репутацию другого пользователя.
    """
    cursor.execute("""
        SELECT last_change FROM reputation_changes
        WHERE changer_id = ? AND target_id = ?
    """, (changer_id, target_id))
    result = cursor.fetchone()

    if result:
        last_change = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        # Ограничение на 5 секунд (или неделя в финальной версии)
        return datetime.now() - last_change > timedelta(days=7)
    return True

def update_reputation_change_time(changer_id: int, target_id: int):
    """
    Обновляет запись о последнем изменении репутации.
    """
    cursor.execute("""
        INSERT OR REPLACE INTO reputation_changes (changer_id, target_id, last_change)
        VALUES (?, ?, ?)
    """, (changer_id, target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def increment_profile_views(target_id: int, viewer_id: int):
    cursor.execute("""
        INSERT OR IGNORE INTO profile_views (target_id, viewer_id)
        VALUES (?, ?)
    """, (target_id, viewer_id))
    conn.commit()

def get_profile_view_count(target_id: int):
    cursor.execute("""
        SELECT COUNT(*) FROM profile_views
        WHERE target_id = ?
    """, (target_id,))
    return cursor.fetchone()[0]
