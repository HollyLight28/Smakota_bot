"""
Обробник ВСІХ callback_query (Inline кнопки).
Це найбільший хендлер, який розруліює натискання inline-кнопок.
"""
import re
import time
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger, format_cart_message, clean_phone, get_maps_url
import database as db
import keyboards


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data

    try:
        # === Role Switching Callbacks ===
        if data.startswith("set_role_"):
            if user_id != ADMIN_ID: return
            
            role = data.replace("set_role_", "")
            
            # Для ШЕФА (ADMIN_ID) ми НЕ видаляємо дані з бази, 
            # щоб не втрачати замовлення та статус зміни.
            # Ми просто змінюємо КНОПКИ (інтерфейс).
            
            if role == "admin":
                bot.edit_message_text("👑 Інтерфейс змінено на **Адмін (Шеф)**.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
                bot.send_message(user_id, "Твоя майстер-панель:", reply_markup=keyboards.get_admin_keyboard())
            elif role == "courier":
                # Перевіряємо чи вже є в базі, якщо немає - додаємо
                if not any(c['chat_id'] == user_id for c in db.get_couriers()):
                    db.add_courier(f"Шеф_{call.from_user.first_name}", user_id)
                bot.edit_message_text("🛵 Інтерфейс змінено на **Кур'єр**.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
                bot.send_message(user_id, "Панель кур'єра (твої замовлення на місці):", reply_markup=keyboards.get_courier_keyboard())
            elif role == "hall":
                if not any(h['chat_id'] == user_id for h in db.get_hall_staff()):
                    db.add_hall_staff(f"Шеф_{call.from_user.first_name}", user_id)
                bot.edit_message_text("💃 Інтерфейс змінено на **Зал (Наташа)**.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
                bot.send_message(user_id, "Панель залу:", reply_markup=keyboards.get_hall_staff_keyboard())
            elif role == "client":
                bot.edit_message_text("👤 Інтерфейс змінено на **Клієнт**.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
                bot.send_message(user_id, "Бачиш бота як звичайний покупець.", reply_markup=keyboards.get_client_keyboard())
            return

        # === Admin Batch & Mailing ===
        if data.startswith(("adm_sel_", "adm_create_route", "adm_assign_", "mail_")):
            if user_id != ADMIN_ID:
                return

            state_info = db.get_user_state(user_id)
            selected_ids = state_info['data'].get('selected_ids', []) if state_info and state_info['state'] == 'admin_batch_building' else []

            if data.startswith("adm_sel_"):
                order_id = int(data.split("_")[2])
                if order_id not in selected_ids:
                    selected_ids.append(order_id)
                    db.set_user_state(user_id, 'admin_batch_building', {'selected_ids': selected_ids})
                    bot.answer_callback_query(call.id, f"Додано #{order_id} (Поз: {len(selected_ids)})")
                    try:
                        conn = db.get_db_connection()
                        orders = conn.execute('SELECT * FROM orders WHERE status = "new"').fetchall()
                        markup = InlineKeyboardMarkup()
                        for order in orders:
                            prefix = "📍"
                            if order['id'] in selected_ids:
                                idx = selected_ids.index(order['id']) + 1
                                prefix = f"{idx}."
                            markup.add(InlineKeyboardButton(f"{prefix} {order['delivery_address']}", callback_data=f"adm_sel_{order['id']}"))
                        markup.add(InlineKeyboardButton(f"🚀 Сформувати ({len(selected_ids)})", callback_data="adm_create_route"))
                        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
                    except Exception:
                        pass
                else:
                    bot.answer_callback_query(call.id, "Вже у списку!")
                return

            elif data == "adm_create_route":
                if not selected_ids:
                    bot.answer_callback_query(call.id, "Спершу оберіть замовлення!", show_alert=True)
                    return
                conn = db.get_db_connection()
                couriers = conn.execute('SELECT * FROM couriers WHERE shift_status = "on"').fetchall()
                if not couriers:
                    bot.answer_callback_query(call.id, "❌ Немає кур'єрів на зміні!", show_alert=True)
                    return
                markup = InlineKeyboardMarkup()
                for c in couriers:
                    markup.add(InlineKeyboardButton(f"🛵 {c['name']}", callback_data=f"adm_assign_{c['chat_id']}"))
                bot.edit_message_text(
                    f"🚀 **Маршрут сформовано ({len(selected_ids)} замовлень).**\nКому передаємо?",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=markup, parse_mode='Markdown'
                )
                return

            elif data.startswith("adm_assign_"):
                courier_id = int(data.split("_")[2])
                batch_id = db.create_route_batch(courier_id, selected_ids)
                if batch_id:
                    bot.edit_message_text(
                        f"✅ **Успішно!** {len(selected_ids)} замовлень передано кур'єру.",
                        call.message.chat.id, call.message.message_id
                    )
                    db.clear_user_state(user_id)
                    conn = db.get_db_connection()
                    batch_orders = conn.execute(
                        'SELECT * FROM orders WHERE batch_id = ? ORDER BY route_order ASC',
                        (batch_id,)
                    ).fetchall()
                    summary = f"🚀 **НОВИЙ МАРШРУТ (#{batch_id})**\n━━━━━━━━━━━━━━\n"
                    for o in batch_orders:
                        summary += f"{o['route_order']}. 📍 {o['delivery_address'].upper()}\n"
                    bot.send_message(
                        courier_id,
                        summary + "\nДеталі доступні в кнопці 'Мої доставки'.",
                        reply_markup=keyboards.get_courier_keyboard(),
                        parse_mode='Markdown'
                    )
                return

            # --- Mailing callbacks ---
            elif data == "mail_new":
                db.set_user_state(user_id, 'mail_waiting_text')
                bot.edit_message_text("📝 **Введіть текст розсилки:**", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
                return
            elif data == "mail_list":
                conn = db.get_db_connection()
                templates = conn.execute('SELECT * FROM mailing_templates').fetchall()
                if not templates:
                    bot.answer_callback_query(call.id, "Шаблонів немає", show_alert=True)
                    return
                markup = InlineKeyboardMarkup()
                for t in templates:
                    markup.add(InlineKeyboardButton(f"📄 {t['name']}", callback_data=f"mail_view_{t['id']}"))
                bot.edit_message_text("📋 **Ваші шаблони:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                return
            elif data.startswith("mail_view_"):
                t_id = data.split("_")[2]
                conn = db.get_db_connection()
                t = conn.execute('SELECT * FROM mailing_templates WHERE id = ?', (t_id,)).fetchone()
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🚀 ЗАПУСТИТИ", callback_data=f"mail_send_{t_id}"))
                markup.add(InlineKeyboardButton("🗑️ Видалити", callback_data=f"mail_del_{t_id}"))
                markup.add(InlineKeyboardButton("🔙 Назад", callback_data="mail_list"))
                bot.edit_message_text(f"📄 **Шаблон: {t['name']}**\n\n{t['content']}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                return
            elif data.startswith("mail_send_"):
                t_id = data.split("_")[2]
                conn = db.get_db_connection()
                t = conn.execute('SELECT * FROM mailing_templates WHERE id = ?', (t_id,)).fetchone()
                users = conn.execute('SELECT chat_id FROM users').fetchall()
                count = 0
                for u in users:
                    try:
                        bot.send_message(u['chat_id'], t['content'], parse_mode='Markdown')
                        count += 1
                        time.sleep(0.05)
                    except Exception:
                        pass
                bot.answer_callback_query(call.id, f"✅ Відправлено {count} користувачам!", show_alert=True)
                return
            elif data.startswith("mail_del_"):
                t_id = data.split("_")[2]
                conn = db.get_db_connection()
                conn.execute('DELETE FROM mailing_templates WHERE id = ?', (t_id,))
                conn.commit()
                bot.answer_callback_query(call.id, "Видалено")
                # Refresh the mailing list inline
                templates = conn.execute('SELECT * FROM mailing_templates').fetchall()
                if templates:
                    markup = InlineKeyboardMarkup()
                    for t in templates:
                        markup.add(InlineKeyboardButton(f"📄 {t['name']}", callback_data=f"mail_view_{t['id']}"))
                    bot.edit_message_text("📋 **Ваші шаблони:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                else:
                    bot.edit_message_text("📋 Шаблонів немає.", call.message.chat.id, call.message.message_id)
                return

        # === Hall Staff Callbacks ===
        elif data.startswith("hall_close_"):
            order_id = int(data.split("_")[2])
            db.update_order_status(order_id, 'completed')
            bot.answer_callback_query(call.id, "✅ Чек закрито! Гроші додано в касу.")
            bot.edit_message_text(f"🏁 **Чек #{order_id} закрито.** Оплата отримана.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            return

        # === Shopping List Callbacks ===
        elif data.startswith("buy_item_"):
            item_id = int(data.split("_")[2])
            db.delete_shopping_item(item_id)
            bot.answer_callback_query(call.id, "✅ Видалено зі списку!")
            # Refresh list
            items = db.get_shopping_list()
            if not items:
                bot.edit_message_text("✅ **Список порожній.** Все є в наявності!", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            else:
                msg = "🛒 **Список закупів для Шефа:**\n\n"
                markup = InlineKeyboardMarkup()
                for item in items:
                    msg += f"• {item['item_name']} — {item['quantity']}\n"
                    markup.add(InlineKeyboardButton(f"✅ Куплено: {item['item_name']}", callback_data=f"buy_item_{item['id']}"))
                bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
            return

        # === Shift Control ===
        if data == "shift_on":
            conn = db.get_db_connection()
            conn.execute('UPDATE couriers SET shift_status = "on" WHERE chat_id = ?', (user_id,))
            conn.commit()
            bot.edit_message_text("✅ **Зміну розпочато!** Тепер ви відображаєтесь у шефа.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            return
        elif data == "shift_off":
            conn = db.get_db_connection()
            conn.execute('UPDATE couriers SET shift_status = "off" WHERE chat_id = ?', (user_id,))
            conn.commit()
            bot.edit_message_text("🔌 **Зміну завершено.** Гарного відпочинку!", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            return

        # === Monitoring Callbacks ===
        if data.startswith("mon_courier_"):
            if user_id != ADMIN_ID:
                return

            courier_id_to_check = int(data.split("_")[2])
            today = datetime.now().strftime('%Y-%m-%d')
            conn = db.get_db_connection()

            courier_info = conn.execute("SELECT name FROM couriers WHERE chat_id = ?", (courier_id_to_check,)).fetchone()
            safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(courier_info['name'])) if courier_info else "Невідомий"

            orders = conn.execute("""
                SELECT * FROM orders
                WHERE courier_id = ? AND date(created_at) = ?
                ORDER BY CASE status WHEN 'delivery' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END,
                         CASE WHEN route_order IS NULL THEN 999 ELSE route_order END
            """, (courier_id_to_check, today)).fetchall()

            if not orders:
                bot.answer_callback_query(call.id, f"У кур'єра {safe_name} сьогодні не було замовлень.", show_alert=True)
                return

            msg = f"**Детальний звіт по {safe_name} (сьогодні):**\n\n"
            for order in orders:
                if order['status'] == 'delivery':
                    status_emoji = "📦"
                elif order['status'] == 'completed':
                    status_emoji = "✅"
                else:
                    status_emoji = "❓"
                route_prefix = f"#{order['route_order']} " if order['route_order'] else ""
                msg += f"{status_emoji} {route_prefix}{order['delivery_address']} ({order['total_amount']} грн)\n"

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад до моніторингу", callback_data="mon_back"))
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
            return

        elif data == "mon_back":
            if user_id != ADMIN_ID:
                return

            # Re-generate monitoring list instead of calling admin_show_monitoring
            couriers = db.get_couriers()
            today = datetime.now().strftime('%Y-%m-%d')
            conn = db.get_db_connection()

            msg = "📊 **Моніторинг кур'єрів (сьогодні):**\n\n"
            markup = InlineKeyboardMarkup()
            for c in couriers:
                active = conn.execute('SELECT COUNT(*) as count FROM orders WHERE courier_id = ? AND status = "delivery"', (c['chat_id'],)).fetchone()['count']
                completed = conn.execute('SELECT COUNT(*) as count FROM orders WHERE courier_id = ? AND status = "completed" AND date(created_at) = ?', (c['chat_id'], today)).fetchone()['count']
                status_emoji = "✅" if c['shift_status'] == 'on' else "🔌"
                safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(c['name']))
                msg += f"{status_emoji} **{safe_name}** | В дорозі: `{active}` | Завершено: `{completed}`\n"
                markup.add(InlineKeyboardButton(f"🔎 Деталі по {safe_name}", callback_data=f"mon_courier_{c['chat_id']}"))

            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
            return

        # === Category Navigation ===
        if data.startswith("category_"):
            # Перевіряємо, чи це стафф (Адмін або Наташа)
            state_info = db.get_user_state(user_id)
            is_staff = (user_id == ADMIN_ID) or (state_info and state_info['state'] in ['dispatcher_picking_items', 'hall_picking_items', 'admin_batch_building'])
            
            if not is_staff:
                bot.answer_callback_query(call.id, "🛒 Будь ласка, використовуйте сайт для замовлення!", show_alert=True)
                return

            category_id = data.split("_")[1]
            category_name = db.get_category_name_by_id(category_id)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"🍽️ **Категорія: {category_name}**\n\n_Натисніть на страву, щоб додати її в кошик._",
                    reply_markup=keyboards.get_items_keyboard(category_id),
                    parse_mode='Markdown'
                )
            except Exception:
                bot.answer_callback_query(call.id)

        elif data == "back_to_categories" or data == "show_menu":
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text="📂 **Оберіть категорію:**",
                    reply_markup=keyboards.get_categories_keyboard(),
                    parse_mode='Markdown'
                )
            except Exception:
                bot.answer_callback_query(call.id)

        # === Item Actions ===
        elif data.startswith("item_"):
            item_id = int(data.split("_")[1])
            item = db.get_item_by_id(item_id)
            if not item: return

            # ШВИДКЕ ДОДАВАННЯ ДЛЯ ПЕРСОНАЛУ (БЕЗ ФОТО)
            state_info = db.get_user_state(user_id)
            is_staff = (user_id == ADMIN_ID) or (state_info and state_info['state'] in ['dispatcher_picking_items', 'hall_picking_items'])
            
            if is_staff:
                db.add_to_cart(user_id, item_id)
                bot.answer_callback_query(call.id, f"✅ Додано: {item['name']}")
                # Ми не видаляємо список страв, щоб можна було клацати далі
                return

            # Якщо раптом клієнт сюди потрапив - шлемо на сайт
            bot.answer_callback_query(call.id, "🛒 Використовуйте 'ВІДКРИТИ МЕНЮ' для замовлення!", show_alert=True)

        elif data.startswith("add_to_cart_"):
            parts = data.split("_")
            if len(parts) >= 4:
                item_id = int(parts[3])
                item = db.get_item_by_id(item_id)
                if item:
                    db.add_to_cart(user_id, item_id)
                    bot.answer_callback_query(call.id, f"✅ {item['name']} додано у кошик!")
                else:
                    bot.answer_callback_query(call.id, "❌ Страву не знайдено.")
            else:
                bot.answer_callback_query(call.id, "⚠️ Помилка формату даних.")

        # === Cart Actions ===
        elif data.startswith("cart_plus_"):
            item_id = int(data.split("_")[2])
            db.update_cart_quantity(user_id, item_id, 1)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException:
                pass

        elif data.startswith("cart_minus_"):
            item_id = int(data.split("_")[2])
            db.update_cart_quantity(user_id, item_id, -1)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException:
                pass

        elif data.startswith("cart_remove_"):
            item_id = int(data.split("_")[2])
            db.remove_from_cart(user_id, item_id)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException:
                pass

        elif data == "clear_cart":
            db.clear_cart(user_id)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text="🗑️ **Кошик очищено!**",
                    reply_markup=keyboards.get_empty_cart_keyboard(),
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException:
                pass

        # === Checkout Start ===
        elif data == "checkout":
            _handle_checkout_start(call, user_id)

        elif data == "noop":
            bot.answer_callback_query(call.id)

        # === Admin Order Management ===
        elif data.startswith("admin_accept_"):
            _handle_admin_accept(call, user_id, data)

        elif data.startswith("admin_cancel_"):
            _handle_admin_cancel(call, user_id, data)

        elif data.startswith("assign_"):
            _handle_assign_courier(call, user_id, data)

        elif data.startswith("courier_delivered_"):
            _handle_courier_delivered(call, user_id, data)

    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, "⚠️ Виникла помилка.")
        except Exception:
            pass  # Callback вже протух — ігноруємо


# === Checkout start helper ===
def _handle_checkout_start(call, user_id):
    """Обробка початку оформлення замовлення через inline-кнопку."""
    _, total, _ = format_cart_message(user_id)
    if total == 0:
        bot.answer_callback_query(call.id, "Кошик порожній!", show_alert=True)
        return

    dispatchers = db.get_dispatchers()
    is_dispatcher = any(d['chat_id'] == user_id for d in dispatchers) or user_id == ADMIN_ID

    hall_staff = db.get_hall_staff()
    is_hall = any(h['chat_id'] == user_id for h in hall_staff)

    if is_hall:
        # Наташа: швидке оформлення without delivery
        cart_items = db.get_cart_items(user_id)
        total = sum(item['price'] * item['quantity'] for item in cart_items)
        order_id = db.create_order(user_id, total, "💵 Каса (ЗАЛ)", {'name': 'Зал', 'address': 'В закладі'}, cart_items)
        if order_id:
            conn = db.get_db_connection()
            conn.execute('UPDATE orders SET hall_staff_id = ? WHERE id = ?', (user_id, order_id))
            conn.commit()
            db.clear_cart(user_id)
            db.clear_user_state(user_id)

            receipt = f"🎫 **ЧЕК #{order_id} (ЗАЛ)**\n"
            receipt += "----------------------------\n"
            for item in cart_items:
                receipt += f"• {item['name']} x{item['quantity']}\n"
            receipt += "----------------------------\n"
            receipt += f"💰 **ВСЬОГО до сплати: {total} грн**\n\n"
            receipt += "📢 Покажіть цей чек на кухні."

            bot.send_message(call.message.chat.id, receipt, reply_markup=keyboards.get_hall_staff_keyboard(), parse_mode='Markdown')
            if ADMIN_ID:
                bot.send_message(ADMIN_ID, f"🆕 **Нове замовлення із ЗАЛУ (#{order_id})**\nСума: {total} грн")
        return

    if is_dispatcher:
        db.set_user_state(user_id, 'manual_checkout_name')
        bot.send_message(
            call.message.chat.id,
            "📞 **Оформлення РУЧНОГО замовлення**\n\nЯк звати клієнта?",
            reply_markup=keyboards.get_checkout_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return

    # Normal client checkout
    last_order = db.get_last_order(user_id)
    if last_order:
        db.set_user_state(user_id, 'checkout_use_history', {'history': dict(last_order)})
        bot.send_message(
            call.message.chat.id,
            f"📝 **Знайдено ваші минулі дані:**\n\n"
            f"👤 {last_order['delivery_name']}\n📞 {last_order['delivery_phone']}\n📍 {last_order['delivery_address']}\n\n"
            "Бажаєте використати їх знову?",
            reply_markup=keyboards.get_use_previous_data_keyboard(),
            parse_mode='Markdown'
        )
    else:
        db.set_user_state(user_id, 'checkout_name')
        bot.send_message(
            call.message.chat.id,
            "📝 **Оформлення замовлення**\n\nЯк до вас звертатися? (Введіть ім'я)",
            reply_markup=keyboards.get_checkout_cancel_keyboard(),
            parse_mode='Markdown'
        )


# === Admin Order helpers ===
def _handle_admin_accept(call, user_id, data):
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
        return

    order_id = data.split("_")[2]
    couriers = db.get_couriers()

    if not couriers:
        bot.answer_callback_query(call.id, "⚠️ Немає кур'єрів! Використайте /add_courier", show_alert=True)
        return

    markup = InlineKeyboardMarkup()
    for courier in couriers:
        markup.add(InlineKeyboardButton(f"🛵 {courier['name']}", callback_data=f"assign_{order_id}_{courier['chat_id']}"))

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=f"✅ **Замовлення #{order_id} прийнято.**\nОберіть кур'єра для доставки:",
            reply_markup=markup, parse_mode='Markdown'
        )
    except telebot.apihelper.ApiTelegramException:
        pass

    order = db.get_order_by_id(order_id)
    if order:
        try:
            bot.send_message(order['user_id'], f"👨‍🍳 **Ваше замовлення #{order_id} прийнято!**\nГотуємо смакоту. Скоро передамо кур'єру.", parse_mode='Markdown')
        except Exception as e:
            logger.warning(f"Failed to notify user: {e}")


def _handle_admin_cancel(call, user_id, data):
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
        return

    order_id = data.split("_")[2]
    db.update_order_status(order_id, 'cancelled')
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=f"❌ **Замовлення #{order_id} СКАСОВАНО.**", parse_mode='Markdown'
        )
    except telebot.apihelper.ApiTelegramException:
        pass

    order = db.get_order_by_id(order_id)
    if order:
        try:
            bot.send_message(order['user_id'], f"❌ **Замовлення #{order_id} скасовано.**\nЗв'яжіться з нами для уточнення деталей.", parse_mode='Markdown')
        except Exception:
            pass


def _handle_assign_courier(call, user_id, data):
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
        return

    _, order_id, courier_id = data.split("_")
    db.assign_courier(order_id, int(courier_id))

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=f"🛵 **Замовлення #{order_id} передано кур'єру.**", parse_mode='Markdown'
        )
    except telebot.apihelper.ApiTelegramException:
        pass

    try:
        order = db.get_order_by_id(order_id)
        courier_markup = InlineKeyboardMarkup()
        courier_markup.add(InlineKeyboardButton("✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО", callback_data=f"courier_delivered_{order_id}"))

        address = order['delivery_address']
        maps_url = get_maps_url(address)
        raw_phone = str(order['delivery_phone'])
        phone = clean_phone(raw_phone)

        courier_markup.add(
            InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url),
            InlineKeyboardButton("📞 Зателефонувати", url=f"tel:{phone}")
        )

        msg = (
            f"📍 **АДРЕСА: {order['delivery_address'].upper()}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 **Телефон:** `{raw_phone}`\n"
            f"👤 **Клієнт:** {order['delivery_name']}\n"
            f"💰 **Сума:** {order['total_amount']} грн ({order['payment_method']})\n"
            f"📝 **Коментар:** {order['comment'] if order['comment'] else '---'}\n"
            f"📦 **Замовлення:** #{order['id']}"
        )
        bot.send_message(courier_id, msg, reply_markup=courier_markup, parse_mode='Markdown')

        bot.send_message(order['user_id'], f"🛵 **Кур'єр вже в дорозі!**\nОчікуйте доставку на адресу: **{order['delivery_address']}**", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Failed to notify courier: {e}")


def _handle_courier_delivered(call, user_id, data):
    order_id = data.split("_")[2]
    order = db.get_order_by_id(order_id)

    if not order or user_id != order['courier_id']:
        bot.answer_callback_query(call.id, "⛔ Ви не є призначеним кур'єром для цього замовлення", show_alert=True)
        return

    db.update_order_status(order_id, 'completed')

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=f"✅ **Замовлення #{order_id} доставлено!**\nГарна робота!", parse_mode='Markdown'
        )
    except telebot.apihelper.ApiTelegramException:
        pass

    if order:
        try:
            bot.send_message(order['user_id'], f"🏁 **Замовлення #{order_id} доставлено!**\nСмачного! Чекаємо на вас знову.", parse_mode='Markdown')
        except Exception:
            pass

    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🏁 Замовлення #{order_id} успішно доставлено.")
        except Exception:
            pass
