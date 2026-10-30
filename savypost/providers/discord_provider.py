"""Discord Provider for SavyPost via Webhooks & Discord API."""

import json
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class DiscordProvider(BaseSocialProvider):
    identifier = "discord"
    name = "Discord"
    max_length = 2000

    def _get_credentials(self, account: SocialAccount):
        webhook_url = account.token_secret or account.token
        settings = json.loads(account.additional_settings or "{}")
        channel_id = settings.get("channel_id")
        return webhook_url, channel_id

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        webhook_url, _ = self._get_credentials(account)
        if not webhook_url:
            return {"success": False, "error": "Discord Webhook URL or Bot Token is required."}

        if "discord.com/api/webhooks" in webhook_url:
            try:
                resp = httpx.get(webhook_url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "message": f"Connected to channel via webhook '{data.get('name')}'",
                        "guild_id": data.get("guild_id"),
                    }
                return {"success": False, "error": f"Discord returned status {resp.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": True, "message": "Bot token configured."}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        webhook_url, _ = self._get_credentials(account)
        if not webhook_url:
            return {"success": False, "error": "Discord Webhook URL is missing.", "platform": self.identifier}

        try:
            # Handle media attachments
            if media_paths and len(media_paths) > 0:
                first_media = Path(media_paths[0])
                if first_media.exists():
                    with open(first_media, "rb") as f:
                        files = {"file": (first_media.name, f)}
                        data = {"content": content[:self.max_length]}
                        resp = httpx.post(webhook_url, data=data, files=files, timeout=30.0)
                        if resp.status_code in [200, 204]:
                            return {
                                "success": True,
                                "post_id": "discord_msg",
                                "release_url": webhook_url.split("?")[0],
                                "platform": self.identifier
                            }
                        return {"success": False, "error": resp.text, "platform": self.identifier}

            # Text payload
            payload = {"content": content[:self.max_length]}
            resp = httpx.post(webhook_url, json=payload, timeout=15.0)
            if resp.status_code in [200, 204]:
                return {
                    "success": True,
                    "post_id": "discord_msg",
                    "release_url": webhook_url.split("?")[0],
                    "platform": self.identifier
                }
            return {
                "success": False,
                "error": f"Discord status {resp.status_code}: {resp.text}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"Discord publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
