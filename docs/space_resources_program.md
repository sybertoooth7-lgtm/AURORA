# AURORA Space Resource Program

A realistic ISRU program: turn lunar/Mars/asteroid resources into water,
oxygen, propellant, metals, and construction materials.  Built on real TRL
values and honest economics — the program shows when extraction pays off
and when it does not.

## Core honesty rule

- Every technology in the TRL registry carries a real-world readiness level.
  `mars_moxygen` is TRL 6 (MOXIE heritage on Perseverance).  Asteroid
  electrorefining is TRL 2 (concept).  Nothing is post-dated.
- Extraction models are **power-capped and feedstock-capped**: a 100 W plant
  cannot produce 500 kg/day; offline plants produce nothing.
- Economics use order-of-magnitude launch costs ($/kg to LEO, lunar surface,
  Mars surface) and compare in-situ cost per kg.  Break-even analysis shows
  the mass at which ISRU beats shipping from Earth.

## 1. Technology readiness registry (`maturity.py`)

Stores per-technology: TRL, mass, power, production rate, risk profile
(technical/schedule/cost/reliability), timeline (development + test +
deployment years), target body, and dependencies.

| ID | Resource | TRL | Body | Prod. rate | Timeline (yrs) |
|---|---|---|---|---|---|
| `lunar_water_electrodialysis` | water | 3 | Moon | 0.5 kg/day | 9 |
| `lunar_water_ferrovolatiles` | water | 3 | Moon | 0.8 kg/day | 9.5 |
| `lunar_oxygen_rwire` | oxygen | 2 | Moon | 0.3 kg/day | 10 |
| `mars_moxygen` | oxygen | 6 | Mars | 0.12 kg/day | 5 |
| `asteroid_water_heating` | water | 2 | Asteroid | 0.2 kg/day | 11 |
| `asteroid_metals_electrorefining` | metals | 2 | Asteroid | 0.15 kg/day | 13 |
| `sintered_regolith_brick` | construction | 4 | Moon | 2.0 kg/day | 7 |
| `propellant_lox_lh2` | propellant | 5 | Moon | 0.5 kg/day | 10 |

`TRLRegistry` uses real-world intent: registering a technology whose
dependencies are absent raises `ValueError`.

## 2. Extraction process models (`extraction.py`)

Each extractor maps power and feedstock into production and waste:

- `WaterIceExtractor` — regolith moisture fraction caps yield.
- `OxygenFromRegolith` — regolith oxygen fraction caps yield.
- `MetalExtractor` — metal fraction caps yield.
- `ConstructionMaterialSinterer` — direct feedstock→brick conversion at
  fixed efficiency.

All extractors return `ExtractionResult` with `yield_fraction` and
`specific_energy_kwh_per_kg` so competing designs can be compared.

## 3. ISRU plant simulation (`isru.py`)

`ISRUPlant` coordinates components and storage tanks:

- power budget (`available_power_w` prevents overdraw)
- per-cycle production routed into `StorageTank`s
- cryogenic boiloff per day per tank
- cumulative energy and production history

## 4. Economics (`economics.py`)

- `DeliveryCostProfile`: Earth-launch, lunar-delivery, Mars-delivery, and
  in-situ cost per kg by resource (water, oxygen, metals, propellant,
  construction material).
- `InfrastructureAsset`: capital cost, cost per kg produced, break-even mass.
- `EconomicsModel.cost_analysis()`: savings vs Earth launch.
- `break_even_analysis()`: the production mass/days an asset must produce to
  recover its capital cost.

Example orders of magnitude (modelled, not flight bids):

| Resource | Earth launch $/kg | In-situ $/kg |
|---|---|---|
| water | 100k | 50k |
| oxygen | 80k | 40k |
| metals | 120k | 60k |
| propellant | 90k | 45k |

## 5. Prospecting (`prospecting.py`)

`ProspectSite` scores candidate sites by resource viability, terrain
accessibility, solar power, and thermal environment.

`ProspectingPlanner`:
- `ranked_sites()` — best-value-first site ordering.
- `generate_survey_plan()` — orbital reconnaissance → surface sampling →
  resource assessment sequence.
- `generate_extraction_plan()` — flags `proceed_with_extraction` only when a
  site's value score clears the bar; otherwise demands more prospecting.

## 6. Program roadmap (`roadmap.py`)

Eight phases, each with milestones, success criteria, critical-path flags,
risk notes, and cost:

| # | Phase | Focal outcome |
|---|---|---|
| 1 | EARTH_TESTING | Validate water extraction on regolith simulant, TRL 3→5 |
| 2 | LUNAR_PROSPECTING | Robotic lander confirms water ice at PSR |
| 3 | LUNAR_PILOT_PLANT | 0.5 kg/day water extraction demo |
| 4 | LUNAR_PRODUCTION | LOX/LH2 propellant depot, sintered landing pad |
| 5 | MARS_PRECURSOR | MOXIE-derived O2 production |
| 6 | MARS_PRODUCTION | Propellant for return ascent vehicle |
| 7 | ORBITAL_INFRASTRUCTURE | Cislunar depot, in-space manufacturing |
| 8 | ASTEROID_RESOURCES | C/M-type asteroid water + metals |

`ProgramRoadmap.program_summary()` aggregates milestone count, total cost,
total duration, and critical-path count; `technology_dependency_graph()`
shows which technologies feed each milestone.

## 7. Verification

```
backend/tests/space_resources/test_isru.py
backend/tests/multiplanetary/test_ops.py       # failsafe + security + radiation
```