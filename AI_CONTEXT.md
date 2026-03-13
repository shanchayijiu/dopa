# AI 开发上下文文档

> 本文档为后续 AI Agent 提供项目理解上下文，确保在修改代码时遵循已有架构和约束。

---

## 1. 项目目标

DOPA3 是一款基于深度学习的 AI 辅助瞄准系统，目标是：

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

### 3.1 core.py

- **最大最复杂的文件**（~7800 行），修改需格外谨慎
- `Valorant` 类是唯一的主控类，持有所有系统状态
- GUI 使用 DearPyGui，所有控件 ID 作为字符串传递
- 配置变更通过 `ConfigChangeHandler` 统一管理
- 线程模型：主线程(GUI) + infer线程 + trigger线程 + 多个定时器回调
- **不要** 在定时器回调中做阻塞操作

### 3.2 aim_pipeline.py

- 已从 `core.py` 解耦的瞄准逻辑模块
- **所有公开方法均使用 `RLock` 保证线程安全**
- 修改目标选择逻辑时需同时考虑 `select_target_by_priority()` 和 `_find_locked_target()`
- `step_frame()` 是主入口，`step_aim()` 是次级入口
- 目标 ID 锁定有宽限帧机制（`_lock_grace_max=5`），修改时需确保逻辑一致

### 3.3 pid.py

- `DualAxisPID` 是主要使用的控制器
- 参数变更通过 `core.py` 的 `refresh_controller_params()` 传递
- 平滑参数是时间常数（毫秒），不是 0-1 的 alpha 值
- `reset()` 必须清理所有内部状态

### 3.4 bytetrack.py

- 标准 ByteTrack 实现，依赖 `scipy.optimize.linear_sum_assignment`
- `STrack._next_id` 是类级别的自增 ID，`reset_id()` 可重置
- `max_center_dist` 参数用于限制中心距离过远的匹配

### 3.5 infer_class.py

- `OnnxRuntimeDmlEngine` 支持延迟初始化
- 模型可能是加密的（`.ZTX`），需通过 `build_onnx()` 解密
- NMS 算法会根据模型输出形状自动选择

### 3.6 screenshot_manager.py

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

- ❌ 不要移动或重命名 `core.py`（系统中枢）
- ❌ 不要修改 `buff.py` 的验证逻辑（已禁用但依赖其类导出）
- ❌ 不要在 `aim_bot_func()` 中添加阻塞操作
- ❌ 不要修改 `config.json` 的 `card_key` 字段结构

### 推荐做法

- ✅ 新功能优先在独立模块中实现，通过 `core.py` 集成
- ✅ 新配置项在 `build_config()` 和 `_init_config_handlers()` 中注册
- ✅ PID 参数变更通过 `refresh_controller_params()` 生效
- ✅ 瞄准逻辑修改在 `aim_pipeline.py` 中进行
- ✅ 新的推理格式支持在 `infer_function.py` 中添加 NMS 处理
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
| core.py 过大 | 高 | ~7400 行，应继续拆分 GUI/推理调度/设备管理 |
| 裸 except | 中 | 多处 `except Exception` 可能隐藏错误（core.py 约 139 处） |
| NMS 三种实现 | 低 | infer_function.py 中 nms_v8/nms_v5/nms 三种实现并存 |

### 已清理的历史债务

- ✅ `key2str` 重复定义 — 已统一至 `function.py`
- ✅ `buff.py` 死代码 — 已从 ~2500 行精简为 76 行存根
- ✅ 反编译痕迹 `# inserted` — 已全部清除
- ✅ 旧版瞄准逻辑冗余 — `aim_bot_func` 双路径已合并为 pipeline 单路径
- ✅ 旧版 `select_target_by_priority()` — 已从 core.py 移除，统一使用 aim_pipeline

---

## 10. 文件修改影响范围

| 修改文件 | 影响范围 |
|----------|----------|
| `aim_pipeline.py` | 瞄准精度、目标切换、预测 |
| `pid.py` | 鼠标移动平滑度、响应速度 |
| `bytetrack.py` | 目标跟踪稳定性、ID 一致性 |
| `infer_class.py` | 推理性能、模型兼容性 |
| `infer_function.py` | NMS 正确性、检测结果 |
| `screenshot_manager.py` | 截图延迟、内存使用 |
| `core.py` | **几乎所有功能** |
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
