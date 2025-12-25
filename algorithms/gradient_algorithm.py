"""
Алгоритм градиентного размещения стикеров
"""

import random
import math
from typing import List, Tuple, Optional, Set
from PIL import Image

from frame_config import StickerConfig, FrameConfig, BorderSide
from .base_algorithm import BaseAlgorithm


class GradientAlgorithm(BaseAlgorithm):
    """Алгоритм градиентного размещения стикеров"""
    
    def generate_positions(self):
        """Генерирует позиции с градиентным распределением."""
        if not self.config.template_size:
            return
            
        template_w, template_h = self.config.template_size
        border = self.config.border_width
        overlap = self.config.border_overlap
        
        positions = []
        sides = self._get_active_sides()
        
        # Больше позиций в центре, меньше по краям
        total_positions = 300
        
        for i in range(total_positions):
            # Выбираем случайную сторону
            if sides:
                side = random.choice(list(sides))
            else:
                continue
            
            # Генерируем позицию в зависимости от стороны
            if side == 'top':
                x = random.randint(-overlap, template_w + overlap)
                # Градиент: больше позиций ближе к центру
                center_factor = abs(x - template_w/2) / (template_w/2)
                y_range = int(border // 2 * (1 - center_factor * 0.5))
                y = random.randint(-overlap, max(1, y_range))
                positions.append((x, y))
            
            elif side == 'bottom':
                x = random.randint(-overlap, template_w + overlap)
                center_factor = abs(x - template_w/2) / (template_w/2)
                y_range = int(border // 2 * (1 - center_factor * 0.5))
                y = template_h - random.randint(1, max(1, y_range + overlap))
                positions.append((x, y))
            
            elif side == 'left':
                y = random.randint(border, template_h - border)
                center_factor = abs(y - template_h/2) / (template_h/2)
                x_range = int(border // 2 * (1 - center_factor * 0.5))
                x = random.randint(-overlap, max(1, x_range))
                positions.append((x, y))
            
            elif side == 'right':
                y = random.randint(border, template_h - border)
                center_factor = abs(y - template_h/2) / (template_h/2)
                x_range = int(border // 2 * (1 - center_factor * 0.5))
                x = template_w - random.randint(1, max(1, x_range + overlap))
                positions.append((x, y))
            
            elif side == 'corners':
                corner_size = border + overlap
                # Градиент в углах
                distance = random.uniform(0, 1)
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
        
        self.perimeter_positions = positions
    
    def get_gradient_density(self, position: Tuple[int, int]) -> float:
        """Рассчитывает коэффициент плотности для градиентного заполнения."""
        if not self.config.gradient_density:
            return 1.0
        
        x, y = position
        template_w, template_h = self.config.template_size
        
        # Сильный градиент от центра
        center_x, center_y = template_w // 2, template_h // 2
        distance_x = abs(x - center_x) / (template_w / 2)
        distance_y = abs(y - center_y) / (template_h / 2)
        
        if self.config.gradient_type == "linear":
            # Линейный градиент
            distance = math.sqrt(distance_x ** 2 + distance_y ** 2)
            return max(0.1, min(1.0, distance))
        else:
            # Радиальный градиент с колебаниями
            base_density = (distance_x + distance_y) / 2
            variation = random.uniform(-0.2, 0.2)
            return max(0.1, min(1.0, base_density + variation))