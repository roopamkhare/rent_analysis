"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";

const HistoryCharts = dynamic(() => import("@/components/HistoryCharts"), { ssr: false });

interface Snapshot {
  date: string;
  totalListings: number;
  medianPrice: number;
  medianRent: number;
  avgPricePerSqFt: number;
  byZipcode: Record<string, { count: number; medianPrice: number; medianRent: number }>;
  byHomeType: Record<string, number>;
}

interface PropertyEntry {
  date: string;
  price: number;
  rent: number | null;
  address: string;
  zipcode: string;
}

interface HistoryData {
  snapshots: Snapshot[];
  properties: Record<string, PropertyEntry[]>;
}

export default function HistoryPage() {
  const [data, setData] = useState<HistoryData | null>(null);

  useEffect(() => {
    fetch("/history.json")
      .then((r) => r.json())
      .then((d: HistoryData) => setData(d))
      .catch(() => setData({ snapshots: [], properties: {} }));
  }, []);

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen text-[var(--color-muted)]">
        Loading history…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="text-lg font-bold">📊 DFW Market History</h1>
          <div className="flex gap-4 text-sm">
            <Link href="/" className="text-[var(--color-muted)] hover:text-[var(--color-text)] transition-colors">
              ← ROI Analyzer
            </Link>
          </div>
        </div>
        {data.snapshots.length > 0 && (
          <p className="text-xs text-[var(--color-muted)]">
            {data.snapshots.length} snapshot{data.snapshots.length !== 1 ? "s" : ""} ·
            Latest: {data.snapshots[data.snapshots.length - 1].date} ·
            {Object.keys(data.properties).length.toLocaleString()} properties tracked
          </p>
        )}
      </nav>

      {/* Content */}
      <main className="max-w-6xl mx-auto p-6">
        {data.snapshots.length === 0 ? (
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-8 text-center">
            <p className="text-lg mb-2">No history data yet</p>
            <p className="text-sm text-[var(--color-muted)]">
              Run the scraper and build_history.py to generate snapshots.
            </p>
          </div>
        ) : (
          <HistoryCharts snapshots={data.snapshots} properties={data.properties} />
        )}

        {/* Footer */}
        <div className="mt-8 pt-4 border-t border-[var(--color-border)] text-center text-xs text-[var(--color-muted)]">
          Data updates automatically every Sunday via GitHub Actions ·{" "}
          {data.snapshots.length} snapshot{data.snapshots.length !== 1 ? "s" : ""} ·{" "}
          {Object.keys(data.properties).length.toLocaleString()} properties tracked
        </div>
      </main>
    </div>
  );
}
