import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.methods import DeleteWebhook
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import requests

TOKEN = ''

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)
dp = Dispatcher()

# Словарь для хранения выбранной пользователем модели
user_models = {}

# Полный словарь моделей (для кнопки "О моделях" и полного списка)
models = {
    "Qwen-32B": "Qwen/QwQ-32B",  # программирование
    "Llama-3.2": "meta-llama/Llama-3.2-90B-Vision-Instruct",
    "DeepSeek-R1": "deepseek-ai/DeepSeek-R1",
    "Llama-3.3": "meta-llama/Llama-3.3-70B-Instruct",
    "dbrx-instruct": "databricks/dbrx-instruct",
    "Ministral-8B": "mistralai/Ministral-8B-Instruct-2410",
    "Confucius-14B": "netease-youdao/Confucius-o1-14B",
    "AceMath-7B": "nvidia/AceMath-7B-Instruct",
    "gemma-2-9B": "google/gemma-2-9b-it",
    "Llama-3.1": "neuralmagic/Llama-3.1-Nemotron-70B-Instruct-HF-FP8-dynamic",
    "Mistral-Large": "mistralai/Mistral-Large-Instruct-2411",
    "phi-4": "microsoft/phi-4",
    "watt-tool": "watt-ai/watt-tool-70B",
    "Bespoke-32B": "bespokelabs/Bespoke-Stratos-32B",
    "Sky-T1": "NovaSky-AI/Sky-T1-32B-Preview",
    "Falcon3-10B": "tiiuae/Falcon3-10B-Instruct",
    "c4ai-command": "CohereForAI/c4ai-command-r-plus-08-2024",
    "glm-4-9B": "THUDM/glm-4-9b-chat",
    "Qwen2.5-Coder": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "aya-expanse": "CohereForAI/aya-expanse-32b",
    "ReaderLM-v2": "jinaai/ReaderLM-v2",
    "MiniCPM3-4B": "openbmb/MiniCPM3-4B",
    "Qwen2.5-1.5B": "Qwen/Qwen2.5-1.5B-Instruct",
    "0x-lite": "ozone-ai/0x-lite",
    "Phi-3.5-mini": "microsoft/Phi-3.5-mini-instruct"
}

# Словарь описаний для моделей (упрощённые и переведённые)
model_descriptions = {
    "Qwen-32B": "Модель Qwen-32B с передовыми возможностями обработки языка для исследований.",
    "Llama-3.2": "Модель Llama-3.2 с поддержкой визуальных инструкций.",
    "DeepSeek-R1": "Высокопроизводительная модель для генерации текста, суммирования и выполнения инструкций.",
    "Llama-3.3": "Крупномасштабная модель, дообученная для точного выполнения инструкций.",
    "dbrx-instruct": "Модель для точных, задач-ориентированных ответов, идеально подходит для корпоративных приложений.",
    "Ministral-8B": "Мощная модель для создания качественного текста и выполнения инструкций.",
    "Confucius-14B": "Модель для качественной обработки текстов.",
    "AceMath-7B": "Специализированная модель для математического мышления и решения задач.",
    "gemma-2-9B": "Лёгкая, но мощная модель для эффективных и контекстно-зависимых ответов.",
    "Llama-3.1": "Модель для точного выполнения инструкций с динамической точностью.",
    "Mistral-Large": "Мощная языковая модель для глубокого понимания инструкций.",
    "phi-4": "Компактная и аналитичная модель с выдающимися способностями.",
    "watt-tool": "Модель для решения сложных задач.",
    "Bespoke-32B": "Специализированная модель для уникальных задач.",
    "Sky-T1": "Предварительная версия с передовыми возможностями обработки данных.",
    "Falcon3-10B": "Надёжная модель для выполнения инструкций.",
    "c4ai-command": "Модель для корпоративного стиля ответов.",
    "glm-4-9B": "Модель для интерактивного общения.",
    "Qwen2.5-Coder": "Модель для генерации кода и программирования.",
    "aya-expanse": "Модель для качественной обработки текстов.",
    "ReaderLM-v2": "Модель для глубокого анализа текстов.",
    "MiniCPM3-4B": "Модель для генерации компактных и точных текстов.",
    "Qwen2.5-1.5B": "Лёгкая версия для выполнения инструкций.",
    "0x-lite": "Модель для быстрого решения текстовых задач.",
    "Phi-3.5-mini": "Компактная и эффективная модель для выполнения инструкций."
}

# Список основных моделей для начальной клавиатуры
default_models = {
    "Qwen-32B": "Qwen/QwQ-32B",
    "DeepSeek-R1": "deepseek-ai/DeepSeek-R1",
    "Ministral-8B": "mistralai/Ministral-8B-Instruct-2410",
    "Mistral-Large": "mistralai/Mistral-Large-Instruct-2411",
    "Llama-3.3": "meta-llama/Llama-3.3-70B-Instruct"
}

# Функция для создания клавиатуры с полным списком моделей
def get_full_models_keyboard():
    buttons = [
        InlineKeyboardButton(text=short_name, callback_data=full_model)
        for short_name, full_model in models.items()
    ]
    keyboard_buttons = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# Функция для создания клавиатуры с 5 основными моделями и кнопкой "Больше моделей"
def get_default_models_keyboard():
    buttons = [
        InlineKeyboardButton(text=short_name, callback_data=full_model)
        for short_name, full_model in default_models.items()
    ]
    # Добавляем кнопку для показа полного списка моделей
    buttons.append(InlineKeyboardButton(text="Больше моделей", callback_data="more_models"))
    keyboard_buttons = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# Функция для создания стартовой клавиатуры с двумя кнопками
def get_start_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="О моделях", callback_data="about_models")],
        [InlineKeyboardButton(text="Выбрать модель", callback_data="select_model")]
    ])
    return keyboard

# Команда /start с красивым приветствием
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = get_start_keyboard()
    await message.answer(
        "Добро пожаловать в волшебный мир нейросети! Выберите интересующую Вас опцию ниже:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Команда /model для выбора модели
@dp.message(Command("models"))
async def cmd_model(message: Message):
    keyboard = get_default_models_keyboard()
    await message.answer("Пожалуйста, выберите модель, которая Вас интересует:", reply_markup=keyboard)

# Обработчик callback_query
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    data = callback.data
    if data == "about_models":
        text_lines = ["<b>Доступные модели:</b>"]
        for short_name, full_model in models.items():
            description = model_descriptions.get(short_name, "Описание отсутствует.")
            text_lines.append(f"• <b>{short_name}</b> ({full_model})\n  <i>{description}</i>")
        await callback.message.answer("\n".join(text_lines), parse_mode="HTML")
        await callback.answer()
    elif data == "select_model":
        # Показываем клавиатуру с 5 основными моделями
        keyboard = get_default_models_keyboard()
        await callback.message.answer("Выберите модель из списка:", reply_markup=keyboard)
        await callback.answer()
    elif data == "more_models":
        # Показываем полный список моделей
        keyboard = get_full_models_keyboard()
        await callback.message.answer("Пожалуйста, выберите модель из полного списка:", reply_markup=keyboard)
        await callback.answer()
    else:
        # Обработка выбора конкретной модели
        selected_model = data
        short_name = next((k for k, v in models.items() if v == selected_model), selected_model)
        user_models[callback.from_user.id] = selected_model
        # В поп-апе выводим красивое сообщение
        await callback.answer(f"Модель выбрана: {short_name}. Теперь напишите Ваш запрос.", show_alert=True)

# Обработчик сообщений пользователя
@dp.message()
async def filter_messages(message: Message):
    await message.answer("Ваш запрос обрабатывается, пожалуйста, подождите...")
    model_used = user_models.get(message.from_user.id, "mistralai/Ministral-8B-Instruct-2410")
    
    url = "https://api.intelligence.io.solutions/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": ("")
    }
    data = {
        "model": model_used,
        "messages": [
            {
                "role": "system",
                "content": "You are the best assistant and you answer perfectly in Russian."
            },
            {
                "role": "user",
                "content": message.text
            }
        ],
    }

    response = requests.post(url, headers=headers, json=data)
    try:
        data_response = response.json()
    except Exception as e:
        logging.error(f"Ошибка декодирования JSON: {e}")
        await message.answer("Извините, произошла ошибка при обработке запроса. Попробуйте повторить позже.")
        return

    bot_text = data_response['choices'][0]['message']['content']
    
    # Если в ответе присутствует тег </think>, берём только текст после последнего вхождения
    lower_text = bot_text.lower()
    if "</think>" in lower_text:
        idx = lower_text.rfind("</think>")
        bot_text = bot_text[idx + len("</think>"):]
    # Удаляем все оставшиеся теги <think> и </think> и лишние пробелы
    bot_text = re.sub(r'</?think>\n?', '', bot_text, flags=re.IGNORECASE).strip()
    
    # Разбиваем текст на части, если он превышает 4000 символов
    max_length = 4000
    if len(bot_text) > max_length:
        for i in range(0, len(bot_text), max_length):
            await message.answer(bot_text[i:i+max_length], parse_mode="Markdown")
    else:
        await message.answer(bot_text, parse_mode="Markdown")

async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
