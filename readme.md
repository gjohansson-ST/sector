# Integratation to Sector Alarm
---
title: "Sector Alarm"
description: "Support for Sector Alarm integration with Homeassistant."
date created: 2020-04-29
last update: 2020-06-01
---

# NOT YET COMPLETED! LOCK DOOR AND TOOGLE ALARM NOT COMPLETE

Integrates with Swedish Sector Alarm home alarm system.
Currently supporting alarm, doorlock and temperature sensors

To add Sector Alarm to your installation, add the following to your `configuration.yaml` file:

## Installation

Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder. Then updated you configuration as per above before restarting your Home Assistant.

```yaml
# Example configuration.yaml entry
sector:
  userid: !secret sector_alarm_email
  password: !secret sector_alarm_pwd
  code: !secret sector_alarm_code
```

