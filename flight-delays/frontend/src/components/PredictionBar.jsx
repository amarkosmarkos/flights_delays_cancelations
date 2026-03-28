const GRADIENT_CANCEL = 'linear-gradient(90deg, #22c55e 0%, #f59e0b 40%, #ef4444 100%)';
const GRADIENT_DELAY = 'linear-gradient(90deg, #22c55e 0%, #f59e0b 30%, #f97316 60%, #ef4444 100%)';

export default function PredictionBar({ value, label, colorScheme = 'cancel', range }) {
  if (value == null) {
    return (
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
          <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
          <span style={{ color: 'var(--color-text-dim)' }}>N/A</span>
        </div>
        <div
          style={{
            height: 6,
            borderRadius: 3,
            background: 'var(--color-surface-2)',
          }}
        />
      </div>
    );
  }

  const clamped = Math.max(0, Math.min(1, value));
  const pct = (clamped * 100).toFixed(1);
  const gradient = colorScheme === 'cancel' ? GRADIENT_CANCEL : GRADIENT_DELAY;

  return (
    <div style={{ marginBottom: 8 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          marginBottom: 2,
        }}
      >
        <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
        <span style={{ color: 'var(--color-text)', fontWeight: 600 }}>{pct}%</span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: 'var(--color-surface-2)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${clamped * 100}%`,
            borderRadius: 3,
            background: gradient,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      {range && (
        <div style={{ fontSize: 10, color: 'var(--color-text-dim)', marginTop: 2 }}>
          {range}
        </div>
      )}
    </div>
  );
}
