#include "sensorUtil.h"
#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/busIMU.h"
#include <Arduino.h>

// Power readings
float sensor_battVolts  = 0;
float sensor_voltage3V  = 0;
float sensor_voltage5V  = 0;

// BME280 readings
float sensor_temperatureC = 0;
float sensor_pressurePasc = 0;
float sensor_humidityRH   = 0;
float sensor_altitudeM    = 0;

// LSM9DS1 events
sensors_event_t imu_accel;
sensors_event_t imu_gyro;
sensors_event_t imu_mag;
sensors_event_t imu_temp;

void readPWR(){
    sensor_battVolts = (analogRead(busPwr.battVolts.pin) * busPwr.battVolts.c1) + busPwr.battVolts.c1;
    sensor_voltage3V = (analogRead(busPwr.voltage3V.pin) * busPwr.voltage3V.c1) + busPwr.voltage3V.c1;
    sensor_voltage5V = (analogRead(busPwr.voltage5V.pin) * busPwr.voltage5V.c1) + busPwr.voltage5V.c1;
}

void setupLSM9DS1(Adafruit_LSM9DS1& lsm)
{
  // 1.) Set the accelerometer range
  lsm.setupAccel(lsm.LSM9DS1_ACCELRANGE_2G, lsm.LSM9DS1_ACCELDATARATE_10HZ);
  //lsm.setupAccel(lsm.LSM9DS1_ACCELRANGE_4G, lsm.LSM9DS1_ACCELDATARATE_119HZ);
  //lsm.setupAccel(lsm.LSM9DS1_ACCELRANGE_8G, lsm.LSM9DS1_ACCELDATARATE_476HZ);
  //lsm.setupAccel(lsm.LSM9DS1_ACCELRANGE_16G, lsm.LSM9DS1_ACCELDATARATE_952HZ);
  
  // 2.) Set the magnetometer sensitivity
  lsm.setupMag(lsm.LSM9DS1_MAGGAIN_4GAUSS);
  //lsm.setupMag(lsm.LSM9DS1_MAGGAIN_8GAUSS);
  //lsm.setupMag(lsm.LSM9DS1_MAGGAIN_12GAUSS);
  //lsm.setupMag(lsm.LSM9DS1_MAGGAIN_16GAUSS);

  // 3.) Setup the gyroscope
  lsm.setupGyro(lsm.LSM9DS1_GYROSCALE_245DPS);
  //lsm.setupGyro(lsm.LSM9DS1_GYROSCALE_500DPS);
  //lsm.setupGyro(lsm.LSM9DS1_GYROSCALE_2000DPS);
}

void readLSM9DS1(Adafruit_LSM9DS1& lsm){
    lsm.read();   /* ask it to read in the data */

    /* Get a new sensor event */ 
    lsm.getEvent(&imu_accel, &imu_gyro, &imu_mag, &imu_temp);
}

void readBME280(Adafruit_BME280& bme){
    sensor_temperatureC = (bme.readTemperature() * busBME280.temperatureC.c1) + busBME280.temperatureC.c0;
    sensor_pressurePasc = (bme.readPressure() * busBME280.pressurePasc.c1) + busBME280.pressurePasc.c0;
    sensor_humidityRH   = (bme.readHumidity() * busBME280.humidityRH.c1) + busBME280.humidityRH.c0;
    sensor_altitudeM    = (bme.readAltitude(1013.25) * busBME280.altitudeM.c1) + busBME280.altitudeM.c0;
}