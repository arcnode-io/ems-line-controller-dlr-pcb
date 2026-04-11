"""I/O breakout headers: I2C, SPI, GPIO.

All headers on 2.54mm pitch pin headers for breadboard compatibility.
I2C includes pull-up resistors to 3.3V.
"""

import skidl


def build_i2c_header(
    sda: skidl.Net, scl: skidl.Net, v3v3: skidl.Net, gnd: skidl.Net
) -> None:
    """Wire I2C header with pull-up resistors."""
    # Pull-ups — 2.2kOhm to 3.3V (fast mode, 100pF bus)
    r_sda = skidl.Part(
        "Device", "R", value="2.2k", footprint="Resistor_SMD:R_0603_1608Metric"
    )
    v3v3 += r_sda[1]
    sda += r_sda[2]

    r_scl = skidl.Part(
        "Device", "R", value="2.2k", footprint="Resistor_SMD:R_0603_1608Metric"
    )
    v3v3 += r_scl[1]
    scl += r_scl[2]

    # 4-pin header: VCC, SDA, SCL, GND
    j_i2c = skidl.Part(
        "Connector_Generic",
        "Conn_01x04",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    )
    j_i2c.value = "I2C"
    v3v3 += j_i2c[1]
    sda += j_i2c[2]
    scl += j_i2c[3]
    gnd += j_i2c[4]


def build_spi_header(
    mosi: skidl.Net,
    miso: skidl.Net,
    sck: skidl.Net,
    cs: skidl.Net,
    v3v3: skidl.Net,
    gnd: skidl.Net,
) -> None:
    """Wire SPI header — 6-pin: VCC, MOSI, MISO, SCK, CS, GND."""
    j_spi = skidl.Part(
        "Connector_Generic",
        "Conn_01x06",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
    )
    j_spi.value = "SPI"
    v3v3 += j_spi[1]
    mosi += j_spi[2]
    miso += j_spi[3]
    sck += j_spi[4]
    cs += j_spi[5]
    gnd += j_spi[6]


def build_gpio_header(v3v3: skidl.Net, gnd: skidl.Net) -> None:
    """Wire GPIO header — 8-pin: VCC, 6x GPIO, GND."""
    gpio_nets = [skidl.Net(f"GPIO{i}") for i in range(6)]

    j_gpio = skidl.Part(
        "Connector_Generic",
        "Conn_01x08",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
    )
    j_gpio.value = "GPIO"
    v3v3 += j_gpio[1]
    for i in range(len(gpio_nets)):
        gpio_nets[i] += j_gpio[i + 2]
    gnd += j_gpio[8]
