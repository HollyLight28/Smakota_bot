# -*- coding: utf-8 -*-
"""
Тести для keyboards.py — перевіряємо що клавіатури генеруються без крашів.

Ці тести НЕ перевіряють Telegram API — вони перевіряють що
функції клавіатур повертають валідні об'єкти.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from telebot.types import InlineKeyboardMarkup, ReplyKeyboardMarkup


class TestKeyboards:
    """Перевірка генерації клавіатур."""

    def test_client_keyboard(self):
        import keyboards
        kb = keyboards.get_client_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_courier_keyboard_no_user(self):
        import keyboards
        kb = keyboards.get_courier_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_courier_keyboard_with_user(self, test_db, sample_courier):
        import keyboards
        kb = keyboards.get_courier_keyboard(user_id=sample_courier['chat_id'])
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_admin_keyboard(self):
        import keyboards
        kb = keyboards.get_admin_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_dispatcher_keyboard(self):
        import keyboards
        kb = keyboards.get_dispatcher_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_hall_staff_keyboard(self):
        import keyboards
        kb = keyboards.get_hall_staff_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_kitchen_keyboard(self):
        import keyboards
        kb = keyboards.get_kitchen_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_categories_keyboard(self, test_db, sample_category):
        import keyboards
        kb = keyboards.get_categories_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_items_keyboard(self, test_db, sample_item):
        import keyboards
        kb = keyboards.get_items_keyboard('pizza')
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_cart_actions_keyboard(self):
        import keyboards
        kb = keyboards.get_cart_actions_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_empty_cart_keyboard(self):
        import keyboards
        kb = keyboards.get_empty_cart_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_payment_method_keyboard(self):
        import keyboards
        kb = keyboards.get_payment_method_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_checkout_contact_keyboard(self):
        import keyboards
        kb = keyboards.get_checkout_contact_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)
