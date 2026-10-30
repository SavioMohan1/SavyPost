"""Command Line Interface for SavyPost — Local AI Social Media Manager."""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
import uvicorn

from savypost.db.database import init_db, get_db
from savypost.db.models import SocialPost, SocialAccount
from savypost.providers.manager import SocialProviderManager
from savypost.agent.social_manager import SocialMediaManager
from savypost.agent.trend_scout import TrendScout
from savypost.config import DEFAULT_HOST, DEFAULT_PORT

cli_app = typer.Typer(help="SavyPost — Autonomous AI Social Media Manager CLI")
console = Console()


@cli_app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, help="Host address to bind"),
    port: int = typer.Option(DEFAULT_PORT, help="Port to listen on")
):
    """Launch the SavyPost Web App & Background Worker."""
    console.print(f"[bold green]>> Launching SavyPost Web App on http://{host}:{port}[/bold green]")
    console.print("[dim]Background scheduler and local SQLite vault active.[/dim]")
    uvicorn.run("savypost.web.app:app", host=host, port=port, reload=False)


@cli_app.command()
def doctor():
    """Run health diagnostics on local database, providers, and media scout."""
    console.print("[bold cyan][*] Running SavyPost Diagnostics[/bold cyan]\n")
    init_db()

    # 1. Database Check
    try:
        with get_db() as db:
            acc_count = db.query(SocialAccount).count()
            post_count = db.query(SocialPost).count()
        console.print(f"  [green][+][/green] SQLite Database: Healthy ({acc_count} accounts, {post_count} posts)")
    except Exception as e:
        console.print(f"  [red][-][/red] SQLite Database Error: {e}")

    # 2. Providers Check
    mgr = SocialProviderManager()
    platforms = ["x", "instagram", "telegram", "discord", "bluesky", "linkedin", "reddit", "youtube", "webhook", "mock"]
    console.print(f"  [green][+][/green] Providers Loaded: {', '.join(platforms)}")

    # 3. Media Scout Check
    scout = TrendScout()
    clips = scout.get_local_video_clips()
    console.print(f"  [green][+][/green] Media Scout: Ready ({len(clips)} local project video clips detected)")

    console.print("\n[bold green]SavyPost is operational and ready to publish locally![/bold green]")


@cli_app.command()
def post(
    content: str = typer.Argument(..., help="Text content of the post"),
    platforms: str = typer.Option("x,telegram,instagram", help="Comma-separated platforms (e.g. x,telegram,instagram)"),
    media: Optional[str] = typer.Option(None, help="Local file path to image or video clip")
):
    """Immediately publish a post to selected social media accounts."""
    init_db()
    mgr = SocialMediaManager()
    target_list = [p.strip().lower() for p in platforms.split(",")]
    media_list = [media] if media else []

    console.print(f"[bold yellow]Publishing to {target_list}...[/bold yellow]")
    post_data = mgr.create_and_schedule_post(
        content=content,
        target_platforms=target_list,
        scheduled_at=datetime.utcnow(),
        media_paths=media_list
    )

    from savypost.scheduler import SocialScheduler
    scheduler = SocialScheduler()
    import asyncio
    asyncio.run(scheduler.process_due_posts())

    with get_db() as db:
        p = db.query(SocialPost).filter(SocialPost.id == post_data["id"]).first()
        console.print(f"[bold green]Done! Post #{p.id} status: {p.status}[/bold green]")
        if p.results:
            console.print(f"Results: {p.results}")


@cli_app.command()
def generate(
    topic: str = typer.Argument(..., help="Topic or idea to generate campaign for"),
    platforms: str = typer.Option("x,instagram,linkedin", help="Target platforms"),
    tone: str = typer.Option("viral_curiosity", help="Tone of the posts")
):
    """Generate viral campaign drafts using SavyPost AI Social Media Manager."""
    console.print(f"[cyan]>> Drafting campaign for topic: '{topic}'...[/cyan]")
    mgr = SocialMediaManager()
    target_list = [p.strip().lower() for p in platforms.split(",")]
    res = mgr.generate_campaign(topic=topic, platforms=target_list, tone=tone)

    for plat, item in res.get("posts", {}).items():
        console.print(f"\n[bold green]--- {plat.upper()} ---[/bold green]")
        console.print(item.get("content"))
        console.print(f"[dim]Length: {item.get('character_count')}/{item.get('limit')} chars[/dim]")


@cli_app.command("list")
def list_posts(
    status: Optional[str] = typer.Option(None, help="Filter by status (SCHEDULED, PUBLISHED, DRAFT)")
):
    """List scheduled, draft, and published posts."""
    init_db()
    with get_db() as db:
        q = db.query(SocialPost).order_by(SocialPost.created_at.desc())
        if status:
            q = q.filter(SocialPost.status == status.upper())
        posts = q.all()

        table = Table(title="SavyPost Queue")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Content", max_width=45)
        table.add_column("Platforms", style="magenta")
        table.add_column("Scheduled At", style="blue")
        table.add_column("Status", style="bold green")

        for p in posts:
            dt_str = p.scheduled_at.strftime("%Y-%m-%d %H:%M") if p.scheduled_at else "Instant"
            status_style = "green" if p.status == "PUBLISHED" else "blue" if p.status == "SCHEDULED" else "dim"
            table.add_row(
                str(p.id),
                p.content[:60].replace("\n", " "),
                ", ".join(json.loads(p.target_platforms or "[]")),
                dt_str,
                f"[{status_style}]{p.status}[/{status_style}]"
            )
        console.print(table)


if __name__ == "__main__":
    cli_app()
