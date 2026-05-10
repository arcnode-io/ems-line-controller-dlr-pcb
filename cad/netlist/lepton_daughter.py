"""Lepton daughterboard — FFC link from main carrier + Lepton mating header.

Per ADR-013: small (~25 × 40 mm) 4-layer PCB that hosts the FLIR Lepton 3.5
module, mounted to a sheet-metal tilt bracket inside the carrier enclosure.
The lens points down through an IR window in the enclosure floor; tilt is
set once at integration and locked with Loctite 243.

Schematic-stage uses a 14-pin THT header as a placeholder for the Lepton
mating socket, mirroring the main carrier's prior J8 convention. PCB layout
swaps the placeholder for the Molex 105028-1001 32-pin SMD socket footprint
(the actual Lepton mating connector) — same pattern as build_assembly.py's
MODEL_OVERRIDES on the main carrier. Pin map preserves the GroupGets 14-pin
breakout signal order so wiring stays identical end-to-end through the FFC.

Outputs:
- cad/lepton_daughter/lepton_daughter.net  — SKiDL-generated netlist
- cad/lepton_daughter/lepton_daughter.kicad_sch — minimal schematic
"""

import os
from pathlib import Path

_SYM_DIR = "/usr/share/kicad/symbols"
for _v in (
    "KICAD_SYMBOL_DIR",
    "KICAD6_SYMBOL_DIR",
    "KICAD7_SYMBOL_DIR",
    "KICAD8_SYMBOL_DIR",
    "KICAD9_SYMBOL_DIR",
):
    os.environ[_v] = _SYM_DIR

import kicad_sch_api as ksa  # noqa: E402
import skidl  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NETLIST_PATH = PROJECT_ROOT / "cad/lepton_daughter/lepton_daughter.net"
SCHEMATIC_PATH = PROJECT_ROOT / "cad/lepton_daughter/lepton_daughter.kicad_sch"
PROJECT_PATH = PROJECT_ROOT / "cad/lepton_daughter/lepton_daughter.kicad_pro"

FP_C_0402 = "Capacitor_SMD:C_0402_1005Metric"
FP_C_0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_FFC_14 = "Connector_FFC-FPC:Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal"
FP_HEADER_14 = "Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical"


def _cap(value: str, fp: str, n1: skidl.Net, n2: skidl.Net) -> None:
    c = skidl.Part("Device", "C", value=value, footprint=fp)
    n1 += c[1]
    n2 += c[2]


def build_netlist() -> None:
    """SKiDL netlist for the Lepton daughterboard."""
    skidl.reset()
    # Power rails (sourced from main PCB through the FFC)
    v3v3 = skidl.Net("3V3")
    gnd = skidl.Net("GND")

    # 14-pin pinout (preserves GroupGets breakout signal order)
    spi_ce0 = skidl.Net("SPI0_CE0")
    spi_mosi = skidl.Net("SPI0_MOSI")
    spi_miso = skidl.Net("SPI0_MISO")
    spi_sck = skidl.Net("SPI0_SCLK")
    vsync = skidl.Net("GPIO25_VSYNC")
    sda = skidl.Net("SDA1")
    scl = skidl.Net("SCL1")
    pwr_dn = skidl.Net("LEPTON_PWR_DN_L")
    reset_n = skidl.Net("LEPTON_RESET_L")
    gpio3 = skidl.Net("LEPTON_GPIO3")

    # 14-pin FFC connector — mate to main PCB J8 FFC
    j_ffc = skidl.Part(
        "Connector_Generic", "Conn_01x14", footprint=FP_FFC_14
    )
    j_ffc.value = "FFC_TO_MAIN"
    gnd += j_ffc[1]
    spi_ce0 += j_ffc[2]
    spi_mosi += j_ffc[3]
    spi_miso += j_ffc[4]
    spi_sck += j_ffc[5]
    vsync += j_ffc[6]
    gpio3 += j_ffc[7]
    sda += j_ffc[8]
    scl += j_ffc[9]
    pwr_dn += j_ffc[10]
    reset_n += j_ffc[11]
    gnd += j_ffc[12]
    v3v3 += j_ffc[13]
    v3v3 += j_ffc[14]

    # Lepton mating header — placeholder for the Molex 32-pin socket. PCB
    # layout swaps this to Connector_PinSocket_1.00mm at the time of layout.
    j_lep = skidl.Part(
        "Connector_Generic", "Conn_01x14", footprint=FP_HEADER_14
    )
    j_lep.value = "LEPTON_SOCKET"
    gnd += j_lep[1]
    spi_ce0 += j_lep[2]
    spi_mosi += j_lep[3]
    spi_miso += j_lep[4]
    spi_sck += j_lep[5]
    vsync += j_lep[6]
    gpio3 += j_lep[7]
    sda += j_lep[8]
    scl += j_lep[9]
    pwr_dn += j_lep[10]
    reset_n += j_lep[11]
    gnd += j_lep[12]
    v3v3 += j_lep[13]
    v3v3 += j_lep[14]

    # Decoupling local to the Lepton VIN — 100 nF + 10 µF on 3V3
    _cap("100nF", FP_C_0402, v3v3, gnd)
    _cap("10uF", FP_C_0805, v3v3, gnd)

    # Pull-ups for active-low Lepton control lines (PWR_DN_L, RESET_L)
    r_pdn = skidl.Part("Device", "R", value="10k", footprint="Resistor_SMD:R_0402_1005Metric")
    pwr_dn += r_pdn[1]
    v3v3 += r_pdn[2]
    r_rst = skidl.Part("Device", "R", value="10k", footprint="Resistor_SMD:R_0402_1005Metric")
    reset_n += r_rst[1]
    v3v3 += r_rst[2]

    skidl.generate_netlist(file_=str(NETLIST_PATH), tool=skidl.KICAD8)


def _real_pin_grid(comp, pin_num: str):
    """Pin position in grid units, applying KiCad's symbol-to-sheet y-inversion."""
    pos = comp.get_pin_position(pin_num)
    if not pos:
        return None
    sym_y = comp.position.y
    real_y = 2 * sym_y - pos.y
    return (round(pos.x / 1.27), round(real_y / 1.27))


def build_schematic() -> None:  # noqa: C901
    """Minimal hand-laid schematic for the daughterboard."""
    pwr_counter = [0]

    def pwr_ref() -> str:
        pwr_counter[0] += 1
        return f"#PWR{pwr_counter[0]:03d}"

    ksa.use_grid_units(True)
    sch = ksa.create_schematic("Lepton Daughterboard")
    sch.set_paper_size("A4")
    sch.set_title_block(
        title="Lepton Daughterboard", company="Engineering With AI", rev="1.0"
    )

    # Two connectors side by side; passives below
    j_ffc = sch.components.add(
        "Connector_Generic:Conn_01x14", "J1", "FFC_TO_MAIN", position=(50, 60)
    )
    j_ffc.footprint = FP_FFC_14

    j_lep = sch.components.add(
        "Connector_Generic:Conn_01x14", "J2", "LEPTON_SOCKET", position=(140, 60)
    )
    j_lep.footprint = FP_HEADER_14

    pin_signals = [
        ("1", "GND"),
        ("2", "SPI0_CE0"),
        ("3", "SPI0_MOSI"),
        ("4", "SPI0_MISO"),
        ("5", "SPI0_SCLK"),
        ("6", "GPIO25_VSYNC"),
        ("7", "LEPTON_GPIO3"),
        ("8", "SDA1"),
        ("9", "SCL1"),
        ("10", "LEPTON_PWR_DN_L"),
        ("11", "LEPTON_RESET_L"),
        ("12", "GND"),
        ("13", "+3V3"),
        ("14", "+3V3"),
    ]

    # Stub each connector pin outward and label / power-symbol it
    for j_comp, sign in [(j_ffc, -1), (j_lep, +1)]:
        for pin_num, label in pin_signals:
            grid = _real_pin_grid(j_comp, pin_num)
            if not grid:
                continue
            stub_end = (grid[0] + sign * 4, grid[1])
            sch.add_wire(start=grid, end=stub_end)
            if label == "GND":
                sch.components.add("power:GND", pwr_ref(), "GND", position=stub_end)
            elif label == "+3V3":
                sch.components.add(
                    "power:+3V3", pwr_ref(), "+3V3", position=stub_end
                )
            else:
                rot = 180 if sign < 0 else 0
                sch.add_label(label, position=stub_end, rotation=rot, size=0.8)

    # Passives row — each cap/resistor vertical, pin 1 at top, pin 2 at bottom
    def _place_passive(lib_id: str, ref: str, value: str, footprint: str,
                       gx: int, top_net: str, bot_net: str) -> None:
        comp = sch.components.add(lib_id, ref, value, position=(gx, 100))
        comp.footprint = footprint
        for pin_num, net_label in (("1", top_net), ("2", bot_net)):
            grid = _real_pin_grid(comp, pin_num)
            if not grid:
                continue
            if net_label == "GND":
                stub_end = (grid[0], grid[1] + 4)
                sch.add_wire(start=grid, end=stub_end)
                sch.components.add("power:GND", pwr_ref(), "GND", position=stub_end)
            elif net_label == "+3V3":
                stub_end = (grid[0], grid[1] - 4)
                sch.add_wire(start=grid, end=stub_end)
                sch.components.add(
                    "power:+3V3", pwr_ref(), "+3V3", position=stub_end
                )
            else:
                # Signal label
                stub_end = (grid[0], grid[1] + 4)
                sch.add_wire(start=grid, end=stub_end)
                sch.add_label(net_label, position=stub_end, rotation=270, size=0.8)

    # C1, C2: 100nF + 10uF decoupling on 3V3
    _place_passive("Device:C", "C1", "100nF", FP_C_0402, 80, "+3V3", "GND")
    _place_passive("Device:C", "C2", "10uF", FP_C_0805, 95, "+3V3", "GND")
    # R1: PWR_DN_L pull-up; R2: RESET_L pull-up
    _place_passive(
        "Device:R", "R1", "10k", "Resistor_SMD:R_0402_1005Metric",
        110, "+3V3", "LEPTON_PWR_DN_L",
    )
    _place_passive(
        "Device:R", "R2", "10k", "Resistor_SMD:R_0402_1005Metric",
        125, "+3V3", "LEPTON_RESET_L",
    )

    # PWR_FLAGs on +3V3 and GND — this board has no native power source; flags
    # tell ERC that both rails are driven from off-board (via the FFC).
    for i, (sym, net) in enumerate([("power:+3V3", "+3V3"), ("power:GND", "GND")]):
        x = 40 + i * 30
        y = 28 + i * 4
        # Match the y-mod-4 trick from main schematic.py: +3V3 lands on residue 2,
        # GND on residue 0 (NET_Y_MOD). Different residues → no false-merge.
        residue = {"+3V3": 2, "GND": 0}[net]
        pwr_y = y - (y % 4) + residue
        flg_y = pwr_y - 8 + ((pwr_y - 8) % 4 - residue) * -1
        flg_y = pwr_y - 8 - ((pwr_y - 8) % 4 - residue) % 4
        sch.components.add(sym, pwr_ref(), net, position=(x, pwr_y))
        sch.components.add("power:PWR_FLAG", f"#FLG{i+1:03d}", "PWR_FLAG", position=(x, flg_y))
        sch.add_wire(start=(x, pwr_y), end=(x, flg_y))

    sch.save_as(str(SCHEMATIC_PATH))


def write_kicad_project() -> None:
    """Write a minimal kicad_pro file pointing at the schematic + (future) PCB."""
    PROJECT_PATH.write_text(
        '{\n'
        '  "meta": {"filename": "lepton_daughter.kicad_pro", "version": 1},\n'
        '  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []}\n'
        '}\n'
    )


if __name__ == "__main__":
    NETLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    build_netlist()
    print(f"Netlist:    {NETLIST_PATH}")
    build_schematic()
    print(f"Schematic:  {SCHEMATIC_PATH}")
    write_kicad_project()
    print(f"Project:    {PROJECT_PATH}")
