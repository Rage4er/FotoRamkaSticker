"""
Базовый алгоритм размещения стикеров - случайное распределение
"""

import random
import math
from typing import List, Tuple, Optional, Set
from PIL import Image

from frame_config import StickerConfig, FrameConfig, BorderSide


class BaseAlgorithm:
    """Базовый алгоритм случайного размещения стикеров"""
    
    def __init__(self, config: FrameConfig):
        self.config = config
        self.inner_rect: Optional[Tuple[int, int, int, int]] = None
        self.perimeter_positions: List[Tuple[int, int]] = []
        
    def calculate_sticker_zone(self):
        """Рассчитывает зону для размещения стикеров по периметру."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        overlap = self.config.border_overlap
        
        # Внутренняя зона
        inner_w = template_w - 2 * border
        inner_h = template_h - 2 * border
        
        if inner_w <= 0 or inner_h <= 0:
            inner_w = max(10, template_w - 20)
            inner_h = max(10, template_h - 20)
            border = min(template_w - inner_w, template_h - inner_h) // 2
        
        self.inner_rect = (border, border, border + inner_w, border + inner_h)
        self.generate_positions()
    
    def generate_positions(self):
        """Генерирует возможные позиции для стикеров по периметру."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        overlap = self.config.border_overlap
        
        positions = []
        step = max(5, border // 10)
        
        # Определяем, какие стороны активны
        sides = self._get_active_sides()
        
        # Базовый алгоритм - простой перебор с шагом
        if 'top' in sides:
            for x in range(-overlap, template_w + overlap, step):
                positions.append((x, random.randint(-overlap, border // 2)))
        
        if 'bottom' in sides:
            for x in range(-overlap, template_w + overlap, step):
                positions.append((x, template_h - random.randint(1, border // 2 + overlap)))
        
        if 'left' in sides:
            for y in range(border, template_h - border, step):
                positions.append((random.randint(-overlap, border // 2), y))
        
        if 'right' in sides:
            for y in range(border, template_h - border, step):
                positions.append((template_w - random.randint(1, border // 2 + overlap), y))
        
        if 'corners' in sides:
            # Угловые позиции
            corner_size = border + overlap
            for x in range(-overlap, corner_size, step):
                for y in range(-overlap, corner_size, step):
                    positions.append((x, y))  # Левый верхний угол
                    positions.append((template_w - x - 1, y))  # Правый верхний
                    positions.append((x, template_h - y - 1))  # Левый нижний
                    positions.append((template_w - x - 1, template_h - y - 1))  # Правый нижний
        
        self.perimeter_positions = positions
    
    def _get_active_sides(self) -> Set[str]:
        """Возвращает набор активных сторон для размещения стикеров."""
        sides = set()
        
        if self.config.border_sides == BorderSide.ALL:
            sides.update(['top', 'bottom', 'left', 'right'])
        elif self.config.border_sides == BorderSide.TOP:
            sides.add('top')
        elif self.config.border_sides == BorderSide.BOTTOM:
            sides.add('bottom')
        elif self.config.border_sides == BorderSide.LEFT:
            sides.add('left')
        elif self.config.border_sides == BorderSide.RIGHT:
            sides.add('right')
        elif self.config.border_sides == BorderSide.TOP_BOTTOM:
            sides.update(['top', 'bottom'])
        elif self.config.border_sides == BorderSide.LEFT_RIGHT:
            sides.update(['left', 'right'])
        elif self.config.border_sides == BorderSide.CORNERS:
            sides.add('corners')
        
        return sides
    
    def is_position_valid(self, sticker: StickerConfig, placed_stickers: List[StickerConfig]) -> bool:
        """Проверяет валидность позиции стикера."""
        if not self.inner_rect:
            return True
            
        x, y = sticker.position
        w, h = sticker.size
        
        # Разрешаем выход за границы с учетом overlap
        overlap = self.config.border_overlap
        if x + w < -overlap or x > self.config.template_size[0] + overlap:
            return False
        if y + h < -overlap or y > self.config.template_size[1] + overlap:
            return False
        
        # Проверка внутренней зоны (только если стикер полностью внутри)
        sticker_rect = (x, y, x + w, y + h)
        if self._rectangles_overlap(sticker_rect, self.inner_rect):
            if (x >= self.inner_rect[0] and x + w <= self.inner_rect[2] and
                y >= self.inner_rect[1] and y + h <= self.inner_rect[3]):
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