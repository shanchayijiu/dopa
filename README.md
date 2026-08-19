# DOPA3 — AI 辅助瞄准系统

## 项目概述

DOPA3 是一款基于深度学习目标检测的 AI 辅助瞄准系统，主要面向 FPS 游戏场景（如 CS2、Valorant 等）。系统通过屏幕截图实时捕获画面，使用 YOLO 系列模型（支持 v5/v8/v11、ONNX/TensorRT）进行目标检测，配合 ByteTrack 多目标跟踪、卡尔曼滤波预测、PID 控制器等算法，实现精确的目标定位与鼠标移动控制。

**版本**：v2.1.5  
**更新日期**：2025-11-04  
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
dopa3-1/
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
├── dll/  models/                # 驱动与模型文件
├── tests/                       # 单元测试（31 项）
└── docs/                        # 架构 / 流程 / 模块 / 安装文档
```

完整按模块分组与整理规划见 [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)。

---

## 相关文档

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构说明
- [PIPELINE.md](docs/PIPELINE.md) — 核心 Pipeline 数据流
- [MODULES.md](docs/MODULES.md) — 模块详细说明
- [AI_CONTEXT.md](docs/AI_CONTEXT.md) — AI 开发上下文
- [CHANGELOG.md](docs/CHANGELOG.md) — 变更日志
- [INSTALL.md](docs/INSTALL.md) — 安装与环境配置
- [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) — 项目结构与整理规划
