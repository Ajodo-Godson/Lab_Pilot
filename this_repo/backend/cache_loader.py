from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def main() -> None:
    # Placeholder: replace with Gemini Context Cache creation at hackathon start.
    print("CACHE_NAME=placeholder-cache-name")
    print("Replace backend/cache_loader.py with real Gemini Context Cache setup.")


if __name__ == "__main__":
    main()
