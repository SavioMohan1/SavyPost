"""Base social provider interface defining the contract for SavyPost channels."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from savypost.db.models import SocialAccount


class BaseSocialProvider(ABC):
    """Abstract base class for all SavyPost social media providers."""

    identifier: str = "base"
    name: str = "Base Provider"
    max_length: int = 5000

    def validate_post(self, content: str, media_paths: List[str] = None) -> Tuple[bool, str]:
        """Validate post constraints such as text length and media requirements."""
        if not content and not media_paths:
            return False, "Post cannot be empty (content or media required)."

        if len(content) > self.max_length:
            return False, f"Content length ({len(content)}) exceeds {self.name} limit ({self.max_length} characters)."

        return True, ""

    @abstractmethod
    def publish(
        self,
        account: SocialAccount,
        content: str,
        media_paths: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Publish the post to the external platform.
        Returns:
            {
                "success": bool,
                "post_id": Optional[str],
                "release_url": Optional[str],
                "error": Optional[str],
                "platform": str
            }
        """
        pass

    @abstractmethod
    def test_connection(self, account: SocialAccount) -> Dict[str, Any]:
        """Verify credential validity and channel connectivity."""
        pass
