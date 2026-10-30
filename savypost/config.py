"""Configuration settings and environment variable management for SavyPost."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Root directory of SavyPost project
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load environment configuration if available
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("SAVYPOST_DB_PATH", str(DATA_DIR / "savypost.db")))
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

RUFLO_MEMORY_PATH = DATA_DIR / "ruflo_memory.json"

DEFAULT_HOST = os.getenv("SAVYPOST_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("SAVYPOST_PORT", "8765"))

# Standard platform character constraints
PLATFORM_LIMITS = {
    "x": 280,
    "bluesky": 300,
    "linkedin": 3000,
    "telegram": 4096,
    "discord": 2000,
    "reddit": 40000,
    "youtube": 5000,
    "instagram": 2200,
    "webhook": 100000,
    "mock": 10000,
}
