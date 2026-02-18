"use client";

import { AnalysisParams } from "@/lib/analyze";

interface Props {
  params: AnalysisParams;
  onChange: (p: AnalysisParams) => void;
  homeTypes: string[];
  selectedTypes: string[];
  onTypesChange: (t: string[]) => void;
  priceRange: [number, number];
  priceMinMax: [number, number];
  onPriceRangeChange: (r: [number, number]) => void;
}

function Slider({
  label, value, min, max, step, unit, onChange,
}: {
  label: string; value: number; min: number; max: number;
  step: number; unit: string; onChange: (v: number) => void;
}) {
  return (
    <label className="block mb-3">
      <span className="text-xs text-[var(--color-muted)] flex justify-between">
        <span>{label}</span>
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
}: Props) {
  const set = (patch: Partial<AnalysisParams>) => onChange({ ...p, ...patch });

  return (
    <aside className="w-72 shrink-0 bg-[var(--color-surface)] border-r border-[var(--color-border)] p-4 overflow-y-auto h-screen sticky top-0">
      <h2 className="text-lg font-bold mb-4">📊 Parameters</h2>

      <Section title="🏦 Loan">
        <Slider label="Interest Rate" value={p.interestRate} min={2} max={10} step={0.25} unit="%" onChange={(v) => set({ interestRate: v })} />
        <label className="block mb-3">
          <span className="text-xs text-[var(--color-muted)]">Loan Term</span>
          <select className="w-full mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-2 py-1 text-sm"
            value={p.loanTerm} onChange={(e) => set({ loanTerm: Number(e.target.value) })}>
            {[15, 20, 30].map((y) => <option key={y} value={y}>{y} years</option>)}
          </select>
        </label>
        <Slider label="Down Payment" value={p.downPaymentPct} min={5} max={50} step={5} unit="%" onChange={(v) => set({ downPaymentPct: v })} />
      </Section>

      <Section title="💸 Transaction">
        <Slider label="Buy Closing Costs" value={p.closingCostsPct} min={1} max={5} step={0.5} unit="%" onChange={(v) => set({ closingCostsPct: v })} />
        <Slider label="Sell Closing Costs" value={p.sellingCostsPct} min={1} max={10} step={0.5} unit="%" onChange={(v) => set({ sellingCostsPct: v })} />
      </Section>

      <Section title="⏳ Holding">
        <label className="block mb-3">
          <span className="text-xs text-[var(--color-muted)]">Years Until Sale</span>
          <select className="w-full mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-2 py-1 text-sm"
            value={p.holdingYears} onChange={(e) => set({ holdingYears: Number(e.target.value) })}>
            {[3, 5, 7, 10, 15, 20, 30].map((y) => <option key={y} value={y}>{y} years</option>)}
          </select>
        </label>
      </Section>

      <Section title="📈 Growth">
        <Slider label="Appreciation" value={p.appreciationRate} min={0} max={10} step={0.5} unit="%/yr" onChange={(v) => set({ appreciationRate: v })} />
        <Slider label="Rent Increase" value={p.rentIncreaseRate} min={0} max={10} step={0.5} unit="%/yr" onChange={(v) => set({ rentIncreaseRate: v })} />
        <Slider label="S&P 500 Return" value={p.spGrowthRate} min={0} max={30} step={0.5} unit="%/yr" onChange={(v) => set({ spGrowthRate: v })} />
      </Section>

      <Section title="🔧 Operating">
        <Slider label="Maintenance" value={p.maintenancePct} min={0.5} max={3} step={0.25} unit="%" onChange={(v) => set({ maintenancePct: v })} />
        <Slider label="Vacancy" value={p.vacancyRate} min={0} max={15} step={1} unit="%" onChange={(v) => set({ vacancyRate: v })} />
        <Slider label="Mgmt Fee" value={p.mgmtFeePct} min={0} max={12} step={1} unit="%" onChange={(v) => set({ mgmtFeePct: v })} />
        <Slider label="Insurance" value={p.insuranceAnnual} min={500} max={5000} step={100} unit="$" onChange={(v) => set({ insuranceAnnual: v })} />
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
      </Section>
    </aside>
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
