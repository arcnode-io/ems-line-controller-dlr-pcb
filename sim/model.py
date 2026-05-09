"""DLR carrier board simulation — power and signal integrity.

Mirrors theory.ipynb derivations as callable functions for test_run.py.
Each function returns a plain float in the unit named in its docstring.
"""

import math

from sim.constants import (
    BAT_CAPACITY,
    BAT_USABLE_FRACTION,
    BUCK_EFFICIENCY,
    BW_HARMONIC_FACTOR,
    C_BUS_ESTIMATED,
    EPSILON_R_FR4,
    F_SPI_MAX,
    G_GAP_USB,
    H_TO_GND,
    I_5V_PEAK,
    I_BG770_PSM,
    I_BG770_TX,
    I_CM4_ACTIVE,
    I_CM4_IDLE,
    I_LEPTON_ON,
    I_SENSORS_ACTIVE,
    LDO_DROPOUT_AT_600MA,
    MPPT_EFFICIENCY,
    PANEL_RATING,
    R_PULLUP,
    SAMPLE_DURATION,
    SAMPLE_INTERVAL,
    SUN_HOURS_WORST,
    TX_DURATION,
    TX_INTERVAL,
    V_BAT_MIN,
    V_BAT_NOM,
    V_PROP_FR4,
    V_RAIL_3V3,
    V_RAIL_5V,
    W_TRACE_USB,
    ureg,
)


def simulate_buck_input_current_peak() -> float:
    """Buck input current at peak load with worst-case battery voltage. Returns mA."""
    eta = BUCK_EFFICIENCY.nominal_value
    i = (V_RAIL_5V * I_5V_PEAK) / (V_BAT_MIN * eta)
    return i.to(ureg.mA).magnitude


def simulate_ldo_headroom() -> float:
    """V_in headroom above (V_out + V_dropout) for the 3V3 LDO. Returns V."""
    headroom = V_RAIL_5V - V_RAIL_3V3 - LDO_DROPOUT_AT_600MA
    return headroom.to(ureg.V).magnitude


def _avg_current_q():
    """Internal helper — average current as a pint Quantity (mA)."""
    sample_duty = (SAMPLE_DURATION / SAMPLE_INTERVAL).to(ureg.dimensionless).magnitude
    tx_duty = (TX_DURATION / TX_INTERVAL).to(ureg.dimensionless).magnitude
    return (
        I_CM4_IDLE
        + (I_CM4_ACTIVE - I_CM4_IDLE) * sample_duty
        + I_LEPTON_ON * sample_duty
        + I_BG770_PSM
        + (I_BG770_TX - I_BG770_PSM) * tx_duty
        + I_SENSORS_ACTIVE * sample_duty
    )


def simulate_daily_energy() -> float:
    """Average current x 5V x 24h. Returns Wh."""
    e = _avg_current_q() * V_RAIL_5V * (24 * ureg.hour)
    return e.to(ureg.W * ureg.hour).magnitude


def simulate_pv_winter() -> float:
    """Solar production at winter worst-case sun hours. Returns Wh."""
    e = PANEL_RATING * SUN_HOURS_WORST * MPPT_EFFICIENCY
    return e.to(ureg.W * ureg.hour).magnitude


def simulate_battery_autonomy() -> float:
    """Days of operation at zero PV production. Returns days."""
    e_bat = V_BAT_NOM * BAT_CAPACITY * BAT_USABLE_FRACTION
    e_daily = _avg_current_q() * V_RAIL_5V * (24 * ureg.hour)
    return (e_bat / e_daily).to(ureg.dimensionless).magnitude


def simulate_i2c_rise_time() -> float:
    """I2C rise time with selected pull-up. Returns ns. t_rise = 0.8473 * R * C."""
    t = 0.8473 * R_PULLUP * C_BUS_ESTIMATED
    return t.to(ureg.ns).magnitude


def simulate_spi_critical_length() -> float:
    """Trace length above which TL behavior matters at FLIR Lepton SPI rate. Returns mm."""
    bw = BW_HARMONIC_FACTOR * F_SPI_MAX
    t_rise = 0.35 / bw
    l_crit = t_rise * V_PROP_FR4 / 2
    return l_crit.to(ureg.mm).magnitude


def simulate_usb_diff_impedance() -> float:
    """Differential impedance of edge-coupled microstrip USB pair (Wadell). Returns Ω."""
    h = H_TO_GND.to(ureg.mm).magnitude
    w = W_TRACE_USB.to(ureg.mm).magnitude
    s = G_GAP_USB.to(ureg.mm).magnitude
    z0 = (60 / math.sqrt(EPSILON_R_FR4)) * math.log(8 * h / w + w / (4 * h))
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s / h))
