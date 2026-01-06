

#include "src/busPwr.h"
#include "src/busBME280.h"
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_ADXL375.h>

#include <SPI.h> 

void readPWR(){
    thisFrame.battVolts = (analogRead(busPwr.battVolts.pin) * busPwr.battVolts.c1) + busPwr.battVolts.c1;
    thisFrame.voltage3V = (analogRead(busPwr.voltage3V.pin) * busPwr.voltage3V.c1) + busPwr.voltage3V.c1;
    thisFrame.voltage5V = (analogRead(busPwr.voltage5V.pin) * busPwr.voltage5V.c1) + busPwr.voltage5V.c1;
}

// ================ BME280 ================
void beginBME280(){
  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/
  temp.timeBtwnSamp       = 1000/1;   // 1 Hz
  pressure.timeBtwnSamp   = 1000/20;  // 20 Hz
  humidity.timeBtwnSamp   = 1000/1;   // 1  Hz
  baroAlt.timeBtwnSamp    = 1000/30;  // 30 Hz
  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/  

  if(bme.begin(0x77, &Wire2)){
      bitSet(thisFrame.sensorsBIT, 0);
  }
}

void readBME280(){
  if (thisFrame.currentMillis - temp.timeLastSamp >= temp.timeBtwnSamp) {
    temp.timeLastSamp = thisFrame.currentMillis;
    thisFrame.temperatureC = (bme.readTemperature() * busBME280.temperatureC.c1) + busBME280.temperatureC.c0;
  }

  if (thisFrame.currentMillis - pressure.timeLastSamp >= pressure.timeBtwnSamp) {
    pressure.timeLastSamp = thisFrame.currentMillis;
    thisFrame.pressurePasc = (bme.readPressure() * busBME280.pressurePasc.c1) + busBME280.pressurePasc.c0;
  }

  if (thisFrame.currentMillis - humidity.timeLastSamp >= humidity.timeBtwnSamp) {
    humidity.timeLastSamp = thisFrame.currentMillis;
    thisFrame.humidityRH   = (bme.readHumidity() * busBME280.humidityRH.c1) + busBME280.humidityRH.c0;
  }

  if (thisFrame.currentMillis - baroAlt.timeLastSamp >= baroAlt.timeBtwnSamp) {
    baroAlt.timeLastSamp = thisFrame.currentMillis;
    thisFrame.altitudeM    = (bme.readAltitude(1013.25) * busBME280.altitudeM.c1) + busBME280.altitudeM.c0;
  }
}

// ================ LSM9DS1 ================
void beginLSM9DS1_AG() {
  //Addresses for the registers
  #define LSM9DS1_ADDRESS_ACCELGYRO            (0x6B)
  #define LSM9DS1_XG_ID                        (0b01101000)
  #define LSM9DS1_REGISTER_CTRL_REG1_G         (0x10)
  #define LSM9DS1_REGISTER_CTRL_REG3_G         (0x12)
  #define LSM9DS1_REGISTER_CTRL_REG5_XL        (0x1F)
  #define LSM9DS1_REGISTER_CTRL_REG6_XL        (0x20)
  #define LSM9DS1_REGISTER_CTRL_REG8           (0x22)
  #define LSM9DS1_REGISTER_OUT_X_L_G           (0x18)
  #define LSM9DS1_REGISTER_OUT_X_L_XL          (0x28)

  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/
  accel.range = 0x10; // 4G
  accel.datarate = 0xA0; // 238Hz
  accel.gainX = accel.gainY = accel.gainZ = 1;
  accel.lsb = 0.00122; // 2G = 0.00061, 4G = 0.00122, 8G = 0.00244, 16G = 0.00732
  accel.timeBtwnSamp = 1000/100;   // 100 Hz
  
  gyro.range = 0x18; // 2000 dps
  gyro.datarate = 0xC0; // 912Hz
  gyro.gainX = gyro.gainY = gyro.gainZ = 1;
  gyro.lsb = 0.07000; // 245DPS = 0.00875, 500DPS = 0.01750, 2000DPS = 0.07000
  gyro.timeBtwnSamp = 1000/100;   // 100 Hz
  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/  

  pinMode(CS_AG_pin, OUTPUT);
  digitalWrite(CS_AG_pin, HIGH);  // inactive high  
  SPI.begin();    

  // soft reset & reboot accel/gyro
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG8, 0x05);  
  delay(20);  

  uint8_t ag_id = read8(CS_AG_pin, 0x0F);   // WHO_AM_I AG 
  MySerial.print("AG WHO_AM_I: 0x"); MySerial.println(ag_id, HEX); 

  if(ag_id == 0x68){
    bitSet(thisFrame.sensorsBIT, 1);
  } 

  // Accel: 119 Hz, ±2g
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG6_XL, accel.range | accel.datarate);

  // Gyro: 119 Hz, 245 dps
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG1_G, gyro.range | gyro.datarate);  

  // Enable accel axes
  write8(CS_AG_pin, LSM9DS1_REGISTER_CTRL_REG5_XL, 0x38); 

  delay(10);  

  //set Accelerometer G level and add G to the gains
  //g = int16_t(1 / accel.gainZ);
  //accel.gainX *= 9.80665;
  //accel.gainY *= 9.80665;
  //accel.gainZ *= 9.80665;
}

void readLSM9DS1_AG(){
  byte buffer[6];

  uint8_t xlo;
  int16_t xhi;
  uint8_t ylo;
  int16_t yhi;
  uint8_t zlo;
  int16_t zhi;

  // Read the accelerometer
  if (thisFrame.currentMillis - accel.timeLastSamp >= accel.timeBtwnSamp) {
    accel.timeLastSamp = thisFrame.currentMillis;
  
    readBuffer(CS_AG_pin, 0x80 | LSM9DS1_REGISTER_OUT_X_L_XL, 6, buffer);

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

    accel.rawX = xhi;
    accel.rawY = yhi;
    accel.rawZ = zhi;

    accel.x = accel.rawX * accel.lsb;  
    accel.y = accel.rawY * accel.lsb; 
    accel.z = accel.rawZ * accel.lsb; 

    thisFrame.accelx = accel.x;
    thisFrame.accely = accel.y;
    thisFrame.accelz = accel.z;

    // apply trigonometry to get the pitch and roll:
    thisFrame.pitch = atan(accel.x/sqrt(pow(accel.y,2) + pow(accel.z,2))) * (180.0/PI);
    thisFrame.yaw = atan(accel.y/sqrt(pow(accel.x,2) + pow(accel.z,2))) * (180.0/PI);
  }

  // Read gyro
  if (thisFrame.currentMillis - gyro.timeLastSamp >= gyro.timeBtwnSamp) {
    gyro.timeLastSamp = thisFrame.currentMillis;
  
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

    gyro.rawX = xhi;
    gyro.rawY = yhi;
    gyro.rawZ = zhi;

    gyro.x = gyro.rawX * gyro.lsb;
    gyro.y = gyro.rawY * gyro.lsb;
    gyro.z = gyro.rawZ * gyro.lsb;

    thisFrame.gyrox = gyro.x;
    thisFrame.gyroy = gyro.y;
    thisFrame.gyroz = gyro.z;
  }
}

void beginLSM9DS1_M() {
  //Addresses for the registers
  #define LSM9DS1_REGISTER_CTRL_REG1_M         (0x20)
  #define LSM9DS1_REGISTER_CTRL_REG2_M         (0x21)
  #define LSM9DS1_REGISTER_CTRL_REG3_M         (0x22)
  #define LSM9DS1_REGISTER_CTRL_REG4_M         (0x23)
  #define LSM9DS1_REGISTER_OUT_X_L_M           (0x28)

  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/
  mag.range = 0x00; // 4 gauss  
  mag.datarate = 0x7C; // 80Hz
  mag.gainX = mag.gainY = mag.gainZ = 1;
  mag.lsb = 0.00014; // 4GAUSS = 0.00014, 8GAUSS = 0.00029, 12GAUSS = 0.00043, 16GAUSS = 0.00058
  mag.timeBtwnSamp = 1000/1;   // 1 Hz
  
  /*====  NEEDS TO BE UPDATEED FROM SETTINGS  ====*/  

  pinMode(CS_MAG_pin, OUTPUT); 
  digitalWrite(CS_MAG_pin, HIGH);  // inactive high 
  SPI.begin();    
  delay(20);  
  
  uint8_t mag_id = read8(CS_MAG_pin, 0x0F);   // WHO_AM_I AG 

  MySerial.print("MAG WHO_AM_I: 0x"); MySerial.println(mag_id, HEX); 

  if(mag_id == 0x3D){
    bitSet(thisFrame.sensorsBIT, 2);
  } 

  // Mag reset
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG2_M, 0x0C | mag.range); 

  delay(10);  

  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG1_M, 0x7C); // ultra-high performance, 80 Hz 
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG3_M, 0x00); // continuous
  write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG4_M, 0x0C); // Z ultra-high 

  //write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG1_M, 0x60 | mag.datarate); // 0x60 = ultra-high performance
  //write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG2_M, 0x08 | mag.range); // 0x08 = reboot memory content
  //write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG3_M, 0x84); // continuous, I2C disable, SPI R/W
  //write8(CS_MAG_pin, LSM9DS1_REGISTER_CTRL_REG4_M, 0x0C); // Z ultra-high 
  uint8_t astat = read8(CS_MAG_pin, 0x27); MySerial.print("ASTAT: "); MySerial.println(astat, BIN); 
}

void readLSM9DS1_M(){
  // Read the magnetometer
  if (thisFrame.currentMillis - mag.timeLastSamp >= mag.timeBtwnSamp) {
    mag.timeLastSamp = thisFrame.currentMillis;

    byte buffer[6];
    readBuffer(CS_MAG_pin, 0xC0 | LSM9DS1_REGISTER_OUT_X_L_M, 6, buffer);

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

    mag.rawX = xhi;
    mag.rawY = yhi;
    mag.rawZ = zhi;

    mag.x = mag.rawX * mag.lsb;
    mag.y = mag.rawY * mag.lsb;
    mag.z = mag.rawZ * mag.lsb;

    thisFrame.magx = mag.x;
    thisFrame.magy = mag.y;
    thisFrame.magz = mag.z;
  }
}

// ==== HELPERS ====
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
  //uint8_t regbuf[1] = {uint8_t(reg | 0x80)};
  //begin SPI transaction
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWriteFast(CS, LOW);
  //send register
  SPI.transfer(reg);
  //read data
  for(uint8_t i = 0; i < len; i++){
    buffer[i] = SPI.transfer(0);
  }
  //end SPI transaction
  digitalWriteFast(CS, HIGH);
  SPI.endTransaction();
  
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