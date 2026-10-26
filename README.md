# Soil Moisture Sensor

Button-activated, battery-powered soil moisture meter with a 0.96" OLED display.

Press the button -> MCU wakes -> load switch powers the OLED and sensor -> moisture reading is shown for 15 s -> everything powers down (~0.5 uA standby).

## Hardware
| Function | Part |
|---|---|
| MCU | Microchip ATtiny1614-SSNR (SOIC-14) |
| Power | 2xAAA (Keystone 2468), direct (2.0-3.2 V), DMG3415U reverse-polarity protection |
| Peripheral power switch | TI TPS22917DBVR load switch |
| Display | ELEGOO 0.96" SSD1306 I2C OLED (0x3C) |
| Sensor | Adafruit 4026 STEMMA capacitive soil sensor (I2C 0x36); optional analog header for generic TLC555 sensors |
| Button | Omron B3F-1000 6 mm tactile |

See `BOM.csv` for the full parts list and `Moisture_Sensor.pdf` for the schematic.

## Pin map (ATtiny1614)
| Signal | Port | Pin |
|---|---|---|
| LOAD_EN | PA4 | 2 |
| SENS_A (optional analog) | PA5 | 3 |
| BTN (wake) | PA6 | 4 |
| SDA | PB1 | 8 |
| SCL | PB0 | 9 |
| UPDI | PA0 | 10 |

## Notes
- Bridge the OLED module's onboard LDO so it operates down to ~2.2 V; verify the module pin order (GND/VCC may be swapped).
- Firmware: run at 5 MHz; set I2C pins to high-Z before switching off VSW to avoid back-powering peripherals.
- `tools/gen_sch.py` regenerates the schematic (run with KiCad's bundled Python).
