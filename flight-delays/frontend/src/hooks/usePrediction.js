import { useState, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || '';

export default function usePrediction() {
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchPrediction = useCallback(async (flightNumber, origin, destination, scheduledDeparture) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        origin,
        destination,
        scheduled_departure: scheduledDeparture,
      });
      const res = await fetch(`${API_BASE}/api/predictions/${flightNumber}?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      setError(err.message);
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return { prediction, loading, error, fetchPrediction };
}
