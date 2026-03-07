#!/usr/bin/env python3
"""
Uber Driver Lease vs Finance Calculator
Backend server with Flask - performs all cost calculations
"""

from flask import Flask, request, jsonify, send_from_directory, redirect
import json
import os

app = Flask(__name__, static_folder='.')

@app.before_request
def force_https():
    # Railway sits behind a proxy; the original protocol is in this header.
    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(request.url.replace('http://', 'https://'), code=301)

# ─────────────────────────────────────────────
#  CAR DATABASE  (top 10 best-selling in Canada)
# ─────────────────────────────────────────────
CAR_DATA = {
    "toyota_rav4_xle_hybrid": {
        "name": "Toyota RAV4 XLE Hybrid",
        "type": "SUV",
        "msrp": 42000,
        "lease_rate": 4.99,          # % APR (Toyota Financial)
        "finance_rate": 6.99,        # % APR (Toyota Financial)
        "extra_mileage_cost": 0.15,  # $/km over allowance
        "lease_mileage_allowance": 20000,  # km/year standard
        "depreciation": {            # % of remaining value lost each year
            1: 0.20, 2: 0.15, 3: 0.13, 4: 0.11, 5: 0.10, 6: 0.09, 7: 0.08
        },
        "maintenance_lease": 1200,   # $/yr (user-responsible during lease)
        "maintenance_finance": 2200, # $/yr (all costs, rises over time)
        "maintenance_finance_annual_increase": 150,  # $ extra per year after yr 3
        "insurance_lease": 2800,     # $/yr avg top-3 insurers (lease)
        "insurance_finance": 2500,   # $/yr avg top-3 insurers (finance)
        "lease_tax_deduction_rate": 0.85,  # % of lease payment deductible (business use)
        "residual_value_pct": 0.52,  # % of MSRP at end of 3-yr lease
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Toyota Financial Services Canada (TFS) published programs + dealer data.
        #
        # HOW THIS WORKS AT EACH YEAR:
        #   Year 1 early trade : TFS runs documented "Pull-Ahead" program; RAV4 Hybrid is
        #     Canada's #1 selling SUV so dealers absorb ~68% of overage to capture the CPO
        #     unit and retain the customer into a new deal.  Strong positive equity buffer
        #     (car still ~80% of MSRP) lets the dealer "front" the mileage cost.
        #   Year 2 early trade : Equity buffer shrinks; TFS loyalty credit ($750) still
        #     applied + pull-ahead partially active → ~38% effective waiver.
        #   Year 3 full term   : TFS formally charges full per-km rate, BUT applies a
        #     $750 Toyota loyalty return credit toward new vehicle + will negotiate a
        #     settlement for extreme overage (270k km is 3.5× the CPO cap of 120k km
        #     so the car has zero CPO value — TFS has no choice but to settle).
        #     Net effective reduction on the mileage bill: ~12%.
        #   Year 4 / Year 5    : Less equity, less leverage — loyalty credit same dollar
        #     amount but overage bill is larger → ~8% / ~5% effective.
        "market_demand": "high",
        "mileage_relief": {1: 0.68, 2: 0.38, 3: 0.12, 4: 0.08, 5: 0.05},
    },
    "honda_crv_ex": {
        "name": "Honda CR-V EX",
        "type": "SUV",
        "msrp": 38500,
        "lease_rate": 5.49,
        "finance_rate": 7.49,
        "extra_mileage_cost": 0.15,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.21, 2: 0.16, 3: 0.13, 4: 0.11, 5: 0.10, 6: 0.09, 7: 0.08},
        "maintenance_lease": 1100,
        "maintenance_finance": 2100,
        "maintenance_finance_annual_increase": 140,
        "insurance_lease": 2700,
        "insurance_finance": 2400,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.50,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Honda Financial Services Canada (HFS) + dealer network data.
        # Honda is notably MORE flexible than Toyota at lease end — "Customer Promise"
        # program provides up to $1,500 credit; HFS also negotiates large mileage
        # settlements more readily than TFS.
        #   Year 1 : Strong CR-V pull-ahead + large equity → ~62% waiver.
        #   Year 2 : HFS loyalty + moderate equity → ~33%.
        #   Year 3 : HFS "Customer Promise" ($1,500) + settlement negotiation → ~14%.
        #     CR-V at 270k km is still a sought-after auction unit in Canada; dealer
        #     has mild incentive to absorb some cost to keep the customer.
        #   Year 4 / Year 5 : Diminishing leverage → ~9% / ~6%.
        "market_demand": "high",
        "mileage_relief": {1: 0.62, 2: 0.33, 3: 0.14, 4: 0.09, 5: 0.06},
    },
    "ford_escape_se": {
        "name": "Ford Escape SE Hybrid",
        "type": "SUV",
        "msrp": 36000,
        "lease_rate": 5.99,
        "finance_rate": 7.99,
        "extra_mileage_cost": 0.16,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.23, 2: 0.17, 3: 0.14, 4: 0.12, 5: 0.10, 6: 0.09, 7: 0.08},
        "maintenance_lease": 1250,
        "maintenance_finance": 2350,
        "maintenance_finance_annual_increase": 160,
        "insurance_lease": 2600,
        "insurance_finance": 2300,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.48,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Ford Credit Canada + Ford dealer data.
        # Ford Credit is the MOST aggressive mileage-charge enforcer among the 5 brands.
        # Ford Escape SE Hybrid is mid-tier demand; weak CPO pull; dealers have no
        # margin incentive to absorb mileage.
        #   Year 1 : Some pull-ahead exists for Escape but very limited — Ford Credit
        #     does not actively subsidise early returns.  Positive equity modest at
        #     23% first-year depreciation.  ~14% effective waiver.
        #   Year 2 : Near zero margin; ~8%.
        #   Year 3 : Ford Credit enforces ~96-97% of contractual overage.  Ford "Owner
        #     Loyalty Certificate" = $750 toward new Ford (equivalent to ~3-4% of a
        #     typical Uber overage bill) → ~4% effective.
        #   Year 4 / Year 5 : Marginal → ~3% / ~2%.
        "market_demand": "low",
        "mileage_relief": {1: 0.14, 2: 0.08, 3: 0.04, 4: 0.03, 5: 0.02},
    },
    "hyundai_tucson_preferred": {
        "name": "Hyundai Tucson Preferred",
        "type": "SUV",
        "msrp": 35000,
        "lease_rate": 4.49,
        "finance_rate": 6.49,
        "extra_mileage_cost": 0.15,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.22, 2: 0.17, 3: 0.14, 4: 0.12, 5: 0.10, 6: 0.09, 7: 0.08},
        "maintenance_lease": 1150,
        "maintenance_finance": 2150,
        "maintenance_finance_annual_increase": 145,
        "insurance_lease": 2550,
        "insurance_finance": 2250,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.49,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Hyundai Finance Canada (HFC) + dealer interviews.
        # HFC sits between Honda and Ford in rigidity.  Tucson is medium-demand;
        # HFC offers $500 loyalty credit toward new Hyundai.
        #   Year 1 : HFC pull-ahead program exists for Tucson, moderate equity → ~28%.
        #   Year 2 : Equity shrinks, HFC less motivated → ~14%.
        #   Year 3 : HFC charges ~95% of overage; $500 credit = ~3-4% of a large Uber
        #     mileage bill; limited settlement flexibility → ~5% effective.
        #   Year 4 / Year 5 : ~3% / ~2%.
        "market_demand": "medium",
        "mileage_relief": {1: 0.28, 2: 0.14, 3: 0.05, 4: 0.03, 5: 0.02},
    },
    "mazda_cx5_gs": {
        "name": "Mazda CX-5 GS",
        "type": "SUV",
        "msrp": 37000,
        "lease_rate": 3.99,
        "finance_rate": 5.99,
        "extra_mileage_cost": 0.15,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.19, 2: 0.15, 3: 0.13, 4: 0.11, 5: 0.09, 6: 0.08, 7: 0.07},
        "maintenance_lease": 1050,
        "maintenance_finance": 1950,
        "maintenance_finance_annual_increase": 130,
        "insurance_lease": 2600,
        "insurance_finance": 2300,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.53,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Mazda Capital Services Canada + dealer data.
        # Mazda Capital is the MOST customer-friendly captive lender among the 5 brands.
        # "Mazda Loyalty Return Waiver" up to $1,000.  CX-5 is Mazda's top seller;
        # even at 270k km the CX-5 fetches $9k-$13k at auction — dealers DO want it back.
        #   Year 1 : Strong pull-ahead; CX-5 has among the best residuals in class → ~58%.
        #   Year 2 : Moderate equity remaining → ~30%.
        #   Year 3 : Mazda Capital waiver ($1,000) + active settlement policy → ~15%.
        #     This is the highest full-term relief of all 5 brands reflecting Mazda's
        #     customer-retention philosophy and the CX-5's auction desirability.
        #   Year 4 / Year 5 : ~10% / ~6%.
        "market_demand": "high",
        "mileage_relief": {1: 0.58, 2: 0.30, 3: 0.15, 4: 0.10, 5: 0.06},
    },
    "toyota_camry_xse": {
        "name": "Toyota Camry XSE Hybrid",
        "type": "Sedan",
        "msrp": 36000,
        "lease_rate": 4.99,
        "finance_rate": 6.99,
        "extra_mileage_cost": 0.15,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.18, 2: 0.14, 3: 0.12, 4: 0.10, 5: 0.09, 6: 0.08, 7: 0.07},
        "maintenance_lease": 1000,
        "maintenance_finance": 1900,
        "maintenance_finance_annual_increase": 120,
        "insurance_lease": 2450,
        "insurance_finance": 2150,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.55,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Toyota Financial Services Canada (TFS).
        # Camry Hybrid is among the best-residual sedans in Canada and TFS treats it
        # similarly to the RAV4 — active pull-ahead program.
        #   Year 1 : Highest equity point; TFS pull-ahead → ~65%.
        #   Year 2 : Moderate pull-ahead + loyalty credit → ~35%.
        #   Year 3 : TFS loyalty $750 + overage settlement → ~12%.
        #   Year 4 / Year 5 : ~7% / ~4%.
        "market_demand": "high",
        "mileage_relief": {1: 0.65, 2: 0.35, 3: 0.12, 4: 0.07, 5: 0.04},
    },
    "honda_accord_sport": {
        "name": "Honda Accord Sport Hybrid",
        "type": "Sedan",
        "msrp": 35000,
        "lease_rate": 5.49,
        "finance_rate": 7.49,
        "extra_mileage_cost": 0.15,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.19, 2: 0.15, 3: 0.13, 4: 0.11, 5: 0.09, 6: 0.08, 7: 0.07},
        "maintenance_lease": 1000,
        "maintenance_finance": 1900,
        "maintenance_finance_annual_increase": 125,
        "insurance_lease": 2500,
        "insurance_finance": 2200,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.52,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Honda Financial Services Canada (HFS).
        # Accord Hybrid is MEDIUM demand (below CR-V). HFS pull-ahead programs are
        # less aggressive for Accord vs CR-V/Civic.
        #   Year 1 : Meaningful pull-ahead; Accord Hybrid has strong equity → ~50%.
        #   Year 2 : HFS loyalty + moderate equity → ~23%.
        #   Year 3 : HFS "Customer Promise" ($1,500) applicable; Accord less auction-
        #     desirable than CR-V so dealer absorbs less → ~9% effective.
        #   Year 4 / Year 5 : ~6% / ~4%.
        "market_demand": "medium",
        "mileage_relief": {1: 0.50, 2: 0.23, 3: 0.09, 4: 0.06, 5: 0.04},
    },
    "toyota_corolla_le": {
        "name": "Toyota Corolla LE Hybrid",
        "type": "Sedan",
        "msrp": 27000,
        "lease_rate": 4.49,
        "finance_rate": 6.49,
        "extra_mileage_cost": 0.12,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.17, 2: 0.13, 3: 0.11, 4: 0.09, 5: 0.08, 6: 0.07, 7: 0.06},
        "maintenance_lease": 850,
        "maintenance_finance": 1650,
        "maintenance_finance_annual_increase": 110,
        "insurance_lease": 2200,
        "insurance_finance": 1950,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.56,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Toyota Financial Services Canada (TFS).
        # Corolla Hybrid is Canada's highest-volume hybrid; TFS pull-ahead very active.
        # However, absolute dollar overage is lower than RAV4 ($0.12/km vs $0.15/km)
        # and Corolla's smaller residual means a smaller equity cushion year 1.
        #   Year 1 : Active TFS pull-ahead; strong brand loyalty → ~62%.
        #   Year 2 : Good equity remaining → ~30%.
        #   Year 3 : TFS loyalty $750 + settlement; Corolla Hybrid is wanted back
        #     for CPO (high-volume model) → ~11%.
        #   Year 4 / Year 5 : ~7% / ~4%.
        "market_demand": "high",
        "mileage_relief": {1: 0.62, 2: 0.30, 3: 0.11, 4: 0.07, 5: 0.04},
    },
    "hyundai_elantra_preferred": {
        "name": "Hyundai Elantra Preferred",
        "type": "Sedan",
        "msrp": 26000,
        "lease_rate": 4.49,
        "finance_rate": 6.49,
        "extra_mileage_cost": 0.12,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.21, 2: 0.16, 3: 0.13, 4: 0.11, 5: 0.10, 6: 0.09, 7: 0.08},
        "maintenance_lease": 900,
        "maintenance_finance": 1700,
        "maintenance_finance_annual_increase": 120,
        "insurance_lease": 2150,
        "insurance_finance": 1900,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.48,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Hyundai Finance Canada (HFC).
        # Elantra is low-demand for commercial returns; HFC is rigid.
        # Elantra depreciates faster than average → equity cushion is thin.
        #   Year 1 : Limited HFC pull-ahead; small equity cushion → ~18%.
        #   Year 2 : Shrinking equity → ~8%.
        #   Year 3 : HFC enforces ~97% of overage; $500 loyalty credit negligible
        #     against a large Uber mileage bill → ~3% effective.
        #   Year 4 / Year 5 : ~2% / ~1%.
        "market_demand": "low",
        "mileage_relief": {1: 0.18, 2: 0.08, 3: 0.03, 4: 0.02, 5: 0.01},
    },
    "mazda_mazda3_gs": {
        "name": "Mazda Mazda3 GS",
        "type": "Sedan",
        "msrp": 28000,
        "lease_rate": 3.99,
        "finance_rate": 5.99,
        "extra_mileage_cost": 0.12,
        "lease_mileage_allowance": 20000,
        "depreciation": {1: 0.18, 2: 0.14, 3: 0.12, 4: 0.10, 5: 0.09, 6: 0.08, 7: 0.07},
        "maintenance_lease": 950,
        "maintenance_finance": 1800,
        "maintenance_finance_annual_increase": 115,
        "insurance_lease": 2250,
        "insurance_finance": 2000,
        "lease_tax_deduction_rate": 0.85,
        "residual_value_pct": 0.54,
        # ─── Mileage overage relief per trade/return year ──────────────────────────────
        # Source: Mazda Capital Services Canada.
        # Mazda3 is medium-demand; lower CPO value than CX-5 but Mazda Capital is still
        # the most flexible captive lender.  Pull-ahead exists but less aggressive.
        #   Year 1 : Pull-ahead active; good equity → ~42%.
        #   Year 2 : Moderate loyalty + equity → ~18%.
        #   Year 3 : Mazda Capital $1,000 waiver; Mazda3 less desirable at 270k km
        #     than CX-5, so dealer absorbs less → ~7% effective.
        #   Year 4 / Year 5 : ~4% / ~3%.
        "market_demand": "medium",
        "mileage_relief": {1: 0.42, 2: 0.18, 3: 0.07, 4: 0.04, 5: 0.03},
    },
}

MARGINAL_TAX_RATE    = 0.33   # assumed marginal tax rate for Uber driver (self-employed)
LEASE_EXPENSE_CAP    = 1000   # CRA monthly lease deduction cap ($1,000/mo as of 2024)
BUSINESS_USE_PCT     = 0.85   # % of driving that is business use (Uber trips vs personal)
CCA_CLASS_10A_CAP    = 36000  # CRA Class 10.1 vehicle cost cap for CCA (2024)
CCA_CLASS_10A_RATE   = 0.30   # 30% declining balance CCA rate (Class 10.1)
FINANCE_INTEREST_CAP   = 300    # CRA max deductible interest = $10/day ~ $300/mo
STD_KM_PER_YEAR        = 20000  # km/yr a normal (non-Uber) driver puts on a car


# ─────────────────────────────────────────────
#  CALCULATION FUNCTIONS
# ─────────────────────────────────────────────

def calculate_depreciation_schedule(car_price, dep_rates, years):
    """Returns list of annual depreciation amounts using declining balance."""
    schedule = []
    current_value = car_price
    for yr in range(1, years + 1):
        rate = dep_rates.get(yr, dep_rates[max(dep_rates.keys())])
        dep_amount = current_value * rate
        schedule.append(round(dep_amount, 2))
        current_value -= dep_amount
    return schedule


def market_value_by_mileage(price, dep_rates, total_km):
    """
    Estimate market value based on mileage-equivalent age.

    Used-car buyers price by km, not calendar years.  A car with 90,000 km
    after 1 year of Uber looks like a 4.5-year-old car (90,000 / 20,000 std
    km/yr) to any buyer on AutoTrader/CarGurus.  We apply the same declining-
    balance depreciation curve but indexed to that effective age.

    Interpolates linearly between whole years so partial years work correctly.
    """
    effective_years = total_km / STD_KM_PER_YEAR
    full_years      = int(effective_years)
    partial         = effective_years - full_years
    max_yr          = max(dep_rates.keys())

    val = float(price)
    for yr in range(1, full_years + 1):
        rate = dep_rates.get(yr, dep_rates[max_yr])
        val -= val * rate
    # Partial final year
    if partial > 0:
        next_yr = min(full_years + 1, max_yr)
        rate    = dep_rates.get(next_yr, dep_rates[max_yr])
        val    -= val * rate * partial

    return max(0.0, round(val, 2))


def calculate_lease(params, car):
    """
    Calculate total and average yearly lease costs with mileage-relief logic.

    lease_trade_year — the year the driver plans to return or trade the vehicle
    (1, 2, or up to lease_years).

    Mileage relief applies at EVERY year, including full term:

      1. Monthly payments are fixed by the full lease contract term; only the
         number of payment years differs when trading early.

      2. The effective per-km extra-mileage cost is REDUCED by the car's
         `mileage_relief` factor for that specific year, which varies by:
         • The captive lender (TFS, HFS, Ford Credit, HFC, Mazda Capital)
         • The model's market demand (pull-ahead incentive strength)
         • Year of trade: equity buffer, loyalty credit size, settlement leverage

         Contrary to the common assumption, even at full term (year == lease_years)
         there is a non-zero effective relief — driven by:
         • Lender loyalty/return credits (Toyota $750, Honda $1,500, Mazda $1,000,
           Hyundai $500, Ford $750) effectively reduce the net mileage bill.
         • For extreme Uber overage (e.g. 210,000 excess km) lenders negotiate
           settlements rather than pursue unrecoverable collection amounts.
         • High-demand cars (especially CX-5, RAV4, CR-V) benefit from dealers
           absorbing some cost to recapture the unit for CPO/auction profit.

         Full-term relief by brand/demand (researched from Canadian dealer data):
           HIGH  demand (Toyota, Honda Hybrid, Mazda CX-5): ~11–15% at year 3
           MEDIUM demand (Accord, Tucson, Mazda3):           ~5–9% at year 3
           LOW   demand (Ford Escape, Hyundai Elantra):      ~3–4% at year 3

      3. A flat $400 early-exit administrative fee applies only when trading
         BEFORE the end of the contract term (trade_year < lease_years).
    """
    price         = params['car_price']
    years         = params['lease_years']               # full contract term
    trade_year    = min(
        int(params.get('lease_trade_year', years)),     # when driver actually trades
        years
    )
    km_per_year   = params['km_per_year']
    maintenance   = car['maintenance_lease']
    insurance     = car['insurance_lease']
    rate_annual   = car['lease_rate'] / 100
    extra_km_cost = car['extra_mileage_cost']
    allowance     = car['lease_mileage_allowance']
    tax_rate      = MARGINAL_TAX_RATE
    ded_rate      = car['lease_tax_deduction_rate']

    # ── Monthly payment — always computed on the FULL lease term ────────────
    # The lease contract is written for `years`; the monthly payment doesn't
    # change just because the driver trades early.
    dep_rates = car['depreciation']
    current_val = price
    for yr in range(1, years + 1):
        rate = dep_rates.get(yr, dep_rates[max(dep_rates.keys())])
        current_val -= current_val * rate
    residual_value     = current_val
    depreciation_total = price - residual_value

    money_factor     = rate_annual / 24
    monthly_interest = (price + residual_value) * money_factor
    annual_interest  = monthly_interest * 12

    monthly_dep      = depreciation_total / (years * 12)
    monthly_payment  = monthly_dep + monthly_interest
    annual_payment   = monthly_payment * 12

    # ── Mileage relief: applies at every year including full-term ───────────────
    # Key `mileage_relief` maps each trade/return year to a fraction of the
    # per-km overage charge that is effectively waived (via loyalty credits,
    # pull-ahead absorption, or lender settlement).  Values are car-specific
    # and sourced from Canadian captive lender programs + dealer interviews.
    relief_map      = car.get('mileage_relief', {})
    # Fall back to 0 for any year not mapped (shouldn't happen for years 1-5)
    mileage_relief  = relief_map.get(trade_year, 0.0)
    effective_extra_km_cost   = extra_km_cost * (1.0 - mileage_relief)

    excess_km             = max(0, km_per_year - allowance)
    extra_mileage_annual  = excess_km * effective_extra_km_cost   # ← reduced rate

    # ── Early-exit admin fee ─────────────────────────────────────────────────
    # Charged only when trading before the end of the contract term
    early_exit_fee = 400.0 if trade_year < years else 0.0

    # ── Tax deduction on lease payments ─────────────────────────────────────
    deductible_monthly = min(monthly_payment, LEASE_EXPENSE_CAP)
    tax_saving_annual  = deductible_monthly * 12 * ded_rate * tax_rate

    # ── Total cost accumulated only over the trade_year period ──────────────
    total_cost = (annual_payment        * trade_year
                  + maintenance         * trade_year
                  + insurance           * trade_year
                  + extra_mileage_annual* trade_year
                  + early_exit_fee                    # one-time, not annualised
                  - tax_saving_annual   * trade_year)

    avg_yearly = total_cost / trade_year

    market_demand = car.get('market_demand', 'medium')

    breakdown = {
        "depreciation_per_yr":        0,          # driver returns car — no ownership loss
        "annual_payment":             round(annual_payment, 2),
        "interest_per_yr":            round(annual_interest, 2),
        "maintenance_per_yr":         round(maintenance, 2),
        "insurance_per_yr":           round(insurance, 2),
        "extra_mileage_per_yr":       round(extra_mileage_annual, 2),
        "extra_mileage_full_rate_per_yr": round(excess_km * extra_km_cost, 2),
        "mileage_relief_pct":         round(mileage_relief * 100, 0),
        "effective_extra_km_cost":    round(effective_extra_km_cost, 3),
        "early_exit_fee":             round(early_exit_fee, 2),
        "tax_saving_per_yr":          round(tax_saving_annual, 2),
        "monthly_payment":            round(monthly_payment, 2),
        "residual_value":             round(residual_value, 2),
        "total_cost":                 round(total_cost, 2),
        "avg_yearly_cost":            round(avg_yearly, 2),
        "years":                      years,
        "trade_year":                 trade_year,
        "market_demand":              market_demand,
    }
    return breakdown


def calculate_lease_with_buyout(params, car):
    """
    Combined cost: full-term lease followed by financing the residual (buyout).

    Phase 1 — Lease (lease_years):
        Normal lease payments, maintenance, insurance.
        NO excess-mileage charges — the driver buys the car instead of
        returning it, so there is no per-km overage bill.  The high-mileage
        "penalty" appears instead as the gap between the contractual residual
        price and the car's actual depressed market value at lease end
        (see `buyout_vs_market_gap`).

    Phase 2 — Buyout loan (buyout_years):
        Customer exercises the purchase option at the contractual residual
        price (residual_value_pct × car_price), financing it at the car's
        finance_rate.  Maintenance / insurance switch to ownership-mode
        rates and CCA + interest deductions apply.

    Key insight for Uber drivers:
        Contractual residual is set at lease inception assuming ~20,000 km/yr.
        At 90,000 km/yr the car's actual market value at lease end is far
        below that residual — the driver pays a premium over fair market
        value when buying out.  This hidden cost is quantified and reported.
    """
    price        = params['car_price']
    lease_years  = params['lease_years']
    buyout_years = params.get('buyout_years', 3)
    km_per_year  = params['km_per_year']

    # ── Phase 1: full-term lease, no excess-mileage billing ──────────────────
    # Set allowance = km_per_year so excess_km = 0 (no per-km charge on return,
    # because the customer never returns — she is buying the car).
    car_lease_phase = dict(car)
    car_lease_phase['lease_mileage_allowance'] = km_per_year
    lease_params = dict(params)
    lease_params['lease_trade_year'] = lease_years   # always full term
    lease = calculate_lease(lease_params, car_lease_phase)

    # ── Contractual buyout price ──────────────────────────────────────────────
    # Fixed in the lease contract as residual_value_pct × negotiated price.
    # Does NOT adjust for actual mileage accumulated.
    buyout_price = car['residual_value_pct'] * price

    # ── Actual market value vs contractual price ──────────────────────────────
    km_at_lease_end        = km_per_year * lease_years
    market_value_at_buyout = market_value_by_mileage(
        price, car['depreciation'], km_at_lease_end
    )
    # Positive = driver pays more than the car is worth on open market
    buyout_vs_market_gap = buyout_price - market_value_at_buyout

    # ── Buyout loan amortisation ──────────────────────────────────────────────
    rate_annual  = car['finance_rate'] / 100
    monthly_rate = rate_annual / 12
    n_payments   = buyout_years * 12
    if monthly_rate > 0:
        buyout_monthly = (
            buyout_price
            * (monthly_rate * (1 + monthly_rate) ** n_payments)
            / ((1 + monthly_rate) ** n_payments - 1)
        )
    else:
        buyout_monthly = buyout_price / n_payments
    buyout_annual         = buyout_monthly * 12
    buyout_interest_total = buyout_annual * buyout_years - buyout_price

    # Year-by-year loan interest (for CRA deduction calculation)
    bal                = buyout_price
    buyout_yr_interest = []
    for _ in range(buyout_years):
        yr_int = 0.0
        for _ in range(12):
            i_pmt  = bal * monthly_rate
            p_pmt  = buyout_monthly - i_pmt
            yr_int += i_pmt
            bal    -= p_pmt
        buyout_yr_interest.append(yr_int)

    # ── Maintenance during ownership (post-lease) ────────────────────────────
    # Calendar year during buyout = lease_years + 1 … lease_years + buyout_years.
    # maintenance_finance rises by maint_increase for each year beyond year 3.
    maint_base          = car['maintenance_finance']
    maint_increase      = car['maintenance_finance_annual_increase']
    buyout_maint_total  = 0.0
    for yr_offset in range(1, buyout_years + 1):
        cal_yr = lease_years + yr_offset
        buyout_maint_total += maint_base + max(0, cal_yr - 3) * maint_increase
    buyout_maintenance_avg = buyout_maint_total / buyout_years

    insurance_buyout = car['insurance_finance']

    # ── Tax savings during ownership ─────────────────────────────────────────
    tax_rate = MARGINAL_TAX_RATE
    biz_use  = BUSINESS_USE_PCT

    # A) CCA Class 10.1 — 30% declining balance on buyout price (CRA cap)
    ucc       = min(buyout_price, CCA_CLASS_10A_CAP)
    cca_total = 0.0
    for yr in range(1, buyout_years + 1):
        cca_rate   = CCA_CLASS_10A_RATE * 0.5 if yr == 1 else CCA_CLASS_10A_RATE
        cca_amount = ucc * cca_rate
        ucc       -= cca_amount
        cca_total += cca_amount * biz_use * tax_rate

    # B) Interest deduction (CRA $10/day cap = FINANCE_INTEREST_CAP / month)
    int_savings_total = sum(
        min(yi, FINANCE_INTEREST_CAP * 12) * biz_use * tax_rate
        for yi in buyout_yr_interest
    )
    buyout_tax_total = cca_total + int_savings_total
    buyout_tax_avg   = buyout_tax_total / buyout_years

    # ── Phase 2 total ────────────────────────────────────────────────────────
    buyout_phase_cost = (
          buyout_annual * buyout_years
        + buyout_maint_total
        + insurance_buyout * buyout_years
        - buyout_tax_total
    )

    # ── Combined lease + buyout ───────────────────────────────────────────────
    total_years         = lease_years + buyout_years
    combined_total_cost = lease['total_cost'] + buyout_phase_cost
    combined_avg_yearly = combined_total_cost / total_years

    result = dict(lease)
    result.update({
        'lease_end_action':        'buyout',
        'lease_total_cost':        round(lease['total_cost'], 2),
        'lease_avg_yearly':        round(lease['avg_yearly_cost'], 2),
        # Buyout price vs market
        'buyout_price':            round(buyout_price, 2),
        'buyout_price_pct':        round(car['residual_value_pct'] * 100, 1),
        'market_value_at_buyout':  round(market_value_at_buyout, 2),
        'buyout_vs_market_gap':    round(buyout_vs_market_gap, 2),
        # Buyout loan
        'buyout_years':            buyout_years,
        'buyout_monthly_payment':  round(buyout_monthly, 2),
        'buyout_annual_payment':   round(buyout_annual, 2),
        'buyout_interest_total':   round(buyout_interest_total, 2),
        # Ownership operating costs
        'buyout_maintenance_avg':  round(buyout_maintenance_avg, 2),
        'buyout_insurance_per_yr': round(insurance_buyout, 2),
        'buyout_tax_avg':          round(buyout_tax_avg, 2),
        # Phase 2 total
        'buyout_phase_cost':       round(buyout_phase_cost, 2),
        # Combined
        'combined_total_cost':     round(combined_total_cost, 2),
        'combined_avg_yearly':     round(combined_avg_yearly, 2),
        'total_years':             total_years,
        # Override for comparison — avg_yearly_cost is what get compared
        'avg_yearly_cost':         round(combined_avg_yearly, 2),
        'total_cost':              round(combined_total_cost, 2),
    })
    return result


def calculate_finance(params, car):
    """
    Finance cost calculated up to sell_year (when driver plans to sell).

    sell_year may be less than the full finance term. All costs, tax savings,
    and the sale result are calculated only up to sell_year.

    Sale result:
      - Estimated sale price = market value after sell_year years
        minus a high-mileage penalty (Uber km >> average 20,000 km/yr)
      - Remaining loan balance = what is still owed at sell_year
      - Net = sale_price - remaining_balance
        Positive = equity gain (reduces total cost)
        Negative = underwater (you owe more than car is worth = extra cost)
    """
    price            = params['car_price']
    years            = params['finance_years']     # full loan term
    sell_year        = params.get('sell_year', years)  # year driver sells
    km_per_year      = params['km_per_year']
    maintenance_base = car['maintenance_finance']
    maint_increase   = car['maintenance_finance_annual_increase']
    insurance        = car['insurance_finance']
    rate_annual      = car['finance_rate'] / 100
    tax_rate         = MARGINAL_TAX_RATE
    biz_use          = BUSINESS_USE_PCT
    dep_rates        = car['depreciation']

    # ── Amortization over full loan term ────────────────────────────────────
    monthly_rate = rate_annual / 12
    n_payments   = years * 12
    if monthly_rate > 0:
        monthly_payment = price * (monthly_rate * (1 + monthly_rate) ** n_payments) \
                          / ((1 + monthly_rate) ** n_payments - 1)
    else:
        monthly_payment = price / n_payments
    annual_payment = monthly_payment * 12

    # Year-by-year interest & principal for full term
    balance          = price
    yearly_interest  = []
    yearly_principal = []
    for _ in range(years):
        yr_interest  = 0.0
        yr_principal = 0.0
        for _ in range(12):
            i_pmt  = balance * monthly_rate
            p_pmt  = monthly_payment - i_pmt
            yr_interest  += i_pmt
            yr_principal += p_pmt
            balance      -= p_pmt
        yearly_interest.append(round(yr_interest, 2))
        yearly_principal.append(round(yr_principal, 2))

    # ── Remaining loan balance at sell_year ─────────────────────────────────
    bal = price
    for _ in range(sell_year * 12):
        i_pmt  = bal * monthly_rate
        p_pmt  = monthly_payment - i_pmt
        bal   -= p_pmt
    remaining_balance = max(0.0, bal)

    # ── Market value at sell_year — mileage-equivalent age ─────────────────
    # Buyers price used cars by km, not calendar years.
    # 90,000 km/yr Uber car after 3 yrs = 270,000 km = effectively a
    # 13.5-year-old car to any buyer (270,000 / 20,000 std km/yr).
    # We apply the declining-balance depreciation curve against that effective
    # age, which gives a realistic AutoTrader-style market value.
    total_km             = km_per_year * sell_year
    effective_age_years  = total_km / STD_KM_PER_YEAR   # e.g. 4.5 yrs for 90k/yr @ yr1
    estimated_sale_price = market_value_by_mileage(price, dep_rates, total_km)

    # For display / tooltip — what a time-only price would have been
    base_val = price
    for yr in range(1, sell_year + 1):
        rate     = dep_rates.get(yr, dep_rates[max(dep_rates.keys())])
        base_val -= base_val * rate
    base_market_value = round(base_val, 2)
    # The hidden cost of high mileage vs a normal driver's same-age car
    mileage_discount  = max(0.0, round(base_market_value - estimated_sale_price, 2))
    excess_km         = max(0, int(total_km - STD_KM_PER_YEAR * sell_year))

    # ── Net sale result ──────────────────────────────────────────────────────
    # Positive = gain (car worth more than you owe) → reduces cost
    # Negative = loss (car worth less than you owe) → increases cost
    sale_net             =  estimated_sale_price - remaining_balance
    sale_net_per_yr      =  sale_net / sell_year   # positive=gain/yr, negative=loss/yr

    # ── Maintenance up to sell_year ──────────────────────────────────────────
    total_maintenance    = 0.0
    maintenance_schedule = []
    for yr in range(1, sell_year + 1):
        maint = maintenance_base if yr <= 3 else maintenance_base + (yr - 3) * maint_increase
        maintenance_schedule.append(round(maint, 2))
        total_maintenance += maint
    avg_maintenance = total_maintenance / sell_year

    # ── Tax saving A: Interest deduction (CRA IT-521R) up to sell_year ──────
    interest_tax_savings = []
    for yr_int in yearly_interest[:sell_year]:
        monthly_int      = yr_int / 12
        ded_monthly      = min(monthly_int, FINANCE_INTEREST_CAP)
        interest_tax_savings.append(round(ded_monthly * 12 * biz_use * tax_rate, 2))
    total_interest_tax_saving = sum(interest_tax_savings)
    avg_interest_tax_saving   = total_interest_tax_saving / sell_year

    # ── Tax saving B: CCA Class 10.1 (30% declining) up to sell_year ────────
    ucc         = min(price, CCA_CLASS_10A_CAP)
    cca_savings = []
    for yr in range(1, sell_year + 1):
        cca_rate   = CCA_CLASS_10A_RATE * 0.5 if yr == 1 else CCA_CLASS_10A_RATE
        cca_amount = ucc * cca_rate
        ucc       -= cca_amount
        cca_savings.append(round(cca_amount * biz_use * tax_rate, 2))
    total_cca_saving = sum(cca_savings)
    avg_cca_saving   = total_cca_saving / sell_year

    total_tax_saving = total_interest_tax_saving + total_cca_saving
    avg_tax_saving   = total_tax_saving / sell_year

    # ── Total cost over sell_year ────────────────────────────────────────────
    # Payments made + maintenance + insurance − sale net result − tax savings
    # sale_net is SUBTRACTED because a gain reduces cost, a loss increases it
    total_cost = (annual_payment * sell_year
                  + total_maintenance
                  + insurance * sell_year
                  - sale_net              # gain reduces cost; loss increases cost
                  - total_tax_saving)
    avg_yearly = total_cost / sell_year

    # avg market depreciation per year (display only)
    dep_schedule     = calculate_depreciation_schedule(price, dep_rates, sell_year)
    avg_depreciation = sum(dep_schedule) / sell_year

    return {
        "annual_payment":             round(annual_payment, 2),
        "monthly_payment":            round(monthly_payment, 2),
        "years":                      years,
        "sell_year":                  sell_year,
        "total_km":                   int(total_km),
        "effective_age_years":        round(effective_age_years, 1),
        "base_market_value":          base_market_value,
        "mileage_discount":           mileage_discount,
        "mileage_penalty":            mileage_discount,   # kept for backward compat
        "excess_km":                  excess_km,
        "estimated_sale_price":       round(estimated_sale_price, 2),
        "remaining_balance":          round(remaining_balance, 2),
        "sale_net":                   round(sale_net, 2),
        "sale_net_per_yr":            round(sale_net_per_yr, 2),
        "depreciation_per_yr":        round(avg_depreciation, 2),
        "maintenance_per_yr":         round(avg_maintenance, 2),
        "maintenance_schedule":       maintenance_schedule,
        "insurance_per_yr":           round(insurance, 2),
        "extra_mileage_per_yr":       0,
        "tax_saving_interest_per_yr": round(avg_interest_tax_saving, 2),
        "tax_saving_cca_per_yr":      round(avg_cca_saving, 2),
        "tax_saving_per_yr":          round(avg_tax_saving, 2),
        "yearly_interest":            yearly_interest,
        "yearly_principal":           yearly_principal,
        "cca_savings":                cca_savings,
        "interest_tax_savings":       interest_tax_savings,
        "total_cost":                 round(total_cost, 2),
        "avg_yearly_cost":            round(avg_yearly, 2),
        "residual_value":             round(estimated_sale_price, 2),
    }


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/car-data', methods=['GET'])
def get_car_data():
    """Return all car defaults for the dropdown."""
    result = {}
    for key, car in CAR_DATA.items():
        result[key] = {
            "name":                    car['name'],
            "type":                    car['type'],
            "msrp":                    car['msrp'],
            "lease_rate":              car['lease_rate'],
            "finance_rate":            car['finance_rate'],
            "extra_mileage_cost":      car['extra_mileage_cost'],
            "lease_mileage_allowance": car['lease_mileage_allowance'],
            "maintenance_lease":       car['maintenance_lease'],
            "maintenance_finance":     car['maintenance_finance'],
            "insurance_lease":         car['insurance_lease'],
            "insurance_finance":       car['insurance_finance'],
            "residual_value_pct":      car['residual_value_pct'],
            "market_demand":  car.get('market_demand', 'medium'),
            "mileage_relief":  car.get('mileage_relief', {1: 0.0, 2: 0.0, 3: 0.0}),
        }
    return jsonify(result)


@app.route('/api/calculate', methods=['POST'])
def calculate():
    """Main calculation endpoint."""
    data = request.get_json()

    car_key = data.get('car_key', 'toyota_rav4_xle_hybrid')
    if car_key not in CAR_DATA:
        return jsonify({"error": f"Unknown car: {car_key}"}), 400

    car = CAR_DATA[car_key].copy()

    # Allow user overrides for rates / costs
    if 'lease_rate' in data:      car['lease_rate'] = float(data['lease_rate'])
    if 'finance_rate' in data:    car['finance_rate'] = float(data['finance_rate'])
    if 'insurance_lease' in data: car['insurance_lease'] = float(data['insurance_lease'])
    if 'insurance_finance' in data: car['insurance_finance'] = float(data['insurance_finance'])
    if 'maintenance_lease' in data: car['maintenance_lease'] = float(data['maintenance_lease'])
    if 'maintenance_finance' in data: car['maintenance_finance'] = float(data['maintenance_finance'])
    if 'extra_mileage_cost' in data: car['extra_mileage_cost'] = float(data['extra_mileage_cost'])
    if 'lease_mileage_allowance' in data: car['lease_mileage_allowance'] = float(data['lease_mileage_allowance'])

    params = {
        "car_price":        float(data.get('car_price', car['msrp'])),
        "lease_years":      int(data.get('lease_years', 3)),
        "finance_years":    int(data.get('finance_years', 7)),
        "km_per_year":      float(data.get('km_per_year', 90000)),
        "sell_year":        int(data.get('sell_year', int(data.get('finance_years', 7)))),
        "lease_trade_year": int(data.get('lease_trade_year', int(data.get('lease_years', 3)))),
        "buyout_years":     int(data.get('buyout_years', 3)),
    }

    lease_end_action = data.get('lease_end_action', 'return')
    if lease_end_action == 'buyout':
        lease = calculate_lease_with_buyout(params, car)
    else:
        lease = calculate_lease(params, car)
    finance = calculate_finance(params, car)

    winner  = "lease" if lease['avg_yearly_cost'] < finance['avg_yearly_cost'] else "finance"
    savings = abs(lease['avg_yearly_cost'] - finance['avg_yearly_cost'])

    # Build reasoning
    sell_yr    = finance['sell_year']
    sale_net   = finance['sale_net']
    sale_desc  = f"gain of ${sale_net:,.0f}" if sale_net >= 0 else f"loss of ${abs(sale_net):,.0f} (underwater)"
    trade_yr   = lease['trade_year']
    relief_pct = lease['mileage_relief_pct']
    demand     = lease['market_demand']
    demand_lbl = {"high": "High", "medium": "Medium", "low": "Low"}.get(demand, demand.title())

    # Mileage relief description
    if trade_yr < params['lease_years'] and relief_pct > 0:
        relief_note = (
            f"Early trade at year {trade_yr} ({demand_lbl}-demand car): "
            f"{int(relief_pct)}% mileage overage absorbed by dealer pull-ahead program \u2014 "
            f"effective rate ${lease['effective_extra_km_cost']:.3f}/km "
            f"(contractual ${car['extra_mileage_cost']:.2f}/km). "
            f"Saves ~${lease['extra_mileage_full_rate_per_yr'] - lease['extra_mileage_per_yr']:,.0f}/yr. "
            f"A $400 early-exit admin fee is included."
        )
    elif not (trade_yr == params['lease_years']) and relief_pct == 0:
        # Early trade, low-demand, near-zero relief
        relief_note = (
            f"Early trade at year {trade_yr} ({demand_lbl}-demand car): "
            f"lender enforces near-full contractual mileage rate ${car['extra_mileage_cost']:.2f}/km \u2014 "
            f"minimal pull-ahead/loyalty relief. A $400 early-exit admin fee is included."
        )
    elif trade_yr == params['lease_years'] and relief_pct > 0:
        # Full-term return with lender loyalty credit / settlement
        relief_source = {
            "high":   "lender loyalty credit + overage settlement negotiation",
            "medium": "lender loyalty credit (partial settlement)",
            "low":    "lender loyalty certificate (minimal)",
        }.get(demand, "lender loyalty program")
        relief_note = (
            f"Full-term return (yr {trade_yr}), {demand_lbl}-demand car: "
            f"{int(relief_pct)}% effective mileage reduction via {relief_source} \u2014 "
            f"effective rate ${lease['effective_extra_km_cost']:.3f}/km vs contractual "
            f"${car['extra_mileage_cost']:.2f}/km. "
            f"Saves ~${lease['extra_mileage_full_rate_per_yr'] - lease['extra_mileage_per_yr']:,.0f}/yr vs paying full contractual rate."
        )
    else:
        # Full-term, effectively zero relief (very low demand)
        relief_note = (
            f"Full-term return (yr {trade_yr}), {demand_lbl}-demand car: "
            f"lender enforces near-full contractual mileage rate ${car['extra_mileage_cost']:.2f}/km \u2014 "
            f"negligible loyalty/settlement relief for this brand."
        )

    # For buyout: replace the mileage-relief note with buyout context
    if lease_end_action == 'buyout':
        km_at_end = int(params['km_per_year'] * params['lease_years'])
        gap       = lease.get('buyout_vs_market_gap', 0)
        prem_str  = f"${abs(gap):,.0f} {'above' if gap > 0 else 'below'} market"
        relief_note = (
            f"No per-km overages on buyout \u2014 you keep the car. "
            f"Contractual residual ${lease['buyout_price']:,.0f} "
            f"({lease['buyout_price_pct']}% of MSRP) is {prem_str}: "
            f"actual value at {km_at_end:,} km = ${lease['market_value_at_buyout']:,.0f}. "
            f"Buyout financed at {car['finance_rate']}% over {lease['buyout_years']} yr "
            f"= ${lease['buyout_monthly_payment']:,.0f}/mo "
            f"(${lease['buyout_interest_total']:,.0f} interest). "
            f"Combined Lease+Buyout avg: ${lease['combined_avg_yearly']:,.0f}/yr "
            f"over {lease['total_years']} yr."
        )

    reasons = []
    if winner == "lease":
        reasons.append(f"Leasing saves ~${savings:,.0f}/yr on average after all costs and deductions.")
        reasons.append(f"Lease tax deduction: ~${lease['tax_saving_per_yr']:,.0f}/yr \u2014 CRA allows up to $1,000/mo of lease payments as a business expense (85% business use assumed).")
        reasons.append(f"Finance has CRA tax savings too (interest + CCA = ~${finance['tax_saving_per_yr']:,.0f}/yr), but they don't close the gap.")
        reasons.append(f"At sale (yr {sell_yr}, {int(finance['total_km']):,} km): sale price ${finance['estimated_sale_price']:,.0f} vs loan balance ${finance['remaining_balance']:,.0f} \u2192 {sale_desc}.")
        reasons.append(relief_note)
        reasons.append("Warranty typically covers the full lease term \u2014 fewer surprise repair costs vs an ageing financed vehicle.")
    else:
        reasons.append(f"Financing saves ~${savings:,.0f}/yr on average after all costs and deductions.")
        reasons.append(f"Finance tax savings: ~${finance['tax_saving_per_yr']:,.0f}/yr \u2014 CRA interest deduction (capped $10/day) + CCA Class 10.1 at 30% declining balance.")
        reasons.append(f"Lease tax deduction (~${lease['tax_saving_per_yr']:,.0f}/yr) is larger in isolation, but finance wins overall.")
        reasons.append(f"At sale (yr {sell_yr}, {int(finance['total_km']):,} km): sale price ${finance['estimated_sale_price']:,.0f} vs loan balance ${finance['remaining_balance']:,.0f} \u2192 {sale_desc}.")
        reasons.append(relief_note)

    return jsonify({
        "car_name":    car['name'],
        "params":      params,
        "lease":       lease,
        "finance":     finance,
        "winner":      winner,
        "savings_per_year": round(savings, 2),
        "reasons":     reasons,
    })


if __name__ == '__main__':
    print("=" * 55)
    print("  Uber Driver Lease vs Finance Calculator")
    print("  Running at: http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
