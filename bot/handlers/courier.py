"""
Хендлери для ролі Кур'єра.
Відображення замовлень, маршрути, звіти.
"""
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
import database as db
import keyboards
from bot.utils import logger, get_maps_url, escape_md


@bot.message_handler(func=lambda message: message.text == '🛵 Мої доставки (в роботі)')
def show_courier_orders_cmd(message):
    """Показує активні замовлення кур'єра."""
    user_id = message.from_user.id
    show_courier_orders(user_id)


def show_courier_orders(user_id: int):
    """Відправляє повідомлення з активними доставками кур'єра."""
    orders = db.get_courier_active_orders(user_id)
    
    if not orders:
        bot.send_message(user_id, "📭 У вас немає активних доставок на даний момент.")
        return

    # Групуємо по батчу, якщо замовлення в маршрутах
    for order in orders:
            raw_phone = str(order['delivery_phone'])
            # Маршрутний номер, якщо є
            route_prefix = f"#{order['route_order']} " if order['route_order'] else ""
            
            text = (
                f"📍 *{route_prefix}АДРЕСА: {escape_md(order['delivery_address']).upper()}*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📞 *Телефон:* {raw_phone}\n"
                f"👤 *Клієнт:* {escape_md(order['delivery_name'])}\n"
                f"💰 *Сума:* {order['total_amount']} грн ({escape_md(order['payment_method'])})\n"
                f"📝 *Коментар:* {escape_md(order['comment']) if order['comment'] else '---'}\n"
                f"📦 *Замовлення:* #{order['id']}"
            )

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                "✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО",
                callback_data=f"courier_delivered_{order['id']}"
            ))

            # Кнопка маршруту
            maps_url = get_maps_url(order['delivery_address'])
            markup.add(
                InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url)
            )

            bot.send_message(user_id, text, reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text in ['🟢 Вийти на зміну', '🔴 Завершити зміну'])
def toggle_shift(message):
    """Вмикає/вимикає статус кур'єра на зміні."""
    user_id = message.from_user.id
    status = "on" if message.text == '🟢 Вийти на зміну' else "off"
    
    conn = db.get_db_connection()
    conn.execute('UPDATE couriers SET shift_status = ? WHERE chat_id = ?', (status, user_id))
    conn.commit()
    
    text = "✅ **Ви на зміні!** Шеф бачить вас у списку." if status == "on" else "🔌 **Зміну завершено.** Гарного відпочинку!"
    bot.send_message(user_id, text, reply_markup=keyboards.get_courier_keyboard(user_id), parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Мій звіт за сьогодні')
def show_courier_report(message):
    """Показує статистику кур'єра за поточний день з розділенням Оплати."""
    user_id = message.from_user.id
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = db.get_db_connection()
    cursor = conn.execute('''
        SELECT total_amount, payment_method 
        FROM orders 
        WHERE courier_id = ? AND status = 'completed' AND date(created_at) = ?
    ''', (user_id, today))
    orders = cursor.fetchall()
    
    count = len(orders)
    total_cash = sum(o['total_amount'] for o in orders if "Готівка" in o['payment_method'])
    total_card = sum(o['total_amount'] for o in orders if "карту" in o['payment_method'])
    total_sum = total_cash + total_card

    report = (
        f"📊 **Твій звіт за сьогодні:**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Доставлено замовлень: `{count}`\n\n"
        f"💵 Готівка: `{total_cash} грн`\n"
        f"💳 На карту: `{total_card} грн`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 **ЗАГАЛЬНА КАСА: {total_sum} грн**"
    )
    
    bot.reply_to(message, report, parse_mode='Markdown')
