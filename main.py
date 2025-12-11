"""
LexiOne Competition Monitor — Главный файл запуска.
Запускает API-сервер в фоновом потоке и открывает PyQt6 интерфейс.
"""

import sys
import time
import threading
import requests
import uvicorn
from app.config import API_HOST, API_PORT, validate_config
from app.api_server import app as fastapi_app
from ui.main_window import run_app


def run_api_server():
    """Запускает FastAPI сервер в фоновом режиме."""
    try:
        config = uvicorn.Config(
            fastapi_app,
            host=API_HOST,
            port=API_PORT,
            log_level="warning"  # Минимум логов
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")


def wait_for_server(max_attempts=10, delay=1):
    """Ждёт пока сервер станет доступен."""
    url = f"http://{API_HOST}:{API_PORT}/"
    for i in range(max_attempts):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(delay)
    return False


def main():
    """Главная функция запуска приложения."""
    print("=" * 50)
    print("⬡ LexiOne Competition Monitor")
    print("=" * 50)
    
    # Проверяем конфигурацию
    try:
        validate_config()
        print("✅ Конфигурация проверена")
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nСоздайте файл .env с переменными:")
        print("OPENAI_API_KEY=ваш_ключ")
        sys.exit(1)
    
    # Запускаем API сервер в отдельном потоке
    print(f"🚀 Запуск API сервера на http://{API_HOST}:{API_PORT}")
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Ждём пока сервер станет доступен
    print("⏳ Ожидание запуска сервера...")
    if wait_for_server():
        print("✅ Сервер запущен и готов к работе")
    else:
        print("⚠️  Сервер не отвечает, но продолжаем запуск...")
    
    # Запускаем UI
    print("🖥️  Запуск интерфейса...")
    print("-" * 50)
    
    exit_code = run_app()
    
    print("-" * 50)
    print("👋 Приложение завершено")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

