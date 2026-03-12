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
├── main.py                  # 程序入口，异常处理、TensorRT 容错
├── core.py                  # 核心模块（~7800行），GUI + 主控制逻辑 + 配置管理
├── aim_pipeline.py          # 瞄准 Pipeline：目标选择、PID 控制、追踪、预测
├── pid.py                   # PID 控制器（单轴 + 双轴）
├── bytetrack.py             # ByteTrack 多目标跟踪器
├── infer_class.py           # ONNX / TensorRT 推理引擎封装
├── infer_function.py        # 推理辅助函数：NMS、框绘制、预处理
├── inference_engine.py      # TensorRT 推理引擎实现
├── screenshot_manager.py    # 截图管理：BetterCam / OBS / 采集卡
├── obs.py                   # OBS UDP 视频流接收
├── function.py              # 通用工具函数
├── gui_handlers.py          # GUI 事件处理、配置变更管理
├── profiler.py              # 帧性能分析器
├── decode_model.py          # 加密模型解密
├── v11onnx_support.py       # YOLOv11 ONNX 模型支持
├── v11onnx_benchmark.py     # YOLOv11 性能基准测试
├── buff.py                  # 网络验证 / 卡密系统（已禁用）
├── remote_config.py         # 远程配置管理（AES 加密通信）
├── server_config.py         # 服务器配置常量
├── server.py                # Web 控制面板（NiceGUI）
├── dhz.py                   # DHZ Box UDP 协议控制
├── catbox_wrapper.py        # CatBox 协议封装
├── cat/                     # CatBox 底层协议
│   ├── __init__.py
│   └── catnet_lite.py       # CatNetLite 虚拟模块
├── config/
│   └── color_range.json     # 颜色范围配置
├── cfg.json                 # 运行时配置文件
├── config.json              # 卡密配置
├── web/                     # Web 前端资源
├── tests/                   # 单元测试
│   ├── test_nms_v8_layout.py
│   ├── test_v11onnx_pipeline_integration.py
│   └── test_v11onnx_support.py
└── MD/                      # 文档
    └── V11ONNX_TEST_REPORT.md
```

---

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构说明
- [PIPELINE.md](PIPELINE.md) — 核心 Pipeline 数据流
- [MODULES.md](MODULES.md) — 模块详细说明
- [AI_CONTEXT.md](AI_CONTEXT.md) — AI 开发上下文
- [CHANGELOG.md](CHANGELOG.md) — 变更日志
