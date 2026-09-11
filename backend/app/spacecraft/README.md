# AURORA Spacecraft — CubeSat Technology Demonstrator

Software architecture and mission design for AURORA's first spacecraft: a
**3U CubeSat (AURORA-1)**. Every subsystem is a Python class with a
deterministic simulation backend, so the full mission can be rehearse-able
offline before any hardware exists.

## Mission design (AURORA-1)

| Item | Design |
|---|---|
| **Class** | 3U CubeSat (~34×10×10 cm, ~4 kg) |
| **Mission objective** | Technology demonstrator: validate AURORA's software-defined EO + AI edge pipeline in orbit, and prove our own flight software / ground segment / operations loop (the real deliverable for later orbital-servicing, autonomous and deep-space programs). |
| **Orbit** | LEO, sun-synchronous, ~400–550 km, 97.4° inclination |
| **Payload** | Multispectral push-broom imager (MS/red-green-blue-NIR, 3 m GSD at 500 km), 20° FOV; on-board NDVI/NDWI/EVI product generation (reuses AURORA `app/ai` pipelines) |
| **Power** | 6 body-mounted triple-junction GaAs solar panels (~80 cm² total), ~6.6 V LiFePO4 10 Wh battery; steady load ≤2 W, transmit peak ≤5 W |
| **Communications** | UHF 435 MHz downlink @ 9.6 kbps (AX.25), VHF 145 MHz uplink; OpenLST-class radio model; store-and-forward |
| **Computing** | CubeSat OBC (ARM Cortex-M7-class MCU for CDH) + Linux-class coprocessor (Raspberry-Pi-CM-class) for payload/AI; flight software in `app/spacecraft/fsw.py` |
| **Attitude control (ADCS)** | 3-axis: magnetometer + coarse sun sensor, 3 reaction wheels, 3 magnetorquers; detumble + sun-pointing; ~1° pointing |
| **Thermal** | Body-mounted radiators, survival heaters, 2 W heater budget, passive thermal control; operating range −10…+50 °C |
| **Flight software** | Priority task scheduler, FDIR (fault detection/isolation/recovery), safe-mode, command execution, telemetry collection |
| **Ground segment** | 1 primary UHF/VHF ground station, mission ops console, telemetry dashboard, data relay to AURORA backend |
| **Telemetry** | Housekeeping every 10 s (power/thermal/ADCS/FSW health), payload metadata on image capture, store-and-forward buffering |
| **Mission operations** | Timeline: launch → LEOP (t+1 h) → commissioning (t+7 d) → nominal ops (30 d+) → extended ops → deorbit |
| **Testing** | Full capacity: unit tests (offline), HIL (hardware-in-the-loop) via same interfaces, mission simulation (`SpacecraftSimulator`), thermal-vac/ESS on flight hardware |
| **Regulatory** | ITU frequency coordination, NOAA/NTIA license (if US) or local spectrum authority, launch manifest via rideshare (e.g., SpaceX/CAPS), COSPAR registration, debris-mitigation plan (deorbit <25 yr) |

## Development stages

1. **Stage 0 — Simulation/architecture (this repo):** orbital sim, eclipse,
   power/thermal/ADCS models, FSW scheduler + FDIR, mission timeline. *No
   hardware dependency.*
2. **Stage 1 — Bench validation:** run the same `tick()`-driven interfaces
   against bench hardware (ADCS sensor board, battery board, SDR radio) via
   hardware backends.
3. **Stage 2 — HIL:** wire real flight components into `SpacecraftSimulator`;
   validate FDIR and safe-mode on hardware.
4. **Stage 3 — Flight build:** clean-room flight software (C + Rust on MCU,
   subset keeps Python sim as reference), thermal-vac + ESS qualification,
   flight and spare units.
5. **Stage 4 — Launch & ops:** manifest, LEOP, commissioning, 6–12 mo
   nominal ops, deorbit.

## Components

| Module | Subsystem |
|---|---|
| `adcs.py` | Attitude determination (sun sensor, magnetometer) + control (reaction wheels, magnetorquers) |
| `power.py` | Solar panels, battery SOC/voltage, power budget |
| `thermal.py` | Lumped-capacitance thermal model, heater control |
| `comms.py` | Radio transceiver, AX.25 packets, link budget, ground station |
| `payload.py` | Multispectral imager, storage, download scheduling |
| `fsw.py` | Task scheduler, FDIR fault manager, telemetry collection |
| `mission.py` | Mission timeline/phases, ground segment, telemetry downlink |
| `simulation.py` | `SpacecraftSimulator` — full mission rehearsal |

## Usage (offline mission rehearsal)

```python
from app.spacecraft.simulation import SpacecraftSimulator

sim = SpacecraftSimulator(altitude_km=500.0, inclination_deg=97.4)
history = sim.run(duration_s=86400)  # one full orbit
for state in history[:5]:
    print(state.to_dict())
```

## Path to orbital servicing / autonomous spacecraft / deep space

The interfaces deliberately do **not** hardcode LEO constants:
- `OrbitalState` propagator can be swapped for a deep-space estimator.
- `RadioTransceiver` + store-and-forward pre-implements interplanetary DTN-style
  relay (see `app/multiplanetary/telemetry.py`).
- `FaultManager` FDIR semantics (safe-mode, watchdogs) are identical for
  crewed-capable and deep-space missions.
- `ImagingPayload` + `app/ai` pipelines already produce the EO/AI products
  needed for rendezvous/approach sensing later.