"""
Главный файл приложения - генератор фоторамок из стикеров
"""

import os
import sys
import random
import math
import json
import io
from pathlib import Path
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw

# PyQt6 импорты
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QComboBox, QCheckBox, QScrollArea, QFrame,
    QSizePolicy, QButtonGroup, QRadioButton, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor

# Импорты из наших модулей
from frame_config import FrameConfig, BorderSide, AlgorithmType
import algorithms


def pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
    """Конвертирует PIL.Image в QPixmap для PyQt6"""
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return pixmap


class StickerFrameGenerator:
    """Генератор фоторамок из стикеров"""
    
    def __init__(self, config: FrameConfig):
        self.config = config
        self.stickers: List = []
        self.loaded_stickers: List[Image.Image] = []
        
        if config.sticker_dir:
            self._load_stickers()
    
    def _load_stickers(self):
        """Загружает все PNG файлы из указанной директории."""
        sticker_dir = Path(self.config.sticker_dir)
        if not sticker_dir.exists():
            raise ValueError(f"Директория не найдена: {self.config.sticker_dir}")
        
        self.loaded_stickers.clear()
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
            for img_file in sticker_dir.glob(ext):
                try:
                    img = Image.open(img_file).convert("RGBA")
                    self.loaded_stickers.append(img)
                except Exception as e:
                    print(f"Ошибка загрузки {img_file}: {e}")
    
    def _rotate_sticker(self, sticker_img: Image.Image, angle: float) -> Image.Image:
        """Поворачивает изображение стикера."""
        if angle == 0:
            return sticker_img.copy()
            
        rotated = sticker_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        
        if rotated.mode in ('RGBA', 'LA'):
            alpha = rotated.split()[-1]
            return rotated.convert("RGBA")
        
        return Image.new("RGBA", rotated.size, (0, 0, 0, 0))
    
    def _apply_opacity(self, sticker_img: Image.Image, opacity: float) -> Image.Image:
        """Применяет прозрачность к изображению стикера."""
        if opacity >= 1.0:
            return sticker_img
            
        result = sticker_img.copy()
        alpha = result.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
        result.putalpha(alpha)
        return result
    
    def generate(self, max_attempts: int = 500) -> Optional[Image.Image]:
        """Генерирует фоторамку со стикерами."""
        if not self.loaded_stickers or not self.config.template_size:
            return None
        
        # Выбираем алгоритм в зависимости от настроек
        if self.config.algorithm == AlgorithmType.BASE:
            algorithm = algorithms.BaseAlgorithm(self.config)
        elif self.config.algorithm == AlgorithmType.UNIFORM:
            algorithm = algorithms.UniformAlgorithm(self.config)
        elif self.config.algorithm == AlgorithmType.GRADIENT:
            algorithm = algorithms.GradientAlgorithm(self.config)
        elif self.config.algorithm == AlgorithmType.CORNER:
            algorithm = algorithms.CornerAlgorithm(self.config)
        else:
            algorithm = algorithms.BaseAlgorithm(self.config)
        
        algorithm.calculate_sticker_zone()
        
        # Создаем изображение с фоном
        template_w, template_h = self.config.template_size
        result = Image.new("RGBA", (template_w, template_h), self.config.background_color)
        
        placed_stickers = []
        attempts = 0
        
        while attempts < max_attempts and len(placed_stickers) < len(algorithm.perimeter_positions) // 2:
            attempts += 1
            
            # Выбираем случайный стикер
            sticker_img = random.choice(self.loaded_stickers)
            
            # Размер
            size = random.randint(self.config.min_sticker_size, self.config.max_sticker_size)
            
            # Сохраняем пропорции
            orig_w, orig_h = sticker_img.size
            aspect = orig_w / orig_h
            
            if random.choice([True, False]):
                width = size
                height = int(width / aspect)
            else:
                height = size
                width = int(height * aspect)
            
            # Масштабируем
            scaled = sticker_img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Поворот
            rotation = random.uniform(-180, 180) if self.config.random_rotation else 0
            
            # Прозрачность
            if self.config.random_opacity:
                opacity = random.uniform(self.config.min_opacity, self.config.max_opacity)
            else:
                opacity = 1.0
            
            # Пытаемся найти позицию
            found = False
            for pos in random.sample(algorithm.perimeter_positions, min(20, len(algorithm.perimeter_positions))):
                # Для градиентных алгоритмов учитываем плотность
                if hasattr(algorithm, 'get_gradient_density'):
                    gradient_factor = algorithm.get_gradient_density(pos)
                    effective_density = self.config.sticker_density * gradient_factor
                    if random.random() > effective_density:
                        continue
                
                sticker_config = type('StickerConfig', (), {
                    'path': "", 'size': (width, height),
                    'position': pos, 'rotation': rotation,
                    'opacity': opacity
                })()
                
                if algorithm.is_position_valid(sticker_config, placed_stickers):
                    # Применяем трансформации
                    if rotation != 0:
                        transformed = self._rotate_sticker(scaled, rotation)
                    else:
                        transformed = scaled
                    
                    if opacity < 1.0:
                        transformed = self._apply_opacity(transformed, opacity)
                    
                    # Добавляем на изображение
                    result.alpha_composite(transformed, pos)
                    placed_stickers.append(sticker_config)
                    found = True
                    break
            
            if not found:
                break
        
        # Масштабируем до выходного размера
        if self.config.output_size != self.config.template_size:
            result = result.resize(self.config.output_size, Image.Resampling.LANCZOS)
        
        return result


class GenerationThread(QThread):
    """Поток для генерации фоторамки"""
    generation_complete = pyqtSignal(object)
    generation_error = pyqtSignal(str)
    
    def __init__(self, config: FrameConfig):
        super().__init__()
        self.config = config
    
    def run(self):
        try:
            generator = StickerFrameGenerator(self.config)
            result = generator.generate()
            if result:
                self.generation_complete.emit(result)
            else:
                self.generation_error.emit("Не удалось сгенерировать изображение")
        except Exception as e:
            self.generation_error.emit(str(e))


class PreviewWidget(QLabel):
    """Виджет для предпросмотра с фиксированным соотношением сторон"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            PreviewWidget {
                background-color: #2d2d2d;
                border: 2px solid #444444;
                border-radius: 5px;
            }
        """)
        self.setText("Предпросмотр появится здесь")
        self.setFont(QFont("Arial", 12))
        self._aspect_ratio = 16/9
        self._current_pixmap = None
    
    def set_aspect_ratio(self, width: int, height: int):
        """Устанавливает соотношение сторон для предпросмотра"""
        if height > 0:
            self._aspect_ratio = width / height
    
    def update_preview(self, image: Image.Image):
        """Обновляет предпросмотр с новым изображением"""
        if image:
            self._aspect_ratio = image.width / image.height
            self._current_pixmap = pil_to_pixmap(image)
            self._update_display()
    
    def resizeEvent(self, event):
        """Переопределяем событие изменения размера"""
        super().resizeEvent(event)
        self._update_display()
    
    def _update_display(self):
        """Обновляет отображение с сохранением соотношения сторон"""
        if self._current_pixmap:
            container_size = self.size()
            pixmap_size = self._current_pixmap.size()
            pixmap_aspect = pixmap_size.width() / pixmap_size.height()
            
            if container_size.width() / container_size.height() > pixmap_aspect:
                new_height = container_size.height()
                new_width = int(new_height * pixmap_aspect)
            else:
                new_width = container_size.width()
                new_height = int(new_width / pixmap_aspect)
            
            scaled_pixmap = self._current_pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)


class SettingsPanel(QWidget):
    """Панель настроек с фиксированной шириной"""
    
    settings_changed = pyqtSignal(FrameConfig)
    generate_requested = pyqtSignal()
    save_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.config = FrameConfig()
        self.init_ui()
        self.setFixedWidth(380)  # Чуть шире для нового выбора алгоритма
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Прокручиваемая область
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        settings_content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(10)
        
        # === ГРУППА: Основные настройки ===
        basic_group = QGroupBox("Основные настройки")
        basic_layout = QFormLayout()
        basic_layout.setSpacing(5)
        
        # Размер шаблона
        size_layout = QHBoxLayout()
        self.template_width = QSpinBox()
        self.template_width.setRange(100, 5000)
        self.template_width.setValue(1200)
        self.template_width.valueChanged.connect(self.on_settings_changed)
        self.template_height = QSpinBox()
        self.template_height.setRange(100, 5000)
        self.template_height.setValue(800)
        self.template_height.valueChanged.connect(self.on_settings_changed)
        
        size_layout.addWidget(QLabel("Ш:"))
        size_layout.addWidget(self.template_width)
        size_layout.addWidget(QLabel("В:"))
        size_layout.addWidget(self.template_height)
        size_layout.addStretch()
        basic_layout.addRow("Размер шаблона:", size_layout)
        
        # Размер вывода
        output_layout = QHBoxLayout()
        self.output_width = QSpinBox()
        self.output_width.setRange(100, 8000)
        self.output_width.setValue(1920)
        self.output_width.valueChanged.connect(self.on_settings_changed)
        self.output_height = QSpinBox()
        self.output_height.setRange(100, 8000)
        self.output_height.setValue(1080)
        self.output_height.valueChanged.connect(self.on_settings_changed)
        
        output_layout.addWidget(QLabel("Ш:"))
        output_layout.addWidget(self.output_width)
        output_layout.addWidget(QLabel("В:"))
        output_layout.addWidget(self.output_height)
        output_layout.addStretch()
        basic_layout.addRow("Размер вывода:", output_layout)
        
        # Алгоритм размещения
        self.algorithm_combo = QComboBox()
        for algo in AlgorithmType:
            self.algorithm_combo.addItem(algo.value, algo)
        self.algorithm_combo.currentIndexChanged.connect(self.on_settings_changed)
        basic_layout.addRow("Алгоритм:", self.algorithm_combo)
        
        # Соотношение сторон предпросмотра
        self.preview_aspect_check = QCheckBox("Сохранять соотношение сторон")
        self.preview_aspect_check.setChecked(True)
        self.preview_aspect_check.stateChanged.connect(self.on_settings_changed)
        basic_layout.addRow(self.preview_aspect_check)
        
        basic_group.setLayout(basic_layout)
        content_layout.addWidget(basic_group)
        
        # === ГРУППА: Стикеры ===
        sticker_group = QGroupBox("Стикеры")
        sticker_layout = QFormLayout()
        sticker_layout.setSpacing(5)
        
        # Директория со стикерами
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("Не выбрана")
        self.dir_label.setStyleSheet("color: #888;")
        dir_button = QPushButton("Выбрать...")
        dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(dir_button)
        sticker_layout.addRow("Директория:", dir_layout)
        
        # Размеры стикеров
        size_range_layout = QHBoxLayout()
        self.min_size = QSpinBox()
        self.min_size.setRange(10, 1000)
        self.min_size.setValue(40)
        self.min_size.valueChanged.connect(self.on_settings_changed)
        self.max_size = QSpinBox()
        self.max_size.setRange(10, 1000)
        self.max_size.setValue(150)
        self.max_size.valueChanged.connect(self.on_settings_changed)
        
        size_range_layout.addWidget(QLabel("Мин:"))
        size_range_layout.addWidget(self.min_size)
        size_range_layout.addWidget(QLabel("Макс:"))
        size_range_layout.addWidget(self.max_size)
        size_range_layout.addStretch()
        sticker_layout.addRow("Размер стикеров:", size_range_layout)
        
        # Плотность
        self.density_slider = QSlider(Qt.Orientation.Horizontal)
        self.density_slider.setRange(1, 100)
        self.density_slider.setValue(60)
        self.density_slider.valueChanged.connect(self.on_settings_changed)
        self.density_label = QLabel("60%")
        density_layout = QHBoxLayout()
        density_layout.addWidget(self.density_slider)
        density_layout.addWidget(self.density_label)
        sticker_layout.addRow("Плотность:", density_layout)
        
        # Ширина рамки
        self.border_width = QSpinBox()
        self.border_width.setRange(10, 500)
        self.border_width.setValue(100)
        self.border_width.valueChanged.connect(self.on_settings_changed)
        sticker_layout.addRow("Ширина рамки:", self.border_width)
        
        # Заход за границу
        self.border_overlap = QSpinBox()
        self.border_overlap.setRange(0, 200)
        self.border_overlap.setValue(20)
        self.border_overlap.valueChanged.connect(self.on_settings_changed)
        sticker_layout.addRow("Заход за границу:", self.border_overlap)
        
        sticker_group.setLayout(sticker_layout)
        content_layout.addWidget(sticker_group)
        
        # === ГРУППА: Размещение ===
        placement_group = QGroupBox("Размещение стикеров")
        placement_layout = QVBoxLayout()
        placement_layout.setSpacing(5)
        
        # Стороны для размещения
        sides_group = QButtonGroup(self)
        sides_layout = QGridLayout()
        
        sides = [
            ("Все стороны", BorderSide.ALL),
            ("Только верх", BorderSide.TOP),
            ("Только низ", BorderSide.BOTTOM),
            ("Только лево", BorderSide.LEFT),
            ("Только право", BorderSide.RIGHT),
            ("Верх и низ", BorderSide.TOP_BOTTOM),
            ("Лево и право", BorderSide.LEFT_RIGHT),
            ("Только углы", BorderSide.CORNERS)
        ]
        
        row, col = 0, 0
        for text, side in sides:
            radio = QRadioButton(text)
            radio.setProperty("side", side.value)
            if side == BorderSide.ALL:
                radio.setChecked(True)
            sides_group.addButton(radio)
            sides_layout.addWidget(radio, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
        
        sides_group.buttonClicked.connect(self.on_side_changed)
        placement_layout.addLayout(sides_layout)
        
        # Градиентное заполнение
        gradient_layout = QHBoxLayout()
        self.gradient_check = QCheckBox("Градиентная плотность")
        self.gradient_check.setChecked(False)
        self.gradient_check.stateChanged.connect(self.on_settings_changed)
        
        self.gradient_combo = QComboBox()
        self.gradient_combo.addItems(["Линейный", "Радиальный"])
        self.gradient_combo.currentTextChanged.connect(self.on_settings_changed)
        self.gradient_combo.setEnabled(False)
        
        gradient_layout.addWidget(self.gradient_check)
        gradient_layout.addWidget(self.gradient_combo)
        placement_layout.addLayout(gradient_layout)
        
        # Перекрытие
        self.overlap_check = QCheckBox("Разрешить перекрытие")
        self.overlap_check.setChecked(True)
        self.overlap_check.stateChanged.connect(self.on_settings_changed)
        placement_layout.addWidget(self.overlap_check)
        
        placement_group.setLayout(placement_layout)
        content_layout.addWidget(placement_group)
        
        # === ГРУППА: Эффекты ===
        effects_group = QGroupBox("Эффекты")
        effects_layout = QFormLayout()
        effects_layout.setSpacing(5)
        
        # Поворот
        self.rotation_check = QCheckBox("Случайный поворот")
        self.rotation_check.setChecked(True)
        self.rotation_check.stateChanged.connect(self.on_settings_changed)
        effects_layout.addRow(self.rotation_check)
        
        # Прозрачность
        opacity_layout = QHBoxLayout()
        self.opacity_check = QCheckBox("Случайная прозрачность")
        self.opacity_check.setChecked(False)
        self.opacity_check.stateChanged.connect(self.on_settings_changed)
        
        self.min_opacity = QDoubleSpinBox()
        self.min_opacity.setRange(0.1, 1.0)
        self.min_opacity.setValue(0.7)
        self.min_opacity.setSingleStep(0.1)
        self.min_opacity.valueChanged.connect(self.on_settings_changed)
        self.min_opacity.setEnabled(False)
        
        self.max_opacity = QDoubleSpinBox()
        self.max_opacity.setRange(0.1, 1.0)
        self.max_opacity.setValue(1.0)
        self.max_opacity.setSingleStep(0.1)
        self.max_opacity.valueChanged.connect(self.on_settings_changed)
        self.max_opacity.setEnabled(False)
        
        opacity_layout.addWidget(self.opacity_check)
        opacity_layout.addWidget(QLabel("от"))
        opacity_layout.addWidget(self.min_opacity)
        opacity_layout.addWidget(QLabel("до"))
        opacity_layout.addWidget(self.max_opacity)
        effects_layout.addRow(opacity_layout)
        
        # Автогенерация предпросмотра
        self.auto_preview_check = QCheckBox("Автогенерация предпросмотра")
        self.auto_preview_check.setChecked(True)
        self.auto_preview_check.stateChanged.connect(self.on_settings_changed)
        effects_layout.addRow(self.auto_preview_check)
        
        effects_group.setLayout(effects_layout)
        content_layout.addWidget(effects_group)
        
        # === ГРУППА: Выходной файл ===
        output_group = QGroupBox("Выходной файл")
        output_layout = QFormLayout()
        output_layout.setSpacing(5)
        
        # Формат вывода
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "WEBP"])
        self.format_combo.currentTextChanged.connect(self.on_settings_changed)
        output_layout.addRow("Формат:", self.format_combo)
        
        output_group.setLayout(output_layout)
        content_layout.addWidget(output_group)
        
        # Растягивающийся элемент
        content_layout.addStretch()
        
        settings_content.setLayout(content_layout)
        scroll_area.setWidget(settings_content)
        layout.addWidget(scroll_area)
        
        # === КНОПКИ ВНИЗУ ===
        button_container = QWidget()
        button_layout = QVBoxLayout()
        button_layout.setSpacing(5)
        
        # Кнопка генерации
        self.generate_btn = QPushButton("🎨 Сгенерировать фоторамку")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_requested.emit)
        
        # Кнопка сохранения
        self.save_btn = QPushButton("💾 Сохранить изображение")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        self.save_btn.clicked.connect(self.save_requested.emit)
        
        # Кнопка случайных настроек
        self.random_btn = QPushButton("🎲 Случайные настройки")
        self.random_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.random_btn.clicked.connect(self.random_settings)
        
        button_layout.addWidget(self.generate_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.random_btn)
        
        button_container.setLayout(button_layout)
        layout.addWidget(button_container)
        
        self.setLayout(layout)
    
    def select_directory(self):
        """Выбор директории со стикерами"""
        directory = QFileDialog.getExistingDirectory(
            self, "Выберите директорию со стикерами"
        )
        if directory:
            self.dir_label.setText(os.path.basename(directory))
            self.dir_label.setToolTip(directory)
            self.dir_label.setStyleSheet("color: white;")
            self.config.sticker_dir = directory
            self.on_settings_changed()
    
    def on_side_changed(self, button):
        """Обработчик изменения выбранной стороны"""
        side_value = button.property("side")
        for side in BorderSide:
            if side.value == side_value:
                self.config.border_sides = side
                break
        self.on_settings_changed()
    
    def on_settings_changed(self):
        """Обработчик изменения настроек"""
        # Основные настройки
        self.config.template_size = (
            self.template_width.value(),
            self.template_height.value()
        )
        self.config.output_size = (
            self.output_width.value(),
            self.output_height.value()
        )
        self.config.preview_aspect = self.preview_aspect_check.isChecked()
        
        # Выбор алгоритма
        self.config.algorithm = self.algorithm_combo.currentData()
        
        # Стикеры
        self.config.min_sticker_size = self.min_size.value()
        self.config.max_sticker_size = self.max_size.value()
        self.config.sticker_density = self.density_slider.value() / 100.0
        self.config.border_width = self.border_width.value()
        self.config.border_overlap = self.border_overlap.value()
        
        # Обновляем метку плотности
        self.density_label.setText(f"{self.density_slider.value()}%")
        
        # Эффекты
        self.config.overlap_allowed = self.overlap_check.isChecked()
        self.config.random_rotation = self.rotation_check.isChecked()
        self.config.random_opacity = self.opacity_check.isChecked()
        self.config.min_opacity = self.min_opacity.value()
        self.config.max_opacity = self.max_opacity.value()
        self.config.preview_auto = self.auto_preview_check.isChecked()
        
        # Градиент
        self.config.gradient_density = self.gradient_check.isChecked()
        gradient_text = self.gradient_combo.currentText()
        self.config.gradient_type = "linear" if gradient_text == "Линейный" else "radial"
        
        # Выходной файл
        self.config.output_format = self.format_combo.currentText()
        
        # Включаем/выключаем связанные элементы
        self.gradient_combo.setEnabled(self.gradient_check.isChecked())
        self.min_opacity.setEnabled(self.opacity_check.isChecked())
        self.max_opacity.setEnabled(self.opacity_check.isChecked())
        
        # Эмитируем сигнал
        self.settings_changed.emit(self.config)
        
        # Если включена автогенерация, запрашиваем генерацию
        if self.config.preview_auto and self.config.sticker_dir:
            self.generate_requested.emit()
    
    def random_settings(self):
        """Случайные настройки"""
        # Случайный размер шаблона
        sizes = [(800, 600), (1200, 800), (1600, 900), (1920, 1080)]
        size = random.choice(sizes)
        self.template_width.setValue(size[0])
        self.template_height.setValue(size[1])
        
        # Случайный алгоритм
        self.algorithm_combo.setCurrentIndex(random.randint(0, self.algorithm_combo.count()-1))
        
        # Случайная плотность
        self.density_slider.setValue(random.randint(30, 90))
        
        # Случайные размеры стикеров
        self.min_size.setValue(random.randint(20, 80))
        self.max_size.setValue(random.randint(100, 250))
        
        # Случайная ширина рамки
        self.border_width.setValue(random.randint(50, 200))
        
        # Случайный заход за границу
        self.border_overlap.setValue(random.randint(0, 100))
        
        # Случайные стороны
        sides = list(BorderSide)
        random_side = random.choice(sides)
        for btn in self.findChildren(QRadioButton):
            if btn.property("side") == random_side.value:
                btn.setChecked(True)
                break
        
        # Случайные флажки
        self.overlap_check.setChecked(random.choice([True, False]))
        self.rotation_check.setChecked(random.choice([True, False]))
        self.opacity_check.setChecked(random.choice([True, False]))
        self.gradient_check.setChecked(random.choice([True, False]))
        
        # Случайный тип градиента
        self.gradient_combo.setCurrentIndex(random.randint(0, 1))
        
        # Случайная прозрачность
        self.min_opacity.setValue(round(random.uniform(0.3, 0.8), 1))
        self.max_opacity.setValue(round(random.uniform(0.8, 1.0), 1))
    
    def get_config(self) -> FrameConfig:
        """Возвращает текущую конфигурацию"""
        return self.config
    
    def enable_save_button(self, enabled: bool):
        """Включает или выключает кнопку сохранения"""
        self.save_btn.setEnabled(enabled)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.current_image = None
        self.generation_thread = None
        self.init_ui()
        self.setWindowTitle("Генератор фоторамок из стикеров")
        self.setGeometry(100, 100, 1400, 800)
    
    def init_ui(self):
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной макет
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === ЛЕВАЯ ПАНЕЛЬ: Настройки ===
        self.settings_panel = SettingsPanel()
        self.settings_panel.settings_changed.connect(self.on_settings_changed)
        self.settings_panel.generate_requested.connect(self.generate_frame)
        self.settings_panel.save_requested.connect(self.save_image)
        
        # === ПРАВАЯ ПАНЕЛЬ: Только предпросмотр ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        # Панель предпросмотра
        preview_group = QGroupBox("Предпросмотр")
        preview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 14px;
            }
        """)
        
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(5, 15, 5, 5)
        
        # Виджет предпросмотра
        self.preview_widget = PreviewWidget()
        preview_layout.addWidget(self.preview_widget)
        
        # Информационная панель
        info_layout = QHBoxLayout()
        
        self.resolution_label = QLabel("Шаблон: 1200×800")
        self.resolution_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.stickers_label = QLabel("Стикеры: 0")
        self.stickers_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.algorithm_label = QLabel("Алгоритм: Базовый")
        self.algorithm_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px;")
        
        info_layout.addWidget(self.resolution_label)
        info_layout.addWidget(self.stickers_label)
        info_layout.addWidget(self.algorithm_label)
        info_layout.addStretch()
        info_layout.addWidget(self.status_label)
        
        preview_layout.addLayout(info_layout)
        preview_group.setLayout(preview_layout)
        
        right_layout.addWidget(preview_group)
        
        right_panel.setLayout(right_layout)
        
        # Добавляем панели в основной макет
        main_layout.addWidget(self.settings_panel)
        main_layout.addWidget(right_panel, 1)
        
        central_widget.setLayout(main_layout)
        
        # Строка состояния
        self.statusBar().showMessage("Готов к работе")
    
    def on_settings_changed(self, config: FrameConfig):
        """Обработчик изменения настроек"""
        # Обновляем информацию
        self.resolution_label.setText(f"Шаблон: {config.template_size[0]}×{config.template_size[1]}")
        self.algorithm_label.setText(f"Алгоритм: {config.algorithm.value}")
        
        # Обновляем количество стикеров
        if config.sticker_dir:
            try:
                sticker_dir = Path(config.sticker_dir)
                count = len(list(sticker_dir.glob("*.png"))) + \
                        len(list(sticker_dir.glob("*.jpg"))) + \
                        len(list(sticker_dir.glob("*.jpeg"))) + \
                        len(list(sticker_dir.glob("*.webp")))
                self.stickers_label.setText(f"Стикеры: {count}")
            except:
                self.stickers_label.setText("Стикеры: ошибка")
        else:
            self.stickers_label.setText("Стикеры: не выбрано")
        
        # Обновляем соотношение сторон в предпросмотре
        if config.preview_aspect:
            self.preview_widget.set_aspect_ratio(*config.template_size)
    
    def generate_frame(self):
        """Генерация фоторамки"""
        config = self.settings_panel.get_config()
        
        if not config.sticker_dir or not os.path.exists(config.sticker_dir):
            QMessageBox.warning(self, "Ошибка", "Выберите директорию со стикерами")
            return
        
        # Отключаем кнопки на время генерации
        self.settings_panel.generate_btn.setEnabled(False)
        self.settings_panel.save_btn.setEnabled(False)
        self.status_label.setText("Генерация...")
        self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 11px;")
        
        # Запускаем в отдельном потоке
        self.generation_thread = GenerationThread(config)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)
        self.generation_thread.generation_error.connect(self.on_generation_error)
        self.generation_thread.start()
    
    def on_generation_complete(self, image: Image.Image):
        """Обработчик завершения генерации"""
        self.current_image = image
        self.preview_widget.update_preview(image)
        self.settings_panel.enable_save_button(True)
        self.settings_panel.generate_btn.setEnabled(True)
        self.status_label.setText("Готово")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px;")
        self.statusBar().showMessage(f"Фоторамка сгенерирована. Размер: {image.size[0]}×{image.size[1]}")
    
    def on_generation_error(self, error_msg: str):
        """Обработчик ошибки генерации"""
        QMessageBox.critical(self, "Ошибка генерации", error_msg)
        self.settings_panel.generate_btn.setEnabled(True)
        self.settings_panel.enable_save_button(False)
        self.status_label.setText("Ошибка")
        self.status_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 11px;")
        self.statusBar().showMessage(f"Ошибка: {error_msg}")
    
    def save_image(self):
        """Сохранение изображения"""
        if not self.current_image:
            return
        
        config = self.settings_panel.get_config()
        
        # Определяем расширение файла
        extensions = {
            "PNG": "png",
            "JPEG": "jpg",
            "WEBP": "webp"
        }
        
        ext = extensions.get(config.output_format, "png")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить фоторамку",
            f"sticker_frame_{config.template_size[0]}x{config.template_size[1]}_{config.algorithm.name.lower()}.{ext}",
            f"Изображения (*.{ext})"
        )
        
        if file_path:
            try:
                # Конвертируем формат если нужно
                if config.output_format == "JPEG":
                    self.current_image = self.current_image.convert("RGB")
                
                self.current_image.save(file_path, config.output_format.upper())
                self.statusBar().showMessage(f"Изображение сохранено: {file_path}")
                QMessageBox.information(self, "Успех", f"Изображение сохранено в:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        if self.generation_thread and self.generation_thread.isRunning():
            self.generation_thread.terminate()
            self.generation_thread.wait()
        event.accept()


def create_test_stickers(directory="test_stickers"):
    """Создает тестовые стикеры"""
    os.makedirs(directory, exist_ok=True)
    
    shapes = [
        ("circle", "Круг", (255, 0, 0, 200)),
        ("square", "Квадрат", (0, 255, 0, 200)),
        ("triangle", "Треугольник", (0, 0, 255, 200)),
        ("star", "Звезда", (255, 255, 0, 200)),
        ("heart", "Сердце", (255, 0, 255, 200)),
        ("hexagon", "Шестиугольник", (0, 255, 255, 200)),
    ]
    
    for i, (shape_type, name, color) in enumerate(shapes):
        size = random.randint(100, 300)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        margin = 20
        
        if shape_type == "circle":
            draw.ellipse([margin, margin, size-margin, size-margin], fill=color)
        elif shape_type == "square":
            draw.rectangle([margin, margin, size-margin, size-margin], fill=color)
        elif shape_type == "triangle":
            points = [(size//2, margin), (margin, size-margin), (size-margin, size-margin)]
            draw.polygon(points, fill=color)
        elif shape_type == "star":
            points = []
            for j in range(5):
                angle = math.pi/2 + j * 2*math.pi/5
                outer_r = (size - 2*margin) // 2
                inner_r = outer_r // 2
                
                points.append((
                    size//2 + int(outer_r * math.cos(angle)),
                    size//2 + int(outer_r * math.sin(angle))
                ))
                
                angle += math.pi/5
                points.append((
                    size//2 + int(inner_r * math.cos(angle)),
                    size//2 + int(inner_r * math.sin(angle))
                ))
            draw.polygon(points, fill=color)
        elif shape_type == "heart":
            draw.ellipse([margin, margin, size//2, size//2], fill=color)
            draw.ellipse([size//2, margin, size-margin, size//2], fill=color)
            points = [
                (margin, size//4),
                (size-margin, size//4),
                (size//2, size-margin)
            ]
            draw.polygon(points, fill=color)
        elif shape_type == "hexagon":
            points = []
            for j in range(6):
                angle = j * 2*math.pi/6
                r = (size - 2*margin) // 2
                points.append((
                    size//2 + int(r * math.cos(angle)),
                    size//2 + int(r * math.sin(angle))
                ))
            draw.polygon(points, fill=color)
        
        draw.text((size//2, size//2), name, fill=(255, 255, 255, 255), anchor="mm")
        img.save(f"{directory}/{shape_type}_{i}.png")
    
    print(f"Созданы тестовые стикеры в папке '{directory}'")
    return directory


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle("Fusion")
    
    # Темная тема
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    
    # Создаем тестовые стикеры если нужно
    test_dir = "test_stickers"
    if not os.path.exists(test_dir) or len(list(Path(test_dir).glob("*.png"))) == 0:
        reply = QMessageBox.question(
            None,
            "Тестовые стикеры",
            "Создать тестовые стикеры?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            create_test_stickers(test_dir)
    
    # Создаем и показываем главное окно
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()