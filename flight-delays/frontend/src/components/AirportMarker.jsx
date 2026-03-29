import { delayLevelToHex } from '../utils/colorScale';

export default function AirportMarker({ airport }) {
  const color = delayLevelToHex(airport.delay_level);
  const size = Math.sqrt((airport.total_departures_7d || 1) / 1000) * 6 + 4;

  return (
    <div
      className="pulse-marker"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: `0 0 ${size}px ${color}`,
        cursor: 'pointer',
      }}
      title={`${airport.iata} — ${airport.name}`}
    />
  );
}
