"""Conversation platform for Hermes Conversation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.template import Template

from .const import (
    CONF_API_KEY,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hermes conversation entities."""
    async_add_entities([HermesConversationEntity(config_entry)])


class HermesConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Hermes conversation agent."""

    _attr_should_poll = False
    _attr_supports_streaming = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Hermes conversation agent."""
        self.entry = entry
        data = {**entry.data, **entry.options}
        self._attr_name = data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register this entity as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity as a conversation agent."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Send the transcribed Assist message to Hermes and return speech."""
        settings = {**self.entry.data, **self.entry.options}
        base_url = str(settings[CONF_URL]).rstrip("/")
        api_key = str(settings[CONF_API_KEY]).strip()
        model = str(settings.get(CONF_MODEL) or DEFAULT_MODEL)
        prompt = await self._async_render_prompt(
            str(settings.get(CONF_PROMPT) or DEFAULT_PROMPT), user_input
        )

        hermes_conversation_id = user_input.conversation_id or "home-assistant-assist"
        payload = {
            "model": model,
            "input": user_input.text,
            "instructions": prompt,
            "conversation": hermes_conversation_id,
        }

        try:
            data = await self._async_call_hermes(base_url, api_key, payload)
            speech_text = _extract_hermes_text(data)
            if not speech_text:
                speech_text = "Não recebi uma resposta do Hermes."
        except Exception as err:  # noqa: BLE001 - convert all failures to spoken response
            _LOGGER.exception("Error while calling Hermes")
            speech_text = f"Erro ao chamar o Hermes: {err}"

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=speech_text,
            )
        )

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech_text)

        return conversation.ConversationResult(
            conversation_id=hermes_conversation_id,
            response=response,
            continue_conversation=False,
        )

    async def _async_render_prompt(
        self, prompt_template: str, user_input: conversation.ConversationInput
    ) -> str:
        """Render the configured prompt as a Home Assistant template."""
        template = Template(prompt_template, self.hass)
        rendered = await template.async_render(
            {
                "language": user_input.language,
                "conversation_id": user_input.conversation_id,
                "agent_id": user_input.agent_id,
            },
            parse_result=False,
        )
        return str(rendered)

    async def _async_call_hermes(
        self, base_url: str, api_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Call Hermes /v1/responses."""
        session = async_get_clientsession(self.hass)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                f"{base_url}/v1/responses",
                headers=headers,
                json=payload,
            )
            text = await response.text()
            if response.status == 401 or response.status == 403:
                raise RuntimeError("autenticação recusada pelo Hermes")
            if response.status >= 400:
                raise RuntimeError(f"Hermes HTTP {response.status}: {text[:300]}")
            try:
                return await response.json()
            except aiohttp.ContentTypeError as err:
                raise RuntimeError(f"resposta não-JSON do Hermes: {text[:300]}") from err


def _extract_hermes_text(data: dict[str, Any]) -> str:
    """Extract text from Hermes/OpenAI-compatible response shapes."""
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    output = data.get("output")
    if isinstance(output, str):
        return output.strip()

    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                    elif isinstance(block.get("content"), str):
                        parts.append(block["content"])
        if parts:
            return "".join(parts).strip()

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"].strip()
            if isinstance(first.get("text"), str):
                return first["text"].strip()

    return ""
