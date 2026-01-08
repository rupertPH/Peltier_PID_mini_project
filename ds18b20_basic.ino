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

DS18B20_7semi sensor(2);  // data pin 2

void setup() {
  Serial.begin(9600);
  if (!sensor.begin()) {
    Serial.println("No DS18B20 found!");
    while (1)
      ;
  }
  uint8_t count = sensor.searchDevices();
  Serial.print("Found devices: ");
  Serial.println(count);
}

void loop() {
  uint8_t addr[8];
  if (sensor.getAddress(0, addr)) {
    float t = sensor.readTemperature(addr);
    //serial.print("Temp C: ");
    Serial.println(t);
  }
  delay(1000);
}
