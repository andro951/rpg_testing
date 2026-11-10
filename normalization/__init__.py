"""Reusable AI-output normalization, separate from generation and scoring."""
from .outer_arrays import ArrayNormalization, normalize_outer_array
__all__ = ['ArrayNormalization', 'normalize_outer_array']
