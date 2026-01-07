[![Sector Alarm](https://github.com/OathMeadow/sector-maintained/blob/master/logos/logo.png)](https://www.sectoralarm.se/)

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge&cacheSeconds=3600)](https://github.com/hacs/integration)
[![Repo size](https://img.shields.io/github/repo-size/OathMeadow/sector-maintained?style=for-the-badge&cacheSeconds=3600)](https://github.com/OathMeadow/sector-maintained)
[![Latest release](https://img.shields.io/github/v/release/OathMeadow/sector-maintained?label=Latest%20release&style=for-the-badge&cacheSeconds=3600)](https://github.com/OathMeadow/sector-maintained/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/OathMeadow/sector-maintained/total?style=for-the-badge&cacheSeconds=3600)](https://github.com/OathMeadow/sector-maintained/releases/latest)
![Stars](https://img.shields.io/github/stars/OathMeadow/sector-maintained?style=for-the-badge&cacheSeconds=3600)
![Issues or Pull Requests](https://img.shields.io/github/issues/OathMeadow/sector-maintained?style=for-the-badge&cacheSeconds=3600)
![License](https://img.shields.io/github/license/OathMeadow/sector-maintained?label=license&style=for-the-badge&cacheSeconds=3600)

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Home%20Assistant-blue?style=for-the-badge&logo=homeassistant)](https://github.com/home-assistant)


# Sector Alarm integration for Home Assistant

> ⚠️ Work in progress: no official release yet.
Bug fixes and updates are applied continuously on the `master` branch.
Please open an issue if you encounter any problems. 🙇

This integration connects Home Assistant with the Sector Alarm system allowing monitoring and control directly from Home Assistant (officially supported in Sweden and expected to work in other regions).

### About this fork ###

This integration is based on the work from
[`gjohansson-ST/sector`](https://github.com/gjohansson-ST/sector).

At the time of forking, the upstream repository had multiple reported issues in version 0.5.0
and no active maintenance for several months.
Help was proposed but did not recieve any response.

This fork aims to:
- Fix known issues in the current release
- Keep compatibility with recent Home Assistant versions
- Provide active maintenance going forward

If upstream maintenance resumes, contributions back to the original project are welcome.

## Supported features ##
- ✅ Alarm control
- ✅ Door lock
- ✅ Smart Plugs
- ✅ Temperature sensors
- ✅ Humidity sensors
- ✅ Various binary sensors

## Important notes ##

On alarm installation which are not wired make sure you take the binary sensor `Online` into account to ensure the alarm state is a trusted state. The entity for alarm panel will only update it's state on alarms which are online.

## Installation ##

**Required Home Assistant version:** 2025.12.0

> ⚠️ You must uninstall and remove existing integration from [`gjohansson-ST/sector`](https://github.com/gjohansson-ST/sector) before installation can begin.

### Option 1: HACS (recommended)

Click the button below to add the repository to HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=OathMeadow&repository=sector-maintained&category=integration)

After installation:

1. Restart Home Assistant
2. Go to **Settings → Integrations**
3. Click **Add Integration**
4. Search for **Sector Alarm**
5. Follow the on-screen setup instructions

### Option 2: Manual ###

1. Create a `custom_components` directory if it does not exist
2. Inside it, create a folder named `sector`
3. Copy the contents of this repository into `custom_components/sector`
4. Restart Home Assistant

## Configuration options ##

### Set once during setup ###
- **Username –** E-mail address associated with your Sector Alarm account
- **Password -** Password used for the Sector Alarm app or website

### Adjustable after setup ###
Options that you can change at any time:

- **Code format –** Number of digits used for the alarm control panel
