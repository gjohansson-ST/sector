---
layout: page
title: "Sector Alarm"
description: "Offers support for Sector Alarm (Sweden) integration with Homeassistant."
date: 2017-11-16 08:00
sidebar: true
comments: false
sharing: true
footer: true
logo: home-assistant.png
ha_category: "Other"
---

Integrates with Swedish Sector Alarm home alarm system

To add Sector Alarm to your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: sector
    userid: <your e-mail>
    password: <your password>
```

## Installation

Create a new folder under `custom_components` called `sector`. Upload the `sensor.py` and `manifest.json` files to the newly created folder. Then updated you configuration as per above before restarting your Home Assistant.