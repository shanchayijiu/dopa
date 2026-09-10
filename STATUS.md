# DOPA3 — 接入与运行卡点阶段文档（截至 2026-08-21）

> 主会话诚实记录：已完成本地离线启动、旧模型绝对路径迁移和“缺少推理后端时 GUI 不崩溃”的保护；真实推理、OBS UDP 真帧、km_net 真移动尚未完成端到端验收。
> **2026-08-21 更新**：45 项测试通过；“单机测试模式”已完成真实 `Valorant.go()` 与窗口验收：BetterCam + 本机 `send_input` 初始化成功，Windows 窗口枚举确认存在 `screenshot` 实时预览窗口。无有效推理引擎时窗口明确显示 `INFERENCE ENGINE NOT LOADED`，推理/扳机线程安全待机；这不是带检测框的真实推理结果，恢复真实推理仍需补齐可加载模型。

---

## 0. 一句话现状

项目已能在当前目录离线启动并打开 GUI，旧配置中的 `.engine` 路径已自动迁移；当前环境只有 ONNX Runtime DML/CPU provider，而项目仅有 TensorRT `.engine`、没有可加载的 `.onnx`，因此下一步决定因是补齐 ONNX 原模型或安装匹配的 TensorRT 运行时。

真跑命令：

```powershell
cd C:\Users\Administrator\Desktop\dopa
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
.\.venv\Scripts\python.exe main.py
```

---

## 1. 已稳的部分（约 65%）

### 1.1 整条链路

1. `main.py` → `Valorant.start()`：已真跑，能初始化依赖并进入 DearPyGui。
2. 本地配置：已真跑，跳过远程验证后可读取 `cfg.json`。
3. 模型路径：已真跑，旧绝对路径会回落到项目 `models` 目录同名文件。
4. GUI：已真跑，模型不可用时仍能保持界面事件循环，不再因 `INVALID_PROTOBUF` 直接退出。
5. 截图源：单机模式下 BetterCam 已完成现场真帧验收；当前配置取得 `(320, 320, 3)` `uint8` 帧并正常释放。OBS UDP / CJK 仍未做现场真帧验收。
6. 推理：尚未通。当前只有 `.engine`，无 TensorRT 时不能交给 ONNX Runtime。
7. 输入/移动：新增显式 `single_machine_mode`。开启时即使 `move_method=km_net`，也会强制绑定本机 `pydirectinput.moveRel`、使用本机键鼠监听，并跳过外置设备初始化、屏蔽和退出清理 API；真实 `km_net` 移动仍待第二台设备现场验收。

### 1.2 已解决的硬阻断

- **远程配置阻断**：当前配置管理改为本地离线读取/保存，不再依赖远程验证；相关改动位于 `settings/remote_config.py`、`settings/server_config.py`。
- **旧绝对模型路径阻断**：`core/mixins/config.py` 新增 `_resolve_model_path()`，失效路径按 basename 回落到项目 `models` 目录。
- **错误后端选择阻断**：`core/mixins/inference.py` 新增 `_find_onnx_fallback()`；无 TensorRT 时，`.engine` 不再进入 ONNX Runtime。
- **GUI 启动稳定性**：没有可用 ONNX 回退模型时，`refresh_engine()` 保留 `engine=None` 并打印明确提示，避免在 `get_input_shape()` 处触发模型解析异常。
- **单机移动测试隔离**：移动设置页新增“单机测试模式”。该开关默认关闭，不覆盖原有 `move_method`；开启并重新启动后强制使用本机 `send_input`，不会连接或调用 KM Net/DHZ/PNMH/CatBox 等外置设备。
- **单机截图源兜底**：单机模式且推理引擎尚未加载时，BetterCam 使用 `single_machine_capture_size`（默认 `320x320`）初始化中心截图区域；有推理引擎时仍优先使用模型输入尺寸，OBS/采集卡路径不变。
- **无引擎安全待机**：截图源和本机输入初始化完成后，如 `engine is None`，`go()` 返回成功但不创建定时器、推理线程和扳机线程，避免后台线程访问空引擎；加载有效模型后仍走原有完整启动链。
- **无引擎实时预览**：单机模式、`infer_debug=true` 且无引擎时，截图管理器启动独立实时预览线程；窗口标题为 `screenshot`，画面标注 `INFERENCE ENGINE NOT LOADED`。该窗口只证明截图链路可用，不代表模型正在推理。

### 1.3 真实样本已落盘（关键资产）

| 文件 | 内容 | 价值 |
|---|---|---|
| `C:\Users\Administrator\Desktop\dopa\cfg.json` | 当前本地运行配置 | 复现当前组、截图源、km_net 和模型选择 |
| `C:\Users\Administrator\Desktop\dopa\models\sjz320v8.engine` | 25,933,932 字节 TensorRT engine | 当前唯一模型产物 |
| `C:\Users\Administrator\Desktop\dopa\core\mixins\config.py` | 模型路径迁移实现 | 解释配置搬目录后的路径回落 |
| `C:\Users\Administrator\Desktop\dopa\core\mixins\inference.py` | 推理后端和 ONNX 回退保护 | 解释当前降级行为 |
| `C:\Users\Administrator\Desktop\dopa\tests` | 45 项回归测试 | 验证离线配置、路径迁移、后端回退、单机输入隔离、截图源兜底、无引擎线程待机及实时预览窗口 |

### 1.4 单机鼠标移动测试

1. 打开 GUI 的移动设置页。
2. 勾选“单机测试模式”。
3. 关闭并重新启动程序，使输入后端切换生效。
4. 此时保留的 `move_method=km_net` 不会被改写，但运行时后端会强制使用本机 `send_input`。
5. 日志应出现：`单机测试模式：使用本机 send_input，跳过外置设备初始化`。

恢复双机联调时取消勾选并重启即可，原 `km_net` IP、Port、UUID 和 `move_method` 均会保留。

真实验收记录：当前机器 BetterCam 成功创建中心区域 `(800, 380, 1120, 700)`，实际取得 `(320, 320, 3)`、`uint8` 帧；真实 `Valorant.go()` 返回 `True`，本机 `send_input` 初始化成功。Windows `EnumWindows` 实测找到标题为 `screenshot` 的窗口，随后 `_secure_cleanup()` / `ScreenshotManager.close()` 正常释放资源。当前窗口为无模型预览，不是检测结果窗口。

---

## 2. 卡点（剩余约 35%，模型推理与外设现场验收） 

### 卡点：TensorRT engine 无可用运行时 —— 决定因 = 模型产物和当前推理后端不匹配

**铁证**：

- 模型清单扫描结果：项目内只有 `models\sjz320v8.engine`，没有 `.onnx`。
- 虚拟环境实测：
  - Python `3.10.20`
  - `onnxruntime 1.23.0`
  - providers = `['DmlExecutionProvider', 'CPUExecutionProvider']`
- NVIDIA 实测：`NVIDIA GeForce RTX 3060 Laptop GPU`，driver `595.97`，显存 `6144 MiB`。
- 首次 GUI 冒烟在旧逻辑下将 `.engine` 交给 ONNX Runtime，真实异常为：
  `onnxruntime...InvalidProtobuf: INVALID_PROTOBUF: Failed to load model because protobuf parsing failed`
- 保护逻辑生效后的 GUI 冒烟输出为：
  `TensorRT不可用，且未找到可用的ONNX原始模型；GUI将继续运行，但推理引擎未加载`
  且随后未出现同一 `INVALID_PROTOBUF` 启动崩溃。

**本会话实证（2026-08-21，逐因变量验证）**：

1. 只修正旧绝对路径：模型文件可找到，但仍触发 `.engine` 的 protobuf 解析失败。
2. 保持当前 provider 不变并增加文件类型保护：不再调用 ONNX Runtime 解析 `.engine`，GUI 可持续运行。
3. 结论：路径不是最终根因；最终根因是当前环境缺少 TensorRT，且没有 ONNX 原始模型可回退。

**这解释一切以往疑点**：

1. “模型文件存在但启动失败”是因为 `.engine` 存在不代表 ONNX Runtime 能加载。
2. “检测到 DML/CPU 但推理仍失败”是因为 provider 可用只说明运行时存在，不会把 TensorRT engine 转换为 ONNX。
3. `error_log.txt` 中较早的 `INVALID_PROTOBUF` 属于保护逻辑落地前的旧失败记录；本次 Ctrl+C 产生的 `KeyboardInterrupt` 是人工停止 GUI 的既有顶层日志行为，不是自发崩溃。

### 2.1 次要修复（保留，非主因）

- `core\mixins\config.py`：统一解析 `infer_model` 和 `original_infer_model`，避免只迁移当前路径而遗漏原始模型路径。
- `core\mixins\inference.py`：无 TensorRT 且无 ONNX 时显式降级，不吞掉真正的 ONNX 模型加载错误。
- `tests\test_model_path_resolution.py`：验证失效绝对路径按文件名回落。
- `tests\test_inference_fallback.py`：验证不存在 ONNX 时不回退、存在原始 ONNX 时正确选择。

### 2.2 解锁路径（按优先级）

1. **P0，决定因**：取得与 `sjz320v8.engine` 对应的 `sjz320v8.onnx`，放入 `C:\Users\Administrator\Desktop\dopa\models\`，再以 DML/CPU 真跑 `go()`、截图和推理。
2. **P0，替代路线**：在确认 engine 的 TensorRT/CUDA 构建版本后，安装匹配的 TensorRT 运行时并验证 `TENSORRT_AVAILABLE=True`；不要盲装版本。
3. **P1，截图链路**：在发送端在线时验证 `udp://169.254.80.4:6666` 的真实帧计数、分辨率、FPS、丢帧和首帧延迟。OBS 实现是 UDP，不应使用 TCP 6666 作为唯一判断。
4. **P1，移动链路**：现场确认当前机器到 `192.168.2.188:41176` 的网卡/路由，再调用现有 `kmNet.init()` 和最小安全移动测试；当前配置的 `km_net_uuid` 只记录为“已配置”，不在文档中保存敏感值。
5. **P2，整链路验收**：模型 → 截图 → ONNX/TRT 推理 → `que_aim` → `aim_pipeline` → `execute_move`，逐段记录输入尺寸、FPS、推理延迟、丢帧率和移动响应。

---

## 3. 后续未真跑的步骤 / 接下来要做的

- **Step 1（P0）**：补齐 `sjz320v8.onnx` 或确认 engine 的 TensorRT 构建环境；重新运行 `refresh_engine()`，确认 `engine.get_input_shape()` 成功。
- **Step 2（P0）**：在不启用移动输出的安全模式下，使用本地/测试画面验证 ONNX DML 推理，确认类别数、输入尺寸和输出框格式。
- **Step 3（P1）**：验证 OBS UDP 真帧：记录 `frames_received`、`frames_dropped`、解码延迟和实际帧尺寸。
- **Step 4（P1）**：验证 `km_net` 端点连通与初始化返回值；先做无输出或极小幅度的设备级测试，再接入瞄准线程。
- **Step 5（P2）**：做完整 10 分钟 soak test，检查线程退出、队列积压、设备断线重连和资源清理。

待验点（旧遗留疑问）：

- `169.254.80.4` 当前 ICMP 不通、TCP `6666` 不通；这不能判定 UDP OBS 流不可用，待发送端在线时实测。
- 当前本机只有 `192.168.1.41`、没有已确认的 `192.168.2.x` 地址；`km_net` 链路尚未现场验证。
- `sjz320v8.engine` 的 TensorRT/CUDA 构建版本未从 engine 元数据中确认。
- 尚未验证 ONNX 原模型与现有 `.engine` 是否完全同版本、同输入尺寸和同类别定义。

---

## 4. 历史卡点（已解决，留作存档）

| 旧卡点 | 状态 |
|---|---|
| 远程配置验证阻止离线启动 | **已解决**（改为本地 `cfg.json` 读取/保存） |
| `cfg.json` 搬目录后模型绝对路径失效 | **已解决**（按项目 `models` 同名文件迁移） |
| 无 TensorRT 时 `.engine` 被错误交给 ONNX Runtime | **已解决**（文件类型保护 + 可用 ONNX 回退） |
| 模型缺失时 GUI 在 `get_input_shape()` 崩溃 | **已解决**（无后端时保留 GUI、推理引擎置空） |

---

## 5. 核心产物（`C:\Users\Administrator\Desktop\dopa`）

- `main.py`：程序入口和启动异常处理。
- `core\valorant.py`：GUI、`go()`、截图源/输入/推理线程启动顺序。
- `core\mixins\config.py`：配置构建和模型路径迁移。
- `core\mixins\inference.py`：推理引擎刷新、TensorRT/ONNX 分支和降级保护。
- `devices\screenshot_manager.py`：BetterCam、OBS UDP、CJK 截图源和帧队列。
- `devices\obs.py`：OBS UDP 视频读取和延迟统计。
- `cfg.json`：当前本地运行配置；包含设备端点配置，但未在本文档展开 UUID。
- `models\sjz320v8.engine`：当前唯一模型文件。
- `tests\`：离线配置、路径解析和推理回退回归测试。

---

## 进度报告（2026-08-21，接入评估阶段）

- **已完成**：项目结构与启动顺序盘点；离线配置启动；模型路径迁移；TensorRT engine/ONNX 后端误用保护；35 项测试；GUI 降级冒烟。
- **当前位置**：接入评估阶段完成，进入 P0 模型产物/运行时解锁阶段；按“可启动 GUI”口径约 65%。
- **离 goal 还差**：可用 ONNX 或匹配 TensorRT；真实推理；OBS UDP 首帧与性能；km_net 连通和最小移动；完整端到端与长时稳定性。
- **下一步**：优先补齐 `sjz320v8.onnx` 或确认 TensorRT 运行时版本，然后在禁用移动输出的安全模式中验证推理。
- ⚠️ **未验证/不确定**：OBS UDP 端点是否有发送端；km_net 端点是否位于当前可达网段；engine 构建版本；ONNX 与 engine 的模型版本一致性；真实推理性能。
