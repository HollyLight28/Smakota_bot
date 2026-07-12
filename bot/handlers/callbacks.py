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
from bot.utils import logger, format_cart_message, clean_phone, get_maps_url, escape_md
import database as db
import keyboards


@bot.callback_query_handler(func=lambda call: not call.data.startswith('checkout'))
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data

    try:
        # === Role Switching Callbacks ===
        if data.startswith("set_role_"):
            if user_id != ADMIN_ID: return
            
            role = data.replace("set_role_", "")
            
            # Зберігаємо роль в базі для залізної пам'яті
            db.set_user_current_role(user_id, role)
            db.clear_user_state(user_id) # ОЧИЩАЄМО ЗОМБІ-СЕРЕДОВИЩЕ
            
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
            elif role == "kitchen":
                if not any(c['chat_id'] == user_id for c in db.get_chefs()):
                    db.add_chef(f"Кухар_{call.from_user.first_name}", user_id)
                bot.edit_message_text("👩‍🍳 Інтерфейс змінено на **Кухня**.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
                bot.send_message(user_id, "Панель кухні:", reply_markup=keyboards.get_kitchen_keyboard())
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

        # === Shopping List Callbacks (legacy) ===
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

        # === Active Shopping List (inline product selection) ===
        elif data.startswith("shop_dept_"):
            dept_id = data.replace("shop_dept_", "")
            products = db.get_products_by_department(dept_id)
            if not products:
                bot.answer_callback_query(call.id, "❌ Немає продуктів у цьому цеху")
                return
            markup = InlineKeyboardMarkup(row_width=1)
            for p in products:
                markup.add(InlineKeyboardButton(
                    f"{p['name']} ({p['unit']})",
                    callback_data=f"shop_prod_{p['id']}"
                ))
            markup.add(InlineKeyboardButton("🔙 Назад до цехів", callback_data="shop_back"))
            bot.edit_message_text(
                f"📋 **Продукти:**\nОбери продукт, щоб додати кількість:",
                call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown'
            )

        elif data.startswith("shop_prod_"):
            prod_id = int(data.replace("shop_prod_", ""))
            prod = db.get_shopping_product_by_id(prod_id)
            if not prod:
                bot.answer_callback_query(call.id, "❌ Продукт не знайдено")
                return
            markup = InlineKeyboardMarkup(row_width=3)
            markup.row(
                InlineKeyboardButton("+1", callback_data=f"shop_qty_{prod_id}_+1"),
                InlineKeyboardButton("+0.5", callback_data=f"shop_qty_{prod_id}_+0.5"),
                InlineKeyboardButton("+5", callback_data=f"shop_qty_{prod_id}_+5")
            )
            bot.edit_message_text(
                f"{prod['name']}\nСкільки додати?",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )

        elif data.startswith("shop_qty_"):
            parts = data.split("_")
            prod_id = int(parts[2])
            qty_str = parts[3]  # e.g. "+1", "+0.5", "+5"
            try:
                qty = float(qty_str)
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Невірна кількість")
                return
            prod = db.get_shopping_product_by_id(prod_id)
            if not prod:
                bot.answer_callback_query(call.id, "❌ Продукт не знайдено")
                return
            db.add_to_active_shopping_list(prod_id, qty, call.from_user.id)
            bot.answer_callback_query(call.id, f"✅ Додано: {prod['name']}")

        elif data == "shop_back":
            depts = db.get_departments()
            markup = InlineKeyboardMarkup(row_width=1)
            for d in depts:
                markup.add(InlineKeyboardButton(d['name'], callback_data=f"shop_dept_{d['id']}"))
            markup.add(InlineKeyboardButton("✅ Готово (до Шефа)", callback_data="shop_done"))
            bot.edit_message_text(
                "📋 **Список закупів**\nОбери цех:",
                call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown'
            )

        elif data == "shop_done":
            items = db.get_active_shopping_list()
            if not items:
                bot.edit_message_text(
                    "✅ Список порожній. Додай продукти через цехи.",
                    call.message.chat.id, call.message.message_id
                )
                return
            msg = "📋 **Список закупів сформовано!**\n\n"
            for i in items:
                status = "✅" if i['is_purchased'] else "⬜"
                msg += f"{status} {i['name']} — {i['quantity']}\n"
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

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
            is_staff = (user_id == ADMIN_ID) or (state_info and state_info['state'] in ['hall_picking_items', 'admin_batch_building'])
            
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
            is_staff = (user_id == ADMIN_ID) or (state_info and state_info['state'] in ['hall_picking_items'])
            
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

        elif data.startswith("pay_cash_") or data.startswith("pay_card_"):
            _handle_finalize_payment(call, user_id, data)

        elif data.startswith("admin_sched_"):
            # Шеф хоче відкласти замовлення
            order_id = data.split("_")[2]
            db.set_user_state(user_id, 'admin_setting_time', {'order_id': order_id})
            bot.send_message(user_id, "⏳ **Введіть час доставки** (наприклад, 18:30):", reply_markup=keyboards.get_checkout_cancel_keyboard(), parse_mode='Markdown')
            bot.answer_callback_query(call.id)
            return

        # === Shopping List Admin Callbacks (Шеф) ===
        if data.startswith("shop_buy_") or data == "shop_clear":
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Доступно тільки Шефу")
                return

            if data.startswith("shop_buy_"):
                list_id = int(data.replace("shop_buy_", ""))
                db.mark_as_purchased(list_id)
                bot.answer_callback_query(call.id, "✅ Позначено як куплено!")
                items = db.get_active_shopping_list()
                markup = InlineKeyboardMarkup(row_width=1)
                msg_text = "📋 **Список закупів**\n\n"
                for item in items:
                    status_icon = "✅" if item['is_purchased'] else "⬜"
                    msg_text += f"{status_icon} **{item['name']}** — {item['quantity']}\n"
                    if not item['is_purchased']:
                        markup.add(InlineKeyboardButton(
                            f"✅ Куплено: {item['name']}",
                            callback_data=f"shop_buy_{item['id']}"
                        ))
                if items:
                    markup.add(InlineKeyboardButton("🔄 Очистити список", callback_data="shop_clear"))
                bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

            elif data == "shop_clear":
                db.clear_todays_list()
                bot.edit_message_text("✅ Список закупів очищено.", call.message.chat.id, call.message.message_id)
                bot.answer_callback_query(call.id, "🧹 Список очищено!")
            return

    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, "⚠️ Виникла помилка.")
        except Exception:
            pass  # Callback вже протух — ігноруємо




# === Admin Order helpers ===
def _handle_admin_accept(call, user_id, data):
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
        return

    order_id = data.split("_")[2]
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 ГОТУВАТИ ОДРАЗУ", callback_data=f"admin_accept_now_{order_id}"))
    markup.add(InlineKeyboardButton("⏰ ПРИЙНЯТИ НА ЧАС", callback_data=f"admin_sched_{order_id}"))

    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id,
        text=f"👨‍🍳 **Замовлення #{order_id}**\nОберіть режим роботи:",
        reply_markup=markup, 
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_accept_now_"))
def _handle_admin_accept_now(call):
    """Швидке прийняття — вибір кур'єра."""
    user_id = call.from_user.id
    order_id = call.data.split("_")[3]
    
    couriers = db.get_couriers()
    if not couriers:
        bot.answer_callback_query(call.id, "⚠️ Немає кур'єрів!", show_alert=True)
        return

    markup = InlineKeyboardMarkup()
    for c in couriers:
        # Показуємо касу кур'єра в дужках як я обіцяв! 💰
        res = db.get_daily_report(c['chat_id'])
        c_cash = res[1] if res else 0
        markup.add(InlineKeyboardButton(f"🛵 {c['name']} ({c_cash} грн)", callback_data=f"assign_{order_id}_{c['chat_id']}"))

    bot.edit_message_text(f"🚀 **Замовлення #{order_id} прийнято.**\nПризначте кур'єра:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')


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
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО", callback_data=f"courier_delivered_{order_id}"))

        address = order['delivery_address']
        maps_url = get_maps_url(address)
        raw_phone = str(order['delivery_phone'])

        markup.add(
            InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url)
        )

        msg = (
            f"📍 *АДРЕСА: {escape_md(order['delivery_address']).upper()}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 *Телефон:* {raw_phone}\n"
            f"👤 *Клієнт:* {escape_md(order['delivery_name'])}\n"
            f"💰 *Сума:* {order['total_amount']} грн ({escape_md(order['payment_method'])})\n"
            f"📝 *Коментар:* {escape_md(order['comment']) if order['comment'] else '---'}\n"
            f"📦 *Замовлення:* #{order['id']}"
        )
        bot.send_message(courier_id, msg, reply_markup=markup, parse_mode='Markdown')

        # TODO: Додати кнопку "Буду за 5 хвилин" для кур'єра, яка надсилатиме повідомлення клієнту

    except Exception as e:
        logger.error(f"Failed to notify courier: {e}")


def _handle_courier_delivered(call, user_id, data):
    order_id = data.split("_")[2]
    order = db.get_order_by_id(order_id)

    if not order or user_id != order['courier_id']:
        bot.answer_callback_query(call.id, "⛔ Ви не є кур'єром цього замовлення", show_alert=True)
        return

    # Замість миттєвого закриття — питаємо про гроші
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💵 ГОТІВКА", callback_data=f"pay_cash_{order_id}"),
        InlineKeyboardButton("💳 НА КАРТУ", callback_data=f"pay_card_{order_id}")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id,
        text=f"💰 **Замовлення #{order_id}**\n📍 {order['delivery_address']}\n\n**Оберіть, як розрахувався клієнт:**",
        reply_markup=markup,
        parse_mode='Markdown'
    )

def _handle_finalize_payment(call, user_id, data):
    """Фінальне закриття замовлення з підтвердженим способом оплати."""
    method_key = "pay_cash_" if "pay_cash_" in data else "pay_card_"
    order_id = data.replace(method_key, "")
    payment_method = "💵 Готівка" if method_key == "pay_cash_" else "💳 На карту"
    
    order = db.get_order_by_id(order_id)
    if not order: return

    # Оновлюємо статус та ФАКТИЧНИЙ спосіб оплати
    db.update_order_status(order_id, 'completed')
    conn = db.get_db_connection()
    conn.execute('UPDATE orders SET payment_method = ?, cash_confirmed = 1 WHERE id = ?', (payment_method, order_id))
    conn.commit()

    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id,
        text=f"✅ **Замовлення #{order_id} закрито!**\nРозрахунок: {payment_method}\n\nГарна робота, шеф задоволений! 😎",
        parse_mode='Markdown'
    )

    # Сповіщення клієнту
    try:
        bot.send_message(order['user_id'], f"🏁 **Смачного!** Замовлення #{order_id} доставлено.\nБудемо раді вашим новим замовленням! ❤️", parse_mode='Markdown')
    except Exception: pass

    # Сповіщення Адміну
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🏁 **Замовлення #{order_id} завершено.**\nКур'єр: {call.from_user.first_name}\nСума: {order['total_amount']} грн ({payment_method})", parse_mode='Markdown')
        except Exception: pass
