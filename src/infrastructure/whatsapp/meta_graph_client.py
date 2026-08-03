from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.domain.shared.errors import ValidationError


@dataclass(frozen=True)
class WabaInfo:
    waba_id: str
    phone_number_id: str
    phone_display: str
    access_token: str


class MetaGraphClient:
    """HTTP client for Meta Graph API — used during WhatsApp Embedded Signup.

    Handles the OAuth code exchange and WABA discovery needed after the
    client completes the Facebook Embedded Signup popup.
    """

    BASE_URL = "https://graph.facebook.com"

    def __init__(self, app_id: str, app_secret: str, api_version: str = "v23.0") -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._version = api_version

    # ── OAuth ─────────────────────────────────────────────────────────────────

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange a short-lived auth code for a user access token.

        Called immediately after the Embedded Signup popup returns a code.
        """
        params = {
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "code": code,
        }
        # Embedded Signup exchanges the code WITHOUT redirect_uri; sending it
        # empty makes Meta reject the exchange.
        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/{self._version}/oauth/access_token",
                params=params,
            )
        data = resp.json()
        if "error" in data:
            raise ValidationError(f"Meta token exchange failed: {data['error'].get('message', 'unknown')}")
        return data["access_token"]

    async def get_long_lived_token(self, short_lived_token: str) -> str:
        """Exchange a short-lived token for a 60-day user access token."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                    "fb_exchange_token": short_lived_token,
                },
            )
        data = resp.json()
        if "error" in data:
            raise ValidationError(f"Meta token extension failed: {data['error'].get('message', 'unknown')}")
        return data["access_token"]

    # ── WABA discovery ────────────────────────────────────────────────────────

    async def get_waba_and_phone(self, user_access_token: str) -> WabaInfo:
        """Discover the WABA ID and phone number ID linked to this user token.

        Returns the first active phone number found in the first WABA. For
        multi-WABA accounts the tenant can later update from Settings.
        """
        waba_id = await self._get_first_waba_id(user_access_token)
        phone_number_id, phone_display = await self._get_first_phone_number(
            waba_id, user_access_token
        )
        return WabaInfo(
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            phone_display=phone_display,
            access_token=user_access_token,
        )

    async def subscribe_waba_to_app(self, waba_id: str, user_access_token: str) -> None:
        """Subscribe the WABA to this app so webhooks are delivered."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self._version}/{waba_id}/subscribed_apps",
                headers={"Authorization": f"Bearer {user_access_token}"},
            )
        data = resp.json()
        if "error" in data:
            raise ValidationError(f"WABA subscription failed: {data['error'].get('message', 'unknown')}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_first_waba_id(self, user_access_token: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/{self._version}/me/whatsapp_business_accounts",
                params={"fields": "id,name", "access_token": user_access_token},
            )
        data = resp.json()
        if "error" in data:
            raise ValidationError(f"Could not fetch WhatsApp Business Accounts: {data['error'].get('message', 'unknown')}")
        accounts = data.get("data", [])
        if not accounts:
            raise ValidationError(
                "No WhatsApp Business Account found. "
                "Make sure the Facebook account has a WhatsApp Business API account linked."
            )
        return accounts[0]["id"]

    async def _get_first_phone_number(
        self, waba_id: str, user_access_token: str
    ) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_URL}/{self._version}/{waba_id}/phone_numbers",
                params={
                    "fields": "id,display_phone_number,verified_name",
                    "access_token": user_access_token,
                },
            )
        data = resp.json()
        if "error" in data:
            raise ValidationError(f"Could not fetch phone numbers: {data['error'].get('message', 'unknown')}")
        phones = data.get("data", [])
        if not phones:
            raise ValidationError(
                "No phone numbers found in the WhatsApp Business Account. "
                "Add a phone number in Meta Business Manager first."
            )
        first = phones[0]
        return first["id"], first.get("display_phone_number", "")
