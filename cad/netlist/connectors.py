"""Off-board connectors: battery (BAT+/BAT-) and debug UART header."""

import skidl


def build_battery_connector(vbat: skidl.Net, gnd: skidl.Net) -> None:
    """2-pin battery input — BMS lives on-pack (ADR-009), carrier sees protected pack."""
    j = skidl.Part(
        "Connector_Generic",
        "Conn_01x02",
        footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    )
    j.value = "BAT"
    vbat += j[1]
    gnd += j[2]


def build_debug_header(
    v3v3: skidl.Net, gnd: skidl.Net, dbg_tx: skidl.Net, dbg_rx: skidl.Net
) -> None:
    """4-pin debug UART header (3V3, TX, RX, GND) for serial console."""
    j = skidl.Part(
        "Connector_Generic",
        "Conn_01x04",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    )
    j.value = "DEBUG_UART"
    v3v3 += j[1]
    dbg_tx += j[2]
    dbg_rx += j[3]
    gnd += j[4]
