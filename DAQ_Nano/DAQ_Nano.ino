// DAQ

#include <SPI.h>
#include "printf.h"
#include <RH_RF95.h>

//Pins
#define CP2  0
#define CP1  1
#define RFM95_INT 2
#define buzzerPin 3
#define fill_out  4
#define vent_out  5
#define mov_out  6
#define pyro_1_fire  7
#define pyro_2_fire  8
#define RFM95_CS 9
#define RFM95_RST 10
// pin 14 spare
#define PT_TANK 20
#define RADIO_LED 16
#define lc_low_in 17
#define lc_high_in 18
#define arm_out 19
// pin 20 spare
#define batt_volt_mon  21

int PT_tank = 0; // int value of PT1 reading (tank ullage)
int LCint = 0; // int value of load cell reading 
bool C1bool = 0;
bool C2bool = 0;
int batt_volt;
int lc_low = 0;
int lc_high = 0;

// Loop timekeeping 
const int dt_abort = 120*1000; // Time to abort if no signal received [ms] (120 seconds)
unsigned long int last_time_rx = 0; // Last receive time (tracking rx for abort) [ms]
const int dt_rx_slow = 1000; // Time between radio readings [ms]
const int dt_rx_fast = 0; // Time between radio readings [ms]
const int dt_data_fast = 10; // Time between data readings [ms]
unsigned long int last_time_data = 0; // Last time data readings were taken (tracking for next read cycle) [ms]
unsigned long int last_time_teensy = 0;
const int dt_lc_fast = 100; // Time between LC readings [ms]
unsigned long int last_time_lc = 0; // Last time LC readings were taken (tracking for next read cycle) [ms]
const int dt_sd_slow = 1000; // Time between slow readings [ms]
int dt_data = dt_sd_slow; // Variable to use for dt between data readings
int dt_lc = dt_sd_slow; // Variable to use for dt between lc readings
int dt_rx = dt_rx_slow; // Time between radio readings [ms]

/// WIRELESS ========================================================================
// Radio Transceiver

#define RF95_FREQ 433.9869
RH_RF95 rf95(RFM95_CS, RFM95_INT);

struct Switch_Payload // Payload from switchbox [9 bytes total payload size]
{
  bool FILL = 0; // Switch 1 state on switchbox [1 byte]
  bool VENT = 0; // Switch 2 state on switchbox [1 byte]
  bool MOV = 0; // Switch 3 state on switchbox [1 byte]
  bool SW4 = 0; // Switch 4 state on switchbox [1 byte]
  bool PYRO1 = 0; // Button 1 state on switchbox [1 byte]
  bool PYRO2 = 0; // Button 2 state on switchbox [1 byte]
  bool BU3 = 0; // Button 3 state on switchbox [1 byte]
  bool BU4 = 0; // Button 4 state on switchbox [1 byte]
  bool ARM = 0; // Switch D state on switchbox [1 byte]
};

struct DAQ_Payload // ACK Payload to send back to switchbox [16 bytes total payload size]
{
  bool CC1 = 0; // Continuity channel 1 [1 byte]
  bool CC2 = 0; // Continuity channel 2 [1 byte]
  char PTC1[5] = {}; // PT channel 1 reading (tank) (format: 0000) [5 bytes]
  char LC1[7] = {}; // Load Cell reading (format: 0000.0) [7 bytes] 
};

Switch_Payload switchstate; // Initialize switchbox payload struct
DAQ_Payload daqstate; // Initialize daq payload struct
bool testRelay = 0;
float teensy_packet;


/// FUNCTIONS ========================================================================

void decodestate(Switch_Payload switchstate) { // SWITCH DECODER ====================================================== 
  if(switchstate.FILL) {
    digitalWrite(fill_out, HIGH);
  } else {
    digitalWrite(fill_out, LOW);
  }

  if(switchstate.VENT) {
    digitalWrite(vent_out, HIGH);
  } else {
    digitalWrite(vent_out, LOW);
  }

  if(switchstate.MOV) {
    digitalWrite(mov_out, HIGH);
  } else {
    digitalWrite(mov_out, LOW);
  }

  if(switchstate.PYRO1) {
    digitalWrite(pyro_1_fire, HIGH);
  } else {
    digitalWrite(pyro_1_fire, LOW);
  }

  if(switchstate.PYRO2) {
    //digitalWrite(LEDPIN,HIGH);
    digitalWrite(pyro_2_fire,HIGH);
  } else {
    //digitalWrite(LEDPIN,LOW);
    digitalWrite(pyro_2_fire,LOW);
  }

  if (switchstate.ARM) { // if data arming switch is on, fast data rate
    digitalWrite(arm_out, HIGH);
    dt_data = dt_data_fast;
    dt_lc = dt_lc_fast;
  } else { // else data arming switch is off, slow data rate
    dt_data = dt_sd_slow;
    dt_lc = dt_sd_slow;
  }
  
}

void ABORT_DAQ(void) { // ABORT ====================================================== 
  
  // Reset control to safe state
  digitalWrite(fill_out, LOW);
  digitalWrite(vent_out, HIGH);
  //digitalWrite(vent_out, LOW);
  digitalWrite(pyro_1_fire,HIGH);
  digitalWrite(pyro_2_fire,HIGH);
  
  // Log abort in data
  //Serial.println("ABORT TRIGGERED");

  // Wait for switchstate transmission, do not break until switch payload received
  while (true)
  {
    tone(buzzerPin, 4750);
    delay(1000);
    noTone(buzzerPin);
    delay(1000);
    if (rf95.available()) // if transmission is available again
    {
      last_time_rx = millis(); // reset  time of most recent transmission
      return; // exit abort
    }
  }
}

void setup() { // SETUP =================================================================================================
  Serial.begin(9600);
  // Sensor setup
  pinMode(CP1,INPUT); // Continuity pins digital input
  pinMode(CP2,INPUT);
  
  pinMode(PT_TANK,INPUT); // PT pins analog input 

  pinMode(lc_low_in,INPUT);
  pinMode(lc_high_in,INPUT);

  pinMode(fill_out,OUTPUT);
  pinMode(vent_out,OUTPUT);
  pinMode(mov_out,OUTPUT);
  pinMode(pyro_1_fire,OUTPUT);
  pinMode(pyro_2_fire,OUTPUT);
  pinMode(arm_out,OUTPUT);

  pinMode(buzzerPin,OUTPUT);

  digitalWrite(pyro_1_fire, LOW);
  digitalWrite(pyro_2_fire, LOW);
  digitalWrite(fill_out, LOW);
  digitalWrite(vent_out, HIGH);
  digitalWrite(mov_out, LOW);
  //digitalWrite(spare1_out, LOW);
  digitalWrite(arm_out, LOW);

  // Radio transceiver set up
  pinMode(RADIO_LED, OUTPUT);
  digitalWrite(RADIO_LED, LOW);
  delay(1000);
  digitalWrite(RADIO_LED, HIGH);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  //Serial.println("Arduino LoRa RX Test!");
  
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  while (!rf95.init()) {
    //Serial.println("LoRa radio init failed");
    //while (1);
    break;
  }
  //Serial.println("LoRa radio init OK!");

  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(RF95_FREQ)) {
    //Serial.println("setFrequency failed");
    //while (1);
  }
  //Serial.print("Set Freq to: "); Serial.println(RF95_FREQ);

  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on

  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  rf95.setTxPower(5, false);

  delay(1000); // delay for begin
}

void loop() { // LOOP =================================================================================================
  

  // Read sensor data
  if (millis()-last_time_data > dt_data) { // Check time between data readings
    C1bool = !digitalRead(CP1); // Continuity channel 1
    C2bool = !digitalRead(CP2); // Continuity channel 2
    PT_tank = analogRead(PT_TANK); // PT channel 1
    
    lc_low = pulseIn(lc_low_in, HIGH, 10000L);
    lc_high = pulseIn(lc_high_in, HIGH, 10000L); // Load cell
    Serial.print(PT_tank); Serial.print(", H:"); Serial.print(highByte(PT_tank)); Serial.print(", L:");  Serial.println(lowByte(PT_tank));
    
    batt_volt = analogRead(batt_volt_mon);// * 0.01700550500; //0.016917293233

    // Send states to teensy
    if(switchstate.ARM == 1) {
      digitalWrite(arm_out, HIGH);
      dt_rx = dt_rx_fast;
      rf95.setTxPower(23, false);

      if(switchstate.PYRO1 == 0) {
        digitalWrite(pyro_1_fire, LOW);
      } 
      if(switchstate.PYRO2 == 0) {
        digitalWrite(pyro_2_fire, LOW);
      } 
    } else {
      digitalWrite(arm_out, LOW);
      dt_rx = dt_rx_slow;
      rf95.setTxPower(5, false);
    }

    if(switchstate.PYRO1 == 1) {
      digitalWrite(pyro_1_fire, HIGH);
    }
    if(switchstate.PYRO2 == 1) {
      digitalWrite(pyro_2_fire, HIGH);
    }

    last_time_data = millis(); // Record time of data reading
  }
  
  // TRANSCEIVER CODE ====================================================================================================
  
  if (rf95.available()) {

    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);

    if (millis()-last_time_rx > dt_rx) { 
      if (rf95.recv(buf, &len)) {
        switchstate.FILL = buf[0];
        switchstate.VENT = buf[1];
        switchstate.MOV = buf[2];
        switchstate.SW4 = buf[3];
        switchstate.PYRO1 = buf[4];
        switchstate.PYRO2 = buf[5];
        switchstate.ARM = buf[6];
        switchstate.BU3 = buf[7];
        switchstate.BU4 = buf[8];

        uint8_t data[] = {C1bool, C2bool, lc_high, lc_low, highByte(PT_tank), lowByte(PT_tank), highByte(batt_volt), lowByte(batt_volt)};
        //uint8_t data[] = {C1bool, C2bool, LCint, PT_tank, highByte(batt_volt), lowByte(batt_volt), 69, 69, 69, 69};
        rf95.send(data, sizeof(data));
        rf95.waitPacketSent();
        digitalWrite(RADIO_LED, LOW);
      } else {
        //Serial.println("Receive failed");
        digitalWrite(RADIO_LED, HIGH);
      }
      // DECODE SWITCH STATE ====================================================================================================
      decodestate(switchstate); // Call function to decode switchstate and issue control commands
      last_time_rx = millis(); // save new time of most recent transmission
    }
    
  }
  
  // AUTO ABORT
  // if the last received transmission happened longer than abort time ago
  if (millis() - last_time_rx > 60000){ABORT_DAQ();}

  if(switchstate.ARM){
    tone(buzzerPin, 4750);
  } else {
    noTone(buzzerPin);
  }
}
