import os
import tempfile
import unittest
from unittest import mock

from v11onnx_support import (
    ModelValidationError,
    build_ort_runtime_components,
    discover_v11onnx_model,
    infer_model_variant_from_path,
    resolve_runtime_config,
    validate_v11onnx_model,
)


class _FakeGraphOpt:
    ORT_DISABLE_ALL = 0
    ORT_ENABLE_BASIC = 1
    ORT_ENABLE_EXTENDED = 2
    ORT_ENABLE_ALL = 99



class _FakeExecMode:
    ORT_SEQUENTIAL = 0
    ORT_PARALLEL = 1


class 0100
    
    
    
    
    
    00
    




akeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.enable_cpu_mem_arena = True
        self.enable_mem_pattern = True
        self.graph_optimization_level = _FakeGraphOpt.ORT_ENABLE_ALL
        self.execution_mode = _FakeExecMode.ORT_SEQUENTIAL


class _FakeRtModule:
    GraphOptimizationLevel = _FakeGraphOpt
    ExecutionMode = _FakeExecMode
    SessionOptions = _FakeSessionOptions

    @staticmethod
    def get_available_providers():
        return [
            "CUDAExecutionProvider",
            "DmlExecutionProvider",
            "CPUExecutionProvider",
        ]


class V11OnnxSupportTests(unittest.TestCase):
    def test_infer_model_variant_from_path(self):
        self.assertEqual(infer_model_variant_from_path("models/yolov11n.onnx"), "v11onnx")
        self.assertEqual(infer_model_variant_from_path("models/custom.onnx", fallback_is_v8=True), "v8onnx")
        self.assertEqual(infer_model_variant_from_path("weights/model.engine"), "tensorrt_engine")

    def test_discover_v11onnx_model_prefers_explicit_env_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            explicit_path = os.path.join(temp_dir, "my_v11.onnx")
            with open(explicit_path, "wb") as f:
                f.write(b"dummy")
            discovered = discover_v11onnx_model(
                configured_path=None,
                search_dirs=[temp_dir],
                env={"DOPA_V11ONNX_MODEL": explicit_path},
            )
            self.assertEqual(os.path.abspath(explicit_path), discovered)

    def test_discover_v11onnx_model_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path_a = os.path.join(temp_dir, "a.onnx")
            path_b = os.path.join(temp_dir, "best_v11.onnx")
            with open(path_a, "wb") as f:
                f.write(b"a")
            with open(path_b, "wb") as f:
                f.write(b"b")
            discovered = discover_v11onnx_model(
                configured_path=None,
                search_dirs=[temp_dir],
                env={},
            )
            self.assertEqual(os.path.abspath(path_b), discovered)

    def test_validate_v11onnx_model_missing_file(self):
        with self.assertRaises(ModelValidationError):
            validate_v11onnx_model("not_exists.onnx")

    def test_validate_v11onnx_model_extension_error(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            bad_path = f.name
            f.write(b"bad")
        try:
            with self.assertRaises(ModelValidationError):
                validate_v11onnx_model(bad_path)
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)

    def test_validate_v11onnx_model_opset_mismatch(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            model_path = f.name
            f.write(b"dummy")
        fake_metadata = {
            "model_version": 1,
            "ir_version": 8,
            "opset": 12,
            "graph_name": "g",
            "node_count": 3,
            "input_count": 1,
            "output_count": 1,
            "op_types": ["Conv"],
            "input_names": ["images"],
            "output_names": ["output0"],
            "output_shapes": [[1, 84, 8400]],
        }
        try:
            with mock.patch("v11onnx_support._collect_onnx_metadata", return_value=fake_metadata):
                with self.assertRaises(ModelValidationError):
                    validate_v11onnx_model(model_path, expected_opset=11)
        finally:
            if os.path.exists(model_path):
                os.remove(model_path)

    def test_validate_v11onnx_model_version_mismatch(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            model_path = f.name
            f.write(b"dummy")
        fake_metadata = {
            "model_version": 3,
            "ir_version": 8,
            "opset": 11,
            "graph_name": "g",
            "node_count": 3,
            "input_count": 1,
            "output_count": 1,
            "op_types": ["Conv"],
            "input_names": ["images"],
            "output_names": ["output0"],
            "output_shapes": [[1, 84, 8400]],
        }
        try:
            with mock.patch("v11onnx_support._collect_onnx_metadata", return_value=fake_metadata):
                with self.assertRaises(ModelValidationError):
                    validate_v11onnx_model(model_path, expected_model_version=2)
        finally:
            if os.path.exists(model_path):
                os.remove(model_path)

    def test_resolve_runtime_config_env_override(self):
        env = {
            "DOPA_ORT_INTRA_OP_THREADS": "4",
            "DOPA_ORT_INTER_OP_THREADS": "2",
            "DOPA_ORT_ENABLE_CPU_MEM_ARENA": "false",
            "DOPA_ORT_EXECUTION_MODE": "parallel",
            "DOPA_ORT_GRAPH_OPT_LEVEL": "extended",
            "DOPA_INFERENCE_DEVICE": "CUDA",
        }
        cfg = resolve_runtime_config({"model_runtime": {}}, {"model_runtime": {}}, env=env)
        self.assertEqual(cfg["intra_op_num_threads"], 4)
        self.assertEqual(cfg["inter_op_num_threads"], 2)
        self.assertFalse(cfg["enable_cpu_mem_arena"])
        self.assertEqual(cfg["execution_mode"], "parallel")
        self.assertEqual(cfg["graph_optimization_level"], "extended")
        self.assertEqual(cfg["selected_device_override"], "CUDA")

    def test_build_ort_runtime_components(self):
        runtime_cfg = {
            "execution_mode": "parallel",
            "graph_optimization_level": "basic",
            "intra_op_num_threads": 2,
            "inter_op_num_threads": 1,
            "enable_cpu_mem_arena": True,
            "enable_mem_pattern": True,
            "cuda_mem_limit_mb": 256,
            "arena_extend_strategy": "kSameAsRequested",
            "selected_device_override": "",
        }
        providers, provider_options, session_options = build_ort_runtime_components(
            rt_module=_FakeRtModule,
            selected_device="CUDA",
            runtime_cfg=runtime_cfg,
            is_trt=False,
        )
        self.assertEqual(providers[0], "CUDAExecutionProvider")
        self.assertIsNotNone(provider_options)
        self.assertEqual(session_options.execution_mode, _FakeExecMode.ORT_PARALLEL)
        self.assertEqual(session_options.graph_optimization_level, _FakeGraphOpt.ORT_ENABLE_BASIC)


if __name__ == "__main__":
    unittest.main()
