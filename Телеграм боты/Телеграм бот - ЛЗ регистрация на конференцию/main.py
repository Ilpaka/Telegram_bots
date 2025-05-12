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
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

# Замените на токен вашего бота
API_TOKEN = ""
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Если требуется отправка уведомлений в канал — укажите его ID или username (например, "@my_channel")
# CHANNEL_ID = -1002478639807  # или "@my_channel"

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("/Users/sip/Yandex.Disk.localized/Работа/Телеграм боты/Телеграм бот - ЛЗ регистрация на конференцию/credentials/tonal-rune-446721-p0-812eabe7ae52.json", scope)  # замените путь к вашему файлу
client = gspread.authorize(creds)
# Открываем таблицу (замените "Agents_team" на название вашей таблицы)
sheet = client.open("LOC_APRIL").sheet1

# Заголовки таблицы: убедитесь, что заголовки в таблице соответствуют этим значениям
EXPECTED_HEADERS = [
    "number", "tg_id", "tg_username", "tg_link", "name", "age", "project", "contacts"
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
        return None

# FSM для регистрации нового агента Лиги Создателей
class RegistrationForm(StatesGroup):
    wait_reg = State()   # Ожидание нажатия кнопки «Зарегистрироваться»
    name = State()       # "Как тебя зовут?"
    age = State()        # "Твой возраст?"
    project = State()    # "Опиши кратко свой проект, идею или задумку"
    contacts = State()   # "Поделись контактами (телефон или email):"

# Обработка команды /start
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    start_text = (
        "Привет! Ты попал в бот Лиги Создателей!\n"
        "Если что-то непонятно — @sash_alexandrovn всегда поможет.\n\n"
        "*Пользуясь ботом, ты соглашаешься на обработку персональных данных.*"
    )
    reg_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Зарегистрироваться")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(start_text, reply_markup=reg_keyboard)

# Обработка нажатия на кнопку "Зарегистрироваться"
@router.message(RegistrationForm.wait_reg)
async def process_wait_reg(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "зарегистрироваться":
        await message.answer("Как тебя зовут?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegistrationForm.name)
    else:
        await message.answer("Пожалуйста, нажмите кнопку «Зарегистрироваться».")

# Начинаем регистрацию после нажатия кнопки
@router.message(Command("start"))
async def start_registration(message: types.Message, state: FSMContext):
    # Этот хэндлер может срабатывать для повторного /start и переводить в состояние ожидания регистрации
    await state.set_state(RegistrationForm.wait_reg)

# Обработка ввода имени
@router.message(RegistrationForm.name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(RegistrationForm.age)
    await message.answer("Твой возраст?")

# Обработка ввода возраста
@router.message(RegistrationForm.age)
async def process_age(message: types.Message, state: FSMContext):
    age_text = message.text.strip()
    if not age_text.isdigit():
        await message.answer("Пожалуйста, введите возраст цифрами (например, 25).")
        return
    age = int(age_text)
    if age < 14:
        await message.answer("К сожалению, участие доступно с 14 лет. Обратись за помощью к @sash_alexandrovn")
        await state.clear()
        return
    await state.update_data(age=age)
    await state.set_state(RegistrationForm.project)
    await message.answer("Опиши кратко свой проект, идею или задумку, которую хочешь воплотить:")

# Обработка ввода описания проекта/идеи
@router.message(RegistrationForm.project)
async def process_project(message: types.Message, state: FSMContext):
    project = message.text.strip()
    await state.update_data(project=project)
    await state.set_state(RegistrationForm.contacts)
    await message.answer("Поделись контактами (телефон или email):")

# Обработка ввода контактов
@router.message(RegistrationForm.contacts)
async def process_contacts(message: types.Message, state: FSMContext):
    contacts = message.text.strip()
    # Простейшая проверка – убедимся, что контакт выглядит как email или номер телефона
    if not (re.match(r'^\+?\d{10,15}$', contacts) or re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', contacts)):
        await message.answer("Неверный формат контакта. Введите номер телефона (например, +1234567890) или email:")
        return
    await state.update_data(contacts=contacts)
    await finish_registration(message, state)

# Финальное сохранение данных в Google Sheets и отправка подтверждения
async def finish_registration(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        tg_id = message.from_user.id
        tg_username = message.from_user.username or ""
        tg_link = f"https://t.me/{tg_username}" if tg_username else ""
        name = data.get("name", "Участник")
        age = data.get("age", "")
        project = data.get("project", "")
        contacts = data.get("contacts", "")
        number = generate_id()
        if number is None:
            raise Exception("Невозможно сгенерировать номер")
        row = [number, tg_id, tg_username, tg_link, name, age, project, contacts]
        sheet.append_row(row)
        
        # Если требуется, можно отправить уведомление в канал
        try:
            channel_message = (
                f"Новая регистрация:\n"
                f"Место №{number}\n"
                f"tg_id: {tg_id}\n"
                f"tg_username: {tg_username}\n"
                f"Имя: {name}\n"
                f"Возраст: {age}\n"
                f"Проект/Идея: {project}\n"
                f"Контакты: {contacts}\n"
            )
            # await bot.send_message(CHANNEL_ID, channel_message)
        except Exception as e:
            logging.error("Ошибка при отправке уведомления в канал", exc_info=True)
            
    except Exception as e:
        logging.error("Ошибка при записи в Google Sheets", exc_info=True)
        await message.answer(
            "Ой, что-то пошло не так. Попробуйте зарегистрироваться ещё раз или обратитесь к @sash_alexandrovn"
        )
        await state.clear()
        return

    final_text = (
        f"Супер, теперь ты — Агент Лиги Создателей: https://t.me/LSkonf2\n\n"
        f"Твоё место в команде: №{number}\n\n"
        "Будет классно, если расскажешь друзьям о нашем сообществе! Чем нас больше, тем интереснее создавать!"
    )
    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.clear()

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
