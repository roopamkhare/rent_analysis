"use client";

import type { AnalysisResult, Listing, AnalysisParams, DataFlag } from "@/lib/analyze";
import { fmtDollar, fmtPct } from "@/lib/format";
import Charts from "./Charts";

interface Props {
  listing: Listing;
  result: AnalysisResult;
  params: AnalysisParams;
}

export default function PropertyDetail({ listing: l, result: r, params: p }: Props) {
  const zillow = l.detailUrl || `https://www.zillow.com/homedetails/${l.streetAddress.replace(/ /g, "-")}/${l.zpid}_zpid/`;
  const cfIcon = r.monthlyCashFlow >= 0 ? "🟢" : "🔴";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">📍 {l.addressRaw}</h2>
          <p className="text-sm text-[var(--color-muted)]">
            {l.homeType.replace("_", " ")} · {l.bedrooms} bed · {l.bathrooms} bath
            {l.livingArea ? ` · ${l.livingArea.toLocaleString()} sqft` : ""}
          </p>
        </div>
        <a href={zillow} target="_blank" rel="noopener noreferrer"
          className="shrink-0 bg-[var(--color-primary)] text-white text-sm px-4 py-2 rounded-lg hover:opacity-90 transition-opacity">
          View on Zillow ↗
        </a>
      </div>

      {/* Data quality flags */}
      {r.dataFlags.length > 0 && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-gold)] rounded-lg p-3">
          <p className="text-xs font-semibold text-[var(--color-gold)] mb-1.5">⚠️ Data Quality Flags</p>
          <div className="flex flex-wrap gap-2">
            {r.dataFlags.map((f) => (
              <span
                key={f.code}
                className={`text-xs px-2 py-1 rounded-full ${
                  f.severity === "error"
                    ? "bg-[var(--color-red)]/20 text-[var(--color-red)]"
                    : "bg-[var(--color-gold)]/20 text-[var(--color-gold)]"
                }`}
              >
                {f.severity === "error" ? "🔴" : "🟡"} {f.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Key metrics */}
      <div className="grid grid-cols-5 gap-3">
        <Metric label="Monthly CF" value={`${cfIcon} ${fmtDollar(r.monthlyCashFlow)}`} />
        <Metric label="Cap Rate" value={fmtPct(r.capRate)} />
        <Metric label="Cash-on-Cash" value={fmtPct(r.cashOnCash)} />
        <Metric label="IRR" value={fmtPct(r.irr)} />
        <Metric label={`Profit (${p.holdingYears}yr)`} value={fmtDollar(r.totalProfit)} />
      </div>

      {/* Financial breakdown */}
      <div className="grid grid-cols-3 gap-4">
        <Card title="Purchase">
          <Row label="Price" value={fmtDollar(l.price)} />
          <Row label={`Down (${p.downPaymentPct}%)`} value={fmtDollar(r.downPayment)} />
          <Row label={`Buy Closing (${p.closingCostsPct}%)`} value={fmtDollar(r.buyClosing)} />
          <Row label="Total Out-of-Pocket" value={fmtDollar(r.initialInvestment)} bold />
        </Card>

        <Card title="Monthly (Year 1)">
          <Row label="Gross Rent" value={fmtDollar(l.rentZestimate ?? l.price * 0.008)} />
          <Row label={`Eff. Rent (−${p.vacancyRate}% vac)`} value={fmtDollar(r.effectiveMonthlyRent)} />
          <Row label={`Mortgage (${p.loanTerm}yr @ ${p.interestRate}%)`} value={fmtDollar(r.monthlyEmi)} />
          <Row label="All Expenses" value={fmtDollar(r.totalMonthlyExpenses)} />
          <Row label="Cash Flow" value={`${cfIcon} ${fmtDollar(r.monthlyCashFlow)}/mo`} bold />
        </Card>

        <Card title={`Sale (Year ${p.holdingYears})`}>
          <Row label="Future Value" value={fmtDollar(r.futurePropertyValue)} />
          <Row label="− Bank Owed" value={fmtDollar(r.remainingMortgage)} />
          <Row label={`− Sell Closing (${p.sellingCostsPct}%)`} value={fmtDollar(r.sellClosing)} />
          <Row label="= Net Proceeds" value={fmtDollar(r.netSaleProceeds)} bold />
        </Card>
      </div>

      {/* Charts */}
      <Charts result={r} holdingYears={p.holdingYears} spGrowthRate={p.spGrowthRate} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--color-surface)] rounded-lg p-3 text-center border border-[var(--color-border)]">
      <div className="text-xs text-[var(--color-muted)]">{label}</div>
      <div className="text-base font-bold mt-1">{value}</div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
      <h3 className="text-sm font-semibold mb-3 text-[var(--color-primary)]">{title}</h3>
      <div className="space-y-1.5 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "font-bold pt-1 border-t border-[var(--color-border)]" : ""}`}>
      <span className="text-[var(--color-muted)]">{label}</span>
      <span>{value}</span>
    </div>
  );
}
