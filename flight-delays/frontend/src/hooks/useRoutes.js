import useGlobeStore from '../stores/globeStore';

export default function useRoutes() {
  const routes = useGlobeStore((s) => s.selectedAirportRoutes);
  const fetchRoutes = useGlobeStore((s) => s.fetchRoutesForAirport);
  return { routes, fetchRoutes };
}
