# ABS-DES Explorer

Interactive visualization tool for exploring the Agent-Based / Discrete-Event Simulation (ABS-DES) model architecture used in APR (AI-Augmented Pandemic Response).

## Views

### 1. Object Model
A React Flow diagram showing the class structure and relationships:

- **SimulationParams** — Configuration dataclass with 66 fields
- **CityDES** — Core discrete-event simulation engine (SimPy)
- **Person** — Agent representation via indexed arrays
- **CitySupply** — Per-city resource tracking (beds, PPE, swabs, reagents)
- **CountrySupplyManager** — Manages resource redistribution across cities
- **ContinentSupplyManager** — Manages vaccine production and reserve deployment
- **DualViewResult** — Output arrays for actual vs observed states

Relationships shown: composition, aggregation, reference, and dependency edges.

### 2. Daily Loop
Step-by-step walkthrough of the simulation's daily loop:

0. Receive Shipments (if supply enabled)
1. Advance SimPy (DES transitions)
2. Provider Screening
3. Vaccinations (if supply enabled)
4. Inter-city Travel
5. Record ACTUAL counts
6. Record OBSERVED counts
7. Supply Chain Update (if supply enabled)

Each step shows which objects are modified and the data flows between them.

### 3. Agent Interrogator
A 3D visualization (Three.js) showing disease progression over time:

- Each agent is a vertical column through time (60 days)
- Color segments show disease state: S → E → I_minor → I_needs → I_care → R/D
- Red lines show transmission events between agents
- Network floor shows social connections
- Time plane shows current day slice

Controls: Play/Pause, day slider, agent selection (all/infected/custom).

## Quick Start

```bash
cd absdes_explorer
npm install
npm run dev
```

Open **http://localhost:5173** to explore.

## Tech Stack

- **React 18** + Vite
- **React Flow** — Object model diagram
- **React Three Fiber** — 3D agent visualization
- **Three.js** — 3D rendering
- **Tailwind CSS** — Styling

## Files

```
absdes_explorer/
├── src/
│   ├── App.jsx          # Main app with all three views
│   ├── App.css          # Minimal custom CSS
│   ├── index.css        # Tailwind imports
│   └── main.jsx         # React entry point
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## Related

- **simulation_app/backend/** — The actual simulation implementation
