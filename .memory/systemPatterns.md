# System Patterns

## Architecture
- **Monolithic Controller**: `bot.py` (1414 lines) — GOD OBJECT, needs refactoring
- **Data Layer**: `database.py` (585 lines) using SQLite with thread-safe connections via `threading.local()`
- **UI Layer**: `keyboards.py` — reply + inline keyboards by role
- **WebApp**: `webapp/` — Telegram Mini App hosted on GitHub Pages (separate repo)
- **Sync Layer**: `sync_menu.py` — scrapes smakota.com.ua, updates DB + generates data.js

## Anti-patterns Found
1. God Object (`bot.py`) — all handlers, FSM, callbacks in one file
2. Missing function `get_couriers()` in `database.py` — FIXED 2026-03-01
3. Zero tests — no test coverage at all
4. No error monitoring — bot crashes silently

## Lessons Learned
- Always check that every `db.xxx()` call in bot.py has a corresponding `def xxx()` in database.py
- The webapp repo (public) is a separate git repo INSIDE the bot repo folder (webapp/.git)
- `start_bot.sh` is the one-button restart: kills old process, syncs menu, starts new bot
- Telegram WebApp images load from smakota.com.ua directly — if site is down, images break

## Deployment
- Bot: runs via `nohup python3 bot.py` on local machine
- WebApp: GitHub Pages at https://hollylight28.github.io/smakota-telegram-app/
- WebApp update: `deploy_webapp.py` or manual upload of index.html + data.js

## Working Schedule
- Mon-Fri: 9:00-17:00
- Sat: 9:00-16:00
- Sun: OFF
