"""
Конфигурация приложения LexiOne Competition Monitor.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
OUTPUTS_DIR = BASE_DIR / "outputs"
HISTORY_DIR = BASE_DIR / "history"

# Создаём директории если не существуют
for directory in [DATA_DIR, SCREENSHOTS_DIR, OUTPUTS_DIR, HISTORY_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# API настройки
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_VISION = "gpt-4o"  # Для анализа изображений
OPENAI_MODEL_TEXT = "gpt-4o-mini"  # Для анализа текста

# Selenium
SELENIUM_HEADLESS = True
SELENIUM_TIMEOUT = 15  # секунд — таймаут на загрузку страницы
SELENIUM_PAGE_LOAD_DELAY = 2  # секунд ожидания после загрузки


def validate_config():
    """Проверяет наличие обязательных настроек."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY не найден. Добавьте его в файл .env"
        )
