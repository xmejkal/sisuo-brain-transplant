import { type ChipProps } from "tscircuit"
export const FireBeetle2Esp32S3 = (props: ChipProps) => (
  <chip
    footprint={<footprint>
        <platedhole  portHints={["RX"]} pcbX="-11.43mm" pcbY="24.8mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["TX"]} pcbX="-11.43mm" pcbY="22.26mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D2"]} pcbX="-11.43mm" pcbY="19.72mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D3"]} pcbX="-11.43mm" pcbY="17.18mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D5"]} pcbX="-11.43mm" pcbY="14.64mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D6"]} pcbX="-11.43mm" pcbY="12.1mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D7"]} pcbX="-11.43mm" pcbY="9.56mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D9"]} pcbX="-11.43mm" pcbY="7.02mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["SDA"]} pcbX="-11.43mm" pcbY="4.48mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["SCL"]} pcbX="-11.43mm" pcbY="1.94mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["MI"]} pcbX="-11.43mm" pcbY="-0.6mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["MO"]} pcbX="-11.43mm" pcbY="-3.14mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["SCK"]} pcbX="-11.43mm" pcbY="-5.68mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["GND1"]} pcbX="-11.43mm" pcbY="-8.22mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["GND2"]} pcbX="-11.43mm" pcbY="-10.76mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["GND3"]} pcbX="-11.43mm" pcbY="-13.3mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["3V3"]} pcbX="-11.43mm" pcbY="-15.84mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["RST"]} pcbX="-11.43mm" pcbY="-18.38mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D10"]} pcbX="11.43mm" pcbY="24.8mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D11"]} pcbX="11.43mm" pcbY="22.26mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D12"]} pcbX="11.43mm" pcbY="19.72mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D13"]} pcbX="11.43mm" pcbY="17.18mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A0"]} pcbX="11.43mm" pcbY="14.64mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A1"]} pcbX="11.43mm" pcbY="12.1mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A2"]} pcbX="11.43mm" pcbY="9.56mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A3"]} pcbX="11.43mm" pcbY="7.02mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A4"]} pcbX="11.43mm" pcbY="4.48mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["A5"]} pcbX="11.43mm" pcbY="1.94mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D14"]} pcbX="11.43mm" pcbY="-0.6mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D-"]} pcbX="11.43mm" pcbY="-3.14mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["D+"]} pcbX="11.43mm" pcbY="-5.68mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<platedhole  portHints={["VCC"]} pcbX="11.43mm" pcbY="-8.22mm" outerDiameter="1.7mm" holeDiameter="1mm" shape="circle" />
<silkscreenpath route={[{"x":-12.7,"y":30},{"x":12.7,"y":30}]} />
<silkscreenpath route={[{"x":12.7,"y":30},{"x":12.7,"y":-30}]} />
<silkscreenpath route={[{"x":12.7,"y":-30},{"x":-12.7,"y":-30}]} />
<silkscreenpath route={[{"x":-12.7,"y":-30},{"x":-12.7,"y":30}]} />
<fabricationnotetext pcbX={0} pcbY={-27} anchorAlignment="center" text="FireBeetle2Esp32S3" font="tscircuit2024" fontSize={1} />
<silkscreentext pcbX={0} pcbY={32} anchorAlignment="center" fontSize={1} font="tscircuit2024" layer="top" text="U1" />
<silkscreentext pcbX={0} pcbY={-24} anchorAlignment="center" fontSize={1.2} font="tscircuit2024" layer="top" text="USB" />
<courtyardoutline outline={[{"x":-12.7,"y":30},{"x":12.7,"y":30}]} layer="top" />
<courtyardoutline outline={[{"x":12.7,"y":30},{"x":12.7,"y":-30}]} layer="top" />
<courtyardoutline outline={[{"x":12.7,"y":-30},{"x":-12.7,"y":-30}]} layer="top" />
<courtyardoutline outline={[{"x":-12.7,"y":-30},{"x":-12.7,"y":30}]} layer="top" />
      </footprint>}
    {...props}
  />
)