from unittest.mock import Mock

import core.mixins.devices as devices_module
from core.mixins.devices import DeviceMixin
from core.mixins.mask import MouseMaskMixin
from settings.config_manager import ensure_defaults, get_default_config


class _DeviceHost(DeviceMixin):
    def __init__(self):
        self.config = {
            "single_machine_mode": True,
            "move_method": "km_net",
        }
        self.move_dll = object()
        self.move_r = None
        self.start_listen = Mock()


class _MaskHost(MouseMaskMixin):
    def __init__(self):
        self.config = {
            "single_machine_mode": True,
            "move_method": "km_net",
            "mask_left": False,
        }


def test_single_machine_mode_defaults_off():
    assert get_default_config()["single_machine_mode"] is False


def test_legacy_config_gets_single_machine_mode_default():
    config = {"move_method": "km_net"}
    ensure_defaults(config)
    assert config["single_machine_mode"] is False


def test_single_machine_mode_binds_local_backend_without_km_net(monkeypatch):
    host = _DeviceHost()
    local_move = Mock(name="local_move")
    fake_thread = Mock()
    thread_factory = Mock(return_value=fake_thread)
    km_init = Mock()

    monkeypatch.setattr(devices_module.pydirectinput, "moveRel", local_move)
    monkeypatch.setattr(devices_module, "Thread", thread_factory)
    monkeypatch.setattr(devices_module.kmNet, "init", km_init)

    host.init_mouse()

    assert host.move_dll is None
    assert host.move_r is local_move
    km_init.assert_not_called()
    thread_factory.assert_called_once_with(target=host.start_listen)
    fake_thread.setDaemon.assert_called_once_with(True)
    fake_thread.start.assert_called_once_with()


def test_single_machine_mask_callback_never_calls_external_api(monkeypatch):
    host = _MaskHost()
    mask_left = Mock()
    monkeypatch.setattr("core.mixins.mask.kmNet.mask_left", mask_left)

    host.on_mask_left_change(None, True)

    assert host.config["mask_left"] is True
    mask_left.assert_not_called()
