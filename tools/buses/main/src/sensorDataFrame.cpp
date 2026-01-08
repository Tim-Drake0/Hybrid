#include "SensorDataFrame.h"
#include <Arduino.h>

/* Sensors BIT:
0: BME280
1: LSM9DS1_AG
2: LSM9DS1_M
3: ADXL375
4: SD Card
5:
6:
7:
*/

SensorDataFrame thisFrame = {
    0,          // currentMillis
    B00000000,  // sensorsBIT
    0,          // battVolts,
    0,          // voltage3V, voltage5V
    0,          // voltage5V
    0,          // temperatureC
    0,          // pressurePasc
    0,          // humidityRH
    0,          // altitudeM
    0,          // accelx
    0,          // accely
    0,          // accelz
    0,          // magx
    0,          // magy
    0,          // magz
    0,          // gyrox
    0,          // gyroy
    0,          // gyroz
    0,          // highG_accelx
    0,          // highG_accely
    0,          // highG_accelz
    0,          // pitch
    0,          // roll
    0           // yaw
};
