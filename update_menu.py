# -*- coding: utf-8 -*-
import sqlite3
import csv
import logging
import re
import os
import hashlib
from database import DATABASE_FILE, setup_database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CSV_FILE = 'menu.csv'

import hashlib

def slugify(text):
    """Generates a URL-friendly slug from a string with collision avoidance."""
    text_orig = text
    text = text.lower()
    # Basic transliteration for Ukrainian characters
    ua_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
        'є': 'ie', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i',
        'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia'
    }
    for ua, en in ua_map.items():
        text = text.replace(ua, en)
    
    # Replace spaces and remove invalid characters
    text = re.sub(r'[^\w\s-]', '', text).strip()
    text = re.sub(r'\s+', '-', text)
    
    # If slug is empty or too short, or to ensure uniqueness for similar names
    if not text:
        text = "cat"
    
    # Add a short hash of the original name to prevent collisions (e.g., "Піца!" vs "Піца?")
    short_hash = hashlib.md5(text_orig.encode()).hexdigest()[:4]
    return f"{text}-{short_hash}"

def parse_price(price_str):
    """Extracts a number from a price string like '40 грн.'."""
    if not price_str:
        return 0.0
    # Find all digits and dots, then join them
    price_parts = re.findall(r'\d+\.?\d*', str(price_str))
    if price_parts:
        return float(price_parts[0])
    return 0.0

def update_menu_from_csv():
    """Update menu from CSV without full deletion to preserve cart items."""
    if not os.path.exists(CSV_FILE):
        logging.error(f"'{CSV_FILE}' not found. Please make sure the file exists.")
        return

    setup_database()

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Read CSV and prepare data ---
        with open(CSV_FILE, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Fetch existing items to preserve IDs
            cursor.execute("SELECT id, name FROM items")
            existing_items = {row['name']: row['id'] for row in cursor.fetchall()}
            
            active_item_ids = []

            for row in reader:
                category_name = row.get('Category', '').strip()
                item_name = row.get('Item Name', '').strip()
                
                if not category_name or not item_name:
                    continue

                # --- Handle Categories ---
                category_id = slugify(category_name)
                cursor.execute('INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)', (category_id, category_name))

                # --- Handle Items ---
                price = parse_price(row.get('Price', ''))
                description = row.get('Description', '').strip()
                weight = row.get('Weight', '').strip()
                full_description = f"{description} ({weight})" if description and weight else description or weight

                item_id = existing_items.get(item_name)
                
                if item_id:
                    cursor.execute('''
                        UPDATE items 
                        SET name=?, price=?, category_id=?, description=?, is_active=1
                        WHERE id=?
                    ''', (item_name, price, category_id, full_description, item_id))
                    active_item_ids.append(item_id)
                else:
                    cursor.execute('''
                        INSERT INTO items (name, price, category_id, description, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (item_name, price, category_id, full_description))
                    active_item_ids.append(cursor.lastrowid)

        # Deactivate items not in the CSV
        if active_item_ids:
            placeholders = ','.join(['?'] * len(active_item_ids))
            cursor.execute(f'UPDATE items SET is_active = 0 WHERE id NOT IN ({placeholders})', active_item_ids)
        else:
            cursor.execute('UPDATE items SET is_active = 0')

        conn.commit()
        conn.close()
        logging.info("Successfully updated the database menu from CSV (non-destructive).")

    except (sqlite3.Error, IOError, csv.Error) as e:
        logging.error(f"An error occurred during menu update: {e}")

    except (sqlite3.Error, IOError, csv.Error) as e:
        logging.error(f"An error occurred during menu update: {e}")

if __name__ == "__main__":
    update_menu_from_csv()
