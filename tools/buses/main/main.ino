#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/streamSerialTelem.h"
#include "src/SensorDataFrame.h"
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
Adafruit_LSM9DS1 lsm = Adafruit_LSM9DS1(&Wire2, 0x1E6B);

unsigned long lastSendTime = 0;

SensorDataFrame thisFrame;

void setup() {
    MySerial.begin(115200);
    Wire2.begin(PB11, PB10); // I2C2

    // Initial values
    thisFrame.sensorsBIT = B00000000; 
    thisFrame.battVolts = 0;
    thisFrame.voltage3V = 0;
    thisFrame.voltage5V = 0;
    thisFrame.temperatureC = 0;
    thisFrame.pressurePasc = 0;
    thisFrame.humidityRH = 0;
    thisFrame.altitudeM = 0;

    // Start sensors
    if(bme.begin(0x77, &Wire2)){
        bitSet(thisFrame.sensorsBIT, 0);
    }

    if(lsm.begin()) {
        bitSet(thisFrame.sensorsBIT, 1);
    }
}

void loop() {
    thisFrame.currentMillis = millis();
    if (thisFrame.currentMillis - lastSendTime >= 1000 / busPwr.frequency) {
        lastSendTime = thisFrame.currentMillis;

        //Gather data
        readPWR(thisFrame);
        readBME280(thisFrame);

        // Generate packet
        auto packet = streamSerialTelem.serialize(thisFrame);
        // Send packet
        MySerial.write(packet.data(), packet.size());
    }
}
