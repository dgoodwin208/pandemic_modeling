import React, { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Zoom level tracker
const ZoomTracker = ({ onZoomChange }) => {
  const map = useMapEvents({
    zoomend: () => onZoomChange(map.getZoom()),
  });
  useEffect(() => onZoomChange(map.getZoom()), [map, onZoomChange]);
  return null;
};

// Fit bounds on mount
const FitBounds = ({ bounds }) => {
  const map = useMap();
  const fittedRef = React.useRef(false);
  useEffect(() => {
    if (bounds && !fittedRef.current) {
      map.fitBounds(bounds, { padding: [20, 20] });
      fittedRef.current = true;
    }
  }, [map, bounds]);
  return null;
};

// ONLY metrics actually used in simulation
const METRICS = {
  hospitals: {
    label: 'Hospitals',
    description: 'Used for: PPE calculation, fallback beds',
    field: 'hospitals',
    colorScale: ['#dbeafe', '#3b82f6', '#1e40af'],
    thresholds: [5, 20, 50],
    format: (v) => v?.toFixed(0) || '0',
  },
  clinics: {
    label: 'Clinics',
    description: 'Used for: PPE calculation, fallback beds',
    field: 'clinics',
    colorScale: ['#d1fae5', '#10b981', '#065f46'],
    thresholds: [10, 50, 150],
    format: (v) => v?.toFixed(0) || '0',
  },
  laboratories: {
    label: 'Laboratories',
    description: 'Used for: Swabs & reagents calculation',
    field: 'laboratories',
    colorScale: ['#fef3c7', '#f59e0b', '#92400e'],
    thresholds: [1, 5, 15],
    format: (v) => v?.toFixed(0) || '0',
  },
  beds: {
    label: 'Hospital Beds',
    description: 'Used for: Bed capacity constraint',
    field: 'hospital_beds_total',
    colorScale: ['#fecaca', '#ef4444', '#7f1d1d'],
    thresholds: [500, 2000, 5000],
    format: (v) => v?.toLocaleString() || '0',
  },
};

// Get color based on value
const getMetricColor = (value, metric) => {
  const config = METRICS[metric];
  if (!value && value !== 0) return '#e2e8f0';
  const { thresholds, colorScale } = config;
  if (value < thresholds[0]) return colorScale[0];
  if (value < thresholds[1]) return colorScale[1];
  return colorScale[2];
};

// Calculate radius
const getRadius = (value, metric, zoom) => {
  const config = METRICS[metric];
  const maxThreshold = config.thresholds[2];
  const normalized = Math.min(value / maxThreshold, 2);
  const baseRadius = 4 + normalized * 12;
  const zoomFactor = Math.pow(1.15, zoom - 3);
  return Math.max(3, Math.min(baseRadius * zoomFactor, 30));
};

// Format numbers
const formatNumber = (num) => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return num?.toString() || '0';
};

// Legend
const Legend = ({ metric }) => {
  const config = METRICS[metric];
  const { thresholds, colorScale, label, description } = config;

  return (
    <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl p-4 z-[1000] shadow-lg max-w-[200px]">
      <div className="text-xs font-semibold text-slate-700 mb-1">{label}</div>
      <div className="text-[10px] text-slate-500 mb-2">{description}</div>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: colorScale[0] }} />
          <span className="text-xs text-slate-500">&lt; {thresholds[0]}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: colorScale[1] }} />
          <span className="text-xs text-slate-500">{thresholds[0]}-{thresholds[1]}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: colorScale[2] }} />
          <span className="text-xs text-slate-500">&gt; {thresholds[1]}</span>
        </div>
      </div>
    </div>
  );
};

// Metric selector
const MetricSelector = ({ metric, onChange }) => (
  <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl p-3 z-[1000] shadow-lg">
    <div className="text-xs font-semibold text-slate-600 mb-2">Show Metric</div>
    <select
      value={metric}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {Object.entries(METRICS).map(([key, config]) => (
        <option key={key} value={key}>{config.label}</option>
      ))}
    </select>
    <div className="text-[10px] text-slate-400 mt-1">Only simulation-used fields</div>
  </div>
);

// City detail panel - only showing what's used
const CityPanel = ({ city, metric, onClose }) => {
  if (!city) return null;

  return (
    <div className="absolute top-4 right-4 bg-white/98 backdrop-blur-xl border border-slate-200 rounded-xl p-4 z-[1001] w-72 shadow-xl">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-800">{city.city}</h3>
          <p className="text-sm text-slate-500">{city.country}</p>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
      </div>

      <div className="text-xs text-slate-500 mb-2">Population: {formatNumber(city.population)}</div>

      <div className="border-t border-slate-200 pt-3 mt-2">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
          Simulation Input Data
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Hospitals</span>
            <span className="font-medium text-slate-700">{city.hospitals || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Clinics</span>
            <span className="font-medium text-slate-700">{city.clinics || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Laboratories</span>
            <span className="font-medium text-slate-700">{city.laboratories || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Hospital Beds</span>
            <span className="font-medium text-slate-700">{city.hospital_beds_total?.toLocaleString() || 'N/A'}</span>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-200 pt-3 mt-3">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
          Derived Resources (at defaults)
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Beds</span>
            <span className="font-mono text-slate-700">{city.hospital_beds_total?.toLocaleString() || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">PPE</span>
            <span className="font-mono text-slate-700">{((city.hospitals || 0) + (city.clinics || 0)) * 500}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Swabs</span>
            <span className="font-mono text-slate-700">{Math.max(1, city.laboratories || 0) * 1000}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Reagents</span>
            <span className="font-mono text-slate-700">{Math.max(1, city.laboratories || 0) * 2000}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function SupplyChainMap() {
  const [geoData, setGeoData] = useState(null);
  const [citiesData, setCitiesData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [zoom, setZoom] = useState(3);
  const [selectedCity, setSelectedCity] = useState(null);
  const [metric, setMetric] = useState('hospitals');

  useEffect(() => {
    Promise.all([
      fetch('/data/africa_boundaries.geojson').then(r => r.json()),
      fetch('/data/african_cities.json').then(r => r.json()),
    ])
      .then(([geo, cities]) => {
        setGeoData(geo);
        setCitiesData(cities.cities);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load map data:', err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleZoomChange = useCallback((z) => setZoom(z), []);

  const getStyle = () => ({
    fillColor: '#f1f5f9',
    weight: 1,
    opacity: 0.6,
    color: '#94a3b8',
    fillOpacity: 0.3,
  });

  const africaBounds = [[-35, -25], [40, 55]];

  if (loading) {
    return (
      <div className="w-full h-[450px] flex items-center justify-center bg-slate-100 rounded-xl">
        <div className="flex items-center gap-2 text-slate-500">
          <div className="w-4 h-4 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
          Loading map data...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-[450px] flex items-center justify-center bg-slate-100 rounded-xl">
        <div className="text-red-500">Error loading map: {error}</div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[450px] rounded-xl overflow-hidden border border-slate-200">
      <MapContainer
        center={[0, 20]}
        zoom={3}
        className="w-full h-full"
        style={{ background: '#f8fafc' }}
        zoomControl={true}
        attributionControl={false}
      >
        <ZoomTracker onZoomChange={handleZoomChange} />

        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        {geoData && (
          <GeoJSON data={geoData} style={getStyle} interactive={false} />
        )}

        {citiesData && citiesData.map((city, idx) => {
          const config = METRICS[metric];
          const value = city[config.field] || 0;
          const radius = getRadius(value, metric, zoom);
          const color = getMetricColor(value, metric);
          const isSelected = selectedCity?.city === city.city;

          return (
            <CircleMarker
              key={`city-${idx}`}
              center={[city.latitude, city.longitude]}
              radius={radius}
              pathOptions={{
                fillColor: color,
                fillOpacity: isSelected ? 1 : 0.75,
                color: isSelected ? '#1e293b' : '#fff',
                weight: isSelected ? 2 : 1,
                opacity: 0.9,
              }}
              eventHandlers={{
                click: (e) => {
                  e.originalEvent.stopPropagation();
                  setSelectedCity(city);
                },
              }}
            >
              <Tooltip direction="top" offset={[0, -radius]} className="custom-tooltip">
                <div className="font-semibold">{city.city}</div>
                <div className="text-sm text-slate-500">{city.country}</div>
                <div className="text-sm">
                  <span className="font-medium">{config.label}:</span> {config.format(value)}
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png"
          attribution='&copy; CARTO'
        />

        <FitBounds bounds={africaBounds} />
      </MapContainer>

      <MetricSelector metric={metric} onChange={setMetric} />
      <Legend metric={metric} />

      {selectedCity && (
        <CityPanel
          city={selectedCity}
          metric={metric}
          onClose={() => setSelectedCity(null)}
        />
      )}
    </div>
  );
}
