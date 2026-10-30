"""LinkedIn Provider for SavyPost via LinkedIn REST API."""

import json
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class LinkedInProvider(BaseSocialProvider):
    identifier = "linkedin"
    name = "LinkedIn"
    max_length = 3000

    def _get_headers(self, account: SocialAccount) -> Dict[str, str]:
        token = account.token or account.token_secret or ""
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401"
        }

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        headers = self._get_headers(account)
        try:
            resp = httpx.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "message": f"Connected as {data.get('name')}",
                    "sub": data.get("sub")
                }
            return {"success": False, "error": f"LinkedIn returned {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        headers = self._get_headers(account)
        settings = json.loads(account.additional_settings or "{}")
        author_urn = settings.get("author_urn") or account.username

        if not author_urn:
            try:
                userinfo = httpx.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10.0).json()
                sub = userinfo.get("sub")
                author_urn = f"urn:li:person:{sub}" if sub else None
            except Exception:
                pass

        if not author_urn:
            return {"success": False, "error": "LinkedIn Author URN could not be resolved.", "platform": self.identifier}

        try:
            payload = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content[:self.max_length]
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            resp = httpx.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=payload, timeout=20.0)
            if resp.status_code in [200, 201]:
                data = resp.json()
                post_urn = data.get("id")
                release_url = f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else "https://www.linkedin.com"
                return {
                    "success": True,
                    "post_id": post_urn,
                    "release_url": release_url,
                    "platform": self.identifier
                }
            return {
                "success": False,
                "error": f"LinkedIn error ({resp.status_code}): {resp.text}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"LinkedIn publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
