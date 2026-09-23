// A VL6180X time-of-flight sensor for the Wokwi simulator.
//
// Wokwi has no ToF sensor, and the bin's whole "wave to open" behaviour depends on one, so this
// stands in for it: an I2C device at 0x29 that answers the registers the driver actually reads,
// with the measured distance coming from a slider you can drag while the simulation runs.
//
// It is a model of the conversation, not of the chip. It knows the handful of registers
// smartbin/vl6180x.py touches and stores anything else written to it, which is enough for the
// firmware to initialise, range, and run in continuous mode.
//
// It models the unhappy paths too, because those are the ones firmware gets wrong:
//   * `status` sets RESULT__RANGE_STATUS, so a simulation can produce the "no target in view"
//     error an empty room reports every time — the reading that once faulted the bin;
//   * `unplugged` makes the device stop acknowledging, which is a cable falling out;
//   * the interrupt **latches** until the firmware clears it, as the real one does, so code
//     that forgets to clear it misbehaves here as it would on a bench.
//
// Register addresses are 16-bit, which is why the write path collects two address bytes before
// it starts reading or writing data.

#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define I2C_ADDRESS 0x29

// The registers the driver reads. Everything else is stored and echoed back.
#define REG_IDENTIFICATION_MODEL_ID 0x000
#define REG_SYSTEM_FRESH_OUT_OF_RESET 0x016
#define REG_SYSTEM_INTERRUPT_CLEAR 0x015
#define REG_SYSRANGE_START 0x018
#define REG_SYSRANGE_INTERMEASUREMENT_PERIOD 0x01B
#define REG_SYSRANGE_THRESH_LOW 0x01A
#define REG_RESULT_RANGE_STATUS 0x04D
#define REG_RESULT_INTERRUPT_STATUS_GPIO 0x04F
#define REG_RESULT_RANGE_VAL 0x062
#define REG_RESULT_RANGE_RETURN_RATE 0x066

#define MODEL_ID 0xB4
#define SAMPLE_READY 0x04          // RESULT__INTERRUPT_STATUS_GPIO: a new sample is waiting
#define RANGE_STATUS_OK 0x00
#define STORED_REGISTERS 0x100     // low registers only; the tuning block above this is ignored

typedef struct {
  pin_t pin_int;
  timer_t ranging_timer;
  uint32_t distance_control;
  uint32_t status_control;
  uint32_t unplugged_control;
  bool interrupt_latched;

  uint16_t address;                // the 16-bit register address being addressed
  uint8_t address_bytes_seen;      // 0, 1 or 2 bytes of it received so far
  uint8_t fresh_out_of_reset;
  bool interrupt_asserted;
  uint8_t registers[STORED_REGISTERS];
} chip_state_t;

static void on_ranging_tick(void *user_data);
static bool on_i2c_connect(void *user_data, uint32_t address, bool read);
static void update_interrupt(chip_state_t *chip);
static uint8_t on_i2c_read(void *user_data);
static bool on_i2c_write(void *user_data, uint8_t data);
static void on_i2c_disconnect(void *user_data);

void chip_init(void) {
  chip_state_t *chip = calloc(1, sizeof(chip_state_t));
  chip->pin_int = pin_init("INT", OUTPUT_LOW);
  chip->distance_control = attr_init("distance", 200);
  chip->status_control = attr_init("status", 0);
  chip->unplugged_control = attr_init("unplugged", 0);
  chip->fresh_out_of_reset = 1;    // a freshly powered sensor, so the driver loads its tuning

  // The real sensor ranges on its own clock once continuous mode is started, and keeps its
  // interrupt pin up to date whether or not anyone is talking to it. That is the entire point
  // of it: the host can sleep. Updating the pin only during I2C traffic — as this chip first
  // did — makes a sleeping host unwakeable, which is a simulation that lies.
  const timer_config_t ranging_timer = {
    .callback = on_ranging_tick,
    .user_data = chip,
  };
  chip->ranging_timer = timer_init(&ranging_timer);

  const i2c_config_t i2c_config = {
    .user_data = chip,
    .address = I2C_ADDRESS,
    .scl = pin_init("SCL", INPUT),
    .sda = pin_init("SDA", INPUT),
    .connect = on_i2c_connect,
    .read = on_i2c_read,
    .write = on_i2c_write,
    .disconnect = on_i2c_disconnect,
  };
  i2c_init(&i2c_config);

  printf("VL6180X: ready at 0x%02X\n", I2C_ADDRESS);
}

static uint8_t measured_distance(chip_state_t *chip) {
  uint32_t millimetres = attr_read(chip->distance_control);
  return millimetres > 255 ? 255 : (uint8_t)millimetres;
}

static uint8_t read_register(chip_state_t *chip, uint16_t address) {
  switch (address) {
    case REG_IDENTIFICATION_MODEL_ID:
      return MODEL_ID;
    case REG_SYSTEM_FRESH_OUT_OF_RESET:
      return chip->fresh_out_of_reset;
    case REG_RESULT_INTERRUPT_STATUS_GPIO:
      return SAMPLE_READY;
    case REG_RESULT_RANGE_STATUS:
      // The real chip reports the error in the high nibble. 7 is "could not converge", which is
      // what an empty field of view gives, every time.
      return (uint8_t)(attr_read(chip->status_control) << 4);
    case REG_RESULT_RANGE_VAL:
      return measured_distance(chip);
    case REG_RESULT_RANGE_RETURN_RATE:
      return 0x10;
    default:
      return address < STORED_REGISTERS ? chip->registers[address] : 0;
  }
}

static void write_register(chip_state_t *chip, uint16_t address, uint8_t value) {
  if (address == REG_SYSTEM_FRESH_OUT_OF_RESET) {
    chip->fresh_out_of_reset = value;
  }
  if (address == REG_SYSTEM_INTERRUPT_CLEAR) {
    chip->interrupt_latched = false;
  }
  if (address < STORED_REGISTERS) {
    chip->registers[address] = value;
  }

  // Starting or stopping continuous ranging starts or stops our own clock with it.
  if (address == REG_SYSRANGE_START) {
    if (value & 0x02) {
      uint32_t period_ms = (chip->registers[REG_SYSRANGE_INTERMEASUREMENT_PERIOD] + 1) * 10;
      timer_start(chip->ranging_timer, period_ms * 1000, true);
      printf("VL6180X: ranging every %u ms\n", period_ms);
    } else {
      timer_stop(chip->ranging_timer);
    }
  }
}

/** One measurement on the sensor's own clock, with the interrupt pin following the result. */
static void on_ranging_tick(void *user_data) {
  update_interrupt((chip_state_t *)user_data);
}

// The interrupt pin asserts while something is closer than the threshold the firmware set, which
// is what lets the simulated bin wake on a hand rather than only on a button.
static void update_interrupt(chip_state_t *chip) {
  uint8_t threshold = chip->registers[REG_SYSRANGE_THRESH_LOW];
  bool continuous = (chip->registers[REG_SYSRANGE_START] & 0x02) != 0;
  bool something_near = threshold > 0 && measured_distance(chip) < threshold;

  // The interrupt latches: once something has been seen, the pin stays asserted until the
  // firmware writes to SYSTEM__INTERRUPT_CLEAR. Firmware that forgets will find the bin waking
  // itself forever, here as on a bench.
  if (continuous && something_near) {
    chip->interrupt_latched = true;
  }
  bool assert_interrupt = chip->interrupt_latched;

  if (assert_interrupt != chip->interrupt_asserted) {
    chip->interrupt_asserted = assert_interrupt;
    printf("VL6180X: %u mm, threshold %u, INT -> %s\n", measured_distance(chip), threshold,
           assert_interrupt ? "HIGH" : "LOW");
  }
  pin_write(chip->pin_int, assert_interrupt ? HIGH : LOW);
}

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = (chip_state_t *)user_data;

  // An unplugged device does not acknowledge, which is what the host sees as a bus error.
  if (attr_read(chip->unplugged_control)) {
    return false;
  }

  if (!read) {
    chip->address_bytes_seen = 0;  // a write always begins with the register address
  }
  return true;
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = (chip_state_t *)user_data;

  if (chip->address_bytes_seen == 0) {
    chip->address = (uint16_t)data << 8;
    chip->address_bytes_seen = 1;
  } else if (chip->address_bytes_seen == 1) {
    chip->address |= data;
    chip->address_bytes_seen = 2;
  } else {
    write_register(chip, chip->address, data);
    chip->address++;               // consecutive writes walk forward, as the real chip does
    update_interrupt(chip);
  }
  return true;                     // ack
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  uint8_t value = read_register(chip, chip->address);
  chip->address++;
  update_interrupt(chip);
  return value;
}

static void on_i2c_disconnect(void *user_data) {
  // Nothing to do: the address survives so a repeated start can read what was just addressed.
}
