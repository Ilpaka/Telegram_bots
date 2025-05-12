import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton


API_TOKEN = ''

CHANNELS = [-1002595519203,
    -1002001709436,
    -1001847313970,
    -1001273005885,
    -1002124413663,
    -1001609826201,
    -1002125589434,
    -1001530559813,
    -1001546562004,
    -1001506797368,
    -1001948531346,
    -1002057923996,
    -1002086483348,
    -1001653943154,
    -1001583561790,
    -1001520517888,
    -1002106730427,
    -1001517208942,
    -1001489109498,
    -1001869478175,
    -1001559459860,
    -1001800027090,
    -1001643201215,
    -1001569998592,
    -1001658118310,
    -1001496785252,
    -1001642707262,
    -1001765905352,
    -1001969280214,
    -1001952608345,
    -1001779719868,
    -1001657598180,
    -1002017179295,
    -1001516863705,
    -1001801069664,
    -1001617591904,
    -1002145062891,
    -1001507869010
]  

ADMINS = [772482922,454944349 ]

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

pending_confirmations = {}

@dp.message(Command(commands=['start']))
async def start_cmd(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Доступ запрещен!")
        return
    await message.answer("Привет! Я бот для пересылки сообщений в каналы")

@dp.message(Command(commands=['add_channel']))
async def add_channel(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Доступ запрещен!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Пожалуйста, укажите идентификатор канала. Пример: /add_channel -1002412419001")
        return

    new_channel = parts[1].strip()
    CHANNELS.append(new_channel)
    await message.reply(f"Канал {new_channel} успешно добавлен!")

@dp.message(lambda message: not (message.text and message.text.startswith('/')))
async def process_message(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Доступ запрещен!")
        return

    key = f"{message.chat.id}_{message.message_id}"
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить", callback_data=f"confirm_{key}")],
        [InlineKeyboardButton(text="Отменить", callback_data=f"cancel_{key}")]
    ])
    await message.answer("Подтвердите отправку сообщения", reply_markup=markup)
    pending_confirmations[key] = message

@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_"))
async def process_confirm(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("Доступ запрещен!", show_alert=True)
        return

    key = callback.data.split("confirm_")[1]
    if key not in pending_confirmations:
        await callback.answer("Нет данных для подтверждения.")
        return

    original_message = pending_confirmations[key]
    success_channels = []
    for channel in CHANNELS:
        try:
            await original_message.copy_to(chat_id=channel)
            logging.info(f"Сообщение успешно отправлено в канал {channel}")
            success_channels.append(channel)
        except Exception as e:
            logging.error(f"Ошибка при отправке в {channel}: {e}")

    if success_channels:
        channels_str = ", ".join(map(str, success_channels))
        await callback.message.edit_text(f"Сообщение успешно отправлено на каналы: {channels_str}")
    else:
        await callback.message.edit_text("Не удалось отправить сообщение ни в один канал.")

    del pending_confirmations[key]
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("cancel_"))
async def process_cancel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("Доступ запрещен!", show_alert=True)
        return

    key = callback.data.split("cancel_")[1]
    if key in pending_confirmations:
        del pending_confirmations[key]
        await callback.message.edit_text("Отправка сообщения отменена.")
    await callback.answer("Отменено.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
