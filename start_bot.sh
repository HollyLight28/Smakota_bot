#!/bin/bash

# 1. Вбиваємо старого бота
echo "🔌 Зупиняємо стару версію..."
pkill -f bot.py

# 2. Оновлюємо меню з сайту (твоя крута фішка!)
echo "🍕 Оновлюємо меню з сайту smakota.com.ua..."
python3 sync_menu.py

# 3. Запускаємо бота в фоні
echo "🚀 Запускаємо бота в фоні..."
nohup python3 bot.py > bot_output.log 2>&1 &

echo "✅ БОТ ПРАЦЮЄ! Ви можете закривати термінал."
echo "Логи дивись тут: tail -f bot_output.log"
