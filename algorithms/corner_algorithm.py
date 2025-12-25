"""
Алгоритм размещения стикеров преимущественно в углах
"""

import random
import math
from typing import List, Tuple, Optional, Set
from PIL import Image

from frame_config import StickerConfig, FrameConfig, BorderSide
from .base_algorithm import BaseAlgorithm


class CornerAlgorithm(BaseAlgorithm):
    """Алгоритм размещения стикеров преимущественно в углах"""
    
    def generate_positions(self):
        """Генерирует позиции с акцентом на углы."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        overlap = self.config.border_overlap
        
        positions = []
        sides = self._get_active_sides()
        
        # 70% позиций в углах, 30% на сторонах
        total_positions = 200
        corner_positions = int(total_positions * 0.7)
        side_positions = total_positions - corner_positions
        
        # Угловые позиции
        corner_size = border + overlap
        
        for i in range(corner_positions):
            # Сильный акцент на углы
            distance = random.uniform(0, 1) ** 2  # Квадрат для большего скопления у углов
            x_offset = int(corner_size * distance)
            y_offset = int(corner_size * distance)
            
            corner = random.choice(['tl', 'tr', 'bl', 'br'])
            if corner == 'tl':  # top-left
                positions.append((-x_offset, -y_offset))
            elif corner == 'tr':  # top-right
                positions.append((template_w + x_offset, -y_offset))
            elif corner == 'bl':  # bottom-left
                positions.append((-x_offset, template_h + y_offset))
            elif corner == 'br':  # bottom-right
                positions.append((template_w + x_offset, template_h + y_offset))
        
        # Позиции на сторонах (редко)
        for i in range(side_positions):
            if 'top' in sides and random.random() < 0.25:
                x = random.randint(-overlap, template_w + overlap)
                y = random.randint(-overlap, border // 4)  # Ближе к краю
                positions.append((x, y))
            
            if 'bottom' in sides and random.random() < 0.25:
                x = random.randint(-overlap, template_w + overlap)
                y = template_h - random.randint(1, border // 4 + overlap)
                positions.append((x, y))
            
            if 'left' in sides and random.random() < 0.25:
                x = random.randint(-overlap, border // 4)
                y = random.randint(border, template_h - border)
                positions.append((x, y))
            
            if 'right' in sides and random.random() < 0.25:
                x = template_w - random.randint(1, border // 4 + overlap)
                y = random.randint(border, template_h - border)
                positions.append((x, y))
        
        self.perimeter_positions = positions
    
    def get_gradient_density(self, position: Tuple[int, int]) -> float:
        """Рассчитывает коэффициент плотности с акцентом на углы."""
        if not self.config.gradient_density:
            return 1.0
        
        x, y = position
        template_w, template_h = self.config.template_size
        
        # Расстояние до ближайшего угла
        corners = [
            (0, 0),  # top-left
            (template_w, 0),  # top-right
            (0, template_h),  # bottom-left
            (template_w, template_h)  # bottom-right
        ]
        
        min_distance = float('inf')
        for corner_x, corner_y in corners:
            distance = math.sqrt((x - corner_x) ** 2 + (y - corner_y) ** 2)
            min_distance = min(min_distance, distance)
        
        # Максимальное расстояние до угла
        max_corner_distance = math.sqrt((template_w/2) ** 2 + (template_h/2) ** 2)
        
        if self.config.gradient_type == "linear":
            # Больше плотности ближе к углам
            return max(0.2, min(1.0, 1 - (min_distance / max_corner_distance)))
        else:
            # Случайные вариации
            base = 1 - (min_distance / max_corner_distance)
            variation = random.uniform(-0.3, 0.3)
            return max(0.1, min(1.0, base + variation))