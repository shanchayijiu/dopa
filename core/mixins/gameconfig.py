# -*- coding: utf-8 -*-
"""游戏/枪械配置 Mixin — 从 core.py 提取 gameconfig 区块。

包含游戏/枪械/弹道下拉渲染（render_*_combo）、增删改回调（on_add/delete/gun/stage）/、
坐标/序号回调（on_x/y/number_change）、游戏/枪械选中回调（on_games/guns/stages_change）、
弹道刷新（refresh_stage）。所有方法操作 self.* 属性，通过 mix-in 继承可用。
"""
import copy

import dearpygui.dearpygui as dpg


class GameConfigMixin:
    """游戏/枪械配置 Mixin。游戏/枪/弹道下拉与增删改回调。"""
    def render_games_combo(self):
        if self.games_combo is not None:
            dpg.delete_item(self.games_combo)
        self.games_combo = dpg.add_combo(label='游戏', items=list(self.config['games'].keys()), default_value=self.config['picked_game'], callback=self.on_games_change, width=self.scaled_width_large, parent=self.dpg_games_tag)

    def render_guns_combo(self):
        if self.guns_combo is not None:
            dpg.delete_item(self.guns_combo)
        guns = list(self.config['games'][self.picked_game].keys())
        if self.picked_gun not in guns:
            self.picked_gun = guns[0]
        self.guns_combo = dpg.add_combo(label='枪械', items=guns, default_value=self.picked_gun, callback=self.on_guns_change, width=self.scaled_width_large, parent=self.dpg_guns_tag)

    def render_stages_combo(self):
        if self.stages_combo is not None:
            dpg.delete_item(self.stages_combo)
        stages = self.config['games'][self.picked_game][self.picked_gun]
        stage_len = len(self.config['games'][self.picked_game][self.picked_gun])
        stages_obj = {}
        for i in range(stage_len):
            stages_obj[str(i)] = stages[i]
        if self.picked_stage not in stages_obj:
            self.picked_stage = '0'
        self.stages_combo = dpg.add_combo(label='索引', items=list(stages_obj.keys()), default_value=self.picked_stage, callback=self.on_stages_change, width=self.scaled_width_large, parent=self.dpg_stages_tag)

    def on_delete_game_click(self, sender, app_data):
        if len(self.config['games']) > 1:
            del self.config['games'][self.picked_game]
            self.picked_game = list(self.config['games'].keys())[0]
            self.config['picked_game'] = self.picked_game
            self.render_games_combo()

    def on_delete_gun_click(self, sender, app_data):
        if len(self.config['games'][self.picked_game]) > 1:
            del self.config['games'][self.picked_game][self.picked_gun]
            self.picked_gun = list(self.config['games'][self.picked_game].keys())[0]
            self.render_guns_combo()

    def on_delete_stage_click(self, sender, app_data):
        if len(self.config['games'][self.picked_game][self.picked_gun]) > 1:
            del self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]
            self.render_stages_combo()

    def on_game_name_change(self, sender, app_data):
        self.add_game_name = app_data

    def on_gun_name_change(self, sender, app_data):
        self.add_gun_name = app_data

    def on_number_change(self, sender, app_data):
        self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['number'] = app_data

    def on_x_change(self, sender, app_data):
        self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][0] = round(app_data, 3)

    def on_y_change(self, sender, app_data):
        self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][1] = round(app_data, 3)

    def on_add_game_click(self, sender, app_data):
        if self.add_game_name not in self.config['games'] and self.add_game_name!= '':
            self.config['games'][self.add_game_name] = copy.deepcopy(self.config['games'][self.picked_game])
            self.picked_game = self.add_game_name
            self.config['picked_game'] = self.picked_game
            self.render_games_combo()

    def on_add_stage_click(self, sender, app_data):
        self.config['games'][self.picked_game][self.picked_gun].append({'number': 0, 'offset': [0, 0]})
        self.render_stages_combo()

    def on_add_gun_click(self, sender, app_data):
        if self.add_gun_name not in self.config['games'][self.picked_game] and self.add_gun_name!= '':
            self.config['games'][self.picked_game][self.add_gun_name] = copy.deepcopy(self.config['games'][self.picked_game][self.picked_gun])
            self.picked_gun = self.add_gun_name
            self.render_guns_combo()
            self.render_stages_combo()
            self.refresh_stage()

    def on_games_change(self, sender, app_data):
        self.picked_game = app_data
        self.config['picked_game'] = self.picked_game
        self.render_guns_combo()
        self.render_stages_combo()
        self.refresh_stage()
        self._current_mouse_re_points = None
        if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False):
            self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()

    def on_guns_change(self, sender, app_data):
        self.picked_gun = app_data
        self.render_stages_combo()
        self.refresh_stage()
        self._current_mouse_re_points = None
        if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False):
            self._current_mouse_re_points = self._load_mouse_re_trajectory_for_current()

    def on_stages_change(self, sender, app_data):
        self.picked_stage = app_data
        self.refresh_stage()

    def refresh_stage(self):
        number = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['number']
        x = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][0]
        y = self.config['games'][self.picked_game][self.picked_gun][int(self.picked_stage)]['offset'][1]
        dpg.set_value(self.number_input, number)
        dpg.set_value(self.x_input, x)
        dpg.set_value(self.y_input, y)

