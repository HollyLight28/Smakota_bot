import sqlite3
conn = sqlite3.connect('/home/vova/Code/Telegram_bots/Smakota_bot/smakota.db')
cursor = conn.cursor()
cursor.execute("INSERT INTO orders (user_id, total_amount, payment_method, status, delivery_name, delivery_phone, delivery_address) VALUES (7581726569, 500.0, '💵 Готівка', 'new', 'Test User', '0681234567', 'вул. Литовська, 55');")
conn.commit()
conn.close()
print("Test order inserted.")
