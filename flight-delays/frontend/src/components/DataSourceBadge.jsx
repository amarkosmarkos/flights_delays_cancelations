import { useState, useRef, useEffect } from 'react';

export default function DataSourceBadge({ dataSources }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (!dataSources) return null;

  const short = dataSources.explanation_short || 'Prediction data unavailable';
  const full = dataSources.explanation_full;

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 10,
          color: 'var(--color-text-dim)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setOpen(!open)}
        onMouseEnter={() => setOpen(true)}
      >
        <span style={{ fontSize: 12 }}>&#8505;</span>
        <span>{short}</span>
      </div>

      {open && full && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 6,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            padding: 12,
            fontSize: 11,
            color: 'var(--color-text-muted)',
            minWidth: 300,
            maxWidth: 380,
            zIndex: 1000,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            lineHeight: 1.5,
          }}
        >
          <div
            style={{
              fontWeight: 600,
              color: 'var(--color-text)',
              marginBottom: 8,
              fontSize: 12,
            }}
          >
            Prediction methodology
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {full.model && (
                <Row label="Model" value={full.model} />
              )}
              {full.trained && (
                <Row label="Trained" value={full.trained} />
              )}
              {full.data && (
                <Row label="Data" value={full.data} />
              )}
              {full.weather && (
                <Row label="Weather" value={full.weather} />
              )}
              {full.route && (
                <Row label="Route" value={full.route} />
              )}
            </tbody>
          </table>

          {full.fallback && (
            <div
              style={{
                marginTop: 8,
                padding: '6px 8px',
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 4,
                fontSize: 10,
                color: '#f59e0b',
              }}
            >
              <span style={{ marginRight: 4 }}>&#9888;</span>
              Fallback model used
              <div style={{ color: 'var(--color-text-dim)', marginTop: 2 }}>
                {full.fallback}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <tr>
      <td
        style={{
          padding: '2px 8px 2px 0',
          color: 'var(--color-text-dim)',
          verticalAlign: 'top',
          whiteSpace: 'nowrap',
        }}
      >
        {label}:
      </td>
      <td style={{ padding: '2px 0' }}>{value}</td>
    </tr>
  );
}
