"""Tests for the scan_interval configuration option."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sector.const import (
    CONFIG_SCAN_INTERVAL,
    CONF_PANEL_ID,
    DEFAULT_SCAN_INTERVAL,
)


_PANEL_ID = "1234"


def _create_mock_config_entry(
    options: dict | None = None,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={
            "panel_id": _PANEL_ID,
            "email": "test@test.com",
            "password": "secret",
        },
        options=options or {},
        entry_id="test_scan",
    )


class TestScanIntervalDefaults:
    """Verify DEFAULT_SCAN_INTERVAL is sane."""

    def test_default_scan_interval_value(self):
        assert DEFAULT_SCAN_INTERVAL == timedelta(seconds=30)

    def test_default_scan_interval_is_timedelta(self):
        assert isinstance(DEFAULT_SCAN_INTERVAL, timedelta)

    def test_config_scan_interval_key(self):
        assert CONFIG_SCAN_INTERVAL == "scan_interval"


class TestScanIntervalFromOptions:
    """Verify that scan_interval is read from config entry options."""

    def test_options_returns_custom_value(self):
        entry = _create_mock_config_entry(options={CONFIG_SCAN_INTERVAL: 10})
        interval = entry.options.get(CONFIG_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        assert interval == 10

    def test_options_returns_default_when_missing(self):
        entry = _create_mock_config_entry(options={})
        interval = entry.options.get(CONFIG_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        assert interval == DEFAULT_SCAN_INTERVAL

    def test_options_returns_default_when_none(self):
        entry = _create_mock_config_entry()
        interval = entry.options.get(CONFIG_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        assert interval == DEFAULT_SCAN_INTERVAL
