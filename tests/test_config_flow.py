"""Tests for the Commons Radio config flow."""

from __future__ import annotations

import pytest
from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN

from .fixtures import BASE_URL, collection


async def _start_user_flow(hass, api_key: str):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_API_KEY: api_key},
    )


async def test_config_flow_success(hass, aioclient_mock) -> None:
    """Create an entry after the Favorites check succeeds."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())

    result = await _start_user_flow(hass, "valid-key")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "valid-key"}
    headers = aioclient_mock.mock_calls[-1][3]
    assert headers["User-Agent"] == "commonsradio-python/0.1.0 HomeAssistant"


@pytest.mark.parametrize(
    ("status", "expected_error"), [(401, "invalid_auth"), (403, "missing_scope")]
)
async def test_config_flow_auth_errors(
    hass, aioclient_mock, status: int, expected_error: str
) -> None:
    """Show a clear error for an invalid key or missing scope."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", status=status)

    result = await _start_user_flow(hass, "bad-key")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_config_flow_connection_error(hass, aioclient_mock) -> None:
    """Show a connection error when the API cannot be reached."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", exc=ClientConnectionError("offline"))

    result = await _start_user_flow(hass, "key")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_updates_key(hass, aioclient_mock) -> None:
    """Replace an expired API key through reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "old-key"},
        title="Commons Radio",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
