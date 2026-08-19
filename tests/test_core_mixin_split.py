# -*- coding: utf-8 -*-
"""Regression tests for the core.py mix-in split.

The refactor moved ~85% of Valorant's methods out of core.py into 20 core_*.py
mix-ins. These tests lock in the two properties that split can silently break:

1. Composition integrity: every mix-in is still in Valorant's MRO, and the
   methods each module owns are actually reachable on the composed class.
2. Behavioral equivalence of the pure-logic callbacks that were moved.

The config-back mix-ins are exercised against a minimal stub host rather
than a real Valorant instance: Valorant.__init__ builds GUI state, devices and
worker threads, none of which these methods touch. The stub documents the exact
contract each mix-in relies on.
"""
import unittest

import core
from core.mixins.aimcfg import AimConfigMixin
from core.mixins.perception import PerceptionMixin
from core.mixins.pidtracker import PidTrackerMixin

EXPECTED_MIXINS = [
    "VerifyMixin",
    "DeviceMixin",
    "InputListenerMixin",
    "InferenceMixin",
    "PerceptionMixin",
    "TriggerMixin",
    "ConfigMixin",
    "ConfigPersistMixin",
    "CrosshairUIMixin",
    "DisplayMixin",
    "GUIMixin",
    "MouseReMixin",
    "GameConfigMixin",
    "MouseMaskMixin",
    "FlashbangMixin",
    "KeyBindMixin",
    "InferConfigMixin",
    "SystemConfigMixin",
    "AimConfigMixin",
    "PidTrackerMixin",
]

# Methods that must stay in core.py itself: the motion-execution loop and the
# lifecycle/config assembly hub. AI_CONTEXT.md 8 forbids relocating these.
CORE_RESIDENT = [
    "aim_bot_func",
    "go",
    "on_start_button_click",
    "_change_callback",
]


class _StubHost:
    """Minimal stand-in for Valorant, exposing only what the config mix-ins read."""

    def __init__(self, key="mouse_right"):
        self.group = "g0"
        self.select_key = key
        self.aim_key = key
        self.pressed_key_config = {}
        self.config = {
            "target_sticky_pixels": 40.0,
            "target_lock_ms": 150.0,
            "large_target_threshold": 0.055,
            "large_target_boost": 1.12,
            "groups": {
                "g0": {
                    "aim_keys": {
                        key: {
                            "aim_bot_scope": 100,
                            "dynamic_scope": {},
                        }
                    }
                }
            },
        }
        self.pid_refresh_calls = 0

    # PidTrackerMixin calls this after every parameter write.
    def _update_pid_params(self):
        self.pid_refresh_calls += 1

    @property
    def key_cfg(self):
        return self.config["groups"][self.group]["aim_keys"][self.select_key]


class _AimHost(_StubHost, AimConfigMixin):
    pass


class _PidHost(_StubHost, PidTrackerMixin):
    pass


class MixinCompositionTests(unittest.TestCase):
    def test_all_mixins_present_in_mro(self):
        mro_names = [c.__name__ for c in core.Valorant.__mro__]
        for name in EXPECTED_MIXINS:
            self.assertIn(name, mro_names, f"{name} dropped out of Valorant's MRO")

    def test_mixin_count_is_locked(self):
        mro_names = [c.__name__ for c in core.Valorant.__mro__]
        mixins = [n for n in mro_names if n.endswith("Mixin")]
        self.assertEqual(
            len(mixins), len(EXPECTED_MIXINS),
            f"mix-in count changed: {sorted(set(mixins) ^ set(EXPECTED_MIXINS))}",
        )

    def test_core_resident_methods_defined_in_core(self):
        """Protected methods must be defined on Valorant itself, not inherited."""
        for name in CORE_RESIDENT:
            self.assertIn(name, core.Valorant.__dict__,
                          f"{name} is no longer defined directly in core.py")

    def test_moved_methods_reachable_on_composed_class(self):
        for name in ("update_crosshair_tracking", "parse_class_priority",
                     "on_pid_kp_x_change", "_mouse_button_to_key", "on_click"):
            self.assertTrue(callable(getattr(core.Valorant, name, None)),
                            f"{name} not reachable on Valorant")

    def test_dead_methods_removed(self):
        """screenshot / smooth_small_targets were proven unused and deleted."""
        for name in ("screenshot", "smooth_small_targets"):
            self.assertFalse(hasattr(PerceptionMixin, name),
                             f"dead method {name} came back")


class MouseButtonMappingTests(unittest.TestCase):
    def test_all_buttons_map_and_unknown_falls_back(self):
        from pynput import mouse
        host = core.Valorant  # unbound use: the method is pure
        cases = {
            mouse.Button.left: "mouse_left",
            mouse.Button.right: "mouse_right",
            mouse.Button.middle: "mouse_middle",
            mouse.Button.x1: "mouse_x1",
            mouse.Button.x2: "mouse_x2",
        }
        for button, expected in cases.items():
            self.assertEqual(host._mouse_button_to_key(None, button), expected)
        self.assertIsNone(host._mouse_button_to_key(None, mouse.Button.unknown))


class ClassPriorityParsingTests(unittest.TestCase):
    def setUp(self):
        self.host = _AimHost()

    def test_empty_text_yields_empty_list(self):
        self.assertEqual(self.host.parse_class_priority(""), [])

    def test_separators_and_dedup(self):
        self.assertEqual(self.host.parse_class_priority("0-1-2"), [0, 1, 2])
        self.assertEqual(self.host.parse_class_priority("2, 0  1"), [2, 0, 1])
        self.assertEqual(self.host.parse_class_priority("1-1-3"), [1, 3])

    def test_non_numeric_token_rejected(self):
        self.assertIsNone(self.host.parse_class_priority("0-x-2"))

    def test_format_round_trips(self):
        self.assertEqual(self.host.format_class_priority([3, 1, 0]), "3-1-0")
        self.assertEqual(self.host.format_class_priority([]), "")


class AimConfigCoercionTests(unittest.TestCase):
    """Invalid GUI input must fall back to the stored value, not crash."""

    def setUp(self):
        self.host = _AimHost()

    def test_sticky_pixels_valid_and_clamped(self):
        self.host.on_target_sticky_pixels_change(None, "55.5")
        self.assertEqual(self.host.config["target_sticky_pixels"], 55.5)
        self.host.on_target_sticky_pixels_change(None, "999")
        self.assertEqual(self.host.config["target_sticky_pixels"], 120.0)
        self.host.on_target_sticky_pixels_change(None, "-5")
        self.assertEqual(self.host.config["target_sticky_pixels"], 0.0)

    def test_sticky_pixels_garbage_falls_back(self):
        self.host.config["target_sticky_pixels"] = 42.0
        self.host.on_target_sticky_pixels_change(None, "not-a-number")
        self.assertEqual(self.host.config["target_sticky_pixels"], 42.0)

    def test_large_target_boost_lower_bound_is_one(self):
        self.host.on_large_target_boost_change(None, "0.1")
        self.assertEqual(self.host.config["large_target_boost"], 1.0)

    def test_dynamic_scope_min_ratio_garbage_defaults(self):
        self.host.on_dynamic_scope_min_ratio_change(None, "bad")
        self.assertEqual(self.host.key_cfg["dynamic_scope"]["min_ratio"], 0.5)

    def test_dynamic_scope_durations_clamp_negative(self):
        self.host.on_dynamic_scope_shrink_ms_change(None, "-100")
        self.assertEqual(self.host.key_cfg["dynamic_scope"]["shrink_duration_ms"], 0)
        self.host.on_dynamic_scope_recover_ms_change(None, "bad")
        self.assertEqual(self.host.key_cfg["dynamic_scope"]["recover_duration_ms"], 300)


class PidCallbackTests(unittest.TestCase):
    def setUp(self):
        self.host = _PidHost()

    def test_pid_writes_round_and_refresh(self):
        self.host.on_pid_kp_x_change(None, 0.123456789)
        self.assertEqual(self.host.key_cfg["pid_kp_x"], 0.1235)
        self.assertEqual(self.host.pid_refresh_calls, 1)

    def test_each_axis_targets_its_own_config_slot(self):
        self.host.on_pid_kp_x_change(None, 1.0)
        self.host.on_pid_kp_y_change(None, 2.0)
        self.host.on_pid_ki_x_change(None, 3.0)
        self.assertEqual(self.host.key_cfg["pid_kp_x"], 1.0)
        self.assertEqual(self.host.key_cfg["pid_kp_y"], 2.0)
        self.assertEqual(self.host.key_cfg["pid_ki_x"], 3.0)
        self.assertEqual(self.host.pid_refresh_calls, 3)


if __name__ == "__main__":
    unittest.main()
