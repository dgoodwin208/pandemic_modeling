import React, { useState } from 'react';
import { X, Database, Package, Building2, FlaskConical, Syringe, Pill, AlertTriangle, ChevronDown, ChevronRight, ArrowRight, ArrowDown } from 'lucide-react';
import SupplyChainMap from './SupplyChainMap';

const Section = ({ title, icon: Icon, children, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
      >
        {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
        <Icon className="w-5 h-5 text-emerald-600" />
        <span className="font-semibold text-slate-700">{title}</span>
      </button>
      {isOpen && <div className="p-4 border-t border-slate-200 bg-white">{children}</div>}
    </div>
  );
};

// Flow diagram component
const SimulationFlowDiagram = () => (
  <div className="bg-slate-50 rounded-lg p-6 overflow-x-auto">
    <div className="min-w-[700px]">
      {/* Row 1: Data Sources */}
      <div className="flex items-center justify-center gap-4 mb-4">
        <div className="text-xs text-slate-500 font-medium uppercase tracking-wide w-24">Data Sources</div>
        <div className="flex gap-4">
          <div className="bg-blue-100 border border-blue-300 rounded-lg px-4 py-2 text-center">
            <div className="text-sm font-semibold text-blue-800">Healthsites.io</div>
            <div className="text-xs text-blue-600">62,253 facilities</div>
          </div>
          <div className="bg-blue-100 border border-blue-300 rounded-lg px-4 py-2 text-center">
            <div className="text-sm font-semibold text-blue-800">WHO GHO</div>
            <div className="text-xs text-blue-600">Beds per 10K</div>
          </div>
        </div>
      </div>

      {/* Arrow down */}
      <div className="flex justify-center mb-4">
        <ArrowDown className="w-6 h-6 text-slate-400" />
      </div>

      {/* Row 2: City Data */}
      <div className="flex items-center justify-center gap-4 mb-4">
        <div className="text-xs text-slate-500 font-medium uppercase tracking-wide w-24">City Data</div>
        <div className="flex gap-3">
          <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-1.5 text-xs font-medium text-emerald-700">hospitals</div>
          <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-1.5 text-xs font-medium text-emerald-700">clinics</div>
          <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-1.5 text-xs font-medium text-emerald-700">laboratories</div>
          <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-1.5 text-xs font-medium text-emerald-700">hospital_beds_total</div>
        </div>
      </div>

      {/* Arrow down */}
      <div className="flex justify-center mb-4">
        <ArrowDown className="w-6 h-6 text-slate-400" />
      </div>

      {/* Row 3: Resource Derivation */}
      <div className="flex items-center justify-center gap-4 mb-4">
        <div className="text-xs text-slate-500 font-medium uppercase tracking-wide w-24">Initialization</div>
        <div className="bg-white border-2 border-slate-300 rounded-lg p-4">
          <div className="text-sm font-semibold text-slate-700 mb-2">derive_city_resources()</div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
            <div><span className="text-slate-500">beds</span> = hospital_beds_total</div>
            <div><span className="text-slate-500">ppe</span> = (hospitals + clinics) × 500</div>
            <div><span className="text-slate-500">swabs</span> = laboratories × 1,000</div>
            <div><span className="text-slate-500">reagents</span> = laboratories × 2,000</div>
            <div><span className="text-slate-500">vaccines</span> = 0 (push-deployed)</div>
            <div><span className="text-slate-500">pills</span> = 0 (push-deployed)</div>
          </div>
        </div>
      </div>

      {/* Arrow down */}
      <div className="flex justify-center mb-4">
        <ArrowDown className="w-6 h-6 text-slate-400" />
      </div>

      {/* Row 4: Simulation Resources */}
      <div className="flex items-center justify-center gap-4 mb-4">
        <div className="text-xs text-slate-500 font-medium uppercase tracking-wide w-24">Simulation</div>
        <div className="flex gap-3">
          <div className="bg-red-100 border border-red-300 rounded-lg px-3 py-2 text-center">
            <Building2 className="w-4 h-4 text-red-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-red-700">Beds</div>
            <div className="text-[10px] text-red-600">capacity</div>
          </div>
          <div className="bg-amber-100 border border-amber-300 rounded-lg px-3 py-2 text-center">
            <Package className="w-4 h-4 text-amber-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-amber-700">PPE</div>
            <div className="text-[10px] text-amber-600">consumed</div>
          </div>
          <div className="bg-blue-100 border border-blue-300 rounded-lg px-3 py-2 text-center">
            <FlaskConical className="w-4 h-4 text-blue-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-blue-700">Swabs</div>
            <div className="text-[10px] text-blue-600">consumed</div>
          </div>
          <div className="bg-purple-100 border border-purple-300 rounded-lg px-3 py-2 text-center">
            <FlaskConical className="w-4 h-4 text-purple-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-purple-700">Reagents</div>
            <div className="text-[10px] text-purple-600">consumed</div>
          </div>
          <div className="bg-emerald-100 border border-emerald-300 rounded-lg px-3 py-2 text-center">
            <Syringe className="w-4 h-4 text-emerald-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-emerald-700">Vaccines</div>
            <div className="text-[10px] text-emerald-600">deployed</div>
          </div>
          <div className="bg-pink-100 border border-pink-300 rounded-lg px-3 py-2 text-center">
            <Pill className="w-4 h-4 text-pink-600 mx-auto mb-1" />
            <div className="text-xs font-semibold text-pink-700">Pills</div>
            <div className="text-[10px] text-pink-600">deployed</div>
          </div>
        </div>
      </div>

      {/* Arrow down */}
      <div className="flex justify-center mb-4">
        <ArrowDown className="w-6 h-6 text-slate-400" />
      </div>

      {/* Row 5: Consumption */}
      <div className="flex items-center justify-center gap-4">
        <div className="text-xs text-slate-500 font-medium uppercase tracking-wide w-24">Consumption</div>
        <div className="bg-slate-100 border border-slate-300 rounded-lg p-3 text-xs">
          <div className="grid grid-cols-3 gap-4">
            <div><span className="font-medium">Screening:</span> 1 PPE + 1 swab + 1 reagent</div>
            <div><span className="font-medium">Hospital care:</span> 2 PPE + 1 pill per day</div>
            <div><span className="font-medium">Beds:</span> occupied while in care</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default function SupplyChainDataModel({ onClose, asTab = false }) {
  const content = (
    <>
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50 border border-blue-200">
            <Database className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-800">Supply Chain Data Model</h2>
            <p className="text-xs text-slate-500">How resource constraints work in the simulation</p>
          </div>
        </div>
        {!asTab && onClose && (
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-6 space-y-4">

        {/* Simulation Flow Diagram */}
        <Section title="How Supply Chain Data Flows Into Simulation" icon={Database} defaultOpen={true}>
          <p className="text-sm text-slate-600 mb-4">
            This diagram shows exactly how external data sources are transformed into simulation resources.
            Only the fields shown here are actually used by the simulation engine.
          </p>
          <SimulationFlowDiagram />
        </Section>

        {/* Data Sources - with real citations */}
        <Section title="Data Sources" icon={Database} defaultOpen={true}>
          <div className="space-y-4">
            <div className="border-l-4 border-blue-400 pl-4 py-2">
              <h4 className="font-semibold text-slate-800">Healthsites.io</h4>
              <p className="text-sm text-slate-600 mt-1">
                Geocoded health facility database with 62,253 facilities across Africa.
                Provides: <code className="bg-slate-100 px-1 rounded">hospitals</code>,
                <code className="bg-slate-100 px-1 rounded">clinics</code>,
                <code className="bg-slate-100 px-1 rounded">laboratories</code>,
                <code className="bg-slate-100 px-1 rounded">pharmacies</code> counts per city.
              </p>
              <p className="text-xs text-blue-600 mt-1">
                Source: <a href="https://healthsites.io" target="_blank" rel="noopener noreferrer" className="underline">healthsites.io</a> (OpenStreetMap derivative)
              </p>
            </div>

            <div className="border-l-4 border-emerald-400 pl-4 py-2">
              <h4 className="font-semibold text-slate-800">WHO Global Health Observatory</h4>
              <p className="text-sm text-slate-600 mt-1">
                Country-level hospital beds per 10,000 population, allocated to cities
                proportionally by hospital count.
              </p>
              <p className="text-xs text-emerald-600 mt-1">
                Source: <a href="https://www.who.int/data/gho" target="_blank" rel="noopener noreferrer" className="underline">WHO GHO API</a>
              </p>
            </div>

            <div className="border-l-4 border-amber-400 pl-4 py-2">
              <h4 className="font-semibold text-slate-800">Derived Values (Model Parameters)</h4>
              <p className="text-sm text-slate-600 mt-1">
                These are configurable model parameters, not external data:
              </p>
              <ul className="text-sm text-slate-600 mt-2 space-y-1 ml-4 list-disc">
                <li><code className="bg-slate-100 px-1 rounded">ppe_sets_per_facility</code> = 500 (default)</li>
                <li><code className="bg-slate-100 px-1 rounded">swabs_per_lab</code> = 1,000 (default)</li>
                <li><code className="bg-slate-100 px-1 rounded">reagents_per_lab</code> = 2,000 (default)</li>
              </ul>
              <p className="text-xs text-amber-600 mt-2">
                These are assumptions, not measured data. Adjustable in simulation parameters.
              </p>
            </div>
          </div>
        </Section>

        {/* Resource Types */}
        <Section title="Resource Types in Simulation" icon={Package}>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Building2 className="w-5 h-5 text-red-600" />
                  <h4 className="font-semibold text-red-800">Hospital Beds</h4>
                </div>
                <p className="text-sm text-red-700 mb-2">Capacity-limited resource</p>
                <ul className="text-xs text-red-600 space-y-1">
                  <li><strong>Source:</strong> WHO GHO (downscaled)</li>
                  <li><strong>Behavior:</strong> Patients queue when full</li>
                  <li><strong>Impact:</strong> Waiting increases mortality (+5%/day)</li>
                </ul>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Package className="w-5 h-5 text-amber-600" />
                  <h4 className="font-semibold text-amber-800">PPE</h4>
                </div>
                <p className="text-sm text-amber-700 mb-2">Consumable resource</p>
                <ul className="text-xs text-amber-600 space-y-1">
                  <li><strong>Source:</strong> Derived (facilities × 500)</li>
                  <li><strong>Consumed:</strong> 1/screening, 2/care-day</li>
                  <li><strong>Replenishment:</strong> Country redistribution</li>
                </ul>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <FlaskConical className="w-5 h-5 text-blue-600" />
                  <h4 className="font-semibold text-blue-800">Swabs & Reagents</h4>
                </div>
                <p className="text-sm text-blue-700 mb-2">Consumable resources</p>
                <ul className="text-xs text-blue-600 space-y-1">
                  <li><strong>Source:</strong> Derived (labs × 1K/2K)</li>
                  <li><strong>Consumed:</strong> 1 each per diagnostic test</li>
                  <li><strong>Replenishment:</strong> Country redistribution</li>
                </ul>
              </div>

              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Syringe className="w-5 h-5 text-emerald-600" />
                  <h4 className="font-semibold text-emerald-800">Vaccines & Pills</h4>
                </div>
                <p className="text-sm text-emerald-700 mb-2">Push-deployed from central reserves</p>
                <ul className="text-xs text-emerald-600 space-y-1">
                  <li><strong>Source:</strong> Continental stockpile (configurable)</li>
                  <li><strong>Initial:</strong> 0 in all cities</li>
                  <li><strong>Deployment:</strong> After manufacturing ramp-up (120+ days)</li>
                </ul>
              </div>
            </div>
          </div>
        </Section>

        {/* Interactive Map */}
        <Section title="Healthcare Facility Map" icon={Building2}>
          <p className="text-sm text-slate-600 mb-4">
            Visualize the healthcare facilities used to initialize supply chain resources.
            Only metrics actually used by the simulation are shown.
          </p>
          <SupplyChainMap />
        </Section>

        {/* Limitations */}
        <Section title="Known Limitations" icon={AlertTriangle}>
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <h4 className="font-semibold text-amber-800 text-sm mb-1">Hospital Bed Estimates</h4>
              <p className="text-xs text-amber-700">
                City-level bed counts are estimated from WHO country totals, weighted by local hospital density.
                Actual bed availability may vary from these estimates.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <h4 className="font-semibold text-amber-800 text-sm mb-1">Resource Multipliers are Assumptions</h4>
              <p className="text-xs text-amber-700">
                The values 500 PPE/facility, 1000 swabs/lab, 2000 reagents/lab are model parameters,
                not measured data. These can be adjusted in simulation settings to test sensitivity.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <h4 className="font-semibold text-amber-800 text-sm mb-1">Urban Bias</h4>
              <p className="text-xs text-amber-700">
                The 442 cities represent major urban centers. ~55% of Africa's population in rural
                areas is not directly modeled. Rural healthcare access patterns differ significantly.
              </p>
            </div>
          </div>
        </Section>

      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
        <p className="text-xs text-slate-500">
          Facility data: Healthsites.io | Bed data: WHO GHO | Model v1.0
        </p>
        {!asTab && onClose && (
          <button onClick={onClose} className="btn-secondary text-sm">Close</button>
        )}
      </div>
    </>
  );

  if (asTab) {
    return (
      <div className="max-w-5xl mx-auto py-6 px-4">
        <div className="card overflow-hidden">{content}</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-6 overflow-y-auto bg-black/30 backdrop-blur-sm animate-fade-in">
      <div className="card max-w-5xl w-full my-8 max-h-[90vh] overflow-hidden flex flex-col">{content}</div>
    </div>
  );
}
