# -*- coding: utf-8 -*-
"""配置持久化 Mixin — 从 core.py 提取的配置读写与保存入口。

包含默认配置/本地配置读取（委托 config_manager）、远程配置异步保存、
保存按钮回调、通用配置变更分发（转发 ConfigChangeHandler）、auto_y 配置迁移。
被 core_config / core_systemcfg / core_pidtracker 等通过 self.* 调用，
经 mix-in 继承可达。

依赖 Valorant 提供:
  self.config / self.config_handler / self.dpg / self.font_normal
  self.save_config_callback()（InferenceMixin）
"""
import threading

from settings import config_manager as cfgmgr
from settings.remote_config import save_remote_config


class ConfigPersistMixin:
    """配置持久化与变更分发 Mixin。"""

    def get_default_config(self):
        print('使用默认配置，跳过远程验证')
        return cfgmgr.get_default_config()

    def read_local_cfg(self):
        return cfgmgr.read_local_cfg()

    def save_config(self):
        """异步保存配置到远程服务器"""

        def _async_save():
            try:
                result = save_remote_config(self.config)
                if not result:
                    if hasattr(self, 'dpg') and self.dpg:
                        self.dpg.add_text('配置保存失败，请检查配置文件权限或磁盘空间', color=[255, 0, 0])
                       
                        self.dpg.set_item_font('配置保存失败，请检查配置文件权限或磁盘空间', self.font_normal)
                        threading.Timer(3.0, lambda: self.dpg.delete_item('配置保存失败，请检查配置文件权限或磁盘空间') if self.dpg.does_item_exist('配置保存失败，请检查配置文件权限或磁盘空间') else None).start()
                    return result
                print('配置保存成功')
                return result
            except Exception as e:
                print(f'配置保存异常: {e}')
                return False
        save_thread = threading.Thread(target=_async_save, daemon=True)
        save_thread.start()
        return True

    def on_save_button_click(self, sender, app_data):
        self.save_config_callback()

    def on_change(self, sender, app_data):
        """\n        通用的配置变更处理方法，将事件转发给ConfigChangeHandler处理\n        \n        Args:\n            sender: 发送者ID\n            app_data: 新的配置值\n        """
        self.config_handler.handle_change(sender, app_data)

    def migrate_auto_y_config(self):
        cfgmgr.migrate_auto_y(self.config)
