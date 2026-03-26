#include <SPI.h>
#include <Servo.h>
#include "HX711.h"
#include <SD.h>
#include <Adafruit_INA219.h>
#include "max6675.h"
#include <RH_RF95.h>

#define thermo1_DO  0
#define thermo1_CS  1
#define servo_1_out  2 // fill
#define servo_2_out  3 // vent
#define servo_3_out  4 // mov
#define servo_4_out  5
#define servo_5_out  6
#define tsy_rx 7    // DELETE
#define tsy_tx 8    // DELETE
#define RFM95_RST  9
#define RFM95_CS 10
#define lc_out_low  11
#define lc_out_high  12

#define pt_3  16
#define pt_4  17
#define pyro_1_cont_in  36
#define pyro_2_cont_in  37
#define pt_5  20
#define pt_6  21

#define thermo2_DO  22
#define thermo2_CS  23
#define pt_1  24           // EDIT
#define pt_2  25           // EDIT
#define five_volt_mon  26    // DELETE
#define radio_volt_mon  27    // DELETE

#define RFM95_INT 28
#define thermo_CLK  30

#define pyro_2_fire  33
#define pyro_1_fire  34

#define pyro_2_fire_in  31    // DELETE
#define pyro_1_fire_in  32    // DELETE
#define mov_in  38    // DELETE
#define vent_in  39    // DELETE
#define fill_in  40    // DELETE
#define RADIO_LED  41  


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

struct __attribute__((packed)) DAQ_Payload // Payload to arduino nano
{
  uint32_t timestamp = 0; 
  uint8_t valve_states = 0;
  uint8_t pyro_states = 0;
  uint8_t arm_state = 0;
  uint8_t sensor_states = 0; // 0 = SD card, 1 = INA219
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

// Load Cell
//HX711 lc1; // Initialize HX711 object for load cell
float calibration_factor = -2053.61580134;// Tension load cell
//float LC_Calibration = -4100; // Load cell calibration factor (see LC_CALIBRATION.ino for getting this value)
float LC1float = 0.0; // float value of load cell reading

// Voltage Monitors
float radio_volt;
float five_volt;
float batt_volt;

// Current sensor
Adafruit_INA219 ina219;

// Thermocouple sensor
MAX6675 tc1(thermo_CLK, thermo1_CS, thermo1_DO);
MAX6675 tc2(thermo_CLK, thermo2_CS, thermo2_DO);
const int dt_tc = 250; // 250ms minimum for MAX6675
unsigned long int last_time_tc = 0;

/// CONTROL ========================================================================
// Servos
int servoopen = 67; // Servo open state (angle) [degrees]
int servoclose = 0; // Servo close state (angle) [degrees]

int servoopen_mini = 90; // Servo open state (angle) [degrees]
int servoclose_mini = 0; // Servo close state (angle) [degrees]

int servo1_trim = 5;
int servo2_trim = 10;
int servo3_trim = 5;
int servo4_trim = 9;


Servo servo1; // Initialize servo1 object (fill)
bool servo1_bool = 0;
int servo1on = servoclose + servo1_trim; // Dectuated state of servo1
int servo1off = servoopen + servo1_trim; // Actuated state of servo1

Servo servo2; // Initialize servo2 object (vent)
bool servo2_bool = 0;
int servo2on = servoclose_mini + servo2_trim; // Actuated state of servo2
int servo2off = servoopen_mini + servo2_trim; // Dectuated state of servo2

Servo servo3; // Initialize servo3 object (mov)
bool servo3_bool = 0;
int servo3on = servoclose_mini + servo3_trim; // Dectuated state of servo3
int servo3off = servoopen_mini + servo3_trim; // Actuated state of servo3

Servo servo4; // Initialize servo4 object (extra)
bool servo4_bool = 0;
int servo4on = servoclose + servo4_trim; // Dectuated state of servo4
int servo4off = servoopen + servo4_trim; // Actuated state of servo4

int PT1int = 0; // int value of PT1 reading (fill)
float PT1float = 0;
float PT1coeff = 2.536967997; float PT1gain = -110.1199292;

int PT2int = 0; // int value of PT2 reading (ox injector)
float PT2float = 0;
float PT2coeff = 2.540186886; float PT2gain = -112.1752796;

int PT3int = 0; // int value of PT3 reading (combustion chamber)
float PT3float = 0;
float PT3coeff = 2.463810563; float PT3gain = -115.7383118;

int PT4int = 0; // int value of PT4 reading (tank)
float PT4float = 0;
float PT4coeff = 2.524649427; float PT4gain = -106.53278;

// int value of PT5 reading (extra)
int PT5int = 0; 
float PT5float = 0;
float PT5coeff = 0; float PT5gain = 0;

int PT6int = 0; // int value of PT6 reading (extra)
float PT6float = 0;
float PT6coeff = 0; float PT6gain = 0;

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
const int dt_abort = 120*1000; // Time to abort if no signal received [ms] (120 seconds)
unsigned long int last_time_rx = 0; // Last receive time (tracking rx for abort) [ms]
const int dt_data_fast = 10; // Time between data readings [ms]
unsigned long int last_time_data = 0; // Last time data readings were taken (tracking for next read cycle) [ms]
unsigned long int last_time_nano = 0;
const int dt_lc_fast = 10; // Time between LC readings [ms]
unsigned long int last_time_lc = 0; // Last time LC readings were taken (tracking for next read cycle) [ms]

int dt_data = 1000/10; // Variable to use for dt between data readings
int dt_lc = 1000; // Variable to use for dt between lc readings

int burn_time = 50000; // [ms] burn time
unsigned long int burn_start = 0;
bool burn_started = 0;
bool burn_ended = 0;

void moveServo(int servo, bool state){
  if(state == 0){
    if(servo == 1){bitWrite(daq_pkt.valve_states, FILL, 0); servo1.write(servo1off);}
    if(servo == 2){bitWrite(daq_pkt.valve_states, VENT, 0); servo2.write(servo2off);}
    if(servo == 3){bitWrite(daq_pkt.valve_states, MOV, 0); servo3.write(servo3off);}
    //if(servo == 4){bitWrite(disWord, FILL, 0); servo4.write(servo4off);}
  }else if(state == 1){
    if(servo == 1){bitWrite(daq_pkt.valve_states, FILL, 1); servo1.write(servo1on);}
    if(servo == 2){bitWrite(daq_pkt.valve_states, VENT, 1); servo2.write(servo2on);}
    if(servo == 3){bitWrite(daq_pkt.valve_states, MOV, 1); servo3.write(servo3on);}
    //if(servo == 4){servo4.write(servo4on);}
  }
}

void save_data() { // Save data to SD card
// "Time[ms],BATT[V],BATT_CURR[mA],TC1[F],TC2[F],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";
  // Open data file and write data, close data file
  datafile = SD.open(filename.c_str(),FILE_WRITE);
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
    datafile.print(PT1float);
    datafile.print(",");
    datafile.print(PT2float);
    datafile.print(",");
    datafile.print(PT3float);
    datafile.print(",");
    datafile.print(PT4float);
    datafile.print(",");
    datafile.print(PT5float);
    datafile.print(",");
    datafile.print(PT6float);
    datafile.print(",");
    datafile.print(LC1float);
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
    datafile.close();
  }
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200); // serial data to/from arduino nano

  pinMode(five_volt_mon, INPUT);
  pinMode(radio_volt_mon, INPUT);

  pinMode(pyro_1_fire, OUTPUT); digitalWrite(pyro_1_fire, HIGH);
  pinMode(pyro_2_fire, OUTPUT); digitalWrite(pyro_2_fire, HIGH);
  pinMode(pyro_1_cont_in, INPUT_PULLDOWN);
  pinMode(pyro_2_cont_in, INPUT_PULLDOWN);
  pinMode(pyro_1_fire_in, INPUT);
  pinMode(pyro_2_fire_in, INPUT);
  
  servo1.attach(servo_1_out); // Attach servo1
  servo2.attach(servo_2_out); // Attach servo2
  servo3.attach(servo_3_out); // Attach servo3
  servo4.attach(servo_4_out); // Attach servo4

  servo1.write(servo1off); // Set servo1 safe state (fill)
  servo2.write(servo2on); // Set servo2 safe state (vent)
  servo3.write(servo3off); // Set servo3 safe state (mov)
  servo4.write(servo4off); // Set servo4 safe state (extra)

  pinMode(mov_in, INPUT);
  pinMode(fill_in, INPUT);
  pinMode(vent_in, INPUT);

  pinMode(pt_1, INPUT);
  pinMode(pt_2, INPUT);
  pinMode(pt_3, INPUT);
  pinMode(pt_4, INPUT);
  pinMode(pt_5, INPUT);
  pinMode(pt_6, INPUT);

  // SD card set up
  if (!SD.begin(BUILTIN_SDCARD)) { // If SD start unsuccessful
    Serial.println("SD Card initalize.. Failed");
  } else { // If SD start successful
  Serial.println("SD card init OK!");
    bitWrite(daq_pkt.sensor_states, 0, 1);
    int i = 0;
    filename = "data"+String(i)+".csv"; // Generate a unique filename
    while (SD.exists(filename.c_str())) { // Check if the filename already exists
      i += 1; // increase filename number
      filename = "data"+String(i)+".csv"; // Generate a new filename
    }
    Serial.println("Logging data to " + filename);
    datafile = SD.open(filename.c_str(),FILE_WRITE); // Open data file
    if (datafile) { // If datafile open
      datafile.println(fileheader); // Write file header
      datafile.close(); // Always close file
    }
  }  

  // Start current sensor
  if (! ina219.begin()) {
    Serial.println("Failed to find INA219 chip");
  } else {
    Serial.println("INA219 init OK!");
    bitWrite(daq_pkt.sensor_states, 1, 1);
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
    rf95.setTxPower(10, false);
    rf95.setSpreadingFactor(7);
    rf95.setSignalBandwidth(250000);  // 250kHz 
  } else {
    Serial.println("LoRa radio init FAILED!");
  }
  


  delay(1000); // delay for begin  
}

void loop() {
  startLoopTime = micros();
  daq_pkt.timestamp = millis();
  
  // DELETE
  if (millis()-last_time_lc > dt_lc) { // Check time between LC readings
    //LC1float = lc1.get_units(); // Load cell 1 
    daq_pkt.load_cell = LC1float;
    //analogWrite(lc_out_low, lowByte(int8_t(LC1float)));
    //analogWrite(lc_out_high, highByte(int8_t(LC1float))); 
    last_time_lc = daq_pkt.timestamp;  // Record time of load cell reading
  }  

  // Read sensor data
  if (millis()-last_time_data > dt_data) { // Check time between data readings
    if(analogRead(pyro_1_cont_in) > 100){
      bitWrite(daq_pkt.arm_state, C1, 1);
    } else {
      bitWrite(daq_pkt.arm_state, C1, 0);
    }
    
    if(analogRead(pyro_2_cont_in) > 100){
      bitWrite(daq_pkt.arm_state, C2, 1);
    } else {
      bitWrite(daq_pkt.arm_state, C2, 0);
    }

    PT1int = analogRead(pt_1); PT1float = (PT1int*PT1coeff) + PT1gain; daq_pkt.pt1 = PT1float;
    PT2int = analogRead(pt_2); PT2float = (PT2int*PT2coeff) + PT2gain; daq_pkt.pt2 = PT2float;
    PT3int = analogRead(pt_3); PT3float = (PT3int*PT3coeff) + PT3gain; daq_pkt.pt3 = PT3float;
    PT4int = analogRead(pt_4); PT4float = (PT4int*PT4coeff) + PT4gain; daq_pkt.pt4 = PT4float;
    PT5int = analogRead(pt_5); PT5float = (PT5int*PT5coeff) + PT5gain; daq_pkt.pt5 = PT5float;
    PT6int = analogRead(pt_6); PT6float = (PT6int*PT6coeff) + PT6gain; daq_pkt.pt6 = PT6float;

    daq_pkt.batt_volts = ina219.getBusVoltage_V();
    daq_pkt.batt_current = ina219.getCurrent_mA();


    // Fire pyros if armed and signal sent
    if(sw_pkt.arm == 1){
      bitWrite(daq_pkt.arm_state, ARM, 1);
      dt_data = dt_data_fast;
      dt_lc = dt_lc_fast;
      if(sw_pkt.py1){
        bitWrite(daq_pkt.pyro_states, PY1, 1);
        digitalWrite(pyro_1_fire, LOW);
      } else if (sw_pkt.py2){
        bitWrite(daq_pkt.pyro_states, PY2, 1);
        digitalWrite(pyro_2_fire, LOW);
      } else {
        bitWrite(daq_pkt.pyro_states, PY1, 0);
        bitWrite(daq_pkt.pyro_states, PY2, 0);
        digitalWrite(pyro_1_fire, HIGH);
        digitalWrite(pyro_2_fire, HIGH);
      }
    } else {
      bitWrite(daq_pkt.arm_state, ARM, 0);
      bitWrite(daq_pkt.pyro_states, PY1, 0);
      bitWrite(daq_pkt.pyro_states, PY2, 0);
      digitalWrite(pyro_1_fire, HIGH);
      digitalWrite(pyro_2_fire, HIGH);
    }


    moveServo(1, sw_pkt.fill);
    moveServo(2, sw_pkt.vent);
    moveServo(3, sw_pkt.mov);
    
    last_time_nano = millis();
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
    Serial.print(", TC1: "); Serial.print(daq_pkt.tc1); Serial.print(", raw TC1: "); Serial.print(tc1.readFahrenheit()); 
    Serial.print(", TC2: "); Serial.print(daq_pkt.tc2); Serial.print(", raw TC2: "); Serial.print(tc2.readFahrenheit()); 
    Serial.print(", PT1: "); Serial.println(daq_pkt.pt1);

    last_time_serial2 = millis();
  }

  if (rf95.available()) {

    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);

    if (rf95.recv(buf, &len)) {
      readRadioPacket(buf, len);
      handleTelemetry();
    } else {
      //Serial.println("Receive failed");
      digitalWrite(RADIO_LED, LOW);
    }
    // DECODE SWITCH STATE ====================================================================================================
    //decodestate(sw_pkt); // Call function to decode switchstate and issue control commands
      
    
  }


  daq_pkt.tsy_looptime = micros() - startLoopTime;
}
