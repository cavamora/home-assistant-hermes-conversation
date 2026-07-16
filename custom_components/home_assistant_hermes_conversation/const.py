"""Constants for the Home Assistant Hermes Conversation integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "home_assistant_hermes_conversation"

CONF_API_KEY: Final = "api_key"
CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_URL: Final = "url"
CONF_VERIFY_SSL: Final = "verify_ssl"

DEFAULT_NAME: Final = "Hermes"
DEFAULT_MODEL: Final = "hermes-agent"
DEFAULT_PROMPT: Final = (
    "Você é Jarvis, assistente de voz da casa. "
    "Responda curto em português do Brasil. "
    "Se precisar controlar ou consultar a casa, use as ferramentas do Hermes."
)
DEFAULT_TIMEOUT: Final = 120
DEFAULT_VERIFY_SSL: Final = False
