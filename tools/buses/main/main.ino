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

Adafruit_BME280 bme;

byte sensorsBIT = B11111111; 

HardwareSerial MySerial(USART1);

uint8_t packet[30]; 

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

        //Gather data
        //uint16_t batt = analogRead(busPwr.battVolts.pin); 
        //uint16_t volt3V = analogRead(busPwr.voltage3V.pin); 
        //uint16_t volt5V = analogRead(busPwr.voltage5V.pin); 

        busPwr.readSensor();
        busBME280.readSensor(bme);

        // header is ABBA and timestamp
        packet[0] = 0xAB;
        packet[1] = 0xBA;

        packet[2] = 0x1A;
        packet[3] = 0xFF; // 6910

        // time in milliseconds
        packet[4] = (currentMillis >> 24) & 0xFF; // Most significant byte (MSB)
        packet[5] = (currentMillis >> 16) & 0xFF;
        packet[6] = (currentMillis >> 8)  & 0xFF;
        packet[7] = currentMillis & 0xFF;         // Least significant byte (LSB)

        //Votlage packets =============================================================
        auto voltage_serialized = busPwr.serialize();

        for (size_t i = 0; i < voltage_serialized.size(); i++) {
            packet[8 + i] = voltage_serialized[i];
        }
 
        //BME280 packets =============================================================
        auto BME280_serialized = busBME280.serialize();

        for (size_t i = 0; i < BME280_serialized.size(); i++) {
            packet[14 + i] = BME280_serialized[i];
        }

        // Send packet
        MySerial.write(packet, sizeof(packet));
    }
}
