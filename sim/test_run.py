"""Assert CM4 carrier board simulation matches analytical expected values."""

from sim.constants import (
    I_HOLD,
    I_TYPICAL,
    T_RISE_MAX,
    V_CM4_MIN,
    V_DIFF_TH,
    ureg,
)
from sim.model import simulate_i2c_rise_time, simulate_power_rail, simulate_rs485_bias


class TestPowerRail:
    """Power rail voltage budget assertions against theory.ipynb."""

    def test_rail_voltage_at_typical_load(self) -> None:
        """V_rail at 1.4A must exceed CM4 minimum (4.75V)."""
        # arrange
        v_min = V_CM4_MIN.to(ureg.V).magnitude

        # act
        v_rail = simulate_power_rail(I_TYPICAL)

        # assert
        assert v_rail > v_min

    def test_polyfuse_no_nuisance_trip(self) -> None:
        """Polyfuse must not trip at typical load. I_typical / I_hold < 1."""
        # arrange — pure constants check, no simulation needed
        ratio = (I_TYPICAL / I_HOLD).to(ureg.dimensionless).magnitude

        # assert
        assert ratio < 1.0


class TestSignalIntegrity:
    """Signal integrity assertions against theory.ipynb."""

    def test_i2c_rise_time(self) -> None:
        """I2C rise time with selected pull-up must be under 300ns."""
        # arrange
        t_max_ns = T_RISE_MAX.to(ureg.ns).magnitude

        # act
        t_rise_ns = simulate_i2c_rise_time()

        # assert
        assert t_rise_ns < t_max_ns

    def test_rs485_idle_bias(self) -> None:
        """RS-485 idle bus differential must exceed receiver threshold."""
        # arrange
        v_threshold = V_DIFF_TH.to(ureg.V).magnitude

        # act
        v_diff = simulate_rs485_bias()

        # assert
        assert v_diff > v_threshold
