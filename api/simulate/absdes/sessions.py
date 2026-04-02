"""Vercel serverless function: GET /api/simulate/absdes/sessions

Returns list of pre-computed demo simulation sessions.
"""

import json
from http.server import BaseHTTPRequestHandler

PRECOMPUTED_SESSIONS = [
    {
        "session_id": "nigeria-covid-natural",
        "label": "Nigeria \u2013 COVID-19 Natural Spread",
        "description": "COVID-19 spreading naturally across Nigerian cities with 5 providers per 1,000 population.",
        "scenario": "covid_natural",
        "country": "Nigeria",
        "total_days": 150,
        "n_cities": 51,
        "total_population": 39011155,
        "total_infected": 38139977,
        "total_deaths": 48815,
        "peak_infectious": 6437190,
        "supply_chain_enabled": False,
        "precomputed": "/precomputed/nigeria-covid-natural.json",
        "timestamp": 1743480000,
    },
    {
        "session_id": "nigeria-covid-bioattack",
        "label": "Nigeria \u2013 COVID-19 Bioattack",
        "description": "Deliberate COVID-19 release in Lagos with higher initial seeding and rapid spread.",
        "scenario": "covid_bioattack",
        "country": "Nigeria",
        "total_days": 150,
        "n_cities": 51,
        "total_population": 39011155,
        "total_infected": 38952956,
        "total_deaths": 245835,
        "peak_infectious": 7350881,
        "supply_chain_enabled": False,
        "precomputed": "/precomputed/nigeria-covid-bioattack.json",
        "timestamp": 1743480000,
    },
    {
        "session_id": "nigeria-supply-chain",
        "label": "Nigeria \u2013 Supply Chain Constrained",
        "description": "COVID-19 natural spread with supply chain modeling \u2013 PPE, swabs, reagents, and hospital beds.",
        "scenario": "covid_natural",
        "country": "Nigeria",
        "total_days": 150,
        "n_cities": 51,
        "total_population": 39011155,
        "total_infected": 38139977,
        "total_deaths": 48815,
        "peak_infectious": 6437190,
        "supply_chain_enabled": True,
        "precomputed": "/precomputed/nigeria-supply-chain.json",
        "timestamp": 1743480000,
    },
]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"sessions": PRECOMPUTED_SESSIONS})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
