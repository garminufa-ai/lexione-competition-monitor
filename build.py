"""
Скрипт сборки LexiOne Competition Monitor в исполняемый файл.
Использует PyInstaller для создания competitionmonitor.exe
"""

import subprocess
import sys
from pathlib import Path

# Пути
BASE_DIR = Path(__file__).parent
MAIN_SCRIPT = BASE_DIR / "main.py"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

# Имя выходного файла
APP_NAME = "competitionmonitor"


def build():
    """Собирает приложение в .exe"""
    print("=" * 50)
    print("⬡ LexiOne Competition Monitor — Сборка")
    print("=" * 50)
    
    # Проверяем наличие PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller не установлен")
        print("Установите: pip install pyinstaller")
        sys.exit(1)
    
    # Команда сборки
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",  # Один исполняемый файл
        "--windowed",  # Без консольного окна
        "--noconfirm",  # Перезаписывать без подтверждения
        "--clean",  # Очистить кэш перед сборкой
        
        # Добавляем данные
        "--add-data", f"app;app",
        "--add-data", f"ui;ui",
        
        # Скрытые импорты
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        
        # Пути
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        
        # Главный скрипт
        str(MAIN_SCRIPT)
    ]
    
    print("\n📦 Запуск сборки...")
    print(f"Команда: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = DIST_DIR / f"{APP_NAME}.exe"
        print("\n" + "=" * 50)
        print("✅ Сборка завершена успешно!")
        print(f"📁 Исполняемый файл: {exe_path}")
        print("=" * 50)
    else:
        print("\n❌ Ошибка сборки")
        sys.exit(1)


if __name__ == "__main__":
    build()

