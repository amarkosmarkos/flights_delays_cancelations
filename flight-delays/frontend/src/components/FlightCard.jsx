import { useState } from 'react';
import PredictionBar from './PredictionBar';
import DataSourceBadge from './DataSourceBadge';
import { formatTime } from '../utils/formatters';
import usePrediction from '../hooks/usePrediction';

export default function FlightCard({ flight }) {
  const { prediction, loading, error, fetchPrediction } = usePrediction();
  const [expanded, setExpanded] = useState(false);

  const handleExpand = () => {
    if (!expanded && !prediction && !loading) {
      fetchPrediction(
        flight.flight_number,
        flight.origin_iata,
        flight.destination_iata,
        flight.scheduled_departure
      );
    }
    setExpanded(!expanded);
  };

  const cancelProb = prediction?.predicted_cancellation_probability;
  const depDelay = prediction?.predicted_departure_delay_minutes ?? prediction?.predicted_delay_minutes;
  const arrDelay = prediction?.predicted_arrival_delay_minutes;
  const intervalLow = prediction?.prediction_interval_low;
  const intervalHigh = prediction?.prediction_interval_high;
  const delayRange =
    intervalLow != null && intervalHigh != null
      ? `likely ${Math.round(intervalLow)}–${Math.round(intervalHigh)} min`
      : null;
  const mq = prediction?.model_quality;

  return (
    <div
      style={{
        background: 'var(--color-surface-2)',
        borderRadius: 8,
        padding: '10px 12px',
        marginBottom: 8,
        cursor: 'pointer',
        border: expanded ? '1px solid var(--color-border)' : '1px solid transparent',
        transition: 'border-color 0.2s',
      }}
      onClick={handleExpand}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{flight.flight_number}</span>
          <span style={{ color: 'var(--color-text-muted)', fontSize: 12, marginLeft: 8 }}>
            {flight.airline_code}
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 13, fontWeight: 500 }}>
            {formatTime(flight.scheduled_departure)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>
            → {flight.destination_iata}
          </div>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--color-border)' }}>
          {loading ? (
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>Loading prediction...</div>
          ) : error ? (
            <div style={{ fontSize: 11, color: '#f87171', lineHeight: 1.45 }}>{error}</div>
          ) : prediction ? (
            <>
              <PredictionBar
                value={cancelProb}
                label="Cancellation probability"
                colorScheme="cancel"
              />
              <PredictionBar
                value={depDelay != null ? Math.min(depDelay / 120, 1) : null}
                label="Departure delay"
                colorScheme="delay"
                range={delayRange}
              />
              {depDelay != null && (
                <div style={{ fontSize: 12, color: 'var(--color-text)', marginBottom: 4 }}>
                  Departure delay: <b>{Math.round(depDelay)} min</b>
                </div>
              )}
              {arrDelay != null && (
                <div style={{ fontSize: 12, color: 'var(--color-text)', marginBottom: 6 }}>
                  Arrival delay: <b>{Math.round(arrDelay)} min</b>
                </div>
              )}
              {mq && <ModelQualityBadge quality={mq} />}
              <DataSourceBadge dataSources={prediction.data_sources_used} />
            </>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>
              Click to load prediction
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ModelQualityBadge({ quality }) {
  if (!quality) return null;
  const { delay_dep_mae, delay_arr_mae, cancellation_auc, test_samples } = quality;
  const parts = [];
  if (delay_dep_mae != null) parts.push(`dep. error ${Math.round(delay_dep_mae)} min`);
  if (delay_arr_mae != null) parts.push(`arr. error ${Math.round(delay_arr_mae)} min`);
  if (cancellation_auc != null) parts.push(`AUC ${cancellation_auc.toFixed(2)}`);
  if (!parts.length) return null;

  return (
    <div
      style={{
        marginBottom: 6,
        padding: '4px 8px',
        borderRadius: 6,
        background: 'rgba(37,99,235,0.08)',
        border: '1px solid rgba(37,99,235,0.18)',
        fontSize: 10,
        color: 'var(--color-text-dim)',
        lineHeight: 1.5,
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--color-text-muted)' }}>Hold-out test: </span>
      {parts.join(' · ')}
      {test_samples != null && ` (${test_samples.toLocaleString()} flights)`}
    </div>
  );
}
