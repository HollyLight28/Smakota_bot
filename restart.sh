#!/bin/bash
# Перезапуск Smakota_bot (модульна версія)
pkill -f "python3 run.py" 2>/dev/null
pkill -f "python3 bot.py" 2>/dev/null
sleep 1
cd /home/vova/Code/Telegram_bots/Smakota_bot
nohup python3 run.py > bot_output.log 2>&1 &
echo "Smakota_bot restarted (modular version via run.py)."
