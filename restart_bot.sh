#!/bin/bash

# Шлях до папки з ботом
PROJECT_DIR="/home/vova/Code/Telegram_bots/Smakota_bot"
LOG_FILE="$PROJECT_DIR/bot_output.log"

echo "🔄 Перезапуск Smakota Bot..."

# 1. Зупиняємо старі процеси
echo "🔌 Зупиняємо старі процеси (run.py, bot.py)..."
pkill -f "python3 run.py"
pkill -f "python3 bot.py"
sleep 2

# 2. Переходимо в папку проекту
cd "$PROJECT_DIR" || exit

# 3. Оновлюємо меню (за бажанням, можна закоментувати якщо не треба щоразу)
echo "🍕 Оновлюємо меню з сайту..."
python3 sync_menu.py

# 4. Запускаємо нову версію
echo "🚀 Запускаємо бота..."
nohup python3 run.py > "$LOG_FILE" 2>&1 &

echo "✅ Бот успішно перезапущений!"
echo "ID процесу: $!"
echo "Логи можна переглянути командою: tail -f $LOG_FILE"

# Повідомлення для користувача (якщо запущено через ярлик)
if [ -t 1 ]; then
    echo "Натисніть будь-яку клавішу, щоб закрити вікно..."
    read -n 1
fi
