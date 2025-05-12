import logging
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    FSInputFile
)
from aiogram.filters import CommandStart
import json
import os


# ------------------------------------------------------------------
# Укажите здесь свой токен бота от BotFather
# ------------------------------------------------------------------
API_TOKEN = ""

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
#-------------------------------------------------------------------
#JSON
#-------------------------------------------------------------------
USERS_FILE = "users.json"

def load_user_ids() -> list[int]:
    """Загружает список user_id из JSON-файла."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_user_ids(user_ids: list[int]) -> None:
    """Сохраняет список user_id в JSON-файл."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_ids, f, ensure_ascii=False, indent=2)

def add_user_id(user_id: int) -> None:
    """Добавляет user_id в файл, если его там ещё нет."""
    ids = load_user_ids()
    if user_id not in ids:
        ids.append(user_id)
        save_user_ids(ids)

# ------------------------------------------------------------------
# Для хранения ID сообщений (альбом + текст) каждого пользователя
# ------------------------------------------------------------------
user_albums = {}

# ------------------------------------------------------------------
# Текст приветствия/описания
# ------------------------------------------------------------------
DESCRIPTION = (
    "👋 Привет!\n\n"
    "Меня зовут Илья, я <b>IT-специалист</b> с опытом работы в разработке и дизайне с <b>2020 года</b>. \n\n"
    "Я занимаюсь:\n"
    "• 🤖 <b>Созданием Telegram-ботов</b> под любые задачи.\n"
    "• 💻 <b>Разработкой сайтов на Tilda</b> с интеграцией: CRM, платёжных систем, систем рассылок.\n"
    "🎯 Моя цель — автоматизировать Ваши процессы и разработать индивидуальное решение!\n\n"
    "✨ <i>Свяжитесь со мной и посмотрите мои работы ниже</i>!"
)
# ------------------------------------------------------------------
# Основная клавиатура (с инлайн-кнопками)
# ------------------------------------------------------------------
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Примеры работ", callback_data="show_projects")],
    [InlineKeyboardButton(text="📜 Отзывы", callback_data="show_reviews")],
    [InlineKeyboardButton(text="✉️ Связаться со мной", url="https://t.me/Pilya_07")]
])

# ------------------------------------------------------------------
# Обработка команды /start
# ------------------------------------------------------------------
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    add_user_id(message.from_user.id)
    """
    Приветственное сообщение: сначала отправляем фото, затем текст с кнопками.
    """
    # Отправляем фото отдельно
    logo = FSInputFile("templates/logo.PNG")  # Укажите путь к логотипу
    await message.answer_photo(
        photo=logo
    )

    # Отправляем текстовое сообщение
    sent_message = await message.answer(
        DESCRIPTION,
        parse_mode="HTML",
        reply_markup=main_keyboard
    )

    # Сохраняем ID текстового сообщения, чтобы редактировать его позже
    user_albums[message.from_user.id] = {"main_message_id": sent_message.message_id}
# ------------------------------------------------------------------
# Хендлер для нажатия на "📂 Примеры работ"
# ------------------------------------------------------------------
@dp.callback_query(F.data == "show_projects")
async def show_portfolio(callback_query: types.CallbackQuery):
    """
    Обработка кнопки "📂 Примеры работ". Редактируем текстовое сообщение, если возможно.
    """
    text = (
        "🌐 <b>Мои проекты</b>\n\n"
        "1️⃣ <a href='https://vakidbook.ru/'>СБОРНИК РЕЦЕПТОВ «Для самых маленьких»</a> — Сайт на Tilda с оплатой и рассылкой писем\n\n"
        "2️⃣ <a href='http://neyrografinya.ru/woman_neyroclub'>«МАГИНЯ»</a> — Сайт на Tilda с оплатой и рассылкой писем\n\n"
        "3️⃣ <a href='http://neyrografinya.ru/chakras'>«Чакры»</a> — Сайт на Tilda с оплатой и рассылкой писем\n\n"
        "4️⃣ <a href='https://t.me/ibratsave_bot'>«Ibratsave»</a> — Telegram-бот для скачивания видео из социальных сетей\n\n"
        "5️⃣ <a href='https://t.me/GPT_IP_bot'>«GPT's by IP» — Telegram-бот с разными ИИ агентами(Бесплатно)</a>\n\n"
        "6️⃣ <a href = 'https://t.me/NEYROGRAFINYA_HAPPYbot'>«Международный клуб Везунчиков и Счастливчиков»</a> -— Telegram-бот с подпиской на клуб\n\n"
        "7️⃣ <a href='https://t.me/League_of_Creators_bot'>«Лига Создателей»</a> — Telegram-бот для регистрации на мероприятии «Лига Создателей»\n\n"
        "8️⃣ <a href='https://t.me/Krygi_reg_bot'>«Krugi»</a> — Telegram-бот для регистрации на танцевальное мероприятие «Krygi»\n\n"
        "9️⃣ <a href='https://t.me/iSneaker_bot'> «SneakerBot»</a> — Telegram-бот для подбора кроссовок для баскетбола \n\n"
        "🔟 <a href='https://t.me/AcademicTop_bot'>«Academic»</a> — Telegram-бот для дня открытых дверей в «IT TOP»\n⏬ Прмиеры работы Telegram-ботов по кнопкам ниже\n\n"
        "1️⃣1️⃣ <u>Проект «Создание базы данных для баскетбольной лиги»</u> — База данных для ведения статистики матчей и игроков в баскетбольной лиге\n⏬ смотри презентацию по кнопке ниже\n\n"
        "⚡️ Хотите что-то подобное или есть уникальная идея - Свяжитесь со мной!"
    )
    # Кнопки возврата и связи
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Смотреть видео «SneakerBot»", callback_data="send_video_sn_bot")],
        [InlineKeyboardButton(text="🎥 Смотреть видео «Academic»", callback_data="send_video_it_top_bot")],
        [InlineKeyboardButton(text="📚 Смотреть презентацию для БД", callback_data="send_presentation")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
        [InlineKeyboardButton(text="✉️ Связаться со мной", url="https://t.me/Pilya_07")]
    ])

    # Проверяем, существует ли сообщение, и оно текстовое
    user_data = user_albums.get(callback_query.from_user.id)
    if user_data and "main_message_id" in user_data:
        try:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=user_data["main_message_id"],
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования сообщения: {e}")
            await callback_query.answer("Не удалось обновить сообщение. Попробуйте позже.", show_alert=True)
            return
    else:
        logging.warning(f"Сообщение для редактирования не найдено у пользователя {callback_query.from_user.id}")
        await callback_query.answer("Не удалось найти сообщение для редактирования.", show_alert=True)
        return

    # Ответ на callback_query, чтобы убрать "часики"
    await callback_query.answer()

@dp.callback_query(F.data == "send_presentation")
async def send_presentation(callback_query: types.CallbackQuery):
    """
    Отправляем презентацию базы данных, удаляем кнопки выше, добавляем кнопку «Назад».
    """
    # Удаляем кнопки
    await callback_query.message.edit_reply_markup()

    try:
        file = FSInputFile("templates/data_base.pptx")  # Укажите путь к файлу
        sent_message = await callback_query.message.answer_document(
            document=file,
            caption="📄 Презентация базы данных",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_message_and_back")]
            ])
        )
        # Сохраняем ID отправленного сообщения
        user_albums[callback_query.from_user.id]["temp_message_id"] = sent_message.message_id
    except Exception as e:
        logging.error(f"Ошибка при отправке презентации: {e}")
        await callback_query.answer("Не удалось отправить файл. Попробуйте позже.", show_alert=True)
        return

    # Ответ на callback_query
    await callback_query.answer("Презентация отправлена!")


@dp.callback_query(F.data == "send_video_sn_bot")
async def send_video_1(callback_query: types.CallbackQuery):
    """
    Отправляем первое видео о работе Telegram-бота, удаляем кнопки выше, добавляем кнопку «Назад».
    """
    # Удаляем кнопки
    await callback_query.message.edit_reply_markup()

    try:
        video = FSInputFile("templates/snaeker_bot.mp4")  # Укажите путь к первому видео
        sent_message = await callback_query.message.answer_video(
            video=video,
            caption="🎥 Видео-демонстрация работы Telegram-бота",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_message_and_back")]
            ])
        )
        # Сохраняем ID отправленного сообщения
        user_albums[callback_query.from_user.id]["temp_message_id"] = sent_message.message_id
    except Exception as e:
        logging.error(f"Ошибка при отправке первого видео: {e}")
        await callback_query.answer("Не удалось отправить видео. Попробуйте позже.", show_alert=True)
        return

    # Ответ на callback_query
    await callback_query.answer("Видео отправлено!")


@dp.callback_query(F.data == "send_video_it_top_bot")
async def send_video_2(callback_query: types.CallbackQuery):
    """
    Отправляем второе видео о работе Telegram-бота, удаляем кнопки выше, добавляем кнопку «Назад».
    """
    # Удаляем кнопки
    await callback_query.message.edit_reply_markup()

    try:
        video = FSInputFile("templates/IT_top_bot.mp4")  # Укажите путь ко второму видео
        sent_message = await callback_query.message.answer_video(
            video=video,
            caption="🎥 Ещё одно видео о работе Telegram-бота",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_message_and_back")]
            ])
        )
        # Сохраняем ID отправленного сообщения
        user_albums[callback_query.from_user.id]["temp_message_id"] = sent_message.message_id
    except Exception as e:
        logging.error(f"Ошибка при отправке второго видео: {e}")
        await callback_query.answer("Не удалось отправить видео. Попробуйте позже.", show_alert=True)
        return

    # Ответ на callback_query
    await callback_query.answer("Видео отправлено!")


@dp.callback_query(F.data == "delete_message_and_back")
async def delete_message_and_back(callback_query: types.CallbackQuery):
    """
    Удаляем отправленный файл или видео и возвращаемся в главное меню.
    """
    user_data = user_albums.get(callback_query.from_user.id)

    # Удаляем отправленное сообщение
    if user_data and "temp_message_id" in user_data:
        try:
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=user_data["temp_message_id"]
            )
        except Exception as e:
            logging.warning(f"Ошибка при удалении сообщения: {e}")
        finally:
            # Удаляем temp_message_id из user_data
            user_data.pop("temp_message_id", None)

    # Проверяем наличие main_message_id
    if user_data and "main_message_id" in user_data:
        try:
            # Редактируем сообщение, возвращая описание и главные кнопки
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=user_data["main_message_id"],
                text=DESCRIPTION,
                parse_mode="HTML",
                reply_markup=main_keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования сообщения (Назад): {e}")
            await callback_query.answer("Не удалось вернуться в главное меню. Попробуйте позже.", show_alert=True)
            return
    else:
        logging.warning(f"main_message_id не найдено у пользователя {callback_query.from_user.id}")
        await callback_query.answer("Не удалось найти сообщение для возврата. Попробуйте позже.", show_alert=True)
        return

    # Ответ на callback_query, чтобы убрать "часики"
    await callback_query.answer()


# ------------------------------------------------------------------
# Хендлер для нажатия на "📜 Отзывы"
# ------------------------------------------------------------------
@dp.callback_query(F.data == "show_reviews")
async def show_reviews(callback_query: types.CallbackQuery):
    """
    Отправляем альбом из трёх фото отзывов и текстовое сообщение с кнопкой «Назад».
    Основное сообщение временно лишается кнопок.
    """
    # Убираем кнопки у основного сообщения
    if callback_query.from_user.id in user_albums:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback_query.message.chat.id,
                message_id=user_albums[callback_query.from_user.id]["main_message_id"],
                reply_markup=None
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении кнопок у основного сообщения: {e}")

    # Подготовим альбом отзывов
    media = [
        InputMediaPhoto(
            media=FSInputFile("templates/reviev1.png"),
            caption="Отзыв №1"
        ),
        InputMediaPhoto(
            media=FSInputFile("templates/reviev2.png"),
            caption="Отзыв №2"
        ),
        InputMediaPhoto(
            media=FSInputFile("templates/reviev3.png"),
            caption="Отзыв №3"
        ),
        InputMediaPhoto(
            media=FSInputFile("templates/reviev4.png"),
            caption="Отзыв №4"
        )
    ]

    try:
        # Отправляем альбом с отзывами
        sent_album = await callback_query.message.answer_media_group(media=media)
    except Exception as e:
        logging.error(f"Ошибка при отправке альбома отзывов: {e}")
        await callback_query.answer("Не удалось загрузить отзывы. Попробуйте позже.", show_alert=True)
        return

    # Отправляем текст с кнопкой «Назад»
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_from_reviews")],
        [InlineKeyboardButton(text="✉️ Связаться со мной", url="https://t.me/Pilya_07")]
    ])
    text_msg = await callback_query.message.answer(
        "<b>Отзывы моих работодателей</b>\n\n"
        "Ниже представлены отзывы от довольных клиентов, с которыми я сотрудничал.\n\n"
        "Нажмите «Назад», чтобы вернуться в главное меню.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    # Сохраняем ID всех сообщений (альбом и текст)
    user_albums[callback_query.from_user.id]["review_message_ids"] = [m.message_id for m in sent_album] + [text_msg.message_id]

    # Ответ на callback_query, чтобы убрать "часики"
    await callback_query.answer()

# ------------------------------------------------------------------
# Кнопка "Назад" — для отзывов
# ------------------------------------------------------------------
@dp.callback_query(F.data == "back_from_reviews")
async def back_from_reviews(callback_query: types.CallbackQuery):
    """
    Удаляем сообщения с отзывами и восстанавливаем кнопки у основного сообщения.
    """
    user_data = user_albums.get(callback_query.from_user.id)

    # Удаляем сообщения с отзывами (альбом и текст)
    if user_data and "review_message_ids" in user_data:
        for msg_id in user_data["review_message_ids"]:
            try:
                await bot.delete_message(
                    chat_id=callback_query.message.chat.id,
                    message_id=msg_id
                )
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения с отзывами: {e}")
        del user_data["review_message_ids"]

    # Восстанавливаем кнопки у основного сообщения
    if user_data and "main_message_id" in user_data:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback_query.message.chat.id,
                message_id=user_data["main_message_id"],
                reply_markup=main_keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка при восстановлении кнопок: {e}")

    # Ответ на callback_query, чтобы убрать "часики"
    await callback_query.answer()

# ------------------------------------------------------------------
# Кнопка "Назад" — возвращаемся на главное меню
# ------------------------------------------------------------------
@dp.callback_query(F.data == "back_main")
async def back_main(callback_query: types.CallbackQuery):
    user_data = user_albums.get(callback_query.from_user.id)
    if user_data and "main_message_id" in user_data:
        try:
            # Редактируем сообщение, возвращая описание и главные кнопки
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=user_data["main_message_id"],
                text=DESCRIPTION,
                parse_mode="HTML",
                reply_markup=main_keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования сообщения (Назад): {e}")
            await callback_query.answer("Не удалось обновить сообщение. Попробуйте позже.", show_alert=True)
            return
    else:
        logging.warning(f"Сообщение для редактирования не найдено у пользователя {callback_query.from_user.id}")
        await callback_query.answer("Не удалось найти сообщение для редактирования.", show_alert=True)
        return

    # Ответ на callback_query, чтобы убрать "часики"
    await callback_query.answer()
# ------------------------------------------------------------------
# Хендлер для остальных сообщений
# ------------------------------------------------------------------
# @dp.message()
# async def fallback(message: types.Message):
#     # При любом сообщении также удаляем альбом, если он есть
#     await remove_album_if_exists(message.from_user.id, message.chat.id)

#     await message.reply(
#         "🤔 Я вас не понял. Попробуйте нажать на кнопки ниже или используйте команду /start.",
#         reply_markup=main_keyboard
#     )

# ------------------------------------------------------------------
# Утилита для удаления альбомов, если они существуют
# ------------------------------------------------------------------
# async def remove_album_if_exists(user_id: int, chat_id: int):
#     """
#     Если у пользователя есть отправленный альбом с отзывами,
#     удаляем все его сообщения из чата и очищаем запись.
#     """
#     if user_id in user_albums:
#         for msg_id in user_albums[user_id]:
#             try:
#                 await bot.delete_message(chat_id, msg_id)
#             except Exception as e:
#                 logging.warning(f"Не удалось удалить сообщение {msg_id}: {e}")
#         del user_albums[user_id]

# ------------------------------------------------------------------
# Функция запуска бота
# ------------------------------------------------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

