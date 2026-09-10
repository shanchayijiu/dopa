import os
from pathlib import Path


def test_runtime_registers_project_dll_directory():
    import core.runtime as runtime

    expected = Path(__file__).resolve().parents[1] / "dll"

    assert Path(runtime.DLL_DIR).resolve() == expected.resolve()
    assert Path(runtime.register_dll_directory()).resolve() == expected.resolve()
    assert os.environ["PATH"].split(os.pathsep)[0] == str(expected)


def test_inference_engine_uses_project_trtexec():
    from inference import inference_engine

    expected = Path(__file__).resolve().parents[1] / "dll" / "trtexec.exe"

    assert Path(inference_engine.DLL_DIR).resolve() == expected.parent.resolve()
    assert Path(inference_engine._find_trtexec()).resolve() == expected.resolve()
