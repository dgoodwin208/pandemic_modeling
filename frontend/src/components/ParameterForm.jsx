import React, { useState, useEffect, useCallback } from 'react';
import { ChevronDown, Settings, Sliders, Zap, Clock, Activity, Info, X, HeartPulse, Package } from 'lucide-react';

const SCENARIOS = [
  { value: 'covid_natural', label: 'COVID-19 — Natural Outbreak' },
  { value: 'covid_bioattack', label: 'COVID-19 — Bioattack' },
  { value: 'covid_ring3', label: 'COVID-19 — Ring Propagation' },
  { value: 'ebola_natural', label: 'Ebola — Natural Outbreak' },
  { value: 'ebola_bioattack', label: 'Ebola — Bioattack' },
  { value: 'ebola_ring3', label: 'Ebola — Ring Propagation' },
];

const SCENARIO_DEFAULTS = {
  covid_natural: { incubation_days: 5.0, infectious_days: 9.0, r0: 2.5 },
  covid_bioattack: { incubation_days: 4.0, infectious_days: 9.0, r0: 3.5 },
  covid_ring3: { incubation_days: 4.0, infectious_days: 9.0, r0: 3.5 },
  ebola_natural: { incubation_days: 10.0, infectious_days: 10.0, r0: 2.0 },
  ebola_bioattack: { incubation_days: 8.0, infectious_days: 10.0, r0: 2.5 },
  ebola_ring3: { incubation_days: 8.0, infectious_days: 10.0, r0: 2.5 },
};

// -- Parameter descriptions for info modals ----------------------------------

const PARAM_INFO = {
  country: {
    title: 'Country',
    description: 'Select which African country to simulate, or "All Africa" for the full continent (442 cities).',
    ranges: 'Individual countries have 3-50+ cities. "All Africa" runs all 442 cities but takes significantly longer (~10 min).',
  },
  scenario: {
    title: 'Disease Scenario',
    description: 'The pathogen model to simulate. Each scenario has preset R0, incubation period, infectious period, and infection fatality rate (IFR).',
    ranges: 'COVID-19 scenarios use IFR=0.5% with respiratory transmission. Ebola scenarios use IFR=50% with contact transmission. "Natural" seeds infection in the largest city; "Bioattack" seeds simultaneously in Cairo, Lagos, Nairobi, Kinshasa, and Johannesburg.',
  },
  n_people: {
    title: 'Population Size (Agents per City)',
    description: 'Number of agents simulated in each city\'s discrete-event simulation. This is the DES scale — results are later scaled up to real city populations for the summary.',
    ranges: '500-2,000 = fast but noisy (more stochastic variation). 5,000 = default balance of speed and accuracy. 10,000-50,000 = smoother curves but much slower. Each city runs independently at this population size regardless of its real population.',
  },
  avg_contacts: {
    title: 'Average Contacts',
    description: 'Average number of close contacts per person in the social network (Watts-Strogatz small-world graph). When left at default, this is inferred from UN household size data for the selected country (≈2× avg household size). You can override it manually.',
    ranges: '2-5 = sparse network (rural, socially distant). 6-10 = typical African countries (derived from household size). 15-25 = dense urban environments, crowded housing. 30+ = extremely dense (mass gatherings, slums). Higher values accelerate epidemic spread.',
  },
  rewire_prob: {
    title: 'Rewire Probability',
    description: 'Controls the "small-world" property of the social network. In a Watts-Strogatz graph, this is the probability of rewiring each edge to a random node instead of a neighbor.',
    ranges: '0.0 = pure lattice (very clustered, slow spread). 0.1-0.3 = small-world regime (clustered but with shortcuts, realistic). 0.4 = default. 0.8-1.0 = approaching random graph (fast, uniform spread). Real social networks are typically in the 0.1-0.4 range.',
  },
  daily_contact_rate: {
    title: 'Daily Contact Rate',
    description: 'Fraction of an agent\'s network contacts they actually interact with each day. Models the fact that people don\'t see all their contacts every single day.',
    ranges: '0.1 = very limited daily interaction (strong social distancing). 0.3-0.5 = normal daily activity. 0.7-1.0 = frequent contact (no distancing). Reducing this simulates the effect of social distancing policies.',
  },
  transmission_factor: {
    title: 'Transmission Factor',
    description: 'Multiplier applied to inter-city travel-based transmission. Controls how strongly infection spreads between cities via the gravity model.',
    ranges: '0.01-0.05 = minimal inter-city spread (isolated cities). 0.1-0.3 = moderate coupling (default 0.3). 0.5-1.0 = heavy inter-city transmission. Lower values mean cities experience epidemics more independently; higher values synchronize outbreaks across cities.',
  },
  gravity_scale: {
    title: 'Gravity Scale',
    description: 'Overall scaling factor for the gravity model that computes inter-city travel rates. Travel rate between cities i,j = scale * (pop_i * pop_j) / distance^alpha.',
    ranges: '0.001 = very little travel between cities. 0.01 = default moderate travel. 0.1-1.0 = heavy travel. This controls the absolute magnitude of travelers per day between city pairs.',
  },
  gravity_alpha: {
    title: 'Gravity Alpha (Distance Exponent)',
    description: 'The distance exponent in the gravity model. Higher values mean distance has a stronger deterrent effect on travel — nearby cities interact more, distant cities interact less.',
    ranges: '0.5-1.0 = distance barely matters (global connectivity). 2.0 = default (standard gravity model, quadratic distance decay). 3.0-4.0 = strong distance penalty (very localized spread). Real-world estimates typically range from 1.5 to 2.5.',
  },
  incubation_days: {
    title: 'Incubation Days',
    description: 'Average number of days from exposure to becoming infectious. During incubation, the agent is in the "Exposed" (E) compartment and cannot transmit the disease.',
    ranges: 'COVID-19: ~5 days (default). Ebola: ~10 days. Influenza: ~2 days. Longer incubation means slower epidemic growth but harder to detect via symptom-based screening. Leave blank to use the scenario default.',
  },
  infectious_days: {
    title: 'Infectious Days',
    description: 'Average number of days an agent remains infectious before recovering. During this period they can transmit the disease to contacts.',
    ranges: 'COVID-19: ~9 days (default). Ebola: ~10 days. Influenza: ~5 days. Longer infectious periods mean each case has more opportunities to spread infection. Combined with R0, this determines the per-contact transmission probability.',
  },
  r0_override: {
    title: 'R0 Override',
    description: 'Basic reproduction number — the average number of new infections caused by a single infectious person in a fully susceptible population. Overrides the scenario default if set.',
    ranges: '0.5-0.9 = epidemic dies out (below threshold). 1.0 = epidemic threshold. 1.5-2.0 = moderate (seasonal flu ~1.3, original SARS-CoV-2 ~2.5). 3.0-5.0 = highly transmissible (measles ~12-18 is the extreme). Leave blank to use the scenario default.',
  },
  // -- Healthcare Interaction parameters --
  provider_density: {
    title: 'Provider Density (per 1,000)',
    description: 'Number of healthcare providers per 1,000 people in each city. Providers screen agents for infection and advise isolation when cases are detected.',
    ranges: '0 = no providers (no surveillance). 1-5 = low coverage typical of rural sub-Saharan Africa. 10-20 = moderate urban coverage. 50+ = high-income country levels. Higher density means more cases are detected and advised to isolate, reducing spread.',
  },
  screening_capacity: {
    title: 'Screening Capacity',
    description: 'Maximum number of agents each provider can screen per day. Providers randomly sample from the population and test for active infection.',
    ranges: '1-5 = very limited testing (resource-constrained clinic). 10-20 = default moderate capacity. 50-100 = high-throughput testing (mass screening). Higher capacity means more cases detected per day, improving surveillance accuracy.',
  },
  disclosure_prob: {
    title: 'Disclosure Probability',
    description: 'Probability that a screened infectious agent reveals their symptoms when asked by a provider. Models willingness to disclose, symptom awareness, and test sensitivity.',
    ranges: '0.0 = screening never detects anyone. 0.3-0.5 = moderate detection (default 0.5). 0.7-0.9 = good diagnostic accuracy. 1.0 = perfect detection. Real-world COVID testing sensitivity was roughly 0.6-0.9 depending on test type and timing.',
  },
  receptivity: {
    title: 'Receptivity (Derived)',
    description: 'Probability that a person accepts and follows provider advice when screened. This value is automatically derived per city from the medical_services_score in the city data (formula: 0.2 + 0.6 × score/100). Cities with better healthcare infrastructure have higher receptivity.',
    ranges: '0.2 = minimum (very low trust/access, score=0). 0.5 = moderate (score ~50). 0.8 = maximum (high trust/access, score=100). Default ~0.6 for most cities. You can override this with a uniform value using "Receptivity Override" below.',
  },
  receptivity_override: {
    title: 'Receptivity Override',
    description: 'Manually set a uniform receptivity for all cities, overriding the per-city values derived from medical service scores. Leave blank to use the automatically derived per-city values.',
    ranges: '0.0 = nobody follows provider advice. 0.3 = low compliance (distrust, access barriers). 0.6 = moderate (default derived). 0.8-1.0 = high compliance (strong public health trust). Leave blank to use per-city medical-score-derived values.',
  },
  base_isolation_prob: {
    title: 'Base Isolation Probability',
    description: 'Probability that an infectious agent voluntarily self-isolates each day WITHOUT provider advice. Models baseline behavior change from public awareness, symptoms, or social norms.',
    ranges: '0.0 = no voluntary isolation (default — worst case). 0.05-0.1 = minimal self-awareness. 0.2-0.4 = moderate voluntary response (people feel sick and stay home). 0.5+ = strong voluntary compliance. Even small values (0.05) can significantly slow epidemics.',
  },
  advised_isolation_prob: {
    title: 'Advised Isolation Probability',
    description: 'Probability that a detected infectious agent follows provider advice to isolate each day. Only applies after a provider has screened and identified the agent and the agent accepted the advice (receptivity).',
    ranges: '0.0 = advice is ignored. 0.2-0.4 = default moderate compliance. 0.6-0.8 = good compliance (effective public health messaging). 1.0 = perfect compliance. This is the key mechanism by which providers reduce transmission.',
  },
  advice_decay_prob: {
    title: 'Advice Decay Probability',
    description: 'Daily probability that an agent who was advised to isolate stops complying. Models "isolation fatigue" — people gradually returning to normal behavior despite being told to stay home.',
    ranges: '0.0 = once advised, agents always comply (unrealistic). 0.01-0.05 = default slow decay (avg 20-100 days of compliance). 0.1-0.2 = rapid fatigue (avg 5-10 days). 0.5 = very poor adherence (avg 2 days). Higher values undermine the surveillance system.',
  },
  base_care_prob: {
    title: 'Base Care-Seeking Probability (Not Yet Implemented)',
    description: 'Probability that an infectious agent seeks medical care each day without having been advised by a provider. In module 003, this modeled spontaneous care-seeking behavior driven by symptom severity.',
    ranges: '0.0 = no spontaneous care-seeking (default). 0.1-0.3 = moderate self-referral. 0.5+ = high care-seeking. This parameter existed in the rule-based behavior module (003) but has not yet been carried into the current DES engine (005). It is shown here for reference.',
  },
  advised_care_prob: {
    title: 'Advised Care-Seeking Probability (Not Yet Implemented)',
    description: 'Probability that an agent who has accepted provider advice actively seeks further medical care each day. In module 003, this modeled the behavioral shift toward treatment after provider interaction.',
    ranges: '0.0 = no care-seeking even after advice. 0.5 = moderate (default in module 003). 1.0 = always seeks care. This parameter existed in the rule-based behavior module (003) but has not yet been carried into the current DES engine (005). It is shown here for reference.',
  },
  // -- Simulation Control --
  days: {
    title: 'Simulation Days',
    description: 'Total number of days to simulate. The model steps forward one day at a time, running transmission, screening, travel coupling, and state transitions each day.',
    ranges: '10-50 = quick test run (early epidemic only). 100-200 = captures initial wave. 400 = default (captures full epidemic arc for most scenarios). 600-1000 = needed for slow-spreading or multi-wave scenarios. Longer runs take proportionally more time.',
  },
  seed_fraction: {
    title: 'Seed Fraction',
    description: 'Fraction of the city population initially infected on day 0 in each seed city. Controls how many "patient zeros" start the epidemic.',
    ranges: '0.0001 = 1 in 10,000 (very few initial cases). 0.001 = 1 in 1,000 (5 agents at N=5,000). 0.002 = default (10 agents at N=5,000). 0.01 = 1% (50 agents). Higher values make the epidemic more robust to stochastic extinction but less realistic for natural outbreaks.',
  },
  random_seed: {
    title: 'Random Seed',
    description: 'Seed for the random number generator. Using the same seed with the same parameters produces identical results. Change this to explore stochastic variation between runs.',
    ranges: 'Any integer. Different seeds produce different epidemic trajectories due to stochastic network generation and transmission events. Some seeds may produce mild epidemics, others severe — this is realistic stochastic variation.',
  },
  // Supply chain parameters
  enable_supply_chain: {
    title: 'Enable Supply Chain',
    description: 'Enable finite resource tracking: hospital beds, PPE, diagnostics (swabs/reagents), vaccines, and therapeutic pills. Resources are consumed during screening and care, with three-tier replenishment (city, country, continent).',
    ranges: 'Off = unlimited resources (default). On = resources are finite and can run out, affecting screening capacity and patient care.',
  },
  beds_per_hospital: {
    title: 'Beds per Hospital',
    description: 'Number of hospital beds per hospital facility. Combined with facility counts from the city data to derive initial bed capacity per city.',
    ranges: '50-200 is typical for African hospitals. Default: 120. Beds are capacity-limited: patients occupy beds during care and release them on recovery or death.',
  },
  beds_per_clinic: {
    title: 'Beds per Clinic',
    description: 'Number of beds per clinic facility. Clinics provide fewer beds than hospitals but are more numerous in many cities.',
    ranges: '2-20 is typical. Default: 8. Some cities have many clinics (e.g., Kinshasa: 849) which can provide significant bed capacity.',
  },
  ppe_sets_per_facility: {
    title: 'PPE Sets per Facility',
    description: 'Initial stock of PPE (masks, gloves, gowns) per hospital or clinic. Consumed during screening (1 per test) and patient care (2 per care-day).',
    ranges: '100-1000. Default: 500. PPE stockouts halt screening and reduce care quality.',
  },
  swabs_per_lab: {
    title: 'Swabs per Lab',
    description: 'Initial stock of diagnostic swabs per laboratory. Consumed 1 per screening test.',
    ranges: '500-5000. Default: 1000. Swab stockouts halt diagnostic screening.',
  },
  reagents_per_lab: {
    title: 'Reagents per Lab',
    description: 'Initial stock of testing reagents per laboratory. Consumed 1 per screening test.',
    ranges: '1000-10000. Default: 2000. Reagent stockouts halt diagnostic screening.',
  },
  lead_time_mean_days: {
    title: 'Lead Time (Days)',
    description: 'Average number of days for country-level supply orders to arrive. Uses Gamma distribution (CV ~0.5) for realistic variation.',
    ranges: '3-30 days. Default: 7. Continent-level deployments take ~2x longer. Shorter lead times reduce stockout duration.',
  },
  continent_vaccine_stockpile: {
    title: 'Continent Vaccine Stockpile',
    description: 'Total vaccine doses available at the continental level for deployment to countries in need. Deployed weekly to countries below critical thresholds.',
    ranges: '0 = no vaccines (default). 100,000-10,000,000 for meaningful coverage. Vaccines reduce susceptibility by 70% for vaccinated individuals.',
  },
  continent_pill_stockpile: {
    title: 'Continent Pill Stockpile',
    description: 'Total therapeutic pills available at the continental level. Deployed weekly. Consumed 1 per patient-day during care.',
    ranges: '0 = no pills (default). 100,000-10,000,000 for meaningful supply.',
  },
};


// -- Info Modal ---------------------------------------------------------------

function InfoModal({ paramKey, onClose }) {
  const info = PARAM_INFO[paramKey];
  if (!info) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl max-w-lg w-full mx-4 overflow-hidden animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-emerald-500" />
            <h3 className="font-semibold text-slate-800">{info.title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">What it does</h4>
            <p className="text-sm text-slate-600 leading-relaxed">{info.description}</p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Value ranges</h4>
            <p className="text-sm text-slate-600 leading-relaxed">{info.ranges}</p>
          </div>
        </div>
        <div className="px-5 py-3 bg-slate-50 border-t border-slate-100">
          <button
            onClick={onClose}
            className="w-full py-2 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}


// -- Info button --------------------------------------------------------------

function InfoButton({ paramKey, onClick, compact }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClick(paramKey); }}
      className={`inline-flex items-center justify-center rounded-full border border-slate-200
        text-slate-400 hover:text-emerald-600 hover:border-emerald-300 hover:bg-emerald-50
        transition-colors flex-shrink-0 ${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'}`}
      title="Parameter info"
    >
      <Info className={compact ? 'w-2 h-2' : 'w-2.5 h-2.5'} />
    </button>
  );
}


// -- Field components ---------------------------------------------------------

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = false, compact = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-3.5 h-3.5 text-slate-400" />}
          <span className={`font-medium text-slate-600 ${compact ? 'text-xs' : 'text-sm'}`}>
            {title}
          </span>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>
      {isOpen && (
        <div className={`${compact ? 'p-2' : 'p-3'} space-y-3 bg-white`}>
          {children}
        </div>
      )}
    </div>
  );
}

function RangeField({ label, paramKey, value, onChange, min, max, step, disabled, compact, placeholder, onInfo }) {
  const numValue = value !== null && value !== '' ? Number(value) : '';
  const displayValue = numValue !== '' ? numValue : placeholder || min;
  const isUsingPlaceholder = numValue === '';

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {label}
          </label>
          <InfoButton paramKey={paramKey} onClick={onInfo} compact={compact} />
        </div>
        <span className={`font-mono ${compact ? 'text-[10px]' : 'text-xs'} ${
          isUsingPlaceholder ? 'text-slate-400 italic' : 'text-emerald-600'
        }`}>
          {isUsingPlaceholder ? `${placeholder} (default)` : numValue}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={displayValue}
        onChange={(e) => onChange(paramKey, parseFloat(e.target.value))}
        disabled={disabled}
        className="w-full"
      />
    </div>
  );
}

function DerivedField({ label, paramKey, value, compact, onInfo, note }) {
  return (
    <div className="opacity-70">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {label}
          </label>
          <InfoButton paramKey={paramKey} onClick={onInfo} compact={compact} />
        </div>
        <span className={`font-mono italic ${compact ? 'text-[10px]' : 'text-xs'} text-slate-400`}>
          {value}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={typeof value === 'number' ? value : 0.6}
        disabled
        className="w-full"
      />
      {note && (
        <p className={`mt-0.5 italic text-slate-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
          {note}
        </p>
      )}
    </div>
  );
}

function DisabledField({ label, paramKey, value, compact, onInfo, note }) {
  return (
    <div className="opacity-50">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {label}
          </label>
          <InfoButton paramKey={paramKey} onClick={onInfo} compact={compact} />
        </div>
        <span className={`font-mono italic ${compact ? 'text-[10px]' : 'text-xs'} text-slate-400`}>
          {value}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={typeof value === 'number' ? value : 0}
        disabled
        className="w-full"
      />
      {note && (
        <p className={`mt-0.5 italic text-slate-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
          {note}
        </p>
      )}
    </div>
  );
}

function NumberField({ label, paramKey, value, onChange, min, max, step, disabled, compact, placeholder, onInfo }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
          {label}
        </label>
        <InfoButton paramKey={paramKey} onClick={onInfo} compact={compact} />
      </div>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value !== null && value !== undefined ? value : ''}
        placeholder={placeholder}
        onChange={(e) => {
          const val = e.target.value;
          onChange(paramKey, val === '' ? null : Number(val));
        }}
        disabled={disabled}
        className={`w-full bg-white border border-slate-200 rounded-md px-2.5 text-slate-700
          placeholder-slate-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30
          disabled:opacity-50 disabled:cursor-not-allowed ${compact ? 'py-1 text-xs' : 'py-1.5 text-sm'}`}
      />
    </div>
  );
}

function SelectField({ label, paramKey, value, onChange, options, disabled, compact, onInfo }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
          {label}
        </label>
        <InfoButton paramKey={paramKey} onClick={onInfo} compact={compact} />
      </div>
      <select
        value={value}
        onChange={(e) => onChange(paramKey, e.target.value)}
        disabled={disabled}
        className={`w-full bg-white border border-slate-200 rounded-md px-2.5 text-slate-700
          focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30
          disabled:opacity-50 disabled:cursor-not-allowed ${compact ? 'py-1 text-xs' : 'py-1.5 text-sm'}`}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function ParameterForm({ params, setParams, onRun, disabled, compact }) {
  const [countries, setCountries] = useState([]);
  const [loadingCountries, setLoadingCountries] = useState(false);
  const [infoParam, setInfoParam] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingCountries(true);
    fetch('/api/countries')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch countries');
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          const countryList = Array.isArray(data) ? data : data.countries || [];
          setCountries(countryList);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCountries(['Nigeria', 'Ghana', 'Kenya', 'South Africa', 'Ethiopia', 'Tanzania', 'Uganda', 'Senegal']);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCountries(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleChange = useCallback((key, value) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  }, [setParams]);

  const handleSubmit = useCallback((e) => {
    e.preventDefault();
    onRun();
  }, [onRun]);

  const openInfo = useCallback((paramKey) => {
    setInfoParam(paramKey);
  }, []);

  const closeInfo = useCallback(() => {
    setInfoParam(null);
  }, []);

  const scenarioDefaults = SCENARIO_DEFAULTS[params.scenario] || SCENARIO_DEFAULTS.covid_natural;

  const countryOptions = [
    { value: 'ALL', label: 'All Africa' },
    ...countries.map((c) => {
      const name = typeof c === 'string' ? c : c.name;
      const count = typeof c === 'string' ? '' : ` (${c.city_count} cities)`;
      return { value: name, label: `${name}${count}` };
    }),
  ];

  if (countries.length === 0 && !loadingCountries) {
    countryOptions.push(
      ...['Nigeria', 'Ghana', 'Kenya', 'South Africa', 'Ethiopia', 'Tanzania', 'Uganda', 'Senegal'].map(
        (c) => ({ value: c, label: c })
      )
    );
  }

  return (
    <>
      {infoParam && <InfoModal paramKey={infoParam} onClose={closeInfo} />}

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Primary Controls - always visible */}
        <div className={`card ${compact ? 'p-2' : 'p-4'} space-y-3`}>
          {!compact && (
            <div className="flex items-center gap-2 mb-1">
              <Activity className="w-4 h-4 text-emerald-500" />
              <span className="text-sm font-medium text-slate-700">Primary Controls</span>
            </div>
          )}

          <SelectField
            label="Country"
            paramKey="country"
            value={params.country}
            onChange={handleChange}
            options={countryOptions}
            disabled={disabled}
            compact={compact}
            onInfo={openInfo}
          />

          <SelectField
            label="Disease Scenario"
            paramKey="scenario"
            value={params.scenario}
            onChange={handleChange}
            options={SCENARIOS}
            disabled={disabled}
            compact={compact}
            onInfo={openInfo}
          />
        </div>

        {/* Healthcare Interaction */}
        <CollapsibleSection title="Healthcare Interaction" icon={HeartPulse} defaultOpen={true} compact={compact}>
          <RangeField label="Provider Density (per 1,000)" paramKey="provider_density" value={params.provider_density} onChange={handleChange} min={0} max={200} step={0.5} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Screening Capacity" paramKey="screening_capacity" value={params.screening_capacity} onChange={handleChange} min={1} max={100} step={1} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Disclosure Probability" paramKey="disclosure_prob" value={params.disclosure_prob} onChange={handleChange} min={0} max={1} step={0.05} disabled={disabled} compact={compact} onInfo={openInfo} />

          <DerivedField
            label="Receptivity"
            paramKey="receptivity"
            value="~0.6 (per city)"
            compact={compact}
            onInfo={openInfo}
            note="Derived from city medical service scores: 0.2 + 0.6 × score/100"
          />
          <RangeField label="Receptivity Override" paramKey="receptivity_override" value={params.receptivity_override} onChange={handleChange} min={0} max={1} step={0.05} disabled={disabled} compact={compact} placeholder="auto" onInfo={openInfo} />

          <RangeField label="Base Isolation Probability" paramKey="base_isolation_prob" value={params.base_isolation_prob} onChange={handleChange} min={0} max={1} step={0.01} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Advised Isolation Probability" paramKey="advised_isolation_prob" value={params.advised_isolation_prob} onChange={handleChange} min={0} max={1} step={0.01} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Advice Decay Probability" paramKey="advice_decay_prob" value={params.advice_decay_prob} onChange={handleChange} min={0} max={0.5} step={0.01} disabled={disabled} compact={compact} onInfo={openInfo} />

          <DisabledField
            label="Base Care-Seeking Prob."
            paramKey="base_care_prob"
            value={0.0}
            compact={compact}
            onInfo={openInfo}
            note="Not yet implemented in DES engine (from module 003)"
          />
          <DisabledField
            label="Advised Care-Seeking Prob."
            paramKey="advised_care_prob"
            value={0.5}
            compact={compact}
            onInfo={openInfo}
            note="Not yet implemented in DES engine (from module 003)"
          />
        </CollapsibleSection>

        {/* Collapsible Sections */}
        <CollapsibleSection title="Network Parameters" icon={Sliders} compact={compact}>
          <RangeField label="Population Size" paramKey="n_people" value={params.n_people} onChange={handleChange} min={500} max={50000} step={500} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Average Contacts" paramKey="avg_contacts" value={params.avg_contacts} onChange={handleChange} min={2} max={50} step={1} disabled={disabled} compact={compact} onInfo={openInfo} placeholder="Auto" />
          <RangeField label="Rewire Probability" paramKey="rewire_prob" value={params.rewire_prob} onChange={handleChange} min={0} max={1} step={0.05} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Daily Contact Rate" paramKey="daily_contact_rate" value={params.daily_contact_rate} onChange={handleChange} min={0.1} max={1.0} step={0.05} disabled={disabled} compact={compact} onInfo={openInfo} />
        </CollapsibleSection>

        <CollapsibleSection title="Transmission" icon={Zap} compact={compact}>
          <RangeField label="Transmission Factor" paramKey="transmission_factor" value={params.transmission_factor} onChange={handleChange} min={0.01} max={1.0} step={0.01} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Gravity Scale" paramKey="gravity_scale" value={params.gravity_scale} onChange={handleChange} min={0.001} max={1.0} step={0.001} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Gravity Alpha" paramKey="gravity_alpha" value={params.gravity_alpha} onChange={handleChange} min={0.5} max={4.0} step={0.1} disabled={disabled} compact={compact} onInfo={openInfo} />
        </CollapsibleSection>

        <CollapsibleSection title="Disease Duration" icon={Clock} compact={compact}>
          <RangeField label="Incubation Days" paramKey="incubation_days" value={params.incubation_days} onChange={handleChange} min={1} max={30} step={0.5} disabled={disabled} compact={compact} placeholder={scenarioDefaults.incubation_days} onInfo={openInfo} />
          <RangeField label="Infectious Days" paramKey="infectious_days" value={params.infectious_days} onChange={handleChange} min={1} max={30} step={0.5} disabled={disabled} compact={compact} placeholder={scenarioDefaults.infectious_days} onInfo={openInfo} />
          <RangeField label="R0 Override" paramKey="r0_override" value={params.r0_override} onChange={handleChange} min={0.5} max={15} step={0.1} disabled={disabled} compact={compact} placeholder={scenarioDefaults.r0} onInfo={openInfo} />
        </CollapsibleSection>

        <CollapsibleSection title="Supply Chain Resources" icon={Package} compact={compact}>
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <label className={`text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>
                  Enable Supply Chain
                </label>
                <InfoButton paramKey="enable_supply_chain" onClick={openInfo} compact={compact} />
              </div>
              <button
                type="button"
                onClick={() => handleChange('enable_supply_chain', !params.enable_supply_chain)}
                disabled={disabled}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  params.enable_supply_chain ? 'bg-emerald-500' : 'bg-slate-300'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                    params.enable_supply_chain ? 'translate-x-4' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          </div>
          {params.enable_supply_chain && (
            <>
              <RangeField label="Beds per Hospital" paramKey="beds_per_hospital" value={params.beds_per_hospital} onChange={handleChange} min={10} max={500} step={10} disabled={disabled} compact={compact} onInfo={openInfo} />
              <RangeField label="Beds per Clinic" paramKey="beds_per_clinic" value={params.beds_per_clinic} onChange={handleChange} min={0} max={50} step={1} disabled={disabled} compact={compact} onInfo={openInfo} />
              <RangeField label="PPE Sets per Facility" paramKey="ppe_sets_per_facility" value={params.ppe_sets_per_facility} onChange={handleChange} min={50} max={5000} step={50} disabled={disabled} compact={compact} onInfo={openInfo} />
              <RangeField label="Swabs per Lab" paramKey="swabs_per_lab" value={params.swabs_per_lab} onChange={handleChange} min={100} max={10000} step={100} disabled={disabled} compact={compact} onInfo={openInfo} />
              <RangeField label="Reagents per Lab" paramKey="reagents_per_lab" value={params.reagents_per_lab} onChange={handleChange} min={100} max={20000} step={100} disabled={disabled} compact={compact} onInfo={openInfo} />
              <RangeField label="Lead Time (Days)" paramKey="lead_time_mean_days" value={params.lead_time_mean_days} onChange={handleChange} min={1} max={30} step={1} disabled={disabled} compact={compact} onInfo={openInfo} />
              <NumberField label="Continent Vaccine Stockpile" paramKey="continent_vaccine_stockpile" value={params.continent_vaccine_stockpile} onChange={handleChange} min={0} max={10000000} step={10000} disabled={disabled} compact={compact} onInfo={openInfo} />
              <NumberField label="Continent Pill Stockpile" paramKey="continent_pill_stockpile" value={params.continent_pill_stockpile} onChange={handleChange} min={0} max={10000000} step={10000} disabled={disabled} compact={compact} onInfo={openInfo} />
            </>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="Simulation Control" icon={Activity} compact={compact}>
          <RangeField label="Simulation Days" paramKey="days" value={params.days} onChange={handleChange} min={10} max={1000} step={10} disabled={disabled} compact={compact} onInfo={openInfo} />
          <RangeField label="Seed Fraction" paramKey="seed_fraction" value={params.seed_fraction} onChange={handleChange} min={0.0001} max={0.1} step={0.0001} disabled={disabled} compact={compact} onInfo={openInfo} />
          <NumberField label="Random Seed" paramKey="random_seed" value={params.random_seed} onChange={handleChange} min={0} max={999999} step={1} disabled={disabled} compact={compact} onInfo={openInfo} />
        </CollapsibleSection>

        {/* Run Button */}
        <button
          type="submit"
          disabled={disabled}
          className={`w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed
            ${compact ? 'py-2 text-sm' : 'py-3 text-base'}`}
        >
          {compact ? 'Re-run Simulation' : 'Run Simulation'}
        </button>
      </form>
    </>
  );
}
