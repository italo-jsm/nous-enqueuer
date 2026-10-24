import json
import time
from unittest.mock import Mock
from types import SimpleNamespace

import pika
import pytest

from enqueuer.publisher import ConfirmedPublisher, PublishFailure


@pytest.fixture
def event():
    return {
        "schemaVersion": 1,
        "source": "telegram",
        "botId": "bot-1",
        "updateId": 7,
        "messageId": 3,
        "chatId": "123",
        "senderId": "123",
        "text": "hello",
        "sentAt": "2026-10-24T15:00:00Z",
        "receivedAt": "2026-10-24T15:00:01Z",
    }


def test_publishes_persistent_json_to_durable_queue(event):
    channel = Mock()
    connection = Mock()
    connection.channel.return_value = channel
    publisher = ConfirmedPublisher(connection_factory=Mock(return_value=connection))
    publisher.publish(event)
    channel.queue_declare.assert_called_once_with(
        queue="ai.telegram.inbound", durable=True, exclusive=False, auto_delete=False,
        arguments={"x-queue-type": "classic"},
    )
    channel.confirm_delivery.assert_called_once_with()
    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["exchange"] == ""
    assert kwargs["routing_key"] == "ai.telegram.inbound"
    assert kwargs["mandatory"] is True
    assert json.loads(kwargs["body"]) == event
    assert kwargs["properties"].delivery_mode == 2
    assert kwargs["properties"].content_type == "application/json"
    assert kwargs["properties"].message_id == "bot-1:7"


@pytest.mark.parametrize("error", [pika.exceptions.UnroutableError([]), pika.exceptions.NackError([])])
def test_unroutable_or_nacked_publish_fails(event, error):
    channel = Mock()
    channel.basic_publish.side_effect = error
    connection = Mock()
    connection.channel.return_value = channel
    publisher = ConfirmedPublisher(connection_factory=Mock(return_value=connection))
    with pytest.raises(PublishFailure):
        publisher.publish(event)
    connection.close.assert_called_once_with()


def test_publish_uses_one_deadline_for_connection_and_confirmation(event):
    channel = Mock()
    channel.basic_publish.side_effect = lambda **_kwargs: (time.sleep(0.04), True)[1]
    connection = Mock()
    connection.channel.return_value = channel
    connection.add_callback_threadsafe.side_effect = lambda callback: callback()
    def slow_connect(timeout):
        assert 0 < timeout <= 0.05
        time.sleep(0.03)
        return connection

    publisher = ConfirmedPublisher(
        settings=SimpleNamespace(publish_timeout_seconds=0.05),
        connection_factory=Mock(side_effect=slow_connect),
    )
    with pytest.raises(PublishFailure):
        publisher.publish(event)
    connection.close.assert_called()
    channel.confirm_delivery.assert_called_once_with()
    channel.basic_publish.assert_called_once()


def test_connection_returned_after_deadline_is_closed(event):
    connection = Mock()

    def slow_connect(_timeout):
        time.sleep(0.02)
        return connection

    publisher = ConfirmedPublisher(
        settings=SimpleNamespace(publish_timeout_seconds=0.01),
        connection_factory=Mock(side_effect=slow_connect),
    )
    with pytest.raises(PublishFailure):
        publisher.publish(event)
    connection.close.assert_called_once_with()
