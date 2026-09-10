import os
import pathlib
import traceback

import numpy as np


root = pathlib.Path(__file__).resolve().parent
dll_dir = root / "dll"
os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
dll_handle = os.add_dll_directory(str(dll_dir))

from inference.inference_engine import TensorRTInferenceEngine


engine_path = root / "models" / "sjz320v8.engine"
print(f"ENGINE_PATH={engine_path}")
print(f"ENGINE_EXISTS={engine_path.is_file()}")

engine = None
try:
    engine = TensorRTInferenceEngine(str(engine_path))
    print(f"ENGINE_TYPE={type(engine).__name__}")
    print(f"INPUT_SHAPE={engine.get_input_shape()}")
    shape = tuple(int(value) for value in engine.get_input_shape())
    sample = np.zeros(shape, dtype=np.float32)
    result = engine.infer(sample)
    print(f"INFER_RESULT_TYPE={type(result).__name__}")
    print(f"INFER_RESULT_COUNT={len(result)}")
    print(f"INFER_RESULT_SHAPES={[getattr(item, 'shape', None) for item in result]}")
    print("ENGINE_SMOKE_OK=True")
except Exception as exc:
    print(f"ENGINE_SMOKE_OK=False")
    print(f"ENGINE_ERROR={type(exc).__name__}: {exc}")
    traceback.print_exc()
    raise
finally:
    if engine is not None:
        try:
            engine.close()
        except Exception as exc:
            print(f"ENGINE_CLOSE_ERROR={type(exc).__name__}: {exc}")
    dll_handle.close()
