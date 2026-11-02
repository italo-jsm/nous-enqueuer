import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


os.environ.setdefault("RABBITMQ_URL", "amqp://localhost:5672/%2F")
_fake_pika = MagicMock()
with patch.dict(sys.modules, {"pika": _fake_pika}):
    app_module = importlib.import_module("app")


class TelegramWebhookTests(unittest.TestCase):
    def setUp(self):
        self.application = app_module.create_app(
            {
                "RABBITMQ_URL": "amqp://broker/vhost",
                "RABBITMQ_QUEUE": "telegram_updates",
                "TESTING": True,
            }
        )
        self.client = self.application.test_client()

    @patch("app.publish_update")
    def test_accepts_update_without_credentials_and_preserves_body(self, publish):
        raw_update = b'{ "update_id": 42, "message": {"text": "hello"} }'

        response = self.client.post(
            "/telegram/webhook",
            data=raw_update,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        publish.assert_called_once_with(
            raw_update.decode("utf-8"), "amqp://broker/vhost", "telegram_updates"
        )

    @patch("app.publish_update")
    def test_rejects_malformed_or_non_json_body(self, publish):
        for body, content_type in (
            (b'{"update_id":', "application/json"),
            (b'{"update_id": 1}', "text/plain"),
            (b"[]", "application/json"),
            (b'{"text":"\xff"}', "application/json"),
            (b'{"value":NaN}', "application/json"),
        ):
            with self.subTest(content_type=content_type, body=body):
                response = self.client.post(
                    "/telegram/webhook", data=body, content_type=content_type
                )
                self.assertEqual(response.status_code, 400)

        publish.assert_not_called()

    @patch("app.publish_update")
    def test_returns_503_when_rabbitmq_publication_fails(self, publish):
        publish.side_effect = app_module.RabbitMQPublishError("broker offline")

        response = self.client.post(
            "/telegram/webhook",
            json={"update_id": 7},
        )

        self.assertEqual(response.status_code, 503)

    def test_requires_rabbitmq_url_during_app_initialization(self):
        with self.assertRaisesRegex(RuntimeError, "RABBITMQ_URL"):
            app_module.create_app({"RABBITMQ_URL": ""})

    @patch("app.validate_rabbitmq_url")
    def test_rejects_invalid_rabbitmq_url_during_app_initialization(self, validate):
        validate.side_effect = ValueError("invalid AMQP URI")

        with self.assertRaisesRegex(RuntimeError, "valid AMQP URI"):
            app_module.create_app({"RABBITMQ_URL": "not-a-uri"})


if __name__ == "__main__":
    unittest.main()
