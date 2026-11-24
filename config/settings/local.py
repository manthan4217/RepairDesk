"""Local development settings. Reads variables from the project .env file."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(BASE_DIR / ".env")

from .base import *  # noqa: E402, F403
