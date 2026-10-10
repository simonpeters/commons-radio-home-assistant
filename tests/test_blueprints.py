"""Tests for the Commons Radio blueprints."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.automation import config as automation_config
from homeassistant.components.automation.helpers import (
    async_get_blueprints as async_get_automation_blueprints,
)
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.script import config as script_config
from homeassistant.components.script.helpers import (
    async_get_blueprints as async_get_script_blueprints,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

REPOSITORY_ROOT = Path(__file__).parents[1]
BLUEPRINTS = (
    (
        "automation",
        "wake_up.yaml",
        {
            "media_players": ["media_player.bedroom"],
            "wake_time": "07:00:00",
            "source_type": "collection",
            "source_name": "Morning",
        },
    ),
    (
        "automation",
        "come_home.yaml",
        {
            "media_players": ["media_player.kitchen"],
            "source_type": "station",
            "source_name": "NTS Radio",
        },
    ),
    (
        "automation",
        "everyone_leaves.yaml",
        {"media_players": ["media_player.kitchen"]},
    ),
    (
        "script",
        "fall_asleep.yaml",
        {
            "media_players": ["media_player.bedroom"],
            "source_type": "favorites",
        },
    ),
)


def _install_blueprint(hass, domain: str, file_name: str) -> str:
    """Copy one repository blueprint into the test Home Assistant config."""
    relative_path = f"commons_radio/{file_name}"
    source = REPOSITORY_ROOT / "blueprints" / domain / relative_path
    destination = Path(hass.config.path("blueprints", domain, relative_path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return relative_path


def _blueprint_instance(path: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Make a config that uses one blueprint."""
    return {
        "alias": f"Test {Path(path).stem}",
        "use_blueprint": {"path": path, "input": inputs},
    }


@pytest.mark.parametrize(("domain", "file_name", "inputs"), BLUEPRINTS)
async def test_blueprint_loads_and_validates(
    hass,
    domain: str,
    file_name: str,
    inputs: dict[str, Any],
) -> None:
    """Load each blueprint and validate a config that uses it."""
    path = _install_blueprint(hass, domain, file_name)
    if domain == "automation":
        manager = async_get_automation_blueprints(hass)
    else:
        manager = async_get_script_blueprints(hass)

    blueprint = await manager.async_get_blueprint(path)

    assert isinstance(blueprint, Blueprint)
    assert blueprint.domain == domain
    assert blueprint.metadata["author"] == "Commons Radio"
    assert blueprint.validate() is None

    instance = _blueprint_instance(path, inputs)
    if domain == "automation":
        validated = await automation_config.async_validate_config_item(
            hass, file_name, instance
        )
        assert validated.validation_status is automation_config.ValidationStatus.OK
    else:
        validated = await script_config.async_validate_config_item(
            hass, "fall_asleep", instance
        )
        assert validated.validation_status is script_config.ValidationStatus.OK


@pytest.mark.freeze_time("2026-10-10 03:00:00+00:00")
async def test_come_home_plays_only_in_time_window(hass, freezer) -> None:
    """Play after the first arrival only when the time window matches."""
    await hass.config.async_set_time_zone("UTC")
    path = _install_blueprint(hass, "automation", "come_home.yaml")
    play_calls = async_mock_service(hass, "commons_radio", "play")
    async_mock_service(hass, "media_player", "volume_set")
    hass.states.async_set("zone.home", "0")
    config = {
        "automation": [
            _blueprint_instance(
                path,
                {
                    "media_players": ["media_player.kitchen"],
                    "source_type": "collection",
                    "source_name": "Morning",
                    "after": "06:00:00",
                    "before": "23:00:00",
                },
            )
        ]
    }
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()

    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()

    assert play_calls == []

    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()
    freezer.move_to("2026-10-10 12:00:00+00:00")
    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()

    assert len(play_calls) == 1
    assert play_calls[0].data == {
        ATTR_ENTITY_ID: ["media_player.kitchen"],
        "collection": "Morning",
    }


async def test_everyone_leaves_stops_selected_speakers(hass) -> None:
    """Stop the selected speakers after the last person leaves."""
    path = _install_blueprint(hass, "automation", "everyone_leaves.yaml")
    stop_calls = async_mock_service(hass, "media_player", "media_stop")
    hass.states.async_set("zone.home", "1")
    config = {
        "automation": [
            _blueprint_instance(
                path,
                {
                    "media_players": [
                        "media_player.kitchen",
                        "media_player.living_room",
                    ],
                    "leave_delay": {"seconds": 0},
                },
            )
        ]
    }
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()

    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()

    assert len(stop_calls) == 1
    assert stop_calls[0].data == {
        ATTR_ENTITY_ID: [
            "media_player.kitchen",
            "media_player.living_room",
        ]
    }
