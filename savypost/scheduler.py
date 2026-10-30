"""Background Scheduler for Automated SavyPost Social Publishing."""

import asyncio
import json
from datetime import datetime
from typing import Optional
from loguru import logger

from savypost.db.database import get_db
from savypost.db.models import SocialPost, SocialAccount
from savypost.providers.manager import SocialProviderManager


class SocialScheduler:
    """Automated task worker that publishes due scheduled posts for SavyPost."""

    def __init__(self, check_interval_seconds: int = 15):
        self.interval = check_interval_seconds
        self.provider_manager = SocialProviderManager()
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background scheduler loop in current asyncio loop."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("🕒 [SavyPost Scheduler] Started background publishing worker.")

    def stop(self):
        """Stop the background scheduler loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            logger.info("🛑 [SavyPost Scheduler] Stopped background worker.")

    async def _run_loop(self):
        while self._is_running:
            try:
                await self.process_due_posts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SavyPost Scheduler] Loop error: {e}")
            await asyncio.sleep(self.interval)

    async def process_due_posts(self):
        """Find and publish any posts whose scheduled time has arrived."""
        now = datetime.utcnow()
        with get_db() as db:
            due_posts = (
                db.query(SocialPost)
                .filter(SocialPost.status == "SCHEDULED", SocialPost.scheduled_at <= now)
                .all()
            )

            for post in due_posts:
                post.status = "PUBLISHING"
                db.flush()

                results = {}
                target_platforms = json.loads(post.target_platforms or "[]")
                account_ids = json.loads(post.account_ids or "[]")
                media_paths = json.loads(post.media_paths or "[]")

                accounts = []
                if account_ids:
                    accounts = db.query(SocialAccount).filter(SocialAccount.id.in_(account_ids), SocialAccount.is_active == True).all()
                elif target_platforms:
                    accounts = db.query(SocialAccount).filter(SocialAccount.provider.in_(target_platforms), SocialAccount.is_active == True).all()

                if not accounts:
                    for plat in target_platforms:
                        mock_acc = SocialAccount(
                            id=0,
                            provider=plat,
                            name=f"{plat.capitalize()} Channel",
                            token="",
                            is_active=True
                        )
                        accounts.append(mock_acc)

                any_success = False
                for acc in accounts:
                    res = self.provider_manager.publish_to_account(
                        account=acc,
                        content=post.content,
                        media_paths=media_paths,
                        options=json.loads(post.metadata_info or "{}")
                    )
                    results[f"{acc.provider}_{acc.id}"] = res
                    if res.get("success"):
                        any_success = True

                post.results = json.dumps(results)
                post.published_at = datetime.utcnow()
                post.status = "PUBLISHED" if any_success else "FAILED"
                db.flush()

                logger.info(f"🚀 [SavyPost Scheduler] Post #{post.id} processed -> Status: {post.status}")
