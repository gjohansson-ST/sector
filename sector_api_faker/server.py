"""Server startup for the Sector Alarm API faker."""

from __future__ import annotations

import logging
import os
from http.server import ThreadingHTTPServer

from .http_handler import SectorAPIHandler
from .inventory import ALARM_PANEL
from .state import DEFAULT_TIME_ZONE, FakerState

LOGGER = logging.getLogger("sector_api_faker")
REQUIRED_ENVIRONMENT_VARIABLES = (
    "SECTOR_API_USER",
    "SECTOR_API_PASSWORD",
    "PANEL_ID",
)


def validate_required_environment() -> None:
    missing = [
        name
        for name in REQUIRED_ENVIRONMENT_VARIABLES
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )


def parse_legacy_mode(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(
        "LEGACY_MODE must be true or false (accepted: 1/0, yes/no, on/off)"
    )


class FakerHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], state: FakerState) -> None:
        super().__init__(address, SectorAPIHandler)
        self.state = state


def main() -> None:
    validate_required_environment()
    legacy_mode = parse_legacy_mode(os.environ.get("LEGACY_MODE", "false"))
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = FakerHTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", "8080"))),
        FakerState(
            os.environ.get("TIME_ZONE", DEFAULT_TIME_ZONE),
            legacy_mode=legacy_mode,
        ),
    )
    LOGGER.info(
        "Sector API faker listening on port %s for panel %s",
        server.server_port,
        ALARM_PANEL.serial,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping Sector API faker")
    finally:
        server.server_close()
