"""
Хендлери для тестового перемикання ролей.
Працюють тільки для адміна (ADMIN_ID).
"""
from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger
import database as db
import keyboards


from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


@bot.message_handler(commands=['roles'])
def show_roles_menu(message):
    """Показує меню вибору ролей для Адміна."""
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Адмін (Шеф)", callback_data="set_role_admin"))
    markup.add(InlineKeyboardButton("🛵 Кур'єр", callback_data="set_role_courier"))
    markup.add(InlineKeyboardButton("💃 Зал (Наташа)", callback_data="set_role_hall"))
    markup.add(InlineKeyboardButton("👤 Клієнт", callback_data="set_role_client"))
    
    bot.reply_to(
        message, 
        "🎭 **Вибір ролі для тестування:**\nОберіть, який інтерфейс ви хочете бачити зараз.",
        reply_markup=markup,
        parse_mode='Markdown'
    )


# Ми прибираємо текстові команди /set_role_... і переносимо логіку в callbacks
# Базова логіка тепер працює через Inline кнопки
