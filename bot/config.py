"""
Конфігурація Smakota Bot.
Всі налаштування, токени та константи зібрані тут.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
ADMIN_ID: int = int(os.getenv('ADMIN_ID', 0))
PAYMENT_PROVIDER_TOKEN: str = os.getenv('PAYMENT_PROVIDER_TOKEN', '')

# Робочі години
WORKING_HOURS = {
    0: (9, 17),   # Понеділок
    1: (9, 17),   # Вівторок
    2: (9, 17),   # Середа
    3: (9, 17),   # Четвер
    4: (9, 17),   # П'ятниця
    5: (9, 16),   # Субота
    6: None,      # Неділя — вихідний
}

# Шляхи
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, 'assets', 'logo.jpg')
