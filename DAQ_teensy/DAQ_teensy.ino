#include <SPI.h>
#include <Servo.h>
#include "HX711.h"
#include <SD.h>

#define servo_1_out  2 // fill
#define servo_2_out  3 // vent
#define servo_3_out  4 // mov
#define servo_4_out  5
#define servo_5_out  6
#define servo_6_out  7
#define spare_1  8
#define pyro_1_cont_out  9
#define pyro_2_cont_out  10
#define lc_out_low  11
#define lc_out_high  12
#define load_cell_sck  13
#define pt_1  14
#define pt_2  15
#define pt_3  16
#define pt_4  17
#define pyro_1_cont_in  18
#define pyro_2_cont_in  19
#define pt_5  20
#define pt_6  21
#define batt_volt_mon  23
#define load_cell_dat  24
#define spare_2  25
#define five_volt_mon  26
#define radio_volt_mon  27
#define pyro_2_fire  33
#define pyro_1_fire  34
#define pyro_2_fire_in  36
#define pyro_1_fire_in  37
#define mov_in  38
#define vent_in  39
#define fill_in  40
#define arm_in  41
/// DATA ========================================================================
// SD Data Logging
int chipSelect = BUILTIN_SDCARD;
//const int SDCS = BUILTIN_SDCARD; // Use built in sd card for data logging
String filename; // Name of data file
File datafile; // Data file instance
String fileheader = "Time[ms],BATT[V],5V[V],RADIO[V],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";

// Load Cell
HX711 lc1; // Initialize HX711 object for load cell
float calibration_factor = -2053.61580134;// Tension load cell
//float LC_Calibration = -4100; // Load cell calibration factor (see LC_CALIBRATION.ino for getting this value)
float LC1float = 0.0; // float value of load cell reading

// Voltage Monitors
float radio_volt;
float five_volt;
float batt_volt;

/// CONTROL ========================================================================
// Servos
int servoopen = 67; // Servo open state (angle) [degrees]
int servoclose = 0; // Servo close state (angle) [degrees]

int servo1_trim = 5;
int servo2_trim = 5;
int servo3_trim = 5;
int servo4_trim = 9;


Servo servo1; // Initialize servo1 object (fill)
bool servo1_bool = 0;
int servo1on = servoclose + servo1_trim; // Dectuated state of servo1
int servo1off = servoopen + servo1_trim; // Actuated state of servo1

Servo servo2; // Initialize servo2 object (vent)
bool servo2_bool = 0;
int servo2on = servoclose + servo2_trim; // Actuated state of servo2
int servo2off = servoopen + servo2_trim; // Dectuated state of servo2

Servo servo3; // Initialize servo3 object (mov)
bool servo3_bool = 0;
int servo3on = servoclose + servo3_trim; // Dectuated state of servo3
int servo3off = servoopen + servo3_trim; // Actuated state of servo3

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

// 8bit Discrete Positions:
byte disWord = B00000000;
int C1 = 0;
int C2 = 1;
int FILL = 2;
int VENT = 3;
int MOV = 4;
int ARM = 5;
int PY1 = 6;
int PY2 = 7;

// Loop timekeeping 
const int dt_abort = 120*1000; // Time to abort if no signal received [ms] (120 seconds)
unsigned long int last_time_rx = 0; // Last receive time (tracking rx for abort) [ms]
const int dt_data_fast = 10; // Time between data readings [ms]
unsigned long int last_time_data = 0; // Last time data readings were taken (tracking for next read cycle) [ms]
unsigned long int last_time_nano = 0;
const int dt_lc_fast = 10; // Time between LC readings [ms]
unsigned long int last_time_lc = 0; // Last time LC readings were taken (tracking for next read cycle) [ms]
const int dt_sd_slow = 1000; // Time between slow readings [ms]
int dt_data = dt_sd_slow; // Variable to use for dt between data readings
int dt_lc = dt_sd_slow; // Variable to use for dt between lc readings

void moveServo(int servo, bool state){
  if(state == 0){
    if(servo == 1){bitWrite(disWord, FILL, 0); servo1.write(servo1off);}
    if(servo == 2){bitWrite(disWord, VENT, 0); servo2.write(servo2off);}
    if(servo == 3){bitWrite(disWord, MOV, 0); servo3.write(servo3off);}
    //if(servo == 4){bitWrite(disWord, FILL, 0); servo4.write(servo4off);}
  }else if(state == 1){
    if(servo == 1){bitWrite(disWord, FILL, 1); servo1.write(servo1on);}
    if(servo == 2){bitWrite(disWord, VENT, 1); servo2.write(servo2on);}
    if(servo == 3){bitWrite(disWord, MOV, 1); servo3.write(servo3on);}
    //if(servo == 4){servo4.write(servo4on);}
  }
}

void save_data() { // Save data to SD card
// "Time[ms],BATT[V],5V[V],RADIO[V],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";
  // Open data file and write data, close data file
  datafile = SD.open(filename.c_str(),FILE_WRITE);
  if (datafile) {
    datafile.print(millis());
    datafile.print(",");
    datafile.print(batt_volt);
    datafile.print(",");
    datafile.print(five_volt);
    datafile.print(",");
    datafile.print(radio_volt);
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
    datafile.print(bitRead(disWord, C1));
    datafile.print(",");
    datafile.print(bitRead(disWord, C2));
    datafile.print(",");
    datafile.print(bitRead(disWord, FILL));
    datafile.print(",");
    datafile.print(bitRead(disWord, VENT));
    datafile.print(",");
    datafile.print(bitRead(disWord, MOV));
    datafile.print(",");
    datafile.print(bitRead(disWord, ARM));
    datafile.print(",");
    datafile.print(bitRead(disWord, PY1));
    datafile.print(",");
    datafile.println(bitRead(disWord, PY2));
    datafile.close();
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(batt_volt_mon, INPUT);
  pinMode(five_volt_mon, INPUT);
  pinMode(radio_volt_mon, INPUT);

  pinMode(pyro_1_fire, OUTPUT); digitalWrite(pyro_1_fire, HIGH);
  pinMode(pyro_2_fire, OUTPUT); digitalWrite(pyro_2_fire, HIGH);
  pinMode(pyro_1_cont_out, OUTPUT); digitalWrite(pyro_1_cont_out, LOW);
  pinMode(pyro_2_cont_out, OUTPUT); digitalWrite(pyro_2_cont_out, LOW);
  pinMode(pyro_1_cont_in, INPUT_PULLDOWN);
  pinMode(pyro_2_cont_in, INPUT_PULLDOWN);
  pinMode(pyro_1_fire_in, INPUT);
  pinMode(pyro_2_fire_in, INPUT);

  pinMode(lc_out_low, OUTPUT);
  pinMode(lc_out_high, OUTPUT);
   
  lc1.begin(load_cell_dat,load_cell_sck); // Load cell pins
  long zero_factor = lc1.read_average(); //Get a baseline reading
  lc1.set_scale(calibration_factor); //Adjust to this calibration factor
  lc1.tare(); // Tare to zero load cell reading 
  
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
  pinMode(arm_in, INPUT);

  pinMode(pt_1, INPUT);
  pinMode(pt_2, INPUT);
  pinMode(pt_3, INPUT);
  pinMode(pt_4, INPUT);
  pinMode(pt_5, INPUT);
  pinMode(pt_6, INPUT);

  // SD card set up
  if (!SD.begin(BUILTIN_SDCARD)) { // If SD start unsuccessful
    Serial.println("SD Card initalize.. Failed");
    while (1) {} // Hang
  } else { // If SD start successful
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
  delay(1000); // delay for begin  
}

void loop() {
  if (millis()-last_time_lc > dt_lc) { // Check time between LC readings
    LC1float = lc1.get_units(); // Load cell 1 
    analogWrite(lc_out_low, lowByte(int8_t(LC1float)));
    analogWrite(lc_out_high, highByte(int8_t(LC1float))); 
    last_time_lc = millis();  // Record time of load cell reading
  }  

  // Read sensor data
  if (millis()-last_time_data > dt_data) { // Check time between data readings
    if(analogRead(pyro_1_cont_in) > 100){
      bitWrite(disWord, C1, 1);
      digitalWrite(pyro_1_cont_out, HIGH);
    } else {
      bitWrite(disWord, C1, 0);
      digitalWrite(pyro_1_cont_out, LOW);
    }
    
    if(analogRead(pyro_2_cont_in) > 100){
      bitWrite(disWord, C2, 1);
      digitalWrite(pyro_2_cont_out, HIGH);
    } else {
      bitWrite(disWord, C2, 0);
      digitalWrite(pyro_2_cont_out, LOW);
    }

    PT1int = analogRead(pt_1); PT1float = (PT1int*PT1coeff) + PT1gain;
    PT2int = analogRead(pt_2); PT2float = (PT2int*PT2coeff) + PT2gain;
    PT3int = analogRead(pt_3); PT3float = (PT3int*PT3coeff) + PT3gain;
    PT4int = analogRead(pt_4); PT4float = (PT4int*PT4coeff) + PT4gain;
    PT5int = analogRead(pt_5); PT5float = (PT5int*PT5coeff) + PT5gain;
    PT6int = analogRead(pt_6); PT6float = (PT6int*PT6coeff) + PT6gain;

    batt_volt = analogRead(batt_volt_mon) * 0.01700550500;
    five_volt = analogRead(five_volt_mon) * 0.00518084066471;
    radio_volt = analogRead(radio_volt_mon) * 0.00387096774194;
    
    moveServo(1, digitalRead(fill_in));
    moveServo(2, digitalRead(vent_in));
    moveServo(3, digitalRead(mov_in));
    
    // Fire pyros if armed and signal sent
    if(digitalRead(arm_in) == 1){
      bitWrite(disWord, ARM, 1);
      dt_data = dt_data_fast;
      dt_lc = dt_lc_fast;
      if(digitalRead(pyro_1_fire_in)){
        bitWrite(disWord, PY1, 1);
        digitalWrite(pyro_1_fire, LOW);
        digitalWrite(pyro_2_fire, LOW);
      } else if (digitalRead(pyro_2_fire_in)){
        bitWrite(disWord, PY2, 1);
        digitalWrite(pyro_1_fire, LOW);
        digitalWrite(pyro_2_fire, LOW);
      } else {
        bitWrite(disWord, PY1, 0);
        bitWrite(disWord, PY2, 0);
        digitalWrite(pyro_1_fire, HIGH);
        digitalWrite(pyro_2_fire, HIGH);
      }
    } else {
      dt_data = dt_sd_slow;
      dt_lc = dt_sd_slow;
      bitWrite(disWord, ARM, 0);
      bitWrite(disWord, PY1, 0);
      bitWrite(disWord, PY2, 0);
      digitalWrite(pyro_1_fire, HIGH);
      digitalWrite(pyro_2_fire, HIGH);
    }
    last_time_nano = millis();
    last_time_data = millis(); // Record time of data reading
    save_data(); // Save data
  }
}
