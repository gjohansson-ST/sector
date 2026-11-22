"""HTTP routes for the Sector Alarm API faker."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Any, Protocol, cast
from urllib.parse import parse_qs, urlsplit

from .auth import credentials_match, is_valid_token, issue_token
from .inventory import ALARM_PANEL
from .payloads import (
    climate_components,
    housecheck_devices,
    legacy_temperatures,
    lock_status,
    logs,
    panel_info,
    panel_list,
    panel_status,
    smart_plug_status,
)
from .state import FakerState

LOGGER = logging.getLogger("sector_api_faker")


class StateServer(Protocol):
    state: FakerState


@dataclass(frozen=True)
class RouteResponse:
    status: int
    body: Any


class SectorAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _dispatch(self, method: str) -> None:
        parsed = urlsplit(self.path)
        route = parsed.path.lower()
        query = {
            key.lower(): value for key, value in parse_qs(parsed.query).items()
        }
        if route == "/api/login/login" and method == "POST":
            body = self._read_json()
            if body is not None:
                self._login(body)
            return
        if not self._authorized():
            self._send_json(401, {"error": "Unauthorized"})
            return

        body = self._read_json() if method == "POST" else {}
        if body is None:
            return

        panel_id = query.get("panelid", [body.get("PanelId", "")])[0]
        if route == "/api/account/getpanellist" and method == "GET":
            self._send_json(200, panel_list())
        elif route == "/api/panel/getpanel" and method == "GET":
            self._with_panel(panel_id, lambda: panel_info(self.faker_server.state))
        elif route == "/api/panel/getpanelstatus" and method == "GET":
            self._with_panel(panel_id, lambda: panel_status(self.faker_server.state))
        elif route == "/api/panel/getsmartplugstatus" and method == "GET":
            self._with_panel(
                panel_id, lambda: smart_plug_status(self.faker_server.state)
            )
        elif route == "/api/panel/getlockstatus" and method == "GET":
            self._with_panel(panel_id, lambda: lock_status(self.faker_server.state))
        elif route == "/api/panel/gettemperatures" and method == "GET":
            self._with_panel(panel_id, legacy_temperatures)
        elif route == "/api/v2/panel/logs" and method == "GET":
            self._with_panel(panel_id, lambda: self._logs(query))
        elif route == "/api/housecheck/doorsandwindows" and method == "POST":
            self._with_panel(
                panel_id, lambda: housecheck_devices("doorsandwindows")
            )
        elif method == "GET" and (
            humidity_route := re.fullmatch(
                r"/api/housecheck/panels/([^/]+)/humidity",
                parsed.path,
                re.IGNORECASE,
            )
        ):
            self._with_panel(
                humidity_route.group(1),
                lambda: climate_components("humidity"),
            )
        elif route == "/api/v2/housecheck/temperatures" and method == "POST":
            self._with_panel(
                panel_id, lambda: climate_components("temperature")
            )
        elif route == "/api/v2/housecheck/leakagedetectors" and method == "POST":
            self._with_panel(
                panel_id, lambda: housecheck_devices("leakagedetectors")
            )
        elif route == "/api/v2/housecheck/smokedetectors" and method == "POST":
            self._with_panel(
                panel_id, lambda: housecheck_devices("smokedetectors")
            )
        elif route in {
            "/api/panel/arm",
            "/api/panel/partialarm",
            "/api/panel/disarm",
        } and method == "POST":
            self._with_panel(panel_id, lambda: self._set_alarm(route))
        elif route in {"/api/panel/lock", "/api/panel/unlock"} and method == "POST":
            self._with_panel(panel_id, lambda: self._set_lock(route, body))
        elif route in {
            "/api/panel/turnonsmartplug",
            "/api/panel/turnoffsmartplug",
        } and method == "POST":
            self._with_panel(panel_id, lambda: self._set_plug(route, query))
        else:
            self._send_json(404, {"error": "Not found"})

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Invalid JSON"})
            return None
        if not isinstance(value, dict):
            self._send_json(400, {"error": "Expected a JSON object"})
            return None
        return value

    def _login(self, body: dict[str, Any]) -> None:
        user = body.get("UserId")
        password = body.get("Password")
        if (
            not isinstance(user, str)
            or not user
            or not isinstance(password, str)
            or not password
        ):
            self._send_json(401, {"error": "UserId and Password are required"})
            return
        if not credentials_match(user, password):
            self._send_json(401, {"error": "Invalid credentials"})
            return
        self._send_json(
            200,
            {"AuthorizationToken": issue_token(user, ALARM_PANEL.serial)},
        )

    def _authorized(self) -> bool:
        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "bearer" and is_valid_token(token)

    def _with_panel(
        self, panel_id: str, handler: Callable[[], Any]
    ) -> None:
        if panel_id != ALARM_PANEL.serial:
            self._send_json(404, {"error": "Panel not found"})
            return
        response = handler()
        if isinstance(response, RouteResponse):
            self._send_json(response.status, response.body)
        else:
            self._send_json(200, response)

    @property
    def faker_server(self) -> StateServer:
        return cast(StateServer, self.server)

    def _logs(self, query: dict[str, list[str]]) -> dict[str, Any]:
        page_size = min(max(int(query.get("pagesize", ["5"])[0]), 1), 100)
        page_number = max(int(query.get("pagenumber", ["1"])[0]), 1)
        return logs(self.faker_server.state, page_number, page_size)

    def _set_alarm(self, route: str) -> dict[str, bool]:
        if route.endswith("/disarm"):
            self.faker_server.state.update_alarm(1, "disarmed")
        elif route.endswith("/partialarm"):
            self.faker_server.state.update_alarm(2, "armed")
        else:
            self.faker_server.state.update_alarm(3, "armed")
        return {"Success": True}

    def _set_lock(self, route: str, body: dict[str, Any]) -> dict[str, Any] | RouteResponse:
        serial = body.get("LockSerial") or body.get("SerialNo")
        status = "lock" if route.endswith("/lock") else "unlock"
        if not isinstance(serial, str) or not self.faker_server.state.update_lock(
            serial, status
        ):
            return RouteResponse(404, {"error": "Lock not found"})
        return {"Success": True}

    def _set_plug(
        self, route: str, query: dict[str, list[str]]
    ) -> dict[str, Any] | RouteResponse:
        plug_id = query.get("switchid", [""])[0]
        status = "On" if route.endswith("/turnonsmartplug") else "Off"
        if not self.faker_server.state.update_plug(plug_id, status):
            return RouteResponse(404, {"error": "Smart plug not found"})
        return {"Success": True}

    def _send_json(self, status: int, value: Any) -> None:
        data = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
