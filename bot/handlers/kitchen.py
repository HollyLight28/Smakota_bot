"""
Хендлери кухні: шоппінг-лист, записник для шефа.
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from bot import bot
import database as db


@bot.message_handler(func=lambda message: message.text == '📝 Записник для Шефа')
def kitchen_add_item(message):
    """Кухар додає товар у шоппінг-лист."""
    user_id = message.from_user.id
    db.set_user_state(user_id, 'kitchen_adding_item')

    templates = db.get_shopping_templates()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for t in templates:
        markup.add(KeyboardButton(f"➕ {t['item_name']}"))
    markup.add(KeyboardButton("❌ Скасувати"))

    bot.reply_to(
        message,
        "📝 **Що саме закінчилось?**\n"
        "Оберіть зі списку або напишіть свою назву та кількість (наприклад: 'Борошно 10кг'):",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == '🛒 Список закупів')
def show_shopping_list(message):
    """Показує поточний шоппінг-лист для шефа."""
    items = db.get_shopping_list()
    if not items:
        bot.reply_to(message, "✅ **Список порожній.** Все є в наявності!", parse_mode='Markdown')
        return

    msg = "🛒 **Список закупів для Шефа:**\n\n"
    markup = InlineKeyboardMarkup()
    for item in items:
        msg += f"• {item['item_name']} — {item['quantity']}\n"
        markup.add(InlineKeyboardButton(
            f"✅ Куплено: {item['item_name']}",
            callback_data=f"buy_item_{item['id']}"
        ))

    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')
