import useGlobeStore from '../stores/globeStore';
import FlightCard from './FlightCard';
import { delayLevelToHex } from '../utils/colorScale';
import { formatDelay, formatPct, formatNumber, formatRelative } from '../utils/formatters';

export default function SidePanel() {
  const selectedAirport = useGlobeStore((s) => s.selectedAirport);
  const flights = useGlobeStore((s) => s.selectedAirportFlights);
  const routes = useGlobeStore((s) => s.selectedAirportRoutes);
  const clearSelection = useGlobeStore((s) => s.clearSelection);
  const isLoading = useGlobeStore((s) => s.isLoading);

  if (!selectedAirport) return null;

  const ap = selectedAirport;

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: 380,
        height: '100%',
        background: 'var(--color-surface)',
        borderLeft: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 500,
        overflow: 'hidden',
        animation: 'slideIn 0.3s ease',
      }}
    >
      <style>{`@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>

      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{ap.iata}</div>
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 2 }}>
              {ap.name}
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>
              {ap.city}{ap.city && ap.country ? ', ' : ''}{ap.country}
              {ap.region && (
                <span
                  style={{
                    marginLeft: 6,
                    padding: '1px 6px',
                    background: 'var(--color-surface-2)',
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 600,
                  }}
                >
                  {ap.region}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={clearSelection}
            style={{
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              borderRadius: 6,
              width: 28,
              height: 28,
              cursor: 'pointer',
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ✕
          </button>
        </div>

        {/* Stats grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: 8,
            marginTop: 12,
          }}
        >
          <StatBox
            label="Avg Delay"
            value={formatDelay(ap.avg_delay_minutes)}
          />
          <StatBox
            label="Cancel Rate"
            value={formatPct(ap.cancellation_rate)}
          />
          <StatBox
            label="Flights 7d"
            value={formatNumber(ap.total_departures_7d)}
          />
        </div>

        {/* Delay level badge */}
        <div
          style={{
            marginTop: 10,
            display: 'inline-block',
            padding: '3px 10px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 600,
            color: delayLevelToHex(ap.delay_level),
            background: `${delayLevelToHex(ap.delay_level)}18`,
            border: `1px solid ${delayLevelToHex(ap.delay_level)}40`,
          }}
        >
          {ap.delay_level || 'UNKNOWN'}
        </div>

        {ap.data_freshness && (
          <div style={{ fontSize: 10, color: 'var(--color-text-dim)', marginTop: 6 }}>
            Data updated {formatRelative(ap.data_freshness)}
          </div>
        )}
      </div>

      {/* Route count */}
      {routes.length > 0 && (
        <div
          style={{
            padding: '8px 20px',
            borderBottom: '1px solid var(--color-border)',
            fontSize: 11,
            color: 'var(--color-text-dim)',
            flexShrink: 0,
          }}
        >
          {routes.length} routes displayed on globe
        </div>
      )}

      {/* Flight list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px',
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--color-text-muted)',
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Next 24h Departures
        </div>
        {isLoading ? (
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)', padding: 16 }}>
            Loading flights...
          </div>
        ) : flights.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)', padding: 16 }}>
            No upcoming flights found. This may be due to limited real-time data coverage.
          </div>
        ) : (
          flights.map((f) => <FlightCard key={f.id} flight={f} />)
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value }) {
  return (
    <div
      style={{
        background: 'var(--color-surface-2)',
        borderRadius: 6,
        padding: '6px 8px',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: 9, color: 'var(--color-text-dim)', marginTop: 2 }}>{label}</div>
    </div>
  );
}
