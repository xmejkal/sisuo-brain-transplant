import { XiaoRealFootprint } from "./XIAO-ESP32-C6-SMD"

/**
 * Smart bin, board v2 — Seeed XIAO ESP32-C6.
 *
 * This is the board the firmware in firmware/micropython/ expects and the simulation in
 * firmware/micropython/sim/ models. The three must agree; `tools/circuit-to-wokwi` regenerates
 * the simulation from this file and fails if they drift.
 *
 * What changed from v1 (board-v1-tb6612.tsx, kept for reference):
 *  - no OLED: the bin never had a screen, and a bicolour LED says everything it needs to.
 *  - L9110S instead of the TB6612: right current class, two inputs instead of three, and the
 *    same simple design the original board used.
 *  - a VL6180X time-of-flight rangefinder replaces the IR pair, on I2C.
 *  - the pin map moved, because **only GPIO0-7 can wake an ESP32-C6 from deep sleep** — on the
 *    XIAO that is D0, D1 and D2, so those three carry the sensor interrupt, the OPEN button and
 *    the one analogue input.
 *  - the MP3 module's TXD is deliberately not wired: powered from the LiPo its idle level
 *    exceeds what this chip tolerates, and nothing reads it.
 *
 * Pin map (D-pin = GPIO): D0=0 D1=1 D2=2 D3=21 D4=22 D5=23 D6=16 D7=17 D8=19 D9=20 D10=18.
 *
 * The outline is 70 x 45 mm, and it is set by what sits on it. Only three things do: the XIAO,
 * the motor driver and the MP3 module. The rangefinder has to look out through the lid and the
 * speaker sits behind a grille, so both are on ribbons to their own 2.54 mm headers and take no
 * board area at all — modelling them as plug-in modules is what made an earlier layout collide
 * with itself. `tools/check-module-clearance.py` reads the 3D bodies back out of the build and
 * reports anything that overlaps or hangs off the edge.
 *
 * The outline still has to be checked against the bin's own cavity before anything is ordered.
 */
export default () => (
  <board width="70mm" height="45mm" autorouter="auto">
    <XiaoRealFootprint name="XIAO" pcbX={-30.92} pcbY={-22.94}
      cadModel={{
        // Seeed publish no 3D model for the C6 (the S3's is a different board), so this is the
        // module's own outline: 21 x 17.5 mm, and 3.5 mm tall over the shield can.
        jscad: {
          type: "colorize",
          color: [0.09, 0.09, 0.1],
          shape: { type: "roundedCuboid", size: [21, 17.5, 3.5], roundRadius: 0.8, segments: 16 },
        },
      }}
      pinLabels={{
        pin1: "TOF_INT",    // D0  - wake-capable
        pin2: "BTN_OPEN",   // D1  - wake-capable
        pin3: "MOTOR_SENSE",// D2  - the only spare ADC pin; stall sensing or a limit switch
        pin4: "MOTOR_IA",   // D3
        pin5: "SDA",        // D4
        pin6: "SCL",        // D5
        pin7: "BTN_MODE",   // D6  - also the ROM console TX: fine for a button, never for the MP3
        pin8: "LED_RED",    // D7
        pin9: "MOTOR_IB",   // D8
        pin10: "MP3_TX",    // D9
        pin11: "LED_GREEN", // D10
        pin12: "V33", pin13: "GND", pin14: "V5",
        // The LiPo pads on the underside. Without these the battery reaches the MP3 module and
        // nothing else, and the bin is mains-only — which is what this board did until now.
        //
        // Polarity is from Seeed's own back-view pinout (parts/xiao/pinout_back.png): looking at
        // the back with USB at the top, BAT- is left and BAT+ is right. This footprint is the
        // top-side land pattern, so it is mirrored: pin23 (x=7.11) is BAT+, pin24 (x=9.65) is
        // BAT-. Cross-checked by scaling the drawing against the 17.78 mm board width.
        //
        // CONFIRM WITH A METER BEFORE CONNECTING A CELL: continuity from pin24 to any GND pin.
        // parts/xiao/getting_started.md says the negative pad is "closest to the USB port", which
        // cannot be read off this footprint at all — both pads share y=4.97. Reversed LiPo
        // polarity destroys the module, so this is worth thirty seconds with a multimeter.
        pin23: "BAT_POS", pin24: "BAT_NEG",
      }} />

    {/* L9110S module on a 6-pin header. Its two motor terminals are screw terminals on the
        module itself, wired to MotorOut below with short leads.

        The 3D body is a real model of this module (CC0), so the render shows what actually
        plugs in rather than a bare header. */}
    <chip name="MotorDriver" footprint="headermodule6" pcbX={-19} pcbY={10.5}
      cadModel={{
        stepUrl: "https://raw.githubusercontent.com/fox7524/MEB-Robotik/main/7-Ortak%20Tasar%C4%B1m/mini_sumo-l9110_driver.step",
        rotationOffset: { x: 0, y: 0, z: 90 },
      }}
      pinLabels={{ pin1:"BIA", pin2:"BIB", pin3:"GND", pin4:"VCC", pin5:"AIA", pin6:"AIB" }} />

    {/* The rangefinder breakout: VIN/GND/SDA/SCL and its interrupt. The same header takes the
        IR LED + receiver fallback, which is why it carries five pins rather than four.

        No 3D body here on purpose: the sensor has to look out through the lid, tens of
        millimetres away from wherever the board is screwed down, so it is never on the board.
        The module carries a 2.54 mm header of its own, and a five-way ribbon reaches it. What
        is on the board is this header — and only this header needs the space. */}
    <chip name="SensorHeader" footprint="pinrow5" pcbX={-3} pcbY={-3}
      pinLabels={{ pin1:"VIN", pin2:"GND", pin3:"SDA", pin4:"SCL", pin5:"INT" }} />

    {/* DFRobot publishes no 3D model for this module, only a dimension drawing — so the body is
        built from it: 30.00 x 22.00 mm, which is what that drawing says. */}
    <chip name="Mp3Player" footprint="headermodule6" pcbX={18} pcbY={11}
      cadModel={{
        jscad: {
          type: "colorize",
          color: [0.06, 0.29, 0.53],
          shape: { type: "cuboid", size: [30, 22, 3.2] },
        },
      }}
      pinLabels={{ pin1:"VCC", pin2:"GND", pin3:"RXD", pin4:"TXD", pin5:"SPKP", pin6:"SPKN" }} />
    {/* The speaker is a 30 mm driver behind a grille on its own flying lead, so what the board
        carries is this two-way JST and nothing else. Its size still has to be checked against
        the bin — see the enclosure notes, not this file. */}
    <chip name="Speaker" footprint="jst_ph_2" pcbX={8} pcbY={-4} pinLabels={{ pin1:"P", pin2:"N" }} />

    {/* Bicolour LED, common cathode: two anodes and one shared return. */}
    <chip name="StatusLed" footprint="pinrow3" pcbX={17} pcbY={-17}
      cadModel={{
        jscad: {
          type: "colorize",
          color: [0.85, 0.85, 0.88],
          shape: { type: "cylinder", radius: 2.5, height: 8.6, resolution: 32 },
        },
      }}
      pinLabels={{ pin1:"RED", pin2:"CATHODE", pin3:"GREEN" }} />
    <resistor name="RedResistor" resistance="330" footprint="0603" pcbX={17} pcbY={-13} />
    <resistor name="GreenResistor" resistance="330" footprint="0603" pcbX={21} pcbY={-13} />

    {/* Real bodies from the part library, by LCSC number — a 6x6 tactile switch and JST PH
        shells. These are the parts the shopping list actually names. */}
    <chip name="BtnOpen" footprint="pushbutton" pcbX={-3} pcbY={-17} pinLabels={{ pin1:"A", pin4:"B" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C110153#ext=obj" }} />
    <chip name="BtnMode" footprint="pushbutton" pcbX={7} pcbY={-17} pinLabels={{ pin1:"A", pin4:"B" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C110153#ext=obj" }} />

    <chip name="BinConnector" footprint="jst_ph_4" pcbX={30} pcbY={-4}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C131334#ext=obj" }}
      pinLabels={{ pin1:"BATP", pin2:"BATN", pin3:"MOTA", pin4:"MOTB" }} />
    <chip name="MotorOut" footprint="jst_ph_2" pcbX={31} pcbY={-11} pinLabels={{ pin1:"OA", pin2:"OB" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C131337#ext=obj" }} />
    <chip name="LipoBattery" footprint="jst_ph_2" pcbX={31} pcbY={-18} pinLabels={{ pin1:"POS", pin2:"NEG" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C131337#ext=obj" }} />

    {/* The pins float for ~300 ms between reset and the firmware running. These are what keep the
        motor still in that window, and through any crash or reflash.

        They return to the driver's OWN ground, not the board's: the shunt lifts the driver's
        ground above system ground while the motor runs, so a pulldown to system ground would
        hold the inputs *below* the driver's idea of zero — outside its input range, and an
        injection path into the chip. */}
    <resistor name="PulldownIa" resistance="10k" footprint="0603" pcbX={-1} pcbY={13} />
    <resistor name="PulldownIb" resistance="10k" footprint="0603" pcbX={-1} pcbY={17} />

    {/* Low-side shunt: the driver's ground returns through it, and D2 reads the voltage across
        it. 0.33 ohm gives ~23 mV running and ~76 mV stalled — above the C6 ADC's noise, while
        costing the motor a tenth of what 1 ohm did.

        The sense line reaches the ADC through a series resistor and a capacitor: the resistor
        limits the current into the pin if the motor ever stalls hard enough to lift this node
        toward the rail, and the capacitor averages the PWM chopping the reading. */}
    <resistor name="CurrentShunt" resistance="0.33" footprint="0805" pcbX={-1} pcbY={1} />
    <resistor name="SenseResistor" resistance="1k" footprint="0603" pcbX={-6} pcbY={-9} />
    {/* 1k + 1uF = 159 Hz, against a 5 kHz PWM carrier: about 30x attenuation, so roughly 1% of
        the ripple survives to the ADC pin. It was 100nF, which puts the corner at 1.6 kHz and
        leaves ~30% of the carrier on the pin — `STALL_SAMPLES = 8` was averaging that away rather
        than the ADC's own noise, which is what it says it is for.

        The time constant is 1 ms, so a stall is visible well inside `MOTION_POLL_MS = 10`. Do not
        grow this much further: the ESP32 ADC wants a low source impedance and a slow settle here
        turns into a late stall. */}
    <capacitor name="SenseFilterCap" capacitance="1uF" footprint="0603" pcbX={-6} pcbY={-11} />

    <capacitor name="MotorBulkCap" capacitance="220uF" footprint="0805" pcbX={-1} pcbY={5} />
    <capacitor name="Mp3ReservoirCap" capacitance="470uF" footprint="0805" pcbX={14} pcbY={-2} />
    <capacitor name="DecoupMotor" capacitance="100nF" footprint="0603" pcbX={-1} pcbY={9} />
    <capacitor name="DecoupMp3" capacitance="100nF" footprint="0603" pcbX={19} pcbY={-2} />
    <capacitor name="DecoupSensor" capacitance="100nF" footprint="0603" pcbX={-6} pcbY={-6} />

    {/* I2C has no push-pull high side: without these the bus never leaves logic 0 and no device
        answers. DESIGN_RULES.md has required them since it was written; the board did not have
        them. The rule and the board disagreed and nothing compared the two.

        4.7k is the usual starting point. It is a budget, not a constant: every extra breakout
        with its own pull-ups puts another resistor in parallel, and the ToF sensor sits on a
        ribbon whose capacitance slows the rising edge. If the bus misbehaves at 400 kHz, the
        numbers to reach for are the total parallel resistance and the cable length. */}
    <resistor name="SdaPullup" resistance="4.7k" footprint="0603" pcbX={-10} pcbY={-6} />
    <resistor name="SclPullup" resistance="4.7k" footprint="0603" pcbX={-10} pcbY={-10} />
    {/* Across the motor terminals: brush arcing, not inductive kickback, is what upsets I2C. */}
    <capacitor name="MotorBrushCap" capacitance="100nF" footprint="0603" pcbX={24} pcbY={-14.5} />

    {/* ---- power ---------------------------------------------------------------------- */}
    <trace from=".BinConnector > .BATP" to="net.MOTOR6V" />
    <trace from=".MotorDriver > .VCC" to="net.MOTOR6V" />
    <trace from=".MotorBulkCap > .pin1" to="net.MOTOR6V" />
    <trace from=".DecoupMotor > .pin1" to="net.MOTOR6V" />
    <trace from=".BinConnector > .BATN" to="net.GND" />
    <trace from=".MotorBulkCap > .pin2" to="net.GND" />
    <trace from=".DecoupMotor > .pin2" to="net.GND" />
    <trace from=".XIAO > .GND" to="net.GND" />
    <trace from=".XIAO > .V33" to="net.V33" />
    <trace from=".LipoBattery > .POS" to="net.VBAT" />
    <trace from=".LipoBattery > .NEG" to="net.GND" />
    {/* The cell feeds the XIAO's own charger and regulator, not just the amplifier. */}
    <trace from=".XIAO > .BAT_POS" to="net.VBAT" />
    <trace from=".XIAO > .BAT_NEG" to="net.GND" />
    <trace from=".Mp3Player > .VCC" to="net.VBAT" />
    <trace from=".Mp3Player > .GND" to="net.GND" />
    <trace from=".Mp3ReservoirCap > .pin1" to="net.VBAT" />
    <trace from=".Mp3ReservoirCap > .pin2" to="net.GND" />
    <trace from=".DecoupMp3 > .pin1" to="net.VBAT" />
    <trace from=".DecoupMp3 > .pin2" to="net.GND" />

    {/* ---- motor ---------------------------------------------------------------------- */}
    <trace from=".XIAO > .MOTOR_IA" to=".MotorDriver > .AIA" />
    <trace from=".XIAO > .MOTOR_IB" to=".MotorDriver > .AIB" />
    <trace from=".PulldownIa > .pin1" to=".MotorDriver > .AIA" />
    <trace from=".PulldownIa > .pin2" to="net.MOTOR_SENSE" />
    <trace from=".PulldownIb > .pin1" to=".MotorDriver > .AIB" />
    <trace from=".PulldownIb > .pin2" to="net.MOTOR_SENSE" />
    {/* Channel B is unused — one motor, one channel — but its inputs are still inputs on a
        powered chip, and a floating CMOS input has no defined level. It drifts, and on an
        H-bridge an undefined input is how both halves of a bridge end up conducting at once.

        Tied to the driver's own ground rather than the board's, for the same reason the channel A
        pulldowns are: the shunt lifts the driver's GND above system ground, and an input judged
        against the wrong reference is the bug those pulldowns exist to avoid. Both low is the
        L9110's coast state, which is what an unused channel should be doing. */}
    <trace from=".MotorDriver > .BIA" to="net.MOTOR_SENSE" />
    <trace from=".MotorDriver > .BIB" to="net.MOTOR_SENSE" />
    <trace from=".MotorDriver > .GND" to="net.MOTOR_SENSE" />
    <trace from=".CurrentShunt > .pin1" to="net.MOTOR_SENSE" />
    <trace from=".CurrentShunt > .pin2" to="net.GND" />
    <trace from=".SenseResistor > .pin1" to="net.MOTOR_SENSE" />
    <trace from=".SenseResistor > .pin2" to="net.SENSE_ADC" />
    <trace from=".XIAO > .MOTOR_SENSE" to="net.SENSE_ADC" />
    <trace from=".SenseFilterCap > .pin1" to="net.SENSE_ADC" />
    <trace from=".SenseFilterCap > .pin2" to="net.GND" />
    <trace from=".BinConnector > .MOTA" to=".MotorOut > .OA" />
    <trace from=".BinConnector > .MOTB" to=".MotorOut > .OB" />
    <trace from=".MotorBrushCap > .pin1" to=".MotorOut > .OA" />
    <trace from=".MotorBrushCap > .pin2" to=".MotorOut > .OB" />

    {/* ---- sensor (I2C + interrupt) --------------------------------------------------- */}
    <trace from=".SensorHeader > .VIN" to="net.V33" />
    <trace from=".SensorHeader > .GND" to="net.GND" />
    {/* Through named nets rather than pin-to-pin, because the pull-ups are a third member of
        each. A resistor wired straight to a chip pin is the trace that trips tscircuit's
        unsatisfiable 1 mm rule and makes the autorouter skip the whole board. */}
    <trace from=".XIAO > .SDA" to="net.SDA" />
    <trace from=".SensorHeader > .SDA" to="net.SDA" />
    <trace from=".SdaPullup > .pin1" to="net.SDA" />
    <trace from=".SdaPullup > .pin2" to="net.V33" />
    <trace from=".XIAO > .SCL" to="net.SCL" />
    <trace from=".SensorHeader > .SCL" to="net.SCL" />
    <trace from=".SclPullup > .pin1" to="net.SCL" />
    <trace from=".SclPullup > .pin2" to="net.V33" />
    <trace from=".XIAO > .TOF_INT" to=".SensorHeader > .INT" />
    <trace from=".DecoupSensor > .pin1" to="net.V33" />
    <trace from=".DecoupSensor > .pin2" to="net.GND" />

    {/* ---- audio ---------------------------------------------------------------------- */}
    {/* Only TX: the module's TXD stays unwired, on purpose. */}
    <trace from=".XIAO > .MP3_TX" to=".Mp3Player > .RXD" />
    <trace from=".Mp3Player > .SPKP" to=".Speaker > .P" />
    <trace from=".Mp3Player > .SPKN" to=".Speaker > .N" />

    {/* ---- buttons and status --------------------------------------------------------- */}
    <trace from=".BtnOpen > .A" to=".XIAO > .BTN_OPEN" />
    <trace from=".BtnOpen > .B" to="net.GND" />
    <trace from=".BtnMode > .A" to=".XIAO > .BTN_MODE" />
    <trace from=".BtnMode > .B" to="net.GND" />
    <trace from=".XIAO > .LED_RED" to=".RedResistor > .pin1" />
    <trace from=".RedResistor > .pin2" to=".StatusLed > .RED" />
    <trace from=".XIAO > .LED_GREEN" to=".GreenResistor > .pin1" />
    <trace from=".GreenResistor > .pin2" to=".StatusLed > .GREEN" />
    <trace from=".StatusLed > .CATHODE" to="net.GND" />
  </board>
)
