"""
Scale Utilities for ML Pipeline
Provides scale-related helper functions for accuracy calculations.
"""

from typing import Tuple


# Scale configuration - max values for each scale type
SCALE_CONFIG = {
    '0-10': {'min': 0.0, 'max': 10.0},
    '0-100': {'min': 0.0, 'max': 100.0},
    '0-10000': {'min': 0.0, 'max': 10000.0},
    'GPA': {'min': 0.0, 'max': 4.0},
    'A-F': {'min': 0.0, 'max': 10.0},  # Internal representation
}


def get_scale_range(scale_type: str) -> Tuple[float, float]:
    """
    Get the valid (min, max) range for a scale type.
    
    Args:
        scale_type: Scale type string
        
    Returns:
        Tuple of (min_value, max_value)
    """
    config = SCALE_CONFIG.get(scale_type, SCALE_CONFIG['0-10'])
    return (config['min'], config['max'])


def get_scale_max(scale_type: str) -> float:
    """
    Get the maximum value for a scale type.
    Used for accuracy calculations.
    
    Args:
        scale_type: Scale type string
        
    Returns:
        Maximum value for this scale
    """
    _, max_val = get_scale_range(scale_type)
    return max_val
