"""Reddit Provider for SavyPost via Reddit OAuth API."""

import json
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class RedditProvider(BaseSocialProvider):
    identifier = "reddit"
    name = "Reddit"
    max_length = 40000

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        token = account.token or account.token_secret
        if not token:
            return {"success": False, "error": "Reddit OAuth token is required."}

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "SavyPost/1.0.0 (by /u/SavioMohan)"
        }
        try:
            resp = httpx.get("https://oauth.reddit.com/api/v1/me", headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "message": f"Connected as u/{data.get('name')}",
                    "karma": data.get("total_karma")
                }
            return {"success": False, "error": f"Reddit status {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        token = account.token or account.token_secret
        settings = json.loads(account.additional_settings or "{}")
        subreddit = settings.get("subreddit") or (options or {}).get("subreddit")

        if not subreddit:
            return {"success": False, "error": "Target subreddit is required.", "platform": self.identifier}

        title = (options or {}).get("title") or content[:80].split("\n")[0]
        body = content

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "SavyPost/1.0.0 (by /u/SavioMohan)"
        }
        data = {
            "sr": subreddit.replace("r/", ""),
            "kind": "self",
            "title": title,
            "text": body,
            "api_type": "json"
        }

        try:
            resp = httpx.post("https://oauth.reddit.com/api/submit", headers=headers, data=data, timeout=20.0)
            res_json = resp.json()
            errors = res_json.get("json", {}).get("errors", [])
            if errors:
                return {"success": False, "error": str(errors), "platform": self.identifier}

            post_data = res_json.get("json", {}).get("data", {})
            post_url = post_data.get("url")
            post_id = post_data.get("id")

            return {
                "success": True,
                "post_id": post_id,
                "release_url": post_url or f"https://reddit.com/r/{subreddit}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"Reddit publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
