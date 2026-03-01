# System Patterns

## Architecture
- **Monolithic Controller:** `bot.py` handles all routing and business logic.
- **Data Layer:** `database.py` uses raw SQL with `sqlite3`. Thread-local storage used for connection safety.
- **Concurrency:** Threading used (standard for `telebot`), but not async.

## Anti-Patterns (To Fix)
- **Synchronous I/O:** Using `telebot` instead of `aiogram` limits scalability.
- **God Object:** `bot.py` is too large and cohesive.
- **Hardcoded Strings:** UI text is scattered in logic.
