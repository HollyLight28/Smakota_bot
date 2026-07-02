"""
Хендлер /start та /help.
Відповідає за вітання користувача та визначення його ролі.
"""
import os

from bot import bot
from bot.config import ADMIN_ID, LOGO_PATH
from bot.utils import logger, escape_md
import database as db
import keyboards


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Вітальне повідомлення з визначенням ролі."""
    user = message.from_user
    logger.info(f"--- /start від {user.id} ({user.first_name}) ---")

    # Зберігаємо користувача в БД
    conn = db.get_db_connection()
    conn.execute(
        'INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
        (user.id, user.username, user.first_name)
    )
    conn.commit()

    db.clear_user_state(user.id)

    welcome_text = (
        f"👋 Вітаємо, {escape_md(user.first_name)}!\n\n"
        "🥘 **SMAKOTA — справжня домашня кухня в Рівному**\n"
        "Ми готуємо з найсвіжіших продуктів, щоб ви насолоджувалися смаком, як вдома.\n\n"
        "⏰ **Графік роботи:**\n"
        "• Пн–Пт: 9:00 – 17:00\n"
        "• Сб: 9:30 – 15:30\n"
        "• Нд: вихідний\n\n"
        "📞 **Телефони:**\n"
        "• +38 068 876 33 08\n"
        "• +38 093 148 53 93\n\n"
        "🚚 **Доставка:**\n"
        "• Вартість: від 40 грн\n"
        "• Безкоштовно при замовленні від 300 грн (у центрі міста)\n"
        "• Мінімальне замовлення онлайн: 300 грн\n\n"
        "👇 **Оберіть бажаний розділ:**"
    )

    # Визначаємо роль
    saved_role = db.get_user_current_role(user.id)

    if saved_role == "admin":
        welcome_text += (
            "\n\n👑 **Панель адміністратора:**\n"
            "• `/set_role_client` — перейти в режим клієнта\n"
            "• `/set_role_courier` — перейти в режим кур'єра\n"
            "• `/roles` — керування ролями"
        )

    markup = _get_role_keyboard(user.id)

    try:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, 'rb') as photo:
                bot.send_photo(
                    message.chat.id,
                    photo=photo,
                    caption=welcome_text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
        else:
            bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error sending welcome: {e}")
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')

    logger.info(f"User {user.id} ({user.username}) started the bot")


def _get_role_keyboard(user_id: int):
    """Визначає клавіатуру на основі поточної ролі користувача."""
    saved_role = db.get_user_current_role(user_id)
    
    if saved_role == "admin": return keyboards.get_admin_keyboard()
    if saved_role == "courier": return keyboards.get_courier_keyboard(user_id)
    if saved_role == "hall": return keyboards.get_hall_staff_keyboard()
    
    # Всі інші випадки (включаючи роль 'client' або відсутність ролі)
    return keyboards.get_client_keyboard()
