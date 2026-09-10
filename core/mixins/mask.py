# -*- coding: utf-8 -*-
"""鼠标按键屏蔽 Mixin — 从 core.py 提取 mouse-mask 区块。

8 个 on_mask_(left|right|middle|side1|side2|x|y|wheel)_change 回调 + 2 个
on_aim_mask_(x|y)_change 回调。根据 self.config['move_method'] 分发到 kmNet /
catbox / self.dhz 设备屏蔽接口。本 mix-in 只 import 模块名 catbox/kmNet；
self.dhz 由 init_mouse 在启动期创建，通过实例属性访问。
"""
from devices.catbox_wrapper import catbox
import kmNet


class MouseMaskMixin:
    """鼠标按键屏蔽 Mixin。km_net/catbox/dhz 三种 move_method 的屏蔽回调。"""
    def _external_mask_enabled(self):
        """单机模式下禁止调用外置设备屏蔽 API。"""
        return not self.config.get('single_machine_mode', False)

    def on_mask_left_change(self, sender, app_data):
        self.config['mask_left'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_left(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_left(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_left(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_left(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_left(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_left(0)

    def on_mask_right_change(self, sender, app_data):
        self.config['mask_right'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_right(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_right(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_right(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_right(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_right(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_right(0)

    def on_mask_middle_change(self, sender, app_data):
        self.config['mask_middle'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_middle(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_middle(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_middle(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_middle(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_middle(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_middle(0)

    def on_mask_side1_change(self, sender, app_data):
        self.config['mask_side1'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_side1(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_side1(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_side1(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_side1(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_side1(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_side1(0)

    def on_mask_side2_change(self, sender, app_data):
        self.config['mask_side2'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_side2(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_side2(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_side2(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_side2(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_side2(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_side2(0)

    def on_mask_x_change(self, sender, app_data):
        self.config['mask_x'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_x(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_x(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_x(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_x(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_x(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_x(0)

    def on_mask_y_change(self, sender, app_data):
        self.config['mask_y'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_y(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_y(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_y(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_y(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_y(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_y(0)

    def on_mask_wheel_change(self, sender, app_data):
        self.config['mask_wheel'] = app_data
        if self._external_mask_enabled() and self.config['move_method'] in ['km_net', 'dhz', 'catbox']:
            if app_data:
                if self.config['move_method'] == 'dhz':
                    self.dhz.mask_wheel(1)
                elif self.config['move_method'] == 'km_net':
                    kmNet.mask_wheel(1)
                elif self.config['move_method'] == 'catbox':
                    catbox.mask_wheel(1)
            elif self.config['move_method'] == 'dhz':
                self.dhz.mask_wheel(0)
            elif self.config['move_method'] == 'km_net':
                kmNet.mask_wheel(0)
            elif self.config['move_method'] == 'catbox':
                catbox.mask_wheel(0)

    def on_aim_mask_x_change(self, sender, app_data):
        self.config['aim_mask_x'] = app_data

    def on_aim_mask_y_change(self, sender, app_data):
        self.config['aim_mask_y'] = app_data

