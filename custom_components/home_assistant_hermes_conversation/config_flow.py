"""Config flow for Home Assistant Hermes Conversation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_KEY,
    CONF_ALLOW_CONTROL,
    CONF_ALLOWED_DOMAINS,
    CONF_ALLOWED_ENTITIES,
    CONF_CONFIRM_DOMAINS,
    CONF_CONFIRM_SERVICES,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DEFAULT_ALLOW_CONTROL,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_ALLOWED_ENTITIES,
    DEFAULT_CONFIRM_DOMAINS,
    DEFAULT_CONFIRM_SERVICES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="https://homeassistant.local:8443"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): TextSelector(),
        vol.Optional(CONF_PROMPT, default=DEFAULT_PROMPT): TemplateSelector(),
        vol.Optional(CONF_ALLOW_CONTROL, default=DEFAULT_ALLOW_CONTROL): BooleanSelector(),
        vol.Optional(CONF_ALLOWED_DOMAINS, default=DEFAULT_ALLOWED_DOMAINS): TextSelector(),
        vol.Optional(CONF_ALLOWED_ENTITIES, default=DEFAULT_ALLOWED_ENTITIES): TextSelector(),
        vol.Optional(CONF_CONFIRM_DOMAINS, default=DEFAULT_CONFIRM_DOMAINS): TextSelector(),
        vol.Optional(CONF_CONFIRM_SERVICES, default=DEFAULT_CONFIRM_SERVICES): TextSelector(),
    }
)


def _normalize_base_url(url: str) -> str:
    """Normalize a Hermes API Server base URL from user input."""
    base_url = url.strip().rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[: -len("/v1")]
    return base_url


class HermesConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Hermes Conversation."""

    VERSION = 1

    async def _async_validate_connection(
        self, url: str, api_key: str, verify_ssl: bool
    ) -> dict[str, str]:
        """Validate Hermes API Server connection."""
        errors: dict[str, str] = {}
        session = async_create_clientsession(self.hass)
        base_url = _normalize_base_url(url)

        try:
            async with asyncio.timeout(15):
                response = await session.get(
                    f"{base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    ssl=verify_ssl,
                )
                if response.status in (401, 403):
                    errors["base"] = "invalid_auth"
                elif response.status == 404:
                    errors["base"] = "endpoint_not_found"
                elif response.status >= 400:
                    _LOGGER.warning(
                        "Hermes API validation failed with HTTP %s: %s",
                        response.status,
                        (await response.text())[:300],
                    )
                    errors["base"] = "cannot_connect"
                else:
                    await response.text()
        except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError) as err:
            _LOGGER.warning("Hermes API TLS verification failed for %s: %s", base_url, err)
            errors["base"] = "ssl_error"
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.warning("Cannot connect to Hermes API at %s: %s", base_url, err)
            errors["base"] = "cannot_connect"
        except Exception as err:  # noqa: BLE001 - surface as unknown in config flow UI
            _LOGGER.exception("Unexpected Hermes API validation error for %s: %s", base_url, err)
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_base_url(str(user_input[CONF_URL]))
            api_key = str(user_input[CONF_API_KEY]).strip()
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
            name = str(user_input.get(CONF_NAME) or DEFAULT_NAME).strip()
            model = str(user_input.get(CONF_MODEL) or DEFAULT_MODEL).strip()
            prompt = str(user_input.get(CONF_PROMPT) or DEFAULT_PROMPT)
            allow_control = bool(user_input.get(CONF_ALLOW_CONTROL, DEFAULT_ALLOW_CONTROL))
            allowed_domains = str(user_input.get(CONF_ALLOWED_DOMAINS) or DEFAULT_ALLOWED_DOMAINS)
            allowed_entities = str(user_input.get(CONF_ALLOWED_ENTITIES) or DEFAULT_ALLOWED_ENTITIES)
            confirm_domains = str(user_input.get(CONF_CONFIRM_DOMAINS) or DEFAULT_CONFIRM_DOMAINS)
            confirm_services = str(user_input.get(CONF_CONFIRM_SERVICES) or DEFAULT_CONFIRM_SERVICES)

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_connection(url, api_key, verify_ssl)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_NAME: name,
                        CONF_MODEL: model,
                        CONF_PROMPT: prompt,
                        CONF_ALLOW_CONTROL: allow_control,
                        CONF_ALLOWED_DOMAINS: allowed_domains,
                        CONF_ALLOWED_ENTITIES: allowed_entities,
                        CONF_CONFIRM_DOMAINS: confirm_domains,
                        CONF_CONFIRM_SERVICES: confirm_services,
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
                    CONF_VERIFY_SSL,
                    default=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MODEL, default=data.get(CONF_MODEL, DEFAULT_MODEL)
                ): TextSelector(),
                vol.Optional(
                    CONF_PROMPT, default=data.get(CONF_PROMPT, DEFAULT_PROMPT)
                ): TemplateSelector(),
                vol.Optional(
                    CONF_ALLOW_CONTROL,
                    default=data.get(CONF_ALLOW_CONTROL, DEFAULT_ALLOW_CONTROL),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ALLOWED_DOMAINS,
                    default=data.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS),
                ): TextSelector(),
                vol.Optional(
                    CONF_ALLOWED_ENTITIES,
                    default=data.get(CONF_ALLOWED_ENTITIES, DEFAULT_ALLOWED_ENTITIES),
                ): TextSelector(),
                vol.Optional(
                    CONF_CONFIRM_DOMAINS,
                    default=data.get(CONF_CONFIRM_DOMAINS, DEFAULT_CONFIRM_DOMAINS),
                ): TextSelector(),
                vol.Optional(
                    CONF_CONFIRM_SERVICES,
                    default=data.get(CONF_CONFIRM_SERVICES, DEFAULT_CONFIRM_SERVICES),
                ): TextSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
