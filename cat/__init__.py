"""
Cat模块包初始化文件
"""

from .catnet_lite import CatNetLite, ErrorCode, BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, BTN_SIDE, BTN_EXTRA

__all__ = [
    'CatNetLite',
    'ErrorCode', 
    'BTN_LEFT',
    'BTN_RIGHT',
    'BTN_MIDDLE',
    'BTN_SIDE',
    'BTN_EXTRA'
]

__version__ = "1.0.0"
__author__ = "Virtual Module"