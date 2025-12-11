"""
Сервис для работы с OpenAI API.
Анализ изображений (GPT-4o vision) и текстов.
"""

import json
import base64
from pathlib import Path
from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_MODEL_VISION, OPENAI_MODEL_TEXT


# Системный промпт для анализа конкурентов
ANALYSIS_SYSTEM_PROMPT = """Ты — эксперт по конкурентному анализу в сфере бизнес-сервисов и digital-продуктов.

Твоя задача — проанализировать сайт/лендинг конкурента и дать ПОДРОБНУЮ оценку, которая поможет пользователю улучшить СВОЙ продукт.

ВАЖНО: Рекомендации должны быть для ПОЛЬЗОВАТЕЛЯ приложения (как ему улучшить свой продукт), а НЕ для конкурента.

Отвечай ТОЛЬКО валидным JSON без дополнительного текста, markdown или пояснений.

Формат ответа:
{
    "company_info": {
        "name": "Название компании/бренда",
        "tagline": "Слоган или главное сообщение",
        "niche": "Ниша/направление деятельности",
        "target_audience": "Целевая аудитория",
        "main_offer": "Главное предложение/оффер",
        "unique_selling_points": ["УТП 1", "УТП 2", "УТП 3"]
    },
    "metrics": {
        "visual_design": {
            "score": 0-10,
            "description": "Краткое описание визуального стиля"
        },
        "usability": {
            "score": 0-10,
            "description": "Оценка удобства использования"
        },
        "content_quality": {
            "score": 0-10,
            "description": "Качество контента и текстов"
        },
        "trust_signals": {
            "score": 0-10,
            "description": "Элементы доверия (отзывы, сертификаты, партнёры)"
        },
        "call_to_action": {
            "score": 0-10,
            "description": "Эффективность призывов к действию"
        },
        "mobile_friendliness": {
            "score": 0-10,
            "description": "Адаптивность и мобильная версия"
        },
        "innovation": {
            "score": 0-10,
            "description": "Инновационность подхода"
        }
    },
    "competitive_analysis": {
        "strengths": ["Сильная сторона 1", "Сильная сторона 2", "Сильная сторона 3"],
        "weaknesses": ["Слабая сторона 1", "Слабая сторона 2"],
        "opportunities": ["Возможность для вас 1", "Возможность для вас 2"],
        "threats": ["Угроза 1", "Угроза 2"]
    },
    "positioning_summary": "Подробное резюме позиционирования конкурента (3-5 предложений)",
    "recommendations_for_user": [
        "Конкретная рекомендация, как улучшить СВОЙ продукт на основе этого анализа",
        "Что можно позаимствовать или сделать лучше",
        "Как дифференцироваться от этого конкурента",
        "На какие слабости конкурента можно сделать акцент в своём продукте"
    ],
    "key_takeaways": [
        "Главный вывод 1",
        "Главный вывод 2",
        "Главный вывод 3"
    ]
}

Описание метрик:
- visual_design: Общее качество визуального дизайна, цветовая схема, типографика
- usability: Понятность интерфейса, навигация, структура информации
- content_quality: Качество текстов, ясность изложения, грамотность
- trust_signals: Отзывы, кейсы, партнёры, сертификаты, гарантии
- call_to_action: Эффективность кнопок и призывов к действию
- mobile_friendliness: Адаптивность, скорость, удобство на мобильных
- innovation: Уникальные фичи, современные технологии, креативные решения"""


def get_client() -> OpenAI:
    """Создаёт клиент OpenAI."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не настроен")
    return OpenAI(api_key=OPENAI_API_KEY)


def encode_image_to_base64(image_path: str | Path) -> str:
    """Кодирует изображение в base64."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Изображение не найдено: {image_path}")
    
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path: str | Path, competitor_name: str = "Неизвестный") -> dict:
    """
    Анализирует скриншот сайта конкурента через GPT-4o vision.
    """
    client = get_client()
    
    image_base64 = encode_image_to_base64(image_path)
    
    ext = Path(image_path).suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }.get(ext, "image/png")
    
    user_prompt = f"""Проанализируй скриншот сайта конкурента "{competitor_name}".
Дай подробную оценку по всем метрикам.
Рекомендации должны быть для МЕНЯ (пользователя), как улучшить МОЙ продукт.
Верни ТОЛЬКО JSON без дополнительного текста."""
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL_VISION,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=3000,
        temperature=0.7
    )
    
    content = response.choices[0].message.content.strip()
    return _parse_json_response(content, competitor_name)


def analyze_text(text: str, competitor_name: str = "Неизвестный") -> dict:
    """
    Анализирует текстовый контент сайта конкурента.
    """
    client = get_client()
    
    # Обрезаем текст если слишком длинный
    max_length = 10000
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[... текст обрезан ...]"
    
    user_prompt = f"""Проанализируй текстовый контент сайта конкурента "{competitor_name}":

---
{text}
---

Дай подробную оценку по всем метрикам.
Рекомендации должны быть для МЕНЯ (пользователя), как улучшить МОЙ продукт на основе анализа этого конкурента.
Верни ТОЛЬКО JSON без дополнительного текста."""
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL_TEXT,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=3000,
        temperature=0.7
    )
    
    content = response.choices[0].message.content.strip()
    return _parse_json_response(content, competitor_name)


def _parse_json_response(content: str, competitor_name: str) -> dict:
    """Парсит JSON-ответ от модели."""
    try:
        # Убираем markdown-обёртки если есть
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            if content.startswith("json"):
                content = content[4:].strip()
        
        result = json.loads(content)
        
        # Проверяем и заполняем обязательные поля
        if "company_info" not in result:
            result["company_info"] = {
                "name": competitor_name,
                "tagline": "",
                "niche": "Не определено",
                "target_audience": "Не определено",
                "main_offer": "Не определено",
                "unique_selling_points": []
            }
        
        if "metrics" not in result:
            result["metrics"] = _get_default_metrics()
        
        if "competitive_analysis" not in result:
            result["competitive_analysis"] = {
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": []
            }
        
        if "positioning_summary" not in result:
            result["positioning_summary"] = "Анализ не завершён"
        
        if "recommendations_for_user" not in result:
            result["recommendations_for_user"] = []
        
        if "key_takeaways" not in result:
            result["key_takeaways"] = []
        
        # Вычисляем средний балл
        result["average_score"] = _calculate_average_score(result.get("metrics", {}))
        
        return result
        
    except json.JSONDecodeError:
        return _get_fallback_result(competitor_name, content)


def _get_default_metrics() -> dict:
    """Возвращает метрики по умолчанию."""
    return {
        "visual_design": {"score": 5, "description": "Не оценено"},
        "usability": {"score": 5, "description": "Не оценено"},
        "content_quality": {"score": 5, "description": "Не оценено"},
        "trust_signals": {"score": 5, "description": "Не оценено"},
        "call_to_action": {"score": 5, "description": "Не оценено"},
        "mobile_friendliness": {"score": 5, "description": "Не оценено"},
        "innovation": {"score": 5, "description": "Не оценено"}
    }


def _calculate_average_score(metrics: dict) -> float:
    """Вычисляет средний балл по метрикам."""
    scores = []
    for key, value in metrics.items():
        if isinstance(value, dict) and "score" in value:
            scores.append(value["score"])
    return round(sum(scores) / len(scores), 1) if scores else 0


def _get_fallback_result(competitor_name: str, raw_content: str) -> dict:
    """Возвращает результат при ошибке парсинга."""
    return {
        "company_info": {
            "name": competitor_name,
            "tagline": "",
            "niche": "Ошибка анализа",
            "target_audience": "",
            "main_offer": "",
            "unique_selling_points": []
        },
        "metrics": _get_default_metrics(),
        "competitive_analysis": {
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": []
        },
        "positioning_summary": raw_content[:500] if raw_content else "Ответ не получен",
        "recommendations_for_user": [],
        "key_takeaways": [],
        "average_score": 0,
        "error": "Не удалось распарсить JSON-ответ"
    }
