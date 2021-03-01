[![Sector Alarm](https://github.com/gjohansson-ST/sector/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge&cacheSeconds=3600)](https://github.com/custom-components/hacs)
[![size_badge](https://img.shields.io/github/repo-size/gjohansson-ST/sector?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)
[![version_badge](https://img.shields.io/github/v/release/gjohansson-ST/sector?label=Latest%20release&style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector/releases/latest)
[![download_badge](https://img.shields.io/github/downloads/gjohansson-ST/sector/total?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector/releases/latest)


# Integratation to Sector Alarm
---
**Title:** "Sector Alarm"

**Description:** "Support for Sector Alarm integration with Homeassistant."

**Date created:** 2020-04-29

**Last update:** 2021-03-01

---

Integrates with Swedish Sector Alarm home alarm system (most likely works in all countries serviced by Sector Alarm).
Currently supporting alarm, door lock and temperature sensors

**From version v.0.3.0 this integration only supports config flow using integration page, any yaml in config.yaml should be removed**

## Installation

### Option 1 (preferred)

Use [HACS](https://hacs.xyz/) to install

### Option 2

Below config-folder create a new folder called`custom_components` if not already exist.

Below new `custom_components` folder create a new folder called `sector`

Upload the files/folders in `custom_components/sector` directory to the newly created folder.

Restart before proceeding

## Activate integration in HA

After installation go to "Integrations" page in HA, press + and search for Sector Alarm
Follow onscreen information to type username, password, code etc.
No restart needed

### Options

After activating the integration there is an option to adjust the frequence off polling.
Any value below 60 seconds will most likely get your account locked so take care setting value lower!

### Option to use yaml to configure the integration has from version 0.3 been depreciated!
