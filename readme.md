[![Sector Alarm](https://github.com/gjohansson-ST/sector/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![download_badge](https://img.shields.io/github/downloads/gjohansson-ST/sector/total?style=for-the-badge)](https://github.com/gjohansson-ST/sector)
[![size_badge](https://img.shields.io/github/repo-size/gjohansson-ST/sector?style=for-the-badge)](https://github.com/gjohansson-ST/sector)
[![issues_badge](https://img.shields.io/github/issues/gjohansson-ST/sector?style=for-the-badge)](https://github.com/gjohansson-ST/sector)


# Integratation to Sector Alarm
---
title: "Sector Alarm"

description: "Support for Sector Alarm integration with Homeassistant."

date created: 2020-04-29

last update: 2020-06-04

---

Integrates with Swedish Sector Alarm home alarm system.
Currently supporting alarm, doorlock and temperature sensors

## Installation

Option1:
Use HACS to install

Option2:
Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder. Then update your configuration as per below before restarting your Home Assistant.

To start Sector Alarm in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sector:
  userid: !secret sector_alarm_email
  password: !secret sector_alarm_pwd
  code: !secret sector_alarm_code
```
