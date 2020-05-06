# Integratation to Sector Alarm
---
layout: page
title: "Sector Alarm"
description: "Support for Sector Alarm integration with Homeassistant."
date: 2020-04-29
---

#NOT YET COMPLETED!

Integrates with Swedish Sector Alarm home alarm system

To add Sector Alarm to your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sector:
  userid: !secret sector_alarm_email
  password: !secret sector_alarm_pwd
  code: !secret sector_alarm_code
```

## Installation

Create a new folder under `custom_components` called `sector`. Upload the `***.py`-files to the newly created folder. Then updated you configuration as per above before restarting your Home Assistant.
