# Soil Moisture Sensor

Button-activated, battery-powered soil moisture meter with a 0.96" OLED display.

Press the button -> MCU wakes -> load switch powers the OLED and sensor -> moisture reading is shown for 15 s -> everything powers down (~0.5 uA standby).

![PCB top](docs/pcb_top.png)

## Hardware
| Ref | Function | Part |
|---|---|---|
| U1 | MCU | Microchip ATtiny1614-SSNR (SOIC-14) |
| J5 | Battery | 2xAAA holder with leads -> JST-PH 2-pin (direct, 2.0-3.2 V) |
| Q1 | Reverse-polarity protection | Diodes DMG3415U P-FET |
| U2 | Peripheral power switch | TI TPS22917DBVR load switch |
| J2 | Display | ELEGOO 0.96" SSD1306 I2C OLED (0x3C), 4x 2.54 mm pads (GND-VCC-SCL-SDA, same order as the module) - solder the supplied Dupont wires or fit a 1x04 header |
| J3 | Sensor | Adafruit 4026 STEMMA capacitive soil sensor (I2C 0x36), JST-SH 4-pin |
| SW1 | Button | C&K KMR221GLFS |
| J1 | Programming | UPDI pads on PCB bottom (DNP) |

See `BOM.csv` for the full parts list and `Moisture_Sensor.pdf` for the schematic.

## PCB
- 27.8 x 17 mm, 2-layer, 1.6 mm, all SMD on top (UPDI pads on bottom), GND pour both sides.
- OLED (J2) pads and sensor (J3) connector are on the top edge; the OLED mounts on the case side, the sensor cable exits the case.
- No mounting holes: hold the board in the case with a ledge/snap clips. `Moisture_Sensor.step` is provided for enclosure design.
- Tallest parts: JST-PH (~6 mm) and JST-SH (~4.3 mm).

## Pin map (ATtiny1614)
| Signal | Port | Pin |
|---|---|---|
| LOAD_EN | PA4 | 2 |
| BTN (wake) | PA6 | 4 |
| SDA | PB1 | 8 |
| SCL | PB0 | 9 |
| UPDI | PA0 | 10 |

## Notes
- Bridge the OLED module's onboard LDO so it operates down to ~2.2 V; verify the module pin order (GND/VCC may be swapped).
- Firmware: run at 5 MHz; set I2C pins to high-Z before switching off VSW to avoid back-powering peripherals; low-battery cutoff ~2.2 V.
- `tools/gen_sch.py` regenerates the schematic and `tools/gen_pcb.py --route` the PCB (KiCad's bundled Python; routing needs Freerouting + Java 25).
