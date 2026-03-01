"""
Default handler — ловить ВСІ повідомлення, які не оброблені іншими хендлерами.
ВАЖЛИВО: Цей модуль ЗАВЖДИ імпортується ОСТАННІМ!
"""
from bot import bot
from bot.utils import logger
import keyboards


@bot.message_handler(func=lambda message: True)
def handle_default_message(message):
    """Стандартна відповідь на невідомі повідомлення."""
    logger.info(f"Unhandled message: '{message.text}' from {message.from_user.id}")
    if message.chat.type == 'private':
        bot.reply_to(message, "🤔 Я вас не розумію. Скористайтеся меню.", reply_markup=keyboards.get_main_keyboard())
