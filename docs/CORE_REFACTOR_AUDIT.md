# core.py Mix-in 拆分审计

> **路径映射（2026-08-10）**：本报告记录扁平布局时期的审计过程，文内 `core.py` / `core_*.py` 路径按当时事实保留。现行布局为 `core/` 包，对应关系：`core.py` → `core/valorant.py`，`core_runtime.py` → `core/runtime.py`，`core_xxx.py` → `core/mixins/xxx.py`。结构与验收详见 `PROJECT_STRUCTURE.md`。

> 目标：按子系统把 `core.py` 拆为独立 mix-in 模块，每块拆完通过整链加载
> `from core import *` + pytest 验证，行为零回归。本文件固化拆分结果与验证证据。

## 1. 拆分总览

`Valorant` 主控类不变，改为多 mix-in 继承，所有 `.py` 仍留在根目录
（扁平 `from xxx import`，受 `kmNet.cp310-win_amd64.pyd` 的 Python 3.10 ABI 锁定）。
`core.py` 不移动、不重命名（`AI_CONTEXT.md` §8 绝对禁止条款）。

```python
class Valorant(VerifyMixin, DeviceMixin, InputListenerMixin, InferenceMixin, PerceptionMixin, TriggerMixin, ConfigMixin, ConfigPersistMixin, CrosshairUIMixin, DisplayMixin, GUIMixin, MouseReMixin, GameConfigMixin, MouseMaskMixin, FlashbangMixin, KeyBindMixin, InferConfigMixin, SystemConfigMixin, AimConfigMixin, PidTrackerMixin):
    ...
```

### 行数变化

| 文件 | 职责子域 | 最终行数 |
|------|----------|----------|
| `core.py` | 中枢：`__init__` 状态装配、`_change_callback`、运动执行环（`aim_bot_func`/`execute_move`/`_emit_move_rel`/`_execute_move_async`/`_try_crosshair_pull`/`get_current_aim_center`）、`down_func` 压枪、生命周期 `start`/`go`/`on_start_button_click`、跨切面 `close_screenshot`/`reset_down_status`/`_update_class_checkboxes` | 940 |
| `core_devices.py` | 设备：`init_mouse`、监听线程、断开、makcu 初始化与锁 | 693 |
| `core_input.py` | 输入监听：`_mouse_button_to_key`、`on_click`/`on_scroll`、`on_press`/`on_release`、`reset_target_lock`、`reset_pid`（pynput 回调层，由 core_devices 注册） | 174 |
| `core_perception.py` | 感知辅助：`update_crosshair_tracking`（预处理线程调用）、`screenshot`、`smooth_small_targets`（后两者零调用死代码，原样保留） | 70 |
| `core_inference.py` | 推理调度：`infer`、引擎刷新、引擎创建、队列清理、状态重置、v11onnx 准备 | 798 |
| `core_trigger.py` | 触发器：`trigger`/鼠标按下抬起/触发进程/后坐力起停 + 扳机配置回调（on_status/continuous/recoil/start/press/end/random_delay、x/y_trigger_scope/offset）、`update_rect` | 298 |
| `core_config.py` | 配置：`build_config`、类元数据初始化与迁移、参数刷新、配置处理器初始化 | 359 |
| `core_crosshair_ui.py` | 准星 UI：`on_crosshair_*` 回调、HSV、取色、小目标开关 | 321 |
| `core_gui.py` | GUI 构建：`gui()` 构建整个 DearPyGui 界面 + `switch_tab` 闭包 | 523 |
| `core_mousere.py` | 鼠标压枪轨迹：mouse_re 回调/导入/清空、JSON 解析、压枪回放线程、下拉渲染 | 300 |
| `core_gameconfig.py` | 游戏/枪械配置：render_*_combo、on_add/delete/game/gun/stage、on_x/y/number、refresh_stage | 119 |
| `core_mask.py` | 鼠标按键屏蔽：on_mask_(left/right/middle/side1/side2/x/y/wheel)、on_aim_mask_(x/y)，三设备分发 | 156 |
| `core_flash.py` | 自动背闪：on_auto_flashbang_*（启用/延迟/角度/灵敏度/回转/曲线/置信度/尺寸）、on_test_flashbang_(left/right)、on_flashbang_debug_info、update_auto_flashbang_ui_state + FlashbangHandler 委托层（_get_flashbang、detect_and_handle_flashbang、execute_flashbang_*） | 153 |
| `core_display.py` | 显示与 DPI：get_system_dpi_scale、get_dpi_aware_screen_size、update_combo_methods、update_target_reference_class_combo、get_gradient_color | 69 |
| `core_persist.py` | 配置持久化：get_default_config、read_local_cfg、save_config（异步远程）、on_save_button_click、on_change（ConfigChangeHandler 分发）、migrate_auto_y_config | 47 |
| `core_keybind.py` | 按键绑定：render_group/key_combo、on_key_change/update_key_inputs、分组增删改、类别多选 checkbox、start/stop_key_binding、_mouse_binding_poll、capture_key_press、on_key_binding_button_click/complete、init_class_aim_positions_for_key | 370 |
| `core_infercfg.py` | 推理配置：on_is_v8/auto_y/use_crosshair/right_down_change、init_target_priority、on_is_show_priority_debug/is_trt/show_infer_time/show_fov_change、get_trt/onnx/current_class_num、on_gui_dpi_scale_change、on_reset_dpi_scale_click | 232 |
| `core_systemcfg.py` | 系统配置：on_game_sens/mouse_dpi/web_server/inference_device/card/infer_debug/is_curve*/scoring_weight/print_fps/show_motion_speed/parallel/turbo/skip_frame/show_down/obs*/cjk*/obs_*/offset_boundary*/distortion*/target_points/km_box*/km_net*/dhz*/catbox*/km_com/move_method、get_local_ip、on_one_click_match | 307 |
| `core_aimcfg.py` | 瞄准配置：on_group_change、on_confidence_threshold/infer_model/select_model 调回、parse_class_priority、update_class_aim_combo/inputs、on_overshoot_*_factor_change、on_aim_*_key/_weight/_ratio_change、on_*_kicker_change 等 44 个回调 | 387 |
| `core_pidtracker.py` | PID 跟踪器配置：on_controller_type_change、on_pid_kp/kd/ki_*_change、on_smooth_*_change、on_tracker_enabled_change、on_kalman_enabled_change、_update_pid_params、_register_control_callback 等 26 个回调 | 104 |
| `core_verify.py` | 授权校验与模型解密：`start_verify_init`、`error_exit`、`verify`、`_decrypt_encrypted_model`、`_validate_onnx_data`、`_secure_cleanup`、`is_using_dopa_model`、`is_using_encrypted_model` | 196 |

**累计提取**：原始 `core.py` ≈6322 行 → **940 行**（保留 15 个方法），二十个 mix-in 共外移约 5382 行（**~85%**）。本轮（第四、五刀）新增 `InputListenerMixin`（174 行，7 方法）与 `PerceptionMixin`（70 行，3 方法），`core.py` 从 1085 行降至 940 行。上一轮新增 `DisplayMixin`（79 行）与 `ConfigPersistMixin`（59 行），并把背闪执行委托层 8 方法并入既有 `FlashbangMixin`。`VerifyMixin`（196 行）、`AimConfigMixin`（439 行）、`PidTrackerMixin`（134 行）、`SystemConfigMixin`（365 行）、`InferConfigMixin`（232 行）、`KeyBindMixin`（370 行）、`FlashbangMixin`（181 行）、`MouseMaskMixin`（156 行）、`GameConfigMixin`（121 行）、`MouseReMixin`（300 行）、`GUIMixin`（523 行）、`CrosshairUIMixin`（321 行）为先前拆分会话提取，并向 `TriggerMixin` 追加扳机配置回调与 `update_rect`；`core_devices`/`core_inference`/`core_trigger`/`core_config` 由最初会话提取。剩余 15 方法经审计判定不宜再拆，理由见 §4.22。

## 2. 各 Mix-in 关键方法

| Mix-in | 文件 | 代表方法 |
|---------|------|----------|
| DeviceMixin | `core_devices.py` | `init_mouse`, `start_listen_*`, `disconnect_device`, `unmask_all`, `_setup_makcu`, `_init_makcu_locks` |
| InputListenerMixin | `core_input.py` | `_mouse_button_to_key`, `on_click`, `on_scroll`, `on_press`, `on_release`, `reset_target_lock`, `reset_pid` |
| PerceptionMixin | `core_perception.py` | `update_crosshair_tracking`, `screenshot`（弃用薄壳，0 调用）, `smooth_small_targets`（已被 AimPipeline 三参版取代，0 调用）|
| InferenceMixin | `core_inference.py` | `infer`, `_harmonize_v8_boxes`, `refresh_engine`, `_create_engine_from_bytes`, `_clear_queues`, `_reset_aim_states`, `_prepare_v11onnx_group_model` |
| TriggerMixin | `core_trigger.py` | `trigger`, `mouse_left_down/up`, `trigger_process`, `continuous_trigger_process`, `start/stop_trigger_recoil`, `on_status_change`, `on_continuous_trigger_change`, `on_trigger_recoil_change`, `on_start_delay_change`, `on_long_press_duration_change`, `on_press_delay_change`, `on_end_delay_change`, `on_random_delay_change`, `on_x_trigger_scope_change`, `on_y_trigger_scope_change`, `on_x_trigger_offset_change`, `on_y_trigger_offset_change`, `update_rect` |
| ConfigMixin | `core_config.py` | `build_config`, `init_all_keys_class_aim_positions`, `migrate_config_to_class_based`, `refresh_controller_params`, `refresh_pressed_key_config`, `_init_config_handlers` |
| CrosshairUIMixin | `core_crosshair_ui.py` | `on_crosshair_*`（HSV/roi/pick/tolerance/color_group/show_*）, `handle_color_pick_hotkey`, `_format_rgb_text`, `_apply_hsv_to_sliders`, `update_crosshair_hsv_ui`, `on_small_target_*`, `on_small_pixel_threshold_change` |
| GUIMixin | `core_gui.py` | `gui()`（构建整个 DearPyGui 视口 + 嵌套 `switch_tab` 闭包切换 tab）|
| MouseReMixin | `core_mousere.py` | `update_mouse_re_ui_status`, `on_*mouse_re*`, `_parse_mouse_re_json`, `_recoil_replay_worker`, `render_mouse_re_*` |
| GameConfigMixin | `core_gameconfig.py` | `render_games_combo`, `render_guns_combo`, `render_stages_combo`, `on_add/delete/game/gun/stage_*`, `on_x/y/number_change`, `on_games/guns/stages_change`, `refresh_stage` |
| MouseMaskMixin | `core_mask.py` | `on_mask_(left/right/middle/side1/side2/x/y/wheel)_change`, `on_aim_mask_(x/y)_change` |
| FlashbangMixin | `core_flash.py` | `on_auto_flashbang_*`（enabled/delay/angle/sensitivity/return_delay/curve*/min_confidence/min_size）, `on_test_flashbang_(left/right)`, `on_flashbang_debug_info`, `update_auto_flashbang_ui_state`, `_get_flashbang`, `detect_and_handle_flashbang`, `execute_flashbang_turn/return/curve_move*/ultra_fast_move` |
| DisplayMixin | `core_display.py` | `get_system_dpi_scale`, `get_dpi_aware_screen_size`, `update_combo_methods`, `update_target_reference_class_combo`, `get_gradient_color` |
| ConfigPersistMixin | `core_persist.py` | `get_default_config`, `read_local_cfg`, `save_config`, `on_save_button_click`, `on_change`, `migrate_auto_y_config` |
| KeyBindMixin | `core_keybind.py` | `render_group_combo`, `render_key_combo`, `on_key_change`, `update_key_inputs`, `update_group_inputs`, `create/remove_checkboxes`, `on_checkbox_change`, `on_add/delete_group/key_click`, `start/stop_key_binding`, `_mouse_binding_poll`, `capture_key_press`, `on_key_binding_button_click/complete`, `init_class_aim_positions_for_key` |
| InferConfigMixin | `core_infercfg.py` | `on_is_v8_change`, `on_auto_y_change`, `on_use_crosshair_change`, `on_right_down_change`, `init_target_priority`, `on_is_show_priority_debug_change`, `on_is_trt_change`, `on_show_infer_time_change`, `on_show_fov_change`, `get_trt/onnx/current_class_num`, `on_gui_dpi_scale_change`, `on_reset_dpi_scale_click` |
| SystemConfigMixin | `core_systemcfg.py` | `on_game_sensitivity_change`, `on_mouse_dpi_change`, `on_web_server_change`, `on_inference_device_change`, `update_sensitivity_display`, `calculate_sensitivity_multiplier`, `on_card_change`, `on_infer_debug_change`, `on_is_curve*/scoring_weight_change`, `on_print_fps/show_motion_speed/is_show_curve/parallel/turbo/skip_frame/show_down_change`, `on_is_obs/cjk*/obs_ip/device_id/fps/resolution/crop_size/fourcc_change`, `get_local_ip`, `on_one_click_match`, `on_obs_fps/port_change`, `on_offset_boundary*/knots_count/distortion*/target_points_change`, `on_km_box*/km_net*/dhz*/catbox*/km_com/move_method_change` |
| AimConfigMixin | `core_aimcfg.py` | `on_group_change`, `on_confidence_threshold_change`, `on_infer_model_change`, `on_select_model_click`, `parse_class_priority`, `format_class_priority`, `get_class_priority`, `update_class_aim_combo`, `update_class_aim_inputs`, `on_overshoot_x/y_factor_change`, `on_aim_*_key/weight/ratio_change`, `on_*_kicker_change` |
| PidTrackerMixin | `core_pidtracker.py` | `on_controller_type_change`, `on_pid_kp/kd/ki_*_change`, `on_smooth_x/y_change`, `on_tracker_enabled_change`, `on_kalman_enabled_change`, `_update_pid_params`, `_register_control_callback` |
| VerifyMixin | `core_verify.py` | `start_verify_init`, `error_exit`, `verify`, `_decrypt_encrypted_model`, `_validate_onnx_data`, `_secure_cleanup`, `is_using_dopa_model`, `is_using_encrypted_model` |

留在 `core.py` 的运行态方法（非 UI 回调）：运动执行环 `aim_bot_func`、`execute_move`、
`_emit_move_rel`、`_execute_move_async`、`_try_crosshair_pull`、`get_current_aim_center`，
压枪 `down_func`，生命周期 `start`/`go`/`on_start_button_click`，以及配置装配中枢
`__init__`/`_change_callback`。完整清单与不拆理由见 §4.22。

全部 `on_*_change` 按钮回调通过 `_change_callback` 的 `getattr(self, f'on_{parts[0]}_change')`
动态派发，不依赖模块位置——这是各 mix-in 能自由承接回调的前提。

## 3. 约束与全局符号

- `core.py` 顶部先完成 `TENSORRT_AVAILABLE` / `TensorRTInferenceEngine` /
  `ensure_engine_from_memory` 的检测与赋值，再定义 `class Valorant`。各 mix-in 用
  `from core import TENSORRT_AVAILABLE, ...` 延迟导入，此时 core 已完成检测、尚未
  定义类，安全。
- `v11onnx_support`、`remote_config`、`catbox_wrapper`、`kmNet`、`infer_function` 等
  被 mix-in 直接引用的依赖，必须在各自 mix-in 文件顶部显式 import——不能再隐式依赖
  `core.py` 的模块级 import（提取时这些依赖若不同步，会在运行期才暴露 NameError，
  见 §4）。
- 读取 `core.py` 必须用 `utf-8-sig`（带 BOM）；Python venv 为 CPython 3.10（由 `uv` 安装）。
- `VerifyMixin` 需读 `core.TENSORRT_AVAILABLE`，但它被 `core.py` 反引用（`Valorant` 首个基类），
  导入期 `from core import TENSORRT_AVAILABLE` 会形成循环。改为模块内 `_tensorrt_available()`
  在调用时 `import core` 并 `getattr` 读取，既避开循环又不做导入期快照。

## 4. 验收

### 4.1 静态

`from core import *` 成功；MRO 正确：
```
Valorant -> DeviceMixin -> InferenceMixin -> TriggerMixin -> ConfigMixin -> CrosshairUIMixin -> object
```
方法定位抽检：准星 UI 回调落在 `CrosshairUIMixin`；`update_crosshair_tracking`、
`_try_crosshair_pull`、`aim_bot_func` 留在 `core`；`init_mouse/infer/trigger/build_config`
分属各自 mix-in。全部无 `NOT_FOUND`。

### 4.2 运行态（关键）

**发现**：前序会话仅用 `from core import *` 加 import 检查，只验证类能否导入，
**从不实例化 `Valorant()`**，因此无法发现 mix-in 内对「core 顶层已 import、但 mix-in
未 import」符号的引用。实启 `main.py` 时一进入 `__init__ -> build_config()` 即
`NameError`。此为前序提取遗留的真实回归，非本会话引入。本会话补齐。

补充的缺失 import（经 AST 扫描「被 Load 但从未本地绑定且未在文件顶层 import」+逐个
溯源到 `core.py` 的 import / 定义定位后确认）：

| 文件 | 补充 import |
|------|------------|
| `core_config.py` | `should_use_v11onnx`, `infer_model_variant_from_path`（均 `v11onnx_support`）, `TENSORRT_AVAILABLE`（`from core import`）, `random` |
| `core_devices.py` | `ctypes`（裸用 `ctypes.c_ushort`，原来只 import 了 `CDLL, windll`） |
| `core_inference.py` | `nms`（`infer_function`）, `import queue`, `validate_v11onnx_model`（`v11onnx_support`）, `save_remote_config`（`remote_config`） |
| `core_trigger.py` | `import ctypes`, `import kmNet`, `import pydirectinput`, `import queue`, `catbox_left_down`, `catbox_left_up`（`catbox_wrapper`），`import dearpygui.dearpygui as dpg`（`update_rect`） |

排除的误报（AST 扫到但实为嵌套 `def`/嵌套 `class`/方法内局部 import）：
`_makcu_sender_worker`、`move_enqueue`、`parse_mouse_button`、`DecryptedModelEngine`、
`_async_save_callback`、`_capture_and_preprocess`、`rt`（`import onnxruntime as rt`）、
`warnings`、`traceback`（均为方法内 `import`）。已逐条 grep 确认。

`core_crosshair_ui.py`（本会话提取）AST 扫描 clean，无缺失。

### 4.3 GUI 实启

`main.py` 启动后进程持续运行 9 秒未退出，`error_log.txt` 为空（事件循环正常拉起，
无运行期异常）。

### 4.4 pytest

```
5 passed, 1 error in 0.66s
```
`1 error` 来自 `tests/test_v11onnx_support.py:29` 的 `class 0100` 语法坏文件，
为**重构前已存在**的预存损坏，与本轮拆分无关。

### 4.5 GUIMixin 拆分验证（后续会话）

**提取目标**：`gui()` 方法（L1203-1709，507 行）+ 其内部嵌套 `switch_tab` 闭包（433 行）。
所有 dpg 回调通过 `self.on_xxx` 绑定（继承可达），`switch_tab` 作为本地闭包随块搬移。

**模块级依赖**：`random`、`string`、`dpg`（顶部 import）+ `create_gradient_image`、`VERSION`、
`UPDATE_TIME`（`from core import` 延迟导入）——经 AST 扫描确认后纳入 header。

**验证结果**：
- `from core import *` + MRO 正确（GUIMixin 末位）：`Valorant -> Device -> Inference -> Trigger -> Config -> CrosshairUI -> GUI -> object`
- 方法定位：`gui -> GUIMixin`（core.py `__dict__` 己不含）；`switch_tab` 为其内部闭包
- AST 扫描：仅 `switch_tab` 误报（嵌套 def，不在绑定计数内），无真缺失 import
- 实启 `main.py` 9 秒进程未退出，`error_log.txt` 为空（GUI 构建期无异常）
- pytest：`5 passed, 1 error`（基线不变）

### 4.6 MouseReMixin 拆分验证（后续拆分会话）

**提取目标**：mouse_re 轨迹压枪区块（L1343-1628，286 行，15 个方法），从
`update_mouse_re_ui_status` 到 `on_mouse_re_guns_change`。该区块在 `gui()` 构建期由
`core_gui.py:516` 调用 `update_mouse_re_ui_status()`，启动期即被动态调用。

**模块级依赖**：`json`、`time`、`threading`（回放线程）、`dpg`（状态面板刷新）——
纳入 header。AST 扫描出的 `filedialog`/`tk`/`traceback` 均为方法内局部 import（误报）。

**验证结果**：
- `from core import *` + MRO 正确（MouseReMixin 末位）：`... CrosshairUI -> GUI -> MouseRe -> object`
- 方法定位：`update_mouse_re_ui_status`/`_recoil_replay_worker`/`render_mouse_re_games_combo` 均在 MouseReMixin
- AST 扫描：`filedialog`/`tk`/`traceback` 均为方法内 `from tkinter import` / `import traceback` （误报）
- 实启 `main.py` 9 秒进程未退出，`error_log.txt` 为空；stderr 仅含上游预存的 font_range_hint 弃用警告

### 4.7 GameConfigMixin 拆分验证（后续拆分会话）

**提取目标**：gameconfig 区块（L2590-2696，107 行，18 个方法），从
`render_games_combo` 到 `refresh_stage`。该区块在 `gui()` 构建期由 `core_gui.py:267/273/279`
调用 `render_*_combo`，启动期即被动态调用。`reset_down_status`/`close_screenshot` 跨切面方法留在 core.py。

**模块级依赖**：仅 `dpg`。无方法内局部 import，AST 扫描无不安全名字。

**验证结果**：
- `from core import *` + MRO 正确（GameConfigMixin 末位）：`... GUI -> MouseRe -> GameConfig -> object`
- 方法定位：`render_*`/`refresh_stage`/`on_add_game_click` 均在 GameConfigMixin；`reset_down_status`/`close_screenshot` 仍在 core
- AST 扫描：无真缺失 import（块内无方法内局部 import）
- 实启 `main.py` 9 秒进程未退出，`error_log.txt` 为空（gui构建期 render_*_combo 动态运行）
- pytest：`5 passed, 1 error`（基线不变）

### 4.8 MouseMaskMixin 拆分验证（后续拆分会话）

**提取目标**：mask 区块（L2606-2747，142 行，10 个方法），
8 个 `on_mask_*` + 2 个 `on_aim_mask_*` 回调。根据 `self.config['move_method']`
分发到 `kmNet` / `catbox` / `self.dhz` 三种输入设备的屏蔽接口；本 mix-in 直接
`import kmNet` 与 `from catbox_wrapper import catbox`，`self.dhz` 由 init_mouse 在启动期创建。

**模块级依赖**：`catbox`、`kmNet`（AST 扫描出三设备裸名中的两个真依赖）；无 `dpg` 使用
（纯输入设备屏蔽逻辑，非 GUI 控件）；无方法内局部 import。`reset_down_status`/`close_screenshot`
在上一块（gameconfig）中判为跨切面，留在 core.py。

**验证结果**：
- `from core import *` + MRO 正确（MouseMaskMixin 末位）：`... MouseRe -> GameConfig -> MouseMask -> object`
- 方法定位：`on_mask_*`/`on_aim_mask_y_change` 均在 MouseMaskMixin；`reset_down_status`/`close_screenshot` 仍在 core
- AST 扫描：三个设备裸名 (`catbox`/`kmNet`/`self.dhz`) — 前两者 纳入 header import，后者为实例属性
- 实启 `main.py` 9 秒进程未退出，`error_log.txt` 为空（`import kmNet`/`from catbox_wrapper import catbox` 在 import 期生效无误）
- pytest：`5 passed, 1 error`（基线不变）

### 4.9 FlashbangMixin 拆分验证（后续拆分会话）

**提取目标**：自动背闪回调区块（L1376-1508，133 行，14 个方法），从
`on_auto_flashbang_enabled_change` 到 `update_auto_flashbang_ui_state`。纯 dpg 控件回调，
通过 `_change_callback` 的 `getattr(self,'on_auto_flashbang_*')` 派发；每个回调以
`self.is_using_dopa_model()` 守卫（仅 ZTX 模型可用），写 `self.config['auto_flashbang']`。
背闪执行链 `_get_flashbang`/`detect_and_handle_flashbang`/`execute_flashbang_*` 跨推理/运动切面，
留在 `core.py`（被 `core_inference.py` 与运动逻辑调用）。

**模块级依赖**：无。`time`、`dearpygui.dearpygui as dpg` 均为方法内局部 import；
其余仅 `self.*` 实例属性。AST 扫描 clean。

**验证结果**：
- `from core import *` + MRO 正确（FlashbangMixin 末位）：`... GameConfig -> MouseMask -> Flashbang -> object`
- 方法定位：`on_auto_flashbang_enabled_change`/`on_test_flashbang_left`/`on_flashbang_debug_info`/`update_auto_flashbang_ui_state` 均在 FlashbangMixin
- AST 扫描：无缺失模块级 import（方法内局部 import 不计入）
- 实启 `main.py` 9 秒存活（4s 与 9s 均 alive），`error_log.txt` 为空（背闪回调启动期不被调用）
- pytest：`5 passed, 1 error`（基线不变，`class 0100` 预存损坏无关）

### 4.10 TriggerMixin 扩展（扳机配置回调 + update_rect，后续拆分会话）

**提取目标**：扳机配置回调整块（L2034-2095，13 个方法，63 行）并入既有
`core_trigger.py` 的 `TriggerMixin`（不新建文件）。含 12 个 `on_*_trigger*/return*/delay*_change`
回调 + `update_rect`。回调写 `self.config['groups'][self.group]['aim_keys']
[self.select_key]['trigger']`；`x/y_trigger_scope/offset` 四回调动调 `self.update_rect()`
重绘 `'small_rect'`。`update_rect` 不新建文件，与扳机执行同属 trigger 域——
keybind 块（后续）的 `on_key_change` 仍通过继承调用。

**模块级依赖**：在 `core_trigger.py` 顶部补 `import dearpygui.dearpygui as dpg`
（`update_rect` 裸用 `dpg.configure_item`）。后半模块级依赖不变。AST 扫描 clean。

**验证结果**：
- MRO 未变（`TriggerMixin` 已在继承列表，未新增/重排）
- 方法定位：`on_status_change`/`on_y_trigger_offset_change`/`update_rect` 均在 TriggerMixin；core.py 主体不再含这些 def
- AST 扫描 `core_trigger.py`：无缺失模块级 import（`dpg` 已补）
- 实启 `main.py` 9 秒存活（4s 与 9s 均 alive），`error_log.txt` 为空（回调启动期不被调用、update_rect 同理）
- pytest：`5 passed, 1 error`（基线不变）

### 4.11 KeyBindMixin 拆分验证（后续拆分会话）

**提取目标**：按键绑定区（L2034-2375，22 个方法，342 行），从 `render_group_combo`
到 `init_class_aim_positions_for_key`。该区在 `gui()` 构建期由 `core_gui.py:311/332/497`
调用 `render_group_combo`/`render_key_combo`/`update_group_inputs`，启动期即被动态调用。
`capture_key_press` 含一段重复的回吊块（前序遗留，非本次引入，未修改）。

**模块级依赖**：`time`（start_key_binding/_mouse_binding_poll）、`threading`（绑定轮询线程）、
`copy`（on_key_binding_complete deepcopy）、`win32api`/`win32con`（GetAsyncKeyState/VK_*）、
`dpg`（面板刷新）、`key2str`（`from function`）均纳入 header。AST 扫描 clean。
跨 mix-in 调用（`update_rect`→TriggerMixin、`update_class_aim_combo`/`update_target_reference_class_combo`→core）
均经 self. 继承可达，无模块级裸依赖。

**验证结果**：
- `from core import *` + MRO 正确（KeyBindMixin 末位）：`... MouseMask -> Flashbang -> KeyBind -> object`
- 方法定位：14/14 抽检方法（render_*、on_key_change、start/stop_key_binding、capture_key_press、on_key_binding_*、init_class_aim_positions_for_key 等）均在 KeyBindMixin
- AST 扫描：无缺失模块级 import（win32api/win32con/key2str/copy/time/threading/dpg 均已补）
- 实启 `main.py` 9 秒存活（4s 与 9s 均 alive），`error_log.txt` 为空（render_group_combo 等在 gui() 构建期运行动态无异常）
- pytest：`5 passed, 1 error`（基线不变）


### 4.12 InferConfigMixin 拆分验证（后续拆分会话）

**提取目标**：推理配置区，分两段非连续区块（被 `reset_down_status`/`close_screenshot`
跨切面方法隔断）：段 A L2035-2055（5 回调 + `init_target_priority`），段 B L2071-2257
（4 回调 + `get_trt/onnx/current_class_num` + DPI 2 回调）。复位与截图管理留在 core。
`on_is_trt_change` 体含 TRT 模式切换与引擎刷新逻辑，调用 `self.refresh_engine()`/`self.create_checkboxes()`。

**模块级依赖**：`os`（TRT 路径拼接/存在性检查）、`dpg`（控件刷新）、`Timer`（错误消息延迟移除）、
`TENSORRT_AVAILABLE`（`from core import` 延迟导入）均纳入 header。AST 扫描 clean。
跨 mix-in 调用（`refresh_engine`→InferenceMixin、`create_checkboxes`/`update_class_aim_combo`→core）经 self. 继承可达。

**验证结果**：
- `from core import *` + MRO 正确（InferConfigMixin 末位）：`... Flashbang -> KeyBind -> InferConfig -> object`
- 方法定位：14/14 抽检方法均在 InferConfigMixin；`reset_down_status`/`close_screenshot` 正确留在 core
- AST 扫描：无缺失模块级 import（os/dpg/Timer/TENSORRT_AVAILABLE 均已补）
- 实启 `main.py` 9 秒存活（4s 与 9s 均 alive），`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）


### 4.13 SystemConfigMixin 拆分验证（后续拆分会话）

**提取目标**：系统与输入设备配置区（L1287-1624，337 行，57 个方法），从
`on_game_sensitivity_change` 到 `on_move_method_change`。含灵敏度/DPI/Web服务器/推理设备/
卡密/调试/曲线/评分权重/并行处理/turbo/跳帧/显示下载/OBS/CJK 采集目标对比/本地IP/一键匹配/
偏移边界/网格控制点数/畸变参数/观测目标总点数/输入设备 kmBox·kmNet·dhz·catbox 配置。
均纯写 self.config + 触发 save_config/refresh_engine/start_web_server。

**模块级依赖**：`socket`（get_local_ip）、`dpg`（控件刷新）、`start_web_server`（
`from server` 带 try/except 兑底为 None）。`threading`/`time` 为 `on_one_click_match` 内局部 import，
非模块级。AST 扫描 `start_web_server` 为涸报（所在 except 块外不被扫描器收录，实际已模块级绑定）。

**验证结果**：
- `from core import *` + MRO 正确（SystemConfigMixin 末位）：`... KeyBind -> InferConfig -> SystemConfig -> object`
- 方法定位：10/10 抽检方法（on_game_sens/web_server/inference_device/get_local_ip/on_one_click_match/on_km_net_ip/on_move_method 等）均在 SystemConfigMixin
- 实启 `main.py` 9 秒存活（4s 与 9s 均 alive），`error_log.txt` 为空（系统配置回调启动期不被调用）
- pytest：`5 passed, 1 error`（基线不变）

### 4.14 AimConfigMixin 拆分验证（后续拆分会话）

**提取目标**：瞄准配置区（L1288-1698 in pre-extraction core.py，387 行，44 个方法），从
`on_group_change` 到 `on_overshoot_y_factor_change`。含分组切换、置信度阈值、推理模型
选择、类别优先级 parse/format、类别瞄准参数（各轴 kicker/weight/ratio）、超调因子等
UI 回调。`reset_down_status`/`close_screenshot`/`on_change` 三个跨切面方法留在 core.py。

**模块级依赖**：`dpg`、`os`（on_infer_model_change/on_select_model_click 的路径判断）、
`infer_model_variant_from_path`（`from v11onnx_support`）。其余为 `self.*` 实例属性与
`self.config` 写入。`tkinter`/`re`/`traceback` 为方法内局部 import，非模块级。

**验证结果**：
- `from core import *` + MRO 正确（AimConfigMixin 倒数第二位）：`... InferConfig -> SystemConfig -> AimConfig -> PidTracker -> object`
- 方法定位：7/7 抽检方法（on_group_change、on_confidence_threshold_change、on_infer_model_change、on_select_model_click、parse_class_priority、update_class_aim_combo、on_overshoot_y_factor_change）均在 AimConfigMixin
- AST 扫描：**首轮查出 2 处真缺失** —— `os`（4 处调用）与 `infer_model_variant_from_path`（1 处），
  两者均只在「选择模型」交互路径上触发，启动期不执行，故实启验证无法暴露；已补入模块头 import 后复扫 clean
- 实启 `main.py` 10 秒存活（5s 与 10s 均 alive），`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.15 PidTrackerMixin 拆分验证（后续拆分会话）

**提取目标**：PID 跟踪器配置区，分两段非连续区块（被 `reset_down_status`/
`close_screenshot`/`on_change` 三个跨切面方法隔断）：段 A L1718-1768
（on_controller_type_change 等初始回调）、段 B L1780-1830（on_pid/smooth/tracker/kalman +
`_update_pid_params`/`_register_control_callback`）。104 行，26 个方法。

**模块级依赖**：仅 `dpg`。`reset_controller_params`/`refresh_controller_params` 经 self. 继承
可达。AST 扫描 clean。

**验证结果**：
- `from core import *` + MRO 正确（PidTrackerMixin 末位）：`... SystemConfig -> AimConfig -> PidTracker -> object`
- 方法定位：7/7 抽检方法（on_controller_type_change、on_pid_kp_x_change、on_smooth_x_change、on_tracker_enabled_change、on_kalman_enabled_change、_update_pid_params、_register_control_callback）均在 PidTrackerMixin
- AST 扫描：无缺失模块级 import
- 实启 `main.py` 9 秒存活（5s 与 9s 均 alive），`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.16 VerifyMixin 拆分验证（后续拆分会话）

**提取目标**：授权校验与模型解密组，8 个方法、158 行，分三段非连续区块（`start_verify_init`
到 `_validate_onnx_data`、`_secure_cleanup`、文件末尾的 `is_using_dopa_model`/
`is_using_encrypted_model`）。选它的依据是内聚度：组内互调 3 处，仅向外借
`_update_class_checkboxes` 与 `refresh_engine` 两个方法，且 core.py 内无其他方法调用本组。

**跨模块调用面**：`is_using_dopa_model` 被 `core_flash.py`（14 处）、`core_inference.py`（2 处）、
`core_gui.py`（1 处）调用；`_decrypt_encrypted_model` 被 `core_aimcfg.py`（2 处）调用；
`_secure_cleanup` 被 `main.py` 以 `valorant_instance._secure_cleanup()` 调用。全部走 `self.`
或实例属性，经 MRO 继承可达，拆分不影响。

**模块级依赖**：`dpg`、`build_model`（`from decode_model`）。`TENSORRT_AVAILABLE` 走
`_tensorrt_available()` 运行时读取（见 §3）。`onnxruntime`/`pycuda.driver`/`cuda_compat`
为方法内局部 import，保持原样。

**MRO 位置**：置于**首位**（`VerifyMixin, DeviceMixin, ...`）。本组无同名方法与其他 mix-in
冲突，首位与末位等价；选首位是为呼应它在生命周期中的前置语义。

**验证结果**：
- 抽取用 AST 方法边界（`lineno`/`end_lineno`）而非硬编码行号，规避多段删除的行号漂移
- 边界检查：类体最后一个方法之后紧跟模块级 import，属合法边界，已放宽判定条件
- `from core import *` + MRO 正确：`Valorant -> VerifyMixin -> DeviceMixin -> ... -> PidTrackerMixin -> object`
- 方法定位：8/8 在 VerifyMixin，`core.Valorant.__dict__` 无残留重复
- AST 扫描 clean；`_tensorrt_available()` 返回值与 `core.TENSORRT_AVAILABLE` 一致
- 实启 `main.py` 10 秒存活（5s 与 10s 均 alive），`error_log.txt` 为空，stderr 仅一条既有的
  dearpygui `add_font_range_hint` 弃用警告
- pytest：`5 passed, 1 error`（基线不变）

### 4.17 FlashbangMixin 扩展（背闪执行委托层，后续拆分会话）

**提取目标**：`core.py` 中的 8 个背闪执行方法（`_get_flashbang`、
`detect_and_handle_flashbang`、`execute_flashbang_turn/return`、
`execute_flashbang_curve_move`、`execute_flashbang_curve_move_fast`、
`execute_flashbang_curve_move_with_tracking`、`execute_flashbang_ultra_fast_move`），
并入既有 `core_flash.py`（不新建文件）。§4.9 当时判定这批"跨推理/运动切面"而留在 core，
本轮复核发现它们实为薄委托：全部转发给 `self._flashbang_handler`（`FlashbangHandler` 实例），
自身不含运动数学，因此可安全并入。

**跨模块调用面**：`detect_and_handle_flashbang` 被 `core_inference.py` 调用一处，
走 `self.` 经 MRO 可达，拆分不影响。

**模块级依赖**：无新增。委托层仅用 `self.*`，`FlashbangHandler` 的构造仍在 core `__init__`。

**验证结果**：
- 抽取用 AST 方法边界（`lineno`/`end_lineno`），非硬编码行号
- 8/8 方法在 `FlashbangMixin.__dict__`，`core.Valorant.__dict__` 无残留，`__module__` 均为 `core_flash`
- AST 扫描 clean；MRO 未变（`FlashbangMixin` 已在继承列表）
- 实启 `main.py` 12 秒存活（4s/8s/10s 三次采样均 alive），`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

**顺带修复**：AST 扫描顺带查出 `core_gameconfig.py` 缺失 `import copy`
（`on_add_game_click`/`on_add_gun_click` 各有一处 `copy.deepcopy`）。属前序 §4.7 提取遗留，
仅在"新增游戏/枪械"交互路径触发，启动期不执行，故此前实启验证无法暴露。已补 import 并复扫 clean。

### 4.18 DisplayMixin 拆分验证（后续拆分会话）

**提取目标**：显示与 DPI 工具组（5 方法 55 行，`core.py` 内一段连续区间），
从 `get_system_dpi_scale` 到 `get_gradient_color`。选它的依据是这组是纯工具方法：
DPI 探测走 `ctypes.windll` + `win32api.GetSystemMetrics`，下拉框刷新只读写 `self.config`
与 dpg 控件，无运行时状态耦合。

**跨模块调用面**：`update_target_reference_class_combo` 被 `core_keybind.py`（4 处）、
`core_aimcfg.py`（2 处）、`core_infercfg.py`（1 处）、`core_gui.py`（1 处）调用；
`get_system_dpi_scale` 被 `core_gui.py`、`core_infercfg.py` 各一处调用，且被
`Valorant.__init__` 直接调用两次（DPI 缩放 + 屏幕尺寸）。全部走 `self.`，经 MRO 可达。

**模块级依赖**：`ctypes`、`win32api` 纳入 header。两者在 core.py 中原本只被这组方法使用，
搬走后成为孤儿 import，但 core.py 未定义 `__all__`、`main.py` 用 `from core import *`，
为避免破坏隐式导出契约，core.py 的 import 保持原样未删。

**MRO 位置**：置于 `CrosshairUIMixin` 与 `GUIMixin` 之间——显示辅助层紧邻 GUI 构建，语义连贯。
本组无同名方法冲突，位置不影响解析。

**已知缺陷（原样保留，未修）**：`get_gradient_color(base_color, step)` 缺 `self` 参数，
作为实例方法调用必然 `TypeError`；全项目零调用，属死代码。本轮只做位置迁移不改行为，
故原样搬移并在此记录。

**验证结果**：
- 5/5 方法在 `DisplayMixin.__dict__`，core 无残留，`__module__` 均为 `core_display`
- MRO 正确：`Valorant -> Verify -> Device -> Inference -> Trigger -> Config -> ConfigPersist -> CrosshairUI -> Display -> GUI -> ...`
- **实调验证**（非仅 hasattr）：`get_system_dpi_scale()` 返回 `1.0`，
  `get_dpi_aware_screen_size()` 返回 `(1920, 1080)`；`__init__` 两处调用点完好
- AST 扫描 clean；实启 `main.py` 12 秒存活，`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.19 ConfigPersistMixin 拆分验证（后续拆分会话）

**提取目标**：配置持久化组（6 方法 33 行，三段非连续区块），含 `get_default_config`、
`read_local_cfg`（委托 `config_manager`）、`save_config`（异步远程保存 + dpg 错误提示）、
`on_save_button_click`、`on_change`（转发 `ConfigChangeHandler`）、`migrate_auto_y_config`。

**审计中主动排除的候选**：`start`/`go`/`on_start_button_click` 虽同属"生命周期"语义，
但 `go()` 装配 `aim_bot` 定时器与 infer/trigger 线程、`on_start_button_click` 驱动启停与
TRT 引擎转换，均紧贴 `AI_CONTEXT.md` §8 保护的运行时装配，风险高于收益，留在 core.py。
`close_screenshot`/`reset_down_status` 为跨切面（截图资源 / 压枪状态），同样留下。

**跨模块调用面**：`save_config` 被 `core_systemcfg.py`（3 处）调用，`on_change` 被
`core_pidtracker.py:134` 用 `dpg.set_item_callback(control_id, self.on_change)` 注册为控件回调，
`get_default_config`/`read_local_cfg` 被 `core_config.py`（2 处）调用，
`on_save_button_click` 被 `core_gui.py:500` 绑定为"保存配置"按钮回调。全部走 `self.`。

**模块级依赖**：`threading`（异步保存线程）、`config_manager as cfgmgr`、
`save_remote_config`（`from remote_config`）纳入 header。

**MRO 位置**：紧随 `ConfigMixin`——同属配置域，读写两侧相邻。

**验证结果**：
- 6/6 方法在 `ConfigPersistMixin.__dict__`，core 无残留，`__module__` 均为 `core_persist`
- **实调验证**：`get_default_config()` 返回 27 键 dict；`read_local_cfg()` 成功读取 `cfg.json` 返回 dict
- AST 扫描 clean；实启 `main.py` 12 秒存活，`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.20 InputListenerMixin 拆分验证（后续拆分会话）

**提取目标**：输入监听层（7 方法 139 行），一段连续区块 + 尾部 `reset_pid`：
`_mouse_button_to_key`、`on_click`、`on_scroll`、`on_press`、`on_release`、
`reset_target_lock`、`reset_pid`。

**内聚依据**：`on_click` 经 `_mouse_button_to_key` 解析 pynput 按钮，三个事件回调都调
`reset_pid`，`on_release` 额外调 `reset_target_lock`。整组由 `core_devices.py` 注册进
`keyboard.Listener` / `mouse.Listener`（键盘 5 处、鼠标 2 处 `self.on_*` 引用），
在监听线程中被调用，与 `aim_bot_func` 定时器热路径不相交。

**审计中主动排除**：`down_func` 虽同由 `__init__` 装配定时器，但函数体含 `move_r` 压枪运动
数学，属运动切面，留在 core.py。

**模块级依赖**：`time`、`from pynput import mouse`、`from function import key2str`
（后者沿用 `core_keybind.py` 的既有先例）。

**MRO 位置**：紧随 `DeviceMixin`——监听器由它注册，语义相邻。

**验证结果**：
- 7/7 方法 `__module__` 为 `core_input`，`core.Valorant.__dict__` 无残留
- **实调验证**：`_mouse_button_to_key` 六例全通过——`Button.left/right/middle/x1/x2`
  分别映射 `mouse_left/right/middle/x1/x2`，`Button.unknown` 回落 `None`；
  `on_scroll(0,0,0,0)` 实调返回 `None`（显式 no-op，不抛）
- `core_devices.py` 监听注册点仍解析到 `core_input`
- AST 扫描 clean；实启 `main.py` 三次采样（4/8/12s）均存活，`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.21 PerceptionMixin 拆分验证（后续拆分会话）

**提取目标**：感知辅助层（3 方法 44 行）：`screenshot`、`smooth_small_targets`、
`update_crosshair_tracking`。

**内聚依据**：三者都在推理/预处理链路的旁路上，不参与 `aim_bot_func` 定时器热路径。
`update_crosshair_tracking` 由 `core_inference.py` 预处理后台线程调用（130/151/158 三处），
委托 `self._crosshair_tracker.update()`。

**死代码认定（AST 精确调用面）**：用 AST 遍历 `ast.Call` + `ast.Attribute` 判定，而非文本
grep，避免把同名定义误计为调用：
- `Valorant.screenshot`：**零调用**。docstring 自述"已弃用"，截图统一走
  `screenshot_manager.get_screenshot()`。
- `Valorant.smooth_small_targets(self, targets)`：**零调用**。已被
  `AimPipeline.smooth_small_targets(self, targets, aim_params)`（`aim_pipeline.py:584-634`，
  三参版本，由 `:1005` 的 `self.` 调用，`self` 是 `AimPipeline` 实例）取代。
  早先审计脚本曾把该同名定义误报为 "aim_pipeline.py(2) 外部调用"，AST 复核后纠正。

两者**原样保留不删**，仅迁移位置：删除超出本次重构范围，且 `from core import *` 的隐式
导出契约不宜擅动。

**模块级依赖**：`time`（`smooth_small_targets` 用 `time.time()` 打帧时戳）。

**MRO 位置**：紧随 `InferenceMixin`——感知辅助紧邻推理域。

**验证结果**：
- 3/3 方法 `__module__` 为 `core_perception`，core 无残留
- **实调验证**：`smooth_small_targets` 喂真实目标结构两趟——首帧历史不足返回原目标
  （`smoothed` 缺省），次帧累积到 2 帧后触发平滑并置 `smoothed=True`，`pos` 为均值
- 运动执行环 7 方法（`aim_bot_func`、`get_current_aim_center`、`_try_crosshair_pull`、
  `execute_move`、`_emit_move_rel`、`_execute_move_async`、`down_func`）逐个断言
  `__module__ == 'core'`，确认保护区未被穿透
- 全量 AST 扫描 20 个 `core_*.py` + `core.py` 均 clean
- 实启 `main.py` 三次采样存活，`error_log.txt` 为空
- pytest：`5 passed, 1 error`（基线不变）

### 4.22 拆分停止边界（本轮结论）

`core.py` 收敛至 940 行 / 15 个方法后**停止继续拆分**。剩余内容按不可拆原因分三类：

| 类别 | 方法 | 不拆原因 |
|------|------|----------|
| 运动执行环 | `aim_bot_func`(73)、`execute_move`、`_emit_move_rel`、`_execute_move_async`、`_try_crosshair_pull`、`get_current_aim_center` | `AI_CONTEXT.md` §8 明令不动 `aim_bot_func` 阻塞逻辑。`aim_bot_func` 每帧调用后五者，是 1ms 定时器热路径 |
| 配置装配中枢 | `__init__`(290)、`_change_callback`(75) | 占 core.py 39%。`__init__` 装配全部实例状态并注册 `aim_bot_func`/`down_func` 定时器，是所有 mix-in 的共同依赖根，拆出即制造循环依赖 |
| 生命周期编排 | `start`、`go`(28)、`on_start_button_click`(73)、`close_screenshot`、`reset_down_status`、`_update_class_checkboxes`、`down_func`(34) | `go()` 建 `aim_bot` 定时器与 infer/trigger 线程，`on_start_button_click` 管启停与定时器销毁——均紧贴 §8 运行时装配。`down_func` 含 `move_r` 运动数学 |

**关于三个零散小方法**（`close_screenshot` / `reset_down_status` / `_update_class_checkboxes`）：
分属截图资源、压枪状态、GUI 类别刷新三个互不相干的切面，硬凑成"杂项 mix-in"只会制造一个
语义空洞的模块，损害可维护性而非改善。判定留在 core.py。

## 5. 提取脚本要点

- 用 `utf-8-sig` 读 `core.py`，按 1-based 闭区间 `[start,end]` 切片取块。
- 从 core 删块后，在最后一条 `from core_* import` 行后插入新 import，并更新
  `class Valorant(...)` 继承列表。
- **边界检查**：抽取区间末尾的下一行必须是空行或同级 `def`，避免 off-by-one
  把下一个方法的签名接力地拉进来而函数体留在 core。
- **去重**：拼接新文件时跳过已存在的 `from core_*` import 行，避免重复 import。
- **行操作用 Python 脚本**，不用 PowerShell 数组索引（易出类型错误）。
- 写 mix-in 文件：头部 import + `class XxxMixin:`，再 `writelines(block)`。

## 6. 推荐后续验证姿势

任何后续 mix-in 提取，验证链**必须**包含实例化路径，不能只靠 `from core import *`：
1. `from core import *` + MRO/方法定位抽检
2. AST 扫描 `core_*.py` 中「类体内被 Load 但从未本地绑定且未顶层 import」的名字
3. 缺失项逐文件溯源定位（区分真缺失 vs 嵌套 `def`/局部 import 误报）
4. **实启 `main.py` ≥8 秒，确认不崩、`error_log.txt` 为空**
5. `pytest -q --continue-on-collection-errors` 维持 `5 passed, 1 error` 基线
