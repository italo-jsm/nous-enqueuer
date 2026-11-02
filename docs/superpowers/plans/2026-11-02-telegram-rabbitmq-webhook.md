# Telegram RabbitMQ Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receive Telegram webhook updates in Flask and enqueue the original JSON in RabbitMQ.

**Architecture:** A Flask `POST /telegram/webhook` route forwards each update to a small `pika` publisher module. Configuration comes from environment variables; the publisher declares a durable queue and sends persistent messages with publisher confirms before the route returns success.

**Tech Stack:** Python, Flask, pika, unittest (standard library), Gunicorn for serving the public endpoint.

**Spec:** `docs/superpowers/specs/2026-11-02-telegram-rabbitmq-webhook-design.md`

## Global Constraints

- No application authentication in this version.
- Publish the complete Telegram update JSON without transforming its contents.
- Queue name defaults to `telegram_updates` and can be configured by environment variable.
- RabbitMQ URI is supplied by deployment and must not be hard-coded.
- Return success only after confirmed publication; return an HTTP error when publication fails.
- Do not add consumers, a database, a UI, automatic Telegram webhook setup, or local RabbitMQ Compose configuration.

## Review Focus

- Missing or malformed RabbitMQ URI: service startup must fail with a clear configuration error (factory/config validation tests).
- Malformed request JSON: webhook returns HTTP 400 and does not publish (route test).
- RabbitMQ publication failure or negative confirmation: webhook returns HTTP 503 rather than success (route and publisher tests).
- Queue/message durability: declare a durable queue and publish persistent messages (publisher test).
- Unauthenticated delivery: valid update is accepted without credentials (route test).

---

## File Structure

- `app.py`: Flask application factory and webhook route.
- `rabbitmq.py`: validates the AMQP URI and synchronously publishes each update using a connection opened and closed per update.
- `payload.py`: validates strict UTF-8 JSON Telegram updates while preserving the original request body.
- `requirements.txt`: runtime dependencies (`Flask`, `pika`, `gunicorn`).
- `.env.example`: names and safe example values for `RABBITMQ_URL` and `RABBITMQ_QUEUE`.
- `tests/test_app.py`: route behavior using Flask's test client and a mocked publisher.
- `tests/test_rabbitmq.py`: publisher configuration, durability, confirmation, and failure behavior using mocked `pika` objects.
- `tests/test_payload.py`: strict JSON validation and original-body preservation without external dependencies.
- `README.md`: setup, environment configuration, run command, Telegram webhook URL shape, and tests.

### Task 1: Add runtime dependencies and configuration documentation

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `README.md`

- [ ] Add Flask, pika, and Gunicorn as runtime dependencies.
- [ ] Document required `RABBITMQ_URL`, optional `RABBITMQ_QUEUE` (default `telegram_updates`), local installation, and production start command `gunicorn --bind 0.0.0.0:8000 app:app`.
- [ ] Document that the endpoint is `POST /telegram/webhook`, requires a public HTTPS URL for Telegram deployment, and has no authentication in this version.
- [ ] Document tests with `python -m unittest discover -s tests -v`.

### Task 2: Implement and test RabbitMQ publishing

**Files:**
- Create: `rabbitmq.py`
- Test: `tests/test_rabbitmq.py`

**Interface:** `validate_rabbitmq_url(rabbitmq_url: str) -> None` raises `ValueError` for a malformed URI. `publish_update(update_json: str, rabbitmq_url: str, queue_name: str) -> None` raises a publication exception if broker connection or confirmation fails.

- [ ] Test that the publisher connects using the supplied URI, declares the configured queue as durable, publishes the original JSON with persistent delivery mode and confirms it.
- [ ] Test that connection and negative-confirmation failures raise a publication exception and resources are closed.
- [ ] Test that a connection-close failure is surfaced as a publication exception.
- [ ] Test that malformed AMQP URIs fail validation with a clear error.
- [ ] Implement `publish_update` with `pika.BlockingConnection`, a channel publisher confirm, durable queue declaration, persistent message properties, and `finally` cleanup.
- [ ] Run `python -m unittest discover -s tests -p 'test_rabbitmq.py' -v` and confirm publisher tests pass.

### Task 3: Implement and test the Flask webhook

**Files:**
- Create: `app.py`
- Create: `payload.py`
- Test: `tests/test_app.py`
- Test: `tests/test_payload.py`

**Interface:** `create_app(config: Optional[Dict[str, object]] = None) -> Flask`; app config keys are `RABBITMQ_URL` and `RABBITMQ_QUEUE`. Module-level `app` supports Gunicorn.

`parse_telegram_update(raw_body: bytes) -> str` returns the original UTF-8 JSON body or raises `ValueError` when the body is not a strict JSON object.

- [ ] Test a valid JSON object is forwarded byte-for-byte as received and returns HTTP 200 without requiring credentials.
- [ ] Test malformed/non-JSON input returns HTTP 400 without calling the publisher.
- [ ] Test non-standard JSON constants such as `NaN` are rejected as malformed.
- [ ] Test publisher failure returns HTTP 503 so Telegram can retry.
- [ ] Test missing `RABBITMQ_URL` fails clearly during app initialization.
- [ ] Test malformed `RABBITMQ_URL` fails clearly during app initialization.
- [ ] Implement strict UTF-8 JSON object validation in `payload.py`, preserving the original decoded body; have `POST /telegram/webhook` reject invalid JSON with HTTP 400, load environment configuration, use `telegram_updates` as queue default, and map publishing failures to HTTP 503.
- [ ] Run `python -m unittest discover -s tests -p 'test_app.py' -v`, then `python -m unittest discover -s tests -v`; confirm all tests pass.

### Task 4: Verify deployment instructions

**Files:**
- Modify: `README.md`

- [ ] Check documented commands and environment variable names against the implementation.
- [ ] Confirm the README shows the public URL shape as `https://<host>/telegram/webhook` and explains that an operator must register it with Telegram separately.
- [ ] Run the complete unittest command from the repository root and confirm it passes.
