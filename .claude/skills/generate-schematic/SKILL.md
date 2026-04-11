---
name: generate-schematic
description: Generate professional KiCad schematic from SKiDL netlist + declarative layout spec. Two-phase: deterministic placement then visual refinement.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
---

# Generate Professional KiCad Schematic

Read `cad/layout_spec.yaml` and the SKiDL netlist to generate a professional `.kicad_sch` file using kicad-sch-api.

## Phase 1: Deterministic Placement

1. **Read layout spec** — `cad/layout_spec.yaml` defines sheet size, title, functional blocks, positions, and components
2. **Read netlist** — parse `cad/netlist/model.py` and its sub-modules (power.py, comms.py, etc.) for component list, pin connections, and net names. Write generated code to `cad/schematic/`.
3. **Generate schematic** — use kicad-sch-api with these rules:

### Layout Rules
- Read `sheet_size` and `title` from `layout_spec.yaml` — never hardcode
- **Sheet border margin**: all block positions must start at >= 30 grid units from origin. Components at (8,8) WILL clip the sheet border
- Each block occupies its declared position region — no overlap
- ICs centered in their block
- Decoupling caps directly below their IC's power pins
- Power symbols (+5V, +3V3) at TOP of each block
- GND symbols at BOTTOM of each block
- Signal inputs on LEFT edge of block, outputs on RIGHT
- Minimum 8 grid units between components within a block

### Wiring Rules — Label-Heavy Strategy
- **All inter-block connections use net labels** — do NOT draw long wires between blocks
- Direct wires ONLY for immediately adjacent components within the same block (e.g., polyfuse → MOSFET source)
- Each component pin gets a short wire stub (3-6 grid units) to a label or power symbol
- **NEVER use** `auto_route_pins()`, `connect_pins_with_wire()`, or `add_wire_to_pin()` — these have coordinate bugs in grid-unit mode
- **ALWAYS use** `add_wire(start, end)` with explicit grid-unit positions

### Y-Coordinate Coincidence Bug (Critical)
KiCad ERC falsely merges nets when two pins from different blocks share the exact same y-coordinate, even without any connecting wire. **Always verify** that pins across blocks do NOT land on the same y grid value. If they do, shift one block by 2-4 grid units.

### ERC Compliance Rules
- **PWR_FLAG placement**: required on power nets not driven by any power output pin. +5V typically needs one. GND may NOT need one if a connector pin (e.g., USB_B_Micro.GND) is typed as power output — adding PWR_FLAG causes "two power outputs" error
- **Single-endpoint nets**: use no-connects, NOT labels. Labels on pins that connect to nothing else create "dangling label" ERC errors (e.g., GPIO header pins not assigned to CM4)
- **PWR_FLAG must be wired** to the net via `add_wire` — placing it nearby is NOT enough
- `no_connects.add()` does NOT respect `use_grid_units()` — pass mm coordinates: `(grid_x * 1.27, grid_y * 1.27)`

4. **Set title block** — `sch.set_title_block(title=spec["title"], company="Engineering With AI")`
5. **Run ERC** — `kicad-cli sch erc cad/*.kicad_sch --severity-all` must pass with 0 errors (warnings OK)

## Phase 2: Visual Review Loop (max 5 iterations)

After Phase 1, iterate on visual quality. **Use lightweight commands for iteration — NOT `poe generate-model`:**

1. **Regenerate schematic** — `uv run python -m cad.schematic.schematic`
2. **Quick SVG export** — `kicad-cli sch export svg cad/*.kicad_sch -e -n -o /tmp/`
3. **Convert to PNG** — `rsvg-convert -w 2400 /tmp/*.svg -o /tmp/schematic_review.png`
4. **Read and inspect the PNG** — look for:
   - Components clipped by sheet border (increase margin)
   - Labels overlapping component references or values
   - Wires crossing through component bodies
   - Unbalanced spacing between sections
   - Text too small or illegible at this resolution
   - Signal flow not reading left-to-right
   - Components too close together
   - Components overlapping title block area (bottom-right)
5. **If issues found**: adjust positions in the schematic generation code, re-run from step 1
6. **If clean**: run final ERC, then proceed to output

After converging, update `cad/layout_spec.yaml` with the refined positions so future runs start from the optimized layout.

## Output

- `cad/<project>.kicad_sch` — generated schematic
- ERC report confirming 0 errors
- Run `uv run poe generate-model` for **final export only** (SVG, PDF with drawing sheet, B&W, etc.) — do NOT run raw `kicad-cli` export commands, as the poe task has project-specific flags already configured. Do NOT run `poe generate-model` during the review loop — it rebuilds the netlist and runs all exports unnecessarily.

## Layout Spec Format Reference

```yaml
sheet_size: A3
title: "Project Title"

blocks:
  block_name:
    position: [x, y]              # grid units from sheet origin (min 30 to clear border)
    components: [R1, U1, C1]      # reference designators
    signal_flow: left_to_right    # or right_to_left, top_to_bottom
    power_rail: "+5V"             # power symbol name (placed at top)
    ground: true                  # add GND symbol at bottom
    labels:
      left: [NET_A, NET_B]       # input net labels
      right: [NET_C]             # output net labels

layout_rules:
  min_component_spacing: 8
  power_symbol_position: top
  ground_symbol_position: bottom
  decoupling_near_ic: true
  routing: labels                 # label-heavy, not manhattan wires
```
