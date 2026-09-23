// An L9110S motor channel for the Wokwi simulator.
//
// Wokwi has no H-bridge and no DC motor, and watching two LEDs only tells you a pin is high.
// This reads the driver's two inputs and prints what the motor would be doing, which turns the
// motor into something a test can assert on:
//
//     MOTOR: opening
//     MOTOR: stopped
//
// The truth table is the chip's own: IA high with IB low drives one way, the reverse drives the
// other, both low coasts, and both high brakes.
//
// The subtlety is PWM. Speed arrives as a square wave on the driven input, so "both inputs low"
// is true for part of every cycle and a naive reading reports the motor stopping and starting
// thousands of times a second. A real motor does not care — its inertia averages the pulses —
// and neither should this. So a direction is reported immediately, but "stopped" only after the
// inputs have been quiet for longer than a PWM period.

#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>

// Longer than one PWM period at the firmware's 5 kHz (200 us), short enough that a genuine stop
// is reported promptly.
#define QUIET_BEFORE_STOPPED_US 5000

typedef struct {
  pin_t pin_ia;
  pin_t pin_ib;
  pin_t pin_oa;
  pin_t pin_ob;
  timer_t stop_timer;
  const char *reported;   // what we last printed, so nothing is announced twice
} chip_state_t;

static void on_input_change(void *user_data, pin_t pin, uint32_t value);
static void on_quiet(void *user_data);
static void report(chip_state_t *chip, const char *state);
static const char *current_state(chip_state_t *chip);

void chip_init(void) {
  chip_state_t *chip = calloc(1, sizeof(chip_state_t));
  chip->pin_ia = pin_init("IA", INPUT);
  chip->pin_ib = pin_init("IB", INPUT);
  chip->pin_oa = pin_init("OA", OUTPUT_LOW);
  chip->pin_ob = pin_init("OB", OUTPUT_LOW);
  chip->reported = "";

  const pin_watch_config_t watch_config = {
    .edge = BOTH,
    .pin_change = on_input_change,
    .user_data = chip,
  };
  pin_watch(chip->pin_ia, &watch_config);
  pin_watch(chip->pin_ib, &watch_config);

  const timer_config_t timer_config = {
    .callback = on_quiet,
    .user_data = chip,
  };
  chip->stop_timer = timer_init(&timer_config);

  printf("L9110S: ready\n");
}

static const char *current_state(chip_state_t *chip) {
  bool ia = pin_read(chip->pin_ia);
  bool ib = pin_read(chip->pin_ib);

  // The outputs mirror the inputs, so a scope or an LED on OA/OB shows the same thing.
  pin_write(chip->pin_oa, ia ? HIGH : LOW);
  pin_write(chip->pin_ob, ib ? HIGH : LOW);

  if (ia && ib) return "braking";
  if (ia) return "opening";
  if (ib) return "closing";
  return "stopped";
}

static void on_input_change(void *user_data, pin_t pin, uint32_t value) {
  chip_state_t *chip = (chip_state_t *)user_data;
  const char *state = current_state(chip);

  if (state == "stopped") {
    // Might be the gap in a PWM cycle rather than a stop. Wait and see.
    timer_start(chip->stop_timer, QUIET_BEFORE_STOPPED_US, false);
    return;
  }

  timer_stop(chip->stop_timer);   // the motor is driving, so any pending "stopped" was a gap
  report(chip, state);
}

/** The inputs have been quiet for a whole PWM period or more, so the motor really has stopped. */
static void on_quiet(void *user_data) {
  chip_state_t *chip = (chip_state_t *)user_data;
  report(chip, current_state(chip));
}

static void report(chip_state_t *chip, const char *state) {
  if (state == chip->reported) return;
  chip->reported = state;
  printf("MOTOR: %s\n", state);
}
