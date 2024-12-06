
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
    can_change_reputation, update_reputation_change_time, 
    get_paginated_reviews, get_reviews_count
)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Настройки бота
BOT_TOKEN = "8126821875:AAGaonnOxupN1rpWpoL6Y8_6BBMl2OAo7mA"
ADMIN_USERNAME = "DxxmII"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True
)

def bold(text: str) -> str:
    return f"<b>{text}</b>"

class ReviewStates(StatesGroup):
    waiting_for_review = State()

@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    user = get_user_by_tg_id(tg_id)
    if user:
        update_username(tg_id, username)
    else:
        existing_user = get_user_by_username(username)
        if existing_user:
            update_username(existing_user[0], username)
        else:
            add_user(tg_id, username)

    await message.answer(bold(f"Добро пожаловать, {message.from_user.full_name}!"), reply_markup=main_menu)

@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message):
    tg_id = message.from_user.id
    user = get_user_by_tg_id(tg_id)

    if user:
        _, username, reputation = user
        reviews = get_reviews(tg_id, limit=1, offset=0)
        reviews_text = f"\n\nПоследний отзыв: {reviews[0][0]}" if reviews else "\n\nОтзывов пока нет."
        await message.answer(
            bold(f"Ваш профиль\n\nИмя пользователя: @{username}\nРепутация: {reputation}{reviews_text}")
        )
    else:
        await message.answer(bold("Ваш профиль не найден. Попробуйте нажать /start."))

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

    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}_0")]
    ]
    if message.from_user.username == ADMIN_USERNAME:
        buttons.append([InlineKeyboardButton(text="🗑️ Очистить репутацию", callback_data=f"reset_{tg_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(bold(f"Профиль @{username} Репутация: {reputation}"), reply_markup=markup)



@router.callback_query(F.data.startswith("reviews_"))
async def reviews_pagination_handler(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    offset = int(callback.data.split("_")[2]) if len(callback.data.split("_")) > 2 else 0
    limit = 1

    reviews = get_paginated_reviews(target_id, limit=limit, offset=offset)
    reviews_count = get_reviews_count(target_id)
    username = get_user_by_tg_id(target_id)[1]

    if not reviews:
        await callback.message.edit_text(bold(f"У пользователя @{username} пока нет отзывов."))
        return

    review = reviews[0]
    changer = get_user_by_tg_id(review[0])
    changer_name = changer[1] if changer else "Неизвестно"
    timestamp = review[2]
    text = bold(f"Репутация: {review[1]}Оставил: @{changer_name} Дата: {timestamp} {review[1]}")

    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"reviews_{target_id}_{offset-1}"))
    if offset + 1 < reviews_count:
        buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"reviews_{target_id}_{offset+1}"))
    buttons.append(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_reviews"))

    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await callback.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data == "close_reviews")
async def close_reviews_handler(callback: types.CallbackQuery):
    await callback.message.delete()

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
