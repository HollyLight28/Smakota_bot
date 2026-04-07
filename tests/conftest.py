# -*- coding: utf-8 -*-
"""
Conftest — спільні фікстури для всіх тестів.

Головна ідея: кожен тест працює з ТИМЧАСОВОЮ базою даних,
щоб не торкатися продакшн smakota.db.
"""
import os
import sys
import sqlite3
import pytest

# Додаємо корінь проєкту до sys.path, щоб імпорти працювали
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Створює тимчасову БД для кожного тесту.
    
    Після тесту файл автоматично видаляється (tmp_path).
    Ніякого ризику зачепити продакшн базу.
    """
    db_path = str(tmp_path / "test_smakota.db")
    
    # Патчимо DATABASE_FILE у модулі database
    import database as db_module
    monkeypatch.setattr(db_module, 'DATABASE_FILE', db_path)
    
    # Очищаємо thread-local з'єднання, щоб воно перестворилось з новим шляхом
    if hasattr(db_module.local_storage, 'connection'):
        try:
            db_module.local_storage.connection.close()
        except Exception:
            pass
        delattr(db_module.local_storage, 'connection')
    
    # Створюємо таблиці
    db_module.setup_database()
    
    yield db_module
    
    # Cleanup: закриваємо з'єднання
    if hasattr(db_module.local_storage, 'connection'):
        try:
            db_module.local_storage.connection.close()
        except Exception:
            pass
        delattr(db_module.local_storage, 'connection')


@pytest.fixture
def sample_category(test_db):
    """Тестова категорія."""
    test_db.upsert_category('pizza', 'Піца')
    return {'id': 'pizza', 'name': 'Піца'}


@pytest.fixture
def sample_item(test_db, sample_category):
    """Тестова страва."""
    test_db.upsert_item(
        name='Маргарита',
        price=159.0,
        category_id='pizza',
        description='Класична піца з моцарелою',
        weight='400г',
        image_url='https://example.com/pizza.jpg'
    )
    # Знаходимо ID
    conn = test_db.get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE name='Маргарита'").fetchone()
    return dict(item)


@pytest.fixture
def sample_courier(test_db):
    """Тестовий кур'єр."""
    test_db.add_courier('Тест Кур\'єр', 12345)
    conn = test_db.get_db_connection()
    conn.execute("UPDATE couriers SET shift_status='on' WHERE chat_id=12345")
    conn.commit()
    return {'name': 'Тест Кур\'єр', 'chat_id': 12345}


@pytest.fixture
def sample_order(test_db, sample_item, sample_courier):
    """Тестове замовлення, призначене кур'єру."""
    # Додаємо товар у кошик
    test_db.add_to_cart(99999, sample_item['id'])
    cart_items = test_db.get_cart_items(99999)
    
    # Створюємо замовлення
    order_id = test_db.create_order(
        user_id=99999,
        total_amount=159.0,
        payment_method='💵 Готівка',
        delivery_data={
            'name': 'Тестовий Клієнт',
            'contact': '0981234567',
            'address': 'Київська 10',
            'comment': 'Без цибулі'
        },
        cart_items=cart_items
    )
    
    # Призначаємо кур'єру
    test_db.assign_courier(order_id, sample_courier['chat_id'])
    
    return {'id': order_id, 'courier_id': sample_courier['chat_id']}
