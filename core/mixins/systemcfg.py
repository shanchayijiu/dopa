# -*- coding: utf-8 -*-
"""系统配置 Mixin - 从 core.py 抽取的系统/输入设备/可观测性配置回调。

包括：灵敏度/DPI/Web服务器/推理设备/卡密/调试/曲线/评分权重/并处/turbo/跳帧/
OBS/CJK采集画面对比/本地IP检测/一键匹配/偏移边界/畸变参数/OBS帧率端口/
kmBox/kmNet/dhz/catbox网络输入设备IP端口UUID/km_com/移动方式配置。
所有方法通过 self.* 访问 Valorant 实例;通过 mix-in 继承可用。
"""
import socket
import dearpygui.dearpygui as dpg

try:
    from webui.server import start_web_server
except ImportError:
    start_web_server = None


class SystemConfigMixin:
    """系统与输入设备配置回调 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.device_info / self.engine
      self.save_config() / self.refresh_engine() (InferenceMixin)
      start_web_server (from server, 可能 None)
      get_local_ip 使用 socket 检测本机 IP
      on_one_click_match 内含局部 import threading/time (回吊线程)
    """

    def on_game_sensitivity_change(self, sender, app_data):
        return

    def on_mouse_dpi_change(self, sender, app_data):
        return

    def on_web_server_change(self, sender, app_data):
        """Web功能开关回调函数"""
        self.config['enable_web_server'] = app_data
        if app_data:
            # 启用Web服务器
            if start_web_server is not None:
                try:
                    start_web_server(self)
                    print('[Web控制面板] Web服务器已启动')
                except Exception as e:
                    print(f'[Web控制面板] 启动Web服务器失败: {e}')
            else:
                print('[Web控制面板] 未找到 web/server.py，无法启动Web服务。')
        else:
            # 禁用Web服务器
            print('[Web控制面板] Web服务器已禁用')
        self.save_config()

    def on_inference_device_change(self, sender, app_data):
        """推理设备选择回调函数"""
        if app_data:
            # 从显示文本中提取设备名称
            device_name = app_data.split(' - ')[0]
            
            # 更新配置
            old_device = self.config.get('inference_device', 'CPU')
            self.config['inference_device'] = device_name
            
            # 获取设备信息
            device_info = self.device_info.get(device_name, {})
            description = device_info.get('description', device_name)
            performance = device_info.get('performance', '未知')
            
            print(f"推理设备已切换: {old_device} -> {device_name}")
            print(f"设备描述: {description}")
            print(f"性能等级: {performance}")
            
            # 保存配置
            self.save_config()

            # 推理设备切换后立即刷新引擎，确保新 provider 生效
            try:
                if self.engine is not None:
                    self.refresh_engine()
            except Exception as e:
                print(f'切换推理设备后刷新引擎失败: {e}')
             
            # 更新界面显示
            dpg.set_value('output_text', f'推理设备已切换到: {device_name}')

    def update_sensitivity_display(self):
        return

    def calculate_sensitivity_multiplier(self):
        return 1.0

    def on_card_change(self, sender, app_data):
        print('卡密是只读的，无法修改')

    def on_infer_debug_change(self, sender, app_data):
        self.config['infer_debug'] = app_data
        print(f"changed to: {self.config['infer_debug']}")

    def on_is_curve_change(self, sender, app_data):
        self.config['is_curve'] = app_data
        print(f"changed to: {self.config['is_curve']}")

    def on_is_curve_uniform_change(self, sender, app_data):
        self.config['is_curve_uniform'] = app_data
        print(f"changed to: {self.config['is_curve_uniform']}")

    def on_distance_scoring_weight_change(self, sender, app_data):
        self.config['distance_scoring_weight'] = app_data
        self.init_target_priority()
        print(f"changed to: {self.config['distance_scoring_weight']}")

    def on_center_scoring_weight_change(self, sender, app_data):
        self.config['center_scoring_weight'] = app_data
        self.init_target_priority()
        print(f"changed to: {self.config['center_scoring_weight']}")

    def on_size_scoring_weight_change(self, sender, app_data):
        self.config['size_scoring_weight'] = app_data
        self.init_target_priority()
        print(f"changed to: {self.config['size_scoring_weight']}")

    def on_print_fps_change(self, sender, app_data):
        self.config['print_fps'] = app_data
        print(f"changed to: {self.config['print_fps']}")

    def on_show_motion_speed_change(self, sender, app_data):
        self.config['show_motion_speed'] = app_data
        self.refresh_controller_params()
        print(f"changed to: {self.config['show_motion_speed']}")

    def on_is_show_curve_change(self, sender, app_data):
        self.config['is_show_curve'] = app_data
        print(f"changed to: {self.config['is_show_curve']}")

    def on_enable_parallel_processing_change(self, sender, app_data):
        self.config['enable_parallel_processing'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('enable_parallel_processing', app_data)
        print(f"changed to: {self.config['enable_parallel_processing']}")

    def on_turbo_mode_change(self, sender, app_data):
        self.config['turbo_mode'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('turbo_mode', app_data)
        print(f"强制提速模式: {('开启' if app_data else '关闭')}")

    def on_skip_frame_processing_change(self, sender, app_data):
        self.config['skip_frame_processing'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('skip_frame_processing', app_data)
        print(f"跳过帧处理: {('开启' if app_data else '关闭')}")

    def on_is_show_down_change(self, sender, app_data):
        self.config['is_show_down'] = app_data
        print(f"changed to: {self.config['is_show_down']}")

    def on_is_obs_change(self, sender, app_data):
        self.config['is_obs'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('is_obs', app_data)
        print(f"changed to: {self.config['is_obs']}")

    def on_is_cjk_change(self, sender, app_data):
        self.config['is_cjk'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('is_cjk', app_data)
        print(f"changed to: {self.config['is_cjk']}")

    def on_obs_ip_change(self, sender, app_data):
        self.config['obs_ip'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('obs_ip', app_data)
        print(f"changed to: {self.config['obs_ip']}")

    def on_cjk_device_id_change(self, sender, app_data):
        self.config['cjk_device_id'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('cjk_device_id', app_data)
        print(f"changed to: {self.config['cjk_device_id']}")

    def on_cjk_fps_change(self, sender, app_data):
        self.config['cjk_fps'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('cjk_fps', app_data)
        print(f"changed to: {self.config['cjk_fps']}")

    def on_cjk_resolution_change(self, sender, app_data):
        self.config['cjk_resolution'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('cjk_resolution', app_data)
        print(f"changed to: {self.config['cjk_resolution']}")

    def on_cjk_crop_size_change(self, sender, app_data):
        self.config['cjk_crop_size'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('cjk_crop_size', app_data)
        print(f"changed to: {self.config['cjk_crop_size']}")

    def on_cjk_fourcc_format_change(self, sender, app_data):
        self.config['cjk_fourcc_format'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('cjk_fourcc_format', app_data)
        print(f'采集卡视频编码格式设置为: {app_data}')

    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            # 创建一个临时socket连接来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            print(f"获取本机IP失败: {e}")
            # 如果获取失败，返回默认IP
            return "127.0.0.1"

    def on_one_click_match(self, sender, app_data):
        """一键匹配功能：自动配置OBS网络参数"""
        try:
            # 获取本机IP地址
            local_ip = self.get_local_ip()
            
            # 设置固定端口为6666
            port = 6666
            
            # 设置固定帧率为144fps
            fps = 144
            
            # 更新配置
            self.config['obs_ip'] = local_ip
            self.config['obs_port'] = port
            self.config['obs_fps'] = fps
            
            # 更新界面显示
            if hasattr(self, 'obs_ip_input'):
                dpg.set_value(self.obs_ip_input, local_ip)
            if hasattr(self, 'obs_port_input'):
                dpg.set_value(self.obs_port_input, port)
            if hasattr(self, 'obs_fps_slider'):
                dpg.set_value(self.obs_fps_slider, fps)
            
            # 更新截图管理器配置
            if self.screenshot_manager:
                self.screenshot_manager.update_config('obs_ip', local_ip)
                self.screenshot_manager.update_config('obs_port', port)
                self.screenshot_manager.update_config('obs_fps', fps)
            
            # 显示成功提示
            print(f"[一键匹配] 配置成功: IP={local_ip}, 端口={port}, 帧率={fps}fps")
            
            # 添加视觉反馈 - 临时改变按钮颜色
            if self.one_click_match_button_tag:
                dpg.configure_item(self.one_click_match_button_tag, label="✓ 匹配成功")
                # 2秒后恢复原状
                import threading
                def reset_button():
                    import time
                    time.sleep(2)
                    dpg.configure_item(self.one_click_match_button_tag, label="一键匹配")
                threading.Thread(target=reset_button, daemon=True).start()
                
        except Exception as e:
            print(f"[一键匹配] 配置失败: {e}")
            # 错误反馈
            if self.one_click_match_button_tag:
                dpg.configure_item(self.one_click_match_button_tag, label="✗ 匹配失败")
                import threading
                def reset_button():
                    import time
                    time.sleep(2)
                    dpg.configure_item(self.one_click_match_button_tag, label="一键匹配")
                threading.Thread(target=reset_button, daemon=True).start()

    def on_obs_fps_change(self, sender, app_data):
        self.config['obs_fps'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('obs_fps', app_data)
        print(f"changed to: {self.config['obs_fps']}")

    def on_obs_port_change(self, sender, app_data):
        self.config['obs_port'] = app_data
        if self.screenshot_manager:
            self.screenshot_manager.update_config('obs_port', app_data)
        print(f"changed to: {self.config['obs_port']}")

    def on_offset_boundary_x_change(self, sender, app_data):
        self.config['offset_boundary_x'] = app_data
        print(f"changed to: {self.config['offset_boundary_x']}")

    def on_offset_boundary_y_change(self, sender, app_data):
        self.config['offset_boundary_y'] = app_data
        print(f"changed to: {self.config['offset_boundary_y']}")

    def on_knots_count_change(self, sender, app_data):
        self.config['knots_count'] = app_data
        print(f"changed to: {self.config['knots_count']}")

    def on_distortion_mean_change(self, sender, app_data):
        self.config['distortion_mean'] = app_data
        print(f"changed to: {self.config['distortion_mean']}")

    def on_distortion_st_dev_change(self, sender, app_data):
        self.config['distortion_st_dev'] = app_data
        print(f"changed to: {self.config['distortion_st_dev']}")

    def on_distortion_frequency_change(self, sender, app_data):
        self.config['distortion_frequency'] = app_data
        print(f"changed to: {self.config['distortion_frequency']}")

    def on_target_points_change(self, sender, app_data):
        self.config['target_points'] = app_data
        print(f"changed to: {self.config['target_points']}")

    def on_km_box_vid_change(self, sender, app_data):
        self.config['km_box_vid'] = app_data
        print(f"changed to: {self.config['km_box_vid']}")

    def on_km_box_pid_change(self, sender, app_data):
        self.config['km_box_pid'] = app_data
        print(f"changed to: {self.config['km_box_pid']}")

    def on_km_net_ip_change(self, sender, app_data):
        self.config['km_net_ip'] = app_data
        print(f"changed to: {self.config['km_net_ip']}")

    def on_km_net_port_change(self, sender, app_data):
        self.config['km_net_port'] = app_data
        print(f"changed to: {self.config['km_net_port']}")

    def on_km_net_uuid_change(self, sender, app_data):
        self.config['km_net_uuid'] = app_data
        print(f"changed to: {self.config['km_net_uuid']}")

    def on_dhz_ip_change(self, sender, app_data):
        self.config['dhz_ip'] = app_data
        print(f"changed to: {self.config['dhz_ip']}")

    def on_dhz_port_change(self, sender, app_data):
        self.config['dhz_port'] = app_data
        print(f"changed to: {self.config['dhz_port']}")

    def on_dhz_random_change(self, sender, app_data):
        self.config['dhz_random'] = app_data
        print(f"changed to: {self.config['dhz_random']}")

    def on_catbox_ip_change(self, sender, app_data):
        self.config['catbox_ip'] = app_data
        print(f"changed to: {self.config['catbox_ip']}")

    def on_catbox_port_change(self, sender, app_data):
        self.config['catbox_port'] = app_data
        print(f"changed to: {self.config['catbox_port']}")

    def on_catbox_uuid_change(self, sender, app_data):
        self.config['catbox_uuid'] = app_data
        print(f"changed to: {self.config['catbox_uuid']}")

    def on_km_com_change(self, sender, app_data):
        self.config['km_com'] = app_data
        print(f"changed to: {self.config['km_com']}")

    def on_move_method_change(self, sender, app_data):
        self.config['move_method'] = app_data
        print(f"changed to: {self.config['move_method']}")

    def on_single_machine_mode_change(self, sender, app_data):
        """切换单机测试模式；输入后端在下一次启动时应用。"""
        self.config['single_machine_mode'] = bool(app_data)
        mode = '开启' if self.config['single_machine_mode'] else '关闭'
        print(f'单机测试模式已{mode}，下次启动时生效')
        self.save_config()
