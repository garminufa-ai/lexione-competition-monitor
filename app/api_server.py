"""
FastAPI-сервер для LexiOne Competition Monitor.
Эндпоинты для анализа изображений, текста и парсинга конкурентов.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import OUTPUTS_DIR, HISTORY_DIR, SCREENSHOTS_DIR
from app.openai_service import analyze_image, analyze_text
from app.parsing_service import parse_competitors_list, parse_website, get_parsed_text


app = FastAPI(
    title="LexiOne Competition Monitor API",
    description="API для анализа сайтов конкурентов",
    version="1.0.0"
)

# CORS для локального UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модели запросов/ответов
class CompetitorItem(BaseModel):
    name: str = ""
    url: str


class ParseRequest(BaseModel):
    competitors: List[CompetitorItem]


class TextAnalysisRequest(BaseModel):
    text: str
    competitor_name: Optional[str] = "Неизвестный"


class AnalysisResponse(BaseModel):
    success: bool
    data: dict
    error: Optional[str] = None


# === Эндпоинты ===

@app.get("/")
async def root():
    """Корневой эндпоинт — информация об API."""
    return {
        "name": "LexiOne Competition Monitor API",
        "version": "1.0.0",
        "endpoints": {
            "/analyze-image": "POST - Анализ изображения/скриншота",
            "/analyze-text": "POST - Анализ текстового контента",
            "/parse": "POST - Парсинг списка URL конкурентов",
            "/parse-single": "POST - Парсинг одного URL"
        }
    }


@app.post("/analyze-image", response_model=AnalysisResponse)
async def endpoint_analyze_image(
    file: UploadFile = File(...),
    competitor_name: str = Form(default="Неизвестный")
):
    """
    Анализирует загруженное изображение (скриншот сайта).
    
    - **file**: Изображение (PNG, JPG, WEBP)
    - **competitor_name**: Название конкурента
    """
    try:
        # Проверяем тип файла
        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый тип файла: {file.content_type}"
            )
        
        # Сохраняем временный файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = Path(file.filename).suffix or ".png"
        temp_path = SCREENSHOTS_DIR / f"upload_{timestamp}{ext}"
        
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Анализируем
        result = analyze_image(temp_path, competitor_name)
        
        # Сохраняем результат
        _save_to_history("image_analysis", competitor_name, result)
        
        return AnalysisResponse(success=True, data=result)
        
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@app.post("/analyze-text", response_model=AnalysisResponse)
async def endpoint_analyze_text(request: TextAnalysisRequest):
    """
    Анализирует текстовый контент сайта.
    
    - **text**: HTML или текст сайта
    - **competitor_name**: Название конкурента
    """
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Текст не может быть пустым")
        
        result = analyze_text(request.text, request.competitor_name)
        
        # Сохраняем результат
        _save_to_history("text_analysis", request.competitor_name, result)
        
        return AnalysisResponse(success=True, data=result)
        
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@app.post("/parse")
async def endpoint_parse(request: ParseRequest):
    """
    Парсит список URL конкурентов и анализирует их.
    Использует текстовый анализ для скорости (GPT-4o-mini вместо GPT-4o vision).
    
    - **competitors**: Список объектов с полями name и url
    """
    try:
        if not request.competitors:
            raise HTTPException(status_code=400, detail="Список конкурентов пуст")
        
        # Преобразуем в список словарей
        competitors_list = [
            {"name": c.name, "url": c.url} 
            for c in request.competitors
        ]
        
        total = len(competitors_list)
        print(f"📋 Начинаю парсинг {total} сайтов...")
        
        # Парсим сайты БЕЗ скриншотов для ускорения
        parsed_results = parse_competitors_list(competitors_list, save_screenshots=False)
        
        print(f"✅ Парсинг завершён, анализирую данные...")
        
        # Анализируем каждого конкурента
        analysis_results = []
        
        for idx, parsed in enumerate(parsed_results, 1):
            print(f"🔍 Анализ {idx}/{total}: {parsed['name']}...")
            
            competitor_result = {
                "name": parsed["name"],
                "url": parsed["url"],
                "parsing_success": parsed["success"],
                "parsing_error": parsed.get("error"),
                "analysis": None
            }
            
            if parsed["success"]:
                # Используем ТЕКСТОВЫЙ анализ (быстрее в 3-5 раз)
                try:
                    text = get_parsed_text(parsed)
                    competitor_result["analysis"] = analyze_text(text, parsed["name"])
                    competitor_result["analysis_type"] = "text"
                except Exception as e:
                    competitor_result["analysis_error"] = str(e)
                    print(f"⚠️ Ошибка анализа {parsed['name']}: {e}")
            else:
                print(f"⚠️ Парсинг не удался: {parsed.get('error', 'Неизвестная ошибка')}")
            
            analysis_results.append(competitor_result)
        
        print(f"✅ Анализ завершён!")
        
        # Сохраняем полный отчёт
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_competitors": len(analysis_results),
            "successful": sum(1 for r in analysis_results if r["parsing_success"]),
            "results": analysis_results
        }
        
        _save_report(report)
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": None
        }


@app.post("/parse-single")
async def endpoint_parse_single(url: str = Form(...), name: str = Form(default="")):
    """
    Парсит один URL и анализирует.
    
    - **url**: URL сайта конкурента
    - **name**: Название (опционально)
    """
    try:
        # Парсим сайт
        parsed = parse_website(url, name if name else None, save_screenshot=True)
        
        result = {
            "name": parsed["name"],
            "url": parsed["url"],
            "parsing_success": parsed["success"],
            "parsing_error": parsed.get("error"),
            "analysis": None
        }
        
        if parsed["success"]:
            screenshot_path = parsed["data"].get("screenshot_path")
            
            if screenshot_path and Path(screenshot_path).exists():
                try:
                    result["analysis"] = analyze_image(screenshot_path, parsed["name"])
                    result["analysis_type"] = "image"
                except:
                    text = get_parsed_text(parsed)
                    result["analysis"] = analyze_text(text, parsed["name"])
                    result["analysis_type"] = "text"
            else:
                text = get_parsed_text(parsed)
                result["analysis"] = analyze_text(text, parsed["name"])
                result["analysis_type"] = "text"
        
        _save_to_history("single_parse", result["name"], result)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e), "result": None}


@app.get("/history")
async def get_history(limit: int = 10):
    """Возвращает историю анализов."""
    history_files = sorted(
        HISTORY_DIR.glob("*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )[:limit]
    
    history = []
    for f in history_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                history.append(json.load(file))
        except:
            pass
    
    return {"history": history}


# === Вспомогательные функции ===

def _save_to_history(analysis_type: str, competitor_name: str, result: dict):
    """Сохраняет результат анализа в историю."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{analysis_type}_{timestamp}.json"
    
    data = {
        "type": analysis_type,
        "competitor": competitor_name,
        "timestamp": datetime.now().isoformat(),
        "result": result
    }
    
    with open(HISTORY_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_report(report: dict):
    """Сохраняет полный отчёт."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"
    
    with open(OUTPUTS_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


# Запуск сервера (для отладки)
if __name__ == "__main__":
    import uvicorn
    from app.config import API_HOST, API_PORT
    uvicorn.run(app, host=API_HOST, port=API_PORT)
