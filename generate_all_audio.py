#!/usr/bin/env python3
"""
Generate audio greetings for ALL 55 African countries using ElevenLabs TTS API.

Usage:
    source .env
    export ELEVENLABS_API_KEY
    python3 generate_all_audio.py

Models:
  - eleven_multilingual_v2: Arabic, French, English, Portuguese, Spanish
  - eleven_v3: Afrikaans, Swahili, Amharic, Hausa, Yoruba, Somali, Zulu,
               Xhosa, Shona, Lingala, Chichewa, Malagasy, Kinyarwanda, etc.
"""

import os
import sys
import time
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY environment variable.")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "frontend", "public", "audio")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — good multilingual

# fmt: off
GREETINGS = [
    # ── Arabic-speaking (v2, language_code=ar) ──────────────────────────────
    {"iso": "DZA", "file": "algeria_arabic.mp3",      "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الجزائر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم في كل ما تحتاجونه."},
    {"iso": "TCD", "file": "chad_arabic.mp3",          "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في تشاد. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "DJI", "file": "djibouti_arabic.mp3",      "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في جيبوتي. أنا مساعدكم الذكي، وأنا هنا لخدمتكم."},
    {"iso": "EGY", "file": "egypt_arabic.mp3",         "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في مصر. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم. تخيلوا لو كان لكل بلد في أفريقيا وكيل ذكاء اصطناعي يتحدث بلغتكم المحلية."},
    {"iso": "ERI", "file": "eritrea_arabic.mp3",       "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في إريتريا. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "LBY", "file": "libya_arabic.mp3",         "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في ليبيا. أنا مساعدكم الذكي، وأنا هنا لخدمتكم."},
    {"iso": "MRT", "file": "mauritania_arabic.mp3",    "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في موريتانيا. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "MAR", "file": "morocco_arabic.mp3",       "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في المغرب. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "SOM", "file": "somalia_arabic.mp3",       "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الصومال. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "SDN", "file": "sudan_arabic.mp3",         "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في السودان. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "TUN", "file": "tunisia_arabic.mp3",       "model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في تونس. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},
    {"iso": "ESH", "file": "western_sahara_arabic.mp3","model": "v2", "lang": "ar",
     "text": "مرحباً! أهلاً وسهلاً بكم في الصحراء الغربية. أنا مساعدكم الذكي، وأنا هنا لمساعدتكم."},

    # ── French-speaking (v2, language_code=fr) ──────────────────────────────
    {"iso": "BEN", "file": "benin_french.mp3",         "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Bénin. Je suis votre assistant intelligent, et je suis là pour vous aider dans tout ce dont vous avez besoin."},
    {"iso": "BFA", "file": "burkina_faso_french.mp3",  "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Burkina Faso. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "BDI", "file": "burundi_french.mp3",       "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Burundi. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "CMR", "file": "cameroon_french.mp3",      "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Cameroun. Je suis votre assistant intelligent, prêt à vous accompagner."},
    {"iso": "CAF", "file": "central_african_republic_french.mp3", "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en République centrafricaine. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "COM", "file": "comoros_french.mp3",       "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue aux Comores. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "COD", "file": "drc_french.mp3",           "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en République démocratique du Congo. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "COG", "file": "congo_french.mp3",         "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Congo. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "CIV", "file": "ivory_coast_french.mp3",   "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en Côte d'Ivoire. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "GAB", "file": "gabon_french.mp3",         "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Gabon. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "GIN", "file": "guinea_french.mp3",        "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue en Guinée. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "MDG", "file": "madagascar_french.mp3",    "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue à Madagascar. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "MLI", "file": "mali_french.mp3",          "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Mali. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "NER", "file": "niger_french.mp3",         "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Niger. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "RWA", "file": "rwanda_french.mp3",        "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Rwanda. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "SEN", "file": "senegal_french.mp3",       "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Sénégal. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},
    {"iso": "STP", "file": "sao_tome_french.mp3",      "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue à São Tomé-et-Príncipe. Je suis votre assistant intelligent, et je suis là pour vous aider."},
    {"iso": "TGO", "file": "togo_french.mp3",          "model": "v2", "lang": "fr",
     "text": "Bonjour ! Bienvenue au Togo. Je suis votre assistant intelligent, et je suis là pour vous accompagner."},

    # ── English-speaking (v2, language_code=en) ─────────────────────────────
    {"iso": "BWA", "file": "botswana_english.mp3",     "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Botswana. I'm your AI assistant, and I'm here to help you with whatever you need. Imagine every country in Africa with its own intelligent agent, speaking your language."},
    {"iso": "GMB", "file": "gambia_english.mp3",       "model": "v2", "lang": "en",
     "text": "Hello! Welcome to The Gambia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "GHA", "file": "ghana_english.mp3",        "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Ghana. I'm your AI assistant, and I'm here to help you with anything you need. It's wonderful to have you here."},
    {"iso": "KEN", "file": "kenya_english.mp3",        "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Kenya. I'm your AI assistant, and I'm here to help you with whatever you need. Karibu sana!"},
    {"iso": "LSO", "file": "lesotho_english.mp3",      "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Lesotho. I'm your AI assistant, and I'm here to help you."},
    {"iso": "LBR", "file": "liberia_english.mp3",      "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Liberia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "MWI", "file": "malawi_english.mp3",       "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Malawi, the warm heart of Africa. I'm your AI assistant, and I'm here to help you."},
    {"iso": "MUS", "file": "mauritius_english.mp3",    "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Mauritius. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "NGA", "file": "nigeria_english.mp3",      "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Nigeria. I'm your AI assistant, and I'm here to help you. Nigeria is the most populous nation in Africa, and we're glad you're here."},
    {"iso": "SYC", "file": "seychelles_english.mp3",   "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Seychelles. I'm your AI assistant, and I'm here to help you."},
    {"iso": "SLE", "file": "sierra_leone_english.mp3", "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Sierra Leone. I'm your AI assistant, and I'm here to help you with anything you need."},
    {"iso": "SSD", "file": "south_sudan_english.mp3",  "model": "v2", "lang": "en",
     "text": "Hello! Welcome to South Sudan. I'm your AI assistant, and I'm here to help you."},
    {"iso": "SWZ", "file": "eswatini_english.mp3",     "model": "v2", "lang": "en",
     "text": "Hello! Welcome to eSwatini. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "UGA", "file": "uganda_english.mp3",       "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Uganda, the Pearl of Africa. I'm your AI assistant, and I'm here to help you."},
    {"iso": "ZMB", "file": "zambia_english.mp3",       "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Zambia. I'm your AI assistant, and I'm here to help you with whatever you need."},
    {"iso": "ZWE", "file": "zimbabwe_english.mp3",     "model": "v2", "lang": "en",
     "text": "Hello! Welcome to Zimbabwe. I'm your AI assistant, and I'm here to help you."},

    # ── Portuguese-speaking (v2, language_code=pt) ──────────────────────────
    {"iso": "AGO", "file": "angola_portuguese.mp3",    "model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Angola. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo em tudo o que precisar."},
    {"iso": "CPV", "file": "cabo_verde_portuguese.mp3","model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Cabo Verde. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo."},
    {"iso": "GNB", "file": "guinea_bissau_portuguese.mp3","model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo à Guiné-Bissau. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo."},
    {"iso": "MOZ", "file": "mozambique_portuguese.mp3","model": "v2", "lang": "pt",
     "text": "Olá! Bem-vindo a Moçambique. Eu sou o seu assistente inteligente, e estou aqui para ajudá-lo em tudo o que precisar."},

    # ── Spanish-speaking (v2, language_code=es) ─────────────────────────────
    {"iso": "GNQ", "file": "equatorial_guinea_spanish.mp3","model": "v2", "lang": "es",
     "text": "¡Hola! Bienvenido a Guinea Ecuatorial. Soy tu asistente inteligente, y estoy aquí para ayudarte en todo lo que necesites."},

    # ── Afrikaans (v3, auto-detect) ─────────────────────────────────────────
    {"iso": "ZAF", "file": "south_africa_afrikaans.mp3","model": "v3", "lang": None,
     "text": "Hallo! Welkom in Suid-Afrika. Ek is jou slim assistent, en ek is hier om jou te help. Stel jou voor elke land in Afrika het sy eie kunsmatige intelligensie-agent wat jou taal praat."},
    {"iso": "NAM", "file": "namibia_afrikaans.mp3",    "model": "v3", "lang": None,
     "text": "Hallo! Welkom in Namibië. Ek is jou slim assistent, en ek is hier om jou te help met alles wat jy nodig het. Dis wonderlik om jou hier te hê."},

    # ── Swahili (v3, auto-detect) ───────────────────────────────────────────
    {"iso": "TZA", "file": "tanzania_swahili.mp3",     "model": "v3", "lang": None,
     "text": "Habari! Karibu Tanzania. Mimi ni msaidizi wako wa akili bandia, na niko hapa kukusaidia kwa chochote unachohitaji."},

    # ── Amharic (v3, auto-detect) ───────────────────────────────────────────
    {"iso": "ETH", "file": "ethiopia_amharic.mp3",     "model": "v3", "lang": None,
     "text": "ሰላም! ወደ ኢትዮጵያ እንኳን ደህና መጡ። እኔ የእርስዎ የሰው ሰራሽ ብልህ ረዳት ነኝ፣ እና እርስዎን ለመርዳት ዝግጁ ነኝ።"},
]
# fmt: on

MODEL_MAP = {
    "v2": "eleven_multilingual_v2",
    "v3": "eleven_v3",
}


def generate_one(g):
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

    # Skip if already exists
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        print(f"  SKIP {g['file']} (already exists)")
        return True

    print(f"  GEN  {g['file']:45s} [{g['model']}]", end="  ", flush=True)

    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
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
            detail = r.json().get("detail", {}).get("message", r.text[:120])
        except Exception:
            detail = r.text[:120]
        print(f"FAIL ({r.status_code}: {detail})")
        return False


def main():
    print("=" * 65)
    print("  ElevenLabs Audio — All 55 African Countries")
    print("=" * 65)
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Voice:  {VOICE_ID}")
    print(f"  Total:  {len(GREETINGS)} greetings")
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
