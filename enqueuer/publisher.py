import json
import logging
import threading
import time
from typing import Any, Callable

import pika

QUEUE_NAME = "ai.telegram.inbound"
QUEUE_ARGUMENTS = {"x-queue-type": "classic"}
logger = logging.getLogger(__name__)


class PublishFailure(RuntimeError):
    """A publish was not confirmed and routed to the inbound queue."""


class _Deadline:
    def __init__(self, timeout_seconds: float):
        self.ends_at = time.monotonic() + timeout_seconds

    def remaining(self) -> float:
        remaining = self.ends_at - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("RabbitMQ publish deadline expired")
        return remaining


class ConfirmedPublisher:
    def __init__(self, settings=None, connection_factory: Callable[..., Any] | None = None):
        self.settings = settings
        self.connection_factory = connection_factory or self._connect

    def _timeout_seconds(self) -> float:
        return self.settings.publish_timeout_seconds if self.settings is not None else 5.0

    def _connect(self, timeout_seconds: float):
        credentials = pika.PlainCredentials(self.settings.rabbitmq_username, self.settings.rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=self.settings.rabbitmq_host,
            port=self.settings.rabbitmq_port,
            virtual_host=self.settings.rabbitmq_vhost,
            credentials=credentials,
            connection_attempts=1,
            socket_timeout=timeout_seconds,
            stack_timeout=timeout_seconds,
            blocked_connection_timeout=timeout_seconds,
            heartbeat=5,
        )
        return pika.BlockingConnection(parameters)

    @staticmethod
    def _check_deadline(deadline: _Deadline, expired: threading.Event) -> None:
        if expired.is_set():
            raise TimeoutError("RabbitMQ publish deadline expired")
        deadline.remaining()

    @staticmethod
    def _close(connection, timer) -> None:
        if timer is not None:
            timer.cancel()
        if connection is not None:
            try:
                if connection.is_open:
                    connection.close()
            except Exception as error:
                logger.warning("rabbitmq close failed; error_type=%s", type(error).__name__)

    def _prepare_channel(self, deadline: _Deadline):
        connection = self.connection_factory(deadline.remaining())
        expired = threading.Event()

        def abort_connection() -> None:
            expired.set()
            try:
                connection.add_callback_threadsafe(connection.close)
            except Exception:
                pass

        timer = None
        try:
            timer = threading.Timer(deadline.remaining(), abort_connection)
            timer.daemon = True
            timer.start()
            self._check_deadline(deadline, expired)
            channel = connection.channel()
            self._check_deadline(deadline, expired)
            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True,
                exclusive=False,
                auto_delete=False,
                arguments=QUEUE_ARGUMENTS,
            )
            self._check_deadline(deadline, expired)
            channel.confirm_delivery()
            self._check_deadline(deadline, expired)
            return connection, channel, timer, expired
        except Exception:
            self._close(connection, timer)
            raise

    def check_ready(self) -> bool:
        connection = timer = None
        try:
            deadline = _Deadline(self._timeout_seconds())
            connection, _channel, timer, expired = self._prepare_channel(deadline)
            self._check_deadline(deadline, expired)
            return True
        except Exception as error:
            logger.warning("rabbitmq readiness failed; error_type=%s", type(error).__name__)
            return False
        finally:
            self._close(connection, timer)

    def publish(self, event: dict[str, Any]) -> None:
        connection = timer = None
        try:
            deadline = _Deadline(self._timeout_seconds())
            connection, channel, timer, expired = self._prepare_channel(deadline)
            properties = pika.BasicProperties(
                content_type="application/json",
                content_encoding="utf-8",
                delivery_mode=2,
                message_id=f"{event['botId']}:{event['updateId']}",
            )
            body = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._check_deadline(deadline, expired)
            confirmed = channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=body,
                properties=properties,
                mandatory=True,
            )
            self._check_deadline(deadline, expired)
            if confirmed is False:
                raise PublishFailure("RabbitMQ did not confirm the message")
        except Exception as error:
            logger.warning(
                "rabbitmq publish failed; botId=%s updateId=%s error_type=%s",
                event.get("botId"), event.get("updateId"), type(error).__name__,
            )
            raise PublishFailure("Message publication was not confirmed") from error
        finally:
            self._close(connection, timer)
