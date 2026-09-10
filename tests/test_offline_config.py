import json

from settings.remote_config import RemoteConfigManager


def test_offline_config_roundtrip_uses_configured_path(tmp_path):
    manager = RemoteConfigManager()
    manager.cfg_file = str(tmp_path / "nested" / "cfg.json")
    payload = {"offline": True, "value": 123}

    assert manager.upload_config(payload) is True
    assert manager.get_remote_config() == payload
    assert json.loads((tmp_path / "nested" / "cfg.json").read_text(encoding="utf-8")) == payload
