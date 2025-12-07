#ifndef SENSOR_DATA_FRAME_H
#define SENSOR_DATA_FRAME_H

#include <Arduino.h>
#include <cstdint>

struct SensorDataFrame {
    unsigned long currentMillis;
    byte sensorsBIT;

    uint16_t battVolts;
    uint16_t voltage3V;
    uint16_t voltage5V;

    float temperatureC;
    float pressurePasc;
    float humidityRH;
    float altitudeM;

    float accelx;
    float accely;
    float accelz;

    float magx;
    float magy;
    float magz;

    float gyrox;
    float gyroy;
    float gyroz;
};

extern SensorDataFrame thisFrame;

#endif
