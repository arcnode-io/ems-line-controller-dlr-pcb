"""DLR carrier board top-level netlist.

Wires power chain (solar -> MPPT -> battery -> buck -> LDOs) to:
  - CM4 SoM (som.py)
  - Cellular interface (cellular.py): BG770A + TXS0108E + u.FL
  - IEEE 738 sensors (sensors.py): FLIR + DHT22 + SI1145 + ADS1115/YL-83
  - Off-board connectors (connectors.py): battery + debug UART
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

from cad.netlist.cellular import build_cellular  # noqa: E402
from cad.netlist.connectors import (  # noqa: E402
    build_battery_connector,
    build_debug_header,
)
from cad.netlist.power import (  # noqa: E402
    build_buck_5v,
    build_ldo_3v3,
    build_ldo_3v8,
    build_mppt_charger,
    build_solar_input,
)
from cad.netlist.sensors import build_sensors  # noqa: E402
from cad.netlist.som import build_cm4  # noqa: E402

NETLIST_PATH = "cad/dlr_carrier.net"


def build_netlist() -> None:
    """Define DLR carrier board in SKiDL and generate KiCad netlist."""
    # Power rails
    pv_in = skidl.Net("PV_IN")
    vbat = skidl.Net("VBAT")
    v5_rail = skidl.Net("5V_RAIL")
    v3v3 = skidl.Net("3V3")
    v3v8 = skidl.Net("3V8_CELL")
    gnd = skidl.Net("GND")

    # CM4 GPIO buses
    sda = skidl.Net("SDA1")
    scl = skidl.Net("SCL1")
    spi_mosi = skidl.Net("SPI0_MOSI")
    spi_miso = skidl.Net("SPI0_MISO")
    spi_sck = skidl.Net("SPI0_SCLK")
    spi_ce0 = skidl.Net("SPI0_CE0")
    uart_tx = skidl.Net("UART_TX_3V3")
    uart_rx = skidl.Net("UART_RX_3V3")
    gpio4 = skidl.Net("GPIO4_DHT22")
    gpio25 = skidl.Net("GPIO25_VSYNC")
    cell_en = skidl.Net("CELL_EN")
    usb_dp = skidl.Net("USB_DP")
    usb_dm = skidl.Net("USB_DM")
    pwrkey = skidl.Net("CELL_PWRKEY")
    reset_n = skidl.Net("CELL_RESET")
    status = skidl.Net("CELL_STATUS")
    net_status = skidl.Net("CELL_NET_STATUS")
    shifter_oe = skidl.Net("SHIFTER_OE")
    dbg_tx = skidl.Net("DBG_TX")
    dbg_rx = skidl.Net("DBG_RX")

    # Power chain
    build_solar_input(pv_in, gnd)
    build_mppt_charger(pv_in, vbat, gnd)
    build_battery_connector(vbat, gnd)
    build_buck_5v(vbat, v5_rail, gnd)
    build_ldo_3v3(v5_rail, v3v3, gnd)
    build_ldo_3v8(v5_rail, v3v8, cell_en, gnd)

    # SoM + consumers
    build_cm4(
        v5_in=v5_rail,
        v3v3=v3v3,
        gnd=gnd,
        sda=sda,
        scl=scl,
        spi_mosi=spi_mosi,
        spi_miso=spi_miso,
        spi_sck=spi_sck,
        spi_ce0=spi_ce0,
        uart_tx=uart_tx,
        uart_rx=uart_rx,
        gpio4=gpio4,
        gpio25=gpio25,
        cell_en=cell_en,
        usb_dp=usb_dp,
        usb_dm=usb_dm,
        pwrkey=pwrkey,
        reset_n=reset_n,
        status=status,
        net_status=net_status,
        shifter_oe=shifter_oe,
        dbg_tx=dbg_tx,
        dbg_rx=dbg_rx,
    )
    build_cellular(
        v3v8=v3v8,
        v3v3=v3v3,
        gnd=gnd,
        usb_dp=usb_dp,
        usb_dm=usb_dm,
        uart_tx_cm4=uart_tx,
        uart_rx_cm4=uart_rx,
        pwrkey=pwrkey,
        reset_n=reset_n,
        status=status,
        net_status=net_status,
        shifter_oe=shifter_oe,
    )
    build_sensors(
        v3v3=v3v3,
        gnd=gnd,
        sda=sda,
        scl=scl,
        spi_mosi=spi_mosi,
        spi_miso=spi_miso,
        spi_sck=spi_sck,
        spi_ce0=spi_ce0,
        gpio4=gpio4,
        gpio25=gpio25,
    )
    build_debug_header(v3v3, gnd, dbg_tx, dbg_rx)

    skidl.generate_netlist(file_=NETLIST_PATH, tool=skidl.KICAD8)


if __name__ == "__main__":
    build_netlist()
    print(f"Netlist: {NETLIST_PATH}")
