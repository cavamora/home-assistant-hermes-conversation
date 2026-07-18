"""Tests for controlled Home Assistant action helpers."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _install_homeassistant_stubs() -> None:
    """Install tiny Home Assistant stubs so pure helpers can be imported."""
    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    conversation_mod = types.ModuleType("homeassistant.components.conversation")
    config_entries = types.ModuleType("homeassistant.config_entries")
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    intent = types.ModuleType("homeassistant.helpers.intent")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    template = types.ModuleType("homeassistant.helpers.template")

    class ConversationEntity:  # noqa: D401 - stub
        pass

    class AbstractConversationAgent:  # noqa: D401 - stub
        pass

    class ConversationEntityFeature:
        CONTROL = 1

    class AssistantContent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class IntentResponse:
        def __init__(self, language=None):
            self.language = language
            self.speech = None

        def async_set_speech(self, speech):
            self.speech = speech

    class Template:
        def __init__(self, template, hass):
            self.template = template

        def async_render(self, *_args, **_kwargs):
            return self.template

    conversation_mod.ConversationEntity = ConversationEntity
    conversation_mod.AbstractConversationAgent = AbstractConversationAgent
    conversation_mod.ConversationEntityFeature = ConversationEntityFeature
    conversation_mod.AssistantContent = AssistantContent
    conversation_mod.ConversationInput = object
    conversation_mod.ChatLog = object
    conversation_mod.ConversationResult = object
    conversation_mod.async_set_agent = lambda *a, **k: None
    conversation_mod.async_unset_agent = lambda *a, **k: None
    config_entries.ConfigEntry = object
    const.CONF_NAME = "name"
    const.MATCH_ALL = "*"
    const.Platform = types.SimpleNamespace(CONVERSATION="conversation")
    core.HomeAssistant = object
    intent.IntentResponse = IntentResponse
    aiohttp_client.async_get_clientsession = lambda hass: None
    entity_platform.AddConfigEntryEntitiesCallback = object
    template.Template = Template

    for module in (
        ha,
        components,
        conversation_mod,
        config_entries,
        const,
        core,
        helpers,
        intent,
        aiohttp_client,
        entity_platform,
        template,
    ):
        sys.modules[module.__name__] = module


_install_homeassistant_stubs()

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
conversation = importlib.import_module(
    "custom_components.home_assistant_hermes_conversation.conversation"
)


def test_parse_control_response_extracts_speech_actions_and_confirmation():
    payload = {
        "output_text": '{"speech":"Vou ligar a luz.","actions":[{"domain":"light","service":"turn_on","entity_id":"light.cozinha"}],"requires_confirmation":true}'
    }

    result = conversation._parse_hermes_control_response(payload)

    assert result.speech == "Vou ligar a luz."
    assert result.requires_confirmation is True
    assert result.actions == [
        {
            "domain": "light",
            "service": "turn_on",
            "entity_id": "light.cozinha",
            "data": {},
        }
    ]


def test_parse_control_response_keeps_plain_text_as_speech_without_actions():
    result = conversation._parse_hermes_control_response({"output_text": "A luz está ligada."})

    assert result.speech == "A luz está ligada."
    assert result.actions == []
    assert result.requires_confirmation is False


def test_parse_control_response_accepts_markdown_json_fence():
    payload = {
        "output_text": '```json\n{"speech":"Pronto.","actions":{"domain":"switch","service":"turn_on","entity_id":"switch.bomba"}}\n```'
    }

    result = conversation._parse_hermes_control_response(payload)

    assert result.speech == "Pronto."
    assert result.actions == [
        {
            "domain": "switch",
            "service": "turn_on",
            "entity_id": "switch.bomba",
            "data": {},
        }
    ]


def test_validate_action_allows_only_configured_domains_and_entities():
    settings = {
        conversation.CONF_ALLOWED_DOMAINS: "light,switch,script",
        conversation.CONF_ALLOWED_ENTITIES: "light.cozinha, script.boas_vindas",
    }

    action = {
        "domain": "light",
        "service": "turn_on",
        "entity_id": "light.cozinha",
        "data": {},
    }

    assert conversation._validate_control_action(action, settings) is None


def test_validate_action_rejects_non_allowlisted_entity():
    settings = {
        conversation.CONF_ALLOWED_DOMAINS: "light,switch",
        conversation.CONF_ALLOWED_ENTITIES: "light.cozinha",
    }
    action = {
        "domain": "light",
        "service": "turn_on",
        "entity_id": "light.quarto",
        "data": {},
    }

    assert conversation._validate_control_action(action, settings) == "entidade light.quarto não permitida"


def test_sensitive_actions_require_confirmation():
    assert conversation._action_requires_confirmation(
        {"domain": "cover", "service": "open_cover", "entity_id": "cover.garagem"},
        {conversation.CONF_CONFIRM_DOMAINS: "cover,lock,alarm_control_panel"},
    ) is True
    assert conversation._action_requires_confirmation(
        {"domain": "light", "service": "turn_on", "entity_id": "light.cozinha"},
        {conversation.CONF_CONFIRM_DOMAINS: "cover,lock,alarm_control_panel"},
    ) is False


def test_native_control_contract_is_appended_to_existing_saved_prompt():
    old_prompt = "Você é Jarvis. Se precisar controlar a casa, use as ferramentas do Hermes."

    result = conversation._with_native_control_contract(
        old_prompt,
        {conversation.CONF_ALLOW_CONTROL: True},
    )

    assert old_prompt in result
    assert "não chame ferramentas de escrita do Hermes" in result
    assert "ha_call_service" in result
    assert "hass.services.async_call" in result


def test_native_control_contract_not_appended_when_control_disabled():
    old_prompt = "Você é Jarvis."

    result = conversation._with_native_control_contract(
        old_prompt,
        {conversation.CONF_ALLOW_CONTROL: False},
    )

    assert result == old_prompt
