import { useEffect, useState } from 'react';
import useGlobeStore from '../stores/globeStore';
import { useIsNarrowLayout } from '../hooks/useMediaQuery';

const API_BASE = import.meta.env.VITE_API_URL || '';

function airportLabel(ap) {
  return `${ap.city || ap.name || ap.iata} (${ap.iata})`;
}

function AirportAutocompleteInput({
  value,
  onChange,
  onPick,
  placeholder,
  suggestions,
  open,
  setOpen,
}) {
  return (
    <div style={{ position: 'relative' }}>
      <input
        placeholder={placeholder}
        value={value}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        style={inputStyle}
      />
      {open && suggestions.length > 0 && (
        <div style={dropdownStyle}>
          {suggestions.map((ap) => (
            <button
              key={ap.iata}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(ap);
                setOpen(false);
              }}
              style={dropdownItemStyle}
            >
              <span style={{ color: 'var(--color-text)' }}>{airportLabel(ap)}</span>
              <span style={{ color: 'var(--color-text-dim)', fontSize: 10 }}>{ap.country}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function RouteSearchBar() {
  const narrow = useIsNarrowLayout();
  const setSelectedRoute = useGlobeStore((s) => s.setSelectedRoute);
  const clearSelectedRoute = useGlobeStore((s) => s.clearSelectedRoute);

  const [originQuery, setOriginQuery] = useState('');
  const [destinationQuery, setDestinationQuery] = useState('');
  const [originSuggestions, setOriginSuggestions] = useState([]);
  const [destinationSuggestions, setDestinationSuggestions] = useState([]);
  const [originOpen, setOriginOpen] = useState(false);
  const [destinationOpen, setDestinationOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const q = originQuery.trim();
    if (q.length < 2) {
      setOriginSuggestions([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/airports/search?q=${encodeURIComponent(q)}&limit=8`,
          { signal: ctrl.signal }
        );
        if (!res.ok) return;
        setOriginSuggestions(await res.json());
      } catch {
        // ignore aborted/temporary network errors
      }
    }, 220);
    return () => {
      ctrl.abort();
      clearTimeout(t);
    };
  }, [originQuery]);

  useEffect(() => {
    const q = destinationQuery.trim();
    if (q.length < 2) {
      setDestinationSuggestions([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/airports/search?q=${encodeURIComponent(q)}&limit=8`,
          { signal: ctrl.signal }
        );
        if (!res.ok) return;
        setDestinationSuggestions(await res.json());
      } catch {
        // ignore aborted/temporary network errors
      }
    }, 220);
    return () => {
      ctrl.abort();
      clearTimeout(t);
    };
  }, [destinationQuery]);

  const submitSearch = async (e) => {
    e.preventDefault();
    setError('');
    if (!originQuery.trim() || !destinationQuery.trim()) {
      setError('Choose both origin and destination.');
      return;
    }
    try {
      setIsSearching(true);
      const params = new URLSearchParams({
        origin: originQuery.trim(),
        destination: destinationQuery.trim(),
      });
      const res = await fetch(`${API_BASE}/api/routes/search?${params.toString()}`);
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || `Search failed (${res.status})`);
      }
      const route = await res.json();
      setSelectedRoute(route);
      setOriginOpen(false);
      setDestinationOpen(false);
    } catch (err) {
      setError(err.message || 'Route not found');
      clearSelectedRoute();
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: narrow ? 84 : 14,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 240,
        width: narrow ? 'calc(100vw - 16px)' : 'min(820px, calc(100vw - 40px))',
        paddingLeft: narrow ? 'env(safe-area-inset-left)' : undefined,
        paddingRight: narrow ? 'env(safe-area-inset-right)' : undefined,
      }}
    >
      <form
        onSubmit={submitSearch}
        style={{
          display: 'grid',
          gridTemplateColumns: narrow ? '1fr' : '1fr 1fr auto',
          gap: 8,
          background: 'rgba(17,24,39,0.88)',
          border: '1px solid var(--color-border)',
          backdropFilter: 'blur(6px)',
          borderRadius: 10,
          padding: narrow ? 10 : 8,
        }}
      >
        <AirportAutocompleteInput
          value={originQuery}
          onChange={setOriginQuery}
          onPick={(ap) => setOriginQuery(ap.iata)}
          placeholder="Origin city or airport (e.g. Madrid, MAD)"
          suggestions={originSuggestions}
          open={originOpen}
          setOpen={setOriginOpen}
        />
        <AirportAutocompleteInput
          value={destinationQuery}
          onChange={setDestinationQuery}
          onPick={(ap) => setDestinationQuery(ap.iata)}
          placeholder="Destination city or airport (e.g. Tokyo, NRT)"
          suggestions={destinationSuggestions}
          open={destinationOpen}
          setOpen={setDestinationOpen}
        />
        <button
          type="submit"
          disabled={isSearching}
          style={{
            padding: narrow ? '10px 14px' : '0 14px',
            borderRadius: 8,
            border: '1px solid #2563eb',
            background: isSearching ? '#1d4ed8a0' : '#2563eb',
            color: '#fff',
            fontWeight: 600,
            cursor: isSearching ? 'default' : 'pointer',
            minHeight: 38,
            width: narrow ? '100%' : undefined,
          }}
        >
          {isSearching ? 'Searching...' : 'Search route'}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#fca5a5', textAlign: 'center' }}>
          {error}
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  minHeight: 38,
  borderRadius: 8,
  border: '1px solid var(--color-border)',
  outline: 'none',
  background: 'var(--color-surface-2)',
  color: 'var(--color-text)',
  padding: '0 12px',
  fontSize: 13,
  width: '100%',
};

const dropdownStyle = {
  position: 'absolute',
  left: 0,
  right: 0,
  top: 42,
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 8,
  overflow: 'hidden',
  zIndex: 260,
  maxHeight: 240,
  overflowY: 'auto',
};

const dropdownItemStyle = {
  width: '100%',
  border: 'none',
  background: 'transparent',
  textAlign: 'left',
  padding: '9px 10px',
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};
