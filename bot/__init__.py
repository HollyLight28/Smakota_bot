"""
Smakota Bot — модульна структура.
Цей файл створює екземпляр бота, який імпортується в кожному хендлері.
"""
import telebot
from bot.config import BOT_TOKEN

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env file")

bot = telebot.TeleBot(BOT_TOKEN)
