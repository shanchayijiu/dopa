import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


V11_VARIANT_ALIASES = {"v11", "v11onnx", "yolo11", "yolov11"}


class ModelValidationError(RuntimeError):
    """Raised when a model fails structural validation."""


@dataclass
class V11ModelMetadata:
    path: str
    model_variant: str = "v11onnx"
    file_size: int = 0
    model_version: Optional[int] = None
    ir_version: Optional[int] = None
    opset: Optional[int] = None
    graph_name: str = ""
    node_count: int = 0
    input_count: int = 0
    output_count: int = 0
    op_types: List[str] = field(default_factory=list)
    input_names: List[str] = field(default_factory=list)
    output_names: List[str] = field(default_factory=list)
    output_shapes: List[List[Optional[int]]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize_variant(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def _is_v11_variant(value: Optional[str]) -> bool:
    return _normalize_variant(value) in V11_VARIANT_ALIASES


def infer_model_variant_from_path(path: Optional[str], fallback_is_v8: bool = False) -> str:
    if not path:
        return "v8onnx" if fallback_is_v8 else "onnx"
    lower_name = os.path.basename(str(path)).lower()
    if re.search(r"(?:yolov11|yolo11|v11onnx|(?:^|[_\-.])v11[a-z0-9]*)", lower_name):
        return "v11onnx"
    ext = Path(str(path)).suffix.lower()
    if ext == ".onnx":
        return "v8onnx" if fallback_is_v8 else "onnx"
    if ext in {".ztx", ".model", ".data"}:
        return "encrypted"
    if ext == ".engine":
        return "tensorrt_engine"
    return "unknown"


def should_use_v11onnx(group_config: Dict[str, Any], env: Optional[Dict[str, str]] = None) -> bool:
    env = env or os.environ
    env_variant = _normalize_variant(env.get("DOPA_MODEL_VARIANT"))
    if env_variant:
        return _is_v11_variant(env_variant)
    return _is_v11_variant(group_config.get("model_variant"))


def _split_search_dirs(raw: str) -> List[str]:
    values = []
    for token in re.split(r"[;,]", raw or ""):
        token = token.strip()
        if token:
            values.append(token)
    return values


def _iter_scan_candidates(search_dirs: Iterable[str], max_depth: int = 2) -> Iterable[str]:
    for base_dir in search_dirs:
        if not base_dir:
            continue
        base_dir = os.path.abspath(base_dir)
        if not os.path.isdir(base_dir):
            continue
        base_depth = Path(base_dir).parts
        for root, dirs, files in os.walk(base_dir):
            current_depth = len(Path(root).parts) - len(base_depth)
            if current_depth >= max_depth:
                dirs[:] = []
            for filename in files:
                if filename.lower().endswith(".onnx"):
                    yield os.path.join(root, filename)


def discover_v11onnx_model(
    configured_path: Optional[str],
    search_dirs: Optional[Sequence[str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    env = env or os.environ
    explicit_candidates: List[str] = []

    for env_key in ("DOPA_V11ONNX_MODEL", "DOPA_MODEL_PATH"):
        env_path = env.get(env_key)
        if env_path:
            explicit_candidates.append(env_path.strip())
    if configured_path:
        explicit_candidates.append(str(configured_path).strip())

    for candidate in explicit_candidates:
        if candidate and os.path.isfile(candidate) and candidate.lower().endswith(".onnx"):
            return os.path.abspath(candidate)

    if search_dirs is None:
        env_dirs = _split_search_dirs(env.get("DOPA_V11ONNX_SEARCH_DIRS", ""))
        cwd = os.getcwd()
        search_dirs = [
            cwd,
            os.path.join(cwd, "models"),
            os.path.join(cwd, "weights"),
            *env_dirs,
        ]

    scored_candidates: List[Tuple[int, str]] = []
    name_pattern = re.compile(
        r"(?:yolov11|yolo11|v11onnx|(?:^|[_\-.])v11[a-z0-9]*)",
        re.IGNORECASE,
    )
    for model_path in _iter_scan_candidates(search_dirs):
        score = 2 if name_pattern.search(os.path.basename(model_path)) else 1
        scored_candidates.append((score, os.path.abspath(model_path)))

    if not scored_candidates:
        return None

    scored_candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return scored_candidates[0][1]


def _safe_dim_value(dim: Any) -> Optional[int]:
    try:
        if hasattr(dim, "dim_value") and dim.dim_value > 0:
            return int(dim.dim_value)
    except Exception:
        pass
    return None


def _collect_onnx_metadata(model_path: str) -> Dict[str, Any]:
    import onnx

    model = onnx.load(model_path, load_external_data=False)
    onnx.checker.check_model(model)
    graph = model.graph
    opset = None
    for opset_import in model.opset_import:
        if opset_import.domain in ("", "ai.onnx"):
            opset = int(opset_import.version)
            break

    output_shapes: List[List[Optional[int]]] = []
    for output in graph.output:
        shape: List[Optional[int]] = []
        tensor_type = output.type.tensor_type if output.type else None
        dims = tensor_type.shape.dim if tensor_type and tensor_type.shape else []
        for dim in dims:
            shape.append(_safe_dim_value(dim))
        output_shapes.append(shape)

    return {
        "model_version": int(getattr(model, "model_version", 0) or 0),
        "ir_version": int(getattr(model, "ir_version", 0) or 0),
        "opset": opset,
        "graph_name": str(getattr(graph, "name", "") or ""),
        "node_count": len(graph.node),
        "input_count": len(graph.input),
        "output_count": len(graph.output),
        "op_types": sorted({node.op_type for node in graph.node if node.op_type}),
        "input_names": [item.name for item in graph.input],
        "output_names": [item.name for item in graph.output],
        "output_shapes": output_shapes,
    }


def _collect_runtime_metadata(model_path: str) -> Dict[str, Any]:
    import onnxruntime as ort

    available = ort.get_available_providers()
    providers = ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else available
    if not providers:
        raise ModelValidationError("未检测到可用 ONNX Runtime provider，无法校验模型。")
    session = ort.InferenceSession(model_path, providers=providers)
    outputs = session.get_outputs()
    inputs = session.get_inputs()
    output_shapes: List[List[Optional[int]]] = []
    for output in outputs:
        shape: List[Optional[int]] = []
        for dim in output.shape:
            shape.append(int(dim) if isinstance(dim, int) else None)
        output_shapes.append(shape)
    return {
        "model_version": None,
        "ir_version": None,
        "opset": None,
        "graph_name": "",
        "node_count": 0,
        "input_count": len(inputs),
        "output_count": len(outputs),
        "op_types": [],
        "input_names": [item.name for item in inputs],
        "output_names": [item.name for item in outputs],
        "output_shapes": output_shapes,
    }


def validate_v11onnx_model(
    model_path: str,
    expected_opset: Optional[int] = None,
    expected_model_version: Optional[int] = None,
    strict_graph: bool = True,
) -> V11ModelMetadata:
    if not model_path:
        raise ModelValidationError("模型路径为空。")
    model_path = os.path.abspath(model_path)
    if not os.path.isfile(model_path):
        raise ModelValidationError(f"模型文件不存在: {model_path}")
    if not model_path.lower().endswith(".onnx"):
        raise ModelValidationError(f"v11onnx 仅支持 .onnx 文件: {model_path}")

    file_size = os.path.getsize(model_path)
    if file_size <= 0:
        raise ModelValidationError(f"模型文件为空: {model_path}")

    metadata_payload: Dict[str, Any]
    try:
        metadata_payload = _collect_onnx_metadata(model_path)
    except ImportError:
        metadata_payload = _collect_runtime_metadata(model_path)
    except Exception as exc:
        raise ModelValidationError(f"ONNX 模型校验失败: {exc}") from exc

    metadata = V11ModelMetadata(path=model_path, file_size=file_size, **metadata_payload)

    if expected_model_version is not None and metadata.model_version is not None:
        if int(metadata.model_version) != int(expected_model_version):
            raise ModelValidationError(
                f"模型版本不匹配: expected={expected_model_version}, actual={metadata.model_version}"
            )

    if expected_opset is not None:
        if metadata.opset is None:
            raise ModelValidationError("无法获取 opset（缺少 onnx 依赖），无法执行 opset 严格校验。")
        if int(metadata.opset) != int(expected_opset):
            raise ModelValidationError(f"opset 不匹配: expected={expected_opset}, actual={metadata.opset}")

    if strict_graph:
        if metadata.input_count < 1 or metadata.output_count < 1:
            raise ModelValidationError("图结构非法: 输入或输出为空。")
        if metadata.node_count == 0 and metadata.op_types:
            raise ModelValidationError("图结构非法: 节点统计异常。")
        if metadata.output_shapes:
            valid_rank = any(2 <= len(shape) <= 4 for shape in metadata.output_shapes)
            if not valid_rank:
                raise ModelValidationError(
                    f"图结构非法: 输出维度异常，shapes={metadata.output_shapes}"
                )

    return metadata


def _env_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: Optional[str], default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except Exception:
        return default


def get_default_runtime_config() -> Dict[str, Any]:
    return {
        "v11_auto_discover": True,
        "v11_expected_opset": None,
        "v11_expected_model_version": None,
        "v11_strict_graph": True,
        "v11_search_dirs": [],
        "intra_op_num_threads": 0,
        "inter_op_num_threads": 0,
        "enable_cpu_mem_arena": True,
        "enable_mem_pattern": True,
        "execution_mode": "sequential",
        "graph_optimization_level": "all",
        "cuda_mem_limit_mb": 0,
        "arena_extend_strategy": "kNextPowerOfTwo",
        "selected_device_override": "",
    }


def resolve_runtime_config(
    config: Optional[Dict[str, Any]],
    group_config: Optional[Dict[str, Any]],
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    env = env or os.environ
    merged = get_default_runtime_config()
    global_cfg = (config or {}).get("model_runtime", {})
    group_cfg = (group_config or {}).get("model_runtime", {})
    if isinstance(global_cfg, dict):
        merged.update(global_cfg)
    if isinstance(group_cfg, dict):
        merged.update(group_cfg)

    env_variant = _normalize_variant(env.get("DOPA_MODEL_VARIANT"))
    if env_variant and _is_v11_variant(env_variant):
        merged["v11_auto_discover"] = True

    env_search_dirs = _split_search_dirs(env.get("DOPA_V11ONNX_SEARCH_DIRS", ""))
    if env_search_dirs:
        merged["v11_search_dirs"] = env_search_dirs

    merged["v11_auto_discover"] = _env_bool(
        env.get("DOPA_V11ONNX_AUTO_DISCOVER"), bool(merged.get("v11_auto_discover", True))
    )
    merged["v11_expected_opset"] = _env_int(
        env.get("DOPA_V11ONNX_EXPECTED_OPSET"),
        merged.get("v11_expected_opset") if isinstance(merged.get("v11_expected_opset"), int) else -1,
    )
    if merged["v11_expected_opset"] < 0:
        merged["v11_expected_opset"] = None

    merged["intra_op_num_threads"] = _env_int(
        env.get("DOPA_ORT_INTRA_OP_THREADS"), int(merged.get("intra_op_num_threads", 0) or 0)
    )
    merged["inter_op_num_threads"] = _env_int(
        env.get("DOPA_ORT_INTER_OP_THREADS"), int(merged.get("inter_op_num_threads", 0) or 0)
    )
    merged["enable_cpu_mem_arena"] = _env_bool(
        env.get("DOPA_ORT_ENABLE_CPU_MEM_ARENA"), bool(merged.get("enable_cpu_mem_arena", True))
    )
    merged["enable_mem_pattern"] = _env_bool(
        env.get("DOPA_ORT_ENABLE_MEM_PATTERN"), bool(merged.get("enable_mem_pattern", True))
    )
    merged["cuda_mem_limit_mb"] = _env_int(
        env.get("DOPA_ORT_CUDA_MEM_LIMIT_MB"), int(merged.get("cuda_mem_limit_mb", 0) or 0)
    )
    merged["execution_mode"] = str(
        env.get("DOPA_ORT_EXECUTION_MODE", merged.get("execution_mode", "sequential"))
    ).strip().lower()
    merged["graph_optimization_level"] = str(
        env.get("DOPA_ORT_GRAPH_OPT_LEVEL", merged.get("graph_optimization_level", "all"))
    ).strip().lower()
    merged["selected_device_override"] = str(
        env.get("DOPA_INFERENCE_DEVICE", merged.get("selected_device_override", ""))
    ).strip()
    return merged


def _resolve_selected_device(selected_device: str, runtime_cfg: Dict[str, Any]) -> str:
    override = str(runtime_cfg.get("selected_device_override", "") or "").strip()
    if override:
        return override
    return selected_device


def build_session_options(rt_module: Any, runtime_cfg: Dict[str, Any]) -> Any:
    options = rt_module.SessionOptions()
    intra_threads = int(runtime_cfg.get("intra_op_num_threads", 0) or 0)
    inter_threads = int(runtime_cfg.get("inter_op_num_threads", 0) or 0)
    if intra_threads > 0:
        options.intra_op_num_threads = intra_threads
    if inter_threads > 0:
        options.inter_op_num_threads = inter_threads
    if hasattr(options, "enable_cpu_mem_arena"):
        options.enable_cpu_mem_arena = bool(runtime_cfg.get("enable_cpu_mem_arena", True))
    if hasattr(options, "enable_mem_pattern"):
        options.enable_mem_pattern = bool(runtime_cfg.get("enable_mem_pattern", True))

    graph_level = str(runtime_cfg.get("graph_optimization_level", "all")).strip().lower()
    graph_map = {
        "disable": rt_module.GraphOptimizationLevel.ORT_DISABLE_ALL,
        "basic": rt_module.GraphOptimizationLevel.ORT_ENABLE_BASIC,
        "extended": rt_module.GraphOptimizationLevel.ORT_ENABLE_EXTENDED,
        "all": rt_module.GraphOptimizationLevel.ORT_ENABLE_ALL,
    }
    if hasattr(options, "graph_optimization_level"):
        options.graph_optimization_level = graph_map.get(
            graph_level, rt_module.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

    exec_mode = str(runtime_cfg.get("execution_mode", "sequential")).strip().lower()
    if hasattr(options, "execution_mode"):
        if exec_mode == "parallel":
            options.execution_mode = rt_module.ExecutionMode.ORT_PARALLEL
        else:
            options.execution_mode = rt_module.ExecutionMode.ORT_SEQUENTIAL
    return options


def build_ort_runtime_components(
    rt_module: Any,
    selected_device: str,
    runtime_cfg: Dict[str, Any],
    is_trt: bool = False,
) -> Tuple[List[str], Optional[List[Dict[str, str]]], Any]:
    available = rt_module.get_available_providers()
    selected = _resolve_selected_device(selected_device, runtime_cfg).upper()
    if is_trt:
        priority = [
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "DmlExecutionProvider",
            "CPUExecutionProvider",
        ]
    else:
        provider_map = {
            "TENSORRT": [
                "TensorrtExecutionProvider",
                "CUDAExecutionProvider",
                "DmlExecutionProvider",
                "CPUExecutionProvider",
            ],
            "CUDA": ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"],
            "DML": ["DmlExecutionProvider", "CPUExecutionProvider"],
            "CPU": ["CPUExecutionProvider"],
        }
        priority = provider_map.get(selected, provider_map["CPU"])

    providers = [provider for provider in priority if provider in available]
    if not providers:
        providers = list(available)

    provider_options: List[Dict[str, str]] = []
    cuda_mem_limit_mb = int(runtime_cfg.get("cuda_mem_limit_mb", 0) or 0)
    arena_extend_strategy = str(runtime_cfg.get("arena_extend_strategy", "") or "").strip()
    for provider in providers:
        options: Dict[str, str] = {}
        if provider in {"CUDAExecutionProvider", "TensorrtExecutionProvider"} and cuda_mem_limit_mb > 0:
            options["gpu_mem_limit"] = str(cuda_mem_limit_mb * 1024 * 1024)
        if arena_extend_strategy:
            options["arena_extend_strategy"] = arena_extend_strategy
        provider_options.append(options)

    if not any(provider_options):
        provider_options_value: Optional[List[Dict[str, str]]] = None
    else:
        provider_options_value = provider_options

    session_options = build_session_options(rt_module, runtime_cfg)
    return providers, provider_options_value, session_options
