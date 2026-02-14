"""
Streamlit Real-Estate Rental & ROI Analysis
Analyses Zillow listings for investment potential with S&P 500 comparison.

Key financial calculations
──────────────────────────
EMI            M = P·i·(1+i)^n / ((1+i)^n − 1)
Remaining bal  B = P·((1+i)^N − (1+i)^n) / ((1+i)^N − 1)
Cap rate       Year-1 NOI / Purchase price
Cash-on-cash   Year-1 cash flow / Total cash invested
IRR            numpy-financial IRR on [-init, cf₁…cfₙ+sale]
Net sale       Sale price − bank balance − sell closing costs
Total profit   Σ(annual CFs) + net sale − initial investment
Property NW    Equity-in-property + cumulative operating cash − initial investment
S&P NW         S&P portfolio − total capital deployed  (same $ as property investor)
"""

import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from numpy_financial import irr as compute_irr


# ═══════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def load_listings(json_path: str = "json/zillow_75071_listings.json") -> pd.DataFrame:
    with open(json_path) as f:
        data = json.load(f)
    listings = data.get("listings", [])
    if not listings:
        return pd.DataFrame()

    df = pd.DataFrame(listings)

    # Numeric conversions
    for col in ("price", "rentZestimate", "livingArea", "lotAreaValue",
                "bedrooms", "bathrooms", "taxAssessedValue"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "propertyTaxRate" in df.columns:
        df["propertyTaxRate"] = pd.to_numeric(df["propertyTaxRate"], errors="coerce")
    else:
        df["propertyTaxRate"] = 2.15  # Collin County default

    if "monthlyHoaFee" in df.columns:
        df["monthlyHoaFee"] = pd.to_numeric(df["monthlyHoaFee"], errors="coerce").fillna(0)
    else:
        df["monthlyHoaFee"] = 0

    df["homeType"] = df.get("homeType", pd.Series(dtype=str)).fillna("Unknown")
    df["bedrooms"] = df["bedrooms"].fillna(0).astype(int)
    df["bathrooms"] = df["bathrooms"].fillna(0)

    # Fallback rent: 0.8 % of price per month when rentZestimate is missing
    df["rentZestimate"] = df.apply(
        lambda r: r["rentZestimate"]
        if pd.notna(r.get("rentZestimate")) and r["rentZestimate"] > 0
        else r["price"] * 0.008
        if pd.notna(r.get("price"))
        else 0,
        axis=1,
    )

    df = df[(df["price"] > 0) & (df["rentZestimate"] > 0)].copy()

    df["full_address"] = df.apply(
        lambda r: (
            f"{r.get('streetAddress','?')}, "
            f"{r.get('city','')}, {r.get('state','')} {r.get('zipcode','')}"
        ),
        axis=1,
    )
    return df


# ═══════════════════════════════════════════════════════════════════
# FINANCIAL HELPERS
# ═══════════════════════════════════════════════════════════════════

def calc_emi(principal: float, annual_rate: float, years: int) -> float:
    """Monthly EMI.  M = P·i·(1+i)^n / ((1+i)^n − 1)"""
    if principal <= 0:
        return 0.0
    if annual_rate == 0:
        return principal / (years * 12)
    i = annual_rate / 100 / 12
    n = years * 12
    return principal * i * (1 + i) ** n / ((1 + i) ** n - 1)


def calc_remaining(principal: float, annual_rate: float,
                   total_years: int, years_paid: int) -> float:
    """Outstanding mortgage balance after *years_paid* years."""
    if years_paid >= total_years or principal <= 0:
        return 0.0
    if annual_rate == 0:
        return principal * (1 - years_paid / total_years)
    i = annual_rate / 100 / 12
    N = total_years * 12
    n = years_paid * 12
    return max(0.0, principal * ((1 + i) ** N - (1 + i) ** n) / ((1 + i) ** N - 1))


# ═══════════════════════════════════════════════════════════════════
# PROPERTY ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def analyze(row: pd.Series, p: dict) -> dict:
    """Full financial analysis for one property."""
    price    = row["price"]
    mo_rent  = row["rentZestimate"]
    tax_rate = row.get("propertyTaxRate", 2.15)
    mo_hoa   = row.get("monthlyHoaFee", 0)

    # ── unpack params ────────────────────────────────────────────
    dp_pct      = p["down_payment_pct"]
    rate        = p["interest_rate"]
    loan_yrs    = p["loan_term"]
    buy_cc_pct  = p["closing_costs_pct"]
    sell_cc_pct = p["selling_costs_pct"]
    hold        = p["holding_years"]
    appr        = p["appreciation_rate"]
    rent_inc    = p["rent_increase_rate"]
    maint_pct   = p["maintenance_pct"]
    vac_pct     = p["vacancy_rate"]
    ins_annual  = p["insurance_annual"]
    mgmt_pct    = p["mgmt_fee_pct"]
    sp_rate     = p["sp_growth_rate"]

    # ── upfront ──────────────────────────────────────────────────
    down     = price * dp_pct / 100
    buy_cc   = price * buy_cc_pct / 100
    init_inv = down + buy_cc
    loan     = price - down
    emi      = calc_emi(loan, rate, loan_yrs)

    # ── year-1 monthly snapshot ──────────────────────────────────
    mo_tax   = price * tax_rate / 100 / 12
    mo_ins   = ins_annual / 12
    mo_maint = price * maint_pct / 100 / 12
    mo_mgmt  = mo_rent * mgmt_pct / 100
    eff_rent = mo_rent * (1 - vac_pct / 100)
    mo_exp   = emi + mo_tax + mo_hoa + mo_ins + mo_maint + mo_mgmt
    mo_cf    = eff_rent - mo_exp

    # cap rate  =  year-1 NOI / price
    yr1_opex = (mo_tax + mo_hoa + mo_ins + mo_maint + mo_mgmt) * 12
    yr1_noi  = eff_rent * 12 - yr1_opex
    cap_rate = yr1_noi / price * 100 if price else 0

    # cash-on-cash  =  year-1 cash-flow / initial investment
    coc = (mo_cf * 12) / init_inv * 100 if init_inv else 0

    # ── year-by-year ─────────────────────────────────────────────
    irr_flows   = [-init_inv]
    annual_cfs  = []          # operating cash-flows only (no sale)
    equity_list = []

    for yr in range(1, hold + 1):
        yr_rent_mo  = mo_rent * ((1 + rent_inc / 100) ** yr)
        yr_eff_ann  = yr_rent_mo * (1 - vac_pct / 100) * 12

        yr_val      = price * ((1 + appr / 100) ** yr)
        yr_tax_ann  = yr_val * tax_rate / 100
        yr_mgmt_ann = yr_rent_mo * mgmt_pct / 100 * 12
        yr_mort     = emi * 12 if yr <= loan_yrs else 0.0   # no payment after loan term
        yr_exp      = (yr_mort + yr_tax_ann + mo_hoa * 12
                       + ins_annual + yr_val * maint_pct / 100 + yr_mgmt_ann)

        yr_cf = yr_eff_ann - yr_exp
        irr_flows.append(yr_cf)
        annual_cfs.append(yr_cf)

        yr_bal = calc_remaining(loan, rate, loan_yrs, yr)
        equity_list.append({
            "year": yr,
            "property_value": yr_val,
            "remaining_mortgage": yr_bal,
            "equity": yr_val - yr_bal,
        })

    # ── sale ─────────────────────────────────────────────────────
    future_val = price * ((1 + appr / 100) ** hold)
    rem_mort   = calc_remaining(loan, rate, loan_yrs, hold)
    sell_cc    = future_val * sell_cc_pct / 100
    net_sale   = future_val - rem_mort - sell_cc        # sale − bank − closing

    irr_flows[-1] += net_sale                           # add to last year for IRR

    total_profit = sum(irr_flows[1:]) - init_inv        # all cash in − initial out

    try:
        irr_val = compute_irr(irr_flows) * 100
        if not np.isfinite(irr_val):
            irr_val = 0.0
    except Exception:
        irr_val = 0.0

    ann_roi = (total_profit / init_inv / hold * 100) if (init_inv and hold) else 0

    # ── PROPERTY NET-WORTH SERIES ────────────────────────────────
    # NW = equity_in_property + cumulative_operating_cash − init_inv
    #   year 0 : equity = down, cash = −init_inv  →  NW = −buy_closing
    #   year N : sold → equity 0, NW = total_profit
    prop_nw = [-buy_cc]
    cumul = 0.0
    for yr in range(1, hold + 1):
        cumul += annual_cfs[yr - 1]
        if yr < hold:
            nw = equity_list[yr - 1]["equity"] + cumul - init_inv
        else:
            nw = total_profit                          # after sale
        prop_nw.append(nw)

    # ── S&P NET-WORTH SERIES ─────────────────────────────────────
    # Invest the same dollars the property investor spends:
    #   • initial_investment at year 0
    #   • any negative operating CF each year (extra out-of-pocket)
    # NW = portfolio − total_capital_deployed
    sp_port     = init_inv
    sp_deployed = init_inv
    sp_nw       = [0.0]
    for yr in range(1, hold + 1):
        sp_port *= (1 + sp_rate / 100)
        cf = annual_cfs[yr - 1]
        if cf < 0:
            sp_port     += abs(cf)
            sp_deployed += abs(cf)
        sp_nw.append(sp_port - sp_deployed)

    return {
        # upfront
        "initial_investment": init_inv,
        "down_payment": down,
        "buy_closing": buy_cc,
        "loan_amount": loan,
        # year-1 snapshot
        "monthly_emi": emi,
        "monthly_cash_flow": mo_cf,
        "annual_cash_flow": mo_cf * 12,
        "total_monthly_expenses": mo_exp,
        "effective_monthly_rent": eff_rent,
        "cap_rate": cap_rate,
        "cash_on_cash": coc,
        # exit
        "future_property_value": future_val,
        "remaining_mortgage": rem_mort,
        "sell_closing": sell_cc,
        "net_sale_proceeds": net_sale,
        # totals
        "total_profit": total_profit,
        "annualized_roi": ann_roi,
        "irr": irr_val,
        # series
        "equity_growth": equity_list,
        "annual_cfs": annual_cfs,
        "prop_nw_series": prop_nw,
        "sp_nw_series": sp_nw,
        "sp_final_nw": sp_nw[-1],
        "sp_total_deployed": sp_deployed,
    }


# ═══════════════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════════════

def _fmt_dollar(v):
    try:
        return f"${float(v):,.0f}"
    except (ValueError, TypeError):
        return "–"


def _fmt_pct(v):
    try:
        return f"{float(v):.2f}%"
    except (ValueError, TypeError):
        return "–"


def _fmt_int(v):
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return "–"


def main():
    st.set_page_config(
        page_title="RE ROI Analyzer",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🏠 Real Estate Rental & ROI Analysis")
    st.markdown(
        "**McKinney, TX (75071)** — Investment Property Analyzer with S&P 500 Comparison"
    )

    df = load_listings()
    if df.empty:
        st.error("No data — check json/zillow_75071_listings.json")
        return

    # ──────────────────────────────────────────────────────────────
    # SIDEBAR
    # ──────────────────────────────────────────────────────────────
    sb = st.sidebar
    sb.header("📊 Analysis Parameters")

    sb.subheader("🏦 Loan")
    interest_rate    = sb.slider("Interest Rate (%)", 2.0, 10.0, 6.5, 0.25)
    loan_term        = sb.selectbox("Loan Term (years)", [15, 20, 30], index=2)
    down_payment_pct = sb.slider("Down Payment (%)", 5, 50, 20, 5)

    sb.subheader("💸 Transaction Costs")
    closing_costs_pct = sb.slider("Buy Closing Costs (%)", 1.0, 5.0, 3.0, 0.5)
    selling_costs_pct = sb.slider("Sell Closing Costs (%)", 1.0, 10.0, 6.0, 0.5)

    sb.subheader("⏳ Holding Period")
    holding_years = sb.selectbox("Years Until Sale", [3, 5, 7, 10, 15, 20, 30], index=4)

    sb.subheader("📈 Growth Assumptions")
    appreciation_rate  = sb.slider("Property Appreciation (%/yr)", 0.0, 10.0, 3.5, 0.5)
    rent_increase_rate = sb.slider("Rent Increase (%/yr)", 0.0, 10.0, 3.0, 0.5)
    sp_growth_rate     = sb.slider("S&P 500 Return (%/yr)", 0.0, 30.0, 10.0, 0.5)

    sb.subheader("🔧 Operating Costs")
    maintenance_pct  = sb.slider("Maintenance (% of value/yr)", 0.5, 3.0, 1.0, 0.25)
    vacancy_rate     = sb.slider("Vacancy Rate (%)", 0, 15, 5, 1)
    mgmt_fee_pct     = sb.slider("Property Mgmt Fee (% of rent)", 0.0, 12.0, 0.0, 1.0)
    insurance_annual = sb.number_input("Annual Insurance ($)", 500, 5000, 1200, 100)

    sb.subheader("🔍 Filters")
    p_min = int(df["price"].min())
    p_max = int(df["price"].max())
    if p_min == p_max:
        p_max = p_min + 1
    price_range = sb.slider(
        "Price Range ($)", p_min, p_max, (p_min, p_max), step=10_000,
        format="$%d",
    )
    home_types = sorted(df["homeType"].unique().tolist())
    sel_types  = sb.multiselect("Home Type", home_types, default=home_types)
    bed_opts   = sorted(df["bedrooms"].unique().tolist())
    sel_beds   = sb.multiselect("Bedrooms", bed_opts, default=bed_opts)

    # apply filters
    fdf = df[
        (df["price"] >= price_range[0])
        & (df["price"] <= price_range[1])
        & (df["homeType"].isin(sel_types))
        & (df["bedrooms"].isin(sel_beds))
    ]

    params = dict(
        interest_rate=interest_rate,
        loan_term=loan_term,
        down_payment_pct=down_payment_pct,
        closing_costs_pct=closing_costs_pct,
        selling_costs_pct=selling_costs_pct,
        holding_years=holding_years,
        appreciation_rate=appreciation_rate,
        rent_increase_rate=rent_increase_rate,
        maintenance_pct=maintenance_pct,
        vacancy_rate=vacancy_rate,
        insurance_annual=insurance_annual,
        mgmt_fee_pct=mgmt_fee_pct,
        sp_growth_rate=sp_growth_rate,
    )

    # ──────────────────────────────────────────────────────────────
    # ANALYZE
    # ──────────────────────────────────────────────────────────────
    if fdf.empty:
        st.warning("No properties match the current filters.")
        return

    with st.spinner(f"Analyzing {len(fdf)} properties …"):
        rows = []
        for _, r in fdf.iterrows():
            a = analyze(r, params)
            rows.append({
                "zpid": r["zpid"],
                "address": r["full_address"],
                "price": r["price"],
                "rent": r["rentZestimate"],
                "beds": r.get("bedrooms", 0),
                "baths": r.get("bathrooms", 0),
                "sqft": r.get("livingArea", 0),
                "homeType": r.get("homeType", "–"),
                **{k: a[k] for k in (
                    "monthly_cash_flow", "annual_cash_flow", "cap_rate",
                    "cash_on_cash", "total_profit", "annualized_roi", "irr",
                    "initial_investment", "future_property_value",
                    "net_sale_proceeds", "sell_closing", "remaining_mortgage",
                    "monthly_emi", "total_monthly_expenses",
                    "effective_monthly_rent", "down_payment", "buy_closing",
                    "sp_final_nw", "sp_total_deployed",
                    "equity_growth", "annual_cfs",
                    "prop_nw_series", "sp_nw_series",
                )},
            })
        rdf = pd.DataFrame(rows)

    # ──────────────────────────────────────────────────────────────
    # SUMMARY METRICS
    # ──────────────────────────────────────────────────────────────
    st.header("📈 Portfolio Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Properties", f"{len(rdf):,}")
    c2.metric("Avg IRR", f"{rdf['irr'].mean():.1f}%")
    c3.metric("Avg Monthly CF", f"${rdf['monthly_cash_flow'].mean():,.0f}")
    pos = int((rdf["monthly_cash_flow"] > 0).sum())
    c4.metric("Cash-Flow +ve", f"{pos} ({pos / len(rdf) * 100:.0f}%)")
    c5.metric("Avg Cash-on-Cash", f"{rdf['cash_on_cash'].mean():.1f}%")

    # ──────────────────────────────────────────────────────────────
    # SORT & TABLE
    # ──────────────────────────────────────────────────────────────
    st.header("🔍 Top Investment Opportunities")
    sc1, sc2 = st.columns([3, 1])
    sort_by = sc1.selectbox(
        "Sort By",
        ["Monthly Cash Flow", "Cap Rate", "IRR",
         "Cash-on-Cash", "Total Profit", "Annualized ROI"],
    )
    top_n = int(sc2.number_input("Show Top N", 5, 100, 10, 5))

    sort_map = {
        "Monthly Cash Flow": "monthly_cash_flow",
        "Cap Rate": "cap_rate",
        "IRR": "irr",
        "Cash-on-Cash": "cash_on_cash",
        "Total Profit": "total_profit",
        "Annualized ROI": "annualized_roi",
    }
    sdf = rdf.sort_values(sort_map[sort_by], ascending=False).head(top_n)

    tbl = sdf[[
        "address", "price", "rent", "beds", "baths", "sqft", "homeType",
        "monthly_cash_flow", "cap_rate", "cash_on_cash", "irr",
    ]].copy()
    tbl.columns = [
        "Address", "Price", "Rent/mo", "Beds", "Baths", "Sqft", "Type",
        "Monthly CF", "Cap Rate", "CoC Return", "IRR",
    ]
    for c in ("Price", "Rent/mo", "Monthly CF"):
        tbl[c] = tbl[c].apply(_fmt_dollar)
    for c in ("Cap Rate", "CoC Return", "IRR"):
        tbl[c] = tbl[c].apply(_fmt_pct)
    for c in ("Beds",):
        tbl[c] = tbl[c].apply(_fmt_int)
    tbl["Baths"] = tbl["Baths"].apply(
        lambda x: f"{float(x):.1f}" if pd.notna(x) else "–"
    )
    tbl["Sqft"] = tbl["Sqft"].apply(
        lambda x: f"{float(x):,.0f}" if pd.notna(x) and float(x) > 0 else "–"
    )

    st.dataframe(tbl, hide_index=True, width="stretch")

    # ──────────────────────────────────────────────────────────────
    # DETAILED PROPERTY VIEWS
    # ──────────────────────────────────────────────────────────────
    st.header("🏡 Property Details")

    for _, row in sdf.iterrows():
        with st.expander(f"📍 {row['address']} — ${row['price']:,.0f}"):

            # ── top metrics ──────────────────────────────────────
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Monthly CF", f"${row['monthly_cash_flow']:,.0f}")
            m2.metric("Cap Rate", f"{row['cap_rate']:.2f}%")
            m3.metric("Cash-on-Cash", f"{row['cash_on_cash']:.2f}%")
            m4.metric("IRR", f"{row['irr']:.2f}%")
            m5.metric(f"Profit ({holding_years}yr)", f"${row['total_profit']:,.0f}")

            # ── financial breakdown ──────────────────────────────
            st.subheader("💰 Financial Breakdown")
            fc1, fc2, fc3 = st.columns(3)

            with fc1:
                st.markdown("**Purchase**")
                st.write(f"Price: ${row['price']:,.0f}")
                st.write(f"Down Payment ({down_payment_pct}%): ${row['down_payment']:,.0f}")
                st.write(f"Buy Closing ({closing_costs_pct}%): ${row['buy_closing']:,.0f}")
                st.write(f"**Total Out-of-Pocket: ${row['initial_investment']:,.0f}**")

            with fc2:
                st.markdown("**Monthly (Year 1)**")
                st.write(f"Gross Rent: ${row['rent']:,.0f}")
                st.write(f"Eff. Rent (−{vacancy_rate}% vacancy): "
                         f"${row['effective_monthly_rent']:,.0f}")
                st.write(f"Mortgage ({loan_term}yr @ {interest_rate}%): "
                         f"${row['monthly_emi']:,.0f}")
                st.write(f"All Expenses: ${row['total_monthly_expenses']:,.0f}")
                cf_color = "green" if row["monthly_cash_flow"] >= 0 else "red"
                st.markdown(
                    f"**Cash Flow: "
                    f"<span style='color:{cf_color}'>${row['monthly_cash_flow']:,.0f}/mo"
                    f"</span>**",
                    unsafe_allow_html=True,
                )

            with fc3:
                st.markdown(f"**Sale (Year {holding_years})**")
                st.write(f"Future Value: ${row['future_property_value']:,.0f}")
                st.write(f"− Bank Owed: ${row['remaining_mortgage']:,.0f}")
                st.write(f"− Sell Closing ({selling_costs_pct}%): "
                         f"${row['sell_closing']:,.0f}")
                st.write(f"**= Net Proceeds: ${row['net_sale_proceeds']:,.0f}**")

            # ── annual cash-flow bar chart ────────────────────
            st.subheader("📊 Annual Operating Cash Flow")
            cfs = row["annual_cfs"]
            cf_yrs = list(range(1, len(cfs) + 1))
            colors = ["#06A77D" if v >= 0 else "#E74C3C" for v in cfs]
            cf_fig = go.Figure(
                go.Bar(x=cf_yrs, y=cfs, marker_color=colors,
                       hovertemplate="Year %{x}: $%{y:,.0f}<extra></extra>")
            )
            cf_fig.update_layout(
                xaxis_title="Year", yaxis_title="Cash Flow ($)",
                height=300, hovermode="x",
            )
            st.plotly_chart(cf_fig, key=f"cf_{row['zpid']}")

            # ── equity growth chart ───────────────────────────
            st.subheader(f"📈 Equity Growth Over {holding_years} Years")
            eq = row["equity_growth"]
            if eq:
                yrs = [e["year"] for e in eq]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=yrs,
                    y=[e["property_value"] for e in eq],
                    name="Property Value",
                    line=dict(color="#2E86AB", width=2),
                ))
                fig.add_trace(go.Scatter(
                    x=yrs,
                    y=[e["remaining_mortgage"] for e in eq],
                    name="Mortgage Balance",
                    line=dict(color="#A23B72", width=2),
                ))
                fig.add_trace(go.Scatter(
                    x=yrs,
                    y=[e["equity"] for e in eq],
                    name="Equity",
                    fill="tonexty",
                    line=dict(color="#06A77D", width=2),
                ))
                fig.update_layout(
                    xaxis_title="Year", yaxis_title="$",
                    height=380, hovermode="x unified",
                )
                st.plotly_chart(fig, key=f"eq_{row['zpid']}")

            # ── Property vs S&P net-worth comparison ──────────
            st.subheader("⚖️ Property vs S&P 500 — Net Worth Comparison")
            st.caption(
                "Both scenarios invest the **same total dollars** "
                "(initial investment + any negative cash-flow years). "
                "Net worth = assets − total capital deployed."
            )

            p_nw = row["prop_nw_series"]
            s_nw = row["sp_nw_series"]
            comp_yrs = list(range(len(p_nw)))

            comp_fig = go.Figure()
            comp_fig.add_trace(go.Scatter(
                x=comp_yrs, y=p_nw,
                name="Property Net Worth",
                line=dict(color="#2E86AB", width=3),
                hovertemplate="Year %{x}: $%{y:,.0f}<extra></extra>",
            ))
            comp_fig.add_trace(go.Scatter(
                x=comp_yrs, y=s_nw,
                name=f"S&P Net Worth ({sp_growth_rate}%/yr)",
                line=dict(color="#F39C12", width=3),
                hovertemplate="Year %{x}: $%{y:,.0f}<extra></extra>",
            ))
            # zero line
            comp_fig.add_hline(y=0, line_dash="dot", line_color="grey",
                               annotation_text="Break-even")
            comp_fig.update_layout(
                xaxis_title="Year", yaxis_title="Net Worth ($)",
                height=420, hovermode="x unified",
            )
            st.plotly_chart(comp_fig, key=f"cmp_{row['zpid']}")

            # final comparison metrics
            prop_profit = row["total_profit"]
            sp_profit   = row["sp_final_nw"]
            delta       = prop_profit - sp_profit
            winner      = "🏠 Property" if delta > 0 else "📈 S&P 500"

            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Property Profit", f"${prop_profit:,.0f}")
            cp2.metric(f"S&P Profit ({sp_growth_rate}%)", f"${sp_profit:,.0f}")
            cp3.metric("Winner", winner, f"by ${abs(delta):,.0f}")

    # ──────────────────────────────────────────────────────────────
    # FOOTER
    # ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        f"Data: json/zillow_75071_listings.json · "
        f"{len(df)} total · {len(fdf)} after filters · {len(rdf)} analyzed"
    )


if __name__ == "__main__":
    main()
