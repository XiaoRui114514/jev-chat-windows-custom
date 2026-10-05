import json
from app import settings

def test_legacy_plugin_config_survives_partial_save(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"jev_provider": "custom_typesafe", "jev_model": "jev",
        "jev_base_url": "https://example.com", "lang": "ko", "future_field": 42}), encoding="utf-8")
    monkeypatch.setattr(settings, "_CONFIG", str(config))
    monkeypatch.setattr(settings, "_read_env", lambda name: "")
    assert settings.jev_base_url() == "https://example.com"
    assert not any(settings.recognition().values())
    settings.save(debug_view_on=True)
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["lang"] == "ko" and data["future_field"] == 42
    assert data["jev_model"] == "jev" and data["schema_version"] == 2
    assert not list(tmp_path.glob("*.tmp"))
    assert "api_key" not in config.read_text(encoding="utf-8")

def test_bad_config_not_overwritten(tmp_path, monkeypatch):
    import pytest
    config = tmp_path / "config.json"
    config.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(settings, "_CONFIG", str(config))
    with pytest.raises(ValueError, match="原文件未被覆盖"):
        settings.save(lang_text="zh")
    assert config.read_text(encoding="utf-8") == "{broken"

def test_vision_key_separate_and_never_in_json(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setattr(settings, "_read_env", lambda name: "")
    saved = {}
    monkeypatch.setattr(settings, "_set_key", lambda name, key: saved.update({name: key}))
    monkeypatch.setattr(settings, "_notify_env", lambda: None)
    settings.save(vision_key_text="private-key", recognition_options={"article": True},
                  vision_options={"base_url": "https://example.com/v1", "model": "vision"})
    assert saved == {"VISION_API_KEY": "private-key"}
    assert "private-key" not in (tmp_path / "config.json").read_text(encoding="utf-8")
    assert settings.recognition()["article"] is True

