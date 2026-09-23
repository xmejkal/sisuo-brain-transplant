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
 */
export default () => (
  <board width="70mm" height="45mm" autorouter="auto">
    <XiaoRealFootprint name="XIAO" pcbX={-8.9} pcbY={-10.5}
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
      }} />

    {/* L9110S module on a 6-pin header. Its two motor terminals are screw terminals on the
        module itself, wired to MotorOut below with short leads. */}
    <chip name="MotorDriver" footprint="headermodule6" pcbX={-24} pcbY={6}
      pinLabels={{ pin1:"BIA", pin2:"BIB", pin3:"GND", pin4:"VCC", pin5:"AIA", pin6:"AIB" }} />

    {/* The rangefinder breakout: VIN/GND/SDA/SCL and its interrupt. The same header takes the
        IR LED + receiver fallback, which is why it carries five pins rather than four. */}
    <chip name="SensorHeader" footprint="pinrow5" pcbX={0} pcbY={-17}
      pinLabels={{ pin1:"VIN", pin2:"GND", pin3:"SDA", pin4:"SCL", pin5:"INT" }} />

    <chip name="Mp3Player" footprint="headermodule6" pcbX={24} pcbY={6}
      pinLabels={{ pin1:"VCC", pin2:"GND", pin3:"RXD", pin4:"TXD", pin5:"SPKP", pin6:"SPKN" }} />
    <chip name="Speaker" footprint="jst_ph_2" pcbX={28} pcbY={15} pinLabels={{ pin1:"P", pin2:"N" }} />

    {/* Bicolour LED, common cathode: two anodes and one shared return. */}
    <chip name="StatusLed" footprint="pinrow3" pcbX={0} pcbY={17}
      pinLabels={{ pin1:"RED", pin2:"CATHODE", pin3:"GREEN" }} />
    <resistor name="RedResistor" resistance="330" footprint="0603" pcbX={-5} pcbY={13} />
    <resistor name="GreenResistor" resistance="330" footprint="0603" pcbX={5} pcbY={13} />

    <chip name="BtnOpen" footprint="pushbutton" pcbX={-13} pcbY={-17} pinLabels={{ pin1:"A", pin4:"B" }} />
    <chip name="BtnMode" footprint="pushbutton" pcbX={13} pcbY={-17} pinLabels={{ pin1:"A", pin4:"B" }} />

    <chip name="BinConnector" footprint="jst_ph_4" pcbX={-27} pcbY={-6}
      pinLabels={{ pin1:"BATP", pin2:"BATN", pin3:"MOTA", pin4:"MOTB" }} />
    <chip name="MotorOut" footprint="jst_ph_2" pcbX={-27} pcbY={13} pinLabels={{ pin1:"OA", pin2:"OB" }} />
    <chip name="LipoBattery" footprint="jst_ph_2" pcbX={28} pcbY={-6} pinLabels={{ pin1:"POS", pin2:"NEG" }} />

    {/* The pins float for ~300 ms between reset and the firmware running. These are what keep the
        motor still in that window, and through any crash or reflash.

        They return to the driver's OWN ground, not the board's: the shunt lifts the driver's
        ground above system ground while the motor runs, so a pulldown to system ground would
        hold the inputs *below* the driver's idea of zero — outside its input range, and an
        injection path into the chip. */}
    <resistor name="PulldownIa" resistance="10k" footprint="0603" pcbX={-17} pcbY={9} />
    <resistor name="PulldownIb" resistance="10k" footprint="0603" pcbX={-17} pcbY={12} />

    {/* Low-side shunt: the driver's ground returns through it, and D2 reads the voltage across
        it. 0.33 ohm gives ~23 mV running and ~76 mV stalled — above the C6 ADC's noise, while
        costing the motor a tenth of what 1 ohm did.

        The sense line reaches the ADC through a series resistor and a capacitor: the resistor
        limits the current into the pin if the motor ever stalls hard enough to lift this node
        toward the rail, and the capacitor averages the PWM chopping the reading. */}
    <resistor name="CurrentShunt" resistance="0.33" footprint="0805" pcbX={-21} pcbY={-1} />
    <resistor name="SenseResistor" resistance="1k" footprint="0603" pcbX={-13} pcbY={-1} />
    <capacitor name="SenseFilterCap" capacitance="100nF" footprint="0603" pcbX={-13} pcbY={2} />

    <capacitor name="MotorBulkCap" capacitance="220uF" footprint="0805" pcbX={-19} pcbY={-8} />
    <capacitor name="Mp3ReservoirCap" capacitance="470uF" footprint="0805" pcbX={19} pcbY={-8} />
    <capacitor name="DecoupMotor" capacitance="100nF" footprint="0603" pcbX={-17} pcbY={3} />
    <capacitor name="DecoupMp3" capacitance="100nF" footprint="0603" pcbX={17} pcbY={3} />
    <capacitor name="DecoupSensor" capacitance="100nF" footprint="0603" pcbX={7} pcbY={-13} />
    {/* Across the motor terminals: brush arcing, not inductive kickback, is what upsets I2C. */}
    <capacitor name="MotorBrushCap" capacitance="100nF" footprint="0603" pcbX={-19} pcbY={17} />

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
    <trace from=".XIAO > .SDA" to=".SensorHeader > .SDA" />
    <trace from=".XIAO > .SCL" to=".SensorHeader > .SCL" />
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
