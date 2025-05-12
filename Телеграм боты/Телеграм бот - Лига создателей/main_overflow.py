import logging
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from oauth2client.service_account import ServiceAccountCredentials
from aiogram.types import BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
from aiogram.filters.state import StateFilter
from aiogram.types import CallbackQuery



logging.basicConfig(level=logging.INFO)

API_TOKEN = "" #лига создателей


bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()


@router.message(Command("start"))
async def start(message: types.Message):
    welcome_text = ("""
😌Упс! Регистрация уже  закрыта  
🫶🏼НО скоро стартует новая регистрация на мартовское мероприятие  
Оставайся с нами в @LigaSozdateley  
За подробностями пиши @sash_alexandrovn"""
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='"Лига Создателей"', url = "https://t.me/LigaSozdateley")],
            [InlineKeyboardButton(text="Написать @sash_alexandrovn", url = "https://t.me/sash_alexandrovn")]
        ])
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

# ---------------- Запуск бота ----------------

async def main():
    dp.include_router(router) 
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())