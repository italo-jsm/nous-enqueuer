"""Flask application that queues Telegram webhook updates."""

import os
from typing import Dict, Optional

from flask import Flask, jsonify, request

from payload import parse_telegram_update
from rabbitmq import RabbitMQPublishError, publish_update, validate_rabbitmq_url


def create_app(config: Optional[Dict[str, object]] = None) -> Flask:
    """Create the webhook app, reading RabbitMQ settings from the environment."""
    application = Flask(__name__)
    application.config.from_mapping(
        RABBITMQ_URL=os.environ.get("RABBITMQ_URL"),
        RABBITMQ_QUEUE=os.environ.get("RABBITMQ_QUEUE", "telegram_updates"),
    )
    if config is not None:
        application.config.update(config)

    if not application.config.get("RABBITMQ_URL"):
        raise RuntimeError("RABBITMQ_URL must be set before starting the service")
    try:
        validate_rabbitmq_url(application.config["RABBITMQ_URL"])
    except ValueError as error:
        raise RuntimeError("RABBITMQ_URL must be a valid AMQP URI") from error
    if not application.config.get("RABBITMQ_QUEUE"):
        raise RuntimeError("RABBITMQ_QUEUE must not be empty")

    @application.post("/telegram/webhook")
    def telegram_webhook():
        if not request.is_json:
            return jsonify(error="Request body must be JSON"), 400

        try:
            raw_update = parse_telegram_update(request.get_data())
        except ValueError:
            return jsonify(error="Request body contains invalid JSON"), 400

        try:
            publish_update(
                raw_update,
                application.config["RABBITMQ_URL"],
                application.config["RABBITMQ_QUEUE"],
            )
        except RabbitMQPublishError:
            return jsonify(error="Could not enqueue Telegram update"), 503

        return jsonify(status="queued"), 200

    return application


app = create_app()
