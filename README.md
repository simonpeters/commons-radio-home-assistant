# Commons Radio for Home Assistant

This custom integration lets Home Assistant users browse and play Commons
Radio stations on their speakers, and use them in automations. It can also
show what is on air on your favorite stations.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=simonpeters&repository=commons-radio-home-assistant&category=integration)

This repository uses the MIT license.

## Status

It supports station browsing, playback of stations, collections and
favorites, the `commons_radio.play` action, blueprints, and on-air sensors.
It does not control a Commons Radio hardware radio yet.

You need a Commons Radio API key with the `catalog:read` and `library:read`
scopes. Make one on https://www.commonsradio.eu in your profile, under
"API keys".

## Install with HACS

You need [HACS](https://hacs.xyz) in your Home Assistant.

1. Select the **Open in HACS** button at the top of this page. Or open HACS,
   open the custom repositories menu, add
   `https://github.com/simonpeters/commons-radio-home-assistant`, and select
   **Integration** as the category.
2. Download **Commons Radio**.
3. Restart Home Assistant.
4. Open **Settings > Devices & services**.
5. Select **Add integration**.
6. Search for **Commons Radio**.
7. Enter your Commons Radio API key.

The integration checks the key with the Favorites endpoint. It reports an
invalid key, a missing scope, or a connection error.

## Use the integration

Open the media browser and select **Commons Radio**. You can browse:

- Favorites
- My collections
- Popular stations

Select a station to play its stream on any media player that Home Assistant
controls. You can also play **Favorites** or a collection. Commons Radio picks
a random station when playback starts.

Each favorite station gets an **On air** sensor. These sensors are off by
default. A disabled sensor costs no requests. The integration makes one shared
Favorites check per hour while it is loaded. New favorites get a sensor within
one hour. To enable a sensor, open **Settings > Devices & services > Entities**.
Select the sensor, open its settings, and enable it. Enabled sensors update
once per minute. Only enabled sensors request schedules. The integration keeps
station details for one hour. The sensor state is the current show title. The
state is `unknown` when the API has no current show. The next show is in the
sensor attributes.

The sensors belong to the **Commons Radio** service device. Its model is
**On-air service**. This model separates it from the **Commons Radio** update
device that HACS creates for the downloaded repository.

## Play from an automation

The `commons_radio.play` action has a media picker:

1. Add an action.
2. Search for **Commons Radio: Play**. You can also select your speaker under
   **By target** first.
3. Select one or more speakers as the target.
4. In **Media**, select **Commons Radio**, then select **Favorites**, a
   collection, or a station.

The **Media** field is the first field in the action editor. For YAML and voice
scripts, you can also set `station`, `collection`, or `favorites: true`. Set
exactly one of these four sources: `media`, `station`, `collection`, or
`favorites`.

This example plays a random station from the Morning collection at 09:00:

```yaml
alias: Morning radio
triggers:
  - trigger: time
    at: "09:00:00"
actions:
  - action: commons_radio.play
    target:
      entity_id: media_player.kitchen
    data:
      collection: Morning
mode: single
```

The station field accepts a station ID, slug, or name:

```yaml
action: commons_radio.play
target:
  entity_id:
    - media_player.kitchen
    - media_player.living_room
data:
  station: nts-radio
```

To use voice control, create a script with the `commons_radio.play` action.
Expose the script to Assist. You can then ask Assist to run the script.

You can also use Home Assistant's standard **Play media** action:

Use the media browser picker in the automation editor:

1. Create an automation and add a time trigger.
2. Set the time to **09:00:00**.
3. Add the **Play media** action.
4. Select the kitchen media player.
5. Select **Choose media**, then **Commons Radio**.
6. Select **Favorites** or a collection.

## Blueprints

Import a blueprint, select your speakers and source, and save it.

### Wake up with Commons Radio

[![Import the wake-up blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fsimonpeters%2Fcommons-radio-home-assistant%2Fmain%2Fblueprints%2Fautomation%2Fcommons_radio%2Fwake_up.yaml)

### Radio when someone comes home

[![Import the come-home blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fsimonpeters%2Fcommons-radio-home-assistant%2Fmain%2Fblueprints%2Fautomation%2Fcommons_radio%2Fcome_home.yaml)

### Stop the radio when everyone leaves

[![Import the everyone-leaves blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fsimonpeters%2Fcommons-radio-home-assistant%2Fmain%2Fblueprints%2Fautomation%2Fcommons_radio%2Feveryone_leaves.yaml)

### Fall asleep to Commons Radio

[![Import the fall-asleep blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fsimonpeters%2Fcommons-radio-home-assistant%2Fmain%2Fblueprints%2Fscript%2Fcommons_radio%2Ffall_asleep.yaml)

## Dashboard

This dashboard card has buttons for two collections, a random favorite, and
stop. Replace the speaker and collection names with your values.

```yaml
type: grid
columns: 2
square: false
cards:
  - type: button
    name: Morning
    icon: mdi:weather-sunset-up
    tap_action:
      action: perform-action
      perform_action: commons_radio.play
      target:
        entity_id: media_player.kitchen
      data:
        collection: Morning
  - type: button
    name: Evening
    icon: mdi:weather-sunset-down
    tap_action:
      action: perform-action
      perform_action: commons_radio.play
      target:
        entity_id: media_player.kitchen
      data:
        collection: Evening
  - type: button
    name: Random favorite
    icon: mdi:shuffle-variant
    tap_action:
      action: perform-action
      perform_action: commons_radio.play
      target:
        entity_id: media_player.kitchen
      data:
        favorites: true
  - type: button
    name: Stop
    icon: mdi:stop
    tap_action:
      action: perform-action
      perform_action: media_player.media_stop
      target:
        entity_id: media_player.kitchen
```

## Other tools

The public API also works with Node-RED, n8n and your own scripts. See
[the public API guide](docs/public-api.md).

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

### Test the install through HACS

The local Home Assistant above loads the integration from this folder. To
test the install like a real user, use the clean instance on port 8124:

1. Start it:

   ```sh
   docker compose --profile clean up -d homeassistant-clean
   ```

2. Open http://localhost:8124 and make a local account.
3. Install HACS in the container. Read the script first on
   https://hacs.xyz/docs/use/download/download/, then run:

   ```sh
   docker exec -it commons-radio-ha-clean bash -c "wget -O - https://get.hacs.xyz | bash -"
   docker compose restart homeassistant-clean
   ```

4. In Home Assistant, add the **HACS** integration and sign in to GitHub
   when it asks.
5. On https://my.home-assistant.io, set your Home Assistant URL to
   `http://localhost:8124`. The "Open in HACS" button then opens this
   instance.
6. Select the "Open in HACS" button at the top of this page, and follow the
   install steps.

Docker on macOS cannot find speakers on your network (mDNS). To test with
real speakers or through HACS, use Home Assistant OS in a virtual machine or
on a real device.
