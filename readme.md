[![Sector Alarm](https://github.com/gjohansson-ST/sector/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge&cacheSeconds=3600)](https://github.com/hacs/integration)
[![size_badge](https://img.shields.io/github/repo-size/gjohansson-ST/sector?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)
[![version_badge](https://img.shields.io/github/v/release/gjohansson-ST/sector?label=Latest%20release&style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector/releases/latest)
[![download_badge](https://img.shields.io/github/downloads/gjohansson-ST/sector/total?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector/releases/latest)
![GitHub Repo stars](https://img.shields.io/github/stars/gjohansson-ST/attribute_as_sensor?style=for-the-badge&cacheSeconds=3600)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/gjohansson-ST/attribute_as_sensor?style=for-the-badge&cacheSeconds=3600)
![GitHub License](https://img.shields.io/github/license/gjohansson-ST/attribute_as_sensor?style=for-the-badge&cacheSeconds=3600)

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Home%20Assistant-blue?style=for-the-badge&logo=homeassistant)](https://github.com/home-assistant)

[![Sponsor me](https://img.shields.io/badge/Sponsor-Me-blue?style=for-the-badge&logo=github)](https://github.com/sponsors/gjohansson-ST)
[![Discord](https://img.shields.io/discord/872446427664625664?style=for-the-badge&label=Discord&cacheSeconds=3600)](https://discord.gg/EG7cWFQMGW)

# Integratation to Sector Alarm
---
**Title:** "Sector Alarm"

**Description:** "Support for Sector Alarm integration with Homeassistant."

**Date created:** 2020-04-29

**Last update:** 2023-11-04

**Required HA version:** 2024.11.0

---

Integrates with Swedish Sector Alarm home alarm system (most likely works in all countries serviced by Sector Alarm).
Currently implements Alarm panel, Locks, Temperature and Smartplugs

**NOTE**

On alarm installation which are not wired make sure you take the binary sensor "Online" into account to ensure the alarm state is a trusted state

The entity for alarm panel will only update it's state on alarms which are online

## Configuration Options

Set once:

- Username: Your e-mail address linked to Sector Alarm account
- Password: Password used for app or Sector website
- Enable Temp sensors (Not recommended and turned off by default due to long api response time)

Options that you can change at any time:

- Code Format: Number of digits in code

## Installation

### Option 1 (preferred)

Use [HACS](https://hacs.xyz/) to install

### Option 2

Below config-folder create a new folder called`custom_components` if not already exist.

Below new `custom_components` folder create a new folder called `sector`

Upload the files/folders in `custom_components/sector` directory to the newly created folder.

Restart before proceeding

## Activate integration in HA

[![Add integrations](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=sector)

After installation go to "Integrations" page in HA, press + and search for Sector Alarm
Follow onscreen information to type username, password, code etc.
No restart needed
