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

    int16_t accelx;
    int16_t accely;
    int16_t accelz;

    int16_t magx;
    int16_t magy;
    int16_t magz;

    int16_t gyrox;
    int16_t gyroy;
    int16_t gyroz;

    float highG_accelx;
    float highG_accely;
    float highG_accelz;
};

extern SensorDataFrame thisFrame;

#endif
