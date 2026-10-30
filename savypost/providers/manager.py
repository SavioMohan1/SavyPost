"""Provider Manager for SavyPost registering and orchestrating platform dispatchers."""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from savypost.db.models import SocialAccount
from savypost.providers.base import BaseSocialProvider
from savypost.providers.x_provider import XProvider
from savypost.providers.telegram_provider import TelegramProvider
from savypost.providers.discord_provider import DiscordProvider
from savypost.providers.bluesky_provider import BlueskyProvider
from savypost.providers.linkedin_provider import LinkedInProvider
from savypost.providers.reddit_provider import RedditProvider
from savypost.providers.youtube_provider import YouTubeProvider
from savypost.providers.instagram_provider import InstagramProvider
from savypost.providers.webhook_provider import WebhookProvider
from savypost.providers.mock_provider import MockProvider


class SocialProviderManager:
    """Central registry and executor for SavyPost social media providers."""

    def __init__(self):
        self._providers: Dict[str, BaseSocialProvider] = {
            "x": XProvider(),
            "telegram": TelegramProvider(),
            "discord": DiscordProvider(),
            "bluesky": BlueskyProvider(),
            "linkedin": LinkedInProvider(),
            "reddit": RedditProvider(),
            "youtube": YouTubeProvider(),
            "instagram": InstagramProvider(),
            "webhook": WebhookProvider(),
            "mock": MockProvider(),
        }
        self._mock_provider = MockProvider()

    def get_provider(self, identifier: str) -> BaseSocialProvider:
        """Get provider instance by identifier, or mock provider if unknown."""
        return self._providers.get(identifier.lower(), self._mock_provider)

    def validate_for_platforms(
        self,
        platforms: List[str],
        content: str,
        media_paths: List[str] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """Validate content against multiple platform constraints."""
        results = {}
        for p in platforms:
            prov = self.get_provider(p)
            valid, err = prov.validate_post(content, media_paths)
            results[p] = (valid, err)
        return results

    def test_account(self, account: SocialAccount) -> Dict[str, Any]:
        """Test an account connection with intelligent simulation fallback."""
        has_credentials = bool(account.token or account.token_secret)
        
        # If no credentials configured, test simulated connectivity
        if not has_credentials:
            return {
                "success": True,
                "mode": "simulation",
                "message": (
                    f"Simulation Mode Active: {account.name} is verified for zero-risk local testing! "
                    f"All posts to this channel will be simulated with realistic preview links. "
                    f"To connect to your real live {account.provider.upper()} profile, click 'Configure' and enter your API keys."
                )
            }

        provider = self.get_provider(account.provider)
        try:
            return provider.test_connection(account)
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection test error: {str(e)}",
                "platform": account.provider
            }

    def publish_to_account(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Publish content to a single social account, using Mock fallback if no token."""
        if not account.token and not account.token_secret and account.provider != "mock":
            logger.info(f"Account '{account.name}' has no live credentials, running in simulation mode.")
            return self._mock_provider.publish(account, content, media_paths, options)

        provider = self.get_provider(account.provider)
        try:
            return provider.publish(account, content, media_paths, options)
        except Exception as e:
            logger.error(f"Error publishing to {account.provider} ({account.name}): {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": account.provider,
                "account_name": account.name
            }
