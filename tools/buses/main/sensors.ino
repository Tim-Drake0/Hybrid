

#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_LSM9DS1.h>
#include <Adafruit_ADXL375.h>

#include <SPI.h> 

void readPWR(SensorDataFrame &frame){
    frame.battVolts = (analogRead(busPwr.battVolts.pin) * busPwr.battVolts.c1) + busPwr.battVolts.c1;
    frame.voltage3V = (analogRead(busPwr.voltage3V.pin) * busPwr.voltage3V.c1) + busPwr.voltage3V.c1;
    frame.voltage5V = (analogRead(busPwr.voltage5V.pin) * busPwr.voltage5V.c1) + busPwr.voltage5V.c1;
}

//void readBME280(SensorDataFrame &frame){
//    frame.temperatureC = (bme.readTemperature() * busBME280.temperatureC.c1) + busBME280.temperatureC.c0;
//    frame.pressurePasc = (bme.readPressure() * busBME280.pressurePasc.c1) + busBME280.pressurePasc.c0;
//    frame.humidityRH   = (bme.readHumidity() * busBME280.humidityRH.c1) + busBME280.humidityRH.c0;
//    
//    frame.altitudeM    = (bme.readAltitude(1013.25) * busBME280.altitudeM.c1) + busBME280.altitudeM.c0;
//}

void beginLSM9DS1_AG() {
  //Addresses for the registers
  #define LSM9DS1_ADDRESS_ACCELGYRO            (0x6B)
  #define LSM9DS1_XG_ID                        (0b01101000)
  #define LSM9DS1_REGISTER_CTRL_REG1_G         (0x10)
  #define LSM9DS1_REGISTER_CTRL_REG3_G         (0x12)
  #define LSM9DS1_REGISTER_CTRL_REG5_XL        (0x1F)
  #define LSM9DS1_REGISTER_CTRL_REG6_XL        (0x20)
  #define LSM9DS1_REGISTER_CTRL_REG8           (0x22)
  #define LSM9DS1_REGISTER_CTRL_REG1_M         (0x20)
  #define LSM9DS1_REGISTER_CTRL_REG2_M         (0x21)
  #define LSM9DS1_REGISTER_CTRL_REG3_M         (0x22)
  #define LSM9DS1_REGISTER_CTRL_REG4_M         (0x23)
  #define LSM9DS1_REGISTER_OUT_X_L_G           (0x18)
  #define LSM9DS1_REGISTER_OUT_X_L_XL          (0x28)
  #define LSM9DS1_REGISTER_OUT_X_L_M           (0x28)

  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/
  accel.range = 0x10; // 4G
  accel.datarate = 0xA0; // 238Hz
  accel.gainX = accel.gainY = accel.gainZ = 0.000122;
  
  gyro.range = 0x18; // 2000 dps
  gyro.datarate = 0xC0; // 912Hz
  gyro.gainX = gyro.gainY = gyro.gainZ = 0.07000;

  mag.range = 0x00; // 4 gauss  
  mag.datarate = 0xC0; // 912Hz
  mag.gainX = mag.gainY = mag.gainZ = 0.14;
  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/  

  pinMode(CS_AG_pin, OUTPUT);
  digitalWrite(CS_AG_pin, HIGH);  // inactive high  
  pinMode(CS_MAG_pin, OUTPUT); // *********** move to begin mag eventually
  digitalWrite(CS_MAG_pin, HIGH);  // inactive high  *********** move to begin mag eventually
  SPI.begin();    

  // soft reset & reboot accel/gyro
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG8, 0x05);  
  delay(20);  
  uint8_t ag_id = read8(CS_AG_pin, 0x0F);   // WHO_AM_I AG
  uint8_t mag_id = read8(CS_MAG_pin, 0x0F);   // WHO_AM_I AG // *********** move to begin mag eventually 

  MySerial.print("AG WHO_AM_I:  0x"); MySerial.println(ag_id, HEX);
  MySerial.print("MAG WHO_AM_I: 0x"); MySerial.println(mag_id, HEX); // *********** move to begin mag eventually 

  if(ag_id != 0x68){
    MySerial.println("AG sensor not detected!");
    while(1);
  } 


  // Accel: 119 Hz, ±2g
  //write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG6_XL, 0x60); 
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG6_XL, accel.range | accel.datarate);

  // Gyro: 119 Hz, 245 dps
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG1_G, gyro.range | gyro.datarate);  

  // Enable accel axes
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG5_XL, 0x38); 

  
  // Mag reset
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG2_M, 0x0C); // *********** move to begin mag eventually

  delay(10);  

  // Mag: ultra-high performance, 10 Hz // *********** move to begin mag eventually
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG1_M, 0x70);
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG3_M, 0x00); // continuous
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG4_M, 0x0C); // Z ultra-high 
  uint8_t gstat = read8(CS_AG_pin, 0x17); MySerial.print("GSTAT: "); MySerial.println(gstat, BIN);
  uint8_t astat = read8(CS_MAG_pin, 0x27); MySerial.print("ASTAT: "); MySerial.println(astat, BIN); 


  //set Accelerometer G level and add G to the gains
  //g = int16_t(1 / accel.gainZ);
  //accel.gainX *= 9.80665;
  //accel.gainY *= 9.80665;
  //accel.gainZ *= 9.80665;
}

uint8_t read8(PinName CS, uint8_t reg) {
  uint8_t val;
  //begin SPI transaction
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS, LOW);
  //send register
  SPI.transfer(reg | 0x80);
  //read data
  val = SPI.transfer(0);
  //end SPI transaction
  digitalWrite(CS, HIGH);
  SPI.endTransaction();
  return val;
}

void write8(PinName CS, uint8_t reg, uint8_t val) {
  //begin SPI transaction
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS, LOW);
  SPI.transfer(reg & 0x7F);
  //Send data
  SPI.transfer(val);
  //End transaction
  digitalWrite(CS, HIGH);
  SPI.endTransaction();
}

void readBuffer(PinName CS, byte reg, byte len, uint8_t *buffer) {
  uint8_t regbuf[1] = {uint8_t(reg | 0x80)};
  //begin SPI transaction
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWriteFast(CS, LOW);
  //send register
  SPI.transfer(regbuf[0]);
  //read data
  for(uint8_t i = 0; i < len; i++){
    buffer[i] = SPI.transfer(0);
  }
  //end SPI transaction
  digitalWriteFast(CS, HIGH);
  SPI.endTransaction();
  
}

void readLSM9DS1_AG(){
  // Read the accelerometer
  byte buffer[6];
  readBuffer(CS_AG_pin, 0x80 | LSM9DS1_REGISTER_OUT_X_L_XL, 6, buffer);

  uint8_t xlo = buffer[0];
  int16_t xhi = buffer[1];
  uint8_t ylo = buffer[2];
  int16_t yhi = buffer[3];
  uint8_t zlo = buffer[4];
  int16_t zhi = buffer[5];

  // Shift values to create properly formed integer (low byte first)
  xhi <<= 8;
  xhi |= xlo;
  yhi <<= 8;
  yhi |= ylo;
  zhi <<= 8;
  zhi |= zlo;
  thisFrame.accelx = xhi;
  thisFrame.accely = yhi;
  thisFrame.accelz = zhi;

  // Read gyro
  readBuffer(CS_AG_pin, 0x80 | LSM9DS1_REGISTER_OUT_X_L_G, 6, buffer);

  xlo = buffer[0];
  xhi = buffer[1];
  ylo = buffer[2];
  yhi = buffer[3];
  zlo = buffer[4];
  zhi = buffer[5];

  // Shift values to create properly formed integer (low byte first)
  xhi <<= 8;
  xhi |= xlo;
  yhi <<= 8;
  yhi |= ylo;
  zhi <<= 8;
  zhi |= zlo;

  thisFrame.gyrox = xhi;
  thisFrame.gyroy = yhi;
  thisFrame.gyroz = zhi;
}


//void readADXL375(SensorDataFrame &frame){
//    sensors_event_t event;
//    adx.getEvent(&event);
//
//    frame.highG_accelx = event.acceleration.x; 
//    frame.highG_accely = event.acceleration.y; 
//    frame.highG_accelz = event.acceleration.z; 
//
//}