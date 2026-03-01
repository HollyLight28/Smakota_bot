"""
FSM (Finite State Machine) хендлери для оформлення замовлення.
Обробляє кроки: ім'я → телефон → адреса → коментар → оплата.
"""
import re

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger
import database as db
import keyboards


@bot.message_handler(func=lambda message: message.text == "❌ Скасувати")
def cancel_checkout(message):
    """Скасовує поточний процес оформлення."""
    user_id = message.from_user.id
    current_state = db.get_user_state(user_id)
    if current_state:
        db.clear_user_state(user_id)

        couriers = db.get_couriers()
        is_courier = any(c['chat_id'] == user_id for c in couriers)

        bot.reply_to(message, "❌ Оформлення замовлення скасовано.", reply_markup=keyboards.get_main_keyboard(is_courier))
    else:
        bot.reply_to(message, "Немає активного процесу для скасування.")


@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def back_step(message):
    """Повертає на попередній крок FSM."""
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)
    if not state_info:
        couriers = db.get_couriers()
        is_courier = any(c['chat_id'] == user_id for c in couriers)
        bot.reply_to(message, "Немає куди повертатися. Скористайтеся меню.", reply_markup=keyboards.get_main_keyboard(is_courier))
        return

    state = state_info['state']
    data = state_info['data']

    if state == 'checkout_contact':
        db.set_user_state(user_id, 'checkout_name', data)
        bot.reply_to(message, "📝 Введіть ваше ім'я:", reply_markup=keyboards.get_checkout_cancel_keyboard())

    elif state == 'checkout_address':
        db.set_user_state(user_id, 'checkout_contact', data)
        bot.reply_to(message, "📞 Введіть ваш номер телефону:", reply_markup=keyboards.get_checkout_contact_keyboard())

    elif state == 'checkout_comment':
        db.set_user_state(user_id, 'checkout_address', data)
        bot.reply_to(message, "📍 Введіть адресу доставки:", reply_markup=keyboards.get_checkout_step_keyboard())

    elif state == 'checkout_payment':
        db.set_user_state(user_id, 'checkout_comment', data)
        bot.reply_to(message, "📝 Бажаєте додати коментар до замовлення?", reply_markup=keyboards.get_checkout_comment_keyboard())


@bot.message_handler(content_types=['text', 'contact'], func=lambda message: db.get_user_state(message.from_user.id) is not None)
def process_checkout_step(message):
    """Основний FSM — обробляє кожен крок оформлення залежно від стану користувача."""
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)

    if not state_info:
        return

    state = state_info['state']
    data = state_info['data']

    # --- Mailing Logic ---
    if state == 'mail_waiting_text':
        data['text'] = message.text
        db.set_user_state(user_id, 'mail_waiting_name', data)
        bot.reply_to(message, "💾 **Текст прийнято.** Тепер введіть коротку назву для цього шаблону (наприклад: 'Акція Суп'):", parse_mode='Markdown')
        return
    elif state == 'mail_waiting_name':
        name = message.text
        content = data['text']
        conn = db.get_db_connection()
        conn.execute('INSERT INTO mailing_templates (name, content) VALUES (?, ?)', (name, content))
        conn.commit()
        db.clear_user_state(user_id)
        bot.reply_to(message, f"✅ **Шаблон '{name}' збережено!**\nВи можете запустити його через меню 'Мої шаблони'.", parse_mode='Markdown')
        return

    # --- Kitchen Shopping List Logic ---
    elif state == 'kitchen_adding_item':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "Скасовано.", reply_markup=keyboards.get_kitchen_keyboard())
            return

        input_text = message.text.replace("➕ ", "").strip()
        parts = input_text.rsplit(maxsplit=1)
        name = parts[0]
        qty = parts[1] if len(parts) > 1 else "?"

        db.upsert_shopping_item(name, qty)
        bot.send_message(message.chat.id, f"✅ Додано в список: **{name} ({qty})**", reply_markup=keyboards.get_kitchen_keyboard(), parse_mode='Markdown')
        db.clear_user_state(user_id)
        return

    # --- Manual Dispatcher Checkout ---
    if state == 'manual_checkout_name':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "❌ Ручне замовлення скасовано.", reply_markup=keyboards.get_dispatcher_keyboard())
            return

        data['name'] = message.text
        db.set_user_state(user_id, 'manual_checkout_contact', data)
        bot.send_message(message.chat.id, "📞 Введіть номер телефону клієнта:", reply_markup=keyboards.get_checkout_step_keyboard())
        return

    elif state == 'manual_checkout_contact':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "❌ Скасовано.", reply_markup=keyboards.get_dispatcher_keyboard())
            return
        if message.text == "🔙 Назад":
            db.set_user_state(user_id, 'manual_checkout_name')
            bot.send_message(message.chat.id, "Як звати клієнта?", reply_markup=keyboards.get_checkout_cancel_keyboard())
            return

        data['contact'] = message.text
        db.set_user_state(user_id, 'manual_checkout_address', data)
        bot.send_message(message.chat.id, "📍 Введіть адресу доставки:", reply_markup=keyboards.get_checkout_step_keyboard())
        return

    elif state == 'manual_checkout_address':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "❌ Скасовано.", reply_markup=keyboards.get_dispatcher_keyboard())
            return
        if message.text == "🔙 Назад":
            db.set_user_state(user_id, 'manual_checkout_contact', data)
            bot.send_message(message.chat.id, "Введіть номер телефону клієнта:", reply_markup=keyboards.get_checkout_step_keyboard())
            return

        data['address'] = message.text

        cart_items = db.get_cart_items(user_id)
        if not cart_items:
            bot.send_message(message.chat.id, "⚠️ Кошик порожній.")
            db.clear_user_state(user_id)
            return

        total = sum(item['price'] * item['quantity'] for item in cart_items)
        order_id = db.create_order(user_id, total, "💵 Готівка (Ручне)", data, cart_items)

        if order_id:
            db.clear_cart(user_id)
            db.clear_user_state(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ **Ручне замовлення #{order_id} створено!**\n\n"
                f"👤 {data['name']}\n📍 {data['address']}\n💰 {total} грн",
                reply_markup=keyboards.get_dispatcher_keyboard(),
                parse_mode='Markdown'
            )

            if ADMIN_ID:
                cart_details = "\n".join([f"• {i['name']} x{i['quantity']}" for i in cart_items])
                admin_msg = f"📞 **РУЧНЕ ЗАМОВЛЕННЯ #{order_id}**\n\n👤 {data['name']}\n📍 {data['address']}\n💰 {total} грн\n\n🛒 **Кошик:**\n{cart_details}"
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("✅ Прийняти", callback_data=f"admin_accept_{order_id}"))
                bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Помилка при створенні.")
        return

    # --- Standard User Checkout ---
    if state == 'checkout_use_history':
        if message.text == "✅ Використати минулі дані":
            hist = data['history']
            data['name'] = hist['delivery_name']
            data['contact'] = hist['delivery_phone']
            data['address'] = hist['delivery_address']
            db.set_user_state(user_id, 'checkout_comment', data)
            bot.reply_to(message, "📍 Дані підтягнуто! Бажаєте додати коментар до замовлення?", reply_markup=keyboards.get_checkout_comment_keyboard())
        else:
            db.set_user_state(user_id, 'checkout_name', data)
            bot.reply_to(message, "📝 Як до вас звертатися? (Введіть ім'я)", reply_markup=keyboards.get_checkout_cancel_keyboard())

    elif state == 'checkout_name':
        if len(message.text) < 2:
            bot.reply_to(message, "⚠️ Ім'я занадто коротке. Спробуйте ще раз.")
            return

        data['name'] = message.text
        db.set_user_state(user_id, 'checkout_contact', data)
        bot.reply_to(message, "📞 Чудово! Тепер введіть номер телефону (або натисніть кнопку):", reply_markup=keyboards.get_checkout_contact_keyboard())

    elif state == 'checkout_contact':
        phone = None
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text
            clean = re.sub(r'[^\d+]', '', phone)
            if not re.match(r'^\+?\d{10,15}$', clean):
                bot.reply_to(message, "⚠️ Схоже, це некоректний номер. Введіть, будь ласка, у форматі +380XXXXXXXXX або скористайтеся кнопкою.")
                return
            phone = clean

        data['contact'] = phone
        db.set_user_state(user_id, 'checkout_address', data)
        bot.reply_to(message, "📍 Куди доставити замовлення? (Вулиця, будинок, під'їзд)", reply_markup=keyboards.get_checkout_step_keyboard())

    elif state == 'checkout_address':
        if len(message.text) < 5:
            bot.reply_to(message, "⚠️ Адреса занадто коротка. Вкажіть детальніше.")
            return

        data['address'] = message.text
        db.set_user_state(user_id, 'checkout_comment', data)
        bot.reply_to(message, "📝 Бажаєте додати коментар до замовлення? (Наприклад: код під'їзду, поверх, або 'залиште біля дверей')", reply_markup=keyboards.get_checkout_comment_keyboard())

    elif state == 'checkout_comment':
        if message.text == "⏭️ Пропустити":
            data['comment'] = ""
        else:
            data['comment'] = message.text

        db.set_user_state(user_id, 'checkout_payment', data)
        bot.reply_to(message, "💳 Як бажаєте оплатити?", reply_markup=keyboards.get_payment_method_keyboard())

    elif state == 'checkout_payment':
        if message.text not in ["💵 Готівка", "💳 Термінал"]:
            bot.reply_to(message, "⚠️ Будь ласка, оберіть спосіб оплати, натиснувши кнопку знизу.")
            return

        cart_items = db.get_cart_items(user_id)
        if not cart_items:
            bot.reply_to(message, "⚠️ Ваш кошик порожній. Замовлення скасовано.", reply_markup=keyboards.get_main_keyboard())
            db.clear_user_state(user_id)
            return

        total_price = sum(item['price'] * item['quantity'] for item in cart_items)
        order_id = db.create_order(user_id, total_price, message.text, data, cart_items)

        if order_id:
            success_msg = (
                f"🎉 **Замовлення #{order_id} успішно оформлено!**\n\n"
                f"👤 {data['name']}\n"
                f"📍 {data['address']}\n"
                f"💰 **{total_price} грн**\n\n"
                "👌 Ми вже готуємо! Чекайте на повідомлення від кур'єра, коли він буде під'їжджати."
            )

            # Поважаємо роль, яку вибрав користувач!
            saved_role = db.get_user_current_role(user_id)
            from bot.handlers.start import _get_role_keyboard
            markup = _get_role_keyboard(user_id)
            
            bot.send_message(message.chat.id, success_msg, reply_markup=markup, parse_mode='Markdown')

            if ADMIN_ID:
                cart_details = "\n".join([f"• {i['name']} x{i['quantity']}" for i in cart_items])
                admin_msg = (
                    f"🔥 **НОВЕ ЗАМОВЛЕННЯ #{order_id}**\n\n"
                    f"👤 {data['name']}\n"
                    f"📞 `{data['contact']}`\n"
                    f"📍 {data['address']}\n"
                    f"💰 **{total_price} грн** ({message.text})\n\n"
                    f"🛒 **Кошик:**\n{cart_details}"
                )
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("✅ Прийняти", callback_data=f"admin_accept_{order_id}"))
                markup.add(InlineKeyboardButton("❌ Скасувати", callback_data=f"admin_cancel_{order_id}"))

                try:
                    bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Failed to send admin notification: {e}")

            db.clear_cart(user_id)
            db.clear_user_state(user_id)
        else:
            bot.reply_to(message, "❌ Помилка сервера. Спробуйте пізніше.", reply_markup=keyboards.get_main_keyboard())
