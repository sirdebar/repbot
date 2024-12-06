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
    update_related_tg_id, update_reviews_target_id_from_username
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

    existing_user = get_user_by_username(username)

    if existing_user:
        existing_tg_id, _, reputation = existing_user
        if existing_tg_id != tg_id:
            update_tg_id_for_user(username, tg_id)
            update_related_tg_id(existing_tg_id, tg_id)

        # Привязываем отзывы, если они были добавлены до регистрации
        update_reviews_target_id_from_username(username, tg_id)

        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\n"
                 f"Ваш профиль успешно обновлен.\nРепутация: {reputation}."),
            reply_markup=main_menu
        )
    else:
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