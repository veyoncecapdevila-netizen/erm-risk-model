"""
simulate_risk.py

Enterprise risk simulation for a fictional mid-size company ("Meridian
Industrial Corp") across three risk categories, aggregated into a total
annual loss distribution -- the core exercise behind economic capital
modeling and ORSA-style (Own Risk and Solvency Assessment) risk reporting
in corporate/enterprise risk management (ERM).

Risk categories, each using a standard, textbook methodology:

  1. MARKET RISK      -- P&L volatility on a $180M market-exposed portfolio
                          (investments + variable-rate debt), modeled with a
                          fat-tailed Student-t shock.
  2. CREDIT RISK       -- counterparty default losses across 200 customers,
                          modeled with the single-factor Gaussian (Vasicek)
                          model that underlies the Basel II IRB capital
                          formula: each counterparty's default is driven by
                          a shared systemic factor plus idiosyncratic noise.
  3. OPERATIONAL RISK  -- rare, high-severity loss events (fraud, system
                          outages, litigation), modeled with the Loss
                          Distribution Approach (LDA) used in Basel
                          operational-risk capital: Poisson frequency x
                          lognormal severity.

Market and credit risk share a common systemic factor (Z), capturing the
well-documented real-world pattern that credit losses spike in the same
years markets fall -- ignoring that correlation is a classic way
enterprise risk models understate tail risk, so it's modeled explicitly
here rather than assumed away. Operational risk is kept independent of
the systemic factor, a standard simplifying assumption (documented in the
README) since operational losses are driven by internal control failures
more than macroeconomic conditions.

Run:
    python3 src/simulate_risk.py
Writes:
    data/simulated_years.csv   -- one row per simulated year, loss by category
    data/risk_metrics.json     -- VaR/CVaR, economic capital, stress tests
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

RNG = np.random.default_rng(7)
N_YEARS = 200_000

COMPANY_NAME = "Meridian Industrial Corp"
AVAILABLE_CAPITAL = 50_000_000  # capital buffer the company holds

# --- Market risk parameters -------------------------------------------------
MARKET_EXPOSURE = 120_000_000
MARKET_VOL = 0.065          # annual volatility of the market-exposed portfolio
MARKET_T_DOF = 5           # fat tails vs. a normal distribution
MARKET_RHO = 0.35           # share of variance explained by the systemic factor

# --- Credit risk parameters (single-factor / Vasicek model) ----------------
N_COUNTERPARTIES = 350
CREDIT_RHO = 0.20           # asset correlation (typical IRB range 0.12-0.24)
BASE_PD = 0.028               # unconditional annual probability of default
LGD_MEAN, LGD_STD = 0.45, 0.15  # loss given default, Beta-distributed

# --- Operational risk parameters (Loss Distribution Approach) --------------
OPRISK_FREQ_MEAN = 3.2
OPRISK_SEV_MEDIAN = 260_000
OPRISK_SEV_SIGMA = 1.3      # lognormal shape -- controls how fat the tail is


def simulate_counterparty_exposures(rng, n=N_COUNTERPARTIES):
    # lognormal spread of exposures, mean ~$400k, ranging roughly $50k-$3M
    return rng.lognormal(mean=np.log(400_000), sigma=0.85, size=n)


def simulate(n_years=N_YEARS, rng=RNG):
    exposures = simulate_counterparty_exposures(rng)
    default_threshold = stats.norm.ppf(BASE_PD)  # Vasicek: P(A_i < threshold) = PD

    # Shared systemic factor -- drives both market and credit risk together.
    Z = rng.normal(0, 1, size=n_years)

    # --- Market risk: t-distributed shock, partly systemic -----------------
    idio_market = rng.standard_t(MARKET_T_DOF, size=n_years)
    idio_market /= idio_market.std()  # normalize to unit variance before mixing
    market_shock = np.sqrt(MARKET_RHO) * Z + np.sqrt(1 - MARKET_RHO) * idio_market
    market_return = market_shock * MARKET_VOL
    market_loss = np.clip(-market_return, 0, None) * MARKET_EXPOSURE

    # --- Credit risk: single-factor Vasicek default model ------------------
    # Each counterparty's latent asset value depends on the shared factor Z
    # plus idiosyncratic risk; a default occurs when that asset value falls
    # below the threshold implied by its unconditional PD.
    credit_loss = np.zeros(n_years)
    batch = 20_000
    for start in range(0, n_years, batch):
        end = min(start + batch, n_years)
        m = end - start
        idio = rng.normal(0, 1, size=(m, N_COUNTERPARTIES))
        asset_value = (
            np.sqrt(CREDIT_RHO) * Z[start:end, None]
            + np.sqrt(1 - CREDIT_RHO) * idio
        )
        defaulted = asset_value < default_threshold
        lgd = np.clip(rng.normal(LGD_MEAN, LGD_STD, size=(m, N_COUNTERPARTIES)), 0.05, 0.95)
        losses = defaulted * lgd * exposures[None, :]
        credit_loss[start:end] = losses.sum(axis=1)

    # --- Operational risk: Poisson frequency x lognormal severity (LDA) ----
    op_mu = np.log(OPRISK_SEV_MEDIAN)
    n_events = rng.poisson(OPRISK_FREQ_MEAN, size=n_years)
    operational_loss = np.zeros(n_years)
    for i in range(n_years):
        if n_events[i] > 0:
            operational_loss[i] = rng.lognormal(op_mu, OPRISK_SEV_SIGMA, size=n_events[i]).sum()

    total_loss = market_loss + credit_loss + operational_loss

    df = pd.DataFrame({
        "Year": np.arange(1, n_years + 1),
        "MarketLoss": market_loss.round(0),
        "CreditLoss": credit_loss.round(0),
        "OperationalLoss": operational_loss.round(0),
        "TotalLoss": total_loss.round(0),
    })
    return df


def var_cvar(losses, confidence):
    var = np.quantile(losses, confidence)
    tail = losses[losses >= var]
    cvar = tail.mean() if len(tail) else var
    return float(var), float(cvar)


def stress_scenarios(rng=RNG):
    """Named, deterministic stress tests -- the kind used in ORSA / board
    risk reporting alongside the probabilistic VaR/CVaR figures."""
    n = 20_000
    scenarios = {}

    # 2008-style credit crisis: force a severe systemic shock (Z fixed at -3)
    Z = np.full(n, -3.0)
    idio_m = rng.standard_t(MARKET_T_DOF, size=n)
    idio_m /= idio_m.std()
    m_shock = np.sqrt(MARKET_RHO) * Z + np.sqrt(1 - MARKET_RHO) * idio_m
    m_loss = np.clip(-m_shock * MARKET_VOL, 0, None) * MARKET_EXPOSURE

    exposures = simulate_counterparty_exposures(rng)
    threshold = stats.norm.ppf(BASE_PD)
    idio_c = rng.normal(0, 1, size=(n, N_COUNTERPARTIES))
    asset_value = np.sqrt(CREDIT_RHO) * Z[:, None] + np.sqrt(1 - CREDIT_RHO) * idio_c
    defaulted = asset_value < threshold
    lgd = np.clip(rng.normal(LGD_MEAN, LGD_STD, size=(n, N_COUNTERPARTIES)), 0.05, 0.95)
    c_loss = (defaulted * lgd * exposures[None, :]).sum(axis=1)
    scenarios["2008-Style Credit Crisis"] = float((m_loss + c_loss).mean())

    # Major single operational loss event (severe, ~1-in-200-year severity draw)
    severe_op = np.exp(np.log(OPRISK_SEV_MEDIAN) + OPRISK_SEV_SIGMA * stats.norm.ppf(0.995))
    baseline_op = OPRISK_FREQ_MEAN * OPRISK_SEV_MEDIAN * np.exp(0.5 * OPRISK_SEV_SIGMA ** 2)
    scenarios["Major Operational Loss Event"] = float(severe_op + baseline_op)

    # Interest-rate shock: market volatility spikes (rates +300bps regime)
    shocked_vol = MARKET_VOL * 1.8
    idio_m2 = rng.standard_t(MARKET_T_DOF, size=n)
    idio_m2 /= idio_m2.std()
    Z2 = rng.normal(0, 1, size=n)
    m_shock2 = np.sqrt(MARKET_RHO) * Z2 + np.sqrt(1 - MARKET_RHO) * idio_m2
    m_loss2 = np.clip(-m_shock2 * shocked_vol, 0, None) * MARKET_EXPOSURE
    scenarios["Rate Shock (+300bps regime)"] = float(m_loss2.mean() + baseline_op)

    return scenarios


def main():
    df = simulate()
    df.to_csv("data/simulated_years.csv", index=False)

    total = df["TotalLoss"].values
    expected_loss = float(total.mean())

    var95, cvar95 = var_cvar(total, 0.95)
    var99, cvar99 = var_cvar(total, 0.99)
    var995, cvar995 = var_cvar(total, 0.995)

    economic_capital = var995 - expected_loss
    capital_adequacy_ratio = AVAILABLE_CAPITAL / var995

    # Risk contribution: average composition of losses in the worst 0.5% of
    # simulated years (a standard practical way to decompose tail risk by
    # category without a full analytic component-VaR derivation).
    tail_mask = total >= var995
    tail_df = df[tail_mask]
    contribution = {
        "Market": float(tail_df["MarketLoss"].sum()),
        "Credit": float(tail_df["CreditLoss"].sum()),
        "Operational": float(tail_df["OperationalLoss"].sum()),
    }
    contrib_total = sum(contribution.values())
    contribution_pct = {k: v / contrib_total for k, v in contribution.items()}

    # Histogram of total loss for the dashboard (capped view for readability)
    hist_counts, hist_edges = np.histogram(total, bins=60, range=(0, np.quantile(total, 0.999)))

    metrics = {
        "company_name": COMPANY_NAME,
        "n_simulated_years": int(N_YEARS),
        "available_capital": AVAILABLE_CAPITAL,
        "expected_annual_loss": expected_loss,
        "var_95": var95, "cvar_95": cvar95,
        "var_99": var99, "cvar_99": cvar99,
        "var_995": var995, "cvar_995": cvar995,
        "economic_capital": economic_capital,
        "capital_adequacy_ratio": capital_adequacy_ratio,
        "risk_contribution_pct": contribution_pct,
        "avg_loss_by_category": {
            "Market": float(df["MarketLoss"].mean()),
            "Credit": float(df["CreditLoss"].mean()),
            "Operational": float(df["OperationalLoss"].mean()),
        },
        "histogram": {
            "counts": hist_counts.tolist(),
            "edges": hist_edges.tolist(),
        },
        "stress_scenarios": stress_scenarios(),
    }

    with open("data/risk_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"{COMPANY_NAME} -- {N_YEARS:,} simulated years")
    print(f"Expected annual loss: ${expected_loss:,.0f}")
    print(f"VaR 99.5%: ${var995:,.0f}  |  CVaR 99.5%: ${cvar995:,.0f}")
    print(f"Economic capital required: ${economic_capital:,.0f}")
    print(f"Available capital: ${AVAILABLE_CAPITAL:,.0f}  |  Capital adequacy ratio: {capital_adequacy_ratio:.2f}x")
    print("Tail (worst 0.5%) risk contribution:", {k: f"{v:.1%}" for k, v in contribution_pct.items()})
    print("Stress scenarios:", {k: f"${v:,.0f}" for k, v in metrics["stress_scenarios"].items()})


if __name__ == "__main__":
    main()
