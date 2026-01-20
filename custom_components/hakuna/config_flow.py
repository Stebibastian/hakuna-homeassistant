"""Config flow for Hakuna integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HakunaApiClient, HakunaApiError, HakunaAuthError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class HakunaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hakuna."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api_client = HakunaApiClient(
                session=session,
                api_token=user_input[CONF_API_TOKEN],
            )

            try:
                # Test the connection by getting overview
                overview = await api_client.get_overview()

                # Try to get user info from timer or tasks
                user_name = ""
                user_id = None

                try:
                    # Try timer first (has user info if running)
                    timer = await api_client.get_timer()
                    if timer and timer.get("user"):
                        user_name = timer["user"].get("name", "")
                        user_id = timer["user"].get("id")
                except HakunaApiError:
                    pass

                # If no user info from timer, try tasks endpoint
                if not user_id:
                    try:
                        tasks = await api_client.get_tasks()
                        # Tasks endpoint works, use token hash as ID
                        if tasks:
                            token_hash = abs(hash(user_input[CONF_API_TOKEN])) % (10**8)
                            user_id = token_hash
                    except HakunaApiError:
                        pass

                # Create entry with whatever info we have
                if user_id:
                    await self.async_set_unique_id(f"hakuna_{user_id}")
                    self._abort_if_unique_id_configured()
                    title = f"Hakuna ({user_name})" if user_name else "Hakuna"
                    return self.async_create_entry(
                        title=title,
                        data={
                            "api_token": user_input[CONF_API_TOKEN],
                            "user_id": user_id,
                            "user_name": user_name,
                        },
                    )

                # Fallback: use token hash as unique ID
                token_hash = abs(hash(user_input[CONF_API_TOKEN])) % (10**8)
                await self.async_set_unique_id(f"hakuna_{token_hash}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Hakuna",
                    data={
                        "api_token": user_input[CONF_API_TOKEN],
                    },
                )

            except HakunaAuthError:
                errors["base"] = "invalid_auth"
            except HakunaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "token_url": "https://app.hakuna.ch/token",
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return HakunaOptionsFlow(config_entry)


class HakunaOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Hakuna."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
        )
