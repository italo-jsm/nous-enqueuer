# Nous enqueuer

Receives Telegram webhook updates and publishes accepted private text messages
to the durable RabbitMQ queue `ai.telegram.inbound`. The AI consumer is a
separate service. This project does not call an AI model or send Telegram replies.

## Contract and behavior

- Endpoint: `POST /telegram/webhook`.
- The `X-Telegram-Bot-Api-Secret-Token` header is checked before the body is read
  or decoded. Missing or invalid secrets return 403.
- JSON must be valid. Malformed JSON or malformed message fields return 400.
- Only new text messages in private chats from `ALLOWED_SENDER_IDS` are queued.
  Other valid updates are ignored with 204.
- Bodies are limited to 1 MiB. Oversized requests return 413.
- An accepted event returns 204 only after RabbitMQ confirms the persistent
  publish and confirms routing through `mandatory=true`; a broker error, nack,
  returned message, or five-second total publish deadline results in a generic
  503. A timeout after the broker accepted a message can lead to redelivery;
  `botId` and `updateId` remain stable for AI-side deduplication.
- The producer declares `ai.telegram.inbound` as a durable, non-exclusive,
  non-auto-delete classic queue without TTL or dead-letter arguments.
- The JSON fields and types match contract v1 in US-001. Telegram username and
  extra Telegram fields are ignored. `botId` is taken from configuration.
- Logs include event IDs and result, never the message, secret, response, or
  broker credentials. Ignored valid updates are logged with a fixed reason code.

## RabbitMQ container host

The enqueuer runs in Kubernetes as a Deployment. This Compose stack runs only
RabbitMQ and the one-shot account initializer on a Linux host with Docker Engine
and the Compose plugin. Choose a stable private IP for the RabbitMQ host. The
cluster pod network and the AI host must reach TCP/5672 over an authorized
private network; restrict the host firewall to those sources. This sample uses
plain AMQP, so configure RabbitMQ TLS before enabling traffic if that network is
not trusted. The management plugin is enabled only for initialization inside the
Compose network; its port is not published.

Compose uses a private user-defined bridge without Docker's `internal: true`
flag so the host-published AMQP port remains reachable. It does not run or
publish the enqueuer.

1. Copy `.env.example` to `.env`, replace every `REPLACE_*` entry, use separate
   long random bootstrap and application passwords, then run `chmod 600 .env`.
   Keep `.env` out of Git and backups that are not protected as secrets; commit
   only `.env.example`.
2. Give `NOUS_ENQUEUER_IMAGE` the immutable GHCR reference published by CI, for
   example `ghcr.io/italo-jsm/nous-enqueuer:sha-<commit>`. It is used only
   by `rabbitmq-init` to provision the application account. Use the exact digest
   when your deployment process records digests.
3. Validate configuration with
   `docker compose --env-file .env -f compose.yaml config --quiet`.
4. If the GHCR package is private, authenticate with `docker login ghcr.io` using
   a read-only package token. Start RabbitMQ and its initializer with
   `docker compose --env-file .env -f compose.yaml up -d`.
5. Confirm RabbitMQ is healthy with `docker compose --env-file .env -f
   compose.yaml ps`. The enqueuer's readiness endpoint is checked in Kubernetes
   and must be healthy before configuring the Telegram webhook.

The RabbitMQ app user is created by the one-shot `rabbitmq-init` service. It has
no administrator tag, can declare only `ai.telegram.inbound`, cannot consume,
and can publish through RabbitMQ's default exchange. RabbitMQ applies write ACLs
to the default exchange resource (`amq.default`), not to each routing key; the
enqueuer fixes the routing key to `ai.telegram.inbound`. The separate bootstrap
account is only used for that initialization and must not be given to the
enqueuer or AI.

## Enqueuer update and rollback

After CI publishes an immutable image, update the image reference in
`applications/nous-enqueuer/deployment.yaml` in the GitOps repository. Argo CD
rolls out the new Deployment. For rollback, restore the previous immutable image
reference in Git and let Argo CD reconcile. Neither action recreates RabbitMQ or
removes `rabbitmq_data`. Never use `docker compose down -v` for routine updates.

## CI and local development

Python 3.12.12 and Gunicorn serve the container; Flask's development server is
used only when running `python -m enqueuer` locally. Run tests with:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

The RabbitMQ integration tests are opt-in. CI runs them against a temporary
RabbitMQ service with `RUN_RABBITMQ_INTEGRATION_TESTS=true`. The unit suite does
not need Docker, Telegram credentials, or an AI provider.

The workflow tests pull requests and publishes `linux/amd64` and `linux/arm64`
images tagged with the commit SHA on pushes to `main`. CI does not use SSH to
production, change GitOps, manage the RabbitMQ host, or configure the Telegram
webhook. RabbitMQ installation/updates remain a host operation. Register the
webhook separately in a protected environment after network, TLS, Deployment,
and broker readiness are validated.
