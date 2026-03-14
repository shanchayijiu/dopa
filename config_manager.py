# -*- coding: utf-8 -*-
"""
配置管理模块 — 从 core.py 抽取的纯配置 I/O 与迁移逻辑

职责：
  - 默认配置生成
  - cfg.json 读写
  - 版本迁移（class_based、auto_y）
  - model_runtime 默认值填充
"""
import json
import os
import copy


def get_default_config():
    """返回完整的默认配置字典"""
    return {
        'enable_parallel_processing': True,
        'turbo_mode': True,
        'skip_frame_processing': True,
        'enable_web_server': False,
        'inference_device': 'CPU',
        'model_runtime': {
            'v11_auto_discover': True,
            'v11_expected_opset': None,
            'v11_expected_model_version': None,
            'v11_strict_graph': True,
            'v11_search_dirs': ['models', 'weights'],
            'intra_op_num_threads': 0,
            'inter_op_num_threads': 0,
            'enable_cpu_mem_arena': True,
            'enable_mem_pattern': True,
            'execution_mode': 'sequential',
            'graph_optimization_level': 'all',
            'cuda_mem_limit_mb': 0,
            'arena_extend_strategy': 'kNextPowerOfTwo',
        },
        'performance_mode': 'balanced',
        'use_async_move': False,
        'frame_skip_ratio': 0,
        'cpu_optimization': True,
        'memory_optimization': True,
        'auto_flashbang': {
            'enabled': False,
            'delay_ms': 150,
            'turn_angle': 90,
            'sensitivity_multiplier': 2.5,
            'return_delay': 80,
            'min_confidence': 0.3,
            'min_size': 5,
            'use_curve': True,
            'curve_speed': 8.0,
            'curve_knots': 3,
        },
        'crosshair_color_lock': {
            'enabled': False,
            'roi_width': 200,
            'roi_height': 200,
            'hsv_ranges': [
                {'h_min': 0, 'h_max': 179, 's_min': 0, 's_max': 255, 'v_min': 0, 'v_max': 255}
            ],
            'active_index': 0,
            'show_crosshair': True,
            'show_lock_box': True,
            'min_area': 12,
            'last_rgb': [0, 0, 0],
            'pull_k': 0.12,
            'pull_max_speed': 6.0,
            'pull_deadzone': 1.0,
            'ema_smooth': 0.4,
        },
        'target_sticky_pixels': 40.0,
        'target_lock_ms': 150.0,
        'large_target_threshold': 0.055,
        'large_target_boost': 1.12,
        'groups': {
            'default': {
                'is_trt': False,
                'is_v8': True,
                'model_variant': 'onnx',
                'infer_model': 'default_model.onnx',
                'original_infer_model': 'default_model.onnx',
                'aim_keys': {
                    'mouse1': {
                        'class_aim_positions': {
                            'default': {
                                'aim_bot_position': 0.0,
                                'aim_bot_position2': 0.0,
                                'confidence_threshold': 0.5,
                                'iou_t': 1.0,
                            }
                        },
                        'pid_params': {
                            'smooth_deadzone': 0.0,
                            'move_deadzone': 1.0,
                        },
                    }
                },
            }
        },
        'picked_game': 'default_game',
        'games': {
            'default_game': {
                'name': '默认游戏',
            }
        },
        'move_method': 'send_input',
        'game_sensitivity': 1.0,
        'mouse_dpi': 800,
        'gui_dpi_scale': 1.0,
        'distance_scoring_weight': 0.6,
        'center_scoring_weight': 0.3,
        'size_scoring_weight': 0.1,
    }


def read_local_cfg(path='cfg.json'):
    """读取本地 cfg.json，失败返回 None"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print('成功读取cfg.json配置文件')
                return config
    except Exception as e:
        print(f'读取cfg.json文件失败: {e}')
    return None


def ensure_defaults(config):
    """给配置填充缺失的顶层默认值（原 build_config 中的 setdefault 块）"""
    config.setdefault('enable_parallel_processing', True)
    config.setdefault('turbo_mode', True)
    config.setdefault('skip_frame_processing', True)
    config.setdefault('performance_mode', 'balanced')
    config.setdefault('use_async_move', False)
    config.setdefault('frame_skip_ratio', 0)
    config.setdefault('cpu_optimization', True)
    config.setdefault('memory_optimization', True)

    if 'auto_flashbang' not in config:
        config['auto_flashbang'] = {
            'enabled': False, 'delay_ms': 150, 'turn_angle': 90,
            'sensitivity_multiplier': 2.5, 'return_delay': 80,
            'min_confidence': 0.3, 'min_size': 5,
            'use_curve': True, 'curve_speed': 8.0, 'curve_knots': 3,
        }

    if 'crosshair_color_lock' not in config:
        config['crosshair_color_lock'] = {
            'enabled': False, 'roi_width': 200, 'roi_height': 200,
            'hsv_ranges': [{'h_min': 0, 'h_max': 179, 's_min': 0, 's_max': 255,
                            'v_min': 0, 'v_max': 255}],
            'active_index': 0, 'show_crosshair': True, 'show_lock_box': True,
            'min_area': 12, 'last_rgb': [0, 0, 0],
            'pull_k': 0.12, 'pull_max_speed': 6.0, 'pull_deadzone': 1.0,
            'ema_smooth': 0.4,
        }

    ccl = config.get('crosshair_color_lock', {})
    if isinstance(ccl, dict):
        ccl.setdefault('pull_k', 0.12)
        ccl.setdefault('pull_max_speed', 6.0)
        ccl.setdefault('pull_deadzone', 1.0)

    config.setdefault('target_sticky_pixels', 40.0)
    config.setdefault('target_lock_ms', 150.0)
    config.setdefault('large_target_threshold', 0.055)
    config.setdefault('large_target_boost', 1.12)
    config.setdefault('target_id_lock_enabled', True)
    config.setdefault('kalman', {})
    config['kalman'].setdefault('enabled', True)
    config['kalman'].setdefault('predict_frames', 5)


def ensure_model_runtime_defaults(config, get_runtime_defaults_fn):
    """
    确保 model_runtime 子配置存在且包含所有默认值

    Args:
        config: 顶层配置 dict
        get_runtime_defaults_fn: 返回默认 runtime 配置的函数
    """
    runtime_cfg = config.get('model_runtime')
    if not isinstance(runtime_cfg, dict):
        runtime_cfg = {}
        config['model_runtime'] = runtime_cfg
    defaults = get_runtime_defaults_fn()
    for key, value in defaults.items():
        runtime_cfg.setdefault(key, copy.deepcopy(value))
    if not isinstance(runtime_cfg.get('v11_search_dirs'), list):
        runtime_cfg['v11_search_dirs'] = ['models', 'weights']
    return runtime_cfg


def migrate_to_class_based(config):
    """迁移全局置信阈值/IOU到基于类别的配置"""
    try:
        for group_config in config.get('groups', {}).values():
            for key_config in group_config.get('aim_keys', {}).values():
                old_conf = key_config.get('confidence_threshold')
                old_iou = key_config.get('iou_t')
                if old_conf is None and old_iou is None:
                    continue
                cap = key_config.get('class_aim_positions')
                if not isinstance(cap, dict):
                    key_config['class_aim_positions'] = {}
                    cap = key_config['class_aim_positions']
                for cls_cfg in cap.values():
                    if isinstance(cls_cfg, dict):
                        if old_conf is not None and 'confidence_threshold' not in cls_cfg:
                            cls_cfg['confidence_threshold'] = old_conf
                        if old_iou is not None and 'iou_t' not in cls_cfg:
                            cls_cfg['iou_t'] = old_iou
    except Exception as e:
        print(f'配置迁移失败: {e}')


def migrate_auto_y(config):
    """迁移 auto_y 从组级别到按键级别"""
    for group_data in config.get('groups', {}).values():
        if 'auto_y' in group_data:
            group_val = group_data['auto_y']
            for key_data in group_data.get('aim_keys', {}).values():
                if 'auto_y' not in key_data:
                    key_data['auto_y'] = group_val
