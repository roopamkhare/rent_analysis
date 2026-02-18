/* ──────────────────────────────────────────────────────────────
   Financial analysis engine — a faithful JS port of the Python
   `analyze()`, `calc_emi()`, `calc_remaining()` from
   rental_roi_app.py.
   ────────────────────────────────────────────────────────────── */

export interface Listing {
  zpid: string;
  price: number;
  zestimate: number | null;
  imgSrc: string;
  detailUrl: string;
  statusText: string;
  addressRaw: string;
  streetAddress: string;
  city: string;
  state: string;
  zipcode: string;
  rentZestimate: number | null;
  taxAssessedValue: number | null;
  bedrooms: number;
  bathrooms: number;
  livingArea: number | null;
  lotAreaValue: number | null;
  homeType: string;
  homeStatus: string;
  daysOnZillow: number;
  latitude: number;
  longitude: number;
  monthlyHoaFee?: number;
  propertyTaxRate?: number;
}

export interface AnalysisParams {
  interestRate: number;      // %
  loanTerm: number;          // years
  downPaymentPct: number;    // %
  closingCostsPct: number;   // buy %
  sellingCostsPct: number;   // sell %
  holdingYears: number;
  appreciationRate: number;  // %/yr
  rentIncreaseRate: number;  // %/yr
  maintenancePct: number;    // % of value/yr
  vacancyRate: number;       // %
  insuranceAnnual: number;   // $
  mgmtFeePct: number;        // % of rent
  spGrowthRate: number;      // %/yr
}

export interface EquityPoint {
  year: number;
  propertyValue: number;
  remainingMortgage: number;
  equity: number;
}

export interface AnalysisResult {
  // upfront
  initialInvestment: number;
  downPayment: number;
  buyClosing: number;
  loanAmount: number;
  // year-1 snapshot
  monthlyEmi: number;
  monthlyCashFlow: number;
  annualCashFlow: number;
  totalMonthlyExpenses: number;
  effectiveMonthlyRent: number;
  capRate: number;
  cashOnCash: number;
  // exit
  futurePropertyValue: number;
  remainingMortgage: number;
  sellClosing: number;
  netSaleProceeds: number;
  // totals
  totalProfit: number;
  annualizedRoi: number;
  irr: number;
  // series
  equityGrowth: EquityPoint[];
  annualCfs: number[];
  propWealthSeries: number[];
  spPortfolioSeries: number[];
  spDeployedSeries: number[];
  spDeployed: number;
  spProfit: number;
}

/* ── helpers ──────────────────────────────────────────────────── */

export function calcEmi(principal: number, annualRate: number, years: number): number {
  if (principal <= 0) return 0;
  if (annualRate === 0) return principal / (years * 12);
  const i = annualRate / 100 / 12;
  const n = years * 12;
  return (principal * i * Math.pow(1 + i, n)) / (Math.pow(1 + i, n) - 1);
}

export function calcRemaining(
  principal: number,
  annualRate: number,
  totalYears: number,
  yearsPaid: number,
): number {
  if (yearsPaid >= totalYears || principal <= 0) return 0;
  if (annualRate === 0) return principal * (1 - yearsPaid / totalYears);
  const i = annualRate / 100 / 12;
  const N = totalYears * 12;
  const n = yearsPaid * 12;
  return Math.max(0, (principal * (Math.pow(1 + i, N) - Math.pow(1 + i, n))) / (Math.pow(1 + i, N) - 1));
}

/** Bisection + Newton-Raphson IRR — robust against divergence. */
function computeIrr(cashFlows: number[]): number {
  // Check if all flows are same sign → no IRR exists
  const hasNeg = cashFlows.some((c) => c < 0);
  const hasPos = cashFlows.some((c) => c > 0);
  if (!hasNeg || !hasPos) return 0;

  // NPV helper
  const npvAt = (rate: number): number => {
    let npv = 0;
    for (let t = 0; t < cashFlows.length; t++) {
      npv += cashFlows[t] / Math.pow(1 + rate, t);
    }
    return npv;
  };

  // 1) Bisection to find a stable bracket
  let lo = -0.5, hi = 5.0; // −50% to 500%
  let nLo = npvAt(lo), nHi = npvAt(hi);

  // If no sign change in bracket, widen or give up
  if (nLo * nHi > 0) {
    // Try wider range
    for (const tryHi of [10, 50, 100]) {
      nHi = npvAt(tryHi);
      if (nLo * nHi <= 0) { hi = tryHi; break; }
    }
    if (nLo * nHi > 0) return 0; // no root found
  }

  // Bisection: 60 iterations ≈ 1e-18 precision
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    const nMid = npvAt(mid);
    if (nMid * nLo <= 0) { hi = mid; nHi = nMid; }
    else { lo = mid; nLo = nMid; }
  }

  const r = (lo + hi) / 2;
  // Clamp to reasonable range: -100% to 1000%
  if (!isFinite(r) || r < -1 || r > 10) return 0;
  return r * 100;
}

/* ── main analyze ─────────────────────────────────────────────── */

export function analyze(listing: Listing, p: AnalysisParams): AnalysisResult {
  const price = listing.price;
  const moRent = listing.rentZestimate && listing.rentZestimate > 0
    ? listing.rentZestimate
    : price * 0.008;
  const taxRate = listing.propertyTaxRate ?? 2.15;
  const moHoa = listing.monthlyHoaFee ?? 0;

  // upfront
  const down = price * p.downPaymentPct / 100;
  const buyCc = price * p.closingCostsPct / 100;
  const initInv = down + buyCc;
  const loan = price - down;
  const emi = calcEmi(loan, p.interestRate, p.loanTerm);

  // year-1 monthly
  const moTax = price * taxRate / 100 / 12;
  const moIns = p.insuranceAnnual / 12;
  const moMaint = price * p.maintenancePct / 100 / 12;
  const moMgmt = moRent * p.mgmtFeePct / 100;
  const effRent = moRent * (1 - p.vacancyRate / 100);
  const moExp = emi + moTax + moHoa + moIns + moMaint + moMgmt;
  const moCf = effRent - moExp;

  const yr1Opex = (moTax + moHoa + moIns + moMaint + moMgmt) * 12;
  const yr1Noi = effRent * 12 - yr1Opex;
  const capRate = price ? (yr1Noi / price) * 100 : 0;
  const coc = initInv ? ((moCf * 12) / initInv) * 100 : 0;

  // year-by-year
  const irrFlows: number[] = [-initInv];
  const annualCfs: number[] = [];
  const equityList: EquityPoint[] = [];

  for (let yr = 1; yr <= p.holdingYears; yr++) {
    const yrRentMo = moRent * Math.pow(1 + p.rentIncreaseRate / 100, yr);
    const yrEffAnn = yrRentMo * (1 - p.vacancyRate / 100) * 12;
    const yrVal = price * Math.pow(1 + p.appreciationRate / 100, yr);
    const yrTaxAnn = yrVal * taxRate / 100;
    const yrMgmtAnn = yrRentMo * p.mgmtFeePct / 100 * 12;
    const yrMort = yr <= p.loanTerm ? emi * 12 : 0;
    const yrExp = yrMort + yrTaxAnn + moHoa * 12 + p.insuranceAnnual + yrVal * p.maintenancePct / 100 + yrMgmtAnn;
    const yrCf = yrEffAnn - yrExp;

    irrFlows.push(yrCf);
    annualCfs.push(yrCf);

    const yrBal = calcRemaining(loan, p.interestRate, p.loanTerm, yr);
    equityList.push({ year: yr, propertyValue: yrVal, remainingMortgage: yrBal, equity: yrVal - yrBal });
  }

  // sale
  const futureVal = price * Math.pow(1 + p.appreciationRate / 100, p.holdingYears);
  const remMort = calcRemaining(loan, p.interestRate, p.loanTerm, p.holdingYears);
  const sellCc = futureVal * p.sellingCostsPct / 100;
  const netSale = futureVal - remMort - sellCc;

  irrFlows[irrFlows.length - 1] += netSale;
  const totalProfit = irrFlows.slice(1).reduce((s, v) => s + v, 0) - initInv;
  const irrVal = computeIrr(irrFlows);
  const annRoi = initInv && p.holdingYears ? (totalProfit / initInv / p.holdingYears) * 100 : 0;

  // S&P comparison
  const sellFrac = p.sellingCostsPct / 100;
  const spPortfolio: number[] = [initInv];
  let spDep = initInv;
  const spDeployedList: number[] = [initInv];

  for (let yr = 1; yr <= p.holdingYears; yr++) {
    const grown = spPortfolio[spPortfolio.length - 1] * (1 + p.spGrowthRate / 100);
    const cf = annualCfs[yr - 1];
    const contrib = cf < 0 ? Math.abs(cf) : 0;
    spDep += contrib;
    spPortfolio.push(grown + contrib);
    spDeployedList.push(spDep);
  }

  // Property path: liquidation value
  const propWealth: number[] = [down - sellFrac * price];
  let cumulOp = 0;
  for (let yr = 1; yr <= p.holdingYears; yr++) {
    cumulOp += annualCfs[yr - 1];
    const ev = equityList[yr - 1];
    const liq = (ev.propertyValue - ev.remainingMortgage - sellFrac * ev.propertyValue) + cumulOp;
    propWealth.push(liq);
  }

  const spProfit = spPortfolio[spPortfolio.length - 1] - spDep;

  return {
    initialInvestment: initInv,
    downPayment: down,
    buyClosing: buyCc,
    loanAmount: loan,
    monthlyEmi: emi,
    monthlyCashFlow: moCf,
    annualCashFlow: moCf * 12,
    totalMonthlyExpenses: moExp,
    effectiveMonthlyRent: effRent,
    capRate,
    cashOnCash: coc,
    futurePropertyValue: futureVal,
    remainingMortgage: remMort,
    sellClosing: sellCc,
    netSaleProceeds: netSale,
    totalProfit,
    annualizedRoi: annRoi,
    irr: irrVal,
    equityGrowth: equityList,
    annualCfs,
    propWealthSeries: propWealth,
    spPortfolioSeries: spPortfolio,
    spDeployedSeries: spDeployedList,
    spDeployed: spDep,
    spProfit,
  };
}
