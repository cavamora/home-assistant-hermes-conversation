"""Constants for the Home Assistant Hermes Conversation integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "home_assistant_hermes_conversation"

CONF_API_KEY: Final = "api_key"
CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_URL: Final = "url"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_ALLOW_CONTROL: Final = "allow_control"
CONF_ALLOWED_DOMAINS: Final = "allowed_domains"
CONF_ALLOWED_ENTITIES: Final = "allowed_entities"
CONF_CONFIRM_DOMAINS: Final = "confirm_domains"
CONF_CONFIRM_SERVICES: Final = "confirm_services"

DEFAULT_NAME: Final = "Hermes"
DEFAULT_MODEL: Final = "hermes-agent"
DEFAULT_ALLOWED_DOMAINS: Final = "light,switch,script,scene,fan,climate,cover,lock,alarm_control_panel,media_player"
DEFAULT_ALLOWED_ENTITIES: Final = ""
DEFAULT_CONFIRM_DOMAINS: Final = "cover,lock,alarm_control_panel"
DEFAULT_CONFIRM_SERVICES: Final = "open_cover,unlock,lock,disarm,alarm_disarm"
DEFAULT_NATIVE_CONTROL_INSTRUCTIONS: Final = (
    "Para consultar status/estado da casa, você pode responder normalmente e usar as ferramentas do Hermes se precisar. "
    "Para ALTERAR qualquer device do Home Assistant, não chame ferramentas de escrita do Hermes, especialmente ha_call_service. "
    "Em vez disso, retorne somente JSON neste formato: "
    "{\"speech\":\"frase curta para falar\",\"actions\":[{\"domain\":\"light\",\"service\":\"turn_on\",\"entity_id\":\"light.exemplo\",\"data\":{}}]}. "
    "A integração do Home Assistant validará e executará as ações permitidas via hass.services.async_call."
)
DEFAULT_PROMPT: Final = (
    "Você é Jarvis, assistente de voz da casa. Responda curto em português do Brasil. "
    + DEFAULT_NATIVE_CONTROL_INSTRUCTIONS
)
DEFAULT_TIMEOUT: Final = 120
DEFAULT_VERIFY_SSL: Final = False
DEFAULT_ALLOW_CONTROL: Final = True
