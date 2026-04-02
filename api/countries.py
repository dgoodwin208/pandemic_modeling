"""Vercel serverless function: GET /api/countries"""

import csv
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CSV_PATH = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            countries: dict[str, int] = {}
            with open(_CSV_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("country", "Unknown")
                    countries[name] = countries.get(name, 0) + 1

            sorted_countries = sorted(countries.items(), key=lambda x: -x[1])
            body = json.dumps({
                "countries": [
                    {"name": name, "city_count": count}
                    for name, count in sorted_countries
                ],
                "total_countries": len(sorted_countries),
            })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body.encode())
        except FileNotFoundError:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"detail": "City data file not found"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
