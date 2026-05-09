"""Assert DLR carrier simulation matches theory.ipynb expected values."""

import pytest

from sim.constants import T_RISE_FAST_MAX, Z_DIFF_USB_TARGET, ureg
from sim.model import (
    simulate_battery_autonomy,
    simulate_buck_input_current_peak,
    simulate_daily_energy,
    simulate_i2c_rise_time,
    simulate_ldo_headroom,
    simulate_pv_winter,
    simulate_spi_critical_length,
    simulate_usb_diff_impedance,
)


class TestPowerArchitecture:
    """Buck + LDO derivations match notebook expected values."""

    def test_buck_input_current_at_peak(self) -> None:
        """Buck input at V_BAT_MIN under peak load = 2178 mA +/-5%."""
        # arrange
        expected_ma = 2178.0

        # act
        actual_ma = simulate_buck_input_current_peak()

        # assert
        assert actual_ma == pytest.approx(expected_ma, rel=0.05)

    def test_buck_input_under_battery_1c_limit(self) -> None:
        """Buck input must not exceed 4 Ah cell 1C discharge (4 A)."""
        # act
        i_buck_a = simulate_buck_input_current_peak() / 1000

        # assert
        assert i_buck_a < 4.0

    def test_ldo_headroom_matches_expected(self) -> None:
        """5V - 3.3V - 250mV dropout = 1.45 V."""
        # arrange
        expected_v = 1.45

        # act
        actual_v = simulate_ldo_headroom()

        # assert
        assert actual_v == pytest.approx(expected_v, rel=0.01)


class TestEnergyBudget:
    """Daily energy + solar + battery autonomy."""

    def test_daily_energy_matches_expected(self) -> None:
        """Daily energy = 29.1 Wh +/-5% at 1/min sample, 1/15min TX."""
        # arrange
        expected_wh = 29.1

        # act
        actual_wh = simulate_daily_energy()

        # assert
        assert actual_wh == pytest.approx(expected_wh, rel=0.05)

    def test_winter_pv_margin_at_least_1_5x(self) -> None:
        """20W panel at 2.5 sun-hr must produce >= 1.5x daily budget."""
        # act
        margin = simulate_pv_winter() / simulate_daily_energy()

        # assert
        assert margin >= 1.5

    def test_battery_autonomy_matches_expected(self) -> None:
        """50 Wh battery (90% DoD) gives ~1.58 days autonomy +/-5%."""
        # arrange
        expected_days = 1.58

        # act
        actual_days = simulate_battery_autonomy()

        # assert
        assert actual_days == pytest.approx(expected_days, rel=0.05)


class TestI2CSignalIntegrity:
    """I2C 400 kHz fast mode rise time."""

    def test_i2c_rise_time_under_spec(self) -> None:
        """t_rise at 2.2 kΩ pull-up < 300 ns spec."""
        # arrange
        spec_ns = T_RISE_FAST_MAX.to(ureg.ns).magnitude

        # act
        actual_ns = simulate_i2c_rise_time()

        # assert
        assert actual_ns < spec_ns

    def test_i2c_rise_time_matches_expected(self) -> None:
        """t_rise = 140 ns +/-5% with selected R x C bus."""
        # arrange
        expected_ns = 140.0

        # act
        actual_ns = simulate_i2c_rise_time()

        # assert
        assert actual_ns == pytest.approx(expected_ns, rel=0.05)


class TestSPISignalIntegrity:
    """FLIR Lepton SPI 20 MHz transmission-line threshold."""

    def test_spi_critical_length_matches_expected(self) -> None:
        """L_crit = 254 mm +/-5% at 20 MHz on FR4."""
        # arrange
        expected_mm = 254.0

        # act
        actual_mm = simulate_spi_critical_length()

        # assert
        assert actual_mm == pytest.approx(expected_mm, rel=0.05)

    def test_spi_critical_length_above_design_rule(self) -> None:
        """L_crit/5 must be >= 50 mm trace budget for lumped routing."""
        # act
        budget_mm = simulate_spi_critical_length() / 5

        # assert
        assert budget_mm >= 50.0


class TestUSBDifferentialRouting:
    """USB 2.0 D+/D- diff pair geometry."""

    def test_usb_diff_impedance_in_tolerance(self) -> None:
        """Z_diff within 90 Ω +/-10% USB 2.0 spec."""
        # arrange
        target_ohm = Z_DIFF_USB_TARGET.to(ureg.ohm).magnitude

        # act
        actual_ohm = simulate_usb_diff_impedance()

        # assert
        assert actual_ohm == pytest.approx(target_ohm, rel=0.10)
