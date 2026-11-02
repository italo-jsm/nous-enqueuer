# Telegram RabbitMQ Webhook

Small Flask service that accepts Telegram webhook updates and publishes each original JSON body to RabbitMQ.

## Requirements

- Python 3.9 or newer
- A RabbitMQ broker and its AMQP URI
- A public HTTPS URL for Telegram to reach the service

## Install and configure

Create a virtual environment and install dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Set the RabbitMQ URI supplied for your deployment. The queue defaults to `telegram_updates`; override it if needed.
The service fails at startup if `RABBITMQ_URL` is missing or is not a valid AMQP URI.

```sh
export RABBITMQ_URL='amqp://user:password@rabbitmq-host:5672/%2F'
export RABBITMQ_QUEUE='telegram_updates'
```

`.env.example` lists the configuration names with a local broker example. The service does not load `.env` files automatically. Do not commit real credentials.

## Run

Start the production WSGI server:

```sh
gunicorn --bind 0.0.0.0:8000 app:app
```

## Run with Docker

Build the image:

```sh
docker build -t telegram-rabbitmq-webhook .
```

With `RABBITMQ_URL` exported in the shell, start the container and pass the configuration at runtime:

```sh
docker run -d \
  --name telegram-rabbitmq-webhook \
  --restart unless-stopped \
  -p 8000:8000 \
  -e RABBITMQ_URL \
  -e RABBITMQ_QUEUE=telegram_updates \
  telegram-rabbitmq-webhook
```

The image runs as a non-root user. Do not put broker credentials in the Dockerfile or image.

Every push to `main` builds and publishes `linux/amd64` and `linux/arm64` variants as `ghcr.io/<owner>/nous-enqueuer:sha-<commit>` and `:latest`. Use the SHA tag in GitOps when pinning a deployment image.

Configure Telegram's webhook separately to call `https://<host>/telegram/webhook`. The host must route HTTPS traffic to this service. The endpoint has no application authentication in this first version.

The service returns success only after RabbitMQ confirms the publication. Broker failures return HTTP 503 so Telegram can retry. Each request body is queued as a persistent message in a durable queue.

## Tests

Run the test suite from the repository root:

```sh
python -m unittest discover -s tests -v
```
