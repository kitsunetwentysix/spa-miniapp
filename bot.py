"""Бегемотик Ботик: открывает Mini App по кнопке Open и пересылает заказы владельцу."""

import asyncio
import json
import logging
import os
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import MenuButtonWebApp, Message, ReplyKeyboardRemove, User, WebAppInfo
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)  # твой chat id: напиши боту /id
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE") or "Europe/Moscow")
API_PORT = int(os.getenv("API_PORT") or 8080)

if not BOT_TOKEN or not WEBAPP_URL:
    raise SystemExit("Заполни BOT_TOKEN и WEBAPP_URL в файле .env")

# Заказы принимаем только со страницы на GitHub Pages
_url = urlsplit(WEBAPP_URL)
ALLOWED_ORIGIN = f"{_url.scheme}://{_url.netloc}"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ---------- Telegram ----------

@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Приглашаю тебя на домашний spa-вечер 🕯\n"
        "Нажми кнопку Open внизу и выбери всё, чего хочется.",
        reply_markup=ReplyKeyboardRemove(),  # убираем старую кнопку под полем ввода
    )


@dp.message(Command("id"))
async def my_id(message: Message) -> None:
    await message.answer(f"Твой chat id: {message.chat.id}\nВставь его в .env как OWNER_ID")


async def deliver_order(user: User | None, order: dict) -> None:
    """Подтверждает заказ гостье и присылает его владельцу."""
    if user:
        await bot.send_message(user.id, "Записала тебя на spa-вечер 💌 Скоро всё будет готово!")
    if not OWNER_ID:
        return
    name = user.full_name if user else "Она"
    username = f" (@{user.username})" if user and user.username else ""
    received = datetime.now(TIMEZONE).strftime("%d.%m %H:%M")
    await bot.send_message(
        OWNER_ID,
        f"🕯 Новый заказ на spa-вечер\n"
        f"От: {name}{username}\n"
        f"Получен: {received}\n"
        f"Начало: {order.get('start', '—')}\n\n"
        f"{order.get('text', '')}",
    )


# Запасной путь: Mini App открыт старой кнопкой под полем ввода
@dp.message(F.web_app_data)
async def got_order_from_keyboard(message: Message) -> None:
    order = json.loads(message.web_app_data.data)
    logging.info("Заказ через sendData: %s", order)
    await deliver_order(message.from_user, order)


# ---------- Веб-API для кнопки Open ----------

def cors(response: web.StreamResponse) -> web.StreamResponse:
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


async def order_options(request: web.Request) -> web.Response:
    return cors(web.Response())


async def order_post(request: web.Request) -> web.Response:
    try:
        body = json.loads(await request.text())
        # Проверяем подпись Telegram: без неё любой мог бы прислать фальшивый заказ
        init = safe_parse_webapp_init_data(BOT_TOKEN, body["initData"])
        order = body["order"]
        if not isinstance(order, dict):
            raise ValueError("order должен быть объектом")
    except (ValueError, KeyError, TypeError) as e:
        logging.warning("Отклонён запрос: %s", e)
        return cors(web.json_response({"ok": False}, status=400))

    logging.info("Заказ через Open от %s: %s", init.user.id if init.user else "?", order)
    await deliver_order(init.user, order)
    return cors(web.json_response({"ok": True}))


async def start_api() -> web.AppRunner:
    app = web.Application(client_max_size=64 * 1024)
    app.router.add_post("/order", order_post)
    app.router.add_options("/order", order_options)
    runner = web.AppRunner(app)
    await runner.setup()
    # Слушаем только локально: снаружи запросы приходят через Caddy с HTTPS
    await web.TCPSite(runner, "127.0.0.1", API_PORT).start()
    logging.info("API заказов слушает 127.0.0.1:%s", API_PORT)
    return runner


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not OWNER_ID:
        logging.warning("OWNER_ID не задан: заказы не будут пересылаться. Напиши боту /id")

    # Кнопка Open слева от поля ввода у всех пользователей бота
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=WEBAPP_URL)))

    runner = await start_api()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
