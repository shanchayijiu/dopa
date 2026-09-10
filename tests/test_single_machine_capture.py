from unittest.mock import Mock

import devices.screenshot_manager as screenshot_module
import core.valorant as valorant_module
from core.valorant import Valorant
from devices.screenshot_manager import ScreenshotManager


def _config(**overrides):
    config = {
        "single_machine_mode": True,
        "single_machine_capture_size": "320x320",
        "is_obs": False,
        "is_cjk": False,
        "screen_width": 1920,
        "screen_height": 1080,
        "enable_parallel_processing": False,
        "infer_debug": False,
    }
    config.update(overrides)
    return config


def test_single_machine_capture_initializes_without_engine(monkeypatch):
    fake_capture = Mock()
    fake_capture.start = Mock()
    monkeypatch.setattr(
        screenshot_module.bettercam,
        "create",
        Mock(return_value=fake_capture),
    )

    manager = ScreenshotManager(_config(), engine=None)

    assert manager.init_sources() is True
    screenshot_module.bettercam.create.assert_called_once_with(
        output_color="BGR",
        max_buffer_len=16,
        region=(800, 380, 1120, 700),
    )
    fake_capture.start.assert_called_once_with(target_fps=0, video_mode=True)


def test_normal_mode_still_requires_engine_for_bettercam(monkeypatch):
    create = Mock()
    monkeypatch.setattr(screenshot_module.bettercam, "create", create)

    manager = ScreenshotManager(_config(single_machine_mode=False), engine=None)

    assert manager.init_sources() is False
    create.assert_not_called()


def test_invalid_single_machine_capture_size_uses_safe_default(monkeypatch):
    fake_capture = Mock()
    monkeypatch.setattr(
        screenshot_module.bettercam,
        "create",
        Mock(return_value=fake_capture),
    )

    manager = ScreenshotManager(
        _config(single_machine_capture_size="not-a-size"),
        engine=None,
    )

    assert manager.init_sources() is True
    screenshot_module.bettercam.create.assert_called_once_with(
        output_color="BGR",
        max_buffer_len=16,
        region=(800, 380, 1120, 700),
    )


def test_single_machine_debug_uses_live_preview_without_engine(monkeypatch):
    fake_capture = Mock()
    thread = Mock()
    thread_factory = Mock(return_value=thread)
    monkeypatch.setattr(
        screenshot_module.bettercam,
        "create",
        Mock(return_value=fake_capture),
    )
    monkeypatch.setattr(screenshot_module, "Thread", thread_factory)

    manager = ScreenshotManager(_config(infer_debug=True), engine=None)

    assert manager.init_sources() is True
    assert thread_factory.call_args.kwargs["target"] == manager.display_screenshot_preview
    assert thread.daemon is True
    thread.start.assert_called_once_with()


def test_preview_renders_frame_and_unloaded_status(monkeypatch):
    manager = ScreenshotManager(_config(infer_debug=True), engine=None)
    frame = screenshot_module.np.zeros((320, 320, 3), dtype=screenshot_module.np.uint8)
    manager.get_screenshot = Mock(return_value=frame)

    def stop_after_first_frame(*args, **kwargs):
        manager.running = False

    monkeypatch.setattr(screenshot_module.cv2, "namedWindow", Mock())
    monkeypatch.setattr(screenshot_module.cv2, "setWindowProperty", Mock())
    monkeypatch.setattr(screenshot_module.cv2, "resizeWindow", Mock())
    monkeypatch.setattr(screenshot_module.cv2, "imshow", Mock())
    monkeypatch.setattr(screenshot_module.cv2, "waitKey", stop_after_first_frame)
    put_text = Mock()
    monkeypatch.setattr(screenshot_module.cv2, "putText", put_text)

    manager.display_screenshot_preview()

    screenshot_module.cv2.namedWindow.assert_called_once()
    screenshot_module.cv2.resizeWindow.assert_called_once_with("screenshot", 320, 320)
    screenshot_module.cv2.imshow.assert_called_once()
    assert put_text.call_args.args[1] == "INFERENCE ENGINE NOT LOADED"


def test_go_keeps_inference_threads_idle_without_engine(monkeypatch, tmp_path):
    model_path = tmp_path / "placeholder.onnx"
    model_path.write_bytes(b"single-machine-startup-placeholder")
    screenshot_manager = Mock()
    screenshot_manager.init_sources.return_value = True
    thread_factory = Mock()
    monkeypatch.setattr(valorant_module, "Thread", thread_factory)

    host = Mock()
    host.config = {
        "single_machine_mode": True,
        "screen_width": 1920,
        "screen_height": 1080,
        "groups": {"default": {"infer_model": str(model_path)}},
    }
    host.group = "default"
    host.screen_width = 1920
    host.screen_height = 1080
    host.decrypted_model_data = None
    host.original_model_path = None
    host.screenshot_manager = screenshot_manager
    host.engine = None
    host.timer_id = 0

    assert Valorant.go(host) is True
    screenshot_manager.init_sources.assert_called_once_with()
    host.init_mouse.assert_called_once_with()
    host.time_set_event.assert_not_called()
    thread_factory.assert_not_called()
