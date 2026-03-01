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
    Тепер ми спершу дивимось, яку роль користувач вибрав останньою в /roles.
    """
    saved_role = db.get_user_current_role(user_id)
    
    if saved_role == "admin": return keyboards.get_admin_keyboard()
    if saved_role == "courier": return keyboards.get_courier_keyboard()
    if saved_role == "hall": return keyboards.get_hall_staff_keyboard()
    if saved_role == "client": return keyboards.get_client_keyboard()

    # Якщо ролі в базі немає (перший старт) - для Адміна все одно покажемо Клієнта (щоб бачив сайт)
    return keyboards.get_client_keyboard()
