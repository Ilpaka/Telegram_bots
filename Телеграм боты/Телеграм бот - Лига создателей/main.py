import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
from aiogram.types import BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
from aiogram.filters.state import StateFilter
from aiogram.types import CallbackQuery
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


logging.basicConfig(level=logging.INFO)

API_TOKEN = ""

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# -- Настройка Google Sheets --
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name("Телеграм бот - Лига создателей/credentials/tonal-rune-446721-p0-6ba0dd0feadc.json", scope)
client = gspread.authorize(creds)

sheet = client.open("Liga_Sozdateley_Registrations").sheet1

EXPECTED_HEADERS = [
    "ID",
    "tg_id",
    "tg_username",
    "tg_link",
    "status",
    "fullname",
    "age",
    "phone",
    "presentation",
    "project_name",
    "project_info",
    "target_audience",
    "branding",
    "goals",
    "participant_help",
    "participant_learn"
]

def increment_prefix(prefix: str) -> str:
    """
    Увеличивает 'префикс' в стиле base-26 (A..Z -> AA..ZZ -> AAA..).
    Пример:
      'A'  -> 'B'
      'Z'  -> 'AA'
      'AZ' -> 'BA'
      'ZZ' -> 'AAA'
    """
    chars = list(prefix)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] < 'Z':
            # Если текущая буква меньше 'Z', просто увеличиваем её
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
        else:
            # Если 'Z', превращаем её в 'A' и двигаемся дальше влево
            chars[i] = 'A'
            i -= 1
    # Если все символы были 'Z', то добавляем 'A' в начале
    return "A" + "".join(chars)

def increment_id(last_id: str) -> str:
    """
    last_id имеет вид 'A0', 'B7', 'Z9', 'AA3' и т.д.
    Префикс (всё кроме последнего символа) — буквы A..Z, AA..ZZ, ...
    Суффикс (последний символ) — цифра 0..9.
    
    Пример переходов:
      A0 -> A1 -> A2 ... A9 -> B0 -> B1 ... Z9 -> AA0 -> AA1 ...
    """
    prefix = last_id[:-1]  # всё, кроме последнего символа
    suffix_char = last_id[-1]  # последний символ — цифра
    
    # Безопасно конвертируем в int (считаем, что в ID всегда одна цифра)
    suffix = int(suffix_char)

    if suffix < 9:
        # Просто увеличиваем суффикс
        return f"{prefix}{suffix + 1}"
    else:
        # Сбрасываем суффикс в 0 и инкрементируем префикс
        new_prefix = increment_prefix(prefix)
        return f"{new_prefix}0"


async def generate_id():
    """
    Генерирует новый ID вида A0..A9 -> B0..B9 -> ... -> Z9 -> AA0..AA9 -> AB0..AB9 -> ...
    """
    try:
        records = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        # Если таблица пуста — начинаем с A0
        if not records:
            return "A0"
        last_id = records[-1]['ID']
        return increment_id(last_id)
    except Exception as e:
        logging.error("Ошибка при получении ID из Google Sheets", exc_info=True)
        # Можете вернуть какой-то дефолт или пробросить дальше
        raise e


class RegistrationForm(StatesGroup):
    status = State()
    fullname = State()
    age = State()
    phone = State()
    presentation = State()
    # Создатель
    project_name = State()
    project_info = State()
    target_audience = State()
    branding = State()
    goals = State()
    # Участник
    participant_help = State()
    participant_learn = State()

    wait_for_subscription = State()
    wait_for_subscription_leader = State()


# Клавиатура для выбора статуса
status_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Создатель")],
        [KeyboardButton(text="Участник")]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    welcome_text = (
        "Привет! 😺\n"
        "Я помогу зарегистрироваться на мероприятие Лиги Создателей и получить доступ "
        "к Телеграм-каналу участников.\n\n"
        "Ответь на несколько вопросов — честно и подробно.\n"
        "Это поможет создать твою самопрезентацию и подготовить бейдж для Форума 🐱"
    )
    await message.answer(welcome_text, parse_mode="HTML")

    telegram_id = message.from_user.id
    username = message.from_user.username or ""
    user_link = f"https://t.me/{username}" if username else ""

    await state.update_data(
        tg_id=telegram_id,
        tg_username=username,
        tg_link=user_link
    )

    await state.set_state(RegistrationForm.status)
    await message.answer(
        "Вы Создатель или Участник?",
        reply_markup=status_keyboard
    )

@router.message(RegistrationForm.status)
async def process_status(message: types.Message, state: FSMContext):
    await state.update_data(status=message.text)
    await state.set_state(RegistrationForm.fullname)
    await message.answer("Введите ваше ФИО:", reply_markup=ReplyKeyboardRemove())

@router.message(RegistrationForm.fullname)
async def process_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await state.set_state(RegistrationForm.age)
    await message.answer("Введите ваш возраст:")


@router.message(RegistrationForm.age)
async def process_age(message: types.Message, state: FSMContext):
    age_str = message.text.strip()
    
    # 1. Проверяем, что введены только цифры (без знаков +, - и т.д.)
    if not re.match(r'^\d+$', age_str):
        await message.answer("Пожалуйста, введите возраст цифрами (например, 20):")
        return

    # 2. Преобразуем в число
    age = int(age_str)

    # 3. Проверяем диапазон
    if age < 13:
        # Создаём inline-клавиатуру с кнопкой
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Написать @sash_alexandrovn",
                        url="https://t.me/sash_alexandrovn"
                    )
                ]
            ]
        )
        await message.answer(
            "Если вам ещё нет 13 лет, тогда, пожалуйста, оставьте свой ник в Telegram.\n"
            "Или свяжитесь напрямую:",
            reply_markup=keyboard
        )
        # Сбрасываем сессию/данные
        await state.clear()
        return
    elif age > 99:
        await message.answer(
            "ОГО! Вы знаете что-то такое про интернет? Уверены, что верно указали возраст?\nВведите настоящий возраст:"
        )
        return

    # Если всё нормально, записываем в состояние и переходим дальше
    await state.update_data(age=age_str)
    
    # Далее переходим к следующему состоянию (например, запрос телефона)
    await state.set_state(RegistrationForm.phone)
    await message.answer(
        "Отправьте ваш номер телефона (или введите вручную в формате +1234567890):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
            resize_keyboard=True
        )
    )

@router.message(RegistrationForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone_number = message.contact.phone_number
    else:
        phone_number = message.text
        if not re.match(r'^\+?\d{10,15}$', phone_number):
            await message.answer(
                "Некорректный формат номера телефона. Введите номер в формате +1234567890:"
            )
            return
    await state.update_data(phone=phone_number)
    await state.set_state(RegistrationForm.presentation)

    data = await state.get_data()
    if data['status'].lower() == "создатель":
        await message.answer(
            'Расскажите немного о себе (например, опыт, чем занимаетесь).',
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            'Расскажите немного о себе (например, чем увлекаетесь).',
            reply_markup=ReplyKeyboardRemove()
        )

@router.message(RegistrationForm.presentation)
async def process_presentation(message: types.Message, state: FSMContext):
    await state.update_data(presentation=message.text)
    data = await state.get_data()

    if data['status'].lower() == "создатель":
        await state.set_state(RegistrationForm.project_name)
        await message.answer("Укажите название вашего проекта или секции:")
    else:
        await state.set_state(RegistrationForm.participant_help)
        await message.answer(
            'Кому и чем вы можете помочь другим участникам или проектам?'
        )

# ---------------- Создатель ---------------- #

@router.message(RegistrationForm.project_name)
async def process_project_name(message: types.Message, state: FSMContext):
    await state.update_data(project_name=message.text)
    await state.set_state(RegistrationForm.project_info)
    await message.answer(
        'Расскажите подробнее о вашем проекте (суть, цель, пример аудитории).'
    )

@router.message(RegistrationForm.project_info)
async def process_project_info(message: types.Message, state: FSMContext):
    await state.update_data(project_info=message.text)
    await state.set_state(RegistrationForm.target_audience)
    await message.answer('Для кого предназначен ваш проект? (возраст, сфера деятельности)')

@router.message(RegistrationForm.target_audience)
async def process_target_audience(message: types.Message, state: FSMContext):
    await state.update_data(target_audience=message.text)
    await state.set_state(RegistrationForm.branding)
    await message.answer('Есть ли у вас оформленный бренд или логотип для проекта? (Да/Нет)')

@router.message(RegistrationForm.branding)
async def process_branding(message: types.Message, state: FSMContext):
    await state.update_data(branding=message.text)
    await state.set_state(RegistrationForm.goals)
    await message.answer(
        'Какие цели вы преследуете, участвуя в форуме? (поиск партнёров, обмен опытом и т.д.)'
    )

@router.message(RegistrationForm.goals)
async def process_goals_subscribe(message: types.Message, state: FSMContext):
    """
    Вместо немедленной записи в Google Sheets — просим Руководителя подписаться на канал.
    После нажатия "Я подписался!" сделаем проверку подписки (см. callback ниже).
    """
    await state.update_data(goals=message.text)

    # Создаём inline-клавиатуру для подписки:
    # 1) Кнопка-ссылка на канал
    # 2) Кнопка "Я подписался!" (callback_data="check_sub_leader")
    subscribe_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подписаться",
                    url="https://t.me/LigaSozdateley"  # ваш канал
                )
            ],
            [
                InlineKeyboardButton(
                    text="Я подписался!",
                    callback_data="check_sub_leader"
                )
            ]
        ]
    )

    await message.answer(
        "Остался всего один шаг! Подпишитесь на канал Создателей, чтобы завершить регистрацию:",
        reply_markup=subscribe_keyboard
    )

    # Переходим в новое состояние, чтобы дождаться нажатия "Я подписался!"
    await state.set_state(RegistrationForm.wait_for_subscription_leader)


##############################################################################
# 2. CALLBACK-ХЕНДЛЕР, который сработает при нажатии "Я подписался!" у Руководителя
##############################################################################

@router.callback_query(
    F.data == "check_sub_leader",  # callback_data из кнопки
    StateFilter(RegistrationForm.wait_for_subscription_leader)
)
async def check_subscription_leader_callback(call: CallbackQuery, state: FSMContext):
    """
    Проверяем, подписан ли Создатель на канал.
    Если подписан — записываем данные в Sheets, отправляем финальное сообщение.
    Если нет — просим подписаться.
    """
    channel_id = "@LigaSozdateley"  # или numeric ID, если канал приватный и бот админ

    # Проверяем статус через getChatMember
    member_info = await bot.get_chat_member(chat_id=channel_id, user_id=call.from_user.id)
    if member_info.status in ("member", "administrator", "creator"):
        # ---- Пользователь действительно подписан ----
        await call.message.delete()

        user_data = await state.get_data()

        try:
            generated_id = await generate_id()
            sheet.append_row([
                generated_id,
                user_data.get('tg_id', ''),
                user_data.get('tg_username', ''),
                user_data.get('tg_link', ''),
                user_data.get('status', ''),
                user_data.get('fullname', ''),
                user_data.get('age', ''),
                user_data.get('phone', ''),
                user_data.get('presentation', ''),
                user_data.get('project_name', ''),
                user_data.get('project_info', ''),
                user_data.get('target_audience', ''),
                user_data.get('branding', ''),
                user_data.get('goals', ''),
                '',  # participant_help
                ''   # participant_learn
            ])
        except Exception as e:
            logging.error("Ошибка при записи (append_row) данных Руководителя", exc_info=True)
            await call.message.answer(
                "Произошла ошибка во время регистрации. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await call.answer()
            return

        # Завершительное сообщение
        await call.message.answer(
            f"Спасибо за регистрацию! Ваш ID: <b>{generated_id}</b>\n"
            "Добро пожаловать в сообщество!\n"
            "Ссылка на телеграм-канал: https://t.me/LigaSozdateley\n\n"
            "<a href='https://t.me/Ilya_Panov_projects_bot'>Создатель бота Илья Панов (@Pilya_07)</a>",
            parse_mode="HTML"
        )
        await state.clear()

    else:
        # ---- Не подписан ----
        await call.message.answer(
            "Кажется, вы ещё не подписались. Подпишитесь на канал, чтобы завершить регистрацию!"
        )

# ---------------- Участник ---------------- #


@router.message(RegistrationForm.participant_help)
async def process_participant_help(message: types.Message, state: FSMContext):
    await state.update_data(participant_help=message.text)
    await state.set_state(RegistrationForm.participant_learn)
    await message.answer(
        "Какие навыки или знания вы хотели бы приобрести на форуме?"
    )

@router.message(RegistrationForm.participant_learn)
async def process_participant_learn(message: types.Message, state: FSMContext):
    """
    Вместо записи в Sheets и отправки карточки мы предлагаем пользователю
    сначала подписаться на канал, а после нажатия "Я подписался!" бот проверит подписку.
    """
    await state.update_data(participant_learn=message.text)

    # Создаём inline-клавиатуру:
    # 1) Кнопка с ссылкой на канал.
    # 2) Кнопка "Я подписался!" (callback_data="check_sub"), 
    #    по которой мы проверяем подписку в отдельном хендлере.
    subscribe_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подписаться",
                    url="https://t.me/LigaSozdateley"  # Замените на ваш канал, если нужно
                )
            ],
            [
                InlineKeyboardButton(
                    text="Я подписался!",
                    callback_data="check_sub"
                )
            ]
        ]
    )

    await message.answer(
        "Осталось совсем чуть-чуть! Подпишитесь на канал Создателей, чтобы завершить регистрацию:",
        reply_markup=subscribe_keyboard
    )

    # Теперь ждём, пока пользователь нажмёт "Я подписался!"
    # (переходим в состояние wait_for_subscription)
    await state.set_state(RegistrationForm.wait_for_subscription)

@router.callback_query(
    F.data == "check_sub",
    StateFilter(RegistrationForm.wait_for_subscription)
)
@router.callback_query(
    F.data == "check_sub",  # callback_data из кнопки
    StateFilter(RegistrationForm.wait_for_subscription)
)
async def check_subscription_callback(call: CallbackQuery, state: FSMContext):
    channel_id = "@LigaSozdateley"  # Или numeric ID, напр. -1001234567890

    # Проверяем подписку на канал
    member_info = await bot.get_chat_member(chat_id=channel_id, user_id=call.from_user.id)
    if member_info.status in ("member", "administrator", "creator"):
        # Пользователь подписан
        await call.message.delete()
        user_data = await state.get_data()
        try:
            generated_id = await generate_id()

            # Генерируем карточку
            card_bytes = await generate_user_card(
                bot,
                user_data['tg_id'],
                generated_id,
                user_data['fullname']
            )

            # Загружаем карточку на Google Drive
            card_url = await upload_to_google_drive(card_bytes, generated_id)

            # Добавляем данные в Google Sheets
            sheet.append_row([
                generated_id,
                user_data.get('tg_id', ''),
                user_data.get('tg_username', ''),
                user_data.get('tg_link', ''),
                user_data.get('status', ''),
                user_data.get('fullname', ''),
                user_data.get('age', ''),
                user_data.get('phone', ''),
                user_data.get('presentation', ''),
                '',  # project_name
                '',  # project_info
                '',  # target_audience
                '',  # branding
                '',  # goals
                user_data.get('participant_help', ''),
                user_data.get('participant_learn', ''),
                card_url  # Ссылка на карточку в Google Drive
            ])

            # Отправляем карточку в чат
            photo_input = BufferedInputFile(
                file=card_bytes.getvalue(),
                filename="card.png"
            )
            await call.message.answer_photo(
                photo=photo_input,
                caption=
                    f"Спасибо за регистрацию!\n"
                    f"Ваш ID: <b>{generated_id}</b>\n"
                    "Добро пожаловать в сообщество!\n"
                    "Ссылка на телеграм-канал: https://t.me/LigaSozdateley\n\n"
                    "<a href='https://t.me/Ilya_Panov_projects_bot'>Создатель бота Илья Панов (@Pilya_07)</a>",
                    parse_mode="HTML"
            )
            # Сбрасываем состояние
            await state.clear()
        except Exception:
            logging.error("Ошибка при записи (append_row)", exc_info=True)
            await call.message.answer(
                "Произошла ошибка во время регистрации. Попробуйте позже или обратитесь к администратору."
            )
            await call.answer()
            return
    else:
        # Пользователь не подписан
        await call.message.answer(
            "Кажется, вы ещё не подписались. Подпишитесь на канал, чтобы завершить регистрацию!"
        )
    await call.answer()


# ------------------ Генерация картинки (Pillow) ------------------

# Путь к JSON-файлу сервисного аккаунта
SERVICE_ACCOUNT_FILE = 'Телеграм бот - Лига создателей/credentials/tonal-rune-446721-p0-6ba0dd0feadc.json'

# ID папки в Google Drive
FOLDER_ID = '1uHEu4DYfAVB9M2SWUwmt9nb6JcbBZwtx'

# Авторизация в API
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=['https://www.googleapis.com/auth/drive.file']
)
drive_service = build('drive', 'v3', credentials=credentials)


async def upload_to_google_drive(file_bytes: io.BytesIO, user_id: str) -> str:
    """
    Загружает файл в Google Drive с именем файла по ID пользователя и возвращает ссылку.
    """
    # Имя файла будет ID пользователя
    filename = f"{user_id}.png"

    # Создаём медиафайл из байтов
    media = MediaIoBaseUpload(file_bytes, mimetype='image/png', resumable=True)

    # Параметры файла
    file_metadata = {
        'name': filename,         # Имя файла = ID пользователя
        'parents': [FOLDER_ID]    # ID папки на Google Drive
    }

    # Загружаем файл
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # Делаем файл доступным по ссылке
    drive_service.permissions().create(
        fileId=file['id'],
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    # Возвращаем ссылку
    file_url = f"https://drive.google.com/uc?id={file['id']}"
    return file_url



async def generate_user_card(bot, user_id: int, user_id_str: str, fio: str) -> io.BytesIO:
    """
    1. Открываем локальный шаблон (photo_card.png) из указанного пути.
    2. Получаем аватарку пользователя (либо заглушку).
    3. Вырезаем круг, добавляем чёрный контур, вставляем чуть выше центра.
    4. Пишем ID и ФИО (чёрным шрифтом) под аватаркой.
    5. Возвращаем результат в BytesIO (PNG).
    """

    # ----- Пути, которые всегда используем -----
    TEMPLATE_PATH = "Телеграм бот - Лига создателей/templates/photo_card.png"
    FONT_PATH = "Телеграм бот - Лига создателей/fonts/arial_bolditalicmt.ttf"

    # 1. Загружаем шаблон
    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    tpl_width, tpl_height = template.size  # предположим, ~700×700

    # 2. Получаем аватарку
    photos = await bot.get_user_profile_photos(user_id, limit=1)
    if photos.total_count > 0:
        file_id = photos.photos[0][0].file_id
        file_obj = await bot.get_file(file_id)
        avatar_bytes = await bot.download_file(file_obj.file_path)
        avatar_image = Image.open(avatar_bytes).convert("RGBA")
    else:
        # Заглушка, если нет аватарки
        avatar_image = Image.new("RGBA", (300, 300), (128, 128, 128, 255))

    # 3. Делаем круг аватарки и добавляем чёрный контур
    avatar_size = (250, 250)
    circle_avatar = make_circle_avatar(avatar_image, avatar_size)
    circle_avatar_with_border = add_circle_outline(circle_avatar, border=5, color=(0, 0, 0, 255))

    # Координаты вставки (чуть выше центра)
    avatar_x = (tpl_width - circle_avatar_with_border.width) // 2
    avatar_y = 200
    # Вклеиваем
    template.paste(circle_avatar_with_border, (avatar_x, avatar_y), circle_avatar_with_border)

    # 4. Добавляем текст (ID и ФИО) — шрифт arial_bolditalicmt.ttf
    draw = ImageDraw.Draw(template)

    font_title = ImageFont.truetype(FONT_PATH, 42)
    font_text = ImageFont.truetype(FONT_PATH, 42)

    # --- ID ---
    id_text = f"ID: {user_id_str}"
    id_x = tpl_width // 2
    id_y = avatar_y + circle_avatar_with_border.height + 75
    draw.text(
        (id_x, id_y),
        id_text,
        font=font_title,
        fill="black",
        anchor="mm"
    )

    # --- ФИО ---
    fio_text = fio
    fio_x = tpl_width // 2
    fio_y = id_y + 50
    draw.text(
        (fio_x, fio_y),
        fio_text,
        font=font_text,
        fill="black",
        anchor="mm"
    )

    # 5. Сохраняем результат в BytesIO и возвращаем
    output = io.BytesIO()
    template.save(output, format="PNG")
    output.seek(0)
    return output


def make_circle_avatar(image: Image.Image, size=(250, 250)) -> Image.Image:
    """Вырезаем круг из аватарки (RGBA)."""
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    image.putalpha(mask)
    return image


def add_circle_outline(circle_image: Image.Image, border=3, color=(0,0,0,255)) -> Image.Image:
    """
    Добавляет вокруг вырезанного круга (RGBA) обводку (border px).
    """
    w, h = circle_image.size
    new_w = w + border*2
    new_h = h + border*2

    outline_img = Image.new("RGBA", (new_w, new_h), (0,0,0,0))
    outline_draw = ImageDraw.Draw(outline_img)
    outline_draw.ellipse((0, 0, new_w, new_h), fill=color)
    outline_img.alpha_composite(circle_image, dest=(border, border))

    return outline_img
# ---------------- Запуск бота ----------------

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())