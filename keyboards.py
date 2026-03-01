# -*- coding: utf-8 -*-
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import database as db

# Emoji mapping for categories
category_emojis = {
    'kompleksni-obidy': '🍱',
    'osnovni-stravy': '🍲',
    'fast-food': '🍔',
    'pitsa': '🍕',
    'salaty': '🥗',
    'deserty': '🍰',
    'napoi': '🥤',
    'stravy-na-zamovlennya': '🔥'
}

def get_client_keyboard():
    """Чиста клавіатура клієнта: тільки WebApp та управління замовленнями."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    from telebot.types import WebAppInfo
    # Використовуємо твій актуальний URL
    web_app = WebAppInfo(url="https://HollyLight28.github.io/smakota-telegram-app/") 
    
    keyboard.row(KeyboardButton('🍕 ВІДКРИТИ МЕНЮ (Сайт)', web_app=web_app))
    keyboard.row('🛒 Мій Кошик (Список)', '📋 Статус замовлення')
    keyboard.row('📞 Контакти', '❓ Допомога')
    return keyboard

def get_courier_keyboard():
    """Main keyboard for couriers."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('🛵 Мої доставки (в роботі)')
    keyboard.row('📊 Мій звіт за сьогодні')
    keyboard.row('❓ Допомога')
    return keyboard

def get_admin_keyboard():
    """Майстер-клавіатура для Адміна/Шефа."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('📋 Нові замовлення', '📊 Виручка за сьогодні')
    keyboard.row('📞 Нове ручне замовлення', '📋 Всі активні замовлення')
    keyboard.row('📊 Моніторинг', '🔄 Оновити меню (GS)')
    keyboard.row('📣 Розсилка', '📖 Інструкція')
    return keyboard

def get_dispatcher_keyboard():
    """Main keyboard for dispatchers (phone order operators)."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('📞 Нове ручне замовлення')
    keyboard.row('📋 Всі активні замовлення')
    keyboard.row('❓ Допомога')
    return keyboard

def get_hall_staff_keyboard():
    """Main keyboard for Natasha (Hall)."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('➕ Новий Чек', '🛒 Моє замовлення')
    keyboard.row('📊 Моя каса за сьогодні')
    keyboard.row('❓ Допомога')
    return keyboard

def get_kitchen_keyboard():
    """Main keyboard for Kitchen Staff."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('📝 Записник для Шефа')
    keyboard.row('🛒 Список закупів')
    keyboard.row('❓ Допомога')
    return keyboard

def get_main_keyboard(is_courier=False, is_dispatcher=False, is_hall=False, is_kitchen=False):
    """Fallback function, now delegates to specific roles."""
    if is_courier:
        return get_courier_keyboard()
    if is_dispatcher:
        return get_dispatcher_keyboard()
    if is_hall:
        return get_hall_staff_keyboard()
    if is_kitchen:
        return get_kitchen_keyboard()
    return get_client_keyboard()

def get_use_previous_data_keyboard():
    """Keyboard for selecting previous order data."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("✅ Використати минулі дані", "🆕 Ввести нові")
    markup.add("❌ Скасувати")
    return markup

def get_categories_keyboard():
    """Builds categories inline keyboard from database."""
    keyboard = InlineKeyboardMarkup()
    categories = db.get_categories()
    for category in categories:
        emoji = category_emojis.get(category['id'], '🍽️') # Default emoji if not found
        keyboard.add(InlineKeyboardButton(f"{emoji} {category['name']}", callback_data=f"category_{category['id']}"))
    return keyboard

def get_items_keyboard(category_id):
    """Builds items inline keyboard for a category from database."""
    keyboard = InlineKeyboardMarkup(row_width=1)
    items = db.get_items_by_category(category_id)
    
    for item in items:
        # Truncate long item names to prevent Telegram API errors
        max_len = 40
        item_name = item['name']
        if len(item_name) > max_len:
            item_name = item_name[:max_len-3] + "..."
            
        button_text = f"{item_name} - {item['price']} грн"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"item_{item['id']}"))
        
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories"))
    return keyboard

def get_cart_item_control_keyboard(item_id, quantity):
    """Creates buttons to manage a specific item in the cart."""
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("➖", callback_data=f"cart_minus_{item_id}"),
        InlineKeyboardButton(f"{quantity} шт.", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cart_plus_{item_id}")
    )
    keyboard.add(InlineKeyboardButton("🗑️ Видалити", callback_data=f"cart_remove_{item_id}"))
    return keyboard

def get_cart_actions_keyboard():
    """Buttons for the main cart message (Checkout/Clear)."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Оформити замовлення", callback_data="checkout"),
        InlineKeyboardButton("🗑️ Очистити кошик", callback_data="clear_cart")
    )
    markup.add(InlineKeyboardButton("🍕 До меню", callback_data="show_menu"))
    return markup

def get_empty_cart_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🍕 Перейти до меню", callback_data="show_menu"))
    return markup

def get_checkout_cancel_keyboard():
    """Simple Cancel button for FSM."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("❌ Скасувати")
    return markup

def get_checkout_contact_keyboard():
    """Contact request + Navigation."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📞 Відправити мій номер", request_contact=True))
    markup.row("🔙 Назад", "❌ Скасувати")
    return markup

def get_checkout_step_keyboard():
    """Standard navigation for text input steps."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("🔙 Назад", "❌ Скасувати")
    return markup

def get_checkout_comment_keyboard():
    """Keyboard for comment step with Skip option."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("⏭️ Пропустити")
    markup.row("🔙 Назад", "❌ Скасувати")
    return markup

def get_payment_method_keyboard():
    """Payment selection + Navigation."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("💵 Готівка", "💳 Термінал")
    markup.row("🔙 Назад", "❌ Скасувати")
    return markup
