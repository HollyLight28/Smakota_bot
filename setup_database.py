# -*- coding: utf-8 -*-
import sqlite3
import logging
import os
from database import setup_database, DATABASE_FILE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# This is the menu data copied from the original bot.py
MENU_DATA = {
    "categories": [
        {"id": "salads", "name": ""},
        {"id": "soups", "name": ""},
        {"id": "main_dishes", "name": ""},
        {"id": "desserts", "name": ""},
        {"id": "drinks", "name": ""},
        {"id": "snacks", "name": ""}
    ],
    "items": [
        # Salads
        {"id": 1, "name": "", "price": 120, "category": "salads", "description": ""},
        {"id": 2, "name": "", "price": 100, "category": "salads", "description": ""},
        {"id": 3, "name": "", "price": 85, "category": "salads", "description": ""},
        {"id": 4, "name": "", "price": 75, "category": "salads", "description": ""},
        {"id": 5, "name": "", "price": 130, "category": "salads", "description": ""},
        
        # Soups
        {"id": 6, "name": "", "price": 95, "category": "soups", "description": ""},
        {"id": 7, "name": "", "price": 70, "category": "soups", "description": ""},
        {"id": 8, "name": "", "price": 80, "category": "soups", "description": ""},
        {"id": 9, "name": "", "price": 110, "category": "soups", "description": ""},
        {"id": 10, "name": "", "price": 85, "category": "soups", "description": ""},
        
        # Main dishes
        {"id": 11, "name": "", "price": 140, "category": "main_dishes", "description": ""},
        {"id": 12, "name": "", "price": 220, "category": "main_dishes", "description": ""},
        {"id": 13, "name": "", "price": 150, "category": "main_dishes", "description": ""},
        {"id": 14, "name": "", "price": 110, "category": "main_dishes", "description": ""},
        {"id": 15, "name": "", "price": 160, "category": "main_dishes", "description": ""},
        {"id": 16, "name": "", "price": 130, "category": "main_dishes", "description": ""},
        {"id": 17, "name": "", "price": 180, "category": "main_dishes", "description": ""},
        {"id": 18, "name": "", "price": 90, "category": "main_dishes", "description": ""},
        {"id": 19, "name": "", "price": 125, "category": "main_dishes", "description": ""},
        {"id": 20, "name": "", "price": 100, "category": "main_dishes", "description": ""},
        
        # Desserts
        {"id": 21, "name": "", "price": 80, "category": "desserts", "description": ""},
        {"id": 22, "name": "", "price": 75, "category": "desserts", "description": ""},
        {"id": 23, "name": "", "price": 90, "category": "desserts", "description": ""},
        {"id": 24, "name": "", "price": 45, "category": "desserts", "description": ""},
        {"id": 25, "name": "", "price": 45, "category": "desserts", "description": ""},
        {"id": 26, "name": "", "price": 50, "category": "desserts", "description": ""},
        {"id": 27, "name": "", "price": 70, "category": "desserts", "description": ""},
        {"id": 28, "name": "", "price": 65, "category": "desserts", "description": ""},
        {"id": 29, "name": "", "price": 85, "category": "desserts", "description": ""},
        {"id": 30, "name": "", "price": 60, "category": "desserts", "description": ""},
        
        # Drinks
        {"id": 31, "name": "", "price": 35, "category": "drinks", "description": ""},
        {"id": 32, "name": "", "price": 45, "category": "drinks", "description": ""},
        {"id": 33, "name": "", "price": 45, "category": "drinks", "description": ""},
        {"id": 34, "name": "", "price": 25, "category": "drinks", "description": ""},
        {"id": 35, "name": "", "price": 25, "category": "drinks", "description": ""},
        {"id": 36, "name": "", "price": 30, "category": "drinks", "description": ""},
        {"id": 37, "name": "", "price": 40, "category": "drinks", "description": ""},
        {"id": 38, "name": "", "price": 40, "category": "drinks", "description": ""},
        {"id": 39, "name": "", "price": 35, "category": "drinks", "description": ""},
        {"id": 40, "name": "", "price": 20, "category": "drinks", "description": ""},
        {"id": 41, "name": "", "price": 20, "category": "drinks", "description": ""},
        {"id": 42, "name": "", "price": 55, "category": "drinks", "description": ""},
        {"id": 43, "name": "", "price": 60, "category": "drinks", "description": ""},
        {"id": 44, "name": "", "price": 30, "category": "drinks", "description": ""},
        {"id": 45, "name": "", "price": 35, "category": "drinks", "description": ""},
        
        # Snacks
        {"id": 46, "name": "", "price": 50, "category": "snacks", "description": ""},
        {"id": 47, "name": "", "price": 70, "category": "snacks", "description": ""},
        {"id": 48, "name": "", "price": 85, "category": "snacks", "description": ""},
        {"id": 49, "name": "", "price": 60, "category": "snacks", "description": ""},
        {"id": 50, "name": "", "price": 65, "category": "snacks", "description": ""},
        {"id": 51, "name": "", "price": 75, "category": "snacks", "description": ""},
        {"id": 52, "name": "", "price": 40, "category": "snacks", "description": ""},
        {"id": 53, "name": "", "price": 35, "category": "snacks", "description": ""},
        {"id": 54, "name": "", "price": 45, "category": "snacks", "description": ""},
        {"id": 55, "name": "", "price": 60, "category": "snacks", "description": ""},
        {"id": 56, "name": "", "price": 70, "category": "snacks", "description": ""},
        {"id": 57, "name": "", "price": 55, "category": "snacks", "description": ""},
        {"id": 58, "name": "", "price": 65, "category": "snacks", "description": ""},
        {"id": 59, "name": "", "price": 75, "category": "snacks", "description": ""},
        {"id": 60, "name": "", "price": 80, "category": "snacks", "description": ""},
        
        # Additional items to reach ~100
        {"id": 61, "name": "", "price": 150, "category": "salads", "description": ""},
        {"id": 62, "name": "", "price": 160, "category": "salads", "description": ""},
        {"id": 63, "name": "", "price": 110, "category": "salads", "description": ""},
        {"id": 64, "name": "", "price": 130, "category": "salads", "description": ""},
        {"id": 65, "name": "", "price": 170, "category": "salads", "description": ""},
        {"id": 66, "name": "", "price": 85, "category": "soups", "description": ""},
        {"id": 67, "name": "", "price": 90, "category": "soups", "description": ""},
        {"id": 68, "name": "", "price": 75, "category": "soups", "description": ""},
        {"id": 69, "name": "", "price": 95, "category": "soups", "description": ""},
        {"id": 70, "name": "", "price": 80, "category": "soups", "description": ""},
        {"id": 71, "name": "", "price": 140, "category": "main_dishes", "description": ""},
        {"id": 72, "name": "", "price": 135, "category": "main_dishes", "description": ""},
        {"id": 73, "name": "", "price": 145, "category": "main_dishes", "description": ""},
        {"id": 74, "name": "", "price": 170, "category": "main_dishes", "description": ""},
        {"id": 75, "name": "", "price": 165, "category": "main_dishes", "description": ""},
        {"id": 76, "name": "", "price": 120, "category": "main_dishes", "description": ""},
        {"id": 77, "name": "", "price": 130, "category": "main_dishes", "description": ""},
        {"id": 78, "name": "", "price": 150, "category": "main_dishes", "description": ""},
        {"id": 79, "name": "", "price": 140, "category": "main_dishes", "description": ""},
        {"id": 80, "name": "", "price": 135, "category": "main_dishes", "description": ""},
        {"id": 81, "name": "", "price": 45, "category": "desserts", "description": ""},
        {"id": 82, "name": "", "price": 45, "category": "desserts", "description": ""},
        {"id": 83, "name": "", "price": 50, "category": "desserts", "description": ""},
        {"id": 84, "name": "", "price": 55, "category": "desserts", "description": ""},
        {"id": 85, "name": "", "price": 55, "category": "desserts", "description": ""},
        {"id": 86, "name": "", "price": 30, "category": "drinks", "description": ""},
        {"id": 87, "name": "", "price": 50, "category": "drinks", "description": ""},
        {"id": 88, "name": "", "price": 55, "category": "drinks", "description": ""},
        {"id": 89, "name": "", "price": 40, "category": "drinks", "description": ""},
        {"id": 90, "name": "", "price": 35, "category": "drinks", "description": ""},
        {"id": 91, "name": "", "price": 60, "category": "drinks", "description": ""},
        {"id": 92, "name": "", "price": 60, "category": "drinks", "description": ""},
        {"id": 93, "name": "", "price": 65, "category": "drinks", "description": ""},
        {"id": 94, "name": "", "price": 70, "category": "drinks", "description": ""},
        {"id": 95, "name": "", "price": 65, "category": "drinks", "description": ""},
        {"id": 96, "name": "", "price": 75, "category": "desserts", "description": ""},
        {"id": 97, "name": "", "price": 50, "category": "desserts", "description": ""},
        {"id": 98, "name": "", "price": 85, "category": "main_dishes", "description": ""},
        {"id": 99, "name": "", "price": 75, "category": "desserts", "description": ""},
        {"id": 100, "name": "", "price": 80, "category": "desserts", "description": ""}
    ]
}

def populate_database():
    """Populate the database with the menu data."""
    # First, ensure the DB file and tables are created
    setup_database()
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Check if already populated
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] > 0:
            logging.warning("Database already contains data. Skipping population.")
            conn.close()
            return

        # Populate categories
        categories_to_insert = [(cat['id'], cat['name']) for cat in MENU_DATA['categories']]
        cursor.executemany("INSERT INTO categories (id, name) VALUES (?, ?)", categories_to_insert)
        logging.info(f"Inserted {len(categories_to_insert)} categories.")

        # Populate items
        items_to_insert = [
            (
                item['id'], 
                item['name'], 
                item['price'], 
                item['category'], 
                item['description']
            ) for item in MENU_DATA['items']
        ]
        cursor.executemany("INSERT INTO items (id, name, price, category_id, description) VALUES (?, ?, ?, ?, ?)", items_to_insert)
        logging.info(f"Inserted {len(items_to_insert)} items.")

        conn.commit()
        conn.close()
        logging.info("Successfully populated the database with menu data.")

    except sqlite3.Error as e:
        logging.error(f"Database error during population: {e}")

if __name__ == "__main__":
    # Check if the database file exists, if so, ask for confirmation to avoid accidental overwrites
    if os.path.exists(DATABASE_FILE):
        confirm = input(f"Database file '{DATABASE_FILE}' already exists. 
This script will only add data if the tables are empty. 
Do you want to proceed? (y/n): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            exit()
            
    populate_database()
