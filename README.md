# 🧠 BonusLab Telegram Parser & Publisher Bot

## 📌 Описание
Этот проект представляет собой Telegram-систему для **автоматического парсинга постов из каналов**, их **модерации через админ-бота** и последующей **публикации в ваш канал**.

- 📡 Парсер на Telethon слушает выбранные каналы.
- 🤖 Бот (PyTelegramBotAPI) отправляет найденные посты владельцу (админу) для утверждения.
- ✅ После одобрения пост публикуется в целевой канал.
- 🧱 Хранение постов и медиа — в SQLite.
- 🔗 Полностью сохраняется форматирование (ссылки, жирный, курсив, code и т.д.).
- 🧽 “Чёрный список” удаляет только нежелательные фразы, не ломая весь текст.

---

## 🚀 Быстрый старт

### 1️⃣ Установка зависимостей

```bash
git clone https://github.com/yourname/bonuslab-bot.git
cd bonuslab-bot
pip install -r requirements.txt
```

> ⚠️ Python 3.9+ обязателен

### 2️⃣ Настройка конфигурации

Открой файл **`config.py`** и укажи:
- `api_id`, `api_hash` — с [my.telegram.org](https://my.telegram.org)
- `bot_token` — токен вашего бота от [@BotFather](https://t.me/BotFather)
- `owner_id` — ваш Telegram ID (можно узнать у @userinfobot)
- `target_channel` — канал, куда публикуются одобренные посты
- `TELEGRAM_PROXY_HOST`, `TELEGRAM_PROXY_PORT`, `TELEGRAM_PROXY_TYPE` — настройки прокси для подключения к Telegram API
- `TELEGRAM_PROXY_URL` — единый URL прокси для всех HTTP(S)-запросов процесса
- `DUPLICATE_WINDOW_HOURS` — окно антидубликатов (например, `3`, чтобы проверять только последние 3 часа)
- `IMAGE_DUPLICATE_THRESHOLD` — чувствительность сравнения фото (по умолчанию `12`)

Пример:

```python
bot_token = '1234567890:ABCDEF...'
owner_id = 123456789
target_channel = '@mychannel'
TELEGRAM_PROXY_HOST = '192.168.30.59'
TELEGRAM_PROXY_PORT = 3128
TELEGRAM_PROXY_TYPE = 'http'
TELEGRAM_PROXY_URL = 'http://192.168.30.59:3128'
DUPLICATE_WINDOW_HOURS = 3
IMAGE_DUPLICATE_THRESHOLD = 12
```

### 3️⃣ Настройка каналов для парсинга

В `config.py` отредактируйте:

```python
channels_to_parse = [
    '@big_bonus_wb',
    '@toporlive',
    '@ecotopor'
]
```

### 4️⃣ Запуск

```bash
python main.py
```

- При первом запуске создастся база `bonuslab.db`
- Все новые посты из указанных каналов будут приходить вам на модерацию

---

## 🧩 Структура проекта

```
bonuslab-bot/
│
├── bot.py           # Telegram-бот для модерации и публикации
├── parser.py        # Парсер сообщений с каналов (Telethon)
├── database.py      # Работа с SQLite
├── config.py        # Настройки
├── main.py          # Точка входа
│
├── media/           # Загруженные фото/видео
├── bonuslab.db      # Локальная база данных
└── README.md
```

---

## ⚙️ Управление постами

- **🟡 pending** — ожидает модерации
- **✅ published** — опубликован
- **🚫 rejected** — отклонён
- **❌ error** — ошибка при публикации

---

## 🛠️ Особенности

✅ Полная поддержка HTML-разметки  
✅ Работает с фото, видео и текстом  
✅ Кликабельные ссылки (`<a href="...">text</a>`) сохраняются  
✅ Удаление мусорных фраз по `blacklist_words`  
✅ Надёжный fallback при сбое `copy_message`  
✅ Разделение длинных сообщений без поломки HTML  

---

## 🧹 .gitignore

Проект уже содержит `.gitignore`, который исключает:
- `__pycache__`, `*.session`, `bonuslab.db`, `media/`
- виртуальные окружения, IDE-файлы, временные файлы

---

## 💬 Контакты / Поддержка

Автор: **BonusLab Automation**  
Если что-то не работает — просто скопируйте ошибку из терминала и отправьте в обсуждение 😉
