#!/usr/bin/env python3
"""
Generate MULTI-LANGUAGE audio greetings for African countries.

This script generates only the NEW audio files needed for the multi-language
click-cycling feature. Existing files (the original 55) are skipped.

Generates into BOTH directories:
  - frontend/public/audio/          (Rachel one-voice)
  - frontend/public/audio/local/    (regional African voices)

Usage:
    source .env && export ELEVENLABS_API_KEY
    python3 generate_multilang_audio.py
    python3 generate_multilang_audio.py --local   # local voices only
    python3 generate_multilang_audio.py --one      # one voice only
"""

import os
import sys
import time
import argparse
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY environment variable.")
    sys.exit(1)

BASE_DIR = os.path.dirname(__file__)
ONE_VOICE_DIR = os.path.join(BASE_DIR, "frontend", "public", "audio")
LOCAL_VOICE_DIR = os.path.join(BASE_DIR, "frontend", "public", "audio", "local")
os.makedirs(ONE_VOICE_DIR, exist_ok=True)
os.makedirs(LOCAL_VOICE_DIR, exist_ok=True)

# Rachel — good multilingual one-voice
RACHEL_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# Regional voice assignments (same as generate_local_audio.py)
REGIONAL_VOICES = {
    "north_africa":      "9SPZl4Mlgwj7QT4gVprb",   # Adam - Egyptian Arabic male
    "west_africa_en":    "JMwQvjJt08OhYlPBWeyc",   # Tolani - Nigerian female
    "west_africa_fr":    "4SFJvuIUvxaPLgk8FoK3",   # Alimata - African French female
    "east_africa":       "uLfPT5jUO3X81OwnftBP",   # Keith Muoki - Kenyan male
    "southern_africa":   "ODKfF1EGCDiD1nUTJmqW",   # Mark Williams - South African male
    "portuguese_africa": "FbFkkfp4Iv6U5Q1WC4C2",   # Marcos - Angolan Portuguese male
    "horn_africa":       "Yru1AaCztNSYkMNCbM1k",   # Mwika Kayange - African male
    "spanish_africa":    "21m00Tcm4TlvDq8ikWAM",   # Rachel (fallback)
}

MODEL_MAP = {
    "v2": "eleven_multilingual_v2",
    "v3": "eleven_v3",
}

# fmt: off
# ─────────────────────────────────────────────────────────────────────────────
# New audio entries — only the ~42 files that DON'T already exist.
# Each entry needs: file, model, lang (or None for v3 auto-detect), text,
# and region (for local voice assignment).
# ─────────────────────────────────────────────────────────────────────────────
GREETINGS = [
    # ── Arabic-block secondary languages ─────────────────────────────────────
    {"file": "algeria_french.mp3",       "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue en Algérie. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "chad_french.mp3",          "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue au Tchad. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "djibouti_french.mp3",      "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue à Djibouti. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "egypt_english.mp3",        "model": "v2", "lang": "en", "region": "north_africa",
     "text": "Hello! Welcome to Egypt. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"file": "eritrea_english.mp3",      "model": "v2", "lang": "en", "region": "horn_africa",
     "text": "Hello! Welcome to Eritrea. I'm your AI assistant, and I'm here to help you."},
    {"file": "libya_english.mp3",        "model": "v2", "lang": "en", "region": "north_africa",
     "text": "Hello! Welcome to Libya. I'm your AI assistant, and I'm here to help you."},
    {"file": "mauritania_french.mp3",    "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue en Mauritanie. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "morocco_french.mp3",       "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue au Maroc. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "somalia_somali.mp3",       "model": "v3", "lang": None, "region": "horn_africa",
     "text": "Salaan! Ku soo dhawoow Soomaaliya. Waxaan ahay kaaliyahaaga caqliga gaarka ah."},
    {"file": "sudan_english.mp3",        "model": "v2", "lang": "en", "region": "north_africa",
     "text": "Hello! Welcome to Sudan. I'm your AI assistant, and I'm here to help you."},
    {"file": "tunisia_french.mp3",       "model": "v2", "lang": "fr", "region": "north_africa",
     "text": "Bonjour ! Bienvenue en Tunisie. Je suis votre assistant intelligent, et je suis là pour vous aider."},

    # ── French-block secondary languages ─────────────────────────────────────
    {"file": "benin_yoruba.mp3",         "model": "v3", "lang": None, "region": "west_africa_en",
     "text": "Ẹ kú àbọ̀! Ẹ kú ilé Benin. Mo jẹ́ olùrànlọ́wọ́ yín tó gbọ́n."},
    {"file": "burundi_kinyarwanda.mp3",  "model": "v3", "lang": None, "region": "east_africa",
     "text": "Muraho! Murakaza neza mu Burundi. Ndi umufasha wawe w'ubwenge bw'ikoranabuhanga."},
    {"file": "cameroon_english.mp3",     "model": "v2", "lang": "en", "region": "west_africa_en",
     "text": "Hello! Welcome to Cameroon. I'm your AI assistant, and I'm here to help you."},
    {"file": "comoros_arabic.mp3",       "model": "v2", "lang": "ar", "region": "north_africa",
     "text": "مرحباً! أهلاً وسهلاً بكم في جزر القمر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"file": "drc_lingala.mp3",          "model": "v3", "lang": None, "region": "west_africa_fr",
     "text": "Mbote! Boyei malamu na République démocratique ya Congo. Nazali mosungi na yo ya mayele."},
    {"file": "drc_swahili.mp3",          "model": "v3", "lang": None, "region": "east_africa",
     "text": "Habari! Karibu Jamhuri ya Kidemokrasia ya Kongo. Mimi ni msaidizi wako wa akili bandia."},
    {"file": "congo_lingala.mp3",        "model": "v3", "lang": None, "region": "west_africa_fr",
     "text": "Mbote! Boyei malamu na Congo. Nazali mosungi na yo ya mayele."},
    {"file": "madagascar_malagasy.mp3",  "model": "v3", "lang": None, "region": "east_africa",
     "text": "Manao ahoana! Tongasoa eto Madagasikara. Izaho no mpanampy anao amin'ny faharanitan-tsaina."},
    {"file": "niger_hausa.mp3",          "model": "v3", "lang": None, "region": "west_africa_en",
     "text": "Sannu! Barka da zuwa Niger. Ni ne mataimakinka na fasaha."},
    {"file": "rwanda_kinyarwanda.mp3",   "model": "v3", "lang": None, "region": "east_africa",
     "text": "Muraho! Murakaza neza mu Rwanda. Ndi umufasha wawe w'ubwenge bw'ikoranabuhanga."},
    {"file": "rwanda_english.mp3",       "model": "v2", "lang": "en", "region": "east_africa",
     "text": "Hello! Welcome to Rwanda. I'm your AI assistant, and I'm here to help you."},
    {"file": "sao_tome_portuguese.mp3",  "model": "v2", "lang": "pt", "region": "portuguese_africa",
     "text": "Olá! Bem-vindo a São Tomé e Príncipe. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo."},

    # ── English-block secondary languages ────────────────────────────────────
    {"file": "botswana_setswana.mp3",    "model": "v3", "lang": None, "region": "southern_africa",
     "text": "Dumela! O amogetswe mo Botswana. Ke mothusi wa gago wa botlhale."},
    {"file": "kenya_swahili.mp3",        "model": "v3", "lang": None, "region": "east_africa",
     "text": "Habari! Karibu Kenya. Mimi ni msaidizi wako wa akili bandia, na niko hapa kukusaidia."},
    {"file": "lesotho_sesotho.mp3",      "model": "v3", "lang": None, "region": "southern_africa",
     "text": "Lumela! Rea u amohela Lesotho. Ke mothusi oa hau oa bohlale."},
    {"file": "malawi_chichewa.mp3",      "model": "v3", "lang": None, "region": "east_africa",
     "text": "Moni! Takulandirani ku Malawi, mtima wofunda wa Africa. Ndine wothandiza wanu wanzeru."},
    {"file": "mauritius_french.mp3",     "model": "v2", "lang": "fr", "region": "southern_africa",
     "text": "Bonjour ! Bienvenue à Maurice. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "nigeria_yoruba.mp3",       "model": "v3", "lang": None, "region": "west_africa_en",
     "text": "Ẹ kú àbọ̀! Ẹ kú ilé Nigeria. Mo jẹ́ olùrànlọ́wọ́ yín tó gbọ́n, mo sì wà níbí láti ràn yín lọ́wọ́."},
    {"file": "nigeria_hausa.mp3",        "model": "v3", "lang": None, "region": "west_africa_en",
     "text": "Sannu! Barka da zuwa Nigeria. Ni ne mataimakinka na fasaha, kuma ina nan don taimaka maka."},
    {"file": "seychelles_french.mp3",    "model": "v2", "lang": "fr", "region": "southern_africa",
     "text": "Bonjour ! Bienvenue aux Seychelles. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "south_sudan_arabic.mp3",   "model": "v2", "lang": "ar", "region": "north_africa",
     "text": "مرحباً! أهلاً وسهلاً بكم في جنوب السودان. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"file": "uganda_swahili.mp3",       "model": "v3", "lang": None, "region": "east_africa",
     "text": "Habari! Karibu Uganda, Lulu ya Afrika. Mimi ni msaidizi wako wa akili bandia."},
    {"file": "zimbabwe_shona.mp3",       "model": "v3", "lang": None, "region": "southern_africa",
     "text": "Mhoro! Titambire kuZimbabwe. Ndiri mubatsiri wenyu wenjere."},

    # ── Portuguese-block secondary languages ─────────────────────────────────
    {"file": "angola_lingala.mp3",       "model": "v3", "lang": None, "region": "portuguese_africa",
     "text": "Mbote! Boyei malamu na Angola. Nazali mosungi na yo ya mayele."},
    {"file": "mozambique_swahili.mp3",   "model": "v3", "lang": None, "region": "east_africa",
     "text": "Habari! Karibu Msumbiji. Mimi ni msaidizi wako wa akili bandia."},

    # ── Other secondary languages ────────────────────────────────────────────
    {"file": "equatorial_guinea_french.mp3", "model": "v2", "lang": "fr", "region": "west_africa_fr",
     "text": "Bonjour ! Bienvenue en Guinée équatoriale. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"file": "south_africa_isixhosa.mp3","model": "v3", "lang": None, "region": "southern_africa",
     "text": "Molo! Wamkelekile eMzantsi Afrika. Ndingumncedisi wakho okrelekrele."},
    {"file": "south_africa_afrikaans.mp3","model": "v3", "lang": None, "region": "southern_africa",
     "text": "Hallo! Welkom in Suid-Afrika. Ek is jou slim assistent, en ek is hier om jou te help."},
    {"file": "namibia_english.mp3",      "model": "v2", "lang": "en", "region": "southern_africa",
     "text": "Hello! Welcome to Namibia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"file": "tanzania_english.mp3",     "model": "v2", "lang": "en", "region": "east_africa",
     "text": "Hello! Welcome to Tanzania. I'm your AI assistant, and I'm here to help you."},
    {"file": "ethiopia_english.mp3",     "model": "v2", "lang": "en", "region": "horn_africa",
     "text": "Hello! Welcome to Ethiopia. I'm your AI assistant, and I'm here to help you."},
]
# fmt: on


def generate_one(g, voice_id, output_dir, label=""):
    """Generate a single audio file."""
    model_id = MODEL_MAP[g["model"]]
    is_v3 = g["model"] == "v3"

    voice_settings = (
        {"stability": 0.5}
        if is_v3
        else {"stability": 0.6, "similarity_boost": 0.7, "style": 0.3}
    )

    body = {
        "text": g["text"],
        "model_id": model_id,
        "voice_settings": voice_settings,
    }
    if g.get("lang") and not is_v3:
        body["language_code"] = g["lang"]

    outpath = os.path.join(output_dir, g["file"])

    # Skip if already exists and is >1KB
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        print(f"  SKIP {label}{g['file']}")
        return True

    print(f"  GEN  {label}{g['file']:45s} [{g['model']}]", end="  ", flush=True)

    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json=body,
            timeout=60,
        )
    except Exception as e:
        print(f"ERROR ({e})")
        return False

    if r.status_code == 200:
        with open(outpath, "wb") as f:
            f.write(r.content)
        print(f"OK ({len(r.content) // 1024} KB)")
        return True
    else:
        detail = ""
        try:
            detail = r.json().get("detail", {}).get("message", r.text[:150])
        except Exception:
            detail = r.text[:150]
        print(f"FAIL ({r.status_code}: {detail})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate multi-language audio files")
    parser.add_argument("--one", action="store_true", help="Generate one-voice (Rachel) only")
    parser.add_argument("--local", action="store_true", help="Generate local voices only")
    args = parser.parse_args()

    # Default: generate both
    do_one = not args.local or args.one
    do_local = not args.one or args.local
    if args.one and args.local:
        do_one = do_local = True

    print("=" * 70)
    print("  ElevenLabs Multi-Language Audio Generator")
    print("=" * 70)
    print(f"  New files to generate: {len(GREETINGS)}")
    if do_one:
        print(f"  One-voice dir:  {ONE_VOICE_DIR}")
    if do_local:
        print(f"  Local-voice dir: {LOCAL_VOICE_DIR}")
    print()

    ok, fail = 0, 0

    if do_one:
        print("─── One Voice (Rachel) ─────────────────────────────────────────────")
        for g in GREETINGS:
            if generate_one(g, RACHEL_VOICE_ID, ONE_VOICE_DIR, label="[one]  "):
                ok += 1
            else:
                fail += 1
            time.sleep(0.3)
        print()

    if do_local:
        print("─── Local Voices (Regional) ────────────────────────────────────────")
        for g in GREETINGS:
            voice_id = REGIONAL_VOICES[g["region"]]
            if generate_one(g, voice_id, LOCAL_VOICE_DIR, label="[local] "):
                ok += 1
            else:
                fail += 1
            time.sleep(0.3)
        print()

    print(f"  Done: {ok} succeeded, {fail} failed")
    print(f"  Total attempts: {ok + fail}")


if __name__ == "__main__":
    main()
