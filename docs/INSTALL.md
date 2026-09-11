# naoma 安装说明

> 本文档记录在干净 Windows x64 环境上复现 naoma 运行环境的完整步骤。
> 已验证版本：Python 3.10.20，2026-08-06。

---

## 一、环境要求

- **操作系统**：Windows x64
- **Python 版本**：**必须 3.10**（不可用 3.11+）
  - 原因：项目内置 `kmNet.cp310-win_amd64.pyd`、`pykm2.pyc` 为 CPython 3.10 专用编译，换其他版本会 `ImportError`。
- **GPU**（可选）：
  - NVIDIA GPU → 可装 TensorRT 走最高性能路径（缺省自动降级 ONNX，不影响运行）。
  - 无独显 → 走 ONNX Runtime DirectML 或 CPU。

---

## 二、安装步骤

### 方法 A：uv 一键安装（推荐）

`uv` 可自动下载管理 Python 3.10，无需系统预装。

1. 安装 uv（若未装）：

   ```powershell
   # Windows PowerShell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. 下载并准备 Python 3.10（首次较慢，约 1-2 分钟）：

   ```powershell
   uv python install 3.10
   ```

3. 在项目目录创建虚拟环境并安装依赖：

   ```powershell
   cd C:\path\to\dopa
   uv venv --python 3.10 .venv
   uv pip install -r requirements.txt --python .venv\Scripts\python.exe
   ```

### 方法 B：手动 venv + pip

适用于已装好官方 Python 3.10 的情况。

```powershell
cd C:\path\to\dopa

# 用已装的 3.10 建虚拟环境
py -3.10 -m venv .venv

# 国内加速（可选）
.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

---

## 三、验证安装

```powershell
# 1. 确认 Python 版本为 3.10.x
.venv\Scripts\python.exe --version

# 2. 整链加载验证（与 main.py 入口等价）
.venv\Scripts\python.exe -c "from core import *; print('所有模块链加载成功')"

# 3. 跑自带测试（5 个用例应通过，1 个文件本身损坏会报 error，属项目历史问题）
.venv\Scripts\python.exe -m pytest tests\ -q --continue-on-collection-errors
```

预期：
- `python --version` 打印 `Python 3.10.x`。
- `from core import *` 打印欢迎横幅后输出「所有模块链加载成功」（约 15s，NiceGUI 初始化耗时）。
- pytest 输出 `5 passed, 1 error`。error 来自 `tests/test_v11onnx_support.py`（该文件第 29 行起内容损坏），与依赖无关。

---

## 四、可选依赖

以下依赖缺失不影响主程序启动，仅按需安装：

| 依赖 | 用途 | 安装命令 |
|------|------|----------|
| `tensorrt` | TensorRT GPU 推理（最高性能） | 见官方文档，需先装 CUDA Toolkit + cuDNN |
| `cupy` | CUDA Graph 加速 | `... cupy-cuda12x`（按 CUDA 版本） |
| `pycuda` | TensorRT 引擎备选 | `... pycuda` |
| `cjk_get` | 采集卡视频源 | 见项目方提供（非 PyPI 公开包） |
| `user_info_manager` | 远程用户信息同步 | 见项目方提供（非 PyPI 公开包） |

说明：
- 未装 TensorRT 时，`main.py` 会捕获异常并打印「将使用 ONNX 推理继续运行」，自动降级。
- `cjk_get` / `user_info_manager` 在代码中以 `try/except` 形式引用，缺失只跳过对应功能。

---

## 五、启动

双击项目根目录的 `run.bat` 即可启动，它自动用 `.venv` 的 Python 3.10 运行 `main.py`，崩溃时控制台窗口会停住显示错误。

命令行启动：

```powershell
.venv\Scripts\python.exe main.py
```

两种方式等价。程序自动检测推理设备（TensorRT > CUDA > DirectML > CPU），优先选最高性能后端，启动 DearPyGui 界面。

**重要**：不要直接双击 `main.py`。系统 `.py` 默认关联到系统 Python（3.13/3.14），与项目内置的 `kmNet.cp310-win_amd64.pyd`（3.10 专用）不兼容，会闪退。如需改关联，建议只为 naoma 单独指向 3.10，避免影响其他项目。

---

## 六、注意事项

- 旧 `.venv` 若指向已删除的 Python 路径会失效，需用 `uv venv --python 3.10 --clear .venv` 重建。
- `kmNet.cp310-win_amd64.pyd` 与 `pykm2` 互为不同模块，二者均为本地文件，不在 PyPI，随仓库分发，无需单独安装。
- 配置文件 `cfg.json` 为运行时状态，会被程序自动读写，请勿手工删除。
