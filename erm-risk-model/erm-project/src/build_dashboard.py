"""
build_dashboard.py

Renders data/risk_metrics.json into a single self-contained HTML dashboard
(docs/index.html). Charts are hand-rolled SVG/JS -- no external libraries or
CDN calls -- so the file works fully offline. No server required: open it
directly in a browser.

Run:
    python3 src/build_dashboard.py
Writes:
    docs/index.html
"""
import json

with open("data/risk_metrics.json") as f:
    M = json.load(f)


def money(x, cents=False):
    return f"${x:,.0f}" if not cents else f"${x:,.2f}"


def moneyM(x):
    return f"${x / 1_000_000:,.1f}M"


contrib = M["risk_contribution_pct"]
contrib_labels = list(contrib.keys())
contrib_values = [round(v * 100, 1) for v in contrib.values()]

avg_by_cat = M["avg_loss_by_category"]
avg_labels = list(avg_by_cat.keys())
avg_values = [round(v, 0) for v in avg_by_cat.values()]

stress = M["stress_scenarios"]
stress_labels = list(stress.keys())
stress_values = [round(v, 0) for v in stress.values()]

var_labels = ["VaR 95%", "VaR 99%", "VaR 99.5%"]
var_values = [round(M["var_95"], 0), round(M["var_99"], 0), round(M["var_995"], 0)]

hist_counts = M["histogram"]["counts"]
hist_edges = M["histogram"]["edges"]

DATA_JS = f"""
const CONTRIB_LABELS = {json.dumps(contrib_labels)};
const CONTRIB_VALUES = {json.dumps(contrib_values)};
const AVG_LABELS = {json.dumps(avg_labels)};
const AVG_VALUES = {json.dumps(avg_values)};
const STRESS_LABELS = {json.dumps(stress_labels)};
const STRESS_VALUES = {json.dumps(stress_values)};
const VAR_LABELS = {json.dumps(var_labels)};
const VAR_VALUES = {json.dumps(var_values)};
const HIST_COUNTS = {json.dumps(hist_counts)};
const HIST_EDGES = {json.dumps(hist_edges)};
const VAR_995 = {M['var_995']};
const CVAR_995 = {M['cvar_995']};
const EXPECTED_LOSS = {M['expected_annual_loss']};
"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{M['company_name']} — Enterprise Risk &amp; Economic Capital Model</title>
<style>
  .viz-root {{
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page-plane:     #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --gridline:       #e1e0d9;
    --baseline:       #c3c2b7;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6; /* blue */
    --series-2:       #eb6834; /* orange */
    --series-3:       #1baf7a; /* aqua */
    --critical:        #d03b3b;
    --good:           #0ca30c;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme: dark;
      --surface-1:      #1a1a19;
      --page-plane:     #0d0d0d;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --gridline:       #2c2c2a;
      --baseline:       #383835;
      --border:         rgba(255,255,255,0.10);
      --series-1:       #3987e5;
      --series-2:       #d95926;
      --series-3:       #199e70;
      --critical:        #e66767;
      --good:           #0ca30c;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page-plane);
    color: var(--text-primary);
  }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 40px 24px 80px; }}
  header {{ margin-bottom: 32px; }}
  header .eyebrow {{
    font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--series-1);
  }}
  header h1 {{ font-size: 26px; margin: 6px 0 8px; letter-spacing: -0.01em; }}
  header p {{ color: var(--text-secondary); font-size: 15px; max-width: 720px; line-height: 1.5; margin: 0; }}
  .callout {{
    margin-top: 16px; padding: 12px 16px; border: 1px solid var(--border); border-radius: 10px;
    background: var(--surface-1); color: var(--text-secondary); font-size: 13px; line-height: 1.5;
  }}
  .callout b {{ color: var(--text-primary); }}

  .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }}
  .kpi {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 18px;
  }}
  .kpi .label {{ font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }}
  .kpi .value {{ font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }}
  .kpi .value.good {{ color: var(--good); }}
  .kpi .sub {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}

  .panel {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px 22px 8px; margin-bottom: 24px;
  }}
  .panel h2 {{ font-size: 15px; margin: 0 0 2px; }}
  .panel .desc {{ font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }}
  .chart-box {{ position: relative; height: 260px; }}
  .chart-box.tall {{ height: 300px; }}
  .chart-box svg {{ width: 100%; height: 100%; overflow: visible; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}

  .bar-rect {{ transition: opacity 0.1s; }}
  .bar-rect:hover {{ opacity: 0.8; }}
  .hover-col {{ fill: transparent; }}
  .hover-col:hover {{ fill: var(--text-primary); opacity: 0.04; }}
  .axis-label {{ fill: var(--text-muted); font-size: 10.5px; }}
  .grid-line {{ stroke: var(--gridline); stroke-width: 1; }}
  .baseline-line {{ stroke: var(--baseline); stroke-width: 1; }}
  .marker-line {{ stroke-width: 1.5; stroke-dasharray: 4 3; }}
  .marker-label {{ font-size: 10px; font-weight: 600; }}

  .legend {{ display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; flex-wrap: wrap; }}
  .legend .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .legend .line {{ display: inline-block; width: 12px; height: 2px; margin-right: 6px; vertical-align: middle; }}

  .tooltip {{
    position: fixed; pointer-events: none; z-index: 50;
    background: var(--text-primary); color: var(--surface-1);
    font-size: 12px; padding: 6px 10px; border-radius: 8px;
    opacity: 0; transform: translate(-50%, -110%); transition: opacity 0.08s;
    white-space: nowrap; line-height: 1.5;
  }}
  .tooltip b {{ font-weight: 700; }}
  .tooltip .row {{ display: flex; align-items: center; gap: 6px; }}
  .tooltip .sw {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}

  .methodology {{ font-size: 14px; line-height: 1.65; color: var(--text-secondary); }}
  .methodology h3 {{ font-size: 14px; color: var(--text-primary); margin: 18px 0 6px; }}
  .methodology code {{ background: var(--page-plane); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-size: 12.5px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--gridline); }}
  th {{ color: var(--text-muted); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }}
  td {{ color: var(--text-secondary); }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

  footer {{ margin-top: 32px; font-size: 12px; color: var(--text-muted); text-align: center; }}

  @media (max-width: 720px) {{
    .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="viz-root">
<div class="wrap">

  <header>
    <div class="eyebrow">Enterprise Risk Management (ERM)</div>
    <h1>{M['company_name']} — Economic Capital &amp; Risk Model</h1>
    <p>
      A Monte Carlo enterprise risk model ({M['n_simulated_years']:,} simulated years) aggregating
      market, credit, and operational risk into a total annual loss distribution — the core analysis
      behind economic capital planning and ORSA-style (Own Risk and Solvency Assessment) risk reporting.
    </p>
    <div class="callout">
      <b>About the company:</b> Meridian Industrial Corp is a fictional mid-size company built to host
      this model (see <code>src/simulate_risk.py</code>). Each risk category uses a real, named
      methodology — a fat-tailed market shock, the single-factor Vasicek model underlying the Basel II
      credit capital formula, and the Loss Distribution Approach used for Basel operational-risk capital
      — with market and credit risk deliberately correlated through a shared systemic factor, since
      treating them as independent is a well-known way real risk models understate tail risk.
    </div>
  </header>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Expected annual loss</div>
      <div class="value">{moneyM(M['expected_annual_loss'])}</div>
      <div class="sub">mean of simulated years</div>
    </div>
    <div class="kpi">
      <div class="label">VaR 99.5%</div>
      <div class="value">{moneyM(M['var_995'])}</div>
      <div class="sub">1-in-200-year loss level</div>
    </div>
    <div class="kpi">
      <div class="label">Economic capital required</div>
      <div class="value">{moneyM(M['economic_capital'])}</div>
      <div class="sub">VaR 99.5% minus expected loss</div>
    </div>
    <div class="kpi">
      <div class="label">Capital adequacy ratio</div>
      <div class="value good">{M['capital_adequacy_ratio']:.2f}x</div>
      <div class="sub">{moneyM(M['available_capital'])} available / VaR 99.5%</div>
    </div>
  </div>

  <div class="panel">
    <h2>Total annual loss distribution</h2>
    <p class="desc">{M['n_simulated_years']:,} simulated years of total enterprise loss (market + credit + operational), with expected loss and the VaR / CVaR 99.5% tail markers.</p>
    <div class="legend">
      <span><span class="line" style="background:var(--text-muted)"></span>Expected loss</span>
      <span><span class="line" style="background:var(--series-2)"></span>VaR 99.5%</span>
      <span><span class="line" style="background:var(--critical)"></span>CVaR 99.5%</span>
    </div>
    <div class="chart-box tall" id="histChart"></div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2>Tail risk contribution</h2>
      <p class="desc">Share of loss, on average, in the worst 0.5% of simulated years — by risk category.</p>
      <div class="chart-box" id="contribChart"></div>
    </div>
    <div class="panel">
      <h2>VaR by confidence level</h2>
      <p class="desc">How the loss threshold rises moving further into the tail.</p>
      <div class="chart-box" id="varChart"></div>
    </div>
  </div>

  <div class="panel">
    <h2>Stress test scenarios</h2>
    <p class="desc">Deterministic named scenarios, reported alongside the probabilistic VaR/CVaR figures — standard practice in ORSA and board-level risk reporting.</p>
    <div class="chart-box" id="stressChart"></div>
  </div>

  <div class="panel">
    <h2>Risk summary (table view)</h2>
    <table>
      <thead><tr><th>Metric</th><th class="num">Value</th></tr></thead>
      <tbody>
        <tr><td>Expected annual loss</td><td class="num">{money(M['expected_annual_loss'])}</td></tr>
        <tr><td>VaR 95%</td><td class="num">{money(M['var_95'])}</td></tr>
        <tr><td>VaR 99%</td><td class="num">{money(M['var_99'])}</td></tr>
        <tr><td>VaR 99.5% (1-in-200-year)</td><td class="num">{money(M['var_995'])}</td></tr>
        <tr><td>CVaR 99.5% (tail average beyond VaR)</td><td class="num">{money(M['cvar_995'])}</td></tr>
        <tr><td>Economic capital required</td><td class="num">{money(M['economic_capital'])}</td></tr>
        <tr><td>Available capital</td><td class="num">{money(M['available_capital'])}</td></tr>
        <tr><td>Capital adequacy ratio</td><td class="num">{M['capital_adequacy_ratio']:.2f}x</td></tr>
      </tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Methodology</h2>
    <div class="methodology">
      <h3>Three risk categories, one aggregate loss distribution</h3>
      <p>
        <b>Market risk</b> is modeled as a fat-tailed (Student-t) shock applied to a market-exposed
        portfolio, capturing the well-documented fact that market returns have heavier tails than a
        normal distribution implies. <b>Credit risk</b> uses the single-factor Gaussian (Vasicek) model
        that underlies the Basel II IRB credit capital formula: each counterparty's default is driven by
        a shared systemic factor plus idiosyncratic risk, so defaults cluster in bad years rather than
        occurring independently. <b>Operational risk</b> uses the Loss Distribution Approach (LDA) from
        Basel operational-risk capital: a Poisson process for how often loss events happen, combined with
        a lognormal severity distribution for how large they are when they do.
      </p>
      <h3>Why market and credit risk are correlated here</h3>
      <p>
        Market and credit risk share a common systemic factor, so credit losses rise in the same
        simulated years that markets fall — the same pattern seen in real credit cycles (e.g. 2008).
        Modeling each risk category independently is a common way enterprise risk models understate tail
        risk, so that correlation is built in explicitly rather than assumed away. Operational risk is
        kept independent of the systemic factor as a documented simplification.
      </p>
      <h3>Risk metrics</h3>
      <p>
        <b>VaR (Value at Risk)</b> at a given confidence level is the loss not expected to be exceeded
        that percentage of the time — VaR 99.5% is the "1-in-200-year" loss. <b>CVaR</b> (Conditional
        VaR, also called Tail VaR) is the average loss <i>given</i> that losses exceed VaR — it captures
        how bad the tail gets, not just where it starts. <b>Economic capital</b> is defined as VaR 99.5%
        minus expected loss (the "unexpected loss" buffer a company needs to hold), and the
        <b>capital adequacy ratio</b> compares available capital against that requirement.
      </p>
      <h3>Stack</h3>
      <p>numpy / scipy for the Monte Carlo simulation and distributions, pandas for aggregation, and a small hand-rolled SVG chart layer for this dashboard (no external JS libraries). See <code>README.md</code> for how to reproduce every number on this page from scratch.</p>
    </div>
  </div>

  <div id="tooltip" class="tooltip"></div>

  <footer>Built with numpy, scipy &amp; pandas — see the repo README for methodology and how to re-run this analysis.</footer>

</div>
</div>

<script>
{DATA_JS}

// ---------------------------------------------------------------------
// Small dependency-free SVG chart engine (bar + histogram, with hover
// tooltips). No CDN / external library required.
// ---------------------------------------------------------------------
const css = getComputedStyle(document.querySelector('.viz-root'));
const col = (name) => css.getPropertyValue(name).trim();
const tooltipEl = document.getElementById('tooltip');
const fmtMoney = (v) => '$' + Math.round(v).toLocaleString();
const fmtMoneyM = (v) => '$' + (v / 1_000_000).toFixed(1) + 'M';

function showTooltip(x, y, html) {{
  tooltipEl.innerHTML = html;
  tooltipEl.style.left = x + 'px';
  tooltipEl.style.top = y + 'px';
  tooltipEl.style.opacity = '1';
}}
function hideTooltip() {{ tooltipEl.style.opacity = '0'; }}

function svgEl(tag, attrs) {{
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}}

function roundedTopBarPath(x, y, w, h, r) {{
  r = Math.min(r, w / 2, Math.max(h, 0));
  if (h <= 0) return `M ${{x}} ${{y + h}} h ${{w}} v 0 h ${{-w}} Z`;
  return `M ${{x}} ${{y + h}}
          L ${{x}} ${{y + r}}
          Q ${{x}} ${{y}} ${{x + r}} ${{y}}
          L ${{x + w - r}} ${{y}}
          Q ${{x + w}} ${{y}} ${{x + w}} ${{y + r}}
          L ${{x + w}} ${{y + h}}
          Z`;
}}

function renderBarChart(containerId, labels, values, {{ unit = '', color = null, colors = null }} = {{}}) {{
  const container = document.getElementById(containerId);
  const W = container.clientWidth || 480, H = container.clientHeight || 260;
  const padL = 8, padR = 8, padT = 12, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxVal = Math.max(...values) * 1.15;
  const barColor = color || col('--series-1');
  const n = labels.length;
  const slot = plotW / n;
  const barW = Math.min(slot * 0.5, 70);

  const svg = svgEl('svg', {{ viewBox: `0 0 ${{W}} ${{H}}`, preserveAspectRatio: 'none' }});

  for (let i = 0; i <= 3; i++) {{
    const gy = padT + plotH - (plotH * i / 3);
    svg.appendChild(svgEl('line', {{ x1: padL, x2: W - padR, y1: gy, y2: gy, class: 'grid-line' }}));
  }}
  svg.appendChild(svgEl('line', {{ x1: padL, x2: W - padR, y1: padT + plotH, y2: padT + plotH, class: 'baseline-line' }}));

  labels.forEach((label, i) => {{
    const cx = padL + slot * i + slot / 2;
    const barH = (values[i] / maxVal) * plotH;
    const bx = cx - barW / 2, by = padT + plotH - barH;
    const thisColor = colors ? colors[i] : barColor;

    const path = svgEl('path', {{ d: roundedTopBarPath(bx, by, barW, barH, 4), class: 'bar-rect', fill: thisColor }});
    svg.appendChild(path);

    const txt = svgEl('text', {{ x: cx, y: H - 8, 'text-anchor': 'middle', class: 'axis-label' }});
    txt.textContent = label;
    svg.appendChild(txt);

    const hover = svgEl('rect', {{ x: padL + slot * i, y: padT, width: slot, height: plotH, class: 'hover-col' }});
    hover.addEventListener('mousemove', (e) => {{
      const shownVal = unit === '$' ? fmtMoney(values[i]) : unit === '%' ? values[i] + '%' : values[i];
      showTooltip(e.clientX, e.clientY, `<div class="row"><span class="sw" style="background:${{thisColor}}"></span><b>${{label}}</b>: ${{shownVal}}</div>`);
    }});
    hover.addEventListener('mouseleave', hideTooltip);
    svg.appendChild(hover);
  }});

  container.innerHTML = '';
  container.appendChild(svg);
}}

function renderHistogram(containerId, counts, edges, markers) {{
  const container = document.getElementById(containerId);
  const W = container.clientWidth || 480, H = container.clientHeight || 300;
  const padL = 8, padR = 8, padT = 16, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxCount = Math.max(...counts) * 1.1;
  const minEdge = edges[0], maxEdge = edges[edges.length - 1];
  const xFor = (v) => padL + ((v - minEdge) / (maxEdge - minEdge)) * plotW;

  const svg = svgEl('svg', {{ viewBox: `0 0 ${{W}} ${{H}}`, preserveAspectRatio: 'none' }});

  for (let i = 0; i <= 3; i++) {{
    const gy = padT + plotH - (plotH * i / 3);
    svg.appendChild(svgEl('line', {{ x1: padL, x2: W - padR, y1: gy, y2: gy, class: 'grid-line' }}));
  }}
  svg.appendChild(svgEl('line', {{ x1: padL, x2: W - padR, y1: padT + plotH, y2: padT + plotH, class: 'baseline-line' }}));

  const barColor = col('--series-1');
  counts.forEach((c, i) => {{
    const x0 = xFor(edges[i]), x1 = xFor(edges[i + 1]);
    const barH = (c / maxCount) * plotH;
    const by = padT + plotH - barH;
    const rect = svgEl('rect', {{ x: x0, y: by, width: Math.max(x1 - x0 - 1, 0), height: barH, fill: barColor, class: 'bar-rect', opacity: 0.85 }});
    svg.appendChild(rect);

    const hover = svgEl('rect', {{ x: x0, y: padT, width: Math.max(x1 - x0, 1), height: plotH, class: 'hover-col' }});
    hover.addEventListener('mousemove', (e) => {{
      showTooltip(e.clientX, e.clientY, `<div>${{fmtMoneyM(edges[i])}} – ${{fmtMoneyM(edges[i+1])}}</div><div><b>${{c.toLocaleString()}}</b> years</div>`);
    }});
    hover.addEventListener('mouseleave', hideTooltip);
    svg.appendChild(hover);
  }});

  // axis ticks (5 evenly spaced money labels)
  for (let i = 0; i <= 4; i++) {{
    const v = minEdge + (maxEdge - minEdge) * (i / 4);
    const txt = svgEl('text', {{ x: xFor(v), y: H - 8, 'text-anchor': 'middle', class: 'axis-label' }});
    txt.textContent = fmtMoneyM(v);
    svg.appendChild(txt);
  }}

  // marker lines (expected loss, VaR, CVaR)
  markers.forEach(m => {{
    const mx = xFor(m.value);
    if (mx < padL || mx > W - padR) return;
    svg.appendChild(svgEl('line', {{ x1: mx, x2: mx, y1: padT, y2: padT + plotH, class: 'marker-line', stroke: m.color }}));
  }});

  container.innerHTML = '';
  container.appendChild(svg);
}}

function renderAll() {{
  renderBarChart('contribChart', CONTRIB_LABELS, CONTRIB_VALUES, {{ unit: '%', colors: [col('--series-1'), col('--series-2'), col('--series-3')] }});
  renderBarChart('varChart', VAR_LABELS, VAR_VALUES, {{ unit: '$', color: col('--series-2') }});
  renderBarChart('stressChart', STRESS_LABELS, STRESS_VALUES, {{ unit: '$', color: col('--critical') }});
  renderHistogram('histChart', HIST_COUNTS, HIST_EDGES, [
    {{ value: EXPECTED_LOSS, color: col('--text-muted') }},
    {{ value: VAR_995, color: col('--series-2') }},
    {{ value: CVAR_995, color: col('--critical') }},
  ]);
}}

renderAll();
let resizeTimer;
window.addEventListener('resize', () => {{
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(renderAll, 150);
}});
</script>
</body>
</html>
"""

with open("docs/index.html", "w") as f:
    f.write(HTML)

print("Wrote docs/index.html")
