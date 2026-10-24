"""Create the dedicated RabbitMQ application user without granting admin tags."""
import base64
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from enqueuer.publisher import QUEUE_NAME


def _request(method: str, path: str, payload: dict | None, username: str, password: str) -> None:
    host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    port = os.environ.get("RABBITMQ_MANAGEMENT_PORT", "15672")
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"http://{host}:{port}/api/{path}",
        data=body,
        method=method,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"RabbitMQ management API returned {response.status}")


def initialize() -> None:
    admin = os.environ["RABBITMQ_BOOTSTRAP_USERNAME"]
    admin_password = os.environ["RABBITMQ_BOOTSTRAP_PASSWORD"]
    username = os.environ["RABBITMQ_USERNAME"]
    password = os.environ["RABBITMQ_PASSWORD"]
    vhost = os.environ.get("RABBITMQ_VHOST", "ai")
    if username == admin:
        raise ValueError("RabbitMQ application user must differ from bootstrap administrator")
    encoded_vhost = quote(vhost, safe="")
    encoded_username = quote(username, safe="")
    deadline = time.monotonic() + 90
    delay = 1
    while True:
        try:
            _request("PUT", f"vhosts/{encoded_vhost}", {}, admin, admin_password)
            _request("PUT", f"users/{encoded_username}", {"password": password, "tags": ""}, admin, admin_password)
            _request(
                "PUT",
                f"permissions/{encoded_vhost}/{encoded_username}",
                {
                    "configure": f"^{QUEUE_NAME}$",
                    "write": r"^amq\.default$",
                    "read": "",
                },
                admin,
                admin_password,
            )
            return
        except (HTTPError, URLError, TimeoutError, ConnectionError) as error:
            if time.monotonic() >= deadline:
                print(f"RabbitMQ user initialization failed: {type(error).__name__}", file=sys.stderr)
                raise SystemExit(1) from None
            time.sleep(delay)
            delay = min(delay + 1, 5)


if __name__ == "__main__":
    initialize()
