# Integratation to Sector Alarm
---
title: "Sector Alarm"
description: "Support for Sector Alarm integration with Homeassistant."
date created: 2020-04-29
last update: 2020-06-01
---

Integrates with Swedish Sector Alarm home alarm system.
Currently supporting alarm, doorlock and temperature sensors

## Installation

Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder. Then update your configuration as per below before restarting your Home Assistant.

To add Sector Alarm to your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sector:
  userid: !secret sector_alarm_email
  password: !secret sector_alarm_pwd
  code: !secret sector_alarm_code
```
