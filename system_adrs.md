# DLR Carrier Board — Architecture Decision Records

Captures architectural and component decisions for the EMS Line Controller DLR PCB. New decisions append as ADR-NNN; supersedes are explicit. Date format ISO 8601.

## Index

| # | Decision | Class |
|---|---|---|
| 001 | Single-PCB CM4 carrier | Architecture |
| 002 | Battery — LiFePO4 4S | Architecture |
| 003 | Cellular bands — NA-only | Architecture |
| 004 | Solar panel — 20W | Architecture |
| 005 | I2C clock — 400 kHz | Architecture |
| 006 | Antenna form — u.FL + external blade | Architecture |
| 007 | 5V buck — TI LMR33630 | Component |
| 008 | MPPT charger — TI BQ24650 | Component |
| 009 | BMS — JBD-SP04S013 (on-pack) | Component |
| 010 | BG770A 3.8V LDO — TI LP5907 | Component |
| 011 | Level shifter — TI TXS0108E | Component |
| 012 | u.FL connector — Hirose U.FL-R-SMT-1(10) | Component |
| 013 | Lepton daughterboard for aim flexibility | Architecture |

---

## ADR-001: Single-PCB CM4 Carrier (vs Pi HAT)

**Status:** Accepted **Date:** 2026-05-08

### Context
30-yr maintenance-free transmission tower deployment, IP55 potted enclosure, IEC 60068-2-6 vibration (5–500 Hz, 2g), −20 to +85°C operating temp, solar+LiFePO4 budget. Initial readme proposed a Pi 5 HAT stack.

### Decision
Single-PCB ~100×80mm 4-layer carrier with Raspberry Pi CM4 mounted via DF40 connector pair. All cellular, sensor, and power-management circuitry on the same board.

### Rationale
- Pi 5 is consumer-grade (0–50°C) and won't survive spec'd environment
- 40-pin HAT stack is a vibration failure mode (connector fretting + lever arm)
- Stock Pi has unused HDMI/audio/USB hub circuitry burning solar budget for 30 yrs
- USB-A cellular dongles are the worst industrial connector
- Conformal-coating a Pi is messy (HDMI/USB ports = giant openings)

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Pi HAT stack | Faster iteration, fails environment spec |
| iMX6ULL or STM32MP1 SoM | More industrial pedigree, worse software ecosystem, longer integration |
| STM32H7 + PSRAM (no Linux) | Lowest power, ~6 mo firmware vs ~3 wk Python |

### Consequences
- 4-layer 1.6mm board with controlled impedance (50Ω microstrip + 90Ω diff)
- Operating temp pinned at −20 to +85°C (CM4 commercial spec)
- Cold-start heater needed below −20°C
- All schematic + layout effort owned by us

---

## ADR-002: Battery — LiFePO4 4S

**Status:** Accepted **Date:** 2026-05-08

### Context
Outdoor solar-powered RTU with 30-yr cycle life. Battery range must be compatible with downstream buck Vin.

### Decision
4S LiFePO4 pack: V_min = 10.0V, V_nom = 12.8V, V_max = 14.6V. 4 Ah cell → ~50 Wh nominal.

### Rationale
4S sits in the Vin range of common 12V-class bucks with transient margin. LiFePO4 has 90% DoD tolerance, 3000+ cycle life, and cold-temp safety (no thermal runaway risk in a sealed enclosure).

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| LiFePO4 3S (9.6V nom) | Cheaper, but 7.5V cutoff below most buck Vin specs |
| Li-ion 3S | Higher energy density, worse thermal safety |
| Lead-acid | Cheap, heavy, low cycle life, poor cold-temp |

### Consequences
- Buck must accept 10.0–14.6V continuously (1.46x ratio)
- BMS must handle 4-cell balancing + 0°C low-temp charge cutoff
- 50 Wh autonomy = 1.58 days at zero PV → flagged for upgrade to 100 Wh

---

## ADR-003: Cellular Bands — NA-Only

**Status:** Accepted **Date:** 2026-05-08

### Context
Cat-M1 RTU deployment scoped to North American utility customers initially. Module SKU + antenna selection depend on band targets.

### Decision
NA-only Cat-M1 bands: B12/B13/B71/B85 (600–960 MHz LB).

### Rationale
NA-only narrows BG770A SKU choice (BG770A-NA), reduces antenna BOM (single LB element vs multiband), avoids global certification cost (FCC/IC only).

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Global multiband | Larger antenna, dual-band cert, higher cost, premature for utility scope |
| EU + NA | Splits cert effort, no current customer pull |

### Consequences
- BG770A-NA SKU only
- Antenna spec: 600–960 MHz, ~3 dBi, single-band blade
- Future global expansion = new SKU + new antenna (acceptable)

---

## ADR-004: Solar Panel — 20W

**Status:** Accepted **Date:** 2026-05-08

### Context
Daily energy budget at 1/min sampling + 1/15-min cellular TX = 29.1 Wh/day (theory.ipynb). Need PV sizing for ≥1.5x winter margin.

### Decision
20W mono panel, ~17V Vmp, ~21V Voc.

### Rationale
20W × 2.5 sun-hours × 0.90 MPPT η = 45 Wh/day winter worst case = 1.55x margin over 29 Wh/day budget. Annual avg = 2.5x. Panel envelope (~30×40 cm, ~2 kg) is mechanically reasonable for a tower cross-arm.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| 10W panel | Insufficient — winter margin <1x |
| 30–40W panel | Larger envelope, unnecessary for IEEE 738 sample rate |

### Consequences
- MPPT charger Vin range must cover 17V Vmp comfortably (5–28V is fine)
- Panel mounting hardware sized for ~2 kg + wind/ice loading
- If sample rate ever bumps to 1Hz, panel must scale to ~125W (separate ADR)

---

## ADR-005: I2C Clock — 400 kHz

**Status:** Accepted **Date:** 2026-05-08

### Context
On-board I2C bus carries ADS1115 (0x48) + SI1145 (0x60) + 2 spare slots. Pull-up sizing depends on clock rate.

### Decision
400 kHz fast mode (UM10204 Rev 7.0).

### Rationale
ADS1115 supports up to 3.4 MHz, SI1145 up to 400 kHz. Fast mode is the highest rate the slowest device supports. With 75 pF estimated C_bus and 2.2 kΩ pull-ups, rise time = 140 ns vs 300 ns spec (53% margin).

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| 100 kHz standard mode | Larger pull-ups OK, but slower readings limit sensor poll rate headroom |
| 1 MHz fast-mode-plus | SI1145 exceeded; would force discrete buffer per device |

### Consequences
- 2.2 kΩ pull-ups on SDA/SCL (E24, in 967Ω–4.72kΩ range)
- C_bus budget: 75 pF (verify after layout)

---

## ADR-006: Antenna Form — u.FL + External Blade

**Status:** Accepted **Date:** 2026-05-08

### Context
Tower-top deployment needs reliable RF link to a Cat-M1 base station. Antenna choice trades cost vs gain vs durability.

### Decision
On-board u.FL connector → external pigtail (RG316) → N-female bulkhead → external blade antenna.

### Rationale
u.FL is the canonical cellular module connector; pigtail to N-female bulkhead gives mechanical robustness at the enclosure wall. External blade provides ~3 dBi at 600–960 MHz vs negative gain for an internal PCB trace antenna.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| On-board PCB trace antenna (Taoglas FXUB63) | No external connector, but gain too low for tower-top |
| MMCX/SMA on-board (no pigtail) | More robust mechanically, 10× footprint, overkill inside potted enclosure |
| Whip with magnetic base | Won't work on transmission tower (lattice, not steel) |

### Consequences
- 50Ω microstrip from BG770A ANT to u.FL (≤30 mm preferred per theory section 5)
- External antenna + pigtail are accessories, specified at integration time
- Pi-network footprint provisioned on-board for VSWR tuning during EVT

---

## ADR-007: 5V Buck — TI LMR33630ADDAR

**Status:** Accepted **Date:** 2026-05-08

### Context
Battery 10–14.6V → 5V/3A continuous + 3.92A boot inrush. Sits upstream of CM4 + BG770A LDO + sensors.

### Decision
TI LMR33630ADDAR, HSOIC-8, programmable Fsw=400 kHz, paired with 470 µF aluminum polymer bulk cap on 5V to absorb CM4 boot inrush.

### Rationale
3.8–36V Vin = huge headroom over 14.6V max. 3A integrated synchronous FETs, ~92% peak η, industrial −40 to +125°C, hand-solderable, ~$1.50.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| TI TPS62133 | Smaller QFN, but Vin tops at 15V — only 0.4V margin over V_BAT_MAX |
| TI TPS54331 | Asynchronous → ~80% light-load η, hurts PSM idle budget |
| LM2596 (legacy) | Cheap + ubiquitous, ~75% η wastes 25% of solar budget |
| MPS MP2459 | Undersized at <1A |

### Consequences
- Bulk cap on 5V rail is mandatory (boot inrush mitigation)
- Programmable Fsw lets us trade efficiency vs component size at layout time
- 92% efficiency vs 90% theory assumption gives small headroom in derivation

---

## ADR-008: MPPT Charger — TI BQ24650RVAR

**Status:** Accepted **Date:** 2026-05-08

### Context
20W panel input → 4S LiFePO4 charge. Needs true MPPT (not just input-voltage regulation) and adjustable charge profile.

### Decision
TI BQ24650RVAR, VQFN-16. R_SR = 20 mΩ for 2A charge (0.5C of 4 Ah cell). VINREG set to 16.8V (~80% of Voc). VFB divider gives 14.6V V_charge.

### Rationale
True MPPT buck charger via VINREG pin (not just CV input regulation). 5–28V Vin covers 17V Vmp + transients. Programmable charge V/I via resistor dividers. Industrial −40 to +85.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| LTC4015 | LiFePO4-aware + I²C telemetry, but 2× cost + 38-pin QFN, overkill |
| MP2731 | Cheap, designed for 1S phone use case — won't drive 4S/14.6V |
| CN3791 | Asian-market chip, sparse docs, max 8.4V output (2S only) |
| Discrete LT3652 + LTC4054 | Most flexible, but 2 ICs + more passives, harder to debug |

### Consequences
- Cell balancing + low-temp cutoff are NOT in BQ24650 → handled by separate BMS (ADR-009)
- TS pin can monitor pack NTC; partially overlaps with BMS — leave NC unless needed
- R_SR = 20 mΩ ±1% sense resistor required

---

## ADR-009: BMS — JBD-SP04S013 (On-Pack)

**Status:** Accepted **Date:** 2026-05-08

### Context
LiFePO4 4S pack needs cell balancing + per-cell over/undervoltage cutoff + low-temp charge inhibit (charging below 0°C destroys LiFePO4 cells permanently).

### Decision
JBD-SP04S013 (or equivalent commoditized 4S LiFePO4 BMS PCB), mounted **physically on the battery pack**, NOT on the carrier PCB. 15A continuous discharge, balancing, 0°C low-temp cutoff, ~150 µA quiescent, ~$8.

### Rationale
Designing a discrete BMS on the carrier multiplies layout complexity, MOSFET sourcing risk, and validation effort for a problem that's already commoditized. On-pack mounting means the carrier sees only `BAT+`/`BAT-` — drastically simpler PCB.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Discrete on-carrier (TI BQ77216 + dual N-FETs) | ~6 ICs + 8 FETs + 30 passives added; ~3 wks of layout + validation |
| Discrete on-carrier (Analog Devices LTC6804) | Best-in-class, $15 IC, designed for EV/grid storage — massive overkill |
| No BMS | NEVER acceptable — cell imbalance kills LiFePO4 in <100 cycles |
| Bioenno BLF-1204AS (battery + BMS combined) | Zero design effort but 3× cost, locks vendor |

### Consequences
- Carrier PCB has 2-pin battery input only (no cell sense lines, no protection FETs)
- Battery is a swappable assembly serviced separately — better 30-yr maintenance story
- BMS quiescent (150 µA × 12.8V × 24h = 0.046 Wh/day) is negligible vs 29 Wh/day budget

---

## ADR-010: BG770A 3.8V LDO — TI LP5907MFX-3.8

**Status:** Accepted **Date:** 2026-05-08

### Context
BG770A VBAT spec is 3.4–4.3V (Li-ion class). Cannot power directly from 4S battery (10–14.6V) or 5V buck. Cellular RF is sensitive to LDO ripple.

### Decision
TI LP5907MFX-3.8, SOT-23-5. Fixed 3.8V output (no resistor divider), 250 mA, 6.5 µVrms ultra-low-noise, 16 µA quiescent.

### Rationale
LP5907 is the LDO Quectel's BG770A hardware design guide explicitly recommends. Fixed 3.8V SKU exactly matches Quectel's typical, no divider drift. Ultra-low noise prevents desensing the cellular receiver.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| MPS MP2161 (3.8V buck from 5V) | Higher η, but switching noise into RF chain — needs filtering, not worth it for ~0.18 Wh/day savings |
| TPS73801 (adjustable LDO) | 1A capacity, but higher quiescent + divider drift |
| AP2112-3.3 (re-use 3V3 LDO) | Below BG770A's 3.4V minimum — TX brownouts |
| Adjustable LDO from battery direct | 12V × 250mA peak = 3.6W heat, thermally infeasible |

### Consequences
- Daily energy budget already accounts for BG770A draw at 5V-equivalent (LDO η ~80%)
- LP5907 EN pin wired to a CM4 GPIO → power-cycle option for stuck cellular state
- 250 mA capacity covers TX peaks with margin

---

## ADR-011: Level Shifter — TI TXS0108E

**Status:** Accepted **Date:** 2026-05-08

### Context
CM4 GPIO is 3.3V CMOS, BG770A I/O is 1.8V CMOS. 8 lines need shifting: TXD, RXD, PWRKEY, RESET, DTR, STATUS, NETLIGHT, RING. (USB doesn't need shifting — USB 2.0 spec on both sides.)

### Decision
TI TXS0108E, TSSOP-20. 8-channel auto-direction-sensing, OD-compatible, 1.65–5.5V on either side, ~1.2 Mbps OD / 50 Mbps push-pull.

### Rationale
Mixed signal types on BG770A side (some OD outputs) — TXS0108E handles both. Single-IC vs 16 discrete transistors. Auto-direction means no DIR pin to manage. Quectel reference designs use this part.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| TI TXB0108 | Stronger push-pull drive, but fails on OD signals — risky if STATUS/NETLIGHT are OD |
| Discrete BSS138 + 10kΩ pulls | Cheapest, but 16 transistors + 16 resistors = 50× layout area |
| 4× SN74LVC1T45 single-channel | Per-channel direction control, but 4 ICs + 4 GPIOs consumed |
| Series resistor only | Will damage BG770A inputs over time via protection diodes |

### Consequences
- VccA = 1.8V (sourced from BG770A VDD_EXT, ~50 mA available)
- VccB = 3.3V (from existing AP2112K)
- OE pin → CM4 GPIO with pull-down for boot-time isolation
- 100 nF decoupling on each Vcc

---

## ADR-012: u.FL Connector — Hirose U.FL-R-SMT-1(10) + Pi-Match

**Status:** Accepted **Date:** 2026-05-08

### Context
On-board RF chain from BG770A ANT pin to external pigtail. Form-factor decision (ADR-006) selected u.FL; this ADR pins the specific connector and matching topology.

### Decision
Hirose U.FL-R-SMT-1(10) connector + 3-pad Pi-network footprint between BG770A ANT and u.FL. Default: 0Ω series jumper, NC/NC shunts. Components populated only if EVT VSWR testing requires.

### Rationale
Hirose is the canonical industry u.FL — every cellular module reference design uses it. Pi-network footprint is free in layout space and preserves tuning option without a respin.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Molex 73412-0110 | Functionally equivalent, sometimes better-stocked, but pigtails specced for Hirose may not seat as well |
| Skip Pi-network, direct trace | One less footprint, but no recourse if VSWR is bad at EVT |
| MMCX/SMA on-board | More robust mechanically, but 10× area + 4–5× cost, overkill inside potted enclosure |

### Consequences
- 50Ω microstrip from BG770A ANT → Pi-network → u.FL center pin
- u.FL placed near board edge for pigtail clearance + 10×10mm keepout for cable bend radius
- Off-board accessories (pigtail + N-female bulkhead + blade antenna) specified at integration, not PCB design

---

## ADR-013: Lepton Daughterboard for Aim Flexibility

**Status:** Accepted **Date:** 2026-05-10

### Context
ADR-001 mandated a single-PCB carrier with all sensor, cellular, and power-management circuitry on one board, motivated by stacked-Pi-HAT vibration failures over 30-yr deployments. Cross-arm DLR deployment requires the FLIR Lepton 3.5 lens to aim at a conductor ~1.5 m below the cross-arm; with a sky-facing solar panel constraint and the lens perpendicular to the main PCB, no monolithic-board orientation satisfies both.

### Decision
Split the Lepton onto a small (~25 × 40 mm) daughterboard linked to the main PCB by a 14-pin 0.5 mm-pitch FFC. Daughterboard mounts to a sheet-metal bracket with M3 pivot + M3 arc-slot lock, allowing ±15° aim adjustment at integration time. Sealed industrial USB-C commissioning port on the main carrier provides live thermal preview to a laptop while the integrator sets aim.

### Rationale
ADR-001's spirit was to avoid stacked compute (Pi 5 HAT). A passive sensor daughterboard with no active electronics beyond the Lepton socket and decoupling is not the failure class ADR-001 was guarding against. The daughterboard inherits the 30-yr robustness of the main carrier (same conformal coat, same enclosure, same potting) and adds no compute.

### Alternatives Considered
| Option | Tradeoff |
|---|---|
| Lens out the side via vertical PCB | CM4 + cellular re-layout, vibration cantilever, antenna re-route. Overkill for an optical aim problem. |
| 45° gold folding mirror inside enclosure | Field-degradation: dust, condensation, ice, biofilm. Mirror-axis drift over 30 yrs. |
| Right-angle Lepton breakout (commercial) | Locks us to a specific vendor SKU with EOL risk; still needs a daughterboard or adapter. |
| GroupGets Lepton breakout as the daughterboard | Pre-designed, but vendor EOL risk over 30 yrs and no native FFC connection — adapter board still needed. |

### Consequences
- Two PCBs in the project: `cad/dlr_carrier.*` (main) and `cad/lepton_daughter/*` (new). Two KiCad projects, two BOM/CPL files, two Gerber sets to fab; ~+$15 marginal fab cost per unit at low volume.
- J8 footprint on main PCB changes from a 14-pin 2.54 mm THT header to a Hirose FH12-14S-0.5SH FFC connector. Pin map preserves the GroupGets 14-pin Lepton breakout signal order so the schematic on the daughterboard is reusable.
- Aim is set once at integration with lockwasher + Loctite 243; no field-accessible knob (an external knob would be an IP55 / O-ring / corrosion-over-30-yrs liability).
- Sealed industrial USB-C commissioning port (J12) is mandatory — without it the integrator can't see the live thermal frame to set aim.
- ADR-001 retains force for compute and the bulk of sensor / power circuitry; ADR-013 is a scoped exception covering only the Lepton optical chain.
