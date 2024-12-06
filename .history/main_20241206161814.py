# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, Text
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"  # Задаем юзернейм админа

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

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
conn.commit()

# Клавиатура главного меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"
    
    # Создание профиля, если он не существует
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
        conn.commit()
        logger.info(f"Создан профиль для пользователя {tg_id} (@{username})")
    else:
        logger.info(f"Пользователь {tg_id} (@{username}) уже существует")
    
    await message.answer(f"**Добро пожаловать, {message.from_user.full_name}!**\n\nВыберите действие:", reply_markup=main_menu)

# Обработчик кнопки "Профиль"
@dp.message(Text("Профиль"))
async def view_profile(message: types.Message):
    tg_id = message.from_user.id
    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()
    
    if user:
        reputation = user[0]
        logger.info(f"Просмотр профиля {tg_id}")
        await message.answer(f"**Ваш профиль**\n\nРепутация: **{reputation}**")
    else:
        logger.warning(f"Попытка доступа к несуществующему профилю {tg_id}")
        await message.answer("**Ваш профиль не найден. Попробуйте нажать /start.**")

# Обработчик кнопки "Найти"
@dp.message(Text("Найти"))
async def find_user(message: types.Message):
    await message.answer("**Введите @тег или ID пользователя:**")

@dp.message(lambda msg: msg.text.startswith("@") or msg.text.isdigit())
async def search_user(message: types.Message):
    input_data = message.text.strip()
    
    # Поиск пользователя
    if input_data.startswith("@"):
        username = input_data[1:]
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    else:
        try:
            tg_id = int(input_data)
            cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            user = cursor.fetchone()
        except ValueError:
            logger.error(f"Некорректный ID: {input_data}")
            await message.answer("**Некорректный ID. Попробуйте снова.**")
            return
    
    if user:
        tg_id, username, reputation = user
    else:
        try:
            user_info = await bot.get_chat(int(input_data) if input_data.isdigit() else input_data)
            tg_id = user_info.id
            username = user_info.username or f"user_{tg_id}"
            
            # Создаем профиль, если его нет
            cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
            conn.commit()
            reputation = 0
            logger.info(f"Создан профиль через поиск для {tg_id} (@{username})")
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя: {e}")
            await message.answer("**Пользователь не найден.**")
            return

    # Формируем профиль пользователя
    profile_text = f"**Профиль @{username}**\n\nРепутация: **{'∞' if username == ADMIN_USERNAME else reputation}**"
    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP",
