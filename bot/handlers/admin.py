"""
Хендлери адміністратора: управління замовленнями, кур'єрами, розсилка, моніторинг.
"""
import re
import threading
from datetime import datetime

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger
import database as db
import keyboards
from update_menu_gs import update_menu_from_json


# --- Admin Commands ---

@bot.message_handler(commands=['add_hall_staff'])
def register_hall_staff(message):
    """Додає персонал залу. Формат: /add_hall_staff Ім'я ChatID"""
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Використання: `/add_hall_staff Наталка ChatID`", parse_mode='Markdown')
            return
        db.add_hall_staff(parts[1], int(parts[2]))
        bot.reply_to(message, f"✅ Наталка {parts[1]} додана!")
    except Exception as e:
        bot.reply_to(message, f"❌ Помилка: {e}")


@bot.message_handler(commands=['add_dispatcher'])
def register_dispatcher(message):
    """Додає диспетчера. Формат: /add_dispatcher Ім'я ChatID"""
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


@bot.message_handler(commands=['add_courier'])
def handle_add_courier(message):
    """Додає кур'єра. Формат: /add_courier ChatID Ім'я"""
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


# --- Admin Text Button Handlers ---

@bot.message_handler(func=lambda message: message.text == '📋 Нові замовлення')
def admin_show_new_orders(message):
    """Показує нові замовлення з можливістю сформувати маршрут."""
    if message.from_user.id != ADMIN_ID:
        return
    conn = db.get_db_connection()
    orders = conn.execute('SELECT * FROM orders WHERE status = "new"').fetchall()
    if not orders:
        bot.reply_to(message, "📭 Немає нових замовлень.")
        return

    db.set_user_state(message.from_user.id, 'admin_batch_building', {'selected_ids': []})

    msg = "📋 **Нові замовлення:**\n\nОберіть адреси по черзі, щоб сформувати маршрут для кур'єра:"
    markup = InlineKeyboardMarkup()
    for order in orders:
        markup.add(InlineKeyboardButton(
            f"📍 {order['delivery_address']} (#{order['id']})",
            callback_data=f"adm_sel_{order['id']}"
        ))
    markup.add(InlineKeyboardButton("🚀 Сформувати Маршрут", callback_data="adm_create_route"))
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Виручка за сьогодні')
def admin_show_revenue(message):
    """Детальний звіт по виручці за сьогодні."""
    if message.from_user.id != ADMIN_ID: return
    
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_db_connection()
    
    # Загальна сума
    total = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed" AND date(created_at) = ?', (today,)).fetchone()[0] or 0
    # По методах оплати
    cash = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed" AND payment_method = "Готівка" AND date(created_at) = ?', (today,)).fetchone()[0] or 0
    terminal = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed" AND payment_method = "Термінал" AND date(created_at) = ?', (today,)).fetchone()[0] or 0
    
    # По відділах
    courier_total = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed" AND courier_id IS NOT NULL AND date(created_at) = ?', (today,)).fetchone()[0] or 0
    hall_total = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed" AND hall_staff_id IS NOT NULL AND date(created_at) = ?', (today,)).fetchone()[0] or 0

    msg = (
        f"📊 **Звіт по виручці ({today}):**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Всього: {total} грн**\n\n"
        f"💵 Готівка: `{cash} грн`\n"
        f"💳 Термінал: `{terminal} грн`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛵 Доставки: `{courier_total} грн`\n"
        f"💃 Зал (Наташа): `{hall_total} грн`"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📖 Інструкція')
def admin_instruction(message):
    """Шпаргалка для Шефа."""
    if message.from_user.id != ADMIN_ID: return
    
    instruct = (
        "📖 **Як користуватися ботом (Шеф):**\n\n"
        "1. **Нові замовлення** — тут падають замовлення з бота. Тисни на замовлення і вибирай кур'єра.\n"
        "2. **Ручне замовлення** — якщо подзвонили по телефону. Обирай страви, введи номер — і воно піде в базу.\n"
        "3. **Моніторинг** — дивись, де зараз кур'єри і скільки вони вже розвезли.\n"
        "4. **Інші ролі** — пиши `/roles`, щоб перевірити як бачить бота клієнт або кур'єр."
    )
    bot.reply_to(message, instruct, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '🛵 Кур\'єри на зміні')
def admin_show_couriers(message):
    """Показує список кур'єрів та їх статус зміни."""
    if message.from_user.id != ADMIN_ID:
        return
    couriers = db.get_couriers()
    if not couriers:
        bot.reply_to(message, "🔌 Немає зареєстрованих кур'єрів.")
        return
    msg = "🛵 **Кур'єри:**\n\n"
    for c in couriers:
        status = "✅ НА ЗМІНІ" if c['shift_status'] == 'on' else "🔌 Поза зміною"
        safe_name = re.sub(r'[_*`\[\]]', r'\\\g<0>', str(c['name']))
        msg += f"• {safe_name} ({status})\n"
    bot.reply_to(message, msg, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Моніторинг')
def admin_show_monitoring(message):
    """Моніторинг кур'єрів: активні замовлення, завершені за сьогодні."""
    if message.from_user.id != ADMIN_ID:
        return

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


# --- Menu Update ---

def _run_update_in_thread(message):
    """Запускає оновлення меню в окремому потоці."""
    try:
        logger.info(f"Admin {message.from_user.id} triggered menu update.")
        update_menu_from_json()
        bot.reply_to(message, "✅ **Меню успішно оновлено!**\nВсі зміни вже доступні користувачам.", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Menu update failed: {e}")
        bot.reply_to(message, f"❌ **Помилка під час оновлення:**\n`{e}`", parse_mode='Markdown')


@bot.message_handler(commands=['updatemenu'])
def handle_update_menu_cmd(message):
    """Команда /updatemenu — оновлює меню з Google Sheets."""
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "⏳ **Оновлення меню розпочато...**\nЦе може зайняти кілька секунд.", parse_mode='Markdown')
    update_thread = threading.Thread(target=_run_update_in_thread, args=(message,))
    update_thread.start()


@bot.message_handler(func=lambda message: message.text == '🔄 Оновити меню (GS)')
def admin_trigger_update(message):
    """Кнопка '🔄 Оновити меню (GS)' — викликає ту саму логіку."""
    handle_update_menu_cmd(message)


# --- Mailing ---

@bot.message_handler(func=lambda message: message.text == '📣 Розсилка')
def admin_mailing_menu(message):
    """Меню управління розсилками."""
    if message.from_user.id != ADMIN_ID:
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🆕 Створити розсилку", callback_data="mail_new"))
    markup.add(InlineKeyboardButton("📋 Мої шаблони", callback_data="mail_list"))
    bot.reply_to(
        message,
        "📢 **Керування розсилками**\n\nВи можете створити нове повідомлення або вибрати зі збережених.",
        reply_markup=markup,
        parse_mode='Markdown'
    )
