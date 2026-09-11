import threading
import json
import os
import queue
import sys
import collections

print("[Web控制面板] 正在初始化...")

# 尝试导入 NiceGUI
try:
    from nicegui import ui, app as ng_app
    print("[Web控制面板] NiceGUI 导入成功")
except Exception as e:
    print(f"[Web控制面板] NiceGUI 导入失败: {e}")
    sys.exit(1)

app_instance = None
config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cfg.json')

# 日志：有界缓冲，避免无人查看时无限增长
log_messages = collections.deque(maxlen=500)  # (seq, text)
_log_lock = threading.Lock()
_log_seq = 0
log_queue = queue.Queue(maxsize=5000)  # 兼容旧引用

# 服务器单例状态
_server_lock = threading.RLock()
_server_state = {'thread': None, 'started': False}
_print_redirect_installed = False

WEB_HOST = '0.0.0.0'
WEB_PORT = 5000
STORAGE_SECRET = 'dopa-web-panel-storage'

# 配置分类映射
CONFIG_CATEGORIES = {
    "基本设置": ["group", "move_method", "is_curve", "curve_type"],
    "性能设置": ["performance_mode", "use_async_move", "frame_skip_ratio", "cpu_optimization", "memory_optimization"],
    "视觉设置": ["show_fov", "is_show_lock_target", "show_infer_time", "is_show_priority_debug"],
    "自动背闪": ["auto_flashbang"],
    "移动设置": ["is_curve", "is_curve_uniform", "curve_switch_mode", "offset_boundary_x", "offset_boundary_y"],
    "按键设置": ["aim_key", "aim_keys_dist"],
    "其他设置": []
}

# 中文标签映射 - 更完整的汉化
CHINESE_LABELS = {
    # 基本设置
    "group": "当前组",
    "move_method": "移动方法",
    "is_curve": "启用曲线",
    "curve_type": "曲线类型",
    "performance_mode": "性能模式",
    "use_async_move": "异步移动",
    "frame_skip_ratio": "跳帧比例",
    "cpu_optimization": "CPU优化",
    "memory_optimization": "内存优化",
    "show_fov": "显示视野",
    "is_show_lock_target": "显示锁敌",
    "show_infer_time": "显示推理时间",
    "is_show_priority_debug": "显示优先级调试",
    "auto_flashbang": "自动背闪",
    "is_curve_uniform": "均匀曲线",
    "curve_switch_mode": "曲线切换模式",
    "offset_boundary_x": "X偏移边界",
    "offset_boundary_y": "Y偏移边界",
    "aim_key": "瞄准按键",
    "aim_keys_dist": "按键配置",
    
    # 自动背闪子项
    "enabled": "启用",
    "delay_ms": "延迟(毫秒)",
    "turn_angle": "转向角度",
    "sensitivity_multiplier": "灵敏度倍数",
    "return_delay": "返回延迟",
    "min_confidence": "最小置信度",
    "min_size": "最小尺寸",
    "use_curve": "使用曲线",
    "curve_speed": "曲线速度",
    "curve_knots": "曲线节点",
    "detect_class_ids": "检测类别ID",
    
    # 其他常见配置
    "km_box_vid": "KM Box VID",
    "km_box_pid": "KM Box PID",
    "km_net_ip": "KM Net IP",
    "km_net_port": "KM Net 端口",
    "km_net_uuid": "KM Net UUID",
    "dhz_ip": "DHZ IP",
    "dhz_port": "DHZ 端口",
    "dhz_random": "DHZ 随机值",
    "catbox_ip": "CatBox IP",
    "catbox_port": "CatBox 端口",
    "catbox_uuid": "CatBox UUID",
    "km_com": "KM COM端口",
    "is_show_curve": "显示曲线",
    "auto_curve_switch": "自动曲线切换",
    "curve_switch_count": "曲线切换次数",
    "curve_switch_interval": "曲线切换间隔",
    "curve_switch_probability": "曲线切换概率",
    "is_show_down": "显示下压",
    "knots_count": "节点数量",
    "distortion_mean": "扭曲均值",
    "distortion_st_dev": "扭曲标准差",
    "distortion_frequency": "扭曲频率",
    "target_points": "目标点数",
    "distance_scoring_weight": "距离评分权重",
    "center_scoring_weight": "中心评分权重",
    "size_scoring_weight": "大小评分权重",
    "picked_game": "选择游戏",
    "down_switch_key": "下压切换键",
    "is_obs": "启用OBS",
    "obs_ip": "OBS IP",
    "obs_port": "OBS 端口",
    "obs_fps": "OBS 帧率",
    "is_cjk": "启用CJK",
    "cjk_device_id": "CJK 设备ID",
    "cjk_fps": "CJK 帧率",
    "cjk_resolution": "CJK 分辨率",
    "cjk_crop_size": "CJK 裁剪大小",
    "cjk_fourcc_format": "CJK 编码格式",
    "mask_left": "左侧掩码",
    "mask_right": "右侧掩码",
    "mask_middle": "中间掩码",
    "mask_side1": "侧边1掩码",
    "mask_side2": "侧边2掩码",
    "mask_x": "X掩码",
    "aim_mask_x": "瞄准X掩码",
    "mask_y": "Y掩码",
    "aim_mask_y": "瞄准Y掩码",
    "mask_wheel": "滚轮掩码",
    "is_v8": "使用V8模型",
    "is_trt": "使用TRT",
    "original_infer_model": "原始推理模型",
    "confidence_threshold": "置信度阈值",
    "iou_t": "IOU阈值",
    "aim_bot_position": "瞄准位置",
    "aim_bot_scope": "瞄准范围",
    "dynamic_scope": "动态范围",
    "smoothing_factor": "平滑因子",
    "base_step": "基础步长",
    "distance_weight": "距离权重",
    "fov_angle": "视野角度",
    "history_size": "历史大小",
    "output_scale_x": "输出缩放X",
    "output_scale_y": "输出缩放Y",
    "deadzone": "死区",
    "uniform_threshold": "均匀阈值",
    "compensation_factor": "补偿因子",
    "continuous_aim": "连续瞄准",
    "trigger": "触发器",
    "status": "状态",
    "continuous": "连续",
    "recoil": "后坐力",
    "start_delay": "开始延迟",
    "press_delay": "按压延迟",
    "end_delay": "结束延迟",
    "random_delay": "随机延迟",
    "x_trigger_scope": "X触发范围",
    "y_trigger_scope": "Y触发范围",
    "x_trigger_offset": "X触发偏移",
    "y_trigger_offset": "Y触发偏移",
    "classes": "类别",
    "class_priority_order": "类别优先级",
    "class_aim_positions": "类别瞄准位置",
    "min_position_offset": "最小位置偏移",
    "min_velocity_threshold": "最小速度阈值",
    "max_velocity_threshold": "最大速度阈值",
    "aim_bot_position2": "瞄准位置2",
    "lock_target_enabled": "启用锁敌",
    "lock_target_miss_threshold": "锁敌丢失阈值",
    "lock_target_position_threshold": "锁敌位置阈值",
    "controller_mode": "控制器模式",
    "pid_kp_x": "PID KP X",
    "pid_ki_x": "PID KI X",
    "pid_kd_x": "PID KD X",
    "pid_kp_y": "PID KP Y",
    "pid_ki_y": "PID KI Y",
    "pid_kd_y": "PID KD Y",
    "pid_integral_limit_x": "PID 积分限制X",
    "pid_integral_limit_y": "PID 积分限制Y",
    "smooth_x": "平滑X",
    "smooth_y": "平滑Y",
    "smooth_deadzone": "平滑死区",
    "smooth_algorithm": "平滑算法",
    "move_deadzone": "移动死区",
    "target_switch_delay": "目标切换延迟",
    "target_reference_class": "目标参考类别",
    "pid_integral_limit": "PID 积分限制",
    "pid_output_limit": "PID 输出限制",
    "pid_deadzone": "PID 死区",
    "lock_target_class_id": "锁敌类别ID",
    "overshoot_threshold": "过冲阈值",
    "overshoot_x_factor": "过冲X因子",
    "overshoot_y_factor": "过冲Y因子",
    "min_scope": "最小范围",
    "shrink_duration_ms": "缩小持续时间",
    "recover_duration_ms": "恢复持续时间",
    "number": "数量",
    "offset": "偏移",
    "infer_debug": "推理调试",
    "print_fps": "打印FPS",
    "show_motion_speed": "显示移动速度",
    "enable_parallel_processing": "启用并行处理",
    "turbo_mode": "涡轮模式",
    "skip_frame_processing": "跳过帧处理",
    "gui_dpi_scale": "GUI DPI缩放",
    "screen_width": "屏幕宽度",
    "screen_height": "屏幕高度",
    "web_password": "Web密码",
    "enable_gpu": "启用GPU",
    "use_mouse_re_trajectory": "使用鼠标轨迹",
    "replay_speed": "回放速度",
    "pixel_enhancement_ratio": "像素增强比例",
    "mapping": "映射",
    "small_target_enhancement": "小目标增强",
    "boost_factor": "增强因子",
    "threshold": "阈值",
    "medium_threshold": "中等阈值",
    "medium_boost": "中等增强",
    "smooth_enabled": "启用平滑",
    "smooth_frames": "平滑帧数",
    "adaptive_nms": "自适应NMS",
    "crosshair_tracking": "准星追踪",
    "mode": "模式",
    "detection_area_size": "检测区域大小",
    "only_center_area": "仅中心区域",
    "miss_detection_enabled": "启用丢失检测",
    "miss_threshold": "丢失阈值",
    "detection_frequency": "检测频率",
    "failure_fallback_enabled": "启用失败回退",
    "failure_fallback_delay_ms": "失败回退延迟",
    "color_parallel_enabled": "启用颜色并行",
    "max_color_workers": "最大颜色工作线程",
    "colors": "颜色",
    "filter": "过滤器",
    "image_enhancement": "图像增强",
    "adaptive_area_enabled": "启用自适应区域",
    "area_min_size": "区域最小大小",
    "area_max_size": "区域最大大小",
    "area_expand_conf_threshold": "区域扩展置信阈值",
    "area_shrink_conf_threshold": "区域缩小置信阈值",
    "area_size_step": "区域大小步长",
    "area_adjust_interval_frames": "区域调整间隔帧",
    "aiming": "瞄准",
    "speed_multiplier": "速度倍数",
    "_crosshair_position": "准星位置",
    "show_position": "显示位置",
    "show_detection_area": "显示检测区域",
    "show_mask": "显示掩码",
    "_color_picker_active": "颜色选择器激活",
    "movement_range": "移动范围",
    "_current_preset": "当前预设",
    "_is_adjusting": "正在调整",
    "boundary_visualization": "边界可视化",
    "line_width": "线宽",
    "dash_length": "虚线长度",
    "dash_gap": "虚线间隔",
    "color": "颜色",
    "highlight_color": "高亮颜色",
    "highlight_line_width": "高亮线宽",
    "parameter_display": "参数显示",
    "update_fps": "更新FPS",
    "position": "位置",
    "_current_detection_region": "当前检测区域",
    "_current_detection_center": "当前检测中心",
    "detection_area_offset": "检测区域偏移",
    "x": "X",
    "y": "Y",
    "dynamic_mode": "动态模式",
    "_detection_area_adjustment_active": "检测区域调整激活",
    "detection_area_height": "检测区域高度",
    "detection_area_width": "检测区域宽度",
    "ml_assist_enabled": "启用ML辅助",
    "gpu_color_ops_enabled": "启用GPU颜色操作",
    "tolerance_profile": "容差配置文件",
    "shape_matching": "形状匹配",
    "reference_area": "参考面积",
    "reference_aspect_ratio": "参考宽高比",
    "reference_circularity": "参考圆度",
    "reference_hu_moments": "参考Hu矩",
    "area_tolerance": "面积容差",
    "aspect_ratio_tolerance": "宽高比容差",
    "circularity_tolerance": "圆度容差",
    "hu_similarity_threshold": "Hu相似度阈值",
    "template_enabled": "启用模板",
    "template_points": "模板点",
    "template_similarity_threshold": "模板相似度阈值",
    "template_weight": "模板权重",
    "reference_contour_template": "参考轮廓模板",
    "background_rejection": "背景拒绝",
    "ring_px": "环形像素",
    "max_ring_ratio": "最大环形比例",
    "min_bbox_fill_ratio": "最小边界框填充比例",
    "debug_logging": "调试日志",
    "log_level": "日志级别",
    "log_to_file": "记录到文件",
    "log_file": "日志文件",
    "log_to_console": "记录到控制台",
    "categories": "类别",
    "crosshair": "准星",
    "coordinate": "坐标",
    "drawing": "绘图",
    "aiming": "瞄准",
    "makcu_firmware": "MAKCU固件"
}

# ---------------- 配置读写（与主程序共享同一 config 对象） ----------------
def _live_config():
    cfg = getattr(app_instance, 'config', None) if app_instance is not None else None
    return cfg if isinstance(cfg, dict) else None


def read_config():
    cfg = _live_config()
    if cfg is not None:
        return cfg
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Web控制面板] 读取配置文件失败: {e}")
        return {}


def save_config(config=None):
    cfg = config if isinstance(config, dict) else read_config()
    live = _live_config()
    if live is not None and cfg is live:
        try:
            from settings.remote_config import save_remote_config
            if save_remote_config(cfg):
                print('[Web控制面板] 配置已保存并与主程序同步')
                return True
        except Exception as e:
            print(f'[Web控制面板] 共享保存失败，回退写文件: {e}')
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print('[Web控制面板] 配置文件保存成功')
        return True
    except Exception as e:
        print(f'[Web控制面板] 保存配置文件失败: {e}')
        return False


def _change_path_supported(path):
    """仅把主程序 _change_callback 能正确处理的路径回灌，避免深路径被误写。"""
    parts = path.split('.')
    if len(parts) == 1:
        return True
    if len(parts) == 3 and parts[0] == 'groups':
        return True
    if len(parts) >= 5 and parts[0] == 'groups' and parts[2] == 'aim_keys':
        param = parts[4]
        if param in ('class_aim_positions', 'pid_params'):
            return False
        if param == 'trigger' and len(parts) == 6:
            return True
        return len(parts) == 5
    return False


def apply_change(path, value):
    """把 Web 端改动回灌到主程序回调，触发刷新引擎/按键配置等副作用。"""
    if app_instance is None:
        return
    if not _change_path_supported(path):
        return
    cb = getattr(app_instance, '_change_callback', None)
    if callable(cb):
        try:
            cb(path, value)
        except Exception as e:
            print(f'[Web控制面板] 应用变更失败 {path}={value!r}: {e}')


# 获取中文标签
def get_chinese_label(key):
    return CHINESE_LABELS.get(key, key)

# 递归创建配置控件（双向写回主程序 config，并回灌变更回调）
def _format_label(path, key):
    label = get_chinese_label(key)
    return label if label != key else (f"{path}.{key}" if path else key)


def _set_live(container, key, value, path):
    container[key] = value
    apply_change(path, value)


def _add_value_control(parent, container, key, path):
    value = container.get(key)
    label = _format_label(path, key)
    with parent:
        if isinstance(value, bool):
            ctrl = ui.switch(label)
            ctrl.value = bool(value)
            ctrl.on_value_change(lambda e: _set_live(container, key, bool(e.value), path))
        elif isinstance(value, int):
            ctrl = ui.number(label)
            ctrl.value = int(value)
            ctrl.on_value_change(
                lambda e: _set_live(container, key, int(round(float(e.value or 0))), path)
            )
        elif isinstance(value, float):
            ctrl = ui.number(label, step=0.01)
            ctrl.value = float(value)
            ctrl.on_value_change(
                lambda e: _set_live(container, key, float(e.value or 0.0), path)
            )
        elif isinstance(value, str):
            ctrl = ui.input(label)
            ctrl.value = value
            ctrl.on_value_change(lambda e: _set_live(container, key, str(e.value), path))
        elif isinstance(value, list):
            ui.label(f"{label}:").classes('font-bold text-center w-full')
            ctrl = ui.textarea(value=json.dumps(value, indent=2, ensure_ascii=False))
            ctrl.classes('w-full max-w-2xl mx-auto')

            def _on_list(e, c=container, k=key, p=path):
                try:
                    parsed = json.loads(e.value)
                except Exception:
                    return
                if parsed != c.get(k):
                    _set_live(c, k, parsed, p)
            ctrl.on_value_change(_on_list)
        else:
            ui.label(f"{label}: {value!r}").classes('text-center w-full')


def create_config_controls(config, parent_container, path=""):
    for key, value in list(config.items()):
        current_path = f"{path}.{key}" if path else key
        label = _format_label(path, key)

        if isinstance(value, dict):
            with parent_container:
                with ui.expansion(label).classes('w-full max-w-2xl mx-auto'):
                    create_config_controls(value, ui.column().classes('items-center w-full'), current_path)
        else:
            _add_value_control(parent_container, config, key, current_path)

# 按分类创建配置控件
def create_config_by_category(config, parent_container):
    categorized_keys = set()
    for keys in CONFIG_CATEGORIES.values():
        categorized_keys.update(keys)

    # 分类项
    for category, keys in CONFIG_CATEGORIES.items():
        category_keys = [key for key in keys if key in config]
        if not category_keys:
            continue
        with parent_container:
            with ui.expansion(category).classes('w-full max-w-2xl mx-auto'):
                for key in category_keys:
                    value = config[key]
                    if isinstance(value, dict):
                        with ui.expansion(_format_label('', key)).classes('w-full'):
                            create_config_controls(value, ui.column().classes('items-center w-full'), key)
                    else:
                        _add_value_control(ui.column().classes('w-full'), config, key, key)

    # 未分类的顶层标量
    uncategorized_keys = [
        key for key in config
        if key not in categorized_keys and not isinstance(config[key], dict)
    ]
    if uncategorized_keys:
        with parent_container:
            with ui.expansion("其他设置").classes('w-full max-w-2xl mx-auto'):
                for key in uncategorized_keys:
                    _add_value_control(ui.column().classes('w-full'), config, key, key)

    # 嵌套的 groups（自瞄/模型等核心设置实际都在这里）
    groups = config.get('groups')
    if isinstance(groups, dict) and groups:
        with parent_container:
            with ui.expansion('模型/分组设置').classes('w-full max-w-2xl mx-auto'):
                create_config_controls(groups, ui.column().classes('items-center w-full'), 'groups')

# ---------------- 日志 ----------------
def _record_log(message):
    global _log_seq
    with _log_lock:
        _log_seq += 1
        seq = _log_seq
        log_messages.append((seq, message))
    try:
        log_queue.put_nowait(message)
    except queue.Full:
        pass
    return seq


def _current_log_seq():
    with _log_lock:
        return _log_seq


def _logs_since(seq):
    with _log_lock:
        return [m for m in log_messages if m[0] > seq]


# 重定向print函数，将日志写入有界缓冲
def redirect_print():
    original_print = print

    def new_print(*args, **kwargs):
        message = ' '.join(map(str, args))
        try:
            original_print(*args, **kwargs)
        except Exception:
            pass
        _record_log(message)
    return new_print


def install_print_redirect():
    global _print_redirect_installed
    if _print_redirect_installed:
        return
    import builtins
    builtins.print = redirect_print()
    _print_redirect_installed = True

# ---------------- 鉴权 ----------------
def _web_password():
    try:
        return str(read_config().get('web_password') or '')
    except Exception:
        return ''


def _is_authed():
    pwd = _web_password()
    if not pwd:
        return True
    try:
        return bool(ng_app.storage.user.get('authed'))
    except Exception:
        # storage 不可用时放行，保证本地可用
        return True


def _register_pages():
    @ui.page('/login')
    def login_page():
        with ui.column().classes('items-center justify-center w-full h-screen'):
            ui.label('DOPA Web 控制面板').classes('text-2xl font-bold mb-4')
            pwd = ui.input('密码', password=True).classes('w-64')

            def do_login():
                if pwd.value == _web_password():
                    try:
                        ng_app.storage.user['authed'] = True
                    except Exception:
                        pass
                    ui.navigate.to('/')
                else:
                    ui.notify('密码错误', type='negative')

            ui.button('登录', on_click=do_login).classes('mt-2')

    @ui.page('/')
    def main_page():
        if not _is_authed():
            ui.navigate.to('/login')
            return
        try:
            config = read_config()
            with ui.header().classes('items-center justify-between bg-gray-100 dark:bg-gray-800 p-4'):
                ui.label('Web控制面板').classes('text-xl font-bold')
                dark_mode_switch = ui.switch('深色模式')
                ui.dark_mode().bind_value(dark_mode_switch, 'value')

            with ui.row().classes('w-full h-[calc(100vh-80px)] p-4 space-x-4 flex'):
                with ui.column().classes('flex-1 overflow-auto bg-white dark:bg-gray-900 rounded-lg shadow-md p-4'):
                    ui.label('配置参数').classes('text-lg font-bold mb-4 text-center')

                    def on_save():
                        if save_config(config):
                            ui.notify('配置保存成功并已同步到主程序', type='success')
                        else:
                            ui.notify('配置保存失败', type='negative')

                    ui.button('保存配置', on_click=on_save).classes(
                        'mt-2 mb-2 bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-md mx-auto block'
                    )
                    create_config_by_category(config, ui.column().classes('space-y-2 w-full'))

                with ui.column().classes('w-1/3 min-w-[300px] bg-white dark:bg-gray-900 rounded-lg shadow-md p-4 flex flex-col'):
                    ui.label('日志输出').classes('text-lg font-bold mb-4 text-center')
                    log_output = ui.log().classes('flex-1 bg-gray-50 dark:bg-gray-800 rounded-md p-2')
                    log_output.push('[Web控制面板] 启动成功')
                    log_output.push('[Web控制面板] 配置已与主程序共享')
                    state = {'last': _current_log_seq()}

                    def flush_log():
                        for seq, text in _logs_since(state['last']):
                            log_output.push(text)
                            state['last'] = seq

                    ui.timer(0.5, flush_log)
        except Exception as e:
            ui.label(f'页面渲染失败: {e}').classes('text-red-500')


# 在单独的线程中启动服务器
def _run_server():
    try:
        print('[Web控制面板] 启动服务器...')
        ui.run(host=WEB_HOST, port=WEB_PORT, reload=False, show=False, storage_secret=STORAGE_SECRET)
    except Exception as e:
        print(f'[Web控制面板] 服务器启动失败: {e}')
    finally:
        with _server_lock:
            _server_state['started'] = False
        print('[Web控制面板] 服务器已停止')


# 启动Web服务器（单例）
def start_web_server(instance=None):
    global app_instance
    if instance is not None:
        app_instance = instance
    with _server_lock:
        if _server_state['started']:
            print('[Web控制面板] 服务器已在运行，忽略重复启动')
            return
        _register_pages()
        install_print_redirect()
        _server_state['started'] = True
        server_thread = threading.Thread(target=_run_server, daemon=True)
        _server_state['thread'] = server_thread
        server_thread.start()
    print(f'[Web控制面板] 访问地址: http://localhost:{WEB_PORT}')


def stop_web_server():
    """请求停止 NiceGUI/uvicorn 服务器（进程内其他功能不受影响）。"""
    with _server_lock:
        if not _server_state['started']:
            return False
    try:
        from nicegui.server import Server
        inst = getattr(Server, 'instance', None)
        if inst is not None:
            inst.should_exit = True
            print('[Web控制面板] 已请求停止服务器')
            return True
    except Exception as e:
        print(f'[Web控制面板] 设置服务器退出标志失败: {e}')
    try:
        from nicegui import core
        loop = getattr(core, 'loop', None)
        if loop is not None and loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(core.app.stop(), loop).result(timeout=5)
            print('[Web控制面板] 已请求停止服务器(应用层)')
            return True
    except Exception as e:
        print(f'[Web控制面板] 停止服务器失败: {e}')
    return False


# 直接运行时的测试代码
if __name__ == '__main__':
    print("[Web控制面板] 启动中...")
    start_web_server(None)
