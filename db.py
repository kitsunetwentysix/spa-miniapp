"""Хранилище заказов в SQLite: один файл orders.db рядом с ботом."""

import csv
import io
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("orders.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,     -- когда заказ получен, ISO с часовым поясом
    user_id     INTEGER,
    name        TEXT,
    username    TEXT,
    event_date  TEXT,              -- дата spa-вечера, ГГГГ-ММ-ДД
    start_time  TEXT,              -- ЧЧ:ММ
    procedures  TEXT,              -- JSON-список id процедур
    text        TEXT NOT NULL,     -- программа целиком, как её видит владелец
    source      TEXT               -- open или keyboard
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(SCHEMA)


def add_order(*, created_at: str, user_id: int | None, name: str, username: str | None,
              order: dict, source: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO orders (created_at, user_id, name, username, event_date, start_time,"
            " procedures, text, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                created_at, user_id, name, username,
                order.get("date"), order.get("start"),
                json.dumps(order.get("procedures", []), ensure_ascii=False),
                order.get("text", ""), source,
            ),
        )
        return cur.lastrowid


def last_orders(limit: int = 10) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get_order(order_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def count_orders() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def export_csv() -> bytes:
    """Все заказы в CSV. BOM и «;» нужны, чтобы Excel сразу открыл кириллицу по колонкам."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["id", "created_at", "user_id", "name", "username", "event_date",
                     "start_time", "procedures", "text", "source"])
    for r in rows:
        writer.writerow([r[k] for k in r.keys()])
    return ("﻿" + buf.getvalue()).encode("utf-8")
