"""
Хендлери кур'єра: доставки, звіти, зміни.
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.utils import logger, clean_phone, get_maps_url
import database as db
import keyboards


@bot.message_handler(func=lambda message: message.text == '🛵 Мої доставки (в роботі)')
def show_courier_orders(message):
    """Показує кур'єру його активні замовлення з маршрутом."""
    user_id = message.from_user.id
    logger.info(f"Courier {user_id} checking orders")

    # Перевіряємо чи це кур'єр
    couriers = db.get_couriers()
    courier = next((c for c in couriers if c['chat_id'] == user_id), None)

    if not courier:
        bot.reply_to(message, "❌ Ви не зареєстровані як кур'єр. Зверніться до адміна.")
        return

    # Контроль зміни
    if courier['shift_status'] == 'off':
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Почати зміну", callback_data="shift_on"))
        bot.reply_to(
            message,
            "🔌 Ви зараз **поза зміною**. Натисніть кнопку, щоб почати роботу та отримувати замовлення.",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return

    conn = db.get_db_connection()
    orders = conn.execute('''
        SELECT * FROM orders
        WHERE courier_id = ? AND status = "delivery"
        ORDER BY CASE WHEN route_order IS NULL THEN 999 ELSE route_order END ASC, created_at DESC
    ''', (user_id,)).fetchall()

    logger.info(f"Found {len(orders)} active orders for courier {user_id}")

    if not orders:
        bot.reply_to(message, "📭 У вас немає активних доставок на даний момент.")
        return

    for order in orders:
        courier_markup = InlineKeyboardMarkup()
        courier_markup.add(InlineKeyboardButton(
            "✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО",
            callback_data=f"courier_delivered_{order['id']}"
        ))

        # Кнопки навігації
        address = order['delivery_address']
        maps_url = get_maps_url(address)
        raw_phone = str(order['delivery_phone'])
        phone = clean_phone(raw_phone)

        courier_markup.add(
            InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url),
            InlineKeyboardButton("📞 Зателефонувати", url=f"tel:{phone}")
        )

        # Номер у маршруті
        route_prefix = f"#{order['route_order']} " if order['route_order'] else ""

        msg = (
            f"📍 **{route_prefix}АДРЕСА: {address.upper()}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 **Телефон:** `{raw_phone}`\n"
            f"👤 **Клієнт:** {order['delivery_name']}\n"
            f"💰 **Сума:** {order['total_amount']} грн ({order['payment_method']})\n"
            f"📝 **Коментар:** {order['comment'] if order['comment'] else '---'}\n"
            f"📦 **Замовлення:** #{order['id']}"
        )
        bot.send_message(user_id, msg, reply_markup=courier_markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Мій звіт за сьогодні')
def show_courier_report(message):
    """Кнопка 'Мій звіт за сьогодні'."""
    handle_my_report(message)


@bot.message_handler(commands=['my_report'])
def handle_my_report(message):
    """Звіт кур'єра за сьогодні: кількість і сума."""
    user_id = message.from_user.id
    count, total = db.get_daily_report(user_id)

    if count == 0:
        bot.reply_to(message, "💤 Сьогодні замовлень ще не було.")
    else:
        bot.reply_to(
            message,
            f"📊 **Ваш звіт за сьогодні:**\n\n"
            f"📦 Доставлено: **{count}**\n"
            f"💰 Готівка: **{total} грн**\n\n"
            f"Продуктивного дня! 🚀",
            parse_mode='Markdown'
        )
