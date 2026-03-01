# -*- coding: utf-8 -*-
import logging
import re
import requests
import csv
import threading
import hashlib
from io import StringIO
import database as db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Link to your Google Sheet (CSV Export)
SHEET_ID = "1MMCrn_kcJjJ3Nr2hMOsl4UabZnKO3Hi9"
GID = "0"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# Global lock for updates
update_lock = threading.Lock()

import hashlib

def slugify(text):
    """Generates a URL-friendly slug from a string with collision avoidance."""
    text_orig = text
    text = text.lower()
    ua_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
        'є': 'ie', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i',
        'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia'
    }
    for ua, en in ua_map.items():
        text = text.replace(ua, en)
    
    text = re.sub(r'[^\w\s-]', '', text).strip()
    text = re.sub(r'\s+', '-', text)
    
    if not text:
        text = "cat"
    
    short_hash = hashlib.md5(text_orig.encode()).hexdigest()[:4]
    return f"{text}-{short_hash}"

def parse_price(price_str):
    if not price_str:
        return 0.0
    price_parts = re.findall(r'\d+\.?\d*', str(price_str))
    if price_parts:
        return float(price_parts[0])
    return 0.0

def update_menu_from_json():
    """Fetches data from Google Sheets and updates the database securely."""
    
    with update_lock:
        db.setup_database()

        try:
            logging.info("Fetching menu from Google Sheets...")
            response = requests.get(SHEET_URL)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                logging.error(f"Failed to fetch Google Sheet. Status code: {response.status_code}")
                return

            csv_data = StringIO(response.text)
            reader = csv.DictReader(csv_data)

            # Get existing items map: Name -> ID
            existing_items = db.get_all_item_names()
            updated_item_ids = []

            for row in reader:
                category_name = row.get('Category', '').strip()
                item_name = row.get('Item Name', '').strip()
                
                if not category_name or not item_name:
                    continue

                # Handle Category
                category_id = slugify(category_name)
                db.upsert_category(category_id, category_name)

                # Handle Item
                price = parse_price(row.get('Price', ''))
                description = row.get('Description', '').strip()
                weight = row.get('Weight', '').strip()
                image_url = row.get('Image URL', '').strip() or None
                
                # Check if item exists to preserve ID
                item_id = existing_items.get(item_name)
                
                db.upsert_item(item_name, price, category_id, description, weight, image_url, item_id)
                
                # If we just inserted a new item, we need its ID.
                # Since upsert_item doesn't return ID easily without extra query, 
                # we can re-fetch or assume if it was None, it's a new ID.
                # Optimisation: Let's fetch the ID again if it was None, or use the existing one.
                if item_id:
                    updated_item_ids.append(item_id)
                else:
                    # New item, we need to find its ID to add to updated_list
                    # This is slightly inefficient but safe.
                    # Alternatively, we can just rely on name matching again later, 
                    # but database.py's upsert_item handles update by ID.
                    # Let's refresh the map briefly or just fetch this specific item ID.
                    # For simplicity/robustness: fetch ID by name.
                    new_item_row = db.get_db_connection().execute("SELECT id FROM items WHERE name = ?", (item_name,)).fetchone()
                    if new_item_row:
                        updated_item_ids.append(new_item_row['id'])

            # Deactivate items that were not in the CSV
            db.deactivate_other_items(updated_item_ids)

            logging.info(f"Successfully updated menu. Active items: {len(updated_item_ids)}")

        except Exception as e:
            logging.error(f"An error occurred during menu update: {e}")

if __name__ == "__main__":
    update_menu_from_json()
