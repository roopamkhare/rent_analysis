"use client";

import type { AnalysisResult, Listing } from "@/lib/analyze";
import { fmtDollar, fmtPct, fmtInt } from "@/lib/format";

interface Row {
  listing: Listing;
  result: AnalysisResult;
}

interface Props {
  rows: Row[];
  selectedZpid: string | null;
  onSelect: (zpid: string) => void;
  sortBy: string;
  onSortChange: (s: string) => void;
}

const SORT_OPTIONS = [
  { label: "Monthly CF", key: "monthlyCashFlow" },
  { label: "Cap Rate", key: "capRate" },
  { label: "IRR", key: "irr" },
  { label: "Cash-on-Cash", key: "cashOnCash" },
  { label: "Total Profit", key: "totalProfit" },
  { label: "Annualized ROI", key: "annualizedRoi" },
];

export default function PortfolioTable({ rows, selectedZpid, onSelect, sortBy, onSortChange }: Props) {
  // portfolio summary
  const count = rows.length;
  const avgIrr = count ? rows.reduce((s, r) => s + r.result.irr, 0) / count : 0;
  const avgCf = count ? rows.reduce((s, r) => s + r.result.monthlyCashFlow, 0) / count : 0;
  const posCf = rows.filter((r) => r.result.monthlyCashFlow > 0).length;
  const avgCoc = count ? rows.reduce((s, r) => s + r.result.cashOnCash, 0) / count : 0;

  return (
    <div className="space-y-4">
      {/* Summary metrics */}
      <div className="grid grid-cols-5 gap-3">
        <SummaryCard label="Properties" value={count.toString()} />
        <SummaryCard label="Avg IRR" value={fmtPct(avgIrr)} />
        <SummaryCard label="Avg Monthly CF" value={fmtDollar(avgCf)} />
        <SummaryCard label="Cash-Flow +ve" value={`${posCf} (${count ? Math.round((posCf / count) * 100) : 0}%)`} />
        <SummaryCard label="Avg Cash-on-Cash" value={fmtPct(avgCoc)} />
      </div>

      {/* Sort control */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-[var(--color-muted)]">Sort by:</span>
        <select
          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded px-3 py-1.5 text-sm"
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--color-surface)] text-[var(--color-muted)] text-xs">
              <th className="text-left px-3 py-2">#</th>
              <th className="text-left px-3 py-2">Address</th>
              <th className="text-right px-3 py-2">Price</th>
              <th className="text-right px-3 py-2">Rent/mo</th>
              <th className="text-center px-3 py-2">Bed</th>
              <th className="text-center px-3 py-2">Bath</th>
              <th className="text-right px-3 py-2">Sqft</th>
              <th className="text-right px-3 py-2">Monthly CF</th>
              <th className="text-right px-3 py-2">Cap Rate</th>
              <th className="text-right px-3 py-2">CoC</th>
              <th className="text-right px-3 py-2">IRR</th>
              <th className="text-center px-3 py-2">Zillow</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ listing: l, result: r }, i) => {
              const isSelected = l.zpid === selectedZpid;
              const zillow = l.detailUrl || `https://www.zillow.com/homedetails/${l.streetAddress.replace(/ /g, "-")}/${l.zpid}_zpid/`;
              return (
                <tr
                  key={l.zpid}
                  className={`border-t border-[var(--color-border)] cursor-pointer transition-colors
                    ${isSelected ? "bg-[var(--color-primary)]/15" : "hover:bg-[var(--color-surface)]"}`}
                  onClick={() => onSelect(l.zpid)}
                >
                  <td className="px-3 py-2 text-[var(--color-muted)]">{i + 1}</td>
                  <td className="px-3 py-2 font-medium max-w-[260px] truncate">{l.streetAddress}</td>
                  <td className="px-3 py-2 text-right">{fmtDollar(l.price)}</td>
                  <td className="px-3 py-2 text-right">{fmtDollar(l.rentZestimate ?? l.price * 0.008)}</td>
                  <td className="px-3 py-2 text-center">{fmtInt(l.bedrooms)}</td>
                  <td className="px-3 py-2 text-center">{l.bathrooms?.toFixed(1) ?? "–"}</td>
                  <td className="px-3 py-2 text-right">{l.livingArea ? l.livingArea.toLocaleString() : "–"}</td>
                  <td className={`px-3 py-2 text-right font-medium ${r.monthlyCashFlow >= 0 ? "text-[var(--color-green)]" : "text-[var(--color-red)]"}`}>
                    {fmtDollar(r.monthlyCashFlow)}
                  </td>
                  <td className="px-3 py-2 text-right">{fmtPct(r.capRate)}</td>
                  <td className="px-3 py-2 text-right">{fmtPct(r.cashOnCash)}</td>
                  <td className="px-3 py-2 text-right">{fmtPct(r.irr)}</td>
                  <td className="px-3 py-2 text-center">
                    <a href={zillow} target="_blank" rel="noopener noreferrer"
                      className="text-[var(--color-primary)] hover:underline"
                      onClick={(e) => e.stopPropagation()}>
                      Open
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--color-surface)] rounded-lg p-3 text-center border border-[var(--color-border)]">
      <div className="text-xs text-[var(--color-muted)]">{label}</div>
      <div className="text-lg font-bold mt-1">{value}</div>
    </div>
  );
}
