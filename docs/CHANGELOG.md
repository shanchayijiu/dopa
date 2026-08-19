# Changelog

## 1.3.0 - 2026-08-11

### Changed
- 三期分包：25 个业务模块按职责收进 6 个包 —— `aim/`（瞄准，5 个）、
  `inference/`（推理，7 个）、`devices/`（外设采集，5 个）、`settings/`（配置授权，
  4 个）、`webui/`（Web 面板，1 个）、`util/`（工具，4 个）。根目录 `.py` 由 27 降至
  2（`main.py`、`conftest.py`），文件总数由 41 降至 12。
- 共重写 66 处 import 语句，覆盖 `core/` 全包、入口与测试。包内同级引用改为相对导入，
  跨包用绝对导入，使每个包可独立移动。
- `config/` 改名 `presets/`：原目录与拟建包名同处顶层会让 import 解析出意外结果。
  其中 `color_range.json` 零代码引用（仅 README 目录树提及），改名无运行风险。
- `tests/test_v11onnx_support.py`：两处 `mock.patch` 目标由 `v11onnx_support.…`
  改为 `inference.v11onnx_support.…`。模块路径写在字符串里，import 重写器无法识别。
- 活文档（`README.md`、`AI_CONTEXT.md`、`ARCHITECTURE.md`、`MODULES.md`、
  `PIPELINE.md`、`PROJECT_STRUCTURE.md`）共回写 116 处模块路径；README 与
  PROJECT_STRUCTURE 的目录树按包层级重绘。
- 历史记录按当时事实保留：`CHANGELOG` 1.2.0 及以前条目、`CORE_REFACTOR_AUDIT.md`、
  `V11ONNX_TEST_REPORT.md` 均不改写。

### Compatibility
- `from core import *` 绑定的 109 个名字与分包前逐名一致。
- `Valorant` 可达方法 368 个、MRO 22 层不变。
- 6 个新包在 stdlib 与 site-packages 中均无同名，不存在模块遮蔽。
- 门槛复验：31 项测试在项目内与项目外目录调用均通过；`main.py` 实启 12 秒存活且
  未产生 `error_log.txt`。

## 1.2.0 - 2026-08-10

### Changed
- 文件结构整理：22 个扁平 `core*.py` 收拢为 `core/` 包 —— `core/valorant.py`
  （主控类，872 行）、`core/runtime.py`（共享运行时事实）、`core/mixins/` 下 20 个
  mix-in。根目录 `.py` 由 48 降至 27，文件总数由 60 降至 37。
- `INSTALL.md` 与 `PROJECT_STRUCTURE.md` 移入 `docs/`，根目录仅保留 `README.md`。
- `core/mixins/verify.py`：函数内延迟读取 `TENSORRT_AVAILABLE` 的 import 改为
  包内相对引用（`from .. import runtime as core_runtime`），运行时降级语义不变。
- 历史文档中 `core.py` / `core_*.py` 路径按当时事实保留；`CORE_REFACTOR_AUDIT.md`
  开头补充新旧路径映射说明。

### Added
- `conftest.py`：显式将项目根加入 `sys.path`，使 `pytest` 从任意工作目录调用均可通过。
- `core/__init__.py`：`__all__` 由 `valorant.py` 的模块级公开名字动态推导，既复现
  包化前的默认星号导入规则，又排除 `mixins` / `runtime` / `valorant` 三个子模块名。

### Compatibility
- `from core import *` 绑定的 109 个名字与包化前逐名一致。
- `Valorant` 可达方法 368 个、MRO 22 层不变。
- 导入图环数由 5 归零，方向恒为 `core/valorant.py → core/mixins/*.py → core/runtime.py`。
- 验收：31 项测试通过（含项目外目录调用），`main.py` 实启 12 秒存活且未产生 `error_log.txt`。

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
