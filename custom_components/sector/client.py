"""Client module for interacting with Sector Alarm API."""
from __future__ import annotations

import requests
import logging

from .const import LOGGER

LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""


class SectorAlarmAPI:
    """Class to interact with the Sector Alarm API."""

    BASE_URL = "https://mypagesapi.sectoralarm.net/api"

    def __init__(self, email, password, panel_id, panel_code):
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.panel_id = panel_id
        self.panel_code = panel_code
        self.access_token = None
        self.headers = {}

    def login(self):
        """Authenticate with the API and obtain an access token."""
        login_url = f"{self.BASE_URL}/Login/LoginUser"
        payload = {
            "userId": self.email,
            "password": self.password,
        }
        response = requests.post(login_url, json=payload)
        if response.status_code != 200:
            LOGGER.error(f"Login failed with status code {response.status_code}")
            raise AuthenticationError("Invalid credentials")
        data = response.json()
        self.access_token = data.get("AuthorizationToken")
        if not self.access_token:
            LOGGER.error("Login failed: No authorization token received")
            raise AuthenticationError("Invalid credentials")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def retrieve_all_data(self):
        """Retrieve all relevant data from the API."""
        data = {}

        # Get panel status
        panel_status_url = f"{self.BASE_URL}/Panel/GetPanelStatus?panelId={self.panel_id}"
        response = requests.get(panel_status_url, headers=self.headers)
        if response.status_code == 200:
            data["Panel Status"] = response.json()
        else:
            LOGGER.error(f"Failed to retrieve panel status: {response.status_code}")

        # Get locks
        locks_url = f"{self.BASE_URL}/Panel/GetLockStatus?panelId={self.panel_id}"
        response = requests.get(locks_url, headers=self.headers)
        if response.status_code == 200:
            data["Lock Status"] = response.json()
        else:
            LOGGER.error(f"Failed to retrieve lock status: {response.status_code}")

        # Get temperatures
        temperatures_url = f"{self.BASE_URL}/Panel/GetTemperatures?panelId={self.panel_id}"
        response = requests.get(temperatures_url, headers=self.headers)
        if response.status_code == 200:
            data["Temperatures"] = response.json()
        else:
            LOGGER.error(f"Failed to retrieve temperatures: {response.status_code}")

        # Get panel logs
        logs_url = f"{self.BASE_URL}/Panel/GetLogs?panelId={self.panel_id}"
        response = requests.get(logs_url, headers=self.headers)
        if response.status_code == 200:
            data["Logs"] = response.json()
        else:
            LOGGER.error(f"Failed to retrieve logs: {response.status_code}")

        # Additional data retrieval can be added here

        return data

    def arm_system(self, mode):
        """Arm the alarm system."""
        arm_url = f"{self.BASE_URL}/Panel/ArmPanel"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "ArmType": mode,  # 'full' or 'partial'
        }
        response = requests.post(arm_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug("System armed successfully")
            return True
        else:
            LOGGER.error(f"Failed to arm system: {response.status_code}")
            return False

    def disarm_system(self):
        """Disarm the alarm system."""
        disarm_url = f"{self.BASE_URL}/Panel/DisarmPanel"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
        }
        response = requests.post(disarm_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug("System disarmed successfully")
            return True
        else:
            LOGGER.error(f"Failed to disarm system: {response.status_code}")
            return False

    def lock_door(self, serial_no):
        """Lock a specific door."""
        lock_url = f"{self.BASE_URL}/Panel/LockDoor"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        response = requests.post(lock_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug(f"Door {serial_no} locked successfully")
            return True
        else:
            LOGGER.error(f"Failed to lock door {serial_no}: {response.status_code}")
            return False

    def unlock_door(self, serial_no):
        """Unlock a specific door."""
        unlock_url = f"{self.BASE_URL}/Panel/UnlockDoor"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        response = requests.post(unlock_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug(f"Door {serial_no} unlocked successfully")
            return True
        else:
            LOGGER.error(f"Failed to unlock door {serial_no}: {response.status_code}")
            return False

    def turn_on_smartplug(self, plug_id):
        """Turn on a smart plug."""
        turn_on_url = f"{self.BASE_URL}/Panel/TurnOnSmartplug"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "Id": plug_id,
        }
        response = requests.post(turn_on_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug(f"Smartplug {plug_id} turned on successfully")
            return True
        else:
            LOGGER.error(f"Failed to turn on smartplug {plug_id}: {response.status_code}")
            return False

    def turn_off_smartplug(self, plug_id):
        """Turn off a smart plug."""
        turn_off_url = f"{self.BASE_URL}/Panel/TurnOffSmartplug"
        payload = {
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "Id": plug_id,
        }
        response = requests.post(turn_off_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug(f"Smartplug {plug_id} turned off successfully")
            return True
        else:
            LOGGER.error(f"Failed to turn off smartplug {plug_id}: {response.status_code}")
            return False

    def logout(self):
        """Logout from the API."""
        logout_url = f"{self.BASE_URL}/Login/Logout"
        response = requests.post(logout_url, headers=self.headers)
        if response.status_code == 200:
            LOGGER.debug("Logged out successfully")
            return True
        else:
            LOGGER.error(f"Failed to logout: {response.status_code}")
            return False
