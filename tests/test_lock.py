from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_CODE
from homeassistant.components.lock.const import LockState
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.client import ApiError, AuthenticationError, LoginError
from custom_components.sector.const import RUNTIME_DATA
from custom_components.sector.coordinator import DeviceRegistry
from custom_components.sector.lock import async_setup_entry, SectorAlarmLock

_PANEL_ID = "1234"
_DEVICE_COORDINATOR_NAME = "device-coordinator"


def _create_mock_coordinator(devices: dict):
    device_registry = DeviceRegistry()
    for d in devices.values():
        device_registry.register_device(d)

    coordinator = MagicMock()
    coordinator.data = {"device_registry": device_registry}
    coordinator.async_request_refresh = AsyncMock()
    coordinator.sector_api = MagicMock()
    coordinator.sector_api.lock_door = AsyncMock()
    coordinator.sector_api.unlock_door = AsyncMock()
    coordinator.name = _DEVICE_COORDINATOR_NAME
    return coordinator


def _create_mock_config_entity() -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={
            "panel_id": _PANEL_ID,
            "username": "abc",
            "password": "xyz",
        },
        entry_id="test123",
    )


def _create_device(serial: str, data: dict[str, Any]) -> dict[str, Any]:
    model: str = data["model"]
    return {
        "name": data["name"],
        "model": model,
        "serial_no": serial,
        "entities": {model: data},
    }


async def test_setup_creates_lock_entity(hass: HomeAssistant):
    # Prepare
    devices = {
        "SERIAL_123": _create_device(
            "SERIAL_123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
        "SERIAL_321": _create_device(
            "SERIAL_321",
            {
                "name": "Back Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 4,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
        "OTHER": _create_device(
            "OTHER",
            {
                "name": "Back Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Dumb Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }

    coordinator = _create_mock_coordinator(devices)
    entry = _create_mock_config_entity()
    entry.runtime_data = {RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator]}

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
    assert front_lock._serial_no == "SERIAL_123"
    assert front_lock._device_name == "Front Door"
    assert front_lock._device_model == "Smart Lock"
    assert front_lock._attr_code_format == r"^\d{6}$"

    assert back_lock.unique_id == "SERIAL_321_lock"
    assert back_lock._serial_no == "SERIAL_321"
    assert back_lock._device_name == "Back Door"
    assert back_lock._device_model == "Smart Lock"
    assert back_lock._attr_code_format == r"^\d{4}$"


async def test_code_format_regex_when_not_defined():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock._attr_code_format == r"^\d{0}$"


async def test_is_locked_true():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock.is_locked is True


async def test_is_locked_false():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock.is_locked is False


async def test_is_locked_missing_device():
    # Prepare
    coordinator = _create_mock_coordinator({})

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock.is_locked is False


async def test_is_locked_missing_status():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": None},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock.is_locked is False


async def test_is_locked_case_insensitive():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "LOCK"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    # Act & Assert
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    assert lock.is_locked is True


async def test_async_lock_success():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act
    await lock.async_lock(**{ATTR_CODE: "123456"})

    # Assert
    coordinator.sector_api.lock_door.assert_awaited_once_with("LOCK123", code="123456")
    coordinator.async_request_refresh.assert_awaited_once()


async def test_async_unlock_success():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act
    await lock.async_unlock(**{ATTR_CODE: "123456"})

    # Assert
    coordinator.sector_api.unlock_door.assert_awaited_once_with(
        "LOCK123", code="123456"
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_async_locking_pending_state_when_calling_lock():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act
    await lock.async_lock(**{ATTR_CODE: "123456"})

    # Assert
    assert lock._pending_state == LockState.LOCKING
    assert lock.is_locking


async def test_async_unlocking_pending_state_when_calling_unlock():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act
    await lock.async_unlock(**{ATTR_CODE: "123456"})

    # Assert
    assert lock._pending_state == LockState.UNLOCKING
    assert lock.is_unlocking


async def test_async_resets_pending_state_when_calling_handle_coordinator_update():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()
    lock._pending_state = LockState.LOCKING

    # Act
    lock._handle_coordinator_update()

    # Assert
    assert lock._pending_state is None
    assert not lock.is_locking
    assert not lock.is_unlocking


async def test_async_lock_login_error():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.lock_door.side_effect = LoginError("bad login")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(ConfigEntryAuthFailed):
        await lock.async_lock(**{ATTR_CODE: "123456"})


async def test_async_lock_authentication_error():
    # Perpare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.lock_door.side_effect = AuthenticationError("bad token")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_lock(**{ATTR_CODE: "123456"})


async def test_async_lock_api_error():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.lock_door.side_effect = ApiError("api broken")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_lock(**{ATTR_CODE: "123456"})


async def test_async_unlock_login_error():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "lock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.unlock_door.side_effect = LoginError("bad login")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(ConfigEntryAuthFailed):
        await lock.async_unlock(**{ATTR_CODE: "123456"})


async def test_async_unlock_authentication_error():
    # Perpare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.unlock_door.side_effect = AuthenticationError("bad token")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_unlock(**{ATTR_CODE: "123456"})


async def test_async_unlock_api_error():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.unlock_door.side_effect = ApiError("api broken")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_unlock(**{ATTR_CODE: "123456"})


async def test_async_lock_error_should_reset_pending_state():
    # Perpare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.lock_door.side_effect = Exception("Some Exception")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_lock(**{ATTR_CODE: "123456"})
    assert lock._pending_state is None
    assert not lock.is_locking
    assert not lock.is_unlocking


async def test_async_unlock_error_should_reset_pending_state():
    # Prepare
    devices = {
        "LOCK123": _create_device(
            "LOCK123",
            {
                "name": "Front Door",
                "sensors": {"lock_status": "unlock"},
                "panel_code_length": 6,
                "model": "Smart Lock",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    coordinator.sector_api.unlock_door.side_effect = Exception("Some Exception")
    lock = SectorAlarmLock(
        coordinator, "LOCK123", "Front Door", "Smart Lock", "Smart Lock"
    )
    lock.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await lock.async_unlock(**{ATTR_CODE: "123456"})
    assert lock._pending_state is None
    assert not lock.is_locking
    assert not lock.is_unlocking
