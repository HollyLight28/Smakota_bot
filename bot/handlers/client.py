"""
Хендлери клієнта: WebApp дані, кошик, контакти, допомога.
"""
import json

from bot import bot
from bot.config import ADMIN_ID
from bot.utils import logger, format_cart_message
import database as db
import keyboards


@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    """Обробляє дані, відправлені з Telegram WebApp."""
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        logger.info(f"WebApp data received from {user_id}: {data}")

        if data.get('action') == 'webapp_order':
            items = data.get('items', {})
            if not items:
                bot.send_message(message.chat.id, "🛒 Ваш кошик порожній.")
                return

            # Очищуємо кошик перед додаванням (як в оригіналі)
            db.clear_cart(user_id)
            
            order_summary = "🛒 **Ви обрали в меню:**\n\n"
            for item_id_str, item_info in items.items():
                item_id = int(item_id_str)
                count = item_info.get('count', 1)
                db.add_to_cart(user_id, item_id, count)
                order_summary += f"• {item_info['name']} x{count} — {item_info['price'] * count} грн\n"

            cart_text, total, cart_markup = format_cart_message(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ **Товари додано до кошика!**\n\n{order_summary}\n💰 **Разом: {total} грн**",
                reply_markup=cart_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error processing WebApp data: {e}")
        bot.send_message(message.chat.id, "❌ Сталася помилка при обробці замовлення з меню.")


@bot.message_handler(func=lambda message: message.text == '🛒 Моє замовлення')
def show_cart(message):
    """Показує користувачу його кошик."""
    db.clear_user_state(message.from_user.id)
    user_id = message.from_user.id
    cart_text, total, cart_markup = format_cart_message(user_id)
    bot.send_message(message.chat.id, cart_text, reply_markup=cart_markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📞 Контакти')
def show_contacts(message):
    """Показує контакти Smakota."""
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
    """Показує інструкцію користування ботом."""
    help_text = (
        "❓ **Як користуватися ботом:**\n\n"
        "1️⃣ Натисніть **'🍕 Меню'**, щоб обрати страви.\n"
        "2️⃣ Додайте бажані страви до кошика.\n"
        "3️⃣ Перейдіть у **'🛒 Моє замовлення'**, щоб редагувати кількість або видалити страви.\n"
        "4️⃣ Натисніть **'✅ Оформити'** та вкажіть дані для доставки.\n\n"
        "Якщо виникли питання, телефонуйте нам!"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📞 Написати Адміну')
def contact_admin(message):
    """Контакт адміна."""
    bot.reply_to(
        message,
        "💬 **Зв'язок з Адміністратором:**\n\n"
        "Ви можете написати прямо власнику або зателефонувати за номерами в розділі 'Контакти'.\n\n"
        "Тисніть сюди: @Redbox1991",
        parse_mode='Markdown'
    )
