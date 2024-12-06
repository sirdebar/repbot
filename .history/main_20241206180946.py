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
    can_change_reputation, update_reputation_change_time
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

    user = create_or_get_user(tg_id, username)
    update_username(tg_id, username)

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
            create_or_get_user(tg_id, username)
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
