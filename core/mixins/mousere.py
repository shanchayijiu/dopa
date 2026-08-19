# -*- coding: utf-8 -*-
"""鼠标压枪轨迹 Mixin — 从 core.py 提取 mouse_re 轨迹压枪回调与辅助方法。

包含 mouse_re 开关/速度/增强回调、轨迹导入/清空、JSON 解析、压枪回放线程、
游戏/枪械下拉渲染。所有方法操作 self.* 属性，通过 mix-in 继承可用。
"""
import json
import time
import threading
import dearpygui.dearpygui as dpg


class MouseReMixin:
    """鼠标压枪轨迹 Mixin。mouse_re 轨迹压枪回调与回放线程。"""
    def update_mouse_re_ui_status(self):
        """刷新mouse_re状态面板"""
        try:
            switch_text = '开' if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False) and getattr(self, 'down_switch', False) else '关'
            key = f"{getattr(self, 'mouse_re_picked_game', '')}:{getattr(self, 'mouse_re_picked_gun', '')}"
            recoil_config = self.config.get('recoil', {})
            mapping = recoil_config.get('mapping', {})
            if not isinstance(mapping, dict):
                print(f'[警告] mapping不是字典类型: {type(mapping)}, 重置为空字典')
                mapping = {}
                self.config['recoil']['mapping'] = {}
            file_text = '无'
            if key and key!= ':':
                entry = mapping.get(key)
                if entry and isinstance(entry, dict) and ('path' in entry):
                    file_text = entry['path'] or '无'
            points_cnt = len(self._current_mouse_re_points) if self._current_mouse_re_points else 0
            if dpg.does_item_exist('mouse_re_switch_text'):
                dpg.set_value('mouse_re_switch_text', f'开关: {switch_text}')
            if dpg.does_item_exist('mouse_re_file_text'):
                dpg.set_value('mouse_re_file_text', f'映射文件: {file_text}')
            if dpg.does_item_exist('mouse_re_points_text'):
                dpg.set_value('mouse_re_points_text', f'轨迹点数: {points_cnt}')
        except Exception as e:
            print(f'刷新mouse_re状态失败: {e}')
            import traceback
            traceback.print_exc()

    def on_use_mouse_re_trajectory_change(self, sender, app_data):
        """启用/禁用 mouse_re 轨迹压枪"""
        try:
            enabled = bool(app_data)
            self.config['recoil']['use_mouse_re_trajectory'] = enabled
            print(f"[mouse_re] 轨迹压枪: {('启用' if enabled else '禁用')}")
            self.update_mouse_re_ui_status()
        except Exception as e:
            print(f'更新mouse_re轨迹压枪开关失败: {e}')

    def on_mouse_re_replay_speed_change(self, sender, app_data):
        """更新mouse_re轨迹回放速度"""
        try:
            speed = float(app_data)
            if speed <= 0:
                speed = 1.0
            self.config['recoil']['replay_speed'] = speed
            print(f'[mouse_re] 回放速度设置为 {speed}x')
        except Exception as e:
            print(f'更新mouse_re回放速度失败: {e}')

    def on_mouse_re_pixel_enhancement_change(self, sender, app_data):
        """更新mouse_re轨迹像素增强比例"""
        try:
            ratio = float(app_data)
            if ratio <= 0:
                ratio = 1.0
            self.config['recoil']['pixel_enhancement_ratio'] = ratio
            print(f'[mouse_re] 像素增强比例设置为 {ratio}x')
        except Exception as e:
            print(f'更新mouse_re像素增强比例失败: {e}')

    def on_import_mouse_re_trajectory_click(self, sender, app_data):
        """为mouse_re选择的游戏/枪械导入轨迹文件"""
        try:
            if not self.mouse_re_picked_game or not self.mouse_re_picked_gun:
                print('[mouse_re] 请先选择游戏和枪械')
                return
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(title='选择mouse_re轨迹JSON', filetypes=[('JSON文件', '*.json'), ('所有文件', '*.*')])
            root.destroy()
            if not file_path:
                return
            key = f'{self.mouse_re_picked_game}:{self.mouse_re_picked_gun}'
            self.config['recoil']['mapping'][key] = {'path': file_path}
            print(f'[mouse_re] 已为 {key} 绑定轨迹: {file_path}')
            self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()
            self.update_mouse_re_ui_status()
        except Exception as e:
            print(f'导入mouse_re轨迹失败: {e}')

    def on_clear_mouse_re_mapping_click(self, sender, app_data):
        """清除mouse_re选择的游戏/枪械的映射"""
        try:
            if not self.mouse_re_picked_game or not self.mouse_re_picked_gun:
                print('[mouse_re] 请先选择游戏和枪械')
                return
            key = f'{self.mouse_re_picked_game}:{self.mouse_re_picked_gun}'
            if key in self.config['recoil']['mapping']:
                del self.config['recoil']['mapping'][key]
                print(f'[mouse_re] 已清除映射: {key}')
            self._current_mouse_re_points = None
            self.update_mouse_re_ui_status()
        except Exception as e:
            print(f'清除mouse_re映射失败: {e}')

    def _load_mouse_re_trajectory_for_current(self):
        # 加载mouse_re选择的游戏/枪械绑定的轨迹为增量点序列
        try:
            if not (getattr(self, 'mouse_re_picked_game', '') and getattr(self, 'mouse_re_picked_gun', '')):
                return None
            key = f'{self.mouse_re_picked_game}' + ':' + f'{self.mouse_re_picked_gun}'
            recoil_config = self.config.get('recoil', {})
            mapping = recoil_config.get('mapping', {})
            if not isinstance(mapping, dict):
                print('[警告] mapping不是字典类型: ' + f'{type(mapping)}')
                return None
            entry = mapping.get(key)
            if not entry or not isinstance(entry, dict) or 'path' not in entry:
                print('[mouse_re] 未找到映射: ' + f'{key}')
                return None
            path = entry['path']
            return self._parse_mouse_re_json(path)
        except Exception as e:
            print('加载mouse_re轨迹失败: ' + f'{e}')
            import traceback
            traceback.print_exc()

    def _parse_mouse_re_json(self, path):
        """解析 mouse_re.py 保存的JSON，转换为增量(dx,dy,dt_ms)序列"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print(f'[mouse_re] JSON格式错误：根对象不是字典，是 {type(data)}')
                return
            moves = data.get('movements')
            if not moves:
                print('[mouse_re] JSON中没有找到 \'movements\' 字段')
                return
            if not isinstance(moves, list):
                print(f'[mouse_re] movements字段不是列表，是 {type(moves)}')
                return
            if len(moves) < 2:
                print(f'[mouse_re] 轨迹点过少: {len(moves)}')
                return
            points = []
            prev = moves[0]
            if not isinstance(prev, dict):
                print(f'[mouse_re] 第一个轨迹点不是字典: {type(prev)}')
                return
            prev_t = float(prev.get('timestamp', 0.0))
            prev_x = float(prev.get('x', 0.0))
            prev_y = float(prev.get('y', 0.0))
            for i in range(1, len(moves)):
                m = moves[i]
                if not isinstance(m, dict):
                    print(f'[mouse_re] 轨迹点 {i} 不是字典: {type(m)}')
                    continue
                cur_t = float(m.get('timestamp', prev_t))
                cur_x = float(m.get('x', prev_x))
                cur_y = float(m.get('y', prev_y))
                dx = cur_x - prev_x
                dy = cur_y - prev_y
                dt_ms = max(0.0, (cur_t - prev_t) * 1000.0)
                points.append({'dx': dx, 'dy': dy, 'dt_ms': dt_ms})
                prev_t, prev_x, prev_y = (cur_t, cur_x, cur_y)
            print(f'[mouse_re] 成功解析轨迹: {len(points)} 个增量点')
            return points
        except Exception as e:
            print(f'解析mouse_re JSON失败: {e}')
            import traceback
            traceback.print_exc()

    def _start_mouse_re_recoil(self):
        """启动 mouse_re 轨迹回放线程"""
        if self._recoil_is_replaying:
            return
        if self.config['groups'][self.group]['right_down'] and (not self.right_pressed):
            return
        if self._current_mouse_re_points is None:
            self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()
        if not self._current_mouse_re_points:
            print('[mouse_re] 没有可用轨迹，无法开始回放')
            return
        self._recoil_is_replaying = True
        self._recoil_replay_thread = threading.Thread(target=self._recoil_replay_worker, args=(self._current_mouse_re_points,), daemon=True)
        self._recoil_replay_thread.start()

    def _stop_mouse_re_recoil(self):
        """停止 mouse_re 轨迹回放"""
        self._recoil_is_replaying = False

    def _recoil_replay_worker(self, points):
        """在后台按时间序列回放相对位移"""
        try:
            speed = float(self.config.get('recoil', {}).get('replay_speed', 1.0))
            speed = 1.0 if speed <= 0 else speed
            enhancement_ratio = float(self.config.get('recoil', {}).get('pixel_enhancement_ratio', 1.0))
            enhancement_ratio = 1.0 if enhancement_ratio <= 0 else enhancement_ratio
            for step in points:
                left_press_valid = self.left_pressed and self.down_switch
                trigger_press_valid = self.trigger_recoil_pressed
                if not self._recoil_is_replaying or (not left_press_valid and (not trigger_press_valid)):
                    break
                if self.config['groups'][self.group]['right_down'] and (not self.right_pressed):
                    break
                dx = step['dx'] * enhancement_ratio
                dy = step['dy'] * enhancement_ratio
                ix = int(round(dx))
                iy = int(round(dy))
                if ix!= 0 or iy!= 0:
                    try:
                        self.move_r(ix, iy)
                    except Exception as e:
                        print(f'[mouse_re] move_r 调用失败: {e}')
                        break
                dt_ms = step.get('dt_ms', 0.0) / speed
                remaining = max(0.0, dt_ms) / 1000.0
                if remaining <= 0.0005:
                    continue
                if remaining <= 0.003:
                    time.sleep(remaining)
                    continue
                while remaining > 0 and self._recoil_is_replaying:
                    left_press_valid = self.left_pressed and self.down_switch
                    trigger_press_valid = self.trigger_recoil_pressed
                    if not left_press_valid and (not trigger_press_valid):
                        break
                    chunk = 0.003 if remaining > 0.006 else remaining
                    time.sleep(chunk)
                    remaining -= chunk
        except Exception as e:
            print(f'mouse_re回放线程错误: {e}')
        finally:
            self._recoil_is_replaying = False

    def render_mouse_re_games_combo(self):
        """渲染mouse_re游戏选择下拉框"""
        try:
            if self.mouse_re_games_combo is not None:
                dpg.delete_item(self.mouse_re_games_combo)
            games_config = self.config.get('games', {})
            if not isinstance(games_config, dict):
                print(f'[警告] games配置不是字典: {type(games_config)}')
                games = []
            else:
                games = list(games_config.keys())
            if not self.mouse_re_picked_game or self.mouse_re_picked_game not in games:
                self.mouse_re_picked_game = games[0] if games else ''
            self.mouse_re_games_combo = dpg.add_combo(label='mouse_re游戏', items=games, default_value=self.mouse_re_picked_game, callback=self.on_mouse_re_games_change, width=150, parent='mouse_re_combos_group')
        except Exception as e:
            print(f'渲染mouse_re游戏下拉框失败: {e}')
            import traceback
            traceback.print_exc()

    def render_mouse_re_guns_combo(self):
        """渲染mouse_re枪械选择下拉框"""
        try:
            if self.mouse_re_guns_combo is not None:
                dpg.delete_item(self.mouse_re_guns_combo)
            if not self.mouse_re_picked_game:
                self.mouse_re_guns_combo = dpg.add_combo(label='mouse_re枪械', items=[], default_value='', callback=self.on_mouse_re_guns_change, width=150, parent='mouse_re_combos_group')
                return
            games_config = self.config.get('games', {})
            if not isinstance(games_config, dict) or self.mouse_re_picked_game not in games_config:
                guns = []
            else:
                game_guns = games_config[self.mouse_re_picked_game]
                if isinstance(game_guns, dict):
                    guns = list(game_guns.keys())
                else:
                    guns = []
            if not self.mouse_re_picked_gun or self.mouse_re_picked_gun not in guns:
                self.mouse_re_picked_gun = guns[0] if guns else ''
            self.mouse_re_guns_combo = dpg.add_combo(label='mouse_re枪械', items=guns, default_value=self.mouse_re_picked_gun, callback=self.on_mouse_re_guns_change, width=150, parent='mouse_re_combos_group')
        except Exception as e:
            print(f'渲染mouse_re枪械下拉框失败: {e}')
            import traceback
            traceback.print_exc()

    def on_mouse_re_games_change(self, sender, app_data):
        """mouse_re游戏选择改变"""
        self.mouse_re_picked_game = app_data
        self.mouse_re_picked_gun = ''
        self.render_mouse_re_guns_combo()
        self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()
        self.update_mouse_re_ui_status()

    def on_mouse_re_guns_change(self, sender, app_data):
        """mouse_re枪械选择改变"""
        self.mouse_re_picked_gun = app_data
        self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()
        self.update_mouse_re_ui_status()

