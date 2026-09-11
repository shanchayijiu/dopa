"""Shared runtime facts and helpers for core.py and its mix-ins.

This module exists to break a circular import. core.py imports the twenty
mix-ins at the bottom of its header, and five of those mix-ins previously did
`from core import TENSORRT_AVAILABLE, VERSION, ...` back into core. That worked
only because those names happened to be defined above the mix-in import block;
moving any of them lower would have broken startup.

Nothing here depends on the Valorant class, so both sides can import from this
module instead and the cycle disappears.
"""
import os

import numpy as np
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL_DIR = os.path.join(PROJECT_ROOT, 'dll')
_DLL_DIRECTORY_HANDLES = []

VERSION = 'v2.5'
UPDATE_TIME = '2025-11-04'

BAR_HEIGHT = 2
SHADOW_OFFSET = 2

GRADIENT_PATH = 'assets/skeet_gradient.png'


def register_dll_directory():
    """Put the project-local dll/ folder on the DLL search path.

    Must run before TensorRT detection so bundled nvinfer*.dll is discoverable.
    """
    dll_path = DLL_DIR
    if not os.path.isdir(dll_path):
        return dll_path
    os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        try:
            handle = os.add_dll_directory(dll_path)
            _DLL_DIRECTORY_HANDLES.append(handle)
        except OSError:
            pass
    return dll_path


def check_tensorrt_availability():
    """Detect whether a usable TensorRT runtime is present."""
    try:
        import glob
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        found_nvinfer = False
        for path_dir in path_dirs:
            if not path_dir or not os.path.isdir(path_dir):
                continue
            try:
                if glob.glob(os.path.join(path_dir, 'nvinfer*.dll')):
                    found_nvinfer = True
                    print(f'在 {path_dir} 发现 TensorRT DLL')
                    break
            except (OSError, ValueError):
                continue
        if not found_nvinfer:
            print('TensorRT DLL文件未找到，将使用ONNX推理')
            return False
        try:
            import tensorrt as trt
            try:
                import pycuda.driver as cuda
            except ImportError:
                from inference import cuda_compat as cuda
            cuda.init()
            print(f'TensorRT环境检测成功 (TensorRT {trt.__version__})')
            return True
        except (ImportError, OSError) as e:
            print(f'TensorRT模块导入失败: {e}')
            print('将使用ONNX推理')
            return False
    except Exception as e:
        print(f'TensorRT环境检测失败: {e}')
        print('将使用ONNX推理')
        return False


def create_gradient_image(width, height):
    gradient = np.zeros((height, width, 4), dtype=np.uint8)
    colors = [(55, 177, 218), (204, 91, 184), (204, 227, 53)]
    for x in range(width):
        t = x / width
        r = int(colors[0][0] * (1 - t) + colors[2][0] * t)
        g = int(colors[0][1] * (1 - t) + colors[2][1] * t)
        b = int(colors[0][2] * (1 - t) + colors[2][2] * t)
        gradient[:, x] = (r, g, b, 255)
    img = Image.fromarray(gradient, 'RGBA')
    img.save(GRADIENT_PATH)
    return GRADIENT_PATH


register_dll_directory()

TENSORRT_AVAILABLE = check_tensorrt_availability()

TensorRTInferenceEngine = None
ensure_engine_from_memory = None

if TENSORRT_AVAILABLE:
    try:
        from inference.inference_engine import (
            TensorRTInferenceEngine,
            ensure_engine_from_memory,
        )
        print('TensorRT推理引擎模块加载成功')
    except Exception as e:
        print(f'TensorRT推理引擎模块加载失败: {e}')
        print(f'错误详情: {str(e)}')
        TENSORRT_AVAILABLE = False
        TensorRTInferenceEngine = None
        ensure_engine_from_memory = None
else:
    print('跳过TensorRT模块导入，使用纯ONNX模式')
