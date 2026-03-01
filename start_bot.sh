#!/bin/bash

# 1. Вбиваємо старого бота (і run.py і bot.py)
echo "🔌 Зупиняємо стару версію..."
pkill -f "python3 run.py"
pkill -f "python3 bot.py"
sleep 1

# 2. Оновлюємо меню з сайту
echo "🍕 Оновлюємо меню з сайту smakota.com.ua..."
python3 sync_menu.py

# 3. Запускаємо НОВУ модульну версію бота в фоні
echo "🚀 Запускаємо бота (модульна версія)..."
nohup python3 run.py > bot_output.log 2>&1 &

echo "✅ БОТ ПРАЦЮЄ! Ви можете закривати термінал."
echo "Логи дивись тут: tail -f bot_output.log"
