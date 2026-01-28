import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, ComposedChart, ReferenceLine
} from 'recharts';
import {
  Play, Pause, RotateCcw, Activity, Users, Skull, TrendingDown,
  MapPin, Building2, TestTube, AlertTriangle, CheckCircle2, Info,
  Settings, ChevronDown, Zap, Map, Database, Lightbulb
} from 'lucide-react';
import AfricaMap from './components/AfricaMap';
import DataTab from './components/DataTab';
import InterventionsTab from './components/InterventionsTab';
import APRLogo from './components/APRLogo';

// =============================================================================
// Configuration & Data
// =============================================================================

const API_BASE = '/api';

const DISEASE_SCENARIOS = {
  'covid-like': { name: 'COVID-like', R0: 2.5, color: '#ef4444', icon: '🦠' },
  'influenza': { name: 'Pandemic Influenza', R0: 1.8, color: '#f59e0b', icon: '🤧' },
  'sars-like': { name: 'SARS-like', R0: 2.0, color: '#8b5cf6', icon: '⚠️' },
  'novel': { name: 'Novel Pathogen X', R0: 3.5, color: '#ec4899', icon: '☣️' },
};

// Total AU population for calculations
const TOTAL_AU_POPULATION = 1400000000;

// =============================================================================
// SEIR Simulation (Client-side fallback)
// =============================================================================

function runSEIRSimulation(params) {
  const {
    population, R0, incubationDays, infectiousDays, ifr, days, initialInfected,
    contactTraceEfficacy, timeToContact, quarantineCompliance, symptomReporting, mobileTestingCoverage,
  } = params;

  const beta = R0 / infectiousDays;
  const sigma = 1 / incubationDays;
  const gamma = 1 / infectiousDays;

  const interventionMultiplier = 1 - (
    (contactTraceEfficacy * 0.3) + ((1 - timeToContact / 72) * 0.2) +
    (quarantineCompliance * 0.25) + (symptomReporting * 0.15) + (mobileTestingCoverage * 0.1)
  );

  const effectiveBeta = beta * Math.max(0.2, interventionMultiplier);

  let S = population - initialInfected, E = 0, I = initialInfected, R = 0, D = 0;
  let cumCases = initialInfected, cumDeaths = 0;
  const results = [];

  for (let day = 0; day <= days; day++) {
    const newExposed = (effectiveBeta * S * I) / population;
    const newInfected = sigma * E;
    const newRecovered = gamma * I * (1 - ifr);
    const newDeaths = gamma * I * ifr;

    S -= newExposed; E += newExposed - newInfected;
    I += newInfected - newRecovered - newDeaths;
    R += newRecovered; D += newDeaths;
    cumCases += newInfected; cumDeaths += newDeaths;

    results.push({
      day, susceptible: Math.max(0, S), exposed: Math.max(0, E),
      infected: Math.max(0, I), recovered: Math.max(0, R), deaths: Math.max(0, D),
      cumCases, cumDeaths, dailyCases: newInfected, dailyDeaths: newDeaths,
      Reff: (effectiveBeta / gamma) * (S / population),
    });
  }
  return results;
}

// =============================================================================
// Helper Functions
// =============================================================================

const formatNumber = (num) => {
  if (num >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return Math.round(num).toLocaleString();
};

// =============================================================================
// Components
// =============================================================================

const StatCard = ({ icon: Icon, label, value, subValue, trend, color = 'blue', glow = false }) => {
  const colorClasses = {
    blue: { bg: 'bg-blue-50', icon: 'text-blue-500', value: 'text-blue-600' },
    red: { bg: 'bg-red-50', icon: 'text-red-500', value: 'text-red-600' },
    orange: { bg: 'bg-orange-50', icon: 'text-orange-500', value: 'text-orange-600' },
    green: { bg: 'bg-emerald-50', icon: 'text-emerald-500', value: 'text-emerald-600' },
    purple: { bg: 'bg-purple-50', icon: 'text-purple-500', value: 'text-purple-600' },
  };

  const colors = colorClasses[color] || colorClasses.blue;

  return (
    <div className={`stat-card ${glow ? `glow-${color}` : ''} transition-all duration-300 hover:shadow-md`}>
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${colors.icon}`} />
        </div>
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <div className={`text-3xl font-semibold tabular-nums ${colors.value}`}>{value}</div>
      {subValue && (
        <div className={`text-sm mt-2 ${trend === 'down' ? 'text-emerald-600' : trend === 'up' ? 'text-red-500' : 'text-slate-500'}`}>
          {subValue}
        </div>
      )}
    </div>
  );
};

const ParamSlider = ({ label, value, onChange, min, max, step, format, baselineValue, inverse = false }) => {
  const improvement = inverse
    ? ((baselineValue - value) / baselineValue * 100)
    : ((value - baselineValue) / (1 - baselineValue) * 100);

  return (
    <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
      <div className="flex justify-between items-center mb-3">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{format(baselineValue)}</span>
          <span className="text-slate-300">→</span>
          <span className="text-sm font-semibold text-emerald-600">{format(value)}</span>
        </div>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="input-range"
      />
      {improvement > 0 && (
        <div className="mt-2 text-xs text-emerald-600 flex items-center gap-1">
          <TrendingDown className="w-3 h-3" />
          {improvement.toFixed(0)}% improvement
        </div>
      )}
    </div>
  );
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-lg">
      <div className="text-sm font-semibold text-slate-800 mb-2">Day {label}</div>
      <div className="space-y-1.5">
        {payload.map((entry, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-slate-500">{entry.name}:</span>
            <span className="font-medium text-slate-800 tabular-nums">{formatNumber(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// =============================================================================
// Main App
// =============================================================================

export default function App() {
  // State
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedScenario, setSelectedScenario] = useState('covid-like');
  const [selectedCountry, setSelectedCountry] = useState(null);
  const [currentDay, setCurrentDay] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showComparison, setShowComparison] = useState(true);
  const [showSettings, setShowSettings] = useState(false);

  const [baselineParams] = useState({
    contactTraceEfficacy: 0.3,
    timeToContact: 48,
    quarantineCompliance: 0.5,
    symptomReporting: 0.3,
    mobileTestingCoverage: 0.1,
  });

  const [aiParams, setAiParams] = useState({
    contactTraceEfficacy: 0.55,
    timeToContact: 12,
    quarantineCompliance: 0.65,
    symptomReporting: 0.5,
    mobileTestingCoverage: 0.25,
  });

  const simulationDays = 180;
  const scenario = DISEASE_SCENARIOS[selectedScenario];
  const scenarioParams = {
    'covid-like': { R0: 2.5, incubationDays: 5, infectiousDays: 10, ifr: 0.01 },
    'influenza': { R0: 1.8, incubationDays: 2, infectiousDays: 5, ifr: 0.002 },
    'sars-like': { R0: 2.0, incubationDays: 4, infectiousDays: 14, ifr: 0.1 },
    'novel': { R0: 3.5, incubationDays: 7, infectiousDays: 12, ifr: 0.05 },
  }[selectedScenario];

  const totalPopulation = TOTAL_AU_POPULATION;

  // Simulations
  const baselineSimulation = useMemo(() => runSEIRSimulation({
    population: totalPopulation,
    ...scenarioParams,
    days: simulationDays,
    initialInfected: Math.max(100, totalPopulation * 0.00001),
    ...baselineParams,
  }), [totalPopulation, scenarioParams, baselineParams]);

  const aiSimulation = useMemo(() => runSEIRSimulation({
    population: totalPopulation,
    ...scenarioParams,
    days: simulationDays,
    initialInfected: Math.max(100, totalPopulation * 0.00001),
    ...aiParams,
  }), [totalPopulation, scenarioParams, aiParams]);

  const comparisonData = useMemo(() => baselineSimulation.map((base, i) => ({
    day: base.day,
    baselineInfected: base.infected,
    aiInfected: aiSimulation[i].infected,
    baselineDeaths: base.cumDeaths,
    aiDeaths: aiSimulation[i].cumDeaths,
    baselineCases: base.cumCases,
    aiCases: aiSimulation[i].cumCases,
    baselineReff: base.Reff,
    aiReff: aiSimulation[i].Reff,
  })), [baselineSimulation, aiSimulation]);

  // Animation
  useEffect(() => {
    if (!isPlaying || currentDay >= simulationDays) return;
    const interval = setInterval(() => setCurrentDay(d => Math.min(d + 1, simulationDays)), 80);
    return () => clearInterval(interval);
  }, [isPlaying, currentDay]);

  // Stats
  const currentStats = comparisonData[currentDay] || comparisonData[0];
  const peakBaseline = Math.max(...comparisonData.map(d => d.baselineInfected));
  const peakAI = Math.max(...comparisonData.map(d => d.aiInfected));
  const finalBaselineDeaths = comparisonData[simulationDays]?.baselineDeaths || 0;
  const finalAIDeaths = comparisonData[simulationDays]?.aiDeaths || 0;
  const livesAverted = finalBaselineDeaths - finalAIDeaths;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200">
        <div className="max-w-[1800px] mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              {/* APR Logo */}
              <APRLogo size="default" showText={true} />

              {/* Tab Navigation */}
              <div className="flex items-center gap-1 ml-4 bg-slate-100 rounded-xl p-1">
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'dashboard'
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Map className="w-4 h-4" />
                  Dashboard
                </button>
                <button
                  onClick={() => setActiveTab('data')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'data'
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Database className="w-4 h-4" />
                  Data
                </button>
                <button
                  onClick={() => setActiveTab('interventions')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'interventions'
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Lightbulb className="w-4 h-4" />
                  Interventions
                </button>
              </div>
            </div>

            {activeTab === 'dashboard' && (
              <div className="flex items-center gap-4">
                {/* Scenario Selector */}
                <div className="relative">
                  <select
                    value={selectedScenario}
                    onChange={(e) => { setSelectedScenario(e.target.value); setCurrentDay(0); }}
                    className="appearance-none bg-slate-100 border border-slate-200 text-slate-700 pl-4 pr-10 py-2.5 rounded-xl text-sm font-medium cursor-pointer hover:border-slate-300 transition-colors"
                  >
                    {Object.entries(DISEASE_SCENARIOS).map(([key, val]) => (
                      <option key={key} value={key}>{val.icon} {val.name}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                </div>

                {/* R0 Badge */}
                <div className="px-4 py-2 rounded-xl text-sm font-semibold bg-slate-100 border border-slate-200"
                     style={{ color: scenario.color }}>
                  R₀ = {scenarioParams.R0}
                </div>

                {/* Settings Toggle */}
                <button
                  onClick={() => setShowSettings(!showSettings)}
                  className={`p-2.5 rounded-xl transition-all ${showSettings ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-500 hover:text-slate-700'}`}
                >
                  <Settings className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      {activeTab === 'data' ? (
        <main className="h-[calc(100vh-64px)]">
          <DataTab />
        </main>
      ) : activeTab === 'interventions' ? (
        <main className="h-[calc(100vh-64px)]">
          <InterventionsTab />
        </main>
      ) : (
      <main className="max-w-[1800px] mx-auto p-6">
        <div className="grid grid-cols-12 gap-6">

          {/* Left Column - Map */}
          <div className="col-span-5">
            <div className="card p-6 h-full">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Map className="w-5 h-5 text-emerald-500" />
                  Cities and Facilities
                </h2>
                <span className="text-xs text-slate-400">442 cities • 55 countries</span>
              </div>

              {/* Real Map */}
              <div className="rounded-xl overflow-hidden border border-slate-200" style={{ height: 'calc(100vh - 440px)', minHeight: 360 }}>
                <AfricaMap
                  currentDay={currentDay}
                  selectedCountry={selectedCountry}
                  onCountrySelect={setSelectedCountry}
                  showLegend={false}
                />
              </div>

              {/* Legend below map */}
              <div className="mt-3 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="text-xs font-medium text-slate-500">City Population:</span>
                    {[
                      { color: '#f59e0b', label: '5M+' },
                      { color: '#ef4444', label: '2-5M' },
                      { color: '#ec4899', label: '1-2M' },
                      { color: '#8b5cf6', label: '500K-1M' },
                      { color: '#60a5fa', label: '100K-500K' },
                    ].map((item, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                        <span className="text-xs text-slate-500">{item.label}</span>
                      </div>
                    ))}
                  </div>
                  <span className="text-xs text-slate-400">Click cities for details</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Stats & Chart */}
          <div className="col-span-7 space-y-6">
            {/* Stats Row */}
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                icon={Activity}
                label="Active Infections"
                value={formatNumber(currentStats.baselineInfected)}
                subValue={showComparison ? `AI: ${formatNumber(currentStats.aiInfected)} (${((1 - currentStats.aiInfected/currentStats.baselineInfected) * 100).toFixed(0)}% ↓)` : null}
                color="red"
                trend="down"
              />
              <StatCard
                icon={Skull}
                label="Cumulative Deaths"
                value={formatNumber(currentStats.baselineDeaths)}
                subValue={showComparison ? `AI: ${formatNumber(currentStats.aiDeaths)}` : null}
                color="orange"
              />
              <StatCard
                icon={Users}
                label="R_eff"
                value={currentStats.baselineReff.toFixed(2)}
                subValue={showComparison ? `AI: ${currentStats.aiReff.toFixed(2)}` : null}
                color={currentStats.baselineReff > 1 ? 'red' : 'green'}
              />
              <StatCard
                icon={CheckCircle2}
                label="Lives Averted (180d)"
                value={formatNumber(livesAverted)}
                subValue={`${((livesAverted / Math.max(1, finalBaselineDeaths)) * 100).toFixed(0)}% reduction`}
                color="green"
                glow={true}
              />
            </div>

            {/* Chart */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-800">Epidemic Curve Comparison</h2>
                <label className="flex items-center gap-2 text-sm text-slate-500 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showComparison}
                    onChange={(e) => setShowComparison(e.target.checked)}
                    className="w-4 h-4 rounded bg-slate-100 border-slate-300 text-emerald-500 focus:ring-emerald-500"
                  />
                  <Zap className="w-4 h-4 text-emerald-500" />
                  Show AI Intervention
                </label>
              </div>

              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={comparisonData} margin={{ top: 10, right: 70, left: 70, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="day" stroke="#94a3b8" fontSize={11}
                    label={{ value: 'Days Since Outbreak', position: 'bottom', offset: 15, style: { fill: '#64748b', fontSize: 12 } }}
                  />
                  {/* Left Y-axis: AI-enabled (green) */}
                  <YAxis
                    yAxisId="left"
                    orientation="left"
                    stroke="#10b981" fontSize={11}
                    tickFormatter={formatNumber}
                    label={{ value: 'With AI Intervention', angle: -90, position: 'insideLeft', offset: -55, style: { fill: '#10b981', fontSize: 11, textAnchor: 'middle' } }}
                  />
                  {/* Right Y-axis: Baseline (red) */}
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#ef4444" fontSize={11}
                    tickFormatter={formatNumber}
                    label={{ value: 'No AI Intervention', angle: 90, position: 'insideRight', offset: -55, style: { fill: '#ef4444', fontSize: 11, textAnchor: 'middle' } }}
                  />
                  <Tooltip content={<CustomTooltip />} />

                  <Area yAxisId="right" type="monotone" dataKey="baselineInfected" name="No AI Intervention" fill="#fecaca" stroke="#ef4444" strokeWidth={2} fillOpacity={0.4} />
                  {showComparison && <Area yAxisId="left" type="monotone" dataKey="aiInfected" name="With AI Intervention" fill="#d1fae5" stroke="#10b981" strokeWidth={2.5} fillOpacity={0.5} />}
                  <ReferenceLine yAxisId="left" x={currentDay} stroke="#64748b" strokeWidth={2} strokeDasharray="5 5" />
                </ComposedChart>
              </ResponsiveContainer>

              {/* Summary bar */}
              {showComparison && (
                <div className="mt-4 p-4 bg-emerald-50 border border-emerald-100 rounded-xl flex justify-center gap-12">
                  {[
                    { label: 'Peak Reduction', value: `${((1 - peakAI/peakBaseline) * 100).toFixed(1)}%` },
                    { label: 'Mortality Reduction', value: `${((1 - finalAIDeaths/Math.max(1,finalBaselineDeaths)) * 100).toFixed(1)}%` },
                    { label: 'Lives Averted', value: formatNumber(livesAverted) },
                  ].map(({ label, value }) => (
                    <div key={label} className="text-center">
                      <div className="text-xs text-slate-500 mb-1">{label}</div>
                      <div className="text-lg font-semibold text-emerald-600 tabular-nums">{value}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Timeline Control */}
            <div className="card p-4">
              <div className="flex items-center gap-4">
                <button onClick={() => setIsPlaying(!isPlaying)} className="btn-primary w-12 h-12 flex items-center justify-center">
                  {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                </button>
                <button onClick={() => setCurrentDay(0)} className="btn-secondary w-12 h-12 flex items-center justify-center">
                  <RotateCcw className="w-5 h-5" />
                </button>
                <div className="flex-1">
                  <input
                    type="range" min={0} max={simulationDays} value={currentDay}
                    onChange={(e) => setCurrentDay(parseInt(e.target.value))}
                    className="input-range"
                  />
                </div>
                <div className="text-lg font-semibold text-slate-800 w-32 text-right tabular-nums">
                  Day {currentDay} <span className="text-slate-400">/ {simulationDays}</span>
                </div>
              </div>
            </div>

            {/* Intervention Parameters (Collapsible) */}
            {showSettings && (
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-emerald-500" />
                  AI Intervention Parameters
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <ParamSlider
                    label="Contact Trace Efficacy"
                    value={aiParams.contactTraceEfficacy}
                    onChange={(v) => setAiParams(p => ({ ...p, contactTraceEfficacy: v }))}
                    min={0} max={1} step={0.05}
                    format={(v) => `${(v*100).toFixed(0)}%`}
                    baselineValue={baselineParams.contactTraceEfficacy}
                  />
                  <ParamSlider
                    label="Time to First Contact"
                    value={aiParams.timeToContact}
                    onChange={(v) => setAiParams(p => ({ ...p, timeToContact: v }))}
                    min={1} max={72} step={1}
                    format={(v) => `${v}h`}
                    baselineValue={baselineParams.timeToContact}
                    inverse={true}
                  />
                  <ParamSlider
                    label="Quarantine Compliance"
                    value={aiParams.quarantineCompliance}
                    onChange={(v) => setAiParams(p => ({ ...p, quarantineCompliance: v }))}
                    min={0} max={1} step={0.05}
                    format={(v) => `${(v*100).toFixed(0)}%`}
                    baselineValue={baselineParams.quarantineCompliance}
                  />
                  <ParamSlider
                    label="Symptom Reporting Rate"
                    value={aiParams.symptomReporting}
                    onChange={(v) => setAiParams(p => ({ ...p, symptomReporting: v }))}
                    min={0} max={1} step={0.05}
                    format={(v) => `${(v*100).toFixed(0)}%`}
                    baselineValue={baselineParams.symptomReporting}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
      )}

      {/* Footer - only show on dashboard */}
      {activeTab === 'dashboard' && (
        <footer className="border-t border-slate-200 bg-white mt-8">
          <div className="max-w-[1800px] mx-auto px-6 py-4 flex justify-between items-center text-sm text-slate-500">
            <div>SEIR Model with Intervention Modifiers • Population: {formatNumber(totalPopulation)}</div>
            <div className="tabular-nums">Peak ↓ {((1 - peakAI/peakBaseline) * 100).toFixed(0)}% • Mortality ↓ {((1 - finalAIDeaths/Math.max(1,finalBaselineDeaths)) * 100).toFixed(0)}%</div>
          </div>
        </footer>
      )}
    </div>
  );
}
