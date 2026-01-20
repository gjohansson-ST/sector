from unittest.mock import AsyncMock, MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_CODE
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.client import ApiError, AuthenticationError, LoginError
from custom_components.sector.coordinator import SectorCoordinatorType
from custom_components.sector.lock import async_setup_entry, SectorAlarmLock

_PANEL_ID = "1234"


def _create_mock_coordinator(devices: dict):
    coordinator = MagicMock()
    coordinator.data = {"devices": devices}
    coordinator.async_request_refresh = AsyncMock()
    coordinator.sector_api = MagicMock()
    coordinator.sector_api.lock_door = AsyncMock()
    coordinator.sector_api.unlock_door = AsyncMock()
    return coordinator


def _create_mock_config_entity(code_format: int) -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={
            "panel_id": _PANEL_ID,
            "username": "abc",
            "password": "xyz",
        },
        options={
            "code_format": code_format,
        },
        entry_id="test123",
    )


async def test_setup_creates_lock_entity(hass: HomeAssistant):
    # Prepare
    devices = {
        "SERIAL_123": {
            "name": "Front Door",
            "serial_no": "SERIAL_123",
            "sensors": {"lock_status": "lock"},
            "model": "Smart Lock",
            "last_updated": "",
        },
        "SERIAL_321": {
            "name": "Back Door",
            "serial_no": "SERIAL_321",
            "sensors": {"lock_status": "unlock"},
            "model": "Smart Lock",
            "last_updated": "",
        },
        "OTHER": {
            "name": "Back Door",
            "serial_no": "SERIAL_321",
            "sensors": {"lock_status": "lock"},
            "model": "Dumb Lock",
            "last_updated": "",
        },
    }

    coordinator = _create_mock_coordinator(devices)
    entry = _create_mock_config_entity(6)
    entry.runtime_data = {SectorCoordinatorType.ACTION_DEVICES: coordinator}

    entities = []

    def async_add_entities(new_entities, update_before_add=False):
        entities.extend(new_entities)

    # Act
    await async_setup_entry(hass, entry, async_add_entities)

    # Assert
    assert len(entities) == 2
    front_lock: SectorAlarmLock = entities[0]
    back_lock: SectorAlarmLock = entities[1]

    assert front_lock.unique_id == "SERIAL_123_lock"
    assert front_lock._device_id == "SERIAL_123"
    assert front_lock.device_name == "Front Door"
    assert front_lock.device_model == "Smart Lock"
    assert front_lock._attr_code_format == r"^\d{6}$"

    assert back_lock.unique_id == "SERIAL_321_lock"
    assert back_lock._device_id == "SERIAL_321"
    assert back_lock.device_name == "Back Door"
    assert back_lock.device_model == "Smart Lock"
    assert back_lock._attr_code_format == r"^\d{6}$"

async def test_is_locked_true():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "lock"},
                "model": "Smart Lock",
                "last_updated": "",
            },
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    assert lock.is_locked is True


async def test_is_locked_false():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    assert lock.is_locked is False


async def test_is_locked_missing_device():
    coordinator = _create_mock_coordinator({})

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    assert lock.is_locked is False

async def test_is_locked_missing_status():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": None},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")
    assert lock.is_locked is False

async def test_is_locked_case_insensitive():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "LOCK"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")
    assert lock.is_locked is True

async def test_async_lock_success():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    await lock.async_lock(**{ATTR_CODE: "123456"})

    coordinator.sector_api.lock_door.assert_awaited_once_with("LOCK123", code="123456")
    coordinator.async_request_refresh.assert_awaited_once()

async def test_async_unlock_success():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    await lock.async_unlock(**{ATTR_CODE: "123456"})

    coordinator.sector_api.unlock_door.assert_awaited_once_with(
        "LOCK123", code="123456"
    )
    coordinator.async_request_refresh.assert_awaited_once()

async def test_async_lock_login_error():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    coordinator.sector_api.lock_door.side_effect = LoginError("bad login")

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    with pytest.raises(ConfigEntryAuthFailed):
        await lock.async_lock(**{ATTR_CODE: "123456"})

async def test_async_lock_authentication_error():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    coordinator.sector_api.lock_door.side_effect = AuthenticationError("bad token")

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    with pytest.raises(HomeAssistantError):
        await lock.async_lock(**{ATTR_CODE: "123456"})

async def test_async_lock_api_error():
    coordinator = _create_mock_coordinator(
        {
            "LOCK123": {
                "name": "Front Door",
                "serial_no": "SERIAL_123",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "last_updated": "",
            }
        }
    )

    coordinator.sector_api.lock_door.side_effect = ApiError("api broken")

    lock = SectorAlarmLock(coordinator, 6, "LOCK123", "Front Door", "Smart Lock")

    with pytest.raises(HomeAssistantError):
        await lock.async_lock(**{ATTR_CODE: "123456"})

def test_code_format_regex():
    coordinator = _create_mock_coordinator({})
    lock = SectorAlarmLock(coordinator, 4, "LOCK123", "Front Door", "Smart Lock")

    assert lock._attr_code_format == r"^\d{4}$"