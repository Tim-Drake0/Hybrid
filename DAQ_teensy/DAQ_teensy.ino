#include <SPI.h>
#include <Wire.h>
#include <PWMServo.h>
#include "HX711.h"
#include <SD.h>
#include <Adafruit_INA219.h>
#include "max6675.h"
#include <RH_RF95.h>
#include <Adafruit_ADS1X15.h>

#define thermo_CLK  0
#define thermo1_CS  1 // top tank
#define thermo2_CS  2 // bot tank
#define thermo_DO  3
#define servo_1_out  4 // fill
#define servo_2_out  5 // vent
#define servo_3_out  6 // mov
#define servo_4_out  7 // spare

#define RFM95_RST  9
#define RFM95_CS 10

#define pt_3  16
#define pt_4  17

#define RFM95_INT 24
#define RADIO_LED 25
#define pyro_1_fire  26
#define pyro_1_cont_in  27
#define buzzerPin 28

#define pyro_2_cont_in  38
#define pyro_2_fire  39
#define arm_out 40

/// DATA ========================================================================
// SD Data Logging
int chipSelect = BUILTIN_SDCARD;
//const int SDCS = BUILTIN_SDCARD; // Use built in sd card for data logging
String filename; // Name of data file
File datafile; // Data file instance
String fileheader = "Time[ms],BATT[V],BATT_CURR[mA],TC1[F],TC2[F],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";

// Serial comms to arduino nano
const int dt_serial2 = 1000/60; // transmission speed [ms]
long int last_time_serial2 = 0;
unsigned long startLoopTime = 0;

// Radio Transceiver
#define RF95_FREQ 433.9869
RH_RF95 rf95(RFM95_CS, RFM95_INT);
bool send_pending = false;

struct __attribute__((packed)) DAQ_Payload // Payload to arduino nano
{
  uint32_t timestamp = 0; 
  uint8_t valve_states = 0;
  uint8_t pyro_states = 0;
  uint8_t arm_state = 0;
  uint8_t sensor_states = 0; // 0 = SD card, 1 = INA219, 2 = ADS1115
  float pt1 = 0;
  float pt2 = 0;
  float pt3 = 0;
  float pt4 = 0;
  float pt5 = 0;
  float pt6 = 0;
  float load_cell = 0;
  float batt_volts = 0;
  float batt_current = 0;
  float tc1 = 0;
  float tc2 = 0;
  int8_t RSSI = 0;
  uint32_t tsy_looptime = 0;
};
DAQ_Payload daq_pkt;

struct __attribute__((packed)) Switch_Payload { // Payload from switches
  bool fill = 0;
  bool vent = 0;
  bool mov = 0; 
  bool SW4 = 0; 
  bool py1 = 0; 
  bool py2 = 0; 
  bool arm = 0; 
  bool SW5 = 0; 
  bool SW6 = 0; 
};
Switch_Payload sw_pkt;

struct EEPROM
{
  float pt1_c0 = 0;
  float pt1_c1 = 1;
  float pt2_c0 = 0;
  float pt2_c1 = 1;
  float pt3_c0 = 0;
  float pt3_c1 = 1;
  float pt4_c0 = 0;
  float pt4_c1 = 1;
  float servo1_open   = 0;
  float servo1_close  = 1;
  float servo2_open   = 0;
  float servo2_close  = 1;
  float servo3_open   = 0;
  float servo3_close  = 1;
  float servo4_open   = 0;
  float servo4_close  = 1;
  int SD_sample_rate = 100;
};
EEPROM eeprom;

// Voltage Monitors
float batt_volt;

// Current sensor
Adafruit_INA219 ina219;

// 16-bit 4 channel ADC 
Adafruit_ADS1115 ads1115;

// Thermocouple sensor
MAX6675 tc1(thermo_CLK, thermo1_CS, thermo_DO);
MAX6675 tc2(thermo_CLK, thermo2_CS, thermo_DO);
const int dt_tc = 250; // 250ms minimum for MAX6675
unsigned long int last_time_tc = 0;

/// CONTROL ========================================================================
// Servos
PWMServo servo1; // Initialize servo1 object (fill)
PWMServo servo2; // Initialize servo2 object (vent)
PWMServo servo3; // Initialize servo3 object (mov)
PWMServo servo4; // Initialize servo4 object (extra)

// valve_states bit offset:
int FILL = 0;
int VENT = 1;
int MOV = 2;

// pyro_states bit offset:
int PY1 = 0;
int PY2 = 1;

// arm_state bit offset:
int ARM = 0;
int C1 = 1;
int C2 = 2;

// Loop timekeeping 
unsigned long int last_time_data = 0; // Last time data readings were taken (tracking for next read cycle) [ms]
unsigned long int last_time_rx = 0; // Last receive time (tracking rx for abort) [ms]

void moveServo(int servo, bool state){
  if(state == 0){
    if(servo == 1){bitWrite(daq_pkt.valve_states, FILL, 0); servo1.write(eeprom.servo1_close);}
    if(servo == 2){bitWrite(daq_pkt.valve_states, VENT, 0); servo2.write(eeprom.servo2_open);}
    if(servo == 3){bitWrite(daq_pkt.valve_states, MOV, 0); servo3.write(eeprom.servo3_close);}
    //if(servo == 4){bitWrite(disWord, FILL, 0); servo4.write(servo4off);}
  }else if(state == 1){
    if(servo == 1){bitWrite(daq_pkt.valve_states, FILL, 1); servo1.write(eeprom.servo1_open);}
    if(servo == 2){bitWrite(daq_pkt.valve_states, VENT, 1); servo2.write(eeprom.servo2_close);}
    if(servo == 3){bitWrite(daq_pkt.valve_states, MOV, 1); servo3.write(eeprom.servo3_open);}
    //if(servo == 4){servo4.write(servo4on);}
  }
}

void save_data() { // Save data to SD card
// "Time[ms],BATT[V],BATT_CURR[mA],TC1[F],TC2[F],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";
  // Open data file and write data, close data file
  //datafile = SD.open(filename.c_str(),FILE_WRITE);
  if (datafile) {
    datafile.print(millis());
    datafile.print(",");
    datafile.print(daq_pkt.batt_volts);
    datafile.print(",");
    datafile.print(daq_pkt.batt_current);
    datafile.print(",");
    datafile.print(daq_pkt.tc1);
    datafile.print(",");
    datafile.print(daq_pkt.tc2);
    datafile.print(",");
    datafile.print(daq_pkt.pt1);
    datafile.print(",");
    datafile.print(daq_pkt.pt2);
    datafile.print(",");
    datafile.print(daq_pkt.pt3);
    datafile.print(",");
    datafile.print(daq_pkt.pt4);
    datafile.print(",");
    datafile.print(daq_pkt.pt5);
    datafile.print(",");
    datafile.print(daq_pkt.pt6);
    datafile.print(",");
    datafile.print(daq_pkt.load_cell);
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.arm_state, C1));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.arm_state, C2));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.valve_states, FILL));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.valve_states, VENT));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.valve_states, MOV));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.arm_state, ARM));
    datafile.print(",");
    datafile.print(bitRead(daq_pkt.pyro_states, PY1));
    datafile.print(",");
    datafile.println(bitRead(daq_pkt.pyro_states, PY2));
    datafile.flush();
  }
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200); // serial data to/from arduino nano

  pinMode(pyro_1_fire, OUTPUT); digitalWrite(pyro_1_fire, LOW);
  pinMode(pyro_2_fire, OUTPUT); digitalWrite(pyro_2_fire, LOW);
  pinMode(pyro_1_cont_in, INPUT_PULLDOWN);
  pinMode(pyro_2_cont_in, INPUT_PULLDOWN);
  pinMode(arm_out, OUTPUT); digitalWrite(arm_out, HIGH);
  
  servo1.attach(servo_1_out); // Attach servo1
  servo2.attach(servo_2_out); // Attach servo2
  servo3.attach(servo_3_out); // Attach servo3
  servo4.attach(servo_4_out); // Attach servo4

  beginSD();

  servo1.write(eeprom.servo1_close); // Set servo1 safe state (fill)
  servo2.write(eeprom.servo2_open); // Set servo2 safe state (vent)
  servo3.write(eeprom.servo3_close); // Set servo3 safe state (mov)
  servo4.write(eeprom.servo4_close); // Set servo4 safe state (spare)
  
  // Start current sensor
  if (! ina219.begin()) {
    Serial.println("Failed to find INA219 chip");
  } else {
    Serial.println("INA219 init OK!");
    bitWrite(daq_pkt.sensor_states, 1, 1);
    ina219.setCalibration_32V_2A();
  }

  // start 16-bit ADC
  if (! ads1115.begin(0x49)) {
    Serial.println("Failed to find ADS1115 chip");
  } else {
    Serial.println("ADS1115 init OK!");
    bitWrite(daq_pkt.sensor_states, 2, 1);
  }

 // Radio transceiver set up
  pinMode(RADIO_LED, OUTPUT);
  digitalWrite(RADIO_LED, HIGH);
  delay(1000);
  digitalWrite(RADIO_LED, LOW);

  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  if (rf95.init()) {
    Serial.println("LoRa radio init OK!");

    // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
    if (rf95.setFrequency(RF95_FREQ)) {
      Serial.print("set frequency to "); Serial.println(RF95_FREQ);
    } else {
      Serial.println("setFrequency failed");
    }
    // you can set transmitter powers from 5 to 23 dBm:
    rf95.setTxPower(23, false);
    rf95.setSpreadingFactor(7);
    rf95.setSignalBandwidth(250000);  // 250kHz 
  } else {
    Serial.println("LoRa radio init FAILED!");
  }
  
  delay(1000); // delay for begin  

  datafile = SD.open(filename.c_str(), FILE_WRITE);
  if (!datafile) Serial.println("Failed to reopen datafile!");
}

void loop() {
  startLoopTime = micros();
  daq_pkt.timestamp = millis();
  
  // Read sensor data
  if (millis()-last_time_data > 1000/eeprom.SD_sample_rate) { // Check time between data readings

    // Check continuity
    if(analogRead(pyro_1_cont_in) > 500){
      bitWrite(daq_pkt.arm_state, C1, 1);
    } else {
      bitWrite(daq_pkt.arm_state, C1, 0);
    }
    
    if(analogRead(pyro_2_cont_in) > 500){
      bitWrite(daq_pkt.arm_state, C2, 1);
    } else {
      bitWrite(daq_pkt.arm_state, C2, 0);
    }

    daq_pkt.pt1 = ((ads1115.readADC_SingleEnded(0)*eeprom.pt1_c1) + eeprom.pt1_c0);
    daq_pkt.pt2 = ((ads1115.readADC_SingleEnded(1)*eeprom.pt2_c1) + eeprom.pt2_c0);
    daq_pkt.pt3 = ((ads1115.readADC_SingleEnded(2)*eeprom.pt3_c1) + eeprom.pt3_c0);
    daq_pkt.pt4 = ((ads1115.readADC_SingleEnded(3)*eeprom.pt4_c1) + eeprom.pt4_c0);
    daq_pkt.pt5 = 0; // DELETE
    daq_pkt.pt6 = 0; // DELETE

    daq_pkt.batt_volts = ina219.getBusVoltage_V() + 0.145;
    daq_pkt.batt_current = ina219.getCurrent_mA() + 48;


    // Fire pyros if armed and signal sent
    if(sw_pkt.arm == 1){
      digitalWrite(arm_out, HIGH);
      bitWrite(daq_pkt.arm_state, ARM, 1);
      if(sw_pkt.py1){
        bitWrite(daq_pkt.pyro_states, PY1, 1);
        digitalWrite(pyro_1_fire, HIGH);
      } else if (sw_pkt.py2){
        bitWrite(daq_pkt.pyro_states, PY2, 1);
        digitalWrite(pyro_2_fire, HIGH);
      } else {
        bitWrite(daq_pkt.pyro_states, PY1, 0);
        bitWrite(daq_pkt.pyro_states, PY2, 0);
        digitalWrite(pyro_1_fire, LOW);
        digitalWrite(pyro_2_fire, LOW);
      }
    } else {
      bitWrite(daq_pkt.arm_state, ARM, 0);
      bitWrite(daq_pkt.pyro_states, PY1, 0);
      bitWrite(daq_pkt.pyro_states, PY2, 0);
      digitalWrite(arm_out, LOW);
      digitalWrite(pyro_1_fire, LOW);
      digitalWrite(pyro_2_fire, LOW);
    }

    // Only move servos if state changes
    if (sw_pkt.fill != bitRead(daq_pkt.valve_states, FILL)) moveServo(1, sw_pkt.fill);
    if (sw_pkt.vent != bitRead(daq_pkt.valve_states, VENT)) moveServo(2, sw_pkt.vent);
    if (sw_pkt.mov  != bitRead(daq_pkt.valve_states, MOV)) moveServo(3, sw_pkt.mov);
    
    last_time_data = millis(); // Record time of data reading
    save_data(); // Save data
  }

  if (millis() - last_time_tc > dt_tc) {
    daq_pkt.tc1 = tc1.readFahrenheit();
    daq_pkt.tc2 = tc2.readFahrenheit();
    last_time_tc = millis();
  }
    

  // Debug print statements
  bool print_debug = true;
  if (print_debug && millis()-last_time_serial2 > 500) { 

    Serial.print("sending packet, time: "); Serial.print(daq_pkt.timestamp);
    Serial.print(", batt volts: "); Serial.print(daq_pkt.batt_volts);
    Serial.print(", current: "); Serial.print(daq_pkt.batt_current);
    Serial.print(", TC1: "); Serial.print(daq_pkt.tc1);
    Serial.print(", TC2: "); Serial.print(daq_pkt.tc2);
    Serial.print(", cont1: "); Serial.print(analogRead(pyro_1_cont_in));
    Serial.print(", cont2: "); Serial.print(analogRead(pyro_2_cont_in));
    Serial.print(", PT1: "); Serial.println(daq_pkt.pt1);



    last_time_serial2 = millis();
  }

  if (rf95.available()) {
      daq_pkt.RSSI = rf95.lastRssi();
      uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
      uint8_t len = sizeof(buf);

      if (rf95.recv(buf, &len)) {
          readRadioPacket(buf, len);
          send_pending = true;
      } else {
          digitalWrite(RADIO_LED, LOW);
      }
  }

  if (send_pending && !rf95.isChannelActive()) {
      handleTelemetry();
      send_pending = false;
  }

  if(sw_pkt.arm){
    tone(buzzerPin, 2300);
  } else {
    noTone(buzzerPin);
  }


  daq_pkt.tsy_looptime = micros() - startLoopTime;
}
