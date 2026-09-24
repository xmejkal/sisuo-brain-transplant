import { FireBeetle2Esp32S3 } from "./FireBeetle2Esp32S3"
import { fireBeetle2Esp32S3Body } from "./FireBeetle2Esp32S3Body"
import { MCU } from "./mcu-pins"

/**
 * Smart bin, board v3 — DFRobot FireBeetle 2 ESP32-S3.
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
 *  - the MP3 module's TXD is deliberately not wired: nothing reads it, and the module is not
 *    3.3V tolerant in that direction.
 *
 * What changed from v2 (the Seeed XIAO ESP32-C6 version):
 *  - **the board.** The C6 could only wake from GPIO0-7, which on the XIAO meant three usable
 *    pins and a pin map bent entirely around them. The S3 has 22 RTC pins, so the map is now
 *    chosen for other reasons — see firmware/micropython/config.py, which explains each one.
 *  - **no LiPo connector.** The FireBeetle carries its own JST battery socket and an ETA6003
 *    charger, so the cell plugs into the module. That also retires the XIAO's BAT-pad polarity
 *    question, which needed a multimeter to answer safely.
 *  - **no VBAT rail.** There is no raw-battery pin on the FireBeetle's header, and there does
 *    not need to be: its 3V3 is a TPS62A02 buck good for 2 A (DFR0975 schematic V1.3), where the
 *    XIAO had a small LDO. The MP3 module sat on VBAT only to keep audio transients off that
 *    LDO; a 2 A buck carries them with room to spare, and 3.3 V is within the DFR0534's stated
 *    3.3-5 V range. Its reservoir cap stays, now local to 3V3.
 *
 * Pin map: the silkscreen label is NOT the GPIO. boards/firebeetle2-esp32s3.json is the one
 * place that map lives; the aliases below name the signal, so the traces read as intent.
 *
 * The outline is 100 x 62 mm, set by what sits on it. The FireBeetle alone is 25.4 x 60 mm —
 * larger than the entire component cluster on v2 — so it lies along the length with its USB-C
 * at the left edge, and everything else shares the strip above it and the zone to its right. 45 mm
 * was tried first and does not fit: the motor driver and the MP3 module are 23 and 22 mm tall,
 * which stack to exactly the board height, leaving nothing for two edges and a gap. The rangefinder has to look out through the lid and the
 * speaker sits behind a grille, so both are on ribbons to their own 2.54 mm headers and take no
 * board area at all — modelling them as plug-in modules is what made an earlier layout collide
 * with itself. `tools/check-module-clearance.py` reads the 3D bodies back out of the build and
 * reports anything that overlaps or hangs off the edge.
 *
 * The outline still has to be checked against the bin's own cavity before anything is ordered.
 */
export default () => (
  <board width="100mm" height="62mm" autorouter="auto"
      thickness="1.6mm"
      fabricatorPreset="jlcpcb_economy"
      automaticPoursEnabled>
    {/* The module lies along the board with its USB-C at the left edge, so a cable can reach it
        without opening the bin further than the lid already opens.

        The footprint is generated (tools/generate-firebeetle-footprint.py) rather than taken
        from a library: every pin position on this board is an obround pad made of a through-hole
        1.27 mm inboard of the edge AND a castellated half-hole centred on the edge. Measure the
        outer circles and the rows are 25.40 mm apart; measure the holes a header actually solders
        into and they are 22.86 mm. A published KiCad footprint for this board uses the former.

        The aliases below are the whole reason the traces did not change when the board did: they
        name the signal, and only this block knows which silkscreen pin carries it. */}
    <FireBeetle2Esp32S3 name="Mcu" pcbX={-19} pcbY={-11} pcbRotation={90}
      cadModel={fireBeetle2Esp32S3Body}
      />

    {/* L9110S module on a 6-pin header. Its two motor terminals are screw terminals on the
        module itself, wired to MotorOut below with short leads.

        The 3D body is a real model of this module (CC0), so the render shows what actually
        plugs in rather than a bare header. */}
    <chip name="MotorDriver" footprint="headermodule6" pcbX={28} pcbY={12}
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
    <chip name="SensorHeader" footprint="pinrow5" pcbX={-42} pcbY={17}
      pinLabels={{ pin1:"VIN", pin2:"GND", pin3:"SDA", pin4:"SCL", pin5:"INT" }} />

    {/* DFRobot publishes no 3D model for this module, only a dimension drawing — so the body is
        built from it: 30.00 x 22.00 mm, which is what that drawing says. */}
    <chip name="Mp3Player" footprint="headermodule6" pcbX={28} pcbY={-12}
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
    <chip name="Speaker" footprint="jst_ph_2" pcbX={46.5} pcbY={-20} pinLabels={{ pin1:"P", pin2:"N" }} />

    {/* Bicolour LED, common cathode: two anodes and one shared return. */}
    <chip name="StatusLed" footprint="pinrow3" pcbX={-6} pcbY={17}
      cadModel={{
        jscad: {
          type: "colorize",
          color: [0.85, 0.85, 0.88],
          shape: { type: "cylinder", radius: 2.5, height: 8.6, resolution: 32 },
        },
      }}
      pinLabels={{ pin1:"RED", pin2:"CATHODE", pin3:"GREEN" }} />
    <resistor name="RedResistor" resistance="330" footprint="0603" pcbX={-10} pcbY={9} />
    <resistor name="GreenResistor" resistance="330" footprint="0603" pcbX={-4} pcbY={9} />

    {/* Real bodies from the part library, by LCSC number — a 6x6 tactile switch and JST PH
        shells. These are the parts the shopping list actually names. */}
    <chip name="BtnOpen" footprint="pushbutton" pcbX={-26} pcbY={15} pinLabels={{ pin1:"A", pin4:"B" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C110153#ext=obj" }} />
    <chip name="BtnMode" footprint="pushbutton" pcbX={-16} pcbY={15} pinLabels={{ pin1:"A", pin4:"B" }}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C110153#ext=obj" }} />

    <chip name="BinConnector" footprint="jst_ph_4" pcbX={-38} pcbY={25}
      cadModel={{ objUrl: "https://modelcdn.tscircuit.com/easyeda_models/download?pn=C131334#ext=obj" }}
      pinLabels={{ pin1:"BATP", pin2:"BATN", pin3:"MOTA", pin4:"MOTB" }} />

    {/* The pins float for ~300 ms between reset and the firmware running. These are what keep the
        motor still in that window, and through any crash or reflash.

        They return to the driver's OWN ground, not the board's: the shunt lifts the driver's
        ground above system ground while the motor runs, so a pulldown to system ground would
        hold the inputs *below* the driver's idea of zero — outside its input range, and an
        injection path into the chip. */}
    <resistor name="PulldownIa" resistance="10k" footprint="0603" pcbX={3} pcbY={4} />
    <resistor name="PulldownIb" resistance="10k" footprint="0603" pcbX={8} pcbY={4} />

    {/* Low-side shunt: the driver's ground returns through it, and the ADC reads across it.

        0.1 ohm in a 2512, not 0.33 ohm in an 0805. The change was made WITHOUT knowing the
        motor's stall current, and that is the point — it is the value that is correct across the
        whole plausible range instead of the value that is correct if the guess holds:

          at 1 A    0805 0.33R dissipates 0.33 W into a 0.125 W part   2512 0.1R: 0.10 W of 1 W
          at 2 A    0805 0.33R dissipates 1.32 W                        2512 0.1R: 0.40 W of 1 W

        It also fixes something worse than heat. The shunt lifts the driver's ground above system
        ground while the motor runs, and the MCU drives IA/IB referenced to SYSTEM ground — so
        the driver sees its logic inputs below its own zero by exactly that lift. At 0.33 ohm and
        2 A that is 660 mV, well past the input protection diode. At 0.1 ohm it is 200 mV.

        The cost is signal: 0.1 ohm gives a third of the millivolts. That is paid for by dropping
        the ADC from 11 dB to 0 dB attenuation (~950 mV full scale instead of ~3.1 V), which the
        smaller shunt makes safe — the signal can no longer reach the rail however hard the motor
        stalls. Net resolution is better than before, not worse.

        `STALL_COUNTS` still has to be calibrated on the bench; it always did. What has changed is
        that nothing IRREVERSIBLE now depends on the unmeasured number. */}
    <resistor name="CurrentShunt" resistance="0.1" footprint="2512" pcbX={32} pcbY={26} />
    <resistor name="SenseResistor" resistance="1k" footprint="0603" pcbX={-31} pcbY={4} />
    {/* 1k + 1uF = 159 Hz, against a 5 kHz PWM carrier: about 30x attenuation, so roughly 1% of
        the ripple survives to the ADC pin. It was 100nF, which puts the corner at 1.6 kHz and
        leaves ~30% of the carrier on the pin — `STALL_SAMPLES = 8` was averaging that away rather
        than the ADC's own noise, which is what it says it is for.

        The time constant is 1 ms, so a stall is visible well inside `MOTION_POLL_MS = 10`. Do not
        grow this much further: the ESP32 ADC wants a low source impedance and a slow settle here
        turns into a late stall. */}
    <capacitor name="SenseFilterCap" capacitance="1uF" maxVoltageRating="50V" footprint="0603"
      // Pinned, not matched. The exported BOM was assigning C14663 to this line - which the
      // supplier's own catalogue says is 100nF, the same part as the four decouplers. At 100nF
      // the filter corner is 1.6 kHz instead of the 159 Hz the comment below depends on, so the
      // stall detector would average PWM ripple rather than motor current.
      supplierPartNumbers={{ jlcpcb: ["C5199872"] }} pcbX={-35} pcbY={4} />

    {/* Radial through-hole, NOT 0805. There is no 220uF or 470uF part in an 0805 land at any
        voltage — the largest 0805 MLCC is tens of microfarads and derates hard under DC bias, and
        no electrolytic exists in that package. The exported BOM was quietly matching a 220uF 4V
        TANTALUM to this line, on a 6.4 V rail; a tantalum above its rating fails SHORT. These are
        also the parts SHOPPING.md actually buys: 6x11 mm radial, from Hadex — which is why both
        are `doNotPlace`. They are hand-soldered, so the assembler must not be asked to source
        them, and the BOM must not imply a supplier part nobody verified. */}
    <capacitor name="MotorBulkCap" doNotPlace capacitance="220uF" maxVoltageRating="25V" polarized footprint="radial_d6.3_p2.5" pcbX={45} pcbY={15} />
    <capacitor name="Mp3ReservoirCap" doNotPlace capacitance="470uF" maxVoltageRating="16V" polarized footprint="radial_d8_p3.5" pcbX={45} pcbY={-6} />
    <capacitor name="DecoupMotor" capacitance="100nF" maxVoltageRating="50V" footprint="0603" pcbX={45} pcbY={9} />
    <capacitor name="DecoupMp3" capacitance="100nF" maxVoltageRating="50V" footprint="0603" pcbX={45} pcbY={-13} />
    <capacitor name="DecoupSensor" capacitance="100nF" maxVoltageRating="50V" footprint="0603" pcbX={-39} pcbY={10} />

    {/* High-side switch on the MP3 module's supply.

        This exists because of a number nobody has measured. The DFR0534 has no enable pin and
        sits permanently on the rail; its own class idles somewhere around 15-25 mA, which if
        true is roughly forty times everything else on this board combined, and would make the
        entire deep-sleep design worth nothing. The measurement has not been taken.

        Rather than guess it, the board is made not to care: a P-channel high-side switch lets
        the firmware cut the module's rail entirely. If the idle draw turns out to be small the
        switch costs three parts and one GPIO; if it is 20 mA the switch is the difference
        between days and months on a cell. Either way the answer no longer has to be known
        BEFORE fabrication, which is the only reason it was blocking anything.

        The gate pull-up is the part that matters and the part that is easy to get wrong. A GPIO
        goes high-impedance during deep sleep and for the ~300 ms between reset and firmware —
        precisely when the module must be off. `Mp3GateHold` holds the gate at the source
        potential through both, so the default state is OFF and the firmware has to ask for
        sound. Same reasoning as the 10k pulldowns on the motor driver, for the same reason.

        Consequence worth knowing: the module re-initialises each time it is powered, so the
        first chirp after a wake is later than the lid. `Silent` remains a supported profile. */}
    <mosfet name="Mp3Switch" channelType="p" mosfetMode="enhancement"
      footprint="sot23" pcbX={38} pcbY={-24}
      connections={{ source: "net.V33", drain: "net.MP3_V33", gate: ".Mp3GateHold > .pin1" }} />
    <resistor name="Mp3GateHold" resistance="100k" footprint="0603" pcbX={32} pcbY={-24} />

    {/* Mounting holes. The board had NONE of its own — the only four holes in it belonged to
        the FireBeetle's footprint, sat underneath the module where no screwdriver reaches, and
        have since been removed. A PCB carrying a motor, in a lid that slams a few thousand times
        a year, held in by tape is a board that eventually hangs off its own 6 V cable.

        M3 clearance (3.2 mm), 4 mm in from each corner. The outline grew from 50 to 62 mm to
        make room, and that is its own finding: the module alone is 60 mm long and runs the whole
        left half of the board, so at 50 mm there was no corner a hole could go in without
        landing under it. */}
    <hole pcbX={-46} pcbY={27} diameter="3.2mm" />
    <hole pcbX={46} pcbY={27} diameter="3.2mm" />
    <hole pcbX={-46} pcbY={-27} diameter="3.2mm" />
    <hole pcbX={46} pcbY={-27} diameter="3.2mm" />

    {/* The two pins that must wake the chip from deep sleep, pulled up in hardware.

        The firmware also enables the internal pull-ups, and on an ESP32-S3 those MAY survive
        deep sleep — the pad is handed to the RTC mux and latched. "May" is the problem: it
        depends on RTC power-domain behaviour this project has not tested, there is an open
        MicroPython issue about pins stuck after a low-level wake (#17334), and the failure mode
        is a bin that wakes spontaneously all night or never wakes again. 100k costs 33 uA only
        while a button is actually held, which is never during sleep, so it is free in the power
        budget and removes the question entirely. It cannot be added after fabrication. */}
    <resistor name="TofIntPullup" resistance="100k" footprint="0603" pcbX={-21} pcbY={4} />
    <resistor name="BtnOpenPullup" resistance="100k" footprint="0603" pcbX={-17} pcbY={4} />

    {/* I2C has no push-pull high side: without these the bus never leaves logic 0 and no device
        answers. DESIGN_RULES.md has required them since it was written; the board did not have
        them. The rule and the board disagreed and nothing compared the two.

        2.2k, not the usual 4.7k, because the firmware runs this bus at 400 kHz
        (config.I2C_FREQ_HZ) and the sensor is on a ribbon. Rise time to V_IH is about
        1.2*R*C, and fast mode allows 300 ns: at a realistic 100 pF, 4.7k gives 566 ns — nearly
        double the limit — while 2.2k gives 265 ns. The ceiling for 300 ns at 100 pF is 2.5k.

        The cost is sink current, and there is room: 3.3 V / 2.2k = 1.5 mA against I2C's 3 mA
        limit, so even in parallel with a breakout's own 10k this stays inside spec.

        The chip's internal pull-ups cannot do this job: 45 kohm nominal is 5.4 us at 100 pF, and
        it is a process-dependent nominal rather than a specified design value, so no rise time
        can be budgeted against it. Buttons are a different matter — those DO use the internal
        pull-ups, and carry no external parts at all. */}
    <resistor name="SdaPullup" resistance="2.2k" footprint="0603" pcbX={-47} pcbY={10} />
    <resistor name="SclPullup" resistance="2.2k" footprint="0603" pcbX={-43} pcbY={10} />
    {/* Across the motor terminals, AT the connector the motor cable enters by — brush arcing is
        what upsets I2C, and a suppression cap 88 mm from the brushes (which is where this was)
        suppresses nothing and turns its own traces into an antenna across the whole board.

        MotorOut used to sit between the driver and this connector. It was a pure pass-through:
        a flying lead crossed the board to reach it, and it then routed 11 mm to BinConnector.
        Deleting it removes a connector, a hand-made lead, and a second jst_ph_2 that was
        mechanically mateable with the speaker's 8 mm away. */}
    <capacitor name="MotorBrushCap" capacitance="100nF" maxVoltageRating="50V" footprint="0603" pcbX={-29} pcbY={22} />

    {/* ---- power ----------------------------------------------------------------------

        The motor loop is 1 mm, not the 0.15 mm default everything else got. 0.15 mm of 1 oz
        copper carries about 0.6 A at a 10 C rise; 1 mm carries about 2.3 A. The motor's real
        stall current has never been measured, but it does not need to be to size this: the
        L9110S cannot pass more than its own limit, so copper sized for the DRIVER's maximum is
        sufficient whatever the motor turns out to want. The measurement decides whether the
        DRIVER is right, not whether the trace is. */}
    <trace from=".BinConnector > .BATP" to="net.MOTOR6V" thickness="1mm" />
    <trace from=".MotorDriver > .VCC" to="net.MOTOR6V" thickness="1mm" />
    <trace from=".MotorBulkCap > .pin1" to="net.MOTOR6V" thickness="1mm" />
    <trace from=".DecoupMotor > .pin1" to="net.MOTOR6V" thickness="1mm" />
    <trace from=".BinConnector > .BATN" to="net.GND" thickness="1mm" />
    <trace from=".MotorBulkCap > .pin2" to="net.GND" thickness="1mm" />
    <trace from=".DecoupMotor > .pin2" to="net.GND" thickness="1mm" />
    {/* All THREE of the module's ground pads, not just one. DFRobot's schematic V1.3 shows P4
        pins 14, 15 and 16 tied together; the first reading of their board render called two of
        them "NC". Wiring one would put the motor return, the audio return and the logic return
        through a single 1 mm pin. */}
    <trace from={`.Mcu > .${MCU.GND}`} to="net.GND" />
    <trace from=".Mcu > .GND2" to="net.GND" />
    <trace from=".Mcu > .GND3" to="net.GND" />
    <trace from={`.Mcu > .${MCU.V33}`} to="net.V33" />
    <trace from=".Mp3Player > .VCC" to="net.MP3_V33" />
    <trace from=".Mp3Player > .GND" to="net.GND" />
    <trace from=".Mp3ReservoirCap > .pin1" to="net.MP3_V33" />
    <trace from=".Mp3ReservoirCap > .pin2" to="net.GND" />
    <trace from=".DecoupMp3 > .pin1" to="net.MP3_V33" />
    {/* Gate held at the source rail, so the switch is OFF whenever the GPIO is not driving it —
        through deep sleep, through reset, through a reflash. */}
    <trace from=".Mp3GateHold > .pin2" to="net.V33" />
    <trace from={`.Mcu > .${MCU.MP3_ENABLE}`} to=".Mp3GateHold > .pin1" />
    <trace from=".DecoupMp3 > .pin2" to="net.GND" />

    {/* ---- motor ---------------------------------------------------------------------- */}
    <trace from={`.Mcu > .${MCU.MOTOR_IA}`} to=".MotorDriver > .AIA" />
    <trace from={`.Mcu > .${MCU.MOTOR_IB}`} to=".MotorDriver > .AIB" />
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
    <trace from={`.Mcu > .${MCU.MOTOR_SENSE}`} to="net.SENSE_ADC" />
    <trace from=".SenseFilterCap > .pin1" to="net.SENSE_ADC" />
    <trace from=".SenseFilterCap > .pin2" to="net.GND" />
    <trace from=".MotorBrushCap > .pin1" to=".BinConnector > .MOTA" thickness="1mm" />
    <trace from=".MotorBrushCap > .pin2" to=".BinConnector > .MOTB" thickness="1mm" />

    {/* ---- sensor (I2C + interrupt) --------------------------------------------------- */}
    <trace from=".SensorHeader > .VIN" to="net.V33" />
    <trace from=".SensorHeader > .GND" to="net.GND" />
    {/* Through named nets rather than pin-to-pin, because the pull-ups are a third member of
        each. A resistor wired straight to a chip pin is the trace that trips tscircuit's
        unsatisfiable 1 mm rule and makes the autorouter skip the whole board. */}
    <trace from={`.Mcu > .${MCU.SDA}`} to="net.SDA" />
    <trace from=".SensorHeader > .SDA" to="net.SDA" />
    <trace from=".SdaPullup > .pin1" to="net.SDA" />
    <trace from=".SdaPullup > .pin2" to="net.V33" />
    <trace from={`.Mcu > .${MCU.SCL}`} to="net.SCL" />
    <trace from=".SensorHeader > .SCL" to="net.SCL" />
    <trace from=".SclPullup > .pin1" to="net.SCL" />
    <trace from=".SclPullup > .pin2" to="net.V33" />
    <trace from={`.Mcu > .${MCU.TOF_INT}`} to=".SensorHeader > .INT" />
    <trace from=".TofIntPullup > .pin1" to=".SensorHeader > .INT" />
    <trace from=".TofIntPullup > .pin2" to="net.V33" />
    <trace from=".DecoupSensor > .pin1" to="net.V33" />
    <trace from=".DecoupSensor > .pin2" to="net.GND" />

    {/* ---- audio ---------------------------------------------------------------------- */}
    {/* Only TX: the module's TXD stays unwired, on purpose. */}
    <trace from={`.Mcu > .${MCU.MP3_TX}`} to=".Mp3Player > .RXD" />
    <trace from=".Mp3Player > .SPKP" to=".Speaker > .P" />
    <trace from=".Mp3Player > .SPKN" to=".Speaker > .N" />

    {/* ---- buttons and status --------------------------------------------------------- */}
    <trace from=".BtnOpen > .A" to={`.Mcu > .${MCU.BTN_OPEN}`} />
    <trace from=".BtnOpenPullup > .pin1" to=".BtnOpen > .A" />
    <trace from=".BtnOpenPullup > .pin2" to="net.V33" />
    <trace from=".BtnOpen > .B" to="net.GND" />
    <trace from=".BtnMode > .A" to={`.Mcu > .${MCU.BTN_MODE}`} />
    <trace from=".BtnMode > .B" to="net.GND" />
    <trace from={`.Mcu > .${MCU.LED_RED}`} to=".RedResistor > .pin1" />
    <trace from=".RedResistor > .pin2" to=".StatusLed > .RED" />
    <trace from={`.Mcu > .${MCU.LED_GREEN}`} to=".GreenResistor > .pin1" />
    <trace from=".GreenResistor > .pin2" to=".StatusLed > .GREEN" />
    <trace from=".StatusLed > .CATHODE" to="net.GND" />
  </board>
)
