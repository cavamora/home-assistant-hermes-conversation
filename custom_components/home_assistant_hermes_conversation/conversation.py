"""Conversation platform for Home Assistant Hermes Conversation."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
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
    CONF_ALLOW_CONTROL,
    CONF_ALLOWED_DOMAINS,
    CONF_ALLOWED_ENTITIES,
    CONF_CONFIRM_DOMAINS,
    CONF_CONFIRM_SERVICES,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_ALLOW_CONTROL,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_ALLOWED_ENTITIES,
    DEFAULT_CONFIRM_DOMAINS,
    DEFAULT_CONFIRM_SERVICES,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_NATIVE_CONTROL_INSTRUCTIONS,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class HermesControlResponse:
    """Hermes response plus optional Home Assistant actions."""

    speech: str
    actions: list[dict[str, Any]]
    requires_confirmation: bool = False


def _split_csv(value: Any) -> set[str]:
    """Return a normalized set from a comma/newline separated option value."""
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        raw_parts = [str(part) for part in value]
    else:
        raw_parts = str(value).replace("\n", ",").split(",")
    return {part.strip() for part in raw_parts if part and part.strip()}


def _normalize_action(raw_action: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Hermes-proposed action to the service-call shape."""
    action = dict(raw_action)
    data = action.get("data")
    if not isinstance(data, dict):
        data = {}
    entity_id = action.get("entity_id")
    if entity_id is None and isinstance(action.get("target"), dict):
        entity_id = action["target"].get("entity_id")
    normalized = {
        "domain": str(action.get("domain", "")).strip(),
        "service": str(action.get("service", "")).strip(),
        "entity_id": entity_id,
        "data": data,
    }
    return normalized


def _strip_json_fence(text: str) -> str:
    """Remove a Markdown JSON code fence if Hermes wrapped structured output."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _parse_hermes_control_response(data: dict[str, Any]) -> HermesControlResponse:
    """Parse Hermes text and optional structured HA actions.

    Plain text remains a normal spoken response. JSON responses may include:
    {"speech": "...", "actions": [{"domain": ..., "service": ..., "entity_id": ...}],
     "requires_confirmation": true}
    """
    text = _extract_hermes_text(data)
    if not text:
        return HermesControlResponse("", [])

    json_text = _strip_json_fence(text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return HermesControlResponse(text.strip(), [])

    if not isinstance(parsed, dict):
        return HermesControlResponse(text.strip(), [])

    speech = parsed.get("speech") or parsed.get("response") or parsed.get("text") or ""
    actions: list[dict[str, Any]] = []
    raw_actions = parsed.get("actions") or []
    if isinstance(raw_actions, dict):
        raw_actions = [raw_actions]
    if isinstance(raw_actions, list):
        for raw_action in raw_actions:
            if isinstance(raw_action, dict):
                actions.append(_normalize_action(raw_action))

    return HermesControlResponse(
        speech=str(speech).strip(),
        actions=actions,
        requires_confirmation=bool(parsed.get("requires_confirmation", False)),
    )


def _validate_control_action(action: dict[str, Any], settings: dict[str, Any]) -> str | None:
    """Validate a proposed HA service call against configured allowlists."""
    domain = str(action.get("domain", "")).strip()
    service = str(action.get("service", "")).strip()
    entity_id = action.get("entity_id")

    if not domain:
        return "domínio ausente"
    if not service:
        return "serviço ausente"

    allowed_domains = _split_csv(settings.get(CONF_ALLOWED_DOMAINS, DEFAULT_ALLOWED_DOMAINS))
    if allowed_domains and domain not in allowed_domains:
        return f"domínio {domain} não permitido"

    allowed_entities = _split_csv(settings.get(CONF_ALLOWED_ENTITIES, DEFAULT_ALLOWED_ENTITIES))
    if allowed_entities and entity_id is not None:
        entity_ids = entity_id if isinstance(entity_id, list) else [entity_id]
        for item in entity_ids:
            item_str = str(item).strip()
            if item_str and item_str not in allowed_entities:
                return f"entidade {item_str} não permitida"

    if not isinstance(action.get("data", {}), dict):
        return "data da ação deve ser um objeto"

    return None


def _action_requires_confirmation(action: dict[str, Any], settings: dict[str, Any]) -> bool:
    """Return true when a service/domain is configured as sensitive."""
    confirm_domains = _split_csv(settings.get(CONF_CONFIRM_DOMAINS, DEFAULT_CONFIRM_DOMAINS))
    confirm_services = _split_csv(settings.get(CONF_CONFIRM_SERVICES, DEFAULT_CONFIRM_SERVICES))
    domain = str(action.get("domain", "")).strip()
    service = str(action.get("service", "")).strip()
    return domain in confirm_domains or service in confirm_services


def _is_confirmation_text(text: str) -> bool:
    """Detect a short affirmative confirmation in Portuguese/English."""
    normalized = text.strip().lower()
    return normalized in {"sim", "pode", "confirmo", "confirma", "ok", "okay", "yes", "y"}


def _service_data_for_action(action: dict[str, Any]) -> dict[str, Any]:
    """Build Home Assistant service data from a normalized action."""
    data = dict(action.get("data") or {})
    entity_id = action.get("entity_id")
    if entity_id:
        data["entity_id"] = entity_id
    return data


def _with_native_control_contract(prompt: str, settings: dict[str, Any]) -> str:
    """Append the native-control contract even for existing saved prompts.

    Existing config entries may still have the old prompt that told Hermes to use
    its own HA write tools. Appending this contract makes the safety behavior
    effective without forcing the user to edit options manually.
    """
    if not bool(settings.get(CONF_ALLOW_CONTROL, DEFAULT_ALLOW_CONTROL)):
        return prompt
    if DEFAULT_NATIVE_CONTROL_INSTRUCTIONS in prompt:
        return prompt
    return f"{prompt.rstrip()}\n\n{DEFAULT_NATIVE_CONTROL_INSTRUCTIONS}"


def _normalize_base_url(url: str) -> str:
    """Normalize a Hermes API Server base URL from user input."""
    base_url = url.strip().rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[: -len("/v1")]
    return base_url


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
        self._pending_actions: dict[str, list[dict[str, Any]]] = {}
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
        conversation_id = user_input.conversation_id or "home-assistant-assist"
        speech_text = "Erro ao chamar o Hermes."

        try:
            settings = {**self.entry.data, **self.entry.options}
            if _is_confirmation_text(user_input.text) and conversation_id in self._pending_actions:
                await self._async_execute_actions(self._pending_actions.pop(conversation_id))
                speech_text = "Confirmado. Executei a ação."
            else:
                base_url = _normalize_base_url(str(settings.get(CONF_URL, "")))
                api_key = str(settings.get(CONF_API_KEY, "")).strip()
                verify_ssl = bool(settings.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
                model = str(settings.get(CONF_MODEL) or DEFAULT_MODEL)

                if not base_url:
                    raise RuntimeError("URL do Hermes não configurada")
                if not api_key:
                    raise RuntimeError("API key do Hermes não configurada")

                prompt = await self._async_render_prompt(
                    _with_native_control_contract(
                        str(settings.get(CONF_PROMPT) or DEFAULT_PROMPT), settings
                    ),
                    user_input,
                )

                payload = {
                    "model": model,
                    "input": user_input.text,
                    "instructions": prompt,
                    "store": False,
                }

                data = await self._async_call_hermes(base_url, api_key, verify_ssl, payload)
                control = _parse_hermes_control_response(data)
                speech_text = control.speech
                if control.actions:
                    speech_text = await self._async_process_control_actions(
                        control, settings, conversation_id
                    )
                if not speech_text:
                    speech_text = "Não recebi uma resposta do Hermes."
        except Exception as err:  # noqa: BLE001 - never let Assist crash on provider failure
            _LOGGER.exception("Error while processing Hermes conversation")
            speech_text = f"Erro ao chamar o Hermes: {err}"

        try:
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=user_input.agent_id,
                    content=speech_text,
                )
            )
        except Exception:  # noqa: BLE001 - chat log failures must not break spoken response
            _LOGGER.exception("Error while adding Hermes response to conversation chat log")

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech_text)

        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=conversation_id in self._pending_actions,
        )

    async def _async_process_control_actions(
        self,
        control: HermesControlResponse,
        settings: dict[str, Any],
        conversation_id: str,
    ) -> str:
        """Validate and execute/prompt for Home Assistant service actions."""
        if not bool(settings.get(CONF_ALLOW_CONTROL, DEFAULT_ALLOW_CONTROL)):
            return "Controle de dispositivos está desativado nesta integração."

        for action in control.actions:
            validation_error = _validate_control_action(action, settings)
            if validation_error:
                return f"Não executei a ação: {validation_error}."

        needs_confirmation = control.requires_confirmation or any(
            _action_requires_confirmation(action, settings) for action in control.actions
        )
        if needs_confirmation:
            self._pending_actions[conversation_id] = control.actions
            return control.speech or "Essa ação precisa de confirmação. Posso executar?"

        await self._async_execute_actions(control.actions)
        return control.speech or "Pronto."

    async def _async_execute_actions(self, actions: list[dict[str, Any]]) -> None:
        """Execute validated Home Assistant service actions natively."""
        for action in actions:
            await self.hass.services.async_call(
                str(action["domain"]),
                str(action["service"]),
                _service_data_for_action(action),
                blocking=True,
            )

    async def _async_render_prompt(
        self, prompt_template: str, user_input: conversation.ConversationInput
    ) -> str:
        """Render the configured prompt as a Home Assistant template."""
        template = Template(prompt_template, self.hass)
        rendered = template.async_render(
            {
                "language": user_input.language,
                "conversation_id": user_input.conversation_id,
                "agent_id": user_input.agent_id,
            },
            parse_result=False,
        )
        return str(rendered)

    async def _async_call_hermes(
        self, base_url: str, api_key: str, verify_ssl: bool, payload: dict[str, Any]
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
                ssl=verify_ssl,
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
