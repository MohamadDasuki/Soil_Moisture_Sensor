/*
  Soil Moisture Meter - ATtiny1614 firmware (megaTinyCore)

  Press button -> load switch powers OLED + sensor -> live moisture reading for 15 s
  (refreshed every second) -> everything off, MCU in power-down (~0.1 uA).
  Short press while on   : restart the 15 s timer.
  Hold 3 s while on      : calibration (sensor in air, then in water), saved to EEPROM.

  Board settings (Tools menu / FQBN options), see README:
    Chip ATtiny1614, Clock 5 MHz internal, BOD disabled (active & sleep),
    millis() timer: default (NOT RTC - this sketch uses the RTC PIT).
*/
#include <Arduino.h>
#include <Wire.h>
#include <avr/sleep.h>
#include <avr/eeprom.h>
#include <util/delay.h>
#include "oled.h"

// ---- pins (see README pin map) ----
#define LOAD_EN_bm  PIN4_bm   // PA4 -> TPS22917 ON
#define AOUT_MUX    ADC_MUXPOS_AIN5_gc   // PA5 sensor analog out
#define BTN_bm      PIN6_bm   // PA6, button to GND, fully-async pin (wakes from power-down on edge)

// ---- behaviour ----
#define ON_SECONDS      15
#define HOLD_CAL_10MS   300     // 3 s hold enters calibration
#define VBAT_LOW_MV     3400    // show LOW BAT warning
#define VBAT_CUTOFF_MV  3100    // refuse to measure (sensor's NE555 needs >~3 V)
#define VBAT_FULL_MV    4650    // 3x fresh alkaline
#define SENSOR_SETTLE_MS 400    // sensor output RC filter settling after power-up

// ---- calibration (raw = 16-sample accumulated ADC, 0..16368, ratiometric to VDD) ----
struct Cal { uint16_t magic, dry, wet; };
#define CAL_MAGIC 0x5A17
static Cal EEMEM eeCal;
static Cal cal = {CAL_MAGIC, 600 * 16, 280 * 16};   // typical v1.2 values; calibrate for accuracy

static volatile bool btnFlag, tickFlag;

ISR(PORTA_PORT_vect) { PORTA.INTFLAGS = BTN_bm; btnFlag = true; }
ISR(RTC_PIT_vect)    { RTC.PITINTFLAGS = RTC_PI_bm; tickFlag = true; }

static inline bool btnDown() { return !(PORTA.IN & BTN_bm); }

// ------------------------------------------------------------------ ADC
static uint16_t adcRead(uint8_t mux, uint8_t refsel) {
  ADC0.CTRLA = ADC_ENABLE_bm;                                    // 10-bit
  ADC0.CTRLB = ADC_SAMPNUM_ACC16_gc;
  ADC0.CTRLC = ADC_SAMPCAP_bm | refsel | ADC_PRESC_DIV8_gc;      // 5 MHz / 8 = 625 kHz
  ADC0.CTRLD = ADC_INITDLY_DLY32_gc;
  ADC0.SAMPCTRL = 4;
  ADC0.MUXPOS = mux;
  uint16_t r = 0;
  for (uint8_t i = 0; i < 2; i++) {                              // first result discarded
    ADC0.COMMAND = ADC_STCONV_bm;
    while (!(ADC0.INTFLAGS & ADC_RESRDY_bm));
    r = ADC0.RES;                                                // reading RES clears RESRDY
  }
  ADC0.CTRLA = 0;                                                // ADC off between readings
  return r;
}

// VDD in mV, by measuring the internal 1.1 V reference against VDD (no divider needed)
static uint16_t readVddmV() {
  VREF.CTRLA = (VREF.CTRLA & ~VREF_ADC0REFSEL_gm) | VREF_ADC0REFSEL_1V1_gc;
  VREF.CTRLB |= VREF_ADC0REFEN_bm;
  _delay_us(50);
  uint16_t r = adcRead(ADC_MUXPOS_INTREF_gc, ADC_REFSEL_VDDREF_gc);
  VREF.CTRLB &= ~VREF_ADC0REFEN_bm;
  return r ? (uint32_t)1100UL * 1023UL * 16UL / r : 0;
}

// Sensor output relative to VDD; the sensor runs from VSW (= VBAT), so this cancels battery droop.
static uint16_t readSensorRaw() { return adcRead(AOUT_MUX, ADC_REFSEL_VDDREF_gc); }

static uint8_t moisturePct(uint16_t raw) {
  if (raw >= cal.dry) return 0;          // higher voltage = drier
  if (raw <= cal.wet) return 100;
  return (uint32_t)(cal.dry - raw) * 100UL / (cal.dry - cal.wet);
}

// ------------------------------------------------------------------ power
static void pinsLowPower() {
  // unused / analog pins: digital input buffers off (no leakage from floating inputs)
  PORTA.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTA.PIN2CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTA.PIN3CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTA.PIN5CTRL = PORT_ISC_INPUT_DISABLE_gc;   // AOUT, analog only
  PORTA.PIN7CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTB.PIN2CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTB.PIN3CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTA.DIRSET = LOAD_EN_bm;
  PORTA.OUTCLR = LOAD_EN_bm;
  PORTA.DIRCLR = BTN_bm;
  PORTA.PIN6CTRL = PORT_PULLUPEN_bm | PORT_ISC_FALLING_gc;
}

static void i2cPinsOff() {
  // OLED/sensor are unpowered: don't drive or pull up SDA/SCL (avoids back-feeding them)
  PORTB.DIRCLR = PIN0_bm | PIN1_bm;
  PORTB.OUTCLR = PIN0_bm | PIN1_bm;
  PORTB.PIN0CTRL = PORT_ISC_INPUT_DISABLE_gc;
  PORTB.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;
}

static bool peripheralsOn() {
  PORTA.OUTSET = LOAD_EN_bm;
  _delay_ms(30);                                   // load-switch ramp + SSD1306 reset
  PORTB.PIN0CTRL = 0;
  PORTB.PIN1CTRL = 0;
  Wire.begin();
  Wire.setClock(400000);
  return oledInit();
}

static void peripheralsOff() {
  oledOff();
  Wire.end();
  i2cPinsOff();
  PORTA.OUTCLR = LOAD_EN_bm;
}

static void pitStart() {
  while (RTC.STATUS || RTC.PITSTATUS);
  RTC.CLKSEL = RTC_CLKSEL_INT1K_gc;                // 1.024 kHz from the 32 kHz ULP oscillator
  RTC.PITINTCTRL = RTC_PI_bm;
  RTC.PITCTRLA = RTC_PERIOD_CYC1024_gc | RTC_PITEN_bm;   // 1 s tick
  tickFlag = false;
}
static void pitStop() {
  while (RTC.PITSTATUS);
  RTC.PITCTRLA = 0;
  RTC.PITINTCTRL = 0;
}

static void sleepNow() {
  set_sleep_mode(SLEEP_MODE_PWR_DOWN);
  cli();
  if (!btnFlag && !tickFlag) { sleep_enable(); sei(); sleep_cpu(); sleep_disable(); }
  sei();
}

// Returns number of 10 ms ticks the button was held (capped at HOLD_CAL_10MS).
static uint16_t measurePress() {
  uint16_t n = 0;
  while (btnDown() && n < HOLD_CAL_10MS) { _delay_ms(10); n++; }
  return n;
}
static void waitRelease() { while (btnDown()) _delay_ms(10); _delay_ms(30); btnFlag = false; }

// ------------------------------------------------------------------ UI
static void u16toa(uint16_t v, char *s) { utoa(v, s, 10); }

static void drawHeader(uint16_t mv) {
  char b[12];
  oledClearPages(0, 0);
  oledText(0, 0, "SOIL");
  if (mv < VBAT_LOW_MV) oledText(36, 0, "LOW BAT");
  b[0] = '0' + mv / 1000; b[1] = '.'; b[2] = '0' + (mv / 100) % 10; b[3] = 'V'; b[4] = 0;
  oledText(128 - 4 * 6, 0, b);
}

static void drawReading(uint8_t pct) {
  char b[6];
  u16toa(pct, b);
  strcat(b, "%");
  oledLine(2, b, 4);                                 // pages 2-5, 32 px tall
  oledLine(6, pct < 30 ? "DRY - WATER ME" : pct > 75 ? "WET" : "OK");
  oledBar(7, pct);
}

static bool waitPressOrTimeout(uint8_t rawPage) {
  // live raw value while waiting; 60 s timeout
  btnFlag = false;
  for (uint16_t t = 0; t < 600; t++) {
    if (t % 5 == 0) {
      char b[8]; u16toa(readSensorRaw() / 16, b);
      oledLine(rawPage, b, 2);
    }
    if (btnDown()) { _delay_ms(30); if (btnDown()) { waitRelease(); return true; } }
    _delay_ms(100);
  }
  return false;
}

static void calibrate() {
  oledClear();
  oledLine(0, "CALIBRATION");
  oledLine(2, "1: SENSOR IN AIR");
  oledLine(3, "THEN PRESS");
  waitRelease();
  if (!waitPressOrTimeout(5)) return;
  uint16_t dry = readSensorRaw();

  oledClearPages(2, 7);
  oledLine(2, "2: SENSOR IN WATER");
  oledLine(3, "THEN PRESS");
  if (!waitPressOrTimeout(5)) return;
  uint16_t wet = readSensorRaw();

  oledClearPages(2, 7);
  if (dry > wet && dry - wet >= 50 * 16) {
    cal.dry = dry; cal.wet = wet; cal.magic = CAL_MAGIC;
    eeprom_update_block(&cal, &eeCal, sizeof cal);
    oledLine(3, "SAVED", 2);
  } else {
    oledLine(3, "FAILED", 2);
    oledLine(6, "AIR/WATER TOO CLOSE");
  }
  _delay_ms(2000);
  oledClear();
}

// ------------------------------------------------------------------ session
static void session() {
  uint16_t mv = readVddmV();
  if (!peripheralsOn()) { peripheralsOff(); return; }   // no display: nothing to show

  if (mv < VBAT_CUTOFF_MV) {
    oledLine(1, "BATTERY", 2);
    oledLine(4, "EMPTY", 2);
    _delay_ms(3000);
    peripheralsOff();
    return;
  }

  oledLine(3, "READING...");
  _delay_ms(SENSOR_SETTLE_MS);
  oledClear();
  drawHeader(mv);

  pitStart();
  btnFlag = false;
  uint8_t seconds = 0;
  while (seconds < ON_SECONDS) {
    drawReading(moisturePct(readSensorRaw()));
    tickFlag = false;
    while (!tickFlag && !btnFlag) sleepNow();       // MCU sleeps, display stays on
    if (btnFlag) {
      if (measurePress() >= HOLD_CAL_10MS) {
        pitStop();
        calibrate();
        drawHeader(readVddmV());
        pitStart();
      }
      waitRelease();
      seconds = 0;                                  // any press restarts the 15 s
    } else {
      seconds++;
    }
  }
  pitStop();
  peripheralsOff();
}

// ------------------------------------------------------------------ Arduino entry
void setup() {
  pinsLowPower();
  i2cPinsOff();
  Cal c;
  eeprom_read_block(&c, &eeCal, sizeof c);
  if (c.magic == CAL_MAGIC && c.dry > c.wet) cal = c;
  sei();
}

void loop() {
  btnFlag = false;
  sleepNow();                       // power-down until the button's falling edge
  if (!btnFlag) return;
  _delay_ms(20);
  if (!btnDown()) return;           // bounce / glitch
  waitRelease();
  session();
  waitRelease();
}
