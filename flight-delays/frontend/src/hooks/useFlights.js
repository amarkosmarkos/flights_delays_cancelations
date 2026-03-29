import useGlobeStore from '../stores/globeStore';

export default function useFlights() {
  const flights = useGlobeStore((s) => s.selectedAirportFlights);
  const fetchFlights = useGlobeStore((s) => s.fetchFlightsForAirport);
  return { flights, fetchFlights };
}
