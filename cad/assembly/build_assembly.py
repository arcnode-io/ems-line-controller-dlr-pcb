"""Build cq.Assembly from pcb_assembly.json — emit GLB + exploded GLB.

Mirrors edp-module-assemblies/src/assemblies/compute_container.py: each
named subassembly becomes a top-level GLB node so the bake pipeline can
bind materials, drive explode animations, and attach hotspots by name.

Run from edp-module-assemblies .venv (cadquery + pygltflib).
"""

import json
from pathlib import Path
from typing import Final

import cadquery as cq

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
JSON_PATH: Final[Path] = REPO_ROOT / "cad/assembly/pcb_assembly.json"
GLB_PATH: Final[Path] = REPO_ROOT / "output/dlr_carrier_pcb.glb"
GLB_EXPLODED: Final[Path] = REPO_ROOT / "output/dlr_carrier_pcb-exploded.glb"

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
# Daughterboard sits above the main carrier J8 position; offset chosen so
# the marketing render shows the FFC link conceptually between the two.
DAUGHTER_POS_MM: Final[tuple[float, float, float]] = (-30.0, 0.0, 45.0)

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


def main() -> None:
    """Emit assembled + exploded GLBs."""
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    build(exploded=False).export(str(GLB_PATH))
    print(f"GLB:          {GLB_PATH}  ({GLB_PATH.stat().st_size//1024} KB)")
    build(exploded=True).export(str(GLB_EXPLODED))
    print(f"GLB exploded: {GLB_EXPLODED}  ({GLB_EXPLODED.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
