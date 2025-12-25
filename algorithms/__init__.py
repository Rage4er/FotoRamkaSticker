"""
Модуль с алгоритмами размещения стикеров
"""

from .base_algorithm import BaseAlgorithm
from .uniform_algorithm import UniformAlgorithm
from .gradient_algorithm import GradientAlgorithm
from .corner_algorithm import CornerAlgorithm

__all__ = ['BaseAlgorithm', 'UniformAlgorithm', 'GradientAlgorithm', 'CornerAlgorithm']