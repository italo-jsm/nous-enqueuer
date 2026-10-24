from datetime import datetime, timezone
import hmac
import json
import logging
from typing import Any, Callable

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from enqueuer.mapper import InvalidUpdate, map_update
from enqueuer.publisher import ConfirmedPublisher, PublishFailure

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 1024 * 1024


def create_app(config: dict[str, Any] | None = None, *, publisher=None) -> Flask:
    app = Flask(__name__)
    logging.getLogger("enqueuer").setLevel(logging.INFO)
    values = dict(config or {})
    if config is None:
        from enqueuer.config import Settings
        settings = Settings.from_env()
        values = {
            "BOT_ID": settings.bot_id,
            "WEBHOOK_SECRET": settings.webhook_secret,
            "ALLOWED_SENDER_IDS": settings.allowed_sender_ids,
            "MAX_BODY_BYTES": MAX_BODY_BYTES,
        }
        publisher = publisher or ConfirmedPublisher(settings)
    required = ("BOT_ID", "WEBHOOK_SECRET", "ALLOWED_SENDER_IDS")
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise ValueError("Missing required webhook configuration: " + ", ".join(missing))
    values.setdefault("MAX_BODY_BYTES", MAX_BODY_BYTES)
    values.setdefault("CLOCK", lambda: datetime.now(timezone.utc))
    app.config.update(values)
    app.config["MAX_CONTENT_LENGTH"] = int(app.config["MAX_BODY_BYTES"])
    if publisher is None:
        raise ValueError("publisher is required")
    app.extensions["message_publisher"] = publisher

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return jsonify(error="payload_too_large"), 413

    @app.errorhandler(BadRequest)
    def bad_request(_error):
        return jsonify(error="invalid_request"), 400

    @app.post("/telegram/webhook")
    def telegram_webhook():
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected = app.config["WEBHOOK_SECRET"]
        if not supplied or not hmac.compare_digest(supplied, expected):
            return "", 403

        try:
            if request.content_length is not None and request.content_length > app.config["MAX_BODY_BYTES"]:
                return jsonify(error="payload_too_large"), 413
            update = request.get_json(force=True, silent=False)
            event = map_update(
                update,
                bot_id=app.config["BOT_ID"],
                allowed_sender_ids=frozenset(str(item) for item in app.config["ALLOWED_SENDER_IDS"]),
                received_at=app.config["CLOCK"](),
            )
        except (BadRequest, InvalidUpdate, UnicodeDecodeError, json.JSONDecodeError):
            return jsonify(error="invalid_request"), 400
        if event is None:
            return "", 204
        try:
            app.extensions["message_publisher"].publish(event)
        except PublishFailure:
            logger.warning("webhook publish unavailable; botId=%s updateId=%s", event["botId"], event["updateId"])
            return jsonify(error="temporarily_unavailable"), 503
        except Exception as error:
            logger.warning(
                "webhook publish unavailable; botId=%s updateId=%s error_type=%s",
                event["botId"], event["updateId"], type(error).__name__,
            )
            return jsonify(error="temporarily_unavailable"), 503
        logger.info("webhook accepted; botId=%s updateId=%s", event["botId"], event["updateId"])
        return "", 204

    @app.get("/health/live")
    def live():
        return jsonify(status="UP"), 200

    @app.get("/health/ready")
    def ready():
        check = getattr(app.extensions["message_publisher"], "check_ready", None)
        if check is not None and not check():
            return jsonify(status="DOWN"), 503
        return jsonify(status="UP"), 200

    return app
