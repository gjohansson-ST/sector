"""Sector Alarm API endpoints."""

API_URL = "https://mypagesapi.sectoralarm.net"


def get_data_endpoints(panel_id):
    """Return a dictionary of data retrieval endpoints."""
    endpoints = {
        # Housecheck endpoints
        "Humidity": ("GET", f"{API_URL}/api/housecheck/panels/{panel_id}/humidity"),
        "Doors and Windows": ("POST", f"{API_URL}/api/v2/housecheck/doorsandwindows"),
        "Leakage Detectors": ("POST", f"{API_URL}/api/v2/housecheck/leakagedetectors"),
        "Smoke Detectors": ("POST", f"{API_URL}/api/v2/housecheck/smokedetectors"),
        "Cameras": ("GET", f"{API_URL}/api/v2/housecheck/cameras/{panel_id}"),
        "Persons": ("GET", f"{API_URL}/api/persons/panels/{panel_id}"),
        "Temperatures": ("POST", f"{API_URL}/api/v2/housecheck/temperatures"),
        # Panel endpoints
        "Panel Status": (
            "GET",
            f"{API_URL}/api/panel/GetPanelStatus?panelId={panel_id}",
        ),
        "Smartplug Status": (
            "GET",
            f"{API_URL}/api/panel/GetSmartplugStatus?panelId={panel_id}",
        ),
        "Lock Status": ("GET", f"{API_URL}/api/panel/GetLockStatus?panelId={panel_id}"),
        "Logs": ("GET", f"{API_URL}/api/panel/GetLogs?panelId={panel_id}"),
    }
    return endpoints


def get_action_endpoints():
    """Return a dictionary of action endpoints."""
    endpoints = {
        # Lock/Unlock endpoints
        "Unlock": ("POST", f"{API_URL}/api/Panel/Unlock"),
        "Lock": ("POST", f"{API_URL}/api/Panel/Lock"),
        # Arm/Disarm endpoints
        "Arm": ("POST", f"{API_URL}/api/Panel/Arm"),
        "PartialArm": ("POST", f"{API_URL}/api/Panel/PartialArm"),
        "Disarm": ("POST", f"{API_URL}/api/Panel/Disarm"),
        # Smartplug endpoints
        "TurnOnSmartplug": ("POST", f"{API_URL}/api/Panel/TurnOnSmartplug"),
        "TurnOffSmartplug": ("POST", f"{API_URL}/api/Panel/TurnOffSmartplug"),
    }
    return endpoints
