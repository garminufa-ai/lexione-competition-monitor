"""
Сервис парсинга сайтов конкурентов через Selenium.
"""

import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from app.config import SELENIUM_HEADLESS, SELENIUM_TIMEOUT, SCREENSHOTS_DIR, SELENIUM_PAGE_LOAD_DELAY


def create_driver() -> webdriver.Chrome:
    """Создаёт и настраивает Chrome WebDriver."""
    options = Options()
    
    if SELENIUM_HEADLESS:
        options.add_argument("--headless=new")
    
    # Базовые настройки
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    
    # Отключаем загрузку картинок для ускорения
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    # User-Agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Отключаем автоматизацию
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # ВАЖНО: Устанавливаем таймауты
    driver.set_page_load_timeout(SELENIUM_TIMEOUT)
    driver.set_script_timeout(SELENIUM_TIMEOUT)
    driver.implicitly_wait(5)
    
    # Скрываем признаки автоматизации
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except:
        pass
    
    return driver


def parse_website(url: str, name: str = None, save_screenshot: bool = True) -> dict:
    """
    Парсит один сайт конкурента.
    
    Args:
        url: URL сайта
        name: Название конкурента (опционально, извлечётся из URL)
        save_screenshot: Сохранять ли скриншот
    
    Returns:
        Словарь с извлечёнными данными
    """
    # Если имя не задано — извлекаем из URL
    if not name:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        name = parsed.netloc.replace("www.", "")
    
    driver = None
    result = {
        "name": name,
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "error": None,
        "data": {}
    }
    
    try:
        driver = create_driver()
        
        # Загружаем страницу с обработкой таймаута
        try:
            driver.get(url)
        except Exception as e:
            # Если таймаут — всё равно пробуем собрать данные
            print(f"   ⏱️ Таймаут загрузки, пробуем собрать данные...")
        
        # Короткое ожидание body
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass
        
        # Короткая пауза
        time.sleep(SELENIUM_PAGE_LOAD_DELAY)
        
        # Собираем данные
        data = {}
        
        # Заголовок страницы
        data["page_title"] = driver.title
        
        # Все заголовки H1-H3
        data["headings"] = []
        for tag in ["h1", "h2", "h3"]:
            elements = driver.find_elements(By.TAG_NAME, tag)
            for el in elements[:5]:  # Максимум 5 каждого типа
                text = el.text.strip()
                if text:
                    data["headings"].append({"tag": tag, "text": text})
        
        # Мета-описание
        try:
            meta_desc = driver.find_element(
                By.CSS_SELECTOR, 'meta[name="description"]'
            )
            data["meta_description"] = meta_desc.get_attribute("content")
        except:
            data["meta_description"] = ""
        
        # Основные тексты (первые параграфы)
        data["paragraphs"] = []
        paragraphs = driver.find_elements(By.TAG_NAME, "p")
        for p in paragraphs[:10]:
            text = p.text.strip()
            if len(text) > 50:  # Только значимые параграфы
                data["paragraphs"].append(text[:500])
        
        # Кнопки CTA
        data["cta_buttons"] = []
        buttons = driver.find_elements(By.TAG_NAME, "button")
        buttons += driver.find_elements(By.CSS_SELECTOR, "a.btn, a.button, .cta")
        for btn in buttons[:10]:
            text = btn.text.strip()
            if text and len(text) < 50:
                data["cta_buttons"].append(text)
        
        # Ссылки в навигации
        data["nav_links"] = []
        try:
            nav = driver.find_element(By.TAG_NAME, "nav")
            links = nav.find_elements(By.TAG_NAME, "a")
            for link in links[:15]:
                text = link.text.strip()
                if text:
                    data["nav_links"].append(text)
        except:
            pass
        
        # Сохраняем скриншот
        if save_screenshot:
            screenshot_name = f"{_sanitize_filename(name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot_path = SCREENSHOTS_DIR / screenshot_name
            
            # Полная высота страницы
            total_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(1920, min(total_height, 4000))
            time.sleep(1)
            
            driver.save_screenshot(str(screenshot_path))
            data["screenshot_path"] = str(screenshot_path)
        
        result["data"] = data
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
        
    finally:
        if driver:
            driver.quit()
    
    return result


def parse_competitors_list(competitors: list[dict], save_screenshots: bool = True) -> list[dict]:
    """
    Парсит список сайтов конкурентов.
    
    Args:
        competitors: Список словарей с ключами 'name' и 'url'
        save_screenshots: Сохранять ли скриншоты
    
    Returns:
        Список результатов парсинга
    """
    results = []
    
    for competitor in competitors:
        url = competitor.get("url", "")
        name = competitor.get("name", "")
        
        if not url:
            continue
            
        print(f"🌐 Парсинг: {name or url}")
        result = parse_website(
            url=url,
            name=name if name else None,
            save_screenshot=save_screenshots
        )
        results.append(result)
        
        if result["success"]:
            print(f"   ✅ Успешно: {result['data'].get('page_title', '')[:50]}")
        else:
            print(f"   ❌ Ошибка: {result.get('error', 'Неизвестно')[:50]}")
        
        # Короткая пауза между запросами
        time.sleep(1)
    
    return results


def get_parsed_text(parsed_data: dict) -> str:
    """
    Формирует текстовое представление спарсенных данных для анализа.
    
    Args:
        parsed_data: Результат парсинга
    
    Returns:
        Форматированный текст
    """
    data = parsed_data.get("data", {})
    
    parts = [
        f"# {parsed_data.get('name', 'Конкурент')}",
        f"URL: {parsed_data.get('url', '')}",
        "",
        f"## Заголовок страницы",
        data.get("page_title", "Не найден"),
        "",
        f"## Мета-описание",
        data.get("meta_description", "Не найдено"),
        "",
        "## Заголовки на странице"
    ]
    
    for h in data.get("headings", []):
        parts.append(f"- [{h['tag'].upper()}] {h['text']}")
    
    parts.extend([
        "",
        "## Основные тексты"
    ])
    
    for p in data.get("paragraphs", []):
        parts.append(f"- {p}")
    
    parts.extend([
        "",
        "## Кнопки CTA"
    ])
    
    for cta in data.get("cta_buttons", []):
        parts.append(f"- {cta}")
    
    parts.extend([
        "",
        "## Навигация"
    ])
    
    for link in data.get("nav_links", []):
        parts.append(f"- {link}")
    
    return "\n".join(parts)


def _sanitize_filename(name: str) -> str:
    """Очищает имя для использования в имени файла."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.replace(" ", "_").lower()
