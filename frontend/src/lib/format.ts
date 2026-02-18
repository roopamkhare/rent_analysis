/** Dollar / percent formatters */

export const fmtDollar = (v: number) =>
  "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

export const fmtPct = (v: number) => v.toFixed(2) + "%";

export const fmtInt = (v: number | null | undefined) =>
  v != null ? Math.round(v).toString() : "–";
