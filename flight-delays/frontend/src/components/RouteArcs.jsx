import { delayLevelToColor, delayLevelToHex } from '../utils/colorScale';

export default function RouteArcs({ routes }) {
  if (!routes || routes.length === 0) return null;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: '8px 12px',
        fontSize: 11,
        color: 'var(--color-text-muted)',
        maxWidth: 200,
      }}
    >
      <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
        {routes.length} routes shown
      </div>
      <div>
        Arcs colored by delay level. Thickness by flight volume.
      </div>
    </div>
  );
}
