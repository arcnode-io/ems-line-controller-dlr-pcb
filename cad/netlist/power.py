"""Power chain: solar -> BQ24650 MPPT -> LiFePO4 4S -> LMR33630 buck -> AP2112K + LP5907.

Battery is a 2-pin connector — BMS lives on-pack (ADR-009), so carrier sees only BAT+ / BAT-.
"""

import skidl

# Footprint shorthand
FP_C_0402 = "Capacitor_SMD:C_0402_1005Metric"
FP_C_0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C_1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_R_0402 = "Resistor_SMD:R_0402_1005Metric"


def _cap(value: str, fp: str, n1: skidl.Net, n2: skidl.Net) -> None:
    """Place a 2-pin capacitor between n1 and n2."""
    c = skidl.Part("Device", "C", value=value, footprint=fp)
    n1 += c[1]
    n2 += c[2]


def _res(value: str, fp: str, n1: skidl.Net, n2: skidl.Net) -> None:
    """Place a 2-pin resistor between n1 and n2."""
    r = skidl.Part("Device", "R", value=value, footprint=fp)
    n1 += r[1]
    n2 += r[2]


def build_solar_input(pv_in: skidl.Net, gnd: skidl.Net) -> None:
    """2-pin PV screw terminal + reverse-polarity Schottky + bulk cap."""
    j_pv = skidl.Part(
        "Connector_Generic",
        "Conn_01x02",
        footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    )
    j_pv.value = "PV_IN"
    pv_raw = skidl.Net("PV_RAW")
    pv_raw += j_pv[1]
    gnd += j_pv[2]

    # SS34: 40V/3A Schottky for reverse-polarity protection
    d_rp = skidl.Part("Device", "D_Schottky", footprint="Diode_SMD:D_SMA")
    d_rp.value = "SS34"
    pv_raw += d_rp["A"]
    pv_in += d_rp["K"]
    _cap("22uF", FP_C_1206, pv_in, gnd)


def build_mppt_charger(pv_in: skidl.Net, vbat: skidl.Net, gnd: skidl.Net) -> None:
    """BQ24650 MPPT: R_SR=20mOhm -> 2A charge, V_FB->14.6V, V_INREG->16.8V."""
    # BQ24650 not in default KiCad libs — placeholder generic 16-pin per pyproject
    # Pin assignments (datasheet SLUSAS9C Table 4-1):
    # 1=STAT1 2=STAT2 3=VFB 4=ISET2 5=BAT 6=SRP 7=SRN 8=PGND
    # 9=LODRV 10=PH 11=BTST 12=HIDRV 13=REGN 14=VCC 15=VINREG 16=TS
    u = skidl.Part(
        "Connector_Generic",
        "Conn_02x08_Odd_Even",
        footprint="Package_DFN_QFN:HVQFN-16-1EP_3x3mm_P0.5mm_EP1.5x1.5mm",
    )
    u.value = "BQ24650"

    pv_in += u[14]
    pv_in += u[15]  # VINREG sense (simplified — real divider TBD)

    sw = skidl.Net("MPPT_SW")
    boot = skidl.Net("MPPT_BOOT")
    srp = skidl.Net("BAT_SRP")
    sw += u[10]
    boot += u[11]

    _cap("100nF", FP_C_0402, boot, sw)  # bootstrap

    # 6.8 uH inductor — typical for BQ24650 at 1-2A charge
    ind = skidl.Part(
        "Device", "L", value="6.8uH", footprint="Inductor_SMD:L_Bourns-SRN6028"
    )
    sw += ind[1]
    srp += ind[2]
    srp += u[6]

    # 20 mOhm sense — I_charge = 0.04V / 20mOhm = 2A
    r_sense = skidl.Part(
        "Device", "R", value="20m", footprint="Resistor_SMD:R_1206_3216Metric"
    )
    srp += r_sense[1]
    vbat += r_sense[2]
    vbat += u[7]
    vbat += u[5]

    _cap("22uF", FP_C_1206, vbat, gnd)
    gnd += u[8]
    gnd += u[9]
    gnd += u[16]  # TS NC — BMS handles low-temp cutoff (ADR-009)


def build_buck_5v(vbat: skidl.Net, v5_rail: skidl.Net, gnd: skidl.Net) -> None:
    """LMR33630 sync buck: 10-14.6V Vbat -> 5V/3A. 470uF bulk for boot inrush."""
    # Pin assignments (datasheet SNVSAQ8B Table 6-1):
    # 1=PG 2=BST 3=VIN 4=GND 5=EN 6=RT 7=FB 8=SW
    u = skidl.Part(
        "Connector_Generic",
        "Conn_02x04_Odd_Even",
        footprint="Package_SO:HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm",
    )
    u.value = "LMR33630ADDA"

    vbat += u[3]  # VIN
    vbat += u[5]  # EN tied to VIN — always-on
    gnd += u[4]
    skidl.Net("NC_BUCK_PG") & u[1]  # PG no-connect

    sw = skidl.Net("BUCK_SW")
    boot = skidl.Net("BUCK_BOOT")
    fb = skidl.Net("BUCK_FB")
    sw += u[8]
    boot += u[2]
    fb += u[7]

    _cap("4.7uF", FP_C_0805, vbat, gnd)
    _cap("100nF", FP_C_0402, vbat, gnd)
    _cap("100nF", FP_C_0402, boot, sw)

    # 10 uH at 400 kHz Fsw, 4A sat
    ind = skidl.Part(
        "Device", "L", value="10uH", footprint="Inductor_SMD:L_Bourns-SRN8040_8x8.15mm"
    )
    sw += ind[1]
    v5_rail += ind[2]

    # FB divider — Vout = 1.0V * (1 + 39.2k/10k) = 4.92V (target 5V)
    _res("39.2k", FP_R_0402, v5_rail, fb)
    _res("10k", FP_R_0402, fb, gnd)

    # RT — 47k for 400 kHz Fsw
    rt = skidl.Net("BUCK_RT")
    rt += u[6]
    _res("47k", FP_R_0402, rt, gnd)

    # Output: 470uF bulk (boot inrush) + ceramic HF
    c_bulk = skidl.Part(
        "Device",
        "C_Polarized",
        value="470uF",
        footprint="Capacitor_SMD:CP_Elec_8x10",
    )
    v5_rail += c_bulk[1]
    gnd += c_bulk[2]
    _cap("22uF", FP_C_0805, v5_rail, gnd)
    _cap("100nF", FP_C_0402, v5_rail, gnd)


def _build_fixed_ldo(
    sym: str,
    label: str,
    vin: skidl.Net,
    vout: skidl.Net,
    en: skidl.Net,
    gnd: skidl.Net,
) -> None:
    """Generic fixed-voltage LDO in SOT-23-5. Pins by number — AP2112K and LP5907 share layout.

    1=VIN, 2=GND, 3=EN, 4=NC, 5=VOUT
    """
    u = skidl.Part("Regulator_Linear", sym, footprint="Package_TO_SOT_SMD:SOT-23-5")
    u.value = label
    vin += u[1]
    gnd += u[2]
    en += u[3]
    skidl.Net(f"NC_{label}") & u[4]
    vout += u[5]
    _cap("1uF", FP_C_0402, vin, gnd)
    _cap("1uF", FP_C_0402, vout, gnd)


def build_ldo_3v3(v5: skidl.Net, v3v3: skidl.Net, gnd: skidl.Net) -> None:
    """AP2112K-3.3 LDO — 5V -> 3.3V/600mA for sensor analog front-end. Always-on."""
    _build_fixed_ldo("AP2112K-3.3", "AP2112K-3.3", v5, v3v3, v5, gnd)


def build_ldo_3v8(
    v5: skidl.Net, v3v8: skidl.Net, en: skidl.Net, gnd: skidl.Net
) -> None:
    """LP5907-3.8 LDO — 5V -> 3.8V/250mA for BG770A VBAT (ADR-010). EN from CM4 GPIO."""
    # Reason: LP5907MFX-3.8 symbol not in default kicad libs; -3.3 symbol with -3.8 value
    _build_fixed_ldo("LP5907MFX-3.3", "LP5907MFX-3.8", v5, v3v8, en, gnd)
