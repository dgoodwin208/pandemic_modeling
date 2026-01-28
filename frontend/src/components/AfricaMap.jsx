import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Zoom level tracker component
const ZoomTracker = ({ onZoomChange }) => {
  const map = useMapEvents({
    zoomend: () => {
      onZoomChange(map.getZoom());
    },
  });

  useEffect(() => {
    onZoomChange(map.getZoom());
  }, [map, onZoomChange]);

  return null;
};

// City color based on population size
const getCityColor = (population) => {
  if (population > 5000000) return '#f59e0b';  // amber for megacities
  if (population > 2000000) return '#ef4444';  // red for large cities
  if (population > 1000000) return '#ec4899';  // pink for medium-large
  if (population > 500000) return '#8b5cf6';   // purple for medium
  return '#60a5fa';                             // blue for smaller (100k-500k)
};

// Calculate circle radius based on population (sqrt scale for area perception)
const getCityRadius = (population, zoom) => {
  const baseRadius = Math.sqrt(population / 100000) * 1.5;
  const zoomFactor = Math.pow(1.2, zoom - 3);
  return Math.max(3, Math.min(baseRadius * zoomFactor, 35));
};

// Format population number
const formatPopulation = (pop) => {
  if (pop >= 1000000) return `${(pop / 1000000).toFixed(1)}M`;
  if (pop >= 1000) return `${(pop / 1000).toFixed(0)}K`;
  return pop.toString();
};

// Map bounds fitter component - only runs once on mount
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

// Get health capacity rating from score
const getHealthCapacityRating = (score) => {
  if (score >= 70) return { label: 'Strong', color: '#16a34a' };
  if (score >= 50) return { label: 'Moderate', color: '#d97706' };
  if (score >= 30) return { label: 'Limited', color: '#dc2626' };
  return { label: 'Critical', color: '#991b1b' };
};

// City Modal component
const CityModal = ({ city, onClose }) => {
  if (!city) return null;

  const {
    city: name,
    country,
    population,
    medical_services_score,
    health_capacity_score,
    total_facilities,
    hospitals,
    clinics,
    health_centers,
    pharmacies,
    laboratories,
    emergency_facilities,
    facilities_per_100k,
    total_beds,
  } = city;

  const color = getCityColor(population);
  const healthRating = getHealthCapacityRating(health_capacity_score || 0);

  return (
    <div className="absolute top-4 right-4 bg-white/98 backdrop-blur-xl border border-slate-200 rounded-xl p-4 z-[1001] w-80 shadow-xl max-h-[90vh] overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded-full flex-shrink-0"
            style={{ backgroundColor: color }}
          />
          <h3 className="font-medium text-slate-800 text-lg">{name}</h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition-colors text-xl leading-none ml-2"
        >
          ×
        </button>
      </div>

      {/* Country & Population */}
      <div className="flex justify-between items-center mb-3">
        <span className="text-sm text-slate-500">{country}</span>
        <span className="text-sm font-medium text-slate-700 tabular-nums">{formatPopulation(population)}</span>
      </div>

      {/* Health Capacity Score - Hero metric */}
      <div className="bg-slate-100 rounded-lg p-3 mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Health Capacity</span>
          <div className="flex items-center gap-2">
            <span className="text-lg font-medium" style={{ color: healthRating.color }}>
              {healthRating.label}
            </span>
            <span className="text-xs text-slate-400 tabular-nums">({health_capacity_score || 0}/100)</span>
          </div>
        </div>
        {/* Score bar */}
        <div className="w-full bg-slate-200 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all"
            style={{
              width: `${health_capacity_score || 0}%`,
              backgroundColor: healthRating.color,
            }}
          />
        </div>
      </div>

      {/* Health Facilities Section */}
      <div className="mb-4">
        <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Health Facilities</div>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-50 border border-slate-100 rounded-lg p-2">
            <div className="text-2xl font-medium text-slate-700 tabular-nums">{total_facilities || 0}</div>
            <div className="text-[10px] text-slate-400">Total Facilities</div>
          </div>
          <div className="bg-slate-50 border border-slate-100 rounded-lg p-2">
            <div className="text-2xl font-medium text-emerald-600 tabular-nums">{hospitals || 0}</div>
            <div className="text-[10px] text-slate-400">Hospitals</div>
          </div>
          <div className="bg-slate-50 border border-slate-100 rounded-lg p-2">
            <div className="text-lg font-medium text-blue-600 tabular-nums">{clinics || 0}</div>
            <div className="text-[10px] text-slate-400">Clinics</div>
          </div>
          <div className="bg-slate-50 border border-slate-100 rounded-lg p-2">
            <div className="text-lg font-medium text-violet-600 tabular-nums">{pharmacies || 0}</div>
            <div className="text-[10px] text-slate-400">Pharmacies</div>
          </div>
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="space-y-1.5 text-xs">
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="text-slate-500">Health Centers</span>
          <span className="text-slate-600 tabular-nums">{health_centers || 0}</span>
        </div>
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="text-slate-500">Laboratories</span>
          <span className="text-slate-600 tabular-nums">{laboratories || 0}</span>
        </div>
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="text-slate-500">Emergency Services</span>
          <span className={emergency_facilities > 0 ? 'text-emerald-600 tabular-nums' : 'text-slate-400 tabular-nums'}>
            {emergency_facilities || 0}
          </span>
        </div>
        {total_beds > 0 && (
          <div className="flex justify-between items-center py-1 border-b border-slate-100">
            <span className="text-slate-500">Hospital Beds</span>
            <span className="text-slate-600 tabular-nums">{total_beds.toLocaleString()}</span>
          </div>
        )}
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="text-slate-500">Facilities per 100K</span>
          <span className="text-slate-600 tabular-nums">{facilities_per_100k || 0}</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-slate-500">Country HAQ Index</span>
          <span className="text-slate-600 tabular-nums">{medical_services_score}/100</span>
        </div>
      </div>

      {/* Population tier indicator */}
      <div className="mt-3 pt-2 border-t border-slate-200">
        <div className="text-[10px] text-slate-400">
          {population > 5000000 ? 'Megacity (5M+)' :
           population > 2000000 ? 'Major City (2-5M)' :
           population > 1000000 ? 'Large City (1-2M)' :
           population > 500000 ? 'Medium City (500K-1M)' :
           'City (100K-500K)'}
        </div>
      </div>
    </div>
  );
};

// Legend component
const Legend = () => {
  const citiesLegend = [
    { color: '#f59e0b', label: '5M+ (megacity)' },
    { color: '#ef4444', label: '2-5M' },
    { color: '#ec4899', label: '1-2M' },
    { color: '#8b5cf6', label: '500K-1M' },
    { color: '#60a5fa', label: '100K-500K' },
  ];

  return (
    <div className="absolute bottom-6 left-6 bg-white/98 backdrop-blur-xl border border-slate-200 rounded-xl p-4 z-[1000] shadow-lg">
      <div className="text-xs font-medium text-slate-600 mb-2">City Population</div>
      <div className="space-y-1">
        {citiesLegend.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-xs text-slate-500">{item.label}</span>
          </div>
        ))}
      </div>
      <div className="text-[10px] text-slate-400 mt-2 border-t border-slate-200 pt-2">
        Click cities for details
      </div>
    </div>
  );
};

export default function AfricaMap({
  currentDay = 0,
  selectedCountry = null,
  onCountrySelect = () => {},
  showLegend = true,
}) {
  const [geoData, setGeoData] = useState(null);
  const [citiesData, setCitiesData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [zoom, setZoom] = useState(3);
  const [selectedCity, setSelectedCity] = useState(null);

  // Load GeoJSON boundaries and cities JSON
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

  // Simple style for country boundaries (light theme)
  const getStyle = (feature) => {
    const iso3 = feature.properties.iso3;
    const isSelected = selectedCountry === iso3;

    return {
      fillColor: '#e2e8f0',
      weight: isSelected ? 2 : 1,
      opacity: 0.8,
      color: isSelected ? '#10b981' : '#94a3b8',
      fillOpacity: 0.4,
    };
  };

  // Event handlers for country features (tooltip only, no click to allow city clicks)
  const onEachFeature = (feature, layer) => {
    const name = feature.properties.name;

    layer.bindTooltip(`<div class="font-semibold">${name}</div>`, {
      permanent: false,
      direction: 'center',
      className: 'custom-tooltip',
    });

    // Hover effect only - no click handler to avoid intercepting city clicks
    layer.on({
      mouseover: (e) => {
        e.target.setStyle({
          weight: 2,
          color: '#10b981',
        });
      },
      mouseout: (e) => {
        if (geoData) {
          e.target.setStyle(getStyle(feature));
        }
      },
    });
  };

  // Africa bounds
  const africaBounds = [[-35, -25], [40, 55]];

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-100 rounded-xl">
        <div className="text-slate-500">Loading map data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-100 rounded-xl">
        <div className="text-red-500">Error loading map: {error}</div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={[0, 20]}
        zoom={3}
        className="w-full h-full rounded-xl"
        style={{ background: '#f8fafc' }}
        zoomControl={false}
        attributionControl={false}
      >
        {/* Track zoom level */}
        <ZoomTracker onZoomChange={setZoom} />

        {/* Light tile layer */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* Africa country boundaries (simple outline) */}
        {geoData && (
          <GeoJSON
            data={geoData}
            style={getStyle}
            onEachFeature={onEachFeature}
            interactive={false}
          />
        )}

        {/* City markers */}
        {citiesData && citiesData.map((city, idx) => {
          const { city: name, country, population, latitude, longitude } = city;
          const radius = getCityRadius(population, zoom);
          const color = getCityColor(population);
          const isSelected = selectedCity?.city === name && selectedCity?.country === country;

          return (
            <CircleMarker
              key={`city-${idx}`}
              center={[latitude, longitude]}
              radius={radius}
              pathOptions={{
                fillColor: color,
                fillOpacity: isSelected ? 1 : 0.8,
                color: '#fff',
                weight: isSelected ? 2 : 1,
                opacity: isSelected ? 1 : 0.8,
              }}
              eventHandlers={{
                click: (e) => {
                  e.originalEvent.stopPropagation();
                  setSelectedCity(city);
                },
              }}
            >
              <Tooltip
                direction="top"
                offset={[0, -radius]}
                className="custom-tooltip"
              >
                <div className="font-semibold">{name}</div>
                <div className="text-sm text-slate-500">{country}</div>
                <div className="text-sm text-slate-500">
                  Pop: {formatPopulation(population)}
                </div>
                <div className="text-sm text-slate-500">
                  {city.total_facilities || 0} facilities | {city.hospitals || 0} hospitals
                </div>
                <div className="text-[10px] text-slate-400 mt-1">Click for details</div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Labels layer on top */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        <FitBounds bounds={africaBounds} />
      </MapContainer>

      {/* Legend */}
      {showLegend && <Legend />}

      {/* Day indicator */}
      <div className="absolute top-4 left-4 bg-white/98 backdrop-blur-xl border border-slate-200 rounded-xl px-4 py-2 z-[1000] shadow-lg">
        <span className="text-xs text-slate-500">Day </span>
        <span className="text-lg font-medium text-slate-700 tabular-nums">{currentDay}</span>
      </div>

      {/* City detail modal */}
      {selectedCity && (
        <CityModal
          city={selectedCity}
          onClose={() => setSelectedCity(null)}
        />
      )}
    </div>
  );
}
