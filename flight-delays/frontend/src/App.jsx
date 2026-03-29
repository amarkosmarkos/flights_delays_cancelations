import { useEffect } from 'react';
import Globe from './components/Globe';
import SidePanel from './components/SidePanel';
import Legend from './components/Legend';
import RouteInfoPanel from './components/RouteInfoPanel';
import RouteSearchBar from './components/RouteSearchBar';
import LoadingOverlay from './components/LoadingOverlay';
import useGlobeStore from './stores/globeStore';
import { useIsNarrowLayout } from './hooks/useMediaQuery';

export default function App() {
  const fetchAirports = useGlobeStore((s) => s.fetchAirports);
  const fetchInitialRoutes = useGlobeStore((s) => s.fetchInitialRoutes);
  const airports = useGlobeStore((s) => s.airports);
  const initialRoutes = useGlobeStore((s) => s.initialRoutes);
  const isLoading = useGlobeStore((s) => s.isLoading);
  const selectedAirportRoutes = useGlobeStore((s) => s.selectedAirportRoutes);
  const narrow = useIsNarrowLayout();

  useEffect(() => {
    fetchAirports();
    fetchInitialRoutes();
  }, [fetchAirports, fetchInitialRoutes]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <LoadingOverlay visible={airports.length === 0 && isLoading} />

      {/* Title bar */}
      <div
        style={{
          position: 'absolute',
          top: narrow ? 10 : 16,
          left: narrow ? 12 : 16,
          right: narrow ? 12 : undefined,
          maxWidth: narrow ? 'min(100%, calc(100vw - 24px))' : undefined,
          zIndex: 100,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            fontSize: narrow ? 15 : 18,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: narrow ? 1.2 : undefined,
          }}
        >
          Flight Delays & Cancellations
        </div>
        {!narrow && (
          <>
            <div
              style={{
                fontSize: 11,
                color: 'var(--color-text-dim)',
                marginTop: 2,
                lineHeight: 1.35,
              }}
            >
              Global real-time visualization with ML predictions
            </div>
            {airports.length > 0 && (
              <div
                style={{
                  fontSize: 10,
                  color: 'var(--color-text-dim)',
                  marginTop: 4,
                }}
              >
                {airports.length} airports · {initialRoutes.length + selectedAirportRoutes.length} routes
              </div>
            )}
          </>
        )}
      </div>

      <Globe />
      <RouteSearchBar />
      <Legend />
      <RouteInfoPanel />
      <SidePanel />
    </div>
  );
}
