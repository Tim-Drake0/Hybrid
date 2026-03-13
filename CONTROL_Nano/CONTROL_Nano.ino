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
#define FILL A0
#define VENT A1
#define MOV A2
#define SW4 A3
#define PY1 A4
#define PY2 A5
#define SW5 A6
#define SW6 A7
#define ARM 8

float batt_volt;
unsigned long startLoopTime = 0;

// Layer 1 - Teensy collects and sends to DAQ Nano
struct __attribute__((packed)) TSY_Payload // Payload from teensy
{
  uint32_t timestamp = 0; 
  uint8_t valve_states = 0;
  uint8_t pyro_states = 0;
  uint8_t arm_state = 0;
  uint8_t sensor_states = 0;
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
    uint32_t    ctrl_sendtime;
    uint32_t    ctrl_waittime;
    DAQ_Payload daq;         // daq data appended
};
CTRL_Payload ctrl_pkt;


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
  sw_pkt.fill = !digitalRead(FILL);
  sw_pkt.vent =  digitalRead(VENT); 
  sw_pkt.mov  = !digitalRead(MOV); 
  sw_pkt.SW4  = !digitalRead(SW4); 
  sw_pkt.py1  = !digitalRead(PY1); 
  sw_pkt.py2  = !digitalRead(PY2); 
  sw_pkt.arm  = !digitalRead(ARM); 

  if (analogRead(SW5) > 511)           // get state of button 3 for transmission (uses analog input pin)
    sw_pkt.SW5 = 0; // high reading
  else
    sw_pkt.SW5 = 1; // low reading

  if (analogRead(SW6) > 511)           // get state of button 4 for transmission (uses analog input pin)
    sw_pkt.SW6 = 0; // high reading
  else
    sw_pkt.SW6 = 1; // low reading
}

void setup() {
  Serial.begin(115200);
  // LCD setup
  //lcd.begin(16,2); // LCD has 16 cols, 2 rows
  //lcd.setCursor(0,0); // Set cursor at beginning
  //lcd.print("Sup..."); // Print startup message
  //lcd.setCursor(0,1); // Set cursor at beginning of second row
  //lcd.print("Starting Radio");
  //delay(1000);
  // Arduino setup
  pinMode(FILL,INPUT_PULLUP);
  pinMode(VENT,INPUT_PULLUP);
  pinMode(MOV,INPUT_PULLUP); 
  pinMode(SW4,INPUT_PULLUP); 
  pinMode(PY1,INPUT_PULLUP); 
  pinMode(PY2,INPUT_PULLUP); 
  pinMode(SW5,INPUT);        
  pinMode(SW6,INPUT);        
  pinMode(ARM,INPUT); 

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
  rf95.setSpreadingFactor(7);
  rf95.setSignalBandwidth(250000);  // 250kHz 

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
    unsigned long t1 = micros();
    CON_ERR = handle_telemetry(&sw_pkt, sizeof(sw_pkt));
    
    unsigned long t2 = micros();

    handle_serial();
    unsigned long t3 = micros();

    last_time_tx = millis();

    ctrl_pkt.ctrl_sendtime = t2-t1;
    ctrl_pkt.ctrl_waittime = t3 - t2;
  }

  ctrl_pkt.ctrl_looptime = micros() - startLoopTime;
}
