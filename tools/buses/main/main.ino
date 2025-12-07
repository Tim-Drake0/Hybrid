#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/busIMU.h"
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

byte sensorsBIT = B11111111; 

//uint8_t packet[30]; 

unsigned long lastSendTime = 0;

void setup() {
    MySerial.begin(115200);

    Wire2.begin(PB11, PB10);  
    if(!bme.begin(0x77, &Wire2)){
        bitClear(sensorsBIT, 0);
    }

    if(!lsm.begin()){
        bitClear(sensorsBIT, 1);
    }

    setupLSM9DS1(lsm);

}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastSendTime >= 1000 / busPwr.frequency) {
        lastSendTime = currentMillis;

        //Gather data
        readPWR();
        readBME280(bme);
        readLSM9DS1(lsm);

        // Generate packet
        auto packet = streamSerialTelem.serialize(currentMillis);
        // Send packet
        MySerial.write(packet.data(), packet.size());
    }
}
