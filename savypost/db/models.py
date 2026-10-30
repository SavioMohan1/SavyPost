"""Database schema and ORM models for SavyPost local SQLite storage."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SocialAccount(Base):
    """Connected Social Media Account / Channel in SavyPost."""
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)  # x, linkedin, telegram, discord, bluesky, youtube, instagram, reddit, webhook, mock
    name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=True)
    picture = Column(String(255), nullable=True)
    token = Column(Text, nullable=True)  # Primary access token or API key
    token_secret = Column(Text, nullable=True)  # API Secret, Webhook URL, or Bot Token
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    additional_settings = Column(Text, default="{}")  # JSON metadata (chat_id, ig_user_id, etc.)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "name": self.name,
            "username": self.username,
            "picture": self.picture,
            "has_token": bool(self.token),
            "is_active": self.is_active,
            "additional_settings": self.additional_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SocialPost(Base):
    """Scheduled, Draft, or Published Social Post in SavyPost."""
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    target_platforms = Column(Text, nullable=False)  # JSON array: ["x", "instagram", "telegram", ...]
    account_ids = Column(Text, default="[]")  # JSON array of specific account IDs
    media_paths = Column(Text, default="[]")  # JSON array of local media file paths
    scheduled_at = Column(DateTime, nullable=True)  # When scheduled to post
    published_at = Column(DateTime, nullable=True)  # When actually published
    status = Column(String(30), default="DRAFT")  # DRAFT, SCHEDULED, PUBLISHING, PUBLISHED, FAILED
    results = Column(Text, default="{}")  # JSON mapping platform -> status/URL/error
    metadata_info = Column(Text, default="{}")  # JSON tags, hashtags, source video/clip ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "target_platforms": json.loads(self.target_platforms or "[]"),
            "account_ids": json.loads(self.account_ids or "[]"),
            "media_paths": json.loads(self.media_paths or "[]"),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "status": self.status,
            "results": json.loads(self.results or "{}"),
            "metadata": json.loads(self.metadata_info or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentMessage(Base):
    """Interaction conversation history with the SavyPost AI Social Media Copilot."""
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
