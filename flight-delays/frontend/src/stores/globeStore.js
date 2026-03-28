import { create } from 'zustand';

const API_BASE = import.meta.env.VITE_API_URL || '';

const useGlobeStore = create((set, get) => ({
  airports: [],
  initialRoutes: [],
  selectedRoute: null,
  selectedAirport: null,
  selectedAirportRoutes: [],
  selectedAirportFlights: [],
  isLoading: false,
  lastUpdated: null,
  viewMode: 'globe',

  fetchAirports: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/airports`);
      const data = await res.json();
      set({ airports: data, lastUpdated: new Date(), isLoading: false });
    } catch (err) {
      console.error('Failed to fetch airports:', err);
      set({ isLoading: false });
    }
  },

  fetchInitialRoutes: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/routes/popular`);
      const data = await res.json();
      set({ initialRoutes: data });
    } catch (err) {
      console.error('Failed to fetch initial routes:', err);
    }
  },

  selectAirport: async (airport) => {
    set({
      selectedAirport: airport,
      selectedRoute: null,
      viewMode: 'airport',
      isLoading: true,
      selectedAirportRoutes: [],
      selectedAirportFlights: [],
    });

    try {
      const [routesRes, flightsRes] = await Promise.all([
        fetch(`${API_BASE}/api/routes/${airport.iata}`),
        fetch(`${API_BASE}/api/flights/${airport.iata}?direction=departures&limit=50`),
      ]);
      const routes = await routesRes.json();
      const flights = await flightsRes.json();
      set({
        selectedAirportRoutes: routes,
        selectedAirportFlights: flights,
        isLoading: false,
      });
    } catch (err) {
      console.error('Failed to fetch airport details:', err);
      set({ isLoading: false });
    }
  },

  clearSelection: () => {
    set({
      selectedAirport: null,
      selectedAirportRoutes: [],
      selectedAirportFlights: [],
      selectedRoute: null,
      viewMode: 'globe',
    });
  },

  setSelectedRoute: (route) => set({ selectedRoute: route }),
  clearSelectedRoute: () => set({ selectedRoute: null }),
}));

export default useGlobeStore;
