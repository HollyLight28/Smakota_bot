#!/usr/bin/env python3
"""
Smakota Bot — Точка входу.
Запуск: python3 run.py
"""
import time
import threading
from datetime import datetime

import database as db
from bot import bot as smakota_bot
from bot.utils import logger, escape_md
from bot.config import ADMIN_ID

# Імпорт хендлерів реєструє їх у потрібному порядку
import bot.handlers  # noqa: F401


def run_reminder_checker():
    """Фонова перевірка відкладених замовлень (кожні 60 сек)."""
    logger.info("⏰ Reminder thread started.")
    while True:
        try:
            scheduled_orders = db.get_orders_to_remind()
            now = datetime.now()

            for order in scheduled_orders:
                try:
                    sched_time_str = order['scheduled_time']
                    sched_time = datetime.strptime(sched_time_str, "%H:%M").replace(
                        year=now.year, month=now.month, day=now.day
                    )

                    diff_minutes = (sched_time - now).total_seconds() / 60

                    if diff_minutes <= 60:
                        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("✅ ПРИЙНЯТИ ЗАРАЗ", callback_data=f"admin_accept_now_{order['id']}"))
                        markup.add(InlineKeyboardButton("❌ СКАСУВАТИ", callback_data=f"admin_cancel_{order['id']}"))

                        msg = (
                            f"🔔 *НАГАДУВАННЯ: ЧАС ГОТУВАТИ!*\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📦 *Замовлення #{order['id']}*\n"
                            f"⏰ Час видачі: *{sched_time_str}*\n\n"
                            f"👤 Клієнт: {escape_md(order['delivery_name'])}\n"
                            f"📞 Тел: {order['delivery_phone']}\n"
                            f"📍 Адреса: {escape_md(order['delivery_address'])}\n"
                            f"💰 Сума: {order['total_amount']} грн"
                        )
                        smakota_bot.send_message(ADMIN_ID, msg, reply_markup=markup, parse_mode='Markdown')
                        db.mark_as_reminded(order['id'])
                        logger.info(f"⏰ Reminder sent for order #{order['id']} (scheduled: {sched_time_str})")
                except Exception as e:
                    logger.error(f"Reminder error for order #{order['id']}: {e}")

        except Exception as e:
            logger.error(f"Reminder thread error: {e}")

        time.sleep(60)


if __name__ == '__main__':
    db.setup_database()
    logger.info("🚀 Smakota Bot запущено (модульна версія)")

    # Запускаємо Будильник у фоні
    reminder_thread = threading.Thread(target=run_reminder_checker, daemon=True)
    reminder_thread.start()

    while True:
        try:
            smakota_bot.polling(none_stop=True, timeout=90, long_polling_timeout=10)
        except Exception as e:
            logger.error(f"🛑 Smakota Bot Polling Error: {e}")
            logger.info("🔄 Restarting polling in 5 seconds...")
            time.sleep(5)

