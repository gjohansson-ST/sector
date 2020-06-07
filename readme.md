[![Sector Alarm](https://github.com/gjohansson-ST/sector/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge&cacheSeconds=3600)](https://github.com/custom-components/hacs)
[![size_badge](https://img.shields.io/github/repo-size/gjohansson-ST/sector?style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)
[![version_badge](https://img.shields.io/github/v/release/gjohansson-ST/sector?sort=semver&style=for-the-badge&cacheSeconds=3600)](https://github.com/gjohansson-ST/sector)


# Integratation to Sector Alarm
---
**Title:** "Sector Alarm"

**Description:** "Support for Sector Alarm integration with Homeassistant."

**Date created:** 2020-04-29

**Last update:** 2020-06-06

---

Integrates with Swedish Sector Alarm home alarm system (most likely works in all countries serviced by Sector Alarm).
Currently supporting alarm, doorlock and temperature sensors

## Installation

Option1:
Use [HACS](https://hacs.xyz/) to install

Option2:
Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder. Then update your configuration as per below before restarting your Home Assistant.

##Activate integration in HA

To start Sector Alarm in your installation, add the following to your `configuration.yaml` file:

```yaml
# Configuration.yaml entry
sector:
  userid: !secret sector_alarm_email
  password: !secret sector_alarm_pwd
  code: !secret sector_alarm_code
```

```yaml
# Example configuration.yaml entry
sector:
  userid: email@gmail.com
  password: VerySecretPassword
  code: "123456"
```
