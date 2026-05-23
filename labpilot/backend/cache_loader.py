"""
Provision the 13 LabPilot Managed Agents.

In V4 this file was a Gemini Context Cache loader. With Managed Agents we
instead pre-create the 13 saved agents (each with its own SKILL.md sources).
Run once at hackathon start to warm everything up.

Usage:
  python cache_loader.py
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from gemini_client import ensure_agents  # noqa: E402


def main() -> None:
    print("Provisioning LabPilot managed agents...")
    ids = ensure_agents()
    print(f"Done. {len(ids)} agents available:")
    for agent_id in ids:
        print(f"  - {agent_id}")


if __name__ == "__main__":
    main()
