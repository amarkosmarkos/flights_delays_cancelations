import { useEffect } from 'react';
import useGlobeStore from '../stores/globeStore';

export default function useAirports() {
  const airports = useGlobeStore((s) => s.airports);
  const fetchAirports = useGlobeStore((s) => s.fetchAirports);
  const isLoading = useGlobeStore((s) => s.isLoading);

  useEffect(() => {
    if (airports.length === 0) {
      fetchAirports();
    }
  }, [airports.length, fetchAirports]);

  return { airports, isLoading };
}
