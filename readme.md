[![Sector Alarm](https://github.com/gjohansson-ST/sector/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge&cacheSeconds=3600)](https://github.com/custom-components/hacs)
[![size_badge](https://img.shields.io/github/repo-size/gjohansson-ST/sector?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)
[![version_badge](https://img.shields.io/github/v/release/gjohansson-ST/sector?label=Latest%20release&style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)


# Integratation to Sector Alarm
---
**Title:** "Sector Alarm"

**Description:** "Support for Sector Alarm integration with Homeassistant."

**Date created:** 2020-04-29

**Last update:** 2020-11-07

---

Integrates with Swedish Sector Alarm home alarm system (most likely works in all countries serviced by Sector Alarm).
Currently supporting alarm, door lock and temperature sensors

**From version v.0.2.0 this integration supports config_flow, see details below for installation and activation details!**

## Installation

### Option 1

Use [HACS](https://hacs.xyz/) to install

### Option 2

Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder.
Restart before proceeding


## Activate integration in HA

### Option 1

After installation go to "Integrations" page in HA, press + and search for Sector Alarm
Follow onscreen information to type username, password, code etc.
No restart needed

### Option 2

To start Sector Alarm in your installation, add the following to your `configuration.yaml` file:

```yaml
# Configuration.yaml entry
sector:
  userid: !secret sector_alarm_email   #email registered with Sector Alarm
  password: !secret sector_alarm_pwd   #password registered with Sector Alarm
  code: !secret sector_alarm_code      #Alarm code neccessary to open/close lock and arm/disarm alarmpanel
  temp: true                           #true/false to activate temperature sensors, default is true (if exist in SA system)
  lock: true                           #true/false to activate lock, default is true (if exist in SA system)
```

```yaml
# Example configuration.yaml entry
sector:
  userid: email@gmail.com
  password: VerySecretPassword
  code: "123456"
  temp: true
  lock: true
```
Dont forget to restart after changing your config file
