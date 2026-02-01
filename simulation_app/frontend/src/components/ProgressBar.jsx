import React, { useState, useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle, Activity } from 'lucide-react';

const PHASE_LABELS = {
  initializing: 'Initializing',
  simulation: 'Simulating',
  rendering: 'Rendering Frames',
};

const PHASE_COLORS = {
  initializing: 'bg-amber-500',
  simulation: 'bg-emerald-500',
  rendering: 'bg-blue-500',
};

export default function ProgressBar({ sessionId, onComplete, onError }) {
  const [phase, setPhase] = useState('initializing');
  const [progress, setProgress] = useState(0);
  const [stepText, setStepText] = useState('Connecting...');
  const [eta, setEta] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    const url = `/api/simulate/absdes/${sessionId}/progress`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.phase) {
          setPhase(data.phase);
        }

        if (data.total > 0) {
          const pct = Math.min(100, Math.max(0, (data.current / data.total) * 100));
          setProgress(pct);
        }

        if (data.message) {
          setStepText(data.message);
        }

        if (data.eta_seconds !== undefined) {
          setEta(data.eta_seconds);
        }

        if (data.phase === 'complete') {
          setIsComplete(true);
          setProgress(100);
          setStepText('Simulation complete');
          eventSource.close();
          if (onComplete) {
            setTimeout(() => onComplete(), 800);
          }
        }

        if (data.phase === 'error') {
          const msg = data.message || 'Simulation failed';
          setErrorMessage(msg);
          eventSource.close();
          if (onError) {
            onError(msg);
          }
        }
      } catch (parseError) {
        // Ignore malformed messages
      }
    };

    eventSource.onerror = () => {
      if (!isComplete && !errorMessage) {
        if (eventSource.readyState === EventSource.CLOSED) {
          setErrorMessage('Connection to server lost');
          if (onError) {
            onError('Connection to server lost');
          }
        }
      }
    };

    return () => {
      eventSource.close();
    };
  }, [sessionId, onComplete, onError]);

  const phaseLabel = PHASE_LABELS[phase] || phase;
  const phaseColor = PHASE_COLORS[phase] || 'bg-emerald-500';

  const formatEta = (seconds) => {
    if (seconds === null || seconds === undefined) return null;
    if (seconds < 60) return `~${Math.ceil(seconds)}s remaining`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.ceil(seconds % 60);
    return `~${mins}m ${secs}s remaining`;
  };

  if (errorMessage) {
    return (
      <div className="card border-red-200 p-6">
        <div className="flex items-center gap-3 mb-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <h3 className="text-red-700 font-semibold">Simulation Error</h3>
        </div>
        <p className="text-red-600 text-sm">{errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {isComplete ? (
            <CheckCircle className="w-5 h-5 text-emerald-500" />
          ) : (
            <Activity className="w-5 h-5 text-emerald-500 animate-pulse" />
          )}
          <div>
            <h3 className={`font-semibold ${isComplete ? 'text-emerald-600' : 'text-slate-700'}`}>
              {isComplete ? 'Simulation Complete' : phaseLabel}
            </h3>
            <p className="text-xs text-slate-500">{stepText}</p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-lg font-mono font-bold text-slate-700">
            {Math.round(progress)}%
          </span>
          {eta !== null && !isComplete && (
            <p className="text-[10px] text-slate-400">{formatEta(eta)}</p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ease-out ${
            isComplete ? 'bg-emerald-500' : `${phaseColor} ${progress < 100 ? 'progress-active' : ''}`
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Phase indicators */}
      <div className="flex items-center gap-4 mt-3">
        {Object.entries(PHASE_LABELS).map(([key, label]) => {
          const isCurrent = key === phase && !isComplete;
          const isPast =
            (key === 'initializing' && (phase === 'simulation' || phase === 'rendering' || isComplete)) ||
            (key === 'simulation' && (phase === 'rendering' || isComplete)) ||
            (key === 'rendering' && isComplete);

          return (
            <div key={key} className="flex items-center gap-1.5">
              <div
                className={`w-2 h-2 rounded-full ${
                  isCurrent
                    ? `${PHASE_COLORS[key]} animate-pulse`
                    : isPast
                    ? 'bg-emerald-500'
                    : 'bg-slate-300'
                }`}
              />
              <span
                className={`text-[10px] ${
                  isCurrent ? 'text-slate-600 font-medium' : isPast ? 'text-emerald-500' : 'text-slate-400'
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
