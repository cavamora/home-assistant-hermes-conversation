# Hermes Conversation for Home Assistant

Custom integration MVP that registers Hermes Agent as a Home Assistant Assist conversation agent.

## What it does

Flow:

```text
Hey Jarvis / Assist satellite
→ Home Assistant STT
→ Hermes Conversation agent
→ Hermes API Server /v1/responses
→ Hermes response text
→ Home Assistant TTS/satellite
```

Hermes controls Home Assistant using its own configured Home Assistant tools/token.

## Requirements

Hermes API Server must be enabled and reachable from Home Assistant:

```bash
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=your-strong-key
```

Restart Hermes/gateway after changing these settings.

Test from the Home Assistant host/network:

```bash
curl http://IP_DO_HERMES:8642/v1/models \
  -H "Authorization: Bearer SUA_CHAVE"
```

## Install

Copy this folder:

```text
custom_components/hermes_conversation
```

into your Home Assistant config folder:

```text
/config/custom_components/hermes_conversation
```

Restart Home Assistant.

Then go to:

```text
Settings → Devices & services → Add Integration → Hermes Conversation
```

Configure:

- Hermes URL: `http://IP_DO_HERMES:8642`
- API key: value of `API_SERVER_KEY`
- Model: `hermes-agent`
- Instructions/personality: e.g. `Você é Jarvis...`

Then choose it in:

```text
Settings → Voice assistants → your Assist pipeline → Conversation agent → Hermes
```

## Notes

This is an MVP:

- no streaming yet
- no HA LLM API tool-loop yet
- Hermes is expected to use its own Home Assistant token/tools
- response parsing supports common `/v1/responses` and chat-completions style shapes


## Git install

From the real Home Assistant config directory:

```bash
cd /config
mkdir -p custom_components
git clone https://github.com/OWNER/hermes-conversation.git /config/custom_components/hermes_conversation
```

For updates:

```bash
cd /config/custom_components/hermes_conversation
git pull
```

Restart Home Assistant after install/update.

For HACS custom repository usage, the repository root should contain `custom_components/hermes_conversation`.
