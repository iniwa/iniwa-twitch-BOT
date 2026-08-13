import pytest

from twitchbot.settings import AppSettings, SettingsValidationError


def test_settings_defaults_are_explicit_and_serialization_is_detached():
    settings = AppSettings()
    assert settings.enable_vod_download is False
    payload = settings.to_mapping()
    payload["ignored_users"].append("viewer")
    assert settings.ignored_users == ()
    assert not any("token" in key or "secret" in key for key in payload)


@pytest.mark.parametrize(
    ("mapping", "code"),
    [
        ({"unexpected": True}, "unknown_key"),
        ({"access_token": "do-not-echo"}, "credential_key"),
        ({"bot_enabled": 1}, "invalid_type"),
        ({"stream_poll_interval_seconds": 0}, "out_of_range"),
        ({"metrics_flush_interval_seconds": 3601}, "out_of_range"),
        ({"ignored_users": ["Viewer"]}, "invalid_filter"),
        ({"ignored_users": ["viewer", "viewer"]}, "duplicate_filter"),
        ({"ignored_users": ["u"] * 101}, "too_many_filters"),
    ],
)
def test_settings_reject_invalid_mappings_without_echoing_values(mapping, code):
    with pytest.raises(SettingsValidationError) as caught:
        AppSettings.from_mapping(mapping)
    assert caught.value.code == code
    assert "do-not-echo" not in str(caught.value)


def test_settings_accept_valid_mapping_and_freezes_filters():
    settings = AppSettings.from_mapping({"enable_vod_download": True, "ignored_users": ["viewer_1"]})
    assert settings.enable_vod_download is True
    assert settings.ignored_users == ("viewer_1",)
