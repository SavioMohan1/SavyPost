"""YouTube Provider for SavyPost via Google Data API v3."""

import json
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class YouTubeProvider(BaseSocialProvider):
    identifier = "youtube"
    name = "YouTube"
    max_length = 5000

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        token = account.token or account.token_secret
        if not token:
            return {"success": False, "error": "Google/YouTube OAuth Access Token required."}

        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = httpx.get(
                "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                headers=headers,
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    title = items[0]["snippet"]["title"]
                    return {"success": True, "message": f"Connected to YouTube channel '{title}'"}
            return {"success": False, "error": f"YouTube status {resp.status_code}: {resp.text}"}
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
        if not token:
            return {"success": False, "error": "YouTube OAuth token missing.", "platform": self.identifier}

        title = (options or {}).get("title") or content[:90].split("\n")[0]
        description = content

        if media_paths and len(media_paths) > 0:
            video_path = Path(media_paths[0])
            if video_path.exists():
                try:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/*",
                        "X-Upload-Content-Length": str(video_path.stat().st_size)
                    }
                    metadata = {
                        "snippet": {
                            "title": title[:100],
                            "description": description[:5000],
                            "categoryId": "22"
                        },
                        "status": {
                            "privacyStatus": (options or {}).get("privacy", "public"),
                            "selfDeclaredMadeForKids": False
                        }
                    }
                    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
                    init_resp = httpx.post(init_url, headers=headers, json=metadata, timeout=15.0)

                    if init_resp.status_code == 200:
                        upload_url = init_resp.headers.get("Location")
                        if upload_url:
                            with open(video_path, "rb") as f:
                                up_resp = httpx.put(upload_url, content=f.read(), timeout=120.0)
                                if up_resp.status_code in [200, 201]:
                                    data = up_resp.json()
                                    vid_id = data.get("id")
                                    return {
                                        "success": True,
                                        "post_id": vid_id,
                                        "release_url": f"https://youtube.com/watch?v={vid_id}",
                                        "platform": self.identifier
                                    }
                    return {"success": False, "error": init_resp.text, "platform": self.identifier}
                except Exception as e:
                    return {"success": False, "error": str(e), "platform": self.identifier}

        return {"success": False, "error": "YouTube publishing requires a video file.", "platform": self.identifier}
