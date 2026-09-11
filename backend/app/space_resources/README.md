# AURORA Space Resource Program

In-situ resource utilisation (ISRU) built on **real-world TRL values** — no
fictional capabilities.  Every technology carries recorded TRL, hardware
spec, energy budget, risk profile, economics, and development timeline.

## Modules

| Module | Capability |
|---|---|
| `maturity.py` | TRL enum (1–9), `ResourceTechnology`, `TRLRegistry` with 8 registered technologies |
| `extraction.py` | Simplified physics-based extractors: water ice, oxygen from regolith, metals, sintered construction material |
| `isru.py` | `ISRUPlant` coordinating components + storage tanks with boiloff |
| `economics.py` | Earth-launch vs in-situ cost comparison, break-even, portfolio analysis |
| `prospecting.py` | `ProspectSite` scoring, `ProspectingPlanner` survey/extraction plans |
| `roadmap.py` | 8-phase program roadmap (Earth testing → asteroid resources) |

## Registered technologies (TRL registry)

| Technology | Resource | TRL | Body |
|---|---|---|---|
| lunar water electrodialysis | water | 3 (Proof of Concept) | Moon |
| lunar water ferrovolatiles | water | 3 | Moon |
| lunar oxygen (ilmenite reduction) | oxygen | 2 (Concept) | Moon |
| Mars oxygen (MOXIE-derived SOX electrolysis) | oxygen | 6 (Prototype — heritage from Perseverance) | Mars |
| asteroid water (thermal desorption) | water | 2 | Asteroid |
| asteroid metals (electrorefining) | metals | 2 | Asteroid |
| sintered regolith bricks | construction material | 4 (Lab validated) | Moon |
| LOX/LH2 propellant | propellant | 5 (Relevant environment) | Moon |

## Example

```python
from app.space_resources.maturity import register_default_technologies
from app.space_resources.isru import ISRUPlant, ISRUComponent, StorageTank
from app.space_resources.extraction import WaterIceExtractor

registry = register_default_technologies()
moxie = registry.get("mars_moxygen")
print(moxie.trl.value, moxie.development_readiness)

plant = ISRUPlant(max_power_w=500.0)
plant.add_component(ISRUComponent("water-ext", WaterIceExtractor(efficiency=0.5, power_w=80.0)))
plant.add_tank(StorageTank("water", capacity_kg=100.0))
plant.start_all()
plant.run_cycle(hours=24.0)
print(plant.inventory(), plant.total_energy_wh)
```

## Design honesty

Extraction yields are **power-capped and feedstock-capped** — a plant cannot
produce water from nothing.  Offline plants produce nothing.  Economics
compare real order-of-magnitude launch costs against modelled in-situ costs,
so the program can show when (and when **not**) ISRU pays off.