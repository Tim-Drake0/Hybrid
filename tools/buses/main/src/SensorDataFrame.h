#ifndef SENSOR_DATA_FRAME_H
#define SENSOR_DATA_FRAME_H

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
};

extern SensorDataFrame thisFrame;

#endif
