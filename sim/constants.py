"""Physical parameters for CM4 carrier board design.

General-purpose CM4 carrier: 5V screw terminal input with polyfuse and
reverse polarity protection, CP2102N USB-UART debug, I2C + SPI + RS-485
(MAX3485) + GPIO headers on 2.54mm pitch, 100x80mm 2-layer board.
"""

from typing import Final

import pint
from uncertainties import ufloat

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# --- Board geometry ---
BOARD_WIDTH: Final = 100.0 * ureg.mm
BOARD_HEIGHT: Final = 80.0 * ureg.mm

# --- Power input ---
V_IN: Final = 5.0 * ureg.V  # Screw terminal, nominal 5V DC

# --- CM4 load profile ---
# Reason: RPi CM4 datasheet + community measurements (forums.raspberrypi.com)
I_STANDBY: Final = 0.3 * ureg.A  # Idle, no peripherals
I_TYPICAL: Final = 1.4 * ureg.A  # Normal operation, moderate CPU
I_PEAK: Final = 3.0 * ureg.A  # Boot surge + USB + stress test

# --- Polyfuse: Littelfuse 1812L200, 1812 package ---
# Reason: Littelfuse 1812L series datasheet, I_hold = 2A variant
I_HOLD: Final = 2.0 * ureg.A  # Max current without trip (20°C still air)
I_TRIP: Final = 4.0 * ureg.A  # Min current that causes trip
R_POLYFUSE: Final = ufloat(0.050, 0.010) * ureg.ohm  # Typical ±20%

# --- Reverse polarity MOSFET: SI2301 P-channel, SOT-23 ---
# Reason: MCC SI2301 datasheet Rev.4-10222024
V_GS_TH: Final = ufloat(-0.45, 0.15) * ureg.V  # Gate threshold max
RDS_ON: Final = ufloat(0.085, 0.015) * ureg.ohm  # At Vgs=-4.5V, Id=-3A

# --- Voltage budget ---
# Reason: V_rail = V_in - I x R_polyfuse - I x Rds_on - I x R_trace
R_TRACE: Final = ufloat(0.020, 0.005) * ureg.ohm  # PCB trace estimate
V_CM4_MIN: Final = 4.75 * ureg.V  # CM4 minimum input (USB-C spec)

# --- RS-485: MAX3485 transceiver, SO-8 ---
# Reason: Analog Devices MAX3485E datasheet, Table 1
Z0: Final = 120.0 * ureg.ohm  # Twisted pair characteristic impedance
R_TERM: Final = 120.0 * ureg.ohm  # Termination = Z0
# Reason: failsafe bias — idle bus defined state, receiver threshold ±200mV
R_BIAS: Final = 560.0 * ureg.ohm  # A→VCC and B→GND bias resistors
V_DIFF_TH: Final = 0.2 * ureg.V  # Receiver differential sensitivity

# --- I2C: fast mode 400kHz, 4-device bus ---
# Reason: NXP I2C spec UM10204, Rev. 7.0, Table 10 (fast-mode)
F_SCL: Final = 400.0 * ureg.kHz
T_RISE_MAX: Final = 300.0 * ureg.ns  # Max rise time, fast mode
C_BUS: Final = ufloat(100.0, 20.0) * ureg.pF  # 4 devices + traces
V_PULLUP: Final = 3.3 * ureg.V  # I2C supply
I_SINK: Final = 3.0 * ureg.mA  # Fast mode sink current
V_OL: Final = 0.4 * ureg.V  # I2C output low threshold
# Derived: R_min = (Vcc - Vol) / I_sink, R_max = t_rise / (0.8473 x C_bus)
R_PULLUP: Final = 2.2 * ureg.kohm  # E24 standard, within calculated range
