"""
Хендлери для тестового перемикання ролей.
Працюють тільки для адміна (ADMIN_ID).
"""
from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger
import database as db
import keyboards


@bot.message_handler(commands=['set_role_admin'])
def set_role_admin(message):
    """Перемикає на роль адміна."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ заборонено")
        return
    bot.reply_to(
        message,
        "👑 Тепер ти **Адмін**. Повний контроль активовано.",
        reply_markup=keyboards.get_admin_keyboard(),
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['set_role_courier'])
def set_role_courier(message):
    """Перемикає на роль кур'єра."""
    user_id = message.from_user.id
    # Спочатку видаляємо, щоб не було дублікатів
    db.remove_courier_by_chat_id(user_id)
    db.add_courier(f"Test_{message.from_user.first_name}", user_id)
    bot.reply_to(
        message,
        "🛵 Тепер ти **Кур'єр**.\nТвій інтерфейс оновлено.",
        reply_markup=keyboards.get_courier_keyboard(),
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['set_role_client'])
def set_role_client(message):
    """Перемикає на роль клієнта."""
    user_id = message.from_user.id
    db.remove_courier_by_chat_id(user_id)
    bot.reply_to(
        message,
        "👤 Тепер ти **Клієнт**.\nТвій інтерфейс оновлено.",
        reply_markup=keyboards.get_client_keyboard(),
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['remove_me'])
def remove_me_from_roles(message):
    """Видаляє з усіх ролей."""
    db.remove_user_from_roles(message.from_user.id)
    bot.reply_to(message, "🔌 Вас видалено з усіх ролей. Натисніть /start, щоб стати звичайним клієнтом.")
