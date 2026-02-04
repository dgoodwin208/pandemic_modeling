# APR: AI-Augmented Pandemic Response

A continental-scale pandemic simulation platform for modeling AI-powered healthcare interventions across Africa. Features discrete-event simulation (DES) with agent-based behavioral modeling, multi-city gravity coupling, and supply chain constraints.

## Quick Start

### Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm

### 1. Start the Backend

```bash
cd simulation_app/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** to access the dashboard.

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Simulation** | Run continental-scale DES simulations with configurable parameters |
| **Data** | Explore African city data, healthcare infrastructure, and demographics |
| **Supply Chain** | Visualize the three-tier medical supply chain model |
| **Interventions** | Configure AI-powered behavioral interventions |
| **Audio** | "Voices of Africa" — AI-generated greetings in 25+ languages across 55 countries |

## Project Structure

```
pandemic_modeling/
├── frontend/                      # React + Vite dashboard (port 3000)
│   ├── src/
│   │   ├── App.jsx               # Main dashboard with tab navigation
│   │   └── components/           # SimulationTab, DataTab, AudioExplorationTab, etc.
│   └── public/
│       └── audio/                # Pre-generated TTS audio files
│
├── simulation_app/
│   └── backend/                  # FastAPI server (port 8000)
│       ├── main.py              # API endpoints
│       ├── simulation.py        # Multi-city simulation orchestrator
│       ├── city_des_extended.py # Core DES engine with 7-state disease model
│       ├── supply_chain.py      # Three-tier supply chain model
│       └── data/                # Disease params, city data, supply chain data
│
├── des_system/                   # Shared DES primitives
│   ├── disease_model.py
│   ├── social_network.py
│   └── config.py
│
├── 001_validation/ → 008_supply_chain_constrained/
│                                 # Validation modules (see WHITE_PAPER.md)
│
├── WHITE_PAPER.md               # Full methodology and validation results
├── PERSON_JOURNEY.md            # Mermaid diagram of disease state transitions
└── README.md
```

## Simulation Engine

The core simulation uses a **Discrete-Event Simulation (DES)** approach with:

- **7-state disease model**: S → E → I → Symptomatic → {Hospitalized, Recovered, Deceased}
- **Small-world network**: Watts-Strogatz topology with configurable rewiring
- **Gravity coupling**: Inter-city travel based on population and distance
- **Provider screening**: 70/30 targeted screening (contact-based + random)
- **Behavioral intervention**: Isolation compliance, care-seeking, advice receptivity

See `PERSON_JOURNEY.md` for the full state transition diagram.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/countries` | GET | List countries with city counts |
| `/scenarios` | GET | Disease scenarios with parameters |
| `/disease-params` | GET | Full disease parameter table |
| `/simulate/absdes` | POST | Start a simulation (returns session_id) |
| `/simulate/absdes/{id}/progress` | GET | SSE stream of simulation progress |
| `/simulate/absdes/{id}/frame/{view}/{day}` | GET | Rendered PNG frame |
| `/simulate/absdes/{id}/summary` | GET | Final simulation metrics |
| `/simulate/absdes/{id}/export/csv` | GET | Export results as CSV |

## Validation

The simulation has been validated through 8 progressive modules documented in `WHITE_PAPER.md`:

1. **DES-SEIR convergence** — mathematical correctness as N → ∞
2. **Agent-based isolation** — behavioral mechanics
3. **Provider detection** — targeted screening accuracy
4. **Multi-city gravity** — spatial wave propagation
5. **Country-scale** — 51-city Nigeria validation
6. **Continental-scale** — 442-city Africa simulation
7. **Coverage sweep** — provider dose-response
8. **Supply chain** — infrastructure constraints

## Tech Stack

**Backend:** Python 3.11, FastAPI, SimPy, NumPy, Matplotlib

**Frontend:** React 18, Vite, Tailwind CSS, Recharts, Leaflet, Lucide Icons

**Audio:** ElevenLabs TTS (eleven_multilingual_v2, eleven_v3)

## License

MIT License

## References

See `WHITE_PAPER.md` for full citations including:
- Diallo, B., et al. "Resurgence of Ebola virus disease outbreaks in the African continent." *The Lancet*, 2021.
- Watts, D.J. and Strogatz, S.H. "Collective dynamics of 'small-world' networks." *Nature*, 1998.
