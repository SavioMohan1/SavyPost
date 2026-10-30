"""Universal Webhook Provider for SavyPost (n8n, Zapier, Make, and custom HTTP endpoints)."""

from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class WebhookProvider(BaseSocialProvider):
    identifier = "webhook"
    name = "Custom Webhook (Zapier/n8n/Make)"
    max_length = 100000

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        url = account.token_secret or account.token
        if not url:
            return {"success": False, "error": "Webhook URL is missing."}
        return {"success": True, "message": f"Webhook target configured: {url[:30]}..."}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        url = account.token_secret or account.token
        if not url:
            return {"success": False, "error": "Webhook endpoint URL required.", "platform": self.identifier}

        payload = {
            "content": content,
            "media_paths": media_paths or [],
            "options": options or {},
            "account": {
                "name": account.name,
                "provider": account.provider,
                "username": account.username
            }
        }

        try:
            resp = httpx.post(url, json=payload, timeout=15.0)
            if resp.status_code in [200, 201, 204]:
                return {
                    "success": True,
                    "post_id": "webhook_event",
                    "release_url": url,
                    "platform": self.identifier
                }
            return {
                "success": False,
                "error": f"Webhook returned HTTP {resp.status_code}: {resp.text[:200]}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"Webhook publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
