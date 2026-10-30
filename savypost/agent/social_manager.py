"""SavyPost Autonomous AI Social Media Manager."""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
import requests

from savypost.db.database import get_db
from savypost.db.models import SocialPost, SocialAccount, AgentMessage
from savypost.agent.trend_scout import TrendScout
from savypost.config import PLATFORM_LIMITS, RUFLO_MEMORY_PATH


class SocialMediaManager:
    """Autonomous AI Social Media Manager for SavyPost."""

    def __init__(self):
        self.scout = TrendScout()

    def store_memory(self, key: str, value: Any, tags: Optional[List[str]] = None) -> bool:
        """Persist viral hooks, campaign learnings, and audit trails in vector memory."""
        try:
            RUFLO_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing = {}
            if RUFLO_MEMORY_PATH.exists():
                try:
                    with open(RUFLO_MEMORY_PATH, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}

            existing[key] = {
                "value": value,
                "tags": tags or ["savypost", "social_manager"],
                "updated_at": datetime.utcnow().isoformat()
            }
            with open(RUFLO_MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.warning(f"SavyPost memory store error: {e}")
            return False

    def generate_campaign(
        self,
        topic: str,
        platforms: List[str] = None,
        tone: str = "engaging",
        video_clip_path: Optional[str] = None,
        youtube_source_url: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = "groq",
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate tailored posts across multiple platforms with high-retention hooks."""
        platforms = platforms or ["x", "instagram", "linkedin", "telegram", "bluesky"]
        logger.info(f"[SavyPost Manager] Drafting campaign for topic: '{topic}'")

        yt_context = ""
        if youtube_source_url:
            yt_info = self.scout.fetch_video_context(youtube_source_url)
            if yt_info.get("success"):
                data = yt_info.get("data", {})
                title = data.get("title", "")
                yt_context = f"\nSource Video Title: {title}\nSummary: {str(data.get('description', ''))[:300]}"

        system_prompt = (
            "You are an elite, viral Social Media Manager and Growth Strategist for SavyPost. "
            "Your job is to produce high-impact, platform-optimized social posts. "
            "Tailor formatting and tone for each platform:\n"
            "- X (Twitter): High-curiosity opening hook, line breaks, maximum 280 characters, 1-2 hashtags.\n"
            "- Instagram: Punchy hook in first sentence, clean bullet points, call-to-action to save/share, 3-5 hashtags, under 2,200 chars.\n"
            "- LinkedIn: Thought-leadership story, clear takeaways, professional yet authentic tone, line breaks.\n"
            "- Telegram / Discord: Community-centric announcement with formatting and emojis.\n"
            "- Bluesky: Witty, casual, under 300 characters.\n"
            "- Reddit: Deep value, discussion prompt, authentic, no hype or hashtags.\n"
            "- YouTube: Compelling title (under 90 chars) and rich description with tags.\n\n"
            "Respond strictly in JSON format with a key for each requested platform containing "
            "the generated text under 'content' and any 'hashtags' list."
        )

        user_prompt = (
            f"Topic: {topic}\nTone: {tone}\nRequested Platforms: {', '.join(platforms)}"
            f"{yt_context}\n"
            "Generate optimized copy for each platform."
        )

        parsed = self._generate_with_llm(
            system_prompt, user_prompt, topic, platforms,
            api_key=api_key, provider=provider, model=model, base_url=base_url
        )

        output_posts = {}
        for plat in platforms:
            plat_data = parsed.get(plat) or parsed.get(plat.lower())
            if isinstance(plat_data, dict):
                content = plat_data.get("content", f"Excited to share insights on {topic}!")
            elif isinstance(plat_data, str):
                content = plat_data
            else:
                content = f"Check out our latest update on {topic}! #Innovation"

            limit = PLATFORM_LIMITS.get(plat, 5000)
            if len(content) > limit:
                content = content[:limit - 3] + "..."

            output_posts[plat] = {
                "platform": plat,
                "content": content,
                "media_paths": [video_clip_path] if video_clip_path else [],
                "character_count": len(content),
                "limit": limit
            }

        self.store_memory(
            key=f"campaign_{topic[:20].lower().replace(' ', '_')}",
            value={"topic": topic, "platforms": platforms, "samples": {k: v["content"][:100] for k, v in output_posts.items()}},
            tags=["social_campaign", "savypost"]
        )

        return {
            "topic": topic,
            "posts": output_posts,
            "video_clip": video_clip_path,
            "status": "ready"
        }

    def create_and_schedule_post(
        self,
        content: str,
        target_platforms: List[str],
        scheduled_at: Optional[datetime] = None,
        account_ids: Optional[List[int]] = None,
        media_paths: Optional[List[str]] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a post and schedule it in the local database."""
        status = "SCHEDULED" if scheduled_at else "DRAFT"
        scheduled_time = scheduled_at or (datetime.utcnow() + timedelta(minutes=5))

        with get_db() as db:
            post = SocialPost(
                title=title or content[:60].split("\n")[0],
                content=content,
                target_platforms=json.dumps(target_platforms),
                account_ids=json.dumps(account_ids or []),
                media_paths=json.dumps(media_paths or []),
                scheduled_at=scheduled_time,
                status=status,
                metadata_info=json.dumps({"source": "savypost_agent"})
            )
            db.add(post)
            db.flush()
            post_dict = post.to_dict()

        logger.info(f"[SavyPost] Scheduled post #{post_dict['id']} for {scheduled_time.isoformat()}")
        return post_dict

    def handle_user_chat(
        self,
        user_message: str,
        api_key: Optional[str] = None,
        provider: Optional[str] = "groq",
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> str:
        """Interactive conversational interface for SavyPost Social Media Manager."""
        with get_db() as db:
            db.add(AgentMessage(role="user", content=user_message))
            db.flush()

            recent_history = db.query(AgentMessage).order_by(AgentMessage.timestamp.desc()).limit(8).all()
            history_text = "\n".join([f"{m.role.capitalize()}: {m.content}" for m in reversed(recent_history)])

        system_prompt = (
            "You are SavyPost, an elite AI Social Media Manager running locally on the user's laptop. "
            "You help creators, founders, and developers plan, draft, optimize viral hooks, and schedule cross-platform campaigns "
            "across Instagram, X, LinkedIn, Telegram, Discord, Bluesky, Reddit, and YouTube. "
            "Be creative, direct, concise, and provide ready-to-copy social media posts with strategic hooks."
        )

        reply = self._chat_with_llm(
            system_prompt, history_text, user_message,
            api_key=api_key, provider=provider, model=model, base_url=base_url
        )

        with get_db() as db:
            db.add(AgentMessage(role="assistant", content=reply))
            db.flush()

        return reply

    def _resolve_llm_config(
        self,
        api_key: Optional[str],
        provider: Optional[str],
        model: Optional[str],
        base_url: Optional[str]
    ):
        """Determine endpoint URL, key, and model according to chosen provider."""
        provider = (provider or "groq").lower()
        key = api_key or os.getenv("LLM_API_KEY", "")

        if provider == "openai":
            url = base_url or "https://api.openai.com/v1"
            m = model or "gpt-4o-mini"
        elif provider == "groq":
            url = base_url or "https://api.groq.com/openai/v1"
            m = model or "llama-3.3-70b-versatile"
        elif provider == "anthropic":
            url = base_url or "https://api.anthropic.com/v1"
            m = model or "claude-3-5-haiku-latest"
        elif provider == "gemini":
            url = base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
            m = model or "gemini-2.0-flash"
        elif provider == "openrouter":
            url = base_url or "https://openrouter.ai/api/v1"
            m = model or "meta-llama/llama-3.3-70b-instruct"
        elif provider == "ollama":
            url = base_url or "http://localhost:11434/v1"
            m = model or "llama3.2:latest"
        else:
            url = base_url or os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
            m = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

        return url.rstrip("/"), key, m

    def _generate_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        topic: str,
        platforms: List[str],
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query LLM endpoint or return intelligent heuristic fallback."""
        url, key, m = self._resolve_llm_config(api_key, provider, model, base_url)

        if key or "localhost" in url or "127.0.0.1" in url:
            try:
                endpoint = f"{url}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"

                payload = {
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7
                }
                res = requests.post(endpoint, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
            except Exception as e:
                logger.warning(f"LLM generation call failed ({e}), falling back to heuristic templates.")

        return self._fallback_generation(topic, platforms)

    def _chat_with_llm(
        self,
        system_prompt: str,
        history: str,
        user_message: str,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> str:
        """Generate response for user chat using configured provider API key."""
        url, key, m = self._resolve_llm_config(api_key, provider, model, base_url)

        if key or "localhost" in url or "127.0.0.1" in url:
            try:
                endpoint = f"{url}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"

                payload = {
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Context:\n{history}\n\nUser: {user_message}"}
                    ],
                    "temperature": 0.7
                }
                res = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"API returned error ({res.status_code}): {res.text[:250]}"
            except Exception as e:
                return f"Connection error to {provider or 'LLM'}: {str(e)}. Please check your API key or endpoint."

        return (
            f"💡 **AI Key Configuration**: You can chat using any AI provider! "
            "Please paste your API key (Groq, OpenAI, Gemini, OpenRouter, or Ollama) in the **AI Provider & Key** bar above, and I will generate live viral hooks, plan your weekly content calendar, and adapt posts across your channels."
        )

    def _fallback_generation(self, topic: str, platforms: List[str]) -> Dict[str, Any]:
        """Heuristic rule-based templates if offline."""
        result = {}
        for p in platforms:
            if p == "x":
                result["x"] = {"content": f"Most people get {topic} completely wrong.\n\nHere is what you actually need to know: breakdown below #BuildInPublic"}
            elif p == "instagram":
                result["instagram"] = {"content": f"The truth about {topic} that nobody talks about:\n\n1. Stop overcomplicating early steps\n2. Focus on distribution first\n\nSave this Reel for later! #CreatorEconomy #SavyPost"}
            elif p == "linkedin":
                result["linkedin"] = {"content": f"The biggest mistake I see teams make regarding {topic}:\n\n1. Overcomplicating early steps\n2. Ignoring feedback loops\n\nWhat is your strategy?"}
            elif p == "telegram":
                result["telegram"] = {"content": f"<b>New Insight: {topic}</b>\n\nWe just compiled our breakdown. Check out the latest findings!"}
            else:
                result[p] = {"content": f"Updates on {topic}: Moving forward with automated local management."}
        return result
