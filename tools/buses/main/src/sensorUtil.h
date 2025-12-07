#ifndef SENSORSUTIL_H
#define SENSORSUTIL_H

#include <Arduino.h>
#include <Adafruit_LSM9DS1.h>
#include <Adafruit_BME280.h>
#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/busIMU.h"
#include "sensorUtil.h"

// Power sensor readings
extern float sensor_battVolts;
extern float sensor_voltage3V;
extern float sensor_voltage5V;

// BME280 sensor readings
extern float sensor_temperatureC;
extern float sensor_pressurePasc;
extern float sensor_humidityRH;
extern float sensor_altitudeM;

// LSM9DS1 sensor readings
extern sensors_event_t imu_accel;
extern sensors_event_t imu_mag;
extern sensors_event_t imu_gyro;
extern sensors_event_t imu_temp;

// Functions
void readPWR();

void setupLSM9DS1(Adafruit_LSM9DS1& lsm);

void readLSM9DS1(Adafruit_LSM9DS1& lsm);

void readBME280(Adafruit_BME280& bme);

#endif // SENSORS_H
