import sqlite3
import logging
import json
import threading
from datetime import datetime

DATABASE_FILE = 'smakota.db'
local_storage = threading.local()

def get_db_connection():
    """Get a thread-safe database connection."""
    conn = getattr(local_storage, 'connection', None)
    if conn is None:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON") # Enable Foreign Keys
        setattr(local_storage, 'connection', conn)
    return conn

def setup_database():
    """Create the database tables if they don't exist and perform migrations."""
    try:
        # Use a temporary, separate connection for setup
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        
        # Items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category_id TEXT NOT NULL,
                description TEXT,
                weight TEXT,
                image_url TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')

        # Migration: Check if columns exist
        cursor.execute("PRAGMA table_info(items)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'is_active' not in columns:
            logging.info("Migrating database: Adding is_active column to items table.")
            cursor.execute("ALTER TABLE items ADD COLUMN is_active INTEGER DEFAULT 1")
        if 'image_url' not in columns:
            logging.info("Migrating database: Adding image_url column to items table.")
            cursor.execute("ALTER TABLE items ADD COLUMN image_url TEXT")

        # Cart table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY (user_id, item_id),
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
            )
        ''')
        
        # User states for FSM
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                data TEXT
            )
        ''')

        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_name TEXT,
                delivery_phone TEXT,
                delivery_address TEXT,
                comment TEXT,
                courier_id INTEGER,
                batch_id INTEGER,
                route_order INTEGER,
                cash_confirmed INTEGER DEFAULT 0
            )
        ''')

        # Users table for mailing and tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_role TEXT
            )
        ''')

        # Mailing templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mailing_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')

        # Order Items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            )
        ''')

        # Couriers table — MUST be created BEFORE shift_status migration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS couriers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                chat_id INTEGER NOT NULL
            )
        ''')

        # Hall staff table (Waitresses)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hall_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                chat_id INTEGER NOT NULL
            )
        ''')

        # Shopping list table (for Kitchen)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL UNIQUE,
                quantity TEXT DEFAULT '0',
                category TEXT DEFAULT 'general'
            )
        ''')

        # Templates for common items
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shopping_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL UNIQUE
            )
        ''')



        # Chefs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chefs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                chat_id INTEGER NOT NULL
            )
        ''')

        # Create route_batches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS route_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                courier_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # ========== MIGRATIONS (after all tables exist) ==========

        # Migration: users.current_role
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'current_role' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN current_role TEXT")

        # Migration: couriers.shift_status
        cursor.execute("PRAGMA table_info(couriers)")
        courier_columns = [info[1] for info in cursor.fetchall()]
        if 'shift_status' not in courier_columns:
            cursor.execute("ALTER TABLE couriers ADD COLUMN shift_status TEXT DEFAULT 'off'")

        # Migration: orders.hall_staff_id, courier_id, batch_id, route_order
        cursor.execute("PRAGMA table_info(orders)")
        order_columns = [info[1] for info in cursor.fetchall()]
        if 'hall_staff_id' not in order_columns:
            logging.info("Migrating database: Adding hall_staff_id column to orders table.")
            cursor.execute("ALTER TABLE orders ADD COLUMN hall_staff_id INTEGER")
        if 'courier_id' not in order_columns:
            logging.info("Migrating database: Adding courier_id column to orders table.")
            cursor.execute("ALTER TABLE orders ADD COLUMN courier_id INTEGER")
        if 'batch_id' not in order_columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN batch_id INTEGER")
        if 'route_order' not in order_columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN route_order INTEGER")
        if 'scheduled_time' not in order_columns:
            logging.info("Migrating database: Adding scheduled_time column.")
            cursor.execute("ALTER TABLE orders ADD COLUMN scheduled_time TEXT")
        if 'reminded' not in order_columns:
            logging.info("Migrating database: Adding reminded column.")
            cursor.execute("ALTER TABLE orders ADD COLUMN reminded INTEGER DEFAULT 0")

        # Seed: shopping templates
        cursor.execute("SELECT COUNT(*) FROM shopping_templates")
        if cursor.fetchone()[0] == 0:
            default_items = [
                ('Борошно',), ('Олія',), ('Цукор',), ('М\'ясо',), 
                ('Картопля',), ('Яйця',), ('Молоко',), ('Сир',)
            ]
            cursor.executemany('INSERT INTO shopping_templates (item_name) VALUES (?)', default_items)

        conn.commit()
        conn.close()
        logging.info("Database setup complete. Tables are ready.")
    except sqlite3.Error as e:
        logging.error(f"Database error during setup: {e}")

# --- FSM State Functions ---

def set_user_state(user_id, state, data=None):
    """Set or update a user's state in the FSM."""
    conn = get_db_connection()
    data_json = json.dumps(data) if data is not None else None
    conn.execute(
        'INSERT OR REPLACE INTO user_states (user_id, state, data) VALUES (?, ?, ?)',
        (user_id, state, data_json)
    )
    conn.commit()

def get_user_state(user_id):
    """Get a user's state from the FSM."""
    conn = get_db_connection()
    row = conn.execute('SELECT state, data FROM user_states WHERE user_id = ?', (user_id,)).fetchone()
    if row:
        data = json.loads(row['data']) if row['data'] is not None else {}
        return {'state': row['state'], 'data': data}
    return None

def clear_user_state(user_id):
    """Clear a user's state from the FSM."""
    conn = get_db_connection()
    conn.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))
    conn.commit()
    
# --- Menu Functions ---

def upsert_category(cat_id, name):
    """Insert or update a category."""
    conn = get_db_connection()
    conn.execute('INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)', (cat_id, name))
    conn.commit()

def get_all_item_names():
    """Get a dictionary of {name: id} for all items."""
    conn = get_db_connection()
    rows = conn.execute('SELECT id, name FROM items').fetchall()
    return {row['name']: row['id'] for row in rows}

def upsert_item(name, price, category_id, description, weight, image_url=None, item_id=None):
    """Insert or update an item. If item_id is provided, update that specific item."""
    conn = get_db_connection()
    if item_id:
        conn.execute('''
            UPDATE items 
            SET name=?, price=?, category_id=?, description=?, weight=?, image_url=?, is_active=1
            WHERE id=?
        ''', (name, price, category_id, description, weight, image_url, item_id))
    else:
        conn.execute('''
            INSERT INTO items (name, price, category_id, description, weight, image_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (name, price, category_id, description, weight, image_url))
    conn.commit()

def deactivate_items_not_in_list(active_names):
    """Set is_active=0 for all items whose names are not in the active_names list."""
    conn = get_db_connection()
    if not active_names:
        conn.execute('UPDATE items SET is_active = 0')
    else:
        placeholders = ','.join(['?'] * len(active_names))
        sql = f'UPDATE items SET is_active = 0 WHERE name NOT IN ({placeholders})'
        conn.execute(sql, active_names)
    conn.commit()

def get_categories():
    """Fetch all categories."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM categories').fetchall()

def get_items_by_category(category_id):
    """Fetch active items for a category."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM items WHERE category_id = ? AND is_active = 1', (category_id,)).fetchall()

def get_item_by_id(item_id):
    """Fetch a single item."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    
def get_category_name_by_id(category_id):
    """Fetch a category name."""
    conn = get_db_connection()
    category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
    return category['name'] if category else "Невідома категорія"

# --- Cart Functions ---

def add_to_cart(user_id, item_id, quantity=1):
    """Add item to cart or increase quantity."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check current quantity
    row = cursor.execute('SELECT quantity FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id)).fetchone()
    
    if row:
        new_quantity = row['quantity'] + quantity
        cursor.execute('UPDATE cart_items SET quantity = ? WHERE user_id = ? AND item_id = ?', (new_quantity, user_id, item_id))
    else:
        cursor.execute('INSERT INTO cart_items (user_id, item_id, quantity) VALUES (?, ?, ?)', (user_id, item_id, quantity))
        
    conn.commit()

def update_cart_quantity(user_id, item_id, change):
    """Increment or decrement item quantity. Removes item if quantity <= 0."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    row = cursor.execute('SELECT quantity FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id)).fetchone()
    if not row:
        return
    
    new_quantity = row['quantity'] + change
    
    if new_quantity <= 0:
        cursor.execute('DELETE FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id))
    else:
        cursor.execute('UPDATE cart_items SET quantity = ? WHERE user_id = ? AND item_id = ?', (new_quantity, user_id, item_id))
    
    conn.commit()

def remove_from_cart(user_id, item_id):
    """Remove specific item from cart."""
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id))
    conn.commit()

def get_cart_items(user_id):
    """Fetch all items in a user's cart (only active items)."""
    conn = get_db_connection()
    cart_items = conn.execute('''
        SELECT items.id, items.name, items.price, cart_items.quantity 
        FROM cart_items
        JOIN items ON cart_items.item_id = items.id
        WHERE cart_items.user_id = ? AND items.is_active = 1
    ''', (user_id,)).fetchall()
    return cart_items

def clear_cart(user_id):
    """Remove all items from a user's cart."""
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()

# --- Order Functions ---

def create_order(user_id, total_amount, payment_method, delivery_data, cart_items):
    """Creates a new order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO orders (user_id, total_amount, payment_method, delivery_name, delivery_phone, delivery_address, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, 
            total_amount, 
            payment_method, 
            delivery_data.get('name'), 
            delivery_data.get('contact'), 
            delivery_data.get('address'), 
            delivery_data.get('comment')
        ))
        
        order_id = cursor.lastrowid
        
        items_to_insert = []
        for item in cart_items:
            # item has 'name', 'price', 'quantity'
            items_to_insert.append((order_id, item['name'], item['quantity'], item['price']))
            
        cursor.executemany('''
            INSERT INTO order_items (order_id, item_name, quantity, price)
            VALUES (?, ?, ?, ?)
        ''', items_to_insert)
        
        conn.commit()
        return order_id
        
    except sqlite3.Error as e:
        logging.error(f"Failed to create order: {e}")
        conn.rollback()
        return None

def get_order_by_id(order_id):
    conn = get_db_connection()
    return conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

def get_active_orders():
    """Fetches all orders that are not completed or cancelled."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM orders WHERE status NOT IN ("completed", "cancelled") ORDER BY created_at DESC').fetchall()

# --- Courier Functions ---

def assign_courier(order_id, courier_id):
    """Assigns an order to a courier."""
    conn = get_db_connection()
    # Якщо замовлення було відкладене — тепер воно в дорозі
    conn.execute('UPDATE orders SET courier_id = ?, status = "delivery" WHERE id = ?', (courier_id, order_id))
    conn.commit()

def get_orders_to_remind():
    """Повертає замовлення, про які треба нагадати шефу (за 60 хв до часу)."""
    conn = get_db_connection()
    # Тільки ті, де статус 'scheduled' і ще не нагадували
    return conn.execute('''
        SELECT * FROM orders 
        WHERE status = 'scheduled' AND reminded = 0 
        AND scheduled_time IS NOT NULL
    ''').fetchall()

def mark_as_reminded(order_id):
    conn = get_db_connection()
    conn.execute('UPDATE orders SET reminded = 1 WHERE id = ?', (order_id,))
    conn.commit()

def set_order_scheduled(order_id, time_str):
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = "scheduled", scheduled_time = ? WHERE id = ?', (time_str, order_id))
    conn.commit()

def get_courier_active_orders(courier_id):
    """Fetches active orders for a specific courier."""
    conn = get_db_connection()
    return conn.execute('''
        SELECT * FROM orders 
        WHERE courier_id = ? AND status IN ("delivery", "assigned")
        ORDER BY CASE WHEN route_order IS NULL THEN 999 ELSE route_order END ASC
    ''', (courier_id,)).fetchall()

def create_route_batch(courier_id, order_ids):
    """Creates a batch of orders for a courier in a specific sequence."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO route_batches (courier_id) VALUES (?)', (courier_id,))
        batch_id = cursor.lastrowid
        for index, order_id in enumerate(order_ids):
            cursor.execute('''
                UPDATE orders 
                SET batch_id = ?, route_order = ?, courier_id = ?, status = "delivery" 
                WHERE id = ?
            ''', (batch_id, index + 1, courier_id, order_id))
        conn.commit()
        return batch_id
    except sqlite3.Error as e:
        logging.error(f"Error creating batch: {e}")
        conn.rollback()
        return None

def update_order_status(order_id, status):
    """Updates the status of an order."""
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()

def get_hall_staff():
    """Fetches all registered hall staff."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM hall_staff').fetchall()

def add_hall_staff(name, chat_id):
    """Adds a new hall staff member."""
    conn = get_db_connection()
    conn.execute('INSERT INTO hall_staff (name, chat_id) VALUES (?, ?)', (name, chat_id))
    conn.commit()

def remove_user_from_roles(chat_id):
    """Removes a user from all staff roles (courier, hall, etc)."""
    conn = get_db_connection()
    conn.execute('DELETE FROM couriers WHERE chat_id = ?', (chat_id,))
    conn.execute('DELETE FROM hall_staff WHERE chat_id = ?', (chat_id,))
    conn.commit()

def get_shopping_templates():
    """Fetches pre-defined shopping items."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM shopping_templates ORDER BY item_name ASC').fetchall()

def add_shopping_template(name):
    """Adds a new pre-defined item template."""
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO shopping_templates (item_name) VALUES (?)', (name,))
    conn.commit()

# --- Shopping List Functions ---

def get_shopping_list():
    """Fetches the entire shopping list."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM shopping_list ORDER BY item_name ASC').fetchall()

def upsert_shopping_item(name, quantity='0'):
    """Adds or updates a shopping list item."""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO shopping_list (item_name, quantity) 
        VALUES (?, ?)
        ON CONFLICT(item_name) DO UPDATE SET quantity = excluded.quantity
    ''', (name, quantity))
    conn.commit()

def delete_shopping_item(item_id):
    """Removes an item from the shopping list."""
    conn = get_db_connection()
    conn.execute('DELETE FROM shopping_list WHERE id = ?', (item_id,))
    conn.commit()



def get_chefs():
    """Fetches all registered chefs."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM chefs').fetchall()

def get_couriers():
    """Fetches all registered couriers."""
    conn = get_db_connection()
    return conn.execute('SELECT * FROM couriers').fetchall()

def add_courier(name, chat_id):
    """Adds a new courier."""
    conn = get_db_connection()
    conn.execute('INSERT INTO couriers (name, chat_id) VALUES (?, ?)', (name, chat_id))
    conn.commit()



def add_chef(name, chat_id):
    """Adds a new chef."""
    conn = get_db_connection()
    conn.execute('INSERT INTO chefs (name, chat_id) VALUES (?, ?)', (name, chat_id))
    conn.commit()

def get_daily_report(courier_id):
    """Calculates total cash collected by a courier for today."""
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = conn.execute('''
        SELECT COUNT(*) as count, SUM(total_amount) as total
        FROM orders 
        WHERE courier_id = ? 
        AND status = 'completed'
        AND payment_method = '💵 Готівка'
        AND date(created_at) = ?
    ''', (courier_id, today)).fetchone()
    
    return result['count'], result['total'] if result['total'] else 0.0

# --- User History / Profile ---

def get_last_order(user_id):
    """Fetches the details of the user's last completed or new order."""
    conn = get_db_connection()
    return conn.execute('''
        SELECT delivery_name, delivery_phone, delivery_address 
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id,)).fetchone()

# --- Testing / Role Switch Functions ---

def remove_courier_by_chat_id(chat_id):
    """Removes a courier from the database (for testing roles)."""
    conn = get_db_connection()
    conn.execute('DELETE FROM couriers WHERE chat_id = ?', (chat_id,))
    conn.commit()

def get_last_order_data(chat_id):
    """Отримує дані останнього замовлення користувача для автозаповнення."""
    conn = get_db_connection()
    res = conn.execute('''
        SELECT delivery_name, delivery_phone, delivery_address 
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 1
    ''', (chat_id,)).fetchone()
    return res if res else None

def set_user_current_role(chat_id, role):
    """Зберігає поточну вибрану роль користувача."""
    conn = get_db_connection()
    conn.execute('UPDATE users SET current_role = ? WHERE chat_id = ?', (role, chat_id))
    conn.commit()

def get_user_current_role(chat_id):
    """Повертає поточну роль користувача."""
    conn = get_db_connection()
    res = conn.execute('SELECT current_role FROM users WHERE chat_id = ?', (chat_id,)).fetchone()
    return res['current_role'] if res and res['current_role'] else None
