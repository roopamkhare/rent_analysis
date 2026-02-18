"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { analyze, type AnalysisParams, type AnalysisResult, type Listing } from "@/lib/analyze";
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
  holdingYears: 15,
  appreciationRate: 3.5,
  rentIncreaseRate: 3,
  maintenancePct: 1,
  vacancyRate: 5,
  insuranceAnnual: 1200,
  mgmtFeePct: 0,
  spGrowthRate: 10,
};

interface ListingsData {
  listings: Listing[];
}

export default function Home() {
  const [raw, setRaw] = useState<Listing[]>([]);
  const [params, setParams] = useState<AnalysisParams>(DEFAULT_PARAMS);
  const [selectedZpid, setSelectedZpid] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("monthlyCashFlow");
  const [priceRange, setPriceRange] = useState<[number, number]>([0, 10_000_000]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const detailRef = useRef<HTMLDivElement>(null);

  // Load data
  useEffect(() => {
    fetch("/listings.json")
      .then((r) => r.json())
      .then((data: ListingsData) => {
        const listings = data.listings.filter((l) => l.price > 0);
        setRaw(listings);
        const prices = listings.map((l) => l.price);
        setPriceRange([Math.min(...prices), Math.max(...prices)]);
        setSelectedTypes([...new Set(listings.map((l) => l.homeType))].sort());
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
      .filter((r) => r.result);
    arr.sort((a, b) => {
      const key = sortBy as keyof AnalysisResult;
      return (b.result[key] as number) - (a.result[key] as number);
    });
    return arr;
  }, [filtered, results, sortBy]);

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
        Loading 820 properties…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
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
        {/* Title */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold">🏠 Real Estate ROI Analyzer</h1>
          <p className="text-sm text-[var(--color-muted)]">
            McKinney, TX (75071) — {filtered.length} properties · Click markers or rows to analyze
          </p>
        </div>

        {/* Map */}
        <div className="mb-6">
          <PropertyMap
            listings={filtered}
            results={results}
            selectedZpid={selectedZpid}
            onSelect={handleSelect}
          />
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
          Data: zillow_75071_listings.json · {raw.length} total · {filtered.length} filtered · {results.size} analyzed
        </div>
      </main>
    </div>
  );
}
