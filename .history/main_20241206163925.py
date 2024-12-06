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
from aiogram.enums.parse_mode import ParseMode

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
conn.commit()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()

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

    # Создаем профиль, если не существует
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))
        conn.commit()
        logger.info(f"Создан профиль для пользователя: {tg_id} (@{username})")

    await message.answer(
        f"<b>Добро пожаловать, {message.from_user.full_name}!</b>\nВыберите действие:",
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
        await message.answer(f"<b>Ваш профиль</b>\n\nРепутация: <b>{reputation}</b>")
    else:
        await message.answer("<b>Ваш профиль не найден. Попробуйте нажать /start.</b>")

# Обработчик кнопки "Найти"
@router.message(F.text == "Найти")
async def find_handler(message: types.Message):
    await message.answer("<b>Введите @тег или ID пользователя:</b>")

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
            await message.answer("<b>Пользователь не найден.</b>")
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
    await message.answer(f"<b>Профиль @{username}</b>\n\nРепутация: <b>{reputation_display}</b>", reply_markup=markup)

# Проверка ограничения на изменение репутации
def can_change_reputation(changer_id, target_id):
    cursor.execute("""
        SELECT last_change FROM reputation_changes
        WHERE changer_id = ? AND target_id = ?
    """, (changer_id, target_id))
    result = cursor.fetchone()

    if result:
        last_change = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now() - last_change > timedelta(weeks=1)
    return True

# Обновление времени изменения репутации
def update_change_time(changer_id, target_id):
    cursor.execute("""
        INSERT OR REPLACE INTO reputation_changes (changer_id, target_id, last_change)
        VALUES (?, ?, ?)
    """, (changer_id, target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# Управление репутацией
@router.callback_query(F.data.startswith("add_"))
async def add_reputation(callback: types.CallbackQuery):
    changer_id = callback.from_user.id
    target_id = int(callback.data.split("_")[1])

    if not can_change_reputation(changer_id, target_id):
        await callback.answer("Вы можете изменить репутацию этого пользователя только раз в неделю.", show_alert=True)
        return

    cursor.execute("UPDATE users SET reputation = reputation + 1 WHERE tg_id = ?", (target_id,))
    conn.commit()
    update_change_time(changer_id, target_id)

    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (target_id,))
    reputation = cursor.fetchone()[0]

    await callback.message.edit_text(
        f"<b>Профиль</b>\n\nРепутация: <b>{reputation}</b>", reply_markup=callback.message.reply_markup
    )
    await callback.answer("Репутация увеличена!")

@router.callback_query(F.data.startswith("sub_"))
async def sub_reputation(callback: types.CallbackQuery):
    changer_id = callback.from_user.id
    target_id = int(callback.data.split("_")[1])

    if not can_change_reputation(changer_id, target_id):
        await callback.answer("Вы можете изменить репутацию этого пользователя только раз в неделю.", show_alert=True)
        return

    cursor.execute("UPDATE users SET reputation = reputation - 1 WHERE tg_id = ?", (target_id,))
    conn.commit()
    update_change_time(changer_id, target_id)

    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (target_id,))
    reputation = cursor.fetchone()[0]

    await callback.message.edit_text(
        f"<b>Профиль</b>\n\nРепутация: <b>{reputation}</b>", reply_markup=callback.message.reply_markup
    )
    await callback.answer("Репутация уменьшена!")

@router.callback_query(F.data.startswith("reset_"))
async def reset_reputation(callback: types.CallbackQuery):
    if callback.from_user.username != ADMIN_USERNAME:
        await callback.answer("У вас нет прав для этой команды.", show_alert=True)
        return

    target_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE users SET reputation = 0 WHERE tg_id = ?", (target_id,))
    conn.commit()

    await callback.message.edit_text(
        f"<b>Профиль</b>\n\nРепутация: <b>0</b>", reply_markup=callback.message.reply_markup
    )
    await callback.answer("Репутация сброшена!")

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
