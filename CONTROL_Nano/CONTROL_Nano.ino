/// nRF24L01+PA+LNA BIDIRECTIONAL TEST
// CONTROL STATION

#include <SPI.h>
#include <LiquidCrystal.h>
#include "printf.h"
#include <RH_RF95.h>

// LCD Pins
#define RS 6
#define EN 7
#define D4 5
#define D5 4
#define D6 3
#define D7 1

// Control switches and buttons pins
#define SWP1 A0
#define SWP2 A1
#define SWP3 A2
#define SWP4 A3
#define BUP1 A4
#define BUP2 A5
#define BUP3 A6
#define BUP4 A7
#define DAP1 8

float batt_volt;
unsigned long startLoopTime = 0;

// Layer 1 - Teensy collects and sends to DAQ Nano
struct __attribute__((packed)) TSY_Payload // Payload from teensy
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
  uint32_t tsy_looptime = 0;
};
TSY_Payload tsy_pkt;

// Layer 2 - DAQ Nano adds its own fields, embeds TSY_Payload
struct __attribute__((packed)) DAQ_Payload  {
    uint32_t    daq_nano_timestamp;
    int8_t      daq_nanoRSSI;
    uint32_t    daq_looptime;
    TSY_Payload tsy;
};
DAQ_Payload daq_pkt;

// Layer 3 - Ctrl Nano adds its own fields, embeds DAQ_Payload
struct __attribute__((packed)) CTRL_Payload {
    uint32_t    ctrl_nano_timestamp;
    int8_t      ctrl_nanoRSSI;
    uint32_t    ctrl_looptime;
    DAQ_Payload daq;         // daq data appended
};
CTRL_Payload ctrl_pkt;



struct Switch_Payload // Payload from switches
{
  bool SW1 = 0; // SW1 
  bool SW2 = 0; // SW2 
  bool SW3 = 0; // SW3 
  bool SW4 = 0; // SW4 
  bool BU1 = 0; // BU1 
  bool BU2 = 0; // BU2 
  bool BU3 = 0; // BU3 
  bool BU4 = 0; // BU4 
  bool DA1 = 0; // SWD 
};

uint8_t switchstate[9];

#define RFM95_CS 9
#define RFM95_RST 10
#define RFM95_INT 2
#define RF95_FREQ 433.9869
int RFM95_PWR = 23;
RH_RF95 rf95(RFM95_CS, RFM95_INT);


bool CON_ERR = 0; // Track if there was successful transmission
bool RECV_ERR = 0;

// Loop parameters
const int dt_tx = 1000/30; // Loop transmission speed [ms]
const int dt_lcd = 100; // Loop lcd print speed [ms] 
long int last_time_tx = 0; // Last transmission completion time tracking [ms]
long int last_time_lcd = 0; // Last lcd time tracking [ms]
int switch_data_count = 0;

bool lowBattery = 0;
float maxThrust = 0;
float thisThrust = 0;

void readswitches(void) {
  switchstate[0] = !digitalRead(SWP1); // get state of switch 1 for transmission
  switchstate[1] = digitalRead(SWP2); // get state of switch 2 for transmission
  switchstate[2] = !digitalRead(SWP3); // mov
  switchstate[3] = !digitalRead(SWP4); // get state of switch 4 for transmission
  switchstate[4] = !digitalRead(BUP1); // get state of button 1 for transmission
  switchstate[5] = !digitalRead(BUP2); // get state of button 2 for transmission
  switchstate[6] = !digitalRead(DAP1); // get state of button D for transmission


  if (analogRead(BUP3) > 511)           // get state of button 3 for transmission (uses analog input pin)
    switchstate[7] = 0; // high reading
  else
    switchstate[7] = 1; // low reading

  if (analogRead(BUP4) > 511)           // get state of button 4 for transmission (uses analog input pin)
    switchstate[8] = 0; // high reading
  else
    switchstate[8] = 1; // low reading
}

void setup() {
  Serial.begin(9600);
  // LCD setup
  //lcd.begin(16,2); // LCD has 16 cols, 2 rows
  //lcd.setCursor(0,0); // Set cursor at beginning
  //lcd.print("Sup..."); // Print startup message
  //lcd.setCursor(0,1); // Set cursor at beginning of second row
  //lcd.print("Starting Radio");
  //delay(1000);
  // Arduino setup
  pinMode(SWP1,INPUT_PULLUP); // Switch 1 pin
  pinMode(SWP2,INPUT_PULLUP); // Switch 2 pin
  pinMode(SWP3,INPUT_PULLUP); // Switch 3 pin
  pinMode(SWP4,INPUT_PULLUP); // Switch 4 pin
  pinMode(BUP1,INPUT_PULLUP); // Button 1 pin
  pinMode(BUP2,INPUT_PULLUP); // Button 2 pin
  pinMode(BUP3,INPUT);        // Button 3 pin
  pinMode(BUP4,INPUT);        // Button 4 pin
  pinMode(DAP1,INPUT); // Data Arming Switch pin

  // Radio trasnceiver setup
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  //manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  while (!rf95.init()) {
    //lcd.clear(); 
    //lcd.setCursor(0,0);
    //lcd.print("Radio Failed! :(");
    while (1);
  }
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(RF95_FREQ)) {
    //lcd.clear();
    //lcd.setCursor(0,0);
    //lcd.print("setFrequency failed! :(");
    while (1);
  }
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  rf95.setTxPower(RFM95_PWR, false);

  //lcd.clear();
  //lcd.setCursor(0,0);
  //lcd.print("Set Freq to: "); lcd.print(RF95_FREQ);
  //lcd.setCursor(0,1);
  //lcd.print("Radio Power: "); lcd.print(RFM95_PWR);
  //delay(1000); 

  //lcd.clear();
  //lcd.setCursor(0,0);
  //lcd.print("Startup");
  //lcd.setCursor(0,1);
  //lcd.print("Complete");
  //delay(1000); // delay for begin
}

void loop() {
  // TRANSCEIVER CODE ====================================================================================================
  startLoopTime = micros();

  if (millis()-last_time_tx > dt_tx) { 
    readswitches(); // record state of switches
    rf95.send(switchstate, sizeof(switchstate));

    CON_ERR = 0;// connection error bool to false
    rf95.waitPacketSent();
    // Now wait for a reply

    
    
    
    
  }

  handle_telemetry();

  ctrl_pkt.ctrl_looptime = micros() - startLoopTime;
}
