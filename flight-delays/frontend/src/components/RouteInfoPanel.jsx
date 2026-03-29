import { useState, useCallback } from 'react';
import useGlobeStore from '../stores/globeStore';
import { useIsNarrowLayout } from '../hooks/useMediaQuery';
import { formatPct } from '../utils/formatters';
import { delayMinutesToColor } from '../utils/colorScale';

const API_BASE = import.meta.env.VITE_API_URL || '';

function reliabilityToColor(reliability) {
  if (reliability === 'HIGH') return 'var(--color-delay-low)';
  if (reliability === 'MEDIUM') return 'var(--color-delay-medium)';
  return 'var(--color-delay-high)';
}

function delayTag(minutes) {
  if (minutes == null) return null;
  const rounded = Math.round(minutes);
  if (rounded <= 0) return { text: rounded < 0 ? `${Math.abs(rounded)} min early` : 'On time', color: 'var(--color-delay-low)' };
  if (rounded < 10) return { text: `~${rounded} min`, color: 'var(--color-delay-low)' };
  if (rounded < 25) return { text: `~${rounded} min`, color: 'var(--color-delay-medium)' };
  if (rounded < 45) return { text: `~${rounded} min`, color: 'var(--color-delay-high)' };
  return { text: `~${rounded} min`, color: 'var(--color-delay-severe)' };
}

function cancellationTag(probability) {
  if (probability == null) return null;
  const pct = probability * 100;
  if (pct < 8) return { label: 'Low risk', color: 'var(--color-delay-low)' };
  if (pct < 18) return { label: 'Moderate risk', color: 'var(--color-delay-medium)' };
  if (pct < 35) return { label: 'High risk', color: 'var(--color-delay-high)' };
  return { label: 'Very high risk', color: 'var(--color-delay-severe)' };
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function maxDateISO() {
  const d = new Date();
  d.setDate(d.getDate() + 14);
  return d.toISOString().slice(0, 10);
}

async function readApiError(res) {
  const body = await res.json().catch(() => null);
  const d = body?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join('; ');
  return `Request failed (${res.status})`;
}

export default function RouteInfoPanel() {
  const narrow = useIsNarrowLayout();
  const route = useGlobeStore((s) => s.selectedRoute);
  const clearSelectedRoute = useGlobeStore((s) => s.clearSelectedRoute);

  const [selectedDate, setSelectedDate] = useState(todayISO);
  const [selectedHour, setSelectedHour] = useState('12');
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const resetPrediction = useCallback(() => {
    setPrediction(null);
    setError(null);
  }, []);

  const handlePredict = useCallback(async () => {
    if (!route) return;
    setLoading(true);
    setError(null);
    setPrediction(null);
    try {
      const dt = `${selectedDate}T${selectedHour.padStart(2, '0')}:00:00Z`;
      const params = new URLSearchParams({
        origin: route.origin,
        destination: route.destination,
        departure_date: dt,
      });
      if (route.airline) params.set('airline', route.airline);

      const res = await fetch(`${API_BASE}/api/predictions/route/estimate?${params}`);
      if (!res.ok) {
        throw new Error(await readApiError(res));
      }
      setPrediction(await res.json());
    } catch (err) {
      setError(err.message || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  }, [route, selectedDate, selectedHour]);

  if (!route) return null;

  const estimatedDelay = route.estimated_delay_minutes ?? route.avg_delay_minutes ?? null;
  const histTag = delayTag(estimatedDelay);

  return (
    <div
      style={{
        position: 'absolute',
        left: narrow ? 12 : undefined,
        right: narrow ? 12 : 16,
        bottom: narrow
          ? 'calc(108px + env(safe-area-inset-bottom))'
          : 16,
        width: narrow ? 'auto' : 380,
        maxWidth: narrow ? 'min(380px, calc(100vw - 24px))' : undefined,
        maxHeight: narrow ? 'min(58vh, 520px)' : 'min(85vh, 640px)',
        overflowY: 'auto',
        WebkitOverflowScrolling: 'touch',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 12,
        zIndex: 220,
        boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
      }}
    >
      <div style={{ padding: '14px 16px 12px', borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>
              {route.origin} → {route.destination}
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 4 }}>
              {route.airline ? `Airline ${route.airline}` : 'All carriers (aggregate)'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              clearSelectedRoute();
              resetPrediction();
            }}
            title="Close"
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'var(--color-surface-2)',
              color: 'var(--color-text-muted)',
              border: '1px solid var(--color-border)',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      </div>

      <div style={{ padding: '12px 16px' }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: 'var(--color-text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 8,
          }}
        >
          Historical (from your data)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <Stat
            label="Avg delay"
            value={estimatedDelay != null ? `${Math.round(estimatedDelay)} min` : 'N/A'}
            valueColor={histTag?.color}
          />
          <Stat label="Delay level" value={route.delay_level || 'UNKNOWN'} />
          <Stat
            label="Cancellation"
            value={route.cancellation_rate == null ? 'N/A' : formatPct(route.cancellation_rate)}
          />
          <Stat
            label="Reliability"
            value={route.reliability || 'LOW'}
            valueColor={reliabilityToColor(route.reliability)}
          />
        </div>
        <div style={{ marginTop: 8, fontSize: 10, color: 'var(--color-text-dim)' }}>
          Source: {route.data_source || 'UNKNOWN'}
          {route.data_source === 'OPENFLIGHTS_CATALOG' && (
            <span> — no delay history for this line; ML uses global model + weather only.</span>
          )}
        </div>
      </div>

      <div
        style={{
          padding: '14px 16px 16px',
          borderTop: '1px solid var(--color-border)',
          background: 'rgba(255,255,255,0.02)',
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: 'var(--color-text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 10,
          }}
        >
          ML prediction (future departure)
        </div>
        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 10, lineHeight: 1.45 }}>
          Pick a planned date and hour. The API runs the trained XGBoost model (needs{' '}
          <code style={{ fontSize: 10 }}>.joblib</code> files from startup training).
        </p>

        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 140px', minWidth: 0 }}>
            <label style={{ fontSize: 10, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
              Date
            </label>
            <input
              type="date"
              value={selectedDate}
              min={todayISO()}
              max={maxDateISO()}
              onChange={(e) => {
                setSelectedDate(e.target.value);
                resetPrediction();
              }}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface-2)',
                color: 'var(--color-text)',
                fontSize: 12,
                fontFamily: 'inherit',
              }}
            />
          </div>
          <div style={{ width: 88 }}>
            <label style={{ fontSize: 10, color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
              Hour (UTC)
            </label>
            <select
              value={selectedHour}
              onChange={(e) => {
                setSelectedHour(e.target.value);
                resetPrediction();
              }}
              style={{
                width: '100%',
                padding: '8px 6px',
                borderRadius: 8,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface-2)',
                color: 'var(--color-text)',
                fontSize: 12,
                fontFamily: 'inherit',
                cursor: 'pointer',
              }}
            >
              {Array.from({ length: 24 }, (_, i) => (
                <option key={i} value={String(i)}>
                  {String(i).padStart(2, '0')}:00
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={handlePredict}
            disabled={loading}
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              border: 'none',
              background: loading ? 'var(--color-border)' : '#2563eb',
              color: '#fff',
              fontSize: 12,
              fontWeight: 600,
              fontFamily: 'inherit',
              cursor: loading ? 'wait' : 'pointer',
              flexShrink: 0,
            }}
          >
            {loading ? 'Running…' : 'Estimate delay'}
          </button>
        </div>

        {error && (
          <div
            style={{
              marginTop: 12,
              padding: '10px 12px',
              borderRadius: 8,
              background: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.35)',
              fontSize: 11,
              color: '#fca5a5',
              lineHeight: 1.5,
            }}
          >
            <strong style={{ color: '#fecaca' }}>No ML output.</strong> {error}
          </div>
        )}

        {prediction && !error && <PredictionResult prediction={prediction} />}
      </div>
    </div>
  );
}

function PredictionResult({ prediction }) {
  const depDelay = prediction.predicted_departure_delay_minutes ?? prediction.predicted_delay_minutes;
  const arrDelay = prediction.predicted_arrival_delay_minutes;
  const cancelProb = prediction.predicted_cancellation_probability;
  const low = prediction.prediction_interval_low;
  const high = prediction.prediction_interval_high;
  const depTag = delayTag(depDelay);
  const arrTag = delayTag(arrDelay);
  const cancelTag = cancellationTag(cancelProb);
  const ds = prediction.data_sources_used;
  const mq = prediction.model_quality;

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          padding: '12px 14px',
          borderRadius: 10,
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border)',
        }}
      >
        {depDelay != null ? (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 24, fontWeight: 700, color: depTag?.color || 'var(--color-text)' }}>
                {depTag?.text}
              </span>
              <span style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>departure delay</span>
            </div>
            {arrDelay != null && (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}>
                <span style={{ fontSize: 16, fontWeight: 600, color: arrTag?.color || 'var(--color-text)' }}>
                  {arrTag?.text}
                </span>
                <span style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>arrival delay</span>
              </div>
            )}
            {low != null && high != null && (
              <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 6 }}>
                Departure range: {Math.round(low)} – {Math.round(high)} min
              </div>
            )}
            {cancelProb != null && (
              <div
                style={{
                  marginTop: 10,
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                  <span
                    style={{
                      fontSize: 24,
                      fontWeight: 700,
                      color: cancelTag?.color || 'var(--color-text)',
                    }}
                  >
                    {(cancelProb * 100).toFixed(1)}%
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>cancellation probability</span>
                </div>
                {cancelTag && (
                  <div style={{ fontSize: 11, marginTop: 4, color: cancelTag.color, fontWeight: 600 }}>
                    {cancelTag.label}
                  </div>
                )}
              </div>
            )}
            {depDelay != null && low != null && high != null && (
              <DelayBar low={low} predicted={depDelay} high={high} />
            )}
          </>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>Model returned no delay value.</div>
        )}
      </div>

      {mq && <ModelQualityBlock quality={mq} />}

      {ds && (
        <div style={{ marginTop: 8, fontSize: 10, color: 'var(--color-text-dim)', lineHeight: 1.55 }}>
          {ds.explanation_short && <div>{ds.explanation_short}</div>}
          {ds.route_coverage && ds.route_coverage !== 'none' && (
            <div>
              Route history coverage:{' '}
              <span
                style={{
                  fontWeight: 600,
                  color:
                    ds.route_coverage === 'high'
                      ? 'var(--color-delay-low)'
                      : ds.route_coverage === 'medium'
                        ? 'var(--color-delay-medium)'
                        : 'var(--color-delay-high)',
                }}
              >
                {ds.route_coverage}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ModelQualityBlock({ quality }) {
  if (!quality) return null;
  const { delay_dep_mae, delay_arr_mae, cancellation_auc, test_samples } = quality;
  const hasDelay = delay_dep_mae != null || delay_arr_mae != null;
  const hasAuc = cancellation_auc != null;
  if (!hasDelay && !hasAuc) return null;

  return (
    <div
      style={{
        marginTop: 8,
        padding: '8px 10px',
        borderRadius: 8,
        background: 'rgba(37,99,235,0.08)',
        border: '1px solid rgba(37,99,235,0.2)',
        fontSize: 11,
        color: 'var(--color-text-muted)',
        lineHeight: 1.55,
      }}
    >
      <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 4, fontSize: 10 }}>
        Model accuracy (hold-out test)
      </div>
      {delay_dep_mae != null && (
        <div>Departure delay avg. error: <b>{Math.round(delay_dep_mae)} min</b></div>
      )}
      {delay_arr_mae != null && (
        <div>Arrival delay avg. error: <b>{Math.round(delay_arr_mae)} min</b></div>
      )}
      {hasAuc && (
        <div>Cancellation detection (AUC): <b>{cancellation_auc.toFixed(2)}</b></div>
      )}
      {test_samples != null && (
        <div style={{ fontSize: 10, color: 'var(--color-text-dim)', marginTop: 2 }}>
          Based on {test_samples.toLocaleString()} test flights
        </div>
      )}
    </div>
  );
}

function DelayBar({ low, predicted, high }) {
  const min = Math.min(low, -5);
  const max = Math.max(high, 60);
  const range = max - min || 1;
  const toPercent = (v) => Math.max(0, Math.min(100, ((v - min) / range) * 100));
  const barLow = toPercent(low);
  const barHigh = toPercent(high);
  const barPred = toPercent(predicted);
  const barZero = toPercent(0);

  return (
    <div style={{ marginTop: 10, position: 'relative', height: 20 }}>
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 0,
          right: 0,
          height: 4,
          borderRadius: 2,
          background: 'var(--color-border)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 5,
          height: 10,
          width: 1,
          left: `${barZero}%`,
          background: 'var(--color-text-dim)',
          opacity: 0.5,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 7,
          height: 6,
          borderRadius: 3,
          left: `${barLow}%`,
          width: `${Math.max(barHigh - barLow, 0.5)}%`,
          background: delayMinutesToColor(predicted, 0.25),
          border: `1px solid ${delayMinutesToColor(predicted, 0.45)}`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 4,
          width: 12,
          height: 12,
          borderRadius: '50%',
          left: `calc(${barPred}% - 6px)`,
          background: delayMinutesToColor(predicted, 1),
          border: '2px solid var(--color-surface)',
          boxShadow: `0 0 8px ${delayMinutesToColor(predicted, 0.5)}`,
        }}
      />
    </div>
  );
}

function Stat({ label, value, valueColor }) {
  return (
    <div
      style={{
        background: 'var(--color-surface-2)',
        borderRadius: 8,
        padding: '8px 10px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--color-text-dim)' }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: valueColor || 'var(--color-text)', marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}
