#!/usr/bin/env python3
"""
Smakota Bot — Точка входу.
Запуск: python3 run.py
"""
import database as db
from bot import bot as smakota_bot
from bot.utils import logger

# Імпорт хендлерів реєструє їх у потрібному порядку
import bot.handlers  # noqa: F401

if __name__ == '__main__':
    db.setup_database()
    logger.info("🚀 Smakota Bot запущено (модульна версія)")
    smakota_bot.polling(none_stop=True)
