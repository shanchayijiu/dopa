# naoma — AI 辅助瞄准系统

## 项目概述

naoma 是一款基于深度学习目标检测的 AI 辅助瞄准系统，主要面向 FPS 游戏场景（如 CS2、Valorant 等）。系统通过屏幕截图实时捕获画面，使用 YOLO 系列模型（支持 v5/v8/v11、ONNX/TensorRT）进行目标检测，配合 ByteTrack 多目标跟踪、卡尔曼滤波预测、PID 控制器等算法，实现精确的目标定位与鼠标移动控制。

**版本**：v2.5  
**更新日期**：2026-09-11  
**开发团队**：HuiyeStudio

---

## 快速开始

### 环境要求

- Python 3.10+
- Windows 操作系统
- 支持的推理后端（按性能排序）：
  - TensorRT（NVIDIA GPU，最高性能）
  - CUDA（NVIDIA GPU）
  - DirectML（Windows GPU 通用）
  - CPU（默认兜底）

### 主要依赖

```
onnxruntime / onnxruntime-directml
opencv-python (cv2)
numpy
bettercam
dearpygui
pynput
pyclick
pydirectinput
scipy
cryptography
requests
kmNet
serial (pyserial)
```

### 启动方式

```bash
python main.py
```

程序会自动检测推理设备环境，优先选择最高性能后端，并启动 DearPyGui 图形界面。

### 输入设备支持

系统支持多种硬件移动方案：
- **km_net** — KM 网络盒子
- **km_box_a** — KM Box A
- **dhz** — DHZ Box（UDP 协议）
- **catbox** — Cat 协议设备
- **makcu** — MAKCU 控制器
- **pnmh** — PNMH 设备
- **send_input** — Windows SendInput
- **logitech** — 罗技驱动

---

## 项目结构

```
naoma/
├── main.py                      # 程序入口，异常处理、TensorRT 容错
├── conftest.py                  # 测试路径引导（使 pytest 可从任意目录调用）
│
├── core/                        # 主控装配包
│   ├── __init__.py              #   星号导出契约（109 个名字）
│   ├── valorant.py              #   Valorant 主控类（872 行）
│   ├── runtime.py               #   共享运行时事实
│   └── mixins/                  #   20 个 mix-in，按子系统分居
├── aim/                         # 瞄准逻辑
│   ├── aim_pipeline.py          #   目标选择、追踪关联、预测、控制装配
│   ├── pid.py                   #   PID 控制器（单轴 + 双轴）
│   ├── bytetrack.py             #   ByteTrack 多目标跟踪
│   └── crosshair_tracker.py     #   准星找色跟踪
├── inference/                   # 推理链路
│   ├── inference_engine.py      #   TensorRT 引擎实现
│   ├── infer_class.py           #   ONNX / TensorRT 引擎封装
│   ├── infer_function.py        #   NMS、预处理、框绘制
│   ├── v11onnx_support.py       #   YOLOv11 ONNX 支持与校验
│   ├── v11onnx_benchmark.py     #   YOLOv11 性能基准
│   ├── cuda_compat.py           #   CUDA / TensorRT 兼容层
│   └── decode_model.py          #   加密模型解密
├── devices/                     # 外设与采集
│   ├── screenshot_manager.py    #   截图源：BetterCam / OBS / 采集卡
│   ├── obs.py                   #   OBS UDP 视频流接收
│   ├── dhz.py                   #   DHZ Box UDP 协议
│   ├── catbox_wrapper.py        #   CatBox 协议封装
│   └── flashbang_handler.py     #   闪光弹检测
├── settings/                    # 配置与授权
│   ├── config_manager.py        #   默认配置、cfg.json 读写
│   ├── remote_config.py         #   远程配置（AES 加密通信）
│   ├── server_config.py         #   服务器配置常量
│   └── buff.py                  #   网络验证 / 卡密（已禁用）
├── webui/                       # Web 控制面板
│   └── server.py                #   NiceGUI 面板
├── util/                        # 通用工具
│   ├── function.py              #   按键名转换等
│   ├── gui_handlers.py          #   GUI 事件与配置变更框架
│   ├── diagnostics.py           #   异常记录
│   └── profiler.py              #   帧性能分析
├── cat/                         # CatBox 底层协议
│   └── catnet_lite.py           #   CatNetLite 虚拟模块
├── sim/                         # 单机合成靶场（测试/调参，独立于主程序）
│   ├── virtual_game.py          #   虚拟游戏：小窗口渲染 + 相机 + 虚拟鼠标后端
│   ├── motion.py                #   目标运动模型（bounce/brownian/teleport/blink/orbit）
│   ├── range_server.py          #   网页靶场服务（WS + overlay + 真值日志）
│   ├── launch_range.py          #   起服务并全屏打开靶场页面
│   ├── replay.py / metrics.py   #   闭环回放与锁定质量指标
│   ├── analyze.py               #   真值 vs 检测离线比对
│   ├── make_320_model.py        #   由 640 现成权重生成 320 YOLOv8n ONNX
│   └── static/                  #   靶场网页（HTML/JS/CSS + 球精灵）
├── tools/                       # 调试/调参脚本
│   ├── lock_quality.py          #   锁定质量量化（mean/std/振荡/命中）
│   ├── target_switch_test.py    #   多目标切换统计
│   ├── track_speed_sweep.py     #   速度扫描
│   ├── blink_lock_test.py       #   瞬移重锁测试
│   └── real_track_demo.py       #   真模型闭环演示（出视频）
│
├── cfg.json                     # 运行时配置（程序会写回）
├── config.json                  # 卡密配置
├── presets/color_range.json     # 颜色范围预设
├── km.dll / logitech.dll        # 输入设备驱动（按裸文件名加载，勿移动）
├── kmNet.cp310-win_amd64.pyd    # 本地编译 KM 模块（3.10 专用）
├── pykm2.pyc                    # 预编译 KM 模块
├── requirements.txt             # 依赖清单
├── run.bat                      # 启动脚本
├── assets/                      # 界面字体、图片
├── dll/  models/                # 驱动与模型文件（含 yolov8n_320.onnx 球模型）
├── tests/                       # 单元测试（73 项）
└── docs/                        # 架构 / 流程 / 模块 / 安装文档
```

完整按模块分组与整理规划见 [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)。

---

## 移动靶追踪与调参

追踪链路：`截图 → YOLO → NMS → ByteTrack → 目标选择 → Kalman 前馈 → PID → 量化 → 鼠标移动`。
静止目标靠 PID 即可；**移动目标靠 Kalman 前馈（提前量）**。

主要参数（GUI：`PID控制器参数` 页）：

- **目标跟踪 (ByteTrack)**：`启用跟踪器`（必须开，否则目标 id 每次变动、锁定失效）、`IoU匹配阈值`、`丢失保留帧数`
- **移动预测**：`启用移动预测`、`预测系数`（提前量≈帧数×8ms）、`预测增益`（1 鼠标计数=多少像素，需按灵敏度标定）、`启用前馈速度`、`最大前馈`、`前馈平滑`
- **目标选择器**（抑制多目标频繁切换）：`目标黏性`、`锁定时间`、`目标ID强锁定`、`目标转移延迟`

### 单机靶场（不依赖真实游戏）

```bash
# 起网页靶场（全屏，小窗口可缩放）
python -m sim.launch_range --size 320 --mode bounce --count 1
# 或跑原生 app + 虚拟游戏（不动真实鼠标）：见 tools/run_virtual_test.py
```

### 调参与验证

```bash
python -m pytest tests -q                                   # 回归
python tools/lock_quality.py --motion orbit --speed 300     # 锁定质量(mean/std/命中)
python tools/target_switch_test.py --count 3 --speed 180    # 多目标切换次数
python tools/track_speed_sweep.py --speeds 150,300,450,600  # 速度扫描
python tools/blink_lock_test.py --blink-interval 2.5        # 瞬移重锁
```

> 双机链路（A 机推流 → B 机 OBS/采集卡接收 + 盒子控鼠标）不受靶场影响，靶场仅用于单机调试。

---

## 相关文档

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构说明
- [PIPELINE.md](docs/PIPELINE.md) — 核心 Pipeline 数据流
- [MODULES.md](docs/MODULES.md) — 模块详细说明
- [AI_CONTEXT.md](docs/AI_CONTEXT.md) — AI 开发上下文
- [CHANGELOG.md](docs/CHANGELOG.md) — 变更日志
- [INSTALL.md](docs/INSTALL.md) — 安装与环境配置
- [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) — 项目结构与整理规划
