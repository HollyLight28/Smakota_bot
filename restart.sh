#!/bin/bash
# Перезапуск Smakota_bot
pkill -f "python3 bot.py"
sleep 1
cd /home/vova/Code/Telegram_bots/Smakota_bot
nohup python3 bot.py > bot_output.log 2>&1 &
echo "Smakota_bot restarted."
