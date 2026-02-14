"""
Streamlit Real Estate Rental & ROI Analysis Application
Analyzes properties from Zillow listings JSON for investment potential
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from numpy_financial import irr


# ═══════════════════════════════════════════════════════════════════
# DATA LOADING & PREPROCESSING
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def load_listings(json_path: str = "json/zillow_75071_listings.json") -> pd.DataFrame:
    """Load and preprocess Zillow listings from JSON."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    listings = data.get("listings", [])
    if not listings:
        st.error("No listings found in JSON file")
        return pd.DataFrame()
    
    df = pd.DataFrame(listings)
    
    # Extract key fields
    required_fields = ["zpid", "streetAddress", "city", "state", "zipcode", 
                       "price", "rentZestimate", "bedrooms", "bathrooms", 
                       "livingArea", "homeType"]
    
    # Clean and convert data types
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    
    if "rentZestimate" in df.columns:
        df["rentZestimate"] = pd.to_numeric(df["rentZestimate"], errors="coerce")
    
    if "propertyTaxRate" in df.columns:
        df["propertyTaxRate"] = pd.to_numeric(df["propertyTaxRate"], errors="coerce")
    else:
        df["propertyTaxRate"] = 2.15  # Default for McKinney, TX
    
    if "monthlyHoaFee" in df.columns:
        df["monthlyHoaFee"] = pd.to_numeric(df["monthlyHoaFee"], errors="coerce").fillna(0)
    else:
        df["monthlyHoaFee"] = 0
    
    # Handle missing rent estimates (0.8% of purchase price per month)
    df["rentZestimate"] = df.apply(
        lambda row: row["rentZestimate"] if pd.notna(row["rentZestimate"]) and row["rentZestimate"] > 0
        else row["price"] * 0.008 if pd.notna(row["price"]) 
        else 0,
        axis=1
    )
    
    # Filter out properties with no price or invalid data
    df = df[df["price"] > 0].copy()
    df = df[df["rentZestimate"] > 0].copy()
    
    # Create full address
    df["full_address"] = df.apply(
        lambda row: f"{row.get('streetAddress', 'Unknown')}, {row.get('city', '')}, {row.get('state', '')} {row.get('zipcode', '')}",
        axis=1
    )
    
    return df


# ═══════════════════════════════════════════════════════════════════
# FINANCIAL CALCULATIONS
# ═══════════════════════════════════════════════════════════════════

def calculate_monthly_emi(principal: float, annual_rate: float, years: int) -> float:
    """
    Calculate monthly EMI using standard formula:
    M = P * [i(1 + i)^n] / [(1 + i)^n - 1]
    where i = monthly interest rate, n = total months
    """
    if annual_rate == 0:
        return principal / (years * 12)
    
    monthly_rate = annual_rate / 100 / 12
    n_months = years * 12
    
    emi = principal * (monthly_rate * (1 + monthly_rate) ** n_months) / \
          ((1 + monthly_rate) ** n_months - 1)
    
    return emi


def calculate_remaining_balance(principal: float, annual_rate: float, 
                               total_years: int, years_paid: int) -> float:
    """Calculate remaining mortgage balance after N years."""
    if annual_rate == 0:
        return principal * (1 - years_paid / total_years)
    
    monthly_rate = annual_rate / 100 / 12
    n_total = total_years * 12
    n_paid = years_paid * 12
    
    remaining = principal * ((1 + monthly_rate) ** n_total - (1 + monthly_rate) ** n_paid) / \
                ((1 + monthly_rate) ** n_total - 1)
    
    return max(0, remaining)


def analyze_property(row: pd.Series, params: dict) -> dict:
    """
    Comprehensive property analysis with all financial calculations.
    
    Returns a dict with monthly cash flow, cap rate, total ROI, IRR, etc.
    """
    price = row["price"]
    monthly_rent = row["rentZestimate"]
    property_tax_rate = row.get("propertyTaxRate", 2.15)
    monthly_hoa = row.get("monthlyHoaFee", 0)
    
    # User parameters
    down_payment_pct = params["down_payment_pct"]
    interest_rate = params["interest_rate"]
    closing_costs_pct = params["closing_costs_pct"]
    holding_years = params["holding_years"]
    appreciation_rate = params["appreciation_rate"]
    rent_increase_rate = params["rent_increase_rate"]
    maintenance_pct = params["maintenance_pct"]
    vacancy_rate = params["vacancy_rate"]
    insurance_annual = params["insurance_annual"]
    
    # Initial costs
    down_payment = price * (down_payment_pct / 100)
    closing_costs = price * (closing_costs_pct / 100)
    initial_investment = down_payment + closing_costs
    
    # Loan details
    loan_amount = price - down_payment
    monthly_emi = calculate_monthly_emi(loan_amount, interest_rate, 30)
    
    # Monthly expenses
    monthly_property_tax = (price * (property_tax_rate / 100)) / 12
    monthly_insurance = insurance_annual / 12
    monthly_maintenance = (price * (maintenance_pct / 100)) / 12
    
    total_monthly_expenses = monthly_emi + monthly_property_tax + monthly_hoa + \
                            monthly_insurance + monthly_maintenance
    
    # Effective rent (accounting for vacancy)
    effective_monthly_rent = monthly_rent * (1 - vacancy_rate / 100)
    
    # Monthly cash flow
    monthly_cash_flow = effective_monthly_rent - total_monthly_expenses
    
    # Annual metrics
    annual_cash_flow = monthly_cash_flow * 12
    
    # Cap rate (Year 1 NOI / Purchase Price)
    annual_noi = (effective_monthly_rent * 12) - \
                 ((monthly_property_tax + monthly_hoa + monthly_insurance + monthly_maintenance) * 12)
    cap_rate = (annual_noi / price) * 100
    
    # Future value calculations
    future_property_value = price * ((1 + appreciation_rate / 100) ** holding_years)
    remaining_mortgage = calculate_remaining_balance(loan_amount, interest_rate, 30, holding_years)
    
    # Total cash flows over holding period (for IRR)
    cash_flows = [-initial_investment]  # Initial outflow
    
    cumulative_equity = 0
    equity_growth = []
    
    for year in range(1, holding_years + 1):
        # Rent grows each year
        year_rent = monthly_rent * ((1 + rent_increase_rate / 100) ** year)
        year_effective_rent = year_rent * (1 - vacancy_rate / 100) * 12
        
        # Expenses (property tax grows with appreciation, others are fixed)
        year_property_value = price * ((1 + appreciation_rate / 100) ** year)
        year_property_tax = (year_property_value * (property_tax_rate / 100))
        year_expenses = monthly_emi * 12 + year_property_tax + (monthly_hoa * 12) + \
                       insurance_annual + (year_property_value * maintenance_pct / 100)
        
        year_cash_flow = year_effective_rent - year_expenses
        cash_flows.append(year_cash_flow)
        
        # Equity = property value - remaining mortgage
        year_remaining_mortgage = calculate_remaining_balance(loan_amount, interest_rate, 30, year)
        year_equity = year_property_value - year_remaining_mortgage
        equity_growth.append({
            "year": year,
            "property_value": year_property_value,
            "remaining_mortgage": year_remaining_mortgage,
            "equity": year_equity
        })
        cumulative_equity = year_equity
    
    # Exit: add final sale proceeds (minus selling costs)
    selling_costs = future_property_value * 0.06  # 6% selling costs
    net_sale_proceeds = future_property_value - remaining_mortgage - selling_costs
    cash_flows[-1] += net_sale_proceeds  # Add to final year cash flow
    
    # Total profit
    total_cash_inflows = sum(cash_flows[1:])
    total_profit = total_cash_inflows - initial_investment
    
    # Calculate IRR
    try:
        irr_value = irr(cash_flows) * 100  # Convert to percentage
        if not np.isfinite(irr_value):
            irr_value = 0
    except:
        irr_value = 0
    
    # Annualized ROI (simple)
    annualized_roi = (total_profit / initial_investment / holding_years) * 100 if initial_investment > 0 else 0
    
    return {
        "initial_investment": initial_investment,
        "down_payment": down_payment,
        "closing_costs": closing_costs,
        "loan_amount": loan_amount,
        "monthly_emi": monthly_emi,
        "monthly_cash_flow": monthly_cash_flow,
        "annual_cash_flow": annual_cash_flow,
        "cap_rate": cap_rate,
        "future_property_value": future_property_value,
        "remaining_mortgage": remaining_mortgage,
        "net_sale_proceeds": net_sale_proceeds,
        "total_profit": total_profit,
        "annualized_roi": annualized_roi,
        "irr": irr_value,
        "equity_growth": equity_growth,
        "total_monthly_expenses": total_monthly_expenses,
        "effective_monthly_rent": effective_monthly_rent,
    }


# ═══════════════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Real Estate ROI Analyzer",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏠 Real Estate Rental & ROI Analysis")
    st.markdown("**McKinney, TX (Zip Code 75071)** — Investment Property Analysis")
    
    # Load data
    df = load_listings()
    
    if df.empty:
        st.error("No data available. Please check the JSON file.")
        return
    
    st.sidebar.header("📊 Analysis Parameters")
    
    # ═══════════════════════════════════════════════════════════════
    # SIDEBAR INPUTS
    # ═══════════════════════════════════════════════════════════════
    
    st.sidebar.subheader("🏦 Loan Details")
    interest_rate = st.sidebar.slider(
        "30-Year Interest Rate (%)", 
        min_value=2.0, max_value=8.0, value=6.5, step=0.25
    )
    down_payment_pct = st.sidebar.slider(
        "Down Payment (%)", 
        min_value=5, max_value=50, value=20, step=5
    )
    closing_costs_pct = st.sidebar.slider(
        "Closing Costs (%)", 
        min_value=1.0, max_value=5.0, value=3.0, step=0.5
    )
    
    st.sidebar.subheader("⏳ Holding Period")
    holding_years = st.sidebar.selectbox(
        "Years Until Sale", 
        options=[5, 10, 15, 20, 30],
        index=2  # Default to 15 years
    )
    
    st.sidebar.subheader("📈 Growth Assumptions")
    appreciation_rate = st.sidebar.slider(
        "Annual Property Appreciation (%)", 
        min_value=0.0, max_value=10.0, value=3.5, step=0.5
    )
    rent_increase_rate = st.sidebar.slider(
        "Annual Rent Increase (%)", 
        min_value=0.0, max_value=10.0, value=3.0, step=0.5
    )
    
    st.sidebar.subheader("🔧 Maintenance & Vacancy")
    maintenance_pct = st.sidebar.slider(
        "Annual Maintenance/Repair (%)", 
        min_value=0.5, max_value=3.0, value=1.0, step=0.25
    )
    vacancy_rate = st.sidebar.slider(
        "Vacancy Rate (%)", 
        min_value=0, max_value=15, value=5, step=1
    )
    
    st.sidebar.subheader("🏥 Insurance")
    insurance_annual = st.sidebar.number_input(
        "Annual Insurance ($)", 
        min_value=500, max_value=3000, value=1200, step=100
    )
    
    # Package parameters
    params = {
        "interest_rate": interest_rate,
        "down_payment_pct": down_payment_pct,
        "closing_costs_pct": closing_costs_pct,
        "holding_years": holding_years,
        "appreciation_rate": appreciation_rate,
        "rent_increase_rate": rent_increase_rate,
        "maintenance_pct": maintenance_pct,
        "vacancy_rate": vacancy_rate,
        "insurance_annual": insurance_annual,
    }
    
    # ═══════════════════════════════════════════════════════════════
    # ANALYZE ALL PROPERTIES
    # ═══════════════════════════════════════════════════════════════
    
    with st.spinner("Analyzing properties..."):
        results = []
        for idx, row in df.iterrows():
            analysis = analyze_property(row, params)
            results.append({
                "zpid": row["zpid"],
                "address": row["full_address"],
                "price": row["price"],
                "rent": row["rentZestimate"],
                "beds": row.get("bedrooms", "N/A"),
                "baths": row.get("bathrooms", "N/A"),
                "sqft": row.get("livingArea", "N/A"),
                "monthly_cash_flow": analysis["monthly_cash_flow"],
                "annual_cash_flow": analysis["annual_cash_flow"],
                "cap_rate": analysis["cap_rate"],
                "total_profit": analysis["total_profit"],
                "annualized_roi": analysis["annualized_roi"],
                "irr": analysis["irr"],
                "initial_investment": analysis["initial_investment"],
                "future_value": analysis["future_property_value"],
                "equity_growth": analysis["equity_growth"],
                "monthly_emi": analysis["monthly_emi"],
                "total_monthly_expenses": analysis["total_monthly_expenses"],
                "effective_monthly_rent": analysis["effective_monthly_rent"],
            })
        
        results_df = pd.DataFrame(results)
    
    # ═══════════════════════════════════════════════════════════════
    # SUMMARY METRICS
    # ═══════════════════════════════════════════════════════════════
    
    st.header("📈 Portfolio Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Properties",
            f"{len(results_df):,}"
        )
    
    with col2:
        avg_roi = results_df["annualized_roi"].mean()
        st.metric(
            "Avg Annualized ROI",
            f"{avg_roi:.2f}%"
        )
    
    with col3:
        avg_cash_flow = results_df["monthly_cash_flow"].mean()
        st.metric(
            "Avg Monthly Cash Flow",
            f"${avg_cash_flow:,.0f}"
        )
    
    with col4:
        positive_cf = len(results_df[results_df["monthly_cash_flow"] > 0])
        st.metric(
            "Positive Cash Flow",
            f"{positive_cf} ({positive_cf/len(results_df)*100:.1f}%)"
        )
    
    # ═══════════════════════════════════════════════════════════════
    # SORTING & FILTERING
    # ═══════════════════════════════════════════════════════════════
    
    st.header("🔍 Top Investment Opportunities")
    
    sort_col1, sort_col2 = st.columns([3, 1])
    
    with sort_col1:
        sort_by = st.selectbox(
            "Sort By",
            options=["Monthly Cash Flow", "Cap Rate", "Total ROI (IRR)", "Annualized ROI"],
            index=0
        )
    
    with sort_col2:
        top_n = st.number_input("Show Top N", min_value=5, max_value=50, value=10, step=5)
    
    # Sort logic
    sort_mapping = {
        "Monthly Cash Flow": "monthly_cash_flow",
        "Cap Rate": "cap_rate",
        "Total ROI (IRR)": "irr",
        "Annualized ROI": "annualized_roi"
    }
    
    sorted_df = results_df.sort_values(
        by=sort_mapping[sort_by], 
        ascending=False
    ).head(top_n)
    
    # ═══════════════════════════════════════════════════════════════
    # DISPLAY TABLE
    # ═══════════════════════════════════════════════════════════════
    
    st.subheader(f"Top {top_n} Properties by {sort_by}")
    
    display_df = sorted_df[[
        "address", "price", "rent", "beds", "baths", "sqft",
        "monthly_cash_flow", "cap_rate", "annualized_roi", "irr"
    ]].copy()
    
    # Format columns
    display_df["price"] = display_df["price"].apply(lambda x: f"${x:,.0f}")
    display_df["rent"] = display_df["rent"].apply(lambda x: f"${x:,.0f}")
    display_df["monthly_cash_flow"] = display_df["monthly_cash_flow"].apply(lambda x: f"${x:,.0f}")
    display_df["cap_rate"] = display_df["cap_rate"].apply(lambda x: f"{x:.2f}%")
    display_df["annualized_roi"] = display_df["annualized_roi"].apply(lambda x: f"{x:.2f}%")
    display_df["irr"] = display_df["irr"].apply(lambda x: f"{x:.2f}%")
    
    display_df.columns = [
        "Address", "Price", "Monthly Rent", "Beds", "Baths", "Sqft",
        "Monthly Cash Flow", "Cap Rate", "Ann. ROI", "IRR"
    ]
    
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True
    )
    
    # ═══════════════════════════════════════════════════════════════
    # DETAILED PROPERTY VIEWS
    # ═══════════════════════════════════════════════════════════════
    
    st.header("🏡 Property Details")
    
    for idx, row in sorted_df.iterrows():
        with st.expander(f"📍 {row['address']} — ${row['price']:,.0f}"):
            
            # Metrics
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            
            with metric_col1:
                st.metric("Monthly Cash Flow", f"${row['monthly_cash_flow']:,.0f}")
            
            with metric_col2:
                st.metric("Cap Rate", f"{row['cap_rate']:.2f}%")
            
            with metric_col3:
                st.metric("Annualized ROI", f"{row['annualized_roi']:.2f}%")
            
            with metric_col4:
                st.metric("IRR", f"{row['irr']:.2f}%")
            
            # Financial breakdown
            st.subheader("💰 Financial Breakdown")
            
            fin_col1, fin_col2 = st.columns(2)
            
            with fin_col1:
                st.markdown("**Initial Investment**")
                st.write(f"Down Payment: ${row['initial_investment'] - (row['price'] * closing_costs_pct / 100):,.0f}")
                st.write(f"Closing Costs: ${row['price'] * closing_costs_pct / 100:,.0f}")
                st.write(f"**Total: ${row['initial_investment']:,.0f}**")
                
                st.markdown("**Monthly Income**")
                st.write(f"Gross Rent: ${row['rent']:,.0f}")
                st.write(f"Effective Rent (after vacancy): ${row['effective_monthly_rent']:,.0f}")
            
            with fin_col2:
                st.markdown("**Monthly Expenses**")
                st.write(f"Mortgage (EMI): ${row['monthly_emi']:,.0f}")
                st.write(f"Total Expenses: ${row['total_monthly_expenses']:,.0f}")
                st.write(f"**Net Cash Flow: ${row['monthly_cash_flow']:,.0f}**")
                
                st.markdown(f"**Exit ({holding_years} years)**")
                st.write(f"Property Value: ${row['future_value']:,.0f}")
                st.write(f"Total Profit: ${row['total_profit']:,.0f}")
            
            # Equity growth chart
            st.subheader(f"📊 Equity Growth Over {holding_years} Years")
            
            equity_data = row["equity_growth"]
            
            if equity_data:
                years = [item["year"] for item in equity_data]
                property_values = [item["property_value"] for item in equity_data]
                mortgages = [item["remaining_mortgage"] for item in equity_data]
                equities = [item["equity"] for item in equity_data]
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=years, y=property_values, 
                    name="Property Value",
                    line=dict(color="#2E86AB", width=3)
                ))
                
                fig.add_trace(go.Scatter(
                    x=years, y=mortgages,
                    name="Remaining Mortgage",
                    line=dict(color="#A23B72", width=3)
                ))
                
                fig.add_trace(go.Scatter(
                    x=years, y=equities,
                    name="Your Equity",
                    fill='tonexty',
                    line=dict(color="#06A77D", width=3)
                ))
                
                fig.update_layout(
                    title="Property Value, Mortgage, and Equity Over Time",
                    xaxis_title="Year",
                    yaxis_title="Amount ($)",
                    hovermode="x unified",
                    height=400
                )
                
                st.plotly_chart(fig, key=f"equity_chart_{row['zpid']}")
    
    # ═══════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.caption(f"Data source: `json/zillow_75071_listings.json` | {len(df)} total properties analyzed")


if __name__ == "__main__":
    main()
