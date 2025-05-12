import logging
import asyncio
import re
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
from aiogram import F
from aiogram.filters.state import StateFilter
from aiogram.types import CallbackQuery

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO)

# Замените на ваш токен бота
API_TOKEN = ""
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# ----- Настройка Google Sheets -----
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials/tonal-rune-446721-p0-135dd79f17b1.json", scope
)
client = gspread.authorize(creds)
sheet = client.open("KRYGI").sheet1

EXPECTED_HEADERS = [
    "ID", "tg_id", "tg_username", "tg_link", "role", "name", "age", "phone",
    "team", "styles", "battle", "battle_style", "dance_experience"
]

# Функция генерации ID с нужным префиксом
async def generate_id_for_user(user_data: dict) -> str:
    role = user_data.get("role", "")
    if role == "Танцор-участник":
        battle = user_data.get("battle", "")
        if battle == "Да":
            prefix = "A"
        else:
            prefix = "B"
    elif role == "Зритель":
        prefix = "C"
    else:
        prefix = "X"
    try:
        records = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        max_num = 0
        for record in records:
            rec_id = record.get("ID", "")
            if rec_id.startswith(prefix):
                num_part = rec_id[len(prefix):]
                try:
                    num = int(num_part)
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
        new_id = f"{prefix}{max_num + 1}"
        return new_id
    except Exception as e:
        logging.error("Ошибка при генерации ID", exc_info=True)
        return f"{prefix}1"

# ----- FSM для регистрации (с возрастом для всех) -----
class RegistrationFormKrygi(StatesGroup):
    role = State()            # Танцор-участник или Зритель
    name = State()            # ФИО или никнейм
    age = State()             # Возраст
    phone = State()           # Номер телефона
    # Для участников (танцоров)
    team = State()            # Команда/коллектив
    styles = State()          # Стиль(и)
    battle = State()          # Участие в баттловом показе (Да/Нет)
    battle_style = State()    # Если участвуют – в каком стиле
    # Для зрителей
    dance_experience = State()    # Танцевальный опыт

# ----- Обработка команды /start -----
@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    # Сохраняем данные пользователя, чтобы корректно записывать его tg_id и т.д.
    await state.update_data(
        tg_id=message.from_user.id,
        tg_username=message.from_user.username or "",
        tg_link=(f"https://t.me/{message.from_user.username}" if message.from_user.username else "")
    )
    welcome_text = (
        "Привет ✌🏻\n"
        "Я помогу зарегистрироваться на мероприятие KRYGI и получить доступ к Телеграм-каналу участников.\n\n"
        "😊Ответь на несколько простых вопросов.\n\n"
        "_При использовании данного сервиса вы автоматически соглашаетесь на обработку персональных данных._"
    )
    await message.answer(welcome_text)
    
    role_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Танцор-участник")],
            [KeyboardButton(text="Зритель")]
        ],
        resize_keyboard=True
    )
    await state.set_state(RegistrationFormKrygi.role)
    await message.answer("Ты танцор-участник или зритель?", reply_markup=role_keyboard)

@router.message(RegistrationFormKrygi.role)
async def process_role(message: types.Message, state: FSMContext):
    role = message.text.strip()
    if role not in ["Танцор-участник", "Зритель"]:
        await message.answer("Пожалуйста, выбери один из вариантов: Танцор-участник или Зритель.")
        return
    await state.update_data(role=role)
    await state.set_state(RegistrationFormKrygi.name)
    await message.answer("Как к тебе обращаться? (Фамилия имя или никнейм)", reply_markup=ReplyKeyboardRemove())

@router.message(RegistrationFormKrygi.name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(RegistrationFormKrygi.age)
    await message.answer("Введите ваш возраст:")

@router.message(RegistrationFormKrygi.age)
async def process_age(message: types.Message, state: FSMContext):
    age_text = message.text.strip()
    data = await state.get_data()
    # Если пользователь – танцор, проводим проверки
    if data.get("role") == "Танцор-участник":
        if not age_text.isdigit():
            await message.answer("Пожалуйста, введите возраст цифрами (например, 20).")
            return
        age = int(age_text)
        if age < 12:
            await message.answer("Если вам ещё нет 12 лет, тогда, пожалуйста, свяжитесь напрямую: https://t.me/l_e_23")
            await state.clear()
            return
        if age > 100:
            await message.answer("ОГО! Вы знаете что такое интернет? Пожалуйста, введите нормальный возраст:")
            return  # остаёмся в этом состоянии, чтобы пользователь ввёл корректный возраст
    # Для зрителей — никаких проверок, любой ввод принимается
    await state.update_data(age=age_text)
    await state.set_state(RegistrationFormKrygi.phone)
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Отправьте ваш номер телефона (или введите вручную в формате +1234567890):",
        reply_markup=phone_keyboard
    )

@router.message(RegistrationFormKrygi.phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        if not re.match(r'^\+?\d{10,15}$', phone):
            await message.answer("Некорректный формат номера телефона. Попробуйте еще раз, например: +1234567890")
            return
    await state.update_data(phone=phone)
    data = await state.get_data()
    if data.get("role") == "Танцор-участник":
        await state.set_state(RegistrationFormKrygi.team)
        await message.answer("Какую команду/коллектив представляешь?", reply_markup=ReplyKeyboardRemove())
    else:
        await state.set_state(RegistrationFormKrygi.dance_experience)
        await message.answer("Есть ли у тебя танцевальный опыт?\n(Пример: Да, 7 лет занимался эстрадными/Нет, но хочу прийти посмотреть)", reply_markup=ReplyKeyboardRemove())

@router.message(RegistrationFormKrygi.team)
async def process_team(message: types.Message, state: FSMContext):
    team = message.text.strip()
    await state.update_data(team=team)
    await state.set_state(RegistrationFormKrygi.styles)
    await message.answer("💁🏻‍♀️Укажи Стиль(и), который будешь представлять:\n\n(Пример:\n• Хип-Хоп/Хаус/Контемп…\nили\n• Авторская хореография/Смешанные стили)")

@router.message(RegistrationFormKrygi.styles)
async def process_styles(message: types.Message, state: FSMContext):
    styles = message.text.strip()
    await state.update_data(styles=styles)
    battle_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data="battle_yes"),
            InlineKeyboardButton(text="Нет", callback_data="battle_no")
        ]
    ])
    await state.set_state(RegistrationFormKrygi.battle)
    await message.answer("Будешь показывать себя и свой стиль в баттловом показе?", reply_markup=battle_keyboard)

@router.callback_query(F.data == "battle_yes", StateFilter(RegistrationFormKrygi.battle))
async def process_battle_yes(call: CallbackQuery, state: FSMContext):
    await call.message.delete()  # Удаляем сообщение с кнопками
    await state.update_data(battle="Да")
    await state.set_state(RegistrationFormKrygi.battle_style)
    await call.message.answer("В каком стиле?")

@router.callback_query(F.data == "battle_no", StateFilter(RegistrationFormKrygi.battle))
async def process_battle_no(call: CallbackQuery, state: FSMContext):
    await call.message.delete()  # Удаляем сообщение с кнопками
    await state.update_data(battle="Нет", battle_style="")  # Если нет – оставляем поле пустым
    await finish_registration(call.message, state)

@router.message(RegistrationFormKrygi.battle_style)
async def process_battle_style(message: types.Message, state: FSMContext):
    battle_style = message.text.strip()
    await state.update_data(battle_style=battle_style)
    await finish_registration(message, state)

@router.message(RegistrationFormKrygi.dance_experience)
async def process_dance_experience(message: types.Message, state: FSMContext):
    experience = message.text.strip()
    await state.update_data(dance_experience=experience)
    await finish_registration(message, state)

async def finish_registration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    generated_id = generate_id_for_user(data)
    row = [
        generated_id,
        data.get("tg_id", message.from_user.id),
        data.get("tg_username", message.from_user.username or ""),
        data.get("tg_link", f"https://t.me/{message.from_user.username}" if message.from_user.username else ""),
        data.get("role", ""),
        data.get("name", ""),
        data.get("age", ""),
        data.get("phone", ""),
        data.get("team", ""),
        data.get("styles", ""),
        data.get("battle", ""),
        data.get("battle_style", ""),
        data.get("dance_experience", "")
    ]
    try:
        sheet.append_row(row)
    except Exception as e:
        logging.error("Ошибка при записи в Google Sheets", exc_info=True)
        await message.answer("Произошла ошибка при регистрации. Попробуйте позже.")
        await state.clear()
        return

    final_text = (
        f"Спасибо за регистрацию!\n"
        f"Ваш ID: <b>{generated_id}</b>\n\n"
        "🤗Добро пожаловать в Dance комьюнити!\n"
        "✅Подпишись на канал, чтобы не пропустить важную информацию\n\n"
        "https://t.me/krygi_gel"
    )
    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.clear()

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
