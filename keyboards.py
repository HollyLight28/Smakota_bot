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

def get_main_keyboard():
    """Creates the main reply keyboard."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('🍕 Меню', '🛒 Моє замовлення')
    keyboard.row('📞 Контакти', '❓ Допомога')
    return keyboard

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
