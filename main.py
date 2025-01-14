import asyncio
import pytz
import os
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
    update_related_tg_id, update_captcha_status, delete_reviews_for_user, increment_profile_views,
    get_profile_view_count, cursor
)
import random
from dotenv import load_dotenv
from datetime import datetime
from aiogram.exceptions import TelegramBadRequest

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Настройки бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAMES = ["tnwfo", "DxxmII"]

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
EMOJIS = ["🐼", "🐻", "🦊", "🐨", "🐸"]

# Состояние для прохождения капчи
class CaptchaStates(StatesGroup):
    solving_captcha = State()

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    tg_id = message.from_user.id
    username = message.from_user.username or f"user_{tg_id}"

    # Проверяем пользователя по tg_id
    user = get_user_by_tg_id(tg_id)

    if not user:
        # Если не найден по tg_id, пробуем найти по username
        user = get_user_by_username(username)
        if user:
            # Если нашли по username, обновляем фиктивный tg_id на реальный
            old_tg_id, _, _, _ = user
            update_related_tg_id(old_tg_id, tg_id)
            update_tg_id_for_user(username, tg_id)  # Обновляем в таблице users
            user = get_user_by_tg_id(tg_id)  # Перезапрашиваем данные
        else:
            # Если пользователь не найден, создаем нового
            create_or_get_user(tg_id, username)
            user = get_user_by_tg_id(tg_id)

    # Проверяем капчу
    _, _, _, captcha_passed = user
    if captcha_passed:
        await message.answer(
            bold(f"Добро пожаловать, {message.from_user.full_name}!\nВаш профиль активен."),
            reply_markup=main_menu
        )
    else:
        # Генерация капчи
        correct_emoji = random.choice(EMOJIS)
        shuffled_emojis = random.sample(EMOJIS, len(EMOJIS))
        buttons = [[InlineKeyboardButton(text=emoji, callback_data=f"captcha_{emoji}")]
                   for emoji in shuffled_emojis]

        markup = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Сохраняем состояние с правильным ответом
        await state.set_state(CaptchaStates.solving_captcha)
        await state.update_data(correct_emoji=correct_emoji)

        await message.answer(
            bold(f"Капча: Нажмите на кнопку с этим смайликом {correct_emoji}"),
            reply_markup=markup
        )



@router.callback_query(F.data.startswith("captcha_"))
async def captcha_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    correct_emoji = data.get("correct_emoji")
    selected_emoji = callback.data.split("_")[1]  # Получаем выбранный смайлик

    if selected_emoji == correct_emoji:
        # Капча пройдена
        await state.clear()
        await callback.message.delete()
        await callback.answer("Капча пройдена!", show_alert=True)

        # Обновляем статус прохождения капчи
        tg_id = callback.from_user.id
        username = callback.from_user.username or f"user_{tg_id}"
        create_or_get_user(tg_id, username)
        update_captcha_status(tg_id, True)

        await callback.message.answer(
            bold(f"Добро пожаловать, {callback.from_user.full_name}!\nВаш профиль активен."),
            reply_markup=main_menu
        )
    else:
        # Неправильный ответ
        await callback.answer("Неправильный смайлик. Попробуйте снова.", show_alert=True)

        # Генерация новой капчи
        correct_emoji = random.choice(EMOJIS)
        shuffled_emojis = random.sample(EMOJIS, len(EMOJIS))
        buttons = [[InlineKeyboardButton(text=emoji, callback_data=f"captcha_{emoji}")]
                   for emoji in shuffled_emojis]

        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await state.update_data(correct_emoji=correct_emoji)
        await callback.message.edit_text(
            bold(f"Капча: Нажмите на кнопку с этим смайликом {correct_emoji}"),
            reply_markup=markup
        )

# Обработчик кнопки "Профиль"
@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message):
    tg_id = message.from_user.id

    if message.from_user.username in ADMIN_USERNAMES:
        await message.answer(bold("Админу профиль не по масти"))
        return

    user = get_user_by_tg_id(tg_id)

    if user:
        tg_id, username, reputation, captcha_passed = user
        if not captcha_passed:
            await message.answer(
                bold("Ваш профиль не активен. Пожалуйста, пройдите капчу, нажав /start.")
            )
            return
        reviews = get_reviews(tg_id, limit=1, offset=0)
        reviews_text = f"\n\nПоследний отзыв: {reviews[0][0]}" if reviews else "\n\nОтзывов пока нет."
        await message.answer(bold(f"Ваш профиль\n\nРепутация: {reputation}{reviews_text}"))
    else:
        await message.answer(bold("Ваш профиль не найден. Попробуйте нажать /start."))

@router.message(Command("news"))
async def news_handler(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAMES:
        await message.answer("У вас нет прав для этой команды.")
        return

    # Определяем текст: если есть подпись, используем её, иначе берём из текста сообщения
    text = message.caption or message.text

    # Удаляем команду `/news` из текста
    if text and text.startswith("/news"):
        text = text.split(maxsplit=1)  # Разделяем только на 2 части
        text = text[1] if len(text) > 1 else ""  # Берём часть после команды

    # Проверяем наличие прикрепленного фото
    photo = message.photo[-1].file_id if message.photo else None

    if not text and not photo:
        await message.answer("Укажите текст новости или прикрепите фото.")
        return

    # Получаем список всех пользователей
    users = cursor.execute("SELECT tg_id FROM users").fetchall()

    for user in users:
        try:
            if photo:
                # Отправляем фото с текстом в качестве подписи
                await bot.send_photo(chat_id=user[0], photo=photo, caption=text)
            else:
                # Отправляем только текст
                await bot.send_message(chat_id=user[0], text=text)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")

    await message.answer("Новость отправлена.")

@router.message(Command("stats"))
async def stats_handler(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAMES:
        await message.answer("У вас нет прав для этой команды.")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reviews")
    review_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT review FROM reviews
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_review = cursor.fetchone()

    stats_text = (
        f"Человек в боте: {user_count}\n"
        f"Оставлено отзывов: {review_count}\n"
        f"Последний отзыв: {last_review[0] if last_review else 'Нет отзывов'}"
    )
    await message.answer(stats_text)


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
        tg_id, username, reputation, captcha_passed = user_info
        username = username or f"user_{tg_id}"
        reputation = int(reputation) if isinstance(reputation, (int, float)) else 0

        # Если найденный пользователь является администратором
        if username in ADMIN_USERNAMES:
            await message.answer(bold(f"Нельзя изменить репутацию администратора @{username}."))
            return
    else:
        # Если пользователь не найден в базе, добавляем его
        username = input_data[1:] if input_data.startswith("@") else f"user_{input_data}"
        tg_id = int(input_data) if input_data.isdigit() else hash(username) % (10**9)
        add_user(tg_id, username)
        reputation = 0

    buttons = [
        [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
         InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
        [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
    ]

    if message.from_user.username in ADMIN_USERNAMES:
        buttons.append(
            [InlineKeyboardButton(text="Очистить репутацию", callback_data=f"reset_{tg_id}")]
        )

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    increment_profile_views(tg_id, message.from_user.id)
    view_count = get_profile_view_count(tg_id)

    await message.answer(
        bold(f"Профиль @{username}\n\nРепутация: {reputation}\n👁️ Интересовались: {view_count}"),
        reply_markup=markup
    )


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

    # Проверяем, что цель не администратор
    target_user = get_user_by_tg_id(target_id)
    if target_user and target_user[1] in ADMIN_USERNAMES:
        await callback.answer("Нельзя изменить репутацию администратору.", show_alert=True)
        return

    if not can_change_reputation(callback.from_user.id, target_id):
        await callback.answer("Вы можете изменять репутацию этого пользователя только раз в неделю.", show_alert=True)
        return

    # Запрос отзыва
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

    # Проверка длины отзыва
    if not (5 <= len(review.split()) <= 40):
        await message.answer(bold("Отзыв должен содержать от 5 до 40 слов. Попробуйте снова:"))
        return

    # Создание пользователя, если он отсутствует
    create_or_get_user(changer_id, message.from_user.username or f"user_{changer_id}")

    # Обновление репутации
    if can_change_reputation(changer_id, target_id):
        update_reputation(target_id, 1 if action == "add" else -1)
        update_reputation_change_time(changer_id, target_id)

    # Добавление нового отзыва
    add_review(target_id, changer_id, review, '+REP' if action == 'add' else '-REP')

    user = get_user_by_tg_id(target_id)
    await message.answer(bold(f"Репутация пользователя @{user[1]} успешно обновлена, отзыв добавлен."))    
    await state.clear()

# Отображение отзывов
@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])
    reviews = get_reviews(target_id, limit=1, offset=0)

    if not reviews:
        await callback.message.edit_text(bold("Отзывов пока нет."))
        return

    review_text, timestamp, action, changer_username = reviews[0]
    emoji = "🟢" if action == "+REP" else "🔴"

    text = (
        f"{emoji} <b>Отзыв:</b> {review_text}\n"
        f"<b>Оставил:</b> @{changer_username}\n"
        f"<b>Дата:</b> {timestamp} (МСК)"
    )

    buttons = [
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"prev_{target_id}_0"),
            InlineKeyboardButton(text="➡️", callback_data=f"next_{target_id}_1"),
        ],
        [InlineKeyboardButton(text="Назад", callback_data=f"back_{target_id}")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data.startswith("back_"))
async def back_to_profile(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    user_info = get_user_by_tg_id(target_id)
    
    if user_info:
        tg_id, username, reputation, captcha_passed = user_info
        username = username or f"user_{tg_id}"
        reputation = int(reputation)
        buttons = [
            [InlineKeyboardButton(text="🟢 +REP", callback_data=f"add_{tg_id}"),
             InlineKeyboardButton(text="🔴 -REP", callback_data=f"sub_{tg_id}")],
            [InlineKeyboardButton(text="Отзывы", callback_data=f"reviews_{tg_id}")]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            bold(f"Профиль @{username}\n\nРепутация: {reputation}"),
            reply_markup=markup
        )

@router.callback_query(F.data.startswith("prev_") | F.data.startswith("next_"))
async def paginate_reviews(callback: types.CallbackQuery):
    action, target_id, offset = callback.data.split("_")
    target_id = int(target_id)
    offset = int(offset)

    # Изменяем смещение в зависимости от направления
    new_offset = offset - 1 if action == "prev" else offset + 1

    # Получаем отзыв с новым смещением
    reviews = get_reviews(target_id, limit=1, offset=new_offset)

    if not reviews:
        # Если отзывов больше нет, предупреждаем пользователя
        await callback.answer("Отзывов больше нет.", show_alert=True)
        return

    # Распаковываем данные отзыва
    review_text, timestamp, action, changer_username = reviews[0]
    emoji = "🟢" if action == "+REP" else "🔴"

    text = (
        f"{emoji} <b>Отзыв:</b> {review_text}\n"
        f"<b>Оставил:</b> @{changer_username}\n"
        f"<b>Дата:</b> {timestamp}"
    )

    # Проверяем, есть ли предыдущий или следующий отзыв
    prev_reviews = get_reviews(target_id, limit=1, offset=new_offset - 1)
    next_reviews = get_reviews(target_id, limit=1, offset=new_offset + 1)

    # Формируем кнопки навигации
    buttons = []
    if prev_reviews:
        buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"prev_{target_id}_{new_offset - 1}"))
    if next_reviews:
        buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"next_{target_id}_{new_offset + 1}"))
    buttons.append(InlineKeyboardButton(text="Закрыть", callback_data="close"))
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])

    # Обновляем текст сообщения
    await callback.message.edit_text(text, reply_markup=markup)


# Очистка репутации
@router.callback_query(F.data.startswith("reset_"))
async def reset_reputation_handler(callback: types.CallbackQuery):
    # Проверяем, что пользователь является администратором
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.answer("У вас нет прав для этой команды.", show_alert=True)
        return

    try:
        target_id = int(callback.data.split("_")[1])

        # Сбрасываем репутацию и удаляем отзывы
        reset_reputation(target_id)
        delete_reviews_for_user(target_id)

        await callback.message.edit_text(bold("Репутация и отзывы пользователя успешно сброшены."))
        logger.info(f"Репутация и отзывы пользователя {target_id} были сброшены администратором.")
    except (ValueError, TelegramBadRequest):
        await callback.answer("Ошибка при сбросе данных.", show_alert=True)



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