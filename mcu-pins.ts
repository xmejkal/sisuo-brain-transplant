/**
 * Which silkscreen pin on the microcontroller module carries which signal.
 *
 * THE ONE PLACE THIS IS DECIDED. Three things read it:
 *   - `board.tsx`, so its traces name the signal rather than the pin;
 *   - `tools/circuit-to-wokwi/lib/mapping.ts`, so the simulation wires the same pins;
 *   - `tools/circuit-to-wokwi/lib/checks/firmware-pins.ts`, which proves it agrees with
 *     `firmware/micropython/config.py` and with `boards/<active>.json`.
 *
 * That last one is the point. config.py says a signal is on a GPIO number; the board definition
 * says which silkscreen pin that GPIO is; this file says which silkscreen pin carries the
 * signal. Three independent statements, and `make check` proves all three agree — which is why
 * this is hand-written rather than generated from config.py. Generating it would make the check
 * tautological, and the bug it exists to catch is precisely a pin map that drifted.
 *
 * Switching board: this table and the placement in board.tsx are the work. The traces are not.
 */
export const MCU = {
  TOF_INT    : "D12",  // GPIO12 - wake-capable, and not on ADC1, so it costs no analogue pin
  BTN_OPEN   : "D11",  // GPIO13 - wake-capable
  MOTOR_SENSE: "A0",  // GPIO4  - ADC1. ADC2 exists but cannot be read with WiFi on
  MOTOR_IA   : "D10",  // GPIO14
  MOTOR_IB   : "D6",  // GPIO18
  SDA        : "SDA",  // GPIO1  - the board's dedicated I2C pins
  SCL        : "SCL",  // GPIO2
  BTN_MODE   : "D14",  // GPIO47 - cannot wake, and need not. Also the on-board button
  MP3_TX     : "D3",
  MP3_ENABLE : "A1",   // GPIO5 - drives the MP3 rail's high-side switch low to turn it ON  // GPIO38 - cannot wake, and need not
  LED_RED    : "D7",  // GPIO9
  LED_GREEN  : "D5",  // GPIO7
  V33        : "3V3",  // the module's 2 A buck output
  GND        : "GND1",  // one of three ground pads; the other two are wired in board.tsx
} as const
