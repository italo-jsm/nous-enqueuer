"""RabbitMQ publishing helpers for Telegram updates."""

import pika


class RabbitMQPublishError(Exception):
    """Raised when an update cannot be confirmed by RabbitMQ."""


def validate_rabbitmq_url(rabbitmq_url):
    """Raise ValueError when the configured AMQP URI cannot be parsed."""
    try:
        pika.URLParameters(rabbitmq_url)
    except Exception as error:
        raise ValueError("RABBITMQ_URL must be a valid AMQP URI") from error


def publish_update(update_json, rabbitmq_url, queue_name):
    """Publish one JSON update and wait for RabbitMQ's publisher confirmation."""
    connection = None
    failure = None
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.confirm_delivery()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=update_json,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )
    except Exception as error:
        failure = error
    finally:
        if connection is not None:
            try:
                if connection.is_open:
                    connection.close()
            except Exception as error:
                if failure is None:
                    failure = error

    if failure is not None:
        raise RabbitMQPublishError("Could not publish update to RabbitMQ") from failure
