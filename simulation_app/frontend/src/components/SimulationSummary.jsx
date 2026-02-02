import React, { useState, useEffect } from 'react';
import { BarChart3, Skull, Users, Eye, TrendingUp, MapPin, Package, AlertTriangle } from 'lucide-react';

function StatCard({ icon: Icon, label, value, sub, color = 'text-slate-700' }) {
  return (
    <div className="stat-card">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">{label}</span>
      </div>
      <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function SimulationSummary({ sessionId }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);

    fetch(`/api/simulate/absdes/${sessionId}/summary`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load summary');
        return res.json();
      })
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId]);

  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <div className="w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
          Loading summary...
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return null;
  }

  const agg = summary.aggregate;
  const fmt = (n) => n.toLocaleString();
  const pct = (n) => `${(n * 100).toFixed(1)}%`;

  const scenarioLabel = summary.scenario.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card p-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="w-4 h-4 text-emerald-600" />
          <h3 className="text-sm font-semibold text-slate-700">Simulation Summary</h3>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">{scenarioLabel}</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">{summary.n_cities} cities</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">{fmt(summary.n_people_per_city)} agents/city</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">{summary.simulation_days} days</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">Fatality: {pct(agg.fatality_rate)}</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded-full">Providers: {summary.provider_density}/1k</span>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard
          icon={Users}
          label="Total Population"
          value={fmt(summary.total_population)}
          color="text-slate-700"
        />
        <StatCard
          icon={TrendingUp}
          label="Total Infected"
          value={fmt(agg.total_infected)}
          sub={`${pct(agg.infection_rate)} of population`}
          color="text-red-600"
        />
        <StatCard
          icon={Skull}
          label="Deaths"
          value={fmt(agg.total_deaths)}
          sub={`${pct(agg.fatality_rate)} fatality rate`}
          color="text-red-800"
        />
        <StatCard
          icon={TrendingUp}
          label="Peak Infectious"
          value={fmt(agg.peak_infectious)}
          sub={`Day ${agg.peak_day}`}
          color="text-amber-600"
        />
        <StatCard
          icon={Eye}
          label="Detected Cases"
          value={fmt(agg.total_detected)}
          sub={`${pct(agg.detection_rate)} detection rate`}
          color="text-blue-600"
        />
      </div>

      {/* Resource Summary (when supply chain enabled) */}
      {summary.supply_chain_enabled && summary.resource_summary && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Package className="w-4 h-4 text-purple-600" />
            <h3 className="text-sm font-semibold text-slate-700">Supply Chain Summary</h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard
              icon={AlertTriangle}
              label="Beds at Capacity"
              value={`${summary.resource_summary.beds_at_capacity_days} days`}
              sub={`${summary.resource_summary.final_beds_occupied}/${summary.resource_summary.final_beds_total} final`}
              color="text-red-600"
            />
            <StatCard
              icon={AlertTriangle}
              label="PPE Stockouts"
              value={`${summary.resource_summary.ppe_stockout_days} days`}
              sub={`${fmt(summary.resource_summary.final_ppe)} remaining`}
              color="text-blue-600"
            />
            <StatCard
              icon={AlertTriangle}
              label="Swab Stockouts"
              value={`${summary.resource_summary.swab_stockout_days} days`}
              sub={`${fmt(summary.resource_summary.final_swabs)} remaining`}
              color="text-green-600"
            />
            <StatCard
              icon={AlertTriangle}
              label="Reagent Stockouts"
              value={`${summary.resource_summary.reagent_stockout_days} days`}
              sub={`${fmt(summary.resource_summary.final_reagents)} remaining`}
              color="text-amber-600"
            />
          </div>
        </div>
      )}

      {/* City Table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <MapPin className="w-3.5 h-3.5 text-slate-400" />
            <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              City Breakdown
              {summary.cities.length < summary.n_cities && (
                <span className="text-slate-400 font-normal ml-1">(top {summary.cities.length} of {summary.n_cities})</span>
              )}
            </h4>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-left">
                <th className="px-3 py-2 font-medium">City</th>
                <th className="px-3 py-2 font-medium text-right">Real Pop.</th>
                <th className="px-3 py-2 font-medium text-right">Infected</th>
                <th className="px-3 py-2 font-medium text-right">Inf. Rate</th>
                <th className="px-3 py-2 font-medium text-right">Peak I</th>
                <th className="px-3 py-2 font-medium text-right">Peak Day</th>
                <th className="px-3 py-2 font-medium text-right">Detected</th>
                <th className="px-3 py-2 font-medium text-right">Deaths</th>
              </tr>
            </thead>
            <tbody>
              {summary.cities.map((city, idx) => (
                <tr key={city.name} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                  <td className="px-3 py-1.5 font-medium text-slate-700">{city.name}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-slate-500">{city.population.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-red-600">{city.total_infected.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-red-500">{pct(city.infection_rate)}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-amber-600">{city.peak_infectious.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-slate-500">{city.peak_day}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-blue-600">{city.total_detected.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-red-800">{city.deaths.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
