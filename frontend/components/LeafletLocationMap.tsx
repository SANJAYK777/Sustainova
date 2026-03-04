'use client';

import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    L?: any;
  }
}

type LeafletLocationMapProps = {
  latitude?: number | null;
  longitude?: number | null;
  zoom?: number;
  heightClassName?: string;
  onSelect?: (latitude: number, longitude: number) => void;
};

const LEAFLET_CSS_ID = 'leaflet-css-cdn';
const LEAFLET_SCRIPT_ID = 'leaflet-js-cdn';

function ensureLeafletLoaded(onReady: () => void, onError: () => void) {
  if (window.L) {
    onReady();
    return;
  }

  if (!document.getElementById(LEAFLET_CSS_ID)) {
    const css = document.createElement('link');
    css.id = LEAFLET_CSS_ID;
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    css.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
    css.crossOrigin = '';
    document.head.appendChild(css);
  }

  const existingScript = document.getElementById(LEAFLET_SCRIPT_ID) as HTMLScriptElement | null;
  if (existingScript) {
    existingScript.addEventListener('load', onReady);
    existingScript.addEventListener('error', onError);
    return;
  }

  const script = document.createElement('script');
  script.id = LEAFLET_SCRIPT_ID;
  script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
  script.crossOrigin = '';
  script.async = true;
  script.onload = onReady;
  script.onerror = onError;
  document.body.appendChild(script);
}

export default function LeafletLocationMap({
  latitude,
  longitude,
  zoom = 15,
  heightClassName = 'h-[350px] md:h-[420px] w-full',
  onSelect,
}: LeafletLocationMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [loadError, setLoadError] = useState('');
  const [mapReady, setMapReady] = useState(false);

  const lat = typeof latitude === 'number' ? latitude : 20.5937;
  const lng = typeof longitude === 'number' ? longitude : 78.9629;
  const initialZoom = typeof latitude === 'number' && typeof longitude === 'number' ? zoom : 5;

  useEffect(() => {
    let active = true;

    const initializeMap = () => {
      if (!active || !containerRef.current || !window.L || mapRef.current) return;

      const map = window.L.map(containerRef.current).setView([lat, lng], initialZoom);
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map);

      const marker = window.L.marker([lat, lng]).addTo(map);

      if (onSelect) {
        map.on('click', (e: any) => {
          const selectedLat = Number(e.latlng.lat.toFixed(6));
          const selectedLng = Number(e.latlng.lng.toFixed(6));
          marker.setLatLng([selectedLat, selectedLng]);
          onSelect(selectedLat, selectedLng);
        });
      }

      mapRef.current = map;
      markerRef.current = marker;
      setMapReady(true);
      setTimeout(() => {
        map.invalidateSize();
      }, 100);
    };

    ensureLeafletLoaded(
      () => initializeMap(),
      () => setLoadError('Unable to load map right now.')
    );

    return () => {
      active = false;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    const handleResize = () => {
      if (mapRef.current) {
        mapRef.current.invalidateSize();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [mapReady]);

  useEffect(() => {
    if (!mapRef.current || !markerRef.current) return;
    markerRef.current.setLatLng([lat, lng]);
    mapRef.current.setView([lat, lng], zoom);
  }, [lat, lng, zoom]);

  return (
    <div className={`w-full max-w-full overflow-hidden rounded-2xl border border-slate-200 shadow-lg ${heightClassName}`}>
      {loadError ? (
        <div className="flex h-full items-center justify-center bg-[#f8f5ee] px-4 text-sm text-red-700">{loadError}</div>
      ) : (
        <div ref={containerRef} className="h-full w-full" />
      )}
    </div>
  );
}
