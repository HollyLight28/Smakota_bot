"""
Хендлер диспетчера: ручне замовлення по телефону.
"""
from bot import bot
from bot.config import ADMIN_ID
import database as db
import keyboards


@bot.message_handler(func=lambda message: message.text == '📞 Нове ручне замовлення')
def start_manual_order(message):
    """Диспетчер починає ручне замовлення."""
    user_id = message.from_user.id
    dispatchers = db.get_dispatchers()
    is_dispatcher = any(d['chat_id'] == user_id for d in dispatchers)

    if not is_dispatcher and user_id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас немає прав для цієї дії.")
        return

    db.clear_cart(user_id)
    db.set_user_state(user_id, 'dispatcher_picking_items')

    bot.send_message(
        message.chat.id,
        "🆕 **Починаємо ручне замовлення.**\n\n"
        "Оберіть страви з меню нижче. Коли закінчите — натисніть кнопку '🛒 Оформити' у кошику.",
        reply_markup=keyboards.get_categories_keyboard(),
        parse_mode='Markdown'
    )
@bot.message_handler(func=lambda message: message.text == '📋 Всі активні замовлення')
def show_active_orders(message):
    """Показує диспетчеру всі поточні активні замовлення."""
    user_id = message.from_user.id
    dispatchers = db.get_dispatchers()
    if not any(d['chat_id'] == user_id for d in dispatchers) and user_id != ADMIN_ID:
        return

    conn = db.get_db_connection()
    orders = conn.execute("SELECT * FROM orders WHERE status IN ('new', 'confirmed', 'delivery', 'hall') ORDER BY created_at DESC").fetchall()

    if not orders:
        bot.reply_to(message, "📭 Активних замовлень зараз немає.")
        return

    for order in orders:
        msg = f"📦 **Замовлення #{order['id']}** ({order['status']})\n"
        msg += f"👤 {order['delivery_name']}\n📞 {order['delivery_phone']}\n📍 {order['delivery_address']}\n"
        msg += f"💰 Сума: {order['total_amount']} грн"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
