/**
 * Which Wokwi part stands in for which component on our board.
 *
 * This is the file a person edits, and it is data rather than logic on purpose: nothing upstream
 * can know that a VL6180X has no Wokwi part, that a bicolour LED is two Wokwi LEDs, or that a
 * pushbutton's pins are called `1.l` and `2.l`.
 *
 * Matching is by component **name**, because tscircuit types everything buildable as
 * `simple_chip` — the type tells us nothing, and the name is what the designer chose.
 *
 * A component that matches nothing is reported, never silently dropped: a part missing from a
 * simulation is a simulation quietly lying about the board.
 */

import { board } from "./board";

export interface PartMapping {
  /** Component name, or a pattern for a family of them. */
  match: string | RegExp;
  /** The Wokwi part type, e.g. "board-xiao-esp32-c6", "chip-vl6180x". */
  wokwiType: string;
  /**
   * Design pin name -> Wokwi pin name. Pins absent here keep their design name.
   *
   * `null` means "the stand-in part has no such pin" — a deliberate statement, not an omission.
   * A TB6612 has a separate PWM input and our L9110S stand-in does not, and saying so here is
   * how that becomes a recorded decision rather than an invalid wire.
   */
  pins?: Record<string, string | null>;
  /** Wokwi part attributes, e.g. a button's colour or a chip's default control value. */
  attrs?: Record<string, string>;
  /** Where it prefers to sit, if the board is in the middle. */
  side?: "left" | "right";
}

export interface SkipRule {
  match: string | RegExp;
  /** Why this is absent from the simulation. Shown in the report, so it reads as a decision. */
  reason: string;
}

/**
 * The board itself.
 *
 * Its pin NAMES are whatever the Wokwi part uses, which is not the same from board to board:
 * Wokwi's XIAO part names pins by silkscreen (D0..D10) and rejects GPIO numbers, while the
 * generic S3 devkit that stands in for the FireBeetle names them by raw GPIO ("12"). The board
 * definition says which, so this table is derived rather than retyped — and a third copy of the
 * pin map is one more chance to be wrong.
 */
const WOKWI_NAMES_PINS_BY_GPIO = board.wokwi_pin_naming === "gpio";

/**
 * The design's name for a pad -> the name the Wokwi part gives it.
 *
 * Built from the board definition alone. This deliberately knows nothing about signals: the
 * design's pads are named for what is printed on the module, and which signal is on which pad
 * is a separate decision living in `mcu-pins.ts`. Keeping the two apart is what lets the board
 * be swapped without touching the simulation, and the wiring be changed without touching this.
 */
const WOKWI_PINS: Record<string, string> = (() => {
  const byName: Record<string, string> = {};
  const aliases = board.physical?.pad_aliases ?? {};
  for (const [name, gpio] of Object.entries(board.pins)) {
    byName[name] = WOKWI_NAMES_PINS_BY_GPIO ? String(gpio) : name;
    // A design writes its traces to the label printed on the PAD, and for a few pins that is
    // an abbreviation of the name the board file keys: the FireBeetle prints `MI` and `MO`
    // where the vendor's header says `MISO` and `MOSI`. Keyed only by the board file's names,
    // this table had no entry for the pad, and the emitter reported a perfectly real pin as
    // not existing on the part. Both spellings are kept: nothing is served by making the
    // design guess which one this table happens to use.
    const pad = aliases[name];
    if (pad !== undefined) {
      byName[pad] = WOKWI_NAMES_PINS_BY_GPIO ? String(gpio) : pad;
    }
  }
  return { ...byName, ...(board.wokwi_power_pins ?? {}) };
})();

export const BOARD: PartMapping = {
  // The design calls the module "Mcu" rather than after any one board, so that swapping the
  // board does not rename a component in every trace and every check.
  match: "Mcu",
  wokwiType: board.wokwi_part_type,
  pins: WOKWI_PINS,
};

export const PARTS: PartMapping[] = [
  BOARD,
  {
    match: /^Btn|Button/,
    wokwiType: "wokwi-pushbutton",
    // tscircuit names a pushbutton's terminals A and B; Wokwi gives four pins, two per side of
    // the switch, and either side of a pair is electrically the same.
    pins: { A: "1.l", B: "2.l", pin1: "1.l", pin2: "2.l" },
    attrs: { color: "green" },
    side: "left",
  },
  {
    match: /Oled|SSD1306/,
    wokwiType: "board-ssd1306",
    // The 4-pin I2C module, not `wokwi-ssd1306` which is the 7-pin SPI one. An easy trap.
    pins: { VCC: "VCC", GND: "GND", SDA: "SDA", SCL: "SCL" },
    side: "right",
  },
  {
    // The board carries a 5-pin header; what plugs into it is the rangefinder breakout (or the
    // IR pair, in the fallback build). Either way the simulation wants "something that reports a
    // distance over I2C", which is the custom chip in sim/chips/.
    match: /SensorHeader|Ir(Sensor)?|Tof|Rangefinder|Vl6180/i,
    wokwiType: "chip-vl6180x",
    // Every name the carriers use for the same five pads. `GPIO1` is Pololu's name for the
    // interrupt on carrier #2489 and `OUT` is the IR receiver's; both are the pin this chip
    // calls INT. A breakout's own silkscreen is not negotiable, so the aliases live here.
    pins: { VIN: "VIN", VCC: "VIN", GND: "GND", SDA: "SDA", SCL: "SCL",
            INT: "INT", OUT: "INT", GPIO1: "INT" },
    attrs: { distance: "200" },
    side: "right",
  },
  {
    // Matched on the PART, not on one board's name for the instance. This was the string
    // "MotorDriver", which is what THIS board calls it — a design generated from a module list
    // names its components after the part (`L9110sModule`), and the same physical driver then
    // failed to map. What the simulation needs to know is "this is an L9110S", and the instance
    // name is the board's business.
    match: /^MotorDriver$|L9110/i,
    wokwiType: "chip-l9110s",
    pins: {
      // v2 names the module's own pins; the v1 board's TB6612 names are kept so the old design
      // still converts.
      AIA: "IA",
      AIB: "IB",
      AIN1: "IA",
      AIN2: "IB",
      AO1: "OA",
      AO2: "OB",
      GND: "GND",
      // Pins the stand-in genuinely lacks. The L9110S carries direction and speed on its two
      // inputs, so there is no PWM or standby pin; its second channel is unused; and the
      // simulator powers the chip itself, so VCC is not wired.
      BIA: null,
      BIB: null,
      PWMA: null,
      STBY: null,
      VM: null,
      VCC: null,
    },
    side: "left",
  },
  {
    // A bicolour LED is two dies sharing a cathode, and Wokwi's nearest part is the RGB LED:
    // wire red and green, leave blue unused, and the colours read the same in the simulator.
    match: /StatusLed/,
    wokwiType: "wokwi-rgb-led",
    pins: { RED: "R", GREEN: "G", CATHODE: "COM", BLUE: "B" },
    side: "right",
  },
  {
    match: /^Led/,
    wokwiType: "wokwi-led",
    pins: { anode: "A", cathode: "C", pin1: "A", pin2: "C" },
    attrs: { color: "red" },
    side: "right",
  },
  {
    match: /^R\d|Resistor|^Pullup/,
    wokwiType: "wokwi-resistor",
    // tscircuit calls a two-terminal part's pins anode/cathode (or pin1/pin2) whatever it is;
    // a resistor has no polarity, so either order is correct.
    pins: { pin1: "1", pin2: "2", anode: "1", cathode: "2", left: "1", right: "2" },
    side: "right",
  },
];

/**
 * Things deliberately absent from the simulation.
 *
 * Each needs a reason, so the report reads as a set of decisions rather than a list of holes.
 *
 * **Anchored patterns only.** An unanchored rule silently swallows parts it was never meant to:
 * `/Power/` matched a component renamed to `PowerLed`, and the status LED vanished from the
 * simulation with a cheerful "the simulator powers the board itself". Match whole names.
 */
export const SKIP: SkipRule[] = [
  {
    match: /^(Decoup|Motor(Bulk|Brush))|Cap$/,
    reason: "decoupling and bulk capacitors do nothing in a digital simulation",
  },
  {
    match: /^BinConnector$|PowerInlet|^Jst/i,
    reason: "a connector is wiring, not a part to simulate. Matched by KIND rather than by one "
      + "board's name for it, so a generated design naming its inlet after the part is covered "
      + "too",
  },
  { match: /^Speaker$/, reason: "no Wokwi part; the firmware's log says which cue it played" },
  {
    match: /^(CurrentShunt|PulldownIa|PulldownIb)$/,
    reason: "hardware with no behaviour to simulate: a sense shunt, and the pulldowns that hold "
      + "the motor still while the board boots",
  },
  { match: /^AudioAmp$/, reason: "no Wokwi part for the I2S amplifier; cues are visible in the serial log" },
  {
    match: /^(TofInt|BtnOpen)Pull(up|down)$/,
    reason: "these hold a deep-sleep wake input at a defined level while the chip is off. Wokwi "
      + "does not wake this chip from a GPIO at all and has no floating-input model, so every "
      + "part it drives is driven — the exact condition these resistors exist for cannot be "
      + "simulated here, and must be checked on the bench. Matched in BOTH directions because "
      + "which one they are is the board's decision, not this file's: they became pull-DOWNS "
      + "when the wake sources moved to 3V3, and a rule naming only one spelling silently "
      + "stopped covering them",
  },
  {
    match: /^(Sda|Scl)Pullup$/,
    reason: "Wokwi's I2C is idealised — its bus reads back correctly with no pull-ups at all, "
      + "so simulating them proves nothing. Which is exactly why their absence on the real "
      + "board went unnoticed: no simulation could ever have caught it",
  },
];

export function findMapping(componentName: string): PartMapping | undefined {
  return PARTS.find((part) => matches(part.match, componentName));
}

export function findSkipRule(componentName: string): SkipRule | undefined {
  return SKIP.find((rule) => matches(rule.match, componentName));
}

function matches(pattern: string | RegExp, name: string): boolean {
  return typeof pattern === "string" ? pattern === name : pattern.test(name);
}

/**
 * The Wokwi pin name for a design pin, or null when the stand-in part deliberately lacks it.
 * Falls back to the design's own name, which is right whenever the two agree.
 */
export function wokwiPinName(mapping: PartMapping, designPin: string): string | null {
  if (mapping.pins && designPin in mapping.pins) return mapping.pins[designPin] ?? null;
  return designPin;
}
