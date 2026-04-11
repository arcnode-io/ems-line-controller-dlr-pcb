"""CM4 carrier board power and signal integrity simulation.

Validates power rail voltage budget under load, I2C rise time with
selected pull-up, and RS-485 failsafe bias voltage.
"""

from sim.constants import ureg

Q_ = ureg.Quantity


def simulate_power_rail(i_load: Q_) -> float:
    """Simulate 5V rail under given load current.

    Returns:
        Rail voltage in volts (float) after polyfuse + MOSFET + trace drops.
    """
    from sim.constants import R_POLYFUSE, R_TRACE, RDS_ON, V_IN

    # Reason: series path — V_rail = V_in - I * (R_fuse + R_fet + R_trace)
    v_in = V_IN.to(ureg.V).magnitude
    i = i_load.to(ureg.A).magnitude
    r_total = (
        R_POLYFUSE.magnitude.nominal_value
        + RDS_ON.magnitude.nominal_value
        + R_TRACE.magnitude.nominal_value
    )

    return v_in - i * r_total


def simulate_i2c_rise_time() -> float:
    """Simulate I2C SDA/SCL rise time with selected pull-up resistor.

    Returns:
        Rise time in nanoseconds (float).
    """
    from sim.constants import C_BUS, R_PULLUP

    # Reason: t_rise = 0.8473 * R * C (RC charge to 70% of Vcc)
    r = R_PULLUP.to(ureg.ohm).magnitude
    c = C_BUS.magnitude.nominal_value * 1e-12  # pF to F

    t_rise_s = 0.8473 * r * c
    return t_rise_s * 1e9  # convert to ns


def simulate_rs485_bias() -> float:
    """Simulate RS-485 idle bus differential voltage with bias network.

    Returns:
        Differential voltage in volts (float).
    """
    from sim.constants import R_BIAS, R_TERM, V_PULLUP

    # Reason: A pulled to Vcc via R_bias, B to GND via R_bias, R_term across A-B
    v_cc = V_PULLUP.to(ureg.V).magnitude
    r_t = R_TERM.to(ureg.ohm).magnitude
    r_b = R_BIAS.to(ureg.ohm).magnitude

    v_diff = v_cc * r_t / (r_t + 2 * r_b)
    return v_diff
