"""
Хендлер залу (Наташа): чекі, каса.
"""
from bot import bot
from bot.config import ADMIN_ID
import database as db
import keyboards


@bot.message_handler(func=lambda message: message.text == '➕ Новий Чек')
def start_hall_order(message):
    """Наташа відкриває новий чек."""
    user_id = message.from_user.id
    hall_staff = db.get_hall_staff()
    if not any(h['chat_id'] == user_id for h in hall_staff) and user_id != ADMIN_ID:
        return

    db.clear_cart(user_id)
    db.set_user_state(user_id, 'hall_picking_items')
    bot.send_message(
        message.chat.id,
        "🎫 **Відкриваємо новий чек (ЗАЛ).**\n\n"
        "Оберіть страви, які замовили клієнти. Коли закінчите — натисніть '🛒 Оформити'.",
        reply_markup=keyboards.get_categories_keyboard(),
        parse_mode='Markdown'
    )
@bot.message_handler(func=lambda message: message.text == '📊 Моя каса за сьогодні')
def show_hall_revenue(message):
    """Показує виручку Наталі (Зал) за сьогодні."""
    user_id = message.from_user.id
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_db_connection()
    res = conn.execute(
        'SELECT SUM(total_amount) as total FROM orders WHERE hall_staff_id = ? AND status = "completed" AND date(created_at) = ?',
        (user_id, today)
    ).fetchone()
    total = res['total'] if res['total'] else 0
    bot.reply_to(message, f"💰 Ваша каса за сьогодні: **{total} грн**", parse_mode='Markdown')
