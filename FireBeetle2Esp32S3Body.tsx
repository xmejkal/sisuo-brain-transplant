/**
 * The FireBeetle 2 ESP32-S3's 3D body, for the board render.
 *
 * Hand-built rather than DFRobot's STEP, for three reasons: their model is 25 MB, it is served
 * inside a RAR inside a ZIP rather than at a URL tscircuit could fetch, and its bounding box is
 * 28.7 x 68.2 mm against the board's 25.4 x 60 because it includes an OV2640 camera and its
 * flex cable hanging off the edge — which would render a board we are not using and trip
 * tools/check-module-clearance.py.
 *
 * Every dimension below is the real one. The footprint it sits on comes from
 * tools/generate-firebeetle-footprint.py, which lists the sources.
 *
 * This is a separate module because `tsci convert` regenerates FireBeetle2Esp32S3.tsx from the
 * .kicad_mod and would throw away anything added there.
 */

// The module's real dimensions — see tools/generate-firebeetle-footprint.py for the sources.
const PCB_LENGTH_MM = 60
const PCB_WIDTH_MM = 25.4
const PCB_THICKNESS_MM = 1.6
const PCB_CORNER_RADIUS_MM = 1.5

// ESP32-S3-WROOM-1, from Espressif's module datasheet. It sits flush with the end away from the
// USB-C connector, which on this footprint is -Y.
const WROOM_WIDTH_MM = 18.0
const WROOM_LENGTH_MM = 25.5
const WROOM_HEIGHT_MM = 3.1
const WROOM_CENTRE_Y_MM = -PCB_LENGTH_MM / 2 + WROOM_LENGTH_MM / 2

// USB-C receptacle at the +Y end, overhanging the outline slightly as these always do.
const USB_WIDTH_MM = 8.9
const USB_DEPTH_MM = 7.35
const USB_HEIGHT_MM = 3.26
const USB_CENTRE_Y_MM = PCB_LENGTH_MM / 2 - USB_DEPTH_MM / 2 + 1.0

const PCB_COLOUR: [number, number, number] = [0.08, 0.08, 0.09]
const SHIELD_COLOUR: [number, number, number] = [0.76, 0.77, 0.79]
const USB_COLOUR: [number, number, number] = [0.68, 0.69, 0.72]

/**
 * The outline of a rounded rectangle, as points for an extruded polygon.
 *
 * A PCB is rounded in X and Y and flat in Z, which `roundedCuboid` cannot express — it rounds
 * every axis, so a 1.5 mm radius on a 1.6 mm thick board is rejected outright. Extruding the
 * real outline gives the true corner radius and square faces.
 */
const roundedRectanglePoints = (
  width: number, height: number, radius: number, segmentsPerCorner: number,
): [number, number][] => {
  const points: [number, number][] = []
  const insetX = width / 2 - radius
  const insetY = height / 2 - radius
  const corners: [number, number, number][] = [
    [insetX, insetY, 0], [-insetX, insetY, Math.PI / 2],
    [-insetX, -insetY, Math.PI], [insetX, -insetY, (3 * Math.PI) / 2],
  ]
  for (const [centreX, centreY, startAngle] of corners) {
    for (let step = 0; step <= segmentsPerCorner; step++) {
      const angle = startAngle + (step / segmentsPerCorner) * (Math.PI / 2)
      points.push([centreX + radius * Math.cos(angle), centreY + radius * Math.sin(angle)])
    }
  }
  return points
}

const PCB_CORNER_SEGMENTS = 8

export const fireBeetle2Esp32S3Body = {
  jscad: {
    type: "union",
    shapes: [
      {
        type: "colorize",
        color: PCB_COLOUR,
        shape: {
          type: "extrudeLinear",
          options: { height: PCB_THICKNESS_MM },
          shape: {
            type: "polygon",
            points: roundedRectanglePoints(
              PCB_WIDTH_MM, PCB_LENGTH_MM, PCB_CORNER_RADIUS_MM, PCB_CORNER_SEGMENTS,
            ),
          },
        },
      },
      {
        type: "colorize",
        color: SHIELD_COLOUR,
        shape: {
          type: "translate",
          vector: [0, WROOM_CENTRE_Y_MM, PCB_THICKNESS_MM + WROOM_HEIGHT_MM / 2],
          shape: {
            type: "cuboid",
            size: [WROOM_WIDTH_MM, WROOM_LENGTH_MM, WROOM_HEIGHT_MM],
          },
        },
      },
      {
        type: "colorize",
        color: USB_COLOUR,
        shape: {
          type: "translate",
          vector: [0, USB_CENTRE_Y_MM, PCB_THICKNESS_MM + USB_HEIGHT_MM / 2],
          shape: {
            type: "roundedCuboid",
            size: [USB_WIDTH_MM, USB_DEPTH_MM, USB_HEIGHT_MM],
            roundRadius: 0.8,
            segments: 16,
          },
        },
      },
    ],
  },
}
