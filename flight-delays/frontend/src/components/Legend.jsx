import { useIsNarrowLayout } from '../hooks/useMediaQuery';

export default function Legend() {
  const narrow = useIsNarrowLayout();
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
        bottom: narrow ? 'calc(10px + env(safe-area-inset-bottom))' : 16,
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: narrow ? '8px 10px' : '10px 16px',
        zIndex: 210,
        display: 'flex',
        alignItems: 'center',
        flexWrap: narrow ? 'wrap' : 'nowrap',
        justifyContent: narrow ? 'center' : 'flex-start',
        gap: narrow ? 8 : 12,
        maxWidth: narrow
          ? 'calc(100vw - 16px - env(safe-area-inset-left) - env(safe-area-inset-right))'
          : undefined,
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          fontSize: narrow ? 10 : 11,
          fontWeight: 600,
          color: 'var(--color-text)',
          marginRight: narrow ? 0 : 4,
          whiteSpace: narrow ? 'normal' : 'nowrap',
          width: narrow ? '100%' : undefined,
          textAlign: narrow ? 'center' : undefined,
          flexBasis: narrow ? '100%' : undefined,
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
            fontSize: narrow ? 9 : 10,
            color: 'var(--color-text-muted)',
            whiteSpace: narrow ? 'normal' : 'nowrap',
            lineHeight: 1.25,
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
