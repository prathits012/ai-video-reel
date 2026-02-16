#!/usr/bin/env python3
"""Validate that the AI Reels Bot environment is ready."""

import shutil
import sys
from pathlib import Path


def check_python() -> bool:
    """Ensure Python 3.12+."""
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 12
    print(f"  Python {v.major}.{v.minor}.{v.micro}: {'✓' if ok else '✗ (need 3.12+)'}")
    return ok


def check_ffmpeg() -> bool:
    """Ensure FFmpeg is installed."""
    path = shutil.which("ffmpeg")
    ok = path is not None
    print(f"  FFmpeg: {'✓' if ok else '✗ (run: brew install ffmpeg)'}")
    return ok


def check_deps() -> bool:
    """Ensure required packages are installed."""
    try:
        import moviepy  # noqa: F401
        import requests  # noqa: F401
        import dotenv  # noqa: F401
        import openai  # noqa: F401
        print("  Dependencies (moviepy, requests, dotenv, openai): ✓")
        return True
    except ImportError as e:
        print(f"  Dependencies: ✗ ({e})")
        print("    Run: pip install -r requirements.txt")
        return False


def check_env() -> bool:
    """Ensure .env exists and has required keys."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("  .env file: ✗ (copy .env.example to .env)")
        return False

    from dotenv import load_dotenv
    load_dotenv()
    import os

    pexels = os.getenv("PEXELS_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    pexels_ok = bool(pexels and pexels != "your_pexels_api_key_here")
    openai_ok = bool(openai_key and openai_key != "your_openai_api_key_here")

    print(f"  PEXELS_API_KEY: {'✓' if pexels_ok else '✗'}")
    print(f"  OPENAI_API_KEY: {'✓' if openai_ok else '✗'}")

    return pexels_ok and openai_ok


def main() -> None:
    print("AI Reels Bot - Setup Check\n")
    results = [
        check_python(),
        check_ffmpeg(),
        check_deps(),
        check_env(),
    ]
    if all(results):
        print("\n✓ All checks passed. Ready to build!")
    else:
        print("\n✗ Fix the items above, then run again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
