"""Multi-sheet hierarchical schematic emission.

Each functional block (power, som, sensors, connectors, cellular, anemometer)
becomes its own .kicad_sch child sheet. Top-level root sheet contains one
sheet symbol per block. Cross-block nets use GLOBAL labels (matched by name
across sheets) and global power symbols (+5V, +3V3, GND). Intra-block nets
use local labels.

The per-sheet ERC scope bounds KiCad's y-coincidence false-merge bug: with
~10-30 components per sheet, the cross-net pin-coordinate collision rate
drops dramatically vs the single-sheet generator.
"""

from __future__ import annotations

import contextlib
import math
from typing import Final

import kicad_sch_api as ksa

from cad.schematic.schematic import (
    BLOCK_TITLES,
    POWER_SYMBOL_BY_NET,
    PwrCounter,
    _add_nc_at_pin,
    _outward_direction,
    _place_block,
    _place_pwr_flags,
    _power_driven_nets,
    _power_symbol_y,
    _real_pin_position,
)

CHILD_SHEET_SIZE: Final = "A3"  # roomy per-block sheet; A3 = 420x297 mm
ROOT_SHEET_SIZE: Final = "A2"  # 594x420 mm; fits 3 rows of sheet symbols


def cross_block_nets(
    by_block: dict[str, list[dict]], nets: list[dict]
) -> set[str]:
    """Nets whose nodes span 2+ blocks → must be global labels for cross-sheet
    connectivity."""
    block_of_ref: dict[str, str] = {}
    for block, comps in by_block.items():
        for c in comps:
            block_of_ref[c["ref"]] = block

    cross: set[str] = set()
    for net in nets:
        blocks = {block_of_ref.get(n["ref"]) for n in net["nodes"]}
        blocks.discard(None)
        if len(blocks) > 1:
            cross.add(net["name"])
    return cross


def _route_pin_multi(
    sch,
    comp,
    pin_num: str,
    net_name: str,
    cross_nets: set[str],
    pwr: PwrCounter,
) -> None:
    """Stub a pin with power symbol / NC / global label / local label.

    Power nets → power symbol (auto-global). Cross-block nets → global label.
    Anything else → local label. Internal-only single-endpoint nets → no-connect.
    """
    try:
        pin_pos_mm = _real_pin_position(comp, pin_num)
    except Exception:
        return
    if not pin_pos_mm:
        return
    pin_grid = (round(pin_pos_mm.x / 1.27), round(pin_pos_mm.y / 1.27))

    # NC_ / N$ prefix from SKiDL means "auto-named net". A real multi-node net
    # may get this prefix if SKiDL merges through an unnamed pin (e.g. tying
    # two pins of the same chip together). Treat such nets as real signals if
    # the cross-block analysis already decided they need a label.
    if (net_name.startswith("NC_") or net_name.startswith("N$")) and net_name not in cross_nets:
        with contextlib.suppress(Exception):
            sch.no_connects.add(
                position=(pin_grid[0] * 1.27, pin_grid[1] * 1.27)
            )
        return

    dx, dy = _outward_direction(comp, pin_num)
    stub_len = 8 if (dx > 0 or dy > 0) else 4

    if net_name in POWER_SYMBOL_BY_NET:
        rail_offset = {"GND": 0, "5V_RAIL": 0, "3V3": 2}.get(net_name, 0)
        sym = POWER_SYMBOL_BY_NET[net_name]
        if net_name == "GND":
            base_y = pin_grid[1] + stub_len + rail_offset
        else:
            base_y = pin_grid[1] - stub_len - rail_offset
        end = (pin_grid[0], _power_symbol_y(net_name, base_y))
        with contextlib.suppress(Exception):
            sch.add_wire(start=pin_grid, end=end)
            sch.components.add(
                sym, pwr.pwr_ref(), sym.split(":")[-1], position=end
            )
        return

    label_pos = (pin_grid[0] + dx * stub_len, pin_grid[1] + dy * stub_len)
    if dx > 0:
        label_rot = 0
    elif dx < 0:
        label_rot = 180
    elif dy > 0:
        label_rot = 270
    else:
        label_rot = 90

    sch.add_wire(start=pin_grid, end=label_pos)
    if net_name in cross_nets:
        # Hierarchical label persists to file (unlike global_label, which is a
        # known kicad-sch-api serialization bug as of v0.5.6 — add_global_label
        # adds to internal data but the serializer doesn't write it).
        # IMPORTANT: add_hierarchical_label does NOT honor use_grid_units; must
        # convert grid -> mm here so the label lands on the wire endpoint.
        sch.add_hierarchical_label(
            net_name,
            position=(label_pos[0] * 1.27, label_pos[1] * 1.27),
            rotation=label_rot,
            size=1.0,
        )
    else:
        sch.add_label(
            net_name, position=label_pos, rotation=label_rot, size=0.8
        )


def build_child_sheet(
    block_name: str,
    comps: list[dict],
    nets: list[dict],
    cross_nets: set[str],
    sheet_path: str,
    sheet_size: str = CHILD_SHEET_SIZE,
) -> set[str]:
    """Emit one functional-block sheet. Returns the cross-net names present
    on this sheet (so the root can add matching sheet pins)."""
    ksa.use_grid_units(True)
    title = BLOCK_TITLES.get(block_name, block_name.upper())
    sch = ksa.create_schematic(title)
    sch.set_paper_size(sheet_size)
    sch.set_title_block(
        title=f"DLR Carrier — {title}",
        company="Engineering With AI",
        rev="1.0",
    )

    # Grid sized to A3 minus title block (~330 x 230 grid units)
    region = {"origin": [30, 30], "width": 280, "height": 200}
    placed = _place_block(sch, comps, region)

    # Filter nets to those touching this block's components
    refs = {c["ref"] for c in comps}
    pwr = PwrCounter()
    routed: set[tuple[str, str]] = set()
    pwr_nets_used: set[str] = set()
    sheet_cross_nets: set[str] = set()
    for net in nets:
        local_nodes = [n for n in net["nodes"] if n["ref"] in refs]
        if not local_nodes:
            continue
        if net["name"] in POWER_SYMBOL_BY_NET:
            pwr_nets_used.add(net["name"])
        # Single endpoint AND not crossing into other sheets → NC
        if len(net["nodes"]) == 1 and net["name"] not in cross_nets:
            node = local_nodes[0]
            comp = placed.get(node["ref"])
            if comp:
                _add_nc_at_pin(sch, comp, node["pin"])
                routed.add((node["ref"], node["pin"]))
            continue
        if net["name"] in cross_nets:
            sheet_cross_nets.add(net["name"])
        for node in local_nodes:
            comp = placed.get(node["ref"])
            if comp:
                _route_pin_multi(
                    sch, comp, node["pin"], net["name"], cross_nets, pwr
                )
                routed.add((node["ref"], node["pin"]))

    # Orphan pins → no-connects
    for ref, comp in placed.items():
        try:
            pins = comp.list_pins()
        except Exception:
            continue
        for pin in pins:
            num = pin["number"]
            if (ref, num) not in routed:
                _add_nc_at_pin(sch, comp, num)

    # Skip PWR_FLAG on child sheets. Multiple children placing PWR_FLAGs for
    # the same global net (e.g. GND on every sheet) creates "multiple Power-out
    # drivers" ERC errors. The root sheet places one PWR_FLAG per undriven
    # power net globally.

    sch.save_as(sheet_path)
    # Power nets (GND/+5V/+3V3) are KiCad-global via power symbols — no parent
    # sheet pins needed. Only signal cross-nets get reported back.
    return sheet_cross_nets - set(POWER_SYMBOL_BY_NET.keys())


def _place_pwr_flag_bank(sch, pwr: PwrCounter, nets_used: set[str]) -> None:
    """Place PWR_FLAG bank in upper-right corner of the child sheet."""
    for i, net_name in enumerate(sorted(nets_used)):
        sym = POWER_SYMBOL_BY_NET.get(net_name)
        if not sym:
            continue
        x = 280 + i * 10  # corner of A3 grid
        y_base = 20 + i * 4
        y = _power_symbol_y(net_name, y_base)
        flg_y = _power_symbol_y(net_name, y - 8)
        with contextlib.suppress(Exception):
            sch.components.add(
                sym, pwr.pwr_ref(), sym.split(":")[-1], position=(x, y)
            )
            sch.components.add(
                "power:PWR_FLAG", pwr.flg_ref(), "PWR_FLAG",
                position=(x, flg_y),
            )
            sch.add_wire(start=(x, y), end=(x, flg_y))


def build_root_sheet(
    block_sheets: list[tuple[str, str, set[str]]],
    sheet_path: str,
    title: str,
    nets: list[dict],
    sheet_size: str = ROOT_SHEET_SIZE,
) -> None:
    """Root sheet with one sheet symbol per child block.

    block_sheets: list of (block_name, child_filename, cross_net_names) tuples.
    For each child the cross_net_names declare which nets the child exports.
    The root adds a matching sheet pin per cross net and a label of the same
    name next to that pin so KiCad's same-name-on-same-sheet net resolution
    binds all child sheets' pins for that net into a single parent net.
    """
    ksa.use_grid_units(False)  # mm coords for sheet symbols
    sch = ksa.create_schematic(title)
    sch.set_paper_size(sheet_size)
    sch.set_title_block(
        title=title, company="Engineering With AI", rev="1.0"
    )

    # 3x2 grid on A2 landscape (594x420 mm) with even spacing + symmetric
    # margins. Cells narrow (just enough for pin labels) — sheet symbols are
    # placeholders, the interior is intentionally hollow. PWR_FLAG bank sits
    # centered above the grid; KiCad title block lives at bottom-right.
    cols = 3
    cell_w = 70.0
    cell_h = 130.0
    col_gap = 30.0
    row_gap = 30.0
    # Center the grid horizontally within the area to the LEFT of the title
    # block (title block occupies bottom-right ~150x60 mm on A2).
    grid_w = cols * cell_w + (cols - 1) * col_gap
    margin_x = (445 - grid_w) / 2  # 445 = title-block left edge
    # Center the grid vertically with even top + bottom margins.
    margin_y = (420 - 2 * cell_h - row_gap) / 2

    for i, (block_name, child_file, child_cross) in enumerate(block_sheets):
        row, col = divmod(i, cols)
        x = margin_x + col * (cell_w + col_gap)
        y = margin_y + row * (cell_h + row_gap)
        title_text = BLOCK_TITLES.get(block_name, block_name.upper())
        try:
            sheet_uuid = sch.add_sheet(
                name=title_text,
                filename=child_file,
                position=(x, y),
                size=(cell_w, cell_h),
                stroke_width=0.2,
            )
        except Exception:
            continue
        # Add one sheet pin per cross net on the LEFT edge of the symbol,
        # evenly distributed bottom-to-top (KiCad's convention for "left" edge
        # is to measure position_along_edge from the bottom).
        nets_sorted = sorted(child_cross)
        if not nets_sorted:
            continue
        edge_spacing = (cell_h - 10) / max(len(nets_sorted), 1)
        STUB = 5.0  # mm wire stub from sheet pin to label
        for j, net_name in enumerate(nets_sorted):
            try:
                sch.add_sheet_pin(
                    sheet_uuid=sheet_uuid,
                    name=net_name,
                    pin_type="bidirectional",
                    edge="left",
                    position_along_edge=5 + j * edge_spacing,
                )
            except Exception:
                continue
            # Sheet pin actual y on left edge = y + cell_h - position_along_edge.
            pin_y = (y + cell_h) - (5 + j * edge_spacing)
            # Short wire stub from the pin outward (leftward) + label on the
            # wire's outer endpoint, OFFSET 8 mm further out so the label text
            # doesn't overlap the sheet pin's own internal name rendering.
            LABEL_OFFSET = 8.0
            with contextlib.suppress(Exception):
                sch.add_wire(
                    start=(x, pin_y),
                    end=(x - STUB - LABEL_OFFSET, pin_y),
                )
                sch.add_label(
                    text=net_name,
                    position=(x - STUB - LABEL_OFFSET, pin_y),
                    rotation=180,
                    size=1.0,
                    grid_units=False,
                )

    # Globally-undriven power nets need ONE PWR_FLAG on the root so ERC is
    # satisfied. Power symbols are global → one driver feeds every child.
    # Place the bank centered above the grid (along grid center x) so the
    # overall page is left-right symmetric.
    ksa.use_grid_units(True)
    driven = _power_driven_nets(nets)
    flag_nets = set(POWER_SYMBOL_BY_NET.keys()) - driven
    grid_center_mm = margin_x + grid_w / 2
    n_flags = len(flag_nets)
    bank_w_grid = max(1, n_flags - 1) * 6
    x0_grid = round((grid_center_mm / 1.27) - bank_w_grid / 2)
    _place_root_pwr_flags(sch, flag_nets, x0_grid=x0_grid, y0_grid=12)
    ksa.use_grid_units(False)

    sch.save_as(sheet_path)


def _place_root_pwr_flags(
    sch, nets_used: set[str], x0_grid: int, y0_grid: int
) -> None:
    """Place one PWR_FLAG + matching power symbol per undriven power net.

    Grid units = 1.27 mm. Mirrors the schematic.py single-sheet pattern that
    is known to produce ERC-clean connectivity; only the x-base differs so
    the bank lands inside the A3 root sheet (420 mm = 331 grid).
    """
    pwr = PwrCounter()
    pwr.n = 100  # avoid clash with child-sheet #PWR refs
    pwr.flg = 100
    for i, net_name in enumerate(sorted(nets_used)):
        sym = POWER_SYMBOL_BY_NET.get(net_name)
        if not sym:
            continue
        x = x0_grid + i * 6
        # For +5V / +3V3 power symbols, pin points UP — connection expects a
        # wire coming from above. For GND, pin points DOWN — wire from below.
        # PWR_FLAG always wants its connection above (pin points up).
        y_base = y0_grid + i * 4
        y = _power_symbol_y(net_name, y_base)
        if net_name == "GND":
            # GND pin down: place FLG above (smaller y).
            flg_y = _power_symbol_y(net_name, y - 8)
        else:
            # +5V / +3V3 pin up: place FLG above (smaller y). PWR symbol sits
            # AT THE TOP of a short wire; PWR_FLAG dangles below.
            flg_y = _power_symbol_y(net_name, y + 8)
        rail = sym.split(":")[-1]
        with contextlib.suppress(Exception):
            sch.components.add(sym, pwr.pwr_ref(), rail, position=(x, y))
            sch.components.add(
                "power:PWR_FLAG", pwr.flg_ref(), "PWR_FLAG",
                position=(x, flg_y),
            )
            sch.add_wire(start=(x, y), end=(x, flg_y))
