import useGlobeStore from '../stores/globeStore';
import { formatPct } from '../utils/formatters';

function reliabilityToColor(reliability) {
  if (reliability === 'HIGH') return 'var(--color-delay-low)';
  if (reliability === 'MEDIUM') return 'var(--color-delay-medium)';
  return 'var(--color-delay-high)';
}

export default function RouteInfoPanel() {
  const route = useGlobeStore((s) => s.selectedRoute);
  const clearSelectedRoute = useGlobeStore((s) => s.clearSelectedRoute);

  if (!route) return null;

  const estimatedDelay =
    route.estimated_delay_minutes ?? route.avg_delay_minutes ?? null;
  const delayText =
    estimatedDelay == null ? 'No reliable estimate yet' : `${Math.round(estimatedDelay)} min`;

  return (
    <div
      style={{
        position: 'absolute',
        right: 16,
        bottom: 16,
        width: 320,
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 10,
        padding: 12,
        zIndex: 220,
        boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>
              {route.origin} {'->'} {route.destination}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>
            {route.airline ? `Airline ${route.airline}` : 'Route aggregate'}
          </div>
        </div>
        <button
          type="button"
          onClick={clearSelectedRoute}
          aria-label="Close route detail and show all routes on the globe"
          title="Close"
          style={{
            flexShrink: 0,
            width: 28,
            height: 28,
            lineHeight: 1,
            borderRadius: 6,
            background: 'var(--color-surface-2)',
            color: 'var(--color-text-muted)',
            border: '1px solid var(--color-border)',
            cursor: 'pointer',
            fontSize: 16,
          }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          marginTop: 10,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 8,
        }}
      >
        <Stat label="Estimated delay" value={delayText} />
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

      <div style={{ marginTop: 10, fontSize: 10, color: 'var(--color-text-dim)' }}>
        Source: {route.data_source || 'UNKNOWN'}.
        {route.reliability === 'LOW' &&
          ' Low reliability means this route lacks enough recent delay history.'}
      </div>
    </div>
  );
}

function Stat({ label, value, valueColor }) {
  return (
    <div
      style={{
        background: 'var(--color-surface-2)',
        borderRadius: 6,
        padding: '6px 8px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--color-text-dim)' }}>{label}</div>
      <div style={{ fontSize: 12, color: valueColor || 'var(--color-text)', marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}
