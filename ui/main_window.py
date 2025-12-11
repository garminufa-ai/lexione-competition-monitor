"""
Главное окно PyQt6 приложения LexiOne Competition Monitor.
Пользователь сам добавляет URL конкурентов для анализа.
"""

import sys
import json
import requests
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QTabWidget, QHeaderView,
    QGroupBox, QSplitter, QStatusBar, QFrame, QLineEdit, QDialog,
    QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from app.config import API_HOST, API_PORT, DATA_DIR


# URL API сервера
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"


class AddCompetitorDialog(QDialog):
    """Диалог добавления нового конкурента."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить конкурента")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Форма
        form = QFormLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        form.addRow("URL сайта*:", self.url_input)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название компании (опционально)")
        form.addRow("Название:", self.name_input)
        
        layout.addLayout(form)
        
        # Подсказка
        hint = QLabel("* URL обязателен. Если название не указано — будет извлечено из URL.")
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(hint)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_data(self) -> dict:
        """Возвращает введённые данные."""
        return {
            "url": self.url_input.text().strip(),
            "name": self.name_input.text().strip()
        }


class AnalysisWorker(QThread):
    """Фоновый поток для анализа."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, task_type: str, data: dict = None):
        super().__init__()
        self.task_type = task_type
        self.data = data or {}
    
    def run(self):
        try:
            # Проверяем доступность сервера перед запросом
            try:
                test_response = requests.get(f"{API_BASE_URL}/", timeout=3)
                if test_response.status_code != 200:
                    raise requests.exceptions.ConnectionError("Сервер не отвечает")
            except requests.exceptions.RequestException:
                from app.config import API_PORT
                self.error.emit(
                    f"Не удалось подключиться к API серверу на {API_BASE_URL}.\n\n"
                    f"Убедитесь, что:\n"
                    f"1. Сервер запущен (должно быть сообщение '✅ Сервер запущен')\n"
                    f"2. Порт {API_PORT} не занят другим приложением\n"
                    f"3. Перезапустите приложение"
                )
                return
            
            if self.task_type == "parse":
                competitors = self.data.get("competitors", [])
                count = len(competitors)
                self.progress.emit(f"⏳ Парсинг {count} сайтов... (это займёт ~{count * 30} сек)")
                
                # Увеличенный таймаут: 60 сек на каждый сайт
                timeout = max(180, count * 60)
                
                response = requests.post(
                    f"{API_BASE_URL}/parse",
                    json={"competitors": competitors},
                    timeout=timeout
                )
                
            elif self.task_type == "parse_single":
                self.progress.emit(f"Парсинг: {self.data.get('url', '')}...")
                response = requests.post(
                    f"{API_BASE_URL}/parse-single",
                    data=self.data,
                    timeout=120
                )
                
            elif self.task_type == "analyze_image":
                self.progress.emit("Анализ изображения...")
                files = {"file": open(self.data["path"], "rb")}
                data = {"competitor_name": self.data.get("name", "Загруженный файл")}
                response = requests.post(
                    f"{API_BASE_URL}/analyze-image",
                    files=files,
                    data=data,
                    timeout=120
                )
            else:
                raise ValueError(f"Неизвестный тип задачи: {self.task_type}")
            
            response.raise_for_status()
            self.finished.emit(response.json())
            
        except requests.exceptions.ConnectionError as e:
            self.error.emit(
                f"Не удалось подключиться к API серверу.\n\n"
                f"Проверьте, что сервер запущен на {API_BASE_URL}\n"
                f"Ошибка: {str(e)}"
            )
        except requests.exceptions.Timeout:
            self.error.emit("Превышено время ожидания ответа от сервера.")
        except Exception as e:
            self.error.emit(f"Ошибка: {str(e)}")


class MainWindow(QMainWindow):
    """Главное окно приложения."""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.competitors = []  # Список конкурентов [{name, url}, ...]
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("LexiOne Competition Monitor")
        self.setMinimumSize(1200, 800)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # === Заголовок ===
        header = self._create_header()
        main_layout.addWidget(header)
        
        # === Основной контент (splitter) ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель — управление конкурентами
        left_panel = self._create_competitors_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель — результаты
        right_panel = self._create_results_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter, stretch=1)
        
        # === Статус бар ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Добавьте URL конкурентов для анализа")
        
        # === Прогресс бар ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Применяем стили
        self._apply_styles()
    
    def _create_header(self) -> QWidget:
        """Создаёт заголовок приложения."""
        header = QFrame()
        header.setObjectName("header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 10)
        
        # Название
        title = QLabel("⬡ LexiOne Competition Monitor")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Подзаголовок
        subtitle = QLabel("Анализ сайтов конкурентов • Companion-приложение к Telegram-боту LexiOne")
        subtitle.setObjectName("subtitle")
        subtitle.setFont(QFont("Segoe UI", 10))
        layout.addWidget(subtitle)
        
        return header
    
    def _create_competitors_panel(self) -> QWidget:
        """Создаёт панель управления конкурентами."""
        group = QGroupBox("Конкуренты для анализа")
        layout = QVBoxLayout(group)
        
        # Панель добавления URL
        add_panel = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Введите URL сайта конкурента...")
        self.url_input.returnPressed.connect(self._on_quick_add)
        add_panel.addWidget(self.url_input, stretch=1)
        
        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self._on_quick_add)
        add_panel.addWidget(btn_add)
        
        btn_add_detailed = QPushButton("📝")
        btn_add_detailed.setToolTip("Добавить с названием")
        btn_add_detailed.setFixedWidth(40)
        btn_add_detailed.clicked.connect(self._on_add_competitor_dialog)
        add_panel.addWidget(btn_add_detailed)
        
        layout.addLayout(add_panel)
        
        # Таблица конкурентов
        self.competitors_table = QTableWidget()
        self.competitors_table.setColumnCount(3)
        self.competitors_table.setHorizontalHeaderLabels(["Название", "URL", ""])
        self.competitors_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.competitors_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.competitors_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.competitors_table.setColumnWidth(2, 40)
        self.competitors_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.competitors_table.setAlternatingRowColors(True)
        layout.addWidget(self.competitors_table)
        
        # Кнопки действий
        actions_panel = QHBoxLayout()
        
        self.btn_clear = QPushButton("🗑️ Очистить")
        self.btn_clear.clicked.connect(self._on_clear_competitors)
        actions_panel.addWidget(self.btn_clear)
        
        actions_panel.addStretch()
        
        self.btn_load_files = QPushButton("📁 Загрузить файлы")
        self.btn_load_files.clicked.connect(self._on_load_files)
        actions_panel.addWidget(self.btn_load_files)
        
        layout.addLayout(actions_panel)
        
        # Кнопка запуска
        self.btn_parse = QPushButton("🚀 Запустить анализ")
        self.btn_parse.setObjectName("primaryButton")
        self.btn_parse.setMinimumHeight(50)
        self.btn_parse.clicked.connect(self._on_start_analysis)
        self.btn_parse.setEnabled(False)
        layout.addWidget(self.btn_parse)
        
        # Счётчик
        self.competitors_count = QLabel("Конкурентов: 0")
        self.competitors_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.competitors_count.setStyleSheet("color: #6b7280;")
        layout.addWidget(self.competitors_count)
        
        return group
    
    def _create_results_panel(self) -> QWidget:
        """Создаёт панель с результатами анализа."""
        group = QGroupBox("Результаты анализа")
        layout = QVBoxLayout(group)
        
        # Табы для разных представлений
        tabs = QTabWidget()
        
        # Таб 1: Обзор конкурентов
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(9)
        self.metrics_table.setHorizontalHeaderLabels([
            "Конкурент", "Дизайн", "UX", "Контент", "Доверие", "CTA", "Инновации", "Средний", "Ниша"
        ])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.setMinimumHeight(150)
        overview_layout.addWidget(self.metrics_table)
        
        tabs.addTab(overview_widget, "📊 Метрики")
        
        # Таб 2: Детальная информация о конкурентах
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setFont(QFont("Segoe UI", 10))
        details_layout.addWidget(self.details_text)
        
        tabs.addTab(details_widget, "🏢 О конкурентах")
        
        # Таб 3: SWOT-анализ
        swot_widget = QWidget()
        swot_layout = QVBoxLayout(swot_widget)
        
        self.swot_text = QTextEdit()
        self.swot_text.setReadOnly(True)
        self.swot_text.setFont(QFont("Segoe UI", 10))
        swot_layout.addWidget(self.swot_text)
        
        tabs.addTab(swot_widget, "📈 SWOT-анализ")
        
        # Таб 4: Рекомендации для ВАШЕГО продукта
        recommendations_widget = QWidget()
        recommendations_layout = QVBoxLayout(recommendations_widget)
        
        rec_label = QLabel("💡 Рекомендации для улучшения ВАШЕГО продукта на основе анализа конкурентов:")
        rec_label.setStyleSheet("font-weight: bold; color: #059669; padding: 10px 0;")
        recommendations_layout.addWidget(rec_label)
        
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setFont(QFont("Segoe UI", 10))
        recommendations_layout.addWidget(self.recommendations_text)
        
        tabs.addTab(recommendations_widget, "🎯 Ваши действия")
        
        # Таб 5: Ключевые выводы
        takeaways_widget = QWidget()
        takeaways_layout = QVBoxLayout(takeaways_widget)
        
        self.takeaways_text = QTextEdit()
        self.takeaways_text.setReadOnly(True)
        self.takeaways_text.setFont(QFont("Segoe UI", 11))
        takeaways_layout.addWidget(self.takeaways_text)
        
        tabs.addTab(takeaways_widget, "⭐ Главные выводы")
        
        layout.addWidget(tabs)
        
        # Дисклеймер
        disclaimer = QLabel(
            "⚠️ Анализ носит оценочный характер. Используйте результаты как отправную точку для собственного исследования."
        )
        disclaimer.setObjectName("disclaimer")
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(disclaimer)
        
        return group
    
    def _apply_styles(self):
        """Применяет CSS стили."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fdf8;
            }
            
            #header {
                background-color: transparent;
            }
            
            #title {
                color: #059669;
            }
            
            #subtitle {
                color: #6b7280;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #059669;
            }
            
            QLineEdit {
                padding: 10px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
            }
            
            QLineEdit:focus {
                border-color: #059669;
            }
            
            QPushButton {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: 600;
                color: #374151;
            }
            
            QPushButton:hover {
                background-color: #e5e7eb;
                border-color: #9ca3af;
            }
            
            QPushButton:pressed {
                background-color: #d1d5db;
            }
            
            QPushButton:disabled {
                background-color: #f9fafb;
                color: #9ca3af;
            }
            
            #primaryButton {
                background-color: #059669;
                border-color: #047857;
                color: white;
                font-size: 14px;
            }
            
            #primaryButton:hover {
                background-color: #047857;
            }
            
            #primaryButton:pressed {
                background-color: #065f46;
            }
            
            #primaryButton:disabled {
                background-color: #9ca3af;
                border-color: #9ca3af;
            }
            
            QTableWidget {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                gridline-color: #f3f4f6;
            }
            
            QTableWidget::item {
                padding: 8px;
            }
            
            QTableWidget::item:selected {
                background-color: #d1fae5;
                color: #065f46;
            }
            
            QHeaderView::section {
                background-color: #f0fdf4;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #059669;
                font-weight: bold;
                color: #047857;
            }
            
            QTextEdit {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 10px;
                background-color: #fafafa;
            }
            
            #disclaimer {
                color: #9ca3af;
                font-size: 10px;
                padding: 5px;
            }
            
            QStatusBar {
                background-color: #f0fdf4;
                border-top: 1px solid #d1fae5;
            }
            
            QProgressBar {
                border: 1px solid #d1fae5;
                border-radius: 4px;
                text-align: center;
            }
            
            QProgressBar::chunk {
                background-color: #059669;
                border-radius: 3px;
            }
            
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                background-color: white;
            }
            
            QTabBar::tab {
                background-color: #f3f4f6;
                border: 1px solid #e5e7eb;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
                color: #059669;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #e5e7eb;
            }
        """)
    
    def _on_quick_add(self):
        """Быстрое добавление URL."""
        url = self.url_input.text().strip()
        if not url:
            return
        
        # Добавляем http:// если нет протокола
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        self._add_competitor("", url)
        self.url_input.clear()
    
    def _on_add_competitor_dialog(self):
        """Открывает диалог добавления конкурента."""
        dialog = AddCompetitorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["url"]:
                url = data["url"]
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                self._add_competitor(data["name"], url)
    
    def _add_competitor(self, name: str, url: str):
        """Добавляет конкурента в список."""
        # Проверяем дубликат
        for c in self.competitors:
            if c["url"] == url:
                QMessageBox.warning(self, "Ошибка", "Этот URL уже добавлен")
                return
        
        # Если имя не задано — извлекаем из URL
        if not name:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            name = parsed.netloc.replace("www.", "")
        
        self.competitors.append({"name": name, "url": url})
        self._update_competitors_table()
    
    def _update_competitors_table(self):
        """Обновляет таблицу конкурентов."""
        self.competitors_table.setRowCount(len(self.competitors))
        
        for i, comp in enumerate(self.competitors):
            self.competitors_table.setItem(i, 0, QTableWidgetItem(comp["name"]))
            self.competitors_table.setItem(i, 1, QTableWidgetItem(comp["url"]))
            
            # Кнопка удаления
            btn_delete = QPushButton("✕")
            btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #ef4444;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #dc2626;
                }
            """)
            btn_delete.clicked.connect(lambda checked, row=i: self._on_delete_competitor(row))
            self.competitors_table.setCellWidget(i, 2, btn_delete)
        
        # Обновляем счётчик и кнопку
        count = len(self.competitors)
        self.competitors_count.setText(f"Конкурентов: {count}")
        self.btn_parse.setEnabled(count > 0)
        
        if count > 0:
            self.status_bar.showMessage(f"Готов к анализу {count} конкурент(ов)")
        else:
            self.status_bar.showMessage("Добавьте URL конкурентов для анализа")
    
    def _on_delete_competitor(self, row: int):
        """Удаляет конкурента из списка."""
        if 0 <= row < len(self.competitors):
            del self.competitors[row]
            self._update_competitors_table()
    
    def _on_clear_competitors(self):
        """Очищает список конкурентов."""
        if not self.competitors:
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить весь список конкурентов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.competitors = []
            self._update_competitors_table()
    
    def _on_load_files(self):
        """Обработчик загрузки файлов."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для анализа",
            str(DATA_DIR),
            "Изображения (*.png *.jpg *.jpeg *.webp);;Все файлы (*.*)"
        )
        
        if files:
            self.loaded_files = files
            self._start_worker("analyze_image", {
                "path": files[0],
                "name": Path(files[0]).stem
            })
    
    def _on_start_analysis(self):
        """Запускает анализ всех конкурентов."""
        if not self.competitors:
            QMessageBox.warning(self, "Ошибка", "Добавьте хотя бы одного конкурента")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Запустить анализ {len(self.competitors)} сайт(ов)?\n\n"
            "Это может занять несколько минут.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._start_worker("parse", {"competitors": self.competitors})
    
    def _start_worker(self, task_type: str, data: dict = None):
        """Запускает фоновый поток."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Ошибка", "Дождитесь завершения текущей операции")
            return
        
        self._set_loading(True)
        
        self.worker = AnalysisWorker(task_type, data)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.start()
    
    def _on_worker_finished(self, result: dict):
        """Обработчик завершения анализа."""
        self._set_loading(False)
        
        try:
            if result.get("success"):
                self._display_results(result)
                self.status_bar.showMessage("Анализ завершён успешно", 5000)
            else:
                error_msg = result.get('error', 'Неизвестная ошибка')
                QMessageBox.warning(self, "Ошибка", f"Ошибка анализа: {error_msg}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка отображения",
                f"Произошла ошибка при отображении результатов:\n{str(e)}\n\n"
                "Результаты могли быть сохранены в папку outputs/"
            )
    
    def _on_worker_error(self, error: str):
        """Обработчик ошибки."""
        self._set_loading(False)
        QMessageBox.critical(self, "Ошибка", error)
    
    def _on_worker_progress(self, message: str):
        """Обработчик прогресса."""
        self.status_bar.showMessage(message)
    
    def _set_loading(self, loading: bool):
        """Устанавливает состояние загрузки."""
        self.progress_bar.setVisible(loading)
        self.btn_parse.setEnabled(not loading and len(self.competitors) > 0)
        self.btn_load_files.setEnabled(not loading)
        self.btn_clear.setEnabled(not loading)
    
    def _display_results(self, result: dict):
        """Отображает результаты анализа с новой расширенной структурой."""
        try:
            if "report" in result:
                report = result.get("report") or {}
                results = report.get("results") or []
                
                # Заполняем таблицу метрик
                self.metrics_table.setRowCount(len(results))
                
                all_details = []
                all_swot = []
                all_recommendations = []
                all_takeaways = []
                
                for i, r in enumerate(results):
                    analysis = r.get("analysis") or {}
                    name = r.get("name", "—")
                    
                    # Извлекаем данные о компании
                    company_info = analysis.get("company_info") or {}
                    metrics = analysis.get("metrics") or {}
                    competitive = analysis.get("competitive_analysis") or {}
                    
                    # Извлекаем метрики (новая структура)
                    design = self._get_metric_score(metrics, "visual_design")
                    ux = self._get_metric_score(metrics, "usability")
                    content = self._get_metric_score(metrics, "content_quality")
                    trust = self._get_metric_score(metrics, "trust_signals")
                    cta = self._get_metric_score(metrics, "call_to_action")
                    innovation = self._get_metric_score(metrics, "innovation")
                    avg = analysis.get("average_score", 0)
                    niche = company_info.get("niche", "—")[:30]
                    
                    # Заполняем таблицу
                    self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
                    self.metrics_table.setItem(i, 1, QTableWidgetItem(str(design)))
                    self.metrics_table.setItem(i, 2, QTableWidgetItem(str(ux)))
                    self.metrics_table.setItem(i, 3, QTableWidgetItem(str(content)))
                    self.metrics_table.setItem(i, 4, QTableWidgetItem(str(trust)))
                    self.metrics_table.setItem(i, 5, QTableWidgetItem(str(cta)))
                    self.metrics_table.setItem(i, 6, QTableWidgetItem(str(innovation)))
                    self.metrics_table.setItem(i, 7, QTableWidgetItem(str(avg)))
                    self.metrics_table.setItem(i, 8, QTableWidgetItem(niche))
                    
                    # Цветовая индикация среднего балла
                    if avg > 0:
                        self._color_cell(self.metrics_table.item(i, 7), avg)
                    
                    # Собираем детальную информацию
                    if analysis and company_info:
                        detail = self._format_company_details(name, company_info, metrics, analysis)
                        all_details.append(detail)
                        
                        # SWOT
                        swot = self._format_swot(name, competitive)
                        all_swot.append(swot)
                        
                        # Рекомендации для пользователя
                        recs = analysis.get("recommendations_for_user") or []
                        if recs:
                            all_recommendations.append(f"📌 На основе анализа {name}:")
                            all_recommendations.extend([f"   • {rec}" for rec in recs])
                            all_recommendations.append("")
                        
                        # Ключевые выводы
                        takeaways = analysis.get("key_takeaways") or []
                        if takeaways:
                            all_takeaways.append(f"🏢 {name}:")
                            all_takeaways.extend([f"   ⭐ {t}" for t in takeaways])
                            all_takeaways.append("")
                    else:
                        error_msg = r.get("parsing_error") or r.get("analysis_error") or "Анализ не выполнен"
                        all_details.append(f"### {name}\n⚠️ {error_msg}\n")
                
                # Заполняем вкладки
                self.details_text.setPlainText("\n".join(all_details) if all_details else "Нет данных")
                self.swot_text.setPlainText("\n".join(all_swot) if all_swot else "Нет данных")
                self.recommendations_text.setPlainText(
                    "\n".join(all_recommendations) if all_recommendations else "Нет рекомендаций"
                )
                self.takeaways_text.setPlainText(
                    "\n".join(all_takeaways) if all_takeaways else "Нет выводов"
                )
            
            # Одиночный анализ
            elif "data" in result:
                self._display_single_result(result.get("data") or {})
                    
        except Exception as e:
            self.details_text.setPlainText(f"Ошибка отображения результатов:\n{str(e)}")
            self.recommendations_text.setPlainText("—")
    
    def _get_metric_score(self, metrics: dict, key: str) -> int:
        """Извлекает оценку из метрики."""
        metric = metrics.get(key) or {}
        if isinstance(metric, dict):
            return metric.get("score", 0)
        return 0
    
    def _format_company_details(self, name: str, company_info: dict, metrics: dict, analysis: dict) -> str:
        """Форматирует детальную информацию о компании."""
        lines = [
            f"{'='*60}",
            f"🏢 {name}",
            f"{'='*60}",
            "",
            f"📌 Слоган: {company_info.get('tagline', '—')}",
            f"🎯 Ниша: {company_info.get('niche', '—')}",
            f"👥 Целевая аудитория: {company_info.get('target_audience', '—')}",
            f"💼 Главный оффер: {company_info.get('main_offer', '—')}",
            ""
        ]
        
        # УТП
        usps = company_info.get("unique_selling_points") or []
        if usps:
            lines.append("✨ Уникальные преимущества:")
            for usp in usps:
                lines.append(f"   • {usp}")
            lines.append("")
        
        # Подробные метрики
        lines.append("📊 Детальные оценки:")
        for key, label in [
            ("visual_design", "Визуальный дизайн"),
            ("usability", "Удобство использования"),
            ("content_quality", "Качество контента"),
            ("trust_signals", "Элементы доверия"),
            ("call_to_action", "Призывы к действию"),
            ("mobile_friendliness", "Мобильная версия"),
            ("innovation", "Инновационность")
        ]:
            metric = metrics.get(key) or {}
            score = metric.get("score", 0) if isinstance(metric, dict) else 0
            desc = metric.get("description", "") if isinstance(metric, dict) else ""
            bar = "█" * score + "░" * (10 - score)
            lines.append(f"   {label}: [{bar}] {score}/10")
            if desc:
                lines.append(f"      → {desc}")
        
        lines.append("")
        
        # Позиционирование
        summary = analysis.get("positioning_summary", "")
        if summary:
            lines.append(f"📝 Резюме позиционирования:")
            lines.append(f"   {summary}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_swot(self, name: str, competitive: dict) -> str:
        """Форматирует SWOT-анализ."""
        lines = [
            f"{'='*50}",
            f"📈 SWOT: {name}",
            f"{'='*50}",
            ""
        ]
        
        # Сильные стороны
        strengths = competitive.get("strengths") or []
        lines.append("💪 СИЛЬНЫЕ СТОРОНЫ конкурента:")
        if strengths:
            for s in strengths:
                lines.append(f"   ✅ {s}")
        else:
            lines.append("   — Не определены")
        lines.append("")
        
        # Слабые стороны
        weaknesses = competitive.get("weaknesses") or []
        lines.append("⚠️ СЛАБЫЕ СТОРОНЫ конкурента (ваши возможности!):")
        if weaknesses:
            for w in weaknesses:
                lines.append(f"   ❌ {w}")
        else:
            lines.append("   — Не определены")
        lines.append("")
        
        # Возможности
        opportunities = competitive.get("opportunities") or []
        lines.append("🚀 ВОЗМОЖНОСТИ для вашего продукта:")
        if opportunities:
            for o in opportunities:
                lines.append(f"   💡 {o}")
        else:
            lines.append("   — Не определены")
        lines.append("")
        
        # Угрозы
        threats = competitive.get("threats") or []
        lines.append("⚡ УГРОЗЫ (на что обратить внимание):")
        if threats:
            for t in threats:
                lines.append(f"   🔴 {t}")
        else:
            lines.append("   — Не определены")
        lines.append("")
        
        return "\n".join(lines)
    
    def _display_single_result(self, analysis: dict):
        """Отображает результат одиночного анализа."""
        if not analysis:
            self.details_text.setPlainText("Анализ не выполнен")
            return
        
        company_info = analysis.get("company_info") or {}
        metrics = analysis.get("metrics") or {}
        competitive = analysis.get("competitive_analysis") or {}
        name = company_info.get("name", "Файл")
        
        # Таблица
        self.metrics_table.setRowCount(1)
        self.metrics_table.setItem(0, 0, QTableWidgetItem(name))
        self.metrics_table.setItem(0, 1, QTableWidgetItem(str(self._get_metric_score(metrics, "visual_design"))))
        self.metrics_table.setItem(0, 2, QTableWidgetItem(str(self._get_metric_score(metrics, "usability"))))
        self.metrics_table.setItem(0, 3, QTableWidgetItem(str(self._get_metric_score(metrics, "content_quality"))))
        self.metrics_table.setItem(0, 4, QTableWidgetItem(str(self._get_metric_score(metrics, "trust_signals"))))
        self.metrics_table.setItem(0, 5, QTableWidgetItem(str(self._get_metric_score(metrics, "call_to_action"))))
        self.metrics_table.setItem(0, 6, QTableWidgetItem(str(self._get_metric_score(metrics, "innovation"))))
        self.metrics_table.setItem(0, 7, QTableWidgetItem(str(analysis.get("average_score", 0))))
        self.metrics_table.setItem(0, 8, QTableWidgetItem(company_info.get("niche", "—")[:30]))
        
        # Детали
        self.details_text.setPlainText(self._format_company_details(name, company_info, metrics, analysis))
        
        # SWOT
        self.swot_text.setPlainText(self._format_swot(name, competitive))
        
        # Рекомендации
        recs = analysis.get("recommendations_for_user") or []
        self.recommendations_text.setPlainText(
            "\n".join([f"• {r}" for r in recs]) if recs else "Нет рекомендаций"
        )
        
        # Выводы
        takeaways = analysis.get("key_takeaways") or []
        self.takeaways_text.setPlainText(
            "\n".join([f"⭐ {t}" for t in takeaways]) if takeaways else "Нет выводов"
        )
    
    def _color_cell(self, item: QTableWidgetItem, value: float):
        """Окрашивает ячейку в зависимости от значения."""
        if value >= 7:
            item.setBackground(QColor("#d1fae5"))  # Зелёный
        elif value >= 5:
            item.setBackground(QColor("#fef3c7"))  # Жёлтый
        else:
            item.setBackground(QColor("#fee2e2"))  # Красный


def run_app():
    """Запускает приложение."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    run_app()
