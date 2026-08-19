# -*- coding: utf-8 -*-
"""感知辅助 Mixin — 准星跟踪的旁路执行层。

update_crosshair_tracking 由 core_inference.py 的预处理后台线程调用（3 处），
同步执行准星找色，委托给 self._crosshair_tracker.update()，不参与
aim_bot_func 定时器热路径。

历史说明：本模块曾另有两个死方法，已于本轮删除，二者均经全仓 AST 验证零消费。
- screenshot(left, top, right, bottom): 已弃用的薄壳，转发至
  self.screenshot_manager.get_screenshot()。截图统一走 screenshot_manager，
  无任何 self.screenshot 属性消费者。
- smooth_small_targets(targets): 单参版本，已被
  AimPipeline.smooth_small_targets(targets, aim_params)（aim_pipeline.py:584，
  由同文件 :1005 调用）完全取代。

依赖 Valorant 提供:
  self._crosshair_tracker / self._get_crosshair_lock_config()（CrosshairUIMixin）
"""


class PerceptionMixin:
    """准星跟踪辅助 Mixin。"""

    def update_crosshair_tracking(self, frame):
        """同步执行准星找色（由预处理后台线程调用，不阻塞推理主线程）"""
        cfg = self._get_crosshair_lock_config()
        self._crosshair_tracker.update(frame, cfg)
