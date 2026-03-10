#include <SPI.h>
#include <Servo.h>
#include "HX711.h"
#include <SD.h>

#define servo_1_out  2 // fill
#define servo_2_out  3 // vent
#define servo_3_out  4 // mov
#define servo_4_out  5
#define servo_5_out  6
#define tsy_rx 7
#define tsy_tx 8
#define servo_6_out  9
#define spare_1  10
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


// Frame constants
#define TELEM_FRAME_START_0  0xAB
#define TELEM_FRAME_START_1  0xCD
#define CMD_FRAME_START_0    0xDE
#define CMD_FRAME_START_1    0xAD
#define FRAME_END_0          0xEF
#define FRAME_END_1          0xBE
#define FRAME_OVERHEAD       7       // 2START + 1CMD + 1LEN + 1CRC + 2END
#define MAX_PAYLOAD_LEN      128

// == Config ====================================================================
#define RX_BUF_SIZE     (MAX_PAYLOAD_LEN + FRAME_OVERHEAD)
#define UART_HANDLE     huart1
#define UART_TIMEOUT_MS 20

// == Telemetry TX staging ================================================================
static uint8_t   telem_buf[RX_BUF_SIZE];
static uint8_t   telem_len   = 0;
volatile uint8_t telem_ready = 0;

/// DATA ========================================================================
// SD Data Logging
int chipSelect = BUILTIN_SDCARD;
//const int SDCS = BUILTIN_SDCARD; // Use built in sd card for data logging
String filename; // Name of data file
File datafile; // Data file instance
String fileheader = "Time[ms],BATT[V],5V[V],RADIO[V],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2";

// Serial comms to arduino nano
const int dt_serial2 = 1000/60; // transmission speed [ms]
long int last_time_serial2 = 0;

struct __attribute__((packed)) TSY_Payload // Payload to arduino nano
{
  uint32_t timestamp = 0; 
  uint8_t valve_states = 0;
  uint8_t pyro_states = 0;
  uint8_t arm_state = 0;
  float pt1 = 0;
  float pt2 = 0;
  float pt3 = 0;
  float pt4 = 0;
  float pt5 = 0;
  float pt6 = 0;
  float load_cell = 0;
  float batt_volts = 0;
  float five_volts = 0;
  float radio_volts = 0;
};
TSY_Payload tsy_pkt;

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
const int dt_sd_slow = 1000; // Time between slow readings [ms]
int dt_data = dt_sd_slow; // Variable to use for dt between data readings
int dt_lc = dt_sd_slow; // Variable to use for dt between lc readings

int burn_time = 50000; // [ms] burn time
unsigned long int burn_start = 0;
bool burn_started = 0;
bool burn_ended = 0;

void moveServo(int servo, bool state){
  if(state == 0){
    if(servo == 1){bitWrite(tsy_pkt.valve_states, FILL, 0); servo1.write(servo1off);}
    if(servo == 2){bitWrite(tsy_pkt.valve_states, VENT, 0); servo2.write(servo2off);}
    if(servo == 3){bitWrite(tsy_pkt.valve_states, MOV, 0); servo3.write(servo3off);}
    //if(servo == 4){bitWrite(disWord, FILL, 0); servo4.write(servo4off);}
  }else if(state == 1){
    if(servo == 1){bitWrite(tsy_pkt.valve_states, FILL, 1); servo1.write(servo1on);}
    if(servo == 2){bitWrite(tsy_pkt.valve_states, VENT, 1); servo2.write(servo2on);}
    if(servo == 3){bitWrite(tsy_pkt.valve_states, MOV, 1); servo3.write(servo3on);}
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
    datafile.print(bitRead(tsy_pkt.arm_state, C1));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.arm_state, C2));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.valve_states, FILL));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.valve_states, VENT));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.valve_states, MOV));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.arm_state, ARM));
    datafile.print(",");
    datafile.print(bitRead(tsy_pkt.pyro_states, PY1));
    datafile.print(",");
    datafile.println(bitRead(tsy_pkt.pyro_states, PY2));
    datafile.close();
  }
}

static uint8_t crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    while (len--) crc ^= *data++;
    return crc;
}

void send2nano(uint8_t start0, uint8_t start1, uint8_t resp_id, const void *payload, uint8_t payload_len) {
    uint8_t *buf;
    uint8_t *len_ptr;
    volatile uint8_t *ready_ptr;
    
    buf       = telem_buf;
    len_ptr   = &telem_len;
    ready_ptr = &telem_ready;

    uint8_t i = 0;
    buf[i++] = start0;
    buf[i++] = start1;
    buf[i++] = resp_id;
    buf[i++] = payload_len;

    if (payload_len > 0 && payload != NULL) {
        memcpy(&buf[i], payload, payload_len);
        i += payload_len;
    }

    buf[i++] = crc8(&buf[2], 2 + payload_len);
    buf[i++] = FRAME_END_0;
    buf[i++] = FRAME_END_1;

    Serial2.write(buf, i);
    last_time_serial2 = millis(); // save new time of most recent transmission

    *len_ptr   = i;
    *ready_ptr = 1;
}

void setup() {
  Serial.begin(9600);
  Serial2.begin(115200); // serial data to/from arduino nano

  pinMode(batt_volt_mon, INPUT);
  pinMode(five_volt_mon, INPUT);
  pinMode(radio_volt_mon, INPUT);

  pinMode(pyro_1_fire, OUTPUT); digitalWrite(pyro_1_fire, HIGH);
  pinMode(pyro_2_fire, OUTPUT); digitalWrite(pyro_2_fire, HIGH);
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
  tsy_pkt.timestamp = millis();
  
  if (millis()-last_time_lc > dt_lc) { // Check time between LC readings
    LC1float = lc1.get_units(); // Load cell 1 
    tsy_pkt.load_cell = LC1float;
    analogWrite(lc_out_low, lowByte(int8_t(LC1float)));
    analogWrite(lc_out_high, highByte(int8_t(LC1float))); 
    last_time_lc = tsy_pkt.timestamp;  // Record time of load cell reading
  }  

  // Read sensor data
  if (millis()-last_time_data > dt_data) { // Check time between data readings
    if(analogRead(pyro_1_cont_in) > 100){
      bitWrite(tsy_pkt.arm_state, C1, 1);
    } else {
      bitWrite(tsy_pkt.arm_state, C1, 0);
    }
    
    if(analogRead(pyro_2_cont_in) > 100){
      bitWrite(tsy_pkt.arm_state, C2, 1);
    } else {
      bitWrite(tsy_pkt.arm_state, C2, 0);
    }

    PT1int = analogRead(pt_1); PT1float = (PT1int*PT1coeff) + PT1gain; tsy_pkt.pt1 = PT1float;
    PT2int = analogRead(pt_2); PT2float = (PT2int*PT2coeff) + PT2gain; tsy_pkt.pt2 = PT2float;
    PT3int = analogRead(pt_3); PT3float = (PT3int*PT3coeff) + PT3gain; tsy_pkt.pt3 = PT3float;
    PT4int = analogRead(pt_4); PT4float = (PT4int*PT4coeff) + PT4gain; tsy_pkt.pt4 = PT4float;
    PT5int = analogRead(pt_5); PT5float = (PT5int*PT5coeff) + PT5gain; tsy_pkt.pt5 = PT5float;
    PT6int = analogRead(pt_6); PT6float = (PT6int*PT6coeff) + PT6gain; tsy_pkt.pt6 = PT6float;

    batt_volt = analogRead(batt_volt_mon) * 0.01700550500;
    five_volt = analogRead(five_volt_mon) * 0.00518084066471;
    radio_volt = analogRead(radio_volt_mon) * 0.00387096774194;

    tsy_pkt.batt_volts = batt_volt;
    tsy_pkt.five_volts  = five_volt;
    tsy_pkt.radio_volts = radio_volt;
    

    
    // Fire pyros if armed and signal sent
    if(digitalRead(arm_in) == 1){
      bitWrite(tsy_pkt.arm_state, ARM, 1);
      dt_data = dt_data_fast;
      dt_lc = dt_lc_fast;
      if(digitalRead(pyro_1_fire_in)){
        bitWrite(tsy_pkt.pyro_states, PY1, 1);
        digitalWrite(pyro_1_fire, LOW);
        digitalWrite(pyro_2_fire, LOW);
      } else if (digitalRead(pyro_2_fire_in)){
        bitWrite(tsy_pkt.pyro_states, PY2, 1);
        digitalWrite(pyro_1_fire, LOW);
        digitalWrite(pyro_2_fire, LOW);
      } else {
        bitWrite(tsy_pkt.pyro_states, PY1, 0);
        bitWrite(tsy_pkt.pyro_states, PY2, 0);
        digitalWrite(pyro_1_fire, HIGH);
        digitalWrite(pyro_2_fire, HIGH);
      }
    } else {
      dt_data = dt_sd_slow;
      dt_lc = dt_sd_slow;
      bitWrite(tsy_pkt.arm_state, ARM, 0);
      bitWrite(tsy_pkt.pyro_states, PY1, 0);
      bitWrite(tsy_pkt.pyro_states, PY2, 0);
      digitalWrite(pyro_1_fire, HIGH);
      digitalWrite(pyro_2_fire, HIGH);
    }


    moveServo(1, digitalRead(fill_in));
    moveServo(2, digitalRead(vent_in));


    moveServo(3, digitalRead(mov_in));


    // This limits the burn time to set variable 'burn_time'
    if(digitalRead(pyro_1_fire_in) || digitalRead(pyro_2_fire_in)){ // If pyros fired, or burn started 
      if(digitalRead(mov_in) == 1){
        if(burn_started == 0){ // Need to get start time of burn, only when MOV is open
          burn_start = millis();
          burn_started = 1;
        }
      }
    }
    if(burn_started == 1){
      if(millis() - burn_start >= burn_time){ // close mov when burn time elapsed
        moveServo(3, 0);
        burn_start = 0;
        burn_started == 0;
      }
    }
    


    


    last_time_nano = millis();
    last_time_data = millis(); // Record time of data reading
    save_data(); // Save data
  }

  // Send packet to nano if ready
  if (millis()-last_time_serial2 > dt_serial2) { 

    Serial.print("sending packet, time: "); Serial.print(tsy_pkt.timestamp);
    Serial.print(", batt volts: "); Serial.print(tsy_pkt.batt_volts);
    Serial.print(", 5 volts: "); Serial.print(tsy_pkt.five_volts);
    Serial.print(", PT1: "); Serial.println(tsy_pkt.pt1);
    
    send2nano(TELEM_FRAME_START_0, TELEM_FRAME_START_1, 0x69, &tsy_pkt, sizeof(tsy_pkt));


  }



}
