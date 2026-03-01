import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot
from bot.utils import logger, clean_phone, get_maps_url
import database as db
import keyboards


def escape_md(text: str) -> str:
    """Екранує спецсимволи MarkdownV1."""
    if not text: return ""
    return re.sub(r'[_*`\[\]]', r'\\\g<0>', str(text))


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

    if not orders:
        bot.reply_to(message, "📭 У вас немає активних доставок на даний момент.\n\n*Перевірте, чи ви почали зміну.*", parse_mode='Markdown')
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

        # Екрануємо дані для Markdown
        route_prefix = f"#{order['route_order']} " if order['route_order'] else ""
        safe_address = escape_md(address.upper())
        safe_name = escape_md(order['delivery_name'])
        safe_comment = escape_md(order['comment'] if order['comment'] else '---')

        msg = (
            f"📍 **{route_prefix}АДРЕСА: {safe_address}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 **Телефон:** `{raw_phone}`\n"
            f"👤 **Клієнт:** {safe_name}\n"
            f"💰 **Сума:** {order['total_amount']} грн ({order['payment_method']})\n"
            f"📝 **Коментар:** {safe_comment}\n"
            f"📦 **Замовлення:** #{order['id']}"
        )
        try:
            bot.send_message(user_id, msg, reply_markup=courier_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Markdown error in courier msg: {e}")
            # Спроба відправити без Markdown якщо впало
            bot.send_message(user_id, msg.replace('*', '').replace('`', ''), reply_markup=courier_markup)


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

@bot.message_handler(func=lambda message: message.text in ['🟢 Вийти на зміну', '🔴 Завершити зміну'])
def toggle_shift(message):
    """Вмикає/вимикає зміну кур'єра."""
    user_id = message.from_user.id
    new_status = 'on' if '🟢' in message.text else 'off'
    
    # Викликаємо функцію оновлення статусу
    conn = db.get_db_connection()
    conn.execute('UPDATE couriers SET shift_status = ? WHERE chat_id = ?', (new_status, user_id))
    conn.commit()
    
    text = "🚀 **Ви на зміні!** Тепер ви бачите замовлення." if new_status == 'on' else "🔌 **Зміну завершено.** Гарного відпочинку!"
    bot.reply_to(message, text, reply_markup=keyboards.get_courier_keyboard(user_id), parse_mode='Markdown')
