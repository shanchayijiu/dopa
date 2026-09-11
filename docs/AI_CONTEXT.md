# AI 开发上下文文档

> 本文档为后续 AI Agent 提供项目理解上下文，确保在修改代码时遵循已有架构和约束。

---

## 1. 项目目标

naoma 是一款基于深度学习的 AI 辅助瞄准系统，目标是：

1. **实时性**：从截图到鼠标移动的端到端延迟尽可能低（目标 < 10ms）
2. **精确性**：通过 PID + 预测算法实现平滑、稳定的瞄准
3. **兼容性**：支持多种推理后端（ONNX/TensorRT）和多种输入设备
4. **可配置性**：所有参数可通过 GUI 实时调节

---

## 2. Pipeline 概要

```
截图 → 预处理 → YOLO推理 → NMS → ByteTrack跟踪 → 目标选择 → 卡尔曼预测 → PID控制 → 量化 → 鼠标移动
```

详细流程见 [PIPELINE.md](PIPELINE.md)。

---

## 3. 关键模块规则

### 3.1 core/ 包

- **中枢**（872 行 / 14 个方法），修改需格外谨慎；Mix-in 架构见 `docs/CORE_REFACTOR_AUDIT.md`
- `Valorant` 是唯一主控类，多继承二十个 mix-in：`class Valorant(VerifyMixin, DeviceMixin, InputListenerMixin, InferenceMixin, PerceptionMixin, TriggerMixin, ConfigMixin, ConfigPersistMixin, CrosshairUIMixin, DisplayMixin, GUIMixin, MouseReMixin, GameConfigMixin, MouseMaskMixin, FlashbangMixin, KeyBindMixin, InferConfigMixin, SystemConfigMixin, AimConfigMixin, PidTrackerMixin)` —— 授权校验/设备/输入监听/推理/感知辅助/触发器/配置/配置持久化/准星UI/显示与DPI/GUI构建/鼠标压枪轨迹/游戏枪械配置/鼠标按键屏蔽/自动背闪/按键绑定/推理配置/系统配置/瞄准配置/PID跟踪器 分居同名 `core_*.py`
- core/valorant.py 保留三类不可拆内容：**配置装配中枢**（`__init__` 290 行 + `_change_callback`）、**运动执行环**（`aim_bot_func`/`execute_move`/`_emit_move_rel`/`_execute_move_async`/`_try_crosshair_pull`/`get_current_aim_center`，受 §8 保护）、**生命周期编排**（`start`/`go`/`on_start_button_click`/`down_func` 及跨切面 `close_screenshot`/`reset_down_status`/`_update_class_checkboxes`）。停止边界论证见 `CORE_REFACTOR_AUDIT.md` §4.22
- 各 mix-in 顶部必须显式 import 自己依赖的模块（不能隐式靠 core 顶层 import）
- `TENSORRT_AVAILABLE` / `TensorRTInferenceEngine` / `ensure_engine_from_memory` / `VERSION` / `create_gradient_image` 一律从 **`core/runtime.py`** 取，**禁止**反向 `from core import ...`；后者曾造成 5 处循环 import，仅靠《名字恰好定义在 mix-in import 之前》维持（安全边距 5 行），已于 2026-08-10 消除。导入方向恒为 `core/valorant.py → core/mixins/*.py → core/runtime.py`
- `Valorant` 类是唯一的主控类，持有所有系统状态
- GUI 使用 DearPyGui，所有控件 ID 作为字符串传递
- 配置变更通过 `ConfigChangeHandler` 统一管理
- 线程模型：主线程(GUI) + infer线程 + trigger线程 + 多个定时器回调
- **不要** 在定时器回调中做阻塞操作

### 3.2 aim/aim_pipeline.py

- 已从 `core/valorant.py` 解耦的瞄准逻辑模块
- **所有公开方法均使用 `RLock` 保证线程安全**
- 修改目标选择逻辑时需同时考虑 `select_target_by_priority()` 和 `_find_locked_target()`
- `step_frame()` 是主入口，`step_aim()` 是次级入口
- 目标 ID 锁定有宽限帧机制（`_lock_grace_max=5`），修改时需确保逻辑一致

### 3.3 aim/pid.py

- `DualAxisPID` 是主要使用的控制器
- 参数变更通过 `core/valorant.py` 的 `refresh_controller_params()` 传递
- 平滑参数是时间常数（毫秒），不是 0-1 的 alpha 值
- `reset()` 必须清理所有内部状态

### 3.4 aim/bytetrack.py

- 标准 ByteTrack 实现，依赖 `scipy.optimize.linear_sum_assignment`
- `STrack._next_id` 是类级别的自增 ID，`reset_id()` 可重置
- `max_center_dist` 参数用于限制中心距离过远的匹配

### 3.5 inference/infer_class.py

- `OnnxRuntimeDmlEngine` 支持延迟初始化
- 模型可能是加密的（`.ZTX`），需通过 `build_onnx()` 解密
- NMS 算法会根据模型输出形状自动选择

### 3.6 devices/screenshot_manager.py

- 内存池模式可显著减少 GC 压力
- BetterCam 是主要截图方式，OBS 是备选
- `get_screenshot()` 返回 numpy array (BGR)

---

## 4. 配置层次约束

```
cfg.json
├── 全局级参数         → self.config['param_name']
├── 组级参数           → self.config['groups'][group_name]['param']  
├── 按键级参数         → self.config['groups'][group_name]['aim_keys'][key_name]['param']
└── 按键-触发器参数    → ...['aim_keys'][key_name]['trigger']['param']
```

**规则**：
- 新增配置项必须在 `build_config()` 中设置默认值
- 嵌套配置使用 `setdefault()` 确保向后兼容
- 配置变更后调用 `self.save_config()` 持久化
- 按键级配置通过 `refresh_pressed_key_config()` 刷新

---

## 5. 线程安全约束

| 资源 | 保护方式 | 说明 |
|------|----------|------|
| `que_aim` | Queue(maxsize=1) | infer → aim_bot |
| `que_trigger` | Queue(maxsize=1) | infer → trigger |
| `aim_pipeline` 内部 | RLock | 所有公开方法 |
| `OnnxRuntimeDmlEngine._session` | threading.Lock | 延迟初始化 |
| 按键状态 | 标志位(非原子) | 依赖事件顺序 |

**注意**：
- `aim_bot_func()` 是 Windows 多媒体定时器回调，运行在独立线程
- 不要在定时器回调中修改 GUI 状态
- Queue maxsize=1 意味着只保留最新帧

---

## 6. 性能敏感区域

| 区域 | 延迟预算 | 关键指标 |
|------|----------|----------|
| 截图 | < 2ms | BetterCam 直接内存映射 |
| 预处理 | < 1ms | Numba 可选加速 |
| 推理 | < 5ms | TensorRT > CUDA > DML > CPU |
| NMS | < 0.5ms | cv2.dnn.NMSBoxes |
| 目标选择 | < 0.1ms | Python 纯计算 |
| PID + 量化 | < 0.05ms | Python 纯计算 |
| 鼠标移动 | < 0.5ms | UDP 网络延迟 |

**优化原则**：
- 推理帧率目标 120-240 FPS
- aim_bot 定时器 1ms 周期，不能有任何阻塞
- 内存池复用避免频繁 numpy 分配
- EMA 平滑比窗口平均更高效

---

## 7. 模型支持矩阵

| 格式 | 后缀 | 支持 | 说明 |
|------|------|------|------|
| ONNX (v8) | .onnx | ✅ | 默认格式 |
| ONNX (v11) | .onnx | ✅ | 自动识别 |
| ONNX (v5) | .onnx | ✅ | 需指定 class_num |
| 加密模型 | .ZTX | ✅ | Fernet 解密 |
| TensorRT | .engine | ✅ | 需 CUDA 环境 |

**NMS 自动选择规则**：
- 输出形状 `[1, 84, N]` → v8 算法
- 指定了 `class_num` → v5 算法
- 否则 → v8 回退

---

## 8. 开发约束

### 绝对禁止

- ❌ 不要让任何 mix-in 反向 `from core import ...`（共享事实一律放 `core/runtime.py`，否则重建循环 import）
- ❌ 不要修改 `settings/buff.py` 的验证逻辑（已禁用但依赖其类导出）
- ❌ 不要在 `aim_bot_func()` 中添加阻塞操作
- ❌ 不要修改 `config.json` 的 `card_key` 字段结构

### 推荐做法

- ✅ 新功能优先在独立模块中实现，通过 `core/valorant.py` 集成
- ✅ 移动或重命名 `core/valorant.py` 需满足两个条件：导入图无环（`core/runtime.py` 已保证），且迁移后通过四项门槛 —— 368 个可达方法、109 个 `from core import *` 名字、MRO 22 层、实启 12 秒无 `error_log.txt`、`pytest tests -q` 全绿。迁移规划见 `docs/PROJECT_STRUCTURE.md`
- ✅ 新配置项在 `build_config()` 和 `_init_config_handlers()` 中注册
- ✅ PID 参数变更通过 `refresh_controller_params()` 生效
- ✅ 瞄准逻辑修改在 `aim/aim_pipeline.py` 中进行
- ✅ 新的推理格式支持在 `inference/infer_function.py` 中添加 NMS 处理
- ✅ 新的输入设备在 `init_mouse()` 中添加分支

### 代码风格

- 中文注释
- `cfg.json` 中的配置键使用 snake_case
- GUI 控件 ID 与配置键对应
- 异常处理：关键路径必须 try-catch 并写入 `error_log.txt`

---

## 9. 已知技术债务

| 问题 | 优先级 | 说明 |
|------|--------|------|
| core/valorant.py 仍较大 | 低 | 872 行 / 14 方法，余下是配置装配中枢（`__init__` 占 31%）、运动执行环、生命周期编排（受 §8 保护，已判定不宜再拆，见 AUDIT §4.22） |
| 裸 except | 中 | 多处 `except Exception` 可能隐藏错误（core/valorant.py 约 139 处） |
| NMS 三种实现 | 低 | inference/infer_function.py 中 nms_v8/nms_v5/nms 三种实现并存 |

### 已清理的历史债务

- ✅ `key2str` 重复定义 — 已统一至 `util/function.py`
- ✅ core/valorant.py 过大 — ~6322 行已按子系统拆为二十个 mix-in，降至 872 行（**~86% 外移**）；详见 `docs/CORE_REFACTOR_AUDIT.md`
- ✅ 循环 import — `core_config`/`core_gui`/`core_infercfg`/`core_inference`/`core_verify` 五处反向 `from core import ...` 已抽入 `core/runtime.py`，导入图环数归零；原状态仅靠 core/valorant.py 内语句顺序维持，改动定义位置即会导致启动失败
- ✅ `Valorant.smooth_small_targets` / `Valorant.screenshot` — AST 调用面核实为零调用死代码（前者已被 `AimPipeline.smooth_small_targets(targets, aim_params)` 取代，后者被 `screenshot_manager` 取代），已迁入 `core/mixins/perception.py` 隔离，未删除以保持 `from core import *` 导出契约
- ✅ mix-in 运行期 NameError — 前序提取遗留的缺失 import（`should_use_v11onnx`、`ctypes`、`queue`、`kmNet`、`TENSORRT_AVAILABLE` 等）已补齐
- ✅ `settings/buff.py` 死代码 — 已从 ~2500 行精简为 76 行存根
- ✅ 反编译痕迹 `# inserted` — 已全部清除
- ✅ 旧版瞄准逻辑冗余 — `aim_bot_func` 双路径已合并为 pipeline 单路径
- ✅ 旧版 `select_target_by_priority()` — 已从 core/valorant.py 移除，统一使用 aim_pipeline

---

## 10. 文件修改影响范围

| 修改文件 | 影响范围 |
|----------|----------|
| `aim/aim_pipeline.py` | 瞄准精度、目标切换、预测 |
| `aim/pid.py` | 鼠标移动平滑度、响应速度 |
| `aim/bytetrack.py` | 目标跟踪稳定性、ID 一致性 |
| `inference/infer_class.py` | 推理性能、模型兼容性 |
| `inference/infer_function.py` | NMS 正确性、检测结果 |
| `devices/screenshot_manager.py` | 截图延迟、内存使用 |
| `core/valorant.py` | **几乎所有功能**：实例状态装配、运动执行环、启停生命周期 |
| `core/mixins/input.py` | pynput 键鼠事件回调 —— 瞄准键/扳机键识别、PID 复位、目标锁复位 |
| `core/mixins/perception.py` | 准星找色跟踪（预处理线程调用）|
| `cfg.json` | 运行时行为（直接生效） |

---

## 11. 测试

现有测试文件：
- `tests/test_nms_v8_layout.py` — NMS v8 格式测试
- `tests/test_v11onnx_pipeline_integration.py` — v11 ONNX Pipeline 集成测试
- `tests/test_v11onnx_support.py` — v11 ONNX 支持模块测试

运行测试：
```bash
python -m pytest tests/ -v
```
