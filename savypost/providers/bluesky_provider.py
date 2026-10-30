"""Bluesky (AT Protocol) Provider for SavyPost."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class BlueskyProvider(BaseSocialProvider):
    identifier = "bluesky"
    name = "Bluesky"
    max_length = 300

    def _get_credentials(self, account: SocialAccount):
        identifier = account.username or account.name
        password = account.token or account.token_secret
        return identifier, password

    def _create_session(self, identifier: str, password: str) -> Dict[str, Any]:
        url = "https://bsky.social/xrpc/com.atproto.server.createSession"
        payload = {"identifier": identifier, "password": password}
        resp = httpx.post(url, json=payload, timeout=15.0)
        if resp.status_code == 200:
            return resp.json()
        raise Exception(f"Bluesky auth error: {resp.text}")

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        identifier, password = self._get_credentials(account)
        if not identifier or not password:
            return {"success": False, "error": "Bluesky Handle/Email and App Password required."}

        try:
            session = self._create_session(identifier, password)
            return {
                "success": True,
                "message": f"Authenticated as @{session.get('handle')}",
                "did": session.get("did")
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
        identifier, password = self._get_credentials(account)
        if not identifier or not password:
            return {"success": False, "error": "Bluesky credentials missing.", "platform": self.identifier}

        try:
            session = self._create_session(identifier, password)
            access_jwt = session["accessJwt"]
            did = session["did"]
            handle = session["handle"]

            embed = None
            # If media path exists, upload blob
            if media_paths and len(media_paths) > 0:
                first_media = Path(media_paths[0])
                if first_media.exists() and first_media.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    mime_type = "image/jpeg" if first_media.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                    blob_url = "https://bsky.social/xrpc/com.atproto.repo.uploadBlob"
                    with open(first_media, "rb") as f:
                        blob_resp = httpx.post(
                            blob_url,
                            headers={
                                "Authorization": f"Bearer {access_jwt}",
                                "Content-Type": mime_type
                            },
                            content=f.read(),
                            timeout=30.0
                        )
                        if blob_resp.status_code == 200:
                            blob_data = blob_resp.json()
                            embed = {
                                "$type": "app.bsky.embed.images",
                                "images": [
                                    {
                                        "alt": content[:50],
                                        "image": blob_data["blob"]
                                    }
                                ]
                            }

            # Create record in repository
            record = {
                "$type": "app.bsky.feed.post",
                "text": content[:self.max_length],
                "createdAt": datetime.utcnow().isoformat() + "Z"
            }
            if embed:
                record["embed"] = embed

            create_url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
            create_payload = {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record
            }
            create_resp = httpx.post(
                create_url,
                headers={"Authorization": f"Bearer {access_jwt}"},
                json=create_payload,
                timeout=15.0
            )

            if create_resp.status_code == 200:
                res_json = create_resp.json()
                uri = res_json.get("uri", "")
                rkey = uri.split("/")[-1] if "/" in uri else ""
                release_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else f"https://bsky.app/profile/{handle}"
                return {
                    "success": True,
                    "post_id": uri,
                    "release_url": release_url,
                    "platform": self.identifier
                }

            return {
                "success": False,
                "error": f"Bluesky error ({create_resp.status_code}): {create_resp.text}",
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"Bluesky publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
