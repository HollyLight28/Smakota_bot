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


def clean_phone(phone: str) -> str:
    """Очищає номер та додає +380 для українських номерів.
    Telegram вимагає tel: URL у міжнародному форматі."""
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    # Якщо номер починається з 0 (укр формат без коду країни)
    if cleaned.startswith('0') and len(cleaned) == 10:
        cleaned = '+380' + cleaned[1:]
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned


def get_maps_url(address: str) -> str:
    """Генерує URL для Google Maps маршруту в м. Рівне."""
    safe_address = urllib.parse.quote(f"м. Рівне, {address}")
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
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ ОФОРМИТИ ЗАМОВЛЕННЯ", callback_data="checkout"))
    
    # Кнопка повернення на сайт (замість старого меню чату)
    web_app = WebAppInfo(url="https://HollyLight28.github.io/smakota-telegram-app/")
    markup.add(InlineKeyboardButton("🔙 ПОВЕРНУТИСЬ НА САЙТ", web_app=web_app))
    
    markup.add(InlineKeyboardButton("🗑️ Очистити кошик", callback_data="clear_cart"))

    return message, total, markup
