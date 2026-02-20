"use client";

import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

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

interface Props {
  snapshots: Snapshot[];
  properties: Record<string, PropertyEntry[]>;
}

const plotLayout = (title: string, h: number, yFormat = "$,.0f"): Partial<Plotly.Layout> => ({
  title: { text: title, font: { color: "#f1f5f9", size: 14 } },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  height: h,
  margin: { l: 65, r: 20, t: 50, b: 50 },
  font: { color: "#94a3b8", size: 11 },
  xaxis: { gridcolor: "#334155", zerolinecolor: "#334155", type: "date" as const },
  yaxis: { gridcolor: "#334155", zerolinecolor: "#334155", tickformat: yFormat },
  hovermode: "x unified" as const,
  legend: { orientation: "h" as const, y: -0.15, font: { color: "#94a3b8" } },
});

export default function HistoryCharts({ snapshots, properties }: Props) {
  const dates = snapshots.map((s) => s.date);

  // ── Price drops ──────────────────────────────────────────────
  const priceDrops: {
    zpid: string;
    address: string;
    zipcode: string;
    prevPrice: number;
    currPrice: number;
    drop: number;
    dropPct: number;
    date: string;
  }[] = [];

  Object.entries(properties).forEach(([zpid, entries]) => {
    if (entries.length < 2) return;
    const curr = entries[entries.length - 1];
    const prev = entries[entries.length - 2];
    if (curr.price < prev.price) {
      const drop = prev.price - curr.price;
      priceDrops.push({
        zpid,
        address: curr.address,
        zipcode: curr.zipcode,
        prevPrice: prev.price,
        currPrice: curr.price,
        drop,
        dropPct: (drop / prev.price) * 100,
        date: curr.date,
      });
    }
  });
  priceDrops.sort((a, b) => b.dropPct - a.dropPct);

  // ── Per-zipcode trend (pick top 6 zips by latest count) ─────
  const latestSnap = snapshots[snapshots.length - 1];
  const topZips = latestSnap
    ? Object.entries(latestSnap.byZipcode)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 6)
        .map(([z]) => z)
    : [];

  const zipColors = ["#2E86AB", "#06A77D", "#F39C12", "#E74C3C", "#A23B72", "#7C3AED"];

  const onlyOne = snapshots.length <= 1;

  return (
    <div className="space-y-6">
      {/* Market Overview Cards */}
      {latestSnap && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: "Total Listings", value: latestSnap.totalListings.toLocaleString() },
            { label: "Median Price", value: `$${latestSnap.medianPrice.toLocaleString()}` },
            { label: "Median Rent", value: `$${latestSnap.medianRent.toLocaleString()}/mo` },
            { label: "Avg $/sqft", value: `$${latestSnap.avgPricePerSqFt}` },
            { label: "Price Drops", value: priceDrops.length.toString(), highlight: priceDrops.length > 0 },
          ].map((card) => (
            <div
              key={card.label}
              className={`bg-[var(--color-surface)] rounded-lg p-4 border ${
                card.highlight ? "border-[var(--color-red)]" : "border-[var(--color-border)]"
              }`}
            >
              <p className="text-xs text-[var(--color-muted)]">{card.label}</p>
              <p className={`text-xl font-bold ${card.highlight ? "text-[var(--color-red)]" : ""}`}>{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {onlyOne && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-gold)] rounded-lg p-6 text-center">
          <p className="text-[var(--color-gold)] font-semibold mb-1">📅 Only 1 snapshot so far</p>
          <p className="text-sm text-[var(--color-muted)]">
            Trend charts will populate as more weekly scrapes run. The automated GitHub Action runs every Sunday.
          </p>
        </div>
      )}

      {/* Median Price & Rent Trends */}
      {!onlyOne && (
        <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <Plot
            data={[
              {
                type: "scatter", mode: "lines+markers", x: dates,
                y: snapshots.map((s) => s.medianPrice),
                name: "Median Price", line: { color: "#2E86AB", width: 3 },
                yaxis: "y",
                hovertemplate: "%{x}: $%{y:,.0f}<extra>Price</extra>",
              },
              {
                type: "scatter", mode: "lines+markers", x: dates,
                y: snapshots.map((s) => s.medianRent),
                name: "Median Rent", line: { color: "#06A77D", width: 3 },
                yaxis: "y2",
                hovertemplate: "%{x}: $%{y:,.0f}/mo<extra>Rent</extra>",
              },
            ]}
            layout={{
              ...plotLayout("📈 Median Price & Rent Trends", 360),
              yaxis: { gridcolor: "#334155", zerolinecolor: "#334155", tickformat: "$,.0f", title: { text: "Price", font: { color: "#2E86AB" } } },
              yaxis2: { overlaying: "y" as const, side: "right" as const, tickformat: "$,.0f", title: { text: "Rent/mo", font: { color: "#06A77D" } }, gridcolor: "transparent" },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Listing Count Trend */}
      {!onlyOne && (
        <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <Plot
            data={[{
              type: "bar", x: dates, y: snapshots.map((s) => s.totalListings),
              marker: { color: "#2E86AB" },
              hovertemplate: "%{x}: %{y:,} listings<extra></extra>",
            }]}
            layout={plotLayout("🏘️ Active Listings Over Time", 280, ",.0f")}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Price per Sqft Trend */}
      {!onlyOne && (
        <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <Plot
            data={[{
              type: "scatter", mode: "lines+markers", x: dates,
              y: snapshots.map((s) => s.avgPricePerSqFt),
              line: { color: "#F39C12", width: 3 },
              marker: { size: 8 },
              hovertemplate: "%{x}: $%{y:.0f}/sqft<extra></extra>",
            }]}
            layout={plotLayout("📐 Average Price per Sq Ft", 280)}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Per-Zipcode Comparison */}
      {!onlyOne && topZips.length > 1 && (
        <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <Plot
            data={topZips.map((zip, i) => ({
              type: "scatter" as const, mode: "lines+markers" as const,
              x: dates,
              y: snapshots.map((s) => s.byZipcode[zip]?.medianPrice ?? null),
              name: zip,
              line: { color: zipColors[i % zipColors.length], width: 2 },
              connectgaps: true,
              hovertemplate: `${zip}: $%{y:,.0f}<extra></extra>`,
            }))}
            layout={plotLayout("🗺️ Median Price by Zipcode (Top 6)", 360)}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Zipcode Summary Table */}
      {latestSnap && Object.keys(latestSnap.byZipcode).length > 0 && (
        <div className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] overflow-hidden">
          <h3 className="px-4 py-3 text-sm font-semibold border-b border-[var(--color-border)]">
            📊 Zipcode Breakdown ({Object.keys(latestSnap.byZipcode).length} zipcodes)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                  <th className="text-left px-4 py-2">Zipcode</th>
                  <th className="text-right px-4 py-2">Listings</th>
                  <th className="text-right px-4 py-2">Median Price</th>
                  <th className="text-right px-4 py-2">Median Rent</th>
                  <th className="text-right px-4 py-2">Rent Yield</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(latestSnap.byZipcode)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([zip, data]) => {
                    const rentYield = data.medianPrice > 0 && data.medianRent > 0
                      ? ((data.medianRent * 12) / data.medianPrice) * 100
                      : 0;
                    return (
                      <tr key={zip} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]">
                        <td className="px-4 py-2 font-mono">{zip}</td>
                        <td className="text-right px-4 py-2">{data.count}</td>
                        <td className="text-right px-4 py-2">${data.medianPrice.toLocaleString()}</td>
                        <td className="text-right px-4 py-2">${data.medianRent.toLocaleString()}/mo</td>
                        <td className={`text-right px-4 py-2 font-semibold ${rentYield >= 6 ? "text-[var(--color-green)]" : rentYield >= 4 ? "text-[var(--color-gold)]" : "text-[var(--color-red)]"}`}>
                          {rentYield > 0 ? `${rentYield.toFixed(1)}%` : "–"}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Home Type Breakdown */}
      {latestSnap && Object.keys(latestSnap.byHomeType).length > 0 && (
        <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
          <Plot
            data={[{
              type: "pie",
              labels: Object.keys(latestSnap.byHomeType),
              values: Object.values(latestSnap.byHomeType),
              textinfo: "label+percent",
              hovertemplate: "%{label}: %{value} listings (%{percent})<extra></extra>",
              marker: { colors: ["#2E86AB", "#06A77D", "#F39C12", "#E74C3C", "#A23B72", "#7C3AED", "#94a3b8"] },
            }]}
            layout={{
              ...plotLayout("🏠 Property Types", 300),
              showlegend: false,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Price Drops Table */}
      <div className="bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] overflow-hidden">
        <h3 className="px-4 py-3 text-sm font-semibold border-b border-[var(--color-border)]">
          🔻 Price Drops ({priceDrops.length} properties)
        </h3>
        {priceDrops.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-[var(--color-muted)]">
            No price drops detected yet. Check back after the next weekly scrape.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                  <th className="text-left px-4 py-2">Address</th>
                  <th className="text-left px-4 py-2">Zip</th>
                  <th className="text-right px-4 py-2">Previous</th>
                  <th className="text-right px-4 py-2">Current</th>
                  <th className="text-right px-4 py-2">Drop</th>
                  <th className="text-right px-4 py-2">%</th>
                </tr>
              </thead>
              <tbody>
                {priceDrops.slice(0, 50).map((d) => (
                  <tr key={d.zpid} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]">
                    <td className="px-4 py-2 max-w-[200px] truncate">{d.address || d.zpid}</td>
                    <td className="px-4 py-2 font-mono">{d.zipcode}</td>
                    <td className="text-right px-4 py-2">${d.prevPrice.toLocaleString()}</td>
                    <td className="text-right px-4 py-2">${d.currPrice.toLocaleString()}</td>
                    <td className="text-right px-4 py-2 text-[var(--color-red)] font-semibold">
                      -${d.drop.toLocaleString()}
                    </td>
                    <td className="text-right px-4 py-2 text-[var(--color-red)]">
                      -{d.dropPct.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
