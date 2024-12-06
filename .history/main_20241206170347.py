import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"  # Админский юзернейм

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Инициализация базы данных
conn = sqlite3.connect("reputation.db")
cursor = conn.cursor()
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

# Инициализация бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()
router = Router()

# Функция для оборачивания текста в жирные теги
def bold(text: str) -> str:
    return f"<b>{text}</b>"

# Клавиатура главного меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True
)

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    # Если пользователь уже есть в БД, обновляем его username
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    else:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
    conn.commit()
    logger.info(f"Профиль обновлен или создан для пользователя: {tg_id} (@{username})")

    await message.answer(
        bold(f"Добро пожаловать, {message.from_user.full_name}!\nВыберите действие:"),
        reply_markup=main_menu
    )

# Обработчик кнопки "Профиль"
@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message):
    tg_id = message.from_user.id
    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()

    if user:
        reputation = user[0]
        await message.answer(bold(f"Ваш профиль\n\nРепутация: {reputation}"))
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
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_info = cursor.fetchone()
    elif input_data.isdigit():
        tg_id = int(input_data)
        cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        user_info = cursor.fetchone()

    if user_info:
        tg_id, username, reputation = user_info
    else:
        tg_id, username = None, None
        try:
            tg_user = await bot.get_chat(input_data if input_data.startswith("@") else int(input_data))
            tg_id = tg_user.id
            username = tg_user.username or f"user_{tg_id}"
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            await message.answer(bold("Пользователь не найден."))
            return

        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
        conn.commit()
        reputation = 0
        logger.info(f"Создан профиль: {tg_id} (@{username})")

    # Кнопки репутации и отзывов
    buttons = [
        [
            InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
            InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")
        ],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
    ]
    if message.from_user.username == ADMIN_USERNAME and username != ADMIN_USERNAME:
        buttons.append([InlineKeyboardButton(text="🗑️ Очистить репутацию", callback_data=f"reset_{tg_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    reputation_display = "∞" if username == ADMIN_USERNAME else reputation
    await message.answer(
        bold(f"Профиль @{username}\n\nРепутация: {reputation_display}"),
        reply_markup=markup
    )

# Функция для проверки длины отзыва
def is_valid_review(text: str) -> bool:
    words = text.split()
    return 5 <= len(words) <= 40

# Управление репутацией
@router.callback_query(F.data.startswith("add_"))
async def add_reputation_start(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await bot.register_message_handler(
        add_reputation_complete,
        lambda msg: is_valid_review(msg.text),
        state={"target_id": target_id, "changer_id": callback.from_user.id, "action": "add"}
    )

@router.callback_query(F.data.startswith("sub_"))
async def sub_reputation_start(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await bot.register_message_handler(
        add_reputation_complete,
        lambda msg: is_valid_review(msg.text),
        state={"target_id": target_id, "changer_id": callback.from_user.id, "action": "sub"}
    )

async def add_reputation_complete(message: types.Message, state):
    action = state["action"]
    target_id = state["target_id"]
    changer_id = state["changer_id"]
    review = message.text.strip()

    if action == "add":
        cursor.execute("UPDATE users SET reputation = reputation + 1 WHERE tg_id = ?", (target_id,))
    elif action == "sub":
        cursor.execute("UPDATE users SET reputation = reputation - 1 WHERE tg_id = ?", (target_id,))
    conn.commit()

    cursor.execute("INSERT INTO reviews (target_id, changer_id, review) VALUES (?, ?, ?)", (target_id, changer_id, review))
    conn.commit()

    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (target_id,))
    reputation = cursor.fetchone()[0]

    await message.answer(bold(f"Репутация обновлена: {reputation}"))
