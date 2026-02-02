import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Download, FlaskConical, History, X, Skull, Users, TrendingUp, Package, Trash2 } from 'lucide-react';
import ParameterForm from './ParameterForm';
import ProgressBar from './ProgressBar';
import TimelineViewer from './TimelineViewer';
import SimulationSummary from './SimulationSummary';
import DiseaseParamsViewer from './DiseaseParamsViewer';
import ResourcePanels from './ResourcePanels';

const DEFAULT_PARAMS = {
  country: 'Nigeria',
  scenario: 'covid_natural',
  n_people: 5000,
  avg_contacts: null,
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
  days: 150,
  seed_fraction: 0.005,
  random_seed: 42,
  incubation_days: null,
  infectious_days: null,
  r0_override: null,
  // Supply chain
  enable_supply_chain: false,
  beds_per_hospital: 120,
  beds_per_clinic: 8,
  ppe_sets_per_facility: 500,
  swabs_per_lab: 1000,
  reagents_per_lab: 2000,
  lead_time_mean_days: 7.0,
  continent_vaccine_stockpile: 0,
  continent_pill_stockpile: 0,
};

const APP_STATES = {
  CONFIGURE: 'CONFIGURE',
  RUNNING: 'RUNNING',
  VIEWING: 'VIEWING',
};

function restoreParams(p) {
  const rc = p.resource_config || {};
  return {
    ...DEFAULT_PARAMS,
    country: p.country ?? DEFAULT_PARAMS.country,
    scenario: p.scenario ?? DEFAULT_PARAMS.scenario,
    n_people: p.n_people ?? DEFAULT_PARAMS.n_people,
    avg_contacts: p.avg_contacts ?? null,
    rewire_prob: p.rewire_prob ?? DEFAULT_PARAMS.rewire_prob,
    daily_contact_rate: p.daily_contact_rate ?? DEFAULT_PARAMS.daily_contact_rate,
    transmission_factor: p.transmission_factor ?? DEFAULT_PARAMS.transmission_factor,
    gravity_scale: p.gravity_scale ?? DEFAULT_PARAMS.gravity_scale,
    gravity_alpha: p.gravity_alpha ?? DEFAULT_PARAMS.gravity_alpha,
    provider_density: p.provider_density ?? DEFAULT_PARAMS.provider_density,
    screening_capacity: p.screening_capacity ?? DEFAULT_PARAMS.screening_capacity,
    disclosure_prob: p.disclosure_prob ?? DEFAULT_PARAMS.disclosure_prob,
    base_isolation_prob: p.base_isolation_prob ?? DEFAULT_PARAMS.base_isolation_prob,
    advised_isolation_prob: p.advised_isolation_prob ?? DEFAULT_PARAMS.advised_isolation_prob,
    advice_decay_prob: p.advice_decay_prob ?? DEFAULT_PARAMS.advice_decay_prob,
    receptivity_override: p.receptivity_override ?? null,
    days: p.days ?? DEFAULT_PARAMS.days,
    seed_fraction: p.seed_fraction ?? DEFAULT_PARAMS.seed_fraction,
    random_seed: p.random_seed ?? DEFAULT_PARAMS.random_seed,
    incubation_days: p.incubation_days ?? null,
    infectious_days: p.infectious_days ?? null,
    r0_override: p.r0_override ?? null,
    enable_supply_chain: rc.enable_supply_chain ?? false,
    beds_per_hospital: rc.beds_per_hospital ?? DEFAULT_PARAMS.beds_per_hospital,
    beds_per_clinic: rc.beds_per_clinic ?? DEFAULT_PARAMS.beds_per_clinic,
    ppe_sets_per_facility: rc.ppe_sets_per_facility ?? DEFAULT_PARAMS.ppe_sets_per_facility,
    swabs_per_lab: rc.swabs_per_lab ?? DEFAULT_PARAMS.swabs_per_lab,
    reagents_per_lab: rc.reagents_per_lab ?? DEFAULT_PARAMS.reagents_per_lab,
    lead_time_mean_days: rc.lead_time_mean_days ?? DEFAULT_PARAMS.lead_time_mean_days,
    continent_vaccine_stockpile: rc.continent_vaccine_stockpile ?? DEFAULT_PARAMS.continent_vaccine_stockpile,
    continent_pill_stockpile: rc.continent_pill_stockpile ?? DEFAULT_PARAMS.continent_pill_stockpile,
  };
}

const fmt = (n) => {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return Math.round(n).toLocaleString();
};

function SessionBrowser({ onSelect, onClose }) {
  const [sessions, setSessions] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/simulate/absdes/sessions')
      .then((res) => res.json())
      .then((data) => { setSessions(data.sessions || []); setLoading(false); })
      .catch(() => { setSessions([]); setLoading(false); });
  }, []);

  const handleDelete = useCallback((e, sessionId) => {
    e.stopPropagation();
    fetch(`/api/simulate/absdes/${sessionId}`, { method: 'DELETE' })
      .then((res) => {
        if (res.ok) setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      })
      .catch(() => {});
  }, []);

  const scenarioLabel = (s) => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const timeAgo = (ts) => {
    const diff = (Date.now() / 1000) - ts;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[80vh] flex flex-col animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center">
              <History className="w-4 h-4 text-slate-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Previous Results</h2>
              <p className="text-[10px] text-slate-400">Select a simulation run to load</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin mr-2" />
              Loading sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              No completed simulations yet
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-left sticky top-0">
                  <th className="px-4 py-2.5 font-medium">When</th>
                  <th className="px-4 py-2.5 font-medium">Scenario</th>
                  <th className="px-4 py-2.5 font-medium">Country</th>
                  <th className="px-4 py-2.5 font-medium text-right">Cities</th>
                  <th className="px-4 py-2.5 font-medium text-right">Population</th>
                  <th className="px-4 py-2.5 font-medium text-right">Infected</th>
                  <th className="px-4 py-2.5 font-medium text-right">Deaths</th>
                  <th className="px-4 py-2.5 font-medium text-right">Peak I</th>
                  <th className="px-4 py-2.5 font-medium text-center">Supply</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s, idx) => (
                  <tr
                    key={s.session_id}
                    className={`${idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'} hover:bg-emerald-50/50 cursor-pointer transition-colors`}
                    onClick={() => onSelect(s)}
                  >
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{timeAgo(s.timestamp)}</td>
                    <td className="px-4 py-2.5 font-medium text-slate-700">{scenarioLabel(s.scenario)}</td>
                    <td className="px-4 py-2.5 text-slate-600">{s.country === 'ALL' ? 'All Africa' : s.country}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-slate-500">{s.n_cities}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-slate-600">{fmt(s.total_population)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-red-600">{fmt(s.total_infected)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-red-800 font-semibold">{fmt(s.total_deaths)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-amber-600">{fmt(s.peak_infectious)}</td>
                    <td className="px-4 py-2.5 text-center">
                      {s.supply_chain_enabled ? (
                        <Package className="w-3.5 h-3.5 text-purple-500 mx-auto" />
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-emerald-600 font-medium hover:underline">Load</span>
                        <button
                          onClick={(e) => handleDelete(e, s.session_id)}
                          className="p-1 rounded hover:bg-red-50 text-slate-300 hover:text-red-500 transition-colors"
                          title="Delete this result"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SimulationTab() {
  const [appState, setAppState] = useState(APP_STATES.CONFIGURE);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [sessionId, setSessionId] = useState(null);
  const [totalDays, setTotalDays] = useState(0);
  const [error, setError] = useState(null);
  const [showDiseaseParams, setShowDiseaseParams] = useState(false);
  const [showSessionBrowser, setShowSessionBrowser] = useState(false);
  const didLoadLatest = useRef(false);

  // On mount, try to restore the latest completed simulation
  useEffect(() => {
    if (didLoadLatest.current) return;
    didLoadLatest.current = true;

    fetch('/api/simulate/absdes/latest')
      .then((res) => {
        if (!res.ok) return null;
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        setSessionId(data.session_id);
        setTotalDays(data.total_days);
        if (data.params) setParams(restoreParams(data.params));
        setAppState(APP_STATES.VIEWING);
      })
      .catch(() => {
        // No previous session — stay in CONFIGURE
      });
  }, []);

  const handleRunSimulation = useCallback(async () => {
    setError(null);

    const SUPPLY_KEYS = new Set([
      'enable_supply_chain', 'beds_per_hospital', 'beds_per_clinic',
      'ppe_sets_per_facility', 'swabs_per_lab', 'reagents_per_lab',
      'lead_time_mean_days', 'continent_vaccine_stockpile', 'continent_pill_stockpile',
    ]);
    const payload = {};
    const resourceConfig = {};
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== '') {
        if (SUPPLY_KEYS.has(key)) {
          resourceConfig[key] = value;
        } else {
          payload[key] = value;
        }
      }
    }
    if (params.enable_supply_chain) {
      payload.resource_config = resourceConfig;
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

  const handleLoadSession = useCallback((session) => {
    setSessionId(session.session_id);
    setTotalDays(session.total_days);
    if (session.params) setParams(restoreParams(session.params));
    setAppState(APP_STATES.VIEWING);
    setShowSessionBrowser(false);
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
    <div className="min-h-[calc(100vh-64px)]">
      {/* Toolbar */}
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between border-b border-slate-100 bg-white/50">
        <p className="text-xs text-slate-500">
          Agent-Based / Discrete-Event hybrid model with behavioral surveillance dynamics
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDiseaseParams(true)}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <FlaskConical className="w-4 h-4" />
            Disease Model
          </button>
          <button
            onClick={() => setShowSessionBrowser(true)}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <History className="w-4 h-4" />
            Load Previous Result
          </button>
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

      {/* Main Content */}
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 py-6">
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
              <ResourcePanels sessionId={sessionId} supplyChainEnabled={params.enable_supply_chain} />
            </div>
          </div>
        )}
      </div>

      {showDiseaseParams && (
        <DiseaseParamsViewer onClose={() => setShowDiseaseParams(false)} />
      )}

      {showSessionBrowser && (
        <SessionBrowser onSelect={handleLoadSession} onClose={() => setShowSessionBrowser(false)} />
      )}
    </div>
  );
}
