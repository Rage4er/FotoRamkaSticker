"""
Конфигурационные классы для генератора фоторамок
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum


class BorderSide(Enum):
    """Стороны для размещения стикеров"""
    ALL = "Все стороны"
    TOP = "Только верх"
    BOTTOM = "Только низ"
    LEFT = "Только лево"
    RIGHT = "Только право"
    TOP_BOTTOM = "Верх и низ"
    LEFT_RIGHT = "Лево и право"
    CORNERS = "Только углы"


class AlgorithmType(Enum):
    """Типы алгоритмов размещения"""
    BASE = "Базовый (случайный)"
    UNIFORM = "Равномерный"
    GRADIENT = "Градиентный"
    CORNER = "Угловой"


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
    border_overlap: int = 20  # Заход за границу шаблона
    overlap_allowed: bool = True
    random_rotation: bool = True
    random_opacity: bool = False
    min_opacity: float = 0.7
    max_opacity: float = 1.0
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 0)
    output_format: str = "PNG"
    border_sides: BorderSide = BorderSide.ALL
    gradient_density: bool = False  # Градиентная плотность
    gradient_type: str = "linear"  # linear или radial
    preview_auto: bool = True  # Автогенерация предпросмотра
    preview_aspect: bool = True  # Сохранять соотношение сторон в предпросмотре
    algorithm: AlgorithmType = AlgorithmType.BASE  # Выбранный алгоритм