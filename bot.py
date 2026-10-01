"""Бегемотик Ботик: открывает Mini App по кнопке Open и пересылает заказы владельцу."""

import asyncio
import json
import logging
import os
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BotCommand, BotCommandScopeChat, BufferedInputFile, MenuButtonWebApp,
                           Message, ReplyKeyboardRemove, User, WebAppInfo)
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web
from dotenv import load_dotenv

import db

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
        "Привет! Меня зовут Бегемотик Ботик и я твой персональный ассистент! "
        "Нажми кнопку Open и выбери всё, чего тебе хочется ❤️",
        reply_markup=ReplyKeyboardRemove(),  # убираем старую кнопку под полем ввода
    )


@dp.message(Command("id"))
async def my_id(message: Message) -> None:
    await message.answer(f"Твой chat id: {message.chat.id}\nВставь его в .env как OWNER_ID")


async def deliver_order(user: User | None, order: dict, source: str) -> None:
    """Сохраняет заказ в базу, подтверждает его гостье и присылает владельцу."""
    # У WebAppUser (кнопка Open) нет full_name, поэтому собираем имя сами
    name = " ".join(filter(None, [user.first_name, user.last_name])) if user else ""
    name = name or "Она"
    now = datetime.now(TIMEZONE)
    # Сначала база: так заказ не потеряется, даже если Telegram не ответит
    order_id = db.add_order(
        created_at=now.isoformat(timespec="seconds"),
        user_id=user.id if user else None,
        name=name,
        username=user.username if user else None,
        order=order,
        source=source,
    )
    logging.info("Заказ №%s сохранён", order_id)

    if user:
        await bot.send_message(user.id, "Записала тебя на spa-вечер 💌 Скоро всё будет готово!")
    if not OWNER_ID:
        return
    username = f" (@{user.username})" if user and user.username else ""
    await bot.send_message(
        OWNER_ID,
        f"🕯 Новый заказ №{order_id} на spa-вечер\n"
        f"От: {name}{username}\n"
        f"Получен: {now:%d.%m %H:%M}\n"
        f"Начало: {order.get('start', '—')}\n\n"
        f"{order.get('text', '')}",
    )


# ---------- Команды владельца: база заказов ----------

def is_owner(message: Message) -> bool:
    return bool(OWNER_ID) and message.chat.id == OWNER_ID


def short_line(row) -> str:
    """Одна строка списка: №, дата вечера, время, имя, сколько процедур."""
    date = row["event_date"] or ""
    date = f"{date[8:10]}.{date[5:7]}" if len(date) == 10 else "—"
    count = len(json.loads(row["procedures"] or "[]"))
    return f"№{row['id']} · {date} в {row['start_time'] or '—'} · {row['name']} · процедур: {count}"


@dp.message(Command("orders"), is_owner)
async def cmd_orders(message: Message) -> None:
    rows = db.last_orders(10)
    if not rows:
        await message.answer("Заказов пока нет.")
        return
    total = db.count_orders()
    lines = [f"📋 Последние заказы (всего {total}):", ""]
    lines += [short_line(r) for r in rows]
    lines += ["", "Полный заказ: /order номер, например /order " + str(rows[0]["id"]),
              "Все заказы файлом: /export"]
    await message.answer("\n".join(lines))


@dp.message(Command("order"), is_owner)
async def cmd_order(message: Message, command: CommandObject) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Укажи номер заказа, например: /order 1")
        return
    row = db.get_order(int(command.args))
    if not row:
        await message.answer(f"Заказа №{command.args.strip()} нет.")
        return
    created = datetime.fromisoformat(row["created_at"]).strftime("%d.%m.%Y %H:%M")
    username = f" (@{row['username']})" if row["username"] else ""
    await message.answer(
        f"🕯 Заказ №{row['id']}\n"
        f"От: {row['name']}{username}\n"
        f"Получен: {created}\n\n"
        f"{row['text']}"
    )


@dp.message(Command("export"), is_owner)
async def cmd_export(message: Message) -> None:
    if not db.count_orders():
        await message.answer("Заказов пока нет.")
        return
    stamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    await message.answer_document(
        BufferedInputFile(db.export_csv(), filename=f"spa-orders-{stamp}.csv"),
        caption="Все заказы. Открывается в Excel или Google Таблицах.",
    )


# Запасной путь: Mini App открыт старой кнопкой под полем ввода
@dp.message(F.web_app_data)
async def got_order_from_keyboard(message: Message) -> None:
    order = json.loads(message.web_app_data.data)
    logging.info("Заказ через sendData: %s", order)
    await deliver_order(message.from_user, order, source="keyboard")


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
    await deliver_order(init.user, order, source="open")
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
    db.init_db()
    if not OWNER_ID:
        logging.warning("OWNER_ID не задан: заказы не будут пересылаться. Напиши боту /id")

    # Кнопка Open слева от поля ввода у всех пользователей бота
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=WEBAPP_URL)))

    # Подсказки команд видит только владелец
    if OWNER_ID:
        await bot.set_my_commands(
            [
                BotCommand(command="orders", description="Последние заказы"),
                BotCommand(command="order", description="Заказ по номеру: /order 1"),
                BotCommand(command="export", description="Все заказы файлом CSV"),
            ],
            scope=BotCommandScopeChat(chat_id=OWNER_ID),
        )

    runner = await start_api()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
