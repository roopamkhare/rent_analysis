"use client";

import { useState } from "react";
import { AnalysisParams } from "@/lib/analyze";

/* ── Tooltip helper (uses native title — never clipped by overflow) ── */
function Tip({ text }: { text: string }) {
  return (
    <span className="ml-1 cursor-help text-[10px] text-[var(--color-primary)] opacity-70 hover:opacity-100" title={text}>
      ⓘ
    </span>
  );
}

interface Props {
  params: AnalysisParams;
  onChange: (p: AnalysisParams) => void;
  homeTypes: string[];
  selectedTypes: string[];
  onTypesChange: (t: string[]) => void;
  priceRange: [number, number];
  priceMinMax: [number, number];
  onPriceRangeChange: (r: [number, number]) => void;
  hideFlagged: boolean;
  onHideFlaggedChange: (v: boolean) => void;
}

function Slider({
  label, value, min, max, step, unit, onChange, tip,
}: {
  label: string; value: number; min: number; max: number;
  step: number; unit: string; onChange: (v: number) => void;
  tip?: string;
}) {
  return (
    <label className="block mb-3">
      <span className="text-xs text-[var(--color-muted)] flex justify-between">
        <span>{label}{tip && <Tip text={tip} />}</span>
        <span className="text-[var(--color-text)] font-medium">
          {unit === "$" ? `$${value.toLocaleString()}` : `${value}${unit}`}
        </span>
      </span>
      <input
        type="range"
        className="w-full mt-1 accent-[var(--color-primary)]"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export default function Sidebar({
  params: p, onChange,
  homeTypes, selectedTypes, onTypesChange,
  priceRange, priceMinMax, onPriceRangeChange,
  hideFlagged, onHideFlaggedChange,
}: Props) {
  const set = (patch: Partial<AnalysisParams>) => onChange({ ...p, ...patch });
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="md:hidden fixed top-3 left-3 z-50 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm font-medium shadow-lg"
      >
        {open ? "✕ Close" : "⚙️ Params"}
      </button>
      {open && <div className="md:hidden fixed inset-0 bg-black/40 z-30" onClick={() => setOpen(false)} />}

      <aside className={`fixed md:sticky top-0 left-0 z-40 w-72 shrink-0 bg-[var(--color-surface)] border-r border-[var(--color-border)] p-4 overflow-y-auto h-screen transition-transform duration-200 ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}>
        <h2 className="text-lg font-bold mb-1 mt-8 md:mt-0">📊 Parameters</h2>
        <p className="text-[10px] text-[var(--color-muted)] mb-4">Adjust assumptions below. Hover ⓘ for explanations.</p>

      <Section title="🏦 Loan">
        <Slider label="Interest Rate" value={p.interestRate} min={2} max={10} step={0.25} unit="%" tip="Annual mortgage interest rate. Check current 30yr fixed rates at bankrate.com." onChange={(v) => set({ interestRate: v })} />
        <label className="block mb-3">
          <span className="text-xs text-[var(--color-muted)]">Loan Term <Tip text="Shorter terms have higher payments but less total interest paid." /></span>
          <select className="w-full mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-2 py-1 text-sm"
            value={p.loanTerm} onChange={(e) => set({ loanTerm: Number(e.target.value) })}>
            {[15, 20, 30].map((y) => <option key={y} value={y}>{y} years</option>)}
          </select>
        </label>
        <Slider label="Down Payment" value={p.downPaymentPct} min={5} max={50} step={5} unit="%" tip="% of price paid upfront. Below 20% typically requires PMI." onChange={(v) => set({ downPaymentPct: v })} />
      </Section>

      <Section title="💸 Transaction">
        <Slider label="Buy Closing Costs" value={p.closingCostsPct} min={1} max={5} step={0.5} unit="%" tip="Title, appraisal, origination fees. Typically 2-3%." onChange={(v) => set({ closingCostsPct: v })} />
        <Slider label="Sell Closing Costs" value={p.sellingCostsPct} min={1} max={10} step={0.5} unit="%" tip="Agent commission + title + transfer taxes. Typically 5-6%." onChange={(v) => set({ sellingCostsPct: v })} />
      </Section>

      <Section title="⏳ Holding">
        <label className="block mb-3">
          <span className="text-xs text-[var(--color-muted)]">Years Until Sale <Tip text="Longer hold = more equity + appreciation. Short holds often lose money due to transaction costs." /></span>
          <select className="w-full mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-2 py-1 text-sm"
            value={p.holdingYears} onChange={(e) => set({ holdingYears: Number(e.target.value) })}>
            {[3, 5, 7, 10, 15, 20, 30].map((y) => <option key={y} value={y}>{y} years</option>)}
          </select>
        </label>
      </Section>

      <Section title="🏘️ Rent Estimate">
        <Slider label="Rent % of Price (mo)" value={p.rentEstimatePct} min={0.2} max={1.5} step={0.01} unit="%" tip="Monthly rent as % of price. Used when Zillow has no rent estimate. Auto-set to data median on load." onChange={(v) => set({ rentEstimatePct: v })} />
      </Section>

      <Section title="📈 Growth">
        <Slider label="Appreciation" value={p.appreciationRate} min={0} max={10} step={0.5} unit="%/yr" tip="Annual value growth. US avg ~3.5%. DFW has been 4-6% recently." onChange={(v) => set({ appreciationRate: v })} />
        <Slider label="Rent Increase" value={p.rentIncreaseRate} min={0} max={10} step={0.5} unit="%/yr" tip="Annual rent growth. Typically tracks inflation at 2-3%." onChange={(v) => set({ rentIncreaseRate: v })} />
        <Slider label="S&P 500 Return" value={p.spGrowthRate} min={0} max={30} step={0.5} unit="%/yr" tip="What if you put the same money in stocks instead? S&P historical avg ~10%/yr." onChange={(v) => set({ spGrowthRate: v })} />
      </Section>

      <Section title="🔧 Operating">
        <Slider label="Maintenance" value={p.maintenancePct} min={0.5} max={3} step={0.25} unit="%" tip="Annual maintenance as % of value. 1% for newer, 2%+ for older homes." onChange={(v) => set({ maintenancePct: v })} />
        <Slider label="Vacancy" value={p.vacancyRate} min={0} max={15} step={1} unit="%" tip="% of time empty. 5% ≈ 2-3 weeks/year. DFW avg ~5-7%." onChange={(v) => set({ vacancyRate: v })} />
        <Slider label="Mgmt Fee" value={p.mgmtFeePct} min={0} max={12} step={1} unit="%" tip="PM fee as % of rent. 0% if self-managed, 8-10% for a PM company." onChange={(v) => set({ mgmtFeePct: v })} />
        <Slider label="Insurance" value={p.insuranceAnnual} min={500} max={5000} step={100} unit="$" tip="Annual homeowners insurance. Varies by location, size, and age." onChange={(v) => set({ insuranceAnnual: v })} />
      </Section>

      <Section title="🔍 Filters">
        <label className="block mb-2">
          <span className="text-xs text-[var(--color-muted)] flex justify-between">
            <span>Price Min</span><span>${priceRange[0].toLocaleString()}</span>
          </span>
          <input type="range" className="w-full mt-1 accent-[var(--color-primary)]"
            min={priceMinMax[0]} max={priceMinMax[1]} step={10000} value={priceRange[0]}
            onChange={(e) => onPriceRangeChange([Number(e.target.value), priceRange[1]])} />
        </label>
        <label className="block mb-3">
          <span className="text-xs text-[var(--color-muted)] flex justify-between">
            <span>Price Max</span><span>${priceRange[1].toLocaleString()}</span>
          </span>
          <input type="range" className="w-full mt-1 accent-[var(--color-primary)]"
            min={priceMinMax[0]} max={priceMinMax[1]} step={10000} value={priceRange[1]}
            onChange={(e) => onPriceRangeChange([priceRange[0], Number(e.target.value)])} />
        </label>

        <span className="text-xs text-[var(--color-muted)] block mb-1">Home Type</span>
        <div className="flex flex-wrap gap-1 mb-3">
          {homeTypes.map((t) => (
            <button key={t}
              className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                selectedTypes.includes(t)
                  ? "bg-[var(--color-primary)] border-[var(--color-primary)] text-white"
                  : "border-[var(--color-border)] text-[var(--color-muted)] hover:border-[var(--color-primary)]"
              }`}
              onClick={() => {
                const next = selectedTypes.includes(t)
                  ? selectedTypes.filter((x) => x !== t)
                  : [...selectedTypes, t];
                onTypesChange(next.length ? next : homeTypes);
              }}>
              {t.replace("_", " ")}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 cursor-pointer mb-1">
          <input
            type="checkbox"
            checked={hideFlagged}
            onChange={(e) => onHideFlaggedChange(e.target.checked)}
            className="accent-[var(--color-primary)]"
          />
          <span className="text-xs text-[var(--color-muted)]">Hide flagged properties <Tip text="Remove listings with suspicious data (missing rent, extreme ratios) from map and table." /></span>
        </label>
      </Section>
      </aside>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-sm font-semibold mb-2 text-[var(--color-primary)]">{title}</h3>
      {children}
    </div>
  );
}
