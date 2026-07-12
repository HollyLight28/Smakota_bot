"""
Хендлери кухні: вибір продуктів по цехах, список закупів.
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot
import database as db
from bot.utils import logger


@bot.message_handler(func=lambda msg: msg.text == '🛒 Список закупів')
def show_departments(msg):
    """Показує цехи для вибору продуктів."""
    depts = db.get_departments()
    markup = InlineKeyboardMarkup(row_width=1)
    for d in depts:
        markup.add(InlineKeyboardButton(d['name'], callback_data=f"shop_dept_{d['id']}"))
    markup.add(InlineKeyboardButton("✅ Готово (до Шефа)", callback_data="shop_done"))
    bot.send_message(msg.chat.id, "📋 **Список закупів**\nОбери цех:", reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(func=lambda msg: msg.text == '📝 Записник для Шефа')
def handle_notepad(msg):
    """Місце для майбутнього записника."""
    bot.send_message(msg.chat.id, "📝 Записник — функція в розробці.")
