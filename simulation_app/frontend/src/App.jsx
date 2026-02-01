import React, { useState, useCallback } from 'react';
import { Activity, Download } from 'lucide-react';
import ParameterForm from './components/ParameterForm';
import ProgressBar from './components/ProgressBar';
import TimelineViewer from './components/TimelineViewer';
import SimulationSummary from './components/SimulationSummary';

const DEFAULT_PARAMS = {
  country: 'Nigeria',
  scenario: 'covid_natural',
  n_people: 5000,
  avg_contacts: 10,
  rewire_prob: 0.4,
  daily_contact_rate: 0.5,
  transmission_factor: 0.3,
  gravity_scale: 0.01,
  gravity_alpha: 2.0,
  provider_density: 5.0,
  screening_capacity: 20,
  disclosure_prob: 0.5,
  base_isolation_prob: 0.0,
  advised_isolation_prob: 0.40,
  advice_decay_prob: 0.05,
  receptivity_override: null,
  days: 200,
  seed_fraction: 0.002,
  random_seed: 42,
  incubation_days: null,
  infectious_days: null,
  r0_override: null,
};

const APP_STATES = {
  CONFIGURE: 'CONFIGURE',
  RUNNING: 'RUNNING',
  VIEWING: 'VIEWING',
};

export default function App() {
  const [appState, setAppState] = useState(APP_STATES.CONFIGURE);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [sessionId, setSessionId] = useState(null);
  const [totalDays, setTotalDays] = useState(0);
  const [error, setError] = useState(null);

  const handleRunSimulation = useCallback(async () => {
    setError(null);

    const payload = {};
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== '') {
        payload[key] = value;
      }
    }

    try {
      const response = await fetch('/api/simulate/absdes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setTotalDays(params.days);
      setAppState(APP_STATES.RUNNING);
    } catch (err) {
      setError(err.message || 'Failed to start simulation');
    }
  }, [params]);

  const handleSimulationComplete = useCallback(() => {
    setAppState(APP_STATES.VIEWING);
  }, []);

  const handleSimulationError = useCallback((errorMsg) => {
    setError(errorMsg);
    setAppState(APP_STATES.CONFIGURE);
  }, []);

  const handleReset = useCallback(() => {
    setAppState(APP_STATES.CONFIGURE);
    setSessionId(null);
    setError(null);
  }, []);

  const handleExportCSV = useCallback(async () => {
    if (!sessionId) return;
    try {
      const response = await fetch(`/api/simulate/absdes/${sessionId}/export/csv`);
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `simulation_${sessionId.slice(0, 8)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to export CSV: ' + err.message);
    }
  }, [sessionId]);

  const isViewing = appState === APP_STATES.VIEWING;
  const isRunning = appState === APP_STATES.RUNNING;
  const isConfigure = appState === APP_STATES.CONFIGURE;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-50 border border-emerald-200">
                <Activity className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-slate-800 leading-tight">
                  AI-Augmented Pandemic Response — ABS-DES Simulation
                </h1>
                <p className="text-xs text-slate-500 leading-tight">
                  Agent-Based / Discrete-Event hybrid model with behavioral surveillance dynamics
                </p>
              </div>
            </div>
            {isViewing && (
              <button
                onClick={handleExportCSV}
                className="btn-secondary flex items-center gap-2 text-sm"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 py-6">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm animate-fade-in">
            <span className="font-medium">Error:</span> {error}
            <button
              onClick={() => setError(null)}
              className="ml-3 text-red-500 hover:text-red-700 underline text-xs"
            >
              dismiss
            </button>
          </div>
        )}

        {isConfigure && (
          <div className="max-w-2xl mx-auto animate-fade-in">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-slate-800 mb-2">Configure Simulation</h2>
              <p className="text-slate-500 text-sm">
                Set parameters for the ABS-DES pandemic simulation model. Adjust network topology,
                transmission dynamics, and agent behaviors below.
              </p>
            </div>
            <ParameterForm
              params={params}
              setParams={setParams}
              onRun={handleRunSimulation}
              disabled={false}
              compact={false}
            />
          </div>
        )}

        {isRunning && (
          <div className="animate-fade-in">
            <div className="max-w-2xl mx-auto mb-8">
              <ProgressBar
                sessionId={sessionId}
                onComplete={handleSimulationComplete}
                onError={handleSimulationError}
              />
            </div>
            <div className="max-w-2xl mx-auto opacity-50 pointer-events-none">
              <ParameterForm
                params={params}
                setParams={setParams}
                onRun={handleRunSimulation}
                disabled={true}
                compact={false}
              />
            </div>
          </div>
        )}

        {isViewing && (
          <div className="grid grid-cols-12 gap-6 animate-fade-in">
            {/* Sidebar */}
            <div className="col-span-12 lg:col-span-3">
              <div className="sticky top-20">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
                    Parameters
                  </h3>
                  <button
                    onClick={handleReset}
                    className="text-xs text-slate-400 hover:text-emerald-600 transition-colors"
                  >
                    New Simulation
                  </button>
                </div>
                <ParameterForm
                  params={params}
                  setParams={setParams}
                  onRun={handleRunSimulation}
                  disabled={false}
                  compact={true}
                />
              </div>
            </div>

            {/* Timeline Viewer + Summary */}
            <div className="col-span-12 lg:col-span-9 space-y-6">
              <TimelineViewer
                sessionId={sessionId}
                totalDays={totalDays}
              />
              <SimulationSummary sessionId={sessionId} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
