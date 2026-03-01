import re
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot
import database as db
import keyboards
from bot.utils import logger

def escape_markdown(text):
    """Екранує спецсимволи MarkdownV1."""
    if not text: return ""
    return re.sub(r'[_*`\[\]]', r'\\\g<0>', str(text))

@bot.message_handler(func=lambda message: message.text == '🛵 Мої доставки (в роботі)')
def show_courier_orders(message):
    """Показує кур'єру його активні замовлення."""
    user_id = message.from_user.id
    
    # Перевіряємо статус зміни
    conn = db.get_db_connection()
    courier = conn.execute('SELECT * FROM couriers WHERE chat_id = ?', (user_id,)).fetchone()
    
    if not courier:
        bot.reply_to(message, "❌ Ви не зареєстровані як кур'єр.")
        return

    if courier['shift_status'] == 'off':
        bot.reply_to(message, "🔌 Ви поза зміною. Натисніть кнопку виходу на зміну!", reply_markup=keyboards.get_courier_keyboard(user_id))
        return

    # Замовлення, які прийняті або вже призначені цьому кур'єру
    orders = conn.execute('''
        SELECT * FROM orders 
        WHERE courier_id = ? AND status IN ('accepted', 'assigned', 'delivery')
        ORDER BY created_at DESC
    ''', (user_id,)).fetchall()

    if not orders:
        bot.reply_to(message, "📭 У вас немає активних доставок.\n\n_Шеф ще не призначив на вас замовлення._", parse_mode='Markdown')
        return

    for order in orders:
        text = (
            f"📦 **ЗАМОВЛЕННЯ #{order['id']}**\n\n"
            f"👤 {order['delivery_name']}\n"
            f"📍 {order['delivery_address']}\n"
            f"💰 Сума: **{order['total_amount']} грн**\n"
            f"💳 Оплата: {order['payment_method']}\n"
        )
        if order['delivery_comment']:
            text += f"📝 Коментар: _{order['delivery_comment']}_"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ ДОСТАВЛЕНО", callback_data=f"courier_delivered_{order['id']}"))
        markup.add(InlineKeyboardButton("📞 Зателефонувати", url=f"tel:{order['delivery_phone']}"))
        
        bot.send_message(user_id, text, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📊 Мій звіт за сьогодні')
def handle_my_report(message):
    """Звіт кур'єра за сьогодні."""
    user_id = message.from_user.id
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_db_connection()
    
    done = conn.execute(
        'SELECT COUNT(*), SUM(total_amount) FROM orders WHERE courier_id = ? AND status = "completed" AND date(created_at) = ?',
        (user_id, today)
    ).fetchone()
    
    active = conn.execute(
        'SELECT COUNT(*) FROM orders WHERE courier_id = ? AND status IN ("accepted", "assigned", "delivery")',
        (user_id,)
    ).fetchone()

    done_count = done[0] if done[0] else 0
    done_total = done[1] if done[1] else 0
    active_count = active[0] if active[0] else 0

    text = (
        f"📊 **Твій звіт за сьогодні:**\n\n"
        f"✅ Доставлено: **{done_count}**\n"
        f"💰 Каса: **{done_total} грн**\n\n"
        f"⏳ У роботі зараз: **{active_count}**"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text in ['🟢 Вийти на зміну', '🔴 Завершити зміну'])
def toggle_shift(message):
    """Вмикає/вимикає зміну."""
    user_id = message.from_user.id
    new_status = 'on' if '🟢' in message.text else 'off'
    
    conn = db.get_db_connection()
    conn.execute('UPDATE couriers SET shift_status = ? WHERE chat_id = ?', (new_status, user_id))
    conn.commit()
    
    text = "🚀 **Ви на зміні!** Чекайте на замовлення." if new_status == 'on' else "🔌 **Зміну завершено.**"
    bot.reply_to(message, text, reply_markup=keyboards.get_courier_keyboard(user_id), parse_mode='Markdown')
