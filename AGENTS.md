# Repository Guidelines

## Project Structure

- `app.py` exposes the Flask Telegram webhook.
- `payload.py` validates raw Telegram JSON bodies without changing them.
- `rabbitmq.py` publishes updates to RabbitMQ.
- `tests/` contains standard-library `unittest` tests for the route, payload validation, and publisher.
- `docs/superpowers/` contains the approved design and implementation plan.

## Setup and Commands

Use Python 3.9 or newer. Create a virtual environment with `python3 -m venv .venv`, activate it, and install dependencies with `pip install -r requirements.txt`. Set `RABBITMQ_URL` before starting the app; `RABBITMQ_QUEUE` is optional and defaults to `telegram_updates`.

- Run locally for development: `flask --app app run --host 0.0.0.0 --port 8000`.
- Serve the public endpoint: `gunicorn --bind 0.0.0.0:8000 app:app`.
- Build and run the container: `docker build -t telegram-rabbitmq-webhook .` then pass `RABBITMQ_URL` with `docker run -e RABBITMQ_URL ...`.
- Pushes to `main` publish SHA and `latest` tags to GHCR via `.github/workflows/publish-ghcr.yml`.
- Run tests: `python -m unittest discover -s tests -v`.

## Style and Tests

Use four spaces for Python indentation, `snake_case` for functions and variables, and descriptive `test_` method names. Keep the service small and synchronous to match Flask and `pika`; add no new framework without updating the design. Tests use `unittest` and mock the broker at the publisher boundary.

## Configuration and Security

Do not commit `.env` files or real broker credentials. `.env.example` is illustrative only; the app reads environment variables directly and does not load dotenv files. The webhook is unauthenticated by design in this initial version, so deployment must provide a public HTTPS endpoint as configured in Telegram.
