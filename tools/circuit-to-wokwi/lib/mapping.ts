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
 * The board itself. Its pins are the XIAO silkscreen names — D0..D10, 3V3, 5V, GND — and
 * crucially NOT GPIO numbers, which Wokwi rejects for this part.
 */
export const BOARD: PartMapping = {
  match: "XIAO",
  wokwiType: "board-xiao-esp32-c6",
  // The design names pins by function; Wokwi names them by silkscreen. This table is the pin map
  // from config.py, read the other way round.
  pins: {
    MA_IN1: "D0",
    MA_IN2: "D1",
    IR_RX: "D2",
    MA_PWM: "D3",
    SDA: "D4",
    SCL: "D5",
    BTN_OPEN: "D6",
    BTN_MODE: "D7",
    SPARE: "D8",
    MP3_TX: "D9",
    MP3_RX: "D10",
    V33: "3V3",
    V5: "5V",
    GND: "GND",
  },
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
    match: /Ir(Sensor)?/,
    wokwiType: "chip-vl6180x",
    // Our own chip: the board's IR module and the v2 rangefinder both stand in as this, because
    // what the simulation needs is "something that reports a distance over I2C".
    pins: { VCC: "VIN", GND: "GND", OUT: "INT", SDA: "SDA", SCL: "SCL" },
    attrs: { distance: "200" },
    side: "right",
  },
  {
    match: "MotorDriver",
    wokwiType: "chip-l9110s",
    pins: {
      AIN1: "IA",
      AIN2: "IB",
      AO1: "OA",
      AO2: "OB",
      GND: "GND",
      // The board's TB6612 has a separate PWM input and a standby pin; the L9110S standing in for
      // it has neither, because its two inputs carry direction and speed together.
      PWMA: null,
      STBY: null,
      VM: null,
      VCC: null,
    },
    side: "left",
  },
  {
    match: /^Led|StatusLed/,
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
 */
export const SKIP: SkipRule[] = [
  {
    match: /Cap|Decoup|^C\d+$/,
    reason: "decoupling and bulk capacitors do nothing in a digital simulation",
  },
  { match: /Connector|JST|BinConnector/, reason: "a connector is wiring, not a part to simulate" },
  { match: /Speaker/, reason: "no Wokwi part; the firmware's log says which cue it played" },
  { match: /Mp3Player|DFR0534/, reason: "no Wokwi part; cues are visible in the serial log" },
  { match: /Battery|Lipo|Power/, reason: "the simulator powers the board itself" },
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
