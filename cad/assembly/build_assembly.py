"""Build cq.Assembly from pcb_assembly.json — emit GLB + exploded GLB.

Mirrors edp-module-assemblies/src/assemblies/compute_container.py: each
named subassembly becomes a top-level GLB node so the bake pipeline can
bind materials, drive explode animations, and attach hotspots by name.

Run from edp-module-assemblies .venv (cadquery + pygltflib).

CLI:
    python build_assembly.py                   # PCB only (back-compat)
    python build_assembly.py --variant hw      # PCB + Calypso kit
    python build_assembly.py --variant lw      # PCB + Vaisala WMT702 kit
"""

import argparse
import json
import math
from pathlib import Path
from typing import Final

import cadquery as cq

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
JSON_PATH: Final[Path] = REPO_ROOT / "cad/assembly/pcb_assembly.json"
GLB_PATH: Final[Path] = REPO_ROOT / "output/dlr_carrier_pcb.glb"
GLB_EXPLODED: Final[Path] = REPO_ROOT / "output/dlr_carrier_pcb-exploded.glb"
GLB_KIT_HW: Final[Path] = REPO_ROOT / "output/dlr_carrier_kit_hw.glb"
GLB_KIT_HW_EXPLODED: Final[Path] = REPO_ROOT / "output/dlr_carrier_kit_hw-exploded.glb"
GLB_KIT_LW: Final[Path] = REPO_ROOT / "output/dlr_carrier_kit_lw.glb"
GLB_KIT_LW_EXPLODED: Final[Path] = REPO_ROOT / "output/dlr_carrier_kit_lw-exploded.glb"

# ── Field-kit geometry (per project_anemometer_sku.md). Primitives only;
# neither vendor offers a public STEP file. Dimensions from datasheets. ──

# Calypso ULP STD — manual v2.0 §3.1: Ø68 x 65 mm. Polyamide black mushroom:
# wider top band housing the 4 transducers, narrower base.
CALYPSO_TOP_DIA_MM: Final[float] = 68.0
CALYPSO_TOP_H_MM: Final[float] = 18.0
CALYPSO_BASE_DIA_MM: Final[float] = 50.0
CALYPSO_BASE_H_MM: Final[float] = 47.0

# Vaisala WMT702 — datasheet B210917EN-M: 348 x 250 x 285 mm (H x W x Ø).
# Central mast w/ 3 horizontal transducer arms at 120° spacing.
WMT702_MAST_DIA_MM: Final[float] = 50.0
WMT702_MAST_H_MM: Final[float] = 348.0
WMT702_ARM_DIA_MM: Final[float] = 12.0
WMT702_ARM_LEN_MM: Final[float] = 285.0 / 2  # arm reach from mast center
WMT702_ARM_HEIGHT_MM: Final[float] = 300.0  # arms near top of mast
WMT702_TRANSDUCER_DIA_MM: Final[float] = 25.0
WMT702_TRANSDUCER_H_MM: Final[float] = 30.0

# Solar PV (rect prism — generic monocrystalline panel)
PV_HW_W_MM: Final[float] = 270.0  # 20 W panel
PV_HW_D_MM: Final[float] = 220.0
PV_HW_T_MM: Final[float] = 17.0
PV_LW_W_MM: Final[float] = 360.0  # 30 W panel
PV_LW_D_MM: Final[float] = 270.0
PV_LW_T_MM: Final[float] = 25.0

# Battery enclosure (LiFePO4 4S pack in ABS box)
BAT_HW_W_MM: Final[float] = 150.0  # 50 Wh
BAT_HW_D_MM: Final[float] = 100.0
BAT_HW_H_MM: Final[float] = 60.0
BAT_LW_W_MM: Final[float] = 200.0  # 100 Wh
BAT_LW_D_MM: Final[float] = 130.0
BAT_LW_H_MM: Final[float] = 70.0

# Sensor cable (5 m shielded twisted pair, ~5 mm OD per Belden 9842 class)
CABLE_OD_MM: Final[float] = 5.0

# Kit-scene placement (assembled view). PCB stays at origin; kit parts
# arranged as a product-shot layout that fits in a tractable bounding box.
SENSOR_POS_MM: Final[tuple[float, float, float]] = (220.0, 0.0, 80.0)
PV_POS_MM: Final[tuple[float, float, float]] = (0.0, 220.0, 60.0)
BAT_POS_MM: Final[tuple[float, float, float]] = (0.0, -200.0, 30.0)
# Cable endpoints: at PCB's anemo M12 (right edge) and at sensor base
CABLE_PCB_END_MM: Final[tuple[float, float, float]] = (60.0, 0.0, 10.0)
CABLE_SENSOR_END_MM: Final[tuple[float, float, float]] = (220.0, 0.0, 50.0)

# Kit-scene explode offsets — push parts further from PCB in exploded view.
KIT_EXPLODE_DX_MM: Final[float] = 150.0
KIT_EXPLODE_DZ_MM: Final[float] = 80.0

# FLIR Lepton 3.5 mechanical refs — Teledyne FLIR public IDD §3.2 (rev D).
# Sealed metal can with chrome lens bezel, mating to a 32-pin LWM-Group
# socket (Molex 105028-1001 / equivalent) on the carrier.
LEPTON_BODY_W_MM: Final[float] = 11.50
LEPTON_BODY_D_MM: Final[float] = 12.70
LEPTON_BODY_H_MM: Final[float] = 5.91
LEPTON_LENS_BEZEL_DIA_MM: Final[float] = 6.0
LEPTON_LENS_BEZEL_H_MM: Final[float] = 1.0
LEPTON_LENS_APERTURE_DIA_MM: Final[float] = 4.0
# Reason: 2x16 P1.00mm SMD pin socket pedestal (KiCad lib) is ~3.6mm tall.
LEPTON_SOCKET_PEDESTAL_H_MM: Final[float] = 3.6

LEPTON_SOCKET_STEP: Final[Path] = Path(
    "/usr/share/kicad/3dmodels/Connector_PinSocket_1.00mm.3dshapes/"
    "PinSocket_2x16_P1.00mm_Vertical_SMD.step"
)
FFC_J8_STEP: Final[Path] = Path(
    "/usr/share/kicad/3dmodels/Connector_FFC-FPC.3dshapes/"
    "Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal.step"
)
USBC_J12_STEP: Final[Path] = Path(
    "/usr/share/kicad/3dmodels/Connector_USB.3dshapes/"
    "USB_C_Receptacle_GCT_USB4085.step"
)

# Per ADR-013: J8 on the main carrier is now a 14-pin FFC connector (link to
# the Lepton daughterboard, not the Lepton mating connector itself). The
# Lepton lives in its own subassembly built from primitives below — see
# _build_lepton_daughterboard().
MODEL_OVERRIDES: Final[dict[tuple[str, str], Path]] = {
    ("vision_thermal", "J8"): FFC_J8_STEP,
    ("debug_header", "J12"): USBC_J12_STEP,
}

# Lepton daughterboard geometry (per ADR-013)
DAUGHTER_PCB_W_MM: Final[float] = 25.0
DAUGHTER_PCB_D_MM: Final[float] = 40.0
DAUGHTER_PCB_THICKNESS_MM: Final[float] = 1.6
BRACKET_W_MM: Final[float] = 30.0
BRACKET_D_MM: Final[float] = 50.0
BRACKET_THICKNESS_MM: Final[float] = 1.5
DAUGHTER_STANDOFF_H_MM: Final[float] = 2.0
# Reason: -15 deg tilt around the bracket's X-pivot is the integrator-set
# aim that points the Lepton lens at a conductor below the cross-arm. The
# bake pipeline can drive this from a parameter to animate the tilt.
LEPTON_TILT_DEG: Final[float] = -15.0
# Daughterboard sits roughly above the J8 (FFC connector) area on the main
# PCB. Z chosen so that when the bake hides the bracket/PCB/socket scaffolding
# the visible Lepton can+lens floats at the same nominal height the old
# Lepton-on-J8 placement had (PEDESTAL_H above the PCB top surface). The
# exploded view lifts the whole subassembly further via EXPLODE_Z_MM.
DAUGHTER_POS_MM: Final[tuple[float, float, float]] = (-50.0, -12.0, -5.1)

# Reason: Z stagger by group — direction-of-installation hint.
# Power groups lift modestly (board-mounted), connectors and modules lift higher
# (the parts a tech would unplug first when servicing a deployed unit).
EXPLODE_Z_MM: Final[dict[str, float]] = {
    "pcb_board": 0.0,
    "power_harvest": 25.0,
    "power_buck": 30.0,
    "power_ldo": 20.0,
    "atmospherics": 35.0,
    "vision_thermal": 60.0,
    "cm4_socket": 70.0,
    "cellular_modem": 50.0,
    "cellular_io": 55.0,
    "bat_terminal": 45.0,
    "debug_header": 45.0,
    "lepton_daughterboard": 80.0,
}


def _bare_pcb(board: dict) -> cq.Workplane:
    """Make a flat green PCB body at the board outline + origin."""
    w, h, t = board["width_mm"], board["height_mm"], board["thickness_mm"]
    # Reason: place origin at PCB center; build_assembly translates the PCB
    # group so the world origin sits on the board's geometric center.
    return cq.Workplane("XY").box(w, h, t, centered=(True, True, True))


def _world_loc(comp: dict, board: dict) -> cq.Location:
    """Map KiCad mm coords (Y-down) to CadQuery world coords (Y-up).

    KiCad places the component at (x_mm, y_mm) in absolute board mm. The
    bare PCB is centered at (0, 0, 0) in world. Translate by the offset
    from board top-left + flip Y.
    """
    cx = board["left_mm"] + board["width_mm"] / 2
    cy = board["top_mm"] + board["height_mm"] / 2
    dx = comp["x_mm"] - cx
    dy = -(comp["y_mm"] - cy)  # Y flip: KiCad +Y is down, CadQuery +Y is up
    dz = board["thickness_mm"] / 2  # sit components on top of the PCB
    rot = -comp["rotation_deg"]  # KiCad rotates CW; CadQuery CCW
    return cq.Location(cq.Vector(dx, dy, dz), cq.Vector(0, 0, 1), rot)


def _synth_block(comp: dict) -> cq.Workplane:
    """Fallback box when the KiCad library is missing the 3D model."""
    w = max(comp.get("bbox_w_mm") or 2.0, 1.0)
    h = max(comp.get("bbox_h_mm") or 2.0, 1.0)
    return cq.Workplane("XY").box(w, h, 1.5, centered=(True, True, False))


def _lepton_body() -> cq.Workplane:
    """FLIR Lepton 3.5 sealed metal can — Teledyne IDD §3.2 dimensions."""
    return (
        cq.Workplane("XY")
        .box(
            LEPTON_BODY_W_MM,
            LEPTON_BODY_D_MM,
            LEPTON_BODY_H_MM,
            centered=(True, True, False),
        )
        .edges("|Z")
        .fillet(0.4)
    )


def _lepton_lens() -> cq.Workplane:
    """Chrome bezel ring with a recessed aperture — the iconic Lepton 'eye'."""
    bezel = (
        cq.Workplane("XY")
        .circle(LEPTON_LENS_BEZEL_DIA_MM / 2)
        .extrude(LEPTON_LENS_BEZEL_H_MM)
    )
    # Reason: subtract a shallow cup so the aperture reads as a recessed lens
    # under directional light. Depth ~60% of bezel keeps the bezel rim solid.
    aperture = (
        cq.Workplane("XY")
        .workplane(offset=LEPTON_LENS_BEZEL_H_MM)
        .circle(LEPTON_LENS_APERTURE_DIA_MM / 2)
        .extrude(-LEPTON_LENS_BEZEL_H_MM * 0.6)
    )
    return bezel.cut(aperture)


def _daughter_bracket() -> cq.Workplane:
    """Sheet-metal mounting bracket (1.5 mm Al, simplified flat plate)."""
    return cq.Workplane("XY").box(
        BRACKET_W_MM,
        BRACKET_D_MM,
        BRACKET_THICKNESS_MM,
        centered=(True, True, False),
    )


def _daughter_pcb() -> cq.Workplane:
    """Lepton daughterboard PCB body — small 4-layer ~25 x 40 mm."""
    return cq.Workplane("XY").box(
        DAUGHTER_PCB_W_MM,
        DAUGHTER_PCB_D_MM,
        DAUGHTER_PCB_THICKNESS_MM,
        centered=(True, True, False),
    )


def _build_lepton_daughterboard() -> cq.Assembly:
    """Bracket → daughterboard → Molex socket → Lepton can → chrome lens.

    Per ADR-013: bracket holds the daughterboard at a tilt set during
    integration. Z-stack stays in the subassembly's local frame; the parent
    build() rotates the whole subassembly by LEPTON_TILT_DEG to represent
    the aim. Each layer is a named node so the bake pipeline can bind
    distinct materials (matte Al for the bracket, FR4 blue for the PCB,
    gunmetal for the can, chrome for the bezel).
    """
    sub = cq.Assembly(name="lepton_daughterboard")

    sub.add(
        _daughter_bracket(),
        name="lepton_daughterboard__bracket",
        color=cq.Color(0.75, 0.75, 0.78, 1.0),  # brushed aluminium
    )

    pcb_z = BRACKET_THICKNESS_MM + DAUGHTER_STANDOFF_H_MM
    sub.add(
        _daughter_pcb(),
        name="lepton_daughterboard__pcb",
        loc=cq.Location(cq.Vector(0, 0, pcb_z)),
        color=cq.Color(0.05, 0.1, 0.35, 1.0),  # dark blue solder mask
    )

    socket_z = pcb_z + DAUGHTER_PCB_THICKNESS_MM
    try:
        socket = cq.importers.importStep(str(LEPTON_SOCKET_STEP))
        sub.add(
            socket,
            name="lepton_daughterboard__socket",
            loc=cq.Location(cq.Vector(0, 0, socket_z)),
        )
    except Exception as e:
        print(f"  fallback daughter socket: {e}")

    body_z = socket_z + LEPTON_SOCKET_PEDESTAL_H_MM
    sub.add(
        _lepton_body(),
        name="lepton_daughterboard__lepton_body",
        loc=cq.Location(cq.Vector(0, 0, body_z)),
    )
    lens_z = body_z + LEPTON_BODY_H_MM
    sub.add(
        _lepton_lens(),
        name="lepton_daughterboard__lepton_lens",
        loc=cq.Location(cq.Vector(0, 0, lens_z)),
    )
    return sub


def _build_group(name: str, components: list[dict], board: dict) -> cq.Assembly:
    """Build one named subassembly: each component imported and placed."""
    sub = cq.Assembly(name=name)
    for comp in components:
        override = MODEL_OVERRIDES.get((name, comp["ref"]))
        path = str(override) if override else comp.get("model_path")
        if path:
            try:
                shape = cq.importers.importStep(path)
            except Exception as e:
                print(f"  fallback {comp['ref']} ({comp['value']}): {e}")
                shape = _synth_block(comp)
        else:
            shape = _synth_block(comp)
        sub.add(shape, name=f"{name}__{comp['ref']}", loc=_world_loc(comp, board))
    return sub


def build(*, exploded: bool) -> cq.Assembly:
    """Compose the full PCB assembly. exploded=True applies Z-stagger offsets."""
    data = json.loads(JSON_PATH.read_text())
    board = data["board"]
    suffix = "_exploded" if exploded else ""
    assy = cq.Assembly(name=f"dlr_carrier{suffix}")

    pcb_z = EXPLODE_Z_MM["pcb_board"] if exploded else 0.0
    assy.add(
        _bare_pcb(board),
        name="pcb_board",
        loc=cq.Location(cq.Vector(0, 0, pcb_z)),
        color=cq.Color(0.0, 0.4, 0.15, 1.0),
    )

    for group_name, components in data["groups"].items():
        if not components:
            continue
        sub = _build_group(group_name, components, board)
        # Reason: per ADR-013 the Lepton no longer lives on J8 of the main PCB
        # (J8 is now the FFC connector to the daughterboard). The Lepton can +
        # chrome bezel are emitted as part of the lepton_daughterboard
        # subassembly below.
        z_lift = EXPLODE_Z_MM.get(group_name, 0.0) if exploded else 0.0
        assy.add(sub, name=group_name, loc=cq.Location(cq.Vector(0, 0, z_lift)))

    # Lepton daughterboard sits above the main PCB inside the enclosure.
    # In exploded view, lift it further along Z to show the FFC link path.
    daughter = _build_lepton_daughterboard()
    dx, dy, dz_base = DAUGHTER_POS_MM
    dz = dz_base + (EXPLODE_Z_MM["lepton_daughterboard"] - dz_base if exploded else 0.0)
    # Tilt around the X axis so the lens-Z axis rotates toward conductor-side
    daughter_loc = cq.Location(
        cq.Vector(dx, dy, dz), cq.Vector(1, 0, 0), LEPTON_TILT_DEG
    )
    assy.add(daughter, name="lepton_daughterboard", loc=daughter_loc)

    return assy


def _calypso_body() -> cq.Workplane:
    """Calypso ULP STD black mushroom — Ø68 x 65 mm polyamide body (manual v2.0).

    Two stacked cylinders: narrower base + wider top (the toroidal "head"
    housing the 4 transducers). No fillets — circular extrusions have no
    sharp |Z edges to round.
    """
    base = cq.Workplane("XY").circle(CALYPSO_BASE_DIA_MM / 2).extrude(CALYPSO_BASE_H_MM)
    top = (
        cq.Workplane("XY")
        .workplane(offset=CALYPSO_BASE_H_MM)
        .circle(CALYPSO_TOP_DIA_MM / 2)
        .extrude(CALYPSO_TOP_H_MM)
    )
    return base.union(top)


def _wmt702_body() -> cq.Workplane:
    """Vaisala WMT702 stainless mast + 3 transducer arms (datasheet B210917EN)."""
    mast = cq.Workplane("XY").circle(WMT702_MAST_DIA_MM / 2).extrude(WMT702_MAST_H_MM)
    arms = cq.Workplane("XY")
    for deg in (0.0, 120.0, 240.0):
        ang = math.radians(deg)
        tip_x = WMT702_ARM_LEN_MM * math.cos(ang)
        tip_y = WMT702_ARM_LEN_MM * math.sin(ang)
        # horizontal arm cylinder
        arm = (
            cq.Workplane("YZ")
            .center(0, 0)
            .circle(WMT702_ARM_DIA_MM / 2)
            .extrude(WMT702_ARM_LEN_MM)
            .translate((0, 0, WMT702_ARM_HEIGHT_MM))
            .rotate((0, 0, 0), (0, 0, 1), deg)
        )
        # transducer head puck at arm tip
        head = (
            cq.Workplane("XY")
            .workplane(offset=WMT702_ARM_HEIGHT_MM)
            .center(tip_x, tip_y)
            .circle(WMT702_TRANSDUCER_DIA_MM / 2)
            .extrude(WMT702_TRANSDUCER_H_MM)
        )
        arms = arms.union(arm).union(head)
    return mast.union(arms)


def _pv_panel(w: float, d: float, t: float) -> cq.Workplane:
    """Flat rect prism — solar panel face. Material spec gives glassy look in bake."""
    return cq.Workplane("XY").box(w, d, t, centered=(True, True, False))


def _battery_box(w: float, d: float, h: float) -> cq.Workplane:
    """ABS battery enclosure — rounded rect prism."""
    return (
        cq.Workplane("XY")
        .box(w, d, h, centered=(True, True, False))
        .edges("|Z")
        .fillet(6.0)
    )


def _cable(
    start_mm: tuple[float, float, float], end_mm: tuple[float, float, float]
) -> cq.Workplane:
    """Straight cable run between two points — circular cross-section sweep.

    Real cable would arc; for a product-shot view a straight segment reads
    cleanly. Bake spec gives it a black jacket material.
    """
    sx, sy, sz = start_mm
    ex, ey, ez = end_mm
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    # Build a circle on a plane perpendicular to the cable direction and
    # extrude along the direction vector.
    return (
        cq.Workplane("XY")
        .circle(CABLE_OD_MM / 2)
        .extrude(length)
        .translate((sx, sy, sz))
        .rotate((sx, sy, sz), (sx + dx, sy + dy, sz), math.degrees(math.atan2(dy, dx)))
    )


def _build_field_kit(variant: str, *, exploded: bool) -> cq.Assembly:
    """Sensor + cable + PV panel + battery as a top-level kit subassembly.

    Variant determines sensor body geometry and PV/battery sizing per the
    project_anemometer_sku.md kit BOM split.
    """
    if variant not in ("hw", "lw"):
        raise ValueError(f"variant must be 'hw' or 'lw', got {variant!r}")

    kit = cq.Assembly(name=f"field_kit_{variant}")

    # Explode offset: push everything outward radially from PCB origin
    ex_dx = KIT_EXPLODE_DX_MM if exploded else 0.0
    ex_dz = KIT_EXPLODE_DZ_MM if exploded else 0.0

    # Sensor body
    sx, sy, sz = SENSOR_POS_MM
    sensor_loc = cq.Location(cq.Vector(sx + ex_dx, sy, sz + ex_dz))
    if variant == "hw":
        kit.add(
            _calypso_body(),
            name="anemometer_body",  # bake spec material: polyamide black
            loc=sensor_loc,
            color=cq.Color(0.05, 0.05, 0.05, 1.0),
        )
    else:
        kit.add(
            _wmt702_body(),
            name="anemometer_body",  # bake spec material: stainless 316
            loc=sensor_loc,
            color=cq.Color(0.75, 0.75, 0.78, 1.0),
        )

    # Cable from PCB to sensor — kit-level node so bake can color it
    # NB: cable endpoints stay anchored to PCB regardless of explode (cable
    # would visibly stretch in exploded view, which is fine for a product shot).
    cable_end = (
        CABLE_SENSOR_END_MM[0] + ex_dx,
        CABLE_SENSOR_END_MM[1],
        CABLE_SENSOR_END_MM[2] + ex_dz,
    )
    kit.add(
        _cable(CABLE_PCB_END_MM, cable_end),
        name="sensor_cable",
        color=cq.Color(0.15, 0.15, 0.15, 1.0),
    )

    # Solar panel
    pv_w, pv_d, pv_t = (
        (PV_HW_W_MM, PV_HW_D_MM, PV_HW_T_MM)
        if variant == "hw"
        else (PV_LW_W_MM, PV_LW_D_MM, PV_LW_T_MM)
    )
    pv_x, pv_y, pv_z = PV_POS_MM
    pv_y_off = pv_y + (ex_dx if exploded else 0.0)  # push PV away in +Y on explode
    kit.add(
        _pv_panel(pv_w, pv_d, pv_t),
        name="pv_panel",
        loc=cq.Location(cq.Vector(pv_x, pv_y_off, pv_z + ex_dz)),
        color=cq.Color(0.05, 0.15, 0.4, 1.0),
    )

    # Battery box
    bat_w, bat_d, bat_h = (
        (BAT_HW_W_MM, BAT_HW_D_MM, BAT_HW_H_MM)
        if variant == "hw"
        else (BAT_LW_W_MM, BAT_LW_D_MM, BAT_LW_H_MM)
    )
    bx, by, bz = BAT_POS_MM
    by_off = by - (ex_dx if exploded else 0.0)  # push battery away in -Y on explode
    kit.add(
        _battery_box(bat_w, bat_d, bat_h),
        name="battery_pack",
        loc=cq.Location(cq.Vector(bx, by_off, bz)),
        color=cq.Color(0.85, 0.85, 0.85, 1.0),
    )

    return kit


def main() -> None:
    """Emit GLBs. Default: PCB only (back-compat). --variant: PCB + field kit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=["pcb", "hw", "lw", "all"],
        default="pcb",
        help="pcb=PCB only (back-compat); hw/lw=add field-kit; all=emit every GLB",
    )
    args = parser.parse_args()

    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _emit_with_kit(variant: str, out_assy: Path, out_exp: Path) -> None:
        for exploded, path in ((False, out_assy), (True, out_exp)):
            assy = build(exploded=exploded)
            assy.add(
                _build_field_kit(variant, exploded=exploded),
                name=f"field_kit_{variant}",
            )
            assy.export(str(path))
            print(
                f"GLB ({variant}, exp={exploded}): {path}  ({path.stat().st_size // 1024} KB)"
            )

    if args.variant in ("pcb", "all"):
        build(exploded=False).export(str(GLB_PATH))
        print(f"GLB:          {GLB_PATH}  ({GLB_PATH.stat().st_size // 1024} KB)")
        build(exploded=True).export(str(GLB_EXPLODED))
        print(
            f"GLB exploded: {GLB_EXPLODED}  ({GLB_EXPLODED.stat().st_size // 1024} KB)"
        )

    if args.variant in ("hw", "all"):
        _emit_with_kit("hw", GLB_KIT_HW, GLB_KIT_HW_EXPLODED)

    if args.variant in ("lw", "all"):
        _emit_with_kit("lw", GLB_KIT_LW, GLB_KIT_LW_EXPLODED)


if __name__ == "__main__":
    main()
