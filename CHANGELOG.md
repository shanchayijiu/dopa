# Changelog

## 1.1.0 - 2026-02-28

### Added
- 新增 `v11onnx` 端到端支持：
  - 自动发现 `.onnx` 模型（配置路径、环境变量、默认目录扫描）。
  - 模型校验：文件合法性、版本信息、opset、图结构。
  - 推理链路对齐：`v11onnx` 自动复用现有 `v8` 预处理/后处理流程。
- 新增 ONNX Runtime 运行时配置能力：
  - 线程数：`intra_op_num_threads`、`inter_op_num_threads`
  - 内存池/内存模式：`enable_cpu_mem_arena`、`enable_mem_pattern`
  - 图优化与执行模式：`graph_optimization_level`、`execution_mode`
  - 后端选择：CPU / DML / CUDA / TensorRT（可通过配置与环境变量控制）
- 新增测试与基准工具：
  - `tests/test_v11onnx_support.py`
  - `tests/test_v11onnx_pipeline_integration.py`
  - `v11onnx_benchmark.py`

### Changed
- `core.py`：模型配置流程新增 `model_variant` / `model_runtime` 兼容处理；引擎刷新时接入 `v11onnx` 校验逻辑与 ORT 运行时参数。
- `infer_class.py`：`OnnxRuntimeDmlEngine` 支持注入运行时配置与设备策略。
- `README.md`：新增 `v11onnx` 支持章节与配置示例。

### Compatibility
- 保持现有 `v10onnx`、`.engine`、`.ZTX` 路径兼容。
- 默认行为保持不变；仅当 `model_variant=v11onnx` 或设置环境变量 `DOPA_MODEL_VARIANT=v11onnx` 时启用 v11 分支。
