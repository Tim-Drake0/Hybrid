

#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_LSM9DS1.h>


void readPWR(SensorDataFrame &frame){
    frame.battVolts = (analogRead(busPwr.battVolts.pin) * busPwr.battVolts.c1) + busPwr.battVolts.c1;
    frame.voltage3V = (analogRead(busPwr.voltage3V.pin) * busPwr.voltage3V.c1) + busPwr.voltage3V.c1;
    frame.voltage5V = (analogRead(busPwr.voltage5V.pin) * busPwr.voltage5V.c1) + busPwr.voltage5V.c1;
}

void readBME280(SensorDataFrame &frame){
    frame.temperatureC = (bme.readTemperature() * busBME280.temperatureC.c1) + busBME280.temperatureC.c0;
    frame.pressurePasc = (bme.readPressure() * busBME280.pressurePasc.c1) + busBME280.pressurePasc.c0;
    frame.humidityRH   = (bme.readHumidity() * busBME280.humidityRH.c1) + busBME280.humidityRH.c0;
    
    frame.altitudeM    = (bme.readAltitude(1013.25) * busBME280.altitudeM.c1) + busBME280.altitudeM.c0;
}

void setupLSM9DS1() {
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


void readLSM9DS1(SensorDataFrame &frame){
    lsm.read();  /* ask it to read in the data */   
    /* Get a new sensor event */ 
    sensors_event_t a, m, g, temp;

    lsm.getEvent(&a, &m, &g, &temp); 

    frame.accelx = a.acceleration.x; 
    frame.accely = a.acceleration.y; 
    frame.accelz = a.acceleration.z; 
    frame.magx = m.magnetic.x; 
    frame.magy = m.magnetic.y; 
    frame.magz = m.magnetic.z; 
    frame.gyrox = g.gyro.x; 
    frame.gyroy = g.gyro.y; 
    frame.gyroz = g.gyro.z;
}