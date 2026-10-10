"""Config flow for Commons Radio."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .commonsradio import (
    Client,
    CommonsRadioConnectionError,
    ForbiddenError,
    UnauthorizedError,
)
from .const import CONF_API_KEY, DOMAIN, TITLE, USER_AGENT


async def _validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Check an API key through the Favorites endpoint."""
    client = Client(async_get_clientsession(hass), api_key, user_agent=USER_AGENT)
    await client.get_favorites()


class CommonsRadioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Commons Radio config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for and validate an API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_validation_error(user_input[CONF_API_KEY])
            if error is None:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save a replacement API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_validation_error(user_input[CONF_API_KEY])
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _async_validation_error(self, api_key: str) -> str | None:
        """Return a translation key for a validation error."""
        try:
            await _validate_api_key(self.hass, api_key)
        except UnauthorizedError:
            return "invalid_auth"
        except ForbiddenError:
            return "missing_scope"
        except CommonsRadioConnectionError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            return "unknown"
        return None
