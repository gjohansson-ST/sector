# Sector Alarm API faker

This standalone, standard-library HTTP server implements the endpoints used by
the Sector Alarm Home Assistant integration, except for camera endpoints. It
requires a configured login user, password, and alarm panel ID, returns an
**unsigned** JWT for valid credentials, and starts with a disarmed panel, two
locked smart locks, an open back door, one smoke detector reporting low
battery, and two switched-off plugs.
The Docker image runs on Python 3.14.
Alarm, lock, and plug states and the audit log are kept in memory and reset
when the faker process restarts.

Climate sensor values are realistic Celsius/relative humidity readings. Each
sensor gets a stable randomized value during a 30-minute interval and a new
reading in the next interval. The `DEVICES` inventory defines each device and
its optional sensors. Locks, plugs, the single alarm panel, and HouseCheck
devices share the device model. Endpoint payloads are generated from that
inventory and the devices' in-memory state. A camera has climate/battery
sensors, and a keypad has temperature, humidity, and battery sensors. The
integration recognizes their `CameraPIR` and `KeyPad` types as synthetic
devices; the camera endpoint itself remains deliberately omitted.
Locks expose their battery sensor and Sector's `lock`/`unlock` status; smart
plugs expose their `On`/`Off` state.

## Build and run

From the repository root:

```sh
SECTOR_API_USER=your-user \
SECTOR_API_PASSWORD=your-password \
PANEL_ID=1234 \
TIME_ZONE=Europe/Stockholm \
LEGACY_MODE=false \
python -m sector_api_faker
```

Or build and run the Docker image:

```sh
docker build -t sector-api-faker ./sector_api_faker
docker run --name sector-api-faker -p 8080:8080 \
  -e SECTOR_API_USER=your-user \
  -e SECTOR_API_PASSWORD=your-password \
  -e PANEL_ID=1234 \
  -e TIME_ZONE=Europe/Stockholm \
  -e LEGACY_MODE=false \
  sector-api-faker
```

The faker refuses to start if any required setting is missing or empty. Login
requests must match the configured user and password. Issued JWTs include a
random token ID and expire after one hour; protected requests must present an
unmodified token issued by the current faker process. Optional environment
variables are `TIME_ZONE`, `LEGACY_MODE`, `PANEL_NAME`, `PORT`, and `LOG_LEVEL`.
Set `TIME_ZONE` to the same IANA time-zone name configured in Home Assistant; it
defaults to `Europe/Stockholm` (Central European time).
Set `LEGACY_MODE=true` to add `UseLegacyHomeScreen` to the panel capabilities
so Home Assistant uses its legacy endpoint selection. It defaults to `false`;
this setting does not alter the faker's API endpoints.

## Point Home Assistant at the faker

The integration's production API URL remains the default. To test against this
container, set `SECTOR_API_URL` in the **Home Assistant process environment**
to the faker's base URL, then restart Home Assistant. For example, on a shared
Docker network use `http://sector-api-faker:8080`; from a Home Assistant process
running on the host use `http://localhost:8080`. Make sure the containers share
a Docker network so Home Assistant can resolve `sector-api-faker`. Use `http://`
for this local development faker. Restart Home Assistant after changing the
environment variable.

Use the configured panel ID in Home Assistant, and use a six-digit code such
as `123456` for alarm and lock controls.

Run the faker's standalone HTTP tests from the repository root with:

```sh
python -m unittest sector_api_faker.tests -v
```
