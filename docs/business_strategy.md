# AURORA Business Strategy & Funding Plan

**Company**: AURORA — space intelligence company, incorporated in Kenya.
**Horizon**: 2026 → 2040+.
**Core belief**: A multi-planetary company is not built on unlimited funding.
It is built by *earning* Earth revenue first, then reinvesting that cash flow —
and only *staged, named* external capital — into robotics, spacecraft, orbital
infrastructure, lunar resources and deep-space exploration.

This document is a financial thesis and an operating plan, not a promise.
All figures are modelled assumptions and must be re-validated quarterly.

---

## 0. The economic thesis

1. **Earth applications** (satellite data + AI + robotics services) generate
   recurring revenue with software margins (70–85%).
2. **Robotics pays for itself on Earth first.** Field inspection robots are
   revenue-generating on day one; the same autonomy stack later transfers to
   the Moon and Mars *for free* (already simulated in `app/robotics`,
   `app/multiplanetary`).
3. **Space is financed three ways, never one:** (a) Earth cash flow,
   (b) milestone-based raises, (c) government/agency anchor contracts.
   Every future phase is **gated** on the previous phase delivering defined
   revenue or EBITDA — or on the named capital being legally committed.
4. **Honesty is a business asset.** The platform distinguishes real vs.
   simulated data everywhere; financial plans use the same discipline —
   no stage is "funded" until the money or the contract exists.

---

## 1. Target customers

Highest willingness-to-pay segments first (Kenya + East Africa), mapped to
the AURORA pipeline types already built (`vegetation_stress`, `land_change`,
`water_monitoring`, `flood_monitoring`, `wildfire_risk`, `anomaly_detection`,
`infrastructure_monitoring`, ...).

| # | Segment | Buyer | Core AURORA product | Willingness to pay |
|---|---|---|---|---|
| 1 | **Agricultural insurance** (parametric weather/crop index) | Insurers, MGAs, brokers, reinsurers | Insurance Index (NDVI/ET triggers) | Very high — pays per hectare |
| 2 | **Agro-processing & commodity exporters** (sugar, tea, coffee, horticulture) | Head of operations/sustainability | Atlas monitoring + EUDR/ESG reports | High — compliance-driven |
| 3 | **Green lending & microfinance** (climate risk scoring) | Credit risk officers | Climate risk reports per parcel | High |
| 4 | **Government agencies** (Ministry of Agriculture, Kenya Space Agency, Kenya Forest Service, water boards) | Programme directors | National monitoring dashboards | Medium-high — contracted |
| 5 | **NGOs & development programmes** (WFP, SNV, One Acre Fund, Fairtrade) | Programme M&E | Program impact monitoring | Medium |
| 6 | **Utilities & telecoms** (Kenya Power, Nairobi City Water, Safaricom) | Network O&M | Vegetation encroachment, catchment health | High |
| 7 | **Mining & construction** | Compliance | Site change detection | Medium |
| 8 | **Carbon / climate-finance developers** | MRV teams | Baseline + MRV land data | High |
| 9 | **ESG & advisory firms** | Partners | White-label data feeds | Medium |
| 10 | **Regional governments** (Uganda, Tanzania, Rwanda) | Agencies | National feeds | Medium-long |

**Y1 focus:** segments 1–3 (highest pay, shortest sales cycle via pilots).

---

## 2. Products

| Product | Description | Status / path |
|---|---|---|
| **AURORA Atlas** | Web dashboard + map UI (React/Vite frontend, `/analysis`, `/satellite`, `/ai/pipelines`) | MVP live |
| **AURORA Sentinel API** | REST + webhook programme access to analyses, alerts, reports (`/api/*`, auth + RBAC) | MVP live |
| **AURORA Insurance Index** | Parametric triggers from NDVI / land-change / flood / wildfire pipelines | Build in Y1–2 |
| **AURORA Field Robotics** | Ground/field inspection service (robotics stack: navigation, perception, control) | Prototype tested Y2, revenue Y3 |
| **AURORA Compliance & ESG** | EUDR/ESG/carbon land reports | Y2+ |

Every product honestly labels simulated vs. real data (source = demo →
`provenance = simulated`; Sentinel/Landsat → `real`).

---

## 3. Pricing

Kenya-conscious pricing in USD with indicative KES (≈ 130 KES/USD). Annual
billing discounts ~15%.

| Tier | Price | What you get |
|---|---|---|
| **Starter** | $199/mo (≈ KES 26k) | 50 analyses/mo, 1 region, dashboard, 3 months history |
| **Growth** | $499/mo (≈ KES 65k) | 250 analyses/mo, alerts + webhooks, API, teams, 12-month history |
| **Enterprise** | from $1,500/mo (≈ KES 195k) | Unlimited analyses, SLA, custom reports, RBAC, on-prem/Konza hosting, priority support |
| **Government / Institutional** | custom contracts $50k–$250k/yr | National dashboards, dedicated pipeline, capacity building |
| **Pilot** | fixed $5k–$25k | 3-month paid pilot with a named success metric; converts to a subscription |

Rule: **no free unlimited tiers in production data.** A free/1-analysis demo
exists only on honest simulated data.

---

## 4. Revenue model

| Stream | Share target (Y3+) | Notes |
|---|---|---|
| SaaS subscriptions | 60–70% | Recurring, predictable, high margin |
| Project analytics contracts | 15–25% | Government/NGO custom work |
| Professional services & training | 10% | Capacity building, onboarding |
| Data/API licensing + robotics field services | 5–15% | Grows with new products |

Target: **>70% recurring revenue by year 3**, so growth does not depend on one
deal per quarter.

---

## 5. First 10 customers (near-term target accounts)

Illustrative target accounts — *not* signed contracts. Deals are staged:
Y1 pilots first, conversions from Q3.

| # | Type | Product | Pilot size | Contract target |
|---|---|---|---|---|
| 1 | Agricultural insurer / MGA (Kenya) | Insurance Index | $10k pilot | $60k/yr |
| 2 | Horticulture exporter (Kenya) | Atlas + EUDR report | $8k pilot | $50k/yr |
| 3 | Tea/coffee processor (Kenya) | Atlas | $6k pilot | $40k/yr |
| 4 | Microfinance green-lending arm | Climate risk feed | $8k pilot | $45k/yr |
| 5 | Ministry of Agriculture programme | National dashboard | $25k contract | $120k/yr |
| 6 | Kenya Forest Service / county gov | Monitoring + wildfire | $20k contract | $90k/yr |
| 7 | NGO development programme (E. Africa) | Program M&E | $6k pilot | $60k/yr |
| 8 | Utility (catchment/vegetation) | Infrastructure monitoring | $10k pilot | $70k/yr |
| 9 | Carbon/MRV developer | Baseline + MRV | $15k pilot | $100k/yr |
| 10 | Sugar cooperative / aggregator (Western Kenya) | Field-level yield | $5k pilot | $30k/yr |

**Note:** revenue disclosures always separate "paid pilot" from "subscription".

---

## 6. Partnerships

| Partner | Purpose | Near-term action |
|---|---|---|
| **Copernicus CDSE / ESA** | Free Sentinel-1/2 data (already integrated) | Formalise as data-acknowledged use |
| **Kenya Space Agency (KSA)** | Regulatory alignment, national relevance, future ground-segment support | MoU in Y1 |
| **RCMRD** (Nairobi) | Geospatial capacity, regional reach | Data/training collaboration |
| **Universities** (UoN, JKUAT, Dedan Kimathi) | Talent, research, robotics testbed | Internships + joint projects |
| **Insurance ecosystem** (AKI/brokers, reinsurers) | Distribution for parametric products | Co-design indexing pilots |
| **Telecoms** (e.g. Safaricom) | Connectivity, M-PESA billing, field data | Explore distribution MoU |
| **KMD / water boards** | Ground-truth + early warning feeds | Data exchange |
| **Future international** (NASA/JSF-JAXA-class, multilateral finance) | Lunar/deep-space anchor funding | Pipeline from 2030+ |

---

## 7. Team (staged, Kenya-competitive salaries)

| Year | Size | Key roles added |
|---|---|---|
| Y1 (2026) | 6 | CEO/PM, CTO, 1 full-stack, 1 data scientist/ML, 1 BD, 1 finance/ops |
| Y2 (2027) | 13 | +2 ML/geospatial, 1 devops, 1 robotics/emb. engineer, 1 account manager, +1 BD, +2 support/data ops |
| Y3 (2028) | 20 | +2 ML, +1 SRE, +2 robotics (software), 1 hardware/test, +2 sales, +1 compliance |
| Y4 (2029) | 30 | CubeSat team start: +1 AOCS, +1 power/thermal, +1 FSW, +1 ground station ops; +2 robotics |
| Y5 (2030) | 45 | Constellation prep, mission ops, lunar-feasibility analyst |

Salaries benchmarked to Kenyan/East African market (not US/Silicon Valley),
with a small remote (EU/US) advisory/engineering premium.

---

## 8. Funding stages (no unlimited funding)

Each stage is only pursued when its **gating milestone** is met (see §10).

| Stage | Year | Amount | Source | Gate to raise it | Use of funds |
|---|---|---|---|---|---|
| **Pre-seed** | 2026 | $250k | Founders + Kenya/East-Africa angels + innovation grant (e.g. UK–EA ecosystem / national innovation fund) | Working MVP + pilot MoUs | Product to paid pilots, data costs, salaries |
| **Seed** | 2027 | $1.5M | Seed VC + grants, convertible-to-SAFE | ≥8 paid pilots, $100–180k revenue, 2 named accounts converted | Scale sales, Insurance Index, robotics prototype |
| **Series A** | 2028–29 | $5M | Africa/deeptech/climate-tech VC + strategic (insurer/reinsurer, ag-tech) | $700k–1M ARR, NRR > 110%, robotics field service paying customers | Field robotics product, CubeSat AURORA-1 feasibility, enterprise/regionals |
| **Series B** | 2030–32 | $15–30M | Growth VC + development finance (IFC/AfDB/FMO) + strategic | CubeSat launched or manifest, $5M revenue, B2G contracts | AURORA-1 constellation, ground segment, orbital servicing prerequisite studies |
| **Lunar / deep-space** | 2035+ | sovereign/agency | NASA/ESA/JSF-JAXA class contracts + multilateral + co-fund with flag state / KSA | Orbital asset profitable + TRL justified (see `docs/space_resources_program.md`) | Lunar ISRU feasibility → prospecting lander phases |

Non-dilutive sources counted separately: ESA Copernicus-ecosystem services,
development-programme contracts, carbon/ESG demand, government analytics
contracts, future spectrum/ground station services.

---

## 9. Operating costs (Kenya-based, USD)

| Category | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| Salaries + benefits | $140k | $360k | $620k | $1.05M | $1.55M |
| Cloud / data / AI compute | $30k | $80k | $160k | $280k | $420k |
| Office, legal, compliance, insurance | $35k | $55k | $80k | $110k | $140k |
| Marketing & sales | $15k | $60k | $120k | $180k | $240k |
| Hardware / robotics testbed | $15k | $60k | $120k | $180k | $300k |
| CubeSat AURORA-1 dev (from Series B + surplus) | – | – | – | $1.4M | $1.8M |
| **Total** | **$235k** | **$615k** | **$1.10M** | **$3.20M** | **$4.45M** |

Y4–Y5 step-up is the CubeSat milestone — budgeted only after Series B closes.

---

## 10. Five-year financial roadmap (2026–2030)

| Metric | 2026 | 2027 | 2028 | 2029 | 2030 |
|---|---|---|---|---|---|
| Customers (paid) | ~10 (mostly pilots) | 25 | 45 | 80 | 130 |
| Revenue | $25k | $180k | $700k | $2.2M | $5.0M |
| Recurring revenue share | 20% | 55% | 70% | 75% | 78% |
| EBITDA margin | −180% | −120% | −45% | −8% | +12% |
| Cash burn | $210k | $430k | $400k | $1.0M* | $0.6M* |
| Capital raised in year | $250k | $1.5M | $2.5M (A-1) | $2.5M (A-2) | $15–30M (B) |
| Robotics revenue | – | – | $40k | $260k | $800k |
| CubeSat manifest | – | – | study | build+launch prep | launch/manifest |

\* decline shows the business approaching breakeven; CubeSat capex appears in
Y4–Y5 as funded line, not core burn.

**Phase gates (the discipline that makes this credible):**
1. **Robotics scale begins only when** Earth-data EBITDA ≥ $300k/yr (or Series A is legally closed with a confirmed robotics budget line).
2. **CubeSat AURORA-1 begins only when** Series B (or named anchor contracts) are legally committed, AND robotics field service revenue ≥ $500k.
3. **Constellation/orbital infrastructure** only with an anchor tenant + concessional/export finance.
4. **Lunar ISRU feasibility** only when orbital assets are revenue-generating and a sovereign/agency partner is contracted — matching the TRL registry in `app/space_resources`.

---

## 11. Investor strategy

**Narrative:** "A space intelligence company that earns Earth revenue first."
Positioning for investors: de-risked space — demo-vs-real honesty, real
customers, real recurring cash, and a long-option on space infrastructure.

**Who to pitch (staged):**
- Pre-seed/seed 2026–27: East-African early-stage + climate-tech funds,
  East-African angel syndicates, corporate venture (insurer/ag-tech/telecom),
  innovation programmes, KSA-space-ecosystem grants.
- Series A 2028–29: Africa-focused deeptech/climate VCs, strategic investors
  (reinsurers, commodity exporters, utilities), development finance
  (FMO, IFC, AfDB early look).
- Series B 2030+ : growth VCs + development finance + sovereign-adjacent
  space funds; anchor government contracts.

**Metrics investors will track:** ARR, pilot→paid conversion, contraction/NRR,
recurring share, data-quality & validation pipeline, B2G pipeline, and the
north-star: *revenue per sq-km monitored*.

**Exit paths:** (a) strategic acquisition by a geospatial/defence/ag-insurance
platforms; (b) independence toward a multi-planetary company with sovereign
partners; horizon 7–10 years. Both require discipline on dilution: each raise
is sized to the *next* milestone, not 10 years.

**Non-dilutive amplifiers:** ESA/Copernicus-ecosystem services, development
programme M&E contracts, carbon/ESG demand, later spectrum & ground-station
revenue, KSA contracts.

---

## 12. Financing the journey Earth → deep space

```
EARTH (data + AI) ──► ROBOTICS (Earth field services) ──► CUBESAT AURORA-1
      │                        │ captured Earth income           │
      │                        └──► funds robotics-R&D            └──► imagery
      ▼                                                               │ revenue
   cash flow                                                            ▼
                                                                 ORBITAL INFRASTRUCTURE
        (anchor tenant + concessional finance, NOT self-funded)
                                                                        ▼
                                                              LUNAR RESOURCES (ISRU)
        (sovereign/agency TRL-funded phases — space_resources roadmap)
                                                                        ▼
                                                      MARS / DEEP SPACE (partnership programmes)
```

| Phase | Years | Financed by | Conditions met before starting |
|---|---|---|---|
| Earth intelligence | 2026–28 | Pre-seed + Seed + subscriptions | MVP live (done); ≥8 paid pilots |
| Robotics field service | 2027–29 | Cash flow + Series A robotics line | Earth EBITDA ≥ $300k or committed A budget |
| CubeSat AURORA-1 | 2029–30 | Series B + Earth surplus + agency contracts | Robotics revenue ≥ $500k; launch contract signed |
| Orbital infrastructure | 2031–35 | Anchor tenant + concessional/export finance | Orbital asset profitable |
| Lunar resources | 2035–40 | Sovereign/agency TRL phases (KSA/ESA/NASA-class) | Orbital profitable + TRL justified |
| Mars / deep space | 2040+ | Partnership programmes | Lunar ISRU demonstrated |

**Gold rules:**
1. Never assume unlimited funding — every line above names its source.
2. No stage starts until the previous stage's gate is *met in writing*.
3. Reinvest profit in the *next* capability, not in vanity.
4. Financial honesty mirrors data honesty: only real contracts count.

---

*Reference: AURORA integration in this repository — `docs/ARCHITECTURE.md`,
`docs/space_resources_program.md`, `docs/multiplanetary_ai_architecture.md`,
`app/space_resources/roadmap.py` (8-phase program) and
`app/capabilities.py` (capability registry).*