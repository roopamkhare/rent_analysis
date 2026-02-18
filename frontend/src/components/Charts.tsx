"use client";

import dynamic from "next/dynamic";
import type { AnalysisResult } from "@/lib/analyze";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Props {
  result: AnalysisResult;
  holdingYears: number;
  spGrowthRate: number;
}

export default function Charts({ result: r, holdingYears, spGrowthRate }: Props) {
  const cfYears = r.annualCfs.map((_, i) => i + 1);
  const cfColors = r.annualCfs.map((v) => (v >= 0 ? "#06A77D" : "#E74C3C"));

  const eqYears = r.equityGrowth.map((e) => e.year);
  const compYears = r.propWealthSeries.map((_, i) => i);

  const plotLayout = (title: string, h: number): Partial<Plotly.Layout> => ({
    title: { text: title, font: { color: "#f1f5f9", size: 14 } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    height: h,
    margin: { l: 60, r: 20, t: 40, b: 40 },
    font: { color: "#94a3b8", size: 11 },
    xaxis: { gridcolor: "#334155", zerolinecolor: "#334155" },
    yaxis: { gridcolor: "#334155", zerolinecolor: "#334155", tickformat: "$,.0f" },
    hovermode: "x unified" as const,
    legend: { orientation: "h" as const, y: -0.2, font: { color: "#94a3b8" } },
  });

  return (
    <div className="space-y-6">
      {/* Annual Cash Flow Bar Chart */}
      <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
        <Plot
          data={[{
            type: "bar", x: cfYears, y: r.annualCfs, marker: { color: cfColors },
            hovertemplate: "Year %{x}: $%{y:,.0f}<extra></extra>",
          }]}
          layout={plotLayout("📊 Annual Operating Cash Flow", 280)}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
        />
      </div>

      {/* Equity Growth */}
      <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
        <Plot
          data={[
            { type: "scatter", mode: "lines", x: eqYears, y: r.equityGrowth.map((e) => e.propertyValue), name: "Property Value", line: { color: "#2E86AB", width: 2 } },
            { type: "scatter", mode: "lines", x: eqYears, y: r.equityGrowth.map((e) => e.remainingMortgage), name: "Mortgage Balance", line: { color: "#A23B72", width: 2 } },
            { type: "scatter", mode: "lines", x: eqYears, y: r.equityGrowth.map((e) => e.equity), name: "Equity", fill: "tonexty", line: { color: "#06A77D", width: 2 } },
          ]}
          layout={plotLayout(`📈 Equity Growth Over ${holdingYears} Years`, 340)}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
        />
      </div>

      {/* Property vs S&P */}
      <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
        <p className="text-xs text-[var(--color-muted)] mb-2">
          Both paths deploy the same out-of-pocket cash. Lines show liquidation value at each year.
        </p>
        <Plot
          data={[
            { type: "scatter", mode: "lines", x: compYears, y: r.propWealthSeries, name: "Property (if sold today)", line: { color: "#2E86AB", width: 3 }, hovertemplate: "Year %{x}: $%{y:,.0f}<extra></extra>" },
            { type: "scatter", mode: "lines", x: compYears, y: r.spPortfolioSeries, name: `S&P Portfolio (${spGrowthRate}%/yr)`, line: { color: "#F39C12", width: 3 }, hovertemplate: "Year %{x}: $%{y:,.0f}<extra></extra>" },
            { type: "scatter", mode: "lines", x: compYears, y: r.spDeployedSeries, name: "Total Cash Deployed", line: { color: "grey", width: 2, dash: "dot" }, hovertemplate: "Year %{x}: $%{y:,.0f}<extra></extra>" },
          ]}
          layout={plotLayout("⚖️ Property vs S&P 500", 380)}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
        />

        {/* Winner summary */}
        <div className="grid grid-cols-4 gap-3 mt-4">
          <MetricBox label="Property Final" value={`$${r.propWealthSeries[r.propWealthSeries.length - 1].toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
            sub={`Profit $${r.totalProfit.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} />
          <MetricBox label="S&P Final" value={`$${r.spPortfolioSeries[r.spPortfolioSeries.length - 1].toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
            sub={`Profit $${r.spProfit.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} />
          <MetricBox label="Deployed" value={`$${r.spDeployed.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} />
          <MetricBox label="Winner"
            value={r.totalProfit > r.spProfit ? "🏠 Property" : "📈 S&P 500"}
            sub={`by $${Math.abs(r.totalProfit - r.spProfit).toLocaleString("en-US", { maximumFractionDigits: 0 })}`} />
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-[var(--color-bg)] rounded-lg p-3 text-center">
      <div className="text-xs text-[var(--color-muted)]">{label}</div>
      <div className="text-sm font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-[var(--color-muted)] mt-0.5">{sub}</div>}
    </div>
  );
}
