"""
Алгоритм равномерного размещения стикеров
"""

import random
import math
from typing import List, Tuple, Optional, Set
from PIL import Image

from frame_config import StickerConfig, FrameConfig, BorderSide
from .base_algorithm import BaseAlgorithm


class UniformAlgorithm(BaseAlgorithm):
    """Алгоритм равномерного размещения стикеров"""
    
    def generate_positions(self):
        """Генерирует равномерные позиции для стикеров по периметру."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        overlap = self.config.border_overlap
        
        positions = []
        sides = self._get_active_sides()
        
        # Равномерное количество позиций для каждой стороны
        positions_per_side = 50  # Фиксированное количество позиций на сторону
        
        if 'top' in sides:
            for i in range(positions_per_side):
                x = random.randint(-overlap, template_w + overlap)
                y = random.randint(-overlap, border // 2)
                positions.append((x, y))
        
        if 'bottom' in sides:
            for i in range(positions_per_side):
                x = random.randint(-overlap, template_w + overlap)
                y = random.randint(template_h - border // 2 - overlap, template_h + overlap)
                positions.append((x, y))
        
        if 'left' in sides:
            for i in range(positions_per_side):
                x = random.randint(-overlap, border // 2)
                y = random.randint(border, template_h - border)
                positions.append((x, y))
        
        if 'right' in sides:
            for i in range(positions_per_side):
                x = random.randint(template_w - border // 2 - overlap, template_w + overlap)
                y = random.randint(border, template_h - border)
                positions.append((x, y))
        
        if 'corners' in sides:
            # Угловые позиции
            corner_size = border + overlap
            corner_positions = positions_per_side // 4
            
            for i in range(corner_positions):
                # Левый верхний угол
                positions.append((
                    random.randint(-overlap, corner_size),
                    random.randint(-overlap, corner_size)
                ))
                # Правый верхний угол
                positions.append((
                    random.randint(template_w - corner_size - overlap, template_w + overlap),
                    random.randint(-overlap, corner_size)
                ))
                # Левый нижний угол
                positions.append((
                    random.randint(-overlap, corner_size),
                    random.randint(template_h - corner_size - overlap, template_h + overlap)
                ))
                # Правый нижний угол
                positions.append((
                    random.randint(template_w - corner_size - overlap, template_w + overlap),
                    random.randint(template_h - corner_size - overlap, template_h + overlap)
                ))
        
        self.perimeter_positions = positions
    
    def get_gradient_density(self, position: Tuple[int, int]) -> float:
        """Рассчитывает коэффициент плотности для градиентного заполнения."""
        if not self.config.gradient_density:
            return 1.0
        
        x, y = position
        template_w, template_h = self.config.template_size
        
        if self.config.gradient_type == "linear":
            # Линейный градиент от центра к краям
            center_x, center_y = template_w // 2, template_h // 2
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            max_distance = math.sqrt(center_x ** 2 + center_y ** 2)
            return max(0.3, min(1.0, distance / max_distance))
        else:
            # Радиальный градиент
            return random.uniform(0.3, 1.0)