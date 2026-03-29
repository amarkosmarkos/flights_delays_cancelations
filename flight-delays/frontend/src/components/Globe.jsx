import { useRef, useEffect, useCallback, useMemo, useState } from 'react';
import ReactGlobe from 'react-globe.gl';
import useGlobeStore from '../stores/globeStore';
import { useIsNarrowLayout } from '../hooks/useMediaQuery';
import { delayLevelToColor } from '../utils/colorScale';

const GLOBE_IMAGE = '//cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg';
const BG_COLOR = '#0a0f1e';
const ARC_OPACITY = 0.2;
const SOLO_ARC_BASE_STROKE = 0.42;
const SOLO_ARC_HIGHLIGHT_STROKE = 0.64;
const MOBILE_DEFAULT_ALTITUDE = 3.8;

/** Deterministic phase in [0, 1) for dash offset — avoids Math.random per arc per frame. */
function arcDashPhase(origin, destination) {
  const s = `${origin}\0${destination}`;
  let h = 2166136261;
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

export default function Globe() {
  const narrow = useIsNarrowLayout();
  const globeRef = useRef();
  const userInterruptedAutoRotateRef = useRef(false);
  const [globeReady, setGlobeReady] = useState(false);
  const [viewport, setViewport] = useState(() => ({
    w: typeof window !== 'undefined' ? window.innerWidth : 0,
    h: typeof window !== 'undefined' ? window.innerHeight : 0,
  }));
  const airportsRaw = useGlobeStore((s) => s.airports);
  const initialRoutes = useGlobeStore((s) => s.initialRoutes);
  const selectedAirport = useGlobeStore((s) => s.selectedAirport);
  const selectedRoutes = useGlobeStore((s) => s.selectedAirportRoutes);
  const selectedRoute = useGlobeStore((s) => s.selectedRoute);
  const selectAirport = useGlobeStore((s) => s.selectAirport);
  const setSelectedRoute = useGlobeStore((s) => s.setSelectedRoute);

  const airports = useMemo(
    () => airportsRaw.filter((a) => a.lat != null && a.lon != null),
    [airportsRaw]
  );

  useEffect(() => {
    const onResize = () =>
      setViewport({ w: window.innerWidth, h: window.innerHeight });
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    if (!globeReady || !narrow) return;
    const globe = globeRef.current;
    if (!globe) return;
    if (selectedAirport || selectedRoute) return;
    globe.pointOfView({ lat: -10, lng: 0, altitude: MOBILE_DEFAULT_ALTITUDE }, 600);
  }, [globeReady, narrow]);

  const arcsData = useMemo(() => {
    /** Solo selection: draw a thin base arc plus animated highlight in same delay color. */
    if (
      selectedRoute &&
      selectedRoute.origin_lat != null &&
      selectedRoute.origin_lon != null &&
      selectedRoute.dest_lat != null &&
      selectedRoute.dest_lon != null
    ) {
      const shared = {
        ...selectedRoute,
        startLat: selectedRoute.origin_lat,
        startLng: selectedRoute.origin_lon,
        endLat: selectedRoute.dest_lat,
        endLng: selectedRoute.dest_lon,
      };
      return [
        {
          ...shared,
          __solo: true,
          __soloLayer: 'base',
        },
        {
          ...shared,
          __solo: true,
          __soloLayer: 'highlight',
        },
      ];
    }

    const source =
      selectedAirport && selectedRoutes.length > 0
        ? selectedRoutes
        : initialRoutes;

    return source
      .filter(
        (r) =>
          r.origin_lat != null &&
          r.origin_lon != null &&
          r.dest_lat != null &&
          r.dest_lon != null
      )
      .map((r) => ({
        ...r,
        startLat: r.origin_lat,
        startLng: r.origin_lon,
        endLat: r.dest_lat,
        endLng: r.dest_lon,
        __solo: false,
      }));
  }, [initialRoutes, selectedRoutes, selectedAirport, selectedRoute]);

  useEffect(() => {
    if (!globeReady) return;
    const globe = globeRef.current;
    if (!globe) return;

    const controls = globe.controls();
    const onControlStart = () => {
      userInterruptedAutoRotateRef.current = true;
      controls.autoRotate = false;
    };

    controls.addEventListener('start', onControlStart);
    controls.autoRotate = !selectedAirport && !selectedRoute && !userInterruptedAutoRotateRef.current;
    controls.autoRotateSpeed = 0.4;

    return () => controls.removeEventListener('start', onControlStart);
  }, [globeReady, selectedAirport, selectedRoute]);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !selectedAirport) return;
    globe.pointOfView(
      { lat: selectedAirport.lat, lng: selectedAirport.lon, altitude: narrow ? 2.4 : 1.5 },
      1000
    );
  }, [selectedAirport, narrow]);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !selectedRoute) return;
    if (
      selectedRoute.origin_lat == null ||
      selectedRoute.origin_lon == null ||
      selectedRoute.dest_lat == null ||
      selectedRoute.dest_lon == null
    ) {
      return;
    }

    // Focus the camera at route midpoint for search context.
    const midLat = (selectedRoute.origin_lat + selectedRoute.dest_lat) / 2;
    const midLng = (selectedRoute.origin_lon + selectedRoute.dest_lon) / 2;

    const dLat = Math.abs(selectedRoute.origin_lat - selectedRoute.dest_lat);
    const dLng = Math.abs(selectedRoute.origin_lon - selectedRoute.dest_lon);
    const span = Math.max(dLat, dLng);
    let altitude = span > 100 ? 2.2 : span > 50 ? 1.8 : 1.4;
    if (narrow) altitude += 0.8;

    globe.pointOfView({ lat: midLat, lng: midLng, altitude }, 1300);
    globe.controls().autoRotate = false;
  }, [selectedRoute]);

  const handlePointClick = useCallback(
    (point) => {
      if (point) selectAirport(point);
    },
    [selectAirport]
  );

  return (
    <ReactGlobe
      ref={globeRef}
      onGlobeReady={() => setGlobeReady(true)}
      globeImageUrl={GLOBE_IMAGE}
      backgroundColor={BG_COLOR}
      atmosphereColor="#1e40af"
      atmosphereAltitude={0.15}
      pointsData={airports}
      pointLat="lat"
      pointLng="lon"
      pointColor={() => 'orange'}
      pointAltitude={0}
      pointRadius={0.02}
      pointsMerge={true}
      pointLabel={(d) =>
        `<div style="text-align:center;font-family:Inter,sans-serif;font-size:12px;">
          <b style="font-size:14px;">${d.iata}</b><br/>
          <span style="color:#9ca3af;">${d.name || ''}</span>
        </div>`
      }
      onPointClick={handlePointClick}
      arcsData={arcsData}
      arcStartLat="startLat"
      arcStartLng="startLng"
      arcEndLat="endLat"
      arcEndLng="endLng"
      arcColor={(d) => {
        if (d.__solo) {
          const alpha = d.__soloLayer === 'highlight' ? 0.98 : 0.62;
          const c = delayLevelToColor(d.delay_level, alpha);
          const tail = delayLevelToColor(d.delay_level, d.__soloLayer === 'highlight' ? 0.2 : 0.1);
          return [c, tail];
        }
        return [
          delayLevelToColor(d.delay_level, ARC_OPACITY * 0.5),
          delayLevelToColor(d.delay_level, ARC_OPACITY + 0.55),
        ];
      }}
      arcStroke={(d) => {
        if (!d.__solo) return 0.35;
        return d.__soloLayer === 'highlight' ? SOLO_ARC_HIGHLIGHT_STROKE : SOLO_ARC_BASE_STROKE;
      }}
      arcCurveResolution={32}
      arcDashLength={(d) => {
        if (!d.__solo) return 0.28;
        return d.__soloLayer === 'highlight' ? 0.16 : 1;
      }}
      arcDashGap={(d) => {
        if (!d.__solo) return 1;
        return d.__soloLayer === 'highlight' ? 0.26 : 0;
      }}
      arcDashInitialGap={(d) => {
        if (!d.__solo) return arcDashPhase(d.origin, d.destination);
        return d.__soloLayer === 'highlight' ? arcDashPhase(d.origin, d.destination) : 0;
      }}
      arcDashAnimateTime={(d) => {
        if (!d.__solo) return 6800;
        return d.__soloLayer === 'highlight' ? 1600 : 0;
      }}
      arcsTransitionDuration={0}
      onArcClick={(arc) => setSelectedRoute(arc)}
      arcLabel={(d) =>
        `<div style="font-family:Inter,sans-serif;font-size:11px;">
          ${d.origin} &#8594; ${d.destination}<br/>
          Delay level: ${d.delay_level || 'UNKNOWN'}
        </div>`
      }
      width={viewport.w}
      height={viewport.h}
    />
  );
}
