import { useState, useCallback, useRef, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Text, Line } from '@react-three/drei'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import * as THREE from 'three'
import './App.css'

// ============================================================================
// SHARED CONFIG
// ============================================================================

const STATE_COLORS = {
  S: '#22c55e', E: '#fbbf24', I_minor: '#f97316', I_needs: '#ef4444',
  I_care: '#ec4899', R: '#3b82f6', D: '#1f2937',
}

// ============================================================================
// COMPLETE OBJECT MODEL with relationships
// ============================================================================

const CLASSES = {
  Person: {
    color: '#22c55e',
    file: 'city_des_extended.py',
    note: 'Implicit (indexed arrays)',
    attributes: [
      { name: '_states[idx]', type: 'int8', access: 'rw' },
      { name: '_neighbors[idx]', type: 'list[int]', access: 'r' },
      { name: '_has_phone[idx]', type: 'bool', access: 'r' },
      { name: '_provider_advised[idx]', type: 'bool', access: 'rw' },
    ],
    collections: [
      { name: '_vaccinated', type: 'set[int]', access: 'rw' },
      { name: '_detected_ever', type: 'set[int]', access: 'rw' },
      { name: '_detected_day', type: 'dict[int,int]', access: 'rw' },
      { name: '_contact_candidates', type: 'set[int]', access: 'rw' },
    ],
  },
  CityDES: {
    color: '#8b5cf6',
    file: 'city_des_extended.py',
    attributes: [
      { name: 'env', type: 'simpy.Environment', access: 'rw' },
      { name: 'n_people', type: 'int', access: 'r' },
      { name: 'transmission_prob', type: 'float', access: 'r' },
      { name: 'incubation_days', type: 'float', access: 'r' },
      { name: 'infectious_days', type: 'float', access: 'r' },
      { name: '_severe_fraction', type: 'float', access: 'r' },
      { name: '_care_survival_prob', type: 'float', access: 'r' },
    ],
    arrays: [
      { name: '_counts[7]', type: 'list[int]', access: 'rw', desc: '[S,E,I_minor,I_needs,I_care,R,D]' },
      { name: '_obs_counts[7]', type: 'list[int]', access: 'rw', desc: 'Detected only' },
    ],
    providers: [
      { name: '_n_providers', type: 'int', access: 'r' },
      { name: '_screening_capacity', type: 'int', access: 'r' },
      { name: '_disclosure_prob', type: 'float', access: 'r' },
      { name: '_receptivity', type: 'float', access: 'r' },
    ],
    refs: [
      { name: '_supply', type: 'CitySupply?', access: 'r' },
    ],
    methods: ['step()', 'inject_exposed()', 'run_provider_screening()', 'apply_vaccinations()', '_transition()'],
  },
  CitySupply: {
    color: '#f59e0b',
    file: 'supply_chain.py',
    beds: [
      { name: 'beds_total', type: 'int', access: 'r' },
      { name: 'beds_occupied', type: 'int', access: 'rw' },
    ],
    consumables: [
      { name: 'ppe', type: 'int', access: 'rw' },
      { name: 'swabs', type: 'int', access: 'rw' },
      { name: 'reagents', type: 'int', access: 'rw' },
      { name: 'vaccines', type: 'int', access: 'rw' },
      { name: 'pills', type: 'int', access: 'rw' },
    ],
    tracking: [
      { name: '_pending', type: 'list[PendingShipment]', access: 'rw' },
      { name: '_burn_rate_ema', type: 'dict[str,float]', access: 'rw' },
      { name: '_daily_consumed', type: 'dict[str,int]', access: 'rw' },
    ],
    methods: ['receive_shipments()', 'try_admit()', 'release_bed()', 'try_consume()', 'add_resource()', 'record_day()'],
  },
  CountrySupplyManager: {
    color: '#3b82f6',
    file: 'supply_chain.py',
    attributes: [
      { name: 'defaults', type: 'ResourceDefaults', access: 'r' },
      { name: 'strategy', type: 'AllocationStrategy?', access: 'r' },
      { name: '_orders_placed', type: 'dict[str,int]', access: 'rw' },
    ],
    refs: [
      { name: 'cities', type: 'dict[str, CitySupply]', access: 'rw' },
    ],
    methods: ['update_and_redistribute()', '_redistribute_resource()'],
  },
  ContinentSupplyManager: {
    color: '#ec4899',
    file: 'supply_chain.py',
    attributes: [
      { name: 'reserves', type: 'dict[str,int]', access: 'rw' },
      { name: 'manufacturing_sites', type: 'list[str]', access: 'r' },
      { name: 'manufacturing_lead_days', type: 'int', access: 'r' },
      { name: '_max_daily_production', type: 'int', access: 'r' },
      { name: 'cumulative_vaccine_production', type: 'int', access: 'rw' },
    ],
    refs: [
      { name: 'countries', type: 'dict[str, CountrySupplyManager]', access: 'rw' },
    ],
    methods: ['produce_vaccines()', 'deploy_reserves()'],
  },
  PendingShipment: {
    color: '#64748b',
    file: 'supply_chain.py',
    note: 'dataclass',
    attributes: [
      { name: 'resource', type: 'str', access: 'r' },
      { name: 'amount', type: 'int', access: 'r' },
      { name: 'arrival_day', type: 'int', access: 'r' },
      { name: 'source', type: 'str', access: 'r' },
    ],
  },
  SimulationParams: {
    color: '#06b6d4',
    file: 'simulation.py',
    note: 'dataclass (66 fields)',
    groups: {
      epidemic: ['scenario', 'incubation_days', 'infectious_days', 'r0_override', 'transmission_factor'],
      network: ['avg_contacts', 'rewire_prob', 'daily_contact_rate', 'p_random'],
      provider: ['provider_density', 'screening_capacity', 'disclosure_prob', 'receptivity_override'],
      behavioral: ['base_isolation_prob', 'advised_isolation_prob', 'advice_decay_prob'],
      supply: ['enable_supply_chain', 'allocation_strategy', 'beds_per_hospital', 'resource_multiplier'],
    },
  },
  DualViewResult: {
    color: '#a855f7',
    file: 'simulation.py',
    note: 'Output dataclass',
    arrays: [
      { name: 'actual_S/E/I/R/D', type: 'np.ndarray', access: 'w', desc: '(n_cities, days+1)' },
      { name: 'observed_S/E/I/R/D', type: 'np.ndarray', access: 'w', desc: '(n_cities, days+1)' },
      { name: 'resource_*', type: 'np.ndarray', access: 'w', desc: 'beds, ppe, swabs...' },
    ],
    metadata: ['city_names', 'city_coords', 'city_populations', 'scenario_name', 'event_log'],
  },
}

// Relationships: source -> target with label and type
const RELATIONSHIPS = [
  { from: 'CityDES', to: 'Person', label: 'contains N', type: 'composition', desc: 'Agents stored as indexed arrays' },
  { from: 'CityDES', to: 'CitySupply', label: '_supply', type: 'reference', desc: 'Optional resource constraints' },
  { from: 'CountrySupplyManager', to: 'CitySupply', label: 'cities[]', type: 'aggregation', desc: 'Manages multiple cities' },
  { from: 'ContinentSupplyManager', to: 'CountrySupplyManager', label: 'countries[]', type: 'aggregation', desc: 'Manages multiple countries' },
  { from: 'CitySupply', to: 'PendingShipment', label: '_pending[]', type: 'composition', desc: 'In-transit shipments' },
  { from: 'SimulationParams', to: 'CityDES', label: 'configures', type: 'dependency', desc: 'Params initialize CityDES' },
  { from: 'CityDES', to: 'DualViewResult', label: 'outputs to', type: 'dependency', desc: 'Daily snapshots' },
  { from: 'CitySupply', to: 'DualViewResult', label: 'outputs to', type: 'dependency', desc: 'Resource snapshots' },
]

// Data flow: which step causes which object to modify which other object
const DATA_FLOWS = [
  { step: 1, from: 'CityDES', to: 'Person', action: '_transition()', desc: 'State changes via SimPy processes' },
  { step: 1, from: 'Person', to: 'CitySupply', action: 'try_admit()', desc: 'I_needs tries to get bed' },
  { step: 1, from: 'Person', to: 'CitySupply', action: 'try_consume()', desc: 'I_care consumes pills, ppe' },
  { step: 2, from: 'CityDES', to: 'Person', action: 'screening', desc: 'Updates _provider_advised, _detected_*' },
  { step: 2, from: 'CityDES', to: 'CitySupply', action: 'try_consume()', desc: 'Lab tests consume ppe/swabs/reagents' },
  { step: 3, from: 'CityDES', to: 'Person', action: 'vaccinate', desc: 'Adds to _vaccinated set' },
  { step: 3, from: 'CityDES', to: 'CitySupply', action: 'try_consume()', desc: 'Consumes vaccines' },
  { step: 7, from: 'CountrySupplyManager', to: 'CitySupply', action: 'redistribute', desc: 'Moves resources between cities' },
  { step: 7, from: 'ContinentSupplyManager', to: 'CountrySupplyManager', action: 'deploy', desc: 'Weekly reserve deployment' },
  { step: 7, from: 'ContinentSupplyManager', to: 'CitySupply', action: 'add_shipment()', desc: 'Creates PendingShipment' },
]

// ============================================================================
// OOP MODEL VIEW - Class diagram with React Flow
// ============================================================================

function ClassNode({ data }) {
  const cls = CLASSES[data.name]
  if (!cls) return null

  const allAttrs = [
    ...(cls.attributes || []),
    ...(cls.arrays || []),
    ...(cls.beds || []),
    ...(cls.consumables || []),
    ...(cls.tracking || []),
    ...(cls.providers || []),
    ...(cls.collections || []),
    ...(cls.refs || []),
  ]

  return (
    <div className="bg-slate-800 rounded-lg border-2 shadow-lg min-w-[220px] max-w-[280px]" style={{ borderColor: cls.color }}>
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />
      <Handle type="target" position={Position.Left} className="!bg-slate-500" />
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
      <Handle type="source" position={Position.Right} className="!bg-slate-500" />

      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-600" style={{ backgroundColor: cls.color + '30' }}>
        <div className="font-bold text-white text-sm">{data.name}</div>
        <code className="text-[9px] text-slate-400">{cls.file}</code>
        {cls.note && <div className="text-[9px] text-slate-500 italic">{cls.note}</div>}
      </div>

      {/* Attributes */}
      <div className="px-2 py-1.5 max-h-48 overflow-y-auto">
        {/* Grouped display for SimulationParams */}
        {cls.groups ? (
          Object.entries(cls.groups).map(([group, fields]) => (
            <div key={group} className="mb-1">
              <div className="text-[8px] text-slate-500 uppercase">{group}</div>
              {fields.slice(0, 3).map((f, i) => (
                <div key={i} className="text-[10px] text-slate-400 pl-1">{f}</div>
              ))}
              {fields.length > 3 && <div className="text-[9px] text-slate-500 pl-1">+{fields.length - 3} more</div>}
            </div>
          ))
        ) : (
          <>
            {allAttrs.slice(0, 8).map((attr, i) => (
              <div key={i} className="flex items-center gap-1 text-[10px] py-0.5">
                <span className={`w-1.5 h-1.5 rounded-full ${attr.access === 'rw' ? 'bg-amber-400' : attr.access === 'w' ? 'bg-red-400' : 'bg-green-400'}`} />
                <code className="text-slate-300">{attr.name}</code>
                <span className="text-slate-500 text-[9px] ml-auto">{attr.type}</span>
              </div>
            ))}
            {allAttrs.length > 8 && (
              <div className="text-[9px] text-slate-500 text-center py-1">+{allAttrs.length - 8} more</div>
            )}
          </>
        )}

        {/* Methods */}
        {cls.methods && (
          <div className="border-t border-slate-700 mt-1 pt-1">
            {cls.methods.slice(0, 4).map((m, i) => (
              <div key={i} className="text-[9px] text-blue-400">{m}</div>
            ))}
            {cls.methods.length > 4 && <div className="text-[9px] text-slate-500">+{cls.methods.length - 4} more</div>}
          </div>
        )}

        {/* Metadata for DualViewResult */}
        {cls.metadata && (
          <div className="border-t border-slate-700 mt-1 pt-1">
            <div className="text-[8px] text-slate-500 uppercase">metadata</div>
            {cls.metadata.map((m, i) => (
              <div key={i} className="text-[9px] text-slate-400">{m}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const oopNodeTypes = { class: ClassNode }

// Position classes in a logical layout
const oopNodes = [
  // Top tier: Config
  { id: 'SimulationParams', type: 'class', position: { x: 50, y: 20 }, data: { name: 'SimulationParams' } },

  // Middle tier: Core simulation
  { id: 'CityDES', type: 'class', position: { x: 350, y: 100 }, data: { name: 'CityDES' } },
  { id: 'Person', type: 'class', position: { x: 650, y: 100 }, data: { name: 'Person' } },

  // Supply chain tier
  { id: 'CitySupply', type: 'class', position: { x: 350, y: 350 }, data: { name: 'CitySupply' } },
  { id: 'PendingShipment', type: 'class', position: { x: 650, y: 400 }, data: { name: 'PendingShipment' } },

  // Management tier
  { id: 'CountrySupplyManager', type: 'class', position: { x: 100, y: 350 }, data: { name: 'CountrySupplyManager' } },
  { id: 'ContinentSupplyManager', type: 'class', position: { x: 100, y: 550 }, data: { name: 'ContinentSupplyManager' } },

  // Output
  { id: 'DualViewResult', type: 'class', position: { x: 650, y: 250 }, data: { name: 'DualViewResult' } },
]

const oopEdges = RELATIONSHIPS.map((rel, i) => ({
  id: `rel-${i}`,
  source: rel.from,
  target: rel.to,
  label: rel.label,
  type: 'smoothstep',
  animated: rel.type === 'dependency',
  style: {
    stroke: rel.type === 'composition' ? '#22c55e' :
            rel.type === 'aggregation' ? '#3b82f6' :
            rel.type === 'reference' ? '#f59e0b' : '#64748b',
    strokeWidth: rel.type === 'dependency' ? 1 : 2,
    strokeDasharray: rel.type === 'dependency' ? '5,5' : undefined,
  },
  markerEnd: {
    type: rel.type === 'composition' ? MarkerType.ArrowClosed :
          rel.type === 'aggregation' ? MarkerType.Arrow : MarkerType.ArrowClosed,
    color: rel.type === 'composition' ? '#22c55e' :
           rel.type === 'aggregation' ? '#3b82f6' :
           rel.type === 'reference' ? '#f59e0b' : '#64748b',
  },
  labelStyle: { fill: '#94a3b8', fontSize: 10 },
  labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8 },
}))

function OOPModelView() {
  const [nodes, , onNodesChange] = useNodesState(oopNodes)
  const [edges, , onEdgesChange] = useEdgesState(oopEdges)
  const [selectedClass, setSelectedClass] = useState(null)
  const [showFlows, setShowFlows] = useState(false)

  const selectedFlows = selectedClass
    ? DATA_FLOWS.filter(f => f.from === selectedClass || f.to === selectedClass)
    : DATA_FLOWS

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Main diagram */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={oopNodeTypes}
          fitView
          minZoom={0.3}
          maxZoom={1.5}
          onNodeClick={(_, node) => setSelectedClass(node.id)}
          onPaneClick={() => setSelectedClass(null)}
        >
          <Background color="#334155" gap={20} />
          <Controls className="!bg-slate-800 !border-slate-700" />
          <MiniMap
            className="!bg-slate-800"
            nodeColor={(n) => CLASSES[n.id]?.color || '#64748b'}
          />
        </ReactFlow>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-slate-800/90 rounded-lg p-3 text-xs space-y-1">
          <div className="font-semibold text-white mb-2">Relationships</div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-green-500" /> <span className="text-slate-400">Composition (owns)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-blue-500" /> <span className="text-slate-400">Aggregation (has many)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-amber-500" /> <span className="text-slate-400">Reference (uses)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-slate-500 border-dashed border-t" /> <span className="text-slate-400">Dependency (configures/outputs)</span>
          </div>
          <div className="border-t border-slate-600 mt-2 pt-2 font-semibold text-white">Attributes</div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400" /> <span className="text-slate-400">Read-only</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-400" /> <span className="text-slate-400">Read-Write</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-red-400" /> <span className="text-slate-400">Write-only</span>
          </div>
        </div>
      </div>

      {/* Right panel - Data flows */}
      <div className="w-80 bg-slate-900 border-l border-slate-700 flex flex-col">
        <div className="p-3 border-b border-slate-700">
          <h2 className="font-bold text-white text-sm">Data Flows</h2>
          <p className="text-[10px] text-slate-400">How objects modify each other during daily loop</p>
        </div>

        {selectedClass && (
          <div className="p-3 border-b border-slate-700" style={{ backgroundColor: CLASSES[selectedClass]?.color + '20' }}>
            <div className="font-semibold text-white text-sm">{selectedClass}</div>
            <code className="text-[10px] text-slate-400">{CLASSES[selectedClass]?.file}</code>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2">
          {selectedFlows.map((flow, i) => (
            <div
              key={i}
              className="bg-slate-800 rounded p-2 mb-2"
              style={{
                borderLeft: `3px solid ${
                  flow.from === selectedClass ? CLASSES[flow.from]?.color :
                  flow.to === selectedClass ? CLASSES[flow.to]?.color : '#64748b'
                }`
              }}
            >
              <div className="flex items-center gap-1 text-xs mb-1">
                <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: CLASSES[flow.from]?.color + '30', color: CLASSES[flow.from]?.color }}>
                  {flow.from}
                </span>
                <span className="text-slate-500">→</span>
                <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: CLASSES[flow.to]?.color + '30', color: CLASSES[flow.to]?.color }}>
                  {flow.to}
                </span>
                <span className="text-slate-600 text-[10px] ml-auto">Step {flow.step}</span>
              </div>
              <code className="text-[10px] text-blue-400 block">{flow.action}</code>
              <div className="text-[10px] text-slate-500">{flow.desc}</div>
            </div>
          ))}
        </div>

        {/* Relationship details for selected class */}
        {selectedClass && (
          <div className="p-3 border-t border-slate-700">
            <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Relationships</div>
            {RELATIONSHIPS.filter(r => r.from === selectedClass || r.to === selectedClass).map((rel, i) => (
              <div key={i} className="text-xs text-slate-400 mb-1">
                <span className={rel.from === selectedClass ? 'text-white' : ''}>{rel.from}</span>
                <span className="text-slate-600"> → </span>
                <span className={rel.to === selectedClass ? 'text-white' : ''}>{rel.to}</span>
                <span className="text-slate-500 text-[10px] block pl-2">{rel.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// DAILY LOOP VIEW (simplified from before)
// ============================================================================

const DAILY_LOOP_STEPS = [
  { step: 0, name: 'Receive Shipments', color: '#f59e0b', objects: ['CitySupply'], condition: 'if supply_enabled' },
  { step: 1, name: 'Advance SimPy (DES)', color: '#8b5cf6', objects: ['CityDES', 'Person', 'CitySupply'] },
  { step: 2, name: 'Provider Screening', color: '#10b981', objects: ['CityDES', 'Person', 'CitySupply'] },
  { step: 3, name: 'Vaccinations', color: '#ec4899', objects: ['CityDES', 'Person', 'CitySupply'], condition: 'if supply_enabled' },
  { step: 4, name: 'Inter-city Travel', color: '#3b82f6', objects: ['CityDES', 'Person'] },
  { step: 5, name: 'Record ACTUAL', color: '#10b981', objects: ['CityDES', 'DualViewResult'] },
  { step: 6, name: 'Record OBSERVED', color: '#8b5cf6', objects: ['CityDES', 'DualViewResult'] },
  { step: 7, name: 'Supply Chain Update', color: '#f59e0b', objects: ['CitySupply', 'CountrySupplyManager', 'ContinentSupplyManager'], condition: 'if supply_enabled' },
]

function DailyLoopView() {
  const [selectedStep, setSelectedStep] = useState(null)

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-white">Daily Simulation Loop</h2>
            <code className="text-sm text-slate-400">simulation.py:run_absdes_simulation()</code>
          </div>

          <div className="space-y-3">
            {DAILY_LOOP_STEPS.map((step, i) => (
              <div key={i}>
                <div
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${selectedStep === step.step ? 'ring-2 ring-white' : 'hover:ring-1 hover:ring-slate-500'}`}
                  style={{ borderColor: step.color, backgroundColor: step.color + '10' }}
                  onClick={() => setSelectedStep(selectedStep === step.step ? null : step.step)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full text-white flex items-center justify-center font-bold" style={{ backgroundColor: step.color }}>
                      {step.step}
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-white">{step.name}</div>
                      {step.condition && <div className="text-xs text-amber-400">{step.condition}</div>}
                    </div>
                    <div className="flex gap-1">
                      {step.objects.map(obj => (
                        <span key={obj} className="text-[10px] px-2 py-1 rounded" style={{ backgroundColor: CLASSES[obj]?.color + '30', color: CLASSES[obj]?.color }}>
                          {obj}
                        </span>
                      ))}
                    </div>
                  </div>

                  {selectedStep === step.step && (
                    <div className="mt-3 pt-3 border-t border-slate-600">
                      <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Data Flows in this Step</div>
                      <div className="space-y-1">
                        {DATA_FLOWS.filter(f => f.step === step.step).map((flow, j) => (
                          <div key={j} className="flex items-center gap-2 text-xs">
                            <span style={{ color: CLASSES[flow.from]?.color }}>{flow.from}</span>
                            <span className="text-slate-500">→</span>
                            <span style={{ color: CLASSES[flow.to]?.color }}>{flow.to}</span>
                            <code className="text-blue-400 text-[10px]">{flow.action}</code>
                            <span className="text-slate-500 text-[10px] ml-auto">{flow.desc}</span>
                          </div>
                        ))}
                        {DATA_FLOWS.filter(f => f.step === step.step).length === 0 && (
                          <div className="text-xs text-slate-500">Read-only step (no object modifications)</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                {i < DAILY_LOOP_STEPS.length - 1 && (
                  <div className="flex justify-center py-1">
                    <div className="w-0.5 h-6 bg-slate-600" />
                  </div>
                )}
              </div>
            ))}
            <div className="text-center text-slate-500 py-2">↺ next day</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// AGENT INTERROGATOR (3D view - kept compact)
// ============================================================================

const DAYS = 60, TIME_SCALE = 0.12

function generateSampleData(seed = 42) {
  let s = seed
  const rng = () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff }
  const agents = [], n = 30
  for (let i = 0; i < n; i++) {
    const angle = (i / n) * Math.PI * 2 + rng() * 0.3, radius = 2 + rng() * 1.5
    agents.push({ id: i, x: Math.cos(angle) * radius, z: Math.sin(angle) * radius, neighbors: [], timeline: [{ day: 0, state: 'S', event: 'init' }] })
  }
  for (let i = 0; i < n; i++) {
    const numNeighbors = 2 + Math.floor(rng() * 3)
    const distances = agents.map((a, j) => ({ j, dist: Math.hypot(a.x - agents[i].x, a.z - agents[i].z) })).filter(d => d.j !== i).sort((a, b) => a.dist - b.dist)
    for (let k = 0; k < Math.min(numNeighbors, distances.length); k++) {
      const neighbor = distances[k].j
      if (!agents[i].neighbors.includes(neighbor)) agents[i].neighbors.push(neighbor)
      if (!agents[neighbor].neighbors.includes(i)) agents[neighbor].neighbors.push(i)
    }
  }
  const params = { incubation_days: 5, infectious_days: 7, severe_fraction: 0.15, care_survival: 0.85, transmission_prob: 0.08 }
  const stateAtDay = agents.map(() => Array(DAYS + 1).fill('S')), events = []
  stateAtDay[0][0] = 'E'
  agents[0].timeline = [{ day: 0, state: 'E', event: 'seed (patient zero)' }]
  events.push({ day: 0, from: null, to: 0, type: 'seed' })
  const scheduled = [{ day: Math.round(params.incubation_days + (rng() - 0.5) * 2), agent: 0, toState: 'I_minor' }]
  for (let day = 1; day <= DAYS; day++) {
    for (let i = 0; i < n; i++) stateAtDay[i][day] = stateAtDay[i][day - 1]
    for (const s of scheduled.filter(s => s.day === day)) {
      stateAtDay[s.agent][day] = s.toState
      agents[s.agent].timeline.push({ day, state: s.toState, event: s.fromAgent !== undefined ? `infected by ${s.fromAgent}` : `→ ${s.toState}` })
      if (s.fromAgent !== undefined) events.push({ day, from: s.fromAgent, to: s.agent, type: 'transmission' })
      if (s.toState === 'I_minor') scheduled.push({ day: day + Math.round(params.infectious_days + (rng() - 0.5) * 3), agent: s.agent, toState: rng() < params.severe_fraction ? 'I_needs' : 'R' })
      else if (s.toState === 'I_needs') scheduled.push({ day: day + 1 + Math.floor(rng() * 3), agent: s.agent, toState: rng() < 0.7 ? 'I_care' : 'D' })
      else if (s.toState === 'I_care') scheduled.push({ day: day + 3 + Math.floor(rng() * 4), agent: s.agent, toState: rng() < params.care_survival ? 'R' : 'D' })
    }
    for (let i = 0; i < n; i++) {
      if (stateAtDay[i][day] === 'I_minor') {
        for (const nb of agents[i].neighbors) {
          if (stateAtDay[nb][day] === 'S' && rng() < params.transmission_prob) {
            stateAtDay[nb][day] = 'E'
            agents[nb].timeline.push({ day, state: 'E', event: `infected by ${i}`, source: i })
            events.push({ day, from: i, to: nb, type: 'transmission' })
            scheduled.push({ day: day + Math.round(params.incubation_days + (rng() - 0.5) * 2), agent: nb, toState: 'I_minor' })
          }
        }
      }
    }
  }
  for (let i = 0; i < n; i++) agents[i].stateAtDay = stateAtDay[i]
  return { agents, events, params }
}

function AgentColumn({ agent, selectedDay, isSelected, onClick, visible }) {
  if (!visible) return null
  const segments = []
  let currentState = agent.stateAtDay[0], segmentStart = 0
  for (let day = 1; day <= DAYS; day++) { if (agent.stateAtDay[day] !== currentState) { segments.push({ state: currentState, startDay: segmentStart, endDay: day }); currentState = agent.stateAtDay[day]; segmentStart = day } }
  segments.push({ state: currentState, startDay: segmentStart, endDay: DAYS })
  return (
    <group position={[agent.x, 0, agent.z]}>
      {segments.map((seg, i) => (<mesh key={i} position={[0, (seg.startDay + (seg.endDay - seg.startDay) / 2) * TIME_SCALE, 0]} onClick={(e) => { e.stopPropagation(); onClick(agent) }}><cylinderGeometry args={[0.12, 0.12, (seg.endDay - seg.startDay) * TIME_SCALE, 12]} /><meshStandardMaterial color={STATE_COLORS[seg.state]} emissive={isSelected ? STATE_COLORS[seg.state] : '#000'} emissiveIntensity={isSelected ? 0.4 : 0} /></mesh>))}
      <Text position={[0, -0.3, 0]} fontSize={0.2} color={isSelected ? '#fff' : '#64748b'} anchorX="center" rotation={[-Math.PI / 2, 0, 0]}>{agent.id}</Text>
      <mesh position={[0, selectedDay * TIME_SCALE, 0]}><sphereGeometry args={[0.18, 16, 16]} /><meshStandardMaterial color={STATE_COLORS[agent.stateAtDay[selectedDay]]} emissive={STATE_COLORS[agent.stateAtDay[selectedDay]]} emissiveIntensity={0.6} /></mesh>
    </group>
  )
}

function NetworkFloor({ agents, visibleIds }) {
  const lines = [], seen = new Set()
  for (const agent of agents) { if (!visibleIds.has(agent.id)) continue; for (const nid of agent.neighbors) { if (!visibleIds.has(nid)) continue; const key = [Math.min(agent.id, nid), Math.max(agent.id, nid)].join('-'); if (seen.has(key)) continue; seen.add(key); lines.push({ from: agent, to: agents[nid], key }) } }
  return (<group><gridHelper args={[10, 20, '#1e293b', '#1e293b']} position={[0, -0.01, 0]} />{lines.map(({ from, to, key }) => (<Line key={key} points={[[from.x, 0, from.z], [to.x, 0, to.z]]} color="#475569" lineWidth={1.5} />))}</group>)
}

function TransmissionLines({ events, agents, selectedDay, visibleIds }) {
  return (<>{events.filter(e => e.type === 'transmission' && e.day <= selectedDay && visibleIds.has(e.from) && visibleIds.has(e.to)).map((ev, i) => (<Line key={i} points={[[agents[ev.from].x, ev.day * TIME_SCALE, agents[ev.from].z], [agents[ev.to].x, ev.day * TIME_SCALE, agents[ev.to].z]]} color="#ef4444" lineWidth={2} />))}</>)
}

function TimeAxis({ selectedDay }) {
  const maxY = DAYS * TIME_SCALE
  return (<group position={[-4, 0, -4]}><Line points={[[0, 0, 0], [0, maxY, 0]]} color="#64748b" lineWidth={2} />{[0, 10, 20, 30, 40, 50, 60].map(day => (<group key={day} position={[0, day * TIME_SCALE, 0]}><Line points={[[-0.1, 0, 0], [0.1, 0, 0]]} color="#64748b" lineWidth={1} /><Text position={[-0.4, 0, 0]} fontSize={0.18} color="#94a3b8" anchorX="right">{day}</Text></group>))}<mesh position={[4, selectedDay * TIME_SCALE, 4]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[10, 10]} /><meshBasicMaterial color="#3b82f6" opacity={0.08} transparent side={THREE.DoubleSide} /></mesh></group>)
}

function Scene3D({ data, selectedDay, selectedAgent, setSelectedAgent, visibleIds }) {
  return (<><ambientLight intensity={0.5} /><directionalLight position={[5, 10, 5]} intensity={0.8} /><NetworkFloor agents={data.agents} visibleIds={visibleIds} /><TimeAxis selectedDay={selectedDay} /><TransmissionLines events={data.events} agents={data.agents} selectedDay={selectedDay} visibleIds={visibleIds} />{data.agents.map(agent => (<AgentColumn key={agent.id} agent={agent} selectedDay={selectedDay} isSelected={selectedAgent?.id === agent.id} onClick={setSelectedAgent} visible={visibleIds.has(agent.id)} />))}<OrbitControls target={[0, DAYS * TIME_SCALE * 0.4, 0]} maxPolarAngle={Math.PI * 0.85} /></>)
}

function AgentInterrogatorView() {
  const [data] = useState(() => generateSampleData())
  const [selectedDay, setSelectedDay] = useState(0)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedAgents, setSelectedAgents] = useState(new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))
  const [filterMode, setFilterMode] = useState('custom')
  const animRef = useRef()
  const visibleIds = useMemo(() => filterMode === 'all' ? new Set(data.agents.map(a => a.id)) : filterMode === 'infected' ? new Set(data.agents.filter(a => a.timeline.some(t => t.state !== 'S')).map(a => a.id)) : selectedAgents, [filterMode, selectedAgents, data.agents])
  const animate = useCallback(() => { setSelectedDay(d => { if (d >= DAYS) { setIsPlaying(false); return DAYS } return d + 1 }); animRef.current = setTimeout(animate, 150) }, [])
  const togglePlay = useCallback(() => { if (isPlaying) { clearTimeout(animRef.current); setIsPlaying(false) } else { if (selectedDay >= DAYS) setSelectedDay(0); setIsPlaying(true); animate() } }, [isPlaying, selectedDay, animate])
  const toggleAgent = (id) => { const s = new Set(selectedAgents); s.has(id) ? s.delete(id) : s.add(id); setSelectedAgents(s); setFilterMode('custom') }

  return (
    <div className="flex flex-1">
      <div className="w-72 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-3 border-b border-slate-700"><h2 className="font-bold text-white text-sm">Agent Selection</h2></div>
        <div className="p-2 border-b border-slate-700 flex gap-1">
          {[['all', 'All'], ['infected', 'Infected'], ['custom', 'Custom']].map(([m, l]) => (<button key={m} onClick={() => setFilterMode(m)} className={`px-2 py-1 rounded text-xs ${filterMode === m ? 'bg-emerald-500 text-white' : 'bg-slate-700 text-slate-300'}`}>{l}</button>))}
        </div>
        <div className="flex-1 overflow-y-auto p-2"><div className="grid grid-cols-5 gap-1">{data.agents.map(a => (<button key={a.id} onClick={() => toggleAgent(a.id)} className={`p-1 rounded text-xs border ${selectedAgents.has(a.id) && filterMode === 'custom' ? 'border-emerald-500 bg-emerald-500/20' : 'border-slate-600 bg-slate-700'}`} style={{ color: STATE_COLORS[a.stateAtDay[DAYS]] }}>{a.id}</button>))}</div></div>
        {selectedAgent && (<div className="p-2 border-t border-slate-700 max-h-48 overflow-y-auto"><div className="font-bold text-white text-sm mb-1">Agent {selectedAgent.id}</div>{selectedAgent.timeline.map((e, i) => (<div key={i} className="text-[10px]" style={{ color: STATE_COLORS[e.state] }}>Day {e.day}: {e.state}</div>))}</div>)}
        <div className="p-2 border-t border-slate-700 space-y-2">
          <div className="flex gap-2"><button onClick={togglePlay} className={`px-3 py-1 rounded text-sm ${isPlaying ? 'bg-amber-500' : 'bg-emerald-500'} text-white`}>{isPlaying ? 'Pause' : 'Play'}</button><button onClick={() => setSelectedDay(0)} className="px-3 py-1 rounded text-sm bg-slate-600 text-white">Reset</button></div>
          <div className="flex items-center gap-2"><span className="text-xs text-slate-400 w-12">Day {selectedDay}</span><input type="range" min={0} max={DAYS} value={selectedDay} onChange={(e) => setSelectedDay(parseInt(e.target.value))} className="flex-1" /></div>
        </div>
      </div>
      <div className="flex-1"><Canvas camera={{ position: [8, 6, 8], fov: 45 }} style={{ background: '#0f172a' }}><Scene3D data={data} selectedDay={selectedDay} selectedAgent={selectedAgent} setSelectedAgent={setSelectedAgent} visibleIds={visibleIds} /></Canvas></div>
    </div>
  )
}

// ============================================================================
// MAIN APP WITH TABS
// ============================================================================

function App() {
  const [view, setView] = useState('oop')

  return (
    <div className="flex flex-col w-screen h-screen bg-slate-900">
      <div className="h-12 bg-slate-800 border-b border-slate-700 flex items-center px-4 gap-4">
        <span className="font-bold text-white">ABS-DES Explorer</span>
        <div className="flex gap-1 ml-4">
          {[
            ['oop', 'Object Model'],
            ['loop', 'Daily Loop'],
            ['agents', 'Agent Interrogator'],
          ].map(([v, label]) => (
            <button key={v} onClick={() => setView(v)} className={`px-3 py-1.5 rounded text-sm font-medium ${view === v ? 'bg-emerald-500 text-white' : 'bg-slate-700 text-slate-300'}`}>{label}</button>
          ))}
        </div>
      </div>
      {view === 'oop' && <OOPModelView />}
      {view === 'loop' && <DailyLoopView />}
      {view === 'agents' && <AgentInterrogatorView />}
    </div>
  )
}

export default App
