import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';

const PLAYBACK_INTERVAL_MS = 150; // ~6.7 fps
const PRELOAD_AHEAD = 5;

function useImagePreloader(sessionId, totalDays, currentDay) {
  const cacheRef = useRef({ actual: {}, observed: {} });

  useEffect(() => {
    if (!sessionId) return;

    const startDay = currentDay;
    const endDay = Math.min(currentDay + PRELOAD_AHEAD, totalDays);

    for (let day = startDay; day <= endDay; day++) {
      if (!cacheRef.current.actual[day]) {
        const imgActual = new Image();
        imgActual.src = `/api/simulate/absdes/${sessionId}/frame/actual/${day}`;
        cacheRef.current.actual[day] = imgActual;
      }
      if (!cacheRef.current.observed[day]) {
        const imgObserved = new Image();
        imgObserved.src = `/api/simulate/absdes/${sessionId}/frame/observed/${day}`;
        cacheRef.current.observed[day] = imgObserved;
      }
    }
  }, [sessionId, totalDays, currentDay]);

  return cacheRef;
}

function FramePanel({ title, description, src, alt }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const prevSrcRef = useRef(null);

  useEffect(() => {
    if (src !== prevSrcRef.current) {
      setLoaded(false);
      setError(false);
      prevSrcRef.current = src;
    }
  }, [src]);

  return (
    <div className="flex-1 min-w-0">
      <div className="mb-2">
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">{title}</h3>
        <p className="text-[10px] text-slate-500 leading-tight">{description}</p>
      </div>
      <div className="timeline-panel relative bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm"
           style={{ minHeight: '600px' }}>
        {!loaded && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50">
            <div className="w-6 h-6 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50 text-slate-400 text-xs">
            Frame unavailable
          </div>
        )}
        <img
          src={src}
          alt={alt}
          className={`w-full h-full object-contain transition-opacity duration-100 ${
            loaded ? 'opacity-100' : 'opacity-0'
          }`}
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
      </div>
    </div>
  );
}

export default function TimelineViewer({ sessionId, totalDays }) {
  const [currentDay, setCurrentDay] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef(null);

  // Preload frames ahead
  useImagePreloader(sessionId, totalDays, currentDay);

  // Playback logic
  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setCurrentDay((prev) => {
          if (prev >= totalDays) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, PLAYBACK_INTERVAL_MS);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPlaying, totalDays]);

  const handlePlayPause = useCallback(() => {
    if (currentDay >= totalDays) {
      setCurrentDay(0);
      setIsPlaying(true);
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, [currentDay, totalDays]);

  const handleReset = useCallback(() => {
    setIsPlaying(false);
    setCurrentDay(0);
  }, []);

  const handleSliderChange = useCallback((e) => {
    const day = parseInt(e.target.value, 10);
    setCurrentDay(day);
  }, []);

  const actualSrc = `/api/simulate/absdes/${sessionId}/frame/actual/${currentDay}`;
  const observedSrc = `/api/simulate/absdes/${sessionId}/frame/observed/${currentDay}`;

  return (
    <div className="space-y-4">
      {/* Frame Panels - side by side */}
      <div className="flex gap-4">
        <FramePanel
          title="Actual"
          description="True epidemic state -- all infections, exposures, and recoveries"
          src={actualSrc}
          alt={`Actual state day ${currentDay}`}
        />
        <FramePanel
          title="Observed"
          description="Provider-inferred state -- only detected cases and their outcomes"
          src={observedSrc}
          alt={`Observed state day ${currentDay}`}
        />
      </div>

      {/* Playback Controls */}
      <div className="card px-4 py-3">
        <div className="flex items-center gap-3">
          {/* Play/Pause */}
          <button
            onClick={handlePlayPause}
            className="flex items-center justify-center w-9 h-9 rounded-lg btn-primary !px-0 !py-0"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4 ml-0.5" />
            )}
          </button>

          {/* Reset */}
          <button
            onClick={handleReset}
            className="flex items-center justify-center w-9 h-9 rounded-lg btn-secondary !px-0 !py-0"
            title="Reset to day 0"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Slider */}
          <div className="flex-1 mx-2">
            <input
              type="range"
              min={0}
              max={totalDays}
              value={currentDay}
              onChange={handleSliderChange}
              className="w-full"
            />
          </div>

          {/* Day counter */}
          <div className="text-right min-w-[100px]">
            <span className="text-sm font-mono text-slate-600">
              Day{' '}
              <span className="text-emerald-600 font-bold">{currentDay}</span>
              <span className="text-slate-400"> / {totalDays}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
