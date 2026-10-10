# Commons Radio for Home Assistant

This custom integration lets Home Assistant users browse and play Commons
Radio stations. It also creates an on-air sensor for each favorite station.

This repository uses the MIT license.

## Status

This is phase 1. It supports station browsing, playback, favorites,
collections, and schedule sensors. It does not control a Commons Radio
hardware radio.

The Commons Radio API is not deployed yet. You need an API key with the
`catalog:read` and `library:read` scopes when the API becomes available.

## Install with HACS

1. Open HACS in Home Assistant.
2. Open the custom repositories menu.
3. Add `https://github.com/simonpeters/commons-radio-home-assistant`.
4. Select **Integration** as the category.
5. Install **Commons Radio**.
6. Restart Home Assistant.
7. Open **Settings > Devices & services**.
8. Select **Add integration**.
9. Search for **Commons Radio**.
10. Enter your Commons Radio API key.

The integration checks the key with the Favorites endpoint. It reports an
invalid key, a missing scope, or a connection error.

## Use the integration

Open the media browser and select **Commons Radio**. You can browse:

- Favorites
- My collections
- Popular stations

Select a station to play its stream on any media player that Home Assistant
controls.

The integration polls favorites and schedules once per minute. It keeps
station details for one hour to reduce API requests. Each favorite station
gets an **On air** sensor. The state is the current show title. The state is
`unknown` when the API has no current show. The next show is in the sensor
attributes.

## Icon

The integration uses the Commons Radio app icon from
`custom_components/commons_radio/brand/`.

## Development

The reusable async client is in `commonsradio/`. The integration uses a
vendored copy because `commonsradio` version 0.1.0 is not on PyPI yet. A test
checks that both copies stay equal.

Create the environment and run the checks:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --python 3.13
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run pytest
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff check .
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff format --check .
```

Tests use mocked HTTP. They do not call the live API.

### Test in a local Home Assistant

You need Docker. On macOS, start a Docker engine first, for example with
`colima start`.

1. Start Home Assistant:

   ```sh
   docker compose up -d
   ```

2. Open http://localhost:8123 and make a local account. The first start
   takes approximately one minute.
3. Make an API key on https://www.commonsradio.eu in your profile, under
   "API keys". Give it the scopes `catalog:read` and `library:read`.
4. Go to **Settings > Devices & services > Add integration**, select
   **Commons Radio**, and enter the key.
5. Open **Media > Commons Radio**. Select a station, and select
   **This browser** as the player. The station plays in your browser.
6. The "On air" sensors for your favorite stations are under
   **Settings > Devices & services > Commons Radio**.

After a change to the code, restart Home Assistant:

```sh
docker compose restart
```

Read the integration log:

```sh
docker compose logs -f homeassistant | grep commons_radio
```

Docker on macOS cannot find speakers on your network (mDNS). To test with
real speakers or through HACS, use Home Assistant OS in a virtual machine or
on a real device.
