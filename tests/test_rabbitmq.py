import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


_fake_pika = MagicMock()
_fake_pika.BasicProperties.side_effect = lambda **kwargs: types.SimpleNamespace(**kwargs)
with patch.dict(sys.modules, {"pika": _fake_pika}):
    rabbitmq = importlib.import_module("rabbitmq")


class PublishUpdateTests(unittest.TestCase):
    def setUp(self):
        self.pika = rabbitmq.pika
        self.connection = MagicMock()
        self.channel = MagicMock()
        self.connection.channel.return_value = self.channel
        self.pika.BlockingConnection.return_value = self.connection
        self.pika.BlockingConnection.side_effect = None
        self.pika.BlockingConnection.reset_mock()
        self.pika.URLParameters.side_effect = None
        self.pika.URLParameters.reset_mock()
        self.pika.BasicProperties.side_effect = lambda **kwargs: types.SimpleNamespace(**kwargs)
        self.pika.BasicProperties.reset_mock()

    def test_validates_amqp_uri(self):
        rabbitmq.validate_rabbitmq_url("amqp://broker/vhost")

        self.pika.URLParameters.assert_called_once_with("amqp://broker/vhost")

    def test_rejects_unparseable_amqp_uri(self):
        self.pika.URLParameters.side_effect = ValueError("invalid URI")

        with self.assertRaisesRegex(ValueError, "valid AMQP URI"):
            rabbitmq.validate_rabbitmq_url("not-a-uri")

    def test_publishes_original_json_to_durable_queue_with_confirmation(self):
        update = '{"update_id":7,"message":{"text":"hello"}}'

        rabbitmq.publish_update(update, "amqp://broker/vhost", "telegram_updates")

        self.pika.URLParameters.assert_called_once_with("amqp://broker/vhost")
        self.pika.BlockingConnection.assert_called_once_with(
            self.pika.URLParameters.return_value
        )
        self.channel.confirm_delivery.assert_called_once_with()
        self.channel.queue_declare.assert_called_once_with(
            queue="telegram_updates", durable=True
        )
        publish_args = self.channel.basic_publish.call_args.kwargs
        self.assertEqual(publish_args["exchange"], "")
        self.assertEqual(publish_args["routing_key"], "telegram_updates")
        self.assertEqual(publish_args["body"], update)
        self.assertEqual(publish_args["properties"].delivery_mode, 2)
        self.connection.close.assert_called_once_with()

    def test_raises_publish_error_when_broker_rejects_confirmation(self):
        self.channel.basic_publish.side_effect = RuntimeError("negative confirmation")

        with self.assertRaises(rabbitmq.RabbitMQPublishError):
            rabbitmq.publish_update("{}", "amqp://broker/vhost", "telegram_updates")

        self.connection.close.assert_called_once_with()

    def test_raises_publish_error_when_connection_close_fails(self):
        self.connection.close.side_effect = RuntimeError("close failed")

        with self.assertRaises(rabbitmq.RabbitMQPublishError):
            rabbitmq.publish_update("{}", "amqp://broker/vhost", "telegram_updates")

    def test_raises_publish_error_when_connection_fails(self):
        self.pika.BlockingConnection.side_effect = RuntimeError("offline")

        with self.assertRaises(rabbitmq.RabbitMQPublishError):
            rabbitmq.publish_update("{}", "amqp://broker/vhost", "telegram_updates")


if __name__ == "__main__":
    unittest.main()
