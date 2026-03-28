import { useState } from 'react';
import PredictionBar from './PredictionBar';
import DataSourceBadge from './DataSourceBadge';
import { formatTime } from '../utils/formatters';
import usePrediction from '../hooks/usePrediction';

export default function FlightCard({ flight }) {
  const { prediction, loading, fetchPrediction } = usePrediction();
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
  const delayMin = prediction?.predicted_delay_minutes;
  const intervalLow = prediction?.prediction_interval_low;
  const intervalHigh = prediction?.prediction_interval_high;
  const delayRange =
    intervalLow != null && intervalHigh != null
      ? `likely ${Math.round(intervalLow)}–${Math.round(intervalHigh)} min`
      : null;

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
          ) : prediction ? (
            <>
              <PredictionBar
                value={cancelProb}
                label="Cancellation probability"
                colorScheme="cancel"
              />
              <PredictionBar
                value={delayMin != null ? Math.min(delayMin / 120, 1) : null}
                label="Delay severity"
                colorScheme="delay"
                range={delayRange}
              />
              {delayMin != null && (
                <div style={{ fontSize: 12, color: 'var(--color-text)', marginBottom: 6 }}>
                  Predicted delay: <b>{Math.round(delayMin)} min</b>
                </div>
              )}
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
