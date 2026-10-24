import pytest

from enqueuer.config import Settings
from enqueuer import init_rabbitmq


def test_settings_require_bot_secret_allowlist_and_broker_credentials():
    with pytest.raises(ValueError):
        Settings.from_env({})
    env = {
        "BOT_ID": "bot",
        "WEBHOOK_SECRET": "secret",
        "ALLOWED_SENDER_IDS": " , ",
        "RABBITMQ_HOST": "rabbitmq",
        "RABBITMQ_VHOST": "ai",
        "RABBITMQ_USERNAME": "app",
        "RABBITMQ_PASSWORD": "password",
    }
    with pytest.raises(ValueError, match="at least one sender"):
        Settings.from_env(env)


def test_rabbit_initializer_creates_non_admin_user_with_queue_scoped_access(monkeypatch):
    calls = []
    monkeypatch.setenv("RABBITMQ_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RABBITMQ_BOOTSTRAP_PASSWORD", "admin-secret")
    monkeypatch.setenv("RABBITMQ_USERNAME", "app")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "app-secret")
    monkeypatch.setenv("RABBITMQ_VHOST", "ai")
    monkeypatch.setattr(init_rabbitmq, "_request", lambda *args: calls.append(args))
    init_rabbitmq.initialize()
    assert calls[1][0:2] == ("PUT", "users/app")
    assert calls[1][2] == {"password": "app-secret", "tags": ""}
    assert calls[2][0:2] == ("PUT", "permissions/ai/app")
    assert calls[2][2] == {
        "configure": "^ai.telegram.inbound$",
        "write": r"^amq\.default$",
        "read": "",
    }


def test_rabbit_initializer_rejects_shared_admin_and_app_identity(monkeypatch):
    monkeypatch.setenv("RABBITMQ_BOOTSTRAP_USERNAME", "same")
    monkeypatch.setenv("RABBITMQ_BOOTSTRAP_PASSWORD", "admin-secret")
    monkeypatch.setenv("RABBITMQ_USERNAME", "same")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "app-secret")
    with pytest.raises(ValueError, match="must differ"):
        init_rabbitmq.initialize()
