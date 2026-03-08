#ifndef SENSOR_DATA_FRAME_H
#define SENSOR_DATA_FRAME_H

#ifdef __cplusplus
extern "C" {
#endif

struct SensorDataFrame {
    unsigned long currentMillis;
    uint8_t sensorsBIT;

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

    float highG_accelx;
    float highG_accely;
    float highG_accelz;

    float pitch;
    float roll;
    float yaw;

    unsigned long loopTime;
};

extern SensorDataFrame thisFrame;

#endif
