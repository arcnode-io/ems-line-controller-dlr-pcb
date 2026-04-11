"""Communication interfaces: RS-485 (MAX3485), USB-UART (CP2102N).

RS-485 half-duplex with termination and failsafe bias.
CP2102N USB-UART bridge for debug console.
"""

import skidl


def build_rs485(
    uart_tx: skidl.Net, uart_rx: skidl.Net, v3v3: skidl.Net, gnd: skidl.Net
) -> None:
    """Wire MAX3485 transceiver with termination and bias."""
    # MAX3485 transceiver
    u_rs485 = skidl.Part(
        "Interface_UART", "MAX3485", footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    )
    u_rs485.value = "MAX3485"

    rs485_a = skidl.Net("RS485_A")
    rs485_b = skidl.Net("RS485_B")
    rs485_de = skidl.Net("RS485_DE")

    v3v3 += u_rs485["VCC"]
    gnd += u_rs485["GND"]
    uart_rx += u_rs485["RO"]
    uart_tx += u_rs485["DI"]
    rs485_de += u_rs485["~{RE}"]
    rs485_de += u_rs485["DE"]
    rs485_a += u_rs485["A"]
    rs485_b += u_rs485["B"]

    # Termination resistor — 120 Ohm across A-B
    r_term = skidl.Part(
        "Device", "R", value="120", footprint="Resistor_SMD:R_0805_2012Metric"
    )
    rs485_a += r_term[1]
    rs485_b += r_term[2]

    # Failsafe bias — A to VCC, B to GND via 560 Ohm
    r_bias_a = skidl.Part(
        "Device", "R", value="560", footprint="Resistor_SMD:R_0603_1608Metric"
    )
    v3v3 += r_bias_a[1]
    rs485_a += r_bias_a[2]

    r_bias_b = skidl.Part(
        "Device", "R", value="560", footprint="Resistor_SMD:R_0603_1608Metric"
    )
    rs485_b += r_bias_b[1]
    gnd += r_bias_b[2]

    # RS-485 header — 4-pin: A, B, DE, GND
    j_rs485 = skidl.Part(
        "Connector_Generic",
        "Conn_01x04",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    )
    j_rs485.value = "RS485"
    rs485_a += j_rs485[1]
    rs485_b += j_rs485[2]
    rs485_de += j_rs485[3]
    gnd += j_rs485[4]

    # Decoupling
    c_rs485 = skidl.Part(
        "Device", "C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric"
    )
    v3v3 += c_rs485[1]
    gnd += c_rs485[2]


def build_usb_uart(
    uart_tx: skidl.Net, uart_rx: skidl.Net, v3v3: skidl.Net, gnd: skidl.Net
) -> None:
    """Wire CP2102N USB-UART bridge with USB connector."""
    u_uart = skidl.Part(
        "Interface_USB",
        "CP2102N-Axx-xQFN20",
        footprint="Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
    )
    u_uart.value = "CP2102N"

    usb_dp = skidl.Net("USB_DP")
    usb_dm = skidl.Net("USB_DM")

    v3v3 += u_uart["VDD"]
    gnd += u_uart["GND"]
    uart_tx += u_uart["RXD"]  # CP2102N RXD receives from CM4 TX
    uart_rx += u_uart["TXD"]  # CP2102N TXD sends to CM4 RX
    usb_dp += u_uart["D+"]
    usb_dm += u_uart["D-"]

    # USB Micro-B connector
    j_usb = skidl.Part(
        "Connector",
        "USB_B_Micro",
        footprint="Connector_USB:USB_Micro-B_Molex_47346-0001",
    )
    j_usb.value = "USB_DEBUG"
    usb_dp += j_usb["D+"]
    usb_dm += j_usb["D-"]
    gnd += j_usb["GND"]
    v3v3 += j_usb["VBUS"]

    # Decoupling
    c_uart = skidl.Part(
        "Device", "C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric"
    )
    v3v3 += c_uart[1]
    gnd += c_uart[2]
