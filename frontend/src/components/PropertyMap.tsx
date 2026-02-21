"use client";

import { useEffect, useRef } from "react";
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
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize map once
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const valid = listings.filter((l) => l.latitude && l.longitude);
    if (!valid.length) return;

    const center: [number, number] = [
      valid.reduce((s, l) => s + l.latitude, 0) / valid.length,
      valid.reduce((s, l) => s + l.longitude, 0) / valid.length,
    ];

    const map = L.map(containerRef.current, {
      center,
      zoom: 12,
      scrollWheelZoom: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;

    // Add markers — color by IRR, size by monthly cash flow
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
      // Color by IRR tier
      const color = irr >= 10 ? "#06A77D" : irr >= 5 ? "#F39C12" : "#E74C3C";
      // Size by absolute cash flow; CF-positive gets bigger circles
      const absCf = Math.abs(cf);
      const radius = cf >= 0
        ? 6 + (absCf / cfMax) * 22   // positive CF: 6–28
        : 4 + (absCf / cfMax) * 6;   // negative CF: 4–10 (small)

      const marker = L.circleMarker([l.latitude, l.longitude], {
        radius,
        fillColor: color,
        color: "#fff",
        weight: 1.5,
        fillOpacity: 0.85,
      }).addTo(map);

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

      marker.on("click", () => onSelect(l.zpid));
      marker.on("mouseover", () => marker.openPopup());
      marker.on("mouseout", () => marker.closePopup());

      markersRef.current.set(l.zpid, marker);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
