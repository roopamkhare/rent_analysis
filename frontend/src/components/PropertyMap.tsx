"use client";

import { useEffect, useRef, useCallback } from "react";
import L from "leaflet";
import type { AnalysisResult, Listing } from "@/lib/analyze";
import { fmtDollar } from "@/lib/format";

interface Props {
  listings: Listing[];
  results: Map<string, AnalysisResult>;
  selectedZpid: string | null;
  onSelect: (zpid: string) => void;
}

export default function PropertyMap({ listings, results, selectedZpid, onSelect }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<string, L.CircleMarker>>(new Map());
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // Keep onSelect in a ref so marker callbacks always use the latest
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Initialize map ONCE on mount
  useEffect(() => {
    if (!containerRef.current) return;

    const map = L.map(containerRef.current, {
      center: [32.95, -96.75],   // DFW default
      zoom: 11,
      scrollWheelZoom: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);

    const lg = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerGroupRef.current = lg;

    return () => {
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
      markersRef.current.clear();
    };
  }, []); // truly once

  // Rebuild markers whenever listings or results change
  useEffect(() => {
    const map = mapRef.current;
    const lg = layerGroupRef.current;
    if (!map || !lg) return;

    // Clear old markers
    lg.clearLayers();
    markersRef.current.clear();

    const valid = listings.filter((l) => l.latitude && l.longitude);
    if (!valid.length) return;

    // Fit map to data bounds
    const bounds = L.latLngBounds(valid.map((l) => [l.latitude, l.longitude] as [number, number]));
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });

    // Compute CF scale
    const cfValues = valid.map((l) => {
      const r = results.get(l.zpid);
      return r ? r.monthlyCashFlow : 0;
    });
    const cfMax = Math.max(...cfValues.map(Math.abs), 1);

    valid.forEach((l) => {
      const r = results.get(l.zpid);
      if (!r) return;
      const cf = r.monthlyCashFlow;
      const irr = r.irr;
      const color = irr >= 10 ? "#06A77D" : irr >= 5 ? "#F39C12" : "#E74C3C";
      const absCf = Math.abs(cf);
      const radius = cf >= 0
        ? 6 + (absCf / cfMax) * 22
        : 4 + (absCf / cfMax) * 6;

      const marker = L.circleMarker([l.latitude, l.longitude], {
        radius,
        fillColor: color,
        color: "#fff",
        weight: 1.5,
        fillOpacity: 0.85,
      });

      marker.bindPopup(
        `<div style="font-size:13px;line-height:1.5">
          <b>${l.streetAddress}</b><br/>
          Price: ${fmtDollar(l.price)}<br/>
          Rent: ${fmtDollar(r.effectiveMonthlyRent)}/mo<br/>
          CF: <span style="color:${color}">${fmtDollar(cf)}/mo</span><br/>
          IRR: ${r.irr.toFixed(1)}% · Cap: ${r.capRate.toFixed(1)}%
        </div>`,
        { closeButton: false },
      );

      marker.on("click", () => onSelectRef.current(l.zpid));
      marker.on("mouseover", () => marker.openPopup());
      marker.on("mouseout", () => marker.closePopup());

      lg.addLayer(marker);
      markersRef.current.set(l.zpid, marker);
    });
  }, [listings, results]);

  // Highlight selected marker
  useEffect(() => {
    markersRef.current.forEach((m, zpid) => {
      const isSelected = zpid === selectedZpid;
      m.setStyle({
        weight: isSelected ? 3 : 1.5,
        color: isSelected ? "#F39C12" : "#fff",
      });
      if (isSelected) {
        m.bringToFront();
        mapRef.current?.panTo(m.getLatLng(), { animate: true });
      }
    });
  }, [selectedZpid]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-[var(--color-border)]"
      style={{ height: 480 }}
    />
  );
}
