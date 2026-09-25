import { type ChipProps } from "tscircuit"

/**
 * DFRobot DFR0954 — MAX98357A I2S class-D amplifier breakout.
 *
 * WHY THIS IS HAND-PLACED RATHER THAN A FOOTPRINTER STRING
 *
 * The module has **no pad-1 marker** — no square pad, no dot, nothing. DFRobot model it as two
 * separate 6-way connectors: P1 is the top row numbered RIGHT-TO-LEFT, P2 the bottom row
 * LEFT-TO-RIGHT, so the concatenation runs counter-clockwise from the top right. Any footprinter
 * string would impose its own numbering convention on top of that, and the two would agree only
 * by luck.
 *
 * Every pad here is therefore named for the label printed beside it, and positioned from the
 * dimension drawing. Nothing downstream has to know a pad number.
 *
 * THE ONE THAT WOULD HAVE BEEN WRONG: **SPK+ and SPK- are not an adjacent pair.** SPK+ is the
 * rightmost pad of the TOP row and SPK- the rightmost of the BOTTOM row — directly across from
 * each other, 15.24 mm apart. A footprint drawn as though they neighboured would wire the
 * speaker across SPK+ and DIN.
 *
 * Geometry: 12 castellated pads, two rows of six at 2.54 mm, rows 15.24 mm apart, 18 x 18 mm
 * body, no mounting holes. Source: DFRobot's DFR0954 dimension drawing (1.0) and their DXF, via
 * the spark part record `max98357a-dfr0954.json`.
 *
 * Holes are 1.0 mm, not the castellation's own size: the module plugs in on a 2.54 mm header, so
 * what goes through this board is a 0.64 mm square pin — 0.905 mm across the diagonal, and
 * plating grows inward.
 */
export const Dfr0954I2sAmp = (props: ChipProps) => (
  <chip
    footprint={<footprint>
      {/* Top row, left to right. */}
      <platedhole portHints={["VCC1"]} pcbX="-6.35mm" pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["GND1"]} pcbX="-3.81mm" pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["LRC"]}  pcbX="-1.27mm" pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["BCLK"]} pcbX="1.27mm"  pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["DIN"]}  pcbX="3.81mm"  pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["SPKP"]} pcbX="6.35mm"  pcbY="7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />

      {/* Bottom row, left to right. SPKN sits directly below SPKP, not beside it. */}
      <platedhole portHints={["GAIN"]} pcbX="-6.35mm" pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["SD"]}   pcbX="-3.81mm" pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["NC"]}   pcbX="-1.27mm" pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["GND2"]} pcbX="1.27mm"  pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["VCC2"]} pcbX="3.81mm"  pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
      <platedhole portHints={["SPKN"]} pcbX="6.35mm"  pcbY="-7.62mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />

      {/* 18 x 18 mm body. */}
      <silkscreenpath route={[{"x":-9,"y":9},{"x":9,"y":9}]} />
      <silkscreenpath route={[{"x":9,"y":9},{"x":9,"y":-9}]} />
      <silkscreenpath route={[{"x":9,"y":-9},{"x":-9,"y":-9}]} />
      <silkscreenpath route={[{"x":-9,"y":-9},{"x":-9,"y":9}]} />
    </footprint>}
    {...props}
  />
)
