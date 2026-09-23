import { XiaoRealFootprint } from "./XIAO-ESP32-C6-SMD"
// Smart bin — full board on the confirmed Seeed XIAO ESP32-C6.
export default () => (
  <board width="70mm" height="45mm" autorouter="auto">
    <XiaoRealFootprint name="XIAO" pcbX={-8.9} pcbY={-10.5}
      pinLabels={{ pin1:"MA_IN1",pin2:"MA_IN2",pin3:"IR_RX",pin4:"MA_PWM",pin5:"SDA",pin6:"SCL",pin7:"BTN_OPEN",pin8:"BTN_MODE",pin9:"SPARE",pin10:"MP3_TX",pin11:"MP3_RX",pin12:"V33",pin13:"GND",pin14:"V5" }} />
    <chip name="MotorDriver" footprint="headermodule8" pcbX={-24} pcbY={6}
      pinLabels={{ pin1:"VM",pin2:"VCC",pin3:"STBY",pin4:"AIN1",pin5:"AIN2",pin6:"PWMA",pin7:"AO1",pin8:"AO2" }} />
    <chip name="Mp3Player" footprint="headermodule6" pcbX={24} pcbY={6} pinLabels={{ pin1:"VCC",pin2:"GND",pin3:"RXD",pin4:"TXD",pin5:"SPKP",pin6:"SPKN" }} />
    <chip name="Speaker" footprint="jst_ph_2" pcbX={28} pcbY={15} pinLabels={{ pin1:"P",pin2:"N" }} />
    <chip name="OledDisplay" footprint="pinrow4" pcbX={0} pcbY={17} pinLabels={{ pin1:"VCC",pin2:"GND",pin3:"SDA",pin4:"SCL" }} />
    <chip name="IrSensor" footprint="pinrow3" pcbX={0} pcbY={-17} pinLabels={{ pin1:"VCC",pin2:"GND",pin3:"OUT" }} />
    <chip name="BinConnector" footprint="jst_ph_4" pcbX={-27} pcbY={-6} pinLabels={{ pin1:"BATP",pin2:"BATN",pin3:"MOTA",pin4:"MOTB" }} />
    <chip name="LipoBattery" footprint="jst_ph_2" pcbX={28} pcbY={-6} pinLabels={{ pin1:"POS",pin2:"NEG" }} />
    <chip name="BtnOpen" footprint="pushbutton" pcbX={-13} pcbY={-17} pinLabels={{ pin1:"A",pin4:"B" }} />
    <chip name="BtnMode" footprint="pushbutton" pcbX={13} pcbY={-17} pinLabels={{ pin1:"A",pin4:"B" }} />
    <resistor name="PullupSda" resistance="4.7k" footprint="0603" pcbX={13} pcbY={13} />
    <resistor name="PullupScl" resistance="4.7k" footprint="0603" pcbX={16} pcbY={13} />
    <capacitor name="MotorBulkCap" capacitance="220uF" footprint="0805" pcbX={-19} pcbY={-8} />
    <capacitor name="Mp3ReservoirCap" capacitance="100uF" footprint="0805" pcbX={19} pcbY={-8} />
    <capacitor name="DecoupMotorVm" capacitance="100nF" footprint="0603" pcbX={-17} pcbY={3} />
    <capacitor name="DecoupMotorVcc" capacitance="100nF" footprint="0603" pcbX={-17} pcbY={-1} />
    <capacitor name="DecoupMp3" capacitance="100nF" footprint="0603" pcbX={17} pcbY={3} />
    <capacitor name="DecoupOled" capacitance="100nF" footprint="0603" pcbX={-7} pcbY={14} />
    <capacitor name="DecoupIr" capacitance="100nF" footprint="0603" pcbX={7} pcbY={-13} />
    <trace from=".BinConnector > .BATP" to="net.MOTOR6V" /><trace from=".MotorDriver > .VM" to="net.MOTOR6V" />
    <trace from=".MotorBulkCap > .pin1" to="net.MOTOR6V" /><trace from=".BinConnector > .BATN" to="net.GND" />
    <trace from=".MotorBulkCap > .pin2" to="net.GND" /><trace from=".XIAO > .GND" to="net.GND" /><trace from=".XIAO > .V33" to="net.V33" />
    <trace from=".MotorDriver > .STBY" to=".XIAO > .V33" /><trace from=".MotorDriver > .VCC" to=".XIAO > .V33" />
    <trace from=".LipoBattery > .POS" to="net.VBAT" /><trace from=".LipoBattery > .NEG" to="net.GND" />
    <trace from=".Mp3Player > .VCC" to="net.VBAT" /><trace from=".OledDisplay > .VCC" to=".XIAO > .V33" />
    <trace from=".IrSensor > .VCC" to=".XIAO > .V33" /><trace from=".Mp3Player > .GND" to="net.GND" />
    <trace from=".OledDisplay > .GND" to="net.GND" /><trace from=".IrSensor > .GND" to="net.GND" />
    <trace from=".XIAO > .MA_IN1" to=".MotorDriver > .AIN1" /><trace from=".XIAO > .MA_IN2" to=".MotorDriver > .AIN2" />
    <trace from=".XIAO > .MA_PWM" to=".MotorDriver > .PWMA" /><trace from=".MotorDriver > .AO1" to=".BinConnector > .MOTA" />
    <trace from=".MotorDriver > .AO2" to=".BinConnector > .MOTB" />
    <trace from=".XIAO > .MP3_TX" to=".Mp3Player > .RXD" /><trace from=".XIAO > .MP3_RX" to=".Mp3Player > .TXD" />
    <trace from=".Mp3Player > .SPKP" to=".Speaker > .P" /><trace from=".Mp3Player > .SPKN" to=".Speaker > .N" />
    <trace from=".XIAO > .SDA" to=".OledDisplay > .SDA" /><trace from=".XIAO > .SCL" to=".OledDisplay > .SCL" />
    <trace from=".PullupSda > .pin1" to=".XIAO > .SDA" /><trace from=".PullupSda > .pin2" to=".XIAO > .V33" />
    <trace from=".PullupScl > .pin1" to=".XIAO > .SCL" /><trace from=".PullupScl > .pin2" to=".XIAO > .V33" />
    <trace from=".XIAO > .IR_RX" to=".IrSensor > .OUT" />
    <trace from=".BtnOpen > .A" to=".XIAO > .BTN_OPEN" /><trace from=".BtnOpen > .B" to="net.GND" />
    <trace from=".BtnMode > .A" to=".XIAO > .BTN_MODE" /><trace from=".BtnMode > .B" to="net.GND" />
    <trace from=".DecoupMotorVm > .pin1" to="net.MOTOR6V" /><trace from=".DecoupMotorVm > .pin2" to="net.GND" />
    <trace from=".DecoupMotorVcc > .pin1" to="net.V33" /><trace from=".DecoupMotorVcc > .pin2" to="net.GND" />
    <trace from=".Mp3ReservoirCap > .pin1" to="net.VBAT" /><trace from=".Mp3ReservoirCap > .pin2" to="net.GND" />
    <trace from=".DecoupMp3 > .pin1" to="net.VBAT" /><trace from=".DecoupMp3 > .pin2" to="net.GND" />
    <trace from=".DecoupOled > .pin1" to="net.V33" /><trace from=".DecoupOled > .pin2" to="net.GND" />
    <trace from=".DecoupIr > .pin1" to="net.V33" /><trace from=".DecoupIr > .pin2" to="net.GND" />
  </board>
)
