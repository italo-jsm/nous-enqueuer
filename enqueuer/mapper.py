from datetime import datetime, timezone
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InvalidUpdate(ValueError):
    pass


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidUpdate(f"{field} must be an integer")
    return value


def _utc_timestamp(value: int, field: str) -> str:
    try:
        instant = datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise InvalidUpdate(f"{field} is outside the supported timestamp range") from error
    return instant.isoformat(timespec="seconds").replace("+00:00", "Z")


def _ignore(bot_id: str, update_id: int, reason: str) -> None:
    logger.info("webhook ignored; botId=%s updateId=%s reason=%s", bot_id, update_id, reason)


def map_update(update: Any, *, bot_id: str, allowed_sender_ids: frozenset[str], received_at: datetime) -> dict[str, Any] | None:
    if not isinstance(update, dict):
        raise InvalidUpdate("update must be an object")
    update_id = _integer(update.get("update_id"), "update_id")
    if "message" not in update:
        _ignore(bot_id, update_id, "unsupported_update")
        return None
    message = update["message"]
    if not isinstance(message, dict):
        raise InvalidUpdate("message must be an object")

    message_id = _integer(message.get("message_id"), "message.message_id")
    sent_at = _utc_timestamp(_integer(message.get("date"), "message.date"), "message.date")
    chat = message.get("chat")
    if not isinstance(chat, dict):
        raise InvalidUpdate("message chat object is required")
    chat_id = str(_integer(chat.get("id"), "message.chat.id"))
    chat_type = chat.get("type")
    if not isinstance(chat_type, str):
        raise InvalidUpdate("message.chat.type must be a string")
    if chat_type != "private":
        _ignore(bot_id, update_id, "non_private_chat")
        return None

    text = message.get("text")
    if text is None:
        _ignore(bot_id, update_id, "unsupported_message_type")
        return None
    if not isinstance(text, str):
        raise InvalidUpdate("message.text must be a string")
    if not text.strip():
        _ignore(bot_id, update_id, "empty_text")
        return None
    sender = message.get("from")
    if not isinstance(sender, dict):
        raise InvalidUpdate("private message from object is required")
    sender_id = str(_integer(sender.get("id"), "message.from.id"))
    if sender_id not in allowed_sender_ids:
        _ignore(bot_id, update_id, "sender_not_allowed")
        return None

    received = received_at.astimezone(timezone.utc)
    return {
        "schemaVersion": 1,
        "source": "telegram",
        "botId": bot_id,
        "updateId": update_id,
        "messageId": message_id,
        "chatId": chat_id,
        "senderId": sender_id,
        "text": text,
        "sentAt": sent_at,
        "receivedAt": received.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
