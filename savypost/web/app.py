"""FastAPI Web Application for SavyPost."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from savypost.db.database import get_db, init_db
from savypost.db.models import SocialAccount, SocialPost, AgentMessage
from savypost.providers.manager import SocialProviderManager
from savypost.agent.social_manager import SocialMediaManager
from savypost.agent.trend_scout import TrendScout
from savypost.scheduler import SocialScheduler
from savypost.config import UPLOAD_DIR, DEFAULT_HOST, DEFAULT_PORT

app = FastAPI(
    title="SavyPost — Local AI Social Media Manager",
    description="Autonomous local multi-channel social media scheduler and AI publisher",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

provider_manager = SocialProviderManager()
social_manager = SocialMediaManager()
trend_scout = TrendScout()
scheduler = SocialScheduler(check_interval_seconds=15)


@app.on_event("startup")
async def startup_event():
    init_db()
    with get_db() as db:
        if db.query(SocialAccount).count() == 0:
            mock_x = SocialAccount(
                provider="x",
                name="Twitter / X (Personal)",
                username="savio_demo",
                token="",
                is_active=True,
                additional_settings="{}"
            )
            mock_ig = SocialAccount(
                provider="instagram",
                name="Instagram (Reels & Creator)",
                username="savio_reels",
                token="",
                is_active=True,
                additional_settings="{}"
            )
            mock_li = SocialAccount(
                provider="linkedin",
                name="LinkedIn (Professional)",
                username="savio_demo",
                token="",
                is_active=True,
                additional_settings="{}"
            )
            mock_tg = SocialAccount(
                provider="telegram",
                name="Telegram (Community Channel)",
                username="savio_channel",
                token="",
                token_secret="",
                is_active=True,
                additional_settings=json.dumps({"chat_id": "@savio_channel"})
            )
            mock_bsky = SocialAccount(
                provider="bluesky",
                name="Bluesky (Creator)",
                username="savio.bsky.social",
                token="",
                is_active=True,
                additional_settings="{}"
            )
            db.add_all([mock_x, mock_ig, mock_li, mock_tg, mock_bsky])
            db.flush()
            logger.info("Initialized default social accounts in SavyPost vault.")
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.stop()


# ----------------- Data Schemas -----------------
class AccountCreate(BaseModel):
    provider: str
    name: str
    username: Optional[str] = None
    token: Optional[str] = None
    token_secret: Optional[str] = None
    additional_settings: Optional[Dict[str, Any]] = None


class PostCreate(BaseModel):
    title: Optional[str] = None
    content: str
    target_platforms: List[str]
    account_ids: Optional[List[int]] = None
    media_paths: Optional[List[str]] = None
    scheduled_at: Optional[str] = None
    publish_now: bool = False


class CampaignGenerateRequest(BaseModel):
    topic: str
    platforms: List[str]
    tone: Optional[str] = "engaging"
    video_clip_path: Optional[str] = None
    youtube_source_url: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = "groq"
    model: Optional[str] = None
    base_url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    api_key: Optional[str] = None
    provider: Optional[str] = "groq"
    model: Optional[str] = None
    base_url: Optional[str] = None


# ----------------- Web UI Route -----------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SavyPost is running. Dashboard template missing.</h1>"


# ----------------- Accounts API -----------------
@app.get("/api/accounts")
async def list_accounts():
    with get_db() as db:
        accounts = db.query(SocialAccount).all()
        return [acc.to_dict() for acc in accounts]


@app.post("/api/accounts")
async def create_account(account_in: AccountCreate):
    with get_db() as db:
        new_acc = SocialAccount(
            provider=account_in.provider.lower(),
            name=account_in.name,
            username=account_in.username,
            token=account_in.token,
            token_secret=account_in.token_secret,
            additional_settings=json.dumps(account_in.additional_settings or {}),
            is_active=True
        )
        db.add(new_acc)
        db.flush()
        return new_acc.to_dict()


@app.put("/api/accounts/{account_id}")
async def update_account(account_id: int, account_in: AccountCreate):
    with get_db() as db:
        acc = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        acc.provider = account_in.provider.lower()
        acc.name = account_in.name
        acc.username = account_in.username
        acc.token = account_in.token
        acc.token_secret = account_in.token_secret
        if account_in.additional_settings is not None:
            acc.additional_settings = json.dumps(account_in.additional_settings)
        db.flush()
        return acc.to_dict()


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    with get_db() as db:
        acc = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        db.delete(acc)
        return {"success": True}


@app.post("/api/accounts/{account_id}/test")
async def test_account(account_id: int):
    with get_db() as db:
        acc = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        return provider_manager.test_account(acc)


# ----------------- Posts API -----------------
@app.get("/api/posts")
async def list_posts(status: Optional[str] = None):
    with get_db() as db:
        query = db.query(SocialPost).order_by(SocialPost.created_at.desc())
        if status:
            query = query.filter(SocialPost.status == status.upper())
        posts = query.all()
        return [p.to_dict() for p in posts]


@app.post("/api/posts")
async def create_post(post_in: PostCreate):
    scheduled_dt = None
    if post_in.scheduled_at and not post_in.publish_now:
        try:
            scheduled_dt = datetime.fromisoformat(post_in.scheduled_at.replace("Z", "+00:00"))
        except Exception:
            scheduled_dt = datetime.utcnow()

    post_dict = social_manager.create_and_schedule_post(
        content=post_in.content,
        target_platforms=post_in.target_platforms,
        scheduled_at=scheduled_dt,
        account_ids=post_in.account_ids,
        media_paths=post_in.media_paths,
        title=post_in.title
    )

    if post_in.publish_now:
        with get_db() as db:
            post = db.query(SocialPost).filter(SocialPost.id == post_dict["id"]).first()
            if post:
                post.scheduled_at = datetime.utcnow()
                post.status = "SCHEDULED"
        await scheduler.process_due_posts()
        with get_db() as db:
            post = db.query(SocialPost).filter(SocialPost.id == post_dict["id"]).first()
            return post.to_dict()

    return post_dict


@app.post("/api/posts/{post_id}/publish-now")
async def publish_post_now(post_id: int):
    with get_db() as db:
        post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        post.scheduled_at = datetime.utcnow()
        post.status = "SCHEDULED"
        db.flush()

    await scheduler.process_due_posts()

    with get_db() as db:
        post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
        return post.to_dict()


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int):
    with get_db() as db:
        post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        db.delete(post)
        return {"success": True}


# ----------------- AI Copilot API -----------------
@app.post("/api/generate")
async def generate_campaign(req: CampaignGenerateRequest):
    return social_manager.generate_campaign(
        topic=req.topic,
        platforms=req.platforms,
        tone=req.tone,
        video_clip_path=req.video_clip_path,
        youtube_source_url=req.youtube_source_url,
        api_key=req.api_key,
        provider=req.provider,
        model=req.model,
        base_url=req.base_url
    )


@app.post("/api/chat")
async def chat_manager(req: ChatRequest):
    reply = social_manager.handle_user_chat(
        user_message=req.message,
        api_key=req.api_key,
        provider=req.provider,
        model=req.model,
        base_url=req.base_url
    )
    return {"reply": reply}


@app.get("/api/chat/history")
async def get_chat_history():
    with get_db() as db:
        messages = db.query(AgentMessage).order_by(AgentMessage.timestamp.asc()).all()
        return [m.to_dict() for m in messages]


@app.get("/api/clips")
async def list_workspace_clips():
    clips = trend_scout.get_local_video_clips()
    return {"clips": clips}


@app.post("/api/upload")
async def upload_media(file: UploadFile = File(...)):
    dest_path = UPLOAD_DIR / file.filename
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {
        "success": True,
        "filename": file.filename,
        "path": str(dest_path.resolve())
    }


@app.get("/api/stats")
async def get_stats():
    with get_db() as db:
        total_posts = db.query(SocialPost).count()
        scheduled_posts = db.query(SocialPost).filter(SocialPost.status == "SCHEDULED").count()
        published_posts = db.query(SocialPost).filter(SocialPost.status == "PUBLISHED").count()
        connected_accounts = db.query(SocialAccount).filter(SocialAccount.is_active == True).count()
        return {
            "total_posts": total_posts,
            "scheduled": scheduled_posts,
            "published": published_posts,
            "accounts": connected_accounts
        }
