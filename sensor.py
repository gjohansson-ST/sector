import logging
import json
import requests
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONTENT_TYPE_JSON
from aiohttp.hdrs import CONTENT_TYPE, AUTHORIZATION

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sector'

ATTR_NAME = 'name'
DEFAULT_NAME = 'Sector'

SCAN_INTERVAL = timedelta(minutes=5)
#SCAN_INTERVAL = timedelta(seconds=20)

CONF_USERID = 'userid'
CONF_PASSWORD = 'password'

DEPENDENCIES = ['http']

# Kolla scripts.py
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERID): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

AUTH_TOKEN = ""


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set Sector Alarm sensors"""

    message_headers = {
        CONTENT_TYPE: CONTENT_TYPE_JSON,
        "API-Version":"5"
    }

    data = {
        'UserId': config[CONF_USERID],
        "Password": config[CONF_PASSWORD]
    }
    response = requests.post(
        "https://mypagesapi.sectoralarm.net/api/Login/Login",  headers=message_headers, json=data, timeout=30)
    if response.status_code != 200:
            _LOGGER.exception("Failed to send Login: %d", response.status_code)
    
    global AUTH_TOKEN
    AUTH_TOKEN = response.json()['AuthorizationToken']
    _LOGGER.info(AUTH_TOKEN)
    

    message_headers = {
        CONTENT_TYPE: CONTENT_TYPE_JSON,
        AUTHORIZATION: AUTH_TOKEN,
        "API-Version":"5"
    }

    response = requests.get(
        "https://mypagesapi.sectoralarm.net/api/panel/getFullSystem", 
        headers=message_headers, json=data, timeout=30)
    if response.status_code != 200:
            _LOGGER.exception("Failed to get system: %d", response.status_code)


    devices = []    
    devices.append(SectorAlarmSensor(config,"", "Alarm", response.json()['Panel']['PanelDisplayName'], response.json()['Panel']['PanelId'], ""))

    for temp in response.json()['Temperatures']:
        devices.append(SectorAlarmSensor(config, "", "Temperature", temp['Label'], response.json()['Panel']['PanelId'], temp['SerialNo']))

    add_devices(devices, True)

    # Return boolean to indicate that initialization was successfully.
    return True


class SectorAlarmSensor(Entity):
    """Implementation of Sector Alarm sensor"""

    def __init__(self, config, client, sensor_type, name, panel_id, id):
        self.config = config
        self.client = client
        self.sensor_type = sensor_type
        self._name = name
        self._state = 0
        self.panel_id = panel_id
        self.id = id
        if self.sensor_type == "Temperature":
            self._unit_of_measurement = "°C"
        else:
            self._unit_of_measurement = ""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        icon = None
        if self.sensor_type == "Temperature":
            icon = 'mdi:thermometer'
        else:
            icon = 'mdi:security-home'
        return icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            'panel_id': self.panel_id,
            'id': self.id
        }
        return attrs


    def update(self):
        message_headers = {
            CONTENT_TYPE: CONTENT_TYPE_JSON,
            "API-Version":"5"
        }

        data = {
            'UserId': self.config[CONF_USERID],
            "Password": self.config[CONF_PASSWORD]
        }
        response = requests.post(
            "https://mypagesapi.sectoralarm.net/api/Login/Login",  headers=message_headers, json=data, timeout=30)
        if response.status_code != 200:
            _LOGGER.exception("Failed to send Login: %d", response.status_code)

        global AUTH_TOKEN
        AUTH_TOKEN = response.json()['AuthorizationToken']
        _LOGGER.info(AUTH_TOKEN)

        message_headers = {
            CONTENT_TYPE: CONTENT_TYPE_JSON,
            AUTHORIZATION: AUTH_TOKEN,
            "API-Version":"5"
        }

        _LOGGER.info("Updating alarm sensors: {}:{}:{}".format(self.sensor_type, self.panel_id, self.id));
        if self.sensor_type == "Temperature":

            response = requests.get(
                "https://mypagesapi.sectoralarm.net/api/panel/GetTemperatures?panelId={}".format(self.panel_id), headers=message_headers, timeout=30)
            if response.status_code != 200:
                _LOGGER.exception("Faled to get system: %d", response.status_code)
            else:
                for temp in response.json():
                    _LOGGER.info("checking {}={}->".format(temp["SerialNo"], self.id,temp["Temprature"] ))
                    if(temp["SerialNo"] == self.id):
                        self._state = temp["Temprature"]
        else:
            response = requests.get(
                "https://mypagesapi.sectoralarm.net/api/panel/GetAlarmSystemStatus?panelId={}".format(self.panel_id), headers=message_headers, timeout=30)
            if response.status_code != 200:
                _LOGGER.exception("Faled to get system: %d", response.status_code)
            else:
                self._state = response.json()["ArmedStatus"]
