#!/usr/bin/env python3
"""
Generate audio greetings for African countries using ElevenLabs TTS API.

Usage:
    export ELEVENLABS_API_KEY="your-key-here"
    python generate_audio.py

This generates MP3 files in frontend/public/audio/ for each country greeting.
Uses eleven_multilingual_v2 for Arabic, eleven_v3 for Afrikaans.
"""

import os
import sys
import json
import time
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY environment variable first.")
    print("  export ELEVENLABS_API_KEY='your-key-here'")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "frontend", "public", "audio")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ElevenLabs default voices that work well for multilingual
# "Rachel" (21m00Tcm4TlvDq8ikWAM) - clear, professional female
# "Adam" (pNInz6obpgDQGcFmaJgB) - professional male
# "Antoni" (ErXwobaYiN019PkySvjV) - warm male
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel - good multilingual support

# Country greetings to generate
GREETINGS = [
    # Arabic-speaking countries (use eleven_multilingual_v2)
    {
        "filename": "egypt_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في مصر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم. تخيلوا لو كان لكل بلد في أفريقيا وكيل ذكاء اصطناعي يتحدث بلغتكم المحلية.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Egypt",
    },
    {
        "filename": "algeria_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في الجزائر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم في كل ما تحتاجونه.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Algeria",
    },
    {
        "filename": "libya_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في ليبيا. أنا مساعدكم الذكي، وأنا هنا لخدمتكم.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Libya",
    },
    {
        "filename": "tunisia_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في تونس. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Tunisia",
    },
    {
        "filename": "morocco_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في المغرب. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Morocco",
    },
    {
        "filename": "sudan_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في السودان. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Sudan",
    },
    {
        "filename": "mauritania_arabic.mp3",
        "text": "مرحباً! أهلاً وسهلاً بكم في موريتانيا. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "ar",
        "country": "Mauritania",
    },
    # Afrikaans-speaking countries (use eleven_v3 - only model supporting Afrikaans)
    {
        "filename": "south_africa_afrikaans.mp3",
        "text": "Hallo! Welkom in Suid-Afrika. Ek is jou slim assistent, en ek is hier om jou te help. Stel jou voor elke land in Afrika het sy eie kunsmatige intelligensie-agent wat jou taal praat.",
        "model_id": "eleven_v3",
        "language_code": "afr",
        "country": "South Africa",
    },
    {
        "filename": "namibia_afrikaans.mp3",
        "text": "Hallo! Welkom in Namibië. Ek is jou slim assistent, en ek is hier om jou te help met alles wat jy nodig het. Dis wonderlik om jou hier te hê.",
        "model_id": "eleven_v3",
        "language_code": "afr",
        "country": "Namibia",
    },
]


def generate_audio(greeting):
    """Generate a single audio file using ElevenLabs TTS API."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    # v3 model requires stability in {0.0, 0.5, 1.0} and doesn't support style/similarity_boost
    # v3 also doesn't support explicit language_code for Afrikaans — auto-detect works fine
    is_v3 = greeting["model_id"] == "eleven_v3"
    voice_settings = (
        {"stability": 0.5}
        if is_v3
        else {"stability": 0.6, "similarity_boost": 0.7, "style": 0.3}
    )

    body = {
        "text": greeting["text"],
        "model_id": greeting["model_id"],
        "voice_settings": voice_settings,
    }

    # Add language_code if specified (skip for v3 as it uses auto-detect)
    if greeting.get("language_code") and not is_v3:
        body["language_code"] = greeting["language_code"]

    print(f"  Generating: {greeting['country']} ({greeting['model_id']})...", end=" ", flush=True)

    response = requests.post(url, headers=headers, json=body, timeout=30)

    if response.status_code == 200:
        output_path = os.path.join(OUTPUT_DIR, greeting["filename"])
        with open(output_path, "wb") as f:
            f.write(response.content)
        size_kb = len(response.content) / 1024
        print(f"OK ({size_kb:.0f} KB)")
        return True
    else:
        print(f"FAILED (HTTP {response.status_code})")
        try:
            err = response.json()
            print(f"    Error: {err.get('detail', {}).get('message', str(err))}")
        except Exception:
            print(f"    Response: {response.text[:200]}")
        return False


def main():
    print("=" * 60)
    print("ElevenLabs Audio Generation for Africa Audio Exploration")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Voice ID: {VOICE_ID}")
    print(f"Greetings to generate: {len(GREETINGS)}")
    print()

    success = 0
    failed = 0

    for greeting in GREETINGS:
        if generate_audio(greeting):
            success += 1
        else:
            failed += 1
        # Small delay to avoid rate limiting
        time.sleep(0.5)

    print()
    print(f"Done! {success} succeeded, {failed} failed.")
    print(f"Audio files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
