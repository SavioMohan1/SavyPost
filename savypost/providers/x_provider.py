"""Twitter / X Provider for SavyPost via Twitter API v2."""

import json
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class XProvider(BaseSocialProvider):
    identifier = "x"
    name = "X (Twitter)"
    max_length = 280

    def _get_auth_header(self, account: SocialAccount) -> Dict[str, str]:
        token = account.token or account.token_secret
        if not token:
            return {}
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        return {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        headers = self._get_auth_header(account)
        if not headers:
            return {"success": False, "error": "API Token or Bearer Token required."}

        try:
            url = "https://api.twitter.com/2/users/me"
            resp = httpx.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "success": True,
                    "message": f"Connected as @{data.get('username')}",
                    "name": data.get("name"),
                    "id": data.get("id")
                }
            return {
                "success": False,
                "error": f"X API returned {resp.status_code}: {resp.text}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        headers = self._get_auth_header(account)
        if not headers:
            return {"success": False, "error": "X API Token is missing.", "platform": self.identifier}

        try:
            payload: Dict[str, Any] = {"text": content[:self.max_length]}
            url = "https://api.twitter.com/2/tweets"

            resp = httpx.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code in [200, 201]:
                data = resp.json().get("data", {})
                tweet_id = data.get("id")
                username = account.username or "user"
                release_url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id else "https://x.com"
                return {
                    "success": True,
                    "post_id": str(tweet_id),
                    "release_url": release_url,
                    "platform": self.identifier
                }

            return {
                "success": False,
                "error": f"X API error {resp.status_code}: {resp.text}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"X publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
