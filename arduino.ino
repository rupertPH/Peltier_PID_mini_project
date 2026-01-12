/*******************************************************
 * @file Basic.ino
 *
 * @brief Basic example demonstrating usage of the 7Semi DS18B20 library.
 *
 * This example initializes a DS18B20 digital temperature sensor using
 * the 1-wire protocol and reads the temperature in Celsius from the
 * first discovered device on the bus.
 *
 * Key features demonstrated:
 * - OneWire protocol setup
 * - Device search and temperature readout
 *
 * @note This example requires the 7Semi DS18B20 library to be installed.
 *
 * @section author Author
 * Written by 7Semi
 *
 * @section license License
 * @license MIT
 * Copyright (c) 2025 7Semi
 *******************************************************/

#include <7semi_DS18B20.h>

DS18B20_7semi sensor(2);

uint8_t addr[8];
bool fanState = false;   // zapamiętany stan wiatraka

void setup() {
  Serial.begin(9600);

  if (!sensor.begin()) {
    Serial.println("ERROR: DS18B20 not found");
    while (1);
  }

  sensor.searchDevices();

  pinMode(10, OUTPUT);
  digitalWrite(10, LOW); // wiatrak startowo OFF
}

void loop() {
  // ---- 1. Odczyt temperatury ----
  if (sensor.getAddress(0, addr)) {
    float temp = sensor.readTemperature(addr);
    Serial.print("T:");
    Serial.println(temp);   // np. T:23.56
  }

  // ---- 2. Odbiór komendy z PC ----
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');

    if (cmd == "F1") {
      fanState = true;
    } 
    else if (cmd == "F0") {
      fanState = false;
    }
  }

  // ---- 3. Sterowanie wiatrakiem ----
  digitalWrite(10, fanState ? HIGH : LOW);

  delay(1000);
}
