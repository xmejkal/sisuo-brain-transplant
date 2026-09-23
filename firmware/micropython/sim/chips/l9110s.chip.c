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
// other, both low coasts, and both high brakes. Direction is all this reports — PWM duty arrives
// as a rapid square wave, and measuring it here would mean sampling rather than watching edges,
// which is more machinery than the digital behaviour needs.

#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct {
  pin_t pin_ia;
  pin_t pin_ib;
  pin_t pin_oa;
  pin_t pin_ob;
  const char *reported;   // what we last printed, so a PWM'd input does not flood the log
} chip_state_t;

static void on_input_change(void *user_data, pin_t pin, uint32_t value);
static void report(chip_state_t *chip);

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

  printf("L9110S: ready\n");
}

static void on_input_change(void *user_data, pin_t pin, uint32_t value) {
  report((chip_state_t *)user_data);
}

static void report(chip_state_t *chip) {
  bool ia = pin_read(chip->pin_ia);
  bool ib = pin_read(chip->pin_ib);

  // The outputs mirror the inputs, so a scope or an LED on OA/OB shows the same thing.
  pin_write(chip->pin_oa, ia ? HIGH : LOW);
  pin_write(chip->pin_ob, ib ? HIGH : LOW);

  const char *state;
  if (ia && ib) {
    state = "braking";
  } else if (ia) {
    state = "opening";
  } else if (ib) {
    state = "closing";
  } else {
    state = "stopped";
  }

  // Only speak when something changed: the driven input is a PWM square wave, and every edge
  // arrives here.
  if (state != chip->reported) {
    chip->reported = state;
    printf("MOTOR: %s\n", state);
  }
}
