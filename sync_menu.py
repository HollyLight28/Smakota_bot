import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os
import json
from database import upsert_category, upsert_item, deactivate_items_not_in_list, get_db_connection
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SyncMenu')

BASE_URL = "https://smakota.com.ua"
MENU_URL = f"{BASE_URL}/menu"

CATEGORY_MAP = {
    "Комплексні обіди": "kompleksni-obidy",
    "Основні страви": "osnovni-stravy",
    "Fast Food": "fast-food",
    "Піца": "pitsa",
    "Салати": "salaty",
    "Десерти": "deserty",
    "Напої": "napoi",
    "Страви на замовлення": "stravy-na-zamovlennya"
}

def export_for_webapp():
    conn = sqlite3.connect('smakota.db')
    conn.row_factory = sqlite3.Row
    items = conn.execute('SELECT * FROM items WHERE is_active = 1').fetchall()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    data = {
        'categories': [dict(c) for c in categories],
        'items': [dict(i) for i in items]
    }
    
    os.makedirs('webapp', exist_ok=True)
    with open('webapp/data.js', 'w', encoding='utf-8') as f:
        f.write(f"const menuData = {json.dumps(data, ensure_ascii=False)};")
    print("📂 Дані для WebApp оновлено у webapp/data.js")
    conn.close()

def sync():
    print(f"🚀 Починаємо синхронізацію меню з {MENU_URL}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(MENU_URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Помилка при завантаженні сайту: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    active_item_names = []

    product_divs = soup.select('div.rounded.shadow-lg')
    print(f"🔍 Знайдено потенційних страв: {len(product_divs)}")

    for i, div in enumerate(product_divs):
        try:
            prev_cat_p = div.find_previous('p', class_='text-center')
            cat_name = prev_cat_p.get_text(strip=True) if prev_cat_p else "Unknown"
            cat_id = CATEGORY_MAP.get(cat_name)
            
            if not cat_id: continue
            # Upsert category first (needed for FK constraint + WebApp)
            upsert_category(cat_id, cat_name)
            
            name_el = div.find('span', class_=lambda x: x and 'font-medium' in x and 'text-lg' in x)
            if not name_el: continue
            name = name_el.get_text(strip=True)

            desc_p = div.find('p', class_=lambda x: x and 'text-gray-500' in x)
            desc_full = desc_p.get_text(strip=True) if desc_p else ""
            
            weight_match = re.search(r'\((.*?)\)', desc_full)
            weight = weight_match.group(1) if weight_match else ""
            description = desc_full.replace(f"({weight})", "").strip()
            
            price_text = div.get_text(strip=True)
            price_match = re.search(r'Ціна:\s*(\d+)\s*грн', price_text)
            if price_match:
                price = float(price_match.group(1))
            else:
                price_b = div.find('b')
                price = float(re.sub(r'[^\d]', '', price_b.get_text())) if price_b else 0
            
            img_tag = div.find('img')
            img_url = ""
            if img_tag and 'src' in img_tag.attrs:
                src = img_tag['src']
                if src.startswith('..'):
                    img_url = BASE_URL + src.replace('..', '')
                elif src.startswith('/'):
                    img_url = BASE_URL + src
                else:
                    img_url = src
            
            conn = sqlite3.connect('smakota.db')
            conn.row_factory = sqlite3.Row
            existing = conn.execute('SELECT id FROM items WHERE name = ?', (name,)).fetchone()
            conn.close()
            
            item_id = existing['id'] if existing else None
            upsert_item(name, price, cat_id, description, weight, img_url, item_id)
            active_item_names.append(name)
            
        except Exception as e:
            logger.error(f"Sync item #{i} error: {e}")

    deactivate_items_not_in_list(active_item_names)
    export_for_webapp()
    print(f"\n✨ Синхронізація завершена! Оброблено страв: {len(active_item_names)}")

if __name__ == "__main__":
    sync()
