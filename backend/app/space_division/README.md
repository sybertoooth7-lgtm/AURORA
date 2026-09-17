# AURORA Space Division

```
Space Division
├── Earth Observation
├── Satellite Constellation
├── CubeSat Technology
└── Deep Space Infrastructure (Future)
```

Four items on AURORA's org chart. Only one of them was actually missing
from the codebase -- this package exists to say which is which, and to
hold the one that's new.

## Earth Observation → `app/ai/` + `app/satellite/`

Already built, and not dormant like the rest of this file -- it's the
actual live product. `app/ai/` has twelve analysis pipelines (vegetation
stress, land change, wildfire risk, flood monitoring, environmental,
infrastructure, insurance index, robotics inspection, anomaly detection,
computer vision). `app/satellite/` is the real Sentinel-2 integration via
the Copernicus Data Space Ecosystem. Nothing to add here.

## CubeSat Technology → `app/spacecraft/`

Already built: AURORA-1, a full 3U CubeSat simulation (ADCS, power,
thermal, comms, payload, flight software) with its own 5-stage
development plan. See `app/spacecraft/README.md`. Nothing to add here
either.

## Satellite Constellation → `constellation.py` (this package)

The actual gap. Managing *one* spacecraft (`app/spacecraft/`) and
managing a *fleet* of them are genuinely different problems -- fleet
composition (which orbital plane and phase slot each satellite occupies,
a first-order revisit-time estimate for fleet-sizing) and ground-segment
contention (AURORA's plan is one primary ground station; more than one
satellite can want it at the same time) don't exist until there's more
than one spacecraft to manage. `Constellation` and
`GroundContactScheduler` are that layer, built in the same Stage-0-
simulation spirit as everything else here: deterministic, offline-
testable, reusing `app.spacecraft.mission.ContactWindow` rather than
redefining it.

## Deep Space Infrastructure (Future) → `app/multiplanetary/` + `app/space_resources/`

Already substantially covered: `app/multiplanetary/` (navigation,
autonomy, collision avoidance, mapping, sensors, telemetry, vision) and
`app/space_resources/` (ISRU, extraction, prospecting, economics,
maturity roadmap). "(Future)" on the org chart matches where this
actually sits in AURORA's staged plan -- present as simulation code, not
meant to be live yet.

## Not wired anywhere

Like every other dormant subsystem in this repo, `constellation.py` is
real, tested code with no route, database table, or connection to real
satellites yet.
