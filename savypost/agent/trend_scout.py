"""Trend and media intelligence for SavyPost."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


class TrendScout:
    """Discovers viral trends, video media, and topic ideas for social publishing."""

    def __init__(self):
        pass

    def fetch_video_context(self, youtube_url: str) -> Dict[str, Any]:
        """Fetch video metadata and transcript from YouTube."""
        logger.info(f"🔍 [SavyPost Scout] Fetching context for YouTube URL: {youtube_url}")
        try:
            import yt_dlp
            ydl_opts = {"quiet": True, "skip_download": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                return {
                    "success": True,
                    "data": {
                        "title": info.get("title", ""),
                        "description": info.get("description", ""),
                        "tags": info.get("tags", []),
                        "duration": info.get("duration", 0)
                    }
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_local_video_clips(self, media_dirs: Optional[List[Path]] = None) -> List[Dict[str, Any]]:
        """Scan workspace folders for ready-to-share vertical video clips and shorts."""
        clips = []
        target_dirs = media_dirs or [
            Path("d:/Projects/Content Rewards/projects"),
            Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
        ]

        for p_dir in target_dirs:
            if p_dir.exists():
                for f in p_dir.glob("**/*.mp4"):
                    clips.append({
                        "filename": f.name,
                        "path": str(f.resolve()),
                        "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                        "category": f.parent.name
                    })
        return clips
