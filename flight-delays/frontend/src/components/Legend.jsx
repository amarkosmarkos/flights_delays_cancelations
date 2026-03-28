export default function Legend() {
  const items = [
    { label: 'Low (<10 min)', color: 'var(--color-delay-low)' },
    { label: 'Medium (10-25 min)', color: 'var(--color-delay-medium)' },
    { label: 'High (25-45 min)', color: 'var(--color-delay-high)' },
    { label: 'Severe (>45 min)', color: 'var(--color-delay-severe)' },
    { label: 'No delay data', color: 'var(--color-delay-unknown)' },
  ];

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: '10px 16px',
        zIndex: 210,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--color-text)',
          marginRight: 4,
          whiteSpace: 'nowrap',
        }}
      >
        Route Delay Level
      </div>
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 10,
            color: 'var(--color-text-muted)',
            whiteSpace: 'nowrap',
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: item.color,
              flexShrink: 0,
            }}
          />
          {item.label}
        </div>
      ))}
    </div>
  );
}
