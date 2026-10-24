from datetime import datetime, timezone
import json
import logging
from unittest.mock import Mock

import pytest

from enqueuer.app import create_app


@pytest.fixture
def publisher():
    return Mock()


@pytest.fixture
def client(publisher):
    app = create_app(
        {
            "BOT_ID": "bot-1",
            "WEBHOOK_SECRET": "secret",
            "ALLOWED_SENDER_IDS": {"123"},
            "MAX_BODY_BYTES": 1024 * 1024,
            "CLOCK": lambda: datetime(2026, 10, 24, 15, 0, 1, tzinfo=timezone.utc),
        },
        publisher=publisher,
    )
    app.testing = True
    return app.test_client()


def update(*, update_id=987654321, chat_type="private", sender_id=123, text="Hi ☕"):
    return {
        "update_id": update_id,
        "unused_extra": True,
        "message": {
            "message_id": 42,
            "date": 1792854000,
            "chat": {"id": sender_id, "type": chat_type},
            "from": {"id": sender_id, "username": "ignored"},
            "text": text,
            "another_extra": "ignored",
        },
    }


def post(client, body, *, secret="secret"):
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    return client.post("/telegram/webhook", data=body, headers=headers)


def test_authentication_precedes_json_parsing(client, publisher):
    assert post(client, b"{", secret=None).status_code == 403
    assert post(client, b"{", secret="wrong").status_code == 403
    publisher.publish.assert_not_called()


def test_malformed_json_and_invalid_required_fields_return_400(client, publisher):
    assert post(client, b"{").status_code == 400
    assert post(client, b'{"update_id":1,"message":{}}').status_code == 400
    assert post(client, b'{}').status_code == 400
    publisher.publish.assert_not_called()


@pytest.mark.parametrize(
    "event",
    [
        update(chat_type="group"),
        update(sender_id=987),
        update(text="  "),
        {"update_id": 4, "edited_message": {"text": "ignored"}},
    ],
)
def test_unsupported_or_unauthorized_updates_are_ignored(client, publisher, event):
    response = post(client, json.dumps(event).encode())
    assert response.status_code == 204
    publisher.publish.assert_not_called()


def test_non_private_chat_without_sender_is_ignored(client, publisher):
    event = update(chat_type="group")
    del event["message"]["from"]
    assert post(client, json.dumps(event).encode()).status_code == 204
    publisher.publish.assert_not_called()


def test_ignored_reason_is_logged_without_message_content(client, publisher, caplog):
    caplog.set_level(logging.INFO, logger="enqueuer.mapper")
    event = update(sender_id=987, text="do not log this message")
    assert post(client, json.dumps(event).encode()).status_code == 204
    assert "reason=sender_not_allowed" in caplog.text
    assert "do not log this message" not in caplog.text


def test_accepted_update_is_normalized_and_published(client, publisher):
    response = post(client, json.dumps(update()).encode())
    assert response.status_code == 204
    event = publisher.publish.call_args.args[0]
    assert event == {
        "schemaVersion": 1,
        "source": "telegram",
        "botId": "bot-1",
        "updateId": 987654321,
        "messageId": 42,
        "chatId": "123",
        "senderId": "123",
        "text": "Hi ☕",
        "sentAt": "2026-10-24T15:00:00Z",
        "receivedAt": "2026-10-24T15:00:01Z",
    }


def test_broker_failure_returns_generic_503(client, publisher):
    publisher.publish.side_effect = RuntimeError("private broker details")
    response = post(client, json.dumps(update()).encode())
    assert response.status_code == 503
    assert b"private broker details" not in response.data


def test_request_body_over_one_mib_returns_413(client, publisher):
    response = client.post(
        "/telegram/webhook",
        data=b"x" * (1024 * 1024 + 1),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )
    assert response.status_code == 413
    publisher.publish.assert_not_called()


def test_health_endpoints_separate_process_and_broker_health(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
