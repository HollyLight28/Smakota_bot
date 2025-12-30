# -*- coding: utf-8 -*-
import sqlite3
import csv
import logging
import re
import os
from database import DATABASE_FILE, setup_database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CSV_FILE = 'menu.csv'

def slugify(text):
    """Generates a URL-friendly slug from a string."""
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
    return text

def parse_price(price_str):
    """Extracts a number from a price string like '40 грн.'."""
    if not price_str:
        return 0.0
    # Find all digits and dots, then join them
    price_parts = re.findall(r'\d+\.?\d*', price_str)
    if price_parts:
        return float(price_parts[0])
    return 0.0

def update_menu_from_csv():
    """Clear existing menu and populate it from the CSV file."""
    if not os.path.exists(CSV_FILE):
        logging.error(f"'{CSV_FILE}' not found. Please make sure the file exists.")
        return

    # Ensure tables exist before doing anything
    setup_database()

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # --- Clear existing menu data ---
        cursor.execute("DELETE FROM items")
        cursor.execute("DELETE FROM categories")
        logging.info("Cleared 'items' and 'categories' tables.")

        # --- Read CSV and prepare data ---
        with open(CSV_FILE, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            categories = {} # To store unique categories: {name: id}
            items_to_insert = []

            for row in reader:
                category_name = row.get('Category', '').strip()
                item_name = row.get('Item Name', '').strip()
                
                if not category_name or not item_name:
                    continue

                # --- Handle Categories ---
                if category_name not in categories:
                    category_id = slugify(category_name)
                    categories[category_name] = category_id

                # --- Handle Items ---
                price = parse_price(row.get('Price', ''))
                
                # Combine description and weight for a full description
                description = row.get('Description', '').strip()
                weight = row.get('Weight', '').strip()
                full_description = f"{description} ({weight})" if description and weight else description or weight

                items_to_insert.append((
                    item_name,
                    price,
                    categories[category_name],
                    full_description
                ))

        # --- Insert data into database ---
        
        # Populate categories
        categories_to_insert = [(cat_id, cat_name) for cat_name, cat_id in categories.items()]
        cursor.executemany("INSERT INTO categories (id, name) VALUES (?, ?)", categories_to_insert)
        logging.info(f"Inserted {len(categories_to_insert)} new categories.")

        # Populate items
        cursor.executemany("INSERT INTO items (name, price, category_id, description) VALUES (?, ?, ?, ?)", items_to_insert)
        logging.info(f"Inserted {len(items_to_insert)} new items.")

        conn.commit()
        conn.close()
        logging.info("Successfully updated the database menu from CSV.")

    except (sqlite3.Error, IOError, csv.Error) as e:
        logging.error(f"An error occurred during menu update: {e}")

if __name__ == "__main__":
    update_menu_from_csv()
