"""
FSM (Finite State Machine) хендлери для оформлення замовлення.
Обробляє кроки: ім'я → телефон → адреса → коментар → оплата.
"""
import re
import json

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger, get_maps_url
import database as db
import keyboards


@bot.message_handler(func=lambda message: message.text == "❌ Скасувати")
def cancel_checkout(message):
    """Скасовує поточний процес оформлення."""
    user_id = message.from_user.id
    current_state = db.get_user_state(user_id)
    if current_state:
        db.clear_user_state(user_id)
        from bot.handlers.start import _get_role_keyboard
        bot.reply_to(message, "❌ Оформлення скасовано.", reply_markup=_get_role_keyboard(user_id))
    else:
        bot.reply_to(message, "Немає активного процесу.")


@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def back_step(message):
    """Повертає на попередній крок FSM."""
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)
    if not state_info:
        from bot.handlers.start import _get_role_keyboard
        bot.reply_to(message, "Головне меню:", reply_markup=_get_role_keyboard(user_id))
        return

    state = state_info['state']
    data = state_info['data'] or {}

    if state == 'checkout_contact':
        db.set_user_state(user_id, 'checkout_name', data)
        bot.reply_to(message, "📝 Введіть ваше ім'я:", reply_markup=keyboards.get_checkout_cancel_keyboard())
    elif state == 'checkout_address':
        db.set_user_state(user_id, 'checkout_contact', data)
        bot.reply_to(message, "📞 Введіть ваш номер телефону:", reply_markup=keyboards.get_checkout_contact_keyboard())
    elif state == 'checkout_comment':
        db.set_user_state(user_id, 'checkout_address', data)
        bot.reply_to(message, "📍 **Введіть назву вулиці та номер будинку:**", reply_markup=keyboards.get_checkout_step_keyboard(), parse_mode='Markdown')
    elif state == 'checkout_payment':
        db.set_user_state(user_id, 'checkout_comment', data)
        bot.reply_to(message, "📝 **Додайте коментар до замовлення:**\n(квартира, під'їзд, код домофону)", reply_markup=keyboards.get_checkout_comment_keyboard(), parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def start_checkout(call):
    """Початок оформлення замовлення. Перевіряємо історію."""
    user_id = call.from_user.id
    last_order = db.get_last_order(user_id)
    
    if last_order:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ ТАК, використати минулі дані", callback_data="checkout_use_history"))
        markup.add(InlineKeyboardButton("🆕 НІ, ввести нові дані", callback_data="checkout_new_data"))
        
        text = (
            "🧐 **Я знайшов ваші минулі дані:**\n\n"
            f"👤 Ім'я: {last_order['delivery_name']}\n"
            f"📞 Тел: {last_order['delivery_phone']}\n"
            f"📍 Адреса: {last_order['delivery_address']}\n\n"
            "Бажаєте викоридати їх для цього замовлення?"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        db.set_user_state(user_id, 'checkout_name', {})
        bot.send_message(user_id, "📝 **Як до вас звертатися?** (Введіть ім'я)", reply_markup=keyboards.get_checkout_cancel_keyboard(), parse_mode='Markdown')
    
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data in ["checkout_use_history", "checkout_new_data"])
def handle_history_choice(call):
    user_id = call.from_user.id
    if call.data == "checkout_use_history":
        last_order = db.get_last_order(user_id)
        data = {
            'name': last_order['delivery_name'],
            'contact': last_order['delivery_phone'],
            'address': last_order['delivery_address']
        }
        db.set_user_state(user_id, 'checkout_comment', data)
        bot.send_message(user_id, "🚀 **Дані підтягнуто!**\n\n📝 **Додайте деталі замовлення:**\n(Номер квартири, під'їзд, код домофону)", reply_markup=keyboards.get_checkout_comment_keyboard(), parse_mode='Markdown')
    else:
        db.set_user_state(user_id, 'checkout_name', {})
        bot.send_message(user_id, "📝 **Введіть ваше ім'я:**", reply_markup=keyboards.get_checkout_cancel_keyboard(), parse_mode='Markdown')
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=['text', 'contact'], func=lambda message: db.get_user_state(message.from_user.id) is not None)
def process_checkout_step(message):
    """Основний FSM — обробляє кожен крок оформлення."""
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)
    if not state_info: return

    state = state_info['state']
    data = state_info['data'] or {}

    # --- Kitchen/Mailing Logic ---
    if state == 'kitchen_adding_item':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            from bot.handlers.start import _get_role_keyboard
            bot.send_message(message.chat.id, "Скасовано.", reply_markup=_get_role_keyboard(user_id))
            return
        parts = message.text.replace("➕ ", "").rsplit(maxsplit=1)
        name, qty = (parts[0], parts[1]) if len(parts) > 1 else (parts[0], "?")
        db.upsert_shopping_item(name, qty)
        from bot.handlers.start import _get_role_keyboard
        bot.send_message(message.chat.id, f"✅ Додано в список: **{name} ({qty})**", reply_markup=_get_role_keyboard(user_id), parse_mode='Markdown')
        db.clear_user_state(user_id)
        return

    # --- Manual Order Logic ---
    if state == 'manual_checkout_name':
        data['name'] = message.text
        db.set_user_state(user_id, 'manual_checkout_contact', data)
        bot.send_message(user_id, "📞 Введіть номер телефону клієнта:", reply_markup=keyboards.get_checkout_step_keyboard())
        return
    elif state == 'manual_checkout_contact':
        data['contact'] = message.text
        db.set_user_state(user_id, 'manual_checkout_address', data)
        bot.send_message(user_id, "📍 Введіть адресу доставки:", reply_markup=keyboards.get_checkout_step_keyboard())
        return
    elif state == 'manual_checkout_address':
        data['address'] = message.text
        cart_items = db.get_cart_items(user_id)
        total = sum(i['price'] * i['quantity'] for i in cart_items)
        order_id = db.create_order(user_id, total, "💵 Ручне", data, cart_items)
        if order_id:
            db.clear_cart(user_id)
            db.clear_user_state(user_id)
            from bot.handlers.start import _get_role_keyboard
            bot.send_message(user_id, f"✅ **Ручне замовлення #{order_id} створено!**", reply_markup=_get_role_keyboard(user_id))
        return

    elif state == 'admin_setting_time':
        order_id = data.get('order_id')
        time_text = message.text
        # Перевірка формату (мінімальна)
        if not re.match(r'^\d{1,2}:\d{2}$', time_text):
            bot.reply_to(message, "⚠️ Будь ласка, введіть час у форматі ЧЧ:ММ (наприклад, 18:30):")
            return
        
        db.set_order_scheduled(order_id, time_text)
        db.clear_user_state(user_id)
        from bot.handlers.start import _get_role_keyboard
        bot.send_message(user_id, f"📅 **Замовлення #{order_id} відкладено на {time_text}**.\nЯ нагадаю вам про нього за годину!", reply_markup=_get_role_keyboard(user_id), parse_mode='Markdown')
        
        # Сповістити клієнта
        order = db.get_order_by_id(order_id)
        if order:
            bot.send_message(order['user_id'], f"👨‍🍳 **Ваше замовлення #{order_id} прийнято!**\nЧас доставки: **близько {time_text}**.", parse_mode='Markdown')
        return
    if state == 'checkout_name':
        data['name'] = message.text
        db.set_user_state(user_id, 'checkout_contact', data)
        bot.reply_to(message, "📞 **Чудово!** Тепер введіть номер телефону:", reply_markup=keyboards.get_checkout_contact_keyboard(), parse_mode='Markdown')
        return

    elif state == 'checkout_contact':
        phone = message.contact.phone_number if message.contact else message.text
        data['contact'] = re.sub(r'[^\d+]', '', phone)
        db.set_user_state(user_id, 'checkout_address', data)
        bot.reply_to(message, "📍 **Введіть назву вулиці та номер будинку:**", reply_markup=keyboards.get_checkout_step_keyboard(), parse_mode='Markdown')
        return

    elif state == 'checkout_address':
        data['address'] = message.text
        db.set_user_state(user_id, 'checkout_comment', data)
        bot.reply_to(message, "📝 **Додайте коментар до замовлення:**\n(квартира, під'їзд, код домофону)", reply_markup=keyboards.get_checkout_comment_keyboard(), parse_mode='Markdown')
        return

    elif state == 'checkout_comment':
        data['comment'] = "" if message.text == "⏭️ Пропустити" else message.text
        db.set_user_state(user_id, 'checkout_payment', data)
        bot.reply_to(message, "💳 **Виберіть спосіб оплати:**", reply_markup=keyboards.get_payment_method_keyboard(), parse_mode='Markdown')
        return

    elif state == 'checkout_payment':
        if message.text not in ["💵 Готівка", "💳 На карту"]:
            bot.reply_to(message, "⚠️ Будь ласка, оберіть спосіб оплати кнопкою.")
            return

        cart_items = db.get_cart_items(user_id)
        if not cart_items:
            from bot.handlers.start import _get_role_keyboard
            bot.reply_to(message, "🛒 Кошик порожній.", reply_markup=_get_role_keyboard(user_id))
            db.clear_user_state(user_id)
            return

        total_price = sum(item['price'] * item['quantity'] for item in cart_items)
        order_id = db.create_order(user_id, total_price, message.text, data, cart_items)

        if order_id:
            db.clear_cart(user_id)
            db.clear_user_state(user_id)
            from bot.handlers.start import _get_role_keyboard
            bot.send_message(user_id, f"🎉 **Замовлення #{order_id} прийнято!**", reply_markup=_get_role_keyboard(user_id), parse_mode='Markdown')
            if ADMIN_ID:
                bot.send_message(ADMIN_ID, f"🔥 **НОВЕ ЗАМОВЛЕННЯ #{order_id}**\n👤 {data['name']}\n📍 {data['address']}\n💰 {total_price} грн", parse_mode='Markdown')
        return
