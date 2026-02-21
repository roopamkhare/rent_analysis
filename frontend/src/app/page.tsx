"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { analyze, computeMedianRentPct, type AnalysisParams, type AnalysisResult, type Listing } from "@/lib/analyze";
import Sidebar from "@/components/Sidebar";
import PropertyDetail from "@/components/PropertyDetail";
import PortfolioTable from "@/components/PortfolioTable";

// Leaflet must be client-only
const PropertyMap = dynamic(() => import("@/components/PropertyMap"), { ssr: false });

const DEFAULT_PARAMS: AnalysisParams = {
  interestRate: 6.5,
  loanTerm: 30,
  downPaymentPct: 20,
  closingCostsPct: 3,
  sellingCostsPct: 6,
  holdingYears: 10,
  appreciationRate: 3.5,
  rentIncreaseRate: 3,
  maintenancePct: 1,
  vacancyRate: 5,
  insurancePct: 0.5,
  mgmtFeePct: 0,
  spGrowthRate: 10,
  rentEstimatePct: 0.55,  // updated once data loads
};

interface ListingsData {
  region?: string;
  scraped_at?: string;
  zipcodes?: string[];
  total_listings?: number;
  listings: Listing[];
}

export default function Home() {
  const [raw, setRaw] = useState<Listing[]>([]);
  const [meta, setMeta] = useState<{ region?: string; scraped_at?: string; zipcodes?: string[] }>({});
  const [params, setParams] = useState<AnalysisParams>(DEFAULT_PARAMS);
  const [selectedZpid, setSelectedZpid] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("monthlyCashFlow");
  const [priceRange, setPriceRange] = useState<[number, number]>([0, 10_000_000]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [hideFlagged, setHideFlagged] = useState(false);
  const detailRef = useRef<HTMLDivElement>(null);

  // Load data
  useEffect(() => {
    fetch("/listings.json")
      .then((r) => r.json())
      .then((data: ListingsData) => {
        const listings = data.listings.filter((l) => l.price > 0);
        setRaw(listings);
        setMeta({ region: data.region, scraped_at: data.scraped_at, zipcodes: data.zipcodes });
        const prices = listings.map((l) => l.price);
        setPriceRange([Math.min(...prices), Math.max(...prices)]);
        setSelectedTypes([...new Set(listings.map((l) => l.homeType))].sort());
        // compute data-driven rent estimate fallback
        const medianPct = computeMedianRentPct(listings);
        setParams((prev) => ({ ...prev, rentEstimatePct: Math.round(medianPct * 100) / 100 }));
      });
  }, []);

  const priceMinMax: [number, number] = useMemo(() => {
    if (!raw.length) return [0, 1_000_000];
    const prices = raw.map((l) => l.price);
    return [Math.min(...prices), Math.max(...prices)];
  }, [raw]);

  const homeTypes = useMemo(
    () => [...new Set(raw.map((l) => l.homeType))].sort(),
    [raw],
  );

  // Filter
  const filtered = useMemo(
    () =>
      raw.filter(
        (l) =>
          l.price >= priceRange[0] &&
          l.price <= priceRange[1] &&
          selectedTypes.includes(l.homeType),
      ),
    [raw, priceRange, selectedTypes],
  );

  // Analyze all
  const results = useMemo(() => {
    const map = new Map<string, AnalysisResult>();
    filtered.forEach((l) => map.set(l.zpid, analyze(l, params)));
    return map;
  }, [filtered, params]);

  // Sort
  const sorted = useMemo(() => {
    const arr = filtered
      .map((l) => ({ listing: l, result: results.get(l.zpid)! }))
      .filter((r) => r.result)
      .filter((r) => !hideFlagged || r.result.dataFlags.length === 0);
    arr.sort((a, b) => {
      const key = sortBy as keyof AnalysisResult;
      return (b.result[key] as number) - (a.result[key] as number);
    });
    return arr;
  }, [filtered, results, sortBy, hideFlagged]);

  // Listings to display (respects hideFlagged)
  const displayListings = useMemo(
    () => sorted.map((r) => r.listing),
    [sorted],
  );

  // Selected property
  const selectedListing = filtered.find((l) => l.zpid === selectedZpid);
  const selectedResult = selectedZpid ? results.get(selectedZpid) : undefined;

  const handleSelect = useCallback((zpid: string) => {
    setSelectedZpid(zpid);
    setTimeout(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
  }, []);

  if (!raw.length) {
    return (
      <div className="flex items-center justify-center h-screen text-[var(--color-muted)]">
        Loading properties…
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row min-h-screen">
      <Sidebar
        params={params}
        onChange={setParams}
        homeTypes={homeTypes}
        selectedTypes={selectedTypes}
        onTypesChange={setSelectedTypes}
        priceRange={priceRange}
        priceMinMax={priceMinMax}
        onPriceRangeChange={setPriceRange}
      />

      <main className="flex-1 p-6 overflow-y-auto">
        {/* Nav + Title */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-1">
            <h1 className="text-2xl font-bold">🏠 Real Estate ROI Analyzer</h1>
            <Link
              href="/history"
              className="text-sm px-3 py-1.5 rounded-md bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors"
            >
              📊 Market History →
            </Link>
          </div>
          <p className="text-sm text-[var(--color-muted)]">
            DFW Metroplex{meta.zipcodes ? ` (${meta.zipcodes.length} zipcodes)` : ""}
            {meta.scraped_at ? ` · Updated ${meta.scraped_at}` : ""}
            {" "} — {displayListings.length} properties{hideFlagged && displayListings.length < filtered.length ? ` (${filtered.length - displayListings.length} flagged hidden)` : ""} · Click markers or rows to analyze
          </p>
        </div>

        {/* Map controls + Map + Legend */}
        <div className="mb-6">
          {/* Hide flagged toggle */}
          <div className="flex items-center justify-between mb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={hideFlagged}
                onChange={(e) => setHideFlagged(e.target.checked)}
                className="accent-[var(--color-primary)]"
              />
              <span className="text-xs text-[var(--color-muted)]">Hide suspicious data properties</span>
              {hideFlagged && displayListings.length < filtered.length && (
                <span className="text-[10px] text-[var(--color-gold)]">
                  ({filtered.length - displayListings.length} hidden)
                </span>
              )}
            </label>
          </div>

          <PropertyMap
            listings={displayListings}
            results={results}
            selectedZpid={selectedZpid}
            onSelect={handleSelect}
          />

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 mt-2 text-[10px] text-[var(--color-muted)]">
            <span className="font-semibold text-xs text-[var(--color-text)]">Legend:</span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: "#06A77D" }} /> IRR ≥ 10%
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: "#F39C12" }} /> IRR 5–10%
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: "#E74C3C" }} /> IRR &lt; 5%
            </span>
            <span className="border-l border-[var(--color-border)] pl-4 flex items-center gap-1">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-muted)]" /> Small = low CF
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-4 h-4 rounded-full bg-[var(--color-muted)]" /> Large = high CF
            </span>
          </div>
        </div>

        {/* Selected property details */}
        <div ref={detailRef}>
          {selectedListing && selectedResult ? (
            <div className="mb-8">
              <PropertyDetail listing={selectedListing} result={selectedResult} params={params} />
            </div>
          ) : (
            <div className="mb-8 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-8 text-center text-[var(--color-muted)]">
              <p className="text-lg">👆 Click a marker on the map or a row in the table below to view property details</p>
            </div>
          )}
        </div>

        {/* Portfolio summary + table */}
        <PortfolioTable
          rows={sorted}
          selectedZpid={selectedZpid}
          onSelect={handleSelect}
          sortBy={sortBy}
          onSortChange={setSortBy}
        />

        {/* Footer */}
        <div className="mt-8 pt-4 border-t border-[var(--color-border)] text-center text-xs text-[var(--color-muted)]">
          {meta.zipcodes?.length ?? 1} zipcodes · {raw.length} total · {filtered.length} filtered · {results.size} analyzed
          {meta.scraped_at ? ` · Last scraped ${meta.scraped_at}` : ""}
          {" · "}
          <Link href="/history" className="underline hover:text-[var(--color-primary)]">View market history</Link>
        </div>
      </main>
    </div>
  );
}
