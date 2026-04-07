"""
Утиліти та допоміжні функції для Smakota Bot.
"""
import logging
import re
import urllib.parse

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import keyboards

# Логер
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("smakota_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SmakotaBot')


def escape_md(text) -> str:
    """Екранує спецсимволи Markdown V1 для безпечної відправки в Telegram.
    Без цього бот впаде, якщо ім'я кур'єра або адреса має _, *, ` тощо."""
    if text is None:
        return ""
    text = str(text)
    for ch in ('_', '*', '`', '[', ']'):
        text = text.replace(ch, f'\\{ch}')
    return text


def clean_phone(phone: str) -> str:
    """Очищає номер та додає +38 для українських номерів.
    Telegram вимагає tel: URL у міжнародному форматі."""
    if not phone:
        return "+380000000000"
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    if cleaned.startswith('0'):
        # Трактуємо як укр номер, навіть якщо зайві цифри (типо помилка вводу)
        cleaned = '+38' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned
        
    return cleaned


def get_maps_url(address: str) -> str:
    """Генерує посилання на Google Maps для м. Рівне."""
    import urllib.parse
    # Додаємо місто для точності, щоб не несло в інше місто
    full_address = f"м. Рівне, {address}"
    safe_address = urllib.parse.quote(full_address)
    return f"https://www.google.com/maps/dir/?api=1&destination={safe_address}"


def format_cart_message(user_id: int):
    """
    Чисте підтвердження кошика для чату.
    БЕЗ кнопок +/- (вони в WebApp). 
    Зі списком 1. 2. 3.
    """
    cart_items = db.get_cart_items(user_id)
    if not cart_items:
        return "🛒 **Ваш кошик порожній**\n\nОберіть щось на сайті!", 0, keyboards.get_empty_cart_keyboard()

    total = 0
    message = "🛒 **Ваше замовлення:**\n\n"

    for i, item in enumerate(cart_items, 1):
        item_total = item['price'] * item['quantity']
        total += item_total
        # Додаємо номер перед кожною стравою
        message += f"{i}. **{item['name']}**\n   `{item['quantity']} шт.` × {item['price']} = **{item_total} грн**\n"

    message += f"\n💰 **РАЗОМ: {total} грн**"

    # Використовуємо спеціальну клавіатуру для фінального кроку
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ ОФОРМИТИ ЗАМОВЛЕННЯ", callback_data="checkout"))
    markup.add(InlineKeyboardButton("🗑️ Очистити кошик", callback_data="clear_cart"))

    return message, total, markup
