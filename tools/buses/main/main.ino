#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/streamSerialTelem.h"
#include <Arduino.h>
#include <HardwareSerial.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_LSM9DS1.h>

#define SDA_PIN PB11
#define SCL_PIN PB10

TwoWire Wire2(PB11, PB10); // SDA, SCL for I2C2
HardwareSerial MySerial(USART1);

Adafruit_BME280 bme;
Adafruit_LSM9DS1 lsm = Adafruit_LSM9DS1();

byte sensorsBIT = B00000000; 

//uint8_t packet[30]; 

unsigned long lastSendTime = 0;

void setup() {
    MySerial.begin(115200);
    Wire2.begin(PB11, PB10); // I2C2

    if(bme.begin(0x77, &Wire2)){
        bitSet(sensorsBIT, 0);
    }
}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastSendTime >= 1000 / busPwr.frequency) {
        lastSendTime = currentMillis;

        //Gather data
        busPwr.readSensor();
        busBME280.readSensor(bme);

        // Generate packet
        auto packet = streamSerialTelem.serialize(currentMillis, sensorsBIT);
        // Send packet
        MySerial.write(packet.data(), packet.size());
    }
}
