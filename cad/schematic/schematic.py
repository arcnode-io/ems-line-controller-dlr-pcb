"""DLR carrier schematic generator — block-aware placement, label-based connectivity.

Reads cad/dlr_carrier.net, classifies each component into a block (power, som,
cellular, sensors, connectors, misc), places each block's components in a
sub-grid within the block's region defined in layout_spec.yaml. Inter-block
connectivity is preserved through labels and power symbols.
"""

import contextlib
import math
from pathlib import Path
from typing import Final

import kicad_sch_api as ksa
import sexpdata
import yaml

LAYOUT_SPEC_PATH = Path("cad/layout_spec.yaml")
NETLIST_PATH = Path("cad/dlr_carrier.net")
SCHEMATIC_PATH = "cad/dlr_carrier.kicad_sch"

LIB_BY_PART: Final = {
    "C": "Device",
    "C_Polarized": "Device",
    "R": "Device",
    "L": "Device",
    "D_Schottky": "Device",
    "D_TVS_Dual_AAC": "Device",
    "Polyfuse": "Device",
    "Conn_Coaxial": "Connector",
    "SIM_Card": "Connector",
    "AP2112K-3.3": "Regulator_Linear",
    "LP5907MFX-3.3": "Regulator_Linear",
    "BG95-M1": "RF_GSM",
    "TXS0108EPW": "Logic_LevelTranslator",
    "ADS1115IDGS": "Analog_ADC",
    "DHT11": "Sensor",
    "SP3485EN": "Interface_UART",
    "USB_C_Receptacle_USB2.0_14P": "Connector",
}

# Component value -> block (catches all uniquely-named ICs and connectors)
VALUE_TO_BLOCK: Final = {
    # power
    "PV_IN": "power",
    "SS34": "power",
    "BQ24650": "power",
    "LMR33630ADDA": "power",
    "AP2112K-3.3": "power",
    "LP5907MFX-3.8": "power",
    # som
    "CM4_J2": "som",
    # cellular
    "BG770A-NA": "cellular",
    "TXS0108E": "cellular",
    "U.FL": "cellular",
    "SIM": "cellular",
    # sensors
    "FLIR_LEPTON": "sensors",
    "FLIR_LEPTON_FFC": "sensors",
    "DHT22": "sensors",
    "SI1145": "sensors",
    "YL-83": "sensors",
    "ADS1115": "sensors",
    # connectors
    "BAT": "connectors",
    "DEBUG_UART": "connectors",
    "USBC_COMMISSIONING": "connectors",
    # anemometer
    "SP3485EN": "anemometer",
    "ANEMO_M12_5P": "anemometer",
    "SM712-like": "anemometer",
}

# Block-specific nets (for classifying passives that don't have unique values)
BLOCK_NETS: Final = {
    "power": {
        "PV_IN",
        "PV_RAW",
        "VBAT",
        "BAT_SRP",
        "MPPT_SW",
        "MPPT_BOOT",
        "BUCK_SW",
        "BUCK_BOOT",
        "BUCK_FB",
        "BUCK_RT",
    },
    "cellular": {
        "3V8_CELL",
        "VDD_EXT_1V8",
        "ANT_IN",
        "ANT_MATCH",
        "CELL_PWRKEY",
        "CELL_RESET",
        "CELL_STATUS",
        "CELL_NET_STATUS",
        "CELL_TX_1V8",
        "CELL_RX_1V8",
        "CELL_PWRKEY_1V8",
        "CELL_RESET_1V8",
        "CELL_STATUS_1V8",
        "CELL_NET_1V8",
    },
    "sensors": {
        "RAIN_AO",
        "GPIO4_DHT22",
        "GPIO25_VSYNC",
    },
    "connectors": {"DBG_TX", "DBG_RX"},
    "anemometer": {
        "ANEMO_RS485_A",
        "ANEMO_RS485_B",
        "ANEMO_UART_TX",
        "ANEMO_UART_RX",
        "ANEMO_DE",
        "ANEMO_V_SENSOR",
        "ANEMO_SHIELD",
    },
}

POWER_SYMBOL_BY_NET: Final = {
    "GND": "power:GND",
    "5V_RAIL": "power:+5V",
    "3V3": "power:+3V3",
}


def _real_pin_position(comp, pin_num: str):
    """Pin position in sheet coords, fixing kicad-sch-api's y-inversion bug.

    kicad-sch-api computes pin_y = sym_y + pin_offset_y, but KiCad's actual
    rendering uses pin_y = sym_y - pin_offset_y (symbol coords are +y up,
    sheet coords are +y down). Reflect ksa's reported y around sym_y to get
    the position KiCad will actually draw the pin at.

    Only valid for unrotated symbols (rotation=0). All components produced
    by _place_one are placed unrotated, so this assumption holds.
    """
    pos = comp.get_pin_position(pin_num)
    if not pos:
        return None
    sym_y = comp.position.y
    return type(pos)(pos.x, 2 * sym_y - pos.y)


def _resolve_lib(part_name: str) -> str:
    if part_name in LIB_BY_PART:
        return LIB_BY_PART[part_name]
    if part_name.startswith("Conn_01x") or part_name.startswith("Conn_02x"):
        return "Connector_Generic"
    raise ValueError(f"Unknown lib for part {part_name!r}")


def _parse_netlist(path: Path) -> tuple[list[dict], list[dict]]:  # noqa: C901
    """Extract components and nets from a SKiDL-generated kicad netlist."""
    data = sexpdata.loads(path.read_text())
    components, nets = [], []

    def s(node) -> str:
        return str(node[0]) if isinstance(node, list) and node else ""

    def find_section(root, key) -> list:
        if isinstance(root, list):
            if s(root) == key:
                return root
            for child in root:
                r = find_section(child, key)
                if r:
                    return r
        return []

    for comp in find_section(data, "components")[1:]:
        info: dict = {}
        for field in comp[1:]:
            tag = s(field)
            if tag == "ref":
                info["ref"] = field[1]
            elif tag == "value":
                info["value"] = field[1]
            elif tag == "footprint":
                info["footprint"] = field[1]
            elif tag == "libsource":
                for sub in field[1:]:
                    if s(sub) == "part":
                        info["part"] = sub[1]
            elif tag == "fields":
                # Look for SKiDL's "SKiDL Line" field — source file pinpoints block
                for sub in field[1:]:
                    if s(sub) == "field":
                        # field structure: (field (name "SKiDL Line") "power.py:17")
                        for inner in sub[1:]:
                            if (
                                isinstance(inner, list)
                                and s(inner) == "name"
                                and len(inner) > 1
                                and inner[1] == "SKiDL Line"
                                and len(sub) > 2
                                and isinstance(sub[2], str)
                            ):
                                # field structure: (field (name "SKiDL Line") "power.py:17")
                                info["source"] = sub[2]
        if info.get("ref"):
            components.append(info)

    for net in find_section(data, "nets")[1:]:
        info = {"name": "", "nodes": []}
        for field in net[1:]:
            tag = s(field)
            if tag == "name":
                info["name"] = field[1]
            elif tag == "node":
                node = {}
                for sub in field[1:]:
                    if s(sub) == "ref":
                        node["ref"] = sub[1]
                    elif s(sub) == "pin":
                        node["pin"] = sub[1]
                    elif s(sub) == "pintype":
                        node["pintype"] = sub[1]
                if node:
                    info["nodes"].append(node)
        if info["name"]:
            nets.append(info)
    return components, nets


def _comp_nets_index(nets: list[dict]) -> dict[str, set[str]]:
    """Build {ref: {net_name, ...}} for all components."""
    idx: dict[str, set[str]] = {}
    for net in nets:
        for node in net["nodes"]:
            idx.setdefault(node["ref"], set()).add(net["name"])
    return idx


SOURCE_FILE_TO_BLOCK: Final = {
    "power.py": "power",
    "som.py": "som",
    "cellular.py": "cellular",
    "sensors.py": "sensors",
    "connectors.py": "connectors",
    "anemometer.py": "anemometer",
    "model.py": "connectors",  # model.py's _build_battery_connector previously
}


def _classify(comp: dict, comp_nets: set[str]) -> str:
    """Assign component to a block by SKiDL source file, then value, then nets."""
    # Best signal: SKiDL records the source file in a field
    src = comp.get("source", "")
    for fname, block in SOURCE_FILE_TO_BLOCK.items():
        if fname in src:
            return block
    val = comp.get("value", "")
    if val in VALUE_TO_BLOCK:
        return VALUE_TO_BLOCK[val]
    scores = {
        b: sum(1 for n in comp_nets if n in nets) for b, nets in BLOCK_NETS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    if {"5V_RAIL", "3V3"} & comp_nets:
        return "power"
    return "misc"


def _grid_for_block(n: int, w: int, h: int) -> tuple[int, int, int]:
    """Choose (cols, cell_w, cell_h) so n components fit in w x h with even spacing."""
    if n == 0:
        return 1, w, h
    cols = max(1, min(n, math.ceil(math.sqrt(n * w / max(h, 1)))))
    rows = math.ceil(n / cols)
    cell_w = max(20, w // cols)
    cell_h = max(20, h // rows)
    return cols, cell_w, cell_h


BLOCK_TITLES: Final = {
    "power": "POWER",
    "som": "CM4 SoM",
    "cellular": "CELLULAR",
    "sensors": "IEEE 738 SENSORS",
    "connectors": "CONNECTORS",
    "anemometer": "ANEMOMETER RS-485",
    "misc": "MISC",
}


def _draw_block_frame(sch, block_name: str, region: dict) -> None:
    """Thin gray dashed border + title text for a functional block."""
    ox, oy = region["origin"]
    w, h = region["width"], region["height"]
    pad = 4  # frame padding so it doesn't crowd components
    gray = (128, 128, 128, 1.0)
    with contextlib.suppress(Exception):
        sch.add_rectangle(
            start=(ox - pad, oy - pad),
            end=(ox + w + pad, oy + h + pad),
            stroke_width=0.05,
            stroke_type="dash",
            stroke_color=gray,
        )
        title = BLOCK_TITLES.get(block_name, block_name.upper())
        sch.add_text(
            title,
            position=(ox, oy - pad - 3),
            size=2.0,
            bold=True,
            color=gray,
        )


# Components whose symbol body is much taller than typical (multi-unit / many-pin).
# Reserve a dedicated full-width row at the top of their block so their pin
# labels and body don't overflow into adjacent components.
TALL_COMPONENT_VALUES: Final = {"BG770A-NA", "CM4_J2"}
TALL_ROW_HEIGHT: Final = 110  # grid units — covers BG770A body (~80) + label margin


def _place_one(sch, comp: dict, gx: int, gy: int):
    """Instantiate a single component at (gx, gy)."""
    lib_id = f"{_resolve_lib(comp['part'])}:{comp['part']}"
    c = sch.components.add(
        lib_id, comp["ref"], comp.get("value", ""), position=(gx, gy)
    )
    if comp.get("footprint"):
        c.footprint = comp["footprint"]
    return c


def _place_block(sch, block_components: list[dict], region: dict) -> dict:
    """Place tall ICs in a dedicated top row, rest in a sub-grid below."""
    placed: dict = {}
    ox, oy = region["origin"]
    w, h = region["width"], region["height"]

    tall = [c for c in block_components if c.get("value") in TALL_COMPONENT_VALUES]
    rest = [c for c in block_components if c.get("value") not in TALL_COMPONENT_VALUES]

    rest_oy, rest_h = oy, h
    if tall:
        cell_w_t = w // len(tall)
        gy_t = oy + TALL_ROW_HEIGHT // 2
        for i, comp in enumerate(tall):
            gx = ox + i * cell_w_t + cell_w_t // 2
            placed[comp["ref"]] = _place_one(sch, comp, gx, gy_t)
        rest_oy = oy + TALL_ROW_HEIGHT
        rest_h = max(20, h - TALL_ROW_HEIGHT)

    n = len(rest)
    if n:
        cols, cw, ch = _grid_for_block(n, w, rest_h)
        for i, comp in enumerate(rest):
            row, col = divmod(i, cols)
            # Per-component (dx, dy) hash jitter breaks x- and y-coincidence
            # across the whole schematic. KiCad ERC falsely merges nets when
            # any two wires share an x or y, so wide entropy is needed to avoid
            # cascade merges. Prime moduli (17, 23) reduce structured collisions
            # vs round moduli that align with pin offsets like 2.54/3.81/5.08.
            h = abs(hash(comp["ref"]))
            dx = h % 17
            dy = (h // 17) % 23
            gx = ox + col * cw + cw // 2 + dx
            gy = rest_oy + row * ch + ch // 2 + dy
            placed[comp["ref"]] = _place_one(sch, comp, gx, gy)
    return placed


class PwrCounter:
    """Generates unique #PWR / #FLG references for power symbols."""

    def __init__(self):
        """Init counters."""
        self.n = 1
        self.flg = 1

    def pwr_ref(self) -> str:
        """Next unique #PWR ref."""
        ref = f"#PWR{self.n:03d}"
        self.n += 1
        return ref

    def flg_ref(self) -> str:
        """Next unique #FLG ref."""
        ref = f"#FLG{self.flg:03d}"
        self.flg += 1
        return ref


def _outward_direction(comp, pin_num: str) -> tuple[int, int]:
    """Direction the pin points outward from the symbol body (dx, dy in grid units).

    Uses the pin's own rotation attribute. Convention: kicad pin rotation 0
    means the pin LINE extends rightward INTO the symbol body, so the
    connection end (outer tip) is on the LEFT. Outward direction is the
    opposite of the pin line direction.
    """
    try:
        p = comp.get_pin(pin_num)
        if not p:
            return (-1, 0)
        rot = int(p.rotation) % 360
    except Exception:
        return (-1, 0)
    if rot == 0:
        return (-1, 0)  # pin points right into body -> outward left
    if rot == 180:
        return (1, 0)  # pin points left into body  -> outward right
    if rot == 90:
        return (0, 1)  # pin points up into body    -> outward down (+y in kicad = down)
    if rot == 270:
        return (0, -1)  # pin points down into body  -> outward up
    return (-1, 0)


def _net_jitter(net_name: str) -> tuple[int, int]:
    """Per-net x/y offset (0-2 grid) to break kicad's false-merge y/x coincidence bug."""
    h = abs(hash(net_name))
    return (h % 3, (h // 3) % 3)


NET_Y_MOD: Final = {"GND": 0, "5V_RAIL": 1, "3V3": 2}


def _power_symbol_y(net_name: str, base_y: int) -> int:
    """Snap a power symbol's y to a unique-per-net residue mod 4.

    KiCad ERC falsely merges nets when any two of their pins/symbols share
    a y-coordinate (anywhere on the sheet — not just adjacent). Forcing each
    net's symbols to land on a distinct y-mod-4 residue guarantees that two
    *different* power nets can never produce a pin at the same y, so the
    cross-net cascade can't trigger. Same-net symbols may share y, which is
    fine because they're supposed to be on the same net anyway.
    """
    target = NET_Y_MOD.get(net_name, 3)
    return base_y - (base_y % 4) + target


def _route_pin(sch, comp, pin_num: str, net_name: str, pwr: PwrCounter) -> None:
    """Stub a single pin — power symbol for power nets, NC marker for NC_*, label otherwise."""
    try:
        pin_pos_mm = _real_pin_position(comp, pin_num)
    except Exception:
        return
    if not pin_pos_mm:
        return
    pin_grid = (round(pin_pos_mm.x / 1.27), round(pin_pos_mm.y / 1.27))

    if net_name.startswith("NC_") or net_name.startswith("N$"):
        with contextlib.suppress(Exception):
            sch.no_connects.add(position=(pin_grid[0] * 1.27, pin_grid[1] * 1.27))
        return

    dx, dy = _outward_direction(comp, pin_num)
    # Asymmetric stubs: right/down labels start text AT anchor (extends outward),
    # left/up labels END text at anchor (text extends back toward symbol). Right-side
    # needs a longer stub so visible text isn't crammed against the symbol body.
    stub_len = 8 if (dx > 0 or dy > 0) else 4

    if net_name in POWER_SYMBOL_BY_NET:
        # Snap the power-symbol y to a per-net mod-4 residue so distinct power
        # nets never share a y-coordinate anywhere on the sheet (KiCad ERC's
        # y-coincidence bug uses that to false-merge nets).
        rail_offset = {"GND": 0, "5V_RAIL": 0, "3V3": 2}.get(net_name, 0)
        sym = POWER_SYMBOL_BY_NET[net_name]
        if net_name == "GND":
            base_y = pin_grid[1] + stub_len + rail_offset
        else:
            base_y = pin_grid[1] - stub_len - rail_offset
        end = (pin_grid[0], _power_symbol_y(net_name, base_y))
        with contextlib.suppress(Exception):
            sch.add_wire(start=pin_grid, end=end)
            sch.components.add(sym, pwr.pwr_ref(), sym.split(":")[-1], position=end)
        return

    # Outward-direction stub + label, with rotation matching pin direction.
    # Smaller font (0.8mm) so labels fit within tight pin spacing on big connectors.
    label_pos = (pin_grid[0] + dx * stub_len, pin_grid[1] + dy * stub_len)
    if dx > 0:
        label_rot = 0
    elif dx < 0:
        label_rot = 180
    elif dy > 0:
        label_rot = 270
    else:
        label_rot = 90
    with contextlib.suppress(Exception):
        sch.add_wire(start=pin_grid, end=label_pos)
        sch.add_label(net_name, position=label_pos, rotation=label_rot, size=0.8)


def _add_nc_at_pin(sch, comp, pin_num: str) -> None:
    """Place a no-connect marker at a component pin (mm coords)."""
    try:
        pos_mm = _real_pin_position(comp, pin_num)
    except Exception:
        return
    if not pos_mm:
        return
    with contextlib.suppress(Exception):
        sch.no_connects.add(position=(pos_mm.x, pos_mm.y))


def _place_pwr_flags(sch, pwr: PwrCounter, nets_used: set[str]) -> None:
    """Place ONE PWR_FLAG per used power net with unique x AND y per flag.

    Per kicad's y/x coincidence ERC false-merge bug, every PWR_FLAG must have
    a unique x AND a unique y from every other PWR_FLAG. Use index-based
    diagonal staggering to guarantee both.
    """
    for i, net_name in enumerate(sorted(nets_used)):
        sym = POWER_SYMBOL_BY_NET.get(net_name)
        if not sym:
            continue
        # Each PWR + FLG pair lands on the per-net mod-4 residue (same as inline
        # power-symbol routing) so the FLAG bank can't y-coincide with any other
        # power symbol on the sheet. Wire must be axis-aligned (KiCad treats
        # diagonals as graphics, not connections).
        # x-base 850 puts the bank in the empty right-of-SoM strip on A0
        # (936 grid wide); was 40 on A1 — that crammed the bank against the
        # power block and triggered false-merges.
        x = 850 + i * 30
        y_base = 28 + i * 4
        y = _power_symbol_y(net_name, y_base)
        flg_y = _power_symbol_y(net_name, y - 8)  # FLG below PWR, same residue
        with contextlib.suppress(Exception):
            sch.components.add(sym, pwr.pwr_ref(), sym.split(":")[-1], position=(x, y))
            sch.components.add(
                "power:PWR_FLAG", pwr.flg_ref(), "PWR_FLAG", position=(x, flg_y)
            )
            sch.add_wire(start=(x, y), end=(x, flg_y))


def _route_explicit_nets(
    sch, placed: dict, nets: list[dict], pwr: PwrCounter
) -> tuple[set[tuple[str, str]], set[str]]:
    """Stub each pin per its net (power symbol / NC marker / label). Returns (routed, pwr_nets_used)."""
    routed: set[tuple[str, str]] = set()
    pwr_nets_used: set[str] = set()
    for net in nets:
        if net["name"] in POWER_SYMBOL_BY_NET:
            pwr_nets_used.add(net["name"])
        if len(net["nodes"]) == 1:
            node = net["nodes"][0]
            comp = placed.get(node["ref"])
            if comp:
                _add_nc_at_pin(sch, comp, node["pin"])
                routed.add((node["ref"], node["pin"]))
            continue
        for node in net["nodes"]:
            comp = placed.get(node["ref"])
            if comp:
                _route_pin(sch, comp, node["pin"], net["name"], pwr)
                routed.add((node["ref"], node["pin"]))
    return routed, pwr_nets_used


def _add_orphan_no_connects(sch, placed: dict, routed: set[tuple[str, str]]) -> None:
    """Mark every un-routed pin as no-connect.

    Now that pin positions are computed correctly (via _real_pin_position with
    the y-inversion fix), large parts like BG95-M1 (102 pins, single-unit) work
    fine here too. The earlier >30 pin skip was a workaround for the y-inversion
    bug that's now fixed.
    """
    for ref, comp in placed.items():
        try:
            pins = comp.list_pins()
        except Exception:
            continue
        for pin in pins:
            num = pin["number"]
            if (ref, num) not in routed:
                _add_nc_at_pin(sch, comp, num)


def _power_driven_nets(nets: list[dict]) -> set[str]:
    """Power nets that already have a Power-output driver (regulator output).

    A PWR_FLAG on such a net would conflict with the driver — ERC sees two
    Power-output pins on one net and reports pin_to_pin. Skip them.
    """
    driven: set[str] = set()
    for net in nets:
        for node in net["nodes"]:
            ptype = node.get("pintype", "").upper().replace("_", "-")
            if "POWER-OUT" in ptype:
                driven.add(net["name"])
                break
    return driven


def _label_pins(sch, placed: dict, nets: list[dict]) -> None:
    pwr = PwrCounter()
    routed, pwr_nets_used = _route_explicit_nets(sch, placed, nets, pwr)
    _add_orphan_no_connects(sch, placed, routed)
    flag_nets = pwr_nets_used - _power_driven_nets(nets)
    _place_pwr_flags(sch, pwr, flag_nets)


def build_schematic() -> None:
    """Top-level — emit hierarchical multi-sheet schematic.

    Root .kicad_sch holds one sheet symbol per functional block; each block
    becomes its own dlr_carrier-<block>.kicad_sch child file. Per-sheet ERC
    scope bounds KiCad's y-coincidence false-merge bug.
    """
    from cad.schematic.multi_sheet import (
        build_child_sheet,
        build_root_sheet,
        cross_block_nets,
    )

    spec = yaml.safe_load(LAYOUT_SPEC_PATH.read_text())
    components, nets = _parse_netlist(NETLIST_PATH)
    comp_nets = _comp_nets_index(nets)

    by_block: dict[str, list[dict]] = {}
    for comp in components:
        block = _classify(comp, comp_nets.get(comp["ref"], set()))
        by_block.setdefault(block, []).append(comp)

    cross_nets = cross_block_nets(by_block, nets)
    root_path = Path(SCHEMATIC_PATH)
    block_sheets: list[tuple[str, str, set[str]]] = []

    block_order = [
        "power",
        "som",
        "sensors",
        "cellular",
        "connectors",
        "anemometer",
        "misc",
    ]
    for block_name in block_order:
        comps = by_block.get(block_name, [])
        if not comps:
            continue
        child_filename = f"{root_path.stem}-{block_name}.kicad_sch"
        child_path = str(root_path.parent / child_filename)
        child_cross = build_child_sheet(block_name, comps, nets, cross_nets, child_path)
        block_sheets.append((block_name, child_filename, child_cross))

    build_root_sheet(block_sheets, str(root_path), spec["title"], nets=nets)
    return  # below logic is single-sheet legacy, unreachable

    # === Legacy single-sheet path (kept for reference; unreachable above) ===
    ksa.use_grid_units(True)
    sch = ksa.create_schematic(spec["title"])
    sch.set_paper_size(spec.get("sheet_size", "A1"))
    sch.set_title_block(title=spec["title"], company="Engineering With AI", rev="1.0")

    placed: dict = {}
    for block_name, comps in by_block.items():
        region = spec["blocks"].get(block_name, spec["blocks"]["misc"])
        _draw_block_frame(sch, block_name, region)
        placed.update(_place_block(sch, comps, region))

    _label_pins(sch, placed, nets)
    sch.save_as(SCHEMATIC_PATH)


if __name__ == "__main__":
    build_schematic()
    print(f"Schematic: {SCHEMATIC_PATH}")
