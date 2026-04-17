# main.py
import os
import threading
import asyncio
from config import TELEGRAM_PROXY_URL

# Принудительно направляем все HTTP(S)-запросы процесса через прокси.
os.environ["HTTP_PROXY"] = TELEGRAM_PROXY_URL
os.environ["HTTPS_PROXY"] = TELEGRAM_PROXY_URL
os.environ["ALL_PROXY"] = TELEGRAM_PROXY_URL

from database import init_db
from bot import run_bot
from parser import run_parser

if __name__ == "__main__":
    init_db()
    print("📁 База данных инициализирована")

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    asyncio.run(run_parser())
