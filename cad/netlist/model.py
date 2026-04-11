"""CM4 carrier board netlist generation.

SKiDL defines the circuit topology -> KiCad netlist.
Modular: power, comms, and I/O sections in separate files.
"""

import os

_SYM_DIR = "/usr/share/kicad/symbols"
for v in (
    "KICAD_SYMBOL_DIR",
    "KICAD6_SYMBOL_DIR",
    "KICAD7_SYMBOL_DIR",
    "KICAD8_SYMBOL_DIR",
    "KICAD9_SYMBOL_DIR",
):
    os.environ[v] = _SYM_DIR

import skidl  # noqa: E402

from cad.netlist.comms import build_rs485, build_usb_uart  # noqa: E402
from cad.netlist.io_headers import (  # noqa: E402
    build_gpio_header,
    build_i2c_header,
    build_spi_header,
)
from cad.netlist.power import build_power  # noqa: E402

NETLIST_PATH = "cad/cm4_carrier.net"


def build_netlist() -> None:
    """Define CM4 carrier board in SKiDL and generate KiCad netlist."""
    v5_in = skidl.Net("5V_IN")
    v5_rail = skidl.Net("5V_RAIL")
    v3v3 = skidl.Net("3V3")
    gnd = skidl.Net("GND")

    uart_tx = skidl.Net("UART_TX")
    uart_rx = skidl.Net("UART_RX")
    sda = skidl.Net("SDA")
    scl = skidl.Net("SCL")
    mosi = skidl.Net("MOSI")
    miso = skidl.Net("MISO")
    sck = skidl.Net("SCK")
    cs = skidl.Net("SPI_CS0")
    rs485_tx = skidl.Net("RS485_TX")
    rs485_rx = skidl.Net("RS485_RX")

    build_power(v5_in, v5_rail, gnd)
    _build_cm4_connector(
        v5_rail,
        v3v3,
        gnd,
        uart_tx,
        uart_rx,
        sda,
        scl,
        mosi,
        miso,
        sck,
        cs,
        rs485_tx,
        rs485_rx,
    )
    build_rs485(rs485_tx, rs485_rx, v3v3, gnd)
    build_usb_uart(uart_tx, uart_rx, v3v3, gnd)
    build_i2c_header(sda, scl, v3v3, gnd)
    build_spi_header(mosi, miso, sck, cs, v3v3, gnd)
    build_gpio_header(v3v3, gnd)
    _build_decoupling(v3v3, gnd, count=4)

    skidl.generate_netlist(file_=NETLIST_PATH, tool=skidl.KICAD8)


def _build_cm4_connector(
    v5_rail: skidl.Net,
    v3v3: skidl.Net,
    gnd: skidl.Net,
    uart_tx: skidl.Net,
    uart_rx: skidl.Net,
    sda: skidl.Net,
    scl: skidl.Net,
    mosi: skidl.Net,
    miso: skidl.Net,
    sck: skidl.Net,
    cs: skidl.Net,
    rs485_tx: skidl.Net,
    rs485_rx: skidl.Net,
) -> None:
    """CM4 module connector — 2x20 header as DF40 placeholder."""
    # Reason: Hirose DF40 100-pin not in standard KiCad libs
    j = skidl.Part(
        "Connector_Generic",
        "Conn_02x20_Odd_Even",
        footprint="Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical",
    )
    j.value = "CM4"
    # Reason: pin assignments per RPi CM4 datasheet GPIO header
    v5_rail += j[1]
    gnd += j[2]
    v5_rail += j[3]
    gnd += j[4]
    v3v3 += j[5]
    sda += j[7]
    scl += j[9]
    uart_tx += j[11]
    uart_rx += j[13]
    mosi += j[15]
    miso += j[17]
    sck += j[19]
    cs += j[21]
    rs485_tx += j[23]
    rs485_rx += j[25]


def _build_decoupling(v3v3: skidl.Net, gnd: skidl.Net, count: int) -> None:
    """Add 100nF decoupling caps for CM4."""
    for _ in range(count):
        c = skidl.Part(
            "Device",
            "C",
            value="100nF",
            footprint="Capacitor_SMD:C_0402_1005Metric",
        )
        v3v3 += c[1]
        gnd += c[2]


if __name__ == "__main__":
    build_netlist()
    print(f"Netlist: {NETLIST_PATH}")
