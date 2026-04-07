# -*- coding: utf-8 -*-
"""
Тести для database.py — серце бота.

Покриваємо:
- Створення/міграція таблиць
- CRUD для кошика
- Створення замовлень
- Призначення кур'єрів
- FSM стани
- Ролі (кур'єр, диспетчер, зал, шеф)
- Шоппінг-лист
"""


class TestDatabaseSetup:
    """Перевіряємо що setup_database() створює всі таблиці."""

    def test_tables_exist(self, test_db):
        conn = test_db.get_db_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t['name'] for t in tables]

        expected = [
            'cart_items', 'categories', 'chefs', 'couriers',
            'dispatchers', 'hall_staff', 'items', 'mailing_templates',
            'order_items', 'orders', 'route_batches',
            'shopping_list', 'shopping_templates', 'user_states', 'users'
        ]
        for table in expected:
            assert table in table_names, f"Таблиця '{table}' не створена!"

    def test_shopping_templates_seeded(self, test_db):
        templates = test_db.get_shopping_templates()
        assert len(templates) > 0, "Шаблони закупок не засіяні!"
        names = [t['item_name'] for t in templates]
        assert 'Борошно' in names
        assert 'Цукор' in names


class TestCategories:
    """Категорії меню."""

    def test_upsert_and_get(self, test_db):
        test_db.upsert_category('salads', 'Салати')
        cats = test_db.get_categories()
        assert len(cats) == 1
        assert cats[0]['name'] == 'Салати'

    def test_upsert_updates_existing(self, test_db):
        test_db.upsert_category('salads', 'Салати')
        test_db.upsert_category('salads', 'Свіжі Салати')
        cats = test_db.get_categories()
        assert len(cats) == 1
        assert cats[0]['name'] == 'Свіжі Салати'

    def test_get_category_name(self, test_db, sample_category):
        name = test_db.get_category_name_by_id('pizza')
        assert name == 'Піца'

    def test_get_unknown_category_name(self, test_db):
        name = test_db.get_category_name_by_id('nonexistent')
        assert name == "Невідома категорія"


class TestItems:
    """Страви (items)."""

    def test_upsert_item(self, test_db, sample_category):
        test_db.upsert_item('Чотири сири', 199.0, 'pizza', 'Багато сиру', '450г')
        items = test_db.get_items_by_category('pizza')
        assert len(items) == 1
        assert items[0]['name'] == 'Чотири сири'
        assert items[0]['price'] == 199.0

    def test_get_item_by_id(self, test_db, sample_item):
        item = test_db.get_item_by_id(sample_item['id'])
        assert item is not None
        assert item['name'] == 'Маргарита'
        assert item['price'] == 159.0
        assert item['description'] == 'Класична піца з моцарелою'

    def test_deactivate_items(self, test_db, sample_category):
        test_db.upsert_item('Піца А', 100, 'pizza', '', '')
        test_db.upsert_item('Піца Б', 200, 'pizza', '', '')
        test_db.upsert_item('Піца В', 300, 'pizza', '', '')

        # Деактивуємо все, крім 'Піца А'
        test_db.deactivate_items_not_in_list(['Піца А'])

        active = test_db.get_items_by_category('pizza')
        assert len(active) == 1
        assert active[0]['name'] == 'Піца А'

    def test_deactivate_all_items(self, test_db, sample_item):
        test_db.deactivate_items_not_in_list([])
        active = test_db.get_items_by_category('pizza')
        assert len(active) == 0

    def test_item_image_url(self, test_db, sample_item):
        item = test_db.get_item_by_id(sample_item['id'])
        assert item['image_url'] == 'https://example.com/pizza.jpg'


class TestCart:
    """Кошик покупця."""

    def test_add_to_cart(self, test_db, sample_item):
        test_db.add_to_cart(user_id=111, item_id=sample_item['id'])
        cart = test_db.get_cart_items(111)
        assert len(cart) == 1
        assert cart[0]['quantity'] == 1

    def test_add_to_cart_increases_quantity(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        test_db.add_to_cart(111, sample_item['id'])
        test_db.add_to_cart(111, sample_item['id'], quantity=3)
        cart = test_db.get_cart_items(111)
        assert cart[0]['quantity'] == 5  # 1 + 1 + 3

    def test_update_cart_quantity_increment(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        test_db.update_cart_quantity(111, sample_item['id'], +2)
        cart = test_db.get_cart_items(111)
        assert cart[0]['quantity'] == 3

    def test_update_cart_quantity_decrement_removes(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        test_db.update_cart_quantity(111, sample_item['id'], -1)
        cart = test_db.get_cart_items(111)
        assert len(cart) == 0  # Кількість 0 → видалення

    def test_remove_from_cart(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        test_db.remove_from_cart(111, sample_item['id'])
        cart = test_db.get_cart_items(111)
        assert len(cart) == 0

    def test_clear_cart(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'], 3)
        test_db.clear_cart(111)
        cart = test_db.get_cart_items(111)
        assert len(cart) == 0

    def test_cart_ignores_inactive_items(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        test_db.deactivate_items_not_in_list([])  # Деактивуємо все
        cart = test_db.get_cart_items(111)
        assert len(cart) == 0  # Неактивні не повертаються

    def test_different_users_different_carts(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'], 2)
        test_db.add_to_cart(222, sample_item['id'], 5)
        cart_111 = test_db.get_cart_items(111)
        cart_222 = test_db.get_cart_items(222)
        assert cart_111[0]['quantity'] == 2
        assert cart_222[0]['quantity'] == 5


class TestOrders:
    """Замовлення."""

    def test_create_order(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'], 2)
        cart = test_db.get_cart_items(111)

        order_id = test_db.create_order(
            user_id=111,
            total_amount=318.0,
            payment_method='💵 Готівка',
            delivery_data={
                'name': 'Олег',
                'contact': '+380981234567',
                'address': 'Київська 24',
                'comment': 'Домофон 45'
            },
            cart_items=cart
        )

        assert order_id is not None
        order = test_db.get_order_by_id(order_id)
        assert order['status'] == 'new'
        assert order['total_amount'] == 318.0
        assert order['delivery_name'] == 'Олег'
        assert order['delivery_address'] == 'Київська 24'
        assert order['comment'] == 'Домофон 45'

    def test_order_items_saved(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'], 2)
        cart = test_db.get_cart_items(111)
        order_id = test_db.create_order(111, 318.0, '💳 Термінал', {'name': 'Test'}, cart)

        conn = test_db.get_db_connection()
        items = conn.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,)).fetchall()
        assert len(items) == 1
        assert items[0]['item_name'] == 'Маргарита'
        assert items[0]['quantity'] == 2

    def test_update_order_status(self, test_db, sample_order):
        test_db.update_order_status(sample_order['id'], 'completed')
        order = test_db.get_order_by_id(sample_order['id'])
        assert order['status'] == 'completed'

    def test_assign_courier(self, test_db, sample_item, sample_courier):
        test_db.add_to_cart(111, sample_item['id'])
        cart = test_db.get_cart_items(111)
        order_id = test_db.create_order(111, 159.0, '💵 Готівка', {'name': 'X'}, cart)

        test_db.assign_courier(order_id, sample_courier['chat_id'])
        order = test_db.get_order_by_id(order_id)
        assert order['courier_id'] == sample_courier['chat_id']
        assert order['status'] == 'delivery'

    def test_get_last_order(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        cart = test_db.get_cart_items(111)
        test_db.create_order(111, 159.0, '💵 Готівка', {
            'name': 'Перший', 'contact': '111', 'address': 'Адреса 1'
        }, cart)

        test_db.add_to_cart(111, sample_item['id'])
        cart = test_db.get_cart_items(111)
        test_db.create_order(111, 200.0, '💳 Термінал', {
            'name': 'Другий', 'contact': '222', 'address': 'Адреса 2'
        }, cart)

        last = test_db.get_last_order(111)
        assert last is not None

    def test_get_active_orders(self, test_db, sample_item):
        """Перевірка фільтрації активних замовлень для адміна."""
        # Нове замовлення
        test_db.add_to_cart(111, sample_item['id'])
        test_db.create_order(111, 100, 'Готівка', {'name': 'New'}, test_db.get_cart_items(111))
        
        # Завершене (не має бути в списку)
        oid = test_db.create_order(222, 100, 'Карта', {'name': 'Done'}, test_db.get_cart_items(111))
        test_db.update_order_status(oid, 'completed')
        
        active = test_db.get_active_orders()
        assert len(active) == 1
        assert active[0]['delivery_name'] == 'New'

    def test_get_courier_active_orders(self, test_db, sample_order, sample_courier):
        """Перевірка замовлень в роботі у кур'єра."""
        # sample_order вже в статусі 'delivery'
        active = test_db.get_courier_active_orders(sample_courier['chat_id'])
        assert len(active) == 1
        assert active[0]['id'] == sample_order['id']


class TestScheduledOrders:
    """Тести для системи 'Будильник' (відкладені замовлення)."""

    def test_set_order_scheduled(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        order_id = test_db.create_order(111, 100, 'Готівка', {'name': 'Later'}, test_db.get_cart_items(111))
        
        test_db.set_order_scheduled(order_id, "18:30")
        order = test_db.get_order_by_id(order_id)
        assert order['status'] == 'scheduled'
        assert order['scheduled_time'] == '18:30'
        assert order['reminded'] == 0

    def test_get_orders_to_remind(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        order_id = test_db.create_order(111, 100, 'Готівка', {'name': 'Later'}, test_db.get_cart_items(111))
        test_db.set_order_scheduled(order_id, "18:30")
        
        to_remind = test_db.get_orders_to_remind()
        assert len(to_remind) == 1
        assert to_remind[0]['id'] == order_id

    def test_mark_as_reminded(self, test_db, sample_item):
        test_db.add_to_cart(111, sample_item['id'])
        order_id = test_db.create_order(111, 100, 'Готівка', {'name': 'Later'}, test_db.get_cart_items(111))
        test_db.set_order_scheduled(order_id, "18:30")
        
        test_db.mark_as_reminded(order_id)
        to_remind = test_db.get_orders_to_remind()
        assert len(to_remind) == 0  # Тепер черга пуста
        
        order = test_db.get_order_by_id(order_id)
        assert order['reminded'] == 1


class TestRouteBatches:
    """Маршрути (батчі)."""

    def test_create_route_batch(self, test_db, sample_item, sample_courier):
        # Створюємо кілька замовлень
        order_ids = []
        for addr in ['Адреса 1', 'Адреса 2', 'Адреса 3']:
            test_db.add_to_cart(111, sample_item['id'])
            cart = test_db.get_cart_items(111)
            oid = test_db.create_order(111, 100, '💵 Готівка', {'name': 'X', 'address': addr}, cart)
            order_ids.append(oid)

        batch_id = test_db.create_route_batch(sample_courier['chat_id'], order_ids)
        assert batch_id is not None

        conn = test_db.get_db_connection()
        batch_orders = conn.execute(
            'SELECT * FROM orders WHERE batch_id=? ORDER BY route_order', (batch_id,)
        ).fetchall()

        assert len(batch_orders) == 3
        assert batch_orders[0]['route_order'] == 1
        assert batch_orders[1]['route_order'] == 2
        assert batch_orders[2]['route_order'] == 3

        # Всі замовлення мають статус delivery
        for o in batch_orders:
            assert o['status'] == 'delivery'
            assert o['courier_id'] == sample_courier['chat_id']


class TestCouriers:
    """Кур'єри."""

    def test_add_courier(self, test_db):
        test_db.add_courier('Вася', 55555)
        couriers = test_db.get_couriers()
        assert len(couriers) == 1
        assert couriers[0]['name'] == 'Вася'

    def test_remove_courier(self, test_db):
        test_db.add_courier('Вася', 55555)
        test_db.remove_courier_by_chat_id(55555)
        couriers = test_db.get_couriers()
        assert len(couriers) == 0

    def test_daily_report(self, test_db, sample_order):
        # Завершуємо замовлення
        test_db.update_order_status(sample_order['id'], 'completed')
        count, total = test_db.get_daily_report(sample_order['courier_id'])
        assert count == 1
        assert total == 159.0


class TestFSMStates:
    """Стани користувача (FSM)."""

    def test_set_and_get_state(self, test_db):
        test_db.set_user_state(111, 'checkout_name')
        state = test_db.get_user_state(111)
        assert state['state'] == 'checkout_name'
        assert state['data'] == {}

    def test_set_state_with_data(self, test_db):
        test_db.set_user_state(111, 'checkout_use_history', {'name': 'Олег', 'phone': '123'})
        state = test_db.get_user_state(111)
        assert state['data']['name'] == 'Олег'

    def test_clear_state(self, test_db):
        test_db.set_user_state(111, 'some_state')
        test_db.clear_user_state(111)
        state = test_db.get_user_state(111)
        assert state is None

    def test_get_nonexistent_state(self, test_db):
        state = test_db.get_user_state(999999)
        assert state is None


class TestRoles:
    """Ролі: зал, диспетчер, шеф."""

    def test_add_hall_staff(self, test_db):
        test_db.add_hall_staff('Наташа', 77777)
        staff = test_db.get_hall_staff()
        assert len(staff) == 1
        assert staff[0]['name'] == 'Наташа'

    def test_add_dispatcher(self, test_db):
        test_db.add_dispatcher('Оля', 88888)
        dispatchers = test_db.get_dispatchers()
        assert len(dispatchers) == 1
        assert dispatchers[0]['name'] == 'Оля'

    def test_remove_from_all_roles(self, test_db):
        test_db.add_courier('Мульти', 11111)
        test_db.add_hall_staff('Мульти', 11111)
        test_db.add_dispatcher('Мульти', 11111)

        test_db.remove_user_from_roles(11111)

        assert len(test_db.get_couriers()) == 0
        assert len(test_db.get_hall_staff()) == 0
        assert len(test_db.get_dispatchers()) == 0

    def test_user_current_role(self, test_db):
        conn = test_db.get_db_connection()
        conn.execute("INSERT INTO users (chat_id, username, first_name) VALUES (111, 'test', 'Test')")
        conn.commit()

        test_db.set_user_current_role(111, 'courier')
        role = test_db.get_user_current_role(111)
        assert role == 'courier'


class TestShoppingList:
    """Список закупів для кухні."""

    def test_upsert_shopping_item(self, test_db):
        test_db.upsert_shopping_item('Борошно', '10 кг')
        items = test_db.get_shopping_list()
        assert len(items) == 1
        assert items[0]['item_name'] == 'Борошно'
        assert items[0]['quantity'] == '10 кг'

    def test_upsert_updates_quantity(self, test_db):
        test_db.upsert_shopping_item('Молоко', '5 л')
        test_db.upsert_shopping_item('Молоко', '10 л')
        items = test_db.get_shopping_list()
        assert len(items) == 1
        assert items[0]['quantity'] == '10 л'

    def test_delete_shopping_item(self, test_db):
        test_db.upsert_shopping_item('Цукор', '2 кг')
        items = test_db.get_shopping_list()
        test_db.delete_shopping_item(items[0]['id'])
        assert len(test_db.get_shopping_list()) == 0
