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
dp = Dispatcher()
router = Router()

# Главная клавиатура
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Найти"), KeyboardButton(text="Профиль")]],
    resize_keyboard=True
)

# Функция для оборачивания текста в жирные теги
def bold(text: str) -> str:
    return f"<b>{text}</b>"

# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    user = get_user_by_tg_id(tg_id)
    if user:
        update_username(tg_id, username)
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
        user_info = get_user_by_username(username)
    elif input_data.isdigit():
        tg_id = int(input_data)
        user_info = get_user_by_tg_id(tg_id)

    if user_info:
        tg_id, username, reputation = user_info
    else:
        # Создание нового профиля для отсутствующего пользователя
        tg_id = None
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
        update_reputation(target_id, 1)
    elif action == "sub":
        update_reputation(target_id, -1)

    add_review(target_id, changer_id, review)
    update_reputation_change_time(changer_id, target_id)

    cursor.execute("SELECT reputation FROM users WHERE tg_id = ?", (target_id,))
    reputation = cursor.fetchone()[0]

    await message.answer(bold(f"Репутация обновлена: {reputation}"))
    logger.info(f"Изменение репутации завершено. Цель: {target_id}, Изменил: {changer_id}")

@router.callback_query(F.data.startswith("reviews_"))
async def reviews_handler(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    reviews = get_reviews(target_id, limit=1, offset=0)
    if reviews:
        await callback.message.edit_text(bold(f"Последний отзыв: {reviews[0][0]}"))
    else:
        await callback.message.edit_text(bold("У этого пользователя пока нет отзывов."))

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
