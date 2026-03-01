"""
Хендлер /start та /help.
Відповідає за вітання користувача та визначення його ролі.
"""
import os

from bot import bot
from bot.config import ADMIN_ID, LOGO_PATH
from bot.utils import logger
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
        f"👋 Вітаємо у Smakota, {user.first_name}!\n\n"
        "🥗 **Справжня домашня кухня у вашому смартфоні.**\n"
        "Ми готуємо з найсвіжіших продуктів Рівного та доставляємо гарячим прямо до ваших дверей.\n\n"
        "✨ **Чому обирають нас:**\n"
        "• Тільки натуральні інгредієнти\n"
        "• Швидка доставка по місту\n"
        "• Смак, як вдома\n\n"
        "👇 **Оберіть бажаний розділ:**"
    )

    # Визначаємо роль
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
    """
    Визначає роль користувача. 
    За запитом Шефа: Адмін (Шеф) по замовчуванню завжди бачить меню Клієнта,
    щоб бачити бота очима покупця.
    """
    if user_id == ADMIN_ID:
        return keyboards.get_client_keyboard()

    # Для іншого персоналу лишаємо їх меню
    couriers = db.get_couriers()
    if any(c['chat_id'] == user_id for c in couriers):
        return keyboards.get_courier_keyboard()

    dispatchers = db.get_dispatchers()
    if any(d['chat_id'] == user_id for d in dispatchers):
        return keyboards.get_dispatcher_keyboard()

    hall_staff = db.get_hall_staff()
    if any(h['chat_id'] == user_id for h in hall_staff):
        return keyboards.get_hall_staff_keyboard()

    return keyboards.get_client_keyboard()
