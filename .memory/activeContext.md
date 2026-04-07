# Active Context

## Поточний статус
- ✅ Рефакторинг bot.py завершено
- ✅ Бот працює на модульній версії (run.py) — PID 2212932
- ✅ Баг "Мої доставки" виправлено
- ⬜ Git push ще не зроблено (потрібен пароль/SSH)

## Що зроблено
1. **Рефакторинг** — розбили `bot.py` (1424 рядки) на 10 модулів:
   - `bot/__init__.py` — екземпляр бота
   - `bot/config.py` — конфігурація
   - `bot/utils.py` — утиліти (format_cart, clean_phone, maps_url)
   - `bot/handlers/start.py` — /start, /help
   - `bot/handlers/client.py` — webapp, кошик, контакти
   - `bot/handlers/admin.py` — адмін-функції
   - `bot/handlers/courier.py` — кур'єрські замовлення
   - `bot/handlers/dispatcher.py` — ручне замовлення
   - `bot/handlers/hall.py` — зал (Наташа)
   - `bot/handlers/kitchen.py` — кухня, шоппінг-лист
   - `bot/handlers/callbacks.py` — ВСІ inline-кнопки
   - `bot/handlers/checkout.py` — FSM оформлення
   - `bot/handlers/roles.py` — тестові ролі
   - `bot/handlers/default.py` — catch-all
   - `run.py` — нова точка входу

2. **Виправлені баги:**
   - Відсутня `get_couriers()` в database.py
   - Відсутній декоратор `@bot.message_handler(commands=['start'])`
   - `tel:` URL без міжнародного формату (+380) крашив бота
   - `answer_callback_query` на протухлий callback крашив бота
   - Дублікати кур'єрів при `set_role_courier`
   - `checkout_use_history` був недосяжний через невірний indent
   - **`delivery_comment` → `comment`** — courier.py звертався до неіснуючої колонки БД, мовчазний краш
   - **`restart.sh`** запускав старий `bot.py` замість `run.py`
   - **13 зависших замовлень** зі статусом `delivery` зачищено → `completed`

## Наступні кроки
1. Протестувати кнопку "Мої доставки" в Telegram
2. `git push` (Вова має зробити руками або налаштувати SSH)
3. Налаштувати cron для автооновлення меню
4. Написати тести для database.py
