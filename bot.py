import telebot
import os
import logging
import re
import urllib.parse
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
import database as db
import keyboards
import threading
from update_menu_gs import update_menu_from_json

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env file")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Enable logging to file and stream
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("smakota_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def format_cart_message(user_id):
    """Formats the cart message and keyboard."""
    cart_items = db.get_cart_items(user_id)
    if not cart_items:
        return "🛒 **Ваш кошик порожній**\n\nОберіть щось смачненьке з меню!", 0, keyboards.get_empty_cart_keyboard()
    
    total = 0
    markup = InlineKeyboardMarkup()
    
    message = "🛒 **Ваше замовлення:**\n\n"
    
    for i, item in enumerate(cart_items, 1):
        item_total = item['price'] * item['quantity']
        total += item_total
        message += f"{i}. **{item['name']}**\n   {item['quantity']} шт. x {item['price']} = {item_total} грн\n"
        
        # Ultra-compact row: [Number + Qty] [Minus] [Plus]
        markup.add(
            InlineKeyboardButton(f"{i}. ({item['quantity']} шт)", callback_data="noop"),
            InlineKeyboardButton("➖", callback_data=f"cart_minus_{item['id']}"),
            InlineKeyboardButton("➕", callback_data=f"cart_plus_{item['id']}")
        )

    message += f"\n💰 **Загалом: {total} грн**"
    
    # Add main action buttons
    markup.add(
        InlineKeyboardButton("✅ Оформити", callback_data="checkout"),
        InlineKeyboardButton("🗑️ Очистити", callback_data="clear_cart")
    )
    markup.add(InlineKeyboardButton("🍕 До меню", callback_data="show_menu"))
    
    return message, total, markup

# --- WebApp Data Handler ---

@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    user_id = message.from_user.id
    try:
        import json
        data = json.loads(message.web_app_data.data)
        
        if data.get('action') == 'webapp_order':
            items = data.get('items', {})
            
            if not items:
                bot.send_message(message.chat.id, "🛒 Ваш кошик порожній.")
                return
            
            # Clear current cart and add items from WebApp
            db.clear_cart(user_id)
            
            order_summary = "🛒 **Ви обрали в меню:**\n\n"
            for item_id, info in items.items():
                db.add_to_cart(user_id, int(item_id), info['count'])
                order_summary += f"• {info['name']} x{info['count']} — {info['price'] * info['count']} грн\n"
            
            cart_text, total, cart_markup = format_cart_message(user_id)
            bot.send_message(message.chat.id, f"✅ **Товари додано до кошика!**\n\n{order_summary}\n💰 **Разом: {total} грн**", reply_markup=cart_markup, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error processing WebApp data: {e}")
        bot.send_message(message.chat.id, "❌ Сталася помилка при обробці замовлення з меню.")

# --- Message Handlers ---

@bot.message_handler(commands=['add_hall_staff'])
def register_hall_staff(message):
    """Admin command: /add_hall_staff NAME CHAT_ID"""
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Використання: `/add_hall_staff Наталка ChatID`", parse_mode='Markdown')
            return
        db.add_hall_staff(parts[1], int(parts[2]))
        bot.reply_to(message, f"✅ Наталка {parts[1]} додана!")
    except Exception as e: bot.reply_to(message, f"❌ Помилка: {e}")

@bot.message_handler(commands=['remove_me'])
def remove_me_from_roles(message):
    """Self-remove from all roles for testing."""
    db.remove_user_from_roles(message.from_user.id)
    bot.reply_to(message, "🔌 Вас видалено з усіх ролей. Натисніть /start, щоб стати звичайним клієнтом.")

@bot.message_handler(commands=['add_dispatcher'])
def register_dispatcher(message):
    """Admin command: /add_dispatcher NAME CHAT_ID"""
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Використання: `/add_dispatcher Ім'я ChatID`", parse_mode='Markdown')
            return

        name = parts[1]
        chat_id = int(parts[2])
        
        db.add_dispatcher(name, chat_id)
        bot.reply_to(message, f"✅ Диспетчер **{name}** (ID: {chat_id}) успішно доданий!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Помилка: {e}")
    user = message.from_user
    # Save user to DB
    conn = db.get_db_connection()
    conn.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)', (user.id, user.username, user.first_name))
    conn.commit()
    
    db.clear_user_state(user.id)
    # Використовуємо локальний шлях до логотипу
    logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.jpg')
    
    # Визначаємо роль для клавіатури
    couriers = db.get_couriers()
    is_courier = any(c['chat_id'] == user.id for c in couriers)
    
    welcome_text = (
        f"👋 Вітаємо у Smakota, {user.first_name}!\n\n"
        "🥗 **Справжня домашня кухня у вашому смартфоні.**\n"
        "Ми готуємо з найсвіжіших продуктів Рівного та доставляємо гарячим прямо до ваших дверей.\n\n"
        "✨ **Чому обирають нас:**\n"
        "• Тільки натуральні інгредієнти\n"
        "• Швидка доставка по місту\n"
        "• Смак, як вдома\n\n"
        "👇 **Оберіть бажаний розділ:**"
    )
    
    # Визначаємо ролі
    couriers = db.get_couriers()
    is_courier = any(c['chat_id'] == user.id for c in couriers)
    
    dispatchers = db.get_dispatchers()
    is_dispatcher = any(d['chat_id'] == user.id for d in dispatchers)

    hall_staff = db.get_hall_staff()
    is_hall = any(h['chat_id'] == user.id for h in hall_staff)

    # Вибираємо правильну клавіатуру
    if user.id == ADMIN_ID:
        markup = keyboards.get_admin_keyboard()
    elif is_courier:
        markup = keyboards.get_courier_keyboard()
    elif is_dispatcher:
        markup = keyboards.get_dispatcher_keyboard()
    elif is_hall:
        markup = keyboards.get_hall_staff_keyboard()
    else:
        markup = keyboards.get_client_keyboard()

    try:
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as photo:
                bot.send_photo(
                    message.chat.id,
                    photo=photo,
                    caption=welcome_text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
        else:
            bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error sending welcome: {e}")
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')
        
    logger.info(f"User {user.id} ({user.username}) started the bot")

@bot.message_handler(func=lambda message: message.text == '📞 Нове ручне замовлення')
def start_manual_order(message):
    user_id = message.from_user.id
    # Перевіряємо, чи це диспетчер або адмін
    dispatchers = db.get_dispatchers()
    is_dispatcher = any(d['chat_id'] == user_id for d in dispatchers)
    
    if not is_dispatcher and user_id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас немає прав для цієї дії.")
        return

    db.clear_cart(user_id) # Очищаємо "кошик" диспетчера для нового замовлення
    db.set_user_state(user_id, 'dispatcher_picking_items')
    
    bot.send_message(
        message.chat.id, 
        "🆕 **Починаємо ручне замовлення.**\n\nОберіть страви з меню нижче. Коли закінчите — натисніть кнопку '🛒 Оформити' у кошику.",
        reply_markup=keyboards.get_categories_keyboard(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '➕ Новий Чек')
def start_hall_order(message):
    user_id = message.from_user.id
    hall_staff = db.get_hall_staff()
    if not any(h['chat_id'] == user_id for h in hall_staff) and user_id != ADMIN_ID:
        return

    db.clear_cart(user_id)
    db.set_user_state(user_id, 'hall_picking_items')
    bot.send_message(
        message.chat.id, 
        "🎫 **Відкриваємо новий чек (ЗАЛ).**\n\nОберіть страви, які замовили клієнти. Коли закінчите — натисніть '🛒 Оформити'.",
        reply_markup=keyboards.get_categories_keyboard(),
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '📝 Записник для Шефа')
def kitchen_add_item(message):
    user_id = message.from_user.id
    db.set_user_state(user_id, 'kitchen_adding_item')
    
    # Show templates as buttons
    templates = db.get_shopping_templates()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for t in templates:
        markup.add(KeyboardButton(f"➕ {t['item_name']}"))
    markup.add(KeyboardButton("❌ Скасувати"))
    
    bot.reply_to(message, "📝 **Що саме закінчилось?**\nОберіть зі списку або напишіть свою назву та кількість (наприклад: 'Борошно 10кг'):", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🛒 Список закупів')
def show_shopping_list(message):
    items = db.get_shopping_list()
    if not items:
        bot.reply_to(message, "✅ **Список порожній.** Все є в наявності!", parse_mode='Markdown')
        return
    
    msg = "🛒 **Список закупів для Шефа:**\n\n"
    markup = InlineKeyboardMarkup()
    for item in items:
        msg += f"• {item['item_name']} — {item['quantity']}\n"
        markup.add(InlineKeyboardButton(f"✅ Куплено: {item['item_name']}", callback_data=f"buy_item_{item['id']}"))
    
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')
    user_id = message.from_user.id
    dispatchers = db.get_dispatchers()
    if not any(d['chat_id'] == user_id for d in dispatchers) and user_id != ADMIN_ID:
        return
        
    conn = db.get_db_connection()
    orders = conn.execute("SELECT * FROM orders WHERE status IN ('new', 'confirmed', 'delivery') ORDER BY created_at DESC").fetchall()
    
    if not orders:
        bot.reply_to(message, "📭 Активних замовлень зараз немає.")
        return
        
    for order in orders:
        msg = f"📦 **Замовлення #{order['id']}** ({order['status']})\n"
        msg += f"👤 {order['delivery_name']}\n📞 {order['delivery_phone']}\n📍 {order['delivery_address']}\n"
        msg += f"💰 Сума: {order['total_amount']} грн"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🛒 Моє замовлення')
def show_cart(message):
    db.clear_user_state(message.from_user.id)
    user_id = message.from_user.id
    cart_text, total, cart_markup = format_cart_message(user_id)
    bot.send_message(message.chat.id, cart_text, reply_markup=cart_markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🛵 Мої доставки (в роботі)')
def show_courier_orders(message):
    user_id = message.from_user.id
    print(f"DEBUG: Button clicked by {user_id}")
    
    # Check if user is courier
    couriers = db.get_couriers()
    courier = next((c for c in couriers if c['chat_id'] == user_id), None)
    
    if not courier:
        print(f"DEBUG: User {user_id} not found in courier list.")
        bot.reply_to(message, "❌ Ви не зареєстровані як кур'єр або ваш ID змінився. Зверніться до адміна.")
        return

    # Shift status control
    if courier['shift_status'] == 'off':
        print(f"DEBUG: Courier {user_id} is OFF shift.")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Почати зміну", callback_data="shift_on"))
        bot.reply_to(message, "🔌 Ви зараз **поза зміною**. Натисніть кнопку, щоб почати роботу та отримувати замовлення.", reply_markup=markup, parse_mode='Markdown')
        return

    logger.info(f"Courier {user_id} is checking orders. Shift status: {courier['shift_status']}")

    conn = db.get_db_connection()
    # Fetch orders including those in batches, ordered by route if available
    orders = conn.execute('''
        SELECT * FROM orders 
        WHERE courier_id = ? AND status = "delivery" 
        ORDER BY CASE WHEN route_order IS NULL THEN 999 ELSE route_order END ASC, created_at DESC
    ''', (user_id,)).fetchall()
    
    print(f"DEBUG: Found {len(orders)} orders for courier {user_id}")
    logger.info(f"Found {len(orders)} active orders for courier {user_id}.")

    if not orders:
        bot.reply_to(message, "📭 У вас немає активних доставок на даний момент.\n\n*P.S. Перевірте, чи ви почали зміну.*")
        return

    for order in orders:
        courier_markup = InlineKeyboardMarkup()
        courier_markup.add(InlineKeyboardButton("✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО", callback_data=f"courier_delivered_{order['id']}"))
        
        # Maps button
        address = order['delivery_address']
        safe_address = urllib.parse.quote(f"м. Рівне, {address}")
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={safe_address}"
        
        # Phone cleaning for link
        raw_phone = str(order['delivery_phone'])
        clean_phone = re.sub(r'[^\d+]', '', raw_phone)
        
        courier_markup.add(
            InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url),
            InlineKeyboardButton("📞 Зателефонувати", url=f"tel:{clean_phone}")
        )
        
        # Route order prefix
        route_prefix = f"#{order['route_order']} " if order['route_order'] else ""
        
        # Priority: Address is the Header
        msg = (
            f"📍 **{route_prefix}АДРЕСА: {order['delivery_address'].upper()}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 **Телефон:** `{raw_phone}`\n"
            f"👤 **Клієнт:** {order['delivery_name']}\n"
            f"💰 **Сума:** {order['total_amount']} грн ({order['payment_method']})\n"
            f"📝 **Коментар:** {order['comment'] if order['comment'] else '---'}\n"
            f"📦 **Замовлення:** #{order['id']}"
        )
        bot.send_message(user_id, msg, reply_markup=courier_markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📞 Контакти')
def show_contacts(message):
    contacts_text = (
        "📞 **Контакти Smakota:**\n\n"
        "📱 Телефони:\n"
        "• +38 (068) 876 33 08\n"
        "• +38 (093) 148 53 93\n"
        "📧 Email: domsmakota@gmail.com\n"
        "📍 Адреса: м. Рівне, вул. Литовська, буд. 55\n\n"
        "⏰ Ми працюємо щодня з 10:00 до 22:00."
    )
    bot.reply_to(message, contacts_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '❓ Допомога')
def show_help(message):
    help_text = (
        "❓ **Як користуватися ботом:**\n\n"
        "1️⃣ Натисніть **'🍕 Меню'**, щоб обрати страви.\n"
        "2️⃣ Додайте бажані страви до кошика.\n"
        "3️⃣ Перейдіть у **'🛒 Моє замовлення'**, щоб редагувати кількість або видалити страви.\n"
        "4️⃣ Натисніть **'✅ Оформити'** та вкажіть дані для доставки.\n\n"
        "Якщо виникли питання, телефонуйте нам!"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

# --- Admin Menu Update ---

def _run_update_in_thread(message):
    """Helper to run the update and notify the admin."""
    try:
        logger.info(f"Admin {message.from_user.id} triggered menu update.")
        update_menu_from_json()
        bot.reply_to(message, "✅ **Меню успішно оновлено!**\nВсі зміни вже доступні користувачам.", parse_mode='Markdown')
        logger.info("Menu update process finished successfully.")
    except Exception as e:
        logger.error(f"Menu update failed: {e}")
        bot.reply_to(message, f"❌ **Помилка під час оновлення:**\n`{e}`", parse_mode='Markdown')

@bot.message_handler(commands=['updatemenu'])
def handle_update_menu(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    bot.reply_to(message, "⏳ **Оновлення меню розпочато...**\nЦе може зайняти кілька секунд.", parse_mode='Markdown')
    update_thread = threading.Thread(target=_run_update_in_thread, args=(message,))
    update_thread.start()

# --- Callback Handlers (Menu & Cart) ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        # --- Admin Batch & Mailing (Shared) ---
        if data.startswith(("adm_sel_", "adm_create_route", "adm_assign_", "mail_")):
            if user_id != ADMIN_ID: return
            
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
                    except: pass
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
                bot.edit_message_text(f"🚀 **Маршрут сформовано ({len(selected_ids)} замовлень).**\nКому передаємо?", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                return

            elif data.startswith("adm_assign_"):
                courier_id = int(data.split("_")[2])
                batch_id = db.create_route_batch(courier_id, selected_ids)
                if batch_id:
                    bot.edit_message_text(f"✅ **Успішно!** {len(selected_ids)} замовлень передано кур'єру.", call.message.chat.id, call.message.message_id)
                    db.clear_user_state(user_id)
                    conn = db.get_db_connection()
                    batch_orders = conn.execute('SELECT * FROM orders WHERE batch_id = ? ORDER BY route_order ASC', (batch_id,)).fetchall()
                    summary = f"🚀 **НОВИЙ МАРШРУТ (#{batch_id})**\n━━━━━━━━━━━━━━\n"
                    for o in batch_orders: summary += f"{o['route_order']}. 📍 {o['delivery_address'].upper()}\n"
                    bot.send_message(courier_id, summary + "\nДеталі доступні в кнопці 'Мої доставки'.", reply_markup=keyboards.get_courier_keyboard(), parse_mode='Markdown')
                return

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
                for t in templates: markup.add(InlineKeyboardButton(f"📄 {t['name']}", callback_data=f"mail_view_{t['id']}"))
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
                    except: pass
                bot.answer_callback_query(call.id, f"✅ Відправлено {count} користувачам!", show_alert=True)
                return
            elif data.startswith("mail_del_"):
                t_id = data.split("_")[2]
                conn = db.get_db_connection()
                conn.execute('DELETE FROM mailing_templates WHERE id = ?', (t_id,))
                conn.commit()
                bot.answer_callback_query(call.id, "Видалено")
                admin_mailing_menu(call.message)
                return

        # --- Hall Staff Callbacks ---
        elif data.startswith("hall_close_"):
            order_id = int(data.split("_")[2])
            db.update_order_status(order_id, 'completed')
            bot.answer_callback_query(call.id, "✅ Чек закрито! Гроші додано в касу.")
            bot.edit_message_text(f"🏁 **Чек #{order_id} закрито.** Оплата отримана.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            return

        # --- Shopping List Callbacks ---
        elif data.startswith("buy_item_"):
            item_id = int(data.split("_")[2])
            db.delete_shopping_item(item_id)
            bot.answer_callback_query(call.id, "✅ Видалено зі списку!")
            # Refresh list
            show_shopping_list(call.message)
            return

        # --- Shift Control ---
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

        # --- Monitoring Callbacks ---
        if data.startswith("mon_courier_"):
            if user_id != ADMIN_ID: return
            
            courier_id_to_check = int(data.split("_")[2])
            today = datetime.now().strftime('%Y-%m-%d')
            conn = db.get_db_connection()
            
            # Get courier info
            courier_info = conn.execute("SELECT name FROM couriers WHERE chat_id = ?", (courier_id_to_check,)).fetchone()
            safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(courier_info['name'])) if courier_info else "Невідомий"
            
            # Get all of today's orders for this courier
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
                    status_emoji = "❓" # Other statuses like 'new' or 'cancelled'
                
                route_prefix = f"#{order['route_order']} " if order['route_order'] else ""
                
                msg += f"{status_emoji} {route_prefix}{order['delivery_address']} ({order['total_amount']} грн)\n"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад до моніторингу", callback_data="mon_back"))
            
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
            return

        elif data == "mon_back":
            if user_id != ADMIN_ID: return
            # We just call the original monitoring function to rebuild the main list
            admin_show_monitoring(call.message)
            return

        # --- Category Navigation ---
        if data.startswith("category_"):
            category_id = data.split("_")[1]
            category_name = db.get_category_name_by_id(category_id)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"🍽️ **Страви категорії: {category_name}**",
                    reply_markup=keyboards.get_items_keyboard(category_id),
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)
        
        elif data == "back_to_categories" or data == "show_menu":
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text="📂 **Оберіть категорію:**", 
                    reply_markup=keyboards.get_categories_keyboard(),
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)

        # --- Item Actions ---
        elif data.startswith("item_"):
            item_id = int(data.split("_")[1])
            item = db.get_item_by_id(item_id)
            if item and item['is_active']:
                # Form item card with photo
                text = f"🍱 **{item['name']}**\n\n"
                if item['description']:
                    text += f"📝 {item['description']}\n"
                if item['weight']:
                    text += f"⚖️ Вага: {item['weight']}\n"
                text += f"\n💰 **Ціна: {item['price']} грн**"
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(f"➕ Додати у кошик", callback_data=f"add_to_cart_{item_id}"))
                markup.add(InlineKeyboardButton("🔙 Назад до меню", callback_data=f"category_{item['category_id']}"))
                
                if item['image_url']:
                    try:
                        bot.send_photo(call.message.chat.id, item['image_url'], caption=text, parse_mode='Markdown', reply_markup=markup)
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except Exception:
                        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='Markdown')
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.answer_callback_query(call.id, "❌ Ця страва зараз недоступна.", show_alert=True)
        
        elif data.startswith("add_to_cart_"):
            # data looks like "add_to_cart_123"
            # split("_") gives ['add', 'to', 'cart', '123']
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
        
        # --- Cart Actions ---
        elif data.startswith("cart_plus_"):
            item_id = int(data.split("_")[2])
            db.update_cart_quantity(user_id, item_id, 1)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)
            
        elif data.startswith("cart_minus_"):
            item_id = int(data.split("_")[2])
            db.update_cart_quantity(user_id, item_id, -1)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)

        elif data.startswith("cart_remove_"):
            item_id = int(data.split("_")[2])
            db.remove_from_cart(user_id, item_id)
            cart_text, total, cart_markup = format_cart_message(user_id)
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=cart_text, reply_markup=cart_markup, parse_mode='Markdown')
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)

        elif data == "clear_cart":
            db.clear_cart(user_id)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text="🗑️ **Кошик очищено!**",
                    reply_markup=keyboards.get_empty_cart_keyboard(),
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    bot.answer_callback_query(call.id)

        # --- Checkout Start ---
        elif data == "checkout":
            _, total, _ = format_cart_message(user_id)
            if total == 0:
                bot.answer_callback_query(call.id, "Кошик порожній!", show_alert=True)
                return

            # Check roles
            dispatchers = db.get_dispatchers()
            is_dispatcher = any(d['chat_id'] == user_id for d in dispatchers) or user_id == ADMIN_ID
            
            hall_staff = db.get_hall_staff()
            is_hall = any(h['chat_id'] == user_id for h in hall_staff)

            if is_hall:
                # Natasha doesn't need address/phone, just a quick confirm
                cart_items = db.get_cart_items(user_id)
                total = sum(item['price'] * item['quantity'] for item in cart_items)
                
                # Create order marked as Hall
                order_id = db.create_order(user_id, total, "💵 Каса (ЗАЛ)", {'name': 'Зал', 'address': 'В закладі'}, cart_items)
                if order_id:
                    # Update order with hall_staff_id
                    conn = db.get_db_connection()
                    conn.execute('UPDATE orders SET hall_staff_id = ? WHERE id = ?', (user_id, order_id))
                    conn.commit()
                    
                    db.clear_cart(user_id)
                    db.clear_user_state(user_id)
                    
                    # PRINT RECEIPT FOR KITCHEN
                    receipt = f"🎫 **ЧЕК #{order_id} (ЗАЛ)**\n"
                    receipt += "----------------------------\n"
                    for item in cart_items:
                        receipt += f"• {item['name']} x{item['quantity']}\n"
                    receipt += "----------------------------\n"
                    receipt += f"💰 **ВСЬОГО до сплати: {total} грн**\n\n"
                    receipt += "📢 Покажіть цей чек на кухні."
                    
                    bot.send_message(message.chat.id, receipt, reply_markup=keyboards.get_hall_staff_keyboard(), parse_mode='Markdown')
                    
                    # Notify Admin (Chef)
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

            # Normal client checkout logic (existing)
            last_order = db.get_last_order(user_id)
            if last_order:
                db.set_user_state(user_id, 'checkout_use_history', {'history': dict(last_order)})
                bot.send_message(
                    call.message.chat.id,
                    f"📝 **Знайдено ваші минулі дані:**\n\n👤 {last_order['delivery_name']}\n📞 {last_order['delivery_phone']}\n📍 {last_order['delivery_address']}\n\nБажаєте використати їх знову?",
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

        elif data == "noop":
            bot.answer_callback_query(call.id)

        # --- Admin Order Management ---
        elif data.startswith("admin_accept_"):
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
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    raise e
            
            # Notify User
            order = db.get_order_by_id(order_id)
            if order:
                try:
                    bot.send_message(order['user_id'], f"👨‍🍳 **Ваше замовлення #{order_id} прийнято!**\nГотуємо смакоту. Скоро передамо кур'єру.", parse_mode='Markdown')
                except Exception as e:
                    logger.warning(f"Failed to notify user: {e}")
            
        elif data.startswith("admin_cancel_"):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
                return

            order_id = data.split("_")[2]
            db.update_order_status(order_id, 'cancelled')
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"❌ **Замовлення #{order_id} СКАСОВАНО.**",
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    raise e
            
            # Notify User
            order = db.get_order_by_id(order_id)
            if order:
                try:
                    bot.send_message(order['user_id'], f"❌ **Замовлення #{order_id} скасовано.**\nЗв'яжіться з нами для уточнення деталей.", parse_mode='Markdown')
                except Exception:
                    pass

        elif data.startswith("assign_"):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "⛔ Доступ заборонено", show_alert=True)
                return

            _, order_id, courier_id = data.split("_")
            db.assign_courier(order_id, int(courier_id))
            
            # Update Admin UI
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"🛵 **Замовлення #{order_id} передано кур'єру.**",
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    raise e
            
            # Notify Courier
            try:
                order = db.get_order_by_id(order_id)
                courier_markup = InlineKeyboardMarkup()
                courier_markup.add(InlineKeyboardButton("✅ ЗАМОВЛЕННЯ ДОСТАВЛЕНО", callback_data=f"courier_delivered_{order_id}"))
                
                address = order['delivery_address']
                safe_address = urllib.parse.quote(f"м. Рівне, {address}")
                maps_url = f"https://www.google.com/maps/dir/?api=1&destination={safe_address}"
                
                # Phone cleaning
                raw_phone = str(order['delivery_phone'])
                clean_phone = re.sub(r'[^\d+]', '', raw_phone)
                
                courier_markup.add(
                    InlineKeyboardButton("🗺️ Побудувати маршрут", url=maps_url),
                    InlineKeyboardButton("📞 Зателефонувати", url=f"tel:{clean_phone}")
                )
                
                # Priority: Address is the Header
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
                
                # Notify User
                bot.send_message(order['user_id'], f"🛵 **Кур'єр вже в дорозі!**\nОчікуйте доставку на адресу: **{order['delivery_address']}**", parse_mode='Markdown')
                
            except Exception as e:
                logger.error(f"Failed to notify courier: {e}")

        elif data.startswith("courier_delivered_"):
            order_id = data.split("_")[2]
            order = db.get_order_by_id(order_id)
            
            if not order or user_id != order['courier_id']:
                bot.answer_callback_query(call.id, "⛔ Ви не є призначеним кур'єром для цього замовлення", show_alert=True)
                return

            db.update_order_status(order_id, 'completed')
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id, message_id=call.message.message_id,
                    text=f"✅ **Замовлення #{order_id} доставлено!**\nГарна робота!",
                    parse_mode='Markdown'
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in e.description.lower():
                    raise e
            
            # Notify User
            if order:
                try:
                    bot.send_message(order['user_id'], f"🏁 **Замовлення #{order_id} доставлено!**\nСмачного! Чекаємо на вас знову.", parse_mode='Markdown')
                except:
                    pass
            
            # Notify Admin
            if ADMIN_ID:
                try:
                    bot.send_message(ADMIN_ID, f"🏁 Замовлення #{order_id} успішно доставлено.")
                except:
                    pass

    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Виникла помилка.")

@bot.message_handler(func=lambda message: message.text == '📊 Мій звіт за сьогодні')
def show_courier_report(message):
    handle_my_report(message)

@bot.message_handler(func=lambda message: message.text == '📋 Нові замовлення')
def admin_show_new_orders(message):
    if message.from_user.id != ADMIN_ID: return
    conn = db.get_db_connection()
    orders = conn.execute('SELECT * FROM orders WHERE status = "new"').fetchall()
    if not orders:
        bot.reply_to(message, "📭 Немає нових замовлень.")
        return
    
    # Init batch building state
    db.set_user_state(message.from_user.id, 'admin_batch_building', {'selected_ids': []})
    
    msg = "📋 **Нові замовлення:**\n\nОберіть адреси по черзі, щоб сформувати маршрут для кур'єра:"
    markup = InlineKeyboardMarkup()
    for order in orders:
        markup.add(InlineKeyboardButton(f"📍 {order['delivery_address']} (#{order['id']})", callback_data=f"adm_sel_{order['id']}"))
    
    markup.add(InlineKeyboardButton("🚀 Сформувати Маршрут", callback_data="adm_create_route"))
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📊 Виручка за сьогодні')
def admin_show_revenue(message):
    if message.from_user.id != ADMIN_ID: return
    conn = db.get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    res = conn.execute('SELECT SUM(total_amount) as total FROM orders WHERE status = "completed" AND date(created_at) = ?', (today,)).fetchone()
    total = res['total'] if res['total'] else 0
    bot.reply_to(message, f"💰 Загальна виручка за сьогодні: **{total} грн**", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🛵 Кур\'єри на зміні')
def admin_show_couriers(message):
    if message.from_user.id != ADMIN_ID: return
    couriers = db.get_couriers()
    if not couriers:
        bot.reply_to(message, "🔌 Немає зареєстрованих кур'єрів.")
        return
    msg = "🛵 **Кур'єри:**\n\n"
    for c in couriers:
        status = "✅ НА ЗМІНІ" if c['shift_status'] == 'on' else "🔌 Поза зміною"
        # Escape name for Markdown safety
        safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(c['name']))
        msg += f"• {safe_name} ({status})\n"
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📊 Моніторинг')
def admin_show_monitoring(message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = db.get_db_connection()
    couriers = db.get_couriers()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if not couriers:
        bot.reply_to(message, "📭 Немає зареєстрованих кур'єрів.")
        return
        
    msg = "📊 **Моніторинг кур'єрів (сьогодні):**\n\n"
    markup = InlineKeyboardMarkup()
    
    for c in couriers:
        active = conn.execute(
            'SELECT COUNT(*) as count FROM orders WHERE courier_id = ? AND status = "delivery"', 
            (c['chat_id'],)
        ).fetchone()['count']
        
        completed = conn.execute(
            'SELECT COUNT(*) as count FROM orders WHERE courier_id = ? AND status = "completed" AND date(created_at) = ?', 
            (c['chat_id'], today)
        ).fetchone()['count']
        
        status_emoji = "✅" if c['shift_status'] == 'on' else "🔌"
        safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(c['name']))
        
        msg += f"{status_emoji} **{safe_name}** | В дорозі: `{active}` | Завершено: `{completed}`\n"
        markup.add(InlineKeyboardButton(f"🔎 Деталі по {safe_name}", callback_data=f"mon_courier_{c['chat_id']}"))
        
    bot.reply_to(message, msg, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🔄 Оновити меню (GS)')
def admin_trigger_update(message):
    handle_update_menu(message)

@bot.message_handler(func=lambda message: message.text == '📞 Написати Адміну')
def contact_admin(message):
    bot.reply_to(message, "💬 **Зв'язок з Адміністратором:**\n\nВи можете написати прямо власнику або зателефонувати за номерами в розділі 'Контакти'.\n\nТисніть сюди: @Redbox1991", parse_mode='Markdown')

# --- Mailing System ---

@bot.message_handler(func=lambda message: message.text == '📣 Розсилка')
def admin_mailing_menu(message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🆕 Створити розсилку", callback_data="mail_new"))
    markup.add(InlineKeyboardButton("📋 Мої шаблони", callback_data="mail_list"))
    bot.reply_to(message, "📢 **Керування розсилками**\n\nВи можете створити нове повідомлення або вибрати зі збережених.", reply_markup=markup, parse_mode='Markdown')

# --- FSM Handlers (Checkout) ---

@bot.message_handler(func=lambda message: message.text == "❌ Скасувати")
def cancel_checkout(message):
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
    user_id = message.from_user.id
    state_info = db.get_user_state(user_id)
    if not state_info:
        # Check if user is courier for dynamic keyboard
        couriers = db.get_couriers()
        is_courier = any(c['chat_id'] == user_id for c in couriers)
        bot.reply_to(message, "Немає куди повертатися. Скористайтеся меню.", reply_markup=keyboards.get_main_keyboard(is_courier))
        return

    state = state_info['state']
    data = state_info['data']
    
    # Simple State Machine Backwards Navigation
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
        admin_mailing_menu(message)
        return

    # --- Kitchen Shopping List Logic ---
    elif state == 'kitchen_adding_item':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "Скасовано.", reply_markup=keyboards.get_kitchen_keyboard())
            return
            
        # If user clicked template button like "➕ Борошно"
        input_text = message.text.replace("➕ ", "").strip()
        
        # Split text into name and quantity
        parts = input_text.rsplit(maxsplit=1)
        name = parts[0]
        qty = parts[1] if len(parts) > 1 else "?"
        
        db.upsert_shopping_item(name, qty)
        bot.send_message(message.chat.id, f"✅ Додано в список: **{name} ({qty})**", reply_markup=keyboards.get_kitchen_keyboard(), parse_mode='Markdown')
        db.clear_user_state(user_id)
        return

    # --- Checkout Logic ---

    # --- Manual Dispatcher Checkout ---
    if state == 'manual_checkout_name':
        if message.text == "❌ Скасувати":
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "❌ Ручне замовлення скасовано.", reply_markup=keyboards.get_dispatcher_keyboard())
            return
        
        data['name'] = message.text
        db.set_user_state(user_id, 'manual_checkout_contact', data)
        bot.send_message(message.chat.id, f"📞 Введіть номер телефону клієнта:", reply_markup=keyboards.get_checkout_step_keyboard())
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
        
        # Finish order
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
            bot.send_message(message.chat.id, f"✅ **Ручне замовлення #{order_id} створено!**\n\nДані замовлення:\n👤 {data['name']}\n📍 {data['address']}\n💰 {total} грн", reply_markup=keyboards.get_dispatcher_keyboard(), parse_mode='Markdown')
            
            # Notify Admin
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
            # Basic validation: digits, optional leading +, length 10-15
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if not re.match(r'^\+?\d{10,15}$', clean_phone):
                bot.reply_to(message, "⚠️ Схоже, це некоректний номер. Введіть, будь ласка, у форматі +380XXXXXXXXX або скористайтеся кнопкою.")
                return
            phone = clean_phone
        
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

        # Finalize
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
                "⏳ Оператор вже обробляє вашу заявку."
            )
            
            # Check for courier for refresh
            couriers = db.get_couriers()
            is_courier = any(c['chat_id'] == user_id for c in couriers)
            
            bot.send_message(message.chat.id, success_msg, reply_markup=keyboards.get_main_keyboard(is_courier), parse_mode='Markdown')
            
            # Notify Admin
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

# --- Courier & Report Commands ---

@bot.message_handler(commands=['add_courier'])
def handle_add_courier(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split(maxsplit=2)
        courier_chat_id = int(parts[1])
        courier_name = parts[2]
        
        db.add_courier(courier_name, courier_chat_id)
        bot.reply_to(message, f"✅ Кур'єр **{courier_name}** доданий успішно!", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "⚠️ Формат: `/add_courier ID Ім'я`\nID можна дізнатися у @userinfobot", parse_mode='Markdown')

@bot.message_handler(commands=['my_report'])
def handle_my_report(message):
    user_id = message.from_user.id
    count, total = db.get_daily_report(user_id)
    
    if count == 0:
        bot.reply_to(message, "💤 Сьогодні замовлень ще не було.")
    else:
        bot.reply_to(message, 
            f"📊 **Ваш звіт за сьогодні:**\n\n"
            f"📦 Доставлено: **{count}**\n"
            f"💰 Готівка: **{total} грн**\n\n"
            f"Продуктивного дня! 🚀",
            parse_mode='Markdown'
        )

# --- Test Mode / Role Switching ---

@bot.message_handler(commands=['set_role_admin'])
def set_role_admin(message):
    """Sets the current user as an admin and refreshes menu."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ заборонено")
        return
    bot.reply_to(
        message, 
        "👑 Тепер ти **Адмін**. Повний контроль активовано.", 
        reply_markup=keyboards.get_admin_keyboard(), 
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['set_role_courier'])
def set_role_courier(message):
    """Sets the current user as a courier and refreshes menu."""
    user_id = message.from_user.id
    db.add_courier(f"Test_{message.from_user.first_name}", user_id)
    bot.reply_to(
        message, 
        "🛵 Тепер ти **Кур'єр**.\nТвій інтерфейс оновлено.", 
        reply_markup=keyboards.get_courier_keyboard(), 
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['set_role_client'])
def set_role_client(message):
    """Removes the user from courier list and refreshes menu."""
    user_id = message.from_user.id
    db.remove_courier_by_chat_id(user_id)
    bot.reply_to(
        message, 
        "👤 Тепер ти **Клієнт**.\nТвій інтерфейс оновлено.", 
        reply_markup=keyboards.get_client_keyboard(), 
        parse_mode='Markdown'
    )

# --- Default Handler ---
@bot.message_handler(func=lambda message: True)
def handle_default_message(message):
    logger.info(f"Received message: {message.text} from {message.from_user.id}")
    if message.chat.type == 'private':
        bot.reply_to(message, "🤔 Я вас не розумію. Скористайтеся меню.", reply_markup=keyboards.get_main_keyboard())

if __name__ == '__main__':
    db.setup_database()
    logger.info("Starting Smakota bot...")
    bot.polling(none_stop=True)