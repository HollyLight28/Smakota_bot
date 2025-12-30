import sqlite3
import logging

DATABASE_FILE = 'smakota.db'

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Create the database tables if they don't exist."""
    try:
        conn = get_db_connection()
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
        
        conn.commit()
        conn.close()
        logging.info("Database setup complete. Tables are ready.")
    except sqlite3.Error as e:
        logging.error(f"Database error during setup: {e}")

# --- Menu Functions ---

def get_categories():
    """Fetch all categories from the database."""
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    return categories

def get_items_by_category(category_id):
    """Fetch all items for a given category."""
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items WHERE category_id = ?', (category_id,)).fetchall()
    conn.close()
    return items

def get_item_by_id(item_id):
    """Fetch a single item by its ID."""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return item
    
def get_category_name_by_id(category_id):
    """Fetch a category name by its ID."""
    conn = get_db_connection()
    category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
    conn.close()
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
    conn.close()
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
    conn.close()
    return cart_items

def clear_cart(user_id):
    """Remove all items from a user's cart."""
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    logging.info(f"Cart cleared for user {user_id}")
