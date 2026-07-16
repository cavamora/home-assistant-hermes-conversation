"""Config flow for Home Assistant Hermes Conversation."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_KEY,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://homeassistant.local:8642"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): TextSelector(),
        vol.Optional(CONF_PROMPT, default=DEFAULT_PROMPT): TemplateSelector(),
    }
)


class HermesConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Hermes Conversation."""

    VERSION = 1

    async def _async_validate_connection(self, url: str, api_key: str) -> dict[str, str]:
        """Validate Hermes API Server connection."""
        errors: dict[str, str] = {}
        session = async_create_clientsession(self.hass)
        base_url = url.rstrip("/")

        try:
            async with asyncio.timeout(15):
                response = await session.get(
                    f"{base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if response.status in (401, 403):
                    errors["base"] = "invalid_auth"
                elif response.status >= 400:
                    errors["base"] = "cannot_connect"
                else:
                    await response.text()
        except (TimeoutError, aiohttp.ClientError):
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001 - surface as unknown in config flow UI
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = str(user_input[CONF_URL]).strip().rstrip("/")
            api_key = str(user_input[CONF_API_KEY]).strip()
            name = str(user_input.get(CONF_NAME) or DEFAULT_NAME).strip()
            model = str(user_input.get(CONF_MODEL) or DEFAULT_MODEL).strip()
            prompt = str(user_input.get(CONF_PROMPT) or DEFAULT_PROMPT)

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_connection(url, api_key)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_NAME: name,
                        CONF_MODEL: model,
                        CONF_PROMPT: prompt,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return HermesConversationOptionsFlow(config_entry)


class HermesConversationOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Home Assistant Hermes Conversation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self._config_entry.data, **self._config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODEL, default=data.get(CONF_MODEL, DEFAULT_MODEL)
                ): TextSelector(),
                vol.Optional(
                    CONF_PROMPT, default=data.get(CONF_PROMPT, DEFAULT_PROMPT)
                ): TemplateSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
