import telebot
import os
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import database as db
import keyboards # Import the new keyboards module
import threading
from update_menu import update_menu_from_csv

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
    
    photo_url = "https://upload.wikimedia.org/wikipedia/commons/6/6d/Good_Food_Display_-_NCI_Visuals_Online.jpg"
    
    welcome_text = (
        "🌟 **Вітаємо у 'Смакоті' — вашій улюбленій столовій!** 🌟\n\n"
        "Смачні домашні страви за чесною ціною, тепер і з доставкою. "
        "Готуємо з любов'ю, доставляємо зі швидкістю!\n\n"
        "Оберіть розділ, щоб почати:"
    )
    
    bot.send_photo(
        message.chat.id,
        photo=photo_url,
        caption=welcome_text,
        reply_markup=keyboards.get_main_keyboard()
    )
    logger.info(f"User {user.id} ({user.username}) started the bot")

# --- Admin Commands ---

def _run_update_in_thread(message):
    """Helper to run the update and notify the admin."""
    try:
        logger.info(f"Admin {message.from_user.id} triggered menu update.")
        update_menu_from_csv()
        bot.reply_to(message, "✅ Меню успішно оновлено!")
        logger.info("Menu update process finished successfully.")
    except Exception as e:
        logger.error(f"Menu update failed: {e}")
        bot.reply_to(message, f"❌ Помилка під час оновлення меню: {e}")

@bot.message_handler(commands=['updatemenu'])
def handle_update_menu(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Ця команда доступна лише адміністратору.")
        return
    
    bot.reply_to(message, "⏳ Починаю оновлення меню... Це може зайняти хвилину.")
    
    # Run in a separate thread to not block the bot
    update_thread = threading.Thread(target=_run_update_in_thread, args=(message,))
    update_thread.start()

@bot.message_handler(func=lambda message: message.text == '🍕 Меню')
def show_menu(message):
    bot.reply_to(message, "Оберіть категорію:", reply_markup=keyboards.get_categories_keyboard())

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
                reply_markup=keyboards.get_items_keyboard(category_id)
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
                text="Оберіть категорію:", reply_markup=keyboards.get_categories_keyboard()
            )
        
        elif data == "checkout":
            _, total = format_cart_message(user_id)
            if total == 0:
                bot.answer_callback_query(call.id, "Ваш кошик порожній!", show_alert=True)
                return

            db.set_user_state(user_id, 'checkout_name')
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
            user_state = db.get_user_state(user_id)
            if user_state and user_state['state'] == 'checkout_confirmation':
                order_details = user_state['data']
                cart_message, total = format_cart_message(user_id)
                
                if ADMIN_ID:
                    try:
                        admin_message = (
                            f"🔔 Нове замовлення!\n\n"
                            f"🧑 Ім'я: {order_details.get('name')}\n"
                            f"📱 Контакт: {order_details.get('contact')}\n"
                            f"🏠 Адреса: {order_details.get('address')}\n"
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
                db.clear_user_state(user_id)
        
        elif data == "cancel_order":
            db.clear_user_state(user_id)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Замовлення скасовано.")

    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка, спробуйте ще раз", show_alert=True)

# --- Checkout Text Handlers ---

@bot.message_handler(func=lambda message: db.get_user_state(message.from_user.id) is not None)
def handle_checkout_message(message):
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)
    
    if not state_info:
        return

    state = state_info['state']
    data = state_info['data']

    if state == 'checkout_name':
        data['name'] = message.text
        db.set_user_state(user_id, 'checkout_contact', data)
        bot.reply_to(message, "Тепер введіть ваш номер телефону:")
        
    elif state == 'checkout_contact':
        data['contact'] = message.text
        db.set_user_state(user_id, 'checkout_address', data)
        bot.reply_to(message, "Тепер введіть адресу доставки:")
        
    elif state == 'checkout_address':
        data['address'] = message.text
        db.set_user_state(user_id, 'checkout_confirmation', data) # Move to confirmation state
        
        cart_message, _ = format_cart_message(user_id)
        summary = (
            f"📋 Підсумок замовлення:\n\n"
            f"🧑 Ім'я: {data.get('name')}\n"
            f"📱 Контакт: {data.get('contact')}\n"
            f"🏠 Адреса: {data.get('address')}\n\n"
            f"{cart_message}\n\n"
            f"Все вірно? Підтвердіть або скасуйте замовлення."
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ Підтвердити", callback_data="confirm_order"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")
        )
        bot.reply_to(message, summary, reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def handle_default_message(message):
    bot.reply_to(message, "Будь ласка, використовуйте кнопки для взаємодії з ботом.", reply_markup=keyboards.get_main_keyboard())


if __name__ == '__main__':
    db.setup_database()  # Ensure DB and tables exist
    logger.info("Starting Smakota bot...")
    bot.polling(none_stop=True)
