# 系统架构文档

## 1. 架构概览

DOPA3 采用 **单进程多线程** 架构，核心由以下子系统组成：

```
┌──────────────────────────────────────────────────────────────────┐
│                         main.py (入口)                           │
│         异常处理 · TensorRT 容错 · 启动 Valorant 实例             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     core/ — Valorant 类                          │
│                    (~7800 行，系统中枢)                           │
│                                                                  │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────────────────┐  │
│  │  GUI 子系统  │ │  配置管理子系统 │ │   输入设备管理子系统     │  │
│  │ (DearPyGui) │ │ (cfg.json)    │ │ (km_net/dhz/catbox/...)  │  │
│  └─────────────┘ └───────────────┘ └──────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                   推理与瞄准子系统                            │ │
│  │  infer线程 → que_aim → aim_bot定时器 → execute_move          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                   触发器子系统 (trigger)                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │               截图管理子系统 (screenshot_manager)             │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件与职责

### 2.1 入口层 — `main.py`

| 职责 | 说明 |
|------|------|
| 程序入口 | 创建 `Valorant()` 实例并调用 `.start()` |
| 异常容错 | 捕获 TensorRT/CUDA 导入错误，降级到 ONNX 推理 |
| 全局异常钩子 | 未处理异常写入 `error_log.txt` |
| 资源清理 | `finally` 块调用 `_secure_cleanup()` |

### 2.2 核心控制层 — `core/valorant.py` / `Valorant` 类

这是系统最大最复杂的模块（约 7800 行），承担了以下职责：

| 子系统 | 职责 |
|--------|------|
| **GUI** | 使用 DearPyGui 构建完整的参数调节界面 |
| **配置管理** | 读写 `cfg.json`，管理分组/按键/推理参数 |
| **推理调度** | `infer()` 线程：截图 → 预处理 → 模型推理 → 后处理 → 投递结果 |
| **瞄准控制** | `aim_bot_func()` 定时器回调（1ms 周期）：消费推理结果 → 控制鼠标 |
| **触发器** | `trigger()` 线程：自动扣枪逻辑 |
| **压枪** | `down_func()` 定时器：后坐力补偿 + 鼠标轨迹回放 |
| **输入设备** | `init_mouse()` 初始化移动方法（km_net/dhz/catbox 等） |
| **键鼠监听** | `on_click/on_press/on_release` 处理用户输入 |
| **准星找色** | 基于 HSV 颜色检测的准星锁定辅助功能 |
| **闪光弹检测** | 自动背闪转向 |

### 2.3 瞄准 Pipeline — `aim/aim_pipeline.py` / `AimPipeline` 类

独立的瞄准逻辑模块，从 `core/valorant.py` 中解耦：

| 组件 | 职责 |
|------|------|
| `ByteTracker` | 多目标跟踪，提供稳定的 track_id |
| `KalmanPredictor2D` | 2D 恒速卡尔曼滤波，预测目标未来位置 |
| `DualAxisPID` | 双轴 PID 控制器，计算鼠标移动量 |
| `AimMoveQuantizer` | 亚像素累积量化，防止小数截断 |
| `AimPointResolver` | 瞄准点解析（支持按类别/随机化） |
| 目标优先级选择 | 距离 + 大小 + 粘滞 + ID 锁定 |
| 移动预测 | 速度估计 + 前馈补偿 |

### 2.4 推理引擎层

| 模块 | 职责 |
|------|------|
| `inference/infer_class.py` | ONNX Runtime 推理引擎封装，支持延迟初始化、多设备选择 |
| `inference/inference_engine.py` | TensorRT 推理引擎（CUDA Graph 加速） |
| `inference/infer_function.py` | NMS 处理（v5/v8 格式）、框坐标转换、可视化绘制 |
| `inference/v11onnx_support.py` | YOLOv11 模型发现、验证、运行时配置 |
| `inference/decode_model.py` | 加密模型 (.ZTX) 解密 |

### 2.5 截图与输入层

| 模块 | 职责 |
|------|------|
| `devices/screenshot_manager.py` | 统一截图接口：BetterCam / OBS / 采集卡，内存池复用 |
| `devices/obs.py` | OBS UDP 视频流接收与解码 |
| `devices/dhz.py` | DHZ Box UDP 命令通信 |
| `devices/catbox_wrapper.py` | CatBox 协议封装 |
| `cat/catnet_lite.py` | CatNetLite 虚拟设备模块 |

### 2.6 辅助层

| 模块 | 职责 |
|------|------|
| `aim/pid.py` | PID 控制器算法（单轴 `PID` + 双轴 `DualAxisPID`） |
| `aim/bytetrack.py` | ByteTrack 多目标跟踪器（IoU + 匈牙利算法） |
| `util/profiler.py` | 帧级性能分析 (EMA 平滑统计) |
| `util/gui_handlers.py` | GUI 配置变更统一处理框架 |
| `util/function.py` | 通用工具（按键转换、配置读取、距离计算） |
| `webui/server.py` | NiceGUI Web 控制面板 |

### 2.7 验证与配置层

| 模块 | 职责 |
|------|------|
| `settings/buff.py` | 卡密验证系统（RC4 加密，已禁用） |
| `settings/remote_config.py` | 远程配置获取（AES-CBC 加密，JWT 令牌认证） |
| `settings/server_config.py` | 服务器连接参数 |

---

## 3. 线程模型

```
主线程 (GUI)
    │
    ├── infer 线程 ──────────────┐
    │   截图 → 预处理 → 推理 → NMS │ → que_aim (Queue maxsize=1)
    │                              │
    ├── aim_bot 定时器 (1ms) ─────┤ ← que_aim
    │   目标选择 → PID → 移动      │ → execute_move()
    │                              │
    ├── trigger 线程 ─────────────┤
    │   自动扣枪逻辑               │
    │                              │
    ├── down 定时器 ──────────────┤
    │   后坐力补偿                  │
    │                              │
    ├── 键鼠监听线程 (pynput) ────┤
    │   on_click / on_press        │
    │                              │
    ├── 设备监听线程 ─────────────┤
    │   km_net / dhz / catbox 状态 │
    │                              │
    └── 心跳线程 (remote_config) ─┤
        令牌续期                    │
```

### 线程间通信

- **`que_aim`** (Queue, maxsize=1)：infer 线程 → aim_bot 定时器，传输检测结果
- **`que_trigger`** (Queue, maxsize=1)：infer 线程 → trigger 线程，传输触发判断数据
- **共享状态**：`aim_key_status`、`left_pressed`、`right_pressed` 等标志位
- **定时器回调**：Windows Multimedia Timer (`timeSetEvent`)，1ms 精度

---

## 4. 配置管理

### 配置层次

```
cfg.json (持久化)
    │
    ├── 全局参数（move_method, is_obs, ...）
    │
    ├── groups/                    ← 配置分组
    │   ├── valorant/
    │   │   ├── infer_model       ← 模型路径
    │   │   ├── is_trt            ← TensorRT 开关
    │   │   ├── is_v8             ← v8 模型格式
    │   │   └── aim_keys/         ← 按键级配置
    │   │       ├── mouse_right/
    │   │       │   ├── confidence_threshold
    │   │       │   ├── aim_bot_scope
    │   │       │   ├── PID 参数
    │   │       │   ├── trigger 参数
    │   │       │   └── class_aim_positions
    │   │       └── ...
    │   └── cs2/
    │       └── ...
    │
    └── games/                    ← 后坐力轨迹数据
        ├── cs2/
        │   └── AK47/
        │       └── [stage_data]
        └── ...
```

### 配置热更新

- `ConfigChangeHandler` 提供统一的值变更处理，支持嵌套路径和上下文变量
- `ConfigItemGroup` 批量注册 80+ GUI 控件到配置路径
- 所有配置变更实时生效，延迟保存到 `cfg.json`

---

## 5. 架构问题分析

### 5.1 紧耦合

- ~~**`core/valorant.py` 过于庞大**（~7400 行）~~ → 已拆为 `core/` 包，`core/valorant.py` 现 872 行（~86% 外移）：同时承担 GUI、配置、推理调度、控制逻辑、设备管理、闪光弹检测等职责，严重违反单一职责原则
- `Valorant` 类持有近 200 个实例属性，理解和维护成本高

### 5.2 模块边界不清

- `aim/aim_pipeline.py` 已从 `core/valorant.py` 解耦瞄准逻辑，`aim_bot_func` 统一走 pipeline 路径
- 触发器逻辑、闪光弹逻辑已分居 `core/mixins/trigger.py`、`core/mixins/flash.py`

### 5.3 冗余逻辑

- NMS 处理有 `nms_v8`、`nms_v5`、`nms` 三种实现

### 5.4 代码质量

- 异常捕获中大量 `except Exception` 可能隐藏错误（core/valorant.py 约 139 处）

### 5.5 已修复的历史问题

- ✅ `aim_bot_func` 双路径 → 已合并为 pipeline 单路径
- ✅ `key2str` 重复定义 → 已统一至 util/function.py
- ✅ `settings/buff.py` ~2500 行死代码 → 已精简为 76 行存根
- ✅ `# inserted` 反编译痕迹 → 已全部清除
- ✅ `select_target_by_priority` 冗余 → 已从 core/valorant.py 移除
