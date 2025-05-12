import logging
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
from aiogram.filters.state import StateFilter
from aiogram.types import CallbackQuery

logging.basicConfig(level=logging.INFO)

API_TOKEN = ""
bot = Bot(token = API_TOKEN, dafault = DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage = MemoryStorage())
router = Router()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет!")

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())