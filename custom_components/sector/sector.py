"""Sector API integration."""
import aiohttp

BASE_URL = "https://api.sectoralarm.net"

class Sector:
    """Class representing the Sector Alarm API."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize Sector Alarm API."""
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()

    async def authenticate(self) -> None:
        """Authenticate with Sector Alarm."""
        url = f"{BASE_URL}/auth"
        payload = {"username": self.username, "password": self.password}
        async with self.session.post(url, json=payload) as response:
            response.raise_for_status()
            self.token = await response.json()

    async def get_all_data(self) -> dict:
        """Fetch all data from Sector Alarm."""
        await self.authenticate()
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{BASE_URL}/devices"
        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def triggeralarm(self, command: str, code: str, panel_id: str) -> None:
        """Send command to trigger alarm."""
        await self.authenticate()
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"command": command, "code": code}
        url = f"{BASE_URL}/devices/{panel_id}/actions"
        async with self.session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
