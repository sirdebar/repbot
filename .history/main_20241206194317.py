# main.py
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
    create_or_get_user, update_username, get_user_by_tg_id, get_user_by_username,
    update_reputation, reset_reputation, add_review, get_reviews,
    can_change_reputation, update_reputation_change_time, add_user, update_tg_id_for_user,
    update_related_tg_id
)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"

# Инициализация ботаНужна твоя помощь, проанализируй код и выдай места которые нужно добавить/исправить
database.py
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

def add_review(target_id: int, changer_id: int, review: str):
    cursor.execute("INSERT INTO reviews (target_id, changer_id, review) VALUES (?, ?, ?)", (target_id, changer_id, review))
    conn.commit()

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

main.py
# main.py
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
    create_or_get_user, update_username, get_user_by_tg_id, get_user_by_username,
    update_reputation, reset_reputation, add_review, get_reviews,
    can_change_reputation, update_reputation_change_time, add_user, update_tg_id_for_user,
    update_related_tg_id
)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"

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

# Состояния для FSM
class ReviewStates(StatesGroup):
    waiting_for_review = State()

class ReviewsPagination(StatesGroup):
    viewing_reviews = State()

# Функция для оборачивания текста в жирные теги
def bold(text: str) -> str:
    return f"<b>{text}</b>"

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    # Проверяем, существует ли пользователь с таким username
    existing_user = get_user_by_username(username)

    if existing_user:
        # Если пользователь с таким username уже есть, обновляем его tg_id
        existing_tg_id, _, reputation = existing_user
        if existing_tg_id != tg_id:  # Проверяем, если ID не совпадают
            update_tg_id_for_user(username, tg_id)

            # Обновляем tg_id в связанных таблицах
            update_related_tg_id(existing_tg_id, tg_id)
            logger.info(f"Обновлен профиль: username @{username} связан с новым tg_id {tg_id}.")
        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\n"
                 f"Ваш профиль успешно обновлен.\nРепутация: {reputation}."),
            reply_markup=main_menu
        )
    else:
        # Если пользователя с таким tg_id или username нет, создаем нового
        user = create_or_get_user(tg_id, username)
        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\nВаш профиль создан."),
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
        # Создание профиля для нового пользователя
        username = input_data[1:] if input_data.startswith("@") else f"user_{input_data}"
        tg_id = int(input_data) if input_data.isdigit() else None

        # Если tg_id недоступен, установим временное значение
        if tg_id is None:
            tg_id = hash(username) % (10**9)  # Генерация фиктивного ID из имени пользователя
            logger.warning(f"Создан пользователь с фиктивным ID: {tg_id}")

        add_user(tg_id, username)
        reputation = 0

    # Создание кнопок для взаимодействия
    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        bold(f"Профиль @{username}\n\nРепутация: {reputation}"),
        reply_markup=markup
    )


# Управление репутацией
@router.callback_query(F.data.startswith("add_") | F.data.startswith("sub_"))
async def reputation_handler(callback: types.CallbackQuery, state: FSMContext):
    action, target_id = callback.data.split("_")

    try:
        target_id = int(target_id)
    except ValueError:
        await callback.answer("Неверный ID пользователя.", show_alert=True)
        return

    if target_id == callback.from_user.id:
        await callback.answer("Вы не можете изменять свою репутацию.", show_alert=True)
        return

    if not can_change_reputation(callback.from_user.id, target_id):
        await callback.answer("Вы можете изменять репутацию этого пользователя только раз в неделю.", show_alert=True)
        return

    # Установка состояния ожидания отзыва
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await state.set_state(ReviewStates.waiting_for_review)
    await state.update_data(target_id=target_id, action=action, changer_id=callback.from_user.id)


@router.message(ReviewStates.waiting_for_review)
async def handle_review_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    action = data["action"]
    changer_id = data["changer_id"]
    review = message.text.strip()

    if not (5 <= len(review.split()) <= 40):
        await message.answer(bold("Отзыв должен содержать от 5 до 40 слов. Попробуйте снова:"))
        return

    update_reputation(target_id, 1 if action == "add" else -1)
    add_review(target_id, changer_id, review)
    update_reputation_change_time(changer_id, target_id)

    await state.clear()
    user = get_user_by_tg_id(target_id)
    await message.answer(bold(f"Репутация пользователя @{user[1]} успешно обновлена."))

# Отображение отзывов
@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])
    reviews = get_reviews(target_id, limit=1, offset=0)

    if not reviews:
        await callback.message.edit_text(bold("Отзывов пока нет."))
        return

    review_text, timestamp, changer_username = reviews[0]
    text = f"<b>Отзыв:</b> {review_text}\n<b>Оставил:</b> @{changer_username}\n<b>Дата:</b> {timestamp}"

    buttons = [
        [InlineKeyboardButton(text="⬅️", callback_data=f"prev_{target_id}_0"),
         InlineKeyboardButton(text="➡️", callback_data=f"next_{target_id}_1")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=markup)

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

# Закрытие сообщений
@router.callback_query(F.data == "close")
async def close_handler(callback: types.CallbackQuery):
    await callback.message.delete()

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
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

# Состояния для FSM
class ReviewStates(StatesGroup):
    waiting_for_review = State()

class ReviewsPagination(StatesGroup):
    viewing_reviews = State()

# Функция для оборачивания текста в жирные теги
def bold(text: str) -> str:
    return f"<b>{text}</b>"

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    # Проверяем, существует ли пользователь с таким username
    existing_user = get_user_by_username(username)

    if existing_user:
        # Если пользователь с таким username уже есть, обновляем его tg_id
        existing_tg_id, _, reputation = existing_user
        if existing_tg_id != tg_id:  # Проверяем, если ID не совпадают
            update_tg_id_for_user(username, tg_id)

            # Обновляем tg_id в связанных таблицах
            update_related_tg_id(existing_tg_id, tg_id)
            logger.info(f"Обновлен профиль: username @{username} связан с новым tg_id {tg_id}.")
        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\n"
                 f"Ваш профиль успешно обновлен.\nРепутация: {reputation}."),
            reply_markup=main_menu
        )
    else:
        # Если пользователя с таким tg_id или username нет, создаем нового
        user = create_or_get_user(tg_id, username)
        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\nВаш профиль создан."),
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
        # Создание профиля для нового пользователя
        username = input_data[1:] if input_data.startswith("@") else f"user_{input_data}"
        tg_id = int(input_data) if input_data.isdigit() else None

        # Если tg_id недоступен, установим временное значение
        if tg_id is None:
            tg_id = hash(username) % (10**9)  # Генерация фиктивного ID из имени пользователя
            logger.warning(f"Создан пользователь с фиктивным ID: {tg_id}")

        add_user(tg_id, username)
        reputation = 0

    # Создание кнопок для взаимодействия
    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        bold(f"Профиль @{username}\n\nРепутация: {reputation}"),
        reply_markup=markup
    )


# Управление репутацией
@router.callback_query(F.data.startswith("add_") | F.data.startswith("sub_"))
async def reputation_handler(callback: types.CallbackQuery, state: FSMContext):
    action, target_id = callback.data.split("_")

    try:
        target_id = int(target_id)
    except ValueError:
        await callback.answer("Неверный ID пользователя.", show_alert=True)
        return

    if target_id == callback.from_user.id:
        await callback.answer("Вы не можете изменять свою репутацию.", show_alert=True)
        return

    if not can_change_reputation(callback.from_user.id, target_id):
        await callback.answer("Вы можете изменять репутацию этого пользователя только раз в неделю.", show_alert=True)
        return

    # Установка состояния ожидания отзыва
    await callback.message.edit_text(bold("Оставьте отзыв о работнике (от 5 до 40 слов):"))
    await state.set_state(ReviewStates.waiting_for_review)
    await state.update_data(target_id=target_id, action=action, changer_id=callback.from_user.id)


@router.message(ReviewStates.waiting_for_review)
async def handle_review_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    action = data["action"]
    changer_id = data["changer_id"]
    review = message.text.strip()

    if not (5 <= len(review.split()) <= 40):
        await message.answer(bold("Отзыв должен содержать от 5 до 40 слов. Попробуйте снова:"))
        return

    update_reputation(target_id, 1 if action == "add" else -1)
    add_review(target_id, changer_id, review)
    update_reputation_change_time(changer_id, target_id)

    await state.clear()
    user = get_user_by_tg_id(target_id)
    await message.answer(bold(f"Репутация пользователя @{user[1]} успешно обновлена."))

# Отображение отзывов
@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])
    reviews = get_reviews(target_id, limit=1, offset=0)

    if not reviews:
        await callback.message.edit_text(bold("Отзывов пока нет."))
        return

    review_text, timestamp, changer_username = reviews[0]
    text = f"<b>Отзыв:</b> {review_text}\n<b>Оставил:</b> @{changer_username}\n<b>Дата:</b> {timestamp}"

    buttons = [
        [InlineKeyboardButton(text="⬅️", callback_data=f"prev_{target_id}_0"),
         InlineKeyboardButton(text="➡️", callback_data=f"next_{target_id}_1")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=markup)

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

# Закрытие сообщений
@router.callback_query(F.data == "close")
async def close_handler(callback: types.CallbackQuery):
    await callback.message.delete()

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())