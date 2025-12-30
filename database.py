import sqlite3
import logging
import json
import threading

DATABASE_FILE = 'smakota.db'
local_storage = threading.local()

def get_db_connection():
    """Get a thread-safe database connection."""
    conn = getattr(local_storage, 'connection', None)
    if conn is None:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        setattr(local_storage, 'connection', conn)
    return conn

def setup_database():
    """Create the database tables if they don't exist."""
    try:
        # Use a temporary, separate connection for setup to ensure it's closed
        conn = sqlite3.connect(DATABASE_FILE)
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
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')

        # Cart table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY (user_id, item_id),
                FOREIGN KEY (item_id) REFERENCES items (id)
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
    logging.info(f"Set state for user {user_id} to {state}")

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
    logging.info(f"Cleared state for user {user_id}")
    
# --- Menu Functions ---

def get_categories():
    """Fetch all categories from the database."""
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    return categories

def get_items_by_category(category_id):
    """Fetch all items for a given category."""
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items WHERE category_id = ?', (category_id,)).fetchall()
    return items

def get_item_by_id(item_id):
    """Fetch a single item by its ID."""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    return item
    
def get_category_name_by_id(category_id):
    """Fetch a category name by its ID."""
    conn = get_db_connection()
    category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
    return category['name'] if category else "Невідома категорія"

# --- Cart Functions ---

def add_to_cart(user_id, item_id, quantity=1):
    """Add an item to a user's cart or update its quantity."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if the item is already in the cart
    cursor.execute('SELECT quantity FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id))
    result = cursor.fetchone()
    
    if result:
        # Update quantity
        new_quantity = result['quantity'] + quantity
        cursor.execute('UPDATE cart_items SET quantity = ? WHERE user_id = ? AND item_id = ?', (new_quantity, user_id, item_id))
    else:
        # Insert new item
        cursor.execute('INSERT INTO cart_items (user_id, item_id, quantity) VALUES (?, ?, ?)', (user_id, item_id, quantity))
        
    conn.commit()
    logging.info(f"Item {item_id} added to cart for user {user_id}")

def get_cart_items(user_id):
    """Fetch all items in a user's cart."""
    conn = get_db_connection()
    # Join cart_items with items to get full item details
    cart_items = conn.execute('''
        SELECT items.name, items.price, cart_items.quantity 
        FROM cart_items
        JOIN items ON cart_items.item_id = items.id
        WHERE cart_items.user_id = ?
    ''', (user_id,)).fetchall()
    return cart_items

def clear_cart(user_id):
    """Remove all items from a user's cart."""
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()
    logging.info(f"Cart cleared for user {user_id}")
