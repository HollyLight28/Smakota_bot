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
    bot.send_message(msg.chat.id, "📝 **Записник для Шефа**\n\nНапиши назву продукту і кількість (наприклад: *Борошно 10кг*), і я додам це в список закупів.", parse_mode='Markdown')


# Дозволяє кухні додавати будь-який текст як продукт в список закупів
@bot.message_handler(func=lambda msg: True)
def kitchen_custom_item(msg):
    """Кухня вводить свій продукт."""
    from bot.config import ADMIN_ID
    if msg.from_user.id == ADMIN_ID:
        return
    user_role = db.get_user_current_role(msg.from_user.id)
    if user_role != 'kitchen':
        return

    text = msg.text.strip()
    if not text or text in ['🛒 Список закупів', '📝 Записник для Шефа', '❓ Допомога']:
        return

    import re
    match = re.match(r'^(.+?)\s*(\d+[.,]?\d*)\s*(кг|л|шт|г|ящ)?$', text)
    if match:
        name = match.group(1).strip().capitalize()
        qty = match.group(2).replace(',', '.')
        qty_float = float(qty)
        unit = match.group(3) or 'шт'
        qty_display = f"{int(qty_float)} {unit}" if qty_float == int(qty_float) else f"{qty_float} {unit}"
    else:
        name = text.capitalize()
        qty_display = "1 шт"

    conn = db.get_db_connection()
    conn.execute(
        'INSERT INTO active_shopping_list (product_id, quantity, added_by, date) VALUES (?, ?, ?, date(\'now\'))',
        (0, qty_display, msg.from_user.id)
    )
    conn.commit()
    bot.reply_to(msg, f"✅ **{name}** — {qty_display} додано в список закупів!", parse_mode='Markdown')
