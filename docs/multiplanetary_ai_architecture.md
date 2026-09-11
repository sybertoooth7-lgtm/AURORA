# AURORA Multi-Planetary AI Architecture

This document describes how the same AI stack evolves from an Earth-bound
system to a deep-space autonomous agent.  The layered design keeps authority,
safety, and human oversight explicit, because a platform operating at
13+ minutes of light-time delay cannot rely on ground commands for
time-critical decisions.

## 1. Design principles

1. **Fail-safe is a system invariant.**  Safe mode must always be reachable,
   even if every layer malfunctions.  The stack checks battery, temperature,
   radiation, and watchdog health *before* running any layer logic.
2. **Layers propose, mission control disposes.**  Most layers generate
   `Action` proposals.  `MissionControlLayer` applies the autonomy budget and
   safety interlocks; irreversible or out-of-budget actions become
   `REQUEST_AUTHORIZATION` for human oversight.
3. **Autonomy grows with distance, shrinks with risk.**  The autonomy level
   the stack may use is derived from round-trip delay, then degraded by low
   battery, high temperature, or loss of contact.
4. **Simulated telemetry is never presented as real.**  Every sensor module
   carries a `simulated` flag; environment constants are injected from
   `PlanetaryEnvironment` config per body.

## 2. The seven layers

```
1. mission_control     authority, autonomy budget, safety interlocks, oversight
2. scientific          hypotheses, survey plans, science value
3. robotics            fleet coordination, agent dispatch, teleop bridge
4. navigation          terrain-aware path planning + obstacle avoidance
5. resource_management inventory, allocation, energy budget
6. infrastructure      ISRU plants, power grid, comms network, habitats
7. human_assistance    advisories, verification, plain-language reporting
```

`AuroraStack.step(ctx)` runs every layer once per decision cycle, folds
proposals through mission control, and returns a `StackDecision`
(`approved_actions`, `pending_authorization`, `rejected_actions`,
`safe_mode_active`).

## 3. Communication-delay evolution

| Destination | One-way latency | Autonomous ops budget | Mission flavor |
|---|---|---|---|
| Earth LEO | ~3 ms | seconds | Real-time teleop possible |
| Moon | ~1.3 s | ~1 minute | Near-real-time commanding |
| Mars | ~13 min | hours–days | Preloaded playbooks, onboard GNC |
| Jupiter | ~45 min | weeks | Long-horizon autonomy |
| Deep space / ISRU outposts | hours | indefinite | Fully self-governing with fail-safe |

`CommsDelayModel.for_target(body)` derives the recommended autonomy level and
maximum uninterrupted autonomous operation time.  `DisconnectedOpsManager`
executes preloaded `MissionPlaybook`s during blackout and forces safe mode if
autonomy time or battery runs out.

## 4. Safety architecture (`ops/`)

- **`fail_safe.FailSafeController`** monitors health signals (battery,
  temperature, etc.) with *safe* and *caution* thresholds, watchdog reset
  counts, and command-loss timeouts.  Crossing a boundary calls a user
  callback (e.g. to trigger plant shutdown) and switches the stack to safe
  mode.
- **`radiation.RadiationEnvironment` + `RadHardStrategy`** models GCR + SPE
  dose per body, tracks cumulative component dose, applies ECC/watchdog
  mitigation, and flags end-of-life components.
- **`security.CyberSecurityLayer`** signs commands with HMAC-SHA256, rejects
  replays via a nonce window, enforces rate limits, and validates flight
  configuration integrity before any new phase of autonomy is enabled.

## 5. Evolution path

```
Earth rover ──► Lunar lander/rover ──► Mars surface ops ──► Asteroid hopper
     │               │                      │                    │
   same APIs      + radiation          + comms delay        + fully autonomous
                 + ISRU power        + disconnected ops       + resource economy
```

New per-body properties (gravity, atmosphere, day length, radiation) are
added **only** in `simulation.py` / `ops/radiation.py` config.  Navigation,
perception, autonomy, and the layer stack do not change.

## 6. Where the code lives

- Layers & orchestrator: `backend/app/multiplanetary/layers/`
- Ops: `backend/app/multiplanetary/ops/`
- Low-level motion/perception/sim: `backend/app/multiplanetary/`
- Space-resource program: `backend/app/space_resources/` (see
  `docs/space_resources_program.md`)
- Tests: `backend/tests/multiplanetary/` (layers, ops, systems),
  `backend/tests/space_resources/`