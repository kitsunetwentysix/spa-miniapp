# Запуск бота на VPS

Инструкция для сервера с Ubuntu 22.04 / 24.04 / 26.04. Команды после `ssh` выполняются **на сервере**.

## 0. Подготовка на ПК

1. Загрузи на GitHub свежие файлы: `bot.py`, `requirements.txt`, `bot.service`, `DEPLOY.md`.
   **Не загружай** `.env`, `.venv`, `avatar.png`.
2. Останови бота на ПК (`Ctrl + C` в терминале). Если бот запущен в двух местах, Telegram выдаст ошибку `Conflict`.
3. Держи под рукой данные из своего `.env`: `BOT_TOKEN`, `WEBAPP_URL`, `OWNER_ID`.

## 1. Подключиться к серверу

В терминале VS Code (подставь IP из письма хостинга):

```
ssh root@IP_СЕРВЕРА
```

- На вопрос `Are you sure you want to continue connecting?` напиши `yes`.
- Пароль при вводе не отображается, даже звёздочками. Это нормально: вставь его (правая кнопка мыши) и нажми Enter.
- Успех: строка стала похожа на `root@имя-сервера:~#`.

## 2. Установить Python и git

```bash
apt update && apt install -y python3-venv python3-pip git
```

## 3. Скачать проект

```bash
cd /root
git clone https://github.com/kitsunetwentysix/spa-miniapp.git
cd spa-miniapp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. Создать `.env` на сервере

```bash
nano .env
```

Откроется текстовый редактор. Вставь три строки со своими значениями:

```
BOT_TOKEN=токен
WEBAPP_URL=https://kitsunetwentysix.github.io/spa-miniapp/
OWNER_ID=181306151
```

Сохранить: `Ctrl + O`, затем `Enter`. Выйти: `Ctrl + X`.

## 5. Проверочный запуск

```bash
.venv/bin/python bot.py
```

Должно появиться `Run polling for bot @...`. Напиши боту `/start` в Telegram, и он должен ответить.
Останови: `Ctrl + C`.

## 6. Включить автозапуск

```bash
cp bot.service /etc/systemd/system/bot.service
systemctl daemon-reload
systemctl enable --now bot
systemctl status bot
```

В выводе должно быть `active (running)` зелёным. Выйти из просмотра: `q`.

Готово. Теперь можно закрыть терминал (`exit`) и выключить ПК: бот работает на сервере, сам перезапускается после падений и после перезагрузки сервера.

## Полезные команды

| Задача | Команда |
|---|---|
| Состояние бота | `systemctl status bot` |
| Логи в реальном времени | `journalctl -u bot -f` (выход: `Ctrl + C`) |
| Перезапустить | `systemctl restart bot` |
| Остановить | `systemctl stop bot` |
| Поменять настройки | `nano /root/spa-miniapp/.env`, затем `systemctl restart bot` |

## Как обновить бота после изменений

1. Загрузи новый `bot.py` на GitHub.
2. На сервере:

```bash
cd /root/spa-miniapp
git pull
systemctl restart bot
```

`index.html` на сервер копировать не нужно: страница живёт на GitHub Pages и обновляется сама.

## Если что-то не так

| Симптом | Что делать |
|---|---|
| `Permission denied` при `ssh` | Неверный пароль. Скопируй его из письма хостинга ещё раз |
| `git clone` просит логин | Репозиторий приватный. Сделай его публичным (Settings → General → Danger Zone → Change visibility) |
| `status` показывает `failed` | Смотри причину: `journalctl -u bot -n 30` |
| `Заполни BOT_TOKEN...` в логах | `.env` не создан или лежит не в `/root/spa-miniapp` |
| `Conflict: terminated by other getUpdates` | Бот ещё запущен на ПК. Останови его там |
