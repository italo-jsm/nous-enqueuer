from dataclasses import dataclass
import os


def _required(env: dict[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"Required configuration is missing: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    bot_id: str
    webhook_secret: str
    allowed_sender_ids: frozenset[str]
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_vhost: str
    rabbitmq_username: str
    rabbitmq_password: str
    publish_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        allowed = frozenset(
            item.strip() for item in _required(source, "ALLOWED_SENDER_IDS").split(",") if item.strip()
        )
        if not allowed:
            raise ValueError("ALLOWED_SENDER_IDS must contain at least one sender ID")
        try:
            port = int(source.get("RABBITMQ_PORT", "5672"))
            timeout = float(source.get("PUBLISH_TIMEOUT_SECONDS", "5"))
        except ValueError as error:
            raise ValueError("RabbitMQ port and timeout must be numeric") from error
        if not 1 <= port <= 65535 or timeout <= 0:
            raise ValueError("RabbitMQ port and timeout are outside valid ranges")
        return cls(
            bot_id=_required(source, "BOT_ID"),
            webhook_secret=_required(source, "WEBHOOK_SECRET"),
            allowed_sender_ids=allowed,
            rabbitmq_host=_required(source, "RABBITMQ_HOST"),
            rabbitmq_port=port,
            rabbitmq_vhost=_required(source, "RABBITMQ_VHOST"),
            rabbitmq_username=_required(source, "RABBITMQ_USERNAME"),
            rabbitmq_password=_required(source, "RABBITMQ_PASSWORD"),
            publish_timeout_seconds=timeout,
        )

