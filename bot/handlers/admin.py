"""
Хендлери для ролі Адміна.
Керування замовленнями, кур'єрами, розсилка, звіти.
"""
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import escape_md, format_cart_message
import database as db
import keyboards


@bot.message_handler(commands=['add_courier'])
def add_courier_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.reply_to(message, "Введіть Ім'я кур'єра та його Telegram ID через пробіл (наприклад: Іван 12345678):")
    bot.register_next_step_handler(msg, process_add_courier)

def process_add_courier(message):
    try:
        parts = message.text.split()
        name = parts[0]
        chat_id = int(parts[1])
        db.add_courier(name, chat_id)
        bot.reply_to(message, f"✅ Кур'єр {name} доданий!")
    except Exception:
        bot.reply_to(message, "❌ Помилка. Формат: Ім'я ID")


@bot.message_handler(func=lambda message: message.text == '📋 Нові замовлення')
def show_new_orders(message):
    if message.from_user.id != ADMIN_ID: return
    orders = db.get_active_orders()
    new_orders = [o for o in orders if o['status'] == 'new']
    
    if not new_orders:
        bot.reply_to(message, "🙌 Нових замовлень немає.")
        return

    for o in new_orders:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Прийняти", callback_data=f"admin_accept_{o['id']}"))
        markup.add(InlineKeyboardButton("❌ Скасувати", callback_data=f"admin_cancel_{o['id']}"))
        
        name = escape_md(o['delivery_name'])
        addr = escape_md(o['delivery_address'])
        
        bot.send_message(
            message.chat.id,
            f"📦 *Замовлення #{o['id']}*\n👤 {name}\n📍 {addr}\n💰 {o['total_amount']} грн",
            reply_markup=markup,
            parse_mode='Markdown'
        )


@bot.message_handler(func=lambda message: message.text == '🛒 Поточний кошик')
def show_admin_cart(message):
    """Показує шефу його поточний кошик для ручного замовлення."""
    if message.from_user.id != ADMIN_ID: return
    msg_text, total, markup = format_cart_message(message.from_user.id)
    bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Виручка за сьогодні')
def show_revenue(message):
    """Показує загальну виручку за сьогодні з розділенням по оплаті."""
    if message.from_user.id != ADMIN_ID: return
    
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_db_connection()
    
    cursor = conn.execute('''
        SELECT total_amount, payment_method 
        FROM orders 
        WHERE status = 'completed' AND date(created_at) = ?
    ''', (today,))
    orders = cursor.fetchall()
    
    total_cash = sum(o['total_amount'] for o in orders if "Готівка" in (o['payment_method'] or ''))
    total_card = sum(o['total_amount'] for o in orders if "карту" in (o['payment_method'] or ''))
    total_sum = total_cash + total_card
    count = len(orders)

    msg = (
        f"💰 *Виручка за сьогодні:*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧾 Кількість замовлень: {count}\n\n"
        f"💵 Готівка: {total_cash} грн\n"
        f"💳 На карту: {total_card} грн\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚀 *ЗАГАЛОМ: {total_sum} грн*"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Моніторинг')
def show_monitoring(message):
    if message.from_user.id != ADMIN_ID: return
    couriers = db.get_couriers()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if not couriers:
        bot.reply_to(message, "Кур'єрів ще не додано. /add\\_courier")
        return
    
    msg = "📊 *Моніторинг кур'єрів (сьогодні):*\n\n"
    markup = InlineKeyboardMarkup()
    
    conn = db.get_db_connection()
    for c in couriers:
        active = conn.execute(
            'SELECT COUNT(*) FROM orders WHERE courier_id = ? AND status = "delivery"',
            (c['chat_id'],)
        ).fetchone()[0]
        completed = conn.execute(
            'SELECT COUNT(*) FROM orders WHERE courier_id = ? AND status = "completed" AND date(created_at) = ?',
            (c['chat_id'], today)
        ).fetchone()[0]
        
        status_emoji = "✅" if c['shift_status'] == 'on' else "🔌"
        safe_name = escape_md(c['name'])
        msg += f"{status_emoji} *{safe_name}* | В дорозі: {active} | Завершено: {completed}\n"
        markup.add(InlineKeyboardButton(f"🔎 Деталі: {c['name']}", callback_data=f"mon_courier_{c['chat_id']}"))

    try:
        bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')
    except Exception:
        # Fallback без Markdown якщо все одно щось не так
        bot.send_message(message.chat.id, msg, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '📣 Розсилка')
def start_mailing(message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Створити нову", callback_data="mail_new"))
    markup.add(InlineKeyboardButton("📋 Мої шаблони", callback_data="mail_list"))
    bot.send_message(message.chat.id, "📣 *Керування розсилками*", reply_markup=markup, parse_mode='Markdown')
