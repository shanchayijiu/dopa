from pathlib import Path

from core.mixins import config as config_module


def test_stale_absolute_model_path_falls_back_to_project_models(monkeypatch):
    project_model = Path(config_module.__file__).resolve().parents[2] / "models" / "sjz320v8.engine"
    stale_path = r"C:\old\location\dopa\models\sjz320v8.engine"
    checked_paths = []

    def fake_isfile(path):
        checked_paths.append(Path(path))
        return Path(path) == project_model

    monkeypatch.setattr(config_module.os.path, "isfile", fake_isfile)

    assert config_module.ConfigMixin._resolve_model_path(stale_path) == str(project_model)
    assert checked_paths == [Path(stale_path), project_model]
