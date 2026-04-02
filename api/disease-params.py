"""Vercel serverless function: GET /api/disease-params"""

import csv
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "simulation_app" / "backend" / "data"


def _load_disease_params() -> dict:
    """Load disease parameters from CSV, matching sim_config.load_disease_params()."""
    csv_path = _DATA_DIR / "disease_params.csv"
    params = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario = row["scenario"]
            params[scenario] = {
                "scenario": scenario,
                "R0": float(row.get("R0", 2.5)),
                "incubation_days": float(row.get("incubation_days", 5.0)),
                "infectious_days": float(row.get("infectious_days", 9.0)),
                "severe_fraction": float(row.get("severe_fraction", 0.15)),
                "care_survival_prob": float(row.get("care_survival_prob", 0.85)),
                "ifr": float(row.get("ifr", 0.01)),
                "gamma_shape": float(row.get("gamma_shape", 3.0)),
                "base_daily_death_prob": float(row.get("base_daily_death_prob", 0.02)),
                "death_prob_increase_per_day": float(row.get("death_prob_increase_per_day", 0.005)),
            }
    return params


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = _load_disease_params()
            body = json.dumps(params)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body.encode())
        except FileNotFoundError:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"detail": "Disease params file not found"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
