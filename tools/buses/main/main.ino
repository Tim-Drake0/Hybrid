#include "src/busPwr.h"
#include "src/busBME280.h"
#include <Arduino.h>
#include <HardwareSerial.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>


#define SDA_PIN PB11
#define SCL_PIN PB10


TwoWire Wire2(PB11, PB10); // SDA, SCL for I2C2

#define SEALEVELPRESSURE_HPA (1013.25)

Adafruit_BME280 bme;

byte sensorsBIT = B11111111; 

HardwareSerial MySerial(USART1);

uint8_t packet[14]; 

uint8_t packetBME[20]; 

unsigned long lastSendTime = 0;

// Read analog voltage and apply calibration
uint16_t readVoltage(int pin) {
    uint16_t raw = analogRead(pin);
    return raw;
}

void setup() {
    MySerial.begin(115200);
    memset(packet, 0, busPwr.size);

    Wire2.begin(PB11, PB10);  
    if(!bme.begin(0x77, &Wire2)){
        bitClear(sensorsBIT, 0);
    }
}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastSendTime >= 1000 / busPwr.frequency) {
        lastSendTime = currentMillis;

        uint16_t batt = analogRead(busPwr.battVolts.pin); 
        uint16_t volt3V = analogRead(busPwr.voltage3V.pin); 
        uint16_t volt5V = analogRead(busPwr.voltage5V.pin); 

        // header is ABBA
        packet[0] = 0xAB;
        packet[1] = 0xBA;

        packet[2] = 0x1A;
        packet[3] = 0xFE; // 6910

        // time in milliseconds
        packet[4] = (currentMillis >> 24) & 0xFF; // Most significant byte (MSB)
        packet[5] = (currentMillis >> 16) & 0xFF;
        packet[6] = (currentMillis >> 8)  & 0xFF;
        packet[7] = currentMillis & 0xFF;         // Least significant byte (LSB)

        // battery voltage
        packet[8] = (batt >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[9] = batt & 0xFF;         // Low byte (bits 7–0)

        packet[10] = (volt3V >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[11] = volt3V & 0xFF;         // Low byte (bits 7–0)

        packet[12] = (volt5V >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[13] = volt5V & 0xFF;         // Low byte (bits 7–0)

        //packet[14] = sensorsBIT;
//
        //packet[15] = (temp >> 8) & 0xFF;  // High byte (bits 9–8)
        //packet[16] = temp & 0xFF;         // Low byte (bits 7–0)

        // BME280 packet
        uint32_t temp = bme.readTemperature();
        uint32_t pressure = bme.readPressure();
        uint32_t humidity = bme.readHumidity();

        // header is ABBA
        packetBME[0] = 0xAB;
        packetBME[1] = 0xBA;

        packetBME[2] = 0x1A;
        packetBME[3] = 0xFF; // 6910

        // time in milliseconds
        packetBME[4] = (currentMillis >> 24) & 0xFF; // Most significant byte (MSB)
        packetBME[5] = (currentMillis >> 16) & 0xFF;
        packetBME[6] = (currentMillis >> 8)  & 0xFF;
        packetBME[7] = currentMillis & 0xFF;         // Least significant byte (LSB)

        packetBME[8] = (temp >> 24) & 0xFF; // Most significant byte (MSB)
        packetBME[9] = (temp >> 16) & 0xFF;
        packetBME[10] = (temp >> 8)  & 0xFF;
        packetBME[11] = temp & 0xFF;         // Least significant byte (LSB)

        packetBME[12] = (pressure >> 24) & 0xFF; // Most significant byte (MSB)
        packetBME[13] = (pressure >> 16) & 0xFF;
        packetBME[14] = (pressure >> 8)  & 0xFF;
        packetBME[15] = pressure & 0xFF;         // Least significant byte (LSB)

        packetBME[16] = (humidity >> 24) & 0xFF; // Most significant byte (MSB)
        packetBME[17] = (humidity >> 16) & 0xFF;
        packetBME[18] = (humidity >> 8)  & 0xFF;
        packetBME[19] = humidity & 0xFF;         // Least significant byte (LSB)

        // Send packet
        //MySerial.write(packet, busPwr.size);
        MySerial.write(packetBME, busBME280.size);
    }
}
