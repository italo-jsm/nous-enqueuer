"""Validation for raw Telegram webhook JSON bodies."""

import json


def _reject_nonstandard_constant(value):
    raise ValueError("Non-standard JSON constant: {}".format(value))


def parse_telegram_update(raw_body):
    """Validate a UTF-8 JSON object and return its original decoded body."""
    try:
        raw_update = raw_body.decode("utf-8")
        update = json.loads(raw_update, parse_constant=_reject_nonstandard_constant)
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError) as error:
        raise ValueError("Telegram update must be valid UTF-8 JSON") from error

    if not isinstance(update, dict):
        raise ValueError("Telegram update must be a JSON object")

    return raw_update
