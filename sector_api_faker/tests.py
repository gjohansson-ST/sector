"""HTTP tests for the standalone Sector Alarm API faker."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import unittest
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from .auth import is_valid_token, issue_token
from .climate import climate_value
from .inventory import ALARM_PANEL, DEVICES_BY_SERIAL
from .server import FakerHTTPServer, main as server_main, parse_legacy_mode
from .state import FakerState

TEST_USER = "faker@example.test"
TEST_PASSWORD = "123456"
PANEL_ID = ALARM_PANEL.serial


class SectorAPIFakerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "SECTOR_API_USER": TEST_USER,
                "SECTOR_API_PASSWORD": TEST_PASSWORD,
                "PANEL_ID": PANEL_ID,
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.server = FakerHTTPServer(("127.0.0.1", 0), FakerState())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.token = self._request(
            "POST",
            "/api/Login/Login",
            {"UserId": TEST_USER, "Password": TEST_PASSWORD},
        )["AuthorizationToken"]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}" if hasattr(self, "token") else "",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request) as response:
            return json.loads(response.read())

    def test_alarm_actions_update_state_and_audit_log(self) -> None:
        self._request("POST", "/api/Panel/Arm", {"PanelId": PANEL_ID})
        status = self._request(
            "GET", f"/api/Panel/GetPanelStatus?panelId={PANEL_ID}"
        )
        logs = self._request(
            "GET", f"/api/v2/panel/logs?panelid={PANEL_ID}&pageNumber=1&pageSize=5"
        )

        self.assertEqual(status["Status"], 3)
        self.assertEqual(logs["Records"][0]["EventType"], "armed")
        self.assertEqual(logs["Records"][0]["LockName"], "")
        self.assertEqual(self.server.state.alarm_status, 3)
        self.assertEqual(self.server.state.logs[0]["EventType"], "armed")

        self._request("POST", "/api/Panel/PartialArm", {"PanelId": PANEL_ID})
        self.assertEqual(
            self._request(
                "GET", f"/api/Panel/GetPanelStatus?panelId={PANEL_ID}"
            )["Status"],
            2,
        )
        self._request("POST", "/api/Panel/Disarm", {"PanelId": PANEL_ID})
        self.assertEqual(
            self._request(
                "GET", f"/api/Panel/GetPanelStatus?panelId={PANEL_ID}"
            )["Status"],
            1,
        )

    def test_account_panel_info_and_legacy_temperature_routes(self) -> None:
        panels = self._request("GET", "/api/account/GetPanelList")
        panel = self._request("GET", f"/api/Panel/GetPanel?panelId={PANEL_ID}")
        temperatures = self._request(
            "GET", f"/api/Panel/GetTemperatures?panelId={PANEL_ID}"
        )

        self.assertEqual(len(panels), 1)
        self.assertEqual(panels[0]["PanelId"], PANEL_ID)
        self.assertEqual(panel["PanelCodeLength"], 6)
        self.assertEqual(len(panel["Locks"]), 2)
        self.assertEqual(len(panel["Smartplugs"]), 2)
        self.assertIn("BatteryLow", panel["Locks"][0])
        self.assertEqual(len(temperatures), 3)
        self.assertNotIn(
            "CAMERA001", {temperature["SerialNo"] for temperature in temperatures}
        )
        self.assertNotIn(
            "KEYPAD001", {temperature["SerialNo"] for temperature in temperatures}
        )
        self.assertTrue(temperatures[0]["Temperature"])

    def test_panel_info_only_adds_legacy_capability_when_enabled(self) -> None:
        panel = self._request("GET", f"/api/Panel/GetPanel?panelId={PANEL_ID}")
        self.assertNotIn("UseLegacyHomeScreen", panel["Capabilities"])

        self.server.state.legacy_mode = True
        panel = self._request("GET", f"/api/Panel/GetPanel?panelId={PANEL_ID}")
        self.assertEqual(panel["Capabilities"], ["UseLegacyHomeScreen"])

    def test_legacy_mode_configuration_parses_boolean_values(self) -> None:
        self.assertTrue(parse_legacy_mode("true"))
        self.assertTrue(parse_legacy_mode("YES"))
        self.assertFalse(parse_legacy_mode("false"))
        self.assertFalse(parse_legacy_mode("0"))
        with self.assertRaisesRegex(ValueError, "LEGACY_MODE"):
            parse_legacy_mode("sometimes")

    def test_device_definitions_drive_primary_and_optional_sensor_data(self) -> None:
        smoke = self._request(
            "POST",
            "/api/v2/housecheck/smokedetectors",
            {"PanelId": PANEL_ID},
        )["Floors"][0]["Rooms"][0]["Devices"][0]
        temperatures = self._request(
            "POST",
            "/api/v2/housecheck/temperatures",
            {"PanelId": PANEL_ID},
        )["Sections"][0]["Places"][0]["Components"]
        humidities = self._request(
            "GET",
            f"/api/housecheck/panels/{PANEL_ID}/humidity",
        )["Sections"][0]["Places"][0]["Components"]
        camera_temperature = next(
            component for component in temperatures
            if component["SerialNo"] == "CAMERA001"
        )
        camera_humidity = next(
            component for component in humidities
            if component["SerialNo"] == "CAMERA001"
        )
        keypad_temperature = next(
            component for component in temperatures
            if component["SerialNo"] == "KEYPAD001"
        )
        keypad_humidity = next(
            component for component in humidities
            if component["SerialNo"] == "KEYPAD001"
        )
        kitchen_humidity = next(
            component for component in humidities
            if component["SerialNo"] == "CLIMATE003"
        )

        self.assertEqual(smoke["Type"], "Smoke Detector")
        self.assertTrue(smoke["LowBattery"])
        self.assertIn("Alarm", smoke)
        self.assertEqual(camera_temperature["Type"], "CameraPIR")
        self.assertIn("Temperature", camera_temperature)
        self.assertIn("LowBattery", camera_temperature)
        self.assertIn("Humidity", camera_humidity)
        self.assertEqual(keypad_temperature["Type"], "KeyPad")
        self.assertIn("Temperature", keypad_temperature)
        self.assertIn("LowBattery", keypad_temperature)
        self.assertEqual(keypad_humidity["Type"], "KeyPad")
        self.assertIn("Humidity", keypad_humidity)
        self.assertIn("LowBattery", keypad_humidity)
        self.assertNotIn("LowBattery", kitchen_humidity)

        request = Request(
            self.base_url + f"/api/v2/housecheck/cameras/{PANEL_ID}",
            method="GET",
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )
        with self.assertRaises(HTTPError) as camera_error:
            with urlopen(request):
                pass
        self.assertEqual(camera_error.exception.code, 404)
        camera_error.exception.close()

    def test_lock_and_plug_actions_update_status_and_audit(self) -> None:
        self._request(
            "POST",
            "/api/Panel/Unlock",
            {"PanelId": PANEL_ID, "LockSerial": "LOCK001"},
        )
        self._request(
            "POST",
            f"/api/Panel/TurnOnSmartplug?switchId=plug-001&panelId={PANEL_ID}",
        )

        lock_status = self._request(
            "GET", f"/api/Panel/GetLockStatus?panelId={PANEL_ID}"
        )
        plug_status = self._request(
            "GET", f"/api/Panel/GetSmartplugStatus?panelId={PANEL_ID}"
        )
        logs = self._request(
            "GET", f"/api/v2/panel/logs?panelid={PANEL_ID}&pageNumber=1&pageSize=5"
        )
        self.assertEqual(lock_status[0]["Status"], "unlock")
        self.assertFalse(lock_status[0]["BatteryLow"])
        self.assertEqual(plug_status[0]["Status"], "On")
        self.assertEqual(
            [record["EventType"] for record in logs["Records"][:1]], ["unlock"]
        )
        self.assertEqual(self.server.state.lock_states["LOCK001"], "unlock")
        self.assertEqual(self.server.state.plug_states["PLUG001"], "On")

    def test_all_supported_housecheck_routes_return_coordinator_shapes(self) -> None:
        doors = self._request(
            "POST",
            "/api/housecheck/doorsandwindows",
            {"PanelId": PANEL_ID},
        )["Floors"][0]["Rooms"][0]["Devices"]
        back_door = next(
            device for device in doors if device["SerialString"] == "DOOR002"
        )
        self.assertFalse(back_door["Closed"])

        for path, body in (
            ("/api/v2/housecheck/temperatures", {"PanelId": PANEL_ID}),
            ("/api/v2/housecheck/leakagedetectors", {"PanelId": PANEL_ID}),
            ("/api/v2/housecheck/smokedetectors", {"PanelId": PANEL_ID}),
        ):
            data = self._request("POST", path, body)
            self.assertTrue("Floors" in data or "Sections" in data)

        humidity = self._request(
            "GET", f"/api/housecheck/panels/{PANEL_ID}/humidity"
        )
        self.assertIn("Sections", humidity)
        self.assertIn("Humidity", humidity["Sections"][0]["Places"][0]["Components"][0])

    def test_climate_values_are_stable_per_interval_and_realistic(self) -> None:
        camera = DEVICES_BY_SERIAL["CAMERA001"]
        first = climate_value(camera, "temperature", now=3600)
        same_interval = climate_value(camera, "temperature", now=5399)
        next_interval = climate_value(camera, "temperature", now=5400)
        humidity = climate_value(camera, "humidity", now=3600)

        self.assertEqual(first, same_interval)
        self.assertNotEqual(first, next_interval)
        self.assertGreaterEqual(first, 16.0)
        self.assertLessEqual(first, 26.0)
        self.assertGreaterEqual(humidity, 25.0)
        self.assertLessEqual(humidity, 65.0)

    def test_device_state_resets_for_a_new_state_instance(self) -> None:
        self.server.state.update_alarm(3, "armed")
        self.server.state.update_lock("LOCK001", "unlock")
        self.server.state.update_plug("plug-001", "On")

        fresh_state = FakerState()

        self.assertEqual(fresh_state.alarm_status, 1)
        self.assertEqual(fresh_state.lock_states["LOCK001"], "lock")
        self.assertEqual(fresh_state.plug_states["PLUG001"], "Off")
        self.assertEqual(fresh_state.logs, [])

    def test_audit_log_uses_default_and_configured_time_zones(self) -> None:
        default_state = FakerState()
        self.assertEqual(default_state.time_zone.key, "Europe/Stockholm")
        default_state.update_alarm(3, "armed")
        default_timestamp = datetime.fromisoformat(default_state.logs[0]["Time"])
        self.assertIn(
            default_timestamp.utcoffset(),
            (timedelta(hours=1), timedelta(hours=2)),
        )

        configured_state = FakerState("Asia/Kolkata")
        configured_state.update_alarm(3, "armed")
        configured_timestamp = datetime.fromisoformat(
            configured_state.logs[0]["Time"]
        )
        self.assertEqual(
            configured_timestamp.utcoffset(),
            timedelta(hours=5, minutes=30),
        )

    def test_audit_log_rejects_an_invalid_time_zone(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown or unavailable IANA"):
            FakerState("Not/A-Time-Zone")

    def test_login_requires_credentials_and_protected_routes_require_token(self) -> None:
        with self.assertRaises(HTTPError) as login_error:
            request = Request(
                self.base_url + "/api/Login/Login",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request):
                pass
        self.assertEqual(login_error.exception.code, 401)
        login_error.exception.close()

        request = Request(self.base_url + "/api/account/GetPanelList")
        with self.assertRaises(HTTPError) as protected_error:
            with urlopen(request):
                pass
        self.assertEqual(protected_error.exception.code, 401)
        protected_error.exception.close()

    def test_login_rejects_incorrect_credentials(self) -> None:
        for credentials in (
            {"UserId": "wrong@example.test", "Password": TEST_PASSWORD},
            {"UserId": TEST_USER, "Password": "wrong"},
        ):
            request = Request(
                self.base_url + "/api/Login/Login",
                data=json.dumps(credentials).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as login_error:
                with urlopen(request):
                    pass
            self.assertEqual(login_error.exception.code, 401)
            login_error.exception.close()

    def test_startup_requires_user_password_and_panel_id(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SECTOR_API_USER": "",
                "SECTOR_API_PASSWORD": "",
                "PANEL_ID": "",
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "SECTOR_API_USER, SECTOR_API_PASSWORD, PANEL_ID",
            ):
                server_main()

    def test_login_returns_unsigned_jwt_with_expiration(self) -> None:
        header_part, payload_part, signature = self.token.split(".")
        header_part += "=" * (-len(header_part) % 4)
        payload_part += "=" * (-len(payload_part) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_part))
        payload = json.loads(base64.urlsafe_b64decode(payload_part))

        self.assertEqual(header["alg"], "none")
        self.assertEqual(signature, "")
        self.assertEqual(payload["iss"], "sector-api-faker")
        self.assertEqual(payload["panelId"], PANEL_ID)
        self.assertIsInstance(payload["jti"], str)
        self.assertGreater(payload["exp"], int(time.time()))
        self.assertTrue(is_valid_token(self.token))

        second_token = self._request(
            "POST",
            "/api/Login/Login",
            {"UserId": TEST_USER, "Password": TEST_PASSWORD},
        )["AuthorizationToken"]
        self.assertNotEqual(second_token, self.token)

    def test_requests_reject_unissued_and_altered_tokens(self) -> None:
        header_part, payload_part, _ = self.token.split(".")
        payload_part += "=" * (-len(payload_part) % 4)
        original_payload = json.loads(base64.urlsafe_b64decode(payload_part))
        for claim, value in (
            ("jti", "not-issued-by-this-faker"),
            ("panelId", "another-panel"),
        ):
            payload = original_payload.copy()
            payload[claim] = value
            forged_payload = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":")).encode()
            ).decode("ascii").rstrip("=")
            forged_token = f"{header_part}.{forged_payload}."
            request = Request(
                self.base_url + "/api/account/GetPanelList",
                headers={"Authorization": f"Bearer {forged_token}"},
            )

            with self.assertRaises(HTTPError) as response:
                with urlopen(request):
                    pass
            self.assertEqual(response.exception.code, 401)
            response.exception.close()

    def test_token_expiration_is_enforced(self) -> None:
        with patch("sector_api_faker.auth.time.time", return_value=1000):
            token = issue_token(TEST_USER, PANEL_ID)
        with patch("sector_api_faker.auth.time.time", return_value=4599):
            self.assertTrue(is_valid_token(token))
        with patch("sector_api_faker.auth.time.time", return_value=4600):
            self.assertFalse(is_valid_token(token))


if __name__ == "__main__":
    unittest.main()
