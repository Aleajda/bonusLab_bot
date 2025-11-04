# main.py
import threading
import asyncio
from database import init_db
from bot import run_bot
from parser import run_parser

if __name__ == "__main__":
    init_db()
    print("📁 База данных инициализирована")

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    asyncio.run(run_parser())
