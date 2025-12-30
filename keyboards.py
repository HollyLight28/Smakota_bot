# -*- coding: utf-8 -*-
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import database as db

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
        keyboard.add(InlineKeyboardButton(category['name'], callback_data=f"category_{category['id']}"))
    return keyboard

def get_items_keyboard(category_id):
    """Builds items inline keyboard for a category from database."""
    keyboard = InlineKeyboardMarkup(row_width=1)
    items = db.get_items_by_category(category_id)
    for item in items:
        keyboard.add(InlineKeyboardButton(f"{item['name']} - {item['price']} грн", callback_data=f"item_{item['id']}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories"))
    return keyboard
