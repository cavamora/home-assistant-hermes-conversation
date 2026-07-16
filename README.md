# Home Assistant Hermes Conversation

Custom integration MVP that registers Hermes Agent as a Home Assistant Assist conversation agent.

## What it does

Flow:

```text
Hey Jarvis / Assist satellite
→ Home Assistant STT
→ Home Assistant Hermes Conversation agent
→ Hermes API Server /v1/responses
→ Hermes response text
→ Home Assistant TTS/satellite
```

Hermes controls Home Assistant using its own configured Home Assistant tools/token.

## Requirements

Hermes API Server must be enabled and reachable from Home Assistant. For the Home Assistant add-on/proxy setup used here, the URL in this integration is usually:

```text
https://homeassistant.local:8443
```

Do not include `/v1` in the integration URL.

```bash
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8443
API_SERVER_KEY=your-strong-key
```

Restart Hermes/gateway after changing these settings.

Test from the Home Assistant host/network:

```bash
curl -k https://homeassistant.local:8443/v1/models \
  -H "Authorization: Bearer ***"
```

If your endpoint is direct HTTP instead of the HTTPS proxy, use HTTP and its port:

```bash
curl http://IP_DO_HERMES:8642/v1/models \
  -H "Authorization: Bearer ***"
```

A `401 Invalid API key` response means the server is reachable and only the API key is wrong. A TLS/certificate error means Home Assistant cannot validate the certificate; leave `Verify SSL certificate` disabled for the local HTTPS proxy/self-signed certificate.

## Manual install

Copy this folder from the repository:

```text
custom_components/home_assistant_hermes_conversation
```

into your Home Assistant config folder:

```text
/config/custom_components/home_assistant_hermes_conversation
```

Restart Home Assistant.

Then go to:

```text
Settings → Devices & services → Add Integration → Home Assistant Hermes Conversation
```

Configure:

- Hermes URL: `https://homeassistant.local:8443`; do not include `/v1`
- API key: value of `API_SERVER_KEY`
- Verify SSL certificate: off for the local `homeassistant.local:8443` endpoint
- Model: `hermes-agent`
- Instructions/personality: e.g. `Você é Jarvis...`

Then choose it in:

```text
Settings → Voice assistants → your Assist pipeline → Conversation agent → Hermes
```

## Git install/update

From the real Home Assistant config directory:

```bash
cd /config
mkdir -p custom_components
git clone https://github.com/cavamora/home-assistant-hermes-conversation.git /tmp/home-assistant-hermes-conversation
cp -r /tmp/home-assistant-hermes-conversation/custom_components/home_assistant_hermes_conversation /config/custom_components/
```

For updates:

```bash
cd /tmp/home-assistant-hermes-conversation
git pull
rm -rf /config/custom_components/home_assistant_hermes_conversation
cp -r custom_components/home_assistant_hermes_conversation /config/custom_components/
```

Restart Home Assistant after install/update.

For HACS custom repository usage, the repository root contains:

```text
custom_components/home_assistant_hermes_conversation
```

Releases also attach `home_assistant_hermes_conversation.zip` for HACS downloads.

## Notes

This is an MVP:

- no streaming yet
- no HA LLM API tool-loop yet
- Hermes is expected to use its own Home Assistant token/tools
- response parsing supports common `/v1/responses` and chat-completions style shapes

## Versioning

Every project change must bump `custom_components/home_assistant_hermes_conversation/manifest.json` `version` before commit.

For HACS-friendly updates, also create and push a matching git tag/release with the release ZIP asset, for example:

```bash
version=v0.1.4
git tag "$version"
git push origin "$version"
cd custom_components/home_assistant_hermes_conversation
zip -r /tmp/home_assistant_hermes_conversation.zip .
cd -
gh release create "$version" /tmp/home_assistant_hermes_conversation.zip --title "$version" --generate-notes
```

