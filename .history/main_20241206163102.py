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
import sqlite3

# Настройки бота
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
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
conn.commit()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()

# Клавиатура главного меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    # Создаем профиль, если не существует
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
        conn.commit()
        logger.info(f"Создан профиль для пользователя: {tg_id} (@{username})")

    await message.answer(
        f"**Добро пожаловать, {message.from_user.full_name}!**\nВыберите действие:",
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
        await message.answer(f"**Ваш профиль**\n\nРепутация: **{reputation}**")
    else:
        await message.answer("**Ваш профиль не найден. Попробуйте нажать /start.**")

# Обработчик кнопки "Найти"
@router.message(F.text == "Найти")
async def find_handler(message: types.Message):
    await message.answer("**Введите @тег или ID пользователя:**")

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
        try:
            tg_user = await bot.get_chat(input_data if input_data.startswith("@") else int(input_data))
            tg_id = tg_user.id
            username = tg_user.username or f"user_{tg_id}"

            cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
            conn.commit()
            reputation = 0
            logger.info(f"Создан профиль: {tg_id} (@{username})")
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            await message.answer("**Пользователь не найден.**")
            return

    # Кнопки репутации
    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")]
    ]
    if message.from_user.username == ADMIN_USERNAME and username != ADMIN_USERNAME:
        buttons.append([InlineKeyboardButton(text="🗑️ Очистить репутацию", callback_data=f"reset_{tg_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    reputation_display = "∞" if username == ADMIN_USERNAME else reputation
    await message.answer(f"**Профиль @{username}**\n\nРепутация: **{reputation_display}**", reply_markup=markup)

# Управление репутацией
@router.callback_query(F.data.startswith("add_"))
async def add_reputation(callback: types.CallbackQuery):
    tg_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE users SET reputation = reputation + 1 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    await callback.answer("Репутация увеличена!")

@router.callback_query(F.data.startswith("sub_"))
async def sub_reputation(callback: types.CallbackQuery):
    tg_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE users SET reputation = reputation - 1 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    await callback.answer("Репутация уменьшена!")

@router.callback_query(F.data.startswith("reset_"))
async def reset_reputation(callback: types.CallbackQuery):
    tg_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    await callback.answer("Репутация сброшена!")

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
