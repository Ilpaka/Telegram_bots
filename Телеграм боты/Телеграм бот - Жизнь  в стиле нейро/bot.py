import asyncio
import logging
import sqlite3
import uuid
import hashlib
from datetime import datetime, timedelta  # Импортируем нужные классы
import random
import datetime as dt  # Импортируем модуль datetime под другим именем
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional


def adapt_datetime(dt_obj: dt.datetime) -> str:
    return dt_obj.isoformat()

def convert_datetime(s: bytes) -> dt.datetime:
    return dt.datetime.fromisoformat(s.decode())

sqlite3.register_adapter(dt.datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)


# ====== НАСТРОЙКИ (должны совпадать с main.py) ======
API_TOKEN = ""
ROBOKASSA_LOGIN = ""
ROBOKASSA_PASSWORD1 = ""
ROBOKASSA_PASSWORD2 = ""
SUPPORT_URL = "https://t.me/Pilya_07"
IS_TEST = 1
PRICE = 5500.00  # Число с двумя знаками после запятой
DESCRIPTION = ""

PHOTO = FSInputFile('Телеграм бот - Жизнь  в стиле нейро/templates/first_photo.jpg')

ADMINS = [772482922]
CHANNELS = [-1002349749601, -1002412419001]

# Инициализация aiogram
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# ----------------------------------------------------------------
#                    Функция подключения к БД
# ----------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(
        'subscriptions.db',
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=10  # задаем таймаут в 10 секунд
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # включаем режим WAL для лучшей конкурентности
    return conn

def get_or_create_user(telegram_id: int, username: str, first_name: str, last_name: str):
    """
    Ищет пользователя в таблице users по telegram_id.
    Если пользователь найден, обновляет его данные (username, first_name, last_name).
    Если не найден – создаёт новую запись.
    Возвращает внутренний id пользователя.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, first_name, last_name FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if row:
        user_id = row["id"]
        # Обновляем данные, если они отличаются
        if row["username"] != username or row["first_name"] != first_name or row["last_name"] != last_name:
            cursor.execute("""
                UPDATE users
                SET username = ?, first_name = ?, last_name = ?
                WHERE telegram_id = ?
            """, (username, first_name, last_name, telegram_id))
            conn.commit()
    else:
        cursor.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (telegram_id, username, first_name, last_name))
        conn.commit()
        user_id = cursor.lastrowid
    conn.close()
    return user_id

def create_invoice_record(invoice_id: str, user_id: int, amount: float, description: str):
    """
    Создаем запись о счете (invoice) в таблице invoices со статусом 'pending'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoices (invoice_id, user_id, amount, description, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (invoice_id, user_id, amount, description, datetime.now()))
    conn.commit()
    conn.close()

# ----------------------------------------------------------------
#                    Подпись для Робокассы
# ----------------------------------------------------------------
def generate_invoice_id() -> int:
    """
    Генерируем целое число в пределах [1..2147483647].
    """
    return random.randint(1, 2147483647)

def generate_robokassa_signature(merchant_login: str, amount: float, inv_id: int, password: str) -> str:
    """
    Формируем MD5-подпись для ссылки на оплату.
    Формат: MD5("{MerchantLogin}:{OutSum}:{InvId}:{Password1}")
    """
    amount_str = "{0:.2f}".format(amount)
    signature_string = f"{merchant_login}:{amount_str}:{inv_id}:{password}"
    return hashlib.md5(signature_string.encode()).hexdigest()

# ----------------------------------------------------------------
#                    Функции Проверок
# ----------------------------------------------------------------
def get_subscription_end_date(user_id: int) -> Optional[datetime]:
    """
    Возвращает дату окончания активной подписки пользователя.
    Если подписки нет или она неактивна, возвращает None.
    Учитываются подарочные подписки (invoice_id начинается с 'gift-').
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_time = datetime.now()
        query = """
            SELECT s.end_date
            FROM subscriptions s
            LEFT JOIN invoices i ON s.invoice_id = i.invoice_id
            WHERE s.user_id = ?
              AND s.is_active = 1
              AND s.end_date > ?
              AND (i.status = 'paid' OR s.invoice_id LIKE 'gift-%')
            LIMIT 1
        """
        cursor.execute(query, (user_id, current_time))
        row = cursor.fetchone()
        if row:
            end_date = row["end_date"]
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            return end_date
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении даты окончания подписки для user_id={user_id}: {e}")
        return None
    finally:
        conn.close()

def remove_user_from_blacklist(user_id: int):
    """
    Убирает пользователя из черного списка, устанавливая is_blacklisted = 0 для данного user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blacklisted = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------
#                    Функции админа
# ----------------------------------------------------------------
@dp.message(Command(commands=["ban"]))
async def admin_ban_subscription(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    args = message.text.split()[1:]

    if not args:
        await message.answer("Использование: /ban <telegram_id>")
        return

    try:
        target_telegram_id = int(args[0])
    except ValueError:
        await message.answer("Неверно указан telegram_id. Он должен быть числом.")
        return

    # Ищем пользователя в БД по telegram_id (не создаём запись, если пользователь отсутствует)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (target_telegram_id,))
    row = cursor.fetchone()
    if not row:
        await message.answer("Пользователь не найден в базе данных.")
        conn.close()
        return

    internal_user_id = row["id"]

    # Отзываем активные подписки у пользователя
    cursor.execute("UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1", (internal_user_id,))
    # Добавляем пользователя в черный список
    cursor.execute("UPDATE users SET is_blacklisted = 1 WHERE id = ?", (internal_user_id,))
    conn.commit()
    conn.close()

    # Проходим по всем каналам и баним пользователя в них, чтобы он не смог зайти через папку
    for channel in CHANNELS:
        try:
            await bot.ban_chat_member(chat_id=channel, user_id=target_telegram_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении пользователя {target_telegram_id} из канала {channel}: {e}")

    await message.answer(
        f"Подписка(и) пользователя с Telegram ID {target_telegram_id} отозвана, пользователь забанен и удалён из всех каналов."
    )

# def create_subscription(user_id: int, invoice_id: str, days: int = 30):
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     cursor.execute("SELECT id FROM subscriptions WHERE invoice_id = ?", (invoice_id,))
#     if cursor.fetchone() is not None:
#         # Запись уже существует — ничего не делаем, чтобы не создавать дубликат
#         conn.close()
#         return
    
#     start_date = datetime.now()
#     end_date = start_date + timedelta(days=days)
#     cursor.execute("""
#         INSERT INTO subscriptions (user_id, invoice_id, start_date, end_date, is_active)
#         VALUES (?, ?, ?, ?, 1)
#     """, (user_id, invoice_id, start_date, end_date))
#     conn.commit()
#     conn.close()

def create_subscription(user_id: int, invoice_id: str, duration: int = 30, unit: str = 'days'):
    """
    Создаёт подписку для пользователя с заданной длительностью.
    Если unit == 'minutes', то подписка действует duration минут,
    иначе — duration дней.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM subscriptions WHERE invoice_id = ?", (invoice_id,))
    if cursor.fetchone() is not None:
        # Если такая подписка уже существует, ничего не делаем
        conn.close()
        return

    start_date = datetime.now()
    if unit == 'minutes':
        end_date = start_date + timedelta(minutes=duration)
    else:
        end_date = start_date + timedelta(days=duration)

    cursor.execute("""
        INSERT INTO subscriptions (user_id, invoice_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (user_id, invoice_id, start_date, end_date))
    conn.commit()
    conn.close()


@dp.message(Command(commands=["gift_sub"]))
# @dp.message(Command(commands=["gift_sub"]))
async def admin_gift_subscription(message: Message):
    # Проверяем, что команду отправил админ
    if message.from_user.id not in ADMINS:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Парсим аргументы: ожидается /gift_sub <telegram_id> [длительность (например, 30 или 15m)]
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /gift_sub <telegram_id> [количество (дней или минут, например: 30 или 15m)]")
        return

    try:
        target_telegram_id = int(args[0])
    except ValueError:
        await message.answer("Неверно указан telegram_id. Он должен быть числом.")
        return

    # По умолчанию выдаём 30 дней
    duration = 30
    unit = "days"
    if len(args) > 1:
        duration_str = args[1]
        # Если аргумент заканчивается на "m" или "min", выдаём подписку в минутах
        if duration_str.endswith("m") or duration_str.endswith("min"):
            try:
                duration = int(duration_str.rstrip("m").rstrip("min"))
                unit = "minutes"
            except ValueError:
                await message.answer("Неверно указано количество минут, будет использовано значение по умолчанию: 30 дней.")
                duration = 30
                unit = "days"
        else:
            try:
                duration = int(duration_str)
            except ValueError:
                await message.answer("Неверно указано количество дней, будет использовано значение по умолчанию: 30.")
                duration = 30

    # Получаем или создаём пользователя в БД (если данные неизвестны, передаем пустые строки)
    target_user_id = get_or_create_user(target_telegram_id, "", "", "")
    
    # Генерируем уникальный идентификатор счета с префиксом "gift-"
    invoice_id = f"gift-{uuid.uuid4()}"
    
    try:
        create_subscription(target_user_id, invoice_id, duration, unit)
    except Exception as e:
        await message.answer(f"Ошибка при создании подписки: {e}")
        return

    # Удаляем пользователя из чёрного списка и разблокируем его в каналах
    remove_user_from_blacklist(target_user_id)
    for channel in CHANNELS:
        try:
            await bot.unban_chat_member(chat_id=channel, user_id=target_telegram_id)
        except Exception as e:
            logging.error(f"Ошибка при разблокировке пользователя {target_telegram_id} в канале {channel}: {e}")

    # Формируем ответное сообщение с указанием единицы измерения
    if unit == "minutes":
        time_str = f"{duration} минут"
    else:
        time_str = f"{duration} дней"
        
    await message.answer(
        f"Подписка выдана пользователю с Telegram ID {target_telegram_id} на {time_str}.\n"
        f"Invoice ID: {invoice_id}\nПользователь удалён из чёрного списка и разблокирован в каналах."
    )

# ----------------------------------------------------------------
#                    Хендлеры бота
# ----------------------------------------------------------------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    user_id = get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or ""
    )

    end_date = get_subscription_end_date(user_id)

    if end_date:
        end_date_str = end_date.strftime("%d.%m.%Y")
        text = f"Ваша подписка активна до {end_date_str}."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Получить доступ к каналам", callback_data="subscribe_channels")],
            [InlineKeyboardButton(text="Поддержка", url=SUPPORT_URL)]
        ])
        await message.answer(text, reply_markup=keyboard)
    else:
        # Подписка не активна – отправляем стандартное приветственное сообщение с кнопками "Перейти к оплате" и "Поддержка"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти к оплате", callback_data="go_pay")],
            [InlineKeyboardButton(text="Поддержка", url=SUPPORT_URL)]
        ])
        text=f"""Привет, {message.from_user.first_name} ! ✨\n
Вы сделали первый шаг в пространство, где каждая ваша проблема и любой вопрос могут быть решены легко, творчески и максимально экологично.\n
Здесь мы не просто ищем ответы — мы создаем новые возможности и открываем двери к внутреннему миру.💫\n\n
ЭТО ЖИЗНЬ В СТИЛЕ НЕЙРО🎨\n\n
Мир Нейрографики, где супер-работающие алгоритмы превращают любые трудности в яркие, творческие и безусловно экологичные решения.\n\n
Представь: 
* Срочно нужны деньги * - порисуй и эта тема решена\n
* Давно хочешь что-то продать?* - >3 алгоритма и вопрос закрыт!)\n
* Мечтаешь о прекрасных отношениях *с любимым мужчиной - > найди время для рисования и твоя мечта станет явью\n
* Не чувствуешь себя женственной, не получала подарков, цветов, комплиментов? Все поправимо! Рисуй!*\n 
*Хочешь наладить отношения с родителями/родом?* А ведь это наша главное сила! И здесь тоже у вас все получится!\n
❤️ЛЮБОЙ ЗАПРОС - РЕШАЕМ!\n
Здесь Цели становятся яркими и достижимыми, словно нарисованные на холсте твоей мечты!\n\n
Нейрографика – это:
* Простой и увлекательный метод, доступный каждому.*\n
* Мощный инструмент для самопознания и саморазвития.*\n
* Ключ к гармонии с собой и миром.*\n
Хочешь ЖИТЬ В СТИЛЕ НЕЙРО?\n
Тогда приглашаю в наш уникальный мир, который откроет двери в бескрайний океан возможностей Нейрографики!\n
Более 40 курсов по различным направлениям - всего за 58000р 5555 рублей в месяц!)\n
ЖИТЬ В СТИЛЕ НЕЙРО ЗДЕСЬ И СЕЙЧАС!\n
Контакты: https://neyrografinya.ru/kontakt\n
Оферта: https://neyrografinya.ru/oferta"""
        #отправка фото
        try:
            await message.answer_photo(photo=PHOTO)
        except Exception as e:
            logging.warning(f"Не удалось отправить фото: {e}")
        
        await message.answer(text, reply_markup=keyboard,
                             parse_mode="HTML",
                             disable_web_page_preview=True)

@dp.callback_query(F.data == "go_pay")
async def instruction_for_pay(callback_query: CallbackQuery):
    """
    Отправляем пользователю инструкцию по оплате.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {PRICE} руб.", callback_data="process_pay")],
        [InlineKeyboardButton(text="Поддержка", url=SUPPORT_URL)]
    ])
    await callback_query.message.edit_text(
        text="Инструкция по оплате через Робокассу (тестовый режим). Нажмите кнопку ниже:",
        reply_markup=kb
    )

@dp.callback_query(F.data == "process_pay")
async def process_pay(callback_query: CallbackQuery):
    """
    Обработка запроса на оплату: формируем счет, ссылку для оплаты.
    После оплаты отправляем сообщение с кнопкой для проверки доступа к каналам.
    """
    db_user_id = get_or_create_user(
        telegram_id=callback_query.from_user.id,
        username=callback_query.from_user.username or "",
        first_name=callback_query.from_user.first_name or "",
        last_name=callback_query.from_user.last_name or ""
    )
    invoice_id = generate_invoice_id()
    amount = PRICE
    description = DESCRIPTION
    create_invoice_record(invoice_id, db_user_id, amount, description)
    signature = generate_robokassa_signature(ROBOKASSA_LOGIN, PRICE, invoice_id, ROBOKASSA_PASSWORD1)
    payment_url = (
        f"https://auth.robokassa.ru/Merchant/Index.aspx?"
        f"MerchantLogin={ROBOKASSA_LOGIN}"
        f"&OutSum={PRICE:.2f}"
        f"&InvoiceID={invoice_id}"
        f"&Description={DESCRIPTION}"
        f"&SignatureValue={signature}"
        f"&IsTest={IS_TEST}"
    )
    
    keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {PRICE:.2f} руб.", url=payment_url)],
        [InlineKeyboardButton(text="Проверить доступ", callback_data="subscribe_channels")],
        [InlineKeyboardButton(text="Поддержка", url=SUPPORT_URL)]    
    ]
)

    await callback_query.message.edit_text(
        text=("Для оплаты нажмите на кнопку ниже ↓\n"
              "После успешной оплаты доступ откроется автоматически в течение 5 минут.\n"
              "После оплаты нажмите кнопку ниже, чтобы получить доступ к приватным каналам.\n"
              "Если доступ не открывается — обратитесь в поддержку."),
        reply_markup= keyboard)

def check_subscription_status(user_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_time = datetime.now()

        query = """
            SELECT s.end_date
            FROM subscriptions s
            LEFT JOIN invoices i ON s.invoice_id = i.invoice_id
            WHERE s.user_id = ?
              AND s.is_active = 1
              AND s.end_date > ?
              AND (i.status = 'paid' OR s.invoice_id LIKE 'gift-%')
            LIMIT 1
        """

        cursor.execute(query, (user_id, current_time))
        row = cursor.fetchone()
        if row:
            return True
        return False
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки для user_id={user_id}: {e}")
        return False
    finally:
        conn.close()

@dp.callback_query(F.data == "subscribe_channels")
async def subscribe_channels_handler(callback_query: CallbackQuery):
    
    # Получаем внутренний ID пользователя из БД, используя get_or_create_user
    internal_user_id = get_or_create_user(
        telegram_id=callback_query.from_user.id,
        username=callback_query.from_user.username or "",
        first_name=callback_query.from_user.first_name or "",
        last_name=callback_query.from_user.last_name or ""
    )
    
    if not check_subscription_status(internal_user_id):
        await callback_query.answer("У вас нет активной подписки или срок подписки истёк.",show_alert=True)
        return

    folder_link = "https://t.me/addlist/m929w2BRFSYxZDZi"  # ссылка на папку с каналами
    # Новая клавиатура – кнопка "Открыть папку с каналами" и кнопка "Поддержка"
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть папку с каналами", url=folder_link)],
        [InlineKeyboardButton(text="Поддержка", url=SUPPORT_URL)]
    ])
    text = "Ваша подписка активна. Вот ссылка на папку с каналами:"
    
    await callback_query.answer(text="Ваша подписка активна 😁", show_alert = True)
    await callback_query.message.edit_text(text=text, reply_markup=new_keyboard)

# ----------------------------------------------------------------
#                    ЗАДАЧИ ДЛЯ ПЛАНИРОВЩИКА (APScheduler)
# ----------------------------------------------------------------
scheduler = AsyncIOScheduler()

async def handle_expired_subscription():
    """
    Обрабатываем истекшие подписки: для каждого пользователя с истёкшей подпиской:
      - помечаем подписку как неактивную;
      - обновляем статус пользователя (is_blacklisted = 1);
      - отправляем уведомление пользователю;
      - баним пользователя во всех указанных каналах.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    
    # Получаем информацию о подписках и соответствующих telegram_id пользователей
    query = """
        SELECT s.id AS subscription_id, s.user_id, u.telegram_id
        FROM subscriptions s
        JOIN users u ON s.user_id = u.id
        WHERE s.is_active = 1 AND s.end_date < ?
    """
    cursor.execute(query, (now,))
    expired_subscriptions = cursor.fetchall()
    
    for sub in expired_subscriptions:
        internal_user_id = sub["user_id"]
        telegram_id = sub["telegram_id"]
        subscription_id = sub["subscription_id"]
        
        # Помечаем подписку как неактивную
        cursor.execute("UPDATE subscriptions SET is_active = 0 WHERE id = ?", (subscription_id,))
        # Добавляем пользователя в черный список
        cursor.execute("UPDATE users SET is_blacklisted = 1 WHERE id = ?", (internal_user_id,))
        
        # Отправляем уведомление пользователю (используем telegram_id)
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="Ваша подписка закончилась"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения пользователю {telegram_id}: {e}")
        
        # Баним пользователя во всех каналах
        for channel in CHANNELS:
            try:
                await bot.ban_chat_member(chat_id=channel, user_id=telegram_id)
            except Exception as e:
                logging.error(f"Ошибка при бане пользователя {telegram_id} в канале {channel}: {e}")
    
    conn.commit()
    conn.close()

# Запускаем проверку каждую минуту
scheduler.add_job(handle_expired_subscription, 'interval', minutes=1)


# ----------------------------------------------------------------
# ЗАПУСК БОТА
# ----------------------------------------------------------------
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Запуск Telegram-бота...")
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
