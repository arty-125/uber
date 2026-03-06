#!/usr/bin/env python3
"""
Uber Driver Lease vs Finance Calculator
Backend server with Flask - performs all cost calculations
"""

from flask import Flask, request, jsonify, send_from_directory
import json
import os

app = Flask(__name__, static_folder='.')

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
    """Calculate total and average yearly lease costs."""
    price         = params['car_price']
    years         = params['lease_years']
    km_per_year   = params['km_per_year']
    maintenance   = car['maintenance_lease']
    insurance     = car['insurance_lease']
    rate_annual   = car['lease_rate'] / 100
    extra_km_cost = car['extra_mileage_cost']
    allowance     = car['lease_mileage_allowance']
    tax_rate      = MARGINAL_TAX_RATE
    ded_rate      = car['lease_tax_deduction_rate']

    # Derive residual value from the depreciation schedule for the exact lease term.
    # This means a 1-yr lease correctly uses ~80% residual, 3-yr ~59%, 5-yr ~47%,
    # instead of the fixed 52% that was calibrated only for 3-yr leases.
    dep_rates = car['depreciation']
    current_val = price
    for yr in range(1, years + 1):
        rate = dep_rates.get(yr, dep_rates[max(dep_rates.keys())])
        current_val -= current_val * rate
    residual_value     = current_val
    depreciation_total = price - residual_value
    # Internal only — used for monthly payment math. Driver has ZERO ownership
    # depreciation on a lease: the car is returned, no value is lost by the driver.
    _payment_dep_per_yr = depreciation_total / years

    # Money factor / interest on average outstanding balance
    money_factor     = rate_annual / 24
    monthly_interest = (price + residual_value) * money_factor
    annual_interest  = monthly_interest * 12

    # Monthly lease payment (depreciation + interest component)
    monthly_dep      = depreciation_total / (years * 12)
    monthly_payment  = monthly_dep + monthly_interest
    annual_payment   = monthly_payment * 12

    # Extra mileage (Uber drivers exceed standard allowance significantly)
    excess_km        = max(0, km_per_year - allowance)
    extra_mileage_annual = excess_km * extra_km_cost

    # Tax deduction on lease payments (CRA cap: $800/mo → $1,000/mo as of 2024)
    deductible_monthly = min(monthly_payment, LEASE_EXPENSE_CAP)
    tax_saving_annual  = deductible_monthly * 12 * ded_rate * tax_rate

    total_cost = (annual_payment * years
                  + maintenance * years
                  + insurance * years
                  + extra_mileage_annual * years
                  - tax_saving_annual * years)

    avg_yearly = total_cost / years

    breakdown = {
        "depreciation_per_yr": 0,  # Always 0 for lease — driver returns car, absorbs no ownership loss
        "annual_payment":      round(annual_payment, 2),  # full lease cost (dep + interest baked in)
        "interest_per_yr":     round(annual_interest, 2),
        "maintenance_per_yr":  round(maintenance, 2),
        "insurance_per_yr":    round(insurance, 2),
        "extra_mileage_per_yr":round(extra_mileage_annual, 2),
        "tax_saving_per_yr":   round(tax_saving_annual, 2),
        "monthly_payment":     round(monthly_payment, 2),
        "residual_value":      round(residual_value, 2),
        "total_cost":          round(total_cost, 2),
        "avg_yearly_cost":     round(avg_yearly, 2),
        "years":               years,
    }
    return breakdown


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
            "name":                  car['name'],
            "type":                  car['type'],
            "msrp":                  car['msrp'],
            "lease_rate":            car['lease_rate'],
            "finance_rate":          car['finance_rate'],
            "extra_mileage_cost":    car['extra_mileage_cost'],
            "lease_mileage_allowance": car['lease_mileage_allowance'],
            "maintenance_lease":     car['maintenance_lease'],
            "maintenance_finance":   car['maintenance_finance'],
            "insurance_lease":       car['insurance_lease'],
            "insurance_finance":     car['insurance_finance'],
            "residual_value_pct":    car['residual_value_pct'],
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
        "car_price":    float(data.get('car_price', car['msrp'])),
        "lease_years":  int(data.get('lease_years', 3)),
        "finance_years":int(data.get('finance_years', 7)),
        "km_per_year":  float(data.get('km_per_year', 90000)),
        "sell_year":    int(data.get('sell_year', int(data.get('finance_years', 7)))),
    }

    lease   = calculate_lease(params, car)
    finance = calculate_finance(params, car)

    winner  = "lease" if lease['avg_yearly_cost'] < finance['avg_yearly_cost'] else "finance"
    savings = abs(lease['avg_yearly_cost'] - finance['avg_yearly_cost'])

    # Build reasoning
    sell_yr   = finance['sell_year']
    sale_net  = finance['sale_net']
    sale_desc = f"gain of ${sale_net:,.0f}" if sale_net >= 0 else f"loss of ${abs(sale_net):,.0f} (underwater)"

    reasons = []
    if winner == "lease":
        reasons.append(f"Leasing saves ~${savings:,.0f}/yr on average after all costs and deductions.")
        reasons.append(f"Lease tax deduction: ~${lease['tax_saving_per_yr']:,.0f}/yr — CRA allows up to $1,000/mo of lease payments as a business expense (85% business use assumed).")
        reasons.append(f"Finance has CRA tax savings too (interest + CCA = ~${finance['tax_saving_per_yr']:,.0f}/yr), but they don't close the gap.")
        reasons.append(f"At sale (yr {sell_yr}, {int(finance['total_km']):,} km): sale price ${finance['estimated_sale_price']:,.0f} vs loan balance ${finance['remaining_balance']:,.0f} → {sale_desc}.")
        if params['km_per_year'] > 60000:
            reasons.append(f"⚠️ High mileage: at {params['km_per_year']:,.0f} km/yr you pay ~${lease['extra_mileage_per_yr']:,.0f}/yr in extra km fees on the lease. Negotiate a higher mileage cap.")
        reasons.append("Warranty typically covers the full lease term — fewer surprise repair costs vs an ageing financed vehicle.")
    else:
        reasons.append(f"Financing saves ~${savings:,.0f}/yr on average after all costs and deductions.")
        reasons.append(f"Finance tax savings: ~${finance['tax_saving_per_yr']:,.0f}/yr — CRA interest deduction (capped $10/day) + CCA Class 10.1 at 30% declining balance.")
        reasons.append(f"Lease tax deduction (~${lease['tax_saving_per_yr']:,.0f}/yr) is larger in isolation, but finance wins overall.")
        reasons.append(f"At sale (yr {sell_yr}, {int(finance['total_km']):,} km): sale price ${finance['estimated_sale_price']:,.0f} vs loan balance ${finance['remaining_balance']:,.0f} → {sale_desc}.")
        if params['km_per_year'] > 80000:
            reasons.append(f"At {params['km_per_year']:,.0f} km/yr, avoiding per-km lease overage fees (~${lease['extra_mileage_per_yr']:,.0f}/yr) is a key advantage of financing.")

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
