"""
Реєстрація всіх хендлерів.
ПОРЯДОК ІМПОРТУ КРИТИЧНО ВАЖЛИВИЙ!

Telebot обробляє хендлери в порядку їх реєстрації.
Тому:
1. Спочатку команди (/start, /add_courier тощо)
2. Потім content_type хендлери (web_app_data)
3. Потім конкретні текстові кнопки
4. Потім callbacks (inline кнопки)
5. Потім FSM (cancel, back, process_checkout_step)
6. Потім ролі
7. ОСТАННІМ — default catch-all
"""

# 1. Commands first
from bot.handlers import start       # /start, /help
from bot.handlers import admin       # /add_hall_staff, /add_dispatcher, /add_courier, /updatemenu, admin buttons
from bot.handlers import courier     # courier buttons, /my_report

# 2. Content type + text button handlers
from bot.handlers import client      # web_app_data, cart, contacts, help
from bot.handlers import dispatcher  # manual order button
from bot.handlers import hall        # hall new check button
from bot.handlers import kitchen     # kitchen buttons

# 3. Callback query handler
from bot.handlers import callbacks   # ALL inline button presses

# 4. FSM handlers (cancel/back MUST come before process_checkout_step!)
from bot.handlers import checkout    # cancel, back, FSM steps

# 5. Role switching (test commands)
from bot.handlers import roles       # /set_role_admin, /set_role_courier, etc.

# 6. DEFAULT HANDLER — MUST BE LAST!
from bot.handlers import default     # catch-all for unrecognized messages
