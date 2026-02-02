#!/usr/bin/env python3
"""
Generate LOCAL VOICE audio greetings — region-appropriate African voices.
These go into frontend/public/audio/local/ alongside the existing "one voice" set.

Usage:
    source .env && export ELEVENLABS_API_KEY
    python3 generate_local_audio.py
"""

import os
import sys
import time
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY"); sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "frontend", "public", "audio", "local")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# Regional voice assignments
# =============================================================================

REGIONAL_VOICES = {
    "north_africa":      "9SPZl4Mlgwj7QT4gVprb",   # Adam - Egyptian Arabic male
    "west_africa_en":    "JMwQvjJt08OhYlPBWeyc",   # Tolani - Nigerian female (3663 uses)
    "west_africa_fr":    "4SFJvuIUvxaPLgk8FoK3",   # Alimata - African French female (2071 uses)
    "east_africa":       "uLfPT5jUO3X81OwnftBP",   # Keith Muoki - Kenyan male (900 uses)
    "southern_africa":   "ODKfF1EGCDiD1nUTJmqW",   # Mark Williams - South African male (2051 uses)
    "portuguese_africa": "FbFkkfp4Iv6U5Q1WC4C2",   # Marcos - Angolan Portuguese male (2034 uses)
    "horn_africa":       "Yru1AaCztNSYkMNCbM1k",   # Mwika Kayange - Malawian/African male (1512 uses)
    "spanish_africa":    "21m00Tcm4TlvDq8ikWAM",   # Rachel (fallback — no African Spanish voice)
}

# fmt: off
GREETINGS = [
    # ── North Africa (Arabic) — Adam, Egyptian voice ────────────────────────
    {"iso": "DZA", "file": "algeria_arabic.mp3",       "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الجزائر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم في كل ما تحتاجونه."},
    {"iso": "TCD", "file": "chad_arabic.mp3",           "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في تشاد. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "DJI", "file": "djibouti_arabic.mp3",       "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في جيبوتي. أنا مساعدكم الذكي، وأنا هنا لخدمتكم."},
    {"iso": "EGY", "file": "egypt_arabic.mp3",          "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في مصر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم. تخيلوا لو كان لكل بلد في أفريقيا وكيل ذكاء اصطناعي يتحدث بلغتكم المحلية."},
    {"iso": "ERI", "file": "eritrea_arabic.mp3",        "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في إريتريا. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "LBY", "file": "libya_arabic.mp3",          "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في ليبيا. أنا مساعدكم الذكي، وأنا هنا لخدمتكم."},
    {"iso": "MRT", "file": "mauritania_arabic.mp3",     "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في موريتانيا. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "MAR", "file": "morocco_arabic.mp3",        "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في المغرب. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "SOM", "file": "somalia_arabic.mp3",        "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الصومال. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "SDN", "file": "sudan_arabic.mp3",          "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في السودان. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "TUN", "file": "tunisia_arabic.mp3",        "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في تونس. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "ESH", "file": "western_sahara_arabic.mp3", "region": "north_africa", "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الصحراء الغربية. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},

    # ── West/Central Africa French — Alimata, African French female ─────────
    {"iso": "BEN", "file": "benin_french.mp3",          "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Bénin. Je suis votre assistant intelligent, et je suis là pour vous aider dans tout ce dont vous avez besoin."},
    {"iso": "BFA", "file": "burkina_faso_french.mp3",   "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Burkina Faso. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "BDI", "file": "burundi_french.mp3",        "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Burundi. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "CMR", "file": "cameroon_french.mp3",       "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Cameroun. Je suis votre assistant intelligent, prêt à vous accompagner."},
    {"iso": "CAF", "file": "central_african_republic_french.mp3", "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en République centrafricaine. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "COM", "file": "comoros_french.mp3",        "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue aux Comores. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "COD", "file": "drc_french.mp3",            "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en République démocratique du Congo. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "COG", "file": "congo_french.mp3",          "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Congo. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "CIV", "file": "ivory_coast_french.mp3",    "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en Côte d'Ivoire. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "GAB", "file": "gabon_french.mp3",          "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Gabon. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "GIN", "file": "guinea_french.mp3",         "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en Guinée. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "MDG", "file": "madagascar_french.mp3",     "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue à Madagascar. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "MLI", "file": "mali_french.mp3",           "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Mali. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "NER", "file": "niger_french.mp3",          "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Niger. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "RWA", "file": "rwanda_french.mp3",         "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Rwanda. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "SEN", "file": "senegal_french.mp3",        "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Sénégal. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "STP", "file": "sao_tome_french.mp3",       "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue à São Tomé-et-Príncipe. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "TGO", "file": "togo_french.mp3",           "region": "west_africa_fr", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Togo. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},

    # ── West Africa English — Tolani, Nigerian female ───────────────────────
    {"iso": "GHA", "file": "ghana_english.mp3",         "region": "west_africa_en", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Ghana. I'm your AI assistant, and I'm here to help you with anything you need. It's wonderful to have you here."},
    {"iso": "GMB", "file": "gambia_english.mp3",        "region": "west_africa_en", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to The Gambia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "LBR", "file": "liberia_english.mp3",       "region": "west_africa_en", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Liberia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "NGA", "file": "nigeria_english.mp3",       "region": "west_africa_en", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Nigeria. I'm your AI assistant, and I'm here to help you. Nigeria is the most populous nation in Africa, and we're glad you're here."},
    {"iso": "SLE", "file": "sierra_leone_english.mp3",  "region": "west_africa_en", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Sierra Leone. I'm your AI assistant, and I'm here to help you with anything you need."},

    # ── East Africa — Keith Muoki, Kenyan male ──────────────────────────────
    {"iso": "KEN", "file": "kenya_english.mp3",         "region": "east_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Kenya. I'm your AI assistant, and I'm here to help you with whatever you need. Karibu sana!"},
    {"iso": "UGA", "file": "uganda_english.mp3",        "region": "east_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Uganda, the Pearl of Africa. I'm your AI assistant, and I'm here to help you."},
    {"iso": "TZA", "file": "tanzania_swahili.mp3",      "region": "east_africa", "model": "v3", "lang": None,
     "text": "Habari! Karibu Tanzania. Mimi ni msaidizi wako wa akili bandia, na niko hapa kukusaidia kwa chochote unachohitaji."},
    {"iso": "SSD", "file": "south_sudan_english.mp3",   "region": "east_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to South Sudan. I'm your AI assistant, and I'm here to help you."},
    {"iso": "MWI", "file": "malawi_english.mp3",        "region": "east_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Malawi, the warm heart of Africa. I'm your AI assistant, and I'm here to help you."},

    # ── Southern Africa — Mark Williams, South African male ─────────────────
    {"iso": "ZAF", "file": "south_africa_afrikaans.mp3","region": "southern_africa", "model": "v3", "lang": None,
     "text": "Hallo! Welkom in Suid-Afrika. Ek is jou slim assistent, en ek is hier om jou te help. Stel jou voor elke land in Afrika het sy eie kunsmatige intelligensie-agent wat jou taal praat."},
    {"iso": "NAM", "file": "namibia_afrikaans.mp3",     "region": "southern_africa", "model": "v3", "lang": None,
     "text": "Hallo! Welkom in Namibië. Ek is jou slim assistent, en ek is hier om jou te help met alles wat jy nodig het. Dis wonderlik om jou hier te hê."},
    {"iso": "BWA", "file": "botswana_english.mp3",      "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Botswana. I'm your AI assistant, and I'm here to help you with whatever you need. Imagine every country in Africa with its own intelligent agent, speaking your language."},
    {"iso": "ZMB", "file": "zambia_english.mp3",        "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Zambia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "ZWE", "file": "zimbabwe_english.mp3",      "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Zimbabwe. I'm your AI assistant, and I'm here to help you."},
    {"iso": "LSO", "file": "lesotho_english.mp3",       "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Lesotho. I'm your AI assistant, and I'm here to help you."},
    {"iso": "SWZ", "file": "eswatini_english.mp3",      "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to eSwatini. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "MUS", "file": "mauritius_english.mp3",     "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Mauritius. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "SYC", "file": "seychelles_english.mp3",    "region": "southern_africa", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Seychelles. I'm your AI assistant, and I'm here to help you."},

    # ── Portuguese Africa — Marcos, Angolan accent ──────────────────────────
    {"iso": "AGO", "file": "angola_portuguese.mp3",     "region": "portuguese_africa", "model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Angola. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo em tudo o que precisar."},
    {"iso": "CPV", "file": "cabo_verde_portuguese.mp3", "region": "portuguese_africa", "model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Cabo Verde. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo."},
    {"iso": "GNB", "file": "guinea_bissau_portuguese.mp3","region": "portuguese_africa", "model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo à Guiné-Bissau. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo."},
    {"iso": "MOZ", "file": "mozambique_portuguese.mp3", "region": "portuguese_africa", "model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Moçambique. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo em tudo o que precisar."},

    # ── Spanish Africa — Rachel fallback ────────────────────────────────────
    {"iso": "GNQ", "file": "equatorial_guinea_spanish.mp3","region": "spanish_africa", "model": "v2", "lang": "es",
     "text": "¡Hola! Bienvenido a Guinea Ecuatorial. Soy tu asistente inteligente, y estoy aquí para ayudarte en todo lo que necesites."},

    # ── Horn of Africa — Mwika Kayange, African male ───────────────────────
    {"iso": "ETH", "file": "ethiopia_amharic.mp3",      "region": "horn_africa", "model": "v3", "lang": None,
     "text": "ሰላም! ወደ ኢትዮጵያ እንኳን ደህና መጡ። እኔ የእርስዎ የሰው ሰራሽ ብልህ ረዳት ነኝ፣ እና እርስዎን ለመርዳት ዝግጁ ነኝ።"},
]
# fmt: on

MODEL_MAP = {
    "v2": "eleven_multilingual_v2",
    "v3": "eleven_v3",
}


def generate_one(g):
    region = g["region"]
    voice_id = REGIONAL_VOICES[region]
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

    outpath = os.path.join(OUTPUT_DIR, g["file"])

    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        print(f"  SKIP {g['file']}")
        return True

    print(f"  GEN  {g['file']:45s} [{region:20s}] voice={voice_id[:12]}...", end="  ", flush=True)

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
    print("=" * 70)
    print("  ElevenLabs Local Voices — Regional African Voices")
    print("=" * 70)
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Greetings: {len(GREETINGS)}")
    print(f"  Regions: {len(REGIONAL_VOICES)}")
    print()
    for region, vid in REGIONAL_VOICES.items():
        print(f"    {region:25s} → {vid}")
    print()

    ok, fail = 0, 0
    for g in GREETINGS:
        if generate_one(g):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)

    print()
    print(f"  Done: {ok} succeeded, {fail} failed")
    print(f"  Files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
