from custom_components.sector import DataEndpointType


async def test_device_endpoints():

    assert DataEndpointType.PANEL_STATUS.is_device
    assert DataEndpointType.SMART_PLUG_STATUS.is_device
    assert DataEndpointType.LOCK_STATUS.is_device
    assert DataEndpointType.DOOR_AND_WINDOW.is_device
    assert DataEndpointType.SMOKE_DETECTOR.is_device
    assert DataEndpointType.LEAKAGE_DETECTOR.is_device
    assert DataEndpointType.CAMERAS.is_device


async def test_non_device_endpoints():

    assert not DataEndpointType.HUMIDITY.is_device
    assert not DataEndpointType.TEMPERATURE.is_device
    assert not DataEndpointType.TEMPERATURE_LEGACY.is_device


async def test_housecheck_endpoints():

    assert DataEndpointType.DOOR_AND_WINDOW.is_house_check_endpoint
    assert DataEndpointType.SMOKE_DETECTOR.is_house_check_endpoint
    assert DataEndpointType.LEAKAGE_DETECTOR.is_house_check_endpoint
    assert DataEndpointType.HUMIDITY.is_house_check_endpoint
    assert DataEndpointType.TEMPERATURE.is_house_check_endpoint


async def test_non_housecheck_endpoints():

    assert not DataEndpointType.PANEL_STATUS.is_house_check_endpoint
    assert not DataEndpointType.SMART_PLUG_STATUS.is_house_check_endpoint
    assert not DataEndpointType.LOCK_STATUS.is_house_check_endpoint
    assert not DataEndpointType.TEMPERATURE_LEGACY.is_house_check_endpoint
