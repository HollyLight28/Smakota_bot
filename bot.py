import telebot
import os
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import database as db

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env file")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FSM states (order details are still in-memory, but cart is in DB)
USER_ORDER = {}
USER_STATE = {}

# --- Keyboard Functions ---

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('🍕 Меню', '🛒 Моє замовлення')
    keyboard.row('📞 Контакти', '❓ Допомога')
    return keyboard

def get_categories_keyboard():
    """Builds categories keyboard from database."""
    keyboard = InlineKeyboardMarkup()
    categories = db.get_categories()
    for category in categories:
        keyboard.add(InlineKeyboardButton(category['name'], callback_data=f"category_{category['id']}"))
    return keyboard

def get_items_keyboard(category_id):
    """Builds items keyboard for a category from database."""
    keyboard = InlineKeyboardMarkup()
    items = db.get_items_by_category(category_id)
    for item in items:
        keyboard.add(InlineKeyboardButton(f"{item['name']} - {item['price']} грн", callback_data=f"item_{item['id']}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories"))
    return keyboard

# --- Cart Formatting ---

def format_cart_message(user_id):
    """Formats the cart message and calculates total by fetching data from the DB."""
    cart_items = db.get_cart_items(user_id)
    if not cart_items:
        return "Ваш кошик порожній", 0
    
    message = "🛒 Ваше замовлення:\n\n"
    total = 0
    
    for item in cart_items:
        item_total = item['price'] * item['quantity']
        total += item_total
        message += f"• {item['name']} x{item['quantity']} = {item_total} грн\n"
    
    message += f"\n💰 Загалом: {total} грн"
    return message, total

# --- Message Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    welcome_text = f"🌟 Вітаємо в Smakota! 🌟\n\nОберіть розділ меню або перегляньте ваше замовлення:"
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"User {user.id} ({user.username}) started the bot")

@bot.message_handler(func=lambda message: message.text == '🍕 Меню')
def show_menu(message):
    bot.reply_to(message, "Оберіть категорію:", reply_markup=get_categories_keyboard())

@bot.message_handler(func=lambda message: message.text == '🛒 Моє замовлення')
def show_cart(message):
    user_id = message.from_user.id
    cart_message, total = format_cart_message(user_id)
    
    if total == 0:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 Переглянути меню", callback_data="show_menu"))
        bot.reply_to(message, cart_message, reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Оформити замовлення", callback_data="checkout"),
            InlineKeyboardButton("❌ Очистити кошик", callback_data="clear_cart")
        )
        bot.reply_to(message, cart_message, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['📞 Контакти', '❓ Допомога'])
def handle_info_buttons(message):
    if message.text == '📞 Контакти':
        contacts_text = (
            "📞 Контакти Smakota:\n\n"
            "📱 Телефон: +380 (12) 345-67-89\n"
            "📧 Email: info@smakota.ua\n"
            "📍 Адреса: м. Київ, вулиця Смакотна, 15"
        )
        bot.reply_to(message, contacts_text)
    elif message.text == '❓ Допомога':
        help_text = (
            "❓ Допомога:\n\n"
            "1. Натисніть '🍕 Меню' для перегляду страв.\n"
            "2. Оберіть категорію та додайте страви до кошика.\n"
            "3. Натисніть '🛒 Моє замовлення' для перегляду та оформлення."
        )
        bot.reply_to(message, help_text)

# --- Callback Query Handlers ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data.startswith("category_"):
            category_id = data.split("_")[1]
            category_name = db.get_category_name_by_id(category_id)
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text=f"Оберіть страву з категорії {category_name}:",
                reply_markup=get_items_keyboard(category_id)
            )
        
        elif data.startswith("item_"):
            item_id = int(data.split("_")[1])
            item = db.get_item_by_id(item_id)
            if item:
                db.add_to_cart(user_id, item_id)
                bot.answer_callback_query(call.id, f"✅ {item['name']} додано до кошика!", show_alert=True)
        
        elif data == "back_to_categories" or data == "show_menu":
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text="Оберіть категорію:", reply_markup=get_categories_keyboard()
            )
        
        elif data == "checkout":
            _, total = format_cart_message(user_id)
            if total == 0:
                bot.answer_callback_query(call.id, "Ваш кошик порожній!", show_alert=True)
                return

            USER_STATE[user_id] = {'step': 'name'}
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text="Почнемо оформлення замовлення.\n\nВведіть ваше ім'я:"
            )
        
        elif data == "clear_cart":
            db.clear_cart(user_id)
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text="❌ Кошик очищено!"
            )
            
        elif data == "confirm_order":
            if user_id in USER_ORDER and 'name' in USER_ORDER[user_id]:
                cart_message, total = format_cart_message(user_id)
                
                if ADMIN_ID:
                    try:
                        order_details = USER_ORDER[user_id]
                        admin_message = (
                            f"🔔 Нове замовлення!\n\n"
                            f"👤 Ім'я: {order_details['name']}\n"
                            f"📞 Контакт: {order_details['contact']}\n"
                            f"📍 Адреса: {order_details['address']}\n"
                            f"💬 Коментар: {order_details.get('comment', 'немає')}\n\n"
                            f"{cart_message}"
                        )
                        bot.send_message(ADMIN_ID, admin_message)
                    except Exception as e:
                        logger.error(f"Failed to send order to admin: {e}")
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"✅ Дякуємо! Ваше замовлення на суму {total} грн прийнято."
                )
                
                # Cleanup
                db.clear_cart(user_id)
                if user_id in USER_ORDER: del USER_ORDER[user_id]
                if user_id in USER_STATE: del USER_STATE[user_id]
        
        elif data == "cancel_order":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Замовлення скасовано.")
            if user_id in USER_ORDER: del USER_ORDER[user_id]
            if user_id in USER_STATE: del USER_STATE[user_id]

    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка, спробуйте ще раз", show_alert=True)

# --- Checkout Text Handlers ---

@bot.message_handler(func=lambda message: USER_STATE.get(message.from_user.id) is not None)
def handle_checkout_message(message):
    user_id = message.from_user.id
    current_step = USER_STATE.get(user_id, {}).get('step')
    
    if current_step == 'name':
        USER_ORDER[user_id] = {'name': message.text}
        USER_STATE[user_id]['step'] = 'contact'
        bot.reply_to(message, "Тепер введіть ваш номер телефону:")
        
    elif current_step == 'contact':
        USER_ORDER[user_id]['contact'] = message.text
        USER_STATE[user_id]['step'] = 'address'
        bot.reply_to(message, "Тепер введіть адресу доставки:")
        
    elif current_step == 'address':
        USER_ORDER[user_id]['address'] = message.text
        USER_STATE[user_id]['step'] = 'comment'
        
        cart_message, _ = format_cart_message(user_id)
        summary = (
            f"📋 Підсумок замовлення:\n\n"
            f"👤 Ім'я: {USER_ORDER[user_id]['name']}\n"
            f"📞 Контакт: {USER_ORDER[user_id]['contact']}\n"
            f"📍 Адреса: {message.text}\n\n"
            f"{cart_message}\n\n"
            f"Додайте коментар або підтвердіть замовлення:"
        )
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("✅ Підтвердити замовлення", callback_data="confirm_order"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")
        )
        bot.reply_to(message, summary, reply_markup=markup)
        # We go to a confirmation step, no more text input expected unless they cancel
        USER_STATE[user_id]['step'] = 'confirmation'


@bot.message_handler(func=lambda message: True)
def handle_default_message(message):
    bot.reply_to(message, "Будь ласка, використовуйте кнопки для взаємодії з ботом.", reply_markup=get_main_keyboard())


if __name__ == '__main__':
    db.setup_database()  # Ensure DB and tables exist
    logger.info("Starting Smakota bot...")
    bot.polling(none_stop=True)
