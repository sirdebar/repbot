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

def add_user(tg_id: int, username: str):
    """
    Добавление пользователя в базу данных.
    """
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    logger.info(f"Пользователь {tg_id} (@{username}) добавлен в базу.")

def update_username(tg_id: int, username: str):
    """
    Обновление username пользователя.
    """
    cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    conn.commit()
    logger.info(f"Username пользователя {tg_id} обновлен на @{username}.")

def get_user_by_tg_id(tg_id: int):
    """
    Получение информации о пользователе по Telegram ID.
    """
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def get_user_by_username(username: str):
    """
    Получение информации о пользователе по username.
    """
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone()

def update_reputation(target_id: int, value: int):
    """
    Изменение репутации пользователя.
    """
    cursor.execute("UPDATE users SET reputation = reputation + ? WHERE tg_id = ?", (value, target_id))
    conn.commit()
    logger.info(f"Репутация пользователя {target_id} изменена на {value}.")

def reset_reputation(target_id: int):
    """
    Обнуление репутации пользователя.
    """
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (target_id,))
    conn.commit()
    logger.info(f"Репутация пользователя {target_id} сброшена.")

def add_review(target_id: int, changer_id: int, review: str):
    """
    Добавление отзыва.
    """
    cursor.execute("INSERT INTO reviews (target_id, changer_id, review) VALUES (?, ?, ?)", (target_id, changer_id, review))
    conn.commit()
    logger.info(f"Добавлен отзыв от {changer_id} для {target_id}.")

def get_reviews(target_id: int, limit: int, offset: int):
    """
    Получение отзывов пользователя.
    """
    cursor.execute("SELECT review FROM reviews WHERE target_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?", 
                   (target_id, limit, offset))
    return cursor.fetchall()

def can_change_reputation(changer_id: int, target_id: int):
    """
    Проверка, может ли пользователь изменить репутацию другого пользователя (ограничение раз в неделю).
    """
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
    """
    Обновление времени изменения репутации.
    """
    cursor.execute("""
        INSERT OR REPLACE INTO reputation_changes (changer_id, target_id, last_change)
        VALUES (?, ?, ?)
    """, (changer_id, target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
Привет, помоги с ботом на aiogram 3.12.0
Есть ошибки
1. Самый главный нюанс. Сейчас если пользователя нет в бд (не добавился путем /start), то его нельзя найти. Но мне нужно сделать так, что если например человек выполняет поиск несуществующего пользователя (который пока что не в бд и не нажал /start), то бот автоматически добавляет содержимое запроса (ну то есть тег или айди) в бд и создает профиль автоматически. То есть чтобы профиль мог быть даже у людей которые не заходили в бота. А если человек все же когда то зайдет в бота и нажмет /start впервые, то если его тег или айди соотвествуют каким то из бд, то профиля свяжутся и репутация (если она есть в бд сразу подвяжется) будет уже у человека, который даже не заходил в бота.
2.  Кнопка отзывов не работает, при нажатии Отзывы ничего не происходит, а должен бот присылать сообщение по типу
{status +rep или -rep} Оставил: {username того кто оставил} {дата добавления отзыва}
{текст отзыва}
под сообщением кнопки закрыть (удаляет сообщение бота) и стрелки право и лево чтобы листать (простая пагинация)
3. Сейчас можно оставить много отзывов, а должно быть ограничение 1 изменения репутации с отзывом в неделю
Вот мой код database.py
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

def add_user(tg_id: int, username: str):
    """
    Добавление пользователя в базу данных.
    """
    cursor.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    logger.info(f"Пользователь {tg_id} (@{username}) добавлен в базу.")

def update_username(tg_id: int, username: str):
    """
    Обновление username пользователя.
    """
    cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    conn.commit()
    logger.info(f"Username пользователя {tg_id} обновлен на @{username}.")

def get_user_by_tg_id(tg_id: int):
    """
    Получение информации о пользователе по Telegram ID.
    """
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def get_user_by_username(username: str):
    """
    Получение информации о пользователе по username.
    """
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone()

def update_reputation(target_id: int, value: int):
    """
    Изменение репутации пользователя.
    """
    cursor.execute("UPDATE users SET reputation = reputation + ? WHERE tg_id = ?", (value, target_id))
    conn.commit()
    logger.info(f"Репутация пользователя {target_id} изменена на {value}.")

def reset_reputation(target_id: int):
    """
    Обнуление репутации пользователя.
    """
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (target_id,))
    conn.commit()
    logger.info(f"Репутация пользователя {target_id} сброшена.")

def add_review(target_id: int, changer_id: int, review: str):
    """
    Добавление отзыва.
    """
    cursor.execute("INSERT INTO reviews (target_id, changer_id, review) VALUES (?, ?, ?)", (target_id, changer_id, review))
    conn.commit()
    logger.info(f"Добавлен отзыв от {changer_id} для {target_id}.")

def get_reviews(target_id: int, limit: int, offset: int):
    """
    Получение отзывов пользователя.
    """
    cursor.execute("SELECT review FROM reviews WHERE target_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?", 
                   (target_id, limit, offset))
    return cursor.fetchall()

def can_change_reputation(changer_id: int, target_id: int):
    """
    Проверка, может ли пользователь изменить репутацию другого пользователя (ограничение раз в неделю).
    """
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
    """
    Обновление времени изменения репутации.
    """
    cursor.execute("""
        INSERT OR REPLACE INTO reputation_changes (changer_id, target_id, last_change)
        VALUES (?, ?, ?)
    """, (changer_id, target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from database import (
    add_user, update_username, get_user_by_tg_id, get_user_by_username,
    update_reputation, reset_reputation, add_review, get_reviews,
    can_change_reputation, update_reputation_change_time
)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"  # Админский юзернейм

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Главная клавиатура
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True
)

# Функция для оборачивания текста в жирные теги
def bold(text: str) -> str:
    return f"<b>{text}</b>"

# Состояния для FSM
class ReviewStates(StatesGroup):
    waiting_for_review = State()

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    user = get_user_by_tg_id(tg_id)
    if user:
        update_username(tg_id, username)
    else:
        # Проверяем, есть ли пользователь с этим username
        existing_user = get_user_by_username(username)
        if existing_user:
            update_username(existing_user[0], username)
        else:
            add_user(tg_id, username)

    await message.answer(
        bold(f"Добро пожаловать, {message.from_user.full_name}!\nВыберите действие:"),
        reply_markup=main_menu
    )

# Обработчик кнопки "Профиль"
@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message):
    tg_id = message.from_user.id
    user = get_user_by_tg_id(tg_id)

    if user:
        _, _, reputation = user
        reviews = get_reviews(tg_id, limit=1, offset=0)
        reviews_text = f"\n\nПоследний отзыв: {reviews[0][0]}" if reviews else "\n\nОтзывов пока нет."
        await message.answer(bold(f"Ваш профиль\n\nРепутация: {reputation}{reviews_text}"))
    else:
        await message.answer(bold("Ваш профиль не найден. Попробуйте нажать /start."))

# Обработчик кнопки "Найти"
@router.message(F.text == "Найти")
async def find_handler(message: types.Message):
    await message.answer(bold("Введите @тег или ID пользователя:"))

# Поиск пользователя
@router.message(F.text.regexp(r"^@|^\d+$"))
async def search_user_handler(message: types.Message):
    input_data = message.text.strip()
    user_info = None

    if input_data.startswith("@"):
        username = input_data[1:]
        user_info = get_user_by_username(username)
    elif input_data.isdigit():
        tg_id = int(input_data)
        user_info = get_user_by_tg_id(tg_id)

    if user_info:
        tg_id, username, reputation = user_info
    else:
        # Создание нового профиля для отсутствующего пользователя
        try:
            tg_user = await bot.get_chat(input_data if input_data.startswith("@") else int(input_data))
            tg_id = tg_user.id
            username = tg_user.username or f"user_{tg_id}"
            add_user(tg_id, username)
            reputation = 0
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            await message.answer(bold("Пользователь не найден."))
            return

    # Запрет на изменение своей репутации
    if tg_id == message.from_user.id:
        await message.answer(bold("Вы не можете изменять свою репутацию."))
        return

    # Формирование интерфейса
    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
    ]
    if message.from_user.username == ADMIN_USERNAME:
        buttons.append([InlineKeyboardButton(text="🗑️ Очистить репутацию", callback_data=f"reset_{tg_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    reputation_display = "∞" if username == ADMIN_USERNAME else reputation
    await message.answer(
        bold(f"Профиль @{username}\n\nРепутация: {reputation_display}"),
        reply_markup=markup
    )

# Управление репутацией
@router.callback_query(F.data.startswith("add_"))
async def add_reputation_start(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])

    # Запрет на изменение своей репутации
    if target_id == callback.from_user.id:
        await callback.answer("Вы не можете изменять свою репутацию.", show_alert=True)
        return

    # Установка состояния ожидания отзыва
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await state.set_state(ReviewStates.waiting_for_review)
    await state.update_data(target_id=target_id, action="add", changer_id=callback.from_user.id)

@router.callback_query(F.data.startswith("sub_"))
async def sub_reputation_start(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])

    # Запрет на изменение своей репутации
    if target_id == callback.from_user.id:
        await callback.answer("Вы не можете изменять свою репутацию.", show_alert=True)
        return

    # Установка состояния ожидания отзыва
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await state.set_state(ReviewStates.waiting_for_review)
    await state.update_data(target_id=target_id, action="sub", changer_id=callback.from_user.id)

@router.message(ReviewStates.waiting_for_review)
async def handle_review_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    action = data["action"]
    changer_id = data["changer_id"]
    review = message.text.strip()

    # Проверка длины отзыва
    if not (5 <= len(review.split()) <= 40):
        await message.answer(bold("Отзыв должен содержать от 5 до 40 слов. Попробуйте снова:"))
        return

    # Обновление репутации
    update_reputation(target_id, 1 if action == "add" else -1)
    add_review(target_id, changer_id, review)
    update_reputation_change_time(changer_id, target_id)

    # Завершение состояния
    await state.clear()
    user = get_user_by_tg_id(target_id)
    await message.answer(bold(f"Репутация пользователя @{user[1]} успешно обновлена."))

# Очистка репутации
@router.callback_query(F.data.startswith("reset_"))
async def reset_reputation_handler(callback: types.CallbackQuery):
    if callback.from_user.username != ADMIN_USERNAME:
        await callback.answer("У вас нет прав для этой команды.", show_alert=True)
        return

    target_id = int(callback.data.split("_")[1])
    reset_reputation(target_id)
    await callback.message.edit_text(bold("Репутация сброшена."))
    logger.info(f"Репутация пользователя {target_id} была сброшена администратором.")

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())