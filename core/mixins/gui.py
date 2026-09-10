# -*- coding: utf-8 -*-
"""GUI 构建 Mixin — 从 core.py 提取 gui() 与其内部 switch_tab 闭包。

gui() 构建整个 DearPyGui 界面（tab 切换由嵌套 switch_tab 处理）。所有 dpg
回调通过 self.on_xxx 绑定（继承可达），switch_tab 作为本地闭包随块一起搬移。
"""
import random
import string
import dearpygui.dearpygui as dpg

# 模块级符号（在 core.py 顶部 L8/L18/L198/L213/L214 已定义，延迟导入安全）
from ..runtime import create_gradient_image, VERSION, UPDATE_TIME


class GUIMixin:
    """GUI 构建 Mixin。gui() 构建主窗口；switch_tab 为本地闭包切换 tab。"""
    def gui(self):
        title = ''.join(random.sample(string.ascii_letters + string.digits, 8)).join(VERSION)
        dpg.create_context()
        gradient_path = create_gradient_image(self.gui_window_width, self.scaled_bar_height)
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(8, 12, [0] * 384, tag='checkbox_texture')
        with dpg.texture_registry():
            width, height, channels, data = dpg.load_image(gradient_path)
            texture_id = dpg.add_static_texture(width, height, data)
        with dpg.font_registry():
            with dpg.font('assets/ChillBitmap_16px.ttf', self.scaled_font_size_main) as msyh:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Full)
                dpg.bind_font(msyh)
            custom_font = dpg.add_font('assets/undefeated.ttf', self.scaled_font_size_custom)
        with dpg.theme() as tab_bar_theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (45, 45, 45, 255))
                dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 0)
        with dpg.theme() as skeet_theme:
            with dpg.theme_component(dpg.mvCheckbox):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (75, 75, 75, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (95, 95, 95, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (154, 197, 39, 255))
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (203, 203, 203, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 1, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (35, 35, 35, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (65, 65, 65, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (25, 25, 25, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (50, 50, 50, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (203, 203, 203, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (150, 150, 150, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 5, 3)
            with dpg.theme_component(dpg.mvInputInt):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (65, 65, 65, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (85, 85, 85, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (203, 203, 203, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 4, 4)
            with dpg.theme_component(dpg.mvCombo):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (45, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (65, 65, 65, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (85, 85, 85, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (203, 203, 203, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 255))
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (35, 35, 35, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 4, 4)
        dpg.create_viewport(title=title, width=self.gui_window_width, height=self.gui_window_height)
        dpg.setup_dearpygui()

        def switch_tab(sender, app_data, user_data):
            """ 切换到对应的 Tab """
            tabs = ['system_settings', 'driver_settings', 'bypass_settings', 'strafe_settings', 'config_settings']
            for tab in tabs:
                dpg.configure_item(tab, show=False)
            dpg.configure_item(user_data, show=True)
            try:
                dpg.set_y_scroll(tab_bar_container, 0)
            except Exception:
                pass
        with dpg.window(label=title, no_title_bar=True, no_resize=True, no_move=True, width=self.gui_window_width, height=self.gui_window_height) as self.window_tag:
            dpg.draw_image(texture_id, (0, 0), (self.gui_window_width, self.scaled_bar_height))
            with dpg.group(horizontal=True):
                with dpg.child_window(width=self.scaled_sidebar_width, height=self.gui_window_height - 120):
                    button_size = int(50 * self.dpi_scale)
                    system = dpg.add_button(label='s', width=button_size, height=button_size, callback=switch_tab, user_data='system_settings')
                    driver = dpg.add_button(label='v', width=button_size, height=button_size, callback=switch_tab, user_data='driver_settings')
                    bypass = dpg.add_button(label='o', width=button_size, height=button_size, callback=switch_tab, user_data='bypass_settings')
                    strafe = dpg.add_button(label='W', width=button_size, height=button_size, callback=switch_tab, user_data='strafe_settings')
                    config = dpg.add_button(label='u', width=button_size, height=button_size, callback=switch_tab, user_data='config_settings')
                    dpg.bind_item_font(system, custom_font)
                    dpg.bind_item_font(driver, custom_font)
                    dpg.bind_item_font(bypass, custom_font)
                    dpg.bind_item_font(strafe, custom_font)
                    dpg.bind_item_font(config, custom_font)
                with dpg.child_window(width=self.gui_window_width - self.scaled_sidebar_width, height=self.gui_window_height - 120) as tab_bar_container:
                    dpg.bind_item_theme(tab_bar_container, tab_bar_theme)
                    dpg.bind_theme(skeet_theme)
                    with dpg.group(tag='tab_bar_group'):
                        with dpg.group(tag='system_settings', show=True):
                            with dpg.group(horizontal=True):
                                self.dpi_scale_slider = dpg.add_slider_float(label='GUI DPI缩放', default_value=self.dpi_scale, min_value=0.5, max_value=3.0, format='%.2f', callback=self.on_gui_dpi_scale_change, width=self.scaled_width_xlarge)
                                dpg.add_button(label='自动检测', callback=self.on_reset_dpi_scale_click)
                            dpg.add_text(f'调整GUI界面的缩放大小 (当前系统检测: {self.get_system_dpi_scale():.2f}, 重启后生效)')
                            dpg.add_separator()
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='推理窗口', default_value=self.config['infer_debug'], callback=self.on_infer_debug_change)
                                dpg.add_checkbox(label='打印帧率', default_value=self.config['print_fps'], callback=self.on_print_fps_change)
                                dpg.add_checkbox(label='显示运动速度', default_value=self.config['show_motion_speed'], callback=self.on_show_motion_speed_change)
                                dpg.add_checkbox(label='显示曲线', default_value=self.config['is_show_curve'], callback=self.on_is_show_curve_change)
                                dpg.add_checkbox(label='显示推理时间', default_value=self.config.get('show_infer_time', True), callback=self.on_show_infer_time_change)
                                dpg.add_checkbox(label='截图分离(多线程)', default_value=self.config.get('enable_parallel_processing', True), callback=self.on_enable_parallel_processing_change)
                                dpg.add_checkbox(label='Web功能', default_value=self.config.get('enable_web_server', False), callback=self.on_web_server_change)
                            dpg.add_separator()
                            
                            # 推理设备选择
                            dpg.add_text('推理设备设置', color=(100, 200, 255))
                            with dpg.group(horizontal=True):
                                # 创建设备选择下拉框
                                device_items = []
                                for device in self.available_devices:
                                    device_info = self.device_info.get(device, {})
                                    description = device_info.get('description', device)
                                    device_items.append(f"{device} - {description}")
                                
                                # 获取当前选择的设备显示文本
                                current_device = self.config.get('inference_device', 'CPU')
                                current_device_info = self.device_info.get(current_device, {})
                                current_display = f"{current_device} - {current_device_info.get('description', current_device)}"
                                
                                self.inference_device_combo = dpg.add_combo(
                                    items=device_items,
                                    label='推理设备',
                                    default_value=current_display,
                                    callback=self.on_inference_device_change,
                                    width=self.scaled_width_xlarge
                                )
                            
                            dpg.add_separator()
                            dpg.add_text('小目标识别增强设置', color=(100, 200, 255))
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='启用小目标识别增强', tag='small_target_enabled_checkbox', default_value=self.config['small_target_enhancement']['enabled'], callback=self.on_small_target_enabled_change)
                                dpg.add_checkbox(label='启用小目标平滑', tag='small_target_smooth_checkbox', default_value=self.config['small_target_enhancement']['smooth_enabled'], callback=self.on_small_target_smooth_change)
                                dpg.add_checkbox(label='自适应NMS', tag='small_target_nms_checkbox', default_value=self.config['small_target_enhancement']['adaptive_nms'], callback=self.on_small_target_nms_change)
                            with dpg.group(horizontal=True):
                                dpg.add_slider_float(label='小目标增强倍数', tag='small_target_boost_slider', default_value=self.config['small_target_enhancement']['boost_factor'], min_value=1.0, max_value=3.0, format='%.1f', callback=self.on_small_target_boost_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='平滑历史帧数', tag='small_target_frames_slider', default_value=self.config['small_target_enhancement']['smooth_frames'], min_value=2, max_value=8, callback=self.on_small_target_frames_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_slider_float(label='小目标阈值', tag='small_target_threshold_slider', default_value=self.config['small_target_enhancement']['threshold'], min_value=0.001, max_value=0.05, format='%.3f', callback=self.on_small_target_threshold_change, width=self.scaled_width_normal)
                                dpg.add_slider_float(label='中等目标阈值', tag='medium_target_threshold_slider', default_value=self.config['small_target_enhancement']['medium_threshold'], min_value=0.01, max_value=0.1, format='%.3f', callback=self.on_medium_target_threshold_change, width=self.scaled_width_normal)
                            dpg.add_text('说明：小目标识别增强可以提高对远距离或小尺寸目标的检测稳定性', color=(150, 150, 150), wrap=self.scaled_width_xlarge)
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='强制提速模式', default_value=self.config.get('turbo_mode', True), callback=self.on_turbo_mode_change)
                                dpg.add_checkbox(label='跳过帧处理', default_value=self.config.get('skip_frame_processing', True), callback=self.on_skip_frame_processing_change)
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='压枪调试', default_value=self.config['is_show_down'], callback=self.on_is_show_down_change)
                                dpg.add_checkbox(label='类别优先级调试', default_value=self.config.get('is_show_priority_debug', False), callback=self.on_is_show_priority_debug_change)
                                dpg.add_checkbox(label='显示瞄准范围', default_value=self.config.get('show_fov', True), callback=self.on_show_fov_change)
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='OBS', default_value=self.config['is_obs'], callback=self.on_is_obs_change)
                                dpg.add_spacer(width=10)
                                self.one_click_match_button_tag = dpg.add_button(label='一键匹配', callback=self.on_one_click_match, width=self.scaled_width_medium)
                            with dpg.group(horizontal=True):
                                self.obs_ip_input = dpg.add_input_text(label='OBS IP', default_value=self.config['obs_ip'], callback=self.on_obs_ip_change, width=self.scaled_width_normal)
                                self.obs_port_input = dpg.add_input_int(label='OBS 端口', default_value=self.config['obs_port'], callback=self.on_obs_port_change, width=self.scaled_width_normal)
                                self.obs_fps_slider = dpg.add_slider_int(label='OBS 帧率', default_value=self.config['obs_fps'], min_value=1, max_value=240, callback=self.on_obs_fps_change, width=self.scaled_width_normal)
                            dpg.add_checkbox(label='采集卡', default_value=self.config['is_cjk'], callback=self.on_is_cjk_change)
                            with dpg.group(horizontal=True):
                                dpg.add_input_int(label='采集卡设备', default_value=self.config['cjk_device_id'], callback=self.on_cjk_device_id_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='采集卡FPS', default_value=self.config['cjk_fps'], min_value=1, max_value=240, callback=self.on_cjk_fps_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='采集卡分辨率', default_value=self.config['cjk_resolution'], callback=self.on_cjk_resolution_change, width=self.scaled_width_medium)
                                dpg.add_input_text(label='采集卡裁剪尺寸', default_value=self.config['cjk_crop_size'], callback=self.on_cjk_crop_size_change, width=self.scaled_width_medium)
                            dpg.add_input_text(label='视频编码格式', default_value=self.config.get('cjk_fourcc_format', 'NV12'), callback=self.on_cjk_fourcc_format_change, width=self.scaled_width_medium, hint='如: NV12, MJPG, YUYV')
                            dpg.add_checkbox(label='单机测试模式', default_value=self.config.get('single_machine_mode', False), callback=self.on_single_machine_mode_change)
                            dpg.add_text('开启后启动时强制使用本机 send_input，跳过外置输入设备；修改后下次启动生效。', color=(150, 150, 150), wrap=self.scaled_width_xlarge)
                            dpg.add_text('目标选择器')
                            with dpg.group(horizontal=True):
                                self.target_sticky_pixels_slider = dpg.add_slider_float(label='目标黏性(px)', default_value=float(self.config.get('target_sticky_pixels', 40.0)), min_value=0.0, max_value=120.0, format='%.0f', callback=self.on_target_sticky_pixels_change, width=self.scaled_width_normal)
                                self.target_lock_ms_slider = dpg.add_slider_float(label='锁定时间(ms)', default_value=float(self.config.get('target_lock_ms', 150.0)), min_value=0.0, max_value=500.0, format='%.0f', callback=self.on_target_lock_ms_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                self.target_id_lock_checkbox = dpg.add_checkbox(label='目标ID强锁定', default_value=bool(self.config.get('target_id_lock_enabled', True)), callback=self.on_target_id_lock_change)
                            dpg.add_separator()
                            dpg.add_text('自动背闪设置')
                            is_dopa = self.is_using_dopa_model()
                            dopa_status_text = '当前使用ZTX模型，功能可用' if is_dopa else '当前未使用ZTX模型，功能不可用'
                            dopa_color = (0, 255, 0) if is_dopa else (255, 100, 100)
                            dpg.add_text(f'注意：此功能仅支持ZTX模型 - {dopa_status_text}', color=dopa_color, wrap=self.scaled_width_xlarge)
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='启用自动背闪', tag='auto_flashbang_enabled_checkbox', default_value=self.config['auto_flashbang']['enabled'] and is_dopa, enabled=is_dopa, callback=self.on_auto_flashbang_enabled_change)
                                dpg.add_slider_int(label='背闪延迟(毫秒)', tag='auto_flashbang_delay_slider', default_value=self.config['auto_flashbang']['delay_ms'], min_value=50, max_value=1000, enabled=is_dopa, callback=self.on_auto_flashbang_delay_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='转向角度', tag='auto_flashbang_angle_slider', default_value=self.config['auto_flashbang']['turn_angle'], min_value=45, max_value=135, enabled=is_dopa, callback=self.on_auto_flashbang_angle_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_slider_float(label='灵敏度倍数', tag='auto_flashbang_sensitivity_slider', default_value=self.config['auto_flashbang']['sensitivity_multiplier'], min_value=0.5, max_value=5.0, format='%.1f', enabled=is_dopa, callback=self.on_auto_flashbang_sensitivity_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='回转延迟(毫秒)', tag='auto_flashbang_return_delay_slider', default_value=self.config['auto_flashbang']['return_delay'], min_value=100, max_value=1000, enabled=is_dopa, callback=self.on_auto_flashbang_return_delay_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='使用曲线移动', tag='auto_flashbang_curve_checkbox', default_value=self.config['auto_flashbang']['use_curve'], enabled=is_dopa, callback=self.on_auto_flashbang_curve_change)
                                dpg.add_slider_float(label='曲线速度', tag='auto_flashbang_curve_speed_slider', default_value=self.config['auto_flashbang']['curve_speed'], min_value=0.1, max_value=2.0, format='%.1f', enabled=is_dopa, callback=self.on_auto_flashbang_curve_speed_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='控制点数量', tag='auto_flashbang_curve_knots_slider', default_value=self.config['auto_flashbang']['curve_knots'], min_value=5, max_value=50, enabled=is_dopa, callback=self.on_auto_flashbang_curve_knots_change, width=self.scaled_width_normal)
                            dpg.add_text('过滤条件（调整这些参数可以改变触发灵敏度）')
                            with dpg.group(horizontal=True):
                                dpg.add_slider_float(label='最小置信度', tag='auto_flashbang_min_confidence_slider', default_value=self.config['auto_flashbang']['min_confidence'], min_value=0.1, max_value=0.9, format='%.2f', enabled=is_dopa, callback=self.on_auto_flashbang_min_confidence_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='最小尺寸(像素)', tag='auto_flashbang_min_size_slider', default_value=self.config['auto_flashbang']['min_size'], min_value=1, max_value=50, enabled=is_dopa, callback=self.on_auto_flashbang_min_size_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_button(label='测试左转', tag='auto_flashbang_test_left_button', enabled=is_dopa, callback=self.on_test_flashbang_left)
                                dpg.add_button(label='测试右转', tag='auto_flashbang_test_right_button', enabled=is_dopa, callback=self.on_test_flashbang_right)
                                dpg.add_button(label='调试信息', tag='auto_flashbang_debug_button', enabled=is_dopa, callback=self.on_flashbang_debug_info)
                        with dpg.group(tag='driver_settings', show=False):
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label='移动曲线', default_value=self.config['is_curve'], callback=self.on_is_curve_change)
                                dpg.add_checkbox(label='补偿曲线', default_value=self.config['is_curve_uniform'], callback=self.on_is_curve_uniform_change)
                                dpg.add_slider_int(label='横向边界', default_value=self.config['offset_boundary_x'], min_value=0, max_value=100, callback=self.on_offset_boundary_x_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='纵向边界', default_value=self.config['offset_boundary_y'], min_value=0, max_value=100, callback=self.on_offset_boundary_y_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_slider_int(label='控制点数量', default_value=self.config['knots_count'], min_value=2, max_value=20, callback=self.on_knots_count_change, width=self.scaled_width_normal)
                                dpg.add_slider_float(label='扰动的平均值', default_value=self.config['distortion_mean'], min_value=0.0, max_value=10.0, format='%.2f', callback=self.on_distortion_mean_change, width=self.scaled_width_normal)
                                dpg.add_slider_float(label='扰动的标准差', default_value=self.config['distortion_st_dev'], min_value=0.0, max_value=5.0, format='%.2f', callback=self.on_distortion_st_dev_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_slider_float(label='扰动的频率', default_value=self.config['distortion_frequency'], min_value=0.0, max_value=10.0, format='%.2f', callback=self.on_distortion_frequency_change, width=self.scaled_width_normal)
                                dpg.add_slider_int(label='路径点总数', default_value=self.config['target_points'], min_value=10, max_value=100, callback=self.on_target_points_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='KM Box VID', default_value=self.config['km_box_vid'], callback=self.on_km_box_vid_change, width=self.scaled_width_small)
                                dpg.add_input_text(label='KM Box PID', default_value=self.config['km_box_pid'], callback=self.on_km_box_pid_change, width=self.scaled_width_small)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='KM Net IP', default_value=self.config['km_net_ip'], callback=self.on_km_net_ip_change, width=self.scaled_width_large)
                                dpg.add_input_text(label='KM Net Port', default_value=self.config['km_net_port'], callback=self.on_km_net_port_change, width=self.scaled_width_small)
                                dpg.add_input_text(label='KM Net UUID', default_value=self.config['km_net_uuid'], callback=self.on_km_net_uuid_change, width=self.scaled_width_medium)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='DHZ IP', default_value=self.config['dhz_ip'], callback=self.on_dhz_ip_change, width=self.scaled_width_large)
                                dpg.add_input_int(label='DHZ Port', default_value=self.config['dhz_port'], callback=self.on_dhz_port_change, width=self.scaled_width_normal)
                                dpg.add_input_int(label='DHZ RANDOM', default_value=self.config['dhz_random'], callback=self.on_dhz_random_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='CatBox IP', default_value=self.config['catbox_ip'], callback=self.on_catbox_ip_change, width=self.scaled_width_large)
                                dpg.add_input_int(label='CatBox Port', default_value=self.config['catbox_port'], callback=self.on_catbox_port_change, width=self.scaled_width_normal)
                                dpg.add_input_text(label='CatBox UUID', default_value=self.config['catbox_uuid'], callback=self.on_catbox_uuid_change, width=self.scaled_width_medium)
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label='COM', default_value=self.config['km_com'], callback=self.on_km_com_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True):
                                dpg.add_combo(label='移动模式', items=['send_input', 'dhz', 'km_net', 'pnmh', 'km_box_a', 'logitech', 'makcu', 'catbox'], default_value=self.config['move_method'], callback=self.on_move_method_change, width=self.scaled_width_large)
                        with dpg.group(tag='bypass_settings', show=False):
                            with dpg.group(horizontal=True):
                                self.mask_left_checkbox = dpg.add_checkbox(label='屏蔽左键', default_value=self.config['mask_left'], callback=self.on_mask_left_change)
                                self.mask_right_checkbox = dpg.add_checkbox(label='屏蔽右键', default_value=self.config['mask_right'], callback=self.on_mask_right_change)
                                self.mask_middle_checkbox = dpg.add_checkbox(label='屏蔽中键', default_value=self.config['mask_middle'], callback=self.on_mask_middle_change)
                                self.mask_side1_checkbox = dpg.add_checkbox(label='屏蔽侧键1', default_value=self.config['mask_side1'], callback=self.on_mask_side1_change)
                                self.mask_side2_checkbox = dpg.add_checkbox(label='屏蔽侧键2', default_value=self.config['mask_side2'], callback=self.on_mask_side2_change)
                            with dpg.group(horizontal=True):
                                self.mask_x_checkbox = dpg.add_checkbox(label='屏蔽X轴', default_value=self.config['mask_x'], callback=self.on_mask_x_change)
                                self.mask_y_checkbox = dpg.add_checkbox(label='屏蔽Y轴', default_value=self.config['mask_y'], callback=self.on_mask_y_change)
                                self.aim_mask_x_checkbox = dpg.add_checkbox(label='瞄准时屏蔽X轴', default_value=self.config['aim_mask_x'], callback=self.on_aim_mask_x_change)
                                self.aim_mask_y_checkbox = dpg.add_checkbox(label='瞄准时屏蔽Y轴', default_value=self.config['aim_mask_y'], callback=self.on_aim_mask_y_change)
                                self.mask_wheel_checkbox = dpg.add_checkbox(label='屏蔽滚轮', default_value=self.config['mask_wheel'], callback=self.on_mask_wheel_change)
                        with dpg.group(tag='strafe_settings', show=False):
                            self.right_down_checkbox = dpg.add_checkbox(label='检测右键', callback=self.on_right_down_change)
                            with dpg.group(horizontal=True):
                                with dpg.group() as self.dpg_games_tag:
                                    self.render_games_combo()
                                dpg.add_button(label='删除游戏', callback=self.on_delete_game_click, width=self.scaled_width_60)
                                dpg.add_input_text(label='游戏名', callback=self.on_game_name_change, width=self.scaled_width_60)
                                dpg.add_button(label='添加游戏', callback=self.on_add_game_click, width=self.scaled_width_60)
                            with dpg.group(horizontal=True):
                                with dpg.group() as self.dpg_guns_tag:
                                    self.render_guns_combo()
                                dpg.add_button(label='删除枪械', callback=self.on_delete_gun_click, width=self.scaled_width_60)
                                dpg.add_input_text(label='枪械名', callback=self.on_gun_name_change, width=self.scaled_width_60)
                                dpg.add_button(label='添加枪械', callback=self.on_add_gun_click, width=self.scaled_width_60)
                            with dpg.group(horizontal=True):
                                with dpg.group() as self.dpg_stages_tag:
                                    self.render_stages_combo()
                                number = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['number']
                                x = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][0]
                                y = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][1]
                            with dpg.group(horizontal=True):
                                self.number_input = dpg.add_input_int(label='次', callback=self.on_number_change, default_value=number, width=self.scaled_width_normal)
                                self.x_input = dpg.add_input_float(label='X', step=0.01, callback=self.on_x_change, default_value=x, width=self.scaled_width_normal)
                                self.y_input = dpg.add_input_float(label='Y', step=0.01, callback=self.on_y_change, default_value=y, width=self.scaled_width_normal)
                                dpg.add_button(label='删除索引', callback=self.on_delete_stage_click, width=self.scaled_width_60)
                                dpg.add_button(label='添加索引', callback=self.on_add_stage_click, width=self.scaled_width_60)
                            dpg.add_separator()
                            with dpg.collapsing_header(label='mouse_re轨迹压枪', default_open=True):
                                with dpg.group(horizontal=True):
                                    dpg.add_checkbox(label='启用mouse_re轨迹压枪', default_value=self.config['recoil']['use_mouse_re_trajectory'], callback=self.on_use_mouse_re_trajectory_change)
                                    dpg.add_slider_float(label='回放速度', default_value=self.config['recoil']['replay_speed'], min_value=0.1, max_value=5.0, format='%.2f', width=self.scaled_width_normal, callback=self.on_mouse_re_replay_speed_change)
                                    dpg.add_slider_float(label='像素增强比例', default_value=self.config['recoil']['pixel_enhancement_ratio'], min_value=0.1, max_value=3.0, format='%.2f', width=self.scaled_width_normal, callback=self.on_mouse_re_pixel_enhancement_change)
                                dpg.add_text('mouse_re压枪配置:', color=(150, 150, 150))
                                with dpg.group(horizontal=True, tag='mouse_re_combos_group'):
                                    pass
                                with dpg.group(horizontal=True):
                                    dpg.add_button(label='导入轨迹文件', callback=self.on_import_mouse_re_trajectory_click, width=self.scaled_width_normal)
                                    dpg.add_button(label='清除映射', callback=self.on_clear_mouse_re_mapping_click, width=self.scaled_width_normal)
                                dpg.add_text('说明：支持加载由 mouse_re.py 生成的JSON文件，按住左键将按轨迹回放进行压枪')
                                dpg.add_separator()
                                dpg.add_text('当前状态:', color=(150, 150, 150))
                                dpg.add_text('开关: 关', tag='mouse_re_switch_text')
                                dpg.add_text('映射文件: 无', wrap=self.scaled_width_xlarge, tag='mouse_re_file_text')
                                dpg.add_text('轨迹点数: 0', tag='mouse_re_points_text')
                        with dpg.child_window(tag='config_settings', show=False, border=False, height=self.gui_window_height - 120 - int(60 * self.dpi_scale)):
                            model_params_group = dpg.add_collapsing_header(label='模型控制器参数', default_open=True)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                with dpg.group() as self.dpg_group_tag:
                                    self.render_group_combo()
                                dpg.add_button(label='删除组', callback=self.on_delete_group_click, width=self.scaled_width_60)
                                dpg.add_input_text(label='组名', callback=self.on_group_name_change, width=self.scaled_width_60)
                                dpg.add_button(label='添加组', callback=self.on_add_group_click, width=self.scaled_width_60)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.is_trt_checkbox = dpg.add_checkbox(label='TRT', callback=self.on_is_trt_change)
                                self.is_v8_checkbox = dpg.add_checkbox(label='V8', callback=self.on_is_v8_change)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.infer_model_input = dpg.add_input_text(label='推理模型', default_value=self.config['groups'][self.group]['infer_model'], callback=self.on_infer_model_change, width=self.scaled_width_xlarge + 50)
                                dpg.add_button(label='选择模型', callback=self.on_select_model_click, width=100)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.auto_y_checkbox = dpg.add_checkbox(label='长按左键不锁Y轴', callback=self.on_auto_y_change)
                                self.use_crosshair_checkbox = dpg.add_checkbox(label='准星找色', default_value=True, callback=self.on_use_crosshair_change)
                                with dpg.tooltip(self.use_crosshair_checkbox):
                                    dpg.add_text('为当前按键启用/禁用准星找色回拉')
                                self.long_press_duration_slider = dpg.add_slider_int(label='长按判断阈值', default_value=self.config['groups'][self.group]['long_press_duration'], min_value=100, max_value=5000, callback=self.on_long_press_duration_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.target_switch_delay_slider = dpg.add_slider_int(label='目标转移延迟(ms)', default_value=0, min_value=0, max_value=2000, callback=self.on_target_switch_delay_change, width=self.scaled_width_normal)
                                self.target_reference_class_combo = dpg.add_combo(label='目标参考类别', items=['类别0'], default_value='类别0', callback=self.on_target_reference_class_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                with dpg.group() as self.aim_key_combo_group:
                                    self.render_key_combo()
                                dpg.add_button(label='删除键', callback=self.on_delete_key_click, width=self.scaled_width_60)
                                # 优化按键绑定按钮布局 - 按钮和状态文本在同一行显示
                                self.key_binding_button_tag = dpg.add_button(label='绑定', callback=self.on_key_binding_button_click, width=self.scaled_width_60)
                                # 添加小间距确保文本紧贴按钮右侧
                                dpg.add_spacer(width=5)
                                self.key_binding_status_tag = dpg.add_text("等待绑定", color=[255, 255, 0])
                                # 添加适当的间距保持布局平衡
                                dpg.add_spacer(width=15)
                            dpg.add_separator()
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.class_priority_input = dpg.add_input_text(label='类别优先级', hint='格式: 0-1-2-3-4', default_value='', callback=self.on_class_priority_change, width=self.scaled_width_large)
                                dpg.add_text('推理类别：')
                                self.checkbox_group_tag = dpg.add_group(horizontal=True)
                                class_num = self.get_current_class_num()
                                class_ary = list(range(class_num))
                                self.create_checkboxes(class_ary)
                                self.update_class_aim_combo()
                                self.update_target_reference_class_combo()
                            with dpg.group(horizontal=True, parent=model_params_group):
                                dpg.add_text('类别瞄准配置:')
                                self.class_aim_combo = dpg.add_combo(items=[], label='选择类别', callback=self.on_class_aim_combo_change, width=self.scaled_width_normal, default_value='')
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.confidence_threshold_slider = dpg.add_slider_float(label='置信阈值', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_confidence_threshold_change, width=self.scaled_width_normal)
                                self.iou_t_slider = dpg.add_slider_float(label='IOU', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_iou_t_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.aim_bot_position_slider = dpg.add_slider_float(label='瞄准部位', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_aim_bot_position_change, width=self.scaled_width_normal)
                                self.aim_bot_position2_slider = dpg.add_slider_float(label='瞄准部位2', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_aim_bot_position2_change, width=self.scaled_width_normal)
                            # ═══ 瞄准行为 ═══
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.min_position_offset_slider = dpg.add_slider_int(label='最小偏移', min_value=0, max_value=100, callback=self.on_min_position_offset_change, width=self.scaled_width_normal)
                                self.aim_bot_scope_slider = dpg.add_slider_int(label='瞄准范围', min_value=0, max_value=1000, callback=self.on_aim_bot_scope_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.dynamic_scope_enabled_input = dpg.add_checkbox(label='动态范围', callback=self.on_dynamic_scope_enabled_change)
                                self.dynamic_scope_min_scope_slider = dpg.add_slider_int(label='最小范围', min_value=0, max_value=2000, callback=self.on_dynamic_scope_min_scope_change, width=self.scaled_width_normal)
                                self.dynamic_scope_shrink_ms_slider = dpg.add_slider_int(label='收缩时长', min_value=0, max_value=5000, callback=self.on_dynamic_scope_shrink_ms_change, width=self.scaled_width_normal)
                                self.dynamic_scope_recover_ms_slider = dpg.add_slider_int(label='恢复时长', min_value=0, max_value=5000, callback=self.on_dynamic_scope_recover_ms_change, width=self.scaled_width_normal)
                            # ═══ 目标参数 ═══
                            with dpg.group(horizontal=True, parent=model_params_group):
                                self.large_target_threshold_slider = dpg.add_slider_float(label='大目标阈值', min_value=0.0, max_value=0.30, default_value=float(self.config.get('large_target_threshold', 0.055)), format='%.3f', callback=self.on_large_target_threshold_change, width=self.scaled_width_normal)
                                self.large_target_boost_slider = dpg.add_slider_float(label='大目标加权', min_value=1.0, max_value=2.5, default_value=float(self.config.get('large_target_boost', 1.12)), format='%.2f', callback=self.on_large_target_boost_change, width=self.scaled_width_normal)
                            self.pid_params_group = dpg.add_collapsing_header(label='PID控制器参数', default_open=True)
                            dpg.add_text('PID参数', parent=self.pid_params_group)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.pid_kp_x_slider = dpg.add_slider_float(label='X轴比例', default_value=0.4, min_value=0.0, max_value=1.0, format='%.4f', callback=self.on_pid_kp_x_change, width=self.scaled_width_normal)
                                self.pid_ki_x_slider = dpg.add_slider_float(label='X轴积分', default_value=0.0, min_value=0.0, max_value=0.5, format='%.4f', callback=self.on_pid_ki_x_change, width=self.scaled_width_normal)
                                self.pid_kd_x_slider = dpg.add_slider_float(label='X轴微分', default_value=0.002, min_value=0.0, max_value=0.05, format='%.4f', callback=self.on_pid_kd_x_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.pid_kp_y_slider = dpg.add_slider_float(label='Y轴比例', default_value=0.4, min_value=0.0, max_value=1.0, format='%.4f', callback=self.on_pid_kp_y_change, width=self.scaled_width_normal)
                                self.pid_ki_y_slider = dpg.add_slider_float(label='Y轴积分', default_value=0, min_value=0.0, max_value=0.5, format='%.4f', callback=self.on_pid_ki_y_change, width=self.scaled_width_normal)
                                self.pid_kd_y_slider = dpg.add_slider_float(label='Y轴微分', default_value=0.002, min_value=0.0, max_value=0.05, format='%.4f', callback=self.on_pid_kd_y_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.pid_integral_limit_x_slider = dpg.add_slider_float(label='X轴限幅', default_value=0.0, min_value=0.0, max_value=50.0, format='%.4f', callback=self.on_pid_integral_limit_x_change, width=self.scaled_width_normal)
                                self.smooth_x_slider = dpg.add_slider_float(label='X轴平滑', default_value=0, min_value=0.0, max_value=500.0, format='%.4f', callback=self.on_smooth_x_change, width=self.scaled_width_normal)
                                self.smooth_algorithm_slider = dpg.add_slider_float(label='平滑算法', default_value=1.0, min_value=0.1, max_value=5.0, format='%.4f', callback=self.on_smooth_algorithm_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.pid_integral_limit_y_slider = dpg.add_slider_float(label='Y轴限幅', default_value=0.0, min_value=0.0, max_value=50.0, format='%.4f', callback=self.on_pid_integral_limit_y_change, width=self.scaled_width_normal)
                                self.smooth_y_slider = dpg.add_slider_float(label='Y轴平滑', default_value=0, min_value=0.0, max_value=500.0, format='%.4f', callback=self.on_smooth_y_change, width=self.scaled_width_normal)
                                self.smooth_deadzone_slider = dpg.add_slider_float(label='平滑禁区', default_value=0.0, min_value=0.0, max_value=25.0, format='%.4f', callback=self.on_smooth_deadzone_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.move_deadzone_slider = dpg.add_slider_float(label='移动死区', default_value=1.0, min_value=0.0, max_value=10.0, format='%.4f', callback=self.on_move_deadzone_change, width=self.scaled_width_normal)
                            with dpg.group(horizontal=True, parent=self.pid_params_group):
                                self.pid_error_filter_alpha_slider = dpg.add_slider_float(label='误差滤波', default_value=float(self.pressed_key_config.get('pid_error_filter_alpha', 0.0)), min_value=0.0, max_value=0.95, format='%.2f', callback=self.on_pid_error_filter_alpha_change, width=self.scaled_width_normal)
                                self.pid_vel_filter_alpha_slider = dpg.add_slider_float(label='速度滤波', default_value=float(self.pressed_key_config.get('pid_vel_filter_alpha', 0.0)), min_value=0.0, max_value=0.95, format='%.2f', callback=self.on_pid_vel_filter_alpha_change, width=self.scaled_width_normal)
                            tracker_group = dpg.add_collapsing_header(label='目标跟踪 (ByteTrack)', default_open=False, parent=self.pid_params_group)
                            with dpg.group(parent=tracker_group):
                                with dpg.group(horizontal=True):
                                    self.tracker_enabled_checkbox = dpg.add_checkbox(label='启用跟踪器', default_value=bool(self.pressed_key_config.get('tracker_enabled', True)), callback=self.on_tracker_enabled_change)
                                    self.tracker_match_thresh_slider = dpg.add_slider_float(label='IoU匹配阈值', default_value=float(self.pressed_key_config.get('tracker_match_thresh', 0.3)), min_value=0.05, max_value=1.0, format='%.2f', callback=self.on_tracker_match_thresh_change, width=self.scaled_width_normal)
                                    self.tracker_track_buffer_slider = dpg.add_slider_int(label='丢失保留帧数', default_value=int(self.pressed_key_config.get('tracker_track_buffer', 30)), min_value=1, max_value=120, callback=self.on_tracker_track_buffer_change, width=self.scaled_width_normal)
                            kalman_group = dpg.add_collapsing_header(label='移动预测', default_open=False, parent=self.pid_params_group)
                            with dpg.group(parent=kalman_group):
                                with dpg.group(horizontal=True):
                                    self.kalman_enabled_checkbox = dpg.add_checkbox(label='启用移动预测', default_value=bool(self.config.get('kalman', {}).get('enabled', True)), callback=self.on_kalman_enabled_change)
                                    self.kalman_predict_frames_slider = dpg.add_slider_int(label='预测系数', default_value=int(self.config.get('kalman', {}).get('predict_frames', 5)), min_value=0, max_value=20, callback=self.on_kalman_predict_frames_change, width=self.scaled_width_normal)
                            crosshair_group = dpg.add_collapsing_header(label='准星找色', default_open=False)
                            with dpg.group(parent=crosshair_group):
                                crosshair_cfg = self._get_crosshair_lock_config()
                                active_hsv, _ = self._get_active_hsv_range(crosshair_cfg)
                                with dpg.group(horizontal=True):
                                    self.crosshair_lock_enabled_checkbox = dpg.add_checkbox(label='启用准星找色', default_value=crosshair_cfg.get('enabled', False), callback=self.on_crosshair_lock_enabled_change)
                                    self.crosshair_start_button = dpg.add_button(label='开始识别', callback=self.on_crosshair_start_click, width=self.scaled_width_normal)
                                    self.crosshair_pick_button = dpg.add_button(label='添加颜色', callback=self.on_crosshair_pick_click, width=self.scaled_width_normal)
                                    self.crosshair_pick_status_text = dpg.add_text('取色模式: 关')
                                with dpg.group(horizontal=True):
                                    dpg.add_text('颜色组')
                                    color_items = self._get_crosshair_color_group_items(crosshair_cfg)
                                    default_group = color_items[crosshair_cfg.get('active_index', 0)] if color_items else ''
                                    self.crosshair_color_group_combo = dpg.add_combo(items=color_items, default_value=default_group, callback=self.on_crosshair_color_group_change, width=self.scaled_width_normal)
                                    self.crosshair_delete_color_button = dpg.add_button(label='删除颜色', callback=self.on_crosshair_delete_color_click, width=self.scaled_width_normal)
                                    self.crosshair_rgb_text = dpg.add_text(self._format_rgb_text(crosshair_cfg.get('last_rgb', [0, 0, 0])))
                                with dpg.group(horizontal=True):
                                    self.crosshair_roi_width_slider = dpg.add_slider_int(label='检测区域宽', default_value=int(crosshair_cfg.get('roi_width', 200)), min_value=20, max_value=800, callback=self.on_crosshair_roi_width_change, width=self.scaled_width_normal)
                                    self.crosshair_roi_height_slider = dpg.add_slider_int(label='检测区域高', default_value=int(crosshair_cfg.get('roi_height', 200)), min_value=20, max_value=800, callback=self.on_crosshair_roi_height_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.crosshair_min_area_slider = dpg.add_slider_float(label='最小面积', default_value=float(crosshair_cfg.get('min_area', 1.0)), min_value=0.1, max_value=50.0, callback=self.on_crosshair_min_area_change, width=self.scaled_width_normal)
                                    self.crosshair_max_area_slider = dpg.add_slider_float(label='最大面积', default_value=float(crosshair_cfg.get('max_area', 1000.0)), min_value=10.0, max_value=5000.0, callback=self.on_crosshair_max_area_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.h_tolerance_slider = dpg.add_slider_int(label='H容差', default_value=int(crosshair_cfg.get('h_tolerance', 10)), min_value=1, max_value=50, callback=self.on_crosshair_h_tolerance_change, width=self.scaled_width_normal)
                                    self.s_tolerance_slider = dpg.add_slider_int(label='S容差', default_value=int(crosshair_cfg.get('s_tolerance', 30)), min_value=1, max_value=100, callback=self.on_crosshair_s_tolerance_change, width=self.scaled_width_normal)
                                    self.v_tolerance_slider = dpg.add_slider_int(label='V容差', default_value=int(crosshair_cfg.get('v_tolerance', 30)), min_value=1, max_value=100, callback=self.on_crosshair_v_tolerance_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.pull_k_slider = dpg.add_slider_float(label='回拉强度', default_value=float(crosshair_cfg.get('pull_k', 0.12)), min_value=0.01, max_value=0.5, callback=self.on_pull_k_change, width=self.scaled_width_normal)
                                    self.pull_max_speed_slider = dpg.add_slider_float(label='最大速度', default_value=float(crosshair_cfg.get('pull_max_speed', 6.0)), min_value=1.0, max_value=50.0, callback=self.on_pull_max_speed_change, width=self.scaled_width_normal)
                                    self.pull_deadzone_slider = dpg.add_slider_float(label='回拉死区', default_value=float(crosshair_cfg.get('pull_deadzone', 1.0)), min_value=0.0, max_value=10.0, callback=self.on_pull_deadzone_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.ema_smooth_slider = dpg.add_slider_float(label='平滑系数', default_value=float(crosshair_cfg.get('ema_smooth', 0.4)), min_value=0.05, max_value=1.0, callback=self.on_ema_smooth_change, width=self.scaled_width_normal)
                                    with dpg.tooltip(self.ema_smooth_slider):
                                        dpg.add_text("控制找色偏移的时间平滑程度。\n越小越平滑（但延迟增大），越大越灵敏。\n推荐 0.3~0.5。")
                                    self.small_pixel_threshold_slider = dpg.add_slider_int(label='小目标阈值', default_value=int(crosshair_cfg.get('small_pixel_threshold', 150)), min_value=20, max_value=500, callback=self.on_small_pixel_threshold_change, width=self.scaled_width_normal)
                                    with dpg.tooltip(self.small_pixel_threshold_slider):
                                        dpg.add_text("匹配像素数低于此值时自动切换为小目标模式，\n跳过腐蚀运算保留细小色块。\n越大越保守（更多情况走小目标模式）。\n推荐 100~200。")
                                with dpg.group(horizontal=True):
                                    self.crosshair_h_min_slider = dpg.add_slider_int(label='H Min', default_value=int(active_hsv.get('h_min', 0)), min_value=0, max_value=179, callback=self.on_crosshair_h_min_change, width=self.scaled_width_normal)
                                    self.crosshair_h_max_slider = dpg.add_slider_int(label='H Max', default_value=int(active_hsv.get('h_max', 179)), min_value=0, max_value=179, callback=self.on_crosshair_h_max_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.crosshair_s_min_slider = dpg.add_slider_int(label='S Min', default_value=int(active_hsv.get('s_min', 0)), min_value=0, max_value=255, callback=self.on_crosshair_s_min_change, width=self.scaled_width_normal)
                                    self.crosshair_s_max_slider = dpg.add_slider_int(label='S Max', default_value=int(active_hsv.get('s_max', 255)), min_value=0, max_value=255, callback=self.on_crosshair_s_max_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.crosshair_v_min_slider = dpg.add_slider_int(label='V Min', default_value=int(active_hsv.get('v_min', 0)), min_value=0, max_value=255, callback=self.on_crosshair_v_min_change, width=self.scaled_width_normal)
                                    self.crosshair_v_max_slider = dpg.add_slider_int(label='V Max', default_value=int(active_hsv.get('v_max', 255)), min_value=0, max_value=255, callback=self.on_crosshair_v_max_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.crosshair_show_crosshair_checkbox = dpg.add_checkbox(label='显示辅助准星', default_value=crosshair_cfg.get('show_crosshair', True), callback=self.on_crosshair_show_crosshair_change)
                                    with dpg.tooltip(self.crosshair_show_crosshair_checkbox):
                                        dpg.add_text("在屏幕中心显示一个固定的黄色准星，\n用于辅助定位屏幕中心。")
                                    self.crosshair_show_lock_box_checkbox = dpg.add_checkbox(label='显示锁定区域', default_value=crosshair_cfg.get('show_lock_box', True), callback=self.on_crosshair_show_lock_box_change)
                                    self.crosshair_show_mask_checkbox = dpg.add_checkbox(label='显示过滤效果', default_value=crosshair_cfg.get('show_mask', False), callback=self.on_crosshair_show_mask_change)
                                    with dpg.tooltip(self.crosshair_show_mask_checkbox):
                                        dpg.add_text("开启后预览框将显示色彩过滤后的图像（黑底保留色），\n用于调试颜色范围是否准确。\n蓝点表示识别到的目标中心点。")
                                    self.crosshair_show_active_only_checkbox = dpg.add_checkbox(label='仅预览当前颜色', default_value=crosshair_cfg.get('show_active_only', False), callback=self.on_crosshair_show_active_only_change)
                                    with dpg.tooltip(self.crosshair_show_active_only_checkbox):
                                        dpg.add_text("开启后，预览框和识别逻辑只针对当前选中的颜色组生效，\n方便单独调试某一种颜色，避免其他颜色干扰。")
                                    self.crosshair_show_debug_log_checkbox = dpg.add_checkbox(label='显示调试日志', default_value=crosshair_cfg.get('show_debug_log', False), callback=self.on_crosshair_show_debug_log_change)
                                    with dpg.tooltip(self.crosshair_show_debug_log_checkbox):
                                        dpg.add_text("开启后会在控制台输出找色信息（每秒一次），\n包括识别到的面积、偏移量等。")
                                    self.crosshair_only_when_aiming_checkbox = dpg.add_checkbox(label='仅瞄准时启用', default_value=crosshair_cfg.get('only_when_aiming', True), callback=self.on_crosshair_only_when_aiming_change)
                                    with dpg.tooltip(self.crosshair_only_when_aiming_checkbox):
                                        dpg.add_text("建议开启！\n开启后：只有按下瞄准键且主自瞄未找到目标时，才会使用颜色找色进行微调。\n关闭后：只要识别到颜色就会自动拉动准星（走路时容易乱拉）。")
                            trigger_setting_tag = dpg.add_collapsing_header(label='扳机配置', default_open=True)
                            with dpg.group(parent=trigger_setting_tag):
                                with dpg.group(horizontal=True):
                                    self.status_input = dpg.add_checkbox(label='自动扳机', callback=self.on_status_change)
                                    self.continuous_trigger_input = dpg.add_checkbox(label='持续扳机', callback=self.on_continuous_trigger_change)
                                    self.trigger_recoil_input = dpg.add_checkbox(label='扳机压枪', callback=self.on_trigger_recoil_change)
                                with dpg.group(horizontal=True):
                                    self.start_delay_slider = dpg.add_slider_int(label='扳机前摇', min_value=0, max_value=1000, callback=self.on_start_delay_change, width=self.scaled_width_normal)
                                    self.press_delay_slider = dpg.add_slider_int(label='按键时长', min_value=0, max_value=1000, callback=self.on_press_delay_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.end_delay_slider = dpg.add_slider_int(label='扳机冷却', min_value=0, max_value=1000, callback=self.on_end_delay_change, width=self.scaled_width_normal)
                                    self.random_delay_slider = dpg.add_slider_int(label='随机延迟', min_value=0, max_value=1000, callback=self.on_random_delay_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.x_trigger_scope_slider = dpg.add_slider_float(label='X轴范围', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_x_trigger_scope_change, width=self.scaled_width_normal)
                                    self.y_trigger_scope_slider = dpg.add_slider_float(label='Y轴范围', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_y_trigger_scope_change, width=self.scaled_width_normal)
                                with dpg.group(horizontal=True):
                                    self.x_trigger_offset_slider = dpg.add_slider_float(label='X轴偏移', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_x_trigger_offset_change, width=self.scaled_width_normal)
                                    self.y_trigger_offset_slider = dpg.add_slider_float(label='Y轴偏移', min_value=0.0, max_value=1.0, format='%.2f', callback=self.on_y_trigger_offset_change, width=self.scaled_width_normal)
                                with dpg.drawlist(width=self.scaled_width_small, height=self.scaled_height_normal):
                                    dpg.draw_rectangle((0, 0), (50, 100), color=(255, 255, 255))
                                    x_trigger_offset = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_offset']
                                    y_trigger_offset = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_offset']
                                    x_trigger_scope = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_scope']
                                    y_trigger_scope = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_scope']
                                    x_trigger_offset = x_trigger_offset * 50
                                    y_trigger_offset = y_trigger_offset * 100
                                    dpg.draw_rectangle((x_trigger_offset, y_trigger_offset), (x_trigger_offset + 50 * x_trigger_scope, y_trigger_offset + 100 * y_trigger_scope), fill=(255, 0, 0), tag='small_rect')
                            self.update_group_inputs()
                    with dpg.group(horizontal=True):
                        self.start_button_tag = dpg.add_button(label='启动', callback=self.on_start_button_click, width=self.scaled_width_normal)
                        dpg.add_button(label='保存配置', callback=self.on_save_button_click, width=self.scaled_width_normal)
                        dpg.add_text('', tag='output_text')
            with dpg.group():
                dpg.add_spacer(height=5)
                with dpg.group(horizontal=True):
                    version_text = dpg.add_text(f'版本: {VERSION} {UPDATE_TIME} {self.buff_single.GetMacCode()}')
                    with dpg.theme() as version_theme, dpg.theme_component(dpg.mvText):
                        dpg.add_theme_color(dpg.mvThemeCol_Text, (150, 150, 150, 255))
                    dpg.bind_item_theme(version_text, version_theme)
            dpg.show_viewport()
            dpg.set_primary_window(self.window_tag, True)
            self.update_sensitivity_display()

            self.update_crosshair_hsv_ui()
            self.render_mouse_re_games_combo()
            self.render_mouse_re_guns_combo()
            self.update_mouse_re_ui_status()
            dpg.start_dearpygui()
        self.running = False
        self.disconnect_device()
        self.close_screenshot()
        print('Exit')
        dpg.destroy_context()

