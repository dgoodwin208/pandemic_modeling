import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Package, AlertTriangle, Shield, Beaker, Pill, BedDouble,
  Syringe, Activity, ChevronDown, TrendingUp, TrendingDown
} from 'lucide-react';

// ─── Sparkline SVG Chart ──────────────────────────────────────────────────────
// Compact inline chart showing a single time series with optional fill

function Sparkline({ data, width = 300, height = 60, color = '#10b981', fill = true, className = '' }) {
  if (!data || data.length === 0) return null;

  const max = Math.max(...data, 1);
  const points = data.map((v, i) => {
    const x = (i / Math.max(data.length - 1, 1)) * width;
    const y = height - (v / max) * (height - 4) - 2;
    return `${x},${y}`;
  });

  const linePath = `M${points.join(' L')}`;
  const fillPath = `${linePath} L${width},${height} L0,${height} Z`;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {fill && (
        <path d={fillPath} fill={color} opacity={0.12} />
      )}
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ─── Dual-axis supply vs demand chart ─────────────────────────────────────────

function SupplyDemandChart({ supply, demand, label, supplyColor, demandColor, height = 140, showStockout = false }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || (!supply && !demand)) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    ctx.clearRect(0, 0, w, h);

    const allVals = [...(supply || []), ...(demand || [])];
    const maxVal = Math.max(...allVals, 1);
    const days = Math.max(supply?.length || 0, demand?.length || 0);
    if (days === 0) return;

    const padTop = 8, padBot = 20, padLeft = 0, padRight = 0;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBot;

    const toX = (i) => padLeft + (i / (days - 1)) * plotW;
    const toY = (v) => padTop + plotH - (v / maxVal) * plotH;

    // Grid lines
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.15)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = padTop + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(w - padRight, y);
      ctx.stroke();
    }

    // Stockout zones (where supply = 0 and demand > 0)
    if (showStockout && supply && demand) {
      ctx.fillStyle = 'rgba(239, 68, 68, 0.06)';
      for (let i = 0; i < days; i++) {
        if (supply[i] === 0 && demand[i] > 0) {
          const x1 = toX(Math.max(0, i - 0.5));
          const x2 = toX(Math.min(days - 1, i + 0.5));
          ctx.fillRect(x1, padTop, x2 - x1, plotH);
        }
      }
    }

    // Draw demand area + line
    if (demand && demand.length > 0) {
      // Area fill
      ctx.beginPath();
      ctx.moveTo(toX(0), toY(0));
      for (let i = 0; i < demand.length; i++) ctx.lineTo(toX(i), toY(demand[i]));
      ctx.lineTo(toX(demand.length - 1), toY(0));
      ctx.closePath();
      ctx.fillStyle = demandColor + '18';
      ctx.fill();

      // Line
      ctx.beginPath();
      for (let i = 0; i < demand.length; i++) {
        i === 0 ? ctx.moveTo(toX(i), toY(demand[i])) : ctx.lineTo(toX(i), toY(demand[i]));
      }
      ctx.strokeStyle = demandColor;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw supply line
    if (supply && supply.length > 0) {
      ctx.beginPath();
      for (let i = 0; i < supply.length; i++) {
        i === 0 ? ctx.moveTo(toX(i), toY(supply[i])) : ctx.lineTo(toX(i), toY(supply[i]));
      }
      ctx.strokeStyle = supplyColor;
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.stroke();
    }

    // X-axis labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    const step = Math.ceil(days / 5);
    for (let i = 0; i < days; i += step) {
      ctx.fillText(`${i}`, toX(i), h - 4);
    }
    ctx.fillText(`${days - 1}`, toX(days - 1), h - 4);

  }, [supply, demand, supplyColor, demandColor, showStockout, height]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full"
      style={{ height: `${height}px` }}
    />
  );
}

// ─── Resource Card ────────────────────────────────────────────────────────────

const RESOURCE_META = {
  beds: {
    icon: BedDouble,
    label: 'Hospital Beds',
    unit: 'beds',
    color: '#6366f1',
    demandColor: '#a78bfa',
  },
  ppe: {
    icon: Shield,
    label: 'PPE Sets',
    unit: 'sets',
    color: '#0ea5e9',
    demandColor: '#7dd3fc',
  },
  swabs: {
    icon: Beaker,
    label: 'Test Swabs',
    unit: 'swabs',
    color: '#14b8a6',
    demandColor: '#5eead4',
  },
  reagents: {
    icon: Activity,
    label: 'Reagents',
    unit: 'units',
    color: '#f59e0b',
    demandColor: '#fcd34d',
  },
  pills: {
    icon: Pill,
    label: 'Antiviral Pills',
    unit: 'pills',
    color: '#ec4899',
    demandColor: '#f9a8d4',
  },
  vaccines: {
    icon: Syringe,
    label: 'Vaccines',
    unit: 'doses',
    color: '#8b5cf6',
    demandColor: '#c4b5fd',
  },
};

const fmt = (n) => {
  if (n == null) return '—';
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return Math.round(n).toLocaleString();
};

function ResourceCard({ resourceKey, supply, demand, supplyEnabled }) {
  const meta = RESOURCE_META[resourceKey];
  if (!meta) return null;

  const Icon = meta.icon;
  const hasDemand = demand && demand.length > 0;
  const hasSupply = supply && supply.length > 0;

  // Compute stats
  const peakDemand = hasDemand ? Math.max(...demand) : 0;
  const totalDemand = hasDemand ? demand.reduce((a, b) => a + b, 0) : 0;
  const peakDay = hasDemand ? demand.indexOf(peakDemand) : 0;

  // Supply stats
  const initialSupply = hasSupply ? supply[0] : null;
  const finalSupply = hasSupply ? supply[supply.length - 1] : null;
  const stockoutDays = hasSupply ? supply.filter(v => v === 0).length : 0;

  // Status indicator
  let status = 'nominal';
  let statusLabel = 'Adequate';
  let statusColor = 'text-emerald-600';
  let statusBg = 'bg-emerald-50 border-emerald-200';

  if (supplyEnabled && hasSupply) {
    const depletionPct = initialSupply > 0 ? (1 - finalSupply / initialSupply) : 0;
    if (stockoutDays > 0) {
      status = 'critical';
      statusLabel = `Stockout ${stockoutDays}d`;
      statusColor = 'text-red-600';
      statusBg = 'bg-red-50 border-red-200';
    } else if (depletionPct > 0.7) {
      status = 'warning';
      statusLabel = 'Low Stock';
      statusColor = 'text-amber-600';
      statusBg = 'bg-amber-50 border-amber-200';
    }
  }

  return (
    <div className={`rounded-xl border overflow-hidden transition-all duration-200 hover:shadow-md ${
      status === 'critical' ? 'border-red-200 bg-gradient-to-b from-red-50/60 to-white' :
      status === 'warning' ? 'border-amber-200 bg-gradient-to-b from-amber-50/40 to-white' :
      'border-slate-200 bg-white'
    }`}>
      {/* Header */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: meta.color + '14' }}>
              <Icon className="w-4 h-4" style={{ color: meta.color }} />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-700 leading-tight">{meta.label}</div>
              <div className="text-[10px] text-slate-400">peak day {peakDay}</div>
            </div>
          </div>
          {supplyEnabled && (
            <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${statusBg} ${statusColor}`}>
              {statusLabel}
            </span>
          )}
        </div>

        {/* Key metrics row */}
        <div className="grid grid-cols-2 gap-3 mt-3">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-400 font-medium">Peak Demand</div>
            <div className="text-base font-bold tabular-nums" style={{ color: meta.demandColor }}>
              {fmt(peakDemand)}
              <span className="text-[10px] text-slate-400 font-normal ml-1">/{meta.unit.charAt(0)}</span>
            </div>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-400 font-medium">
              {supplyEnabled && hasSupply ? 'Remaining' : 'Total Need'}
            </div>
            <div className="text-base font-bold tabular-nums" style={{ color: supplyEnabled && hasSupply ? meta.color : meta.demandColor }}>
              {supplyEnabled && hasSupply ? fmt(finalSupply) : fmt(totalDemand)}
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-2 pb-2">
        {supplyEnabled && hasSupply ? (
          <SupplyDemandChart
            supply={supply}
            demand={demand}
            supplyColor={meta.color}
            demandColor={meta.demandColor}
            showStockout={true}
            height={100}
          />
        ) : hasDemand ? (
          <SupplyDemandChart
            supply={null}
            demand={demand}
            supplyColor={meta.color}
            demandColor={meta.demandColor}
            height={100}
          />
        ) : (
          <div className="h-[100px] flex items-center justify-center text-xs text-slate-300">
            No data
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="px-4 pb-3 flex items-center gap-4 text-[9px] text-slate-400">
        {supplyEnabled && hasSupply && (
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 rounded-full" style={{ backgroundColor: meta.color }} />
            <span>Supply</span>
          </div>
        )}
        {hasDemand && (
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 rounded-full" style={{ backgroundColor: meta.demandColor }} />
            <span>Demand</span>
          </div>
        )}
        {supplyEnabled && stockoutDays > 0 && (
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm bg-red-100 border border-red-200" />
            <span className="text-red-500">Stockout</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

export default function ResourcePanels({ sessionId, supplyChainEnabled }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);

    fetch(`/api/simulate/absdes/${sessionId}/resources`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load resource data');
        return res.json();
      })
      .then((json) => {
        setData(json);
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
          Loading resource data...
        </div>
      </div>
    );
  }

  if (error || !data) return null;

  const supply = data.supply;
  const demand = data.demand;
  const hasAnyData = supply || demand;
  if (!hasAnyData) return null;

  const isSupplyEnabled = data.supply_chain_enabled;

  // Resource keys to display
  const resources = ['beds', 'ppe', 'swabs', 'reagents', 'pills', 'vaccines'];

  // Aggregate stats for the header
  let totalStockoutDays = 0;
  let criticalResources = 0;
  if (isSupplyEnabled && supply) {
    for (const key of ['ppe', 'swabs', 'reagents']) {
      const arr = supply[key];
      if (arr) {
        const days = arr.filter(v => v === 0).length;
        totalStockoutDays += days;
        if (days > 0) criticalResources++;
      }
    }
  }

  return (
    <div className="space-y-4">
      {/* Section header */}
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-purple-50 border border-purple-200 flex items-center justify-center">
              <Package className="w-4 h-4 text-purple-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-700">
                {isSupplyEnabled ? 'Supply Chain — Supply vs Demand' : 'Resource Demand (Shadow Accounting)'}
              </h3>
              <p className="text-[10px] text-slate-400">
                {isSupplyEnabled
                  ? 'Actual supply levels and daily consumption across all cities'
                  : 'Projected resource needs if supply chain were active'}
              </p>
            </div>
          </div>
          {isSupplyEnabled && criticalResources > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 border border-red-200">
              <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              <span className="text-xs font-semibold text-red-600">
                {criticalResources} resource{criticalResources > 1 ? 's' : ''} in stockout
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Resource cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {resources.map((key) => {
          const supplyData = supply?.[key === 'beds' ? 'beds_occupied' : key] ?? null;
          const demandData = demand?.[key] ?? null;

          // Skip if no data at all
          if (!supplyData && !demandData) return null;

          return (
            <ResourceCard
              key={key}
              resourceKey={key}
              supply={supplyData}
              demand={demandData}
              supplyEnabled={isSupplyEnabled}
            />
          );
        })}
      </div>
    </div>
  );
}
