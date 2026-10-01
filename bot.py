"""Бот для spa-вечера: открывает Mini App и пересылает выбор девушки владельцу."""

import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)  # твой chat id: напиши боту /id

if not BOT_TOKEN or not WEBAPP_URL:
    raise SystemExit("Заполни BOT_TOKEN и WEBAPP_URL в файле .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# sendData работает только из Mini App, открытого кнопкой reply-клавиатуры,
# поэтому кнопка живёт здесь, а не в Menu Button
spa_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💆‍♀️ Выбрать процедуры", web_app=WebAppInfo(url=WEBAPP_URL))]],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Сегодня у тебя домашний spa-вечер 🕯\n"
        "Нажми кнопку внизу и выбери всё, чего хочется.",
        reply_markup=spa_keyboard,
    )


@dp.message(Command("id"))
async def my_id(message: Message) -> None:
    await message.answer(f"Твой chat id: {message.chat.id}\nВставь его в .env как OWNER_ID")


@dp.message(F.web_app_data)
async def got_order(message: Message) -> None:
    order = json.loads(message.web_app_data.data)
    logging.info("Новый выбор: %s", order)

    await message.answer("Записала тебя на spa-вечер 💌 Скоро всё будет готово!", reply_markup=spa_keyboard)

    if OWNER_ID and message.chat.id != OWNER_ID:
        name = message.from_user.full_name if message.from_user else "Она"
        await bot.send_message(OWNER_ID, f"{name} выбрала:\n\n{order['text']}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not OWNER_ID:
        logging.warning("OWNER_ID не задан: выбор не будет пересылаться. Напиши боту /id")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
