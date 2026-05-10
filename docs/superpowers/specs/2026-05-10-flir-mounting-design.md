# FLIR Lepton Mounting Redesign

**Date:** 2026-05-10
**Status:** Draft (awaiting review)
**Supersedes:** Lepton-on-main-PCB schematic in `cad/netlist/sensors.py`

## Context

The current `cad/netlist/sensors.py` represents the FLIR Lepton 3.5 as a 14-pin 2.54 mm THT header (`J8`) on the main carrier PCB, with the lens pointing perpendicular to the board (+Z). The CadQuery assembly in `cad/assembly/build_assembly.py` stacks a synthetic Lepton can on top of `J8` with the bezel facing +Z.

Cross-arm-mounted DLR deployment requires the lens to aim at a conductor suspended ~1.5 m below the cross-arm. With the current PCB layout that means either (a) physically inverting the enclosure (incompatible with sky-facing solar panel + cellular antenna), (b) folding the optical path with a mirror (long-term degradation in field service), or (c) decoupling the Lepton's mechanical orientation from the rest of the carrier.

This design specifies (c): a tilt-adjustable Lepton daughterboard linked to the main PCB by a 14-pin FFC, plus a sealed USB-C commissioning port that gives the integrator a live thermal preview while aiming the camera.

## Decisions (converged in brainstorm 2026-05-10)

| Decision | Choice |
|---|---|
| Mount location | Cross-arm body (~1–2 m from one phase conductor) |
| Lepton orientation | Lens-down through bottom of enclosure, in overhang past cross-arm right edge |
| PCB topology | Main carrier PCB + small Lepton daughterboard, 14-pin FFC link |
| Aim mechanism | Sheet-metal bracket with M3 pivot + M3 arc-slot lockscrew, ±15° tilt range |
| Aim adjustment timing | Set once at integration, locked with lockwasher + blue locktite, no field-accessible knob |
| Commissioning interface | Sealed industrial USB-C (IP67 capped) on enclosure side wall, wired to CM4 USB2 OTG |
| IR window | Germanium, AR-coated, 8–14 µm, ~25 mm diameter, silicone-gasketed |

## Architecture

### Mechanical (cross-section)

```
                                                       solar panel (20W)
                                              ┌─────────────────────────────┐
                                              │           PV                │
                                              └─────────────────────────────┘
                                              ┌──[enclosure  IP55]─────────┐
                                              │  main PCB (CM4 + cell + pwr)│
                                              │  └ FFC J8                   │
                                              │     ╲                       │
                                              │      ╲ 14-pin FFC ribbon    │── sealed USB-C
                                              │       ╲                     │   (commissioning)
                                              │  bracket──daughterboard──── │
                                              │    pivot   tilted -15°      │
                                              │            ▼                │
                                              │     [Molex 32-pin socket]   │
                                              │     [Lepton can]            │
                                              │     [chrome bezel] ──────── │── Ge IR window
                                              └─────────────────────────────┘
            ┌──[cross-arm beam]───────────────┐                                ↓ optical axis
            │                                 │                                │ 15° from vertical
            └─────────────────────────────────┘                                │
                            │                                                  │
                            ▽ insulator string (~1.5 m)                        │
                            ▽                                                  │
                            ●                                                ◉ conductor
```

PNG of the rendered SVG cross-section: `.superpowers/brainstorm/<session>/screenshots/architecture-summary-v2.png`. Engineering verification of the geometry happens against the CadQuery output (`uv run poe generate-asm`, output GLB), not the SVG sketch.

### Electrical signal flow

**Main PCB → FFC → Daughterboard:** the existing 14-pin Lepton breakout pin map (per GroupGets module) is preserved on the FFC. Pin map:

| FFC pin | Net | Source on main PCB |
|---|---|---|
| 1 | GND | gnd |
| 2 | SPI_CE0 | CM4 J5 pin 24 |
| 3 | SPI_MOSI | CM4 J5 pin 19 |
| 4 | SPI_MISO | CM4 J5 pin 21 |
| 5 | SPI_SCK | CM4 J5 pin 23 |
| 6 | VSYNC | CM4 J5 pin 22 (GPIO25) |
| 7 | LEPTON_GPIO3 | floating net (NC) |
| 8 | I2C_SDA | CM4 J5 pin 3 |
| 9 | I2C_SCL | CM4 J5 pin 5 |
| 10 | PWR_DN_L | pulled to 3V3 via 10k (moves to daughterboard) |
| 11 | RESET_L | pulled to 3V3 via 10k (moves to daughterboard) |
| 12 | GND | gnd |
| 13 | 3V3 | AP2112K LDO output |
| 14 | VIN (= 3V3) | AP2112K LDO output |

**CM4 → commissioning port:** CM4 J1 USB 2.0 OTG pair routes to a sealed industrial USB-C connector on the enclosure side wall. The current `cad/netlist/som.py` uses a placeholder `Conn_02x20_Odd_Even` for the CM4 with USB on header pins 27/28. The real CM4 USB lives on the J1 connector pair, which has both a USB host pair (already routed to BG770A) and a USB OTG pair (new — routes to commissioning port). The custom DF40-100 footprint (referenced in `som.py`) needs to expose both pairs.

## Component Changes

### Main PCB (`cad/`)

| Ref | Old | New |
|---|---|---|
| J8 | 14-pin 2.54 mm THT header (`Conn_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical`) | **14-pin 0.5 mm pitch FFC connector** (Hirose FH12-14S-0.5SH or compatible) |
| J12 (new) | — | **Sealed industrial USB-C connector** wired to CM4 J1 USB 2.0 OTG pair (e.g., Bulgin PX0843, Amphenol RJF-USB-C, or board-level USB-C with external M12-X pigtail) |
| R9 (PWR_DN pull-up) | on main PCB at `[55, 64, 90]` | **moves to daughterboard** (closer to Lepton, signal integrity) |
| (RESET_L pull-up — currently inline in `build_flir_lepton`) | on main PCB | **moves to daughterboard** |
| C25 (FLIR deco) | on main PCB at `[30, 68, 0]` | **moves to daughterboard** (decoupling local to Lepton VIN) |

### Lepton daughterboard (new)

A new ~25 × 40 mm 4-layer PCB. Lives in a new directory `cad/lepton_daughter/` with the same project structure as `cad/` (KiCad project files, SKiDL netlist, placement YAML).

Components:

- **Molex 105028-1001 32-pin SMD socket** (or pin-compatible equivalent — this is what the Lepton mates to). Mounted on the **bottom side** of the daughterboard so the Lepton can hangs below, lens-down.
- **14-pin 0.5 mm FFC connector** mating the FFC ribbon from main PCB.
- **C_decoupling**: 100 nF + 10 µF on 3V3 rail, near the Molex socket VIN/VDDC pins.
- **R_PWR_DN, R_RESET**: 10 kΩ pull-ups to 3V3 on PWR_DN_L and RESET_L.
- **4× M2 corner mounting holes** for sheet-metal bracket attachment.

Routing notes: keep SPI traces (MOSI/MISO/SCK/CE0) on a single layer, ground-referenced. Lepton SPI runs at 20 MHz — preserve the impedance treatment from `theory.ipynb` Section 5.

### FFC ribbon

- **14 conductors, 0.5 mm pitch, ~80 mm length.**
- Type-A (same-side contacts) — both connectors are 0.5 mm bottom-contact ZIF, so a Type-A cable preserves pin numbering 1↔1.
- Specific length finalized once enclosure mechanical envelope is locked. 80 mm is a working assumption for design intent.

### Mechanical bracket

- **Material:** 1.5 mm aluminium sheet metal, alodine or anodized for corrosion.
- **Geometry:** flat plate, ~30 × 50 mm, 4× M2 clearance holes on a rectangular pattern matching the daughterboard, M3 clearance hole at one short edge (pivot), M3 arc slot at the opposite short edge spanning ~25 mm of arc (centred on the pivot, giving ±15° tilt range).
- **Hardware:**
  - 1× M3 shoulder bolt (pivot)
  - 1× M3 socket-cap screw + lockwasher + blue locktite (Loctite 243) at the slot
  - 4× M2 socket-cap screws + standoffs for daughterboard mounting
- **Bracket-to-enclosure:** mounts to the inside face of the enclosure top wall (or upper side wall, depending on enclosure mechanical design — out of scope here).

### IR window

- **Material:** germanium, broadband AR-coated for 8–14 µm, ~50% transmission.
- **Aperture:** ~25 mm diameter circular opening centred under the Lepton's optical axis at nominal aim (with the lens at the centre of its ±15° range).
- **Sealing:** silicone gasket on the inside of the enclosure floor, retained by a stainless steel bezel ring with 4× M2 screws.
- **Cost-down alternative:** HDPE (~70 % transmission, may yellow over 30 yrs in UV).

## CAD Code Changes

| File | Change |
|---|---|
| `cad/netlist/sensors.py` | `build_flir_lepton`: replace 14-pin THT header part with a 14-pin FFC connector. Move `R_PWR_DN`, `R_RESET`, and `C25` decoupling out of this function — they belong on the daughterboard now. |
| `cad/netlist/lepton_daughter.py` (new) | New SKiDL module: builds the daughterboard circuit (Molex 32-pin socket + FFC connector + decoupling + pull-ups). Mirrors the function-style of the existing `cad/netlist/` modules. |
| `cad/netlist/connectors.py` | New function `build_commissioning_usbc(usb_dp, usb_dm, gnd)` that adds the sealed industrial USB-C connector. |
| `cad/netlist/som.py` | `build_cm4`: add second USB pair (`commissioning_dp`, `commissioning_dm`) routed from the OTG pins of the (custom) DF40-100 footprint. |
| `cad/netlist/model.py` | Add `commissioning_dp`/`commissioning_dm` nets. Wire `build_commissioning_usbc` into the top-level netlist. |
| `cad/pcb_placement.yaml` | `J8` keeps the same position but the footprint changes; add `J12` for the commissioning USB-C in the `connectors` block. |
| `cad/assembly/build_assembly.py` | `MODEL_OVERRIDES` for `J8` changes from the Molex pin socket (current) to the FFC connector STEP. Add a new "lepton_daughterboard" subassembly with the bracket model + daughterboard PCB body + Lepton can/lens, all rotated by `LEPTON_TILT_DEG = -15` about the bracket pivot axis. The bracket itself is a `cq.Workplane` sheet-metal model. |
| `cad/lepton_daughter/` (new) | Full KiCad project for the daughterboard: `lepton_daughter.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `.net`, `placement.yaml`. Generated by re-running `/generate-schematic` and `/layout-pcb` skills against the new SKiDL module. |
| `pyproject.toml` | Add poe tasks for the daughterboard: `validate-daughter`, `inspect-daughter`, `generate-daughter` (mirror the existing main-PCB tasks). |
| `system_adrs.md` | Add **ADR-013**. |
| `readme.md` | Update the *Project Structure* tree with the new `cad/lepton_daughter/` and `cad/netlist/lepton_daughter.py` entries. Update the *Fabrication Pipeline* to call out two PCBs. |

## ADR-013 (to add to `system_adrs.md`)

```markdown
## ADR-013: Lepton Daughterboard for Aim Flexibility

**Status:** Accepted **Date:** 2026-05-10

### Context
ADR-001 mandates a single-PCB carrier with all sensor, cellular, and power-management
circuitry on one board. That decision was driven by stacked-Pi-HAT vibration failures
in 30-yr deployments — keeping the compute and electronics monolithic.

Cross-arm DLR deployment requires the FLIR Lepton 3.5 lens to aim at a conductor
~1.5 m below the cross-arm. With the lens perpendicular to the main PCB and a
sky-facing solar panel constraint, no monolithic-board orientation satisfies both.

### Decision
Split the Lepton onto a small (~25 × 40 mm) daughterboard linked to the main PCB
by a 14-pin 0.5 mm pitch FFC. Daughterboard mounts to a sheet-metal bracket with
M3 pivot + M3 arc-slot lock, allowing ±15° aim adjustment at integration time.

### Rationale
The spirit of ADR-001 was to avoid stacked compute (Pi 5 HAT). A passive sensor
daughterboard with no active electronics beyond the Lepton socket and decoupling
is not the failure class ADR-001 was guarding against. The daughterboard inherits
the 30-yr robustness of the main carrier (same conformal coat, same enclosure,
same potting) and adds no compute.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Lens out the side via vertical PCB | CM4 + cellular re-layout, vibration cantilever, antenna re-route. Overkill for an optical aim problem. |
| 45° gold folding mirror inside enclosure | Field-degradation: dust, condensation, ice, biofilm. Mirror-axis drift over 30 yrs. |
| Right-angle Lepton breakout (commercial) | Locks us to a specific vendor SKU with EOL risk; still needs a daughterboard or adapter. |

### Consequences
- Two PCBs in the project (main + daughter); two KiCad projects, two BOM files, two CPL files
- Two Gerber sets to fab; ~+$15 marginal fab cost per unit at low volume
- Aim is set once at integration, locked with lockwasher + Loctite 243; no field-accessible knob
- Sealed industrial USB-C commissioning port becomes mandatory (without it, the integrator can't see the live thermal frame to set aim)
- ADR-001 retains force for compute and the bulk of sensor/power circuitry; ADR-013 is a scoped exception for the Lepton optical chain only
```

## Optical Performance Targets

Per FLIR's radiometric guidance, **≥ 3 px on target** is the floor for accurate temperature readings. Targets:

| Parameter | Value | Source |
|---|---|---|
| Lepton 3.5 array | 160 × 120 px | Teledyne IDD §3.1 |
| HFOV (stock optic) | 57° | Teledyne IDD §4.2 |
| IFOV (per-pixel angular) | 6.22 mrad (0.356°) | computed |
| Mount distance to conductor | ~1.5 m | cross-arm geometry |
| Ground sample distance at 1.5 m | ~9.3 mm/px | computed |
| Conductor diameter (representative ACSR) | 25 mm | mid-range sub-T |
| Pixels on conductor | ~2.7 px | borderline 3-px floor |
| Aim tolerance for ≥3 px | ±5° from optimal | derived |
| ±15° tilt range design margin | 3× aim tolerance | conservative |

## Out of Scope

- **Software** — the live thermal preview tool used during commissioning (`lepton-live` or equivalent). That lives in the firmware/host stack, not the PCB design.
- **Enclosure mechanical design** — overall enclosure geometry, IP55 sealing, conformal coating procedure. The carrier defines the connector + mounting hole interfaces; the enclosure wraps around them and is specified in a separate document.
- **Tower mounting hardware** — cross-arm clamps, U-bolts, anti-vibration mounts. Off-board accessories.
- **Cellular antenna selection** — covered in ADR-006/-012.
- **Lepton 3.5 SKU choice** — radiometric variant assumed (current readme spec).

## Validation / EVT

| Check | How |
|---|---|
| Main PCB ERC + DRC clean | `uv run poe validate-model` + `uv run poe validate-asm` |
| Daughterboard ERC + DRC clean | New `validate-daughter` poe task |
| FFC pin map matches Lepton breakout | Net-by-net inspection of generated `cad/dlr_carrier.net` and `cad/lepton_daughter/lepton_daughter.net` |
| Bracket clearance + tilt range | Render `output/dlr_carrier_pcb.glb` (CadQuery output), confirm daughterboard tilts ±15° without colliding with main PCB or enclosure walls |
| Optical axis lands on conductor | Render at nominal -15° tilt and confirm the optical-axis vector through the IR window lands at the expected conductor position 1.5 m below |
| Commissioning USB-C reachable when capped | Mechanical: verify the M12 cap clears the bracket and FFC ribbon |
| Lab radiometric calibration | Bench-mount carrier, point at hot resistor at known T, verify Lepton reading within ±2°C of contact thermocouple |
| Field aim workflow | Mock cross-arm install: open enclosure, plug laptop, run live preview, tilt, lock, seal. Time the workflow; target ≤ 10 min per unit. |

## Open Questions

- Specific FFC connector P/N (Hirose FH12 family is canonical but exact SKU depends on stocking).
- Specific sealed industrial USB-C connector — Bulgin vs Amphenol vs custom M12-X with USB-C pigtail. Decision deferred to procurement.
- Bracket vendor — sheet-metal shop sourcing or laser-cut from local fab.
- Whether to use a commercial Germanium window assembly (e.g., Edmund Optics) or fabricate from raw Ge stock with a custom retainer.
