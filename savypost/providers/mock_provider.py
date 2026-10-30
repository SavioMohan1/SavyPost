"""Simulation / Dry-Run Provider for SavyPost testing."""

import uuid
from typing import Dict, Any, List
from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider


class MockProvider(BaseSocialProvider):
    identifier = "mock"
    name = "Simulation (Mock Mode)"
    max_length = 10000

    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Simulation mode active for {account.name}. Ready for zero-risk test posts!"
        }

    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        post_id = str(uuid.uuid4())[:8]
        release_url = f"https://mock.social/posts/{account.provider}/{post_id}"

        return {
            "success": True,
            "post_id": post_id,
            "release_url": release_url,
            "platform": account.provider,
            "message": f"[Simulated Post] Successfully posted to {account.name} ({account.provider})"
        }
