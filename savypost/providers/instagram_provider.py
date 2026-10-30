"""Instagram Provider for SavyPost via Meta Graph API (Reels & Feed Publishing)."""

import json
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider

META_GRAPH_VERSION = "v21.0"


class InstagramProvider(BaseSocialProvider):
    identifier = "instagram"
    name = "Instagram (Reels & Feed)"
    max_length = 2200

    def _get_credentials(self, account: SocialAccount):
        access_token = account.token or account.token_secret or ""
        settings = json.loads(account.additional_settings or "{}")
        ig_user_id = settings.get("ig_user_id") or account.username
        return access_token, ig_user_id

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        access_token, ig_user_id = self._get_credentials(account)
        if not access_token:
            return {
                "success": False,
                "error": "Instagram/Meta Graph Access Token is required."
            }

        try:
            url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/me?fields=id,name,accounts&access_token={access_token}"
            resp = httpx.get(url, timeout=12.0)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "message": f"Connected to Meta Account '{data.get('name')}'",
                    "id": data.get("id"),
                    "ig_user_id_configured": bool(ig_user_id)
                }
            return {
                "success": False,
                "error": f"Meta Graph API error ({resp.status_code}): {resp.text}"
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
        access_token, ig_user_id = self._get_credentials(account)
        if not access_token or not ig_user_id:
            return {
                "success": False,
                "error": "Instagram requires Meta Graph Access Token and Instagram Business Account ID (ig_user_id).",
                "platform": self.identifier
            }

        if not media_paths or len(media_paths) == 0:
            return {
                "success": False,
                "error": "Instagram requires at least one photo or video attachment.",
                "platform": self.identifier
            }

        first_media = media_paths[0]
        caption = content[:self.max_length]
        is_video = first_media.lower().endswith((".mp4", ".mov", ".m4v"))

        try:
            container_url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{ig_user_id}/media"
            container_params = {
                "access_token": access_token,
                "caption": caption
            }

            if first_media.startswith(("http://", "https://")):
                if is_video:
                    container_params["media_type"] = "REELS"
                    container_params["video_url"] = first_media
                else:
                    container_params["image_url"] = first_media
            else:
                settings = json.loads(account.additional_settings or "{}")
                media_host = settings.get("media_host_url") or (options or {}).get("media_host_url")
                if media_host:
                    filename = first_media.replace("\\", "/").split("/")[-1]
                    public_url = f"{media_host.rstrip('/')}/{filename}"
                    if is_video:
                        container_params["media_type"] = "REELS"
                        container_params["video_url"] = public_url
                    else:
                        container_params["image_url"] = public_url
                else:
                    return {
                        "success": False,
                        "error": (
                            "Meta Graph API requires an accessible media URL for Instagram to download. "
                            "Upload media to an accessible URL or use a webhook/mock connector."
                        ),
                        "platform": self.identifier
                    }

            create_resp = httpx.post(container_url, data=container_params, timeout=30.0)
            create_data = create_resp.json()

            if "id" not in create_data:
                return {
                    "success": False,
                    "error": f"Failed to create Instagram media container: {create_resp.text}",
                    "platform": self.identifier
                }

            container_id = create_data["id"]

            publish_url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{ig_user_id}/media_publish"
            publish_params = {
                "creation_id": container_id,
                "access_token": access_token
            }
            pub_resp = httpx.post(publish_url, data=publish_params, timeout=30.0)
            pub_data = pub_resp.json()

            if "id" in pub_data:
                media_id = pub_data["id"]
                return {
                    "success": True,
                    "post_id": media_id,
                    "release_url": f"https://www.instagram.com/p/{media_id}",
                    "platform": self.identifier
                }

            return {
                "success": False,
                "error": f"Failed to publish Instagram container: {pub_resp.text}",
                "platform": self.identifier
            }

        except Exception as e:
            logger.error(f"Instagram publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
