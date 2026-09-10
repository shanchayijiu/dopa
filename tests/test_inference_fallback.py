from core.mixins.inference import _find_onnx_fallback


def test_engine_without_onnx_has_no_runtime_fallback(tmp_path):
    engine = tmp_path / "model.engine"
    engine.write_bytes(b"tensorrt")

    assert _find_onnx_fallback({}, str(engine)) is None


def test_engine_uses_existing_original_onnx(tmp_path):
    engine = tmp_path / "model.engine"
    original = tmp_path / "original.onnx"
    engine.write_bytes(b"tensorrt")
    original.write_bytes(b"onnx")

    group_cfg = {"original_infer_model": str(original)}
    assert _find_onnx_fallback(group_cfg, str(engine)) == str(original)
