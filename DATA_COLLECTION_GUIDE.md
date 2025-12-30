# Ефективне збирання даних з веб-сайтів для бота

Цей документ містить інформацію про те, як ефективно збирати дані з веб-сайтів для використання в Telegram-ботах.

## Методи збирання даних

### 1. Веб-скрейпінг (Web Scraping)

#### Використання бібліотеки BeautifulSoup
```python
from bs4 import BeautifulSoup
import requests

# Приклад збирання даних з веб-сторінки
url = "https://example-restaurant.com/menu"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Знаходження всіх елементів меню
menu_items = soup.find_all('div', class_='menu-item')

for item in menu_items:
    name = item.find('h3').text
    price = item.find('span', class_='price').text
    description = item.find('p', class_='description').text
    print(f"Назва: {name}, Ціна: {price}, Опис: {description}")
```

#### Використання Selenium (для динамічних сайтів)
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Налаштування Chrome для роботи без GUI
chrome_options = Options()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(options=chrome_options)

driver.get("https://example-restaurant.com/menu")

# Знаходження елементів
items = driver.find_elements(By.CLASS_NAME, "menu-item")

for item in items:
    name = item.find_element(By.TAG_NAME, "h3").text
    price = item.find_element(By.CLASS_NAME, "price").text
    print(f"Назва: {name}, Ціна: {price}")

driver.quit()
```

### 2. Використання API (якщо доступне)

Багато сайтів надають API для доступу до даних:

```python
import requests

# Приклад використання API
api_url = "https://api.example-restaurant.com/menu"
headers = {
    "Authorization": "Bearer your_api_key",
    "Content-Type": "application/json"
}

response = requests.get(api_url, headers=headers)
menu_data = response.json()

for item in menu_data['items']:
    print(f"Назва: {item['name']}, Ціна: {item['price']}")
```

### 3. Парсинг JSON-файлів

Деякі сайти зберігають дані в JSON-форматі:

```python
import requests
import json

# Завантаження JSON-даних
json_url = "https://example-restaurant.com/menu.json"
response = requests.get(json_url)
menu_data = response.json()

for category in menu_data:
    for item in category['items']:
        print(f"Категорія: {category['name']}, Назва: {item['name']}, Ціна: {item['price']}")
```

## Інструменти для автоматизації

### 1. Scrapy - потужний фреймворк для скрейпінгу

```bash
pip install scrapy
```

Приклад простого скрейпера:
```python
import scrapy

class MenuSpider(scrapy.Spider):
    name = "menu"
    start_urls = ["https://example-restaurant.com/menu"]

    def parse(self, response):
        for item in response.css('.menu-item'):
            yield {
                'name': item.css('h3::text').get(),
                'price': item.css('.price::text').get(),
                'description': item.css('p.description::text').get()
            }
```

### 2. Octoparse - візуальний інструмент (без коду)

Octoparse дозволяє створювати скрейпери за допомогою інтерфейсу без написання коду.

### 3. Import.io - ще один інструмент без коду

## Автоматизація оновлення даних

### Збереження даних у JSON для подальшого використання

```python
import json
from datetime import datetime

def save_menu_to_json(menu_data, filename="menu_data.json"):
    data = {
        "last_updated": datetime.now().isoformat(),
        "items": menu_data
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Приклад використання
menu_items = [
    {"id": 1, "name": "Борщ", "price": 80, "category": "soups"},
    {"id": 2, "name": "Котлета", "price": 120, "category": "main_dishes"}
]

save_menu_to_json(menu_items)
```

### Регулярне оновлення даних

```python
import schedule
import time

def update_menu_data():
    # Ваш код для отримання нових даних
    print("Оновлення даних меню...")
    # Тут можна викликати функцію скрейпінгу
    # і зберегти результати

# Оновлення даних щодня о 6:00
schedule.every().day.at("06:00").do(update_menu_data)

while True:
    schedule.run_pending()
    time.sleep(60)  # Перевірка кожну хвилину
```

## Важливі зауваження

### 1. Законність та етичність

- Перевірте файл `robots.txt` сайту перед скрейпінгом
- Дотримуйтесь умов використання сайту
- Не перевантажуйте сервер великим числом запитів
- Додайте затримки між запитами

### 2. Обробка помилок

```python
import time
import random

def safe_scrape(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Викине виняток для помилкових статусів
            return response
        except requests.RequestException as e:
            print(f"Спроба {attempt + 1} не вдалася: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))  # Випадкова затримка
            else:
                raise
```

### 3. Збереження даних у структурованому форматі

Для використання в боті рекомендується зберігати дані в форматі, схожому на цей:

```json
{
  "categories": [
    {
      "id": "soups",
      "name": "Супи"
    },
    {
      "id": "main_dishes",
      "name": "Гарячі страви"
    }
  ],
  "items": [
    {
      "id": 1,
      "name": "Борщ",
      "price": 80,
      "category": "soups",
      "description": "Традиційний український борщ"
    }
  ]
}
```

## Практичні поради

1. **Починайте з простого**: спочатку зробіть робочий прототип для одного сайту
2. **Використовуйте кешування**: не робіть запити щоразу, якщо дані не змінюються
3. **Тестуйте регулярно**: сайти змінюють структуру, тому потрібно оновлювати скрейпер
4. **Використовуйте проксі**: для уникнення блокування IP
5. **Зберігайте історію змін**: це допоможе відстежити, коли ціни або асортимент змінилися

## Інтеграція з ботом

Після збирання даних їх можна завантажити в бота:

```python
def load_menu_from_file(filename="menu_data.json"):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Файл {filename} не знайдено, використовується стандартне меню")
        return default_menu_data

# Використання в боті
MENU = load_menu_from_file()
```

Ці методи дозволять вам ефективно збирати дані з будь-якого сайту та використовувати їх у вашому Telegram-боті для доставки їжі.