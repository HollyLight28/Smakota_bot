# -*- coding: utf-8 -*-
"""
Тести для утилітних функцій.

Покриваємо:
- clean_phone (bot/utils.py) — нормалізація телефону для tel: URL
- normalize_phone (bot/handlers/courier.py) — те саме, для кур'єрського хендлера
- get_maps_url — генерація Google Maps URL
"""
import os
import sys
import re
import urllib.parse

# Додаємо корінь проєкту до sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- Тестуємо clean_phone з bot/utils.py ---
# Імпортуємо напряму, щоб уникнути імпорту бота
# (бот вимагає .env і telebot ініціалізацію)

from bot.utils import clean_phone, get_maps_url


class TestCleanPhone:
    """Тести для clean_phone() — нормалізація телефону."""

    def test_ukrainian_local_format(self):
        """098... → +38098..."""
        assert clean_phone('0981234567') == '+380981234567'

    def test_already_international(self):
        """+380... залишається як е."""
        assert clean_phone('+380981234567') == '+380981234567'

    def test_with_spaces_and_dashes(self):
        """Прибирає форматування."""
        assert clean_phone('+38 (098) 123-45-67') == '+380981234567'

    def test_problematic_number_from_log(self):
        """Реальний номер з лога, який крашив бота: 0981919191991."""
        result = clean_phone('0981919191991')
        assert result == '+380981919191991'

    def test_empty_string(self):
        result = clean_phone('')
        assert result == '+380000000000'

    def test_none_input(self):
        result = clean_phone(None)
        assert result == '+380000000000'


class TestGetMapsUrl:
    """Тести для get_maps_url() — генерація маршруту."""

    def test_basic_address(self):
        url = get_maps_url('Київська 24')
        assert 'google.com/maps' in url
        assert 'destination=' in url
        # Має містити 'Рівне' в URL
        assert '%D0%A0%D1%96%D0%B2%D0%BD%D0%B5' in url or 'Рівне' in urllib.parse.unquote(url)

    def test_address_with_special_chars(self):
        url = get_maps_url('вул. Литовська, буд. 55/2')
        assert 'google.com/maps' in url
        # Не повинен крашитися на спецсимволах

    def test_cyrillic_encoded(self):
        url = get_maps_url('Соборна')
        # Перевіряємо що URL правильно закодований
        assert '%' in url  # Кирилиця має бути percent-encoded


class TestEscapeMd:
    """Тести для escape_md() — захист від крашів Markdown."""

    def test_underscore_escaping(self):
        from bot.utils import escape_md
        assert escape_md('Vova_Pro') == r'Vova\_Pro'

    def test_asterisk_escaping(self):
        from bot.utils import escape_md
        assert escape_md('Meat*Ball') == r'Meat\*Ball'

    def test_backtick_escaping(self):
        from bot.utils import escape_md
        assert escape_md('Price `100`') == r'Price \`100\`'

    def test_multiple_chars(self):
        from bot.utils import escape_md
        assert escape_md('_[Test]_') == r'\_\[Test\]\_'

    def test_none_input(self):
        from bot.utils import escape_md
        assert escape_md(None) == ''

    def test_normal_text(self):
        from bot.utils import escape_md
        assert escape_md('Замовлення 123') == 'Замовлення 123'
