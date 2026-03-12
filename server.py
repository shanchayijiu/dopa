import threading
import json
import os
import queue

print("[Web控制面板] 正在初始化...")

# 尝试导入 NiceGUI
try:
    from nicegui import ui
    print("[Web控制面板] NiceGUI 导入成功")
except Exception as e:
    print(f"[Web控制面板] NiceGUI 导入失败: {e}")
    import sys
    sys.exit(1)

app_instance = None
config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cfg.json')
log_messages = []
log_queue = queue.Queue()

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
    "is_curve_uniform": "均匀曲线",
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
    "enabled": "启用",
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

# 读取配置文件
def read_config():
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Web控制面板] 读取配置文件失败: {e}")
        return {}

# 保存配置文件
def save_config(config):
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("[Web控制面板] 配置文件保存成功")
        return True
    except Exception as e:
        print(f"[Web控制面板] 保存配置文件失败: {e}")
        return False

# 获取中文标签
def get_chinese_label(key):
    return CHINESE_LABELS.get(key, key)

# 递归创建配置控件
def create_config_controls(config, parent_container, path=""):
    for key, value in config.items():
        current_path = f"{path}.{key}" if path else key
        label = get_chinese_label(key)
        
        if isinstance(value, dict):
            # 创建折叠面板，居中显示
            with parent_container:
                with ui.expansion(label).classes('w-full max-w-2xl mx-auto'):
                    create_config_controls(value, ui.column().classes('items-center'), current_path)
        elif isinstance(value, list):
            # 列表类型，暂时显示为文本
            with parent_container:
                ui.label(f"{label}:").classes('font-bold text-center w-full')
                ui.textarea(value=json.dumps(value, indent=2, ensure_ascii=False), 
                           placeholder="输入JSON格式的列表").classes('w-full max-w-2xl mx-auto')
        elif isinstance(value, bool):
            # 布尔类型，使用开关
            with parent_container:
                ui.switch(label, value=value).bind_value(config, key).classes('max-w-2xl mx-auto')
        elif isinstance(value, (int, float)):
            # 数值类型，使用输入框
            with parent_container:
                if isinstance(value, int):
                    ui.number(label, value=value).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
                else:
                    ui.number(label, value=value, step=0.01).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
        else:
            # 字符串类型，使用输入框
            with parent_container:
                ui.input(label, value=str(value)).bind_value(config, key).classes('w-full max-w-2xl mx-auto')

# 按分类创建配置控件
def create_config_by_category(config, parent_container):
    # 首先处理有分类的配置
    for category, keys in CONFIG_CATEGORIES.items():
        category_keys = [key for key in keys if key in config]
        if category_keys:
            with parent_container:
                with ui.expansion(category).classes('w-full max-w-2xl mx-auto'):
                    for key in category_keys:
                        value = config[key]
                        label = get_chinese_label(key)
                        
                        if isinstance(value, dict):
                            # 创建折叠面板
                            with ui.expansion(label).classes('w-full'):
                                create_config_controls(value, ui.column().classes('items-center'))
                        elif isinstance(value, list):
                            # 列表类型，暂时显示为文本
                            ui.label(f"{label}:").classes('font-bold text-center w-full')
                            ui.textarea(value=json.dumps(value, indent=2, ensure_ascii=False), 
                                       placeholder="输入JSON格式的列表").classes('w-full max-w-2xl mx-auto')
                        elif isinstance(value, bool):
                            # 布尔类型，使用开关
                            ui.switch(label, value=value).bind_value(config, key).classes('max-w-2xl mx-auto')
                        elif isinstance(value, (int, float)):
                            # 数值类型，使用输入框
                            if isinstance(value, int):
                                ui.number(label, value=value).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
                            else:
                                ui.number(label, value=value, step=0.01).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
                        else:
                            # 字符串类型，使用输入框
                            ui.input(label, value=str(value)).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
    
    # 处理未分类的配置
    categorized_keys = set()
    for keys in CONFIG_CATEGORIES.values():
        categorized_keys.update(keys)
    
    uncategorized_keys = [key for key in config if key not in categorized_keys and not isinstance(config[key], dict)]
    if uncategorized_keys:
        with parent_container:
            with ui.expansion("其他设置").classes('w-full max-w-2xl mx-auto'):
                for key in uncategorized_keys:
                    value = config[key]
                    label = get_chinese_label(key)
                    
                    if isinstance(value, bool):
                        ui.switch(label, value=value).bind_value(config, key).classes('max-w-2xl mx-auto')
                    elif isinstance(value, (int, float)):
                        if isinstance(value, int):
                            ui.number(label, value=value).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
                        else:
                            ui.number(label, value=value, step=0.01).bind_value(config, key).classes('w-full max-w-2xl mx-auto')
                    else:
                        ui.input(label, value=str(value)).bind_value(config, key).classes('w-full max-w-2xl mx-auto')

# 日志处理器
def log_handler():
    while True:
        try:
            message = log_queue.get(timeout=1)
            if hasattr(ui, 'log_output'):
                ui.log_output.push(message)
        except queue.Empty:
            pass

# 重定向print函数，将日志发送到队列
def redirect_print():
    original_print = print
    def new_print(*args, **kwargs):
        message = ' '.join(map(str, args))
        original_print(*args, **kwargs)
        log_queue.put(message)
    return new_print

# 启动Web服务器
def start_web_server(instance):
    global app_instance
    app_instance = instance
    
    # 读取配置
    config = read_config()
    print("[Web控制面板] 配置文件读取成功")
    
    # 创建主界面
    @ui.page('/')
    def main_page():
        # 创建主题切换按钮
        with ui.header().classes('items-center justify-between bg-gray-100 dark:bg-gray-800 p-4'):
            ui.label('Web控制面板').classes('text-xl font-bold')
            dark_mode_switch = ui.switch('深色模式')
            ui.dark_mode().bind_value(dark_mode_switch, 'value')
        
        # 创建左右布局，使用flex布局确保右侧固定
        with ui.row().classes('w-full h-[calc(100vh-80px)] p-4 space-x-4 flex'):
            # 左侧参数区，可滚动
            with ui.column().classes('flex-1 overflow-auto bg-white dark:bg-gray-900 rounded-lg shadow-md p-4'):
                ui.label('配置参数').classes('text-lg font-bold mb-4 text-center')
                
                # 按分类创建配置控件
                create_config_by_category(config, ui.column().classes('space-y-2'))
                
                # 保存按钮
                def on_save():
                    if save_config(config):
                        # 重新读取配置以确保同步
                        new_config = read_config()
                        # 更新UI显示
                        ui.notify('配置保存成功并已同步', type='success')
                        # 这里可以添加重新加载UI的逻辑
                
                ui.button('保存配置', on_click=on_save).classes('mt-4 bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-md mx-auto block')
        
        # 右侧日志输出区，固定宽度，不随左侧变化
        with ui.column().classes('w-1/3 min-w-[300px] bg-white dark:bg-gray-900 rounded-lg shadow-md p-4 flex flex-col'):
            ui.label('日志输出').classes('text-lg font-bold mb-4 text-center')
            
            # 创建日志输出控件，占满剩余空间
            log_output = ui.log().classes('flex-1 bg-gray-50 dark:bg-gray-800 rounded-md p-2')
            log_output.push("[Web控制面板] 启动成功")
            log_output.push("[Web控制面板] 配置文件读取成功")
            log_output.push("[Web控制面板] 欢迎使用 NiceGUI 控制面板")
            
            # 保存日志输出控件引用
            ui.log_output = log_output
    
    # 启动日志处理线程
    log_thread = threading.Thread(target=log_handler, daemon=True)
    log_thread.start()
    
    # 重定向print函数
    import builtins
    builtins.print = redirect_print()
    
    # 启动服务器线程
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    print("[Web控制面板] 服务器启动中...")
    print("[Web控制面板] 访问地址: http://localhost:5000")

# 在单独的线程中启动服务器
def run_server():
    try:
        print("[Web控制面板] 启动服务器...")
        ui.run(host='0.0.0.0', port=5000, reload=False)
    except Exception as e:
        print(f"[Web控制面板] 服务器启动失败: {e}")

# 直接运行时的测试代码
if __name__ == '__main__':
    print("[Web控制面板] 启动中...")
    config = read_config()
    start_web_server(None)
