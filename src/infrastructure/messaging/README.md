# Infrastructure: Messaging

Channel adapters. Each implements a common `MessagingProvider` port so the application layer is channel-agnostic.

## Adapters

- `whatsapp_provider.py` — Meta WhatsApp Cloud API
- `instagram_provider.py` — Instagram Direct (Meta Graph API)
- `web_widget_provider.py` — In-house WebSocket gateway for the embeddable widget

## Common port

```python
class MessagingProvider(ABC):
    async def send_text(channel_address: str, body: str) -> str
    async def send_buttons(channel_address: str, body: str, buttons: list[Button]) -> str
    async def download_media(media_id: str) -> bytes
    async def verify_webhook(signature: str, payload: bytes) -> bool
```

This makes adding new channels (Telegram, SMS) a matter of implementing the interface.
