import logging
import os
from aiogram import Bot, Dispatcher, executor, types
import aiohttp

# Получение токена из переменных окружения или прямое указание
API_TOKEN = ("")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
    
async def get_exchange_rates(base: str = "USD"):
    """
    Получает данные о курсах валют с базовой валютой base.
    Используется API exchangerate.host.
    """
    url = f"https://api.exchangerate.host/latest?base={base}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """
    Обрабатывает команду /start.
    Отправляет приветственное сообщение и инструкции.
    """
    welcome_text = (
        "Привет! Я бот для получения информации о курсах валют.\n"
        "Используй команду /rate с указанием базовой валюты.\n"
        "Например: /rate USD\n"
        "Если не указать валюту, по умолчанию используется USD."
    )
    await message.answer(welcome_text)

@dp.message_handler(commands=['rate'])
async def cmd_rate(message: types.Message):
    """
    Обрабатывает команду /rate.
    Принимает параметр базовой валюты (например, USD, EUR) и отправляет курсы избранных валют.
    """
    # Получаем аргументы команды (если есть)
    args = message.get_args()
    base_currency = args.upper().strip() if args else "USD"
    
    try:
        data = await get_exchange_rates(base=base_currency)
        if "rates" in data:
            rates = data["rates"]
            # Выбираем основные валюты для отображения
            currencies = ["EUR", "RUB", "GBP", "UAH"]
            reply = f"Курсы валют относительно {base_currency}:\n"
            for cur in currencies:
                # Если данные по валюте отсутствуют, выводим сообщение "Нет данных"
                value = rates.get(cur, "Нет данных")
                reply += f"{cur}: {value}\n"
            await message.answer(reply)
        else:
            await message.answer("Не удалось получить данные о курсах валют.")
    except Exception as e:
        logging.exception("Ошибка при получении данных: %s", e)
        await message.answer("Произошла ошибка при получении данных о валютном курсе.")

if __name__ == '__main__':
    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
