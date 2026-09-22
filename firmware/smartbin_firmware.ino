/**
 * Smart Bin — ESP32 brain-transplant firmware
 * Board: Seeed XIAO ESP32-C6 (Arduino core)
 *
 * Behaviour (v1, timed):
 *   - Wave a hand near the IR sensor  -> open the lid, chirp, show status
 *   - Lid stays open for a hold time  -> then closes automatically
 *   - OPEN button  = manual open
 *   - MODE  button = cycle sound/behaviour modes
 *
 * The lid is driven by a TB6612 H-bridge; closing is TIMED with a hard safety
 * cap so a blocked lid can never burn the motor. Motor-current ("stall") sensing
 * is intentionally left as a v2 hook (see closeLid / MOTOR_MAX_RUN_MS).
 *
 * Pin map = the smart-bin board (board.tsx), XIAO ESP32-C6 D-pins:
 *   D0  MotorIn1 (TB6612 AIN1)      D6  Open button
 *   D1  MotorIn2 (TB6612 AIN2)      D7  Mode button
 *   D3  MotorPwm (TB6612 PWMA)      D9  MP3 TX  -> module RXD
 *   D2  IR sensor OUT               D10 MP3 RX  <- module TXD
 *   D4  I2C SDA (OLED)              D5  I2C SCL (OLED)
 * TB6612 STBY is tied to 3V3 in hardware (always enabled).
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ----------------------------- Pin assignments -----------------------------
constexpr uint8_t PIN_MOTOR_IN1   = D0;   // TB6612 AIN1 (direction A)
constexpr uint8_t PIN_MOTOR_IN2   = D1;   // TB6612 AIN2 (direction B)
constexpr uint8_t PIN_MOTOR_PWM   = D3;   // TB6612 PWMA (speed)
constexpr uint8_t PIN_IR_SENSOR   = D2;   // IR module digital OUT
constexpr uint8_t PIN_BUTTON_OPEN = D6;
constexpr uint8_t PIN_BUTTON_MODE = D7;
constexpr uint8_t PIN_MP3_TX      = D9;   // XIAO -> module RXD
constexpr uint8_t PIN_MP3_RX      = D10;  // XIAO <- module TXD
// I2C uses the XIAO default Wire pins: D4 = SDA, D5 = SCL.

// ----------------------------- Tunable behaviour ---------------------------
constexpr uint8_t  MOTOR_OPEN_SPEED   = 220;   // PWM 0-255 while opening
constexpr uint8_t  MOTOR_CLOSE_SPEED  = 200;   // PWM 0-255 while closing
constexpr uint16_t LID_OPEN_RUN_MS    = 900;   // time to drive the lid open  (CALIBRATE)
constexpr uint16_t LID_CLOSE_RUN_MS   = 950;   // time to drive the lid closed (CALIBRATE)
constexpr uint16_t LID_OPEN_HOLD_MS   = 4000;  // how long the lid stays open
constexpr uint16_t MOTOR_MAX_RUN_MS   = 1500;  // SAFETY: never drive the motor longer than this
constexpr uint16_t IR_RETRIGGER_MS    = 1500;  // ignore the IR for a moment after acting
constexpr bool     IR_ACTIVE_LOW      = true;  // many IR modules pull OUT LOW when something is near
constexpr uint16_t BUTTON_DEBOUNCE_MS = 40;

// ----------------------------- OLED display --------------------------------
constexpr uint8_t OLED_WIDTH   = 128;
constexpr uint8_t OLED_HEIGHT  = 64;
constexpr uint8_t OLED_I2C_ADDR = 0x3C;
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, /*reset=*/-1);

// ----------------------------- MP3 (DFRobot DFR0534, UART) ------------------
HardwareSerial Mp3Serial(1);
constexpr uint32_t MP3_BAUD        = 9600;
constexpr uint8_t  MP3_VOLUME      = 22;   // 0-30
constexpr uint16_t MP3_TRACK_OPEN  = 1;    // clip to play when the lid opens
constexpr uint16_t MP3_TRACK_CLOSE = 2;    // clip to play when the lid closes

// ----------------------------- Lid state machine ---------------------------
enum class LidState { Idle, Opening, Open, Closing };
LidState  lidState       = LidState::Idle;
uint32_t  stateEnteredMs = 0;
uint32_t  lastActionMs   = 0;

// =============================== Motor control =============================

/** Coast the lid motor (both inputs low). */
void motorStop() {
  digitalWrite(PIN_MOTOR_IN1, LOW);
  digitalWrite(PIN_MOTOR_IN2, LOW);
  analogWrite(PIN_MOTOR_PWM, 0);
}

/** Drive the lid motor. openDirection=true opens, false closes. */
void motorDrive(bool openDirection, uint8_t speed) {
  digitalWrite(PIN_MOTOR_IN1, openDirection ? HIGH : LOW);
  digitalWrite(PIN_MOTOR_IN2, openDirection ? LOW  : HIGH);
  analogWrite(PIN_MOTOR_PWM, speed);
}

// =============================== Sensors / input ===========================

/** True when the IR module reports something in front of it. */
bool handDetected() {
  const int raw = digitalRead(PIN_IR_SENSOR);
  return IR_ACTIVE_LOW ? (raw == LOW) : (raw == HIGH);
}

/** Debounced "button is pressed" (buttons wire the pin to GND, using INPUT_PULLUP). */
bool buttonPressed(uint8_t pin) {
  if (digitalRead(pin) != LOW) return false;
  delay(BUTTON_DEBOUNCE_MS);
  return digitalRead(pin) == LOW;
}

// =============================== MP3 module =================================

/**
 * Send one command frame to the DFR0534: 0xAA, CMD, LEN, DATA..., SUM.
 * SUM is the low byte of the sum of every preceding byte.
 * NOTE: verify the exact command bytes against the DFR0534 datasheet
 * (parts/datasheets on your Mac) — they vary slightly by firmware revision.
 */
void mp3SendCommand(uint8_t command, const uint8_t *data, uint8_t length) {
  uint8_t frame[16];
  uint8_t i = 0;
  frame[i++] = 0xAA;
  frame[i++] = command;
  frame[i++] = length;
  for (uint8_t d = 0; d < length; d++) frame[i++] = data[d];
  uint16_t sum = 0;
  for (uint8_t s = 0; s < i; s++) sum += frame[s];
  frame[i++] = static_cast<uint8_t>(sum & 0xFF);
  Mp3Serial.write(frame, i);
}

void mp3SetVolume(uint8_t volume) {
  const uint8_t data[1] = { volume };
  mp3SendCommand(0x13, data, 1);           // 0x13 = set volume
}

void mp3PlayTrack(uint16_t track) {
  const uint8_t data[2] = { static_cast<uint8_t>(track >> 8),
                            static_cast<uint8_t>(track & 0xFF) };
  mp3SendCommand(0x07, data, 2);           // 0x07 = play track by index
}

// =============================== OLED status ===============================

void showStatus(const char *title, const char *detail) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 4);
  display.println(title);
  display.setTextSize(1);
  display.setCursor(0, 40);
  display.println(detail);
  display.display();
}

// =============================== State helpers =============================

void enterState(LidState next) {
  lidState = next;
  stateEnteredMs = millis();
}

uint32_t timeInState() { return millis() - stateEnteredMs; }

// =============================== Arduino setup =============================

void setup() {
  pinMode(PIN_MOTOR_IN1, OUTPUT);
  pinMode(PIN_MOTOR_IN2, OUTPUT);
  pinMode(PIN_MOTOR_PWM, OUTPUT);
  pinMode(PIN_IR_SENSOR, INPUT);
  pinMode(PIN_BUTTON_OPEN, INPUT_PULLUP);
  pinMode(PIN_BUTTON_MODE, INPUT_PULLUP);
  motorStop();

  Wire.begin();                              // D4 SDA / D5 SCL
  display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR);

  Mp3Serial.begin(MP3_BAUD, SERIAL_8N1, PIN_MP3_RX, PIN_MP3_TX);
  delay(200);
  mp3SetVolume(MP3_VOLUME);

  showStatus("Ready", "wave to open");
}

// =============================== Main loop ================================

void loop() {
  const bool openRequested =
      (lidState == LidState::Idle) &&
      (millis() - lastActionMs > IR_RETRIGGER_MS) &&
      (handDetected() || buttonPressed(PIN_BUTTON_OPEN));

  switch (lidState) {
    case LidState::Idle:
      if (openRequested) {
        motorDrive(/*openDirection=*/true, MOTOR_OPEN_SPEED);
        mp3PlayTrack(MP3_TRACK_OPEN);
        showStatus("Opening", "");
        enterState(LidState::Opening);
      }
      break;

    case LidState::Opening:
      // stop when the calibrated time elapses OR the safety cap trips
      if (timeInState() >= LID_OPEN_RUN_MS || timeInState() >= MOTOR_MAX_RUN_MS) {
        motorStop();
        showStatus("Open", "");
        enterState(LidState::Open);
      }
      break;

    case LidState::Open:
      if (timeInState() >= LID_OPEN_HOLD_MS) {
        motorDrive(/*openDirection=*/false, MOTOR_CLOSE_SPEED);
        mp3PlayTrack(MP3_TRACK_CLOSE);
        showStatus("Closing", "");
        enterState(LidState::Closing);
      }
      break;

    case LidState::Closing:
      // v2 hook: replace the timer with a motor-current/stall check here.
      if (timeInState() >= LID_CLOSE_RUN_MS || timeInState() >= MOTOR_MAX_RUN_MS) {
        motorStop();
        lastActionMs = millis();
        showStatus("Ready", "wave to open");
        enterState(LidState::Idle);
      }
      break;
  }
}
