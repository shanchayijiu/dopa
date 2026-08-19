# -*- coding: utf-8 -*-
"""Valorant 主控装配包。

对外契约与包化前的 `core.py` 完全一致：`main.py` 的 `from core import *` 仍取到
同一批模块级名字（`Valorant`、`detect_inference_devices`、`auto_convert_engine`、
`global_exception_hook`，以及 `core.py` 顶层 import 引入的第三方与本地模块名）。

`__all__` 由 `valorant.py` 的模块级公开名字动态推导，与包化前的默认星号导入规则
逐名等价。显式设定它是为了排除 `mixins` / `runtime` / `valorant` 三个子模块名 ——
它们是包结构的产物，包化前不存在，不应泄入调用方命名空间。动态推导同时保证新增或
删除 valorant.py 的顶层名字会自动反映到包接口，无需同步维护清单。

布局：
    runtime.py   共享运行时事实（版本常量、DLL 注册、TensorRT 探测、渐变图）
    valorant.py  Valorant 主控类：配置装配中枢 + 运动执行环 + 生命周期编排
    mixins/      20 个 mix-in，按子系统分居

导入方向恒为 valorant -> mixins -> runtime，无环。禁止任何 mixin 反向导入
valorant，否则重建包化前那 5 处循环依赖。
"""

from . import valorant as _valorant
from .valorant import *  # noqa: F401,F403  (star-export contract, see docstring)
from .valorant import Valorant  # noqa: F401  (explicit: the primary entry point)

__all__ = [_n for _n in vars(_valorant) if not _n.startswith("_")]
