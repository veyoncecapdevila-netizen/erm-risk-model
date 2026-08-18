# Meridian Industrial Corp — Enterprise Risk & Economic Capital Model

A Monte Carlo enterprise risk model that aggregates market, credit, and operational risk into a
total annual loss distribution, then derives the risk metrics (VaR, CVaR, economic capital) used
in real corporate ERM and ORSA-style (Own Risk and Solvency Assessment) risk reporting.

![Dashboard preview](assets/dashboard-preview.png)

**To view it live:** open `docs/index.html` directly in a browser, or enable GitHub Pages for
this repo (Settings → Pages → Deploy from branch → `main` / `docs`) for a shareable link.

## What this is

This project is built specifically around Corporate Finance & ERM — the actuarial practice area
focused on managing risk across an entire organization, not just pricing individual insurance
policies. It answers the questions an ERM function actually has to answer: how much could this
company plausibly lose in a bad year, how much capital does it need to hold to survive that, and
is it currently holding enough?

Three risk categories are modeled, each with a real, named methodology:

- **Market risk** — a fat-tailed (Student-t) shock applied to a market-exposed portfolio, since
  real market returns have heavier tails than a normal distribution captures.
- **Credit risk** — the single-factor Gaussian (**Vasicek**) model that underlies the Basel II IRB
  credit capital formula: each counterparty's default is driven by a shared systemic factor plus
  idiosyncratic risk, so defaults cluster together in bad years rather than happening independently.
- **Operational risk** — the **Loss Distribution Approach (LDA)** used in Basel operational-risk
  capital: a Poisson process for how *often* loss events happen, combined with a lognormal
  severity distribution for how *large* they are.

Market and credit risk deliberately share a systemic factor, so credit losses rise in the same
simulated years markets fall — the same pattern seen in real credit cycles (e.g. 2008). Modeling
risk categories as independent is a well-known way enterprise risk models understate tail risk, so
that correlation is built in explicitly rather than assumed away. Operational risk is kept
independent of the systemic factor as a documented simplification (it's driven more by internal
control failures than macro conditions).

## About the company

Meridian Industrial Corp is a fictional mid-size company built to host this model — see
[`src/simulate_risk.py`](src/simulate_risk.py) for every assumption (portfolio size, counterparty
count, default probabilities, loss severities). The methodology is real and standard; the company
itself is a stand-in so the model has something concrete to run against.

## Repo structure

```
├── src/
│   ├── simulate_risk.py     # Monte Carlo simulation across all 3 risk categories
│   └── build_dashboard.py   # renders docs/index.html from the simulation output
├── data/
│   ├── simulated_years.csv    # one row per simulated year, loss by category (generated)
│   └── risk_metrics.json      # VaR/CVaR, economic capital, stress tests (generated)
├── docs/
│   └── index.html            # the interactive dashboard (self-contained, no build step)
├── assets/
│   └── dashboard-preview.png
└── requirements.txt
```

## Running it

```bash
pip install -r requirements.txt
python3 src/simulate_risk.py      # writes data/simulated_years.csv, data/risk_metrics.json
python3 src/build_dashboard.py    # writes docs/index.html
```

Then open `docs/index.html` in any browser — it's a single self-contained file (charts are
hand-rolled SVG/JS, no external libraries or CDN calls), so it works completely offline too.

## Key results

| Metric | Value |
|---|---|
| Simulated years | 200,000 |
| Expected annual loss | ~$7.1M |
| VaR 99.5% (1-in-200-year loss) | ~$35.9M |
| CVaR 99.5% (average loss beyond VaR) | ~$43.3M |
| Economic capital required | ~$28.8M |
| Available capital | $50.0M |
| Capital adequacy ratio | 1.39x |

In the worst 0.5% of simulated years, market risk drives ~49% of total losses, credit risk ~31%,
and operational risk ~20% — a reasonably balanced tail, which is itself a useful finding: no single
risk category dominates, so capital planning has to account for all three rather than focusing on
just the biggest one. The named stress scenarios (a 2008-style credit crisis, a major single
operational loss event, a +300bps rate shock) are reported alongside the probabilistic VaR/CVaR
figures, matching how real ORSA and board-level risk reports typically present both a probabilistic
view and specific deterministic "what if" scenarios side by side.

## Stack

numpy / scipy (Monte Carlo simulation, Student-t / lognormal / normal distributions), pandas
(aggregation), and a small dependency-free SVG charting layer for the dashboard.

---

*Suggested resume line: "Built a Monte Carlo enterprise risk model (200,000 simulated years)
aggregating market, credit, and operational risk — using the Vasicek single-factor credit model
and Basel Loss Distribution Approach — to derive VaR/CVaR, economic capital requirements, and
stress-test scenarios, presented in an interactive risk dashboard."*
