# AI-Augmented Pandemic Response Model

A full-stack simulation dashboard for modeling AI interventions in pandemic response across African Union member states. Features SEIR epidemic modeling, interactive visualization, and parameter tuning.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Pandemic+Response+Dashboard)

## Features

- **SEIR Epidemic Model**: Compartmental model (Susceptible → Exposed → Infected → Recovered/Dead)
- **AI Intervention Parameters**: Model the effect of AI-powered contact tracing, mobile testing, and compliance tools
- **Geographic Visualization**: Interactive map of 55 African Union member states
- **Real-time Simulation**: Animated epidemic curves with baseline vs. AI-augmented comparison
- **Dual Y-Axis Charts**: Track infections and cumulative deaths simultaneously
- **Multiple Disease Scenarios**: COVID-like, Pandemic Influenza, SARS-like, Novel Pathogen X

## Project Structure

```
pandemic-model/
├── backend/                    # Python FastAPI server
│   ├── main.py                # API endpoints and SEIR model
│   └── requirements.txt       # Python dependencies
├── frontend/                   # React + Vite application
│   ├── src/
│   │   ├── App.jsx           # Main dashboard component
│   │   ├── main.jsx          # React entry point
│   │   └── index.css         # Tailwind + custom styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
├── run.sh                      # Start script (Mac/Linux)
├── run.bat                     # Start script (Windows)
└── README.md
```

## Quick Start

### Prerequisites

- **Python 3.9+** ([Download](https://www.python.org/downloads/))
- **Node.js 18+** ([Download](https://nodejs.org/))
- **npm** or **yarn**

### Option 1: Using Run Scripts

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

**Windows:**
```cmd
run.bat
```

### Option 2: Manual Setup

#### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000

#### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/scenarios` | GET | List available disease scenarios |
| `/countries` | GET | Get all African Union countries |
| `/countries/{id}` | GET | Get specific country by ID |
| `/simulate` | POST | Run epidemic simulation |
| `/simulate/sensitivity` | POST | Run parameter sensitivity analysis |

### Example: Run Simulation

```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "population": 1400000000,
    "scenario": "covid-like",
    "days": 180,
    "initial_infected": 1000,
    "baseline_params": {
      "contact_trace_efficacy": 0.3,
      "time_to_contact": 48,
      "quarantine_compliance": 0.5,
      "symptom_reporting": 0.3,
      "mobile_testing_coverage": 0.1
    },
    "ai_params": {
      "contact_trace_efficacy": 0.85,
      "time_to_contact": 4,
      "quarantine_compliance": 0.8,
      "symptom_reporting": 0.75,
      "mobile_testing_coverage": 0.4
    }
  }'
```

## Intervention Parameters

| Parameter | Baseline | AI-Augmented | Description |
|-----------|----------|--------------|-------------|
| Contact Trace Efficacy | 30% | 85% | Probability of successful contact identification |
| Time to First Contact | 48h | 4h | Hours from positive test to reaching contacts |
| Quarantine Compliance | 50% | 80% | Proportion of contacts who properly isolate |
| Symptom Reporting | 30% | 75% | Proportion of symptomatic individuals seeking testing |
| Mobile Testing Coverage | 10% | 40% | Population with access to mobile testing facilities |

## Disease Scenarios

| Scenario | R₀ | Incubation | Infectious | IFR |
|----------|-----|------------|------------|-----|
| COVID-like | 2.5 | 5 days | 10 days | 1% |
| Pandemic Influenza | 1.8 | 2 days | 5 days | 0.2% |
| SARS-like | 2.0 | 4 days | 14 days | 10% |
| Novel Pathogen X | 3.5 | 7 days | 12 days | 5% |

## Extending the Model

### Adding Custom Disease Scenarios

Edit `backend/main.py`:

```python
DISEASE_PARAMS = {
    DiseaseScenario.MY_DISEASE: {
        "name": "My Custom Disease",
        "R0": 2.8,
        "incubation_days": 3,
        "infectious_days": 7,
        "ifr": 0.02,
    },
    # ... existing scenarios
}
```

### Connecting to External Models

The backend is designed to be extensible. You can integrate more complex models:

```python
# In main.py or a new module

def run_advanced_simulation(params):
    """
    Integrate with external epidemic models like:
    - GLEAM (Global Epidemic and Mobility Model)
    - CovidSim (Imperial College)
    - Custom agent-based models
    """
    # Your integration code here
    pass
```

### Adding Supply Chain Data

The country data structure supports supply chain fields:

```python
CountryData(
    id="KEN",
    name="Kenya",
    population=53800000,
    supply_hubs=3,
    testing_facilities=10,
    hospital_beds=14000,      # Add real data
    icu_beds=500,             # Add real data
    vaccine_storage=20000,    # Custom fields
)
```

## Development

### Backend Development

```bash
cd backend

# Run with auto-reload
uvicorn main:app --reload

# Run tests (if added)
pytest

# Type checking
mypy main.py
```

### Frontend Development

```bash
cd frontend

# Development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Tech Stack

**Backend:**
- Python 3.9+
- FastAPI
- Pydantic
- NumPy
- Uvicorn

**Frontend:**
- React 18
- Vite
- Recharts
- Tailwind CSS
- Lucide Icons

## License

MIT License - feel free to use this for research, education, or commercial purposes.

## Acknowledgments

- SEIR model based on classical compartmental epidemiology (Kermack & McKendrick, 1927)
- Intervention effect weights derived from literature including Ferretti et al. (2020) and Peak et al. (2020)
- African Union population data from World Bank (2023)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
