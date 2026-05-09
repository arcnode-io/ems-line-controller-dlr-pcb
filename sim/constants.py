"""Physical parameters for DLR carrier board design.

Mirrors theory.ipynb constants — notebook is the derivation document,
constants.py is the parameter source for sim/test_run.py.
"""

import math
from typing import Final

import pint
from uncertainties import ufloat

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# === Battery: LiFePO4 4S ===
# Reason: 3.2V/cell nominal x 4 = 12.8V; 2.5V cutoff x 4 = 10.0V; 3.65V charge x 4 = 14.6V
V_BAT_NOM: Final = 12.8 * ureg.V
V_BAT_MIN: Final = 10.0 * ureg.V
V_BAT_MAX: Final = 14.6 * ureg.V
BAT_CAPACITY: Final = 4.0 * ureg.A * ureg.hour
BAT_USABLE_FRACTION: Final = 0.90

# === BMS — JBD-SP04S013, on-pack (off-carrier) ===
# Reason: commoditized 4S LiFePO4 protection PCB, mounts to battery pack
BMS_I_DISCHARGE_MAX: Final = 15.0 * ureg.A  # protection trip current
BMS_LOW_TEMP_CUTOFF: Final = 0.0  # degC; charging below this destroys LiFePO4 cells
BMS_QUIESCENT: Final = 150 * ureg.uA  # 0.046 Wh/day continuous battery drain

# === Buck (5V) — TI LMR33630ADDAR, HSOIC-8 ===
# Reason: LMR33630 datasheet SNVSAQ8B Table 7-1; 3.8-36V Vin, 3A integrated FETs
V_RAIL_5V: Final = 5.0 * ureg.V
LMR33630_VIN_MIN: Final = 3.8 * ureg.V
LMR33630_VIN_MAX: Final = 36.0 * ureg.V
LMR33630_IOUT_RATED: Final = 3.0 * ureg.A
LMR33630_FSW: Final = 400 * ureg.kHz  # programmable; 400kHz max efficiency
BUCK_EFFICIENCY: Final = ufloat(0.90, 0.03)  # LMR33630 typical curve at 12V->5V/1.5A
# Reason: 5V bulk cap absorbs CM4 boot inrush (3.92A peak) while buck stays <3A
C_BULK_5V: Final = 470 * ureg.uF

# === LDO (3V3) — Diodes Inc AP2112K-3.3 ===
V_RAIL_3V3: Final = 3.3 * ureg.V
LDO_DROPOUT_AT_600MA: Final = 250 * ureg.mV  # AP2112K datasheet

# === LDO (3V8 cellular) — TI LP5907MFX-3.8, SOT-23-5 ===
# Reason: Quectel BG770A hardware design guide recommends LP5907; ultra-low-noise (6.5 µVrms)
V_RAIL_3V8: Final = 3.8 * ureg.V
LP5907_DROPOUT_AT_250MA: Final = 250 * ureg.mV  # LP5907 datasheet
LP5907_QUIESCENT: Final = 16 * ureg.uA

# === Level shifter (CM4 3.3V <-> BG770A 1.8V) — TI TXS0108E, TSSOP-20 ===
# Reason: 8-ch auto-direction, OD-compatible, Quectel BG770A reference design
V_RAIL_1V8: Final = 1.8 * ureg.V  # sourced from BG770A VDD_EXT output

# === Solar / power budget ===
PANEL_RATING: Final = 20 * ureg.W
PANEL_VMP: Final = 17.0 * ureg.V  # typical 12V-class 20W mono panel
PANEL_VOC: Final = 21.0 * ureg.V
SUN_HOURS_WORST: Final = 2.5 * ureg.hour  # December NE US
SUN_HOURS_AVG: Final = 4.0 * ureg.hour  # Annual avg NE US
MPPT_EFFICIENCY: Final = 0.90
I_5V_PEAK: Final = 3920 * ureg.mA
I_5V_TYPICAL: Final = 1660 * ureg.mA

# === MPPT charger — TI BQ24650RVAR, VQFN-16 ===
# Reason: BQ24650 datasheet SLUSAS9C; programmable charge V/I, true MPPT via VINREG
BQ24650_VIN_MIN: Final = 5.0 * ureg.V
BQ24650_VIN_MAX: Final = 28.0 * ureg.V
BQ24650_VFB_REF: Final = 2.1 * ureg.V  # charge voltage feedback ref
BQ24650_VINREG_REF: Final = 5.0 * ureg.V  # MPPT input regulation ref
BQ24650_ISENSE_FULL: Final = 0.04 * ureg.V  # V across R_SR at full charge current
# Reason: 0.5C charge for LiFePO4 long cycle life on 4 Ah cell = 2 A
BQ24650_I_CHARGE_TARGET: Final = 2.0 * ureg.A
# Reason: 80% of Voc keeps panel near MPP under typical irradiance
BQ24650_VINREG_TARGET: Final = (0.80 * PANEL_VOC.magnitude) * ureg.V

# === Duty cycle (1/min sample, 1/15-min TX) ===
SAMPLE_INTERVAL: Final = 1 * ureg.minute
SAMPLE_DURATION: Final = 5 * ureg.s
TX_INTERVAL: Final = 15 * ureg.minute
TX_DURATION: Final = 5 * ureg.s
I_CM4_IDLE: Final = 120 * ureg.mA
I_CM4_ACTIVE: Final = 1400 * ureg.mA
I_LEPTON_ON: Final = 150 * ureg.mA
I_BG770_PSM: Final = 1 * ureg.mA
I_BG770_TX: Final = 250 * ureg.mA
I_SENSORS_ACTIVE: Final = 9 * ureg.mA

# === I2C (UM10204 Rev 7.0 Table 10, fast mode 400 kHz) ===
V_OL_MAX: Final = 0.4 * ureg.V
I_OL_FAST: Final = 3.0 * ureg.mA
T_RISE_FAST_MAX: Final = 300 * ureg.ns
C_BUS_ESTIMATED: Final = 75 * ureg.pF
R_PULLUP: Final = 2.2 * ureg.kohm  # E24, in 967-4720 ohm range

# === FLIR Lepton SPI ===
F_SPI_MAX: Final = 20 * ureg.MHz
BW_HARMONIC_FACTOR: Final = 5  # 5x f_clk for clean edges

# === FR4 substrate + USB 2.0 ===
EPSILON_R_FR4: Final = 4.3
V_PROP_FR4: Final = 3e8 / math.sqrt(EPSILON_R_FR4) * ureg.m / ureg.s
Z_DIFF_USB_TARGET: Final = 90 * ureg.ohm
USB_SKEW_MAX: Final = 100 * ureg.ps
H_TO_GND: Final = 0.20 * ureg.mm  # F.Cu to In1.GND, 4L 1.6mm fab order
W_TRACE_USB: Final = 0.20 * ureg.mm  # 8 mil
G_GAP_USB: Final = 0.15 * ureg.mm  # 6 mil

# === RF — u.FL connector + Pi-match footprint (Hirose U.FL-R-SMT-1(10)) ===
# Reason: canonical cellular module connector; Pi-network provisioned but not populated by default
Z_RF: Final = 50.0 * ureg.ohm  # antenna feed impedance, 50 ohm microstrip from BG770A
RF_MATCH_SERIES_DEFAULT: Final = 0.0 * ureg.ohm  # default: 0R jumper, no matching
# RF_MATCH_SHUNT_INPUT, RF_MATCH_SHUNT_OUTPUT footprints provisioned, NC by default
