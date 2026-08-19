# DOPA3 项目结构

> 2026-08-10。一期（文档归位）与二期（`core/` 包化）已执行完毕，本文记录落地后的
> 实际结构；三期为待定项。
>
> 历史校正：旧版记录的 `core.py` 约 1345 行、29 个 `.py`、15 个 mix-in 均已过时；
> 旧版结论"所有 `.py` 必须留在根目录"成立于循环 import 尚未消除的时期，该前提已
> 于 2026-08-10 随 `core/runtime.py` 的引入消失。

---

## 当前事实

| 项 | 整理前 | 二期后 | 三期后（当前） |
|----|-------|-------|--------------|
| 根目录 `.py` | 48 | 27 | **2**（`main.py`、`conftest.py`） |
| 根目录文件总数 | 60 | 41 | **12** |
| `core` 承载形式 | 22 个扁平 `core*.py` | `core/` 包，24 个模块 | 同左 |
| 业务模块承载形式 | 扁平散落根目录 | 仍扁平（25 个） | **6 个职责包** |
| 循环 import | 5 处（靠语句顺序维持） | 0 | 0 |
| `from core import *` 名字 | 109 | 109 | 109（逐名一致） |
| `Valorant` 可达方法 | 368 | 368 | 368 |
| MRO 层数 | 22 | 22 | 22 |
| 测试 | 31 passed | 31 passed | 31 passed |

---

## 物理目录树

```
dopa/
├── main.py                      程序入口（from core import * 取 109 个名字）
├── conftest.py                  pytest 引导：显式把项目根加入 sys.path
├── core/                        Valorant 主控装配包
│   ├── __init__.py              re-export valorant 的公开名字（__all__ 动态推导）
│   ├── valorant.py              主控类（872 行）：装配中枢 + 运动执行环 + 生命周期
│   ├── runtime.py               共享运行时事实（版本/DLL 注册/TensorRT 探测/渐变图）
│   └── mixins/                  20 个 mix-in（5832 行），按子系统分居
├── aim/                         瞄准：目标选择、追踪关联、预测、PID、准星找色（5 个）
├── inference/                   推理：TensorRT/ONNX 引擎、NMS、模型发现解密（7 个）
├── devices/                     外设采集：输入协议、截图源、闪光弹检测（5 个）
├── settings/                    配置授权：默认配置、cfg 读写、远程配置、卡密（4 个）
├── webui/                       NiceGUI Web 控制面板（1 个）
├── util/                        工具：按键转换、异常记录、性能分析、配置变更（4 个）
├── cfg.json                     运行时配置（裸文件名读写，须留根目录）
├── config.json                  卡密存储（裸文件名）
├── km.dll / logitech.dll        输入驱动（mixins/devices.py 中 CDLL('./…') 硬编码）
├── kmNet.cp310-win_amd64.pyd    本地编译模块（3.10 专用 ABI，裸名 import）
├── pykm2.pyc                    本地编译模块（裸名 import）
├── assets/                      字体、UI 渐变图（以 assets/ 前缀引用）
├── cat/                         CatBox 底层协议包
├── presets/                     准星找色 HSV 预设（原 `config/`，为避免与包名混淆而改名）
├── dll/                         TensorRT 运行时 DLL（gitignore）
├── docs/                        架构/流程/模块/安装文档
├── models/                      TensorRT 引擎文件
├── tests/                       单元测试（31 passed）
├── requirements.txt
├── run.bat                      venv 3.10 启动脚本
└── README.md
```

---

## `core/` 包

### 导入方向

```
valorant.py  ──>  mixins/*.py  ──>  runtime.py
```

恒为单向，无环。**禁止任何 mixin 反向导入 `valorant`** —— 那正是包化前 5 处循环的
成因。

### 循环 import 的消除

包化前，`core_config` / `core_gui` / `core_infercfg` / `core_inference` /
`core_verify` 五个 mix-in 反向 `from core import TENSORRT_AVAILABLE / VERSION /
create_gradient_image`，与 `core.py` 底部的 mix-in import 构成 5 处循环。它能运行
仅因这些名字恰好定义在 L38–215、赶在 mix-in import（L220）之前 —— 安全边距 5 行，
`VERSION` 位于 L214。改动定义位置即会导致启动失败。

这些与 `Valorant` 类无关的共享事实现归入 `core/runtime.py`，两侧统一从它取用。

`core/mixins/verify.py` 是特例：它在函数体内延迟 `import runtime`，以便引擎导入
失败时读到降级后的 `TENSORRT_AVAILABLE`，而非导入期快照。包化时该处一并改为
`from .. import runtime as core_runtime`，语义不变。

### 星号导出契约

`main.py` L5 的 `from core import *` 取 109 个名字。`core/__init__.py` 的
`__all__` 由 `valorant.py` 的模块级公开名字动态推导，与包化前的默认星号导入规则
逐名等价，并排除 `mixins` / `runtime` / `valorant` 三个子模块名（包结构的产物，
包化前不存在）。动态推导意味着 `valorant.py` 增删顶层名字会自动反映到包接口。

### 三类不可拆内容

`core/valorant.py` 保留 **配置装配中枢**（`__init__` 290 行 + `_change_callback`）、
**运动执行环**（`aim_bot_func` / `execute_move` / `_emit_move_rel` /
`_execute_move_async` / `_try_crosshair_pull` / `get_current_aim_center`）、
**生命周期编排**（`start` / `go` / `on_start_button_click` / `down_func` 及跨切面
`close_screenshot` / `reset_down_status` / `_update_class_checkboxes`）。停止边界论证见
`CORE_REFACTOR_AUDIT.md` §4.22。

### mixins/ 清单（20 个，5832 行）

| 模块 | 行数 | 职责 |
|------|-----|------|
| `inference.py` | 800 | 推理调度：`infer`、引擎刷新/创建、队列清理、v11onnx 准备 |
| `devices.py` | 695 | 设备：`init_mouse`、监听线程、断开、makcu 初始化与锁 |
| `gui.py` | 523 | GUI 构建：`gui()` 构建整个 DearPyGui 界面 + `switch_tab` |
| `aimcfg.py` | 439 | 瞄准配置：分组切换、置信度、模型选择、类别优先级与瞄准参数 |
| `keybind.py` | 370 | 按键绑定：分组增删改、类别多选、绑定捕获轮询 |
| `systemcfg.py` | 365 | 系统配置：灵敏度/DPI/Web/推理设备/卡密/OBS/输入设备 |
| `config.py` | 359 | 配置：`build_config`、类元数据初始化与迁移、参数刷新 |
| `crosshair_ui.py` | 321 | 准星 UI：`on_crosshair_*`、HSV、取色、小目标开关 |
| `mousere.py` | 300 | 鼠标压枪轨迹：JSON 解析、回放线程、下拉渲染 |
| `trigger.py` | 298 | 触发器：`trigger`、按下抬起、后坐力起停、`update_rect` |
| `infercfg.py` | 232 | 推理配置：v8/TRT 开关、目标优先级初始化、DPI 缩放 |
| `verify.py` | 199 | 授权校验、加密模型解密、敏感数据清理 |
| `flash.py` | 181 | 自动背闪回调与 UI 状态 |
| `input.py` | 174 | 键鼠监听器生命周期 |
| `mask.py` | 156 | 鼠标按键屏蔽（kmNet/catbox/dhz 三设备分发） |
| `pidtracker.py` | 134 | PID/跟踪器配置回调、`_update_pid_params` |
| `gameconfig.py` | 121 | 游戏/枪械配置渲染与增删改 |
| `display.py` | 79 | 显示相关回调 |
| `persist.py` | 59 | 配置持久化 |
| `perception.py` | 27 | 隔离的零调用死代码（保 `import *` 导出契约） |

---

## 业务分包（25 个模块 / 6 个包）

### 瞄准 Pipeline 与推理（4903 行）
| 文件 | 职责 |
|------|------|
| `aim/aim_pipeline.py` | 目标选择 + 跟踪关联 + 卡尔曼预测 + PID + 量化（线程安全） |
| `aim/crosshair_tracker.py` | 准星 HSV 找色追踪（无 GUI 依赖） |
| `inference/inference_engine.py` | TensorRT 引擎（CUDA Graph、ONNX→engine 转换） |
| `inference/v11onnx_support.py` | YOLOv11 模型发现/验证/运行时配置 |
| `aim/bytetrack.py` | ByteTrack 多目标跟踪（IoU + 匈牙利匹配） |
| `aim/pid.py` | 双轴 PID 控制器（抗饱和、EMA 滤波、死区） |
| `inference/infer_function.py` | NMS（v8/v5/standard）、坐标转换、可视化 |
| `inference/infer_class.py` | ONNX Runtime 封装（DML/CUDA/CPU、NMSProcessor） |
| `inference/cuda_compat.py` | CUDA Driver API 兼容层（pycuda 替代） |
| `inference/v11onnx_benchmark.py` | YOLOv11 性能基准 |
| `inference/decode_model.py` | 加密模型 `.ZTX` 解密（PBKDF2 + Fernet） |

### 采集与设备（1971 行）
| 文件 | 职责 |
|------|------|
| `devices/screenshot_manager.py` | 统一截图接口（BetterCam/OBS/采集卡，内存池） |
| `devices/flashbang_handler.py` | 闪光弹检测与人性化背闪执行 |
| `devices/catbox_wrapper.py` | CatBox 高层协议封装 |
| `devices/dhz.py` | DHZ Box UDP 控制 |
| `devices/obs.py` | OBS UDP 视频流接收解码 |
| `settings/buff.py` | 卡密验证（已禁用存根，保留类导出） |
| `cat/` | CatBox 底层协议包（当前虚拟实现） |

### 配置、Web 与工具（1681 行）
| 文件 | 职责 |
|------|------|
| `settings/remote_config.py` | 远程配置（AES-CBC + JWT） |
| `webui/server.py` | NiceGUI Web 控制面板 |
| `settings/config_manager.py` | 默认配置字典、`cfg.json` 读写 |
| `util/gui_handlers.py` | 配置变更统一框架（ConfigChangeHandler / ConfigItemGroup） |
| `util/function.py` | 通用工具（按键转换、距离、机器码、光标可见性） |
| `util/diagnostics.py` | 异常抑制记录 |
| `util/profiler.py` | 帧级性能分析（EMA 平滑） |
| `settings/server_config.py` | 服务器连接常量 |

---

## 三条硬约束

整理受这三条支配，也是分期依据：

**约束一 · 裸名 import**：本地模块靠 `from xxx import` 互相引用，搬迁需同步改
import。二期共改写 29 处（20 个 mixin 引用 + 5 处 runtime 引用 + 3 处测试引用 +
1 处函数内延迟 import）。

**约束二 · CWD 相对路径**：`CDLL('./km.dll')`、`CDLL('./logitech.dll')`
（`core/mixins/devices.py`）；`cfg.json` 在 `config_manager` / `remote_config` /
`server` 三处；`error_log.txt` 在 `main` / `core/valorant` / `screenshot_manager`
三处。这些依赖"进程 CWD 即项目根"。搬 `.py` 不影响，搬数据文件会。

**约束三 · `from core import *` 是入口契约**：109 个名字，见上文星号导出契约。

---

## 三期 · 业务模块分包（已完成）

25 个业务模块按职责收进 6 个包，根目录只留 `main.py` 与 `conftest.py`。

先决条件是包名占用：原 `config/` 数据目录与拟建包名同处顶层，Python 会让先命中
的一方胜出。核查发现 `config/color_range.json` 零代码引用（仅 README 目录树提
及），改名 `presets/` 无运行风险，先决条件即解。另已确认 6 个包名在 stdlib 与
site-packages 中均无同名，不存在遮蔽。

搬迁沿用二期的做法：先从活代码抓契约基线，在暂存目录重写全部 import，验证通过
再原子替换。共重写 66 处 import 语句，覆盖 `core/` 全包、入口、测试。

包内同级引用改为相对导入（如 `aim_pipeline` 引 `pid` 用 `from .pid import`），
跨包用绝对导入，这样每个包都能独立移动。

一处遗漏值得记下：`mock.patch("v11onnx_support._collect_onnx_metadata")` 把模块
路径写在字符串里，import 重写器看不见它，替换后 2 项测试报
`ModuleNotFoundError`。全仓扫描字符串形式的模块引用后确认只有这 2 处需改；其余
命中都是字典键与属性名（`'dhz'`、`'pid'`、`self.aim_pipeline`），动了反而会坏。

---

## 验收门槛

任何结构调整需通过四项，缺一不可：

1. `from core import *` 绑定的名字集与调整前逐名一致（109 个）
2. `Valorant` 可达方法 368 个、MRO 22 层不变
3. `main.py` 实启 12 秒存活且不产生 `error_log.txt`
4. `pytest tests -q` 全绿（31 passed），且从项目外目录调用同样通过

二期实测：四项全过，stderr 中的 DearPyGui 弃用警告来源已由 `core_gui.py` 变为
`core/mixins/gui.py`，可作为新包确已生效的旁证。

---

## 不可移动清单

- **`cfg.json` / `config.json`**：多处裸文件名读写（约束二）
- **`km.dll` / `logitech.dll`**：`CDLL('./…')` 硬编码
- **`kmNet.cp310-win_amd64.pyd` / `pykm2.pyc`**：裸名 import，前者 3.10 专用 ABI，不可删不可移
- **`assets/` 内文件名**：`core/mixins/gui.py`、`core/runtime.py` 以 `assets/` 前缀引用

已清理残留：`debug.log`、`trt_cache.lock`、`error_log.txt`（运行时再生）、`*.bak`、
各 `__pycache__/`、`_v_err.txt`、`_v_out.txt`、`_verify4.ps1`。
