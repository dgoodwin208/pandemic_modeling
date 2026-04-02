import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Download, FlaskConical, History, X, Package, Trash2, Github, Play, ExternalLink } from 'lucide-react';
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
  const [loadingSession, setLoadingSession] = useState(null);

  useEffect(() => {
    fetch('/api/simulate/absdes/sessions')
      .then((res) => res.json())
      .then((data) => { setSessions(data.sessions || []); setLoading(false); })
      .catch(() => { setSessions([]); setLoading(false); });
  }, []);

  const handleSelect = useCallback(async (session) => {
    if (session.precomputed) {
      setLoadingSession(session.session_id);
      try {
        const res = await fetch(session.precomputed);
        if (!res.ok) throw new Error('Failed to load precomputed data');
        const data = await res.json();
        onSelect({ ...session, _precomputedData: data });
      } catch {
        onSelect(session);
      } finally {
        setLoadingSession(null);
      }
    } else {
      onSelect(session);
    }
  }, [onSelect]);

  const handleDelete = useCallback((e, sessionId) => {
    e.stopPropagation();
    fetch(`/api/simulate/absdes/${sessionId}`, { method: 'DELETE' })
      .then((res) => {
        if (res.ok) setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      })
      .catch(() => {});
  }, []);

  const scenarioLabel = (s) => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

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
              <h2 className="text-sm font-semibold text-slate-800">Load Simulation Results</h2>
              <p className="text-[10px] text-slate-400">Select a pre-computed scenario to explore</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* Sessions list */}
        <div className="overflow-auto flex-1 p-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin mr-2" />
              Loading sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              No simulation results available
            </div>
          ) : (
            sessions.map((s) => (
              <button
                key={s.session_id}
                className="w-full text-left p-4 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 transition-all group"
                onClick={() => handleSelect(s)}
                disabled={loadingSession === s.session_id}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-semibold text-slate-800 group-hover:text-emerald-700 transition-colors">
                        {s.label || scenarioLabel(s.scenario)}
                      </h3>
                      {s.supply_chain_enabled && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-600 text-[10px] font-medium">
                          <Package className="w-2.5 h-2.5" />
                          Supply Chain
                        </span>
                      )}
                    </div>
                    {s.description && (
                      <p className="text-xs text-slate-500 mb-2">{s.description}</p>
                    )}
                    <div className="flex items-center gap-4 text-[11px]">
                      <span className="text-slate-500">{s.n_cities} cities</span>
                      <span className="text-slate-500">{fmt(s.total_population)} pop</span>
                      {s.total_infected != null && (
                        <span className="text-red-600">{fmt(s.total_infected)} infected</span>
                      )}
                      {s.total_deaths != null && (
                        <span className="text-red-800 font-medium">{fmt(s.total_deaths)} deaths</span>
                      )}
                      {s.peak_infectious != null && (
                        <span className="text-amber-600">peak {fmt(s.peak_infectious)}</span>
                      )}
                      <span className="text-slate-400">{s.total_days} days</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {loadingSession === s.session_id ? (
                      <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
                    ) : (
                      <span className="text-xs text-emerald-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                        Load
                      </span>
                    )}
                    {!s.precomputed && (
                      <button
                        onClick={(e) => handleDelete(e, s.session_id)}
                        className="p-1 rounded hover:bg-red-50 text-slate-300 hover:text-red-500 transition-colors"
                        title="Delete this result"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function DemoIntroModal({ onLoadDataset, onConfigure, onClose }) {
  const [sessions, setSessions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingSession, setLoadingSession] = useState(null);

  useEffect(() => {
    fetch('/api/simulate/absdes/sessions')
      .then((res) => res.json())
      .then((data) => { setSessions(data.sessions || []); setLoading(false); })
      .catch(() => { setSessions([]); setLoading(false); });
  }, []);

  const handleLoad = useCallback(async (session) => {
    if (session.precomputed) {
      setLoadingSession(session.session_id);
      try {
        const res = await fetch(session.precomputed);
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        onLoadDataset({ ...session, _precomputedData: data });
      } catch {
        onLoadDataset(session);
      } finally {
        setLoadingSession(null);
      }
    } else {
      onLoadDataset(session);
    }
  }, [onLoadDataset]);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg flex flex-col animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 pt-6 pb-4 text-center">
          <h2 className="text-xl font-bold text-slate-800 mb-1">
            AI Pandemic Response Explorer
          </h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            This demo runs on a minimal serverless instance.
            Explore pre-computed simulation results below, or clone the repo to run your own.
          </p>
        </div>

        {/* Precomputed datasets */}
        <div className="px-6 pb-4 space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Load a dataset to explore
          </p>
          {loading ? (
            <div className="flex items-center justify-center py-6 text-sm text-slate-400">
              <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin mr-2" />
              Loading...
            </div>
          ) : (
            sessions.map((s) => (
              <button
                key={s.session_id}
                className="w-full text-left p-3 rounded-lg border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 transition-all group flex items-center gap-3"
                onClick={() => handleLoad(s)}
                disabled={loadingSession === s.session_id}
              >
                <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0 group-hover:bg-emerald-100 transition-colors">
                  {loadingSession === s.session_id ? (
                    <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 text-emerald-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-slate-700 group-hover:text-emerald-700 transition-colors">
                    {s.label}
                  </h3>
                  <p className="text-[11px] text-slate-400 truncate">{s.description}</p>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Footer actions */}
        <div className="px-6 pb-6 pt-2 border-t border-slate-100 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={onConfigure}
              className="flex-1 btn-secondary text-sm py-2.5 text-center"
            >
              Configure Custom Simulation
            </button>
            <a
              href="https://github.com/dgoodwin208/pandemic_modeling"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 btn-primary text-sm py-2.5 text-center flex items-center justify-center gap-2"
            >
              <Github className="w-4 h-4" />
              Clone & Run Locally
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <p className="text-[10px] text-slate-400 text-center">
            Full simulations with geographic rendering require local execution.
            See the README for setup instructions.
          </p>
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
  const [showIntroModal, setShowIntroModal] = useState(false);
  const didLoadLatest = useRef(false);
  // Sync mode: when the server returns full results in the POST response
  const [syncData, setSyncData] = useState(null);
  // Base URL for precomputed frame PNGs (e.g. /precomputed/frames/nigeria-covid-natural)
  const [frameBaseUrl, setFrameBaseUrl] = useState(null);

  // On mount, show the intro modal for demo
  useEffect(() => {
    if (didLoadLatest.current) return;
    didLoadLatest.current = true;
    setShowIntroModal(true);
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
      setAppState(APP_STATES.RUNNING);
      setSyncData(null);
      setFrameBaseUrl(null);

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
      setTotalDays(data.total_days || params.days);

      if (data.sync_mode) {
        // Serverless mode: results returned directly in response
        setSyncData({ summary: data.summary, resources: data.resources });
        setAppState(APP_STATES.VIEWING);
      } else {
        // Traditional mode: poll SSE for progress
        setAppState(APP_STATES.RUNNING);
      }
    } catch (err) {
      setError(err.message || 'Failed to start simulation');
      setAppState(APP_STATES.CONFIGURE);
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
    setSyncData(null);
    setFrameBaseUrl(null);
    setError(null);
  }, []);

  const handleLoadSession = useCallback((session) => {
    setSessionId(session.session_id);
    setTotalDays(session.total_days);
    if (session.params) setParams(restoreParams(session.params));
    setError(null);
    setShowSessionBrowser(false);

    // If precomputed data was fetched by SessionBrowser, load it as syncData
    if (session._precomputedData) {
      const d = session._precomputedData;
      setSyncData({ summary: d.summary, resources: d.resources });
      // Set frame base URL for precomputed PNGs
      setFrameBaseUrl(`/precomputed/frames/${session.session_id}`);
      if (session.supply_chain_enabled != null) {
        setParams((prev) => ({ ...prev, enable_supply_chain: session.supply_chain_enabled }));
      }
    } else {
      setSyncData(null);
      setFrameBaseUrl(null);
    }
    setAppState(APP_STATES.VIEWING);
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
              {sessionId ? (
                <ProgressBar
                  sessionId={sessionId}
                  onComplete={handleSimulationComplete}
                  onError={handleSimulationError}
                />
              ) : (
                <div className="card p-6">
                  <div className="flex items-center gap-3 text-slate-500 text-sm">
                    <div className="w-5 h-5 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
                    Running simulation... This may take up to 60 seconds.
                  </div>
                  <p className="text-xs text-slate-400 mt-2">
                    Demo mode — simulation runs on a serverless backend with limited capacity.
                  </p>
                </div>
              )}
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
                framesAvailable={!syncData || !!frameBaseUrl}
                frameBaseUrl={frameBaseUrl}
              />
              <SimulationSummary sessionId={sessionId} data={syncData?.summary} />
              <ResourcePanels sessionId={sessionId} supplyChainEnabled={params.enable_supply_chain} data={syncData?.resources} />
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

      {showIntroModal && (
        <DemoIntroModal
          onLoadDataset={(session) => {
            setShowIntroModal(false);
            handleLoadSession(session);
          }}
          onConfigure={() => setShowIntroModal(false)}
          onClose={() => setShowIntroModal(false)}
        />
      )}
    </div>
  );
}
