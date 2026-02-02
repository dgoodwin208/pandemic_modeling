import React, { useState } from 'react';
import { Activity, Database, Lightbulb, Zap } from 'lucide-react';
import APRLogo from './components/APRLogo';
import SimulationTab from './components/SimulationTab';
import DataTab from './components/DataTab';
import InterventionsTab from './components/InterventionsTab';
import AudioExplorationTab from './components/AudioExplorationTab';

const TABS = [
  { id: 'simulation', label: 'Simulation', icon: Activity },
  { id: 'data', label: 'Data', icon: Database },
  { id: 'interventions', label: 'Interventions', icon: Lightbulb },
  { id: 'audio', label: 'Audio', icon: Zap },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('simulation');

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200">
        <div className="max-w-[1920px] mx-auto px-6 py-3">
          <div className="flex items-center gap-6">
            {/* APR Logo */}
            <APRLogo size="default" showText={true} />

            {/* Tab Navigation */}
            <div className="flex items-center gap-1 ml-4 bg-slate-100 rounded-xl p-1">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === id
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content — all tabs stay mounted, hidden via CSS */}
      <div style={{ display: activeTab === 'simulation' ? 'block' : 'none' }}>
        <SimulationTab />
      </div>
      <div style={{ display: activeTab === 'data' ? 'block' : 'none' }}>
        <main className="h-[calc(100vh-64px)]">
          <DataTab />
        </main>
      </div>
      <div style={{ display: activeTab === 'interventions' ? 'block' : 'none' }}>
        <main className="h-[calc(100vh-64px)]">
          <InterventionsTab />
        </main>
      </div>
      <div style={{ display: activeTab === 'audio' ? 'block' : 'none' }}>
        <main className="h-[calc(100vh-64px)]">
          <AudioExplorationTab />
        </main>
      </div>
    </div>
  );
}
