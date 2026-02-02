import React, { useState, useEffect } from 'react';
import { X, FlaskConical } from 'lucide-react';

const SCENARIO_LABELS = {
  covid_natural: 'COVID-19 Natural',
  covid_bioattack: 'COVID-19 Bioattack',
  covid_ring3: 'COVID-19 Ring Propagation',
  ebola_natural: 'Ebola Natural',
  ebola_bioattack: 'Ebola Bioattack',
  ebola_ring3: 'Ebola Ring Propagation',
};

export default function DiseaseParamsViewer({ onClose }) {
  const [params, setParams] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/disease-params')
      .then((res) => res.json())
      .then((data) => {
        setParams(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
        <div className="card p-6 text-slate-400 text-sm">Loading disease parameters...</div>
      </div>
    );
  }

  if (!params) return null;

  const scenarios = Object.values(params);
  const pct = (v) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="card max-w-4xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-semibold text-slate-700">Disease Model Parameters</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-xs text-slate-500 mb-4">
            7-state model: S → E → I_minor → (R | I_needs_care → I_receiving_care → (R | D)).
            Waiting times use Gamma distributions (shape parameter controls variance).
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-left">
                  <th className="px-3 py-2 font-medium">Parameter</th>
                  {scenarios.map((s) => (
                    <th key={s.scenario} className="px-3 py-2 font-medium text-center">
                      {SCENARIO_LABELS[s.scenario] || s.scenario}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-slate-600">R0</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono">{s.R0}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-1.5 text-slate-600">Incubation (days)</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono">{s.incubation_days}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-slate-600">Infectious (days)</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono">{s.infectious_days}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-1.5 text-slate-600">Severe fraction</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono text-red-600">{pct(s.severe_fraction)}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-slate-600">Care survival prob</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono text-emerald-600">{pct(s.care_survival_prob)}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-1.5 text-slate-600">IFR (reference)</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono">{pct(s.ifr)}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-slate-600">Gamma shape</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono">{s.gamma_shape}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-1.5 text-slate-600">Base daily death prob</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono text-red-600">{pct(s.base_daily_death_prob)}</td>
                  ))}
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-slate-600">Death prob increase/day</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario} className="px-3 py-1.5 text-center font-mono text-red-600">+{pct(s.death_prob_increase_per_day)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 text-[10px] text-slate-400 space-y-1">
            <p><strong>Severe fraction:</strong> Probability that an infectious person progresses from mild (I_minor) to needing care (I_needs_care).</p>
            <p><strong>Base daily death prob:</strong> Daily probability of death on first day without care. Increases additively each day untreated (capped at 95%).</p>
            <p><strong>Care survival prob:</strong> Base probability of surviving while receiving care, modulated by city medical services score (0.5-1.0x).</p>
          </div>
        </div>
      </div>
    </div>
  );
}
