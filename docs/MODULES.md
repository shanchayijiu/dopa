# 模块详细说明

## 1. 入口模块

### main.py

**职责**：程序入口点

- 创建 `Valorant()` 实例并调用 `start()`
- 全局异常钩子 `sys.excepthook`：未处理异常写入 `error_log.txt`
- TensorRT 导入错误容错：捕获 `ImportError`/`OSError` 后降级到 ONNX 运行
- `finally` 中调用 `_secure_cleanup()` 确保资源释放

**关键函数**：
| 函数 | 说明 |
|------|------|
| `global_exception_hook()` | 全局异常写文件 |
| `handle_tensorrt_error()` | TensorRT 缺失时打印指导信息 |

---

## 2. 核心控制模块

### core/valorant.py — `Valorant` 类

**职责**：系统中枢，约 7800 行

**核心方法**：

| 方法 | 行数范围 | 说明 |
|------|----------|------|
| `__init__()` | ~300-500 | 初始化 200+ 实例属性、配置加载、设备检测 |
| `start()` | ~1097 | 入口：创建 Buff 实例 → 设置 verified → 启动 GUI |
| `gui()` | ~1200-2100 | DearPyGui 完整界面构建（侧边栏 + 多 Tab 面板） |
| `go()` | ~1103 | 启动推理：初始化截图管理器 → 初始化鼠标 → 启动 infer/trigger 线程 |
| `infer()` | ~2300-2500 | 推理主循环：截图 → 预处理 → 推理 → NMS → 投递 |
| `aim_bot_func()` | ~2137-2303 | 1ms 定时器回调：消费推理结果 → Pipeline → 执行移动 |
| `trigger()` | ~2500+ | 触发器线程：自动扣枪 |
| `down_func()` | ~800-900 | 后坐力补偿定时器 |
| `init_mouse()` | ~5558-5767 | 输入设备初始化（多种移动方法） |
| `on_click/on_press/on_release()` | ~900-1000 | 键鼠事件处理 |
| `build_config()` | ~2853-2990 | 配置文件加载与默认值填充 |
| `_init_config_handlers()` | ~7015-7200 | 80+ 配置项注册 |
| `execute_move()` | ~5800+ | 鼠标移动执行 |
| `detect_and_handle_flashbang()` | ~7330-7430 | 闪光弹检测 |
| `handle_color_pick_hotkey()` | ~6700-6870 | F3 取色功能 |
| `_secure_cleanup()` | ~1068-1096 | 安全资源清理 |

**全局函数**：

| 函数 | 说明 |
|------|------|
| `check_tensorrt_availability()` | 检测 TensorRT 环境 |
| `detect_inference_devices()` | 检测可用推理设备 (CPU/DML/CUDA/TensorRT) |
| `create_gradient_image()` | 生成 UI 渐变背景 |

---

## 3. 瞄准 Pipeline 模块

### aim/aim_pipeline.py

**职责**：独立的瞄准数据处理管线

**类**：

#### `KalmanPredictor2D`
- 2D 恒速卡尔曼滤波预测器
- 状态向量：`[x, y, vx, vy]`
- Per-track 状态管理，支持 `max_tracks` 限制
- 方法：`update()` → 观测更新，`predict()` → 多帧预测

#### `AimMoveQuantizer`
- 鼠标移动量化器
- 累积亚像素残差，防止 `int()` 截断导致的精度丢失
- `quantize(dx, dy)` → `(int_dx, int_dy)`

#### `AimPointResolver`
- 瞄准点解析器
- 支持按类别配置不同瞄准高度
- 支持随机化瞄准位置（范围内均匀分布）

#### `AimPipeline` — 核心类
- **目标跟踪**：内置 `ByteTracker`，提供稳定 track_id
- **目标选择**：`select_target_by_priority()` — 多维评分 + 粘滞 + ID 强锁定 + 宽限帧
- **小目标增强**：时间平滑 + 面积 boost
- **移动预测**：自维护速度估计（补偿自身鼠标运动）+ EMA 前馈
- **PID 控制**：双轴 PID → 量化
- **线程安全**：全部关键方法使用 `RLock`

主要方法：

| 方法 | 说明 |
|------|------|
| `step_frame()` | 完整帧处理入口 |
| `step_aim()` | 目标选择 + PID 控制 |
| `select_from_aim_targets()` | 构建目标列表 + ByteTrack + 选择 |
| `select_target_by_priority()` | 优先级排序 + 锁定逻辑 |
| `smooth_small_targets()` | 小目标时间平滑 |
| `compute_pid_move()` | PID 计算 + 量化（外部接口） |
| `reset()` | 重置所有状态 |

---

## 4. PID 控制模块

### aim/pid.py

**职责**：鼠标移动控制算法

#### `PID` (单轴)
- 基础位置式 PID 控制器
- 支持输出限幅和积分抗饱和

#### `DualAxisPID` (双轴) — 主要使用
- X/Y 轴独立 PID 参数
- **积分抗饱和**：`freeze` 模式 + `windup_guard` 限幅
- **误差滤波**：EMA 平滑输入误差，过滤检测框抖动
- **速度滤波**：EMA 平滑输出，减少移动抖动
- **指数平滑**：时间常数式平滑 (`tau_x/y` ms)
- **死区**：`smooth_deadzone` 内直接通过

参数说明：

| 参数 | 说明 |
|------|------|
| `kp [x, y]` | 比例系数 |
| `ki [x, y]` | 积分系数 |
| `kd [x, y]` | 微分系数 |
| `windup_guard [x, y]` | 积分限幅 |
| `smooth_params [x, y, deadzone, algo]` | 平滑参数 |
| `error_filter_alpha` | 误差 EMA 系数 (0~0.95) |
| `vel_filter_alpha` | 速度 EMA 系数 (0~0.95) |

---

## 5. 目标跟踪模块

### aim/bytetrack.py

**职责**：多目标跟踪，提供稳定的 track_id

**核心类**：

#### `STrack`
- 单目标轨迹
- 状态机：`NEW → TRACKED → LOST → REMOVED`
- EMA 速度估计（`_vel_alpha=0.15`）
- 匀速模型预测 `predict()`

#### `ByteTracker`
- 参数：`track_thresh`, `match_thresh`, `track_buffer`, `max_center_dist`
- **两阶段匹配**：
  1. 高分检测 → 已跟踪轨迹（IoU + 中心距离混合代价）
  2. 低分检测 → 丢失轨迹
- 匈牙利算法（`scipy.optimize.linear_sum_assignment`）
- 丢失轨迹保留 `track_buffer` 帧后移除

**辅助函数**：

| 函数 | 说明 |
|------|------|
| `_iou_batch()` | 批量 IoU 计算 |
| `_linear_assignment()` | 匈牙利算法封装 |

---

## 6. 推理引擎模块

### inference/infer_class.py — `OnnxRuntimeDmlEngine`

**职责**：ONNX 模型加载与推理

- 支持加密模型 (`.ZTX`) 和明文 ONNX
- 多后端：CPU / DML / CUDA / TensorRT
- 延迟初始化 (`lazy_init`)
- 线程安全（`threading.Lock`）
- 内置 `NMSProcessor`：自动选择 NMS 算法

#### `NMSProcessor`
- 支持 `v8` / `v5` / `standard` 三种算法
- 基于输入形状自动选择最优算法
- 性能统计 + 结果缓存

### inference/inference_engine.py — `TensorRTInferenceEngine`

**职责**：TensorRT GPU 推理引擎

- CUDA 上下文管理
- 内存分配 (`pagelocked_host + device`)
- CUDA Graph 加速（CuPy 可选）
- 自动从 ONNX 转换 engine (`trtexec`)
- 显式资源清理

### inference/infer_function.py

**职责**：推理辅助函数

| 函数 | 说明 |
|------|------|
| `nms_v8()` | YOLOv8/v11 格式 NMS（cv2.dnn.NMSBoxes） |
| `nms_v5()` | YOLOv5 格式 NMS |
| `nms()` | 标准 NMS |
| `draw_boxes_v8()` | 检测框可视化 |
| `convert_box_coordinates()` | cx,cy,w,h → x1,y1,x2,y2 |
| `numba_convert_new_array()` | Numba 加速归一化（可选） |
| `numba_resize_and_normalize()` | Numba 加速 resize+归一化 |

### inference/v11onnx_support.py

**职责**：YOLOv11 ONNX 模型专用支持

| 函数/类 | 说明 |
|---------|------|
| `V11ModelMetadata` | 模型元数据 dataclass |
| `infer_model_variant_from_path()` | 从文件名推断模型变体 |
| `should_use_v11onnx()` | 判断是否使用 v11 流程 |
| `discover_v11onnx_model()` | 自动搜索 v11 模型文件 |
| `validate_v11onnx_model()` | 模型结构验证 |
| `build_ort_runtime_components()` | 构建 ORT session 参数 |
| `resolve_runtime_config()` | 解析运行时配置 |

### inference/decode_model.py

**职责**：加密模型解密

- PBKDF2 密钥派生 (`SHA256, 100000 iterations`)
- Fernet 对称解密
- 用户名 + 固定盐值生成密钥

---

## 7. 截图与视频模块

### devices/screenshot_manager.py — `ScreenshotManager`

**职责**：统一截图接口

- **多源支持**：BetterCam / OBS / 采集卡
- **分离模式**：多线程异步截图 + 内存池复用
- **简单模式**：同步截图（向后兼容）

**辅助类**：

| 类 | 说明 |
|----|------|
| `MemoryPool` | numpy 数组内存池，减少 GC 压力 |
| `PerformanceMonitor` | FPS/延迟统计，自适应性能等级 |

### devices/obs.py — `OBSVideoStream`

**职责**：OBS UDP 视频流接收

- FFmpeg UDP 源 (`udp://ip:port`)
- 低延迟配置：`BUFFERSIZE=1`
- 线程池读取 + 帧队列（maxsize=1）
- 延迟统计报告

---

## 8. 输入设备模块

### devices/dhz.py — `DHZBOX`

**职责**：DHZ Box UDP 控制

- 鼠标移动 / 按键 / 屏蔽
- 加密字符串协议（凯撒密码偏移）
- UDP 发送 + 接收线程监听按键状态

### devices/catbox_wrapper.py — `CatBoxWrapper`

**职责**：CatBox 协议高层封装

- 调用 `CatNetLite` 底层库
- 鼠标移动 / 按键 / 屏蔽
- 连接管理

### cat/catnet_lite.py — `CatNetLite`

**职责**：CatBox 底层协议（当前为虚拟实现）

- 错误码定义 (`ErrorCode`)
- 按钮常量 (`BTN_LEFT/RIGHT/MIDDLE/SIDE/EXTRA`)
- 虚拟模式：打印操作日志

---

## 9. GUI 与配置模块

### util/gui_handlers.py

**职责**：GUI 事件处理框架

#### `ConfigChangeHandler`
- 统一配置变更处理
- 支持嵌套路径（如 `groups.{group}.aim_keys.{key}.value`）
- 上下文变量解析
- 注册后处理回调

#### `ConfigItemGroup`（在代码末尾）
- 批量注册控件到配置路径
- 简化 80+ 配置项的绑定

### webui/server.py

**职责**：Web 控制面板

- NiceGUI 框架
- 配置分类展示 + 中文标签
- 实时日志查看
- 远程参数调节

---

## 10. 验证与网络模块

### settings/buff.py — `Buff_Single` / `Buff_User`

**职责**：卡密网络验证系统（已禁用）

- RC4 加密通信
- 机器码绑定（CPU ID + MD5）
- 单码/注册码登录
- 心跳保活
- **当前状态**：`RequestURL = None`，验证已跳过

### settings/remote_config.py — `RemoteConfigManager`

**职责**：远程配置管理

- AES-CBC-PKCS7 加密（与 PHP 后端兼容）
- JWT 令牌认证 + 自动续期
- 心跳线程（60 秒间隔）
- 配置上传/下载

### settings/server_config.py

**职责**：服务器连接常量

```python
REMOTE_CONFIG_SERVER_URL = 'http://127.0.0.1:2028'
ENCRYPTION_KEY = 'huiyestudio'
REQUEST_TIMEOUT = 10
DEBUG_MODE = False
```

---

## 11. 工具模块

### util/function.py

**职责**：通用工具函数

| 函数 | 说明 |
|------|------|
| `key2str()` | pynput 按键 → 字符串 |
| `is_cursor_visible()` | 检测光标可见性 |
| `get_config()` | 读取 `config.json` |
| `get_linear_distance()` | 两点距离计算 |
| `get_machine_code()` | 获取机器码 |

### util/profiler.py — `FrameProfiler`

**职责**：帧级性能分析

- 记录每帧各阶段耗时（cap/pre/infer/post）
- EMA 平滑统计
- 定期报告
- TRT 细粒度分析（H2D/exec/D2H）

---

## 12. 配置文件

### cfg.json

运行时配置文件，包含：
- 全局参数（移动方法、设备连接、截图源配置）
- 分组配置（模型路径、按键绑定、PID 参数、触发器）
- 游戏后坐力数据

### config.json

卡密存储文件（`card_key` 字段）

### presets/color_range.json

准星颜色锁定的 HSV 范围预设
