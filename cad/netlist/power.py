"""Power input section: screw terminal, polyfuse, reverse polarity MOSFET.

5V screw terminal -> polyfuse (1812L200) -> SI2301 P-FET -> 5V_RAIL
"""

import skidl


def build_power(v5_in: skidl.Net, v5_rail: skidl.Net, gnd: skidl.Net) -> None:
    """Wire power input protection between screw terminal and 5V rail."""
    # Screw terminal — 5.08mm pitch, 2-position
    j_pwr = skidl.Part(
        "Connector_Generic",
        "Conn_01x02",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    )
    j_pwr.value = "5V_IN"
    v5_in += j_pwr[1]
    gnd += j_pwr[2]

    # Polyfuse — Littelfuse 1812L200
    fuse = skidl.Part("Device", "Polyfuse", footprint="Fuse:Fuse_1812_4532Metric")
    fuse.value = "2A"
    fuse_out = skidl.Net("FUSE_OUT")
    v5_in += fuse[1]
    fuse_out += fuse[2]

    # Reverse polarity MOSFET — SI2301 P-channel
    # Reason: gate to GND, source to fuse_out, drain to rail
    # Normal polarity: Vgs = 0 - 5V = -5V, FET on (Rds_on path)
    # Reverse polarity: Vgs = 0 - (-5V) = +5V, FET off (blocks)
    q_prot = skidl.Part(
        "Transistor_FET", "Q_PMOS_GSD", footprint="Package_TO_SOT_SMD:SOT-23"
    )
    q_prot.value = "SI2301"
    fuse_out += q_prot["S"]
    v5_rail += q_prot["D"]
    gnd += q_prot["G"]

    # Bulk capacitors on 5V rail
    c_bulk = skidl.Part(
        "Device", "C", value="100uF", footprint="Capacitor_SMD:C_1210_3225Metric"
    )
    v5_rail += c_bulk[1]
    gnd += c_bulk[2]

    c_decoup = skidl.Part(
        "Device", "C", value="10uF", footprint="Capacitor_SMD:C_0805_2012Metric"
    )
    v5_rail += c_decoup[1]
    gnd += c_decoup[2]
