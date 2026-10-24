import json
import os

import pika
import pytest

from enqueuer.config import Settings
from enqueuer.publisher import ConfirmedPublisher, QUEUE_NAME, PublishFailure

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_RABBITMQ_INTEGRATION_TESTS") != "true",
    reason="set RUN_RABBITMQ_INTEGRATION_TESTS=true to use a real RabbitMQ broker",
)


def test_confirmed_persistent_message_is_available_from_queue():
    settings = Settings(
        bot_id="bot-1",
        webhook_secret="unused-secret",
        allowed_sender_ids=frozenset({"123"}),
        rabbitmq_host=os.environ["RABBITMQ_TEST_HOST"],
        rabbitmq_port=int(os.environ["RABBITMQ_TEST_PORT"]),
        rabbitmq_vhost=os.environ["RABBITMQ_TEST_VHOST"],
        rabbitmq_username=os.environ["RABBITMQ_TEST_USERNAME"],
        rabbitmq_password=os.environ["RABBITMQ_TEST_PASSWORD"],
    )
    publisher = ConfirmedPublisher(settings)
    assert publisher.check_ready()
    queue_connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=settings.rabbitmq_host, port=settings.rabbitmq_port,
        virtual_host=settings.rabbitmq_vhost,
        credentials=pika.PlainCredentials(settings.rabbitmq_username, settings.rabbitmq_password),
    ))
    try:
        queue_connection.channel().queue_purge(QUEUE_NAME)
    finally:
        queue_connection.close()
    event = {
        "schemaVersion": 1, "source": "telegram", "botId": "bot-1", "updateId": 991,
        "messageId": 2, "chatId": "123", "senderId": "123", "text": "hello",
        "sentAt": "2026-10-24T15:00:00Z", "receivedAt": "2026-10-24T15:00:01Z",
    }
    publisher.publish(event)
    credentials = pika.PlainCredentials(settings.rabbitmq_username, settings.rabbitmq_password)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=settings.rabbitmq_host, port=settings.rabbitmq_port,
        virtual_host=settings.rabbitmq_vhost, credentials=credentials,
    ))
    try:
        channel = connection.channel()
        method, properties, body = channel.basic_get(QUEUE_NAME, auto_ack=False)
        assert method is not None
        assert properties.delivery_mode == 2
        assert properties.content_type == "application/json"
        assert json.loads(body) == event
        channel.basic_ack(method.delivery_tag)
    finally:
        connection.close()


def test_rabbitmq_rejects_wrong_credentials_without_success():
    settings = Settings(
        bot_id="bot-1", webhook_secret="unused-secret", allowed_sender_ids=frozenset({"123"}),
        rabbitmq_host=os.environ["RABBITMQ_TEST_HOST"],
        rabbitmq_port=int(os.environ["RABBITMQ_TEST_PORT"]),
        rabbitmq_vhost=os.environ["RABBITMQ_TEST_VHOST"],
        rabbitmq_username="wrong-user", rabbitmq_password="wrong-password",
    )
    with pytest.raises(PublishFailure):
        ConfirmedPublisher(settings).publish({"botId": "bot-1", "updateId": 1})


def test_stopped_broker_returns_publish_failure():
    settings = Settings(
        bot_id="bot-1", webhook_secret="unused-secret", allowed_sender_ids=frozenset({"123"}),
        rabbitmq_host=os.environ["RABBITMQ_TEST_HOST"],
        rabbitmq_port=int(os.environ["RABBITMQ_TEST_PORT"]) + 1,
        rabbitmq_vhost=os.environ["RABBITMQ_TEST_VHOST"],
        rabbitmq_username=os.environ["RABBITMQ_TEST_USERNAME"],
        rabbitmq_password=os.environ["RABBITMQ_TEST_PASSWORD"],
        publish_timeout_seconds=0.2,
    )
    with pytest.raises(PublishFailure):
        ConfirmedPublisher(settings).publish({"botId": "bot-1", "updateId": 2})


def test_mandatory_unroutable_publish_is_returned_even_with_confirms():
    username = os.environ["RABBITMQ_TEST_USERNAME"]
    password = os.environ["RABBITMQ_TEST_PASSWORD"]
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=os.environ["RABBITMQ_TEST_HOST"],
        port=int(os.environ["RABBITMQ_TEST_PORT"]),
        virtual_host=os.environ["RABBITMQ_TEST_VHOST"],
        credentials=pika.PlainCredentials(username, password),
    ))
    try:
        channel = connection.channel()
        channel.confirm_delivery()
        with pytest.raises(pika.exceptions.UnroutableError):
            channel.basic_publish(
                exchange="", routing_key="ai.telegram.missing-route", body=b"test", mandatory=True,
                properties=pika.BasicProperties(delivery_mode=2),
            )
    finally:
        connection.close()
