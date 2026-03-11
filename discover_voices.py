#!/usr/bin/env python3
"""
Discover ElevenLabs voices suitable for African regional accents.
Queries the shared voice library API and prints candidates per region.

Usage:
    source .env && export ELEVENLABS_API_KEY
    python3 discover_voices.py
"""

import os
import sys
import json
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY"); sys.exit(1)

HEADERS = {"xi-api-key": API_KEY}
BASE = "https://api.elevenlabs.io/v1"


def search_voices(accent=None, language=None, gender=None, search=None, page_size=20):
    params = {"page_size": page_size}
    if accent: params["accent"] = accent
    if language: params["language"] = language
    if gender: params["gender"] = gender
    if search: params["search"] = search

    r = requests.get(f"{BASE}/shared-voices", headers=HEADERS, params=params, timeout=15)
    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
        return []
    data = r.json()
    return data.get("voices", [])


def print_voices(voices, label):
    print(f"\n{'='*60}")
    print(f"  {label} ({len(voices)} results)")
    print(f"{'='*60}")
    for v in voices[:10]:
        name = v.get("name", "?")
        vid = v.get("voice_id", "?")
        accent = v.get("accent", "?")
        gender = v.get("gender", "?")
        age = v.get("age", "?")
        lang = v.get("language", "?")
        desc = v.get("description", "")[:80]
        use_count = v.get("cloned_by_count", 0)
        print(f"  {name:30s}  id={vid}")
        print(f"    accent={accent}, gender={gender}, age={age}, lang={lang}, uses={use_count}")
        if desc:
            print(f"    desc: {desc}")
        print()


def main():
    print("ElevenLabs Voice Discovery for African Regions")
    print("=" * 60)

    searches = [
        ("African accent (English)", {"accent": "african", "language": "en"}),
        ("African accent (general)", {"accent": "african"}),
        ("Nigerian accent", {"accent": "nigerian"}),
        ("South African accent", {"accent": "south african"}),
        ("Search: 'Nigerian'", {"search": "Nigerian", "language": "en"}),
        ("Search: 'African'", {"search": "African", "language": "en"}),
        ("Search: 'Kenyan'", {"search": "Kenyan"}),
        ("Search: 'South African'", {"search": "South African"}),
        ("Arabic voices", {"language": "ar"}),
        ("French African", {"accent": "african", "language": "fr"}),
        ("Search: 'African French'", {"search": "African French"}),
        ("Portuguese voices", {"language": "pt"}),
        ("Search: 'Ethiopian'", {"search": "Ethiopian"}),
        ("Search: 'Swahili'", {"search": "Swahili"}),
    ]

    all_found = {}
    for label, params in searches:
        voices = search_voices(**params)
        print_voices(voices, label)
        for v in voices:
            all_found[v["voice_id"]] = v

    print("\n" + "=" * 60)
    print(f"  TOTAL UNIQUE VOICES FOUND: {len(all_found)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
