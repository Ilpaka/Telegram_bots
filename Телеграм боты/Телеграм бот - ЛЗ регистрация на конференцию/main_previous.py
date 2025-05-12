import logging
import asyncio
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery

logging.basicConfig(level=logging.INFO)

# Замените на токен вашего бота
API_TOKEN = ""
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Добавьте username или ID канала (замените значение на актуальное, например, "@my_channel")
CHANNEL_ID = -1002478639807

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials/tonal-rune-446721-p0-812eabe7ae52.json", scope)
client = gspread.authorize(creds)
# Открываем таблицу (замените "LOC_conferences" на название вашей таблицы)
sheet = client.open("LOC_conferences").sheet1

EXPECTED_HEADERS = [
    "number", "tg_id", "tg_username", "tg_link", "name", "age", "phone", "email"
]

def generate_id():
    try:
        records = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        max_num = 0
        for record in records:
            rec_id = record.get("number", "")
            try:
                num = int(rec_id)
                if num > max_num:
                    max_num = num
            except (ValueError, TypeError):
                continue
        new_id = max_num + 1
        return new_id
    except Exception as e:
        logging.error("Ошибка при генерации номера места", exc_info=True)
        return

def support_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sash_alexandrovn", url="https://t.me/sash_alexandrovn")]
    ])

# FSM для регистрации конференции
class RegistrationFormConference(StatesGroup):
    wait_reg = State()  # Ожидание нажатия кнопки «Зарегистрироваться»
    name = State()      # Как вас зовут?
    age = State()       # Сколько вам лет?
    phone = State()     # Номер телефона
    ask_email = State() # Запрос, хотите ли отправить email?
    email = State()     # Электронная почта (если выбрали "Да")

# Обработка команды /start
@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    logo = FSInputFile("templates/logo.png")
    await message.answer_photo(photo=logo)
    await state.clear()
    first_message = (
        "<b>Добро пожаловать в Бот Лиги Создателей!</b>\n"
        "<b>Конференция Лиги Создателей</b> — это место, где каждый получит возможность высказаться и быть услышанным!\n"
        "*возраст участников: от 14 лет и старше.*"
    )
    continue_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="continue")]
    ])
    await message.answer(first_message, parse_mode="HTML", reply_markup=continue_kb)

# Обработка inline-кнопки "Продолжить"
@router.callback_query(lambda c: c.data == "continue")
async def continue_registration(call: CallbackQuery, state: FSMContext):
    second_message = (
        "<b>Зарегистрируйтесь</b> сейчас, чтобы забронировать место для себя.\n"
        "*Если хотите стать спикером на Конференции, напишите: @sash_alexandrovn*\n\n"
        "<i>При использовании данного сервиса вы автоматически соглашаетесь на обработку персональных данных</i>"
    )
    await call.message.edit_text(second_message, parse_mode="HTML")
    reg_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Зарегистрироваться")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await call.message.answer("Нажмите кнопку «Зарегистрироваться» для продолжения", reply_markup=reg_keyboard)
    await state.set_state(RegistrationFormConference.wait_reg)

# Обработка нажатия на кнопку «Зарегистрироваться»: спрашиваем имя
@router.message(RegistrationFormConference.wait_reg)
async def process_wait_reg(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "зарегистрироваться":
        await message.answer("Как вас зовут?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegistrationFormConference.name)
    else:
        await message.answer("Пожалуйста, нажмите кнопку «Зарегистрироваться».")

# Сохраняем имя и переходим к вводу возраста
@router.message(RegistrationFormConference.name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(RegistrationFormConference.age)
    await message.answer("Сколько вам лет?")

# Обработка возраста с проверкой
@router.message(RegistrationFormConference.age)
async def process_age(message: types.Message, state: FSMContext):
    age_text = message.text.strip()
    if not age_text.isdigit():
        await message.answer("Пожалуйста, введите возраст цифрами (например, 25).")
        return
    age = int(age_text)
    if age > 100:
        await message.answer("ОГО! Вы знаете что такое интернет? Пожалуйста, введите нормальный возраст:")
        return
    if age < 14:
        await message.answer("Если вам ещё нет 14 лет, свяжитесь напрямую:", reply_markup=support_keyboard())
        await state.clear()
        return
    await state.update_data(age=age)
    
    # Запрос номера телефона с клавиатурой «Поделиться номером»
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await state.set_state(RegistrationFormConference.phone)
    await message.answer("Отправьте ваш номер телефона (или введите вручную в формате +1234567890):", reply_markup=phone_keyboard)

# Чистая реализация обработки номера телефона
@router.message(RegistrationFormConference.phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        if not re.match(r'^\+?\d{10,15}$', phone):
            await message.answer("Некорректный формат номера телефона. Попробуйте ещё раз, например: +1234567890")
            return
    await state.update_data(phone=phone)
    
    # Переходим к запросу email
    await state.set_state(RegistrationFormConference.ask_email)
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="email_yes"),
         InlineKeyboardButton(text="Нет", callback_data="email_no")]
    ])
    await message.answer("Хотите отправить email?", reply_markup=inline_kb)

# Обработка выбора email: если "ДА" – спрашиваем email, если "НЕТ" – удаляем сообщение и переходим к сохранению
@router.callback_query(lambda c: c.data in ["email_yes", "email_no"])
async def process_email_choice(call: CallbackQuery, state: FSMContext):
    if call.data == "email_yes":
        await state.set_state(RegistrationFormConference.email)
        await call.message.edit_text("Введите ваш email:")
    else:
        await call.message.delete()
        await finish_registration(call.message, state, user=call.from_user)

# Обработка введённого email с проверкой формата
@router.message(RegistrationFormConference.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        await message.answer("Некорректный формат email. Пожалуйста, введите действующий email:")
        return
    await state.update_data(email=email)
    await finish_registration(message, state)

# Финальное сохранение в Google Sheets, отправка уведомления в канал и сообщение пользователю
async def finish_registration(message: types.Message, state: FSMContext, user: types.User = None):
    if user is None:
        user = message.from_user
    try:
        data = await state.get_data()
        tg_id = user.id
        tg_username = user.username or ""
        tg_link = f"https://t.me/{tg_username}" if tg_username else ""
        name = data.get("name", "Участник")
        age = data.get("age", "")
        phone = data.get("phone", "")
        email = data.get("email", "")
        number = generate_id()
        row = [number, tg_id, tg_username, tg_link, name, age, phone, email]
        sheet.append_row(row)
        
        # Отправка уведомления в специальный канал с данными регистрации
        try:
            channel_message = (
                f"Новая регистрация:\n"
                f"Место №{number}\n"
                f"tg_id: {tg_id}\n"
                f"tg_username: {tg_username}\n"
                f"tg_link: {tg_link}\n"
                f"Имя: {name}\n"
                f"Возраст: {age}\n"
                f"Телефон: {phone}\n"
                f"Email: {email}\n"
            )
            await bot.send_message(CHANNEL_ID, channel_message)
        except Exception as e:
            logging.error("Ошибка при отправке уведомления в канал", exc_info=True)
            
    except Exception as e:
        logging.error("Ошибка при записи в Google Sheets", exc_info=True)
        await message.answer(
            "Ой, что-то пошло не так. Попробуйте зарегестрироваться ещё раз или напишете @sash_alexandrovn",
            reply_markup=support_keyboard()
        )
        await state.clear()
        return

    final_text = (
        f"Поздравляем! Ваше место №{number} на конференции Лиги Создателей!\n"
        "Переходите в канал КОНФЕРЕНЦИИ, там мы подробнее рассказываем что будет на мероприятии https://t.me/LSkonf1"
    )
    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.clear()

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
