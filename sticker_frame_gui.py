import os
import sys
import random
import math
import json
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass, asdict
from PIL import Image, ImageDraw
import io

# PyQt6 импорты
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QComboBox, QCheckBox, QSplitter, QProgressBar, QTextEdit,
    QTabWidget, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QPalette, QColor


@dataclass
class StickerConfig:
    """Конфигурация для стикера"""
    path: str
    size: Tuple[int, int]
    position: Tuple[int, int]
    rotation: float
    opacity: float = 1.0


@dataclass
class FrameConfig:
    """Конфигурация для фоторамки"""
    template_size: Tuple[int, int] = (1200, 800)
    output_size: Tuple[int, int] = (1920, 1080)
    sticker_dir: str = ""
    sticker_density: float = 0.6
    min_sticker_size: int = 40
    max_sticker_size: int = 150
    border_width: int = 100
    overlap_allowed: bool = True
    random_rotation: bool = True
    random_opacity: bool = False
    min_opacity: float = 0.7
    max_opacity: float = 1.0
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 0)
    output_format: str = "PNG"


def pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
    """Конвертирует PIL.Image в QPixmap для PyQt6"""
    # Конвертируем PIL Image в байты PNG
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    
    # Создаем QPixmap из байтов
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return pixmap


class StickerFrameGenerator:
    """Генератор фоторамок из стикеров"""
    
    def __init__(self, config: FrameConfig):
        self.config = config
        self.stickers: List[StickerConfig] = []
        self.loaded_stickers: List[Image.Image] = []
        self.inner_rect: Optional[Tuple[int, int, int, int]] = None
        self.perimeter_positions: List[Tuple[int, int]] = []
        
        if config.sticker_dir:
            self._load_stickers()
            self._calculate_sticker_zone()
    
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
    
    def _calculate_sticker_zone(self):
        """Рассчитывает зону для размещения стикеров по периметру."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        
        # Внутренняя зона
        inner_w = template_w - 2 * border
        inner_h = template_h - 2 * border
        
        if inner_w <= 0 or inner_h <= 0:
            inner_w = max(10, template_w - 20)
            inner_h = max(10, template_h - 20)
            border = min(template_w - inner_w, template_h - inner_h) // 2
        
        self.inner_rect = (border, border, border + inner_w, border + inner_h)
        self._generate_perimeter_positions()
    
    def _generate_perimeter_positions(self):
        """Генерирует возможные позиции для стикеров по периметру."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        
        positions = []
        step = max(5, border // 10)
        
        # Верхняя и нижняя границы
        for x in range(0, template_w, step):
            positions.append((x, random.randint(0, border // 2)))
            positions.append((x, template_h - random.randint(1, border // 2)))
        
        # Левая и правая границы
        for y in range(border, template_h - border, step):
            positions.append((random.randint(0, border // 2), y))
            positions.append((template_w - random.randint(1, border // 2), y))
        
        self.perimeter_positions = positions
    
    def _is_position_valid(self, sticker: StickerConfig, placed_stickers: List[StickerConfig]) -> bool:
        """Проверяет валидность позиции стикера."""
        if not self.inner_rect:
            return True
            
        x, y = sticker.position
        w, h = sticker.size
        
        # Проверка границ
        if x < 0 or y < 0 or x + w > self.config.template_size[0] or y + h > self.config.template_size[1]:
            return False
        
        # Проверка внутренней зоны
        sticker_rect = (x, y, x + w, y + h)
        if self._rectangles_overlap(sticker_rect, self.inner_rect):
            return False
        
        # Проверка перекрытия
        if not self.config.overlap_allowed:
            for placed in placed_stickers:
                placed_rect = (placed.position[0], placed.position[1],
                              placed.position[0] + placed.size[0],
                              placed.position[1] + placed.size[1])
                if self._rectangles_overlap(sticker_rect, placed_rect):
                    return False
        
        return True
    
    @staticmethod
    def _rectangles_overlap(rect1: Tuple[int, int, int, int], rect2: Tuple[int, int, int, int]) -> bool:
        """Проверяет пересечение двух прямоугольников."""
        return not (rect1[2] <= rect2[0] or rect1[0] >= rect2[2] or
                   rect1[3] <= rect2[1] or rect1[1] >= rect2[3])
    
    def _rotate_sticker(self, sticker_img: Image.Image, angle: float) -> Image.Image:
        """Поворачивает изображение стикера."""
        if angle == 0:
            return sticker_img.copy()
            
        rotated = sticker_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        
        # Сохраняем прозрачность
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
        
        # Создаем изображение с фоном
        template_w, template_h = self.config.template_size
        result = Image.new("RGBA", (template_w, template_h), self.config.background_color)
        
        # Количество стикеров
        if not self.perimeter_positions:
            self._generate_perimeter_positions()
            
        total_positions = len(self.perimeter_positions)
        num_stickers = int(total_positions * self.config.sticker_density)
        num_stickers = max(1, min(num_stickers, total_positions // 2))
        
        placed_stickers = []
        
        for _ in range(num_stickers):
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
            for _ in range(max_attempts):
                pos = random.choice(self.perimeter_positions)
                sticker_config = StickerConfig(
                    path="", size=(width, height),
                    position=pos, rotation=rotation,
                    opacity=opacity
                )
                
                if self._is_position_valid(sticker_config, placed_stickers):
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
    """Виджет для предпросмотра"""
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            PreviewWidget {
                background-color: #f0f0f0;
                border: 2px solid #cccccc;
                border-radius: 5px;
            }
        """)
        self.setText("Предпросмотр появится здесь")
        self.setFont(QFont("Arial", 12))
    
    def update_preview(self, image: Image.Image):
        """Обновляет предпросмотр с новым изображением"""
        if image:
            # Конвертируем PIL Image в QPixmap
            pixmap = pil_to_pixmap(image)
            
            # Масштабируем для отображения
            scaled_pixmap = pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)


class SettingsWidget(QWidget):
    """Виджет настроек"""
    
    settings_changed = pyqtSignal(FrameConfig)
    
    def __init__(self):
        super().__init__()
        self.config = FrameConfig()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Вкладки
        tabs = QTabWidget()
        
        # Основные настройки
        basic_tab = QWidget()
        self.setup_basic_tab(basic_tab)
        tabs.addTab(basic_tab, "Основные")
        
        # Настройки стикеров
        sticker_tab = QWidget()
        self.setup_sticker_tab(sticker_tab)
        tabs.addTab(sticker_tab, "Стикеры")
        
        # Настройки внешнего вида
        appearance_tab = QWidget()
        self.setup_appearance_tab(appearance_tab)
        tabs.addTab(appearance_tab, "Внешний вид")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def setup_basic_tab(self, parent):
        layout = QFormLayout()
        
        # Размер шаблона
        self.template_width = QSpinBox()
        self.template_width.setRange(100, 5000)
        self.template_width.setValue(1200)
        self.template_width.valueChanged.connect(self.update_config)
        layout.addRow("Ширина шаблона:", self.template_width)
        
        self.template_height = QSpinBox()
        self.template_height.setRange(100, 5000)
        self.template_height.setValue(800)
        self.template_height.valueChanged.connect(self.update_config)
        layout.addRow("Высота шаблона:", self.template_height)
        
        # Размер вывода
        self.output_width = QSpinBox()
        self.output_width.setRange(100, 8000)
        self.output_width.setValue(1920)
        self.output_width.valueChanged.connect(self.update_config)
        layout.addRow("Ширина вывода:", self.output_width)
        
        self.output_height = QSpinBox()
        self.output_height.setRange(100, 8000)
        self.output_height.setValue(1080)
        self.output_height.valueChanged.connect(self.update_config)
        layout.addRow("Высота вывода:", self.output_height)
        
        # Соотношение сторон
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["Свободное", "16:9", "4:3", "1:1", "9:16"])
        self.aspect_combo.currentTextChanged.connect(self.apply_aspect_ratio)
        layout.addRow("Соотношение сторон:", self.aspect_combo)
        
        parent.setLayout(layout)
    
    def setup_sticker_tab(self, parent):
        layout = QFormLayout()
        
        # Директория со стикерами
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("Не выбрана")
        dir_layout.addWidget(self.dir_label)
        
        self.dir_button = QPushButton("Выбрать...")
        self.dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_button)
        
        layout.addRow("Директория стикеров:", dir_layout)
        
        # Размеры стикеров
        self.min_size = QSpinBox()
        self.min_size.setRange(10, 1000)
        self.min_size.setValue(40)
        self.min_size.valueChanged.connect(self.update_config)
        layout.addRow("Мин. размер стикера:", self.min_size)
        
        self.max_size = QSpinBox()
        self.max_size.setRange(10, 1000)
        self.max_size.setValue(150)
        self.max_size.valueChanged.connect(self.update_config)
        layout.addRow("Макс. размер стикера:", self.max_size)
        
        # Плотность
        self.density_slider = QSlider(Qt.Orientation.Horizontal)
        self.density_slider.setRange(1, 100)
        self.density_slider.setValue(60)
        self.density_slider.valueChanged.connect(self.update_config)
        
        self.density_label = QLabel("60%")
        density_layout = QHBoxLayout()
        density_layout.addWidget(self.density_slider)
        density_layout.addWidget(self.density_label)
        layout.addRow("Плотность:", density_layout)
        
        # Ширина полосы
        self.border_width = QSpinBox()
        self.border_width.setRange(10, 500)
        self.border_width.setValue(100)
        self.border_width.valueChanged.connect(self.update_config)
        layout.addRow("Ширина полосы:", self.border_width)
        
        parent.setLayout(layout)
    
    def setup_appearance_tab(self, parent):
        layout = QFormLayout()
        
        # Флажки
        self.overlap_check = QCheckBox("Разрешить перекрытие")
        self.overlap_check.setChecked(True)
        self.overlap_check.stateChanged.connect(self.update_config)
        layout.addRow(self.overlap_check)
        
        self.rotation_check = QCheckBox("Случайный поворот")
        self.rotation_check.setChecked(True)
        self.rotation_check.stateChanged.connect(self.update_config)
        layout.addRow(self.rotation_check)
        
        self.opacity_check = QCheckBox("Случайная прозрачность")
        self.opacity_check.setChecked(False)
        self.opacity_check.stateChanged.connect(self.update_config)
        layout.addRow(self.opacity_check)
        
        # Прозрачность
        self.min_opacity = QDoubleSpinBox()
        self.min_opacity.setRange(0.1, 1.0)
        self.min_opacity.setValue(0.7)
        self.min_opacity.setSingleStep(0.1)
        self.min_opacity.valueChanged.connect(self.update_config)
        layout.addRow("Мин. прозрачность:", self.min_opacity)
        
        self.max_opacity = QDoubleSpinBox()
        self.max_opacity.setRange(0.1, 1.0)
        self.max_opacity.setValue(1.0)
        self.max_opacity.setSingleStep(0.1)
        self.max_opacity.valueChanged.connect(self.update_config)
        layout.addRow("Макс. прозрачность:", self.max_opacity)
        
        # Формат вывода
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "WEBP"])
        self.format_combo.currentTextChanged.connect(self.update_config)
        layout.addRow("Формат вывода:", self.format_combo)
        
        parent.setLayout(layout)
    
    def select_directory(self):
        """Выбор директории со стикерами"""
        directory = QFileDialog.getExistingDirectory(
            self, "Выберите директорию со стикерами"
        )
        if directory:
            self.dir_label.setText(directory)
            self.config.sticker_dir = directory
            self.settings_changed.emit(self.config)
    
    def apply_aspect_ratio(self, aspect: str):
        """Применяет соотношение сторон"""
        if aspect == "Свободное":
            return
            
        width = self.template_width.value()
        ratio_map = {
            "16:9": 16/9,
            "4:3": 4/3,
            "1:1": 1,
            "9:16": 9/16
        }
        
        if aspect in ratio_map:
            new_height = int(width / ratio_map[aspect])
            self.template_height.setValue(new_height)
    
    def update_config(self):
        """Обновляет конфигурацию"""
        self.config.template_size = (
            self.template_width.value(),
            self.template_height.value()
        )
        self.config.output_size = (
            self.output_width.value(),
            self.output_height.value()
        )
        self.config.min_sticker_size = self.min_size.value()
        self.config.max_sticker_size = self.max_size.value()
        self.config.sticker_density = self.density_slider.value() / 100.0
        self.config.border_width = self.border_width.value()
        self.config.overlap_allowed = self.overlap_check.isChecked()
        self.config.random_rotation = self.rotation_check.isChecked()
        self.config.random_opacity = self.opacity_check.isChecked()
        self.config.min_opacity = self.min_opacity.value()
        self.config.max_opacity = self.max_opacity.value()
        self.config.output_format = self.format_combo.currentText()
        
        # Обновляем метку плотности
        self.density_label.setText(f"{self.density_slider.value()}%")
        
        # Эмитируем сигнал
        self.settings_changed.emit(self.config)
    
    def get_config(self) -> FrameConfig:
        """Возвращает текущую конфигурацию"""
        return self.config


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.current_image = None
        self.generation_thread = None
        self.init_ui()
        self.setWindowTitle("Генератор фоторамок из стикеров")
        self.setGeometry(100, 100, 1200, 800)
    
    def init_ui(self):
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной макет
        main_layout = QHBoxLayout()
        
        # Разделитель
        splitter = QSplitter()
        
        # Левая панель - настройки
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setMinimumWidth(350)
        
        self.settings_widget = SettingsWidget()
        self.settings_widget.settings_changed.connect(self.on_settings_changed)
        settings_scroll.setWidget(self.settings_widget)
        
        # Правая панель - предпросмотр и управление
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Предпросмотр
        preview_group = QGroupBox("Предпросмотр")
        preview_layout = QVBoxLayout()
        
        self.preview_widget = PreviewWidget()
        preview_layout.addWidget(self.preview_widget)
        
        # Информационная панель под предпросмотром
        info_layout = QHBoxLayout()
        
        self.resolution_label = QLabel("Разрешение: 1200x800")
        self.stickers_label = QLabel("Стикеры: 0")
        self.status_label = QLabel("Готов")
        
        info_layout.addWidget(self.resolution_label)
        info_layout.addWidget(self.stickers_label)
        info_layout.addStretch()
        info_layout.addWidget(self.status_label)
        
        preview_layout.addLayout(info_layout)
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group, 3)
        
        # Панель управления
        control_group = QGroupBox("Управление")
        control_layout = QHBoxLayout()
        
        # Кнопки
        self.generate_btn = QPushButton("Сгенерировать")
        self.generate_btn.clicked.connect(self.generate_frame)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_image)
        self.save_btn.setEnabled(False)
        
        self.random_btn = QPushButton("Случайные настройки")
        self.random_btn.clicked.connect(self.random_settings)
        
        control_layout.addWidget(self.generate_btn)
        control_layout.addWidget(self.save_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.random_btn)
        
        control_group.setLayout(control_layout)
        right_layout.addWidget(control_group, 1)
        
        right_panel.setLayout(right_layout)
        
        # Добавляем в разделитель
        splitter.addWidget(settings_scroll)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 850])
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # Строка состояния
        self.statusBar().showMessage("Готов к работе")
    
    def on_settings_changed(self, config: FrameConfig):
        """Обработчик изменения настроек"""
        self.resolution_label.setText(f"Разрешение: {config.template_size[0]}x{config.template_size[1]}")
        
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
    
    def generate_frame(self):
        """Генерация фоторамки"""
        config = self.settings_widget.get_config()
        
        if not config.sticker_dir or not os.path.exists(config.sticker_dir):
            QMessageBox.warning(self, "Ошибка", "Выберите директорию со стикерами")
            return
        
        # Отключаем кнопку на время генерации
        self.generate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Генерация...")
        
        # Запускаем в отдельном потоке
        self.generation_thread = GenerationThread(config)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)
        self.generation_thread.generation_error.connect(self.on_generation_error)
        self.generation_thread.start()
    
    def on_generation_complete(self, image: Image.Image):
        """Обработчик завершения генерации"""
        self.current_image = image
        self.preview_widget.update_preview(image)
        self.save_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.status_label.setText("Готово")
        self.statusBar().showMessage(f"Фоторамка сгенерирована. Размер: {image.size[0]}x{image.size[1]}")
    
    def on_generation_error(self, error_msg: str):
        """Обработчик ошибки генерации"""
        QMessageBox.critical(self, "Ошибка генерации", error_msg)
        self.generate_btn.setEnabled(True)
        self.status_label.setText("Ошибка")
        self.statusBar().showMessage(f"Ошибка: {error_msg}")
    
    def save_image(self):
        """Сохранение изображения"""
        if not self.current_image:
            return
        
        config = self.settings_widget.get_config()
        
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
            f"sticker_frame.{ext}",
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
    
    def random_settings(self):
        """Случайные настройки"""
        # Случайный размер шаблона
        sizes = [(800, 600), (1200, 800), (1600, 900), (1920, 1080)]
        size = random.choice(sizes)
        self.settings_widget.template_width.setValue(size[0])
        self.settings_widget.template_height.setValue(size[1])
        
        # Случайная плотность
        density = random.randint(30, 90)
        self.settings_widget.density_slider.setValue(density)
        
        # Случайные размеры стикеров
        min_size = random.randint(20, 80)
        max_size = random.randint(100, 250)
        self.settings_widget.min_size.setValue(min_size)
        self.settings_widget.max_size.setValue(max_size)
        
        # Случайная ширина полосы
        border = random.randint(50, 200)
        self.settings_widget.border_width.setValue(border)
        
        # Случайные флажки
        self.settings_widget.overlap_check.setChecked(random.choice([True, False]))
        self.settings_widget.rotation_check.setChecked(random.choice([True, False]))
        self.settings_widget.opacity_check.setChecked(random.choice([True, False]))
        
        self.statusBar().showMessage("Применены случайные настройки")
    
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
                
                # Внешняя точка
                points.append((
                    size//2 + int(outer_r * math.cos(angle)),
                    size//2 + int(outer_r * math.sin(angle))
                ))
                
                # Внутренняя точка
                angle += math.pi/5
                points.append((
                    size//2 + int(inner_r * math.cos(angle)),
                    size//2 + int(inner_r * math.sin(angle))
                ))
            draw.polygon(points, fill=color)
        elif shape_type == "heart":
            # Левая часть сердца
            draw.ellipse([margin, margin, size//2, size//2], fill=color)
            # Правая часть сердца
            draw.ellipse([size//2, margin, size-margin, size//2], fill=color)
            # Нижняя часть
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
        
        # Добавляем текст
        draw.text((size//2, size//2), name, fill=(255, 255, 255, 255), anchor="mm")
        
        img.save(f"{directory}/{shape_type}_{i}.png")
    
    print(f"Созданы тестовые стикеры в папке '{directory}'")
    return directory


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle("Fusion")
    
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