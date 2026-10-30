"""Telegram Provider for SavyPost via Official Telegram Bot API."""

import json
from pathlib import Path
from typing import Dict, Any, List
import httpx
from loguru import logger
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class TelegramProvider(BaseSocialProvider):
    identifier = "telegram"
    name = "Telegram"
    max_length = 4096

    def _get_credentials(self, account: SocialAccount):
        bot_token = account.token or account.token_secret
        settings = json.loads(account.additional_settings or "{}")
        chat_id = settings.get("chat_id")
        return bot_token, chat_id

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        bot_token, chat_id = self._get_credentials(account)
        if not bot_token:
            return {"success": False, "error": "Bot token is missing."}

        try:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            resp = httpx.get(url, timeout=10.0)
            data = resp.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                return {
                    "success": True,
                    "message": f"Connected as @{bot_info.get('username')}",
                    "bot_name": bot_info.get("first_name"),
                    "chat_id_configured": bool(chat_id)
                }
            return {"success": False, "error": data.get("description", "Failed to connect to Telegram.")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        bot_token, chat_id = self._get_credentials(account)
        if not bot_token or not chat_id:
            return {
                "success": False,
                "error": "Telegram Bot Token and Chat ID (channel/group) are required.",
                "platform": self.identifier
            }

        try:
            # If media is provided, send photo or video
            if media_paths and len(media_paths) > 0:
                first_media = Path(media_paths[0])
                if first_media.exists():
                    ext = first_media.suffix.lower()
                    endpoint = "sendVideo" if ext in [".mp4", ".mov", ".mkv", ".webm"] else "sendPhoto"
                    field = "video" if endpoint == "sendVideo" else "photo"

                    url = f"https://api.telegram.org/bot{bot_token}/{endpoint}"
                    with open(first_media, "rb") as f:
                        files = {field: (first_media.name, f)}
                        data = {
                            "chat_id": chat_id,
                            "caption": content[:1024],
                            "parse_mode": "HTML"
                        }
                        resp = httpx.post(url, data=data, files=files, timeout=30.0)
                        res_json = resp.json()
                        if res_json.get("ok"):
                            msg_id = res_json["result"]["message_id"]
                            channel_clean = chat_id.replace("@", "")
                            release_url = f"https://t.me/{channel_clean}/{msg_id}" if not chat_id.startswith("-100") else f"https://t.me/c/{chat_id[4:]}/{msg_id}"
                            return {
                                "success": True,
                                "post_id": str(msg_id),
                                "release_url": release_url,
                                "platform": self.identifier
                            }
                        return {"success": False, "error": res_json.get("description", "Telegram media error"), "platform": self.identifier}

            # Standard text message
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": content,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            resp = httpx.post(url, json=payload, timeout=15.0)
            res_json = resp.json()
            if res_json.get("ok"):
                msg_id = res_json["result"]["message_id"]
                channel_clean = chat_id.replace("@", "")
                release_url = f"https://t.me/{channel_clean}/{msg_id}"
                return {
                    "success": True,
                    "post_id": str(msg_id),
                    "release_url": release_url,
                    "platform": self.identifier
                }
            return {
                "success": False,
                "error": res_json.get("description", "Failed to send message"),
                "platform": self.identifier
            }
        except Exception as e:
            logger.error(f"Telegram publish error: {e}")
            return {"success": False, "error": str(e), "platform": self.identifier}
